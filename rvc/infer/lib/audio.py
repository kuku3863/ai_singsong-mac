import platform, os, subprocess, ctypes, shutil
import logging
import ffmpeg
import numpy as np
import av
from io import BytesIO

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCAL_FFMPEG = os.path.join(BASE_DIR, "ffmpeg.exe")
FFMPEG_PATH = _LOCAL_FFMPEG if os.path.exists(_LOCAL_FFMPEG) else (shutil.which("ffmpeg") or "ffmpeg")

# 最大音频长度限制（采样点数），默认 600 秒 × 16000Hz = 9,600,000
MAX_AUDIO_SAMPLES = 9600000


def wav2(i, o, format):
    inp = av.open(i, "rb")
    if format == "m4a":
        format = "mp4"
    out = av.open(o, "wb", format=format)
    if format == "ogg":
        format = "libvorbis"
    if format == "mp4":
        format = "aac"

    ostream = out.add_stream(format)

    for frame in inp.decode(audio=0):
        for p in ostream.encode(frame):
            out.mux(p)

    for p in ostream.encode(None):
        out.mux(p)

    out.close()
    inp.close()


def _get_short_path(long_path):
    """获取 Windows 短路径名（8.3 格式），解决 ffmpeg 中文路径问题。"""
    try:
        buf_size = ctypes.c_uint32(260)
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, buf_size)
        short = buf.value
        if short and short != long_path:
            return short
    except Exception:
        pass
    return None


def load_audio(file, sr):
    if not file:
        raise RuntimeError("未选择音频文件，请上传音频后再试")
    
    try:
        file = clean_path(file)
        if not file:
            raise RuntimeError("音频文件路径无效")

        # Windows 下 ffmpeg 对中文/特殊字符路径报错，使用 Windows 短路径名（8.3格式）
        if platform.system() == "Windows":
            file = _get_short_path(file) or file

        out, err = (
            ffmpeg.input(file, threads=0)
            .output("-", format="f32le", acodec="pcm_f32le", ac=1, ar=sr)
            .run(cmd=[FFMPEG_PATH, "-nostdin"], capture_stdout=True, capture_stderr=True, overwrite_output=True)
        )
        if err:
            print(f"ffmpeg stderr: {err.decode('utf-8', errors='ignore')}")
    except ffmpeg._run.Error as e:
        err_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        raise RuntimeError(f"Failed to load audio: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Failed to load audio: {e}")

    audio = np.frombuffer(out, np.float32).flatten()

    # 防御性检查：空音频
    if len(audio) == 0:
        raise RuntimeError(f"音频文件为空或无法解码: {file}")

    # 防御性检查：限制最大长度，防止损坏/异常文件导致 GPU OOM
    if len(audio) > MAX_AUDIO_SAMPLES:
        duration_sec = len(audio) / sr
        max_sec = MAX_AUDIO_SAMPLES / sr
        logger.warning(
            f"音频过长 ({duration_sec:.1f}s)，截断到 {max_sec:.0f}s: {os.path.basename(file)}"
        )
        audio = audio[:MAX_AUDIO_SAMPLES]

    return audio


def clean_path(path_str):
    if platform.system() == "Windows":
        path_str = path_str.replace("/", "\\")
    return path_str.strip(" ").strip('"').strip("\n").strip('"').strip(" ")
