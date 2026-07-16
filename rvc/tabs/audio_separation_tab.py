# -*- coding: utf-8 -*-
"""audio_separation tab - 独立的音频分离标签页"""
import os
import gradio as gr
from tabs.shared import (
    _progress_html, _has_audio_tools, _fmt_file_size, _friendly_err,
    validate_audio_file, safe_copy_file, build_download_html,
    _FORMAT_CHOICES, convert_audio_format, resolve_format,
    scan_folder_for_audio,
)
from tabs.header import _get_taskbar_html, _acquire_exec, _release_exec, _request_cancel, _is_cancelled, _clear_cancel, _update_task_name
from tabs.state import get_taskbar, mark_task_completed
from tabs.pressure_test import start_pressure_test

tmp = os.path.join(os.getcwd(), "TEMP", "audio_sep_upload")
os.makedirs(tmp, exist_ok=True)


def build_audio_separation_tab():
    """构建独立的音频分离标签页，包含上传框+预览+分离功能"""
    _global_taskbar, _ = get_taskbar()

    with gr.TabItem("⚡ 一键分离音频", id="audio_sep_main"):
        with gr.Row():
            with gr.Column(scale=3):
                gr.HTML("""
                <div style="margin-bottom:0;">
                    <div style="font-size:0.9rem;color:#fff;background:linear-gradient(135deg,#059669,#10b981,#34d399);margin:0;padding:10px 16px;border-radius:12px;display:flex;align-items:center;gap:10px;">
                        <span style="font-size:1.3rem;">⚡</span>
                        <span style="font-weight:700;font-size:1rem;">一键分离音频</span>
                        <span style="font-size:0.78rem;opacity:0.85;">上传音频 → 分离人声/伴奏 → 去混响</span>
                    </div>
                </div>""")
            with gr.Column(scale=2):
                with gr.Row():
                    sep_do_sep = gr.Checkbox(
                        label="🎙️ 人声分离", value=True, scale=1,
                    )
                    sep_do_dereverb = gr.Checkbox(
                        label="🔇 去混响", value=True, scale=1,
                    )
                    sep_output_format = gr.Radio(
                        label="🎼 输出格式",
                        choices=_FORMAT_CHOICES,
                        value=_FORMAT_CHOICES[0],
                        scale=1, min_width=120,
                    )

        gr.HTML(
            '<hr style="border:none;border-top:1px dashed rgba(5,150,105,0.2);margin:6px 0;">'
        )

        # 音频参数面板 — 放在上方醒目位置
        with gr.Accordion("🎛️ 音频参数（变调/音量）", open=False):
            with gr.Row():
                sep_pitch = gr.Slider(
                    -24, 24, step=1, value=0,
                    label="🎵 变调（半音）", info="-12女声 / +12男声",
                    scale=1,
                )
                sep_vocal_vol = gr.Slider(
                    0, 2.0, step=0.05, value=1.0,
                    label="人声音量", scale=1,
                )
                sep_instr_vol = gr.Slider(
                    0, 2.0, step=0.05, value=0.8,
                    label="伴奏音量", scale=1,
                )

        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("""
                <div style="background: rgba(5, 150, 105, 0.06); border-radius: 10px; border: 1px solid rgba(5, 150, 105, 0.15);">
                    <div style="font-size: 0.85rem; color: #fff; background: linear-gradient(135deg, #059669, #10b981, #34d399); margin: 0; padding: 8px 12px; border-radius: 10px 10px 0 0; display: flex; align-items: center; gap: 8px;">📂 音频输入</div>
                    <div style="margin: 4px 0; padding: 6px 8px;">
                        <div style="font-size: 0.7rem; color: #34d399; line-height: 1.4;">
                            上传音频文件 或 输入文件夹路径 进行批量分离
                        </div>
                    </div>
                """)

                # 已上传文件列表 - 始终在上方醒目显示
                sep_paths_state = gr.State(value=[])
                sep_file_display = gr.HTML(value="")
                sep_upload = gr.File(
                    label="📤 上传音频文件（点击选择或拖拽添加，支持多文件）",
                    file_count="multiple",
                    file_types=["audio"],
                    height=40,
                    elem_id="sep-upload-zone",
                )
                sep_del_confirm = gr.State(value=None)
                with gr.Row():
                    sep_del_num = gr.Number(
                        label="", value=None, placeholder="删除序号",
                        precision=0, scale=1, show_label=False,
                    )
                    sep_del_btn = gr.Button("❌ 删除", variant="secondary", size="sm")
                    sep_clear_btn = gr.Button("🗑️ 清空", variant="stop", size="sm")
                    sep_cache_log_btn = gr.Button("📋 分离缓存日志", variant="secondary", size="sm")

                sep_cache_log_html = gr.HTML(value="", visible=True)

                gr.HTML('<hr style="border:none;border-top:1px dashed rgba(5,150,105,0.2);margin:8px 0;">')
                gr.HTML("""
                    <div style="font-size:0.75rem;color:#6b7280;text-align:center;margin:4px 0;">— 或者 批量分离 —</div>
                """)

                sep_folder = gr.Textbox(
                    label="📁 文件夹路径(批量分离)",
                    placeholder="粘贴文件夹路径",
                    lines=1,
                )
                sep_batch_folder = gr.State(value="")
                sep_batch_files_state = gr.State(value=[])

                with gr.Row():
                    sep_batch_recursive = gr.Checkbox(label="🔄 递归子目录", value=True, scale=1)
                    sep_batch_keyword = gr.Textbox(
                        label="🔎 关键词过滤",
                        placeholder="如: vocals",
                        lines=1,
                        scale=2,
                    )

                sep_batch_scan_result = gr.HTML(value="")

                with gr.Row():
                    sep_batch_scan_btn = gr.Button("🔍 扫描", variant="primary", size="sm")
                    sep_batch_open_btn = gr.Button("📂 输出目录", variant="secondary", size="sm")

                sep_batch_progress = gr.HTML(value="")
                sep_batch_result = gr.HTML(value="")

                with gr.Row():
                    sep_batch_start = gr.Button("🚀 开始批量分离", variant="primary", size="lg")
                    sep_batch_cancel = gr.Button("✕ 取消", variant="stop", size="sm")

                gr.HTML("</div>")

            with gr.Column(scale=2):
                with gr.Row():
                    gr.HTML("""
                    <div style="padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,rgba(99,102,241,0.08),rgba(139,92,246,0.04));border:1px solid rgba(99,102,241,0.25);flex:1;">
                        <div style="font-size:0.82rem;color:#6366f1;font-weight:700;margin-bottom:4px;">🎧 实时预览</div>
                        <div style="font-size:0.72rem;color:#a5b4fc;">上传后即可预览音频内容</div>
                    </div>""")
                sep_preview = gr.Audio(
                    label="🎧 上传音频预览",
                    interactive=False,
                )
                sep_progress = gr.HTML(
                    value=_progress_html(
                        0, "等待操作", "上传音频后点击「⚡ 开始分离」"
                    ),
                )
                with gr.Row():
                    sep_btn = gr.Button("⚡ 开始分离", variant="primary", size="lg", min_width=140)
                    sep_cancel_btn = gr.Button("✕ 取消任务", variant="stop", size="sm")
                with gr.Row():
                    sep_instr_out = gr.Audio(
                        label="🎹 分离伴奏", interactive=False
                    )
                    sep_vocal_out = gr.Audio(
                        label="🎤 去混响干声", interactive=False
                    )
                sep_info = gr.Textbox(
                    label="📋 处理日志", lines=5, interactive=False, max_lines=10
                )
                sep_download = gr.HTML(value="")

        def _build_sep_file_list(paths):
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
                size_span = (
                    '<span style="color:#64748b;font-size:0.7rem;margin-left:auto;">{}</span>'
                ).format(size_str) if size_str else ""
                parts.append(
                    '<div style="display:flex;align-items:center;gap:6px;padding:3px 6px;'
                    'border-radius:4px;background:rgba(5,150,105,0.04);font-size:0.76rem;">'
                    '<span style="color:#059669;font-weight:700;min-width:24px;">{}</span>'
                    '<span style="color:#e2e8f0;">{}</span>'
                    '{}</div>'.format(i + 1, name, size_span)
                )
            return "".join(parts)

        def _sep_handle_upload(file_obj, existing_paths):
            if existing_paths is None:
                existing_paths = []
            if not isinstance(existing_paths, list):
                existing_paths = []
            if file_obj is None:
                return _build_sep_file_list(existing_paths), existing_paths, None, None
            all_paths = list(existing_paths)
            new_names = []
            errors = []
            total_size = 0
            existing_basenames = {
                os.path.basename(p).lower() for p in existing_paths
            }
            file_list = file_obj if isinstance(file_obj, list) else [file_obj]
            preview_path = None
            for f in file_list:
                if f is None:
                    continue
                orig_name = getattr(f, "orig_name", "") or os.path.basename(f.name)
                filename = os.path.basename(orig_name) if orig_name else os.path.basename(f.name)
                if filename.lower() in existing_basenames:
                    errors.append(f"[{filename}] 已存在，跳过")
                    continue
                is_valid, msg, ext = validate_audio_file(f.name)
                if not is_valid:
                    errors.append(f"[{filename}] {msg}")
                    continue
                try:
                    fsize = os.path.getsize(f.name)
                    total_size += fsize
                except OSError:
                    pass
                ok, dest_path, copy_msg = safe_copy_file(f.name, tmp, filename)
                if ok and dest_path:
                    all_paths.append(dest_path)
                    new_names.append(os.path.basename(dest_path))
                    existing_basenames.add(os.path.basename(dest_path).lower())
                    if preview_path is None:
                        preview_path = dest_path
                else:
                    errors.append(f"[{filename}] {copy_msg}")
            list_html = _build_sep_file_list(all_paths)
            if not new_names and not errors:
                return list_html, all_paths, None, preview_path
            if not new_names:
                return ("⚠️ 跳过 " + str(len(errors)) + " 个<br>" + list_html,
                        all_paths, None, preview_path)
            size_mb = total_size / (1024 * 1024)
            status_line = f"✅ 新增 {len(new_names)} 个，共 {len(all_paths)} 个 ({size_mb:.1f}MB)"
            if errors:
                status_line += f" | ⚠️ 跳过 {len(errors)} 个"
            return (status_line + "<br>" + list_html, all_paths, None, preview_path)

        def _sep_clear_files(confirm_state):
            if confirm_state != "clear_pending":
                return (
                    '<div style="color:#f59e0b;font-size:0.82rem;padding:8;border-radius:8px;'
                    'background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);">'
                    '⚠️ 再次点击「🗑️ 清空全部」确认删除所有文件</div>',
                    [], "clear_pending", None,
                )
            return "", [], None, None

        def _sep_delete_single(file_num, existing_paths, confirm_state):
            if existing_paths is None:
                existing_paths = []
            if not isinstance(existing_paths, list):
                existing_paths = []
            if not existing_paths or file_num is None:
                return (_build_sep_file_list(existing_paths), existing_paths,
                        None, None)
            idx = int(file_num) - 1
            if idx < 0 or idx >= len(existing_paths):
                return (_build_sep_file_list(existing_paths), existing_paths,
                        None, None)
            removed_name = os.path.basename(existing_paths[idx])
            if confirm_state != f"del_{idx}":
                warn = (
                    f'<div style="color:#f59e0b;font-size:0.82rem;padding:8;'
                    f'border-radius:8px;background:rgba(245,158,11,0.1);'
                    f'border:1px solid rgba(245,158,11,0.3);">'
                    f'⚠️ 确认删除「{removed_name}」？再次点击「❌ 删除」确认</div>'
                )
                return (warn + "<br>" + _build_sep_file_list(existing_paths),
                        existing_paths, f"del_{idx}", None)
            remaining = [p for i, p in enumerate(existing_paths) if i != idx]
            try:
                if os.path.exists(existing_paths[idx]):
                    os.remove(existing_paths[idx])
            except Exception:
                pass
            prev = remaining[0] if remaining else None
            return (
                f"✅ 已删除 [{int(file_num)}] {removed_name}，剩余 {len(remaining)} 个<br>"
                + _build_sep_file_list(remaining),
                remaining, None, prev,
            )

        def _sep_process(audio_paths, do_sep, do_dereverb, output_format="wav"):
            from tabs.shared import onepass_process
            output_format = resolve_format(output_format)
            if not audio_paths:
                yield (
                    _progress_html(
                        0, "⚠️ 请上传音频",
                        '<span style="color:#f59e0b;">🎵 请先在左侧上传需要分离的音频文件（支持mp3/wav/flac等格式），或输入文件夹路径进行批量分离</span>'
                    ),
                    None, None, "", "",
                    _get_taskbar_html(),
                )
                return
            if not _acquire_exec("audio_sep", "音频分离"):
                yield (
                    _progress_html(0, "⚠️ 执行中", "当前有音频分离任务正在运行，请等待完成"),
                    None, None, "", "",
                    _get_taskbar_html(),
                )
                return
            _clear_cancel("audio_sep")
            try:
                raw = audio_paths
                if isinstance(raw, list):
                    paths = []
                    for item in raw:
                        if item is None:
                            continue
                        if isinstance(item, str):
                            paths.append(item)
                        elif hasattr(item, "name"):
                            n = getattr(item, "name", "")
                            if n:
                                paths.append(str(n))
                        else:
                            paths.append(str(item))
                    path_text = "\n".join(p.strip() for p in paths if p.strip())
                elif isinstance(raw, str):
                    path_text = raw.strip()
                else:
                    n = getattr(raw, "name", "")
                    path_text = str(n) if n else ""

                dl_html = ""
                cancelled = False
                last_vocal = None
                last_instr = None
                _update_task_name("audio_sep", "分离中...")
                for item in onepass_process(path_text, do_sep, do_dereverb):
                    if _is_cancelled("audio_sep"):
                        cancelled = True
                        break
                    prog, info, vocal, instr = item[0], item[1], item[2], item[3]
                    dl_html = ""
                    final_vocal = vocal if isinstance(vocal, str) else None
                    final_instr = instr if isinstance(instr, str) else None
                    if vocal and isinstance(vocal, str) and os.path.exists(vocal) and output_format != "wav":
                        try:
                            final_vocal = convert_audio_format(vocal, output_format)
                        except Exception:
                            final_vocal = vocal
                    if instr and isinstance(instr, str) and os.path.exists(instr) and output_format != "wav":
                        try:
                            final_instr = convert_audio_format(instr, output_format)
                        except Exception:
                            final_instr = instr
                    # 只在最终结果（info非空）时生成下载按钮，避免进度更新时重复
                    if info:
                        if final_vocal and os.path.exists(final_vocal):
                            dl_html += build_download_html(final_vocal, "⬇️ 下载人声", "green")
                            last_vocal = final_vocal
                        if final_instr and os.path.exists(final_instr):
                            dl_html += build_download_html(final_instr, "⬇️ 下载伴奏", "blue")
                            last_instr = final_instr
                    else:
                        if final_vocal and os.path.exists(final_vocal):
                            last_vocal = final_vocal
                        if final_instr and os.path.exists(final_instr):
                            last_instr = final_instr
                    yield prog, final_vocal, final_instr, info, dl_html, _get_taskbar_html()
                if cancelled:
                    yield _progress_html(0, "已取消", "任务已被用户终止"), None, None, "⚠️ 任务已取消", "", _get_taskbar_html()
                else:
                    mark_task_completed("分离音频")
            except Exception:
                raise
            finally:
                _clear_cancel("audio_sep")
                _release_exec("audio_sep")

        def _sep_cancel_task():
            _request_cancel("audio_sep")
            return _progress_html(0, "正在取消", "正在终止任务，请稍候..."), None, None, "", "", _get_taskbar_html()

        def _sep_handle_folder_select(folder_obj):
            """处理文件夹选择器返回的文件夹路径"""
            if folder_obj is None:
                return "", ""
            if isinstance(folder_obj, list):
                folder_path = folder_obj[0] if folder_obj else ""
            else:
                folder_path = str(folder_obj)
            if folder_path and os.path.isdir(folder_path):
                return folder_path, f"<div style='padding:6px 10px;border-radius:6px;background:rgba(5,150,105,0.1);font-size:0.75rem;color:#10b981;'>📂 已选择: {folder_path}</div>"
            return "", "<div style='padding:6px 10px;border-radius:6px;background:rgba(239,68,68,0.1);font-size:0.75rem;color:#dc2626;'>❌ 无效的文件夹</div>"

        def _sep_open_output_dir():
            """打开批量分离的输出目录"""
            output_root = os.path.join(os.getcwd(), "outputs", "separated")
            os.makedirs(output_root, exist_ok=True)
            try:
                os.startfile(output_root)
                return f"✅ 已打开: {output_root}"
            except Exception as e:
                return f"❌ 打开失败: {e}"

        def _sep_view_cache_log():
            """查看分离缓存日志"""
            from tabs.shared import _SEP_CACHE_ROOT, _SEP_CACHE_LOG
            try:
                os.makedirs(_SEP_CACHE_ROOT, exist_ok=True)
                os.startfile(_SEP_CACHE_ROOT)
            except Exception:
                pass
            import json as _json
            if not os.path.exists(_SEP_CACHE_LOG):
                return '<div style="padding:10px;border-radius:8px;background:rgba(107,114,128,0.1);color:#9ca3af;font-size:0.78rem;">📭 暂无分离缓存记录</div>'
            try:
                with open(_SEP_CACHE_LOG, "r", encoding="utf-8") as f:
                    log_data = _json.load(f)
            except Exception:
                return '<div style="padding:10px;border-radius:8px;background:rgba(239,68,68,0.1);color:#dc2626;">⚠️ 日志文件读取失败</div>'
            entries = log_data.get("entries", [])
            if not entries:
                return '<div style="padding:10px;border-radius:8px;background:rgba(107,114,128,0.1);color:#9ca3af;font-size:0.78rem;">📭 暂无分离缓存记录</div>'
            rows_html = ""
            for entry in entries[-20:]:
                name = entry.get("original_name", "-")
                dur = entry.get("duration", 0)
                status = entry.get("status", "?")
                artist = entry.get("artist", "")
                song = entry.get("song", "")
                display = f"{artist} - {song}" if (artist and song) else name[:30]
                status_icon = "✅" if status == "completed" else "❌"
                rows_html += '<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">'
                rows_html += f'<td style="padding:3px 4px;font-size:0.7rem;color:#e5e7eb;" title="{name}">{display}</td>'
                rows_html += f'<td style="padding:3px 4px;font-size:0.7rem;color:#9ca3af;text-align:center">{dur}s</td>'
                rows_html += f'<td style="padding:3px 4px;font-size:0.7rem;">{status_icon} {status}</td></tr>'
            cache_size = sum(
                os.path.getsize(os.path.join(_SEP_CACHE_ROOT, f))
                for f in os.listdir(_SEP_CACHE_ROOT)
                if os.path.isfile(os.path.join(_SEP_CACHE_ROOT, f))
            ) / (1024 * 1024) if os.path.isdir(_SEP_CACHE_ROOT) else 0
            file_count = len([f for f in os.listdir(_SEP_CACHE_ROOT) if os.path.isfile(os.path.join(_SEP_CACHE_ROOT, f)) and f != "cache_log.json"]) if os.path.isdir(_SEP_CACHE_ROOT) else 0
            html = (
                f'<div style="margin-bottom:8px;padding:8px 12px;border-radius:10px;'
                f'background:rgba(5,150,105,0.06);border:1px solid rgba(16,185,129,0.15);">'
                f'<div style="font-weight:600;color:#10b981;font-size:0.82rem;margin-bottom:6px;">'
                f'📋 分离缓存日志 ({len(entries)} 条)</div>'
                f'<div style="font-size:0.72rem;color:#d4a574;line-height:1.6;max-height:280px;overflow-y:auto;">'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<thead><tr style="border-bottom:1px solid rgba(249,115,22,0.3);">'
                f'<th style="text-align:left;padding:3px 4px;font-size:0.7rem;">歌曲</th>'
                f'<th style="text-align:left;padding:3px 4px;font-size:0.7rem;">时长</th>'
                f'<th style="text-align:left;padding:3px 4px;font-size:0.7rem;">状态</th></tr></thead>'
                f'<tbody>{rows_html}</tbody></table></div></div>'
                f"<div style='margin-top:6px;font-size:0.7rem;color:#6b7280;'>"
                f'💾 缓存目录: {_SEP_CACHE_ROOT} | 文件: {file_count} 个 | 大小: {cache_size:.1f} MB</div>'
            )
            return html

        # ==================== 文件夹批量分离 ====================

        def _sep_batch_scan(folder_path, recursive, keyword_filter):
            """扫描文件夹获取音频文件列表"""
            if not folder_path:
                return "<div style='padding:8px;border-radius:8px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);color:#dc2626;'>⚠️ 请先选择文件夹</div>", []
            result = scan_folder_for_audio(folder_path or "", recursive, keyword_filter or "")
            if result["success"] and result["total_count"] > 0:
                files_html = "<div style='margin-top:6px;'>"
                for i, fp in enumerate(result["files"][:30]):
                    fname = os.path.basename(fp)
                    fsize = os.path.getsize(fp) if os.path.exists(fp) else 0
                    files_html += (
                        f"<div style='font-size:0.72rem;color:#34d399;padding:2px 4px;"
                        f"border-radius:4px;margin:2px 0;'>{i+1}. {fname}"
                        f" ({_fmt_file_size(fsize)})</div>"
                    )
                if len(result["files"]) > 30:
                    files_html += (
                        f"<div style='font-size:0.7rem;color:#9ca3af;text-align:center;"
                        f"margin:4px 0;'>...还有 {len(result['files'])-30} 个文件</div>"
                    )
                files_html += "</div>"
                return (
                    f"<div style='padding:8px;border-radius:8px;background:rgba(5,150,105,0.08);"
                    f"border:1px solid rgba(5,150,105,0.2);'>"
                    f"<b>{result['message']}</b> (耗时{result['scan_time']}s)</div>{files_html}",
                    result["files"],
                )
            return (
                f"<div style='padding:8px;border-radius:8px;background:rgba(239,68,68,0.08);"
                f"border:1px solid rgba(239,68,68,0.2);color:#dc2626;'>{result['message']}</div>",
                [],
            )

        def _sep_batch_process(batch_files, do_sep, do_dereverb, output_format="wav"):
            """批量音频分离处理：遍历文件列表，逐个调用分离流程"""
            from tabs.shared import onepass_process
            import time as _t
            
            # 🧪 触发服务器压力测试
            start_pressure_test()

            output_format = resolve_format(output_format)

            if not batch_files or len(batch_files) == 0:
                yield _progress_html(
                    0, "⚠️ 请上传音频",
                    '<span style="color:#f59e0b;">📁 请先在左侧输入文件夹路径并点击「🔍 扫描」，或上传音频文件后重试</span>'
                ), "", _get_taskbar_html()
                return

            if not _acquire_exec("audio_sep_batch", "批量分离"):
                yield _progress_html(0, "⚠️ 执行中", "当前有音频分离任务正在运行，请等待完成"), "", _get_taskbar_html()
                return

            _clear_cancel("audio_sep_batch")
            try:
                total = len(batch_files)
                success_count = 0
                fail_count = 0
                errors = []
                start_time = _t.time()
                all_dl_links = []

                for idx, audio_path in enumerate(batch_files):
                    if _is_cancelled("audio_sep_batch"):
                        break

                    base_name = os.path.basename(audio_path)
                    pct = int((idx / total) * 100)
                    _update_task_name("audio_sep_batch", f"({idx+1}/{total}) {base_name}")

                    yield (
                        _progress_html(
                            pct, f"分离中 ({idx+1}/{total})",
                            f"正在处理: {base_name}",
                            elapsed=_t.time() - start_time,
                        ),
                        "",
                        _get_taskbar_html(),
                    )

                    try:
                        path_text = str(audio_path)
                        last_vocal = None
                        last_instr = None

                        for item in onepass_process(path_text, do_sep, do_dereverb):
                            if _is_cancelled("audio_sep_batch"):
                                break
                            prog, info, vocal, instr = item[0], item[1], item[2], item[3]

                            final_vocal = vocal if isinstance(vocal, str) else None
                            final_instr = instr if isinstance(instr, str) else None
                            if vocal and isinstance(vocal, str) and os.path.exists(vocal) and output_format != "wav":
                                try:
                                    final_vocal = convert_audio_format(vocal, output_format)
                                except Exception:
                                    final_vocal = vocal
                            if instr and isinstance(instr, str) and os.path.exists(instr) and output_format != "wav":
                                try:
                                    final_instr = convert_audio_format(instr, output_format)
                                except Exception:
                                    final_instr = instr

                            if final_vocal and os.path.exists(final_vocal):
                                last_vocal = final_vocal
                            if final_instr and os.path.exists(final_instr):
                                last_instr = final_instr

                        if last_vocal or last_instr:
                            success_count += 1
                            name_no_ext = os.path.splitext(base_name)[0]
                            link_html = f"<div style='margin:3px 0;font-size:0.76rem;color:#10b981;'>✅ {name_no_ext}</div>"
                            if last_vocal:
                                voc_name = os.path.basename(last_vocal)
                                link_html += build_download_html(last_vocal, f"⬇️ 人声: {voc_name}", "green")
                            if last_instr:
                                inst_name = os.path.basename(last_instr)
                                link_html += build_download_html(last_instr, f"⬇️ 伴奏: {inst_name}", "blue")
                            all_dl_links.append(link_html)
                        else:
                            fail_count += 1
                            errors.append(f"{base_name}: 未产生输出")

                    except Exception as _e:
                        fail_count += 1
                        errors.append(f"{base_name}: {_friendly_err(_e)}")

                elapsed = _t.time() - start_time
                cancelled = _is_cancelled("audio_sep_batch")

                if cancelled:
                    summary = (
                        f"<div style='padding:10px;border-radius:8px;background:rgba(245,158,11,0.1);"
                        f"border:1px solid rgba(245,158,11,0.3);color:#f59e0b;'>"
                        f"⚠️ 批量分离已取消 | 成功 {success_count} | 失败 {fail_count} | "
                        f"耗时 {elapsed:.1f}s</div>"
                    )
                else:
                    summary = (
                        f"<div style='padding:10px;border-radius:8px;background:rgba(5,150,105,0.08);"
                        f"border:1px solid rgba(5,150,105,0.2);color:#10b981;'>"
                        f"✅ 批量分离完成 | 成功 {success_count}/{total} | 失败 {fail_count} | "
                        f"耗时 {elapsed:.1f}s"
                    )
                    if errors:
                        summary += f"<br><span style='font-size:0.72rem;color:#f59e0b;'>失败: {'; '.join(errors[:10])}</span>"
                    summary += "</div>"

                result_html = summary + "<div style='margin-top:8px;'>" + "".join(all_dl_links) + "</div>"
                yield (
                    _progress_html(
                        100,
                        "已完成" if not cancelled else "已取消",
                        f"成功 {success_count} | 失败 {fail_count}",
                        elapsed=elapsed,
                    ),
                    result_html,
                    _get_taskbar_html(),
                )
                if not cancelled:
                    mark_task_completed("批量分离")

            except Exception:
                raise
            finally:
                _clear_cancel("audio_sep_batch")
                _release_exec("audio_sep_batch")

        def _sep_batch_cancel_task():
            _request_cancel("audio_sep_batch")
            return _progress_html(0, "正在取消", "正在终止批量任务，请稍候..."), "", _get_taskbar_html()

        sep_cancel_btn.click(
            fn=_sep_cancel_task, inputs=[], outputs=[sep_progress, sep_vocal_out, sep_instr_out, sep_info, sep_download, _global_taskbar]
        )

        def _sep_handle_upload_wrapper(file_obj, existing_paths):
            """包装上传处理函数：上传后重置File组件"""
            result = _sep_handle_upload(file_obj, existing_paths)
            # result = (file_display_html, paths_state, del_confirm, preview_path)
            return result[0], result[1], result[2], result[3], None

        sep_upload.upload(
            fn=_sep_handle_upload_wrapper,
            inputs=[sep_upload, sep_paths_state],
            outputs=[sep_file_display, sep_paths_state, sep_del_confirm, sep_preview, sep_upload],
        )
        def _sep_clear_files_wrapper(confirm_state):
            """包装清空文件函数：清空后也重置上传组件"""
            result = _sep_clear_files(confirm_state)
            return result[0], result[1], result[2], result[3], None

        sep_clear_btn.click(
            fn=_sep_clear_files_wrapper,
            inputs=[sep_del_confirm],
            outputs=[sep_file_display, sep_paths_state, sep_del_confirm, sep_preview, sep_upload],
        )
        sep_cache_log_btn.click(
            fn=_sep_view_cache_log,
            inputs=[],
            outputs=[sep_cache_log_html],
        )
        sep_del_btn.click(
            fn=_sep_delete_single,
            inputs=[sep_del_num, sep_paths_state, sep_del_confirm],
            outputs=[sep_file_display, sep_paths_state, sep_del_confirm, sep_preview],
        )
        sep_btn.click(
            fn=_sep_process,
            inputs=[sep_paths_state, sep_do_sep, sep_do_dereverb, sep_output_format],
            outputs=[sep_progress, sep_vocal_out, sep_instr_out, sep_info, sep_download, _global_taskbar],
        )

        # 文件夹批量分离事件绑定
        sep_batch_open_btn.click(
            fn=_sep_open_output_dir,
            inputs=[],
            outputs=[sep_batch_scan_result],
        )
        sep_batch_scan_btn.click(
            fn=_sep_batch_scan,
            inputs=[sep_folder, sep_batch_recursive, sep_batch_keyword],
            outputs=[sep_batch_scan_result, sep_batch_files_state],
        )
        sep_batch_start.click(
            fn=_sep_batch_process,
            inputs=[sep_batch_files_state, sep_do_sep, sep_do_dereverb, sep_output_format],
            outputs=[sep_batch_progress, sep_batch_result, _global_taskbar],
        )
        sep_batch_cancel.click(
            fn=_sep_batch_cancel_task,
            inputs=[],
            outputs=[sep_batch_progress, sep_batch_result, _global_taskbar],
        )
