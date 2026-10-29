"""Figures for m19 (exact footprint). Reads the bench outputs in
measurements/m19-footprint/ and writes docs/img/m19-*.png."""
import csv, json, os, statistics, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
MEAS = os.path.join(HERE, "..", "measurements", "m19-footprint")
IMG = os.path.join(HERE, "..", "docs", "img")
C = {"box": "#7f7f7f", "cb": "#d62728", "win": "#1f77b4", "int": "#2ca02c", "ink": "#222222"}
COLS = ["label", "d", "box", "exact", "cb_pp", "acc_pp", "acc_lat", "int_lat",
        "cb_t", "cb_c", "cb_r", "acc_t", "acc_c", "acc_r", "int_t", "int_c", "int_r", "cells"]


def load_runs():
    runs = []
    for k in (1, 2, 3):
        p = os.path.join(MEAS, f"sweep{k}.csv")
        with open(p) as f:
            runs.append([dict(zip(COLS, r)) for r in csv.reader(f)])
    # median over runs, row by row (same order in every run)
    out = []
    for rows in zip(*runs):
        m = {"label": rows[0]["label"], "d": int(rows[0]["d"])}
        for c in COLS[2:]:
            m[c] = statistics.median(float(r[c]) for r in rows)
        out.append(m)
    return out


def fig_footprint():
    j = json.load(open(os.path.join(MEAS, "fig1.json")))
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]
    c0, r0, w, h = j["c0"], j["r0"], j["w"], j["h"]
    cov = np.array(j["cov"]).reshape(h, w)
    ax.imshow(np.ma.masked_less_equal(cov, 1e-9), extent=(c0, c0 + w, r0 + h, r0), cmap="Blues", vmin=0, vmax=1.15,
              interpolation="nearest")
    for i in range(c0, c0 + w + 1):
        ax.axvline(i, color="#cccccc", lw=0.5, zorder=0)
    for r in range(r0, r0 + h + 1):
        ax.axhline(r, color="#cccccc", lw=0.5, zorder=0)
    ax.add_patch(MPoly(list(zip(j["x16"], j["y16"])), closed=True, fill=False, ec=C["ink"], lw=1.6,
                       label="outline, densify 16"))
    ax.add_patch(MPoly(list(zip(j["x1"], j["y1"])), closed=True, fill=False, ec=C["win"], lw=1.2, ls="--",
                       label="outline, densify 1 (chords)"))
    (x0, y0), (x2, y2) = (j["x1"][0], j["y1"][0]), (j["x1"][2], j["y1"][2])
    ax.add_patch(Rectangle((min(x0, x2), min(y0, y2)), abs(x2 - x0), abs(y2 - y0), fill=False, ec=C["cb"], lw=1.4,
                           label="GDAL box (top-left, bottom-right)"))
    ax.plot([x0, x2], [y0, y2], "o", color=C["cb"], ms=4)
    ax.set_xlim(c0 - 0.5, c0 + w + 0.5)
    ax.set_ylim(r0 + h + 0.5, r0 - 0.5)
    ax.set_aspect("equal")
    ax.set_xlabel("source column")
    ax.set_ylabel("source row")
    ax.set_title("(a) one destination pixel in source pixel space", fontsize=10, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=8, ncol=2, frameon=False)

    # (b) shared edges and the boundary integral
    ax = axs[1]
    def warp(u, v):
        return 1.2 + 2.3 * u + 0.55 * v + 0.12 * u * v, 1.0 + 0.45 * u + 2.1 * v + 0.05 * u * u
    for i in range(0, 10):
        ax.axvline(i, color="#cccccc", lw=0.5, zorder=0)
    for r in range(0, 9):
        ax.axhline(r, color="#cccccc", lw=0.5, zorder=0)
    t = np.linspace(0, 1, 30)
    for k in range(4):
        x, y = warp(t * 3, np.full_like(t, k)); ax.plot(x, y, color=C["ink"], lw=1)
        x, y = warp(np.full_like(t, k), t * 3); ax.plot(x, y, color=C["ink"], lw=1)
    # highlight the shared vertical edge between pixels (1,1) and (2,1)
    x, y = warp(np.full_like(t, 2), 1 + t)
    ax.plot(x, y, color=C["int"], lw=3)
    xs = np.linspace(0, 1, 400)
    ex, ey = warp(np.full_like(xs, 2), 1 + xs)
    cells = set((int(np.floor(a)), int(np.floor(b))) for a, b in zip(ex, ey))
    for (ci, rj) in cells:
        ax.add_patch(Rectangle((ci, rj), 1, 1, fc=C["int"], alpha=0.15, ec="none"))
    for (u, v, lab) in [(1.5, 1.5, "P"), (2.5, 1.5, "Q")]:
        px, py = warp(u, v)
        ax.text(px, py, lab, ha="center", va="center", fontsize=12, weight="bold")
    mx, my = warp(2, 1.5)
    ax.annotate("one edge, integrated once:\n+ to P, - to Q", xy=(mx, my), xytext=(mx - 0.6, my - 3.6),
                fontsize=8.5, arrowprops=dict(arrowstyle="->", color=C["int"]), color=C["int"])
    ax.annotate("", xy=(0.2, 7.6), xytext=(4.2, 7.6), arrowprops=dict(arrowstyle="<-", color=C["ink"]))
    ax.text(0.2, 8.4, "row prefix S(i, j): sum of the row left of column i", fontsize=8.5)
    ax.set_xlim(0, 9.5); ax.set_ylim(8.8, 0)
    ax.set_aspect("equal")
    ax.set_xlabel("source column"); ax.set_ylabel("source row")
    ax.set_title("(b) shared edges: pieces split at cell walls", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "m19-footprint.png"), dpi=150)


def fig_cost(rows):
    rot = [r for r in rows if r["label"].startswith("rot")]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, d in zip(axs, (1, 4)):
        rr = [r for r in rot if r["d"] == d]
        s = [float(r["label"].split("=")[1]) for r in rr]
        for key, lab, col in [("box", "GDAL box", C["box"]), ("exact", "rwarp 0.2 exact (controlledburn burn)", C["cb"]),
                              ("acc_lat", "lattice + coverage window", C["win"]),
                              ("int_lat", "lattice + shared-edge boundary integral", C["int"])]:
            ax.plot(s, [r[key] for r in rr], "o-", color=col, label=lab, lw=1.6, ms=4)
        ax.set_xscale("log", base=2); ax.set_yscale("log")
        ax.set_xlabel("source pixels per destination pixel (linear)")
        ax.set_title(f"densify {d}", fontsize=10, loc="left")
        ax.grid(True, which="both", color="#eeeeee")
    axs[0].set_ylabel("microseconds per destination pixel")
    axs[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("Average, one band, affine source (rotated 0.1 rad), median of 3 runs", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "m19-cost.png"), dpi=150)


def fig_projected(rows):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, tr in zip(axs, ("exact", "approx")):
        pick = [r for r in rows if r["label"].startswith("3031 10km") and r["label"].endswith(tr) and r["d"] in (1, 4)]
        bars = []
        for r in pick:
            bars.append((f"rwarp 0.2\nd={r['d']}", r["cb_t"], r["cb_c"], r["cb_r"], r["box"]))
            bars.append((f"window\nd={r['d']}", r["acc_t"], r["acc_c"], r["acc_r"], r["box"]))
            bars.append((f"integral\nd={r['d']}", r["int_t"], r["int_c"], r["int_r"], r["box"]))
        x = np.arange(len(bars))
        t = np.array([b[1] for b in bars]); c = np.array([b[2] for b in bars]); rd = np.array([b[3] for b in bars])
        ax.bar(x, t, color="#9467bd", label="transform")
        ax.bar(x, c, bottom=t, color=C["win"], label="coverage or integral")
        ax.bar(x, rd, bottom=t + c, color="#ff7f0e", label="reduce (for the integral: prefix sums)")
        ax.axhline(bars[0][4], color=C["ink"], lw=1.2, ls="--", label="GDAL box, same transformer")
        ax.set_xticks(x); ax.set_xticklabels([b[0] for b in bars], fontsize=8)
        name = "exact per-point transforms" if tr == "exact" else "ApproxTransformer, max error 0.125"
        ax.set_title(name, fontsize=10, loc="left")
        ax.grid(True, axis="y", color="#eeeeee")
    axs[0].set_ylabel("microseconds per destination pixel")
    axs[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("EPSG:4326 0.1 degree source to an EPSG:3031 10 km 256 x 256 tile (proj4rs), median of 3 runs", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "m19-projected.png"), dpi=150)


def fig_densify():
    rows = [l.split() for l in open(os.path.join(MEAS, "densify.txt")).read().splitlines()[1:]]
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    cols = {"2.5": "#1f77b4", "25": "#ff7f0e", "100": "#2ca02c"}
    for res, col in cols.items():
        rr = [r for r in rows if r[0] == res]
        d = [int(r[1]) for r in rr]
        ax.plot(d, [float(r[2]) for r in rr], "o-", color=col, label=f"{res} km pixels, densify d")
        ax.axhline(float(rr[0][6]), color=col, ls=":", lw=1.2)
    ax.plot([], [], ":", color="#555555", label="GDAL box (same pixels)")
    dd = np.array([1, 16]); ax.plot(dd, 2e-3 * dd ** -2.0, color="#999999", lw=0.8)
    ax.text(5, 2e-3 * 5 ** -2.0 * 1.6, "1/d^2", color="#777777", fontsize=8)
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xlabel("densify (segments per pixel edge)")
    ax.set_ylabel("mean |difference| from densify 64 (field units)")
    ax.set_title("Average, EPSG:4326 0.1 degree to EPSG:3031", fontsize=10, loc="left")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", color="#eeeeee")
    fig.tight_layout()
    fig.savefig(os.path.join(IMG, "m19-densify.png"), dpi=150)


if __name__ == "__main__":
    rows = load_runs()
    fig_footprint(); fig_cost(rows); fig_projected(rows); fig_densify()
