# m05: The chunk cache as a growing implicit store

Status: musing, 2026-10-17; its four questions answered the same day
(section 8), so pilot C1 is ready to pick up. It explores an idea
of Michael's and ends with a smallest pilot and the questions that would
turn it into work; it becomes work only through a numbered document.

## 1. The idea

Michael, 2026-10-17:

> When we plan a source to warp we have this indirection where byte refs
> (chunks) are cached in a flat table, when those are read there's an
> opportunity to cache them undecided and the table is a natural place
> with a binary blob column or another store with a link. There's another
> opportunity to cache target chunks after warp which could have the same
> structure, refs, link, encoded chunk - or the chunk's data can be
> rendered, sent somewhere else, discarded. Zarr is a materialized store
> but our tabular cache of source (and potentially target) provides a
> growing implicit store that doesn't preclude later reuse, and doesn't
> dictate format.

Put plainly: every read wxylib makes already passes through a row of a
byte-reference table (where the chunk is) or could. If the bytes that come
back are kept, still encoded, next to that row, the table grows from an
index into a store. Nobody decided to build a Zarr copy; one accumulates,
covering exactly what was looked at, in the source's own encoding, and it
can still be published as Zarr or Icechunk later. The same row shape works
on the far side of a warp, where a target chunk can be kept, linked,
handed on, or thrown away, with the row recording which.

### Where it came from

- **cogcache** (rgdal-dev/cogcache, `inst/doc-archive/cog-duckdb-cache.qmd`
  and `cog-duckdb-prototype-sketch.md`, 2026-03): a COG's tile catalog in
  DuckDB (`tile_col, tile_row, byte_offset, byte_length`, extents), raw
  tile bytes fetched by range request into a `raw_bytes BLOB` column, and
  decoded outside GDAL to pixels identical to GDAL's read. "The deliverable
  is a `.duckdb` file you can hand someone and say this *is* that COG's
  tile structure, and here are the actual bytes." rwarp grew out of the
  same repository.
- **blocklist** (hypertidy/blocklist): byte refs as a flat table
  `(path, offset, size, raw)` written as kerchunk Parquet. The `raw`
  column is kerchunk's inline chunk; blocklist leaves it empty. Offsets
  are copy-invariant, so a table scanned on one copy of a file is valid
  for every byte-identical copy (`access` and `public` paths).
- **mdim-refs/0.2** (`specs/mdim-refs-0.2.md`): the chunk rows already
  carry `data BLOB`, used today for inline chunks (`present = 1`, `offset`
  null). `wxy-virtual` reads it (m02).
- **wxylib/web** `src/fetch.rs`: the browser reader keeps every range it
  fetched in a `HashMap<(offset, len), Bytes>`, so panning re-reads tiles
  from memory. It is the same cache, unnamed, per page and lost on reload.

So the blob column has been sitting in three tables for a while. What is
new here is treating it as the main event: a cache that is also a store.

## 2. What it joins in wxylib today

- **The fetch and decode split.** `ChunkSource` (wxy-source) separates
  `fetch` (I/O, returns `Encoded`) from `decode` (CPU). Doc 02 section 5
  already says the block cache (survey M16) "belongs to the fetch step,
  keyed by chunk key, shared across fields and plans". This musing is that
  cache, made persistent and kept encoded.
- **Plans as values.** `Explain` and `--dry-run` list every chunk a warp,
  point read or zonal summary fetches, in fetch order, with stored bytes
  where the source knows (core 50ed027). Against a cache, a dry run can
  also say which of those are held and how many bytes the run would
  actually move. That is the cheapest visible payoff.
- **WarpPlan batches and GridWriter.** S4b streams whole source chunks in
  batches and writes target chunks through `wxy-zarr`'s `GridWriter`.
  Both ends already handle one chunk at a time; a cache hook on each end
  is a tap on an existing stream, not a new pipeline.
- **The ref table and Icechunk.** Gate 4 made Icechunk the reference store
  and asked to keep exploring a flat table where Icechunk is overkill.
  Icechunk holds virtual refs and native chunks side by side; a cache row
  with bytes is a native chunk waiting to be written, a row without is a
  virtual ref. The cache is the flat table, with a path to Icechunk.

## 3. Two caches, one row shape

| | Source side | Target side |
|---|---|---|
| Key | source, array, level, chunk key | plan id, chunk key |
| Reference | path, offset, size (+ etag) | where it was sent, if anywhere |
| Held | encoded bytes inline, or a link | encoded bytes inline, or a link |
| Fate | held, not held | held, linked, rendered, sent, discarded |
| Lineage | none (it is the origin) | the source rows it was computed from |

**Source rows** are a ref table row plus what was read. The bytes are the
stored bytes exactly as fetched (compressed, predictor applied, as the
format left them), never decoded: format-neutral, small, and checkable
against `size` and a hash.

**Target rows** need a key that captures everything that decided the
output: the source identity and version, the target `GridSpec`, the
`WarpOptions`. All of these already serialise (plans as values), and plans
are rebuilt from those inputs rather than deserialised, so a hash of their
canonical serialisation is a usable **plan id**. A target chunk's fate
column records what happened to it: kept encoded in the table, written to
a store and linked, rendered to a PNG tile and sent, or computed and
dropped. A dropped chunk still leaves a row, and that row is what lets a
later request skip the work or know exactly what to recompute.

Lineage (target row to source rows) is the piece no Zarr store holds. It
answers "a new source granule arrived, which target chunks are stale",
the incremental warp in cogcache's `VWARP_VISION.md` item 15.

## 4. Design points, and what is hard

**Two places to key a cache.** A range cache sits below the format, keyed
on `(path, offset, size)`, wrapping async-tiff's `AsyncFileReader` or an
`object_store` store. It needs no format knowledge and catches header and
IFD reads too, so a held COG opens offline. A chunk cache sits on
`ChunkSource`, keyed on the chunk key, but `Encoded.payload` is
`Box<dyn Any>` (an async-tiff `Tile` for TIFF, bytes for Zarr), so it
would need the trait to hand out bytes and rebuild an `Encoded` from them.
The ref table already holds both keys in one row, so the cache does not
have to choose: store by range, and the chunk key comes from joining the
ref table on `(path, offset, size)`. The range layer is the place to
start.

**Ranges must be the requested ones.** `object_store`'s `get_ranges`
coalesces nearby ranges. The cache must sit above that (at the
`AsyncFileReader`, where async-tiff still asks per tile) so that rows are
one tile each; otherwise lookups need interval containment, not equality.

**Validity.** A held chunk is valid while the source is unchanged:
mdim-refs `sources` already has `size`, `mtime` and `etag`. A held row
keeps the etag it was read under; a mismatch on open invalidates the
source's rows. Copy-invariance means the bytes stay valid when a table is
re-pointed from `access` to `public` paths.

**Inline or link.** Small chunks inline in the table; large ones, or a
cache meant to be shared, as content-addressed files (`blobs/<sha256>`)
in any object store, with the table holding the hash. Content addressing
also deduplicates the empty and fill-only tiles that recur across a
collection.

**The table engine.** Parquet is immutable, so a growing cache is a
directory of append-only fragments (one per run), compacted later; reads
see the union, and concurrent writers never contend. SQLite (as
mdim-refs 0.2) or DuckDB (as cogcache) give upserts and eviction queries
but a single writer, and SQLite does not build for the browser. In the
browser the same rows could live in OPFS. Fragments suit "growing" best.

**Not dictating format, and its limit.** Held bytes stay in the source's
encoding, decoded by the same reader that fetched them. Materialising to
Zarr works when the encoding has a Zarr codec chain: OISST's zlib and
shuffle do; a TIFF tile with predictor 2 does not map cleanly to a Zarr
`delta` filter (cogcache's kerchunk notes), so such bytes publish to
Zarr only by re-encoding. That is a fact about the export, not about the
cache: the cache never needs to care.

**Eviction and growth.** "Growing" is the point, but disks fill. A
`last_used` per row cannot be updated in place in Parquet; a small access
log fragment can stand in. Out of scope for a pilot.

**Holding a copy is distributing a copy.** A cache handed to someone
carries the data, so it carries the source's licence. Worth one line in
any user-facing doc.

## 5. Schema sketch

An extension of the mdim-refs/0.2 chunk row, not a new format. New
columns are marked `+`.

Source rows (one table per array, or one with an `array` column):

| column | type | note |
|---|---|---|
| `source_id`, `dim_0 .. dim_{n-1}` | key | as mdim-refs |
| `present`, `path`, `offset`, `size`, `info` | | as mdim-refs |
| `data` | BLOB | the held bytes, or null |
| `+ held` | enum | `ref` (not held), `inline` (the only copy), `copy` (held copy of a referenced chunk), `link` |
| `+ link` | TEXT | URI of the held bytes when `held = link` |
| `+ hash` | TEXT | sha256 of the bytes, when held |
| `+ etag` | TEXT | the source etag the bytes were read under |
| `+ fetched` | timestamp | |

The `copy` state is the one change to mdim-refs semantics: today `data`
set means `offset` is null (inline). A held copy has both. Readers that
ignore `held` still read correctly from `path`, `offset`, `size`.

Target rows, plus a `plans` table (`plan_id`, the serialised inputs as
JSON, the codec chosen for the target array):

| column | type | note |
|---|---|---|
| `plan_id`, `dim_0 .. dim_{n-1}` | key | |
| `fate` | enum | `inline`, `link`, `rendered`, `sent`, `discarded` |
| `data`, `link`, `hash` | | as above |
| `sources` | list | source row keys read for this chunk (lineage) |
| `computed` | timestamp | |

The range-level pilot below needs only `path, offset, size, data, hash,
etag, fetched`: a ref table without the keys, which the join supplies.

## 6. Opt-in, configurable, and level with GDAL's caches

Off by default: a run without `--cache` behaves exactly as today. The
cache is configured, not implied: where it lives, inline threshold,
which side (source, target, both), and read-only use of someone else's
cache.

GDAL has two caches this must at least match:

| GDAL | What it is | Here |
|---|---|---|
| block cache (`GDAL_CACHEMAX`) | decoded blocks, in memory, per process | the in-memory decoded cache M16 already plans on the fetch side |
| `/vsicurl/` range cache (`CPL_VSIL_CURL_CACHE_SIZE`) | fetched ranges, in memory, per process | the range layer of C1, with an in-memory mode and the same size cap |

What it adds beyond them: it persists across runs and machines; it holds
bytes encoded, so it is small and format-neutral; it is a table, so it can
be queried, joined to the ref table, handed on and published; plans can
see it (`--dry-run` hits and misses); and on the target side it records
what was computed and from what, which neither GDAL cache does.

## 7. Smallest pilot

**C1, a persistent range cache under `wxy-tiff`.** A wrapper
`AsyncFileReader` that looks up `(path, offset, size)` in an in-memory
index loaded from a directory of Parquet fragments, fetches misses through
the inner reader, and appends what it fetched as one new fragment when
dropped. Plumbed into `wxy warp` as `--cache DIR`.

Done when:
- `wxy warp --cache DIR` on a fixture COG, run twice, makes zero inner
  reads the second time and writes identical output;
- `wxy warp --dry-run --cache DIR` adds held and missing counts and bytes
  to the plan's `fetch` summary;
- the fragments, joined to an mdim-refs table for the same COG on
  `(path, offset, size)`, give back the chunk keys `Explain` listed.

No trait change, no new format, no target side. C2 (the same wrapper
over `object_store`, for Zarr and virtual sources) and T1 (target rows
from `GridWriter`, keyed by plan id, with fate and lineage) follow only if
C1 earns them. Publishing a fully held array as kerchunk Parquet with
`raw` filled, or as Icechunk native chunks, is the materialisation step
and comes after T1.

## 8. Questions that would turn this into work

Answered by Michael, 2026-10-17:

1. Byte-range level.
2. Append-only. Rows say where their bytes came from, so held data can
   be flushed or moved to another store for more sophisticated handling
   later; DuckDB is a tiny step from there, and not in scope.
3. The `copy` state goes into mdim-refs after the pilot proves it.
4. Yes, a small `wxy-cache` crate.

So pilot C1 (section 7) is the next step, as core work. The questions as
asked:

1. For a referenced chunk the chunk is the byte range, so the row is the
   same either way; the question is only where the hook sits. At the
   byte reader first (recommended: bytes are already bytes there, no
   trait change, and header reads come along), or on `ChunkSource`,
   which is the only place chunks with no byte range (GDAL-workaround
   blocks, computed chunks) can be held?
2. Engine: append-only Parquet fragments (recommended: growing, no write
   contention, wasm-friendly) or SQLite/DuckDB?
3. Should the `copy` state go into the mdim-refs spec now, or wait for a
   pilot to prove it?
4. Home: a small crate (say `wxy-cache`) depending only on async-tiff,
   object_store and parquet, owned with core by the planning thread.

## 9. What we would get, what it costs, what if we didn't

- Get: second and later runs over the same region move no bytes;
  `--dry-run` says what a run will really cost; a cache you can hand
  someone ("this is that COG", cogcache's phrase) that is still just a ref
  table; a store that accumulates without anyone choosing a format; on the
  target side, lineage for incremental rewarps and a record of what was
  computed even when the output was thrown away.
- Cost: one more crate and a column convention to keep in step with
  mdim-refs; validity and etag handling done carefully, because a stale
  cache is worse than none; disk growth with no eviction story yet; held
  TIFF bytes that are not directly publishable as Zarr.
- Without it: every run refetches; the browser cache stays per page; the
  ref table remains an index only, and caching is left to whatever each
  object store or HTTP layer happens to do, invisible to plans.
