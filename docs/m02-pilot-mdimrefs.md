# m02: Pilot, a byte-reference table as a wxy-virtual source

Status: musing, 2026-10-16. A small proposal in three slices, each with its
own gate. It becomes work only by being picked up into a numbered document.

**Implementation (2026-10-28):** Implemented. P1 fixture [fixtures #1](https://github.com/wxylib/fixtures/pull/1), P2 reader in
`wxy-virtual` [core #2](https://github.com/wxylib/core/pull/2), P3 real data as the OISST walk-through
[docs #3](https://github.com/wxylib/docs/pull/3). The table is now read directly by `wxy-refs` (stage S3c).

## Why this pilot

wxylib's design leaves one question open at gate 4 (design doc 03, "Open
topic"; doc 04, section 18.2): should `wxy-virtual` produce a flat table of
chunk references first (one row per chunk: key, url, offset, length), with
Icechunk as one place to write it?

A table of exactly that shape already exists and is validated:
**mdim-refs/0.2**, a byte-reference table built from a `gdal mdim mosaic`
VRT. It holds the OISST v2.1 daily archive (16,387 netCDF4 files, four
arrays) in a 14 MB SQLite file, and three readers (GDAL on its kerchunk
Parquet export, zaro on the table, GDAL on the source netCDF) already agree
byte for byte on sample days. Its spec lists Icechunk as "not started".

So one pilot answers a wxylib question and closes a gap on the table side:

- wxylib gets its first non-TIFF format, by virtualisation (principle A6),
  with GDAL acting as the scanner (A6 allows this "where nothing else
  exists") and staying the oracle.
- The table gets its Icechunk writer, in Rust, on wxylib's existing
  `write_icechunk` and `open_icechunk`.
- The "table first, Icechunk as a sink" idea is tried on real data before
  anyone designs a wxylib table format.

## The table, in one paragraph

Per dataset: `arrays` (dims, global shape, chunks, numpy dtype, fill, codec
as Zarr v2 ids, CF attrs, coordinates as affine `{start, step}` or inline
values), and a view `refs_<array>` with columns `dim_0..dim_{n-1}`,
`present`, `path`, `offset`, `size`, `info`. The view is the global chunk
index, already placed by the mosaic, so a consumer never needs the VRT.
`remap` rewrites path prefixes at publish (local mirror to `https://` or
`s3://`). Spec: [mdim-refs/0.2](../specs/mdim-refs-0.2.md) (zaro reader in
[hypertidy/zaro PR #5](https://github.com/hypertidy/zaro/pull/5)).

OISST `sst`: shape `[16387, 1, 720, 1440]`, chunks `[1, 1, 720, 1440]`,
`<i2`, fill -999, codec shuffle(2) then zlib(1). One chunk per file.

## Slices

### P1. Fixture (wxylib/fixtures, new `mdimrefs/`)

A script, in the style of `make_zarr_fixtures.py`, that:

1. writes three tiny netCDF4 files shaped like OISST (time 1, zlev 1,
   lat 36, lon 72, int16, shuffle plus deflate, one chunk each);
2. runs `gdal mdim mosaic` over them to a VRT;
3. scans the chunk byte ranges with stock GDAL (`GetRawBlockInfo`) into an
   mdim-refs/0.2 table;
4. records what GDAL reads for a few windows (`oracle/*.bin`, the same
   layout as `cog/oracle`).

Gate: the fixture is small (tens of KB) and regenerates from the script.

### P2. Reader (wxylib/core, `wxy-virtual`)

`wxy_virtual::from_refs_table(...) -> Vec<VirtualArray>`:

- codec mapping, v2 ids to Zarr v3: `bytes` (little endian),
  `numcodecs.shuffle` (elementsize from dtype), `numcodecs.zlib`. zarrs
  ships both (shuffle unconditionally, zlib behind its `zlib` feature,
  which wxy-virtual already needs for TIFF Deflate).
- affine `lat`/`lon` coordinates to GeoZarr `spatial:` attrs plus
  `proj:code` EPSG:4326, through `wxy-geozarr`; time stays a CF coordinate.
- refs rows with `present = 1` become `ChunkRef { key, url, offset,
  length }`; absent rows are left out (fill value), as the TIFF scanner
  does for sparse tiles.

Then the existing path: `write_icechunk`, `open_icechunk`, `wxy_zarr::open`.

Gate: a test `virtual_mdimrefs_matches_gdal`, shaped like the current
`virtual_cog_matches_gdal`, passes byte for byte in CI.

### P3. Real data (demo, not CI)

The 30-day September 1981 OISST table (paths remapped to the public NOAA
S3 bucket) through the same reader, read back for day 30 and compared with
GDAL on the source file. This needs an HTTP or S3 virtual chunk container
in `wxy-virtual`, which is local-file only today.

Gate: day 30 identical to GDAL. Stretch: `wxy warp` that day to EPSG:3031
(needs a 2D slice of the 4D array).

## Input format: decided (Parquet, 2026-10-16)

The table is SQLite today. For P2 the Rust side reads (a); (b) was the
alternative considered:

- **(a) Parquet export of the view plus a small `arrays.json`**
  (chosen). Pure Rust (arrow/parquet), wasm friendly, and it is itself
  the flat table gate 4 asks about.
- (b) the SQLite file directly through `rusqlite` (bundled C SQLite). Reads
  the spec form as is, but adds a C dependency.

## Out of scope

Bluelink and other multi-chunk-per-source arrays, a wxylib table format,
kerchunk export, and R or Python bindings (wxylib stage S6).

## What it does not do

It does not serve R users yet: wxylib has no R package until S6. The table
side is R today (the R scripts that build it, and zaro), so R users already
read the same table; this pilot gives that table a second, Rust, consumer.

## Open questions for wxylib

1. Accept a GDAL-backed scanner (block-info from stock GDAL) for netCDF4 in
   fixtures, before a Rust netCDF scanner (roteiro-gis hdf5-reader) exists?
2. Should P2 land in `wxy-virtual`, or in a separate crate for table
   sources?
