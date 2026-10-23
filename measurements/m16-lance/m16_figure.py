"""m16_figure.py -- history size of one year of daily commits, per store.

Usage: python m16_figure.py MEASUREMENTS_DIR OUT.png
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d, out = sys.argv[1:3]
j = lambda f: json.load(open(os.path.join(d, f)))
lance = j("load-log.json")
frag = j("frag-log.json")
rows = [
    ("Flat Parquet export (no history)", 5.3e6),
    ("Lance, all versions kept", sum(lance["bytes"].values())),
    ("Parquet fragments + create-only manifest", sum(frag["bytes"].values())),
    ("Icechunk, manifest split 1 day", j("icechunk-split1-log.json")["bytes"]),
    ("Icechunk, manifest split 30 days", j("icechunk-split30-log.json")["bytes"]),
    ("Icechunk, manifest split 365 days", j("icechunk-split365-log.json")["bytes"]),
]
fig, ax = plt.subplots(figsize=(8, 3.4), dpi=150)
y = range(len(rows))[::-1]
v = [r[1] / 1e6 for r in rows]
ax.barh(list(y), v, color="#2a78d6", height=0.6)
ax.set_xscale("log")
ax.set_yticks(list(y), [r[0] for r in rows], color="#333333")
for yi, vi in zip(y, v):
    ax.text(vi * 1.12, yi, f"{vi:,.1f} MB", va="center", fontsize=8, color="#333333")
ax.set_xlim(1, 1e4)
ax.set_xlabel("bytes on disk after bulk + 184 daily commits + 1 rescan (MB, log scale)", color="#555555")
ax.set_title("GHRSST MUR analysed_sst 2024, 935,496 refs: cost of keeping the history",
             fontsize=10, loc="left", color="#111111")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color("#bbbbbb"); ax.spines["bottom"].set_color("#bbbbbb")
ax.tick_params(colors="#555555", labelsize=8)
ax.grid(axis="x", color="#eeeeee", linewidth=0.6); ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(out)
