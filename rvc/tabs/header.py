# -*- coding: utf-8 -*-
"""Header JS, particles, slider fix, and taskbar - rendered inside gr.Blocks context."""
import threading
import gradio as gr
from tabs.shared import *
from tabs.state import register_taskbar, get_completed_state, reset_completed_state

# ==================== 全局任务状态栏 TaskBar（模块级别，供其他tab导入） ====================
_executing_lock = threading.Lock()
_executing_tasks: dict[str, str] = {}
_cancel_flags: dict[str, bool] = {}
_last_complete_time: float = 0.0
_last_complete_info: str = ""


def _request_cancel(task_type: str):
    with _executing_lock:
        _cancel_flags[task_type] = True


def _is_cancelled(task_type: str) -> bool:
    with _executing_lock:
        return _cancel_flags.get(task_type, False)


def _clear_cancel(task_type: str):
    with _executing_lock:
        _cancel_flags.pop(task_type, None)


def _acquire_exec(task_type: str, task_name: str = "") -> bool:
    global _executing_tasks
    with _executing_lock:
        if task_type in _executing_tasks:
            return False
        _executing_tasks[task_type] = task_name or task_type
        return True


def _release_exec(task_type: str):
    global _executing_tasks
    with _executing_lock:
        _executing_tasks.pop(task_type, None)


def _update_task_name(task_type: str, task_name: str):
    """更新正在运行的任务的显示名称（实时状态）。
    例如: _update_task_name("audio_sep", "分离: 歌名") 
    任务栏会实时显示 ⚡ 分离: 歌名
    """
    with _executing_lock:
        if task_type in _executing_tasks:
            _executing_tasks[task_type] = task_name


def _is_executing(task_type: str) -> bool:
    with _executing_lock:
        return task_type in _executing_tasks


def _get_taskbar_html():
    import time as _time
    with _executing_lock:
        tasks = dict(_executing_tasks)
    comp_count, comp_info = get_completed_state()
    if comp_count > 0:
        with _executing_lock:
            global _last_complete_time, _last_complete_info
            _last_complete_time = _time.time()
            _last_complete_info = comp_info or f"{comp_count}个任务"
        reset_completed_state()
    if not tasks:
        with _executing_lock:
            if _last_complete_time > 0 and (_time.time() - _last_complete_time) < 30:
                elapsed_sec = int(_time.time() - _last_complete_time)
                if comp_count > 0:
                    return '<div id="global-taskbar" style="position:sticky;top:0;z-index:999;display:flex;align-items:center;gap:8px;padding:6px 14px;border-radius:8px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);font-size:0.76rem;animation:task-complete-flash 0.6s ease-out;"><span style="color:#10b981;">✅</span><span style="color:#059669;font-weight:600;">完成</span><span style="color:#10b981;font-weight:700;margin-left:4px;">' + str(comp_count) + '</span><span style="color:#9ca3af;">个任务 — ' + _last_complete_info + '</span></div><style>@keyframes task-complete-flash{0%{background:rgba(16,185,129,0.3);transform:scale(1.02)}100%{background:rgba(16,185,129,0.12);transform:scale(1)}}</style>'
                return '<div id="global-taskbar" style="position:sticky;top:0;z-index:999;display:flex;align-items:center;gap:8px;padding:6px 14px;border-radius:8px;background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.15);font-size:0.76rem;opacity:' + str(max(0.4, 1.0 - elapsed_sec / 30.0)) + ';transition:opacity 1s;"><span style="color:#10b981;">✅</span><span style="color:#059669;font-weight:500;">最近完成</span><span style="color:#9ca3af;margin-left:4px;">' + _last_complete_info + ' (' + str(elapsed_sec) + '秒前)</span></div>'
        return '<div id="global-taskbar" style="position:sticky;top:0;z-index:999;display:flex;align-items:center;gap:8px;padding:6px 14px;border-radius:8px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);font-size:0.76rem;"><span style="color:#10b981;">●</span><span style="color:#059669;font-weight:600;">就绪</span><span style="color:#9ca3af;margin-left:4px;">所有模块空闲</span></div>'
    items = []
    icons = {
        "ai_cover": "🎤",
        "vc_convert": "🔊",
        "batch_convert": "📦",
        "full_pipeline": "🚀",
        "audio_sep": "⚡",
        "audio_sep_batch": "📦",
    }
    for ttype, tname in tasks.items():
        icon = icons.get(ttype, "⚡")
        items.append(
            '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:6px;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.25);color:#f59e0b;font-weight:500;white-space:nowrap;">'
            + icon
            + " "
            + tname
            + "</span>"
        )
    items_html = "".join(items)
    count = len(tasks)
    return (
        '<div id="global-taskbar" style="position:sticky;top:0;z-index:999;display:flex;align-items:center;gap:8px;padding:6px 14px;border-radius:8px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);font-size:0.76rem;"><span style="color:#f59e0b;animation:pulse-dot 1.5s infinite;">●</span><span style="color:#d97706;font-weight:600;">运行中</span> <span style="color:#f59e0b;font-weight:700;">'
        + str(count)
        + '</span> <span style="color:#9ca3af;">个任务</span><span style="margin-left:auto;display:flex;gap:4px;flex-wrap:wrap;">'
        + items_html
        + "</span></div><style>@keyframes pulse-dot{0%,100%{opacity:1}50%{opacity:0.3}}</style>"
    )


def build_header():
    """Create the header elements (JS, particles, taskbar) inside gr.Blocks context."""

    # 粒子效果背景（增强版）
    gr.HTML("""
    <div class="particles">
        <div class="particle" style="left: 5%; top: 15%; animation-delay: 0s; background: #7c3aed; width: 4px; height: 4px;"></div>
        <div class="particle" style="left: 15%; top: 85%; animation-delay: 2s; background: #8b5cf6; width: 6px; height: 6px;"></div>
        <div class="particle" style="left: 55%; top: 35%; animation-delay: 4s; background: #6d28d9; width: 3px; height: 3px;"></div>
        <div class="particle" style="left: 75%; top: 65%; animation-delay: 1s; background: #7c3aed; width: 5px; height: 5px;"></div>
        <div class="particle" style="left: 85%; top: 5%; animation-delay: 3s; background: #a78bfa; width: 4px; height: 4px;"></div>
        <div class="particle" style="left: 30%; top: 95%; animation-delay: 5s; background: #c4b5fd; width: 3px; height: 3px;"></div>
        <div class="particle" style="left: 20%; top: 25%; animation-delay: 7s; background: #8b5cf6; width: 4px; height: 4px;"></div>
        <div class="particle" style="left: 60%; top: 75%; animation-delay: 9s; background: #7c3aed; width: 5px; height: 5px;"></div>
        <div class="particle" style="left: 90%; top: 45%; animation-delay: 11s; background: #a78bfa; width: 3px; height: 3px;"></div>
        <div class="particle" style="left: 10%; top: 55%; animation-delay: 13s; background: #6d28d9; width: 4px; height: 4px;"></div>
    </div>
    """)

    # 强制显示Slider数值输入框的JavaScript
    gr.HTML("""
    <script>
    (function() {
        function fixSliderNumberInputs() {
            document.querySelectorAll('.gr-slider input[type="number"]').forEach(function(el) {
                el.style.display = 'block';
                el.style.visibility = 'visible';
                el.style.opacity = '1';
                el.style.width = '80px';
                el.style.minWidth = '60px';
                el.style.background = 'rgba(30, 30, 40, 0.9)';
                el.style.border = '1px solid rgba(255, 215, 0, 0.4)';
                el.style.borderRadius = '6px';
                el.style.color = '#fff';
                el.style.fontSize = '0.85rem';
                el.style.padding = '4px 8px';
                el.style.textAlign = 'center';
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fixSliderNumberInputs);
        } else {
            fixSliderNumberInputs();
        }
        setInterval(fixSliderNumberInputs, 2000);
    })();
    </script>
    """)

    # ==================== 全局任务状态栏 Gradio 组件 ====================
    _global_taskbar_state = gr.State(value="idle")

    taskbar_display = gr.HTML(value=_get_taskbar_html())
    sched_action_input = gr.Textbox(value="", visible=False, max_lines=1)

    # 注册到全局状态（供其他tabs组件使用）
    register_taskbar(taskbar_display, sched_action_input)

    return {
        "taskbar_display": taskbar_display,
        "sched_action_input": sched_action_input,
        "acquire_exec": _acquire_exec,
        "release_exec": _release_exec,
        "is_executing": _is_executing,
        "get_taskbar_html": _get_taskbar_html,
    }
