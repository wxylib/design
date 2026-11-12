# m33: Warp meshes: one contract, one engine

Status: musing, 2026-11-12. Open: nothing proposed is built. Scopes the
approximate, pan-while-you-look path that [m31](m31-view-chunk-planner.md)
section 5 and the [visgl watch note](watch/visgl.md) (section 2.1) leave
open: a triangle mesh that carries a raster from its own CRS into a view,
for the GPU or the CPU. Based on hypertidy/rwarp at `690afe0`
(`approx.rs`, `mesh`, `rwarp-wasm`), hypertidy/wgis at `25cdce2`
(`src/engine/refine.ts`, `docs/mesh-refinement.md`),
mdsumner/ortho-cog-viewer at `c35b303` (`src/engine/mesh.ts`, `uv.ts`),
deck.gl-raster at `5b55894` (`packages/raster-reproject`, its dev-docs
and its
[reprojection explainer](https://developmentseed.org/deck.gl-raster/examples/reprojection-explainer/)),
hypertidy/playproj at `959576b` (`src/core/families/globals.js`,
`src/core/texmap.js`), allboa/design at `51dedba` (decisions 0005 and
0012), allboa/scenespec at `c09ba98` (0.7 mesh layers), and the
trianglewins pages
[Reprojection meshes for raster tiles](https://mdsumner.github.io/trianglewins/dev-drafts/reprojection-mesh/)
and the [Warp Mesh Casebook](https://mdsumner.github.io/trianglewins/casebook/)
(the measurements below come from their code). Builds on
[doc 04](04-landscape.md) lesson L4, [m12](m12-bigcurve-densify.md)
(bigcurve-rs), [m20](m20-movement-crates.md) (the movement layer),
[m26](m26-bindings-on-rust.md) (bindings on Rust) and
[m31](m31-view-chunk-planner.md) (the view planner).

## Summary

The question: four projects in or next to this ecosystem each build
their own warp mesh (ortho-cog-viewer and wgis in screen space,
deck.gl-raster in source tiles, math.gl#367 as an example), and each
learned the pole, seam, horizon and lobe cases separately. Should the
mesh be a shared piece, what does it hand over, and where does it live?

- **One contract first.** A warp mesh is vertices with a target
  position and a source coordinate, triangles, and a per-triangle error
  with its unit. That is the mesh spec's triangle form with two column
  groups added, and it is what every consumer (a GPU layer, a CPU warp,
  a scenespec mesh layer) needs. Agree it before any engine.
- **One engine, two strategies.** A screen-space grid refined on error
  (wgis's design) and source-space tiles refined per tile with shared
  edges (deck.gl-raster's design, plus conforming edges). They fail in
  different places, and the casebook shows each one's failures are the
  other's strengths. The engine offers both behind one call.
- **Domains need metadata PROJ does not give.** Where a projection's
  valid region ends and where its cuts are (map edge, lobes, limb, pole
  points) decides whether a mesh is exact or smeared. playproj already
  holds the lobe and cut tables for the interrupted projections, tested
  against PROJ 9.8, and allboa decision 0005 already computes a view
  domain by walking bearings. Port both into one small table.
- **Rust, in rwarp, beside m31's planner.** rwarp is the no-I/O movement
  layer, already in the browser as `rwarp-wasm`, already holds the
  approximate transformer this generalises, and m26 puts the R and
  Python bindings on the Rust crates. A `rwarp::view::mesh` module
  answers "how do I draw it" next to m31's "what do I fetch". It moves to
  its own crate only when a consumer outside rwarp asks, the rule m31
  and rwarp decision N4 already use.
- **The JS stays as the reference.** The casebook's `core.js` and
  `tiles.js` and wgis's `refine.ts` become the oracle the Rust engine is
  replayed against, the way bigcurve-rs stage 1 was replayed against the
  C++ engine.

## 1. The problem

A viewer that draws a raster in another CRS without resampling it lays
triangles over the view, gives each vertex an exact source coordinate,
and lets the GPU interpolate linearly inside each triangle. The mesh
carries the warp. How it is built decides the error on screen, the
triangle count, whether neighbouring pieces meet, and which projections
can be drawn at all. It fails in a small number of places, all of them
singularities of the inverse:

- **The pole** of a lon/lat source: longitude curves like 1/r around it,
  and a triangle around it spans every longitude.
- **The seam**, where u jumps from 1 to 0 (the antimeridian of a global
  source, the edge of a world map, the cuts between lobes).
- **The edge of the domain**: the limb of a globe, the outline of a
  world projection, a hole.
- **Seams between pieces**: tiles or refinement levels that do not share
  their edge vertices.

The same mesh drives a CPU warp: give each output pixel the barycentric
source coordinate of its triangle and sample. That is GDAL's approximate
transformer (rwarp's `approx.rs`) with triangles in place of row
segments, and an error bound that holds in two dimensions.

## 2. What exists

| Project | Where the mesh lives | Refinement | Seams and poles | Domain edge |
|---|---|---|---|---|
| ortho-cog-viewer | screen grid, 64 cells | none | per-triangle u unwrap with REPEAT; pole triangle split into three at the pole's projected point (exact) | round-trip test per vertex, crossing edges bisected and clipped |
| wgis (`refine.ts`, from ortho-cog-viewer) | screen grid, refined | split a cell while error > 0.5 screen px at centre and edge midpoints, down to about 2 px; batched level by level as a generator | as ortho-cog-viewer, plus refinement round a pole | edge kinds classified (outline, cut, interruption, hole, texture edge); curved edges refined and clipped, straight cuts clipped coarse |
| deck.gl-raster (`RasterReprojector`) | one mesh per LOD tile, in source uv | greedy Delaunay insertion while error > 0.125 x one source pixel's size on screen at the tile centre | antimeridian by unwrap then clip at the world edge; 0.5 degree pole guard | box seeds (projection domain boxes); no curved domains |
| math.gl#367 (example on master, not API) | target triangles | refined against source-texel interpolation error, with a budget | polar and seam fixtures, rejects invalid samples | mesh clipping that keeps target positions and source identity |
| rwarp | (none) | GDAL's approximate transformer along rows | n/a | n/a |

What none of them has: a stated output contract another project can
consume, conforming edges between independently built pieces, and the
lobe and cut metadata an interrupted projection needs.

## 3. Measurements

From the casebook's code at a 900 px view (900 x 450 for world maps),
error at the centroid and three edge midpoints of each triangle, in
screen pixels:

| Case | Screen grid, 64 | Screen grid, refined to 0.25 px | Source tiles, per-tile unit |
|---|---|---|---|
| Orthographic globe, centre 147E 42S | 6,348 tris, worst 11 px (limb 4 to 6 px, pole ring 8 to 11 px) | 28,800 tris, 0.33 px | 36,600 tris, 0.10 px, edge of the disc short by about 0.1% |
| Orthographic, 20E 80S | 6,348 tris, worst 7.8 px | 26,100 tris, 0.25 px | n/a |
| South polar stereographic to the equator | 8,194 tris, worst 11 px (pole ring) | 10,500 tris, 0.35 px | 29,700 tris, 0.11 px; 26,500 with one screen pixel as the unit |
| Equal Earth centred on 150E | 3,502 tris, worst 6.6 px; 432 px without unwrap | n/a | 20,253 tris, 0.10 px when split at the map edge; 432 px when not |
| Interrupted Goode (igh) | 2,807 tris, worst 16 px at the gap tips | 54,800 tris, still 16 px | 38,400 tris, 0.14 px when split at the lobe edges (refinement stops at one source pixel); about 200 px when not |

Between tiles, the per-tile unit leaves 256 T-junctions in the polar
view; the cracks are under 0.06 px, so they show as sparkle, not gaps.
Splitting the neighbour's edge at each one removes them for under 1%
more triangles. wgis's own `check-mesh` gives the same picture on a
1000 x 800 canvas: refined 64 brings the missed edge from about 5% to
under 0.1% on every projection, and the interrupted homolosine keeps a
worst error of 6.98 px.

Two lessons:

1. **Screen space is right for the view and wrong at known cuts.** A
   screen mesh cannot crack (every vertex is placed in screen space) and
   its error is in the unit the viewer cares about. But near the
   equator each igh gap narrows to a point, and a triangle can have all
   corners valid, one in each lobe, while straddling the gap. Splitting
   it gives smaller triangles that still straddle it. Only knowing where
   the cut is fixes that.
2. **Source space is right at known cuts and needs care at edges.** In
   source lon/lat the cuts are meridians, so splitting tiles there is
   exact. But independent tiles disagree along shared edges, the unit
   varies from tile to tile, and box seeds cannot follow a curved domain.

## 4. The contract

A warp mesh is one value, serialisable, with no renderer in it:

- `vertices`: target position (`x`, `y`, in target CRS units, or in
  screen pixels with the view transform recorded), source coordinate
  (`u`, `v`, in the source grid's fractional pixel space, so it does
  not depend on how the texture is stored), and `origin` (grid, rim,
  pole, cut, refined).
- `triangles`: three vertex indices, CCW in target space; `error` (worst
  sampled error, in `error_unit`); `part` (tile, lobe or piece id), so a
  consumer can draw or fetch by piece.
- metadata: `tolerance` and `error_unit` (`screen_px` or
  `source_px`), the sample rule (centroid and edge midpoints), the
  source grid and target CRS, and whether the mesh conforms (no
  T-junctions) or not.

This is the mesh spec's triangle form (vertex and triangle tables,
0-based on the wire) with column groups added; a v0.3 annex is the
natural home, so meshcore, laridae and cdtr tooling read it unchanged.
For drawing, it is a scenespec mesh layer (0.7) whose colour comes from
a raster through `u`, `v` instead of a face column: one new layer kind,
a candidate for 0.9.

## 5. The engine

One call, two strategies, the same contract out:

- **Screen.** A grid over the view, inverse-projected; split where error
  exceeds the tolerance; edges classified and clipped as wgis does;
  per-triangle unwrap; pole split. Plus one thing wgis and
  ortho-cog-viewer lack: if the domain table names cuts, a triangle
  whose corners fall in different lobes or on either side of a cut is
  split at the cut before the error test, which closes the igh tips.
- **Source.** Tiles from m31's per-region plan; per tile, refinement in
  source space from seeds clipped to the domain and split at the cuts;
  one tolerance in screen pixels for every tile (not a per-tile source
  pixel); shared tile edges decided by the edge alone, so neighbours
  agree. Use this when the source is tiled and the pieces are drawn or
  fetched separately.

The edge decision is bigcurve's rule: bisect while the projected
midpoint is off the chord of the projected ends. bigcurve-rs already
implements it with bitwise-identical results in either direction; the
engine can call it for shared edges, or reimplement the few lines, as
long as the replay tests agree.

Projection calls dominate the cost. The engine takes a projection trait
with batched forward and inverse (the shape of rwarp's `CrsTransform`),
built-in analytic forms for common view projections (ortho, stere,
laea, aeqd, eqearth, moll, igh) for speed in wasm, and `proj` or
`proj4rs` behind the trait for the rest, as rwarp does now. A refinement
that yields batches and is handed back their transforms (wgis's
generator) keeps the browser path to a few calls per level when the
projection lives in JS.

## 6. Domain and cut metadata

PROJ gives forward and inverse but not where a projection's domain ends
or where it is cut. The engine needs, per target CRS:

- the valid region in target space (a polygon, or a test), with its
  kind per edge piece (outline, straight cut, interruption, hole);
- cut meridians in source lon/lat, per latitude band (one for any world
  map: lon_0 + 180; four south and two north for igh);
- pole points in target space (one per lobe for interrupted maps, none
  where the pole is a line).

Sources to port, not reinvent: playproj's `globals.js` (lobes for igh,
igh_o, imoll, imoll_o and gores, checked against PROJ 9.8 by
`test/check-globals.mjs`), allboa decision 0005's bearing walk for the
valid region of a bounded projection, and wgis's edge classification.
A table keyed by PROJ operation name covers the named projections; the
round-trip test and the bearing walk cover the rest.

## 7. Where it lives

| Option | For | Against |
|---|---|---|
| A. `rwarp::view::mesh`, exported in `rwarp-wasm` (recommended) | beside m31's planner and the approximate transformer; already in the browser; R and Python through m26 | rwarp grows; `rwarp::mesh` is already taken by quad meshes, so the name must differ |
| B. its own crate (`warpmesh`), consumed by rwarp | own version and voice, like bigcurve-rs | another crate before a second consumer exists |
| C. a TS package from wgis and ortho-cog-viewer's core | closest to the browser viewers, no wasm boundary | a second implementation for the CPU warp and R; the visgl note already expects that package to come from math.gl or the viewers |
| D. wait for math.gl's recipe to become an API | no work | browser only; no CPU warp, no R; not yet an API |

**Rust or TypeScript.** Rust, for the engine: one implementation for
the CPU warp (`wxy-warp`), the browser (`rwarp-wasm`) and R and Python
(m26), with replay tests against the JS. The cost is the wasm boundary:
per-vertex callbacks into a JS projection are slow, which is why the
built-in projections and the batched generator matter. The browser
viewers keep their TS meshers until the wasm path matches their speed on
their own pages.

## 8. Test cases

The casebook's cases as JSON (view, source grid, expected worst error,
expected coverage, expected T-junction count): the constant mesh, pole
in view, horizon, antimeridian, polar stereographic, tile seams,
tolerance unit, pole guard and interrupted Goode, for both strategies.
Add wgis's `check-mesh` projections (tilted perspective, Winkel tripel,
sinusoidal, oblique Mercator with a Web Mercator source) and
math.gl#367's polar and seam fixtures. These sit beside m31's planner
cases, so a viewer can run both.

## 9. What we get, what it costs, what if we didn't

- **Get:** one answer to "how do I draw it" for any CRS pair, from Rust,
  JS, R and Python; a contract others can consume or produce; the
  interrupted and polar cases closed in one place; a CPU approximate
  warp with a two-dimensional error bound.
- **Cost:** a module of perhaps a thousand lines plus the domain table,
  the test JSON and replay tests; a contract annex in the mesh spec; one
  scenespec layer kind.
- **If we didn't:** each viewer keeps its own mesher and its own subset
  of the fixes (ortho-cog-viewer: no refinement; wgis: no cut metadata;
  deck.gl-raster: no curved domains, cracks between tiles), and the
  lessons stay in the code of whoever learned them.

## 10. Open questions

1. Screen positions or target CRS units in the contract? Screen is what
   a GPU draws; CRS units survive a pan. Possibly both, with the view
   transform recorded.
2. Should the source strategy conform tile edges always, or only when
   the consumer draws tiles separately?
3. Error unit for the CPU warp: screen pixels mean output pixels there;
   is 0.125 (gdalwarp's `-et`) the default, or 0.5 (wgis, OpenLayers)?
4. Curvilinear and model sources (ROMS, ICON): the source side needs an
   index lookup; rwarp's quad mesh and bigcurve-rs cover the geometry,
   as in m31's open question 1.
5. Whether to offer the contract and the test cases to deck.gl-raster
   and math.gl; held, as in m31, until the engine passes them.

## 11. Decisions for the maintainer

1. Accept the contract (section 4) as a mesh spec annex, or keep it
   private to rwarp for now?
2. Home: option A, B, C or D (section 7)?
3. Scope of the first stage: screen strategy with cut metadata only (it
   covers ortho-cog-viewer and wgis), or both strategies at once?
