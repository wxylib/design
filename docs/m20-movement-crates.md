# m20: rwarp, controlledburn and bigcurve as wxylib's movement layer

Status: musing, 2026-10-28. Direction only; each roadmap item becomes
work in its own repository (hypertidy/rwarp, hypertidy/controlledburn-rs,
hypertidy/bigcurve-rs) or in a numbered wxylib stage. Based on rwarp at
28e3b47 (after PRs #3, #10 and #11), controlledburn-rs at 7b92c51
(0.2.2 on crates.io), bigcurve-rs at 5446a89 (stage 1 merged, stage 2
planned) and wxylib/core at 2752c6b (core #22).

**Implementation (2026-10-28):** Partly implemented. rwarp 0.2.0 and
0.3.0 are on crates.io and wxylib depends on the version (core #24,
#25). rwarp took the chunk planner and exact retry (`plan_chunks`,
hypertidy/rwarp#15; wxy-warp's `chunked.rs` deleted in core #25), GDAL's
backmap geolocation inverse (rwarp#20) and conservative weights as values
(rwarp#22, stage 1 of rwarp's `design/conservative.md`). Zonal coverage
burns holes whole on controlledburn 0.2.2 (core #25). Section 8 is the
wxylib side of the weights. Open: `geoloc.rs`, `cover.rs` and
`rasterize.rs` in wxy-warp, bigcurve stage 2, the controlledburn items.

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
  pins rwarp by git revision in core and web, bumped by hand in both.
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
| Used by wxylib | every warp method since core #22, by git revision c42d130 (web the same) | zonal `--coverage` and the cover module, 0.2.1 | not yet |

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
   checked against ESMF's weight files. wxylib/docs PR #14 ([wxylib/docs#14](https://github.com/wxylib/docs/pull/14), the nonaffine example's `esmf_oracle.py`) already has an ESMF
   conservative oracle on rotated, rectilinear and curvilinear grids.
   This is wxylib's "tables of what to do" idea (byte references,
   plans) applied to resampling.
2. **Curvilinear targets for area methods.** The geolocation
   transformer is in rwarp; the exact footprint needs the destination
   cell's outline, which for a curvilinear target is the cell's corner
   polygon (ESMF's definition) or its geolocation-interpolated outline
   (the same docs PR measured the difference against ESMF: up to 0.75% of a cell). Make the
   choice explicit, as that PR recommends: cell, edge model, measure.
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
   revisions to the version (one version to bump, not two revisions).
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
2. **Weights as a table: which schema?** Answered in section 8: rwarp's
   own unnormalised columns as Parquet, with ESMF's netCDF weight file as
   an export and an import.
3. **Does rwarp keep "GDAL" in its description?** It describes the
   lineage accurately and is hypertidy's choice; wxylib's naming rule
   applies to things wxylib publishes, not to its dependencies.

## 8. Conservative weights in wxylib

rwarp now returns conservative weights as values (hypertidy/rwarp#22):
`exact_weights` gives one entry per overlapping (target cell, source cell)
pair, with full-grid row and column indices, the overlap as an unrounded
`f64` fraction of the source cell (`frac`), and each target cell's outline
area (`dst_area`). `Weights::normalised` gives ESMF's `S` under
`FracArea` (xESMF `conserve_normed`, what `warp()` computes) or
`DestArea` (xESMF `conserve`); `Weights::apply` applies them to bands;
`esmf_row_col` gives ESMF's 1-based flattened indices; tiles concatenate
to the whole. rwarp's `design/conservative.md` sets out the rest (an ESMF
oracle suite, a spherical measure, curvilinear and periodic grids, meshes,
second order) and leaves files, CLI and stored weights to wxylib. This
section is that part.

The weights are the same kind of thing as wxylib's other tables: a list
of what to do, computed once, inspectable, and applied by anything that
can read a table. For a time series on a fixed pair of grids (a year of
BRAN2023 or GHRSST onto a model or polar grid) they are computed once and
applied 365 times.

### 8.1 One table, with ESMF's file as a view

- **Canonical: Parquet.** One file of entries, `dst_row`, `dst_col`,
  `src_row`, `src_col` (`u32`) and `frac` (`f64`), sorted by target row
  then column, with row groups by target row band so a tile reads only
  its band; and one of target cells, `dst_row`, `dst_col`, `dst_area`
  (`NaN` where the outline failed). Key-value metadata carries what makes
  the weights reusable and checkable: both grids (shape, GeoZarr
  `spatial:` transform and `proj:` CRS, or a reference to geolocation
  arrays), `densify`, the measure (planar in source pixel space until
  rwarp's spherical stage), the cell definition, the rwarp version and the
  options. Unnormalised `frac` keeps both normalisations available, so
  the choice is made when the weights are applied, not when they are
  stored. Get: the format wxylib already writes (wxy-cache) and reads
  (wxy-refs), readable by DuckDB, Arrow, pandas and R's arrow, and
  self-describing as m17 asks of stores. Cost: one more small schema,
  written down in this repository's specs when it is first written.
- **Export: ESMF's offline weight file (netCDF).** `n_a`, `n_b`, `n_s`,
  `col`, `row` (1-based, flattened), `S`, `frac_b`, `area_b`,
  `src_grid_dims`, `dst_grid_dims`: what xESMF reads back as `weights=`
  and what `ESMF_RegridWeightGen` writes. Written with the pure-Rust
  `netcdf3` crate (classic and 64-bit offset files, no libnetcdf, builds
  for wasm); check its CDF-5 support before relying on it for weight sets
  past 4 GiB per variable. CDO's and NCO's map files want SCRIP's full
  grid variables as well (centres and corners in degrees, `area_a`,
  `area_b` in steradians, masks). wxylib can compute centres and corners
  through the transformers, but areas in steradians only come with rwarp's
  spherical measure; until then the export says its areas are in source
  pixel units and leaves the SCRIP grid variables out.
- **Import: ESMF and SCRIP weight files.** Weights made by ESMF, xESMF,
  CDO or TempestRemap, read into rwarp's `Weights` (flattened indices
  split by the grid dimensions in the file) and applied by
  `Weights::apply`. This is the commit criteria's rule that producers live
  outside wxylib, applied to weights: wxylib applies anyone's weights,
  and rwarp is one producer among several.

What if we didn't: weights stay inside a warp call and are recomputed
for every time step, and wxylib's conservative warps cannot be checked
against, or replaced by, the tools climate users already trust.

### 8.2 CLI: `wxy weights`, and `wxy warp --weights`

- `wxy weights SRC --t_srs ... --te ... --tr ...` (the target arguments
  of `wxy warp`) reads only the source's grid, no pixels, and writes the
  Parquet pair (default) or `--format esmf`. `--normalize fracarea|destarea`
  applies to the ESMF export only. `--dry-run` reports the plan as `warp`
  does, with the entry count and bytes estimated from target cells times
  source cells per target cell (rwarp's note, section 3.4).
- `wxy warp SRC --weights FILE` applies stored weights (Parquet or ESMF
  netCDF) to every slice of the source, checking the grids recorded in the
  file against the source and target before reading a pixel.
- No `regrid` verb: `wxy warp -r average --exact-footprint N` already
  computes and applies in one pass, and conservative regridding is that
  plus a stored table.

Get: compute once, apply to a time series, and hand the same file to
xESMF or CDO. Cost: one verb and one flag, and grid-matching rules for
the check. If not: users wanting reuse would script rwarp themselves.

The Python and R bindings follow when they grow past warp (m09): weights
as an Arrow table, which xESMF can take as an xarray Dataset without a
file.

### 8.3 Fixtures

Two oracles, split so nothing is checked twice:

- **rwarp owns the numbers** (stage 2 of its note): weights per pair,
  `frac_b`, `area_b` and regridded fields against ESMPy, reduced to
  committed text fixtures and generated in a hypertidy image with ESMPy.
  The expected difference is part of the oracle and is not zero even for
  regular longitude-latitude grids, because ESMF treats every cell edge,
  parallels included, as a great circle. The zero-difference gate is a
  Cartesian twin of each case: ESMF run with `CoordSys.CART` on the same
  corners has exactly rwarp's equal-area curvilinear cells (straight
  quadrilaterals, planar area), so those pairs must agree to rounding.
  wxylib/docs PR #14 already ran ESMPy 8.9 in CART mode and found the
  world-space clip within 1e-13.
- **wxylib/fixtures owns the files and a real case**: an ESMF weight file
  written by `wxy weights` read by xESMF and applied, field equal to
  `wxy warp --weights` on the same file; a file from
  `ESMF_RegridWeightGen` imported and applied by wxy, field equal to
  xESMF's; and GHRSST MUR (0.01 degree) onto a 0.25 degree grid,
  conservative, against xESMF, as the first real-data case.

Both run in one image, a leaf of hypertidy/gdal-r-ci:
`gdal-r-python-esmf`, built FROM `gdal-r-python:latest` with ESMF 8.9.1
from source (`ESMF_COMM=mpiuni`, against the image's libnetcdf),
`ESMF_RegridWeightGen` on the path, and ESMPy and xESMF in the same venv
as `osgeo.gdal`; TempestRemap as an optional second oracle. It is
`:latest` only. The GDAL oracles stay on `gdal-r-python:dev`; the ESMF
generators write their grids' corner coordinates into the fixtures, so
the tests read the corners ESMF used and do not depend on the image's
PROJ. A conda-forge environment (an `esmf` environment in gdal-r-ci's
pixi image) is the fallback if the source build is troublesome. The
choice and the rest of the options are in the image's own README.

### 8.4 Order

1. Parquet writer and `wxy weights` with `--dry-run`, in a `wxy-weights`
   crate or a `weights` module of wxy-warp (the crate check of m09
   section 5 decides: a geo-free Parquet layer would be its own crate).
2. `wxy warp --weights` for Parquet, over every slice.
3. ESMF netCDF export and import (`netcdf3`); the fixtures round trips.
4. The GHRSST real-data case against xESMF.
5. After rwarp's spherical measure: areas in steradians and the full
   SCRIP grid variables, so CDO and NCO read the export too.

## 9. The GPU path beside rwarp

Browser maps in any CRS draw rasters by a mesh warp: a grid of
triangles in display space, each vertex given texture coordinates by the
inverse projection, the GPU interpolating linearly inside each triangle.
It is approximate by construction (the error is the curvature inside a
triangle) and fast enough to redraw while panning. rwarp is the exact
engine; the two are complementary, and neither replaces the other.

Two implementations now exist:

- **The ortho-cog-viewer and wgis mesh engine**, with refinement by
  screen-pixel texture error, the map edge found by bisection and
  classified as a limb, a cut or a hole, and poles handled in periodic
  textures; rwarp already serves it as the exact warp.
- **math.gl 5.0.0-beta.1** (visgl/math.gl#367, #368): the same mesh plus
  texture warp, packaged as a renderer-neutral npm module with a CRS
  resolver over proj-wasm (batched in a worker) and mesh clipping that
  keeps provenance. deck.gl layers will use it once per-view CRS
  (visgl/deck.gl#10874) lands. Its Antarctic pole fixture is currently
  wrong, which is the case the wgis pole handling covers.

### 9.1 Decisions

1. **Should the browser mesh core target math.gl's mesh and CRS types,
   or stay separate and be compared?** Recommended: stay separate while
   math.gl is in beta, and keep the core's output to plain typed arrays
   (positions, texture coordinates, triangle indices, a parent index per
   triangle) so an adapter to math.gl's types is a few lines when it
   settles. Compare the two on one shared case set (the Antarctic pole,
   an orthographic limb, an antimeridian cut, a hole in the source),
   scored against rwarp (9.2). Revisit when math.gl 5.0 is released and
   deck.gl#10874 is merged. Get: no tracking of a moving API, and a
   measured answer when the choice is made. Cost: a second
   implementation lives on for now. If not: either the core is rewritten
   to a beta API, or the comparison is never made and the better
   refinement stays unknown to the ecosystem.
2. **Should the wgis edge and pole handling be offered upstream?**
   Recommended: yes, first as an issue on math.gl with the pole fixture's
   failure reproduced, the bisection and pole approach described, and a
   pull request offered if the maintainers want one. This is the
   upstream-first principle of doc 04: the packaged module is where
   deck.gl users will get their warp, so a fix there reaches more people
   than a separate engine does. Making that contact is for the wgis
   maintainer.

### 9.2 What rwarp offers the GPU path

An oracle. A mesh warp's error is the difference between its frame and
an exact warp of the same view, and rwarp computes the exact warp in the
browser too (`rwarp-wasm`, nearest or bilinear, the same transformer).
So one harness can score any mesh engine, wgis or math.gl, in screen
pixels of texture error per case: the measurement behind 9.1's
comparison, and a test either project could adopt. Nothing in rwarp
changes for it. Where the mesh needs exactness (a measured overlay, a
conservative regrid), the answer stays rwarp, not a finer mesh.

Roadmap additions: wxylib/web gains the comparison page (the case set,
both engines, the rwarp difference image); rwarp gains nothing new.
