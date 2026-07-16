import os
import glob
import shutil
from pydub import AudioSegment, silence
from concurrent.futures import ThreadPoolExecutor

def process_file(file_path, output_path, threshold_db=-50.0, min_silence_len=50, keep_silence=50):
    try:
        audio = AudioSegment.from_file(file_path)
        
        # Detect non-silent chunks
        nonsilent_ranges = silence.detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=threshold_db
        )
        
        if not nonsilent_ranges:
            print(f"Warning: {os.path.basename(file_path)} seems empty/silent. Skipping.")
            return

        # Reconstruct clean audio
        output_audio = AudioSegment.silent(duration=0) # Start empty
        
        for start, end in nonsilent_ranges:
            # Add a bit of padding
            start = max(0, start - keep_silence)
            end = min(len(audio), end + keep_silence)
            
            chunk = audio[start:end]
            # Fade edges to avoid clicking
            chunk = chunk.fade_in(10).fade_out(10)
            
            output_audio += chunk
            # Add a small silence between chunks if they were separated
            # output_audio += AudioSegment.silent(duration=100) 
        
        # Export
        output_audio.export(output_path, format="wav")
        # print(f"Cleaned: {os.path.basename(file_path)}")
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def clean_dataset():
    input_dir = "dataset_raw/my_voice"
    backup_dir = "dataset_raw/my_voice_original"
    
    # 1. Backup
    if not os.path.exists(backup_dir):
        print(f"Backing up original data to {backup_dir}...")
        shutil.copytree(input_dir, backup_dir)
    else:
        print(f"Backup already exists at {backup_dir}, skipping backup.")
    
    # 2. Process
    files = glob.glob(os.path.join(input_dir, "*.wav"))
    print(f"Found {len(files)} files. Starting cleaning (Threshold: -50dB)...")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        for f in files:
            executor.submit(process_file, f, f) # Overwrite the file in dataset_raw
            
    print("Dataset cleaning completed!")

if __name__ == "__main__":
    clean_dataset()
