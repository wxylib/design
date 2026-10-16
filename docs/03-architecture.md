# 03: Architecture and staged roadmap

Status: gate 3 provisional, 2026-10-16 (stage 1 chosen; open to revision)
Builds on: [01 module survey](01-module-survey.md),
[02 data model](02-data-model.md) and their gate decisions.

## 1. Shape

One Cargo workspace, `wxylib/core`, holding the wxylib crates. External
crates stay where they are: rwarp (hypertidy, transfer pending), vaster,
async-tiff, zarrs, object_store, the CRS backends.

| Crate | Layer | Holds | Depends on |
|-------|-------|-------|------------|
| `vaster` (external) | L0 | grid arithmetic | nothing |
| `wxy-domain` | L3 | `Dim`, `Domain`, `Mapping`, `Positions`, `Frame`, `CellConvention`, `Field`, `Collection`, `DataType`, value semantics, normalisation | vaster |
| `wxy-source` | L3 | `ChunkSource`, `ChunkGrid`, `ChunkKey`, read plans | wxy-domain, `bytes`, `futures` |
| `wxy-tiff` | L2 adapter | COG/GeoTIFF as a `Collection` with `ChunkSource`s; GeoKeys to mapping and frame | wxy-source, async-tiff |
| `wxy-zarr` | L2 adapter | Zarr as a `Collection`; CF and GeoZarr only as far as existing crates go | wxy-source, zarrs |
| `wxy-resample` | L4 | one set of kernels for warp, overviews and resampled reads | wxy-domain |
| `rwarp` (external) | L4 | transformers, source-window planning, warp kernels | vaster, a CRS backend |
| `wxy-warp` | L4 | domain mappings as rwarp `Transformer`s; plan, fetch, warp across sources | wxy-source, rwarp |
| `wxy-cli` | L6 | `wxy info`, `wxy warp` | everything above |
| `wxy-py`, `wxy-r` | L6 | bindings | everything above |

Names are working names with a `wxy-` prefix, all free on crates.io as of
2026-10-16. Repository names stay simple and technical.

| Repo | Holds | Needed from |
|------|-------|-------------|
| `design` | these documents | now (exists) |
| `core` | the Cargo workspace above | S1 |
| `fixtures` | GDAL oracle outputs and test files, kept out of `core` | S2 |
| `docs` | book, tutorials and explainers | S2 onward |
| `py` | Python bindings (maturin, pyo3) | S6 |
| `r` | R package (extendr or savvy) | S6 |
| `web` | browser app, the successor to rwarp-wasm | after S4 |

All were requested together on 2026-10-16 so that none blocks later work;
any that go unused stay as stubs.

## 2. Decisions, with rationale

**A1. One workspace repo first; split crates into their own repos only when
they need their own release cycle.**
- Get: one repo to create, atomic changes across crates while the types
  are still moving, one CI.
- Cost: crates release together for a while; the repo grows.
- Without it: a repo per crate on day one, and every type change becomes a
  coordinated multi-repo release.

**A2. rwarp stays external and is consumed by git or crates.io; wxylib
wraps it rather than forking it.**
- Get: rwarp keeps its own validation story and users; the pending
  transfer is a rename, not a merge.
- Cost: changes that rwarp needs (a `proj-core` backend, `proj4rs` 0.2,
  scaled kernels) go through its repo.
- Without it: two copies of the warp core.

**A3. The mapping-to-Transformer bridge lives in `wxy-warp`, not in
`wxy-domain`.**
- Get: the domain crate has no CRS or warp dependency (layer rule, DM7) and
  builds for wasm with nothing but vaster.
- Cost: one more crate.
- Without it: every user of the types inherits rwarp and a CRS backend.

**A4. Adapters are thin: format metadata into a `Collection`, chunks
through `ChunkSource`, nothing else.**
- Get: async-tiff and zarrs can be upgraded without touching the core; the
  GDAL workaround (survey D7) becomes one more adapter of the same shape.
- Cost: convention gaps show up as missing frames or mappings rather than
  guesses, until an upstream crate fills them.
- Without it: convention logic leaks into the core, as in GDAL's drivers.

**A5. GDAL is an oracle in tests, not a dependency.**
- Get: bit-level comparison with GDAL where it matters (windows,
  georeferencing, warps), run where GDAL exists: Michael's machine (through
  a `brief.md`), or CI with an OSGeo GDAL image.
- Cost: oracle fixtures must be generated and committed; tests that need
  GDAL are opt-in.
- Without it: correctness claims rest on our own reading of GDAL's source.

## 3. Stages

Each stage is small, works on its own, and ends in a gate.

| Stage | Delivers | Gate | Get | Cost | Without it |
|-------|----------|------|-----|------|------------|
| **S1** | `wxy-domain`: the types for R0 to R3, R2-to-R1 normalisation with a report, cell conventions; tests from regular-in-what cases (float32 GHRSST axis, AVISO Mercator latitude, NSIDC 3412) | the types read well in code | the model from doc 02 becomes concrete and testable with no I/O | design churn is still cheap here, so expect revisions | every later stage invents its own types |
| **S2** | `wxy-source` and `wxy-tiff`: open a COG (local and HTTP), plan a window, fetch, decode | windows match GDAL (oracle) | the plan, fetch, decode seam is real | async plumbing; a sync convenience layer | the seam stays theoretical |
| **S3** | `wxy-zarr`: Zarr v2/v3 through zarrs, CF and GeoZarr frames where zarrs or its ecosystem supports them | same window, same numbers as S2 for a COG converted to Zarr | the two formats meet in one model | partial conventions | Zarr support lags and the model is shaped by TIFF alone |
| **S4** | `wxy-warp` and `wxy-cli warp`: COG or Zarr to a target grid spec, through rwarp | bit-identical to `gdalwarp` at 1:1 (rwarp's existing bar) | the first end-to-end tool, the browser app's pipeline on servers | output format choice (Zarr first, since zarrs writes) | rwarp stays without a native I/O story |
| **S5** | `wxy-resample`: kernels shared by warp and overviews; overview selection in planning | rwarp's downsampling limitation fixed and matched to GDAL | one validated kernel set | harder bit-identity at scaled support | two kernel sets, as in GDAL |
| **S6** | Python (pyo3) and R (extendr or savvy) bindings of S4's surface | a notebook and an R script reproduce S4 | the tool reaches its users | binding maintenance | Rust only |
| **S7** | the virtual scheme: select, remap, combine, compute, serialised | a VRT mosaic and a warped VRT expressed and evaluated | the VRT replacement | a new file format to design | virtual data stays GDAL-only |
| **S8** | explicit meshes: R5 on meshspec v0.1, UGRID through existing readers | meshcore's UGRID cases reproduce | meshes join the model | topology module design | the spectrum stops at R3 |
| **later** | implicit meshes (DGGS: `h3o`, `healpix`, `s2`), features (GeoArrow), curvilinear inverse mappings, byte views | each its own gate | the full spectrum | | |

S1 is chosen as the first stage. It needs no I/O, no new external
dependency beyond vaster, and it is where the data model is cheapest to get
wrong and fix.

## 4. Questions for gate 3

1. **Workspace repo name.** `wxylib/core` for the workspace (A1)?
2. **Crate prefix.** `wxy-` for crates on crates.io, or another prefix?
3. **Oracle runs.** Generate GDAL fixtures on your machine from a
   `brief.md`, or set up CI with an OSGeo GDAL image, or both?
