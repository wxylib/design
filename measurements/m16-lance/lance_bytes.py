"""lance_bytes.py -- read oracle windows through the Lance refs, check against GDAL.

For each window in the store's manifest.json: resolve the chunk refs from
the Lance chunk table at a tag, through the remap view (target s3direct),
fetch each byte range, decode (zstd, then TIFF horizontal differencing),
assemble the window, and compare its SHA-256 with (a) the manifest, written
earlier by GDAL 3.13 on the plan VRT, and (b) osgeo.gdal reading the same
window now from the plan VRT with the gdal-s3direct remap applied to it.

Usage:
  python lance_bytes.py LANCE_DIR STORE_DIR [--tag rescan]
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request

import duckdb
import lance
import numcodecs
import numpy as np
from osgeo import gdal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lance_query import VIEW  # noqa: E402

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")


def sha(v):
    return hashlib.sha256(np.ascontiguousarray(v).astype(v.dtype.newbyteorder("<")).tobytes()).hexdigest()


def fetch(url, off, size):
    req = urllib.request.Request(url, headers={"Range": f"bytes={off}-{off + size - 1}"})
    with urllib.request.urlopen(req) as r:
        b = r.read()
    if len(b) != size:
        sys.exit(f"short read {url} {off} {size}: {len(b)}")
    return b


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ldir")
    p.add_argument("store")
    p.add_argument("--tag", default="rescan")
    a = p.parse_args()
    doc = json.load(open(os.path.join(a.store, "out", "flat", "arrays.json")))
    arr = json.load(open(os.path.join(a.ldir, "load-log.json")))["array"]
    meta = next(r for r in doc["arrays"] if r["array"] == arr)
    dt = np.dtype(meta["dtype"])
    cs = meta["chunks"]
    zstd = numcodecs.Zstd()
    man = json.load(open(os.path.join(a.store, "manifest.json")))

    uri = {k: os.path.join(a.ldir, f"{k}.lance") for k in ("sources", "placements", "remap", arr)}
    chunks = lance.dataset(uri[arr], version=a.tag)
    sources, placements, remap = (lance.dataset(uri[k]) for k in ("sources", "placements", "remap"))
    con = duckdb.connect()
    for n, d in (("chunks", chunks), ("sources", sources), ("placements", placements), ("remap", remap)):
        con.register(n, d)
    con.execute("CREATE VIEW refs AS " + VIEW.format(target="s3direct", array=arr))

    # the GDAL oracle: the plan VRT, remapped with the gdal-s3direct rows
    rules = con.execute("SELECT prefix, replacement FROM remap WHERE target = 'gdal-s3direct'").fetchall()
    xml = open(os.path.join(a.store, "out", "mdim.vrt")).read()
    for pre, rep in rules:
        xml = xml.replace(pre, rep)
    vrt = os.path.join(tempfile.mkdtemp(), "mdim-s3direct.vrt")
    open(vrt, "w").write(xml)
    garr = gdal.OpenEx(vrt, gdal.OF_MULTIDIM_RASTER).GetRootGroup().OpenMDArray(arr)

    res = {"tag": a.tag, "version": chunks.version, "gdal": gdal.__version__, "windows": {}}
    for name, w in man["oracle"].items():
        st, cn = w["start"], w["count"]
        lo = [s // c for s, c in zip(st, cs)]
        hi = [(s + n - 1) // c for s, n, c in zip(st, cn, cs)]
        where = " AND ".join(f"dim_{i} BETWEEN {lo[i]} AND {hi[i]}" for i in range(3))
        rows = con.execute(f"SELECT dim_0, dim_1, dim_2, path, \"offset\", size FROM refs WHERE {where}").fetchall()
        t0 = time.time()
        out = np.full(cn, int(meta["fill"]), dtype=dt)
        for d0, d1, d2, path, off, size in rows:
            raw = zstd.decode(fetch(path, off, size))
            tile = np.frombuffer(raw, dtype=dt).reshape(cs)
            tile = np.cumsum(tile, axis=-1, dtype=dt)  # undo Predictor=2 (wraps like the codec)
            g0 = [d0 * cs[0], d1 * cs[1], d2 * cs[2]]
            sl_out, sl_t = [], []
            for i in range(3):
                a0 = max(st[i], g0[i])
                a1 = min(st[i] + cn[i], g0[i] + cs[i])
                sl_out.append(slice(a0 - st[i], a1 - st[i]))
                sl_t.append(slice(a0 - g0[i], a1 - g0[i]))
            out[tuple(sl_out)] = tile[tuple(sl_t)]
        tl = time.time() - t0
        t0 = time.time()
        g = garr.ReadAsArray(array_start_idx=st, count=cn)
        tg = time.time() - t0
        h = sha(out)
        res["windows"][name] = {"chunks": len(rows), "lance_sha": h[:16],
                                "manifest_matches": h == w["sha256"],
                                "gdal_now_matches": h == sha(g),
                                "lance_seconds": round(tl, 2), "gdal_seconds": round(tg, 2)}
        print(name, res["windows"][name])
    json.dump(res, open(os.path.join(a.ldir, f"bytes-{a.tag}.json"), "w"), indent=1)
    if not all(v["manifest_matches"] and v["gdal_now_matches"] for v in res["windows"].values()):
        sys.exit("MISMATCH")


if __name__ == "__main__":
    main()
