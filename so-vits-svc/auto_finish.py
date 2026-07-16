import time
import os
import glob
import subprocess
import sys

def get_latest_step():
    model_files = glob.glob("logs/44k/G_*.pth")
    if not model_files:
        return 0
    
    max_step = 0
    for f in model_files:
        try:
            step = int(f.split("_")[-1].split(".")[0])
            if step > max_step:
                max_step = step
        except:
            continue
    return max_step

def kill_training_process():
    print("Stopping training process...")
    # Use wmic to find python processes running train.py
    try:
        # Get list of python processes with command line
        cmd = 'wmic process where "name=\'python.exe\'" get commandline,processid'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        
        lines = output.strip().split('\n')
        for line in lines:
            if 'train.py' in line and 'configs/config.json' in line:
                # Extract PID (last token)
                parts = line.strip().rsplit(None, 1)
                if len(parts) == 2:
                    pid = parts[1]
                    print(f"Found training process: {pid}")
                    os.system(f"taskkill /F /PID {pid}")
                    print("Training process killed.")
                    return True
    except Exception as e:
        print(f"Error killing process: {e}")
    
    print("Training process not found or error occurred.")
    return False

def main():
    target_step = 2400
    print(f"Monitoring training... Waiting for step {target_step}...")
    
    # Wait for target step
    while True:
        current_step = get_latest_step()
        sys.stdout.write(f"\rCurrent step: {current_step}")
        sys.stdout.flush()
        
        if current_step >= target_step:
            print(f"\nTarget step {target_step} reached! (Current: {current_step})")
            kill_training_process()
            break
        
        time.sleep(10) # Check every 10 seconds

    print("\nStarting generation test...")
    # Run the real battle inference script
    cmd = "python run_real_battle.py"
    print(f"Executing: {cmd}")
    os.system(cmd)
    print("All done!")

if __name__ == "__main__":
    main()
