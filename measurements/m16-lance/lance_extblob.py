"""lance_extblob.py -- one blob column for refs and held bytes alike.

Lance's blob column stores each value either inline (the bytes, kind 0) or
as an external range (uri, position, size, kind 3), and `read_blobs`
resolves both through its object store. That is the mdim-refs `data` /
`offset` / `size` pair, and m05's `held` states, in one column.

  v1  every chunk of the year as an external blob (s3:// uri via remap)
  v2  the 63 box chunks of days 0..4 promoted to held bytes (merge_insert),
      bytes taken from lance_held.py's table
  read block-t0to9-hobart through read_blobs at v1 and v2 (mixed),
      decode, compare with the GDAL hash in manifest.json

Usage:
  python lance_extblob.py STORE_DIR HELD_LANCE OUT_DIR
"""
import json
import os
import shutil
import sqlite3
import sys
import time

import lance
import lance.blob as lb
import numcodecs
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lance_held import sha  # noqa: E402
from lance_load import dirsize  # noqa: E402

S3 = "s3://us-west-2.opendata.source.coop/"
OPTS = {"aws_region": "us-west-2", "aws_skip_signature": "true"}


def main():
    store, held, out = sys.argv[1:4]
    shutil.rmtree(out, ignore_errors=True)
    con = sqlite3.connect(os.path.join(store, "store.sqlite"))
    doc = json.load(open(os.path.join(store, "out", "flat", "arrays.json")))
    meta = next(r for r in doc["arrays"] if r["storage"] == "referenced")
    arr, cs, dt, fill = meta["array"], meta["chunks"], np.dtype(meta["dtype"]), int(meta["fill"])
    # remap for Lance's object store: https is not a scheme it reads, s3 is
    pre = "/vsicurl/https://data.source.coop/"
    rows = con.execute(f"select c.source_id, c.dim_0, c.dim_1, c.dim_2, c.\"offset\", c.size, s.source "
                       f"from `{arr}` c join sources s using (source_id)").fetchall()
    day_of = {sid: json.loads(d)[0] for sid, d in con.execute(
        "select source_id, dest from placements where array = ?", (arr,))}
    t0 = time.time()
    blobs = lb.blob_array([lb.Blob.from_uri(S3 + r[6][len(pre):], r[4], r[5]) for r in rows])
    t = pa.table({"source_id": [r[0] for r in rows], "dim_0": [r[1] for r in rows],
                  "dim_1": [r[2] for r in rows], "dim_2": [r[3] for r in rows], "data": blobs})
    p = os.path.join(out, f"{arr}.lance")
    ds = lance.write_dataset(t, p, allow_external_blob_outside_bases=True, storage_options=OPTS)
    ds.tags.create("refs", ds.version)
    log = {"rows": len(rows), "write_seconds": round(time.time() - t0, 1), "bytes_refs_only": dirsize(p)}

    # promote days 0..4 of the held box to inline bytes
    h = lance.dataset(held, version="scan").to_table(columns=["source_id", "dim_0", "dim_1", "dim_2", "data"])
    h = h.filter(pc.is_in(h["source_id"], pa.array([s for s, d in day_of.items() if d < 5])))
    promo = pa.table({k: h[k] for k in ("source_id", "dim_0", "dim_1", "dim_2")}).append_column(
        "data", lb.blob_array([lb.Blob.from_bytes(b) for b in h["data"].to_pylist()]))
    r = (lance.dataset(p, storage_options=OPTS).merge_insert(["source_id", "dim_0", "dim_1", "dim_2"])
         .when_matched_update_all().when_not_matched_insert_all().execute(promo))
    log["promote"] = r
    log["bytes_mixed"] = dirsize(p)

    man = json.load(open(os.path.join(store, "manifest.json")))["oracle"]["block-t0to9-hobart"]
    st, cn = man["start"], man["count"]
    zstd = numcodecs.Zstd()
    for ver in ("refs", None):
        d = lance.dataset(p, version=ver, storage_options=OPTS) if ver else lance.dataset(p, storage_options=OPTS)
        sel = d.to_table(columns=["source_id", "dim_1", "dim_2", "data"], with_row_id=True,
                         filter=pc.field("source_id").isin([s for s, x in day_of.items() if x < 10]) &
                         (pc.field("dim_1") == 25) & (pc.field("dim_2") == 63))
        kinds = sorted(x["kind"] for x in sel["data"].to_pylist())
        t0 = time.time()
        got = dict(d.read_blobs("data", ids=sel["_rowid"].to_pylist()))
        tread = time.time() - t0
        v = np.full(cn, fill, dtype=dt)
        for rid, sid, y, x in zip(sel["_rowid"].to_pylist(), sel["source_id"].to_pylist(),
                                  sel["dim_1"].to_pylist(), sel["dim_2"].to_pylist()):
            tile = np.cumsum(np.frombuffer(zstd.decode(got[rid]), dtype=dt).reshape(cs), axis=-1, dtype=dt)
            y0, x0 = y * cs[1], x * cs[2]
            v[day_of[sid] - st[0]] = tile[0, st[1] - y0:st[1] - y0 + cn[1], st[2] - x0:st[2] - x0 + cn[2]]
        log[f"window_{ver or 'mixed'}"] = {"kinds": {str(k): kinds.count(k) for k in set(kinds)},
                                         "sha_matches_gdal": sha(v) == man["sha256"],
                                         "read_seconds": round(tread, 2)}
    json.dump(log, open(os.path.join(out, "extblob-log.json"), "w"), indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
