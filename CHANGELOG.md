# Changelog

## 0.1.0 (unreleased)

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
