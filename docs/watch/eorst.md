# Watch: EORST and rss_core (JRSRP)

Status: tracking note, 2026-11-11, for `eorst` 1.0.1 (2026-05-13) and
`rss_core` 0.6.0 (2026-05-29) as published on crates.io, plus the
author's public GDAL and Rust contributions found on GitHub. Checked at
the monthly landscape refresh with [rewrites.md](rewrites.md).
Author: Leonardo (Leo) Hardtke, Joint Remote Sensing Research Program
(JRSRP), Queensland Department of the Environment, Tourism, Science and
Innovation. GitHub and crates.io login `geohardtke` (the crates.io
publisher of both crates; matching it to the person is an inference from
the crate metadata, the FOSS4G 2025 workshop and the This Week in Rust
entries).
Sources: crates.io sources of both crates (read in full for module
layout, `Cargo.toml`, README and CHANGELOG), GitHub commit, PR and issue
search for `geohardtke`, the public `gitlab.com/jrsrp/foss4g_2025`
repository, the georust/gdal CHANGES.md. Licence: LGPL-3.0-or-later
since 0.2.0 (0.1.x was MIT OR Apache-2.0), so nothing here copies code.
Context: [m20](../m20-movement-crates.md) (rwarp, controlledburn,
bigcurve), [m23](../m23-byte-ref-harvesting.md),
[m25](../m25-vrt-engine.md), [m27](../m27-oracle-harness.md),
[m26](../m26-bindings-on-rust.md).

## 1. Summary

1. **EORST is a GDAL-backed block-processing toolkit for satellite time
   series, used in production by a state agency.** A `RasterDataset` is
   built from files or a STAC query, aligned onto one grid, cut into
   blocks with optional overlap, and a user worker
   (`Fn(&RasterDataBlock<T>) -> Result<Array4<U>>`, axes time, layer,
   row, column) runs over the blocks with rayon. Results go straight to
   one GeoTIFF or COG through a parallel windowed writer. Around that sit
   point sampling, rasterisation, zonal histograms to Parquet (polars),
   LightGBM classification and OpenCV filters. About 8.6k lines.
2. **`rss_core` is the catalogue half.** It queries STAC (Digital Earth
   Australia, Element84, Planetary Computer) and a PostgreSQL metadata
   database, maps canonical band names across providers (`red` to
   `nbart_red` for DEA, `band4` elsewhere), reads remote scenes through
   `/vsis3/` and `/vsicurl/` or downloads them into a file cache, and
   parses the Queensland QVF filename convention. Optional pyo3
   bindings. About 6k lines.
3. **Alignment and mosaicking are GDAL subprocesses.** The builder warps
   every source to the target EPSG, extent and resolution by spawning
   `gdalwarp` into temporary VRTs, mosaics with `gdalbuildvrt`, and
   writes single-band VRT XML by hand. The 1.0 rewrite removed the
   block-file and `gdal_translate` round trip on output (about 2x faster,
   about 17% faster than a rioxarray baseline, per the CHANGELOG), but
   the input side still shells out.
4. **It already uses the wxylib spine for one path.** `async_io` reads
   DEA public COGs from S3 with async-tiff 0.3 and object_store 0.13 in
   place of GDAL VSI, and `rss_core` carries a benchmark of download
   versus remote read. The same crates sit under wxy's COG reader and
   refharvest.
5. **The author was an early georust/gdal contributor, including the
   first multidimensional (MDArray) attempt.** Raster creation options
   (#193, in 0.11), `OGR_L_SetFeature` (#264, in 0.12), prebuilt GDAL
   3.4 bindings (#231) and two MDArray branches (#233, #287, closed;
   the MDArray API landed as #273). Issues raised: concurrent read and
   write (#102, 2020), "multidimensional raster data model not yet
   supported" (#232), GDAL compressed metadata (OSGeo/gdal#4292),
   GDAL vector geometries in polars (pola-rs/polars#3208, 2022).
6. **Teaching and outreach in Rust for EO.** FOSS4G 2025 (Auckland)
   workshop "Oxidize to Decarbonize", built on a Nix dev environment
   (Rust, evcxr Jupyter kernel, Python GDAL, QGIS); EORST blog posts
   "Getting Started with Geospatial Rust" and "End-to-End Geospatial
   Processing with EORST", listed in This Week in Rust (2026-05-13).
   Also PRs and issues on the Rust LightGBM bindings (lightgbm-rs,
   lightgbm3-rs) and a 2025 Planetary Computer Landsat mask issue.

No GDAL C++ commits by this login were found. The crate repository
field points at `gitlab.com/jrsrp/sys/eors_workspace`, which the GitLab
API does not show publicly (private or moved); the crate sources,
docs.rs and the blog are public. Other public JRSRP repositories
(`asyncog` async COG reads in Python, `raster_mosaic` HPC warp-and-COG
pipeline, `eo-history` lineage metadata, `gdal_python_binaries` wheels)
are mostly by another JRSRP author and are listed here only as the
group's context.

## 2. Pieces and where they meet wxylib

| Piece | What it does | Nearest wxylib part | Relation |
|-------|--------------|---------------------|----------|
| `RasterDatasetBuilder` alignment | warp each source to target EPSG, `-te`, `-tr` via `gdalwarp` temp VRTs | rwarp planner + kernels; `wxy warp` | **swap candidate**: the in-process rwarp path replaces the subprocess, with GDAL-matched kernels and the oracle sets as proof |
| block + overlap iteration | fixed blocks, overlap then trim (`trimm_array3_asymmetric`) for filters | `rwarp::plan`, m31 view chunk planner | **compare**: their block/overlap is a chunk plan with a halo; ours has none yet for focal ops |
| `ParallelGeoTiffWriter`, `translate_to_cog` | mutex-guarded GDAL dataset, parallel windowed writes, COG via GDAL | M12 writer gap (roteiro-gis `geotiff-writer` candidate) | **shared gap**: a pure-Rust parallel COG writer would serve both |
| `async_io` | async-tiff + object_store read of DEA S3 COGs, DEA bucket and region hard-wired | wxy COG reader, refharvest | **same spine**; a natural first shared test |
| `rss_core` STAC + band mapping | canonical names across providers, remote or cached reads | rustac (adopt), m29 name mapping | **align**: their YAML product registry is a worked name-mapping table |
| DEA Sentinel-2 time stacks | per-tile, per-date COGs | GHRSST COG store, m23 harvesting | **byte-ref candidate**: one refs table per MGRS tile replaces repeated header reads |
| `rasterize`, `zonal_histograms_*` | GDAL burn, per-zone histograms to Parquet | `wxy zonal`, controlledburn-rs coverage weights | **offer**: exact coverage weights for polygon zones |
| `extract` point sampling | block-wise lookup of point values | `wxy points` | **compare** outputs on the same COGs |
| hand-written VRT XML | glue between steps | `vrt-model` (core), m25 | **use**: model-built VRTs instead of string templates |
| `static-gdal` feature (`gdal-src`), Nix env | GDAL packaging for Rust builds | images repo, m26 packaging | **share notes** |
| georust/gdal MDArray history | early mdim wrapper attempt | mdim.vrt, GDAL xarray backend | **context**: shared interest in mdim from Rust |

## 3. What do we get, what does it cost, what if we didn't

- **Get.** A production consumer with real Australian EO workloads (DEA
  Sentinel-2 and Landsat, Queensland state mapping such as Spatial
  BioCondition) that exercises exactly the pieces in the movement layer:
  warp to a common grid, burn, zonal, sample. EORST's subprocess calls
  are a concrete, bounded list of places where rwarp, controlledburn-rs
  and `vrt-model` could go in, each checkable against the GDAL result
  EORST already produces. That is commit criterion work done on someone
  else's data.
- **Cost.** Time to read their private workspace if offered, and care
  over licence boundaries: EORST is LGPL-3.0-or-later and wxylib is
  MIT OR Apache-2.0, so EORST may depend on our crates freely, but we do
  not copy from EORST. A dependency from EORST on rwarp also means
  keeping rwarp's API steady for an outside user, which m20 already
  plans for.
- **If we didn't.** EORST keeps shelling out to `gdalwarp` and both
  projects maintain a separate async COG path and block planner. Nothing
  breaks; we just miss the nearest outside user of the layer below
  wxylib.

## 4. Talking points

1. **Warp in process.** Would rwarp (GDAL-matching kernels, planner,
   `--dry-run` style plans) replace the `gdalwarp` temp-VRT step in the
   builder? Offer to run their alignment cases through the fixtures
   oracle sets and report differences.
2. **async-tiff path.** How does `get_remote` (GDAL VSI) compare with
   the async-tiff path on DEA in their benchmark? Is async-tiff meeting
   their needs (predictors, masks, overviews)? wxylib has wxy-predictor
   and the same object_store setup; a shared DEA case is easy to add.
3. **Byte refs for DEA tiles.** Would a per-tile refs table (one row per
   chunk across dates, as for GHRSST) cut their STAC-then-open cost? It
   is a direct test of the m23 harvester on a second COG collection.
4. **Zonal with coverage weights.** Their zonal histograms count whole
   pixels; controlledburn-rs gives exact fractions with no GDAL. Do
   their condition-mapping zones need partial-pixel weights?
5. **Block plans with halos.** Their overlap-and-trim for focal filters
   is a chunk plan wxylib does not yet have. Compare with m31 and ask
   which overlap rules they found they needed.
6. **COG writer.** Both projects write COGs through GDAL. A pure-Rust
   parallel COG writer is a shared gap; ask what properties they rely on
   (ZSTD, predictor, overviews, tags).
7. **MDArray from Rust.** His 2021 georust/gdal MDArray branches predate
   the merged API. Ask what he would want from mdim in Rust now, and
   whether mdim.vrt or virtual Zarr views of time stacks would fit their
   time-series model.
8. **Teaching material.** The FOSS4G Nix environment and blog posts are
   a good model for wxylib tutorials; ask about reuse and cross-linking.
9. **Repository access.** Is `jrsrp/sys/eors_workspace` meant to be
   public? A public repo would let wxylib list EORST as a downstream
   user and run CI against it.

## 5. Possible collaboration, ranked

1. rwarp as EORST's alignment step, checked against their current GDAL
   output (largest overlap, smallest change on their side).
2. A shared DEA Sentinel-2 test case on the async-tiff + object_store
   path, added to fixtures and their benchmark.
3. controlledburn-rs weights in their zonal statistics.
4. A refs-table trial for one MGRS tile time stack.
5. Shared COG writer requirements feeding the M12 writer choice.

## 6. Log

- 2026-11-11: first note (eorst 1.0.1, rss_core 0.6.0).
