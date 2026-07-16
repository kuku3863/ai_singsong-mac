import os
import glob
import shutil
from pydub import AudioSegment, silence
import librosa
import soundfile
import numpy as np

def apply_aggressive_gate(input_path, output_path, threshold_db=-55.0, min_silence_len=50, keep_silence=50):
    """
    Ultra-aggressive gate: mute anything below threshold.
    """
    print(f"Applying Ultra Gate: Threshold={threshold_db}dB")
    audio = AudioSegment.from_file(input_path)
    nonsilent_ranges = silence.detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=threshold_db
    )
    output_audio = AudioSegment.silent(duration=len(audio))
    for start, end in nonsilent_ranges:
        start = max(0, start - keep_silence)
        end = min(len(audio), end + keep_silence)
        chunk = audio[start:end].fade_in(10).fade_out(10)
        output_audio = output_audio.overlay(chunk, position=start)
    output_audio.export(output_path, format="wav")
    print(f"Ultra-gated saved to: {output_path}")

def run_final_clean():
    # Use the file that actually exists
    vocal_path = r"D:\桌面\1_1_rs_(Vocals)_(No Reverb).wav"
    spk_name = "my_voice"
    config_path = "configs/config.json"
    
    # 1. Ultra Gate
    temp_gated = "raw/temp_ultra_gated.wav"
    if not os.path.exists("raw"):
        os.makedirs("raw")
    apply_aggressive_gate(vocal_path, temp_gated, threshold_db=-55, min_silence_len=50, keep_silence=50)

    # 2. Latest 100k model
    model_files = glob.glob("logs/44k/G_*.pth")
    if not model_files:
        print("No model files found!")
        return
    model_files.sort(key=lambda f: int(f.split("_")[-1].split(".")[0]), reverse=True)
    latest_model = model_files[0]
    print(f"Using latest model: {latest_model}")

    # 3. Variations
    variations = [
        {
            "name": "v7_ultra_gate",
            "desc": "Ultra Gate + Slice -60 + No Cluster + No Diff",
            "params": "-sd -60 -cr 0 -ns 0.1"
        },
        {
            "name": "v8_ultra_gate_f0filter",
            "desc": "Ultra Gate + Slice -60 + No Cluster + F0-Filter 0.05",
            "params": "-sd -60 -cr 0 -ns 0.1 -f0f -ft 0.05"
        }
    ]

    for var in variations:
        print(f"\n=== {var['name']} ===")
        cmd = f'python inference_main.py -m "{latest_model}" -c "{config_path}" -n "{os.path.basename(temp_gated)}" -s "{spk_name}" -f0p rmvpe {var["params"]}'
        print(f"Running: {cmd}")
        ret = os.system(cmd)
        if ret != 0:
            print(f"Inference failed for {var['name']}")
            continue

        # Find and rename
        candidates = [f for f in os.listdir("results") if "temp_ultra_gated" in f and f.endswith(".flac")]
        if not candidates:
            print("No output found.")
            continue
        candidates.sort(key=lambda x: os.path.getmtime(os.path.join("results", x)), reverse=True)
        raw = os.path.join("results", candidates[0])
        final = os.path.join("results", f"{var['name']}_vocal_only.flac")
        shutil.move(raw, final)
        print(f"Saved clean vocal: {final}")

if __name__ == "__main__":
    run_final_clean()
