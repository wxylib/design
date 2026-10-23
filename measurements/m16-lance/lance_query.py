"""lance_query.py -- time travel, diff and the remap view over the Lance store.

Usage:
  python lance_query.py LANCE_DIR FLAT_DIR

LANCE_DIR is lance_load.py's output; FLAT_DIR is the mdim-refs flat export
(refs_<array>.parquet) the view must reproduce row for row.
"""
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import timedelta

import datafusion
import duckdb
import lance
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

# The global view (mdim-refs refs_<array>) for a time-concat plan whose
# placements are chunk aligned, as SQL both engines accept: remap is applied
# to the sources table (one row per file), so its cost does not grow with
# the number of chunks. dest is a JSON array; split_part keeps the SQL
# portable (DataFusion has no JSON functions built in).
VIEW = """
WITH r AS (
  SELECT s.source_id, s.source, m.prefix, m.replacement,
         row_number() OVER (PARTITION BY s.source_id ORDER BY length(m.prefix) DESC) AS k
  FROM sources s LEFT JOIN remap m
    ON m.target = '{target}' AND starts_with(s.source, m.prefix)
), src AS (
  SELECT source_id,
         CASE WHEN prefix IS NULL THEN source
              ELSE concat(replacement, substr(source, length(prefix) + 1)) END AS path
  FROM r WHERE k = 1
), pl AS (
  SELECT source_id,
         CAST(split_part(trim(src_offset, '[]'), ',', 1) AS BIGINT) AS o0,
         CAST(split_part(trim(dest, '[]'), ',', 1) AS BIGINT) AS d0
  FROM placements WHERE "array" = '{array}'
)
SELECT c.dim_0 - pl.o0 + pl.d0 AS dim_0, c.dim_1, c.dim_2, c.present,
       src.path, c."offset", c.size, c.info, c.data
FROM chunks c JOIN pl ON pl.source_id = c.source_id
              JOIN src ON src.source_id = c.source_id
"""


def rowhash(t, cols):
    t = t.select(cols)
    t = t.cast(pa.schema([pa.field(f.name, pa.string() if pa.types.is_string_view(f.type) else f.type)
                          for f in t.schema]))
    t = t.sort_by([(c, "ascending") for c in cols[:3]])
    h = hashlib.sha256()
    for b in t.to_batches():
        h.update(b.serialize().to_pybytes())
    return h.hexdigest()[:16]


def main():
    ldir, flat = sys.argv[1:3]
    arr = json.load(open(os.path.join(ldir, "load-log.json")))["array"]
    uri = {k: os.path.join(ldir, f"{k}.lance") for k in ("sources", "placements", "remap", arr)}
    out = {}

    # 1. time travel: tags pin the chunk table; the small tables are read at latest
    ch = lance.dataset(uri[arr])
    tags = ch.tags.list()
    out["tags"] = {k: v["version"] for k, v in tags.items()}
    days = {}
    for tag in ("first-half", "year", "rescan"):
        d = lance.dataset(uri[arr], version=tag)
        days[tag] = {"rows": d.count_rows(),
                     "sources": len(pc.unique(d.to_table(columns=["source_id"])["source_id"]))}
    out["time_travel"] = days

    # 2. diff. Lance's own delta (stable row ids) against a plain EXCEPT.
    v1, vy, vr = out["tags"]["first-half"], out["tags"]["year"], out["tags"]["rescan"]
    dl = ch.delta(begin_version=v1, end_version=vy)
    ins = dl.get_inserted_rows().read_all().num_rows
    dr = ch.delta(begin_version=vy, end_version=vr)
    upd = dr.get_updated_rows().read_all().num_rows
    a = lance.dataset(uri[arr], version="first-half")
    b = lance.dataset(uri[arr], version="year")
    t0 = time.time()
    exc = duckdb.sql("SELECT count(*) FROM (SELECT source_id, dim_0, dim_1, dim_2, \"offset\", size FROM b "
                     "EXCEPT SELECT source_id, dim_0, dim_1, dim_2, \"offset\", size FROM a)").fetchone()[0]
    out["diff"] = {"delta_inserted_first_half_to_year": ins,
                   "delta_updated_year_to_rescan": upd,
                   "delta_transactions_first_half_to_year": len(dl.list_transactions()),
                   "except_rows_first_half_to_year": exc,
                   "except_seconds": round(time.time() - t0, 2)}

    # 3. the view, in DuckDB and DataFusion, against the flat export
    want = pq.read_table(os.path.join(flat, f"refs_{arr}.parquet"))
    cols = ["dim_0", "dim_1", "dim_2", "present", "path", "offset", "size"]
    # path in the flat export is verbatim: target 'none' matches no remap rows
    chunks = lance.dataset(uri[arr], version="year")
    sources = lance.dataset(uri["sources"])
    placements = lance.dataset(uri["placements"])
    remap = lance.dataset(uri["remap"])
    sql = VIEW.format(target="none", array=arr)
    t0 = time.time()
    got = duckdb.sql(sql).arrow()
    if hasattr(got, "read_all"):
        got = got.read_all()
    tduck = time.time() - t0
    ctx = datafusion.SessionContext()
    for name, d in (("chunks", chunks), ("sources", sources), ("placements", placements), ("remap", remap)):
        ctx.register_table(name, lance.FFILanceTableProvider(d))
    t0 = time.time()
    gdf = pa.Table.from_batches(ctx.sql(sql).collect())
    tdf = time.time() - t0
    out["view"] = {"flat_rows": want.num_rows, "duckdb_rows": got.num_rows, "datafusion_rows": gdf.num_rows,
                   "flat_hash": rowhash(want, cols), "duckdb_hash": rowhash(got, cols),
                   "datafusion_hash": rowhash(gdf, cols),
                   "duckdb_seconds": round(tduck, 2), "datafusion_seconds": round(tdf, 2)}

    # remap as a view: the same rows, late-bound to another target
    rm = duckdb.sql(VIEW.format(target="s3direct", array=arr) +
                    " WHERE c.dim_0 - pl.o0 + pl.d0 = 0 AND c.dim_1 = 0 AND c.dim_2 = 0").fetchall()
    out["remap_example"] = {"target": "s3direct", "row": [str(x) for x in rm[0][:7]]}

    # a box query: Hobart, days 0..9, at the first-half tag, chunk table only
    a = lance.dataset(uri[arr], version="first-half")
    pl = placements.to_table().to_pylist()
    first = [p["source_id"] for p in pl if json.loads(p["dest"])[0] < 10]
    t0 = time.time()
    box = a.to_table(filter=pc.field("source_id").isin(first) &
                     (pc.field("dim_1") >= 25) & (pc.field("dim_1") <= 25) &
                     (pc.field("dim_2") >= 63) & (pc.field("dim_2") <= 63))
    out["box_query"] = {"rows": box.num_rows, "seconds": round(time.time() - t0, 3)}

    # 4. compaction and cleanup on a copy: what history costs, and what is kept
    cp = os.path.join(ldir, "compacted", f"{arr}.lance")
    shutil.rmtree(os.path.dirname(cp), ignore_errors=True)
    shutil.copytree(uri[arr], cp)
    d = lance.dataset(cp)
    before = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(cp) for f in fs)
    t0 = time.time()
    m = d.optimize.compact_files(target_rows_per_fragment=4 * 1024 * 1024)
    d = lance.dataset(cp)
    st = d.cleanup_old_versions(older_than=timedelta(0), delete_unverified=True, error_if_tagged_old_versions=False)
    after = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(cp) for f in fs)
    still = {t: lance.dataset(cp, version=t).count_rows() for t in ("first-half", "year", "rescan")}
    out["compaction"] = {"bytes_before": before, "bytes_after": after,
                         "fragments_after": len(d.get_fragments()), "versions_after": len(d.versions()),
                         "removed_versions": st.old_versions, "tags_still_readable": still,
                         "seconds": round(time.time() - t0, 2),
                         "fragments_removed": m.fragments_removed, "fragments_added": m.fragments_added}
    json.dump(out, open(os.path.join(ldir, "query-log.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
