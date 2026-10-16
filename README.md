# wxylib/design

Design notes, surveys and staging plans for wxylib: Rust tooling that takes
the modular concepts GDAL already contains, gives each one its own home, and
builds an ecosystem of crates, bindings and documentation around them.

Nothing here is code. Each document ends in a gate: a decision to accept,
revise or reject before the next document starts.

## Principles

- Slow incremental steps that are productive, consistent, modular and
  extensible.
- Separate planning, reading and computing. A plan can be inspected,
  serialised and costed before any pixel is touched (the rwarp model).
- Leverage existing crates (object_store, async-tiff, zarrs, proj, proj4rs,
  vaster) where they fit. Build only what has no good home.
- GDAL itself is a workaround for now, never the basis. If we reach for
  functionality before we have the foundation for it, we stop and build the
  foundation.
- GDAL is the inspiration and, for now, a workaround we may call. Nothing
  we publish carries "gdal" in its name.
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
| 5 | [Pain points in GDAL, R and Python](docs/05-pain-points.md) | Roadmap findings and reference-table alignment (open) |

## Musings

Blue-sky side notes, not plans and not gated. A musing becomes work only
by being picked up into a numbered document.

- [m01: Downstream UX](docs/m01-downstream-ux.md): what front ends (a
  modular QGIS among them) could do with the core's pieces, and which
  doors the core should keep open for them.

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
