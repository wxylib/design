# Watch: custom projections and raster warp in deck.gl and math.gl (visgl)

Status: living tracking note, started 2026-10-28. Updated by the same
twice-weekly check as [opengeos.md](opengeos.md) (Wednesdays and
Sundays); newest entry first in section 4.
Context: [04 landscape](../04-landscape.md), lesson L4 (browser
reprojection has converged on adaptive meshes), the deck.gl-raster rows,
and the browser CRS decision (LS4: proj-wasm behind rwarp-wasm's JS
callbacks).

deck.gl is adding projections beyond Web Mercator and the globe, with the
supporting geometry in math.gl. The raster part of that work targets the
same cases wxylib uses to test warp: a polar grid (EPSG:3031), grids that
cross the antimeridian (Fiji, UTM zone 60), a whole-world raster, and
projections with a horizon (orthographic, tilted perspective). It is the
closest browser-side overlap with `wxy-warp`, the web warp demo and the
non-affine grid work.

## 1. What is being tracked

| Item | What | State at 2026-10-28 |
|---|---|---|
| [deck.gl#10739](https://github.com/visgl/deck.gl/issues/10739) | Tracker: custom projection. Per-view target CRS (`toCrs`) and per-layer source CRS (`coordinateSystem`, deck.gl#10874), CPU pre-projection, fp64 GPU projection as a v10 goal, math.gl mesh and raster pieces | Open. Generic raster reprojection, GPU projection families and cache invalidation for view-dependent geometry are listed as still open |
| [math.gl#367](https://github.com/visgl/math.gl/pull/367) | Qualified inverse-mesh recipe for polar and seam-crossing rasters: refines target triangles against source-texel interpolation error, rejects invalid samples or an exhausted budget, clips with math.gl mesh clipping while keeping target positions and source identity. 32 example tests (coverage, holes, conformity, provenance, budget failures), checked against pinned PROJ samples | PR page still shows open with no human review, but its content landed on math.gl master on 2026-10-28 (`4bc2d44e`, "(#367)") and ships in the 5.0 betas; now under `examples/geospatial/projection-domains/src/warp/`. Example-owned, not a public API (correction made 2026-11-08) |
| [math.gl#368](https://github.com/visgl/math.gl/pull/368) | Stacked on #367: drives the refinement with asynchronous proj-wasm batches (one reused WGS84-to-source operation, including ellipsoidal EPSG:3031), cooperative cancellation between batches, hands the finished raster to a task worker | Same as #367: PR page open, content on master since 2026-10-28 (`3e9baa32`, "(#368)"). Published packages gain no dependencies |
| [deck.gl-raster](https://github.com/developmentseed/deck.gl-raster) (Development Seed) | Client-side COG and Zarr layers with adaptive-mesh GPU reprojection (`raster-reproject`), added to this note 2026-11-05. Plans are tracked in GitHub milestones (0.10 open; no due dates) and issues; npm is the reliable release record, since GitHub releases lag | 0.9.0 (2026-10-23): mesh error in output pixels, antimeridian in output mode. 0.10.0-beta.2 (2026-10-30): COGSource, MultiCOGSource, coalescing range reader, GeoZarr via ZarrSource, classic `parseVRT` (see m25). 0.10.0 released 2026-11-09 (section 2.2) |

## 2. How it relates to wxylib

- **Same problem, same test cases.** Choosing where to sample a source
  grid for a target view, at the pole and across the seam, is what
  `wxy-warp` plans and what the web warp demo does in the browser. The
  #367 fixtures (EPSG:3031, Fiji, UTM 60, world, horizons) can be checked
  against wxylib's fixtures and GDAL as the oracle, and the other way
  round.
- **Refinement criterion.** #367 refines on source-texel interpolation
  error in the target. That is the tolerance-in-target idea behind
  bigcurve-rs (adaptive densify) and the index-space view of non-affine
  grids (m07). Agreement on the criterion would let a mesh made by one
  side be judged by the other.
- **Browser CRS.** #368 uses proj-wasm for the transforms, which is the
  browser CRS choice wxylib already made (LS4). The deck.gl tracker
  shows the other side of that choice: CRS syntax is broad but only the
  projection families ported into math.gl and checked against PROJ
  transform, and EPSG codes can resolve to families it cannot run. A
  configurable PROJ-in-wasm backend closes that gap; the rust-proj-capability
  matrix measures the same thing for Rust engines.
- **Batching and cancellation.** #368's bounded async driver with
  cooperative cancellation is the browser form of the progress and cancel
  handle listed as a missing module in m09, section 6.
- **Mesh contract.** A warp expressed as a target mesh carrying source
  identity per vertex is the mesh contract that doc 04 tracks against
  deck.gl-raster and zarr-layer (G5). math.gl keeping provenance through
  clipping is a step towards a shared form.
- **A known failure at the pole.** An automated review of #367 found that
  for the pole-containing Antarctic fixture, clipping drops zero-area
  source-space faces: about 24 triangles go, the target point
  (-170, -89.9) is left uncovered, and the result still reports no
  omitted triangles. A cell or triangle that contains the pole collapses
  in source space; wxylib's polar fixtures meet the same case and should
  test for it.

### 2.1 Against the existing browser mesh viewers

The browser viewers that sit next to wxylib already work this way, so
math.gl is converging on their design rather than introducing a new one:

- **ortho-cog-viewer** (mdsumner): a mesh engine that lays a regular grid
  in display space, finds each vertex's source texel by inverse
  projection, checks it by a lon/lat round trip, and lets the GPU
  interpolate linearly inside each triangle; proj4 or proj-wasm as the
  executor; rwarp in a worker as the exact engine beside it. Same split
  as math.gl: approximate on the GPU, exact elsewhere.
- **wgis** (mdsumner, `refine.ts`): adaptive refinement where the texture
  lands more than a set number of screen pixels out, with the map edge
  found by bisection and handled differently for a limb, a cut and a
  hole, including refinement round a pole in a periodic texture. That is
  the case math.gl's Antarctic fixture currently gets wrong.
- **rangefinder** (hypertidy): the other approach. A Leaflet CRS built
  from a proj4 definition, a CPU composite onto a grid in the output CRS,
  no live reprojection while panning. Less affected by math.gl.

What math.gl has that these do not is packaging: one renderer-neutral
npm package with a CRS resolver, provenance-keeping mesh clipping and
tests, with deck.gl layers on top once deck.gl#10874 lands. Turning the
viewers' shared core into a package is the plan those repos already set
out for themselves.

For wxylib/web: `cog.html` is the exact path (rwarp in wasm onto a
canvas) and stays distinct, since neither math.gl nor the mesh viewers
reproduce GDAL's resampling kernels. An approximate, pan-while-you-look
path for the web demos would come either from the viewers' core package
or from math.gl; the decision trigger below makes that choice once
math.gl's raster recipe becomes an API.

### 2.2 deck.gl-raster 0.10 and its range reader

deck.gl-raster 0.10.0 (npm, 2026-11-09; release post at
`docs/blog/v0.10-release.md`, commit `6da743d`) adds no new reprojection
or VRT capability over the betas already logged here. `parseVRT` has not
changed since #835 (2026-11-02), so m25's coverage table stands: it reads
classic mosaics only, one COG per item. What is new for wxylib is that
the coalescing reader is now its own zero-dependency package,
`@developmentseed/range-reader` 0.10.0, with a written design
(`dev-docs/specs/2026-10-26-range-reader-design.md`).

What the reader does:

- Reads issued in the same task are merged into one range request when
  the gap between them is at most `maxGap` (default: the median read
  length) and the bytes merged across stay under `maxOverfetchBytes`.
- Each response body is read as a stream, and each tile resolves as soon
  as its last byte arrives, so merging never delays the first tile.
  A stream is cancelled once nothing ahead of it is still wanted.
- Every received byte, including the gaps merged across, goes into one
  byte cache keyed by file offset, with separate budgets for header and
  tile bytes. A later read inside an earlier request is served from it.
- A per-origin limiter holds six requests at a time, because browsers
  open six HTTP/1.1 connections per host and S3 does not offer HTTP/2 to
  browsers. Waiting happens in the limiter, where priority and
  cancellation apply, not in the browser's queue.
- It never needs the file size (`Content-Range` is not CORS-safelisted),
  and a 200 answer to a ranged request is used only when the whole
  object is under a size limit; otherwise the read fails rather than
  downloading the file.

Measured on one GHRSST MUR COG on source.coop (2024-01-01,
36000 x 17999, 512-pixel tiles, ZSTD), counting the tiles a view needs
and merging them with the reader's defaults (gap up to the median tile
length, at most 1 MiB per request and 1 MiB merged across), then warping
the same views in Chromium with wxylib/web before and after it adopted
that policy (web PR #27). Request counts in the browser include the
header read:

| View | Level | Tiles | Merged requests | Browser, before | Browser, after |
|---|---|---|---|---|---|
| Tasmania, 10 x 10 degrees | 0 | 9 (1.0 MB) | 3 | 10 requests, 4.2 s | 4 requests, 1.7 s |
| Southern Ocean, 60 x 30 degrees | 0 | 91 (8.5 MB) | 12 | 92 requests, 30.4 s | 13 requests, 7.0 s |
| Whole globe, about 2250 px wide | 4 | 15 (2.1 MB) | 3 | 16 requests, 4.2 s | 4 requests, 2.0 s |

A GDAL-written COG keeps each level's tiles in row-major order, so
without a size cap a view costs about one request per row of tiles (7
for the Southern Ocean view). The 1 MiB request cap splits long runs,
which keeps each request short against the link's latency (their #815).
The values were identical before and after; 632 bytes were fetched
across gaps on the largest view.

Where wxylib stands:

| Path | Today | Gap |
|---|---|---|
| Native COG reads (`wxy-tiff`) | async-tiff's `ObjectReader`, whose `get_byte_ranges` calls `object_store::get_ranges`, which merges nearby ranges | None for merging. No streaming: a merged range decodes only when complete |
| Browser COG reads (web `src/fetch.rs`) | `FetchReader` implemented only `get_bytes`, so async-tiff's default `get_byte_ranges` fetched tiles one at a time, in sequence | Closed by web PR #27 (R1): merged reads, six at a time, measured above |
| Byte-ref stores (`wxy-refs` `RefsStore::fetch`) | One `get_range` per ref | Refs that share a file (BRAN, many chunks per netCDF file) are not merged. m29 section 8 already plans "ref rows grouped into coalesced ranges"; the reader's policy is a measured starting point |
| Browser ref reads (`bran.js`, `mdim.js`) | One `fetch` per chunk | Same as above, in JS |
| Chunk cache (m05) | Rows are the requested ranges, keyed by `(path, offset, size)`; the cache sits above `get_ranges` so lookups are exact matches | deck.gl-raster made the other choice: cache everything received, keyed by offset, lookups by interval containment. Both are reasonable; m05 should state why it keeps exact keys (ref-table joins) and what it gives up (gap bytes are dropped) |

Pickups, in order of value for effort:

- **R1.** Merge reads in the browser COG reader. Done in web PR #27:
  `get_byte_ranges` in `src/fetch.rs` with the policy in `src/ranges.rs`
  and up to six requests at once. Streaming can come later.
- **R2.** Merge ref reads per source in `wxy-refs`, grouping a batch by
  source and calling `get_ranges`. This is the fetch stage of m29 and
  helps the many-chunks-per-file case most.
- **R3.** Use `@developmentseed/range-reader` as is in the plain-JS
  pages (`bran.js`, `mdim.js`) rather than writing a JS coalescer. It is
  ESM with no dependencies, so it loads from a CDN without a build step.
- **R4.** Record the m05 cache-key choice against the offset-keyed
  design above.

Also in 0.10 and in line with `wxy-geozarr`: an array inherits its
group's `proj:` and `spatial:` attributes, and `spatial:dimensions` is
read by position (Y then X). The new `ZarrSource` and the planned
coalescing for sharded Zarr (their next release) are the points where a
wxylib byte-ref store could feed deck.gl-raster directly (signal 5).

## 3. Signals and decision triggers

Signals at each check:

1. State of math.gl#367 and #368: reviews, merge, changes to the
   fixtures, how the pole finding is resolved.
2. Whether the recipe moves from an example into a published math.gl
   or deck.gl API (a raster warp or mesh-preparation module).
3. deck.gl#10739 checklist: the `toCrs` / `coordinateSystem` PR
   (deck.gl#10874), generic raster reprojection, GPU projection families.
4. The CRS backend: whether proj-wasm becomes configurable or a default,
   and which projection families math.gl ports.
5. Any use of COG, Zarr or byte-reference sources in the examples (the
   point where wxylib stores could feed it directly).
6. deck.gl-raster: npm versions of `@developmentseed/deck.gl-raster` and
   `raster-reproject`, the open milestone, and changes to the mesh
   refinement, VRT or GeoZarr support. Whether it adopts math.gl's CRS or
   mesh pieces is the main thing to watch.

Decision triggers:

- **A published raster warp API in math.gl or deck.gl.** Compare its
  mesh and provenance form with `wxy-warp`'s plan output, and decide
  whether the web demo should produce or consume it, and whether its
  approximate path uses math.gl or the mesh viewers' core package
  (section 2.1).
- **The pole fix lands.** Run the same fixture through `wxy-warp` and
  record whether both agree with GDAL.
- **proj-wasm is configurable in deck.gl.** The browser CRS path that
  wxylib chose then works in deck.gl without extra glue; note it in the
  web demo docs.

## 4. Log

- **2026-11-09.** deck.gl-raster 0.10.0 released (npm 2026-11-09, release
  post the same day); see section 2.2. Since beta.4: #861 serves reads
  that arrive as their stream finishes, #862 declares the ECMWF grid
  node-registered in the zarr-globe example, #860 and #859 fixes.
  `parseVRT` unchanged since #835. `@developmentseed/range-reader` is
  published as its own package. No use of math.gl's CRS or mesh pieces.

- **2026-11-08.** Correction: math.gl#367 and #368 landed on master on
  2026-10-28 (`4bc2d44e` and `3e9baa32`, both committed by GitHub with the
  PR numbers), and are in every 5.0 beta, although both PR pages still
  read "Open" with no human review. Earlier log lines that called them
  unmerged read only the PR pages. Follow-on example work also landed
  (#369 Antarctica and Fiji lab, #378, #379, #382, #383 periodic paths and
  domain adapters, #384 raster strategies compared on display-space
  error). The pole finding on #367 still has no reply; whether master
  still drops the zero-area pole faces was not checked. math.gl
  5.0.0-beta.5 (2026-11-08) splits Arrow and Tasks into standalone
  packages (#448) and exposes resolved projection metadata for matching a
  CRS backend (#438). deck.gl: no release after 9.4.1; #10874 open, no
  activity since 2026-10-15. deck.gl-raster: 0.10.0-beta.3 (2026-11-05)
  and beta.4 (2026-11-06); #794 (zarr-globe) merged 2026-11-06; #858
  clamps globe mesh latitudes to the poles (a 0.25 degree grid whose rows
  end at -90.25 folded over the pole); #851 orders GeoZarr multiscales
  levels by pixel size, since the convention does not fix `layout` order;
  #792 adds a read of arbitrary pixel windows. No use of math.gl's CRS or
  mesh pieces seen.
- **2026-11-05.** deck.gl-raster added to this note and the twice-weekly
  check (it was monthly only, doc 04 section 15 row 8). npm: 0.9.0
  latest, 0.10.0-beta.2 (2026-10-30); milestone 0.10 open, 8 of 12
  issues closed. No GitHub Projects board was found (the projects pages
  could not be read).
- **2026-11-04.** No change. math.gl#367, #368 and deck.gl#10874 are
  open with no human review; the pole finding has no reply. No math.gl
  release after 5.0.0-beta.1, no deck.gl release after 9.3.12.
- **2026-11-01.** No change on the tracked items. math.gl#367 and #368
  are still open with no human review, and the pole finding has no reply;
  deck.gl#10874 is still open. No math.gl release after 5.0.0-beta.1.
  deck.gl shipped 9.4.1 (2026-10-28: flat common-space helpers for
  non-flat projections, #10657) and 9.3.12, neither with CRS or raster
  reprojection.
- **2026-10-28, evening.** math.gl 5.0.0-beta.1 released the same day.
  Its release notes list an opt-in CRS definition resolver, descriptor
  builders, target-plane domains, an external-engine path with proj-wasm
  integration, and clipping of triangle meshes with attribute provenance;
  raster mesh refinement and domain clipping are documented as recipes,
  not an API. This is the math.gl half of the proj-wasm trigger in
  section 3; deck.gl itself has not released anything since 9.4.0.
  math.gl#367 and #368 are still open with no human review, and the pole
  finding has no reply. deck.gl#10874 (arbitrary CRS strings in
  `Layer.coordinateSystem`, per-view `toCrs`) is open; a reviewer asked
  for PROJJSON in the CRS type.
- **2026-10-28.** Started. math.gl#367 opened (qualified inverse-mesh
  recipe for polar and seam-crossing rasters, example-owned, 32 tests),
  with #368 stacked on it (async proj-wasm batches). Both open and
  unreviewed; an automated review flags dropped zero-area faces at the
  pole. The work follows feedback on deck.gl#10739, which asked for a
  configurable PROJ-in-wasm backend.
