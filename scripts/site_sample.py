"""The pages tools/site-checks/run.sh audits with axe-core, the 320px reflow
check and pa11y-ci, one path per line.

    uv run python scripts/site_sample.py <built-site-dir>

Every page that is not a station or region page (home, about, privacy, both
king-tide pages, 404, every state page), every 25th region page, every
split-region page, the station pages of the golden-test fixtures (a
harmonic and a subordinate station in every state), the station pages
of the committed booklet, calendar and poster lists, which carry a link no
other station page has (DECISIONS 0030, 0035 and 0037), and the page that
lists the calendars and posters when the build has one (0037), and the
tide gifts page when the build has one (0041).

A moved region page that redirects (a meta refresh to its new page,
DECISIONS 0017 and 0018) is left out: it is noindex, has nothing of its own
to audit, and navigates away while the checkers run, which destroys their
page context. The page it redirects to is a region page like any other. A
split region's page does not redirect and lists its new pages, so it is in
the sample.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tidehours import booklets, calendars, gifts, posters, printables

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
REDIRECT = '<meta http-equiv="refresh"'
SPLIT = "data-split-region"


def redirects(page: Path) -> bool:
    return REDIRECT in page.read_text(encoding="utf-8")


def sample(site: Path) -> list[str]:
    ids: list[str] = []
    for name in ("golden-app.json", "golden-sample.json"):
        d = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        ids += list(d["harmonic"]) + list(d["subordinate"])
    listed = [*booklets.load(), *calendars.load(), *posters.load()]
    ids += [i for i in listed if (site / "stations" / i / "index.html").is_file()]
    pages = ["./", "about/", "privacy/", "king-tides/", "es/king-tides/", "404.html"]
    if (site / printables.PATH / "index.html").is_file():
        pages.append(printables.PATH)
    if (site / gifts.PATH / "index.html").is_file():
        pages.append(gifts.PATH)
    states = sorted(p.parent.relative_to(site).as_posix() + "/" for p in site.glob("states/*/index.html"))
    region_files = sorted(site.glob("states/*/*/index.html"))
    regions = [p.parent.relative_to(site).as_posix() + "/" for p in region_files if not redirects(p)]
    splits = [r for r in regions if SPLIT in (site / r / "index.html").read_text(encoding="utf-8")]
    picked = list(dict.fromkeys(regions[::25] + splits))
    return pages + states + picked + [f"stations/{i}/" for i in dict.fromkeys(ids)]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: site_sample.py <built-site-dir>", file=sys.stderr)
        return 2
    print("\n".join(sample(Path(argv[0]))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
