# m35: Unstructured grids and DGGS: one spectrum, strict names

Status: position, 2026-11-21. Nothing here is built and nothing is
proposed for building now (section 7). It answers where wxylib stands on
grids that have no (i, j) index, fixes the vocabulary so that "DGGS" and
"unstructured" stop being used for each other, and reads one concrete
proposal against that vocabulary: the dynamical.org draft layout for
reduced Gaussian, icosahedral and HEALPix datasets, as shown in the
notebook
[dwd-icon-eu-forecast-5-day-icosahedral-unstructured-grid](https://github.com/dynamical-org/notebooks/blob/unstructured-grid-access-patterns/dwd-icon-eu-forecast-5-day-icosahedral-unstructured-grid.ipynb)
(branch `unstructured-grid-access-patterns`, read 2026-11-21). The
notebook's outputs were read; the staging store behind it was not
reachable from the build environment, so nothing below was measured on
its bytes. Based on wxylib/core at `15bab9e` and design at `4c17881`.
Builds on [doc 02](02-data-model.md) (the rung ladder),
[doc 04](04-landscape.md) section 8, [m20](m20-movement-crates.md),
[m21](m21-conservative-examples.md), [m24](m24-foundations-hardening.md),
[m31](m31-view-chunk-planner.md), [m33](m33-warp-meshes.md) and the
[pyinterp watch note](watch/pyinterp.md).

## Summary

- **The names.** A grid without an (i, j) index is described by four
  questions (section 2): are positions computed or stored, is topology
  computed or stored, is there a hierarchy by arithmetic, and does a cell
  id mean the same thing outside this dataset. A **DGGS** answers
  computed, computed, yes, yes. A general **unstructured mesh** answers
  stored, stored, no, no. Reduced Gaussian grids and ICON sit between,
  at different places, and neither is a DGGS.
- **Where wxylib sits.** The data model has had both rungs since doc 02
  (R4 implicit, R5 explicit) and `wxy-domain` carries the two variants as
  opaque traits. No reader, no scheme and no mesh operation exists. The
  movement crates below wxylib hold most of the geometry a first mesh
  operation needs (exact coverage of a polygon on a grid, great-circle
  edges, conservative weights), built for other reasons.
- **The gap in the model.** Doc 02 puts "DGGS and L3 bins" on one rung.
  That rung needs two named kinds: *row schemes* (reduced Gaussian, L3
  bins: ragged rows, no hierarchy) and *DGGS* proper. Section 2 proposes
  the wording.
- **The dynamical.org draft** is sound: one `cell` dimension with centre
  coordinates is the CF reduced-grid form, and UGRID in a side group is
  the right home for polygons. Section 5 lists ten points of feedback,
  the main ones being a stored cell area, cell order as a stated
  property, a different encoding for HEALPix (ids, not polygons) and a
  global test case before the layout is fixed.
- **Build now?** No. The roadmap places meshes and DGGS after the
  current stages, and nothing has changed that. Section 7 names the two
  small pieces that would come first and what would trigger them.

## 1. The question

Three grid families are in wide use for weather and climate output and
none fits two horizontal dimensions: reduced Gaussian (ECMWF IFS),
icosahedral triangles (DWD ICON, also MPAS and FESOM style meshes) and
HEALPix (Destination Earth, nextGEMS). They are often all called
"unstructured", and HEALPix and H3 are often called "grids" beside
ICON's. Both habits hide differences that decide what a dataset has to
store and what a library can compute. The question has two halves: what
are the right names, and how much of each family can wxylib describe,
read and operate on today.

## 2. The spectrum

Doc 02 section 3 already separates what is computed from what is stored.
For grids with no (i, j) index, two more questions are needed to keep
DGGS distinct.

1. **Positions**: computed from a cell number by a rule, or stored per
   cell?
2. **Topology** (neighbours, shared edges, vertices): computed, or
   stored as connectivity?
3. **Hierarchy**: are a cell's parent and children found by arithmetic
   on its id?
4. **Identity**: does the cell id name the same piece of the Earth in
   any dataset that uses the same system, with no file consulted?

| Grid | Positions | Topology | Hierarchy | Identity | What must be stored |
|------|-----------|----------|-----------|----------|---------------------|
| Regular lon/lat | computed | from (i, j) | by decimation | the affine | 6 numbers |
| Reduced Gaussian (N320, O1280) | computed from a row table | within a row by arithmetic; between rows by search | none | the grid name | grid name, or one count per row |
| L3 bins (integerised sinusoidal) | computed from `NUMROWS` | as reduced Gaussian | none | `NUMROWS` | 1 number |
| HEALPix, rHEALPix | computed | computed | yes, 4 children | global: (level, scheme, id) | level and indexing scheme |
| H3, ISEA families, S2, A5 | computed | computed | yes (aperture 7, 3, 4) | global | system and level |
| ICON (R2B8 and nests) | stored | stored | by construction, stored as parent indices in the grid file | the grid file's UUID | every vertex, connectivity, or a pointer to the grid file |
| MPAS, FESOM, coastal models, TINs (UGRID generally) | stored | stored | none | the file | everything |

Reading the table:

- **A DGGS is a reference system, not a mesh format.** All four answers
  are "computed" or "yes". Two datasets in the same DGGS align by joining
  on the id, with no geometry and no file in common. This is the strict
  sense: global, hierarchical, id arithmetic, dataset-independent. It is
  why a DGGS dataset should store ids and a system name, and should not
  store polygons.
- **Reduced Gaussian is implicit but not a DGGS.** The grid name fixes
  every position, so it is on the implicit side, but there is no
  hierarchy (O640 does not nest in O1280) and no id system beyond a
  position in the row order. It is closest to a rectilinear grid whose
  rows have different lengths: latitude is a 1D vector, each row is
  regular in longitude. NASA's L3 bins are the same structure.
- **ICON is an explicit mesh with a generator.** It is made by bisecting
  an icosahedron and then relaxing the vertices, so positions cannot be
  recomputed from a formula; the grid file is the definition. Its
  hierarchy exists but is stored. A limited-area nest such as ICON-EU is
  a subset of a refined global grid, so it is not global either. In
  practice it is handled as a UGRID mesh that happens to be very regular.
- **The spectrum is real.** From top to bottom each row stores more and
  computes less, exactly as R1 to R3 do for indexed grids. Hierarchy and
  identity are what separate DGGS from the rows around it, not the cell
  shape and not the absence of (i, j).

**Proposed wording for doc 02.** Keep R4 (implicit) and R5 (explicit) as
the rungs. Name two kinds within R4: *row schemes* (reduced Gaussian, L3
bins) and *DGGS* (hierarchical, global ids). Reserve "unstructured" for
"no (i, j) index" as doc 02 already does, covering both rungs, and say
"explicit mesh" when R5 is meant. ICON is R5 with a `related` hierarchy;
the generator is provenance. This is a wording change and one added
example row, with no change to types: `CellScheme` covers both R4 kinds,
and hierarchy would be an optional second trait.

## 3. Where wxylib sits

| Piece | State | Bearing |
|-------|-------|---------|
| Data model (doc 02) | R4 and R5 rungs, DGGS as "a mesh whose everything is computed", decisions DM1, DM7, DM8 | the taxonomy above extends it; no conflict |
| `wxy-domain` | `Positions::Scheme(dyn CellScheme)` with `name` and `centre`; `Positions::Explicit(dyn Elements)` with `len`, "kept opaque" | variants exist so types need not change; no implementation of either |
| `wxy-zarr` | reads arrays and GeoZarr `proj:`; no CF `coordinates`, UGRID or `cell_ids` handling | a `(time, cell)` array opens as values with no positions |
| controlledburn | exact coverage fractions of polygons on a regular grid, `burn_par`, `relate_cells` | burning each mesh face onto a target grid is the mesh-to-grid conservative weight table (m21 example E5, rwarp stage 5) |
| bigcurve | great-circle edge densification with shared edges | mesh edges are great-circle arcs; needed where cells are large or near a pole |
| rwarp `mesh` | stage 1: `QuadMesh` for curvilinear grids only (equal-area cell maps, point location with hints) | quads with (i, j), so R3; no triangles, no connectivity |
| rwarp conservative weights | rectilinear and spherical box weights, equal to pyinterp to 1.3e-15 | row schemes are rows of spherical boxes: reduced Gaussian to regular is within reach of the same engine, row by row |
| Warp meshes (m33) | contract for a drawable triangle mesh, not built | a UGRID triangle mesh with face values is already close to that contract: drawing is nearer than computing |
| View planner (m31) | chunks for a view on affine pyramids; curvilinear and model grids listed as open | for one `cell` dimension the answer depends on cell order (section 5, point 3) |
| Landscape (doc 04 section 8) | crates to adopt named: cdshealpix, h3o, a5; "no Rust UGRID crate" and "no single Rust DGGS abstraction" recorded as gaps | unchanged |
| Roadmap | meshes and DGGS in S8 and later; "mesh is conversion-first" (gate 5); "DGGS = implicit mesh, later" (gate 1) | unchanged |

In one sentence: the model is ready, the engines beside it cover mesh to
grid by accident of design, and nothing reads or indexes a mesh or a
DGGS yet.

## 4. Gaps, in the order they would bite

1. **No positions for a `cell` dimension.** CF `coordinates` (1D centre
   arrays over one dimension) is not read. This is the smallest step and
   it is shared by all three families.
2. **No point location.** Nearest centre on the sphere, and containing
   face. For a DGGS this is arithmetic (cdshealpix); for a row scheme it
   is a row search and a division; for R5 it needs a tree.
3. **No UGRID adapter.** Face-node connectivity, start index, fill for
   mixed faces, and the `mesh` and `location` attributes on data.
4. **No mesh-to-grid weights as a product.** The geometry exists
   (controlledburn on faces); the table, its normalisation and an oracle
   (ESMF, already used in the non-affine experiment) do not.
5. **No scheme implementation.** A HEALPix `CellScheme` over cdshealpix
   is small; row schemes need only the row table.
6. **No grid-to-mesh or mesh-to-mesh.** Not needed for conversion-first.

## 5. The dynamical.org draft, read against this

The draft: horizontal space is one `cell` dimension with `latitude` and
`longitude` centre coordinates; where the source defines polygons, a
`mesh/` group holds them as UGRID; grids without stored polygons
(reduced Gaussian, HEALPix) have no `mesh/` group. Data variables carry
`mesh: /mesh/mesh` and `location: face`. The example is ICON-EU on its
triangles, 768,608 cells.

What is right and should stay: the single dimension with auxiliary
coordinates is CF's own form for reduced grids (CF section 5.3), so it
is a convention, not an invention; plain xarray works with no extra
library; polygons are kept out of the way of users who do not need
them; UGRID is the vocabulary every mesh library reads.

Feedback, most useful first:

1. **Store the cell area.** A `cell_area` variable on `cell`, named by
   `cell_measures = "area: cell_area"` on each data variable. ICON's
   grid file has it, Gaussian weights give it for reduced Gaussian, and
   it is constant for HEALPix. Area-weighted means then need no mesh
   and no library (`field.weighted(ds.cell_area)`), the same way on all
   three families. In the notebook this is the step that pulled in the
   mesh and UXarray only to get weights.
2. **Say which sphere.** ICON's positions are on a sphere of radius
   6,371,229 m, and so are its areas. The `spatial_ref` variable should
   state that datum and the areas should say they are spherical on that
   radius, so that nobody has to guess whether a datum shift applies
   (the usual practice is to take the angles as they are) or which
   figure an area sum should reach.
3. **Treat cell order as a property and state it.** With one spatial
   dimension, which chunks a region needs is decided only by the order
   of cells. In the notebook the 4,718 cells in a box over Portugal span
   indices 411,173 to 512,751: 0.6% of the cells spread over 13% of the
   index range. Either keep the source order and record the grid
   identifiers (`uuidOfHGrid`, `number_of_grid_used`) so the grid file,
   and weights other people publish for it, still match by position; or
   reorder along a space-filling curve for locality and store the
   permutation. Both are defensible; an unstated order is not. For
   reduced Gaussian keep the GRIB order (rows north to south) and store
   the count per row, so a latitude band is one contiguous slice and a
   box is one short slice per row with no search. For HEALPix use nested
   order, where every chunk of 4^k cells is one parent cell.
4. **HEALPix is a DGGS: store ids and the system, not a mesh.** The
   draft's "no `mesh/` group" is right, but the positive half is
   missing. A `cell_ids` coordinate with `grid_name`, `level` and
   `indexing_scheme` (what xdggs decodes), the CF healpix grid mapping,
   and the zarr `dggs` convention together make the dataset usable by
   xdggs, healpy, healpix-geo and cdshealpix with boundaries, neighbours
   and coarsening computed. Latitude and longitude arrays are then
   redundant; keeping them is cheap and keeps the simple path uniform
   across families.
5. **Reduced Gaussian needs its name.** The grid name (for example
   O1280) and the per-row counts are the whole definition. With them,
   cells, bounds and weights are computable; without them a reader has
   to rediscover rows from the latitude array.
6. **Check the cross-group link in practice.** `mesh: /mesh/mesh` points
   out of the group that holds the data. In the notebook UXarray needed
   the mesh group opened separately and the field attached by hand, and
   the result came back on `n_face`, not `cell`. Setting the topology's
   `face_dimension` to `cell`, naming `latitude` and `longitude` as its
   `face_coordinates`, and testing that one call opens grid plus data
   would remove that step. Stating `start_index` explicitly, storing
   node coordinates as float64, and including `face_face_connectivity`
   (ICON's grid file has it) cost little.
7. **Consider CF bounds beside UGRID.** `latitude_bnds(cell, 3)` and
   `longitude_bnds(cell, 3)` duplicate each vertex about six times, but
   they are plain CF, they live on the same dimension as the data, and
   they are what CDO and ESMF-based tools read directly for
   unstructured data. If only one form is stored, UGRID is the better
   one; the question is whether the simple form is worth about 37 MB
   (float64, before compression).
8. **Nearest centre in degrees is not nearest on the ground.** The
   notebook's `NDPointIndex` selection measures distance in degrees. On
   a triangle grid that returns a different cell from the truly nearest
   one for about 10% of query points at 38 N, 21% at 60 N and 27% at
   70 N, always an adjacent cell and at most a few kilometres farther
   (`scripts/m35_nearest.py`, a synthetic equilateral lattice). That is
   harmless for smooth fields and visible at coasts and in mountains.
   The documented simple path should build the tree on unit vectors
   (x, y, z), which is a few more lines.
9. **Test a global grid before fixing the layout.** ICON-EU avoids the
   antimeridian and the poles. Global ICON, IFS and HEALPix do not, and
   that is where planar clipping of longitude and latitude polygons (the
   notebook's section 4c), bounding boxes and triangulated plots fail.
   The convention should be shown to work on one global case.
10. **Publish weights for the common move.** Most users want a regular
    longitude and latitude grid. A sparse weight table (row, column,
    weight, in the layout ESMF and SCRIP weight files use) for one or
    two standard targets turns regridding into a sparse product in any
    language, with conservative weights computed once by the producer.
    It is a few numbers per cell and it is data in place: nothing is
    resampled until someone asks.

Libraries worth testing against, beyond xarray and UXarray:

| Library | Why |
|---------|-----|
| xdggs | the DGGS path for HEALPix: decode, select by point or box, coarsen by level |
| healpy, healpix-geo, cdshealpix | HEALPix arithmetic on the sphere and the ellipsoid; the check that ids and level were written correctly |
| easygems | the nextGEMS helpers and the HEALPix attribute form already used for ICON output remapped to HEALPix |
| xESMF and ESMPy | conservative regridding from a mesh; the reference for published weights |
| CDO | reads centres plus bounds directly; `remapcon`, `sellonlatbox`; the tool much of the ICON community uses |
| earthkit-regrid | ECMWF's precomputed-matrix regridding and grid naming for reduced Gaussian and HEALPix |
| pyinterp | reduced Gaussian interpolation from parallels and counts, with index ranges for a box computed before any read |
| xugrid | the other UGRID reader for xarray; a second opinion on the mesh group |
| xpublish-tiles, gridlook | tile server and browser viewer that already take triangular, reduced Gaussian and HEALPix Zarr |
| GDAL multidimensional (osgeo.gdal) | reads the Zarr arrays and CF coordinates; shows what a non-Python consumer gets without mesh support |

## 6. What the layout means for bytes in place

A `cell` dimension is the plainest case for the reference-store work:
one array, one chunked axis, no pyramid. Three things follow.

- A row scheme gives byte ranges from geometry by arithmetic: the rows a
  box touches and a slice in each. This is pyinterp's `Zone`, and it is
  a planned extraction in the m31 sense with no index structure at all.
- A nested DGGS gives the same through the id: a region is a short list
  of id ranges, and a coarser level is a reduction over fixed groups of
  four, so overviews need no resampling kernel.
- An explicit mesh gives it only if the order has locality, which is
  point 3 above, or through a stored spatial index over chunks.

So the three families differ in the same way for I/O planning as they
do in section 2, which is the practical reason to keep the names apart.

## 7. Should wxylib build any of this now

No. The first slices (affine, rectilinear, curvilinear, references,
views) are where the current consumers are, and the guardrail asks
whether a piece is missing elsewhere before building it. For meshes and
DGGS the Python side is well served (UXarray, xugrid, xdggs, xESMF), and
the Rust side has the arithmetic crates. What is missing in Rust is the
thin layer between them and one data model, which is worth building only
when something of ours consumes it.

Two pieces are small, self-contained and line up with work already
planned, so they are the ones to pull forward when a trigger arrives:

| Piece | What | Size | Trigger |
|-------|------|------|---------|
| Mesh-to-grid weights | faces burned onto a regular grid by controlledburn, great-circle edges by bigcurve, emitted as a weight table, checked against ESMF | rwarp stage 5 as already planned in m21 (E5); an example and an oracle, no new crate | a published mesh store to run it on (the ICON-EU store leaving staging would do), or a request for weights |
| A HEALPix and a row `CellScheme` | `centre`, plus optional `parent`, `children`, `neighbours`, over cdshealpix; reduced Gaussian and L3 bins from a row table | a few hundred lines in a feature-gated crate | a DGGS store we want in the viewer or the planner (Destination Earth HEALPix Zarr), or the view planner reaching model grids |

Not before a consumer asks: a UGRID topology crate, mesh-to-mesh
regridding, a DGGS abstraction over several systems, any mesh writer.

## 8. Open

1. The doc 02 wording in section 2 (two kinds within R4, "explicit
   mesh" for R5): adopt, or keep one R4 row.
2. Whether the feedback in section 5 goes to the dynamical.org
   discussion as is.
3. Whether either piece in section 7 should be scheduled now rather
   than left to its trigger.
