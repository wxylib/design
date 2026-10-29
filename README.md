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

Side notes, not plans and not gated. A musing becomes work only by being
picked up into a numbered document. Some end in questions; where those
have been answered, the status says so and the musing records the
decisions.

Status says how much of a musing is built, checked against the merged
work in core, fixtures, docs and web (2026-10-28). Each musing repeats
its line, with links, under its own status:

- **Implemented**: what the musing proposed for wxylib is merged.
- **Partly implemented**: some of it is merged; the rest is listed.
- **Decided, not built**: its questions are answered; no stage has
  started.
- **Open**: nothing proposed is built yet.
- **Assessment**: a review or measurement that proposes no build of its
  own.

| Musing | About | Status |
|--------|-------|--------|
| [m01: Downstream UX, blue sky](docs/m01-downstream-ux.md) | What front ends (a modular QGIS among them) could build from the core, and which doors the core keeps open for them | Partly implemented: plans you can see, rendering as a warp (web demos); catalogue, map document and navigator open |
| [m02: Pilot, a byte-reference table as a wxy-virtual source](docs/m02-pilot-mdimrefs.md) | The mdim-refs/0.2 table (OISST) through `wxy-virtual` into Icechunk, checked against GDAL | Implemented: [fixtures #1](https://github.com/wxylib/fixtures/pull/1), [core #2](https://github.com/wxylib/core/pull/2), walk-through on the [docs site](https://wxylib.org/docs/oisst-virtual.html) |
| [m03: Presentation on raw data, and the map as a document](docs/m03-presentation-and-map-format.md) | Image scaling that travels with untouched values, and a map that references its sources (doc 05, X1 and X2) | Open; nothing built |
| [m04: The loftier goals, reassessed](docs/m04-lofty-goals-reassessed.md) | Doc 03 section 5 and m01 to m03 checked against what had landed by 2026-10-17 | Assessment; three of the four items in its section 5 order done |
| [m05: The chunk cache as a growing implicit store](docs/m05-chunk-cache.md) | Keeping the encoded bytes of every chunk a run reads beside the byte-reference rows, so a store accumulates without dictating a format | Implemented (pilot C1, `wxy-cache`, inside S3c); T1 and the `copy` state open |
| [m06: Response to the foundation assessment](docs/m06-foundation-assessment-response.md) | An outside review of wxylib checked point by point; proposes the flat refs store with the cache inside, and a Bluelink-shaped fixture | Partly implemented: section 6 built as S3c (`wxy-refs`); Bluelink CI fixture, binding pins and scale open (section 8) |
| [m07: Index space and coordinate space](docs/m07-index-space.md) | The playproj grids placed on the ladder, the gaps they show, and five small Zarr fixtures to pin them | Partly implemented: fixtures I1 and I3; I2, I4, I5 and the vertical mapping open |
| [m08: Point clouds, lidar and PDAL on the ladder](docs/m08-point-clouds.md) | Point clouds as R6 on an R1 lattice with an R4 octree chunk scheme (COPC), the Rust crates, and a stance: ladder moves, PDAL as oracle, no processing toolkit | Decided 2026-10-18 (all six as recommended); not built |
| [m09: The modules that don't exist yet](docs/m09-missing-modules.md) | The CLI as an operation registry, VSI through object_store, byte views and a chain grammar as the real gaps, a crate check before each stage, and GDAL's other infrastructure | Open: five questions with recommended answers; none taken up |
| [m10: Overlapping COG mosaics, measured on REMA v2 and COP30](docs/m10-overlapping-mosaics.md) | Overlap, variable chunk sizes and padded tiles as three problems; tile-edge and origin cuts as duals; the predictor codec as the first blocker | Open, measured; one prerequisite in (`wxy-predictor`, [core #13](https://github.com/wxylib/core/pull/13)); requirements in section 8 |
| [m11: Quiet operations](docs/m11-quiet-operations.md) | What composite raster readers do without saying so, a ladder from hidden to separated, and REMA v2, COP30 and Sentinel-2 as the fixtures that expose it | Open; COP30 source table in [measurements/cop30](measurements/cop30/README.md) |
| [m12: An adaptive densify engine (bigcurve in Rust)](docs/m12-bigcurve-densify.md) | Where a Rust port of bigcurve's adaptive densify belongs, how it fits the non-affine grid front ends, and the one change it needs (a pluggable edge model) | Partly implemented, outside wxylib: [hypertidy/bigcurve-rs](https://github.com/hypertidy/bigcurve-rs) stage 1 ([#1](https://github.com/hypertidy/bigcurve-rs/pull/1)) |
| [m13: Four views of one byte table](docs/m13-four-views.md) | The mdim VRT, flat table, kerchunk and Icechunk views of the live BRAN2023 store; where the proofs sit; next steps by value; uses for learning, analysis and teaching | Partly implemented: three views read identically to GDAL, BRAN2023 and GHRSST examples; public home, CI fixture and plan gaps open |
| [m14: What is missing](docs/m14-unreferenced-datasets.md) | Survey of widely used ocean, sea ice, reanalysis and topography datasets with no cloud copy or published byte-reference index, ranked by value and harvest difficulty | Open, for review; nothing harvested yet |
| [m15: mdim-refs/0.2 reconciliation](docs/m15-mdim-refs-reconciliation.md) | The spec against its R reference implementation, the fixtures and the BRAN2023 and MUR stores: placements and info encodings settled, placement-first chunk lookup, rank and codec rules, SQLite vs Parquet roles | Implemented on the wxylib side: spec edits, [fixtures #9](https://github.com/wxylib/fixtures/pull/9); per-axis edges open |
| [m16: A versioned byte-ref table](docs/m16-versioned-byte-ref-table.md) | Lance, Parquet fragments with a create-only manifest commit, and Icechunk, each holding the same GHRSST MUR 2024 history; Icechunk features as table operations, measured; then the chunk bytes held in Lance (versioned, and mixed with refs in one blob column); bytes checked against GDAL | Assessment, measured: Lance not adopted for refs, as recommended; Lance first for held bytes |
| [m17: Self-describing reference stores](docs/m17-self-describing-stores.md) | A description contract (what a published store must state, what may stay open) against mdim-refs/0.2 and the wxy readers; two BRAN2023 builds and the fixtures checked, a rounded scale_factor (about 0.5 C) and a fill conflict found; a one-file check with a GDAL oracle | Partly implemented: fill handling ([core #17](https://github.com/wxylib/core/pull/17)), the one-file check; producer packing fix and CI check open |
| [m18: An editing canvas with CAD control](docs/m18-editing-canvas.md) | A personal canvas for drawing and editing vector data exactly: Manifold, QGIS, CAD and web drawing libraries as prior art; snapping, typed locks and an operation log as a small headless engine; the edit frame, an underlay warped by `wxy-warp`, and input and output left as slots; a prototype in wxylib/web | Partly implemented: prototype in wxylib/web ([web #11](https://github.com/wxylib/web/pull/11) to [#14](https://github.com/wxylib/web/pull/14)); section 8 next steps open |
| [m19: The exact footprint](docs/m19-exact-footprint.md) | What controlledburn does inside rwarp's exact footprint for average and mode, how it compares with GDAL's box and what densify buys; where the time goes (burn setup and per-cell records, and transforms the approximate transformer cannot reach); a shared lattice, a coverage window and a boundary integral over row prefix sums, measured; patches for controlledburn-rs and rwarp; adaptive densify with bigcurve as the next step | Open, measured: patches in review as controlledburn-rs#13 and rwarp#10, #11 |
| [m20: rwarp, controlledburn and bigcurve as the movement layer](docs/m20-movement-crates.md) | What is left in each crate, what each could become (a conservative regridder, one exact coverage engine, adaptive edges), the boundaries and seam between them, what wxy-warp carries that belongs below, a short roadmap per crate, and conservative weights in wxylib (Parquet, ESMF netCDF, `wxy weights`) | Partly implemented: rwarp 0.3 on crates.io with the chunk planner, backmap inverse and weights ([rwarp#22](https://github.com/hypertidy/rwarp/pull/22)), core #24 and #25; wxylib weights files and verb open |

## Reference specs

Specs from adjacent work that the design documents refer to. Not wxylib
formats.

| Spec | About | Status |
|------|-------|--------|
| [mdim-refs/0.2](specs/mdim-refs-0.2.md) | A byte-reference table built from a `gdal mdim mosaic` VRT (SQLite; Parquet and kerchunk exports) | Draft; open questions on per-axis chunk edges and the Parquet export layout |

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
