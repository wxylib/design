"""frag_store.py -- the thin alternative: Parquet fragments plus a manifest
committed with object_store PutMode::Create (obstore's mode="create").

Same replay as lance_load.py (bulk half-year, one commit per day, one rescan
upsert), same rows, then time travel, diff and the DataFusion view, and a
two-writer race. About as small as a versioned table can be:

  data/<uuid>.parquet       immutable fragments
  _commits/<n>.json         {version, parent, fragments, added, removed, message}
                            written with put-if-absent; the winner of a race
                            owns version n, the loser reloads and retries

Usage:
  python frag_store.py STORE.sqlite OUT_DIR LANCE_DIR
(LANCE_DIR for the comparison numbers in load-log.json.)
"""
import json
import os
import shutil
import sqlite3
import sys
import time
import uuid

import datafusion
import obstore
import pyarrow as pa
import pyarrow.dataset as pds
import pyarrow.parquet as pq
from obstore.store import LocalStore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lance_load import PLACEMENTS, SOURCES, chunk_schema, dirsize, table  # noqa: E402
from lance_query import VIEW, rowhash  # noqa: E402


class FragTable:
    def __init__(self, root):
        os.makedirs(root, exist_ok=True)
        self.root = os.path.abspath(root)
        self.store = LocalStore(self.root)

    def latest(self):
        names = [o["path"] for o in self.store.list("_commits").collect()]
        return max((int(os.path.basename(n).split(".")[0]) for n in names), default=0)

    def manifest(self, v):
        if v == 0:
            return {"version": 0, "fragments": []}
        return json.loads(bytes(obstore.get(self.store, f"_commits/{v:020d}.json").bytes()))

    def commit(self, add=None, remove=(), message="", base=None, retries=10):
        """Write fragment `add` (a table), drop fragments `remove`, commit."""
        added = []
        if add is not None and add.num_rows:
            path = f"data/{uuid.uuid4().hex}.parquet"
            buf = pa.BufferOutputStream()
            pq.write_table(add, buf, row_group_size=128 * 1024)
            obstore.put(self.store, path, buf.getvalue().to_pybytes(), mode="create")
            added = [{"path": path, "rows": add.num_rows}]
        base = self.latest() if base is None else base
        for _ in range(retries):
            m = self.manifest(base)
            keep = [f for f in m["fragments"] if f["path"] not in remove]
            if len(m["fragments"]) - len(keep) != len(remove):
                raise RuntimeError("conflict: a fragment to remove is gone")
            new = {"version": base + 1, "parent": base, "message": message, "ts": time.time(),
                   "fragments": keep + added, "added": [f["path"] for f in added], "removed": list(remove)}
            try:
                obstore.put(self.store, f"_commits/{base + 1:020d}.json",
                            json.dumps(new).encode(), mode="create")
                return base + 1, _
            except Exception as e:  # AlreadyExists: someone else won this version
                if "exist" not in str(e).lower():
                    raise
                base = self.latest()
        raise RuntimeError("gave up")

    def dataset(self, v=None):
        m = self.manifest(self.latest() if v is None else v)
        return pds.dataset([os.path.join(self.root, f["path"]) for f in m["fragments"]], format="parquet")


def main():
    store, out, ldir = sys.argv[1:4]
    shutil.rmtree(out, ignore_errors=True)
    con = sqlite3.connect(store)
    arr = "analysed_sst"
    day = {sid: json.loads(d)[0] for sid, d in con.execute(
        "select source_id, dest from placements where array = ?", (arr,))}
    by_day = sorted(day, key=day.get)
    cs = chunk_schema(3)
    keycols = ["source_id", "dim_0", "dim_1", "dim_2"]

    def rows(ids):
        q = ",".join(str(i) for i in ids)
        return (table(con, f"select * from sources where source_id in ({q})", SOURCES),
                table(con, f"select * from placements where source_id in ({q})", PLACEMENTS),
                table(con, f"select * from `{arr}` where source_id in ({q}) order by " + ", ".join(keycols), cs))

    t = {k: FragTable(os.path.join(out, k)) for k in ("sources", "placements", arr)}
    log = {"commits": []}
    t0 = time.time()
    tags = {}
    for i, ids in enumerate([by_day[:182]] + [[s] for s in by_day[182:]]):
        s, pl, ch = rows(ids)
        t1 = time.time()
        t["sources"].commit(s)
        t["placements"].commit(pl)
        v, _ = t[arr].commit(ch, message=f"day {day[ids[-1]]}")
        log["commits"].append(round(time.time() - t1, 4))
        if i == 0:
            tags["first-half"] = v
    tags["year"] = v

    # rescan of day 100 as copy-on-write: no deletion vectors, so the
    # fragment holding that day is rewritten without it, plus the new rows
    sid = by_day[100]
    _, _, ch = rows([sid])
    t1 = time.time()
    m = t[arr].manifest(v)
    hit = [f["path"] for f in m["fragments"]
           if pq.read_table(os.path.join(t[arr].root, f["path"]), columns=["source_id"],
                            filters=[("source_id", "=", sid)]).num_rows]
    rest = pa.concat_tables([pq.read_table(os.path.join(t[arr].root, p), filters=[("source_id", "!=", sid)])
                             for p in hit] + [ch]).cast(cs)
    v, _ = t[arr].commit(rest, remove=hit, message=f"rescan day 100")
    tags["rescan"] = v
    log["rescan_seconds"] = round(time.time() - t1, 3)
    log["rescan_rows_rewritten"] = rest.num_rows
    log["replay_seconds"] = round(time.time() - t0, 1)
    log["tags"] = tags

    # time travel and diff: a manifest is a fragment list, so the diff of two
    # versions starts as a set difference of fragments, then rows
    log["rows"] = {k: t[arr].dataset(v).count_rows() for k, v in tags.items()}
    fa = {f["path"] for f in t[arr].manifest(tags["year"])["fragments"]}
    fb = {f["path"] for f in t[arr].manifest(tags["rescan"])["fragments"]}
    log["diff_year_to_rescan_fragments"] = {"added": len(fb - fa), "removed": len(fa - fb)}

    # the same view through DataFusion, over pyarrow datasets
    ctx = datafusion.SessionContext()
    ctx.register_dataset("chunks", t[arr].dataset(tags["year"]))
    ctx.register_dataset("sources", t["sources"].dataset())
    ctx.register_dataset("placements", t["placements"].dataset())
    ctx.register_dataset("remap", pds.dataset(pa.table(
        {"target": pa.array([], pa.string()), "prefix": pa.array([], pa.string()),
         "replacement": pa.array([], pa.string())})))
    t1 = time.time()
    got = pa.Table.from_batches(ctx.sql(VIEW.format(target="none", array=arr)).collect())
    log["view_seconds"] = round(time.time() - t1, 2)
    want = pq.read_table(os.path.join(os.path.dirname(store), "out", "flat", f"refs_{arr}.parquet"))
    cols = ["dim_0", "dim_1", "dim_2", "present", "path", "offset", "size"]
    log["view_hash_matches_flat"] = rowhash(got, cols) == rowhash(want, cols)

    # two writers from the same base version: one wins, one retries
    base = t[arr].latest()
    va, ra = t[arr].commit(ch.slice(0, 1), message="writer A", base=base)
    vb, rb = t[arr].commit(ch.slice(1, 1), message="writer B", base=base)
    log["race"] = {"base": base, "A": [va, ra], "B": [vb, rb]}

    log["bytes"] = {k: dirsize(x.root) for k, x in t.items()}
    log["bytes_commits_dir"] = dirsize(os.path.join(t[arr].root, "_commits"))
    log["bytes_data_dir"] = dirsize(os.path.join(t[arr].root, "data"))
    daily = sorted(log["commits"][1:])
    log["daily_median_seconds"] = daily[len(daily) // 2]
    json.dump(log, open(os.path.join(out, "frag-log.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in log.items() if k != "commits"}, indent=1))


if __name__ == "__main__":
    main()
