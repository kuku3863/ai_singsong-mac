import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except Exception:
        return False


_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._() -]+")


def _slugify_filename(name: str) -> str:
    cleaned = _SAFE_CHARS_RE.sub("_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" _")
    if not cleaned:
        cleaned = "file"
    return cleaned


def _unique_name(existing: set, candidate: str, original: str) -> str:
    if candidate not in existing:
        return candidate
    h = hashlib.sha1(original.encode("utf-8", errors="ignore")).hexdigest()[:8]
    stem, ext = os.path.splitext(candidate)
    alt = f"{stem}_{h}{ext}"
    if alt not in existing:
        return alt
    i = 2
    while True:
        alt2 = f"{stem}_{h}_{i}{ext}"
        if alt2 not in existing:
            return alt2
        i += 1


def _read_text_lines_any_encoding(path: Path) -> Tuple[List[str], str]:
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=enc) as f:
                return [ln.rstrip("\n") for ln in f], enc
        except Exception:
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [ln.rstrip("\n") for ln in f], "utf-8-ignore"


def _write_text_lines_utf8(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for ln in lines:
            f.write(f"{ln}\n")


def rename_non_ascii_wavs(
    dataset_dir: Path,
    filelist_paths: List[Path],
    dry_run: bool,
) -> Dict[str, str]:
    dataset_dir = dataset_dir.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(str(dataset_dir))

    wav_paths = sorted(dataset_dir.glob("*.wav"))
    existing_names = {p.name for p in dataset_dir.iterdir() if p.is_file()}

    mapping: Dict[str, str] = {}

    for wav_path in wav_paths:
        if _is_ascii(wav_path.name):
            continue

        new_name = _slugify_filename(wav_path.name)
        if not new_name.lower().endswith(".wav"):
            new_name = os.path.splitext(new_name)[0] + ".wav"
        new_name = _unique_name(existing_names, new_name, wav_path.name)

        old_rel = wav_path.as_posix()
        new_path = wav_path.with_name(new_name)
        new_rel = new_path.as_posix()

        mapping[old_rel] = new_rel

        old_spec = wav_path.with_suffix(".spec.pt")
        new_spec = new_path.with_suffix(".spec.pt")

        sidecar_suffixes = [
            ".f0.npy",
            ".soft.pt",
            ".vol.npy",
            ".aug_vol.npy",
            ".mel.npy",
            ".aug_mel.npy",
        ]
        sidecars = [(wav_path.with_name(wav_path.name + suf), new_path.with_name(new_path.name + suf)) for suf in sidecar_suffixes]

        if dry_run:
            continue

        if new_path.exists():
            raise FileExistsError(str(new_path))

        wav_path.rename(new_path)
        existing_names.discard(wav_path.name)
        existing_names.add(new_path.name)

        if old_spec.exists() and (not new_spec.exists()):
            old_spec.rename(new_spec)

        for old_sc, new_sc in sidecars:
            if old_sc.exists() and (not new_sc.exists()):
                old_sc.rename(new_sc)

    if not mapping:
        return mapping

    for fl in filelist_paths:
        if not fl.exists():
            continue
        lines, _ = _read_text_lines_any_encoding(fl)
        out_lines = []
        for ln in lines:
            key = ln.strip()
            if key in mapping:
                out_lines.append(mapping[key])
            else:
                out_lines.append(ln)
        if not dry_run:
            _write_text_lines_utf8(fl, out_lines)

    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_dir", type=str, required=True)
    ap.add_argument("--filelists", type=str, nargs="*", default=[])
    ap.add_argument("--dry_run", action="store_true")
    args = ap.parse_args()

    mapping = rename_non_ascii_wavs(
        dataset_dir=Path(args.dataset_dir),
        filelist_paths=[Path(p) for p in args.filelists],
        dry_run=bool(args.dry_run),
    )

    print(f"renamed: {len(mapping)}")
    if mapping:
        sample = list(mapping.items())[:10]
        for a, b in sample:
            print(f"{a} -> {b}")


if __name__ == "__main__":
    main()

