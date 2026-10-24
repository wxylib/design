# m17: Self-describing reference stores

Status: musing, 2026-10-24. Reconciles a proposed description contract
for published byte-reference stores with what mdim-refs/0.2
([specs/mdim-refs-0.2.md](../specs/mdim-refs-0.2.md), m15) and the wxy
readers already state or infer, measures two BRAN2023 stores and the
fixtures against it, and answers the proposal's open questions. Nothing
here is decided.

## Summary

- A static browser page over the BRAN2023 kerchunk Parquet stores showed
  that a reader can discover a store's **layout** (record size, file
  partitioning, refs compression, builder, host) and needs only its
  **description** (axis roles, fill, packing, codecs, coordinates, time,
  the chunk-to-row rule) to be stated. The proposal is a small
  MUST/SHOULD/MAY-stay-open contract, a sidecar `store.json` and
  conformance checks.
- mdim-refs/0.2 already states most of the MUST list as columns of
  `arrays` or as rules. Its gaps are provenance (builder and date) and a
  rule tying `fill` to the CF attributes. The chunk-to-row rule and
  missing-chunk representation, open in kerchunk Parquet, are explicit
  in the table by construction.
- Two real defects, both found by reading descriptions, neither
  catchable by the byte-identity proofs (those compare stored integers):
  - **Rounded scale_factor.** The R-built store, and the wxylib fixture
    cut from it, carry `0.0078` where the source has
    `0.007782219909131527` (a float32, widened exactly). Every decoded
    BRAN temperature from those stores is about **0.5 C too cold**
    (0.56 C at -2 C, 0.49 C at 30 C).
  - **Fill conflict.** The VirtualiZarr store's `.zarray` says
    `fill_value: -32767`; its CF attributes say `-32768`. wxy's kerchunk
    reader takes the `.zarray` value and writes it over `_FillValue`, so
    wxy on that store would leave land unmasked, reading as -10.01 C.
- A stdlib Python check ([scripts/m17_contract.py](../scripts/m17_contract.py))
  reports the contract per array for kerchunk `.zmetadata` and mdim-refs
  `arrays.json`, compares two builds of the same data, and with
  `--oracle` compares fill, packing and units with osgeo.gdal on a source
  file. It finds both defects above. Recommended home: the producer's
  publish step and the fixtures CI, not a package.
- Recommendations, all small: fix the producer's packing and the fixture;
  one fill rule; optional `producer` and `created` keys in `meta`; one
  `store.json` per store, written from the flat table; orientation and
  longitude range derived from coordinates rather than stated twice.

## 1. The proposal

A browser explorer (one static page,
[virtual-cog-pilot/zarr-explorer](https://mdsumner.github.io/virtual-cog-pilot/zarr-explorer/))
reads two independently built kerchunk Parquet stores of BRAN2023 daily
temperature in `mdsumner/virtualized`: one from VirtualiZarr
(`remote/ocean_temp_2023.parq`), one from R with rhdf5 and GDAL multidim
(`zarr/ocean_temp.zarr`, the store the wxylib fixture
`mdimrefs/bran2023-temp-201001` was cut from). It reads `.zmetadata`,
footers and row windows of the refs files over HTTP range requests,
decodes chunks in the browser (zlib, HDF5 shuffle, fill, packing), and
has a contract tab that labels each description item per variable as
explicit, convention, inferred, missing or conflict.

The finding: nothing the page needed to know about **layout** had to be
agreed in advance. Every guess was about **meaning**. So the proposed
contract is about what a published store states, not how it is arranged:

| | Items |
|---|---|
| MUST | 1 strict JSON; 2 chunk-to-reference rule (C order, record size, file naming, file count); 3 dimension names; 4 axis role per dimension; 5 exactly one fill per array, CF `missing_value` equal to it if kept; 6 packing verbatim, never rounded; 7 codec chain in encode order; 8 coordinates inline; 9 time units and calendar; 10 provenance (builder and version, build date, source URI set) |
| SHOULD | 11 Y orientation; 12 longitude convention and periodicity; 13 vertical `positive`; 14 content summary (chunks, bytes, missing chunks); 15 padding and missing-chunk representation |
| MAY stay open | record size and partitioning, refs compression, which published forms exist, hosting, the harvesting tool |

Items with no slot in a format go in a descriptive sidecar, `store.json`.
Conformance starts as the explorer's contract tab and moves to a
headless check in CI.

## 2. The contract against what wxylib already states

mdim-refs/0.2 is the flat table every published form is projected from
(m13, m15). The contract belongs to the projection step: the table must
carry each fact once so that every form can state it.

| # | Item | mdim-refs/0.2 | Projections (kerchunk, Icechunk, VRT) | wxy-refs reads it from |
|---|---|---|---|---|
| 1 | Strict JSON | `arrays.json` is written by the producer; strict in every fixture | VirtualiZarr's `.zmetadata` has bare `NaN` | `serde_json`, which rejects bare `NaN`: wxy cannot open that store as published |
| 2 | Chunk-to-row rule | explicit: every row carries `dim_0..dim_{n-1}` | kerchunk: fsspec convention plus `record_size`; Icechunk and VRT: internal to the format | kerchunk: implements the convention (`crates/wxy-refs/src/kerchunk.rs`) |
| 3 | Dimension names | `arrays.dims` | `_ARRAY_DIMENSIONS`, `dimension_names`, VRT `Dimension` | yes |
| 4 | Axis roles | coordinate `attrs` (CF `axis` or MOM's `cartesian_axis`) when the source has them | attributes; VRT dimension `type` | not read; roles come from `standard_name`, `units` and names (`wxy_zarr::cf_axis`) |
| 5 | One fill | `arrays.fill` (one value), `attrs._FillValue` beside it; **no rule that they agree** | `.zarray fill_value` and `.zattrs` can disagree (section 3.2) | `fill` wins and is written over `_FillValue` |
| 6 | Packing verbatim | `attrs.scale_factor`, `add_offset`; **verbatim not stated** | attributes | yes |
| 7 | Codec chain | `arrays.codec` plus the Codec mapping table | `.zarray`, Zarr v3 `codecs` | yes |
| 8 | Coordinates inline | `storage` = `inline` or `affine` | inline `raw` rows | yes |
| 9 | Time units and calendar | coordinate `attrs` | attributes | units yes; calendar not used yet |
| 10 | Provenance | `sources` (URI, size, mtime, etag), `meta.plan`, `meta.dataset`; **no builder or date** | none in `.zmetadata` | no |
| 11, 12 | Orientation, longitude range | follow from `affine` start and step, or inline values | follow from coordinates | derived from coordinates |
| 13 | Vertical `positive` | coordinate `attrs` | attributes | not used |
| 14 | Content summary | computable from the rows in one pass | not present | `--dry-run` could report it (m13 section 5.3) |
| 15 | Missing chunks | explicit: `present = 0` (the Presence rule) | kerchunk: null `path` and `raw`; Icechunk: no ref | absent rows read as fill |

So the table already meets the contract on every item except three
rules and one pair of keys, all small (section 4). The defects sit in
the producers and the projections.

## 3. What the stores and fixtures show

The check was run on the three mdim-refs fixtures and on both stores'
`.zmetadata` at `mdsumner/virtualized@1e9c46f`. Full output:
[measurements/m17-contract/report.txt](../measurements/m17-contract/report.txt).
Rows that are not explicit, for the main data array:

| Store | Not explicit |
|---|---|
| fixtures `mdimrefs/arrays.json` (OISST, sst) | axis roles inferred; provenance missing; no `positive` on `zlev` |
| fixtures `mdimrefs/oisst-198109` (sst) | axis roles inferred; no calendar (CF default); provenance missing |
| fixtures `mdimrefs/bran2023-temp-201001` (temp) | provenance partial (`manifest.json`: source index and files, no builder or date) |
| VirtualiZarr `remote/ocean_temp_2023.parq` (temp) | not strict JSON; chunk-to-row and missing chunks by convention; **fill conflict**; provenance missing; content summary missing |
| R `zarr/ocean_temp.zarr` (temp) | chunk-to-row and missing chunks by convention; provenance missing; content summary missing |

Compared with each other, the BRAN builds differ in packing and fill:

```
DIFFER temp scale_factor: 0.0078 (fixture, R store) vs 0.007782219909131527 (VirtualiZarr)
DIFFER temp fill: -32768 (fixture, R store) vs -32767 (VirtualiZarr)
```

### 3.1 The rounded scale_factor

`0.007782219909131527` is exactly a float32 widened to double, which is
how netCDF stores it; `0.0078` is that value rounded to four decimal
places. The rounding is in the R build: the fixture's `arrays.json` and
the R store's `.zattrs` both carry `0.0078`. Four decimal places is
jsonlite's default `digits` for `toJSON()`; the published
`R/mdimrefs.R` writes with `digits = NA`, so the rounding happened
before it (the scanner's description, or an earlier writer). That is a
likely cause, not a confirmed one.

The effect is not small. BRAN packs temperature around `add_offset`
245, so stored integers near -30000 multiply the error:

| Temperature (true scale) | Stored integer | Decoded with 0.0078 minus true |
|---|---|---|
| -2 C | -31739 | -0.56 C |
| 10 C | -30197 | -0.54 C |
| 30 C | -27627 | -0.49 C |

Every BRAN temperature read through the R-built store or the wxylib
fixture is about half a degree too cold. The m13 proofs still hold:
they show that every reader gets the same stored bytes, and the bytes
are right. Packing sits outside a byte proof. That is the case for
item 6 and for an oracle on the description (section 5).

The OISST fixtures carry `0.009999999776482582`, the widened float32,
which `--oracle` confirms against osgeo.gdal on a source netCDF
([oracle-oisst.txt](../measurements/m17-contract/oracle-oisst.txt)).
Note that even `0.01` there would be a rounding: verbatim means the
source's stored value exactly.

### 3.2 The fill conflict

In the VirtualiZarr store, `temp/.zarray` says `fill_value: -32767`
while `_FillValue` and `missing_value` say `-32768`, and `valid_range`
is `[-32767, 32767]`. The same pattern holds for every float64
auxiliary array: `.zarray` says `9.969209968386869e+36` (netCDF's
default double fill) while `_FillValue` (base64-encoded) and
`missing_value` say `1e+20`. Both are consistent with the `.zarray`
value coming from the HDF5 dataset's own fill property and the
attributes from the CF writer.

What each value means:

- The format fill is what an unwritten chunk decodes to.
- CF masks both `_FillValue` and `missing_value`.

The risk the proposal names, masking -32767 and hiding a valid value, is
not a practical one here: -32767 decodes to -10.00 C, below any sea
temperature. The practical risk is the other direction. A reader that
masks the format fill (wxy-refs does: `referenced()` in
`crates/wxy-refs/src/table.rs` writes the array's `fill` over
`_FillValue`) leaves every land cell (-32768) unmasked at -10.01 C, and
masks nothing.

### 3.3 Strict JSON

VirtualiZarr's `.zmetadata` writes `_FillValue: NaN` on the coordinate
arrays as a bare token. Zarr metadata is JSON, which has no NaN; Zarr
v2 encodes a NaN fill as the string `"NaN"`. Python's
`json` accepts the token, so the store works in Python; `serde_json`
and the browser's `JSON.parse` do not. This is an upstream fix in the
writer, not a reason for readers to accept non-JSON. wxy should say
what it found in its error (today it reports serde's line and column).

### 3.4 Coverage

The two BRAN stores have 5479 and 5844 time steps (180 and 192 source
files). That is a difference in the source set, which `sources` already
records for mdim-refs; it only becomes a defect when two stores are
compared by index. Provenance with the source set (item 10) makes it
visible without opening either.

## 4. The contract, reconciled

Changes to the proposed lists, and where each item lives:

| Item | Change | Where it lives |
|---|---|---|
| 1 Strict JSON | keep | every form |
| 2 Chunk-to-row rule | keep; met by construction in mdim-refs and Icechunk | kerchunk only: `store.json` |
| 3 to 4 Dims, axis roles | keep; accept CF `axis` or `cartesian_axis` | coordinate attributes |
| 5 One fill | rephrase: **one fill per array, equal to the format fill and to `_FillValue`; `missing_value`, if kept, equal to it.** A source with two values is described by the producer choosing the CF one for both and saying so in `store.json` | `arrays.fill` and `attrs` |
| 6 Packing verbatim | keep; verbatim means the stored attribute widened exactly to double | `attrs` |
| 7 to 9 | keep | as now |
| 10 Provenance | keep; add optional `producer` (tool and version) and `created` (ISO 8601) to `meta` | `meta`, `sources`; `store.json` for other forms |
| 11 to 12 Orientation, longitude | **derived, not stated**: a function of the coordinates, which item 8 already makes explicit. A stated value can only disagree with them. A check computes and reports them | the check's output; `store.json` summary |
| 13 Vertical `positive` | promote to MUST when the array has a Z axis: it cannot be derived | coordinate attributes |
| 14 Content summary | keep as SHOULD | `store.json`, computed from the table |
| 15 Missing chunks | split: representation is fixed per form (below); padding stays open | spec rule |

**Missing chunks (open question 3).** Two states, kept apart, because
m15 found that conflating them hid an unscanned source:

- *Known empty*: the source has no data for the chunk. mdim-refs:
  a row with `present = 0`. kerchunk: a row with null `path` and `raw`.
  Icechunk: no ref. VRT: no source for the slab. Readers use the fill.
- *Not scanned*: no row at all in the mdim-refs view. Not a valid
  published state: `mr_check()` reports it, and the projection should
  refuse it (today `mr_set_plan()` warns).

The flat export therefore keeps `present = 0` rows rather than dropping
them, and the content summary counts present, known-empty and total.

**Spec edits proposed** (not made here; the spec is not a wxylib format):

1. Rules: "`arrays.fill` equals the array's `_FillValue` and any
   `missing_value` in `attrs`."
2. Rules: "`scale_factor` and `add_offset` are the source's values,
   widened exactly; never rounded."
3. `meta` optional keys: `producer`, `created`.
4. Presence: "the export keeps `present = 0` rows; a missing row is an
   unscanned chunk."

## 5. Conformance

`scripts/m17_contract.py` is about 350 lines of standard-library Python,
plus osgeo.gdal for one option:

```
python scripts/m17_contract.py STORE [STORE ...] [--oracle SOURCE.nc] [--json]
```

- STORE is a kerchunk store (its `.zmetadata`, local or by URL) or an
  mdim-refs `arrays.json`. Each data array gets one row per item.
- Two or more stores are compared on packing and fill.
- `--oracle` reads one source file with osgeo.gdal's multidimensional
  API and compares fill, scale, offset and units with the store. This is
  the description's equivalent of the byte oracle, and the only check
  that catches item 6.
- Exit status 1 on any conflict or mismatch, so it can gate a step.

What it does not do: read refs files (padding, file count and missing-chunk
counts need the rows; DuckDB or pyarrow does that in a few lines), or
open the data. The explorer's contract tab stays the interactive view;
both should report the same states, and the JSON records have the same
shape (store, array, items).

**Where it runs (open question 2).**

- In the producer's publish step: run the check, with `--oracle` on one
  source, before writing any form. The producer is the only place that
  has the source in hand.
- In wxylib CI, over the fixtures and the oracle file the fixtures
  already hold (`mdimrefs/nc/`). Fixtures has no CI yet; core's CI
  already checks fixtures out and can run the script.
- Not as a package. If it grows past one file, that is the sign to stop.

## 6. Answers to the open questions

1. **Sidecar.** One `store.json` per store, at the store root, listing
   the forms present with their relative paths, plus provenance (item
   10), content summary (14), the kerchunk chunk-to-row rule (2) and any
   fill choice made (5). Written by the render step from the flat table,
   which holds every fact already; descriptive only. Its keys are the
   mdim-refs `meta`, `sources` and `arrays` names, so it is a projection
   of the table, not a new format (commit criterion 4). For the flat
   form itself, the same keys belong in the Parquet export's key-value
   metadata (spec open question 5), and `store.json` repeats them.
2. **Checks.** In the explorer, and as the one-file script at the
   producer's publish step and in wxylib CI (section 5). Not a package.
3. **Missing chunks.** Explicit known-empty rows; no row means not
   scanned and is an error (section 4).
4. **The two BRAN builds.** Keep both as comparison fixtures, labelled
   by builder, and make their differences deliberate: fix the packing in
   the R build (and the wxylib fixture), fix the fill in the
   VirtualiZarr build (or document it in `store.json`), and record each
   source set. Differences in builder and coverage are the point of
   having two; differences in description are defects.
5. **Chunk-to-row rule upstream.** Worth a short issue on fsspec once
   `store.json` has carried the rule for a while: the rule is already
   fixed by fsspec's code, so stating it in `.zmetadata` (beside
   `record_size`) costs one key. Not before a trial, and not as a
   blocker: wxy and the explorer both implement the convention.

## 7. Next steps, by value

1. **Producer fix for packing**, then rebuild the R store and correct
   `fixtures/mdimrefs/bran2023-temp-201001/arrays.json`. Every BRAN
   temperature from those depends on it. The fixture fix is one line,
   but it should land with the producer fix so fixture and store agree.
2. **wxy fill handling** (core, small): keep a CF `_FillValue` when the
   attributes have one; use the format fill only for absent chunks; mask
   `missing_value` too when it differs. And name the bad token when
   `.zmetadata` is not strict JSON.
3. **Fixture tidy**: `positive` on OISST `zlev` and the calendar on
   `oisst-198109` time, so the fixtures pass the contract they test.
4. **The check in CI** over the fixtures, with `--oracle` on the OISST
   source file.
5. **Spec edits** of section 4, and `producer` and `created` in the
   producer's `meta`.
6. Upstream: VirtualiZarr's bare `NaN` and its fill choice; the fsspec
   rule question later.

## What do we get, what does it cost, what if we didn't

- **Get:** readers that agree on meaning, not only on bytes; a cheap
  check that caught two defects the byte proofs could not, one of them a
  half-degree bias in every temperature of a store in use; a sidecar
  that adds no format, since it projects the table.
- **Cost:** four spec sentences, two `meta` keys, one script, and a
  render step that writes `store.json`. Each published form needs no
  change beyond correct attributes.
- **Without it:** each reader infers meaning for itself and readers
  disagree quietly; byte-identical stores decode to different values;
  the next producer repeats the fill and packing mistakes, and nothing
  fails.

**Are we overbuilding?** The contract adds no crate and no format, and
the check is one file kept beside the design note. The line not to cross
is a validation package or a sidecar schema with versions of its own:
the table and the spec already say what the sidecar holds.
