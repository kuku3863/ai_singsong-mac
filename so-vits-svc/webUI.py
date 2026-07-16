import os
import sys
import argparse
import glob
import json
import logging
import subprocess
import traceback
import re
import datetime
import time
import tempfile
import shutil
import asyncio
import html as html_lib
from urllib.parse import quote
from pathlib import Path

import gradio as gr
import librosa
import numpy as np
import soundfile

from inference.infer_tool import Svc
from compress_model import removeOptimizer
from pedalboard import Pedalboard, Reverb, Delay

logging.getLogger('numba').setLevel(logging.WARNING)
logging.getLogger('markdown_it').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

logs_root = "logs"
# 全局变量
model = None
debug = False
last_vocal_output = None
last_bgm_path = None

def _atomic_write_wav(path, audio, sr):
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".wav", dir=out_dir)
    os.close(fd)
    try:
        soundfile.write(tmp_path, audio, sr, format="wav")
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _atomic_ffmpeg_to_mp3(in_wav_path, out_mp3_path):
    out_dir = os.path.dirname(os.path.abspath(out_mp3_path))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".mp3", dir=out_dir)
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-i", in_wav_path, "-y", "-acodec", "libmp3lame", "-q:a", "2", tmp_path],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        os.replace(tmp_path, out_mp3_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _build_audio_players_html(file_paths, elem_prefix: str):
    if not file_paths:
        return "<div class='audio_list'></div>"
    rows = []
    for i, p in enumerate(file_paths):
        if not p:
            continue
        try:
            p_abs = os.path.abspath(p)
        except Exception:
            p_abs = p
        p_enc = quote(p_abs, safe="")
        p_url = "/gradio_api/file=" + p_enc
        p_url_fallback = "/file=" + p_enc
        file_name = html_lib.escape(os.path.basename(p_abs))
        audio_id = f"{elem_prefix}_{i}"
        rows.append(
            f"""
<div class="audio_row">
  <a class="audio_file_link" href="{p_url}" target="_blank" rel="noopener noreferrer">{file_name}</a>
  <audio id="{audio_id}" controls preload="none" src="{p_url}" onerror="(function(el){{if(el && el.src && !el.__fallback){{el.__fallback=true; el.src='{p_url_fallback}'; el.load();}}}})(this)"></audio>
  <div class="playback_controls">
    <button type="button" onclick="(function(btn){{const root=btn.getRootNode(); const a=root && root.querySelector('#{audio_id}'); if(a){{a.playbackRate=0.5;}}}})(this)">0.5x</button>
    <button type="button" onclick="(function(btn){{const root=btn.getRootNode(); const a=root && root.querySelector('#{audio_id}'); if(a){{a.playbackRate=1.0;}}}})(this)">1x</button>
    <button type="button" onclick="(function(btn){{const root=btn.getRootNode(); const a=root && root.querySelector('#{audio_id}'); if(a){{a.playbackRate=2.0;}}}})(this)">2x</button>
  </div>
</div>
""".strip()
        )
    inner = "\n".join(rows)
    return f"<div class='audio_list'>{inner}</div>"

def convert_to_safe_wav(input_path):
    if not input_path or not os.path.exists(input_path):
        return None
    try:
        cache_dir = os.path.join("results", "temp_cache")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        safe_filename = f"safe_{int(time.time()*1000)}_{base_name.encode('ascii', 'ignore').decode('ascii') or 'audio'}.wav"
        safe_audio_path = os.path.join(cache_dir, safe_filename)
        safe_audio_path = os.path.abspath(safe_audio_path)
        cmd = ["ffmpeg", "-i", input_path, "-acodec", "pcm_s16le", "-ar", "44100", "-y", safe_audio_path]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not os.path.exists(safe_audio_path) or os.path.getsize(safe_audio_path) == 0:
             raise Exception("Converted file is missing or empty")
        time.sleep(0.2)
        return safe_audio_path
    except Exception as e:
        print(f"Error converting file {input_path}: {e}")
        return None

def remix_audio(vocal_vol, bgm_vol, output_format):
    global last_vocal_output, last_bgm_path, model
    
    if not last_vocal_output or not os.path.exists(last_vocal_output):
        return None, None, _build_audio_players_html([], "out_list_audio"), "⚠️ 无法重新混合：找不到上次生成的音频文件 (请先运行一次推理)"
        
    if not last_bgm_path or not os.path.exists(last_bgm_path):
        return None, None, _build_audio_players_html([], "out_list_audio"), "⚠️ 无法重新混合：找不到上次使用的伴奏文件"
        
    try:
        # Load Vocal
        vocal_audio, sr = librosa.load(last_vocal_output, sr=None)
        
        # Load BGM
        bgm_audio, _ = librosa.load(last_bgm_path, sr=sr)
        
        # Adjust lengths
        max_len = max(len(vocal_audio), len(bgm_audio))
        vocal_final = np.zeros(max_len)
        bgm_final = np.zeros(max_len)
        
        # Convert dB to linear
        vocal_gain = 10 ** (vocal_vol / 20)
        bgm_gain = 10 ** (bgm_vol / 20)
        
        vocal_final[:len(vocal_audio)] = vocal_audio * vocal_gain
        bgm_final[:len(bgm_audio)] = bgm_audio * bgm_gain
        
        # Mix
        mixed = vocal_final + bgm_final
        
        # Normalize
        max_amp = np.max(np.abs(mixed))
        if max_amp > 1.0:
            mixed = mixed / max_amp
            
        # Save
        base, ext = os.path.splitext(last_vocal_output)
        if "_mixed" in base:
            base = base.replace("_mixed", "")
            
        mix_out_path = f"{base}_remix_v{vocal_vol}_b{bgm_vol}.wav"
        _atomic_write_wav(mix_out_path, mixed, sr)
        
        final_path = mix_out_path
        if output_format == "mp3":
            mp3_path = mix_out_path.replace(".wav", ".mp3")
            _atomic_ffmpeg_to_mp3(mix_out_path, mp3_path)
            final_path = mp3_path
            
        results = [final_path]
        players_html = _build_audio_players_html(results, "out_list_audio")
        return results, final_path, players_html, f"👉 重新混合成功: {final_path}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, _build_audio_players_html([], "out_list_audio"), f"⚠️ 重新混合失败: {e}"

cuda = {}
if sys.platform == 'win32':
    try:
        from torch import cuda as torch_cuda
        if torch_cuda.is_available():
            for i in range(torch_cuda.device_count()):
                cuda[f"cuda:{i}"] = torch_cuda.get_device_name(i)
    except Exception:
        pass

def debug_change():
    global debug
    debug = debug_button.value

def get_speaker_folders():
    if not os.path.exists(logs_root):
        return []
    folders = [f for f in os.listdir(logs_root) if os.path.isdir(os.path.join(logs_root, f))]
    # 过滤掉一些明显的非说话人目录，比如 eval
    folders = [f for f in folders if f not in ['eval', 'backups']]
    return sorted(folders)

def get_models_in_folder(folder):
    if not folder:
        return [], []
    path = os.path.join(logs_root, folder)
    if not os.path.exists(path):
        return [], []
    
    # 推理只使用 G 模型
    g_pths = glob.glob(os.path.join(path, "G_*.pth"))
    # 提取步数并排序
    def get_step(p):
        match = re.search(r'G_(\d+)\.pth', p)
        return int(match.group(1)) if match else -1
    
    g_pths = sorted(g_pths, key=get_step, reverse=True)
    g_names = [os.path.basename(p) for p in g_pths]
    
    # 查找扩散模型
    diff_path = os.path.join(path, "diffusion")
    diff_names = ["无"]
    if os.path.exists(diff_path):
        diff_pths = glob.glob(os.path.join(diff_path, "model_*.pt"))
        # 排序扩散模型
        def get_diff_step(p):
            match = re.search(r'model_(\d+)\.pt', p)
            return int(match.group(1)) if match else -1
        diff_pths = sorted(diff_pths, key=get_diff_step, reverse=True)
        diff_names += [os.path.join("diffusion", os.path.basename(p)) for p in diff_pths]
        
    return g_names, diff_names

def on_speaker_change(speaker):
    g_names, diff_names = get_models_in_folder(speaker)
    # 自动选择步数最大的 G 模型
    default_g = g_names[0] if g_names else None
    # 自动查找该目录下的 config.json
    config_path = os.path.join(logs_root, speaker, "config.json")
    config_status = "找到 config.json" if os.path.exists(config_path) else "未找到 config.json"
    
    # 查找扩散配置
    diff_config = "无"
    diff_config_path = os.path.join(logs_root, speaker, "diffusion", "config.yaml")
    if os.path.exists(diff_config_path):
        diff_config = os.path.join("diffusion", "config.yaml")

    return (
        gr.Dropdown(choices=g_names, value=default_g),
        gr.Dropdown(choices=diff_names, value="无"),
        gr.Dropdown(choices=["config.json"] if os.path.exists(config_path) else ["无"], value="config.json" if os.path.exists(config_path) else "无"),
        gr.Dropdown(choices=[diff_config] if diff_config != "无" else ["无"], value=diff_config),
        f"已切换至 {speaker}，{config_status}"
    )

def modelAnalysis(speaker, model_name, config_name, cluster_model_path, device, enhance, diff_model_name, diff_config_name, only_diffusion, use_spk_mix):
    global model
    try:
        if not speaker or not model_name:
            return "请先选择说话人文件夹和模型文件", gr.Dropdown(choices=[])
            
        device = None if device == "Auto" else device
        speaker_path = os.path.join(logs_root, speaker)
        
        model_path = os.path.join(speaker_path, model_name)
        config_path = os.path.join(speaker_path, config_name)
        
        diff_model_path = None
        if diff_model_name != "无":
            diff_model_path = os.path.join(speaker_path, diff_model_name)
            
        diff_config_path = None
        if diff_config_name != "无":
            diff_config_path = os.path.join(speaker_path, diff_config_name)

        if not os.path.exists(model_path) or not os.path.exists(config_path):
            return f"模型或配置路径错误: {model_path}", gr.Dropdown(choices=[])
        
        model = Svc(model_path, 
                    config_path, 
                    device=device, 
                    cluster_model_path=cluster_model_path.name if cluster_model_path else "", 
                    nsf_hifigan_enhance=enhance,
                    diffusion_model_path=diff_model_path if diff_model_path else "",
                    diffusion_config_path=diff_config_path if diff_config_path else "",
                    shallow_diffusion=True if diff_model_path else False,
                    only_diffusion=only_diffusion,
                    spk_mix_enable=use_spk_mix)
        
        spks = list(model.spk2id.keys())
        return "模型加载成功", gr.Dropdown(choices=spks, value=spks[0])
    except Exception as e:
        if debug:
            traceback.print_exc()
        return f"加载失败: {str(e)}", gr.Dropdown(choices=[])

def modelUnload():
    global model
    model = None
    return "模型已卸载", gr.Dropdown(choices=[], value=None)

def vc_infer(output_format, sid, input_audio, truncated_basename, vc_transform, auto_f0, cluster_ratio, slice_db, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity):
    global model, last_vocal_output
    _audio = model.slice_inference(input_audio, sid, vc_transform, slice_db, cluster_ratio, auto_f0, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment)
    
    # 音效处理
    if reverb_intensity > 0 or delay_intensity > 0:
        # Ensure audio is 2D (channels, samples) for pedalboard
        audio_for_pedal = _audio.reshape(1, -1) if _audio.ndim == 1 else _audio
        sr = model.target_sample
        
        if reverb_intensity > 0:
            room_size_map = (0.20, 0.55, 0.95)
            wet_level_map = (0.02, 0.12, 0.50)
            dry_level_map = (0.95, 0.85, 0.50)
            
            def interpolate(value, mapping):
                if value <= 4: return mapping[0] + (mapping[1] - mapping[0]) * (value / 4.0)
                else: return mapping[1] + (mapping[2] - mapping[1]) * ((value - 4.0) / 6.0)
                
            room_size = interpolate(reverb_intensity, room_size_map)
            wet_level = interpolate(reverb_intensity, wet_level_map)
            dry_level = interpolate(reverb_intensity, dry_level_map)
            
            board = Pedalboard([Reverb(room_size=room_size, wet_level=wet_level, dry_level=dry_level)])
            audio_for_pedal = board(audio_for_pedal, sr)
            
        if delay_intensity > 0:
            try:
                y_mono = librosa.to_mono(audio_for_pedal)
                tempo, _ = librosa.beat.beat_track(y=y_mono[:sr*30], sr=sr)
                if isinstance(tempo, (list, np.ndarray)): tempo = tempo[0]
                if tempo < 40 or tempo > 220: tempo = 120
                delay_time = 60.0 / tempo
            except:
                delay_time = 0.5
                
            feedback = 0.1 + (0.5 * (delay_intensity / 10.0))
            mix = 0.05 + (0.35 * (delay_intensity / 10.0))
            
            board = Pedalboard([Delay(delay_seconds=delay_time, feedback=feedback, mix=mix)])
            audio_for_pedal = board(audio_for_pedal, sr)
        
        _audio = audio_for_pedal.flatten()

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    key = "Z" if vc_transform >= 0 else "F"
    key += str(abs(vc_transform))
    cluster = f"_cluster_{cluster_ratio}" if cluster_ratio > 0 else ""
    isdiffusion = "_diff" if model.shallow_diffusion else ""
    
    if auto_filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_name = f'result_{timestamp}_{truncated_basename}_{sid}_{key}{cluster}{isdiffusion}.{output_format}'
    else:
        output_file_name = f'result_{truncated_basename}_{sid}_{key}{cluster}{isdiffusion}.{output_format}'
        
    output_file = os.path.join(output_folder, output_file_name)
    soundfile.write(output_file, _audio, model.target_sample, format=output_format)
    last_vocal_output = output_file
    return output_file

def vc_fn(sid, input_audio, bgm_path, output_format, vc_transform, auto_f0,cluster_ratio, slice_db, noise_scale,pad_seconds,cl_num,lg_num,lgr_num,f0_predictor,enhancer_adaptive_key,cr_threshold,k_step,use_spk_mix,second_encoding,loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity):
    global model, last_bgm_path
    try:
        if input_audio is None:
            return "请上传音频", None
        if model is None:
            return "请先加载模型", None
        
        last_bgm_path = bgm_path # 记录伴奏路径

        audio, sampling_rate = soundfile.read(input_audio)
        if np.issubdtype(audio.dtype, np.integer):
            audio = (audio / np.iinfo(audio.dtype).max).astype(np.float32)
        if len(audio.shape) > 1:
            audio = librosa.to_mono(audio.transpose(1, 0))
            
        truncated_basename = Path(input_audio).stem
        processed_audio = os.path.join("raw", f"{truncated_basename}.wav")
        if not os.path.exists("raw"): os.makedirs("raw")
        soundfile.write(processed_audio, audio, sampling_rate, format="wav")
        
        output_file = vc_infer(output_format, sid, processed_audio, truncated_basename, vc_transform, auto_f0, cluster_ratio, slice_db, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity)

        return "转换成功", output_file
    except Exception as e:
        if debug: traceback.print_exc()
        raise gr.Error(e)

SUPPORTED_LANGUAGES = ["Auto", "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunxiNeural", "zh-CN-YunjianNeural", "zh-CN-XiaochenNeural", "zh-CN-XiaohanNeural", "zh-CN-XiaomengNeural", "zh-CN-XiaomoNeural", "zh-CN-XiaoqiuNeural", "zh-CN-XiaoruiNeural", "zh-CN-XiaoshuangNeural", "zh-CN-XiaoxuanNeural", "zh-CN-XiaozhenNeural", "zh-CN-YunfengNeural", "zh-CN-YunhaoNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyeNeural", "zh-CN-YunzeNeural", "zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural", "zh-TW-HsiaoYuNeural", "zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural"]

def vc_fn2(_text, _lang, _gender, _rate, _volume, sid, output_format, vc_transform, auto_f0,cluster_ratio, slice_db, noise_scale,pad_seconds,cl_num,lg_num,lgr_num,f0_predictor,enhancer_adaptive_key,cr_threshold, k_step,use_spk_mix,second_encoding,loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity):
    global model
    try:
        if model is None: return "请先加载模型", None
        _rate = f"+{int(_rate*100)}%" if _rate >= 0 else f"{int(_rate*100)}%"
        _volume = f"+{int(_volume*100)}%" if _volume >= 0 else f"{int(_volume*100)}%"
        if _lang == "Auto":
            _gender = "Male" if _gender == "男" else "Female"
            subprocess.run([sys.executable, "edgetts/tts.py", _text, _lang, _rate, _volume, _gender])
        else:
            subprocess.run([sys.executable, "edgetts/tts.py", _text, _lang, _rate, _volume])
        target_sr = 44100
        y, sr = librosa.load("tts.wav")
        resampled_y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        soundfile.write("tts.wav", resampled_y, target_sr, subtype = "PCM_16")
        output_file_path = vc_infer(output_format, sid, "tts.wav", "tts", vc_transform, auto_f0, cluster_ratio, slice_db, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity)
        os.remove("tts.wav")
        return "转换成功", output_file_path
    except Exception as e:
        if debug: traceback.print_exc()
        raise gr.Error(e)

theme = gr.themes.Base(
    primary_hue = gr.themes.colors.green,
    font=[gr.themes.Font("Microsoft YaHei"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=['JetBrains mono', "Consolas", 'Courier New']
)

with gr.Blocks(theme=theme) as app:
    gr.Markdown("### So-vits-svc 4.0 推理面板 (智能读取 Logs)")
    
    with gr.Row():
        with gr.Column(scale=4):
            with gr.Row(variant="panel"):
                with gr.Column():
                    gr.Markdown("#### 1. 选择说话人目录")
                    with gr.Row():
                        speaker_folder = gr.Dropdown(label="说话人文件夹 (logs/)", choices=get_speaker_folders(), interactive=True)
                        refresh_button = gr.Button("🔄 刷新目录", variant="secondary", size="sm")
                    
                    gr.Markdown("#### 2. 模型与配置 (自动读取)")
                    with gr.Row():
                        model_selection = gr.Dropdown(label='G 模型文件 (推理必选)', choices=[], interactive=True)
                        config_selection = gr.Dropdown(label='配置文件', choices=[], interactive=True)
                    
                    with gr.Row():
                        diff_model_selection = gr.Dropdown(label="（可选）扩散模型", choices=[], value="无", interactive=True)
                        diff_config_selection = gr.Dropdown(label="（可选）扩散配置", choices=[], value="无", interactive=True)
                    
                    cluster_model_path = gr.File(label="（可选）上传聚类/特征检索模型", height=100)
                    
                    with gr.Row():
                        device = gr.Dropdown(label="设备", choices=["Auto",*cuda.keys(),"cpu"], value="Auto")
                        enhance = gr.Checkbox(label="NSF_HIFIGAN增强", value=False)
                        only_diffusion = gr.Checkbox(label="全扩散推理", value=False)
                        use_spk_mix = gr.Checkbox(label="声线融合", value=False)
                
                with gr.Column():
                    gr.Markdown("#### 3. 加载控制")
                    model_load_button = gr.Button(value="加载模型", variant="primary")
                    model_unload_button = gr.Button(value="卸载模型")
                    sid = gr.Dropdown(label="音色（说话人）", choices=[])
                    sid_output = gr.Textbox(label="加载状态", placeholder="请先选择目录并加载...")
                    
                    gr.Markdown("#### 4. 推理参数")
                    with gr.Row():
                        auto_f0 = gr.Checkbox(label="自动f0预测", value=False)
                        f0_predictor = gr.Dropdown(label="F0预测器", choices=["pm","dio","harvest","crepe","rmvpe","fcpe"], value="pm")
                    vc_transform = gr.Number(label="变调 (12为高八度)", value=0)
                    cluster_ratio = gr.Slider(label="聚类比例", minimum=0, maximum=1, value=0, step=0.1)
                    noise_scale = gr.Number(label="noise_scale", value=0.4)
                    k_step = gr.Slider(label="扩散步数", value=100, minimum = 1, maximum = 1000)

        with gr.Column(scale=3):
            gr.Markdown("#### 5. 转换与输出")
            with gr.Tabs():
                with gr.TabItem("🎵 音频转音频"):
                    vc_input3 = gr.Audio(label="上传人声音频", type="filepath")
                    bgm_input = gr.Audio(label="（可选）上传伴奏音频", type="filepath")
                    vc_submit = gr.Button("开始转换", variant="primary")
                with gr.TabItem("📝 文字转音频"):
                    text2tts = gr.Textbox(label="输入文字", lines=3)
                    with gr.Row():
                        tts_gender = gr.Radio(label="性别", choices=["男","女"], value="男")
                        tts_lang = gr.Dropdown(label="语言", choices=SUPPORTED_LANGUAGES, value="Auto")
                    with gr.Row():
                        tts_rate = gr.Slider(label="语速", minimum=-1, maximum=3, value=0, step=0.1)
                        tts_volume = gr.Slider(label="音量", minimum=-1, maximum=1.5, value=0, step=0.1)
                    vc_submit2 = gr.Button("开始 TTS 转换", variant="primary")
            
            vc_output1 = gr.Textbox(label="转换状态")
            vc_output2 = gr.Audio(label="输出结果", interactive=False)
            
            with gr.Accordion("合成伴奏 (Remix)", open=False):
                with gr.Row():
                    vocal_vol = gr.Slider(label="人声音量 (dB)", minimum=-20, maximum=20, value=0, step=0.5)
                    bgm_vol = gr.Slider(label="伴奏音量 (dB)", minimum=-20, maximum=20, value=0, step=0.5)
                remix_submit = gr.Button("重新混合伴奏", variant="secondary")
                remix_output_html = gr.HTML(label="混合结果列表")

            with gr.Accordion("高级特效设置", open=False):
                with gr.Row():
                    reverb_intensity = gr.Slider(label="混响", minimum=0, maximum=10, value=0)
                    delay_intensity = gr.Slider(label="回声", minimum=0, maximum=10, value=0)
                effect_mode = gr.Dropdown(label="预设特效", choices=["无 (None)", "混响 (Reverb)", "空洞 (Hollow)", "空灵 (Ethereal)"], value="无 (None)")
                output_format = gr.Radio(label="输出格式", choices=["wav", "flac", "mp3"], value="mp3")

    # 隐藏的参数组件
    slice_db = gr.Number(value=-40, visible=False)
    pad_seconds = gr.Number(value=0.5, visible=False)
    cl_num = gr.Number(value=0, visible=False)
    lg_num = gr.Number(value=0, visible=False)
    lgr_num = gr.Number(value=0.75, visible=False)
    enhancer_adaptive_key = gr.Number(value=0, visible=False)
    cr_threshold = gr.Number(value=0.05, visible=False)
    second_encoding = gr.Checkbox(value=False, visible=False)
    loudness_envelope_adjustment = gr.Number(value=1, visible=False)
    output_folder = gr.Textbox(value="results", visible=False)
    auto_filename = gr.Checkbox(value=True, visible=False)
    debug_button = gr.Checkbox(label="Debug模式", value=debug, visible=False)

    # 联动逻辑
    def refresh_speakers():
        return gr.Dropdown(choices=get_speaker_folders())

    refresh_button.click(refresh_speakers, [], [speaker_folder])

    speaker_folder.change(
        on_speaker_change, 
        inputs=[speaker_folder], 
        outputs=[model_selection, diff_model_selection, config_selection, diff_config_selection, sid_output]
    )

    model_load_button.click(
        modelAnalysis, 
        [speaker_folder, model_selection, config_selection, cluster_model_path, device, enhance, diff_model_selection, diff_config_selection, only_diffusion, use_spk_mix], 
        [sid_output, sid]
    )
    
    model_unload_button.click(modelUnload, [], [sid_output, sid])
    
    vc_submit.click(
        vc_fn, 
        [sid, vc_input3, bgm_input, output_format, vc_transform, auto_f0, cluster_ratio, slice_db, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity], 
        [vc_output1, vc_output2]
    )
    
    remix_submit.click(
        remix_audio,
        [vocal_vol, bgm_vol, output_format],
        [vc_output2, vc_output2, remix_output_html, vc_output1]
    )
    
    vc_submit2.click(
        vc_fn2, 
        [text2tts, tts_lang, tts_gender, tts_rate, tts_volume, sid, output_format, vc_transform, auto_f0, cluster_ratio, slice_db, noise_scale, pad_seconds, cl_num, lg_num, lgr_num, f0_predictor, enhancer_adaptive_key, cr_threshold, k_step, use_spk_mix, second_encoding, loudness_envelope_adjustment, output_folder, auto_filename, effect_mode, reverb_intensity, delay_intensity], 
        [vc_output1, vc_output2]
    )


app.launch()
