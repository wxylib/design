# m31: A view-to-chunk planner for browser viewers

Status: musing, 2026-11-07. Scopes one module that answers, for a view in
any CRS, which chunks at which level of a source grid the view needs,
with a thin Zarr viewer on top to show it. Based on hypertidy/rwarp at
`56d55b4` (`rwarp::source_window`, `rwarp::plan`, `rwarp-wasm`),
wxylib/core at main (`wxy_warp::choose_overview`, `wxy-zarr`,
`wxy-refs`), wxylib/web at main, hypertidy/wgis at `25cdce2`
(`src/core/source.ts` `planFetch`), mdsumner/ortho-cog-viewer at
`c35b303`, deck.gl-raster 0.9.0 and its PR #794, gridlook 1.6.1 (README
and changelog only) and the playproj `fourd.html` page (page and main
script only). Builds on doc 04 lesson L4 (browser reprojection has
converged on adaptive meshes), m20 (the movement layer), m25 (VRT in the
browser), m28 (output-grid defaults) and the visgl watch note.
Measurements: [measurements/m31-view-plan](../measurements/m31-view-plan/README.md).

## Summary

The question: the browser viewers that read Zarr and COG (deck.gl-raster,
zarr-layer, gridlook, the mesh viewers, the playproj pages) all read
chunks with the same reader (zarrita or geotiff.js) and each decides on
its own which chunks to fetch. Should wxylib build another viewer, or the
piece they share?

- **Build the planner, not a viewer.** One function: view (CRS, extent,
  screen size) plus source description (CRS, levels, chunk grid per
  level) in; a list of (level, chunk) keys with priorities out. No I/O,
  no rendering. It lives beside `rwarp::source_window` and ships in
  `rwarp-wasm`, so any viewer can call it from JS.
- **Plan per screen region, not per view.** The rule the mesh viewers use
  (one source box, one level from the mean scale) fetches 5.6 times the
  bytes of a per-region plan for a polar view of a global grid, and 8.5
  times for a lon/lat view across the antimeridian, while serving no
  pixel better (section 4).
- **Source layout matters more than the planner.** With per-tile
  planning, having overview levels at all cuts the bytes 49 times for the
  globe view and 17 times for the polar view (3.6 times across the seam,
  none for a city-sized view); with levels, the planner cuts 1.2 to 8.5
  times more. A virtual store over netCDF
  files with no overviews (BRAN) cannot be made fast by planning alone.
  Reduced copies are a store question, kept out of this module.
- **A thin viewer shows it.** `zarr.html` in wxylib/web: one Zarr or COG
  source, three views (globe, polar, lon/lat), the plan drawn over the
  map with its byte count, and the same view planned by the single-box
  rule beside it.
- **The lessons travel with the code.** The pole, seam, horizon and
  local-scale cases that the mesh viewers learned become the planner's
  test cases, which other projects can run against their own planners.

## 1. The problem

A viewer showing a raster in a CRS other than the raster's own has to
decide, every time the view changes, which source chunks to fetch and at
which resolution level. This is the warper's source-window question
(GDAL's `ComputeSourceWindow` with `-ovr AUTO`) asked for a screen, and it
fails in the same places:

- **A bounding box of a curved footprint** over-covers. Across the
  antimeridian a lon/lat box spans the whole width; at a pole it spans all
  longitudes.
- **One scale for the whole view** fits nowhere. An azimuthal view is
  finest at its centre and coarsest at its rim; a polar view of a lon/lat
  grid needs a few longitudes near the pole and many at the rim.
- **Points past the horizon or outside the CRS's domain** return garbage
  or nothing, and a single bad point can wreck a min or max.

Each viewer solves these separately, with different results, and the
fixes do not travel.

## 2. What exists

| Project | Chunk and level choice | Notes |
|---|---|---|
| wgis, ortho-cog-viewer (`planFetch`) | One source box from the visible mesh vertices, one level from the mean source units per screen pixel times 0.7, then coarser until the texture fits a size cap | One texture per view; the comment in the code says the estimate is an average and the centre of an azimuthal view is finer than its rim |
| deck.gl-raster 0.9.0 | deck.gl tile traversal in the view (Web Mercator or globe), each tile reprojected by an adaptive mesh refined on error in output pixels | Chunk choice follows the view's tile pyramid. PR #794 (ECMWF forecast on the globe) reads about 1.5 GB over about 4 minutes for its first view, 558 tiles of 8 x 8 degrees, per its own description |
| gridlook 1.6.1 | Not verified (source not read). Changelog lists caching, HEALPix levels, regular, curvilinear, reduced Gaussian and UGRID grids | three.js with its own shaders, zarrita 0.7.5, icechunk-js 0.6.0 |
| playproj `fourd.html` | Reads a box of the source at every level to a chosen depth, with read-ahead of three time steps | three.js, zarrita 0.7.5, icechunk-js 0.6.0, proj4 |
| GDAL warper | Inverse source window per output chunk (`ComputeSourceWindow`: densified edges, grid fallback, padding, antimeridian snap), one overview for the whole warp (`-ovr AUTO`) | Exact, per chunk, but one level |
| rwarp | `source_window::compute_source_window` (GDAL's algorithm as a pure function of a transformer), `plan::plan_chunks` (gdalwarp's chunk splitting) | No I/O, in `rwarp-wasm` already for the warp |
| wxy-warp | `choose_overview` (gdalwarp's `-ovr` rules) | One level per warp |

Every piece needed is already in rwarp or wxy-warp; what no project has is
the per-region level and chunk list for a screen, as a callable function.

## 3. The module

### 3.1 Inputs

- **View.** CRS (any string the CRS backend resolves), extent in that
  CRS, screen size in device pixels. Optional: a horizon (for globe and
  perspective views), a quality factor (finer than needed, for zooming).
- **Source.** CRS, and per level a geotransform (or a lon/lat or index
  lookup for curvilinear and model grids, later), a size and a chunk
  shape. This is what GeoZarr `multiscales`, COG overviews and tile
  pyramids all describe; wxy-geozarr and wxy-tiff already read it.
- **Transformer.** The same callback `rwarp-wasm` takes (proj-wasm,
  proj4, or a Rust engine), batched.
- **Budget.** Optional maximum bytes or chunks.

### 3.2 Steps

1. Split the screen into tiles (64 px by default).
2. For each tile, sample a small grid of points, transform them to the
   source CRS, and drop failures and points that fail a round trip
   (past the horizon). Count them; a tile with none is empty.
3. Check the singular points: forward-transform the source's poles and
   seam into the view; a pole inside a tile means that tile takes the
   full row of longitudes at its level.
4. Local scale: the source cell one screen pixel needs at each sample
   (square root of the Jacobian determinant), lowest quartile over the
   tile.
5. Level per tile: the coarsest no coarser than that need (gdalwarp's
   `-ovr AUTO` rule, applied per tile).
6. Footprint per tile, unwrapped about the tile's centre longitude, then
   the chunk keys it intersects at its level.
7. Merge across tiles, keep the finest level where tiles disagree on the
   same area, order centre out (or by screen area), and cut to the budget
   by moving the outermost tiles one level coarser until it fits.
8. Return the keys with, per key, its level, screen area served and a
   priority; optionally the difference from the previous plan (what to
   fetch, what to drop) for panning.

Steps 2 and 3 are `compute_source_window` per tile; step 5 is
`choose_overview` per tile. Steps 4, 6 and 7 are new and short.

### 3.3 Outputs and what callers do with them

The plan is a value (serde in Rust, a plain object in JS). The caller
turns keys into byte ranges through whatever store it has (zarrita,
geotiff.js, wxy-refs for a byte-reference table) and draws however it
draws (a deck.gl layer, three.js, a canvas through `rwarp-wasm`'s warp).
The planner never sees a byte.

### 3.4 Where it lives

`rwarp::view` beside `source_window` and `plan`, exported in `rwarp-wasm`.
rwarp is already the no-I/O movement layer (m20), already in the browser,
and already holds both halves of the algorithm. The chunk-grid
description is geo-free and small; it stays in the same module until a
second user needs it elsewhere. A separate npm package is not needed
until a viewer outside wxylib asks for it; `rwarp-wasm` is that package.

## 4. Measurements

A global lon/lat grid like GHRSST MUR (36000 x 18000 cells at 0.01
degree, 512 x 512 int16 chunks, levels halving to level 6), four
1024 x 1024 views, planned from metadata only by the single-box rule and
by per-tile planning (section 3.2, without the budget step).
"Over" is the share of visible screen pixels served at least two levels
finer than they need; no pixel in any case was served two or more levels
too coarse.

| View | Single box: chunks, MB, levels, over | Per tile: chunks, MB, levels, over |
|---|---|---|
| Orthographic disk centred 147E 42S | 36, 15.6, level 3, 5 % | 34, 13.2, levels 3 to 5, 0 % |
| Orthographic 600 km, Hobart | 4, 2.1, level 0, 0 % | 4, 2.1, level 0, 0 % |
| EPSG:3031, 8000 km across | 216, 102.8, level 1, 90 % | 45, 18.4, levels 2 to 4, 0 % |
| Lon/lat 160E to 160W, 30S to 10N | 180, 92.2, level 1, 0 % | 25, 10.9, level 1, 0 % |

With full resolution only (no overviews, as a virtual store over netCDF
files):

| View | Single box MB | Per tile MB |
|---|---|---|
| Orthographic disk | 958.5 | 649.0 |
| Orthographic 600 km | 2.1 | 2.1 |
| EPSG:3031 | 368.6 | 315.2 |
| Lon/lat across 180 | 331.8 | 39.2 |

What this shows:

- **Polar views are where one scale fails.** The single rule takes its
  scale from the latitude span, which a polar view compresses, so it
  picks a level two steps too fine for 90 % of the screen.
- **The seam is where one box fails.** The lon/lat view across 180 asks
  for 40 degrees of longitude; its box is 360 degrees wide.
- **Small views are unaffected.** At 600 km both rules agree, so the
  planner costs nothing where the old rule was already right.
- **Overviews dominate.** Without levels, the globe view needs 0.65 to
  0.96 GB whatever the planner; with them, 13 to 16 MB. For stores
  without overviews, reduced copies are the remedy, and this note does
  not design them.

The measurement uses chunk counts from metadata, not fetches; it does not
time anything, and decode cost per chunk is the same for both rules.

## 5. The thin viewer

`wxylib/web/www/zarr.html`, on the existing wasm build:

- Opens a Zarr (GeoZarr `multiscales` where present, a single level
  otherwise) or a COG by URL.
- Three views: orthographic globe, polar stereographic, lon/lat with the
  seam in view.
- Draws the plan over the map (tiles coloured by level) with chunk and
  byte counts, and the single-box plan's counts beside it for the same
  view.
- Fetches and draws through `rwarp-wasm` (exact) first; a mesh path can
  come from math.gl or the mesh viewers' core package later (visgl note,
  section 2.1).
- Sources: GHRSST MUR COGs (with overviews), a GeoZarr multiscale store,
  and BRAN as the no-overview case.

## 6. Test cases

Shipped with the module as plain JSON (view, source description,
expected levels and key counts), so other planners can run them:

- Pole in the view: EPSG:3031 over a global lon/lat grid, and the north
  pole case.
- Seam in the view: lon/lat views across 180, and a UTM zone 60 source
  shown in lon/lat.
- Horizon: an orthographic disk and a tilted perspective view.
- Small and large: a city-sized view and a whole-world view.
- A source in a polar CRS shown on the globe (the Antarctic case the
  math.gl pole fixture gets wrong).

These overlap math.gl #367's fixtures and the wgis edge cases on purpose;
the visgl note's triggers say when to compare.

## 7. What we get, what it costs, what if we didn't

- **Get:** one place where the view-to-source question is answered
  correctly for any CRS pair, callable from Rust and JS; a per-tile level
  that no current viewer has; test cases others can adopt; and a reason
  for other viewers to depend on rwarp-wasm.
- **Cost:** a module of a few hundred lines on top of existing functions,
  plus the test JSON and one web page. The CRS callback cost is the same
  batched transform the warp already does: 256 tiles of 81 points is
  about 21 000 transforms per view change.
- **If we didn't:** each viewer keeps its own rule; the polar and seam
  cases keep costing 5 to 9 times the bytes; and the lessons stay in code
  only their authors read.

## 8. Open questions

1. Curvilinear and model grids (ROMS, ICON, HEALPix): the source side
   needs an index lookup instead of a geotransform. bigcurve-rs and the
   non-affine work cover the geometry; the planner takes that input
   later.
2. Time and depth: the plan is per 2D slice; read-ahead along other axes
   (as `fourd.html` does) is the caller's choice, or a later option that
   repeats the keys with another leading index.
3. Reduced copies for stores without overviews: a store design question
   (m23 and m29 touch it), separate from this module.
4. Whether to offer the test cases to deck.gl-raster and math.gl once the
   planner passes them; held with the other offers until the VRT work is
   further along.
