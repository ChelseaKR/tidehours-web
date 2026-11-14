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
subordinate station in every state, every high and low of November 2026
at 81 stations, and the two days around 00:00 GMT on January 1 of 2027 and
2028 at 18 stations. The app's engine makes the same two choices: it
removes "stands" (DECISIONS 0004; the app's #2) and keeps a year's
constants for the highs and lows of the first 30 minutes of the next
(DECISIONS 0031; the app's DECISIONS 0006, #16).

## Commands

    make verify        # the gate: format, lint, types, tests (incl. NOAA accuracy), full build + checks, audit, secrets, hygiene
    make site-checks   # axe-core and pa11y-ci on a sample of 161 pages (needs Node 22 and Chrome)
    make site          # build with today's numbers into ./site
    uv run python scripts/refresh_data.py --app-checkout ~/portfolio/tide-app   # refresh NOAA data (network)
    uv run python scripts/fetch_golden.py [--month | --add | --year-boundary]    # refresh the NOAA fixtures (network)

Build options: `--now` (pin the clock), `--states CA,OR,WA` (a subset),
`--base-url`, `--ga4-id` (empty: no analytics), `--app-store-url`,
`--amazon-tag` (empty: no Amazon links; DECISIONS 0016), `--print-shop-url`
(empty: no link to the print shop; DECISIONS 0029), `--booklets FILE` (a
list of printed booklets in place of `src/tidehours/copy/booklets.json`,
for tests; DECISIONS 0030), `--calendars FILE` (a list of printable
calendars in place of `src/tidehours/copy/calendars.json`, for tests;
DECISIONS 0035), `--posters FILE` (the same for the printable posters,
`src/tidehours/copy/posters.json`; DECISIONS 0037), `--gifts FILE` (the
same for the other products the tide gifts page lists,
`src/tidehours/copy/gifts.json`; DECISIONS 0041).

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
5. Amazon links (DECISIONS 0016): add `https://tidehours.com` to the
   Associates website list and create the `tidehours-20` tracking ID. Only
   after Gate A passes (no earlier than 2026-12-01), set the repository
   variable `AMAZON_ASSOCIATE_TAG` to it. Empty it to turn the links off.
6. Printed booklets (DECISIONS 0030): when a booklet is live on Amazon, add
   its station id, ASIN, year and cover title to
   `src/tidehours/copy/booklets.json` in a pull request. That station's page
   then links to it until the booklet's year is over.
7. Printable calendars (DECISIONS 0035): when a calendar is live in the
   Etsy shop, add its station id, Etsy listing id (the digits after
   `/listing/`), year and title to `src/tidehours/copy/calendars.json` in a
   pull request. That station's page then links to it until the calendar's
   year is over. The print shop's sentence on the About and king-tide pages
   names "printable 2027 tide calendars" in `copy/print_shop.json`; change
   it when the year changes.
8. Printable posters (DECISIONS 0037): when a poster is live in the Etsy
   shop, add its station id, Etsy listing id, year and title ("2027 Tide
   Poster: Place") to `src/tidehours/copy/posters.json` in a pull request.
   That station's page then links to it, and `/tide-calendars/` lists it
   with every other calendar and poster, until the poster's year is over.
9. Other products (DECISIONS 0041): when a tide rings print, a tide
   blanket pattern, a moon phase calendar, a solstice print or a
   multi-town book is live,
   add it to `src/tidehours/copy/gifts.json` in a pull request with its
   Etsy listing id or ASIN, year, title, station or towns, and `live`, the
   date it was marked live; add `until` (YYYY-MM-DD, Pacific) for one that
   is delisted on a known day. `/tide-gifts/` then lists it until its year
   is over or its `until` comes. Calendars and posters go in their own lists (7 and 8) and appear
   there too.
