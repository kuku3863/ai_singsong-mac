import os
import glob
import librosa
import soundfile
import argparse

def run_diagnostic():
    vocal_path = r"D:\桌面\Vocals.wav"
    music_path = r"D:\桌面\music.wav"
    
    # Check if files exist
    if not os.path.exists(vocal_path):
        print(f"Error: Vocal file not found: {vocal_path}")
        return
    if not os.path.exists(music_path):
        print(f"Error: Music file not found: {music_path}")
        return

    # Prepare temp wav
    if not os.path.exists("raw"):
        os.makedirs("raw")
    temp_wav = "raw/temp_vocal.wav"
    y, sr = librosa.load(vocal_path, sr=44100, mono=True)
    soundfile.write(temp_wav, y, sr)
    print(f"Prepared temp wav: {temp_wav}")

    # Find latest model
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
    print(f"Latest model: {latest_model}")

    config_path = "configs/config.json"
    spk_name = "my_voice"
    
    # Define test cases
    tests = [
        {
            "name": "clean_baseline",
            "desc": "No Cluster, No Diffusion (Pure Model)",
            "args": "-f0p rmvpe -sd -30 -ns 0.1 -eh -cl 0"
        },
        {
            "name": "with_cluster",
            "desc": "With Cluster (Ratio 0.5)",
            "args": "-f0p rmvpe -sd -30 -ns 0.1 -eh -cl 0 -cm logs/44k/kmeans_10000.pt -cr 0.5"
        },
        {
            "name": "with_diffusion",
            "desc": "With Shallow Diffusion (No Cluster)",
            "args": "-f0p rmvpe -sd -30 -ns 0.1 -eh -cl 0 -shd -dm logs/44k/diffusion/model_0.pt -dc logs/44k/diffusion/config.yaml -ks 50"
        },
        {
            "name": "full_stack",
            "desc": "Full (Cluster + Diffusion)",
            "args": "-f0p rmvpe -sd -30 -ns 0.1 -eh -cl 0 -cm logs/44k/kmeans_10000.pt -cr 0.5 -shd -dm logs/44k/diffusion/model_0.pt -dc logs/44k/diffusion/config.yaml -ks 50"
        }
    ]

    for test in tests:
        print(f"\n--- Running Test: {test['name']} ({test['desc']}) ---")
        
        # Clean previous results
        results_dir = "results"
        if os.path.exists(results_dir):
            for f in os.listdir(results_dir):
                if "temp_vocal" in f:
                    os.remove(os.path.join(results_dir, f))
        
        cmd = f'python inference_main.py -m "{latest_model}" -c "{config_path}" -n "temp_vocal.wav" -s "{spk_name}" {test["args"]}'
        print(f"Command: {cmd}")
        os.system(cmd)
        
        # Find result
        candidates = [f for f in os.listdir("results") if "temp_vocal" in f and f.endswith(".flac")]
        if candidates:
            # Sort by time
            candidates.sort(key=lambda x: os.path.getmtime(os.path.join("results", x)), reverse=True)
            res_file = os.path.join("results", candidates[0])
            new_name = f"results/test_{test['name']}.flac"
            if os.path.exists(new_name):
                os.remove(new_name)
            os.rename(res_file, new_name)
            print(f"Saved result to: {new_name}")
        else:
            print("Inference failed for this test case.")

    print("\nDiagnostic run complete. Please check results/ folder.")

if __name__ == "__main__":
    run_diagnostic()
