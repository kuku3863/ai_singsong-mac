import os
import wave
import numpy as np
import glob

def normalize_audio(input_dir, target_db=-1.0):
    """
    对指定目录下的所有 wav 文件进行音量归一化到 target_db。
    """
    wav_files = glob.glob(os.path.join(input_dir, "*.wav"))
    if not wav_files:
        print(f"未在 {input_dir} 中找到 wav 文件")
        return

    # 计算目标线性增益
    target_amplitude = 10 ** (target_db / 20) * 32767

    print(f"开始处理 {len(wav_files)} 个音频文件...")
    
    for wav_path in wav_files:
        with wave.open(wav_path, 'rb') as wf:
            params = wf.getparams()
            frames = wf.readframes(params.nframes)
            # 转换为 numpy 数组 (int16)
            audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
            
            # 获取当前最大振幅
            max_val = np.max(np.abs(audio_data))
            
            if max_val > 0:
                # 计算增益系数
                gain = target_amplitude / max_val
                # 应用增益
                normalized_audio = (audio_data * gain).clip(-32768, 32767).astype(np.int16)
                
                # 写回文件 (直接覆盖原始文件，因为是训练集处理)
                with wave.open(wav_path, 'wb') as out_wf:
                    out_wf.setparams(params)
                    out_wf.writeframes(normalized_audio.tobytes())
                
                print(f"已处理: {os.path.basename(wav_path)} (原最大值: {int(max_val)} -> 目标值: {int(target_amplitude)})")
            else:
                print(f"跳过静音文件: {os.path.basename(wav_path)}")

if __name__ == "__main__":
    dataset_path = r"F:\Python_project\ai_singsong\so-vits-svc\dataset_raw\rongrong"
    normalize_audio(dataset_path)
    print("\n所有音频已完成音量归一化 (-1dB)。")
