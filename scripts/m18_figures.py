"""Figures for docs/m18-editing-canvas.md.

1. m18-constraints.png: how one placed vertex comes from the pointer, a
   snap and the locked values, in three cases the prototype implements
   (wxylib/web www/edit-core.js, constrain()).
2. m18-layers.png: the editing canvas as front end, engine and slots.

    python3 -m pip install numpy matplotlib
    python3 scripts/m18_figures.py
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "img")

INK = "#1d1d1f"
FEAT = "#3b6ea5"
GUIDE = "#7c3aed"
SNAP = "#db2777"
PLACED = "#15803d"
MUTED = "#8e8e93"


def ref_mark(ax, p, label="previous vertex"):
    ax.plot(*p, "s", ms=7, mfc="white", mec=INK, zorder=5)
    ax.annotate(label, p, xytext=(-8, -14), textcoords="offset points", ha="left", fontsize=8, color=INK)


def cursor_mark(ax, p):
    ax.plot(*p, "x", ms=7, color=MUTED, mew=1.5, zorder=5)
    ax.annotate("pointer", p, xytext=(6, 4), textcoords="offset points", fontsize=8, color=MUTED)


def placed_mark(ax, p, label="placed"):
    ax.plot(*p, "+", ms=14, color=PLACED, mew=2.2, zorder=6)
    ax.annotate(label, p, xytext=(8, -12), textcoords="offset points", fontsize=8, color=PLACED, weight="bold")


def ray(ax, o, theta, lo=-2, hi=12, **kw):
    d = np.array([np.cos(theta), np.sin(theta)])
    a, b = np.array(o) + lo * d, np.array(o) + hi * d
    ax.plot([a[0], b[0]], [a[1], b[1]], ls=(0, (5, 4)), lw=1.1, color=GUIDE, **kw)


def line_line(o, theta, c, d):
    o, c, d = map(np.asarray, (o, c, d))
    r = np.array([np.cos(theta), np.sin(theta)])
    s = d - c
    den = r[0] * s[1] - r[1] * s[0]
    t = ((c - o)[0] * s[1] - (c - o)[1] * s[0]) / den
    return o + t * r


def panel_angle_segment(ax):
    ref = (0.0, 0.0)
    theta = np.radians(35)
    seg = ((6.5, -1.0), (7.5, 7.5))
    ax.plot(*zip(*seg), color=FEAT, lw=2)
    ax.annotate("existing segment", seg[1], xytext=(-90, -4), textcoords="offset points", fontsize=8, color=FEAT)
    ray(ax, ref, theta)
    ax.annotate("a locked at 35", (1.6, 1.55), fontsize=8, color=GUIDE, rotation=35)
    cur = (8.6, 3.0)
    cursor_mark(ax, cur)
    # the snap: nearest point on the segment to the pointer
    a, b = np.array(seg[0]), np.array(seg[1])
    t = np.dot(np.array(cur) - a, b - a) / np.dot(b - a, b - a)
    sp = a + t * (b - a)
    ax.plot(*sp, marker="$\u29d7$", ms=11, color=SNAP, zorder=5)
    ax.annotate("segment snap", sp, xytext=(8, -14), textcoords="offset points", fontsize=8, color=SNAP)
    p = line_line(ref, theta, *seg)
    placed_mark(ax, p, "placed: on both")
    ref_mark(ax, ref)
    ax.set_title("Angle lock and a segment snap", fontsize=10)
    ax.set_xlim(-1.5, 10)
    ax.set_ylim(-2, 8)


def panel_distance_x(ax):
    ref = (0.0, 0.0)
    r = 5.0
    ax.add_patch(Circle(ref, r, fill=False, ls=(0, (5, 4)), lw=1.1, color=GUIDE))
    ax.annotate("d locked at 5", (-3.9, 3.6), fontsize=8, color=GUIDE)
    x = 3.0
    ax.plot([x, x], [-6.5, 6.5], ls=(0, (5, 4)), lw=1.1, color=GUIDE)
    ax.annotate("x locked at +3\n(relative)", (x, 5.6), xytext=(5, 0), textcoords="offset points", fontsize=8, color=GUIDE)
    y = np.sqrt(r * r - x * x)
    ax.plot([x], [y], "o", ms=5, mfc="white", mec=GUIDE, zorder=5)
    ax.annotate("other crossing", (x, y), xytext=(8, -2), textcoords="offset points", fontsize=8, color=GUIDE)
    cur = (4.6, -2.6)
    cursor_mark(ax, cur)
    placed_mark(ax, (x, -y), "placed: nearer\ncrossing")
    ref_mark(ax, ref)
    ax.set_title("Distance lock and an x lock", fontsize=10)
    ax.set_xlim(-6.5, 8)
    ax.set_ylim(-6.5, 7)


def panel_bearing(ax):
    prev = (-5.0, -1.8)
    ref = (0.0, 0.0)
    ax.plot(*zip(prev, ref), color=PLACED, lw=2)
    ax.annotate("previous segment", (-4.6, -1.15), fontsize=8, color=PLACED, rotation=np.degrees(np.arctan2(1.8, 5)))
    base = np.arctan2(ref[1] - prev[1], ref[0] - prev[0])
    for k in range(-6, 7):
        th = base + np.radians(15 * k)
        d = np.array([np.cos(th), np.sin(th)])
        ax.plot([0, 7 * d[0]], [0, 7 * d[1]], color=GUIDE, lw=0.6, alpha=0.35)
    cur = (2.5, 5.3)
    cursor_mark(ax, cur)
    raw = np.arctan2(cur[1], cur[0])
    k = round((raw - base) / np.radians(15))
    th = base + k * np.radians(15)
    d = np.array([np.cos(th), np.sin(th)])
    ax.plot([0, 8 * d[0]], [0, 8 * d[1]], ls=(0, (5, 4)), color=GUIDE, lw=1.3)
    p = d * np.dot(cur, d)
    placed_mark(ax, p, f"placed: turn of {15 * k} deg")
    ref_mark(ax, ref, "")
    ax.set_title("Bearing steps of 15 deg, relative", fontsize=10)
    ax.set_xlim(-6, 7)
    ax.set_ylim(-3, 7.5)


def constraints():
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.4))
    for f, ax in zip((panel_angle_segment, panel_distance_x, panel_bearing), axs):
        f(ax)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#d2d2d7")
    fig.suptitle("One vertex: the pointer, then a snap, then the locks", fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m18-constraints.png"), dpi=130)


def box(ax, x, y, w, h, text, fc, ec="#8e8e93", fs=8.5, weight="normal", dashed=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1.0, ls=(0, (4, 3)) if dashed else "-"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight=weight, color=INK, wrap=True)


def layers():
    fig, ax = plt.subplots(figsize=(12, 6.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.6)
    ax.axis("off")

    ax.text(0.1, 6.35, "Front ends", fontsize=10, weight="bold", color=INK)
    box(ax, 0.1, 5.25, 3.7, 0.9, "edit.html canvas (now)\npointer, panels, coordinate table", "#e8f0fe", weight="bold")
    box(ax, 4.1, 5.25, 3.7, 0.9, "desktop window (egui, later)", "#f5f5f7", dashed=True)
    box(ax, 8.1, 5.25, 3.7, 0.9, "notebook widget, R or Python (later)", "#f5f5f7", dashed=True)

    ax.text(0.1, 4.85, "Engine: no input or output, no DOM; a crate when a second front end needs it",
            fontsize=10, weight="bold", color=INK)
    eng = [
        ("document\nfeatures in the edit\nframe, source kept", 0.1),
        ("snap\nvertex, segment, middle,\nintersection, grid", 2.5),
        ("constrain\nd, a, x, y, bearing,\nperpendicular, parallel", 4.9),
        ("operations\nmove, insert, delete,\nadd, remove, batch", 7.3),
        ("log\ninvertible, ordered,\nreplayable", 9.7),
    ]
    for t, x in eng:
        box(ax, x, 3.35, 2.2, 1.25, t, "#eef7ee")
    for x in (2.3, 4.7, 7.1, 9.5):
        ax.annotate("", (x + 0.2, 3.97), (x, 3.97), arrowprops=dict(arrowstyle="->", color=MUTED))

    ax.text(0.1, 2.95, "Slots: decided later, each one swappable", fontsize=10, weight="bold", color=INK)
    slots = [
        ("source\nGeoJSON now; GeoParquet\n(DuckDB page), FlatGeobuf", 0.1),
        ("frame\nlocal plane now; a CRS\n(proj4rs, terrio-crs)", 3.05),
        ("underlay\nCOG warped to the frame\n(wxy-warp in wasm)", 6.0),
        ("store and write\ndownload now; the log as\na table; apply to source", 8.95),
    ]
    for t, x in slots:
        box(ax, x, 1.45, 2.85, 1.25, t, "#fff7ed", dashed=True)

    ax.text(0.1, 1.05, "Reuse before writing", fontsize=10, weight="bold", color=INK)
    ax.text(0.1, 0.45,
            "Rust: geo (closest point, intersections, boolean ops, simplify, validity), rstar (snap index), "
            "robust (exact predicates), geojson, geozero, geoarrow\n"
            "JavaScript: none needed yet; Terra Draw, Leaflet-Geoman and OpenLayers' Snap and Modify "
            "cover web-map drawing, not typed constraints",
            fontsize=8.5, color=INK, va="center")
    fig.savefig(os.path.join(OUT, "m18-layers.png"), dpi=130, bbox_inches="tight")


if __name__ == "__main__":
    constraints()
    layers()
