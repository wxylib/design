"""Figure for m21 (conservative regridding examples).

    python scripts/m21_figures.py

Left: one EPSG:3031 25 km target cell over 0.1 degree lon/lat source cells
off Prydz Bay, each source cell coloured by the fraction of it the target
cell takes (rwarp exact_weights, densify 4). The entries and the outline
come from measurements/m21-conservative (cargo run --release there first).

Right: the ACCESS-OM2 1 degree tripolar ocean grid (as published with
ACCESS-CM2 in CMIP6 on Google Cloud), the corners of every cell north of
55N in north polar stereographic, showing the fold the grid's two northern
poles make over land.
"""

import os
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numcodecs
import numpy as np
from matplotlib.collections import PolyCollection

HERE = os.path.dirname(os.path.abspath(__file__))
MEAS = os.path.join(HERE, "..", "measurements", "m21-conservative")
OUT = os.path.join(HERE, "..", "docs", "img", "m21-cells.png")
CMIP6 = ("https://storage.googleapis.com/cmip6/CMIP6/CMIP/CSIRO-ARCCSS/"
         "ACCESS-CM2/historical/r1i1p1f1/Omon/tos/gn/v20191108")


def vertices(name):
    with urllib.request.urlopen(f"{CMIP6}/{name}/0.0.0") as r:
        raw = numcodecs.Blosc().decode(r.read())
    return np.frombuffer(raw, "<f8").reshape(300, 360, 4)


def cell_panel(ax):
    e = np.loadtxt(os.path.join(MEAS, "cell.txt"), skiprows=1)
    o = np.loadtxt(os.path.join(MEAS, "outline.txt"))
    lon = lambda c: 60 + 0.1 * c
    lat = lambda r: -60 - 0.1 * r
    polys = [[(lon(c), lat(r)), (lon(c + 1), lat(r)), (lon(c + 1), lat(r + 1)),
              (lon(c), lat(r + 1))] for c, r, _ in e]
    pc = PolyCollection(polys, array=e[:, 2], cmap="viridis",
                        edgecolors="white", linewidths=0.6)
    pc.set_clim(0, 1)
    ax.add_collection(pc)
    ring = np.vstack([o, o[:1]])
    ax.plot(lon(ring[:, 0]), lat(ring[:, 1]), color="#d62728", lw=1.6)
    ax.autoscale_view()
    ax.set_aspect(1 / np.cos(np.radians(lat(e[:, 1]).mean())))
    ax.set_xlabel("longitude (degrees)")
    ax.set_ylabel("latitude (degrees)")
    ax.set_title(f"One 25 km EPSG:3031 cell over 0.1 degree source cells\n"
                 f"{len(e)} weights, fraction of each source cell taken",
                 fontsize=10)
    plt.colorbar(pc, ax=ax, shrink=0.8, label="frac")


def tripolar_panel(ax):
    la, lo = vertices("vertices_latitude"), vertices("vertices_longitude")
    keep = la.min(axis=2) > 55
    r = 2 * np.tan(np.radians(90 - la[keep]) / 2)
    t = np.radians(lo[keep])
    x, y = r * np.sin(t), -r * np.cos(t)
    polys = np.stack([x, y], axis=-1)
    ax.add_collection(PolyCollection(polys, facecolors="none",
                                     edgecolors="#1f4e79", linewidths=0.25))
    ax.autoscale_view()
    ax.set_aspect(1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"ACCESS-OM2 tripolar cells north of 55N, from CF corners\n"
                 f"{keep.sum()} of 108000 cells, north polar stereographic",
                 fontsize=10)


fig, (a, b) = plt.subplots(1, 2, figsize=(11, 5.2))
cell_panel(a)
tripolar_panel(b)
fig.tight_layout()
fig.savefig(OUT, dpi=130)
print(OUT)
