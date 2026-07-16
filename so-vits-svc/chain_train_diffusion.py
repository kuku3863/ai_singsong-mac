import os
import time
import subprocess
import glob
import sys

def get_latest_step(project_name):
    """获取指定项目的最新训练步数"""
    model_dir = f"logs/{project_name}/diffusion"
    if not os.path.exists(model_dir):
        return 0
    
    model_files = glob.glob(f"{model_dir}/model_*.pt")
    if not model_files:
        return 0
    
    max_step = 0
    for f in model_files:
        try:
            basename = os.path.basename(f)
            step_str = basename.replace("model_", "").replace(".pt", "")
            step = int(step_str)
            if step > max_step:
                max_step = step
        except Exception:
            continue
    return max_step

def is_process_running(command_substring):
    """检查是否有包含特定字符串的进程在运行"""
    try:
        output = subprocess.check_output('wmic process get commandline', shell=True).decode('utf-8', errors='ignore')
        return command_substring in output
    except Exception:
        return False

def start_training(project_name):
    """启动指定项目的训练并返回进程对象"""
    python_exe = sys.executable
    config_path = f"configs/{project_name}_diffusion.yaml"
    
    if not os.path.exists(config_path):
        print(f"\n[Error] 找不到配置文件: {config_path}")
        return None

    print("\n" + "="*50)
    print(f"正在启动 {project_name} 的扩散训练...")
    print("="*50)
    
    cmd = [python_exe, "train_diff.py", "-c", config_path]
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 使用 Popen 启动，并让它在后台运行
        p = subprocess.Popen(cmd)
        return p
    except Exception as e:
        print(f"\n[Error] 启动 {project_name} 训练失败: {e}")
        return None

def monitor_and_restart(project_name, target_step=100000):
    """监控并自动重启训练直到达到目标步数"""
    print(f"\n开始自动化监控与维护 {project_name} 的训练任务...")
    
    while True:
        current_step = get_latest_step(project_name)
        running = is_process_running(f"{project_name}_diffusion.yaml")
        
        if current_step >= target_step:
            if running:
                print(f"\n[Info] {project_name} 已达到目标步数 {target_step}，正在等待进程自然结束...")
                time.sleep(30)
                continue
            else:
                print(f"\n[Success] {project_name} 训练已圆满完成 (最终步数: {current_step})")
                break
        
        if not running:
            print(f"\n[Warning] 检测到 {project_name} 训练进程异常停止 (当前步数: {current_step})，正在尝试重启...")
            start_training(project_name)
            time.sleep(10) # 给进程一点启动时间
            continue
        
        sys.stdout.write(f"\r[{project_name}] 进度: {current_step}/{target_step} | 状态: 🚀 正在高速训练中...")
        sys.stdout.flush()
        
        time.sleep(30)

def main():
    target_step = 100000
    
    # 按顺序执行链式任务
    for project in ["rongrong", "qingyi", "tian"]:
        monitor_and_restart(project, target_step)

    print("\n" + "="*50)
    print("🎉 所有扩散训练链式任务已全部完成！")
    print("="*50)

if __name__ == "__main__":
    main()
