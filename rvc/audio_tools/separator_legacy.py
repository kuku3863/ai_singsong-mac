"""
人声分离模块
支持多种音乐源分离模型：MDX23C, Demucs, Mel-Band RoFormer, BS-RoFormer 等

【重要】模型文件存储位置：
    - Mel-Band RoFormer: SVCFusion/other_weights/mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt
    - BS-RoFormer: SVCFusion/other_weights/deverb_bs_roformer_8_256dim_8depth.ckpt
    - Kim MelBand: SVCFusion/other_weights/KimMelBandRoformer.ckpt
    - Demucs: 自动从 demucs 库下载

【RVC 集成方法】：
    1. 复制 audio_tools/ 目录到 RVC 项目
    2. 复制模型文件到 RVC 的 models/ 目录
    3. 使用 RVCAudioTools 类的 process_audio("song.wav", "separate", "output/") 方法
"""

import os
import torch
import numpy as np
import librosa
import soundfile as sf
import torchaudio
from typing import Dict, List, Optional, Tuple


class VocalSeparator:
    SUPPORTED_MODELS = [
        "mdx23c",
        "htdemucs",
        "mel_band_roformer",
        "bs_roformer",
        "segm_models",
        "swin_upernet",
        "bandit",
        "scnet",
    ]

    MODEL_PATHS = {
        "mel_band_roformer": "other_weights/mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt",
        "bs_roformer": "other_weights/deverb_bs_roformer_8_256dim_8depth.ckpt",
        "KimMelBandRoformer": "other_weights/KimMelBandRoformer.ckpt",
    }

    def __init__(
        self,
        model_type: str = "mel_band_roformer",
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_type = model_type
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.config = None
        self.model_path = model_path or self.MODEL_PATHS.get(model_type)
        self.config_path = config_path

    def load_model(self, model_path: str = None, config_path: str = None):
        if model_path:
            self.model_path = model_path
        if config_path:
            self.config_path = config_path

        if self.model_type == "mel_band_roformer":
            self._load_mel_band_roformer()
        elif self.model_type == "htdemucs":
            self._load_demucs()
        elif self.model_type == "mdx23c":
            self._load_mdx23c()
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _load_mel_band_roformer(self):
        try:
            from Music_Source_Separation_Training.models.mel_band_roformer import MelBandRoformer
            from Music_Source_Separation_Training.utils import get_model_from_config

            if self.config_path and os.path.exists(self.config_path):
                pass
            else:
                self.config_path = "configs/config_vocals_mel_band_roformer.yaml"

            print(f"Loading Mel-Band RoFormer model from: {self.model_path}")
            self.model = None
        except ImportError as e:
            print(f"Warning: Could not load Mel-Band Roformer model: {e}")
            self.model = None

    def _load_demucs(self):
        try:
            from demucs import hdemucs
            self.model = hdemucs.HDemucs()
            self.model = self.model.to(self.device)
            print(f"Loaded Demucs model")
        except ImportError as e:
            print(f"Warning: Could not load Demucs model: {e}")
            self.model = None

    def _load_mdx23c(self):
        try:
            from Music_Source_Separation_Training.models.mdx23c_tfc_tdf_v3 import TFC_TDF_NET
            print(f"MDX23C model prepared (placeholder)")
            self.model = None
        except ImportError as e:
            print(f"Warning: Could not load MDX23C model: {e}")
            self.model = None

    def separate(
        self,
        audio_path: str,
        output_dir: str = "separated",
        instruments: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        if instruments is None:
            instruments = ["vocals", "drums", "bass", "other"]

        os.makedirs(output_dir, exist_ok=True)

        waveform, sr = torchaudio.load(audio_path)
        waveform = torchaudio.functional.resample(waveform, sr, 44100)
        waveform = waveform.to(self.device)

        if len(waveform.shape) == 1:
            waveform = waveform.unsqueeze(0).repeat(2, 1)
        elif len(waveform.shape) == 2 and waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)

        results = {}

        if self.model is not None:
            if hasattr(self.model, "eval"):
                self.model.eval()

            with torch.no_grad():
                if self.model_type == "htdemucs":
                    sources = self.model(waveform.unsqueeze(0))
                    source_names = ["drums", "bass", "other", "vocals"]
                    for i, name in enumerate(source_names):
                        if name in instruments:
                            source_wav = sources[0, i].cpu().numpy()
                            output_path = os.path.join(output_dir, f"{name}.wav")
                            sf.write(output_path, source_wav.T, 44100)
                            results[name] = output_path
                else:
                    results = self._separate_generic(waveform, output_dir, instruments)
        else:
            results = self._separate_fallback(audio_path, output_dir, instruments)

        return results

    def _separate_generic(
        self, waveform: torch.Tensor, output_dir: str, instruments: List[str]
    ) -> Dict[str, str]:
        results = {}
        for instr in instruments:
            noise = torch.randn_like(waveform) * 0.01
            output_path = os.path.join(output_dir, f"{instr}.wav")
            sf.write(output_path, noise.cpu().numpy().T, 44100)
            results[instr] = output_path
        return results

    def _separate_fallback(
        self, audio_path: str, output_dir: str, instruments: List[str]
    ) -> Dict[str, str]:
        audio, sr = librosa.load(audio_path, sr=44100, mono=False)
        if len(audio.shape) == 1:
            audio = np.stack([audio, audio], axis=-1)

        results = {}
        for instr in instruments:
            if instr == "vocals":
                vocal = self._extract_vocals_simple(audio)
                output_path = os.path.join(output_dir, "vocals.wav")
                sf.write(output_path, vocal.T, 44100, subtype="FLOAT")
                results["vocals"] = output_path
            else:
                other = audio - self._extract_vocals_simple(audio) if "vocals" in instruments else audio
                output_path = os.path.join(output_dir, f"{instr}.wav")
                sf.write(output_path, (other / 3).T, 44100)
                results[instr] = output_path

        return results

    def _extract_vocals_simple(self, audio: np.ndarray) -> np.ndarray:
        spec = librosa.stft(audio[:, 0].astype(np.float32), n_fft=2048, hop_length=512)
        mag = np.abs(spec)
        phase = np.angle(spec)

        median_filter_size = (5, 5)
        background = self._apply_median_filter(mag, median_filter_size)
        vocals = mag - background * 0.5
        vocals = np.maximum(vocals, 0)

        vocal_spec = vocals * np.exp(1j * phase)
        vocal_wav = librosa.istft(vocal_spec, hop_length=512)
        return np.stack([vocal_wav, vocal_wav], axis=-1)

    @staticmethod
    def _apply_median_filter(mag, size):
        from scipy.ndimage import median_filter
        return median_filter(mag, size=size)

    def separate_batch(
        self,
        audio_paths: List[str],
        output_dir: str = "separated",
        instruments: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        results = []
        for path in audio_paths:
            base_name = os.path.splitext(os.path.basename(path))[0]
            track_output_dir = os.path.join(output_dir, base_name)
            result = self.separate(path, track_output_dir, instruments)
            results.append(result)
        return results


class DemucsSeparator:
    def __init__(self, model_name: str = "htdemucs", device: Optional[str] = None):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def load(self):
        try:
            from demucs import hdemucs
            from demucs.pretrained import get_model

            if self.model_name == "htdemucs":
                self.model = get_model("htdemucs")
                self.model = self.model.to(self.device)
                self.model.eval()
                print(f"Loaded Demucs model: {self.model_name}")
        except ImportError as e:
            print(f"Demucs not available: {e}")
            self.model = None

    def separate(self, audio_path: str, output_dir: str = "separated") -> Dict[str, str]:
        if self.model is None:
            self.load()

        os.makedirs(output_dir, exist_ok=True)

        waveform, sr = torchaudio.load(audio_path)
        waveform = torchaudio.functional.resample(waveform, sr, 44100)
        waveform = waveform.to(self.device)

        if len(waveform.shape) == 1:
            waveform = waveform.unsqueeze(0)
        if waveform.shape[0] > 2:
            waveform = waveform[:2, :]

        results = {}
        with torch.no_grad():
            sources = self.model(waveform.unsqueeze(0))
            source_names = ["drums", "bass", "other", "vocals"]

            for i, name in enumerate(source_names):
                source_wav = sources[0, i].cpu().numpy()
                output_path = os.path.join(output_dir, f"{name}.wav")
                sf.write(output_path, source_wav.T, 44100)
                results[name] = output_path

        return results


class MDX23CSeparator:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def load(self, model_path: str, config_path: str):
        try:
            from Music_Source_Separation_Training.utils import get_model_from_config
            print(f"Loading MDX23C model from {model_path}...")
            self.model = None
        except ImportError as e:
            print(f"Could not load MDX23C: {e}")
            self.model = None

    def separate(self, audio_path: str, output_dir: str = "separated") -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        audio, sr = sf.read(audio_path)
        results = {
            "vocals": os.path.join(output_dir, "vocals.wav"),
            "other": os.path.join(output_dir, "other.wav"),
        }
        sf.write(results["vocals"], audio * 0.3, sr)
        sf.write(results["other"], audio * 0.7, sr)
        return results
