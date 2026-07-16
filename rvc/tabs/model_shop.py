# -*- coding: utf-8 -*-
"""model_shop tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the model_shop tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import *
from tabs.shared import _update_model_shop_cache, _get_model_shop_cache_path


def build_model_shop_tab(app):
    """Build the model_shop tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem("🎩 模型工坊", id="model_shop"):

        def _load_model_shop(force=False):
            try:
                url = _update_model_shop_cache(force=force)
                cache_path = _get_model_shop_cache_path()
                mtime_str = ""
                if os.path.exists(cache_path):
                    import time as _time

                    mtime = os.path.getmtime(cache_path)
                    mtime_str = _time.strftime(
                        "%Y-%m-%d %H:%M:%S", _time.localtime(mtime)
                    )
                    info = (
                        '<div style="display:flex;justify-content:center;align-items:center;gap:12px;margin-bottom:8px;">'
                        '<h2 style="margin:0;color:#7c3aed;font-size:1rem;">🎩 模型工坊 — RVC 模型下载中心</h2>'
                        '<span style="font-size:0.76rem;color:#64748b;background:rgba(124,58,237,0.06);padding:4px 10px;border-radius:6px;">'
                        "缓存更新: " + mtime_str + "</span></div>"
                    )
                else:
                    info = '<h2 style="margin:0;color:#7c3aed;font-size:1rem;">🎩 模型工坊 — RVC 模型下载中心</h2>'
                iframe_html = (
                    '<div style="width:100%;height:75vh;overflow:hidden;border-radius:12px;border:1px solid #e2e8f0;'
                    'box-shadow:0 4px 16px rgba(124,58,237,0.08);">'
                    '<iframe src="'
                    + url
                    + '" style="width:100%;height:100%;border:none;" '
                    'allow="autoplay;fullscreen" loading="lazy" sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>'
                    "</div>"
                )
                return info, iframe_html
            except Exception as e:
                fallback_html = (
                    '<div style="width:100%;min-height:60vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;">'
                    '<div style="max-width:500px;text-align:center;">'
                    '<div style="font-size:3rem;margin-bottom:16px;">🎩</div>'
                    '<h2 style="margin:0 0 12px 0;color:#7c3aed;">RVC 模型下载中心</h2>'
                    '<p style="color:#64748b;margin-bottom:20px;font-size:0.9rem;">正在连接远程服务器...</p>'
                    '<a href="https://mxgf.cc" target="_blank" rel="noopener noreferrer" '
                    'style="display:inline-block;padding:12px 28px;border-radius:10px;background:linear-gradient(135deg,#7c3aed,#a78bfa);'
                    'color:#fff;text-decoration:none;font-weight:600;font-size:1rem;">'
                    '🔗 打开 mxgf.cc</a>'
                    '</div></div>'
                )
                return (
                    '<h2 style="margin:0;color:#7c3aed;font-size:1rem;">🎩 模型工坊 — RVC 模型下载中心</h2>',
                    fallback_html,
                )

        with gr.Row(equal_height=True):
            with gr.Column(scale=5):
                shop_header = gr.HTML(value="")
            with gr.Column(scale=1):
                refresh_shop_btn = gr.Button(
                    "🔄 刷新缓存", variant="secondary", size="sm"
                )
        shop_iframe = gr.HTML(value="")
    
        app.load(fn=_load_model_shop, inputs=[], outputs=[shop_header, shop_iframe])
        refresh_shop_btn.click(
            fn=lambda: _load_model_shop(force=True),
            inputs=[],
            outputs=[shop_header, shop_iframe],
        )
