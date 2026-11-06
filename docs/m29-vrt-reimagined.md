# m29: VRT, reimagined

Status: musing, 2026-11-05. A conceptual note, not a work plan: what a
modern rework of GDAL's virtual formats would be, given what Zarr,
Icechunk, table formats, query engines, Arrow, WebAssembly and shared
memory have built since, and whether it is worth pursuing. Builds on, and
does not repeat, m25 (the VRT engine scope and `vrt-model`), m13 (four
views of one store), m15 and the mdim-refs/0.2 spec (placements and chunk
tables), m16 (versioned tables, held bytes), m17 (the store description),
m22 (logical plans), m23 (harvesting refs), m26 (bindings), m10 and m11
(cuts and quiet operations), m09 (registry, chain grammar) and the mizu
row of doc 04 section 10.2. Figures:
[img/m29-properties.svg](img/m29-properties.svg),
[img/m29-levels.svg](img/m29-levels.svg),
[img/m29-tiers.svg](img/m29-tiers.svg). Measurement:
[measurements/m29-vrt-rework](../measurements/m29-vrt-rework/README.md).

## Summary

The question: if VRT were designed now, taking its best ideas and
everything built around it since (Zarr, Icechunk, Iceberg and other table
formats, SQL and dataframe engines, JAX, WebAssembly, Arrow, shared-memory
processing), across the hard boundaries between software ecosystems, what
would it be? And is a rework worth considering at all?

- **VRT's lasting idea is a written-down open.** A VRT defines a dataset by
  naming sources, placing windows of them, asserting what they lack, and
  deferring every byte until a window is asked for. Because the result
  opens like any other dataset, it composes. Six properties carry this
  (section 1): closure, names, placement, assertion, deferral, emission.
- **Each property has since been rebuilt, better, inside one ecosystem.**
  Icechunk has byte references with history, but only for chunks that
  line up. Table formats keep sources as rows with statistics. Polars,
  DuckDB and JAX treat the plan as a value an engine optimises. Arrow
  carries memory across languages. mizu shares it across processes. None
  has all six, and none composes misaligned windows of arbitrary formats
  by name, which only VRT does (figure 1).
- **The rework is a model, not a format.** One model on three levels:
  steps (whole-array operations), placements (windows of named sources)
  and refs (byte ranges by chunk key), each a table beside a declared
  header. Lowering moves down a level where it is exact and refuses, with
  a reason, where it is not. Every existing form is a projection at one
  level: VRT XML, `vrt://` and GDALG at steps and placements, GTI at
  placements, mdim-refs, kerchunk and Icechunk at refs (figure 2). That
  satisfies the commit test's "no new file format".
- **Measured: model output lowers completely; imagery mosaics do not
  lower at all.** All 38,360 placements of the published GHRSST
  `mdim.vrt` lower to regular byte references, which is why its four
  views agree. COP30 has none that do: 45 % overlap their neighbours and
  need a cut, 55 % resample. Every one of the 3,817 placements in USGS
  3DEP's 1 arc-second VRT is resampled bilinearly, by a sub-pixel shift
  of up to 0.10 px that comes from a pixel size written as 2.777778e-4
  instead of 1/3600 degree. Snapped, they all overlap and need a cut
  (figure 3).
- **The plan as a table travels better than the plan as XML, but not for
  the reason usually given.** The GHRSST placements are 247 KB as
  Parquet. The XML is 16.6 MB as served, but only 352 KB gzipped, so size
  is mostly a compression question. What the table adds is row-group
  pruning, column statistics, and every SQL and dataframe engine reading
  it with no VRT code.
- **Open modes become a named choice of view.** GDAL decides by driver and
  open flag whether a source is bands, an n-dimensional array or
  features. The rework names the view: `raster`, `array`, `features` or
  `table`. The table view, a virtual dataset read as its own plan rows, is
  the one no system offers and the one that crosses every boundary.
- **Text, Arrow and byte ranges cross ecosystem boundaries; APIs do not.**
  The least specified crossing is the source name. GDAL VSI chains, fsspec
  chained URLs, object_store URLs, Icechunk's virtual chunk containers and
  the R package dsn each spell the same location differently. A mapping
  between them is the smallest piece with the widest reach.
- **Worth it as a reframing, not as a build.** Most of the pieces exist or
  have started (`vrt-model`, mdim-refs, refharvest, the oracle harness,
  raad.virtualize). The reframing adds four small ones (a tier classifier,
  classic placements as a table, a view parameter, a name mapping) and
  says where to stop: no new format, no expression language, no engine.
  The corner where it would first be compelling is "VRT in, virtual Zarr
  out where exact, with a reason where not", which would bring existing
  VRTs to the xarray and Zarr world. Cross-language reach would then
  spread the way Arrow's did, because the cheapest thing to accept is a
  table.

![Six of VRT's properties and seven it lacks, against the systems built
since: only VRT composes misaligned windows by name; byte references,
history, sources as rows, optimised plans and cross-language memory all
live elsewhere](img/m29-properties.svg)

## 1. What VRT is, distilled

GDAL's VRT is usually described by its elements. Read as a design, it
rests on six properties. A rework keeps all six and loses none.

| # | Property | How VRT has it | Why it matters |
|---|---|---|---|
| 1 | **Closure** | a VRT is a dataset; it opens wherever GDAL opens a dataset, and can be the source of another VRT | composition without a new kind of object; the SQL view is the same idea |
| 2 | **Names** | a source is a dataset name: any driver, any VSI chain, any subdataset (m25 section 4.4) | reach: everything GDAL can open can be placed |
| 3 | **Placement** | a source window pasted into a destination window, at any offset, any size, overlapping or not; the planner (`GetSrcDstWindow`) resolves each read | sources need not line up, which is the normal case for imagery |
| 4 | **Assertion** | the VRT states what the source lacks or gets wrong: SRS, geotransform, nodata, scale and offset, dimension types | metadata repair without copying bytes; 7 of the 29 `vrt://` keys begin `a_` (`a_srs`, `a_ullr`, `a_gt`, `a_nodata`, `a_scale`, `a_offset`, `a_coord_epoch`) |
| 5 | **Deferral** | nothing is read until a window is requested; opening is planning | cheap to make, cheap to hand on, cheap to throw away |
| 6 | **Emission** | tools write it: `gdalbuildvrt`, `gdal_translate -of VRT`, `gdalwarp -of VRT`, `gdal raster mosaic`, `gdal mdim mosaic` | VRT is a target language that tools compile to; almost no large VRT is written by hand |

What VRT is not is just as telling. It stops at dataset names and never
says where the bytes are. It has no history. Its sources are XML
elements, not rows, so a 38,360-source plan is one 16.6 MB document.
Its semantics live in one implementation (m25 counts about 41,000 lines
of C++ across four families that share a name and little else). And a
`vrt://` string cannot nest.

## 2. What has been built since

Each system below took one or two of VRT's properties and did them
better inside its own ecosystem, or added what VRT lacks. Figure 1 marks
them; this table says what each one teaches a rework.

| System | What it does better | What it lacks, from VRT's list | Lesson for a rework |
|---|---|---|---|
| Zarr v3 | the array model as an interface over keys; codecs as a declared pipeline; implemented independently in Python, Rust, JS, R, Julia | names (keys only), placement, emission by GDAL-style tools | the header should be Zarr-shaped, so that a Zarr reader is always one possible consumer |
| kerchunk, VirtualiZarr | byte references per chunk key; parsers that emit them from netCDF, HDF5, TIFF, GRIB | placement other than chunk-aligned; any per-source operation | refs are the bottom level, and they need a producer (m23) |
| Icechunk | refs plus history (commits, branches, tags); named virtual chunk containers; spec v2 rectilinear grids | misaligned placement; per-source operations; each commit rewrites the manifest split it touches (m16: 1.84 GB for a year of daily commits at the default split) | history belongs at the refs level, split by the append unit |
| Iceberg, Delta, Lance, DuckLake | a metadata tree of snapshots, manifests and data files with column bounds, so planning is pruning; Lance's blob column holds bytes inline or as external ranges (m16) | arrays; names beyond URIs | a large placement list should be a table with statistics; GDAL's own GTI already moved sources into a vector layer |
| DuckDB, DataFusion, Polars, SedonaDB | lazy plans as values with predicate and projection pushdown; `EXPLAIN`; views (closure, again) | grids, windows and resampling; SedonaDB's `RS_Resample` calls GDAL (doc 04) | if placements are rows, "which sources does this window need" is a `WHERE` clause any engine already runs |
| JAX | a function traced to a typed program (jaxpr) with shapes and types inferred before data; transformations (`jit`, `vmap`, `grad`) are functions from programs to programs; staged lowering | I/O, names, placement | the header is shape inference; steps should be a small typed list that lowers to someone else's IR (ArrIR, m22), not a new language |
| GDAL CLI pipelines, GDALG | algorithm steps chained with `!` and saved as JSON that opens as a dataset: closure for algorithms | outside GDAL, nothing reads it; the step arguments are GDAL's command-line flags | the steps level already has a written form; read it rather than invent one |
| Arrow | a memory layout and a C interface small enough that every language implements both sides; IPC and Parquet as its forms in motion and at rest | nothing, for this purpose | it is the carrier for every level; it won by being cheap to accept, one corner at a time |
| WebAssembly | the planner can run where the data is looked at | GDAL's wasm builds are at 3.8 (m25) | an I/O-free planner is the part worth compiling to wasm |
| mirai, mori, mizu (Charlie Gao) | mirai dispatches tasks to R processes; mizu shares vectors, arrays and Arrow tables zero-copy between R and Python processes on one machine (doc 04 section 10.2); mori is in the same family, not checked here | everything above the bytes | decoded windows can be shared between processes and languages instead of copied; the plan rows are the task list |

Three things stand out in figure 1. VRT is still the only system with
placement of misaligned windows from any format by name, which is why
GDAL's VRT outlives every attempt to replace it. Everything VRT lacks
(refs, history, sources as rows, optimised plans, memory across languages)
exists, but in a different system each time. And the plan as an
optimisable value, which VRT had first in spirit, is now ordinary in every
ecosystem except geospatial rasters.

## 3. One model on three levels

A virtual dataset in the rework is a **header** and three **levels**, each
a table.

- **Header.** Dimensions, types, CRS and grid, fill, packing, units: the
  store description of m17, Zarr-shaped. Assertions are edits to the
  header; they never touch the levels below.
- **Steps.** Whole-array operations: DerivedArray steps (View, Transpose,
  Resample, Grid), pixel functions, warped datasets, GDALG pipeline steps.
  Rows of (step, inputs, parameters). This is ArrIR's logical chain (m22).
- **Placements.** Windows of named sources pasted into windows of the
  destination, with per-placement operations (scale, nodata, LUT,
  resampling). Rows of (source name, source window, destination window,
  operations). VRT sources, GTI rows and the mdim-refs `placements` table
  are all this level.
- **Refs.** Byte ranges by chunk key. Rows of (key, uri, offset, size,
  codecs, etag). mdim-refs chunk tables, kerchunk and Icechunk manifests
  are this level.

Two moves connect the levels. **Lowering** goes down: a step lowers to
placements when it only re-indexes (a view, a transpose, a slab subset),
and a placement lowers to refs when it lines up with the chunk grid and
changes no value. **Raising** goes up: refs group by source into
placements (as the mdim-refs placements table does), and placements
render to VRT XML (as raad.virtualize already does for GHRSST and BRAN).
Where a lowering is not exact, it refuses and says why.

The useful observation is that a byte reference is a degenerate
placement: aligned to the grid, identity operation. So Icechunk's
virtual chunks and VRT's SimpleSource are the same kind of thing at two
levels, and m11's quiet operations are exactly the placements that do not
lower. m13's four views of BRAN and GHRSST agree because both datasets
sit entirely in the lowerable part.

![The rework as one model on three levels, with the header beside them:
steps, placements and refs, each a table; lowering moves down where exact,
raising moves up; existing forms are projections at one level](img/m29-levels.svg)

Every existing form is then a projection at a level, and the rework adds
no format:

| Form | Level | What it adds beyond the level | Written by |
|---|---|---|---|
| VRT XML (classic, mdim, vector) | steps and placements | closure inside GDAL | GDAL tools, vrtstack, raad.virtualize |
| `vrt://` strings | placements (one source) | a URI form; keys as translate flags (m25 section 4.1) | people, dsn's `vrtcon()` |
| GDALG JSON | steps | algorithm chains | `gdal ... pipeline` |
| GTI | placements as a vector layer | spatial index over sources | `gdaltindex`, `gdal driver gti create` |
| mdim-refs/0.2 | placements and refs | the global view with remap; SQLite or Parquet | R producers, refharvest |
| kerchunk JSON or Parquet | refs | fsspec reach | kerchunk, VirtualiZarr |
| Icechunk | refs plus history | commits, tags, containers | VirtualiZarr, Icechunk clients |

Because every level is a table beside a header, every level is
Arrow-native, and planning at any level is a filter and a join: the
window selects placements, placements join to refs, refs group into
fetches. That is what `vrt-model`'s planner computes in code today
(m25), and what mdim-refs already computes as a SQL view.

## 4. How far real VRTs lower

The lowering rule needs a test. Each placement falls into one of four
tiers:

| Tier | Condition | What can hold it |
|---|---|---|
| T0 regular refs | integer offset, same size in source and destination, no value operation, on the chunk grid | any virtual Zarr: kerchunk, Icechunk, mdim-refs |
| T1 refs with chunk edges | as T0 but off the regular grid, and not overlapping another placement | a rectilinear grid (Icechunk spec v2, mdim-refs per-axis edges, m10) |
| T2 needs a cut | integer and unresampled, but overlapping another placement | a cut that decides which source owns each cell (m10), then T0 or T1 |
| T3 needs computing | fractional offset, a size change (resampling) or a value operation (scale, LUT, a nodata that differs) | an evaluator only: rwarp for resampling, the reader for operations |

[tiers.py](../measurements/m29-vrt-rework/tiers.py) classifies every
placement of a VRT without opening any source (results in
[results.jsonl](../measurements/m29-vrt-rework/results.jsonl)):

| VRT | Placements | T0 | T1 | T2 | T3 |
|---|---|---|---|---|---|
| GHRSST MUR `mdim.vrt` (source.coop, 5 arrays) | 38,360 | 38,360 | 0 | 0 | 0 |
| COP30 (OpenTopography, from m10's source table) | 26,475 | 0 | 52 | 11,834 | 14,589 |
| USGS 3DEP 1 arc-second seamless, as written | 3,817 | 0 | 0 | 0 | 3,817 |
| USGS 3DEP, offsets snapped at 0.15 px | 3,817 | 0 | 2 | 3,815 | 0 |
| `fixtures/vrt` corpus c01 to c09 | 14 | 6 | 1 | 2 | 5 |

![Share of placements per tier: GHRSST all regular refs; COP30 45 percent
cut and 55 percent computed; 3DEP all computed as written and all cut
once snapped; the corpus covers every tier](img/m29-tiers.svg)

Three readings.

- **Gridded model output written one step per file lowers completely.**
  GHRSST (and BRAN, m13) is the case virtual Zarr was built for, and for
  it VRT and refs carry the same information. Here the rework is only a
  matter of keeping the projections in step.
- **Imagery mosaics in the wild do not lower at all.** COP30 is m11's
  case: tiles of different widths resampled to one grid, and tiles that
  overlap by a pixel. That is information no virtual Zarr can hold, and
  exactly what VRT exists for.
- **3DEP shows what assertion is for.** Its tiles are 3,612 pixels on a
  3,600-pixel pitch (6 pixels of overlap on each side), and its
  destination offsets drift linearly across the mosaic, from 0 at the
  western edge through -0.01 to -0.03 px across the conterminous US to
  0.10 px in absolute value at the far eastern end. The drift is the
  difference between the VRT's pixel size (2.7777779999999875e-4, so
  about 8e-8 too large) and the 1/3600-degree pitch the tiles sit on.
  Every read of the published VRT therefore resamples every tile
  bilinearly by a few hundredths of a pixel. An exact assertion of the
  pixel size would turn all 3,817 placements into integer ones; the
  overlaps would still need a cut. (Whether GDAL takes a shortcut for
  near-integer windows was not checked here; m27's harness is where to
  check it.) deck.gl-raster's `parseVRT` draws each COG with its own
  georeferencing (m25 section 2), which for this VRT is closer to the
  source pixels than the VRT itself.

The corpus row is small by design: it has one case per tier, and the
nested case (c09) is counted at T1 because the classifier does not
recurse into a child VRT yet, while `vrt-model`'s planner does.

## 5. The plan as a table

The same script writes each placement list as Parquet (zstd, 4,096 rows
per row group) and times a one-window lookup from it:

| VRT | XML as served | XML gzipped | Python XML parse | Parquet | One-window lookup |
|---|---|---|---|---|---|
| GHRSST `mdim.vrt` | 16,630,393 B | 351,694 B | 0.20 s | 247,240 B | 0.012 s, 5 rows (one day, five arrays) |
| USGS 3DEP 1 arc-second | 2,153,591 B | 55,517 B | 0.03 s | 22,331 B | 0.007 s, 2 rows |

The usual argument for tables is size, and it is weaker than it looks.
Gzipped, the XML is within a factor of 1.4 to 2.5 of the table; the
16.6 MB a browser downloads today is a server setting (source.coop sends
the file without `Content-Encoding`), not a format limit. Parsing is not
the bottleneck either: 0.2 s in Python for 38,360 sources.

What the table adds is of another kind:

- **Partial reads.** A reader fetches the footer and the row groups whose
  statistics match its window rather than the whole document. In the
  XML's order (array by array) one day touches 5 of the GHRSST table's 10
  row groups; sorted by time it would touch one.
- **Questions without VRT code.** "Which days are missing", "which
  sources resample" (m11's quiet operations as a `WHERE` clause), "which
  sources changed since the last scan" (m16's etag) are SQL in DuckDB,
  DataFusion, SedonaDB or Polars, and in DuckDB-wasm in the browser.
- **Joins with catalogues.** A placement table joins to STAC items or a
  provider's file list by source name.
- **History where it belongs.** Snapshots of the placement table (Lance,
  Delta, Iceberg) record which sources a dataset was made of; held bytes
  record what those sources contained (m16).

So the placements level at rest is a Parquet table with the header in its
key-value metadata: mdim-refs/0.2's `placements` table, generalised from
slabs to classic windows and operations. GTI is GDAL's own move in this
direction; the difference is that the table here is the plan, not an
index beside one.

## 6. Open modes as a named view

GDAL opens the same bytes as different data models depending on driver
and flag. A netCDF file opens as subdatasets of 2D bands or, with
`GDAL_OF_MULTIDIM_RASTER`, as groups and arrays. A Zarr store opens
either way. A GTI is opened as a raster although its sources are
features. A Parquet refs table opens as a vector layer. The choice is real
and it is hidden in flags.

The rework names it. A virtual dataset is opened with a **view**:

| View | What the reader sees | Natural consumers |
|---|---|---|
| `array` | n-dimensional arrays with named dimensions | xarray (through Zarr, or through the osgeo.gdal xarray backend), zarrs, ArrIR |
| `raster` | 2D bands on a grid | GDAL classic, terra, rasterio, deck.gl-raster |
| `features` | geometries with fields | sf, geopandas, GeoArrow, DuckDB spatial |
| `table` | the plan's own rows at a chosen level | DuckDB, Polars, SedonaDB, Arrow in any language |

m25's rule that the `vrt://` keys decide the family is this choice made
by keys: `array` or `group` makes the result an array, `layer` or `where`
features, and the rest a raster. `vrt://...?transpose=` is a change of
view from array to raster. The `table` view is the new one. Nobody offers
a virtual dataset as its own rows, yet it is the view every ecosystem can
already read.

## 7. The boundaries, and what crosses them

The hard boundaries are of five kinds, and in each case what crosses is
data, never an API:

| Boundary | What crosses today | What does not |
|---|---|---|
| language runtime (R, Python, JS, Rust, Julia) | text, Arrow through the C data interface, Parquet | objects, class hierarchies, driver registries |
| process | Arrow IPC, shared memory (mizu) | handles, caches |
| engine (GDAL, xarray, DuckDB, browser) | files and byte ranges over HTTP | open semantics |
| version (GDAL 3.8 in wasm against 3.13 on the desktop) | the subset both read | newer keys (m27: `a_nodata` refused on 3.8.4) |
| names | strings, each ecosystem with its own grammar | the meaning of a string |

Names are the least specified crossing. One file inside a zip on S3:

| Grammar | Spelling |
|---|---|
| GDAL VSI | `/vsizip/{/vsis3/bucket/a.zip}/b.tif` |
| fsspec chained URL | `zip://b.tif::s3://bucket/a.zip` |
| object_store URL | `s3://bucket/a.zip` (no archive layer) |
| Icechunk | a virtual chunk container for `s3://bucket/`, refs relative to it |
| R dsn | `vsizip()` around `vsis3()`, writing the GDAL form |

m25 section 4.4 types GDAL's grammar as a value (`Dsn`), and m09 has the
chain grammar for byte layers. A mapping between these spellings, both
ways, with a refusal where one side has no equivalent (object_store has
no archive layer; fsspec has no subdataset prefix), is small, has no I/O,
and is needed by every system that reads a name written by another. Of
all the pieces here it has the widest reach for its size.

## 8. Plan once, fetch once, decode once, view many

GDAL evaluates a VRT in one process: it parses, plans, fetches, decodes
and caches with its own block cache, and a second process does it all
again. With the model as tables, the work splits into stages that can
each live in a different process or language:

1. **Plan** (pure, wasm-able): window to placement rows to ref rows.
2. **Fetch**: ref rows grouped into coalesced ranges. The key
   (uri, offset, size, etag) is both the deduplication key and the cache
   key (m05), so two processes that need the same tile fetch it once.
3. **Decode**: the codec chain of the header.
4. **Assemble**: placement copies and per-placement operations (T0 to
   T2); resampling for T3 through rwarp.
5. **Compute**: steps, lowered to an executor (rwarp, an ArrIR backend,
   or GDAL through GDALG) or refused.

The shared-memory systems slot in at 2 to 4. Plan rows become mirai
tasks; decoded windows land in a shared buffer that R and Python workers
read zero-copy through mizu; Arrow's C data interface hands the result to
whatever is in the same process. None of this needs building now. It is
the reason the plan must be data: a plan that exists only inside a C++
object cannot be handed to another process, language or engine.

The JAX lesson applies to the steps level. Shapes and types are known
from the header before any data, and a transformation over a plan
("the same plan for each placement", the way `vmap` maps a program) is a
function on tables. That is enough. The steps level should be a short
list of named, typed operations that lowers to someone else's IR, with
GDAL's pixel functions taken as names in the m09 registry. Expressions
(muparser, exprtk, Python pixel functions) stay GDAL's.

## 9. Is it worth it?

| | Get | Cost | Without it |
|---|---|---|---|
| A new format | nothing an existing form lacks | commit criterion 4; another schema to keep in step | nothing lost |
| A new engine | GDAL parity, eventually | m25: about 41,000 lines to port, ruled out | nothing lost |
| **The model, as a reframing** | one account of every virtual form; lowering as a checked function with reasons; the plan as a table any engine reads; a named view; a name mapping | keeping semantics equal to GDAL (the corpus and m27 carry this); the risk that only wxylib reads the table form; the pull toward an expression language, resisted by stopping at named steps | VRT stays a single implementation; virtual Zarr tools keep ignoring the large existing estate of VRT mosaics; each browser library keeps reimplementing the mosaic subset (m25); quiet operations stay hidden |

The reframing is cheap because most of it exists. `vrt-model` parses the
steps and placements levels and plans them (m25, 32 of 32 reads equal to
GDAL). mdim-refs is the placements and refs levels as tables, with the
global view as SQL. refharvest produces refs from bytes (m23). The oracle
harness keeps the answers per GDAL version (m27). raad.virtualize raises
refs back to VRT. What the reframing adds is four small pieces, none with
I/O:

1. **The tier classifier** in `vrt-model`: lowering as a function that
   returns refs or a reason. A first version is about 230 lines of Python here.
2. **Classic placements as a table**: the mdim-refs `placements` columns
   generalised to windows and operations, so COP30 and 3DEP have the same
   at-rest form as GHRSST.
3. **The view parameter**: `array`, `raster`, `features`, `table`, with
   the `vrt://` family rule as its string form.
4. **The name mapping**: GDAL, fsspec, object_store and Icechunk
   spellings both ways, round-tripping with dsn.

### The first compelling corner

Arrow did not arrive everywhere at once. It filled one corner where it
was clearly better (pandas to Parquet), and each new corner was cheaper
because the last one existed. The same is likely here, and the corner
with the most pull is **VRT in, virtual Zarr out where exact, with a
reason where not**: a VRT reader for VirtualiZarr, through `vrt-model`
compiled for Python. It would bring the existing estate of VRT mosaics
to xarray and Icechunk users. On GHRSST it would emit refs for every
placement. On 3DEP it would report that every placement is a resample
caused by a rounded pixel size, that asserting 1/3600 degree makes them
integer, and that the 6-pixel overlaps then need a cut. That one report
is the whole argument of this note in a tool's output.

The second corner is the `table` view in DuckDB, SedonaDB and Polars,
which costs nothing beyond writing the Parquet. After those, R through
dsn and nanoarrow, and the browser through the wasm build m25 already
plans, fill in as each becomes the cheapest next step, not as a promise
to cover every language.

## 10. Open questions

None of these needs an answer to keep the current work going.

1. **Tier classifier in `vrt-model`?** Recommended (provisional): yes, as
   part of the planner, returning a reason with every refusal.
2. **Classic placements in mdim-refs?** Either mdim-refs grows window and
   operation columns (an 0.3 question for the spec), or classic
   placements get their own table beside it. Recommended: grow mdim-refs,
   so that one spec covers both families.
3. **A VirtualiZarr reader of VRT: build, or offer the idea?** Contact
   with VirtualiZarr, Development Seed or Earthmover is Michael's call;
   the classifier and corpus would come first either way (as m25
   decision 4 already set for the browser libraries).
4. **The 3DEP pixel size.** A provider's VRT, not GDAL's; worth a note
   to USGS only if the m27 harness shows that GDAL does resample those
   reads.

## 11. Not claimed

- The marks in figure 1 are a reading of each project's documentation and
  of earlier notes in this repository, not the result of a common test.
  mori was not checked.
- The tiers are computed from the XML alone. T0 for GHRSST takes the
  array's declared `BlockSize` (1, 512, 512) as the source tiling; the COG
  headers were not read. COP30's tiers come from m10's source table, read
  from the VRT on 2026-10-19. The overlap test is exact for the integer
  placements and per band.
- Snapping 3DEP at 0.15 px is a what-if, not something GDAL does.
- Timings are single runs on the cloud container (Python 3, pyarrow, an
  in-memory buffer), to show orders of magnitude.
- The inputs are upstream files that can change; their SHA-256 sums are
  in the measurement README.
