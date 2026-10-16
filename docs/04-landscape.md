# 04: The landscape: related work, what to leverage, what to track

Status: gate 4 passed 2026-10-16 (decisions in section 18)
Builds on: [01 module survey](01-module-survey.md), [02 data model](02-data-model.md),
[03 architecture](03-architecture.md) and their gate decisions.
Checked: crate, PyPI, npm and CRAN versions were read from the registries on
2026-10-16. Code claims come from read-only shallow clones. GitHub issue
search was not available, so roadmap claims rest on READMEs, changelogs,
release notes, blog posts, mailing lists and talk listings. Anything not
confirmed from a primary source is marked *(unverified)*.

## 1. Why a landscape survey

wxylib's principles say: lean on existing crates and adjacent efforts, stay
small, and give every decision a rationale. That needs a map of who else is
building what. This document is that map, for two readers:

- **others**, who want to know where wxylib sits among GDAL, the Python
  datacube stack, the Zarr and GeoZarr work, and the new Rust projects;
- **us**, to find pieces we can adopt or contribute to instead of building,
  and the efforts we must stay compatible with.

It is organised by the module layers of doc 01, after two sections on the
organisations that matter most (Earthmover and Development Seed) and the
overall shape of the field.

### Verdicts

| Verdict | Meaning |
|---------|---------|
| **adopt** | depend on it (perhaps behind a trait) |
| **contribute** | it is the right home for something we need; send work upstream |
| **align** | stay compatible with its model, vocabulary or outputs; do not depend on it |
| **watch** | relevant, but too early, too unclear, or overlapping; check again at each gate |
| **avoid** | do not depend on it or copy its approach |

## 2. The shape of the field in October 2026

Five findings frame everything below.

**L1. A Rust I/O spine already exists, and the Python stack is moving onto
it.** `object_store` (bytes), `async-tiff` (COG), `zarrs` (Zarr) and
`icechunk` (versioned and virtual Zarr) are maintained by different groups
but share one store abstraction. Development Seed's `obstore` and `zarrista`
put Python on the same crates, and zarrista is prototyping a zarrs backend
for zarr-python (zarr-python PR #4064). wxylib chose this spine in doc 01
(D3, D4). The landscape confirms it: building on these crates puts wxylib
inside the mainstream, not beside it.

**L2. GeoZarr became a set of small conventions, and GDAL already speaks
them.** The OGC GeoZarr SWG now builds composable `zarr-conventions`:
`spatial:` (affine transform, registration, bbox), `proj:` (code, WKT2,
PROJJSON), `multiscales`, `dggs`, and a `cf` registration. GDAL 3.13
(2026-05-08) reads and writes `spatial:` and `proj:`. ESA's EOPF Sentinel
Zarr products use the same conventions. This matches doc 02's separation of
mapping, frame and storage closely, and it leaves room for wxylib's R2 and
R3 work: the `spatial:` convention lists "lookup", "rpc" and "polynomial"
transform types as future work.

**L3. Virtualisation is how the field reaches legacy formats.** VirtualiZarr
2.8 (2026-10-14) has parsers for HDF5/NetCDF4, NetCDF3, HDF4, FITS, DMR++,
GRIB (through the Rust `gribberish`) and TIFF (through `virtual-tiff`, which
sits on async-tiff). Icechunk is the de facto manifest store, and its Rust
API writes virtual references. Doc 03's A6 ("formats arrive by
virtualisation first") is the same bet the rest of the field has made. The
gap is that every scanner is Python. A Rust scanner set is open territory.

**L4. Browser reprojection has converged on adaptive meshes.** deck.gl-raster
(`@developmentseed/raster-reproject`), CarbonPlan/dynamical.org's zarr-layer
and OpenLayers all reproject rasters on the GPU or CPU by building an
error-bounded triangle mesh in the target CRS. That is the same idea as GDAL's
approximate transformer, which rwarp implements. rwarp-wasm's niche is exact,
GDAL-identical warping. A shared mesh contract with these libraries would let
each use the other.

**L5. The pure-Rust "GDAL replacement" projects show what not to do.**
OxiGDAL/OxiGeo, terrio and the Whitebox Next Gen crates each wrote their own
Zarr, S3 access, TIFF and CRS engine. None of them reuses zarrs,
object_store, async-tiff or the proj crates. Their bug histories sit in
exactly those reimplemented areas (section 11). terrio, though, has the best
idea in that group: a generated, public conformance table against GDAL and
PROJ.

## 3. Earthmover

Earthmover (earthmover.io, github.com/earth-mover) is the commercial home of
much of the xarray, Zarr and Pangeo leadership. It raised a seed round in
September 2025. In June 2026 the US National Weather Service adopted
Icechunk (through Booz Allen, on NWS CIRRUS).

| Project | Lang | State (2026-10-16) | What it is | Verdict |
|---------|------|--------------------|------------|---------|
| [icechunk](https://github.com/earth-mover/icechunk) | Rust core, Python, JS | 2.3.0, 2026-10-06 | Transactional, versioned Zarr store. Spec v2 (2.0.0, 2026-04-08) adds rectilinear grids and named virtual chunk containers (`vcc://`). icechunk-js reads HTTP virtual chunks in the browser (2.2.1). | **adopt** as the virtual-reference store, for both reading and writing |
| VirtualiZarr (co-led) | Python | 2.8.0, 2026-10-14 | Parsers from legacy formats to manifests, written to Icechunk or kerchunk | **align**: its parser contract defines what our scanners emit |
| [xpublish-tiles](https://github.com/xpublish-community) | Python | 0.11.2, 2026-10-12 | Open-source tile engine behind Flux. Handles regular, curvilinear, triangular, HEALPix and polar grids; XYZ, WMTS, OGC Tiles, WMS, EDR | **align, contribute**: a compiled window and warp kernel is what its pyproj and Datashader path approximates |
| Arraylake, Flux | proprietary | active | Hosted Zarr platform and API layer. arraylake-rs 0.15.1 is a Rust client | **watch** |
| Zax | proprietary *(unverified)* | announced 2026-09-15 | Tensor-native compute with SQL and openEO front ends (beta) | **watch**: it may set user expectations for querying datacubes |
| zarr-python, xarray stewardship | Python | zarr-python 3.4.1 | Earthmover staff lead or co-lead both | **align** |

What matters for wxylib:

- Icechunk is Earthmover's main Rust asset, and its Rust API is complete
  enough to write virtual references directly (section 6.3).
- zarrs reads Icechunk repositories through `zarrs_icechunk` 0.6.0
  (2026-10-09). The ecosystem doc says this includes virtual datacubes
  created by VirtualiZarr.
- Earthmover's writing ("I/O-maxing tensors", 2025-11; "Science data comes
  in tables and tensors", 2026-09; "Icechunk vs Iceberg", 2026-10) is the
  clearest statement of where the Python datacube world is heading. It is
  worth reading at each gate.

## 4. Development Seed

Development Seed (developmentseed.org) builds most of the cloud-native
Rust-with-Python infrastructure. Kyle Barron leads the Rust, Arrow and async
I/O work. Vincent Sarago leads the titiler family *(unverified)*. With EOX,
they also run ESA's EOPF Zarr Explorer.

| Project | Lang | State | What it is | Verdict |
|---------|------|-------|------------|---------|
| [async-tiff](https://github.com/developmentseed/async-tiff) | Rust, Python | Rust 0.4.0, 2026-09-18 | Async TIFF/COG reader over object_store. Fetch and decode are separate. 0.3.0 exposed internal tile byte ranges (#261) | **adopt, contribute** |
| [async-geotiff](https://github.com/developmentseed/async-geotiff) | Python on async-tiff | 0.5.1, 2026-05-18 | GeoTIFF georeferencing, overviews, windows, TMS. All the georeferencing is in Python (`_crs.py`, `_transform.py`) | **align**: the reference to port into Rust (section 6.2) |
| [obstore](https://github.com/developmentseed/obstore), pyo3-object_store | Python, Rust | 0.12.0, 0.13.0, 2026-10-15 | Python bindings to object_store, and a crate that lets any pyo3 extension accept those stores | **adopt** in `wxy-py` |
| [zarrista](https://github.com/developmentseed/zarrista) | Rust, Python | 0.1.0, 2026-08-13 | Low-level Python Zarr on zarrs, with Davis Bennett. Aims to become a zarr-python backend | **align**: the model for our Python bindings |
| [geoarrow-rs](https://github.com/geoarrow/geoarrow-rs) | Rust, Python, JS | crates 0.9.0, 2026-09-11 | GeoArrow arrays, IO and algorithms | **adopt** for R6 (doc 02 gate default) |
| pyo3-arrow, arro3 | Rust, Python | 0.20.0, 0.9.1 | Zero-copy Arrow across pyo3 without pyarrow | **adopt** for tabular outputs |
| [deck.gl-raster](https://github.com/developmentseed/deck.gl-raster) | TypeScript | 0.8.1, 2026-09-23 | Client-side COG and Zarr rendering with adaptive-mesh GPU reprojection. Includes `raster-reproject`, `geozarr`, TS ports of `affine` and `morecantile`, and a compact EPSG database | **align, contribute**: shared mesh contract with rwarp (section 8) |
| lonboard | Python, TS | 0.17.0, 2026-10-01 | Jupyter maps on deck.gl. COG raster via async-geotiff since 0.16 | **align**: the notebook front end for `wxy-py` |
| titiler, rio-tiler, morecantile | Python (GDAL) | titiler-core 2.4.0; rio-tiler 9.4.12; morecantile 7.1.0 | Dynamic tiling. morecantile is the reference TileMatrixSet implementation | **align**. Use morecantile's TMS as the tiling model, and offer a non-GDAL reader to rio-tiler later |
| [rustac](https://github.com/stac-utils/rustac) (stac-utils, with DevSeed staff) | Rust, Python | stac 0.17.6, rustac 0.2.16 | STAC I/O, validation, stac-geoparquet, DuckDB search | **adopt** for catalogue-driven mosaics (M23) |
| [virtual-tiff](https://github.com/virtual-zarr/virtual-tiff) (Max Jones) | Python on async-tiff | 0.5.0, 2026-04-29 | VirtualiZarr parser from TIFF to virtual Zarr | **align**: our Rust TIFF scanner should emit the same references |
| geozarr-examples, EOPF Explorer, titiler-eopf | mixed | active | GeoZarr reference data and services for Sentinel | **adopt** as test fixtures |
| datacube-guide | docs | active | DevSeed's curated map of datacube visualisation and tiling | **watch**, as a second landscape |

What matters for wxylib:

- DevSeed's pattern is the one wxylib already follows. The core is in Rust
  on object_store, and Python sits on top through pyo3, obstore and
  pyo3-arrow. The Python layer then plugs into existing tools such as
  xarray, rio-tiler and lonboard. We should copy the workspace layout of
  geoarrow-rs and obstore (core crates, then `python/` and `js/` crates).
- DevSeed has no Rust georeferencing layer and does not plan one. The
  georust/geotiff issue #13 records "CRS handling in Rust later". wxylib
  can fill that gap and offer it upstream (section 6.2).
- Talks to follow: Kyle Barron at FOSS4G 2026 on browser reprojection and on
  deck.gl-raster (both 2026-09-01), and Alex Mandel at FOSS4G NA 2026 on
  virtual Zarr and GeoZarr (2026-11-03).

## 5. Layer 0: grids, CRS, tiling

### 5.1 Grid and index models

| Item | Lang | State | Relation | Verdict |
|------|------|-------|----------|---------|
| vaster / vaster-rs (hypertidy) | R, Rust | vaster 0.2.0 crate, 0.6.0 CRAN | Our grid arithmetic (doc 03) | **adopt** |
| [rasterix](https://rasterix.readthedocs.io) | Python | 0.2.4, 2026-10-06 | Lazy affine `RasterIndex` for xarray: R1 as an index | **align**. The natural place for a `wxy-py` xarray hook |
| odc-geo | Python | 0.5.3, 2026-07 | `GeoBox` (affine plus CRS plus shape), the most mature Python R1 model | **align**. `wxy-py` should accept and return GeoBox-compatible values |
| xproj | Python | 0.2.1, 2025-07 | CRS-aware xarray index | **align** |
| pyresample 2.0 roadmap | Python | 1.35.0 | Plans resampler classes with a registry, a precompute/compute split with caches, and a separate index API | **align**. It is the same plan/compute split as rwarp |

### 5.2 CRS and geodesy

The CRS backend decision belongs to
[rust-proj-capability](https://github.com/mdsumner/rust-proj-capability)
(doc 01, D5). Its current scores for exact matches against PROJ 9.9.0 on 93
fixtures:

| Crate | Exact / 93 | Notes |
|-------|-----------|-------|
| `proj` | 86 | Bindings to libproj; C++ build; no wasm |
| `proj-core` | 33 | Pure Rust, wasm, embedded EPSG, NTv2 and GTX grids. Matches PROJ's operation choice on EPSG-coded datum shifts. No custom CRS |
| `wbprojection` | 32 | Whitebox; towgs84 Helmert sign wrong |
| `proj4rs` | 20 (46 with bound strings) | Exact for what it implements; wasm with default features off |
| `crs-definitions` | 19 / 38 applicable | |
| `geodesy` | 9 | See below |
| `miniproj` | 8 | Same datum only |

Two further groups matter as much as the scores:

- **Rust Geodesy** ([busstoptaktik/geodesy](https://github.com/busstoptaktik/geodesy),
  `geodesy` 0.15.0, 2026-03-03, Thomas Knudsen). It is an experimental
  platform, not a PROJ port. Its aims are geodetic experiments, extensible
  operator pipelines and other data-flow models for transformations. Its
  low exact-match score reflects its smaller set of projections, not its
  design. It has a WebAssembly build (geodesy-wasm, Sean Rennie,
  demonstrated in 2023). For wxylib it is two things. First, it is the
  architecture reference for a pipeline-of-operators CRS backend: data flow
  as values, which suits the plan, fetch, compute split. Second, it is a
  pure-Rust backend candidate behind the CRS trait where its coverage is
  enough. **Verdict: align on design; watch, then adopt as a backend.**
- **PROJ compiled to WebAssembly.** This gives the browser full PROJ (all of
  proj.db, datum grids) with no Rust port:
  - [wasm-proj](https://jjimenezshaw.github.io/wasm-proj/) (Javier
    Jimenez Shaw, a PROJ developer) is a web page that runs PROJ in wasm.
    It supports custom and auxiliary proj.db files (the NSRS 2022
    modernisation, for example), horizontal and vertical transforms,
    distortion factors, and a summary of each operation PROJ chose. Its
    build approach uses PROJ's Emscripten fetch option for grids.
  - [proj-wasm](https://www.npmjs.com/package/proj-wasm) (Will Cohen,
    0.1.0-alpha9, August 2026) is an npm package. It is single-threaded
    with a worker pool and fetches grids from workers, so it needs no
    special server headers. A GDAL wasm build using the same hooks is
    planned.
  - [proj.js](https://github.com/mmomtchev/proj.js) (Momtchil Momtchev,
    beta, January 2026) is a SWIG-generated JS binding to the C and C++
    API, both as native Node modules and as wasm. The bundle is about
    1.2 MB compressed, and it has no file or network access in wasm.

  rwarp-wasm already accepts JS projection callbacks
  (`Warper.withTransforms`). Any of these can therefore serve as the
  browser CRS backend today. That gives exact PROJ answers in the web app
  while pure-Rust coverage catches up. **Verdict: adopt proj-wasm or
  wasm-proj's build as the default browser backend through JS callbacks;
  watch proj.js.**

Other CRS items:

- `projjson` 0.1.1 (JosiahParry) parses PROJJSON. `epsg-utils` 0.0.3
  (yutannihilation) handles EPSG, WKT2 and PROJJSON. `proj-wkt` 0.11.0
  (with proj-core) parses WKT, PROJ strings and basic PROJJSON. **Watch.**
  We need a PROJJSON value type for frames (doc 02 `Frame::Crs`), and one
  of these may serve.
- No PROJ project plan for a Rust port was found *(unverified absence)*.

**Recommendation.** Keep the trait. The backends are: `proj` on servers;
`proj-core` in pure-Rust and wasm builds where EPSG-coded datums matter;
`proj4rs` 0.2 for PROJ strings; JS callbacks to PROJ-in-wasm in the
browser. Track Rust Geodesy as both a backend and the design reference for
operator pipelines. Push these backends into rwarp, which still pins
`proj4rs` 0.1.10.

### 5.3 Tiling

| Item | State | Verdict |
|------|-------|---------|
| OGC TileMatrixSet 2.0 | approved standard | **adopt** its JSON as the pyramid description (M4) |
| morecantile (Python), its TS port in deck.gl-raster | 7.1.0 | **align**: test our TMS against it |
| `tile-grid` crate | 0.6.2, last release 2024-10 | **avoid**: stale |
| `ogc-tms` crate | 0.1.0, 2026-08 | **watch**: very new |
| `pmtiles` crate (stadiamaps) | 0.25.0, 2026-10-15 | **adopt** as an output target, not a model |
| hypertidy/grout, tilemath, s2tiles | R, Rust | **align**. These are our own tile and block index arithmetic |

A maintained Rust crate for TMS 2.0 does not exist. It is a small gap
wxylib could fill as part of M4.

## 6. Layers 1 and 2: bytes, codecs, formats, virtualisation

### 6.1 Bytes and codecs

| Item | State | Verdict |
|------|-------|---------|
| `object_store` (now in its own repo, apache/arrow-rs-object-store) | 0.14.2, 2026-09-15 | **adopt** (D3) |
| obspec, obspec-utils | 0.1.0; 0.9.0 | **align** at the Python boundary only |
| zarrs codec plugins (`zarrs_codec`, for example `zarrs_jpeg` 0.2.0) | active | **contribute**. TIFF predictors or LERC go here as zarrs codecs, so virtual TIFF references decode through zarrs |
| `gribberish` | 1.8.4, 2026-10-14 | **adopt** as the GRIB codec and scanner (VirtualiZarr already uses it) |

### 6.2 TIFF and GeoTIFF

| Item | State | Verdict |
|------|-------|---------|
| async-tiff | 0.4.0 | **adopt**. Its `geo` module stops at `GeoKeyDirectory`, `epsg_code()` and the raw model tags. It builds no affine transform and no CRS |
| [geotiff-rust](https://github.com/roteiro-gis/geotiff-rust): `geotiff-core` (roteiro-gis) | 0.8.1, 2026-08-13 | **adopt or port**. It has no dependencies, and provides `GeoKeyDirectory::parse`, `GeoTransform` (from tiepoint plus scale, or a matrix) and `CrsInfo` (EPSG, horizontal and vertical). It cannot produce PROJJSON for user-defined CRSs |
| georust `geotiff` | 0.1.0, synchronous, low activity | **watch**. Issue #13 is where async and georeferencing design is discussed |
| image-rs `tiff` | 0.11.3, synchronous | **watch** (it is the TIFF writer candidate for M12) |
| MapLibre Martin's COG source | on async-tiff | **watch**. It has its own EPSG:3857-only check, which shows the georeferencing gap |

**Answer to the planning thread's question 1.** No Rust GeoTIFF
georeferencing layer exists on async-tiff, and none is planned. The
proposal:

1. Feed async-tiff's raw tag values into `geotiff-core`, or port it
   thinly.
2. Port async-geotiff's GeoKeys-to-PROJJSON logic behind the CRS trait.
3. Open an issue with Development Seed proposing this as an async-tiff
   `geo` feature, or as the redesign georust/geotiff #13 asks for.

If they accept, `wxy-tiff` shrinks to an adapter.

### 6.3 Zarr and Icechunk

| Item | State | Verdict |
|------|-------|---------|
| zarrs and its split crates | 0.23.14, 2026-08-14. Rectilinear grids arrived in 0.23.8; it builds for wasm | **adopt** (D4) |
| `zarrs_icechunk`, `zarrs_object_store`, `zarrs_zip`, `zarrs_http` | 0.6.0, 0.7.0, 0.5.2, current | **adopt** as needed |
| zarr-python 3.4.1, zarrita.js 0.7.5 | current | **align** as interop targets; zarrita.js is the web app's Zarr reader |
| Zarr governance | ZEP 11 accepted 2026-05-29: a Spec Committee now owns specs and the extensions list | **watch** zarr-extensions (rectilinear grid, `cast_value`, `scale_offset`) |

### 6.4 Virtualisation

| Item | State | Verdict |
|------|-------|---------|
| VirtualiZarr | 2.8.0. Parsers: HDF5/NetCDF4, NetCDF3, HDF4, FITS, DMR++, Zarr, zip, kerchunk, GRIB (gribberish), TIFF (virtual-tiff) | **align**. No Rust port is planned |
| Icechunk virtual references | `Store::set_virtual_refs`, `Session::set_chunk_ref` with `ChunkPayload::Virtual(VirtualChunkRef { location, offset, length, checksum })`, `RepositoryConfig::set_virtual_chunk_container` | **adopt** as our reference writer |
| kerchunk | 0.2.10. VirtualiZarr's parsers are replacing it | **align**. Read its JSON and Parquet references; emit them for interop |
| Chunk-manifest spec | not ratified. Candidate formats are JSON, Parquet, kerchunk and Icechunk's FlatBuffers (zarr-specs #287, #82) | **watch**. Icechunk is the working standard |
| [rasteret](https://github.com/terrafloww/rasteret) | Python, 0.4.1 | **align**. It stores COG tile byte ranges as queryable Parquet: a manifest by another name |
| hypertidy/blocklist, mdsumner/virtualized | R, notes | **align**. They are Michael's own kerchunk-Parquet and GDAL-versus-VirtualiZarr experiments |

**Answer to the planning thread's question 2.** Yes, a Rust
virtual-reference writer exists, in Icechunk's Rust API, and VirtualiZarr
already calls it through Python. There is no Rust kerchunk writer, and no
Rust VirtualiZarr. The proposal for S3b (`wxy-virtual`):

- Scanners are Rust producers of `(key, url, offset, length, checksum)`
  plus Zarr metadata.
- They persist through Icechunk's `set_virtual_refs`, and reading goes
  back through `zarrs_icechunk`.
- A small kerchunk JSON or Parquet emitter is an open slot in Rust that we
  could fill for interop.

### 6.5 HDF5, NetCDF and GRIB

| Item | State | Verdict |
|------|-------|---------|
| [hdf5-reader, netcdf-reader](https://github.com/roteiro-gis/netcdf-rust) (roteiro-gis) | 0.9.1, 2026-07-29 | **adopt as scanner base, after checking**. Pure-Rust HDF5 and NetCDF (CDF-1/2/5, NetCDF-4), fuzzed against the C libraries. A public `chunk_index::ChunkEntry { address, size, filter_mask, offsets }` is a chunk-reference scanner in all but name. No szip, no HDF5 virtual datasets |
| hidefix | 0.12.0 (2024). Its S3 reader was merged in 2026 but not released | **watch**. Its chunk index needs native libhdf5 |
| hdf5-metno, georust `netcdf` | bindings to the C libraries | fallback only |
| gribberish; grib-rs | 1.8.4; 0.19.1 | **adopt** gribberish; **watch** grib-rs |
| consus | 0.3.0, 2026-10-15, very new | **watch** |

Who is behind the roteiro-gis crates (geotiff-rust, proj-rust,
netcdf-rust) is unconfirmed beyond the main committer, Ian Norden. They
are small, focused, tested and growing, and they are the strongest
pure-Rust readers in this survey. Getting in touch is worth it.

## 7. Layer 3: conventions and the data model

### 7.1 Conventions to read and write

| Convention | State | Maps to | Verdict |
|------------|-------|---------|---------|
| [zarr-conventions/spatial](https://github.com/zarr-conventions/spatial) v0.1 | Pilot. Affine in rasterio order (not GDAL GT order); `registration` defaults to pixel; future types "rpc", "polynomial", "lookup" | R1 mapping plus cell convention | **adopt, contribute** the R2, R3 and fitted-model transform types |
| [zarr-conventions/proj](https://github.com/zarr-conventions/proj) v0.1 | Pilot. `proj:code`, `proj:wkt2`, `proj:projjson` | `Frame::Crs` | **adopt** |
| [zarr-conventions/multiscales](https://github.com/zarr-conventions/multiscales) v0.1 | Pilot | overviews, pyramids | **adopt** |
| [zarr-conventions/dggs](https://github.com/zarr-conventions/dggs) v1 | Pilot. Modelled on the CF-1.13 healpix grid mapping | R4 `Scheme` | **adopt** when R4 arrives |
| zarr-conventions/cf | Proposal | CF attributes alongside `proj:` | **align** |
| [GeoZarr spec](https://github.com/zarr-developers/geozarr-spec) (OGC SWG) | Unversioned; now built from conventions. CF, DGGS and TMS are under consideration | the whole | **align**. Join the monthly SWG |
| CF-1.13 (Dec 2025; 1.14 in draft) | released | R2, R3 vocabulary; healpix grid mapping | **align** (gate 1: as far as crates go) |
| UGRID 1.0.1, SGRID | stable | R5 topology, staggering | **adopt** as vocabulary |
| CoverageJSON (OGC Community Standard) | stable | its domain types roughly follow our spectrum | **align** as an interchange check |

Rust support for these conventions is thin. The only verified Rust GeoZarr
reader is internal to Apache SedonaDB (`sedona-raster-zarr` 0.5.0,
`geozarr.rs`). zarrs has no geo conventions. A small shared crate
(serde types plus validation for `spatial:`, `proj:`, `multiscales` and
`dggs`) is a clear gap. Development Seed, SedonaDB and others could all
use it. geozarr-toolkit (Python) and metazarr (a JS validator) supply
JSON Schemas we can test against.

### 7.2 The spectrum in other stacks

The xarray ecosystem has independently grown one index type per rung,
which supports doc 02's framing:

| Rung | Python reference |
|------|------------------|
| R1 | rasterix `RasterIndex`, odc-geo `GeoBox` |
| R2, R3 | xESMF and cf-xarray for regridding; xpublish-tiles for rendering |
| R4 | [xdggs](https://xdggs.readthedocs.io) 0.7.0 (H3, HEALPix; encodes the xdggs, CF and zarr DGGS conventions) |
| R5 | uxarray 2026.9.1, xugrid 0.15.3 (UGRID) |
| R6 | xvec 0.5.2 (vector data cubes) |

What they lack is one model under all five. That is wxylib's contribution,
and these packages are the obvious first consumers through `wxy-py`.

## 8. Meshes and DGGS (R4, R5)

| Item | Lang | State | Verdict |
|------|------|-------|---------|
| MDAL | C++ | maintenance mode (QGIS) | **align**: its driver list is a format checklist |
| meshio | Python | 5.3.5 (2024), stagnant | format reference only |
| hypertidy/meshcore | R | active (2026-10-14) | **align closely**. Its verb set (cells, boundaries, vertices, edges, neighbours, parent and children) is the R1, R4 and R5 API |
| Rust UGRID or geoscience mesh crates | n/a | none (`mefikit`, `jaali` are general-purpose) | **gap**: wxylib can own R5 in Rust |
| OGC API - DGGS Part 1 | standard | approved 2025-10 | **align**. DGGRS identifiers become R4 scheme ids |
| [DGGAL](https://github.com/ecere/dggal) | eC with Rust bindings | 0.0.6 | **adopt** as an optional R4 backend (FFI cost) |
| rs4dggs | Rust | 0.2.0, 2026-10, pure-Rust port of DGGAL grids | **watch** |
| h3o | Rust | 0.11.0 | **adopt** |
| cdshealpix, healpix-geo (Grid4Earth) | Rust, Python | 0.10.1, 2026-10-15 | **adopt** cdshealpix. healpix-geo adds the ellipsoid |
| a5 | Rust | 1.0.0 | **adopt** as a plugin |
| s2 | Rust | 0.2.0, thin | **watch** |

No single Rust DGGS abstraction exists. doc 02's `Scheme` variant, wrapping
h3o, cdshealpix, a5 and DGGAL with zarr `dggs` encoding, would be the first.
Destination Earth's HEALPix Zarr data is a ready test corpus.

## 9. Layer 4: warp, resampling, regridding

| Item | Lang | State | Relation | Verdict |
|------|------|-------|----------|---------|
| GDAL warper | C++ | 3.13.3 | the oracle rwarp matches | **align** |
| rasterio, rioxarray reproject | Python | 1.5.2; 0.23.0 | Python argument vocabulary (`dst_crs`, `resolution`, `resampling`) | **align** for the `wxy-py` API |
| odc-geo `xr_reproject`, odc-loader, odc-stac | Python | 0.5.3; 0.6.5; 0.5.3 | GDAL underneath | **align** |
| pyresample, satpy | Python | 1.35.0; 0.60.0 | swath resampling (KD-tree, EWA, bucket) | **align**. Its 2.0 resampler registry could host a wxylib resampler |
| xESMF, ESMF | Python, Fortran | 0.9.2; ESMF 8.9.1 | conservative weights for curvilinear and unstructured grids | **avoid duplicating**. Read ESMF and SCRIP weight files later |
| [gridr](https://crates.io/crates/gridr) (CNES) | Rust, pyo3 | 0.7.0, 2026-10-16 | resampling through a target-to-source coordinate grid, full or undersampled: the approximate transformer idea | **watch closely**: a possible collaborator |
| warp-rs | Rust | 0.2.1, "nothing warps yet" | | **watch** |
| fast_image_resize | Rust | 6.1.0 | SIMD separable resize, same CRS only | **adopt** for same-CRS overview paths |
| `@developmentseed/raster-reproject` | TS | 0.8.1 | adaptive delatin mesh, refined in uv space with error samples, 0.125 px default | **align, contribute**. Agree on a mesh exchange so rwarp's approximate transformer can produce or consume it |
| zarr-layer (dynamical.org, ex-CarbonPlan) | TS | 0.11.0 | mesh GPU reprojection with zarrita, experimental GeoZarr multiscales | **align** |
| wgpu or WebGPU geo-warp crate | Rust | none found *(unverified absence)* | | **gap**: rwarp's mesh feeding a wgpu path |
| controlledburn-rs (hypertidy) | Rust | 0.2.1, 2026-10-15 | exact-coverage sparse rasterisation | **adopt** for cutlines and masks |

## 10. Layers 5 and 6: composition, catalogues, surfaces

### 10.1 Composition and catalogues

| Item | State | Verdict |
|------|-------|---------|
| GDAL VRT, GTI, `gdal mdim mosaic` (3.12), GDALG pipelines (3.11+) | current | **align**. They are the behaviour our virtual scheme (S7) must express |
| rustac, stac-geoparquet | current | **adopt** |
| GeoParquet 2.0 (rc.1) and native Parquet GEOMETRY/GEOGRAPHY types | adopted 2025; Apache blog 2026-02-13 | **adopt** for R6 storage |
| [Apache SedonaDB](https://github.com/apache/sedona-db) | Rust on DataFusion, 0.5.0, 2026-10-13. Its raster type is effectively R1 and "not quite ready to make a splash"; crates `sedona-raster`, `sedona-raster-zarr`, `sedona-raster-gdal` | **watch, contribute**. Offer the R2+ model and the conventions crate rather than compete |
| DuckDB `raster` (GDAL-backed), `raquet` | community extensions | **watch** |

### 10.2 Bindings

| Item | State | Verdict |
|------|-------|---------|
| pyo3 0.30.1, maturin 1.15.0, numpy crate 0.30.0 | current | **adopt** |
| pyo3-arrow, pyo3-object_store, pyo3-geoarrow | current | **adopt** |
| extendr (extendr-api 0.8.2) vs savvy (0.11.0) | both active | **choose one at S6**. extendr is Michael's habit (robstore, rustycogs, trowel). savvy is used by r-polars and SedonaDB's R package |
| nanoarrow, geoarrow (R) | 0.9.0; 0.4.4 | **adopt** for zero-copy Arrow into R |
| wasm-bindgen 0.2.129 | current | **adopt** (already used in rwarp-wasm) |

### 10.3 Browser and serving

| Item | State | Verdict |
|------|-------|---------|
| deck.gl-raster, lonboard | 0.8.1; 0.17.0 | **align, contribute** (section 4) |
| OpenLayers `ol/source/GeoTIFF`, `ol/source/GeoZarr` | 10.11.0 | **align**. An rwarp-wasm source could stand in where OpenLayers' triangulation is slow |
| MapLibre GL with a COG protocol | 6.14.0; protocol 0.10.0 | **align**. MapLibre does not reproject rasters *(unverified)* |
| geotiff.js, `@cogeotiff/core` | 3.0.5; 9.5 | **adopt** in the web app if JS fetches the tiles |
| GridLook, Browzarr, zarr-cesium | active | **watch** |
| titiler-xarray, titiler-multidim, titiler-cmr, titiler-eopf | active (titiler-multidim and titiler-cmr unreleased) | **align** |
| Xpublish, xpublish-tiles | 0.5.2; 0.11.2 | **align, contribute** |
| hypertidy rangefinder, mdsumner rema-ovr | HTML/JS | **align**. They are prior art for the `web` repo |

## 11. Pure-Rust GDAL alternatives (the contrast case)

| Project | Size and history | Reuse of the shared spine | Validation | Verdict |
|---------|-----------------|---------------------------|------------|---------|
| [OxiGDAL, renamed OxiGeo](https://github.com/cool-japan/oxigdal) (COOLJAPAN) | 78 crates, then 75. About 1.1M lines of Rust in 13 commits, one per release (the first adds 794k lines). v0.2.4, 2026-08-18. About 1k downloads of the top crate | none of zarrs, object_store, async-tiff, tiff, geoarrow, proj-core. It has its own Zarr, S3, codecs and `oxiproj` | test workflows disabled. Fixes driven by issues: Zarr codec dispatch stub, COG mask IFDs counted as overviews, VRT parsing, GPKG overflow pages | **avoid**. Mine its issues for test cases |
| [terrio](https://github.com/opengeos/terrio) (Qiusheng Wu) | 2 crates, about 103k lines in 3 days, through reviewed PRs. 0.2.0, 2026-10-15 | builds on Whitebox crates. Its own Zarr, S3 SigV4 and HTTP; GDAL is optional | **a generated conformance table** against GDAL 3.12.2 and PROJ 9.7.1: 40,054 cases, 39,816 identical, 206 within tolerance, 32 different (all CRS or datum grid) | **watch**. **Copy the conformance harness idea** |
| [Whitebox Next Gen](https://github.com/jblindsay/whitebox_next_gen) `wbraster`, `wbprojection` (John Lindsay) | a port of a mature codebase, 854 commits | its own GeoTIFF, projection and local Zarr | 471 tests. Recent polar stereographic accuracy fixes | **watch**. Its domain is credible, but remote access is weak |
| surtgis, eorst, cogrs | small | partial | | **watch** |

The lesson for wxylib (it extends doc 01 D4 and doc 03 A5):

- Breadth grows with code generation. Correctness grows only with
  validation against a reference.
- The monoliths' bugs sit in exactly the parts they reimplemented instead
  of adopting.
- Publish a terrio-style conformance table, generated from oracle runs
  (identical, within tolerance, different), for `info`, windows, transforms
  and warps.
- Never count `#[test]` attributes as validation.

## 12. Michael's own reference repositories

These are listed so that wxylib reuses ideas already worked out, and so
others can find the lineage.

| Area | Repositories |
|------|--------------|
| Warp and grid core | hypertidy/rwarp (the warp core), vaster and vaster-rs, vapour (`vapour_warp_raster`, the reference warper API), gdalio, warpaint, whatarelief, ceramic |
| Concepts | regular-in-what (the frame-relative ladder), playproj, cb-grid-report, mdsumner/rasterwise (broken grid encodings; a test-case catalogue) |
| Tiling and planning | grout and pygrout, tilemath, s2tiles (Rust; arithmetic MGRS-to-COG index), filearchy |
| Meshes | meshcore (with its mesh-spec draft), silicate (`silicate2` UGRID branch), anglr, quadmesh, textures (grid as quad mesh: the GPU mesh idea), trowel (Rust; constrained Delaunay), decido, wkpool |
| Rasterise and exact algorithms | controlledburn and controlledburn-rs, gridflood (Rust; exact tiled driver), fasterize |
| Rust I/O already started | rustycogs (R on async-tiff and object_store), robstore (R on object_store), starc (STAC reference cache in Parquet) |
| Virtualisation and multidim | blocklist (kerchunk-Parquet from NetCDF and HDF5), mdsumner/virtualized, vrtstack, gdalxarray, zaro, altarr, lazyraster, gdalblock, cmemsarco |
| Data users (AAD) | raadtools, raadfiles, raadvrt, bowerbird, blueant, seaice, SOmap, angstroms, xyt: the first real downstream workloads |
| Browser | rangefinder (server-free STAC, COG and Zarr explorer), mdsumner/rema-ovr |

The Trackage org is about tracking data and is not relevant here. The
mdsumner user account (over 500 repos) could not be listed completely, so
this table is partial.

## 13. Gaps wxylib can fill

Each gap is something the landscape needs, that no one is building in Rust,
and that sits inside wxylib's existing plan. Contributing it upstream where a
home exists keeps wxylib lean.

**G1. Rust GeoTIFF georeferencing on async-tiff.** GeoKeys to the R1
mapping plus a PROJJSON frame.
- Get: `wxy-tiff` becomes trivial, and async-tiff users (Martin, rustycogs,
  async-geotiff's eventual Rust path) gain it too.
- Cost: an upstream conversation, and possibly waiting for review.
- Without it: every Rust COG user writes its own, as Martin did.

**G2. Rust scanners writing virtual references through Icechunk.** TIFF
first (with async-tiff's byte-range API), then HDF5 and NetCDF (with
roteiro-gis hdf5-reader) and GRIB (with gribberish).
- Get: VirtualiZarr-compatible references produced without Python, usable
  from the CLI, R and the browser.
- Cost: we must keep parity with VirtualiZarr's parser behaviour and
  follow Icechunk's spec changes.
- Without it: virtualisation stays Python-only, and doc 03 A6 depends on a
  Python runtime.

**G3. A Rust crate for the zarr geo conventions** (`spatial:`, `proj:`,
`multiscales`, later `dggs`), validated against the geozarr-toolkit
schemas.
- Get: one shared implementation for zarrs users, SedonaDB and us, and a
  seat in the GeoZarr SWG.
- Cost: small. We must follow a spec that is still at Pilot.
- Without it: each Rust project embeds its own reader, as SedonaDB does
  today.

**G4. Non-affine transform types for `spatial:`.** "lookup" (R2 and R3),
"rpc" and "polynomial" (R3'). This is doc 02's spectrum, contributed as
conventions.
- Get: the data model becomes a community standard rather than a wxylib
  idiom.
- Cost: standards process time.
- Without it: R2 and up stay outside GeoZarr, and every tool guesses.

**G5. A mesh contract shared with browser reprojectors.** rwarp's
approximate transformer emits, or accepts, the same error-bounded
triangle mesh as `raster-reproject` and zarr-layer.
- Get: exact GDAL-identical warps and fast GPU display share one plan.
- Cost: agreeing a small format with Development Seed.
- Without it: two incompatible linearisations of the same transform.

**G6. Rust R4 and R5 layers** (DGGS trait over h3o, cdshealpix, a5 and
DGGAL; UGRID topology). These are already in doc 03's later stages. The
landscape shows nobody else is building them in Rust.

**G7. A public conformance table against GDAL and PROJ** (terrio's idea),
generated by the oracle runs of doc 03 A5.

## 14. Decisions proposed, with rationale

**LS1. Treat Development Seed and Earthmover crates as upstream, not as
dependencies to wrap defensively.** Open issues before building anything
they might host (G1, G5).
- Get: smaller wxylib, better crates for everyone, early warning of
  breaking changes.
- Cost: slower when upstream is busy, and some design compromise.
- Without it: a parallel stack that drifts, which is the path the
  monoliths took.

**LS2. Emit and read the zarr-conventions natively; contribute the
spectrum as transform types (G3, G4).**
- Get: GDAL 3.13+, ESA EOPF, deck.gl-raster and OpenLayers all read our
  output.
- Cost: we follow Pilot-stage specs as they change.
- Without it: a wxylib metadata dialect nobody else reads.

**LS3. Icechunk is the virtual-reference store; kerchunk JSON or Parquet
is an interop export (G2).**
- Get: one store with a Rust writer, read by zarrs, zarr-python and
  icechunk-js.
- Cost: an Icechunk dependency in `wxy-virtual`, and its MSRV
  (1.95 at 2.3.0).
- Without it: we would design our own manifest, while the chunk-manifest
  spec is still unsettled.

**LS4. In the browser, PROJ arrives as wasm through JS callbacks; on native
builds, through the trait backends; Rust Geodesy is the design reference
for operator pipelines.**
- Get: exact PROJ answers in the web app now, without waiting for pure-Rust
  coverage.
- Cost: about 1 MB or more of wasm, and worker plumbing for grids.
- Without it: the web app is limited to what proj4rs or proj-core
  implement.

**LS5. Publish a conformance table (G7) from S2 onwards.**
- Get: credibility that the monoliths lack, and a regression net.
- Cost: oracle runs on Michael's machine or in CI with GDAL.
- Without it: claims of GDAL parity are unfalsifiable.

## 15. Watch list

Ranked by how directly each item can change a wxylib decision.

| # | What | Signal to watch | Why |
|---|------|-----------------|-----|
| 1 | async-tiff (Rust) | rust-v* release tags, issue on georeferencing (G1) | our COG engine; breaking changes are frequent |
| 2 | zarrs and zarrista | zarrs releases; zarr-python PR #4064 | our Zarr engine is becoming Python's |
| 3 | Icechunk | releases and spec page | the virtual store (LS3) |
| 4 | VirtualiZarr and the virtual-zarr org | releases; virtual-tiff | the parser contract our scanners match |
| 5 | zarr-conventions and the GeoZarr SWG | github.com/zarr-conventions; monthly SWG notes | the metadata we emit (LS2, G4) |
| 6 | rust-proj-capability, proj-core, proj4rs, Rust Geodesy, proj-wasm | releases; the PROJ mailing list | the CRS backend decision |
| 7 | GDAL NEWS and gdal-dev | 3.14 Zarr, GeoZarr and CLI changes | the oracle; the warning about unsponsored cloud protocols |
| 8 | deck.gl-raster and zarr-layer | releases; FOSS4G talks | mesh contract (G5); web app overlap |
| 9 | roteiro-gis crates (geotiff, proj, netcdf) | crates.io versions | candidate dependencies for G1 and G2 |
| 10 | Apache SedonaDB raster | releases | the nearest Rust raster engine; a consumer of G3 |
| 11 | ESA EOPF Zarr and DestinE HEALPix | sample services | real GeoZarr and DGGS corpora for fixtures |
| 12 | terrio, gridr, OxiGeo | releases, issues | overlapping scope; test cases from their bugs |

Also on the radar: the Zarr Spec Committee and zarr-extensions, OGC DGGS
and TMS work, CF-1.14, GeoParquet 2.0 final, Earthmover Zax and Flux,
xpublish-tiles, the CNG Forum and Zarr Summit (for 2027 talks), pyresample
2.0, DGGAL and rs4dggs, Pangeo Discourse, and the R spatial community
(r-spatial, rOpenSci, the r-universe `geozarr` package *(unverified)*).

The cheapest way to keep this current is a monthly check of the release
feeds above, written into this document's section 15 as a dated delta.

## 16. Questions for gate 4

1. **Upstream first (LS1).** Should we open the async-tiff georeferencing
   issue (G1) now, before `wxy-tiff` S2 work goes further?
2. **Icechunk as the reference store (LS3).** Accept the dependency in
   `wxy-virtual`, with kerchunk export for interop?
3. **Browser CRS (LS4).** proj-wasm (npm, worker pool) or a wasm-proj-style
   Emscripten build as the default, behind rwarp-wasm's JS callbacks?
4. **Conventions work (G3, G4).** Should wxylib take a seat in the GeoZarr
   SWG and propose "lookup" and "rpc" transform types?
5. **Watch cadence.** Monthly deltas to section 15, run as a routine?

## 17. Not verified

- GitHub issue and discussion state across all projects (search was not
  available).
- Earthmover Flux and Zax internals and licensing; people's current roles.
- The status of zarr-specs #287 (chunk manifest).
- Who is behind roteiro-gis beyond its main committer.
- Whether gribberish exposes GRIB message byte offsets as a public Rust API.
- Whether MapLibre reprojects rasters natively.
- The completeness of proj-wasm's PROJ build.

## 18. Gate 4 decisions (2026-10-16)

1. **Upstream georeferencing (G1, LS1): later.** Michael will raise it with
   Development Seed when he can. Until then, `wxy-tiff` keeps its own
   GeoKeys-to-mapping code, written so it can move upstream as one piece.
2. **Icechunk as the reference store (LS3): yes**, with kerchunk JSON or
   Parquet export for interop. This comes with an open topic to keep
   exploring: the simpler, flat view of references as a table (one row
   per chunk: key, url, offset, length, checksum, as in kerchunk Parquet
   or rasteret). That is enough when there are no versions, no
   transactions and one writer. The questions to answer are when Icechunk
   is overkill, and whether `wxy-virtual` should produce a table first,
   with Icechunk as one place to write it.
3. **Browser CRS (LS4): proj-wasm**, behind rwarp-wasm's JS callbacks.
4. **Conventions work (G3, G4): yes, both.** wxylib takes part in the GeoZarr
   SWG, proposes the "lookup" and "rpc" transform types for `spatial:`, and
   publishes a small Rust crate for the zarr geo conventions.
5. **Watch cadence: monthly.** A scheduled check of the section 15 feeds
   adds a dated delta to this document.
