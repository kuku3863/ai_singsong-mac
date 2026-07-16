import os
import glob
from inference.infer_tool import Svc
import librosa
import numpy as np
import soundfile
import logging
import warnings
import subprocess

# Filter warnings
warnings.filterwarnings("ignore")
logging.getLogger('numba').setLevel(logging.WARNING)

def convert_to_mp3(wav_path, mp3_path):
    try:
        # Use ffmpeg to convert
        cmd = f'ffmpeg -y -i "{wav_path}" -codec:a libmp3lame -qscale:a 2 "{mp3_path}"'
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  -> Converted to MP3: {mp3_path}")
        # Optional: remove wav file to save space, but keeping it is safer for now
        # os.remove(wav_path) 
    except Exception as e:
        print(f"  -> MP3 conversion failed: {e}")

def mix_audio(vocal_data, bgm_path, output_path, sr):
    try:
        # Load BGM
        bgm_audio, _ = librosa.load(bgm_path, sr=sr, mono=False)
        
        # Ensure dimensions match
        if len(bgm_audio.shape) == 1:
             bgm_audio = np.expand_dims(bgm_audio, axis=0)
        
        if len(vocal_data.shape) == 1:
             vocal_data = np.expand_dims(vocal_data, axis=0)
             
        if bgm_audio.shape[0] == 2 and vocal_data.shape[0] == 1:
             vocal_data = np.repeat(vocal_data, 2, axis=0)
        
        max_len = max(vocal_data.shape[1], bgm_audio.shape[1])
        channels = max(vocal_data.shape[0], bgm_audio.shape[0])
        
        final_mix = np.zeros((channels, max_len), dtype=np.float32)
        
        final_mix[:vocal_data.shape[0], :vocal_data.shape[1]] += vocal_data
        final_mix[:bgm_audio.shape[0], :bgm_audio.shape[1]] += bgm_audio
        
        max_val = np.max(np.abs(final_mix))
        if max_val > 0.99:
            final_mix = final_mix / max_val * 0.99
            
        soundfile.write(output_path, final_mix.T, sr, format="wav")
        return True
    except Exception as e:
        print(f"  -> Mixing failed: {e}")
        return False

def run_chouyan():
    print("Starting 'CHOUYAN' inference...")

    # Configuration
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
    model_path = model_files[0]
    print(f"Using model: {model_path}")

    svc_model = Svc(model_path, "configs/config.json")
    
    vocal_path = r"D:\桌面\1_1_1_《抽烟的人》rs(Vocals)_(No Reverb)_(Vocals).wav"
    bgm_path = r"D:\桌面\bgm.wav"
    song_name = "抽烟的人"
    
    if not os.path.exists(vocal_path):
        print(f"Error: Vocal file not found at {vocal_path}")
        return
    if not os.path.exists(bgm_path):
        print(f"Error: BGM file not found at {bgm_path}")
        return

    output_dir = "results/chouyan"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define variations based on feedback (User liked 0, disliked +12)
    variations = [
        {"name": "原调_0", "tran": 0, "auto_f0": False, "desc": "原调 (推荐)"},
        {"name": "升调_4", "tran": 4, "auto_f0": False, "desc": "升4key (微调)"},
        {"name": "升调_8", "tran": 8, "auto_f0": False, "desc": "升8key (女声尝试)"},
        {"name": "自动音高", "tran": 0, "auto_f0": True, "desc": "自动预测"}
    ]

    for v in variations:
        print(f"\nProcessing Version: {v['desc']}...")
        try:
            _audio = svc_model.slice_inference(
                vocal_path,
                "luo",
                v['tran'],
                -40,
                cluster_infer_ratio=0,
                auto_predict_f0=v['auto_f0'],
                noice_scale=0.4,
                pad_seconds=0.5
            )
            
            svc_model.clear_empty()
            
            # Temporary WAV path
            wav_name = f"{song_name}_{v['name']}.wav"
            wav_path = os.path.join(output_dir, wav_name)
            
            # Mix and Save WAV
            if mix_audio(_audio, bgm_path, wav_path, svc_model.target_sample):
                # Convert to MP3
                mp3_name = f"{song_name}_{v['name']}.mp3"
                mp3_path = os.path.join(output_dir, mp3_name)
                convert_to_mp3(wav_path, mp3_path)
            
        except Exception as e:
            print(f"Failed to process {v['name']}: {e}")

if __name__ == "__main__":
    run_chouyan()
