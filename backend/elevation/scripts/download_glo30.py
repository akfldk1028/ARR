"""
Copernicus GLO-30 DEM 한국 영역 자동 다운로드 (AWS S3 Open Data Sponsorship).

- 출처: s3://copernicus-dem-30m/ (인증 X, AWS unsigned access)
- 라이선스: ESA Standard License (무료, 상업 가능, 출처 표시)
- 한국 bbox: 33~39°N, 124~132°E → 1°×1° 타일 50개 ≈ 1~2GB
- 결과: ../data/copernicus_glo30/*.tif (opentopodata mount path)

사용법:
    cd ARR/backend/elevation
    python scripts/download_glo30.py [--bbox lat_min lat_max lng_min lng_max]

요구사항: boto3 (`pip install boto3`)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
except ImportError:
    print("ERROR: boto3 not installed. Run: pip install boto3", file=sys.stderr)
    sys.exit(1)


BUCKET = "copernicus-dem-30m"
# 한국 bbox (제주~철원 + 동서 끝). 약간 여유 둠.
DEFAULT_BBOX = (33, 39, 124, 132)   # (lat_min, lat_max, lng_min, lng_max)
OUT_DIR = Path(__file__).parent.parent / "data" / "copernicus_glo30"


def tile_name(lat: int, lng: int) -> str:
    """Copernicus DEM 타일 명명규칙: Copernicus_DSM_COG_10_N37_00_E127_00_DEM."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lng >= 0 else "W"
    return (
        f"Copernicus_DSM_COG_10_"
        f"{ns}{abs(lat):02d}_00_{ew}{abs(lng):03d}_00_DEM"
    )


def s3_key(tile: str) -> str:
    return f"{tile}/{tile}.tif"


def download_bbox(bbox: tuple[int, int, int, int], out_dir: Path) -> tuple[int, int]:
    """bbox 안 1°×1° 타일들 모두 다운로드. (다운로드된 수, 스킵된 수)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))

    lat_min, lat_max, lng_min, lng_max = bbox
    downloaded = 0
    skipped = 0
    failed = 0
    total = (lat_max - lat_min + 1) * (lng_max - lng_min + 1)
    idx = 0

    for lat in range(lat_min, lat_max + 1):
        for lng in range(lng_min, lng_max + 1):
            idx += 1
            tile = tile_name(lat, lng)
            key = s3_key(tile)
            local = out_dir / f"{tile}.tif"

            if local.exists() and local.stat().st_size > 0:
                skipped += 1
                print(f"[{idx}/{total}] SKIP {tile} (이미 존재)")
                continue

            try:
                print(f"[{idx}/{total}] GET {tile} ...", end=" ", flush=True)
                s3.download_file(BUCKET, key, str(local))
                size_mb = local.stat().st_size / 1024 / 1024
                print(f"OK ({size_mb:.1f} MB)")
                downloaded += 1
            except Exception as e:
                # 일부 좌표는 해상에 있어 타일이 없음 — INVALID/NotFound는 정상
                err_str = str(e)
                if "404" in err_str or "NoSuchKey" in err_str:
                    print("(없음, 해상)")
                else:
                    print(f"FAIL: {e}")
                failed += 1

    return downloaded, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=int, metavar=("LAT_MIN", "LAT_MAX", "LNG_MIN", "LNG_MAX"),
                    default=DEFAULT_BBOX)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    print(f"Copernicus GLO-30 DEM 다운로드")
    print(f"  bucket:  s3://{BUCKET}/ (unsigned, free)")
    print(f"  bbox:    lat {args.bbox[0]}~{args.bbox[1]}, lng {args.bbox[2]}~{args.bbox[3]}")
    print(f"  out_dir: {args.out}")
    print()

    dl, sk = download_bbox(tuple(args.bbox), args.out)
    print()
    print(f"완료: 다운로드 {dl}, 스킵 {sk}")
    print(f"opentopodata config.yaml에서 path 확인: data/copernicus_glo30/")


if __name__ == "__main__":
    main()
