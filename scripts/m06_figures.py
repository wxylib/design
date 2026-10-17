"""Figures for docs/m06-index-space.md.

Index space against coordinate space for the grids on the playproj pages
(hypertidy/playproj: indexspace.html, grids.html, regular.html), drawn from
small numpy ports of the same constructions. Spherical earth throughout:
these are pictures, not fixtures.

    python3 -m pip install numpy matplotlib
    python3 scripts/m06_figures.py path/to/coastline-110m.json

The coastline file is playproj's data/coastline-110m.json (Natural Earth
110m, flat [lon, lat, lon, lat, ...] lists); without it the maps have no
coast.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection

D2R = np.pi / 180.0
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "img")
CMAP = "viridis"

COAST = []
if len(sys.argv) > 1:
    with open(sys.argv[1]) as f:
        COAST = [np.asarray(c).reshape(-1, 2) for c in json.load(f)]


# --------------------------------------------------------------- sphere

def destination(lon0, lat0, c, az):
    """Point at angular distance c (radians) and azimuth az from lon0, lat0."""
    p0, l0 = lat0 * D2R, lon0 * D2R
    lat = np.arcsin(np.sin(p0) * np.cos(c) + np.cos(p0) * np.sin(c) * np.cos(az))
    lon = l0 + np.arctan2(np.sin(az) * np.sin(c) * np.cos(p0),
                          np.cos(c) - np.sin(p0) * np.sin(lat))
    return wrap(lon / D2R), lat / D2R


def wrap(lon):
    return (lon + 180.0) % 360.0 - 180.0


def ortho(lon, lat, lon0, lat0):
    """Orthographic x, y and a visibility mask."""
    l, p = (lon - lon0) * D2R, lat * D2R
    p0 = lat0 * D2R
    x = np.cos(p) * np.sin(l)
    y = np.cos(p0) * np.sin(p) - np.sin(p0) * np.cos(p) * np.cos(l)
    vis = np.sin(p0) * np.sin(p) + np.cos(p0) * np.cos(p) * np.cos(l) > 0
    return x, y, vis


def field(lon, lat):
    """A smooth made-up field that belongs to the place, not the index."""
    return (np.cos(lat * D2R) ** 2 + 0.25 * np.sin(3 * lon * D2R) * np.cos(2 * lat * D2R))


# ---------------------------------------------------------------- grids
# Each returns vertex arrays lon, lat shaped (nj + 1, ni + 1), as ROMS's
# psi points or CF bounds collapsed to corners.

def fan(ni=24, lon0=150.4, lat0=-33.2, bearing=105, spread=90, r0=0.9, r1=18):
    """playproj js/roms.js fan(): log-polar in stereographic radius."""
    q0 = np.log(2 * np.tan(r0 * D2R / 2))
    q1 = np.log(2 * np.tan(r1 * D2R / 2))
    a = spread * D2R
    nj = max(4, round(ni * (q1 - q0) / a))
    u = np.linspace(0, 1, ni + 1)
    v = np.linspace(0, 1, nj + 1)
    U, V = np.meshgrid(u, v)
    c = 2 * np.arctan(np.exp(q0 + (q1 - q0) * V) / 2)
    return destination(lon0, lat0, c, bearing * D2R + (U - 0.5) * a)


def merc_y(lat):
    return np.log(np.tan(np.pi / 4 + lat * D2R / 2))


def merc_lat(y):
    return (2 * np.arctan(np.exp(y)) - np.pi / 2) / D2R


def ring(ni=48, lat0=-78, lat1=-30, lon0=20):
    """playproj js/roms.js southernOcean(): periodic in i, Mercator in j."""
    y0, y1 = merc_y(lat0), merc_y(lat1)
    nj = max(4, round(ni * (y1 - y0) / (2 * np.pi)))
    U, V = np.meshgrid(np.linspace(0, 1, ni + 1), np.linspace(0, 1, nj + 1))
    return wrap(lon0 + 360 * U), merc_lat(y0 + (y1 - y0) * V)


def rotated(plon=-162.0, plat=39.25, win=(-28.375, 18.155, -23.375, 21.835), step=2.0):
    """CF rotated_latitude_longitude (PROJ ob_tran): EURO-CORDEX domain."""
    rl = np.arange(win[0], win[1] + 1e-9, step)
    rp = np.arange(win[2], win[3] + 1e-9, step)
    RL, RP = np.meshgrid(rl * D2R, rp * D2R)
    pp = plat * D2R
    lat = np.arcsin(np.cos(pp) * np.cos(RP) * np.cos(RL) + np.sin(pp) * np.sin(RP))
    lon = np.arctan2(np.cos(RP) * np.sin(RL),
                     np.sin(pp) * np.cos(RP) * np.cos(RL) - np.cos(pp) * np.sin(RP))
    return wrap(lon / D2R + plon + 180.0), lat / D2R


CUBE = [  # centre, east, north for each face, as in FV3's numbering
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
]


def cube_face(f, n=8):
    """Equiangular gnomonic face f of a cubed sphere (FV3 style)."""
    c, e, nn = (np.asarray(v, float) for v in CUBE[f])
    t = np.tan(np.linspace(-np.pi / 4, np.pi / 4, n + 1))
    X, Y = np.meshgrid(t, t)
    p = c[None, None] + X[..., None] * e + Y[..., None] * nn
    p /= np.linalg.norm(p, axis=-1, keepdims=True)
    return np.arctan2(p[..., 1], p[..., 0]) / D2R, np.arcsin(p[..., 2]) / D2R


def geos(n=20, lon0=-75.0, h=35786023.0, r=6378137.0, smax=0.1515):
    """Equal steps of scan angle from a geostationary satellite (sphere,
    sweep x gimbal as PROJ's geos +sweep=x). Off-disc vertices are NaN."""
    s = np.linspace(-smax, smax, n + 1)
    X, Y = np.meshgrid(s, s[::-1])
    H = (h + r) / r
    vz = np.tan(Y)
    vy = np.tan(X) * np.hypot(1.0, vz)
    d = np.stack([-np.ones_like(X), vy, vz], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    b = H * d[..., 0]
    disc = b * b - (H * H - 1)
    t = -b - np.sqrt(np.where(disc > 0, disc, np.nan))
    p = np.array([H, 0, 0]) + t[..., None] * d
    lon = np.arctan2(p[..., 1], p[..., 0]) / D2R + lon0
    lat = np.arcsin(np.clip(p[..., 2], -1, 1)) / D2R
    return wrap(lon), lat


# --------------------------------------------------------------- drawing

def centres(a):
    return 0.25 * (a[:-1, :-1] + a[1:, :-1] + a[:-1, 1:] + a[1:, 1:])


def cell_polys(x, y):
    q = np.stack([np.stack([x[:-1, :-1], y[:-1, :-1]], -1),
                  np.stack([x[:-1, 1:], y[:-1, 1:]], -1),
                  np.stack([x[1:, 1:], y[1:, 1:]], -1),
                  np.stack([x[1:, :-1], y[1:, :-1]], -1)], -2)
    return q.reshape(-1, 4, 2)


def draw_index(ax, lon, lat, offset=(0, 0), norm=None):
    nj, ni = lon.shape[0] - 1, lon.shape[1] - 1
    I, J = np.meshgrid(np.arange(ni + 1) + offset[0], np.arange(nj + 1) + offset[1])
    v = field(centres_lonlat(lon, lat)[0], centres_lonlat(lon, lat)[1])
    pc = PolyCollection(cell_polys(I, J), array=v.ravel(), cmap=CMAP, norm=norm,
                        edgecolor="white", linewidth=0.3)
    ax.add_collection(pc)


def centres_lonlat(lon, lat):
    """Cell centres as the mean of corner unit vectors."""
    x = np.cos(lat * D2R) * np.cos(lon * D2R)
    y = np.cos(lat * D2R) * np.sin(lon * D2R)
    z = np.sin(lat * D2R)
    cx, cy, cz = centres(x), centres(y), centres(z)
    return np.arctan2(cy, cx) / D2R, np.arctan2(cz, np.hypot(cx, cy)) / D2R


def draw_globe(ax, lon0, lat0):
    t = np.linspace(0, 2 * np.pi, 361)
    ax.fill(np.cos(t), np.sin(t), color="#eef2f6", zorder=0)
    ax.plot(np.cos(t), np.sin(t), color="#8a96a3", lw=0.6)
    for g in np.arange(-180, 180, 30):
        la = np.linspace(-90, 90, 181)
        x, y, vis = ortho(np.full_like(la, g), la, lon0, lat0)
        ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan), color="#c9d1da", lw=0.4)
    for g in np.arange(-60, 90, 30):
        lo = np.linspace(-180, 180, 361)
        x, y, vis = ortho(lo, np.full_like(lo, g), lon0, lat0)
        ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan), color="#c9d1da", lw=0.4)
    for c in COAST:
        x, y, vis = ortho(c[:, 0], c[:, 1], lon0, lat0)
        ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan), color="#5b6570", lw=0.5)


def draw_cells_on_globe(ax, lon, lat, lon0, lat0, norm=None):
    x, y, vis = ortho(lon, lat, lon0, lat0)
    clon, clat = centres_lonlat(lon, lat)
    v = field(clon, clat).ravel()
    ok = (vis[:-1, :-1] & vis[1:, :-1] & vis[:-1, 1:] & vis[1:, 1:]).ravel()
    ok &= np.isfinite(v)
    polys = cell_polys(x, y)[ok]
    pc = PolyCollection(polys, array=v[ok], cmap=CMAP, norm=norm, edgecolor="white",
                        linewidth=0.25, zorder=2)
    ax.add_collection(pc)


def tidy(ax, title=None):
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, fontsize=9, loc="left")


def six_grids():
    norm = matplotlib.colors.Normalize(-0.25, 1.25)
    fig, axs = plt.subplots(2, 5, figsize=(15, 6.4),
                            gridspec_kw={"height_ratios": [1, 1.15]})
    panels = [
        ("Coastal fan (ROMS)", fan(), (152.0, -36.0), "R3: 2D lon/lat"),
        ("Circumpolar ring", ring(), (20.0, -70.0), "R3, periodic in i"),
        ("Rotated pole (CORDEX)", rotated(), (10.0, 50.0), "R1 in ob_tran"),
        ("Cubed sphere", None, (-30.0, 30.0), "6 x R1 in gnom"),
        ("Geostationary disc", geos(), (-75.0, 0.0), "R1 in geos"),
    ]
    for k, (title, g, (lon0, lat0), rung) in enumerate(panels):
        top, bot = axs[0, k], axs[1, k]
        if g is not None:
            lon, lat = g
            draw_index(top, lon, lat, norm=norm)
            nj, ni = lon.shape[0] - 1, lon.shape[1] - 1
            top.set_xlim(-0.5, ni + 0.5)
            top.set_ylim(-0.5, nj + 0.5)
            draw_globe(bot, lon0, lat0)
            draw_cells_on_globe(bot, lon, lat, lon0, lat0, norm=norm)
        else:
            n = 8
            net = {0: (1, 1), 1: (2, 1), 2: (1, 2), 3: (3, 1), 4: (0, 1), 5: (1, 0)}
            draw_globe(bot, lon0, lat0)
            for f in range(6):
                lon, lat = cube_face(f, n)
                ox, oy = net[f]
                draw_index(top, lon, lat, offset=(ox * n, oy * n), norm=norm)
                top.text(ox * n + n / 2, oy * n + n / 2, str(f), ha="center", va="center",
                         color="white", fontsize=9, weight="bold")
                draw_cells_on_globe(bot, lon, lat, lon0, lat0, norm=norm)
            top.set_xlim(-0.5, 4 * n + 0.5)
            top.set_ylim(-0.5, 3 * n + 0.5)
        if title == "Circumpolar ring":
            nj = lon.shape[0] - 1
            top.annotate("", xy=(-0.4, nj / 2), xytext=(lon.shape[1] - 0.6, nj / 2),
                         arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1,
                                         connectionstyle="arc3,rad=0.35"))
            top.text(lon.shape[1] / 2, nj * 1.18, "i = ni is i = 0", ha="center",
                     color="#c0392b", fontsize=8)
            top.set_ylim(-0.5, nj * 1.4)
        tidy(top, f"{title}\nindex space ({rung})")
        tidy(bot, "coordinate space (orthographic)")
        bot.set_xlim(-1.05, 1.05)
        bot.set_ylim(-1.05, 1.05)
        if title.startswith("Coastal fan"):
            x, y, _ = ortho(lon, lat, lon0, lat0)
            pad = 0.08
            bot.set_xlim(x.min() - pad, x.max() + pad)
            bot.set_ylim(y.min() - pad, y.max() + pad)
            tidy(bot, "coordinate space (orthographic, zoomed)")
    fig.suptitle("The same cells, the same colours: as the array has them (top) and as the earth has them (bottom)",
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m06-index-coordinate.png"), dpi=110)
    plt.close(fig)


# ------------------------------------------------------------- vertical

def stretch4(s, ts=7.0, tb=2.0):
    """ROMS Vstretching 4 (Shchepetkin 2010)."""
    c = (1 - np.cosh(ts * s)) / (np.cosh(ts) - 1)
    return (np.exp(tb * c) - 1) / (1 - np.exp(-tb))


def depth_vt2(s, h, hc=250.0, zeta=0.0):
    """ROMS Vtransform 2: CF ocean_s_coordinate_g2."""
    z0 = (hc * s + h * stretch4(s)) / (hc + h)
    return zeta + (zeta + h) * z0


def section():
    N = 20
    lon, lat = fan(ni=24)
    col = lon.shape[1] // 2
    clon, clat = lon[:, col], lat[:, col]
    # distance along the section, km
    p = np.stack([np.cos(clat * D2R) * np.cos(clon * D2R),
                  np.cos(clat * D2R) * np.sin(clon * D2R), np.sin(clat * D2R)], -1)
    seg = np.arccos(np.clip((p[1:] * p[:-1]).sum(-1), -1, 1)) * 6371.0
    dist = np.concatenate([[0], np.cumsum(seg)])
    # an idealised shelf, slope and abyss, metres
    h = 15 + 135 * np.tanh(dist / 60.0) + 4300 / (1 + np.exp(-(dist - 260) / 45.0))
    s_w = (np.arange(N + 1) - N) / N
    zw = depth_vt2(s_w[:, None], h[None, :])          # (N + 1, nj + 1)
    D, _ = np.meshgrid(dist, s_w)
    zc = 0.25 * (zw[1:, 1:] + zw[:-1, 1:] + zw[1:, :-1] + zw[:-1, :-1])
    dc = 0.5 * (dist[1:] + dist[:-1])
    temp = 1 + 8 * np.exp(zc / 1500.0) + 13 * np.exp(zc / 250.0) + 1.5 * np.sin(dc / 70.0)[None, :] * np.exp(zc / 600.0)
    norm = matplotlib.colors.Normalize(temp.min(), temp.max())

    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1, 1.6]})
    J, K = np.meshgrid(np.arange(len(dist)), np.arange(N + 1))
    a.add_collection(PolyCollection(cell_polys(J, K), array=temp.ravel(), cmap="magma",
                                    norm=norm, edgecolor="white", linewidth=0.3))
    a.set_xlim(-0.5, len(dist) - 0.5)
    a.set_ylim(-0.5, N + 0.5)
    a.set_aspect("equal")
    a.set_xlabel("j (eta_rho)")
    a.set_ylabel("k (s_rho)")
    a.set_title("index space: every (j, k) cell is a unit square", fontsize=9, loc="left")
    pc = PolyCollection(cell_polys(D, zw), array=temp.ravel(), cmap="magma", norm=norm,
                        edgecolor="white", linewidth=0.2)
    b.add_collection(pc)
    b.fill_between(dist, -h, -h.max() * 1.05, color="#b9a88f")
    b.set_xlim(0, dist.max())
    b.set_ylim(-h.max() * 1.05, 50)
    b.set_xlabel("distance offshore (km)")
    b.set_ylabel("z (m)")
    b.set_title("coordinate space: z = f(s, C(s), h, zeta, hc), CF ocean_s_coordinate_g2",
                fontsize=9, loc="left")
    fig.colorbar(pc, ax=b, label="made-up temperature", shrink=0.8)
    fig.suptitle("A ROMS section off New South Wales: N = 20 layers, Vtransform 2, Vstretching 4, theta_s 7, theta_b 2, hc 250",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "m06-roms-section.png"), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    six_grids()
    section()
