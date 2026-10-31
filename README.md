# tidehours-web

The website for Tide Hours at **tidehours.com** (live since 2026-10-31): free tide
predictions for every NOAA tide prediction station in the US, computed with
the Tide Hours iPhone app's engine, as a static site.

- **Free here:** a page per station (3,256 of them) with today's and
  tomorrow's highs and lows and a tide curve; state and region pages; the
  West Coast king-tide pages (English and Spanish), moved from chelseakr.com.
- **In the app** (ChelseaKR/tide-hours): 7-day tables, favorites, widgets,
  offline. Every page links to it as "Coming soon to the App Store" until
  `--app-store-url` is set.

Every page says the numbers are predictions, not observations, not for
navigation, and not a NOAA product, and credits NOAA CO-OPS.

## How it works

`tidehours --out site` loads the committed NOAA data (`src/tidehours/data/`,
see [docs/DATA.md](docs/DATA.md)), computes each station's highs, lows and
curve for its own local today and tomorrow, and renders HTML with Jinja.
Nothing is fetched at build time. A full build is about 9 seconds and 54 MB
(3,741 pages). Why build time and not the browser:
[docs/DECISIONS.md](docs/DECISIONS.md) 0002.

The engine (`src/tidehours/engine.py`) is a line-for-line port of the app's
TideCore. `make verify` checks it against NOAA's own published predictions:
a week at 16 stations (the app's fixture), three days at a harmonic and a
subordinate station in every state, and every high and low of November 2026
at 81 stations. The one deliberate difference from the app, removing
"stands", is DECISIONS 0004.

## Commands

    make verify        # the gate: format, lint, types, tests (incl. NOAA accuracy), full build + checks, audit, secrets, hygiene
    make site-checks   # axe-core and pa11y-ci on a sample of 127 pages (needs Node 22 and Chrome)
    make site          # build with today's numbers into ./site
    uv run python scripts/refresh_data.py --app-checkout ~/portfolio/tide-app   # refresh NOAA data (network)
    uv run python scripts/fetch_golden.py [--month]                              # refresh the NOAA fixtures (network)

Build options: `--now` (pin the clock), `--states CA,OR,WA` (a subset),
`--base-url`, `--ga4-id` (empty: no analytics), `--app-store-url`.

## CI

- `ci`: `make verify` on the runner named by the `CI_RUNS_ON` repository
  variable (the self-hosted Mac runner), hosted when unset.
- `site-checks`: the accessibility gates, pull requests only, hosted
  (Chrome has no build for the arm64 Mac runners).
- `publish`: the full daily build at 11:20 UTC with its checks, on the Mac
  runner, then a deploy job on a hosted runner (OIDC, no AWS credentials on
  the Mac runner) that syncs to S3, invalidates CloudFront and checks the
  live home page. Both are skipped unless the variable `PUBLISH_ENABLED` is
  `true`. Hosting: [infra/README.md](infra/README.md), DECISIONS 0009.

## Owner steps

Done on 2026-10-31: the domain, the AWS member account, hosting and DNS
(`infra/site.yaml`, live), the GA4 property (G-JCCFJNV1CV), and the
`protect-main` ruleset requiring `verify`.

1. Search Console: verify `sc-domain:tidehours.com` and submit
   `https://tidehours.com/sitemap.xml`.
2. GA4: accept the Data Processing Terms and turn off data sharing, as for
   Lake Notice.
3. After the app is approved: its App Store URL in `APP_STORE_URL`.
4. Merge the personal-site branch that redirects `/tide-hours/king-tides`
   here.
