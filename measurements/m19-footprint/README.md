# m19 measurements: the exact footprint

Bench crate and logs behind [m19](../../docs/m19-exact-footprint.md).

## Files

- `bench/`: a Rust crate pinned to hypertidy/rwarp 4ae1446 and
  hypertidy/controlledburn-rs c66deb2 (git dependencies; rwarp with the
  pure-Rust `proj4rs` backend, so no libproj is needed).
  - `src/lib.rs`: the prototypes. `cb_per_pixel` is a replica of rwarp
    0.2's `area_row_exact` with the time split into transform, burn and
    reduce; `accum_*` is the coverage window (section 5.2); `Lattice` is the
    shared lattice transform (5.1); `Prefix` and `green_*` are the boundary
    integral over row prefix sums (5.3).
  - `examples/sweep.rs`: the ratio sweep (affine) and the EPSG:3031 sweep.
    Prints a table on stdout and CSV on stderr.
  - `examples/densify.rs`: error against densify 64, and the box.
  - `examples/tiles.rs`: per-pixel cost against tile size.
  - `examples/holes.rs`: the boundary integral against rwarp's exact
    footprint on a source with nodata.
  - `examples/wall.rs`: window coverage against brute-force clipping, for
    outlines with edges on cell walls.
  - `examples/fig1.rs`: data for the footprint figure (`fig1.json`).
  - `patched/oldnew.rs`: rwarp 0.2 against the patched rwarp. Needs both
    patches from m19 section 6 applied, the patched controlledburn-rs as a
    `[patch.crates-io]` path, and the unpatched rwarp under another name
    (`rwarp_orig = { package = "rwarp", path = ... }`, with its version
    changed so the lockfile can hold both).
- `sweep1.csv` to `sweep3.csv` (and `.txt`): three runs of `sweep all`.
  CSV columns: label, densify, box, rwarp 0.2 exact, then totals for the
  burn replica, window per pixel, window with lattice, integral with
  lattice, then transform / coverage / reduce for the burn replica, the
  window with lattice and the integral with lattice, then covered cells
  per pixel. Microseconds per destination pixel.
- `densify.txt`, `oldnew.txt`, `fig1.json`: the other runs.

## Running

```sh
cd bench
cargo run --release --example sweep -- all > sweep.txt 2> sweep.csv
cargo run --release --example densify > densify.txt
cargo run --release --example fig1 > fig1.json
python3 ../../../scripts/m19_figures.py   # reads this folder
```

Single-threaded; one cloud container (x86_64), 2026-10-28. Expect
+-20% between runs; the figures use the median of three.
