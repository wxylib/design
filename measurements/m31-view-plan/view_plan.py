"""m31: single-level versus per-region chunk planning for a view.

No I/O. A source pyramid is described by its metadata only (a global
lon/lat grid like GHRSST MUR: 36000 x 18000 cells of 0.01 degree, levels
halving to level 6, 512 x 512 chunks of int16). For each view (CRS, extent,
1024 x 1024 screen pixels) two planners pick chunks:

- single: one source bounding box from sampled view points and one level
  from the mean source cell per screen pixel (the rule the existing mesh
  viewers use, with their quality factor 0.7);
- region: the screen split into 64 x 64 pixel tiles, each with its own
  level from the local scale (square root of the Jacobian determinant of
  screen pixel to source cell, lowest quartile over the tile), its own
  footprint unwrapped about the tile centre longitude, chunks de-duplicated.

Reported: chunks, megabytes, and the share of visible screen pixels whose
data is more than one level too coarse (under) or too fine (over) against
the local need. Run: python3 measurements/m31-view-plan/view_plan.py > results.json
"""
import json
import math
import sys

import numpy as np
from pyproj import CRS, Transformer

W = H = 1024
NX0, NY0, RES0 = 36000, 18000, 0.01
NLEV = 7
CHUNK = 512
BYTES = 2
TILE = 64


def levels(n=NLEV):
    out = []
    for k in range(n):
        f = 2 ** k
        out.append({"k": k, "res": RES0 * f, "nx": math.ceil(NX0 / f), "ny": math.ceil(NY0 / f)})
    return out


def view_points(view, px, py):
    """Screen pixel centres (px, py arrays) to lon/lat, NaN where invalid."""
    x0, y0, x1, y1 = view["extent"]
    x = x0 + (px + 0.5) / W * (x1 - x0)
    y = y1 - (py + 0.5) / H * (y1 - y0)
    if view["crs"] == "lonlat":
        lon = ((x + 180.0) % 360.0) - 180.0
        return lon, y
    t = Transformer.from_crs(CRS(view["crs"]), CRS("EPSG:4326"), always_xy=True)
    lon, lat = t.transform(x, y)
    lon = np.where(np.isfinite(lon) & (np.abs(lon) <= 180), lon, np.nan)
    lat = np.where(np.isfinite(lat) & (np.abs(lat) <= 90), lat, np.nan)
    bad = np.isnan(lon) | np.isnan(lat)
    if view["crs"].startswith("+proj=ortho"):
        # round trip check: points past the horizon do not come back
        f = Transformer.from_crs(CRS("EPSG:4326"), CRS(view["crs"]), always_xy=True)
        bx, by = f.transform(np.where(bad, 0, lon), np.where(bad, 0, lat))
        tol = (x1 - x0) / W
        bad |= ~(np.isfinite(bx) & (np.abs(bx - x) < tol) & (np.abs(by - y) < tol))
    lon = np.where(bad, np.nan, lon)
    lat = np.where(bad, np.nan, lat)
    return lon, lat


def local_need(view, px, py):
    """Source cell (degrees) that one screen pixel needs at each point."""
    lon, lat = view_points(view, px, py)
    lx, ax = view_points(view, px + 0.5, py)
    ly, ay = view_points(view, px, py + 0.5)
    dlx = ((lx - lon + 180) % 360 - 180) * 2
    dly = ((ly - lon + 180) % 360 - 180) * 2
    dax = (ax - lat) * 2
    day = (ay - lat) * 2
    det = np.abs(dlx * day - dly * dax)
    need = np.sqrt(det)
    return lon, lat, need


def pick_level(levs, need):
    lev = levs[0]
    for L in levs:
        if L["res"] <= need:
            lev = L
    return lev


def chunks_for(lev, lon, lat, centre_lon=None):
    """Chunk keys covering the points, unwrapped about centre_lon."""
    ok = np.isfinite(lon) & np.isfinite(lat)
    if not ok.any():
        return set()
    lo, la = lon[ok], lat[ok]
    if centre_lon is not None:
        lo = centre_lon + ((lo - centre_lon + 180) % 360 - 180)
    pad = lev["res"]
    xmin, xmax = lo.min() - pad, lo.max() + pad
    ymin, ymax = max(la.min() - pad, -90), min(la.max() + pad, 90)
    if xmax - xmin >= 360:
        xmin, xmax = -180, 180
    c0 = math.floor((xmin + 180) / lev["res"] / CHUNK)
    c1 = math.floor((xmax + 180 - 1e-9) / lev["res"] / CHUNK)
    r0 = math.floor((90 - ymax) / lev["res"] / CHUNK)
    r1 = math.floor((90 - ymin - 1e-9) / lev["res"] / CHUNK)
    ncx = math.ceil(lev["nx"] / CHUNK)
    ncy = math.ceil(lev["ny"] / CHUNK)
    out = set()
    for c in range(c0, c1 + 1):
        for r in range(max(r0, 0), min(r1, ncy - 1) + 1):
            out.add((lev["k"], c % ncx, r))
    return out


def chunk_bytes(keys, levs):
    tot = 0
    for k, c, r in keys:
        L = levs[k]
        w = min(CHUNK, L["nx"] - c * CHUNK)
        h = min(CHUNK, L["ny"] - r * CHUNK)
        tot += w * h * BYTES
    return tot


def plan_single(view, levs):
    g = np.linspace(0, W - 1, 64)
    px, py = np.meshgrid(g, g)
    lon, lat = view_points(view, px.ravel(), py.ravel())
    ok = np.isfinite(lon)
    bw = np.nanmax(lon) - np.nanmin(lon)
    bh = np.nanmax(lat) - np.nanmin(lat)
    # displayed span of the visible points, in screen pixels
    sw = np.ptp(px.ravel()[ok]) + 1
    sh = np.ptp(py.ravel()[ok]) + 1
    need = min(bw / sw, bh / sh) * 0.7
    lev = pick_level(levs, need)
    keys = chunks_for(lev, lon, lat)
    return keys, lambda tx, ty: lev["res"]


def plan_region(view, levs):
    keys = set()
    tile_res = {}
    s = np.linspace(0, TILE - 1, 9)
    for ty in range(H // TILE):
        for tx in range(W // TILE):
            px, py = np.meshgrid(tx * TILE + s, ty * TILE + s)
            lon, lat, need = local_need(view, px.ravel(), py.ravel())
            ok = np.isfinite(need) & (need > 0)
            if not ok.any():
                continue
            lev = pick_level(levs, float(np.quantile(need[ok], 0.25)))
            tile_res[(tx, ty)] = lev["res"]
            cl = float(np.nanmedian(lon))
            keys |= chunks_for(lev, lon, lat, centre_lon=cl)
    return keys, lambda tx, ty: tile_res.get((tx, ty), np.nan)


def score(view, levs, resfun):
    g = np.arange(2, W, 4.0)
    px, py = np.meshgrid(g, g)
    px, py = px.ravel(), py.ravel()
    _, _, need = local_need(view, px, py)
    ok = np.isfinite(need) & (need > 0)
    used = np.array([resfun(int(x // TILE), int(y // TILE)) for x, y in zip(px[ok], py[ok])])
    n = need[ok]
    # snap need to the level that ideally serves it
    ideal = np.array([pick_level(levs, v)["res"] for v in n])
    under = float(np.mean(used >= ideal * 4 - 1e-12))
    over = float(np.mean(used <= ideal / 4 + 1e-12))
    return under, over, float(ok.mean())


VIEWS = [
    {"name": "ortho disk, 147E 42S", "crs": "+proj=ortho +lon_0=147 +lat_0=-42 +R=6371000",
     "extent": [-6.4e6, -6.4e6, 6.4e6, 6.4e6]},
    {"name": "ortho 600 km, Hobart", "crs": "+proj=ortho +lon_0=147.3 +lat_0=-42.9 +R=6371000",
     "extent": [-3e5, -3e5, 3e5, 3e5]},
    {"name": "EPSG:3031, 4000 km", "crs": "EPSG:3031",
     "extent": [-4e6, -4e6, 4e6, 4e6]},
    {"name": "lon/lat 160E..160W", "crs": "lonlat",
     "extent": [160, -30, 200, 10]},
]


def main(levn):
    levs = levels(levn)
    rows = []
    for v in VIEWS:
        row = {"view": v["name"], "levels": levn}
        for name, fn in (("single", plan_single), ("region", plan_region)):
            keys, resfun = fn(v, levs)
            under, over, vis = score(v, levs, resfun)
            row[name] = {"chunks": len(keys), "mb": round(chunk_bytes(keys, levs) / 1e6, 1),
                         "levels_used": sorted({k for k, _, _ in keys}),
                         "under": round(under, 3), "over": round(over, 3)}
            row["visible"] = round(vis, 3)
        rows.append(row)
    return rows


if __name__ == "__main__":
    out = {"pyramid": main(NLEV), "full_resolution_only": main(1)}
    json.dump(out, sys.stdout, indent=1)
    print()
