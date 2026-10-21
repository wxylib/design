# Commit criteria: when wxylib becomes the engine

Status: live checklist, updated as criteria move. Last updated 2026-10-21
(core 9b486a6; m06 section 6; m10).

wxylib is being pushed hard to see whether it deserves a long-term
commitment as the engine of a wider scheme: byte-reference tables over
archives that stay where they are, with every format (a GDAL mosaic VRT,
a flat Parquet table, kerchunk Parquet, Icechunk) a projection of one
table. The four criteria below are the test. This page is the one place
their status is kept; stages and musings link here rather than restating
it.

- If all four hold, wxylib is the engine for the whole scheme.
- If 2 or 4 fail, wxylib is still a strong reader of the tables, which is
  worth a lot on its own.

## The pipeline these criteria sit in

```
harvest     block-info scans, rhdf5 chunk walks, TIFF IFDs, DMR++  -> chunk rows per source
collate     arrays metadata, placements from the mosaic VRT, remap rules
middle      flat refs store ("parquet-zarr-lite")                     <- harvest into, render from
render      mdim VRT | kerchunk Parquet | Icechunk | Zarr virtual index | OGR layer
read        GDAL, R, Python, DuckDB, the browser, wxylib
```

The flat refs store is the middle stage, not one of the renders: tables
are harvested and collated into it, and every virtual index is rendered
from it. Today it is the mdim-refs Parquet export (`refs_<array>.parquet`
plus `arrays.json`), which `wxy-refs` reads directly. Two things about it
are open (see the
[spec's open questions](../specs/mdim-refs-0.2.md#open-questions)):

- its file layout is not fixed (one self-describing Parquet file with the
  metadata in key-value metadata is the likely end, replacing the sidecar
  JSON);
- the export does not yet carry the `sources` table (`source`, `size`,
  `mtime`, `etag`), which cache validation needs.

S3c is written to survive either layout: metadata from `arrays.json` now,
from the Parquet key-value metadata when that lands.

## The criteria

| # | Criterion | Status | What closes it |
|---|---|---|---|
| 1 | wxylib reads the table directly, with the cache inside, and BRAN is checked byte for byte against GDAL | **Met for BRAN; CI case open.** `wxy-refs` (S3c, core 9b486a6) reads the table without Icechunk, with `wxy-cache` keyed on the pre-remap source; OISST matches GDAL. BRAN2023 daily `temp` for 2010 (365 x 51 x 1500 x 3600, 1,116,900 references into NCI THREDDS) read from a flat export on keyed S3 (core PR #10, #11): both oracle windows identical to GDAL 3.14 reading the store's `mdim.vrt` (fixtures `scripts/oracle_bran2023_store.py`), 2026-10-21 | the synthetic Bluelink-shaped fixture (m06, section 2) in fixtures, so the many-chunks-per-file case is in CI |
| 2 | wxylib reads a table made by a producer it does not own | **Agreed, not shown.** m06 section 6: several producers, one contract; blocklist, the gdalraster `getRawBlockRefs()` branch and later GDAL7 each count once they reproduce the fixture tables. None has been checked yet. The BRAN fixture table already comes from an outside build (R, rhdf5 and GDAL multidim, via a kerchunk index), but its bytes are unverified, so it does not count yet | one producer's rows for `mdimrefs/` (synthetic, offline) and `mdimrefs/oisst-198109/` equal to the fixture rows on offset, size and presence; then wxylib reading that producer's table matching GDAL |
| 3 | An R user reads a table through wxylib without installing Rust, or wxylib's R surface is declared not the goal | **Not started.** Order set (m06 section 6): the flat store comes before R bindings that open sources, so R never vendors Icechunk | a CRAN feasibility check of the `wxy` package (vendored crate size, the rustc version CRAN builders carry, build time), then a decision |
| 4 | No new file format | **Holding, under pressure.** S7 reads the mosaic VRT subset and the table as its inputs. m10 (overlapping COG mosaics) needs per-axis chunk edges, the first real extension to mdim-refs | the extension agreed in the mdim-refs spec (proposed in its [open questions](../specs/mdim-refs-0.2.md#open-questions)) before any wxylib code writes it. If it lands only inside wxylib, this criterion fails |

## Rules that follow

- **Producers live outside wxylib.** wxylib owns the reader and the flat
  store (held to "own every line", m06 section 6); harvesting is someone
  else's code, and the fixture tables are the contract between them.
- **Spec first, code second.** Any column, table or grid shape a wxylib
  stage needs that mdim-refs/0.2 lacks goes to the spec as a proposal
  before it is written. The wxylib copy of the spec tracks the canonical
  one; it does not fork it.
- **Prove bytes, not structure.** A table that opens with the right shape
  is not a table that reads the same values as GDAL. Each criterion closes
  on an oracle comparison.
- **No sixth schema.** Extend columns; do not add tables that duplicate
  ones the spec already has.

## What we get, what it costs, what if we didn't

- Get: one honest answer to "is wxylib the engine or a reader", checked
  against things that can be run, instead of a judgement made from line
  counts.
- Cost: keeping this page current, and a little discipline (spec before
  code) that slows m10-style work by one review.
- Without it: wxylib keeps growing on its own momentum, the extension in
  m10 quietly becomes a wxylib format, and the commitment question is
  answered by default.
