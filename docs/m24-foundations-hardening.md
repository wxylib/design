# m24: hardening controlledburn, bigcurve and rwarp

Status: musing, 2026-10-31. An audit of the three foundation crates
below wxylib, and a restructuring proposal. It builds on m20 (the
movement layer), m19 (the exact footprint) and m21 (conservative
regridding), and does not reopen them. Based on rwarp at 77266db (0.3.1
plus the spherical measure), controlledburn-rs at 6017733 (0.2.4),
controlledburn (C++, R, Python) at ed5281b (0.3.2.9000), bigcurve-rs at
5446a89 (stage 1 merged), and wxylib/core at caba7b2.

**Implementation (2026-10-31):** Started. bigcurve stage 2 is up
(hypertidy/bigcurve-rs#3). The controlledburn-rs audit fixes and its
canonical tables are in hypertidy/controlledburn-rs#22. The C++ core's
check against those tables is hypertidy/controlledburn#37 (all 6737
records agree). rwarp's `mesh` module, stage 1 of its curvilinear front
end (section 7, step 3), is hypertidy/rwarp#28.

## Summary

The goal is to put controlledburn (with the Rust crate as the canon and
the C++ core following it), bigcurve and rwarp in as complete a state as
possible. The aim is high: controlledburn onto irregular grids, with
controlledburn and bigcurve used inside rwarp itself. The three are one
connected foundation, so they should be restructured where that is
sensible, and they must stay usable from other languages in the ways
they are used today. wxy is the engine over all three, so wxylib
coordinates the effort.

- **The layer is sound, and the parts are closer to done than the plan
  suggests.** All suites are green at the audited commits. rwarp matches
  gdalwarp cell for cell across kernels, chunking, geolocation and
  cutlines. controlledburn's property suite runs 10,000 cases per
  property in CI, clean. bigcurve reproduces the R engine bit for bit. What is
  missing is the work m20 named "beyond parity", and it all goes through
  one piece that does not exist yet: rwarp's curvilinear front end.
- **Two defects found and fixed.** In controlledburn-rs, `crop` was
  never compiled (it was missing from `lib.rs`) and still used 1-based
  indices. The C++ core's only cross-check against the Rust canon was 15
  aggregate cases. Both are fixed in the PRs above; the C++ core now
  checks 240 generated cases record by record against tables the Rust
  crate writes.
- **Restructure inside repositories, not across them.** Keep four
  repositories and their release trains. Inside rwarp, add a `mesh`
  module that needs no CRS backend, and split `warp.rs` (3300 lines)
  along the seams it already has. Do not create a shared types crate or
  a C ABI per crate.
- **One controlledburn core, eventually.** Two implementations of one
  algorithm cost a port for every new feature: `CoverageWindow`,
  `Measure` and `crop` exist only in Rust. The canonical tables make the
  port cheap to check but not free. The proposal is that the Python
  package builds from the Rust crate before its first PyPI release, and
  that the R package follows once it has had a release cycle on CRAN's
  Rust toolchain. That is a decision for the maintainer (section 9).
- **Order:** bigcurve stage 2, then rwarp `mesh` (quad mesh, equal-area
  cells, the walk), then the bigcurve feature in rwarp (adaptive
  footprint edges, reprojected polygons), then the curvilinear exact
  footprint as conservative remapping. wxylib's `cover.rs` moves down
  when the walk lands.

## 1. State at the audit

| crate | release | tests at audit | done | open, from its own plans |
|---|---|---|---|---|
| controlledburn-rs | 0.2.4 on crates.io | 18 unit, golden (31 cases, bitwise vs the C++ tables), properties (7 properties, 10,000 cases in CI), window, measure, holes, wall cells | burn (coverage, approx), lines, points, WKB, materialize, `CoverageWindow`, `RowPrefix`, `Measure::CosLatitude`, geo-types | f32 or f64 fractions (cb#24 item 8); reusable burner scratch; capacity estimate (#5); DE-9IM tables (design note only) |
| controlledburn (C++ core, R, Python) | R 0.3.2 on CRAN (fix due 16 Nov), Python 0.4.0 not on PyPI | ctest (unit, 15 parity aggregates), testthat, pytest | burn, materialize (polygons), WKB, bbox; R: crop, extract, materialise_chunk; Python: Arrow input, crop | #13 dense lines and points; #22 PyPI; #24 cross-surface gaps; no `CoverageWindow`, `Measure` |
| bigcurve-rs | unpublished, 0.1.0 | fixtures (bitwise vs the C++ header with PROJ), properties | great circle engine, path and mesh drivers, shared edges | stage 2 edge models and batching (now PR #3), `Geodesic`, adapters (PROJ, geo-types), examples |
| rwarp | 0.3.1 on crates.io | 10 suites, about 210 tests, both CRS backends | transformers (affine+CRS, GCP, geolocation with quad index and backmap), approx, source windows, chunk plans, all kernels, cutline, exact footprint, conservative weights (stage 1, 2, 3a) | curvilinear front end (design only, stages 1-5), bigcurve feature, weights stages 3b-6, `warp_vector`, displacement transformers |

The existing ways these are used from other languages:

| user | route | depends on |
|---|---|---|
| R `controlledburn` (CRAN) | cpp11 over the C++ core (`tools/sync-core.sh`) | C++ core |
| Python `controlledburn` | pybind11 over the C++ core | C++ core |
| R `bigcurve` (CRAN) | its own C++ header | header (fixtures keep the Rust port in step) |
| browser | `rwarp-wasm` (wasm-bindgen), wxylib/web | rwarp with proj4rs |
| R `wxy`, Python `wxy` | extendr and PyO3 over wxylib/core, pinned by commit | rwarp, controlledburn through wxy-warp |
| `wxy` CLI, Docker images | wxylib/core | the same |

Nothing in the layer has a C ABI. The C ABI in doc 03 belongs on top of
wxy, not on each foundation crate.

## 2. Findings

### controlledburn-rs

1. `src/crop.rs` was not declared in `lib.rs`. It was never compiled,
   and its book chapter was not in `SUMMARY.md`, so the chapter's
   examples were never run. It still used the 1-based, inclusive indices
   from before the switch to 0-based tables. Fixed in
   controlledburn-rs#22, with a property test against slicing the dense
   raster.
2. The crate docs said the C++ core emits 1-based indices. That stopped
   being true when the +1 moved to the R shim. Fixed in the same PR.
3. The C++ core's only record-level link to Rust ran the other way: the
   golden JSON was written by the C++ core, and the Rust crate checked
   itself against it. Since the canon moved to Rust, nothing checked the
   C++ core against Rust's output. Fixed: `tests/canon.rs` writes 240
   generated cases (lattice-biased rings, self-intersections from
   snapping, holes, multipolygons, lines and points on non-dyadic grids),
   and the C++ core reads them (controlledburn#37).
4. The C++ core has `bbox_wkb`; the Rust crate does not. It is small and
   the bindings use it for default extents. Worth adding when Python moves
   (section 5.2).
5. Fractions are `f32`. The exact footprint and the weights already work
   in `f64` through `CoverageWindow` and round only for warp
   compatibility. A curvilinear front end makes the truncation visible
   per cell. The decision stays with cb#24 item 8, and it should be made
   before a 0.3.0, because it changes the output schema in every
   binding.

### controlledburn (C++, R, Python)

6. The features exist only in Rust: `CoverageWindow`, `RowPrefix`,
   `Measure`, coalescing, crop in the core. Each one is a port waiting to
   happen, or a reason for a binding to move to the Rust crate (section
   5.2).
7. The cross-surface gaps in #24 (R's `materialise_chunk` reimplements
   the core in R loops; "sum" means different things in R and Python;
   mixed geometry kinds) are binding work. They get cheaper if both
   bindings sit on one core with one materializer.

### bigcurve-rs

8. Stage 2 was planned, and rwarp needs it for adaptive edges and the
   curvilinear front end. It is now PR #3: an `Edge` trait (`GreatCircle`,
   `Planar`) and `ForwardBatch`, which moves arrays in place, reports
   success per point, and carries a `near` hint per point (the target
   position of the edge's start, so a cell search can start next to the
   answer). Refinement is level by level, one forward call per level,
   with bitwise the same vertices as the depth-first engine.
9. Still open: `Geodesic` (needs `geographiclib-rs` and a fixture from R's
   `densify(ellipsoid = TRUE)`), the PROJ and geo-types adapters, and a
   crates.io release. rwarp cannot take an optional dependency on a git
   crate and still publish, so **bigcurve 0.2.0 on crates.io is the gate
   for the bigcurve feature in rwarp.**

### rwarp

10. The curvilinear front end (`design/curvilinear-frontend.md`) is
    design only: no `QuadMesh`, no `CellMap`, no walk. Everything the
    goal of irregular grids needs goes through it: polygon coverage on
    curvilinear grids, the exact footprint with geolocation sources, and
    weights stage 4.
11. `warp.rs` is 3300 lines in nine sections: entry points, nearest,
    generic interpolated, bilinear, cubic, lanczos, types and conversion,
    generic interleaved kernel, area methods. `Lattice` and the coverage
    step are shared with `weights.rs` through `pub(crate)` items in
    `warp.rs`. The seams are already there. Section 5.3 proposes the
    split.
12. The crate docs still describe validation "in the cogcache package"
    and analysis "at GDAL 3.13.0dev". The tables below them are current
    (3.14dev). A small edit.
13. The default `proj` feature links libproj. `GeolocArrays`, the quad
    index and anything a curvilinear front end needs use no CRS at all.
    A front end in rwarp should therefore build with
    `--no-default-features`, so a burn-only consumer gets no C
    dependency.

### wxylib

14. `wxy-warp/src/cover.rs` (411 lines: index-space and world-space
    coverage on non-affine grids) was meant to move down (m20). Its
    index method is the bilinear-cell measure that the equal-area map
    corrects. It should be replaced by rwarp's front end, not moved.
15. The R and Python bindings pin wxylib/core at 39b07bb, from before
    rwarp 0.3. This is known from the m06 recheck, and still open.
16. Nothing in wxylib builds against the foundation crates' main
    branches, so a breaking change shows up only at the next version
    bump.

## 3. Seams

Four seams carry everything. Each is a plain value or a single trait.

| seam | owner | used by |
|---|---|---|
| index space: fractional (col, row), row 0 at the top, 0-based tables, half-open runs | controlledburn (`design/grid-frontends.md`) | every front end, rwarp's footprint and weights |
| `CoverageWindow` / `RowPrefix` / `Measure`: f64 coverage and integrals of small rings on a window | controlledburn | rwarp footprint, weights, cutline |
| `ForwardBatch`: arrays in place, per-point success, `near` hint | bigcurve | rwarp adapter for any `Transformer`; the curvilinear front end's world-to-index map |
| `Transformer`: arrays in place, direction flag, per-point success | rwarp | wxylib, the bigcurve adapter |

The `ForwardBatch` and `Transformer` shapes match on purpose. The
adapter is a dozen lines: copy into scratch, call `transform`, copy out.
That is why no shared types crate is needed. Coordinates cross every
seam as `f64` pairs or slices.

## 4. What to keep

- **Four repositories, four release trains.** controlledburn and
  bigcurve have R packages beside them, and rwarp has a book and a wasm
  demo. Merging them into one workspace would tie a CRAN deadline to a
  warp kernel change, and gain nothing that a version pin does not give.
- **No I/O, pure Rust, wasm builds, no unsafe** in all three, as now.
- **controlledburn stays in index space and dependency free.** Front ends
  live in rwarp (m20). The `Axis` seam (controlledburn-rs#8) stays
  closed.
- **Patches stay small and tested against an oracle**: gdalwarp for
  rwarp, the C++ header for bigcurve, the Rust crate for the C++ core.

## 5. What to change

### 5.1 controlledburn-rs is the canon, mechanically

Done in this round: the canonical tables (finding 3). A change to the
algorithm regenerates `fixtures/canon-tables.txt` in Rust, the file is
copied into the C++ repository, and the C++ change is ready when
`test_canon_tables` passes. This turns "port the strategy to C++" into a
test that fails until the port is done.

- What we get: drift between the cores becomes a CI failure on the C++
  side, with the first differing record named.
- Cost: a 250 KB file in each repository, and a copy step.
- If we did not: drift would show up as a user's bug report, as the
  corner-pass bugs did (#25), found only because the Rust property suite
  ran.

### 5.2 One controlledburn core for the bindings

The tables check the port, but every Rust-only feature still has to be
ported by hand. The alternative is that the bindings build from the Rust
crate:

- **Python first.** It is not on PyPI yet. A PyO3 module built with
  maturin replaces `_core.cpp` (353 lines) and keeps the Python API in
  `__init__.py` unchanged. The pytest suite is the acceptance test.
  Arrow input stays zero-copy through `arrow-rs` or the buffer protocol.
  It gains `CoverageWindow`, `Measure` and Rust's `crop` and coalescing.
  Its wheels are pure Rust with no dependencies, so cibuildwheel builds
  them for every platform.
- **R second.** The crate's zero dependencies make vendoring trivial
  (CRAN requires offline builds), and wxylib/r already builds Rust with
  extendr in this project. The R API stays as it is, and the cpp11 shim's
  +1 moves to the extendr shim. Do it after the 16 Nov CRAN fix, as its
  own release, with the C++ core kept in the tarball history for one
  cycle.
- **The C++ core** stays as a library for C++ users (`LinkingTo:`
  consumers, if any appear) while the canonical tables keep it honest.
  It is retired once no binding uses it.

What we get: one implementation behind three languages, Rust-only
features in R and Python, and an end to the port tax. Cost: two binding
rewrites (the Python one is small), Rust in the R build, and a CRAN
review of the new build. If we did not: every new feature (and f64
fractions in particular) is two implementations, checked by tables.
This is the one decision here that changes the goal of the C++ work, so
it is in section 9.

### 5.3 rwarp: a `mesh` module, and `warp.rs` split along its seams

- **`mesh`** holds `QuadMesh` (corner arrays, validation, `CellMap::{
  Bilinear, EqualArea}`, topology `Bounded` first), the upgraded quad
  index (hints, all matches, CSR buckets), the equal-area cell map, and
  later the walk and `burn_curvilinear`. No CRS: it builds with
  `--no-default-features`. `GeolocArrays` keeps its own inverse for GDAL
  parity, and moves onto `QuadMesh` only where the curvilinear design
  says so (area methods, stage 3).
- **The split** keeps the public API (`rwarp::warp::*`) and re-exports.
  `warp/point.rs` takes nearest and the generic, bilinear, cubic and
  lanczos kernels; `warp/sample.rs` takes `Sample` and the conversions;
  `warp/area.rs` takes average, mode and the order statistics; and
  `footprint.rs` takes `Lattice` and the shared coverage step used by
  `warp` and `weights`. It is a move, with no code changes, and its own
  PR, done when no other branch touches `warp.rs`.

What we get: the front end gets a home a burn-only consumer can build,
and the footprint becomes a module the curvilinear work can change
without reading kernel code. Cost: one large move PR (review is a diff
of moves). If we did not: the front end would land inside a 3300-line
file, or behind the `proj` feature.

### 5.4 A separate crate for the front end? Not yet

The m09 guardrail asks whether the front end should be its own crate.
Not yet. Its consumers are rwarp itself (footprint, weights), wxylib
(zonal, cover), and later the controlledburn bindings, if they want
curvilinear burns. All three can depend on rwarp without default
features. The test for a split is a consumer that wants the mesh but not
rwarp's dependencies (vaster, controlledburn). Today there is none.

### 5.5 Integration CI in wxylib

A scheduled job in wxylib/core that builds wxy-warp and runs its tests
with `[patch.crates-io]` pointing rwarp, controlledburn and bigcurve at
their `main` branches (finding 16). It fails early, and it never blocks
a wxylib PR.

### 5.6 What not to build

- No shared geometry types crate: `f64` pairs and slices cross the
  seams.
- No C ABI per crate: bindings go through wxy or through each crate's
  own language package.
- No GDAL parity work beyond what the oracles already cover. New work
  goes past GDAL (equal-area cells, conservative weights, adaptive
  edges).

## 6. Keeping the other languages working

| change | R | Python | wasm | wxy |
|---|---|---|---|---|
| canonical tables | none (test only) | none | none | none |
| crop fix | none (R crops in its binding) | none | none | none |
| bigcurve stage 2 | R package unchanged (own header; fixtures keep it in step) | none | builds (no deps) | not used yet |
| rwarp `mesh`, split | none | none | `rwarp-wasm` unchanged (re-exports) | new API, opt in |
| Python binding on Rust | none | same API, same tests, gains features | none | none |
| R binding on Rust | same API, same tests | none | none | none |

## 7. Order of work

1. **bigcurve stage 2** (PR #3). Done when merged; then release
   bigcurve 0.2.0 to crates.io (maintainer).
2. **controlledburn canon tables and crop** (controlledburn-rs#22,
   controlledburn#37). Done when merged; then a controlledburn-rs 0.2.5.
3. **rwarp `mesh` stage 1**: `QuadMesh`, `CellMap`, the equal-area map
   (forward and inverse per cell), and location with hints. Oracles:
   brute-force point in quad, the map's area identity, and the
   `grid_frontends.rs` numbers in controlledburn-rs. No change to
   existing outputs.
4. **rwarp `mesh` stage 2**: the walk, `burn_curvilinear`, rectilinear
   and affine front ends. Oracles: curvilinear-frontend.md generators 1
   to 4 and 7. Then wxylib replaces `cover.rs` with it.
5. **rwarp `bigcurve` feature**: the `ForwardBatch` adapter for any
   `Transformer`, reprojected polygons onto curvilinear grids, and
   adaptive footprint edges (m19 sec 5.4). Needs step 1's release.
6. **Exact footprint on geolocation sources** (front-end stage 3): the
   equal-area inverse for area methods, the antimeridian copies, the
   pole closure. This makes `Footprint::Exact` and the weights
   first-order conservative on curvilinear sources, which is weights
   stage 4.
7. **The `warp.rs` split** (section 5.3), whenever no branch is open on
   it.
8. **Python on the Rust crate**, then R, if section 9 says so.
9. **controlledburn 0.3.0** with the f64 decision, after the front end
   has shown what it needs.

Periodic and tripolar topology (front-end stage 4), weights stages 5 and
6 (meshes, second order), and `Geodesic` follow when a use asks for
them. E3 in m21 (ACCESS-OM2 tripolar) is the first use that will ask.

## 8. Done in this round

| PR | what |
|---|---|
| hypertidy/bigcurve-rs#3 | stage 2: `Edge` (`GreatCircle`, `Planar`), `ForwardBatch`, level-order engine; R fixtures still bitwise; 7 new tests |
| hypertidy/controlledburn-rs#22 | `crop` compiled and 0-based, property test; canonical tables for the C++ core; docs |
| hypertidy/controlledburn#37 | the C++ core checks 240 cases (6737 records) against the Rust canon, all agree |
| hypertidy/rwarp#28 | `mesh` stage 1: `QuadMesh`, `CellMap::{Bilinear, EqualArea}`, canonical ownership, hinted location; equal-area identity to 1e-9 on six meshes (non-convex and clockwise included), bilinear equal to `geo_to_pixel` |

## 9. Decisions for the maintainer

1. **Bindings onto the Rust crate** (section 5.2): Python first, then R
   (recommended); or keep the C++ core as a checked port indefinitely; or
   both bindings at once.
2. **Publish bigcurve 0.2.0** to crates.io once PR #3 is merged. It is
   the gate for step 5.
3. **The open choices in rwarp's curvilinear design** are taken at their
   recommendations, provisionally. These are `EqualArea` for coverage
   and area methods with `Bilinear` kept for point kernels, accepting
   non-convex cells with a note, refusing folds other than tripolar, and
   plain `f64` with snapping first. On public surface, `mesh` is public
   but documented as unstable until wxylib uses it.
