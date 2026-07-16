"""
简单音频处理模块
提供音频切片、静音检测、音频分割等功能
"""

import numpy as np
import librosa
import torch
import torchaudio


class Slicer:
    def __init__(
        self,
        sr: int = 44100,
        threshold: float = -40.0,
        min_length: int = 5000,
        min_interval: int = 300,
        hop_size: int = 20,
        max_sil_kept: int = 5000,
    ):
        if not min_length >= min_interval >= hop_size:
            raise ValueError(
                "The following condition must be satisfied: min_length >= min_interval >= hop_size"
            )
        if not max_sil_kept >= hop_size:
            raise ValueError(
                "The following condition must be satisfied: max_sil_kept >= hop_size"
            )
        min_interval = sr * min_interval / 1000
        self.threshold = 10 ** (threshold / 20.0)
        self.hop_size = round(sr * hop_size / 1000)
        self.win_size = min(round(min_interval), 4 * self.hop_size)
        self.min_length = round(sr * min_length / 1000 / self.hop_size)
        self.min_interval = round(min_interval / self.hop_size)
        self.max_sil_kept = round(sr * max_sil_kept / 1000 / self.hop_size)
        self.sr = sr

    def _apply_slice(self, waveform, begin, end):
        if len(waveform.shape) > 1:
            return waveform[:, begin * self.hop_size : min(waveform.shape[1], end * self.hop_size)]
        else:
            return waveform[begin * self.hop_size : min(waveform.shape[0], end * self.hop_size)]

    def slice(self, waveform):
        if len(waveform.shape) > 1:
            samples = librosa.to_mono(waveform)
        else:
            samples = waveform
        if samples.shape[0] <= self.min_length:
            return {"0": {"slice": False, "split_time": f"0,{len(waveform)}"}}

        rms_list = librosa.feature.rms(
            y=samples, frame_length=self.win_size, hop_length=self.hop_size
        ).squeeze(0)
        sil_tags = []
        silence_start = None
        clip_start = 0

        for i, rms in enumerate(rms_list):
            if rms < self.threshold:
                if silence_start is None:
                    silence_start = i
                continue
            if silence_start is None:
                continue

            is_leading_silence = silence_start == 0 and i > self.max_sil_kept
            need_slice_middle = i - silence_start >= self.min_interval and i - clip_start >= self.min_length

            if not is_leading_silence and not need_slice_middle:
                silence_start = None
                continue

            if i - silence_start <= self.max_sil_kept:
                pos = rms_list[silence_start : i + 1].argmin() + silence_start
                if silence_start == 0:
                    sil_tags.append((0, pos))
                else:
                    sil_tags.append((pos, pos))
                clip_start = pos
            elif i - silence_start <= self.max_sil_kept * 2:
                pos = rms_list[i - self.max_sil_kept : silence_start + self.max_sil_kept + 1].argmin()
                pos += i - self.max_sil_kept
                pos_l = rms_list[silence_start : silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[i - self.max_sil_kept : i + 1].argmin() + i - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                    clip_start = pos_r
                else:
                    sil_tags.append((min(pos_l, pos), max(pos_r, pos)))
                    clip_start = max(pos_r, pos)
            else:
                pos_l = rms_list[silence_start : silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[i - self.max_sil_kept : i + 1].argmin() + i - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                else:
                    sil_tags.append((pos_l, pos_r))
                clip_start = pos_r
            silence_start = None

        total_frames = rms_list.shape[0]
        if silence_start is not None and total_frames - silence_start >= self.min_interval:
            silence_end = min(total_frames, silence_start + self.max_sil_kept)
            pos = rms_list[silence_start : silence_end + 1].argmin() + silence_start
            sil_tags.append((pos, total_frames + 1))

        if len(sil_tags) == 0:
            return {"0": {"slice": False, "split_time": f"0,{len(waveform)}"}}

        chunks = []
        if sil_tags[0][0]:
            chunks.append(
                {"slice": False, "split_time": f"0,{min(waveform.shape[0], sil_tags[0][0] * self.hop_size)}"}
            )

        for i in range(len(sil_tags)):
            if i:
                chunks.append(
                    {
                        "slice": False,
                        "split_time": f"{sil_tags[i-1][1] * self.hop_size},{min(waveform.shape[0], sil_tags[i][0] * self.hop_size)}",
                    }
                )
            chunks.append(
                {
                    "slice": True,
                    "split_time": f"{sil_tags[i][0] * self.hop_size},{min(waveform.shape[0], sil_tags[i][1] * self.hop_size)}",
                }
            )

        if sil_tags[-1][1] * self.hop_size < len(waveform):
            chunks.append(
                {"slice": False, "split_time": f"{sil_tags[-1][1] * self.hop_size},{len(waveform)}"}
            )

        chunk_dict = {}
        for i in range(len(chunks)):
            chunk_dict[str(i)] = chunks[i]
        return chunk_dict


class AudioSlicer:
    @staticmethod
    def cut(audio_path, db_thresh=-30, min_len=5000, flask_mode=False, flask_sr=None):
        if not flask_mode:
            audio, sr = librosa.load(audio_path, sr=None)
        else:
            audio = audio_path
            sr = flask_sr

        slicer = Slicer(sr=sr, threshold=db_thresh, min_length=min_len)
        chunks = slicer.slice(audio)
        return chunks

    @staticmethod
    def cut_by_silence(
        audio_path,
        output_dir,
        min_duration=5.0,
        max_duration=30.0,
        top_db=60,
        frame_length=2048,
        hop_length=512,
    ):
        import os
        from pathlib import Path

        audio, sr = librosa.load(audio_path, sr=None, mono=False)
        if len(audio.shape) == 1:
            audio = audio[np.newaxis, :]

        segments = librosa.effects.split(
            audio.T,
            top_db=top_db,
            frame_length=frame_length,
            hop_length=hop_length,
        )

        os.makedirs(output_dir, exist_ok=True)
        base_name = Path(audio_path).stem
        saved_files = []

        for i, (start, end) in enumerate(segments):
            segment = audio[:, start:end]
            duration = (end - start) / sr

            if duration < min_duration:
                continue
            if duration > max_duration:
                sub_segments = AudioSlicer._split_long_segment(segment, sr, max_duration)
                for j, sub_seg in enumerate(sub_segments):
                    output_path = os.path.join(output_dir, f"{base_name}_{i:04d}_{j:04d}.wav")
                    AudioSlicer._save_audio(sub_seg, sr, output_path)
                    saved_files.append(output_path)
            else:
                output_path = os.path.join(output_dir, f"{base_name}_{i:04d}.wav")
                AudioSlicer._save_audio(segment, sr, output_path)
                saved_files.append(output_path)

        return saved_files

    @staticmethod
    def _split_long_segment(segment, sr, max_duration):
        max_samples = int(max_duration * sr)
        num_splits = len(segment[0]) // max_samples
        sub_segments = []
        for i in range(num_splits + 1):
            start = i * max_samples
            end = min((i + 1) * max_samples, len(segment[0]))
            if end > start:
                sub_segments.append(segment[:, start:end])
        return sub_segments

    @staticmethod
    def _save_audio(audio, sr, output_path):
        if len(audio.shape) == 1:
            audio = audio[np.newaxis, :]
        audio_tensor = torch.from_numpy(audio)
        torchaudio.save(output_path, audio_tensor, sr)

    @staticmethod
    def chunks2audio(audio_path, chunks):
        chunks = dict(chunks)
        audio, sr = torchaudio.load(audio_path)
        if len(audio.shape) == 2 and audio.shape[1] >= 2:
            audio = torch.mean(audio, dim=0).unsqueeze(0)
        audio = audio.cpu().numpy()[0]
        result = []
        for k, v in chunks.items():
            tag = v["split_time"].split(",")
            if tag[0] != tag[1]:
                result.append((v["slice"], audio[int(tag[0]) : int(tag[1])]))
        return result, sr


def trim_audio(audio, top_db=30):
    return librosa.effects.trim(audio, top_db=top_db)


def split_stereo(audio):
    if len(audio.shape) == 1:
        return audio, audio
    return audio[0], audio[1]


def normalize_audio(audio, target_db=-20):
    peak = np.abs(audio).max()
    target_linear = 10 ** (target_db / 20)
    return audio * (target_linear / peak) if peak > 0 else audio


def pad_audio(audio, target_length, mode="constant"):
    current_length = len(audio)
    if current_length >= target_length:
        return audio
    if mode == "constant":
        padding = target_length - current_length
        return np.pad(audio, (0, padding), mode=mode)
    elif mode == "wrap":
        return np.concatenate([audio, audio[: target_length - current_length]])
    return audio
