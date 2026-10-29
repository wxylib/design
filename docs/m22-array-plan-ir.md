# m22: An array plan IR beside wxylib: what ArrIR's ideas need from us

Status: musing, 2026-10-29. Reads charles-turner-bot/ArrIR at main
`82f5a19` (the merged extraction contract, `plans/design.md` and
`plans/chunked-layout.md`) and its open design PRs #20, #21 and #22
(`plans/grids.md`, `plans/warp.md`, `plans/cast.md`), against
wxylib/core at `caba7b2` and design docs 02, m07, m09, m11, m16, m20 and
m21. ArrIR and wxylib are developed independently; this note is
wxylib's side of a later comparison, not a proposal to either repo.
Figure: [img/m22-layers.svg](img/m22-layers.svg).

## Summary

The question: what are the most abstract ideas in ArrIR, how would they
sit in wxylib, and does taking them on mean a large refactor, or are the
pieces nearly there?

- **ArrIR is a logical plan layer.** A plan is a value: a linear chain
  of unary operations (`Open -> Select -> Reduce -> Warp -> Cast`) over
  a dataset named by a binding and described by a declared schema. Each
  operation states its effect on the schema and, later, its footprint.
  Adapters lower host calls into the chain or emit the chain to a host,
  and reject what they cannot express exactly. A separate storage layout
  (byterefs, the flat mdim-refs/0.2 form) says what is on disk, and a
  physical planner combines the two into chunk keys and byte ranges.
- **wxylib already has the two lower thirds and none of the top.** The
  physical plan exists as `Explain` (chunk keys in fetch order, bytes,
  cache hits) behind every `--dry-run`. The layout exists as wxy-refs,
  a second Rust reader of the same flat form. The movement layer (rwarp,
  controlledburn, bigcurve) is the executor ArrIR's `Warp` would lower
  to. What wxylib lacks is a composed logical plan: each verb builds its
  own physical plan straight from options and a source.
- **The nine purity rules are already wxylib rules, under other names.**
  Seven hold today (section 3). The two that do not are where wxylib
  makes a choice ArrIR forbids: planning reads coordinate arrays, and
  GDAL-parity mode estimates a kernel scale per chunk instead of stating
  it.
- **The grid model is the real difference.** wxy-domain evaluates
  positions (rungs R0 to R6, coordinate values held, trait objects for
  the open rungs, several mappings per domain with normalisation
  reports). ArrIR's grid is a schema entity that names coordinate
  variables and never holds them, with five staggering positions per
  axis. They agree on more than they differ (corner-anchored GDAL
  affine, declared regularity, one variant per kind), and each has
  something the other lacks (section 4).
- **No large refactor.** Taking the ideas on is one new layer on top and
  two small changes below it: a serialisable value form of a wxy-domain
  description, and the m09 registry's smallest step (each verb's options
  as an operation struct). Readers, refs, cache, warp kernels and the
  movement layer do not change (section 6).
- **The comparison needs a shared artefact more than shared code.** The
  cheapest useful step is for `wxy --dry-run` to print the logical chain
  it ran alongside the physical plan, so the same job can be written in
  both representations and diffed. Comparison points for the later
  merge plan close the note (section 8).

![Three layers: logical plan, storage layout, physical plan, with
ArrIR's crates and wxylib's pieces placed on each](img/m22-layers.svg)

## 1. ArrIR's ideas, from most to least abstract

1. **Plans are values, not calls.** Serialisable, versioned, no host
   objects; importing a plan never executes or resolves it.
2. **Name data by binding, not location.** `Open { binding, schema }`
   starts every plan. Mapping a binding to a URI, a refs table or an
   in-memory array happens outside the plan, so a plan validates
   offline. Warp targets that are data (a tripolar grid, a mesh) arrive
   the same way, as a `GeometryBinding` with a declared schema.
3. **Three things, generic at different levels.** Logical plan (what to
   compute), storage layout (what is on disk), physical plan (which
   chunks and byte ranges). The logical plan never sees a byte
   reference, and the crate graph enforces it.
4. **Effects and footprints per operation.** Effects say what an
   operation does to dimensions (preserved, resized, consumed), so a
   schema propagates along the chain without data. Footprints say which
   input region an output region needs, which is what physical planning
   and sound rewrites rest on.
5. **No silent approximation.** An adapter emits an equivalent operation
   or returns an error. Unknown facts block rewrites; they are not zero.
6. **Semantics defined on their own terms.** Resampling methods, mode
   ties, kernel widening, edge rules, empty-cell values and type
   conversion are defined in the IR and checked by hand-worked fixtures,
   not by what one engine does. GDAL is one adapter.
7. **Grids are schema entities.** A grid owns its dimensions, CRS and
   model (affine, rectilinear, curvilinear); variables refer to it, with
   a staggering position per axis (centre, left, right, inner, outer).
   Meshes, DGGS and N-D grids are sketched variants, so adding them adds
   a variant rather than changing one.
8. **Rewrites over one algebra.** Selection and rechunk pushdown first,
   with a termination measure; no second optimiser IR.
9. **Growth by small reviewable steps.** Linear chains before graphs,
   binary operations only when a concrete use earns them.

## 2. Where each idea lands in wxylib

| ArrIR idea | wxylib piece | State |
| --- | --- | --- |
| Logical plan, linear chain | none; each verb plans alone | missing |
| `Open { binding, schema }` | verb input path plus the reader's `Domain` | near: a schema exists, but not as a value |
| Storage layout (byterefs) | wxy-refs `from_refs_table`, `RefsStore` | have: second reader of the same form |
| Physical plan | `Explain`, `--dry-run` JSON | have, and measured against GDAL |
| Footprint of `Select` | `ChunkGrid::plan(window)` | have |
| Footprint of `Warp` | `wxy_warp::plan` source window, rwarp's chunk planner | have, for affine and curvilinear sources |
| Regridding weights as physical output | m20 section 8, rwarp weights, `wxy weights` | planned in m20 and m21 |
| Effects, schema propagation | none; one operation per run | missing, small |
| Adapters with rejection | GDAL oracle tests show parity, not rejection | partial |
| Methods defined in the IR | `WarpOptions` follows gdalwarp names and quirks | different stance (section 5) |
| Grids with CRS and staggering | wxy-domain `Mapping`, `Positions`, `Frame`, `Location` | have, different shape (section 4) |
| Meshes, DGGS as later variants | rungs R4, R5, R6 as trait-object variants | have, same extension story |
| Rewrites | none; the warp window is a pushdown done by hand | missing, not needed yet |
| Operation catalogue | m09 registry sketch | planned, not started |

The verbs wxy has today, written as ArrIR chains:

- `wxy warp` is `Open -> Select (leading slices, a window) -> Warp ->
  Cast`. gdalwarp's convert-at-the-end is exactly `Cast(Warp(x))`, and
  wxy's batching of leading slices is the physical plan of the `Select`.
- `wxy points` is a pointwise selection (nearest) or a warp to a target
  of points (bilinear, cubic). ArrIR lists pointwise selection as an
  open question; a list of points as a `GeometryBinding` target is the
  answer that needs no new operation.
- `wxy zonal` is a grouped reduction whose groups come from an external
  binding (the polygons), with coverage weights from controlledburn. That
  is ArrIR's roadmap step 4 (contextual reductions with explicit
  bindings), and its weights have the same shape as regridding weights.
- Building refs stores (wxy-virtual, and producers outside wxylib) is
  layout work, not planning.

## 3. The purity rules, held against wxylib

| Rule | wxylib today |
| --- | --- |
| 1. Planning reads no data chunks | Holds for chunks. Curvilinear planning reads the coordinate arrays (`SourceGrid::from_domain`), which ArrIR treats as variables. |
| 2. Plans, schemas and demands are values | `Explain`, `GridSpec`, `WarpOptions` round-trip through serde; a plan is rebuilt from them, not deserialised. `Domain` is not serialisable (trait objects). |
| 3. Effects and footprints | Footprints yes (windows, chunk planner); effects not stated, since nothing composes. |
| 4. No silent approximation | m11's whole subject. One exception: `kernel_scale: None` estimates per chunk, as GDAL does. |
| 5. Physical planning in index space | m07 and m20 section 2.2: index space is the seam. |
| 6. No I/O or async in the core | wxy-domain and the movement layer hold; I/O lives in wxy-source and up. |
| 7. Determinism | `Explain` lists keys in fetch order; tests pin it. |
| 8. Regularity declared, never inferred | Doc 02 section 6: normalisation is an operation with a report, and the stored mapping is kept. |
| 9. A chunk key names the same bytes | m05 cache keys (source, offset, size) plus etag; m16's review adds in-place source changes as the case to guard. |

The two exceptions are deliberate. Reading coordinate arrays at plan time
is what makes a curvilinear warp plannable at all; ArrIR's equivalent is
a label-resolution step between the logical and physical plans, which
reads the same arrays under another name. The estimated kernel scale is
GDAL parity, and m20 already moved wxylib towards stating it (the
`kernel_scale` option exists because the estimate varies by chunk). In
an IR, a parity adapter would emit the stated scale it chose, or reject.

## 4. Two grid models

| | wxy-domain | ArrIR (`grids.md`, proposed) |
| --- | --- | --- |
| Unit | `Domain` (ordered dims) plus any number of `Mapping`s, one primary per dim | dataset schema with named `Grid`s; a variable refers to one grid |
| Affine | `Positions::Affine`, GDAL order, corner-anchored, dims `[row, col]` | `GridModel::Affine`, GDAL order, corner-anchored, `column_dim`, `row_dim` |
| Rectilinear, curvilinear | coordinate values held in the mapping | coordinate variables named, values held elsewhere |
| Where coordinates sit | `CellConvention::{Centre, Edge}` | `AxisPosition::{Centre, Left, Right, Inner, Outer}` per axis |
| Where values sit | `Location::{Cell, Node, Edge, Face, Volume}` | `GridPlacement` with a position per axis; `MeshLocation` for meshes |
| Pixel meaning | implied by `CellConvention` | `PixelInterpretation::{Area, Point}`, separate from the transform |
| CRS | `Frame::{Index, Crs(String), Other(String)}`, opaque | `Crs { definition, axis_order }`, verbatim, equal only as text |
| Fitted (GCP, RPC) | rung R3', `FittedModel` trait | open question |
| DGGS, meshes | R4 `CellScheme`, R5 `Elements` traits | sketched `Dggs`, `Mesh` variants with fields |
| Features | R6 | out of scope |
| Several placements of one domain | yes, with provenance and a normalisation report | no: one model per grid |
| Vector components | `Field.components`, so a warp rotates `u`, `v` | none |
| Missing values | `ValueSemantics { nodata, scale, offset }` | `MissingValues::{Known, Unknown}`; packing not designed |

What each could take from the other:

- **wxylib from ArrIR: the staggering vocabulary.** Five positions per
  axis say what two cell conventions and a location cannot: an Arakawa
  C grid's `u` and `v`, NEMO's upper-face convention, bounds as the
  `Outer` position with `N + 1` points. wxy-domain's `Location` was
  written for meshes and reads awkwardly on staggered grids. Adopting
  `AxisPosition` is additive for R2 and R3.
- **wxylib from ArrIR: name coordinates, do not hold them.** A value
  description that refers to coordinate variables serialises without
  carrying 200,000 numbers, which is what rule 2 needs. wxy-domain can
  keep evaluating positions; the description and the evaluated mapping
  become two types, the first converting into the second when the
  coordinates are read.
- **wxylib from ArrIR: `PixelInterpretation` and `axis_order` as
  explicit fields,** both cheap and both places a CRS goes silently
  wrong.
- **ArrIR from wxylib: several mappings per domain.** A grid stored as
  curvilinear lon/lat that is regular in polar stereographic (doc 02
  section 6) has both, and keeping the stored one with a report is what
  makes normalisation honest. One model per grid forces a choice.
- **ArrIR from wxylib: the rung ladder up to features,** and the
  `Fitted` rung for GCPs and RPCs (its question 3).
- **ArrIR from wxylib: vector components.** A warp of `u`, `v` that
  does not rotate them is a silent approximation by ArrIR's own rule 4.

## 5. Warp, three ways

ArrIR's proposed `Warp`, wxy's `WarpOptions` and rwarp's kernels describe
the same operation from three directions.

- **Already aligned:** a stated kernel widening factor
  (`KernelScaling::Widen` and `kernel_scale`), mode tie rules (`ModeTie`
  and `mode_ties`), the approximate transformer's `error_threshold`, the
  type conversion after the warp, and weights as a physical-plan output
  computed with no data read (`warp.md`, Footprint; m20 section 8).
- **ArrIR states what wxy leaves to GDAL:** a method per variable (wxy
  has one per run, as gdalwarp does), `EdgeRule` for grids without bounds
  (wxy's curvilinear path implies edges between centres, as gdalwarp's
  geolocation transformer does), and a required `empty_value`.
- **wxy states what ArrIR does not yet:** `wrap_globe` for global
  lon/lat sources, the overview level (`-ovr`), the working-memory limit
  (which changes GDAL-mode output), and `Footprint::{Box, Exact}`, the
  difference between gdalwarp's `average` and a conservative mean that
  ArrIR's question 2 records.
- **Edge shape is bigcurve's subject.** `EdgeShape::{StraightInIndex,
  StraightInLonLat, GreatCircle}` is exactly the question bigcurve-rs
  answers by densifying: which space a cell side is straight in. m19's
  densify measurements and m21's spherical measure are wxylib's evidence
  for that field.

ArrIR's stance that methods are defined on their own terms and GDAL is
one adapter is the same stance m20 takes for rwarp ("GDAL parity as its
floor"). The difference is order: wxylib reached it from parity, ArrIR
starts from it. The hand-worked reference fixtures ArrIR plans (4 x 4
onto 2 x 2, octants of the sphere) are what wxylib/fixtures lacks; the
GDAL and ESMF oracles wxylib has are what ArrIR's adapters will need.

## 6. What adopting the ideas would cost

**Changes below the new layer, both small:**

1. A value form of a domain description in wxy-domain: serde types for
   dims, affine, named coordinate variables, staggering positions, CRS
   and axis order, with a conversion into today's evaluated `Mapping`.
   The trait-object rungs get value forms when their first reader lands
   (a GCP list, a DGGS system name and level). A few hundred lines; no
   reader changes, since readers already build a `Domain`.
2. m09's smallest step: each verb's options as one serde type in the
   library crate. `WarpOptions` and `PointOptions` are most of the way.

**The new layer:**

3. A logical chain (`open`, `select`, `warp`, `cast`, and for zonal a
   grouped reduce) that each verb records as it plans, printed by
   `--dry-run` beside `Explain`. About 200 lines, with no change to what
   runs. This is the comparison artefact.
4. Later, and only if wanted: planning from a chain rather than from
   flags. Each operation's footprint already exists inside a verb, so
   this is rearrangement, not new mathematics.

**Untouched:** wxy-source, wxy-tiff, wxy-zarr, wxy-refs, wxy-cache,
wxy-virtual, the movement layer, the CLI surface, the bindings.

**What we get.** A plan a user, a binding or another project can read,
store and diff; a direct comparison with ArrIR for the same job; and a
place for multi-step jobs (select, warp, reduce) that today need several
runs and intermediate files.

**What it costs.** Mainly design attention: a second description of a
grid alongside the evaluated one, kept in step; and the temptation to
grow a full IR inside wxylib, which would duplicate ArrIR rather than
compare with it. Item 3 is the cap until the comparison is made.

**What if we didn't.** wxylib stays a set of verbs with good physical
plans, which is fine for the CLI. The comparison would then be prose
against ArrIR's types, and any later merge would start by inventing the
logical chain wxylib never wrote down.

## 7. Three ways to relate the two, later

- **wxylib as an ArrIR executor.** ArrIR holds the logical plan and
  layout binding; wxylib is an emit target whose physical planner and
  kernels run it. The cleanest split, and close to how both are drawn.
  It ties wxylib's plan types to another repository's pace.
- **Shared lower crates, separate plans.** One byterefs reader, one
  hand-worked warp fixture suite and one grid-description crate, used by
  both; each keeps its own plan layer. Less coupling, some duplication
  at the top.
- **Independent, with a converter.** Each keeps everything; a converter
  maps chains both ways and the shared fixtures prove they agree. The
  cheapest start, and where section 6 leaves things.

These are for the comparison to choose between, not this note.

## 8. Comparison points for a merge plan

1. **Grid description.** wxy-domain's evaluated `Mapping` against
   ArrIR's `Grid` that names coordinate variables. Likely outcome: one
   value description, both evaluating it their own way.
2. **Staggering.** `AxisPosition` against `CellConvention` plus
   `Location`. wxylib should probably adopt ArrIR's form for structured
   grids.
3. **Several placements and normalisation reports.** Present in wxylib,
   absent in ArrIR; test with an R3 grid that is R1 in another CRS.
4. **CRS.** Verbatim text with explicit axis order, against `Frame`. Both
   avoid parsing; ArrIR's question 2 (WKT2 or PROJJSON) and wxylib's CRS
   backend question (proj4rs, terrio-crs) meet here.
5. **Vector components and rotation** in a warp.
6. **Warp options.** Per-variable methods, `EdgeRule`, `EdgeShape` and
   `empty_value` against `wrap_globe`, overview level, memory limit and
   `Footprint`. Each side lists what the other omits.
7. **Weights as a value.** ArrIR's footprint section and m20 section 8
   describe the same (target, source, weight) table; agree one schema
   and its ESMF view.
8. **The byterefs reader.** `arrir-layout` (proposed) and wxy-refs
   (working) read the same flat form. wxy-refs has no check that every
   grid cell has a row, which ArrIR's binding makes an error; that rule
   came from m15 and m17. One crate, its validation list taken from
   ArrIR's, its tests from wxylib's live stores.
9. **Points and zonal as operations.** Pointwise selection, a warp to a
   point target, and grouped reductions over a polygon binding, against
   ArrIR's open questions and roadmap step 4.
10. **Coordinates at plan time.** wxylib reads them while planning;
    ArrIR resolves them in a step between logical and physical plans.
    Agree what that step is called and what it may read.
11. **Physical plan.** wxylib's `Explain` (keys in fetch order, decoded
    and stored bytes, cache hits) against ArrIR's planned request lists
    and demands. `Explain` is the measured one and a candidate seed for
    `arrir-physical`.
12. **Fixtures.** ArrIR's hand-worked warp fixtures, wxylib's GDAL and
    ESMF oracles and live-store hashes: one suite both run.
13. **Dataset or array.** ArrIR's `Open` binds a dataset and projects a
    variable; wxy verbs take one array with leading dims. A chain over
    a dataset is the bigger change for wxylib.
14. **Rewrites.** wxylib has none, but its warp window is a selection
    pushed below a warp by hand. Test ArrIR's pushdown rules against
    the windows wxy computes.
15. **Extension story.** Rungs as trait-object variants against grid
    kinds as sketched enum variants. Both promise the same thing (a new
    kind adds a variant); compare how each stays serialisable.

## 9. Not claimed

- ArrIR's grids, warp and cast documents are open proposals; any of the
  shapes above can change.
- The line counts in section 6 are estimates from the size of
  wxy-domain (about 1,050 lines) and `explain.rs` (257), not built.
- The wxy-refs observation in point 8 comes from reading the source, not
  from a failing test.
