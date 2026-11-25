"""Cost before read: tile byte sizes for every level of every 2024 GHRSST
MUR COG, from the headers only (one 128 KB range GET per file), plus the
level 0 sizes from the store's flat refs table to check them against.

usage: python harvest.py REFS_PARQUET OUT_JSON"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pyarrow.parquet as pq

from cogtiles import Cog

refs, out = sys.argv[1], sys.argv[2]
t = pq.read_table(refs, columns=["dim_0", "dim_1", "dim_2", "path", "size"])
d0 = t["dim_0"].to_numpy()
paths = {}
for i, p in zip(d0, t["path"].to_pylist()):
    paths.setdefault(int(i), p)
lvl0 = np.zeros((366, 36, 71), dtype=np.int64)
lvl0[d0, t["dim_1"].to_numpy(), t["dim_2"].to_numpy()] = t["size"].to_numpy()


def one(day):
    url = paths[day].replace("/vsicurl/", "")
    c = Cog(url)
    levels = []
    for k in range(len(c.ifds)):
        lv = c.level(k)
        ncol = -(-lv["width"] // lv["tw"])
        levels.append(dict(width=lv["width"], height=lv["height"], ncol=ncol,
                           sizes=[int(s) for s in lv["sizes"]]))
    return day, url, levels


with ThreadPoolExecutor(16) as ex:
    res = sorted(ex.map(one, range(366)))

agree = all(np.array_equal(np.array(r[2][0]["sizes"]).reshape(36, 71), lvl0[r[0]]) for r in res)
json.dump({"agree_level0_with_refs": bool(agree),
           "days": [{"day": d, "url": u, "levels": lv} for d, u, lv in res]}, open(out, "w"))
print("days", len(res), "level-0 sizes equal refs table:", agree, flush=True)
os._exit(0)
