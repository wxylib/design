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
| [math.gl#367](https://github.com/visgl/math.gl/pull/367) | Qualified inverse-mesh recipe for polar and seam-crossing rasters: refines target triangles against source-texel interpolation error, rejects invalid samples or an exhausted budget, clips with math.gl mesh clipping while keeping target positions and source identity. 32 example tests (coverage, holes, conformity, provenance, budget failures), checked against pinned PROJ samples | Open, unreviewed. Example-owned (`examples/geospatial/projection-domains/warp/`), not a public API |
| [math.gl#368](https://github.com/visgl/math.gl/pull/368) | Stacked on #367: drives the refinement with asynchronous proj-wasm batches (one reused WGS84-to-source operation, including ellipsoidal EPSG:3031), cooperative cancellation between batches, hands the finished raster to a task worker | Open. Published packages gain no dependencies |

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
