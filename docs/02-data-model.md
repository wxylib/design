# 02: One data model, from raster to vector

Status: draft for review (gate 2)
Builds on: [01 module survey](01-module-survey.md) (M3, M14, M15, M16, M26)
and the gate 1 decisions recorded there. Section 10 adds context from
hypertidy/meshcore and CGAL.
Reads with: [regular-in-what](https://github.com/hypertidy/regular-in-what)
(the two questions, the ladder, the costumes) and
[playproj](https://github.com/hypertidy/playproj) (index space against the
sphere, model grids, tiles and overviews, rasterize).

## 1. The question

GDAL has three data models for gridded and mesh data, and a fourth for
features:

- **classic raster**: a 2D grid of bands with a six-number geotransform, plus
  side channels for geolocation arrays, GCPs and RPCs;
- **multidimensional** (`GDALMDArray`): named dimensions, indexing variables,
  attributes, groups;
- **MDAL meshes**, in a separate library: vertices, edges, faces and volumes,
  with datasets defined on each, over time;
- **OGR features**: one geometry and a row of attributes per feature.

Are these really different? This document argues that they are one model
that differs along a single axis: **how much has to be stored to say where
each element is**. That axis is the ladder in regular-in-what, extended past
"unstructured" into meshes and then features. The proposal is to make that
axis the organising idea of the core, so that a GeoTIFF band, a Zarr
variable, a ROMS grid, an MDAL mesh dataset, an L3 bin file and a polygon
layer are all the same kind of thing with a different position mapping.

## 2. Three separations, taken from regular-in-what

regular-in-what makes three separations that GDAL's models blur. The core
keeps all three apart.

1. **Index mapping**: how a position is worked out from an index. Regular,
   rectilinear, curvilinear, unstructured.
2. **Frame**: what the positions mean. A CRS, rotated longitude and latitude,
   scan angle, or no frame at all (index space only).
3. **Storage**: what a producer wrote down. Six numbers, 1D vectors or 2D
   arrays, in this frame or another one.

A grid is "regular *in a frame*". So the core never stores a bare
geotransform. It stores a mapping *and the frame that mapping is regular in*.

There is a fourth thing the book names as separate from both questions:

4. **Location on the cell**: centre or corner (PixelIsPoint and
   PixelIsArea), and for staggered and mesh data, which element a value
   lives on (node, edge, face, volume). This is a property of a variable, not
   of the grid.

## 3. The spectrum

Each row stores strictly more than the one above it, and every row can
describe everything above it, wastefully. "Kind" here is not a mode flag. It
is which position mapping a domain carries.

| Rung | Positions come from | Stored | Examples | GDAL today |
|------|--------------------|--------|----------|------------|
| R0 index only | nothing | 0 | PNG, raw binary | classic, no geotransform |
| R1 regular | arithmetic: origin, step (affine) | 6 numbers per 2D | COG, OISST once normalised, MODIS SIN tiles | classic geotransform |
| R2 rectilinear | outer product of 1D vectors | nx + ny | pressure levels, stretched grids, AVISO before normalising | mdim indexing variables |
| R3 curvilinear | a position per cell, still (i, j) indexed | 2 nx ny | ROMS, NEMO ORCA, VIIRS swath | classic geolocation arrays; mdim 2D coordinates |
| R3' fitted models | a fitted function of the index | a few dozen coefficients | GCP polynomials, RPC, TPS | classic GCP and RPC metadata |
| R4 implicit unstructured | arithmetic from a cell id, no (i, j) | 1 to a few numbers | L3 bins (`NUMROWS`), H3, S2, HEALPix | none |
| R5 explicit unstructured | per element positions plus connectivity | vertices and topology | UGRID, MDAL meshes, TINs | MDAL (separate), not GDAL |
| R6 features | a geometry per element, no shared topology | a geometry per row | points, lines, polygons | OGR |

Two observations make this one axis rather than four models:

- **R1 to R3 are one family.** Balaji's "logically rectangular": every cell
  is a box in index space. GDAL already moves between them: mdim's
  `GuessGeoTransform()` collapses R2 to R1, and `AsClassicDataset()` falls
  back to geolocation arrays (R3) when it cannot. regular-in-what's field
  guide goes further and collapses R3 to R1 *in another frame* (the cryptic
  curvilinear case).
- **R4 to R6 are one family too.** They drop the (i, j) index. A point layer
  is an R5 mesh with no connectivity. An R5 mesh dataset on faces is an R6
  polygon layer whose polygons share edges. L3 bins are R4 in storage and R6
  when materialised as rectangles. playproj's rasterize page is the same
  move in the other direction: an R6 polygon becomes an R1 field (centre-in)
  or an R1 coverage fraction (exact).

So the operations GDAL spreads across drivers and apps (normalise, warp,
rasterize, polygonize, extract, mesh to grid) are all **moves along this
axis, or between frames at the same rung**.

## 4. Core types

Rust-flavoured sketch. Names are placeholders; doc 03 names crates. Nothing
here depends on a CRS crate, a format crate or a geometry crate (decision D5
and the layer rule).

### 4.1 Dimensions and domains

```rust
/// A named axis of index space. Size may be unknown for streams.
struct Dim { name: String, size: u64 }

/// Where elements of a domain are. Index space plus how to place it.
struct Domain {
    dims: Vec<Dim>,
    /// Each mapping covers a subset of `dims` (x and y together, time on
    /// its own, a mesh element dim on its own). Dims with no mapping are
    /// plain index axes (band, ensemble member).
    mappings: Vec<Mapping>,
    /// Extra structure that index space does not carry (R4, R5).
    topology: Option<Topology>,
}
```

### 4.2 Mappings: the rungs

```rust
enum Positions {
    /// R1. One affine per group of dims; covers rotated and sheared grids.
    Affine { transform: Affine },                // 2D: the six numbers
    Regular1 { origin: f64, step: f64 },         // any single axis, eg time
    /// R2. One coordinate vector per dim.
    Rectilinear { coords: Vec<ArrayRef> },
    /// R3. One array per output coordinate, shaped like the dims.
    Curvilinear { coords: Vec<ArrayRef> },
    /// R3'. A fitted function (GCP polynomial, RPC, TPS).
    Fitted { model: FittedRef },
    /// R4. Positions by arithmetic from a cell id (L3 bins, DGGS).
    Scheme { scheme: SchemeRef },
    /// R5, R6. Positions of the elements: vertices, or geometries.
    Explicit { elements: ElementsRef },
}

struct Mapping {
    dims: Vec<usize>,        // which of the domain's dims this covers
    positions: Positions,
    frame: Frame,            // what the output numbers mean
    cell: CellConvention,    // centre or corner registration, edges n+1
}

/// A frame is opaque to the core. The CRS backend (see rust-proj-capability)
/// interprets it. `Index` means index space only.
enum Frame { Index, Crs(CrsDef), Other(String) }
```

The key property: **every `Positions` variant can answer "index to frame
position"**, and most can answer the inverse. That is exactly rwarp's
`Transformer` trait. An affine answers by arithmetic, a curvilinear grid by
lookup and search, a fitted model by evaluation, a scheme by its formula, a
mesh by point location. So the warp pipeline (survey M17 to M19) works
across the whole spectrum, not only on R1: `GenImgProjTransformer` becomes
"source mapping, then frame to frame, then inverse target mapping", with the
mappings supplied by the domains.

### 4.3 Topology, for R4 and R5

```rust
enum Topology {
    /// Connectivity listed explicitly, UGRID and MDAL style.
    Mesh { node_dim: usize, edges: Option<Conn>, faces: Option<Conn>,
           volumes: Option<Layered> },
    /// Connectivity computed from the scheme (neighbours of an L3 bin,
    /// an S2 cell's children).
    Implicit { scheme: SchemeRef },
    /// SGRID: how staggered (i, j) locations relate.
    Staggered { faces: Vec<usize>, nodes: Vec<usize>, padding: Padding },
}
```

Topology lives in an optional module (doc 03). The core type only carries a
reference to it, so a crate that handles R0 to R3 never compiles mesh code.

### 4.4 Fields: values on a domain

```rust
struct Field {
    name: String,
    dtype: DataType,               // survey M3: one shared vocabulary
    values: ValueSemantics,        // nodata, mask, scale and offset, units
    domain: DomainRef,             // shared between fields
    location: Location,            // Node, Edge, Face, Volume, Cell
    components: Option<usize>,     // index of a vector-component dim (u, v)
    source: SourceRef,             // where the numbers come from (section 5)
}

/// A set of fields and domains with attributes. Covers a classic dataset,
/// an mdim group, an MDAL mesh with its dataset groups, a feature layer.
struct Collection {
    fields: Vec<Field>,
    domains: Vec<Domain>,
    attrs: Attrs,
    children: Vec<Collection>,
    related: Vec<Relation>,        // overviews, staggered siblings, ...
}
```

`components` matters for the vector-quantity warps that rwarp already plans
for (`Transformer::jacobian`): a `(u, v)` field says so in its type, so a
warp can refuse to resample it as two scalars.

### 4.5 How each existing model maps onto this

| Existing model | As a Collection |
|---|---|
| Classic GeoTIFF, 3 bands | one Domain `(band, y, x)`, one Affine mapping on `(y, x)` with its CRS frame, `band` unmapped; one Field. Overviews are `related` Domains whose affine is scaled, not separate datasets. |
| Classic with geolocation arrays | Domain `(y, x)`, Curvilinear mapping whose coord arrays are Fields of the same Collection. |
| Classic with GCPs or RPC | Fitted mapping. |
| GDAL mdim / Zarr / netCDF variable | Domain from the dims; one mapping per indexing variable (Regular1 or Rectilinear) or per 2D coordinate pair (Curvilinear); CF or GeoZarr decides the frame. |
| CORDEX rotated pole | Affine mapping in the rotated frame. The 2D geographic arrays become a second, Curvilinear mapping on the same dims, kept for reference. A domain may carry more than one mapping in different frames. |
| ROMS | Domain `(eta, xi)` per stagger location, Curvilinear mappings, Staggered topology tying rho, u, v and psi together; vertical s-coordinate as a Fitted mapping on `(s, eta, xi)`. |
| MDAL mesh | Domain with a node dim (Explicit vertices) and Mesh topology. Each dataset group is a Field with a `time` dim and a Location (vertex, face, edge, volume); vector dataset groups set `components`. |
| L3 bin file | Domain with a `bin` dim, Scheme mapping (`NUMROWS`), Implicit topology. Stored bins are a sparse subset, so the source carries the bin numbers present. |
| H3, S2, HEALPix | as L3 bins, with a different scheme. |
| Feature layer | Domain with a `feature` dim, Explicit mapping to geometries (GeoArrow), no topology; attribute columns are Fields on that dim. |

One table, and none of the rows needs a mode flag.

## 5. Sources: plan, fetch, decode

Survey finding F5: async-tiff and zarrs both split "fetch encoded bytes" from
"decode". The core makes that split part of the source contract, rather than
hiding it behind a `read_window` call as `RasterIO` does.

```rust
trait ChunkSource {
    /// Chunking of the field's index space. Regular chunking is itself an
    /// R1 mapping, from chunk index to element index.
    fn chunk_grid(&self) -> &ChunkGrid;
    /// I/O bound, async. Returns encoded bytes; no decoding.
    async fn fetch(&self, keys: &[ChunkKey]) -> Result<Vec<Bytes>>;
    /// CPU bound, sync, can run on any thread or in wasm.
    fn decode(&self, key: ChunkKey, bytes: Bytes) -> Result<ArrayChunk>;
}
```

A read is then always three steps, matching rwarp's diagram:

1. **plan**: selection in index space to chunk keys (and, for a warp, target
   window to source window to chunk keys);
2. **fetch**: object_store, merged and scheduled across the whole plan;
3. **decode and compute**: kernels over decoded chunks.

Adapters: an async-tiff IFD and a zarrs array each implement `ChunkSource`
directly. A mesh or feature source from a non-chunked format (2DM, a
GeoParquet file) implements it with one chunk, or with row groups as chunks.
The GDAL workaround (survey D7) implements it with GDAL blocks as chunks.

The block cache (survey M16) then belongs to the fetch step, keyed by chunk
key, shared across fields and plans. It is not attached to a band.

## 6. Normalisation is an operation, not a reader side effect

GDAL's readers silently choose a rung: the classic netCDF driver collapses
evenly spaced 1D coordinates to a geotransform (good) and reports 2D
coordinates as geolocation arrays (wrong for cryptic curvilinear grids).

The core instead reads **what was stored** (the costume) and offers
normalisation as an explicit step that returns a new mapping and a report:

- R2 to R1: spacing within a stated tolerance (`IsRegularlySpaced`,
  `GuessGeoTransform`), with the observed deviation recorded. Float32
  coordinates need a tolerance (regular-in-what, figure on float32 steps).
- R3 to R1 in another frame: test candidate frames (the field guide's
  detection), record which frame and the deviation.
- R2 to R1 through a frame: AVISO's latitude vector is regular in Mercator y.

The original mapping is kept alongside, so nothing is lost and a user can see
why a grid was labelled what it was.

## 7. What is genuinely different between classic, mdim and mesh

Unifying the types does not remove every difference. The real ones are:

- **Shared versus per-variable domains.** Classic requires every band to
  share one domain. mdim and MDAL do not. The unified model allows sharing
  (`DomainRef`) without requiring it.
- **Overviews.** Classic has them natively, mdim and Zarr express them as
  multiscale conventions, meshes rarely have them. As `related` domains with
  a scaled mapping they are one concept.
- **Neighbourhood.** R1 to R3 get neighbours from index arithmetic. R4 gets
  them from the scheme, R5 from topology, R6 not at all. Algorithms that need
  neighbours (focal operations, contouring, mesh interpolation) depend on
  the topology module, and that dependency is visible in their signatures.
  meshcore (section 10) suggests this difference is smaller than it looks:
  one verb set answers neighbour questions on every rung, computed on some
  and stored on others.
- **Interpolation inside a cell.** On R1 to R3, bilinear in index space. On
  a mesh, barycentric on faces. On features, not defined. The resampling
  crate (gate 1, decision 2) takes a domain and dispatches on its rung.

## 8. Decisions, with rationale

**DM1. One Domain and Field model for classic, mdim, mesh and features,
distinguished by position mapping.**
- Get: one set of types, one set of bindings, one VRT scheme; moves between
  raster and vector are ordinary operations instead of format conversions.
- Cost: the model is more abstract than "a raster is a 2D array plus six
  numbers"; simple cases need a convenience API so they stay simple.
- Without it: four models with bridges between them, as in GDAL plus MDAL,
  and every operation written up to four times.

**DM2. A mapping always names its frame; a domain may carry several.**
- Get: "regular in EPSG:3412" is representable, rotated-pole and scan-angle
  grids keep their native frame, and the geographic arrays can ride along.
- Cost: readers must decide which mapping is primary, and the API must make
  that choice visible.
- Without it: the cryptic curvilinear problem is built into the core.

**DM3. Every mapping implements the rwarp `Transformer` seam (index to frame
and back).**
- Get: warping, source-window planning and extraction work on curvilinear
  grids, fitted models, schemes and meshes, not only affine rasters. rwarp's
  existing curvilinear and displacement-field plans fit without change.
- Cost: inverse mappings for R3 and R5 need search structures (a KD-tree or
  a mesh locator), which are real work and memory.
- Without it: warping stays an R1-only operation and everything else is
  first converted to geolocation arrays, as GDAL does.

**DM4. Read what was stored, then normalise explicitly, with a report.**
- Get: no silent mislabelling, recorded tolerances, reproducible decisions,
  and the regular-in-what field guide becomes code.
- Cost: users with simple data must call one more function, or accept a
  default policy that does it for them.
- Without it: the label a grid gets is decided by whatever the producer
  stored and whatever the reader guessed.

**DM5. Value location and vector components are part of a Field.**
- Get: staggered grids, mesh datasets on faces or vertices, PixelIsPoint, and
  `(u, v)` fields are typed, so a warp can do the right thing or refuse.
- Cost: more fields in every type; adapters must fill them in from
  conventions that are often missing or wrong.
- Without it: half-pixel shifts and unrotated velocity vectors stay silent
  errors.

**DM6. The source contract is plan, fetch, decode, with chunking in index
space.**
- Get: async I/O scheduled across a whole plan, decode in parallel or in
  wasm, one cache keyed by chunk, and direct alignment with async-tiff and
  zarrs.
- Cost: a synchronous convenience layer is needed for scripts and bindings;
  non-chunked formats need a trivial one-chunk adapter.
- Without it: we rebuild `RasterIO` and the per-band block cache.

**DM7. Topology and geometries are optional modules; the core depends on no
CRS, format or geometry crate.**
- Get: the R0 to R3 path stays small and builds for wasm; mesh and feature
  support can grow at their own pace.
- Cost: an extra crate boundary at exactly the place where raster and vector
  meet, which needs careful design in doc 03.
- Without it: every user of a COG pulls in mesh and geometry code.

**DM8. Conventions (CF, GeoZarr, GeoKeys, UGRID, MDAL formats) are adapters,
and use existing crate support where it exists.**
- Get: conventions change without touching the core, and gate 1's "defer to
  existing crate support" is respected.
- Cost: some conventions will be partially supported until a crate covers
  them.
- Without it: convention parsing leaks into the core types, as frame
  inference does in GDAL's netCDF driver.

## 9. VRT, classic and multidimensional, as one scheme

With one model, a virtual dataset is a Collection whose Field sources are
other Fields plus an operation. The operations are few:

- **select**: a window or slice in index space (VRT SimpleSource, mdim view);
- **remap**: a change of domain through mappings (warped VRT, mdim
  reproject, mesh to grid);
- **combine**: mosaic along existing dims, or stack along a new dim (VRT
  mosaics, mdim concatenation, GTI);
- **compute**: per-element functions (pixel functions, scale and offset,
  expressions).

Because each operation knows its input and output domains, a virtual
Collection can be planned (which chunks of which sources), costed and
serialised before any data is read. That serialisation is the VRT
replacement. Its file format is a doc 03 question; the operations are what
this document commits to.

## 10. Context from meshcore and CGAL (not decisions)

Read after the draft was written, for context only. Nothing here changes the
proposals above; it points at where they could go further.

### hypertidy/meshcore

[meshcore](https://github.com/hypertidy/meshcore) (R, prototype, read at
`7e577dc`) runs one verb set over a regular grid (GRID), a HEALPix discrete
global grid (CELL) and, through silicate's `silicate2` branch, UGRID meshes.
Four of its ideas fit this model directly.

- **One verb set across rungs.** `cells()`, `boundaries()`, `vertices()`,
  `edges()`, `face_edge()`, `neighbours()`, `parent()`, `children()` and
  `join_array()`. Only `cells()`, `boundaries()` and the hierarchy are
  written per model; edges and neighbours are one generic implementation on
  integer vertex keys. In this document's terms, the Topology module (4.3)
  is not only for R4 and R5. Every rung from R1 to R5 can answer the same
  verbs: R1 and R4 compute them from the index or cell id, R5 reads them
  from storage. That is a candidate trait surface for the topology module.
- **The identity ladder.** Whether two vertices are the same is a level a
  model records, not a fact about the data: lattice (same key computed from
  the cell id), exact, snapped, noded, exact predicates (CGAL). It is a
  second axis, orthogonal to the position ladder in section 3. The position
  ladder says *where* an element is; the identity ladder says *which
  elements are the same*. It matters most at R5 and R6, where shared
  boundaries are found rather than given.
- **Keyed dimensions with a binding rung.** An array joins to a model's
  entities by a keyed dimension, with no geometry: computed (GeoTIFF
  `row * ncol + col`), stored (xdggs `cell_ids`) or positional (UGRID
  `n_face`). The binding records how it was decided: declared, ugrid
  attributes, name, or size. This is `Field.location` plus a domain dim,
  and the binding rung belongs in the same report as normalisation (DM4).
- **A written mesh spec.** meshspec v0.1 defines three forms as Arrow
  tables (PSLG, triangle mesh, drawable mesh) with settled decisions on
  index base, winding and provenance. For R5 wire formats it is an existing
  spec to adopt rather than a new one to invent, and it sits naturally
  beside GeoArrow (gate 2, question 4).

meshcore's MDAL findings also support DM8 (conventions as adapters): MDAL
and GDAL multidim agree exactly when both read a UGRID file, but MDAL loads
no edges for 2D meshes and can silently return the wrong mesh. The model
should own the entity tables, with MDAL as one reader among several and a
key-agreement check as validation.

Two of meshcore's open questions are this document's too: GRID hierarchy
(2 x 2 blocks against GDAL's same-extent overviews, which is the `related`
domains question in section 7) and 64-bit cell ids for DGGS at fine levels.

### CGAL

From general knowledge of CGAL's design, not from reading its source for
this document. Three of its ideas are relevant.

- **Kernels separate predicates from constructions, and exactness is a
  parameter.** The same algorithm runs with floating point filters or exact
  arithmetic. That is the top rung of meshcore's identity ladder, and it has
  the same shape as the CRS decision (D5): the core names the operation, a
  backend decides how exactly it is done.
- **Combinatorial maps and linear cell complexes** describe topology in any
  dimension with one structure (darts and their links), with attributes
  attachable to cells of any dimension. That generalises `Location` (node,
  edge, face, volume) to "a cell of dimension i, for i from 0 to d", and
  covers layered 3D meshes without a special case.
- **Generic programming by concept and model.** Algorithms are written
  against concepts (traits) and any data structure that models the concept
  can be used. meshcore's verbs and this document's `Positions`
  implementing `Transformer` are the same idea. In Rust, traits are the
  natural form.

Rust already has pieces at this level: `spade` 2.15 (Delaunay and
constrained Delaunay, the engine under hypertidy/trowel), `cdt` 0.1,
`robust` 1.2 (adaptive exact predicates), `h3o` 0.11, `healpix` 0.3, `s2`
0.2 and `geo-index` 0.4. None of them shares a cell or topology model with
the others, which is the gap this document's Topology module would fill.

## 11. Questions for gate 2

1. **The spectrum as the core.** Is the R0 to R6 ladder the right organising
   axis, including R3' (fitted models) and R4 (schemes such as L3 bins and
   DGGS) as rungs of their own?
2. **Multiple mappings per domain (DM2).** Should a domain keep every mapping
   it was given (native and geographic), or keep one primary mapping and
   discard the rest after normalisation?
3. **Normalisation default (DM4).** Should readers return the stored costume
   and leave normalisation to the caller, or apply a conservative default
   (R2 to R1 within float32 tolerance) and report it?
4. **Feature geometries (R6).** Use GeoArrow as the geometry representation
   for R6, or keep the core geometry-agnostic and let each adapter choose?
5. **First slice.** Which rungs should the first implementation cover? My
   suggestion is R0 to R3 (COG and Zarr through async-tiff and zarrs, with
   rwarp), then R5 meshes, then R4 and R6.
