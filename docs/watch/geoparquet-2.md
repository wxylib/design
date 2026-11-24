# Watch: GeoParquet 2.0

Status: tracking note, 2026-11-24, for GeoParquet v2.0.0 (released
2026-11-24). Checked at the monthly landscape refresh.
Source: the release post
[GeoParquet 2.0 Released](https://cloudnativegeo.org/blog/2026/11/geoparquet-2-0-released/)
(Cloud-Native Geospatial Forum, 2026-11-24) and the specification at the
[v2.0.0 tag](https://github.com/opengeospatial/geoparquet/releases/tag/v2.0.0):
`format-specs/geoparquet.md`, `compatible-parquet.md`,
`distributing-geoparquet.md` and `parquet-raster.md`.
Context: [04 landscape](../04-landscape.md) section 10.1 (R6 storage),
[m17](../m17-self-describing-stores.md) (store description contract),
[m32](../m32-byterefs-position.md) (byterefs position),
[m16](../m16-versioned-byte-ref-table.md) (versioned refs),
[m27](../m27-oracle-harness.md) (oracle harness),
[vrtmate.md](vrtmate.md) (footprint index), web `www/vector.html` and
`www/vrt-vector.html`.

## 1. Summary

1. **2.0 moves the meaning into the base format and shrinks the
   convention to a helper.** The geometry column is the native Parquet
   `GEOMETRY` or `GEOGRAPHY` logical type (Parquet 2.11, March 2025). The
   CRS travels on the column and per-row-group bounding boxes come from
   Parquet's own geospatial statistics. The `geo` footer metadata stays
   for what core Parquet cannot say: a guaranteed inline PROJJSON CRS,
   polygon winding order, coordinate epoch, and the primary column when
   there are several.
2. **A file without the convention is still first-class input.** Every
   2.0 reader must read a Parquet file that has the native types and no
   `geo` metadata. A writer that cannot produce PROJJSON is told to write
   the native types with an `AUTH:CODE` CRS and leave `geo` out.
3. **The CRS rule is liberal for readers and strict for writers.** The
   Parquet `crs` property may be inline PROJJSON, `AUTH:CODE`,
   `srid:<n>` or `projjson:<key>`. Readers must take the first two and
   should try the others. Writers should use only the first two. Absent
   means OGC:CRS84. Unknown is explicit: `srid:0` on the column, `crs:
   null` in `geo`. The two must never describe different CRSs.
4. **A redundant column was removed and then restored as optional.** The
   `bbox` covering column became unnecessary for row-group pruning, but
   it came back because only an ordinary column gets a page index, so
   only it prunes pages inside a row group. GeoArrow native encodings were
   dropped for lack of use; GeoArrow stays the in-memory form.
5. **The release ships more than a spec.** It comes with a publishing
   guide beside the spec (zstd at level 15 or more, spatial order, row
   groups of 50,000 to 150,000 rows, spatial partitions past about 2 GB,
   STAC), an official test corpus, and a validator. The validator is a
   command-line tool compiled to wasm that reads a URL by range requests,
   has Rust, Python, npm and C builds, and reports conformance classes
   (Core, Cloud-Optimized Distribution).
6. **Defaults lag on purpose.** Readers are broad (GDAL 3.12, DuckDB 1.5,
   Arrow 21, GeoPandas 1.2, Spark 4.2, SedonaDB 0.4, hyparquet 1.19, QGIS
   4.2), but no writer emits 2.0 by default yet. 1.1 with a `bbox`
   covering stays the choice for the widest audience, and Overture still
   publishes it. `GEOGRAPHY` lags `GEOMETRY` everywhere.

## 2. What it means for byte-reference tables

The byte-reference table (byterefs/0.1, mdim-refs/0.2) has the same
shape of problem: a convention over a base format that already carries
part of the meaning. GeoParquet's answer gives five concrete rules.

| GeoParquet 2.0 | Byte-reference table |
|---|---|
| Native type carries the meaning; `geo` is a helper | Where Zarr v3 or Icechunk can carry chunk references, the table adds only what they cannot: remap, (source, etag) identity, placements |
| A file without `geo` is first-class input | `wxy-refs` reads a bare chunk table or a kerchunk Parquet with no byterefs metadata and infers what it can, saying what it inferred |
| Readers liberal, writers PROJJSON or `AUTH:CODE` | The same rule for the table's CRS statement, with CF `grid_mapping` as one more accepted reader form |
| Unknown CRS is explicit (`srid:0`, `crs: null`) | Replace the EPSG:4326 fallback with an explicit unknown; absent stays a reader default only where the spec names one |
| Publishing guide beside the spec | A "publishing byte-reference tables" guide: sort by array then chunk key, dictionary-encode paths, row-group size, split by the append unit ([m16](../m16-versioned-byte-ref-table.md) Icechunk finding), carry the etag |
| Test corpus and a wasm validator with conformance classes | `scripts/m17_contract.py` and the oracle harness are the seed of a validator; Core (rows and schema) and Distribution (sort, row groups, remap) classes |
| 1.x stays readable for years | Keep reading `mdim-refs/0.2` beside `byterefs/0.1`, as core already does; do not tag before two producers write it |

## 3. Footprints as native geometry

A sources table that carries each source's footprint as a native
`GEOMETRY` column gets spatial pruning from DuckDB, GDAL and SedonaDB
with no index of its own. This is the job VRTMate does over a classic
VRT ([vrtmate.md](vrtmate.md)) and the job `vrt-model` should answer
from a world box. Footprints in a non-geographic CRS keep their CRS on
the column. Spatial order and row-group size then follow the GeoParquet
publishing guide rather than a rule of our own.

## 4. Parquet Raster (alpha)

The repository also carries `parquet-raster.md`, marked alpha. A raster
column is a struct of affine parameters, size, optional CRS and bands,
with a required companion `GEOMETRY` or `GEOGRAPHY` column for the
footprint. Bands are in-db (pixels in the row, PostGIS WKB-raster style)
or out-db (a band number and a `file`, `http` or `https` URL).

- Out-db references name a whole file and band, not byte ranges. A
  byte-reference table is the finer level under it, so the two compose:
  an out-db row could point at a virtual store rather than a GeoTIFF.
- The affine origin `ip_x`, `ip_y` is the **centre** of the upper-left
  cell, unlike the GDAL geotransform's corner. Any reader or writer
  wxylib offers must convert by half a cell. This is the first thing to
  check in an implementation.
- Only affine georeferencing is allowed, so curvilinear and rotated
  grids beyond skew are out of scope, where they are core to wxylib
  (R2 and up).
- Related: DuckDB `raquet` (section 10.1 of doc 04). No action now.

## 5. Parquet edges

The Parquet `edges` values are `planar`, `spherical`, `vincenty`,
`thomas`, `andoyer` and `karney`. There is no rhumb line. A loxodrome
drawn in the editing canvas must be densified before it is written as
`GEOGRAPHY`, and a `GEOMETRY` export of geodesic edges is only exact if
densified too.

## 6. Done and next

| Item | State |
|---|---|
| web `vrt-vector.html` (`ogrvrt.js`): geometry column found from the native type when there is no `geo` metadata; Parquet CRS rules (absent, `srid:0`, `projjson:<key>`); `crs: null` in `geo` read as unknown, as GDAL does; test file `countries-native.parquet` | done (web PR) |
| web `vector.html`: file-set bboxes from native geospatial statistics (`parquet_metadata` `geo_bbox`, DuckDB 1.4.3) when a file has no `geo` metadata | done (web PR) |
| The compatibility fallback (a `geometry` or `geography` WKB column with no type and no metadata) in `ogrvrt.js` | not done; `vector.html` already decodes a WKB column named `geometry` |
| byterefs rules in section 2 | input for the implementers' meeting, not decisions |
| Footprint column on the sources table (section 3) | proposed |
| Validator from `m17_contract.py` and the oracle harness | proposed |

## 7. Not verified

- The release post and the validator page could not be fetched from this
  environment; the post was read from its source, and the specification
  from the v2.0.0 tag.
- DuckDB-wasm 1.32.0 is assumed to load the same parquet extension as
  DuckDB 1.4.3 (its binary names v1.4.3); the `geo_bbox` query was run
  in DuckDB 1.4.3 for Python, not in the browser.
- No 2.0 file from another writer (GDAL, DuckDB 1.5, GeoPandas) was
  tested; the native test file was written by pyarrow 26 with
  geoarrow-pyarrow.
