---
name: travel-itinerary-builder
description: Plans a multi-day trip from the traveller's own bookings and wish-list, researches and verifies every place, then generates a phone-first live trip guide (one scrolling HTML page with an illustrated route map drawn from real coastline data, Now/Next, day-by-day plans, swipeable options, vetted food and bar picks, know-how and bookings) plus a shareable A4 PDF summary with working map and booking links and PNG copies of each page for WhatsApp. Use whenever someone asks to plan, organise, build, redesign or "make a page/PDF for" a trip, holiday, itinerary, travel plan or group getaway — including when they paste a list of places from YouTube or friends, share flight/hotel bookings, ask for a day-wise summary to share with friends, or want an itinerary they can open on their phone during the trip.
---

# Travel itinerary builder

This skill turns "here are our flights, hotels and a list of places we saw on YouTube" into three things a group actually uses on the road:

1. **A live trip guide** — one HTML page, light by default so it reads in sun and crowds, with frosted-glass top and bottom bars, an illustrated route map, a Now/Next card that switches on during the trip, the plan day by day, options for every flexible slot, Explore (eat & drink / places / options / events, filtered by area, with per-phone tick-offs), and Info (SOS numbers, know-how, bookings).
2. **A shareable PDF** — page 1 is the map, the stays, every transfer and the emergency numbers; then four days per page with the key times and the day's cafés, bars, places and tours, every one a tappable Google Maps or booking link.
3. **PNG copies of each PDF page** — for the WhatsApp chat preview (links don't work in images; the PDF is the one to tap).

It was distilled from a real eight-day, five-person, four-base trip (Phuket → Krabi → Phi Phi → Phuket) built over many rounds of feedback. The rules below are the ones that feedback produced; most of them exist because the first version got it wrong.

Everything is generated from one data file, `trip.json`, by `scripts/itinerary_kit.py`. You write the data; the script owns the design. **Never hand-edit the generated HTML** — change `trip.json` and rebuild, so every correction lands in the page, the PDF and the PNGs at once.

## Workflow

### 1. Intake — ask once, then work

Ask (in one round, multiple-choice where you can) only what you can't find: dates; who's travelling and from where (arrival and departure times per person matter); what's booked (flights, stays, ferries/trains, tours) and what's still open; the must-dos and any list they've collected; hard constraints (no hikes, budget level, kids, dietary); special days (a birthday — no transfers or venue changes that day); and where outputs should go. If they've uploaded bookings, read them instead of asking.

Save their list verbatim — you will check every item and report back on each one.

### 2. Research — verify, don't recall

Treat every fact as something to look up for *these dates*. Search the web (use a fetch sub-agent to read pages if you have no fetch tool), and keep the URLs for the footer and your reply.

- **Entry rules** for each traveller's passport: visa, arrival cards (opening windows matter — Thailand's TDAC opens 3 days before arrival), banned items (vapes in Thailand), cash-on-entry rules.
- **Every place on their list**: does it exist, is it open on that weekday, opening hours, where exactly it is, and the Google rating. Correct misnamed items ("Kamala viewpoint" was really Laem Singh) and say so.
- **Places you add**: cafés, bars and restaurants you suggest must be well rated (Google ≥ 4.5 with a meaningful review count) and a proper sit-down or destination venue — not a cheap street stall — unless it's on the user's list. The user explicitly rejected a roti stall that was "famous". Replace anything closed or under 4.5.
- **Transport**: real schedules and durations (ferry slots, check-in times — the hotel's 14:00 check-in set the shape of a whole afternoon), pier/station fees, taxi/Grab fares, last-departure times.
- **Tours and what's on**: search a tour marketplace (Klook, GetYourGuide) for the destination and dates; pull operator, price, rating and the booking URL. Search for events and festivals in the date range, and weekday-only things (weekend markets, closed-on-Monday bars).
- **Local know-how**: scams, money (ATM fees, exchange), getting around, sea and sun, and the four emergency numbers that matter (tourist police, ambulance, police, fire) plus the embassy.

### 3. Plan — rules that came from real feedback

- **Arrival day stays light until everyone is there.** If one person lands at 20:00, the afternoon is organised but modest — lunch, a beach, a mall/market from their list — and nothing famous happens before the whole group is together.
- **Build in the real constraints**: be at the pier 30 minutes early and leave Patong traffic a buffer; morning activities must end before tour pickups; check-in times; weekend-only markets on the weekend; venues closed on certain days. Say *why* in the row note or the day's tip.
- **Give flexible slots options, and keep them visible.** A dawn temple climb, a viewpoint at sunset vs. the beach, three evening choices — put them in `options` with one `pick`. The user missed an option the first time because it was folded away; options now render as cards in the day and in Explore → Options. Make optional rows say "Optional:" in plain words.
- **Respect the group's stated pace.** A rest afternoon in a private-pool room is a plan, not a gap. When they say "we'd rather relax", cut the itinerary down, don't pad it.
- **No budget tables, countdowns, "straight answers" panels or other content the user didn't ask for.** They were each removed after the user saw them. Add only what helps someone standing on the street decide where to go next.

### 4. Write `trip.json`

Follow `references/trip-schema.md`; start from `examples/andaman-trip.json` (a complete eight-day trip). The essentials:

- Times are 24-hour `HH:MM`. Write sentence case; mark importance with `"key": true`, never ALL CAPS.
- Every row with a location gets a map link; give `map` when the display text (`"Patong, Phuket"`) is too vague to search.
- The day `tip` is one sentence of insider advice ("Toy-Tor-Toe takes cash only and closes at 7 — that's why it's lunch").
- Places: `source: "list"` for theirs, `"pick"` for yours, each with `rating`, `hours`, `what` and `day`.
- `checked`: one entry per item they sent — Checked / Corrected / Heads up / Closest match, and where it landed.

### 5. The route map

The map is an illustrated chart drawn to scale from real coastline — flat land on a soft sea, numbered pins with label tags, dotted ferry routes with small boats, solid roads, ring dots for piers and airports, a few silhouettes. (A plain lat/long scatter chart was rejected as "odd, confusing"; this style replaced it.)

1. Pick a `bbox` that holds every point with sea margin on the sides where labels will sit.
2. Fetch land: `python3 scripts/fetch_coastline.py <lon0> <lat0> <lon1> <lat1> land.json` (needs `npm` and `pip install shapely`; downloads OSM-derived land polygons once, ~50 MB, then clips to a few KB). Without network, omit `land` — the map still draws routes and pins on sea.
3. Bend sea legs out into the water, place labels with `dx`/`dy`, then look at the phone screenshot from `check` and fix collisions with `dx_narrow`/`dy_narrow` or `hide_narrow`. Expect two or three passes.
4. The map credits "Coastline © OpenStreetMap contributors" automatically when land is drawn — keep that.

### 6. Build, render, check

```bash
python3 scripts/itinerary_kit.py fonts                 # once: caches the three fonts locally via npm (for PDF/PNG/screenshots)
python3 scripts/itinerary_kit.py all trip.json --out dist/
```

`build` writes `artifact.html` (fragment for Claude's Artifact tool), `page.html` (standalone, opens anywhere), `page.local.html` (same, with local fonts for screenshots) and `summary.html`. `render` prints `<slug>-summary.pdf` and `<slug>-pageN.png` through headless Chromium, reports any PDF card that overflows, and counts the links. `check` audits the page at 390 px (light and dark) and 1280 px — horizontal overflow, smallest font (≥12 px), font weights (≤3), tap targets (≥44 px), JS errors — and saves screenshots.

Requirements: Python 3.9+; `pip install playwright pypdf` and `playwright install chromium` for render/check (skip the install if Chromium is already present). `build` alone needs only the standard library.

**Then look.** Open the phone screenshot, the dark one and every PDF page image yourself before you call it done. The automated audit catches overflow; only your eyes catch a label sitting on a pin, a card that's mostly empty, or a day that reads wrong. Fix in `trip.json` (or the map offsets), rebuild, look again.

### 7. Deliver

- **In Claude with the Artifact tool**: publish `dist/artifact.html` (load the `artifact-design` skill first if you haven't — the page already meets its contract: tokens with dark-mode blocks, safe-area gutters, no external hosts but Google Fonts). Then set `live_url` to the published URL, run `render` again so the PDF's "Open the live guide" button works, and send the PDF and PNGs as files. Republish to the **same** artifact on every change so the link they've shared keeps working.
- **Elsewhere**: hand over `page.html` (host it anywhere, or open it locally), the PDF and the PNGs. If a folder on the user's machine is connected, save them there.
- Reply in a few lines: what changed, anything they must do before the trip (arrival card, book this tour a day ahead, cash), what you couldn't verify, and sources.

### 8. Iterate

Corrections will come in rounds ("move the shooting range to the 18th morning", "we want Kamala sunset then Sunday Old Town for dinner"). For each: re-check the facts that the change touches (opening times, check-in, travel time), edit `trip.json`, rebuild everything, look at the affected day on the phone and in the PDF, republish to the same URL, resend the PDF. Keep the structure the user has approved — change content, not layout, unless they ask.

## The design, and why

The generator encodes these; know them so your content fits and so you can extend the kit without breaking it.

- **Light by default, night mode on request.** The page is read outdoors in bright sun and in crowds. A moon button switches to dark and the phone remembers. Both themes are full token sets.
- **One continuous scroll** — Today (hero, map, Now/Next) → the route timeline → day by day → Explore → Info — with frosted-glass chrome that always says where you are. The top bar shows the current day once that day covers at least 60% of the screen below the bars (switching earlier felt jumpy); the date strip pins under it inside the days; a bottom tab bar on phones, inline nav on desktop. An **Explore** button and quick links (Eat & drink, Places, Options, Events) sit at the top, because "just show me the food list" is the most common need mid-trip. A red **SOS** button jumps to the emergency numbers from anywhere.
- **Now/Next only during the trip**, computed in the destination's time zone, and it moves to the top of the page on trip days. No countdown — it was explicitly unwanted.
- **Progressive disclosure keeps it short but complete.** Each row is time · activity · place; tap for the note and the map button. Every-address lists fold. Options never fold.
- **Type**: Bricolage Grotesque (display, condensed widths), Atkinson Hyperlegible Next (body — designed for legibility), Atkinson Hyperlegible Mono (times and numbers). Weights 400/500/600 only; nothing under 12 px; body line height ~1.55, headings 1.1–1.25.
- **Colour**: cool limestone-mist canvas, white surfaces with 1 px hairlines, deep ink, one accent (Andaman blue `#0A5C9E`), marigold (`#F4B33A`, the colour of longtail ribbons) reserved for "now", key moments and birthdays, red only for SOS. Override per trip with `theme`.
- **Touch and layout**: every control ≥44 px; nothing scrolls sideways at 375 px; hover effects only inside `(hover: hover)`; side gutters use safe-area insets.
- **Motion**: scroll-driven and subtle — a progress hairline, the route line drawing in, cards easing up — transform/opacity only, 100–300 ms tokens, all of it off under `prefers-reduced-motion`. The page is complete without it.
- **PDF**: A4, Chromium print, so links survive (don't use reportlab for this — no shared layout with the page and harder links). A postage stamp of original scenery, the same map tightened, cards that must fit — `render` tells you if they don't.

## Lessons that cost time

- **Grid/flex children that contain a horizontal scroller need `min-width: 0`.** Without it, the swipeable options row silently widened the whole page to 631 px on phones.
- **Author CSS beats the `hidden` attribute.** Anything you show/hide with `el.hidden` needs `[hidden]{display:none!important}` (the kit includes it).
- **Sticky headers break naive scrolling.** Jump targets need `scroll-margin-top` equal to the bar heights, or headings land under the glass.
- **Don't detect special days from text.** "Birthday eve" in a title once got the birthday badge; use the date/`badge` field.
- **Map labels clip at phone width.** Labels left of a coastal pin run off the left edge; give the map sea margin or a `dx_narrow` to the right, and hide region and small labels on phones.
- **Fonts may not load in a headless sandbox** (Google Fonts blocked), so screenshots and PDFs silently fall back to system fonts. Run `itinerary_kit.py fonts` once; the kit points `@font-face` at the cached files for rendering.
- **Clipping a continent is slow.** Pre-filter polygons by bounding box before any geometry work (`fetch_coastline.py` does) — `make_valid` on the Asia polygon timed out.
- **Python 3.12-only f-strings** (nested same-type quotes, backslashes in `{}`) break the script on 3.10/3.11. Keep the kit 3.9-compatible; check with `vermin`.
- **Stale facts are the biggest risk.** A restaurant on the first draft had closed; a viewpoint fee had gone from 30 to 50 THB; a ferry pier fee was 20 THB, not the 400 THB "island fee" one source claimed. Verify with the most recent dated source and say when sources conflict.

## Bundled resources

- `scripts/itinerary_kit.py` — the generator (`build`, `render`, `check`, `all`, `fonts`). Self-contained; its CSS and JS were taken from the reference build and hold no trip-specific text.
- `scripts/fetch_coastline.py` — clips real coastline to your map box.
- `references/trip-schema.md` — every field of `trip.json`, with examples. Read it before writing the data.
- `examples/andaman-trip.json` + `examples/andaman-land.json` — the full reference trip (names anonymised), ready to build: `python3 scripts/itinerary_kit.py all examples/andaman-trip.json --out /tmp/andaman`.
- `evals/evals.json` — prompts to test the skill against.

## What else it leans on

These were used to build and polish the reference trip; use them when your environment has them, and do the equivalent by hand when it doesn't.

- **Claude Artifact tool + `artifact-design` skill** — publishing the live page and its page contract (theme tokens for light/dark, safe-area gutters, CDN/font allowlist, title rules).
- **VectorLab UX skills** (`ux-audit`, `typography`, `colour-palette`, `spacing`, `viewports`, `motion`, `reduced-motion`, `verbs`, `anti-slop`, `page-patterns`) — the hard rules behind the weights, sizes, 44 px targets, verb-first buttons ("Open map", "Tick off", "Book on Klook"), motion tokens and the pre-flight audit. `check` automates the measurable ones.
- **`pdf` skill** — guidance for PDF work; this kit prints with Chromium instead of reportlab so links and layout match the page.
- **Web search + a page-fetch sub-agent** — for verification; tour marketplaces (Klook) for tours, prices and booking links; Google Maps search URLs for every place.
- **Libraries**: Playwright/Chromium (PDF, PNG, audit), pypdf (link count), shapely (coastline clipping), `@geo-maps/earth-lands-500m` from npm (OpenStreetMap-derived land polygons, ODbL — keep the attribution), and `@fontsource` packages for local copies of the three Google Fonts (SIL OFL).

## Portability

Nothing here is specific to Claude Code. Any agent that can run Python and read this file can follow the workflow: write `trip.json`, run the kit, look at the screenshots, deliver `page.html` + PDF + PNGs. Where there's no Artifact tool, host `page.html` anywhere static (or just send it — it works offline, minus fonts and map links).
