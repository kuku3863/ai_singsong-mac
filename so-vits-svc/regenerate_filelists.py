import argparse
import os
import random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_dir", type=str, required=True)
    ap.add_argument("--train_list", type=str, required=True)
    ap.add_argument("--val_list", type=str, required=True)
    ap.add_argument("--val_count", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    dataset_dir = Path(args.dataset_dir)
    wavs = sorted(dataset_dir.glob("*.wav"))
    wavs = [p.as_posix() for p in wavs]
    random.Random(args.seed).shuffle(wavs)

    val = wavs[: max(0, min(args.val_count, len(wavs)))]
    train = wavs[len(val) :]

    Path(args.train_list).parent.mkdir(parents=True, exist_ok=True)
    Path(args.val_list).parent.mkdir(parents=True, exist_ok=True)

    with open(args.train_list, "w", encoding="utf-8", newline="\n") as f:
        for p in train:
            f.write(p + "\n")
    with open(args.val_list, "w", encoding="utf-8", newline="\n") as f:
        for p in val:
            f.write(p + "\n")

    print(f"train: {len(train)}")
    print(f"val: {len(val)}")
    if val:
        print("val_sample:", val[0])


if __name__ == "__main__":
    main()

