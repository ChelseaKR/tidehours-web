"""Refresh the site's committed NOAA data. Network; run by hand, never in
`make verify` or the daily build (the build must not depend on NOAA being up).

    uv run python scripts/refresh_data.py --app-checkout ~/portfolio/tide-app

1. stations.json: copied byte for byte from the Tide Hours app's bundle
   (TideCore/Sources/TideCore/Resources/stations.json at the app's main
   branch), so the site and the app compute from the same constants. The
   app's pipeline (pipeline/build_bundle.py) builds it from NOAA CO-OPS.
2. regions.json: NOAA's region name for each tide prediction station, from
   the CO-OPS metadata API's tidepredstations list.
3. datums.json: MHHW and MLLW for the king-tide stations, from the CO-OPS
   metadata API, for "above a normal high tide".

Each file records where and when it came from. A failed request or a
response without the expected fields exits non-zero and writes nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "tidehours" / "data"
MDAPI = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
UA = "tidehours-web data refresh (https://github.com/ChelseaKR/tidehours-web)"

sys.path.insert(0, str(ROOT / "src"))
from tidehours.kingtides import STATIONS as KING_TIDE_STATIONS  # noqa: E402


def get_json(url: str) -> Any:
    if not url.startswith("https://api.tidesandcurrents.noaa.gov/"):
        raise SystemExit(f"refusing to fetch {url}")
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
                return json.load(res)
        except Exception as err:
            if attempt == 3:
                raise SystemExit(f"{url}: {err}") from err
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-checkout", type=Path, required=True)
    args = ap.parse_args()
    today = dt.date.today().isoformat()

    src = args.app_checkout / "TideCore/Sources/TideCore/Resources/stations.json"
    bundle = json.loads(src.read_text(encoding="utf-8"))
    if bundle.get("schema") != 1 or len(bundle["harmonic"]) < 1000:
        raise SystemExit(f"{src}: not a schema-1 station bundle")

    stations = get_json(f"{MDAPI}/tidepredstations.json")["stationList"]
    regions = {s["stationId"]: s["region"] for s in stations if s.get("stationId") and s.get("region")}
    if len(regions) < 3000:
        raise SystemExit(f"tidepredstations: only {len(regions)} regions")

    datums: dict[str, dict[str, Any]] = {}
    for _, sid, _ in KING_TIDE_STATIONS:
        d = get_json(f"{MDAPI}/stations/{sid}/datums.json?units=english")
        values = {x["name"]: x["value"] for x in d.get("datums") or []}
        if not isinstance(values.get("MHHW"), (int, float)) or not isinstance(values.get("MLLW"), (int, float)):
            raise SystemExit(f"{sid}: no MHHW/MLLW datum")
        datums[sid] = {
            "mhhwAboveMllwFt": round(values["MHHW"] - values["MLLW"], 2),
            "epoch": d.get("epoch"),
        }
        time.sleep(0.5)

    shutil.copyfile(src, DATA / "stations.json")
    (DATA / "regions.json").write_text(
        json.dumps(
            {
                "source": f"{MDAPI}/tidepredstations.json (NOAA CO-OPS), field 'region'",
                "retrieved": today,
                "regions": dict(sorted(regions.items())),
            },
            indent=0,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (DATA / "datums.json").write_text(
        json.dumps(
            {
                "source": f"{MDAPI}/stations/{{id}}/datums.json?units=english (NOAA CO-OPS)",
                "retrieved": today,
                "datums": datums,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256((DATA / "stations.json").read_bytes()).hexdigest()
    print(f"stations.json {digest} (retrieved {bundle['retrieved']}); {len(regions)} regions; {len(datums)} datums")
    return 0


if __name__ == "__main__":
    sys.exit(main())
