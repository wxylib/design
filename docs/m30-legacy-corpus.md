# m30: The rasterwise legacy corpus in modern terms

Status: plan, 2026-11-07. Preparation only: the corpus is being made
interim-ready, so this note sets out the checks, the mapping and the
pages, and records one pilot measurement. Builds on m27 (oracle harness),
m23 (byte-ref harvesting), m25 and m29 (VRT engine, VRT reimagined), m17
(store description) and m13 (multiple views of one store). Measurement:
[measurements/m30-rasterwise](../measurements/m30-rasterwise/).

## Summary

rgdal-dev/rasterwise is an archive of problem files: gridded data, mostly
netCDF and HDF with some GeoTIFF and raw binary, that broke readers or
misled them, each with a written case saying what is wrong and how to read
it correctly. Most of these files are not pressing in themselves. Their
structures live on, though: in Zarr's assumptions (array order is image
order, coordinates are arrays, a fill value is one number), in virtual
stores that inherit source chunking, and in every reader that has to
guess. The aim is to find out how much of the corpus can be scanned, read
and shown with current tools, how each legacy structure sits in modern
terms (byte references, mdim.vrt, Zarr), what metadata augmentation
("assertion") each needs and in which form, and which usage pipelines
follow. Some of it should become browser pages, grouped by the problem
the files share rather than by format or source.

The plan:

1. **A check ladder per file** (section 3): identity, scan, read, refs,
   wxy read, view, assertion. GDAL (osgeo.gdal) is the oracle; each rung
   is an `oracle-case/0` question so answers are recorded per GDAL
   version.
2. **A mapping table** from each costume letter and finding code to its
   modern expression (section 4). Most legacy problems reduce to an
   assertion over unchanged bytes; a few need a cut or a view; very few
   need a copy.
3. **Assertions as data** (section 5): one record per claim, keyed by
   sha256, with evidence and an oracle check, emitted as classic VRT,
   `vrt://`, mdim.vrt, Zarr attributes or a STAC patch.
4. **Pipelines** (section 6) per problem class, ending in GDAL, the GDAL
   xarray backend, wxy or the browser.
5. **Nine browser pages** (section 7), each one shared problem, each
   showing the file as stored, as a naive reader shows it, and as
   asserted.

Nothing here writes to rasterwise. It stays standalone and read-only from
wxylib's side; outputs key to its `sha256` and case slugs, which its
README already declares stable.

## 1. What the corpus is (rasterwise 4942498, 2026-11-07)

| Item | Count |
|---|---|
| Cases (`cases/<slug>/case.yaml` + README) | 31 (25 understood, 4 open, 2 fixed upstream) |
| Manifest rows (files by sha256) | 143, 109 used by a case, 4.46 GB in all (4.07 GB in cases) |
| Formats sniffed | netCDF4/HDF5 36, netCDF3 24, raw binary 13, VRT 10, TIFF 6, GeoTIFF 2, HDF4 1, PNG 3, scripts and text 37, unsniffed 11 |
| Status | 141 ok, 2 truncated |
| Redistributable | 46 no, 97 unknown, 0 yes |
| Missing (known to have existed, no intact bytes) | 39 rows in `missing.csv`, with 50 `ncdump -h` fingerprints |

Costume letters (from regular-in-what's table A to H) over the 31 cases (a case can carry more than one):
C 14, E 8, none 5, D 4, A 3, B 2, E2 2, H 1. The commonest finding codes
are `Y_ASCENDING` (12 cases), `LON_0_360` (8), `GRID_2D_LONLAT_ONLY` (7),
`AXES_X_BEFORE_Y` (5), `LAT_MERCATOR_SPACED` (4),
`GRID_2D_WITH_PROJECTED_1D` (3) and `DSG_NOT_GRID` (3); 30 more codes
occur once each.

The corpus is already shaped for this work: identity by content, stable
slugs, a `how_to_read` per case (often a VRT or a GDAL call, verified
against GDAL 3.14dev), a fingerprint per lost file, and a downstream
consumer (storecard) that builds metadata cards keyed to the manifest and
defines the assertion record. What it lacks is published bytes: `url` is
empty for every row until the blob store is staged.

### Pilot (measurements/m30-rasterwise)

The v0.0.12 release bundle (47 MB, 36 members) was fetched from the
repo's releases and scanned with osgeo.gdal 3.8.4
([pilot.py](../measurements/m30-rasterwise/pilot.py),
[pilot-v0.0.12-gdal-3.8.4.jsonl](../measurements/m30-rasterwise/pilot-v0.0.12-gdal-3.8.4.jsonl)).

- All 36 members match a manifest row by sha256, so the manifest and the
  releases agree.
- Of the 29 data files, 28 open in the classic API and 28 in the
  multidimensional API. The two refusals are the expected ones: the WOD
  single-cast profile (not a raster, `wod-profile-cast-not-a-grid`) in
  classic, and the GeoTIFF in multidim.
- Opening is not reading correctly. Of the 15 files that open as a single
  raster, 7 have no geotransform and 13 have no CRS. The case notes
  already say which of the rest are wrong (transposed, flipped, Mercator
  as lon/lat). "Opens" is the bottom rung, not the measure.

So scan coverage is near total even on an old GDAL; the work is in the
upper rungs, where each case's `how_to_read` becomes a checked claim.

## 2. Where the work lands

| Repo | What |
|---|---|
| rgdal-dev/rasterwise | unchanged; source of bytes, cases and stable keys |
| wxylib/fixtures | an `oracle-case/0` set `rasterwise/`: `cases.json` questions keyed by sha256, answers per GDAL version; assertion records and their checks |
| wxylib/core | nothing new expected; the wxy rungs use existing readers (wxy-refs, wxy-zarr, wxy-tiff) and show where they stop |
| wxylib/refharvest | refs for netCDF4/HDF5 members via async-hdf5; netCDF3 and raw binary are header arithmetic (section 4.3) |
| wxylib/web | the problem-group pages (section 7) |
| wxylib/docs | a gallery page linking the groups, the case READMEs and regular-in-what |
| hypertidy/storecard | its consumer role stays: cards and assertions are its records; wxylib checks them against GDAL and emits forms |

Guardrail check (m09): nothing here needs a new crate. The only candidate
is a netCDF3 classic header reader for byte refs, and pure-Rust readers
already exist (the `netcdf3` crate on crates.io is the first to check),
as do kerchunk's and VirtualiZarr's netCDF3 readers in Python.

## 3. The check ladder

One row per file (per array where a file holds several), one column per
rung. Each rung is an `oracle-case/0` question so it is recorded once and
answered by each GDAL version (3.8.4 in the cloud, current release and
HEAD in Actions, as fixtures #14 does).

| Rung | Question | Tool | Answer recorded |
|---|---|---|---|
| R0 identity | do the bytes match the manifest? | sha256, `tools/curate.py check` | match, truncated, absent |
| R1 scan | what does a reader see without reading data? | `raster.info`, `mdim.info` (osgeo.gdal), storecard card | driver, dims, coords, CRS, geotransform, fill, packing, chunks, findings |
| R2 read | what values come back for fixed windows? | `raster.read`, `mdim.read` | checksums and small arrays per window |
| R3 refs | can every array be expressed as byte ranges? | refharvest (HDF5), header arithmetic (netCDF3, raw), kerchunk/VirtualiZarr as a cross-check | refs table rows, or a reason (compressed HDF4 chunk layout, VRT source, truncated) |
| R4 wxy | does wxy read the refs to the same values as R2? | wxy-refs, wxy-zarr | identical, differs, refused |
| R5 view | what does the file look like as stored, as read naively, and as asserted? | quicklook PNGs from osgeo.gdal (as read) and from the asserted view | three images per array |
| R6 assertion | with the case's assertion applied, does GDAL reproduce the file's own coordinates? | the assertion record (section 5) emitted as VRT, opened by GDAL | residual statistics against stored lon/lat |

R6 is the rung that turns `how_to_read` prose into evidence: for a cryptic
curvilinear file the residual is the distance between the stored 2D
lon/lat and the asserted grid's cell centres (the cases quote 40 m for
CryoSat-2, 0.42 m for the fast-ice grid, 7 m for COCO). A case is
"asserted" when R6 passes on the oldest GDAL that can open it.

The ladder doubles as a GDAL version history: the case notes record
behaviour that changed (5D band labels fixed, the 2007 crash). Answering
the same questions on 3.8.4 and HEAD shows which problems were reader
problems and which are still in the files.

## 4. Legacy structures in modern terms

### 4.1 By costume

| Costume | Stored as | Modern expression | Bytes | Cases |
|---|---|---|---|---|
| A | array, no position | assertion of CRS + transform (+ dtype, byte order, shape for raw) | refs as-is | nsidc no-coords, fast ice, UCSD topo |
| B | dimension + affine (+ CRS) | already modern; check the CRS is true | as-is | rotated `out.tif` (wrong CRS asserted) |
| C | 1D regular coordinates | a transform; the 1D arrays are redundant (degenerate rectilinear) | refs as-is | 14 cases |
| D | 1D lon, Mercator-spaced lat | assertion of a Mercator CRS + transform; the lat array becomes evidence | refs as-is | AVISO, ACC fronts, UCSD, COCO |
| E | 2D lon/lat only | fitted CRS + transform (cryptic curvilinear); 2D arrays kept as evidence | refs as-is | CryoSat-2, NHSCE, MESAN, CORDEX stripped, LAEA globe |
| E2 | 2D lon/lat plus rotated or projected 1D | the 1D axes with their grid mapping; already a transform | as-is | rotated pole, RegCM LCC |
| H | 2D, regular in no frame | coordinates stay arrays; geolocation, not a transform | as-is | CM2.1 tripolar |
| none | not a grid | a table or feature view (m29's view parameter), not a raster | as-is | Argo, WOD, DSG timeseries, catchment ids |

The pattern: in every costume but H and none, the modern form is the
same bytes plus four numbers and a CRS. That is an assertion, not a
conversion. The cost of not stating it is paid by every reader, every
time, which is the argument regular-in-what makes.

### 4.2 By finding

| Finding | Modern expression | Zarr assumption it meets |
|---|---|---|
| `Y_ASCENDING`, `ROW_ORDER_INCONSISTENT` | sign of the transform's y step; no byte change | Zarr has no orientation; array order is taken as image order by most viewers |
| `AXES_X_BEFORE_Y`, `ARRAY_TRANSPOSED`, `GEOTRANSFORM_TRANSPOSED` | dimension roles asserted (`x`, `y` by name, not by position); for one-chunk arrays a Zarr v3 `transpose` codec may express it in refs alone (to measure: which readers honour it) | dimension order is assumed (..., y, x) |
| `LON_0_360`, `LON_ABOVE_360`, `LON_BELOW_MINUS_180` | the transform as stored; wrapping is a view choice | none in Zarr; viewers assume -180..180 |
| duplicated seam column (ACC fronts) | a cut (m29 tier T2): placement drops one column | none |
| `LAT_MERCATOR_SPACED`, `GRID_2D_LONLAT_ONLY`, `GRID_MAPPING_MISLABELLED`, `MODEL_COORDS_AS_LONLAT` | CRS + transform assertion with residuals | coordinates are arrays; no declared transform in core Zarr (the zarr-conventions `spatial:`/`proj:` attributes fill this) |
| `FILL_ATTR_NONSTANDARD`, `SENTINEL_UNDECLARED`, `FLAG_IN_VALUE_PARITY` | fill and flag values asserted (`_FillValue`, `flag_values`, `flag_masks`) | one `fill_value` per array; flags are attributes only |
| NaN read as 0 (ACC fronts, classic API) | an oracle question, possibly a GDAL bug | fill value and NaN conflated |
| `CHUNKS_SPAN_BAND_DIM` | a cost figure (request amplification per band, m17 `cost`); a rechunked copy is the only fix, so it is a copy decision, not an assertion | chunks are fixed by the source |
| `TRUNCATED` | refs with `present=0` for unreachable chunks (m17) | absent chunk means fill, not error |
| `RAW_NO_HEADER`, `HEADER_NO_GEOTRANSFORM` | refs with a `bytes` codec (endian) and an asserted shape and dtype | a store needs metadata; raw bytes get it from the assertion |
| `SIDECAR_GEOREF_WRONG`, `COPY_IS_RESAMPLED` | the corpus's own old assertions, now evidence: an assertion record can be marked wrong with residuals | none |
| `DSG_NOT_GRID`, `ID_AS_COORDINATE`, `CHAR_DIM_DROPPED` | a table view; char variables as string columns | Zarr strings are a v3 extension |

### 4.3 Byte references per format

- **netCDF3 classic and 64-bit offset** (24 files): fixed variables are
  one contiguous range each; record variables are one range per record,
  strided by the record size. Offsets come from the header alone. Every
  netCDF3 file in the corpus should reach R3.
- **netCDF4/HDF5** (36 files): refharvest with async-hdf5, as for BRAN and
  OISST. Contiguous and chunked layouts both reduce to rows; compact
  datasets (small attributes-like arrays) are inlined.
- **Raw binary** (13 files, UCSD topo and the fast-ice images): one range
  per array, codec `bytes` with the asserted endianness; the assertion
  carries shape, dtype and the grid. This is costume A becoming a
  first-class store without a copy.
- **TIFF and GeoTIFF**: async-tiff as in the GHRSST store.
- **HDF4** (1 file, MODIS): out of scope for refs until a reader exists;
  R1 and R2 through GDAL only.
- **VRT** (10 files): these are the corpus's own historical assertions.
  They are parsed (vrt-model) and judged at R6 like any other assertion.

### 4.4 mdim.vrt as the bridge

For netCDF members, mdim.vrt is the form GDAL already reads that can
carry both placement and assertion: dimension renames and order,
`<RegularlySpacedValues>` for a fitted axis, CRS on an array, nodata. The
GDAL xarray backend reads it too, so one emitted mdim.vrt serves osgeo.gdal,
xarray and (via the browser mdim parser, web PR #20) the pages. A classic
VRT or a `vrt://` string serves the 2D cases where a one-line repair is
the point.

## 5. Assertion

An assertion supplies what a source lacks or corrects what it gets wrong,
without copying a byte (VRT's assertion property; storecard's record).
For the corpus each case's `how_to_read` becomes one or more records:

```yaml
assertion: 0
target:
  sha256: 13cc4140fb59...        # the file
  array: sea_ice_concentration    # or a subdataset path
asserts:
  crs: EPSG:3412
  transform: [-3950000, 25000, 0, 4350000, 0, -25000]
  dims: {x: x, y: y}             # roles by name
  row_order: top-down
  fill: null                     # only fields asserted are present
evidence:
  method: fit 2D lon/lat         # gproj/regula, or "documented", or "case notes"
  residual_m: {max: 41, rms: null}
  against: lat, lon               # the stored arrays used
check:
  oracle: gdal-3.8.4              # R6 answer id
  status: pass
emits: [vrt, vrt-url, mdim-vrt, zarr-attrs, stac]
source: cases/cryosat2-sea-ice-cryptic-curvilinear
```

Rules:

- Keyed by sha256 and array, never by path, so it follows content.
- Only asserted fields appear; an absent field means "as stored".
- Evidence is required. A record without evidence is a hypothesis and is
  emitted only on request.
- One record can be superseded, never edited; a wrong historical
  assertion (the UCSD VRTs, `out.tif`) is kept as a record with failing
  evidence.
- Emission is a projection: the same record yields a classic VRT, a
  `vrt://` string (`a_srs`, `a_ullr`, `a_nodata`, `a_scale`,
  `a_offset`), an mdim.vrt, Zarr attributes (zarr-conventions `spatial:`
  and `proj:`) for a virtual store, or a STAC asset patch.

The format belongs with storecard, which already defines assertion; the
fixtures set holds a copy of the records it checks and the GDAL answers.
Which repo is canonical is open (section 9).

## 6. Usage pipelines

| Problem class | Pipeline | Ends in |
|---|---|---|
| Regular grid in costume (A, C, D, E) | card (R1) -> fit or documented claim -> assertion -> emit mdim.vrt or `vrt://` -> open | osgeo.gdal, GDAL xarray backend, wxy, browser |
| Same, as a store | refs (R3) + assertion as Zarr attributes -> virtual Zarr (flat table, kerchunk, Icechunk) | any Zarr reader that honours `spatial:`/`proj:`; plain Zarr readers get correct values with naive placement, which the page shows |
| Many files of one product (the bowerbird collection) | header-only sniff -> card -> group by fingerprint -> one assertion per group | the problem-class counts the TODO asks for |
| Model grids (H, displaced pole) | refs + coordinates as arrays -> geolocation warp (rwarp) to a regular grid | a resampled copy, stated as such |
| Not a grid | table view -> GeoParquet points or profiles | DuckDB, the vector pages |
| Cost problems | card `cost` -> decide copy or not; a rechunked copy is named as a copy | a decision, recorded |

The first pipeline is the general one, and it is cheap: the bytes stay
where they are, the assertion is a few hundred bytes, and every reader
downstream gets the right answer without detecting anything.

## 7. Browser pages, grouped by shared problem

Each page loads the files of its group, and for each array shows three
panels: as stored (array order, no georeferencing), as a naive reader
places it, and as asserted. The difference between the last two is the
lesson. Where a file is not redistributable, the page uses a synthetic
twin built to the same header (as storecard's fixtures do) and says so.

| Page | Shared problem | Cases | What the page shows |
|---|---|---|---|
| 1 Upside down and sideways | row order and axis order | nsidc no-coords, RegCM south-up, GPM DPR, AVISO MDT, LAEA globe, fast ice | a flip and transpose toggle; the transform sign that would have said it |
| 2 Cryptic curvilinear | 2D lon/lat hiding a projected grid | CryoSat-2, NHSCE, MESAN, CORDEX stripped, regional example1, fast ice, LAEA globe | stored points over the fitted grid; residual map; EPSG:3031 vs 3412 on CryoSat-2 |
| 3 Mercator in lon/lat clothing | Mercator-spaced latitude | AVISO, ACC fronts, UCSD topo, COCO | latitude spacing plot; features displaced up to 19.5 degrees when read as lon/lat |
| 4 Rotated pole | rotated frames, labelled and stripped | rotated-pole-as-lonlat (`out.tif` in the Atlantic), CORDEX stripped, MESAN, regional encodings, RegCM LCC | the two frames side by side; cross and dot points |
| 5 Grids in no frame | tripolar and displaced pole | CM2.1, COCO | nominal 1D axes vs true 2D positions |
| 6 Values that lie | fill, sentinels, packing, flags | TOPEX, AVISO MDT 9999, ACC fronts NaN as 0, ensemble members as variables | value histograms before and after the asserted fill |
| 7 Not a grid | DSG and ids as coordinates | Argo, WOD, DSG timeseries, catchment ids | what GDAL makes of them vs the table view |
| 8 Bytes without a header | raw binary made a store by assertion | UCSD topo, fast ice | the refs table and the assertion that make a headerless file readable in the browser |
| 9 Cost | chunking and size | SILO rain, E-OBS, UKCP18 truncated | bytes fetched per band, from the card, and what a rechunked copy would cost |

Reading in the browser: netCDF3 headers are simple enough for a small JS
parser; netCDF4 members go through refs (the browser refs explorer
pattern) or mdim.vrt (web PR #20). Pages 1 to 3 cover 15 of the 31 cases
and need no new reader beyond that, so they come first.

All pages need bytes on a CORS-enabled host. None of the 143 files is
marked redistributable yet, so page work waits on the blob store or uses
twins.

## 8. Order of work

| Stage | Work | Needs |
|---|---|---|
| S0 (done) | inventory, pilot scan of v0.0.12, this plan | nothing |
| S1 | R0 to R2 over every file in the release bundles, recorded as `rasterwise/` in fixtures, on GDAL 3.8.4 and current | nothing (release bundles are public) |
| S2 | assertion records for the understood cases, R6 checks | the record format agreed |
| S3 | R3 and R4 for netCDF3, netCDF4 and raw members | refharvest, a netCDF3 header reader |
| S4 | pages 1 to 3 | published bytes or twins |
| S5 | pages 4 to 9, gallery page in docs | S4 |
| later | the bowerbird collection survey by fingerprint | the header-only mode of `harvest.py` |

## 9. What do we get, what does it cost, what if we didn't

- **Get**: a measured answer to "how much of the old world reads now",
  per rung and per GDAL version; every `how_to_read` turned into a
  checked, emittable assertion; evidence that most legacy problems are a
  few hundred bytes of metadata away from modern; browser pages that
  teach the problems by showing them; a test corpus for wxy's readers and
  for storecard's detector that is real data, not synthetic.
- **Cost**: one fixtures set and its answers; assertion records for 25
  understood cases; nine pages, three of them early. No new crate.
- **If we didn't**: the cases stay prose, checked once against one GDAL;
  the lessons stay in the archive instead of in the formats and pages
  people now use; and new stores keep repeating them.

## 10. Open questions

1. Canonical home of the assertion record format: storecard (which
   defines it) with fixtures holding checked copies, or fixtures first.
   Recommended: storecard, keyed to the rasterwise manifest.
2. Bytes for the pages: the blob store's public URL and per-file
   redistributability, or synthetic twins for the `no` rows.
   Recommended: twins for `no`, real bytes for public products once
   `url` is set.
3. Whether the Zarr v3 `transpose` codec is worth measuring as a refs-only
   fix for lon-major arrays, or whether dimension roles in attributes are
   enough.
4. Whether HDF4 (one MODIS file now, more in the bowerbird collection)
   warrants a refs reader, or stays GDAL-only.
5. Whether the ACC fronts NaN-as-0 behaviour should become a minimal
   reproducer for GDAL (tracked in the OSGeo upstream tracker, not here).
