"""
音频分离模型模块 (Audio Separation Model)
基于 ZFTurbo/Music-Source-Separation 推理管线

支持的模型：
    - Mel-Band RoFormer (推荐) - 人声/伴奏分离
    - BS-RoFormer - 去混响
    - MDX23C - 多轨分离
    - KimMelBand RoFormer - 人声提取

使用方法：
    from audio_tools.separator_model import SeparatorModel

    model = SeparatorModel(model_type="mel_band_roformer")
    result = model.separate("input.wav", "output_dir/")
"""

import os
import sys
import importlib
import torch
import numpy as np
import librosa
import soundfile as sf
import torchaudio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


def get_best_torch_device() -> str:
    """Prefer GPU backends for separator inference on local machines."""
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        try:
            torch.zeros(1).to("mps")
            return "mps"
        except Exception:
            pass
    return "cpu"


# 确保 src/separator 的父目录在 sys.path 中，使 separator 可作为包导入
_AUDIO_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_AUDIO_TOOLS_DIR, "src")
# 把 audio_tools/src 加入 sys.path，使 'separator' 成为顶级包
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
# 也把 audio_tools 加入，以防其他模块需要
if _AUDIO_TOOLS_DIR not in sys.path:
    sys.path.insert(0, _AUDIO_TOOLS_DIR)

# 验证 separator 包可导入
try:
    import separator  # noqa: F401
    _SEP_PKG_AVAILABLE = True
except ImportError:
    _SEP_PKG_AVAILABLE = False
    # fallback: 把 separator 目录直接加入 path
    _SEP_DIR = os.path.join(_SRC_DIR, "separator")
    if _SEP_DIR not in sys.path:
        sys.path.insert(0, _SEP_DIR)

SUPPORTED_SEPARATION_MODELS = [
    "mel_band_roformer",
    "bs_roformer",
    "KimMelBandRoformer",
    "mdx23c",
]

# 链式分离管线模型定义（对齐 SVC Fusion）
CHAINED_PIPELINE_MODELS = {
    "kim_vocal": {
        "model_type": "mel_band_roformer",
        "real_type": "mel_band_roformer",
        "config": "configs/separator_kim_mel_band_roformer.yaml",
        "model": "models/separator/KimMelBandRoformer.ckpt",
        "target_instrument": "vocals",
        "description": "Kim 人声提取 (Mel-Band RoFormer)",
    },
    "deverb": {
        "model_type": "bs_roformer",
        "real_type": "bs_roformer",
        "config": "configs/separator_deverb_bs_roformer.yaml",
        "model": "models/separator/deverb_bs_roformer_8_256dim_8depth.ckpt",
        "target_instrument": "noreverb",
        "description": "去混响 (BS-RoFormer depth=8 dim=256)",
    },
    "karaoke": {
        "model_type": "mel_band_roformer",
        "real_type": "mel_band_roformer",
        "config": "configs/separator_karaoke_mel_band_roformer.yaml",
        "model": "models/separator/mel_band_roformer_karaoke.ckpt",
        "target_instrument": "karaoke",
        "description": "伴奏提取 (Mel-Band RoFormer Karaoke)",
    },
}


@dataclass
class SeparationResult:
    vocals: Optional[str] = None
    drums: Optional[str] = None
    bass: Optional[str] = None
    other: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class SeparatorModel:
    DEFAULT_MODEL_PATHS = {
        "mel_band_roformer": "models/separator/mel_band_roformer.ckpt",
        "bs_roformer": "models/separator/bs_roformer.ckpt",
        "KimMelBandRoformer": "models/separator/KimMelBandRoformer.ckpt",
        "mdx23c": "models/separator/mdx23c.ckpt",
    }

    DEFAULT_CONFIG_PATHS = {
        "mel_band_roformer": "configs/separator_mel_band_roformer.yaml",
        "bs_roformer": "configs/separator_bs_roformer.yaml",
        "KimMelBandRoformer": "configs/separator_kim_mel_band_roformer.yaml",
        "mdx23c": "configs/separator_mdx23c.yaml",
    }

    def __init__(
        self,
        model_type: str = "mel_band_roformer",
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        device: Optional[str] = None,
        sample_rate: int = 44100,
    ):
        self.model_type = model_type
        self.device = device or get_best_torch_device()
        self.sample_rate = sample_rate
        self.model = None
        self.config = None
        self._loaded = False

        base_dir = Path(__file__).parent
        self.model_path = model_path or str(base_dir / self.DEFAULT_MODEL_PATHS.get(model_type, ""))
        self.config_path = config_path or str(base_dir / self.DEFAULT_CONFIG_PATHS.get(model_type, ""))

    def load(self) -> bool:
        if self._loaded:
            return self.model is not None

        if not os.path.exists(self.model_path):
            print(f"[Separator] Model not found: {self.model_path}, using fallback")
            self._loaded = True
            return False

        if not os.path.exists(self.config_path):
            print(f"[Separator] Config not found: {self.config_path}, using fallback")
            self._loaded = True
            return False

        try:
            from separator.utils import get_model_from_config

            self.model, self.config = get_model_from_config(self.model_type, self.config_path)

            if self.model is None:
                print(f"[Separator] Failed to create model architecture for {self.model_type}")
                self._loaded = True
                return False

            checkpoint = torch.load(self.model_path, map_location="cpu", weights_only=False)
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                sd = checkpoint["state_dict"]
            elif isinstance(checkpoint, dict) and "model" in checkpoint:
                sd = checkpoint["model"]
            else:
                sd = checkpoint

            # 先尝试严格加载，失败则宽松加载（保留能匹配的层）
            try:
                self.model.load_state_dict(sd, strict=True)
            except Exception:
                missing, unexpected = self.model.load_state_dict(sd, strict=False)
                if missing:
                    print(f"[Separator] Partial load: {len(missing)} missing, {len(unexpected)} unexpected keys")
                # 如果关键层（transformer）缺失太多，放弃模型
                transformer_missing = [k for k in missing if k.startswith("layers.")]
                if len(transformer_missing) > 10:
                    print(f"[Separator] Too many transformer layers missing ({len(transformer_missing)}), using fallback")
                    self.model = None
                    self._loaded = True
                    return False

            self.model = self.model.to(self.device)
            self.model.eval()
            print(f"[Separator] {self.model_type} loaded on {self.device}")
            self._loaded = True
            return True
        except Exception as e:
            print(f"[Separator] Load failed ({self.model_type}): {e}")
            self.model = None
            self._loaded = True
            return False

    def separate(
        self,
        audio_path: str,
        output_dir: str = "separated",
        instruments: Optional[List[str]] = None,
    ) -> SeparationResult:
        if instruments is None:
            instruments = ["vocals", "other"]

        os.makedirs(output_dir, exist_ok=True)

        # 加载音频 (C, T) float32
        audio = None
        try:
            audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=False)
        except Exception as e:
            print(f"[Separator] librosa load failed: {e}")

        # ffmpeg fallback（处理 librosa 不兼容的 MP3/ID3 标签等格式问题）
        if audio is None or (hasattr(audio, 'shape') and audio.shape[-1] == 0):
            print("[Separator] librosa returned empty, trying ffmpeg fallback...")
            try:
                import subprocess
                tmp_wav = os.path.join(output_dir, "_tmp_input.wav")
                cmd = [
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ar", str(self.sample_rate), "-ac", "2",
                    "-acodec", "pcm_f32le", tmp_wav
                ]
                r = subprocess.run(cmd, capture_output=True, timeout=120)
                if r.returncode == 0 and os.path.exists(tmp_wav):
                    import soundfile as sf
                    audio, sr = sf.read(tmp_wav, dtype='float32')
                    if audio.ndim == 1:
                        audio = np.stack([audio, audio], axis=0)
                    elif audio.ndim == 2 and audio.shape[1] == 2:
                        audio = audio.T
                    try:
                        os.remove(tmp_wav)
                    except OSError:
                        pass
                    print(f"[Separator] ffmpeg fallback OK: shape={audio.shape}")
                else:
                    print(f"[Separator] ffmpeg failed: {r.returncode}")
            except Exception as e:
                print(f"[Separator] ffmpeg fallback error: {e}")

        if audio is None:
            print("[Separator] All loading methods failed")
            return SeparationResult()

        if len(audio.shape) == 1:
            audio = np.stack([audio, audio], axis=0)
        elif audio.shape[0] == 1:
            audio = np.tile(audio[0], (2, 1))

        if self.model is not None and self.config is not None:
            # demix_track 需要 (C, T) 格式，即 (channels, samples)
            mix = torch.from_numpy(audio).float()
            # 安全检查：确保维度为 (channels, time) 而非 (time, channels)
            if mix.dim() == 2 and mix.shape[0] > 2 and mix.shape[1] <= 2:
                mix = mix.T
            elif mix.dim() == 1:
                mix = mix.unsqueeze(0)
                mix = torch.cat([mix, mix], dim=0)
            result = self._separate_with_model(mix, output_dir, instruments)
        else:
            # 转为 (T, C) 格式给 fallback 方法
            audio_tc = audio.T
            result = self._separate_fallback(audio_tc, output_dir, instruments)

        return result

    @staticmethod
    def _save_wav(path: str, audio: np.ndarray, sr: int):
        """安全写入 WAV 文件，确保兼容性。
        统一将音频转为 (samples, channels) 即 (T, C) 格式后交给 soundfile。
        """
        audio = np.asarray(audio, dtype=np.float64)
        # 去除多余维度: (1, C, T) -> (C, T), (C, T) 保持
        if audio.ndim == 3:
            audio = audio[0]
        # 判断格式并统一为 (T, C):
        # 使用更健壮的启发式：通道数通常 <= 8，采样数通常 > 1000
        if audio.ndim == 2:
            # (C, T) 检测：shape[0] 是小数字（通道数），shape[1] 是大数字（采样数）
            if audio.shape[0] <= 8 and audio.shape[1] > audio.shape[0] * 10:
                audio = audio.T  # (C, T) -> (T, C)
            elif audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)  # (T, 1) -> (T, 2)
        # 检查数据有效性
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        audio = np.clip(audio, -1.0, 1.0)
        # 使用 PCM_24 保存，比 PCM_16 精度高（144dB vs 96dB），
        # 减少量化噪声对 other = mix - vocal 的影响
        sf.write(path, audio, sr, subtype="PCM_24")

    def _separate_with_model(
        self,
        mix: torch.Tensor,
        output_dir: str,
        instruments: List[str],
    ) -> SeparationResult:
        result = SeparationResult()

        try:
            # 输入音频长度检查
            if mix.numel() == 0 or mix.shape[-1] < 100:
                print(f"[Separator] Audio too short ({mix.shape}), skipping")
                return result

            from separator.utils import demix_track

            # 创建一个 no-op progress 避免 gradio 报错
            # demix_track 会在返回值上调用 .update(step) 和 .close(None)
            class _NoProgress:
                def tqdm(self, iterable=None, **kw):
                    return self
                def update(self, n):
                    pass
                def close(self, val=None):
                    pass

            estimates = demix_track(
                self.config, self.model, mix, self.device,
                progress=_NoProgress(),
                progress_desc="",
            )

            # 保存模型直接输出的音轨
            raw_vocal_np = None
            for name, wav in estimates.items():
                if name in instruments:
                    wav_np = np.asarray(wav, dtype=np.float64)
                    if name == "vocals":
                        raw_vocal_np = wav_np.copy()  # 保留原始副本用于伴奏计算
                        wav_np = self._enhance_vocals(wav_np, self.sample_rate)
                    output_path = os.path.join(output_dir, f"{name}.wav")
                    self._save_wav(output_path, wav_np, self.sample_rate)
                    setattr(result, name, output_path)

            # 伴奏 other = mix - vocals_raw（必须用原始模型输出，不能用 _enhance_vocals 后的）
            # demix_track 在 target_instrument != None 时只返回 vocals，所以 other 总是需要计算
            if "other" in instruments and raw_vocal_np is not None:
                # 严格长度对齐（对齐 SVC Fusion 的 run_folder 逻辑）：
                # demix_track 的 reflect padding + 裁剪可能导致 vocal 和 mix 长度有微小差异
                min_len = min(mix.shape[-1], raw_vocal_np.shape[-1])
                mix_np = mix.double().numpy()[..., :min_len]   # (C, min_len) float64
                vocal_np = raw_vocal_np[..., :min_len]          # (C, min_len) float64
                other_np = mix_np - vocal_np                   # (C, T) float64
                other_path = os.path.join(output_dir, "other.wav")
                self._save_wav(other_path, other_np, self.sample_rate)
                result.other = other_path

        except Exception as e:
            print(f"[Separator] Inference error: {e}")
            import traceback
            traceback.print_exc()
            # mix shape: (C, T) → 转为 (T, C) 给 HPSS
            audio_np = mix.numpy().T
            vocal = self._hpss_vocal_extraction(audio_np)
            if "vocals" in instruments:
                vocal_path = os.path.join(output_dir, "vocals.wav")
                self._save_wav(vocal_path, vocal, self.sample_rate)
                result.vocals = vocal_path
            if "other" in instruments:
                min_len = min(audio_np.shape[0], vocal.shape[0])
                other = audio_np[:min_len] - vocal[:min_len]
                other_path = os.path.join(output_dir, "other.wav")
                self._save_wav(other_path, other, self.sample_rate)
                result.other = other_path

        return result

    def _separate_fallback(
        self,
        audio: np.ndarray,
        output_dir: str,
        instruments: List[str],
    ) -> SeparationResult:
        result = SeparationResult()
        # audio shape: (T, C)

        vocal = self._hpss_vocal_extraction(audio)

        if "vocals" in instruments:
            vocal_path = os.path.join(output_dir, "vocals.wav")
            self._save_wav(vocal_path, vocal, self.sample_rate)
            result.vocals = vocal_path

        if "other" in instruments:
            min_len = min(audio.shape[0], vocal.shape[0])
            other = audio[:min_len] - vocal[:min_len]
            other_path = os.path.join(output_dir, "other.wav")
            self._save_wav(other_path, other, self.sample_rate)
            result.other = other_path

        return result

    @staticmethod
    def _apply_highpass(audio_np: np.ndarray, cutoff_hz: float, sample_rate: int, order: int = 4) -> np.ndarray:
        """对 (C, T) 格式音频应用高通滤波，去除指定频率以下的成分"""
        from scipy.signal import butter, filtfilt
        nyquist = sample_rate / 2.0
        if cutoff_hz >= nyquist:
            return audio_np
        # scipy filtfilt 要求输入长度 > 3 * max(len(a), len(b)) - 1
        min_len = 3 * (3 * order + 1)  # butter order=4 => padlen=15 => min_len=46
        if audio_np.shape[-1] < min_len:
            return audio_np
        b, a = butter(order, cutoff_hz / nyquist, btype='high')
        filtered = np.zeros_like(audio_np)
        for ch in range(audio_np.shape[0]):
            if audio_np.shape[-1] < min_len:
                filtered[ch] = audio_np[ch]
            else:
                filtered[ch] = filtfilt(b, a, audio_np[ch])
        return filtered

    @staticmethod
    def _apply_lowpass(audio_np: np.ndarray, cutoff_hz: float, sample_rate: int, order: int = 4) -> np.ndarray:
        """对 (C, T) 格式音频应用低通滤波，去除指定频率以上的成分"""
        from scipy.signal import butter, filtfilt
        nyquist = sample_rate / 2.0
        if cutoff_hz >= nyquist:
            return audio_np
        min_len = 3 * (3 * order + 1)
        if audio_np.shape[-1] < min_len:
            return audio_np
        b, a = butter(order, cutoff_hz / nyquist, btype='low')
        filtered = np.zeros_like(audio_np)
        for ch in range(audio_np.shape[0]):
            filtered[ch] = filtfilt(b, a, audio_np[ch])
        return filtered

    @staticmethod
    def _enhance_vocals(audio_np: np.ndarray, sample_rate: int) -> np.ndarray:
        """增强人声纯净度：
        1. 80Hz 高通去除低频噪声（空调/电子嗡嗡声/低频泄漏）
        2. 轻度压缩动态范围，让人声更均匀
        3. 归一化防止爆音
        audio shape: (C, T)
        """
        # Step 1: 80Hz 高通，去除低频残留
        vocal = SeparatorModel._apply_highpass(audio_np, 80, sample_rate, order=4)

        # Step 2: 轻度 soft-clip 压缩，让人声更干净
        # 对超过 0.95 的部分做 soft clipping
        threshold = 0.95
        mask = np.abs(vocal) > threshold
        if mask.any():
            # tanh soft clip: 将超出部分平滑压缩
            over = np.sign(vocal) * (np.abs(vocal) - threshold)
            vocal = np.where(mask, np.sign(vocal) * (threshold + np.tanh(over * 5) * 0.05), vocal)

        # Step 3: 归一化
        peak = np.abs(vocal).max()
        if peak > 0.99:
            vocal = vocal * (0.95 / peak)

        return vocal

    def _cleanup_instrumental(self, other_np, config, model, device, sample_rate):
        """二次分离清扫：对伴奏再跑一遍模型，提取残留人声并从伴奏中减去。
        这是消除伴奏中残留人声的最有效方法。

        流程：
        1. 将伴奏作为输入再次送入分离模型
        2. 模型会从伴奏中检测到残留的人声成分
        3. 将检测到的残留人声从伴奏中减去
        4. 对最终结果做轻度归一化

        other_np shape: (C, T) float64
        """
        try:
            from separator.utils import demix_track

            # 构建降噪 progress
            class _NoProgress:
                def tqdm(self, iterable=None, **kw):
                    return self
                def update(self, n):
                    pass
                def close(self, val=None):
                    pass

            # 将伴奏转为 tensor 送入模型二次分离
            instr_tensor = torch.from_numpy(other_np.astype(np.float32))

            # 检查维度，确保是 (channels, time)
            if instr_tensor.dim() == 2 and instr_tensor.shape[0] > 2 and instr_tensor.shape[1] <= 2:
                instr_tensor = instr_tensor.T
            elif instr_tensor.dim() == 1:
                instr_tensor = instr_tensor.unsqueeze(0)
                instr_tensor = torch.cat([instr_tensor, instr_tensor], dim=0)

            # 用同样的模型对伴奏做二次分离
            second_estimates = demix_track(
                config, model, instr_tensor, device,
                progress=_NoProgress(),
                progress_desc="cleanup",
            )

            # 提取二次分离检测到的残留人声
            residual_vocal = None
            for name, wav in second_estimates.items():
                if name == "vocals":
                    residual_vocal = np.asarray(wav, dtype=np.float64)
                    break

            if residual_vocal is not None:
                # 确保长度匹配
                min_len = min(other_np.shape[-1], residual_vocal.shape[-1])
                other_np_trimmed = other_np[..., :min_len]
                residual_vocal_trimmed = residual_vocal[..., :min_len]

                # 从伴奏中减去残留人声
                cleaned = other_np_trimmed - residual_vocal_trimmed

                # 归一化
                peak = np.abs(cleaned).max()
                if peak > 0.99:
                    cleaned = cleaned * (0.95 / peak)

                print(f"[Separator] 二次清扫完成，已去除残留人声 (残留幅度: {np.abs(residual_vocal_trimmed).max():.4f})")
                return cleaned
            else:
                # 模型没有输出 vocals（不太可能），直接归一化返回
                peak = np.abs(other_np).max()
                if peak > 0.99:
                    other_np = other_np * (0.95 / peak)
                return other_np

        except Exception as e:
            print(f"[Separator] 二次清扫失败，使用原始伴奏: {e}")
            # 失败时做简单的归一化返回
            peak = np.abs(other_np).max()
            if peak > 0.99:
                other_np = other_np * (0.95 / peak)
            return other_np

    @staticmethod
    def _hpss_vocal_extraction(audio: np.ndarray, sample_rate: int = 44100) -> np.ndarray:
        """HPSS (谐波-冲击源分离) + 立体声中置提取 人声

        方法：
        1. 对立体声音频取中置 (L+R)/2 提取人声
        2. 对中置信号做 HPSS 分离谐波 (人声) 和冲击 (伴奏)
        3. 用中置的谐波成分作为人声估计
        4. 对侧差 (L-R)/2 做高通滤波提取残留人声
        5. 混合中置谐波 + 侧差高通 = 最终人声

        audio shape: (T, C) — 已转置为 (samples, channels)
        """
        # 单声道直接走 HPSS
        if audio.ndim == 1 or (audio.ndim == 2 and audio.shape[1] == 1):
            mono = audio.flatten().astype(np.float32)
            harmonic, _ = librosa.effects.hpss(mono, kernel_size=31, margin=4)
            vocal = harmonic
        else:
            # 立体声
            left = audio[:, 0].astype(np.float32)
            right = audio[:, 1].astype(np.float32)

            # 中置（人声通常在中央）
            mid = (left + right) / 2.0
            # 侧差（伴奏通常在两侧）
            side = (left - right) / 2.0

            # HPSS 分离中置的谐波（人声）和冲击（鼓/打击乐）
            mid_harmonic, mid_percussive = librosa.effects.hpss(mid, kernel_size=31, margin=4)

            # 从侧差中提取可能的人声残留（中高频段）
            side_harmonic, _ = librosa.effects.hpss(side, kernel_size=31, margin=4)

            # 侧差的高通滤波 — 只保留中高频的人声
            from scipy.signal import butter, filtfilt
            nyquist = sample_rate / 2
            cutoff = 300  # 300Hz 高通
            b, a = butter(4, cutoff / nyquist, btype='high')
            side_harmonic_hp = filtfilt(b, a, side_harmonic)

            # 混合：中置谐波为主 + 少量侧差高通
            vocal = mid_harmonic + 0.3 * side_harmonic_hp

        # 归一化防止爆音
        peak = np.abs(vocal).max()
        if peak > 0.99:
            vocal = vocal * (0.95 / peak)

        if audio.ndim == 2 and audio.shape[1] == 2:
            return np.stack([vocal, vocal], axis=-1)
        else:
            return vocal

    def separate_batch(
        self,
        audio_paths: List[str],
        output_dir: str = "separated",
        instruments: Optional[List[str]] = None,
    ) -> List[SeparationResult]:
        results = []
        for path in audio_paths:
            base_name = Path(path).stem
            track_output_dir = os.path.join(output_dir, base_name)
            result = self.separate(path, track_output_dir, instruments)
            results.append(result)
        return results


def get_available_models() -> List[str]:
    """列出 audio_tools/models/separator/ 中已有权重的模型"""
    base_dir = Path(__file__).parent
    models_dir = base_dir / "models" / "separator"
    configs_dir = base_dir / "configs"

    available = []
    for model_type, ckpt_name in SeparatorModel.DEFAULT_MODEL_PATHS.items():
        ckpt_path = models_dir / ckpt_name.split("/")[-1]
        cfg_name = SeparatorModel.DEFAULT_CONFIG_PATHS.get(model_type, "")
        cfg_path = configs_dir / cfg_name.split("/")[-1] if cfg_name else None
        if ckpt_path.exists() and (cfg_path is None or cfg_path.exists()):
            available.append(model_type)

    return available


def create_separator_model(
    model_type: str = "mel_band_roformer",
    model_path: Optional[str] = None,
    device: Optional[str] = None,
) -> SeparatorModel:
    model = SeparatorModel(model_type=model_type, model_path=model_path, device=device)
    model.load()
    return model


class ChainedSeparator:
    """多模型链式分离管线（对齐 SVC Fusion 的 vr.py 实现）

    管线流程（与 SVC Fusion 一致）：
        原始音频 → [kim_vocal] 人声提取 → 保存 raw_kim_vocal
                    ↓
              [deverb] 去混响 → 干净人声
                    ↓
              [karaoke] 人声精炼 → 更干净的人声（去除残留伴奏）
                    ↓
              最终人声 = karaoke 精炼后
              伴奏 = mix - raw_kim_vocal（算术相减，非 karaoke 输出）

    关键：SVC Fusion 中 karaoke 模型的输出不用于伴奏！
    伴奏始终使用 kim_vocal 阶段的 mix - vocal（对应 real_inst_path 逻辑）。
    karaoke 模型的真实作用是进一步清理人声中的残留伴奏成分。

    使用方法：
        cs = ChainedSeparator()
        cs.load(["kim_vocal", "deverb", "karaoke"])
        result = cs.separate("input.wav", "output_dir/")
        # result.vocals = 清理后的人声路径
        # result.other = 伴奏路径（mix - kim_vocal）
    """

    def __init__(self, device: Optional[str] = None, sample_rate: int = 44100):
        self.device = device or get_best_torch_device()
        self.sample_rate = sample_rate
        self.models = {}  # stage_name -> (model, config, real_type, target_instrument)
        self._loaded_stages = set()

    def load(self, stages: Optional[List[str]] = None) -> bool:
        """加载指定阶段的模型。

        Args:
            stages: 要加载的阶段列表，默认加载全部 ["kim_vocal", "deverb", "karaoke"]
        """
        if stages is None:
            stages = ["kim_vocal", "deverb", "karaoke"]

        base_dir = Path(__file__).parent
        all_loaded = True

        for stage in stages:
            if stage in self._loaded_stages:
                continue

            info = CHAINED_PIPELINE_MODELS.get(stage)
            if info is None:
                print(f"[ChainedSeparator] Unknown stage: {stage}, skipping")
                all_loaded = False
                continue

            model_path = str(base_dir / info["model"])
            config_path = str(base_dir / info["config"])
            real_type = info["real_type"]
            target_instr = info["target_instrument"]

            if not os.path.exists(model_path):
                print(f"[ChainedSeparator] Model not found: {model_path}")
                all_loaded = False
                continue
            if not os.path.exists(config_path):
                print(f"[ChainedSeparator] Config not found: {config_path}")
                all_loaded = False
                continue

            try:
                from separator.utils import get_model_from_config

                model, config = get_model_from_config(real_type, config_path)
                if model is None:
                    print(f"[ChainedSeparator] Failed to create model for stage {stage}")
                    all_loaded = False
                    continue

                checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
                if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                    sd = checkpoint["state_dict"]
                elif isinstance(checkpoint, dict) and "model" in checkpoint:
                    sd = checkpoint["model"]
                else:
                    sd = checkpoint

                try:
                    model.load_state_dict(sd, strict=True)
                except Exception:
                    missing, unexpected = model.load_state_dict(sd, strict=False)
                    if missing:
                        print(f"[ChainedSeparator] {stage} partial load: {len(missing)} missing")
                    transformer_missing = [k for k in missing if k.startswith("layers.")]
                    if len(transformer_missing) > 10:
                        print(f"[ChainedSeparator] {stage} too many missing layers, skipping")
                        all_loaded = False
                        continue

                model = model.to(self.device)
                model.eval()
                self.models[stage] = (model, config, real_type, target_instr)
                self._loaded_stages.add(stage)
                print(f"[ChainedSeparator] {stage} ({info['description']}) loaded on {self.device}")

                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            except Exception as e:
                print(f"[ChainedSeparator] Failed to load {stage}: {e}")
                import traceback
                traceback.print_exc()
                all_loaded = False

        return all_loaded

    def _run_stage(self, stage: str, audio_tensor: torch.Tensor) -> Optional[np.ndarray]:
        """运行单个阶段的分离，返回目标音轨的 numpy 数组 (C, T) float64。

        Args:
            stage: 阶段名称
            audio_tensor: 输入音频 tensor (C, T) float32
        Returns:
            目标音轨 numpy 数组，或 None
        """
        if stage not in self.models:
            print(f"[ChainedSeparator] Stage {stage} not loaded")
            return None

        model, config, real_type, target_instr = self.models[stage]

        try:
            # 输入音频长度检查
            if audio_tensor.numel() == 0 or audio_tensor.shape[-1] < 100:
                print(f"[ChainedSeparator] {stage}: audio too short ({audio_tensor.shape}), skipping")
                return None

            from separator.utils import demix_track

            class _NoProgress:
                def tqdm(self, iterable=None, **kw):
                    return self
                def update(self, n):
                    pass
                def close(self, val=None):
                    pass

            estimates = demix_track(
                config, model, audio_tensor, self.device,
                progress=_NoProgress(),
                progress_desc=f"[{stage}]",
            )

            # 提取目标音轨
            for name, wav in estimates.items():
                if name == target_instr:
                    result = np.asarray(wav, dtype=np.float64)
                    if result.size == 0:
                        print(f"[ChainedSeparator] {stage}: empty output")
                        return None
                    return result

            # 如果找不到目标名称，取第一个
            if estimates:
                first_key = list(estimates.keys())[0]
                print(f"[ChainedSeparator] {stage}: target '{target_instr}' not in output, using '{first_key}'")
                result = np.asarray(estimates[first_key], dtype=np.float64)
                if result.size == 0:
                    print(f"[ChainedSeparator] {stage}: empty output")
                    return None
                return result

            print(f"[ChainedSeparator] {stage}: no output from model")
            return None

        except Exception as e:
            print(f"[ChainedSeparator] {stage} inference error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _save_wav(path: str, audio: np.ndarray, sr: int):
        """安全写入 WAV 文件"""
        audio = np.asarray(audio, dtype=np.float64)
        if audio.ndim == 3:
            audio = audio[0]
        if audio.ndim == 2:
            if audio.shape[0] <= 8 and audio.shape[1] > audio.shape[0] * 10:
                audio = audio.T
            elif audio.shape[1] == 1:
                audio = np.repeat(audio, 2, axis=1)
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
        audio = np.clip(audio, -1.0, 1.0)
        sf.write(path, audio, sr, subtype="PCM_24")

    def separate(
        self,
        audio_path: str,
        output_dir: str = "separated",
        use_kim_vocal: bool = True,
        use_deverb: bool = True,
        use_karaoke: bool = True,
    ) -> SeparationResult:
        """链式分离入口。

        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录
            use_kim_vocal: 是否使用 Kim 人声提取（替代默认 mel_band_roformer）
            use_deverb: 是否使用去混响
            use_karaoke: 是否使用 karaoke 模型直接输出伴奏
        """
        os.makedirs(output_dir, exist_ok=True)
        result = SeparationResult()

        # 加载音频 (C, T) float32
        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1
        print(f"[ChainedSeparator] Loading: {audio_path} ({file_size} bytes)")

        # 文件完整性检查
        if file_size < 44:
            print(f"[ChainedSeparator] File too small ({file_size} bytes), likely corrupted or empty")
            return result

        audio, sr = None, self.sample_rate

        # 方法 1: librosa 加载
        try:
            audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=False)
        except Exception as e:
            print(f"[ChainedSeparator] librosa load failed: {e}")

        # 方法 2: ffmpeg fallback（处理 librosa 不兼容的 ID3 标签等格式问题）
        if audio is None or (hasattr(audio, 'shape') and audio.shape[-1] == 0):
            print("[ChainedSeparator] librosa returned empty, trying ffmpeg fallback...")
            try:
                import subprocess
                tmp_wav = os.path.join(output_dir, "_tmp_input.wav")
                cmd = [
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ar", str(self.sample_rate), "-ac", "2",
                    "-acodec", "pcm_f32le", tmp_wav
                ]
                r = subprocess.run(cmd, capture_output=True, timeout=120)
                if r.returncode == 0 and os.path.exists(tmp_wav):
                    import soundfile as sf
                    audio, sr = sf.read(tmp_wav, dtype='float32')
                    if audio.ndim == 1:
                        audio = np.stack([audio, audio], axis=0)
                    elif audio.ndim == 2 and audio.shape[1] == 2:
                        audio = audio.T  # (T, C) -> (C, T)
                    print(f"[ChainedSeparator] ffmpeg fallback OK: shape={audio.shape}")
                    try:
                        os.remove(tmp_wav)
                    except OSError:
                        pass
                else:
                    print(f"[ChainedSeparator] ffmpeg failed: {r.returncode}")
            except Exception as e:
                print(f"[ChainedSeparator] ffmpeg fallback error: {e}")

        if audio is None:
            print("[ChainedSeparator] All loading methods failed")
            return result

        print(f"[ChainedSeparator] Loaded: shape={audio.shape}, sr={sr}")

        if len(audio.shape) == 1:
            audio = np.stack([audio, audio], axis=0)
        elif audio.shape[0] == 1:
            audio = np.tile(audio[0], (2, 1))

        # 音频长度检查（STFT 需要足够的采样点）
        if audio.shape[-1] < 100:
            print(f"[ChainedSeparator] Audio too short ({audio.shape[-1]} samples), skipping separation")
            print(f"[ChainedSeparator] File may be corrupted or empty (size={file_size} bytes)")
            return result

        mix = torch.from_numpy(audio).float()
        if mix.dim() == 2 and mix.shape[0] > 2 and mix.shape[1] <= 2:
            mix = mix.T
        elif mix.dim() == 1:
            mix = mix.unsqueeze(0)
            mix = torch.cat([mix, mix], dim=0)

        # 保存原始 mix 用于可能的算术相减 fallback
        mix_np = mix.double().numpy()

        vocal_np = None
        instrumental_np = None
        raw_kim_vocal_np = None  # 保留 kim 原始人声，用于伴奏计算（对齐 SVC Fusion）

        # Step 1: Kim 人声提取
        if use_kim_vocal and "kim_vocal" in self._loaded_stages:
            print("[ChainedSeparator] Stage 1/3: Kim vocal extraction...")
            vocal_np = self._run_stage("kim_vocal", mix)
            if vocal_np is not None:
                raw_kim_vocal_np = vocal_np.copy()  # 保存原始 kim 人声用于伴奏计算
                print(f"[ChainedSeparator] Kim vocal extracted, peak: {np.abs(vocal_np).max():.4f}")
        else:
            # Fallback: 用通用 mel_band_roformer
            print("[ChainedSeparator] Stage 1/3: Fallback to mel_band_roformer...")
            if "mel_band_roformer" in self._loaded_stages:
                vocal_np = self._run_stage("mel_band_roformer", mix)
                if vocal_np is not None:
                    raw_kim_vocal_np = vocal_np.copy()  # fallback 也保存用于伴奏计算

        # Step 2: 去混响
        if use_deverb and vocal_np is not None and "deverb" in self._loaded_stages:
            print("[ChainedSeparator] Stage 2/3: De-reverb...")
            # 将人声转为 float32 tensor 送入去混响模型
            deverb_input = torch.from_numpy(vocal_np.astype(np.float32))
            deverb_np = self._run_stage("deverb", deverb_input)
            if deverb_np is not None:
                vocal_np = deverb_np
                print(f"[ChainedSeparator] De-reverb done, peak: {np.abs(vocal_np).max():.4f}")

        # Step 3: Karaoke 人声精炼 — 已禁用
        # 实测发现算术相减 (vocal - karaoke_residual) 会导致音量忽大忽小，
        # 因为 karaoke 模型在不同段落对人声的识别不稳定，减去后会引入音量波动。
        # 伴奏使用 mix - kim_vocal（算术相减），质量足够好。
        # 如果未来需要启用，需要用频域掩码而非时域相减。
        if False and use_karaoke and vocal_np is not None and "karaoke" in self._loaded_stages:
            print("[ChainedSeparator] Stage 3/3: Karaoke vocal refinement (DISABLED)...")

        # 保存结果
        if vocal_np is not None:
            # 人声后处理：80Hz 高通 + soft-clip + RMS 归一化
            vocal_np = SeparatorModel._apply_highpass(vocal_np, 80, self.sample_rate, order=4)
            threshold = 0.95
            mask = np.abs(vocal_np) > threshold
            if mask.any():
                over = np.sign(vocal_np) * (np.abs(vocal_np) - threshold)
                vocal_np = np.where(mask, np.sign(vocal_np) * (threshold + np.tanh(over * 5) * 0.05), vocal_np)

            # RMS 归一化到目标电平（-3 dBFS = 0.707 RMS），解决音量忽大忽小问题
            target_rms = 0.707
            current_rms = np.sqrt(np.mean(vocal_np ** 2))
            if current_rms > 1e-6:
                gain = target_rms / current_rms
                # 限制增益范围 ±6dB，避免过度放大或压缩
                gain = np.clip(gain, 0.5, 2.0)
                vocal_np = vocal_np * gain

            peak = np.abs(vocal_np).max()
            if peak > 0.99:
                vocal_np = vocal_np * (0.95 / peak)

            vocal_path = os.path.join(output_dir, "vocals.wav")
            self._save_wav(vocal_path, vocal_np, self.sample_rate)
            result.vocals = vocal_path

        # 伴奏：始终使用 mix - kim_vocal_raw（对齐 SVC Fusion 的 real_inst_path 逻辑）
        # SVC Fusion 的伴奏来源固定为 kim_vocal 阶段的 mix - vocal，不使用 karaoke 模型输出
        if raw_kim_vocal_np is not None:
            print("[ChainedSeparator] Instrumental = mix - kim_vocal (SVC Fusion method)")
            min_len = min(mix_np.shape[-1], raw_kim_vocal_np.shape[-1])
            instrumental_np = mix_np[..., :min_len] - raw_kim_vocal_np[..., :min_len]
        elif vocal_np is not None:
            print("[ChainedSeparator] Instrumental = mix - final_vocal (fallback)")
            min_len = min(mix_np.shape[-1], vocal_np.shape[-1])
            instrumental_np = mix_np[..., :min_len] - vocal_np[..., :min_len]

        if instrumental_np is not None:
            # 自适应频谱人声抑制后处理
            if vocal_np is not None:
                instrumental_np = ChainedSeparator._reduce_vocal_leakage(
                    instrumental_np, vocal_np, self.sample_rate
                )

            peak = np.abs(instrumental_np).max()
            if peak > 0.99:
                instrumental_np = instrumental_np * (0.95 / peak)

            inst_path = os.path.join(output_dir, "other.wav")
            self._save_wav(inst_path, instrumental_np, self.sample_rate)
            result.other = inst_path

        # 如果都没有成功，用 HPSS fallback
        if vocal_np is None and instrumental_np is None:
            print("[ChainedSeparator] All models failed, using HPSS fallback")
            audio_tc = audio.T
            hpss_vocal = SeparatorModel._hpss_vocal_extraction(audio_tc)
            vocal_path = os.path.join(output_dir, "vocals.wav")
            self._save_wav(vocal_path, hpss_vocal, self.sample_rate)
            result.vocals = vocal_path

            min_len = min(audio_tc.shape[0], hpss_vocal.shape[0])
            other = audio_tc[:min_len] - hpss_vocal[:min_len]
            inst_path = os.path.join(output_dir, "other.wav")
            self._save_wav(inst_path, other, self.sample_rate)
            result.other = inst_path

        return result

    @staticmethod
    def _reduce_vocal_leakage(
        inst_np: np.ndarray,
        vocal_np: np.ndarray,
        sample_rate: int = 44100,
        strength: float = 0.5,
    ) -> np.ndarray:
        """自适应频谱人声抑制：使用已分离人声作为参考，精确消除伴奏中的人声残留。

        速度：O(N log N)，仅 FFT 运算，比模型推理快 100x+，对处理速度无感知影响。

        算法原理：
        1. 对伴奏和人声分别做 STFT
        2. 计算人声在各时间-频率 bin 的能量
        3. 对人声能量做时间平滑（约 0.3 秒窗口），消除瞬态抖动
        4. 在人声主频段 (150-5000 Hz) 内，根据人声能量自适应抑制伴奏对应频段
        5. 抑制深度上限 -8 dB，保护共享频段的乐器（如吉他、钢琴和人声重叠区域）

        Args:
            inst_np: (C, T) float64 伴奏音频
            vocal_np: (C, T) float64 已分离人声（用作参考）
            sample_rate: 采样率
            strength: 0.0~1.0 整体抑制强度，默认 0.5（平衡效果和音质）

        Returns:
            处理后的伴奏 (C, T) float64
        """
        try:
            import librosa
            n_fft = 2048
            hop_length = 512
            win_length = 2048

            vocal_low_hz = 150
            vocal_high_hz = 5000
            max_suppression_db = 8.0  # 最大抑制 8 dB（保护乐器）

            # 生成频率 mask：仅在人声主频段内抑制
            freq_bins = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
            vocal_band_mask = (freq_bins >= vocal_low_hz) & (freq_bins <= vocal_high_hz)
            # 边缘渐变（避免硬截止产生伪影）
            edge_bins = 4
            fade_mask = vocal_band_mask.astype(np.float64)
            for i in range(edge_bins):
                t = (i + 1) / (edge_bins + 1)
                # 低频边缘
                idx_low = np.where(vocal_band_mask)[0]
                if len(idx_low) > 0 and idx_low[0] > 0:
                    fi = idx_low[0] - edge_bins + i
                    if 0 <= fi < len(fade_mask):
                        fade_mask[fi] = max(fade_mask[fi], t)
                # 高频边缘
                if len(idx_low) > 0:
                    fi = idx_low[-1] + edge_bins - i
                    if 0 <= fi < len(fade_mask):
                        fade_mask[fi] = max(fade_mask[fi], t)

            result_channels = []
            for ch in range(inst_np.shape[0]):
                inst_ch = inst_np[ch].astype(np.float64)
                vocal_ch = vocal_np[ch].astype(np.float64)

                min_len = min(len(inst_ch), len(vocal_ch))
                inst_ch = inst_ch[:min_len]
                vocal_ch = vocal_ch[:min_len]

                # STFT
                inst_stft = librosa.stft(inst_ch, n_fft=n_fft, hop_length=hop_length, win_length=win_length)
                vocal_stft = librosa.stft(vocal_ch, n_fft=n_fft, hop_length=hop_length, win_length=win_length)

                inst_mag = np.abs(inst_stft)
                inst_phase = np.angle(inst_stft)
                vocal_mag = np.abs(vocal_stft)

                # 人声能量 (功率谱)
                vocal_power = vocal_mag ** 2

                # 时间维度平滑（0.3 秒窗口），避免瞬态噪声误触发
                smooth_frames = max(1, int(0.3 * sample_rate / hop_length))
                if smooth_frames > 1:
                    kernel = np.hanning(smooth_frames * 2 + 1)
                    kernel = kernel / kernel.sum()
                    # 对每个频率 bin 独立平滑
                    for f in range(vocal_power.shape[0]):
                        vocal_power[f] = np.convolve(vocal_power[f], kernel, mode='same')

                # 全局平均能量（归一化用，避免静默段误触发）
                global_avg = np.mean(vocal_power) + 1e-12

                # 计算自适应抑制因子
                # relative_energy > 1 时开始抑制，越高抑制越强
                relative_energy = vocal_power / global_avg

                # sigmoid 映射：relative_energy 从 0→1 映射到 suppression 从 0→strength
                suppression = strength / (1.0 + np.exp(-3.0 * (relative_energy - 0.8)))

                # 仅在人声频段内抑制
                suppression *= fade_mask[np.newaxis, :]

                # 转为线性增益（dB → 线性）
                gain = 10.0 ** (-suppression * max_suppression_db / 20.0)

                # 应用抑制
                inst_mag_cleaned = inst_mag * gain

                # 重构信号
                inst_stft_cleaned = inst_mag_cleaned * np.exp(1j * inst_phase)
                inst_cleaned = librosa.istft(
                    inst_stft_cleaned, hop_length=hop_length, win_length=win_length, length=min_len
                )

                result_channels.append(inst_cleaned)

            # 对齐到原始长度
            target_len = inst_np.shape[-1]
            result = np.zeros_like(inst_np)
            for ch, cleaned in enumerate(result_channels):
                copy_len = min(len(cleaned), target_len)
                result[ch, :copy_len] = cleaned[:copy_len]

            leakage_before = np.mean(np.abs(inst_np)) if inst_np.size > 0 else 0
            leakage_after = np.mean(np.abs(result)) if result.size > 0 else 0
            print(
                f"[ChainedSeparator] Vocal leakage suppression applied "
                f"(strength={strength:.1f}, "
                f"rms: {leakage_before:.4f} -> {leakage_after:.4f})"
            )
            return result

        except Exception as e:
            print(f"[ChainedSeparator] Vocal leakage suppression failed: {e}")
            return inst_np

    def unload_all(self):
        """卸载所有模型，释放 GPU 显存"""
        for stage in list(self.models.keys()):
            model = self.models[stage][0]
            del model
        self.models.clear()
        self._loaded_stages.clear()
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[ChainedSeparator] All models unloaded")


def create_chained_separator(
    stages: Optional[List[str]] = None,
    device: Optional[str] = None,
) -> ChainedSeparator:
    """创建并加载链式分离器。

    Args:
        stages: 要加载的阶段列表，默认 ["kim_vocal", "deverb", "karaoke"]
        device: 设备，默认自动检测
    """
    cs = ChainedSeparator(device=device)
    cs.load(stages)
    return cs


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="音频分离模型")
    parser.add_argument("input", help="输入音频文件")
    parser.add_argument("output", help="输出目录")
    parser.add_argument("--model", default="mel_band_roformer", help="模型类型")
    args = parser.parse_args()

    model = create_separator_model(args.model)
    result = model.separate(args.input, args.output)
    print(f"分离完成: {result.to_dict()}")
