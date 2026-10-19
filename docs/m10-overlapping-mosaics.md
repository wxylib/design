# m10: Overlapping COG mosaics, measured on REMA v2

Status: musing, 2026-10-19. It measures one real case and states what a
virtual store of it would need; it becomes work only through a numbered
document.

Michael, 2026-10-19: virtualise a COG mosaic whose tiles overlap, which
needs what Zarr calls rectilinear chunks, with the REMA v2 2 m mosaic
(5800 COGs, AustralianAntarcticDivision/remav2 `data-raw/rema_index2m.parquet`)
as the example. He also noted that rectilinear means "just different sized
chunks", not overlap, and that the two are easy to conflate.

## 1. Two problems, kept apart

- **Overlap** is a question for the plan: where two sources cover the same
  cells, which one is read. A Zarr chunk key maps to exactly one chunk, so
  a store cannot hold two candidates for one cell. Overlap has to be
  resolved before byte references are written, by choosing a cut.
- **Rectilinear chunks** are a question for the grid: once the cut is
  chosen, the chunks either side of it may not all be the same size. A
  rectilinear grid lists the chunk edges along each axis, so it can carry
  those sizes. It says nothing about overlap.

The link between them: a byte reference must be a whole encoded tile (a
range inside a compressed tile is not addressable). So the cut decides
which tiles stay whole, and the tiles that do not stay whole become the
odd-sized chunks the rectilinear grid has to describe.

## 2. What REMA v2 2 m looks like

Measured over HTTP from the public PGC bucket, on three COGs of supertile
41_40 (`2_1`, `2_2` side by side, `1_2` below `2_2`), reading only their
headers and four tiles (scripts in the project folder
`wxylib-design/m10/`, tifffile over range requests):

| | value |
|---|---|
| shape per COG | 25100 x 25100, float32, 2 m |
| tiles | 512 x 512, 50 x 50 = 2500 per COG, 7 levels |
| compression | LZW (5) with floating-point predictor (3) |
| nodata | -9999 |
| neighbour offset | 50 km = 25000 px, so 100 px (200 m) of overlap per seam |
| tile alignment across a seam | 25000 = 48 x 512 + 424: the two tile grids never share an edge |
| overlap values | identical: 2 x 51,200 overlap cells compared, all equal |
| edge tile padding | the padded part of a COG's last tile decodes to 0, not -9999 |

Because the overlap values are identical, priority does not matter for
REMA: any cut inside the overlap gives the same pixels.

## 3. The cut and the grid

Along one axis, with COG A on the left and B starting 25000 px later:

- Cut at A's tile edge 25088. A's tiles 0 to 48 stay whole (references).
  A's tile 49 (12 valid px plus padding) is dropped: B covers it.
- B's tile 0 spans A-coordinates 25000 to 25512; only 25088 to 25512 is
  wanted, so it becomes one 424 px chunk that is computed and stored
  (inline), not referenced.
- B's tiles 1 to 49 stay whole, and so on at the next seam.

No other cut does better: the two tile grids never share an edge, so one
chunk per seam per axis cannot be a whole tile. The x edges are then
`[512] x 49, 424, [512] x 49, 424, ...`, and the same for y: a rectilinear
grid in which nearly every chunk is 512 and one per seam is 424. zarrs
0.23 accepts a last chunk that runs past the array edge
(`rectilinear.rs`: `offset + size >= array_size`), so the outer padded
tiles can stay references.

Per COG, in a mosaic with all neighbours present: 49 x 49 = 2401 whole
tiles are references and 99 cells are computed, so 96 percent of chunks
stay virtual. Across 5800 COGs that is about 13.9 M references and 0.57 M
computed chunks. From the file sizes, the computed chunks are roughly 4
percent of the full-resolution bytes, on the order of 100 GB (inferred,
not counted).

Overviews repeat this per level (level 1: 12500 = 24 x 512 + 212), each
level its own rectilinear array under GeoZarr `multiscales`.

## 4. What breaks today

1. **The codec.** LZW with predictor 3 has no Zarr v3 codec in zarrs, and
   `wxy_virtual::scan_tiff` refuses any predictor. Without a
   `floatpred`-style codec (imagecodecs has one for zarr-python, not
   checked here), REMA cannot be read virtually by wxylib whatever the
   grid. The computed chunks must also be written in the same codec, since
   mdim-refs allows one codec per array.
2. **The grid.** wxylib reads regular grids only (`wxy-zarr` rejects
   others, `ChunkGrid` has one chunk shape), and mdim-refs/0.2 assumes one
   regular grid per array.
3. **A missing neighbour.** Where a COG has no neighbour (the coast, or a
   three-COG test), its last tile's padding decodes to 0, so that tile
   cannot be referenced as is: 0 is a valid elevation. It must be computed
   with the padding set to nodata.

Icechunk 2.3 stores arrays on any chunk grid and refuses only to reindex
non-regular ones, so it is not the blocker.

## 5. Smallest test

The same three COGs, cropped to a few tiles either side of the two seams:

- build the plan (a GTI or mosaic VRT; for REMA any order works);
- emit the rectilinear edges, references for whole tiles, and computed
  chunks for the seam column, the seam row and the uncovered corner;
- compare with GDAL reading the VRT, every cell;
- report the reference fraction and the computed bytes.

It needs, in order: a predictor-3 decoder in wxylib's TIFF path (or a
test COG rewritten without a predictor, to separate the two problems), a
rectilinear `ChunkGrid`, and an mdim-refs extension carrying per-axis
chunk edges.

## 6. What we would get, what it costs, what if we didn't

- Get: a 5800-COG mosaic as one array with 96 percent of its bytes left
  in place; the case Michael's REMA and Icechunk work already hit
  (19.5 M refs from rustycogs IFDs) put on a footing that can be checked
  against GDAL.
- Cost: a codec, a grid type, a spec extension, and a computed-chunk
  writer that encodes exactly as the source does.
- Without it: overlapping mosaics stay VRT- or GTI-only, or get copied
  whole.
