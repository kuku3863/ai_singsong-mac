# -*- coding: utf-8 -*-
"""music_unlock tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the music_unlock tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import *


def build_music_unlock_tab():
    """Build the music_unlock tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem("🔓 歌曲解码", id="music_unlock"):
        gr.HTML("""
        <div style="margin-bottom:12px;">
            <div style="font-size:0.9rem;color:#fff;background:linear-gradient(135deg,#7c3aed,#a78bfa);margin:0;padding:14px 16px;border-radius:12px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:1.3rem;">🔓</span>
                <span style="font-weight:700;font-size:1rem;">歌曲解码</span>
                <span style="font-size:0.78rem;opacity:0.85;">在线解码各平台加密音乐文件</span>
            </div>
        </div>""")
    
        gr.HTML("""
        <div id="unlock_container" style="border-radius:12px;overflow:hidden;border:1px solid rgba(124,58,237,0.3);background:#1a0a2e;position:relative;color-scheme:light dark;">
            <div id="unlock_banner" style="position:absolute;top:0;left:0;right:0;z-index:10;padding:6px 12px;background:rgba(26,10,46,0.92);border-bottom:1px solid rgba(124,58,237,0.3);display:flex;align-items:center;justify-content:space-between;gap:8px;backdrop-filter:blur(8px);">
                <span style="font-size:0.7rem;color:#c4b5fd;">🎵 支持: 网易云(ncm) · QQ音乐(qmc/mgg) · 酷狗(kgm) · 虾米(xm) · 酷我(kwm)</span>
                <button onclick="document.getElementById('unlock_banner').style.display='none';document.getElementById('unlock_iframe').style.height='calc(100vh - 280px)';" style="background:rgba(124,58,237,0.3);border:1px solid rgba(124,58,237,0.5);color:#a78bfa;border-radius:50%;width:22px;height:22px;cursor:pointer;font-size:0.7rem;line-height:1;padding:0;display:flex;align-items:center;justify-content:center;">×</button>
            </div>
            <iframe
                id="unlock_iframe"
                src="https://m.starkettle.com/"
                width="100%"
                height="680"
                style="border:none;display:block;border-radius:12px;"
                loading="lazy"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
            ></iframe>
        </div>
        <div style="margin-top:10px;padding:12px 16px;border-radius:12px;background:rgba(239,68,68,0.05);border:1px solid rgba(249,115,22,0.25);font-size:0.88rem;color:#d4a574;">
            <div style="font-weight:700;margin-bottom:8px;font-size:1rem;color:#fbbf24;">⚠️ 格式转换说明</div>
            <div style="margin-bottom:6px;">• <b style="color:#fb923c;">.mgg .mflac .kgg .kgma</b> 格式转换失败 → 降级安装旧版后可转换</div>
            <div style="margin-bottom:6px;">• <b style="color:#fb923c;">QQ音乐</b> 降级版【<a href="https://www.123865.com/s/6a0Bjv-rZ6zv" target="_blank" style="color:#f97316;">点此下载 1951版</a>】</div>
            <div style="margin-bottom:6px;">• <b style="color:#fb923c;">酷狗音乐</b> 降级版【<a href="https://www.123865.com/s/6a0Bjv-8Z6zv" target="_blank" style="color:#f97316;">点此下载 10.250版</a>】</div>
            <div style="margin-bottom:6px;">• <b style="color:#fb923c;">.ncm</b> 部分失败 → 将网易云音乐更新至最新版，重新下载歌曲后重试</div>
            <div>• <b style="color:#fb923c;">mflac</b> 转码后为 .flac 格式（非 MP3），属正常行为</div>
        </div>
        <div style="margin-top:8px;padding:8px 12px;border-radius:8px;background:rgba(124,58,237,0.06);border-left:3px solid #a78bfa;font-size:0.75rem;color:#c4b5fd;text-align:center;">
            💡 如果页面无法加载，请访问 <a href="https://m.starkettle.com/" target="_blank" style="color:#a78bfa;">m.starkettle.com</a> 手动打开
        </div>
        """)
    
    # ==================== 模型训练 Tab ====================
    
