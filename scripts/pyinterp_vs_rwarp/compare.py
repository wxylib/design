"""pyinterp 2026.11.0 conservative regridding against rwarp's exact weights.

Run from this directory:
    cargo build --release
    ./target/release/pyinterp_vs_rwarp 1 5 && mv rwarp_out.bin r_1_5.bin
    ./target/release/pyinterp_vs_rwarp 0.25 1 && mv rwarp_out.bin r_025_1.bin
    python3 compare.py

The field is 2 + cos(lat)^2 cos(2 lon) at cell centres (amplitude 1).
Both sides use cells bounded by meridians and parallels on the unit sphere.
"""
import time

import numpy as np
import pyinterp.regrid as regrid
from pyinterp.core.geometry.geographic import Spheroid


def centres(n, start, res):
    return start + (np.arange(n) + 0.5) * res


def run(sres, dres, rfile, spheroid=None):
    sx = centres(int(360 / sres), -180, sres)
    sy = centres(int(180 / sres), 90, -sres)
    dx = centres(int(360 / dres), -180, dres)
    dy = centres(int(180 / dres), 90, -dres)
    lon, lat = np.meshgrid(np.radians(sx), np.radians(sy))
    field = 2 + np.cos(lat) ** 2 * np.cos(2 * lon)  # (lat, lon)

    def bounds(c, r):
        return np.column_stack((c - r / 2, c + r / 2))

    args = (field.T, bounds(sx, sres), bounds(sy, sres),
            bounds(dx, dres), bounds(dy, dres))
    for nt in (1, 0):
        t = time.perf_counter()
        for _ in range(20):
            out = regrid.conservative(*args, num_threads=nt, spheroid=spheroid)
        ms = (time.perf_counter() - t) / 20 * 1e3
        print(f"{sres} -> {dres}, threads={nt or 'all'}: {ms:.2f} ms")
    ref = np.fromfile(rfile, "<f8").reshape(len(dy), len(dx))
    diff = np.abs(out.T - ref)
    label = "WGS84" if spheroid is not None else "sphere"
    print(f"  {label}: max |pyinterp - rwarp| {diff.max():.2e}")
    return out


run(1, 5, "r_1_5.bin")
sphere = run(0.25, 1, "r_025_1.bin")
wgs84 = run(0.25, 1, "r_025_1.bin", spheroid=Spheroid())
print(f"sphere vs WGS84 (authalic): max {np.abs(wgs84 - sphere).max():.2e}")
