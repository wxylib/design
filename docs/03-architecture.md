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
- Clarified at gate 5 (doc 05, D2): TIFF stays read natively by `wxy-tiff`.
  Icechunk references for TIFF (S3b) are an option for stores that mix
  formats, not a replacement for the native path.
- One reference-table shape (gate 5, doc 05, D1): scanner rows in
  `wxy-virtual` use the mdim-refs/get-refs columns (`dim_0..dim_{n-1}`,
  `present`, `path`, `offset`, `size`), so a table from R, GDAL or a Rust
  scanner reads the same way. The m02 pilot (`from_refs_table`) is the
  trial.

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

**A8. No global state (added at gate 5, 2026-10-16; doc 05, B3 and B4).**
Options are explicit values passed in a call. The environment is read only
when a caller asks for it, and whatever is read reports where it came from.
Sources report unexpected content, such as an HTML error page where data
should be, instead of decoding it.
- Get: the same call behaves the same in every process, and a surprising
  result can be traced to its cause.
- Cost: a little more ceremony at the call site, and a helper for "read my
  environment" that callers opt into.
- Without it: GDAL's configuration precedence problem (config options,
  environment variables, open options and thread-local state) again.

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
| **S4b** | mdim warp (gate 5; doc 05, W1 and W3): any number of non-spatial dims, streamed slice by slice under one plan, so a time x depth x lat x lon store warps without loading it; the target stays explicit (an extent suggestion, if wanted, is a separate helper) | a 4D Zarr store warps slice by slice and each slice matches the 2D S4 warp of that slice | Michael's headline pain answered while the warp code is fresh | chunk-aware slicing in `wxy-warp` | wxylib repeats GDAL's slice-by-hand mdim warp |
| **S4c** | planned extraction (gate 5; doc 05, E1): map points or features to chunk keys through the plan seam, fetch each chunk once, return values per point | values match GDAL's point reads on the fixtures, with each chunk fetched once | extraction at scale without reading whole windows | a small stage on the existing seam | users read windows and pick points by hand |
| **S5** | `wxy-resample`: kernels shared by warp and overviews; a plain/scaled kernel switch (gate 5; doc 05, W2), so rwarp's one known divergence becomes an option; overview selection in planning, chosen per tile; overviews passed through derived (calc) fields (V3) | rwarp's downsampling limitation fixed and matched to GDAL with scaled kernels; plain kernels match today's output | one validated kernel set | harder bit-identity at scaled support | two kernel sets, as in GDAL; one overview level for a whole warp |
| **S5b** | curvilinear (R3) warp (moved from "later" at gate 5; doc 05, W4 and L4): inverse mappings for 2D coordinate arrays (swaths, model grids) | a curvilinear fixture warps to match GDAL's geolocation-array warp | the most repeated pain across GDAL, R and Python | the inverse-mapping design comes sooner | swaths and model grids stay on pyresample, xESMF and geolocation arrays |
| **S6** | Python (pyo3) and R (extendr or savvy) bindings of S4's surface | a notebook and an R script reproduce S4 | the tool reaches its users | binding maintenance | Rust only |
| **S7** | the virtual scheme: select, remap, combine, compute, serialised; covers features and mesh as well as grids, and the scheme is written by the library rather than by hand; combine validates its inputs the way gdalbuildvrt does (CRS, resolution, band count, data type) and reports what it dropped (gate 5; doc 05, V1, V5, D3) | a VRT mosaic and a warped VRT expressed and evaluated | the VRT replacement | a new file format to design | virtual data stays GDAL-only |
| **S8** | explicit meshes: R5 on meshspec v0.1, UGRID through existing readers; the kept mesh form is a conversion target first, and algorithms such as overlay run on it once the topology module exists (gate 5) | meshcore's UGRID cases reproduce | meshes join the model | topology module design | the spectrum stops at R3 |
| **later** | implicit meshes (DGGS: `h3o`, `healpix`, `s2`), features (GeoArrow), byte views | each its own gate | the full spectrum | | |

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

S5's first slice is done (2026-10-17): `wxy-resample` holds GDAL's warp
kernels ported in their arithmetic order (4-sample bilinear and cubic, the
scaled kernel in SSE2 lane order, the general kernel with validity and
nodata), and `wxy-warp` runs GDAL's warp operation around them, chunk by
chunk (chunk list, per-chunk source windows and kernel scales). Every warp
oracle case, nearest, bilinear and cubic, coarse targets, nodata and
chunked windows included, is identical to GDAL (24 cases). The
plain/scaled switch is `WarpOptions::chunked` (`wxy warp --plain`), and
plain gives the S4 output. What we get: GDAL's output without GDAL. What
it costs: GDAL's chunking and per-chunk scale come along, quirks included,
and a probe point check that PROJ does but proj4rs does not. Without it,
coarse warps would alias. Overview selection followed (core 45ec852):
`WarpOptions::overview` ports gdalwarp's `-ovr AUTO` rule (a 10x10
lattice of target corners mapped to source pixels, then the closest
coarsest level still finer than the target), `AUTO-n` and fixed levels, and the CLI
defaults to auto as gdalwarp does; three overview cases match GDAL. What
we get: gdalwarp's default output and its read savings. What it costs:
one level for the whole warp, as gdalwarp, rather than per tile. Without
it, coarse warps read full resolution and differ from gdalwarp. Per-tile
selection stays an extension for later. Overviews
through derived fields wait for a use.

S4b followed (core 8f14888): `WarpPlan` plans once from the spatial dims
and warps any number of leading dims in batches of whole source chunks
(capped in bytes), and the CLI writes each batch to the output store as
it is warped (wxy-zarr `GridWriter`). Each slice equals the 2D warp of
that slice alone, on both routes. What we get: a time x depth x y x x
store warps without being loaded, and one plan instead of one per slice.
What it costs: the plain route now warps slice by slice too (rwarp's
multi-band pass masked a cell in every band when one band had nodata).
Without it, mdim warps would be sliced by hand, as with GDAL. Leading
coordinate values (time stamps, depths) are not yet copied to the
output.

S5b's first slice followed (core 4765e0e, fixtures 3ff8fb1): a grid placed
by 2D x and y arrays at cell centres warps through a port of GDAL's
geolocation-array transformer (forward interpolation, its float32 backmap
with GDAL's hole filling, and the exact inverse bilinear refinement), and
all 12 curvilinear oracle cases match GDAL cell for cell, including a ring
around the south pole that crosses the antimeridian. What we get:
swath and ocean-model grids warp without resampling them to a regular
grid first. What it costs: the backmap is built once per source (memory
about 1.3 times the grid, in float32). Without it, curvilinear sources
would need GDAL.

S5b's second slice (core e1311e2 and 1671818, fixtures 9625fd6) takes CF
coordinates from Zarr: 2D lon/lat arrays become a curvilinear mapping,
1D axes warp as an affine grid when evenly spaced and otherwise as 2D
arrays (GDAL's route for irregular axes), and grids placed by their cell
corners (CF 2D bounds, or corner arrays one row and column larger) warp
with GDAL's TOP_LEFT_CORNER convention. The 6 corner cases match GDAL
cell for cell, and `wxy warp` on a CF Zarr store matches GDAL from the
CLI. Centres stay the default placement, as in GDAL's netCDF driver;
`--bounds` chooses the corners. What we get: xarray-written stores warp
from the shell. What it costs: one more CLI flag. Without it, CF stores
would need a GeoZarr `spatial:` rewrite first. Still to come: 1D CF
bounds (`lat_bnds`, n by 2) and netCDF input.

Gate 5 (2026-10-16; doc 05, sections 12 and 15) added S4b, S4c and S5b,
widened S5 and S7, added A8, and clarified A6. The order from here is S5,
then S4b and S5b, with S4c fitted in where it is cheapest. S4b and S4c
build on S4 directly, so either can move ahead of S5 if a use calls for
it.

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
