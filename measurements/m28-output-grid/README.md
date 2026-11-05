# m28 measurements: what each tool infers for a warp's target grid

Three scripts over the same five source grids and six target CRSs
(`cases.py`), for [m28](../../docs/m28-warp-output-grid.md):

- `gdal_matrix.py` (osgeo.gdal): gdalwarp's grid with only the target CRS
  given (GDALSuggestedWarpOutput2 plus gdalwarp's rounding), and the
  option matrix (`-tr`, `-ts`, `-te`, `-tap`, `-te_srs` and their
  combinations) on two pairs. Each case warps to a VRT, so no pixels move.
  Output: `gdal_matrix.json`, recorded with GDAL 3.8.4.
- `odc_cases.py` (odc-geo 0.5.4): `compute_output_geobox` with its
  defaults (resolution "auto", pixel edges snapped to 0, 0). Output:
  `odc_cases.json`.
- `suggest_rule.py` (osgeo.gdal, numpy): a prototype of the rule m28
  section 5 recommends, with GDAL's exact transformer moving the points.
  Output: `suggest_rule.json`.

`scripts/m28_figures.py` draws `docs/img/m28-rules.png` and
`docs/img/m28-extents.png` from the three JSON files.

The sources are empty in-memory rasters: only the grid and CRS matter.

| name | CRS | grid |
|---|---|---|
| world-0.5 | EPSG:4326 | 720 x 360, -180 to 180 |
| world-0.25-0to360 | longlat, `+lon_wrap=180` | 1440 x 720, 0 to 360 (BRAN, GHRSST L4 style) |
| antarctic-25km | EPSG:3031 | 480 x 480 at 25 km, pole at the centre |
| utm55s-10m | EPSG:32755 | 10980 x 10980 at 10 m (a Sentinel-2 tile over Tasmania) |
| pacific-150to210 | EPSG:4326 | 240 x 120, 150E to 150W, 60S to 30S |

One gdalwarp case is not run: world-0.5 to EPSG:3031 with `-tr 25000`
and no `-te` would ask for about 1e39 cells, and GDAL 3.8.4 aborts the
whole Python process (`std::length_error`) rather than raising. The
script records that instead of calling it.
