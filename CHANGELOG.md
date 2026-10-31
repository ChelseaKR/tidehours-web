# Changelog

## 0.1.0 (unreleased)

- First version: a page per NOAA tide prediction station (3,256) with today's
  and tomorrow's highs, lows and tide curve; state and region pages; the
  2026-27 West Coast king-tide pages in English and Spanish, computed rather
  than copied.
- The Tide Hours app's prediction engine, ported to Python, checked in
  `make verify` against NOAA's published predictions at 81 stations.
- Removes NOAA-style stands that the app's engine shows (DECISIONS 0004).
- GA4 hook, off by default. Sitemap, robots.txt, canonical URLs.
