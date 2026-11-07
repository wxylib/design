# VRTMate checks

Scripts behind [docs/watch/vrtmate.md](../../docs/watch/vrtmate.md).
Python standard library only.

```sh
curl -sSO https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/USGS_Seamless_DEM_13.vrt
python3 probe.py USGS_Seamless_DEM_13.vrt
python3 bbox.py USGS_Seamless_DEM_13.vrt
python3 ../../measurements/m29-vrt-rework/tiers.py classic USGS_Seamless_DEM_13.vrt
SNAP_PX=0.15 python3 ../../measurements/m29-vrt-rework/tiers.py classic USGS_Seamless_DEM_13.vrt
```

`bbox.py` uses a fixed seed (1), so its counts repeat for the same VRT.
The VRT is republished as tiles are added (1,430 sources when VRTMate's
page was written, 1,449 on 2026-11-07), so counts drift with it.
