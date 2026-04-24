# wme-zip-city-data

USPS-aligned ZIP → city lookup data for Waze Map Editor (WME) userscripts.

Built to help WME editors correct RPP (Residential Place Point) cities to match USPS's preferred delivery city names.

## What's here

| File | Purpose |
| --- | --- |
| `co_zip_cities.json` | 589 Colorado ZIPs mapped to their USPS-recognized city name(s). |
| `co_zcta.min.geojson` | 526 Colorado ZCTA polygons, simplified for runtime point-in-polygon. Lets a script derive the ZIP for any lat/lon in CO. |
| `build_co_zip_cities_from_xls.py` | Regenerates `co_zip_cities.json` from the USPS XLS. |
| `build_co_zcta.py` | Regenerates `co_zcta.min.geojson` from the Colorado Open Data source. |
| `ZIP_Locale_Detail.xls` | USPS Post Office Locale Detail file (source for city data). |
| `Colorado_ZIP_Code_Tabulation_Areas_(ZCTA).geojson` | Full-resolution ZCTA source (~25 MB). |

## Data format

```json
{
  "metadata": {
    "source": "USPS ZIP_Locale_Detail.xls (Post Office Locale Detail)",
    "state": "CO",
    "generated": "2026-04-24T...",
    "zip_count": 589,
    "ambiguous_count": 32
  },
  "zips": {
    "80908": { "cities": ["COLORADO SPRINGS"], "state": "CO" },
    "80133": { "cities": ["MONUMENT", "PALMER LAKE"], "state": "CO" }
  }
}
```

- `cities` is always a list. A single-entry list = unambiguous ZIP. A multi-entry list = ZIP spans multiple USPS-recognized city names (32 such ZIPs in CO).
- City names are uppercase exactly as USPS publishes them.

## Auto-fixer logic

WME venues don't carry a ZIP attribute, so we derive it from the RPP's location:

1. Take the RPP's geometry centroid (lat/lon).
2. Run point-in-polygon against `co_zcta.min.geojson` to get the 5-digit ZIP.
3. Look up that ZIP in `co_zip_cities.json`.
4. If RPP city (case-insensitive) matches any entry in `cities` → leave alone.
5. If `cities` has exactly one entry and RPP doesn't match → set city to that entry.
6. If `cities` has multiple entries and RPP doesn't match any → flag for manual review.

## Consuming from a userscript

Fetch both files once on first run, cache in GM storage. Both files update at most monthly, so a 7-day cache is fine.

```js
const DATA_URL = 'https://raw.githubusercontent.com/manchesterjm/wme-zip-city-data/main/co_zip_cities.json';
const ZCTA_URL = 'https://raw.githubusercontent.com/manchesterjm/wme-zip-city-data/main/co_zcta.min.geojson';
```

`co_zip_cities.json` is ~57 KB; `co_zcta.min.geojson` is ~1.75 MB.

For point-in-polygon, [Turf.js](https://turfjs.org/) is a drop-in:

```js
const pt = turf.point([lon, lat]);
for (const feature of zcta.features) {
  const bbox = turf.bbox(feature);
  if (lon < bbox[0] || lon > bbox[2] || lat < bbox[1] || lat > bbox[3]) continue;
  if (turf.booleanPointInPolygon(pt, feature)) {
    return feature.properties.zip;
  }
}
```

## Regenerating the data

Both sources update at most monthly:

```powershell
# City data from USPS
D:\Python313\python.exe build_co_zip_cities_from_xls.py

# ZCTA polygons from Colorado Open Data
D:\Python313\python.exe build_co_zcta.py
```

Dependencies: `pandas` + `xlrd` (for `build_co_zip_cities_from_xls.py`), `shapely` (for `build_co_zcta.py`).

## Why not just scrape `tools.usps.com`?

Tried; USPS's Akamai bot protection rate-limits even real browser sessions after a handful of requests. The XLS file is the same data in bulk form — authoritative, offline, and reproducible.

## Scope

Currently Colorado only. Architecture extends trivially to other states — change the filter in the builder.

## License

Data is USPS-sourced (public). Code under this repo is MIT.
