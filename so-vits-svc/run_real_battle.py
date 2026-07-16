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

def run_battle():
    print("Starting REAL BATTLE inference...")

    # Configuration
    model_path = ""
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
    model_path = model_files[0]
    print(f"Using model: {model_path}")

    config_path = "configs/config.json"
    
    # Load model
    svc_model = Svc(model_path, config_path)
    
    # Input files
    vocal_path = r"D:\桌面\rs.wav"
    bgm_path = r"D:\桌面\bgm.wav"
    
    if not os.path.exists(vocal_path):
        print(f"Error: Vocal file not found: {vocal_path}")
        return
    if not os.path.exists(bgm_path):
        print(f"Error: BGM file not found: {bgm_path}")
        return

    # Output paths
    if not os.path.exists("results"):
        os.makedirs("results")
    vocal_output_path = "results/real_battle_vocal.wav"
    final_output_path = "results/real_battle_final.wav"

    # Inference parameters
    spk = "luo"
    tran = 0
    slice_db = -40
    
    print(f"Inferencing vocal: {vocal_path}...")
    
    try:
        # Run inference on vocal
        _audio = svc_model.slice_inference(
            vocal_path,
            spk,
            tran,
            slice_db,
            cluster_infer_ratio=0,
            auto_predict_f0=False,
            noice_scale=0.4,
            pad_seconds=0.5
        )
        
        svc_model.clear_empty()
        
        # Save converted vocal
        soundfile.write(vocal_output_path, _audio, svc_model.target_sample, format="wav")
        print(f"Saved converted vocal to {vocal_output_path}")
        
        # Mixing
        print("Mixing with BGM...")
        
        # Load BGM
        bgm_audio, bgm_sr = librosa.load(bgm_path, sr=svc_model.target_sample, mono=False)
        
        # Prepare Vocal Audio
        vocal_audio = _audio
        
        # Ensure dimensions match for stereo/mono
        # Handle BGM shape
        if len(bgm_audio.shape) == 1: # Mono BGM (samples,)
             bgm_audio = np.expand_dims(bgm_audio, axis=0) # (1, samples)
        
        # Handle Vocal shape
        if len(vocal_audio.shape) == 1: # Mono Vocal (samples,)
             vocal_audio = np.expand_dims(vocal_audio, axis=0) # (1, samples)
             
        # If BGM is stereo (2, samples) and Vocal is mono (1, samples), duplicate vocal
        if bgm_audio.shape[0] == 2 and vocal_audio.shape[0] == 1:
             vocal_audio = np.repeat(vocal_audio, 2, axis=0)
        
        # Length matching
        max_len = max(vocal_audio.shape[1], bgm_audio.shape[1])
        channels = max(vocal_audio.shape[0], bgm_audio.shape[0])
        
        final_mix = np.zeros((channels, max_len), dtype=np.float32)
        
        # Add vocal
        final_mix[:vocal_audio.shape[0], :vocal_audio.shape[1]] += vocal_audio
        
        # Add BGM
        final_mix[:bgm_audio.shape[0], :bgm_audio.shape[1]] += bgm_audio
        
        # Normalize/Clip to prevent clipping distortion
        max_val = np.max(np.abs(final_mix))
        if max_val > 0.99:
            print(f"Normalizing mix (max val: {max_val})...")
            final_mix = final_mix / max_val * 0.99
            
        # Save final mix
        # soundfile expects (samples, channels)
        soundfile.write(final_output_path, final_mix.T, svc_model.target_sample, format="wav")
        print(f"Saved final mix to {final_output_path}")
        
    except Exception as e:
        print(f"Inference/Mixing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_battle()
