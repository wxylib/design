"""lance_load.py -- an mdim-refs/0.2 store as Lance datasets, built as history.

Copies the four mdim-refs tables (sources, placements, remap, one chunk
table per referenced array) from store.sqlite into Lance datasets with the
same columns, then replays the year as it would have been produced:

  v1      bulk load of the first half (days 0..181), tagged
  v2..    one commit per day for the rest (days 182..365), tagged at the end
  last    a rescan of one day as an upsert (merge_insert on the chunk key)

Usage:
  python lance_load.py STORE.sqlite OUT_DIR [--bulk 182] [--rescan 100]
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

import lance
import pyarrow as pa


def dirsize(p):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)


def table(con, sql, schema):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pa.table({c: [r[i] for r in rows] for i, c in enumerate(cols)}, schema=schema)


SOURCES = pa.schema([("source_id", pa.int64()), ("source", pa.string()),
                     ("size", pa.int64()), ("mtime", pa.int64()), ("etag", pa.string())])
PLACEMENTS = pa.schema([("array", pa.string()), ("source_id", pa.int64()),
                        ("source_array", pa.string()), ("src_offset", pa.string()),
                        ("count", pa.string()), ("dest", pa.string())])
REMAP = pa.schema([("target", pa.string()), ("prefix", pa.string()), ("replacement", pa.string())])


def chunk_schema(ndim):
    return pa.schema([("source_id", pa.int64())] +
                     [(f"dim_{i}", pa.int64()) for i in range(ndim)] +
                     [("present", pa.int8()), ("offset", pa.int64()), ("size", pa.int64()),
                      ("info", pa.string()), ("data", pa.binary())])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("store")
    p.add_argument("out")
    p.add_argument("--bulk", type=int, default=182)
    p.add_argument("--rescan", type=int, default=100)
    a = p.parse_args()

    con = sqlite3.connect(a.store)
    arrays = [r[0] for r in con.execute("select array from arrays where storage = 'referenced'")]
    if len(arrays) != 1:
        sys.exit("this replay handles one referenced array")
    arr = arrays[0]
    ndim = len(json.loads(con.execute("select dims from arrays where array = ?", (arr,)).fetchone()[0]))
    # day index of each source, from its placement
    day = {sid: json.loads(d)[0] for sid, d in con.execute(
        "select source_id, dest from placements where array = ?", (arr,))}
    by_day = sorted(day, key=day.get)

    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    uri = {k: os.path.join(a.out, f"{k}.lance") for k in ("sources", "placements", "remap", arr)}
    lance.write_dataset(table(con, "select * from remap", REMAP), uri["remap"])
    # the arrays table and meta stay JSON (arrays.json), as in the flat export

    cs = chunk_schema(ndim)
    keycols = ["source_id"] + [f"dim_{i}" for i in range(ndim)]
    qchunks = f"select * from `{arr}` where source_id in ({{}}) order by " + ", ".join(keycols)

    def batch(ids):
        q = ",".join(str(i) for i in ids)
        return (table(con, f"select * from sources where source_id in ({q})", SOURCES),
                table(con, f"select * from placements where source_id in ({q})", PLACEMENTS),
                table(con, qchunks.format(q), cs))

    log = {"array": arr, "commits": []}

    def commit(ids, mode, msg):
        s, pl, ch = batch(ids)
        t0 = time.time()
        # commit order: sources, placements, then the chunk table. The chunk
        # table version is the reader's snapshot handle; the two small
        # tables only ever gain rows, so a reader pinned to chunk version N
        # with newer sources/placements still resolves every row it sees.
        lance.write_dataset(s, uri["sources"], mode=mode)
        lance.write_dataset(pl, uri["placements"], mode=mode)
        ds = lance.write_dataset(ch, uri[arr], mode=mode, commit_message=msg,
                                 enable_stable_row_ids=True, max_rows_per_file=4 * 1024 * 1024)
        log["commits"].append({"version": ds.version, "rows": ch.num_rows, "msg": msg,
                               "seconds": round(time.time() - t0, 3)})
        return ds

    t0 = time.time()
    ds = commit(by_day[:a.bulk], "create", f"bulk load days 0..{a.bulk - 1}")
    ds.tags.create("first-half", ds.version)
    for sid in by_day[a.bulk:]:
        ds = commit([sid], "append", f"append day {day[sid]}")
    ds.tags.create("year", ds.version)

    # rescan of one day: the same rows arrive again; an upsert keyed within
    # the source must leave the row count alone and touch only that day
    sid = by_day[a.rescan]
    _, _, ch = batch([sid])
    t1 = time.time()
    r = (ds.merge_insert(keycols).when_matched_update_all()
         .when_not_matched_insert_all().execute(ch))
    ds = lance.dataset(uri[arr])
    ds.tags.create("rescan", ds.version)
    log["commits"].append({"version": ds.version, "rows": ch.num_rows,
                           "msg": f"rescan day {a.rescan} (upsert)", "merge": r,
                           "seconds": round(time.time() - t1, 3)})
    log["replay_seconds"] = round(time.time() - t0, 1)
    log["versions"] = len(ds.versions())
    log["rows"] = ds.count_rows()
    log["fragments"] = len(ds.get_fragments())
    log["bytes"] = {k: dirsize(v) for k, v in uri.items()}
    log["bytes_versions_dir"] = dirsize(os.path.join(uri[arr], "_versions"))
    log["bytes_data_dir"] = dirsize(os.path.join(uri[arr], "data"))
    with open(os.path.join(a.out, "load-log.json"), "w") as f:
        json.dump(log, f, indent=1)
    c = log["commits"]
    daily = [x["seconds"] for x in c[1:-1]]
    print(f"{arr}: {log['rows']} rows, {log['versions']} versions, {log['fragments']} fragments, "
          f"{log['bytes'][arr] / 1e6:.1f} MB (versions dir {log['bytes_versions_dir'] / 1e6:.2f} MB); "
          f"bulk {c[0]['seconds']} s, daily median {sorted(daily)[len(daily) // 2]} s, "
          f"rescan {c[-1]['seconds']} s {c[-1]['merge']}; replay {log['replay_seconds']} s")


if __name__ == "__main__":
    main()
