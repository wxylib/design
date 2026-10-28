# m12: An adaptive densify engine (bigcurve in Rust)

Status: musing. Not a plan; it becomes work only through its own repo's
design notes or a numbered wxylib doc.

**Implementation (2026-10-28):** Partly implemented, outside wxylib. The recommended home was
taken: [hypertidy/bigcurve-rs](https://github.com/hypertidy/bigcurve-rs),
with stage 1 (a faithful port, replayed against the C++ engine) in
[bigcurve-rs#1](https://github.com/hypertidy/bigcurve-rs/pull/1). The
pluggable edge model and the `wxy-warp` front end are open.

## Summary

bigcurve (R package, hypertidy/bigcurve, CRAN 0.6.0) adds vertices to
lines only where a map projection bends them, by recursive midpoint
bisection measured in the target plane (d3-geo's `resampleLineTo`). Its
core is a 200 line header with no R or PROJ in it, and a comment that it
is "the piece that gets reused in Python (or rewritten in Rust) later".

The question is where a Rust version should be framed, and whether it
earns a place behind the non-affine grid front ends worked out for
controlledburn (see the grid front-ends note for controlledburn-rs, core
PR #9, docs PR #13).

**Recommendation: a dedicated repo and project, `hypertidy/bigcurve-rs`
publishing the crate `bigcurve` (the name is free on crates.io), with its
own voice and README. Neither wxylib nor controlledburn-rs should hold
it; both consume it.** The reasons are below: no existing Rust crate does
this job, the engine is smaller and more general than either consumer,
and the one change that makes it useful to grids (a pluggable edge model
and an arbitrary forward map) is a change to bigcurve's own idea, so it
should be argued in bigcurve's own place.

## What bigcurve is, reduced to parts

The engine is three choices and a loop:

1. **An edge model**: what the "middle" of an edge is in the source
   space. bigcurve fixes this to the great circle midpoint (with an
   optional move onto the WGS84 geodesic at the same fraction).
2. **A forward map**: source position to target position, which may
   fail. bigcurve injects this (`Transform`), and binds it to PROJ.
3. **A tolerance in target units**: how far the projected midpoint may
   sit from the chord of the projected ends.
4. **The loop**: bisect while the midpoint is off the chord (or sheared
   along it), with a forced split for long edges, an arc floor, and a
   depth limit. Each point is transformed once.

Two properties go beyond d3-geo and matter for coverage work:

- **Shared edges refine identically.** Arithmetic runs in one canonical
  direction, so `a -> b` and `b -> a` give bitwise identical vertices. Two
  zones that share a boundary stay a partition after densifying.
- **Provenance.** Each refined segment knows its parent segment, so
  feature, ring and path identity survive (the wkpool contract).

## Posed against the non-affine grid input handling

The grid front ends move each polygon into the grid's index space
(fractional col, row) and burn it on a lattice of unit cells. The front
end has two jobs: map positions, and cut edges so each piece is straight
in index space. That second job is exactly bigcurve's job with **index
space as the target plane**.

| case | what the front end needs | bigcurve-style engine |
|---|---|---|
| rotated or sheared affine | vertices only | not needed (it would add nothing, correctly) |
| rectilinear, walls known | cut edges at every wall crossing | not the right tool: the map is piecewise linear, so the exact answer is the wall intersections; bisection only approaches each kink to tolerance |
| rectilinear, centres only | walls chosen as midpoints, then as above | as above |
| curvilinear (2D coordinates) | short pieces, then an inverse cell search per vertex | **good fit**: few vertices where the grid is near affine, many where it bends; each new vertex costs a search, so economy matters |
| polygon in another CRS, any grid | reproject, then map to index, cutting edges | **good fit**: the forward map is "reproject then index", one composed function |
| exact curvilinear (world-space clip) | cell outlines traced in the polygon's CRS | **good fit, other direction**: cell edges are curves in the polygon's CRS when the CRSs differ; densify them with forward = grid CRS to polygon CRS |
| remaining curvilinear error | the fraction of a unit square is not the fraction of the cell's area | **cannot help**: this is a measure error, not a shape error; densifying converges to it, not past it |

What the engine brings to these cases:

- **A natural tolerance.** In index space the tolerance is a fraction of
  a cell (say 1e-3), the same for every grid and CRS. No guessing metres
  per pixel, which is the weakest part of bigcurve's current default.
- **Locality for the inverse search.** Midpoints are near their parents,
  so a walk-based cell search can start from the parent's cell. A
  uniform densify spends searches where nothing bends.
- **Partitions stay partitions** (the shared-edge property), which is
  what makes zonal weights over a set of zones sum to one.
- **Unprojectable points do not error**, which suits grids with masked or
  missing coordinates (swaths with fill values in the 2D arrays).

What has to change for it to work there:

- **The edge model must be a parameter.** A polygon in a projected CRS
  has straight edges in that CRS, and a polygon in longitude, latitude
  read by GEOS or GDAL (and by exactextract) also has planar edges.
  bigcurve's great circle reading is right for s2 users and for drawing,
  but for coverage parity the default edge model has to be planar in the
  source CRS, with great circle and geodesic as choices. This is the one
  conceptual change to bigcurve, and it is why the generalisation should
  be argued in bigcurve's own repo.
- **The long-edge guard is sphere specific** (arcs over 30 degrees always
  split; the arc floor converts metres to an angle). It needs restating
  per edge model, for example a maximum source step for planar edges, or
  a maximum index step derived from the first transformed endpoints.
- **The midpoint test assumes a smooth map.** A curvilinear grid read by
  bilinear interpolation has kinks at cell walls, like the rectilinear
  case. Bisection still converges to tolerance, but if exact cuts are
  wanted the front end should cut at walls (known in index space) after
  densifying, which is cheap once vertices are in index space.

So, in the controlledburn picture: the engine stays as it is; the
rectilinear front end needs no densifier at all; the curvilinear and
"polygon in another CRS" front ends are where a bigcurve engine sits,
and so does the cell outline tracing for the exact world clip.

## Overlap check: does it exist already?

| crate or library | what it does | why it is not this |
|---|---|---|
| `geo` (`Densify` over `Euclidean`, `Haversine`, `Geodesic`, `Rhumb`) | uniform densify to a maximum segment length in a source metric | not adaptive, no target map, no tolerance in the target plane; but its `InterpolatePoint` metric spaces are the right shape for the edge model and could be reused as such |
| `d3_geo_rs` (MIT) | a full Rust port of d3-geo, including the resampler | the resampler is wired into d3's projection stream pipeline and its own projections; not a standalone engine over an arbitrary map, no shared-edge determinism, no mesh or pool input |
| `s2` (Rust port, Apache-2.0) | cells, points, regions | no edge tessellator; C++ s2's `S2EdgeTessellator` is the closest prior art, and supports only plate carree and Mercator |
| `geographiclib-rs` | ellipsoidal geodesics | the geodesic edge model, not the engine |
| PROJ `proj_trans_bounds` | uniform densify of a box edge | uniform, box only |
| GDAL approx transformer (also in wxy-warp, via rwarp) | bisects a row of a warp until the linear interpolation error is under a threshold | the same idea, specialised to scanlines; a shared engine could serve it, but it is hot path code and should not be forced |

Nothing combines an arbitrary forward map, a pluggable edge model, a
tolerance in the target plane, and shared-edge determinism. It should be
its own crate. It should not be a geo PR either: the edge model can
borrow geo's metric spaces through a small trait, but the engine's
contract (map, tolerance, provenance) is not geo's.

On s2 specifically: the bigcurve vignette's split still holds in Rust.
s2 answers what a shape is on the sphere; bigcurve answers how many
vertices it needs on one plane. For exact spherical coverage (great
circle polygons, spherical cell areas) s2 is the reference, and the
index-space burn is the fast first pass, as with the planar world clip.

## Where to frame it

Three homes were weighed.

- **Inside wxylib.** wxylib owns only what nobody else has and keeps a
  lean, impersonal voice. A densifier would fit technically (warp
  windows, reprojected extents, coverage), but it would become one
  module among many and lose its own explanation. wxylib is a consumer.
- **Inside controlledburn-rs.** The engine has two optional
  dependencies and the grid note argues that front ends sit outside it.
  A sphere-aware densifier would pull geometry semantics into a crate
  whose contract is a regular lattice. controlledburn-rs is a consumer,
  through a front end or helper module, perhaps behind a feature.
- **Its own repo and project.** bigcurve has a personal, idiomatic
  framing (the d3 lineage, the Simon Wotherspoon midpoint, "the
  projection decides"), an existing R user surface, and a tested header
  that already separates the engine from PROJ. The Rust crate can keep
  that voice, carry the generalisation argument above, and later back
  the R package itself (as controlledburn-rs relates to controlledburn).

The third is recommended: `hypertidy/bigcurve-rs`, crate `bigcurve`,
with a dedicated project for its planning. Suggested shape:

- core: no PROJ, no geo; `Edge` trait (great circle default, planar,
  geodesic behind a `geographiclib` feature), `Forward` trait returning
  `Option`, tolerance, depth, canonical direction, parent ids;
- inputs: slices of coordinates and segment meshes (vertex pool plus
  index pairs), with `geo-types` behind a feature;
- adapters as features or sibling crates: PROJ (`proj` crate), and an
  index-space adapter example matching the grid note;
- fixtures: bigcurve's R outputs as the oracle, bit for bit on vertex
  counts and shared-edge identity.

wxylib's part is small: this note, and later a front end in `wxy-warp`
(`cover`) that takes a `bigcurve::Forward` for curvilinear and
reprojected polygons, and the same engine for densified warp windows.
