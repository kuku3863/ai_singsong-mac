# -*- coding: utf-8 -*-
"""audio_tools tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the audio_tools tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import (
    _FORMAT_CHOICES, _has_audio_tools,
    save_audio_with_format, convert_audio_format,
)
from tabs.shared import *

def build_audio_tools_tab():
    """Build the audio_tools tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem("🧰 音频工具箱", id="audio_tools"):
        if not _has_audio_tools:
            gr.Markdown(
                "### audio_tools 模块未正确加载\n\n请检查 `audio_tools/` 目录是否存在且依赖完整。"
            )
        else:
            with gr.Tabs():
                # ----- 变调工具 -----
                with gr.TabItem("🎵 变调工具"):
                    gr.Markdown(
                        "### 音高偏移（Pitch Shift）\n对音频进行独立变调处理，不改变语速。男转女约 +12 半音，女转男约 -12 半音。"
                    )
                    with gr.Row():
                        with gr.Column(scale=1):
                            at_pitch_input = gr.Textbox(
                                label="音频文件路径",
                                placeholder="拖放上传或手动输入路径",
                                lines=1,
                            )
                            at_pitch_file = gr.File(
                                label="或上传音频文件", file_count="single"
                            )
                            at_pitch_steps = gr.Slider(
                                minimum=-24,
                                maximum=24,
                                step=1,
                                value=0,
                                label="变调步数（半音）",
                                info="正数升高，负数降低",
                            )
                            at_pitch_method = gr.Dropdown(
                                choices=["librosa", "phase_vocoder"],
                                value="librosa",
                                label="变调算法",
                                info="librosa 质量更高，phase_vocoder 速度更快",
                            )
                            at_pitch_output_format = gr.Dropdown(
                                label="🎼 输出格式",
                                choices=_FORMAT_CHOICES,
                                value="wav",
                                info="变调输出格式",
                            )
                            at_pitch_btn = gr.Button(
                                "🎵 开始变调", variant="primary"
                            )
                        with gr.Column(scale=1):
                            at_pitch_output = gr.Audio(
                                label=i18n("变调结果"), interactive=False
                            )
                            at_pitch_info = gr.Textbox(
                                label=i18n("处理信息"), lines=3, interactive=False
                            )
                            with gr.Row():
                                at_pitch_open_dir = gr.Button(
                                    "📂 打开输出目录",
                                    size="sm",
                                    variant="secondary",
                                )
                                at_pitch_dir_info = gr.HTML(value="")
    
                    def at_handle_pitch_upload(file_obj):
                        if file_obj is None:
                            return ""
                        path = (
                            file_obj.name
                            if hasattr(file_obj, "name")
                            else str(file_obj)
                        )
                        return path
    
                    at_pitch_file.change(
                        fn=at_handle_pitch_upload,
                        inputs=[at_pitch_file],
                        outputs=[at_pitch_input],
                    )
    
                    def _at_pitch_with_format(audio_path, n_steps, method, output_format="wav"):
                        out_path, info_msg = at_pitch_shift(audio_path, n_steps, method)
                        if output_format != "wav" and out_path and os.path.exists(out_path):
                            try:
                                out_path = convert_audio_format(out_path, output_format)
                                info_msg = info_msg.replace("输出:", f"格式:{output_format.upper()} | 输出:")
                            except Exception:
                                pass
                        return out_path, info_msg

                    at_pitch_btn.click(
                        fn=_at_pitch_with_format,
                        inputs=[at_pitch_input, at_pitch_steps, at_pitch_method, at_pitch_output_format],
                        outputs=[at_pitch_output, at_pitch_info],
                    )
    
                    def _at_pitch_open_dir():
                        d = get_output_dir("tools", "pitch_shift")
                        os.makedirs(d, exist_ok=True)
                        try:
                            os.startfile(d)
                            return '<div style="color:#059669;font-size:0.78rem;">✅ 已打开</div>'
                        except Exception as e:
                            return (
                                '<div style="color:#ef4444;font-size:0.78rem;">❌ '
                                + str(e)
                                + "</div>"
                            )
    
                    at_pitch_open_dir.click(
                        fn=_at_pitch_open_dir,
                        inputs=[],
                        outputs=[at_pitch_dir_info],
                    )
    
                # ----- 混音工具 -----
                with gr.TabItem("🎛️ 混音工具"):
                    gr.Markdown(
                        "### 音轨混音\n将人声和伴奏按指定比例混合，支持普通混音和智能人声闪避混音。"
                    )
                    with gr.Row():
                        with gr.Column(scale=1):
                            with gr.Group():
                                gr.Markdown("#### 📥 输入音轨")
                                at_vocal_path = gr.Textbox(
                                    label="人声音轨路径",
                                    placeholder="人声文件路径",
                                    lines=1,
                                )
                                at_vocal_file = gr.File(
                                    label="或上传人声音轨", file_count="single"
                                )
                                at_inst_path = gr.Textbox(
                                    label="伴奏音轨路径",
                                    placeholder="伴奏文件路径",
                                    lines=1,
                                )
                                at_inst_file = gr.File(
                                    label="或上传伴奏音轨", file_count="single"
                                )
    
                            with gr.Group():
                                gr.Markdown("#### ⚙️ 混音参数")
                                with gr.Row():
                                    at_vocal_vol = gr.Slider(
                                        0,
                                        2.0,
                                        step=0.05,
                                        value=1.0,
                                        label="人声音量",
                                    )
                                    at_inst_vol = gr.Slider(
                                        0,
                                        2.0,
                                        step=0.05,
                                        value=1.0,
                                        label="伴奏音量",
                                    )
                                at_ducking = gr.Slider(
                                    0,
                                    1.0,
                                    step=0.05,
                                    value=0.3,
                                    label="人声闪避强度",
                                    info="0=不闪避, 1=完全闪避",
                                )
                        with gr.Column(scale=1):
                            with gr.Row():
                                at_mix_output_format = gr.Dropdown(
                                    label="🎼 输出格式",
                                    choices=_FORMAT_CHOICES,
                                    value="wav",
                                    info="混音输出格式",
                                )
                                at_mix_btn = gr.Button(
                                    "🎶 普通混音", variant="primary"
                                )
                                at_smart_output_format = gr.Dropdown(
                                    label="🎼 输出格式",
                                    choices=_FORMAT_CHOICES,
                                    value="wav",
                                    info="智能混音输出格式",
                                )
                                at_smart_btn = gr.Button(
                                    "🤖 智能混音", variant="secondary"
                                )
                            at_mix_output = gr.Audio(
                                label=i18n("混音结果"), interactive=False
                            )
                            at_mix_info = gr.Textbox(
                                label=i18n("处理信息"), lines=4, interactive=False
                            )
                            with gr.Row():
                                at_mix_open_dir = gr.Button(
                                    "📂 打开输出目录",
                                    size="sm",
                                    variant="secondary",
                                )
                                at_mix_dir_info = gr.HTML(value="")
    
                    def at_handle_vocal_upload(f):
                        return f.name if f and hasattr(f, "name") else ""
    
                    def at_handle_inst_upload(f):
                        return f.name if f and hasattr(f, "name") else ""
    
                    at_vocal_file.change(
                        fn=at_handle_vocal_upload,
                        inputs=[at_vocal_file],
                        outputs=[at_vocal_path],
                    )
                    at_inst_file.change(
                        fn=at_handle_inst_upload,
                        inputs=[at_inst_file],
                        outputs=[at_inst_path],
                    )
    
                    def _at_mix_with_format(vocal_path, inst_path, vocal_vol, inst_vol, output_format="wav"):
                        out_path, info_msg = at_mix_two_tracks(vocal_path, inst_path, vocal_vol, inst_vol)
                        if output_format != "wav" and out_path and os.path.exists(out_path):
                            try:
                                out_path = convert_audio_format(out_path, output_format)
                                info_msg = info_msg.replace("输出:", f"格式:{output_format.upper()} | 输出:")
                            except Exception:
                                pass
                        return out_path, info_msg

                    at_mix_btn.click(
                        fn=_at_mix_with_format,
                        inputs=[
                            at_vocal_path,
                            at_inst_path,
                            at_vocal_vol,
                            at_inst_vol,
                            at_mix_output_format,
                        ],
                        outputs=[at_mix_output, at_mix_info],
                    )
                    def _at_smart_mix_with_format(vocal_path, inst_path, ducking, vocal_vol, inst_vol, output_format="wav"):
                        out_path, info_msg = at_smart_mix(vocal_path, inst_path, ducking, vocal_vol, inst_vol)
                        if output_format != "wav" and out_path and os.path.exists(out_path):
                            try:
                                out_path = convert_audio_format(out_path, output_format)
                                info_msg = info_msg.replace("输出:", f"格式:{output_format.upper()} | 输出:")
                            except Exception:
                                pass
                        return out_path, info_msg

                    at_smart_btn.click(
                        fn=_at_smart_mix_with_format,
                        inputs=[
                            at_vocal_path,
                            at_inst_path,
                            at_ducking,
                            at_vocal_vol,
                            at_inst_vol,
                            at_smart_output_format,
                        ],
                        outputs=[at_mix_output, at_mix_info],
                    )
    
                    def _at_mix_open_dir():
                        d = get_output_dir("tools", "mix")
                        os.makedirs(d, exist_ok=True)
                        try:
                            os.startfile(d)
                            return '<div style="color:#059669;font-size:0.78rem;">✅ 已打开</div>'
                        except Exception as e:
                            return (
                                '<div style="color:#ef4444;font-size:0.78rem;">❌ '
                                + str(e)
                                + "</div>"
                            )
    
                    at_mix_open_dir.click(
                        fn=_at_mix_open_dir, inputs=[], outputs=[at_mix_dir_info]
                    )
    
                # ----- 切片工具 -----
                with gr.TabItem("✂️ 音频切片"):
                    gr.Markdown(
                        "### 静音切片\n按静音段自动将音频分割为多个片段，适合从长录音中提取有效语音。"
                    )
                    with gr.Row():
                        with gr.Column(scale=1):
                            at_slice_input = gr.Textbox(
                                label="音频文件路径",
                                placeholder="拖放上传或手动输入路径",
                                lines=1,
                            )
                            at_slice_file = gr.File(
                                label="或上传音频文件", file_count="single"
                            )
                            with gr.Row():
                                at_slice_min = gr.Slider(
                                    0.5,
                                    30.0,
                                    step=0.5,
                                    value=5.0,
                                    label="最短片段(秒)",
                                )
                                at_slice_max = gr.Slider(
                                    5.0,
                                    120.0,
                                    step=5.0,
                                    value=30.0,
                                    label="最长片段(秒)",
                                )
                            at_slice_db = gr.Slider(
                                20,
                                80,
                                step=5,
                                value=60,
                                label="静音阈值(dB)",
                                info="越大越容易切分",
                            )
                            at_slice_output_dir = gr.Textbox(
                                label="输出目录（留空使用默认）",
                                placeholder="例如: D:/output/sliced",
                                lines=1,
                                value="",
                            )
                            at_slice_btn = gr.Button(
                                "✂️ 开始切片", variant="primary"
                            )
                        with gr.Column(scale=1):
                            at_slice_info = gr.Textbox(
                                label=i18n("切片结果"), lines=10, interactive=False
                            )
                            with gr.Row():
                                at_slice_open_dir = gr.Button(
                                    "📂 打开输出目录",
                                    size="sm",
                                    variant="secondary",
                                )
                                at_slice_dir_info = gr.HTML(value="")
    
                    def at_handle_slice_upload(f):
                        return f.name if f and hasattr(f, "name") else ""
    
                    at_slice_file.change(
                        fn=at_handle_slice_upload,
                        inputs=[at_slice_file],
                        outputs=[at_slice_input],
                    )
    
                    at_slice_btn.click(
                        fn=at_slice_audio,
                        inputs=[
                            at_slice_input,
                            at_slice_min,
                            at_slice_max,
                            at_slice_db,
                            at_slice_output_dir,
                        ],
                        outputs=[at_slice_info, at_slice_info],
                    )
    
                    def _at_slice_open_dir():
                        d = get_output_dir("tools", "slice")
                        os.makedirs(d, exist_ok=True)
                        try:
                            os.startfile(d)
                            return '<div style="color:#059669;font-size:0.78rem;">✅ 已打开</div>'
                        except Exception as e:
                            return (
                                '<div style="color:#ef4444;font-size:0.78rem;">❌ '
                                + str(e)
                                + "</div>"
                            )
    
                    at_slice_open_dir.click(
                        fn=_at_slice_open_dir,
                        inputs=[],
                        outputs=[at_slice_dir_info],
                    )
    
                # ----- 混响效果 -----
                with gr.TabItem("🔊 混响效果"):
                    gr.Markdown(
                        "### 混响（Reverb）\n为干声添加空间混响效果，适合给人声录音增加环境感。"
                    )
                    with gr.Row():
                        with gr.Column(scale=1):
                            at_rev_input = gr.Textbox(
                                label="音频文件路径",
                                placeholder="拖放上传或手动输入路径",
                                lines=1,
                            )
                            at_rev_file = gr.File(
                                label="或上传音频文件", file_count="single"
                            )
                            at_rev_room = gr.Slider(
                                0.1,
                                2.0,
                                step=0.1,
                                value=0.5,
                                label="空间大小",
                                info="越大混响越长",
                            )
                            at_rev_damp = gr.Slider(
                                0.1,
                                1.0,
                                step=0.05,
                                value=0.5,
                                label="阻尼",
                                info="越大高频衰减越快",
                            )
                            at_rev_wet = gr.Slider(
                                0.0,
                                0.8,
                                step=0.05,
                                value=0.3,
                                label="湿声比例",
                                info="混响效果的混合比例",
                            )
                            at_rev_output_format = gr.Dropdown(
                                label="🎼 输出格式",
                                choices=_FORMAT_CHOICES,
                                value="wav",
                                info="混响输出格式",
                            )
                            at_rev_btn = gr.Button("🔊 添加混响", variant="primary")
                        with gr.Column(scale=1):
                            at_rev_output = gr.Audio(
                                label="处理结果", interactive=False
                            )
                            at_rev_info = gr.Textbox(
                                label=i18n("处理信息"), lines=3, interactive=False
                            )
                            with gr.Row():
                                at_rev_open_dir = gr.Button(
                                    "📂 打开输出目录",
                                    size="sm",
                                    variant="secondary",
                                )
                                at_rev_dir_info = gr.HTML(value="")
    
                    def at_handle_rev_upload(f):
                        return f.name if f and hasattr(f, "name") else ""
    
                    at_rev_file.change(
                        fn=at_handle_rev_upload,
                        inputs=[at_rev_file],
                        outputs=[at_rev_input],
                    )
    
                    def _at_reverb_with_format(audio_path, room_size, damping, wet_level, output_format="wav"):
                        out_path, info_msg = at_reverb_effect(audio_path, room_size, damping, wet_level)
                        if output_format != "wav" and out_path and os.path.exists(out_path):
                            try:
                                out_path = convert_audio_format(out_path, output_format)
                                info_msg = info_msg.replace("输出:", f"格式:{output_format.upper()} | 输出:")
                            except Exception:
                                pass
                        return out_path, info_msg

                    at_rev_btn.click(
                        fn=_at_reverb_with_format,
                        inputs=[at_rev_input, at_rev_room, at_rev_damp, at_rev_wet, at_rev_output_format],
                        outputs=[at_rev_output, at_rev_info],
                    )
    
                    def _at_rev_open_dir():
                        d = get_output_dir("tools", "reverb")
                        os.makedirs(d, exist_ok=True)
                        try:
                            os.startfile(d)
                            return '<div style="color:#059669;font-size:0.78rem;">✅ 已打开</div>'
                        except Exception as e:
                            return (
                                '<div style="color:#ef4444;font-size:0.78rem;">❌ '
                                + str(e)
                                + "</div>"
                            )
    
                    at_rev_open_dir.click(
                        fn=_at_rev_open_dir, inputs=[], outputs=[at_rev_dir_info]
                    )
    
                # ----- AI 自动混音（已移至独立 Tab） -----
    
    # ==================== 模型工坊 Tab ====================
    # ==================== 模型工坊 Tab ====================
    
