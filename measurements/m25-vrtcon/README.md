# m25 measurement: vector vrt:// lowered to OGR VRT

`vrtcon.py` parses a vector `vrt://` string whose keys are ogr2ogr flags
(`layer`, `select`, `where`, `sql`, `spat`, `a_srs`, `t_srs`, `x`/`y`,
`name`) and lowers it to the `OGRVRTDataSource` XML GDAL already reads. It
needs no GDAL. `check.py` is the GDAL oracle: it reads each lowered
document with GDAL (through pyogrio) and, where GDAL has a direct
equivalent (`columns`, `where`, `bbox`, `sql`), compares the two reads
feature by feature.

    pip install pyogrio
    python check.py DATA_DIR > results.txt

DATA_DIR holds `ne_110m_admin_0_countries.geojson` (Natural Earth
v5.1.2, from the nvkelso/natural-earth-vector repository) and
`stations.csv` (wxylib/web `www/data/vrt`).

Result (GDAL 3.12.4, pyogrio 0.13.0): 5 of 5 cases pass; the three with a
direct equivalent are identical in geometry and fields
([results.txt](results.txt)).
