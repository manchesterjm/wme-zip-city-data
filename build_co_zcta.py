"""
Build co_zcta.min.geojson — slim Colorado ZCTA polygons for runtime point-in-polygon.

Source: Colorado ZIP Code Tabulation Areas (ZCTA) GeoJSON from Colorado Open Data.

Transforms:
  - Drop properties down to {"zip": "<ZCTA5CE10>"} only.
  - Simplify each polygon with Douglas-Peucker at 0.0005° (~56 m) — well within
    the precision of USPS ZCTA boundaries, which are already rough approximations.
  - Round coords to 4 decimal places (~11 m) after simplification.
  - Emit compact JSON (no whitespace).

Typical output: ~1.75 MB for all 526 Colorado ZCTAs (from 24.7 MB source).

Dependencies: shapely (pre-installed on Windows Python D:\\Python313).
Run with:
  D:\\Python313\\python.exe build_co_zcta.py
"""

import json
import sys
from pathlib import Path

from shapely.geometry import shape, mapping

INPUT = Path(__file__).parent / "Colorado_ZIP_Code_Tabulation_Areas_(ZCTA).geojson"
OUTPUT = Path(__file__).parent / "co_zcta.min.geojson"
SIMPLIFY_TOLERANCE_DEG = 0.00005  # ~5.6 m at Colorado's latitude
COORD_PRECISION = 6


def round_coords(coords, precision=COORD_PRECISION):
    if isinstance(coords, (int, float)):
        return round(coords, precision)
    return [round_coords(c, precision) for c in coords]


def main() -> int:
    if not INPUT.exists():
        print(f"Source not found: {INPUT}", file=sys.stderr)
        return 1

    in_size = INPUT.stat().st_size
    print(f"Reading {INPUT.name} ({in_size / 1024 / 1024:.1f} MB)...")
    with INPUT.open("r", encoding="utf-8") as f:
        g = json.load(f)

    out_features = []
    skipped = 0
    for feat in g.get("features", []):
        props = feat.get("properties") or {}
        zip_code = props.get("ZCTA5CE10") or props.get("GEOID10") or props.get("zip")
        geom = feat.get("geometry")
        if not zip_code or not geom:
            skipped += 1
            continue
        simplified = shape(geom).simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        if simplified.is_empty:
            skipped += 1
            continue
        mapped = mapping(simplified)
        out_features.append({
            "type": "Feature",
            "properties": {"zip": str(zip_code)},
            "geometry": {
                "type": mapped["type"],
                "coordinates": round_coords(mapped["coordinates"]),
            },
        })

    out = {"type": "FeatureCollection", "features": out_features}
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    out_size = OUTPUT.stat().st_size
    print(f"Wrote {OUTPUT.name}: {len(out_features)} features, "
          f"{out_size / 1024 / 1024:.2f} MB "
          f"({100 * out_size / in_size:.1f}% of source)")
    if skipped:
        print(f"  skipped {skipped} features missing zip or geometry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
