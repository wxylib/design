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
- Every module, design choice and stage carries a rationale: what we get,
  what it costs, and what happens if we don't do it.

## Plan

| Step | Document | Gate |
|------|----------|------|
| 1 | [Module survey](docs/01-module-survey.md) | Agree the module map |
| 2 | Data model: classic raster vs mdim (to come) | Accept core types and traits |
| 3 | Architecture around rwarp and a staged roadmap (to come) | Pick the first implementation stage |

## Related repositories

- [hypertidy/rwarp](https://github.com/hypertidy/rwarp): the warp core
  (transformers, source window planning, kernels). No I/O. A candidate for
  transfer into wxylib, pending.
- [mdsumner/rust-proj-capability](https://github.com/mdsumner/rust-proj-capability):
  the survey of CRS crates. The CRS backend decision defers to it.
- [hypertidy/vaster-rs](https://github.com/hypertidy/vaster-rs): grid
  arithmetic with no dependencies.
- [developmentseed/async-tiff](https://github.com/developmentseed/async-tiff),
  [zarrs/zarrs](https://github.com/zarrs/zarrs),
  [developmentseed/zarrista](https://github.com/developmentseed/zarrista):
  I/O models to align with.

## License

MIT OR Apache-2.0, matching rwarp and the crates we build on.
