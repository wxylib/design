# m15: mdim-refs/0.2 against its reference implementation and two live stores

Status: musing, 2026-10-21. Reconciles the mdim-refs/0.2 spec
([specs/mdim-refs-0.2.md](../specs/mdim-refs-0.2.md)) with the R reference
implementation (`R/mdimrefs.R` in raad.virtualize), the wxylib fixtures,
wxy-refs in core, and the two stores built with that implementation:
BRAN2023 daily temperature (1,116,900 chunks, netCDF4 over NCI THREDDS)
and GHRSST MUR analysed_sst (935,496 chunks for 2024 and 22,766,292 for
the full series, COGs on source.coop). The spec edits recommended in
section 4 are made in the same change.

**Implementation (2026-10-28):** Implemented on the wxylib side. The spec edits of section 4
are in the same change ([design #30](https://github.com/wxylib/design/pull/30)) and the fixtures use the
settled placements and info forms ([fixtures #9](https://github.com/wxylib/fixtures/pull/9)). The
implementation patch of section 5 belongs to the producer. Per-axis
chunk edges remain open in the spec.

## Summary

- The 2026-10-03 draft and the wxylib copy of the spec say the same
  thing; the wxylib copy adds open questions 4 (per-axis chunk edges) and
  5 (Parquet export layout). There is no text to merge.
- The reference implementation and both live stores agree with each
  other. The wxylib fixtures disagreed with them in two encodings, now
  fixed in the fixtures: `placements.dest` was an object
  `{offset, count}` (implementation: a plain array of element offsets),
  and `info` was a JSON list (implementation: `K=V; K=V` text).
- Open question 1 (view lookups at millions of chunks) has a cheaper
  answer than materialising the view: join from the placement to the
  chunk table, so SQLite uses the chunk table's primary key. Measured
  under 1 ms against 0.9 to 1.9 s through the view, on both stores.
- The spec needs four small additions the stores exercised: within-source
  keys carry the global rank (2D COGs in a 3D array), the `info` text
  form, the TIFF predictor in the codec mapping, and `sources` in the
  Parquet export.
- SQLite stays the working store (scan, upsert, plan); the Parquet export
  is the published middle stage that every renderer and reader should
  start from. Recommended, not decided.
- The implementation had a handful of correctness gaps, the worst being
  that a source in the plan with no scanned chunks reads as fill without
  a warning. A tested patch is with the implementation's owner.

## 1. Agreements

| Topic | Spec | Implementation | BRAN2023 | MUR | wxy-refs |
|---|---|---|---|---|---|
| Three layers (physical, plan, view) | yes | yes | yes | yes | reads the view export |
| `sources` verbatim, remap at publish | yes | yes | `/vsicurl/` sources; `public`, `gdal` targets | `public`, `s3direct`, `gdal-s3direct` | applies `remap` rows, longest prefix |
| Byte columns 64-bit | BIGINT | BIGINT | OGR reads `offset`, `size` as Integer64 (GDAL 3.12.4) | int64 in Parquet | int64 |
| One codec per array | rule | checked within one scan | one codec | one codec (ZSTD, Predictor=2) | one codec chain per array |
| Chunk-aligned plan | rule | checked in `mr_set_plan` | month files, time chunk 1 | one day per source | n/a |
| DELETE journal at publish | rule | `mr_publish` | `journal_mode` = delete | yes | n/a |
| OGR layer per view | claim | n/a | `refs_temp` opens as a layer, attribute filters work | yes | n/a |

Both stores pass a plan-against-rows check: every placement's source has
chunk rows, every global chunk has exactly one row, no key is duplicated.

## 2. Conflicts

**`placements.dest`.** The spec said "JSON element offsets and counts",
which the fixtures read as `{"offset": [...], "count": [...]}` with the
count repeated from `count`. The implementation and both stores write a
plain array of offsets, the VRT's `DestSlab offset` (a DestSlab has no
count). The implementation's view reads `$[i]`, the fixtures' view read
`$.offset[i]`, so neither could read the other's store. The plain array
wins: it is what the VRT holds and what the live stores already use.
wxy-refs reads only the export, so nothing in core changes.

**`info` encoding.** The implementation and the MUR harvest write the
block-info text form, `COMPRESSION=DEFLATE; FILTER=SHUFFLE;
ENDIANNESS=LITTLE`. The fixtures wrote osgeo.gdal's `GetInfo()` list as
JSON. The one-codec rule compares `info` values, so two producers that
agree on the codec but not the encoding would fail it. The text form
wins; readers may accept the JSON list, and the comparison should be on
the parsed pairs, not the raw string.

Both are fixed in wxylib/fixtures (script and committed files; the views
give identical rows before and after, and arrays.json is unchanged).

## 3. Points weighed

### 3.1 SQLite store or Parquet export as the middle stage

The flat refs store is meant to be the middle stage: harvest and collate
into it, render every virtual index from it. In practice the SQLite file
does the collating (upserts by source, the plan, the views) and the
Parquet export is rendered from it, as are kerchunk, the VRT and
Icechunk.

The two roles are different and both are needed:

| | SQLite store | Parquet export |
|---|---|---|
| Holds | physical rows, plan, remap, views | the view, arrays, remap, meta, sources |
| Good at | rescans, upserts, single writer, OGR | object storage, any language, row-group pruning |
| Cost at 22.8M chunks | collate 563 s; one file | 128 MB; path column must be dictionary-encoded |
| Who needs it | the producer | every renderer and reader |

Recommendation: the spec defines the logical tables once and two
encodings of them. SQLite is the working encoding, optional for a
producer that has another way to keep its physical rows. The Parquet
export is the published encoding and the interchange point: renderers
(kerchunk, Icechunk, VRT) should take the export, not the SQLite file,
so that a producer in any language (a Rust scanner, `gdal mdim
get-refs`) that writes the export can feed every renderer. What we get:
one contract for producers and consumers. What it costs: renderers in
raad.virtualize move from SQL queries to reading Parquet. If we didn't:
SQLite becomes the format, and every producer has to write it.

### 3.2 Placements JSON shape

Settled by section 2: `src_offset`, `count` and `dest` are JSON arrays of
element offsets or counts, one per global dimension. Steps are always 1
(the plan rule), so no `step` column.

### 3.3 Remap table

Works as specified on both stores, including several targets per store
and a prefix that does not match (BRAN's `gdal` target names
`/g/data/gb6/`, its sources are `/vsicurl/` URLs, so they pass through).
MUR uses remap for a second fetch route (`s3direct`) when the published
host is not reachable, which is the intended use. No change.

### 3.4 View lookups at millions of chunks (open question 1)

The view computes global keys, so `WHERE dim_0 = ... AND ...` scans every
row. Measured (SQLite, one chunk):

| Store | Chunks | Through the view | From the placement | Materialised keyed copy |
|---|---|---|---|---|
| BRAN2023, 2010 | 1,116,900 | 1.9 s | 0.2 ms | 0.2 ms, about 9 s to build |
| MUR analysed_sst, 2024 | 935,496 | 1.4 s | 0.5 ms | 0.3 ms, about 8 s to build |

"From the placement" inverts the join: find the placement whose `dest`
slab holds the global key (placements are few: 12 and 366 here, 8907 for
the full MUR series), compute the local key
`dim_i(source) = dim_i(global) - dest_i / c_i + src_offset_i / c_i`, and
look it up by the chunk table's primary key. SQLite's plan confirms both
the placement and chunk searches use primary keys. The view scan grows
with the row count (about 35 s a lookup at 22.8M chunks); this does not.

Recommendation: keep `refs_<array>` as a view; the spec documents the
placement-first lookup as the per-chunk read path. Materialisation stays
an option for SQL-only readers that filter ranges through the view.

The Parquet export has the same problem in another form: both stores
write one row group per array, so a reader cannot prune. The export
should be sorted by the dims and split into row groups along `dim_0`
(for example one row group per N time steps), so a reader that needs a
window reads a few row groups by their statistics. This is also the route
out of wxy's RefsStore holding all 22.8M refs in memory.

### 3.5 One codec per array

Holds for every dataset tried. Two gaps in how it is enforced: the
check ran within one scan only, so a later ingest with a different codec
or chunk shape silently rewrote the array's metadata under the chunks
already held; and it compared raw `info` strings (section 2). Both are
fixed in the implementation patch. The rule itself stays.

### 3.6 Codec mapping

The spec names Zarr v2 ids but not the mapping from `info`. The stores
need it written down:

| `info` | Zarr v2 | Zarr v3 (as rendered) |
|---|---|---|
| `COMPRESSION=DEFLATE` | compressor `zlib` | `numcodecs.zlib` |
| `COMPRESSION=ZSTD` | compressor `zstd` | `zstd` (core; zarrs does not read `numcodecs.zstd`) |
| `FILTER=SHUFFLE` | filter `shuffle` (elementsize = item size) | `numcodecs.shuffle` |
| `PREDICTOR=2` (TIFF) | filter `imagecodecs_delta` (axis -1, dist 1) | `HorizontalDeltaCodec` (virtual-tiff), ahead of `bytes` |
| `ENDIANNESS=LITTLE` / `BIG` | must match the dtype's byte order | `bytes` endian |

GDAL's Zarr driver reads neither predictor form, so GDAL readers of a
predicted array use the VRT view. `PREDICTOR=3` is unmapped (the m10
blocker).

### 3.7 Lower-rank sources

The MUR sources are 2D COGs placed in a 3D array by a vrtstack plan
(`SourceBand 1`, `SourceTranspose -1,0,1`). The harvest writes local keys
`(0, ty, tx)`, so the view arithmetic works unchanged. The spec did not
say this, and the implementation ignored `SourceTranspose`, so a plan
that permuted source axes would have been accepted and read wrongly. The
rule to add: within-source keys carry the global rank; a source of lower
rank has key 0 on the axes its placement adds; a placement may add
leading axes but not permute the source's own.

### 3.8 The `sources` table

Now present in the BRAN and MUR exports as `sources.parquet` (`source_id`,
`source`, `size`, `mtime`, `etag`). That closes the second half of open
question 5; the export rows still carry `path` per row rather than
`source_id`, which keeps each row a block-info row. At MUR scale `path`
must be dictionary-encoded (Arrow's 2 GB string limit); wxy-refs accepts
that.

## 4. Spec changes made

In [specs/mdim-refs-0.2.md](../specs/mdim-refs-0.2.md):

1. `placements`: `src_offset`, `count`, `dest` are JSON arrays of element
   offsets or counts per global dimension; `dest` is the DestSlab offset.
2. `info`: the block-info text form `K=V; K=V`; one-codec comparison on
   the parsed pairs; the codec mapping table of section 3.6.
3. Rank rule for lower-rank sources (section 3.7).
4. The view section: the placement-first lookup as the per-chunk path;
   open question 1 updated with the measurements.
5. Open question 5: `sources.parquet` is in the export; sorted,
   row-grouped export and dictionary-encoded `path` recommended; the
   SQLite/Parquet roles of section 3.1.

## 5. Implementation patch

Against `R/mdimrefs.R` after the GHRSST patch (which added
`PREDICTOR=2` and `SourceBand` sources). Tested on copies of both live
stores and on synthetic cases.

- A rescan replaces a source's rows instead of upserting into them, so a
  source that now has fewer chunks leaves no stale keys (opt-in on
  `mr_merge`, used by `mr_ingest_scan`, which always holds whole
  sources).
- The one-codec rule holds across ingests: an array that already holds
  chunks refuses a new chunk shape, dtype or codec.
- `info` is read in either encoding; `ENDIANNESS` is checked against the
  dtype; an `info` without `PREDICTOR` or `COMPRESSION` no longer stops
  with "subscript out of bounds".
- `mr_ingest_scan` passes the chunk shape the predictor mapping needs.
- `SourceTranspose` is kept from the plan VRT and only added leading
  axes are accepted; a slab with no count stops with a clear message.
- `mr_check()` reports placements with no chunk rows, missing global
  chunks and duplicated keys; `mr_set_plan()` warns when any is non-zero
  (before, an unscanned source read as fill silently).
- `mr_chunk()` uses the placement-first lookup.
- Coordinate bytes for 8-byte integers and large `u4` values (R's
  `writeBin` takes integers of size 1, 2 or 4 only), and a store without
  `coord_attrs` no longer fails in `mr_set_plan()`.

## 6. Open

- The SQLite/Parquet split of 3.1 and the row-grouped export of 3.4 are
  recommendations for the owner of the format.
- The home of `R/mdimrefs.R` (open question 3) is unchanged.
- Per-axis chunk edges (open question 4) are untouched by these stores;
  both are regular grids.
