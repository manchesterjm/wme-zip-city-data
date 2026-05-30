"""
Diff a USPS Cities-by-ZIP collector dump against the current co_zip_cities.json
and emit ready-to-insert override entries for any ZIP whose USPS data differs.

Usage:
  python analyze_usps_dump.py [path-to-usps_metro.json]

The dump is the JSON produced by usps_metro_collector.console.js — a map of
ZIP -> USPS cityByZip response. Only resultStatus == SUCCESS entries are used.
USPS response maps to our schema as:
  defaultCity   -> preferred
  citiesList[]  -> recognized   (USPS-valid aliases)
  nonAcceptList[] -> avoid       (USPS-invalid names)

Output is REPORT-ONLY: it prints the override lines; a human inserts them into
co_zip_cities.overrides.json (so the hand-formatted file stays clean), then runs
build_co_zip_cities_from_xls.py.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DUMP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/mnt/c/Users/manch/Desktop/usps_metro.json")
CURRENT = HERE / "co_zip_cities.json"


def norm(s):
    return (s or "").strip().upper()


def cities(lst):
    return sorted({norm(c.get("city")) for c in (lst or []) if norm(c.get("city"))})


def main():
    usps = json.load(DUMP.open())
    cur = json.load(CURRENT.open())["zips"]

    ok = {z: v for z, v in usps.items() if isinstance(v, dict) and v.get("resultStatus") == "SUCCESS"}
    missing = sorted(z for z, v in usps.items() if z not in ok)
    print(f"Dump: {len(usps)} ZIPs | {len(ok)} SUCCESS | {len(missing)} missing/errored")
    if missing:
        print("Missing:", " ".join(missing))
    print()

    changes = []
    for z, v in sorted(ok.items()):
        u_pref = norm(v.get("defaultCity"))
        u_rec = cities(v.get("citiesList"))
        u_avoid = cities(v.get("nonAcceptList"))
        c = cur.get(z, {})
        c_pref = norm(c.get("preferred"))
        c_rec = sorted(norm(x) for x in (c.get("recognized") or []))
        c_avoid = sorted(norm(x) for x in (c.get("avoid") or []))
        if (u_pref, u_rec, u_avoid) != (c_pref, c_rec, c_avoid):
            changes.append((z, u_pref, u_rec, u_avoid, c_pref, u_pref != c_pref))

    wrong_pref = [c for c in changes if c[5]]
    print(f"{len(ok) - len(changes)} already correct | {len(changes)} need an override "
          f"({len(wrong_pref)} of them change the preferred city)\n")

    if wrong_pref:
        print("--- WRONG PREFERRED (review these) ---")
        for z, up, ur, ua, cp, _ in wrong_pref:
            print(f"  {z}: {cp!r} -> {up!r}  rec={ur} avoid={ua}")
        print()

    if changes:
        print("--- Override lines to insert (sorted by ZIP) ---")
        for z, up, ur, ua, _cp, _ in changes:
            rec = json.dumps(ur)
            avoid = json.dumps(ua)
            print(f'    "{z}": {{ "preferred": "{up}", "recognized": {rec}, '
                  f'"avoid": {avoid}, "state": "CO" }},')
    else:
        print("No new overrides needed — everything in this dump already matches.")


if __name__ == "__main__":
    main()
