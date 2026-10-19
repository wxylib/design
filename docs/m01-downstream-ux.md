# m01: Downstream UX, blue sky

Status: musing. Not a plan, not a gate, not a commitment. Nothing here is
scheduled and nothing here changes docs 01 to 03. It exists so that early
choices in the core can be checked against where the pieces might one day
be used, including the idea that QGIS could itself be a more modular set
of resources.

The "m" series sits beside the numbered, gated documents. A musing becomes
work only by being picked up into a numbered document and passing a gate.

## 1. The thought

wxylib takes the modules implicit in GDAL and gives each its own home. The
same move can be imagined one level up, for the applications that sit on
GDAL. QGIS is the obvious one: a desktop GIS that is, underneath, a large
collection of genuinely useful resources:

- a project file that says which sources, in which order, with which styles
- a data source manager and browser
- a map canvas that reprojects and renders on the fly
- a CRS picker and transformation chooser
- a style system (renderers, colour ramps, labels; QML and SLD files)
- an expression engine
- the Processing framework: hundreds of algorithms, each with typed
  parameter descriptions, also runnable headless through `qgis_process`
- a temporal controller, mesh layers (through MDAL), point clouds (through
  PDAL), print layouts, a plugin ecosystem

QGIS already splits these into libraries (core, gui, analysis), but they
live inside one C++ and Qt object model. To use the Processing catalogue
you run QGIS, headless or not. To reuse a style you need something that
reads QML. To see what a project file shows, you open it in QGIS.

The blue-sky question: what would it look like if each of those were a
resource in its own right, with a plain description that many front ends
can evaluate, the way a COG is a resource many readers can open?

wxylib would not build that. The point of the musing is to notice which
of those resources fall naturally out of the core's design, which belong
to adjacent efforts, and which doors the core should avoid closing.

## 2. Musings

Each is short. "Rests on" names what in the current design it would need;
"prior art" names what already exists and should be joined, not repeated.

### 2.1 Rendering is warping to a screen grid

A map canvas is a target grid: R1, in a screen or web-map frame, with a
size in pixels. Drawing a layer is plan (which source chunks, which
overview level), fetch, warp, then colour. That is exactly rwarp's
browser app and S4's pipeline, with a colour step at the end.

If that holds, "a renderer" stops being a component of a GIS and becomes
a function anyone can call: a browser canvas, a Jupyter cell, an R
graphics device, a terminal with sixel graphics, a tile server, a QGIS
layer. All draw the same pixels, because they run the same plan.

- Rests on: the plan, fetch, decode separation; `wxy-warp`; the wasm build.
- Prior art: deck.gl-raster, titiler, lonboard (DevSeed), MapLibre.
  wxylib's addition would be the exact warp and the domain model, not a
  renderer.

### 2.2 Plans as something a user can see

Every view has a cost before any pixel moves: how many requests, how many
bytes, which overview, which chunks, how much of each chunk is wasted. The
core already computes this, so a front end could show it: a "dry run"
panel, an EXPLAIN for maps. Pan the view and watch the chunk footprint
move across the source's index space.

This is the UX payoff of separating planning from computing. It is also a
teaching tool: most of the confusion about COG overviews, Zarr chunking
and polar reprojection disappears once you can see the footprint.

- Rests on: serialisable read plans (`wxy-source`), rwarp's window planning.
- Prior art: rwarp's browser app, which already plans before it fetches;
  SQL EXPLAIN as the interaction model.

### 2.3 An inspector that draws the domain

`wxy info` as a picture. Show a source in index space and in its frame
side by side: the grid lines of a curvilinear model bending, the cells of
a rectilinear axis stretching, a DGGS cell's neighbours, a UGRID mesh's
faces. Label the rung (R0 to R6) and the cell convention. Show what
normalisation would do and what it reports.

This is the data model from doc 02 made visible, and it belongs in the
docs repo as much as in any app: explainers that are live inspectors of
real files.

- Rests on: `Domain`, `Mapping`, the normalisation report.
- Prior art: regular-in-what's field guide; playproj.

### 2.4 One operation catalogue, many surfaces

The Processing toolbox's real asset is not the dialogs but the
descriptions: name, typed inputs, typed outputs, defaults. If wxylib's
operations (normalise, warp, rasterize, polygonize, regrid, mesh to grid,
all "moves along the spectrum" in doc 02) carried one machine-readable
description each, then the CLI flags, the Python and R function
signatures, a GUI form, a web form, an OGC API Processes endpoint and an
agent's tool list could all be generated from it.

Typed by rung, a catalogue could also say what applies: "this source is
R3, so these operations accept it; warp will need an inverse mapping."
QGIS knows a layer is a raster or a mesh; the spectrum knows more.

- Rests on: operations as plain functions over domains and fields; a
  schema per operation (not designed, and not needed until several
  surfaces exist).
- Prior art: openEO process descriptions and process graphs; OGC API
  Processes; QGIS's own parameter definitions; JSON Schema.

### 2.5 The map as a document

A QGIS project file is a description of virtual data plus a view plus
styles, which only QGIS fully evaluates. The core's virtual scheme (S7)
already aims to describe sources, selections, combinations and
computations. Add a view (a target grid, or a set of them) and a style,
and the result is a "map document" that a CLI could render to a file, a
browser could pan, a notebook could embed, and a desktop app could open.

The caution is that this is where projects invent formats. The musing is
to compose existing specs (a virtual Zarr or icechunk store for data, a
MapLibre style or a similar spec for appearance, a STAC item for
discovery) and contribute a thin view layer only if nothing fits.

- Rests on: S7; virtualisation as the default pathway (README).
- Prior art: MapLibre style spec, Vega-Lite (grammar, not app), kepler.gl
  configs, Felt, QGIS project files themselves.

### 2.6 Styles and value semantics as data

Nodata, scale and offset, categories and their labels, valid ranges and
units are data model concerns, already carried by fields. A colour map is
one step further. If those travelled with the data in a plain form, the
same layer would look the same in QGIS, matplotlib, ggplot2, MapLibre and
a terminal, and the style would be versioned with the data instead of
inside a project file.

- Rests on: value semantics in `wxy-domain`.
- Prior art: SLD and SE, MapLibre styles, CF `flag_values` and
  `flag_meanings`, cmocean and viridis palettes, STAC's classification and
  raster extensions.

### 2.7 A dimension navigator, not a time slider

QGIS's temporal controller is about time. The data model has dimensions:
time, depth, pressure level, ensemble member, band, wavelength. A front
end could generate its navigation controls from the domain itself: a
slider for an ordered dimension, a picker for a categorical one, a
labelled axis for a rectilinear one with uneven steps. The same code
serves a sea surface temperature series and a hyperspectral cube.

- Rests on: `Dim` and R2 mappings carrying labels and order.
- Prior art: xarray's repr and hvplot widgets; mdim in GDAL; the QGIS
  temporal controller as the case to generalise.

### 2.8 QGIS as a consumer, not a rival

The most grounded musing: QGIS could use wxylib pieces without anyone
rewriting QGIS. A Python plugin over `wxy-py` could add a layer type
backed by a virtual store, a warp plan or a mesh-to-grid operation, and
Processing algorithms generated from the catalogue in 2.4. A C ABI
(doc 03, section 5) would allow a native data provider later. Mesh
support in QGIS already comes through MDAL, which is the concept doc 01
folded into the spectrum, so there is a natural meeting point.

The reverse also holds: QGIS's CRS picker, expression engine and style
editor are mature, and a modular world would let other tools borrow them
rather than redo them. That is QGIS's call, not ours; the musing is only
that the core should not make it harder.

- Rests on: S6 bindings; the C ABI and Arrow interchange (doc 03, sec 5).
- Prior art: QGIS Python plugins, `qgis_process`, MDAL.

### 2.9 Agents and scripts as first-class users

If operations have descriptions (2.4) and plans are inspectable (2.2),
an agent or a script can propose an operation, show its plan and its
cost, and only then run it. The user approves a plan, not a black box.
This is the same property that makes a GUI honest, applied to automation.

- Rests on: 2.2 and 2.4.
- Prior art: MCP tool descriptions; openEO's "validate before run".

## 3. What wxylib would not do

- Build a desktop GIS. If someone builds the next one from parts, wxylib
  should be a good part.
- Build a renderer, a tile server or a style language that competes with
  MapLibre, deck.gl, titiler or SLD. Join them.
- Invent a map document format before composing existing ones has been
  tried and found wanting.
- Let any of this pull the core forward. The dev track comes first;
  these are reasons to keep certain doors open, not reasons to walk
  through them.

## 4. Doors to keep open, checked against today's design

Most of these are already decisions; the musings above are mainly extra
reasons for them.

| Door | Musings it serves | Status in the design |
|------|-------------------|----------------------|
| Plans are values: inspectable, serialisable, costed before fetch | 2.1, 2.2, 2.9 | a principle (README); real in `wxy-source` |
| The core builds for wasm | 2.1, 2.3 | three crates do; `wxy-zarr` needs a small fix (doc 03, sec 5) |
| Operations are plain functions over domains and fields, no app state | 2.4, 2.8 | implied by the layer rule; worth stating when S4 lands |
| Value semantics live in the data model, not in readers | 2.6, 2.7 | doc 02, fields |
| Dimensions carry labels and order | 2.7 | doc 02, `Dim` and R2 |
| Virtual descriptions are data, evaluable anywhere | 2.5 | S7, virtualisation principle |
| Arrow and a C ABI as shared binding layers | 2.8 | doc 03, sec 5 (aspiration) |

One thing not yet covered: an operation description (2.4). It is not
needed until there are at least two surfaces to generate (the CLI in S4
and the bindings in S6). If it is ever wanted, the moment to consider it
is just before S6, so that the bindings are not hand-written twice.

## 5. What we would get, what it costs, what if we didn't

- Get: a check on the core from the user's side. Each musing names the
  core property it would need, so a design choice that quietly closes one
  of these doors is easier to notice.
- Cost: one document to read, and the risk that musings are mistaken for
  plans. The status line and the "m" numbering are there to prevent that.
- Without it: the core is still fine, but its downstream value is
  argued only in terms of GDAL parity, and choices that matter to front
  ends (plan visibility, wasm, value semantics) are made without saying
  why they matter.
