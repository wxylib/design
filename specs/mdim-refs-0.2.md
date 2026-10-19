# mdim-refs/0.2: byte-reference table

Status: draft, 2026-10-03. Merges the raad.virtualize store (`R/store.R`) and
the aad-filelist store (`inst/scheme/hardcore_sqlite_zarr/mdim_refs_sqlite.R`,
format `mdim-refs/0.1`). Column names follow the GDAL block-info draft
(`gdal mdim get-refs`, branch `feature/mdim-get-refs` on mdsumner/gdal).
Reference implementation (R store and writers, a Python block-info scanner)
is not yet public; the zaro reader is in
[hypertidy/zaro PR #5](https://github.com/hypertidy/zaro/pull/5).

Kept in wxylib/design as a reference for the flat reference table question
(doc 03, "Open topic"; doc 04, section 18.2) and the pilot in
[m02](../docs/m02-pilot-mdimrefs.md). It is not a wxylib format.

## Model

Three layers, each held once:

1. **Physical**: for each source and each array in it, the byte range of every
   chunk, keyed on the chunk's position *within the source*. This is the row
   block-info emits when run on one source file. It holds no time, no dataset
   and no remapping, so a source is scanned once and a rescan is an in-place
   upsert.
2. **Plan**: where each source's slab sits in the global array. This is the
   `<Source>` list of a `gdal mdim mosaic` VRT (SourceSlab and DestSlab),
   copied into the store so that the table stands alone outside GDAL.
3. **View**: the global chunk index, `refs_<array>`, computed from 1 and 2.
   Its rows are what block-info would emit if run on the mosaic as one array.

Every published form (kerchunk Parquet, Icechunk, a GDAL OGR layer, a zaro
store) is a projection of the view plus the `arrays` metadata.

## Tables

One SQLite file per dataset. Names `meta`, `sources`, `arrays`, `placements`,
`remap` and the prefix `refs_` are reserved.

| Table | Key | Columns |
|---|---|---|
| `meta` | `key` | `value`. Required: `format_version` = `mdim-refs/0.2`. Optional: `dataset` (bowerbird source id), `plan` (VRT URI the placements came from), `coord_attrs` |
| `sources` | `source_id` | `source` TEXT UNIQUE, `size` BIGINT, `mtime` BIGINT, `etag` TEXT |
| `arrays` | `array` | `kind` (`data`, `coord`), `storage` (`referenced`, `inline`, `affine`), `dims`, `shape`, `chunks` (JSON), `dtype` (numpy, e.g. `<i2`), `fill` (text), `codec` (JSON `{compressor, filters}`, Zarr v2 ids), `attrs` (JSON, CF), `affine` (JSON `{start, step}`), `values` (BLOB) |
| `<array>` | `(source_id, dim_0..dim_{n-1})` | `present` INTEGER, `offset` BIGINT, `size` BIGINT, `info` TEXT, `data` BLOB |
| `placements` | `(array, dest)` | `source_id`, `source_array`, `src_offset`, `count`, `dest` (JSON element offsets and counts) |
| `remap` | `(target, prefix)` | `replacement` |
| `refs_<array>` (view) | `dim_0..dim_{n-1}` | `present`, `path`, `offset`, `size`, `info`, `data` |

All chunk tables are `WITHOUT ROWID`. `shape` in `arrays` is the global shape
from the plan; `chunks`, `dtype` and `codec` describe the sources.

## Rules

- **Source rule.** `sources.source` is the URI opened at scan time, verbatim
  (`/rdsi/...`, `/vsicurl/https://...`, `/vsis3/...`). Offsets are bound to it.
  Preliminary and final versions of a granule are distinct sources; which one a
  dataset uses is decided by the plan.
- **Remap at publish.** A published path is the source with the longest
  matching `remap.prefix` for the chosen `target` replaced. Remapping is never
  written into `sources`. This replaces the three ad hoc rewrites (Parquet
  edits, `rename_paths`, `ref_prefix`).
- **Presence.** Block-info's three states: present and referenced
  (`present=1`, `offset` and `size` set), present and inline (`present=1`,
  `offset` NULL, `data` set), absent (`present=0`; readers use `fill`).
- **Byte columns are BIGINT**, so OGR and Arrow read them as 64-bit.
- **One codec per array.** All present chunks of an array carry the same
  `info`. A source whose chunks disagree (a filter skipped on some chunks)
  cannot join the array; ingest fails rather than writing a mixed array.
- **Chunk-aligned plan.** Each placement has step 1, `src_offset` and `dest`
  divisible by `chunks`, and `dest + count` divisible by `chunks` unless it
  reaches the end of the global axis. Otherwise the mosaic has no single
  regular chunk grid and cannot be virtualised.
- **Coordinates** come from the plan (`InlineValues` as `values`,
  `RegularlySpacedValues` as `affine`). Their CF attributes come from the
  source scan, because the mosaic VRT drops some (time `units` for OISST).
- **Publish in DELETE journal mode** (checkpoint, then `journal_mode=DELETE`),
  so a read-only remote copy opens without WAL sidecars.

## The view

For array `a` with chunk shape `c`, a row of `refs_a` is a row of chunk table
`a` joined to its placement, with

```
dim_i(global) = dim_i(source) - src_offset_i / c_i + dest_i / c_i
```

restricted to source chunks inside the slab, and `path` the verbatim source.
`mr_view_sql(con, a, target)` writes the same query with remapped paths. The
columns are exactly the block-info layer: `dim_0..dim_{n-1}`, `present`,
`path`, `offset`, `size`, `info`, plus `data` for inline chunks.

## Writers and readers

| Form | Route | State |
|---|---|---|
| GDAL vector (OGR) | open the SQLite file; `refs_<array>` is a layer | works with stock GDAL |
| kerchunk Parquet (D) | `mr_write_kerchunk_parquet()` -> `blocklist::write_kerchunk_parquet()` | works; read by GDAL as `ZARR:"/vsikerchunk_parquet_ref/{dir}"` |
| zaro | `zaro("mdimrefs://store.sqlite", target = "public")` | works; serves Zarr v2 keys from the view |
| Icechunk (C) | bulk-load the view rows as virtual chunk refs | not started |
| block-info producer | `blockinfo_scan.py` (stock `GetRawBlockInfo`) now; `gdal mdim get-refs` output is the same rows | Python only; no R binding of `GetRawBlockInfo` exists |

## Mapping from earlier stores

| Concept | raad.virtualize | aad-filelist 0.1 | block-info | 0.2 |
|---|---|---|---|---|
| file | `files(file_id, source)` | `sources(file_id, access, public)` | `path` per row | `sources(source_id, source, size, mtime, etag)` |
| chunk key | `file_id, idx0..` (within file) | `idx0..` (global) | `dim_0..` | `source_id, dim_0..` (within source) + view `dim_0..` (global) |
| bytes | `offset, size` INTEGER | `offset, size` INTEGER | `offset, size` Integer64 | `offset, size` BIGINT |
| per-chunk codec | none | `info` | `info` | `info` |
| inline | none | `data` BLOB | planned | `data` BLOB |
| array metadata | none (from the VRT) | `arrays` | layer metadata | `arrays`, global shape from the plan |
| placement | in the projection code | implicit in global `idx` | n/a | `placements` (from the VRT) |
| public paths | projection code | `public` column | n/a | `remap` |

## Validation (2026-10-03)

- Block-info rows from stock GDAL 3.13 `GetRawBlockInfo` on the NOAA S3 copies
  equal the v0.1 store rows for the same files: 120 of 120 rows (30 days, four
  arrays) match on offset and size, so the /rdsi mirror and S3 agree there.
- 30 days (September 1981): `gdal mdim mosaic` over `/vsicurl/` -> scan ->
  store -> kerchunk Parquet. Day 30 read through GDAL from the kerchunk store
  and through zaro from the table both equal GDAL reading the source netCDF.
- Full store: the 16,387-source v0.1 store migrated in under 10 s (14 MB). The
  `refs_sst` view returns 16,387 rows in 0.14 s; kerchunk Parquet for four
  arrays writes in 1.3 s. Days 1981-09-01, 1995-03-17, 2026-06-01 and
  2026-07-13 (preliminary) read identically through GDAL-on-kerchunk,
  zaro-on-table and GDAL-on-source.
- Not tested: bluelink (NCI THREDDS was not reachable from the build
  environment), Icechunk, multi-chunk-per-source arrays, absent and inline
  chunks against real data.

## Open questions

1. The view filters on computed columns, so a single-chunk lookup scans the
   array's rows. Fine at 16k rows; for arrays with millions of chunks the
   publish step should materialise `refs_<array>` as a keyed table.
2. Placements duplicate the VRT. The alternative is to keep the VRT as the only
   plan and compute the view in code; that loses SQL-only readers.
3. Home for `R/mdimrefs.R`: raad.virtualize (store) with the writer staying in
   blocklist, or a small package of its own.
4. **Proposed: per-axis chunk edges** (from wxylib design m10, overlapping
   COG mosaics). 0.2 assumes one regular chunk grid per array, so a mosaic
   whose winning tiles have unequal sizes cannot be virtualised. The
   proposal: an optional `chunk_edges` column in `arrays` (JSON, one list
   of cumulative edges per dimension, the Zarr `rectilinear` grid of
   zarr-extensions), with `chunks` kept as the source chunk shape; when
   present, the view's global keys index those edges instead of
   `dest_i / c_i`, and the chunk-aligned plan rule becomes "each placement
   starts and ends on an edge". Readers that do not know the column refuse
   the array rather than misread it. To be agreed here before any writer
   or reader emits it; it is not a wxylib extension.
5. **Parquet export layout.** The export (`refs_<array>.parquet` plus
   `arrays.json`) is the flat refs store that tables are harvested into and
   virtual indexes are rendered from. Its layout is not fixed: one
   self-describing Parquet file with `meta`, `arrays` and `remap` in
   key-value metadata is the likely end. The export also lacks the
   `sources` table (`source`, `size`, `mtime`, `etag`), which a cache
   needs to validate held bytes.
