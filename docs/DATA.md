# Data

Everything the site computes from is committed here, so a build never
depends on NOAA being up. `scripts/refresh_data.py` refreshes it by hand;
`make hygiene` fails if a file's SHA-256 is not the one recorded below, so a
data change is always reviewed with this file.

- `src/tidehours/data/stations.json`: NOAA CO-OPS harmonic constants (1,232 stations), MLLW-referenced Z0 and the offsets of 2,024 subordinate stations. A byte-for-byte copy of the Tide Hours app's bundle (ChelseaKR/tide-hours, `TideCore/Sources/TideCore/Resources/stations.json` at `cf49f2d`), which the app's `pipeline/build_bundle.py` builds from the CO-OPS Metadata API. NOAA data retrieved 2026-10-24. sha256 `83b123087e3e0a7c2d5dae77af1e0478047296dd018190b6954e76182397897a`
- `src/tidehours/data/regions.json`: NOAA's region name for 3,461 tide prediction stations, from `mdapi/prod/webapi/tidepredstations.json`, field `region`. Retrieved 2026-10-31. 32 catalog stations are not in that list and are shown as "without a region". sha256 `31c8443054aedbc7c2ff560da71fe6639fe0ef0a3ea70668d8a9ec77dbaf11c4`
- `src/tidehours/data/datums.json`: MHHW above MLLW for the 31 king-tide stations, from `mdapi/prod/webapi/stations/{id}/datums.json`. Retrieved 2026-10-31. sha256 `de62c86f7454b45370b85a2c317adad5ee4cb67507247d214c7beef3d4d351c0`

All of it is U.S. Government work in the public domain
(https://tidesandcurrents.noaa.gov/disclaimers.html). The site credits NOAA
on every page and says it is not a NOAA product.

## Test fixtures (NOAA's own published predictions)

- `tests/fixtures/golden-app.json`: copied from the app's
  `TideCore/Tests/TideCoreTests/Fixtures/golden_predictions.json`: 12
  harmonic and 4 subordinate stations, 2026-11-01 to 07, plus three stations
  in June 2031.
- `tests/fixtures/golden-sample.json`: one harmonic and one subordinate
  station per state code (where one exists), picked by the smallest SHA-256
  of the station id: 32 harmonic and 31 subordinate stations, 2026-11-01 to
  03, with hourly heights for the harmonic ones. `scripts/fetch_golden.py`.
  Retrieved 2026-10-31; the 6 stations covering states that changed with
  DECISIONS 0018 (GU, AS, MP, PR subordinate, and no state) were added on
  2026-11-05 with `--add`.
- `tests/fixtures/golden-month.json`: every NOAA high and low in November
  2026 at the 73 fixture stations above plus 14 small-range Gulf and
  Caribbean stations (81 distinct). `scripts/fetch_golden.py --month`.
- `tests/fixtures/king-tides-noaa-2026-27.json`: the data behind the old
  chelseakr.com king-tides page (ChelseaKR/personal-site
  `src/content/kingTides.data.json` at `6ae96ab`), built from NOAA's
  published high/low predictions and datums.
