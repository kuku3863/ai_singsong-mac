import os
import librosa
import soundfile as sf
import numpy as np
from tqdm import tqdm
import argparse
import shutil

def slice_audio(input_file, output_dir, min_sec=2, max_sec=12, top_db=40):
    """
    将单个长音频文件切分为 2-12 秒的片段，并去除静音。
    使用更宽松的阈值以确保捕捉到声音。
    """
    try:
        # 加载音频
        y, sr = librosa.load(input_file, sr=44100)
        
        # 1. 预修剪头尾静音
        y, _ = librosa.effects.trim(y, top_db=top_db)
        
        # 2. 使用更短的 frame_length 来探测更细微的声音
        intervals = librosa.effects.split(y, top_db=top_db, frame_length=1024, hop_length=256)
        
        basename = os.path.splitext(os.path.basename(input_file))[0]
        count = 0
        
        for start, end in intervals:
            chunk = y[start:end]
            duration = librosa.get_duration(y=chunk, sr=sr)
            
            # 如果片段太长，按 max_sec 进行二次切分
            if duration > max_sec:
                samples_per_chunk = int(max_sec * sr)
                for i in range(0, len(chunk), samples_per_chunk):
                    sub_chunk = chunk[i:i + samples_per_chunk]
                    sub_duration = librosa.get_duration(y=sub_chunk, sr=sr)
                    if sub_duration >= min_sec:
                        output_path = os.path.join(output_dir, f"{basename}_{count}.wav")
                        sf.write(output_path, sub_chunk, sr)
                        count += 1
            # 如果片段长度在范围内，保存
            elif duration >= min_sec:
                output_path = os.path.join(output_dir, f"{basename}_{count}.wav")
                sf.write(output_path, chunk, sr)
                count += 1
        
        return count
    except Exception as e:
        print(f"Error slicing {input_file}: {e}")
        return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True, help="Path to speaker directory in dataset_raw")
    args = parser.parse_args()
    
    target_dir = args.dir
    backup_dir = target_dir + "_original_backup"
    
    if not os.path.exists(backup_dir):
        print(f"Backup directory {backup_dir} does not exist. Please check your files.")
        exit(1)
        
    # 从备份目录读取文件进行处理
    wav_files = [f for f in os.listdir(backup_dir) if f.endswith(".wav")]
    
    if not wav_files:
        print(f"No wav files found in {backup_dir}")
        exit(1)

    total_count = 0
    for filename in tqdm(wav_files, desc="Processing audio files from backup"):
        file_path = os.path.join(backup_dir, filename)
        
        # 执行切片，输出到原目录
        num_slices = slice_audio(file_path, target_dir)
        total_count += num_slices
        print(f"File {filename} sliced into {num_slices} chunks.")
    
    print(f"Done! Total {total_count} chunks generated in {target_dir}.")
