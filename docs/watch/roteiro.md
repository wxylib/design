# Watch: pure-Rust format crates from roteiro-gis

Status: assessment and living tracking note, started 2026-10-31. Checked
at the monthly landscape refresh (doc 04 section 15, row 9), not more
often. Newest entry first in section 7.
Context: [04 landscape](../04-landscape.md) sections 5.2 (CRS), 6.1
(codecs), 6.2 (TIFF), 6.5 (HDF5, NetCDF, GRIB);
[m08](../m08-point-clouds.md) (point clouds);
[m23](../m23-byte-ref-harvesting.md) (byte-ref harvesting);
[crs-coverage.md](crs-coverage.md).

## 1. Summary

[roteiro-gis](https://github.com/roteiro-gis) publishes one pure-Rust
workspace per format: TIFF and GeoTIFF, HDF5 and NetCDF, GRIB, LERC, COPC,
plus a CRS library, and two small grid-algorithm crates. Every format
workspace has the same shape (a `-core` model crate, a `-reader` and a
`-writer`), no C libraries or build scripts in the default build, fuzz
targets, and a CI job that checks parity against the reference C library
for that format. They are the most complete pure-Rust format readers and
writers found in the doc 04 survey, and they now carry real downstream use
(hdf5-reader about 50k downloads; terrio reads NetCDF and HDF5 through
them).

They are a parallel stack to wxylib's spine, not a part of it. The I/O is
synchronous behind a small byte-source trait, remote access (where it
exists) is reqwest, not `object_store`, and none of them uses async-tiff,
zarrs or Icechunk. So the right use is selective: take the pieces nobody
else has, use the readers as independent oracles, and keep async-tiff,
zarrs and async-hdf5 as the engines.

Ranked pickups, each small and reversible:

1. **`lerc-reader` as a zarrs codec.** The missing LERC decoder for
   virtual COG references (m23 section 4 lists LERC as needing a codec).
   Pure Rust, checked against libLerc.
2. **`hdf5-reader` and `netcdf-reader` as oracles in refharvest.** A third
   independent HDF5 parser next to async-hdf5 and hdf5-pure, and a
   netCDF classic header parser for the netCDF-3 step in m23's order.
3. **`proj-core` 0.12.1 as a column in crs-coverage.md.** Its strength is
   EPSG-registry operation selection (datum steps), where proj4rs fails.
4. **`geotiff-writer` as the COG writer candidate** for doc 01 M12, ahead
   of image-rs `tiff`.
5. **`copc-reader`'s range reader** as the first COPC reader for m08's
   "COPC is already virtual" rung.

## 2. What it is

| Repo | Crates (crates.io, 2026-10-31) | What | Oracle in CI |
|---|---|---|---|
| [geotiff-rust](https://github.com/roteiro-gis/geotiff-rust) | tiff-core, tiff-reader, tiff-writer, geotiff-core, geotiff-reader, geotiff-writer 0.10.0 | TIFF/BigTIFF and GeoTIFF/COG read and write. Deflate, LZW, PackBits, LERC (+DEFLATE, +ZSTD), JPEG, ZSTD, WebP decode; predictors 2 and 3. COG writer with overviews, GDAL ghost-area metadata, tile streaming; writer builds for wasm32. Optional HTTP COG reads, blocking or Tokio | GDAL and libtiff |
| [netcdf-rust](https://github.com/roteiro-gis/netcdf-rust) | hdf5-core, hdf5-reader, hdf5-writer, netcdf-core, netcdf-reader, netcdf-writer 0.12.0 | HDF5 and NetCDF (CDF-1/2/5, NetCDF-4) read and write. All chunk index kinds; deflate, shuffle, fletcher32, lz4, nbit, scaleoffset, szip on read. CF unpack, mask, calendars. No HDF5 virtual datasets | libhdf5 (h5py), netcdf-c (netCDF4-python) |
| [proj-rust](https://github.com/roteiro-gis/proj-rust) | proj-core, proj-wkt, proj-epsg-format 0.12.1 | CRS definitions, operation selection from an embedded EPSG registry generated from `proj.db` (about 1.1 MB), datum shifts (Helmert, NTv2, GTX, PROJ-format GeoTIFF grids), 17 projection methods. `proj-wkt` reads EPSG, WKT1, WKT2, PROJJSON and PROJ strings, and writes WKT and PROJJSON. wasm32 check in CI | C PROJ (bundled, dev only) |
| [grib-rust](https://github.com/roteiro-gis/grib-rust) | grib-core, grib-reader, grib-writer 0.7.0 (+ grib-aec) | GRIB1 and GRIB2 read and write; simple, complex, IEEE packing; JPEG 2000 (OpenJPEG) and CCSDS (libaec) behind features | ecCodes |
| [lerc-rust](https://github.com/roteiro-gis/lerc-rust) | lerc-core, lerc-reader, lerc-writer 0.5.2 | Lerc1 and Lerc2 decode, Lerc2 encode, with a GDAL profile that reproduces GDAL's blobs | libLerc |
| [copc-rust](https://github.com/roteiro-gis/copc-rust) | copc-core, copc-reader, copc-writer 0.9.0 | COPC read (hierarchy walk, LOD and bounds queries, column batches, a lazy range-request reader with coalesced reads) and write (LOD distribution, LAS/LAZ intake) | none listed |
| [terrand](https://github.com/roteiro-gis/terrand) | terrand-rs 0.1 | Slope, aspect, hillshade, curvature, roughness, D8 hydrology, viewshed, marching-squares contours on `ndarray::Array2` | none |
| [eikonal](https://github.com/roteiro-gis/eikonal) | eikonal 0.1.0 | Fast marching and grid shortest paths (cost distance) | none |
| [geo-crdt](https://github.com/roteiro-gis/geo-crdt) | Go | CRDTs for collaborative GeoJSON editing; vertices addressed by stable IDs, not indices | n/a |
| roteiro-agent, roteiro-sdk | Go; TypeScript and Python | MCP server and SDKs for the Roteiro WebGIS platform's API. The platform itself is not public | n/a |

All Rust crates are MIT or Apache-2.0.

## 3. Maturity

- **People.** One main author, Ian Norden, writes 93 to 99 percent of
  the commits in every repo; a few outside contributors appear in
  geotiff-rust, netcdf-rust, proj-rust and lerc-rust. The org lists no
  public members. The crates appear to be the foundation layer under the
  Roteiro WebGIS platform. Some netcdf-rust commits (31 of 483) carry an
  agent co-author trailer; the other repos have few or none.
- **Age and pace.** All started in March to May 2026. In October 2026:
  119 commits to netcdf-rust, 47 to geotiff-rust, 15 to 19 to proj, GRIB
  and LERC. Every repo works through PRs and tagged releases, minor
  versions about monthly.
- **Testing.** Fuzz targets per reader, property tests, bounded parsing
  of untrusted input, and parity jobs against the C library of each
  format (table above). This is the same "C library as oracle" stance as
  wxylib's GDAL oracle.
- **Use.** crates.io downloads (all time): hdf5-reader 50.6k,
  netcdf-reader 41.8k, lerc-core 39.2k, tiff-core 29.1k, proj-core 8.5k,
  copc-core 6.3k, grib-reader 2.0k. Reverse dependencies include terrio
  (hdf5-reader, netcdf-reader, lerc-reader), earthsciio,
  ras-commander-fast-hdf, opentopography_api and omap.
- **Risk.** A single author is the bus factor for all of it. The pinned
  versions and the format-per-workspace split make that risk easy to
  contain: each crate can be dropped or replaced on its own.

## 4. Overlap with wxylib

| wxylib piece | wxylib choice | roteiro-gis piece | Relation |
|---|---|---|---|
| COG and TIFF reading (S2, `wxy-tiff`) | async-tiff + wxy-predictor | tiff-reader, geotiff-reader | Parallel. Sync with a `TiffSource` trait; HTTP through reqwest. **Keep async-tiff** |
| GeoTIFF georeferencing (doc 04 G1) | geotiff-core proposed for GeoKeys | geotiff-core 0.10.0 | Unchanged since doc 04: GeoKeys, `GeoTransform`, EPSG-centric `CrsInfo`; still no PROJJSON for user-defined CRSs |
| TIFF and COG writing (doc 01 M12) | image-rs `tiff` candidate | tiff-writer, geotiff-writer `CogBuilder` | **Stronger candidate**: COG layout, overviews, LERC and ZSTD, tile streaming, wasm |
| Codecs (doc 01 M7, zarrs codec plugins) | zarrs codecs; LERC open | lerc-reader, lerc-writer | **Fills the gap** |
| HDF5 harvest (m23, refharvest) | async-hdf5 + level-parallel walk; hdf5-pure as second oracle | hdf5-reader | Third independent parser. Public `chunk_index::ChunkEntry { address, size, filter_mask, offsets }`, `RangeRequestStorage` takes a callback |
| netCDF classic harvest (m23 step 5) | netcdf3 or netcdf-reader | netcdf-reader | Candidate header parser |
| GRIB harvest (m23, doc 04 6.5) | gribberish | grib-reader | `MessageMetadata` has public `message_offset` and `message_length`. Reads the whole file (path, bytes or `Read`), no range source. Its decoders could back a GRIB codec |
| CRS backend (doc 04 5.2, crs-coverage.md) | proj4rs in core; terrio-crs measured | proj-core, proj-wkt | Candidate, see section 5 |
| Point clouds (m08) | laz-rs via laspy in figures; no reader in core | copc-reader `CopcRangeReader` | **Candidate**: range-first COPC with lazy hierarchy pages, which is m08's model |
| Raster algorithms (doc 01 M20, deferred) | none | terrand, eikonal | Watch. No I/O, ndarray in and out, the same no-I/O shape as m20's movement layer |
| Editing canvas (m18) | own design | geo-crdt (Go) | Design reference only: stable vertex IDs for edits that merge |

## 5. proj-core against wxylib's CRS cases

Not measured here; this section is read from the 0.12.1 source and
README. The rust-proj-capability score in doc 04 (33 of 93) is for an
earlier version.

- **EPSG side.** Polar stereographic (3031, 3412, 3413, 3976), Australian
  Albers and Lambert, UTM, Web Mercator, LAEA (including 6931/6932),
  Equal Earth, Azimuthal Equidistant and Krovak resolve from the
  registry. Operation selection comes from the EPSG registry, so a datum
  step such as GDA94 to GDA2020 should take PROJ's operation, not a hub
  through WGS84.
- **PROJ strings.** 13 families are parsed: longlat, cart/geocent, utm,
  tmerc, merc, stere, sterea, lcc, aea, eqc, laea, omerc, cass. These are
  refused: ortho, sinu, moll, robin, eqearth (EPSG only), igh, gnom,
  tpers, nsper, geos, ob_tran, and aeqd (EPSG only). That is about 14 of
  the 35 crs-coverage.md cases, so proj-core would not replace terrio-crs
  or proj4rs 0.3 for the PROJ-string side.
- **Forms.** WKT1, WKT2 and PROJJSON in, WKT and PROJJSON out. Custom
  definitions must fit its CRS model (lon/lat order, Greenwich, one linear
  unit).

Next step: add `proj-core 0.12.1` as a column in crs-coverage.md with the
same script and oracle, which settles this section with numbers.

## 6. What to leverage, and what not

**Leverage (each one a small, separate step):**

1. **LERC codec.** Wrap `lerc-reader` as a zarrs codec (a
   `zarrs_codec` plugin, or next to wxy-predictor in core). It lets
   virtual references to LERC COGs (common in Esri-produced elevation)
   decode through zarrs, and the libLerc parity job in lerc-rust already
   covers correctness. Cost: one small crate and one fixture.
2. **Oracles for refharvest.** Add hdf5-reader's `ChunkEntry` listing as a
   third parser in m23's comparison (BRAN, OISST), and netcdf-reader as
   the netCDF classic header parser. Cost: a dev-dependency.
3. **CRS coverage column.** Section 5's next step. Cost: one run.
4. **COG writer.** When a wxylib command first needs to write a COG (doc
   01 M12; today `wxy warp` writes GeoZarr), start from `geotiff-writer`.
5. **COPC reads.** When m08's point-cloud rung gets code, start from
   `copc-reader`'s range reader behind wxylib's byte source.

**Do not:**

- Switch the COG engine from async-tiff, or HDF5 harvesting from
  async-hdf5. The roteiro readers are sync and do not speak
  `object_store`; changing engines would split the I/O layer.
- Adopt geotiff-reader's HTTP COG path. It duplicates `object_store` with
  its own reqwest client and retry logic.
- Take terrand or eikonal into wxylib's scope now. Raster algorithms are
  deferred (M20).

**Upstream conversations worth offering** (Michael decides whether and
when):

- An `object_store`-backed implementation of `TiffSource` and HDF5
  `Storage`, or an async variant of the source traits. This is the one
  change that would let the roteiro readers sit on wxylib's spine.
- A range-backed source for grib-reader, matching hdf5-reader's
  `RangeRequestStorage`.
- PROJJSON output for user-defined GeoTIFF CRSs in geotiff-core (doc 04
  G1).

## 7. Log

### 2026-10-31

First assessment. All 11 public repos read at their main branches:
geotiff-rust 0.10.0 (released today; doc 04 had 0.8.1), netcdf-rust
0.12.0 (doc 04 had 0.9.1, m23 had 0.10.1), proj-rust 0.12.1, grib-rust
0.7.0, lerc-rust 0.5.2, copc-rust 0.9.0. New to wxylib's notes: lerc-rust,
copc-rust's range reader, grib-reader's public message offsets, terrand,
eikonal, geo-crdt, and the Roteiro platform context.
