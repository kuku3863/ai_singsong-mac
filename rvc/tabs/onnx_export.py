# -*- coding: utf-8 -*-
"""onnx_export tab - extracted from infer-web.py"""
import gradio as gr
from tabs.shared import *


def build_onnx_export_tab():
    """Build the onnx_export tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem(i18n("📤 Onnx导出"), id="onnx"):
        with gr.Group():
            gr.Markdown("### 📤 " + i18n("导出 ONNX 模型"))
            gr.Markdown(i18n("将 RVC 模型导出为 ONNX 格式，用于跨平台部署"))

            with gr.Row():
                with gr.Column(scale=1):
                    ckpt_dir = gr.Textbox(
                        label=i18n("RVC模型路径"),
                        placeholder="model.pth",
                    )
                with gr.Column(scale=1):
                    onnx_dir = gr.Textbox(
                        label=i18n("输出路径"),
                        placeholder="model.onnx",
                    )

            with gr.Row():
                butOnnx = gr.Button(i18n("🚀 开始导出"), variant="primary")

            infoOnnx = gr.Textbox(
                label=i18n("导出信息"), lines=3, interactive=False
            )

            butOnnx.click(
                export_onnx, [ckpt_dir, onnx_dir], infoOnnx, api_name="export_onnx"
            )

