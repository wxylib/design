# wxylib/design

Design notes, surveys and staging plans for wxylib: Rust tooling that takes
the modular concepts GDAL already contains, gives each one its own home, and
builds an ecosystem of crates, bindings and documentation around them.

New to wxylib? Start at **https://wxylib.org/docs/**: what works, how-tos,
explainers and how to help. These documents are rendered there too, under
[Design](https://wxylib.org/docs/design/README.html).

Nothing here is code. Each document ends in a gate: a decision to accept,
revise or reject before the next document starts.

![The R0 to R6 raster-vector spectrum that doc 02 builds the data model on](https://raw.githubusercontent.com/wxylib/docs/main/img/spectrum.svg)

## Principles

- Slow incremental steps that are productive, consistent, modular and
  extensible.
- Separate planning, reading and computing. A plan can be inspected,
  serialised and costed before any pixel is touched (the rwarp model).
- Leverage existing crates (object_store, async-tiff, zarrs, proj, proj4rs,
  vaster) where they fit. Build only what has no good home.
- GDAL is the inspiration, the test oracle and, for now, a workaround we
  may call, never the basis. If we reach for functionality before we have
  the foundation for it, we stop and build the foundation. Nothing we
  publish carries "gdal" in its name.
- Virtualisation is the default pathway for formats. A format we need gets
  a scanner that emits chunk references (byte ranges plus codecs) readable
  as virtual Zarr, rather than a reader of its own. This bridges to future
  format standardisation and defers legacy complexity; GDAL and other tools
  may serve as scanners where nothing else exists.
- Every module, design choice and stage carries a rationale: what we get,
  what it costs, and what happens if we don't do it.

## Plan

| Step | Document | Gate |
|------|----------|------|
| 1 | [Module survey](docs/01-module-survey.md) | Agree the module map (passed 2026-10-16) |
| 2 | [One data model, from raster to vector](docs/02-data-model.md) | Accept core types and traits (provisional) |
| 3 | [Architecture and staged roadmap](docs/03-architecture.md) | Pick the first implementation stage (S1 chosen, provisional) |
| 4 | [The landscape: related work, what to leverage, what to track](docs/04-landscape.md) | Upstream-first, Icechunk refs, browser CRS, conventions work (passed 2026-10-16) |
| 5 | [Pain points in GDAL, R and Python](docs/05-pain-points.md) | S4b mdim warp, curvilinear after S5, an extraction stage, no global state (passed 2026-10-16) |

Whether wxylib earns a long-term commitment is tested by four
[commit criteria](docs/commit-criteria.md), with their live status.

Which stages are built is kept in one place, doc 03's
[stages section](docs/03-architecture.md#3-stages); what they add up to
for a user is on the [capability map](https://wxylib.org/docs/capabilities.html).

## Musings

Blue-sky side notes, not plans and not gated. A musing becomes work only
by being picked up into a numbered document.

- [m01: Downstream UX](docs/m01-downstream-ux.md): what front ends (a
  modular QGIS among them) could do with the core's pieces, and which
  doors the core should keep open for them.
- [m02: Pilot, a byte-reference table as a wxy-virtual source](docs/m02-pilot-mdimrefs.md):
  the mdim-refs/0.2 table (OISST) through `wxy-virtual` into Icechunk,
  checked against GDAL; a trial of the gate 4 "table first" question.
- [m03: Presentation on raw data, and the map as a document](docs/m03-presentation-and-map-format.md):
  image scaling that travels with untouched values, and a map that
  references its sources (from doc 05, X1 and X2).
- [m04: The loftier goals, reassessed](docs/m04-lofty-goals-reassessed.md):
  doc 03 section 5 and m01 to m03 checked against what has landed
  (2026-10-17): what is closer, newly reachable, still far, or worth
  reframing.
- [m05: The chunk cache as a growing implicit store](docs/m05-chunk-cache.md):
  keeping the encoded bytes of every chunk a run reads (and, after a warp,
  a record of every target chunk) beside the byte-reference rows, so a
  store accumulates without dictating a format; ends with a range-cache
  pilot.
- [m06: Response to the foundation assessment](docs/m06-foundation-assessment-response.md):
  the cogcache/blocklist review of wxylib checked point by point against
  the repos; proposes a flat refs store (table first, with the cache
  inside), a Bluelink-shaped fixture, and changes to C1 and S7.
- [m07: Index space and coordinate space](docs/m07-index-space.md):
  the playproj pages (ROMS, rotated pole, cubed sphere, geostationary and
  more) placed on the ladder, the gaps they show (computed vertical
  positions, periodic and folded index, patches, stored frames) and five
  small Zarr fixtures to pin them.
- [m08: Point clouds, lidar and PDAL on the ladder](docs/m08-point-clouds.md):
  point clouds as R6 on an R1 lattice with an R4 octree chunk scheme
  (COPC), scans as R1 or R3 in the sensor frame, COPC as already virtual,
  the Rust crates (las, laz, copc-streaming), and a stance: ladder moves
  and planned reads, PDAL as oracle, no processing toolkit (all six
  questions answered as recommended, 2026-10-18).
- [m09: The modules that don't exist yet](docs/m09-missing-modules.md):
  the CLI as an operation registry (GDAL's `gdal` framework, what clap
  lacks, a geo-free crate that generates CLI, py and r), VSI through
  object_store, its registry and async-tiff's reader seam, the two real
  gaps (byte views and a chain grammar), a "crate check" before each
  stage, and GDAL's other infrastructure (configuration, progress,
  threads, CRS naming, time, plugins, testing) through the same lens.
- [m10: Overlapping COG mosaics, measured on REMA v2 and COP30](docs/m10-overlapping-mosaics.md):
  overlap, variable chunk sizes and padded tiles as three problems; the
  tile-edge and origin cuts as duals; on REMA v2 2 m 96 percent of chunks
  stay references and the pyramid breaks at level 3; COP30 ships on two
  grids; the predictor codec (with an encoder) is the first blocker.
- [m11: Quiet operations](docs/m11-quiet-operations.md): what composite
  raster readers do without saying so (painting order, baked resampling,
  registration, level substitution), a ladder from hidden to separated
  rendering, and REMA v2, COP30 and Sentinel-2 as the fixtures that
  expose them. Source table in [measurements/cop30/](measurements/cop30/).

## Reference specs

Specs from adjacent work that the design documents refer to. Not wxylib
formats.

- [mdim-refs/0.2](specs/mdim-refs-0.2.md): a byte-reference table built
  from a `gdal mdim mosaic` VRT (SQLite; Parquet and kerchunk exports).

## Related repositories

- [hypertidy/rwarp](https://github.com/hypertidy/rwarp): the warp core
  (transformers, source window planning, kernels). No I/O. A candidate for
  transfer into wxylib, pending.
- [hypertidy/regular-in-what](https://github.com/hypertidy/regular-in-what)
  and [hypertidy/playproj](https://github.com/hypertidy/playproj): the
  grid concepts (regular in a frame, the ladder, index space) behind doc 02.
- [mdsumner/rust-proj-capability](https://github.com/mdsumner/rust-proj-capability):
  the survey of CRS crates. The CRS backend decision defers to it.
- [hypertidy/vaster-rs](https://github.com/hypertidy/vaster-rs): grid
  arithmetic with no dependencies.
- [developmentseed/async-tiff](https://github.com/developmentseed/async-tiff),
  [zarrs/zarrs](https://github.com/zarrs/zarrs),
  [developmentseed/zarrista](https://github.com/developmentseed/zarrista):
  I/O models to align with.
- [earth-mover/icechunk](https://github.com/earth-mover/icechunk) and
  [VirtualiZarr](https://github.com/zarr-developers/VirtualiZarr): the
  virtual-reference store and parser contract (doc 04).
- [zarr-conventions](https://github.com/zarr-conventions): the `spatial:`,
  `proj:` and `multiscales` conventions behind GeoZarr (doc 04).

## License

MIT OR Apache-2.0, matching rwarp and the crates we build on.
