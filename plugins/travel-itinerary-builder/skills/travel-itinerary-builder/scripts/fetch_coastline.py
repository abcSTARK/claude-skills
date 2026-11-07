#!/usr/bin/env python3
"""
Clip real coastline (OSM-derived land polygons, 500 m resolution) to a lon/lat box and save it
as the compact ring list that itinerary_kit.py draws.

  python3 fetch_coastline.py 97.86 7.56 99.10 8.28 land.json [--tolerance 0.0012]

Needs: npm (to fetch @geo-maps/earth-lands-500m once, ~50 MB, cached) and shapely (pip).
If either is unavailable, leave "land" out of trip.json - the map still draws sea, routes and pins.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

CACHE = Path(os.environ.get("ITINERARY_CACHE", Path.home() / ".cache" / "itinerary-kit"))


def land_file():
    f = CACHE / "node_modules/@geo-maps/earth-lands-500m/map.geo.json"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        if not (CACHE / "package.json").exists():
            (CACHE / "package.json").write_text('{"name":"itinerary-kit-cache","private":true}')
        subprocess.run(["npm", "i", "--silent", "@geo-maps/earth-lands-500m"], cwd=CACHE, check=True)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lon0", type=float); ap.add_argument("lat0", type=float)
    ap.add_argument("lon1", type=float); ap.add_argument("lat1", type=float)
    ap.add_argument("out")
    ap.add_argument("--tolerance", type=float, default=0.0012, help="simplify tolerance in degrees")
    a = ap.parse_args()
    import shapely
    from shapely.geometry import Polygon
    d = json.load(open(land_file()))
    geoms = d["geometries"] if "geometries" in d else [f["geometry"] for f in d["features"]]
    out = []
    for g in geoms:
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
        for rings in polys:
            xs = [p[0] for p in rings[0]]; ys = [p[1] for p in rings[0]]
            if max(xs) < a.lon0 or min(xs) > a.lon1 or max(ys) < a.lat0 or min(ys) > a.lat1:
                continue          # bbox pre-filter: never make_valid() a continent
            c = shapely.clip_by_rect(Polygon(rings[0], rings[1:]), a.lon0, a.lat0, a.lon1, a.lat1)
            for q in ([c] if c.geom_type == "Polygon" else getattr(c, "geoms", [])):
                if q.geom_type != "Polygon" or q.is_empty:
                    continue
                q = q.simplify(a.tolerance, preserve_topology=True)
                if q.is_empty or q.area < 0.000004:
                    continue
                out.append([[[round(x, 4), round(y, 4)] for x, y in q.exterior.coords]] +
                           [[[round(x, 4), round(y, 4)] for x, y in r.coords] for r in q.interiors])
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print(f"{len(out)} polygons -> {a.out} ({Path(a.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
