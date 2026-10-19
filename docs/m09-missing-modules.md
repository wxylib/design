# m09: The modules that don't exist yet

Status: musing, 2026-10-19. Direction, not a plan: nothing is built from
it, and it becomes work only through a numbered document. It ends in five
questions, each with a recommended answer.

## 1. Summary

wxylib's aim is not parity with GDAL but to find the modules that do not
exist yet: pieces GDAL has inside it that have no standalone home, which
wxy would be the first user of rather than the owner of. Doc 01 already
names two candidates, M24 (algorithm registry, CLI, pipelines; "own,
designed last") and M5/M6 (byte access, adopt `object_store`; byte views,
"no single Rust home", F4 and D3). This musing revisits both with that
framing, and proposes a design-process rule that follows from it.

- **An extensible CLI that reflects the API is a pattern, and a new
  module.** Nothing in Rust turns one typed operation description into a
  CLI, a Python call, an R call and a machine-readable catalogue. clap
  describes a command line, not an operation. Build it as a crate with no
  geo dependency, proven on wxy's three verbs (section 3).
- **VSI mostly exists, with one real gap.** `object_store` covers remote
  bytes and, in the 0.14 we use, the URL-to-store dispatch
  (`object_store::registry`); async-tiff's `AsyncFileReader` is the right
  reader seam, and the DevSeed and Kyle Barron crates are the exemplars
  to think with. What is missing is the composable *view*: a member of a
  zip on a URL, a gzip with a seek index, a byte range as a file, a cache
  as a layer, and one string grammar that names a chain of them
  (section 4).
- **A crate check before each stage.** Before implementation starts, ask
  whether a crate already does the job, whether the piece should be its
  own crate, and whether we are overbuilding (section 5).
- **The rest of GDAL's infrastructure** (configuration, errors,
  progress, threads, CRS naming, time, plugins, testing) mostly maps onto
  existing crates or is a pattern to follow. Three more pieces look like
  missing modules: a progress-and-cancel handle, a CF time crate, and a
  GDAL oracle harness (section 6).

## 2. What wxy does today

- **CLI.** `wxy-cli` is one `main.rs` (about 680 lines) using clap's derive
  API: `warp`, `points`, `zonal`. Each verb has its own clap struct, maps
  it by hand onto the library's options (`WarpOptions`, `GridSpec`, ...),
  and has `--dry-run`, which prints the plan as JSON and reads nothing.
  The py and r packages hand-write `warp` again (m04 section 4 flagged
  this: "the CLI has three verbs and two bindings hand-write the warp").
- **Bytes.** Everything reads through `object_store`: `wxy-tiff`'s
  `path_reader` (local), `wxy-zarr` via `zarrs_object_store`, and
  `wxy-cache` wraps async-tiff's `AsyncFileReader` with a persistent range
  cache (m05, m06). Core PR #7 (open) adds `https://` sources: `url_store`
  splits a URL into an `HttpBuilder` store plus a path, `url_etag` gets
  the cache validator, `is_url` tests the prefix, and `wxy-cli`'s
  `open_cached` routes on it.
- **Not there.** No `s3://`, `gs://` or `az://` sources yet (S3c plans S3
  through `object_store`), no registry of stores, no archive members, and
  no way for one argument to name "this member of that zip at that URL".

PR #7's `url_store` is a small hand-rolled version of what
`object_store::registry::DefaultObjectStoreRegistry` already does (resolve
a URL to a store and a path, longest-prefix match, lazily built from the
environment). That is a concrete instance of the crate check
(section 5): the crate existed; we wrote a smaller copy.

## 3. The CLI as a module: an operation registry

### 3.1 What GDAL's new CLI framework gives that clap alone doesn't

GDAL 3.11 introduced the `gdal` command (`gdal raster reproject`,
`gdal vector info`, `gdal vsi ls`, ...). It is built on `GDALAlgorithm`
and a global algorithm registry, and its value is in the layer under the
command line, not in the parsing:

| GDAL framework | What it means | clap alone |
|---|---|---|
| An algorithm is an object with typed, described arguments (`GDALAlgorithmArg`: type, choices, min/max count, mutual exclusion, positional, "this is an input dataset of type raster") | The operation is described once, as data | Describes argv; types are Rust types, metadata is help text |
| A registry, walked as a tree (`gdal` -> `raster` -> `reproject`) | Discoverable; plugins add algorithms | Subcommands are fixed at compile time (the builder API can add them at runtime, but there is no catalogue) |
| `--json-usage` prints every argument as JSON | A machine-readable catalogue: GUIs, docs, agents, other bindings read it | No equivalent |
| The same algorithm is called from C (`GDALAlgorithmRegistryGetAlgorithm`) and Python (`gdal.Run("raster", "reproject", input=..., dst_crs=...)`) | Bindings are one generic entry point, not a hand-written wrapper per operation | Nothing below the CLI |
| `gdal raster pipeline read ... ! reproject ... ! write ...` | Steps compose, streaming through in-memory datasets | No notion of steps |
| `.gdalg.json`: a pipeline saved as JSON opens as a dataset | The pipeline is itself a virtual dataset | No notion of persistence |
| Shell completion, progress, consistent `--input`/`--output`/`--overwrite` | Uniform surface | Completion only (clap_complete) |

wxy could copy this design without the mix of old
and new it still carries in GDAL (the classic `gdal_translate` family and
the per-program option parsers alongside it). wxy's own variant has one
extra asset GDAL's lacks: every operation already separates plan from run,
and `--dry-run` already prints the plan. In GDAL a pipeline is persisted as
the *arguments* that produce it; in wxy it could be persisted as the
*plan*, which is costed and inspectable before any byte is read.

### 3.2 Does it exist in Rust?

Not as one piece. The parts exist:

| Part | Crate | Covers |
|---|---|---|
| argv parsing, help, completion | `clap` 4 (derive and builder) | the CLI surface only |
| a schema from a Rust type | `schemars` 1.x (JSON Schema), `facet` (reflection, with `facet-args` for CLI parsing; pre-1.0) | the description, not the dispatch |
| distributed registration | `inventory`, `linkme` | "every crate that links adds its operations" |
| multi-language bindings from one interface | `uniffi` 0.32 (Kotlin, Swift, Python; R and JS only via third parties) | an FFI layer, not an operation catalogue |
| clap plus config files | `clap-serde-derive`, `twelf` | merging sources of options |

What nobody has written is the glue that GDAL, QGIS Processing
(`qgis_process` is generated from the Processing registry) and GStreamer
(`gst-inspect` and `gst-launch` from the element registry) each have in
their own world: **an operation registry whose descriptions generate the
CLI, a generic `run(name, args)` for bindings, a JSON catalogue, and a
serialisable pipeline.** That is the module.

### 3.3 Sketch

Names are placeholders; doc 01's rule is that nothing carries "gdal".

```rust
/// One operation: typed options in, a plan, then a result.
pub trait Operation: Send + Sync {
    type Options: Serialize + DeserializeOwned + JsonSchema;
    type Plan: Serialize;
    const NAME: &'static str;          // "warp"
    const GROUP: &'static [&'static str]; // ["raster"]
    fn describe() -> Description;      // summary, per-arg docs, roles (input/output)
    async fn plan(&self, opts: Self::Options) -> Result<Self::Plan>;
    async fn run(&self, plan: Self::Plan) -> Result<Output>;
}
```

- The **Options** type is the single source. Its JSON Schema is the
  catalogue (`wxy --json-usage`). A clap `Command` is built from the
  schema at runtime (clap's builder API), so `--dry-run`, `--json-usage`,
  `--output`, `--overwrite` and completion come once for every verb.
- **Bindings** expose one generic call: `wxy.run("warp", source=...,
  crs=...)` in Python and `wxy_run("warp", source = ..., crs = ...)` in R,
  passing the options as JSON (or Arrow, when tables are involved) through
  one FFI function. Typed per-operation wrappers can then be *generated*
  from the catalogue for IDE help, instead of hand-written.
- A **pipeline** is a list of (name, options), and `plan` of a pipeline is
  the concatenated plan: the `.gdalg.json` analogue, and the same idea as
  doc 01's "virtual descriptions are data" and m01 section 2.4's
  operation catalogue.
- The crate has **no wxy dependency**. wxy registers its operations into
  it; another project (rwarp's CLI, a controlledburn CLI, other
  hypertidy tools) could do the same.

### 3.4 What do we get, what does it cost, what if we didn't

- **Get.** Each new operation costs one options type and one impl: the
  CLI, py, r, docs pages and an agent tool list follow. A catalogue
  that says which operations accept which rung (m01 2.4). A module others
  could use, which is the "modules that don't exist" aim.
- **Cost.** A framework before there are many operations: three verbs is a
  thin sample, and a generic surface fights the cases that need
  per-verb care (warp's `--extent` taking four numbers, zonal reading
  GeoJSON from a path). Runtime-built clap loses some compile-time
  checking. Async in the trait needs the runtime question settled for
  bindings (m04 noted the `Send`/`Sync` fix for the browser). Designing it
  to be general costs more than designing it for wxy.
- **Without it.** Every verb is written three times (CLI, py, r) and drifts;
  m04 already sees that with warp. No machine-readable catalogue, so docs
  and GUIs are hand-kept. Still fine at three verbs; not fine at ten.

The smallest step that keeps both doors open: move each verb's options into
a serde + schemars type in the library crate (`WarpOptions` is most of the
way), add `wxy --json-usage`, and have py and r call one `run` entry. That
is useful for wxy alone. Extract the registry into its own crate when the
second operation family or a second project wants it, but write it from
the start as if it were one: no imports from `wxy-*` in that module.

## 4. VSI, through the Rust exemplars

### 4.1 What GDAL's VSI is

GDAL's VSI is a POSIX-like file handle (`VSIVirtualHandle`: open, seek,
read) behind path prefixes. Three ideas make it powerful: **one string
names any byte source** (`/vsicurl/https://...`, `/vsis3/bucket/key`);
**handlers chain** (`/vsizip/{/vsicurl/https://host/a.zip}/b.tif`); and
**configuration rides along**, per process or per path prefix
(`GDAL_HTTP_*`, `AWS_*`, `VSISetPathSpecificOption`). Its costs are the
same three: string parsing with special cases, seek-and-read rather than
range requests at the core, and global configuration (pain points B3 and
A8).

### 4.2 The Rust and DevSeed shape of it

Kyle Barron's and DevSeed's crates take it apart differently, and better:

- **A store** (`object_store::ObjectStore`): `get_range`, `get_ranges`,
  `head`, `list`, `put`. No seek, no handle: range requests are the
  primitive, which is what cloud storage actually serves. Credentials and
  options are on the builder, per store, not global.
- **A reader trait at the format's seam** (async-tiff's
  `AsyncFileReader`: `get_bytes`, `get_byte_ranges`). The TIFF reader
  asks for ranges; anything can answer: an `ObjectReader` over any store, a
  `ReqwestReader`, a `TokioReader` over a file, or wxy-cache's wrapper.
  zarrs makes the same split with its storage traits.
- **A protocol, not a dependency**, in Python: `obspec` (interfaces) and
  `obspec-utils` 0.9 (readers and an `ObjectStoreRegistry`, used by
  VirtualiZarr) mean a Python library accepts any store that implements
  the protocol, `obstore` or otherwise.
- **The registry**: `object_store::registry` (Rust) and
  `obspec_utils.registry` (Python) map URL prefixes to configured stores.
  That is the VSI prefix dispatcher, without the global state.

Apache OpenDAL is the other Rust option ("one layer, all storage"), with
composable layers (retry, cache, logging, metrics) and an `object_store`
bridge (`object_store_opendal`). Its layer model is the closest thing in
Rust to VSI chaining, but for services, not for views into files.

### 4.3 GDAL handler by handler

| GDAL | Rust today | Status |
|---|---|---|
| `/vsicurl/`, `/vsis3/`, `/vsigs/`, `/vsiaz/`, `/vsiadls/` | `object_store` http, aws, gcp, azure | exists (D3) |
| path-prefix dispatch, per-path options | `object_store::registry`, store builders | exists; PR #7 hand-rolls it |
| `/vsimem/` | `object_store::memory::InMemory` | exists |
| `/vsicurl/` range cache, `/vsicached?` | wxy-cache (persistent, m05/m06); `foyer` (hybrid memory/disk); OpenDAL cache layer | exists in pieces; wxy-cache is wxy's |
| `/vsisubfile/` (a byte range as a file) | a few lines over `get_range` | trivial, unowned |
| `/vsizip/`, `/vsitar/` | `rc-zip` (I/O-agnostic zip parser), `async-zip`; `zarrs_zip` (Zarr only) | **parsers exist; no store or reader over a member** |
| `/vsigzip/` with seek index | nothing seekable over a range store | **missing** |
| `/vsikerchunk/` | wxy-virtual refs tables, icechunk virtual refs | wxy's own pathway |
| `/vsistdin/`, `/vsicurl_streaming/` | tokio readers | exists, rarely needed |
| one string naming a chain | fsspec's `zip://b.tif::https://host/a.zip` in Python; nothing in Rust | **missing** |

### 4.4 What is genuinely missing

Two things, and both are small, general and geo-free, which makes them
candidates for crates of their own rather than wxy modules:

1. **Byte views.** A view is a store or reader made from another one: a
   zip or tar member (central directory read once, by range, then member
   reads become range reads on the parent when stored, or decoded when
   deflated), a byte range, a gzip stream with a saved seek index, a cache.
   Each implements the same reader trait it consumes, so views compose.
   This is doc 01's M6, which F4 said had "no single Rust home"; that is
   still true.
2. **A chain grammar.** One string that a CLI argument, a refs-table
   `path` column or a config file can carry, naming a chain of views over
   a store. fsspec's `::` chains are the established form in the Python
   geo stack (kerchunk and VirtualiZarr users already write them); GDAL's
   `/vsi` prefixes are what GDAL users already write. Parse both into one
   tree:

   ```
   Source = Store(url) | Member(name, Source) | Range(offset, len, Source)
          | Gunzip(index, Source) | Cache(config, Source)
   ```

   and resolve the leaves through `object_store::registry`.

Caching, in this shape, is a layer in the chain (fsspec's
`simplecache::`, `blockcache::`), which is how wxy-cache already behaves:
it wraps a reader. Configuration stays on the registry, per prefix, never
global (A8).

### 4.5 What do we get, what does it cost, what if we didn't

- **Get.** Zipped GeoTIFFs and shapefiles on a server, gzipped netCDF
  members and the like become readable without download, from the CLI and
  from refs tables; GDAL users' `/vsizip/{/vsicurl/...}` strings keep
  working. The pieces are useful to anyone using async-tiff, zarrs or
  object_store, so upstream or a standalone crate is the natural home.
- **Cost.** Zip has corner cases (zip64, data descriptors, encrypted
  members to refuse); gzip seek indexes are real work and few datasets need
  them. Two grammars to parse. The views must implement `ObjectStore` (big
  trait) or a reader trait (async-tiff's and zarrs' differ), so the seam
  needs choosing.
- **Without it.** Only plain objects are readable; anything archived needs
  a download and unpack first, or GDAL as a scanner (the existing
  "workaround for now"). Nothing breaks while wxy's sources stay COG and
  Zarr, which is the current state.

Near-term and small: replace PR #7's `url_store` with
`object_store::registry`, which adds `s3://`, `gs://` and `az://` at the
same time (S3c wants S3 anyway). Views and the grammar wait for the first
dataset that needs them.

## 5. A design-process rule: the crate check

The hypertidy experience is that small, niche pieces (vaster's grid
arithmetic, controlledburn's exact coverage, rwarp's warp core) later slot
together one after another, *because* each was its own crate with a narrow
job. This musing found two such pieces, and also found that PR #7 wrote a
small copy of something `object_store` already has. Proposed rule, for
every numbered stage before implementation starts, recorded in the stage's
row or doc:

1. **Does a crate already do this?** Search crates.io and the landscape
   (doc 04), including modules of crates we already depend on. If yes,
   use it, or say in one line why not.
2. **Is this piece geo-free, or useful outside wxy?** If yes, it is
   written as its own crate (in the core workspace to start, with no
   `wxy-*` imports), not as a module inside a `wxy-*` crate.
3. **What is the smallest interface it needs?** A trait at the seam
   (`AsyncFileReader`, `ObjectStore`, an `Operation`) rather than a
   concrete type, so the next piece can slot in.
4. **Are we overbuilding?** If the piece is bigger than the stage needs,
   build the stage's slice and leave the rest as a note in the piece's
   README.

Get: fewer quiet copies of existing code; pieces others can use; a record
of why each dependency was or wasn't taken. Cost: a short review per
stage, and some crates that stay small or never get a second user (that is
acceptable, as with the stub repos). Without it: wxy grows the GDAL shape,
one large library where each part is only usable through the whole, which
is what the project set out not to be.

## 6. The rest of GDAL, through the same lens

Doc 01 maps GDAL by data layer (bytes, formats, the data model,
algorithms, composition, surfaces) and gives each module a verdict.
Sections 3 and 4 above revisit two of its rows. This section goes through
the parts of GDAL that doc 01 does not map because they are not about
data: the infrastructure every driver and algorithm leans on. Most of it
lives in `port/` (CPL, the "common portability library") and the
cross-cutting parts of `gcore/`. For each, the question is the same: does
a Rust crate already do it, is there a missing module, or is it only a
pattern wxy should follow?

| GDAL | What it does | Rust today | Verdict |
|---|---|---|---|
| Driver manager and capabilities (`GDALDriverManager`, `DCAP_*` flags, `Identify`/`Open` probing, creation and open option lists as XML) | Finds a driver for a file and says what it can do | None generic; registries per crate (zarrs codecs via `inventory`) | **Pattern.** wxy's formats arrive through scanners (virtualisation principle), so the registry it needs is of scanners. Typed options, as in section 3, replace option XML |
| Configuration (`CPLGetConfigOption`, environment, `gdalrc`, thread-local and path-specific options) | Global knobs read anywhere | `figment`, `config`; `object_store` builders read the environment | **Pattern, no crate.** Configuration is an explicit value passed in (pain point A8, B3); environment only at the edge, in the CLI and bindings |
| Errors and logging (`CPLError`, handler stacks, `CPLDebug` categories, `CPL_DEBUG`) | Reporting, and silencing by category | `thiserror`, `tracing` | **Adopt.** `tracing` spans per plan step; nothing in core logs yet |
| Progress and cancellation (`GDALProgressFunc` returning false to cancel, `GDALScaledProgress` for sub-steps) | One callback type every long operation takes | `indicatif` (display), `tokio_util::sync::CancellationToken` (cancel), separately | **Candidate crate, small.** A geo-free progress-and-cancel handle that nests (scaled sub-steps), and crosses into Python (tqdm) and R (cli) as one callback. Pairs with the operation registry: every operation takes one |
| Threads and memory budgets (`GDAL_NUM_THREADS`, `GDAL_CACHEMAX`, the worker pool, the block cache LRU) | Shared limits across drivers | `rayon`, `tokio`, `moka`, `quick_cache`, `foyer` | **Adopt, as plan inputs.** wxy's plans already cap bytes per batch; a budget is a field of the plan, not a global (A8) |
| CRS model beyond the transform (WKT1/WKT2/PROJJSON I/O, `FindMatches` to identify an EPSG code, axis-order policy `OAMS_TRADITIONAL_GIS_ORDER`) | Reading, writing and naming CRSs | `projjson` 0.1 (typed PROJJSON, 2026-09), `crs-definitions`, `proj4rs`, `proj-core`, `proj` (C PROJ) | **Watch, possibly contribute.** The pieces are appearing; the gap is identification (WKT in, "this is EPSG:3031" out) and one axis-order rule. Part of the open PROJ-in-Rust question |
| Time and units (netCDF driver's CF time decoding, calendars, units strings) | Turning coordinate values into dates | `cftime-rs` 0.1.6 (2023), `chrono` (no CF calendars) | **Candidate crate, or upstream.** CF calendars (`365_day`, `360_day`, `noleap`) matter for climate data; core has no calendar code today. Check whether `cftime-rs` is alive before writing one |
| Metadata domains, PAM `.aux.xml` sidecars, statistics, histograms, RAT, colour tables | Values and descriptions stored beside the data | Zarr attributes, CF; nothing for statistics | **Data model, not a crate** (doc 02). Statistics and histograms are derived products: cacheable like any plan output (m05), not a sidecar format |
| Plugins and deferred driver loading (`GDAL_DRIVER_PATH`, deferred plugins since 3.9) | Drivers added without rebuilding GDAL | No stable Rust ABI; `abi_stable` (stale), WebAssembly components (`wasmtime`, `extism`) | **Later, and likely WebAssembly.** Until then, cargo features and `inventory` registration, plus a subprocess for anything GDAL-only |
| HTTP behaviour (`GDAL_HTTP_*` retry, timeouts, multi-range requests, the on-disk HTTP cache, `AdviseRead` prefetch) | Making remote reads cheap | `object_store` (retry, credentials, range coalescing in `get_ranges`), wxy-cache | **Exists**; prefetch is what wxy's plan already is |
| OGR feature model, OGR SQL, spatial filters | Vector access and query | `geo`, `geoarrow`, `geozero`, DataFusion and SedonaDB | **Exists**; out of scope in doc 01 |
| The test suite as an oracle (`autotest`, driver conformance) | Defines "correct" | None shared; wxy has its GDAL oracle tests and fixtures; terrio's conformance table (doc 04) | **Candidate crate.** A harness that runs one operation in GDAL (through `osgeo.gdal`) and in a Rust crate and compares bytes and values is useful to every Rust geo project, not only wxy |

Three new candidates come out of this, beside sections 3 and 4: a
**progress-and-cancel handle**, a **CF time crate** (or contribution to an
existing one), and a **GDAL oracle harness**. Like the operation registry
and byte views, none of them needs anything from wxy, so each would be a
crate of its own. The rest is
pattern: explicit configuration, budgets in plans, `tracing`, typed
options instead of option lists.

What do we get: a full list of where wxy would otherwise copy GDAL's
infrastructure piece by piece, each with a home that is not wxy. What does
it cost: nothing until a stage needs one of them; the crate check
(section 5) then applies to that row. What if we didn't: the
infrastructure arrives one module at a time, inside `wxy-*` crates, and
wxy ends up with GDAL's shape after all.

## 7. Questions

1. **Is the operation registry its own module?** Recommended: yes, as a
   geo-free crate in the core workspace, extracted when a second project
   wants it. First slice: serde + schemars options per verb, `wxy
   --json-usage`, and one `run` entry for py and r.
2. **When?** Recommended: before the bindings grow past warp (m04 said the
   same), and not before `wxy` has been used enough to know the verbs'
   shape; this musing is direction only.
3. **Byte views and the chain grammar: wxy's, or a standalone crate (or
   upstream to object_store / async-tiff)?** Recommended: standalone,
   started only when a real dataset needs an archive member; offer the
   zip view upstream first.
4. **Adopt the crate check (section 5) as a standing rule in doc 03?**
   Recommended: yes, as a short checklist each stage row answers before
   implementation, starting with the next stage (S3c). Its first finding
   is already actionable: use `object_store::registry` in place of PR #7's
   `url_store`.
5. **Which of section 6's candidates first?** Recommended: the oracle
   harness, because wxy already has the pieces (fixtures, `osgeo.gdal`
   scripts, oracle tests) and every stage leans on it; progress and
   cancellation with the operation registry; CF time when a stage first
   decodes time.
