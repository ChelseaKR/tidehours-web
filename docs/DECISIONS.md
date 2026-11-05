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
