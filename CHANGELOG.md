# Changelog

## 0.1.0 (unreleased)

- Subordinate station pages are indexed and in the sitemap: 2,022 of the
  2,024, which takes the sitemap from 1,577 to 3,599 URLs. Each page now
  says which reference station NOAA predicts it from, how far away, and
  NOAA's published time and height corrections. The 2 whose corrections
  leave every time and high tide as the reference's (Cabrillo Beach and
  Great Diamond Island) stay noindex with a canonical link to the reference
  station's page. `check_site.py` checks the noindex and the canonical of
  every station page (DECISIONS 0033, superseding 0013's noindex).
- A high or low in the first 30 minutes of a GMT year (7:00 to 7:30 PM
  Eastern, 4:00 to 4:30 PM Pacific on New Year's Eve) now matches NOAA's
  published one. NOAA finds it with the old year's lunar-node constants; the
  engine used the new year's, which put Bar Harbor's 2028-01-01 00:09 GMT
  low at 00:07 and 0.465 ft against NOAA's 0.377 ft. Measured at 18 stations
  around the 2027 and 2028 new years; the tide curve is unchanged, as NOAA's
  is (DECISIONS 0031).
- A station's page can link to that station's printed tide-table booklet
  on Amazon. `src/tidehours/copy/booklets.json` lists the booklets on sale
  (station id, ASIN, year, title) and ships empty, which leaves the build
  byte for byte as it was. A listed station's page carries one sentence with
  one plain link, `https://www.amazon.com/dp/ASIN`, with no tag even when
  the affiliate switch is on, until the booklet's year is over; the privacy
  page says where it goes and the terms page names Amazon. `check_site.py`
  allows that one link on that one page and nothing else (DECISIONS 0030).
- A link to the Tide Hours print shop on Etsy, off by default. With the
  repository variable `PRINT_SHOP_URL` set to the shop's address, the About
  page and the English king-tide page each carry one sentence with one plain
  link, the privacy page says where it goes, and the terms page names Etsy.
  Unset, the build has no trace of it. `check_site.py --print-shop-url`
  fails the build if the link is missing, repeated, on another page or not
  the configured address (DECISIONS 0029).
- King-tide calendars open with the answer: "When are the king tides in
  Washington?", one line per month with the days and peak days. Their titles
  and descriptions name the places people search (Seattle, Puget Sound, the
  Oregon coast, San Francisco, San Diego). The king-tide pages define "king
  tide" as a popular, non-scientific name and link the three calendars
  under the lead, as does the home page. The sitemap's `lastmod` is now the
  date a page last changed, not the build date (DECISIONS 0028).
- The king-tide page's title names Washington, Oregon and California in
  full, and its description leads with the next dates and names Seattle,
  Puget Sound and the Oregon coast, the words people search with
  (DECISIONS 0025).
- Winter king-tide calendars by month for Washington, Oregon and California
  (`/king-tides/washington/`, `/king-tides/oregon/`,
  `/king-tides/california/`): each place's runs of predicted king tides from
  November 2026 to February 2027, with dates, Pacific times and heights above
  MLLW and MHHW. Linked from the king-tide pages, the three state pages and
  king-tide and nearby station pages (DECISIONS 0024).
- Region pages that shared a label now say which part they are, from
  NOAA's coordinates: "Outer Coast (north)" and "(south)" in Maine and South
  Carolina, "Gulf Coast (north)" and "(south)" in Florida and "Delaware River
  (north)" and "(south)" in New Jersey. Five St. John, Virgin Islands station
  names say "St. John", not "St. Johns". No URL changes (DECISIONS 0023).
- Station names are corrected for display: 40 NOAA misspellings backed by
  USGS GNIS names (Chickahominy, Sergius Narrows, Frederiksted), Spanish and
  Hawaiian diacritics (Mayagüez, Nāwiliwili), casing, punctuation and "St."
  slips, and four pairs of stations that shared a title. Station titles drop
  " | Tide Hours", then "today", when needed to fit in 60 characters. Region
  labels read as names ("East Coast", not "FLORIDA, East Coast"; "Hawaiian
  Islands"). No URL changes (DECISIONS 0020).
- Stations NOAA lists without a state are filed under a state: by a hand
  map for island stations (GU, AS, and new U.S. Minor Outlying Islands and
  Northern Mariana Islands pages), by the state their NOAA name ends in, or
  by their reference station's state, unless a border check rules it out.
  Tanapag Harbor, Saipan moves from GU to MP, and Apia (independent Samoa)
  leaves American Samoa and takes Samoa's time zone. Chelsea (Arthur Kill)
  is filed under New York. Ten western Aleutian stations now filed under
  Alaska use America/Adak, so their summer times are no longer an hour early. 186 stations change
  state, including Apra Harbor, Guam, Cape Hatteras and Key Largo; 11 stay on
  "Stations without a state". Names no longer repeat their state ("Apra
  Harbor, Guam", not "Apra Harbor, Guam, GU"). Old region pages send visitors
  to the new ones (DECISIONS 0018).
- Region pages that list only one or two stations (66 of 370, about 130
  words each, the same list their state page shows) carry noindex and are
  left out of the sitemap and lastmod.json. They keep their URLs and links;
  station and state pages are unchanged (DECISIONS 0022).
- The 12 U.S. Virgin Islands stations that NOAA codes PR (Cruz Bay, Magens
  Bay, Salt River Bay and others) are listed under the U.S. Virgin Islands,
  in America/St_Thomas, instead of on the Puerto Rico page. Station URLs are
  unchanged; the three `/states/pr/st-*-island/` region pages now send visitors
  to the matching `/states/vi/` region pages, which the stations join
  (DECISIONS 0017).
- Station pages label "Today" and "Tomorrow" from the station's own date
  when the page is read, not when it was built. Before dawn on the East
  Coast, and for most of the day in Guam, the page used to call yesterday
  "Today". Days that have passed are hidden, and when today is not on the
  page at all it says so in words. Without JavaScript the headings are
  plain dates.
- Amazon affiliate links for the English king-tide page, off by default:
  four tagged category searches after the method section with Amazon's
  disclosure, and matching privacy, terms and about lines, all only when
  `--amazon-tag` (repo variable `AMAZON_ASSOCIATE_TAG`) is set (DECISIONS 0016).
- The king-tide pages lead with the runs coming up: their title names the
  month and year ("King tides November 2026"), and the first section gives
  the dates by state and each place's highest tide with its local time and
  height, in English and Spanish. Station pages show their own run near the
  top, and WA, OR and CA stations within 15 miles of a king-tide station
  show the nearest one's run, labeled as that station's. Region, state and
  home pages link to the dates. All of it appears only while a run starts
  within 30 days or is under way, and all of it is computed (DECISIONS 0015).
- Each harmonic station's page states its type of tide (semidiurnal; mixed,
  mainly semidiurnal; mixed, mainly diurnal; or diurnal) with one plain
  sentence on what it means. It is computed from the station's own NOAA
  constants with the form factor (K1 + O1) / (M2 + S2) and NOAA's glossary
  thresholds: 1,230 of 1,232 harmonic stations. The two whose constants list
  no S2, and the subordinate stations, show none (DECISIONS 0014).
- Search engines are asked to index the 1,232 harmonic station pages and the
  hub pages, not yet the 2,024 subordinate station pages, which are near
  copies of their reference station's page. Those keep their URLs and links
  but carry `noindex,follow` and are left out of the sitemap and IndexNow.
  Reference station pages list the stations predicted from them, with the
  time corrections, and NOAA names in capitals ("SAN FRANCISCO") are shown
  as place names (DECISIONS 0013).
- A plain-language terms of use page at /terms/ (English, like the privacy
  and about pages), linked from every page's footer next to Privacy, with
  the link label in Spanish on the Spanish king-tide page. It names who runs
  the site, says in bold that the predictions are not for navigation, says
  they can be wrong or late, and sets California law. Not reviewed by an
  attorney.
- After each deploy, the pages whose HTML changed are announced to IndexNow
  (Bing and the other participating engines), so they are crawled sooner.
  The build writes `lastmod.json`, a SHA-256 per page, to compare with the
  live one; a failed announcement only logs a notice (DECISIONS 0011).
- The deploy role accepts GitHub's immutable OIDC subject for main, which
  this repository's tokens use (DECISIONS 0012).
- The daily build runs on a hosted runner, because the Mac runner is asleep
  at 4:20 AM Pacific and missed two days (DECISIONS 0010).
- First version: a page per NOAA tide prediction station (3,256) with today's
  and tomorrow's highs, lows and tide curve; state and region pages; the
  2026-27 West Coast king-tide pages in English and Spanish, computed rather
  than copied.
- The Tide Hours app's prediction engine, ported to Python, checked in
  `make verify` against NOAA's published predictions at 81 stations.
- Removes NOAA-style stands that the app's engine shows (DECISIONS 0004).
- GA4 hook, off by default. Sitemap, robots.txt, canonical URLs.
- Hosting as code (`infra/site.yaml`: S3, CloudFront, ACM, Route 53, the
  OIDC deploy role) and a deploy job in `publish.yml` (DECISIONS 0009).
