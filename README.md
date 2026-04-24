# wme-zip-city-data

USPS-aligned ZIP → city lookup data for Waze Map Editor (WME) userscripts.

Built to help WME editors correct RPP (Residential Place Point) cities to match USPS's preferred delivery city names.

## What's here

| File | Purpose |
| --- | --- |
| `co_zip_cities.json` | The data. 589 Colorado ZIPs mapped to their USPS-recognized city name(s). |
| `build_co_zip_cities_from_xls.py` | Builder that regenerates the JSON from the USPS source XLS. |
| `ZIP_Locale_Detail.xls` | USPS Post Office Locale Detail file (authoritative source). |

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

For each RPP:

1. Read RPP's ZIP from its address.
2. Look up the ZIP in `zips`. If not present, leave the RPP alone.
3. If RPP city (case-insensitive) matches any entry in `cities` → leave alone.
4. If `cities` has exactly one entry and RPP doesn't match → set city to that entry.
5. If `cities` has multiple entries and RPP doesn't match any → flag for manual review; don't auto-fix.

## Consuming from a userscript

Fetch once, cache locally:

```js
GM_xmlhttpRequest({
  method: 'GET',
  url: 'https://raw.githubusercontent.com/manchesterjm/wme-zip-city-data/main/co_zip_cities.json',
  onload: (res) => {
    const data = JSON.parse(res.responseText);
    GM_setValue('zipCityData', data);
    GM_setValue('zipCityDataFetchedAt', Date.now());
  }
});
```

The file is small (~57 KB) and the USPS source only updates monthly, so caching a week is fine.

## Regenerating the data

The USPS source file (`ZIP_Locale_Detail.xls`) updates monthly. To refresh:

1. Download the latest `ZIP_Locale_Detail.xls` from USPS.
2. Replace the local copy.
3. Run:

   ```powershell
   D:\Python313\python.exe build_co_zip_cities_from_xls.py
   ```

Dependencies: `pandas`, `xlrd` (for the `.xls` format).

## Why not just scrape `tools.usps.com`?

Tried; USPS's Akamai bot protection rate-limits even real browser sessions after a handful of requests. The XLS file is the same data in bulk form — authoritative, offline, and reproducible.

## Scope

Currently Colorado only. Architecture extends trivially to other states — change the filter in the builder.

## License

Data is USPS-sourced (public). Code under this repo is MIT.
