"""Figures and numbers for docs/m08-point-clouds.md.

Two figures:

1. m08-scan-rungs.png: one synthetic terrestrial scan drawn twice. As the
   scanner records it, a range image on a regular (azimuth, elevation)
   grid (R1 in the sensor's angle frame), and as a LAS file keeps it, an
   unordered list of x, y, z returns (R6).
2. m08-copc-octree.png: PDAL's autzen-classified COPC file read over HTTP.
   The octree node footprints (the chunk scheme), the coarse levels of the
   points, and those points binned to a 30 ft grid (an R6 to R1 move). The file is in
   EPSG:2992 (international feet) plus NAVD88 height (US survey feet).

The COPC numbers quoted in the musing (header, hierarchy size, nodes,
points and bytes per level) are printed by `hierarchy()`, which reads the
header and the hierarchy pages with plain HTTP range requests. Point
decoding uses laspy with the lazrs backend (laz-rs underneath).

    python3 -m pip install numpy matplotlib "laspy[lazrs]" requests
    python3 scripts/m08_figures.py
"""

import collections
import os
import struct
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "img")
URL = "https://s3.amazonaws.com/hobu-lidar/autzen-classified.copc.laz"
CMAP = "viridis"


def get_range(offset, length):
    req = urllib.request.Request(
        URL, headers={"Range": f"bytes={offset}-{offset + length - 1}"}
    )
    return urllib.request.urlopen(req).read()


def hierarchy():
    """Header, COPC info VLR and every hierarchy entry, by range reads."""
    head = get_range(0, 375 + 54 + 160)
    fmt = head[104] & 0x3F
    scale = struct.unpack_from("<3d", head, 131)
    offset = struct.unpack_from("<3d", head, 155)
    npoints = struct.unpack_from("<Q", head, 247)[0]
    cx, cy, cz, half, spacing, hoff, hsize, _, _ = struct.unpack_from(
        "<5d2Q2d", head, 375 + 54
    )
    print(f"point format {fmt}, scale {scale}, offset {offset}")
    print(f"{npoints} points, cube half size {half:.1f} ft, spacing {spacing:.2f} ft")
    print(f"root hierarchy page: {hsize} bytes at offset {hoff}")
    pages, nodes, requests = [(hoff, hsize)], [], 1
    while pages:
        off, size = pages.pop()
        page = get_range(off, size)
        requests += 1
        for i in range(size // 32):
            d, x, y, z, eoff, nbytes, count = struct.unpack_from("<4iQii", page, i * 32)
            if count == -1:
                pages.append((eoff, nbytes))
            else:
                nodes.append((d, x, y, z, eoff, nbytes, count))
    print(f"{requests} range requests (header included), {len(nodes)} entries")
    levels = collections.defaultdict(lambda: [0, 0, 0])
    for d, _, _, _, _, nbytes, count in nodes:
        if count > 0:
            levels[d][0] += 1
            levels[d][1] += count
            levels[d][2] += nbytes
    print("level  nodes  points  bytes  node edge (ft)")
    for d in sorted(levels):
        n, c, b = levels[d]
        print(f"{d}  {n}  {c}  {b}  {2 * half / 2**d:.1f}")
    return (cx, cy, cz, half), nodes


def scan():
    """A synthetic terrestrial scan: ground, a wall and a sphere."""
    az = np.radians(np.linspace(-60, 60, 241))
    el = np.radians(np.linspace(-30, 20, 101))
    A, E = np.meshgrid(az, el)
    dx, dy, dz = np.cos(E) * np.cos(A), np.cos(E) * np.sin(A), np.sin(E)
    r = np.full(A.shape, np.inf)
    # ground plane z = -1.5
    t = np.where(dz < 0, -1.5 / np.where(dz < 0, dz, -1), np.inf)
    r = np.minimum(r, t)
    # wall x = 12, |y| < 4, z < 3
    t = 12.0 / np.where(dx > 0, dx, np.nan)
    hit = (np.abs(t * dy) < 4) & (t * dz < 3) & (t * dz > -1.5)
    r = np.where(hit & (t < r), t, r)
    # sphere centre (6, -5, 0), radius 1.5
    c = np.array([6.0, -5.0, 0.0])
    b = dx * c[0] + dy * c[1] + dz * c[2]
    disc = b**2 - (c @ c - 1.5**2)
    t = np.where(disc > 0, b - np.sqrt(np.maximum(disc, 0)), np.inf)
    r = np.where((t > 0) & (t < r), t, r)
    r[r > 30] = np.nan
    return A, E, r, dx * r, dy * r, dz * r


def fig_scan():
    A, E, r, x, y, z = scan()
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    im = ax[0].pcolormesh(np.degrees(A), np.degrees(E), r, cmap=CMAP, shading="nearest")
    ax[0].set_xlabel("azimuth (degrees): column index")
    ax[0].set_ylabel("elevation (degrees): row index")
    ax[0].set_title("As scanned: range on a regular angle grid (R1)")
    fig.colorbar(im, ax=ax[0], label="range (m)")
    ok = np.isfinite(r)
    rng = np.random.default_rng(1)
    order = rng.permutation(ok.sum())
    sc = ax[1].scatter(x[ok][order], y[ok][order], c=r[ok][order], s=1.5, cmap=CMAP)
    ax[1].plot(0, 0, "r^", ms=8)
    ax[1].set_aspect("equal")
    ax[1].set_xlabel("x (m)")
    ax[1].set_ylabel("y (m)")
    ax[1].set_title("As a LAS file keeps it: unordered x, y, z (R6)")
    fig.colorbar(sc, ax=ax[1], label="range (m)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m08-scan-rungs.png"), dpi=110)
    plt.close(fig)


def fig_copc(cube, nodes):
    import laspy

    cx, cy, _, half = cube
    with laspy.CopcReader.open(URL) as reader:
        pts = reader.query(level=range(0, 4))
    x, y, z = np.asarray(pts.x), np.asarray(pts.y), np.asarray(pts.z)
    print(f"levels 0 to 3: {len(x)} points")
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    keep = np.random.default_rng(2).choice(len(x), 120000, replace=False)
    ax[0].scatter(x[keep], y[keep], c=z[keep], s=0.2, cmap=CMAP)
    seen = set()
    colours = plt.get_cmap("plasma")
    for d, kx, ky, _, _, _, count in sorted(nodes):
        if count <= 0 or (d, kx, ky) in seen:
            continue
        seen.add((d, kx, ky))
        edge = 2 * half / 2**d
        ax[0].add_patch(Rectangle((cx - half + kx * edge, cy - half + ky * edge), edge, edge,
                                  fill=False, lw=1.6 - 0.25 * d, ec=colours(d / 6)))
    ax[0].set_xlim(x.min() - 150, x.max() + 150)
    ax[0].set_ylim(y.min() - 150, y.max() + 150)
    ax[0].set_aspect("equal")
    ax[0].set_title("Octree nodes (levels 0 to 5) over levels 0 to 3")
    # R6 to R1: bin to a 30 ft grid, keeping the maximum z and the count
    res = 30.0
    x0, y1 = np.floor(x.min() / res) * res, np.ceil(y.max() / res) * res
    col = ((x - x0) // res).astype(int)
    row = ((y1 - y) // res).astype(int)
    shape = (row.max() + 1, col.max() + 1)
    flat = row * shape[1] + col
    zmax = np.full(shape[0] * shape[1], np.nan)
    order = np.argsort(z)
    zmax[flat[order]] = z[order]
    count = np.bincount(flat, minlength=zmax.size).astype(float)
    count[count == 0] = np.nan
    extent = (x0, x0 + shape[1] * res, y1 - shape[0] * res, y1)
    im = ax[1].imshow(zmax.reshape(shape), extent=extent, cmap=CMAP)
    ax[1].set_title("Binned to 30 ft: maximum z (R1)")
    fig.colorbar(im, ax=ax[1], shrink=0.7, label="z (US survey ft)")
    im = ax[2].imshow(count.reshape(shape), extent=extent, cmap="magma")
    ax[2].set_title("Binned to 30 ft: points per cell")
    fig.colorbar(im, ax=ax[2], shrink=0.7, label="points")
    for a in ax:
        a.set_xticks([])
        a.set_yticks([])
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m08-copc-octree.png"), dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_scan()
    cube, nodes = hierarchy()
    fig_copc(cube, nodes)
