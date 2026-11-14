# Decisions

Owner decisions are marked **(owner, date)**. Everything else is a build
decision made while carrying them out, and can be changed.

## 0001: A website for Tide Hours at tidehours.com (owner, 2026-10-31)

Tide Hours gets its own site at tidehours.com. The owner checked the
trademark search and is buying the domain. This repository was private until
the owner made it public on 2026-11-12.

The product split:

- **Free on the web:** a page per NOAA tide prediction station with today's
  and tomorrow's highs and lows and a simple tide curve; state and region
  index pages; and the king-tide pages, moved here from chelseakr.com.
- **App only:** 7-day tables, favorites, widgets and offline use.

Every page links to the app, marked "Coming soon to the App Store" until it
is approved. Every page says the numbers are predictions, not observations,
not for navigation, and not a NOAA product, and credits NOAA.

## 0002: Compute at build time, not in the browser

Each page is rendered once a day with that day's numbers in the HTML.

- **Search:** the reason the site exists is to be found by someone typing
  "Monterey tide times". The answer has to be in the HTML that a crawler
  reads, not computed by a script after load. The title and description of
  every station page carry today's highs and lows.
- **Correctness:** one engine, in one place, tested against NOAA in
  `make verify`. A browser engine would be a third copy (after Swift and
  Python) running on every visitor's device and time zone setting.
- **Cost:** a full build of all 3,256 stations takes about 9 seconds on the
  Mac and writes about 54 MB in 3,741 pages, so a daily rebuild is cheap.
  The pages are static files with no server, no API and no per-visit compute.
- **The trade-off:** a page is only as fresh as the last build. Each station's
  "today" is its own local date at build time, every table is headed with its
  date, and a small script on the page says so if the visitor's date at the
  station is later than the page's. The build runs at 11:20 UTC, when every
  US station's local date is the same calendar day (American Samoa, UTC-11,
  has just passed midnight; the one UTC+12 station has not reached it).

## 0003: The app's engine, ported line for line

`src/tidehours/engine.py` is a port of the app's TideCore (`Astronomy.swift`,
`Constituents.swift`, `Prediction.swift`): the same Schureman arguments, node
factors at July 2, compound constituents, 6-minute search with bisection,
NOAA's subordinate method and the cosine curve between subordinate highs and
lows. The data file is the app's own `stations.json`, byte for byte
(docs/DATA.md). numpy vectorizes it; the formulas are unchanged.

## 0004: Stands, the one place the site differs from the app

Measured 2026-10-31 against a month of NOAA's published highs and lows at 81
stations: where the tide barely moves, the harmonic sum has a low and a high
minutes apart and a few thousandths of a foot apart. NOAA's tables leave
these pairs out; the app's engine (and so the app) shows them. At 14 small-
range Gulf and Caribbean stations the app's method produced 24 such events
in November 2026, at Galveston, Dog Island, Port Isabel, St. Louis Bay and
Charlotte Amalie among others.

The site removes a pair as a **stand** when a low and a high are less than
120 minutes apart and less than 0.06 ft apart, flattest pair first
(`engine.drop_stands`). The evidence for the thresholds: every pair NOAA
omitted was 7 to 125 minutes apart and up to 0.07 ft; the closest pairs NOAA
kept were 120, 122, 125 and 127 minutes apart (0.011 to 0.022 ft). There is
no rule that separates all of them, because near a flat peak our time and
NOAA's can differ by a few minutes, so 120 minutes, the edge of what NOAA
keeps, was chosen.

Subordinate stations: NOAA derives them from every reference high and low,
stands included (Christmas Bay, TX lists a low at 06:58 between two highs at
07:30 and 11:00 on 2026-11-13, the shifted image of a Galveston stand), so the
site shifts the reference's raw events and then removes the stands that
result at the subordinate station.

What remains, all listed in `tests/test_golden.py`: of NOAA's 8,406 highs
and lows, 8,366 match within 3 minutes and 0.05 ft, 39 are flat peaks
(within 15 minutes, and the tide at NOAA's minute within 0.01 ft), and one
is a flat double high where the site keeps the other peak. The site shows
three stands NOAA omits (pairs 121 and 125 minutes apart, and a subordinate
pair 99 minutes apart and 0.07 ft).

**For the app:** the app shows these stands today. Porting `drop_stands`
to TideCore is a recommended follow-up, so the app and the site agree
everywhere.

Update, 2026-11-11: the app made this change in ChelseaKR/tide-hours#2, so
the site and the app no longer differ here.

## 0005: States, regions and stations NOAA lists without a state

States come from the station bundle; regions are NOAA's own region names
from its tide prediction station list. 194 stations have no state in NOAA's
metadata. They are not assigned one by guessing from coordinates: they are
listed on "Stations without a state", grouped by NOAA's region. 32 stations
are missing from NOAA's region list; they are listed under "Stations without
a region in NOAA's list" on their state page, with no region page.

Station URLs are `/stations/<NOAA id>/`: stable when NOAA renames a station.

## 0006: King tides: computed, one season at a time

The king-tide pages use the app's ranking (ported from personal-site's
`king-tides-rank.mjs`) over the site's own computed highs, not NOAA's
published list, so the site depends on nothing but its committed data. The
test compares them to NOAA's published predictions (the old page's data):
the same days at all 31 stations, times within a minute, heights within
0.02 ft.

The season (`kingtides.SEASON_START`, 2026-11-01) and its copy (the
Coastal Commission's 2026-27 dates and El Niño note) are fixed, not rolled
by the clock: a new season is an edit to that constant and the copy, before
November each year. No test reads the wall clock, so the gate cannot go red
on a date.

The pages are in English and Spanish, as they were on chelseakr.com. The
rest of the site is English for now.

## 0007: Google Analytics hook, off until the owner supplies an ID

Following the portfolio's "GA4 everywhere" decision (2026-09-17) and Lake
Notice's implementation: `--ga4-id` (empty by default) adds the GA4 tag with
Global Privacy Control and Do Not Track respected, an opt-out button in the
footer, consent mode denied in the EEA, UK and Switzerland, and Google
signals and ad personalization off. The privacy page describes analytics
only when the ID is set, and says "collects nothing" when it is not.

The property is "Tide Hours" (properties/561756091, stream G-JCCFJNV1CV),
created 2026-10-31 with Lake Notice's settings: Pacific time, USD, Google
signals off, 14-month retention, `purchase` as a key event. Its ID is the
repository variable `GA4_MEASUREMENT_ID`.

## 0008: CI on the Mac runner; hosting is the owner's

`make verify` is the gate, run by `ci` on the runner chosen by the
`CI_RUNS_ON` repository variable (the portfolio's self-hosted Mac runners;
hosted when unset). The accessibility checks (axe-core and pa11y-ci over a
sample of pages, `tools/site-checks/run.sh`) run locally with `make
site-checks`; in CI they need Chrome, which the arm64 Mac runners do not
have, so `site-checks` runs on pull requests only, on a hosted runner, and
on a sample.

`publish` builds the whole site daily at 11:20 UTC, runs the build checks,
and deploys it (0009). A scheduled run is inert unless the repository
variable `PUBLISH_ENABLED` is `true`.

## 0009: Hosting: S3 and CloudFront in the tidehours account (owner, 2026-10-31)

The owner approved putting tidehours.com live on 2026-10-31. The site is
served from a private S3 bucket behind CloudFront in its own AWS member
account, `tidehours` (932775612205), per the portfolio's one-account-per-app
rule. All of it is one CloudFormation stack, `infra/site.yaml`
(infra/README.md). CloudFormation rather than CDK: this is a Python
repository, and one template needs no Node toolchain and no CDK bootstrap
resources in the account.

- **Pattern:** the same as chelseakr.com's `ChelseaStaticSiteStack`: Origin
  Access Control, a viewer-request function for www and directory indexes,
  a response-headers policy, the 404 page for 403 and 404, and a GitHub OIDC
  role that can only sync this bucket and invalidate this distribution.
- **Trust:** the role trusts `repo:ChelseaKR/tidehours-web:ref:refs/heads/main`
  only, with no GitHub environment (an environment would change that
  subject).
- **Who holds credentials:** `build` stays on the shared Mac runner with no
  AWS access; `deploy` runs on a hosted runner (about 2 minutes a day).
- **Caching:** pages change daily, so browsers keep HTML 10 minutes and
  CloudFront a day, and every deploy invalidates `/*` (one path, inside the
  free 1,000 a month). `style.css` is not fingerprinted, so an hour and a day.
- **Canonical URLs:** `/path` redirects to `/path/` (the form the canonical
  links and sitemap use), www redirects to the apex, http to https.
- **CSP:** enforced, not report-only. Scripts and styles allow
  `'unsafe-inline'` because the pages carry small inline scripts (the
  analytics guard and the stale-date note) and inline SVG curves. Network
  access is this site plus Google Analytics.
- **Not used:** a logging bucket and WAF (cost; the owner's brief).
- **Cost:** about $1.20 a month (infra/README.md), plus the domain.


## 0010: The daily build runs on a hosted runner (2026-11-02)

The scheduled publish failed on 2026-11-01 and 11-02 with "The self-hosted
runner lost communication with the server". The Mac was asleep on battery at
11:20 UTC (4:20 AM Pacific), so the `build` job on the Mac runner never ran
and the live tide tables went a day stale. The schedule can't move, because
11:20 UTC is the only hour when every US station's local date is the same day
(0002).

`build` now runs on `ubuntu-latest`. The build takes about a minute, about
45 hosted minutes a month, well inside the plan's free minutes. CI on pull
requests stays on the Mac runner (0008), since a missed CI run only delays a
merge and never leaves the live site stale.


## 0011: Announce new and changed pages to IndexNow after each deploy (2026-11-03)

ChatGPT search leans on Bing's index, and IndexNow is how a site tells Bing
(and the other participating engines) that a page is new or changed instead
of waiting for the next crawl. Trout Truck and Next Home Game have run the
same `indexnow.py` since 2026-10-23 and get HTTP 200 on their daily runs.

What changed is judged by each page's HTML, not the sitemap: every sitemap
`lastmod` is the build date, so it would call every page changed every day.
The build now writes `lastmod.json`, a SHA-256 per sitemap page, and the next
build compares its own with the live one. Measured on two builds a day apart
(2026-11-01 and 11-02): 3,256 of 3,741 pages differed (every station page,
because today's and tomorrow's tides are new), and the 485 state, home, about,
privacy and king-tide pages did not; a rebuild of the same day differed in
none. So a normal day announces about 3,256 URLs, under the 10,000 per
request limit, and the first deploy with this change announces every page
once, because there is no live `lastmod.json` yet.

`publish.yml` picks the list in `build`, before `deploy` replaces the live
site, and a separate `indexnow` job submits it only after `deploy` and its
live check succeeded. If the live manifest cannot be read, nothing is
announced. The script exits 0 on any problem and prints a notice, so there is
no `continue-on-error` (the standards ban it) and the deploy is never blocked.
The job holds no AWS credentials and no secret: the key file at the site root
is public by design, and only a tidehours.com build carries it. To stop
announcing, delete the `indexnow` job and the two IndexNow steps.

## 0012: The deploy role trusts GitHub's immutable OIDC subject (2026-11-02)

The first automated deploy failed with "Not authorized to perform
sts:AssumeRoleWithWebIdentity". This repository's OIDC tokens use GitHub's
immutable subject, which carries the owner and repository ids
(`repo:ChelseaKR@3114598/tidehours-web@1441166194:ref:refs/heads/main`), but
the role trusted only the legacy name form. `GitHubSubjects` now lists both,
and both name main only, so the scope is unchanged.

## 0013: Index the harmonic stations first; subordinate pages are noindex (2026-11-03)

Measured 2026-11-03, three days after launch. Search Console had downloaded
the sitemap (3,740 URLs, 0 errors) and listed 0 indexed, but URL Inspection
on 32 pages found 17 already indexed, all crawled that day, and 15 not yet
known to Google. Google was indexing the site page by page that day, so what
it was about to index mattered.

What it was about to index: 3,256 station pages from one template. Measured
on a full build, about 87% of the words on a median station page are words
that appear on at least half of all station pages; what differs is the name,
the numbers and the nearby list. 2,024 of the 3,256 are subordinate
stations, whose highs and lows are one of 91 reference stations' moved by
fixed minutes and scaled, so each is close to a copy of another page here
(the top reference has 149). 1,070 stations have another station within 2
miles. Trout Truck, a young domain with about 1,300 indexed template pages,
lost about 97% of its Google impressions in one sitewide re-rank on
2026-10-22 (growth/tt-google-drop-2026-11-03.md). Its cause is not
determined, but a young site made mostly of near-identical template pages
is the leading explanation.

So, for now:

- **Indexed:** home, about, privacy, terms, the king-tide pages, the 30
  state and 449 region pages, and the 1,232 harmonic station pages: 1,717
  pages, all in the sitemap.
- **Served but noindex:** the 2,024 subordinate station pages carry
  `noindex,follow` and are left out of the sitemap and `lastmod.json`, so
  IndexNow (0011) never announces them. They keep their URLs and canonical
  links, and are linked from their state and region pages and from their
  reference station's page.
- **Reference pages list them:** each harmonic page that NOAA uses as a
  reference lists the stations predicted from it, nearest first, with the
  published time corrections ("Santa Cruz, Monterey Bay, CA, 25 mi: high
  tide 6 min earlier"). That is real data a visitor can use, and it makes
  those 91 pages different from every other page.
- **Names:** 105 NOAA names are written in capitals (NOAA's convention for
  the long-running reference stations: "SAN FRANCISCO (Golden Gate)",
  "BOSTON", "HONOLULU"), which put capitals in the titles of the most
  searched pages. `catalog.tidy_name` writes those words as place names and
  keeps abbreviations (ICWW, USCG, N.J.). Display only: ids, URLs and the
  data file are NOAA's. The app shows NOAA's names as they are.

The cost: some well-known places exist here only as subordinate stations
(Santa Cruz, Tybee Light, East Pass (Destin), Daytona Beach Shores and
Ocean Beach, NJ), so those pages will not be found in search until the
rule changes. `site.indexable` is the one place to change it.

When to widen: when the indexed pages earn impressions for four straight
weeks without a sitewide drop, allow subordinate pages back, a state or a
named list at a time, and re-measure. Allowing a page back is a code change
that adds it to the sitemap and `lastmod.json`, so IndexNow announces it.

Superseded on 2026-11-12 by 0033: subordinate pages are indexed, except
the two whose corrections make them copies of their reference station's.

## 0014: Each harmonic station's type of tide, from its own constants (2026-11-04)

The 1,232 indexed station pages (0013) differ mostly in names and numbers. A
station's type of tide is a real fact that differs by station, is computed
from data already here, and tells a visitor what to expect: whether there are
two highs a day or one, and whether they are alike.

**Definition.** The form factor F = (K1 + O1) / (M2 + S2), the sum of the
amplitudes of the two main daily constituents over the two main twice-daily
ones. NOAA CO-OPS's Tide and Current Glossary, under "type of tide"
(quantitative classification after Dietrich): under 0.25 semidiurnal; 0.25
to 1.5 mixed, mainly semidiurnal; 1.5 to 3.0 mixed, mainly diurnal; over 3.0
diurnal. The page shows F to 2 decimals and classifies that shown value, so the number and the label never disagree (0.2466 shows
as 0.25 and is mixed). At the edges: 0.25 and 1.5 belong to the class above,
3.0 to mixed, mainly diurnal.

**Only where the data has it.** The amplitudes are the station's NOAA
harmonic constants in `stations.json`. A station gets a type only when K1,
O1, M2 and S2 are all listed and M2 + S2 is positive; nothing is estimated.
Of the 1,232 harmonic stations, 1,230 qualify: 313 semidiurnal, 641 mixed and
mainly semidiurnal, 107 mixed and mainly diurnal, 169 diurnal (data
retrieved 2026-10-24). Two list no S2 (8653244 Pungo River, NC and 8773896
Shoalwater Flats, TX) and show no type. Subordinate stations have no
constants of their own and show none; they are noindex anyway.

**On the page:** a short "Type of tide" section with one plain sentence on
what it means and the form factor with the thresholds. It says this is the
usual pattern and that each day's highs and lows are the ones to go by.
`scripts/check_site.py` checks every station page shows exactly the
computed type, or none, with a negative control in the tests.

**For the app:** display only; the prediction method is unchanged. The app
does not show a type of tide.

## 0015: Lead with the king tides coming up, and link to them in season (2026-11-04)

People search for king tides by place and month ("king tides Seattle
November 2026") in the days before a run. The king-tide pages opened with
the Coastal Commission's text and listed each station's whole season far
down the page, under a title that named only "2026–27".

**What counts as coming up.** A station's next run is the first of its
computed runs (0006) that has not ended on the build day, in Pacific time
(every king-tide station is on Pacific time; `kingtides.season` refuses one
that isn't). It is coming up when it starts within `kingtides.LEAD_DAYS`
(30) days or is under way. Built 2026-11-04, all 31 stations' next runs are
coming up: Nov 23 to Dec 1, 2026, peaking Nov 25 to 27 (Washington's Puget
Sound stations run latest). Measured over the season, the set is empty from
2027-02-25 to 2027-05-04 and from 2027-08-04 to 2027-09-27, and then nothing
below renders.

**While runs are coming up:**

- **King-tide pages (English and Spanish):** the title names the month and
  year ("King tides November 2026: WA, OR and CA dates and times"; "Mareas
  reales (king tides) noviembre de 2026") and the description the dates. The
  first section after the lead gives the dates, one line per state, and a
  table of each place's run, highest tide with its local time, and height.
  The "prediction, not a flood forecast" warning moved up to follow it. A
  station with no run coming up is left out of the table, and the page says
  how many are left out.
- **Station pages:** a king-tide station shows its run near the top, in
  place of the section lower down. A WA, OR or CA station within
  `kingtides.NEAR_KM` (15 miles) of a king-tide station shows the nearest
  one's run, named and with its distance, and says these are that station's
  predictions, not this one's. 212 stations get that link (54 harmonic),
  plus the 31.
- **Region pages** list the king-tide stations nearest their stations, and
  the WA, OR and CA state pages and the home page give the dates.

The months in a title are each run's peak month, or the build month for a
run still under way after its peak, so on Nov 28 the title reads "November
and December 2026" while Seattle's run lasts.

**Still computed, still pinned.** Every date, time and height is the
engine's (0006); nothing is copied from another site, and no affiliate
links are added. Which run is "next" depends on the build day, as the
station pages' king-tide line already did, and tests pass the day in, so
the gate does not read the wall clock. `scripts/check_site.py` recomputes
the runs coming up for the day the page was built (`data-kt-today`) and
checks both king-tide pages' tables and titles, and every station page's
link or its absence, with a negative control in the tests.

**For the app:** nothing changes. The app does not show king tides yet.

## 0016: Amazon affiliate links on the English king-tide page, off by default (2026-11-04)

The owner approved a small affiliate test on 2026-11-02: Phase 1 only, four
Amazon links on `/king-tides/` in English, built with the switch off and
turned on no earlier than 2026-12-01, and only if Gate A passes (indexing
and impressions thresholds, kept in the owner's growth notes). The expected
money is cents a season; the point is the Associates account's qualifying
sales count, not revenue. Don't expand it without new data.

**The switch.** `Config.amazon_tag` (`--amazon-tag`, the repository
variable `AMAZON_ASSOCIATE_TAG` in `publish.yml`) is empty by default, and
empty means off: the build is byte-identical to the build before this
change, with no Amazon link, no disclosure, and the privacy, terms and about
pages unchanged. The CLI accepts only a tracking ID shaped like
`tidehours-20` (`^[a-z0-9][a-z0-9-]*-2[0-9]$`, matched in full). Switching
on means setting the variable to the Associates tracking ID `tidehours-20`
after the owner adds tidehours.com to the Associates website list and
creates that ID. The kill switch is emptying the variable: the next daily
build removes every link. Turning it on or off changes the HTML of the
English king-tide, privacy, terms and about pages, so IndexNow (0011)
announces those four; that is expected.

**Where.** Website only: never in the iPhone app, a widget or an email.
Only the English king-tide page; the Spanish page, station, state, region,
home and about pages get no links. The block comes after the method
section, whose last paragraph is the app line, so the page's answer, method
and app come before Amazon.

**What.** Four plain category searches, `https://www.amazon.com/s?k=<terms>&tag=<tag>`
built with `urlencode`, with no redirect, shortener or script rewriting:
phone tripod, waterproof phone pouch, rubber boots (`waterproof rubber
boots`), rain jacket. They fit the Coastal Commission's King Tides Project,
which asks for shoreline photos at these tides, in rain season. No brand,
price, rating, image, "best" or "deal": Amazon's Program Policies allow
prices only from its product APIs, and searches avoid naming products.
`rel="sponsored nofollow noopener"` follows Google's guidance on paid links.
Nothing implies safety, flood protection, prediction or navigation.

**Excluded.** A tide clock: it follows the 12 h 25 min semidiurnal cycle,
and every king-tide station is a mixed tide (0014), so it drifts from the
real highs and lows. That is a prediction claim the page cannot stand
behind, and it competes with the app. Also excluded: headlamps (they read
as gear for walking out at night), traction footwear, life jackets, radios,
sandbags or flood barriers, printed tide tables, charts and GPS (safety,
flood or navigation implications, or they compete with the app).

**Disclosure.** Amazon's required sentence, byte for byte ("As an Amazon
Associate I earn from qualifying purchases."), sits in the paragraph right
before the list, with a plain statement that the links earn a commission
and that neither NOAA nor the California Coastal Commission endorses them.
When on, the privacy page says "no display ads" instead of "no ads" and has
an "Affiliate links" section (`/privacy/#affiliate`); the terms page names
Amazon among the trademarks; the about page points to Privacy.

**Analytics.** When GA4 is on (0007), a click on one of these links sends a
`gear_click` event with its placement, link type and host only, read from
data attributes, never the link's address, so the tracking ID and search
terms never reach Google. The handler runs after the Global Privacy
Control, Do Not Track and opt-out guards, and is rendered only on the page
that has the links.

**Checked.** `scripts/check_site.py --amazon-tag` fails the build if, with
no tag, "amazon" appears anywhere; or, with one, a link appears outside the
English king-tide page, before the end of the method section, without the
configured tag or the three `rel` values, in JSON-LD, the sitemap,
robots.txt or lastmod.json, or without the disclosure right before it.
`tests/test_affiliate.py` covers both states with negative controls.

## 0017: U.S. Virgin Islands stations are listed under VI, not PR (2026-11-05)

NOAA's station metadata (the mdapi station record's `state` field, and so
the app's `stations.json`) codes 12 U.S. Virgin Islands stations PR:
9751082, 9751084, 9751219, 9751274, 9751389, 9751417, 9751419, 9751472,
9751561, 9751574, 9751693 and 9751749. Each was checked on 2026-11-05: its
coordinates are on St. Croix, St. John or St. Thomas, and NOAA's region for it
is "St. Croix Island", "St. Johns Island" or "St. Thomas Island". The site
listed them on the Puerto Rico page.

`catalog.territory` lists any station in one of those three NOAA regions,
and any station NOAA codes VI, under VI with the time zone
`America/St_Thomas`. It is the same clock as `America/Puerto_Rico` (UTC-4,
no daylight saving time), so no prediction or time changes; the station page
names the islands' own zone. The data files are not edited: `stations.json`
is copied byte for byte from the app's bundle, so the root fix belongs in the
app's pipeline (ChelseaKR/tide-hours, `pipeline/build_bundle.py`), and until
then this is a difference between the site and the app.

URLs: station pages stay at `/stations/<id>/`. The state page `/states/vi/`
and its three region pages already existed and are in the sitemap; the
moved stations join them. `/states/pr/st-croix-island/`,
`/states/pr/st-johns-island/` and `/states/pr/st-thomas-island/` were in
the live sitemap, so they must not 404. The site is static files on S3
behind CloudFront, whose one viewer-request function handles only www and
trailing slashes, and changing it is an AWS change. So each old path is
built as a stub (`site.MOVED_REGIONS`, `moved.html.jinja`): a meta refresh,
`rel=canonical` to the VI page, a plain link, and noindex, so it is out of
the sitemap and lastmod.json. A stub is built only when its VI page is. `tests/test_site.py` checks that no
station NOAA codes VI, no pinned station, and no station inside the islands'
bounding box is listed under PR.

## 0018: File stations NOAA lists without a state by their reference station (owner, 2026-11-05)

Supersedes the "no guessing" part of 0005. 194 stations have no state in
NOAA's metadata (checked again against the mdapi station list on
2026-11-05): 188 subordinate stations and 6 harmonic ones. They were all on
"Stations without a state", including Guam's reference station (Apra
Harbor), Cape Hatteras, Ocracoke Inlet and Key Largo. The owner chose to
file them from NOAA's own data, not from coordinates. `catalog.file_state`
takes the first of these that applies:

1. **A hand map from NOAA's station names**, `catalog.TERRITORY_STATES`:
   Apra Harbor and Pago Bay are GU; Pago Pago is AS; Johnston Atoll, Midway
   (Sand Island) and Wake Island are UM, the U.S. Minor Outlying Islands;
   Saipan Harbor, Tinian, Rota and Pagan are MP, the Northern Mariana Islands.
   UM and MP are new state pages. `catalog.PLACE_STATES` adds Chelsea
   (TEC1645, Arthur Kill), which is on Staten Island, NY, though its
   reference station, Sandy Hook, is NJ.
2. **The state the NOAA name ends in** ("Clifton Beach, Smith Point, Md.",
   "Harrington Point, Wash."), from `catalog.STATE_NAMES` and the older
   abbreviations in `catalog.STATE_ABBREVIATIONS`. It comes before the
   reference station's: Harrington Point is predicted from Astoria, OR.
3. **The reference station's state**, after that station's own state is
   settled (so a reference in a U.S. Virgin Islands region gives VI, 0017).

Rules 2 and 3 are vetoed when the station's coordinates are across an
obvious border from the state (`catalog.BORDERS`): the 49th parallel and Juan
de Fuca (WA and British Columbia), Dixon Entrance and Pearse Canal (Alaska
and British Columbia), 42°N (CA and OR), the Columbia (OR and WA), the
St. Marys and Savannah rivers, Little River Inlet (SC and NC), the Pearl
River (LA and MS), the District of Columbia's box, and the line between Guam
and the Northern Mariana Islands. The checks are coarse on purpose. Every
station NOAA itself codes with a state passes its state's checks, except
Tanapag Harbor, Saipan (1633227), which NOAA codes GU. A vetoed station keeps
no state; it is not moved to the neighbor, because that would be a guess
from coordinates.

Two stations NOAA codes wrongly are corrected (`catalog.STATE_CORRECTIONS`):
Tanapag Harbor is MP, not GU, and Apia (1778000) is in independent Samoa,
not American Samoa (AS), so it has no state here. Apia also takes Samoa's
own time zone, `Pacific/Apia` (UTC+13), instead of American Samoa's
UTC-11 from NOAA's offset: same clock time, one day later. Its predictions,
which are in UTC, do not change.

Region names: NOAA puts Apra Harbor and Pago Bay in "Northern Marianas
Islands", Johnston Atoll and Midway in "Hawaiin Islands" and Wake in
"Marshall Islands". Those five are listed under their own island's name
(`catalog.REGION_CORRECTIONS`): Guam, Johnston Atoll, Midway Islands and
Wake Island.

Names: a station's display name no longer repeats its state. When the name
already ends in the state's name or abbreviation, the code is not appended
("Apra Harbor, Guam", "Burlington, N.J.", not "Burlington, N.J., NJ"), and
"Wake Island (U.S.)" drops "(U.S.)" before its UM code. This changes 93
station names, 86 of them NOAA-coded stations, most on the Delaware and Potomac
rivers. Words inside a name are left alone ("N.C. State Fisheries, NC").
Rewriting names more broadly is left for a later change.

Result: 186 stations change state from main: 184 of the 194 (11 by the hand
maps, 4 by name, 169 by reference station) plus the two corrections. 11
stations are on "Stations without a state": Apia, Wales Island (British
Columbia), 4 Oregon stations predicted from Crescent City, CA, and one each
on the GA/SC, SC/NC and LA/MS lines and two on the FL/GA line. The list is
pinned in `tests/test_site.py`, with a negative control that drops the border
checks and sees Wales Island land on the Alaska page. The golden sample
gained six NOAA-compared stations so it still covers every state
(docs/DATA.md).

Each filed or corrected station's page says what NOAA's list says and why it
is listed where it is. Time zones: each station keeps the zone in the bundle,
except Apia (above) and the ten western Aleutian stations now filed under AK
(Kiska, Attu, Amchitka and others). The bundle gives them `Pacific/Honolulu`
from NOAA's UTC-10 offset, which has no daylight saving time, so their summer
times were an hour early. They take `America/Adak` (`catalog.ALEUTIAN_TZ`),
as the app already does for stations NOAA codes AK. URLs: station pages stay at
`/stations/<id>/`. Each region page whose stations all moved, by NOAA's own
state and region for them, is built as a noindex stub (`site.moved_regions`,
`moved.html.jinja`). If the region moved whole, the stub sends visitors to its
new page, as in 0017. If it split, the stub does not pick one part: it lists
each new region page with the stations it holds, with no redirect and its
own canonical URL. NOAA's "Hawaiin Islands" split into Johnston Atoll and
Midway Islands; "Northern Marianas Islands" (without a state) into Guam and
the Northern Mariana Islands; and the stateless "Columbia River" stations into
Oregon and Washington. A region that still has a station keeps its page.

The data files are not edited. The same rules belong in the app's pipeline
(ChelseaKR/tide-hours, `pipeline/build_bundle.py`); until then this is a
difference between the site and the app.

## 0019: Sunrise, sunset, twilight and the moon on station pages, computed (2026-11-05, finished 2026-11-12)

Each station page's two days (today and tomorrow, as now; DECISIONS 0001's
free-web line is unchanged) carry one line: sunrise and sunset, civil dawn
and dusk, the moon's phase with the share of it lit, and moonrise and
moonset, all in the station's own time zone. For example: "Sunrise 6:40 AM,
sunset 5:07 PM. Civil dawn 6:12 AM, civil dusk 5:34 PM. Moon: waning
crescent, 12% lit at noon. Moonrise 3:06 AM, moonset 3:06 PM." The day's
tide curve shades the hours the sun is down (`aria-hidden`, like the rest of
the drawing; the line carries the facts).

**Computed, not fetched (0002).** `src/tidehours/sky.py` has no data file and
makes no request. Sunrise and sunset use NOAA's Solar Calculator equations
(NOAA GML, after Meeus) at the station's latitude and longitude, with the
sun's center at -0.833 degrees, the U.S. Naval Observatory's definition;
civil dawn and dusk are the sun's center at -6 degrees, also USNO's. The
altitude is sampled every minute from the station's local midnight to the
next, in its IANA zone, so a daylight saving day has 23 or 25 hours, and
each crossing is interpolated between two samples. The moon uses the main
terms of Meeus chapter 47 and the phase angle of chapter 48. The share lit is
at local noon. The phase name follows USNO's convention: new or full moon
when the share rounds to 0% or 100%, a quarter at 50%, otherwise waxing or
waning, crescent or gibbous. A primary phase whose instant falls on the day
is named with its local time ("full moon at 6:53 AM"). Moonrise and moonset
turn the same series into right ascension and declination, take the
station's local sidereal time (Meeus 12.4), and put the moon's center at a
geocentric altitude of 0.7275 times its horizontal parallax less 0.5667
degrees (Meeus 15): the upper limb on the horizon after refraction, as USNO
defines them. A subordinate station uses its own position, not its
reference station's.

**Absence is words.** A day the sun does not rise says "The sun does not
rise on this day (polar night)." A day it does not set says "The sun does
not set on this day (midnight sun)." A day with only one of them names the
missing one ("No sunrise on this day."). The same holds for civil twilight
("It does not get darker than civil twilight on this day." or "No civil
twilight on this day: the sun stays more than 6° below the horizon.") and
for the moon, which skips a moonrise or a moonset about once a month
everywhere ("No moonrise on this day.", "The moon is up all day.", "The
moon does not rise on this day."). No page ever shows a stand-in time. At
Prudhoe Bay (9497645) the sun stays down from November 23 to January 18 and
up from May 15 to July 28 in the fixture years.

**Checked.** `tests/fixtures/usno-sky-2026.json` holds USNO's
`api/rstt/oneday` answers for 186 station-days: 22 stations covering every
time zone in the catalog and latitudes from Pago Pago (14°S) to Prudhoe Bay
(70°N), 7 of them in Alaska (Guam, Pago Pago, Wake, Adak, Shemya across the
date line, Puerto Rico, the Virgin Islands, Hawaii, the Arctic), on 7 dates
(both ends of US daylight saving time, a new moon, a full moon, both
solstices), plus 32 days at Prudhoe Bay on both edges of polar night and the
midnight sun. Fetched by hand with `scripts/fetch_sky.py` (aa.usno.navy.mil
has no robots.txt, 404 on 2026-11-05 and 2026-11-12; requests a second
apart, with `ID=` and a User-Agent that name the site). First fetched
2026-11-05 with sunrise and sunset only; fetched again 2026-11-12 for
twilight and the moon, when every earlier value came back the same except
Shemya's two summer-time days, which moved with 0018's zone change.
Measured on 2026-11-12: all 350 sunrises and sunsets are within 2 minutes
of USNO's (348 within 1; the two are grazing days at Prudhoe Bay); all 334
civil dawns and dusks and all 310 moonrises and moonsets are within 1
minute; the days without one are exactly USNO's; and the phase name, the
share lit and the 55 primary phases on those days match. `tests/test_sky.py`
holds 2 minutes for every time. On a daylight saving day USNO's day (24
hours at the noon offset) and the station's (23 or 25) differ by an hour,
so the moon test compares where they overlap. `scripts/check_site.py`
recomputes each station page's line for both of its days and fails the
build if it is missing, different, or shows "00:00"; negative controls in
`tests/test_sky.py` remove the line, replace polar night with a "00:00"
sunrise, and move a sunrise, a civil dusk, a moonrise and the moon's phase,
and assert the check fails each time. USNO is a test oracle only: its values
are not shown on the site or redistributed.

**Not checked against "12:00 AM".** A real sunset or moonrise can fall at
12:00 AM, so the gate does not ban that text; it compares every line with
the computed one instead, which catches a stand-in time.

**Time zones.** Times use `Station.tz`, so they follow whatever zone the
catalog gives a station, including 0018's `America/Adak` for the western
Aleutians.

**Reuse.** `sky.sun_times(lat, lon, tz, date)` returns the day's sunrise and
the sunset after it as POSIX seconds, or None, the same contract as
`lowtides.sun_times` on the `feat/low-tides` branch (DECISIONS 0021 there),
which carries its own copy of the solar equations because this module was
not on `main` yet. Once both merge, low-tides should call this one and drop
its copy, so the site has one sun.

**Differences from the app.** The app (ChelseaKR/tide-hours) does not show the
sun or moon yet. When its 7-day view adds them, it should port this method
and the same fixture, or record a difference here.

**Not done.** Nautical and astronomical twilight, the moon's transit, a
tide-movement line ("Rising until 12:30 PM"), and anything beyond the two
days on the page.

## 0020: Correct NOAA's station names for display, and fit titles in 60 characters (owner, 2026-11-05)

(0019 is reserved for another branch.) An audit of every station page
(2026-11-05) found NOAA spelling and punctuation slips in the names, lost
diacritics, two pairs of indexed stations with the same title, and 380 of
the 1,232 indexed titles over 60 characters, where search results cut them
off. The owner chose the recommended fix for each:

- **Names** (`tidehours/names.py`, applied after `tidy_name`): 88 stations,
  each entry pinned to the exact name NOAA gives now, so a refresh that
  changes the name drops the correction and fails `tests/test_names.py`.
  - 40 misspellings, each backed by the USGS GNIS official name of a
    feature near the station ("Chicahomny" to "Chickahominy", "Serguis" to
    "Sergius", "Fredericksted" to "Frederiksted"). For Beacon (8518934),
    GNIS has no "Flushkill", so the station takes NOAA's harmonic-constants
    name, "Beacon, Hudson River".
  - Spanish diacritics for 5 Puerto Rico names (Peñuelas, Guánica, Boquerón,
    Bahía Salinas, Mayagüez) and Hawaiian ʻokina and kahakō for 13 Hawaii
    stations (Nāwiliwili, Hanapēpē, Waiʻanae and others), as GNIS writes
    them. Names GNIS does not confirm are left alone.
  - 12 casing or truncated words ("Myrtle beach", "Vineyard Hvn Hbr",
    "Deception Pass St. Park", where St. is State), 4 punctuation slips
    ("Brighton Beach. May River", "St, Croix", a period after a full word),
    and 8 names written "St." for Saint ("Port Saint Joe", "St Croix").
  - 6 names that told no two stations apart, with NOAA's own current name or
    region for each: "Freeport" (8772440) next to "Freeport Harbor"
    (8772471), "Anchor Point, Cook Inlet" and "Anchor Point, Wrangell
    Narrows", "Little Torch Key", and "Tinicum National Wildlife Refuge 3"
    and "4". No two station pages now share a title.
- **Titles:** the longest of "{name} tide times today | Tide Hours", "{name}
  tide times today" and "{name} tide times" that fits in 60 characters
  (`site.station_title`). `og:title` follows; the H1 and description do not
  change. 410 of the 1,232 indexed titles change (55 of them because the
  name changed); 5 indexed titles stay over 60 at 61 to 64 characters.
- **Region labels** (`site.region_label`): NOAA's region names out of
  capitals, without its page-break "-cont." and ", etc.", without a leading
  state part on that state's own pages ("FLORIDA, East Coast" is "East
  Coast" on the Florida page), and with NOAA's typos fixed ("Hawaiin
  Islands", "St. Johns Island" for St. John, and "western shore" in step
  with "Eastern Shore"). Rename only: no regions merge, so Maine and South
  Carolina each show two "Outer Coast" regions, and Florida two "Gulf Coast"
  and New Jersey two "Delaware River", as NOAA splits them.
- **URLs do not change.** Station pages stay at `/stations/<id>/`, and a
  region page's path is still made from NOAA's region name.

The state that a name ends in ("Bladensburg, Md.") is still handled by 0018.
The same corrections belong in the app's pipeline (ChelseaKR/tide-hours);
until then this is a difference between the site and the app.

## 0022: Region pages of one or two stations are noindex (2026-11-05)

Measured 2026-11-05 with Search Console URL Inspection
(growth/indexing-gaps-2026-11-05.md): 11 of 14 well-known harmonic stations
(San Francisco, the Battery, San Diego, Seattle, Honolulu and others) were
still unknown to Google five days after the domain went live, and Google
reaches station pages through state and region pages. Meanwhile some region
pages carry about 130 words: `/states/md/tred-avon-river/` and
`/states/pa/schuylkill-river-pennsylvania/` each list two stations. A region page is
a heading and a list of its stations, and its state page shows the same
heading and the same list, so a one- or two-station region page is a
near-empty copy of part of its state page. On the full catalog, with the
stations filed by 0018, 66 of the 370 region pages list one or two
stations (127 of 446 before 0018).

So `site.region_indexable` asks for at least `site.REGION_MIN_STATIONS`
(3) stations. A smaller region page is still built at its URL, linked from
its state page and followed, with its own canonical, but carries
`noindex,follow` and is left out of the sitemap and `lastmod.json`, so
IndexNow (0011) does not announce it. `scripts/check_site.py` fails the
build if a region page's noindex does not match the rule.

What does not change: every station page keeps its own rule (0013), so a
harmonic station in a small region is still indexed and is linked from its
state page. State pages stay indexed, including the shortest territory
pages (`/states/as/`, `/states/gu/`, `/states/dc/`): the home page links
only state pages, so a state page is the one path to its stations, and
American Samoa has no region page at all. No template changes.

When to revisit: when region pages are filed differently, the count
changes on its own. If a small
region page starts earning impressions anyway, or the station pages are
indexed well, lower the threshold and re-measure.

## 0023: Tell apart the region pages that 0020 left with one label (owner, 2026-11-05)

(0021 and 0022 are reserved for other branches.) 0020 renamed region labels
without merging regions, so four states each showed two region pages with
the same label and title: Maine and South Carolina "Outer Coast", Florida
"Gulf Coast" and New Jersey "Delaware River". In each pair NOAA's own names
differ only by its page-break "-cont." ("MAINE, outer coast" and "MAINE,
outer coast-cont."), which says "continued", not where. The owner chose to
tell them apart with NOAA's own detail, and geography only where NOAA's
data supports it:

- **North and south, from NOAA's coordinates** (`site.tell_apart`). In all
  four pairs every station of one part is north of every station of the
  other, so the parts read "(north)" and "(south)", in NOAA's own style for
  qualifiers ("(inside)", "(outside)"). Maine's Damariscove to Friendship
  Harbor part is north of its Seapoint to Pine Point part; South Carolina's
  North Inlet to Little River part is north of its Edisto to Folly Creek
  part; Florida's Indian Rocks Beach to Panhandle part is north of its Cape
  Sable to Venice Inlet part; and New Jersey's Mantua Creek to Trenton part
  is north of its Stow Creek to Oldmans Creek part. "Upper" and "lower" are not used: "Upper Delaware" names
  the non-tidal river above Port Jervis. If a refresh gives two parts that
  overlap north to south, or three parts with one label, the build stops.
- **URLs do not change.** The pages stay at NOAA's region paths
  (`maine-outer-coast-cont/` and so on).
- **St. John station names.** Five Virgin Islands stations that NOAA's
  bundle calls "St. Johns" now say "St. John", like the region label: GNIS
  names the island "Saint John" and has no "Saint Johns" on it, each
  station's named feature is on it within 0.7 km, and NOAA's own current
  names write "St. John" or "St John" for two of them. That makes 45 GNIS
  misspellings and 93 name corrections, and "Leinster Point, Leinster Bay,
  St. John Island, VI tide times" now fits in 60 characters, leaving 4
  indexed titles over 60.

`tests/test_names.py` checks that no two region pages in a state share a
label or a title, and that without `tell_apart` the four pairs come back.

## 0024: A winter king-tide calendar for each state, by month (2026-11-05)

People plan king-tide visits by month and place ("Washington king tides
December 2026"). The king-tide page lists each station's whole year, and its
summary shows only the runs within 30 days (0015), so on November 5 nothing
on the site named the January or February dates in one place.

**Pages.** `/king-tides/washington/`, `/king-tides/oregon/` and
`/king-tides/california/`, in English (the Spanish king-tide page links to
them, marked as English). Each lists, for November 2026 through February
2027 (`kingtides.CALENDAR_FIRST` and `CALENDAR_LAST`), the runs from 0006
whose highest tide falls in that month, filed under that month: place,
days, highest tide with its Pacific time, height above MLLW and height above
MHHW, with the MHHW epoch from the committed datums (1983–2001 for all 31).
The runs are the same objects as on the king-tide page, so the two cannot
disagree; nothing is copied from another site and nothing is new data.

**Absence.** A month in which no station in the state has a run is still
listed and says in words that no run of the year's highest tides peaks then,
and that this is not a prediction of no high tides (California's February
2027). A month in which some stations have none says the others' high tides
are predicted, but lower than the peak of each of their runs on the page.
The count is of stations, not runs: some Washington stations have two
December runs.

**Pinned, not rolled.** Like 0006, the window is a constant edited once a
season; no run is hidden or marked as past by the build date, so the pages
change only when the data does. Runs that have ended stay listed under their
month.

**Links.** The king-tide pages (under each state's heading), the WA, OR and
CA state pages (always, not only in season), each king-tide station's page,
and each station page that shows a nearby king-tide station's run (0015).
Region and home pages are unchanged. Structured data is a plain `WebPage`
about the state; no `Event` markup, because a predicted tide has no
organizer, place or tickets and the rich result would overstate it.

**Checked.** `scripts/check_site.py` recomputes each state's calendar and
compares every row (`data-kt-cal`), the list of months, and the sentence for
each empty month; `tests/test_king_calendar.py` checks Seattle's February run
against Washington Sea Grant's table and California's peaks against the
Coastal Commission's dates, with a negative control for the check.

**For the app:** nothing changes.

## 0025: Name the states in full in the king-tide page's title (2026-11-07)

(0019 and 0021 are reserved for other branches.) Search Console for
sc-domain:tidehours.com, Oct 10 to Nov 7, 2026 (data from Nov 3 on): 289
impressions, 0 clicks, average position 33.6. The English king-tide page had
84 of 306 page impressions at an average position of 8.1, the only page with
real volume on Google's first page. Its queries name a month or a place in
full and ask when: "king tides november 2026", "when are the king tides this
year", "king tides oregon 2026 schedule", "king tides puget sound 2026",
"king tides seattle 2026", "washington state king tides 2026". The title said
"WA, OR and CA", and the description led with "West Coast" and "Bellingham to
San Diego".

- **Title (in season):** "King tides {months}: Washington, Oregon and
  California" (54 characters for "November 2026", under 0020's 60), in place
  of "King tides {months}: WA, OR and CA dates and times". The months still
  come from 0015, and `scripts/check_site.py` still checks them.
- **Title (out of season):** "King tides 2026–27: Washington, Oregon and
  California dates".
- **Description (in season):** answer first: "The next West Coast king tides
  are {range}: the peak day, local time and height at {count} NOAA stations,
  from Seattle and Puget Sound to the Oregon coast and San Diego." Seattle,
  Tacoma, Olympia and five Oregon coast stations are on the page, so each
  name is something the page has.
- **Not changed:** the Spanish page (no Spanish queries yet), the H1 and
  body (the dates already lead, 0015), and station and region titles. Station
  pages averaged position 40 to 100, beyond Google's second page, where a
  title cannot earn a click; their fix is time and links, not copy.

At position 8 an 84-impression sample would expect about one to three
clicks, so 0 clicks is weak evidence on its own. Recheck the page's
click-through rate after the Nov 23 run.

**For the app:** nothing changes.

## 0028: King-tide pages answer the winter searches first; sitemap lastmod is the date a page changed (2026-11-09)

(0026 and 0027 are reserved for other branches.) Search Console for
sc-domain:tidehours.com, Aug 10 to Nov 7, 2026 (data from Nov 3 on): the
English king-tide page had 112 impressions, 1 click, average position 8.3,
the only page with real volume. Its named queries ask when, by month or
place: "king tides november 2026", "when are the king tides this year",
"king tides oregon 2026 schedule", "king tides puget sound 2026", "king
tides washington coast 2026", "washington state king tides 2026", "king
tides december 2026", "king tides seattle 2026". The three state calendars
(0024) had no impressions yet. Every sitemap `lastmod` was the build date, so
the king-tide pages claimed a change every day though their HTML had not
changed.

- **State calendars, title and description:** named for the places on
  them that people search ("Washington king tides 2026–27: Seattle, Puget
  Sound, coast"; "Oregon king tides 2026–27: coast schedule by month,
  Nov–Feb"; "California king tides 2026–27: San Francisco to San Diego"),
  from `kingtides.CALENDAR_SEARCH`. Every place named is a king-tide
  station's place or its catalog region (Puget Sound is Seattle's, Tacoma's
  and Olympia's region; San Francisco Bay is Golden Gate's, Alameda's and
  Redwood City's), checked by `tests/test_king_calendar.py`, with a
  negative control. Titles stay within 60 characters (0020).
- **Answer first:** each calendar opens with "When are the king tides in
  {state}?", one line per month: the days, the peak days and how many
  stations, from the same `CalendarMonth.span` the month's sentence uses,
  so the two cannot disagree. A month without a run says so in words. Still
  pinned to the season, never rolled by the build date (0024).
- **Definition:** the king-tide pages (English and Spanish) say that "king
  tide" is a popular, non-scientific name, as NOAA does, give NOAA's reason
  for higher tides, say what it means on the page, and say it does not
  forecast storms, waves or flooding.
- **Links:** the king-tide pages link the three calendars right under the
  lead, and the home page's king-tide paragraph links them too.
- **No region pages.** Puget Sound and San Francisco Bay have three
  king-tide stations each, all already on their state's calendar; a page of
  its own would repeat those rows (0022's thin-page concern). The titles and
  descriptions name them instead.
- **Sitemap lastmod:** `publish.yml` saves the live `sitemap.xml` and
  `lastmod.json` before the build, and `tidehours --previous` keeps a page's
  live `lastmod` when its SHA-256 matches the live one (0011); a changed or
  new page gets the build date. If either file is missing or unreadable, or a
  date is later than the build, every page gets the build date, as before.
  Station pages still change daily (today's tides), so they still carry the
  build date.

Not changed: the king-tide page's title and description (0025), the Spanish
title, URLs, and the app.

**For the app:** nothing changes.

## 0029: A link to the Tide Hours print shop on Etsy, off by default (2026-11-10)

(0026 and 0027 are reserved for other branches.) On 2026-11-10 the owner
opened an Etsy shop, TideHours, with one listing: a made-to-order print of
the tide at one place on one day, drawn by this site's engine. Each print's
footer names tidehours.com. The owner asked for a link back from the site.
The site's traffic is small (0028: the English king-tide page is the only
page with real volume), so this is a courtesy to a reader who wants the
print, not a traffic plan.

**The switch.** `Config.print_shop_url` (`--print-shop-url`, the repository
variable `PRINT_SHOP_URL`). Empty, the default, means off, and off leaves no
trace: no link, no section, and the privacy and terms pages as they were.
The value must be an Etsy shop's own address
(`https://www.etsy.com/shop/Name`): no listing, query string or tracking
parameter. A listing address changes when a listing is renewed or replaced;
the shop's does not.

**On.** The About page and the English king-tide page each end with a
"Prints" section of one sentence and one link (`rel="noopener"`). The copy
is in `src/tidehours/copy/print_shop.json`. The Spanish king-tide page has no
link, because the sentence has had no native-Spanish review. Station, state
and region pages have none: they are a reference, and 3,700 links to a shop
would read as an ad on every page. The privacy page says where the link goes
and that this site sends nothing to Etsy; the terms page adds Etsy to the
names and trademarks.

**Not an affiliate link.** The shop is Tide Hours' own. There is no tag, no
click event and no `sponsored` rel, and the sentence states no price and
makes no claim (a test refuses the same words 0016 refuses). The privacy
page's "no ads" sentence is unchanged: this is the site naming its own
print, as it names its own app.

**Checked.** `scripts/check_site.py --print-shop-url` fails the build if,
with no address, "etsy" appears in any page, the sitemap, robots.txt,
lastmod.json or llms.txt; or if, with one, either page lacks the link, has
it twice, or has another address or rel, or any other page links to or
mentions Etsy (the privacy and terms pages may name it). `publish.yml`
passes the same variable to the build and the check.
`tests/test_print_shop.py` covers both states and has negative controls for
each rule, each asserting the sabotage changed the build.

**What it changes for the print test.** Views that arrive from this site
count toward Etsy's view total, so the 2027-01-15 read of the listing is no
longer a read of Etsy's search alone.

**Reversible.** Yes: empty the variable and the next build has no link. To
remove the code, drop `printshop.py`, the copy file, the template and its
two includes, the privacy and terms lines, and the check.

**For the app:** nothing changes.

## 0030: A station page links to its own printed booklet on Amazon (2026-11-10)

(0026 and 0027 are reserved for other branches.) On 2026-11-10 the owner
published printed 2027 tide-table booklets through Amazon KDP under the
author name Tide Hours, one station each, computed by this site's engine:
Bar Harbor (station 8413320) and Half Moon Bay (9414131) are in Amazon's
review, and Garibaldi (9437540) and Brewster Flats (8447241) follow. The
reader of a station's page is the reader that station's booklet is for, so
the page says the booklet exists. None is on sale yet, so the list ships
empty.

**The list.** `src/tidehours/copy/booklets.json` maps a station id to its
booklet's ASIN, year and title. It ships empty, and empty leaves no trace:
the full build with the pinned clock is byte for byte the build before this
change (3,761 files compared, with the switches off and with all of them
on). There is no repository variable. An entry is added by a pull request
when a booklet is live, so an ASIN is reviewed like code and the same list
is what `check_site.py` reads. `--booklets FILE` on the build and on
`check_site.py` names another list; it is for tests.

**What the list refuses.** An ASIN that is not ten characters of "B0" and
eight capitals or digits, or an ISBN-10 whose check digit is right (a KDP
paperback has one or the other), matched in full, so a whole address, a
tag or a trailing space stops the build. A year that is not a whole number
from 2000 to 2099. A title that is not "YEAR Tide Tables: Place" with the
entry's own year. Any other key. One ASIN under two stations. A station id
the catalog does not have.

**The title is the booklet's own.** The first proposal was to build the
link text from the station's name ("Bar Harbor Tide Tables 2027"). The
titles the owner approved for the covers are "2027 Tide Tables: Bar Harbor",
"2027 Tide Tables: Half Moon Bay" and so on, and this site's names for two
of the stations are "Pillar Point Harbor, Half Moon Bay, CA" and "Sesuit
Harbor, East Dennis, MA" (the Brewster Flats booklet). A title built from
the station's name would be one no booklet has, so each entry carries the
title printed on its cover, and its shape is checked.

**The link.** Exactly `https://www.amazon.com/dp/ASIN`, with nothing after
it: no Associates tag, no query string, no tracking parameter, no click
event, `rel="noopener"` as in 0029. This is Tide Hours linking to its own
book, not an affiliate link, and it stays untagged when the affiliate switch
(0016) is on. Whether the Associates Operating Agreement asks for anything
when a site in the program also links to its own book without a tag was not
read for this change; that is with the owner.

**Where.** Only on that station's own page: one sentence with one link,
after the tide tables and the paragraph about the app and NOAA's own
predictions, before the type of tide, the nearby stations and the closing
notes. "A printed 2027 tide table for this station is sold on Amazon as
2027 Tide Tables: Bar Harbor." with the title as the link. It states no
price and makes no claim (a test refuses the words 0029 refuses). Not on
state, region, home or king-tide pages, and not in the page's title,
description or JSON-LD, the sitemap, robots.txt or llms.txt. `lastmod.json`
changes only in that page's fingerprint.

**When it leaves.** The link shows while the first day on the page, which
is the station's own date when the site was built, is in the booklet's year
or earlier. A 2027 booklet shows from the day it is listed until
December 31, 2027 at the station, and the build of January 1, 2028 has no
trace of it, with nobody editing a file. The entry can be removed whenever.

**Privacy and terms.** While at least one page in the build shows a link,
the privacy page has a "Booklet links" section (`/privacy/#booklets`) that
says Tide Hours publishes the booklet, that the link is plain, where it
goes and that this site sends nothing to Amazon; and the terms page names
Amazon among the trademarks, once, whether or not the affiliate switch is
also on. The sentence for every earlier combination of switches is
unchanged. The privacy page's "no ads" sentence is unchanged, as in 0029:
this is the site naming its own book.

**What changed in 0016's check.** Before: with no tag, "amazon" appears
nowhere; with one, an Amazon link appears only on the English king-tide
page. Now `check_site.py` reads the list, works out from each listed
station page's own date which pages are due the sentence, checks that
sentence by itself, takes it out of the page, and runs 0016's rules,
unchanged, on everything that is left. With no booklet listed the only
difference is that llms.txt joins the files that may never mention Amazon.
With one listed, the build fails if a due page has no sentence or two; if
the sentence has more than one link, an address that is not exactly the
booklet's, a rel other than `noopener` or a click event; if it sits before
the tide tables or after the closing notes; if a sentence is on any page
that is not due one, which covers a booklet whose year is over; or if
Amazon is linked or named anywhere else. With no tag, the privacy and terms
pages may name Amazon in words while a link shows, never with a link.

**Analytics.** The link has no event of its own. If the GA4 property's
Enhanced measurement counts outbound clicks, Google Analytics records a
click on any link that leaves the site, with its address; that is a
setting in the property, not in this repository, and it is with the owner
to check.

**What it changes elsewhere.** Listing a booklet, or its year ending,
changes that station's page and the privacy and terms pages, so their
sitemap `lastmod` moves and IndexNow announces them (0011, 0028); that is
expected.

**Tests.** `tests/test_station_booklets.py`: the empty list leaves no
trace; one booklet changes that page, privacy, terms and their
fingerprints and nothing else; bad entries are refused; the link leaves at
the year's end by the station's date; the affiliate switch and a booklet
together pass; and a negative control for each rule above, each asserting
the sabotage changed the build. `tests/test_site.py` builds California
with an empty list, so its tests do not change when a California booklet is
listed.

**Reversible.** Yes: empty the list and the next build has no link. To
remove the code, drop `booklets.py`, the two copy files, the template and
its include, the privacy and terms lines, and the check.

**For the app:** nothing changes.

## 0031: Highs and lows keep a year's constants for 30 minutes into the next (2026-11-10)

**What was wrong.** The engine picks each instant's lunar-node constants (f
and V0 + u) by its GMT year, as the app does, so its curve steps at 00:00
GMT on January 1 and it found every high and low on that stepped curve.
NOAA's published highs and lows do not all step there. At Bar Harbor
(8413320) NOAA's low on 2028-01-01 is at 00:09 GMT and 0.377 ft; the engine
said 00:07 and 0.465 ft. No test looked at this hour: the fixtures were
November 2026 and June 2031.

**Measured (2026-11-10).** 20 requests to NOAA's predictions API, each for
two days, two seconds apart (`scripts/fetch_golden.py --year-boundary`,
`tests/fixtures/golden-year-boundary.json`): the highs and lows at 18
stations, the 6-minute heights at one, and Bar Harbor's highs and lows
again, asked for from January 1. The stations were chosen with
the engine: harmonic stations with a high or low near 00:00 GMT on
2028-01-01 or 2027-01-01, spread over the first hour, where the two years'
constants give heights at least 0.04 ft apart. Each row is NOAA's tide
nearest midnight, where each year's constants, held, put that tide (minutes
after 00:00 GMT), and how far each is from NOAA's height.

2028-01-01:

| Station | NOAA (GMT) | Old year puts it at | and is off by | New year puts it at | and is off by | NOAA's is |
|---|---|---|---|---|---|---|
| Wauna, OR 9439099 | 23:55 H 6.820 ft | -4.94 min | +0.003 ft | -4.24 min | -0.107 ft | old |
| Popokamute, AK 9466057 | 00:02 H 5.444 ft | +2.39 min | +0.001 ft | +0.02 min | +0.188 ft | old |
| Bar Harbor, ME 8413320 | 00:09 L 0.377 ft | +8.86 min | +0.001 ft | +7.18 min | +0.088 ft | old |
| Oceanville, ME 8414249 | 00:25 L -0.251 ft | +24.96 min | -0.007 ft | +22.63 min | +0.130 ft | old |
| Fire Island, AK 9455912 | 00:26 L 5.634 ft | +25.88 min | -0.004 ft | +25.37 min | -0.273 ft | old |
| Wells, ME 8419317 | 00:29 L 0.125 ft | +29.17 min | -0.000 ft | +27.15 min | +0.072 ft | old |
| Kodiak, Womens Bay, AK 9457292 | 00:30 H 8.700 ft | +29.96 min | -0.001 ft | +30.71 min | -0.073 ft | old |
| Ouzinkie, AK 9457287 | 00:31 H 8.136 ft | +30.28 min | +0.061 ft | +31.04 min | +0.003 ft | new |
| Milbridge, ME 8412581 | 00:30 L 0.647 ft | +30.44 min | -0.040 ft | +29.45 min | +0.006 ft | new |
| New Haven, CT 8465705 | 00:31 L 0.164 ft | +31.64 min | -0.059 ft | +30.69 min | -0.000 ft | new |
| Pettegrove Point, ME 8410834 | 00:34 L 0.866 ft | +35.27 min | -0.237 ft | +34.09 min | +0.005 ft | new |
| Birch Islands, ME 8410875 (subordinate) | 01:33 L 0.461 ft | +93.00 min | -0.005 ft | +91.63 min | +0.104 ft | old |

2027-01-01:

| Station | NOAA (GMT) | Old year puts it at | and is off by | New year puts it at | and is off by | NOAA's is |
|---|---|---|---|---|---|---|
| Anchor Point, AK 9455606 | 00:02 L 3.252 ft | +1.87 min | -0.003 ft | -1.22 min | -0.179 ft | old |
| Port Angeles, WA 9444090 | 00:19 L 1.763 ft | +18.88 min | +0.007 ft | +16.40 min | -0.117 ft | old |
| Lomavik, AK 9466328 | 00:28 L 0.162 ft | +28.52 min | -0.001 ft | +25.75 min | -0.146 ft | old |
| Dolgoi Harbor, AK 9459758 | 00:32 L 1.561 ft | +33.77 min | +0.067 ft | +31.72 min | +0.005 ft | new |
| Platinum, AK 9465396 | 00:35 H 8.262 ft | +36.17 min | -0.227 ft | +35.42 min | -0.009 ft | new |
| Goodnews Bay, AK 9465438 | 01:01 H 8.317 ft | +61.68 min | -0.210 ft | +60.96 min | +0.009 ft | new |

Three rows measured earlier the same day and not in the fixture agree:
Eastport (8410140) 2028-01-01 00:20 L 0.615 ft is the old year's (-0.007
ft), and Anchorage (9455920) 00:37 L 5.904 ft and 06:05 H 27.812 ft are the
new year's. Every other tide in the two days at the 18 stations, 108 of
them, is the year's own to 0.010 ft: all of December 31 the old year's,
all from 05:54 GMT on January 1 the new year's.

**The rule that fits every row.** A high or low that the old year's
constants put before 00:30 GMT on January 1 is published with the old
year's constants. Otherwise it is published with the new year's. What
decides is where the old year's constants put the tide, not where the new
year's do and not NOAA's printed minute: Kodiak, Womens Bay (old year
00:29.96, new year 00:30.71) is the old year's, and Milbridge (old year
00:30.44, new year 00:29.45) is the new year's, though NOAA prints both at
00:30. The cutoff is between 29.96 and 30.28 minutes in 2028 and between
28.52 and 33.77 in 2027; 30 minutes is the one round number in both.

Also measured:

- **Before midnight.** No tide before 00:00 GMT uses the next year's
  constants (Wauna, five minutes before; every December 31 tide).
- **NOAA's curve is different.** NOAA's 6-minute heights at Fire Island,
  AK follow the old year's constants through 23:54 and the new year's from
  00:00 on, each to 0.007 ft. Its own curve reads 5.37 ft where its
  published 00:26 low says 5.634 ft. So NOAA's curve steps at midnight, as
  this engine's does, and only its list of highs and lows runs on.
- **Subordinate stations follow the reference's tide.** Birch Islands'
  01:33 low, 93 minutes after midnight, is the old year's: it is Eastport's
  00:20 low moved 73 minutes.
- **The answer does not depend on the request.** Bar Harbor asked for from
  January 1 gives the same 00:09 low, 0.377 ft, as asked for from December
  31.

**What changed.** `engine.py`, highs and lows only. `raw_events` finds
them year by year, each year's constants held from 30 minutes after its
start to 30 minutes after its end (`YEAR_CARRY`, `tide_year`), on a curve
with no step in it. At the hand-over (00:30 GMT) the two years can
disagree on whether the tide is rising (`_hand_over`):

- The old year has just passed a high or low and the new year has not
  reached it (Kodiak): the old year's stands, and the new year's copy of
  the same tide, which follows within the stand rule's 120 minutes and 0.06
  ft (0004), is left out.
- The new year has passed it and the old year has not reached it
  (Milbridge): neither finds it, so it is put at 00:30 with the new year's
  height there. NOAA prints that low at 00:30, half a minute after the new
  year's own 00:29.45.

`heights`, `height` and `curve` are unchanged: they step at 00:00 GMT, as
NOAA's 6-minute heights do. So for up to 30 minutes a year a high or low
can sit off the drawn curve by the size of the step (0.08 ft at Bar Harbor,
0.27 ft at Fire Island), as NOAA's does. Subordinate stations needed no
change: they take the reference station's highs and lows.

Finding highs and lows on a curve without a step also removes what the
step made. At Hanbury Point, WA on 2028-01-01 the old engine listed a
"low" of 6.148 ft followed by a "high" of 6.062 ft, one from each year's
constants; now the old year's 0.018 ft pair is a stand and is dropped.

**How much.** Over the ten new years 2026 to 2035 at the 1,232 harmonic
stations, 1,055 of 12,320 station-years change. In 1,053 one tide changes:
274 by 0.05 ft or more, 98 by 0.10 ft or more, the largest 0.27 ft. In the
other two (Hanbury Point and Telegraph Bay, WA, 2028) the pair above is no
longer listed. The changed tides are between 10 minutes before and 47
minutes after midnight, except 12 flat tides in Florida, Alabama,
Mississippi and Louisiana that the two years' constants put 22 minutes to
three hours apart, where the old year's is now the one kept (South Pass,
LA 2035: two minutes before midnight, not 51 after). A build on New Year's
Eve 2026 changes a row in the tide table of 147 station pages, and moves a
chart coordinate by half a unit or less on 879 more. The pinned build that
`make verify` makes (2026-11-01) is byte for byte the same, so no page's
HTML changes today.

**Tests.** `tests/test_golden.py`: each of the 18 stations passes the
existing comparison (3 minutes, 0.05 ft, same count) over its two days,
and its tide nearest midnight is within a minute and 0.02 ft of NOAA's,
which tells the two years apart at every station. Negative controls set
the carry to 0 (10 stations miss, Bar Harbor by 0.088 ft), 29.9 minutes
(Kodiak misses), 30.5 (Ouzinkie and Milbridge miss) and 60 (six of the
seven new-year stations miss). The 6-minute heights pin the curve to the
calendar year. On the engine before this change the tests of the 10
stations whose tide NOAA takes from the old year fail. No existing test
changed, no tolerance was loosened, and nothing was added to
`KNOWN_DIVERGENCES`: no divergence remains in the fixture.

**Not known.**

- Whether the cutoff is exactly 30 minutes, and whether a tide at 00:30:00
  itself is the old year's. Kodiak is 2.3 seconds inside it.
- Whether NOAA prints a tide the hand-over puts at 00:30 at that minute.
  It does at Milbridge, but there the new year's own low is only half a
  minute earlier. Kings Point, NY (8516945) on 2028-01-01 would settle it
  and narrow the cutoff: the old year puts the low at 00:30.21 and the new
  year at 00:27.40, 0.068 ft apart. The rule says NOAA's is the new year's,
  and the engine prints it at 00:30; NOAA prints 00:27 or 00:30. One
  request (add the station to `YEAR_BOUNDARY`); the 20 allowed for this
  measurement were used before the station was noticed.
- What NOAA publishes where the two years put one flat tide more than 30
  minutes apart on either side of 00:30 (12 station-years in ten above).
  The engine keeps one tide, never two or none; NOAA was not asked.
- Why NOAA does it. One mechanism reproduces every row, Milbridge's
  printed minute included: a search for changes of sign in the rate on
  6-minute steps, with a year's constants used through the 00:30 step.
  That is what `raw_events` now does, but it is a fit to what NOAA
  publishes at two new years, not NOAA's description. A third
  (2029-01-01) would be a cheap check: the same script with a new list of
  stations.

**For the app.** TideCore still finds highs and lows on the stepped
curve, so on New Year's Eve (the 30 minutes from 7:00 PM Eastern, 4:00 PM
Pacific, 3:00 PM Alaska, 2:00 PM Hawaii) the app can show a tide a few
minutes and up to 0.27 ft from NOAA's and from this site. To stay in step,
`HarmonicPredictor.events` in `Prediction.swift` would have to:

1. Evaluate dh/dt and the height in the search with one year's constants
   held, the year of `t - 1800 s`, not each instant's own year; and split
   the search at `yearStart(Y) + 1800 s`, so no 6-minute step or bisection
   straddles two years.
2. At each split point inside the range, or less than two hours before its
   start, compare the sign of dh/dt there under the old year's and the new
   year's constants. If they agree, do nothing. If they differ, take the
   new year's first high or low after the split point: when it is less
   than 120 minutes later and less than 0.06 ft from the new year's height
   at the split point, drop it (the old year already found that tide);
   otherwise add an event at the split point with the new year's height
   there, a low if the old year's curve was falling and a high if rising.
3. Leave `height(at:)` and the curve alone: they change constants at 00:00
   GMT, as NOAA's do.
4. Copy `tests/fixtures/golden-year-boundary.json` into TideCore's
   fixtures and assert the 18 tides nearest midnight to a minute and 0.02
   ft. The subordinate predictor needs no change.

The app is not changed here. Until it is, this is the second stated
difference between the site and the app, after 0004.

Update, 2026-11-11: the app made the same change the same day
(ChelseaKR/tide-hours DECISIONS 0006, #16); both engines give the same
highs and lows at the fixture's 18 stations and on three ordinary days at
three more, so
the site and the app no longer differ here.

## 0032: Station, state and region pages answer first (2026-11-12)

Search Console, 28 days to 2026-11-11 (876 impressions, 2 clicks): 557
impressions went to station pages, at a weighted position of 58. Of the 280
station impressions that came with a query, people typed the town, beach or
water body with "tides" (129), "tide chart" (47), "high tide" (32), "tide
schedule" (15), "tide table" (9), "tide times" (8) and "low tide" (7). They
named the place as NOAA's station name starts ("nantasket beach ma", "hull
tide chart", "duxbury tides", "high tide in ocean city md"). Pages are not
yet on page 1 or 2, so this is for the click once they are.

- **Station titles** (amends 0020's tiers; the 60-character fit stays): the
  longest of "{name} tides today: high and low tide chart", "{name} tides
  today: high and low", "{name} tides today" and "{name} tides" that fits
  (`site.station_title`). The name stays first because NOAA's names already
  start with the town or beach. The brand is left to `og:site_name`. Every
  indexed title now fits in 60 characters (four did not), and no two
  stations share one.
- **Station H1 and first screen:** the H1 is "{name} tides today". Then
  two plain questions, "When is high tide at {name} today?" and the same for
  low tide. Each lists today's and tomorrow's times in local time with
  heights, by date. The page's script adds "Today" or "Tomorrow" and hides a
  day that has passed, as it does for the day tables (0002). A day without a
  high or a low says so.
- **Meta description:** generated per station from the same numbers, in
  155 characters at most (`site.station_description`). Both days when they
  fit, else today's with a pointer to tomorrow, else today's alone. Dates,
  not "today", so it is true whenever it is read. The king-tide sentence is
  added only when it fits.
- **Nearby:** other stations in the same state within 25 miles, nearest
  first, at most 6, with distances (`site.neighbors`). A station with none
  shows no list. Before, every page listed the 6 nearest stations at any
  distance, across state lines.
- **State and region pages:** the title is "{state} tides today: tide times
  at {n} stations" and "{region}, {state} tides today: tide times", each
  fit to 60 characters. One line of lead, then the list. The king-tide
  callout moves below the list.

- **Searched names** (`copy/place_names.json`, `site.place_name`): five
  stations are searched by a name their page did not carry. Their title, H1
  and questions lead with that name, then the station: "Maui (Kahului,
  HI)", "Oʻahu (Honolulu, HI)", "Kauaʻi (Nāwiliwili, HI)", "St. Simons
  Island (St. Simons Light, GA)" and "OCMD, Ocean City (Fishing Pier), MD".
  Each entry names the Search Console query it comes from and what ties
  the name to the station (NOAA's region, or the station's own name). Like
  names.py, each entry is pinned to the station's current display name and
  stops applying when NOAA renames the station.

Other station names are not split into "town, then station". The catalog
has no town field, and guessing one from the name would be wrong for names
like "Sesuit Harbor, East Dennis".

## 0033: Index the subordinate station pages, except the twins (2026-11-12)

Supersedes 0013's noindex on subordinate station pages. (0026 and 0027 are
reserved for other branches.) 0013 held the 2,024 subordinate pages back on
2026-11-03 because each "is close to a copy of another page here". Measured
on a full build for 2026-11-12, that is true of two of them and not of the
other 2,022:

- **The answer differs.** A subordinate page's highs and lows are its
  reference's moved by NOAA's published minutes and scaled or shifted by its
  height corrections, so the table rows differ from the reference page's on
  2,023 of the 2,024 pages. Ano Nuevo Island, CA against San Francisco
  (Golden Gate): high 12:51 AM 3.9 ft against 2:15 AM 4.6 ft, and no row in
  common over the two days. Sebastian, FL against Government Cut, Miami:
  high 11:48 AM 0.4 ft against 10:16 AM 2.8 ft. Long Beach, Inner Harbor,
  CA against Los Angeles (4 and 5 minutes later, x0.96) still differs in
  every row.
- **The rest of the page is its own.** Name, title, description, region,
  breadcrumbs, coordinates, NOAA's own predictions link and nearby list are
  the station's. Over the 2,022 pages, a median 40% of a page's text lines
  (at least 19%) appear nowhere on its reference station's page, curves and
  scripts left out.
- **New on each page:** a "How this station is predicted" section that
  names the reference station (linked), its distance, and NOAA's published
  corrections in words ("high tide 1 h 24 min earlier, low tide 1 h 4 min
  earlier; heights 0.7 ft lower at high tide and 0.1 ft lower at low tide").
  That is data the reference page does not carry for this station in that
  form, and it says plainly how the numbers are made.

**Twins.** A subordinate station is a twin when both time corrections round
to 0 minutes and the high-tide height is unchanged (x1.00, or 0.0 ft), so
every time and every high tide on its page is its reference's, every day
(`subordinate.is_twin`, `Station.twin_of`). Two are:

- Cabrillo Beach, CA (9410650) from Los Angeles (Outer Harbor) (9410660):
  0 min, 0 min, x1.00, x1.00. Its table rows are the reference's byte for
  byte.
- Great Diamond Island, ME (8417988) from Portland (8418150): 0 min, 0 min,
  x1.00, x1.03; only the lows' heights can differ, by 3%.

A twin's page is still built, linked from its state, region and reference
pages and followed, but carries `noindex,follow`, a canonical link (and
`og:url`) to its reference station's page, and a sentence saying why; it is
left out of the sitemap and `lastmod.json`. Windham Bay, AK (9451962) has
0-minute times but highs 1.1 ft lower than Juneau's, so it is not a twin.

**Counts.** Station pages in the sitemap go from 1,232 to 3,254; the
sitemap from 1,577 to 3,599 URLs (the full pinned build); noindex pages from
2,177 to 155 (the 2 twins, the small region pages of 0022 and the moved
region stubs of 0017 and 0018).

**IndexNow.** `lastmod.json` holds only indexable pages, and today's tides
change every station page daily, so a normal day now announces about 3,254
station pages instead of about 1,232, under the 10,000 per request limit
(0011). The first deploy announces the 2,022 newly listed pages within that
count.

**The risk 0013 named.** Trout Truck lost about 97% of its impressions in
one re-rank on 2026-10-22, with a young domain of near-identical template
pages the leading explanation. This change roughly doubles the indexable
station pages on a domain under two weeks old. Two things make it a
smaller bet than 0013 feared: the pages are not near-identical in what a
searcher came for (the numbers differ on every indexed page), and 66
subordinate pages already drew 90 of 306 impressions while noindex
(growth/th-noindex-links-audit-2026-11-07.md), with 22 of them at a page-one
average position. A later read (growth/th-seo-competitors-2026-11-12.md,
876 impressions to 2026-11-12) found the noindex subordinate pages earning
284 impressions at an average position of 52.5, against 273 at 63.8 for the
indexed harmonic pages, and 25 subordinate pages with 3 or more impressions:
Nantasket Beach (20), Sebastian (13), Hull (9), Kemp Channel Viaduct (8, at
position 6), Bush Point (4, at position 14) and Norfolk (6, at position 23)
among them. Google already wants these pages, by name. A smaller step was
weighed: index only those 25 and 0013's five named places. It was not
chosen because the test that matters, whether a page has its own answer,
holds for 2,022 pages, not 30, and a named list would hold back pages on a
rule they pass. That list stays the fallback. To watch: total impressions and indexed-page count in
Search Console for four weeks after the deploy. If impressions fall
sitewide by half or more for a week, revert this change (`site.indexable`
is still the one place) and re-measure.

**Checked.** `scripts/check_site.py` fails the build if a twin's page lacks
noindex or its canonical to the reference, or any other station page has
noindex or a canonical other than its own URL. `tests/test_site.py`: an
indexed subordinate page's answer lines differ from its reference's; a
negative control that Cabrillo Beach stays noindex with Los Angeles as its
canonical, with its rows equal to Los Angeles's, and that a 1% change to
its high-tide ratio ends the twin; the sitemap holds every station page but
the twins (3,254 over the catalog).

## 0034: Structured data restates the page; dateModified is the sitemap lastmod (2026-11-12)

(0032 and 0033 are reserved for other branches.) Machine-readable facts for
search engines and AI answer engines, held to what the page already shows.

**Emitted** (`src/tidehours/schema.py`, `templates/_jsonld.html.jinja`):

- **Station pages:** a `Place` (the page's station name, `geo` with the
  catalog's latitude and longitude, `containedInPlace` the state the site
  lists it under) and a `Dataset` for the two days on the page:
  `temporalCoverage` those two dates, `isBasedOn` NOAA's prediction page
  for the station, `creditText` "Source: NOAA CO-OPS station <id>,
  predictions computed by Tide Hours on <build date>", and a description
  that says MLLW, local time, predictions not observations, not for
  navigation and not a NOAA product. The existing `WebPage` and
  `BreadcrumbList` nodes are unchanged. A station without a usable position
  gets no `Place` and no `spatialCoverage`. A station NOAA lists without a
  state, or filed under its reference station's state (0018), claims no
  `containedInPlace`, because the listing says nothing about where it is.
- **King-tide pages (English and Spanish):** a `Dataset` for the season's
  window (`temporalCoverage`), Washington, Oregon and California, named and
  described by the page's own heading and lead, based on NOAA CO-OPS data.
- **Every page in the sitemap, and every station page:** `<meta
  name="dateModified">`, and the same date on each JSON-LD `dateModified`.
  It is the page's sitemap `lastmod` (0028), never the clock: the page is
  rendered with a placeholder, its fingerprint for `lastmod.json` is taken
  then, and `site.write` puts the decided date in. So an unchanged page
  keeps its date and its fingerprint. A noindex page that is not a station
  page has no lastmod, so it carries no date. The first deploy with this
  change alters every page's HTML once, so every page gets that day's date
  and IndexNow announces every page once.
- **`/llms.txt`** (#20) now links the state and territory index, and the
  About page links `/llms.txt`; no other page does.

**NOAA is the creator of the source data, not of the predictions.** Tide
Hours computes them and is not a NOAA product, so each `Dataset`'s
`creator` is Tide Hours. On a station page, `isBasedOn` is a NOAA CO-OPS
`Dataset` whose creator is NOAA CO-OPS and whose `license` is NOAA's
public-domain statement (disclaimers.html).

**Never emitted:** `Event`, `Product`, `Offer`, reviews or ratings (nothing
here is sold, scheduled or rated); a `SearchAction` (the site has no
search); a `license` on Tide Hours' own predictions (an owner decision);
an `FAQPage` (the king-tide pages do have "What is a king tide?", but with
the affiliate and print-shop switches on, the English page is within about a
kilobyte of check_site's 120,000-byte limit, and the question and answer
would repeat 760 bytes the page already shows; no other page has a question
with its answer under it); `datePublished` (no record of when each page
first went live exists, and a guessed date would be a value standing in for
"unknown"); a `BreadcrumbList` for a one-item trail (state pages, as #13
decided).

**Validated** by `tests/test_jsonld.py`, stdlib only: every block parses
with `json`, and every type and property is in a table checked against
schema.org's vocabulary file (release 30.1): the type exists and each
property's `domainIncludes` covers it or a supertype. Forbidden types fail
the test. JSON-LD is written compactly (`schema.dumps`) to save page bytes.

**For the app:** nothing changes.

## 0035: A station page links to its own printable calendar on Etsy (owner, 2026-11-12)

(0032 to 0034 are reserved for other branches.) The Tide Hours shop on
Etsy (0029) now sells printable 2027 tide calendars, one town each,
computed by this site's engine: Bar Harbor (station 8413320), Half Moon Bay
(9414131) and Garibaldi (9437540). On 2026-11-12 the owner gave the three
listing ids from her live listings, approved the wording below, and asked
for each station's page to link to its own calendar, as 0030 does for the
printed booklets. The listings were not fetched for this change.

**The list.** `src/tidehours/copy/calendars.json` maps a station id to its
calendar's Etsy listing id, year and title, as `booklets.json` does (0030).
It ships with the three entries the owner gave. There is no repository
variable: an entry is added by a pull request when a listing is live, and
the same list is what `check_site.py` reads. `--calendars FILE` on the
build and on `check_site.py` names another list; it is for tests. An empty
list leaves the build byte for byte as it is without this change, apart
from the print shop's sentence below.

**What the list refuses.** A listing id that is not digits only (six to
fifteen, no leading zero), matched in full, so a slug
(`4614956632/2027-tide-calendar-bar-harbor`), a whole address, a query
string or a trailing space stops the build. A year that is not a whole
number from 2000 to 2099. A title that is not "YEAR Tide Calendar: Place"
with the entry's own year, or that carries one of the words 0030 refuses.
Any other key. One listing under two stations. A station id the catalog
does not have.

**The link.** Exactly `https://www.etsy.com/listing/ID`, with nothing after
the id: no slug (Etsy's own links add one, and it changes when a listing is
renamed), no query string, no tracking parameter, no click event,
`rel="noopener"` as in 0029. The shop is Tide Hours' own, so this is not an
affiliate link.

**Where.** Only on that station's own page, one sentence with one link, in
the place 0030 gives the booklet sentence (after the tide tables and the
paragraph about the app, before the type of tide, the nearby stations and
the closing notes), and after the booklet sentence when a station has both:
"A printable 2027 tide calendar for this station is in the Tide Hours shop
on Etsy: 2027 Tide Calendar: Bar Harbor." with the title as the link. No
price, no image, no claim. Not on state, region, home or king-tide pages,
and not in the page's title, description or JSON-LD, the sitemap,
robots.txt or llms.txt. The site has no Spanish station pages, so there is
no Spanish sentence, as in 0030; the Spanish king-tide page still has no
Etsy link (0029).

**When it leaves.** As 0030: the link shows while the first day on the page,
the station's own date when the site was built, is in the calendar's year
or earlier. The 2027 calendars leave the three pages with the build of
January 1, 2028, with nobody editing a file.

**The print shop's sentence.** With the print shop on (0029), the About and
English king-tide pages now say: "Tide Hours also sells a made-to-order
print of the tide at one place on one day, and printable 2027 tide
calendars for a few towns, all drawn from the same predictions as this
site. They are in the Tide Hours shop on Etsy." (owner's wording,
2026-11-12). The year is in the copy file, not computed; it needs an edit
when the calendars change year.

**Privacy and terms.** The privacy page's section on the Etsy links
(`/privacy/#shop`) says what the build shows, and `calendars.notice` picks
it, as `booklets.notice` does for 0030's section:

- No Etsy link: no section, as before.
- The print shop only (no calendar link shows, for example in 2028): 0029's
  sentence, unchanged, under "Shop link".
- The print shop and a calendar link, as the site is published: "The About
  and king tides pages, and the station pages of towns with a printable
  calendar, link to the Tide Hours shop on Etsy. This site sends nothing to
  Etsy. The link takes you to Etsy, where Etsy's own privacy policy
  applies." (owner's wording, 2026-11-12), under "Shop links".
- A calendar link with the print shop off: "The station pages of towns
  with a printable calendar link to that calendar in the Tide Hours shop
  on Etsy." and the same two sentences after it. This one is a build
  decision: it says nothing about the About and king-tide pages, which then
  have no link.

The terms page names Etsy among the trademarks, once, while any Etsy link
shows. The "no ads" sentence is unchanged, as in 0029 and 0030.

**What changed in 0029's check.** As 0030 did for 0016's: `check_site.py`
reads the list, works out from each listed station page's own date which
pages are due the sentence, checks that sentence by itself, takes it out of
the page, and runs 0029's Etsy rules, unchanged, on everything that is
left. The build fails if a due page has no sentence or two; if the sentence
has more than one link, an address that is not exactly the listing's, a rel
other than `noopener` or a click event; if it sits before the tide tables,
after the closing notes or before the booklet sentence; if a sentence is on
any page that is not due one, which covers a calendar whose year is over;
or if Etsy is linked or named anywhere else (with no shop address, the
privacy and terms pages may name Etsy in words while a calendar link shows,
never with a link). New: the privacy page's section must be exactly the one
`calendars.notice` gives for the build, so a section that names pages with
no link, or leaves out pages with one, fails.

**Accessibility sample.** `scripts/site_sample.py` adds the station pages
of the booklet and calendar lists to the pages `make site-checks` audits,
so the sentence is checked by axe and pa11y.

**Analytics.** As 0030: the link has no event of its own. Whether GA4's
Enhanced measurement records outbound clicks is a setting in the property,
with the owner.

**What it changes elsewhere.** The three station pages and the privacy page
change (the terms page already names Etsy while the print shop is on), and
with them their sitemap `lastmod`, so IndexNow announces them (0011, 0028).
So do the About and king-tide pages, for the print shop's sentence. Views
that arrive from these links count toward the listings' Etsy views.

**Tests.** `tests/test_station_calendars.py`: the committed list is the
owner's three; bad entries are refused (a letter, a slug, a URL, a query
string, a bad title, a claim word, a duplicate listing, an unknown
station); the empty list leaves no trace; one calendar changes that page,
privacy, terms and their fingerprints and nothing else; the three committed
calendars show on their three pages only, with the exact sentence and
address, and leave on January 1, 2028; the privacy section in each of the
four cases; the print shop's sentence; the booklet sentence first when both
show; and a negative control for each rule above, each asserting the
sabotage changed the build. `tests/test_site.py` builds California with an
empty calendar list, so its tests stay about the site without one.

**Reversible.** Yes: empty the list and the next build has no calendar
link. To remove the code, drop `calendars.py`, the two copy files, the
template and its include, the privacy notice's calendar cases, the terms
condition, the sample line and the check, and put back 0029's sentence in
`copy/print_shop.json`.

**For the app:** nothing changes.

Update, 2026-11-12 (evening): six more calendars went on sale and are added
to `copy/calendars.json` at the owner's request: La Jolla (9410230), Monterey
(9413450), Hull (8444351), St. Simons Island (8677344), Ocean City (8570283)
and Westport (9441102), with the listing ids the owner gave. Nothing else changes;
the sentence, the checks and the 2028 removal apply to all nine.

Update, 2026-11-12 (night): three more, Eastport (8410140), Brewster Flats
(Sesuit Harbor, 8447241) and New Smyrna Beach (8721164), bring the list to
twelve, with the listing ids the owner gave.

Update, 2026-11-13: sixteen more calendars went on sale and are added at the
owner's request, bringing the list to twenty-eight: Plymouth (8446493),
Portsmouth (Fort Point, 8423898), Kennebunkport (8418911), Portland (8418150),
Fort Bragg (Noyo Harbor, 9417426), Olympia (Olympia Shoal, 9446807),
Newburyport (8440466), Duxbury (8446166), Provincetown (8446121),
St. Augustine (St. Augustine Beach, 8720587), Hatteras Island (Cape Hatteras
Fishing Pier, 8654400), Seward (9455090), Gloucester (8441841), La Push
(9442396), Hood Canal (Union, 9445478) and Homer (9455558). Each link goes on
the page of the station its calendar is computed from. Nothing else changes.

Update, 2026-11-13 (night): twelve more calendars went on sale and are added
at the owner's request, bringing the list to forty: Long Beach (Cape
Disappointment, 9440581), Eureka (Humboldt Bay, North Spit, 9418767),
Ogunquit (Wells, Webhannet River, 8419317), Tybee Island (Fort Pulaski,
8670870), Fernandina Beach (8720030), Atlantic Beach (8656590), Old Orchard
Beach (Pine Point, Scarborough River, 8418445), Wrightsville Beach (8658163),
Newport (Southbeach, 9435380), Myrtle Beach (Springmaid Pier, 8661070), Cape
May (ferry terminal, 8536110) and Lewes (Breakwater Harbor, 8557380). Each
link goes on the page of the station its calendar is computed from, as
before. Delaware, New Jersey and South Carolina join the states whose pages
can show one. Nothing else changes.

## 0036: Near stands: fewer highs and lows NOAA does not list (2026-11-12)

**What was wrong.** The site's standard is that it shows no tide NOAA does
not list. The stand rule of 0004 removes a high and a low less than 120
minutes and less than 0.06 ft apart. Checks for the print shop found tides
it leaves in that NOAA leaves out: at Port Townsend, WA (9444900) in 2027
all 1,387 of NOAA's tides matched and the engine printed 12 more, six
pairs 90 to 114 minutes and 0.061 to 0.092 ft apart. The 0.06 ft came from
one month at 14 small-range stations (0004), where no pair NOAA omitted
was taller than 0.07 ft.

**Measured (2026-11-12).** NOAA's lists for 178 stations, 110,591 tides
(some days are in two lists): the golden fixtures, the lists saved by the
print shop's checks (43 station-years of 2027 and 52 months and days),
and 40 new requests to NOAA's predictions API, one at a time, two
seconds apart, none repeated, at 33 stations: 2027 at 31 stations picked
with the engine for near stands (Puget Sound and the San Juans, the Gulf
of Mexico, the Caribbean, San Francisco Bay, Alaska, and the double tides
of Maine, Cape Cod, Narragansett Bay and the East River), and nine shorter
ones. NOAA's public pages do not state a rule for predictions; the one
number found is in its hydrographic survey specifications (April 2017,
4.3.2), for tabulating observed tides: successive tides are tabulated only
when "greater than 2.0 hours apart in time and 0.030 meters different in
elevation".

What NOAA's own lists show:

- **In NOAA's own heights the line is 0.100 ft.** NOAA lists 257 pairs of
  a high and a low less than 120 minutes apart by its own printed times
  (65 in its to-the-minute lists at harmonic stations, 84 in its
  6-minute-grid lists, 108 at subordinate stations). The smallest
  difference between the two printed heights is 0.100 ft, four times; none
  is 0.099 ft or less. Subordinate stations follow the same line in their
  own times and heights, not their reference station's.
- **On the engine's heights the line is blurred by a few thousandths of a
  foot.** In NOAA's to-the-minute lists at harmonic stations the engine
  puts 1,077 pairs under 118 minutes apart. Under 0.09 ft, NOAA lists both
  tides of one pair in 919 (in a flat run of five tides at Magueyes Island,
  PR). From 0.09 to 0.0984 ft, of 2 in 25: both at Friday Harbor, WA,
  0.0977 and 0.0978 ft here and 0.101 and 0.103 ft in NOAA's heights. From
  0.0984 ft up, of 61 in 133; it omits both tides of two (Woods Hole, MA,
  0.0991 ft here, and Bangor, below) and one tide of the other 70, each
  time where that tide is also in a second, flatter pair.
- **The two hours are blurred by a minute or two.** NOAA lists pairs the
  engine puts 118.5 minutes apart (Point Au Fer, LA, subordinate, 0.071
  ft), 119.3 (Friday Harbor, 2027-03-17, 0.062 ft), 119.4 and 120.0 (Vaca
  Key, FL), and omits pairs the engine puts 119.3 (Port San Luis, CA,
  2027-03-15, 0.064 ft), 120.3 (Christiansted, VI), 121.8 (Captiva, FL)
  and 126.1 (Charlotte Amalie, VI) minutes apart. No line on the engine's
  clock separates them.
- **Three tides in question.** Where a high, a low and a high (or a low, a
  high and a low) are each under two hours and 0.10 ft from the next, NOAA
  lists one of the outer two. Which one was not found: it lists the later
  one in most cases (Vineyard Haven, MA six times of six; Vaca Key 11
  times) and the earlier one in others (Cape Cod Canal five times of seven,
  Levelock, AK four of four), and neither "flattest pair first", "first
  pair first" nor "shortest pair first" fits them all. A search for sign
  changes on a coarser grid (steps of 6 to 120 minutes, offsets every 6
  minutes) does not either.
- **NOAA has two answers for some stations.** Asked for all of 2027 at
  Vineyard Haven, Edgartown, Rumford, Providence, Worlds Fair Marina,
  Harlem River and Port St. Joe, NOAA answers with every time on a
  6-minute mark and a few tides its shorter answer does not have (two lows
  in a row at Rumford on 2027-07-12). Asked for nine days at Rumford or a
  month at Vineyard Haven and Edgartown, it answers to the minute, as it
  does for a year at the other 66 stations asked for a year. The site
  shows a week, and the print shop's order check asks for a day, so the
  to-the-minute answer is the one this decision follows; both were counted.

The cases that started this, each a pair the engine printed and NOAA
omits (times GMT, as the engine has them):

| Station | Day | The pair | Minutes apart | Feet apart | The 0.06 ft rule missed it on | Now |
|---|---|---|---|---|---|---|
| Port Townsend, WA 9444900 | 2027-01-18 | H 11:10 7.646, L 12:51 7.554 | 100.8 | 0.092 | height | removed |
| Port Townsend | 2027-03-30 | L 14:22 6.473, H 16:16 6.554 | 113.6 | 0.081 | height | removed |
| Port Townsend | 2027-04-28 | L 14:07 5.848, H 15:46 5.915 | 99.8 | 0.067 | height | removed |
| Port Townsend | 2027-07-28 | H 22:44 6.867, L 00:20 6.799 | 95.5 | 0.068 | height | removed |
| Port Townsend | 2027-10-08 | L 02:23 6.119, H 04:07 6.208 | 104.3 | 0.089 | height | removed |
| Port Townsend | 2027-11-06 | L 02:02 5.807, H 03:33 5.868 | 90.2 | 0.061 | height | removed |
| Rumford, RI 8453433 | 2027-07-17 | L 05:00 1.186, H 06:05 1.248 | 64.6 | 0.062 | height | removed |
| Redhook Bay, VI 9751540 (subordinate) | 2026-01-08 | L 00:58 0.237, H 02:52 0.304 | 114.5 | 0.067 | height | removed |
| Port San Luis, CA 9412110 | 2027-03-15 | H 00:44 2.743, L 02:43 2.679 | 119.3 | 0.064 | height | printed: inside the time margin |
| Anna Maria Key, FL 8726243 (subordinate) | 2026-01-18 | H 18:42 1.116, L 20:29 1.018 | 106.4 | 0.098 | height | printed: inside the height margin |
| Captiva, FL 8725383 | 2027-10-05 | H 23:01 1.888, L 01:03 1.857 | 121.8 | 0.032 | time | printed: over two hours on the engine's clock |
| Christiansted, VI 9751364 | 2024-09-20 | L 21:25 0.642, H 23:25 0.655 | 120.3 | 0.014 | time | printed: over two hours on the engine's clock |
| Bangor, ME 8414612 | 2027-08-13 | L 13:34 10.447, H 14:32 10.568 | 57.8 | 0.121 | height | printed: not explained |

**The rule.** NOAA's own: a high and a low less than two hours apart are
listed only when NOAA's heights for them differ by 0.100 ft or more. That
is one rule, and it does not fit the engine as it stands, because the
engine's times and heights are not NOAA's to the last digit: with 120
minutes and 0.10 ft the engine removes tides NOAA lists (six at Friday
Harbor alone). So the engine takes the part of it that removes no tide
NOAA lists anywhere it was tested: after the stands of 0004, a **near
stand** is removed, a high and a low less than 115 minutes and less than
0.095 ft apart, unless the tide before the pair or the tide after it is
itself within 120 minutes and 0.10 ft of its neighbor in the pair. The
margins are five minutes under NOAA's two hours and 0.005 ft under its
0.100 ft; the closest pairs NOAA lists are 118.5 minutes and 0.0977 ft
apart here. Where a neighbor is that close, three tides are in question
and all three stay, as before.

**What changed.** `engine.py`: `drop_stands` runs 0004's rule unchanged
and then `_drop_near_stands` (`NEAR_STAND_MINUTES`, `NEAR_STAND_FEET`,
`NOAA_STAND_FEET`). `STAND_MARGIN`, the time read on each side of a window
so that an answer does not depend on where the window starts, goes from
three hours to six: the pair, the pair beside it, and the pair that could
remove that one. Harmonic and subordinate stations both go through
`drop_stands`, so both change; a subordinate pair is judged in its own
times and heights, as NOAA's are. `raw_events`, the curve and the year
boundary (0031) are untouched.

**How much.** Against every list on hand, 316 lists at 178 stations,
110,591 NOAA tides: the engine printed 1,194 tides NOAA does not list and
now prints 584; NOAA's tides it does not print are the same 375 before and
after (271 at Port of West Sacramento, below), and none is newly left
out.

| NOAA's lists | Lists | Stations | NOAA tides | Extra before | Extra now | NOAA tides not printed, before and now |
|---|---|---|---|---|---|---|
| To the minute, harmonic | 222 | 125 | 84,394 | 314 | 102 | 32 |
| 6-minute grid (a year at seven stations) | 7 | 7 | 9,548 | 438 | 152 | 72 |
| Subordinate | 86 | 48 | 15,238 | 156 | 50 | 0 |
| Port of West Sacramento, CA | 1 | 1 | 1,411 | 286 | 280 | 271 |

Over all of 2027 at all 3,256 stations the engine printed 4,377,685 highs
and lows; 1,549 fewer now, at 146 stations (61 harmonic, 85 subordinate:
50 in Alaska, 34 in Florida, 34 in Washington, 8 in California, 7 in
Louisiana, 5 in Hawaii, 4 in Massachusetts, 2 in Rhode Island, 1 each in
Maine and the Virgin Islands), and none added. Most: Vineyard Haven and
Edgartown (104 each), Port St. Joe (58), Mangrove Point (46). In the nine
days around the pinned build (2026-11-01) 38 tides at 18 stations go. The
twelve stations with a printed calendar or booklet (0030, 0035) do not
change in 2027: not one tide.

**What is left**, in NOAA's to-the-minute and subordinate lists (152
tides):

- Pairs inside the margins: from 115 minutes up or from 0.095 ft up on the
  engine's numbers, which NOAA omits (Port San Luis, Anna Maria Key, two
  pairs at Friday Harbor).
- Pairs the engine puts just over two hours apart, 120.3 to 126.1 minutes,
  all very flat, which NOAA omits (Captiva, Christiansted, Charlotte Amalie,
  Corpus Christi). 0004 recorded these.
- Three tides in question, where the engine keeps all three, or keeps the
  other one of the outer two (Vineyard Haven, Vaca Key, Woods Hole, Cape
  Cod Canal, Galveston). Where it keeps the other one, a NOAA tide is not
  printed: the 32 above, all there before this change.
- Reference wiggles of 0.0024 ft or less that NOAA's subordinate lists do
  not show (Skan Bay, AK 12 tides, Christmas Bay, TX 6): whether such a
  wiggle exists at all turns on the fourth decimal of the reference curve.
- Bangor, ME, 2027-08-13: a low and a high 57.8 minutes and 0.121 ft
  apart, which NOAA omits, though it lists a pair 52.9 minutes and 0.102
  ft apart there on 2027-09-11. Not explained.

**Tests.** `tests/fixtures/extra-tides/`: eight of NOAA's answers, byte
for byte, with their SHA-256 in docs/DATA.md and in the test. In
`tests/test_golden.py`: Port Townsend's 2027 (1,387 tides), Rumford's nine
days and Redhook Bay's three now pass the accuracy gate whole (3 minutes,
0.05 ft, the same count); every tide still printed that NOAA does not list
is named with its cause (22, from 68 before); the two NOAA tides not
printed are the same two as before. Negative controls, each asserting
first that the sabotage changed the output: 0.08 and 0.09 ft leave Port
Townsend pairs; 0.10 ft removes the pair NOAA lists at Friday Harbor on
2027-12-29; 0.125 ft removes ten of NOAA's tides at Vineyard Haven; 110
minutes leaves pairs at Port Townsend and Redhook Bay; 120 minutes removes
the pair NOAA lists at Friday Harbor on 2027-03-17; 150 minutes, one rule
of 120 minutes and 0.095 or 0.10 ft, any height under two hours, 0.095 ft
at any spacing, and no guard each remove tides NOAA lists. On the engine
before this change 18 tests fail. One line of `KNOWN_DIVERGENCES` goes:
the Redhook Bay pair of 2026-11-06 is no longer printed. No tolerance was
loosened.

**Not known.**

- Whether NOAA's line is 0.100 ft or 0.030 m (0.0984 ft). No listed pair
  is printed 0.099 ft apart; about three would be expected if the line
  were 0.0984 ft.
- Which of the two outer tides NOAA lists when three are in question, and
  so how to remove the 32 NOAA tides the engine does not print.
- Why NOAA omits the Bangor pair of 2027-08-13.
- Why NOAA answers a year's request at seven stations on a 6-minute grid,
  and what rule that answer follows: it lists two lows in a row, which
  removing pairs cannot produce. Where the two answers differ, the engine
  now agrees with the to-the-minute one more often than with the other.
- Port of West Sacramento, CA (9416131): the engine's highs and lows are a
  median 18 minutes from NOAA's and 271 of NOAA's 1,411 have no engine tide
  within 45 minutes. This is not a stand; it was found here and not looked
  into.
- NOAA was asked about 2027 almost everywhere. Other years are only the
  saved lists and the fixtures (a day to a month each, 1946 to 2035, most
  of them November 2026), which agree.

**For the app.** TideCore has `dropStands` from 0004 (tide-hours #2) and
nothing for near stands, so the app shows the 1,549 tides in 2027 that the
site no longer does. To stay in step, in `Prediction.swift`:

1. After `dropStands` has removed every high/low pair less than 120
   minutes and less than 0.06 ft apart, flattest first, repeat until none
   is found: among adjacent pairs of a high and a low (either order) that
   are less than 115 minutes apart (strictly) and less than 0.095 ft apart
   (strictly), skip any pair where the event before it and the pair's
   first event are of different kinds, less than 120 minutes apart and
   less than 0.10 ft apart, or the pair's second event and the event after
   it are; of the pairs not skipped, remove the one with the smallest
   height difference, both events.
2. Read six hours of events on each side of the window before removing
   anything, not three (`STAND_MARGIN`), and for a subordinate station six
   hours plus the larger time offset plus 30 minutes, as now.
3. Apply it to subordinate stations after the offsets, to the sorted list,
   exactly as `dropStands` is applied.
4. Copy `tests/fixtures/extra-tides/` and assert the same lists: no extra
   tide at Port Townsend in 2027, four at Friday Harbor, and the named
   ones elsewhere.

The app is not changed here. Until it is, this is a stated difference
between the site and the app.

**Reversible.** Yes: set `NEAR_STAND_MINUTES` to 0 and the engine is 0004's
again (with the wider margin, which removes nothing by itself).

## 0037: Station pages link to their posters, and one page lists every calendar and poster (2026-11-13)

The Tide Hours shop on Etsy (0029) now also sells printable year-of-tides
posters, one town each, as digital downloads: Bar Harbor (station 8413320),
Eastport (8410140), Homer (9455558), Provincetown (8446121), La Jolla
(9410230) and Monterey (9413450). On 2026-11-13 the owner gave the six
listing ids from her live listings and asked for two things, to send more
of the site's readers to the listings: each of those station pages links
to its poster, as 0035 does for the calendars, and one page lists every
calendar and poster. The site had no such page. The listings were not
fetched for this change. The wording below is this change's, for the owner
to approve before it is merged.

**The poster list.** `src/tidehours/copy/posters.json` maps a station id to
its poster's Etsy listing id, year and title, as `calendars.json` does
(0035), and refuses what that list refuses: a listing id that is not digits
only, a year that is not a whole number from 2000 to 2099, a title that is
not "YEAR Tide Poster: Place" with the entry's own year or that carries one
of the words 0030 refuses, any other key, one listing under two stations,
and a station the catalog does not have. New: a listing that is also in the
calendar list stops the build. Each poster is listed under the station its
town's calendar is listed under; each of the six towns has exactly one
station in `calendars.json`. `--posters FILE` on the build and on
`check_site.py` names another list; it is for tests. There is no repository
variable.

**The poster sentence.** On that station's own page, right after the
calendar sentence (0035): "A printable 2027 year-of-tides poster for this
station is in the Tide Hours shop on Etsy: 2027 Tide Poster: Bar Harbor."
with the title as the link. The link is exactly
`https://www.etsy.com/listing/ID` with `rel="noopener"`, as in 0035: no
slug, no query string, no parameter of any kind, no click event, no price,
no image, no claim. It leaves with the build of January 1, 2028, as the
calendars do.

**The page.** `tide-calendars/` ("Printable 2027 tide calendars and
posters"), from `printables.py`, `copy/printables.json` and
`templates/printables.html.jinja`. It is built from the two lists and
nothing else: every town whose station page shows a calendar or poster
link in this build, under its state's name, states and towns in
alphabetical order. A town's name links to its station page, and after it
come the same links the station page carries, the calendar first:
"Bar Harbor: 2027 Tide Calendar: Bar Harbor, 2027 Tide Poster: Bar
Harbor". Above the list, two paragraphs: "Tide Hours sells printable 2027
tide calendars and year-of-tides posters, one town each, as digital
downloads in the Tide Hours shop on Etsy." and "They are listed here by
state. Each town's name links to its tide times on this site, and each
calendar or poster links to its listing on Etsy." The description is
"Printable 2027 tide calendars and posters from Tide Hours, one town each,
listed by state, with links to each town's tide times and its Etsy
listing." As published it lists 28 towns in 11 states and 34 listings.

- No price, image, claim, count or shop link on it, and no JSON-LD: nothing
  on this site is marked up as a product or an offer (0034).
- It is an indexed page: in the sitemap and `lastmod.json`, with the
  `dateModified` every sitemap page has. It is not in `llms.txt`, which
  still says nothing about Etsy (0029).
- The words follow what the build has, as the privacy section does in
  0035: with calendars only, "Printable 2027 tide calendars" and "each
  calendar"; with posters only, "Printable 2027 tide posters" and "each
  poster"; with calendars and posters of more than one year, no year. As
  published it is always the first form. The address stays
  `tide-calendars/` in each case.
- A build whose station pages show no calendar or poster link has no such
  page and no link to one. So the page leaves with the links on January 1,
  2028, and an empty pair of lists leaves no trace.

**The footer.** While the page exists, the footer of every English page,
the 404 page included, links to it after Privacy, Terms and About: "Tide
calendars and posters" ("Tide calendars" or "Tide posters" when the build
has one kind). The header's three links are unchanged. The Spanish
king-tide page's footer does not link to it: the page is in English and the
label has had no native-Spanish review (0029). 0029 kept shop links off
station, state and region pages because 3,700 links to a shop would read as
an ad on every page. This is one link to a page of this site, among the
footer's other page links, and no page links to Etsy that did not before
except the new one; it is still a pointer to things for sale on every page,
and the owner asked for it.

**What it changes in 0035.** "Only on that station's own page" now reads:
on that station's own page and on `tide-calendars/`. The privacy page's
section on the Etsy links (`/privacy/#shop`) is now picked by
`printables.notice`, which replaces `calendars.notice`, and its sentences
name the new page, so the two sentences the owner worded on 2026-11-12
change:

- No Etsy link: no section, as before.
- The print shop only (for example in 2028): 0029's sentence, unchanged.
- The print shop and a calendar or poster link, as the site is published:
  "The About and king tides pages, the tide calendars and posters page,
  and the station pages of towns with a printable calendar or poster, link
  to the Tide Hours shop on Etsy. This site sends nothing to Etsy. The
  link takes you to Etsy, where Etsy's own privacy policy applies."
- A calendar or poster link with the print shop off: "The tide calendars
  and posters page, and the station pages of towns with a printable
  calendar or poster, link to those calendars and posters in the Tide
  Hours shop on Etsy." and the same two sentences after it.

In the last two, a build with one kind names that kind only ("the tide
calendars page", "a printable calendar"). The last two sentences of each
are 0035's, word for word. The terms page names Etsy among the trademarks
as before. The print shop's sentence on the About and king-tide pages
(0035) is not changed: it still says "printable 2027 tide calendars for a
few towns" and does not name the posters or link the new page.

**Checked.** `check_site.py` reads the poster list as it reads the calendar
list, works out from each listed station page's own date which pages are
due the poster sentence, checks that sentence by 0035's rules (exactly one,
one link, exactly the listing's address, `rel="noopener"`, no click event,
between the tide tables and the closing notes, after the booklet and
calendar sentences), and takes it out before 0029's Etsy rules run on the
rest. New, `check_printables`: while any page is due a calendar or poster
sentence, `tide-calendars/` exists; its title, heading and two paragraphs
are exactly `printables.py`'s for those sentences; its towns are exactly
the due ones, in order, each with its station page's address and name and
each listing's exact address and title; it has one Etsy link for each
listing and no other, each `rel="noopener"` with no click event; and Etsy
is not in its JSON-LD. That page is the one page left out of 0029's rules.
Every page with `lang="en"` links to it exactly once and the Spanish page
not at all; with no sentence due there is no such page and no link to it
anywhere. The privacy section must be exactly `printables.notice`'s.
`check_page`'s rules (the required statements, the size limit, no broken
internal link) apply to the page as to any other.

**Accessibility sample.** `scripts/site_sample.py` adds the page, when the
build has it, and the station pages of the poster list to the pages
`make site-checks` audits. The page is a heading, two paragraphs, and a
heading and a list for each state. The list is styled as the station
lists are, in one column at every width: three selectors in `style.css`
gain `ul.printables`. It adds no script.

**Analytics.** None added. As in 0030 and 0035 the links have no event of
their own; whether GA4's Enhanced measurement records outbound clicks is a
setting in the property, with the owner.

**What it changes elsewhere.** The footer link changes the HTML of every
English page once, so the build that first carries it gives every page
that build's sitemap `lastmod`, and IndexNow announces the state, region,
king-tide and other pages that otherwise change rarely, along with the
station pages it announces every day (0011, 0028). The six station pages
gain the poster sentence, and the sitemap gains one URL. Views that arrive
from these links count toward the listings' Etsy views (0029).

**Tests.** `tests/test_station_posters.py`: the committed list is the
owner's six, each under its calendar's station, no listing in both lists;
bad entries are refused; the empty list leaves no trace; one poster puts
one link on its page and on the list page; the sentence after the calendar
sentence; the 2028 removal; and a negative control for each rule of the
sentence. `tests/test_printables.py`: the published page, word for word,
with its 28 towns and 34 listings in order, each town's links the same as
its station page's; the sitemap; the footer of every English page and not
the Spanish one; the words for each kind; no page and no link with nothing
to list or in 2028; the accessibility sample; and 21 negative controls for
`check_printables`. Each negative control asserts first that its sabotage
changed the build. `tests/test_station_calendars.py` now expects the list
page and the footer link wherever a calendar shows, and the new privacy
sentences. `tests/test_site.py` builds with an empty poster list too.

**Not checked.**

- The listings themselves: the ids are the owner's, and Etsy was not
  asked. The year, 2027, and the link text "2027 Tide Poster: Place" are
  this change's, written to match the calendars'; they were not read from
  the listings, whose own titles may differ.
- `make site-checks` (axe-core and pa11y) was not run on the machine this
  was written on; it runs on the pull request.

**Reversible.** Yes: empty `posters.json` and the next build has no poster
sentence; empty both lists and it has no list page and no footer link. To
remove the code, drop `posters.py`, `printables.py`, their three copy
files and two templates, the two includes, the footer link, the sample
lines and the checks, and put back `calendars.notice` and the two privacy
sentences in `copy/calendar_link.json` from 0035.

**For the app:** nothing changes.

Update, 2026-11-13 (night): with the twelve calendars added to 0035's list,
the page lists 40 towns and 46 listings. The page and its checks are
unchanged.

## 0038: Station pages: the next tide, and the chart above the table (owner, 2026-11-13)

On 2026-11-13 the owner approved the phase 2 layout proposal "all as
recommended". This is its first part, 2a, the station page (Q1, Q2, Q3 and
Q7, option A each). It changes the layout of the first screen and adds one
line. It does not change the look from PR #19, the H1, the two questions,
the king-tide callout's place or words, or the printable sentences' words,
place or count.

**The answer box** (amends 0032's first screen). The H1 and the two
questions keep 0032's exact wording, set smaller, in one box with both
days. Each listed time is wrapped (`span.times`, `span.ev`) so the script
can mark it; the text around the times, "Sunday, Nov 1: " and the
heights, is unchanged.

**The next-tide line** (amends 0002's role for the page's script). At
build time, `p#next` opens the answer box with the first day's highs and
lows in order, by date: "Friday, Nov 13, in order: high 2:25 AM, low
5:30 AM, high 11:34 AM, low 7:35 PM." A day with neither says "Friday,
Nov 13: no high or low tide predicted." It names the date, not "today"
(0032's rule for descriptions), so it is true whenever it is read; it is
what crawlers and readers without the script get (`Day.in_order`).

The script that already labels the days (0002) now also takes the first
high or low after the reader's clock from the times the build wrote in the
day tables, and replaces the line: "Next low tide: 7:35 PM (0.0 ft), in
2 h 5 min. The predicted tide is falling until then." After the day's last
tide it names tomorrow's first: "Next high tide: 3:29 AM tomorrow (3.7 ft),
in 7 h 29 min. The predicted tide is rising until then." It marks each time
in the answer that has passed (dimmed, with "passed: " for screen readers).
It never computes a tide, a height or a curve: the times, heights and
direction all come from the build's own table, and "in" is the clock's
difference to that time, so it is right across a daylight saving change.
When the next tide on the page is not the station's today or tomorrow, when
every tide on it has passed, or when the zone is unknown to the browser,
the build's line stays. The wording is the proposal's Appendix A; on
2026-11-13 the owner approved each line as written: the build sentence, the
absence sentence, the "tomorrow" form and the spoken "passed: ".

**The day cards.** The chart comes before the table in each day's card,
then the sun and moon line. From 60rem wide, the table and the sun and moon
sit beside the chart, and the two questions side by side. At 390×844 in
king-tide season, today's chart now starts about 1,065 px down Monterey's
page (the proposal measured 1,532 px before, on its mockup).

**King tides** (0015 unchanged). The callout keeps its place before day 1
and its words, with less padding and smaller type; its two links share a
line.

**The printable sentences** (0030, 0035, 0037 unchanged). A hairline and a
little space before the first of them, so they do not read as part of "The
rest of the week". No box, heading, icon or color.

**Header.** One row from 360 px wide; it wraps below that, as before.

**Weight.** Monterey's page grows by 3,514 bytes (1,090 gzip) and
`style.css` by 3,650 bytes (902 gzip). The largest station page in a
California build is 37,831 bytes, under check_site's 120,000.

**Checks.** `check_site.check_next`: every station page has exactly one
`p#next`, inside the answer box, and it is the first day's table's highs and
lows in order, written out in the check itself, or the absence sentence,
with no placeholder. `tests/test_next_tide.py` holds its negative controls
(the line removed, doubled, moved out of the box, reordered, a wrong time,
tomorrow's date, "Today", a placeholder, and a table that no longer
matches), each asserting first that its sabotage changed the page.
`tests/test_today.py` runs the shipped script under Node against the
built rows: before the first tide, between tides, at the minute of a tide,
after today's last (the "tomorrow" form), after every tide, a missed build
and a clock behind the build, an unknown zone, and the fall-back day in New
York. `test_station_title_shape_and_lead_answer` passes as written and
asserts the line.

**Not changed.** A high or low that rounds to midnight stays in the day
the table already lists it under, so the line can end "low 12:00 AM." as
the answer and the table do (for example station 9414811 on 2026-11-13).

**Reversible.** Yes: drop `p#next` and the wrappers, the script's
`tidehoursNext`, `check_next`, the new style rules, and put the chart back
after the table.

**For the app:** nothing changes.

## 0039: Hubs in coast order, with the day's tides on region pages (owner, 2026-11-14)

Phase 2b of the layout proposal the owner approved on 2026-11-13 (Q4 and
Q5, option A each). On 2026-11-14 she approved the California order and
every line of wording below as written. The look from PR #19 is unchanged.

**State pages: coast order** (`copy/region_order.json`, `site.coast_order`).
A state listed in the file has its regions in the file's order, and the
file must name each of its regions exactly once; the build stops on an
unknown or missing region, a region listed twice, a state the site does not
name, or the "other" group. Only California is listed, in the owner's
order: down the north coast, into San Francisco Bay and the Delta rivers,
then back out to the coast and south (Outer Coast, San Francisco; Humboldt
Bay; San Francisco Bay; San Pablo Bay; Carquinez Strait; Suisun Bay;
Sacramento River; San Joaquin River; Mokelumne River; Outer Coast, Port
San Luis; Monterey Bay; Santa Barbara Channel; Santa Barbara Islands; San
Pedro Channel; Southern California). Every other state's regions go north
to south by the average latitude of their stations; on Florida's page, that
interleaves the Atlantic and Gulf regions. The "other" group keeps its
alphabetical order. Stations without a region stay last.

- The lead ends ", north to south." when a state has more than one region.
- With more than three regions, a collapsed "Jump to a region, north to
  south (15)" lists them, linking to each region's section.
- Each region heading gains its count, "20 places" or "1 place".
- A find box, "Find a place in California", filters the names already on
  the page as you type: "1 place matches “half moon”.", "12 places match
  “bay”.", or "No place on this page matches “xyz”. Try the town, beach or
  bay name." It ignores case, accents and the ʻokina, and also matches a
  station's searched name from `copy/place_names.json` ("Maui"). The
  page's script adds the box, so a page read without the script has none.
  No request is made, and nothing typed leaves the page. The "other"
  group's page has no box, jump list or lead change.

**Region pages: the day's highs and lows.** Under the lead, "High and low
tides, Friday, November 13, 2026 (Pacific Time; heights on each place's
page)", then each place's row adds its times for that day, computed at
build time from the same `Day` as its station page: "High 2:25 AM, 11:34 AM
Low 5:30 AM, 7:35 PM". Times only, so no height appears without its datum.
A day without either says "no high or low tide predicted", and one without
a high or a low says "no high tide" or "no low tide", as the descriptions
do (0032). The 11 regions whose stations span two zones (on the Florida
panhandle, in Alaska and one in Texas) say "(local time at each place; heights on
each place's page)". A region whose stations have different dates gets no
heading and no times, as before; at 11:20 UTC no region does (0002). The
rows stay alphabetical.

**Amends 0028:** region pages now change every day, so their sitemap
`lastmod` moves daily and IndexNow announces the 304 indexable region pages
each day, about 3,560 URLs a day against its 10,000 limit. Whether that
changes how often search engines crawl them was not studied.

**Weight,** on a full build pinned to 2026-11-13: the largest region page,
Florida Keys, goes from 24,300 to 60,352 bytes (3,779 to 7,048 gzip). The
California state page goes from 19,186 to 23,003 bytes, and `style.css`
grows by 2,475 bytes (503 gzip). The largest page of the build is still
the Spanish king-tide page, at 96,591 bytes, under 120,000.

**Checks.** `check_site.check_hubs`: each state page lists every region once,
in `coast_order`'s order, with the stations without a region last; each
region page lists exactly its stations; and under a dated heading each
row's times are its station page's first-day highs and lows, written out in
the check itself. The station page's date must be the heading's. Without a
heading, no row shows times. `tests/test_hubs.py`: the owner's order, the
order file's refusals, north to south for the rest, the built pages' words,
the find script under Node (matches, no match, an empty box, case and
spaces, accents and the ʻokina, a searched name), and eight negative
controls for `check_hubs`. `tests/test_indexnow.py` now expects a new day to
change the region pages as well as the station pages, and nothing else.

**Reversible.** Yes: drop the order file, `coast_order`, the hub heading and
times, the find script and their styles and checks, and the state and
region pages are as before.

**For the app:** nothing changes.

## 0040: A find box over a static list, and the home page by coast (owner, 2026-11-14)

Phase 2c of the layout proposal the owner approved on 2026-11-13 (Q6, option
A). On 2026-11-14 she approved every line of wording below as written.

**States by coast** (`site.COAST_GROUPS`). Under "Choose a state or
territory", the home page groups the states: "Pacific coast, north to
south" (Washington, Oregon, California); "Alaska"; "Hawaii and the Pacific
islands" (Hawaii, Guam, the Northern Mariana Islands, American Samoa, the
U.S. Minor Outlying Islands); "Atlantic coast, north to south" (Maine to
Florida, with Pennsylvania and the District of Columbia where their rivers
meet the coast); "Gulf Coast, east to west" (Florida to Texas); "Caribbean"
(Puerto Rico, the U.S. Virgin Islands); and "Other" (stations without a
state). Florida has a coast in two groups and is listed in both, with the
same link. A state in no group stops the build, so none can fall off the
page. Each group is an `h3` naming its `ul.states`.

**Find a tide station** (amends 0034's "the site has no search": the home
page now filters a static list, but there is still no search page and no
`SearchAction`). The build
writes `/places.json`: one row per station page, `[id, display name]`,
with the searched-for name from `copy/place_names.json` as a third item for
the five stations that have one. It is 132,997 bytes, 40,283 gzip (CloudFront
compresses it, `infra/site.yaml`), and is not in the sitemap. The home
page's script puts a box, "Find a tide station by town, beach or bay", under
the lead. It fetches `/places.json` from this site the first time the box
is focused, never before, and filters it in the browser. Nothing typed
leaves the page. From two letters on, it lists at most 12 stations, each
linking to its page, and says "1 station matches.", "2 stations match.",
"The first 12 of 40 stations that match. Type more to narrow them.", or
"No station name matches “xyz”. Try a nearby town, or pick a state below."
If the list does not load: "The list of places did not load. The states
below list every station." It ignores case, accents and the ʻokina, as the
state pages' box does (0039). Without the script, or without `fetch`, there
is no box, and the states list every station as before.

**Weight.** The home page goes from 7,195 to 10,985 bytes (2,097 to 3,497
gzip) with the groups and the script; the list costs nothing until someone
uses the box.

**Checks.** `check_site.check_places`: `/places.json` is exactly the
station pages of the build, in id order, each with its display name and
its searched name when it has one; and the home page shows
`site.coast_groups` for the states of the build. `tests/test_home_find.py`:
every state in a group and Florida in two, the built home page, the list,
the find script under Node with the full catalog's list (two matches for
"half moon", "Maui" by its searched name, nothing for one letter, the
first 12 for "bay", no match, a list that fails to load, and one fetch,
on first use), and seven negative controls for `check_places`.
`test_jsonld` still refuses `SearchAction`.

**Reversible.** Yes: drop the groups, the anchor, the script, the list and
their styles and checks, and the home page is as before.

## 0041: A tide gifts page lists every Tide Hours product, by kind and by town (2026-11-14)

The owner asked for more
Google visitors to the Tide Hours products for holiday gift searches ("tide
chart gift", "Bar Harbor tide calendar 2027", "tide art print"). The site
already had `tide-calendars/` (0037), which lists the printable calendars
and posters by state for a reader who wants a town's calendar. This page is
for a reader who wants a gift: every product the site can link to, grouped
by kind, and by town within a kind. The owner approved the page and its
wording on 2026-11-14 with two changes, both below: the Maine Coast
hardcover waits until she has checked her author copy, and the products
listed that day (two more tide rings prints and the winter solstice print)
are added. The listings were not fetched for this change.

**Nothing forbids it.** No decision here freezes the site or rules out a
new page. 0029 kept shop links off station, state and region pages, and
0037 added one footer link to a page of this site on the owner's request;
this change adds a second footer link of the same kind and no link to a
shop from any page that did not have one, apart from the new page.

**The page.** `tide-gifts/` (the address follows `tide-calendars/` and
`king-tides/`), from `gifts.py`, `copy/gifts_page.json` and
`templates/gifts.html.jinja`. Title and heading "Tide chart gifts and tide
art prints" ("Tide chart gifts" when the build has no art print). A lead
that says each one is made by Tide Hours and that the tide gifts are "art,
not for navigation, and not a NOAA product", a sentence on how the page is
listed, then one section per kind, in this order, each with a sentence on
what the thing is:

- **Custom tide chart prints:** the print shop's made-to-order print
  (0029), with one link to the shop's own address. Shown only when
  `PRINT_SHOP_URL` is set, as it is on the live site. It links to the shop
  and not to a listing, because the listing ids of the custom print and its
  occasion versions are not marked live in the product notes the owner
  keeps for each listing.
- **Winter solstice print:** the made-to-order daylight print for the
  solstice of December 21, 2026, one line with its listing. Its sentence is
  the wording already approved on its live Etsy listing, with only its first
  two sentences of the second paragraph joined ("Made to order as a digital
  file" and the places it works): "The winter solstice in your city,
  December 21, 2026: the shortest day of the year, and the first bar on the
  page. After it come the 364 days to December 20, 2027, one thin bar for
  each, from midnight at the top to midnight at the bottom, so you can
  watch the light come back through spring to the long days of June and
  out again. Made to order as a digital file, for any city in the 50
  states, Puerto Rico or the U.S. Virgin Islands; not interior or northern
  Alaska, Guam, the Northern Mariana Islands or American Samoa." It shows
  sun, not tide, so the page's tide wording does not describe it.
- **Tide rings art prints, year-of-tides posters, printable calendars and
  tide blanket patterns:** one line per town, alphabetical: the town's
  name linked to its station page, the state, and the listing linked by
  its title.
- **Printed tide tables:** each book, linked by its cover title, with the
  towns it covers, each linked to its station page.
- **Moon phase calendars:** one line each, no town. The sentence says they
  show the moon, not the tide.

**The lists.** The calendars and posters are exactly the ones the station
pages of this build link to (0035, 0037); this page adds no id to them. The
other products are in `copy/gifts.json`, a list of entries of five kinds
(`daylight`, `rings`, `blanket`, `moon`, `book`) with the Etsy listing id or
ASIN, the year, a title in a fixed shape ("2026 Winter Solstice Print: The
Light Returns", "2027 Tide Rings: Bar Harbor", "2027 Tide Blanket Pattern:
Half Moon Bay", "2027 Moon Phase Poster: US Time Zones", "2027 Tide
Tables: Maine Coast"), the station for a town-bound entry, the format and
the towns for a book, **`live`, the date its listing was marked live**,
and, optionally, **`until`, the first day it no longer shows**, read in
Pacific time (the shop's own). A solstice print must carry `until`, and a
list may hold at most one, since its sentence names its dates. An entry without a `live` date, or with anything but a date
there ("draft", "LISTED", an empty string), stops the build, as do a slug,
a whole address, a claim word, a price, an unknown kind or key, a listing
listed twice or also in the calendar or poster list, and a station the
catalog does not have, an `until` that is not a date or not after `live`,
and a second solstice print. As committed it holds the ten entries marked
live in the owner's product notes on 2026-11-13 and 2026-11-14: the winter
solstice print (`until` 2026-12-22, the day the owner delists it), tide
rings for Bar Harbor, Half Moon Bay, Monterey and San Francisco, tide
blanket patterns for Bar Harbor and Half Moon Bay, and the three moon phase
calendars. The hardcover "2027 Tide Tables: Maine Coast" (ASIN B0HRP6Z64Q,
marked live) is left out until the owner has checked her author copy, so
the "Printed tide tables" section, the privacy page's "Book links" section
and Amazon's name on the terms page do not render; adding its entry back
brings all three. `booklets.json` (0030) is still empty. `--gifts FILE` on the build and
on `check_site.py` names another list; it is for tests.

**The links.** Exactly `https://www.etsy.com/listing/ID` or
`https://www.amazon.com/dp/ASIN`, `rel="noopener"`, as on the station pages
(0030, 0035): no slug, query string, Associates tag (even with 0016's
switch on), tracking parameter or click event. No price, sale, discount,
image, rating or claim anywhere on the page. The Etsy shop's 20% sale
(November 20 to December 2) is left out: the site states no prices, and the
daily build at 11:20 UTC would keep a sale sentence up for hours after the
sale ends in Pacific time, or longer if a publish failed.

**Structured data.** None added. The page carries the `dateModified` every
sitemap page has (0034) and no JSON-LD: there is nothing on it that
schema.org can describe accurately without `Product` and `Offer`, which
0034 rules out, and a `Book` or `ItemList` of other sites' pages would be
markup for things this site does not hold. Etsy and Amazon are never in
its JSON-LD.

**When it exists.** Only while an entry of `gifts.json` shows: its year is
not over by the build's date (UTC), its `until`, if any, has not come by
the build's date in Pacific time, and a town-bound one's station has a page
in the build. The solstice print leaves with the first build on or after
midnight, December 22, 2026, Pacific: the daily build of December 22 at
11:20 UTC. The December 21 build stays up until then, so the page lists it
for about three hours after midnight Pacific on December 22. The calendars, posters and custom print alone make no
page, because `tide-calendars/` and the print shop's own link already list
them. So the build of January 1, 2028 has no gifts page and no footer link
to one, with nobody editing a file; the About and king-tide pages keep the
shop link.

**Links to it.** The footer of every English page, the 404 page included,
links to it after "Tide calendars and posters": "Tide gifts". That is the
link from the home page and from every town's station page. The Spanish
king-tide page's footer does not (0029, 0037). No page body links to it,
and it is not in `llms.txt`, which says nothing about Etsy or Amazon.

**Indexing.** In the sitemap and `lastmod.json`. The footer link changes
the HTML of every English page once, so the first build with it gives every
page that build's `lastmod` and IndexNow announces every page once (0011,
0028), as 0037's footer link did.

**Privacy and terms.** The privacy page's Etsy section (`/privacy/#shop`)
names the new page while it links to Etsy (`gifts.shop_notice`); every
earlier case is unchanged. As published: "The About and king tides pages,
the tide calendars and posters page, the tide gifts page, and the station
pages of towns with a printable calendar or poster, link to the Tide Hours
shop on Etsy. This site sends nothing to Etsy. The link takes you to Etsy,
where Etsy's own privacy policy applies." While the page lists a book (none
as committed), the
Amazon section (`/privacy/#booklets`) reads, under "Book links": "The tide
gifts page links to printed tide tables that Tide Hours publishes and sells
on Amazon. They are plain links, not affiliate links, and this site sends
nothing to Amazon. A link takes you to Amazon, where Amazon's own privacy
notice applies." (with "Some station pages, and the tide gifts page, link
to ..." when a station booklet also shows). The terms page then names
Amazon and Etsy among the trademarks. The "no ads" sentence is unchanged.

**Checked.** `check_site.py` works out from the build what the page must
list (`gift_listing`: the calendars and posters due on the station pages,
the live entries whose year is not over on the date the station pages say
the build was made and whose `until` has not come on the date a Pacific
station page shows, and the custom print when the shop address is set),
and `check_gifts` fails the build if the page is missing or present when it
should not be; if its title, heading, two paragraphs, section headings or
section sentences differ; if its lines or their links differ or are out of
order; **if it links to any Etsy listing or Amazon book that it does not
list, which covers one not marked live**, or to one twice; if a link's rel
is not `noopener` or it has a click event; if Etsy or Amazon is in its
JSON-LD; if it names a price, sale, discount or claim; or if an English
page does not link to it exactly once or the Spanish page links to it.
0016's and 0029's rules leave this page to `check_gifts`, and still hold
for every other page; the privacy and terms pages may name Amazon and Etsy
in words while the page links to them, never with a link. The privacy
page's Amazon section must be exactly `gifts.book_notice`'s.

**Accessibility sample.** `scripts/site_sample.py` adds the page when the
build has it. It is a heading, two paragraphs, and a heading, a sentence
and a list for each kind, styled as `ul.printables`; no new CSS and no
script.

**Tests.** `tests/test_gifts.py`: the committed list is exactly the ten
listings marked live, with no book; 27 bad entries are refused, six of them
a missing or non-date `live` and six about `until` or the solstice print; the
published page word for word, its 57 outbound links (40 calendars, 6
posters, 10 gifts and the shop), towns in order; with no book entry, no
file of the published build links to or names Amazon; the solstice print
shown at 23:59 on December 21 Pacific and gone at midnight, and check_site
failing a page that still lists it past its `until`; no price, sale, rating
or product markup; the footer of every English page and not the Spanish
one; the sitemap and not `llms.txt`; the privacy and terms pages; the shop
off; a one-town book; a moon calendar alone; the 2028
build; an empty list, and calendars, posters and the custom print with no
gift, both without a page; the affiliate switch on; the accessibility sample;
and 25 negative controls, three of them links to a listing or book that is
not marked live. `tests/conftest.py` points `gifts.load()` with no path at
an empty list for the whole test session, so the other test modules stay
about what they test; `test_gifts.py` names the committed list wherever it
means the site as published.

**Not checked.** The listings themselves: their ids are from the owner's
notes, and Etsy and Amazon were not asked. The link titles are this
change's, written to match the calendars' and posters'; the listings' own
titles are longer. The Maine hardcover waits for the owner's author copy.

**Reversible.** Yes: empty `gifts.json` and the next build has no page and
no footer link. To remove the code, drop `gifts.py`,
its two copy files and template, the footer link, the privacy and terms
cases in `gifts.shop_notice` and `gifts.book_notice`, the sample line,
`check_gifts` and `tests/conftest.py`.

**For the app:** nothing changes.
