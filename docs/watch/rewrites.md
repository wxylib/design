# Watch: rewrites of the warper and other reference-library parts

Status: living tracking note, started 2026-11-01. Checked at the monthly
landscape refresh (doc 04 section 15, row 13). Newest entry first in
section 7.
Context: [04 landscape](../04-landscape.md) sections 9 (warp) and 11
(pure-Rust alternatives); [m20](../m20-movement-crates.md) (movement
layer); [m24](../m24-foundations-hardening.md); sibling notes
[opengeos.md](opengeos.md) (terrio), [roteiro.md](roteiro.md) (formats),
[crs-coverage.md](crs-coverage.md) (CRS), [visgl.md](visgl.md) (browser
meshes).

## 1. Summary

The reference C++ library is being reimplemented piece by piece, in many
languages and by many people, mostly without coordination. The existing
watch notes follow projects; this one follows **parts**. For each part of
the reference library it lists who else rewrites that part, how it
compares to wxylib's own piece, and how mature it is, so that a new
project can be placed in one row instead of a new note.

It starts with the warper, because rwarp is wxylib's rewrite of it and
the comparison is sharpest there. Findings at the first pass:

1. **terrio is now a second full warper rewrite in Rust.** terrio 0.6.0
   (2026-10-31) has a 4.8k-line `ops/warp.rs` covering the general image
   projection transformer, the approximate transformer (0.125 px
   default), source windows per region, cutlines, geolocation arrays,
   GCP and RPC transformers, suggested output grids, the full kernel
   list including statistics kernels, and a `KernelVersion` switch for
   the 3.12 and 3.13 scale rules. It is the only rewrite at rwarp's
   scope. It lives inside the terrio crate, not as its own crate.
2. **Nothing else rewrites the whole pipeline.** The other projects
   rewrite one part (gridr: the coordinate-grid resampler; Whitebox
   `wbraster`: a reproject with five kernels; xarray-spatial: a Numba
   reproject with its own approximation; warp-rs: an affine type so far)
   or plan the output grid and call the reference warper underneath
   (odc-geo, SedonaDB).
3. **The browser rewrites converge on meshes,** not on the pixel
   pipeline: OpenLayers' triangulation, `@developmentseed/raster-reproject`
   and math.gl's inverse mesh are three versions of the approximate
   transformer for the GPU. They are tracked in [visgl.md](visgl.md) and
   listed here only by part.
4. **The useful act is comparison, not adoption.** terrio and rwarp
   both claim kernel parity with the same oracle. A shared oracle set
   (fixtures' `oracles` workflow) run against both is the cheapest
   cross-check either project can get. That is an offer for Michael to
   make, not a dependency.

## 2. Parts of the warper

Each part has a short code used in the tables. The rwarp column names the
module that holds wxylib's version.

| Code | Part | What it does | rwarp |
|---|---|---|---|
| W1 | Transformer chain | pixel to CRS to CRS to pixel, the general image projection transformer | `transform`, `crs` |
| W2 | Approximate transformer | interpolate along rows, refine where error exceeds a threshold (0.125 px) | `approx` |
| W3 | Source window | which source pixels a target region needs, with padding and retries | `source_window` |
| W4 | Output grid suggestion | default extent, resolution and size from a source and a target CRS | none (wxy-warp sets the grid) |
| W5 | Chunk planning | split the target into regions that fit memory, with per-chunk scale | `plan` (`plan_chunks`, `warp_chunks`) |
| W6 | Resampling kernels | nearest to lanczos, statistics kernels, the per-chunk scale rule | `warp` (`ResampleAlg`, `KernelScaling`) |
| W7 | Geolocation arrays | swath and curvilinear sources, inverse lookup | `geoloc_transform` (backmap) |
| W8 | Cutline and footprint | mask the target by a polygon, exact coverage | `cutline`; controlledburn-rs |
| W9 | Antimeridian and wrap | CENTER_LONG, sources crossing the seam | `transform` (`CENTER_LONG`) |
| W10 | GCP, RPC, thin plate spline | non-CRS georeferencing | `gcp_transform` (polynomial order 1-3 only) |

## 3. Inventory: full or near-full warper rewrites

| Project | Lang | Author | Version, date | Parts | Oracle | Compared to rwarp |
|---|---|---|---|---|---|---|
| [rwarp](https://github.com/hypertidy/rwarp) | Rust | hypertidy | 0.3.1, 2026-10-28 | W1-W3, W5-W9, W10 polynomial | 3.14dev oracle sets in fixtures | wxylib's own; pure Rust, no I/O, crates.io |
| [terrio](https://github.com/opengeos/terrio) `ops/warp.rs` | Rust (+ Python, wasm) | opengeos (one main author) | 0.6.0, 2026-10-31 | W1-W10 | Python parity tests against the reference library and rasterio's `WarpedVRT` | A wider scope: adds W4 (suggested grid), RPC and the warped-VRT region path. Kernel default is the 3.12 rule (rwarp tracks 3.13+). Geolocation uses an R-tree inverse lookup, not the backmap. Regions follow the warped VRT's `WarpRegionToBuffer` path. Not a separate crate; part of a 100k+ line I/O crate |
| [OxiGeo](https://github.com/cool-japan/oxigeo) `oxigeo-algorithms`, `oxigeo-gpu` | Rust | COOLJAPAN | 0.2.4, 2026-08-18 | W1, W6 (claims) | none running (doc 04 section 11) | Generated monolith. **Avoid**; mine issues for test cases |

## 4. Inventory: one part each

| Project | Lang | Version, date | Part | Status | Relation |
|---|---|---|---|---|---|
| [gridr](https://github.com/CNES/gridr) (CNES) | Rust, pyo3 | 0.7.0, 2026-10-16 | W2, W6 | active, institutional | Resampling through a target-to-source coordinate grid, full or undersampled, with masks: the approximate transformer as a data structure. Kernels nearest, linear, cubic, B-spline. Closest to bigcurve-rs; a candidate collaborator |
| [Whitebox `wbraster`](https://github.com/jblindsay/whitebox_next_gen) | Rust | 0.2.1, 2026-07-30 | W1, W4, W6, W9 | active, one author | `reproject_with_options`: nearest, bilinear, cubic, lanczos, average, min and more; antimeridian policy; parity fixtures against reference output. Exact transforms, no approximate transformer found |
| [warp-rs](https://github.com/jjcfrancisco/warp-rs) | Rust | 0.2.1, 2026-10-10 | W1 (affine only) | early: "nothing warps yet" | Arrays in, arrays out, no I/O: the same shape as rwarp. Human-written by policy |
| [rust-warp](https://github.com/jakenotjay/rust-warp) | Rust, pyo3 | 0.1.0, last commit 2026-02-28 | W1, W2, W5, W6 | quiet since February; generated code by its author's account | Inverse-mapping warp with its own projection math (UTM, Web Mercator, LCC, Albers, stereographic, sinusoidal, equirectangular), scanline approximation, five kernels, dask HighLevelGraph chunking and an xarray `.warp` accessor. Speed claims against rasterio, no parity oracle found |
| [warp-rs (ljstrnadiii)](https://github.com/ljstrnadiii/warp-rs) | Rust | 0.1.0, last commit 2026-03-01 | W1, W3, W6 | learning project, mostly generated | Not the crates.io `warp-rs`. Destination-driven reproject with chunky and planar layouts, five kernels (incl. sum), PROJ behind a feature, I/O planning in PLAN.md |
| [lazycogs](https://github.com/developmentseed/lazycogs) (Development Seed) | Python | 0.7.0, 2026-07-01 | W1, W3, W6 (nearest) | active, institutional | Lazy STAC-to-xarray over async-geotiff, obstore and rustac with no reference library; reprojection is pyproj plus numpy, nearest only. The stackstac/odc-stac pattern on wxylib's spine |
| [vaster](https://github.com/hypertidy/vaster-rs), [bigcurve-rs](https://github.com/hypertidy/bigcurve-rs) | Rust | 0.2.0; stage 2 | grid logic; W2 | hypertidy | wxylib's own movement layer (m20), listed for completeness |
| [controlledburn-rs](https://github.com/hypertidy/controlledburn-rs), [exactextract](https://github.com/isciences/exactextract) | Rust; C++ | 0.2.2; current | W8 | active | Exact coverage; rwarp's cutline footprint uses controlledburn-rs |
| [xarray-spatial](https://github.com/xarray-contrib/xarray-spatial) `reproject` | Python, Numba, CUDA | current | W1, W2, W6 | active | No reference library; Numba kernels for a few projection families, pyproj fallback; `transform_precision=0` gives exact transforms. A GPU path rwarp lacks |
| [pyresample](https://github.com/pytroll/pyresample) | Python | 1.35.0 | W7 | mature | Swath resampling (KD-tree, EWA, bucket); the reference for geolocation outside the reference library |
| [odc-geo](https://github.com/opendatacube/odc-geo) | Python | 0.5.3 | W3, W4, W5 | mature | Own `GeoBox` planning and dask chunk planning; pixels still go through the reference warper. Plan-only rewrite |
| [SedonaDB](https://github.com/apache/sedona-db) `RS_Resample` | Rust | 0.5.0 | W4 (via library) | experimental | Calls the reference warper at run time; rwarp is a candidate backend (doc 04 section 10.1) |
| OpenLayers `ol/reproj`, [`@developmentseed/raster-reproject`](https://github.com/developmentseed/deck.gl-raster), math.gl #367 | JS, TS | current | W2 as a GPU mesh | active | Browser meshes; see [visgl.md](visgl.md) |
| xESMF/ESMF, xarray-regrid | Python, Fortran | 0.9.2 | conservative weights | mature | Regridding, not warping; ESMF is the conservative oracle (m21) |

## 5. Other areas (structure for later)

Each area gets the same treatment when it is first needed: a parts table
like section 2, then the two inventory tables. Areas that already have a
note point to it instead of repeating it.

| Area | Parts (first cut) | Existing coverage |
|---|---|---|
| A. Warper | W1-W10 | this note |
| B. CRS and transforms | definitions, operation selection, datum grids, WKT/PROJJSON | [crs-coverage.md](crs-coverage.md) |
| C. Formats and drivers | TIFF/COG, HDF5/netCDF, GRIB, Zarr, LERC, COPC | [roteiro.md](roteiro.md), doc 04 section 6 |
| D. Rasterize and zonal | burn rules, all-touched, coverage weights, zonal statistics | doc 04 section 9 row controlledburn; to add |
| E. Composition | VRT, mosaic, multidimensional VRT, pipelines | doc 04 section 10.1; to add |
| F. Virtual file systems | URL schemes, range reads, chained paths | m09 section 4 |
| G. Algorithms and CLI | algorithm registry, `gdal`-style CLI, terrain, contour, polygonize | m09; [opengeos.md](opengeos.md) |
| H. Overviews and tiling | overview kernels, tile matrix sets, COG layout | to add |

## 6. Refresh

- **When.** At the monthly landscape refresh (doc 04 section 15,
  row 13). terrio is also seen weekly through [opengeos.md](opengeos.md);
  a terrio warper change found there is copied into section 7 here.
- **How.** Re-run these crates.io searches and note any new crate with a
  warper part: `reproject`, `raster warp`, `raster resample`,
  `geotransform`, `rasterize`, `regrid`. Then check each row's version.
  A new row needs: part codes, author, version and date, an oracle (or
  "none"), and one sentence relative to rwarp.
- **What is in scope.** Code that reimplements a part, in any language.
  A project that only calls the reference library is listed once, as
  plan-only or a consumer, and not followed.
- **Triggers for more than a row.** A second project adopts rwarp or
  gridr; terrio splits its warper into its own crate; any project
  publishes oracle results for W6 under the 3.13 rule. Each is a reason
  for a comparison run, not a design change.

## 7. Log

- **2026-11-01 (later).** Added rust-warp, ljstrnadiii's warp-rs and
  lazycogs from rwarp issue 1, which is closed in favour of this note.
  The shared-oracle run against terrio and rwarp (section 1 item 4) is
  planned, after rwarp's next upgrades.
- **2026-11-01.** Note started. First pass of the warper area (sections
  3 and 4). terrio 0.6.0 checked at commit 48efb49 (W1-W10 present,
  `KernelVersion` 3.12 default, R-tree geolocation). gridr 0.7.0,
  wbraster 0.2.1, warp-rs 0.2.1 read from source. xarray-spatial read
  from its documentation only; the March 2026 Numba projection work may
  sit on a feature branch *(unverified)*.
