# Changelog

## 0.1.0 (unreleased)

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
