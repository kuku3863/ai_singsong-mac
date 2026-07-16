import os
import argparse
import soundfile
import librosa
import numpy as np
from pydub import AudioSegment
import glob
import shutil

def run_full_cover():
    # 1. Configuration
    vocal_path = r"D:\桌面\人声.wav"
    inst_path = r"D:\桌面\bgm.wav"
    
    config_path = "configs/config.json"
    spk_name = "my_voice"
    
    # Check inputs
    if not os.path.exists(vocal_path):
        print(f"Error: Vocal file not found: {vocal_path}")
        return
    if not os.path.exists(inst_path):
        print(f"Error: Instrumental file not found: {inst_path}")
        return

    # 2. Clear results folder (User requested)
    results_dir = "results"
    if os.path.exists(results_dir):
        print(f"Clearing {results_dir}...")
        for f in os.listdir(results_dir):
            file_path = os.path.join(results_dir, f)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
    else:
        os.makedirs(results_dir)

    # 3. Prepare Input for Inference
    # Copy clean vocal to temp location
    temp_wav = "raw/temp_clean_vocal.wav"
    if not os.path.exists("raw"):
        os.makedirs("raw")
    shutil.copy(vocal_path, temp_wav)
    print(f"Prepared vocal input: {temp_wav}")

    # 4. Find Latest Model
    model_files = glob.glob("logs/44k/G_*.pth")
    if not model_files:
        print("No model files found!")
        return
    
    def get_steps(f):
        try:
            return int(f.split("_")[-1].split(".")[0])
        except:
            return 0
            
    model_files.sort(key=get_steps, reverse=True)
    latest_model = model_files[0]
    print(f"Using latest model: {latest_model}")

    # 5. Run Inference
    # -cm: Cluster model (timbre)
    # -cr: Cluster ratio
    # -f0p: F0 predictor (rmvpe is best)
    # -ns: Noise scale (0.1 for clean output)
    # -cl: Clip threshold (0=auto)
    # -shd: Shallow Diffusion (Optional)
    
    diffusion_model = "logs/44k/diffusion/model_0.pt"
    use_diffusion = False
    if os.path.exists(diffusion_model):
        use_diffusion = True
        print("Shallow Diffusion enabled.")
    
    # Using aggressive parameters as refined in previous turn
    cmd = f'python inference_main.py -m "{latest_model}" -c "{config_path}" -n "temp_clean_vocal.wav" -s "{spk_name}" -f0p rmvpe -ns 0.1 -cl 0 -cm logs/44k/kmeans_10000.pt -cr 0.4'
    
    if use_diffusion:
        cmd += f' -shd -dm {diffusion_model} -dc logs/44k/diffusion/config.yaml -ks 100 -sd -45'
    else:
        cmd += ' -sd -45'
        
    print(f"Running inference...")
    ret = os.system(cmd)
    
    if ret != 0:
        print("Inference failed.")
        return

    # 6. Find Result
    candidates = [f for f in os.listdir("results") if "temp_clean_vocal" in f and f.endswith(".flac")]
    if not candidates:
        print("No result file found.")
        return
        
    candidates.sort(key=lambda x: os.path.getmtime(os.path.join("results", x)), reverse=True)
    svc_result_path = os.path.join("results", candidates[0])
    print(f"Inference output: {svc_result_path}")
    
    # Rename for clarity (User asked for pure vocal version)
    pure_vocal_output = "results/final_vocal_only.flac"
    try:
        shutil.copy(svc_result_path, pure_vocal_output)
        print(f"Pure vocal version saved to: {pure_vocal_output}")
    except Exception as e:
        print(f"Error saving pure vocal version: {e}")

    # 7. Mix with Instrumental using Pydub
    print("Mixing with instrumental...")
    try:
        # Load audio
        vocal_audio = AudioSegment.from_file(svc_result_path)
        inst_audio = AudioSegment.from_file(inst_path)
        
        # Overlay vocal on instrumental
        final_mix = inst_audio.overlay(vocal_audio)
        
        # Save
        output_filename = "results/final_complete_cover.mp3"
        final_mix.export(output_filename, format="mp3")
        print(f"\nSUCCESS! Final mixed cover saved to: {output_filename}")
        
    except Exception as e:
        print(f"Mixing failed: {e}")
        print("Trying fallback mixing with soundfile/numpy...")
        try:
            # Fallback mixing
            v, sr_v = librosa.load(svc_result_path, sr=44100, mono=False)
            i, sr_i = librosa.load(inst_path, sr=44100, mono=False)
            
            # Ensure same length
            min_len = min(v.shape[-1], i.shape[-1])
            if len(v.shape) > 1:
                v = v[..., :min_len]
            else:
                v = v[:min_len]
                
            if len(i.shape) > 1:
                i = i[..., :min_len]
            else:
                i = i[:min_len]
            
            mix = v + i
            
            output_filename = "results/final_complete_cover_fallback.wav"
            soundfile.write(output_filename, mix.T, 44100)
            print(f"SUCCESS! Final mixed cover saved to: {output_filename}")
            
        except Exception as e2:
            print(f"Fallback mixing also failed: {e2}")

if __name__ == "__main__":
    run_full_cover()
