# Watch: terrio and RustGIS (opengeos)

Status: living tracking note, started 2026-10-24. Updated by a check twice
a week (Wednesdays and Sundays, from 2026-10-29); newest entry first in
section 4. terrio is tracked as observation, not a race: its design
decisions and features are logged where they meet wxylib's stance and
plans, and wxylib's own contributors now contribute to it.
Context: [04 landscape](../04-landscape.md), sections 5.2 (terrio's CRS
engine) and 11 (pure-Rust GDAL alternatives).

Both projects come from Qiusheng Wu's opengeos org and are moving fast,
mostly through agent-written, squash-merged PRs. They are the closest
pure-Rust overlap with wxylib's scope, so this note tracks them more often
than the monthly landscape refresh does.

## 1. What each one is

| | terrio | RustGIS |
|---|---|---|
| Repo | [opengeos/terrio](https://github.com/opengeos/terrio), docs at [terrio.opengeos.org](https://terrio.opengeos.org) | [opengeos/RustGIS](https://github.com/opengeos/RustGIS), [rustgis.app](https://rustgis.app) |
| What | Pure-Rust geospatial data I/O and GDAL-style operations: rasters, vectors, point clouds | Desktop GIS (egui) with a web build, CLI, Python, an AI assistant and an MCP server |
| License | MIT | Apache-2.0 |
| Builds on | Whitebox Next Gen (`wbraster`, `wbvector`, `wbprojection`), `tiff`, `gribberish`, `geo`, arrow/parquet, netcdf-reader, hdf5-reader; GDAL as an optional backend | `geo`, `proj4rs` 0.2, egui; GeoLibre and Whitebox tools through `rustgis-geolibre`. **Does not depend on terrio** |
| CRS | `terrio-crs`, its own engine as a separate crate, no PROJ (doc 04, 5.2; coverage of wxylib's cases in [crs-coverage.md](crs-coverage.md)) | `proj4rs` |
| Surfaces | Rust crates, CLI, Python (rasterio-style `terrio.rio`, xarray), terrio-js (wasm, threads, memory64), MCP server | Desktop app, web app, CLI, Python, MCP server |

## 2. Signals to track

1. **Releases.** The cadence and what each release adds (crates.io
   `terrio`, `terrio-cli`; RustGIS GitHub releases).
2. **terrio's conformance table** (`docs/conformance.md`), especially the
   coordinate transformation and datum grid rows. These are the numbers
   behind the CRS-backend question.
3. **terrio-crs** (split out 2026-10-25): releases, the rust-proj-capability
   columns, and [crs-coverage.md](crs-coverage.md)'s table of wxylib's own
   cases, rerun at each check against terrio main.
4. **Overlap with wxylib's plan.** Virtual rasters (VRT), mosaics and
   catalogues, multidimensional arrays, warp, Zarr and GeoZarr, wasm
   builds.
5. **Reuse direction.** Does either project start using the shared spine
   (zarrs, async-tiff, object_store, proj-core)? So far neither does.
6. **Downloads and reverse dependencies**, as a check on adoption beyond
   opengeos.
7. **Design decisions that meet wxylib's stance**: virtual-first versus
   materialising, GDAL as oracle versus GDAL as backend, CLI-reflects-API,
   remote I/O (VSI) design, and the tensor and table views of data.
8. **Contributors**, including wxylib's own, and which areas they work on.

## 3. What would change a wxylib decision

- A standalone terrio CRS crate that scores well in rust-proj-capability
  would become the leading pure-Rust backend behind the CRS trait (doc 04,
  LS4 and section 5.2).
- terrio's VRT, mosaic and multidimensional work overlaps the planned
  virtual scheme (doc 03, S7) and the m-series notes. Where it matches
  GDAL, its test cases are worth borrowing.
- If terrio moved onto zarrs or async-tiff, it would become a possible
  partner rather than a parallel stack.

## 4. Log

### 2026-10-28, evening (DGGS projections in terrio-crs; RustGIS rechecked)

terrio (12 commits since the morning entry, no new crates.io release):
- **CRS:** three projections behind discrete global grids, all contributed
  by Michael Sumner: the quadrilateralized spherical cube (#359), HEALPix
  and rHEALPix (#367), and the Icosahedral Snyder Equal Area projection
  (#371). These are the projections under DGGS cell layouts, which
  gate 1 placed in wxylib as an implicit mesh, later.
- **wxylib's own CRS cases:** rerun on terrio-crs main (3c3706b); results
  byte-identical, still 34 of 35. The PROJJSON `meridian` miss remains.
- **Overlap with wxylib's plan:** `terrio validate-cog`, a GDAL-free port
  of rio-cogeo's validator (#362); TIFF chunk metadata cached per image
  level (#360); PMTiles and MBTiles pyramids and DEM colour relief streamed
  in bounded memory (#368, #363).
- **Stance:** the acknowledgements now credit GDAL and its developers
  (#370).
- **Reuse:** still no zarrs, async-tiff, object_store or proj crate.

RustGIS (first recheck since 2026-10-25): no release since v0.4.0
(2026-10-24), but 159 commits from 15 authors since then (Dominik
Strebel, Qiusheng Wu, Daniel Hofbauer, Mavrick Fitzgerald and Li-Sheng
Chou lead). Still on `proj4rs` 0.2 and `geo`, with no terrio dependency.
Points of overlap: GeoTIFFs read in place from URLs without a file name
(#1052), a Data Cubes pane with a catalogue (#683), WMS and WMTS time
dimensions on a time slider (#1100, #1106), and vector export to PMTiles
(#1006).

### 2026-10-28 (terrio fills most CRS gaps; contributors widen)

terrio (about 60 commits since 2026-10-25, no new crates.io release; still
`terrio` 0.5.0 and `terrio-crs` 0.1.0):
- **CRS:** geocentric CRSs (#286), PROJJSON parsing (#287) and writing
  (#311), IAU planetary codes (#293), native tpers and nsper (#294), the
  general oblique transformation `ob_tran` (#349) and the interrupted
  Goode homolosine (#343), both contributed by Michael Sumner, and a batch
  of CRS correctness fixes against GDAL and PROJ (#296). Work on all four
  gap areas tracked in #269 to #272 has landed on main.
- **wxylib's own CRS cases:** [crs-coverage.md](crs-coverage.md) runs 35
  cases. terrio-crs main is exact on 34, against 16 for proj4rs 0.1.10
  (what core uses) and 24 for proj4rs 0.3.0. The miss is PROJJSON for
  polar CRSs (the axis `meridian` member).
- **Overlap with wxylib's plan:**
  - remote I/O: `terrio vsi` list, copy, delete, move and sync (#302),
    streamed signed S3 uploads (#345), and cheaper remote reads (#341).
    This is the VSI ground of m09, built in-house rather than on
    object_store;
  - an optional `ndarray` view of rasters (#320), which meets the tensor
    view in the tensors-and-tables framing;
  - GeoZarr read and write (`spatial:`, `proj:`, `multiscales`, Zarr v2
    and v3) is documented in `docs/formats.md`, alongside `wxy-geozarr`;
  - raster management (overviews, create, edit, update; #304), blending
    (#346), gdal_grid and ogrlineref (#305), and windowed reads of raw
    rasters such as SRTM HGT (#342).
- **Reuse:** still no zarrs, async-tiff, object_store or proj crate.
- **Contributors:** 10 authors in the history now. Since 2026-10-25:
  Ben Dyson (CRS correctness, PROJJSON writing, GeoTIFF fixes), William
  Mark Katzenmeyer (NAVD88 geoids, point cloud heights, hexbin), Michael
  Sumner (ob_tran, igh), Roozbeh Valavi (ndarray), Alejandra Duque Ropero
  (warp nodata, shapefile rings), Mazdak Ghasemi (geoid warnings), with
  Qiusheng Wu writing about two thirds.

RustGIS: not rechecked this time.

### 2026-10-25 (trigger fired: standalone CRS crate)

terrio:
- **Section 3's first trigger fired.** After opengeos/terrio#266 (benchmark
  results and a request to split the CRS engine), the engine was extracted
  the same day as **`terrio-crs` 0.1.0** on crates.io (#274, #276, #282).
  It is MIT, builds for wasm32, and has two optional features:
  `wbprojection-fallback` (projections it does not implement natively) and
  `grid-transport` (PROJ CDN grids). terrio 0.5.0's own crate now depends on
  it, with both features on.
- **Benchmark** (rust-proj-capability, PRs #7 and #8, merged): CRS study
  71 of 93 exact natively and 74 with the fallback, against the frozen PROJ
  9.9.0 oracle. The best pure-Rust crate before was proj-core with 33.
  Projections suite: 40 of 54 exact with the fallback. The moll, wag4, wag5
  and ortho-inverse misses we reported were fixed upstream (#273). wintri
  stays as the documented `lat_1` default difference.
- **Footprint:** about 50 crates natively and 58 with the fallback (in the
  benchmark harness's tree), against 186 for terrio built without default
  features.
- **Gaps tracked upstream:** geocentric CRSs, PROJJSON, IAU codes and more
  projections (terrio #269 to #272).
- What it means for wxylib: terrio-crs is now the leading candidate for a
  pure-Rust backend behind the CRS trait (doc 04, LS4 and section 5.2). It
  would sit alongside proj4rs, not replace it yet. Trying it out belongs to
  core, so it was suggested to the planning thread; no wxylib decision has
  changed.
- Otherwise: no new release of `terrio` itself (still 0.5.0, 424
  downloads). The conformance page's CRS and grid rows are unchanged.
  terrio was archived on Zenodo, with a citation. New features: DWG and DXF
  vector interchange, footprint attributes, and CRS and precision options
  for zonal statistics and point sampling. It still does not use zarrs,
  async-tiff, object_store or any proj crate.
- Contributors: Qiusheng Wu wrote nearly all of the commits, with two
  drive-by contributors (COG overviews; an HDF5 fix for HEC-RAS files) and
  dependabot.

RustGIS:
- **v0.4.0** (2026-10-24). Since then: QGIS project and style import,
  ellipsoidal buffers and Spatial Join distances, raster-stack trends, a
  data-cube catalog, a PMTiles helper and Polish. It was also archived on
  Zenodo.
- It still uses `proj4rs` 0.2 (with `aeqd`) for CRS, not terrio-crs.
  Moving to terrio-crs would make it the first shared core between the two
  opengeos projects. Watch for that.

### 2026-10-24 (baseline catch-up since 0.3.2)

terrio:
- 0.3.2 (2026-10-20) to **0.5.0** (2026-10-24): releases 0.4.0, 0.4.1 and
  0.4.2 came in between, so five releases in five days. Commits went from
  121 to 202. The repo now holds about 136k lines of Rust, about 10.8k of
  them CRS code, and it has `AGENTS.md` for coding agents.
- **CRS:** CRS-to-CRS operations are now chosen as PROJ lists them,
  including chains through several intermediate datums. It added
  vertical-to-vertical transformations, point motion between coordinate
  epochs, grids read from the PROJ CDN by HTTP range requests, Robinson and
  ten more world projections ported from PROJ, ellipsoidal eqc, sinu, gnom
  and others, and a check of every PROJ projection as both a PROJ string
  and WKT. Its reference is now PROJ 9.8.1.
- **Conformance, as published:**

  | Row | Cases | Identical | Within tolerance | Different |
  |---|---:|---:|---:|---:|
  | Coordinate transformations | 19,017 | 19,002 | 13 | 2 |
  | Datum grids, geoids, epochs | 19,253 | 19,223 | 28 | 2 |

  At 0.3.2 the coordinate transformation rows (forward, inverse and CRS to
  CRS, 19,003 cases) had 74 within tolerance and 19 different, and the grid
  row had 115 and 29.
- **The CRS engine is still inside the `terrio` crate.** There is no
  standalone crate yet, and no stated plan for one in ROADMAP.md.
- **New scope that overlaps wxylib:**
  - richer VRTs, lazy pansharpened VRTs and indexed raster catalogs (GTI
    style);
  - "native multidimensional scientific array APIs" and Zarr arrays with
    more than three dimensions;
  - warping of scientific swaths with geolocation arrays (R3), RPC
    transformers, and overview selection when warping;
  - a pure-Rust GRIB1/GRIB2 driver (on `gribberish`, CCSDS only) and
    STACTA;
  - wasm threads, memory64 (over 4 GB) and a smaller core build.
- Also new: viewshed, contours, zonal statistics, vector SQL and topology,
  nodata filling, a rio command line, PDAL-style point cloud filters, and
  AUR and Fedora COPR packages. The roadmap says no prebuilt wheels will
  bundle GDAL. A "practical GDAL parity tracker" was marked complete on
  2026-10-24.
- **Reuse:** it added `geo`, `rstar` and `gribberish`. It still does not
  use zarrs, async-tiff, object_store or any proj crate.

RustGIS:
- v0.1.0 and v0.2.0 were covered by It's FOSS on 2026-10-13
  ([article](https://itsfoss.com/rustgis-open-source-gis-tool/)). The
  workspace is at 0.3.0, and issue and PR numbers passed 840 by
  2026-10-24.
- It is an egui desktop GIS with a web app, CLI, Python, an AI assistant
  pane and an MCP server. It offers over 1,000 GeoLibre and Whitebox tools
  through `opengeos/geolibre-rust`, and SQL through DuckDB Spatial.
- **It uses `proj4rs` 0.2 for CRS, not terrio's engine,** and it does not
  depend on terrio. The two opengeos projects do not share a CRS or I/O
  core yet.
- Relevance to wxylib: low for the core, and on the same theme as Mapsuke
  (doc 04, 10.4): agents driving a GIS through an MCP server and tools.
