# m31 measurements: chunk planning for a view

`view_plan.py` (numpy, pyproj 3.8.0; no I/O) plans the chunks a
1024 x 1024 view needs from a source described by metadata only: a global
lon/lat grid of 36000 x 18000 cells at 0.01 degree (the GHRSST MUR shape),
512 x 512 int16 chunks, with levels halving to level 6 ("pyramid") or full
resolution only ("full_resolution_only", the case of a virtual store over
netCDF files with no overviews).

Two planners:

- `single`: one bounding box of 64 x 64 sampled view points and one level
  from the mean source cell per screen pixel, times 0.7 (the rule in the
  existing mesh viewers' `planFetch`).
- `region`: 64 x 64 pixel screen tiles, each with a level from the lowest
  quartile of the local scale (square root of the Jacobian determinant,
  screen pixel to source cell) over 9 x 9 samples, a footprint unwrapped
  about the tile's centre longitude, chunks de-duplicated.

`under` and `over` are the shares of visible screen pixels (sampled every
4 px) served by a level at least two steps coarser or finer than the
local need. Orthographic views drop points past the horizon by a round
trip check. Results: [results.json](results.json).
