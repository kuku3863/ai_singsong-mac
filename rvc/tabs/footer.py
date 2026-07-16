# -*- coding: utf-8 -*-
"""Footer HTML (inside gr.Blocks) and startup code (after gr.Blocks)."""
from tabs.shared import *
from tabs.shared import _BOLD, _RESET, _STATUS_STYLES, _AI_OUTPUT_ROOT, _install_recursion_guard


def build_footer():
    """Build footer elements inside gr.Blocks context."""
    # 底部版权信息
    gr.HTML("""
    <style>
        .promo-section {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(5, 150, 105, 0.06));
            border-radius: 16px;
            padding: 25px;
            margin: 20px 0;
            border: 1px solid rgba(16, 185, 129, 0.2);
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.08);
            animation: fadeInUp 1.2s ease-out;
        }

        .promo-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            gap: 12px;
        }

        .promo-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #10b981, #34d399);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }

        .promo-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #059669;
            margin: 0;
        }

        .promo-content {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }

        .promo-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }

        .promo-card:hover {
            transform: translateY(-2px);
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.12);
        }

        .promo-card-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #059669;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .promo-card-text {
            font-size: 0.95rem;
            color: #6b7280;
            line-height: 1.6;
            margin-bottom: 12px;
        }

        .promo-stats {
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stat-item {
            text-align: center;
        }

        .stat-number {
            font-size: 2rem;
            font-weight: 700;
            color: #10b981;
            display: block;
        }

        .stat-label {
            font-size: 0.85rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .promo-cta {
            text-align: center;
            margin-top: 25px;
        }

        .promo-btn {
            background: linear-gradient(135deg, #10b981, #34d399);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        }

        .promo-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
            background: linear-gradient(135deg, #059669, #10b981);
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .feature-item {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #10b981;
            transition: all 0.3s ease;
        }

        .feature-item:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(5px);
        }

        .feature-icon {
            width: 20px;
            height: 20px;
            background: #10b981;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            margin-right: 8px;
            font-weight: bold;
        }

        .feature-text {
            display: inline;
            font-weight: 500;
            color: #d1d5db;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @media (max-width: 768px) {
            .promo-content {
                grid-template-columns: 1fr;
            }
            .promo-stats {
                flex-direction: column;
                gap: 15px;
            }
        }
    </style>

    <!-- 模型工坊推广模块 -->
    <div class="promo-section">
        <div class="promo-header">
            <div class="promo-icon">🎯</div>
            <h2 class="promo-title">模型工坊 mxgf.cc</h2>
        </div>

        <div class="promo-content">
            <div class="promo-card">
                <div class="promo-card-title">
                    <span class="feature-icon">🏆</span>
                    全网最全 RVC 音色模型库
                </div>
                <p class="promo-card-text">
                    超 600 款 RVC/SVC 模型，涵盖动漫、游戏、影视明星等多类型角色音色。
                    48k 全音域模型，支持高质量 AI 翻唱和实时变声需求。
                </p>
            </div>

            <div class="promo-card">
                <div class="promo-card-title">
                    <span class="feature-icon">📚</span>
                    专业学习资源平台
                </div>
                <p class="promo-card-text">
                    网站排版清晰易读，提供详细的模型使用教学视频和图文教程。
                    支持免费学习基础知识，付费解锁高级模型和独家资源。
                </p>
            </div>

            <div class="promo-card">
                <div class="promo-card-title">
                    <span class="feature-icon">⚡</span>
                    及时更新 • 质量保障
                </div>
                <p class="promo-card-text">
                    资源更新及时，严格的质量控制体系，确保每个模型都经过测试验证。
                    部分模型免费下载，大部分付费模型提供试听和预览功能。
                </p>
            </div>
        </div>

        <!-- 核心优势展示 -->
        <div class="feature-grid">
            <div class="feature-item">
                <span class="feature-icon">🎮</span>
                <span class="feature-text">游戏角色音色</span>
            </div>
            <div class="feature-item">
                <span class="feature-icon">🎬</span>
                <span class="feature-text">影视明星配音</span>
            </div>
            <div class="feature-item">
                <span class="feature-icon">🎤</span>
                <span class="feature-text">专业歌手音色</span>
            </div>
            <div class="feature-item">
                <span class="feature-icon">🎵</span>
                <span class="feature-text">48k 高质量模型</span>
            </div>
            <div class="feature-item">
                <span class="feature-icon">🤖</span>
                <span class="feature-text">AI 实时变声</span>
            </div>
            <div class="feature-item">
                <span class="feature-icon">🎨</span>
                <span class="feature-text">创意音乐制作</span>
            </div>
        </div>

        <!-- 数据统计 -->
        <div class="promo-stats">
            <div class="stat-item">
                <span class="stat-number">600+</span>
                <span class="stat-label">优质模型</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">48kHz</span>
                <span class="stat-label">全音域支持</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">7×24</span>
                <span class="stat-label">及时更新</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">100%</span>
                <span class="stat-label">质量保障</span>
            </div>
        </div>

        <!-- 行动号召 -->
        <div class="promo-cta">
            <a href="https://mxgf.cc" target="_blank" class="promo-btn">
                🚀 立即访问模型工坊
            </a>
            <p style="margin-top: 15px; color: #6b7280; font-size: 0.9rem;">
                探索更多音色 • 学习专业技巧 • 开启 AI 音乐创作之旅
            </p>
        </div>
    </div>

    <!-- 底部版权信息 -->
    <div style="text-align: center; margin-top: 40px; padding: 20px; 
                background: rgba(0, 0, 0, 0.05); border-radius: 10px; color: #6b7280;">
        <p>© 2026 RVC 音色转换工具 | 技术支持：模型工坊 mxgf.cc | 微信：xiaoming1870
           专业 AI 语音解决方案提供商</p>
        <div style="margin-top: 15px; padding: 15px; background: rgba(16, 185, 129, 0.05); border-radius: 8px; text-align: left; font-size: 0.85rem;">
            <h4 style="margin: 0 0 10px 0; color: #059669;">MIT协议暨相关引用库协议</h4>
            <p style="margin: 5px 0; line-height: 1.6;">
                <strong>MIT License:</strong> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
            </p>
            <p style="margin: 10px 0 5px 0; color: #475569;">
                <strong>相关依赖库:</strong> PyTorch, Gradio, FAISS, Fairseq, NumPy, SciPy 等开源库
            </p>
        </div>
    </div>
    """)

    # 注入音频播放器美化样式
    gr.HTML("""
    <style>
    /* ====== Gradio 音频组件美化 ====== */
    .gr-audio, .gradio-audio, [data-testid="audio"] {
    background: linear-gradient(145deg, #fefeff 0%, #f8f4ff 30%, #f3e8ff 70%, #ede9fe 100%) !important;
    border: 2px solid rgba(139, 92, 246, 0.25) !important;
    border-radius: 20px !important;
    padding: 12px 16px !important;
    box-shadow:
        0 4px 24px rgba(139, 92, 246, 0.12),
        0 1px 3px rgba(0,0,0,0.04),
        inset 0 2px 0 rgba(255,255,255,0.95),
        inset 0 -1px 0 rgba(139,92,246,0.05) !important;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative !important;
    overflow: hidden !important;
    }

    /* 背景光效 */
    .gr-audio::after, .gradio-audio::after, [data-testid="audio"]::after {
    content: '' !important;
    position: absolute !important;
    top: -50% !important;
    left: -50% !important;
    width: 200% !important;
    height: 200% !important;
    background: radial-gradient(circle at 30% 30%, rgba(167,139,250,0.08) 0%, transparent 50%) !important;
    pointer-events: none !important;
    animation: audioGlow 4s ease-in-out infinite alternate !important;
    }

    @keyframes audioGlow {
    0% { opacity: 0.5; transform: translate(0, 0); }
    100% { opacity: 1; transform: translate(5%, 5%); }
    }

    .gr-audio:hover, .gradio-audio:hover, [data-testid="audio"]:hover {
    border-color: rgba(139, 92, 246, 0.45) !important;
    box-shadow:
        0 8px 36px rgba(139, 92, 246, 0.18),
        0 3px 10px rgba(0,0,0,0.06),
        inset 0 2px 0 rgba(255,255,255,0.95) !important;
    transform: translateY(-2px);
    }

    /* 顶部流光线 */
    .gr-audio::before, .gradio-audio::before, [data-testid="audio"]::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 4px !important;
    background: linear-gradient(90deg,
        transparent 0%,
        #7c3aed 15%,
        #a78bfa 30%,
        #c4b5fd 50%,
        #a78bfa 70%,
        #7c3aed 85%,
        transparent 100%) !important;
    background-size: 200% 100% !important;
    animation: audioShine 2.5s linear infinite !important;
    border-radius: 20px 20px 0 0 !important;
    opacity: 0.9 !important;
    }

    @keyframes audioShine {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
    }

    /* audio 元素 */
    .gr-audio audio, .gradio-audio audio, [data-testid="audio"] audio {
    width: 100% !important;
    height: 50px !important;
    border-radius: 12px !important;
    position: relative !important;
    z-index: 1 !important;
    }

    /* 控制面板 */
    audio::-webkit-media-controls-panel {
    background: linear-gradient(180deg,
        rgba(255,255,255,0.95) 0%,
        rgba(250,245,255,0.92) 50%,
        rgba(245,240,255,0.9) 100%) !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 10px !important;
    padding: 6px 10px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.8) !important;
    }

    /* 播放按钮 */
    audio::-webkit-media-controls-play-button {
    background: linear-gradient(145deg, #a78bfa, #7c3aed) !important;
    border-radius: 50% !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(124,58,237,0.35), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transition: all 0.2s ease !important;
    transform: scale(1) !important;
    }

    audio::-webkit-media-controls-play-button:hover {
    background: linear-gradient(145deg, #8b5cf6, #6d28d9) !important;
    box-shadow: 0 3px 12px rgba(124,58,237,0.45), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transform: scale(1.08) !important;
    }

    audio::-webkit-media-controls-play-button:active {
    transform: scale(0.95) !important;
    }

    /* 时间显示 */
    audio::-webkit-media-controls-current-time-display,
    audio::-webkit-media-controls-time-remaining-display {
    color: #6d28d9 !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    font-family: 'SF Mono', 'Consolas', monospace !important;
    text-shadow: 0 0 1px rgba(109,40,217,0.15) !important;
    letter-spacing: 0.5px !important;
    }

    /* 进度条 */
    audio::-webkit-media-controls-timeline {
    background: linear-gradient(90deg,
        rgba(139,92,246,0.12) 0%,
        rgba(167,139,250,0.18) 50%,
        rgba(139,92,246,0.12) 100%) !important;
    border-radius: 6px !important;
    height: 6px !important;
    border: 1px solid rgba(139,92,246,0.1) !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    }

    audio::-webkit-media-controls-timeline:hover {
    height: 8px !important;
    background: linear-gradient(90deg,
        rgba(139,92,246,0.18) 0%,
        rgba(167,139,250,0.25) 50%,
        rgba(139,92,246,0.18) 100%) !important;
    }

    /* 音量滑块 */
    audio::-webkit-media-controls-volume-slider {
    background: linear-gradient(90deg, #ede9fe, #c4b5fd, #a78bfa) !important;
    border-radius: 4px !important;
    height: 5px !important;
    }

    audio::-webkit-media-controls-volume-slider::-webkit-slider-thumb {
    background: #7c3aed !important;
    }

    /* 静音按钮 */
    audio::-webkit-media-controls-mute-button {
    filter: hue-rotate(260deg) saturate(1.2) !important;
    opacity: 0.85 !important;
    transition: all 0.2s ease !important;
    }

    audio::-webkit-media-controls-mute-button:hover {
    opacity: 1 !important;
    transform: scale(1.1) !important;
    }

    /* 隐藏下载按钮 */
    audio::-internal-media-controls-download-button,
    audio::-webkit-media-controls-download-button,
    audio::-webkit-media-controls-fullscreen-button {
    display: none !important;
    }

    /* Gradio 内部容器 */
    .gr-audio .wrap, .gradio-audio .wrap,
    .gr-audio .audio-container, .gradio-audio .audio-container {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    }

    /* 播放中状态动画 */
    .gr-audio:has(audio:not([paused]))::before,
    .gradio-audio:has(audio:not([paused]))::before {
    animation: audioShine 1.5s linear infinite !important;
    }
    </style>
    """)



def launch_app(app):
    """Startup and launch the Gradio app. Called after gr.Blocks context exits."""
    # 打印启动横幅
    print_banner()

    # 检测可用端口
    print_status("🔍 正在检测可用端口...", "info")
    target_port = config.listen_port
    free_port = get_free_port(target_port)

    if free_port is None:
        print_status("💥 没有可用的端口，程序无法启动！", "error")
        sys.exit(1)

    if free_port != target_port:
        print_status(
            f"⚠️  端口 {target_port} 已被占用，自动切换到端口 {free_port}", "warning"
        )
    else:
        print_status(f"✅ 端口 {target_port} 就绪，一切正常", "success")

    # 打印系统信息
    print()
    print(f"  {_BOLD}{_STATUS_STYLES['purple']['color']}{'═' * 56}{_RESET}")
    print(
        f"  {_BOLD}{_STATUS_STYLES['purple']['color']}🚀 AI 翻唱音色替换系统 启动中...{_RESET}"
    )
    print(f"  {_BOLD}{_STATUS_STYLES['purple']['color']}{'═' * 56}{_RESET}")
    print()
    print_status(f"📂 工作目录: {now_dir}", "info")
    print_status(f"🐍 Python 版本: {sys.version.split()[0]}", "info")

    import torch as _torch

    gpu_info = ""
    if _torch.cuda.is_available():
        gpu_name = _torch.cuda.get_device_name(0)
        gpu_mem = _torch.cuda.get_device_properties(0).total_memory / (1024**3)
        gpu_info = f" ({gpu_name}, {gpu_mem:.1f}GB)"
        print_status(f"🎮 GPU 加载成功{gpu_info}", "success")
    else:
        print_status(
            "💻 当前使用 CPU 模式运行（建议使用 GPU 以获得更好性能）", "warning"
        )

    print_status("🔗 模型工坊优化版 - https://mxgf.cc", "purple")
    print_status("🎨 百款动漫游戏声音模型等你下载体验", "info")
    print()

    init_ai_output_structure()

    _download_allowed_dirs = [
        now_dir,
        os.path.join(now_dir, "TEMP"),
        _AI_OUTPUT_ROOT,
        os.path.join(now_dir, "assets"),
        os.path.join(now_dir, "logs"),
        os.path.join(now_dir, "AI批量转换目录"),
    ]
    _download_allowed_dirs = [
        os.path.abspath(d) for d in _download_allowed_dirs if os.path.isdir(d)
    ]
    print_status(
        f"📁 文件下载权限已配置（{len(_download_allowed_dirs)} 个目录）", "info"
    )

    print_status("✅ 下载服务就绪（使用 Gradio 内置文件端点）", "success")

    _install_recursion_guard()

    if config.iscolab:
        app.queue(concurrency_count=511, max_size=1022).launch(share=True)
    else:
        print()
        print(f"  {_BOLD}\033[38;5;82m{'─' * 56}{_RESET}")
        print(
            f"  {_BOLD}\033[38;5;82m🌐 正在启动 Web UI 服务... 端口: {free_port}{_RESET}"
        )
        print(f"  {_BOLD}\033[38;5;82m{'─' * 56}{_RESET}")
        print_status("🌍 浏览器将自动打开，请稍候...", "info")

        try:
            app.queue(concurrency_count=511, max_size=1022).launch(
                server_name="127.0.0.1",
                inbrowser=not config.noautoopen,
                server_port=free_port,
                quiet=False,
            )
        except Exception as e:
            print_status(f"💥 启动失败: {str(e)}", "error")
            print_status("🔄 正在尝试其他可用端口...", "warning")
            free_port = get_free_port(free_port + 1)
            if free_port:
                print_status(f"🔁 切换到端口 {free_port} 重新启动...", "info")
                app.queue(concurrency_count=511, max_size=1022).launch(
                    server_name="127.0.0.1",
                    inbrowser=not config.noautoopen,
                    server_port=free_port,
                    quiet=False,
                )
