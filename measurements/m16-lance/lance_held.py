"""lance_held.py -- hold the chunk bytes, not only the refs, in a versioned table.

Takes a box of chunks from an mdim-refs store (days 0..29, chunk rows
24..30, chunk columns 60..68 of GHRSST MUR analysed_sst: the Tasman Sea and
Southern Ocean south of Tasmania), fetches their bytes through the
s3direct remap, and holds them in the mdim-refs `data` column as held
copies (offset and size kept, m05's `held = copy`). Then:

  - writes them to Lance (plain binary, and blob-encoded) and to Parquet
    (one row group, and 64-row row groups) and compares size and the time
    to fetch single chunks by key;
  - replays days 20..29 as daily commits and tags the scan;
  - overwrites one day's bytes (a stand-in for a reprocessed granule) and
    shows the tag still reads the original bytes;
  - decodes the oracle window block-t0to9-hobart from the held bytes, with
    no network, at both versions, against the GDAL hash in manifest.json.

Usage:
  python lance_held.py STORE_DIR OUT_DIR
"""
import concurrent.futures as cf
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
import time
import urllib.request

import lance
import numcodecs
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lance_load import chunk_schema, dirsize  # noqa: E402

DAYS, ROWS, COLS = range(0, 30), range(24, 31), range(60, 69)


def fetch(url, off, size):
    req = urllib.request.Request(url, headers={"Range": f"bytes={off}-{off + size - 1}"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            if len(b) == size:
                return b
        except Exception:
            time.sleep(2 ** i)
    raise SystemExit(f"fetch failed {url} {off}")


def sha(v):
    return hashlib.sha256(np.ascontiguousarray(v).astype(v.dtype.newbyteorder("<")).tobytes()).hexdigest()


def window(tab, day_of, st, cn, cs, dt, fill):
    """Assemble a window from held rows (decode zstd, undo Predictor=2)."""
    zstd = numcodecs.Zstd()
    out = np.full(cn, fill, dtype=dt)
    for r in tab.to_pylist():
        g0 = [day_of[r["source_id"]] * cs[0], r["dim_1"] * cs[1], r["dim_2"] * cs[2]]
        if any(g0[i] + cs[i] <= st[i] or g0[i] >= st[i] + cn[i] for i in range(3)):
            continue
        tile = np.frombuffer(zstd.decode(r["data"]), dtype=dt).reshape(cs)
        tile = np.cumsum(tile, axis=-1, dtype=dt)
        so, sl = [], []
        for i in range(3):
            a0, a1 = max(st[i], g0[i]), min(st[i] + cn[i], g0[i] + cs[i])
            so.append(slice(a0 - st[i], a1 - st[i]))
            sl.append(slice(a0 - g0[i], a1 - g0[i]))
        out[tuple(so)] = tile[tuple(sl)]
    return out


def main():
    store, out = sys.argv[1:3]
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    con = sqlite3.connect(os.path.join(store, "store.sqlite"))
    doc = json.load(open(os.path.join(store, "out", "flat", "arrays.json")))
    meta = next(r for r in doc["arrays"] if r["storage"] == "referenced")
    arr, cs, dt, fill = meta["array"], meta["chunks"], np.dtype(meta["dtype"]), int(meta["fill"])
    pre, rep = con.execute("select prefix, replacement from remap where target = 's3direct'").fetchone()
    day_of = {sid: json.loads(d)[0] for sid, d in con.execute(
        "select source_id, dest from placements where array = ?", (arr,))}
    sids = [s for s, d in day_of.items() if d in DAYS]
    q = (f"select c.source_id, c.dim_0, c.dim_1, c.dim_2, c.present, c.\"offset\", c.size, c.info, s.source "
         f"from `{arr}` c join sources s using (source_id) where c.source_id in ({','.join(map(str, sids))}) "
         f"and c.dim_1 between {ROWS.start} and {ROWS.stop - 1} and c.dim_2 between {COLS.start} and {COLS.stop - 1}")
    rows = con.execute(q).fetchall()
    rows.sort(key=lambda r: (day_of[r[0]], r[2], r[3]))

    log = {"box": {"days": [DAYS.start, DAYS.stop - 1], "chunk_rows": [ROWS.start, ROWS.stop - 1],
                   "chunk_cols": [COLS.start, COLS.stop - 1]}, "chunks": len(rows)}
    t0 = time.time()
    with cf.ThreadPoolExecutor(16) as ex:
        data = list(ex.map(lambda r: fetch(rep + r[8][len(pre):], r[5], r[6]), rows))
    log["fetch_seconds"] = round(time.time() - t0, 1)
    log["held_bytes"] = sum(len(b) for b in data)

    sch = chunk_schema(3)
    full = pa.table({"source_id": [r[0] for r in rows], "dim_0": [r[1] for r in rows],
                     "dim_1": [r[2] for r in rows], "dim_2": [r[3] for r in rows],
                     "present": [r[4] for r in rows], "offset": [r[5] for r in rows],
                     "size": [r[6] for r in rows], "info": [r[7] for r in rows], "data": data}, schema=sch)
    days = pc.array_take(pa.array([day_of[s] for s in full["source_id"].to_pylist()]), pa.array(range(full.num_rows)))
    full = full.append_column("day", days)  # helper only, dropped before writing

    def part(lo, hi):
        m = pc.and_(pc.greater_equal(full["day"], lo), pc.less(full["day"], hi))
        return full.filter(m).drop_columns(["day"])

    # Lance, plain binary, built as history: days 0..19 bulk, then one commit a day
    lp = os.path.join(out, f"{arr}.lance")
    ds = lance.write_dataset(part(0, 20), lp)
    for d in range(20, 30):
        ds = lance.write_dataset(part(d, d + 1), lp, mode="append")
    ds.tags.create("scan", ds.version)
    # Lance, blob-encoded data column, one write
    bsch = pa.schema([f if f.name != "data" else pa.field("data", pa.large_binary(),
                      metadata={"lance-encoding:blob": "true"}) for f in sch])
    bp = os.path.join(out, f"{arr}-blob.lance")
    lance.write_dataset(part(0, 30).cast(bsch), bp)
    # Parquet, default row group (one) and 64-row row groups
    pq.write_table(part(0, 30), os.path.join(out, "held.parquet"))
    pq.write_table(part(0, 30), os.path.join(out, "held-rg64.parquet"), row_group_size=64)

    log["bytes"] = {"lance": dirsize(lp), "lance_blob": dirsize(bp),
                    "parquet": os.path.getsize(os.path.join(out, "held.parquet")),
                    "parquet_rg64": os.path.getsize(os.path.join(out, "held-rg64.parquet"))}

    # single-chunk fetch by key, 50 random keys, cold-ish (new handle each time)
    random.seed(1)
    keys = random.sample([(r[0], r[2], r[3]) for r in rows], 50)

    def flt(k):
        return (pc.field("source_id") == k[0]) & (pc.field("dim_1") == k[1]) & (pc.field("dim_2") == k[2])

    timing = {}
    for name, open_and_get in {
        "lance": lambda k: lance.dataset(lp).to_table(filter=flt(k), columns=["data"]),
        "lance_blob": lambda k: lance.dataset(bp).to_table(filter=flt(k), columns=["data"]),
        "parquet": lambda k: pq.read_table(os.path.join(out, "held.parquet"), columns=["data"],
                                           filters=[("source_id", "=", k[0]), ("dim_1", "=", k[1]),
                                                    ("dim_2", "=", k[2])]),
        "parquet_rg64": lambda k: pq.read_table(os.path.join(out, "held-rg64.parquet"), columns=["data"],
                                                filters=[("source_id", "=", k[0]), ("dim_1", "=", k[1]),
                                                         ("dim_2", "=", k[2])]),
    }.items():
        t0 = time.time()
        n = [open_and_get(k).num_rows for k in keys]
        if set(n) != {1} and name != "lance_blob":
            raise SystemExit(f"{name}: lookup returned {set(n)} rows")
        timing[name] = round((time.time() - t0) / len(keys) * 1000, 1)
    log["lookup_ms_per_chunk"] = timing
    # Lance take by row offset (what an index or a sorted key gives you)
    d = lance.dataset(lp)
    idx = random.sample(range(d.count_rows()), 50)
    t0 = time.time()
    for i in idx:
        d.take([i], columns=["data"])
    log["lookup_ms_per_chunk"]["lance_take_by_row"] = round((time.time() - t0) / 50 * 1000, 2)

    # a reprocessed granule: day 5's bytes replaced (here by day 6's, as a stand-in)
    d5 = [s for s, x in day_of.items() if x == 5][0]
    d6 = [s for s, x in day_of.items() if x == 6][0]
    new = part(5, 6)
    other = {(r["dim_1"], r["dim_2"]): r["data"] for r in part(6, 7).to_pylist()}
    new = new.set_column(new.schema.get_field_index("data"), "data",
                         pa.array([other[(a, b)] for a, b in zip(new["dim_1"].to_pylist(), new["dim_2"].to_pylist())],
                                  pa.binary()))
    r = (lance.dataset(lp).merge_insert(["source_id", "dim_0", "dim_1", "dim_2"])
         .when_matched_update_all().when_not_matched_insert_all().execute(new))
    log["reprocess_day5"] = r

    # decode the oracle window from held bytes only, at the tag and at latest
    man = json.load(open(os.path.join(store, "manifest.json")))["oracle"]["block-t0to9-hobart"]
    st, cn = man["start"], man["count"]
    res = {}
    for ver in ("scan", None):
        tab = (lance.dataset(lp, version=ver) if ver else lance.dataset(lp)).to_table(
            filter=pc.field("source_id").isin([s for s, x in day_of.items() if x < 10]))
        v = window(tab, day_of, st, cn, cs, dt, fill)
        res[ver or "latest"] = {"sha_matches_gdal": sha(v) == man["sha256"],
                                "days_differing_from_scan": None, "array": v}
    res["latest"]["days_differing_from_scan"] = [
        int(t) for t in range(cn[0]) if not np.array_equal(res["latest"]["array"][t], res["scan"]["array"][t])]
    for k in res:
        res[k].pop("array")
    log["window_block_t0to9_hobart"] = res
    log["versions"] = len(lance.dataset(lp).versions())
    json.dump(log, open(os.path.join(out, "held-log.json"), "w"), indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
