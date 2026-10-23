# m16 measurements: a versioned byte-ref table

Scripts and logs behind [m16](../../docs/m16-versioned-byte-ref-table.md).
Input: the GHRSST MUR analysed_sst 2024 store built by raad.virtualize
(mdim-refs/0.2 `store.sqlite`, its flat export and `manifest.json` with the
GDAL 3.13.3 window hashes), 366 COGs, 935,496 chunk rows.

Environment (2026-10-23): conda-forge Python 3.12, GDAL 3.12.4 (osgeo.gdal),
pyarrow 25, duckdb, pip pylance 13.0.0, datafusion 54.1.0 (Lance 13's
DataFusion table provider refuses 55), icechunk 2.3.0, obstore 0.12.0,
zarr, numcodecs, sedonadb 0.5.0.

| Script | Does | Log |
|---|---|---|
| `lance_load.py STORE.sqlite OUT` | mdim-refs tables into Lance datasets with the same columns; bulk half-year, 184 daily commits, one rescan upsert; tags | `load-log.json` |
| `lance_query.py OUT FLAT` | time travel at tags; Lance delta vs EXCEPT; the remap view in DuckDB and DataFusion, row hash against the flat export; a box query; compaction and cleanup on a copy | `query-log.json` |
| `lance_bytes.py OUT STORE` | each oracle window read through the Lance refs (remap target `s3direct`), decoded, hashed; compared with the manifest and with osgeo.gdal on the plan VRT remapped by `gdal-s3direct` | `bytes-rescan.json` |
| `frag_store.py STORE.sqlite OUT LANCE` | the same history as Parquet fragments plus a manifest written with object_store `PutMode::Create` (obstore `mode="create"`); view in DataFusion; two-writer race | `frag-log.json` |
| `icechunk_replay.py FLAT OUT --split N` | the same history as an Icechunk repo with manifests split every N days (write side only) | `icechunk-split{1,30,365}-log.json` |
| `m16_figure.py DIR OUT.png` | the history-size figure | `../../docs/img/m16-history-size.png` |

Remote reads need `SSL_CERT_FILE` / `CURL_CA_BUNDLE` set in a proxied
environment. `data.source.coop` was not reachable from the test machine;
the `s3direct` remap rows (already in the store) were, which is itself a
use of remap as a view.
