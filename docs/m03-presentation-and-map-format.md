# m03: Presentation on raw data, and the map as a document

Status: musing, 2026-10-16. Not a plan and not a gate. Picked up from doc 05
section 11 (X1, X2) at gate 5, and builds on m01 sections 2.5 and 2.6,
which first raised both ideas. It becomes work only through a numbered
document.

## 1. Two gaps

- **Presentation on raw data (X1).** No real raster format carries the
  image scaling (stretch, palette, gamma, band-to-RGB mapping, nodata
  styling) next to untouched raw values, so that it travels with the data
  and is applied at read time. Today presentation is either baked into a
  rendered byte copy, which loses the data, or kept in a sidecar the next
  tool ignores. Scale and offset are about units, not presentation.
- **No real map format (X2).** Nothing sendable holds presentation, links
  to raster and vector sources, derived label layers, view states (CRS,
  extent, zoom) and accoutrements (graticule, scale bar, legend, north
  arrow, insets, titles), ready for the recipient to open, explore, modify
  and view. Desktop project files are tool-bound and fragile; web map
  styles are tied to tiles and one projection; GeoPDF is an export, not a
  live document.

## 2. The shape of an answer

Both are "recipe, not payload": a description that references its sources
and is evaluated by whoever opens it.

**Three layers, kept apart.**

1. *Value semantics* (data model, exists): units, scale and offset,
   nodata, categories, valid range. Readers apply these to get numbers.
2. *Presentation* (new, optional): how numbers become colour. Stretch
   (limits, function: linear, log, histogram equalise, gamma), palette or
   colour map, band-to-RGB(A) mapping, nodata and out-of-range styling.
   Never applied by a reader unless asked; a renderer applies it after the
   warp to a screen grid (m01 section 2.1).
3. *Map* (new, optional): an ordered list of layers, each a reference to a
   source (a mosaic VRT or an mdim-refs table, the inputs S7 reads, or a
   plain URL) plus a
   presentation; one or more views (target CRS, extent, size or zoom
   states); and accoutrements as declarative items.

**Where presentation lives.** As a Zarr attribute convention beside
`spatial:` and `proj:`, so it versions with the data in a GeoZarr or
Icechunk store, and as a standalone small JSON document for formats that
cannot carry it. One schema, two homes. A natural proposal to take to the
GeoZarr conventions work (gate 4 said yes to that work), as an optional
`presentation:` or similar namespace.

**Where the map lives.** A small JSON document that composes existing
specs rather than inventing one where it can: a mosaic VRT or an mdim-refs
table for data (never its own source description), the presentation
schema above for raster appearance, a MapLibre style subset for vector
appearance, and a thin view and accoutrement layer only where nothing
fits. Views are explicit target grids (doc 05 W1), so a map
is not tied to one projection or to tiles.

## 3. What wxylib would and would not do

- Would: define the presentation schema in a small crate with no
  dependencies on the rest (like `wxy-geozarr`); let `wxy-domain` fields
  carry an optional presentation; let `wxy warp` and the browser app apply
  it when rendering.
- Would not: build a renderer, a cartography engine or a desktop app.
  Accoutrements are described, not drawn, by the core.

## 4. What we would get, what it costs, what if we didn't

- Get: the same layer looks the same in every tool that reads the
  convention; raw values are never lost to a rendered copy; a map can be
  sent as a few kilobytes that reference cloud data.
- Cost: a schema to design and keep small; convincing other tools to read
  it; the risk of a format nobody else adopts.
- Without it: presentation stays baked or lost, and maps stay inside the
  tool that made them.

## 5. Prior art to read before any design

SLD and SE, QGIS QML, MapLibre style
spec, GDAL's colour tables and RAT, STAC raster and classification
extensions, CF `flag_values`, TiTiler rescale and colormap parameters,
Vega-Lite as a grammar, GeoPDF as the export it is.
