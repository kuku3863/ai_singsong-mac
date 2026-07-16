# -*- coding: utf-8 -*-
"""auto_mix tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the auto_mix tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import (
    _FORMAT_CHOICES, save_audio_with_format, convert_audio_format,
)
from tabs.shared import *


def build_auto_mix_tab():
    """Build the auto_mix tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem("✨ AI 自动混音", id="automix"):
        gr.HTML("""
        <div class="cyber-card" style="margin-bottom: 12px;">
            <div style="font-size: 0.85rem; color: #64748b; background: rgba(124,58,237,0.04); padding: 8px 12px; border-radius: 8px;">
                基于 pedalboard 的专业级人声后处理引擎（移植自 SVC Fusion）
                <br>自动 EQ、压缩、去齿音、混响、回声 → 与伴奏智能混音 → 总线限幅
            </div>
        </div>
        """)
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("#### 📥 输入音轨")
                am_vocal_file = gr.Audio(
                    label="人声音轨（干声/已转换音色）", type="filepath"
                )
                am_inst_file = gr.Audio(label="伴奏音轨", type="filepath")
    
                gr.Markdown("#### ⚙️ 基础参数")
                am_vocal_vol = gr.Slider(
                    -20,
                    20,
                    step=0.5,
                    value=0,
                    label="人声音量调节 (dB)",
                    info="调整人声整体音量",
                )
                am_music_genre = gr.Dropdown(
                    label="音乐风格预设",
                    choices=[
                        ("流行 POP", "POP"),
                        ("摇滚 ROCK", "ROCK"),
                        ("爵士 JAZZ", "JAZZ"),
                        ("电子 ELECTRONIC", "ELECTRONIC"),
                        ("民谣 FOLK", "FOLK"),
                        ("古典 CLASSICAL", "CLASSICAL"),
                    ],
                    value="POP",
                    info="不同风格自动调整 EQ、压缩、混响参数",
                )
                am_voice_type = gr.Dropdown(
                    label="人声类型",
                    choices=[
                        ("男声低音", "MALE_LOW"),
                        ("男声高音", "MALE_HIGH"),
                        ("女声", "FEMALE"),
                        ("说唱", "RAP"),
                        ("美声", "VOCAL"),
                    ],
                    value="FEMALE",
                    info="不同人声类型自动优化 EQ 参数",
                )
    
                with gr.Accordion("🎛️ 高级参数", open=False):
                    gr.Markdown("##### 专业混音参数（一般无需调整）")
                    am_reverb_level = gr.Dropdown(
                        label="混响等级",
                        choices=[
                            ("无混响", "DRY"),
                            ("轻微", "SUBTLE"),
                            ("轻度", "LIGHT"),
                            ("中度", "MODERATE"),
                            ("重度", "HEAVY"),
                            ("极重", "EXTREME"),
                        ],
                        value="MODERATE",
                    )
                    am_deesser = gr.Dropdown(
                        label="去齿音强度",
                        choices=[
                            ("关闭", "OFF"),
                            ("轻微", "LIGHT"),
                            ("中等", "MODERATE"),
                            ("强烈", "HEAVY"),
                        ],
                        value="MODERATE",
                    )
                    am_compression = gr.Dropdown(
                        label="压缩强度",
                        choices=[
                            ("轻压缩", "LIGHT"),
                            ("标准压缩", "MODERATE"),
                            ("重压缩", "HEAVY"),
                        ],
                        value="MODERATE",
                    )
                    am_eq_style = gr.Dropdown(
                        label="EQ 风格",
                        choices=[
                            ("中性", "NEUTRAL"),
                            ("明亮", "BRIGHT"),
                            ("温暖", "WARM"),
                            ("复古", "VINTAGE"),
                        ],
                        value="NEUTRAL",
                    )
                    am_echo_level = gr.Dropdown(
                        label="回声等级",
                        choices=[
                            ("关闭", "OFF"),
                            ("轻微", "SUBTLE"),
                            ("轻度", "LIGHT"),
                            ("中度", "MODERATE"),
                            ("重度", "HEAVY"),
                        ],
                        value="OFF",
                    )
    
            with gr.Column(scale=1):
                am_output_format = gr.Dropdown(
                    label="🎼 输出格式",
                    choices=_FORMAT_CHOICES,
                    value="wav",
                    info="选择混音输出的格式（默认 WAV 无损）",
                )
                am_mix_btn = gr.Button(
                    "✨ 开始 AI 自动混音", variant="primary", size="lg"
                )
                am_output = gr.Audio(
                    label="混音输出", type="filepath", interactive=False
                )
                am_info = gr.Textbox(label="处理信息", lines=6, interactive=False)

        def at_automix_process(
            vocal_path,
            inst_path,
            vocal_vol,
            genre_str,
            voice_type_str,
            reverb_str,
            deesser_str,
            compression_str,
            eq_str,
            echo_str,
            output_format="wav",
        ):
            """AI 自动混音处理"""
            from audio_tools.automix import (
                automix,
                check_dependencies,
                MusicGenre,
                VoiceType,
                ReverbLevel,
                DeEsserStrength,
                CompressionStrength,
                EQStyle,
                EchoLevel,
            )
    
            if not vocal_path or not inst_path:
                return None, "⚠️ 请同时提供人声和伴奏音轨"
    
            ok, msg = check_dependencies()
            if not ok:
                return None, f"❌ {msg}"
    
            # Gradio Dropdown 可能返回 (value, index) tuple，提取字符串值
            def _str_val(v, default="POP"):
                if isinstance(v, (list, tuple)):
                    return str(v[0]) if v else default
                return str(v) if v else default
    
            genre = getattr(MusicGenre, _str_val(genre_str, "POP"), MusicGenre.POP)
            voice_type = getattr(
                VoiceType, _str_val(voice_type_str, "FEMALE"), VoiceType.FEMALE
            )
            reverb_level = getattr(
                ReverbLevel, _str_val(reverb_str, "MODERATE"), ReverbLevel.MODERATE
            )
            deesser = getattr(
                DeEsserStrength,
                _str_val(deesser_str, "MODERATE"),
                DeEsserStrength.MODERATE,
            )
            compression = getattr(
                CompressionStrength,
                _str_val(compression_str, "MODERATE"),
                CompressionStrength.MODERATE,
            )
            eq_style = getattr(
                EQStyle, _str_val(eq_str, "NEUTRAL"), EQStyle.NEUTRAL
            )
            echo = getattr(EchoLevel, _str_val(echo_str, "OFF"), EchoLevel.OFF)
    
            try:
                import time as _t

                _t0 = _t.time()
                result_path = automix(
                    voc_path=vocal_path,
                    inst_path=inst_path,
                    sample_rate=44100,
                    reverb_gain=0,
                    headroom=-8,
                    voc_input=-4 + vocal_vol,
                    reverb_level=reverb_level,
                    music_genre=genre,
                    voice_type=voice_type,
                    deesser_strength=deesser,
                    compression_strength=compression,
                    eq_style=eq_style,
                    echo_level=echo,
                )

                if output_format != "wav" and result_path and os.path.exists(result_path):
                    try:
                        result_path = convert_audio_format(result_path, output_format)
                    except Exception:
                        pass

                elapsed = _t.time() - _t0
                info = (
                    f"✅ AI 自动混音完成 (耗时 {elapsed:.1f}s)\n"
                    f"风格: {genre_str} | 人声类型: {voice_type_str}\n"
                    f"混响: {reverb_str} | 去齿音: {deesser_str}\n"
                    f"压缩: {compression_str} | EQ: {eq_str} | 回声: {echo_str}\n"
                    f"格式: {output_format.upper()} | 输出: {result_path}"
                )
                return result_path, info
            except Exception as e:
                import traceback
    
                traceback.print_exc()
                return None, f"❌ 混音失败: {str(e)}"
    
        am_mix_btn.click(
            fn=at_automix_process,
            inputs=[
                am_vocal_file,
                am_inst_file,
                am_vocal_vol,
                am_music_genre,
                am_voice_type,
                am_reverb_level,
                am_deesser,
                am_compression,
                am_eq_style,
                am_echo_level,
                am_output_format,
            ],
            outputs=[am_output, am_info],
        )
    
    # ==================== 🔓 歌曲解码 Tab ====================
    
