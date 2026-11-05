"""Figures for m28 (warp output-grid defaults).

    python scripts/m28_figures.py

Reads measurements/m28-output-grid/*.json (gdal_matrix.json from
gdalwarp, odc_cases.json from odc-geo, suggest_rule.json from the m28
rule) and writes docs/img/m28-rules.png: for each source and target pair,
the suggested grid's cell count over the source's, and the fraction of
the source's footprint (its cell centres, moved with GDAL's exact
transformer) that the suggested extent holds. Then docs/img/m28-extents.png:
the extents over the footprint for the 150E to 150W box in Mollweide.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from osgeo import gdal, osr

HERE = os.path.dirname(os.path.abspath(__file__))
MEAS = os.path.join(HERE, "..", "measurements", "m28-output-grid")
IMG = os.path.join(HERE, "..", "docs", "img")
sys.path.insert(0, MEAS)
from cases import SOURCES, TARGETS  # noqa: E402

gdal.UseExceptions()
g = json.load(open(os.path.join(MEAS, "gdal_matrix.json")))["suggested"]
o = json.load(open(os.path.join(MEAS, "odc_cases.json")))
m = json.load(open(os.path.join(MEAS, "suggest_rule.json")))["cases"]
RULES = [("gdalwarp (GDALSuggestedWarpOutput2)", lambda k: g[k]["gdal"], "#c0504d", "o"),
         ("odc-geo compute_output_geobox", lambda k: o[k], "#4f81bd", "s"),
         ("m28 rule", lambda k: m[k], "#2e2e2e", "D")]


def footprint(sname, tcrs, n=200):
    crs, ext, size = SOURCES[sname]
    xmin, xmax, ymin, ymax = ext
    ds = gdal.GetDriverByName("MEM").Create("", size[0], size[1], 1)
    ds.SetGeoTransform([xmin, (xmax - xmin) / size[0], 0, ymax, 0, -(ymax - ymin) / size[1]])
    s = osr.SpatialReference()
    s.SetFromUserInput(crs)
    ds.SetProjection(s.ExportToWkt())
    t = gdal.Transformer(ds, None, [f"DST_SRS={tcrs}"])
    nx, ny = min(n, size[0]), min(n, size[1])
    px, py = np.meshgrid((np.arange(nx) + 0.5) * size[0] / nx, (np.arange(ny) + 0.5) * size[1] / ny)
    pts, ok = t.TransformPoints(0, list(zip(px.ravel(), py.ravel())))
    q = np.array([(r[0], r[1]) for r in pts])
    f = np.array(ok, dtype=bool) & np.isfinite(q).all(axis=1)
    return q[f]


def held(q, e):
    if e is None:
        return np.nan
    inside = (q[:, 0] >= e[0]) & (q[:, 0] <= e[2]) & (q[:, 1] >= e[1]) & (q[:, 1] <= e[3])
    return inside.mean()


keys = list(m)
rows = []
for k in keys:
    sname, tname = k.split(" -> ")
    q = footprint(sname, TARGETS[tname])
    ncell = SOURCES[sname][2][0] * SOURCES[sname][2][1]
    r = []
    for _, get, _, _ in RULES:
        v = get(k)
        if "error" in v:
            r.append((np.nan, np.nan))
        else:
            r.append((v["size"][0] * v["size"][1] / ncell, held(q, v["extent"])))
    rows.append(r)
rows = np.array(rows)

fig, axes = plt.subplots(1, 2, figsize=(11, 8.5), sharey=True,
                         gridspec_kw={"width_ratios": [1.6, 1]})
y = np.arange(len(keys))[::-1]
for j, (name, _, col, mk) in enumerate(RULES):
    off = (j - 1) * 0.22
    ratio = np.clip(rows[:, j, 0], 1e-3, 1e3)
    axes[0].scatter(ratio, y + off, color=col, marker=mk, s=28, label=name, zorder=3)
    over = rows[:, j, 0] > 1e3
    axes[0].scatter(np.full(over.sum(), 1e3), (y + off)[over], color=col, marker=">", s=60, zorder=3)
    axes[1].scatter(rows[:, j, 1], y + off, color=col, marker=mk, s=28, zorder=3)
    bad = np.isnan(rows[:, j, 0])
    axes[0].scatter(np.full(bad.sum(), 1e-3), (y + off)[bad], color=col, marker="x", s=40, zorder=3)
axes[0].set_xscale("log")
axes[0].set_xlim(7e-4, 1.5e3)
axes[0].axvline(1, color="#999", lw=1)
axes[0].set_xlabel("suggested cells / source cells (log; > clipped at 1000, x = error)")
axes[1].set_xlim(-0.03, 1.03)
axes[1].set_xlabel("footprint held by the extent")
axes[0].set_yticks(y)
axes[0].set_yticklabels(keys, fontsize=8)
for ax in axes:
    ax.grid(axis="x", color="#ddd", zorder=0)
    for yy in y:
        ax.axhline(yy - 0.5, color="#eee", lw=0.6, zorder=0)
axes[0].legend(loc="upper left", bbox_to_anchor=(0, 1.07), ncol=3, fontsize=8, frameon=False)
fig.suptitle(f"Suggested target grids, with only the target CRS given (GDAL {g and json.load(open(os.path.join(MEAS, 'gdal_matrix.json')))['gdal']})",
             y=0.995, fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "m28-rules.png"), dpi=110)

# Two pairs drawn: the footprint and each rule's extent.
fig, axes = plt.subplots(1, 1, figsize=(10, 3.6))
for ax, k in zip([axes], ["pacific-150to210 -> moll"]):
    sname, tname = k.split(" -> ")
    q = footprint(sname, TARGETS[tname], n=120)
    ax.scatter(q[:, 0], q[:, 1], s=0.3, color="#9bbb59")
    for name, get, col, _ in RULES:
        v = get(k)
        if "error" in v:
            continue
        e = v["extent"]
        ax.add_patch(Rectangle((e[0], e[1]), e[2] - e[0], e[3] - e[1], fill=False,
                               ec=col, lw=1.6, label=f"{name}: {v['size'][0]} x {v['size'][1]}"))
    lim = m[k]["extent"]
    pad = 0.05 * (lim[2] - lim[0])
    ax.set_xlim(lim[0] - pad, lim[2] + pad)
    ax.set_ylim(lim[1] - 0.3 * (lim[3] - lim[1]), lim[3] + 1.2 * (lim[3] - lim[1]))
    ax.set_aspect("equal")
    ax.set_title(k + " (odc-geo: AssertionError)", fontsize=10)
    ax.legend(loc="upper center", fontsize=8, frameon=False)
    ax.ticklabel_format(style="sci", scilimits=(6, 6))
fig.tight_layout()
fig.savefig(os.path.join(IMG, "m28-extents.png"), dpi=110)
for k, r in zip(keys, rows):
    print(k, " ".join(f"{a:9.3g} {b:5.2f}" for a, b in r))
