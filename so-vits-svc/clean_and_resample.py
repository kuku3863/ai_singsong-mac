import os
import glob
import shutil
import librosa
import soundfile as sf
import numpy as np
from tqdm import tqdm
import argparse
from scipy import signal

def butter_highpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='high', analog=False)
    return b, a

def highpass_filter(data, cutoff, fs, order=5):
    b, a = butter_highpass(cutoff, fs, order=order)
    y = signal.filtfilt(b, a, data)
    return y

def clean_dataset(src_dir, backup_dir, target_dir=None):
    # 1. Backup
    if not os.path.exists(backup_dir):
        print(f"Backing up {src_dir} to {backup_dir}...")
        shutil.copytree(src_dir, backup_dir)
    else:
        print(f"Backup already exists at {backup_dir}, skipping backup.")

    # 2. Process files
    files = glob.glob(os.path.join(src_dir, "*.wav"))
    print(f"Found {len(files)} files in {src_dir}")

    removed_count = 0
    processed_count = 0

    if target_dir:
        if os.path.exists(target_dir):
            print(f"Clearing existing target directory: {target_dir}")
            shutil.rmtree(target_dir)
        os.makedirs(target_dir)

    for f in tqdm(files):
        try:
            # Load audio (resample to 44100)
            y, sr = librosa.load(f, sr=44100)

            # Apply High-pass filter (remove rumble/noise < 70Hz)
            y = highpass_filter(y, 70, sr)

            # Trim silence
            # top_db=30 means anything below -30dB relative to max is considered silence
            yt, index = librosa.effects.trim(y, top_db=30)

            # Check duration
            duration = librosa.get_duration(y=yt, sr=sr)
            
            # Filter: 2s < duration < 15s
            if duration < 2.0:
                # print(f"Removing {f}: Too short ({duration:.2f}s)")
                os.remove(f)
                removed_count += 1
                continue
            
            if duration > 15.0:
                # print(f"Removing {f}: Too long ({duration:.2f}s)")
                os.remove(f)
                removed_count += 1
                continue

            # Normalize volume to -1dB (peak normalization to 0.891)
            # This ensures consistent volume across training data and prevents clipping
            target_peak = 10 ** (-1.0 / 20)
            yt = librosa.util.normalize(yt) * target_peak

            # Overwrite file
            sf.write(f, yt, sr)
            
            # Copy to target dir if specified
            if target_dir:
                target_path = os.path.join(target_dir, os.path.basename(f))
                shutil.copy(f, target_path)
                
            processed_count += 1

        except Exception as e:
            print(f"Error processing {f}: {e}")
            pass

    print(f"Cleaning complete for {src_dir}.")
    print(f"Processed: {processed_count}")
    print(f"Removed: {removed_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dirs", type=str, nargs="+", help="List of specific directories to process")
    args = parser.parse_args()

    base_raw_dir = "dataset_raw"
    base_target_dir = "dataset/44k"
    
    if not os.path.exists(base_raw_dir):
        print(f"Error: {base_raw_dir} does not exist.")
        exit(1)

    # Scan all subdirectories in dataset_raw
    all_subdirs = [d for d in os.listdir(base_raw_dir) if os.path.isdir(os.path.join(base_raw_dir, d))]
    
    if args.dirs:
        # Filter dirs
        subdirs = [d for d in all_subdirs if d in args.dirs]
        print(f"Processing selected directories: {subdirs}")
    else:
        subdirs = all_subdirs
        print(f"Processing all directories: {subdirs}")
    
    if not subdirs:
        print(f"No matching folders found in {base_raw_dir}.")
        exit(1)
    
    for char_name in subdirs:
        # Skip backup folders
        if "_backup" in char_name:
            continue
            
        dataset_dir = os.path.join(base_raw_dir, char_name)
        backup_dir = os.path.join(base_raw_dir, f"{char_name}_backup")
        target_dir = os.path.join(base_target_dir, char_name)
        
        print(f"\nProcessing character: {char_name}")
        clean_dataset(dataset_dir, backup_dir, target_dir)

