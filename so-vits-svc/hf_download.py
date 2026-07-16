
from huggingface_hub import hf_hub_download
import os

models = [
    {
        "repo_id": "Himawari00/so-vits-svc4.0-pretrain-models",
        "filename": "G_0.pth",
        "local_dir": "logs/44k",
        "local_filename": "G_0.pth"
    },
    {
        "repo_id": "Himawari00/so-vits-svc4.0-pretrain-models",
        "filename": "D_0.pth",
        "local_dir": "logs/44k",
        "local_filename": "D_0.pth"
    }
]

# Set mirror
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

for m in models:
    print(f"Downloading {m['filename']}...")
    try:
        path = hf_hub_download(
            repo_id=m['repo_id'],
            filename=m['filename'],
            local_dir=m['local_dir'],
            local_dir_use_symlinks=False
        )
        # Rename if needed
        target_path = os.path.join(m['local_dir'], m['local_filename'])
        if os.path.exists(path) and path != target_path:
            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(path, target_path)
        print(f"Successfully downloaded to {target_path}")
    except Exception as e:
        print(f"Failed to download {m['filename']}: {e}")
