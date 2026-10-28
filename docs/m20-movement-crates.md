# m20: rwarp, controlledburn and bigcurve as wxylib's movement layer

Status: musing, 2026-10-28. Direction only; each roadmap item becomes
work in its own repository (hypertidy/rwarp, hypertidy/controlledburn-rs,
hypertidy/bigcurve-rs) or in a numbered wxylib stage. Based on rwarp at
28e3b47 (after PRs #3, #10 and #11), controlledburn-rs at 7b92c51
(0.2.2 on crates.io), bigcurve-rs at 5446a89 (stage 1 merged, stage 2
planned) and wxylib/core at 2752c6b (core #22).

## Summary

The question: what is left in each of the three crates, what could each
become, and how should they divide the work so they serve wxylib's aims
(modules that do not yet exist, not GDAL parity; lean; leverage existing
crates)?

- **Together they are a layer, not three projects.** rwarp moves grids
  to grids, controlledburn moves shapes to cells, bigcurve moves shapes
  between spaces, and vaster does the grid arithmetic underneath. None
  of them reads a byte or knows a format. wxylib owns everything with
  I/O in it (bytes, tables, plans as stored artefacts, CLI, bindings) and
  consumes this layer. Doc 03's layer rule, applied one level down.
- **They meet in index space.** Every one of them works best in
  fractional (column, row) coordinates: controlledburn's window and
  prefix sums already do, rwarp's transformers map into it, bigcurve's
  tolerance is naturally a fraction of a cell. Making index space the
  stated common currency, and a batched forward map the one seam, lets
  each grow without depending on the others.
- **Parity work is nearly done; the new work is where they go past
  GDAL.** rwarp matches gdalwarp cell for cell in most kernels. What no
  library offers in a light, wasm-ready form is exact conservative
  remapping onto any grid (affine, rectilinear, curvilinear), with the
  weights available as a table, and exact polygon measures on the same
  grids. That is what the three are close to, between them.
- **wxylib carries about 2300 lines that belong below it.** `wxy-warp`
  has its own GDAL-parity chunk planner and exact retry (`chunked.rs`),
  GDAL's backmap geolocation inverse (`geoloc.rs`), GDAL's
  centre-and-all-touched rasterizer (`rasterize.rs`) and the
  index-space and world-space cover (`cover.rs`). Each is a
  general-purpose piece wearing a wxy name. Moving them down is the
  crate check of m09 section 5 applied after the fact.
- **Releases unblock wxylib's pins.** controlledburn 0.2.2 is published.
  rwarp's 0.2.0 has every dependency on crates.io now (proj4rs 0.3.0,
  controlledburn 0.2.2), yet crates.io still serves 0.1.1, so wxylib
  pins rwarp by git revision, and core and web pin different ones.
  bigcurve is unpublished and should stay so until its edge-model API
  (stage 2) is fixed.
- **Keep them in hypertidy.** Each is useful outside wxylib, has an R or
  C++ sibling and its own oracle. Moving them into wxylib would make
  them look like parts of wxy. wxylib's job is to be their most demanding
  consumer.

Short roadmaps per crate are in section 6.

![The movement layer: rwarp, controlledburn, bigcurve and vaster below
wxylib, meeting in index space](img/m20-crates.svg)

## 1. Where each stands

| | rwarp | controlledburn-rs | bigcurve-rs |
|---|---|---|---|
| Job | GDAL's warp pipeline without I/O: transformers (CRS, approximate, GCP, geolocation arrays), source windows and chunk lists, point kernels, area methods | polygons, lines and points to cells with exact coverage; sparse runs and edge tables | adaptive densify: vertices only where a forward map bends an edge, judged in the target plane |
| Size | about 6000 lines, plus `rwarp-wasm` and an mdbook | about 3400 lines, an mdbook, design notes | about 500 lines |
| Verified against | gdalwarp (GDAL 3.14dev for kernels, 3.8.4 for geolocation), fixtures committed | the C++ controlledburn's golden tables (28 cases, bitwise), properties at 10000 cases | the C++ bigcurve header run with PROJ, forward calls recorded and replayed (bitwise on linux-gnu) |
| crates.io | 0.1.1; 0.2.0 on main, unreleased | 0.2.2 (2026-10-28) | unpublished, name free |
| Dependencies | vaster, controlledburn, proj or proj4rs, optional half | none (serde, geo-types optional) | none |
| wasm | yes with proj4rs; browser demo on its book | yes | yes |
| Used by wxylib | every warp method since core #22, by git revision c42d130 (web: 4f1ab19) | zonal `--coverage` and the cover module, 0.2.1 | not yet |

Recently landed: rwarp's 0.2 API (`warp()` with `WarpOptions`, area
methods, mode ties, per-band nodata, separate source and output types,
geolocation transformers), the shared lattice and coverage window for
the exact footprint (rwarp #11, m19), and the approximate transformer
fix (#10); controlledburn's hole and wall-cell fixes and the
`CoverageWindow` and `RowPrefix` module (#13); bigcurve's faithful port
(#1) and a stage 2 plan with rwarp as first consumer (#2).

Open and known, from those threads and the code:

- rwarp: the exact retry for points just off the source (wxy-warp has
  it, rwarp does not); the exact footprint at the antimeridian; window
  padding for a fixed kernel scale; an integral path for average and RMS;
  adaptive densify; GDAL bug candidates it could carry the fix for
  (chunk-offset scale, already fixed; antimeridian last column, #6478).
- controlledburn: the `Axis` seam for rectilinear grids (branch
  `grid-geometry-stage1`, exploratory); reuse of burn scratch (about 40%
  of the burn's instructions are allocation, m19); the C++ port of the
  hole fix and the window; DE-9IM and topology as design notes only.
- bigcurve: stage 2 (edge-model trait, `Planar`, batched forward map),
  stage 3 adapters, then consumers.

## 2. What the three are, together

GDAL has no name for this layer because it never separated it: the warp
operation, the rasterizer, the cutline code, the geolocation transformer
and `OGRGeometry::segmentize` each hold a piece, with I/O threaded
through. Split out, the pieces are four questions:

| Question | Crate | Input | Output |
|---|---|---|---|
| Where is this cell, in that grid? | vaster (affine), rwarp transformers (everything else) | cell indices, a grid description | fractional indices in another grid |
| How many vertices does this edge need over there? | bigcurve | an edge, a forward map, a tolerance | vertices, with parents |
| Which cells does this shape cover, and how much? | controlledburn | a ring in index space | runs and fractions, or a dense window, or a boundary integral |
| What value does that cell get? | rwarp kernels and area methods | a source buffer, a transformer | a destination buffer |

The fourth question is the one GDAL answers. The first three are what
make the fourth exact on grids GDAL handles approximately (the box
footprint, vertex-only cutlines) or not at all (a curvilinear target for
area methods).

### 2.1 Boundaries

Rules that keep the layer lean, each with a reason:

- **controlledburn stays dependency-free and in index space.** It takes
  rings in cell coordinates (or a regular `GridSpec`) and knows nothing
  of CRSs, transformers or curves. Get: it ports line for line to C++,
  so the R and Python packages stay in step; it builds anywhere. Cost:
  every non-regular grid needs a front end outside it. If not: it grows
  a transformer trait, and the C++ sibling cannot follow.
- **bigcurve stays dependency-free and owns the forward-map trait.** Its
  stage 2 batched map (slices in, per-point success out) has the shape of
  rwarp's `Transformer::transform`. rwarp implements bigcurve's trait for
  its transformers behind a feature, not the other way round. Get: the
  smallest crate holds the seam, and anything with a forward map (a
  closure, PROJ, a geolocation array) can be densified. Cost: an adapter
  in rwarp. If not: a fourth crate for one trait, or bigcurve depending on
  rwarp's types.
- **rwarp is where the three compose.** It already depends on
  controlledburn and vaster and holds every transformer, so the grid
  front ends that need all three (a polygon onto a curvilinear grid, an
  exact footprint with adaptive edges) live in rwarp or in its consumers,
  never in controlledburn. Get: one place where a grid's description
  meets exact coverage. Cost: rwarp grows a coverage-facing API beside
  the warp. If not: wxy-warp keeps doing it (section 3), useful to nobody
  else.
- **No plan formats or I/O below wxylib.** rwarp can return a plan as a
  value with serde derives; storing, costing and executing plans against
  bytes is wxylib's (m05, m06). Get: rwarp stays a library. If not: rwarp
  becomes cogcache again.

### 2.2 The seam: index space and a batched forward map

The three crates already agree on index space without saying so:

- `CoverageWindow` and `RowPrefix` take rings in cell index space
  (column `i` spans `[i, i + 1]`, row 0 at the top).
- rwarp's transformers map destination pixel and line to source pixel and
  line: index space to index space.
- bigcurve's tolerance has a natural unit in index space, a fraction of a
  cell, the same for every grid and CRS (m12).

A grid of any rung of the ladder (doc 02) is then whatever maps world
coordinates to its index space: an affine is a 2 x 3 matrix, a
rectilinear grid two monotone searches, a curvilinear grid rwarp's
geolocation inverse. That is a transformer. So the layer needs no new
grid-description type: the transformer is the grid's description for
the purpose of moving things onto it. m07 (index space and coordinate
space) is the background.

Stating this in each crate's docs costs a paragraph and stops each from
inventing its own convention (y up in controlledburn's `GridSpec`, y down
in its window, pixel corners versus centres in transformers).

## 3. What wxylib carries that belongs below

From `wxy-warp` at core 2752c6b:

| Module | Lines | What it is | Proposed home |
|---|---|---|---|
| `chunked.rs` | 534 | GDAL 3.14's chunk list, source window with fill ratio, per-chunk kernel scale, and the exact retry (`Retry`) | rwarp: a `plan_chunks` that returns chunks as values, and the retry inside `warp()` when it is given the exact transformer beside the approximate one. rwarp's own `collect_chunk_list` and this port should become one |
| `geoloc.rs` | 1039 | GDAL 3.12's geolocation transformer with its float32 backmap, ported in GDAL's arithmetic order for cell parity | rwarp: as an inverse option (`Backmap`) beside its quadrilateral index (`rwarp::geoloc_transform`), so parity with gdalwarp is a choice, not a second implementation |
| `rasterize.rs` | 307 | GDAL's centre rule and all-touched rule from `llrasterize.cpp` | controlledburn: approx mode is already the centre rule (fasterize semantics); an all-touched mode in index space is small. Check first whether approx equals GDAL on centre ties |
| `cover.rs` | 411 | index-space burn with densify, and world-space clip of cell outlines, for non-affine grids | rwarp (the composition point, section 2.1), with densify by bigcurve once stage 2 lands |
| `zonal.rs` | part | per-ring burns to work around controlledburn 0.2.1's hole bug | delete: 0.2.2 has the fix; small polygons can use `CoverageWindow` |

What we get: wxy-warp shrinks to glue (reading chunks, batching
polygons by chunk, CLI shapes), and every piece becomes usable from R,
Python or the browser through the crate that owns it. What it costs:
each move is a PR to a hypertidy repo with its tests, and wxylib's
oracles must still pass after the switch (they are the check that the
move kept parity). What if we didn't: wxylib holds the most complete
GDAL-parity warp planner in Rust where no one else can reach it, and two
implementations of geolocation and chunking drift.

Order: the zonal workaround first (a version bump), then `chunked.rs`
(it is what makes rwarp's output equal gdalwarp's for a whole raster,
not one window), then `geoloc.rs`, then `cover.rs` once bigcurve's
stage 2 exists.

## 4. What each could become

### 4.1 rwarp: a conservative regridder, with GDAL parity as its floor

GDAL's warp is the reference and rwarp now meets it. The step beyond is
the exact footprint, which is first-order conservative remapping (m19):
each destination cell's value is the area-weighted mean of the source
cells it overlaps, with areas measured exactly in source index space.
That is what xESMF and ESMF provide for climate grids, through a large
Fortran and C++ stack; in Rust, or in the browser, nothing does.

Three pieces turn rwarp's exact footprint into a regridder:

1. **Weights as a table.** For a fixed pair of grids the weights do not
   change. Return them as a sparse table (destination cell, source cell,
   weight), so they can be stored, inspected and applied by anything (a
   sparse matrix in NumPy or R, a join in DuckDB, a GPU kernel), and
   checked against ESMF's weight files. docs #14 already has an ESMF
   conservative oracle on rotated, rectilinear and curvilinear grids.
   This is wxylib's "tables of what to do" idea (byte references,
   plans) applied to resampling.
2. **Curvilinear targets for area methods.** The geolocation
   transformer is in rwarp; the exact footprint needs the destination
   cell's outline, which for a curvilinear target is the cell's corner
   polygon (ESMF's definition) or its geolocation-interpolated outline
   (docs #14 measured the difference against ESMF: up to 0.75% of a cell). Make the
   choice explicit, as docs #14 recommends: cell, edge model, measure.
3. **The integral path.** `RowPrefix` gives average and RMS in time
   proportional to the perimeter (m19 section 5.3). With weights stored,
   it matters for the first application only; without stored weights, it
   is the fast path.

Get: a light, verified, wasm-capable conservative regridder, which is a
module that does not yet exist, not a GDAL feature reproduced. Cost: an
API for weights and cell definitions; more oracle cases (ESMF beside
GDAL). If not: rwarp is a good gdalwarp port and the exact footprint stays
an option few people find.

Second-order conservative remapping (gradients per source cell) is a
later step and needs nothing from the others; leave it as a note.

### 4.2 controlledburn: exact cell measures, for any consumer

controlledburn is the exact version of "which cells, how much", and is
already shared by R, Python and Rust through its C++ and Rust cores. It
has two engines now: `burn` for many polygons on a large grid (sparse
output, cost by perimeter) and the window and row prefix for one small
ring (dense, allocation-free). What it could become:

- **The single answer for coverage in index space**, with a front-end
  contract written down: the caller brings rings in index space, densified
  as needed; controlledburn returns exact planar area in that space. The
  `Axis` seam (exploratory branch) is the one question left in that
  contract: whether rectilinear grids are cut at their walls inside
  controlledburn (exact, and cheap since walls are known) or moved to
  index space outside it (a monotone map per axis, piecewise linear, so
  exact too if vertices are added at each wall). Recommendation: outside,
  as a front end in rwarp, so controlledburn keeps a unit-cell grid and
  the C++ port stays small. Cutting at walls is a vertex insertion, not a
  burn change.
- **A burner that reuses its scratch.** About 40% of a small burn is
  allocation. A `Burner` holding its hash map and arenas across calls
  helps zonal statistics over many small polygons, where `CoverageWindow`
  does not apply (it needs one ring at a time and a dense window).
- **Relations, when asked.** The DE-9IM per cell and shared-arc topology
  notes are sound and stay notes until a consumer (zonal "touches", a
  partition check) asks.

Get: one exact coverage engine with three languages and clear inputs.
Cost: front ends live elsewhere, which is a documentation burden. If not:
coverage on non-regular grids stays in wxy-warp, where only wxy can use
it.

### 4.3 bigcurve: the honest-edges step wherever a shape changes space

bigcurve is small and should stay small. Its uses, all outside it:

- rwarp's exact footprint: refine only lattice edges whose sagitta
  exceeds a fraction of a source cell (m19 section 5.4), through the
  exact transformer;
- polygons into the index space of a curvilinear or reprojected grid,
  for controlledburn (m12, the grid front-ends note);
- drawing: wxylib/web's edit canvas densifies geodesic edges in its own
  JavaScript today (m18); a wasm build of bigcurve with a `Geodesic` edge
  model would serve it and the warp demo's outlines;
- source windows and extents, opt-in, with containment guaranteed.

Get: one tested answer to "how many vertices does this edge need
there", replacing fixed densify counts in four places. Cost: stage 2's
trait design, which decides the published API. If not: each consumer
picks a fixed densify, wasting points where the map is flat and missing
curvature where it is not.

## 5. Cross-cutting

- **Oracles: one convention, not yet a crate.** The three crates already
  share a shape: run the reference once (gdalwarp, the C++ core, the C++
  header with PROJ), commit its output, and test against it without the
  reference installed. bigcurve goes furthest, recording every forward
  call so tests replay PROJ without linking it. m09 section 6 proposed a
  GDAL oracle harness as a crate; these three are its first test cases
  and show its variety. Recommendation: write the convention down (a
  `fixtures/README` in each: which reference, which version, how to
  regenerate, in which CI image; ghcr.io/hypertidy/gdal-r-python:dev for
  GDAL) and extract a crate only when two of them want the same helper.
- **wasm in CI.** All three build for `wasm32-unknown-unknown`;
  rwarp's CI and Pages workflows build it. controlledburn and bigcurve
  should add a one-line `cargo build --target wasm32-unknown-unknown`
  job, since the browser is where wxylib shows them off.
- **Bindings stay with the C++ and R siblings.** controlledburn and
  bigcurve already have C++ cores in R packages, and controlledburn a
  Python package. The Rust crates are canonical (with C++ port notes) and
  the committed fixtures keep the languages in step. Linking R packages to
  the Rust crates waits on wxylib's commit criterion 3 (CRAN and Rust);
  until then, nothing changes for R users.
- **Licences follow lineage.** rwarp is MIT OR Apache-2.0, controlledburn
  Apache-2.0 (exactextract), bigcurve MIT (d3-geo notice). All are
  compatible with each other and with wxylib; no change needed.
- **Home.** Keep all three in hypertidy. A move to the wxylib org would
  say they are parts of wxy, which section 2.1 says they are not.

## 6. Roadmaps

Short, ordered, each item a PR or a release. "wxylib" items are in
wxylib repos.

### rwarp

1. Release 0.2.0 on crates.io; wxylib core and web switch from git
   revisions to the version (one pin, no drift between core and web).
2. wxylib: bump wxy-warp to rwarp main (28e3b47: exact footprint 2 to 6x
   faster, approximate transformer fix), with the oracles as the check.
3. Absorb the exact retry and GDAL's chunk planning from wxy-warp's
   `chunked.rs` (section 3); a plan type with serde derives.
4. Geolocation backmap inverse as an option, from wxy-warp's `geoloc.rs`.
5. Exact footprint: antimeridian, integral path for average and RMS,
   adaptive edges through bigcurve (feature).
6. Weights as a table for the exact footprint; ESMF oracle cases beside
   GDAL's; curvilinear targets for area methods.
7. Carry fixes ahead of GDAL where gdalwarp looks wrong (antimeridian
   last column), as options documented on the parity page.

### controlledburn-rs

1. wxylib: bump to 0.2.2, delete the per-ring hole workaround in zonal,
   use `CoverageWindow` for small polygons in cover and zonal.
2. C++ ports of the hole and wall-cell fixes and of the window module,
   golden tables regenerated together.
3. Decide the `Axis` seam (recommended: no, rectilinear is a front end
   outside) and close the branch with a note in the grid front-ends
   design doc.
4. A reusable `Burner` (scratch kept across calls); the
   `perf/reserve-output-capacity` branch is a start.
5. All-touched mode in index space, if section 3's rasterize move goes
   ahead.
6. A wasm build job in CI.

### bigcurve-rs

1. Stage 2: edge-model trait, `Planar`, batched forward map. Then publish
   0.1.0.
2. rwarp feature `bigcurve`: adaptive refinement of the exact
   footprint's lattice edges, measured against fixed densify on m19's
   cases.
3. Stage 3: `geo-types` adapter; the curvilinear index-space example.
4. `Geodesic` edge model (geographiclib-rs, feature) and a wasm build
   for wxylib/web's edit canvas.
5. A wasm build job in CI.

## 7. Questions

1. **Should the composition point be rwarp, or a fourth crate?**
   Recommended: rwarp, until a consumer wants transformers and coverage
   without kernels. Then split rwarp's transformers into their own crate
   along the module line that already exists.
2. **Weights as a table: which schema?** Recommended: the three columns
   ESMF and xESMF use (row, column, weight, 0-based indices into the
   flattened grids) as Arrow or Parquet, so existing tools read them.
   A spec in wxylib/design only if it gains columns.
3. **Does rwarp keep "GDAL" in its description?** It describes the
   lineage accurately and is hypertidy's choice; wxylib's naming rule
   applies to things wxylib publishes, not to its dependencies.
