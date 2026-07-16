import argparse
import os
import subprocess
import sys
from pathlib import Path

import torch
from loguru import logger
from torch.optim import lr_scheduler

from diffusion.data_loaders import get_data_loaders
from diffusion.logger import utils
from diffusion.solver import train
from diffusion.unit2mel import Unit2Mel
from diffusion.vocoder import Vocoder


def parse_args(args=None, namespace=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=True,
        help="path to the config file")
    parser.add_argument(
        "-n",
        "--names",
        type=str,
        nargs="+",
        help="list of speaker names to overwrite config.spk")
    parser.add_argument(
        "--print_only",
        action="store_true",
        help="print resolved config overrides and exit")
    return parser.parse_args(args=args, namespace=namespace)

def _derive_isolated_expdir(base_expdir: str, spk_name: str) -> str:
    p = Path(base_expdir)
    parts = list(p.parts)
    logs_idx = None
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() == "logs":
            logs_idx = i
            break
    if logs_idx is not None:
        logs_root = Path(*parts[:logs_idx + 1])
        return str(logs_root / spk_name / "diffusion")
    if p.name == "diffusion" and p.parent.parent != p.parent:
        return str(p.parent.parent / spk_name / "diffusion")
    return str(p / spk_name)

def _infer_project_name(expdir: str):
    try:
        p = Path(expdir).as_posix().rstrip("/")
        parts = p.split("/")
        if len(parts) >= 2 and parts[-1] == "diffusion" and parts[-2] != "logs":
            return parts[-2]
    except Exception:
        pass
    return "44k"

def _read_lines_any_encoding(path):
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read().splitlines()
        except Exception:
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().splitlines()

def _listfile_head(path: str, limit: int = 10):
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=enc) as f:
                lines = []
                for _ in range(limit):
                    line = f.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        lines.append(line)
                return lines
        except Exception:
            continue
    return []

def _needs_diffusion_features(train_list_path: str):
    wavs = _listfile_head(train_list_path, limit=10)
    if not wavs:
        return False
    required_suffixes = (".vol.npy", ".aug_vol.npy", ".mel.npy", ".aug_mel.npy")
    for wav in wavs:
        for suf in required_suffixes:
            p = wav + suf
            if (not os.path.exists(p)) or os.path.getsize(p) == 0:
                return True
    return False

def _run_preprocess_for_diffusion(project_name: str, diffusion_config_path: str, speakers: list, num_processes: int = 1):
    cfg_path = "configs/config.json" if project_name == "44k" else f"configs/{project_name}.json"
    if not os.path.exists(cfg_path):
        cfg_path = "configs/config.json"
    py = sys.executable
    cmd = [
        py,
        "preprocess_hubert_f0.py",
        "--use_diff",
        "--device",
        "cpu",
        "--num_processes",
        str(int(num_processes)),
        "--config_path",
        cfg_path,
        "--diffusion_config_path",
        diffusion_config_path,
    ]
    if speakers:
        cmd.append("--speech_export")
        cmd.extend(speakers)
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
    # parse commands
    cmd = parse_args()
    
    # load config
    args = utils.load_config(cmd.config)
    if cmd.names:
        args.spk = {name: i for i, name in enumerate(cmd.names)}
        if isinstance(args.get("model"), dict):
            args["model"]["n_spk"] = len(cmd.names)
        logger.info(f" > Overwriting config.spk with command line args: {args.spk}")
        logger.info(f" > Overwriting config.model.n_spk with: {args.model.n_spk}")
        
        # Check if the speaker exists in the current training files
        # If not, try to find a specialized filelist for this speaker
        if len(cmd.names) == 1:
            spk_name = cmd.names[0]
            train_lines = _read_lines_any_encoding(args.data.training_files)
            spk_found = False
            for line in train_lines:
                if f"/{spk_name}/" in line.replace("\\", "/"):
                    spk_found = True
                    break
            
            if not spk_found:
                logger.warning(f" > Speaker '{spk_name}' not found in {args.data.training_files}")
                alt_train = f"filelists/{spk_name}_train.txt"
                alt_val = f"filelists/{spk_name}_val.txt"
                if os.path.exists(alt_train) and os.path.exists(alt_val):
                    logger.info(f" > Found alternative filelists: {alt_train}, {alt_val}")
                    args["data"]["training_files"] = alt_train
                    args["data"]["validation_files"] = alt_val
                else:
                    logger.error(f" > No alternative filelists found for '{spk_name}'. Training will likely fail.")

    spk_keys = list(getattr(args, "spk", {}).keys()) if hasattr(args, "spk") else []
    if len(spk_keys) == 1:
        base_expdir = args.env.expdir
        spk_name = spk_keys[0]
        if spk_name != "luo":
            new_expdir = _derive_isolated_expdir(base_expdir, spk_name)
            if isinstance(args.get("env"), dict):
                args["env"]["expdir"] = new_expdir
            if cmd.print_only:
                logger.info(f" > base expdir: {base_expdir}")
                logger.info(f" > derived expdir: {new_expdir}")
            logger.info(f" > Overwriting config.env.expdir to isolate speaker: {args.env.expdir}")
            os.makedirs(args.env.expdir, exist_ok=True)
    
    logger.info(' > config:'+ cmd.config)
    logger.info(' > exp:'+ args.env.expdir)
    logger.info(f" > spk keys: {spk_keys}")
    if cmd.print_only:
        raise SystemExit(0)

    try:
        if _needs_diffusion_features(args.data.training_files):
            project_name = _infer_project_name(args.env.expdir)
            speakers = list(getattr(args, "spk", {}).keys())
            logger.info(" > Missing diffusion features detected. Running preprocess_hubert_f0.py --use_diff ...")
            _run_preprocess_for_diffusion(project_name, cmd.config, speakers, num_processes=1)
    except Exception as e:
        logger.warning(f" > Auto diffusion preprocess failed: {e}")
    
    # load vocoder
    vocoder = Vocoder(args.vocoder.type, args.vocoder.ckpt, device=args.device)
    
    # load model
    model = Unit2Mel(
                args.data.encoder_out_channels, 
                args.model.n_spk,
                args.model.use_pitch_aug,
                vocoder.dimension,
                args.model.n_layers,
                args.model.n_chans,
                args.model.n_hidden,
                args.model.timesteps,
                args.model.k_step_max
                )
    
    logger.info(f' > Now model timesteps is {model.timesteps}, and k_step_max is {model.k_step_max}')
    
    # load parameters
    try:
        optimizer = torch.optim.AdamW(model.parameters(), foreach=False)
    except TypeError:
        optimizer = torch.optim.AdamW(model.parameters())
    initial_global_step, model, optimizer = utils.load_model(args.env.expdir, model, optimizer, device=args.device)
    for param_group in optimizer.param_groups:
        param_group['initial_lr'] = args.train.lr
        param_group['lr'] = args.train.lr * (args.train.gamma ** max(((initial_global_step-2)//args.train.decay_step),0) )
        param_group['weight_decay'] = args.train.weight_decay
    scheduler = lr_scheduler.StepLR(optimizer, step_size=args.train.decay_step, gamma=args.train.gamma,last_epoch=initial_global_step-2)
    
    # device
    if args.device == 'cuda':
        torch.cuda.set_device(args.env.gpu_id)
    model.to(args.device)
    
    for state in optimizer.state.values():
        for k, v in state.items():
            if torch.is_tensor(v):
                state[k] = v.to(args.device)
                    
    # datas
    loader_train, loader_valid = get_data_loaders(args, whole_audio=False)
    
    if len(loader_train.dataset) == 0:
        logger.error(" > Error: Training dataset is empty! Please check if your filelist contains the specified speakers and if the diffusion features (.vol.npy, .mel.npy, etc.) have been generated.")
        logger.error(f" > Current training files: {args.data.training_files}")
        logger.error(f" > Current speakers: {list(args.spk.keys())}")
        raise SystemExit(1)
    
    # run
    train(args, initial_global_step, model, optimizer, scheduler, vocoder, loader_train, loader_valid)
    
