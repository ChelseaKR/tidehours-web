# Decisions

Owner decisions are marked **(owner, date)**. Everything else is a build
decision made while carrying them out, and can be changed.

## 0001: A website for Tide Hours at tidehours.com (owner, 2026-10-31)

Tide Hours gets its own site at tidehours.com. The owner checked the
trademark search and is buying the domain. This repository is private until
the owner says otherwise.

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
