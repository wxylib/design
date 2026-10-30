# m23: Byte-reference harvesting with few dependencies

Status: musing, 2026-10-29; decisions in section 8 (2026-10-30). Asks what a general byte-reference harvester
(HDF5 first, then TIFF, GRIB and others) should be, and how much of it
needs writing. Based on crates.io as of 2026-10-29, wxylib/core
(wxy-virtual `scan_tiff`, wxy-refs), the mdim-refs/0.2 spec, m02, m09
(the crate check), m13, m14 (format classes and costs), m15, m16 and m17.
Measurements and the probe code:
[measurements/m23-harvest](../measurements/m23-harvest/README.md).

## Summary

The question, in two forms:

1. Can wxylib start a foundation for harvesting byte references from
   HDF5 (and later TIFF, GRIB and others) in which the harvesting is
   home-grown logic with minimal dependencies, and the native libraries
   for each format are used only in a research track (read the libraries
   and the spec, reverse engineer, test on real files) whose results are
   passed into the generic low-dependency foundation?
2. Or: what is the lightest general harvester that uses the best of what
   already exists in Rust, which wxylib either contributes to or simply
   uses?

The answer is mostly the second form, with the first form's split kept
as the working method:

- **The format parsers already exist.** In 2026 there are pure-Rust,
  range-reading parsers for both formats that matter most. async-tiff
  (Development Seed) already harvests wxylib's TIFFs. async-hdf5 0.1
  (Max Jones, a VirtualiZarr maintainer; modelled on async-tiff,
  metadata only, object_store and reqwest readers, Python bindings with
  a VirtualiZarr entry point) reads B-tree v1 and v2, fixed array,
  extensible array and single-chunk indexes (implicit indexes not yet).
  hdf5-pure 0.47 (no_std capable, one dependency with default features
  off) has a public `Dataset::chunks()` that is the analogue of
  `H5Dget_chunk_info`. GRIB has gribberish and grib-rs. Writing another
  HDF5 parser would be overbuilding.
- **Measured: both HDF5 crates are byte-identical to libhdf5.** On the
  30 OISST files in the fixtures (GDAL-scanned) every one of 120 refs
  matches for async-hdf5 and for hdf5-pure, over HTTPS range reads. On a
  5.3 GB BRAN2023 file (NCI THREDDS, oracle: the VirtualiZarr store in
  the fixtures) all 94,860 refs match by chunk index, offset and size.
- **What is missing is how the index is walked, not how it is parsed.**
  netCDF4 files written by appending put the chunk B-tree's nodes all
  through the file (the BRAN file's 1,696 nodes span 5.3 GB). Both
  crates measured walk the tree one node at a time, so a harvest costs
  one round trip per node: async-hdf5 as shipped took 690 s (exact), and
  hdf5-pure with 1 MiB blocks was stopped after 10 minutes, at the 1 s
  latency from the cloud to NCI. A 120-line walker that fetches each level's nodes
  concurrently, on top of async-hdf5's metadata, did the same file in
  22 s with 32 requests in flight and 13 s with 128, from 1,696 GETs and
  13.9 MB read; with 1 in flight the same walker had not finished
  after 400 s.
- **So the foundation is small and format-free.** Four pieces, none a
  parser: (1) a row contract (the parser yields chunk index, offset,
  size, filter mask; the foundation writes mdim-refs/0.2 rows), (2) a
  latency-aware fetch plan (level-parallel walks, coalesced ranges,
  small node reads instead of large cache blocks), (3) a codec map (HDF5
  filter pipeline, TIFF compression and predictor, GRIB packing to Zarr
  codecs, or a refusal), and (4) an oracle harness per format that
  compares against the native library. Proposed name: `refharvest`.
- **Upstream first, home-grown only for the gaps.** The level-parallel
  walk is offered to async-hdf5 as an issue with the measurements; the
  row contract and oracle harness are the parts nobody else has, because
  they are tied to mdim-refs and the store contract (m17). The research
  track keeps the native libraries (libhdf5 through osgeo.gdal or h5py,
  ecCodes, libtiff) as oracles only.

## 1. What exists, format by format

Checked on crates.io on 2026-10-29, source read for the HDF5 crates.

### 1.1 HDF5 and netCDF4

| Crate | Version, licence | Deps (minimal build) | Reads by range | Chunk refs public | Index kinds | Notes |
|---|---|---|---|---|---|---|
| async-hdf5 | 0.1.0 (2026-03), MIT/Apache | async-trait, byteorder, bytes, futures, num_enum, thiserror, tokio; object_store, reqwest optional | yes, async `AsyncFileReader` (async-tiff's shape), 8 MiB block cache | `chunk_index()`: indices, offset, length, filter mask | B-tree v1 and v2, fixed array, extensible array, single chunk, contiguous; not implicit | metadata only by design; README: experimental, 59% of the HDF5 test suite, no fuzzing; Python bindings and `open_virtual_hdf5` for VirtualiZarr |
| hdf5-pure | 0.47.0 (2026-09), MIT/Apache | byteorder (std, checksum, deflate are features) | yes, sync `Source::read_at`, streaming open | `Dataset::chunks()`: offset, address, stored size, filter mask | B-tree v1, fixed and extensible arrays, implicit; B-tree v2 not enumerated yet | full reader and writer, no_std and wasm; 127k lines; checked in CI against libhdf5 |
| hdf5-reader (roteiro-gis netcdf-rust) | 0.10.1 (2026-10), MIT/Apache | memmap2, libc, parking_lot, lru, smallvec, ndarray | storage trait incl. range requests | collectors per index kind, lower level | all | companion netcdf-reader reads netCDF-3 and netCDF-4; terrio reads netCDF through it |
| rust-hdf5, oxih5, hdf5-rust, consus | various | various | various | partial | partial | younger or wider than needed; not assessed further |
| hidefix | 0.12.0 (2024) | libhdf5 to build the index | no | serialisable index | via libhdf5 | the idea (index once, read concurrently) without the pure parser |
| hdf5, hdf5-metno | C bindings | libhdf5 | no | `H5Dchunk_iter` via FFI | all | research track and oracle only |

async-hdf5 is the closest fit: async, range-first, metadata-only, the
same reader seam as async-tiff, and already wired to VirtualiZarr.
hdf5-pure is the stronger general library and the better second oracle
(it shares no code with async-hdf5 or libhdf5).

### 1.2 The other formats

| Format | Rust today | Harvest gap | Codec gap |
|---|---|---|---|
| GeoTIFF, COG | async-tiff (in core); wxy-predictor for predictors | none for tiled files; strips are the same walk | none for DEFLATE, ZSTD, LZW with wxy-predictor; JPEG and LERC need codecs |
| netCDF classic (CDF-1/2/5) | netcdf3 0.6 (pure), netcdf-reader | header parse is trivial; record variables are one ref per record | none (raw, big-endian) |
| GRIB1, GRIB2 | gribberish 1.9 (VirtualiZarr's GRIB parser and Zarr codec), grib 0.20 (noritada), grib-reader 0.6 | a message walk is a hop from one section 0 to the next: one round trip per message unless an `.idx` sidecar exists | the real problem: each message needs a GRIB decode codec (simple, complex, JPEG 2000, CCSDS packing); there is no zarrs codec for it |
| HDF4, HDF-EOS2 | nothing | map files (h4mapwriter) or a new parser | mostly DEFLATE and raw |
| zip, gzip wrappers | rc-zip, async-zip (m09 sec 4) | stored zip members are refs into the parent | deflated members and gzip are copies, not refs |

The pattern repeats: parsing is solved or nearly so, while the fetch
plan and the codec are where formats differ in cost.

## 2. The measurement

Probe code in `measurements/m23-harvest/probe/` (a Cargo project with
three binaries) and `compare.py`, which checks a harvester's output
against an mdim-refs fixture table.

### 2.1 Correctness

| Files | Oracle | async-hdf5 | hdf5-pure | level-parallel walk |
|---|---|---|---|---|
| OISST v2.1, 1981-09, 30 files, 4 variables (sst, anom, err, ice), NOAA public bucket over HTTPS | fixtures `mdimrefs/oisst-198109` (GDAL `GetRawBlockInfo`, libhdf5) | 120 of 120 | 120 of 120 | 60 of 60 (sst, ice) |
| BRAN2023 `ocean_temp_2010_01.nc`, 5.3 GB, `temp`, 31 x 51 x 5 x 12 chunks, NCI THREDDS over HTTPS | fixtures `mdimrefs/bran2023-temp-201001` (VirtualiZarr store, h5py and libhdf5) | 94,860 of 94,860 | stopped (see 2.2) | 94,860 of 94,860, by index, offset and size |

Each OISST variable is one chunk per file, so OISST checks that the
superblock, object header, layout and filter messages are read right.
BRAN checks the B-tree: three levels (1, 30, 1,665 nodes), no filter
masks set.

### 2.2 Cost of the walk

| Walk | Requests | Bytes read | Wall time |
|---|---|---|---|
| level-parallel, 128 in flight, 8 KiB per node | 1,696 index GETs plus async-hdf5's metadata blocks | 13.9 MB for the index | 12.8 s (6.8 s of it opening the file and finding `temp`) |
| level-parallel, 32 in flight | same | same | 21.8 s (6.5 s open) |
| level-parallel, 8 in flight | same | same | 60.4 s (2.9 s open) |
| same walker, 1 in flight (sequential) | same | same | stopped at 400 s, not finished |
| hdf5-pure, sequential, 1 MiB blocks, no read-ahead | 265 one-MiB blocks fetched before it was stopped, at blocks 0 to 818 of about 5,000 (one in three touched) | 265 MiB by then; extrapolated about 1.3 GB | stopped after over 10 minutes; extrapolated over an hour |
| async-hdf5 0.1.0 as shipped, sequential, 8 MiB blocks | not instrumented; at most 632 blocks (the file is 5.3 GB) | not instrumented; up to the whole file | 690 s, 94,860 of 94,860 exact |

The latency from the cloud container to NCI is about 1 s per request,
for 64 KiB and 1 MiB alike. At that latency the number of sequential
round trips is the whole cost. A large cache block does not help when
the nodes are hundreds of megabytes apart, and makes each miss cost
more bytes.

Why the nodes are scattered: libhdf5 grows a B-tree v1 as chunks are
appended and allocates each new node at the end of the file, next to
the chunks written at the same time (observed here; the likely cause).
Any file written one time step at a time (most model output, BRAN
included) should look like this. Files written in one go, or repacked, keep the index
near the front and are cheap either way.

## 3. What the foundation is

A harvester is a pipeline from a URL to mdim-refs rows. The parser is
borrowed; the foundation owns the four pieces around it.

```
URL --> fetch plan --> format parser --> row contract --> refs table
          ^                 |                 |
          |   node addresses|                 +--> codec map (or refusal)
          +-----------------+
                       oracle harness (research track, native libs)
```

### 3.1 Row contract

The narrowest interface every format can meet:

```rust
pub struct ChunkRef {
    pub index: Vec<u64>,   // chunk grid position
    pub offset: u64,       // absolute byte offset in the source
    pub size: u64,         // stored bytes
    pub skip: u32,         // filters not applied (HDF5 filter mask; 0 elsewhere)
}

pub struct ArrayRefs {
    pub name: String,
    pub shape: Vec<u64>,
    pub chunks: Vec<u64>,
    pub dtype: String,             // Zarr v3 data type
    pub codecs: Vec<serde_json::Value>, // Zarr v3 codec chain, or Err(refusal)
    pub fill: Option<serde_json::Value>,
    pub attrs: serde_json::Map<String, serde_json::Value>,
    pub refs: Vec<ChunkRef>,
}
```

Rows go out as mdim-refs/0.2 (one row per chunk, `present` explicit,
placements per m15), with source keys by path and ETag (design issue
#36). This is the same shape wxy-refs reads today, so nothing downstream
changes: the table is the scan.

A chunk whose filter mask is not zero is a chunk whose codec chain
differs from its array's. The contract keeps the mask; the writer either
gives that chunk its own codec note in `info` or refuses the array. No
file checked has one; the check belongs in the oracle harness.

### 3.2 Fetch plan

The general rule from section 2: harvest cost is the number of
sequential round trips, so walk indexes breadth first and fetch each
level concurrently.

- **Index trees** (HDF5 B-tree v1 and v2, extensible arrays): one
  concurrent batch per level, small reads sized from the node header
  (8 KiB covers a v1 chunk node with K = 32 up to rank 7), retry on
  short reads.
- **Linear chains** (GRIB messages, TIFF IFD chains, netCDF-3 records):
  no concurrency is possible without a sidecar, so use the sidecar when
  it exists (`.idx` for GRIB) and otherwise read large sequential blocks.
- **Many files**: files are independent, so concurrency across files
  hides latency even for sequential walkers; a 365-file year is a batch.
  Per-file metadata cost (6.5 s for BRAN's open and the lookup of
  `temp`, through async-hdf5's 8 MiB block cache) is then the next
  thing to shrink.

This is where async-hdf5 is best improved in place: its B-tree walkers
are recursive and sequential. The change is local (collect a level's
child addresses, then `buffer_unordered`), and the probe's 120 lines
show the shape.

### 3.3 Codec map

The parser reports the format's own description (HDF5 filter ids and
client data, TIFF compression and predictor tags, GRIB data
representation template); the map turns it into a Zarr v3 codec chain
or a named refusal. wxy-virtual already does this for TIFF; HDF5 needs
shuffle, deflate, fletcher32 (strip), scale-offset (refuse at first),
szip and the common plugin filters (zstd, blosc, lz4, bitshuffle).
Refusals are rows too: an array that cannot be referenced is recorded
as such, not dropped (m17).

### 3.4 Oracle harness

The research track's output, per format: a corpus of real files, the
native library's answer for every chunk, and a script that compares.
For HDF5 the oracles are osgeo.gdal (`GetRawBlockInfo`, as the OISST
fixtures already use) and, where GDAL cannot (unallocated chunks raise
in GDAL 3.13), libhdf5's `H5Dchunk_iter` through h5py. The fixture
tables in wxylib/fixtures are already this for two collections.

## 4. The research track

Kept from the first form of the question: native libraries are for
finding out, not for shipping. Per format, one dossier under
`research/<format>/` (or in fixtures, next to the corpus):

1. **Spec.** The format's own document (HDF5 File Format Specification
   v3/v4, TIFF 6 and the COG notes, WMO GRIB manual, netCDF classic
   format spec) and the parts that bear on byte refs.
2. **Libraries.** What the native library does that the spec does not
   say: libhdf5's choices for netCDF-4 (B-tree v1 by default, K = 32,
   where leaves go when appending), ecCodes' message scan, libtiff's
   strip and tile edge cases, GDAL's driver quirks.
3. **Reverse engineering.** `h5dump -p -H`, `h5ls -v`, hex walks from the
   superblock, and the native library's chunk query, against the same
   file, so a disagreement is explained before it is coded around.
4. **Real files.** A corpus chosen from m14's ranking (BRAN, OISST,
   GHRSST, ERA5 netCDF, CMIP6, a GRIB2 GFS cycle), each with its oracle
   rows, plus the awkward ones (B-tree v2 from h5py `libver='latest'`,
   unlimited dimensions in two axes, filter masks, external storage,
   userblocks, `/vsicurl/`-only hosts).
5. **Verdict.** Referenceable as is, referenceable with a codec that does
   not exist yet, or a copy. The verdict, the corpus and the oracle rows
   are what pass into the foundation; the native library does not.

## 5. Not overbuilding

The m09 crate check, answered:

| Piece | Exists? | Decision |
|---|---|---|
| HDF5 parser | yes, twice (async-hdf5, hdf5-pure) | use async-hdf5; hdf5-pure as second oracle |
| TIFF parser | yes (async-tiff) | keep |
| GRIB parser | yes (gribberish, grib) | use when GRIB is picked up |
| level-parallel index walk | no | upstream to async-hdf5; keep the probe until it lands |
| row contract to mdim-refs | no (VirtualiZarr's ManifestStore is the Python analogue) | own it; it is the reason the crate exists |
| codec map | partly (wxy-virtual for TIFF, VirtualiZarr for HDF5 in Python) | own the Rust version; reuse VirtualiZarr's filter table as the reference |
| oracle harness | partly (fixtures, m17 script) | own it, in fixtures |
| GRIB Zarr codec in Rust | no | a zarrs codec over gribberish, later; offer to gribberish |

What do we get: Rust harvests that wxylib, raad.virtualize and the
browser can share, measured against the native libraries, at a cost set
by latency rather than file size.

What does it cost: one small crate (rows, plan, codec map; a few hundred
lines over async-hdf5 and async-tiff), an issue upstream, and the corpus
work that the fixtures already started.

What if we didn't: harvesting stays in Python with libhdf5 (VirtualiZarr,
kerchunk) or in R with GDAL, which is fine on a workstation next to the
data and slow from anywhere else; wxylib keeps reading tables it cannot
make, which is commit criterion 2's answer (a producer it does not own)
but leaves the browser and the wasm build with no harvester at all.

## 6. Name, home and relations

- **Name.** `refharvest` (free on crates.io; no geo, no "gdal"). It
  matches raad.virtualize's harvest, collate, render stages. Other free
  names: `refscan`, `chunkrefs`.
- **Home.** Its own repository once stage 1 holds (geo-free, like m09's
  registry and byte views), in the wxylib org. Until then the probe
  stays in this measurement directory, not in core.
- **wxy-virtual.** `scan_tiff` becomes the TIFF front of `refharvest`;
  wxy-virtual keeps the Icechunk and Zarr side. wxy-refs keeps reading
  the tables; it never needs to know which harvester wrote them.
- **raad.virtualize.** Stays the producer: it owns collate and render,
  dataset recipes and publishing. `refharvest` is a harvest stage it can
  call (through Python bindings, or async-hdf5's own bindings once the
  walk lands upstream) in place of h5py or GDAL where those are slow or
  absent. The existing R and Python harvests become oracles for it.
- **VirtualiZarr.** The parallel effort in Python, with async-hdf5
  already a parser for it. Rows from `refharvest` and a VirtualiZarr
  ManifestStore describe the same bytes; m17's contract script can check
  one against the other.
- **Versioning (m16).** Rows keyed by (file, ETag) keep a harvest
  append-only; a rerun of a changed file is a new fragment.

## 7. Stages, if picked up

1. **HDF5 via async-hdf5.** `refharvest` with the row contract, the
   level-parallel walk (local until upstream), the HDF5 codec map, and
   mdim-refs output; oracle-checked on OISST and the full BRAN 2010 temp
   pair; a corpus case for each index kind. Done when it writes the
   fixture tables byte for byte.
2. **Upstream.** Issue on async-hdf5 with section 2's numbers and the
   walk; adopt the release that includes it and delete the local walk.
3. **TIFF.** Move `scan_tiff` behind the same contract; GHRSST's 2024
   COGs (m13, ghrsst-store) are the oracle.
4. **Many files.** Concurrency across files and a lighter open; a full
   BRAN variable (all months) as the benchmark against the R harvest.
5. **netCDF classic, then GRIB** (with the codec question first), then
   HDF4 only if m14's ranking asks for it.

## 8. Decisions

Settled 2026-10-30:

1. **Home.** `refharvest` is a wxylib repository (geo-free, needed by
   the browser as well as the producers), not the Rust half of
   raad.virtualize.
2. **Parser.** Try and measure: async-hdf5 first, with the level-parallel
   walk carried locally until it lands upstream. Parity is checked
   against libhdf5 through rhdf5 devel (`h5getAllChunkInfo`, which wraps
   `H5Dchunk_iter`) as well as the GDAL and VirtualiZarr fixture tables;
   hdf5-pure stays the independent second parser for the oracle harness.
3. **Upstream.** The async-hdf5 issue is opened by a person, with a
   Docker reproduction of section 2.2 (stock walk, level walk and rhdf5
   on the same file).
4. **Walk cost as metadata.** Yes: each harvest records its requests,
   bytes and seconds per source file in the store's description (m17),
   so a store says what it cost to make and what a rerun would cost
   (m16).
