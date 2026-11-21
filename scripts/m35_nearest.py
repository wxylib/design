"""m35: how often does "nearest cell centre in degrees" differ from
"nearest cell centre on the ground" on a triangular grid?

Cell centres of an equilateral triangle tiling (a honeycomb lattice) are
laid out on a local tangent plane at a latitude, written as longitude and
latitude in degrees, and queried at random points. The answer depends
only on the latitude (the cos(lat) stretch of a degree of longitude) and
the lattice orientation, not on the cell size. numpy only.

Run: python3 scripts/m35_nearest.py
"""
import numpy as np

R = 6371229.0  # ICON's sphere, metres
EDGE = 9880.0  # triangle edge for a 6.5 km (root of area) grid


def centres(n, edge, rot):
    """Centroids of an equilateral triangle tiling, rotated by rot radians."""
    h = edge * np.sqrt(3) / 2
    i, j = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    x0 = (i + 0.5 * j).ravel() * edge
    y0 = j.ravel() * h
    up = np.c_[x0 + edge / 2, y0 + h / 3]
    down = np.c_[x0 + edge, y0 + 2 * h / 3]
    p = np.r_[up, down]
    c, s = np.cos(rot), np.sin(rot)
    return p @ np.array([[c, s], [-s, c]])


def nearest(p, q):
    d = ((q[:, None, :] - p[None, :, :]) ** 2).sum(-1)
    return d.argmin(1), np.sqrt(d.min(1))


def run(lat, rot, rng, nq=4000):
    p = centres(12, EDGE, rot)
    q = rng.uniform(-3 * EDGE, 3 * EDGE, size=(nq, 2))
    k = np.cos(np.deg2rad(lat))
    deg = lambda a: np.c_[np.rad2deg(a[:, 0] / (R * k)), np.rad2deg(a[:, 1] / R)]
    i_m, d_m = nearest(p, q)
    i_d, _ = nearest(deg(p), deg(q))
    wrong = i_m != i_d
    extra = np.sqrt(((p[i_d] - q) ** 2).sum(1)) - d_m
    return wrong.mean(), extra[wrong].max() if wrong.any() else 0.0


if __name__ == "__main__":
    rng = np.random.default_rng(35)
    print("lat  different_cell_pct  worst_extra_distance_km")
    for lat in (0, 38, 50, 60, 70, 80):
        f, e = zip(*(run(lat, r, rng) for r in np.linspace(0, np.pi / 3, 7)[:-1]))
        print(f"{lat:3d}  {100 * np.mean(f):6.1f}  {max(e) / 1000:6.2f}")
