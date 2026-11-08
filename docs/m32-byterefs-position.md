# m32: wxylib's position on byterefs

Status: position for review, 2026-11-08. Not settled: the choices in
section 3 are for a joint meeting of the byterefs implementers, and each
recommendation here is wxylib's input to it, not a decision. Based on
byterefs/spec at `70dc249` (brief, `spec/byterefs-0.1.md`, decisions
0001 to 0006, IMPLEMENTATIONS.md), mdsumner/raad.virtualize at `ab62f6f`
(including `docs/handover/`, the production handover of 2026-11-06),
wxylib/core at `57909df` plus PRs #35 and #36, wxylib/refharvest and
wxylib/fixtures at main. Builds on m02 (the pilot), m15 (reconciliation),
m16 (versioned tables), m17 (self-describing stores), m23 (harvesting),
m31 (view-to-chunk planner) and the commit criteria.

## Summary

The byte-reference table that wxylib piloted as mdim-refs/0.2 now has its
own home: byterefs/spec, with numbered decision records and gates. It is
the same layout under a new identifier (`byterefs/0.1`), with remap rules
that travel with the table and a `meta.default_target`. raad.virtualize,
the producer of every live store, already writes the new identifier.

- **wxylib's role.** wxylib is a reader and a test bed, not the owner of
  the format. It brings a Rust reader (`wxy-refs`), a second producer
  (`refharvest`), fixtures with GDAL oracle reads, and the oracle harness.
  This is the position the commit criteria want: no wxylib format
  (criterion 4) and tables made outside wxylib (criterion 2).
- **What wxylib needs from 0.1.** Two things above all: a fixed published
  encoding, since the Parquet export is what `wxy-refs` reads and it is
  still unspecified (brief question 7), and an identifier that names one
  layout. Today `byterefs/0.1` is written before 0.1 is fixed.
- **The gate needs a second producer.** The v0.1 gate asks for two
  independent implementations producing the fixture tables. Only
  raad.virtualize is listed. `refharvest` already reproduces the OISST
  and BRAN fixture rows from libhdf5-independent code, and is the obvious
  second one.
- **Overview levels (decision 0006).** Accept, with two clarifications.
  Levels as ordinary arrays cost `wxy-refs` nothing and are exactly what
  the m31 planner reads.
- **Two gaps to raise.** Source identity by (source, etag), proposed in
  the mdim-refs draft after byterefs was seeded, did not carry over. And
  the tables do not state a CRS, which every georeferenced reader needs.
- **Done now, without waiting.** `wxy-refs` accepts both identifiers
  (core #35) and applies `meta.default_target` (core #36). The mdim-refs
  draft in this repository is marked as superseded by byterefs/spec.

## 1. Where byterefs stands

| Item | State |
|---|---|
| Spec text | `spec/byterefs-0.1.md`, draft, not normative until the v0.1 gate. The mdim-refs/0.2 text plus two changes: the identifier (0003) and remap rules that travel with the table (0004) |
| Accepted decisions | 0001 scope, 0002 start from mdim-refs/0.2, 0003 identifier `byterefs/<major>.<minor>` (readers accept `mdim-refs/0.2` until 0.2 is tagged), 0004 verbatim sources, prefix remap rules, `meta.default_target` |
| Proposed decisions | 0005 grammar for `placements.source_array` (`<name>`, `lift:<name>`, `band:<n>`, `band:<n>/dir:<k>`); 0006 overview levels as ordinary arrays (`overview_of`, `overview_factor`, `overview_resampling`) |
| Normative encoding | SQLite store; the Parquet export (`arrays.json`, `refs_<array>.parquet`, `sources.parquet`) is "the published one", but its layout is open question 5 / brief question 7 |
| Fixtures, schema, conformance | Directories hold a README only |
| Implementations listed | raad.virtualize (producer), `wxy-refs` (reader), ArrIR `arrir-layout` (reader, design), zaro (reader of the SQLite store). The page says no implementation writes `byterefs/0.1` yet; raad.virtualize does (`R/mdimrefs.R` `MR_FORMAT`) |
| Production | The handover proposes a research lane and a production lane with a gate between them; production stores "stamp the version". IBCSO, Bedmap3 and GEBCO are the production pilot, built by hand; the rest are drafts on scratch |

What raad.virtualize writes into `arrays.json` today, beyond the spec:
`meta` (including `default_target`), `dimensions`, and a per-array
`summary` (chunks, present, absent, bytes). The summary is the content
summary that the v0.2 gate asks to define.

## 2. wxylib's role

wxylib contributes four things to byterefs, and owns none of the format:

| Contribution | What it is | State |
|---|---|---|
| Reader | `wxy-refs`: the Parquet export as virtual Zarr arrays over `object_store`, with the cache inside; writes Icechunk | Oracle-tested against GDAL on OISST, BRAN2023 and GHRSST stores built by raad.virtualize |
| Producer | `refharvest`: pure-Rust HDF5 harvest (async-hdf5 fork with the level-parallel B-tree walk) writing the flat export | Rows identical to libhdf5, hdf5-pure and the fixture tables for OISST and BRAN; writes `mdim-refs/0.2` |
| Fixtures | wxylib/fixtures `mdimrefs/`: synthetic 3-day store with a never-written chunk, OISST September 1981, BRAN2023 January 2010, synthetic Bluelink (many chunks per file), each with GDAL reads | Brief section 10 step 5 names these as the first byterefs fixtures |
| Conformance runner | `oracle-case/0` (m27): questions apart from per-GDAL-version answers; the m17 description check script | Working in wxylib/fixtures and core |

The stance behind this: a table read identically by several independent
readers, produced by more than one producer, is worth more than a
wxylib format. If byterefs fixes the encoding and wxylib reads it
exactly, commit criteria 2 and 4 hold by construction.

## 3. Choices for the meeting

Each choice lists the options and wxylib's recommendation. The order is
by how much each blocks wxylib.

### 3.1 The published encoding (brief question 7)

`wxy-refs` reads only the Parquet export, and ArrIR's `arrir-layout`
binds the same "three-file" form. The SQLite store is the producer's
working encoding.

| Option | For | Against |
|---|---|---|
| A. Fix the three-file export for 0.1: `arrays.json` (format_version, meta, dimensions, arrays, remap), `refs_<array>.parquet`, `sources.parquet`, with a JSON schema and an Arrow schema | It exists; two readers and one producer use it; rows sorted by dims, row groups along `dim_0`, dictionary-encoded `path` are already measured needs (22.8M refs) | A sidecar JSON can drift from the Parquet files it describes |
| B. One self-describing Parquet file per array, metadata in key-value footer | No sidecar; one object per array | Every reader and the producer change before 0.1; `arrays` and `remap` are store-level, so they repeat per file |
| C. One Parquet file per store | One object | Arrays have different ranks, so the chunk keys do not share a schema |

**Recommendation: A for 0.1**, with `meta`, `dimensions` and `summary`
written into the spec as optional keys, and B left as a 0.2 question. It
fixes what is already read and leaves the single-file form to be measured
rather than argued.

### 3.2 The identifier before 0.1 is tagged

Decision 0003 says producers stop writing `mdim-refs/0.2` once 0.1 is
tagged. It does not say what to write before. raad.virtualize writes
`byterefs/0.1` now, so if 3.1 changes the layout, two layouts carry one
identifier.

| Option | Consequence |
|---|---|
| A. Keep writing `byterefs/0.1`; every store written before the tag is scratch and is rebuilt at the tag | No code change; relies on every pre-tag store being rebuilt (0003 records a full Bluelink daily variable rebuilding in about 16 minutes), including the production pilot |
| B. Write `byterefs/0.1-draft` until the tag | Unambiguous; readers that match on the `byterefs/` prefix (`wxy-refs` after #35, raad.virtualize's Icechunk render) accept it unchanged |
| C. Keep writing `mdim-refs/0.2` until the tag | What 0003 literally implies; undoes raad.virtualize #62 |

**Recommendation: B.** It costs one constant in the producer and no
reader change, and it means a store that says `byterefs/0.1` always has
the tagged layout. A is acceptable if the meeting records that the three
production pilot stores are rebuilt at the tag.

### 3.3 The second implementation for the v0.1 gate

| Option | For | Against |
|---|---|---|
| A. `refharvest` | Independent code (Rust, no libhdf5, no GDAL); already equal to the fixture rows for OISST and BRAN | HDF5 only; the gate's COG-with-predictor fixture needs a TIFF harvest (async-tiff, m23) |
| B. GDAL `gdal mdim chunk-info` | The reference library | Not merged; timing is outside the group's control |
| C. A VirtualiZarr adapter (manifest to rows) | Wide reach | Its fills and attributes differ from the source (m17), so it tests the description check more than the rows |

**Recommendation: A**, adding a TIFF path to `refharvest` for the COG
fixture, and listing it in IMPLEMENTATIONS.md. B and C count later when
they reproduce the fixture tables.

### 3.4 Where the fixtures live

**Recommendation:** copy the smallest wxylib/fixtures cases (the
synthetic 3-day store, OISST September 1981, synthetic Bluelink) into
byterefs/spec `fixtures/` with their expected tables, under Apache-2.0.
wxylib/fixtures then consumes them pinned by commit. The alternative, referencing wxylib/fixtures from the spec,
would make wxylib the format's home again.

### 3.5 Overview levels (decision 0006)

**Recommendation: accept**, with two clarifications to the text:

1. `overview_of` always names the full-resolution base, never another
   level, so a reader finds every level with one filter and the factors
   share a base.
2. State whether a reduction along a non-spatial dimension (daily to
   monthly means) is an overview. wxylib's view: no, that is a derived
   product with its own array, because a viewer that picks a level by
   screen scale must never switch time aggregation silently. If the
   meeting agrees, `overview_factor` covers only the dimensions a
   viewer zooms along.

For wxylib, 0006 costs nothing in `wxy-refs`: a level is an array with
its own dimensions and coordinates, which it already reads. The m31
planner reads levels through `overview_of` and `overview_factor`, with
any factor and any dtype, and `wxy_warp::choose_overview` can take the
same list from a refs store. Held or derived levels (bytes the producer
computes, as BRAN needs) stay open and wait on m16's held-bytes work.

Decision 0005 needs no change from wxylib: `wxy-refs` never rebuilds a
plan, so it does not parse `source_array`. One note for readers that do:
GDAL's `GTIFF_DIR:<k>` counts every IFD, mask IFDs included, so `k` is
the producer's reading of each file, not a level number.

### 3.6 Source identity (not yet in byterefs)

The mdim-refs draft gained open question 6 after byterefs was seeded:
key `sources` by (source, etag), so a file rewritten in place becomes a
new source rather than silently pairing new bytes with old offsets
(m16 section 6a). byterefs 0.1 keeps `source` UNIQUE, and brief question
8 (which integrity fields are required, what a reader does on mismatch)
is undecided.

**Recommendation:** raise it as a byterefs decision under question 8,
with the m16 measurement as evidence. On the wxylib side, `wxy-refs`
should read `sources.parquet` and pass `etag` on as Icechunk's
`checksum_etag` and as part of the cache key; today it reads neither.

### 3.7 CRS (not stated in the tables)

Decision 0001 puts georeferencing out of scope "beyond carrying the
source's attributes". The tables carry no CRS today, and `wxy-refs`
falls back to assuming EPSG:4326 when the coordinates look like latitude
and longitude. Every projected source (IBCSO, Bedmap3, REMA, the polar
sea ice grids) is unreadable as georeferenced data without one.

| Option | Consequence |
|---|---|
| A. Carry it as CF: a `crs` coordinate-kind array with `grid_mapping` attributes (`crs_wkt`, `spatial_ref`), named by each data array's `grid_mapping` attribute; for TIFF sources the producer writes `crs_wkt` from the GeoKeys | Within 0001's scope (carrying attributes); every CF reader already understands it |
| B. A `meta.crs` key | Simple, but one CRS per store, and not what CF readers look for |
| C. Leave it to the plan (the mdim VRT) | Readers that never open the VRT (`wxy-refs`, kerchunk, Icechunk) stay without it |

**Recommendation: A**, as a required statement in the description
contract (brief question 10, m17), and brought forward from v0.2
because the planner and every warp need it.

### 3.8 Per-axis chunk edges

The proposed `chunk_edges` column (brief question 5, from m10) is now a
byterefs question at the v0.3 gate. Commit criterion 4 follows it: the
extension is agreed in byterefs/spec before any wxylib code writes it.

## 4. Done now

| Change | Where |
|---|---|
| Accept `byterefs/` and `mdim-refs/` identifiers | core #35 |
| Apply `meta.default_target` when no target is given (0004) | core #36 |
| Mark `specs/mdim-refs-0.2.md` as superseded by byterefs/spec; point commit criterion 4 at byterefs | this note's pull request |

Held until the meeting: switching `refharvest` to the new identifier
(3.2 decides which string), reading `sources.parquet` in `wxy-refs`
(3.6), and replacing the EPSG:4326 fallback (3.7).

## 5. What do we get, what does it cost, what if we didn't

- **What do we get.** One table format with several independent
  producers and readers, owned by none of them; wxylib reads what
  production publishes without a wxylib format; the v0.1 gate becomes
  reachable because wxylib supplies the second producer and the
  fixtures.
- **What does it cost.** A TIFF path in `refharvest`; moving fixtures
  into byterefs/spec; following byterefs's decision process rather than
  changing the layout from a wxylib design note.
- **What if we didn't.** `wxy-refs` would track one producer's export by
  reading its code, the gate would wait on GDAL, and the mdim-refs draft
  in this repository and byterefs/spec would drift apart.

## 6. Open

- Whether the meeting takes 3.2 B or rebuilds the pilot stores at the tag.
- Whether `summary` should count bytes of inline chunks.
- Which published store first carries indexed overview levels for the
  m31 planner to read.
