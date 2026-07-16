import os
import argparse
import soundfile
import librosa
import numpy as np
from pydub import AudioSegment

def run_inference_and_mix(vocal_path, music_path, model_path, config_path, spk_name):
    print(f"Converting vocal: {vocal_path}")
    
    # 1. Convert MP3 to WAV for inference (if needed)
    wav_path = "raw/temp_vocal.wav"
    if not os.path.exists("raw"):
        os.makedirs("raw")
    
    # 0. Clean up old files
    if os.path.exists(wav_path):
        os.remove(wav_path)
    
    results_dir = "results"
    if os.path.exists(results_dir):
        for f in os.listdir(results_dir):
            if "temp_vocal" in f:
                os.remove(os.path.join(results_dir, f))
                print(f"Removed old result: {f}")

    y, sr = librosa.load(vocal_path, sr=44100, mono=True)
    soundfile.write(wav_path, y, sr)
    print(f"Saved temp wav to {wav_path}")

    # 2. Run inference using system call to avoid import issues
    # Using python inference_main.py arguments
    # -cm logs/44k/kmeans_10000.pt: Cluster model path
    # -cr 0.5: Cluster ratio (0.5 is recommended)
    # -f0p rmvpe: Use RMVPE pitch predictor
    # -sd -30: Slice threshold (increased from -40 to cut more noise)
    # -ns 0.1: Noise scale (reduced from 0.4 to reduce hiss)
    # -eh: Enable NSF_HIFIGAN enhancer
    # -cl 0: Auto clip (0 is default/auto)
    # -shd: Enable Shallow Diffusion (using downloaded model_0.pt)
    # -dm logs/44k/diffusion/model_0.pt: Diffusion model path
    # -dc logs/44k/diffusion/config.yaml: Diffusion config path
    # -ks 50: k_step (50-100 recommended for shallow diffusion)
    cmd = f'python inference_main.py -m "{model_path}" -c "{config_path}" -n "temp_vocal.wav" -s "{spk_name}" -f0p rmvpe -sd -30 -ns 0.1 -eh -cl 0 -cm logs/44k/kmeans_10000.pt -cr 0.5 -shd -dm logs/44k/diffusion/model_0.pt -dc logs/44k/diffusion/config.yaml -ks 50'
    print(f"Running inference command: {cmd}")
    ret = os.system(cmd)
    
    if ret != 0:
        print("Inference failed! Return code:", ret)
        return

    # 3. Find the result file
    # We will search for the NEW file
    files = os.listdir("results")
    candidates = [f for f in files if "temp_vocal" in f and f.endswith(".flac")]
    if candidates:
        # Pick the most recently created file
        candidates.sort(key=lambda x: os.path.getmtime(os.path.join("results", x)), reverse=True)
        result_filename = os.path.join("results", candidates[0])
        print(f"Inference result found: {result_filename}")
    else:
        print("Could not find result file!")
        return

    # 4. Mix with instrumental
    print(f"Mixing with music: {music_path}")
    
    # Load vocal (the result)
    vocal = AudioSegment.from_file(result_filename)
    
    # Load music
    music = AudioSegment.from_file(music_path)
    
    # Adjust lengths if needed (usually just overlay)
    combined = music.overlay(vocal)
    
    output_path = "final_cover_song.mp3"
    combined.export(output_path, format="mp3")
    print(f"Successfully created: {output_path}")

if __name__ == "__main__":
    vocal = r"D:\桌面\Vocals.wav"
    music = r"D:\桌面\music.wav"
    
    # Auto-detect latest model
    import glob
    model_files = glob.glob("logs/44k/G_*.pth")
    if model_files:
        # Sort by step count (G_100.pth -> 100)
        # Extract number from filename
        def get_steps(f):
            try:
                return int(f.split("_")[-1].split(".")[0])
            except:
                return 0
        
        model_files.sort(key=get_steps, reverse=True)
        model = model_files[0]
        print(f"Auto-selected latest model: {model}")
    else:
        model = "logs/44k/G_18400.pth" # Fallback
        print(f"No model found, using fallback: {model}")

    config = "configs/config.json"
    spk = "my_voice"
    
    run_inference_and_mix(vocal, music, model, config, spk)
