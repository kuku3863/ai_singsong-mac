import os

import torch
from fairseq import checkpoint_utils


def get_index_path_from_model(sid):
    roots = [
        root
        for root in (os.getenv("index_root"), os.getenv("outside_index_root"))
        if root and os.path.isdir(root)
    ]
    if not sid or not roots:
        return None
    return next(
        (
            f
            for root_dir in roots
            for f in [
                os.path.join(root, name)
                for root, _, files in os.walk(root_dir, topdown=False)
                for name in files
                if name.endswith(".index") and "trained" not in name
            ]
            if sid.split(".")[0] in f
        ),
        None,
    )


def load_hubert(config):
    # PyTorch 2.6+ defaults torch.load(weights_only=True), but fairseq
    # checkpoints contain trusted fairseq classes. Force the legacy behavior
    # only while loading the bundled local Hubert checkpoint.
    orig_torch_load = torch.load

    def _torch_load_compat(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return orig_torch_load(*args, **kwargs)

    torch.load = _torch_load_compat
    try:
        models, _, _ = checkpoint_utils.load_model_ensemble_and_task(
            ["assets/hubert/hubert_base.pt"],
            suffix="",
        )
    finally:
        torch.load = orig_torch_load
    hubert_model = models[0]
    hubert_model = hubert_model.to(config.device)
    if config.is_half:
        hubert_model = hubert_model.half()
    else:
        hubert_model = hubert_model.float()
    return hubert_model.eval()
