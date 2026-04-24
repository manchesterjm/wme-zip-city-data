"""
Build co_zip_cities.json — USPS-aligned ZIP -> city data for Colorado.

Sources:
  1. USPS ZIP_Locale_Detail.xls (Post Office Locale Detail) — free, public
     download from postalpro.usps.com. Gives us the preferred city per ZIP.
  2. co_zip_cities.overrides.json — hand-verified entries from the USPS
     Cities-by-ZIP web tool, adding recognized aliases and avoid lists.

Merge order: XLS base -> overrides win where present.

Schema:
  {
    "metadata": { source, state, generated, zip_count, ambiguous_count,
                  overrides_applied, schema },
    "zips": {
      "<ZIP>": {
        "preferred":  "CITY NAME" | null,      // null = ambiguous, unresolved
        "candidates": ["A", "B"],              // only present when preferred is null
        "recognized": ["ALIAS", ...],
        "avoid":      ["NAME", ...],
        "state":      "CO"
      }
    }
  }

Auto-fixer logic (match Josh's policy on 2026-04-24):
  - preferred set, current city == preferred          -> OK
  - preferred set, current city in recognized          -> OK (USPS-valid alias)
  - preferred set, current city in avoid               -> FIX to preferred
  - preferred set, current city blank                  -> FIX to preferred
  - preferred set, current city is anything else      -> FIX to preferred
  - preferred null, current city in candidates         -> OK
  - preferred null, current city blank                 -> AMBIGUOUS (manual)
  - preferred null, current city mismatch candidates  -> AMBIGUOUS (manual)
  - ZIP not in data                                    -> NO_DATA
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

HERE = Path(__file__).parent
SOURCE = HERE / "ZIP_Locale_Detail.xls"
OVERRIDES_SRC = HERE / "co_zip_cities.overrides.json"
OUTPUT = HERE / "co_zip_cities.json"
TARGET_STATE = "CO"
SCHEMA_VERSION = 2


def load_overrides() -> dict:
    if not OVERRIDES_SRC.exists():
        return {}
    with OVERRIDES_SRC.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("overrides", {}) or {}


def build_base_from_xls() -> dict:
    """Read XLS, emit one entry per CO ZIP with preferred or candidates set."""
    print(f"Reading {SOURCE} ...")
    df = pd.read_excel(SOURCE, sheet_name="ZIP_DETAIL")
    co = df[df["PHYSICAL STATE"] == TARGET_STATE].copy()

    base = {}
    for zip_code, group in co.groupby("DELIVERY ZIPCODE"):
        cities = sorted({
            c.strip().upper()
            for c in group["PHYSICAL CITY"].dropna().tolist()
            if isinstance(c, str) and c.strip()
        })
        if not cities:
            continue
        zip_str = f"{int(zip_code):05d}"
        if len(cities) == 1:
            base[zip_str] = {
                "preferred": cities[0],
                "recognized": [],
                "avoid": [],
                "state": TARGET_STATE,
            }
        else:
            # Ambiguous: XLS has multiple post office cities for this ZIP.
            # Without the USPS City State Product, we can't tell which is the
            # USPS-preferred name — leave null for manual resolution via
            # overrides file.
            base[zip_str] = {
                "preferred": None,
                "candidates": cities,
                "recognized": [],
                "avoid": [],
                "state": TARGET_STATE,
            }
    return base


def merge(base: dict, overrides: dict) -> tuple[dict, int]:
    """Apply overrides over base. Override wins entirely for each ZIP it touches."""
    merged = dict(base)
    applied = 0
    for zip_code, override in overrides.items():
        existing = merged.get(zip_code, {"state": TARGET_STATE})
        # Override replaces the semantic fields entirely; preserves state if absent.
        merged[zip_code] = {
            "preferred":  override.get("preferred"),
            "recognized": sorted(set(override.get("recognized", []))),
            "avoid":      sorted(set(override.get("avoid", []))),
            "state":      override.get("state", existing.get("state", TARGET_STATE)),
        }
        # Drop candidates — an override resolves the ambiguity.
        applied += 1
    return merged, applied


def main() -> int:
    if not SOURCE.exists():
        print(f"Source not found: {SOURCE}", file=sys.stderr)
        return 1

    overrides = load_overrides()
    print(f"Loaded {len(overrides)} override entries from {OVERRIDES_SRC.name}")

    base = build_base_from_xls()
    print(f"Built base: {len(base)} ZIPs")

    merged, applied = merge(base, overrides)
    print(f"Merged: {applied} overrides applied")

    ambiguous = sum(1 for e in merged.values() if e.get("preferred") is None)
    print(f"Remaining ambiguous (preferred=null): {ambiguous}")

    output = {
        "metadata": {
            "source": "USPS ZIP_Locale_Detail.xls + co_zip_cities.overrides.json",
            "source_xls_last_modified": datetime.fromtimestamp(
                SOURCE.stat().st_mtime, timezone.utc
            ).isoformat(timespec="seconds"),
            "state": TARGET_STATE,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "zip_count": len(merged),
            "overrides_applied": applied,
            "ambiguous_count": ambiguous,
            "schema": SCHEMA_VERSION,
            "schema_note": "preferred=city-to-normalize-to (null=ambiguous). recognized=USPS-valid aliases (leave alone). avoid=USPS-invalid names (fix to preferred).",
        },
        "zips": dict(sorted(merged.items())),
    }

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {OUTPUT.name} ({len(merged)} ZIPs, schema v{SCHEMA_VERSION})")

    # Spot-check.
    for z in ["80106", "80831", "80908", "81212", "80133", "80918"]:
        e = merged.get(z)
        if e:
            pref = e.get("preferred") or f"(ambiguous: {', '.join(e.get('candidates', []))})"
            rec = e.get("recognized", [])
            avo = e.get("avoid", [])
            extras = []
            if rec: extras.append(f"+{len(rec)} recognized")
            if avo: extras.append(f"+{len(avo)} avoid")
            extras_str = f" [{', '.join(extras)}]" if extras else ""
            print(f"  {z} -> {pref}{extras_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
