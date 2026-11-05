# m28: Warp output-grid defaults

Status: musing, 2026-11-05. Settles which parts of a warp's target grid
(CRS, extent, cell size, cell count) a caller gives and which are
inferred, in wxylib's CLI, bindings and browser. Based on wxylib/core at
`caba7b2` (`wxy warp`, `wxy_warp::GridSpec`), rwarp 0.3.1 and
hypertidy/rwarp at `d908348`, vaster 0.2.0, wxylib/py and wxylib/r at
main, wxylib/web at main (`render::bounds`, `cog.js`), GDAL 3.8.4
(osgeo.gdal) and odc-geo 0.5.4. Builds on doc 05 (W1, extent heuristics),
doc 03 (S4b: "the target stays explicit; an extent suggestion, if wanted,
is a separate helper"), m11 (quiet operations) and m20 (the movement
layer). Measurements:
[measurements/m28-output-grid](../measurements/m28-output-grid/README.md).
Figures: [img/m28-rules.png](img/m28-rules.png),
[img/m28-extents.png](img/m28-extents.png), from `scripts/m28_figures.py`.

## Summary

The question: when a warp is asked for with less than a full target grid
(only a CRS, or a CRS and a cell size, or a CRS and an extent), what
should wxylib fill in, by what rule, and where should that code live? And
where should wxylib differ from gdalwarp?

- **The warp itself stays explicit.** `GridSpec` (CRS, geotransform,
  size) is still the only target the warp and its planner accept.
  Defaults are resolved before it, by a separate step whose every
  inference is reported (`--dry-run` lists what was given and what was
  inferred). This is doc 05 W1 and doc 03 S4b carried through, not
  reopened.
- **gdalwarp's suggestion fails on exactly the cases that matter.**
  Measured on 28 source and target pairs: a whole-world grid into south
  polar stereographic gets cells 1.4e21 m across; a 150E to 150W box into
  Mollweide gets an extent that holds half the data; a 0 to 360 global
  grid into Web Mercator gets 133 x 1605 cells. odc-geo, the other common
  rule, errors or degenerates on 12 of the 28. On a UTM tile into nearby
  CRSs gdalwarp and the rule below agree within 2 %.
- **A rule that keeps cell area, finds tears and drops singular cells
  works on all 28.** Measure the target area each source cell takes
  over a lattice of blocks; the cell size is the square root of the
  median. Tell a tear (the target's seam, a wrap round a pole) from a
  stretch (a pole of the target) by bisecting long block edges. The
  extent is the bounding box of the good blocks plus the two sides of
  each tear. Every result covers at least 90 % of the footprint, and
  reports what it dropped.
- **Recommended defaults (section 6):** the target CRS defaults to the
  source's; a given extent is never moved; a given cell size aligns the
  inferred extent to its own multiples (gdalwarp's `-tap`, on by
  default); over-determined requests that do not agree are errors, not
  silent edge moves; a cell budget refuses absurd grids before any
  allocation. The suggestion's limits (singular ratio, the target CRS's
  area of use, an optional size cap) are on by default and each can be
  set or turned off (section 6.1).
- **Where it lives:** grid arithmetic (resolve, snap, check) in vaster,
  which already has `vcrop`; the suggestion in rwarp, which has the
  transformers; flags, reporting and bindings in wxylib. About 300 lines
  in rwarp and 150 in vaster, no new crate.

## 1. What exists now

| Where | What the caller gives | What is inferred |
|---|---|---|
| `wxy warp` (CLI) | `--crs`, `--extent XMIN YMIN XMAX YMAX`, `--size NCOL NROW`, all required | nothing |
| `wxy_warp::GridSpec` | `from_extent(crs, [xmin, xmax, ymin, ymax], [ncol, nrow])` | nothing |
| wxylib/py `warp` | `dst_extent (xmin, xmax, ymin, ymax)`, `dst_dim`, `dst_crs` | nothing |
| wxylib/r `wxy_warp` | `dst_extent`, `dst_dim`, `dst_crs` | nothing |
| wxylib/web `cog.html` | a CRS from a preset list, a canvas | extent from a preset, or from `render::bounds` (the source's 33 x 33 lattice of points moved to the target, bounding box) grown to the canvas aspect |
| rwarp 0.3.1 | a target geotransform and size | nothing (`with_target_extent` only tells the transformer a lon/lat target crosses 180) |

Two observations follow. The warp has never guessed, and nothing has
needed it to except the browser, which grew its own bounding-box helper.
And the four entry points disagree on extent order: the CLI takes
gdalwarp's `-te` order (xmin ymin xmax ymax), `GridSpec`, the bindings and
the browser take vaster's (xmin xmax ymin ymax).

## 2. What gdalwarp does

`gdalwarp` resolves the target grid in `GDALSuggestedWarpOutput2` (the
part that guesses) and then in `gdalwarp_lib.cpp` (the part that combines
options). Measured with osgeo.gdal 3.8.4, warping to a VRT so no pixels
move (`gdal_matrix.py`).

### 2.1 The option matrix

On a 10 m UTM tile over Tasmania into EPSG:4326 (the well-behaved pair):

| given | size | cell size | extent | note |
|---|---|---|---|---|
| `-t_srs` only | 12584 x 9244 | 0.0001078 | footprint | square cells |
| `-tr 0.0001` | 13566 x 9965 | 0.0001 | footprint, right and bottom edges moved out | |
| `-tr -tap` | 13566 x 9966 | 0.0001 | snapped outward to multiples of 0.0001 | |
| `-ts 1000 1000` | 1000 x 1000 | 0.0013566 x 0.0009966 | footprint | cells not square |
| `-ts 1000 0` | 1000 x 735 | 0.0013566 | footprint, bottom edge moved | square, aspect kept |
| `-te` | 12939 x 9633 | 0.0001059 | given | cell size re-derived for the extent |
| `-te -tr 0.0001` | 13700 x 10200 | 0.0001 | given | divides exactly |
| `-te -tr 0.000137` | 10000 x 7445 | 0.000137 | ymin moved from -43.42 to -43.41996 | silent |
| `-te -tr -tap` | 10001 x 7446 | 0.000137 | given extent snapped outward | silent |
| `-te -ts 1000 1000` | 1000 x 1000 | 0.00137 x 0.00102 | given | |
| `-tr -ts` | error | | | "cannot be used at the same time" |
| `-tap` alone | error | | | needs `-tr` |

The combination rules are sound. Two of them are quiet operations in m11's
sense: with `-te` and a `-tr` that does not divide it, gdalwarp rounds the
cell count to nearest and moves the right and bottom edges (here by 4.4 m;
on world-0.5 into EPSG:3031 with an 8000 km extent and 34.25 km cells,
outward by 14.5 km), and says nothing.

### 2.2 The suggestion

With only `-t_srs`, `GDALSuggestedWarpOutput2` samples points along the
source's edges (and a lattice inside, if edge points fail), takes their
bounding box in the target, and sets the cell size so that the source's
diagonal in pixels equals the target's: cells are square, and the cell
count roughly matches the source's when the map is close to conformal and
the footprint fills its box.

![For each of 28 source and target pairs, the suggested grid's cell
count over the source's (left, log scale) and the fraction of the
source's footprint inside the suggested extent (right), for gdalwarp,
odc-geo and the m28 rule.](img/m28-rules.png)

The failures, all with only the target CRS given:

| pair | gdalwarp result | what went wrong |
|---|---|---|
| world-0.5 to EPSG:3031 | 569 x 569 cells of 1.4e21 m | the north pole maps to infinity in south polar stereographic; the bounding box takes it |
| same, with `-tr 25000` | the process aborts (`std::length_error`) | 1e39 cells requested; not an error, an abort |
| same, `-te_srs EPSG:4326 -te 140 -70 160 -60` | "Attempt to create -10x59 dataset" | a negative width from the absurd suggested cell size |
| world-0.25 (0 to 360) to EPSG:3857 | 133 x 1605 cells, y from -2.4e8 to 2.4e8 m | the latitude clamp gdalwarp applies to a -180 to 180 source is not applied to a 0 to 360 one |
| pacific-150to210 to Mollweide | 242 x 116, half the data outside the extent | the footprint is split by the target's seam; one side is kept |
| world-0.5 to Mollweide | 1610 x 805, five times the source's cells | the diagonal rule on a map whose bounding box is mostly empty corners |
| utm55s-10m to Mollweide | 6.97 m cells from a 10 m source, 4.4 times the cells | the diagonal rule on a sheared footprint; Mollweide is equal-area, so 10 m is the honest answer |

![The 150E to 150W, 60S to 30S box in Mollweide: the footprint (green)
falls on both sides of the map's seam; gdalwarp's extent (red) holds the
eastern half; the m28 rule's (black) holds both, at the cost of the empty
middle.](img/m28-extents.png)

These are GDAL 3.8.4 results. GDAL's suggestion code has changed since
(antimeridian handling especially), so each row needs rechecking on 3.14dev
before anything is said upstream; the fixtures `oracles` workflow can run
`gdal_matrix.py` in `gdal-r-python:dev`. The point for wxylib does not
depend on the version: a bounding box of moved points has no defence
against a point that should not count.

### 2.3 odc-geo

odc-geo's `compute_output_geobox` (Python, the rule odc-geo's xarray `reproject`
uses when given only a CRS) is the other widely used rule: cell size "same" when source
and target units agree, otherwise "fit" (the scale at the centre pixel);
pixel edges snapped to 0, 0 by default; a single `shape` number means the
longer side. Its default alignment is the better default (section 6).
Its "same" rule keeps 10 m for a UTM tile into Web Mercator at 43S, where
a 10 m cell is 13.7 m of Mercator, so it asks for 1.9 times the cells.
The centre pixel is the worst place to measure a polar source (the pole),
and its footprint polygon breaks at seams and target poles: 12 of the 28
pairs give an error (`AssertionError` for three Mollweide pairs), a grid
of one or two cells, an extent that holds under half the footprint, or
an extent to 1e23 m.

## 3. What a default should do

The cases sort the requirements:

1. **Hold the footprint.** The extent should contain every part of the
   source that lands somewhere sensible in the target, including both
   sides of a seam.
2. **Keep the information, not the diagonal.** One target cell per source
   cell, by area, where the map is well behaved: equal-area maps then get
   the source's cell size exactly (10 m stays 10 m in Mollweide).
3. **Drop what is singular, and say so.** A pole of the target (north
   pole in 3031, the poles in Mercator) cannot be in any finite grid.
   Leaving it out is right; leaving it out silently is not.
4. **No per-projection cases.** Doc 05 W1 asked for this; gdalwarp's
   Mercator clamp is the cautionary example (it applies to one source
   longitude convention and not the other).
5. **Refuse before allocating.** A suggested grid bigger than a budget is
   an error with the numbers in it, never an abort.

## 4. Is this overbuilding?

No Rust crate suggests a warp output grid. In Python, rasterio's
`calculate_default_transform` calls GDAL's; odc-geo has its own (above).
The rule is small (the prototype is under 200 lines of numpy), it needs only a
forward map and a source grid, and the browser already carries a cruder
copy of it. It belongs in the movement layer (m20), where the
transformers are, not in a new crate.

## 5. The rule

`measurements/m28-output-grid/suggest_rule.py` is the prototype. Given a
source grid and a forward map (any rwarp transformer):

1. Lay a lattice of up to 128 x 128 blocks over the source and move every
   block corner to the target.
2. Each block's quadrilateral area, divided by the source cells it holds,
   is the target area one source cell takes there.
3. An edge is long when, per source cell along it, it is more than 20
   times the square root of the median area. Bisect each long edge in
   source pixel space (40 steps). If both sides settle on two separate
   points, the edge is torn: the map jumps there (the target's seam, or a
   wrap round a pole). If one side keeps running away, the edge is
   stretched towards a pole of the target. A block with a torn edge is
   torn. A block is singular if a corner fails to move, or if it is not
   torn and its area is more than 100 times the median.
4. Cell size: the square root of the median area over the good blocks
   (neither torn nor singular). Square cells, cell area kept.
5. Extent: the bounding box of the good blocks' corners, plus the
   settled points either side of each tear that lie within one good
   block of them, so the extent reaches the seam from both sides.
6. Whole cells, the overshoot split evenly about the footprint.

Reported with the grid: the fraction of blocks dropped as singular and
as torn.

Results (all 28 pairs in `suggest_rule.json`; selected):

| pair | gdalwarp | odc-geo | m28 rule | dropped (singular, torn) |
|---|---|---|---|---|
| utm55s-10m to 4326 | 12584 x 9244 | 12765 x 9377 | 12914 x 9486 | 0, 0 |
| utm55s-10m to moll | 33567 x 15714 at 6.97 m | 23398 x 10955 at 10 m | 23380 x 10945 at 10.006 m | 0, 0 |
| world-0.5 to 3857 | 699 x 699, clamped to the Web Mercator square | 720 x 8716, y to 2.4e8 m | 610 x 854, y to 2.8e7 m (85.9 degrees) | 1.6 %, 0 |
| world-0.5 to 3031 | 569 x 569 cells of 1.4e21 m | 5.9e16 x 3.7e18 | 1552 x 1552 at 91 km, to 7.1e7 m | 10.9 %, 0 |
| world-0.25 (0 to 360) to 4326 | 1440 x 720 | 1426 x 722 | 1440 x 720, -180 to 180 | 0, 0.8 % |
| antarctic-25km to 4326 | 667 x 127 | 2 x 1 | 1469 x 281, lat from -90 | 0, 0.4 % |
| pacific-150to210 to moll | 242 x 116, half the data | error | 1411 x 139, both sides | 0, 0.8 % |
| identity (four sources already in the target CRS) | the source grid | the source grid | the source grid | 0, 0 |

What the rule does not do well, and why that is acceptable:

- **A footprint split by a seam gets a box across the whole map**
  (pacific-150to210 into Mercator or Mollweide: 6 to 7 times the source's
  cells, most of them empty). This is the honest bounding box; the
  useful answer is a different target (centre the map on the data, as
  `+lon_0=180` does). The torn fraction is the signal: wxylib should say
  so and suggest that, not pick a side.
- **The limit near a target pole is a knob, not a fact.** With the
  singular threshold at 100 times the median area, world into Mercator
  stops at 85.9 degrees (Web Mercator's square stops at 85.05) and world
  into south polar stereographic stops near 53N. Both grids are finite,
  modest (2 and 9 times the source's cells) and reported as dropping 1.6
  % and 10.9 %. A user who wants a different cut gives an extent.
- **A whole-world source into a polar projection is still a strange
  request.** The rule makes it harmless, not sensible.

With an extent given, the same lattice gives the cell size from the
blocks that land inside it: world-0.5 into 3031 within 4000 km of the
pole gets 33 km cells (gdalwarp: 7.6 km, about 19 times the cells a
0.5-degree source holds there); the UTM tile gets 0.000105 degrees
(gdalwarp 0.0001059).

## 6. Recommended defaults

What the caller gives, and what wxylib infers:

| given | gdalwarp | wxylib (recommended) |
|---|---|---|
| nothing (no `--crs`) | source CRS | source CRS (today: required) |
| CRS | suggested extent and cell size | suggested (section 5), reported |
| CRS, cell size | suggested extent, right and bottom edges moved; `-tap` to align | suggested extent, snapped outward to multiples of the cell size (aligned by default) |
| CRS, size | suggested extent, non-square cells | suggested extent grown about its centre to the size's aspect, square cells (what `cog.html` does to fit a canvas) |
| CRS, size with one 0 | aspect from the extent | same |
| CRS, extent | cell size re-derived for the extent; size rounded; cell size adjusted per axis | cell size from the blocks inside the extent (section 5); size rounded; cell size adjusted per axis, reported |
| extent, cell size | size rounded to nearest; right and bottom edges moved silently | exact or an error: "extent is 233.6 cells of 34250; give 234 cells (extent to 4014500) or a cell size of 34188.03" |
| extent, size | exact | exact |
| cell size, size | error | allowed: that many cells at that size, centred on the footprint's centre, snapped |
| all three | error | exact or an error |
| extent in another CRS (`-te_srs`) | box corners and edges moved | the box densified with bigcurve, moved, bounding box |

Every row with an inference ends in a `GridSpec` and a record of what was
inferred, how (rule, lattice, thresholds), and what the suggestion
dropped. `--dry-run` prints it; the GeoZarr output does not carry it (it
describes the grid, not how it was chosen).

Three defaults differ from gdalwarp, each with a reason:

- **Alignment on when the cell size is given.** A user who types a cell
  size wants grids that stack; snapping the inferred extent to multiples
  of it costs at most one cell per edge. odc-geo made the same choice.
  Get: separate warps at the same resolution line up without `-tap`.
  Cost: the extent can differ from gdalwarp's by under a cell. If not:
  wxylib repeats a footgun every gdalwarp user learns about the hard way.
  A suggested cell size is never snapped to: it is nobody's number.
- **Disagreement is an error.** Get: the extent a user typed is the
  extent they get (m11: no unsigned operations). Cost: one more message
  to read. If not: edges move by up to half a cell (or more, as measured)
  with no record.
- **A cell budget.** `--max-cells`, default 2^30 (a gigacell, 4 GB of
  float32), checked before anything is allocated or fetched. Get: no
  aborts and no surprise 1e39-cell plans. Cost: a flag for the rare large
  job. If not: wxylib inherits gdalwarp's crash.

And warnings, not errors: any dropped fraction above zero, and any torn
fraction, are printed with the grid (and the torn case names the
recentring fix).

### 6.1 Limits on a suggestion: on by default, each settable

The section 5 rule has one limit built in (the singular ratio). Two more
belong beside it, and all three are heuristics a user can set or turn
off, rather than fixed behaviour:

| limit | default | what it does | off |
|---|---|---|---|
| singular ratio | 100 | drops blocks whose area per source cell is more than this times the median | `none`: every finite corner counts |
| CRS expanse | on, when the target CRS has an area of use | drops blocks whose centre is outside the target CRS's area of use (a lon/lat box in its EPSG metadata) | `none`: the footprint is not clipped |
| size cap | off; `--suggest-max-size NX NY` | coarsens the suggested cell size until the grid fits NX by NY (a thumbnail, a preview) | the default |

`--suggest-limit none` turns all of them off and gives the raw bounding
box, which is what gdalwarp does. The cell budget (`--max-cells`) is not
one of them: it refuses, it does not shape.

The CRS expanse is metadata, not a per-projection case, and on the EPSG
targets here it does what the special cases try to (second pass in
`suggest_rule.json`, `area_of_use`):

| pair | section 5 rule | with the CRS expanse | dropped as outside |
|---|---|---|---|
| world-0.5 to 3857 | 610 x 854, to 85.9 degrees | 620 x 595, to 85.06 degrees (the area of use's own limit) | 6.2 % |
| world-0.5 to 3031 | 1552 x 1552 at 91 km, to 7.1e7 m | 236 x 236 at 27.9 km, to 3.3e6 m (60S) | 83.6 % |
| antarctic-25km to 32755 | 764 x 594 | 30 x 261, the 144E to 150E strip | 98.2 % |
| utm55s-10m to 3031 | 15177 x 15177 | refused: Tasmania is outside "Antarctica" | 100 % |
| antarctic-25km to 3031 (identity) | 480 x 480 | 270 x 270, cut at 60S | 75.8 % |

The last two rows set two rules. An identity request (target CRS equal to
the source's, nothing else given) returns the source grid and never runs
the suggestion, so a store is never cropped to its own CRS's area of use.
And a request the expanse refuses outright says which limit refused it
and how to turn it off (`--suggest-limit none`, or give `--extent`): a
UTM tile in polar stereographic is a legitimate request, only an unusual
one. PROJ strings (Mollweide, the Hobart LAEA here) carry no area of use,
so for them the singular ratio is the only limit.

The CRS backend has to supply the area of use: PROJ's database does,
proj4rs does not. Until wxylib's CRS backend has one (terrio-crs, or a
small table of EPSG areas generated from PROJ's), the expanse limit is
unavailable and the ratio stands alone, as in section 5.

## 7. Where the code lives

| piece | home | why |
|---|---|---|
| resolve given and inferred parts, snap, check agreement | vaster (`resolve_grid`, beside `vcrop`) | pure grid arithmetic, no CRS; R vaster has the same vocabulary, so the C++ and R siblings can follow |
| the suggestion (section 5) | rwarp (`suggest::suggest_grid(src, &transformer, opts) -> Suggestion`) | needs a forward map and nothing else; GDAL keeps its own next to the warper too |
| densifying a box in another CRS | bigcurve, through rwarp's adapter | m20: bigcurve owns the forward-map seam |
| flags, `--dry-run` record, `--max-cells`, `--suggest-limit`, bindings arguments | wxylib (wxy-warp `GridRequest`, wxy-cli, py, r, web) | I/O and presentation stay above the movement layer |

wxy-cli gains `--res` and makes `--extent` and `--size` optional;
`--crs` defaults to the source's. The bindings gain optional `dst_res`
and lose the requirement on `dst_extent` and `dst_dim`. The browser
replaces `render::bounds` with the rwarp suggestion and keeps its
canvas fit, which is the "size given" row.

Extent order stays as it is in each place (gdalwarp's in the CLI,
vaster's in code and bindings), because each matches its users; the
`--dry-run` record names the four numbers so a mixed-up order is visible.

## 8. Order of work

1. vaster: `resolve_grid` with the section 6 table as its tests (pure,
   small).
2. rwarp: `suggest_grid`, with the 28 pairs as a test table against the
   prototype's JSON (same thresholds; agreement to a cell).
3. wxylib: `GridRequest` in wxy-warp, the CLI flags and `--dry-run`
   record, then py and r, then web.
4. Recheck section 2 on GDAL 3.14dev in the fixtures workflow; anything
   that still fails goes to the osgeo-upstream tracker as a note, not as
   a GDAL contribution.

Steps 1 and 2 wait for rwarp's current sprints, like m20's moves.

## 9. Open

- The thresholds (100 for singular, 20 for long edges, a 128 lattice)
  are from 28 pairs. A curvilinear source (a swath, a tripolar ocean
  grid) is the next test; the rule only needs a forward map, so rwarp's
  geolocation transformer should drop in.
- Whether a torn footprint should also offer the recentred CRS directly
  (`+lon_0` moved to the footprint's middle), or only name it.
- Whether "cell size, size" (allowed here, an error in gdalwarp) earns
  its place.
- Where the area of use comes from for wxylib's CRS backend (section
  6.1), and whether the expanse limit should apply only to the side that
  overflows (keeping a source that straddles the area's edge whole along
  the other axis).
