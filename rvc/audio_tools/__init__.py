"""
Audio Tools Package
音频处理工具包 - 切片、人声分离、变调、混音
为 RVC 整合包设计，独立于 RVC 推理/训练流程
"""

__version__ = "1.1.0"

from .slicer import Slicer, AudioSlicer, trim_audio, split_stereo, normalize_audio, pad_audio
from .separator_model import SeparatorModel, create_separator_model, SeparationResult
from .vocoder import PhaseVocoder, TorchPhaseVocoder, PitchShifter, F0Extractor, pitch_shift_audio
from .mixer import AutoMixer, AudioMixer
from .mixer_model import MixerModel, MixingConfig, create_mixer, simple_mix
from .rvc_interface import (
    RVCAudioTools,
    RVCProcessPipeline,
    create_rvc_interface,
    quick_pitch_shift,
    quick_mix,
)

__all__ = [
    # Slicer
    "Slicer",
    "AudioSlicer",
    "trim_audio",
    "split_stereo",
    "normalize_audio",
    "pad_audio",
    # Separator
    "SeparatorModel",
    "create_separator_model",
    "SeparationResult",
    # Vocoder
    "PhaseVocoder",
    "TorchPhaseVocoder",
    "PitchShifter",
    "F0Extractor",
    "pitch_shift_audio",
    # Mixer
    "AutoMixer",
    "AudioMixer",
    "MixerModel",
    "MixingConfig",
    "create_mixer",
    "simple_mix",
    # Interface
    "RVCAudioTools",
    "RVCProcessPipeline",
    "create_rvc_interface",
    "quick_pitch_shift",
    "quick_mix",
]
