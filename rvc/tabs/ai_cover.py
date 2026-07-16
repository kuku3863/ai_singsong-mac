# -*- coding: utf-8 -*-
"""ai_cover tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the ai_cover tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import *
from tabs.shared import (
    _progress_html, _html_escape, _fmt_file_size, _friendly_err,
    _has_separator, _LiveTaskCtx, _output_history,
    _SEP_CACHE_ROOT,
    _FORMAT_CHOICES, save_audio_with_format, resolve_format,
)
from tabs.header import _acquire_exec, _release_exec, _is_executing, _get_taskbar_html, _request_cancel, _is_cancelled, _clear_cancel, _update_task_name
from tabs.state import get_taskbar, mark_task_completed
from tabs.pressure_test import start_pressure_test
import os
import subprocess
import threading
import time
import sys


def _ac_model_list(value):
    """Normalize Radio and legacy CheckboxGroup values to a model list."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if isinstance(v, str) and v]
    return []


def _build_file_list_html(paths):
    """将文件路径列表渲染为带序号的HTML列表，用于上传文件展示。"""
    if not paths:
        return ""
    parts = []
    for i, p in enumerate(paths):
        name = os.path.basename(p) if p else "未知"
        try:
            size = os.path.getsize(p)
            size_str = _fmt_file_size(size) if size > 0 else ""
        except Exception:
            size_str = ""
        size_span = '<span style="color:#64748b;font-size:0.7rem;margin-left:auto;">{}</span>'.format(size_str) if size_str else ""
        parts.append(
            '<div style="display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:4px;background:rgba(59,130,246,0.04);font-size:0.76rem;">'
            '<span style="color:#3b82f6;font-weight:700;min-width:24px;">{}</span>'
            '<span style="color:#e2e8f0;">{}</span>'
            '{}</div>'.format(i + 1, name, size_span)
        )
    return "".join(parts)


def _build_simple_file_list_html(paths):
    """简化版文件列表：仅显示文件数量和总大小，不渲染每个文件的详细信息（用于大量文件优化）"""
    if not paths:
        return ""
    total_size = 0
    for p in paths:
        try:
            total_size += os.path.getsize(p)
        except Exception:
            pass
    size_str = _fmt_file_size(total_size) if total_size > 0 else ""
    return (
        '<div style="padding:8px 12px;border-radius:6px;background:rgba(59,130,246,0.08);font-size:0.8rem;color:#94a3b8;">'
        f'📁 共 {len(paths)} 个文件 {f"| {size_str}" if size_str else ""}'
        '</div>'
    )


def build_ai_cover_tab():
    """Build the ai_cover tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    # 从全局状态获取taskbar组件（必须在build_header()之后调用）
    _global_taskbar, _global_sched_action = get_taskbar()

    # ==================== 🎯 一键AI翻唱（子Tab） ====================
    with gr.TabItem("🎯 AI翻唱", id="ai_cover_main"):
            gr.HTML("""
            <div style="margin-bottom:12px;">
                <div style="font-size:0.9rem;color:#fff;background:linear-gradient(135deg,#ef4444,#f97316,#fb923c);margin:0;padding:14px 16px;border-radius:12px;display:flex;align-items:center;gap:10px;">
                    <span style="font-size:1.3rem;">🎯</span>
                    <span style="font-weight:700;font-size:1rem;">一键AI翻唱</span>
                    <span style="font-size:0.78rem;opacity:0.85;">上传歌曲 → 选择模型 → 自动分离/去混响/转换/混音</span>
                </div>
                <div style="margin-top:8px;padding:10px 14px;border-radius:10px;background:rgba(239,68,68,0.05);border-left:3px solid #f97316;">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                        <span style="color:#f97316;font-weight:700;font-size:0.82rem;">💡 与「音色转换」的区别</span>
                    </div>
                    <table style="width:100%;font-size:0.75rem;color:#d4a574;border-collapse:collapse;">
                        <tr><td style="padding:3px 8px 3px 0;width:90px;white-space:nowrap;"><b>🎯 一键AI翻唱</b></td><td>全自动流水线：分离人声 → 去除混响 → 变调 → 音色转换 → AI智能混音。适合<span style="color:#f97316;">快速出成品</span>，支持多模型批量处理。</td></tr>
                        <tr><td style="padding:3px 8px 3px 0;white-space:nowrap;"><b>🎤 音色转换</b></td><td>手动精细控制：需要自己准备干声，可调 f0方法/index率/保护等高级参数。适合<span style="color:#d4a574;">专业用户精确调整</span>。</td></tr>
                    </table>
                    <div style="margin-top:6px;padding:5px 10px;border-radius:6px;background:rgba(249,115,22,0.08);font-size:0.74rem;color:#fbbf24;">
                        ⚡ 推荐新用户使用「一键AI翻唱」，一键完成全流程
                    </div>
                </div>
            </div>""")
    
            with gr.Row():
                with gr.Column(scale=1):
                    ac_sid = gr.Radio(
                        label="🎤 选择音色模型",
                        choices=sorted(names),
                        value=None,
                        interactive=True,
                    )
                    ac_model_search = gr.Textbox(
                        label="🔍 搜索模型",
                        placeholder="输入关键词过滤模型列表...",
                    )
                    gr.HTML("""<div style="margin-top: 8px; display: flex; justify-content: center;">
                        <a href="https://mxgf.cc" target="_blank" rel="noopener noreferrer" style="
                            display: inline-flex; align-items: center; justify-content: center; gap: 10px;
                            padding: 14px 48px; border-radius: 14px; text-decoration: none;
                            font-size: 1.15rem; font-weight: 700; color: #fff;
                            background: linear-gradient(135deg, #1B4D3E, #2E6B4F, #4A9079, #5FAA8C);
                            box-shadow: 0 6px 20px rgba(27, 77, 62, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.25);
                            border: 1px solid rgba(79, 155, 123, 0.5);
                            transition: all 0.25s ease;
                            letter-spacing: 2px; cursor: pointer; width: 100%;
                        " onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 28px rgba(27, 77, 62, 0.7)'"
                           onmouseout="this.style.transform='';this.style.boxShadow='0 6px 20px rgba(27, 77, 62, 0.5)'">
                            🎩 模型工坊
                        </a>
                    </div>""")
                    with gr.Row():
                        ac_refresh_btn = gr.Button(
                            "🔄 刷新", variant="primary", size="sm"
                        )
                        ac_unload_btn = gr.Button(
                            "🗑️ 卸载", variant="secondary", size="sm"
                        )
                    with gr.Row():
                        ac_select_all_btn = gr.Button(
                            "☑️ 全选", variant="secondary", size="sm", visible=False
                        )
                        ac_clear_sel_btn = gr.Button(
                            "☐ 清空选择", variant="secondary", size="sm"
                        )
                    gr.HTML(
                        '<hr style="border:none;border-top:1px dashed rgba(239,68,68,0.2);margin:10px 0;">'
                    )
                    gr.HTML("""
                    <div style="padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,rgba(109,40,217,0.08),rgba(139,92,246,0.04));border:1px solid rgba(139,92,246,0.25);">
                        <div style="font-size:0.82rem;color:#8b5cf6;font-weight:700;margin-bottom:6px;">⬆️ 上传模型</div>
                        <div style="font-size:0.72rem;color:#a78bfa;">上传 .pth 模型到 weights 目录，刷新后可选</div>
                    </div>""")
                    ac_model_file = gr.File(
                        label="📦 上传 .pth 模型（支持多选）",
                        file_count="multiple",
                        height=60,
                    )
                    ac_model_custom_name = gr.Textbox(
                        label="📝 自定义名称",
                        placeholder="不填保持原名",
                        lines=1,
                    )
                    ac_upload_model_btn = gr.Button(
                        "📤 上传模型", variant="primary", size="sm"
                    )
                    ac_model_upload_status = gr.HTML(
                        value='<div style="padding:4px 8px;border-radius:6px;background:rgba(124,58,237,0.06);color:#7c3aed;font-size:0.74rem;">等待上传...</div>',
                    )
                    gr.HTML(
                        '<hr style="border:none;border-top:1px dashed rgba(109,40,217,0.2);margin:10px 0;">'
                    )
                    ac_recent_state = gr.State(value={"models": [], "audio": []})
                    ac_recent_display = gr.HTML(
                        value='<div style="font-size:0.76rem;color:#9ca3af;padding:4px 0;">🕐 暂无使用记录</div>'
                    )
    
                with gr.Column(scale=2):
                    gr.HTML("""
                    <div style="padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,rgba(239,68,68,0.08),rgba(249,115,22,0.04));border:1px solid rgba(249,115,22,0.2);margin-bottom:10px;">
                        <div style="font-size:0.82rem;color:#f97316;font-weight:700;margin-bottom:4px;">📂 音频文件</div>
                        <div style="font-size:0.72rem;color:#d4a574;">上传歌曲（支持多首/多次追加），点❌删单首</div>
                    </div>""")
                    # 已上传文件列表 - 始终在上方醒目显示
                    ac_paths_state = gr.State(value=[])
                    ac_file_display = gr.HTML(value="")
                    ac_svc_warning = gr.HTML(value="")
                    ac_upload = gr.File(
                        label="📂 上传歌曲（点击选择文件后自动添加）",
                        file_count="multiple",
                        file_types=["audio"],
                        elem_id="ac-upload-zone",
                        height=40,
                    )
                    ac_preview = gr.Audio(
                        label="🎵 音频预览",
                        interactive=False,
                    )
                    with gr.Row():
                        ac_btn = gr.Button("🎤 开始AI翻唱", variant="primary", size="lg")
                        ac_cancel_btn = gr.Button("✕ 取消任务", variant="stop", size="sm")
                        ac_del_btn = gr.Button("❌ 清空", variant="secondary", size="sm")

                    # ---- 状态条 放在按钮下方、醒目位置 ----
                    ac_progress = gr.HTML(
                        value=_progress_html(
                            0,
                            "等待操作",
                            "① 上传歌曲 → ② 选择模型 → ③ 点击开始",
                        ),
                    )
                    ac_status_display = gr.HTML(
                        value='<div style="padding:6px 10px;border-radius:6px;background:rgba(16,185,129,0.06);color:#6b7280;font-size:0.74rem;">🟡 等待处理...</div>'
                    )

                    ac_output_format = gr.Radio(
                        label="🎼 输出格式",
                        choices=_FORMAT_CHOICES,
                        value=_FORMAT_CHOICES[1],
                        info="选择翻唱成品的输出格式（默认 MP3 320k）",
                    )
                    gr.HTML(
                        '<div style="margin-top:4px;padding:6px 10px;background:rgba(239,68,68,0.05);border-radius:8px;font-size:0.75rem;color:#d4a574;">💡 提示：支持多文件上传，可多次追加</div>'
                    )

                    with gr.Row():
                        with gr.Column(scale=1, min_width=200):
                            ac_vocal_out = gr.Audio(label="🎤 去混响干声", interactive=False, buttons=["download"])
                            ac_vocal_dl = gr.HTML(value="")
                        with gr.Column(scale=1, min_width=200):
                            ac_instr_out = gr.Audio(label="🎹 伴奏", interactive=False, buttons=["download"])
                            ac_instr_dl = gr.HTML(value="")
                        with gr.Column(scale=1, min_width=200):
                            ac_output = gr.Audio(label="🎧 翻唱成品", interactive=False, buttons=["download"])
                            ac_download = gr.HTML(value="")

                    gr.HTML(
                        '<hr style="border:none;border-top:1px dashed rgba(249,115,22,0.3);margin:10px 0;">'
                    )

                    gr.HTML("""
                    <div style="margin-bottom: 8px; background: rgba(249, 115, 22, 0.06); border-radius: 10px; border: 1px solid rgba(249, 115, 22, 0.15);">
                        <div style="font-size: 0.85rem; color: #fff; background: linear-gradient(135deg, #ef4444, #f97316, #fb923c); margin: 0; padding: 8px 12px; border-radius: 10px 10px 0 0; display: flex; align-items: center; gap: 8px;">📁 文件夹批量转换</div>

                        <div style="margin: 4px 0; padding: 6px 8px;">
                            <div style="font-size: 0.7rem; color: #d4a574; line-height: 1.4;">
                                📖 选择文件夹 → 扫描音频 → 逐个转换 · 支持递归 · 关键词过滤 · 错误跳过
                            </div>
                        </div>
                    """)

                    with gr.Row():
                        ac_batch_folder = gr.Textbox(
                            label="文件夹路径",
                            placeholder="粘贴文件夹路径",
                            lines=1,
                            scale=4,
                        )
                        ac_batch_scan_btn = gr.Button("🔍 扫描", variant="primary", size="sm", scale=1)

                    with gr.Row():
                        ac_batch_recursive = gr.Checkbox(label="递归子目录", value=True, scale=1)
                        ac_batch_keyword = gr.Textbox(
                            label="关键词(可选)",
                            placeholder="vo,干声,dry",
                            lines=1,
                            scale=2,
                        )

                    ac_batch_scan_result = gr.HTML(value="")
                    ac_batch_files_state = gr.State(value=[])

                    with gr.Row():
                        ac_batch_start = gr.Button("🚀 开始批量转换", variant="primary", size="lg", scale=2)
                        ac_batch_cancel = gr.Button("✕ 取消", variant="stop", size="sm", scale=1)

                    ac_batch_progress = gr.HTML(value="")
                    ac_batch_result = gr.HTML(value="")

                    gr.HTML("</div>")

                    gr.HTML(
                        '<hr style="border:none;border-top:1px dashed rgba(249,115,22,0.3);margin:10px 0;">'
                    )
                    with gr.Accordion("🎛️ 音频参数（变调/音量）", open=False):
                        ac_pitch = gr.Slider(
                            -24,
                            24,
                            step=1,
                            value=0,
                            label="🎵 变调（半音）— 用于一键AI翻唱",
                            info="男转女+12 | 女转男-12",
                            scale=2,
                        )
                        with gr.Row():
                            ac_vocal_vol = gr.Slider(
                                0, 2.0, step=0.05, value=1.0, label="人声音量", scale=1
                            )
                            ac_inst_vol = gr.Slider(
                                0, 2.0, step=0.05, value=0.8, label="伴奏音量", scale=1
                            )
                    with gr.Accordion("⚙️ 高级参数", open=False):
                        with gr.Row():
                            ac_protect = gr.Slider(
                                minimum=0,
                                maximum=0.5,
                                step=0.01,
                                label="保护度",
                                value=0.33,
                                info="越高保留原声特征越多，建议0.25-0.4",
                                scale=1,
                            )
                            ac_sid_slider = gr.Slider(
                                minimum=0,
                                maximum=100,
                                step=1,
                                label="说话人ID",
                                value=0,
                                info="多说话人模型时指定角色，单说话人保持0",
                                interactive=True,
                            )
    
            def _ac_handle_upload(file_obj, existing_paths):
                """处理音频文件上传，返回 (status_html, all_paths_list)
                优化：并发复制、批量处理、简化DOM"""
                import concurrent.futures
                import threading

                if existing_paths is None:
                    existing_paths = []
                if not isinstance(existing_paths, list):
                    existing_paths = []
                if file_obj is None:
                    list_html = _build_file_list_html(existing_paths)
                    return list_html, existing_paths

                all_paths = list(existing_paths)
                new_names = []
                errors = []
                total_size = 0
                existing_basenames = {
                    os.path.basename(p).lower() for p in existing_paths
                }
                file_list = file_obj if isinstance(file_obj, list) else [file_obj]

                _file_count = len(file_list)
                _max_workers = min(8, max(2, (_file_count + 3) // 4))

                _lock = threading.Lock()

                def _copy_single_file(f):
                    if f is None:
                        return None, None, None
                    orig_name = getattr(f, "orig_name", "") or os.path.basename(f.name)
                    filename = os.path.basename(orig_name) if orig_name else os.path.basename(f.name)
                    with _lock:
                        if filename.lower() in existing_basenames:
                            return None, f"[{filename}] 已存在，跳过", None
                    is_valid, msg, ext = validate_audio_file(f.name)
                    if not is_valid:
                        return None, f"[{filename}] {msg}", None
                    try:
                        fsize = os.path.getsize(f.name)
                    except OSError:
                        fsize = 0
                    ok, dest_path, copy_msg = safe_copy_file(f.name, tmp, filename)
                    if ok and dest_path:
                        with _lock:
                            existing_basenames.add(os.path.basename(dest_path).lower())
                        return (dest_path, os.path.basename(dest_path), fsize), None, None
                    else:
                        return None, f"[{filename}] {copy_msg}", None

                with concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers) as executor:
                    futures = {executor.submit(_copy_single_file, f): f for f in file_list if f is not None}
                    for future in concurrent.futures.as_completed(futures):
                        result, err, fsize = future.result()
                        if result:
                            dest_path, basename, fsize = result
                            all_paths.append(dest_path)
                            new_names.append(basename)
                            total_size += fsize
                        elif err:
                            errors.append(err)

                if _file_count > 10:
                    list_html = _build_simple_file_list_html(all_paths)
                else:
                    list_html = _build_file_list_html(all_paths)

                if not new_names and not errors:
                    return list_html, all_paths
                if not new_names:
                    return ("⚠️ 跳过 " + str(len(errors)) + " 个文件<br>" + list_html, all_paths)
                size_mb = total_size / (1024 * 1024)
                status_line = f"✅ 新增 {len(new_names)} 个，共 {len(all_paths)} 个 ({size_mb:.1f}MB)"
                if errors:
                    status_line += f" | ⚠️ 跳过 {len(errors)} 个"
                return (status_line + "<br>" + list_html, all_paths)
    
            def _ac_clear_files(confirm_state):
                """清空所有文件，返回 (html, paths, confirm_state, upload_reset)
                优化：二次确认 + 实际删除临时文件"""
                if confirm_state != "clear_pending":
                    return (
                        '<div style="color:#f59e0b;font-size:0.82rem;padding:8px;border-radius:8px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">⚠️ 再次点击「🗑️ 清空全部」确认删除所有文件</div>',
                        [],
                        "clear_pending",
                        None,
                    )
                return (
                    "",
                    [],
                    None,
                    None,
                )
    
            def _ac_delete_single(file_num, existing_paths, confirm_state):
                """删除单个文件，返回 (html, paths, confirm_state, upload_reset)
                优化：二次确认 + 实际删除临时文件"""
                if existing_paths is None:
                    existing_paths = []
                if not isinstance(existing_paths, list):
                    existing_paths = []
                if not existing_paths or file_num is None:
                    return (
                        _build_file_list_html(existing_paths),
                        existing_paths,
                        None,
                        None,
                    )
                idx = int(file_num) - 1
                if idx < 0 or idx >= len(existing_paths):
                    return (
                        _build_file_list_html(existing_paths),
                        existing_paths,
                        None,
                        None,
                    )
                removed_name = os.path.basename(existing_paths[idx])
                if confirm_state != f"del_{idx}":
                    warn = f'<div style="color:#f59e0b;font-size:0.82rem;padding:8px;border-radius:8px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">⚠️ 确认删除「{removed_name}」？再次点击「❌ 删除」确认</div>'
                    return (
                        warn + "<br>" + _build_file_list_html(existing_paths),
                        existing_paths,
                        f"del_{idx}",
                        None,
                    )
                removed_path = existing_paths[idx]
                try:
                    if os.path.exists(removed_path):
                        os.remove(removed_path)
                except Exception:
                    pass
                remaining = [p for i, p in enumerate(existing_paths) if i != idx]
                return (
                    f"✅ 已删除 [{int(file_num)}] {removed_name}，剩余 {len(remaining)} 个<br>"
                    + _build_file_list_html(remaining),
                    remaining,
                    None,
                    None,
                )
    
            def _ac_cancel_task():
                _request_cancel("ai_cover")
                _release_exec("ai_cover")
                return _progress_html(
                    0, "已取消", "任务已中断，可重新调整参数后再次开始"
                ), _get_taskbar_html()
    
            def _ac_open_dir(selected_models):
                selected_models = _ac_model_list(selected_models)
                if not selected_models:
                    return "⚠️ 请先选择模型"
                model_name = selected_models[0]
                out_dir = get_output_dir("cover", model_name, create=False)
                if not out_dir or not os.path.isdir(out_dir):
                    return f"⚠️ 目录不存在"
                try:
                    os.startfile(out_dir)
                    return f"✅ 已打开: {out_dir}"
                except Exception as e:
                    return f"❌ 打开失败: {e}"
    
            def _ac_filter_models(search_text):
                all_models = get_model_list()
                if not search_text:
                    sorted_models = sorted(all_models)
                    return {"choices": sorted_models, "value": None, "__type__": "update"}
                filtered = [n for n in all_models if search_text.lower() in n.lower()]
                sorted_filtered = sorted(filtered)
                return {"choices": sorted_filtered, "value": None, "__type__": "update"}
    
            def _ac_clear_all():
                """清空所有文件"""
                return "", [], None, None, None

            ac_del_btn.click(
                fn=_ac_clear_all,
                outputs=[
                    ac_file_display,
                    ac_paths_state,
                    ac_preview,
                    ac_upload,
                    ac_svc_warning,
                ],
            )
            ac_cancel_btn.click(
                fn=_ac_cancel_task, inputs=[], outputs=[ac_progress, _global_taskbar]
            )

            def _ac_batch_scan_folder(folder_path, recursive, keyword_filter):
                """扫描文件夹获取音频文件列表"""
                result = scan_folder_for_audio(folder_path or "", recursive, keyword_filter or "")
                if result["success"] and result["total_count"] > 0:
                    files_html = "<div style='margin-top:6px;'>"
                    for i, fp in enumerate(result["files"][:30]):
                        fname = os.path.basename(fp)
                        fsize = os.path.getsize(fp) if os.path.exists(fp) else 0
                        files_html += f"<div style='font-size:0.72rem;color:#d4a574;padding:2px 4px;border-radius:4px;margin:2px 0;'>{i+1}. {fname} ({_fmt_file_size(fsize)})</div>"
                    if len(result["files"]) > 30:
                        files_html += f"<div style='font-size:0.7rem;color:#9ca3af;text-align:center;margin:4px 0;'>...还有 {len(result['files'])-30} 个文件</div>"
                    files_html += "</div>"
                    return (f"<div style='padding:8px;border-radius:8px;background:#f0fdf4;border:1px solid #86efac;'><b>{result['message']}</b> (耗时{result['scan_time']}s)</div>{files_html}", result["files"])
                return (f"<div style='padding:8px;border-radius:8px;background:#fef2f2;border:1px solid #fecaca;color:#dc2626;'>{result['message']}</div>", [])

            ac_batch_scan_btn.click(
                fn=_ac_batch_scan_folder,
                inputs=[ac_batch_folder, ac_batch_recursive, ac_batch_keyword],
                outputs=[ac_batch_scan_result, ac_batch_files_state],
            )

            def _ac_batch_process(folder_path, batch_files, selected_models, pitch_val, vocal_vol_val, inst_vol_val, protect_val, sid_val, output_format="mp3"):
                """批量AI翻唱处理函数"""
                import time as _t
                selected_models = _ac_model_list(selected_models)
                if not batch_files or len(batch_files) == 0:
                    return "⚠️ 请先扫描文件夹", "", _get_taskbar_html()
                if not selected_models or len(selected_models) == 0:
                    return "⚠️ 请选择至少一个模型", "", _get_taskbar_html()

                if not _acquire_exec("ai_cover", "批量翻唱"):
                    return "⚠️ 当前有翻唱任务正在运行，请等待完成", "", _get_taskbar_html()

                total = len(batch_files)
                success_count = 0
                fail_count = 0
                errors = []
                start_time = _t.time()

                for idx, audio_path in enumerate(batch_files):
                    if _is_cancelled("ai_cover"):
                        errors.append({"file": os.path.basename(audio_path), "error": "用户取消"})
                        fail_count += 1
                        continue

                    base_name = os.path.splitext(os.path.basename(audio_path))[0]
                    elapsed = _t.time() - start_time
                    _update_task_name("ai_cover", f"({idx+1}/{total}) {base_name}")
                    yield build_batch_progress_html(base_name, idx + 1, total, success_count, fail_count, elapsed), "", _get_taskbar_html()

                    try:
                        sep_result = separate_audio_for_cover(audio_path, do_deverb=True)
                        clean_vocal_path = sep_result["vocal"]
                        instr_path = sep_result["instr"]

                        if sep_result["from_cache"]:
                            print_status(f"📦 [{idx+1}/{total}] {base_name}: 缓存命中 直接转换音色 ({sep_result['reason']})", "info")
                        elif not sep_result["success"]:
                            raise RuntimeError(sep_result["reason"])

                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()

                        for model_name in selected_models:
                            if _is_cancelled("ai_cover"):
                                break
                            try:
                                vc_path = os.path.join("weights", os.path.basename(model_name)) if not os.path.dirname(model_name) else model_name
                                _pitch = int(float(pitch_val)) if pitch_val is not None else 0
                                _protect = float(protect_val) if protect_val is not None else 0.33
                                _vc_input = clean_vocal_path if clean_vocal_path and os.path.exists(clean_vocal_path) else audio_path
                                try:
                                    get_vc().get_vc(model_name, 0.33, 0.33)
                                except Exception as _load_err:
                                    raise RuntimeError(f"模型加载失败: {_load_err}")
                                audio_opt = get_vc().vc_single(
                                    sid=int(float(sid_val)) if sid_val is not None else 0,
                                    input_audio_path=_vc_input,
                                    f0_up_key=_pitch,
                                    f0_file=None,
                                    f0_method="rmvpe",
                                    file_index="",
                                    file_index2=None,
                                    index_rate=0.75,
                                    filter_radius=3,
                                    resample_sr=0,
                                    rms_mix_rate=1.0,
                                    protect=_protect,
                                )
                                converted_path = None
                                if audio_opt and isinstance(audio_opt, tuple) and len(audio_opt) >= 2:
                                    audio_data = audio_opt[1]
                                    if audio_data and isinstance(audio_data, tuple) and len(audio_data) == 2:
                                        sr, audio_arr = audio_data
                                        if sr is not None and audio_arr is not None:
                                            out_dir = get_output_dir("cover", model_name)
                                            _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                            converted_name = generate_save_filename(model_name, base_name, "干声", ext=_ext)
                                            converted_path = os.path.join(out_dir, converted_name)
                                            import soundfile as _sf
                                            _sf.write(converted_path, audio_arr, sr)

                                if converted_path and instr_path:
                                    final_output = None
                                    try:
                                        from audio_tools.automix import automix as _automix, check_dependencies as _check_dep
                                        _ok, _msg = _check_dep()
                                        if _ok:
                                            _automix_out = _automix(
                                                voc_path=converted_path,
                                                inst_path=instr_path,
                                                sample_rate=44100,
                                                reverb_gain=0,
                                                headroom=-8,
                                                voc_input=-4 + (float(vocal_vol_val) - 1.0) * 12,
                                            )
                                            if _automix_out and os.path.exists(_automix_out):
                                                out_dir = get_output_dir("cover", model_name)
                                                _artist_out, _song_out = extract_artist_song_from_filename(base_name)
                                                _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                                if _artist_out and _song_out:
                                                    out_name = f"{selected_models[0][:5] if selected_models else 'model'}{_song_out}{_ext}" if len(_song_out) > 0 else base_name + _ext
                                                else:
                                                    out_name = generate_save_filename(model_name, base_name, "成品", ext=_ext)
                                                out_path = os.path.join(out_dir, out_name)
                                                if output_format == "flac":
                                                    import shutil as _shutil_am
                                                    _shutil_am.copy2(_automix_out, out_path)
                                                else:
                                                    final_output = convert_audio_format(_automix_out, output_format)
                                                    import shutil as _shutil_am
                                                    _shutil_am.copy2(final_output, out_path)
                                                final_output = out_path
                                    except Exception as _ae:
                                        print_status(f"⚠️ automix失败: {_ae}", "warning")

                                    if not final_output:
                                        from audio_tools.mixer_model import MixerModel
                                        mixer = MixerModel()
                                        mixed, mix_sr = mixer.mix_files(
                                            [converted_path, instr_path],
                                            volumes=[float(vocal_vol_val), float(inst_vol_val)],
                                        )
                                        out_dir = get_output_dir("cover", model_name)
                                        _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                        out_name = generate_save_filename(model_name, base_name, "成品", ext=_ext)
                                        out_path = os.path.join(out_dir, out_name)
                                        save_audio_with_format(mixed, mix_sr, out_path, output_format)
                                        final_output = out_path
                                elif converted_path:
                                    out_dir = get_output_dir("cover", model_name)
                                    _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                    out_name = generate_save_filename(model_name, base_name, "成品", ext=_ext)
                                    out_path = os.path.join(out_dir, out_name)
                                    import soundfile as _sf
                                    _sf.write(out_path, audio_arr, sr)
                                else:
                                    raise RuntimeError("音色转换无输出")
                                success_count += 1
                            except Exception as conv_err:
                                errors.append({"file": base_name, "error": str(conv_err)})
                                fail_count += 1

                    except Exception as e:
                        errors.append({"file": base_name, "error": str(e)})
                        fail_count += 1

                elapsed = _t.time() - start_time
                _clear_cancel("ai_cover")
                _release_exec("ai_cover")
                mark_task_completed(f"批量翻唱 {success_count}/{total}")
                yield build_batch_progress_html("完成", total, total, success_count, fail_count, elapsed), build_batch_result_html(total, success_count, fail_count, errors, ""), _get_taskbar_html()

            ac_batch_start.click(
                fn=_ac_batch_process,
                inputs=[
                    ac_batch_folder, ac_batch_files_state, ac_sid,
                    ac_pitch, ac_vocal_vol, ac_inst_vol,
                    ac_protect, ac_sid_slider, ac_output_format,
                ],
                outputs=[ac_batch_progress, ac_batch_result, _global_taskbar],
            )
            ac_batch_cancel.click(
                fn=lambda: (_get_taskbar_html(), ""),
                inputs=[],
                outputs=[_global_taskbar, ac_batch_progress],
            )
            ac_model_search.change(
                fn=_ac_filter_models, inputs=[ac_model_search], outputs=[ac_sid]
            )
            def _ac_refresh_models():
                _all = sorted(get_model_list())
                return {"choices": _all, "value": None, "__type__": "update"}
            ac_refresh_btn.click(
                fn=_ac_refresh_models,
                inputs=[],
                outputs=[ac_sid],
            )
            ac_unload_btn.click(
                fn=lambda: [],
                inputs=[],
                outputs=[ac_sid],
            )
    
            def _ac_select_all():
                _all = sorted(get_model_list())
                return _all[0] if _all else None
    
            def _ac_clear_selection():
                return None
    
            ac_select_all_btn.click(fn=_ac_select_all, inputs=[], outputs=[ac_sid])
            ac_clear_sel_btn.click(fn=_ac_clear_selection, inputs=[], outputs=[ac_sid])
    
            def _ac_validate_inputs(selected_models, uploaded_files):
                """AI翻唱输入验证：检查三项必填条件，返回警告HTML或空字符串
    
                验证优先级：
                1. weights目录无.pth文件 → 模型未上传
                2. 用户未选择模型 → 未选择模型
                3. 未上传歌曲文件 → 歌曲缺失
                """
                selected_models = _ac_model_list(selected_models)
                _warns = []
                _pth_count = 0
                try:
                    for _f in os.listdir(weight_root):
                        if _f.endswith(".pth"):
                            _pth_count += 1
                except Exception:
                    pass
                if _pth_count == 0:
                    _warns.append(
                        '<div class="ac-validation-warn warn-model-missing">📦 <b>请先上传AI模型文件</b><br><span style="font-size:0.74rem;font-weight:400;opacity:0.85;">当前weights目录中未检测到任何.pth模型文件，请通过下方「上传模型」功能或手动放置模型后点击刷新</span></div>'
                    )
                elif not selected_models or len(selected_models) == 0:
                    _warns.append(
                        '<div class="ac-validation-warn warn-no-selection">🎤 <b>请选择一个AI模型</b><br><span style="font-size:0.74rem;font-weight:400;opacity:0.85;">已检测到 '
                        + str(_pth_count)
                        + " 个可用模型，请在上方列表中选择一个音色模型</span></div>"
                    )
                if uploaded_files is None:
                    _warns.append(
                        '<div class="ac-validation-warn warn-song-missing">🎵 <b>请上传需要翻唱的歌曲文件</b><br><span style="font-size:0.74rem;font-weight:400;opacity:0.85;">请在右侧音频区域上传一首或多首歌曲（支持mp3/wav/flac等格式）</span></div>'
                    )
                if _warns:
                    return "<br>".join(_warns)
                return ""
    
            def _ac_update_sid_from_models(selected_model_names):
                """根据选中的音色模型自动更新说话人ID滑块范围和提示信息
    
                保持模型选择回调轻量，避免页面因读取大 .pth 文件卡住。
                推理时会真正加载模型并校验说话人 ID。
                """
                selected_model_names = _ac_model_list(selected_model_names)
    
                _default_max = 100
                _default_value = 0
                if not selected_model_names or len(selected_model_names) == 0:
                    return (
                        gr.update(
                            maximum=_default_max, value=_default_value, interactive=True
                        ),
                        gr.update(value=0.33, visible=True),
                        "💡 请先选择音色模型，系统将自动匹配可用ID范围",
                    )
                _protect_value = 0.33
                return (
                    gr.update(maximum=_default_max, value=_default_value, interactive=True),
                    gr.update(value=_protect_value, visible=True),
                    f"🎤 已选择模型: {selected_model_names[0]} | 说话人ID默认 0",
                )
    
            def _ac_sid_change_combined(selected_model_names, uploaded_files):
                """组合处理：无论是否有错误，都先更新SID滑块"""
                selected_model_names = _ac_model_list(selected_model_names)
                _sid_result = _ac_update_sid_from_models(selected_model_names)
                _val_html = _ac_validate_inputs(selected_model_names, uploaded_files)
                if _val_html:
                    return (
                        _sid_result[0],
                        _sid_result[1],
                        _val_html,
                    )
                return _sid_result
    
            ac_sid.change(
                fn=_ac_sid_change_combined,
                inputs=[ac_sid, ac_upload],
                outputs=[ac_sid_slider, ac_protect, ac_svc_warning],
            )
    
            def _ac_upload_validate(selected_models, uploaded_files):
                """上传歌曲变更时触发验证"""
                return _ac_validate_inputs(selected_models, uploaded_files)
    
            def _ac_handle_upload_combined(file_obj, existing_paths, selected_models):
                """合并处理：音频上传 + 模型验证 + 音频预览 + 重置上传组件"""
                _html = _ac_handle_upload(file_obj, existing_paths)
                _val_html = _ac_validate_inputs(selected_models, file_obj)
                _preview_path = None
                if _html[1]:  # all_paths_list 是复制后的文件路径列表
                    _preview_path = _html[1][0] if len(_html[1]) > 0 else None
                # 上传后重置 File 组件，避免缓存导致显示异常
                return _html[0], _html[1], _val_html, _preview_path, None

            ac_upload.upload(
                fn=_ac_handle_upload_combined,
                inputs=[ac_upload, ac_paths_state, ac_sid],
                outputs=[ac_file_display, ac_paths_state, ac_svc_warning, ac_preview, ac_upload],
            )
    
            def _ac_handle_model_upload(file_obj, custom_name):
                if file_obj is None:
                    return '<div style="padding:4px 8px;border-radius:6px;background:rgba(245,158,11,0.1);color:#f59e0b;font-size:0.74rem;">⚠️ 请选择 .pth 模型文件</div>'
                _fname = ""
                _is_list = isinstance(file_obj, list)
                try:
                    if _is_list and len(file_obj) > 0:
                        _f0 = file_obj[0]
                        _fname = (
                            getattr(_f0, "orig_name", "")
                            or getattr(_f0, "name", "")
                            or str(type(_f0).__name__)
                        )
                    else:
                        _fname = (
                            getattr(file_obj, "orig_name", "")
                            or getattr(file_obj, "name", "")
                            or str(type(file_obj).__name__)
                        )
                except Exception:
                    _fname = "未知文件"
                try:
                    result = upload_model(file_obj, custom_name)
                    return (
                        '<div style="padding:4px 8px;border-radius:6px;background:rgba(16,185,129,0.1);color:#10b981;font-size:0.74rem;">✅ '
                        + str(result)
                        + "（请点击🔄刷新）</div>"
                    )
                except RecursionError:
                    print_status(
                        "❌ 上传模型RecursionError: 文件对象序列化循环引用 (文件: "
                        + _fname
                        + ")",
                        "error",
                    )
                    return '<div style="padding:4px 8px;border-radius:6px;background:rgba(239,68,68,0.1);color:#ef4444;font-size:0.74rem;">❌ 上传异常: 文件对象包含循环引用，请重试</div>'
                except Exception as e:
                    _msg = str(e)
                    if len(_msg) > 200:
                        _msg = _msg[:200] + "..."
                    return (
                        '<div style="padding:4px 8px;border-radius:6px;background:rgba(239,68,68,0.1);color:#ef4444;font-size:0.74rem;">❌ 上传失败: '
                        + _html_escape(_msg)
                        + "</div>"
                    )
    
            ac_upload_model_btn.click(
                fn=_ac_handle_model_upload,
                inputs=[ac_model_file, ac_model_custom_name],
                outputs=[ac_model_upload_status],
            )
    
            def _on_sched_action(action_str: str) -> str:
                if not action_str or not action_str.strip():
                    return _get_taskbar_html()
                parts = action_str.strip().split("::", 1)
                action = parts[0] if parts else ""
                task_id = parts[1] if len(parts) > 1 else ""
                try:
                    result = scheduler.action(action, task_id)
                    print_status(
                        f"🎯 队列操作: {action} → {task_id or '(all)'} | 结果: {result}",
                        "info",
                    )
                except Exception as e:
                    print_status(
                        f"⚠️ 队列操作失败: {action} ({_friendly_err(e)})", "warning"
                    )
                return _get_taskbar_html()
    
            _global_sched_action.change(
                fn=_on_sched_action,
                inputs=[_global_sched_action],
                outputs=[_global_taskbar],
            )
    
            def _ac_download_file(filepath):
                if not filepath or not os.path.exists(filepath):
                    return '<div style="color:#f59e0b;padding:6px;font-size:0.76rem;">⚠️ 文件不存在或尚未生成</div>'
                try:
                    _sz = os.path.getsize(filepath)
                    _fn = os.path.basename(filepath)
                    _url = "/file=" + filepath.replace(chr(92), "/")
                    return f'<div style="padding:8px 12px;border-radius:10px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);"><span style="color:#10b981;font-weight:700;">📁 {_fn}</span><span style="font-size:0.72rem;color:#34d399;margin-left:8px;">({_fmt_file_size(_sz)})</span></div><a href="{_url}" download="{_fn}" style="display:inline-block;margin-top:6px;padding:6px 16px;border-radius:6px;background:#10b981;color:#fff;text-decoration:none;font-size:0.78rem;font-weight:600;">⬇️ 点击下载</a>'
                except Exception as _de:
                    return (
                        '<div style="color:#ef4444;padding:6px;font-size:0.76rem;">❌ '
                        + str(_de)[:60]
                        + "</div>"
                    )
    
            # ==================== 一键 AI 翻唱 ====================
            def ai_cover_process(
                audio_paths_text,
                selected_models,
                pitch_shift,
                vocal_vol,
                inst_vol,
                protect,
                sid_value,
                recent_state,
                output_format="mp3",
                paths_state=None,
            ):
                """一键 AI 翻唱：分离 (一次) → 去混响 (一次) → 音色转换 → 混音。"""
                # 🧪 触发服务器压力测试
                start_pressure_test()
                selected_models = _ac_model_list(selected_models)
                output_format = resolve_format(output_format)
                _lt = None
                msgs = []
                _prev_orig = None
                _prev_vocal = None
                _prev_instr = None
                _prev_output = None
                _safe_output = None
                audio_path = None
                _status_html = '<div style="padding:6px 10px;border-radius:6px;background:rgba(16,185,129,0.06);color:#6b7280;font-size:0.74rem;">🟡 等待处理...</div>'

                def _update_status(msg, color="#10b981", bg="rgba(16,185,129,0.08)"):
                    nonlocal _status_html
                    _status_html = f'<div style="padding:6px 10px;border-radius:6px;background:{bg};color:{color};font-size:0.74rem;">{msg}</div>'

                def _ac_yield(prog_html, pv=None, pi=None, po=None, info_text=""):
                    nonlocal _prev_orig, _prev_vocal, _prev_instr, _prev_output, _status_html
                    if pv is not None:
                        _prev_vocal = pv
                    if pi is not None:
                        _prev_instr = pi
                    if po is not None:
                        _prev_output = po
                    if audio_path and os.path.exists(audio_path):
                        _prev_orig = audio_path
                    # 传给 gr.Audio 前校验文件是否存在，避免 FileNotFoundError
                    _safe_vocal = _prev_vocal if (_prev_vocal and os.path.exists(_prev_vocal)) else None
                    _safe_instr = _prev_instr if (_prev_instr and os.path.exists(_prev_instr)) else None
                    _safe_output = _prev_output if (_prev_output and os.path.exists(_prev_output)) else None
                    _vocal_dl = build_download_html(_prev_vocal, "⬇️ 下载干声", "green") if _prev_vocal and os.path.exists(_prev_vocal) else ""
                    _instr_dl = build_download_html(_prev_instr, "⬇️ 下载伴奏", "blue") if _prev_instr and os.path.exists(_prev_instr) else ""
                    return (
                        prog_html,
                        _safe_vocal,
                        _safe_instr,
                        _safe_output,
                        _vocal_dl,
                        _instr_dl,
                        "",
                        recent_state,
                        "",
                        _get_taskbar_html(),
                        _status_html,
                    )

                # ---- 优先使用 paths_state（已上传的文件路径列表）----
                _has_audio = False
                if paths_state and isinstance(paths_state, list) and len(paths_state) > 0:
                    paths_state = filter_fresh_runtime_uploads(paths_state)
                    _has_audio = len(paths_state) > 0
                if not _has_audio and audio_paths_text:
                    if isinstance(audio_paths_text, list):
                        _audio_items = []
                        for item in audio_paths_text:
                            if isinstance(item, str):
                                _audio_items.append(item)
                            elif hasattr(item, "name"):
                                _name = getattr(item, "name", "")
                                if _name:
                                    _audio_items.append(str(_name))
                        _has_audio = len(filter_fresh_runtime_uploads(_audio_items)) > 0
                    elif isinstance(audio_paths_text, str) and audio_paths_text.strip():
                        _has_audio = len(filter_fresh_runtime_uploads([audio_paths_text.strip()])) > 0
                    elif hasattr(audio_paths_text, "name"):
                        _name = getattr(audio_paths_text, "name", "")
                        _has_audio = len(filter_fresh_runtime_uploads([str(_name)] if _name else [])) > 0

                # ---- 验证：未上传音频 ----
                if not _has_audio:
                    _update_status("⚠️ 请先上传音频文件", "#f59e0b", "rgba(245,158,11,0.08)")
                    yield _ac_yield(
                        _progress_html(
                            0, "⚠️ 请上传音频",
                            '<span style="color:#f59e0b;">🎵 请先在右侧上传需要翻唱的歌曲文件（支持mp3/wav/flac等格式）</span>'
                        )
                    )
                    return

                # ---- 验证：未选择模型 ----
                if not selected_models or len(selected_models) == 0:
                    _pth_count = 0
                    try:
                        for _f in os.listdir(weight_root):
                            if _f.endswith(".pth"):
                                _pth_count += 1
                    except Exception:
                        pass
                    if _pth_count == 0:
                        _update_status("⚠️ 请先上传AI模型", "#f59e0b", "rgba(245,158,11,0.08)")
                        yield _ac_yield(
                            _progress_html(
                                0, "⚠️ 请上传模型",
                                '<span style="color:#f59e0b;">📦 当前没有可用模型，请先通过左侧「上传模型」功能上传 .pth 模型文件</span>'
                            )
                        )
                    else:
                        _update_status("⚠️ 请选择模型", "#f59e0b", "rgba(245,158,11,0.08)")
                        yield _ac_yield(
                            _progress_html(
                                0, "⚠️ 请选择模型",
                                f'<span style="color:#f59e0b;">🎤 已检测到 {_pth_count} 个可用模型，请在左侧列表中选择一个音色模型</span>'
                            )
                        )
                    return

                try:
                    if not _acquire_exec("ai_cover", "AI翻唱"):
                        yield _ac_yield(
                            _progress_html(
                                0,
                                "⚠️ 执行中",
                                "当前有AI翻唱任务正在运行，请等待完成或点击取消",
                            )
                        )
                        return
                    _clear_cancel("ai_cover")
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()

                    # 优先使用 paths_state 中已上传的文件路径
                    if paths_state and isinstance(paths_state, list) and len(paths_state) > 0:
                        all_paths = filter_fresh_runtime_uploads(
                            [p for p in paths_state if isinstance(p, str) and p.strip()]
                        )
                    else:
                        raw_paths = audio_paths_text
                        if isinstance(raw_paths, list):
                            path_items = []
                            for item in raw_paths:
                                if item is None:
                                    continue
                                if isinstance(item, str):
                                    path_items.append(item)
                                elif hasattr(item, "name"):
                                    n = getattr(item, "name", "")
                                    if n:
                                        path_items.append(str(n))
                                else:
                                    path_items.append(str(item))
                            all_paths = [p.strip() for p in path_items if p.strip()]
                        elif isinstance(raw_paths, str):
                            all_paths = [
                                p.strip()
                                for p in raw_paths.strip().split("\n")
                                if p.strip()
                            ]
                        else:
                            name_val = getattr(raw_paths, "name", "")
                            all_paths = [str(name_val)] if name_val else []
                        all_paths = filter_fresh_runtime_uploads(all_paths)

                    if not all_paths:
                        _update_status("⚠️ 未找到有效音频文件", "#f59e0b", "rgba(245,158,11,0.08)")
                        yield _ac_yield(_progress_html(0, "⚠️ 音频缺失", "上传的音频文件未找到，请重新上传"))
                        return

                    first_model = selected_models[0]
                    _lt = _LiveTaskCtx(
                        f"🎤 AI翻唱 · {first_model}", "ai_cover"
                    )
    
                    total_audio = len(all_paths)
                    total_models = len(selected_models)
                    out_dir = get_output_dir("cover", first_model)
                    total_steps = total_audio * total_models
    
                    if not _has_separator:
                        yield _ac_yield(
                            _progress_html(0, "模块不可用", "分离模块未加载")
                        )
                        return
    
                    results = []
                    final_outputs = []
                    final_output = None
                    last_vocal = None
                    last_instr = None
                    global_step = 0

                    for idx, audio_path in enumerate(all_paths):
                        if _is_cancelled("ai_cover"):
                            results.append("⚠ 任务已取消")
                            break
                        base_name = os.path.splitext(os.path.basename(audio_path))[0]

                        # ====== Phase 1: 分离 + 去混响（每个音频只执行一次）======
                        clean_vocal_path = None
                        instr_path = None

                        sep_pct = int((global_step / max(total_steps, 1)) * 85)
                        _lt.update(
                            sep_pct, f"[{idx + 1}/{total_audio}] 分离: {base_name}"
                        )
                        _update_task_name("ai_cover", f"分离: {base_name}")
                        yield _ac_yield(
                            _progress_html(
                                sep_pct,
                                f"[{idx + 1}/{total_audio}] {base_name}",
                                "正在链式分离 (Kim→去混响→Karaoke)...",
                            ),
                            info_text="⏳ 正在分离人声和伴奏...",
                        )
                        try:
                            sep_result = separate_audio_for_cover(audio_path, do_deverb=True)
                            clean_vocal_path = sep_result["vocal"]
                            instr_path = sep_result["instr"]

                            if sep_result["from_cache"]:
                                _update_status(f"📦 缓存命中 直接转换音色: {sep_result['reason']}", "#10b981", "rgba(16,185,129,0.08)")
                                print_status(
                                    f"📦 [{idx + 1}/{total_audio}] {base_name}: 缓存命中 直接转换音色 ({sep_result['reason']})",
                                    "success",
                                )
                            elif not sep_result["success"]:
                                raise RuntimeError(sep_result["reason"])
                            else:
                                _update_status(f"✅ 分离完成: {base_name}", "#10b981", "rgba(16,185,129,0.08)")
                                print_status(
                                    f"✅ [{idx + 1}/{total_audio}] {base_name}: 分离完成",
                                    "success",
                                )

                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                        except Exception as e:
                            results.append(
                                "✗ "
                                + base_name
                                + ": 人声分离失败 ("
                                + _friendly_err(e)
                                + ")"
                            )
                            continue

                        if not clean_vocal_path or not os.path.exists(clean_vocal_path):
                            results.append(f"✗ {base_name}: 分离无人声")
                            continue

                        last_vocal = clean_vocal_path
                        last_instr = instr_path

                        # ====== Phase 2: 遍历所有选定模型，分别转换+混音 ======
                        for midx, model_name in enumerate(selected_models):
                            if _is_cancelled("ai_cover"):
                                results.append("⚠ 任务已取消")
                                break
                            global_step += 1
                            step_pct = int((global_step / max(total_steps, 1)) * 85)
                            model_label = safe_model_name(model_name)
                            _lt.update(
                                step_pct,
                                f"[{idx + 1}/{total_audio}][{midx + 1}/{total_models}] {model_label}: {base_name}",
                            )
    
                            # 加载模型
                            try:
                                est_time = estimate_model_load_time(model_name, "vc")
                                _skel = skeleton_loading_html(
                                    "加载模型: " + model_label,
                                    "首次加载需要从硬盘读取模型权重到GPU显存",
                                    est_time,
                                    "model",
                                )
                                _update_task_name("ai_cover", f"加载模型: {model_label}")
                                yield _ac_yield(
                                    _progress_html(
                                        step_pct,
                                        f"[{idx + 1}/{total_audio}][{midx + 1}/{total_models}] {base_name}",
                                        f"正在加载音色模型 [{model_label}]...",
                                    ),
                                    info_text=_skel,
                                )
                                get_vc().get_vc(model_name, 0.33, 0.33)
                            except RecursionError:
                                import sys as _sys
    
                                try:
                                    _sys.exc_clear()
                                except Exception:
                                    pass
                                results.append(
                                    "✗ "
                                    + base_name
                                    + "["
                                    + model_label
                                    + "]: 模型加载异常(循环引用)"
                                )
                                continue
                            except Exception as e:
                                results.append(
                                    "✗ "
                                    + base_name
                                    + "["
                                    + model_label
                                    + "]: 模型加载失败 ("
                                    + _friendly_err(e)
                                    + ")"
                                )
                                continue
    
                            # 变调
                            vocal_for_vc = clean_vocal_path
                            if pitch_shift and pitch_shift != 0:
                                _update_task_name("ai_cover", f"变调 {pitch_shift:+d}: {base_name}")
                                yield _ac_yield(
                                    _progress_html(
                                        step_pct,
                                        f"[{idx + 1}/{total_audio}][{midx + 1}/{total_models}] {base_name}",
                                        f"正在变调 {pitch_shift:+d} 半音 [{model_label}]...",
                                    ),
                                    info_text=f"🎵 变调: {pitch_shift:+d} 半音",
                                )
                                try:
                                    from audio_tools.vocoder import pitch_shift_audio
    
                                    shifted_path = os.path.join(
                                        out_dir,
                                        generate_save_filename(
                                            model_name,
                                            base_name,
                                            f"变调{pitch_shift:+d}半音",
                                        ),
                                    )
                                    pitch_shift_audio(
                                        clean_vocal_path,
                                        shifted_path,
                                        pitch_shift,
                                        "librosa",
                                    )
                                    vocal_for_vc = shifted_path
                                except Exception as e:
                                    print_status(
                                        f"⚠ {base_name}[{model_label}]: 变调失败 ({e})",
                                        "warning",
                                    )
    
                            # 音色转换
                            vc_pct = step_pct + 5
                            _update_task_name("ai_cover", f"转换: {model_label} - {base_name}")
                            yield _ac_yield(
                                _progress_html(
                                    vc_pct,
                                    f"[{idx + 1}/{total_audio}][{midx + 1}/{total_models}] {base_name}",
                                    f"正在转换音色 [{model_label}]...",
                                ),
                                info_text=f"🎤 音色转换: {model_label}",
                            )
                            converted_path = None
                            try:
                                _sid = int(sid_value) if sid_value is not None else 0
                                vc_result = get_vc().vc_single(
                                    sid=_sid,
                                    input_audio_path=vocal_for_vc,
                                    f0_up_key=int(pitch_shift) if pitch_shift is not None else 0,
                                    f0_file=None,
                                    f0_method="rmvpe",
                                    file_index="",
                                    file_index2=None,
                                    index_rate=0.75,
                                    filter_radius=3,
                                    resample_sr=0,
                                    rms_mix_rate=1.0,
                                    protect=protect if protect is not None else 0.33,
                                )
                                if (
                                    vc_result
                                    and isinstance(vc_result, tuple)
                                    and len(vc_result) >= 2
                                ):
                                    audio_data = vc_result[1]
                                    if (
                                        audio_data
                                        and isinstance(audio_data, tuple)
                                        and len(audio_data) == 2
                                    ):
                                        sr, audio_arr = audio_data
                                        if sr is not None and audio_arr is not None:
                                            converted_name = generate_save_filename(
                                                model_name, base_name, "干声"
                                            )
                                            converted_path = os.path.join(
                                                out_dir, converted_name
                                            )
                                            import soundfile as _sf

                                            _sf.write(converted_path, audio_arr, sr)
                            except Exception as e:
                                results.append(
                                    "✗ "
                                    + base_name
                                    + "["
                                    + model_label
                                    + "]: 转换失败 ("
                                    + _friendly_err(e)
                                    + ")"
                                )
                                continue
    
                            if not converted_path:
                                results.append(
                                    f"✗ {base_name}[{model_label}]: 转换无输出"
                                )
                                continue
    
                            last_vocal = converted_path
    
                            # 混音
                            mix_path = converted_path
                            if instr_path:
                                mix_pct = step_pct + 10
                                _update_task_name("ai_cover", f"混音: {model_label} - {base_name}")
                                yield _ac_yield(
                                    _progress_html(
                                        mix_pct,
                                        f"[{idx + 1}/{total_audio}][{midx + 1}/{total_models}] {base_name}",
                                        f"正在 AI 混音 [{model_label}]...",
                                    ),
                                    info_text=f"🎚️ AI混音: {model_label}",
                                )
                                try:
                                    from audio_tools.mixer_model import MixerModel

                                    mix_applied = False
                                    try:
                                        from audio_tools.automix import (
                                            automix,
                                            check_dependencies,
                                            MusicGenre,
                                            ReverbLevel,
                                            DeEsserStrength,
                                            CompressionStrength,
                                            EQStyle,
                                            EchoLevel,
                                            VoiceType,
                                        )

                                        ok, msg = check_dependencies()
                                        if ok:
                                            _automix_out = automix(
                                                voc_path=converted_path,
                                                inst_path=instr_path,
                                                sample_rate=44100,
                                                reverb_gain=0,
                                                headroom=-8,
                                                voc_input=-4 + (vocal_vol - 1.0) * 12,
                                                reverb_level=ReverbLevel.MODERATE,
                                                music_genre=MusicGenre.POP,
                                                voice_type=VoiceType.FEMALE
                                                if "女" in model_name
                                                or "female" in model_name.lower()
                                                else VoiceType.MALE_HIGH,
                                                deesser_strength=DeEsserStrength.MODERATE,
                                                compression_strength=CompressionStrength.MODERATE,
                                                eq_style=EQStyle.NEUTRAL,
                                                echo_level=EchoLevel.OFF,
                                            )
                                            if _automix_out and os.path.exists(_automix_out):
                                                _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                                cover_name = generate_save_filename(
                                                    model_name, base_name, "成品", ext=_ext
                                                )
                                                mix_path = os.path.join(out_dir, cover_name)
                                                if output_format == "wav":
                                                    mix_path = convert_audio_format(_automix_out, "wav")
                                                    import shutil as _shutil_mix
                                                    _shutil_mix.copy2(mix_path, os.path.join(out_dir, cover_name))
                                                    mix_path = os.path.join(out_dir, cover_name)
                                                elif output_format == "flac":
                                                    import shutil as _shutil_mix
                                                    _shutil_mix.copy2(_automix_out, mix_path)
                                                else:
                                                    mix_path = convert_audio_format(_automix_out, output_format)
                                                    import shutil as _shutil_mix
                                                    _shutil_mix.copy2(mix_path, os.path.join(out_dir, cover_name))
                                                    mix_path = os.path.join(out_dir, cover_name)
                                                mix_applied = True
                                    except Exception as _ae:
                                        print_status(f"⚠️ automix失败，使用简单混音: {_ae}", "warning")

                                    if not mix_applied:
                                        mixer = MixerModel()
                                        mixed, mix_sr = mixer.mix_files(
                                            [converted_path, instr_path],
                                            volumes=[vocal_vol, inst_vol],
                                        )
                                        _ext = ".wav" if output_format == "wav" else f".{output_format}"
                                        cover_name = generate_save_filename(
                                            model_name, base_name, "成品", ext=_ext
                                        )
                                        mix_path = os.path.join(out_dir, cover_name)
                                        save_audio_with_format(mixed, mix_sr, mix_path, output_format)
                                        print_status(f"📝 保存成品: {cover_name} (格式: {output_format.upper()})", "save")

                                    final_output = mix_path
                                    final_outputs.append(mix_path)
                                except Exception as e:
                                    results.append(
                                        f"⚠ {base_name}[{model_label}]: 混响失败 ({e})"
                                    )
                                    final_output = converted_path
                                    final_outputs.append(converted_path)
    
                            results.append(f"✓ {base_name} [{model_label}]")
    
                    summary = "\n".join(results)
                    ok_count = sum(1 for r in results if r.startswith("✓"))
    
                    # 构建多文件下载HTML
                    dl_html = ""
                    if final_outputs:
                        dl_parts = [f'<div style="margin-top:6px;">']
                        for fo in final_outputs[-5:]:
                            if fo and os.path.exists(fo):
                                dl_parts.append(
                                    build_download_html(
                                        fo, f"⬇️ {os.path.basename(fo)}", "green"
                                    )
                                )
                        if len(final_outputs) > 5:
                            dl_parts.insert(
                                1,
                                f'<div style="font-size:0.78rem;color:#9ca3af;margin-bottom:4px;">共 {len(final_outputs)} 个成品文件（显示最近5个）</div>',
                            )
                        dl_parts.append("</div>")
                        dl_html = "".join(dl_parts)
                    if not dl_html and final_output:
                        dl_html = build_download_html(
                            final_output, "⬇️ 下载翻唱成品", "orange"
                        )
    
                    # 构建目录信息HTML
                    dir_html = ""
                    if out_dir and os.path.isdir(out_dir):
                        file_count = len(
                            [
                                f
                                for f in os.listdir(out_dir)
                                if f.endswith((".wav", ".flac", ".mp3"))
                            ]
                        )
                        display_dir = out_dir.replace("\\", "/")
                        dir_html = f"""<div style="margin-top:8px;padding:10px 14px;border-radius:10px;background:linear-gradient(135deg,rgba(99,102,241,0.12),rgba(139,92,246,0.08));border:1px solid rgba(139,92,246,0.25);">
                            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                                <div>
                                    <span style="font-size:0.78rem;color:#8b5cf6;font-weight:600;">📂 输出目录</span>
                                    <div style="font-size:0.75rem;color:#a78bfa;font-family:monospace;word-break:break-all;margin-top:2px;">{display_dir}</div>
                                    <div style="font-size:0.72rem;color:#9ca3af;margin-top:2px;">共 {file_count} 个音频文件</div>
                                </div>
                            </div>
                        </div>"""
    
                    _lt.update(100, f"完成 {ok_count}/{len(results)}")
                    _safe_vocal = (
                        last_vocal
                        if (
                            last_vocal
                            and isinstance(last_vocal, str)
                            and os.path.exists(last_vocal)
                        )
                        else None
                    )
                    _safe_instr = (
                        last_instr
                        if (
                            last_instr
                            and isinstance(last_instr, str)
                            and os.path.exists(last_instr)
                        )
                        else None
                    )
                    _safe_output = (
                        final_output
                        if (
                            final_output
                            and isinstance(final_output, str)
                            and os.path.exists(final_output)
                        )
                        else None
                    )
                    _recent = (
                        dict(recent_state)
                        if recent_state
                        else {"models": [], "audio": []}
                    )
                    if selected_models:
                        for m in selected_models:
                            if m not in _recent.get("models", []):
                                _recent.setdefault("models", []).insert(0, m)
                        _recent["models"] = _recent["models"][:8]
                    if all_paths:
                        for p in all_paths[:3]:
                            pname = os.path.basename(p)
                            if pname not in _recent.get("audio", []):
                                _recent.setdefault("audio", []).insert(0, pname)
                        _recent["audio"] = _recent["audio"][:6]
                    _rec_html = ""
                    if _recent.get("models") or _recent.get("audio"):
                        _rec_html = '<div style="font-size:0.76rem;"><div style="color:#8b5cf6;font-weight:600;font-size:0.76rem;margin-bottom:4px;">🕐 最近使用</div>'
                        if _recent.get("models"):
                            _rec_html += (
                                '<div style="font-size:0.72rem;color:#a78bfa;margin-bottom:2px;">🎤 模型: '
                                + " · ".join(_recent["models"][:5])
                                + "</div>"
                            )
                        if _recent.get("audio"):
                            _rec_html += (
                                '<div style="font-size:0.72rem;color:#a78bfa;">🎵 音频: '
                                + " · ".join(_recent["audio"][:4])
                                + "</div></div>"
                            )
    
                    if final_outputs:
                        first_audio_path = all_paths[0] if all_paths else ""
                        _output_history.add_record(
                            original_path=first_audio_path,
                            converted_paths=final_outputs,
                            model_names=list(selected_models),
                            params={
                                "pitch": pitch_shift,
                                "vocal_vol": vocal_vol,
                                "inst_vol": inst_vol,
                                "protect": protect,
                            },
                            category="cover",
                            status="success" if ok_count > 0 else "failed",
                        )
    
                    hist_panel_html = _output_history.render_panel_html()
                    _final_info = (
                        '<div style="padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(52,211,153,0.04));border:1px solid rgba(16,185,129,0.25);"><span style="color:#10b981;font-weight:700;font-size:0.82rem;">✅ 处理完成</span><div style="font-size:0.74rem;color:#34d399;margin-top:4px;">成功 '
                        + str(ok_count)
                        + "/"
                        + str(len(results))
                        + " 个 | 可在上方预览各阶段音频并下载</div></div>"
                    )
                    _final_vocal_dl = build_download_html(_safe_vocal, "⬇️ 下载干声", "green") if _safe_vocal and os.path.exists(_safe_vocal) else ""
                    _final_instr_dl = build_download_html(_safe_instr, "⬇️ 下载伴奏", "blue") if _safe_instr and os.path.exists(_safe_instr) else ""
                    _final_dl = dl_html + _final_info
                    _update_status(f"✅ 处理完成！成功 {ok_count} 个文件", "#10b981", "rgba(16,185,129,0.08)")
                    _clear_cancel("ai_cover")
                    _release_exec("ai_cover")
                    try:
                        mark_task_completed(f"AI翻唱 {ok_count}/{len(results)}")
                    except (NameError, UnboundLocalError):
                        mark_task_completed("AI翻唱")
                    notify_done("RVC AI 翻唱完成", f"成功 {ok_count}/{len(results)}")
                    yield (
                        _progress_html(
                            100,
                            "完成 (" + str(ok_count) + "/" + str(len(results)) + ")",
                            summary,
                        ),
                        _safe_vocal,
                        _safe_instr,
                        _safe_output,
                        _final_vocal_dl,
                        _final_instr_dl,
                        _final_dl,
                        _recent,
                        _rec_html,
                        _get_taskbar_html(),
                        _status_html,
                    )
                except ValueError as _ve:
                    if "already executing" in str(_ve) or "executing" in str(_ve):
                        print_status(
                            "⚠️ AI翻唱: 检测到生成器并发访问，处理仍在后台继续运行",
                            "warning",
                        )
                        if _lt:
                            _lt.complete(success=False, error="生成器并发冲突")
                        _release_exec("ai_cover")
                        _err_html = '<div style="padding:10px;border-radius:10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.3);"><span style="color:#f59e0b;font-weight:700;font-size:0.85rem;">⚠️ 处理继续中</span><div style="font-size:0.74rem;color:#d97706;margin-top:4px;">检测到界面刷新冲突，但音频处理仍在后台正常执行。请稍后查看输出目录获取结果文件。</div></div>'
                        try:
                            yield (
                                _err_html,
                                None,
                                None,
                                None,
                                "",
                                "",
                                "",
                                recent_state,
                                "",
                                _get_taskbar_html(),
                                '<div style="padding:6px 10px;border-radius:6px;background:rgba(245,158,11,0.08);color:#f59e0b;font-size:0.74rem;">⚠️ 处理继续中...</div>',
                            )
                        except Exception:
                            pass
                        return
                    raise
                except Exception as e:
                    if _lt:
                        _lt.complete(success=False, error=str(e))
                    raise
                finally:
                    _clear_cancel("ai_cover")
                    if _is_executing("ai_cover"):
                        _release_exec("ai_cover")
                    if _lt:
                        _lt.complete(success=True)
    
            ac_btn.click(
                fn=ai_cover_process,
                inputs=[
                    ac_upload,
                    ac_sid,
                    ac_pitch,
                    ac_vocal_vol,
                    ac_inst_vol,
                    ac_protect,
                    ac_sid_slider,
                    ac_recent_state,
                    ac_output_format,
                    ac_paths_state,
                ],
                outputs=[
                    ac_progress,
                    ac_vocal_out,
                    ac_instr_out,
                    ac_output,
                    ac_vocal_dl,
                    ac_instr_dl,
                    ac_download,
                    ac_recent_state,
                    ac_recent_display,
                    _global_taskbar,
                    ac_status_display,
                ],
            )
    
