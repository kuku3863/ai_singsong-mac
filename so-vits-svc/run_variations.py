import os
import glob
from inference.infer_tool import Svc
import librosa
import numpy as np
import soundfile
import logging
import warnings

# Filter warnings
warnings.filterwarnings("ignore")
logging.getLogger('numba').setLevel(logging.WARNING)

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
        print(f"  -> Mixed audio saved to: {output_path}")
    except Exception as e:
        print(f"  -> Mixing failed: {e}")

def run_variations():
    print("Starting MULTI-VERSION inference...")

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
    
    vocal_path = r"D:\桌面\rs.wav"
    bgm_path = r"D:\桌面\bgm.wav"
    
    if not os.path.exists(vocal_path) or not os.path.exists(bgm_path):
        print("Error: Input files not found.")
        return

    output_dir = "results/variations"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define variations
    # tran: 升降调 (半音)，男转女通常建议 +8 到 +12
    variations = [
        {"name": "original_pitch", "tran": 0, "auto_f0": False, "desc": "原调 (适合低音/男声)"},
        {"name": "pitch_plus_8", "tran": 8, "auto_f0": False, "desc": "升8key (通用男转女)"},
        {"name": "pitch_plus_12", "tran": 12, "auto_f0": False, "desc": "升12key (高八度/甜美)"},
        {"name": "auto_pitch", "tran": 0, "auto_f0": True, "desc": "自动预测音高"}
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
            
            # Save vocal only
            vocal_out = f"{output_dir}/vocal_{v['name']}.wav"
            soundfile.write(vocal_out, _audio, svc_model.target_sample, format="wav")
            
            # Mix with BGM
            final_out = f"{output_dir}/final_{v['name']}.wav"
            mix_audio(_audio, bgm_path, final_out, svc_model.target_sample)
            
        except Exception as e:
            print(f"Failed to process {v['name']}: {e}")

if __name__ == "__main__":
    run_variations()
