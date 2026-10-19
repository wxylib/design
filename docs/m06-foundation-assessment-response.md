# m06: Response to the foundation assessment

Status: musing, 2026-10-17. A response, not a plan: each point below
says where it would land, and becomes work only when the owning document
or repository picks it up. Changes it proposes to doc 03 are listed in
section 5.

An assessment of wxylib was written from the adjacent cogcache,
blocklist, sds and bowerbird work (2026-10-17). Its scheme:
bowerbird and sds as the catalog, a `gdal mdim mosaic` VRT as the plan,
the mdim-refs/0.2 byte-reference table as the cross-language contract,
then Icechunk (C) and kerchunk Parquet (D) as outputs, R users first.
Its verdict is that wxylib is a strong foundation for the consumer and
sink end of that scheme, and not the home of the table itself.

This note checks each gap and push-back against the repositories as they
stand (core a2d7cf0, fixtures 6c703cb, design 1c30f96, r 0b479dd) and
says agree, partly or disagree, with the evidence. The verdict itself is
agreed: wxylib reads the table and is not where the table is made.

## 1. Summary

| # | Point | Verdict | Lands in |
|---|---|---|---|
| 1 | Table producer (step B) has no public home | Agree | Out of scope for wxylib; decided in section 6 |
| 2 | "Table first" not closed: the only read path materialises Icechunk | Agree | core: a flat refs store (section 3) |
| 3 | Only one chunk per file tested | Partly | fixtures: a small Bluelink-shaped fixture in CI |
| 4 | Icechunk does not serve R users; who owns kerchunk Parquet (D) | Agree | Out of scope: D stays with blocklist |
| 5 | R binding far from R users; CRAN feasibility | Agree | r, after item 2, with a feasibility check first |
| 6 | S7 and the m03 map document risk a new format | Agree | doc 03 S7 wording; m03 |
| 7 | No seam to the sds catalog | Agree | Out of scope for wxylib |
| 8 | Pace versus ownership | Agree | Decided in section 6 |
| 9a | `ChunkSource::stored_bytes` empty for refs-backed sources | Agree | core, with item 2 |
| 9b | GDAL 3.13 `GetRawBlockInfo` errors on an unwritten chunk | Agree | Upstream GDAL issue |
| C1 | Cache pilot misses the refs and Icechunk read path | Agree | wxy-cache interface now; C2 becomes the flat refs store |
| C2 | Key on the source, not the resolved path | Agree | C1 key |
| C3 | THREDDS validity fallback | Agree, plus a gap | C1 validator column; Parquet export lacks `sources` |
| C4 | Compaction and scale | Agree | C1 directory layout |
| C5 | `copy` read order in zaro | Checked: safe | mdim-refs spec note when `copy` lands |

C1 to C5 are folded into pilot C1 before it starts.

## 2. The gaps, one by one

**1. The table producer has no public home.** Agree. Step B lives in
fixtures as `scripts/make_mdimrefs_oisst_198109.py` (a scanner through
osgeo.gdal) and `scripts/make_mdimrefs_bran2023_temp.py` (a converter
from the kerchunk Parquet index in mdsumner/virtualized, not a scanner),
and in blocklist and byteref on the R side. wxylib's scope is narrower
than "by its own design" suggests, though: principle A6 makes scanners
wxylib's business (`wxy_virtual::scan_tiff` exists), so scanning one
file into chunk rows is in scope. What is out of scope is placement:
turning a mosaic VRT into a global chunk grid is the plan, and the plan
is the VRT. Recommendation: the producer gets its home outside wxylib
(any R producer that reproduces the fixture tables, section 6); fixtures
keeps the Python scanner as the oracle builder. A Rust scanner that
emits mdim-refs rows (the DMR++ idea, assessment item 6) is the natural
first wxylib scanner that is not GDAL, and is a later musing, not now.

**2. "Table first" is not really closed.** Agree, and m04 section 2
overstated it. `wxy-virtual` exposes `from_refs_table`, then
`write_icechunk` and `open_icechunk` (lib.rs); there is no path from the
table to zarrs without writing an Icechunk repository. Doc 03's own
open-topic text asks for "a flat sink and a reader over it (Parquet or
similar, served as zarrs storage)", which is still unbuilt. Lands as
core work, section 3.

**3. Only the easy case is tested.** Partly. Since the assessment's
snapshot, fixtures `mdimrefs/bran2023-temp-201001` (fixtures 2e9af6b)
added the many-chunks-per-file case: BRAN2023 `temp`, 4D, 300 x 300
chunks, 3060 per file per day, 97,920 rows, with core's `bran_refs`
example reading it through Icechunk (core 8c24d08). So the code path is
exercised. What is still true: it needs thredds.nci.org.au and is not in
CI, it has one variable and no unwritten chunk, and its manifest oracle
windows carry no SHA-256, so nothing compares it to GDAL yet. Also
untested in the refs path: LZW, predictors, and `s3://` references
(Icechunk is built with only `object-store-fs` and `object-store-http`,
so an `s3://` ref cannot be read today; the OISST walk-through's
https remap is the workaround). Lands in fixtures:

- a small synthetic Bluelink-shaped netCDF pair: two variables, 4D,
  several chunks per file, one unwritten chunk, zlib and shuffle; scanned
  with osgeo.gdal `GetRawBlockInfo` by `make_mdimrefs_fixtures.py`; GDAL
  oracle windows with hashes; a CI test in `wxy-virtual`;
- the BRAN oracle hashes computed where THREDDS is reachable (a
  local machine or NCI), by brief.

**4. Icechunk does not serve the priority audience; who owns D.** Agree
with the recommendation: kerchunk Parquet stays in R (blocklist), zaro's
reader gets fixed for the fsspec layout, and wxylib does not grow a D
emitter until something Rust-side needs one. Not re-checked here: whether
GDAL 3.13 reads Icechunk (believed not; it does read kerchunk Parquet
through `/vsikerchunk_parquet_ref/`). One thing wxylib can do cheaply:
the flat refs store in section 3 reads the same row shape as kerchunk
Parquet, so reading D as a second input is a small extension if it is
ever wanted. Not proposed now.

**5. The R binding is far from R users.** Agree. wxylib/r is pinned to
core 39b07bb and its DESCRIPTION describes a matrix warp, regularity test
and geotransform: no sources, no refs. `wxy-virtual` declares
`rust-version = "1.95"` (the only crate that does), and its tree includes
Icechunk, tokio, arrow and zarrs. The flat refs store helps here
directly: an R binding over it drops Icechunk and its networking stack,
which is most of the vendored weight. Lands in r, after section 3, and
starts with a CRAN feasibility check (vendored tarball size, the MSRV the
dependency tree really needs, against what CRAN's builders carry). The
cheaper R win the assessment names (a gdalraster binding of
`GetRawBlockInfo`) is upstream of wxylib.

**6. S7 risks a new format.** Agree. Doc 03's S7 row ends "a new file
format to design". The plan already has a serialisation: the mosaic VRT
(Source, SourceSlab, DestSlab) and the mdim-refs table. S7 should take
those as inputs and serialise only what neither carries (compute steps,
features and mesh), and that remainder is a decision for S7's own gate,
not a given. The m03 map document has the same risk: it should
reference sources by a VRT or an mdim-refs table, not inline its own
source description. Proposed wording in section 5.

**7. No seam to the catalog.** Agree that sds has no kinds for
`mdim_refs`, `icechunk`, `kerchunk_parquet` or `mdim_vrt`, and that this
is sds's work, not wxylib's. wxylib's side of the seam is already the
table and its `remap` targets; fixtures manifests name the published
URLs an sds entry would point at.

**8. Pace versus ownership.** Agree that the oracle tests protect
correctness, not understanding. The crates held to the "own every
line" bar are `wxy-virtual`'s refs reader and the flat refs store, as the
assessment suggests, because they are the contract with zaro and
blocklist (section 6).

**9a. `stored_bytes` for refs-backed sources.** Agree. `ChunkSource`'s
default returns `None` (wxy-source lib.rs) and only `wxy-tiff` overrides
it; `wxy-zarr`'s source does not. A refs-backed source knows every
chunk's `size` from the table, so `--dry-run` could report real bytes for
OISST and BRAN. Through Icechunk the size is behind the manifest; through
the flat refs store it is a column. Lands with section 3.

**9b. The GDAL 3.13 quirk.** Agree it deserves an upstream issue
(`GetRawBlockInfo` errors on an unwritten chunk instead of reporting it
absent). It belongs with the GDAL-side work; the synthetic fixture
in item 3 would make a clean reproducer.

## 3. Proposed: a flat refs store (and with it, C2)

A zarrs async storage that reads an exported mdim-refs table
(`arrays.json` and `refs_<array>.parquet`) directly: metadata from
`arrays.json` (the conversion `from_refs_table` already does), chunk
keys looked up in the Parquet rows, present rows fetched as byte ranges
through `object_store`, inline rows returned from `data`, absent rows
reported missing so zarrs fills. Icechunk stays as an optional sink:
`write_icechunk` keeps working from the same `VirtualArray`s.

The cache addendum's first point fits here: Icechunk fetches virtual
chunks through its own containers, so neither the C1 `wxy-tiff` wrapper
nor m05's planned C2 (an `object_store` wrapper) sees OISST or BRAN
reads. In the flat refs store, the reader already holds the row
(`path, offset, size`) when it fetches, so it can ask `wxy-cache` first
and append on a miss. Reader and cache become one component, and this
replaces m05's C2.

- Get: "table first" closed honestly; a read path that sidesteps
  Icechunk limits (bluelink hit them); real `stored_bytes` in plans; the
  thing bindings would expose, with a much smaller dependency tree; the
  place the cache sees every virtual read.
- Cost: one storage implementation to keep in step with zarrs' storage
  traits, and a second read path (direct and through Icechunk) to test
  against the same oracle.
- Without it: every read of a table writes an Icechunk repository first,
  the cache cannot see virtual reads, and bindings carry Icechunk.

## 4. The cache addendum (m05)

**C1 placement.** Agree (section 3). C1 itself can stay on COGs as
planned, provided `wxy-cache`'s index, fragment writer and lookup sit
behind a plain interface (get and put by key, offset and size) with no
async-tiff types, so the flat refs store reuses it unchanged.

**C2 key on the source.** Agree. m05 keys `(path, offset, size)` and
also relies on copy-invariance across `remap` targets, but `remap`
rewrites `path` per target, so a cache filled through `public` misses
through `access`. The Parquet export's `refs_<array>` view has no
`source_id`, so the key is the pre-remap path (the `sources.source` URI
as scanned), or the URL as given for a bare COG; the fetched URL is a
recorded column, not part of the key.

**C3 validity on THREDDS.** Agree, with one gap found. Record a
validator: the etag when the server gives one, else size and
last-modified, with a column saying which was used (or none). The gap:
m05 and the assessment both fall back to `size` and `mtime` from mdim-refs
`sources`, but the Parquet export carries no `sources` table
(`arrays.json` holds only `format_version`, `arrays` and `remap` in both
fixtures). The fallback needs the export to include `sources`, or the
cache to take size and last-modified from a HEAD request. A spec
proposal for the export, for whoever holds mdim-refs.

**C4 scale.** Agree. All of BRAN `temp` is about 16.8M chunks; an index
over every fragment in memory will not hold it. Partition fragments by
source (one directory per hashed source key, one fragment per run) so a
run loads only the sources its plan touches. This fixes the directory
layout, so it belongs in C1; compaction can still come later.

**C5 `copy` read order.** Checked: zaro's `mdimrefs://` reader
(R/mdimrefs.R) treats a row as inline when `path` is NA, and
`wxy-virtual` (refs.rs) when `offset` is null. A held copy has both
`path` and `offset` set, so both read it as a reference: safe. The two
readers use different discriminators, though, and the spec says
"`offset` NULL". When `copy` goes into the spec, it should state that
inline means `offset` null, and zaro should follow.

## 5. Proposed changes

- Doc 03, gate 4 open topic: not closed. Replace the m04 framing with
  "a flat refs store over the Parquet export is the default read path;
  Icechunk is a sink" and add the store as a stage (numbering decided
  in doc 03).
- Doc 03, S7 row: replace "a new file format to design" with "reads the
  mosaic VRT subset and the mdim-refs table as its inputs; any further
  serialisation (compute steps, features, mesh) is decided at S7's gate".
- m05 section 7: C2 becomes the flat refs store with the cache inside;
  C1 keys on the source and partitions by source.
- fixtures: the synthetic Bluelink-shaped refs fixture (section 2,
  item 3), then BRAN oracle hashes by brief.

m04's line "Doc 03's open topic can be closed" is marked superseded by
this note.

## 6. Decisions (2026-10-19)

1. **Step B's home: several producers, one contract.** The table is the
   contract, so the producer need not be one package. Three R routes
   exist, none of them in wxylib:
   - blocklist over rhdf5: reads the HDF5 chunk index directly, no GDAL;
     netCDF4 and HDF5 only, and not exposed to the GDAL 3.13 unwritten
     chunk error (gap 9b).
   - The gdalraster `gdalmultidim-api` branch (mdsumner fork): binds
     `GDALMDArray::GetRawBlockInfo` per chunk and a whole-array
     `getRawBlockRefs()` returning a data frame (filename, offset, size,
     info, one index column per dimension); any driver GDAL reads. It
     drops a chunk whose call fails as well as one that is absent, so on
     GDAL 3.13 an unwritten HDF5 chunk and a real error look the same.
   - GDAL7 (rgdal-dev): has an MDArray class and lazy chunked reads, but
     does not bind `GetRawBlockInfo` yet; as a generator over GDAL's SWIG
     interface it can take the method once GDAL's SWIG carries it
     (inferred, not checked).
   Any of them counts as a producer once it reproduces the fixtures
   tables (`mdimrefs/oisst-198109`, and `bran2023-temp-201001` for many
   chunks per file); the Python scanner in fixtures stays the oracle
   builder. A producer that tells a failed call from an absent chunk is
   preferred.
2. **Ownership bar:** `wxy-virtual`'s refs reader and the flat refs store
   are held to "own every line"; the rest is covered by oracle tests and
   review.
3. **Order:** the flat refs store comes before R bindings that open
   sources, which removes Icechunk from what R would vendor.

## 7. What we would get, what it costs, what if we didn't

- Get: a contract (the table) with an honest table-first reader, a cache
  that sees the reads that matter for OISST and BRAN, tests for the case
  the scheme actually needs (many chunks per file, several variables, a
  missing chunk), and S7 kept from inventing a seventh schema.
- Cost: one more storage implementation and fixture; pilot C1
  grows a source key, a validator column and a partitioned
  layout before it starts.
- Without it: "table first" stays a claim, the cache misses the virtual
  path it was meant for, and R users wait on a binding that vendors
  Icechunk.
