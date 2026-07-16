import os
import glob
import shutil
from pydub import AudioSegment, silence
import librosa
import soundfile
import numpy as np

def apply_noise_gate(input_path, output_path, threshold_db=-50.0, min_silence_len=100, keep_silence=100):
    """
    Apply a hard noise gate using pydub's silence detection.
    Any segment quieter than threshold_db is muted.
    """
    print(f"Applying Noise Gate: Threshold={threshold_db}dB")
    audio = AudioSegment.from_file(input_path)
    
    # Detect non-silent chunks
    # silence.detect_nonsilent returns [start, end] list
    nonsilent_ranges = silence.detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=threshold_db
    )
    
    # Create a new silent audio of the same length
    output_audio = AudioSegment.silent(duration=len(audio))
    
    # Paste the non-silent chunks back onto the silent track
    # We add a small fade in/out to avoid clicking
    for start, end in nonsilent_ranges:
        # Add buffer (keep_silence) to avoid cutting breath too abruptly
        start = max(0, start - keep_silence)
        end = min(len(audio), end + keep_silence)
        
        chunk = audio[start:end]
        # Fade edges
        chunk = chunk.fade_in(20).fade_out(20)
        
        output_audio = output_audio.overlay(chunk, position=start)
        
    output_audio.export(output_path, format="wav")
    print(f"Gated audio saved to: {output_path}")

def run_fix_artifacts():
    # 1. Configuration
    vocal_path = r"D:\桌面\1_1_1_人声_(Vocals)_(No Reverb)_(No Reverb).wav"
    inst_path = r"D:\桌面\bgm.wav"
    spk_name = "my_voice"
    config_path = "configs/config.json"
    
    # 2. Prepare Input
    if not os.path.exists("raw"):
        os.makedirs("raw")
    
    # Apply Noise Gate FIRST
    # This directly addresses "noise between phrases"
    temp_gated_wav = "raw/temp_gated_vocal.wav"
    apply_noise_gate(vocal_path, temp_gated_wav, threshold_db=-50.0)

    # 3. Find Latest Model
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

    # 4. Define Variations (Based on V4 structure but with improvements)
    variations = [
        {
            "name": "v5_gate_only",
            "desc": "V4 + 噪音门限 (彻底静音空白处)",
            "input": temp_gated_wav,
            "params": f"-sd -45 -cr 0 -ns 0.1" # No diffusion, No cluster
        },
        {
            "name": "v6_gate_f0filter",
            "desc": "V4 + 噪音门限 + F0平滑 (减少音高抖动)",
            "input": temp_gated_wav,
            "params": f"-sd -45 -cr 0 -ns 0.1 -f0f" # -f0f enables F0 filtering
        }
    ]

    # 5. Run Inference
    for var in variations:
        print(f"\nProcessing: {var['name']} [{var['desc']}]")
        
        cmd = f'python inference_main.py -m "{latest_model}" -c "{config_path}" -n "{os.path.basename(var["input"])}" -s "{spk_name}" -f0p rmvpe {var["params"]}'
        
        print(f"Running inference...")
        ret = os.system(cmd)
        
        # Find result
        candidates = [f for f in os.listdir("results") if "temp_gated_vocal" in f and f.endswith(".flac") and var['name'] not in f]
        if not candidates: continue
        
        candidates.sort(key=lambda x: os.path.getmtime(os.path.join("results", x)), reverse=True)
        raw_output = os.path.join("results", candidates[0])
        
        # Rename
        vocal_final_path = os.path.join("results", f"{var['name']}_vocal.flac")
        shutil.move(raw_output, vocal_final_path)
        
        # Mix
        mix_output = os.path.join("results", f"{var['name']}_mix.mp3")
        mix_audio(vocal_final_path, inst_path, mix_output)

def mix_audio(vocal_file, inst_file, output_file):
    print(f"Mixing to {output_file} ...")
    try:
        v = AudioSegment.from_file(vocal_file)
        i = AudioSegment.from_file(inst_file)
        mixed = i.overlay(v)
        mixed.export(output_file, format="mp3")
        print("Mixing success.")
    except Exception as e:
        print(f"Mixing failed: {e}")

if __name__ == "__main__":
    run_fix_artifacts()
