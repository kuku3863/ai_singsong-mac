import argparse
import concurrent.futures
import os
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count

import librosa
import numpy as np
from rich.progress import track
from scipy.io import wavfile


def load_wav(wav_path):
    return librosa.load(wav_path, sr=None)


def trim_wav(wav, top_db=35):
    """
    More aggressive trimming to remove breathing and silence.
    Uses librosa.effects.split to remove silent intervals within the audio.
    """
    intervals = librosa.effects.split(wav, top_db=top_db)
    new_wav = []
    for start, end in intervals:
        new_wav.append(wav[start:end])
    if len(new_wav) == 0:
        return wav, None
    return np.concatenate(new_wav), None


def normalize_peak(wav, threshold=1.0):
    """
    Peak normalization to 0.98 threshold (matching the other project).
    """
    peak = np.abs(wav).max()
    if peak > 0:
        wav = 0.98 * wav / peak
    return wav


def resample_wav(wav, sr, target_sr):
    return librosa.resample(wav, orig_sr=sr, target_sr=target_sr)


def save_wav_to_path(wav, save_path, sr):
    wavfile.write(
        save_path,
        sr,
        (wav * np.iinfo(np.int16).max).astype(np.int16)
    )


def process(item):
    spkdir, wav_name, args = item
    speaker = spkdir.replace("\\", "/").split("/")[-1]

    wav_path = os.path.join(args.in_dir, speaker, wav_name)
    if os.path.exists(wav_path) and '.wav' in wav_path:
        os.makedirs(os.path.join(args.out_dir2, speaker), exist_ok=True)

        wav, sr = load_wav(wav_path)
        old_len = len(wav)
        wav, _ = trim_wav(wav)
        new_len = len(wav)
        if old_len != new_len:
            print(f"Trimmed {wav_name}: {old_len/sr:.2f}s -> {new_len/sr:.2f}s")
        wav = normalize_peak(wav)
        resampled_wav = resample_wav(wav, sr, args.sr2)

        if not args.skip_loudnorm:
            resampled_wav = 0.98 * resampled_wav / np.max(np.abs(resampled_wav))

        save_path2 = os.path.join(args.out_dir2, speaker, wav_name)
        save_wav_to_path(resampled_wav, save_path2, args.sr2)


"""
def process_all_speakers():
    process_count = 30 if os.cpu_count() > 60 else (os.cpu_count() - 2 if os.cpu_count() > 4 else 1)

    with ThreadPoolExecutor(max_workers=process_count) as executor:
        for speaker in speakers:
            spk_dir = os.path.join(args.in_dir, speaker)
            if os.path.isdir(spk_dir):
                print(spk_dir)
                futures = [executor.submit(process, (spk_dir, i, args)) for i in os.listdir(spk_dir) if i.endswith("wav")]
                for _ in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
                    pass
"""
# multi process


def process_all_speakers():
    process_count = 4 # Reduced workers to avoid MemoryError
    skip_speakers = args.skip_speakers.split(",") if args.skip_speakers else []
    with ProcessPoolExecutor(max_workers=process_count) as executor:
        for speaker in speakers:
            if speaker in skip_speakers:
                print(f"Skipping speaker: {speaker}")
                continue
            spk_dir = os.path.join(args.in_dir, speaker)
            if os.path.isdir(spk_dir):
                print(spk_dir)
                futures = [executor.submit(process, (spk_dir, i, args)) for i in os.listdir(spk_dir) if i.endswith("wav")]
                for _ in track(concurrent.futures.as_completed(futures), total=len(futures), description="resampling:"):
                    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sr2", type=int, default=44100, help="sampling rate")
    parser.add_argument("--in_dir", type=str, default="./dataset_raw", help="path to source dir")
    parser.add_argument("--out_dir2", type=str, default="./dataset/44k", help="path to target dir")
    parser.add_argument("--skip_loudnorm", action="store_true", help="Skip loudness matching if you have done it")
    parser.add_argument("--skip_speakers", type=str, default="luo", help="Comma separated list of speakers to skip (e.g. 'luo,tian')")
    args = parser.parse_args()

    print(f"CPU count: {cpu_count()}")
    speakers = os.listdir(args.in_dir)
    process_all_speakers()
