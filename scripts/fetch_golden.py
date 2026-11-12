"""Fetch NOAA's own published predictions for a sample of stations, as the
golden fixture for tests/test_golden.py. Network; run by hand.

    uv run python scripts/fetch_golden.py            # golden-sample.json
    uv run python scripts/fetch_golden.py --month    # golden-month.json
    uv run python scripts/fetch_golden.py --sky      # usno-sky-2026.json

The sample: for every state code in the catalog (and the stations NOAA lists
without one), one harmonic and one subordinate station, picked by the
smallest SHA-256 of the station id. That choice is deterministic and does not
favor stations the engine happens to do well on. NOAA's high/low predictions
for 2026-11-01 to 2026-11-03 (GMT, MLLW, feet) and, for harmonic stations,
the hourly heights on 2026-11-01.

The app's own fixture (tests/fixtures/golden-app.json, copied from
ChelseaKR/tide-hours) covers 12 harmonic and 4 subordinate stations over a
week and 2031; this one widens the sample to every state.

`--sky` fetches the U.S. Naval Observatory's sunrise, sunset and moon phase
(api/rstt/oneday) for SKY_STATIONS on SKY_DATES, plus the polar edges at
Prudhoe Bay, as the oracle for tests/test_sky.py (DECISIONS 0019).
aa.usno.navy.mil has no robots.txt (404, checked 2026-11-05); requests are
spaced a second apart and say who is asking.
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
API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
USNO = "https://aa.usno.navy.mil/api/rstt/oneday"
SKY_OUT = ROOT / "tests" / "fixtures" / "usno-sky-2026.json"
USER_AGENT = "tidehours-web test fixture (https://tidehours.com; run by hand)"
# Every time zone in the catalog, both hemispheres, the Arctic, and a station
# west of the date line in Hawaii time (the western Aleutians, DECISIONS 0018).
SKY_STATIONS = [
    "9414290", "9447130", "8443970", "8518750", "8665530", "8410140", "8724580", "8729840",
    "8771450", "9759110", "9751639", "1612340", "1630000", "1770000", "1890000", "9461380",
    "TWC2309", "9451600", "9455920", "9468756", "9491094", "9497645",
]  # fmt: skip
# The end and start of US daylight saving time, a new moon, a full moon, and
# both solstices.
SKY_DATES = ["2026-11-01", "2026-11-05", "2026-11-09", "2026-11-24", "2026-12-21", "2027-03-14", "2027-06-21"]
# Prudhoe Bay: the last sunrises before polar night, the first after it, and
# the edges of the midnight sun.
PRUDHOE = "9497645"
PRUDHOE_DATES = [
    "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22",
    "2026-11-23", "2027-01-17", "2027-01-18",
    "2027-01-19", "2027-01-20", "2027-01-21", "2027-01-22", "2027-01-23", "2027-01-24", "2027-01-25",
    "2027-05-09", "2027-05-10", "2027-05-11", "2027-05-12", "2027-05-13", "2027-05-14", "2027-05-15", "2027-05-16",
    "2027-07-28", "2027-07-29", "2027-07-30", "2027-07-31", "2027-08-01", "2027-08-02", "2027-08-03",
]  # fmt: skip
BEGIN, END = "20261101", "20261103"


def pred(station: str, begin: str, end: str, interval: str) -> list[list[Any]]:
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
    for attempt in range(1, 5):
        # NOAA sometimes answers a valid request with "No Predictions data
        # was found"; the same request succeeds on a retry.
        with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
            d = json.load(res)
        if "predictions" in d:
            break
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


def usno_day(lat: float, lon: float, date: str, offset_h: float) -> dict[str, Any]:
    q = urllib.parse.urlencode({"date": date, "coords": f"{lat:.5f},{lon:.5f}", "tz": f"{offset_h:g}", "dst": "false"})
    req = urllib.request.Request(f"{USNO}?{q}", headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
        data: dict[str, Any] = json.load(res)["properties"]["data"]
    return {
        "tz": offset_h,
        "sundata": [s for s in data["sundata"] if s["phen"] in ("Rise", "Set") or "continuously" in s["phen"]],
        "curphase": data["curphase"],
        "fracillum": data["fracillum"],
        "closestphase": data["closestphase"],
    }


def sky() -> None:
    """USNO's sun and moon for the sky fixture. The offset sent is the
    station's UTC offset at local noon, with dst=false, so each time in the
    fixture is unambiguous; the tests convert it to an instant. Days already
    in the fixture are kept, not fetched again."""
    from zoneinfo import ZoneInfo

    cat = load()
    out: dict[str, Any] = (
        json.loads(SKY_OUT.read_text(encoding="utf-8"))
        if SKY_OUT.exists()
        else {
            "source": "U.S. Naval Observatory, Astronomical Applications API, api/rstt/oneday (dst=false)",
            "retrieved": dt.date.today().isoformat(),
            "stations": {},
        }
    )
    jobs = [(sid, d) for sid in SKY_STATIONS for d in SKY_DATES] + [(PRUDHOE, d) for d in PRUDHOE_DATES]
    for sid, d in jobs:
        if d in out["stations"].get(sid, {}).get("days", {}):
            continue
        st = cat.station(sid)
        assert st is not None  # noqa: S101
        noon = dt.datetime.combine(dt.date.fromisoformat(d), dt.time(12), ZoneInfo(st.tz))
        offset = noon.utcoffset()
        assert offset is not None  # noqa: S101
        entry = out["stations"].setdefault(sid, {"label": st.display_name, "lat": st.lat, "lon": st.lon, "days": {}})
        entry["days"][d] = usno_day(st.lat, st.lon, d, offset.total_seconds() / 3600)
        print(f"{sid} {d}", flush=True)
        time.sleep(1)
    SKY_OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SKY_OUT}: {len(jobs)} station-days")


def main() -> int:
    if sys.argv[1:] == ["--sky"]:
        sky()
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
