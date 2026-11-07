#!/usr/bin/env python3
"""
itinerary_kit.py - turn one trip.json into a phone-first trip guide (HTML), a shareable
A4 summary (PDF with working links) and PNG copies of each PDF page.

  python3 itinerary_kit.py build  trip.json --out dist/      # page.html + artifact.html
  python3 itinerary_kit.py render trip.json --out dist/      # summary.pdf + summary-page-N.png
  python3 itinerary_kit.py check  trip.json --out dist/      # layout audit (overflow, fonts, tap targets, PDF fit)
  python3 itinerary_kit.py all    trip.json --out dist/      # build + render + check
  python3 itinerary_kit.py fonts                             # cache the three web fonts locally (npm)

build needs only the standard library. render/check need Playwright (chromium) and, for the
link count, pypdf. The schema lives in references/trip-schema.md.
"""
import argparse
import html
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus

e = html.escape
TRIP = {}
BASE = Path(".")
FONT_DIR = Path(os.environ.get("ITINERARY_FONTS", Path.home() / ".cache" / "itinerary-kit" / "fonts"))
WEEKDAYS = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}


# ================================================================== helpers
def gmap(q):
    region = TRIP.get("map_region", "")
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(q + (", " + region if region else ""))


def to_min(t):
    m = re.match(r"^(\d{1,2}):(\d{2})$", t or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else -1


KEY_MARK = '<i class="key" aria-label="Key moment"></i>'


def wrap(tag, text):
    return f"<{tag}>{e(text)}</{tag}>" if text else ""


def ext(url, label):
    return f'<a class="btn" href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


ICON = {
    "today": '<path d="M12 3v2M12 19v2M5 12H3M21 12h-2M6.3 6.3 4.9 4.9M19.1 19.1l-1.4-1.4M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',
    "days": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "explore": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6v.1"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "boat": '<path d="M3 15h18l-2.5 4h-13Z"/><path d="M6 15V9h9l3 6M10 9V5h3v4"/>',
    "car": '<path d="M4 16v-4l2-5h12l2 5v4ZM4 16v2M20 16v2"/><circle cx="7.5" cy="13" r=".6"/><circle cx="16.5" cy="13" r=".6"/>',
    "train": '<rect x="6" y="3.5" width="12" height="13" rx="3"/><path d="M6 11h12M9 20l-2 1.5M15 20l2 1.5M9.5 14h.1M14.5 14h.1"/>',
    "plane": '<path d="M2.5 13.5 21 7l-2 3.6-7.6 2.3L8 20l-1.8.4.9-6.6-4.6-.3Z"/>',
    "chev": '<path d="m8 10 4 4 4-4"/>',
}


def icon(name, cls="ico"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON.get(name, ICON["car"])}</svg>')


# ================================================================== original scenery (stamp art)
def _ridge(seed, w, base_y, floor, h_lo, h_hi, w_lo, w_hi, gap_lo, gap_hi):
    rnd = random.Random(seed)
    d = [f"M-40,{floor}", f"L-40,{base_y}"]
    x = -20.0
    while x < w + 40:
        x += rnd.uniform(gap_lo, gap_hi)
        bw, h = rnd.uniform(w_lo, w_hi), rnd.uniform(h_lo, h_hi)
        top = base_y - h
        d.append(f"L{x:.1f},{base_y:.1f}")
        d.append(f"C{x - bw*0.13:.1f},{base_y - h*0.52:.1f} {x - bw*0.17:.1f},{base_y - h*0.86:.1f} {x - bw*0.06:.1f},{top:.1f}")
        d.append(f"C{x + bw*0.16:.1f},{top - h*0.10:.1f} {x + bw*0.56:.1f},{top - h*0.07:.1f} {x + bw*0.74:.1f},{top + h*0.07:.1f}")
        d.append(f"C{x + bw*0.90:.1f},{top + h*0.34:.1f} {x + bw*1.12:.1f},{base_y - h*0.44:.1f} {x + bw:.1f},{base_y:.1f}")
        x += bw
    d += [f"L{w + 40},{base_y}", f"L{w + 40},{floor} Z"]
    return " ".join(d)


def scene(w=340, h=400):
    """Sea, sun and a ridge of hills, coloured by CSS tokens --sc1..--sc8 so it follows the theme."""
    k, sea_y, sun_x = h / 480.0, int(h * 0.615), int(w * 0.77)
    u = f"s{w}x{h}"
    rnd = random.Random("sea")
    glints = "".join(f'<rect x="{sun_x - 34 - i*6 + rnd.uniform(-10, 10):.0f}" y="{sea_y + 5 + i*(h-sea_y)/11:.0f}" width="{68 + i*13:.0f}" '
                     f'height="{2.2 + i*0.3:.1f}" style="fill:var(--sc3)" opacity="{max(0.05, 0.42 - i*0.035):.3f}"/>' for i in range(11))
    return f"""<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>
<linearGradient id="sky-{u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" style="stop-color:var(--sc1)"/><stop offset="100%" style="stop-color:var(--sc2)"/></linearGradient>
<linearGradient id="sea-{u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" style="stop-color:var(--sc7)"/><stop offset="100%" style="stop-color:var(--sc8)"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#sky-{u})"/><circle cx="{sun_x}" cy="{sea_y - 30}" r="{max(18, 34*k):.0f}" style="fill:var(--sc3)"/>
<path d="{_ridge(u+'f', w, sea_y + 2, h, 0.15*h, 0.33*h, 30*k, 84*k, 16*k, 70*k)}" style="fill:var(--sc4)" opacity=".6"/>
<path d="{_ridge(u+'m', w, sea_y + 3, h, 0.24*h, 0.44*h, 44*k, 112*k, 110*k, 260*k)}" style="fill:var(--sc5)"/>
<rect x="0" y="{sea_y}" width="{w}" height="{h - sea_y}" fill="url(#sea-{u})"/>{glints}
<path d="{_ridge(u+'n', w, h + 6, h + 44, 0.40*h, 0.62*h, 78*k, 150*k, 620*k, 1050*k)}" style="fill:var(--sc6)"/></svg>"""


# ================================================================== route map
class Map:
    def __init__(self, m, bbox=None):
        self.m = m
        self.x0, self.y0, self.x1, self.y1 = bbox or m["bbox"]
        self.K = 1000 / max(self.x1 - self.x0, 0.0001)            # ~1000 units across
        self.cx = math.cos(math.radians((self.y0 + self.y1) / 2))
        self.W = round((self.x1 - self.x0) * self.K * self.cx)
        self.H = round((self.y1 - self.y0) * self.K)
        self.P = {k: (v["lat"], v["lon"]) for k, v in m["points"].items()}

    def xy(self, lat, lon):
        return ((lon - self.x0) * self.K * self.cx, (self.y1 - lat) * self.K)

    def land(self):
        src = self.m.get("land")
        if not src:
            return ""
        rings = json.load(open(BASE / src))
        out = []
        for poly in rings:
            for ring in poly:
                pts = [self.xy(la, lo) for lo, la in ring]
                if len(pts) > 2:
                    out.append("M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
        return f'<path class="m-land" d="{" ".join(out)}"/>'

    def curve(self, a, b, bend):
        (x1, y1), (x2, y2) = self.xy(*self.P[a]), self.xy(*self.P[b])
        mx, my, dx, dy = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        cx, cy = mx - dy / L * bend, my + dx / L * bend
        return (f"M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}",
                (0.25 * x1 + 0.5 * cx + 0.25 * x2, 0.25 * y1 + 0.5 * cy + 0.25 * y2))

    def svg(self):
        m, W, H = self.m, self.W, self.H
        s = [f'<svg class="rmap-svg" viewBox="0 0 {W} {H}" role="img" aria-label="{e(m.get("aria", "Route map"))}">',
             f'<rect width="{W}" height="{H}" class="m-sea"/>']
        for i in range(max(4, H // 66)):
            y, x = 60 + i * 66, (i * 137) % 260
            s.append(f'<path class="m-wave" d="M{x},{y} q12,-8 24,0 t24,0 M{x + W * .45:.0f},{y + 28} q12,-8 24,0 t24,0"/>')
        s.append(self.land())
        for d in m.get("decor", []):
            x, y = self.xy(d["lat"], d["lon"])
            sc = d.get("scale", 1)
            if d["type"] == "peaks":
                s.append(f'<g transform="translate({x:.1f},{y:.1f}) scale({sc})" class="m-karst"><path d="M-30,0 C-29,-14 -25,-27 -18,-30 '
                         'C-12,-31 -9,-18 -8,0 Z M-6,0 C-6,-22 -1,-40 8,-42 C17,-42 19,-20 20,0 Z M18,0 C19,-10 23,-19 28,-19 C33,-18 33,-8 34,0 Z"/></g>')
            elif d["type"] == "flag":
                s.append(f'<g transform="translate({x:.1f},{y:.1f})" class="m-flag"><path d="M0,0 L0,-34" class="m-pole"/>'
                         '<path d="M0,-34 L22,-30 L18,-24 L22,-18 L0,-20 Z"/></g>')
            elif d["type"] == "plane":
                s.append(f'<g transform="translate({x:.1f},{y:.1f}) rotate(-30)" class="m-plane"><path d="M-16,0 L16,0 M0,0 L-8,-11 '
                         'M0,0 L-8,11 M-13,0 L-17,-5 M-13,0 L-17,5"/></g>')
        mids = []
        for leg in m.get("legs", []):
            d, mid = self.curve(leg["from"], leg["to"], leg.get("bend", 0))
            cls = {"sea": "m-sealeg", "rail": "m-rail", "air": "m-air"}.get(leg.get("mode"), "m-road")
            s.append(f'<path class="{cls}" d="{d}"/>')
            if leg.get("mode") == "sea":
                mids.append(mid)
        for x, y in mids:
            s.append(f'<g transform="translate({x:.1f},{y:.1f})" class="m-boat"><path d="M-17,-2 C-10,5 10,5 17,-3 L13,6 L-12,6 Z"/>'
                     '<path d="M-5,-2 L-5,-12 L6,-12 L9,-2 Z" class="m-cab"/></g>')
        for k, v in m["points"].items():
            if v.get("kind", "place") == "place" and v.get("dot", True):
                x, y = self.xy(v["lat"], v["lon"])
                s.append(f'<circle class="m-pier" cx="{x:.1f}" cy="{y:.1f}" r="7"/>')
        for n, st in enumerate(m.get("stops", []), 1):
            x, y = self.xy(*self.P[st["point"]])
            s.append(f'<g transform="translate({x:.1f},{y:.1f})" class="m-pin"><path d="M0,0 C-6,-12 -18,-20 -18,-34 A18,18 0 1 1 18,-34 '
                     f'C18,-20 6,-12 0,0 Z"/><circle cy="-34" r="11" class="m-pin-in"/><text y="-29.5" text-anchor="middle" class="m-pin-n">{n}</text></g>')
        s.append('</svg>')
        return "".join(s)

    def html(self, max_h_mm=None):
        m, W, H = self.m, self.W, self.H
        L = []

        def pos(lat, lon, item, dx, dy):
            x, y = self.xy(lat, lon)
            v = f"left:{x / W * 100:.2f}%;top:{y / H * 100:.2f}%;--dx:{item.get('dx', dx)};--dy:{item.get('dy', dy)}"
            if item.get("dx_narrow") or item.get("dy_narrow"):
                v += f";--ndx:{item.get('dx_narrow', item.get('dx', dx))};--ndy:{item.get('dy_narrow', item.get('dy', dy))}"
            return v

        def hide(item):
            return " hide-narrow" if item.get("hide_narrow") else ""
        for n, st in enumerate(m.get("stops", []), 1):
            lat, lon = self.P[st["point"]]
            L.append(f'<span class="m-lab stop{hide(st)}" style="{pos(lat, lon, st, "-50%", "-260%")}">'
                     f'<b>{n}</b> {e(st["label"])} <i>{e(st.get("dates", ""))}</i></span>')
        for k, v in m["points"].items():
            if v.get("label"):
                L.append(f'<span class="m-lab place{hide(v)}" style="{pos(v["lat"], v["lon"], v, "12px", "-50%")}">{e(v["label"])}</span>')
        for t in m.get("texts", []):
            L.append(f'<span class="m-lab {e(t.get("kind", "sea"))}{hide(t)}" style="{pos(t["lat"], t["lon"], t, "-50%", "-50%")}">{e(t["text"])}</span>')
        legend = ('<div class="m-legend">'
                  + "".join(f'<span><svg width="30" height="8" aria-hidden="true"><path d="M0,4 H30" class="{c}"/></svg>{l}</span>'
                            for c, l, mode in (("m-sealeg", "Ferry", "sea"), ("m-road", "Road", "road"), ("m-rail", "Train", "rail"), ("m-air", "Flight", "air"))
                            if any(g.get("mode", "road") == mode for g in m.get("legs", [])))
                  + '<span><svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4" class="m-pier"/></svg>Pier, station or airport</span>'
                  + ('<span class="m-attr">Coastline © OpenStreetMap contributors</span>' if m.get("land") else "") + '</div>')
        size = f"aspect-ratio:{W}/{H}"
        if max_h_mm:                                   # PDF: cap the height so tall (portrait) regions still fit page 1
            size += f";width:min(100%,{max_h_mm * W / H:.1f}mm);margin-inline:auto"
        return f'<figure class="rmap"><div class="m-box" style="{size}">{self.svg()}{"".join(L)}</div>{legend}</figure>'


def route_map(bbox=None, max_h_mm=None):
    return Map(TRIP["map"], bbox).html(max_h_mm) if TRIP.get("map") else ""


# ================================================================== page sections
def journey():
    J = TRIP["journey"]
    stops, legs = J["stops"], J.get("legs", [])
    o = ['<ol class="journey">']
    if J.get("start"):
        o.append(f'<li class="j-end">{icon(J["start"].get("icon", "plane"))}<div><b>{e(J["start"]["title"])}</b><span>{e(J["start"].get("sub", ""))}</span></div></li>')
    for i, st in enumerate(stops):
        o.append(f'<li class="j-stop"><span class="j-dot" aria-hidden="true"></span><div class="j-body">'
                 f'<span class="j-n">Stop {i+1} of {len(stops)} · {e(st.get("nights", ""))}</span>'
                 f'<a class="j-place" href="#d{st.get("first_day", 1)}">{e(st["name"])}</a>'
                 f'<span class="j-meta">{e(st.get("dates", ""))} · {e(st.get("stay", ""))}</span>'
                 + (f'<a class="mini" href="{gmap(st["map_query"])}" target="_blank" rel="noopener">Open map</a>' if st.get("map_query") else "")
                 + '</div></li>')
        if i < len(legs):
            lg = legs[i]
            o.append(f'<li class="j-leg">{icon(lg.get("icon", "boat"))}<span><b>{e(lg["when"])}</b> {e(lg["what"])}'
                     f'{" · " + e(lg["duration"]) if lg.get("duration") else ""}</span></li>')
    if J.get("end"):
        o.append(f'<li class="j-end">{icon(J["end"].get("icon", "plane"))}<div><b>{e(J["end"]["title"])}</b><span>{e(J["end"].get("sub", ""))}</span></div></li>')
    o.append('</ol>')
    return "".join(o)


def row(r):
    key = r.get("key")
    meta = [e(x) for x in (r.get("loc"), r.get("who")) if x]
    m = f'<span class="r-meta">{" · ".join(meta)}</span>' if meta else ""
    head = (f'<time class="r-t">{e(r["time"])}</time><span class="r-b"><span class="r-a">'
            f'{KEY_MARK if key else ""}{e(r["act"])}</span>{m}</span>')
    cls = "row" + (" hl" if key else "")
    q = r.get("map", r.get("loc"))
    if r.get("note") or q:
        more = []
        if r.get("note"):
            more.append(f'<p class="r-note">{e(r["note"])}</p>')
        if q:
            more.append(f'<a class="btn" href="{gmap(q)}" target="_blank" rel="noopener">Open map</a>')
        return (f'<li class="{cls}" data-min="{to_min(r["time"])}"><details><summary>{head}'
                f'{icon("chev", "chev")}</summary><div class="r-more">{"".join(more)}</div></details></li>')
    return f'<li class="{cls}" data-min="{to_min(r["time"])}"><div class="r-plain">{head}</div></li>'


def option(op):
    meta = [e(x) for x in (op.get("time"), op.get("effort"), op.get("price")) if x]
    if op.get("rating"):
        meta.append("★ " + e(op["rating"]))
    acts = []
    if op.get("q"):
        acts.append(f'<a class="btn" href="{gmap(op["q"])}" target="_blank" rel="noopener">Open map</a>')
    if op.get("url"):
        acts.append(ext(op["url"], op.get("url_label", "Book")))
    return (f'<li class="opt{" pick" if op.get("pick") else ""}"><div class="o-h"><b>{e(op["name"])}</b>'
            f'{"<span class=o-flag>Our pick</span>" if op.get("pick") else ""}</div>'
            f'<p class="o-m">{" · ".join(meta)}</p><p class="o-t">{e(op.get("note", ""))}</p><div class="o-a">{"".join(acts)}</div></li>')


def opt_block(day_, heading=None):
    out = []
    for grp in day_.get("options", []):
        h = heading(grp["label"]) if heading else f'Options · {e(grp["label"])}'
        out.append(f'<div class="optblock"><p class="ob-h"><b>{h}</b><span>{len(grp["items"])} choices</span></p><ul class="opts">'
                   + "".join(option(op) for op in grp["items"]) + '</ul></div>')
    return "".join(out)


def place(pid):
    return PLACES[pid]


def spot(pid):
    x = place(pid)
    g = f' · ★ {x["rating"]}' if x.get("rating") else ""
    return (f'<li><a href="{gmap(x["q"])}" target="_blank" rel="noopener"><span class="s-n">{e(x["name"])}</span>'
            f'<span class="s-k">{e(x["type"])}{g}</span><span class="s-go">Open map</span></a></li>')


def day_label(d):
    wd, num = d["label"].split(" ")[:2]
    return wd, num


def day(i, d):
    wd, num = day_label(d)
    n = len(TRIP["days"])
    sleep = d.get("sleep") or "Flying home"
    o = [f'<article data-area="{e(d.get("area", ""))}" class="day{" bday" if d.get("badge") else ""}" id="d{i+1}" data-date="{d["date"]}" '
         f'data-ctx="Day {i+1} · {e(d["label"])} · {e(sleep.split(",")[0])}">',
         '<header class="d-head">',
         f'<div class="d-date"><span class="d-num">{num}</span><span class="d-wd">{WEEKDAYS.get(wd, wd)}<br>Day {i+1} of {n}</span></div><div class="d-tt">']
    if d.get("badge"):
        o.append(f'<p class="d-bday">{e(d["badge"])}</p>')
    o.append(f'<h3>{e(d["title"])}</h3><p class="d-sleep">{"Sleeping at " if d.get("sleep") else ""}<b>{e(sleep)}</b></p>'
             '<span class="d-today">Today</span></div></header>')
    if d.get("tip"):
        o.append(f'<p class="tip">{e(d["tip"])}</p>')
    o.append('<ol class="rows">' + "".join(row(r) for r in d["rows"]) + '</ol>')
    o.append(opt_block(d))
    if d.get("spots"):
        o.append(f'<details class="fold"><summary><span><b>Every address today</b> · {len(d["spots"])} places</span>'
                 f'{icon("chev", "chev")}</summary><ul class="spots">' + "".join(spot(s) for s in d["spots"]) + '</ul></details>')
    o.append('</article>')
    return "".join(o)


def entry(x):
    mine = x.get("source") == "list"
    bits = [f'<span class="who-{"mine" if mine else "ours"}">{"Your list" if mine else "Our pick"}</span>', e(x["type"])]
    for k in ("hours", "day"):
        if x.get(k):
            bits.append(e(x[k]))
    rate = f'<span class="e-r"><b>★ {e(x["rating"])}</b> {e(x.get("reviews", ""))}</span>' if x.get("rating") else ""
    return (f'<li class="entry" data-area="{e(x["area"])}"><div class="e-h"><span class="e-n">{e(x["name"])}</span>{rate}</div>'
            f'<p class="e-k">{" · ".join(bits)}</p><p class="e-w">{e(x.get("what", ""))}</p>'
            f'<div class="e-a"><a class="btn" href="{gmap(x["q"])}" target="_blank" rel="noopener">Open map</a>'
            f'<button class="btn tick" type="button" data-id="{e(x["id"])}" aria-pressed="false">'
            f'<span class="tk" aria-hidden="true"></span><span class="tk-t">Tick off</span></button></div></li>')


def listing(kind):
    items = [x for x in TRIP["places"] if x["kind"] == kind]
    o = []
    for a, label in TRIP["areas"].items():
        g = [x for x in items if x["area"] == a]
        if g:
            o.append(f'<section class="grp" data-scope="{kind}" data-area="{e(a)}"><h3 class="grp-h">{e(label)}<span>{len(g)}</span></h3>'
                     '<ul class="entries">' + "".join(entry(x) for x in g) + '</ul></section>')
    return "".join(o)


def accordion(id_, title, sub, lis):
    return (f'<details class="acc" id="{id_}"><summary><span><b>{title}</b><small>{sub}</small></span>{icon("chev", "chev")}</summary>'
            f'<ul class="lg">{"".join(lis)}</ul></details>')


def page(local_fonts=False, standalone=False):
    T = TRIP
    o = []
    A = o.append
    head = (f'<title>{e(T["short_title"])}</title><meta name="claude:viewport-fit-sides" content="cover">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Mono:wght@400;500'
            '&family=Atkinson+Hyperlegible+Next:ital,wght@0,400;0,500;0,600;1,400&family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,600&display=swap">'
            + (font_faces() if local_fonts else "") + f"<style>{theme_css()}{CSS}{MAP_CSS}</style>")
    A(head)
    navs = [("today", "Today", "#today"), ("days", "Days", "#days"), ("explore", "Explore", "#explore"), ("info", "Info", "#info")]
    A(f'<header class="bar"><div class="wrap bar-in"><a class="mark" href="#today">{e(T["short_title"])}</a>'
      f'<span class="ctx" id="ctx" aria-live="polite"><b class="ctx-m">{e(T["short_title"])}</b><span class="ctx-x">{e(T.get("dates_label", ""))}</span></span>'
      '<nav class="topnav" aria-label="Sections">')
    for k, l, h in navs:
        A(f'<a href="{h}" data-nav="{k}" aria-current="{"true" if k == "today" else "false"}">{l}</a>')
    A(f'</nav><a class="exp" href="#explore" aria-label="Explore food, drinks and places" title="Explore food, drinks and places">{icon("explore")}<span>Explore</span></a>'
      '<a class="sos" href="#sos" aria-label="Emergency numbers">SOS</a>'
      f'<button class="theme" id="theme" type="button" data-moon=\'{icon("moon")}\' data-sun=\'{icon("sun")}\' '
      f'aria-label="Switch to night mode" title="Switch to night mode">{icon("moon")}</button></div><span class="progress" aria-hidden="true"></span></header>')
    A('<main><section id="today" data-sec="today" class="wrap" style="scroll-margin-top:calc(var(--safe-t) + var(--bar))">')
    A(f'<div class="hero"><div><p class="eyebrow">{e(T.get("eyebrow", ""))}</p><h1>{T["title_html"]}</h1></div>'
      f'<div><p class="hero-dek">{e(T.get("dek", ""))}</p><p class="crew">{" · ".join(e(p) for p in T.get("travellers", []))}</p>'
      '<nav class="jump" aria-label="Jump to Explore"><a href="#eat">Eat &amp; drink</a><a href="#places">Places</a>'
      '<a href="#options">Options</a><a href="#events">Events</a></nav></div></div>'
      f'<div class="hero-map">{route_map()}</div></section>')
    A('<div class="wrap"><div class="today"><section class="card" id="now" hidden aria-live="polite"><p class="eyebrow">Today</p><h2 id="now-h"></h2>'
      '<div class="now-grid"><div class="nn is-now"><span class="lbl"><span class="live" aria-hidden="true"></span>Now</span>'
      '<span class="v" id="nn-now"></span><span class="m" id="nn-now-m"></span></div>'
      '<div class="nn"><span class="lbl">Next</span><span class="v" id="nn-next"></span><span class="m" id="nn-next-m"></span></div></div>'
      '<div class="now-foot"><p id="now-sleep"></p><a class="btn" id="now-go" href="#d1">Open today&rsquo;s plan</a></div></section></div>')
    A('<section class="sec" aria-labelledby="route-h"><div class="sec-h"><h2 id="route-h">The route</h2><p>Tap a stop to jump to its days</p></div>'
      + journey() + '</section></div>')
    # days
    A('<section class="sec wrap" id="days" data-sec="days" aria-labelledby="days-h"><div class="sec-h"><h2 id="days-h">Day by day</h2>'
      '<p>Tap a line for notes and the map</p></div><div class="days-grid"><nav class="scrub" aria-label="Jump to a day"><ol>')
    for i, d in enumerate(T["days"]):
        wd, num = day_label(d)
        A(f'<li><a href="#d{i+1}" aria-current="{"true" if i == 0 else "false"}"><b>{num}</b><span>{wd}</span></a></li>')
    A('</ol></nav><div class="days">' + "".join(day(i, d) for i, d in enumerate(T["days"])) + '</div></div></section>')
    # explore
    A('<section class="sec wrap" id="explore" data-sec="explore" aria-labelledby="ex-h">'
      f'<div class="sec-h"><h2 id="ex-h">Explore</h2><p>{e(T.get("explore_note", "Your list, checked, plus well-rated picks"))}</p></div>'
      '<div class="seg" role="group" aria-label="Show"><button type="button" data-kind="eat" aria-pressed="true">Eat &amp; drink</button>'
      '<button type="button" data-kind="go" aria-pressed="false">Places</button><button type="button" data-kind="opt" aria-pressed="false">Options</button>'
      '<button type="button" data-kind="on" aria-pressed="false">Events</button></div>'
      '<div class="areas" id="areas" role="group" aria-label="Area"><button class="chip" type="button" data-area="all" aria-pressed="true">Everywhere</button>')
    for a, label in T["areas"].items():
        A(f'<button class="chip" type="button" data-area="{e(a)}" aria-pressed="false">{e(label)}</button>')
    A('</div><p class="count" id="count" aria-live="polite"></p>' + listing("eat") + listing("go") + '<div id="optall" hidden>')
    for i, d in enumerate(T["days"]):
        if d.get("options"):
            A(opt_block(d, lambda lab, d=d, i=i: f'Day {i+1} · {e(d["label"])} · {e(lab)}'))
    A('</div><ul class="ev" id="ev" hidden>')
    for ev in T.get("events", []):
        A(f'<li><span class="w">{e(ev["when"])}</span><b>{e(ev["name"])}</b><p>{e(ev.get("note", ""))}</p>'
          + (f'<a class="mini" href="{gmap(ev["where"])}" target="_blank" rel="noopener">Open map · {e(ev["where"])}</a>' if ev.get("where") else "") + '</li>')
    A('</ul>')
    if T.get("checked"):
        rows = [f'<li><span class="l {"ok" if c.get("verdict") == "Checked" else "warnw"}">{e(c.get("verdict", ""))}</span><span class="m">{e(c["item"])}'
                f'{wrap("small", c.get("finding"))}</span><span class="a" style="font-weight:400;color:var(--ink-3)">{e(c.get("where", ""))}</span></li>'
                for c in T["checked"]]
        A('<div class="acc-list checked"><details class="acc" id="list-check"><summary><span><b>Your list, checked</b>'
          f'<small>All {len(rows)} items you sent, what we found, and where each one went</small></span>{icon("chev", "chev")}</summary>'
          '<ul class="lg">' + "".join(rows) + '</ul></details></div>')
    A('</section>')
    # info
    A('<section class="sec wrap" id="info" data-sec="info" aria-labelledby="info-h">'
      f'<div class="sec-h"><h2 id="info-h">Info</h2><p>{e(T.get("researched", ""))}</p></div>'
      '<div id="sos" style="scroll-margin-top:calc(var(--safe-t) + var(--bar) + 16px)"><p class="eyebrow" style="margin-bottom:var(--s3)">Emergency</p><div class="sosgrid">')
    for k, s in enumerate(T.get("emergency", [])[:4]):
        A(f'<a class="sosc{" main" if k == 0 else ""}" href="tel:{e(s["number"])}"><span>{e(s["name"])}</span><b>{e(s["number"])}</b>'
          f'{wrap("span", s.get("note"))}</a>')
    A('</div>')
    if T.get("emergency_link"):
        L = T["emergency_link"]
        A(f'<p class="emb">{e(L["text"])} <a href="{e(L["url"])}" target="_blank" rel="noopener">{e(L.get("label", "Open website"))}</a></p>')
    A('</div><div class="info2"><div class="acc-list"><p class="eyebrow" style="padding-top:var(--s4)">Know-how</p>')
    for j, k in enumerate(T.get("know", [])):
        A(f'<details class="acc" id="know-{j+1}"><summary><span><b>{e(k["kicker"])}</b><small>{e(k["title"])}</small></span>{icon("chev", "chev")}</summary><dl>')
        A("".join(f'<div><dt>{e(h)}</dt><dd>{e(b)}</dd></div>' for h, b in k["items"]) + '</dl></details>')
    A('</div><div class="acc-list"><p class="eyebrow" style="padding-top:var(--s4)">Bookings</p>')
    for j, b in enumerate(T.get("bookings", [])):
        lis = []
        for r in b["rows"]:
            link = f'<a href="{e(r["url"])}" target="_blank" rel="noopener">{e(r.get("url_label", "Open"))}</a>' if r.get("url") else (
                f'<a href="{gmap(r["map"])}" target="_blank" rel="noopener">Open map</a>' if r.get("map") else "")
            status = f'<span class="ok">{e(r["status"])}</span>' if r.get("status") else link
            lis.append(f'<li><span class="l">{e(r.get("lead", ""))}</span><span class="m">{e(r["main"])}'
                       f'{wrap("small", r.get("small"))}</span><span class="a">{status}</span></li>')
        A(accordion(f"book-{j+1}", e(b["title"]), e(b.get("sub", "")), lis))
    A('</div></div>')
    A(f'<footer>{e(T.get("footer", ""))}</footer></section></main><nav class="tabbar" aria-label="Sections"><ul>')
    for k, l, h in navs:
        A(f'<li><a href="{h}" data-nav="{k}" aria-current="{"true" if k == "today" else "false"}">{icon(k)}<span>{l}</span></a></li>')
    first_area = next(iter(T["areas"]))
    js = (JS.replace("__KEY__", e(T.get("storage_key", "trip"))).replace("__START__", T["days"][0]["date"])
          .replace("__END__", T["days"][-1]["date"]).replace("__FIRSTAREA__", first_area)
          .replace("__TZ__", str(T.get("utc_offset_hours", 0))))
    A(f'</ul></nav><script>{js}</script>')
    body = "\n".join(o)
    if standalone:
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>'
                + body + '</body></html>')
    return body


def theme_css():
    t = TRIP.get("theme", {})
    if not t:
        return ""
    light = ";".join(f"--{k}:{v}" for k, v in t.get("light", {}).items())
    dark = ";".join(f"--{k}:{v}" for k, v in t.get("dark", {}).items())
    return (f":root{{{light}}}" if light else "") + (
        f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]){{{dark}}}}}:root[data-theme=\"dark\"]{{{dark}}}" if dark else "")


# ================================================================== the shareable PDF
def pick_rows(d, cap=7):
    rows = d["rows"]
    keep = [r for r in rows if r.get("key") or r.get("pdf")]
    if len(keep) < 4:
        keep = rows
    return keep[:cap]


def pdf_day(i, d):
    wd, num = day_label(d)
    title = d.get("pdf_title", d["title"])
    o = [f'<section class="day{" bday" if d.get("badge") else ""}"><div class="dh"><div class="num">{num}</div><div>'
         + (f'<span class="bd">{e(d["badge"])}</span><br>' if d.get("badge") else '')
         + f'<div class="wd">{e(wd)} · Day {i+1} of {len(TRIP["days"])}</div><div class="dt">{e(title)}</div>'
         f'<div class="sl">{e("Sleep · " + d["sleep"]) if d.get("sleep") else "Flying home"}</div></div></div><ul class="tl">']
    for r in pick_rows(d):
        label = e(r.get("pdf_act", r["act"]))
        q = r.get("map", r.get("loc"))
        if q:
            label = f'<a href="{gmap(q)}">{label}</a>'
        o.append(f'<li><time>{e(r["time"])}</time><span>{"<i class=k></i>" if r.get("key") else ""}{label}</span></li>')
    o.append('</ul>')

    def links(xs):
        return ", ".join(f'<a href="{gmap(x["q"])}">{e(x["name"])}</a>' + (f' {e(x["rating"])}★' if x.get("rating") else "") for x in xs)
    spots = [place(s) for s in d.get("spots", [])]
    eats, goes = [x for x in spots if x["kind"] == "eat"], [x for x in spots if x["kind"] == "go"]
    if eats:
        o.append(f'<p class="tag"><b>Eat &amp; drink</b>{links(eats)}</p>')
    if goes:
        o.append(f'<p class="tag"><b>Go</b>{links(goes)}</p>')
    ops = [op for g in d.get("options", []) for op in g["items"]][:5]
    if ops:
        o.append('<p class="tag"><b>Options</b>' + ", ".join(f'<a href="{e(op.get("url") or gmap(op.get("q") or op["name"]))}">{e(op["name"])}</a>' for op in ops) + '</p>')
    elif d.get("book"):
        o.append('<p class="tag"><b>Book</b>' + ", ".join(f'<a href="{e(b["url"])}">{e(b["label"])}</a>' for b in d["book"]) + '</p>')
    if d.get("tip"):
        o.append(f'<p class="tip">{e(d["tip"])}</p>')
    o.append('</section>')
    return "".join(o)


def pdf_html():
    T, P = TRIP, TRIP.get("pdf", {})
    o = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(T["short_title"])} summary</title>'
         + font_faces() + f'<style>{theme_css()}{MAP_CSS}{PDF_CSS}</style></head><body>']
    stops = T["journey"]["stops"]
    o.append(f'<section class="pg"><div class="top"><div><p class="eyebrow">Trip summary · {e(T.get("dates_label", ""))}</p>'
             f'<h1>{T["title_html"]}</h1><p class="crew">{" · ".join(e(p) for p in T.get("travellers", []))}'
             f'{" · " + e(P["facts"]) if P.get("facts") else ""}</p></div>'
             f'<div class="stamp"><div class="stamp-in">{scene()}<b>{e(P.get("stamp_title", T["short_title"]))}</b><i>{e(P.get("stamp_note", ""))}</i></div></div></div>')
    bbox = P.get("map_bbox")
    o.append(route_map(bbox, P.get("map_max_height_mm", 110)) + f'<div class="stops" style="grid-template-columns:repeat({min(len(stops), 4)},1fr)">')
    for n, st in enumerate(stops, 1):
        o.append(f'<a class="stop" href="{gmap(st.get("map_query", st["name"]))}"><span class="n"><b>{n}</b>{e(st.get("nights", ""))}</span>'
                 f'<span class="p">{e(st.get("short", st["name"]))}</span><span class="d">{e(st.get("dates", ""))}</span><span class="d">{e(st.get("stay", ""))} ↗</span></a>')
    o.append('</div>')
    sos = '<div class="sos">' + "".join(f'<div class="{"main" if k == 0 else ""}">{e(s["name"])}<b>{e(s["number"])}</b></div>'
                                        for k, s in enumerate(T.get("emergency", [])[:4])) + '</div>'
    left = "".join(f'<div><span class="w">{e(t["when"])}</span><span>{e(t["main"])}{wrap("small", t.get("small"))}</span></div>'
                   for t in P.get("transport", []))
    right = "".join(f'<li><span class="hw">{e(h["when"])}</span><b><a href="{gmap(h["q"])}" style="color:var(--ink)">{e(h["name"])}</a></b><br>{e(h.get("note", ""))}</li>'
                    for h in P.get("handy", []))
    boxes = []
    if left:
        boxes.append(f'<div class="box"><h2>Getting there and between</h2><div class="tbl">{left}</div></div>')
    boxes.append('<div class="box">' + (f'<h2>Options to keep handy</h2><ul class="pf">{right}</ul>' if right else '<h2>Emergency</h2>') + sos + '</div>')
    o.append(f'<div class="cols"{" style=grid-template-columns:1fr" if len(boxes) == 1 else ""}>{"".join(boxes)}</div>')
    if T.get("live_url"):
        o.append(f'<div class="live"><span><b style="color:#fff">Live guide</b> · Now/Next, every address, tick-offs, know-how</span>'
                 f'<a href="{e(T["live_url"])}">Open the live guide</a></div>')
    o.append('</section>')
    days = T["days"]
    for start in range(0, len(days), 4):
        chunk = list(range(start, min(start + 4, len(days))))
        title = P.get("day_page_titles", {}).get(str(start // 4), f"Days {chunk[0]+1}–{chunk[-1]+1}")
        o.append(f'<section class="pg"><div class="ph"><h2>{e(title)}</h2><p>Tap any underlined place for Google Maps · ◆ key moment</p></div><div class="grid">')
        o.extend(pdf_day(i, days[i]) for i in chunk)
        o.append(f'</div><div class="foot"><span>{e(T["short_title"])} · {e(T.get("dates_label", ""))}</span>'
                 + (f'<a href="{e(T["live_url"])}">Full plan and options in the live guide ↗</a>' if T.get("live_url") else "<span></span>") + '</div></section>')
    o.append('</body></html>')
    return "".join(o)


# ================================================================== fonts
FONT_FILES = {
    ("Atkinson Hyperlegible Next", 400, "normal"): "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-400-normal.woff2",
    ("Atkinson Hyperlegible Next", 500, "normal"): "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-500-normal.woff2",
    ("Atkinson Hyperlegible Next", 600, "normal"): "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-600-normal.woff2",
    ("Atkinson Hyperlegible Next", 400, "italic"): "@fontsource/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-400-italic.woff2",
    ("Atkinson Hyperlegible Mono", 400, "normal"): "@fontsource/atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-400-normal.woff2",
    ("Atkinson Hyperlegible Mono", 500, "normal"): "@fontsource/atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-500-normal.woff2",
    ("Bricolage Grotesque", "200 800", "normal"): "@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-wdth-normal.woff2",
}


def font_faces():
    root = FONT_DIR / "node_modules"
    out = []
    for (fam, w, st), rel in FONT_FILES.items():
        p = root / rel
        if p.exists():
            extra = ";font-stretch:75% 100%" if fam.startswith("Bricolage") else ""
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:{st}{extra};src:url({p.as_uri()})}}")
    return f"<style>{''.join(out)}</style>" if out else ""


def cmd_fonts():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    if not (FONT_DIR / "package.json").exists():
        (FONT_DIR / "package.json").write_text('{"name":"itinerary-kit-fonts","private":true}')
    subprocess.run(["npm", "i", "--silent", "@fontsource/atkinson-hyperlegible-next", "@fontsource/atkinson-hyperlegible-mono",
                    "@fontsource-variable/bricolage-grotesque"], cwd=FONT_DIR, check=True)
    print("fonts cached in", FONT_DIR)


# ================================================================== commands
def load(path):
    global TRIP, BASE, PLACES
    BASE = Path(path).resolve().parent
    TRIP = json.load(open(path))
    PLACES = {x["id"]: x for x in TRIP.get("places", [])}
    missing = [s for d in TRIP["days"] for s in d.get("spots", []) if s not in PLACES]
    if missing:
        sys.exit(f"days reference unknown place ids: {sorted(set(missing))}")


def cmd_build(out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "artifact.html").write_text(page())                                  # for Claude's Artifact tool (no doctype)
    (out / "page.html").write_text(page(standalone=True))                       # opens anywhere
    (out / "page.local.html").write_text(page(local_fonts=True, standalone=True))  # for local screenshots
    (out / "summary.html").write_text(pdf_html())
    print("built", out / "artifact.html", out / "page.html", out / "summary.html")


def cmd_render(out):
    from playwright.sync_api import sync_playwright
    slug = TRIP.get("file_slug", "trip")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=2)
        pg.goto((out / "summary.html").resolve().as_uri())
        pg.wait_for_timeout(800)
        over = pg.evaluate("""()=>[...document.querySelectorAll('.pg,.day,.box,.cols')].filter(d=>d.scrollHeight>d.clientHeight+1)
                               .map(d=>d.className+' +'+(d.scrollHeight-d.clientHeight)+'px: '+((d.querySelector('.num,h2')||{}).textContent||''))""")
        pg.pdf(path=str(out / f"{slug}-summary.pdf"), format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        for i, el in enumerate(pg.query_selector_all(".pg")):
            el.screenshot(path=str(out / f"{slug}-page{i+1}.png"))
        b.close()
    print("rendered", out / f"{slug}-summary.pdf")
    if over:
        print("PDF OVERFLOW - trim rows/options or shorten text:", *over, sep="\n  ")
    try:
        from pypdf import PdfReader
        r = PdfReader(str(out / f"{slug}-summary.pdf"))
        print("pdf pages:", len(r.pages), "links:", sum(len(pp.get("/Annots", [])) for pp in r.pages))
    except ImportError:
        pass


AUDIT = """()=>{const W=document.documentElement.clientWidth;let mf=99,ws=new Set(),small=[];
for(const el of document.querySelectorAll('body *')){if(el.offsetParent===null&&getComputedStyle(el).position!=='fixed')continue;const cs=getComputedStyle(el);
 if([...el.childNodes].some(n=>n.nodeType==3&&n.textContent.trim())){mf=Math.min(mf,parseFloat(cs.fontSize));ws.add(cs.fontWeight)}
 if(el.matches('a,button,summary,label')){const r=el.getBoundingClientRect();if(r.width&&r.height&&r.height<43.5&&!el.closest('.r-note,.emb,.e-k'))small.push(el.className+':'+Math.round(r.height))}}
return {overflow:document.documentElement.scrollWidth>W,minFont:mf,weights:[...ws].sort(),smallTargets:[...new Set(small)].slice(0,8)}}"""


def cmd_check(out):
    from playwright.sync_api import sync_playwright
    ok = True
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, w, h, theme in (("phone", 390, 844, "light"), ("phone-dark", 390, 844, "dark"), ("desktop", 1280, 900, "light")):
            ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
            if theme == "dark":
                ctx.add_init_script(f"try{{localStorage.setItem('{TRIP.get('storage_key', 'trip')}-theme','dark')}}catch(e){{}}")
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda x: errs.append(str(x)))
            pg.goto((out / "page.local.html").resolve().as_uri())
            pg.wait_for_timeout(600)
            res = pg.evaluate(AUDIT)
            res["jsErrors"] = errs
            pg.screenshot(path=str(out / f"check-{name}.png"))
            bad = res["overflow"] or res["minFont"] < 12 or len(res["weights"]) > 3 or res["smallTargets"] or errs
            ok &= not bad
            print(("FAIL " if bad else "ok   ") + name, res)
            ctx.close()
        b.close()
    print("layout audit", "passed" if ok else "FAILED - see above; screenshots in", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build", "render", "check", "all", "fonts"])
    ap.add_argument("trip", nargs="?")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    if a.command == "fonts":
        return cmd_fonts()
    if not a.trip:
        ap.error("trip.json is required")
    load(a.trip)
    out = Path(a.out)
    if a.command in ("build", "all"):
        cmd_build(out)
    if a.command in ("render", "all"):
        cmd_render(out)
    if a.command in ("check", "all"):
        cmd_check(out)


# ================================================================== styles and script (generated from the reference build)
CSS = r'''
/* Layout: one continuous scroll - today, the route, eight days, explore, info - under glass chrome
   that always says where you are. Light by default for sun and crowds; night mode on request. */
:root{
  --bg:#F2F5F5; --surface:#FFFFFF; --surface-2:#E7EDEE; --ink:#0C1D26; --ink-2:#384A53; --ink-3:#54656D;
  --accent:#0A5C9E; --on-accent:#FFFFFF; --sun:#F4B33A; --on-sun:#2A1C00; --ok:#1D6A3A;
  --line:color-mix(in srgb,var(--ink) 11%,transparent); --line-2:color-mix(in srgb,var(--ink) 18%,transparent);
  --glass:color-mix(in srgb,var(--surface) 82%,transparent);
  --map-sea:#BFE0EA; --map-wave:color-mix(in srgb,#FFFFFF 55%,transparent); --map-land:#FFFFFF; --map-coast:#8DB8C6; --map-karst:#A9C4CB; --map-ink:#3E6C7C; --map-region:#9AB1B8;
  --sc1:#CFE2EA; --sc2:#F4EFE2; --sc3:#FFFDF5; --sc4:#A3BEC6; --sc5:#6B909C; --sc6:#2B5260; --sc7:#8CC0CC; --sc8:#3B7F91;
  --display:"Bricolage Grotesque","Avenir Next Condensed","Arial Narrow",system-ui,sans-serif;
  --body:"Atkinson Hyperlegible Next","Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"Atkinson Hyperlegible Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --t-meta:.75rem; --t-sec:.875rem; --t-body:1rem; --t1:1.2rem; --t2:1.44rem; --t3:1.728rem; --t4:2.074rem; --t5:2.488rem; --t6:2.986rem;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s6:24px; --s8:32px; --s12:48px; --s16:64px;
  --m100:100ms; --m150:150ms; --m200:200ms; --m300:300ms; --out:cubic-bezier(.16,1,.3,1);
  --bar:56px; --scrub:56px; --tabbar:64px;
  --safe-t:env(safe-area-inset-top,0px); --safe-b:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0A1317; --surface:#111D22; --surface-2:#1A282E; --ink:#E8F0F1; --ink-2:#B3C2C6; --ink-3:#8C9DA2;
  --accent:#86BFF2; --on-accent:#05121B; --sun:#F4B33A; --on-sun:#2A1C00; --ok:#7CD39B;
  --map-sea:#0E2732; --map-wave:color-mix(in srgb,#86BFF2 14%,transparent); --map-land:#1B2B31; --map-coast:#35525C; --map-karst:#2C434B; --map-ink:#7FA6B4; --map-region:#4F6970;
  --sc1:#0B1820; --sc2:#2A4351; --sc3:#E8E3D2; --sc4:#2E4A55; --sc5:#1B3440; --sc6:#08151B; --sc7:#163743; --sc8:#08161C;
  color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0A1317; --surface:#111D22; --surface-2:#1A282E; --ink:#E8F0F1; --ink-2:#B3C2C6; --ink-3:#8C9DA2;
  --accent:#86BFF2; --on-accent:#05121B; --sun:#F4B33A; --on-sun:#2A1C00; --ok:#7CD39B;
  --map-sea:#0E2732; --map-wave:color-mix(in srgb,#86BFF2 14%,transparent); --map-land:#1B2B31; --map-coast:#35525C; --map-karst:#2C434B; --map-ink:#7FA6B4; --map-region:#4F6970;
  --sc1:#0B1820; --sc2:#2A4351; --sc3:#E8E3D2; --sc4:#2E4A55; --sc5:#1B3440; --sc6:#08151B; --sc7:#163743; --sc8:#08161C;
  color-scheme:dark}

*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);font-size:var(--t-body);line-height:1.55;
  -webkit-font-smoothing:antialiased;padding-bottom:calc(var(--tabbar) + var(--safe-b) + var(--s6))}
body::before{content:"";position:fixed;inset:0 0 auto;height:var(--safe-t);z-index:30;background:var(--surface)}
a{color:var(--accent)}
h1,h2,h3{margin:0;text-wrap:balance}
p{margin:0}
ol,ul{margin:0;padding:0;list-style:none}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.wrap{width:100%;max-width:1180px;margin-inline:auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.eyebrow{font-size:var(--t-meta);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);font-weight:500;line-height:1.4}
.sec{padding-block:var(--s12) 0;scroll-margin-top:calc(var(--safe-t) + var(--bar))}
.sec-h{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:var(--s2) var(--s4);margin-bottom:var(--s6)}
.sec-h h2{font-family:var(--display);font-weight:600;font-size:var(--t4);line-height:1.1;letter-spacing:-.02em;font-stretch:90%}
.sec-h p{color:var(--ink-3);font-size:var(--t-sec)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--s2);min-height:44px;padding:0 var(--s4);
  border:1px solid var(--line-2);border-radius:10px;background:var(--surface);color:var(--ink);font:500 var(--t-sec)/1.2 var(--body);
  text-decoration:none;cursor:pointer;transition:border-color var(--m150) var(--out)}
.mini{display:inline-flex;align-items:center;min-height:44px;font-size:var(--t-sec);font-weight:500;text-decoration:none}
.ico{width:20px;height:20px;flex:none}

/* ---------- glass chrome */
.bar{position:sticky;top:var(--safe-t);z-index:20;background:var(--glass);border-bottom:1px solid var(--line);
  -webkit-backdrop-filter:blur(16px) saturate(1.6);backdrop-filter:blur(16px) saturate(1.6)}
.bar-in{display:flex;align-items:center;gap:var(--s2);height:var(--bar)}
.mark{font-family:var(--display);font-weight:600;font-size:var(--t1);letter-spacing:-.02em;color:var(--ink);text-decoration:none;
  display:inline-flex;align-items:center;min-height:44px;line-height:1.1}
.ctx{flex:1;min-width:0;font-size:var(--t-sec);color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3}
.ctx b{font-weight:500;color:var(--ink)}
.topnav{display:none}
.mark{display:none}
.ctx-x{display:none}
.ctx .ctx-m{font-family:var(--display);font-weight:600;font-size:var(--t1);letter-spacing:-.02em}
.jump{display:flex;flex-wrap:wrap;gap:var(--s2);margin-top:var(--s4)}
.jump a{display:inline-flex;align-items:center;min-height:44px;padding:0 var(--s4);border-radius:999px;border:1px solid var(--line-2);
  background:var(--surface);color:var(--ink);font-weight:500;font-size:var(--t-sec);text-decoration:none}
.exp{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 10px;border-radius:10px;border:1px solid var(--line-2);
  color:var(--ink);text-decoration:none;font-size:var(--t-sec);font-weight:500}
.exp .ico{width:18px;height:18px;color:var(--accent)}
@media (max-width:380px){.exp span{display:none}.exp{width:44px;justify-content:center;padding:0}}
.sos{display:inline-flex;align-items:center;min-height:44px;padding:0 var(--s3);border-radius:10px;font-weight:600;font-size:var(--t-sec);
  color:#FFFFFF;background:#B3261E;text-decoration:none;letter-spacing:.04em}
.theme{width:44px;height:44px;display:inline-grid;place-items:center;border:1px solid var(--line-2);border-radius:10px;background:transparent;color:var(--ink);cursor:pointer}
.progress{position:absolute;left:0;right:0;bottom:-1px;height:2px;background:var(--accent);transform-origin:0 50%;transform:scaleX(0)}
.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:20;background:var(--glass);border-top:1px solid var(--line);
  -webkit-backdrop-filter:blur(16px) saturate(1.6);backdrop-filter:blur(16px) saturate(1.6);
  padding:0 max(8px,env(safe-area-inset-right,0px)) var(--safe-b) max(8px,env(safe-area-inset-left,0px))}
.tabbar ul{display:grid;grid-template-columns:repeat(4,1fr);max-width:560px;margin-inline:auto}
.tabbar a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;height:var(--tabbar);
  color:var(--ink-3);text-decoration:none;font-size:var(--t-meta);font-weight:500;letter-spacing:.02em;line-height:1.2;position:relative}
.tabbar a[aria-current="true"]{color:var(--accent)}
.tabbar a::before{content:"";position:absolute;top:0;left:30%;right:30%;height:2px;border-radius:2px;background:var(--accent);
  transform:scaleX(0);transition:transform var(--m200) var(--out)}
.tabbar a[aria-current="true"]::before{transform:scaleX(1)}
.tabbar .ico{width:22px;height:22px}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){.bar,.tabbar{background:var(--surface)}}

/* ---------- hero */
.hero{padding-block:var(--s8) 0}
.hero h1{font-family:var(--display);font-weight:600;font-size:var(--t6);line-height:1.02;letter-spacing:-.035em;font-stretch:85%;
  margin-top:var(--s3);max-width:12ch}
.hero h1 em{font-style:normal;color:var(--accent)}
.hero-dek{margin-top:var(--s4);color:var(--ink-2);max-width:56ch}
.crew{margin-top:var(--s3);font-size:var(--t-sec);color:var(--ink-3)}
.hero-map{margin-top:var(--s6)}

/* ---------- today card */
.today{margin-top:var(--s8);display:grid;gap:var(--s4)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:var(--s6)}
.card h2{font-family:var(--display);font-weight:600;font-size:var(--t2);line-height:1.15;letter-spacing:-.01em;margin-top:var(--s1)}
.now-grid{display:grid;gap:var(--s4);margin-top:var(--s4)}
.nn{display:grid;gap:var(--s1);padding:var(--s4);border-radius:12px;background:var(--surface-2)}
.nn.is-now{background:color-mix(in srgb,var(--sun) 26%,var(--surface))}
.nn .lbl{display:flex;align-items:center;gap:var(--s2);font-size:var(--t-meta);letter-spacing:.1em;text-transform:uppercase;font-weight:600;color:var(--ink-2);line-height:1.4}
.nn .v{font-size:var(--t1);font-weight:500;line-height:1.3}
.nn .m{font-family:var(--mono);font-size:var(--t-sec);color:var(--ink-2)}
.live{width:8px;height:8px;border-radius:50%;background:#B3261E;animation:pulse 2s ease-in-out infinite}
@keyframes pulse{50%{opacity:.35}}
.now-foot{display:flex;flex-wrap:wrap;gap:var(--s2);margin-top:var(--s4);align-items:center}
.now-foot p{flex:1 1 220px;color:var(--ink-2);font-size:var(--t-sec)}
.pf{display:grid;gap:0;margin-top:var(--s4)}
.pf li{border-top:1px solid var(--line)}
.pf label{display:grid;grid-template-columns:28px minmax(0,1fr);gap:var(--s3);padding:var(--s4) 0;cursor:pointer}
.pf input{width:22px;height:22px;margin:2px 0 0;accent-color:var(--accent)}
.pf b{font-weight:600;display:block;line-height:1.35}
.pf span span{display:block;color:var(--ink-2);font-size:var(--t-sec);margin-top:var(--s1);line-height:1.55}
.pf input:checked + span b{text-decoration:line-through;text-decoration-color:var(--ink-3);color:var(--ink-3)}

/* ---------- journey */
.journey{position:relative;display:grid;gap:0;padding-left:28px}
.journey::before{content:"";position:absolute;left:9px;top:14px;bottom:14px;width:2px;background:var(--line-2)}
.journey::after{content:"";position:absolute;left:9px;top:14px;bottom:14px;width:2px;background:var(--accent);transform-origin:50% 0;transform:scaleY(1)}
.journey li{position:relative}
.j-end{display:flex;gap:var(--s3);align-items:flex-start;padding:var(--s3) 0;color:var(--ink-2);font-size:var(--t-sec)}
.j-end .ico{position:absolute;left:-29px;top:12px;background:var(--bg);padding:1px;width:22px;height:22px;color:var(--ink-2)}
.j-end b{display:block;color:var(--ink);font-weight:500;font-size:var(--t-body)}
.j-stop{padding:var(--s3) 0}
.j-dot{position:absolute;left:-26px;top:22px;width:16px;height:16px;border-radius:50%;background:var(--surface);border:3px solid var(--accent)}
.j-body{display:grid;gap:2px;padding:var(--s4);background:var(--surface);border:1px solid var(--line);border-radius:14px}
.j-n{font-size:var(--t-meta);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:500;line-height:1.4}
.j-place{font-family:var(--display);font-weight:600;font-size:var(--t3);line-height:1.1;letter-spacing:-.02em;color:var(--ink);
  text-decoration:none;font-stretch:90%;justify-self:start;display:inline-flex;align-items:center;min-height:44px}
.j-meta{color:var(--ink-2);font-size:var(--t-sec)}
.j-body .mini{justify-self:start;margin-bottom:-8px}
.j-leg{display:flex;gap:var(--s3);align-items:center;padding:var(--s2) 0 var(--s2) var(--s2);font-size:var(--t-sec);color:var(--ink-2)}
.j-leg .ico{position:absolute;left:-30px;background:var(--bg);color:var(--accent);padding:1px;width:22px;height:22px}
.j-leg b{font-family:var(--mono);font-weight:500;color:var(--ink)}

/* ---------- days */
.scrub{position:sticky;top:calc(var(--safe-t) + var(--bar));z-index:15;margin-inline:calc(-1 * max(16px,env(safe-area-inset-left,0px)));
  background:var(--glass);-webkit-backdrop-filter:blur(16px) saturate(1.6);backdrop-filter:blur(16px) saturate(1.6);border-bottom:1px solid var(--line)}
.scrub ol{display:flex;gap:var(--s1);overflow-x:auto;scrollbar-width:none;padding:6px max(16px,env(safe-area-inset-left,0px));scroll-snap-type:x proximity}
.scrub ol::-webkit-scrollbar{display:none}
.scrub a{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:48px;height:44px;border-radius:10px;
  text-decoration:none;color:var(--ink-2);scroll-snap-align:center;position:relative;transition:background-color var(--m150) var(--out)}
.scrub a b{font-family:var(--display);font-weight:600;font-size:var(--t1);line-height:1.1;color:var(--ink)}
.scrub a span{font-size:var(--t-meta);line-height:1.2}
.scrub a[aria-current="true"]{background:var(--ink);color:var(--bg)}
.scrub a[aria-current="true"] b{color:var(--bg)}
.scrub a.is-today::after{content:"";position:absolute;top:4px;right:6px;width:7px;height:7px;border-radius:50%;background:var(--sun)}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){.scrub{background:var(--surface)}}
.days{display:grid;grid-template-columns:minmax(0,1fr);gap:var(--s6);padding-top:var(--s6);min-width:0}
.day{min-width:0}
.day{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:var(--s6);
  scroll-margin-top:calc(var(--safe-t) + var(--bar) + var(--scrub) + var(--s2))}
.day.bday{border-color:color-mix(in srgb,var(--sun) 70%,transparent);box-shadow:inset 0 4px 0 var(--sun)}
.d-head{display:grid;grid-template-columns:auto minmax(0,1fr);gap:var(--s4);align-items:start}
.d-date{display:flex;flex-direction:column;align-items:flex-start}
.d-num{font-family:var(--display);font-weight:600;font-size:var(--t6);line-height:1;letter-spacing:-.04em;font-stretch:80%;
  font-variant-numeric:lining-nums tabular-nums;line-height:1.1}
.d-wd{font-size:var(--t-meta);color:var(--ink-3);line-height:1.4;letter-spacing:.04em}
.d-tt h3{font-family:var(--display);font-weight:600;font-size:var(--t2);line-height:1.15;letter-spacing:-.015em;font-stretch:92%}
.d-bday{font-size:var(--t-meta);letter-spacing:.12em;text-transform:uppercase;font-weight:600;color:var(--on-sun);
  background:var(--sun);display:inline-block;padding:2px 8px;border-radius:4px;margin-bottom:var(--s2);line-height:1.4}
.d-sleep{margin-top:var(--s2);font-size:var(--t-sec);color:var(--ink-3)}
.d-sleep b{font-weight:500;color:var(--ink-2)}
.d-today{display:none}
.day.today .d-today{display:inline-block;margin-top:var(--s2);font-size:var(--t-meta);font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--on-sun);background:var(--sun);padding:2px 8px;border-radius:4px;line-height:1.4}
.tip{margin-top:var(--s4);padding:var(--s3) var(--s4);border-radius:12px;background:var(--surface-2);font-size:var(--t-sec);color:var(--ink);line-height:1.55;max-width:70ch}
.rows{margin-top:var(--s4)}
.row{border-top:1px solid var(--line)}
.row summary,.r-plain{display:grid;grid-template-columns:48px minmax(0,1fr) 20px;gap:var(--s3);padding:10px 0;align-items:start;min-height:44px}
.r-plain{grid-template-columns:48px minmax(0,1fr)}
.row summary{cursor:pointer;list-style:none}
.row summary::-webkit-details-marker,.fold summary::-webkit-details-marker{display:none}
.r-t{font-family:var(--mono);font-size:var(--t-sec);color:var(--ink-3);padding-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap}
.r-b{display:grid;gap:2px;min-width:0}
.r-a{font-weight:500;line-height:1.4}
.r-meta{font-size:var(--t-sec);color:var(--ink-3);line-height:1.45}
.key{display:inline-block;width:8px;height:8px;background:var(--sun);transform:rotate(45deg) translateY(-2px);margin-right:var(--s2);border-radius:1px}
.row.hl .r-a{color:var(--ink)}
.chev{width:20px;height:20px;color:var(--ink-3);margin-top:2px;transition:transform var(--m200) var(--out)}
details[open] > summary .chev{transform:rotate(180deg)}
.r-more{display:grid;gap:var(--s3);justify-items:start;padding:0 0 var(--s4) calc(48px + var(--s3))}
.r-note{font-size:var(--t-sec);color:var(--ink-2);line-height:1.55;max-width:65ch}
.row.is-now{background:color-mix(in srgb,var(--sun) 18%,transparent);margin-inline:calc(-1 * var(--s3));padding-inline:var(--s3);border-radius:10px}
.fold{border-top:1px solid var(--line);margin-top:0}
.fold:first-of-type{margin-top:var(--s2)}
.fold summary{display:flex;align-items:center;justify-content:space-between;gap:var(--s3);min-height:52px;cursor:pointer;list-style:none;font-size:var(--t-sec);color:var(--ink-2)}
.fold summary b{color:var(--accent);font-weight:600}
.optblock{border-top:1px solid var(--line);padding-top:var(--s3);margin-top:var(--s1)}
.ob-h{display:flex;justify-content:space-between;align-items:baseline;gap:var(--s3);font-size:var(--t-sec);color:var(--ink-3);margin-bottom:var(--s3)}
.ob-h b{color:var(--accent);font-weight:600}
.opts{display:flex;gap:var(--s3);overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;padding-bottom:var(--s4);
  margin-inline:calc(-1 * var(--s6));padding-inline:var(--s6);scroll-padding-inline:var(--s6)}
.opts::-webkit-scrollbar{display:none}
.opts .opt{flex:0 0 min(84%,340px);scroll-snap-align:start;align-content:start}
.o-a{display:flex;flex-wrap:wrap;gap:var(--s2);margin-top:auto;padding-top:var(--s1)}
#optall .optblock{margin-top:var(--s6);border-top:0;padding-top:0}
#optall .opts{margin-inline:0;padding-inline:0;display:grid;grid-template-columns:minmax(0,1fr);overflow:visible}
#optall .opt{background:var(--surface)}
.opt{padding:var(--s4);border:1px solid var(--line);border-radius:12px;display:grid;gap:var(--s2);justify-items:start;background:var(--surface)}
.opt.pick{border-color:color-mix(in srgb,var(--accent) 45%,transparent)}
.o-h{display:flex;gap:var(--s2);align-items:baseline;flex-wrap:wrap}
.o-h b{font-weight:600}
.o-flag{font-size:var(--t-meta);font-weight:600;color:var(--accent);letter-spacing:.06em;text-transform:uppercase}
.o-m{font-size:var(--t-sec);color:var(--ink-3)}
.o-t{font-size:var(--t-sec);color:var(--ink-2)}
.spots{padding-bottom:var(--s3)}
.spots a{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:0 var(--s3);padding:var(--s3) 0;border-top:1px solid var(--line);text-decoration:none;min-height:44px}
.s-n{color:var(--ink);font-weight:500}
.s-k{grid-column:1;font-size:var(--t-sec);color:var(--ink-3)}
.s-go{grid-column:2;grid-row:1 / span 2;align-self:center;font-size:var(--t-sec);font-weight:500;color:var(--accent)}

/* ---------- explore */
.seg{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--s1);padding:var(--s1);background:var(--surface-2);border-radius:12px;max-width:520px}
.seg button{min-height:44px;border:0;border-radius:9px;background:transparent;color:var(--ink-2);font:500 var(--t-sec)/1.2 var(--body);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(12,29,38,.06)}
.areas{display:flex;gap:var(--s2);overflow-x:auto;scrollbar-width:none;margin:var(--s4) calc(-1 * max(16px,env(safe-area-inset-left,0px))) 0;
  padding:0 max(16px,env(safe-area-inset-left,0px)) var(--s1)}
.areas::-webkit-scrollbar{display:none}
.chip{flex:none;min-height:44px;padding:0 var(--s4);border:1px solid var(--line-2);border-radius:999px;background:var(--surface);
  color:var(--ink-2);font:500 var(--t-sec)/1.2 var(--body);cursor:pointer;white-space:nowrap}
.chip[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.count{margin-top:var(--s3);font-size:var(--t-sec);color:var(--ink-3)}
.grp{margin-top:var(--s6)}
.grp-h{display:flex;align-items:baseline;gap:var(--s2);font-family:var(--display);font-weight:600;font-size:var(--t2);line-height:1.15;
  letter-spacing:-.015em;font-stretch:92%;margin-bottom:var(--s3)}
.grp-h span{font-family:var(--mono);font-size:var(--t-sec);font-weight:400;color:var(--ink-3)}
.entries{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.entry{padding:var(--s4);border-top:1px solid var(--line);display:grid;gap:var(--s1)}
.entry:first-child{border-top:0}
.e-h{display:flex;justify-content:space-between;gap:var(--s3);align-items:baseline}
.e-n{font-weight:600;font-size:var(--t-body);line-height:1.35}
.e-r{flex:none;font-family:var(--mono);font-size:var(--t-meta);color:var(--ink-3);white-space:nowrap}
.e-r b{font-weight:500;color:var(--ink);font-size:var(--t-sec)}
.e-k{font-size:var(--t-sec);color:var(--ink-3);line-height:1.45}
.who-mine{color:var(--accent);font-weight:500}
.who-ours{color:var(--ink-2);font-weight:500}
.e-w{font-size:var(--t-sec);color:var(--ink-2);line-height:1.55;max-width:65ch}
.e-a{display:flex;gap:var(--s2);margin-top:var(--s2);flex-wrap:wrap}
.tk{width:14px;height:14px;border-radius:50%;border:1.5px solid currentColor}
.tick[aria-pressed="true"]{background:var(--ok);border-color:var(--ok);color:var(--surface)}
.tick[aria-pressed="true"] .tk{background:currentColor}
.entry.done .e-n{color:var(--ink-3)}
.ev{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-top:var(--s6)}
.ev li{padding:var(--s4);border-top:1px solid var(--line);display:grid;gap:var(--s1)}
.ev li:first-child{border-top:0}
.ev .w{font-family:var(--mono);font-size:var(--t-sec);color:var(--accent)}
.ev b{font-weight:600}
.ev p{font-size:var(--t-sec);color:var(--ink-2)}
.ev .mini{justify-self:start}
.checked{margin-top:var(--s8)}

/* ---------- info */
.sosgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--s3)}
.sosc{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:var(--s4);display:grid;gap:2px;text-decoration:none;color:var(--ink)}
.sosc b{font-family:var(--mono);font-weight:500;font-size:var(--t4);line-height:1.1;letter-spacing:-.02em;user-select:all}
.sosc span{font-size:var(--t-sec);color:var(--ink-2);line-height:1.4}
.sosc.main{border-color:color-mix(in srgb,#B3261E 45%,transparent)}
.sosc.main b{color:#B3261E}
.emb{margin-top:var(--s3);font-size:var(--t-sec);color:var(--ink-2)}
.acc-list{margin-top:var(--s8);background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:0 var(--s4)}
.acc{border-top:1px solid var(--line)}
.acc:first-child{border-top:0}
.acc > summary{display:flex;align-items:center;justify-content:space-between;gap:var(--s3);min-height:60px;cursor:pointer;list-style:none}
.acc > summary::-webkit-details-marker{display:none}
.acc > summary span{display:grid;line-height:1.3}
.acc > summary b{font-weight:600}
.acc > summary small{font-size:var(--t-sec);color:var(--ink-3);margin-top:2px}
.acc dl{margin:0;padding-bottom:var(--s4);display:grid;gap:var(--s3)}
.acc dt{font-weight:600;font-size:var(--t-sec)}
.acc dd{margin:2px 0 0;font-size:var(--t-sec);color:var(--ink-2);line-height:1.55;max-width:70ch}
.lg{padding-bottom:var(--s4)}
.lg li{display:grid;grid-template-columns:76px minmax(0,1fr) auto;gap:var(--s3);padding:var(--s3) 0;border-top:1px solid var(--line);align-items:baseline}
.lg li:first-child{border-top:0}
.lg .l{font-family:var(--mono);font-size:var(--t-sec);color:var(--ink-3)}
.lg .m{font-size:var(--t-sec);line-height:1.5;min-width:0}
.lg .m small{display:block;color:var(--ink-3);font-size:var(--t-sec)}
.lg .a{font-size:var(--t-sec);font-weight:500}
.lg .a a{display:inline-flex;align-items:center;min-height:44px;text-decoration:none}
.ok{color:var(--ok)}
.warnw{color:var(--accent)}
footer{margin-top:var(--s12);padding-block:var(--s6);border-top:1px solid var(--line);font-size:var(--t-meta);color:var(--ink-3);line-height:1.5;max-width:75ch}

/* ---------- wide */
@media (min-width:768px){
  :root{--tabbar:0px}
  .tabbar{display:none}
  .topnav{display:flex;gap:var(--s1)}
  .exp{display:none}
  .mark{display:inline-flex}
  .ctx .ctx-m,.ctx .ctx-d{display:none}
  .ctx .ctx-x{display:inline}
  .topnav a{display:inline-flex;align-items:center;min-height:44px;padding:0 var(--s3);border-radius:10px;color:var(--ink-2);text-decoration:none;font-size:var(--t-sec);font-weight:500}
  .topnav a[aria-current="true"]{color:var(--ink);background:var(--surface-2)}
  .hero{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:var(--s8);align-items:end}
  .hero h1{font-size:4.3rem}
  .hero-map{grid-column:1 / -1}
  .top2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s8);align-items:start}
  .top2 .sec{padding-top:var(--s8)}
  .days-grid{display:grid;grid-template-columns:120px minmax(0,1fr);gap:var(--s8);align-items:start}
  .scrub{top:calc(var(--safe-t) + var(--bar) + var(--s6));margin:var(--s6) 0 0;background:transparent;border:0;-webkit-backdrop-filter:none;backdrop-filter:none}
  .scrub ol{flex-direction:column;padding:0;overflow:visible}
  .scrub a{flex-direction:row;justify-content:flex-start;gap:var(--s3);padding:0 var(--s3);height:48px;width:100%}
  .day{scroll-margin-top:calc(var(--safe-t) + var(--bar) + var(--s6));padding:var(--s8)}
  .opts{margin-inline:0;padding-inline:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));overflow:visible}
  #optall .opts{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
  .journey{max-width:760px}
  .entries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}
  .entry{border-top:1px solid var(--line);border-left:1px solid var(--line)}
  .entry:nth-child(-n+2){border-top:0}
  .entry:nth-child(odd){border-left:0}
  .sosgrid{grid-template-columns:repeat(4,minmax(0,1fr))}
  .info2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--s6);align-items:start}
  .info2 .acc-list{margin-top:var(--s8)}
}
@media (hover:hover){
  .btn:hover,.chip:hover{border-color:var(--ink-3)}
  .scrub a:not([aria-current="true"]):hover,.topnav a:hover{background:var(--surface-2)}
}

/* ---------- scroll-driven motion (progressive; the page is complete without it) */
@media (prefers-reduced-motion:no-preference){
  @supports (animation-timeline:scroll()){
    .progress{animation:grow linear both;animation-timeline:scroll(root)}
    @keyframes grow{to{transform:scaleX(1)}}
    .journey::after{transform:scaleY(0);animation:draw linear both;animation-timeline:view();animation-range:entry 20% cover 60%}
    @keyframes draw{to{transform:scaleY(1)}}
    .day,.entries,.j-body,.card{animation:rise linear both;animation-timeline:view();animation-range:entry 0% entry 35%}
    @keyframes rise{from{opacity:.6;transform:translateY(16px)}to{opacity:1;transform:none}}
  }
}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .live{animation:none}
  .chev,.tabbar a::before,.scrub a,.btn{transition:none}
}
'''
MAP_CSS = r'''.rmap{margin:0}
.m-box{position:relative;width:100%;max-width:100%;border-radius:18px;overflow:hidden;border:1px solid var(--line)}
.rmap-svg{display:block;width:100%;height:100%}
.m-sea{fill:var(--map-sea)}
.m-wave{fill:none;stroke:var(--map-wave);stroke-width:2.2;stroke-linecap:round}
.m-land{fill:var(--map-land);stroke:var(--map-coast);stroke-width:1.6;stroke-linejoin:round}
.m-karst{fill:var(--map-karst)}
.m-road{fill:none;stroke:var(--ink-2);stroke-width:3.2;stroke-linecap:round;opacity:.75}
.m-rail{fill:none;stroke:var(--ink-2);stroke-width:3.2;stroke-dasharray:14 6;opacity:.8}
.m-air{fill:none;stroke:var(--ink);stroke-width:2.4;stroke-dasharray:2 9;stroke-linecap:round;opacity:.8}
.m-sealeg{fill:none;stroke:var(--accent);stroke-width:4;stroke-dasharray:3 11;stroke-linecap:round}
.m-boat{fill:var(--accent)}
.m-boat .m-cab{fill:var(--map-land);stroke:var(--accent);stroke-width:2.5}
.m-plane{fill:none;stroke:var(--ink);stroke-width:4;stroke-linecap:round}
.m-flag{fill:var(--ink)}
.m-pole{stroke:var(--ink);stroke-width:2.5}
.m-pier{fill:var(--map-land);stroke:var(--ink);stroke-width:3}
.m-pin path{fill:var(--accent)}
.m-pin-in{fill:var(--map-land)}
.m-pin-n{font:600 15px var(--body);fill:var(--accent)}
.m-lab{position:absolute;white-space:nowrap;line-height:1.2;pointer-events:none;transform:translate(var(--dx),var(--dy))}
.m-lab.stop{display:inline-flex;align-items:center;gap:6px;padding:5px 9px 5px 5px;border-radius:8px;background:var(--surface);
  border:1px solid var(--line-2);font-weight:600;font-size:var(--t-sec);color:var(--ink);box-shadow:0 1px 3px rgba(12,29,38,.07)}
.m-lab.stop b{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;background:var(--accent);color:var(--on-accent);font-size:var(--t-meta);font-weight:600}
.m-lab.stop i{font-style:normal;font-family:var(--mono);font-weight:400;color:var(--ink-3);font-size:var(--t-meta)}
.m-lab.place{font-size:var(--t-meta);font-weight:500;color:var(--ink-2)}
.m-lab.sea{font-size:var(--t-sec);font-style:italic;color:var(--map-ink)}
.m-lab.region{font-family:var(--display);font-weight:600;font-size:var(--t1);letter-spacing:.2em;color:var(--map-region)}
.m-legend{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s6);margin-top:var(--s3);font-size:var(--t-sec);color:var(--ink-3)}
.m-legend span{display:inline-flex;align-items:center;gap:var(--s2)}
.m-legend .m-attr{margin-left:auto;font-size:var(--t-meta)}
@media (max-width:767.98px){
  .m-lab{transform:translate(var(--ndx,var(--dx)),var(--ndy,var(--dy)))}
  .m-lab.stop{font-size:var(--t-meta);padding:3px 7px 3px 3px}
  .m-lab.stop b{width:18px;height:18px}
  .m-lab.place,.m-lab.region,.m-lab.hide-narrow{display:none}
}
'''
PDF_CSS = r'''
:root{--bg:#F4F7F7;--surface:#FFFFFF;--surface-2:#E8EEEF;--ink:#0C1D26;--ink-2:#384A53;--ink-3:#54656D;--accent:#0A5C9E;--on-accent:#fff;
  --sun:#F4B33A;--on-sun:#2A1C00;--line:rgba(12,29,38,.12);--line-2:rgba(12,29,38,.2);
  --map-sea:#BFE0EA;--map-wave:rgba(255,255,255,.55);--map-land:#FFFFFF;--map-coast:#8DB8C6;--map-karst:#A9C4CB;--map-ink:#3E6C7C;--map-region:#9AB1B8;
  --sc1:#CFE2EA;--sc2:#F4EFE2;--sc3:#FFFDF5;--sc4:#A3BEC6;--sc5:#6B909C;--sc6:#2B5260;--sc7:#8CC0CC;--sc8:#3B7F91;
  --display:"Bricolage Grotesque",sans-serif;--body:"Atkinson Hyperlegible Next",sans-serif;--mono:"Atkinson Hyperlegible Mono",monospace;
  --t-meta:11px;--t-sec:12.5px;--t1:16px;--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s6:24px}
@page{size:A4;margin:0}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);-webkit-print-color-adjust:exact;print-color-adjust:exact}
a{color:var(--accent);text-decoration:none}
p,h1,h2,h3{margin:0}
.pg{width:210mm;height:297mm;padding:11mm 12mm 9mm;overflow:hidden;position:relative;page-break-after:always;display:flex;flex-direction:column;gap:4mm}
.pg:last-child{page-break-after:auto}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:6mm}
.eyebrow{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
h1{margin:2mm 0 0;font-family:var(--display);font-weight:600;font-size:40px;line-height:1;letter-spacing:-.035em;font-stretch:85%}
h1 em{font-style:normal;color:var(--accent)}
.crew{margin-top:2mm;font-size:12px;color:var(--ink-2)}
.stamp{flex:none;width:30mm;height:36mm;padding:2mm;background:#fff;transform:rotate(4deg);border:1.6px dashed #9AB1B8;box-shadow:0 1px 4px rgba(12,29,38,.08)}
.stamp-in{width:100%;height:100%;position:relative;overflow:hidden;border:1px solid var(--line)}
.stamp-in svg{width:100%;height:100%;display:block}
.stamp-in b{position:absolute;left:2mm;top:1.5mm;font-family:var(--display);font-size:13px;color:var(--ink);font-weight:600}
.stamp-in i{position:absolute;right:2mm;bottom:1.5mm;font-style:normal;font-family:var(--mono);font-size:9px;color:#fff}
.m-box{border-radius:12px}
.m-lab.stop{font-size:11.5px}
.m-lab.place{font-size:10px}
.m-lab.sea{font-size:11px}
.m-lab.region{font-size:13px}
.m-legend{font-size:11px;margin-top:2mm}
.stops{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm}
.stop{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:2.4mm 3mm;display:grid;gap:1px}
.stop .n{display:flex;gap:6px;align-items:center;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.stop .n b{display:inline-grid;place-items:center;width:17px;height:17px;border-radius:50%;background:var(--accent);color:#fff;font-size:10px;letter-spacing:0}
.stop .p{font-family:var(--display);font-weight:600;font-size:18px;line-height:1.1;font-stretch:90%;color:var(--ink)}
.stop .d{font-size:11px;color:var(--ink-2)}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:4mm;flex:1;min-height:0}
.box{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:3.5mm}
.box h2{margin:0 0 2mm;font-family:var(--display);font-weight:600;font-size:15px;line-height:1.15}
.tbl{display:grid;gap:0;font-size:11.5px}
.tbl div{display:grid;grid-template-columns:15mm 1fr;gap:2mm;padding:1.4mm 0;border-top:1px solid var(--line);line-height:1.35}
.tbl div:first-child{border-top:0}
.tbl .w{font-family:var(--mono);color:var(--ink-3);font-size:10.5px}
.tbl small{display:block;color:var(--ink-3);font-size:10.5px}
.pf{margin:0;padding:0;list-style:none;font-size:11.5px;line-height:1.35}
.pf li{padding:1.4mm 0;border-top:1px solid var(--line)}
.pf li:first-child{border-top:0}
.pf b{font-weight:600}
.hw{float:right;font-family:var(--mono);font-size:10px;color:var(--accent);margin-left:2mm}
.sos{display:grid;grid-template-columns:repeat(4,1fr);gap:1.6mm;margin-top:2.5mm}
.sos div{border:1px solid var(--line);border-radius:8px;padding:2mm 2.5mm;font-size:10.5px;color:var(--ink-2)}
.sos div{padding:1.6mm 2mm!important;font-size:9.5px!important}
.sos div b{display:block;font-family:var(--mono);font-weight:500;font-size:16px;color:var(--ink);line-height:1.1}
.sos div.main b{color:#B3261E}
.live{display:flex;justify-content:space-between;align-items:center;gap:4mm;padding:3mm 4mm;border-radius:10px;background:var(--ink);color:#fff;font-size:12px}
.live a{color:#fff;font-weight:600;border:1px solid rgba(255,255,255,.5);border-radius:8px;padding:1.6mm 3mm;white-space:nowrap}
.live span{color:#C9D6DA}
/* day pages */
.ph{display:flex;justify-content:space-between;align-items:baseline}
.ph h2{margin:0;font-family:var(--display);font-weight:600;font-size:26px;letter-spacing:-.02em;font-stretch:88%}
.ph p{margin:0;font-size:11px;color:var(--ink-3)}
.grid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:4mm;flex:1;min-height:0}
.day{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:4mm;display:flex;flex-direction:column;gap:2.2mm;overflow:hidden;position:relative}
.day.bday{box-shadow:inset 0 3px 0 var(--sun);border-color:rgba(244,179,58,.7)}
.dh{display:grid;grid-template-columns:auto 1fr;gap:3mm;align-items:start}
.num{font-family:var(--display);font-weight:600;font-size:40px;line-height:.95;letter-spacing:-.04em;font-stretch:80%}
.wd{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.dt{font-family:var(--display);font-weight:600;font-size:15.5px;line-height:1.15;margin-top:1px}
.sl{font-size:10.5px;color:var(--ink-3);margin-top:2px}
.bd{display:inline-block;background:var(--sun);color:var(--on-sun);font-size:9.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:1px 6px;border-radius:3px;margin-bottom:2px}
.tl{margin:0;padding:0;list-style:none;font-size:11.2px;line-height:1.32}
.tl li{display:grid;grid-template-columns:10.5mm 1fr;gap:2mm;padding:1.1mm 0;border-top:1px solid var(--line)}
.tl li:first-child{border-top:0}
.tl time{font-family:var(--mono);color:var(--ink-3);font-size:10.5px}
.tl .k{display:inline-block;width:6px;height:6px;background:var(--sun);transform:rotate(45deg) translateY(-1px);margin-right:5px}
.tl a{color:var(--ink)}
.tag{font-size:10.5px;line-height:1.45;color:var(--ink-2)}
.tag b{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:600;margin-right:4px}
.tag a{color:var(--accent);font-weight:500}
.tag a::after{content:" \2197";font-size:9px}
.tip{margin-top:auto;font-size:10.5px;line-height:1.4;color:var(--ink);background:var(--surface-2);border-radius:8px;padding:2mm 2.5mm}
.foot{font-size:9.5px;color:var(--ink-3);display:flex;justify-content:space-between}
'''
JS = r'''
(function(){
  var root = document.documentElement;
  // theme: light by default (sun and crowds), night mode remembered on this phone
  var tb = document.getElementById('theme');
  function setTheme(t){ root.setAttribute('data-theme', t);
    tb.setAttribute('aria-label', t === 'dark' ? 'Switch to day mode' : 'Switch to night mode');
    tb.title = tb.getAttribute('aria-label');
    tb.innerHTML = t === 'dark' ? tb.getAttribute('data-sun') : tb.getAttribute('data-moon'); }
  var saved = null; try { saved = localStorage.getItem('__KEY__-theme'); } catch (e) {}
  setTheme(saved === 'dark' ? 'dark' : 'light');
  tb.addEventListener('click', function(){ var t = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    setTheme(t); try { localStorage.setItem('__KEY__-theme', t); } catch (e) {} });

  // where am I: section + day context in the glass bar, active states in both navs
  var ctx = document.getElementById('ctx'), def = ctx.innerHTML;
  var navs = [].slice.call(document.querySelectorAll('[data-nav]'));
  var chips = [].slice.call(document.querySelectorAll('.scrub a'));
  var scrubOl = document.querySelector('.scrub ol');
  function mark(sec){ navs.forEach(function(a){ a.setAttribute('aria-current', a.getAttribute('data-nav') === sec ? 'true' : 'false'); }); }
  var curSec = 'today', curDay = null;
  function paintCtx(){
    if (curSec === 'days' && curDay) ctx.innerHTML = '<b>' + curDay.getAttribute('data-ctx').replace(/ · /, '</b> · ');
    else if (curSec === 'explore') ctx.innerHTML = '<b>Explore</b> · eat, drink, go';
    else if (curSec === 'info') ctx.innerHTML = '<b>Info</b> · know-how and bookings';
    else ctx.innerHTML = def;
  }
  // scroll spy: a section or day becomes current only once it fills at least 60% of the visible area
  // under the glass bars (its top has passed 40% of the way down) - or has reached the top
  var secEls = [].slice.call(document.querySelectorAll('[data-sec]'));
  var dayEls = [].slice.call(document.querySelectorAll('.day')), barEl = document.querySelector('.bar'), scrubEl = document.querySelector('.scrub');
  function spy(){
    var top = barEl.getBoundingClientRect().bottom, sb = scrubEl.getBoundingClientRect();
    if (sb.top <= top + 1 && sb.height < 80) top = Math.max(top, sb.bottom);
    var line = top + 0.4 * (window.innerHeight - top);
    var sec = secEls[0];
    secEls.forEach(function(el){ if (el.getBoundingClientRect().top <= line) sec = el; });
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) sec = secEls[secEls.length - 1];
    var day = dayEls[0];
    dayEls.forEach(function(d){ if (d.getBoundingClientRect().top <= line) day = d; });
    var secName = sec.getAttribute('data-sec');
    if (secName !== curSec) { curSec = secName; mark(curSec); paintCtx(); }
    if (day !== curDay) {
      curDay = day; paintCtx();
      chips.forEach(function(c){ var on = c.getAttribute('href') === '#' + day.id; c.setAttribute('aria-current', on ? 'true' : 'false');
        if (on && scrubOl.scrollWidth > scrubOl.clientWidth) scrubOl.scrollTo({ left: c.offsetLeft - scrubOl.clientWidth / 2 + c.offsetWidth / 2, behavior: 'smooth' }); });
    }
  }
  var ticking = false;
  window.addEventListener('scroll', function(){ if (!ticking) { ticking = true; requestAnimationFrame(function(){ ticking = false; spy(); }); } }, { passive: true });
  window.addEventListener('resize', spy);
  spy();

  // local trip time (UTC offset from trip.json): today, now and next - only while the trip is on
  var bkk = new Date(Date.now() + __TZ__ * 3600 * 1000), ymd = bkk.toISOString().slice(0, 10);
  var nowMin = bkk.getUTCHours() * 60 + bkk.getUTCMinutes();
  var hit = document.querySelector('.day[data-date="' + ymd + '"]');
  var nowCard = document.getElementById('now');
  var todayArea = null;
  if (hit) {
    nowCard.hidden = false; hit.classList.add('today');
    var sec = document.getElementById('today'); sec.insertBefore(nowCard, sec.firstChild); nowCard.style.marginTop = '24px';
    todayArea = hit.getAttribute('data-area');
    var chip = document.querySelector('.scrub a[href="#' + hit.id + '"]'); if (chip) chip.classList.add('is-today');
    var rows = [].slice.call(hit.querySelectorAll('.row')).filter(function(r){ return +r.getAttribute('data-min') >= 0; });
    var cur = null, nxt = null;
    rows.forEach(function(r){ if (+r.getAttribute('data-min') <= nowMin) cur = r; else if (!nxt) nxt = r; });
    function fill(id, r, none){
      document.getElementById(id).textContent = r ? r.querySelector('.r-a').textContent : none;
      var m = r && r.querySelector('.r-meta');
      document.getElementById(id + '-m').textContent = r ? (r.querySelector('.r-t').textContent + (m ? ' · ' + m.textContent : '')) : '';
    }
    fill('nn-now', cur, 'Free time'); fill('nn-next', nxt, 'Nothing else planned today');
    if (cur) cur.classList.add('is-now');
    document.getElementById('now-h').textContent = hit.querySelector('.d-tt h3').textContent;
    document.getElementById('now-sleep').textContent = hit.querySelector('.d-sleep').textContent;
    document.getElementById('now-go').href = '#' + hit.id;
  }

  // explore: kind + area
  var kind = 'eat', area = todayArea || (ymd < '__START__' ? '__FIRSTAREA__' : 'all');
  var segs = [].slice.call(document.querySelectorAll('.seg button')), areaChips = [].slice.call(document.querySelectorAll('.chip'));
  function apply(){
    segs.forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-kind') === kind ? 'true' : 'false'); });
    var avail = {};
    document.querySelectorAll('.grp').forEach(function(g){ if (g.getAttribute('data-scope') === kind) avail[g.getAttribute('data-area')] = 1; });
    var isEv = kind === 'on' || kind === 'opt';
    document.getElementById('areas').hidden = isEv;
    if (!isEv && area !== 'all' && !avail[area]) area = 'all';
    areaChips.forEach(function(c){ var a = c.getAttribute('data-area'); c.hidden = a !== 'all' && !avail[a];
      c.setAttribute('aria-pressed', a === area ? 'true' : 'false'); });
    var n = 0, done = 0;
    document.querySelectorAll('.grp').forEach(function(g){
      var show = g.getAttribute('data-scope') === kind && (area === 'all' || g.getAttribute('data-area') === area);
      g.hidden = !show; if (show) { n += g.querySelectorAll('.entry').length; done += g.querySelectorAll('.entry.done').length; } });
    document.getElementById('ev').hidden = kind !== 'on';
    document.getElementById('optall').hidden = kind !== 'opt';
    document.getElementById('count').textContent = kind === 'on' ? 'Listings for 17–24 November' : kind === 'opt' ? 'Every optional plan, by day' :
      (n + (n === 1 ? ' address' : ' addresses') + (done ? ' · ' + done + ' ticked off' : ''));
  }
  segs.forEach(function(b){ b.addEventListener('click', function(){ kind = b.getAttribute('data-kind'); apply(); }); });
  areaChips.forEach(function(c){ c.addEventListener('click', function(){ area = c.getAttribute('data-area'); apply(); }); });

  // tick off, per phone
  var KEY = '__KEY__-been', been = {};
  try { been = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { been = {}; }
  function paint(){
    document.querySelectorAll('.tick').forEach(function(b){ var on = !!been[b.getAttribute('data-id')];
      b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.querySelector('.tk-t').textContent = on ? 'Ticked' : 'Tick off';
      b.closest('.entry').classList.toggle('done', on); });
    apply();
  }
  document.querySelectorAll('.tick').forEach(function(b){ b.addEventListener('click', function(){
    var id = b.getAttribute('data-id'); if (been[id]) delete been[id]; else been[id] = 1;
    try { localStorage.setItem(KEY, JSON.stringify(been)); } catch (e) {} paint(); }); });
  paint();

  // deep links: #d1-#d8, #explore, #info
  var KINDS = { eat: 'eat', places: 'go', options: 'opt', events: 'on' };
  function route(){ var h = (location.hash || '').slice(1);
    if (KINDS[h]) { kind = KINDS[h]; apply(); var ex = document.getElementById('explore'); setTimeout(function(){ ex.scrollIntoView(); }, 30); return true; }
    var el = h && document.getElementById(h);
    if (el) { if (el.tagName === 'DETAILS') el.open = true; setTimeout(function(){ el.scrollIntoView(); }, 30); return true; } return false; }
  window.addEventListener('hashchange', route);
  if (!route() && hit) setTimeout(function(){ document.getElementById('today').scrollIntoView(); }, 30);
})();
'''

if __name__ == "__main__":
    main()
