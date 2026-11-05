# m29 measurement: how far VRT placements lower toward byte refs

`tiers.py` reads a VRT's XML (no source is opened) and puts every
placement in one of four tiers (m29 section 4): T0 regular refs, T1 refs
with chunk edges, T2 needs a cut (overlap), T3 needs computing (fractional
offset, resampling or a value operation). It also writes the placements
as Parquet in memory and times a one-window lookup. Python 3 standard
library, plus pyarrow for the table timing and the COP30 input.
`figures.py` writes the three m29 figures from `results.jsonl`.

    python3 tiers.py classic USGS_Seamless_DEM_1.vrt
    SNAP_PX=0.15 python3 tiers.py classic USGS_Seamless_DEM_1.vrt
    python3 tiers.py mdim ghrsst-mur-v2.vrt
    python3 tiers.py cop30 ../cop30/cop30_sources.parquet
    for f in fixtures/vrt/c0*.vrt; do python3 tiers.py classic $f; done
    python3 figures.py results.jsonl ../../docs/img

`SNAP_PX` is the tolerance under which an offset counts as integer
(default 1e-3 px).

Inputs, read on 2026-11-05:

| File | Bytes | SHA-256 |
|---|---|---|
| https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/USGS_Seamless_DEM_1.vrt | 2153591 | `f046c156a88b523f7544fd1199da4f2f5c0f8a7e979306519c0bf795773f2cc2` |
| https://data.source.coop/ausantarctic/ghrsst-mur-v2/ghrsst-mur-v2.vrt | 16630393 | `6fe8781ba1a42028818b50f0a3cf116adaf49fa661e8ada83ea8d2b6a72bd79f` |
| `../cop30/cop30_sources.parquet` (m10, read from COP30_hh.vrt on 2026-10-19) | | see [../cop30/README.md](../cop30/README.md) |
| wxylib/fixtures `vrt/c01` to `c09` (fixtures `aed9d1e`) | | |

Results ([results.jsonl](results.jsonl), one JSON object per run):

| VRT | Placements | T0 | T1 | T2 | T3 |
|---|---|---|---|---|---|
| GHRSST `mdim.vrt` | 38,360 | 38,360 | 0 | 0 | 0 |
| COP30 | 26,475 | 0 | 52 | 11,834 | 14,589 |
| 3DEP as written | 3,817 | 0 | 0 | 0 | 3,817 |
| 3DEP, SNAP_PX=0.15 | 3,817 | 0 | 2 | 3,815 | 0 |
| corpus c01 to c09 | 14 | 6 | 1 | 2 | 5 |

The nested corpus case (c09) counts as T1 because the classifier does not
recurse into the child VRT.
