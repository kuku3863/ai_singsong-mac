import os
import urllib.request
import shutil
from pathlib import Path
import librosa
import soundfile as sf
import numpy as np

# Paths
BASE_DIR = Path("f:/Python_project/ai_singsong/so-vits-svc")
PRETRAIN_DIR = BASE_DIR / "pretrain"
LOGS_DIR = BASE_DIR / "logs/44k"
DATASET_RAW_DIR = BASE_DIR / "dataset_raw"
SPEAKER_NAME = "my_voice"
SPEAKER_DIR = DATASET_RAW_DIR / SPEAKER_NAME
SOURCE_AUDIO = Path("f:/Python_project/ai_singsong/Voice (251027.2351).mp3")

# Create dirs
print("Creating directories...")
PRETRAIN_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SPEAKER_DIR.mkdir(parents=True, exist_ok=True)

# Downloads
urls = {
    "checkpoint_best_legacy_500.pt": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt",
    "G_0.pth": "https://huggingface.co/Gaiigd/so-vits-svc-4.0-init/resolve/main/G_0.pth",
    "D_0.pth": "https://huggingface.co/Gaiigd/so-vits-svc-4.0-init/resolve/main/D_0.pth"
}

print("Downloading models...")
for name, url in urls.items():
    if name == "checkpoint_best_legacy_500.pt":
        dest = PRETRAIN_DIR / name
    else:
        dest = LOGS_DIR / name
    
    if not dest.exists():
        print(f"Downloading {name} from {url}...")
        try:
            # Add User-Agent to avoid 403 Forbidden
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            print(f"Downloaded {name}")
        except Exception as e:
            print(f"Failed to download {name}: {e}")
    else:
        print(f"{name} already exists.")

# Audio Processing
print(f"Processing audio from {SOURCE_AUDIO}...")
if not SOURCE_AUDIO.exists():
    print(f"Error: Source audio file not found at {SOURCE_AUDIO}")
else:
    try:
        # Load audio (resample to 44.1k)
        y, sr = librosa.load(str(SOURCE_AUDIO), sr=44100)
        
        # Split silence
        # top_db=30 is a reasonable default for clean speech/singing
        intervals = librosa.effects.split(y, top_db=30, frame_length=2048, hop_length=512)
        
        count = 0
        for i, (start, end) in enumerate(intervals):
            chunk = y[start:end]
            duration = len(chunk) / sr
            
            # Filter short/long segments (2s - 15s)
            if duration < 2.0:
                continue
            
            # If segment is too long, just save it (or split further? let's keep it simple for now)
            # ideally we should split >10s segments.
            
            out_name = SPEAKER_DIR / f"{SPEAKER_NAME}_{count:04d}.wav"
            sf.write(str(out_name), chunk, sr)
            count += 1
            
        print(f"Audio processing complete. Created {count} slices in {SPEAKER_DIR}")
        
    except Exception as e:
        print(f"Audio processing failed: {e}")
        import traceback
        traceback.print_exc()

print("Setup complete.")
