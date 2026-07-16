"""
音频混音模型模块 (Audio Mixing Model)
独立的音频混音处理模块，支持多种混音功能

功能：
    - 多轨混音
    - 响度归一化
    - 智能混音（人声 ducking）
    - 混响效果
    - 动态压缩

使用方法：
    from audio_tools.mixer_model import MixerModel

    mixer = MixerModel()
    result = mixer.mix_tracks(["vocals.wav", "instrumental.wav"], volumes=[1.0, 0.8])
    mixer.save("mixed.wav")
"""

import os
import numpy as np
import torch
import librosa
import soundfile as sf
import torchaudio
from scipy.signal import fftconvolve
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class MixingConfig:
    sample_rate: int = 44100
    target_loudness: float = -14.0
    crossfade_duration: float = 0.1
    normalize: bool = True
    bit_depth: int = 32


class MixerModel:
    def __init__(
        self,
        config: Optional[MixingConfig] = None,
        device: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ):
        if config is None:
            config = MixingConfig()
        if sample_rate is not None:
            config.sample_rate = sample_rate
        self.config = config
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = self.config.sample_rate
        self.mixed_audio: Optional[np.ndarray] = None

    def mix_tracks(
        self,
        tracks: List[np.ndarray],
        volumes: Optional[List[float]] = None,
        panning: Optional[List[float]] = None,
        normalize: bool = True,
    ) -> np.ndarray:
        if len(tracks) == 0:
            raise ValueError("No tracks provided")

        if volumes is None:
            volumes = [1.0] * len(tracks)
        if panning is None:
            panning = [0.0] * len(tracks)

        max_length = max(len(t) for t in tracks)
        num_channels = 2

        mixed = np.zeros((max_length, num_channels), dtype=np.float32)

        for track, vol, pan in zip(tracks, volumes, panning):
            if len(track.shape) == 1:
                track = np.stack([track, track], axis=-1)

            if len(track) < max_length:
                track = np.pad(track, ((0, max_length - len(track)), (0, 0)))

            left_gain = vol * np.sqrt(0.5 - pan / 2)
            right_gain = vol * np.sqrt(0.5 + pan / 2)

            mixed[:, 0] += track[:, 0] * left_gain
            mixed[:, 1] += track[:, 1] * right_gain

        if normalize:
            mixed = self.normalize_loudness(mixed, self.config.target_loudness)

        self.mixed_audio = mixed
        return mixed

    def mix_files(
        self,
        file_paths: List[str],
        volumes: Optional[List[float]] = None,
        panning: Optional[List[float]] = None,
    ) -> Tuple[np.ndarray, int]:
        tracks = []
        for path in file_paths:
            audio, sr = librosa.load(path, sr=self.sample_rate, mono=False)
            tracks.append(self._ensure_2d_stereo(audio))

        mixed = self.mix_tracks(tracks, volumes, panning)
        return mixed, self.sample_rate

    @staticmethod
    def _ensure_2d_stereo(audio: np.ndarray) -> np.ndarray:
        """确保音频为 2D (T, C) 立体声格式。
        
        支持输入：
        - 1D (T,) → (T, 2)
        - 2D (T, 1) → (T, 2)
        - 2D (T, 2) → 原样
        - 2D (1, T) → (T, 2)  (librosa mono=False 加载单声道文件)
        - 2D (2, T) → (T, 2)  (librosa mono=False 加载立体声文件)
        """
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=-1)  # (T,) → (T, 2)
        elif audio.ndim == 2:
            if audio.shape[0] in (1, 2) and audio.shape[1] > 2:
                audio = audio.T  # (C, T) → (T, C)
            if audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)  # (T, 1) → (T, 2)
        return audio

    def smart_mix(
        self,
        vocals: np.ndarray,
        accompaniment: np.ndarray,
        vocal_ducking: float = 0.3,
        vocal_volume: float = 1.0,
        accompaniment_volume: float = 1.0,
    ) -> np.ndarray:
        vocals = self._ensure_2d_stereo(vocals)
        accompaniment = self._ensure_2d_stereo(accompaniment)

        vocal_energy = librosa.feature.rms(
            y=vocals[:, 0], frame_length=2048, hop_length=512
        )[0]

        vocal_energy_norm = vocal_energy / (np.max(vocal_energy) + 1e-6)

        ducking_mask = 1.0 - vocal_energy_norm * (1.0 - vocal_ducking)
        ducking_mask = np.repeat(ducking_mask, 512)[: len(accompaniment)]

        accompaniment_ducked = accompaniment * ducking_mask[: len(accompaniment), np.newaxis]

        vocals_adjusted = vocals * vocal_volume
        accompaniment_adjusted = accompaniment_ducked * accompaniment_volume

        mixed = vocals_adjusted + accompaniment_adjusted
        mixed = self.normalize_loudness(mixed, self.config.target_loudness)

        self.mixed_audio = mixed
        return mixed

    def smart_mix_files(
        self,
        vocal_path: str,
        accompaniment_path: str,
        output_path: Optional[str] = None,
        vocal_ducking: float = 0.3,
        vocal_volume: float = 1.0,
        accompaniment_volume: float = 1.0,
    ) -> Tuple[np.ndarray, int]:
        vocals, sr1 = librosa.load(vocal_path, sr=self.sample_rate, mono=False)
        accompaniment, sr2 = librosa.load(accompaniment_path, sr=self.sample_rate, mono=False)

        if len(vocals.shape) == 1:
            vocals = np.stack([vocals, vocals], axis=-1)
        if len(accompaniment.shape) == 1:
            accompaniment = np.stack([accompaniment, accompaniment], axis=-1)

        mixed = self.smart_mix(
            vocals.T,
            accompaniment.T,
            vocal_ducking=vocal_ducking,
            vocal_volume=vocal_volume,
            accompaniment_volume=accompaniment_volume,
        )

        if output_path:
            self.save(output_path, mixed)

        return mixed, self.sample_rate

    def apply_reverb(
        self,
        audio: np.ndarray,
        room_size: float = 0.5,
        damping: float = 0.5,
        wet_level: float = 0.3,
    ) -> np.ndarray:
        """应用 Freeverb 混响效果（Schroeder/Moorer 算法）。

        8 并行梳状滤波器 + 4 串联全通滤波器，产生自然平滑的混响尾音。
        """
        sr = self.sample_rate
        audio = np.asarray(audio, dtype=np.float64)

        # Freeverb 标准延迟线长度（基于 44100Hz，按采样率等比缩放）
        scale = sr / 44100.0
        comb_delays = [int(d * scale) for d in [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]]
        allpass_delays = [int(d * scale) for d in [225, 556, 441, 341]]

        # room_size 映射到反馈增益（0.0~0.98）
        feedback = 0.7 + room_size * 0.28

        # damping 映射到低通系数（越大 HF 衰减越快）
        damp1 = damping * 0.4
        damp2 = 1.0 - damp1

        def _process_channel(signal):
            """对单声道应用 Freeverb"""
            n = len(signal)
            # 8 个并行梳状滤波器的缓冲区 + 低通状态
            comb_bufs = [np.zeros(d) for d in comb_delays]
            comb_idx = [0] * 8
            filter_store = [0.0] * 8

            # 4 个串联全通滤波器的缓冲区
            ap_bufs = [np.zeros(d) for d in allpass_delays]
            ap_idx = [0] * 4

            output = np.zeros(n)

            for i in range(n):
                input_val = signal[i]

                # --- 8 并行梳状滤波器 ---
                comb_out = 0.0
                for k in range(8):
                    buf = comb_bufs[k]
                    idx = comb_idx[k]
                    # 读取缓冲区旧值
                    buf_val = buf[idx]
                    # 低通滤波（模拟 HF 吸收）
                    filter_store[k] = buf_val * damp2 + filter_store[k] * damp1
                    # 写入新值 = 输入 + 反馈 × 低通输出
                    buf[idx] = input_val + filter_store[k] * feedback
                    comb_idx[k] = (idx + 1) % len(buf)
                    comb_out += buf_val

                comb_out *= 0.125  # 8 路平均

                # --- 4 串联全通滤波器 ---
                ap_val = comb_out
                for k in range(4):
                    buf = ap_bufs[k]
                    idx = ap_idx[k]
                    buf_val = buf[idx]
                    feedback_val = buf_val * 0.5
                    buf[idx] = ap_val + feedback_val
                    ap_idx[k] = (idx + 1) % len(buf)
                    ap_val = -buf_val + feedback_val

                output[i] = ap_val

            return output

        # 处理声道
        if audio.ndim == 1:
            wet = _process_channel(audio)
        elif audio.ndim == 2:
            wet_l = _process_channel(audio[:, 0])
            wet_r = _process_channel(audio[:, 1])
            wet = np.stack([wet_l, wet_r], axis=-1)
        else:
            wet = audio

        # 干湿混合 + 等功率补偿
        result = audio * (1 - wet_level) + wet * wet_level * 0.6

        # Peak normalization 防削波
        peak = np.max(np.abs(result))
        if peak > 0.98:
            result = result * (0.97 / peak)

        return result.astype(np.float32)

    def compress(
        self,
        audio: np.ndarray,
        threshold: float = 0.5,
        ratio: float = 4.0,
        attack: float = 0.01,
        release: float = 0.1,
    ) -> np.ndarray:
        envelope = np.abs(audio)
        smoothed = np.zeros_like(envelope)

        attack_coef = np.exp(-1.0 / (self.sample_rate * attack))
        release_coef = np.exp(-1.0 / (self.sample_rate * release))

        for i in range(1, len(envelope)):
            if envelope[i] > smoothed[i - 1]:
                smoothed[i] = attack_coef * smoothed[i - 1] + (1 - attack_coef) * envelope[i]
            else:
                smoothed[i] = release_coef * smoothed[i - 1] + (1 - release_coef) * envelope[i]

        gain = np.ones_like(smoothed)
        above_threshold = smoothed > threshold
        gain[above_threshold] = 1.0 / (
            1.0
            + (smoothed[above_threshold] - threshold) * (ratio - 1.0) / (smoothed[above_threshold] + 1e-6)
        )

        return audio * gain

    def adjust_stereo_width(
        self,
        audio: np.ndarray,
        width: float = 1.0,
    ) -> np.ndarray:
        if len(audio.shape) != 2:
            return audio

        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2

        side = side * width

        left = mid + side
        right = mid - side

        return np.stack([left, right], axis=-1)

    @staticmethod
    def normalize_loudness(audio: np.ndarray, target_db: float = -14.0) -> np.ndarray:
        # librosa.feature.rms 对 2D 输入会做 STFT 导致巨大内存消耗
        # 只取第一个声道计算 RMS
        if audio.ndim == 2:
            y = audio[:, 0]
        else:
            y = audio
        current_loudness = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        current_db = 20 * np.log10(np.mean(current_loudness) + 1e-6)
        gain_db = target_db - current_db
        gain_linear = 10 ** (gain_db / 20)
        result = audio * gain_linear
        # 峰值限制防止削波
        peak = np.max(np.abs(result))
        if peak > 0.98:
            result = result * (0.97 / peak)
        return result

    @staticmethod
    def apply_crossfade(
        audio1: np.ndarray,
        audio2: np.ndarray,
        duration: float,
        sr: int,
    ) -> np.ndarray:
        crossfade_samples = int(duration * sr)
        if crossfade_samples > min(len(audio1), len(audio2)):
            crossfade_samples = min(len(audio1), len(audio2)) // 2

        fade_out = np.linspace(1, 0, crossfade_samples)
        fade_in = np.linspace(0, 1, crossfade_samples)

        if len(audio1.shape) == 1:
            audio1[-crossfade_samples:] *= fade_out
            audio2[:crossfade_samples] *= fade_in
        else:
            audio1[-crossfade_samples:] *= fade_out[:, np.newaxis]
            audio2[:crossfade_samples] *= fade_in[:, np.newaxis]

        return np.concatenate(
            [
                audio1[:-crossfade_samples],
                audio1[-crossfade_samples:] + audio2[:crossfade_samples],
                audio2[crossfade_samples:],
            ]
        )

    def save(self, output_path: str, audio: Optional[np.ndarray] = None) -> str:
        if audio is None:
            audio = self.mixed_audio
        if audio is None:
            raise ValueError("No audio to save. Provide audio or call mix_tracks first.")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        sf.write(output_path, audio, self.sample_rate, subtype="FLOAT")
        return output_path

    def get_loudness(self, audio: np.ndarray) -> float:
        current_loudness = librosa.feature.rms(y=audio, frame_length=2048, hop_length=512)[0]
        return float(20 * np.log10(np.mean(current_loudness) + 1e-6))


def create_mixer(config: Optional[MixingConfig] = None) -> MixerModel:
    return MixerModel(config=config)


def simple_mix(
    vocal_path: str,
    instrumental_path: str,
    output_path: str,
    vocal_ratio: float = 1.0,
    instrumental_ratio: float = 1.0,
) -> str:
    mixer = MixerModel()
    mixed, sr = mixer.mix_files(
        [vocal_path, instrumental_path],
        volumes=[vocal_ratio, instrumental_ratio],
    )
    sf.write(output_path, mixed, sr)
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="音频混音模型")
    parser.add_argument("inputs", nargs="+", help="输入音频文件")
    parser.add_argument("output", help="输出文件")
    parser.add_argument("--volumes", nargs="+", type=float, help="音量列表")
    args = parser.parse_args()

    mixer = MixerModel()
    mixed, sr = mixer.mix_files(args.inputs, volumes=args.volumes)
    mixer.save(args.output, mixed)
    print(f"混音完成: {args.output}")
