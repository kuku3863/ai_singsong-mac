# AI 翻唱系统

本仓库当前按 macOS 版本整理。

## 版本区分

- macOS 主线：`start.sh`、`启动 AI 翻唱.command`、`rvc/Start_RVC.command`、`rvc/install_mac.sh`、`so-vits-svc/Start_WebUI_Mac.sh`
- Windows 版本：保留为独立分支/独立仓库内容，不并入本仓库主线
- 模型占位：`models/rvc/`、`models/svc/`

## 快速开始

1. 双击 `启动 AI 翻唱.command`
2. 选择混合一体 WebUI 或独立 RVC / SVC
3. 模型放到本地 `models/` 下面对应目录

## 同步更新

- 改完代码后，双击 `同步到 GitHub.command`
- 该脚本只提交已跟踪的代码和文档
- 模型、音频、日志、缓存和训练产物都会被忽略

## 提交原则

- 不上传模型文件
- 不上传生成的歌曲和临时音频
- 不上传隐私数据、日志、缓存和训练产物
