"""Fetch NOAA's own published predictions for a sample of stations, as the
golden fixture for tests/test_golden.py. Network; run by hand.

    uv run python scripts/fetch_golden.py            # golden-sample.json
    uv run python scripts/fetch_golden.py --month    # golden-month.json
    uv run python scripts/fetch_golden.py --add      # golden-sample.json, missing keys only
    uv run python scripts/fetch_golden.py --year-boundary   # golden-year-boundary.json, missing keys only

The sample: for every state code in the catalog (and the stations NOAA lists
without one), one harmonic and one subordinate station, picked by the
smallest SHA-256 of the station id. `--add` keeps the stations already in
the sample and fetches only (state, harmonic or subordinate) pairs it does
not cover, for when the catalog's states change (DECISIONS 0018). That choice is deterministic and does not
favor stations the engine happens to do well on. NOAA's high/low predictions
for 2026-11-01 to 2026-11-03 (GMT, MLLW, feet) and, for harmonic stations,
the hourly heights on 2026-11-01.

The app's own fixture (tests/fixtures/golden-app.json, copied from
ChelseaKR/tide-hours) covers 12 harmonic and 4 subordinate stations over a
week and 2031; this one widens the sample to every state.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tidehours.catalog import load  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "golden-sample.json"
MONTH_OUT = ROOT / "tests" / "fixtures" / "golden-month.json"
# Small-range Gulf and Caribbean stations, where stands (a high and a low a
# few hundredths of a foot apart) happen; used to calibrate drop_stands.
SMALL_RANGE = [
    "9751494", "9751639", "9755371", "8729840", "8771450", "8724580", "8779770",
    "8775870", "8735180", "8747437", "8760922", "9751364", "8723214", "1612340",
]  # fmt: skip
YEAR_BOUNDARY_OUT = ROOT / "tests" / "fixtures" / "golden-year-boundary.json"
# Stations with a high or low near 00:00 GMT on January 1, chosen with the
# engine itself so the minutes after midnight are spread out and the change
# of lunar-node constants is large enough to see (DECISIONS 0031). Each is
# fetched for December 31 and January 1 (GMT).
YEAR_BOUNDARY: dict[int, list[str]] = {
    2028: ["8413320", "9466057", "9439099", "8414249", "9455912", "8419317", "9457292", "8410834",
           "9457287", "8412581", "8465705", "8410875"],
    2027: ["9444090", "9466328", "9459758", "9465396", "9455606", "9465438"],
}  # fmt: skip
# NOAA's 6-minute heights from 22:00 to 02:00 GMT around the same midnight,
# to see where its curve changes constants.
YEAR_BOUNDARY_SERIES: dict[int, list[str]] = {2028: ["9455912"]}
# The same highs and lows asked for from January 1 on (January 1 and 2), to
# see whether NOAA's answer depends on where the request starts.
YEAR_BOUNDARY_FROM_JAN1: dict[int, list[str]] = {2028: ["8413320"]}
API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
BEGIN, END = "20261101", "20261103"


def pred(station: str, begin: str, end: str, interval: str, attempts: int = 4) -> list[list[Any]]:
    q = urllib.parse.urlencode(
        {
            "product": "predictions",
            "application": "tidehours-web",
            "begin_date": begin,
            "end_date": end,
            "datum": "MLLW",
            "station": station,
            "time_zone": "gmt",
            "units": "english",
            "interval": interval,
            "format": "json",
        }
    )
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "tidehours-web golden fixture"})  # noqa: S310
    for attempt in range(1, attempts + 1):
        # NOAA sometimes answers a valid request with "No Predictions data
        # was found"; the same request succeeds on a retry.
        with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
            d = json.load(res)
        if "predictions" in d:
            break
        if attempt < attempts:
            time.sleep(3 * attempt)
    if "predictions" not in d:
        raise SystemExit(f"no predictions for {station}: {d}")
    rows: list[list[Any]] = []
    for p in d["predictions"]:
        row: list[Any] = [p["t"].replace(" ", "T") + "Z", float(p["v"])]
        if "type" in p:
            row.append(p["type"])
        rows.append(row)
    return rows


def month(cat_ids: list[str]) -> None:
    """A month of NOAA highs and lows (2026-11) at every fixture station plus
    the small-range set: the measurement behind DECISIONS 0004."""
    out: dict[str, Any] = {
        "source": "NOAA CO-OPS datagetter product=predictions interval=hilo, datum MLLW, GMT, feet",
        "retrieved": dt.date.today().isoformat(),
        "stations": {},
    }
    for sid in dict.fromkeys(SMALL_RANGE + cat_ids):
        out["stations"][sid] = pred(sid, "20261101", "20261130", "hilo")
        time.sleep(1)
    MONTH_OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {MONTH_OUT}: {len(out['stations'])} stations")


def year_boundary() -> None:
    """The measurement behind DECISIONS 0031: NOAA's highs and lows on
    December 31 and January 1 (GMT) at the YEAR_BOUNDARY stations, its
    6-minute heights around that midnight at the YEAR_BOUNDARY_SERIES
    stations, and its highs and lows at the YEAR_BOUNDARY_FROM_JAN1 stations
    asked for from January 1 on. Keeps what the file already has and makes
    one request, with no retry, for each key it lacks, two seconds apart."""
    out: dict[str, Any] = {"retrieved": dt.date.today().isoformat()}
    if YEAR_BOUNDARY_OUT.exists():
        out = json.loads(YEAR_BOUNDARY_OUT.read_text(encoding="utf-8"))
    out["source"] = "NOAA CO-OPS datagetter product=predictions (interval hilo, or 6 for series), datum MLLW, GMT, feet"
    wanted = [
        ("boundaries", YEAR_BOUNDARY, "hilo", 0),
        ("series", YEAR_BOUNDARY_SERIES, "6", 0),
        ("fromJanuary1", YEAR_BOUNDARY_FROM_JAN1, "hilo", 1),
    ]
    fetched = 0
    for section, stations, interval, shift in wanted:
        for year, ids in stations.items():
            got = out.setdefault(section, {}).setdefault(str(year), {})
            begin = dt.date(year - 1, 12, 31) + dt.timedelta(days=shift)
            end = begin + dt.timedelta(days=1)
            for sid in ids:
                if sid in got:
                    continue
                rows = pred(sid, f"{begin:%Y%m%d}", f"{end:%Y%m%d}", interval, attempts=1)
                if section == "series":
                    rows = [r for r in rows if f"{year - 1}-12-31T22:00Z" <= r[0] <= f"{year}-01-01T02:00Z"]
                got[sid] = rows
                fetched += 1
                YEAR_BOUNDARY_OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
                print(f"{section} {year} {sid}: {len(rows)} rows", flush=True)
                time.sleep(2)
    print(f"{YEAR_BOUNDARY_OUT}: {fetched} requests")


def main() -> int:
    if sys.argv[1:] == ["--year-boundary"]:
        year_boundary()
        return 0
    cat = load()
    if sys.argv[1:] == ["--month"]:
        sample = json.loads(OUT.read_text(encoding="utf-8"))
        app_fx = json.loads((ROOT / "tests/fixtures/golden-app.json").read_text(encoding="utf-8"))
        ids = [i for fx in (sample, app_fx) for g in ("harmonic", "subordinate") for i in fx[g]]
        month(ids)
        return 0
    app = json.loads((ROOT / "tests/fixtures/golden-app.json").read_text(encoding="utf-8"))
    already = set(app["harmonic"]) | set(app["subordinate"])
    pick: dict[tuple[str, bool], str] = {}
    for s in sorted(cat.stations, key=lambda s: hashlib.sha256(s.id.encode()).hexdigest()):
        key = (s.state, s.is_subordinate)
        if s.id not in already and key not in pick:
            pick[key] = s.id
    out: dict[str, Any] = {
        "source": "NOAA CO-OPS datagetter product=predictions, datum MLLW, GMT, feet",
        "retrieved": dt.date.today().isoformat(),
        "harmonic": {},
        "subordinate": {},
    }
    if sys.argv[1:] == ["--add"]:
        out = json.loads(OUT.read_text(encoding="utf-8"))
        for group in ("harmonic", "subordinate"):
            for sid in out[group]:
                st = cat.station(sid)
                assert st is not None  # noqa: S101
                pick.pop((st.state, group == "subordinate"), None)
    for (state, sub), sid in sorted(pick.items()):
        st = cat.station(sid)
        assert st is not None  # noqa: S101
        entry: dict[str, Any] = {"label": st.display_name, "hilo": pred(sid, BEGIN, END, "hilo")}
        if not sub:
            entry["hourly"] = pred(sid, BEGIN, BEGIN, "h")
        out["subordinate" if sub else "harmonic"][sid] = entry
        print(f"{'S' if sub else 'H'} {state or '--'} {sid} {st.name}", flush=True)
        time.sleep(1)
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(out['harmonic'])} harmonic, {len(out['subordinate'])} subordinate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
