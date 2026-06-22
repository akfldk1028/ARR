"""F1 — Download glb meshes from Objaverse for selected UIDs."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import objaverse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter-json", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True,
                        help="dir to symlink/copy glb files (overrides Objaverse cache)")
    parser.add_argument("--processes", type=int, default=8)
    parser.add_argument("--copy", action="store_true",
                        help="copy instead of symlink (use if cache dir not on same FS)")
    args = parser.parse_args()

    with open(args.filter_json, encoding="utf-8") as f:
        meta = json.load(f)

    uids = [s["uid"] for s in meta["selected"]]
    print(f"Downloading {len(uids)} meshes from Objaverse (cache + {args.output_dir}/)...")

    paths = objaverse.load_objects(uids=uids, download_processes=args.processes)
    print(f"  cached {len(paths)} glb files")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n_done = 0
    failed = []
    for uid, src_path in paths.items():
        if not src_path or not Path(src_path).exists():
            failed.append(uid)
            continue
        dst = out_dir / f"{uid}.glb"
        if dst.exists() or dst.is_symlink():
            n_done += 1
            continue
        try:
            if args.copy:
                shutil.copy2(src_path, dst)
            else:
                dst.symlink_to(src_path)
            n_done += 1
        except Exception as e:
            print(f"  link/copy err for {uid}: {e}")
            failed.append(uid)

    print(f"  linked {n_done}/{len(paths)} files to {out_dir}")
    if failed:
        print(f"  failed: {len(failed)} (first 5: {failed[:5]})")

    # Update filter.json with paths
    for s in meta["selected"]:
        u = s["uid"]
        s["glb_path"] = str(out_dir / f"{u}.glb") if (out_dir / f"{u}.glb").exists() else None
    with open(args.filter_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  updated {args.filter_json} with glb_path field")


if __name__ == "__main__":
    main()
