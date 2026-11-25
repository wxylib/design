"""m36: cost of each plan before any read, then the read and the picture.

Joins the planner's keys (plans.jsonl, from plan/) with the tile byte sizes
harvested from the COG headers (harvest.py) for a Hovmoller at one
latitude, then fetches the per-axis plan for 2024 and one map slice at the
same level, and draws both from the bytes fetched.

usage: python hovmoller.py TILES_JSON OUT_DIR [LAT]"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from cogtiles import Cog

tiles_json, out_dir = sys.argv[1], sys.argv[2]
LAT = float(sys.argv[3]) if len(sys.argv) > 3 else -42.0
os.makedirs(out_dir, exist_ok=True)
T = json.load(open(tiles_json))["days"]
plans = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), "plans.jsonl"))]

# Row of LAT at level 0 (lat starts at 89.99, step -0.01), and its tile row per level.
row0 = int(round((89.99 - LAT) / 0.01))


def tile_row(k):
    return (row0 >> k) // 512


def row_in_tile(k):
    return (row0 >> k) % 512


def size(day, k, col):
    lv = T[day]["levels"][k]
    return lv["sizes"][tile_row(k) * lv["ncol"] + col]


per_day_mean = {}
rows = []
for p in plans:
    if not p["case"].startswith("hov"):
        continue
    days = int(p["case"].split("-")[-1][:-1])
    nrows = p["rows"]
    total = 0
    for k, col in p["cols"]:
        # exact for up to 366 days; beyond that, the 2024 mean per day times the rows read
        mean = per_day_mean.setdefault((k, col), np.mean([size(d, k, col) for d in range(366)]))
        if days <= 366:
            total += sum(size(d, k, col) for d in range(days))
        else:
            total += mean * nrows
    rows.append(dict(case=p["case"], rule=p["rule"], unit=p["time_unit"], levels=p["levels"],
                     tiles=p["chunks"], rows=nrows, mb=round(total / 1e6, 1), exact=days <= 366))

# What a level-0 read of the latitude row costs, as a plain array read would.
naive = sum(size(d, 0, c) for d in range(366) for c in range(71)) / 1e6
rows.append(dict(case="hov-world-366d", rule="level-0 slice", unit="-", levels=[0], tiles=366 * 71,
                 rows=366, mb=round(naive, 1), exact=True))
with open(os.path.join(out_dir, "costs.jsonl"), "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
        print(r)

# Read the per-axis 2024 plan: level 5, three tiles a day at LAT.
K = 5
hp = next(p for p in plans if p["case"] == "hov-world-366d" and p["rule"] == "per-axis" and p["time_unit"] == "day")
cols = sorted(c for k, c in hp["cols"] if k == K)
predicted = sum(size(d, K, c) for d in range(366) for c in cols)


def read_day(day):
    c = Cog(T[day]["url"])
    parts, got = [], 0
    for col in cols:
        a, n = c.tile(K, col, tile_row(K))
        got += n
        parts.append(a[row_in_tile(K)])
    return day, np.concatenate(parts)[: T[day]["levels"][K]["width"]], got


with ThreadPoolExecutor(16) as ex:
    res = sorted(ex.map(read_day, range(366)), key=lambda r: r[0])
hov = np.stack([r[1] for r in res])
fetched = sum(r[2] for r in res)
print("hovmoller tiles", 366 * len(cols), "predicted bytes", predicted, "fetched", fetched)

# Map slice: the same level, one day (2024-07-01), all six tiles.
mday = 182
c = Cog(T[mday]["url"])
lv = c.level(K)
ncol, nrow = -(-lv["width"] // 512), -(-lv["height"] // 512)
grid = np.full((nrow * 512, ncol * 512), -32768, dtype=np.int16)
for r in range(nrow):
    for col in range(ncol):
        a, _ = c.tile(K, col, r)
        grid[r * 512:(r + 1) * 512, col * 512:(col + 1) * 512] = a
smap = grid[: lv["height"], : lv["width"]]

np.save(os.path.join(out_dir, "hov.npy"), hov)
np.save(os.path.join(out_dir, "map.npy"), smap)
json.dump(dict(lat=LAT, level=K, tiles=366 * len(cols), predicted=predicted, fetched=fetched,
               map_day=mday, map_url=T[mday]["url"]), open(os.path.join(out_dir, "read.json"), "w"), indent=1)
os._exit(0)
