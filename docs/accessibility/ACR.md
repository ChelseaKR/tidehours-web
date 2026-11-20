# Tide Hours website: Accessibility Conformance Report

Accessibility Conformance Report (ACR), based on the VPAT® 2.5 Rev WCAG
edition.

VPAT® is a registered service mark of the Information Technology Industry
Council (ITI).

## Name of product and version

Tide Hours website, tidehours.com (repository `tidehours-web`, version
0.1.0, at branch `a11y/acr-2026-11` on top of main `ff8eb88`).

## Report date

2026-11-19

## Product description

A static website of free tide predictions for every NOAA tide prediction
station in the United States: a home page with a station finder, a page
per state and per NOAA region, a page per station (3,256) with today's and
tomorrow's highs and lows, a tide chart and a table, the West Coast
king-tide page in English and Spanish, a king-tide calendar for Washington,
Oregon and California, a list of printable calendars and posters, a tide
gifts page, and About, Privacy and Terms pages. The pages are built once a
day; a little JavaScript labels "Today" and "Tomorrow", says when a page's
day has passed, finds a station by name, and offers the analytics opt-out.

## Contact information

The contact given on the site's [terms page](https://tidehours.com/terms/).

## Notes

- **When this is true.** The remarks describe the site with the fixes on
  branch `a11y/acr-2026-11` (DECISIONS 0054). Until that branch is merged
  and deployed, the live site lacks those fixes; the remarks say which
  criterion each one affects.
- **What was evaluated.** One or more pages of every template, in light
  and dark mode, at 1280 px and 320 px wide, as listed under Evaluation
  methods. Station, state and region pages are built from one template
  each, with the same markup for every place.
- **What was not.** No person has yet used the site with a screen reader
  for this report. Where a criterion depends on how a screen reader speaks
  the page, the remark says what was verified (markup, the accessibility
  tree Chrome exposes, automated rules) and what still needs that
  walkthrough; the walkthrough is in the appendix. The printable PDFs sold
  in the Etsy shop are separate products and are not covered here.
- **Third-party pages.** Links lead to NOAA, the National Weather Service,
  the California Coastal Commission, Washington Sea Grant, the Oregon King
  Tides Project, Etsy, Amazon and Apple. Those pages are not covered.

## Evaluation methods used

- **axe-core 4.13** (through `@axe-core/puppeteer` 4.13.0 and Puppeteer 25.16), the tags
  `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa`, light and
  dark mode: the repository's `make site-checks` gate on its sample of
  pages, and a separate run on one page per template with the shop link
  and analytics turned on as in production.
- **pa11y-ci 5.0** (pa11y 10, axe runner, WCAG2AA) in the same gate.
- **Reflow and text spacing**, measured in headless Chrome: horizontal
  scrolling at 320 × 256 CSS px, and clipped or overflowing text after
  applying the WCAG 1.4.12 spacing (line height 1.5, letter spacing
  0.12 em, word spacing 0.16 em, paragraph spacing 2 em) at 320 and 1280 px.
- **Keyboard**, measured in headless Chrome: Tab through every focusable
  element of each page at 1280 × 900 and 375 × 667, recording the focus
  order, whether each element shows a focus outline, whether it is on
  screen, and whether anything covers it.
- **Contrast**, computed from the color tokens in
  `src/tidehours/templates/style.css` (WCAG 2 relative luminance), light
  and dark, and checked by axe on the rendered pages.
- **Code review** of every template in `src/tidehours/templates/` and of
  the page scripts.

Pages evaluated (one per template, and the variations that change the
markup): home; state (California; the stations without a state); region
(Monterey Bay; a split region); station (San Francisco, harmonic; a
subordinate station; Bar Harbor, with printable links; a station without a
state); king tides (English and Spanish); Washington king-tide calendar;
tide calendars and posters; tide gifts; About; Privacy; Terms; the
not-found page.

## Applicable standards and guidelines

| Standard / guideline | Included in report |
| --- | --- |
| Web Content Accessibility Guidelines 2.2 | Level A (Yes), Level AA (Yes), Level AAA (No) |

WCAG 2.2 includes every success criterion of WCAG 2.0 and 2.1 except 4.1.1
Parsing, which 2.2 removed, so this report covers 2.0 and 2.1 Level A and
AA as well. 4.1.1 is listed for readers who need a 2.0 or 2.1 answer.

## Terms

- **Supports**: the functionality of the product has at least one method
  that meets the criterion without known defects or meets with equivalent
  facilitation.
- **Partially Supports**: some functionality of the product does not meet
  the criterion.
- **Does Not Support**: the majority of product functionality does not
  meet the criterion.
- **Not Applicable**: the criterion is not relevant to the product.
- **Not Evaluated**: the product has not been evaluated against the
  criterion (used for Level AAA only).

## WCAG 2.2 report

"Verified" in a remark means measured or read for this report, on the
pages listed under Evaluation methods. "Screen reader: pending" means the
markup and Chrome's accessibility tree were checked but no person has yet
listened to it; see the appendix.

### Table 1: Success Criteria, Level A

| Criteria | Conformance Level | Remarks and Explanations |
| --- | --- | --- |
| 1.1.1 Non-text Content (Level A) | Supports | The site has no `<img>` elements. Each day's tide chart is hidden from assistive technology (`aria-hidden`), and its `<figcaption>` says the day's highs and lows in words, next to a table with every number. Chrome exposes the figure with the caption as its content (not as a separate name). The logo mark, the wave rule, the notice icon and the high and low triangles are CSS decoration with no text. Verified: code review; axe `image-alt`, `svg-img-alt` and `role-img-alt` pass or do not apply. Screen reader: pending. |
| 1.2.1 Audio-only and Video-only (Prerecorded) (Level A) | Not Applicable | No audio or video. |
| 1.2.2 Captions (Prerecorded) (Level A) | Not Applicable | No audio or video. |
| 1.2.3 Audio Description or Media Alternative (Prerecorded) (Level A) | Not Applicable | No video. |
| 1.3.1 Info and Relationships (Level A) | Supports | One `h1` per page and no skipped heading levels; header, nav (labeled "Site", "Breadcrumb"), main and footer landmarks; lists for lists; every data table has a caption, a header row and `scope` on its headers, and the High and Low rows use row headers; the wide king-tide tables sit in a named, focusable region; the find boxes have a `<label>`; each chart is a `<figure>` with a `<figcaption>`. Verified: code review of every template; axe structure rules; Chrome's accessibility tree for the find box, the tables, the figure and the breadcrumb. Screen reader: pending (table navigation, appendix step 3). |
| 1.3.2 Meaningful Sequence (Level A) | Supports | Reading order is document order. From 60 rem wide, a station day's card shows the table left of the chart, while the document has the chart first; each stands alone, so the order does not change the meaning. Verified: code review; Tab order measured. |
| 1.3.3 Sensory Characteristics (Level A) | Supports | Words like "below", "dashed" and "up triangle" always come with the name of the thing (the tide chart and table, High and Low). Verified: code review. |
| 1.4.1 Use of Color (Level A) | Supports | High and Low are words, with an up or down triangle, as well as blue and brown. Links in text are underlined. King-tide boxes have headings. On the chart, highs are peaks and lows are troughs, and the table beside it names each. Verified: code review; axe `link-in-text-block` passes. |
| 1.4.2 Audio Control (Level A) | Not Applicable | No audio. |
| 2.1.1 Keyboard (Level A) | Supports | Every control is a native link, button, text input or `<details>` summary; the wide king-tide tables scroll in a region that takes focus. The find boxes work from the keyboard, and Enter moves to the first match. Verified: Tab walk through every focusable element (up to 60 per page) on 17 pages; the find box with typed text and Enter. |
| 2.1.2 No Keyboard Trap (Level A) | Supports | Verified: the Tab walk reaches the last control in the footer on every page with fewer than 60 controls, and leaves the find boxes and table regions with Tab. |
| 2.1.4 Character Key Shortcuts (Level A) | Not Applicable | No keyboard shortcuts. |
| 2.2.1 Timing Adjustable (Level A) | Not Applicable | No time limits. A region page that moved redirects at once (a 0-second refresh), which is not a time limit. |
| 2.2.2 Pause, Stop, Hide (Level A) | Not Applicable | Nothing moves, blinks, scrolls or updates on its own. The page script fills in "Today" and the next tide once, when the page loads. |
| 2.3.1 Three Flashes or Below Threshold (Level A) | Supports | Nothing flashes; there is no animation. |
| 2.4.1 Bypass Blocks (Level A) | Supports | "Skip to content" is the first link on every page and becomes visible on focus; landmarks and headings. Verified: Tab walk. |
| 2.4.2 Page Titled (Level A) | Supports | Each page's title names its place or subject, for example "San Francisco (Golden Gate), CA tides today: high and low …" and "How Tide Hours predicts tides | Tide Hours". Verified: built pages; axe `document-title`. |
| 2.4.3 Focus Order (Level A) | Supports | Focus follows the visual order: skip link, header, breadcrumb, content, footer. The find box's Enter moves focus to the first match, which is the next thing below it. Verified: Tab walk at 1280 and 375 px. |
| 2.4.4 Link Purpose (In Context) (Level A) | Supports | No "click here" or "more"; links name their place or page. Verified: code review; axe `link-name` passes. |
| 2.5.1 Pointer Gestures (Level A) | Not Applicable | No multipoint or path gestures. |
| 2.5.2 Pointer Cancellation (Level A) | Supports | Only native links and buttons, which act on release. |
| 2.5.3 Label in Name (Level A) | Supports | Each control's accessible name is its visible text or label. Verified: Chrome's accessibility tree for the find boxes and the opt-out button; axe `label-content-name-mismatch` (needs-review) reported nothing. |
| 2.5.4 Motion Actuation (Level A) | Not Applicable | Nothing responds to device motion. |
| 3.1.1 Language of Page (Level A) | Supports | `lang="en"` on English pages and `lang="es"` on the Spanish king-tide page. Verified: built pages; axe `html-has-lang`, `html-lang-valid`. |
| 3.2.1 On Focus (Level A) | Supports | Focus never changes the page or opens anything. |
| 3.2.2 On Input (Level A) | Supports | Typing in a find box filters the list on the same page; nothing navigates until a link is chosen. Enter moves focus to the first match, which the reader asked for. |
| 3.2.6 Consistent Help (Level A) | Supports | Every page's footer has, in the same order, "How to read a tide page" and the Terms page, which gives the contact. Verified: built pages. |
| 3.3.1 Error Identification (Level A) | Not Applicable | No form is submitted and no input can be in error. A find box with no match says so in words ("No station name matches …"). |
| 3.3.2 Labels or Instructions (Level A) | Supports | The find boxes have visible labels ("Find a tide station by town, beach or bay"; "Find a place in California"). Verified: Chrome's accessibility tree. |
| 3.3.7 Redundant Entry (Level A) | Not Applicable | No multi-step process. |
| 4.1.1 Parsing (Level A) | Supports | Obsolete and removed in WCAG 2.2; for WCAG 2.0 and 2.1 it is always satisfied for HTML, per the WCAG errata. Listed for 2.0 and 2.1 readers. |
| 4.1.2 Name, Role, Value (Level A) | Supports | Native elements throughout; the table regions have `role="region"` and the caption as their name; the jump lists and "every day" lists are native `<details>`. Verified: Chrome's accessibility tree for the find boxes (searchbox, named by the label), the opt-out (button), the table regions (region, named by the caption), the tables (named by the caption) and the breadcrumb (navigation "Breadcrumb"); axe ARIA and name rules pass. Not verified: the `<details>` state in the tree. Screen reader: pending (appendix steps 3 and 5). |

### Table 2: Success Criteria, Level AA

| Criteria | Conformance Level | Remarks and Explanations |
| --- | --- | --- |
| 1.2.4 Captions (Live) (Level AA) | Not Applicable | No live audio or video. |
| 1.2.5 Audio Description (Prerecorded) (Level AA) | Not Applicable | No video. |
| 1.3.4 Orientation (Level AA) | Supports | No orientation lock; the layout works upright and sideways. |
| 1.3.5 Identify Input Purpose (Level AA) | Not Applicable | The only inputs are the find boxes, which search place names and collect nothing about the reader. |
| 1.4.3 Contrast (Minimum) (Level AA) | Supports | Text, light / dark, from the color tokens: body 14.85 / 15.44; muted text 6.83 / 8.81 on the page, lowest 6.27 (light, on the king-tide tint) and 7.53 (dark, on the panel); links 7.66 / 10.83, lowest 7.03 / 9.25; High 7.14 / 9.01 and Low 7.03 / 9.15 on a day's card; footer 11.00 / 12.32 (links 11.00 / 8.64). Verified: axe `color-contrast` in light and dark mode on 17 pages; `tests/test_design.py` holds the tokens to 4.5:1. |
| 1.4.4 Resize Text (Level AA) | Supports | Sizes in rem; no maximum zoom. Verified: at 320 CSS px (1280 px at 400% zoom) nothing scrolls sideways or is clipped. Text-only zoom (Safari, Firefox) was not measured separately. |
| 1.4.5 Images of Text (Level AA) | Supports | No images of text. The name "Tide Hours" is text; the mark beside it is a drawing. |
| 1.4.10 Reflow (Level AA) | Supports | Verified: 0 px of sideways scrolling at 320 × 256 on all 17 pages, light and dark (`make site-checks` checks this on its whole sample). The king-tide tables scroll sideways inside their own focusable box, which data tables may. |
| 1.4.11 Non-text Contrast (Level AA) | Supports | Focus outline, light / dark: 11.00 / 10.12 on the page, 11.00 / 12.32 in the footer; find box border 7.45 / 8.14; tide curve 7.14 / 9.01; the 0 ft datum line 3.59 / 4.20 (3.08 / 4.84 where the chart is shaded for night); high and low dots 7.14 / 7.03 light. The night shading of the chart (1.2:1) is not needed to read it: the caption says it and the sun times are in text. |
| 1.4.12 Text Spacing (Level AA) | Supports | Verified: with line height 1.5, letter spacing 0.12 em, word spacing 0.16 em and paragraph spacing 2 em applied, no page scrolled sideways and no text was clipped, at 320 and 1280 px, light and dark, on all 17 pages. |
| 1.4.13 Content on Hover or Focus (Level AA) | Supports | No tooltips, menus or pop-ups. The only thing shown on focus is the skip link itself, which stays while it has focus and goes when focus moves. |
| 2.4.5 Multiple Ways (Level AA) | Supports | The home page's find box and states list, state and region lists, breadcrumbs, the header's links, and "Nearby" links on station pages. |
| 2.4.6 Headings and Labels (Level AA) | Supports | Headings name what follows ("When is high tide at … today?", the date of each day, "Nearby"); find-box labels say what they search. Verified: code review. |
| 2.4.7 Focus Visible (Level AA) | Supports | A 3 px outline, offset 2 px, on every link, button, summary, input and table region. Verified: every focused element in the Tab walk had it. |
| 2.4.11 Focus Not Obscured (Minimum) (Level AA) | Supports | Nothing is sticky or fixed. Verified: in the Tab walk at 1280 × 900 and 375 × 667, every focused element was on screen and no other element covered its center. |
| 2.5.7 Dragging Movements (Level AA) | Not Applicable | Nothing is dragged. |
| 2.5.8 Target Size (Minimum) (Level AA) | Supports | Header links at least 44 px tall; list links at least 24 px; the find boxes 44 px. The smaller targets are links in sentences or the footer's line of links, which are spaced so 24 px circles do not overlap. Verified: axe `target-size` passes on 17 pages. |
| 3.1.2 Language of Parts (Level AA) | Supports | The Spanish king-tide page marks its link to the English page as English, and, with this branch, marks the footer's English analytics opt-out as English (before the fix it did not: DECISIONS 0054). Project names and the term "king tide", given with their Spanish meaning, are left unmarked as proper names and technical terms. |
| 3.2.3 Consistent Navigation (Level AA) | Supports | The same header links and footer links, in the same order, on every page; the Spanish page has the same three header links, translated. |
| 3.2.4 Consistent Identification (Level AA) | Supports | The same link text for the same destination across pages. |
| 3.3.3 Error Suggestion (Level AA) | Not Applicable | No input errors. A find box with no match suggests "Try a nearby town, or pick a state below." |
| 3.3.4 Error Prevention (Legal, Financial, Data) (Level AA) | Not Applicable | No transactions or submissions. Purchases happen on Etsy, Amazon or the App Store. |
| 3.3.8 Accessible Authentication (Minimum) (Level AA) | Not Applicable | No sign-in. |
| 4.1.3 Status Messages (Level AA) | Supports | The find boxes' result counts are in an `<output>` (role status) that exists before it changes; the opt-out's messages and the "today is not on this page yet" notice have `role="status"`. Verified: Chrome's accessibility tree shows each as role status, live polite; typing "monterey" in the home find box set it to "2 stations match." with focus still in the box, and Enter then moved focus to the first result. Screen reader: pending (appendix step 2). |

### Table 3: Success Criteria, Level AAA

Not evaluated.

## Summary of conformance

| Level | Supports | Partially Supports | Does Not Support | Not Applicable | Total |
| --- | --- | --- | --- | --- | --- |
| A (WCAG 2.2, 31 criteria) | 20 | 0 | 0 | 11 | 31 |
| AA (WCAG 2.2, 24 criteria) | 17 | 0 | 0 | 7 | 24 |

4.1.1 Parsing, listed for WCAG 2.0 and 2.1, is not counted.

Before this branch's fix, 3.1.2 was Partially Supports: the Spanish
page's footer had unmarked English text whenever analytics was on (always,
on the published site).

## Appendix: the screen-reader walkthrough still to do

About 60 to 75 minutes. Use the published site after the branch is
deployed. Note what is read, in what order, and anything confusing; a
finding goes to a GitHub issue and, if it is a failure, changes this
report.

1. **VoiceOver on an iPhone (Safari), a station page** (for example
   `/stations/9414290/`). Swipe from the top. Listen for: "Skip to
   content"; the H1; the next-tide sentence; each question heading and its
   days; each day's heading with its date; the chart read as one figure
   with its caption (the drawing itself should be silent); the table with
   "Tide", "Time", "Height" headers and each row's High or Low. Use the
   rotor's Headings and Tables. (15 min)
2. **VoiceOver on a Mac (Safari), the home page find box.** Tab to it.
   Type "monterey": the count ("N stations match.") should be spoken
   without moving focus. Press Enter: focus should land on the first
   result, read as a link. Type "zzzz": the no-match sentence should be
   spoken. Repeat on `/states/ca/`. (10 min)
3. **NVDA with Firefox or Chrome on Windows, the king-tide page**
   (`/king-tides/`). Tab into a table region: its name (the table caption)
   should be read. Use table navigation (Ctrl+Alt+arrows) in one station's
   table: column headers and the row's dates should be read with each
   cell. Open one "every day" disclosure with Enter or Space: expanded
   should be announced. (15 min)
4. **NVDA or VoiceOver, the Spanish page** (`/es/king-tides/`). The page
   should be read with a Spanish voice; the "English" link and the
   footer's "Opt out of analytics" with an English voice. Press the
   opt-out button: "Analytics is off on this device." should be spoken;
   press again to opt back in. (10 min)
5. **TalkBack on Android (Chrome), a region page**
   (`/states/ca/monterey-bay/`). Each place should be read as a link,
   then its highs and lows as text; the jump list's summary as a
   collapsed button that expands. (10 min)
6. **Any reader, the king-tide calendar** (`/king-tides/washington/`) and
   **About**: headings list (rotor or NVDA's Insert+F7) should give the
   page's outline without gaps. (5 to 10 min)
