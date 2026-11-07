# m30 pilot: one rasterwise release bundle scanned with osgeo.gdal

`pilot.py` hashes every member of an extracted rasterwise release bundle,
matches it to the rasterwise `manifest.csv` by sha256, and records the
classic and multidimensional opens. `pilot-v0.0.12-gdal-3.8.4.jsonl` is
the result for the v0.0.12 `weird.tar.gz` (36 members) on GDAL 3.8.4.

```sh
curl -LO https://github.com/rgdal-dev/rasterwise/releases/download/v0.0.12/weird.tar.gz
mkdir b12 && tar -xzf weird.tar.gz -C b12
python3 -I pilot.py b12 path/to/rasterwise/manifest.csv > pilot.jsonl
```

Result: 36 of 36 members in the manifest; of 29 data files, 28 open in
the classic API (the WOD profile is refused) and 28 in the multidim API
(the GeoTIFF is refused).
