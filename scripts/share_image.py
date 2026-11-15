"""Writes the HTML page that is drawn once into the site's share image,
`src/tidehours/static/share.png` (1200 x 630; docs/DECISIONS.md 0042).

    uv run python scripts/share_image.py --fonts DIR --logo PNG --out share.html

The curve is real: the engine's predicted tide at Bar Harbor, Maine
(8413320) from midnight to midnight on January 1, 2027, local time, drawn
to fill the width. No number is printed on the image. `--fonts` is a folder
with Bitter and Archivo (SIL Open Font License 1.1) as
`bitter-latin-wght-normal.woff2` and `archivo-latin-wght-normal.woff2`;
`--logo` is the Tide Hours clock-over-wave mark, 1000 x 1000. Neither is
committed here; the page embeds both, so it needs nothing else to draw.

Drawn with headless Chrome and stripped with ImageMagick:

    chrome --headless --hide-scrollbars --force-device-scale-factor=1 \\
      --window-size=1200,630 --screenshot=share-raw.png file:///.../share.html
    magick share-raw.png -strip -define png:compression-level=9 \\
      -define png:exclude-chunks=date,time share.png

The home-screen icons are the same mark scaled down, and favicon.ico is
templates/favicon.svg drawn small:

    magick LOGO -filter Lanczos -resize 180x180 -strip apple-touch-icon.png   # and 192, 512
    rsvg-convert -w 16 -h 16 favicon.svg -o 16.png                            # and 32, 48
    magick 16.png 32.png 48.png favicon.ico

The files are committed; the build only copies them, so nothing here runs
in `make verify`.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
from pathlib import Path
from zoneinfo import ZoneInfo

from tidehours.catalog import load
from tidehours.days import local_midnight

STATION = "8413320"
DATE = dt.date(2027, 1, 1)
W, H = 1200, 630
# The curve's highest point and lowest point, in image pixels from the top.
TOP, BOTTOM = 376.0, 500.0

# The shop's Night palette (the tide prints' "night" style).
NIGHT = {"bg": "#0f2238", "ink": "#f4efe2", "water": "#1d4468", "edge": "#9cc6ea", "muted": "#a9b6c4"}

WORDMARK = "Tide Hours"
TAGLINE = "Free tide times for today and tomorrow at every NOAA tide prediction station in the US."
CAPTION = "The predicted tide at Bar Harbor, Maine, on January 1, 2027"
ADDRESS = "tidehours.com"


def curve(step: float = 300.0) -> list[tuple[float, float]]:
    """(seconds since local midnight, feet above MLLW) for the whole day."""
    cat = load()
    station = cat.station(STATION)
    if station is None:
        raise SystemExit(f"station {STATION} is not in the catalog")
    zone = ZoneInfo(station.tz)
    start = local_midnight(DATE, zone)
    end = local_midnight(DATE + dt.timedelta(days=1), zone)
    return [(t - start, h) for t, h in cat.predictor(STATION).curve(start, end, step)]


def water_path(points: list[tuple[float, float]]) -> tuple[str, str]:
    """The water under the curve, closed along the bottom, and the curve
    itself, as SVG paths."""
    span = points[-1][0]
    lo = min(h for _, h in points)
    hi = max(h for _, h in points)

    def xy(t: float, h: float) -> str:
        return f"{t / span * W:.1f},{BOTTOM - (h - lo) / (hi - lo) * (BOTTOM - TOP):.1f}"

    line = " L".join(xy(t, h) for t, h in points)
    return f"M{line} L{W},{H} L0,{H} Z", f"M{line}"


def font_face(family: str, path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{family}';font-weight:100 900;"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
    )


def page(fonts: Path, logo: Path) -> str:
    c = NIGHT
    fill, edge = water_path(curve())
    mark = base64.b64encode(logo.read_bytes()).decode("ascii")
    style = (
        font_face("Bitter", fonts / "bitter-latin-wght-normal.woff2")
        + font_face("Archivo", fonts / "archivo-latin-wght-normal.woff2")
        + f"html,body{{margin:0;padding:0}}body{{width:{W}px;height:{H}px;overflow:hidden;position:relative;"
        f"background:{c['bg']};color:{c['ink']};font-family:Archivo,sans-serif}}"
        "svg{position:absolute;inset:0}"
        ".head{position:absolute;left:80px;top:60px;display:flex;align-items:center;gap:36px}"
        ".head img{width:136px;height:136px;border-radius:30px;display:block}"
        ".head b{font-family:Bitter,serif;font-weight:600;font-size:104px;letter-spacing:-1px;line-height:1}"
        f".tag{{position:absolute;left:80px;top:226px;width:1000px;font-size:38px;line-height:1.3;"
        f"font-weight:400;color:{c['ink']}}}"
        f".cap{{position:absolute;left:80px;bottom:40px;font-size:22px;color:{c['muted']}}}"
        f".url{{position:absolute;right:80px;bottom:34px;font-size:36px;font-weight:600;color:{c['ink']}}}"
    )
    svg = (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" aria-hidden="true">'
        f'<path d="{fill}" fill="{c["water"]}"/>'
        f'<path d="{edge}" fill="none" stroke="{c["edge"]}" stroke-width="4" stroke-linejoin="round"/></svg>'
    )
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{style}</style></head><body>'
        f"{svg}"
        f'<div class="head"><img alt="" src="data:image/png;base64,{mark}"><b>{html.escape(WORDMARK)}</b></div>'
        f'<p class="tag">{html.escape(TAGLINE)}</p>'
        f'<p class="cap">{html.escape(CAPTION)}</p>'
        f'<p class="url">{html.escape(ADDRESS)}</p>'
        "</body></html>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", type=Path, required=True)
    ap.add_argument("--logo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.write_text(page(a.fonts, a.logo), encoding="utf-8")


if __name__ == "__main__":
    main()
