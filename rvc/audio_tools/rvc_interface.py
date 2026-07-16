"""
RVC 整合包接口模块
提供与 RVC 整合包的无缝集成接口
"""

import os
import sys
import torch
import numpy as np
from typing import Optional, Dict, List, Tuple, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .slicer import Slicer, AudioSlicer
from .separator_legacy import VocalSeparator, DemucsSeparator
from .vocoder import PhaseVocoder, PitchShifter, F0Extractor, pitch_shift_audio
from .mixer import AutoMixer, AudioMixer, simple_mix


class RVCAudioTools:
    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = 44100

        self.slicer = None
        self.separator = None
        self.pitch_shifter = None
        self.mixer = None

    def initialize(self, config: Optional[Dict] = None):
        if config is None:
            config = {}

        model_type = config.get("model_type", "mel_band_roformer")
        separator_model = config.get("separator_model")
        separator_config = config.get("separator_config")

        self.separator = VocalSeparator(
            model_type=model_type,
            model_path=separator_model,
            config_path=separator_config,
            device=self.device,
        )

        self.pitch_shifter = PitchShifter(
            sample_rate=self.sample_rate,
            hop_size=config.get("hop_size", 512),
        )

        self.mixer = AutoMixer(
            sample_rate=self.sample_rate,
            target_loudness=config.get("target_loudness", -14.0),
        )

        self.slicer = AudioSlicer()

        print(f"[RVCAudioTools] Initialized on device: {self.device}")

    def process_audio(
        self,
        audio_path: str,
        task: str,
        output_dir: str = "output",
        **kwargs,
    ) -> Dict:
        os.makedirs(output_dir, exist_ok=True)

        if task == "slice":
            return self._process_slice(audio_path, output_dir, **kwargs)
        elif task == "separate":
            return self._process_separate(audio_path, output_dir, **kwargs)
        elif task == "pitch_shift":
            return self._process_pitch_shift(audio_path, output_dir, **kwargs)
        elif task == "mix":
            return self._process_mix(audio_path, output_dir, **kwargs)
        elif task == "auto_mix":
            return self._process_auto_mix(audio_path, output_dir, **kwargs)
        else:
            raise ValueError(f"Unknown task: {task}")

    def _process_slice(
        self,
        audio_path: str,
        output_dir: str,
        **kwargs,
    ) -> Dict:
        top_db = kwargs.get("top_db", 60)
        min_duration = kwargs.get("min_duration", 5.0)
        max_duration = kwargs.get("max_duration", 30.0)

        saved_files = self.slicer.cut_by_silence(
            audio_path,
            output_dir,
            min_duration=min_duration,
            max_duration=max_duration,
            top_db=top_db,
        )

        return {
            "status": "success",
            "task": "slice",
            "output_files": saved_files,
            "num_files": len(saved_files),
        }

    def _process_separate(
        self,
        audio_path: str,
        output_dir: str,
        **kwargs,
    ) -> Dict:
        instruments = kwargs.get("instruments", ["vocals", "drums", "bass", "other"])

        if self.separator.model is None and self.separator.model_path is None:
            default_model_path = kwargs.get("model_path")
            default_config = kwargs.get("config_path")
            if default_model_path:
                self.separator.load_model(default_model_path, default_config)

        results = self.separator.separate(audio_path, output_dir, instruments)

        return {
            "status": "success",
            "task": "separate",
            "output_files": results,
            "instruments": instruments,
        }

    def _process_pitch_shift(
        self,
        audio_path: str,
        output_dir: str,
        **kwargs,
    ) -> Dict:
        n_steps = kwargs.get("n_steps", 0)
        method = kwargs.get("method", "librosa")

        base_name = os.path.basename(audio_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(output_dir, f"{name}_shifted{ext}")

        pitch_shift_audio(audio_path, output_path, n_steps, method)

        return {
            "status": "success",
            "task": "pitch_shift",
            "output_file": output_path,
            "n_steps": n_steps,
            "method": method,
        }

    def _process_mix(
        self,
        audio_path: str,
        output_dir: str,
        **kwargs,
    ) -> Dict:
        instrumental_path = kwargs.get("instrumental_path")
        vocal_ratio = kwargs.get("vocal_ratio", 1.0)
        instrumental_ratio = kwargs.get("instrumental_ratio", 1.0)

        if instrumental_path is None:
            return {
                "status": "error",
                "message": "instrumental_path is required for mix task",
            }

        base_name = os.path.basename(audio_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(output_dir, f"{name}_mixed{ext}")

        simple_mix(
            audio_path,
            instrumental_path,
            output_path,
            vocal_ratio=vocal_ratio,
            instrumental_ratio=instrumental_ratio,
        )

        return {
            "status": "success",
            "task": "mix",
            "output_file": output_path,
        }

    def _process_auto_mix(
        self,
        audio_path: str,
        output_dir: str,
        **kwargs,
    ) -> Dict:
        vocal_volume = kwargs.get("vocal_volume", 1.0)
        instrumental_volume = kwargs.get("instrumental_volume", 1.0)
        vocal_ducking = kwargs.get("vocal_ducking", 0.3)

        separated = self.separator.separate(
            audio_path,
            os.path.join(output_dir, "separated"),
            ["vocals", "other"],
        )

        base_name = os.path.basename(audio_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(output_dir, f"{name}_automix{ext}")

        vocals_path = separated.get("vocals")
        other_path = separated.get("other")

        if vocals_path and other_path:
            import soundfile as sf
            vocals, sr = sf.read(vocals_path)
            other, _ = sf.read(other_path)

            vocals = vocals.T if len(vocals.shape) > 1 else np.stack([vocals, vocals])
            other = other.T if len(other.shape) > 1 else np.stack([other, other])

            mixed = self.mixer.smart_mix(
                vocals,
                other,
                vocal_ducking=vocal_ducking,
            )

            if isinstance(mixed, tuple):
                mixed = mixed[0]

            sf.write(output_path, mixed, sr)
        else:
            import shutil
            shutil.copy(audio_path, output_path)

        return {
            "status": "success",
            "task": "auto_mix",
            "output_file": output_path,
            "separated_files": separated,
        }

    def extract_f0(
        self,
        audio_path: str,
        extractor: str = "pyin",
        **kwargs,
    ) -> np.ndarray:
        import librosa

        audio, sr = librosa.load(audio_path, sr=self.sample_rate, mono=False)
        if len(audio.shape) > 1:
            audio = audio[0]

        f0_extractor = F0Extractor(
            extractor=extractor,
            sample_rate=sr,
            hop_size=kwargs.get("hop_size", 512),
        )

        f0 = f0_extractor.extract(audio, uv_interp=kwargs.get("uv_interp", True))

        return f0


class RVCProcessPipeline:
    def __init__(self, device: Optional[str] = None):
        self.tools = RVCAudioTools(device=device)
        self.device = self.tools.device

    def run_full_pipeline(
        self,
        audio_path: str,
        tasks: List[str],
        output_dir: str = "output",
        **kwargs,
    ) -> Dict:
        results = {}
        current_path = audio_path

        for task in tasks:
            print(f"[Pipeline] Running task: {task}")

            result = self.tools.process_audio(
                current_path,
                task,
                output_dir=output_dir,
                **kwargs,
            )

            results[task] = result

            if result.get("status") == "success":
                if "output_file" in result:
                    current_path = result["output_file"]
                elif "output_files" in result and result["output_files"]:
                    current_path = result["output_files"][0]

        results["final_output"] = current_path
        return results


def create_rvc_interface(config: Optional[Dict] = None) -> RVCAudioTools:
    tools = RVCAudioTools()
    tools.initialize(config)
    return tools


def quick_separate(
    audio_path: str,
    output_dir: str = "separated",
    model_type: str = "mel_band_roformer",
) -> Dict[str, str]:
    tools = RVCAudioTools()
    return tools.process_audio(
        audio_path,
        "separate",
        output_dir=output_dir,
        model_type=model_type,
    )


def quick_pitch_shift(
    audio_path: str,
    output_path: str,
    n_steps: float,
) -> str:
    return pitch_shift_audio(audio_path, output_path, n_steps)


def quick_mix(
    vocal_path: str,
    instrumental_path: str,
    output_path: str,
    vocal_ratio: float = 1.0,
    instrumental_ratio: float = 1.0,
) -> str:
    return simple_mix(
        vocal_path,
        instrumental_path,
        output_path,
        vocal_ratio=vocal_ratio,
        instrumental_ratio=instrumental_ratio,
    )
