"""
自动混音模块
提供音频混音、合并、增强等功能
支持多轨混音、混响效果、音量平衡
"""

import numpy as np
import torch
import librosa
import soundfile as sf
import torchaudio
from typing import List, Optional, Tuple, Dict


class AutoMixer:
    def __init__(
        self,
        sample_rate: int = 44100,
        target_loudness: float = -14.0,
        crossfade_duration: float = 0.1,
    ):
        self.sample_rate = sample_rate
        self.target_loudness = target_loudness

    @staticmethod
    def _ensure_2d_stereo(audio: np.ndarray) -> np.ndarray:
        """确保音频为 2D (T, C) 立体声格式"""
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=-1)
        elif audio.ndim == 2:
            if audio.shape[0] in (1, 2) and audio.shape[1] > 2:
                audio = audio.T  # (C, T) → (T, C)
            if audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)  # (T, 1) → (T, 2)
        return audio
        self.crossfade_duration = crossfade_duration

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
            mixed = self.normalize_loudness(mixed, self.target_loudness)

        return mixed

    def mix_files(
        self,
        file_paths: List[str],
        volumes: Optional[List[float]] = None,
        output_path: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        tracks = []
        for path in file_paths:
            audio, sr = librosa.load(path, sr=self.sample_rate, mono=False)
            audio = self._ensure_2d_stereo(audio)
            tracks.append(audio)

        mixed = self.mix_tracks(tracks, volumes)

        if output_path:
            sf.write(output_path, mixed, self.sample_rate)

        return mixed, self.sample_rate

    def separate_and_remix(
        self,
        audio_path: str,
        vocal_volume: float = 1.0,
        instrumental_volume: float = 1.0,
        output_path: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        from .separator import VocalSeparator

        separator = VocalSeparator(model_type="mel_band_roformer")
        separated = separator.separate(audio_path, output_dir="tmp_separated")

        vocals_path = separated.get("vocals")
        other_path = separated.get("other")

        if vocals_path is None or other_path is None:
            audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=False)
            if len(audio.shape) == 1:
                audio = np.stack([audio, audio], axis=-1)
            return audio.T, self.sample_rate

        vocals, _ = librosa.load(vocals_path, sr=self.sample_rate, mono=False)
        other, _ = librosa.load(other_path, sr=self.sample_rate, mono=False)

        if len(vocals.shape) == 1:
            vocals = np.stack([vocals, vocals], axis=-1)
        if len(other.shape) == 1:
            other = np.stack([other, other], axis=-1)

        mixed = vocals.T * vocal_volume + other.T * instrumental_volume
        mixed = self.normalize_loudness(mixed, self.target_loudness)

        if output_path:
            sf.write(output_path, mixed, self.sample_rate)

        return mixed, self.sample_rate

    def smart_mix(
        self,
        vocals: np.ndarray,
        accompaniment: np.ndarray,
        vocal_ducking: float = 0.3,
        output_path: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        vocals = self._ensure_2d_stereo(vocals)
        accompaniment = self._ensure_2d_stereo(accompaniment)

        vocal_energy = librosa.feature.rms(
            y=vocals[:, 0], frame_length=2048, hop_length=512
        )[0]

        vocal_energy_norm = vocal_energy / (np.max(vocal_energy) + 1e-6)

        ducking_mask = 1.0 - vocal_energy_norm * (1.0 - vocal_ducking)
        ducking_mask = np.repeat(ducking_mask, 512)[: len(accompaniment)]

        accompaniment_ducked = accompaniment * ducking_mask[: len(accompaniment), np.newaxis]

        mixed = vocals + accompaniment_ducked
        mixed = self.normalize_loudness(mixed, self.target_loudness)

        if output_path:
            sf.write(output_path, mixed, self.sample_rate)

        return mixed, self.sample_rate

    @staticmethod
    def normalize_loudness(audio: np.ndarray, target_db: float = -14.0) -> np.ndarray:
        if audio.ndim == 2:
            y = audio[:, 0]
        else:
            y = audio
        current_loudness = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        current_db = 20 * np.log10(np.mean(current_loudness) + 1e-6)
        gain_db = target_db - current_db
        gain_linear = 10 ** (gain_db / 20)
        result = audio * gain_linear
        peak = np.max(np.abs(result))
        if peak > 0.98:
            result = result * (0.97 / peak)
        return result

    @staticmethod
    def apply_crossfade(audio1: np.ndarray, audio2: np.ndarray, duration: float, sr: int) -> np.ndarray:
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

        return np.concatenate([audio1[:-crossfade_samples], audio1[-crossfade_samples:] + audio2[:crossfade_samples], audio2[crossfade_samples:]])


class AudioMixer:
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def blend(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        ratio: float = 0.5,
    ) -> np.ndarray:
        if len(audio1) != len(audio2):
            min_len = min(len(audio1), len(audio2))
            audio1 = audio1[:min_len]
            audio2 = audio2[:min_len]

        return audio1 * ratio + audio2 * (1 - ratio)

    def adjust_stereo_width(self, audio: np.ndarray, width: float = 1.0) -> np.ndarray:
        if len(audio.shape) != 2:
            return audio

        mid = (audio[:, 0] + audio[:, 1]) / 2
        side = (audio[:, 0] - audio[:, 1]) / 2

        side = side * width

        left = mid + side
        right = mid - side

        return np.stack([left, right], axis=-1)

    def apply_reverb(
        self,
        audio: np.ndarray,
        room_size: float = 0.5,
        damping: float = 0.5,
        wet_level: float = 0.3,
    ) -> np.ndarray:
        impulse_length = int(self.sample_rate * room_size * 2)
        impulse = np.exp(-np.linspace(0, damping * 10, impulse_length))
        impulse = impulse * (np.random.rand(impulse_length) * 2 - 1)

        if len(audio.shape) == 1:
            reverbed = np.convolve(audio, impulse, mode="full")[: len(audio)]
            return audio * (1 - wet_level) + reverbed * wet_level
        else:
            reverbed_l = np.convolve(audio[:, 0], impulse, mode="full")[: len(audio)]
            reverbed_r = np.convolve(audio[:, 1], impulse, mode="full")[: len(audio)]
            reverbed = np.stack([reverbed_l, reverbed_r], axis=-1)
            return audio * (1 - wet_level) + reverbed * wet_level

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
        gain[above_threshold] = 1.0 / (1.0 + (smoothed[above_threshold] - threshold) * (ratio - 1.0) / (smoothed[above_threshold] + 1e-6))

        return audio * gain


def simple_mix(
    vocal_path: str,
    instrumental_path: str,
    output_path: str,
    vocal_ratio: float = 1.0,
    instrumental_ratio: float = 1.0,
) -> str:
    mixer = AutoMixer()
    mixed, sr = mixer.mix_files([vocal_path, instrumental_path], volumes=[vocal_ratio, instrumental_ratio])
    sf.write(output_path, mixed, sr)
    return output_path
