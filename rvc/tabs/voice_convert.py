# -*- coding: utf-8 -*-
"""voice_convert tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the voice_convert tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import *
from tabs.shared import (
    _SVC_BLOCKED_MODELS, _get_audio_info, _fmt_duration, _fmt_file_size,
    _friendly_err, _LiveTaskCtx, _has_audio_tools, _progress_html,
    _FORMAT_CHOICES, save_audio_with_format, convert_audio_format, resolve_format,
)
from tabs.header import _acquire_exec, _release_exec, _is_executing, _get_taskbar_html, _request_cancel, _is_cancelled, _clear_cancel, _update_task_name
from tabs.state import get_taskbar, mark_task_completed
from tabs.pressure_test import start_pressure_test
import os
import subprocess
import threading
import sys


def build_voice_convert_tab():
    """Build the voice_convert tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    # 从全局状态获取taskbar组件（必须在build_header()之后调用）
    _global_taskbar, _ = get_taskbar()

    with gr.TabItem("🎤 音色转换", id="infer"):
        def refresh_models():
            """刷新模型和索引列表，保持索引文件为空"""
            names = get_model_list()
            indices = get_index_list()
            return (
                {"choices": names, "value": None, "__type__": "update"},
                {"choices": indices, "__type__": "update", "value": None},
            )
    
        # ==================== 三栏布局 ====================
        with gr.Row():
            # ==================== 左侧栏：模型选择 ====================
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="cyber-card" style="margin-bottom: 12px;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #fff; background: linear-gradient(90deg, #7c3aed, #a78bfa); margin: -12px -12px 10px -12px; padding: 8px 12px; border-radius: 12px 12px 0 0;">
                        ⚡ 选择模型
                    </div>
                """)
    
                sid0 = gr.Radio(
                    label="选择模型",
                    choices=sorted(names),
                    value=None,
                    interactive=True,
                )
    
                model_search = gr.Textbox(
                    label="🔍 搜索模型",
                    placeholder="输入关键词搜索已上传的模型...",
                    visible=True,
                )

                def _get_svc_warning():
                    if _SVC_BLOCKED_MODELS:
                        items = "<br>".join(f"• {m}" for m in _SVC_BLOCKED_MODELS)
                        return f"""<div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(234,88,12,0.12);border-left:3px solid #ea580c;">
                            <span style="color:#fbbf24;font-size:0.75rem;font-weight:600;">⚠️ 已拦截 {len(_SVC_BLOCKED_MODELS)} 个大模型（>300MB，可能是SVC模型，不兼容RVC）：</span><br>
                            <span style="color:#fca5a5;font-size:0.7rem;">{items}</span></div>"""
                    return ""
    
                gr.HTML("""<div style="margin-top: 8px; display: flex; justify-content: center;">
                    <a href="https://mxgf.cc" target="_blank" rel="noopener noreferrer" style="
                        display: inline-flex; align-items: center; justify-content: center; gap: 10px;
                        padding: 16px 48px; border-radius: 14px; text-decoration: none;
                        font-size: 1.2rem; font-weight: 700; color: #fff;
                        background: linear-gradient(135deg, #1B4D3E, #2E6B4F, #4A9079, #5FAA8C);
                        box-shadow: 0 4px 16px rgba(27, 77, 62, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.25);
                        border: 1px solid rgba(79, 155, 123, 0.5);
                        transition: all 0.25s ease;
                        letter-spacing: 1px; cursor: pointer;
                    " onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 6px 24px rgba(27, 77, 62, 0.7)'"
                       onmouseout="this.style.transform='';this.style.boxShadow='0 4px 16px rgba(27, 77, 62, 0.5)'">
                        🎩 模型工坊
                    </a>
                </div>
                """)
    
                with gr.Row():
                    refresh_button = gr.Button(i18n("🔄 刷新"), variant="primary")
                    clean_button = gr.Button(i18n("🗑️ 卸载"), variant="secondary")
    
                with gr.Row():
                    clear_all_btn2 = gr.Button(
                        i18n("清空"), variant="secondary", size="sm"
                    )
    
                clean_button.click(
                    fn=clean, inputs=[], outputs=[sid0]
                )
    
                def _filter_models(search_text):
                    all_models = get_model_list()
                    if not search_text or not search_text.strip():
                        return {
                            "choices": all_models,
                            "value": None,
                            "__type__": "update",
                        }
                    keyword = search_text.strip().lower()
                    filtered = [m for m in all_models if keyword in m.lower()]
                    return {
                        "choices": filtered,
                        "value": None,
                        "__type__": "update",
                    }
    
                svc_warning = gr.HTML(value="")

                model_search.change(
                    fn=_filter_models,
                    inputs=[model_search],
                    outputs=[sid0],
                )

                gr.HTML("</div>")

                # 模型上传功能
                gr.HTML("""
                <div style="padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,rgba(139,92,246,0.08),rgba(139,92,246,0.04));border:1px solid rgba(139,92,246,0.25);">
                    <div style="font-size:0.82rem;color:#8b5cf6;font-weight:700;margin-bottom:6px;">⬆️ 上传模型</div>
                    <div style="font-size:0.72rem;color:#a78bfa;">上传 .pth 模型到 weights 目录，刷新后可选</div>
                </div>""")
                vc_model_file = gr.File(
                    label="📦 上传 .pth 模型（支持多选）",
                    file_count="multiple",
                    height=60,
                )
                vc_model_custom_name = gr.Textbox(
                    label="📝 自定义名称",
                    placeholder="不填保持原名",
                    lines=1,
                )
                vc_upload_model_btn = gr.Button(
                    "📤 上传模型", variant="primary", size="sm"
                )
                vc_model_upload_status = gr.HTML(
                    value='<div style="padding:4px 8px;border-radius:6px;background:rgba(139,92,246,0.06);color:#8b5cf6;font-size:0.74rem;">等待上传...</div>',
                )

                gr.HTML(
                    '<hr style="border:none;border-top:1px dashed rgba(139,92,246,0.2);margin:10px 0;">'
                )

            # ==================== 中央栏：上传音频 ====================
            with gr.Column(scale=2):
                # 音频可视化
                gr.HTML("""
                <div class="audio-viz" style="margin-bottom: 15px; height: 50px;">
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                    <div class="viz-bar"></div>
                </div>
                """)
    
                # 隐藏组件（需要在使用前定义）
                f0_file = gr.File(label=i18n("F0曲线(可选)"), visible=False)
                file_index1 = gr.Textbox(
                    label=i18n("索引路径(可选)"), visible=False
                )
                file_index2 = gr.Dropdown(
                    label=i18n("索引文件"),
                    choices=sorted(index_paths),
                    value=None,
                    visible=False,
                )
                filter_radius0 = gr.Slider(
                    minimum=0, maximum=7, step=1, value=3, visible=False
                )
                resample_sr0 = gr.Slider(
                    minimum=0, maximum=48000, step=1000, value=0, visible=False
                )
                rms_mix_rate0 = gr.Slider(
                    minimum=0, maximum=1, step=0.05, value=1, visible=False
                )
    
                # 上传音频区域
                gr.HTML("""
                <div style="margin-bottom: 8px; background: rgba(139, 92, 246, 0.06); border-radius: 10px; border: 1px solid rgba(139, 92, 246, 0.15);">
                    <div style="font-size: 0.85rem; color: #fff; background: linear-gradient(135deg, #8b5cf6, #a78bfa); margin: 0; padding: 8px 12px; border-radius: 10px 10px 0 0; display: flex; align-items: center; gap: 8px;">📤 上传音频</div>
                """)

                # 已上传文件列表 - 始终在上方醒目显示
                uploaded_paths_state = gr.State(value=[])
                uploaded_files_display = gr.HTML(value="")
                audio_files_batch = gr.File(
                    label="📂 上传音频（点击选择文件后自动添加）",
                    file_count="multiple",
                    file_types=["audio"],
                    elem_id="audio-upload-zone",
                    height=40,
                )

                input_audio0 = gr.Textbox(visible=False)
                input_audio_preview = gr.Audio(visible=False)

                with gr.Row():
                    clear_files_btn = gr.Button("🗑️ 清空", variant="secondary", size="sm")
                    vc_cancel_btn = gr.Button("✕ 取消", variant="stop", size="sm")
                    but0 = gr.Button("🎤 开始转换", variant="primary", size="lg")

                vc_output_format = gr.Radio(
                    label="🎼 输出格式",
                    choices=_FORMAT_CHOICES,
                    value=_FORMAT_CHOICES[0],
                    info="选择输出音频文件的格式（默认 WAV 无损）",
                )

                gr.HTML('<div style="margin-top:4px;padding:6px 10px;background:rgba(139,92,246,0.05);border-radius:8px;font-size:0.75rem;color:#a78bfa;">💡 提示：支持多文件上传，可多次追加</div>')

                gr.HTML('<hr style="border:none;border-top:1px dashed rgba(139,92,246,0.3);margin:10px 0;">')

                # 转换结果（移到文件夹批量转换上方）
                gr.HTML("""
                <div class="cyber-card" style="margin-top: 8px;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #fff; background: linear-gradient(90deg, #059669, #34d399); margin: -12px -12px 10px -12px; padding: 8px 12px; border-radius: 12px 12px 0 0;">
                        🎧 转换结果
                    </div>
                """)

                vc_output2 = gr.Audio(
                    label=i18n("转换结果"),
                    interactive=False,
                )

                vc_output1 = gr.HTML(
                    label=i18n("状态"),
                    value="",
                )

                # 下载按钮（美化样式，转换完成后显示）
                download_html = gr.HTML(
                    value="""<div id="download-btn-area" style="margin-top: 10px;">
                    <span style="font-size:0.75rem;color:#9ca3af;">💡 转换完成后此处显示下载按钮</span>
                </div>"""
                )

                vc_dir_info = gr.HTML(value="")
                vc_open_dir_btn = gr.Button(
                    "📂 打开输出目录", size="sm", variant="secondary"
                )

                gr.HTML("</div>")

                gr.HTML("""
                <div style="margin-bottom: 8px; background: rgba(139, 92, 246, 0.06); border-radius: 10px; border: 1px solid rgba(139, 92, 246, 0.15);">
                    <div style="font-size: 0.85rem; color: #fff; background: linear-gradient(135deg, #10b981, #34d399); margin: 0; padding: 8px 12px; border-radius: 10px 10px 0 0; display: flex; align-items: center; gap: 8px;">📁 文件夹批量转换</div>

                    <div style="margin: 4px 0; padding: 6px 8px;">
                        <div style="font-size: 0.7rem; color: #a78bfa; line-height: 1.4;">
                            📖 选择文件夹 → 扫描音频 → 逐个转换 · 支持递归 · 关键词过滤 · 错误跳过
                        </div>
                    </div>
                """)

                with gr.Row():
                    dir_scan_input = gr.Textbox(
                        label="文件夹路径",
                        placeholder="粘贴文件夹路径",
                        lines=1,
                        scale=4,
                    )
                    dir_scan_btn = gr.Button("🔍 扫描", variant="primary", size="sm", scale=1)

                with gr.Row():
                    dir_scan_recursive = gr.Checkbox(label="递归子目录", value=True, scale=1)
                    dir_scan_keyword = gr.Textbox(
                        label="关键词(可选)",
                        placeholder="vo,干声,dry",
                        lines=1,
                        scale=2,
                    )

                dir_scan_result = gr.HTML(value="")
                dir_scan_files_state = gr.State(value=[])
                vc_batch_progress = gr.HTML(value="")
                vc_batch_result = gr.HTML(value="")

                with gr.Row():
                    vc_batch_start = gr.Button("🚀 开始批量转换", variant="primary", size="lg", scale=2)
                    vc_batch_cancel = gr.Button("✕ 取消", variant="stop", size="sm", scale=1)

                gr.HTML("</div>")

                gr.HTML('<hr style="border:none;border-top:1px dashed rgba(139,92,246,0.3);margin:10px 0;">')

                # 目录扫描函数
                def scan_directory_for_audio(dir_path, existing_paths=None):
                    """扫描目录，优先获取包含vo/干声的文件，否则获取所有音频"""
                    if existing_paths is None:
                        existing_paths = []
                    if not isinstance(existing_paths, list):
                        existing_paths = []

                    if not dir_path or not os.path.isdir(dir_path):
                        return "❌ 目录不存在或无效", "", None, existing_paths

                    audio_files = []
                    keyword_files = []

                    for root, dirs, files in os.walk(dir_path):
                        for fname in files:
                            ext = os.path.splitext(fname)[1].lower()
                            if ext not in SUPPORTED_AUDIO_EXTS:
                                continue
                            fpath = os.path.join(root, fname)
                            fname_lower = fname.lower()
                            if "vo" in fname_lower or "干声" in fname_lower or "dry" in fname_lower:
                                keyword_files.append(fpath)
                            else:
                                audio_files.append(fpath)

                    # 如果有关键词文件，只返回关键词文件；否则返回所有音频
                    if keyword_files:
                        all_audio = keyword_files
                        audio_files = []  # 清空非关键词列表
                    else:
                        all_audio = audio_files

                    if not all_audio:
                        return "❌ 未找到音频文件", "", None, existing_paths

                    new_paths = [p for p in all_audio if p not in existing_paths]
                    all_paths = list(existing_paths) + new_paths

                    status = f"✅ 扫描完成：找到 {len(all_audio)} 个音频"
                    if keyword_files:
                        status += f"（含 {len(keyword_files)} 个关键词文件）"
                    status += f"，新增 {len(new_paths)} 个"

                    if len(all_paths) > 10:
                        list_html = _build_simple_file_list_html(all_paths)
                    else:
                        list_html = _build_file_list_html(all_paths)

                    return "\n".join(all_paths), status + "<br>" + list_html, all_paths[0] if all_paths else None, all_paths

                # ====== 文件夹批量转换模式 ======

                # 续传+追加的批量上传处理
                def handle_audio_batch(file_obj, existing_paths):
                    import concurrent.futures
                    import threading

                    if file_obj is None:
                        paths_str = (
                            "\n".join(existing_paths) if existing_paths else ""
                        )
                        if existing_paths and len(existing_paths) > 10:
                            list_html = _build_simple_file_list_html(existing_paths)
                        else:
                            list_html = _build_file_list_html(existing_paths)
                        return paths_str, list_html, None, existing_paths
                    try:
                        if isinstance(file_obj, list):
                            _file_count = len(file_obj)
                            if _file_count > MAX_BATCH_COUNT:
                                err_msg = f"⚠️ 批量上限 {MAX_BATCH_COUNT} 个文件，当前 {len(file_obj)} 个"
                                print_status(err_msg, "error")
                                paths_str = (
                                    "\n".join(existing_paths)
                                    if existing_paths
                                    else ""
                                )
                                if existing_paths and len(existing_paths) > 10:
                                    list_html = _build_simple_file_list_html(existing_paths)
                                else:
                                    list_html = _build_file_list_html(existing_paths)
                                return paths_str, list_html, None, existing_paths

                            all_paths = list(existing_paths)
                            new_names = []
                            errors = []
                            existing_basenames = {
                                os.path.basename(p).lower() for p in existing_paths
                            }
                            _lock = threading.Lock()
                            _max_workers = min(4, max(2, (_file_count + 4) // 5))

                            def _copy_single_file(f):
                                orig_name = getattr(f, "orig_name", "") or os.path.basename(f.name)
                                filename = os.path.basename(orig_name) if orig_name else os.path.basename(f.name)
                                with _lock:
                                    if filename.lower() in existing_basenames:
                                        return None, f"已存在，跳过: {filename}", None
                                is_valid, msg, ext = validate_audio_file(f.name)
                                if not is_valid:
                                    return None, f"[{filename}] {msg}", None
                                ok, dest_path, copy_msg = safe_copy_file(f.name, tmp, filename)
                                if ok and dest_path:
                                    with _lock:
                                        existing_basenames.add(os.path.basename(dest_path).lower())
                                    return (dest_path, os.path.basename(dest_path)), None, None
                                return None, f"❌ [{filename}] {copy_msg}", None

                            with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as executor:
                                futures = {executor.submit(_copy_single_file, f): f for f in file_obj}
                                for future in concurrent.futures.as_completed(futures):
                                    result, err, _ = future.result()
                                    if result:
                                        dest_path, basename = result
                                        all_paths.append(dest_path)
                                        new_names.append(basename)
                                    elif err:
                                        errors.append(err)

                            if _file_count > 10:
                                list_html = _build_simple_file_list_html(all_paths)
                            else:
                                list_html = _build_file_list_html(all_paths)

                            if not new_names:
                                return "\n".join(existing_paths) if existing_paths else "", list_html, None, existing_paths

                            status_line = f"✅ 新增 {len(new_names)} 个，共 {len(all_paths)} 个"
                            if errors:
                                status_line += f" | ⚠️ 跳过 {len(errors)} 个"
                            first_path = all_paths[0] if all_paths else None
                            return (
                                "\n".join(all_paths),
                                status_line + "<br>" + list_html,
                                first_path,
                                all_paths,
                            )
    
                        else:
                            # 单文件上传（续传追加）
                            filename = os.path.basename(file_obj.name)
                            existing_basenames = {
                                os.path.basename(p).lower() for p in existing_paths
                            }
                            if filename.lower() in existing_basenames:
                                print_status(
                                    f"⏭️  文件已存在，跳过: {filename}", "warning"
                                )
                                paths_str = (
                                    "\n".join(existing_paths)
                                    if existing_paths
                                    else ""
                                )
                                list_html = _build_file_list_html(existing_paths)
                                return paths_str, list_html, None, existing_paths
                            is_valid, msg, ext = validate_audio_file(file_obj.name)
                            if not is_valid:
                                print_status(f"⏭️  上传跳过: {msg}", "warning")
                                paths_str = (
                                    "\n".join(existing_paths)
                                    if existing_paths
                                    else ""
                                )
                                list_html = _build_file_list_html(existing_paths)
                                return paths_str, list_html, None, existing_paths
                            ok, dest_path, copy_msg = safe_copy_file(
                                file_obj.name, tmp
                            )
                            if ok and dest_path:
                                all_paths = list(existing_paths) + [dest_path]
                                print_status(
                                    f"📤 上传成功: {os.path.basename(dest_path)}",
                                    "success",
                                )
                                list_html = _build_file_list_html(all_paths)
                                return (
                                    "\n".join(all_paths),
                                    f"✅ {os.path.basename(dest_path)}<br>"
                                    + list_html,
                                    dest_path,
                                    all_paths,
                                )
                            print_status(f"❌ 上传失败: {copy_msg}", "error")
                            paths_str = (
                                "\n".join(existing_paths) if existing_paths else ""
                            )
                            list_html = _build_file_list_html(existing_paths)
                            return paths_str, list_html, None, existing_paths
                    except Exception as e:
                        print_status(f"❌ 上传过程异常: {str(e)}", "error")
                        paths_str = (
                            "\n".join(existing_paths) if existing_paths else ""
                        )
                        list_html = _build_file_list_html(existing_paths)
                        return paths_str, list_html, None, existing_paths
    
                def _build_file_list_html(paths):
                    """构建文件列表 HTML，自动根据文件数量选择详细或简化模式"""
                    if not paths:
                        return ""
                    if len(paths) > 10:
                        return _build_simple_file_list_html(paths)
                    items = []
                    total_dur = 0
                    total_size = 0
                    for i, p in enumerate(paths):
                        name = os.path.basename(p)
                        dur, fsize, sr = _get_audio_info(p)
                        total_dur += dur
                        total_size += fsize
                        dur_tag = _fmt_duration(dur)
                        size_tag = _fmt_file_size(fsize)
                        sr_tag = (
                            str(int(sr) / 1000) + "k"
                            if sr >= 1000
                            else str(sr)
                            if sr > 0
                            else ""
                        )
                        meta_parts = []
                        if dur_tag != "--:--":
                            meta_parts.append("⏱ " + dur_tag)
                        if size_tag:
                            meta_parts.append("📦 " + size_tag)
                        if sr_tag:
                            meta_parts.append("🔊 " + sr_tag)
                        meta_str = " | ".join(meta_parts) if meta_parts else ""
                        item_html = '<div style="display:inline-block;background:#f3f4f6;border-radius:6px;padding:4px 10px;margin:2px;min-width:180px;">'
                        item_html += (
                            '<div style="font-size:0.78rem;color:#374151;font-weight:500;">'
                            + str(i + 1)
                            + ". "
                            + name
                            + "</div>"
                        )
                        if meta_str:
                            item_html += (
                                '<div style="font-size:0.68rem;color:#6b7280;margin-top:1px;">'
                                + meta_str
                                + "</div>"
                            )
                        item_html += "</div>"
                        items.append(item_html)
                    summary = ""
                    if len(paths) > 1:
                        summary = '<div style="margin-top:6px;padding:5px 10px;border-radius:6px;background:rgba(59,130,246,0.06);font-size:0.72rem;color:#3b82f6;">'
                        summary += (
                            "共 "
                            + str(len(paths))
                            + " 首 | 总时长 "
                            + _fmt_duration(total_dur)
                            + " | 总大小 "
                            + _fmt_file_size(total_size)
                        )
                        summary += "</div>"
                    return (
                        '<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:4px;">'
                        + "".join(items)
                        + "</div>"
                        + summary
                    )

                def _build_simple_file_list_html(paths):
                    """简化版文件列表：仅显示文件数量和总大小，不获取音频详情（用于大量文件优化）"""
                    if not paths:
                        return ""
                    total_size = 0
                    for p in paths:
                        try:
                            total_size += os.path.getsize(p)
                        except Exception:
                            pass
                    return (
                        '<div style="padding:8px 12px;border-radius:6px;background:rgba(59,130,246,0.08);font-size:0.8rem;color:#94a3b8;">'
                        f'📁 共 {len(paths)} 个文件 | 总大小 {_fmt_file_size(total_size)}'
                        '</div>'
                    )
    
                def clear_uploaded_files(confirm_state):
                    """清空全部已上传文件（两步确认）"""
                    if confirm_state != "clear_pending":
                        return (
                            "",
                            '<div style="color:#f59e0b;font-size:0.82rem;padding:8px;border-radius:8px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">⚠️ 再次点击「🗑️ 清空全部」确认删除所有文件（此操作不可撤销）</div>',
                            None,
                            [],
                            "clear_pending",
                        )
                    return (
                        "",
                        "",
                        None,
                        [],
                        None,
                    )
    
                def delete_single_file(file_num, existing_paths, confirm_state):
                    """根据序号删除单个已上传文件（带确认提示）"""
                    if not existing_paths or file_num is None:
                        list_html = _build_file_list_html(existing_paths)
                        paths_str = (
                            "\n".join(existing_paths) if existing_paths else ""
                        )
                        return (
                            paths_str,
                            list_html,
                            None,
                            existing_paths,
                            confirm_state,
                        )
                    idx = int(file_num) - 1
                    if idx < 0 or idx >= len(existing_paths):
                        list_html = _build_file_list_html(existing_paths)
                        paths_str = (
                            "\n".join(existing_paths) if existing_paths else ""
                        )
                        return (
                            paths_str,
                            list_html,
                            None,
                            existing_paths,
                            confirm_state,
                        )
                    removed_name = os.path.basename(existing_paths[idx])
                    if confirm_state != f"del_{idx}":
                        warn_html = f'<div style="color:#f59e0b;font-size:0.82rem;padding:8px;border-radius:8px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">⚠️ 确认删除「{removed_name}」？再次点击「❌ 删除」确认</div>'
                        return (
                            "\n".join(existing_paths),
                            warn_html
                            + "<br>"
                            + _build_file_list_html(existing_paths),
                            existing_paths[idx],
                            existing_paths,
                            f"del_{idx}",
                        )
                    remaining = [
                        p for i, p in enumerate(existing_paths) if i != idx
                    ]
                    list_html = _build_file_list_html(remaining)
                    paths_str = "\n".join(remaining) if remaining else ""
                    preview = remaining[0] if remaining else None
                    status = f"✅ 已删除 [{int(file_num)}] {removed_name}，剩余 {len(remaining)} 个"
                    return (
                        paths_str,
                        status + "<br>" + list_html,
                        preview,
                        remaining,
                        None,
                    )
    
                def _handle_audio_batch_wrapper(file_obj, existing_paths):
                    """包装上传处理函数：上传后重置File组件，避免缓存显示异常"""
                    result = handle_audio_batch(file_obj, existing_paths)
                    # result = (input_audio0_str, uploaded_files_display_html, preview_path, updated_paths_state)
                    # 追加 None 用于重置 audio_files_batch 组件
                    return result[0], result[1], result[2], result[3], None

                audio_files_batch.upload(
                    fn=_handle_audio_batch_wrapper,
                    inputs=[audio_files_batch, uploaded_paths_state],
                    outputs=[
                        input_audio0,
                        uploaded_files_display,
                        input_audio_preview,
                        uploaded_paths_state,
                        audio_files_batch,
                    ],
                )

                def _dir_scan_do_scan(folder_path, recursive, keyword_filter):
                    """扫描文件夹获取音频文件列表"""
                    result = scan_folder_for_audio(folder_path or "", recursive, keyword_filter or "")
                    if result["success"] and result["total_count"] > 0:
                        files_html = "<div style='margin-top:6px;'>"
                        for i, fp in enumerate(result["files"][:30]):
                            fname = os.path.basename(fp)
                            fsize = os.path.getsize(fp) if os.path.exists(fp) else 0
                            files_html += f"<div style='font-size:0.72rem;color:#a78bfa;padding:2px 4px;border-radius:4px;margin:2px 0;'>{i+1}. {fname} ({_fmt_file_size(fsize)})</div>"
                        if len(result["files"]) > 30:
                            files_html += f"<div style='font-size:0.7rem;color:#9ca3af;text-align:center;margin:4px 0;'>...还有 {len(result['files'])-30} 个文件</div>"
                        files_html += "</div>"
                        return (f"<div style='padding:8px;border-radius:8px;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.2);'><b>{result['message']}</b> (耗时{result['scan_time']}s)</div>{files_html}", result["files"])
                    return (f"<div style='padding:8px;border-radius:8px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);color:#dc2626;'>{result['message']}</div>", [])

                dir_scan_btn.click(
                    fn=_dir_scan_do_scan,
                    inputs=[dir_scan_input, dir_scan_recursive, dir_scan_keyword],
                    outputs=[
                        dir_scan_result,
                        dir_scan_files_state,
                    ],
                )

                def _vc_batch_scan_folder(folder_path, recursive, keyword_filter):
                    """扫描文件夹获取音频文件列表"""
                    result = scan_folder_for_audio(folder_path or "", recursive, keyword_filter or "")
                    if result["success"] and result["total_count"] > 0:
                        files_html = "<div style='margin-top:6px;'>"
                        for i, fp in enumerate(result["files"][:30]):
                            fname = os.path.basename(fp)
                            fsize = os.path.getsize(fp) if os.path.exists(fp) else 0
                            files_html += f"<div style='font-size:0.72rem;color:#a78bfa;padding:2px 4px;border-radius:4px;margin:2px 0;'>{i+1}. {fname} ({_fmt_file_size(fsize)})</div>"
                        if len(result["files"]) > 30:
                            files_html += f"<div style='font-size:0.7rem;color:#9ca3af;text-align:center;margin:4px 0;'>...还有 {len(result['files'])-30} 个文件</div>"
                        files_html += "</div>"
                        return (f"<div style='padding:8px;border-radius:8px;background:#f5f3ff;border:1px solid #c4b5fd;'><b>{result['message']}</b> (耗时{result['scan_time']}s)</div>{files_html}", result["files"])
                    return (f"<div style='padding:8px;border-radius:8px;background:#fef2f2;border:1px solid #fecaca;color:#dc2626;'>{result['message']}</div>", [])

                def _clear_all_files():
                    """清空所有文件"""
                    return "", "", None, [], None, None

                clear_files_btn.click(
                    fn=_clear_all_files,
                    outputs=[
                        input_audio0,
                        uploaded_files_display,
                        input_audio_preview,
                        uploaded_paths_state,
                        audio_files_batch,
                        svc_warning,
                    ],
                )

                gr.HTML("</div>")
    
            # ==================== 右侧栏：参数 + 转换 + 结果 ====================
            with gr.Column(scale=1):
                gr.HTML("""
                <div style="padding:6px 10px;border-radius:8px;background:linear-gradient(135deg,rgba(59,130,246,0.06),rgba(96,165,250,0.03));border:1px solid rgba(59,130,246,0.15);margin-bottom:6px;">
                    <div style="font-size:0.78rem;color:#3b82f6;font-weight:600;">⚙️ 高级参数</div>
                </div>""")
                f0method0 = gr.Dropdown(
                    choices=["rmvpe", "pm", "crepe", "crepe-tiny", "fcpe", "hybrid"],
                    value="rmvpe",
                    label="F0提取方法",
                    interactive=True,
                )
                with gr.Row():
                    index_rate1 = gr.Slider(
                        0.0, 1.0, step=0.01, value=0.75,
                        label="Index比率", info="越高越像原声",
                    )
                    filter_radius0 = gr.Slider(
                        0, 7, step=1, value=3,
                        label="滤波半径", visible=False,
                    )
                with gr.Row():
                    rmvpe_hop0 = gr.Slider(
                        64, 512, step=32, value=128,
                        label="RMVPE Hop", info="精度/速度",
                    )
                    resample_sr0 = gr.Slider(
                        0, 48000, step=1000, value=0,
                        label="重采样率", visible=False,
                    )

                with gr.Accordion("🎛️ 转换参数（变调/保护度）", open=False):
                    vc_transform_single = gr.Slider(
                        minimum=-24,
                        maximum=24,
                        step=1,
                        label="🎵 变调（半音）",
                        value=0,
                        info="男转女：+12 | 女转男：-12",
                    )

                    with gr.Row():
                        protect0 = gr.Slider(
                            minimum=0,
                            maximum=0.5,
                            step=0.01,
                            label=i18n("保护度"),
                            value=0.33,
                        )
                        spk_item = gr.Slider(
                            minimum=0,
                            maximum=2333,
                            step=1,
                            label=i18n("说话人ID"),
                            value=0,
                            visible=False,
                            interactive=True,
                        )

                def clear_all_models():
                    return {
                        "choices": get_model_list(),
                        "value": None,
                        "__type__": "update",
                    }
    
                gr.HTML("""
                <div style="margin: 8px 0; padding: 10px 14px; border-radius: 10px; background: linear-gradient(135deg, rgba(124,58,237,0.08), rgba(139,92,246,0.04)); border: 1px solid rgba(124,58,237,0.2);">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <span style="font-size:0.82rem;color:#7c3aed;font-weight:700;">🎵 MXGF.CC</span>
                        <span style="background:linear-gradient(90deg,#7c3aed,#a78bfa);color:#fff;font-size:9px;padding:1px 6px;border-radius:8px;font-weight:600;">官方</span>
                    </div>
                    <div style="font-size:0.75rem;color:#8b5cf6;">
                        全网最优质最全面RVC/SVC声音模型 · 定制声音模型 · 探索前沿AI声音项目 → <b><a href="https://mxgf.cc" target="_blank" style="color:#7c3aed;text-decoration:underline;">mxgf.cc</a></b>
                    </div>
                </div>""")
    
                # 清空按钮事件（绑定到左侧 sid0）
                clear_all_btn2.click(fn=clear_all_models, outputs=[sid0])
    
                # 获取GPU显存信息
                def get_gpu_memory_info():
                    try:
                        import torch
    
                        if torch.cuda.is_available():
                            mem_used = (
                                torch.cuda.memory_allocated(0) / 1024 / 1024 / 1024
                            )
                            mem_total = (
                                torch.cuda.get_device_properties(0).total_memory
                                / 1024
                                / 1024
                                / 1024
                            )
                            return f"{mem_used:.1f}GB / {mem_total:.1f}GB"
                        return "无GPU"
                    except Exception:
                        return "未知"
    
        # 刷新按钮事件（在所有变量定义完成后）
        def _refresh_models_and_index():
            model_names = get_model_list()
            selected_model = model_names[0] if model_names else None
            index_choices = get_index_list()
            return (
                {"choices": model_names, "value": selected_model, "__type__": "update"},
                {
                    "choices": index_choices,
                    "__type__": "update",
                    "value": get_index_path_from_model(selected_model),
                },
                _get_svc_warning(),
            )

        refresh_button.click(
            fn=_refresh_models_and_index,
            inputs=[],
            outputs=[sid0, file_index2, svc_warning],
        )

        def _vc_handle_model_upload(file_obj, custom_name):
            if file_obj is None:
                return '<div style="padding:4px 8px;border-radius:6px;background:rgba(245,158,11,0.1);color:#f59e0b;font-size:0.74rem;">⚠️ 请选择 .pth 模型文件</div>'
            try:
                result = upload_model(file_obj, custom_name)
                return (
                    '<div style="padding:4px 8px;border-radius:6px;background:rgba(16,185,129,0.1);color:#10b981;font-size:0.74rem;">✅ '
                    + str(result)
                    + "（请点击🔄刷新）</div>"
                )
            except RecursionError:
                return '<div style="padding:4px 8px;border-radius:6px;background:rgba(239,68,68,0.1);color:#ef4444;font-size:0.74rem;">❌ 上传异常: 文件对象包含循环引用，请重试</div>'
            except Exception as e:
                _msg = str(e)
                if len(_msg) > 200:
                    _msg = _msg[:200] + "..."
                return (
                    '<div style="padding:4px 8px;border-radius:6px;background:rgba(239,68,68,0.1);color:#ef4444;font-size:0.74rem;">❌ 上传失败: '
                    + _msg
                    + "</div>"
                )

        vc_upload_model_btn.click(
            fn=_vc_handle_model_upload,
            inputs=[vc_model_file, vc_model_custom_name],
            outputs=[vc_model_upload_status],
        )

        def change_model_wrapper(selected_models, protect0_val):
            """模型选择变更回调：调用 vc.get_vc 真正加载模型，
            正确设置说话人ID范围、保护度可见性、自动匹配索引文件"""
            # Radio 返回字符串；兼容旧的列表形态
            model_name = selected_models[0] if isinstance(selected_models, list) and selected_models else (selected_models or "")
            if not model_name:
                # 无选择时：隐藏说话人ID、重置保护度和索引
                return (
                    gr.update(visible=False, value=0),
                    gr.update(value=0.33, visible=True),
                    gr.update(value=None),
                    "",
                )
            # 300MB SVC 模型检查
            pth_path = os.path.join(weight_root, model_name)
            try:
                size_mb = os.path.getsize(pth_path) / (1024 * 1024)
                if size_mb > 300:
                    print_status(
                        f"❌ 拒绝加载 {model_name} ({round(size_mb, 0)}MB): 超过300MB，可能是SVC模型",
                        "error",
                    )
                    return (
                        gr.update(visible=False, value=0),
                        gr.update(value=0.33, visible=True),
                        gr.update(value=None),
                        f'<div style="padding:6px 10px;border-radius:6px;background:rgba(239,68,68,0.12);border-left:3px solid #ef4444;"><span style="color:#fca5a5;font-size:0.75rem;">❌ {model_name} ({round(size_mb, 0)}MB) 超过300MB限制</span></div>',
                    )
            except Exception as e:
                print_status(f"⚠️ 获取文件大小失败: {e}", "warning")
            index_value = get_index_path_from_model(model_name)
            all_indices = get_index_list()
            index_update = gr.update(choices=all_indices, value=index_value) if index_value else gr.update(value=None)
            return (
                gr.update(visible=True, value=0, maximum=100),
                gr.update(value=protect0_val if protect0_val is not None else 0.33, visible=True),
                index_update,
                f'<div style="padding:4px 8px;border-radius:6px;background:rgba(16,185,129,0.08);color:#10b981;font-size:0.74rem;">✅ 已选择 {model_name}，点击转换时加载模型</div>',
            )
    
        sid0.change(
            fn=change_model_wrapper,
            inputs=[sid0, protect0],
            outputs=[spk_item, protect0, file_index2, svc_warning],
        )
    
        def vc_single_wrapper(selected_models, *args, output_format="wav"):
            """干声转换：单模型×多音频批量遍历。Radio 返回字符串。"""
            if isinstance(selected_models, str):
                selected_models = [selected_models] if selected_models else []
            # 🧪 触发服务器压力测试
            start_pressure_test()
            _lt = None
            _dir_html = ""

            # ---- 提前验证：未选择模型 ----
            if not selected_models or len(selected_models) == 0:
                _pth_count = 0
                try:
                    for _f in os.listdir(weight_root):
                        if _f.endswith(".pth"):
                            _pth_count += 1
                except Exception:
                    pass
                hidden_html = """<div id="download-btn-area" style="display:none; margin-top: 10px;"></div>"""
                if _pth_count == 0:
                    return (
                        '<div style="padding:10px 14px;border-radius:10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);"><span style="color:#f59e0b;font-weight:700;font-size:0.85rem;">⚠️ 请先上传AI模型</span><div style="font-size:0.74rem;color:#d97706;margin-top:4px;">📦 当前没有可用模型，请先通过左侧「上传模型」功能上传 .pth 模型文件后刷新</div></div>',
                        None,
                        hidden_html,
                        "",
                        _get_taskbar_html(),
                    )
                else:
                    return (
                        f'<div style="padding:10px 14px;border-radius:10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);"><span style="color:#f59e0b;font-weight:700;font-size:0.85rem;">⚠️ 请选择音色模型</span><div style="font-size:0.74rem;color:#d97706;margin-top:4px;">🎤 已检测到 {_pth_count} 个可用模型，请在左侧列表中选择一个音色模型</div></div>',
                        None,
                        hidden_html,
                        "",
                        _get_taskbar_html(),
                    )

            # ---- 提前验证：未上传音频 ----
            _has_audio = False
            # uploaded_paths_state 是最后一个args参数
            _uploaded_state = args[-1] if args else None
            if _uploaded_state and isinstance(_uploaded_state, list) and len(_uploaded_state) > 0:
                _uploaded_state = filter_fresh_runtime_uploads(_uploaded_state)
                _has_audio = len(_uploaded_state) > 0
            if not _has_audio:
                hidden_html = """<div id="download-btn-area" style="display:none; margin-top: 10px;"></div>"""
                return (
                    '<div style="padding:10px 14px;border-radius:10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);"><span style="color:#f59e0b;font-weight:700;font-size:0.85rem;">⚠️ 请先上传音频文件</span><div style="font-size:0.74rem;color:#d97706;margin-top:4px;">🎵 请在上方音频区域上传需要转换的音频文件（支持mp3/wav/flac等格式）</div></div>',
                    None,
                    hidden_html,
                    "",
                    _get_taskbar_html(),
                )

            try:
                if not _acquire_exec("vc_convert", "干声转换"):
                    hidden_html = """<div id="download-btn-area" style="display:none; margin-top: 10px;"></div>"""
                    return (
                        "⚠️ 当前有转换任务正在运行",
                        None,
                        hidden_html,
                        "",
                        _get_taskbar_html(),
                    )
                _clear_cancel("vc_convert")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
    
                # 优先使用 uploaded_paths_state 中已上传的文件路径
                _uploaded_state = args[-1] if args else None
                if _uploaded_state and isinstance(_uploaded_state, list) and len(_uploaded_state) > 0:
                    all_paths = filter_fresh_runtime_uploads(
                        [p for p in _uploaded_state if isinstance(p, str) and p.strip()]
                    )
                else:
                    all_paths = []
    
                if not all_paths:
                    _release_exec("vc_convert")
                    hidden_html = """<div id="download-btn-area" style="display:none; margin-top: 10px;"></div>"""
                    return (
                        '<div style="padding:10px 14px;border-radius:10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);"><span style="color:#f59e0b;font-weight:700;font-size:0.85rem;">⚠️ 音频文件缺失</span><div style="font-size:0.74rem;color:#d97706;margin-top:4px;">上传的音频文件未找到，请重新上传后重试</div></div>',
                        None,
                        hidden_html,
                        "",
                        _get_taskbar_html(),
                    )
    
                _batch_model = selected_models[0] if selected_models else ""
                _lt = _LiveTaskCtx(
                    f"🔊 干声转换 · {safe_model_name(_batch_model)}", "vc_convert"
                )
                output_dir = get_output_dir("batch", _batch_model)
                import soundfile as sf
    
                results = []
                last_audio = None
                last_output_file = None
                total_tasks = len(selected_models) * len(all_paths)
                task_num = 0
    
                for model_name in selected_models:
                    if _is_cancelled("vc_convert"):
                        break
                    model_label = safe_model_name(model_name)
                    _lt.update(
                        int(task_num / max(total_tasks, 1) * 90),
                        f"转换中: {model_label}",
                    )
                    _update_task_name("vc_convert", f"加载: {model_label}")
                    try:
                        get_vc().get_vc(model_name, 0.33, 0.33)
                    except RecursionError:
                        import sys as _sys2
    
                        try:
                            _sys2.exc_clear()
                        except Exception:
                            pass
                        results.append(
                            "✗ 模型 [" + model_label + "] 加载异常(循环引用)"
                        )
                        continue
                    except Exception as e:
                        results.append(
                            "✗ 模型 ["
                            + model_label
                            + "] 加载失败 ("
                            + _friendly_err(e)
                            + ")"
                        )
                        continue
    
                    for audio_path in all_paths:
                        task_num += 1
                        base_name = os.path.splitext(os.path.basename(audio_path))[
                            0
                        ]
                        _lt.update(
                            int(task_num / max(total_tasks, 1) * 90),
                            f"[{task_num}/{total_tasks}] {base_name}",
                        )
                        _update_task_name("vc_convert", f"{model_label}: {base_name}")
                        try:
                            batch_args = list(args)
                            batch_args[1] = audio_path
                            result = get_vc().vc_single(
                                sid=int(batch_args[0]) if batch_args[0] is not None else 0,
                                input_audio_path=batch_args[1],
                                f0_up_key=int(batch_args[2]) if batch_args[2] is not None else 0,
                                f0_method=batch_args[4] or "rmvpe",
                                f0_file=batch_args[3],
                                file_index=batch_args[5] or "",
                                file_index2=batch_args[6],
                                index_rate=float(batch_args[7]) if batch_args[7] is not None else 0.75,
                                filter_radius=int(batch_args[8]) if batch_args[8] is not None else 3,
                                resample_sr=int(batch_args[9]) if batch_args[9] is not None else 0,
                                rms_mix_rate=float(batch_args[10]) if batch_args[10] is not None else 1.0,
                                protect=float(batch_args[11]) if batch_args[11] is not None else 0.33,
                            )
    
                            if result[1] is None or (
                                isinstance(result[1], tuple)
                                and result[1][1] is None
                            ):
                                results.append(
                                    f"✗ [{model_label}] {base_name}: 转换失败"
                                )
                                continue
    
                            if isinstance(result[1], tuple) and len(result[1]) == 2:
                                sr, audio = result[1]
                                from tabs.shared import generate_filename
                                _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                output_filename = generate_filename(
                                    model_name=model_label,
                                    song_name=base_name,
                                    file_type="转换",
                                    ext=_ext,
                                    target_dir=output_dir,
                                )
                                save_audio_with_format(audio, sr, output_filename, output_format)
                                results.append(
                                    "✓ [" + model_label + "] " + base_name
                                )
                                last_audio = output_filename
                                last_output_file = output_filename
                        except Exception as e:
                            results.append(
                                "✗ ["
                                + model_label
                                + "] "
                                + base_name
                                + ": "
                                + _friendly_err(e)
                            )
    
                ok_count = sum(1 for r in results if r.startswith("✓"))
                fail_count = sum(1 for r in results if r.startswith("✗"))
                result_rows = ""
                for r in results:
                    if r.startswith("✓"):
                        result_rows += (
                            '<div style="padding:3px 8px;font-size:0.78rem;color:#059669;background:rgba(5,150,105,0.06);border-radius:4px;margin:2px 0;">'
                            + r
                            + "</div>"
                        )
                    else:
                        result_rows += (
                            '<div style="padding:3px 8px;font-size:0.78rem;color:#ef4444;background:rgba(239,68,68,0.06);border-radius:4px;margin:2px 0;">'
                            + r
                            + "</div>"
                        )
                summary_html = (
                    '<div style="margin-top:6px;"><div style="display:flex;gap:12px;margin-bottom:6px;font-size:0.82rem;"><span style="color:#059669;font-weight:600;">✅ 成功 '
                    + str(ok_count)
                    + '</span><span style="color:#ef4444;font-weight:600;">❌ 失败 '
                    + str(fail_count)
                    + '</span><span style="color:#64748b;">共 '
                    + str(total_tasks)
                    + ' 任务</span></div><div style="max-height:200px;overflow-y:auto;padding:4px;border-radius:8px;background:rgba(15,23,42,0.3);">'
                    + result_rows
                    + "</div></div>"
                )
    
                dl_html = build_download_html(
                    last_output_file
                    if (last_output_file and os.path.exists(last_output_file))
                    else None,
                    "📥 下载最后转换结果",
                    "green",
                )
                if last_output_file and os.path.exists(last_output_file):
                    dl_html = dl_html.replace(
                        "</div>",
                        '<span style="font-size:0.75rem;color:#64748b;margin-left:8px;">全部结果已保存到 AI批量转换目录</span></div>',
                    )
                _lt.update(100, f"✅ 完成 {ok_count}/{total_tasks}")
                _dir_html = (
                    '<div style="margin-top:8px;padding:10px 14px;border-radius:10px;background:linear-gradient(135deg,rgba(5,150,105,0.08),rgba(52,211,153,0.04));border:1px solid rgba(5,150,105,0.25);"><span style="font-size:0.78rem;color:#059669;font-weight:600;">📂 输出目录</span><div style="font-size:0.72rem;color:#34d399;font-family:monospace;margin-top:2px;">'
                    + output_dir.replace(chr(92), "/")
                    + '</div><div style="font-size:0.72rem;color:#9ca3af;margin-top:2px;">共 '
                    + str(ok_count)
                    + " 个文件 | "
                    + str(len(selected_models))
                    + " 模型 × "
                    + str(len(all_paths))
                    + " 音频</div></div>"
                )
                _clear_cancel("vc_convert")
                _release_exec("vc_convert")
                if _lt:
                    _lt.complete(success=True)
                mark_task_completed("音色转换")
                notify_done("RVC 音色转换完成", f"成功 {ok_count}/{total_tasks}")
                return (
                    summary_html,
                    last_audio,
                    dl_html,
                    _dir_html,
                    _get_taskbar_html(),
                )
            except Exception as e:
                if _lt:
                    _lt.complete(success=False, error=str(e))
                raise
            finally:
                _clear_cancel("vc_convert")
                if _is_executing("vc_convert"):
                    _release_exec("vc_convert")
    
        but0.click(
            vc_single_wrapper,
            [
                sid0,
                spk_item,
                input_audio0,
                vc_transform_single,
                f0_file,
                f0method0,
                file_index1,
                file_index2,
                index_rate1,
                filter_radius0,
                resample_sr0,
                rms_mix_rate0,
                protect0,
                vc_output_format,
                uploaded_paths_state,
            ],
            [vc_output1, vc_output2, download_html, vc_dir_info, _global_taskbar],
        )

        def _vc_batch_process(batch_files, selected_models, pitch_val, index_rate_val, protect_val, output_format="wav"):
            """批量音色转换处理函数"""
            import time as _t
            if isinstance(selected_models, str):
                selected_models = [selected_models] if selected_models else []
            if not batch_files or len(batch_files) == 0:
                yield "⚠️ 请先扫描文件夹", "", _get_taskbar_html()
                return
            if not selected_models or len(selected_models) == 0:
                yield "⚠️ 请选择至少一个模型", "", _get_taskbar_html()
                return

            if not _acquire_exec("batch_convert", "批量转换"):
                yield "⚠️ 当前有转换任务正在运行，请等待完成", "", _get_taskbar_html()
                return

            total = len(batch_files)
            success_count = 0
            fail_count = 0
            errors = []
            start_time = _t.time()

            for idx, audio_path in enumerate(batch_files):
                if _is_cancelled("voice_convert"):
                    errors.append({"file": os.path.basename(audio_path), "error": "用户取消"})
                    fail_count += 1
                    continue

                base_name = os.path.splitext(os.path.basename(audio_path))[0]
                elapsed = _t.time() - start_time
                _update_task_name("batch_convert", f"({idx+1}/{total}) {base_name}")
                yield build_batch_progress_html(base_name, idx + 1, total, success_count, fail_count, elapsed), "", _get_taskbar_html()

                try:
                    for model_name in selected_models:
                        try:
                            get_vc().get_vc(model_name, 0.33, 0.33)
                        except Exception as _load_err:
                            errors.append({"file": base_name + " [" + model_name + "]", "error": f"模型加载失败: {_load_err}"})
                            fail_count += 1
                            continue
                        matched_index = get_index_path_from_model(model_name)
                        audio_opt = get_vc().vc_single(
                            sid=0,
                            input_audio_path=audio_path,
                            f0_up_key=int(pitch_val) if pitch_val is not None else 0,
                            f0_file=None,
                            f0_method="rmvpe",
                            file_index="",
                            file_index2=matched_index,
                            index_rate=float(index_rate_val) if index_rate_val is not None else 0.75,
                            filter_radius=3,
                            resample_sr=0,
                            rms_mix_rate=1.0,
                            protect=float(protect_val) if protect_val is not None else 0.33,
                        )
                        if audio_opt and isinstance(audio_opt, tuple) and len(audio_opt) >= 2:
                            audio_data = audio_opt[1]
                            if audio_data is None or (isinstance(audio_data, tuple) and len(audio_data) == 2 and audio_data[1] is None):
                                errors.append({"file": base_name + " [" + model_name + "]", "error": "转换输出为空"})
                                fail_count += 1
                                continue
                            if isinstance(audio_data, tuple) and len(audio_data) == 2:
                                sr_val, arr_data = audio_data
                                if sr_val is not None and arr_data is not None:
                                    out_dir = get_output_dir("batch", model_name)
                                    _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                    out_name = generate_save_filename(model_name, base_name, "成品")
                                    _base_no_ext, _ = os.path.splitext(out_name)
                                    out_name = f"{_base_no_ext}{_ext}" if _ext else out_name
                                    out_path = os.path.join(out_dir, out_name)
                                    save_audio_with_format(arr_data, sr_val, out_path, output_format)
                                    success_count += 1
                                else:
                                    errors.append({"file": base_name + " [" + model_name + "]", "error": "转换输出无效"})
                                    fail_count += 1
                            else:
                                errors.append({"file": base_name + " [" + model_name + "]", "error": "转换输出格式异常"})
                                fail_count += 1
                        else:
                            errors.append({"file": base_name + " [" + model_name + "]", "error": "转换输出为空"})
                            fail_count += 1
                except Exception as e:
                    errors.append({"file": base_name, "error": str(e)})
                    fail_count += 1

            elapsed = _t.time() - start_time
            _clear_cancel("voice_convert")
            _release_exec("batch_convert")
            mark_task_completed(f"批量转换 {success_count}/{total}")
            notify_done("RVC 批量转换完成", f"成功 {success_count}/{total}")
            yield build_batch_progress_html("完成", total, total, success_count, fail_count, elapsed), build_batch_result_html(total, success_count, fail_count, errors, ""), _get_taskbar_html()

        vc_batch_start.click(
            fn=_vc_batch_process,
            inputs=[dir_scan_files_state, sid0, vc_transform_single, index_rate1, protect0, vc_output_format],
            outputs=[vc_batch_progress, vc_batch_result, _global_taskbar],
        )
        vc_batch_cancel.click(
            fn=lambda: (_get_taskbar_html(), ""),
            inputs=[],
            outputs=[_global_taskbar, vc_batch_progress],
        )

        def _vc_cancel_task():
            _request_cancel("vc_convert")
            return "⚠️ 正在取消任务...", None, "", "", _get_taskbar_html()

        vc_cancel_btn.click(
            fn=_vc_cancel_task, inputs=[], outputs=[vc_output1, vc_output2, download_html, vc_dir_info, _global_taskbar]
        )
    
        def _vc_open_dir():
            d = get_output_dir("batch", "")
            try:
                os.startfile(d)
                return (
                    '<div style="color:#059669;font-size:0.8rem;">✅ 已打开: '
                    + d
                    + "</div>"
                )
            except Exception as e:
                return (
                    '<div style="color:#ef4444;font-size:0.8rem;">❌ 打开失败: '
                    + str(e)
                    + "</div>"
                )
    
        vc_open_dir_btn.click(fn=_vc_open_dir, inputs=[], outputs=[vc_dir_info])
    
        # ai_cover_btn.click(...)  — 已迁移至 🎯 一键AI翻唱 顶级Tab
        # ai_cover_open_dir.click(...)  — 已迁移至 🎯 一键AI翻唱 顶级Tab
    
        # 批量转换按钮
        def vc_batch_convert(
            selected_models,
            audio_paths_text,
            transform,
            f0method,
            f0file,
            index1,
            index2,
            index_rate,
            filter_radius,
            resample_sr,
            rms_mix_rate,
            protect,
            output_format="wav",
        ):
            """批量转换：单模型 × 多音频文件"""
            output_format = resolve_format(output_format)
            if isinstance(selected_models, str):
                selected_models = [selected_models] if selected_models else []
            _lt = None
            try:
                if not _acquire_exec("batch_convert", "批量转换"):
                    return "⚠️ 当前有批量转换任务正在运行", None
                model_name = selected_models[0] if selected_models else None
                if not model_name:
                    _release_exec("batch_convert")
                    return "⚠️ 请先选择模型", None
                if not audio_paths_text:
                    _release_exec("batch_convert")
                    return "⚠️ 请先批量上传音频文件", None
                _bm = selected_models[0] if selected_models else ""
                _lt = _LiveTaskCtx(
                    f"📦 批量转换 · {safe_model_name(_bm)}", "batch_convert"
                )
                output_dir = get_output_dir("batch", _bm)
    
                raw_audio = audio_paths_text
                if isinstance(raw_audio, list):
                    audio_paths = []
                    for item in raw_audio:
                        if item is None:
                            continue
                        if isinstance(item, str):
                            audio_paths.append(item)
                        elif hasattr(item, "name"):
                            n = getattr(item, "name", "")
                            if n:
                                audio_paths.append(str(n))
                        else:
                            audio_paths.append(str(item))
                elif isinstance(raw_audio, str):
                    audio_paths = raw_audio.strip().split("\n")
                else:
                    n = getattr(raw_audio, "name", "")
                    audio_paths = [str(n)] if n else []
                audio_paths = [p.strip() for p in audio_paths if p.strip()]
    
                if not audio_paths:
                    _release_exec("batch_convert")
                    return "⚠️ 没有找到音频文件", None
    
                all_results = []
                all_output_files = []
    
                for i, audio_path in enumerate(audio_paths):
                    _lt.update(
                        int((i + 1) / max(len(audio_paths), 1) * 90),
                        f"[{i + 1}/{len(audio_paths)}] {os.path.basename(audio_path)}",
                    )
                    _update_task_name("batch_convert", f"({i+1}/{len(audio_paths)}) {os.path.basename(audio_path)}")
                    try:
                        print_status(
                            f"🔄 正在转换 [{i + 1}/{len(audio_paths)}]: {os.path.basename(audio_path)}",
                            "convert",
                        )
                        result = get_vc().vc_single(
                            sid=0,
                            input_audio_path=audio_path,
                            f0_up_key=int(transform) if transform is not None else 0,
                            f0_method=f0method or "rmvpe",
                            f0_file=f0file,
                            file_index=index1 or "",
                            file_index2=index2,
                            index_rate=float(index_rate) if index_rate is not None else 0.75,
                            filter_radius=int(filter_radius) if filter_radius is not None else 3,
                            resample_sr=int(resample_sr) if resample_sr is not None else 0,
                            rms_mix_rate=float(rms_mix_rate) if rms_mix_rate is not None else 1.0,
                            protect=float(protect) if protect is not None else 0.33,
                        )
                        if result[1] is not None and not (
                            isinstance(result[1], tuple) and result[1][1] is None
                        ):
                            output_file = result[1]
                            all_output_files.append(output_file)
    
                            if (
                                isinstance(output_file, tuple)
                                and len(output_file) == 2
                            ):
                                sr, audio = output_file
                                from tabs.shared import generate_filename
                                _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                output_filename = generate_filename(
                                    model_name=model_name,
                                    song_name=audio_path,
                                    file_type="转换",
                                    ext=_ext,
                                    target_dir=output_dir,
                                )

                                save_audio_with_format(audio, sr, output_filename, output_format)
                                print_status(
                                    f"💾 转换结果已保存: {os.path.basename(output_filename)} (格式: {output_format.upper()})",
                                    "success",
                                )
    
                            all_results.append(
                                f"✓ {os.path.basename(audio_path)} 转换成功"
                            )
                        else:
                            all_results.append(
                                f"✗ {os.path.basename(audio_path)} 转换失败"
                            )
                    except Exception as e:
                        all_results.append(
                            f"✗ {os.path.basename(audio_path)} 错误：{str(e)}"
                        )
    
                summary = "\n".join(all_results)
                first_output = all_output_files[0] if all_output_files else None
                _lt.update(100, "✅ 批量完成")
                _release_exec("batch_convert")
                if _lt:
                    _lt.complete(success=True)
                mark_task_completed("批量转换")
                notify_done("RVC 批量转换完成", f"输出目录: {output_dir}")
                return (
                    f"批量转换完成 (输出目录: {output_dir})\n{summary}",
                    first_output,
                )
            except Exception as e:
                if _lt:
                    _lt.complete(success=False, error=str(e))
                raise
            finally:
                if _is_executing("batch_convert"):
                    _release_exec("batch_convert")

    # ==================== 音频工具箱 Tab ====================
    
