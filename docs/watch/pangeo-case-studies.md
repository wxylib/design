# Watch: ganymede case studies (GOES-16 LST, NWM, Sentinel-2)

Status: watch note, 2026-11-12. Covers the three case-study notebooks in
[eugo-inc/ganymede](https://github.com/eugo-inc/ganymede) at `f48902b`
(BSD-3-Clause), announced on the Pangeo Discourse on 2026-11-12 ("Three
worked notebooks on public NOAA and Sentinel-2 data"). The post asks for
expert feedback on quality-flag cuts, clear-sky thresholds, Sentinel-2
Collection 1 offsets and bilinear resampling of 20 m bands.
Context: [m17](../m17-self-describing-stores.md) (store contract),
[m21](../m21-conservative-examples.md) (conservative weights),
[m23](../m23-byte-ref-harvesting.md) (harvesting),
[m27](../m27-oracle-harness.md) (oracle harness),
[m31](../m31-view-chunk-planner.md) (view-to-chunk planner),
[crs-coverage.md](crs-coverage.md).
Scripts: [scripts/pangeo_case_studies](../../scripts/pangeo_case_studies).

## 1. Summary

The notebooks are plain, careful Python (xarray, s3fs, pyproj,
pystac-client, rasterio) with Ray only as the fan-out. Each one does a
per-file step on one file, then the same step over many files. None uses
byte references, and every step is one that wxylib already has a piece
for. Four things came out of reading them against the files themselves:

1. **Sentinel-2: the overview GDAL picks is not the one that gives the
   right answer.** For the notebook's 10 m to 60 m area average, the 40 m
   overview (the coarsest level finer than the target, which is what
   gdalwarp's `-ovr AUTO` rule and `wxy_warp::choose_overview` pick) does
   not nest into 60 m and gives a mean NDVI error of 0.0056 against the
   exact 6 x 6 block mean. The notebook's own GDAL "average on read" gets
   0.0058. The 20 m overview nests (factor 3, aligned) and gives 0.00005
   for the same bytes, because each level costs one tile here
   (section 3.3). This is a small, testable rule for the planner: for
   average and conservative kernels, prefer the coarsest level whose
   grid nests into the target.
2. **GOES-16 LST: the four regions touch 5 of 60 chunks.** Each hourly
   file is downloaded whole (3.15 MB) to read about 3,800 pixels. LST and
   DQF in those 5 chunks are 413 KB, 7.6 times less, and the 72-file Ray
   run would read 30 MB instead of 227 MB (section 3.1). A byte-ref store
   over the hourly series (one fixed grid, time as the outer axis) is the
   m02/m13 pattern on a geostationary grid.
3. **NWM: byte refs gain only what the producer's chunks allow.** The five
   gauges fall in all 3 streamflow chunks (925,578 reaches each), so a
   refs read is 1.7 MB of a 12.6 MB file. A gauge time series over 240
   forecast hours still means 240 reads of half a megabyte each. That is a
   held-bytes (rechunk) problem, which bytes-in-place does not solve, and
   the retrospective Zarr already is the rechunked answer (section 3.2).
4. **Two contract checks for m17.** Sentinel-2 C1 COGs carry `SCALE`
   0.0001 and `OFFSET` -0.1 in their GDAL metadata, matching STAC
   `raster:bands`, so the files are self-describing and the notebook's
   `earthsearch:boa_offset_applied` switch is a catalogue-level fact a
   store description must carry. NWM stores `scale_factor` as float32
   0.01, so decoded values carry float32 noise (743661 decodes to
   7436.6098337788135, as printed in the notebook, not 7436.61).

Recommended: item 1 as a short core change plus an oracle case, then one
docs example built on the GOES file (byte-ref store, coverage-weighted
zonal on the fixed grid, warp with off-disk pixels). Nothing here needs a
new crate.

## 2. The three notebooks

| Notebook | Data | Format and layout | Per-file step | Reads |
|---|---|---|---|---|
| `goes16_netcdf` | `s3://noaa-goes16/ABI-L2-LSTC`, hourly CONUS, 13 to 15 July 2023 | NetCDF-4, LST/DQF/PQI uint16 1500 x 2500, chunks 250 x 250, gzip 1 + shuffle; `goes_imager_projection` (geos, sweep x, lon_0 -75); x/y int16 scan angles | download whole file to memory, DQF <= 1, mean LST over pixels whose centre is in each of four lon/lat boxes, 20% clear rule | 72 files, 227 MB |
| `national_water_model` | `s3://noaa-nwm-pds` medium-range mem1, 240 hourly files; reach coordinates from the NWM retrospective v3.0 Zarr | NetCDF-4, 1-D over 2,776,734 reaches, chunks 925,578, gzip 2 + shuffle, int32 with float32 scale 0.01 | download whole file, select five gauge reaches by `feature_id` | 50 files, about 0.6 GB |
| `sentinel2_resampling` | Earth Search `sentinel-2-c1-l2a`, tile 15TVG, 37 scenes, 2024 season | COG, deflate + predictor 2, 1024 tiles at 10 m and 512 at 20 m, overviews x2 to x16 built with AVERAGE (MODE for SCL) | windowed read of a 6 km box, 10 to 60 m by nearest, block mean and GDAL average on read; 20 to 10 m nearest and bilinear; cloud-masked NDVI at 20 m | a few tiles per band per scene |

The Sentinel-2 notebook snaps the window to 60 m so the 10, 20 and 60 m
grids line up inside it, resamples reflectance before forming NDVI, and
keeps SCL on nearest. All three choices are sound and are the ones wxylib
would make.

## 3. Measurements

All from the public files, no credentials; scripts and URLs are in
[scripts/pangeo_case_studies](../../scripts/pangeo_case_studies).

### 3.1 GOES-16 LST chunks

One file (`s20231962001177`, 20 UTC on 15 July 2023): 60 chunks per
variable. The notebook's region selection (pixel centre in the lon/lat
box, computed with pyproj from the CF grid mapping) reproduces its pixel
counts exactly (1278, 615, 651, 1249).

| Region | Pixels | Chunks |
|---|---|---|
| Sonoran Desert | 1278 | 2 |
| Central Valley | 615 | 1 |
| Cascade Range | 651 | 2 |
| Corn Belt | 1249 | 1 |
| All four | 3793 | 5 of 60 |

LST + DQF bytes in those 5 chunks: 413,176 of a 3,151,232-byte file. The
corner of the CONUS sector has 47,162 pixels that miss the Earth (the
notebook's reason for not regridding).

### 3.2 NWM streamflow chunks

One file (`f024` of the 2026-11-09 00 UTC run): the five gauge reaches
sit at indices 168,292 to 2,709,914, in chunks 0, 1 and 2 of 3 (610, 521
and 570 KB compressed). `feature_id` is sorted and the same in every
file, so the index lookup is done once per run.

### 3.3 Sentinel-2 overview nesting

Scene `S2A_T15TVG_20240818T171118_L2A`, red (B04) and NIR (B08), the
notebook's window (432540, 4661520, 438540, 4667520) in EPSG:32615. The
tile origin is 399960, 4700040, so the window starts at 3258 pixels at
10 m, 1629 at 20 m and 814.5 at 40 m: the 40 m grid is offset by half a
pixel and its cells are 1.5 times smaller than the target's.

| 60 m NDVI from | Mean abs error vs exact | Max abs error | Compressed bytes (B04 + B08) |
|---|---|---|---|
| level 0, exact 6 x 6 block mean | 0 (reference) | 0 | 2,471,111 |
| level 0, nearest (centre pixel) | 0.02189 | 0.380 | 2,471,111 |
| 40 m overview, exact area weights | 0.00561 | 0.119 | 731,050 |
| 20 m overview, 3 x 3 block mean | 0.00005 | 0.0002 | 708,809 |
| notebook: GDAL average on read (40 m) | 0.0058 | - | - |

The nearest row matches the notebook's 0.0219 to four places, which
checks the reproduction. Even exact area weights on the 40 m level cannot
recover the 10 m block mean, because its cells mix pixels from either
side of each 60 m edge. The 20 m level differs from exact only by the
integer rounding GDAL applied when it built the overview.

## 4. Where wxylib fits, step by step

| Step | Notebook does | wxylib piece | Gain or check |
|---|---|---|---|
| list and read hourly NetCDF-4 | whole-file download per hour | refharvest + async-hdf5 to a refs table; one mdim store over the series (time outer axis) | 7.6x fewer bytes for GOES regions; one store instead of a glob |
| geos fixed grid to lon/lat | pyproj from CF attributes | domain from the CF grid mapping; geos is exact in both CRS backends ([crs-coverage.md](crs-coverage.md) rows `geos-goes`, `geos-himawari`) | oracle: GDAL's geotransform for radian x/y vs ours |
| region means | centre-in-box mask, unweighted mean | `wxy zonal --coverage`: box edges densified (bigcurve) into fixed-grid index space, exact weights from controlledburn | measures how far centre-in-box is from area-weighted on a grid whose pixel area varies |
| map without regridding | plots native grid | `wxy warp` to an Albers grid, off-disk pixels as failed transforms; DQF by mode, LST by average | oracle case: gdalwarp vs rwarp on a geos source with off-Earth corners |
| NWM gauge lookup | 13 MB download for 5 values | refs table over 1-D arrays (not a grid) | 7.4x, capped by 925,578-reach chunks |
| S2 window read | rasterio window + out_shape | COG reader with the view planner (m31) | none, already efficient |
| S2 10 to 60 m | nearest, numpy block mean, GDAL average | rwarp average and conservative weights (m21) | nested-overview rule (section 3.3) |
| S2 20 to 10 m | nearest, bilinear | rwarp kernels | oracle: RasterIO bilinear vs warp bilinear at window edges |
| SCL | nearest, mode when coarsening | rwarp mode; the file's own overviews are MODE | none |
| scale, offset | from STAC `raster:bands` | m17 contract, file metadata | both agree for C1 |

## 5. Candidates

Ranked by value for cost.

1. **Nested-overview rule** (core, small). In `choose_overview`, for
   average, mode and conservative kernels, prefer the coarsest level
   whose cell size divides the target's and whose origin is aligned;
   fall back to the gdalwarp rule otherwise. Keep `-ovr AUTO`
   behaviour as the default for GDAL parity and add this as an option
   first. Oracle case for fixtures: the section 3.3 window, answers from
   osgeo.gdal (`gdal.Translate(-projwin, -tr 60 60, -r average)` with
   default and with `-ovr` forced to the 20 m level).
2. **GOES LST docs example** (docs, medium). One page: refs table over a
   day of hourly files, regional means with coverage weights against the
   notebook's centre-in-box numbers, and a warp to Albers. It shows three
   pieces (refs, controlledburn on a projected non-lon/lat grid, rwarp
   with failed transforms) on data people know, and credits the notebook.
3. **geos oracle case** (fixtures, small). One LSTC file by URL: GDAL's
   reported geotransform and CRS for radian x/y, and a gdalwarp output to
   EPSG:5070 with off-Earth corners. Public domain data, 3 MB, so a
   cropped copy can live in fixtures if a URL case is not enough.
4. **NWM as a 1-D refs test** (fixtures, small, later). The refs table
   and readers are tested on grids; a 1-D feature array with a sorted
   index exercises the same code without a CRS. The float32 scale goes
   into the m17 contract checks.

Not taken: Ray fan-out, STAC search and plotting are outside wxylib.
Rechunking NWM for gauge time series is held bytes and belongs to the
retrospective Zarr's producers.

## 6. Notes for a reply on the post

If a reply is wanted, two points are ours to make, with numbers: the
nested-overview result (a 20 m read for a 60 m average is about 100 times
closer to the exact mean than GDAL's default 40 m choice, at the same
cost here), and the chunk counts for GOES and NWM, which show what a
byte-reference index would save over whole-file reads. The quality-flag
and clear-sky questions are domain calls we have no measurement for.
