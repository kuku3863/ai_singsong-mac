# -*- coding: utf-8 -*-
"""
自动混音引擎 - 基于 pedalboard 的专业级人声后处理与混音
移植自 SVC Fusion 项目 automix.py (by C_Zim)

提供：
  - 专业级人声处理链（EQ、压缩、去齿音、混响、回声）
  - 基于音乐风格和人声类型的智能参数预设
  - 基于节拍分析的时间参数自动计算
  - 总线压缩与限幅
"""

import tempfile
import warnings
from typing import Tuple, List
from enum import Enum

import numpy as np
import soundfile as sf

warnings.filterwarnings("ignore")


# ============================================================
# 枚举定义
# ============================================================

class ReverbLevel(Enum):
    """混响等级"""
    DRY = 0
    SUBTLE = 1
    LIGHT = 2
    MODERATE = 3
    HEAVY = 4
    EXTREME = 5


class MusicGenre(Enum):
    """音乐风格"""
    POP = "pop"
    ROCK = "rock"
    JAZZ = "jazz"
    ELECTRONIC = "electronic"
    FOLK = "folk"
    CLASSICAL = "classical"


class VoiceType(Enum):
    """人声类型"""
    MALE_LOW = "male_low"
    MALE_HIGH = "male_high"
    FEMALE = "female"
    RAP = "rap"
    VOCAL = "vocal"


class DeEsserStrength(Enum):
    """去齿音强度"""
    OFF = 0
    LIGHT = 1
    MODERATE = 2
    HEAVY = 3


class CompressionStrength(Enum):
    """压缩强度"""
    LIGHT = 1
    MODERATE = 2
    HEAVY = 3


class EQStyle(Enum):
    """EQ风格"""
    NEUTRAL = "neutral"
    BRIGHT = "bright"
    WARM = "warm"
    VINTAGE = "vintage"


class EchoLevel(Enum):
    """回声等级"""
    OFF = 0
    SUBTLE = 1
    LIGHT = 2
    MODERATE = 3
    HEAVY = 4
    EXTREME = 5


# ============================================================
# 节拍时间计算器
# ============================================================

class TimeCalculator:
    """基于音频节拍的时间参数计算"""

    def __init__(self, inst_path: str):
        try:
            import librosa
            y, sr = librosa.load(inst_path, sr=None)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = round(int(tempo), 0)
        except Exception:
            bpm = 120  # 默认 BPM
        if bpm is None or bpm <= 0:
            bpm = 120
        if bpm >= 100:
            bpm = bpm / 2
        self.basic_time = 60000 / bpm
        self.times = {
            "pre_delay": self.reverb_pre_delay(),
            "release": self.compressor_release(),
        }

    def _calculate_time(self, times: List[float]) -> List[float]:
        stop = 0
        for time in times[:]:
            half_time = time / 2
            times.append(half_time)
            stop += 1
            if stop >= 15:
                break
        return times[:]

    def _select_time(
        self,
        time_lists: List[float],
        standard_value: float,
        standard_range: float,
        double_mode: bool = False,
    ) -> float:
        if min(time_lists) >= standard_range:
            return standard_value * 2 if double_mode else standard_value
        min_diff = float("inf")
        closest_num = standard_value
        for time_value in time_lists:
            diff = abs(time_value - standard_value)
            if diff < min_diff:
                min_diff = diff
                closest_num = time_value
        return closest_num * 2 if double_mode else closest_num

    def _note(self, rate: float, mode: int) -> List[float]:
        if mode == 0:
            note = self.basic_time * rate
        elif mode == 1:
            note = self.basic_time / rate
        else:
            raise ValueError("Mode must be 0 or 1")
        dot = note * 1.5
        triplet = note * 2 / 3
        bases = [note, dot, triplet]
        fulls = self._calculate_time(bases)
        return sorted(fulls)

    def reverb_pre_delay(self) -> Tuple[float, float, float, float]:
        pre_delay_raws = self._note(8, 1)
        pre_delays = [round(pre_delay, 2) for pre_delay in pre_delay_raws]
        room_er = self._select_time(pre_delays, 0.6, 1, True)
        room_lr = self._select_time(pre_delays, 2, 4, True)
        plate = self._select_time(pre_delays, 10, 20, True)
        hall = self._select_time(pre_delays, 20, 40, True)
        return room_er, room_lr, plate, hall

    def compressor_release(self) -> Tuple[float, float, float, float]:
        release_raws = self._note(2, 0)
        releases = [round(release, 1) for release in release_raws]
        fast = self._select_time(releases, 100, 200)
        medium = self._select_time(releases, 350, 500)
        slow = self._select_time(releases, 500, 1000)
        limiter = self._select_time(releases, 450, 800)
        return fast, medium, slow, limiter


# ============================================================
# 参数获取函数
# ============================================================

def get_genre_parameters(genre) -> dict:
    parameters = {
        MusicGenre.POP: {
            "vocal_brightness": 0, "compression_ratio": 2.5,
            "reverb_adjustment": 0, "high_shelf_gain": 0,
        },
        MusicGenre.ROCK: {
            "vocal_brightness": 2, "compression_ratio": 3.5,
            "reverb_adjustment": -3, "high_shelf_gain": 2,
        },
        MusicGenre.JAZZ: {
            "vocal_brightness": -1, "compression_ratio": 1.8,
            "reverb_adjustment": 2, "high_shelf_gain": -1,
        },
        MusicGenre.ELECTRONIC: {
            "vocal_brightness": 3, "compression_ratio": 4.0,
            "reverb_adjustment": 0, "high_shelf_gain": 3,
        },
        MusicGenre.FOLK: {
            "vocal_brightness": -2, "compression_ratio": 1.5,
            "reverb_adjustment": 1, "high_shelf_gain": -2,
        },
        MusicGenre.CLASSICAL: {
            "vocal_brightness": -1, "compression_ratio": 1.2,
            "reverb_adjustment": 4, "high_shelf_gain": 0,
        },
    }
    return parameters.get(genre, parameters[MusicGenre.POP])


def get_voice_type_parameters(voice_type) -> dict:
    parameters = {
        VoiceType.MALE_LOW: {
            "highpass_freq": 80, "presence_freq": 2500,
            "presence_gain": 2, "brightness_freq": 8000, "brightness_gain": 1,
        },
        VoiceType.MALE_HIGH: {
            "highpass_freq": 100, "presence_freq": 3000,
            "presence_gain": 3, "brightness_freq": 10000, "brightness_gain": 2,
        },
        VoiceType.FEMALE: {
            "highpass_freq": 120, "presence_freq": 3500,
            "presence_gain": 2.5, "brightness_freq": 12000, "brightness_gain": 2.5,
        },
        VoiceType.RAP: {
            "highpass_freq": 150, "presence_freq": 4000,
            "presence_gain": 4, "brightness_freq": 8000, "brightness_gain": 3,
        },
        VoiceType.VOCAL: {
            "highpass_freq": 60, "presence_freq": 2000,
            "presence_gain": 1, "brightness_freq": 10000, "brightness_gain": 1,
        },
    }
    return parameters.get(voice_type, parameters[VoiceType.FEMALE])


def get_deesser_parameters(strength) -> dict:
    parameters = {
        DeEsserStrength.OFF: {"freq": 0, "gain": 0, "q": 1},
        DeEsserStrength.LIGHT: {"freq": 6500, "gain": -2, "q": 2},
        DeEsserStrength.MODERATE: {"freq": 6000, "gain": -4, "q": 2.5},
        DeEsserStrength.HEAVY: {"freq": 5500, "gain": -6, "q": 3},
    }
    return parameters.get(strength, parameters[DeEsserStrength.OFF])


def get_eq_style_parameters(style) -> dict:
    parameters = {
        EQStyle.NEUTRAL: {"low_shelf_gain": 0, "mid_gain": 0, "high_shelf_gain": 0},
        EQStyle.BRIGHT: {"low_shelf_gain": -1, "mid_gain": 1, "high_shelf_gain": 3},
        EQStyle.WARM: {"low_shelf_gain": 2, "mid_gain": -1, "high_shelf_gain": -2},
        EQStyle.VINTAGE: {"low_shelf_gain": 1, "mid_gain": 2, "high_shelf_gain": -3},
    }
    return parameters.get(style, parameters[EQStyle.NEUTRAL])


def get_reverb_parameters(level) -> Tuple[float, float, float, float]:
    parameters = {
        ReverbLevel.DRY: (0.0, 1.0, 0.0, -60),
        ReverbLevel.SUBTLE: (0.2, 0.8, 0.1, -18),
        ReverbLevel.LIGHT: (0.3, 0.7, 0.2, -12),
        ReverbLevel.MODERATE: (0.5, 0.6, 0.3, -6),
        ReverbLevel.HEAVY: (0.7, 0.4, 0.5, 0),
        ReverbLevel.EXTREME: (0.9, 0.2, 0.7, 3),
    }
    return parameters.get(level, parameters[ReverbLevel.MODERATE])


def get_echo_parameters(level, basic_time: float) -> dict:
    parameters = {
        EchoLevel.OFF: {
            "delay_time": 0, "feedback": 0, "wet_level": 0, "gain_adjustment": 0,
        },
        EchoLevel.SUBTLE: {
            "delay_time": 60, "feedback": 0.05, "wet_level": 0.08, "gain_adjustment": -4,
        },
        EchoLevel.LIGHT: {
            "delay_time": 120, "feedback": 0.1, "wet_level": 0.15, "gain_adjustment": -2,
        },
        EchoLevel.MODERATE: {
            "delay_time": min(basic_time / 8, 200), "feedback": 0.2,
            "wet_level": 0.25, "gain_adjustment": 0,
        },
        EchoLevel.HEAVY: {
            "delay_time": min(basic_time / 4, 350), "feedback": 0.3,
            "wet_level": 0.4, "gain_adjustment": 1,
        },
        EchoLevel.EXTREME: {
            "delay_time": min(basic_time / 2, 500), "feedback": 0.45,
            "wet_level": 0.6, "gain_adjustment": 2,
        },
    }
    return parameters.get(level, parameters[EchoLevel.OFF])


# ============================================================
# 效果器处理链构建
# ============================================================

def _ensure_pedalboard():
    """确保 pedalboard 已安装"""
    try:
        from pedalboard import Pedalboard, Gain, HighpassFilter, PeakFilter
        from pedalboard import HighShelfFilter, LowShelfFilter, Delay
        from pedalboard import Invert, Compressor, Reverb, Limiter, Mix
        from pedalboard.io import AudioFile
        return True
    except ImportError:
        return False


def create_vocal_chain(
    voc_input: float,
    release: float = 300,
    feedback: float = 180,
    genre=MusicGenre.POP,
    voice_type=VoiceType.FEMALE,
    deesser_strength=DeEsserStrength.MODERATE,
    compression_strength=CompressionStrength.MODERATE,
    eq_style=EQStyle.NEUTRAL,
    echo_level=EchoLevel.OFF,
    basic_time: float = 500,
):
    """创建人声处理链（返回 pedalboard.Pedalboard 实例）"""
    from pedalboard import (
        Pedalboard, Gain, HighpassFilter, PeakFilter, HighShelfFilter,
        LowShelfFilter, Delay, Invert, Compressor, Reverb, Limiter, Mix,
    )

    genre_params = get_genre_parameters(genre)
    voice_params = get_voice_type_parameters(voice_type)
    deesser_params = get_deesser_parameters(deesser_strength)
    eq_params = get_eq_style_parameters(eq_style)

    compression_ratios = {
        CompressionStrength.LIGHT: 1.8,
        CompressionStrength.MODERATE: 2.5,
        CompressionStrength.HEAVY: 3.5,
    }
    base_ratio = compression_ratios[compression_strength]
    final_ratio = base_ratio * (genre_params["compression_ratio"] / 2.5)

    effects = [
        Gain(voc_input),
        HighpassFilter(voice_params["highpass_freq"]),
    ]

    if eq_params["low_shelf_gain"] != 0:
        effects.append(LowShelfFilter(200, eq_params["low_shelf_gain"], 0.7))

    effects.extend([
        PeakFilter(
            2700 + voice_params["presence_freq"] - 2500,
            -2 + eq_params["mid_gain"], 1,
        ),
        HighShelfFilter(
            20000,
            -2 + eq_params["high_shelf_gain"] + genre_params["high_shelf_gain"],
            1.8,
        ),
        Gain(1),
        PeakFilter(
            voice_params["presence_freq"],
            voice_params["presence_gain"] + genre_params["vocal_brightness"],
            1.15,
        ),
        PeakFilter(
            voice_params["brightness_freq"],
            voice_params["brightness_gain"] + genre_params["vocal_brightness"],
            1,
        ),
    ])

    if deesser_strength != DeEsserStrength.OFF:
        effects.append(
            PeakFilter(deesser_params["freq"], deesser_params["gain"], deesser_params["q"])
        )

    if echo_level != EchoLevel.OFF:
        echo_params = get_echo_parameters(echo_level, basic_time)
        delay_time_seconds = echo_params["delay_time"] / 1000
        effects.append(
            Pedalboard([
                Delay(delay_time_seconds, echo_params["feedback"], echo_params["wet_level"]),
                Gain(echo_params["gain_adjustment"]),
            ])
        )

    effects.extend([
        Gain(-1),
        Mix([
            Gain(0),
            Pedalboard([Invert(), Compressor(-30, 3.2, 40, feedback), Gain(-40)]),
        ]),
        Compressor(-18, final_ratio, 19, release),
        Gain(0),
    ])

    return Pedalboard(effects)


def create_reverb_chain(
    reverb_gain: float,
    short: float = 5,
    medium: float = 25,
    long: float = 50,
    delay: float = 200,
    level=ReverbLevel.MODERATE,
):
    """创建混响处理链"""
    from pedalboard import Pedalboard, Gain, Delay, Reverb, PeakFilter, Mix

    room_size, damping, wet_level, gain_adjustment = get_reverb_parameters(level)

    if level == ReverbLevel.DRY:
        return Pedalboard([Gain(reverb_gain + gain_adjustment)])

    adjusted_reverb_gain = reverb_gain + gain_adjustment

    delay_chain = Pedalboard([
        Gain(-20), Delay(delay / 8, 0, wet_level * 0.3), Gain(-12),
    ])
    short_reverb = Pedalboard([
        Gain(-20), Delay(short / 1000, 0, wet_level * 0.2),
        Reverb(room_size * 0.4, damping, wet_level, 0, 1, 0), Gain(-12),
    ])
    medium_reverb = Pedalboard([
        Gain(-16), Delay(medium / 1000, 0.3, wet_level * 0.4),
        Reverb(room_size * 0.7, damping, wet_level, 0, 1, 0), Gain(-19),
    ])
    long_reverb = Pedalboard([
        Gain(-12), Delay(long / 1000, 0.6, wet_level * 0.6),
        Reverb(room_size, damping, wet_level, 0, 1, 0), Gain(-23),
    ])

    return Pedalboard([
        Mix([short_reverb, medium_reverb, long_reverb, delay_chain]),
        PeakFilter(1450, -4, 1.83),
        PeakFilter(2300, 5, 0.51),
        Gain(adjusted_reverb_gain),
    ])


def create_instrument_chain(headroom: float):
    """创建乐器处理链"""
    from pedalboard import Pedalboard, Gain
    return Pedalboard([Gain(headroom)])


def create_master_chain(comp_release: float = 500, limiter_release: float = 400):
    """创建总线处理链"""
    from pedalboard import Pedalboard, Compressor, Limiter, Gain
    return Pedalboard([
        Compressor(-10, 1.6, 10, comp_release),
        Limiter(-3, limiter_release),
        Gain(-0.5),
    ])


# ============================================================
# 核心混音函数
# ============================================================

def _load_audio_pedalboard(path: str, sample_rate: int) -> np.ndarray:
    """使用 pedalboard 加载音频"""
    from pedalboard.io import AudioFile
    with AudioFile(path).resampled_to(sample_rate) as audio:
        data = audio.read(audio.frames)
    return data


def automix(
    voc_path: str,
    inst_path: str,
    sample_rate: int = 44100,
    reverb_gain: int = 0,
    headroom: int = -8,
    voc_input: int = -4,
    reverb_level=ReverbLevel.MODERATE,
    music_genre=MusicGenre.POP,
    voice_type=VoiceType.FEMALE,
    deesser_strength=DeEsserStrength.MODERATE,
    compression_strength=CompressionStrength.MODERATE,
    eq_style=EQStyle.NEUTRAL,
    echo_level=EchoLevel.OFF,
) -> str:
    """
    自动混音处理

    Args:
        voc_path: 人声文件路径
        inst_path: 伴奏文件路径
        sample_rate: 采样率 (默认 44100)
        reverb_gain: 混响增益 dB
        headroom: 乐器动态余量 dB
        voc_input: 人声输入增益 dB
        reverb_level: 混响等级
        music_genre: 音乐风格
        voice_type: 人声类型
        deesser_strength: 去齿音强度
        compression_strength: 压缩强度
        eq_style: EQ风格
        echo_level: 回声等级

    Returns:
        输出文件路径 (.flac)
    """
    # 计算时间参数
    time_calculator = TimeCalculator(inst_path)
    pre_delay = time_calculator.times["pre_delay"]
    release = time_calculator.times["release"]

    # 加载音频
    vocal_audio = _load_audio_pedalboard(voc_path, sample_rate)
    instrument_audio = _load_audio_pedalboard(inst_path, sample_rate)

    # 根据风格调整混响增益
    genre_params = get_genre_parameters(music_genre)
    adjusted_reverb_gain = reverb_gain + genre_params["reverb_adjustment"]

    # 创建处理链
    vocal_fx = create_vocal_chain(
        voc_input, release[1], release[0],
        music_genre, voice_type, deesser_strength,
        compression_strength, eq_style, echo_level,
        time_calculator.basic_time,
    )
    reverb_fx = create_reverb_chain(
        adjusted_reverb_gain,
        pre_delay[0], pre_delay[2], pre_delay[3], pre_delay[1],
        reverb_level,
    )
    instrument_fx = create_instrument_chain(headroom)
    master_fx = create_master_chain(release[3], release[2])

    # 处理人声
    processed_vocal = vocal_fx(vocal_audio, sample_rate)

    # 处理立体声
    if processed_vocal.ndim > 1 and processed_vocal.shape[0] > 2:
        stereo = np.mean(processed_vocal, axis=0, keepdims=True)
    else:
        stereo = processed_vocal

    # 处理混响和乐器
    reverb_audio = reverb_fx(stereo, sample_rate)
    processed_instrument = instrument_fx(instrument_audio, sample_rate)

    # 合并音频
    min_length = min(
        processed_vocal.shape[1],
        reverb_audio.shape[1],
        processed_instrument.shape[1],
    )
    combined_audio = (
        processed_vocal[:, :min_length]
        + reverb_audio[:, :min_length]
        + processed_instrument[:, :min_length]
    )

    # 主总线处理
    final_output = master_fx(combined_audio, sample_rate)

    # 输出文件
    output_path = tempfile.mktemp(suffix=".flac")
    sf.write(output_path, final_output.T, samplerate=sample_rate, format="flac")

    return output_path


def check_dependencies() -> Tuple[bool, str]:
    """检查 automix 所需依赖是否已安装

    Returns:
        (is_available, message)
    """
    missing = []
    try:
        import pedalboard
    except ImportError:
        missing.append("pedalboard")
    try:
        import librosa
    except ImportError:
        missing.append("librosa")
    try:
        import soundfile
    except ImportError:
        missing.append("soundfile")

    if missing:
        return False, f"缺少依赖: {', '.join(missing)}。请运行: pip install {' '.join(missing)}"
    return True, "自动混音模块就绪"
