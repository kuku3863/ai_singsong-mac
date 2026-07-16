
import subprocess
import os
import time

models = [
    {
        "url": "https://hf-mirror.com/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\pretrain\checkpoint_best_legacy_500.pt",
        "name": "ContentVec"
    },
    {
        "url": "https://hf-mirror.com/Himawari00/so-vits-svc4.0-pretrain-models/resolve/main/G_0.pth",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\logs\44k\G_0.pth",
        "name": "G_0.pth"
    },
    {
        "url": "https://hf-mirror.com/Himawari00/so-vits-svc4.0-pretrain-models/resolve/main/D_0.pth",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\logs\44k\D_0.pth",
        "name": "D_0.pth"
    },
    {
        "url": "https://hf-mirror.com/NaruseMioShirakana/MoeSS-SUBModel/resolve/main/vec-768-layer-12.onnx",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\pretrain\vec-768-layer-12.onnx",
        "name": "ContentVec ONNX"
    },
    {
        "url": "https://hf-mirror.com/datasets/ylzz1997/rmvpe_pretrain_model/resolve/main/rmvpe.pt",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\pretrain\rmvpe.pt",
        "name": "RMVPE"
    },
    {
        "url": "https://hf-mirror.com/datasets/ylzz1997/rmvpe_pretrain_model/resolve/main/fcpe.pt",
        "path": r"f:\Python_project\ai_singsong\so-vits-svc\pretrain\fcpe.pt",
        "name": "FCPE"
    }
]

def download_with_resume(url, path, name):
    print(f"Starting/Resuming download of {name}...")
    
    # Check if file exists and is too small (likely corrupted or just a placeholder)
    if os.path.exists(path):
        file_size = os.path.getsize(path)
        if file_size < 1000:  # If less than 1KB, it's probably a failed download or error page
            print(f"File {path} is too small ({file_size} bytes), deleting and restarting...")
            os.remove(path)

    while True:
        try:
            # -L follow redirects, -k insecure, -C - resume, -o output
            # Using basic subprocess to avoid version issues
            cmd = ["curl.exe", "-LkC", "-", url, "-o", path]
            process = subprocess.Popen(cmd)
            process.wait()
            
            if process.returncode == 0:
                # Verify final size is reasonable (most models are > 1MB)
                if os.path.exists(path) and os.path.getsize(path) > 1000:
                    print(f"Successfully finished downloading {name}.")
                    break
                else:
                    print(f"Download of {name} finished but file is too small. Retrying...")
                    if os.path.exists(path): os.remove(path)
            else:
                print(f"Download of {name} interrupted (code {process.returncode}). Retrying in 5 seconds...")
                time.sleep(5)
        except Exception as e:
            print(f"Error downloading {name}: {e}. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(r"f:\Python_project\ai_singsong\so-vits-svc\pretrain", exist_ok=True)
    os.makedirs(r"f:\Python_project\ai_singsong\so-vits-svc\logs\44k", exist_ok=True)
    
    for model in models:
        download_with_resume(model["url"], model["path"], model["name"])
