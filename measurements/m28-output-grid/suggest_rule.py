"""A prototype of the m28 suggestion rule, with GDAL's exact transformer
as the point mover, on the m28 source/target pairs.

    python measurements/m28-output-grid/suggest_rule.py > measurements/m28-output-grid/suggest_rule.json

The rule (m28 section 5):

1. Lay a lattice of up to N x N blocks over the source (N = 128, or the
   source size when smaller) and move every block corner to the target.
2. Each block whose four corners all moved is a quadrilateral; its area
   over the number of source cells it holds is the target area one source
   cell takes there.
3. An edge is long when, per source cell along it, it is longer than
   T (20) times the square root of the median area. Bisecting a long edge
   in source pixel space tells a tear (the map jumps between two points
   that settle: the target's seam, or a wrap round a pole) from a stretch
   (continuous and steep, or running away towards a pole of the target). A block
   with a torn edge is torn. A block is singular when it has a non-finite
   corner, or is not torn and its area is more than K (100) times the
   median.
4. Cell size: the square root of the median area over the blocks that are
   neither singular nor torn. Square cells, cell area kept.
5. Extent: the bounding box of the corners of the good blocks (neither
   torn nor singular), plus the two points either side of each tear, from
   the bisection, so the extent reaches the seam from both sides (those
   within one good block's longest edge of the good corners).
6. Whole cells: size = ceil(extent / cell size), the overshoot split
   evenly on both sides. No snapping to multiples of the cell size, which
   is nobody's number here.

Reported beside the grid: the fraction of blocks dropped as singular and
as torn, so a caller sees what the suggestion left out.
"""

import json
import math
import os
import sys

import numpy as np
from osgeo import gdal, osr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import SOURCES, TARGETS  # noqa: E402

gdal.UseExceptions()
N, K, T = 128, 100.0, 20.0


def source(name, crs, extent, size):
    xmin, xmax, ymin, ymax = extent
    ds = gdal.GetDriverByName("MEM").Create(name, size[0], size[1], 1, gdal.GDT_Byte)
    ds.SetGeoTransform([xmin, (xmax - xmin) / size[0], 0, ymax, 0, -(ymax - ymin) / size[1]])
    s = osr.SpatialReference()
    s.SetFromUserInput(crs)
    ds.SetProjection(s.ExportToWkt())
    return ds


def suggest(ds, dst_crs, within=None):
    nx, ny = ds.RasterXSize, ds.RasterYSize
    bx, by = min(N, nx), min(N, ny)
    cx = np.linspace(0, nx, bx + 1)
    cy = np.linspace(0, ny, by + 1)
    gx, gy = np.meshgrid(cx, cy)
    t = gdal.Transformer(ds, None, [f"DST_SRS={dst_crs}"])

    def move(px, py):
        pts, ok = t.TransformPoints(0, list(zip(np.ravel(px), np.ravel(py))))
        q = np.array([(r[0], r[1]) for r in pts], dtype=float)
        q[~np.array(ok, dtype=bool)] = np.nan
        return q[:, 0].reshape(np.shape(px)), q[:, 1].reshape(np.shape(px))

    X, Y = move(gx, gy)
    # Block corners in ring order a b c d (a top left, then clockwise).
    idx = [(slice(None, -1), slice(None, -1)), (slice(None, -1), slice(1, None)),
           (slice(1, None), slice(1, None)), (slice(1, None), slice(None, -1))]
    cxs = [X[i] for i in idx]
    cys = [Y[i] for i in idx]
    area = 0.5 * np.abs(sum(cxs[k] * cys[(k + 1) % 4] - cxs[(k + 1) % 4] * cys[k]
                            for k in range(4)))
    wx = np.diff(cx)[None, :] * np.ones((by, 1))   # cells along a block's x edges
    wy = np.diff(cy)[:, None] * np.ones((1, bx))   # cells along its y edges
    a = area / (wx * wy)
    finite = np.isfinite(a)
    med = float(np.median(a[finite]))
    step = math.sqrt(med)
    # Edge k joins corner k to corner k + 1: x edges are 0 and 2, y edges 1 and 3.
    ncell = [wx, wy, wx, wy]
    elen = [np.hypot(cxs[(k + 1) % 4] - cxs[k], cys[(k + 1) % 4] - cys[k]) / ncell[k]
            for k in range(4)]
    # A long edge is either stretched (the map is continuous along it, only
    # steep) or torn (it jumps). Bisect each long edge in source pixel space
    # to tell which: a tear leaves a gap that does not close.
    pcx = [gx[i] for i in idx]
    pcy = [gy[i] for i in idx]
    tear = [np.zeros(a.shape, dtype=bool) for _ in range(4)]
    sides = []
    for k in range(4):
        sel = finite & (elen[k] > T * step)
        if not sel.any():
            continue
        p0 = np.stack([pcx[k][sel], pcy[k][sel]], axis=1)
        p1 = np.stack([pcx[(k + 1) % 4][sel], pcy[(k + 1) % 4][sel]], axis=1)
        q0 = np.stack([cxs[k][sel], cys[k][sel]], axis=1)
        q1 = np.stack([cxs[(k + 1) % 4][sel], cys[(k + 1) % 4][sel]], axis=1)
        for it in range(40):
            if it == 39:
                r0, r1 = q0.copy(), q1.copy()
            pm = 0.5 * (p0 + p1)
            mx, my = move(pm[:, 0], pm[:, 1])
            qm = np.stack([mx, my], axis=1)
            left = np.hypot(*(qm - q0).T) >= np.hypot(*(q1 - qm).T)
            p1 = np.where(left[:, None], pm, p1)
            q1 = np.where(left[:, None], qm, q1)
            p0 = np.where(left[:, None], p0, pm)
            q0 = np.where(left[:, None], q0, qm)
        # A tear's two sides settle on two points; a blow-up (a pole of the
        # target at or near the edge) keeps one side running away.
        settled = ((np.hypot(*(q0 - r0).T) < 1e-3 * step)
                   & (np.hypot(*(q1 - r1).T) < 1e-3 * step))
        jump = (np.hypot(*(q1 - q0).T) > T * step) & settled
        tear[k][sel] = jump
        sides.append((q0[jump], q1[jump]))
    torn = np.logical_or.reduce(tear)
    singular = ~finite | (~torn & ((a > K * med) | (a <= 0)))
    good = ~singular & ~torn
    if within is not None:
        # A given extent: the cell size from the blocks that land in it.
        mxc, myc = sum(cxs) / 4, sum(cys) / 4
        inside = ((mxc >= within[0]) & (mxc <= within[2])
                  & (myc >= within[1]) & (myc <= within[3]))
        res = math.sqrt(float(np.median(a[good & inside])))
        return {"res": [res, res]}
    res = math.sqrt(float(np.median(a[good])))
    keep = np.zeros(gx.shape, dtype=bool)
    for i in idx:
        keep[i] |= good
    xs, ys = list(X[keep]), list(Y[keep])
    # The points either side of each tear, so the extent reaches the seam;
    # only those within one good block of the good corners (a tear along a
    # row that runs into a pole of the target is not a reach).
    reach = max(float(np.nanmax(e[good] * n[good])) for e, n in zip(elen, ncell))
    box = [min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach]
    for q0, q1 in sides:
        for q in (q0, q1):
            f = (np.isfinite(q).all(axis=1) & (q[:, 0] >= box[0]) & (q[:, 0] <= box[2])
                 & (q[:, 1] >= box[1]) & (q[:, 1] <= box[3]))
            xs += list(q[f, 0])
            ys += list(q[f, 1])
    e = [min(xs), min(ys), max(xs), max(ys)]
    # No snapping for a suggested cell size (it is no one's number): whole
    # cells, the overshoot split evenly about the footprint.
    size = [max(1, math.ceil((e[2] - e[0]) / res - 1e-9)),
            max(1, math.ceil((e[3] - e[1]) / res - 1e-9))]
    ox = (size[0] * res - (e[2] - e[0])) / 2
    oy = (size[1] * res - (e[3] - e[1])) / 2
    s = [e[0] - ox, e[1] - oy, e[2] + ox, e[3] + oy]
    return {"extent": s, "res": [res, res], "size": size, "footprint": e,
            "singular": float(singular.mean()), "torn": float(torn.mean())}


out = {"N": N, "K": K, "T": T, "gdal": gdal.__version__, "cases": {}}
for sname, (crs, ext, size) in SOURCES.items():
    src = source(sname, crs, ext, size)
    for tname, tcrs in TARGETS.items():
        if sname.startswith("world") and tname == "32755":
            continue
        try:
            out["cases"][f"{sname} -> {tname}"] = suggest(src, tcrs)
        except Exception as e:  # noqa: BLE001
            out["cases"][f"{sname} -> {tname}"] = {"error": str(e)[:200]}
# Given extents (gdalwarp -te, no -tr), as in gdal_matrix.py.
out["within"] = {}
for key, sname, tcrs, te in [
        ("utm55s-10m -> 4326", "utm55s-10m", "EPSG:4326", [146.99, -43.42, 148.36, -42.4]),
        ("world-0.5 -> 3031", "world-0.5", "EPSG:3031", [-4e6, -4e6, 4e6, 4e6])]:
    crs, ext, size = SOURCES[sname]
    out["within"][key] = suggest(source(sname, crs, ext, size), tcrs, within=te)
print(json.dumps(out, indent=1))
