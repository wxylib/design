# 05: Pain points in GDAL, R and Python, and where wxylib answers them

Status: draft for gate 5, 2026-10-16
Builds on: [02 data model](02-data-model.md) (the R0 to R6 spectrum),
[03 architecture](03-architecture.md) (stages S1 to S8),
[04 landscape](04-landscape.md).

## 1. Why a pain point catalogue

Docs 01 to 04 ask what GDAL contains and what the field already offers.
This one asks what hurts. Each pain point is a feature request in disguise:
if wxylib is built so that the pain cannot arise, that is a design property
worth stating; if it can only be fixed by building something, that is a
stage or a gate criterion.

- Get: stage gates tied to real failures rather than to feature lists; a
  place to send the next "why is this hard" moment.
- Cost: one more document to keep current; some entries are GDAL bugs that
  wxylib only needs to avoid, not fix.
- Without it: the roadmap is shaped by what GDAL has, not by where it
  falls short, and wxylib risks rebuilding the same weak spots.

## 2. How to read the tables

Each entry has an id, the pain, its source, and where it lands.

- Source: **M** from Michael's working notes and messages in the project
  thread; **C** Claude's seed list (general knowledge, not checked against
  specific issues, see section 13).
- Lands in: a rung (R0 to R6, doc 02), a stage (S1 to S8, doc 03), a crate,
  or a **principle** (a design property, no stage). **Upstream** means the
  fix belongs in GDAL and Michael is pursuing it there; wxylib records the
  design so the two stay consistent.

## 3. Warper and extents

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| W1 | Extent heuristics. `GDALSuggestedWarpOutput` densifies edges and hits singularities at exactly the boundary that matters. gdalwarp clamps latitude for Mercator but `AutoCreateWarpedVRT` does not. Per-projection special cases are whack-a-mole. | M S4 `wxy-warp` (done): the target grid is already explicit (`GridSpec`: extent, size, CRS). Keep it so: suggesting one is a separate, optional helper, anchored at the centre where the transform is well behaved, with an ncol/nrow budget and resolution from the local scale factor. No per-projection cases. |
| W2 | No plain kernel when downsampling. The kernel always scales its support to the source/destination ratio and nothing turns it off; `-ovr NONE` only picks the band read. Overview choice is baked into gdalwarp and picks one level for the whole output. rwarp matches GDAL bit for bit at 1:1; this scaling is the only divergence. | M | S5 `wxy-resample`: support scaling is a parameter (scaled or plain), and overview choice is part of the plan, per output tile, not one level for the whole output. |
| W3 | Low-power mdim warp. mdim to classic (`AsClassicDataset`) then the warper works, but "warp this time x lat x lon store slice by slice" is not a first-class operation, and the completeness of `GDALMDArray::GetResampled()` is unclear. | M S4 (done) already plans once for a 2D or 3D domain with one leading dim, but reads that dim whole. Next: any number of non-spatial dims, carried through and streamed slice by slice under the one plan (section 12). |
| W4 | Geolocation arrays (R3) are side metadata (RFC 4). The backmap inversion is approximate and struggles at poles, the antimeridian and swath edges. | C | R3 as a first-class `Mapping`; curvilinear warp is "later" in doc 03 and is a candidate to move earlier (section 12). |
| W5 | Warp planning is opaque: source windows from edge sampling can miss poles, and there is no API to ask which source tiles a view needs. | C | rwarp's planner exposed as a plan value (S2 plan, fetch, decode; S4). |
| W6 | Longitude 0..360 versus -180..180 and antimeridian crossing need ad hoc options per tool. | C | Wrap as a property of the mapping or frame in `wxy-domain`, honoured by the planner. |

## 4. Multidimensional

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| D1 | Chunk location. `gdal mdim get-refs` (GDAL PR 14677) lists per-chunk path, offset, size and info as a no-geometry vector layer; rework and rename pending. | M, upstream Already aligned in principle: [mdim-refs/0.2](../specs/mdim-refs-0.2.md) takes its column names from the get-refs draft, and the [m02 pilot](m02-pilot-mdimrefs.md) reads that table through `wxy-virtual`. Keep `wxy-virtual`'s own scanner rows in the same columns, so GDAL's output, mdim-refs and wxylib's table are one shape. |
| D2 | GeoTIFF is not in mdim. GTiff has no mdim capability, and a mdim VRT over GeoTIFFs fails `GetRawBlockInfo`, although TileOffsets and TileByteCounts already are the chunk manifest. "Virtualizing GeoTIFF" is wasteful: a tiled TIFF is already virtualized. | M, upstream | `wxy-tiff` already serves tiles as a `ChunkSource` straight from the tile index, and is the native-reader exception in A6. Writing TIFF refs to Icechunk (S3b) is for composition and versioning, not a prerequisite for reading. See section 12. |
| D3 | 2D to mdim promotion. A `vrt://` decorator that promotes a 2D raster to a singleton mdim slice feeding `gdal mdim mosaic`, or a `gdal mdim stack` with gdalbuildvrt's validation conventions (check all, skip with warning, `--strict`, explicit allow flags). | M, upstream | No promotion step exists in wxylib: a 2D raster is a `Domain` with two dims, and adding a singleton dim is a domain operation. Stacking is S7's combine along a new dim, adopting the same validation conventions. |
| D4 | `mdim mosaic` breaks on dims without an indexing variable (CF `bnds`). It needs a pass-through state (size check only), not synthetic start and increment values. | M, upstream | A dim with no positions is an R0 dim in `wxy-domain`: legal, carried through, checked by size. Never synthesise coordinates. |
| D5 | Subset by coordinate value but not by index (`-isubset`); no reusable `GDALDimension::GetIndexForValue()`, the lookup is inline in translate code. | M, upstream | Both are domain operations in S1, with value-to-index as a public function on every mapping rung. |
| D6 | `gdalmdiminfo --detailed` has no default limit and can attempt enormous dumps. | M, upstream | `wxy info` limits per dimension by default, with an opt-out. |
| D7 | Rank-blind options: bare `ARRAY:BLOCKSIZE` hits 1D coordinate arrays; the workaround is `ARRAY:IF(DIM=3):BLOCKSIZE=...`. | M, upstream | Options are addressed to arrays by name or role, as typed values, never by string conditions. |
| D8 | Classic has no rectilinear (R2). Near-regular float32 axes give a slightly wrong geotransform or a silent fallback. | C | S1 normalisation with a report (done). |
| D9 | Cell versus point (half pixel) conventions differ by driver. | C | `CellConvention` in S1 (done). |
| D10 | Subdataset connection strings (`NETCDF:"f.nc":var`) and separate classic and mdim open modes. | C | One `Collection` per source (S3). |

## 5. Virtual composition

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| V1 | No VRT write for vector. The OGR VRT driver is read only and is handcrafted (ogrmerge style). A dsn provenance field is only possible through `SrcSQL`, which loses fast paths (feature count, extent, filter pushdown). | M, upstream | S7 covers R6: select, remap and combine apply to feature collections too, and the library writes the description. Provenance is a column the scheme adds, not SQL, so pushdown survives. |
| V2 | Blank-grid VRT: `vrt://` with an empty source, so the translate vocabulary (`outsize`, `a_ullr`, `a_gt`, `a_srs`, `ot`) describes a sourceless grid. | M, upstream | Native in wxylib: a `Domain` with no `Field` is the base type (S1). The CLI should accept the same vocabulary to build one. |
| V3 | Calc-derived bands do not expose source overviews, so the warper reads at native resolution and appears to hang (multi-band calc over PMTiles). Workaround: `overview add` as a pipeline step. | M, upstream | A derived field is a lazy expression over sources, and its resolution levels are those of its inputs. The planner chooses a level through the expression (S5 plus S7). |
| V4 | STACIT is 2D and bands only, not mdim. | M, upstream | A catalogue becomes a `Collection` with a time dim (S7, later). |
| V5 | Classic VRT and mdim VRT are separate XML dialects; a warped VRT cannot be mdim. | C | S7: one scheme for classic, mdim, mesh and features. |

## 6. Features and meshes

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| F1 | No easy transition between vector features and mesh forms. GEOS does it under the hood (noding into a planar graph for overlay, triangulation, polygonize), then discards the topology and returns simple features; the next call rebuilds it. sf, terra and shapely expose only the features. hypertidy/silicate and anglr exist because of this (PATH, SC, TRI models). | M | The R6 to R5 move from doc 02 section 3 as an explicit operation whose result is kept: features to a shared-vertex mesh (deduplicated vertices, noded edges, feature ids as labels) and back. Topology module in S8, with silicate's models as the reference. |
| F2 | Meshes live in MDAL, outside GDAL; DGGS nowhere. | C | S8 and later. |

## 7. Extraction

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| E1 | Planned, vectorised pixel extraction. Zonal statistics presuppose efficient value extraction planned by block across a mosaic of files. The GDAL target is a narrow inner-loop feature informed by an external planner. | M, upstream | A new candidate stage after S4: points or features to chunk keys, grouped by chunk, fetched once, sampled. It is the same plan, fetch, decode seam as S2, and wxylib's planner can serve as the external planner for GDAL too. |

## 8. Footguns, and the principles they suggest

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| B1 | COG driver relative tolerance `fabs(a - b) < 1e-10 * fabs(a)` degenerates when an extent coordinate is exactly 0, forcing a warp and silently dropping `OVERVIEWS=FORCE_USE_EXISTING`. | M, upstream | Principle: grid comparisons use absolute plus relative tolerance in `wxy-domain`; a fixture with a zero extent coordinate. |
| B2 | Parquet writer fails on coded field domains with a null description; workaround is a FlatGeobuf hop. | M, upstream | A fixture for when features (GeoArrow, GeoParquet) arrive. |
| B3 | Config precedence. gdalrc outranks env vars, so a global `AWS_NO_SIGN_REQUEST` silently suppressed /vsis3 write signing. In 3.13 the environment is snapshotted at init, so env vars set after load are invisible. | M | Principle: no global state. Options are explicit values per source or call; anything read from the environment is read when asked, and its origin is reported. Proposed as decision A8 (section 12). |
| B4 | Silent HTML: `/vsicurl` gives no hint when a URL returns an HTML page rather than dataset bytes (cloud-drive share links). | M | Principle: a source reports what it received (content type, first bytes) when they do not match what was expected. In `wxy-source`. |
| B5 | Dataset handles are not thread safe or serialisable; I/O is sync with limited multi-range async. | C | Async `ChunkSource`, plans as plain data (S2). |

## 9. R and Python

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| L1 | sf, terra, stars, vapour, gdalraster each link their own GDAL; version and driver skew in one session. Python's rasterio and fiona wheels bundle GDAL and clash with conda or osgeo GDAL. | C | Bindings with no system GDAL (S6). |
| L2 | terra's `SpatRaster` is an external pointer: opaque, not serialisable, awkward in parallel. Dask with GDAL: handles do not pickle, per-worker reopen. | C | Domains and plans as plain values that cross the binding (S6). |
| L3 | No common lightweight "grid without data" type in R; vaster, vapour and others exist to fill it. | C | `wxy-domain` (S1), exposed to R and Python. |
| L4 | Regridding is fragmented: rioxarray reproject for grids, pyresample or satpy for swaths, xESMF for curvilinear, stars for both but slowly. | C | One warp across R1 to R3 (S4 plus W4). |
| L5 | ncdf4, RNetCDF, tidync and GDAL give different georeferencing for the same file; xarray CRS conventions compete (rioxarray, odc-geo, GeoZarr). | C | One model plus the GeoZarr conventions crate (gate 4). |

## 10. Distribution and process

| Id | Pain | Src | Lands in |
|----|------|-----|----------|
| P1 | Static builds and R CI are a precursor for R, wheel and FaaS distribution (gdal-r-ci). | M | Pure Rust core with wasm builds (doc 03 section 5) avoids the problem for wxylib; gdal-r-ci stays the route for GDAL itself. |
| P2 | Contribution friction in GDAL: C++ fluency, review expectations, the LLM-code policy. Plan: fund GDAL with a scoped wishlist and a pre-review checker. | M | wxylib can prototype the funding bundle. Its pieces already exist here in another form: chunk refs (D1, `wxy-virtual`), GeoTIFF block info through a chunked model (D2, `wxy-tiff`), 2D to mdim (D3, `wxy-domain`), index subsetting (D5). A working reference makes each GDAL item easier to justify on its own. |

## 11. Stretch: presentation and the map as a document

These are not stages. They belong with the musings (m01 downstream UX) until
a numbered document picks them up.

- **X1. Presentation on raw data (M).** No raster format carries the image
  scaling (stretch, palette, gamma, band-to-RGB mapping, nodata styling)
  alongside untouched raw values, applied at read time. It is baked into a
  rendered copy, losing the data, or lost in a sidecar. Scale and offset
  are about units, not presentation. A wxylib reading: presentation is a
  separate, optional attribute of a `Field`, stored as a Zarr convention
  next to `spatial:` and `proj:`, never applied by a reader unless asked.
  A natural thing to propose to the GeoZarr conventions work.
- **X2. A real map format (M).** One sendable thing holding presentation,
  links to sources, derived layers, view states (CRS, extent, zoom) and
  accoutrements (graticule, scale bar, legend, insets), that the recipient
  can open, explore and modify. Recipe, not payload: it is S7's virtual
  description extended with views and presentation. A candidate m03.

## 12. Findings for the roadmap

These change doc 03. They are sent to the planning thread, which owns 03;
nothing here edits it.

1. **An S4b: mdim warp (W3), and explicit targets kept (W1).** S4 is done
   for 2D and one leading dim read whole. S4b carries any number of
   non-spatial dims and streams them slice by slice under one plan, so a
   time x depth x lat x lon store warps without loading it. Extent
   suggestion, if added, is a separate helper.
   Get: Michael's headline pain answered while the warp code is fresh.
   Cost: chunk-aware slicing in `wxy-warp`. Without it: wxylib repeats
   GDAL's slice-by-hand mdim warp.
2. **S5 adds a plain/scaled kernel switch, per-tile overview choice, and
   overviews through derived fields (W2, V3).** Get: rwarp's one known
   divergence becomes an option rather than a bug. Cost: harder bit
   identity tests. Without it: the hang in V3 and the one-level overview
   choice carry over.
3. **Curvilinear (R3) warp moves from "later" to just after S5 (W4, L4).**
   Get: the most repeated pain across GDAL, R and Python. Cost: the inverse
   mapping design comes sooner. Without it: swaths and model grids stay on
   pyresample, xESMF and geolocation arrays.
4. **Decision A8: no global state (B3, B4).** Options are explicit values;
   environment reads happen on request and report their origin; sources
   report unexpected content. Get: the same call behaves the same in every
   process. Cost: a little more ceremony at the call site. Without it:
   GDAL's config precedence problem, again.
5. **S7 covers features and mesh, written by the library, with
   gdalbuildvrt-style validation for combine (V1, V5, D3).**
6. **One reference-table shape (D1).** `wxy-virtual` scanner rows use the
   mdim-refs/get-refs columns; the m02 pilot is the trial.
7. **TIFF stays read natively; Icechunk refs for TIFF are optional (D2).**
   A clarification of A6 and S3b, not a reversal.
8. **A new candidate stage after S4: planned extraction (E1).**

## 13. Not verified

The C entries come from general knowledge of the stacks and have not been
checked against specific issues. The M entries are Michael's own and are
taken as stated. GDAL PR 14677 and the 3.13 environment snapshot are as
reported in Michael's notes.

## 14. Questions for gate 5

1. Add S4b, mdim warp streamed under one plan (finding 1)? Recommended:
   yes, next after S5 or before it if you want it sooner.
2. Move curvilinear warp to just after S5 (finding 3)? Recommended: yes.
3. Add planned extraction as a stage after S4 (E1)? Recommended: yes, as a
   small stage on the existing seam.
4. Should overlay and similar algorithms run on the kept mesh form (F1), or
   is the mesh only a conversion target at first? Recommended: conversion
   first, algorithms on it once S8's topology module exists.
5. Presentation and the map format (section 11): an m03 musing now, or
   leave until S7? Recommended: m03 now, since it shapes S7's description.
