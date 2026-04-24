"""
Build co_zip_cities.json from USPS ZIP_Locale_Detail.xls.

Source: USPS Post Office Locale Detail file (ZIP_Locale_Detail.xls)
        downloaded from USPS. Authoritative — same data USPS uses internally.

Schema:
  {
    "metadata": { source, state, generated, zip_count, ambiguous_count, ... },
    "zips": {
      "80908": { "cities": ["COLORADO SPRINGS"],            "state": "CO" },
      "80133": { "cities": ["MONUMENT", "PALMER LAKE"],     "state": "CO" }
    }
  }

RPP auto-fixer logic:
  - If RPP city (case-insensitive) is in `cities`: leave alone.
  - Else if `cities` has 1 entry: set RPP city to that entry.
  - Else (`cities` has multiple entries and RPP doesn't match any): flag
    for manual review — we don't know which of the USPS-recognized cities
    is correct for this specific address.

Run with Windows Python (has pandas + xlrd):
  D:\\Python313\\python.exe build_co_zip_cities_from_xls.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("pandas not available. Run with D:\\Python313\\python.exe", file=sys.stderr)
    sys.exit(1)

SOURCE = Path(__file__).parent / "ZIP_Locale_Detail.xls"
OUTPUT = Path(__file__).parent / "co_zip_cities.json"
TARGET_STATE = "CO"


def main() -> int:
    if not SOURCE.exists():
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        return 1

    print(f"Reading {SOURCE} (this takes a few seconds for 44K rows)...")
    df = pd.read_excel(SOURCE, sheet_name="ZIP_DETAIL")
    print(f"  {len(df)} total rows")

    co = df[df["PHYSICAL STATE"] == TARGET_STATE].copy()
    print(f"  {len(co)} {TARGET_STATE} rows covering {co['DELIVERY ZIPCODE'].nunique()} unique ZIPs")

    # Each ZIP may be served by multiple post offices. When their PHYSICAL
    # CITY values agree, the ZIP is unambiguous. When they differ, the ZIP
    # spans multiple USPS-recognized city names and we emit all of them —
    # the auto-fixer treats a match against any entry as correct.
    result = {}
    ambiguous_zips = []
    for zip_code, group in co.groupby("DELIVERY ZIPCODE"):
        cities = sorted({
            c.strip().upper()
            for c in group["PHYSICAL CITY"].dropna().tolist()
            if isinstance(c, str) and c.strip()
        })
        if not cities:
            continue
        zip_str = f"{int(zip_code):05d}"
        result[zip_str] = {"cities": cities, "state": TARGET_STATE}
        if len(cities) > 1:
            ambiguous_zips.append((zip_str, cities))

    if ambiguous_zips:
        print(f"\n  {len(ambiguous_zips)} ZIPs span multiple cities (emitting all):")
        for z, cs in ambiguous_zips[:10]:
            print(f"    {z}: {cs}")
        if len(ambiguous_zips) > 10:
            print(f"    ... {len(ambiguous_zips) - 10} more")

    output = {
        "metadata": {
            "source": "USPS ZIP_Locale_Detail.xls (Post Office Locale Detail)",
            "source_file": str(SOURCE),
            "source_last_modified": datetime.fromtimestamp(SOURCE.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "state": TARGET_STATE,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "zip_count": len(result),
            "ambiguous_count": len(ambiguous_zips),
            "schema_note": "Each ZIP maps to {cities: [...], state}. Multi-entry cities = ZIP spans multiple USPS-recognized city names.",
        },
        "zips": dict(sorted(result.items())),
    }

    # Path(__file__) gives the Windows path when invoked from WSL via powershell.
    # Resolve it to a real output location.
    out_path = Path(OUTPUT)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {out_path} ({len(result)} ZIPs)")

    # Sanity check: show known ZIPs so Josh can spot-check.
    for z in ["80908", "80918", "80919", "80920", "80808", "80132", "80133"]:
        if z in result:
            print(f"  {z} -> {result[z]['cities']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
