#!/usr/bin/env python3
import argparse
import os
import sys

import soundfile as sf


def main():
    parser = argparse.ArgumentParser(description="Isolated RVC inference worker")
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--f0-key", type=int, default=0)
    parser.add_argument("--f0-method", default="rmvpe")
    parser.add_argument("--index-path", default="")
    parser.add_argument("--index-rate", type=float, default=0.75)
    parser.add_argument("--filter-radius", type=int, default=3)
    parser.add_argument("--resample-sr", type=int, default=0)
    parser.add_argument("--rms-mix-rate", type=float, default=1.0)
    parser.add_argument("--protect", type=float, default=0.33)
    args = parser.parse_args()

    sys.argv = [sys.argv[0]]
    from app import RVCEngine

    engine = RVCEngine()
    tgt_sr, audio = engine.infer(
        args.model,
        args.input,
        f0_up_key=args.f0_key,
        f0_method=args.f0_method,
        index_path=args.index_path,
        index_rate=args.index_rate,
        filter_radius=args.filter_radius,
        resample_sr=args.resample_sr,
        rms_mix_rate=args.rms_mix_rate,
        protect=args.protect,
    )
    if audio is None or tgt_sr is None:
        raise RuntimeError("RVC inference returned no audio")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    sf.write(args.output, audio, tgt_sr)


if __name__ == "__main__":
    main()
