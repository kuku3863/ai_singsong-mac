"""
人声声码器变调模块
提供基于相位声码器的实时变调功能
支持多种F0提取算法：RMVPE, Crepe, Harvest, Dio, Parselmouth
"""

import numpy as np
import torch
import librosa
from typing import Optional, Tuple


class PhaseVocoder:
    def __init__(self):
        pass

    @staticmethod
    def phase_vocoder(a: np.ndarray, b: np.ndarray, fade_out: np.ndarray, fade_in: np.ndarray) -> np.ndarray:
        window = np.sqrt(fade_out * fade_in)
        fa = np.fft.rfft(a * window)
        fb = np.fft.rfft(b * window)
        absab = np.abs(fa) + np.abs(fb)
        n = a.shape[0]
        if n % 2 == 0:
            absab[1:-1] *= 2
        else:
            absab[1:] *= 2
        phia = np.angle(fa)
        phib = np.angle(fb)
        deltaphase = phib - phia
        deltaphase = deltaphase - 2 * np.pi * np.floor(deltaphase / 2 / np.pi + 0.5)
        w = 2 * np.pi * np.arange(n // 2 + 1) + deltaphase
        t = np.arange(n) / n
        result = (
            a * (fade_out**2)
            + b * (fade_in**2)
            + np.sum(absab * np.cos(w * t + phia), axis=-1) * window / n
        )
        return result

    @classmethod
    def pitch_shift_numpy(
        cls,
        audio: np.ndarray,
        sr: int,
        n_steps: float,
        n_fft: int = 2048,
        hop_length: int = 512,
    ) -> np.ndarray:
        if n_steps == 0:
            return audio

        pitch_factor = 2 ** (n_steps / 12)
        time_stretch_factor = 1.0 / pitch_factor

        stretched = librosa.effects.time_stretch(audio, rate=time_stretch_factor)

        if len(stretched) < len(audio):
            stretched = np.pad(stretched, (0, len(audio) - len(stretched)))
        else:
            stretched = stretched[: len(audio)]

        return stretched


class TorchPhaseVocoder:
    @staticmethod
    def phase_vocoder_torch(
        a: torch.Tensor,
        b: torch.Tensor,
        fade_out: torch.Tensor,
        fade_in: torch.Tensor,
    ) -> torch.Tensor:
        window = torch.sqrt(fade_out * fade_in)
        fa = torch.fft.rfft(a * window)
        fb = torch.fft.rfft(b * window)
        absab = torch.abs(fa) + torch.abs(fb)
        n = a.shape[0]
        if n % 2 == 0:
            absab[1:-1] *= 2
        else:
            absab[1:] *= 2
        phia = torch.angle(fa)
        phib = torch.angle(fb)
        deltaphase = phib - phia
        deltaphase = deltaphase - 2 * np.pi * torch.floor(deltaphase / 2 / np.pi + 0.5)
        w = 2 * np.pi * torch.arange(n // 2 + 1).to(a) + deltaphase
        t = torch.arange(n).unsqueeze(-1).to(a) / n
        result = (
            a * (fade_out**2)
            + b * (fade_in**2)
            + torch.sum(absab * torch.cos(w * t + phia), -1) * window / n
        )
        return result


class PitchShifter:
    def __init__(
        self,
        sample_rate: int = 44100,
        hop_size: int = 512,
        n_fft: int = 2048,
        n_harmonics: int = 64,
    ):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self.n_fft = n_fft
        self.n_harmonics = n_harmonics

    def shift_pitch(
        self,
        audio: np.ndarray,
        n_steps: float,
        method: str = "phase_vocoder",
    ) -> np.ndarray:
        if method == "phase_vocoder":
            return self._phase_vocoder_shift(audio, n_steps)
        elif method == "librosa":
            return self._librosa_shift(audio, n_steps)
        elif method == "psola":
            return self._psola_shift(audio, n_steps)
        else:
            raise ValueError(f"Unknown pitch shifting method: {method}")

    def _phase_vocoder_shift(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        if n_steps == 0:
            return audio

        pitch_factor = 2 ** (n_steps / 12)
        audio_stretched = librosa.effects.time_stretch(audio, rate=1.0 / pitch_factor)

        if len(audio_stretched) < len(audio):
            audio_stretched = np.pad(
                audio_stretched, (0, len(audio) - len(audio_stretched))
            )
        else:
            audio_stretched = audio_stretched[: len(audio)]

        return audio_stretched

    def _librosa_shift(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        return librosa.effects.pitch_shift(audio, sr=self.sample_rate, n_steps=n_steps)

    def _psola_shift(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        f0, _, _ = self._extract_f0(audio)
        if f0 is None or len(f0) == 0:
            return audio

        avg_f0 = np.median(f0[f0 > 0]) if np.any(f0 > 0) else 440.0
        new_f0 = avg_f0 * (2 ** (n_steps / 12))

        f0_ratio = new_f0 / avg_f0 if avg_f0 > 0 else 1.0
        time_ratio = 1.0 / f0_ratio

        return librosa.effects.time_stretch(audio, rate=time_ratio)

    def _extract_f0(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C1"),
            fmax=librosa.note_to_hz("C7"),
            sr=self.sample_rate,
        )
        return np.array(f0), np.array(voiced_flag), np.array(voiced_probs)


class F0Extractor:
    SUPPORTED_EXTRACTORS = ["crepe", "rmvpe", "fcpe", "parselmouth", "dio", "harvest", "pyin"]

    def __init__(
        self,
        extractor: str = "crepe",
        sample_rate: int = 44100,
        hop_size: int = 512,
        f0_min: float = 65,
        f0_max: float = 800,
        device: Optional[str] = None,
    ):
        self.extractor_name = extractor
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self.f0_min = f0_min
        self.f0_max = f0_max
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

        if extractor == "rmvpe":
            self._load_rmvpe()
        elif extractor == "crepe":
            self._load_crepe()

    def _load_rmvpe(self):
        try:
            import sys, os
            _base = os.environ.get("rmvpe_root", os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "assets", "rvc_weights"
            ))
            model_path = os.path.join(_base, "rmvpe.pt") if os.path.exists(os.path.join(_base, "rmvpe.pt")) else "assets/rvc_weights/rmvpe.pt"
            from infer.lib.rmvpe import RMVPE
            self.model = RMVPE(model_path, is_half=False, device=self.device)
            print("Loaded RMVPE model")
        except Exception as e:
            print(f"Could not load RMVPE: {e}")
            self.model = None

    def _load_crepe(self):
        try:
            import torchcrepe
            self.model = torchcrepe
            print("Loaded Crepe model")
        except Exception as e:
            print(f"Could not load Crepe: {e}")
            self.model = None

    def extract(self, audio: np.ndarray, uv_interp: bool = False) -> np.ndarray:
        if self.extractor_name == "crepe":
            return self._extract_crepe(audio)
        elif self.extractor_name == "parselmouth":
            return self._extract_parselmouth(audio)
        elif self.extractor_name == "dio":
            return self._extract_dio(audio)
        elif self.extractor_name == "harvest":
            return self._extract_harvest(audio)
        elif self.extractor_name == "pyin":
            return self._extract_pyin(audio)
        elif self.extractor_name == "rmvpe":
            return self._extract_rmvpe(audio)
        else:
            return self._extract_pyin(audio)

    def _extract_crepe(self, audio: np.ndarray) -> np.ndarray:
        try:
            import torchcrepe
            from torchaudio.transforms import Resample

            resampler = Resample(self.sample_rate, 16000).to(self.device)
            wav16k = resampler(torch.FloatTensor(audio).unsqueeze(0).to(self.device))

            f0, pd = torchcrepe.predict(
                wav16k,
                16000,
                80,
                self.f0_min,
                self.f0_max,
                pad=True,
                model="full",
                batch_size=512,
                device=self.device,
                return_periodicity=True,
            )

            import sys
            import os
            _at_dir = os.path.join(os.path.dirname(__file__), "src", "mixer")
            if _at_dir not in sys.path:
                sys.path.insert(0, _at_dir)
            from core import MaskedAvgPool1d

            pd = MaskedAvgPool1d(pd, 4)
            f0 = torchcrepe.threshold.At(0.05)(f0, pd)
            f0 = MaskedAvgPool1d(f0, 4)
            f0 = f0.squeeze(0).cpu().numpy()

            n_frames = int(len(audio) // self.hop_size) + 1
            if len(f0) < n_frames:
                f0 = np.pad(f0, (0, n_frames - len(f0)))
            else:
                f0 = f0[:n_frames]

            if uv_interp:
                f0 = self._interp_unvoiced(f0)

            return f0
        except Exception as e:
            print(f"Crepe extraction failed: {e}")
            return self._extract_pyin(audio)

    def _extract_parselmouth(self, audio: np.ndarray) -> np.ndarray:
        import parselmouth

        n_frames = int(len(audio) // self.hop_size) + 1
        l_pad = int(np.ceil(1.5 / self.f0_min * self.sample_rate))
        r_pad = int(
            self.hop_size * ((len(audio) - 1) // self.hop_size + 1)
            - len(audio)
            + l_pad
            + 1
        )

        sound = parselmouth.Sound(np.pad(audio, (l_pad, r_pad)), self.sample_rate).to_pitch_ac(
            time_step=self.hop_size / self.sample_rate,
            voicing_threshold=0.6,
            pitch_floor=self.f0_min,
            pitch_ceiling=self.f0_max,
        )

        f0 = np.pad(sound.selected_array["frequency"], (0, n_frames - len(f0)))
        f0 = f0[:n_frames]

        if uv_interp:
            f0 = self._interp_unvoiced(f0)

        return f0

    def _extract_dio(self, audio: np.ndarray) -> np.ndarray:
        import pyworld as pw

        n_frames = int(len(audio) // self.hop_size) + 1
        _f0, t = pw.dio(
            audio.astype("double"),
            self.sample_rate,
            f0_floor=self.f0_min,
            f0_ceil=self.f0_max,
            channels_in_octave=2,
            frame_period=(1000 * self.hop_size / self.sample_rate),
        )
        f0 = pw.stonemask(audio.astype("double"), _f0, t, self.sample_rate)
        f0 = np.pad(f0.astype("float"), (0, n_frames - len(f0)))

        if uv_interp:
            f0 = self._interp_unvoiced(f0)

        return f0

    def _extract_harvest(self, audio: np.ndarray) -> np.ndarray:
        import pyworld as pw

        n_frames = int(len(audio) // self.hop_size) + 1
        f0, _ = pw.harvest(
            audio.astype("double"),
            self.sample_rate,
            f0_floor=self.f0_min,
            f0_ceil=self.f0_max,
            frame_period=(1000 * self.hop_size / self.sample_rate),
        )
        f0 = np.pad(f0.astype("float"), (0, n_frames - len(f0)))

        if uv_interp:
            f0 = self._interp_unvoiced(f0)

        return f0

    def _extract_pyin(self, audio: np.ndarray) -> np.ndarray:
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C1"),
            fmax=librosa.note_to_hz("C7"),
            sr=self.sample_rate,
            hop_length=self.hop_size,
        )

        f0 = np.array(f0)
        voiced_flag = np.array(voiced_flag)

        if uv_interp:
            f0 = self._interp_unvoiced(f0)
        else:
            f0[~voiced_flag] = 0

        return f0

    def _extract_rmvpe(self, audio: np.ndarray) -> np.ndarray:
        if self.model is None:
            print("RMVPE model not loaded, falling back to pyin")
            return self._extract_pyin(audio)

        try:
            f0 = self.model.infer_from_audio(audio, thred=0.03)
            n_frames = int(len(audio) // self.hop_size) + 1
            if len(f0) < n_frames:
                f0 = np.pad(f0, (0, n_frames - len(f0)))
            else:
                f0 = f0[:n_frames]

            if uv_interp:
                f0 = self._interp_unvoiced(f0)

            return f0
        except Exception as e:
            print(f"RMVPE extraction failed: {e}")
            return self._extract_pyin(audio)

    @staticmethod
    def _interp_unvoiced(f0: np.ndarray) -> np.ndarray:
        voiced = f0 > 0
        if not np.any(voiced):
            return f0

        indices = np.arange(len(f0))
        f0[~voiced] = np.interp(indices[~voiced], indices[voiced], f0[voiced])
        return f0


def pitch_shift_audio(
    audio_path: str,
    output_path: str,
    n_steps: float,
    method: str = "librosa",
) -> str:
    audio, sr = librosa.load(audio_path, sr=None)

    if method == "librosa":
        shifted = librosa.effects.pitch_shift(audio, sr=sr, n_steps=n_steps)
    elif method == "phase_vocoder":
        pv = PhaseVocoder()
        shifted = pv.pitch_shift_numpy(audio, sr, n_steps)
    else:
        shifter = PitchShifter(sample_rate=sr)
        shifted = shifter.shift_pitch(audio, n_steps, method=method)

    import soundfile as sf
    sf.write(output_path, shifted, sr)
    return output_path
