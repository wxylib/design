# m17 contract check output

Produced by [scripts/m17_contract.py](../../scripts/m17_contract.py)
(design m17) on 2026-10-24, run from `wxylib/fixtures/mdimrefs`:

```
python scripts/m17_contract.py arrays.json oisst-198109/arrays.json \
  bran2023-temp-201001/arrays.json \
  https://raw.githubusercontent.com/mdsumner/virtualized/1e9c46f/remote/ocean_temp_2023.parq \
  https://raw.githubusercontent.com/mdsumner/virtualized/1e9c46f/zarr/ocean_temp.zarr
python scripts/m17_contract.py oisst-198109/arrays.json \
  --oracle nc/198109/oisst-avhrr-v02r01.19810901.nc
```

- `report.txt`: per store and array, the state of each contract item,
  then the packing and fill differences between stores. Exit status 1
  (conflicts found).
- `oracle-oisst.txt`: fill, scale, offset and units against osgeo.gdal
  (GDAL 3.13.3, conda-forge) on one OISST source file. All agree.
