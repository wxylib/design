# 01: The modules implicit in GDAL

Status: gate 1 passed 2026-10-16 (decisions in section 8)
Sources read: GDAL `master` at `aa6c524` (2026-10-16), hypertidy/rwarp at
`20572c3`, async-tiff 0.4.0, zarrs (workspace head), zarrista 0.1.0, and
mdsumner/rust-proj-capability at `5a0ce79` for everything about CRS.
Crate versions were checked on crates.io on 2026-10-16.

## 1. Why a survey

GDAL is organised by build target (`port/`, `gcore/`, `alg/`, `frmts/`,
`ogr/`, `apps/`), not by concept. Several clean concepts live inside it but
are bound to each other through `GDALDataset` and `GDALRasterBand`. The warper
is the clearest example. `GDALWarpOperation` plans source windows, reads
through the block cache, transforms coordinates and runs the kernel in a
single object. rwarp has already shown that the planning, transform and
kernel parts come apart cleanly when the reading part is handed back to the
caller.

This document lists the concepts that come apart the same way, says where
each lives in GDAL, what Rust already offers for it, and how they could
depend on each other. It does not design any of them. Step 2 designs the data
model and step 3 the crates.

## 2. Method

For each concept:

- **GDAL home**: the files that implement it.
- **Coupling**: what it needs from the rest of GDAL. "Low" means it could be
  lifted out with its inputs passed as plain values.
- **Rust today**: crates that already cover it, with versions.
- **Verdict**: *adopt* (use an existing crate, maybe behind a trait), *own*
  (wxylib builds and maintains it), *own-later* (wanted, not yet), or
  *defer* (out of scope until something needs it).

## 3. The module map

Modules are grouped in layers. A module may only depend on modules in lower
layers. That rule is the main thing this map proposes.

### Layer 0: values with no I/O

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M1 | Grid: geotransform, extent, dimension, cell index, window arithmetic | `gcore/gdal_geotransform.h`, `gdal_misc.cpp` (`GDALInvGeoTransform`, `GDALApplyGeoTransform`) | Low | `vaster` 0.2.0 | own (vaster) |
| M2 | CRS: definition, parsing, CRS-to-CRS point transform | `ogr/ogrspatialreference.cpp`, `ogr/ogrct.cpp`, `ogr_srs_*.cpp` | Medium (PROJ) | `proj` 0.31, `proj-core` 0.11, `proj4rs` 0.2.1 (+ `crs-definitions` 0.6), others; see [rust-proj-capability](https://github.com/mdsumner/rust-proj-capability) | open question; adopt behind a trait (`rwarp::crs::CrsTransform` already does this) |
| M3 | Data types, nodata, masks, scale/offset | `gcore/gdal.h` (`GDALDataType`), `gdal*maskband.cpp`, `gdalmultidim_array_unscaled.cpp` | Low | partly in async-tiff and zarrs, each with its own enum | own (one small shared vocabulary) |
| M4 | Tile matrix sets | `gcore/tilematrixset.cpp` | Low | `tile-grid` 0.6.2 (last release 2024) | own-later; check `tile-grid` first |

### Layer 1: bytes

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M5 | Byte access ("VSI"): local, HTTP, S3, GCS, Azure, range reads | `port/cpl_vsil_*.cpp`, `cpl_vsil_curl.cpp`, `cpl_aws.cpp` | Low | `object_store` 0.14.2 | adopt |
| M6 | Byte views: subfile, zip/tar, gzip, in-memory, cached reader | `cpl_vsil_subfile.cpp`, `cpl_vsil_tar.cpp`, `cpl_vsil_gzip.cpp`, `cpl_vsi_mem.cpp`, `cpl_vsil_cache.cpp` | Low | `object_store` (memory), `zarrs_zip`, `async_zip` | own-later as thin adapters over M5 |
| M7 | Codecs: deflate, LZW, zstd, JPEG, LERC, blosc, predictors | `port/cpl_compressor.cpp`, libtiff codecs, `frmts/zarr/zarr_v3_codec_*.cpp` | Low | async-tiff decoders, `zarrs_codec`, `flate2`, `zstd`, `weezl`, `zune-jpeg`, `lerc` | adopt |

### Layer 2: formats (containers)

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M8 | TIFF/COG structure: IFDs, tiles, overviews as IFDs | `frmts/gtiff/` with bundled libtiff | High in GDAL, low in Rust | `async-tiff` 0.4.0 (async, object_store, read and decode separated) | adopt |
| M9 | GeoTIFF georeferencing: GeoKeys to grid and CRS | `frmts/gtiff/gt_wkt_srs.cpp`, libgeotiff | Medium | `async-tiff::geo` (tags), `geotiff` 0.1.0 | own a thin layer: GeoKeys to M1 + M2 |
| M10 | Zarr v2/v3 arrays, groups, codecs, sharding | `frmts/zarr/` | High in GDAL, low in Rust | `zarrs` (Zarr 3.1 conformant), `zarrs_object_store` 0.7, `icechunk` 2.3 | adopt |
| M11 | Virtual chunk references (kerchunk JSON or Parquet) | `frmts/zarr/vsikerchunk*.cpp` | Medium | storage transformers in zarrs, icechunk virtual chunks | own, early: the default pathway for formats (doc 03, A6, added 2026-10-16) |
| M12 | Write path: GeoTIFF/COG creation, Zarr writing | `gtiffdataset_write.cpp`, `cogdriver.cpp`, `zarr_*` | High | `tiff` 0.11 (sync encoder), zarrs (full write) | defer for TIFF, adopt zarrs when needed |
| M13 | The other ~130 raster drivers | `frmts/*` | High | `gdal` 0.19 crate (bindings) | defer; reach them through the GDAL workaround (section 6) |

### Layer 3: the data model

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M14 | Classic raster: dataset, bands, blocks, `RasterIO`, overviews | `gcore/gdaldataset.cpp`, `gdalrasterband.cpp`, `rasterio.cpp`, `gdaldefaultoverviews.cpp` | Very high; it is the hub | none generic | own (step 2) |
| M15 | Multidimensional: group, array, dimension, attribute, views | `gcore/multidim/` (31 files) | High | zarrs `Array`/`Group` for Zarr only | own (step 2) |
| M16 | Chunk cache and read scheduling | `gdal_abstractbandblockcache.h`, `gdalrasterblock.cpp`, `gdal_thread_pool.cpp`, `gdalarraybandblockcache.cpp` | High | async-tiff merges tile requests; zarrs has chunk caches | own-later; design the seam in step 2 |

### Layer 4: algorithms (pure compute over plans and arrays)

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M17 | Transformers: GenImgProj, approximate, GCP polynomial, RPC, TPS, geolocation arrays | `alg/gdaltransformer.cpp`, `gdal_crs.cpp`, `gdal_rpc.cpp`, `gdal_tps.cpp`, `gdalgeoloc*.cpp` | Medium | `rwarp`: GenImgProj, Approx, GCP | own (rwarp); RPC, TPS and geolocation later |
| M18 | Warp planning: source window, chunk list, antimeridian split | `alg/gdalwarpoperation.cpp` | Medium | `rwarp::source_window` | own (rwarp) |
| M19 | Resampling kernels | `alg/gdalwarpkernel.cpp`, `gcore/overview.cpp`, `rasterio.cpp`, `alg/gdalresamplingkernels.h` | Medium | `rwarp::warp` (warp kernels), `fast_image_resize` (images only) | own; see finding F3 |
| M20 | Raster algorithms: polygonize, rasterize, contour, proximity, sieve, fill nodata, viewshed, gridding, DEM | `alg/*.cpp`, `apps/gdaldem_lib.cpp` | Low to medium | `geo` 0.33, `contour` crates | defer |

### Layer 5: composition (descriptions of virtual data)

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M21 | VRT classic: simple, complex and averaged sources, warped VRT, derived and processed bands, pixel functions | `frmts/vrt/` | Very high | none | own (after step 2) |
| M22 | VRT multidimensional | `frmts/vrt/vrtmultidim.cpp` | High | none | own, with M21 as one scheme if step 2 unifies them |
| M23 | Tile indexes and mosaics: GTI, STAC, buildvrt | `frmts/gti/`, `frmts/stacit/`, `apps/gdalbuildvrt_lib.cpp` | High | `geoarrow` 0.9 for GeoParquet indexes | own-later |

### Layer 6: surfaces

| # | Module | GDAL home | Coupling | Rust today | Verdict |
|---|--------|-----------|----------|------------|---------|
| M24 | Algorithm registry, CLI, pipelines | `gcore/gdalalgorithm*.cpp`, `apps/gdalalg_*.cpp` | High | `clap` | own, designed last |
| M25 | Bindings: Python, R, wasm | `swig/` | n/a | `pyo3`, `extendr-api` 0.9, `savvy` 0.11, `wasm-bindgen` (rwarp-wasm already uses it) | own, thin per crate |

### Added at gate 1: meshes (the MDAL concept)

| # | Module | Inspiration | Coupling | Rust today | Verdict |
|---|--------|-------------|----------|------------|---------|
| M26 | Meshes: vertices, edges, faces, layered volumes, and datasets defined on each of them, over time | MDAL (the mesh library under QGIS, separate from GDAL), UGRID, SGRID | n/a (not in GDAL) | no general crate | own, as part of the one data model (doc 02), not as a third mode |

MDAL predates GDAL's multidimensional API and does not align with it. Rather
than bridge the two, doc 02 treats classic raster, multidimensional arrays,
meshes and vector features as points on one spectrum.

### Out of scope for now

Vector drivers and SQL (~80 OGR drivers), GNM networks, PAM `.aux.xml`
sidecars, metadata domains, raster attribute tables, colour tables. Vector
*data* is not out of scope: it sits at one end of the raster to vector
spectrum in doc 02. georust (`geo`, `geo-types`), `geoarrow` and `geozero`
cover vector geometry and formats, and we use them rather than rebuild them.

## 4. Dependency sketch

```
 L6  surfaces     CLI/pipelines (M24)        bindings py / R / wasm (M25)
                        |                              |
 L5  composition  VRT classic+mdim (M21,M22)    mosaics/indexes (M23)
                        |                              |
 L4  algorithms   transformers (M17) -> warp plan (M18) -> kernels (M19)
                        |                    |                |
 L3  data model   array + dims + georef (M14/M15) <---- cache/schedule (M16)
                        |
 L2  formats      COG/TIFF (M8)  GeoKeys (M9)  Zarr (M10)  refs (M11)
                        |              |           |
 L1  bytes        object_store (M5)   views (M6)   codecs (M7)
                        |
 L0  values       grid (M1)   CRS trait (M2)   dtype/nodata (M3)   TMS (M4)
```

Two edges matter more than the rest:

- **L4 does not depend on L1 or L2.** Transformers, planning and kernels take
  grids, CRS handles and slices of numbers. This is already true of rwarp and
  it is what lets rwarp run in a browser over tiles that JavaScript fetched.
- **L2 does not depend on L3.** async-tiff and zarrs know nothing about our
  data model. Adapters from each format into the model live in L3 (or in
  small adapter crates), so the format crates can be swapped or upgraded
  without touching anything above.

## 5. Findings from reading the code

**F1. GDAL already treats classic raster as a special case of mdim, in one
direction at a time.** `gcore/multidim/gdalmultidim_array_bridge_classic.cpp`
exposes a raster band as a 2D `GDALMDArray`, and `GDALMDArray::AsClassicDataset`
goes the other way. `gdalmultidim_array_resampled.cpp` and the newer
`gdal mdim reproject` algorithm warp mdim arrays with the same warper. These
are bridges bolted on after the fact, and they show a unified model is
possible. Step 2 will start from them.

**F2. Planning, reading and computing are fused in three places, not one.**
The warper (`gdalwarpoperation.cpp`), overview building (`overview.cpp`) and
resampled `RasterIO` (`rasterio.cpp`) each choose source windows, read
through the block cache, then resample. rwarp separates this for the warper.
The same plan, read, compute split applies to the other two.

**F3. There are two resampling implementations.** The warp kernel
(`gdalwarpkernel.cpp`) and the overview/RasterIO path (`overview.cpp`,
`gdalresamplingkernels.h`) implement nearest, bilinear, cubic and Lanczos
separately, with different edge and antialiasing rules. rwarp's documented
limitation (no kernel scaling when downsampling) is exactly the behaviour the
overview path has and the warp path adds. One resampling module serving both
is cheaper than two, and it fixes the rwarp limitation as a by-product.

**F4. VSI is two things.** Remote byte access (curl, S3, Azure, GCS) is fully
covered by `object_store`. Byte views (subfile, archive members, gzip, kerchunk
references) are small and composable but have no single Rust home. They are
only needed once we read archives or virtual references.

**F5. async-tiff and zarrs already make the I/O split we want.** Both separate
"fetch encoded bytes" (I/O-bound, async) from "decode" (CPU-bound). async-tiff
says so in its feature list. zarrista exposes encoded chunk access for the same
reason. That is the same seam rwarp's plan/read/warp diagram draws. Our data
model should expose it too, rather than hide it behind a synchronous
`read_window` call the way `RasterIO` does.

**F6. The georeferencing is spread across formats.** GeoTIFF has GeoKeys, Zarr
has conventions (CF, GeoZarr, `spatial:` attributes), and VRT has a
`GeoTransform` element. GDAL turns all of these into a geotransform plus an
`OGRSpatialReference` inside each driver. The same normalisation (format
metadata to M1 grid plus M2 CRS) belongs in one place per format, just above
the format crate.

**F7. Which CRS backend is an open question, and rwarp predates the evidence.**
rwarp offers `proj` and `proj4rs` 0.1.10 behind its `CrsTransform` trait.
The newer [rust-proj-capability](https://github.com/mdsumner/rust-proj-capability)
survey measures 7 crates against PROJ 9.9.0 on 93 fixtures. In short: only
`proj` does everything, at the cost of C++ and no wasm. `proj-core` is the
pure-Rust choice when EPSG-coded datum shifts matter. `proj4rs` executes what
it ports exactly but needs good PROJ strings. `proj4rs` with default features
and libproj also cannot share one native binary because of a `geod_*` symbol
clash. We defer to that survey for the CRS decision, and push changes to
rwarp (a `proj-core` backend, `proj4rs` 0.2) as it settles.

## 6. Organising decisions, with rationale

Each decision lists what we get, what it costs, and what happens without it.

**D1. Layering rule: a module depends only on lower layers.**
- Get: each crate builds, tests and documents on its own. Kernels run in wasm.
  Format crates can be swapped.
- Cost: more crates and more small adapter types between them, plus some
  duplicated conversion code.
- Without it: we rebuild GDAL's hub, where `GDALDataset` is needed to do
  anything, and lose rwarp's main property.

**D2. Plan, read, compute as the shape of every pipeline (warp, overviews,
resampled reads, VRT evaluation).**
- Get: plans can be inspected, costed, serialised and resumed. I/O can be
  scheduled and merged across a whole plan. The browser and server can share
  the compute half.
- Cost: callers do more work than with a single `read_window`. A convenience
  layer that runs plan, read and compute in one call is needed on top.
- Without it: performance tuning hides inside each module, as in GDAL, and
  async I/O cannot be scheduled well.

**D3. Adopt object_store for remote bytes instead of building a VSI.**
- Get: S3, GCS, Azure, HTTP and local paths, maintained by the Arrow project,
  and the same store type that async-tiff and zarrs already accept.
- Cost: no `/vsizip/` style path strings; byte views (M6) need their own
  small layer later. Its async-only API needs a runtime in synchronous
  callers.
- Without it: we would maintain cloud authentication code, which is a large
  and security-sensitive surface far from our purpose.

**D4. Adopt async-tiff and zarrs as the format layer and add no format
readers of our own.**
- Get: COG and Zarr v3 (with sharding and icechunk), both async, both
  maintained, with Python bindings already aligned (async-tiff's Python
  package, zarrista).
- Cost: we follow their release cycles and data type enums, and each needs a
  small adapter into our model.
- Without it: we would write a TIFF reader and a Zarr implementation, taking
  years, before reaching the parts no one else has built.

**D5. CRS stays behind a trait (as in rwarp), the core never depends on a
CRS crate, and the choice of backend is left to the rust-proj-capability
survey.**
- Get: libproj on servers, a pure-Rust backend (`proj-core` or `proj4rs`) in
  wasm, and the page's own projection library from JavaScript, all from one
  build of the core. The backend can change as that survey's answer changes,
  without touching anything else.
- Cost: CRS metadata such as WKT, axis order and datum information has to
  travel as opaque strings until a richer abstraction is needed. Backends must
  be mutually exclusive features in native builds, because of the symbol clash
  in F7.
- Without it: the core inherits the native libproj dependency and loses wasm,
  or locks in a pure-Rust crate that the survey shows is silently wrong for
  some datums.

**D6. One resampling module shared by warp, overviews and resampled reads.**
- Get: one set of kernels to validate against GDAL, and correct downsampling
  in warps (F3).
- Cost: kernels must handle scaled support, which is harder to make
  bit-identical with GDAL for every case.
- Without it: two divergent kernels, as in GDAL, and the rwarp downsampling
  limitation stays.

**D7. GDAL is reachable only as one source adapter behind a feature flag,
through the `gdal` crate.**
- Get: the ~130 drivers we will not rebuild (HDF, NetCDF, GRIB and others)
  stay usable while the foundation grows, and GDAL output stays available as
  a validation oracle in tests.
- Cost: a native dependency for anyone who turns the flag on, plus pressure
  to "just use GDAL" for features that should be built properly.
- Without it: users with one awkward format cannot use any of the stack. The
  rule against reaching early is enforced by keeping GDAL at L2 as one source
  among others, never in L3 or above.

**D8. Defer vector, the write path, sidecars and most drivers.**
- Get: focus on the read, plan, warp path that rwarp and the browser app
  already prove.
- Cost: no COG writer means early outputs are Zarr, PNG tiles, or GDAL via
  D7.
- Without it: the scope becomes "rewrite GDAL", the failure mode this project
  exists to avoid.

## 7. Questions for gate 1

1. **Layer rule.** Is "depend only on lower layers" the right hard rule, or
   should the composition layer (VRT) be allowed to sit beside the data model
   rather than above it?
2. **Resampling.** Should the unified resampling module (D6) live in rwarp, or
   in its own crate that rwarp depends on?
3. **Georeferencing conventions (F6).** For Zarr, should we target GeoZarr
   specifically, CF conventions, or both from the start?
4. **Byte views (M6).** Are archive members (`/vsizip/` style) and kerchunk
   references needed early for your data, or can they wait?
5. **Anything missing.** Any GDAL concept you rely on that this map does not
   name? Candidates I left out on purpose: PAM sidecars, RAT, colour tables,
   metadata domains.

Once these are settled, step 2 takes M3, M14, M15 and M16 and designs the
data model, starting from F1 and F5.

## 8. Gate 1 decisions (2026-10-16)

1. **Layer rule: hard.** A module depends only on lower layers. VRT sits
   above the data model and consumes it like any other client.
2. **Resampling: its own crate.** rwarp and overview building both depend on
   it; neither depends on the other.
3. **Zarr georeferencing: both GeoZarr and CF**, but only as far as existing
   crate support goes. No significant new convention work of our own.
4. **Byte views (archives, kerchunk references): later.**
5. **Missing concepts: meshes (MDAL)**, added as M26. Two further principles
   came with this answer and shape doc 02:
   - classic raster, mdim and mesh should be reimagined together, informed
     by [regular-in-what](https://github.com/hypertidy/regular-in-what) and
     [playproj](https://github.com/hypertidy/playproj);
   - raster and vector are a spectrum, and the core is organised around that
     spectrum rather than around distinct modes.
