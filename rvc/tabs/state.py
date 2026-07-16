# -*- coding: utf-8 -*-
"""
Global State Manager - 跨Tabs组件共享状态
解决组件间依赖注入和作用域问题
"""
import threading

# Gradio组件引用（由header.py注册）
taskbar_display = None
sched_action_input = None

# 任务完成状态追踪
_completed_count = 0
_last_completed_info = ""
_completed_lock = threading.Lock()


def register_taskbar(display_component, action_input):
    """注册任务栏组件到全局状态（在build_header()中调用）"""
    global taskbar_display, sched_action_input
    taskbar_display = display_component
    sched_action_input = action_input


def get_taskbar():
    """获取已注册的任务栏组件"""
    if taskbar_display is None:
        raise RuntimeError("taskbar_display未初始化！请确保在调用tabs组件前先调用build_header()")
    return taskbar_display, sched_action_input


def mark_task_completed(task_name="", count=1):
    """标记任务完成，更新全局完成计数"""
    global _completed_count, _last_completed_info
    with _completed_lock:
        _completed_count += count
        _last_completed_info = task_name or f"{count}个任务"


def get_completed_state():
    """获取当前完成状态 (count, info)"""
    with _completed_lock:
        return _completed_count, _last_completed_info


def reset_completed_state():
    """重置完成状态（读取后调用）"""
    global _completed_count, _last_completed_info
    with _completed_lock:
        c, i = _completed_count, _last_completed_info
        _completed_count = 0
        _last_completed_info = ""
        return c, i
