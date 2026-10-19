# m11: Quiet operations: what composite raster readers hide, and the fixtures that expose them

Status: musing, 2026-10-19. Companion to m10 (overlapping COG mosaics),
which measures REMA v2 and COP30 and states the cut, grid and codec each
needs. This one generalizes: it inventories the operations that
composite readers perform silently, places reader designs on a ladder of
explicitness, and proposes the fixture set that exposes each operation.
Claims about REMA and COP30 are measured (m10, plus section 4a's
source-table pass: 26,475 rows from one VRT download, kept in
`measurements/cop30/`, a stratified 12-file header sample, one
cross-distribution read); claims about Sentinel-2 are stated as
predicates to run. It becomes work only through a numbered document.

## 1. The failure mode: honesty does not compose

Exhibit: the OpenTopography COP30 VRT. Every child file reports its true
grid (a 1201 x 3601 tile at 3 arcseconds says so). The VRT reports its true
grid (1,296,001 x 626,401 at 1 arcsecond). Both are honest. But the
composite interface returns one geotransform, no overviews, block 128 x
128 - and nothing says that polar samples are 10-arcsecond values
replicated into 10 x 10 blocks. A user computing slope near the pole gets
artifacts at a resolution the dataset never had, and every tool in the
chain behaved correctly. Each layer is honest; honesty does not survive
composition, because the composition step is where decisions get made and
the composite interface has no slot to report them.

These decisions are the quiet operations. They are not bugs: each one is
the reason composite readers are usable at all. The problem is only that
they are unsigned.

## 2. Inventory of quiet operations

Each row is an operation a composite reader (VRT, GTI, driver-internal
mosaicking) performs without declaration, with the dataset where it was
observed:

| operation | what it hides | observed in |
|---|---|---|
| painting order over overlap | a per-pixel source-selection policy (last-listed-valid wins) | REMA buffers (harmless: values identical, proven) |
| implicit resampling | SrcRect != DstRect in a source entry is a silent warp | COP30 VRT (ratios exactly 1.5 to 10; 55 percent of sources, measured) |
| registration reconciliation | pixel-is-point vs area, shared edge lines, +1 grids | COP30 children (3601 convention), VRT (+1 global grid) |
| product substitution across scales | overview levels that are different datasets | rema-ovr pyramid (section 5) |
| dtype and codec substitution | per-level or per-source type changes unified on read | rema-ovr (Float32 / Int16 / Float32 across levels) |
| CRS pretence or refusal | heterogeneous-projection sources forced onto one grid, or rejected | Sentinel-2 zone mosaics (section 4) |
| temporal compositing | "the mosaic" of scenes is an undeclared latest-valid composite | any scene mosaic VRT |
| access-pattern re-presentation | composite advertises its own block size, unrelated to source tiling | COP30 VRT (128 x 128 over 512-tiled children) |
| periodic-axis flattening | a cylinder stored with its seam duplicated | COP30 (-180 and +180 columns both present) |

The general observation: every one of these is a rendering decision fused
into the read path. Painting is compositing; SrcRect scaling is warping;
level substitution is generalization. The reader is a renderer that does
not say so.

## 3. The ladder: hidden, declared, separated

Three designs for composite access, ordered by where rendering decisions
live:

1. **Hidden rendering** - plain mosaic VRT and driver-internal
   mosaicking. The operations above run inside open/read with no
   declaration. Maximally convenient; the operations are unsigned.
2. **Declared rendering** - warped VRT, GTI, explicit resampling flags.
   The target grid, algorithm, and source table are written down and
   inspectable. But the renderer is still welded to the reader: the
   declaration can be read, it cannot be not-run.
3. **Separated rendering** - virtual chunk references plus a grid
   declaration. The store cannot express a resample, a composite, or a
   substitution even if it wants to, so every quiet operation is forced to
   become a plan-time decision (the cut), a declared structure (band or
   zone arrays, rectilinear edges, a levels table), or a named runtime
   verb (regrid, composite).

GTI deserves a precise placement: it is a vector layer of source
footprints with per-source attributes - the instance relation, already,
at file granularity, with the renderer attached. The virtualization
program can be stated in one line against it: the same relation, at chunk
granularity, with the renderer detached. The lineage that produced the
most capable hidden-rendering tools also converged on the table; the
remaining step is separation, not invention.

Rung 3 is not a replacement for rungs 1 and 2. Hidden and declared
renderers remain the right tools for consumption. Rung 3 is the storage
and distribution layer underneath them, where the operations are signed.

## 4. The fixture trilogy

Three public archives, each breaking a different assumption, each
measurable in an afternoon of header reads:

| | REMA v2 2m | COP30 (OpenTopography) | Sentinel-2 MGRS |
|---|---|---|---|
| overlap | 100 px interior buffer, identical data | 1 shared line, identical by construction | ~10 km, same acquisition resampled twice |
| the cut | free (either dual) | free (origin, trivially) | priced: a policy decision |
| structure | one grid | resolution bands (array per band) | CRS zones (array per zone) |
| time | snapshot | snapshot | per-tile ragged observation sets |
| seam assertion | identity (passed) | identity (expected) | inverted: assert difference, measure it |
| status | measured (m10) | measured (m10 and 4a) | predicates below |

Sentinel-2 decomposes into the first two fixtures plus one new
ingredient. Within a UTM zone, adjacent granules share one lattice and
their overlaps come from one resampling of one datatake: predicted
bit-identical, i.e. REMA-like, the m10 recipe applies per zone. Zones are
COP30's bands with CRS in place of resolution: regular subdomains that
cannot share an array, so the honest shape is a tree of per-zone arrays.
The new ingredient is the cross-zone overlap, where values are close but
not equal because the same acquisition was resampled through two
projections. There the cut is a genuine data decision (for example:
prefer the native zone), and the seam assertion inverts - assert the
overlaps differ, and record the differences. That histogram is not a test
artifact: it is the processing chain's resampling error, measured
empirically at every zone boundary, obtainable from byte references
alone. The fixture that breaks the identity check starts producing
science at the moment it breaks.

Smallest Sentinel-2 test: one datatake crossing one zone boundary, four
to six COGs covering both zones and all three band resolutions
(10980/5490/1830 px grids); header scan for dims, blocking, codec
contract; within-zone identity asserted; cross-zone deltas binned;
per-zone rectilinear declaration computed. All predicates, no claims,
until run.

### 4a. COP30, measured

From the VRT's own source table (26,475 rows, one XML download, no COG
requests) plus a stratified header sample (two files per width, about a
dozen requests) and one cross-distribution read:

- **Convention:** src_h = 3601 for all 26,475 sources; widths exactly
  {361, 721, 1201, 1801, 2401, 3601}. The N+1 shared-line (SRTM-style)
  convention holds archive-wide.
- **Registration:** raw tiepoints sit exactly on integer degrees (all
  sampled origin residues are 0): pixel-is-point, with readers supplying
  the half-pixel edge. The VRT's extents at integer +/- 1/7200 degree
  confirm it globally - and explain the apparent band bleed when binning
  tiles by their top edge: boundary rows tip into the neighbouring bin by
  half a pixel. Binning artifact, not anomaly.
- **Bands:** width maps one-to-one onto the absolute-latitude bands once
  boundary rows are binned on tile interiors rather than top edges.
- **Baked resampling:** DstRect/SrcRect ratios are exactly
  {1, 1.5, 2, 3, 5, 10}, anti-diagonal with band; 14,589 of 26,475
  sources (55 percent) are upsampled in the index. Children are pasted
  at ratio x src_w (DstRect widths 3601 to 3610, a fractional 3601.5 for
  the 1.5 band), so each paste is 3600 + ratio wide and neighbours
  overlap by the shared sample line rendered at the paste ratio (1 to 10
  destination pixels) - painting quietly resolves that as well.
- **Coverage:** 26,475 of 62,640 one-degree cells (42.3 percent);
  latitude spans the south pole (to -90) up to 84N, and every cell south
  of 80S is present, at 720 or 360 px per degree; 31 sources occupy the two
  antimeridian columns (W180 and E179), so the duplicated meridian is
  present wherever land is.
- **Encoding** (sampled; assumed constant pending a full scan): tiled
  512 x 512, float32, Deflate, predictor None - and no nodata tag at
  all. Two consequences. The virtual store's fill value is a declaration,
  not a read: nothing in the files supplies it (ocean is stored as 0, a
  value, not a mask). And the codec chain is zlib alone - no predictor
  stage, no specialty codecs - so the reader gap for this fixture
  reduces to existing Zarr v3 zlib/numcodecs handling (for GDAL, already
  filed as OSGeo/gdal#14917). Of the fixtures, this is the one GDAL is
  closest to reading back today.
- **Two distributions, one tile** (N73 W030): OpenTopography serves
  1201 x 3601, Deflate, no predictor; the AWS copernicus-dem-30m copy of
  the same logical tile is 1200 x 3600, Deflate, FloatingPoint predictor.
  The distribution determines the grid convention AND the codec chain.
  This upgrades section 1's framing from inferred to measured: the
  dataset has neither a grid nor an encoding of its own - its
  distributions do, and the virtualization layer is where both get
  chosen.

A fourth case is named but not specified: nested insets - a
high-resolution patch inside a regional grid. Overlap with different
resolution and different data simultaneously; neither a cut nor a
rectilinear grid resolves it, because the correct structure is
multiscale-with-overlap. It is recorded here as the open case.

## 5. The liberal pyramid (rema-ovr, measured from its own repo)

mdsumner/rema-ovr publishes a single-endpoint VRT for REMA v2 whose
overview chain is, deliberately:

- 2 m, 10 m, 32 m: VRTs over the archive's Float32 tiles (LZW,
  floating-point predictor), unfilled DEM, hosted on the source bucket.
- 100 m: a conversion of the FILLED product (filled with a different
  DEM) to Int16, sparse tiles, internal overviews stripped, hosted on
  GitHub.
- 500 m, 1 km: the filled product's Float32 singles, copied out of slow
  tarballs to GitHub.

So walking the pyramid changes the product (voids fill in as you zoom
out), the dtype (Float32 to Int16 to Float32), the codec profile, and the
host. GDAL's Overview mechanism accepts all of it without comment,
because it never promised that an overview is a decimation of its base -
and the result is useful precisely because of the substitutions: at
coarse scales the filled surface is the right answer, at fine scales the
honest voids are.

This is cartographic generalization rediscovered: level of detail as
curation, not derivation. Different scales legitimately show different
data - map series always did. The consequence for strict multiscale
conventions is direct: a convention that models a pyramid as one dataset
at several sizes, with one dtype and one codec chain and implicit shared
provenance, cannot describe this object at all. What can describe it is a
levels relation: one row per level with its own grid, dtype, codec,
provenance, and host - the instance table again, this time along the
scale axis. The declaration-shaped question "which stand-in answers at
which scale" is a policy, and policies belong in tables, not in
assumptions.

(m10's pyramid-break result is the involuntary version of the same
point: even a derivation pyramid stops being one mosaicable dataset past
level 2, by arithmetic. rema-ovr is the voluntary version: the pyramid
was never one dataset, by design.)

## 6. Cubes, relations, and the hybrid

A gridded cube of a swath-and-tile archive requires three renderings
before the first array exists: a warp (many CRSs to one), a temporal
binning (per-tile ragged observation times to one shared axis), and a
grid unification (multiple native resolutions to one). Datacube pipelines
perform all three and present the output as the data. Meanwhile the
archive's own canonical description - its catalog - is already the
instance relation at file granularity, with acquisition times, zone CRSs,
and native grids intact.

The structural reading: the relation is the published truth; the cube is
a thrice-rendered view; and the common tooling gradient runs backwards,
treating relation-to-cube conversion as ingestion into the real format
and the relation as scaffolding. Table/array hybrids are therefore not a
workaround for awkward data - they are the factoring the data has had
since the first granule: tables for the instance layer (what exists,
where, when, in which CRS, at which bytes), arrays for rendered views,
each view carrying its rendering declaration. The Sentinel-2 fixture is
the entry point because it is the archive where the table cannot be
hidden: there is no cube without visibly running the warp.

## 7. Not claimed

- COP30 full-archive encoding scan: section 4a's contract comes from a
  stratified 12-file sample and is assumed constant; the full pass is one
  header-harvest call away when it matters.
- COP30 seam values: the shared line duplicates samples by construction,
  but no value read has confirmed identity.
- Sentinel-2 within-zone overlap identity, codec contract, blocking, and
  cross-zone delta magnitudes: all awaiting the header pass and seam
  reads (tooling exists: catalog cache, tile arithmetic, header scanner).
- The inset fixture: named, not designed.
- Whether any current multiscale convention admits per-level dtype,
  codec, and provenance: to check against the conventions' texts before
  asserting in a numbered document.
- Periodic-axis handling in chunked stores (the duplicated meridian):
  recorded as structure, no proposal made.
