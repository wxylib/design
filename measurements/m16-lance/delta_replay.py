"""delta_replay.py -- the m16 history as Delta Lake tables (delta-rs).

Same replay as lance_load.py and frag_store.py: a half-year bulk load, one
commit per day for the rest, one rescan of day 100 as an upsert (merge on
the within-source key). Then time travel, change data feed, the remap view
through DuckDB (over delta-rs' Arrow dataset), a two-writer race,
compaction and vacuum.

Then m16 section 6b: a source that changes in place. Day 100's file is
"reprocessed" under the same name with a new etag, recorded two ways:

  inplace  the sources row is updated (source stays UNIQUE, as 0.2 says)
  keyed    a new sources row keyed by (source, etag), new chunk rows under
           the new source_id, the placement switched to it

and a reader pinned to the "year" versions reads day 100 with every table
pinned, and with sources and placements at latest (the commit-point
convention of m16 section 1).

Usage:
  python delta_replay.py STORE.sqlite OUT_DIR [--layout single|day]

--layout single writes the bulk half-year as one file; --layout day
partitions the chunk table by source_id, one file per day (the append
unit). The log is delta-<layout>-log.json in OUT_DIR.
"""
import json
import os
import shutil
import sqlite3
import sys
import time

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from deltalake import DeltaTable, write_deltalake

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lance_load import PLACEMENTS, SOURCES, chunk_schema, dirsize, table  # noqa: E402
from lance_query import VIEW, rowhash  # noqa: E402

KEY = ["source_id", "dim_0", "dim_1", "dim_2"]
CDF = {"delta.enableChangeDataFeed": "true"}


def upsert(uri, new, keys):
    pred = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    return (DeltaTable(uri).merge(new, predicate=pred, source_alias="s", target_alias="t")
            .when_matched_update_all().when_not_matched_insert_all().execute())


def main():
    store, out = sys.argv[1:3]
    layout = sys.argv[sys.argv.index("--layout") + 1] if "--layout" in sys.argv else "single"
    part = ["source_id"] if layout == "day" else None
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    con = sqlite3.connect(store)
    arr = "analysed_sst"
    day = {sid: json.loads(d)[0] for sid, d in con.execute(
        "select source_id, dest from placements where array = ?", (arr,))}
    by_day = sorted(day, key=day.get)
    cs = chunk_schema(3)

    def rows(ids):
        q = ",".join(str(i) for i in ids)
        return (table(con, f"select * from sources where source_id in ({q})", SOURCES),
                table(con, f"select * from placements where source_id in ({q})", PLACEMENTS),
                table(con, f"select * from `{arr}` where source_id in ({q}) order by " + ", ".join(KEY), cs))

    names = ("sources", "placements", arr)
    uri = {k: os.path.join(out, k) for k in names}
    log = {"layout": layout, "commits": []}
    vers = {}
    t0 = time.time()
    for i, ids in enumerate([by_day[:182]] + [[s] for s in by_day[182:]]):
        s, pl, ch = rows(ids)
        t1 = time.time()
        cfg = CDF if i == 0 else None
        write_deltalake(uri["sources"], s, mode="append", configuration=cfg)
        write_deltalake(uri["placements"], pl, mode="append", configuration=cfg)
        write_deltalake(uri[arr], ch, mode="append", configuration=cfg, partition_by=part)
        log["commits"].append(round(time.time() - t1, 4))
        if i == 0:
            vers["first-half"] = {k: DeltaTable(uri[k]).version() for k in names}
    vers["year"] = {k: DeltaTable(uri[k]).version() for k in names}

    # rescan of day 100: merge on the within-source key
    sid = by_day[100]
    _, _, ch = rows([sid])
    t1 = time.time()
    m = upsert(uri[arr], ch, KEY)
    log["rescan_seconds"] = round(time.time() - t1, 3)
    log["rescan_metrics"] = {k: m.get(k) for k in (
        "num_source_rows", "num_target_rows_updated", "num_target_rows_inserted",
        "num_target_rows_copied", "num_target_files_added", "num_target_files_removed")}
    vers["rescan"] = {k: DeltaTable(uri[k]).version() for k in names}
    log["replay_seconds"] = round(time.time() - t0, 1)
    log["versions"] = vers
    daily = sorted(log["commits"][1:])
    log["daily_median_seconds"] = daily[len(daily) // 2]

    # time travel
    log["rows"] = {k: DeltaTable(uri[arr], version=v[arr]).count() for k, v in vers.items()}
    # change data feed between year and rescan: what the rescan touched
    cdf = pa.table(DeltaTable(uri[arr]).load_cdf(starting_version=vers["year"][arr] + 1).read_all())
    log["cdf_year_to_rescan"] = {str(k): v.as_py() for k, v in zip(
        *pc.value_counts(cdf["_change_type"]).flatten())} if cdf.num_rows else {}
    # a set difference of the two versions, as for Lance
    a = DeltaTable(uri[arr], version=vers["year"][arr]).to_pyarrow_dataset()
    b = DeltaTable(uri[arr], version=vers["first-half"][arr]).to_pyarrow_dataset()
    t1 = time.time()
    n = duckdb.sql("select count(*) from (select * exclude (info, data) from a "
                   "except select * exclude (info, data) from b)").fetchall()[0][0]
    log["except_year_minus_first_half"] = {"rows": n, "seconds": round(time.time() - t1, 2)}

    # the remap view in DuckDB, over the Delta tables at the rescan version
    chunks = DeltaTable(uri[arr]).to_pyarrow_dataset()
    sources = DeltaTable(uri["sources"]).to_pyarrow_dataset()
    placements = DeltaTable(uri["placements"]).to_pyarrow_dataset()
    remap = pa.table({"target": pa.array([], pa.string()), "prefix": pa.array([], pa.string()),
                      "replacement": pa.array([], pa.string())})
    t1 = time.time()
    got = duckdb.sql(VIEW.format(target="none", array=arr)).arrow()
    if hasattr(got, "read_all"):
        got = got.read_all()
    log["view_seconds"] = round(time.time() - t1, 2)
    want = pq.read_table(os.path.join(os.path.dirname(store), "out", "flat", f"refs_{arr}.parquet"))
    cols = ["dim_0", "dim_1", "dim_2", "present", "path", "offset", "size"]
    log["view_hash_matches_flat"] = rowhash(got, cols) == rowhash(want, cols)
    del chunks, sources, placements, remap

    # two writers from the same base version: both appends land
    base = DeltaTable(uri[arr])
    other = DeltaTable(uri[arr])
    write_deltalake(base, ch.slice(0, 1), mode="append", partition_by=part)
    try:
        write_deltalake(other, ch.slice(1, 1), mode="append", partition_by=part)
        log["race_append"] = "both landed"
    except Exception as e:
        log["race_append"] = f"second refused: {type(e).__name__}"
    log["race_versions"] = DeltaTable(uri[arr]).version()
    # two merges of the same day from one base: the second must conflict or
    # re-plan, never leave duplicate keys
    x, y = DeltaTable(uri[arr]), DeltaTable(uri[arr])
    pred = " AND ".join(f"t.{k} = s.{k}" for k in KEY)
    x.merge(ch, predicate=pred, source_alias="s", target_alias="t") \
        .when_matched_update_all().when_not_matched_insert_all().execute()
    try:
        y.merge(ch, predicate=pred, source_alias="s", target_alias="t") \
            .when_matched_update_all().when_not_matched_insert_all().execute()
        log["race_merge"] = "both landed"
    except Exception as e:
        log["race_merge"] = f"second refused: {type(e).__name__}: {str(e)[:120]}"
    d = DeltaTable(uri[arr]).to_pyarrow_dataset()
    # (the race appends re-added two of day 100's rows: no key constraint)
    log["race_rows_day100"] = d.count_rows(filter=pc.field("source_id") == sid)

    log["bytes_before_optimize"] = {k: dirsize(uri[k]) for k in names}
    log["files_before_optimize"] = len(DeltaTable(uri[arr]).file_uris())
    log["bytes_log_dir"] = dirsize(os.path.join(uri[arr], "_delta_log"))
    t1 = time.time()
    DeltaTable(uri[arr]).optimize.compact()
    log["compact_seconds"] = round(time.time() - t1, 2)
    log["files_after_optimize"] = len(DeltaTable(uri[arr]).file_uris())
    vac = DeltaTable(uri[arr]).vacuum(retention_hours=0, enforce_retention_duration=False,
                                      dry_run=False)
    log["vacuum_removed_files"] = len(vac)
    log["bytes_after_vacuum"] = dirsize(uri[arr])
    try:
        # count() can answer from the log alone, so read the rows
        n = DeltaTable(uri[arr], version=vers["first-half"][arr]).to_pyarrow_table(
            columns=["offset"]).num_rows
        log["first_half_after_vacuum"] = f"readable, {n} rows"
    except Exception as e:
        log["first_half_after_vacuum"] = f"unreadable: {type(e).__name__}"

    log["source_change"] = source_change(out, rows, by_day, cs, part)
    name = f"delta-{layout}-log.json"
    json.dump(log, open(os.path.join(out, name), "w"), indent=1)
    print(json.dumps({k: v for k, v in log.items() if k != "commits"}, indent=1))


def source_change(out, rows, by_day, cs, part):
    """Day 100's file reprocessed in place under the same name (section 6b)."""
    res = {}
    sid = by_day[100]
    s, pl, ch = rows([sid])
    for mode in ("inplace", "keyed"):
        root = os.path.join(out, f"change-{mode}")
        u = {k: os.path.join(root, k) for k in ("sources", "placements", "chunks")}
        s0 = s.set_column(4, "etag", pa.array(["e1"]))
        write_deltalake(u["sources"], s0)
        write_deltalake(u["placements"], pl)
        write_deltalake(u["chunks"], ch, partition_by=part)
        year = {k: DeltaTable(v).version() for k, v in u.items()}
        # the provider rewrites the file: new etag, new size, new offsets
        ch2 = ch.set_column(cs.get_field_index("offset"), "offset",
                            pc.add(ch["offset"], 1000))
        if mode == "inplace":
            s1 = s0.set_column(4, "etag", pa.array(["e2"])).set_column(
                2, "size", pc.add(s0["size"], 1000))
            upsert(u["sources"], s1, ["source_id"])
            upsert(u["chunks"], ch2, KEY)
        else:
            new = sid + 100000
            s1 = s0.set_column(0, "source_id", pa.array([new])).set_column(
                4, "etag", pa.array(["e2"])).set_column(2, "size", pc.add(s0["size"], 1000))
            write_deltalake(u["sources"], s1, mode="append")
            write_deltalake(u["chunks"], ch2.set_column(0, "source_id",
                            pa.array([new] * ch2.num_rows)), mode="append", partition_by=part)
            pl1 = pl.set_column(1, "source_id", pa.array([new]))
            dt = DeltaTable(u["placements"])
            dt.merge(pl1, predicate="t.array = s.array AND t.dest = s.dest",
                     source_alias="s", target_alias="t").when_matched_update_all().execute()
        live_etag = "e2"
        out_m = {"sources_rows_latest": DeltaTable(u["sources"]).count()}
        for read in ("all-pinned", "chunks-pinned"):
            sv = year["sources"] if read == "all-pinned" else None
            pv = year["placements"] if read == "all-pinned" else None
            S = DeltaTable(u["sources"], version=sv).to_pyarrow_table()
            P = DeltaTable(u["placements"], version=pv).to_pyarrow_table()
            C = DeltaTable(u["chunks"], version=year["chunks"]).to_pyarrow_table()
            j = duckdb.sql("select c.offset, s.etag from P p join C c using (source_id) "
                           "join S s using (source_id)").fetchall()
            if not j:
                verdict = "day missing: placement points at a source the pinned chunks lack"
            else:
                old_offsets = all(o == r for (o, _), r in zip(sorted(j), sorted(ch["offset"].to_pylist())))
                et = {e for _, e in j}
                if et == {live_etag}:
                    verdict = ("old offsets accepted as the new file" if old_offsets
                               else "new offsets, new file")
                else:
                    verdict = "etag differs from the live file: refused, stale detected"
            out_m[read] = {"rows": len(j), "etags": sorted({e for _, e in j}), "verdict": verdict}
        res[mode] = out_m
    return res


if __name__ == "__main__":
    main()
