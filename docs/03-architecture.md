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

**A6. Formats arrive by virtualisation first (added 2026-10-16).** A format
wxylib needs gets a *scanner* that writes chunk references (path, byte
offset, length, codec chain) as a virtual Zarr store, which `wxy-zarr` reads
through zarrs. A native reader (as `wxy-tiff` is) is the exception, kept
where it is already cheap or performance demands it.
- Get: one read path (zarrs) for every format; formats are described once,
  in a standard form other tools (zarr-python, VirtualiZarr, icechunk) also
  read; legacy quirks stay in scanners, out of the core.
- Cost: formats whose chunks are not independently decodable (strips with
  shared state, some HDF4 or GRIB layouts) need scanners that are honest
  about what cannot be referenced; the reference store must be kept in step
  with the source files.
- Without it: a native reader per format, which is GDAL's driver model and
  the scope this project exists to avoid.

**A7. Adjacent efforts first (added 2026-10-16).** Before building a piece,
check whether Earthmover, Development Seed, the zarrs project, the GeoZarr
conventions or others already have it, or plan to. Use it, or contribute
the missing piece upstream; wxylib keeps only what nobody else has (the
unified domain model, warp, and the glue between them). The related work
survey in this repo is the map for this.
- Get: a small project that composes with icechunk, VirtualiZarr,
  async-tiff and GeoZarr rather than competing with them; our work counts
  toward shared standards (for example, a Rust implementation of the
  GeoZarr `spatial:` and `proj:` conventions).
- Cost: upstream timelines and review; some pieces wait or live in other
  repos.
- Without it: a reimplement-everything org, the failure mode several
  pure-Rust "GDAL alternatives" on crates.io already show.

**A5. GDAL is an oracle in tests, not a dependency.**
- Get: bit-level comparison with GDAL where it matters (windows,
  georeferencing, warps), run where GDAL exists: Michael's machine (through
  a `brief.md`), or CI with an OSGeo GDAL image.
- Cost: oracle fixtures must be generated and committed; tests that need
  GDAL are opt-in.
- Without it: correctness claims rest on our own reading of GDAL's source.

**CRS backend: what each candidate covers today (open, 2026-10-16).**
The backend choice defers to mdsumner/rust-proj-capability; these are the
facts S4 and the CRS guide work have added.
- proj4rs (in use, through rwarp): `EPSG:NNNN` and PROJ strings only. No
  WKT2, PROJJSON, `ESRI:` or `OGC:CRS84`. So `wxy warp --crs` takes EPSG
  codes: a PROJ string would warp, but GeoZarr `proj:` has no field to
  record one.
- Rust Geodesy: no `stere` operator, so no EPSG:3031 or other polar
  stereographic CRSs. It cannot be the only backend while polar data is a
  first use. rust-proj-capability's `geodesy_ad.rs` adapter turns
  `+towgs84` PROJ pairs into Geodesy pipelines (exact fixtures went from 9
  to 27 of 93). That could later become a small helper here.
- PROJ (C), and proj-wasm in the browser: full coverage. It is the backend
  that unlocks WKT2 and PROJJSON input.

## 3. Stages

Each stage is small, works on its own, and ends in a gate.

| Stage | Delivers | Gate | Get | Cost | Without it |
|-------|----------|------|-----|------|------------|
| **S1** | `wxy-domain`: the types for R0 to R3, R2-to-R1 normalisation with a report, cell conventions; tests from regular-in-what cases (float32 GHRSST axis, AVISO Mercator latitude, NSIDC 3412) | the types read well in code | the model from doc 02 becomes concrete and testable with no I/O | design churn is still cheap here, so expect revisions | every later stage invents its own types |
| **S2** | `wxy-source` and `wxy-tiff`: open a COG (local and HTTP), plan a window, fetch, decode | windows match GDAL (oracle) | the plan, fetch, decode seam is real | async plumbing; a sync convenience layer | the seam stays theoretical |
| **S3** | `wxy-zarr`: Zarr through zarrs, georeferenced by the GeoZarr `spatial:` and `proj:` conventions (v0.1) or CF 1D coordinates | same window, same numbers as S2 for a COG converted to Zarr | the two formats meet in one model | partial conventions | Zarr support lags and the model is shaped by TIFF alone |
| **S3b** | `wxy-virtual` (first slice done 2026-10-16: tiled TIFF without predictor, written with Icechunk and read through wxy-zarr, matching GDAL): scanners emit (chunk key, url, offset, length, checksum) plus Zarr metadata, written with icechunk's Rust `set_virtual_refs` and read back through `zarrs_icechunk`. TIFF scanning is already done by virtual-tiff (Python, on async-tiff), so a Rust scanner is only built if a Rust-side need appears; HDF5 and GRIB have Rust pieces to reuse (hdf5-reader chunk index, gribberish) | a COG read through its icechunk virtual store matches S2 and GDAL byte for byte | the virtualisation pathway (A6) is real, on shared infrastructure (A7) | icechunk as a dependency; a small kerchunk JSON/Parquet emitter is an open slot if needed | every new format needs a native reader |
| **S4** | `wxy-warp` and `wxy-cli warp` (done 2026-10-16): COG or Zarr to a target grid spec, through rwarp | bit-identical to `gdalwarp` at 1:1 (rwarp's existing bar) | the first end-to-end tool, the browser app's pipeline on servers | output format choice (Zarr first, since zarrs writes) | rwarp stays without a native I/O story |
| **S5** | `wxy-resample`: kernels shared by warp and overviews; overview selection in planning | rwarp's downsampling limitation fixed and matched to GDAL | one validated kernel set | harder bit-identity at scaled support | two kernel sets, as in GDAL |
| **S6** | Python (pyo3) and R (extendr or savvy) bindings of S4's surface | a notebook and an R script reproduce S4 | the tool reaches its users | binding maintenance | Rust only |
| **S7** | the virtual scheme: select, remap, combine, compute, serialised | a VRT mosaic and a warped VRT expressed and evaluated | the VRT replacement | a new file format to design | virtual data stays GDAL-only |
| **S8** | explicit meshes: R5 on meshspec v0.1, UGRID through existing readers | meshcore's UGRID cases reproduce | meshes join the model | topology module design | the spectrum stops at R3 |
| **later** | implicit meshes (DGGS: `h3o`, `healpix`, `s2`), features (GeoArrow), curvilinear inverse mappings, byte views | each its own gate | the full spectrum | | |

Status (2026-10-16): S1, S2, S3 and a first slice of S3b are done in
wxylib/core, all matching GDAL 3.12 byte for byte on the fixtures. S3b's
next pieces (predictor and LZW, which have no standard Zarr codec yet;
GDAL-backed scanners; kerchunk export) wait for a need.

S4 is done: `wxy-warp` and `wxy warp` (GeoTIFF or Zarr in, GeoZarr out).
Nearest neighbour is identical to GDAL's warper on every fixture case, and
every method is identical near 1:1. Bilinear and cubic at downsampling
ratios differ, as expected until S5's kernel scaling. Two rwarp bugs found
on the way (approximate transformer endpoints, nearest truncation) have
patches waiting for hypertidy/rwarp; until a release carries them,
`wxy-warp` pins rwarp by git revision and shims both.

Open topic (gate 4): a flat tabular reference store. Scanners already
produce a table (one row per chunk: key, url, offset, length, checksum,
plus the array's Zarr metadata), and Icechunk is one sink for it. A flat
sink and a reader over it (Parquet or similar, served as zarrs storage)
would cover the cases where Icechunk's versioning is more than a job needs.
Keep exploring before choosing; see the landscape survey, section 18. `wxy-tiff`'s georeferencing (GeoKeys, transform) has no Rust
home upstream yet; it may align with geotiff-core or be offered to
async-tiff or async-geotiff rather than grow here.

S1 is chosen as the first stage. It needs no I/O, no new external
dependency beyond vaster, and it is where the data model is cheapest to get
wrong and fix.

## 4. Questions for gate 3

1. **Workspace repo name.** `wxylib/core` for the workspace (A1)?
2. **Crate prefix.** `wxy-` for crates on crates.io, or another prefix?
3. **Oracle runs.** Generate GDAL fixtures on your machine from a
   `brief.md`, or set up CI with an OSGeo GDAL image, or both?

## 5. Running wxylib: platforms, images, bindings (aspirations)

Noted now so choices made early do not close doors; built only when a stage
needs it (Michael, 2026-10-16: "consider, plan, implement when timely").
The aim is that the development track is as easy to run as the eventual
use tracks.

**What is true today.**
- The workspace is plain Rust and builds with `cargo` alone on Linux; CI
  runs on Ubuntu only. macOS and Windows are expected to work but are
  untested.
- Native C code arrives through codecs, not through our crates:
  `zstd-sys`, and `blosc-src` (bringing `lz4-sys` and `libz-sys`) through
  zarrs' default codec set. A C compiler is therefore needed.
- `wxy-domain`, `wxy-source` and `wxy-tiff` compile for
  `wasm32-unknown-unknown` (local-file openers are left out there).
  `wxy-zarr` does not yet: zarrs drops `Send`/`Sync` on wasm, and our
  `ChunkSource` trait still requires them. That is a small fix to make when
  the browser track starts, together with checking that the C codecs build
  for wasm (or are swapped for pure-Rust ones).
- GDAL is only a test oracle (A5), and the easiest cross-platform route to
  it is a Python wheel (`pip install rasterio` bundles GDAL), which is how
  wxylib/fixtures is generated.

**Ways to run, when timely.**

| Track | Route | Becomes timely | Known challenges |
|-------|-------|----------------|------------------|
| Rust | `cargo add` / `cargo install wxy-cli` | S4 (first CLI) | C codecs need a compiler; feature flags to opt out |
| Prebuilt CLI | release binaries for Linux, macOS, Windows (x86_64, arm64), for example with cargo-dist | after S4 settles | signing on macOS and Windows |
| Containers | a small image with the CLI, and a dev image that adds the GDAL oracle (OSGeo GDAL images or rasterio wheels); amd64 and arm64 | S4, or sooner if the oracle moves into CI | image size with GDAL; keeping oracle GDAL versions pinned |
| Python | maturin wheels (abi3) for manylinux, macOS, Windows | S6 | wheel matrix in CI; async runtime under Python |
| R | extendr or savvy package | S6 | CRAN's Rust policy: vendored crates, offline builds, minimum rustc on CRAN machines, Windows toolchains |
| Browser | wasm build behind rwarp's slippy-map app; CRS through proj-wasm (gate 4) | with the web repo | `Send`/`Sync` bounds; C codecs on wasm; CORS for HTTP range reads; no local files; proj-wasm size and worker plumbing |
| Cloud | the CLI or Python next to the data (object_store backends) | S4 | credentials and region; egress cost |

**Beyond Python and R.** Most other languages are reachable through two
shared layers, so those come first and each binding stays thin:

- **A C ABI** (one `wxy-ffi` crate, like zarrs_ffi). Get: Julia (`ccall`),
  Go, C/C++ and others from one surface. Cost: a stable, versioned C API
  to maintain. Without it: each language binds Rust its own way.
- **Arrow interchange** (the Arrow C Data Interface, GeoArrow for R6
  features, Arrow tables for chunk indexes and virtual references). Get:
  zero-copy handoff to anything that speaks Arrow (pyarrow, R's nanoarrow,
  DuckDB, Polars, JS) without a binding per host. Cost: shaping our
  outputs as Arrow. Without it: copies and per-host adapters.

| Binding | Route | Becomes timely | Notes |
|---------|-------|----------------|-------|
| TypeScript / JS | wasm-bindgen over the browser build | with the web repo | sits beside deck.gl-raster (DevSeed) rather than competing: rwarp's exact warp and the domain model are what we add |
| DuckDB | a Rust extension (DuckDB's extension template) | once virtual references or features exist | tables of chunk references, domains or warp plans to query with SQL; DuckDB's spatial extension already covers vector work, so we would not repeat it |
| Julia | the C ABI | when the C ABI exists | Julia's own geospatial stack (Rasters.jl, ArchGDAL.jl) is a user, not a target to replace |
| Command line | `wxy-cli` | S4 | the binding every other track can shell out to |

**The hard one: PROJ.** Real CRS work needs PROJ (C++, SQLite, grid
files), which is the main cross-platform cost in GDAL-based stacks. wxylib
defers it to mdsumner/rust-proj-capability; until that settles, frames are
carried as strings and no crate links PROJ, so none of the routes above
inherits that cost yet.

**What we would get, cost, and without it.**
- Get: every track stays installable with one command, and problems are
  stated before users hit them.
- Cost: a CI matrix and release tooling, added stage by stage rather than
  up front.
- Without it: the usual geospatial install story, where the hardest part
  of using a tool is building it.
