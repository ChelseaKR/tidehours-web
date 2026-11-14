# Tide Hours brand

The source of truth for how tidehours.com and the Tide Hours iPhone app look. The site's tokens are in `src/tidehours/templates/style.css`. `tests/test_design.py` recomputes the contrast ratios below from that file and fails under WCAG AA.

## The idea

A tide almanac printed on nautical-chart paper. Tide tables are an almanac form, and NOAA charts are where the datum, mean lower low water (MLLW), is zero. In light mode the site is cream chart paper with navy ink and the pale blue that charts use for shallow water. Dark mode is a navy "night chart".

What the design must keep, always:

- The disclaimer on every page: predictions, not observations; not for navigation; not a NOAA product.
- The datum next to every height and under every chart.
- Absence is said in words. A missing prediction is never drawn or written as a value.

## Palette

Text pairs need 4.5:1 or more and graphics need 3:1 or more, in both themes.

| Token | Role | Light | Dark |
|---|---|---|---|
| `--bg` | Page (chart paper / night chart) | #f7f3e8 | #0b1624 |
| `--surface` | A day's card | #fffdf7 | #101e30 |
| `--fg` | Ink | #14202e | #e8edf2 |
| `--muted` | Secondary text | #4b5561 | #a9b6c4 |
| `--brand` | Channel navy: headings, mark, card rule | #17365d | #9cc6ea |
| `--link` | Links | #1a4e85 | #9fcdf3 |
| `--panel` | Shallow-water tint: disclaimer band, callouts | #e2edf0 | #12253a |
| `--high` | High tide rows, dots and the curve | #1d5a8c | #8cc4f0 |
| `--low` | Low tide (tideflat) | #87470f | #f0b46a |
| `--buoy` | Red buoy: king tides only | #ad3420 | #ff8e75 |
| `--buoy-tint` | King-tide callout background | #f8e6df | #2a1915 |
| `--datum` | The dotted 0 ft line | #7d8792 | #6f8195 |
| `--foot-bg` / `--foot-fg` | Footer | #17365d / #f7f3e8 | #060e18 / #e8edf2 |

Contrast ratios, light / dark:

| Pair | Light | Dark |
|---|---|---|
| Ink on page | 14.85 | 15.44 |
| Muted on page | 6.83 | 8.81 |
| Link on page | 7.66 | 10.83 |
| Navy on page | 11.00 | 10.12 |
| High on page | 6.55 | 9.76 |
| Low on page | 6.45 | 9.91 |
| High on card | 7.14 | 9.01 |
| Low on card | 7.03 | 9.15 |
| Muted on panel | 6.35 | 7.53 |
| Link on panel | 7.12 | 9.25 |
| Link on warning | 7.45 | 9.25 |
| Link on king-tide tint | 7.03 | 10.01 |
| Footer text | 11.00 | 16.45 |
| Footer link | 11.00 | 11.53 |
| Curve on card (graphic) | 7.14 | 9.01 |
| Datum line on card (graphic) | 3.59 | 4.20 |
| Buoy on its tint (graphic) | 5.28 | 7.51 |

Red buoy is the one warm accent. Use it for king tides and nothing else.

## Type

- **Headings and the wordmark:** "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", "URW Palladio L", P052, Georgia, serif. It's a book serif, like the place names on a chart. Weight 600.
- **Body and interface:** system-ui, -apple-system, "Segoe UI", Roboto, sans-serif.
- **Numbers:** tabular and lining (`font-variant-numeric: tabular-nums lining-nums`), so times and heights line up in columns.
- No web fonts. The site makes no font requests.

## The mark

A clock ring with hands at about 10 past, over a tide wave. It's the same drawing as the app icon (ChelseaKR/tide-hours `design/render_icon.swift`).

- On the site, it's drawn through a CSS mask in the link's own color, so the header link's text stays exactly "Tide Hours".
- `/favicon.svg` is the mark in cream on a navy rounded square, with the wave in light blue.
- At small sizes, keep the ring, one hand and the wave. Drop the second hand first.

## Motifs

Each motif carries information, except the wave rule.

- **Wave rule.** A thin repeating wave under the header, in the panel-line blue. It's decorative and hidden from assistive technology. Never put it behind text.
- **Legend-box disclaimer.** The disclaimer band sits under the header on every page, in the shallow-water tint with an "i" drawn in CSS, like a chart's legend box. Its wording doesn't change, and it's never hidden or collapsed.
- **High and low triangles.** Every high row has a drawn up triangle and every low row a down triangle, in the high or low color. High and low differ by shape as well as color. The triangles are CSS shapes, not characters, so nothing extra is read aloud.
- **Dotted datum line.** On every chart, the 0 ft (MLLW) gridline is dotted and heavier. The key under the chart says "Heights in feet above mean lower low water (MLLW); the dotted line is 0 ft, the datum." When 0 ft is outside the drawing, the key names the datum and no line is drawn. A subordinate station's estimated curve stays dashed, which is different from the dotted datum line.
- **Day cards.** Each day is a card with a navy rule along the top and the date set in the serif.

## For the iPhone app

The app is held for Apple's review. Make these changes in the release after Apple's decision, not in a pending submission.

- **Mark:** the app icon already is the clock over the wave. Keep the favicon and the icon the same drawing.
- **Accent:** move AccentColor from #006190 / #1a73b3 to channel navy #17365d (light) and #9cc6ea (dark), with the high and low colors above.
- **Triangles:** use the same up and down triangles for high and low in the day list and widgets.
- **Datum key:** under the chart, use the same words: feet above MLLW, with the dotted line at 0 ft.
- **Serif station names:** set station names in New York (the iOS system serif, close to Iowan Old Style), with tabular numbers for times and heights.
- **Reading guide:** reuse the site's "How to read a tide page" text (/about/#reading) for the app's About screen.
- **Distinct from sister apps:** the app must look like its own product next to Trout Truck and Lake Notice (App Store 4.3(a)), so don't borrow their layouts.
