# m36: a Hovmoller from the map planner

Plans a map slice and a Hovmoller (longitude by time at 42 S) of GHRSST
MUR 2024 with `rwarp::view::plan_view` (rwarp `62e11dd`, unchanged),
prices each plan from tile sizes before reading, then fetches the
per-axis plan and draws it. See [m36](../../docs/m36-visualizer-primitives.md).

| File | What |
|---|---|
| `plan/` | Rust: the planner cases; `cargo run --release > ../plans.jsonl` |
| `plans.jsonl` | One line per case and rule: levels, keys, distinct (level, lon chunk) pairs, rows |
| `cogtiles.py` | Minimal COG reader (standard library, numpy, zstandard): IFDs, tile sizes, ZSTD + predictor 2 decode |
| `harvest.py` | Tile sizes of every level of the 366 COGs from their headers; checks level 0 against the flat refs table |
| `hovmoller.py` | Prices each plan, fetches the per-axis 2024 plan and one map slice |
| `costs.jsonl`, `read.json` | Results (predicted and fetched bytes) |
| `figures.py` | `docs/img/m36-hovmoller.png`, `docs/img/m36-cost.png` |

Run (about a minute and 210 MB of range reads):

```sh
tar xzf ghrsst-mur-v2-20240101-20241231.tar.gz   # the store; flat/refs_analysed_sst.parquet
python harvest.py .../out/flat/refs_analysed_sst.parquet tiles-2024.json
python hovmoller.py tiles-2024.json out
python figures.py out ../../docs/img
```

Results (2026-11-25): level 0 sizes in the refs table equal the headers'
for all 366 days; per-axis plan predicted 205,547,537 bytes and fetched
205,547,537.
