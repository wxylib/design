# m21 measurements: weights for two planned examples

`cargo run --release > log.txt` builds rwarp's conservative weights
(`rwarp::weights::exact_weights`, rwarp at 87f9b42, the pure-Rust
`proj4rs` backend) for two windows the size of the planned examples in
[m21](../../docs/m21-conservative-examples.md), prints entry counts,
timings and the source-side conservation check, and writes the entries
and outline of one target cell (`cell.txt`, `outline.txt`) for
`scripts/m21_figures.py`.

- A: a 0.01 degree source (GHRSST MUR's grid) onto 0.25 degrees, 140E to
  160E and 48S to 38S.
- B: a 0.1 degree source (BRAN2023's grid) onto EPSG:3031 at 25 km over
  Prydz Bay, densify 1 and 4.

`log.txt` is the run recorded for m21.
