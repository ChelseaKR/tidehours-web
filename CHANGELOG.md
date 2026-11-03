# Changelog

## 0.1.0 (unreleased)

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
