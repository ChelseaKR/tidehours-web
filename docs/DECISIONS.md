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
only when the ID is set, and says "collects nothing" when it is not. No
property exists yet; creating one is an owner step.

## 0008: CI on the Mac runner; hosting is the owner's

`make verify` is the gate, run by `ci` on the runner chosen by the
`CI_RUNS_ON` repository variable (the portfolio's self-hosted Mac runners;
hosted when unset). The accessibility checks (axe-core and pa11y-ci over a
sample of pages, `tools/site-checks/run.sh`) run locally with `make
site-checks`; in CI they need Chrome, which the arm64 Mac runners do not
have, so `site-checks` runs on pull requests only, on a hosted runner, and
on a sample.

`publish` builds the whole site daily at 11:20 UTC and runs the build checks.
It deploys nothing: hosting, the domain, DNS and the AWS member account are
owner steps (README). Until then a scheduled run is inert unless the
repository variable `PUBLISH_ENABLED` is `true`.
