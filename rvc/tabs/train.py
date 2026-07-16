# -*- coding: utf-8 -*-
"""train tab - extracted from infer-web.py"""
# This file contains the UI definition and event handlers for the train tab.
# All functions defined here use globals from tabs.shared module.
import gradio as gr
from tabs.shared import *
from tabs.pressure_test import start_pressure_test


def build_train_tab():
    """Build the train tab UI. Called inside `with gr.Blocks()` and `with gr.Tabs()` context."""
    with gr.TabItem(i18n("🔧 模型训练"), id="train"):
        gr.Markdown("### 🔧 " + i18n("模型训练"))
    
        # 基础配置
        with gr.Group():
            gr.Markdown("#### 📋 " + i18n("实验配置"))
            with gr.Row():
                with gr.Column(scale=1):
                    exp_dir1 = gr.Textbox(
                        label=i18n("实验名称"),
                        value="mi-test",
                        info=i18n("实验数据放在logs下"),
                    )
                with gr.Column(scale=1):
                    sr2 = gr.Radio(
                        label=i18n("目标采样率"),
                        choices=["40k", "48k"],
                        value="40k",
                    )
                with gr.Column(scale=1):
                    version19 = gr.Radio(
                        label=i18n("模型版本"),
                        choices=["v1", "v2"],
                        value="v2",
                    )
    
            with gr.Row():
                with gr.Column(scale=1):
                    if_f0_3 = gr.Radio(
                        label=i18n("音高指导"),
                        choices=[True, False],
                        value=True,
                        info=i18n("唱歌需要开启"),
                    )
                with gr.Column(scale=1):
                    np7 = gr.Slider(
                        minimum=1,
                        maximum=get_config().n_cpu,
                        step=1,
                        label=i18n("CPU进程数"),
                        value=int(np.ceil(get_config().n_cpu / 1.5)),
                    )
                with gr.Column(scale=1):
                    spk_id5 = gr.Slider(
                        minimum=0,
                        maximum=4,
                        step=1,
                        label=i18n("说话人ID"),
                        value=0,
                    )
    
        # 数据预处理
        with gr.Group():
            gr.Markdown("#### 📂 " + i18n("Step 1: 数据预处理"))
            gr.Markdown(i18n("自动遍历训练文件夹下的音频文件并进行切片归一化"))
            with gr.Row():
                with gr.Column(scale=3):
                    trainset_dir4 = gr.Textbox(
                        label=i18n("训练数据文件夹"),
                        placeholder=i18n("E:\\audio\\singer"),
                    )
                with gr.Column(scale=1):
                    but1 = gr.Button(i18n("🚀 开始处理"), variant="primary")
    
            info1 = gr.Textbox(label=i18n("处理日志"), lines=3, interactive=False)
    
            but1.click(
                preprocess_dataset,
                [trainset_dir4, exp_dir1, sr2, np7],
                [info1],
                api_name="train_preprocess",
            )
    
        # 特征提取
        with gr.Group():
            gr.Markdown("#### 🎯 " + i18n("Step 2: 特征提取"))
            with gr.Row():
                with gr.Column(scale=1):
                    f0method8 = gr.Radio(
                        label=i18n("音高提取算法"),
                        choices=["pm", "harvest", "dio", "rmvpe", "rmvpe_gpu"],
                        value="rmvpe_gpu",
                    )
                with gr.Column(scale=1, visible=F0GPUVisible):
                    gpus6 = gr.Textbox(
                        label=i18n("GPU卡号"), value=gpus, info="0-1-2 使用多卡"
                    )
                with gr.Column(scale=1, visible=F0GPUVisible):
                    gpus_rmvpe = gr.Textbox(
                        label=i18n("RMVPE GPU配置"),
                        value="%s-%s" % (gpus, gpus),
                    )
    
                f0method8.change(
                    fn=change_f0_method,
                    inputs=[f0method8],
                    outputs=[gpus_rmvpe],
                )
    
            with gr.Row(visible=F0GPUVisible):
                gpu_info9 = gr.Textbox(
                    label=i18n("显卡信息"), value=gpu_info, interactive=False
                )
    
            with gr.Row():
                but2 = gr.Button(i18n("🚀 开始提取"), variant="primary")
    
            info2 = gr.Textbox(label=i18n("提取日志"), lines=5, interactive=False)
    
            but2.click(
                extract_f0_feature,
                [gpus6, np7, f0method8, if_f0_3, exp_dir1, version19, gpus_rmvpe],
                [info2],
                api_name="train_extract_f0_feature",
            )
    
        # 模型训练
        with gr.Group():
            gr.Markdown("#### ⚙️ " + i18n("Step 3: 训练设置"))
            with gr.Row():
                with gr.Column(scale=1):
                    save_epoch10 = gr.Slider(
                        minimum=1,
                        maximum=50,
                        step=1,
                        label=i18n("保存频率"),
                        value=5,
                    )
                with gr.Column(scale=1):
                    total_epoch11 = gr.Slider(
                        minimum=2,
                        maximum=1000,
                        step=1,
                        label=i18n("总训练轮数"),
                        value=20,
                    )
                with gr.Column(scale=1):
                    batch_size12 = gr.Slider(
                        minimum=1,
                        maximum=40,
                        step=1,
                        label=i18n("Batch Size"),
                        value=default_batch_size,
                    )
    
            with gr.Row():
                with gr.Column(scale=1):
                    if_save_latest13 = gr.Radio(
                        label=i18n("仅保存最新"),
                        choices=[i18n("是"), i18n("否")],
                        value=i18n("否"),
                    )
                with gr.Column(scale=1):
                    if_cache_gpu17 = gr.Radio(
                        label=i18n("缓存到显存"),
                        choices=[i18n("是"), i18n("否")],
                        value=i18n("否"),
                        info=i18n("小数据可加速"),
                    )
                with gr.Column(scale=1):
                    if_save_every_weights18 = gr.Radio(
                        label=i18n("保存中间权重"),
                        choices=[i18n("是"), i18n("否")],
                        value=i18n("否"),
                    )
    
            with gr.Row():
                pretrained_G14 = gr.Textbox(
                    label=i18n("预训练底模G"),
                    value="assets/pretrained_v2/f0G40k.pth",
                )
                pretrained_D15 = gr.Textbox(
                    label=i18n("预训练底模D"),
                    value="assets/pretrained_v2/f0D40k.pth",
                )
                gpus16 = gr.Textbox(
                    label=i18n("GPU卡号"),
                    value=gpus,
                )
    
            # 联动更新
            sr2.change(
                change_sr2,
                [sr2, if_f0_3, version19],
                [pretrained_G14, pretrained_D15],
            )
            version19.change(
                change_version19,
                [sr2, if_f0_3, version19],
                [pretrained_G14, pretrained_D15, sr2],
            )
            if_f0_3.change(
                change_f0,
                [if_f0_3, sr2, version19],
                [f0method8, gpus_rmvpe, pretrained_G14, pretrained_D15],
            )
    
            with gr.Row():
                but3 = gr.Button(i18n("🎓 训练模型"), variant="primary")
                but4 = gr.Button(i18n("📇 训练索引"), variant="secondary")
                but5 = gr.Button(i18n("🚀 一键训练"), variant="primary")
    
            info3 = gr.Textbox(label=i18n("训练日志"), lines=8, interactive=False)
    
            but3.click(
                click_train,
                [
                    exp_dir1,
                    sr2,
                    if_f0_3,
                    spk_id5,
                    save_epoch10,
                    total_epoch11,
                    batch_size12,
                    if_save_latest13,
                    pretrained_G14,
                    pretrained_D15,
                    gpus16,
                    if_cache_gpu17,
                    if_save_every_weights18,
                    version19,
                ],
                info3,
                api_name="train_start",
            )
            but4.click(train_index, [exp_dir1, version19], info3)
            but5.click(
                train1key,
                [
                    exp_dir1,
                    sr2,
                    if_f0_3,
                    trainset_dir4,
                    spk_id5,
                    np7,
                    f0method8,
                    save_epoch10,
                    total_epoch11,
                    batch_size12,
                    if_save_latest13,
                    pretrained_G14,
                    pretrained_D15,
                    gpus16,
                    if_cache_gpu17,
                    if_save_every_weights18,
                    version19,
                    gpus_rmvpe,
                ],
                info3,
                api_name="train_start_all",
            )
    
    # ==================== 模型处理 Tab ====================
    
