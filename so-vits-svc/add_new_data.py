
import os
import librosa
import soundfile as sf
from pathlib import Path

def process_new_audio(input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
    
    # 获取已经存在的文件数量，避免覆盖
    existing_files = [f for f in os.listdir(output_dir) if f.endswith('.wav')]
    start_index = len(existing_files)
    print(f"Existing files: {start_index}. Starting from index {start_index}")

    # 我们要处理的新文件
    new_files = ['Voice.mp3', 'Voice1.mp3']
    
    count = start_index
    for filename in new_files:
        filepath = input_path / filename
        if not filepath.exists():
            print(f"File not found: {filepath}")
            continue
            
        print(f"Processing {filename}...")
        try:
            # 加载音频 (采样率 44100)
            y, sr = librosa.load(str(filepath), sr=44100)
            
            # 切分静音 (top_db=30)
            intervals = librosa.effects.split(y, top_db=30, frame_length=2048, hop_length=512)
            
            file_count = 0
            for start, end in intervals:
                chunk = y[start:end]
                duration = len(chunk) / sr
                
                # 过滤太短的片段 (小于 2秒)
                if duration < 2.0:
                    continue
                
                # 如果片段太长 (大于 15秒)，进行二次切分
                if duration > 15.0:
                    # 简单处理：平分成两段或多段
                    num_sub_chunks = int(duration / 10) + 1
                    sub_chunk_len = len(chunk) // num_sub_chunks
                    for j in range(num_sub_chunks):
                        sub_chunk = chunk[j*sub_chunk_len : (j+1)*sub_chunk_len]
                        if len(sub_chunk) / sr >= 2.0:
                            out_name = output_path / f"my_voice_{count:04d}.wav"
                            sf.write(str(out_name), sub_chunk, sr)
                            count += 1
                            file_count += 1
                else:
                    out_name = output_path / f"my_voice_{count:04d}.wav"
                    sf.write(str(out_name), chunk, sr)
                    count += 1
                    file_count += 1
            
            print(f"Added {file_count} chunks from {filename}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

if __name__ == "__main__":
    process_new_audio(r"f:\Python_project\ai_singsong\song", r"f:\Python_project\ai_singsong\so-vits-svc\dataset_raw\my_voice")
