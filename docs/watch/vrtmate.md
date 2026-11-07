# Watch: VRTMate (Postholer)

Status: tracking note, 2026-11-07, for `VRTMate.js` as served on
2026-11-07 (Last-Modified 2026-01-02). Checked at the monthly landscape
refresh with [rewrites.md](rewrites.md) area E.
Source: <https://www.postholer.com/portfolio/notebook/VRTMate/> and
<https://www.postholer.com/portfolio/resource/VRTMate.js> (K. Scott
Parks, Postholer; no licence stated, so nothing here copies its code).
Context: [m25](../m25-vrt-engine.md) section 2 (VRT readers outside
GDAL), [m29](../m29-vrt-reimagined.md) (placements, tiers, name
mapping), core `crates/vrt-model`, web `www/vrt.html`, `mdim.html`,
`vrt-vector.html`.
Scripts: [scripts/vrtmate](../../scripts/vrtmate).

## 1. Summary

1. **VRTMate is a footprint index read from a classic VRT, in the
   browser.** One JavaScript class (206 lines, no dependencies) fetches a
   `.vrt`, turns the XML into a generic object, and for each source keeps
   the file path and a world bounding box computed from `DstRect` and the
   VRT's `GeoTransform`. `rastersByBBox` returns the sources that meet a
   query box. It reads no pixels, and its page says it does not process a VRT the
   way GDAL does: it retrieves file paths and the overall and per-raster
   spatial information only.
2. **It is one third of a serverless map.** The companion Serverless page
   draws Leaflet layers with three classes: FGBMate (FlatGeobuf vectors),
   COGMate (one COG per layer, through georaster) and VRTMate. On each
   map move, VRTMate lists the USGS 1/3 arc-second DEM tiles in the
   viewport and COGMate adds or removes one layer per tile. The VRT is
   used as a catalogue, not as a raster: each COG is drawn from its own
   header.
3. **It is one of several readers that take the same narrow cut of a
   VRT: source boxes from `DstRect` and `GeoTransform`, and the paths.**
   vaster's `extent_vrt()` (R, MIT) returns the boxes as a matrix,
   VRTMate (2026-01-02) adds paths and a box query in the browser, and
   deck.gl-raster's `parseVRT` (2026-11-02) does the same to draw each
   COG with its own georeferencing. maplibre-gl-raster's `parseVrt`
   accepts only VRTs where that cut is exact. None of them reads what
   the VRT says to do with the pixels (resampling, scaling, NODATA,
   `SrcRect`), so each is a catalogue reader rather than a VRT reader.
4. **For wxylib it confirms a use rather than adding a technique.** The
   most common job asked of a VRT outside GDAL is "which sources are in
   this box, and what URL do I fetch", and it has been written at least
   four times. `vrt-model` can already answer the first in
   pixel space, but not from a world box, and it does not map
   `/vsicurl/` or `/vsis3/` names to fetchable URLs. Those are the two
   pickups (section 4).

## 2. What it does

| Piece | Behaviour |
|---|---|
| Input | an `http(s)` URL to a classic `.vrt`, fetched whole and parsed with `DOMParser` into a generic element/attribute object |
| Dataset info | `GeoTransform` split into six numbers, `rasterXSize`, `rasterYSize`, overall box and centre; EPSG taken as the last `"EPSG","n"` in the `SRS` text |
| Sources | the first band holding any of `ComplexSource`, `SimpleSource`, `AveragedSource`, `NoDataFromMaskSource`, `ArraySource`, `MaskedBand`, `KernelFilteredSource`; per source: sequence number, box from `DstRect`, pixel size, path from `SourceFilename`, a sort key from the box corner |
| Query | `rastersByBBox({bbox, bands}, limit)`: sources whose box meets the query box, filtered by band number |
| Paths | returned as written (`/vsicurl/https://...`). The caller turns them into URLs with a hand-set `prefix` and an `Array.slice` of the path parts (`basenameSlice`) |
| Not read | `SrcRect`, `relativeToVRT`, scaling, NODATA, resampling, nested VRTs, overviews, mdim, vector, `vrt://` |

## 3. Checked against the USGS 1/3 arc-second VRT

`USGS_Seamless_DEM_13.vrt` as served on 2026-11-07: 830,253 bytes, one
band, 1,449 sources (the page's example says 1,430, so tiles have been
added since), all `ComplexSource resampling="bilinear"`, all
`/vsicurl/` with `relativeToVRT="0"`, `SrcRect` covering each whole
tile, no overviews.

**Tiers (m29 section 4).** With `measurements/m29-vrt-rework/tiers.py`:
all 1,449 placements are T3 as written, because every `DstRect` offset
is fractional. Snapped at 0.15 px, 1,422 become T2 (whole tiles that
overlap their neighbours) and 27 stay T3. This is the 1 arc-second
finding of m29 again at 1/3 arc-second: the VRT asserts a bilinear
sub-pixel shift that the tiles do not need. A reader that draws each COG
from its own header, as VRTMate with COGMate does, shows the snapped
(T2) picture, not the one the VRT describes. Three browser readers make
three different choices on this file: VRTMate and deck.gl-raster ignore
the shift, maplibre-gl-raster refuses VRTs that reposition sources, and
GDAL resamples. The m29 tier classifier would report which choice is
exact, with its reason.

**Box test.** `rastersByBBox` treats two boxes as meeting when a corner
of one lies inside the other. That misses the crossing case, where a
tall narrow box passes through a wide one and neither holds a corner of
the other. `scripts/vrtmate/bbox.py` repeats the test against a plain
interval overlap on 2,000 random boxes over CONUS for each shape:

| Query shape | Queries missing at least one tile | Tiles missed |
|---|---|---|
| map-like, 1 to 8 deg wide, aspect 0.5 to 2 | 2 (0.1%) | 2 of 72,101 (0.00%) |
| phone portrait, 0.5 to 2 deg wide, 2 to 2.5 times taller | 77 (3.9%) | 82 of 16,426 (0.50%) |
| strips, 0.2 to 1 deg wide, 3 to 10 deg tall | 775 (38.8%) | 3,893 of 21,373 (18.2%) |

On a desktop map the gap is invisible; on a narrow viewport it shows as
missing tiles. Any wxylib box query should use interval overlap, and the
crossing case belongs in a corpus test.

**From reading the code (not run).** A band with a single source is
stored as an object, not an array, so it yields no rasters; a band that
mixes source kinds keeps only the last kind in the list; an `SRS`
written as WKT2 (`ID["EPSG",4269]`), as a PROJ string or without an
EPSG code makes the EPSG regex fail; the `GeoTransform` terms 2 and 4
are labelled offsets but are the rotation terms, so a rotated VRT gives
wrong boxes; `SrcRect` is ignored, so a source cropped by `SrcRect` is
listed with the box of its `DstRect` but fetched whole.

## 4. What wxylib could pick up

| # | Pickup | Where | Size | Why |
|---|---|---|---|---|
| P1 | World-box source query: invert the `GeoTransform`, take the pixel window, run `plan_band`, return each source with its world box and the window it supplies | `vrt-model` (and its wasm export in web) | small | the job vaster, VRTMate, deck.gl-raster and maplibre-gl-raster each wrote; `vrt-model` has the pixel-space planner but no world-box entry point. Interval overlap, `SrcRect` and nested VRTs come for free from the planner |
| P2 | `Dsn` to fetchable URL: `/vsicurl/https://...` to `https://...`, `/vsis3/b/k` to an endpoint URL from configuration, `relativeToVRT` resolved against the VRT's own URL | `vrt-model` `dsn.rs` | small | replaces VRTMate's hand-set `prefix` and `basenameSlice`; it is the browser row of m29's name mapping (GDAL VSI, fsspec, object_store, Icechunk, dsn) |
| P3 | Corpus cases: a 4-source excerpt of the 1/3 arc-second VRT (fractional `DstRect`, bilinear) with tier and box-query answers, including a crossing query | `fixtures/vrt` | small | gives the tier classifier and P1 a real 3DEP case with known answers |
| P4 | A footprint view in `vrt.html`: draw each placement's box, colour by tier, list the URLs a box needs | web | medium | the demo VRTMate's page makes, with the tier reason that none of the browser readers show; waits on P1 and P2 |

Not picked up: the generic XML-to-object shape (`vrt-model` has a typed
model), the corner test, and the Leaflet and georaster rendering, which
is a consumer of P1 rather than part of it.

## 5. Refresh

At the monthly landscape check, with rewrites.md area E: re-read the
`Last-Modified` of `VRTMate.js` and of the Notebook index
(<https://www.postholer.com/portfolio/>). A change in what the class
reads (`SrcRect`, nested VRTs, mdim) is a new row in m25 section 2; a
change in the USGS VRT (offsets snapped, overviews added) is a rerun of
section 3.

## 6. Log

### 2026-11-07

First note. `VRTMate.js` (Last-Modified 2026-01-02) and the VRTMate and
Serverless notebook pages read; USGS 1/3 arc-second VRT measured for
tiers and the box test. Row added to m25 section 2 and an entry to
rewrites.md section 7.
