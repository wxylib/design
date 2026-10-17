# m04: The loftier goals, reassessed (2026-10-17)

Status: musing. An assessment, not a plan; nothing here is scheduled. It
rereads the aspirations in doc 03 section 5 and musings m01 to m03 against
what has landed, so the next choices are made with a current map
(Michael, 2026-10-17: "How do those loftier goals look now, can we
reassess").

What has landed since those documents were written: S1 to S5, S4b
(streamed mdim warp), S4c (points, interpolated points, zonal statistics
with exact coverage), S5b (curvilinear and CF coordinates), the
byte-reference table read as a virtual source with Icechunk as a sink,
Python and R spikes, the intro page, the OISST walk-through, the zonal
example and rendered previews in docs CI. Every ported GDAL piece matches
GDAL on the fixtures.

Each goal below is put in one of four groups: closer, newly reachable,
still far, or worth reframing.

## 1. Newly reachable

**The browser track (m01 2.1, wxylib/web).** Checked today:
`cargo check --target wasm32-unknown-unknown` passes for `wxy-warp`
(so the GDAL kernels, the chunked warp, curvilinear warp, points and
zonal all build for the browser), as it already did for `wxy-domain`,
`wxy-source` and `wxy-tiff`. CRS work is proj4rs, pure Rust, so EPSG
codes work in wasm without proj-wasm. Two crates still fail: `wxy-zarr`
(zarrs drops `Send`/`Sync` on wasm and `ChunkSource` requires them; the
known small fix in doc 03 section 5) and `wxy-virtual` (Icechunk pulls in
tokio's networking). So a COG warped in the browser through wxylib's
exact warp is reachable now; Zarr follows the `Send`/`Sync` fix; virtual
stores in the browser are still far.
- Get: "rendering is warping to a screen grid" shown live, not argued;
  the first consumer for m03's presentation layer.
- Cost: wasm-bindgen glue, a worker, CORS on range reads; the web repo
  goes from a stub to code to maintain.
- Without it: the claim rests on PNG figures (the OISST walk-through
  already renders a day to EPSG:3031).

**Plans as visible values (m01 2.2 and 2.9).** `WarpPlan`, `PointPlan`
and `ZonePlan` all exist and each fetches every chunk once, but they are
`Debug` and `Clone` only: not serialisable, and the CLI cannot print one.
Adding serde to the plans and a `--dry-run` (or `--plan`) to `wxy warp`,
`wxy points` and `wxy zonal` that prints chunks, bytes and overview level
as JSON is a small step.
- Get: an EXPLAIN for maps; the approve-the-plan-first flow for agents
  and scripts; a teaching aid for chunking and overviews.
- Cost: serde on plan types (and on the domain types they hold); a plan
  format that will change.
- Without it: "plans are values" stays true inside Rust only.

**A first release (doc 03 section 5, "after S4 settles").** S4 has
settled, but crates.io refuses git dependencies, and `wxy-warp` pins
rwarp by git revision while waiting for two patches. The controlledburn
hole fix is also waiting (worked around today). So the release track is
blocked on upstream, not on wxylib: the rwarp and controlledburn patches
(in the project files) landing and being released.
- Get: `cargo install wxy-cli`, then binaries and wheels; bindings that
  pin versions instead of commits.
- Cost: semver promises on young APIs (a 0.x release keeps that light).
- Without it: every user builds from git, and py and r pin core commits.

## 2. Closer

**The project topic itself.** "Cherry-pick modular GDAL concepts": the
warper and its chunking, the warp kernels, the geolocation-array
transformer, the rasterizer (centre and ALL_TOUCHED), InterpolateAtPoint
and `-ovr AUTO` are each ported, standalone and identical to GDAL. "Expand
the ecosystem": `wxy-geozarr` stands alone, controlledburn and rwarp have
patches, the refs table gained a Rust reader. "Rich docs": an intro page,
a real-data walk-through, an example with timings, a CRS guide; not yet
tutorials or explainers.

The explainers are now the cheapest lofty goal: the knowledge from each
port (how GDAL chunks a warp and scales kernels, the geolocation backmap
and hole filling, why ALL_TOUCHED differs, how `-ovr AUTO` picks a level)
is fresh and nowhere else written down, and the figures can come from the
fixtures. They belong in wxylib/docs and serve GDAL users whether or not
they use wxylib.

**Arrow interchange.** Arrow is already in the dependency tree
(`wxy-virtual` reads the Parquet refs table through arrow-array).
Points and zonal output are tables (CSV today), which makes them the
natural first Arrow outputs, reaching pyarrow, nanoarrow and DuckDB
without a binding per host.

**The flat reference table (gate 4 open topic, m02).** Answered in
practice: the mdim-refs table is read directly as a source, and Icechunk
is one sink for it. Doc 03's open topic can be closed as "table first,
Icechunk as a sink", and m02 marked done.

## 3. Still far

- **C ABI and Julia.** Nothing asks for them, and a stable C API before a
  first release would freeze young types. Park until after a release.
- **QGIS as a consumer (m01 2.8).** Needs Python bindings that open
  sources (files and URLs), not only in-memory arrays. The spikes are
  pinned at older core commits (py and r both lack points, zonal and
  curvilinear).
- **Map document and presentation (m01 2.5, 2.6, m03).** The map document
  waits on S7 (the virtual scheme), which has not started. The
  presentation schema could be written standalone like `wxy-geozarr`,
  but has no consumer until the browser track exists; that is the moment
  to revisit it.
- **Dimension navigator (m01 2.7) and inspector (m01 2.3).** Need a front
  end; the inspector could start as static explainer figures.
- **Meshes, DGGS, features (S8 and later).** Untouched, as planned.
- **PROJ.** Still proj4rs: EPSG codes, no datum grids. Parity on real
  data with datum shifts stays out of reach until
  mdsumner/rust-proj-capability settles.

## 4. Worth reframing

- **Arrow before a C ABI, and arising from outputs.** Doc 03 section 5
  names both as shared binding layers to build first. In practice Arrow
  arrives through the tables wxylib already produces (refs, points,
  zones); the C ABI waits for a release.
- **DuckDB.** "Once virtual references exist": they exist, as Parquet,
  which DuckDB reads already, so querying references needs nothing from
  wxylib. An extension would only add points and zonal as table
  functions; that is still far.
- **The operation catalogue (m01 2.4).** m01 said to consider it "just
  before S6, so that the bindings are not hand-written twice". That
  moment has arrived: the CLI has three verbs and two bindings hand-write
  the warp. The smallest form is one serialisable options type per
  operation (the same serde work as plans), which the CLI, py and r all
  map from. Worth deciding before the bindings grow past warp.
- **Doc 03 section 5's "becomes timely" column.** S4 and S6 have passed
  (S6 as spikes); the column should say what each track now waits on:
  the release blockers above for prebuilt CLI and wheels, CRAN's
  vendoring rules for R, the `Send`/`Sync` fix for the browser.

## 5. An order, when timely

Not a schedule; the order the evidence suggests if these are picked up.

1. Serialisable plans and options, with `--dry-run` (small; serves
   plans-as-values, the catalogue and the bindings at once).
2. Upstream release blockers: rwarp and controlledburn patches released,
   then a 0.x crates.io release of the workspace.
3. A browser COG warp demo in wxylib/web on `wxy-tiff` and `wxy-warp`;
   the `wxy-zarr` `Send`/`Sync` fix after it.
4. Explainers in wxylib/docs, one per ported GDAL concept.
5. Bindings that open sources, mapped from the shared options types.

S7 (the virtual scheme) remains the next large core stage, and the map
document and presentation layer follow it.

## 6. What we would get, what it costs, what if we didn't

- Get: the aspirations checked against code rather than memory, with
  one wasm check run today; two decisions surfaced that are cheap now and
  dearer later (plan and option serialisation, the release blockers).
- Cost: one more document to keep current; it is dated so it can simply
  be superseded.
- Without it: the musings drift from the code, and the release track
  stays blocked on upstream patches without anyone saying so.
