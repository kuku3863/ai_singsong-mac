import argparse
import logging
import os
import random
from concurrent.futures import ProcessPoolExecutor
from glob import glob
from random import shuffle

import librosa
import numpy as np
import torch
import torch.multiprocessing as mp
from loguru import logger
from tqdm import tqdm

import utils
import diffusion.logger.utils as du
from diffusion.vocoder import Vocoder
from modules.mel_processing import spectrogram_torch

logging.getLogger("numba").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# Removed global hps/sampling_rate/hop_length/speech_encoder to avoid config mismatch in process_one
# They are now updated in if __name__ == "__main__" and passed down if needed, 
# or re-read from the correct config inside process_one.

def _atomic_save_npy(path, array, allow_pickle=True):
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        np.save(f, array, allow_pickle=allow_pickle)
    os.replace(tmp_path, path)

def _needs_regen(path):
    try:
        return (not os.path.exists(path)) or os.path.getsize(path) == 0
    except Exception:
        return True


def process_one(filename, hmodel, f0_predictor, device, diff=False, mel_extractor=None, config_path="configs/config.json"):
    # Re-read hps inside process_one to ensure we use the correct sampling_rate and vol_embedding setting
    hps = utils.get_hparams_from_file(config_path)
    sampling_rate = hps.data.sampling_rate
    hop_length = hps.data.hop_length

    wav, sr = librosa.load(filename, sr=sampling_rate)
    audio_norm = torch.FloatTensor(wav)
    audio_norm = audio_norm.unsqueeze(0)
    soft_path = filename + ".soft.pt"
    if _needs_regen(soft_path):
        wav16k = librosa.resample(wav, orig_sr=sampling_rate, target_sr=16000)
        wav16k = torch.from_numpy(wav16k).to(device)
        c = hmodel.encoder(wav16k)
        torch.save(c.cpu(), soft_path)
        del c, wav16k

    f0_path = filename + ".f0.npy"
    if _needs_regen(f0_path):
        f0,uv = f0_predictor.compute_f0_uv(
            wav
        )
        _atomic_save_npy(f0_path, np.asanyarray((f0, uv), dtype=object), allow_pickle=True)


    spec_path = filename.replace(".wav", ".spec.pt")
    if _needs_regen(spec_path):
        # Process spectrogram
        # The following code can't be replaced by torch.FloatTensor(wav)
        # because load_wav_to_torch return a tensor that need to be normalized

        if sr != hps.data.sampling_rate:
            raise ValueError(
                "{} SR doesn't match target {} SR".format(
                    sr, hps.data.sampling_rate
                )
            )

        #audio_norm = audio / hps.data.max_wav_value

        spec = spectrogram_torch(
            audio_norm,
            hps.data.filter_length,
            hps.data.sampling_rate,
            hps.data.hop_length,
            hps.data.win_length,
            center=False,
        )
        spec = torch.squeeze(spec, 0)
        torch.save(spec, spec_path)

    if diff or hps.model.vol_embedding:
        volume_path = filename + ".vol.npy"
        volume_extractor = utils.Volume_Extractor(hop_length)
        # Always regenerate volume if vol_embedding is enabled, to ensure consistency
        volume = volume_extractor.extract(audio_norm)
        _atomic_save_npy(volume_path, volume.to("cpu").numpy(), allow_pickle=False)

    if diff:
        mel_path = filename + ".mel.npy"
        if mel_extractor is None:
            raise RuntimeError("diff mode requires mel_extractor (check diffusion vocoder ckpt and config)")
        if _needs_regen(mel_path):
            mel_t = mel_extractor.extract(audio_norm.to(device), sampling_rate)
            mel = mel_t.squeeze().to('cpu').numpy()
            _atomic_save_npy(mel_path, mel, allow_pickle=False)
        aug_mel_path = filename + ".aug_mel.npy"
        aug_vol_path = filename + ".aug_vol.npy"
        max_amp = float(torch.max(torch.abs(audio_norm))) + 1e-5
        max_shift = min(1, np.log10(1/max_amp))
        log10_vol_shift = random.uniform(-1, max_shift)
        keyshift = random.uniform(-5, 5)
        aug_mel_t = mel_extractor.extract(audio_norm.to(device) * (10 ** log10_vol_shift), sampling_rate, keyshift=keyshift)
        aug_mel = aug_mel_t.squeeze().to('cpu').numpy()
        aug_vol = volume_extractor.extract(audio_norm * (10 ** log10_vol_shift))
        if _needs_regen(aug_mel_path):
            _atomic_save_npy(aug_mel_path, np.asanyarray((aug_mel, keyshift), dtype=object), allow_pickle=True)
        if _needs_regen(aug_vol_path):
            _atomic_save_npy(aug_vol_path, aug_vol.to("cpu").numpy(), allow_pickle=False)


def process_batch(file_chunk, f0p, speech_encoder, diff=False, mel_extractor=None, device="cpu", config_path="configs/config.json"):
    logger.info("Loading speech encoder for content...")
    rank = mp.current_process()._identity
    rank = rank[0] if len(rank) > 0 else 0
    if torch.cuda.is_available():
        gpu_id = rank % torch.cuda.device_count()
        device = torch.device(f"cuda:{gpu_id}")
    logger.info(f"Rank {rank} uses device {device}")
    hmodel = utils.get_speech_encoder(speech_encoder, device=device)

    hps = utils.get_hparams_from_file(config_path)
    f0_predictor = utils.get_f0_predictor(f0p, sampling_rate=hps.data.sampling_rate, hop_length=hps.data.hop_length, device=device, threshold=0.05)

    logger.info(f"Loaded speech encoder for rank {rank}")
    for filename in tqdm(file_chunk, position = rank):
        process_one(filename, hmodel, f0_predictor, device, diff, mel_extractor, config_path)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

def parallel_process(filenames, num_processes, f0p, speech_encoder, diff, mel_extractor, device, config_path):
    with ProcessPoolExecutor(max_workers=num_processes) as executor:
        tasks = []
        for i in range(num_processes):
            start = int(i * len(filenames) / num_processes)
            end = int((i + 1) * len(filenames) / num_processes)
            file_chunk = filenames[start:end]
            tasks.append(executor.submit(process_batch, file_chunk, f0p, speech_encoder, diff, mel_extractor, device=device, config_path=config_path))
        for task in tqdm(tasks, position = 0):
            task.result()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', type=str, default=None)
    parser.add_argument(
        "--in_dir", type=str, default="dataset/44k", help="path to input dir"
    )
    parser.add_argument(
        '--use_diff',action='store_true', help='Whether to use the diffusion model'
    )
    parser.add_argument(
        '--f0_predictor', type=str, default="rmvpe", help='Select F0 predictor, can select crepe,pm,dio,harvest,rmvpe,fcpe|default: rmvpe'
    )
    parser.add_argument(
        '--num_processes', type=int, default=1, help='You are advised to set the number of processes to the same as the number of CPU cores'
    )
    parser.add_argument("--speech_export", type=str, nargs="+", help="List of speakers to process")
    parser.add_argument("--config_path", type=str, default="configs/config.json", help="path to config")
    parser.add_argument("--diffusion_config_path", type=str, default="configs/diffusion.yaml", help="path to diffusion config (used when --use_diff)")
    args = parser.parse_args()
    
    # Load config and update global variables
    hps = utils.get_hparams_from_file(args.config_path)
    sampling_rate = hps.data.sampling_rate
    hop_length = hps.data.hop_length
    speech_encoder = hps["model"]["speech_encoder"]

    f0p = args.f0_predictor
    device = args.device
    if device is None:
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    print(speech_encoder)
    logger.info("Using device: " + str(device))
    logger.info("Using SpeechEncoder: " + speech_encoder)
    logger.info("Using extractor: " + f0p)
    logger.info("Using diff Mode: " + str(args.use_diff))

    if args.use_diff:
        print("use_diff")
        print("Loading Mel Extractor...")
        dconfig = du.load_config(args.diffusion_config_path)
        mel_extractor = Vocoder(dconfig.vocoder.type, dconfig.vocoder.ckpt, device=device)
        print("Loaded Mel Extractor.")
    else:
        mel_extractor = None
    filenames = glob(f"{args.in_dir}/*/*.wav", recursive=True)  # [:10]
    
    if args.speech_export:
        filenames = [f for f in filenames if os.path.basename(os.path.dirname(f)) in args.speech_export]
        
    shuffle(filenames)
    mp.set_start_method("spawn", force=True)

    num_processes = args.num_processes
    if num_processes == 0:
        num_processes = 1

    parallel_process(filenames, num_processes, f0p, speech_encoder, args.use_diff, mel_extractor, device, args.config_path)
