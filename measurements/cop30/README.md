# COP30 source table (OpenTopography)

The source table behind m10 section 5 and m11 section 4a: one row per
child COG of OpenTopography's `COP30_hh.vrt`, read from the VRT's own
XML with no COG requests.

| File | What |
|---|---|
| `cop30_summary.R` | downloads the VRT, writes `cop30_sources.parquet`, prints the census; an optional block (off by default) reads about a dozen COG headers for codec and registration |
| `cop30_sources.parquet` | 26,475 rows: `filename`, `src_w`, `src_h`, `dst_xoff`, `dst_yoff`, `dst_w`, `dst_h`, `ratio_x`, `lon`, `lat` (the paste's top-left corner in degrees) |
| `cop30_bands.py` | band counts per hemisphere and seam-chunk pixel fractions from the parquet (pyarrow only) |

Inputs as read on 2026-10-19:

| | SHA-256 |
|---|---|
| `COP30_hh.vrt` (11,726,674 bytes, not kept here) | `8b0a0a51dd1e174d70438601dd1fd29cf686b2f22759d5a709128655672b794a` |
| `cop30_sources.parquet` | `5a618769a20859db274b9e25f579944aeb13d3345ac6a3a197ab388f8b56f2d9` |

Regenerate:

```sh
Rscript cop30_summary.R          # needs curl, xml2, arrow
python3 cop30_bands.py cop30_sources.parquet
```

The VRT is upstream's and can change; a different hash means the table
should be rebuilt and the numbers in m10 and m11 checked.
