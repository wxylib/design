# m10: Overlapping COG mosaics, measured on REMA v2 and COP30

Status: musing, 2026-10-19. It measures two real archives and states what a
virtual store of each would need; it becomes work only through a numbered
document. Claims are marked measured (read from the files, or from a
source table kept in `measurements/`), reported (from header reads made
elsewhere, not repeated here) or inferred.

**Implementation (2026-10-28):** Open. One prerequisite landed: the TIFF horizontal predictor
(Predictor=2) as a codec, `wxy-predictor` ([core #13](https://github.com/wxylib/core/pull/13)). Predictor=3,
a rectilinear `ChunkGrid`, per-axis chunk edges in mdim-refs and the
truncate codec (section 8) are open.

The question: virtualise a COG mosaic whose files overlap, which needs what
Zarr calls rectilinear chunks. REMA v2 2 m (5800 COGs,
AustralianAntarcticDivision/remav2 `data-raw/rema_index2m.parquet`) and the
Copernicus 30 m DEM (COP30, as distributed on AWS and by OpenTopography) are
the two test archives.

## 1. Three problems, kept apart

- **Overlap** is a question for the plan: where two files cover the same
  cells, which one is read. A Zarr chunk key maps to exactly one chunk, so
  overlap is resolved before byte references are written, by a cut.
- **Variable chunk sizes** are a question for the grid. A rectilinear grid
  lists the chunk edges along each axis. It says nothing about overlap.
- **Padded tiles.** A TIFF's last tile in each row and column is stored
  full size and padded. A Zarr chunk decodes to exactly its declared shape,
  so a padded tile can be a reference only where it hangs off the end of
  the array (zarrs 0.23 allows a last chunk with `offset + size >=
  array_size`, `rectilinear.rs`). Inside a mosaic, a padded tile needs a
  codec that keeps only the leading part of the decoded block (a truncate
  codec), or the chunk is computed and stored.

A byte reference must be a whole encoded tile, so the cut decides which
tiles stay whole, and what is left at each seam is either a truncated
reference or a computed chunk.

## 2. REMA v2 2 m

Measured over HTTP from the public PGC bucket on three COGs of supertile
41_40 (`2_1`, `2_2` side by side, `1_2` below `2_2`), reading headers and
four tiles (scripts in the project folder `wxylib-design/m10/`, tifffile
over range requests). A header scan of all 5800 COGs (40,600 IFD rows) is
reported to give the same codec row for every file.

| | value |
|---|---|
| shape per COG | 25100 x 25100, float32, 2 m, pixel-is-area |
| tiles | 512 x 512, 50 x 50 = 2500 per COG |
| overviews | 12550, 6275, 3138, 1569, 785, 393 (each `ceil(dim / 2)`) |
| compression | LZW (5) with floating-point predictor (3) |
| nodata | -9999 |
| neighbour offset | 50 km = 25000 px, so 100 px (200 m) of overlap per seam |
| tile alignment across a seam | 25000 = 48 x 512 + 424: the two tile grids never share an edge |
| overlap values | identical: 2 x 51,200 overlap cells compared, all equal |
| edge tile padding | the padded part of a COG's last tile decodes to 0, not -9999 |

Because the overlap values are identical, priority does not matter for
REMA: any cut inside the overlap gives the same pixels.

## 3. Two cuts, and they are duals

Along one axis, COG A at 0 and B at 25000:

| | tile-edge cut (at A's edge 25088) | origin cut (at B's origin 25000) |
|---|---|---|
| A keeps | tiles 0 to 48 whole | tiles 0 to 47 whole, tile 48 truncated to 424 px |
| B keeps | tile 0 cut to 424 px (computed), tiles 1 to 49 whole | tiles 0 to 49 from its origin |
| per COG, 2D | 2401 whole references, 99 computed chunks | 2304 whole references, 97 truncated references, 0 computed |
| needs | an encoder matching the source codec | a truncate codec |
| stored bytes | the computed chunks, about 4 percent (inferred, on the order of 100 GB for all 5800) | none |

The whole-tile references are the same tiles under both cuts. Moving from
the tile-edge cut to the origin cut, once a truncate codec exists, replaces
only the seam chunks: a re-manifest, recorded as one commit, with the
computed chunks then garbage. So the cut is a sequencing choice: tile-edge
now, origin later, references reused throughout.

Either way the x edges are 512 almost everywhere and 424 once per seam: a
rectilinear grid. The outer padded tiles of the mosaic stay references
through the end-overhang allowance.

## 4. The pyramid breaks at level 3

Neighbours register at overview level L only if their 25000 px offset is a
whole number of level-L pixels: `25000 * dim_L / 25100 = 250 * dim_L / 251`,
an integer only when 251 (prime) divides `dim_L`.

| level | dim | 251 divides | one mosaic array by reference |
|---|---|---|---|
| 0 | 25100 | yes (offset 25000) | yes |
| 1 | 12550 | yes (offset 12500) | yes |
| 2 | 6275 | yes (offset 6250) | yes |
| 3 | 3138 | no | no: neighbours sit a fraction of a pixel apart |
| 4 to 6 | 1569, 785, 393 | no | no |

The `ceil` in the overview sizes is the cause. Mosaic arrays by reference
exist for levels 0 to 2; levels 3 and up are either one array per COG or a
pyramid computed from level 2.

## 5. COP30, one product on two grids

**AWS** (`copernicus-dem-30m`, `Copernicus_DSM_COG_10_...`), measured on
N00 E006 and N55 E010:

| | value |
|---|---|
| shape | 3600 x 3600 at the equator, 3600 x 2400 at 55N (longitude banded by latitude) |
| registration | pixel-is-point, first sample on the integer degree; 3600 per degree, no shared line |
| tiles | 1024 x 1024, three overview levels |
| compression | DEFLATE (8) with floating-point predictor (3) |
| nodata | no tag |

No overlap at all, but 3600 = 3 x 1024 + 528, so every file's last tile
row and column is padded and lands inside the mosaic. Per axis the chunks
are `1024, 1024, 1024, 528` repeating. Without a truncate codec, 7 of every
16 chunks are computed (about 27 percent of the bytes). For this
distribution the truncate codec is on the critical path.

**OpenTopography** (`COP30_hh.vrt` and its children), measured from the
VRT's own source table (26,475 rows, `measurements/cop30/`), a header
sample of two files per width and one file read from both distributions:

- children are 3601 rows by band width + 1 columns, pixel-is-point with
  tiepoints on integer degrees, every adjacent pair sharing one sample
  line: overlap in its smallest form;
- 512 x 512 tiles, float32, DEFLATE with no predictor, and no nodata tag
  (ocean is stored as 0, a value; a store's fill value is a declaration,
  not something read from the files); the sample is assumed to hold
  archive-wide;
- the same tile (N73 W030) is 1201 x 3601 with no predictor here and
  1200 x 3600 with predictor 3 on AWS: the distribution sets the codec
  chain as well as the grid;
- the VRT is 1,296,001 x 626,401 at 1 arcsecond, 90S to 84N, and pastes
  every source at the ratio of its band (1, 1.5, 2, 3, 5, 10; 14,589 of
  26,475 sources upsampled, DstRect widths 3601 to 3610, 3601.5 for the
  1.5 band). Each paste is 3600 + ratio wide, so neighbours overlap by
  exactly the shared sample at the paste ratio. Neither the upsampling
  nor the edge-inclusive grid can be expressed by byte references;
- 26,475 of 62,640 one-degree cells are present (42.3 percent): sparse,
  so missing chunks in Zarr; 31 sources sit in the antimeridian columns
  (W180 and E179).

The width falls to a tenth of the equatorial width, and most of the
narrow files are Antarctic: every one of the 3,600 cells south of 80S is
present, at 720 or 360 px per degree. Under the origin cut each file owns
from its origin and drops its shared last line, which falls inside the
block that is truncated anyway. Kept widths and x chunks per band, with
the file counts per hemisphere:

| band (abs lat) | px per degree | VRT ratio | files N | files S | x chunks |
|---|---|---|---|---|---|
| 0 to 50 | 3600 | 1 | 7889 | 3997 | 512 x 7, 16 |
| 50 to 60 | 2400 | 1.5 | 2373 | 86 | 512 x 4, 352 |
| 60 to 70 | 1800 | 2 | 2988 | 594 | 512 x 3, 264 |
| 70 to 80 | 1200 | 3 | 1704 | 2848 | 512 x 2, 176 |
| 80 to 85 | 720 | 5 | 396 (to 84N) | 1800 | 512, 208 |
| 85 to 90 | 360 | 10 | 0 | 1800 | 360 |

y is `512 x 7, 16` everywhere. No chunk grid expresses the banding itself,
because pixel width depends on latitude; the honest shape is one array per
latitude band, each rectilinear, oceans as missing chunks.

Without a truncate codec, the seam chunks of each file are computed:
about 0.9 percent of the pixels in the 3600 band, 15 percent in the
2400, 1800 and 1200 bands, 29 percent at 720, and all of the 360 band,
whose files are narrower than one block. Over the archive that is 6.6
percent of the pixels (measured counts, inferred bytes). With no
predictor, computed chunks need only a zlib encoder.

The same product ships on two grid conventions depending on distributor.
The grid is a property of the distribution, not the dataset, and the
virtualisation layer is where it gets chosen.

## 6. The fixture pair

| | REMA v2 2 m | COP30 |
|---|---|---|
| overlap | 100 px buffer | none (AWS); one shared line (OpenTopography) |
| resolution | uniform | banded by latitude |
| coverage | dense | 42.3 percent |
| cut | either | origin |
| seam chunks | computed or truncated | truncated (computed costs about 27 percent on AWS, 6.6 percent on OpenTopography) |
| codec | LZW, predictor 3 | DEFLATE, predictor 3 (AWS); DEFLATE, no predictor (OpenTopography) |
| extra structure | pyramid break at level 3 | band tree; VRT-baked rendering |
| awkward files | margin tiles off the origin lattice | 84N cap; antimeridian column |

Both come to the same recipe: a cut (plan), a rectilinear grid
(declaration), a seam set proportional to perimeter over area (computed or
truncated), and one codec shared by referenced and computed chunks.

## 7. Padding and the codec, in consequence

- **Padding is the writer's choice, not a spec.** REMA pads with 0, a valid
  elevation. A hole inside the mosaic (a missing neighbour on the coast)
  must therefore be computed with the pad set to nodata; the end-overhang
  allowance covers only the outer edge of the array. Any account that says
  pad equals nodata is wrong. Each new archive gets a pad-value check in
  its fixtures.
- **Computed chunks need encoder parity.** They must be encoded with the
  array's codec (mdim-refs allows one codec per array), so the pipeline
  needs LZW and predictor-3 encode as well as decode. A decode fixture
  (source tiles read back through the chunk codec chain) does not prove
  the encoder. The reverse fixture does: encode a known block with the
  pipeline's codec, decode through the array chain, assert bit identity.
  A GDAL cell-by-cell comparison covers both ends but does not say which
  one failed.

## 8. Requirements, in dependency order

1. An encoder-parity fixture for the TIFF codec path (encode, then decode,
   bit identical), beside the decode fixture.
2. Predictor-3 decode and encode in wxylib's TIFF path, for LZW and
   DEFLATE (REMA and AWS COP30; OpenTopography COP30 has no predictor).
   Today `wxy_virtual::scan_tiff` refuses any predictor and zarrs
   has no floating-point predictor codec.
3. A rectilinear `ChunkGrid` in wxylib (today `wxy-zarr` reads regular
   grids only), with zarrs' end-overhang allowance so outer padded tiles
   stay references.
4. An mdim-refs extension carrying per-axis chunk edges (0.2 assumes one
   regular grid per array).
5. A truncate codec (a zarr-extensions proposal). Not on the critical path
   for REMA, where it converts the tile-edge cut to the origin cut by
   re-manifest; on the critical path for AWS COP30; for OpenTopography
   COP30 it saves 6.6 percent of the pixels, and the whole 360 band.

Icechunk 2.3 stores arrays on any chunk grid and refuses only to reindex
non-regular ones, so it is not the blocker.

## 9. Smallest test

The three REMA COGs, cropped to a few tiles either side of the two seams,
plus one COP30 band seam:

- build the plan (a GTI or mosaic VRT; for REMA any order works);
- emit the rectilinear edges, references for whole tiles, and computed
  chunks for the seams and the uncovered corner;
- include overview level 3 (the pyramid break), an interior hole with the
  pad check, and the encoder-parity fixture;
- compare with GDAL reading the VRT, every cell;
- report the reference fraction and the computed bytes.

## 10. Not claimed

- OpenTopography COP30 codec: from a sample of two files per width,
  assumed constant; the full header scan is not run.
- COP30 seam values: the shared line duplicates samples by construction;
  no read has confirmed identity.
- Computed-chunk byte totals for COP30: pixel fractions only, not
  compressed bytes.
- That a truncate codec proposal exists in zarr-extensions: reported, not
  checked here.

## 11. What we would get, what it costs, what if we didn't

- Get: a 5800-COG mosaic as one array per level 0 to 2 with 96 percent of
  its bytes left in place, and the AWS COP30 tiles likewise once a
  truncate codec exists; the 19.5 M references already built for REMA
  from its IFDs put on a footing that is checked against GDAL.
- Cost: a predictor codec with an encoder, a grid type, a spec extension,
  a truncate codec for COP30, and a computed-chunk writer.
- Without it: overlapping or padded mosaics stay VRT- or GTI-only, or get
  copied whole.
