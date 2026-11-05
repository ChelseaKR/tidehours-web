"""Date, time and height formatting for the king-tide pages, in English and
Spanish: a port of personal-site's src/lib/kingTidesFormat.ts, so the
moved page reads the same."""

from __future__ import annotations

from typing import Any


def fill(template: str, **values: str) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


def _parts(date: str) -> tuple[int, int, int]:
    y, m, d = (int(x) for x in date.split("-"))
    return y, m, d


def fmt_date(date: str, lang: str, c: dict[str, Any]) -> str:
    """ "Nov 24, 2026" / "24 nov 2026"."""
    y, m, d = _parts(date)
    mon = c["months"][m - 1]
    return f"{d} {mon} {y}" if lang == "es" else f"{mon} {d}, {y}"


def fmt_long_date(date: str, lang: str, c: dict[str, Any]) -> str:
    y, m, d = _parts(date)
    mon = c["monthsLong"][m - 1]
    return f"{d} de {mon} de {y}" if lang == "es" else f"{mon} {d}, {y}"


def fmt_range(first: str, last: str, lang: str, c: dict[str, Any]) -> str:
    if first == last:
        return fmt_date(first, lang, c)
    ay, am, ad = _parts(first)
    by, bm, bd = _parts(last)
    if ay != by:
        return f"{fmt_date(first, lang, c)}–{fmt_date(last, lang, c)}"
    mons = c["months"]
    if lang == "es":
        if am == bm:
            return f"{ad}–{bd} {mons[am - 1]} {ay}"
        return f"{ad} {mons[am - 1]}–{bd} {mons[bm - 1]} {ay}"
    if am == bm:
        return f"{mons[am - 1]} {ad}–{bd}, {ay}"
    return f"{mons[am - 1]} {ad}–{mons[bm - 1]} {bd}, {ay}"


def fmt_time(time: str, lang: str) -> str:
    """ "10:49 AM" in English, "10:49" in Spanish (24-hour)."""
    h, minute = (int(x) for x in time.split(":"))
    if lang == "es":
        return f"{h}:{minute:02d}"
    return f"{h % 12 or 12}:{minute:02d} {'AM' if h < 12 else 'PM'}"


def fmt_feet(ft: float, lang: str, c: dict[str, Any], signed: bool = False) -> str:
    v = round(ft, 1)
    v = 0.0 if v == 0 else v
    n = f"{v:.1f}".replace("-", "−")
    if lang == "es":
        n = n.replace(".", ",")
    return f"{'+' if signed and v >= 0 else ''}{n} {c['ft']}"


def fmt_months(months: list[tuple[int, int]], lang: str, c: dict[str, Any]) -> str:
    """ "November 2026", "November and December 2026", "December 2026 and
    January 2027" / "noviembre de 2026", "noviembre y diciembre de 2026"."""
    if not months:
        raise ValueError("fmt_months: no months")
    names = c["monthsLong"]
    conj = " y " if lang == "es" else " and "
    years: dict[int, list[str]] = {}
    for y, m in sorted(months):
        years.setdefault(y, []).append(names[m - 1])
    groups = []
    for y, ms in years.items():
        joined = ms[0] if len(ms) == 1 else ", ".join(ms[:-1]) + conj + ms[-1]
        groups.append(f"{joined} de {y}" if lang == "es" else f"{joined} {y}")
    return conj.join(groups)
