"""m36 figures from the arrays hovmoller.py read.

usage: python figures.py OUT_DIR IMG_DIR"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

out, img = sys.argv[1], sys.argv[2]
read = json.load(open(os.path.join(out, "read.json")))
hov = np.load(os.path.join(out, "hov.npy")).astype(float)
smap = np.load(os.path.join(out, "map.npy")).astype(float)
for a in (hov, smap):
    a[a == -32768] = np.nan
hov = hov * 0.001 + 25
smap = smap * 0.001 + 25

ink, muted, land = "#1f2328", "#59636e", "#d0d7de"
seq = LinearSegmentedColormap.from_list("seq", ["#f2f6fb", "#9ec3e6", "#3d7cc9", "#173f78", "#0b1f3f"])
seq.set_bad(land)
div = LinearSegmentedColormap.from_list("div", ["#1d5fa8", "#8fb6df", "#e9e9e9", "#e8a07c", "#b23a1a"])
div.set_bad(land)
plt.rcParams.update({"font.size": 9, "text.color": ink, "axes.labelcolor": ink,
                     "xtick.color": muted, "ytick.color": muted, "axes.edgecolor": land})

lat, k = read["lat"], read["level"]
w = smap.shape[1]
lon = (-180, 180)
fig, axs = plt.subplots(3, 1, figsize=(8, 9.2), height_ratios=[1, 1.15, 1.15], constrained_layout=True)

ax = axs[0]
im = ax.imshow(smap, extent=(*lon, -90, 90), cmap=seq, vmin=-2, vmax=31, interpolation="nearest")
ax.axhline(lat, color="#b23a1a", lw=1.2)
ax.text(-176, lat + 3, f"{abs(lat):.0f} S: the Hovmoller row", color=ink, fontsize=8)
ax.set_title(f"Map slice: axes (lon, lat), one day (2024-07-01), level {k}", loc="left")
ax.set_ylabel("latitude")
fig.colorbar(im, ax=ax, label="SST (C)", shrink=0.9)

ax = axs[1]
im = ax.imshow(hov, extent=(*lon, 366, 0), aspect="auto", cmap=seq, vmin=4, vmax=20, interpolation="nearest")
ax.set_title(f"Hovmoller: axes (lon, time) at {abs(lat):.0f} S, 2024, level {k}", loc="left")
ax.set_ylabel("day of 2024")
fig.colorbar(im, ax=ax, label="SST (C)", shrink=0.9)

ax = axs[2]
anom = hov - np.nanmean(hov, axis=0, keepdims=True)
im = ax.imshow(anom, extent=(*lon, 366, 0), aspect="auto", cmap=div, norm=TwoSlopeNorm(0, -4, 4),
               interpolation="nearest")
ax.set_title("Same rows, less each longitude's 2024 mean", loc="left")
ax.set_ylabel("day of 2024")
ax.set_xlabel("longitude")
fig.colorbar(im, ax=ax, label="anomaly (C)", shrink=0.9)
fig.savefig(os.path.join(img, "m36-hovmoller.png"), dpi=110)

# Cost before read, 2024 Hovmoller, by rule.
rows = [json.loads(l) for l in open(os.path.join(out, "costs.jsonl"))]
pick = [("level-0 slice", "-", "Level 0, every day (a plain array read)"),
        ("rwarp-shortest", "hour", "rwarp Need::Shortest, time in hours"),
        ("rwarp-shortest", "day", "rwarp Need::Shortest, time in days"),
        ("rwarp-area", "day", "rwarp Need::Area (either unit)"),
        ("per-axis", "day", "Per-axis need (either unit)")]
vals, labs = [], []
for rule, unit, lab in pick:
    r = next(r for r in rows if r["case"] == "hov-world-366d" and r["rule"] == rule and r["unit"] == unit)
    vals.append(r["mb"])
    labs.append(f"{lab}: level {r['levels'][0]}, {r['tiles']:,} tiles")
fig, ax = plt.subplots(figsize=(8, 2.8), constrained_layout=True)
y = np.arange(len(vals))[::-1]
ax.barh(y, vals, color="#3d7cc9", height=0.6)
for yi, v in zip(y, vals):
    ax.text(v * 1.05, yi, f"{v:,.0f} MB", va="center", color=ink, fontsize=8)
ax.set_yticks(y, labs)
ax.set_xscale("log")
ax.set_xlim(100, 12000)
ax.set_xlabel("bytes to read, MB (log scale), known from headers before any tile is fetched")
ax.set_title(f"Hovmoller at {abs(lat):.0f} S, 2024, on a 1024 x 512 screen", loc="left")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color=land, lw=0.5)
ax.set_axisbelow(True)
fig.savefig(os.path.join(img, "m36-cost.png"), dpi=110)
print("ok")
