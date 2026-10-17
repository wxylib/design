# wxylib/design

Design notes, surveys and staging plans for wxylib: Rust tooling that takes
the modular concepts GDAL already contains, gives each one its own home, and
builds an ecosystem of crates, bindings and documentation around them.

New to wxylib? The [intro page](https://github.com/wxylib/docs#readme)
says what works, what the tests check and how to get involved.

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

Which stages are built is kept in one place, doc 03's
[stages section](docs/03-architecture.md#3-stages); what they add up to
for a user is on the [intro page](https://github.com/wxylib/docs#what-works-today).

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
