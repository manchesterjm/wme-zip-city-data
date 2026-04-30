"""
Build co_zcta.min.geojson from Census TIGERweb (current ZCTA service).

Why this exists: the Colorado Open Data ZCTA shapefile (used by the original
build_co_zcta.py) has different boundaries from TIGERweb's current ZCTA layer.
WME's gov-boundaries script and the official USPS-aligned Census ZCTAs both
use TIGERweb, so we should too — otherwise our point-in-polygon disagrees
with what the user sees on the map.

Source:
  https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/2

CO ZCTAs are 80xxx and 81xxx (no NM/WY overlap in those prefixes).
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import shape, mapping

OUTPUT = Path(__file__).parent / "co_zcta.min.geojson"
SIMPLIFY_TOLERANCE_DEG = 0.00005   # ~5.6 m
COORD_PRECISION = 6
SCHEMA_VERSION = 2                  # bumped from 1: switched data source
WHERE = "ZCTA5 LIKE '80%' OR ZCTA5 LIKE '81%'"
SERVICE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer/2/query"
PAGE = 200                          # ESRI default cap for geometry queries; smaller is gentler


def fetch_page(offset: int) -> dict:
    params = {
        "where": WHERE,
        "outFields": "ZCTA5",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": str(offset),
        "resultRecordCount": str(PAGE),
    }
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def round_coords(coords, precision=COORD_PRECISION):
    if isinstance(coords, (int, float)):
        return round(coords, precision)
    return [round_coords(c, precision) for c in coords]


def main() -> int:
    all_features = []
    offset = 0
    while True:
        print(f"  fetching offset={offset}...", flush=True)
        page = fetch_page(offset)
        feats = page.get("features", [])
        if not feats:
            break
        all_features.extend(feats)
        if len(feats) < PAGE:
            break
        offset += PAGE
        time.sleep(0.3)

    print(f"Fetched {len(all_features)} ZCTAs from TIGERweb")

    out_features = []
    for f in all_features:
        zip_code = f.get("properties", {}).get("ZCTA5")
        geom = f.get("geometry")
        if not zip_code or not geom:
            continue
        simplified = shape(geom).simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        if simplified.is_empty:
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

    out = {
        "type": "FeatureCollection",
        "metadata": {
            "schema": SCHEMA_VERSION,
            "source": "TIGERweb tigerWMS_Current MapServer/2 (2020 Census ZCTA)",
            "state": "CO",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "feature_count": len(out_features),
            "simplify_tolerance_deg": SIMPLIFY_TOLERANCE_DEG,
            "coord_precision": COORD_PRECISION,
        },
        "features": out_features,
    }
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    out_size = OUTPUT.stat().st_size
    print(f"Wrote {OUTPUT.name}: {len(out_features)} features, {out_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
