# Byte-level checks on the ganymede case studies

Scripts behind [docs/watch/pangeo-case-studies.md](../../docs/watch/pangeo-case-studies.md).
They look at storage layout (HDF5 chunk tables, COG tile tables), which
GDAL does not report directly, so they use h5py and tifffile for headers
and plain HTTP range reads for bytes. The oracle versions of these cases,
when written, use osgeo.gdal (`gdal.Translate` with `-projwin`, `-tr` and
`-r average`, and `gdal.Warp`).

| Script | Input | Question |
|---|---|---|
| `goes_lst_chunks.py` | one `noaa-goes16` ABI-L2-LSTC file (3.2 MB) | which 250 x 250 chunks the four regions touch |
| `nwm_chunks.py` | one `noaa-nwm-pds` medium-range channel file (12.6 MB) | which streamflow chunks the five gauges sit in |
| `s2_overview_nesting.py` | Sentinel-2 C1 L2A item prefix (B04, B08) | 10 m to 60 m from level 0, the 20 m overview and the 40 m overview |

Files for the first two:

    https://noaa-goes16.s3.amazonaws.com/ABI-L2-LSTC/2023/196/20/OR_ABI-L2-LSTC-M6_G16_s20231962001177_e20231962003549_c20231962004571.nc
    https://noaa-nwm-pds.s3.amazonaws.com/nwm.20261109/medium_range_mem1/nwm.t00z.medium_range.channel_rt_1.f024.conus.nc

The NWM operational bucket is a rolling archive, so the second URL will
go away; any medium-range channel file has the same layout.
