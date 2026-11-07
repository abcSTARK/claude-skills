# trip.json schema

`itinerary_kit.py` reads one JSON file. Everything the page, PDF and PNGs show comes from it — no trip-specific code. `examples/andaman-trip.json` is a complete, real 8-day example; copy it and replace the content rather than starting from nothing.

Conventions that apply everywhere:

- **Times are 24-hour `"HH:MM"`** (`"07:00"`, `"21:30"`). Now/Next on the live page compares these to the trip's local clock, so a time like `"~noon"` is allowed but will never be "Now".
- **Write in sentence case.** No ALL-CAPS to signal importance — set `"key": true` on the row instead. The generator escapes all text, so write `&` and quotes literally (only `title_html` takes markup).
- **Map queries (`q`, `map`, `loc`, `map_query`)** become Google Maps search links. Make them specific enough to land on the right pin: `"Kopitiam by Wilai Phuket"`, not `"Kopitiam"`. `map_region` is appended to every query.
- Optional fields can be left out entirely; empty strings are treated as absent.

## Top level

| Field | Type | Notes |
|---|---|---|
| `short_title` | string | Browser tab, top bar, PDF footer. Two to four words: `"Thailand ’26"`. |
| `title_html` | string | Hero headline. May contain `<em>` for the accent word: `"Phuket, Krabi <em>&amp;</em> Phi Phi"`. |
| `dates_label` | string | `"17–24 Nov · Phuket, Krabi, Phi Phi"` — top bar on wide screens and PDF eyebrow. |
| `eyebrow` | string | Small caps line above the hero title. |
| `dek` | string | One or two sentences under the title: the shape of the trip. |
| `travellers` | string[] | First names, shown under the dek and on the PDF. |
| `utc_offset_hours` | number | Destination's UTC offset (Thailand `7`, India `5.5`). Drives Today and Now/Next. |
| `storage_key` | string | Prefix for per-phone storage (theme, tick-offs). Short, unique per trip: `"th26"`. |
| `file_slug` | string | Output file names: `<slug>-summary.pdf`, `<slug>-page1.png`. |
| `map_region` | string | Appended to every Google Maps query, e.g. `"Thailand"`. |
| `researched` | string | Shown beside the Info heading: `"Researched November 2026"`. |
| `explore_note` | string | Line under the Explore heading. |
| `live_url` | string | URL of the published live page. When set, the PDF gets an "Open the live guide" button and footer link. Publish first, then set this and re-render. |
| `footer` | string | Sources, caveats, "confirm X when you book". |
| `theme` | object | Optional token overrides: `{"light": {"accent": "#7A3E9D"}, "dark": {"accent": "#C9A2E6"}}`. Keys are token names without `--` (see the design section of SKILL.md). |
| `map` | object | The illustrated route map — below. |
| `journey` | object | The route timeline — below. |
| `areas` | object | Ordered `{ "area_id": "Label" }`. Order = chip order in Explore and group order in lists. |
| `days` | array | One object per calendar day — below. |
| `places` | array | Every café, bar, restaurant, beach, sight — below. |
| `events` | array | What's on during the dates. |
| `checked` | array | Optional: the user's own list, each item verified. |
| `emergency` | array | First four render as big tap tiles; the first is styled as primary. |
| `emergency_link` | object | `{ "text", "url", "label" }` — embassy or similar, as a sentence with a link. |
| `know` | array | Know-how accordions. |
| `bookings` | array | Booking accordions. |
| `pdf` | object | PDF-only content — below. |

## `map`

```jsonc
"map": {
  "bbox": [97.86, 7.56, 99.10, 8.28],          // lon0, lat0, lon1, lat1 - include sea to the sides for labels
  "land": "andaman-land.json",                  // from scripts/fetch_coastline.py, path relative to trip.json; omit if unavailable
  "aria": "Route map: ...",                     // one-sentence description of the route for screen readers
  "points": {
    "hkt":    {"lat": 8.113, "lon": 98.317, "label": "Airport", "dx": "16px", "dy": "-50%"},
    "patong": {"lat": 7.896, "lon": 98.297, "kind": "stop"}
  },
  "stops": [                                    // numbered pins, in travel order; "point" refers to points{}
    {"point": "patong", "label": "Patong", "dates": "17", "dx": "calc(-100% - 14px)", "dy": "-10%"},
    {"point": "kamala", "label": "Kamala", "dates": "22–24", "dx": "calc(-100% - 14px)", "dy": "-130%",
     "dx_narrow": "12px", "dy_narrow": "-125%"}
  ],
  "legs": [{"from": "rassada", "to": "klong", "mode": "sea", "bend": -70}],
  "texts": [{"text": "Andaman Sea", "lat": 7.71, "lon": 98.10, "kind": "sea"},
            {"text": "PHUKET", "lat": 8.05, "lon": 98.37, "kind": "region"},
            {"text": "Phang Nga Bay", "lat": 8.02, "lon": 98.47, "kind": "sea", "hide_narrow": true}],
  "decor": [{"type": "peaks", "lat": 8.12, "lon": 98.53, "scale": 1.1},
            {"type": "plane", "lat": 8.139, "lon": 98.277},
            {"type": "flag",  "lat": 7.700, "lon": 98.817}]
}
```

- **points** — every place a leg touches. `kind: "stop"` points are drawn only as numbered pins; other points (piers, stations, airports) get a ring dot and, if `label` is set, a small label. Small labels are hidden on phones.
- **Label offsets** — `dx`/`dy` are CSS lengths applied as `translate(dx, dy)` from the point. `-50%`/`-260%` puts a label centred above a pin; `calc(-100% - 14px)` / `-10%` puts it to the left. `dx_narrow`/`dy_narrow` override on phones (<768px), where the map is ~360px wide and labels collide sooner. Check the phone screenshot and tune these; it is normal to need two or three passes.
- **legs** — `mode`: `road` (solid grey), `sea` (dotted accent with a boat at the midpoint), `rail` (dashed), `air` (fine dots). `bend` bows the curve (map units, ±10–80); use it to push ferry routes out into water and to separate two roads between the same towns.
- **texts** — `kind`: `sea` (italic, for water bodies), `region` (spaced caps, hidden on phones), or `place`. `hide_narrow` hides any label on phones.
- **decor** — `peaks` (limestone/mountain silhouette; scale 0.6–1.2), `plane` (near the airport), `flag` (a small pennant — used for the birthday boat). Keep it to a handful; decor is seasoning.

## `journey`

```jsonc
"journey": {
  "start": {"title": "Land at Phuket airport", "sub": "Tue 17 · four at 11:35, Rohan at 20:00", "icon": "plane"},
  "stops": [{"name": "Ao Nang, Krabi", "short": "Ao Nang", "stay": "Nomads Ao Nang", "dates": "Wed 18 – Fri 20 Nov",
             "nights": "2 nights", "map_query": "Nomads Ao Nang Krabi", "first_day": 2}],
  "legs":  [{"icon": "boat", "when": "Wed 18 · 13:30", "what": "Ferry, Rassada Pier → Klong Jilad", "duration": "~2 h 30"}],
  "end":   {"title": "Fly home", "sub": "Mon 23 · Kabir, Dev 12:30 · Tue 24 · ...", "icon": "plane"}
}
```

`legs[i]` is drawn between `stops[i]` and `stops[i+1]`, so there is one fewer leg than stops. Icons: `plane`, `boat`, `car`, `train`. `first_day` (1-based) is where tapping the stop jumps. `short` is used on the PDF stop cards.

## `days[]`

```jsonc
{
  "date": "2026-11-21", "label": "Sat 21 Nov",          // label must start "<Wkd> <day-number>"
  "title": "Pirate boat day", "sleep": "Koh Phi Phi, Bayview",   // omit sleep on the last day -> "Flying home"
  "area": "phiphi",                                     // Explore opens on this area when the trip is on this day
  "badge": "Rohan’s birthday",                          // optional: gold badge + gold card edge
  "tip": "Carry cash onto the boat: the 1,900 THB balance plus the bar.",
  "rows": [
    {"time": "11:30", "act": "Phi Phi Pirate Boat — booked", "loc": "Phi Phi Leh", "who": "",
     "note": "Maya Bay, Pileh Lagoon, Viking Cave ...", "key": true, "map": "Relax Bar Koh Phi Phi",
     "pdf_act": "Pirate boat", "pdf": true}
  ],
  "options": [{"label": "Sunset", "items": [ <option>, <option> ]}],
  "spots": ["mango-garden", "relax-bar"],              // place ids; shown in "Every address today" and on the PDF
  "book": [{"label": "Hanuman luge on Klook", "url": "https://..."}],   // PDF only, when the day has no options
  "pdf_title": "shorter title for the PDF card"
}
```

- **rows** — one line per thing that happens, in time order. `loc` is shown under the line and used for the map link unless `map` overrides it. `who` only when it's not the whole group. `note` hides behind the tap — put the practical detail there (prices, booking rules, "cash only"). `key: true` adds the gold diamond and makes the row eligible for the PDF; `pdf: true` forces a non-key row onto the PDF (arrivals, departures). The PDF shows at most 7 rows per day — mark accordingly.
- **options** — choices for a flexible slot, rendered as swipeable cards under the day and collected in Explore → Options. One item per group should usually be `"pick": true`.

### `<option>`

```jsonc
{"name": "Phi Phi Viewpoint 1 + 2 at sunset", "time": "16:45 - 18:45", "effort": "Steep stairs, 20-30 min up",
 "price": "50 THB pp", "rating": "4.8 (249 reviews)", "pick": true,
 "note": "Stairs start on the east side of Tonsai ...", "q": "Phi Phi Viewpoint 2",
 "url": "https://www.klook.com/activity/...", "url_label": "Book on Klook"}
```

## `places[]`

```jsonc
{"id": "kopitiam", "kind": "eat", "name": "Kopitiam by Wilai", "area": "oldtown", "type": "Thai",
 "source": "list", "rating": "4.6", "reviews": "3,120", "hours": "11:00–22:00",
 "what": "One of the best pad thais on the island, right on Thalang Rd", "day": "Day 6 dinner",
 "q": "Kopitiam by Wilai Phuket"}
```

- `kind`: `eat` (food and drink) or `go` (beaches, sights, markets, activities).
- `source`: `list` (the user asked for it — labelled "Your list") or `pick` (you added it — labelled "Our pick"). Picks must clear the quality bar in SKILL.md.
- `day` says when it fits ("Day 3 lunch", "Days 6–8", "Not placed — backup"). `id` must be unique; days reference it.

## Smaller arrays

```jsonc
"events":    [{"when": "Sun 22 Nov, 1-7 pm", "name": "Zoo del Mar daytime party", "where": "Cafe del Mar, Kamala", "note": "..."}],
"checked":   [{"item": "Kamala viewpoint", "verdict": "Corrected", "finding": "No viewpoint by that name ...", "where": "Day 7 - Laem Singh"}],
"emergency": [{"name": "Tourist Police", "number": "1155", "note": "English-speaking - first call"}],
"know":      [{"kicker": "Money", "title": "Cash, cards and ATMs", "items": [["ATM fee", "Every foreign card pays 220 THB ..."]]}],
"bookings":  [{"title": "Flights", "sub": "All ten legs booked",
               "rows": [{"lead": "17 Nov", "main": "Arjun", "small": "Bangalore (BLR) 06:15 → Phuket 11:40", "status": "Booked"},
                        {"lead": "Day 3", "main": "7 Islands sunset tour", "small": "From ~US$40", "url": "https://...", "url_label": "Book on Klook"},
                        {"lead": "22 Nov", "main": "Zenmaya Oceanfront", "small": "...", "map": "Zenmaya Oceanfront Kamala"}]}]
```

`verdict` values: `Checked` renders green; anything else (`Corrected`, `Heads up`, `Closest match`) renders in the accent colour. A booking row shows `status` if present, else a `url` link, else a `map` link.

## `pdf`

```jsonc
"pdf": {
  "facts": "7 nights, 4 stays, 3 ferries",
  "stamp_title": "Andaman", "stamp_note": "THB · 2026",           // the postage stamp on page 1
  "map_bbox": [97.86, 7.66, 99.10, 8.18],                         // tighter crop than the page map, so page 1 fits
  "map_max_height_mm": 110,                                       // default 110; portrait regions shrink in width to fit
  "day_page_titles": {"0": "Days 1–4 · Patong, Krabi, Phi Phi", "1": "Days 5–8 · The birthday, then Phuket"},
  "transport": [{"when": "Wed 18", "main": "Ferry 13:30 · Rassada → Klong Jilad", "small": "Be at the pier by 13:00"}],
  "handy":     [{"when": "Thu 19 · dawn", "name": "Tiger Cave Temple", "note": "1,260 steps, ~1 h up", "q": "Tiger Cave Temple Krabi"}]
}
```

Page 1 = title, stamp, map, stop cards, "Getting there and between" (`transport`, ~7 rows max), "Options to keep handy" (`handy`, ~5 rows max) and the emergency tiles. Then one page per four days. If `render` reports overflow, shorten `transport`/`handy`, tighten `map_bbox`, cut PDF rows (`key`/`pdf` flags) or set a shorter `pdf_title`.
