# m25: A VRT engine outside GDAL

Status: musing, 2026-11-05. Scopes a reader of GDAL's virtual formats
that runs without GDAL, in Rust and in the browser, across all four VRT
families, and asks where it could be contributed. Based on GDAL master at
`fa1fc3c` (2026-11-03), terrio 0.7.0 at `3a2e373`, OxiGeo at `9e73da7`,
deck.gl-raster at `4e162ee`, maplibre-gl-raster 0.14.16 at `9f3cac4`,
gdal3.js at `bbc1390`, the Pyodide and webR GDAL recipes, and wxylib/web
PRs #20 (`mdim-vrt.js`) and #21 (`ogrvrt.js`). Builds on doc 03 stage
S7 (the virtual scheme), m09 (missing modules, the crate check), m11
(quiet operations), m13 (four views), m22 (plan IR) and
[watch/rewrites.md](watch/rewrites.md) (area E, composition).
Figures: [img/m25-coverage.svg](img/m25-coverage.svg),
[img/m25-model.svg](img/m25-model.svg). Measurement:
[measurements/m25-vrtcon](../measurements/m25-vrtcon/README.md).

## Summary

The question: should wxylib build a VRT engine outside GDAL (GDAL in
WebAssembly, a Rust rewrite, a TypeScript port, or a rewrite built on
the VRT schema), covering classic raster VRT, `vrt://` connection
strings, multidimensional VRT and vector VRT, with a `vrt://`-style
syntax for the multidimensional and vector families too? And could it be
contributed to an existing effort?

- **Everyone else who is working on this reads classic raster mosaics
  only.** Two browser libraries added VRT readers this year:
  deck.gl-raster's `parseVRT` (2026-11-02) and maplibre-gl-raster's
  `parseVrt` (2026-07-16). Both read only where each source sits and
  throw on anything else. terrio has a Rust rewrite of most of classic
  VRT (Simple, Complex, Averaged, Kernel, Derived, Warped,
  Pansharpened) inside the terrio crate. None of them reads `vrt://`,
  multidimensional VRT or vector VRT. The only browser readers of those
  two families found are wxylib's own, from this week (figure 1).
- **GDAL in WebAssembly is real but stuck at 3.8.** gdal3.js (3.8.4),
  Pyodide's `libgdal` (3.8.3) and webR (3.8.1) all compile GDAL with
  Emscripten; GDAL's own CI has no Emscripten job. That misses the
  `vrt://` options added in 3.9, 3.12 and 3.13 and is many megabytes to
  load. It is the right browser oracle, not the engine.
- **A full rewrite would be a port of about 41,000 lines of C++** (the
  raster VRT driver 37,340, of which pixel functions 4,528 and
  multidimensional VRT 3,307; the vector VRT driver 3,856). That is GDAL
  parity, which m09's guardrail rules out.
- **What is missing is small and has no home: a typed model of the VRT
  schema with a planner, and no I/O.** The model parses and writes all
  four families (GDAL ships schemas for two: `gdalvrt.xsd`, 135 element
  names including the multidimensional ones, and `ogrvrt.xsd`, 34). The
  planner answers the question every reader starts with: for this
  window, slice or bounding box, which sources, which source windows,
  which destination windows and which operations. Readers keep their
  own I/O: wxy in Rust, and deck.gl-raster, maplibre-gl-raster or
  wxylib's pages in the browser through wasm (figure 2).
- **`vrt://` is a `gdal_translate` call written as a URI**, and that
  rule extends cleanly. GDAL builds the `vrt://` dataset by turning each
  query key into a `gdal_translate` flag (29 of them). The same rule
  with `gdal mdim translate` flags gives a multidimensional form, and
  with `ogr2ogr` flags a vector form. Each such string lowers to VRT XML
  that GDAL already opens, so GDAL can check the new forms today. A
  prototype lowers vector `vrt://` strings to OGR VRT; GDAL 3.12.4 reads
  all 5 cases, and the 3 with a direct equivalent are identical
  feature by feature.
- **The most contributable piece is a conformance corpus**: VRT files
  of all four families, small sources, and GDAL's reads recorded per
  GDAL version. deck.gl-raster, maplibre-gl-raster, terrio (which
  already cross-reads its VRTs against GDAL) and wxylib all need it, and
  it is conformance work in the plainest sense.
- **Recommendation:** build the model and planner as a crate of its own
  (working name `vrt-model`) in the core workspace with no wxy
  dependencies, compile it to wasm for the web pages, and extract it
  when another project adopts it. Start the corpus in wxylib/fixtures
  first, because both the crate and any outside offer depend on it.
  Anything for GDAL itself (the new `vrt://` keys, nesting, an
  Emscripten CI job) is Michael's to raise; GDAL RFC 111 bars agent
  submissions.

## 1. VRT is four families, not one

GDAL's word "VRT" covers four things that share a name and a file
extension.

| Family | Since | What it is | Written by | Schema | Code in GDAL |
|---|---|---|---|---|---|
| Classic raster VRT | 1.x | bands built from windows of other rasters: Simple, Complex (scale, LUT, nodata), Averaged, KernelFiltered sources; Derived bands with pixel functions; Warped and Pansharpened datasets | `gdalbuildvrt`, `gdal_translate -of VRT`, `gdalwarp -of VRT`, `gdal raster mosaic` | `gdalvrt.xsd` | `frmts/vrt`, 37,340 lines with the next row |
| `vrt://` strings | 3.1 | one source dataset with `gdal_translate` options in a query string; no file | by hand, by tools that pass a dataset name | none (documented in prose) | `VRTDataset::OpenVRTProtocol` |
| Multidimensional VRT | 3.1 | groups, dimensions, arrays; each array from sources with SourceView, SourceTranspose, SourceSlab and DestSlab; DerivedArray with View, Transpose, Resample, Grid steps | `gdal mdim mosaic` (3.12), by hand, vrtstack | `gdalvrt.xsd` (Group, Array, Dimension types) | `vrtmultidim.cpp`, 3,307 lines |
| Vector VRT | 1.x | layers from other layers: field selection and renaming, geometry from columns or WKT/WKB, SQL, a region, reprojection, unions | by hand, `ogr2ogr` users | `ogrvrt.xsd` | `ogr/ogrsf_frmts/vrt`, 3,856 lines |

Two neighbours sit beside them. GTI (GDAL Tile Index, 3.9) is a mosaic
whose sources are rows of a vector layer. GDALG (3.11) is a JSON file
holding a `gdal` pipeline command, with a JSON Schema
(`gdalg.schema.json`), for raster and vector; its own documentation
calls it "conceptually close to VRT, although the implementation is
substantially different". GDALG is to the new `gdal` CLI what `vrt://`
is to `gdal_translate`: a written form of a command.

### 1.1 What `vrt://` actually is

`OpenVRTProtocol` splits the string at the first `?`, splits the query
on `&`, and turns each key into a `gdal_translate` argument (`bands` to
`-b`, `srcwin` to `-srcwin`, `a_srs` to `-a_srs` and so on, 29
`AddString` calls), then runs `GDALTranslate` with VRT output on the
opened source. The options arrived over several releases:

| GDAL | Keys added |
|---|---|
| 3.1 | `bands` |
| 3.7 | `a_srs`, `a_ullr`, `ovr`, `expand`, `a_scale`, `a_offset`, `ot`, `gcp`, `if`, `scale`, `exponent`, `outsize` |
| 3.8 | `projwin`, `projwin_srs`, `tr`, `r`, `srcwin`, `a_gt`, `oo`, `unscale`, `a_coord_epoch`, `nogcp`, `epo`, `eco` |
| 3.9 | `a_nodata`, `sd_name`, `sd` |
| 3.12 | `transpose` (one array of a multidimensional source, as a 2D classic view) |
| 3.13 | `block` (one natural block as a window) |

Three things follow. The string is a serialised command, so its grammar
is the command's flags. `transpose` already reaches into the
multidimensional model, but it returns a classic 2D dataset; there is no
string form whose result is a multidimensional array, and none for
vector data. And because the split is at the first `?`, a `vrt://`
string cannot be the source of another one with options of its own.

## 2. Who else is working on it

Read from each project's source at the commits in the status line.

| Project | Language, home | Families | Scope | Added |
|---|---|---|---|---|
| GDAL in wasm: gdal3.js, Pyodide `libgdal`, webR | C++ via Emscripten | all four, as of 3.8 | GDAL 3.8.4, 3.8.3 and 3.8.1. gdal3.js last commit 2026-05-13, npm 2.8.1. Network reads need a worker or a mounted file | long-standing |
| terrio `ops/vrt.rs`, `ops/vrt/virtual_raster.rs` | Rust, inside the terrio crate (MIT) | classic | 4,110 lines, translated from GDAL 3.13.3 `vrtsources.cpp` and others. Simple, Complex (NODATA, ScaleOffset, ScaleRatio, LUT), Averaged sources; lazy Warped; built-in scalar Derived bands (no Python); kernel sources; Pansharpened. `scripts/compare_vrt_with_gdal.py` cross-reads against `osgeo.gdal` | 2026-10-14 |
| OxiGeo `oxigeo-vrt` (formerly OxiGDAL) | Rust, monolith (Apache-2.0) | classic | 7,281 lines: mosaics, scaling, pixel functions, warped VRTs. Doc 04 marks the project "avoid" | 2026 |
| deck.gl-raster `parseVRT` (Development Seed) | TypeScript, `@developmentseed/deck.gl-geotiff` | classic mosaic | 148 lines. One item per source with its WGS84 box from `DstRect`, `GeoTransform` and `SRS`; each COG drawn with its own georeferencing; `SrcRect`, scaling and NODATA ignored; throws on warped or derived. Example: the USGS 3DEP 1 arc-second VRT, 2.2 MB of XML, 3,811 COGs, parsed in 50 to 90 ms | 2026-11-02 (PR #835) |
| maplibre-gl-raster `parseVrt` (opengeos) | TypeScript | classic mosaic | 541 lines. Accepts only VRTs whose sources sit where their own headers put them; rejects anything that repositions, crops, rescales or computes, naming the GDAL command that would make a supported file | 2026-07-16 (PR #40) |
| wxylib web `mdim-vrt.js` | JavaScript | multidimensional | 197 lines. Parses the published GHRSST `mdim.vrt` (16.6 MB, 38,360 COG sources) and answers "which source holds this element"; partial SourceSlab and SourceView not yet honoured | 2026-11-05 (web PR #20) |
| wxylib web `ogrvrt.js` | JavaScript | vector | 1,195 lines. OGRVRTLayer, geometry encodings, SrcSQL as an OGR SQL subset, SrcRegion, FID, Style, Field, Warped and Union layers; 5 examples equal GDAL 3.12.4 | 2026-11-05 (web PR #21) |

Not found: VRT support in geotiff.js, in VirtualiZarr's parsers, or a
browser reader of multidimensional or vector VRT outside wxylib. That is
a search result, not proof of absence.

![Who reads which VRT family, 2026-11-05: GDAL and its wasm builds read
all four; terrio and OxiGeo read classic raster; two browser libraries
read classic mosaics only; wxylib's pages read a subset of
multidimensional and vector VRT](img/m25-coverage.svg)

Two observations. The browser libraries arrived independently, months
apart, and each reads the same narrow subset in its own way; each will
meet the same COP30-style VRT (m11: 55 percent of its sources resample
silently through `SrcRect` and `DstRect`) and decide alone what to do.
And the people involved are already in view: terrio and
maplibre-gl-raster are Qiusheng Wu's (opengeos; Michael collaborates on
terrio), and deck.gl-raster is Kyle Barron's (Development Seed). Both
are inside doc 04's "stay compatible" circle.

## 3. Four ways to build it

### 3.1 A. GDAL compiled to WebAssembly

- **Get.** Every family, exactly as GDAL reads it, as of the build's
  version. No interpretation to get wrong.
- **Cost.** All three maintained builds are at 3.8, so `vrt://` lacks
  `a_nodata`, `sd`, `sd_name`, `transpose` and `block`. The bundle is
  large (GDAL plus PROJ, GEOS, SQLite and codecs). HTTP range reads go
  through Emscripten's file system rather than `fetch` from the page.
  Keeping a build current is a project of its own, and GDAL's CI does
  not build for Emscripten.
- **Without it.** No in-browser oracle; checks run in CI with
  `osgeo.gdal` instead, which is where wxylib's oracles already run.
- **Role.** The oracle in the browser, for a "compare with GDAL" button
  on a page. Not the engine.

### 3.2 B. A Rust rewrite of the VRT drivers

- **Get.** A GDAL-free VRT in Rust, with wasm for free.
- **Cost.** About 41,000 lines to port and track, half of it pixel
  machinery (resampling, pixel functions, muparser and Python
  expressions, pansharpening) that is not VRT-specific. terrio has done
  the classic part inside its crate, translated from GDAL's source; a
  second translation would compete with it rather than help.
- **Without it.** Nothing lost that the model in D does not cover; the
  pixel work belongs to rwarp (warped and resampled sources) and to an
  expression layer (m22's plan IR, not a VRT concern).
- **Role.** Ruled out as a goal. It is GDAL parity.

### 3.3 C. TypeScript ports, one per page

- **Get.** Fast to write and ship; wxylib has two already, the browser
  libraries one each.
- **Cost.** The same rules written once per language and once per
  project, each with its own subset and its own bugs; the Rust side
  (wxy, stage S7) needs the rules again.
- **Without it.** The pages wait for the wasm build of D.
- **Role.** Prototypes. `mdim-vrt.js` and `ogrvrt.js` are the
  specification by example for D, and their tests become corpus cases.

### 3.4 D. A schema-first model and planner, no I/O

- **Get.** One typed model of all four families: parse, validate
  against GDAL's two schemas, write back the same XML, and keep anything
  unknown as text so nothing is silently dropped. One planner that turns
  a request into rows of (source, source window, destination window,
  operations), which is also the table m11 asks for (quiet operations
  become visible as rows whose `SrcRect` and `DstRect` differ). `vrt://`
  strings and JSON parse into the same model. Compiled to wasm, it is a
  drop-in for `parseVRT` and `parseVrt` that returns more, and the
  rules exist once.
- **Cost.** Modelling the multidimensional family needs source metadata
  (dimension sizes and types come from the source header when the VRT
  omits them), so the planner's input includes a small "source
  description" that readers fill in. The derived and warped families can
  be modelled and planned but not evaluated here; evaluation stays with
  rwarp and wxy. A serde model of about 170 element names is a few thousand
  lines, mostly mechanical.
- **Without it.** Every reader keeps reimplementing the mosaic subset;
  stage S7 builds its own; the multidimensional and vector families stay
  GDAL-only outside wxylib's two pages.
- **Role.** Recommended (figure 2).

![The proposed crate: three written forms (VRT XML, vrt:// strings,
JSON) parse into one model; a planner turns requests into source rows;
wxy, browser libraries and GDAL consume it; a conformance corpus checks
everything](img/m25-model.svg)

### 3.5 The crate check (m09 section 5)

- **Does a crate exist?** A model crate, no. terrio's is inside terrio
  and reads files itself; OxiGeo's is part of a monolith; the
  TypeScript readers are functions inside rendering libraries. A
  standalone, I/O-free VRT model is the missing module.
- **Are we overbuilding?** Only if the crate starts evaluating pixels.
  The line is: the model and planner say what to read and from where;
  they never read bytes and never compute values.
- **Its own crate?** Yes, with no wxy dependency, so terrio, the
  browser libraries and wxy could all use it. Start it in the core
  workspace (as m09 does for geo-free pieces) and extract it once a
  second project wants it.

## 4. `vrt://` for all four families

### 4.1 The rule

GDAL's own `vrt://` keys are `gdal_translate` flags. Keep that rule and
apply it per family: the keys are the flags of that family's translate
command, and the result is the VRT that command would write.

| Family | Command whose flags are the keys | Example |
|---|---|---|
| Classic raster | `gdal_translate` (GDAL's 29 keys, unchanged) | `vrt://dem.tif?srcwin=0,0,512,512&ot=Float32` |
| Multidimensional | `gdal mdim translate` (`array`, `view`, `transpose`, `subset`, `scaleaxes`, `group`) | `vrt://ghrsst.vrt?array=/analysed_sst&subset=time("2024-01-01","2024-01-31")` |
| Vector | `ogr2ogr` (`layer`, `select`, `where`, `sql`, `spat`, `a_srs`, `t_srs`, `name`; `x`, `y` for points from columns) | `vrt://stations.csv?layer=stations&x=lon&y=lat&a_srs=EPSG:4326&where=operator='Australia'` |

The family is decided by the keys, as GDAL decides between `sd_name`
and `transpose` today: `array` or `group` makes the result
multidimensional, `layer`, `select`, `where`, `sql` or `spat` makes it
vector, and anything else is classic. Shared keys (`a_srs`, `oo`, `if`)
mean the same in all three. A clash (`bands` with `layer`) is an error.

### 4.2 Lowering, and why it matters

Every string lowers to a VRT document of its family: the classic form
to what `gdal_translate -of VRT` writes (GDAL already does exactly
this), the multidimensional form to a `<VRTDataset>` with one `<Array>`
whose `<Source>` carries `SourceArray`, `SourceView`, `SourceTranspose`
and `SourceSlab`, and the vector form to an `<OGRVRTDataSource>`. So
GDAL can check the new forms now, before any of them exists in GDAL:
lower the string, open the XML with GDAL, compare with GDAL's direct
read using the same flags.

The prototype in [measurements/m25-vrtcon](../measurements/m25-vrtcon/README.md)
does this for the vector family (`vrtcon.py` needs no GDAL; `check.py`
is the oracle). With GDAL 3.12.4 through pyogrio, all 5 cases read; the
3 with a direct equivalent (`select` plus `where`, `select` plus
`spat`, `sql`) are identical to GDAL's direct read in geometry and
fields; points from CSV columns and reprojection to EPSG:3031 read as
expected. Two details from writing it: OGR VRT has no attribute-filter
element, so `where` lowers to `SrcSQL` (the same fact web PR #21 found),
and `t_srs` lowers to an `OGRVRTWarpedLayer` around the layer.

The multidimensional lowering needs the source's dimensions and types,
so it opens the source header first, as GDAL's own classic `vrt://`
does. It is not in the prototype, because this environment had no
`osgeo.gdal` build with the multidimensional API; it is the first thing
to check with the corpus.

### 4.3 Nesting

Splitting at the last `?` instead of the first lets a `vrt://` string
be the source of another, which GDAL's split does not. The cleaner
answer for chains longer than two is GDALG's `!` pipeline, which GDAL
already has; the model should read GDALG's JSON too, since it is the
same idea one level up. Byte-level chains (`/vsizip/`, `/vsicurl/`)
stay m09's chain grammar and appear here only as source names.

### 4.4 Source names: the grammar the schemas leave out

Both schemas type a source name as a plain string. `SourceFilename`
(raster) carries only `relativeToVRT` (and the deprecated
`relativetoVRT`) and `shared`; `SrcDataSource` (vector) carries
`relativeToVRT`, with `OpenOptions` beside it. Everything a GDAL dataset
name can be is outside the schema, defined only by the drivers' open
code and their documentation:

| Form | Example |
|---|---|
| plain or relative path, URL | `tile_01.tif`, `https://host/a.tif` |
| VSI chain | `/vsicurl/https://...`, `/vsizip/{/vsicurl/https://host/a.zip}/b.tif`, `/vsis3/bucket/key` |
| driver prefix and subdataset | `NETCDF:"file.nc":sst`, `HDF5:"f.h5"://grp/var`, `ZARR:"s3://b/x.zarr":/sst` |
| another VRT | `mosaic.vrt` (nesting), `vrt://file.nc?sd_name=sst` |
| inline VRT | a string starting with `<VRTDataset>` |

The browser readers in section 2 accept the first row and `/vsicurl/`
only: maplibre-gl-raster rejects every other `/vsi*` prefix and steers
users away from a `.vrt` source; deck.gl-raster throws on other prefixes,
and a nested `.vrt` URL would pass its check and then fail when opened
as a COG. So nesting and the variety of source names are where the model
earns its place. It parses each source name into a typed value:

```
Dsn = Path(relative_to_vrt) | Vsi(m09 chain) | Driver(prefix, Dsn, subdataset)
    | Vrt(Dsn)            | VrtString(Dsn, options)  | Inline(VRT model)
```

A nested VRT, a `vrt://` string or an inline document becomes a child
model, so the planner recurses through it to the leaf sources; a VSI
chain is handed to m09's chain grammar; a driver prefix names the reader
the leaf needs. The corpus gets one case per row of the table above,
nested at least two levels.

## 5. Contributing it

Ordered by how directly each helps someone else, and by who acts.

1. **The conformance corpus (wxylib/fixtures; ours to build, anyone's
   to use).** VRT files of the four families plus `vrt://` and the new
   string forms, small sources, and GDAL's reads recorded per GDAL
   version with `osgeo.gdal`. Start from what exists: web PR #21's five
   vector examples and its oracle, the GHRSST and BRAN `mdim.vrt` files
   (m13), the COP30 and REMA mosaics (m10, m11), the 3DEP VRT that
   deck.gl-raster's example reads. Offer it to deck.gl-raster and
   maplibre-gl-raster as test data, and to terrio next to
   `compare_vrt_with_gdal.py`. Contacting those projects is Michael's
   call.
2. **The crate, as a wasm package (ours; offered).** Once the planner
   handles classic mosaics with `SrcRect` and `DstRect` and the
   multidimensional slabs, it can stand behind `parseVRT` or `parseVrt`
   unchanged in signature and return the source rows as well. Whether
   either project wants a wasm dependency is theirs to say; the corpus
   helps them either way.
3. **terrio (Michael's collaboration).** terrio's classic VRT could sit
   on the model instead of its own parser, the way terrio-crs became its
   own crate. Not to be drafted until Michael says so (as for all
   terrio contributions).
4. **GDAL (Michael only, under RFC 111).** Candidates, each as a
   tracker note on mdsumner/osgeo-upstream, with any GDAL text his: the
   multidimensional and vector `vrt://` keys (the prototype and corpus
   are evidence; Michael wrote most of the existing keys), nesting
   (split at the last `?`), schema gaps the corpus finds, and an
   Emscripten CI job so browser builds stop lagging (a conversation with
   the gdal3.js, Pyodide and webR maintainers first).

The framing throughout is conformance and ecosystem: the corpus and the
lowering make GDAL the reference that every other reader is checked
against, and the new string forms are written so that GDAL could adopt
them unchanged.

## 6. Decisions

1. **Which approach?** Recommended: D, the model and planner, with
   wxylib's two JavaScript readers kept as prototypes until the wasm
   build replaces their parsing; A as the in-browser oracle only; B
   ruled out.
2. **Where does the crate live?** Recommended: `vrt-model` (working
   name) in the core workspace with no wxy dependencies, extracted to
   its own repository when another project adopts it. Alternative: a
   standalone repository now (Michael creates it), if the outside offer
   should come first.
3. **The multidimensional and vector `vrt://` forms: a wxylib extension
   now?** Recommended: yes, defined by the rule in section 4.1 and
   always lowered to XML, so they never diverge from what GDAL can
   check; Michael decides if and when they go to GDAL.
4. **Offer the corpus to deck.gl-raster, maplibre-gl-raster and
   terrio?** Recommended: yes, once it holds classic mosaic cases with
   GDAL reads; Michael makes the contact.

## 7. First steps

1. **Corpus.** `fixtures/vrt/`: about 20 cases across the four families
   and the string forms, each with small sources and GDAL 3.12 and 3.13
   reads (`osgeo.gdal`, in the images or through a brief). Include the
   five vector cases from web PR #21 and this note's five string cases.
2. **Model.** Typed parse and write for classic, multidimensional and
   vector VRT; round trip every corpus file; validate against
   `gdalvrt.xsd` and `ogrvrt.xsd`; unknown elements kept and reported.
3. **Planner.** Classic mosaics (with `SrcRect`/`DstRect` resampling
   reported as rows, per m11) and multidimensional slabs. Targets:
   3DEP (3,811 sources), COP30 (26,475), GHRSST `mdim.vrt` (38,360).
4. **Strings and source names.** Typed source names (section 4.4) with nested VRTs planned through; a `vrt://` parser covering GDAL's 29 keys, lowered as
   GDAL lowers them, plus the multidimensional and vector keys of
   section 4.1; port the prototype; check the multidimensional lowering
   against GDAL.
5. **Browser.** A wasm build used by `mdim.html` and `vrt-vector.html`
   for parsing and source lookup, timed against the JavaScript parsers
   on the same files.

Later, and outside the crate: evaluation in wxy (stage S7), with rwarp
for warped and resampled sources.

## 8. Not claimed

- The line counts are of GDAL master at `fa1fc3c`, counted with `wc -l`
  over the driver directories, so they include comments and headers.
- The coverage marks in figure 1 come from reading each project's
  source and documentation, not from running a common test set; the
  corpus is what would make them measurements.
- "Not found" in section 2 means not found by searching the projects
  named and the web on 2026-11-05.
- The multidimensional lowering and the planner are designs, not yet
  code.
