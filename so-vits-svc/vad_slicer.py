import os
import librosa
import soundfile as sf
import numpy as np
from tqdm import tqdm

def merge_intervals(intervals, min_silence_samples):
    if len(intervals) <= 1:
        return intervals
    
    merged = []
    curr_start, curr_end = intervals[0]
    
    for i in range(1, len(intervals)):
        next_start, next_end = intervals[i]
        silence_duration = next_start - curr_end
        
        if silence_duration < min_silence_samples:
            # Silence is too short, merge segments
            curr_end = next_end
        else:
            # Silence is long enough, save current and start new
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
            
    merged.append((curr_start, curr_end))
    return merged

def slice_audio_vad(input_file, output_dir, min_sec=2, max_sec=12, top_db=40, frame_length=1024, hop_length=256, fade_ms=50, silence_gap=0.5):
    """
    Advanced VAD-based slicer with fade-in/out and length control.
    """
    try:
        # Load audio
        y, sr = librosa.load(input_file, sr=44100)
        
        # 1. Use librosa's split (VAD)
        actual_top_db = abs(top_db)
        intervals = librosa.effects.split(y, top_db=actual_top_db, frame_length=frame_length, hop_length=hop_length)
        
        # --- NEW: Merge short silences to avoid over-fragmentation ---
        # If silence is less than silence_gap, don't cut there
        min_silence_samples = int(silence_gap * sr) 
        intervals = merge_intervals(intervals, min_silence_samples)
        
        print(f"--- Slicing {os.path.basename(input_file)} ---")
        print(f"Input duration: {len(y)/sr:.2f}s, top_db used: {actual_top_db}, silence_gap: {silence_gap}s")
        print(f"Intervals after merging: {len(intervals)}")
        
        basename = os.path.splitext(os.path.basename(input_file))[0]
        count = 0
        
        fade_samples = int(fade_ms * sr / 1000)
        
        for start, end in intervals:
            # Add a bit of padding if possible
            pad = int(0.1 * sr) # 100ms padding
            start_padded = max(0, start - pad)
            end_padded = min(len(y), end + pad)
            
            chunk = y[start_padded:end_padded]
            duration = len(chunk) / sr
            
            # If the chunk is too short, skip it
            if duration < min_sec:
                # print(f"  Skipping chunk (too short): {duration:.2f}s")
                continue
                
            # If the chunk is too long, split it further
            if duration > max_sec:
                samples_per_chunk = int(max_sec * sr)
                for i in range(0, len(chunk), samples_per_chunk):
                    sub_chunk = chunk[i:i + samples_per_chunk]
                    if len(sub_chunk) / sr >= min_sec:
                        sub_chunk = apply_fade(sub_chunk, fade_samples)
                        output_path = os.path.join(output_dir, f"{basename}_{count}.wav")
                        sf.write(output_path, sub_chunk, sr)
                        count += 1
            else:
                chunk = apply_fade(chunk, fade_samples)
                output_path = os.path.join(output_dir, f"{basename}_{count}.wav")
                sf.write(output_path, chunk, sr)
                count += 1
        
        print(f"Total slices saved: {count}")
        return count
    except Exception as e:
        print(f"Error slicing {input_file}: {e}")
        return 0

def apply_fade(audio, fade_samples):
    """Apply linear fade in and fade out."""
    if len(audio) < 2 * fade_samples:
        fade_samples = len(audio) // 2
    
    if fade_samples <= 0:
        return audio
        
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    audio[:fade_samples] *= fade_in
    audio[-fade_samples:] *= fade_out
    
    return audio

def process_folder(input_dir, output_dir, **kwargs):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.wav', '.mp3', '.flac', '.m4a'))]
    total_slices = 0
    for f in tqdm(files):
        path = os.path.join(input_dir, f)
        total_slices += slice_audio_vad(path, output_dir, **kwargs)
    return total_slices
