# m23 measurements: harvesting HDF5 chunk refs in pure Rust

Supports [m23](../../docs/m23-byte-ref-harvesting.md). Run 2026-10-29
from a cloud container (about 1 s per request to NCI THREDDS).

## Contents

- `probe/`: a Cargo project with three harvesters, each printing
  `var,i:j:k,offset,size,filter_mask` per chunk.
  - `async_h5`: async-hdf5 0.1.0 `chunk_index()`, as shipped.
  - `pure_h5`: hdf5-pure 0.47.0 `Dataset::chunks()` through a small
    blocking HTTP `Source` (1 MiB blocks, no read-ahead).
  - `bfs_h5`: async-hdf5 for the metadata, then a level-parallel walk of
    the B-tree v1 chunk index (`bfs_h5 <url> <var> [in-flight]`).
- `compare.py`: per-file (offset, size) check against an mdim-refs
  fixture table, for many files.
- `bran_check.py`: chunk index, offset and size check for one BRAN file.
- `bran-bfs-log.txt`: the 32-in-flight BRAN run.

## Run

```
cd probe && cargo build --release && cd ..
export SSL_CERT_FILE=...   # only behind a TLS-intercepting proxy
FX=../../../fixtures/mdimrefs   # a wxylib/fixtures checkout
python3 compare.py probe/target/release/async_h5 $FX/oisst-198109/refs_sst.parquet sst
U=https://thredds.nci.org.au/thredds/fileServer/gb6/BRAN/BRAN2023/daily/ocean_temp_2010_01.nc
probe/target/release/bfs_h5 $U temp 32 > bran.csv
python3 bran_check.py $FX/bran2023-temp-201001/refs_temp.parquet $U bran.csv
```

## Results

| Harvester | OISST 1981-09 (30 files x 4 vars) | BRAN 2010-01 temp (94,860 chunks) |
|---|---|---|
| async_h5 | 120 of 120 | 94,860 of 94,860; 690 s (sequential walk, 8 MiB blocks) |
| pure_h5 | 120 of 120 | stopped after 10 minutes (sequential, 1 MiB blocks) |
| bfs_h5 | 60 of 60 (sst, ice), 3 of 3 (err) | 94,860 of 94,860; 12.8 s at 128 in flight, 21.8 s at 32, 60.4 s at 8, over 400 s at 1 |

The oracle for OISST is GDAL `GetRawBlockInfo` (libhdf5); for BRAN it is
the VirtualiZarr store behind the fixture (h5py, libhdf5).
