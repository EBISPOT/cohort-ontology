#!/usr/bin/env python3
"""
Draw docs/images/cohort-map.svg, the map in the README of where COHO's cohorts
recruited: each country shaded by the number of cohorts with a data collection
location there, with a key to the shades. `om make prepare_release` redraws it
(the map's target in owlmake.yaml), so each release commits the map of its own
data.

Sources:
  src/templates/locations.tsv   the cohorts' data collection locations
  src/templates/gaz_xrefs.tsv   which places are countries (NCIT:C25464), and
                                their labels
  src/map/countries-110m.json   the country outlines: Natural Earth's 1:110m
                                Admin 0 countries (version 4.1.0, public domain)
                                as TopoJSON, from the world-atlas package,
                                version 2.0.2 (ISC licence, in
                                src/map/LICENSE-world-atlas):
                                https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json

A cohort located in several countries counts in each; cohorts located only to a
region, such as Europe, are not drawn. The script names the located countries it
has no outline for. Only very small ones, such as Singapore, should be among
them: a larger one is named differently in the outlines, and needs an entry in
OUTLINE_NAMES.

Usage: src/scripts/cohort_map.py
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCATIONS = ROOT / "src/templates/locations.tsv"
GAZ = ROOT / "src/templates/gaz_xrefs.tsv"
OUTLINES = ROOT / "src/map/countries-110m.json"
SVG = ROOT / "docs/images/cohort-map.svg"

COUNTRY = "NCIT:C25464"

# the outlines' names for the countries whose label in gaz_xrefs.tsv differs
OUTLINE_NAMES = {
    "dbpedia:United_States": "United States of America",
    "dbpedia:Republic_of_Ireland": "Ireland",
    "dbpedia:Czech_Republic": "Czechia",
    "dbpedia:Democratic_Republic_of_the_Congo": "Dem. Rep. Congo",
    "dbpedia:Ivory_Coast": "Côte d'Ivoire",
}

# the drawing, in SVG units
WIDTH, MARGIN = 1000, 12
GROUND, LAND, MUTED = "#F4F7F7", "#DCE2E1", "#5A6B6D"
# the shades, each from its lowest number of cohorts
SHADES = [(1, "#B5DBD4"), (5, "#86C2BA"), (20, "#58A69E"), (50, "#2F8780"), (100, "#146A64"), (200, "#08443F")]
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"


def table(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))


def cohorts_per_country():
    """The number of cohorts located in each country."""
    places = {r[0]: r[2] for r in table(GAZ)[2:]}
    where = defaultdict(set)
    for r in table(LOCATIONS)[2:]:
        where[r[0]].update(p for p in r[3].split("|") if p)
    per = defaultdict(int)
    for cohort, located in sorted(where.items()):
        unknown = located - places.keys()
        if unknown:
            raise SystemExit(f"{cohort}: {', '.join(sorted(unknown))} not in {GAZ.relative_to(ROOT)}")
        for p in located:
            if places[p] == COUNTRY:
                per[p] += 1
    return per


def outlines():
    """Each country's rings of (longitude, latitude) by name, without
    Antarctica; a ring that crosses the 180th meridian is cut in two there."""
    topo = json.loads(OUTLINES.read_text(encoding="utf-8"))
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            points.append((x * sx + tx, y * sy + ty))
        arcs.append(points)

    def ring(ids):
        points = []
        for i in ids:
            arc = arcs[i] if i >= 0 else arcs[~i][::-1]
            points.extend(arc[1:] if points else arc)
        return points

    countries = {}
    for g in topo["objects"]["countries"]["geometries"]:
        name = g["properties"]["name"]
        if name == "Antarctica":
            continue
        if g["type"] == "Polygon":
            polygons = [g["arcs"]]
        elif g["type"] == "MultiPolygon":
            polygons = g["arcs"]
        else:
            continue
        countries[name] = [part for polygon in polygons for ids in polygon for part in cut(ring(ids))]
    return countries


def cut(ring):
    """A ring, or the two parts of one that crosses the 180th meridian."""
    if all(abs(a[0] - b[0]) <= 180 for a, b in zip(ring, ring[1:])):
        return [ring]
    ring = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in ring]
    east = side(ring, lambda lon: lon <= 180)
    west = [(lon - 360, lat) for lon, lat in side(ring, lambda lon: lon > 180)]
    return [part for part in (east, west) if len(part) > 2]


def side(ring, keep):
    """The part of a ring whose longitudes keep accepts, closed along 180 degrees."""
    out = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if keep(a[0]):
            out.append(a)
        if keep(a[0]) != keep(b[0]):
            out.append((180, a[1] + (180 - a[0]) / (b[0] - a[0]) * (b[1] - a[1])))
    return out


A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def equal_earth(lon, lat):
    """The Equal Earth projection (Šavrič, Patterson and Jenny 2018), y up."""
    t = math.asin(M * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 ** 3
    return (math.radians(lon) * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))),
            t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2)))


def fitted(countries):
    """Equal Earth, scaled so the outlines span the width inside MARGIN, and the
    height of the map it draws."""
    xs, ys = zip(*(equal_earth(*p) for rings in countries.values() for r in rings for p in r))
    k = (WIDTH - 2 * MARGIN) / (max(xs) - min(xs))

    def project(lon, lat):
        x, y = equal_earth(lon, lat)
        return MARGIN + k * (x - min(xs)), MARGIN + k * (max(ys) - y)
    return project, 2 * MARGIN + k * (max(ys) - min(ys))


def tenths(t):
    """A length given in tenths of a unit, as briefly as SVG path data allows."""
    s = f"{t / 10:.1f}".removesuffix(".0")
    return s.replace("0.", ".", 1) if s.lstrip("-").startswith("0.") else s


def path(rings, project):
    """Rings as SVG path data: each a move, then lines relative to it."""
    d = []
    for ring in rings:
        points = [(round(10 * x), round(10 * y)) for x, y in (project(*p) for p in ring)]
        steps = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
        steps = [s for s in steps if s != (0, 0)]
        if len(steps) < 2:
            continue
        line = ""
        for v in (v for s in steps for v in s):
            n = tenths(v)
            line += n if not line or n.startswith("-") else "," + n
        d.append(f"M{tenths(points[0][0])},{tenths(points[0][1])}l{line}z")
    return "".join(d)


def shade(n):
    return [colour for low, colour in SHADES if n >= low][-1] if n else LAND


def draw(per):
    """The map as SVG, and the located countries it has no outline for."""
    labels = {r[0]: r[3] for r in table(GAZ)[2:]}
    countries = outlines()
    project, height = fitted(countries)
    by_outline = {OUTLINE_NAMES.get(c, labels[c]): n for c, n in per.items()}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}" '
           f'viewBox="0 0 {WIDTH} {height:.0f}" role="img" aria-labelledby="title">',
           '<title id="title">Where COHO’s cohorts recruited, each country shaded by its number of cohorts</title>',
           f'<rect width="100%" height="100%" fill="{GROUND}"/>',
           f'<g stroke="{GROUND}" stroke-width="0.6" stroke-linejoin="round" fill-rule="evenodd">']
    for name, rings in sorted(countries.items()):
        out.append(f'<path fill="{shade(by_outline.get(name, 0))}" d="{path(rings, project)}"/>')
    out.append("</g>")

    # the key to the shades, highest first, in the empty ocean at the bottom left
    keys = [("0", LAND)] + [(f"{low}–{high - 1}" if high else f"{low}+", colour)
                            for (low, colour), (high, _) in zip(SHADES, SHADES[1:] + [(None, None)])]
    y = height - MARGIN - 6 - 21 * len(keys)
    out.append(f'<g font-family="{FONT}" font-size="15" style="font-variant-numeric:tabular-nums">')
    for label, colour in reversed(keys):
        out.append(f'<rect x="{MARGIN + 8}" y="{y:.1f}" width="22" height="14" rx="2" fill="{colour}"/>')
        out.append(f'<text x="{MARGIN + 38}" y="{y + 12:.1f}" fill="{MUTED}">{label}</text>')
        y += 21
    out += ["</g>", "</svg>"]
    unshown = sorted((c for c in per if OUTLINE_NAMES.get(c, labels[c]) not in countries),
                     key=lambda c: (-per[c], labels[c]))
    return "\n".join(out) + "\n", [f"{labels[c]} ({per[c]})" for c in unshown]


def main():
    per = cohorts_per_country()
    svg, unshown = draw(per)
    SVG.parent.mkdir(parents=True, exist_ok=True)
    SVG.write_text(svg, encoding="utf-8")
    print(f"{SVG.relative_to(ROOT)}: {len(per)} countries; no outline for {', '.join(unshown) or 'none'}")


if __name__ == "__main__":
    main()
