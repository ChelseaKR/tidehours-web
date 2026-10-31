#!/usr/bin/env bash
# Accessibility gates over the built site, the same locally and in CI:
#
#   1. Build the whole site with a pinned clock, outside the checkout.
#   2. Serve it on a free local port.
#   3. axe-core (WCAG 2.0/2.1/2.2 A and AA, critical/serious/moderate) and a
#      320px reflow check on a sample of pages (axe.mjs).
#   4. pa11y-ci with the axe runner, WCAG2AA, on the same sample.
#
# The sample: every page that is not a station or region page (home, about,
# privacy, both king-tide pages, 404, every state page), every 25th region
# page, and the station pages of the golden-test fixtures (a harmonic and a
# subordinate station in every state). Station pages share one template, so
# the sample covers each shape: harmonic, subordinate, no state, no region.
#
# Google Analytics is blocked in every browser this starts.
#
# Setup, once: (cd tools/site-checks && npm ci && npx puppeteer browsers install chrome)
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
tools="$root/tools/site-checks"
work="$(mktemp -d)"
server_pid=""
cleanup() {
  if [ -n "$server_pid" ]; then kill "$server_pid" 2>/dev/null || true; fi
  rm -rf "$work"
}
trap cleanup EXIT

echo "== the checkers' own dependencies"
(cd "$tools" && npm audit --audit-level=high --no-fund)

echo "== build the site"
(cd "$root" && uv run --frozen tidehours --out "$work/site" --now 2026-11-01T11:20:00Z)

pages_file="$work/pages.txt"
(cd "$root" && uv run --frozen python - "$work/site" > "$pages_file" <<'PY'
import json, sys
from pathlib import Path
site = Path(sys.argv[1])
fx = Path("tests/fixtures")
ids = []
for name in ("golden-app.json", "golden-sample.json"):
    d = json.loads((fx / name).read_text(encoding="utf-8"))
    ids += list(d["harmonic"]) + list(d["subordinate"])
pages = ["./", "about/", "privacy/", "king-tides/", "es/king-tides/", "404.html"]
states = sorted(p.parent.relative_to(site).as_posix() + "/" for p in site.glob("states/*/index.html"))
regions = sorted(p.parent.relative_to(site).as_posix() + "/" for p in site.glob("states/*/*/index.html"))
pages += states + regions[::25] + [f"stations/{i}/" for i in dict.fromkeys(ids)]
print("\n".join(pages))
PY
)
page_count="$(wc -l < "$pages_file" | tr -d ' ')"
if [ "$page_count" -lt 100 ]; then
  echo "site-checks: only $page_count page(s) in the sample; refusing to pass" >&2
  exit 1
fi
echo "   $page_count pages in the sample"

port="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
base="http://127.0.0.1:$port/"
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$work/site" > "$work/server.log" 2>&1 &
server_pid=$!
for _ in $(seq 1 50); do
  if curl -fsS -o /dev/null "$base" 2>/dev/null; then break; fi
  sleep 0.2
done
curl -fsS -o /dev/null "$base"

cd "$tools"
chrome="$(node -e 'Promise.resolve(require("puppeteer").executablePath()).then((p) => console.log(p))')"
if [ ! -x "$chrome" ]; then
  echo "site-checks: no Chrome at $chrome; run: (cd tools/site-checks && npx puppeteer browsers install chrome)" >&2
  exit 1
fi

echo "== axe-core and 320px reflow"
xargs node axe.mjs "$base" < "$pages_file"

echo "== pa11y-ci, axe runner, WCAG2AA"
python3 - "$base" "$pages_file" "$chrome" > "$work/pa11yci.json" <<'PY'
import json, sys
base, pages_file, chrome = sys.argv[1:4]
urls = [base + line.strip().removeprefix("./") for line in open(pages_file, encoding="utf-8") if line.strip()]
print(json.dumps({
    "defaults": {
        "standard": "WCAG2AA",
        "runners": ["axe"],
        "level": "error",
        "timeout": 60000,
        "chromeLaunchConfig": {
            "executablePath": chrome,
            "args": [
                "--no-sandbox",
                "--host-resolver-rules=MAP *.googletagmanager.com ~NOTFOUND, "
                "MAP *.google-analytics.com ~NOTFOUND",
            ],
        },
    },
    "urls": urls,
}))
PY
npx --no-install pa11y-ci --config "$work/pa11yci.json"

echo "site-checks: all gates passed"
