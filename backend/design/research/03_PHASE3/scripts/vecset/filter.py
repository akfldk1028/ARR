"""
F1 — Objaverse lvis 카테고리 필터: building/architecture 후보 UID 추출.

LVIS = 1156 categories. We pick architectural keywords + report counts.
Output: data/objaverse/meta/filter.json with selected uids.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import objaverse


# LVIS architectural ALLOWLIST — only categories that are actually buildings/structures.
# Discovered after first run: most "house"/"wall" keyword matches were unrelated
# (cabinet, wallet, wall_clock, mashed_potato, etc.). Whitelist real building-like categories.
ALLOWLIST = {
    "birdhouse",        # 50 — small architectural form
    "clock_tower",      # 49 — vertical tower with detail
    "dollhouse",        # 56 — house structure (multi-story, roof)
    "houseboat",        # 8  — building on water, asymmetric
    "water_tower",      # 29 — vertical structure
}

# Backward compat — keep KEYWORDS for old behavior path
KEYWORDS = list(ALLOWLIST)


def find_matching_categories(lvis: dict[str, list[str]], keywords: list[str]) -> dict[str, list[str]]:
    """Return {category_name: [uid, ...]} restricted to ALLOWLIST."""
    return {cat: uids for cat, uids in lvis.items() if cat in ALLOWLIST}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, required=True,
                        help="path to write filter.json")
    parser.add_argument("--max-per-category", type=int, default=200,
                        help="cap per category to avoid one category dominating")
    parser.add_argument("--total-cap", type=int, default=1000,
                        help="overall mesh count cap")
    parser.add_argument("--print-all-categories", action="store_true",
                        help="print full LVIS category list for inspection")
    args = parser.parse_args()

    print("Loading LVIS annotations from Objaverse...")
    lvis = objaverse.load_lvis_annotations()
    print(f"  {len(lvis)} LVIS categories total")

    if args.print_all_categories:
        for cat in sorted(lvis.keys()):
            print(f"    {cat}: {len(lvis[cat])} uids")
        return

    matched = find_matching_categories(lvis, KEYWORDS)
    print(f"  matched {len(matched)} architectural categories:")
    total_uids = 0
    for cat, uids in sorted(matched.items()):
        print(f"    {cat}: {len(uids)} uids")
        total_uids += len(uids)
    print(f"  total uids in matched cats: {total_uids}")

    # Sample up to max_per_category per cat → total_cap overall
    selected = []
    selected_meta = []
    for cat in sorted(matched.keys()):
        uids = matched[cat]
        n = min(args.max_per_category, len(uids))
        for u in uids[:n]:
            selected.append(u)
            selected_meta.append({"uid": u, "category": cat})
        if len(selected) >= args.total_cap:
            break
    selected = selected[:args.total_cap]
    selected_meta = selected_meta[:args.total_cap]
    print(f"  selected {len(selected)} uids (cap={args.total_cap})")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "keywords": KEYWORDS,
            "n_total_lvis": len(lvis),
            "n_matched_categories": len(matched),
            "matched_categories": {c: len(uids) for c, uids in matched.items()},
            "n_selected": len(selected),
            "selected": selected_meta,
        }, f, indent=2, ensure_ascii=False)
    print(f"  saved {out_path}")


if __name__ == "__main__":
    main()
