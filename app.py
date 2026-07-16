#!/usr/bin/env python3
"""
🎤 AI 翻唱统一系统
   RVC (Retrieval-based Voice Conversion) + So-VITS-SVC 双引擎
   一键翻唱 + 独立推理，Apple Silicon GPU 加速
"""

import os, sys, shutil, json, tempfile, argparse, traceback, time, glob as glob_mod, re, subprocess
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────
NOW_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(NOW_DIR)
sys.path.insert(0, NOW_DIR)

# Gradio imports httpx at module import time. If macOS has a SOCKS proxy in
# ALL_PROXY/all_proxy but the venv lacks socksio, the whole app exits before
# start.sh gets a chance to clean the environment.
for _proxy_var in ("ALL_PROXY", "all_proxy"):
    if os.environ.get(_proxy_var, "").lower().startswith("socks"):
        os.environ.pop(_proxy_var, None)
os.environ["NO_PROXY"] = ",".join(
    dict.fromkeys(
        ["127.0.0.1", "localhost", "::1"]
        + [p for p in os.environ.get("NO_PROXY", "").split(",") if p]
    )
)
os.environ["no_proxy"] = os.environ["NO_PROXY"]

OUTPUT_DIR = os.path.join(NOW_DIR, "output")
TEMP_DIR = os.path.join(NOW_DIR, "temp")
RVC_DIR = os.path.join(NOW_DIR, "rvc")
SVC_DIR = os.path.join(NOW_DIR, "so-vits-svc")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# RVC env
sys.path.insert(0, RVC_DIR)
os.environ.setdefault("weight_root", "assets/weights")
os.environ.setdefault("weight_uvr5_root", "assets/uvr5_weights")
os.environ.setdefault("index_root", "logs")
os.environ.setdefault("outside_index_root", "assets/indices")
os.environ.setdefault("rmvpe_root", "assets/rmvpe")

# SVC env
sys.path.insert(0, SVC_DIR)

# ── Imports ────────────────────────────────────────────────
import gradio as gr
import numpy as np
import librosa
import soundfile as sf
import torch

try:
    from pedalboard import Pedalboard, Reverb
    _HAS_PEDALBOARD = True
except ImportError:
    _HAS_PEDALBOARD = False

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RVC_DIR, ".env"))
except ImportError:
    pass

# ── Device ─────────────────────────────────────────────────
def detect_device():
    requested_device = os.environ.get("AI_COVER_DEVICE", "").strip().lower()
    if requested_device in {"cpu", "mps", "cuda", "cuda:0"}:
        if requested_device == "cpu":
            return "cpu"
        if requested_device == "mps":
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                try:
                    torch.zeros(1).to(torch.device("mps"))
                    return "mps"
                except Exception:
                    return "cpu"
        if requested_device.startswith("cuda") and torch.cuda.is_available():
            return "cuda:0"

    if torch.cuda.is_available():
        return "cuda:0"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        try:
            torch.zeros(1).to(torch.device("mps"))
            return "mps"
        except Exception:
            return "cpu"
    return "cpu"

DEVICE = detect_device()
# macOS: 解除 MPS 内存上限 + 主动 GC，防止大音频 OOM
if DEVICE == "mps":
    os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")
    os.environ.setdefault("PYTORCH_MPS_ALLOCATOR_POLICY", "garbage_collection")
print(f"🚀 AI 翻唱系统 | 设备: {DEVICE.upper()} | 工作目录: {NOW_DIR}")


def notify_done(title, message):
    """macOS sound + notification; no-op on unsupported environments."""
    if sys.platform != "darwin":
        return
    try:
        import subprocess
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        safe_title = str(title).replace("\\", "\\\\").replace('"', '\\"')
        safe_message = str(message).replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# ENGINE WRAPPERS
# ═══════════════════════════════════════════════════════════

class RVCEngine:
    def __init__(self):
        self.config = None
        self.vc = None
        self.loaded_model = None

    def _ensure_config(self):
        if self.config is None:
            os.chdir(RVC_DIR)
            from configs.config import Config
            self.config = Config()
            self.config.device = DEVICE
            if DEVICE == "mps":
                self.config.is_half = False

    def get_models(self):
        """扫描所有 RVC 模型: assets/weights/ 和 logs/ 下"""
        models = {}
        search_roots = [
            os.path.join(RVC_DIR, os.getenv("weight_root", "assets/weights")),  # 模型目录
            os.path.join(RVC_DIR, "logs"),  # 训练产生的模型
        ]
        for root in search_roots:
            if not os.path.exists(root):
                continue
            for f in os.listdir(root):
                fp = os.path.join(root, f)
                if f.endswith(".pth") and os.path.isfile(fp):
                    models[f] = fp
        return sorted(models.keys())

    def get_model_path(self, model_name):
        """根据模型名称找到完整路径"""
        search_roots = [
            os.path.join(RVC_DIR, os.getenv("weight_root", "assets/weights")),
            os.path.join(RVC_DIR, "logs"),
        ]
        for root in search_roots:
            fp = os.path.join(root, model_name)
            if os.path.exists(fp):
                return fp
        return os.path.join(RVC_DIR, "assets/weights", model_name)

    def get_indices(self):
        """扫描所有 RVC 索引文件"""
        indices = []
        for root_name in ["index_root", "outside_index_root"]:
            root = os.path.join(RVC_DIR, os.getenv(root_name, ""))
            if not os.path.exists(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if f.endswith(".index") and os.path.isfile(fp):
                        indices.append(fp)
        return sorted(indices)

    def find_matching_index(self, model_name):
        """根据 RVC 模型名自动匹配最可能的 FAISS 索引。"""
        if not model_name:
            return None

        model_base = os.path.splitext(os.path.basename(model_name))[0].lower()
        model_tokens = [t for t in re.split(r"[^a-z0-9]+", model_base) if t]
        if not model_tokens:
            return None

        best = (0, None)
        for index_path in self.get_indices():
            index_base = os.path.splitext(os.path.basename(index_path))[0].lower()
            index_tokens = [t for t in re.split(r"[^a-z0-9]+", index_base) if t]
            if not index_tokens:
                continue

            score = 0
            if index_tokens[:len(model_tokens)] == model_tokens:
                score += 100
            if model_base in index_base:
                score += 50
            if os.path.basename(index_path).startswith("added_"):
                score += 10
            if os.path.dirname(index_path).lower().endswith(f"/{model_base}"):
                score += 25

            if score > best[0]:
                best = (score, index_path)

        return best[1] if best[0] >= 50 else None

    def load_model(self, model_name):
        self._ensure_config()
        os.chdir(RVC_DIR)
        from infer.modules.vc.modules import VC
        self.vc = VC(self.config)
        # RVC's get_vc uses os.getenv("weight_root")/sid
        # model_name is just the filename like "binbin.pth"
        self.vc.get_vc(model_name)
        self.loaded_model = model_name

    def infer(self, model_name, input_path, f0_up_key=0, f0_method="rmvpe",
              index_path="", index_rate=0.75, filter_radius=3,
              resample_sr=0, rms_mix_rate=1.0, protect=0.33):
        self._ensure_config()
        os.chdir(RVC_DIR)
        # RVC get_vc uses weight_root/model_name internally
        if self.vc is None or self.loaded_model != model_name:
            self.load_model(model_name)
        _, result = self.vc.vc_single(
            0, input_path, f0_up_key, None, f0_method,
            index_path if index_path else "", None, index_rate, filter_radius,
            resample_sr, rms_mix_rate, protect,
        )
        return result


class SVCEngine:
    def __init__(self):
        self.model = None
        self.loaded_ckpt = None

    def get_models(self):
        """扫描所有 SVC 模型: logs/<singer>/G_*.pth"""
        models = {}
        logs_dir = os.path.join(SVC_DIR, "logs")
        if not os.path.exists(logs_dir):
            return []
        for singer in sorted(os.listdir(logs_dir)):
            singer_dir = os.path.join(logs_dir, singer)
            if not os.path.isdir(singer_dir):
                continue
            for f in os.listdir(singer_dir):
                if f.startswith("G_") and f.endswith(".pth"):
                    if f == "G_0.pth":
                        continue
                    display = f"{singer}/{f}"
                    models[display] = os.path.join(singer_dir, f)
        # Sort by mtime descending (latest first)
        return sorted(models.keys(), key=lambda k: os.path.getmtime(models.get(k, "")), reverse=True)

    def get_model_path(self, display_name):
        """根据显示名（singer/G_xxx.pth）找到完整路径"""
        if "/" in display_name:
            singer, fname = display_name.split("/", 1)
            return os.path.join(SVC_DIR, "logs", singer, fname)
        return os.path.join(SVC_DIR, display_name)

    def get_configs(self):
        configs = []
        for d in [os.path.join(SVC_DIR, "configs"),
                   os.path.join(SVC_DIR, "logs", "44k"),
                   os.path.join(SVC_DIR, "models")]:
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.endswith(".json"):
                        configs.append(os.path.join(d, f))
        return sorted(configs)

    def get_speakers(self, display_name=None):
        """获取指定 SVC 模型的说话人列表。"""
        models = self.get_models()
        if not display_name:
            display_name = models[0] if models else None
        if not display_name:
            return ["my_voice"]
        try:
            ckpt_path = self.get_model_path(display_name)
            config_path = os.path.join(os.path.dirname(ckpt_path), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    cfg = json.load(f)
                spk = cfg.get('spk', {})
                if spk:
                    return list(spk.keys())
        except Exception:
            pass
        return ["my_voice"]

    def normalize_speaker(self, display_name, spk_name=None):
        speakers = self.get_speakers(display_name)
        if spk_name in speakers:
            return spk_name
        return speakers[0] if speakers else "my_voice"

    def load_model(self, ckpt_path, config_path="configs/config.json", device=None):
        os.chdir(SVC_DIR)
        from inference.infer_tool import Svc
        if device is None:
            device = DEVICE
        self.model = Svc(
            ckpt_path, config_path, device=device,
            cluster_model_path="", nsf_hifigan_enhance=False,
            diffusion_model_path="", diffusion_config_path="",
            shallow_diffusion=False, only_diffusion=False,
            spk_mix_enable=False, feature_retrieval=False,
        )
        self.loaded_ckpt = ckpt_path

    def infer(self, display_name, input_path, spk="my_voice", tran=0,
              auto_predict_f0=False, cluster_infer_ratio=0, noise_scale=0.4,
              f0_predictor="rmvpe", slice_db=-45, pad_seconds=0.5):
        os.chdir(SVC_DIR)
        ckpt_path = self.get_model_path(display_name)
        if self.model is None or self.loaded_ckpt != ckpt_path:
            cfg = self._auto_config(ckpt_path)
            self.load_model(ckpt_path, cfg)
        audio = self.model.slice_inference(
            input_path, spk=spk, tran=tran, slice_db=slice_db,
            cluster_infer_ratio=cluster_infer_ratio,
            auto_predict_f0=auto_predict_f0,
            noice_scale=noise_scale, pad_seconds=pad_seconds,
            f0_predictor=f0_predictor,
        )
        return audio

    def _auto_config(self, ckpt_path):
        config_path = os.path.join(os.path.dirname(ckpt_path), "config.json")
        if os.path.exists(config_path):
            return config_path
        return "configs/config.json"


# Singleton instances
_rvc = RVCEngine()
_svc = SVCEngine()


# ═══════════════════════════════════════════════════════════
# SHARED AUDIO UTILS
# ═══════════════════════════════════════════════════════════

def separate_vocal_safe(input_path):
    """人声分离 → 返回 (vocal_path, inst_path)
    优先使用 demucs-mlx 精细模式，失败后回退 RVC 内置分离。"""
    if not input_path or not os.path.exists(input_path):
        raise FileNotFoundError(f"输入音频不存在: {input_path}")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    vocal_path = os.path.join(TEMP_DIR, f"{base_name}_vocal.wav")
    inst_path = os.path.join(TEMP_DIR, f"{base_name}_inst.wav")
    for stale_path in (vocal_path, inst_path):
        if os.path.exists(stale_path):
            os.remove(stale_path)

    # ── 方法0: demucs-mlx (MLX + Metal GPU，高质量且在 Apple Silicon 上更稳定) ──
    try:
        os.chdir(RVC_DIR)
        from tabs.shared import _separate_with_vocal_separator

        sep_out = os.path.join(TEMP_DIR, f"{base_name}_demucs_mlx")
        result = _separate_with_vocal_separator(input_path, sep_out)
        if result.get("success") and result.get("vocal") and os.path.exists(result["vocal"]):
            shutil.copy(result["vocal"], vocal_path)
            if result.get("instr") and os.path.exists(result["instr"]):
                shutil.copy(result["instr"], inst_path)
            os.chdir(NOW_DIR)
            return vocal_path, inst_path
        print(f"   demucs-mlx 分离不可用，回退内置分离: {result.get('reason', '')}")
    except Exception as e:
        print(f"   demucs-mlx 分离失败: {e}")
        traceback.print_exc()
    finally:
        os.chdir(NOW_DIR)

    # ── 方法1: audio_tools SeparatorModel ──
    try:
        os.chdir(RVC_DIR)
        from audio_tools.separator_model import SeparatorModel, get_available_models

        models = get_available_models()
        if models:
            model_type = models[0]
            print(f"   使用分离模型: {model_type}")
            sep = SeparatorModel(model_type=model_type, device=DEVICE)
            result = sep.separate(input_path)
            # Result is a SeparationResult with .vocals and .other attributes
            if hasattr(result, 'vocals') and result.vocals and os.path.exists(result.vocals):
                shutil.copy(result.vocals, vocal_path)
            if hasattr(result, 'other') and result.other and os.path.exists(result.other):
                shutil.copy(result.other, inst_path)
            elif hasattr(result, 'vocals') and result.vocals:
                # If no "other" track, use the vocals as-is
                pass

        if os.path.exists(vocal_path):
            os.chdir(NOW_DIR)
            return vocal_path, inst_path
    except Exception as e:
        print(f"   SeparatorModel 分离失败: {e}")
        traceback.print_exc()
    finally:
        os.chdir(NOW_DIR)

    # ── 方法2: UVR5 ──
    try:
        os.chdir(RVC_DIR)
        from infer.modules.uvr5.modules import uvr
        import shutil as _shutil

        uvr_model = "onnx_dereverb_By_FoxJoy"
        uvr_out_dir = os.path.join(TEMP_DIR, "uvr5_output")
        os.makedirs(uvr_out_dir, exist_ok=True)

        print(f"   使用 UVR5: {uvr_model}")
        uvr(uvr_model, uvr_out_dir, uvr_out_dir, [input_path], uvr_out_dir, 10, "wav")

        # uvr outputs files to uvr_out_dir
        for f in os.listdir(uvr_out_dir):
            fp = os.path.join(uvr_out_dir, f)
            if not os.path.isfile(fp) or os.path.getsize(fp) < 1000:
                continue
            flow = f.lower()
            if "vocal" in flow or "main_vocal" in flow:
                _shutil.copy(fp, vocal_path)
            elif "inst" in flow or "instrument" in flow or "no_vocal" in flow:
                _shutil.copy(fp, inst_path)

        if os.path.exists(vocal_path):
            os.chdir(NOW_DIR)
            return vocal_path, inst_path
    except Exception as e:
        print(f"   UVR5 分离失败: {e}")
        traceback.print_exc()
    finally:
        os.chdir(NOW_DIR)

    # ── 降级: 整首当人声 ──
    print("   ⚠️ 降级：整首当作人声（无分离）")
    audio, sr = librosa.load(input_path, sr=None, mono=True)
    sf.write(vocal_path, audio, sr)
    sf.write(inst_path, np.zeros(int(sr * 0.5)), sr)
    os.chdir(NOW_DIR)
    return vocal_path, inst_path


def mix_tracks(vocal_path, inst_path, vocal_vol=0, inst_vol=0, fmt="mp3",
               reverb_enabled=False, reverb_room_size=0.5, reverb_wet=0.3,
               reverb_dry=0.8, reverb_damping=0.5):
    """混音 → 返回 output_path。支持可选的 Reverb 混响效果。"""
    v, sr = librosa.load(vocal_path, sr=None, mono=True)
    i, _ = librosa.load(inst_path, sr=sr, mono=True)

    # ── Reverb: 给人声添加空间感（仅作用于 AI 人声，不影响伴奏）──
    reverb_label = ""
    if reverb_enabled and _HAS_PEDALBOARD:
        try:
            board = Pedalboard([
                Reverb(
                    room_size=float(reverb_room_size),
                    damping=float(reverb_damping),
                    wet_level=float(reverb_wet),
                    dry_level=float(reverb_dry),
                    width=1.0,
                )
            ])
            v = board(v, sr)
            reverb_label = f" [Reverb: room={reverb_room_size:.1f} wet={reverb_wet:.1f}]"
        except Exception as e:
            print(f"   ⚠️ Reverb 处理失败，跳过: {e}")
    elif reverb_enabled and not _HAS_PEDALBOARD:
        print("   ⚠️ pedalboard 未安装，跳过混响处理")

    max_len = max(len(v), len(i))
    v = np.pad(v, (0, max_len - len(v))) * (10 ** (vocal_vol / 20))
    i = np.pad(i, (0, max_len - len(i))) * (10 ** (inst_vol / 20))
    mixed = v + i
    mx = np.abs(mixed).max()
    if mx > 0.99:
        mixed /= mx * 1.01

    base = os.path.splitext(os.path.basename(vocal_path))[0].replace("_vocal", "").replace("_converted", "")
    out_path = os.path.join(OUTPUT_DIR, f"final_{base}{reverb_label}.{fmt}")

    if fmt == "mp3":
        wav_tmp = out_path.replace(".mp3", "_tmp.wav")
        sf.write(wav_tmp, mixed, sr)
        try:
            import subprocess
            subprocess.run(["ffmpeg", "-i", wav_tmp, "-y", "-acodec", "libmp3lame",
                          "-q:a", "2", out_path], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            os.remove(wav_tmp)
        except Exception:
            out_path = wav_tmp
    else:
        sf.write(out_path, mixed, sr)
    return out_path


def run_rvc_worker(model_name, input_audio, f0_key, f0_method,
                   index_path, index_rate, filter_radius, protect,
                   resample_sr, rms_mix_rate, output_path, device_label,
                   timeout_sec=120):
    worker = os.path.join(NOW_DIR, "rvc_infer_worker.py")
    cmd = [
        sys.executable, worker,
        "--model", model_name,
        "--input", input_audio,
        "--output", output_path,
        "--f0-key", str(int(float(f0_key))),
        "--f0-method", str(f0_method),
        "--index-path", index_path if index_path else "",
        "--index-rate", str(float(index_rate)),
        "--filter-radius", str(int(float(filter_radius)) if filter_radius else 3),
        "--resample-sr", str(int(float(resample_sr)) if resample_sr else 0),
        "--rms-mix-rate", str(float(rms_mix_rate) if rms_mix_rate else 1.0),
        "--protect", str(float(protect) if protect else 0.33),
    ]
    env = os.environ.copy()
    if device_label:
        env["AI_COVER_DEVICE"] = device_label
    log_path = output_path + ".log"
    print(
        f"RVC worker start: device={env.get('AI_COVER_DEVICE', DEVICE)} "
        f"index={'on' if index_path and index_rate else 'off'} log={log_path}",
        flush=True,
    )
    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            proc = subprocess.run(
                cmd,
                cwd=NOW_DIR,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_sec,
            )
    except subprocess.TimeoutExpired:
        class TimeoutResult:
            returncode = 124
            stdout = ""
            stderr = f"RVC worker timed out after {timeout_sec}s. See log: {log_path}"

        print(f"RVC worker timeout after {timeout_sec}s; retrying fallback.", flush=True)
        return TimeoutResult()

    proc.stdout = ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
            proc.stderr = log_file.read()[-4000:]
    except Exception:
        proc.stderr = ""
    return proc


def is_known_bad_rvc_index(index_path):
    return bool(index_path) and os.path.basename(index_path) in {
        "qiqi_IVF775_Flat_nprobe_1_qiqi_v2.index",
    }


# ═══════════════════════════════════════════════════════════
# UI CALLBACKS
# ═══════════════════════════════════════════════════════════

# ── One-Click Cover ──────────────────────────────────────

def one_click_cover(input_song, engine_choice, model_name,
                    f0_method, f0_key, index_rate, protect,
                    noise_scale, auto_f0, spk_name,
                    vocal_vol, inst_vol,
                    reverb_enabled, reverb_room_size, reverb_wet,
                    reverb_dry, reverb_damping,
                    progress=gr.Progress()):
    """
    🎯 一键翻唱：分离 → 转换 → 混音，一个按钮完成
    """
    if input_song is None:
        return None, "❌ 请上传歌曲文件"
    if not model_name:
        return None, "❌ 请选择音色模型"

    try:
        # Step 1: Separate
        progress(0.05, desc="✂️ 正在分离人声/伴奏...")
        vocal_path, inst_path = separate_vocal_safe(input_song)
        if not os.path.exists(vocal_path):
            return None, "❌ 人声分离失败"

        progress(0.3, desc="✅ 分离完成")

        # Step 2: Convert
        progress(0.35, desc="🎙️ 正在音色转换...")
        if engine_choice == "RVC":
            converted_path = os.path.join(TEMP_DIR, os.path.basename(vocal_path).replace(".wav", "_converted.wav"))
            wav_from_worker = converted_path
            last_error = ""
            matching_index = _rvc.find_matching_index(model_name)
            attempts = []
            if matching_index and not is_known_bad_rvc_index(matching_index):
                attempts.append((DEVICE, model_name, matching_index, index_rate, 25))
            attempts.append((DEVICE, model_name, "", 0.0, 120))
            if DEVICE != "cpu":
                attempts.append(("cpu", model_name, "", 0.0, 240))

            for device_label, retry_model, retry_index_path, retry_index_rate, timeout_sec in attempts:
                proc = run_rvc_worker(
                    retry_model, vocal_path,
                    f0_key, f0_method,
                    retry_index_path,
                    retry_index_rate,
                    3,
                    protect,
                    0,
                    1.0,
                    wav_from_worker,
                    device_label,
                    timeout_sec=timeout_sec,
                )
                if proc.returncode == 0 and os.path.exists(wav_from_worker):
                    break
                last_error = (proc.stderr or proc.stdout or "").strip()
                if proc.returncode in (-11, 139):
                    continue
            else:
                return None, f"❌ 音色转换失败: RVC 子进程退出\n{last_error[-1200:]}"
        else:
            spk_name = _svc.normalize_speaker(model_name, spk_name)
            audio = _svc.infer(
                model_name, vocal_path,
                tran=int(float(f0_key)),
                auto_predict_f0=auto_f0,
                noise_scale=float(noise_scale),
                f0_predictor=f0_method,
                spk=spk_name,
            )
            converted_path = os.path.join(TEMP_DIR, os.path.basename(vocal_path).replace(".wav", "_converted.wav"))
            sf.write(converted_path, audio, 44100)

        progress(0.7, desc="✅ 转换完成")

        # Step 3: Mix
        progress(0.75, desc="🎛️ 正在混音...")
        out_path = mix_tracks(converted_path, inst_path, vocal_vol, inst_vol, "mp3",
                               reverb_enabled, reverb_room_size, reverb_wet,
                               reverb_dry, reverb_damping)

        progress(1.0, desc="🎉 完成!")
        status = f"✅ 一键翻唱完成！\n💾 {os.path.basename(out_path)}\n📁 {OUTPUT_DIR}"
        notify_done("AI 翻唱完成", os.path.basename(out_path))
        return out_path, status

    except Exception as e:
        traceback.print_exc()
        return None, f"❌ 翻唱失败: {str(e)}"
    finally:
        os.chdir(NOW_DIR)


def on_cover_engine_change(engine):
    """切换引擎 → 更新模型列表和相关参数"""
    if engine == "RVC":
        models = _rvc.get_models()
        return (
            gr.update(choices=models, value=models[0] if models else ""),
            gr.update(visible=True, value="rmvpe"),    # rvc_f0
            gr.update(visible=True),                     # rvc_params
            gr.update(visible=False),                    # svc_params
        )
    else:
        models = _svc.get_models()
        return (
            gr.update(choices=models, value=models[0] if models else ""),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
        )


# ── RVC Standalone Inference ─────────────────────────────

def rvc_infer_fn(model_name, input_audio, f0_key, f0_method,
                 index_path, index_rate, filter_radius, protect,
                 resample_sr, rms_mix_rate, output_fmt, progress=gr.Progress()):
    """RVC 独立推理"""
    if input_audio is None:
        return None, "❌ 请上传音频"
    if not model_name:
        return None, "❌ 请选择模型"

    try:
        progress(0.1, desc="🎙️ RVC 推理中...")
        base = os.path.splitext(os.path.basename(input_audio))[0]
        out_path = os.path.join(OUTPUT_DIR, f"rvc_{base}_{model_name.replace('.pth','')}.{output_fmt}")
        wav_from_worker = out_path if output_fmt == "wav" else out_path.replace(f".{output_fmt}", "_worker.wav")
        last_error = ""
        used_device = DEVICE
        attempts = []
        if index_path and not is_known_bad_rvc_index(index_path):
            attempts.append((DEVICE, index_path, float(index_rate), 25))
        attempts.append((DEVICE, "", 0.0, 120))
        if DEVICE != "cpu":
            attempts.append(("cpu", "", 0.0, 240))

        proc = None
        used_index = False
        skipped_bad_index = bool(index_path and is_known_bad_rvc_index(index_path))
        for device_label, retry_index_path, retry_index_rate, timeout_sec in attempts:
            used_device = device_label
            used_index = bool(retry_index_path and retry_index_rate)
            proc = run_rvc_worker(
                model_name, input_audio, f0_key, f0_method,
                retry_index_path, retry_index_rate, filter_radius, protect,
                resample_sr, rms_mix_rate, wav_from_worker, device_label,
                timeout_sec=timeout_sec,
            )
            if proc.returncode == 0 and os.path.exists(wav_from_worker):
                break
            last_error = (proc.stderr or proc.stdout or "").strip()
            if proc.returncode == -11 or proc.returncode == 139:
                if retry_index_path:
                    print("RVC worker crashed with Segmentation fault; retrying without index.")
                else:
                    print(f"RVC worker crashed with Segmentation fault; retrying on {device_label.upper()}.")
                continue
        else:
            return None, f"❌ 推理失败: RVC 子进程退出\n{last_error[-1200:]}"

        if output_fmt == "mp3":
            wav_tmp = out_path.replace(".mp3", "_tmp.wav")
            shutil.move(wav_from_worker, wav_tmp)
            subprocess.run(["ffmpeg", "-i", wav_tmp, "-y", "-acodec", "libmp3lame",
                          "-q:a", "2", out_path], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            os.remove(wav_tmp)

        progress(1.0, desc="✅ 完成!")
        notify_done("RVC 推理完成", os.path.basename(out_path))
        notes = []
        if str(used_device).lower() == "cpu" and DEVICE == "mps":
            notes.append("MPS 失败后已自动切到 CPU")
        if index_path and not used_index:
            if skipped_bad_index:
                notes.append("已跳过已知会卡住的 qiqi 索引")
            else:
                notes.append("索引超时/崩溃，已自动禁用索引重试")
        mode_note = f"（{'；'.join(notes)}）" if notes else ""
        return out_path, f"✅ RVC 推理完成{mode_note}\n💾 {os.path.basename(out_path)}"
    except Exception as e:
        traceback.print_exc()
        return None, f"❌ 推理失败: {str(e)}"
    finally:
        os.chdir(NOW_DIR)


# ── SVC Standalone Inference ─────────────────────────────

def svc_infer_fn(model_name, input_audio, f0_key, f0_method,
                 spk_name, noise_scale, auto_f0, slice_db,
                 cluster_ratio, pad_seconds, output_fmt, progress=gr.Progress()):
    """SVC 独立推理"""
    if input_audio is None:
        return None, "❌ 请上传音频"
    if not model_name:
        return None, "❌ 请选择模型"

    try:
        progress(0.1, desc="🎙️ SVC 推理中...")
        spk_name = _svc.normalize_speaker(model_name, spk_name)
        audio = _svc.infer(
            model_name, input_audio,
            tran=int(float(f0_key)),
            auto_predict_f0=auto_f0,
            noise_scale=float(noise_scale),
            f0_predictor=f0_method,
            spk=spk_name,
            slice_db=int(float(slice_db)) if slice_db else -45,
            cluster_infer_ratio=float(cluster_ratio),
            pad_seconds=float(pad_seconds) if pad_seconds else 0.5,
        )
        base = os.path.splitext(os.path.basename(input_audio))[0]
        clean_name = model_name.replace("/","_").replace(".pth","")
        out_path = os.path.join(OUTPUT_DIR, f"svc_{base}_{clean_name}.{output_fmt}")

        if output_fmt == "mp3":
            wav_tmp = out_path.replace(".mp3", "_tmp.wav")
            sf.write(wav_tmp, audio, 44100)
            import subprocess
            subprocess.run(["ffmpeg", "-i", wav_tmp, "-y", "-acodec", "libmp3lame",
                          "-q:a", "2", out_path], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            os.remove(wav_tmp)
        else:
            sf.write(out_path, audio, 44100)

        progress(1.0, desc="✅ 完成!")
        notify_done("SVC 推理完成", os.path.basename(out_path))
        return out_path, f"✅ SVC 推理完成\n💾 {os.path.basename(out_path)}"
    except Exception as e:
        traceback.print_exc()
        return None, f"❌ 推理失败: {str(e)}"
    finally:
        os.chdir(NOW_DIR)


# ── Model Refresh ────────────────────────────────────────

def refresh_all_models():
    rvc_m = _rvc.get_models()
    rvc_i = _rvc.get_indices()
    svc_m = _svc.get_models()
    svc_s = _svc.get_speakers(svc_m[0] if svc_m else None)
    return (
        gr.update(choices=rvc_m, value=rvc_m[0] if rvc_m else ""),  # cover_model
        gr.update(choices=rvc_m, value=rvc_m[0] if rvc_m else ""),  # rvc_model
        gr.update(choices=rvc_i, value=_rvc.find_matching_index(rvc_m[0]) if rvc_m else None),  # rvc_index
        gr.update(choices=svc_m, value=svc_m[0] if svc_m else ""),  # svc_model
        gr.update(choices=svc_s, value=svc_s[0] if svc_s else ""),  # svc_spk
    )


def on_rvc_model_change(model_name):
    indices = _rvc.get_indices()
    return gr.update(choices=indices, value=_rvc.find_matching_index(model_name))


def refresh_rvc_models():
    models = _rvc.get_models()
    selected_model = models[0] if models else ""
    return (
        gr.update(choices=models, value=selected_model),
        on_rvc_model_change(selected_model),
    )


def on_svc_model_change(model_name):
    speakers = _svc.get_speakers(model_name)
    return gr.update(choices=speakers, value=speakers[0] if speakers else "my_voice")


# ═══════════════════════════════════════════════════════════
# GRADIO UI
# ═══════════════════════════════════════════════════════════

F0_METHODS_RVC = ["rmvpe", "harvest", "crepe", "pm", "fcpe"]
F0_METHODS_SVC = ["rmvpe", "pm", "crepe", "harvest", "dio", "fcpe"]
OUTPUT_FORMATS = ["mp3", "wav", "flac"]

HEADER_HTML = f"""
<div style="text-align:center;background:linear-gradient(135deg,#667eea,#764ba2);padding:28px;border-radius:14px;margin-bottom:18px;">
    <h1 style="color:#fff;margin:0;font-size:2.2em;">🎤 AI 翻唱系统</h1>
    <p style="color:rgba(255,255,255,0.9);margin:8px 0 0;font-size:1.05em;">
        RVC + So-VITS-SVC 双引擎 | 设备: {DEVICE.upper()}
    </p>
</div>"""


def create_ui():
    rvc_initial = _rvc.get_models()
    svc_initial = _svc.get_models()
    rvc_indices_initial = _rvc.get_indices()
    svc_spks_initial = _svc.get_speakers(svc_initial[0] if svc_initial else None)

    with gr.Blocks(title="🎤 AI 翻唱系统") as app:
        gr.HTML(HEADER_HTML)

        with gr.Tabs():

            # ═══════════════════════════════════════════════
            # TAB 1: 一键翻唱
            # ═══════════════════════════════════════════════
            with gr.TabItem("🎯 一键翻唱", id="cover"):
                gr.Markdown("### 🎯 一键 AI 翻唱 — 上传 → 选引擎 → 一键出成品")

                with gr.Row():
                    # 左栏：输入
                    with gr.Column(scale=2):
                        cover_song = gr.Audio(label="📤 上传完整歌曲", type="filepath")

                        cover_engine = gr.Radio(
                            label="🎯 选择 AI 引擎",
                            choices=["RVC", "SVC"],
                            value="RVC",
                            info="RVC: 唱歌效果最佳 | SVC: 语音+唱歌通用",
                        )

                        cover_model = gr.Radio(
                            label="🎙️ 目标音色模型",
                            choices=rvc_initial,
                            value=rvc_initial[0] if rvc_initial else "",
                            info="选择要替换成谁的声音",
                        )

                        cover_f0_method = gr.Radio(
                            label="🎵 F0 音高提取方法",
                            choices=F0_METHODS_RVC,
                            value="rmvpe",
                            visible=True,
                            info="rmvpe 效果最好（推荐）",
                        )

                        cover_f0_key = gr.Slider(-12, 12, 0, step=1, label="🎹 音调调整 (半音)")

                    # 右栏：参数 + 输出
                    with gr.Column(scale=2):
                        # RVC 参数组
                        with gr.Group(visible=True) as cover_rvc_params:
                            gr.Markdown("**RVC 参数**")
                            cover_index_rate = gr.Slider(0, 1, 0.75, step=0.05, label="📇 索引混合比例")
                            cover_protect = gr.Slider(0, 0.5, 0.33, step=0.01, label="🛡️ 呼吸保护 (protect)")

                        # SVC 参数组
                        with gr.Group(visible=False) as cover_svc_params:
                            gr.Markdown("**SVC 参数**")
                            cover_noise_scale = gr.Slider(0, 1, 0.4, step=0.05, label="🔊 噪声级别 (noise_scale)")
                            cover_auto_f0 = gr.Checkbox(label="🤖 自动 F0 (语音模式)", value=False)
                            cover_spk = gr.Textbox(label="👤 说话人名称", value="my_voice")

                        gr.Markdown("---")
                        gr.Markdown("**🎛️ 混音设置**")
                        with gr.Row():
                            cover_vocal_vol = gr.Slider(-12, 12, 0, step=1, label="人声音量 (dB)")
                            cover_inst_vol = gr.Slider(-12, 12, 0, step=1, label="伴奏音量 (dB)")

                        # Reverb 混响
                        cover_reverb_enabled = gr.Checkbox(label="🎶 启用混响 (Reverb)", value=False,
                            info="给人声添加空间感，让翻唱更专业自然")
                        with gr.Row():
                            cover_reverb_room = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="🏠 房间大小 (Room Size)",
                                info="0=小房间 1=大厅/教堂")
                            cover_reverb_wet = gr.Slider(0.0, 1.0, 0.3, step=0.05, label="💧 湿声 (Wet)",
                                info="混响效果量，0=无效果 1=全效果")
                        with gr.Row():
                            cover_reverb_dry = gr.Slider(0.0, 1.0, 0.8, step=0.05, label="🏜️ 干声 (Dry)",
                                info="保留原声比例，0=全混响 1=全原声")
                            cover_reverb_damping = gr.Slider(0.0, 1.0, 0.5, step=0.05, label="🔇 高频衰减 (Damping)",
                                info="0=明亮反射 1=暗淡温暖")

                        cover_run_btn = gr.Button("🚀 一键翻唱", variant="primary", size="lg")

                with gr.Row():
                    cover_output = gr.Audio(label="📀 最终作品", interactive=False)
                    cover_status = gr.Textbox(label="状态", lines=6)

                # Engine change → update models
                cover_engine.change(
                    on_cover_engine_change, cover_engine,
                    [cover_model, cover_f0_method, cover_rvc_params, cover_svc_params],
                )

                # The ONE button
                cover_run_btn.click(
                    one_click_cover,
                    [cover_song, cover_engine, cover_model,
                     cover_f0_method, cover_f0_key, cover_index_rate, cover_protect,
                     cover_noise_scale, cover_auto_f0, cover_spk,
                     cover_vocal_vol, cover_inst_vol,
                     cover_reverb_enabled, cover_reverb_room, cover_reverb_wet,
                     cover_reverb_dry, cover_reverb_damping],
                    [cover_output, cover_status],
                )

                gr.Markdown("""
                ---
                ### 📖 使用说明
                1. **上传完整歌曲** (mp3/wav/flac)
                2. 选择 **AI 引擎** (RVC 唱歌好 / SVC 通用)
                3. 选择 **目标音色模型**
                4. 点击 **🚀 一键翻唱** → 自动完成 分离→转换→混音 → 输出 MP3
                """)

            # ═══════════════════════════════════════════════
            # TAB 2: RVC 独立推理
            # ═══════════════════════════════════════════════
            with gr.TabItem("🎵 RVC 推理", id="rvc_infer"):
                gr.Markdown("### 🎵 RVC — 音色转换推理（完整参数）")

                with gr.Row():
                    # 左栏：模型
                    with gr.Column(scale=1):
                        gr.Markdown("#### ⚡ 模型选择")
                        rvc_model = gr.Radio(
                            label="🎙️ 模型",
                            choices=rvc_initial,
                            value=rvc_initial[0] if rvc_initial else "",
                            info="RVC 音色模型 (.pth)",
                        )
                        rvc_index = gr.Dropdown(
                            label="📇 索引文件",
                            choices=rvc_indices_initial,
                            value=_rvc.find_matching_index(rvc_initial[0]) if rvc_initial else None,
                            info="FAISS 索引，提升音色还原度（可选）",
                        )
                        with gr.Row():
                            rvc_refresh_btn = gr.Button("🔄 刷新", size="sm")
                        with gr.Row():
                            rvc_model_upload = gr.File(label="📦 上传模型", file_count="multiple", height=60)

                    # 右栏：参数
                    with gr.Column(scale=2):
                        gr.Markdown("#### ⚙️ 推理参数")
                        with gr.Row():
                            rvc_f0_method = gr.Radio(
                                F0_METHODS_RVC, value="rmvpe",
                                label="F0 音高提取方法",
                                info="rmvpe: 深度学习，效果最好 | harvest: 传统算法，速度快",
                            )
                            rvc_out_fmt = gr.Radio(
                                OUTPUT_FORMATS, value="mp3",
                                label="输出格式",
                            )
                        with gr.Row():
                            rvc_f0_key = gr.Slider(-24, 24, 0, step=1, label="🎹 音调 (半音)")
                            rvc_index_rate = gr.Slider(0, 1, 0.75, step=0.05, label="📇 索引比例")
                        with gr.Row():
                            rvc_filter_radius = gr.Slider(0, 7, 3, step=1, label="🔍 中值滤波半径")
                            rvc_protect = gr.Slider(0, 0.5, 0.33, step=0.01, label="🛡️ 呼吸保护")
                        with gr.Row():
                            rvc_resample_sr = gr.Number(0, label="🔄 重采样率 (0=原始)", precision=0)
                            rvc_rms_mix = gr.Slider(0, 1, 1.0, step=0.05, label="📊 RMS 混合率")

                # Audio I/O
                with gr.Row():
                    rvc_input = gr.Audio(label="📤 上传人声", type="filepath")
                    rvc_output = gr.Audio(label="📀 输出音频", interactive=False)

                with gr.Row():
                    rvc_infer_btn = gr.Button("🎙️ 开始推理", variant="primary", size="lg")
                rvc_status = gr.Textbox(label="状态", lines=3)

                # Bindings
                rvc_refresh_btn.click(
                    refresh_rvc_models,
                    [], [rvc_model, rvc_index],
                )
                rvc_model.change(
                    on_rvc_model_change,
                    rvc_model,
                    rvc_index,
                )
                rvc_infer_btn.click(
                    rvc_infer_fn,
                    [rvc_model, rvc_input, rvc_f0_key, rvc_f0_method,
                     rvc_index, rvc_index_rate, rvc_filter_radius, rvc_protect,
                     rvc_resample_sr, rvc_rms_mix, rvc_out_fmt],
                    [rvc_output, rvc_status],
                )

            # ═══════════════════════════════════════════════
            # TAB 3: SVC 独立推理
            # ═══════════════════════════════════════════════
            with gr.TabItem("🎶 SVC 推理", id="svc_infer"):
                gr.Markdown("### 🎶 So-VITS-SVC — 音色转换推理（完整参数）")

                with gr.Row():
                    # 左栏：模型
                    with gr.Column(scale=1):
                        gr.Markdown("#### ⚡ 模型选择")
                        svc_model = gr.Radio(
                            label="🎙️ 模型 (G_*.pth)",
                            choices=svc_initial,
                            value=svc_initial[0] if svc_initial else "",
                            info="So-VITS-SVC 音色模型",
                        )
                        svc_spk = gr.Dropdown(
                            label="👤 说话人",
                            choices=svc_spks_initial,
                            value=svc_spks_initial[0] if svc_spks_initial else "",
                            allow_custom_value=True,
                            info="模型内的说话人 ID",
                        )
                        with gr.Row():
                            svc_refresh_btn = gr.Button("🔄 刷新", size="sm")

                    # 右栏：参数
                    with gr.Column(scale=2):
                        gr.Markdown("#### ⚙️ 推理参数")
                        with gr.Row():
                            svc_f0_method = gr.Radio(
                                F0_METHODS_SVC, value="rmvpe",
                                label="F0 音高提取方法",
                            )
                            svc_out_fmt = gr.Radio(
                                OUTPUT_FORMATS, value="mp3",
                                label="输出格式",
                            )
                        with gr.Row():
                            svc_f0_key = gr.Slider(-24, 24, 0, step=1, label="🎹 音调 (半音)")
                            svc_noise_scale = gr.Slider(0, 1, 0.4, step=0.05, label="🔊 噪声级别")
                        with gr.Row():
                            svc_slice_db = gr.Slider(-60, -20, -45, step=5, label="✂️ 切片阈值 (dB)")
                            svc_cluster_ratio = gr.Slider(0, 1, 0.0, step=0.05, label="📊 聚类/特征比例")
                        with gr.Row():
                            svc_pad_seconds = gr.Slider(0, 2, 0.5, step=0.1, label="⏱️ Pad 秒数")
                            svc_auto_f0 = gr.Checkbox(label="🤖 自动 F0 (语音模式)", value=False)

                # Audio I/O
                with gr.Row():
                    svc_input = gr.Audio(label="📤 上传人声", type="filepath")
                    svc_output = gr.Audio(label="📀 输出音频", interactive=False)

                with gr.Row():
                    svc_infer_btn = gr.Button("🎙️ 开始推理", variant="primary", size="lg")
                svc_status = gr.Textbox(label="状态", lines=3)

                # Bindings
                svc_refresh_btn.click(
                    lambda: (
                        gr.update(choices=_svc.get_models(), value=_svc.get_models()[0] if _svc.get_models() else ""),
                        on_svc_model_change(_svc.get_models()[0] if _svc.get_models() else None),
                    ),
                    [], [svc_model, svc_spk],
                )
                svc_model.change(
                    on_svc_model_change,
                    svc_model,
                    svc_spk,
                )
                svc_infer_btn.click(
                    svc_infer_fn,
                    [svc_model, svc_input, svc_f0_key, svc_f0_method,
                     svc_spk, svc_noise_scale, svc_auto_f0, svc_slice_db,
                     svc_cluster_ratio, svc_pad_seconds, svc_out_fmt],
                    [svc_output, svc_status],
                )

            # ═══════════════════════════════════════════════
            # TAB 4: 系统信息
            # ═══════════════════════════════════════════════
            with gr.TabItem("ℹ️ 系统信息", id="info"):
                rvc_n = len(_rvc.get_models())
                svc_n = len(_svc.get_models())
                gr.Markdown(f"""
                ## 🖥️ 系统信息

                | 项目 | 信息 |
                |------|------|
                | PyTorch | {torch.__version__} |
                | 推理设备 | **{DEVICE.upper()}** |
                | MPS (Apple GPU) | {'✅ 可用' if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() else '❌ 不可用'} |
                | CUDA | {'✅ 可用' if torch.cuda.is_available() else '❌ 不可用'} |
                | RVC 模型 | {rvc_n} 个 (rvc/assets/weights/) |
                | SVC 模型 | {svc_n} 个 (so-vits-svc/logs/44k/) |
                | 输出目录 | {OUTPUT_DIR} |

                ---
                ### 📁 目录结构
                ```
                ├── app.py              ← 统一入口
                ├── rvc/assets/weights/  ← 放 RVC 模型 (.pth)
                ├── rvc/assets/indices/  ← 放 FAISS 索引 (.index)
                ├── so-vits-svc/logs/44k/ ← 放 SVC 模型 (G_*.pth)
                └── output/             ← 输出文件
                ```

                ### 🚀 快捷操作
                - **一键翻唱**: 上传完整歌曲 → 选引擎 → 一键出 MP3
                - **RVC 推理**: 上传已分离的人声 → 选模型 → 音色转换
                - **SVC 推理**: 上传已分离的人声 → 选模型 → 音色转换
                """)

    return app


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="🎤 AI 翻唱系统")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true")
    parser.add_argument("--listen", action="store_true")
    args = parser.parse_args()

    app = create_ui()

    rvc_n = len(_rvc.get_models())
    svc_n = len(_svc.get_models())
    print(f"""
╔══════════════════════════════════════════════════════╗
║     🎤 AI 翻唱系统 — RVC + SVC 双引擎             ║
║                                                    ║
║  🌐 http://127.0.0.1:{args.port}                         ║
║  📱 设备: {DEVICE.upper():<40} ║
║  📂 RVC: {rvc_n} 模型 | SVC: {svc_n} 模型                  ║
║                                                    ║
╚══════════════════════════════════════════════════════╝
    """)

    app.launch(
        server_port=args.port,
        share=args.share,
        server_name="0.0.0.0" if args.listen else "127.0.0.1",
        inbrowser=True,
        allowed_paths=[NOW_DIR, OUTPUT_DIR, TEMP_DIR, RVC_DIR, SVC_DIR],
    )


if __name__ == "__main__":
    main()
