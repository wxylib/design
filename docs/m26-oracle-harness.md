# m26: An oracle harness

Status: musing, 2026-11-05. Builds the GDAL oracle harness that m09
section 6 recommends as the first GDAL infrastructure candidate, and
makes it the base that m25's VRT conformance corpus can sit on. Based on
wxylib/fixtures at `e203c85` with its open PR #13 (the first VRT corpus),
wxylib/core at `caba7b2` with its open PR #29 (`vrt-model`), wxylib/web
PR #21 (`vrt_oracle.py`) and m23 section 3.4 (oracles per harvest
format). Implementation: wxylib/fixtures `ORACLE.md` and
`scripts/oraclecase.py`, wxylib/core `crates/oracle-case`.

## Summary

- **The missing piece is a format, not a library.** wxylib already has
  13 oracle scripts and 14 test files that check against them. Each
  script writes its own `manifest.json` shape; each test re-implements
  finding the checkout, decoding the `.bin` files and comparing. Each set
  holds one GDAL version's answers, overwritten when regenerated.
- **Questions apart from answers.** A set's `cases.json` says what to
  ask (open this dsn, read this window, this slab, these features);
  `answers/<oracle-id>/` holds one oracle run's answers. GDAL 3.8 (the
  browser builds), 3.12 and 3.14dev answer the same questions side by
  side, and the difference between two answer sets is a finding.
- **The recorder is generic.** Because the questions are declarative,
  one script answers any set: `oraclecase.py record <set>` with
  osgeo.gdal, 3.8 or later. `diff` compares two answer sets; `adopt`
  describes an existing set in the format without touching its files.
- **The reader is a small Rust crate with no geo dependencies**,
  `oracle-case`, in the core workspace, extracted when another project
  uses it (the m25 rule for `vrt-model`).
- **First results.** `cog/` adopted: GDAL 3.8.4 reads all 15 windows
  byte-identical to the 3.12.2 answers it was made with, and wxy-tiff
  matches both. The VRT corpus of fixtures PR #13 hosted in place: 31 of
  its 32 reads are identical on 3.8.4; the 32nd is a refusal, since
  GDAL 3.8.4 has no `a_nodata` key in `vrt://`. A browser reader built on
  GDAL 3.8 would not read that case.

## 1. What exists

| Where | Oracle | Shape |
|---|---|---|
| fixtures `scripts/make_*_fixtures.py` (11) and `oracle_*.py` (2) | GDAL through osgeo.gdal or rasterio | one `manifest.json` per set, a different schema each; `.bin` per answer; GDAL version as a single field |
| fixtures PR #13 `vrt/` | GDAL 3.12.2 through rasterio | `manifest.json` with `dsn` and `requests` (window, buf, file) |
| fixtures `oracles` workflow | GDAL HEAD in gdal-r-python:dev | regenerates whole sets, overwriting the previous version's answers |
| core tests (14 files) | the sets above | each has its own `fixtures()`, decode and compare |
| web PR #21 `vrt_oracle.py` | GDAL through pyogrio | one JSON of features for the vector VRT page |
| refharvest (m23 sec 3.4) | osgeo.gdal `GetRawBlockInfo`, h5py | per-format chunk tables |

The sets are good; what they lack is a common shape, so every new
consumer (core, the browser pages, Python and R bindings, `vrt-model`)
writes the same loader again, and a GDAL change shows up only as a
failing test after a regeneration, never as a recorded difference.

## 2. The crate check (m09 section 5)

| Prior art | What it does | Why it is not this |
|---|---|---|
| GDAL `autotest` | GDAL's own tests; expected values are assertions in Python (checksums, values) | tests GDAL; answers live in code, not data another language can read |
| pytest-regressions, syrupy (Python), insta (Rust) | snapshot testing: record a run's output, compare later runs | snapshots of the implementation's own output, in one language |
| zarr-developers/zarr_implementations | data written by several Zarr implementations, read by each other | the closest pattern (a cross-implementation matrix); Zarr only |
| terrio `compare_vrt_with_gdal.py` | runs GDAL and terrio on VRT files | a script, answers not kept |

Nothing records a reference library's answers as language-neutral data
with the version beside them. So: a format (the part to share), a
recorder in Python next to the fixtures (where GDAL runs), a reader per
language (Rust first). No new repository: the format and recorder live
in wxylib/fixtures, the crate in the core workspace.

## 3. The format: `oracle-case/0`

Defined in full in fixtures `ORACLE.md`. In short:

```
<set>/cases.json                       questions
<set>/answers/<oracle-id>/answers.json answers of one run, with the oracle's version
<set>/answers/<oracle-id>/*.bin|*.json arrays (raw, little-endian, C order) and features
```

| op | Asks | Answer |
|---|---|---|
| `raster.info` | dataset structure | size, band types, nodata, blocks, overviews, geotransform, CRS |
| `raster.read` | `window`, `buf`, `bands`, `resampling` | values (band, row, col) |
| `mdim.info`, `mdim.read` | `array`, `start`, `count`, `step` | dims, type, attributes; values |
| `vector.read` | `layer`, `bbox`, `where` | fields, CRS, features (ISO WKT) |

Four choices carry the design:

1. **The dsn is the test.** It is written as the implementation should
   receive it: path, VSI chain, driver prefix, `vrt://` string or inline
   document. Relative names resolve with the set directory as working
   directory, so `vrt://src/a.tif?bands=1` and `NETCDF:"x.nc":sst` work
   unchanged; `{set}` stands for the absolute set path in chains such as
   `/vsizip/{set}/tiles.zip/mosaic.vrt`. This is what lets one format
   host m25 section 4.4's source-name table.
2. **A refusal is an answer.** `status: error` with GDAL's message. An
   implementation that reads what GDAL refuses is reported, and a
   version that starts or stops refusing (as `a_nodata` above) shows in
   the diff.
3. **Tolerance belongs to the case**, not the test: exact by default,
   absolute or relative, with a count of cells allowed to differ and a
   note. A known difference by design (GDAL's float mode, m20) is a
   case with a note, not a skipped test.
4. **Types are numpy names** and arrays raw bytes with a sha256, so any
   language reads them with what it has.

`messages` keeps GDAL's warnings and debug lines per case: the `CPL_DEBUG`
capture that warp oracles already use (overview choice, chunk lines)
becomes part of the answer when a case sets `config`.

## 4. What was built

- fixtures: `ORACLE.md`; `scripts/oraclecase.py` (`record`, `diff`,
  `adopt-cog`, `adopt-vrt`, `list`; osgeo.gdal 3.8 or later); `cog/`
  described as a set with answers `gdal-3.12.2` (adopted, files
  unchanged) and `gdal-3.8.4` (recorded); an `answers` workflow that
  answers sets with GDAL HEAD and writes the diff against every answer
  set present into the run summary.
- core: `crates/oracle-case` (serde, serde_json, sha2, thiserror):
  `Set::open`, `Set::from_env` (skip when absent), `answers`,
  `answers_default` (`ORACLE_ID` or the newest GDAL), `values_bytes`
  (size and checksum checked), `values_f64`, `features`, `compare`. Its
  own test set is answered by GDAL 3.8.4. wxy-tiff's new
  `tests/oracle_case.rs` reads every `cog/` window against every answer
  set; it skips until core's fixtures pin includes `cases.json`.

Measured (GDAL 3.8.4 from Ubuntu 24.04, Python 3.12):

| Set | Answer sets | Result |
|---|---|---|
| `cog/` | 3.12.2 (rasterio, as made), 3.8.4 | 15 of 15 windows byte-identical; wxy-tiff identical to both |
| fixtures PR #13 `vrt/`, adopted in a scratch copy | 3.12.2 (rasterio), 3.8.4 | 31 of 32 reads identical; `v05-nodata` refused by 3.8.4 ("Unknown option: a_nodata") |

## 5. Hosting the VRT corpus

The corpus of fixtures PR #13 needs no second copy. Its manifest already
has the shape of `raster.read` questions (`dsn`, `window`, `buf`), so
`adopt-vrt` writes `vrt/cases.json` and an answer set pointing at its
existing `oracle/*.bin`. From there:

1. its generator writes `cases.json` directly and lets the recorder
   answer it (osgeo.gdal, which project practice prefers to rasterio);
2. m25's remaining families arrive as `mdim.read` and `vector.read`
   cases: the GHRSST and BRAN `mdim.vrt` slabs, and web PR #21's five
   vector VRTs (its `vrt-oracle.json` becomes their answer set);
3. the source-name forms of m25 section 4.4 are dsn strings of cases,
   nested two levels as m25 asks;
4. `vrt-model`'s oracle test (core PR #29) reads through `oracle-case`
   instead of its own loader.

## 6. Order of migration

Sets move when they are next touched, not in one sweep. `zarr/` next
(the same windows as `cog/`), then `mdimrefs/` and `points/`. The warp
sets need one more op, `raster.warp` (target grid, method, the
gdalwarp or `gdal raster reproject` argv recorded with the answer), and
the harvest oracles of m23 an op of their own, `refs.chunks` (byte
offset and size per chunk through `GetRawBlockInfo`). Both are added
when a set needs them; the format version changes only if an existing
field changes meaning.

## 7. What do we get, what does it cost, what if we didn't

What do we get: one loader per language instead of one per test; GDAL
versions side by side, so version changes (3.13's kernel scale, 3.8's
missing `vrt://` keys) are recorded findings rather than regenerations;
a corpus other projects can use without wxylib's code (m25 section 5).
What does it cost: about 430 lines of Python and 600 of Rust, and a
second copy of answers per GDAL version (300 KB for `cog/` at 3.8.4).
What if we didn't: every consumer of the VRT corpus, and every binding,
writes its own reader of thirteen manifest shapes, and GDAL's version
history stays implicit in git.

## 8. Decisions (provisional, Michael to confirm)

1. **Name.** `oracle-case` for the format and crate (no "gdal" in the
   name; the oracle is any reference library).
2. **Home.** Format and recorder in wxylib/fixtures; crate in the core
   workspace, extracted on first outside use.
3. **Which GDAL versions answer.** HEAD (the `answers` workflow, as for
   the warp oracles), the version a set was made with, and 3.8.4 for
   the browser builds. A 3.12 conda-forge job can be added beside HEAD.
4. **The VRT corpus** adopts the format in its own PR (section 5),
   decided in the VRT thread.

## 9. Not claimed

- The 3.8.4 answers come from Ubuntu's GDAL build, not the gdal3.js
  wasm build; the two share a version, not necessarily drivers.
- Nothing here has been run on GDAL HEAD yet; the `answers` workflow
  does that on the fixtures PR.
- The diff of PR #13's corpus was made on a scratch copy; nothing was
  pushed to that branch.
