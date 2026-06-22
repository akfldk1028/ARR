"""F1.v2 — Download 1000 Sketchfab category=architecture meshes from Objaverse-1.0."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import objaverse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter-json", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--processes", type=int, default=12)
    args = parser.parse_args()

    with open(args.filter_json, encoding="utf-8") as f:
        meta = json.load(f)
    uids = [s["uid"] for s in meta["selected"]]
    print(f"Downloading {len(uids)} architecture meshes from Objaverse...", flush=True)

    t0 = time.time()
    paths = objaverse.load_objects(uids=uids, download_processes=args.processes)
    print(f"  cached {len(paths)} glb files in {time.time()-t0:.1f}s", flush=True)

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
            dst.symlink_to(src_path)
            n_done += 1
        except Exception:
            failed.append(uid)
    print(f"  linked {n_done}/{len(paths)} files to {out_dir}", flush=True)
    if failed:
        print(f"  failed: {len(failed)} (first 5: {failed[:5]})", flush=True)

    for s in meta["selected"]:
        uid = s["uid"]
        p = out_dir / f"{uid}.glb"
        s["glb_path"] = str(p) if p.exists() else None
    with open(args.filter_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"  updated {args.filter_json}", flush=True)


if __name__ == "__main__":
    main()
