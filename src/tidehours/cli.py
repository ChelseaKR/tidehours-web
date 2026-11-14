"""tidehours build: computes and renders the site.

    tidehours --out site [--now 2026-11-01T11:20:00Z] [--states CA,OR,WA]
              [--base-url https://tidehours.com/] [--ga4-id G-...]
              [--app-store-url https://apps.apple.com/...]
              [--amazon-tag tidehours-20]
              [--print-shop-url https://www.etsy.com/shop/...]
              [--booklets booklets.json] [--calendars calendars.json]
              [--posters posters.json]

`--now` pins the clock (tests and reproducible builds); without it the
build uses the current time. `--amazon-tag` turns on the Amazon links on
the English king-tide page (docs/DECISIONS.md 0016); empty, the default,
leaves them off. `--print-shop-url` turns on the link to the Tide Hours
shop on Etsy on the About page and the English king-tide page
(docs/DECISIONS.md 0029); empty, the default, leaves it off. `--booklets`
names a list of printed booklets to use in place of the committed one,
src/tidehours/copy/booklets.json (docs/DECISIONS.md 0030); it is for tests.
`--calendars` does the same for the printable calendars on Etsy,
src/tidehours/copy/calendars.json (docs/DECISIONS.md 0035), and `--posters`
for the printable posters there, src/tidehours/copy/posters.json (0037).
Each station's "today" is its own local date at that instant. Nothing is fetched: the NOAA data is committed in
src/tidehours/data/ (scripts/refresh_data.py refreshes it).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

from . import affiliate, booklets, calendars, catalog, posters, printshop, site


def parse_now(text: str | None) -> dt.datetime:
    if not text:
        return dt.datetime.now(dt.UTC)
    now = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise SystemExit("--now needs a time zone, e.g. 2026-11-01T11:20:00Z")
    return now


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tidehours")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--now")
    ap.add_argument("--states", help="comma-separated state codes ('other' for stations without one)")
    ap.add_argument("--base-url", default=site.DEFAULT_BASE_URL)
    ap.add_argument("--ga4-id", default="")
    ap.add_argument("--app-store-url", default="")
    ap.add_argument("--amazon-tag", default="")
    ap.add_argument("--print-shop-url", default="")
    ap.add_argument("--booklets", type=Path, help="a booklet list to use in place of copy/booklets.json (tests)")
    ap.add_argument("--calendars", type=Path, help="a calendar list to use in place of copy/calendars.json (tests)")
    ap.add_argument("--posters", type=Path, help="a poster list to use in place of copy/posters.json (tests)")
    ap.add_argument(
        "--previous",
        type=Path,
        help="directory holding the live sitemap.xml and lastmod.json: unchanged pages keep their lastmod",
    )
    args = ap.parse_args(argv)
    if args.ga4_id and not args.ga4_id.startswith("G-"):
        raise SystemExit("--ga4-id must look like G-XXXXXXX")
    if args.app_store_url and not args.app_store_url.startswith("https://apps.apple.com/"):
        raise SystemExit("--app-store-url must be an https://apps.apple.com/ link")
    if args.amazon_tag and not affiliate.valid_tag(args.amazon_tag):
        raise SystemExit("--amazon-tag must be an Associates tracking ID like tidehours-20")
    if args.print_shop_url and not printshop.valid_url(args.print_shop_url):
        raise SystemExit("--print-shop-url must be an Etsy shop address like https://www.etsy.com/shop/TideHours")
    try:
        booklets.load(args.booklets)
    except (OSError, ValueError) as err:
        raise SystemExit(f"booklets: {err}") from err
    try:
        calendars.load(args.calendars)
    except (OSError, ValueError) as err:
        raise SystemExit(f"calendars: {err}") from err
    try:
        posters.load(args.posters)
    except (OSError, ValueError) as err:
        raise SystemExit(f"posters: {err}") from err
    started = time.monotonic()
    cat = catalog.load()
    states = None
    if args.states:
        states = {s.strip().upper() if s.strip() != "other" else "other" for s in args.states.split(",")}
    cfg = site.Config(
        args.base_url,
        args.ga4_id,
        args.app_store_url,
        states,
        args.amazon_tag,
        args.print_shop_url,
        args.booklets,
        args.calendars,
        args.posters,
    )
    n = site.write(cat, cfg, parse_now(args.now), args.out, args.previous)
    print(f"tidehours: {n} pages in {time.monotonic() - started:.1f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
