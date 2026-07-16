import os
import shutil
from pathlib import Path
from huggingface_hub import hf_hub_download

# Paths
BASE_DIR = Path("f:/Python_project/ai_singsong/so-vits-svc")
PRETRAIN_DIR = BASE_DIR / "pretrain"
LOGS_DIR = BASE_DIR / "logs/44k"

# Create dirs
PRETRAIN_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def download_file(repo_id, filename, target_path):
    print(f"Downloading {filename} from {repo_id}...")
    try:
        file_path = hf_hub_download(repo_id=repo_id, filename=filename)
        shutil.copy(file_path, target_path)
        print(f"Success: Copied to {target_path}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")

# ContentVec
target_contentvec = PRETRAIN_DIR / "checkpoint_best_legacy_500.pt"
if not target_contentvec.exists():
    download_file(
        repo_id="lj1995/VoiceConversionWebUI",
        filename="hubert_base.pt",
        target_path=target_contentvec
    )
else:
    print("ContentVec already exists.")

# G_0
target_g = LOGS_DIR / "G_0.pth"
if not target_g.exists():
    download_file(
        repo_id="Gaiigd/so-vits-svc-4.0-init",
        filename="G_0.pth",
        target_path=target_g
    )
else:
    print("G_0 already exists.")

# D_0
target_d = LOGS_DIR / "D_0.pth"
if not target_d.exists():
    download_file(
        repo_id="Gaiigd/so-vits-svc-4.0-init",
        filename="D_0.pth",
        target_path=target_d
    )
else:
    print("D_0 already exists.")
