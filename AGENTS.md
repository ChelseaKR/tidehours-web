# AGENTS.md: tidehours-web

Follow /Users/chelsea/portfolio/AGENTS.md first. In this repository:

- **Private.** Do not change the repository's visibility.
- **Work on branches** in a git worktree; `main` takes pull requests only.
  Never push to `main` directly (the initial scaffold was the one exception).
- **The gate is `make verify`.** Run it before every push and never bypass
  it. `make site-checks` (accessibility) also runs on pull requests.
- **No DNS, domain or AWS changes** from an agent unless the owner asks.
  Hosting is `infra/site.yaml` (infra/README.md); the daily deploy is
  `publish.yml`. Never put AWS credentials on the shared Mac runner.
- **Never weaken the NOAA accuracy tests** (`tests/test_golden.py`). If the
  engine changes and a divergence appears, measure it and record it in
  `KNOWN_DIVERGENCES` with what it is, and in docs/DECISIONS.md.
- **Keep the engine in step with the app** (ChelseaKR/tide-hours TideCore).
  A change to the method belongs in both, or in DECISIONS as a difference.
- **Data is committed and hashed.** Change `src/tidehours/data/` only with
  `scripts/refresh_data.py`, and update the SHA-256 in docs/DATA.md.
- **Every page must say:** predictions, not observations; not for
  navigation; not a NOAA product; NOAA CO-OPS credited; the app "coming soon"
  until approved. `scripts/check_site.py` enforces it.
- **Absence never renders as a value.** A day with no high or low says so;
  a missing curve draws nothing.
- American English everywhere. No AI attribution in commits or PR bodies;
  do not sign commits; stage explicit paths, never `git add -A`.
