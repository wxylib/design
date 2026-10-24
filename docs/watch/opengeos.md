# Watch: terrio and RustGIS (opengeos)

Status: living tracking note, started 2026-10-24. Updated by a weekly check;
newest entry first in section 4.
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
| CRS | Its own engine, no PROJ (doc 04, 5.2) | `proj4rs` |
| Surfaces | Rust crates, CLI, Python (rasterio-style `terrio.rio`, xarray), terrio-js (wasm, threads, memory64), MCP server | Desktop app, web app, CLI, Python, MCP server |

## 2. Signals to track

1. **Releases.** The cadence and what each release adds (crates.io
   `terrio`, `terrio-cli`; RustGIS GitHub releases).
2. **terrio's conformance table** (`docs/conformance.md`), especially the
   coordinate transformation and datum grid rows. These are the numbers
   behind the CRS-backend question.
3. **Whether the CRS engine is split out** as its own crate. Michael has
   asked its authors about their PROJ stance. If it is split out, add it
   to the rust-proj-capability fixtures.
4. **Overlap with wxylib's plan.** Virtual rasters (VRT), mosaics and
   catalogues, multidimensional arrays, warp, Zarr and GeoZarr, wasm
   builds.
5. **Reuse direction.** Does either project start using the shared spine
   (zarrs, async-tiff, object_store, proj-core)? So far neither does.
6. **Downloads and reverse dependencies**, as a check on adoption beyond
   opengeos.

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
