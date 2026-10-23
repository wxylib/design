# m16: A versioned byte-ref table, Lance against the alternatives

Status: musing, measured, 2026-10-23. Tests the "Bytes in place" claim
that Icechunk's addressing and layout features are views over a byte-ref
table and its versioning features are storage, and answers its open
question: for a byte-ref table with history, Lance, or a thin layer of
Parquet fragments plus an `object_store` `PutMode::Create` manifest
commit, queried by DataFusion or SedonaDB? A second part (section 7) asks
the same of the chunk bytes themselves, held in the table rather than
referenced. Scripts and logs:
[measurements/m16-lance](../measurements/m16-lance/README.md).

## Summary

The question in one line: if the mdim-refs table ever needs history
(snapshots, append-as-commit, diff, time travel), which table format holds
it, and is it worth doing now?

- **Lance holds mdim-refs/0.2 rows unchanged.** The four tables
  (`sources`, `placements`, `remap`, one chunk table per array) load into
  Lance datasets with the same columns. No new schema; Lance's own row ids
  and version numbers stay internal.
- **Everything asked of it worked on a real store.** GHRSST MUR
  analysed_sst 2024 (935,496 refs) replayed as a half-year bulk load, 184
  daily commits and one rescan: tags, time travel, Lance's `delta` (equal
  to a SQL `EXCEPT` of two versions), and the mdim-refs global view with
  remap, in DuckDB and DataFusion, reproducing the flat export row for row.
  Five oracle windows (84 chunks) read through the Lance refs match the
  GDAL hashes and a fresh osgeo.gdal read.
- **Lance beats the thin layer where the thin layer is thin.** Parquet
  fragments plus a create-only manifest commit took about 100 lines and
  handled append, time travel and a two-writer race. It has no deletion
  files, so a one-day rescan rewrote half a year of rows; compaction,
  version cleanup that respects tags, and a row-level delta would each be
  more code. That is the list of things Lance already has.
- **The striking result is about Icechunk, not Lance.** The same daily
  history in Icechunk costs 22 MB with manifests split per day, 116 MB
  split per 30 days, and 1.84 GB split per 365 days, because each commit
  rewrites the whole manifest its day falls in. The current render default
  (365) is right for a one-shot render and wrong for a daily-appended repo.
- **For refs, Lance is a good fit but not a needed one. For bytes it is
  the stronger case.** A refs table is small, and any format serves it. Lance
  is built for large binary values with fast row access, and its blob
  column holds each value either inline or as an external
  (uri, position, size) range, read the same way. That is the mdim-refs
  `data` / `offset` / `size` pair and the m05 `held` states in one column.
  On a 1,890-chunk box (234 MB) of held GHRSST bytes, a chunk comes back by
  row in 1 ms. The oracle window decodes from held bytes with no network. A
  reprocessed day changes only the new version, and the scan tag still
  reproduces GDAL. A mixed table of held and referenced chunks reads through
  one call. This is the zaro position ("the table is the store, Arrow is the
  codec engine") with history added (section 7). Section 8 proposes,
  provisionally, how mdim-refs `data` maps onto that column.
- **Recommendation: do not adopt Lance for refs yet.** Nothing that reads the
  stores needs "as of" today; most versioning is already columns (sources
  keyed by file, prelim and final as distinct sources); and R and GDAL,
  the first readers, cannot read Lance. Keep SQLite as the working store
  and the flat Parquet as the published middle stage. Name the triggers
  that would change this (section 6). Act now on the Icechunk split. For
  held bytes (the chunk cache, a hardened zaro store), Lance is the first
  table format to try when that work starts.

## 1. What was built

```
store.sqlite (mdim-refs/0.2, raad.virtualize)
   |  lance_load.py: same columns, commit order sources -> placements -> chunks
   v
sources.lance   placements.lance   remap.lance   analysed_sst.lance
   (append)        (append)          (once)        v1 bulk days 0..181   tag first-half
                                                   v2..v185 one day each tag year
                                                   v186 rescan of day 100 tag rescan
```

One Lance dataset per mdim-refs table, because a Lance commit covers one
dataset. A reader therefore needs one snapshot handle: the chunk table's
version (or a tag on it). The small tables only gain rows, and the writer
commits them first, so a reader pinned to chunk version N that reads
`sources` and `placements` at latest still resolves every row it sees.
This "commit point" convention is the price of no multi-table
transaction. Icechunk has cross-array atomicity in one snapshot; a
many-array store in Lance would need either this convention per array or
one chunk table with an `array` column (a schema change, so not done).

## 2. The Icechunk features, tested as table operations

The "Bytes in place" mapping, now with a result per row.

| Feature | Table form | Kind | Result here |
|---|---|---|---|
| Virtual chunk containers, relocation | remap joined to `sources` at read (longest prefix) | view | Worked. Cost is O(sources), 366 rows, not O(chunks). The machine running the test could not reach `data.source.coop`; the store's `s3direct` remap rows fixed that with no rewrite, for the table and for GDAL (the same rows applied to the plan VRT) |
| Global chunk index | `refs_<array>` view over placements | view | DuckDB 0.49 s, DataFusion 1.17 s for 935,496 rows; row hash equal to the flat export |
| Snapshots, tags | Lance versions and tags | storage | Worked; cleanup refuses to drop a tagged version unless told to skip tags |
| Append as commit | Lance append | storage | 0.011 s median per day (2,556 rows) |
| Upsert of a rescan | `merge_insert` on (source_id, dim_*) | storage | 2,556 rows updated, 0 inserted, 0.10 s; deletion file, no rewrite |
| Diff | Lance `delta`, or `EXCEPT` of two versions | view, given snapshots | 470,304 inserted rows both ways (EXCEPT 0.24 s); 2,556 updated for the rescan |
| Time travel | open at a version or tag | storage | 465,192 / 935,496 / 935,496 rows at the three tags |
| Conflict handling | Lance optimistic retry | storage | Two appends from one base both land (187, 188); two upserts of the same day both land with the row count unchanged |
| Manifest splitting | fragments, compaction | layout | 186 fragments compact to 1 in 0.4 s |
| Expiration, GC | `cleanup_old_versions` | storage ops | Keeps tagged versions, so with three tags the store grew from 10.1 to 14.2 MB after compaction: history you tag is history you keep |

So the claim holds as stated: remap, index and diff are views; snapshots
and commits need a format that has them, and Lance does.

## 3. Lance against the thin layer

The thin layer, `frag_store.py`: each commit writes an immutable Parquet
fragment and then `_commits/<n>.json` (the full fragment list, added,
removed) with `PutMode::Create`. The writer that creates `<n>` owns that
version; the other gets `AlreadyExists`, reloads and retries. DataFusion
reads a version as a pyarrow dataset over its fragment list.

| | Lance 13 | Fragments + create-only manifest |
|---|---|---|
| Code to own | none (a dependency) | about 100 lines for append-only |
| Daily append | 0.011 s | 0.007 s |
| Rescan of one day | deletion file + new fragment, 0.10 s | copy-on-write of the fragment holding the day: 465,192 rows rewritten, 0.44 s |
| Race | retried inside Lance | one retry, by construction |
| Diff | row-level `delta`; or EXCEPT | fragment-set difference (1 added, 1 removed); rows by EXCEPT |
| Compaction, cleanup with tags | built in | to write |
| Bytes, one year with history | 13.8 MB (all four tables) | 22.2 MB (Parquet footers on 366-row and 1-row files) |
| Readers | pylance, Rust `lance`, DuckDB and SedonaDB via Arrow streams, DataFusion via an FFI table provider pinned to one DataFusion major (54 accepted, 55 refused) | anything that reads Parquet, including GDAL, R arrow and DuckDB; the manifest is JSON |
| Format churn | Lance file format versions 2.0 to 2.3 and a fast-moving Python package (13.0.0) | Parquet and JSON |

Both share two habits worth knowing. Each version's manifest lists every
live fragment, so manifests grow by about 137 bytes per fragment in Lance
(1,051 bytes at version 1, 26,313 at version 185) and all of them are kept
until cleanup: quadratic history without compaction, in every design here.
And neither enforces a key: a day appended twice is in the table twice
(Lance: 938,052 rows after a repeated append). Ingest must be an upsert on
the within-source key, which is already how mdim-refs defines a rescan.

SedonaDB 0.5.0 read a Lance version as an Arrow stream (whole scan, no
pushdown into Lance); it did not accept the Lance DataFusion provider. For
query pushdown today the path is DataFusion with matching majors, or
DuckDB.

Answer to the open question: if history is wanted, Lance, not the thin
layer. The thin layer is attractive only while the table is append-only
and nobody tags anything; the first rescan, the first compaction and the
first "what changed" request each turn it into a small Lance, written
again. That is the "do not grow one" reminder, confirmed by measurement.

## 4. Icechunk with daily commits

The same history (half-year bulk, 184 daily commits, one rescan) written
to Icechunk 2.3.0 with the virtual refs of the flat export, manifests
split along time:

| Split (days per manifest) | Repo size | Manifests | Daily commit, median | Replay |
|---|---|---|---|---|
| 1 | 21.9 MB | 367 | 0.023 s | 16 s |
| 30 | 116 MB | 192 | 0.056 s | 14 s |
| 365 | 1,840 MB | 186 | 0.99 s | 192 s |

Every snapshot remains readable at its tag in all three. A daily commit
rewrites every manifest touched, and with a 365-day split that is the
year's manifest: about 10 MB per day, growing. Splitting by the append
unit (one day on time for a daily product) keeps a commit proportional to
the day. For a one-shot render the large split is fine and gives fewer
objects; the choice depends on whether the repo is a render or a log.

Also seen: Icechunk 2.3 deprecates `None` as the credential for an
anonymous virtual chunk container (pass the explicit HTTP access
sentinel instead); a render that passes `None` for public buckets will
need that change before a later release refuses it.

## 5. Bytes

`lance_bytes.py` resolves each oracle window in the store's manifest
through the Lance refs at the `rescan` tag, remapped to `s3direct`,
fetches each range, decodes (zstd, then TIFF horizontal differencing),
assembles the window and hashes it.

| Window | Chunks | Matches manifest (GDAL 3.13.3) | Matches osgeo.gdal 3.12.4 now |
|---|---|---|---|
| chunk-t0-y0-x0 | 1 | yes | yes |
| tile-tlast-y25-x63 | 1 | yes | yes |
| row-tmid-y17000 | 71 | yes | yes |
| edge-tlast-y35-x70 | 1 | yes | yes |
| block-t0to9-hobart | 10 | yes | yes |

The GDAL read is the plan VRT with the `gdal-s3direct` remap rows applied
to its source paths: the same rows, rendered for the other reader. The
rescan upsert left the bytes right, and the remap view is proven on the
bytes, not only on the rows.

## 6. What it buys, what it costs, what if not

**What we get with Lance as the store of record:** reproducible reads "as
of" a tag; upsert and diff without code of our own; concurrent writers
without a server, by the same put-if-absent mechanism Icechunk uses; a
history that costs about 2.6 times the flat export for a year of daily
commits.

**What it costs:** a fast-moving format and package in the path of every
reader; DataFusion version coupling; no R or GDAL reader, against the
"R users first" reminder; one dataset per table, so cross-table
consistency rests on a convention; and an operational duty (compaction,
cleanup, tag policy) that a write-once Parquet export does not have.

**What if we don't:** today, nothing breaks. The working store is SQLite
on one machine with one writer; the published form is a Parquet export
rewritten whole; consumers read the latest. Prelim and final are distinct
sources, a day is new rows keyed by source, and "which granules were used
on date X" is a plan question. That covers most of what versioning would
answer for these stores.

**Triggers that would change the answer:**

1. A second writer to the same store (for example scans run where the
   data is, at more than one site, into one table).
2. A consumer that cites a version (a paper, a derived product, a cache
   validated against a snapshot).
3. A published table too large to rewrite whole on each update (the full
   GHRSST series is 22.8M refs for one variable; a daily rewrite of that
   export is where an append-only versioned table starts to pay).

When one of them arrives, the step is small: a Lance emitter beside the
Parquet export in the producer, the commit-point convention above, tags
named by date, cleanup that keeps tags. The measurements here are the
first test of it.

**Act now:** split daily-appended Icechunk repos by the append unit along
time (section 4). That is the one result that changes something already
planned (daily GHRSST and BRAN updates).

## 7. Holding the bytes, not only the refs

Section 1 to 6 version a table of references; the bytes stay in the
provider's files. The other reading of "Lance for arrays" is the table
holding the chunk bytes. mdim-refs already allows it (`data`, present
and inline), and m05 proposes held copies beside refs (`held = copy`) for
the chunk cache. That reading sharpens the position zaro takes in its
design notes: the Parquet is the store, Arrow the codec engine, no GDAL in
the pixel path. What it lacks is a way to hold bytes that can be revised
without losing what was read before. Scripts: `lance_held.py`,
`lance_extblob.py`.

**Held box.** Days 0 to 29 of 2024, chunk rows 24 to 30 and columns 60 to
68 (Tasman Sea to south of Tasmania): 1,890 chunks, 234.3 MB of encoded
bytes, fetched through the `s3direct` remap in 51 s with 16 threads. The
mdim-refs chunk columns are unchanged, with `data` filled and `offset` and
`size` kept (a held copy).

| Store of the same 1,890 rows | Size | One chunk by key, mean of 50 |
|---|---|---|
| Parquet, one row group | 234.4 MB | 436 ms |
| Parquet, 64-row row groups | 234.4 MB | 29 ms |
| Lance, binary column, filter | 234.4 MB | 59 ms (no index; scans keys) |
| Lance, binary column, take by row | same | 1.0 ms |
| Lance, blob column | 234.4 MB | 4 ms to find the descriptor, then about 5 ms to read |

Sizes are equal because the bytes are already compressed. The difference
is access. Parquet reads in row groups, so a big row group means reading a
lot to get one chunk. Lance reads single rows, so once a key maps to a row
(a sorted key, or a scalar index), getting one chunk costs about as much as
a local file read.

**Versioned bytes.** The box was written as 20 days bulk, then 10 daily
commits, and tagged `scan`. Day 5's 63 chunks were then overwritten (with
day 6's bytes, a stand-in for a reprocessed granule) by `merge_insert`.
The oracle window block-t0to9-hobart decoded from held bytes only, with no
network, gives this:

| Version | Matches GDAL hash | Days differing from `scan` |
|---|---|---|
| tag `scan` | yes | none |
| latest | no | day 5 only |

A reference cannot do this. If the provider overwrites a file, every ref
into it is stale, and the best a refs table can do is detect it (`sources`
mtime and etag). A versioned table of held bytes keeps what was read, by
tag, while the latest version follows the provider.

**One column, refs and bytes.** Lance blob values have a kind. Kind 0 or
1 is the bytes, held in the dataset. Kind 3 is an external range: uri,
position, size. `read_blobs` returns bytes for either. The whole 2024 table
was written with each chunk as an external blob into the source COGs: 10.7
s for 935,496 rows, read through Lance's object store. Then 315 chunks
(days 0 to 4 of the box) were promoted to held bytes by `merge_insert`.
The Hobart window read through one `read_blobs` call, 5 external and 5
held, matches the GDAL hash, and so does the refs-only tag. That is m05's
cache promotion (`ref` to `copy`) as an ordinary versioned upsert.

Limits seen:

- Lance's object store reads `s3://`, `gs://`, `az://` and `file://`, not
  `https://`. External blobs need a remap target in one of those schemes
  (`s3://us-west-2.opendata.source.coop/` here, anonymous). That is one
  more reason remap stays a view.
- The external uri is stored in full on each row: 56 MB for the year,
  against 10 MB for the plain columns with `source_id`. Plain columns
  stay the better layout for a refs-only table. External blobs earn their
  place where some rows are held.
- No R reader, as before. A hardened zaro on this layout would read Lance
  through Arrow streams from a Python or Rust helper, or wait for a Lance
  reader in R.

What it buys: a store that answers a chunk by key in milliseconds, keeps
what was read when sources change, and moves a chunk from referenced to
held without a new schema. What it costs: the bytes (234 MB here for 30
days of a small box; about 335 MB a day for the whole globe), a Lance
dependency in the reader, and a cache policy someone must own. What if
not: refs plus a range cache stay correct while sources are immutable,
and that holds for this archive today. The case strengthens when the
data is a mutable provider (NRT products, reprocessing) or when a
derived chunk has no source file at all.

## 8. Proposal: the `data` column as a Lance blob (provisional)

Provisional default, for review. It extends the mdim-refs chunk table and
m05's held columns. It is not a new schema. It applies only where a store is
held in Lance. SQLite and the Parquet export keep `data` as BLOB / binary.

**Columns.** The mdim-refs chunk table is unchanged
(`source_id`, `dim_0..n`, `present`, `offset`, `size`, `info`). In Lance,
`data` is a blob v2 column. m05's `held` and `hash` come along when a
store holds bytes.

**States.** Each block-info state, and each m05 held state, maps to one
row form:

| State | `present` | `offset`, `size` | `data` (Lance blob) | `held` |
|---|---|---|---|---|
| absent | 0 | null | null | `ref` |
| referenced | 1 | set | null | `ref` |
| inline (the only copy) | 1 | null | inline bytes (kind 0 or 1) | `inline` |
| held copy of a referenced chunk | 1 | set | inline bytes | `copy` |
| referenced, published render | 1 | set | external range (kind 3: uri, position = `offset`, size = `size`) | `ref` |

Null and inline blob values are written and read side by side
(`read_blobs` returns None for null), so the first four rows are one
column with no special cases.

**Remap stays a view in the store of record.** In the working store and
in any Lance copy that is the store of record, a referenced row keeps
`data` null. Its bytes are found through `sources` and the `remap` view,
as now. This keeps relocation a one-row change and avoids storing a full
uri on every row (56 MB against 10 MB for the 2024 refs).

**External blobs are a render.** A Lance render for one remap target may
fill `data` with external ranges, so that a reader needs only
`read_blobs` and nothing else from mdim-refs. That binds the remap when the
render is published, which is what "remap at publish" already means for
the other renders. The target's scheme must be one Lance's object store
reads: `s3://`, `gs://`, `az://` or `file://`. An `https://` target needs
an s3-scheme twin in `remap` (for source.coop:
`s3://us-west-2.opendata.source.coop/`, anonymous).

**Promotion and expiry are upserts.** A cache moving a chunk from
`ref` to `copy` is a `merge_insert` on the within-source key that sets
`data`, `held` and `hash`. Dropping held bytes is the same upsert with
`data` null. Tags keep earlier versions readable, so a cache can expire
bytes without breaking a tagged read, until cleanup removes that tag.

**Validity.** A held copy is valid while its source matches `sources`
(`size`, `mtime`, `etag`), as in m05. When a source changes, the held
row is kept: it is what was read. The new scan arrives as a new version,
and the earlier tag still reads the old bytes.

**Readers.** In order of reach:

1. Any Lance reader (Python, Rust) through `read_blobs`, on a render with
   external ranges.
2. The same, on the store of record. Rows with null `data` and
   `present = 1` resolve through `sources` and `remap`, as an mdim-refs
   reader does now.
3. R and GDAL: none yet. They keep the VRT and the Parquet export, where
   held bytes are a plain binary `data` column.

Not proposed: a Lance-only column, a different key, or putting
`sources` and `placements` in the same dataset as the chunks.

## 9. Open questions

1. Is one chunk table per array the right Lance layout for a many-array
   store (BRAN has several variables), given that a Lance commit covers one
   dataset? The alternative, one table with an `array` column and a list
   of keys, changes the schema and is not proposed.
2. Does the Lance R story change (a reader in R without Python) before
   any of the triggers arrive? If not, Lance stays a producer-side store
   with Parquet and VRT as the published forms.
3. DuckLake and Delta Lake were not tested. DuckLake needs a catalog
   database; Delta's log commit is put-if-absent as Lance's is, and Delta
   tables are readable from R through DuckDB. Worth one replay each if the
   triggers arrive.
4. For held bytes: is the right unit the chunk (one row per chunk, as
   here) or a held copy of the whole source file with the refs pointing
   into it (`held = link`)? The first gives versioned chunks; the second
   keeps file-level validation against `sources` simple.
