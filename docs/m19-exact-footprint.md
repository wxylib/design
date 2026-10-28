# m19: The exact footprint, what controlledburn does in rwarp and what it costs

Status: musing, measured, 2026-10-28. Explains rwarp 0.2's
`Footprint::Exact` (hypertidy/rwarp at 4ae1446), measures where its time
goes, and tests four ways to make it cheaper. Two of them come with
patches for hypertidy/controlledburn-rs and hypertidy/rwarp. Bench code
and logs: [measurements/m19-footprint](../measurements/m19-footprint/README.md).
Figures: `scripts/m19_figures.py`.

## Summary

The question in one line: rwarp's exact footprint for `average` and
`mode` burns each destination pixel's outline with controlledburn and costs
about 25x GDAL's box. What is it computing, where does the time go, and
how much of the cost is necessary?

- **What it computes.** Each destination pixel's outline (its four edges,
  each split into `densify` segments) is transformed into source pixel
  space and intersected exactly with the source pixels. The average is
  then the area-weighted mean over valid pixels: first-order conservative
  remapping, with areas measured in source pixel space. GDAL's box takes
  two transformed corners and the axis-aligned box between them, which is
  exact only when the pixel maps to an axis-aligned rectangle.
- **The box is far less accurate than densify matters.** On an
  EPSG:4326 to EPSG:3031 warp, the box differs from the exact footprint by
  0.09 to 0.26 field units on average; the chord error of densify 1 is
  20 to 2600 times smaller and falls as 1/d^2. Densify matters only for
  coarse destination pixels (100 km: 0.012 at d = 1).
- **Where the time goes.** Two things, neither of them geometry. In the
  burn, per-call setup and per-boundary-cell records (a hash map entry, a
  vector of traversals, row vectors, a sort): allocation alone is about 40%
  of its instructions. Under a projection, the transform: every pixel
  transforms its own four corners and densified edges, so each corner is
  transformed four times and each edge point twice. And because the rings
  of a row go to the transformer as one array that is not a scanline, an
  `ApproxTransformer` silently falls back to exact transforms for the exact
  footprint while it interpolates for the box.
- **The cost is not necessary.** Measured, all exact to controlledburn's
  `f32` fractions:
  - a shared lattice (each corner and edge point transformed once, row
    lines and densify levels as scanlines) removes 75% of the transform
    work, and lets the approximate transformer apply;
  - a dense coverage window (the signed-area cell accumulation of
    FreeType's rasteriser) replaces the burn at 0.2 to 0.5 microseconds a
    pixel, against 1 to 2.5 for the burn at low ratios;
  - a boundary integral over row prefix sums gives the weighted sum from
    the outline alone, so cost follows the perimeter, and each edge of the
    destination lattice is integrated once and shared by its two pixels.
  At ratios up to 4:1 the integral costs 1.3 to 2.3x the box and the window
  2 to 5x, against 13 to 20x for rwarp 0.2. From about 16:1 both are faster
  than the box.
- **Patches.** controlledburn-rs gains `CoverageWindow` and `RowPrefix`
  (version 0.2.2, property-tested against `burn`). rwarp's exact footprint
  uses the lattice and the window: unchanged output under exact
  transforms, 2.4 to 6x faster, and up to 8x with the approximate
  transformer. Both are in `/mnt/project-files/exact-footprint/` for
  review; nothing is pushed to hypertidy.

## 1. The call path

`warp()` with `ResampleAlg::Average` or `Mode` (and min, max, median,
quartiles, RMS) goes to `warp_area`, which picks a reducer (running
weighted mean, mode histogram, and so on) and calls `warp_area_with`. That
loops over destination rows and, for `Footprint::Exact { densify }`, calls
`area_row_exact` for each:

1. Build every pixel's outline in destination pixel coordinates: top edge
   left to right, right edge down, bottom right to left, left edge up,
   each edge as `densify` points, so `4 densify` points per pixel. All
   pixels of the row go into one pair of coordinate arrays.
2. Transform the arrays in one call (destination to source).
3. For each pixel: skip it if any point failed; subtract the source
   buffer offset and flip y (controlledburn's grids have y up); take the
   outline's bounding box clipped to the buffer; build a `GridSpec` for
   just those source pixels; call `controlledburn::burn` with one polygon
   in coverage mode.
4. Feed the reducer: every cell of each interior run with weight 1, every
   boundary cell with its `f32` fraction; write the result.

## 2. What controlledburn computes per pixel

controlledburn's coverage mode is the exactextract algorithm. For one ring
on a padded subgrid:

- **Walk.** Follow the ring through the grid cell by cell, splitting it
  where it crosses a cell wall, and record each pass through a cell (a
  traversal: entry side, coordinates, exit side) in a per-cell record,
  found through a hash map.
- **Fractions.** A boundary cell crossed once gets its covered fraction
  analytically (the traversal plus the cell corners on the arc from exit
  to entry, as one small polygon); a cell crossed more than once chains its
  traversals around the cell perimeter.
- **Winding.** Each traversal that crosses its row's centre line adds a
  winding delta. A sweep along each row then emits interior runs between
  boundary cells where the winding is non-zero, and boundary cells as edges
  with their fractions.

This is the right machinery for a large polygon on a large grid: the
output is sparse, interior cells cost nothing, and holes, multipolygons and
odd geometry are handled. For a destination pixel outline covering a few to
a few hundred source pixels, the machinery is the cost. Callgrind on
4096 pixels at 1:1 and 8:1 (rotated affine, densify 1) puts about 40% of
the burn's instructions in `malloc` and `free` (a `Vec` per cell record, per
row, per merged row, per analytic fraction; the hash map's growth), and
the rest in the walk, the per-cell fraction and the sweep.

## 3. Densify, and the box

![(a) A 300 km EPSG:3031 pixel in the pixel space of a 0.5 degree
longitude-latitude source: exact coverage, the densified outline, the chord
quadrilateral of densify 1, and GDAL's box; (b) the shared edges and prefix
sums of section 6](img/m19-footprint.png)

A straight destination pixel edge is a curve in source pixel space unless
the transform is affine. Densify replaces the curve by `densify` chords.
The area between a curve and its chord shrinks as the square of the
chord's length, so the error falls as 1/d^2:

![Mean absolute difference from densify 64, for three destination pixel
sizes, with GDAL's box for the same pixels as dotted lines](img/m19-densify.png)

| Pixel size | d = 1 | d = 4 | d = 16 | GDAL box |
|---|---|---|---|---|
| 2.5 km | 3.6e-5 | 2.2e-6 | 1.3e-7 | 0.094 |
| 25 km | 1.1e-3 | 5.7e-5 | 3.3e-6 | 0.26 |
| 100 km | 0.012 | 7.4e-4 | 4.5e-5 | 0.23 |

(Mean absolute difference from densify 64 in field units, on a field of
amplitude about 12 with a 3-pixel checker; EPSG:4326 0.1 degree source to
EPSG:3031; pixels that straddle the antimeridian excluded.)

The box's error is not a densify question. GDAL transforms only the
top-left and bottom-right corners and takes the axis-aligned box between
them (figure, panel a). Where the destination is rotated against the
source, as EPSG:3031 is against longitude and latitude everywhere, the box
is a different region from the pixel, and the error is of the order of the
field's variation over a pixel. rwarp keeps the box as the default because
it is GDAL's; the exact footprint is the correct one.

So densify 1 is enough for destination pixels up to a few tens of source
pixels across; larger pixels, or strongly curved transforms (near a pole,
or a curvilinear grid), want more. Section 6 proposes an adaptive rule.

## 4. Where the time goes, measured

Average, one band, `f32`, single thread. Two settings: an affine source
rotated 0.1 radians at ratios from 0.5 to 32 source pixels per destination
pixel (linear), with a source window just covering the tile as a planner
would give it; and an EPSG:4326 0.1 degree global source to a 256 x 256
EPSG:3031 tile at 2.5 to 50 km, through proj4rs, with exact transforms and
with rwarp's `ApproxTransformer` (max error 0.125). Times are microseconds
per destination pixel, median of three runs.

![Cost against ratio for the box, rwarp 0.2, and the two prototypes, at
densify 1 and 4](img/m19-cost.png)

| Ratio | Box | rwarp 0.2 | ratio to box | Burn alone | Cells per pixel |
|---|---|---|---|---|---|
| 0.5 | 0.07 | 1.00 | 14x | 1.02 | 2 |
| 1 | 0.08 | 1.56 | 20x | 1.32 | 4 |
| 2 | 0.12 | 2.38 | 20x | 2.55 | 9 |
| 4 | 0.34 | 4.28 | 13x | 4.92 | 26 |
| 8 | 0.79 | 9.22 | 12x | 9.49 | 82 |
| 16 | 3.08 | 18.5 | 6x | 17.8 | 292 |
| 32 | 10.7 | 42.6 | 4x | 33.3 | 1095 |

(Affine, densify 1. "Burn alone" is the burn call in a replica of
`area_row_exact`, timed separately; the replica's output equals rwarp's.)

Three things show:

- **The burn costs about 1 microsecond a call plus about 1 microsecond
  per source row the outline spans.** It grows linearly with ratio, as the
  boundary does, never quadratically: interior runs are cheap. The box's
  own reduce loop is quadratic in ratio (it visits every covered pixel and
  computes a separable weight), which is why the ratio to the box falls
  from 20x to 4x.
- **The tile size does not matter.** Per-pixel cost is flat from 16 x 16
  to 1024 x 1024 destination tiles (2:1: box 0.11 to 0.17, rwarp 0.2 2.4 to
  3.0). Batching outlines into fewer calls would not help either: the burn
  treats each polygon on its own, and rwarp's own note records that one
  burn per row measured no faster.
- **Under a projection the transform dominates.** At 10 km (about 7 source
  pixels per destination pixel) with exact transforms, rwarp 0.2 spends 1.5
  of its 3.7 microseconds transforming at densify 1, 6.0 of 8.8 at densify
  4 and 23 of 28 at densify 16. With the `ApproxTransformer` the box drops
  to 0.42 but the exact footprint does not move: its arrays are rings, not
  scanlines, and the approximate transformer, which only interpolates
  along a line of constant y, transforms them exactly. Against the box
  under the same transformer that is 10x (densify 1) to 77x (densify 16).

![Transform, coverage and reduce for rwarp 0.2 and the two prototypes on
the EPSG:3031 10 km tile, with exact and approximate transforms](img/m19-projected.png)

## 5. Four ways to make it cheaper, measured

All four keep the exact footprint's answer: each prototype's output was
compared with rwarp 0.2's on every case above, and agrees to 1e-6 relative
(the `f32` rounding of controlledburn's fractions); with nodata holes, too.

### 5.1 A shared lattice for the transform

The destination pixel outlines of a tile are the lines of one lattice.
Transform it once per row band: the band's bottom row line (`ncol densify +
1` points) becomes the next band's top line, and the interior points of
each densify level (`ncol + 1` points at `y = row + k / densify`) are a line
too. Each pixel's outline is then assembled from shared points. A corner is
transformed once instead of four times, an edge point once instead of
twice: 1 point per pixel at densify 1 instead of 4, 7 instead of 16 at
densify 4. Every array is a scanline, so the approximate transformer
interpolates it.

Measured at 10 km with exact transforms, the transform falls from 1.5 to
0.38 microseconds at densify 1 and 6.0 to 2.4 at densify 4; with the
approximate transformer to 0.15 and 1.35.

### 5.2 A coverage window instead of the burn

For one small ring the sparse output and the traversal tables are not
needed. Split each edge at every cell wall, so each piece lies in one cell
`(i, j)`, with midpoint `xm` and height `dy`. By Green's theorem the area
of the ring inside row `j` and left of `x = k` is the sum of `(x - k) dy`
over the pieces left of `k` (the walls contribute nothing). Differencing
at `k = i` and `k = i + 1`:

```text
coverage(i, j) = sum over pieces in (i, j) of (xm - (i + 1)) dy
               - sum over pieces in row j left of column i of dy
```

Book the first sum and each piece's height into a dense window over the
ring's bounding box, then one prefix pass per row resolves coverage. This
is the cell accumulation of FreeType's "gray" rasteriser and of font-rs,
kept in `f64` instead of quantised. No chaining around cell perimeters, no
per-cell records, and no allocation once the window is warm. Contributions
are signed and add, so holes are rings with weight -1.

With the lattice, coverage plus reduce costs 0.28 microseconds a pixel at
0.5:1, 0.47 at 2:1 and 1.3 at 8:1 (densify 1), against 1.0, 2.6 and 9.5
for the burn alone.
At 16:1 and above the window plus reduce is faster than the box, whose
reduce computes a weight per covered pixel.

### 5.3 Shared edges: a boundary integral over row prefix sums

For `average` the reducer only needs the weighted sum and the valid area.
Let `S(i, j)` be the sum of valid values in row `j` left of column `i`.
Inside cell `(i, j)` the field's antiderivative in x is
`F(x) = S(i, j) + (x - i) v(i, j)`, and the area-weighted sum over the
pixel is the boundary integral of `F dy`, one lookup per piece. The valid
area is the same integral over the validity mask. The work follows the
outline's perimeter in source pixels, not its area: interior pixels are
skipped entirely, which is the "skip interior pixels" idea taken to its
end.

Because the result is a line integral, each edge of the destination
lattice can be integrated once, added to the pixel on its left and
subtracted from the pixel on its right (figure, panel b). A pixel's sum is
then four lookups into per-edge results: half the walking of a per-pixel
outline. This is the "one traversal over the destination grid's edges"
idea; with an additive formulation it needs no shared topology, only the
lattice.

The prefix sums cost one pass over the source window, shared by all
destination pixels (0.003 to 2.8 microseconds a destination pixel across
the ratios, included in the figures). At 0.5:1 to 4:1 the integral costs
0.12 to 0.43 microseconds a pixel, 1.3 to 2.3x the box. Summed-area tables
(Crow 1984) do the same for axis-aligned boxes; the boundary integral
extends them to any polygon.

It does not serve every reducer. Mode, min, max and the quantiles need
each covered pixel's weight, so they keep the window. RMS is the integral
of `v^2`; `AverageThresholds` needs a prefix per excluded value. Multiband
with `BandNodata::Partial` needs a validity prefix per band.

### 5.4 A box fast path, and an adaptive densify

A separate box path for near-affine transforms is not needed. The box is
exact only for axis-aligned pixels, and there the boundary integral is
already cheap: horizontal edges have `dy = 0` and contribute nothing, so
only the two vertical edges are walked. The window has the same property.

Densify can be chosen per lattice edge. The midpoint of each edge is on
the densify-2 lattice, itself a scanline, so transforming it costs one
more approximate line per band. The area between edge and chord is about
two thirds of the edge length times the sagitta (the midpoint's distance
from the chord), and the error falls as 1/d^2, so `d = ceil(sqrt(sagitta /
tolerance))` per edge reaches a tolerance with no wasted points. Not built;
the 1/d^2 law in section 3 is the evidence it would work.

## 6. The patches

Both are in `/mnt/project-files/exact-footprint/`, as `git format-patch`
files on the current `main` of each repository.

**controlledburn-rs** (`0001-CoverageWindow-and-RowPrefix...patch`, on
c66deb2): a new module `window` with

- `CoverageWindow`: `reset`, `reset_to_ring`, `add_ring(xs, ys, weight)`
  (orientation-independent; 1 for an exterior, -1 for a hole),
  `add_segment`, `resolve`. Index space (column `i` spans `[i, i + 1]`,
  row 0 at the top), with the conversion from a `GridSpec` documented.
  Pieces beyond the window's columns clamp exactly, so a caller can size
  the window to its buffer rather than the ring.
- `RowPrefix<K>`: row prefix sums of `K` fields (values and a mask for a
  mean), `integrate_ring` and `integrate_polyline` for shared edges.
- `ring_area`.

Tests check both against `burn` in coverage mode on star-shaped rings,
rings with every vertex on the lattice (edges along cell walls), a ring
partly outside the window, holes, and shared edges, 20,000 random cases
clean. Version 0.2.2: additive API. The module docs carry a C++ port note:
both are plain loops over `double` and port line for line to the C++
controlledburn.

The window is also the natural backend for wxy-warp's index-space cover
(`CoverMethod::Index`) and for `zonal --coverage` on small polygons, and
`RowPrefix` gives a zonal mean over a polygon in time proportional to its
perimeter.

**rwarp** (`0001-Exact-footprint-shared-lattice...patch`, on 4ae1446):
`Footprint::Exact` uses a `Lattice` (section 5.1, with each densify level
transformed as its own scanline) and a reused `CoverageWindow`. Weights
follow what `burn` gave (within 1e-6 of 1 is 1, at or below 1e-6 is
dropped, others rounded to `f32`; full cells reduced before partial ones),
so every reducer and tie rule sees the same sequence as before. It needs
controlledburn 0.2.2 (test locally with a `[patch.crates-io]` path entry).

| EPSG:3031 tile | rwarp 0.2 | patch, exact | patch, approximate |
|---|---|---|---|
| 2.5 km, d = 1 | 2.37 | 0.66 (3.6x) | 0.40 (5.9x) |
| 2.5 km, d = 4 | 7.93 | 3.29 (2.4x) | 1.02 (7.8x) |
| 10 km, d = 1 | 4.09 | 0.97 (4.2x) | 0.71 (5.8x) |
| 10 km, d = 4 | 9.93 | 3.83 (2.6x) | 1.83 (5.4x) |
| 50 km, d = 1 | 15.2 | 2.63 (5.8x) | 2.04 (7.4x) |
| 50 km, d = 4 | 21.1 | 5.55 (3.8x) | 4.70 (4.5x) |

(Microseconds per pixel, average; speed-up against rwarp 0.2 with exact
transforms. Mode costs within about 25% of average.)

With exact transforms the patched output equals rwarp 0.2's: average
identical to 2.4e-7, mode identical in every pixel, nodata pattern
identical, on all six cases with a source full of nodata blocks. All rwarp
tests pass, including the mode fixtures that run through the exact
footprint. rwarp's timing test goes from 327 to 55 ms at densify 1 and
361 to 84 ms at densify 4, against 18 ms for the box. With the approximate
transformer the output differs by the approximation itself (up to 0.9
field units on a blocky field), as the box path's does.

Not in the patch, as follow-ups by value: the boundary integral for
`Average` and `Rms` without thresholds (a further 1.5 to 2x at low ratios,
more at high ratios, but per-band prefixes under `BandNodata` and a second
code path); adaptive densify; and reusing burn scratch inside controlledburn
itself (worth about 40% of every `burn` call, for every caller, not only
rwarp).

## 7. Caveats

- **Signed areas.** The window and the integral add signed contributions.
  For a valid ring that is the same as the burn. A destination pixel whose
  outline folds (a transform with a fold, or a pixel across a
  singularity) gets the signed measure of its pullback rather than the
  non-zero winding rule. Both answers are meaningless there; the burn's
  is no better.
- **Antimeridian.** Neither the exact footprint nor the patch handles a
  pixel that straddles the source's longitude seam: its outline spans the
  whole source width. The box has GDAL's wrap detection. Unchanged by the
  patch.
- **Precision.** Row prefix sums are `f64` and local to the source window,
  so a lookup differences numbers no larger than a row's sum; at 8,000
  columns of values near 1e4 that is about 1e-8 absolute. The window keeps
  `f64` and rounds to `f32` only to match the burn.
- **Area is in source pixel space.** As before: planar area in the source
  CRS for an affine source, neither target CRS area nor ellipsoidal area.

## 8. What do we get, what does it cost, what if we didn't

**We get** the exact footprint at a cost close to the box: under exact
transforms the transform now dominates both, and with the approximate
transformer the exact footprint is 1.5 to 3x the box at densify 1 rather
than 9 to 17x. That makes it a reasonable default candidate for `average`
and `mode` in wxylib, where the box is wrong by the field's variation over
a pixel whenever the grids are rotated. controlledburn gains two small
tools with uses beyond rwarp (index-space cover, zonal means).

**It costs** about 530 lines in controlledburn (half of them tests) and a net 110
in rwarp, a minor version bump of controlledburn, and a dependency bump in
rwarp. The C++ controlledburn has nothing to port unless it wants the
tools.

**If we didn't**, the exact footprint stays 9 to 200x the box under a
projection, mostly in transforms the approximate transformer cannot reach,
and few callers would choose it.
