# CRS coverage: terrio-crs against proj4rs for wxylib's cases

Status: measured 2026-10-28. A watch note, not a decision. Changing the
CRS backend in core belongs to the planning track.

## 1. Question

wxylib's warp, points and zonal commands reach CRSs through rwarp's
`proj4rs` backend (core pins proj4rs 0.1.10 with `crs-definitions`). That
accepts `EPSG:NNNN` codes and PROJ strings only. The question here is which
of the CRS cases wxylib actually meets would be covered if
[`terrio-crs`](https://crates.io/crates/terrio-crs) sat behind the same
trait instead, or alongside it.

## 2. Cases

35 cases, chosen from what wxylib's data, docs and design notes use:

- **EPSG, polar:** Antarctic and Arctic polar stereographic (3031, 3412,
  3413, 3976, 9354).
- **EPSG, other:** Australian Albers and Lambert (3577, 3112), UTM 55S,
  Web Mercator, EASE-Grid 2.0 (6933).
- **Datum steps:** GDA94 to GDA2020, and NAD83 to NAD27 UTM.
- **PROJ strings:** polar and oblique laea and aeqd, polar stere and gnom,
  CF rotated pole (`ob_tran`), ortho, geostationary satellites (Himawari,
  GOES), MODIS sinusoidal, world maps (moll, eqearth, robin, igh, eqc),
  and perspective views (tpers, nsper).
- **Input forms:** EPSG:3031 as WKT2, WKT1 and PROJJSON, `OGC:CRS84` as
  the source, and `ESRI:102020`.

The oracle is PROJ 9.8.1 through pyproj 3.8.0, with the network off and no
extra grids. Each case is one point forward and PROJ's result back.
"Exact" means within 1 mm both ways.

## 3. Results

| case | group | proj4rs 0.1.10 | proj4rs 0.3.0 | terrio-crs 0.1.0 | terrio-crs main | terrio-crs main+fallback |
|---|---|---|---|---|---|---|
| 3031 | epsg-polar | exact | exact | exact | exact | exact |
| 3412 | epsg-polar | exact | exact | exact | exact | exact |
| 3413 | epsg-polar | exact | exact | exact | exact | exact |
| 3976 | epsg-polar | exact | exact | exact | exact | exact |
| 9354 | epsg-polar | exact | no | exact | exact | exact |
| 3577 | epsg-other | exact | exact | exact | exact | exact |
| 32755 | epsg-other | exact | exact | exact | exact | exact |
| 3857 | epsg-other | exact | exact | exact | exact | exact |
| 6933 | epsg-other | no | exact | exact | exact | exact |
| 3112 | epsg-other | exact | exact | exact | exact | exact |
| 4283-7844 | datum | OFF 1.51 m inv 1.51 m | OFF 1.51 m inv 1.51 m | exact | exact | exact |
| 4269-26711 | datum | no | no | exact | exact | exact |
| laea-south | proj-polar | no | exact | exact | exact | exact |
| laea-north | proj-polar | exact | exact | exact | exact | exact |
| aeqd-south | proj-polar | exact | exact | exact | exact | exact |
| aeqd-oblique | proj-local | exact | exact | exact | exact | exact |
| stere-south | proj-polar | exact | exact | exact | exact | exact |
| ob_tran-cordex | proj-rotated | no | no | exact | exact | exact |
| ortho | proj-local | no | exact | exact | exact | exact |
| geos-himawari | proj-sat | exact | exact | exact | exact | exact |
| geos-goes | proj-sat | exact | exact | exact | exact | exact |
| sinu-modis | proj-world | no | exact | exact | exact | exact |
| moll | proj-world | exact | exact | exact | exact | exact |
| eqearth | proj-world | no | exact | exact | exact | exact |
| robin | proj-world | no | exact | exact | exact | exact |
| igh | proj-world | no | no | no | exact | exact |
| eqc | proj-world | OFF 2.38e+04 m inv 2.38e+04 m | OFF 2.38e+04 m inv 2.38e+04 m | exact | exact | exact |
| gnom-south | proj-polar | no | exact | exact | exact | exact |
| tpers | proj-local | no | exact | no | exact | exact |
| nsper | proj-local | no | exact | no | exact | exact |
| 3031-wkt2 | form | no | no | exact | exact | exact |
| 3031-projjson | form | no | no | no | no | no |
| 3031-crs84 | form | no | no | exact | exact | exact |
| 102020-esri | form | no | no | exact | exact | exact |
| 3031-wkt1 | form | no | no | exact | exact | exact |

| engine | exact | off | refused |
|---|---:|---:|---:|
| proj4rs 0.1.10 (what core uses) | 16 | 2 | 17 |
| proj4rs 0.3.0 | 24 | 2 | 9 |
| terrio-crs 0.1.0 (crates.io) | 31 | 0 | 4 |
| terrio-crs main (9ca108f, 2026-10-28) | 34 | 0 | 1 |

The fallback feature changes nothing on these cases at main.

## 4. What terrio-crs would have covered

Compared with what core uses today (proj4rs 0.1.10), terrio-crs main adds:

- **Input forms wxylib already meets:** WKT1, WKT2, `OGC:CRS84` and ESRI
  codes. GeoZarr's `proj:wkt2`, CF's `crs_wkt` and GeoTIFF-derived WKT
  would resolve without a lookup table of our own. The CLI help says WKT2
  and PROJJSON wait on a PROJ-backed CRS; terrio-crs would provide WKT2
  without PROJ, and PROJJSON once the fix below lands.
- **Datum steps:** GDA94 to GDA2020 is exact (proj4rs is 1.5 m off,
  because it hubs through WGS84), and NAD83 to NAD27 resolves where
  proj4rs needs a grid it does not have.
- **Projections proj4rs 0.1.10 lacks:** polar laea at exactly
  `lat_0=-90`, CF rotated pole (`ob_tran`), ortho, sinu, eqearth, robin,
  igh, gnom, tpers and nsper, EASE-Grid 2.0, and ellipsoidal eqc (proj4rs
  is 24 km off at 42S).
- **Output:** `to_projjson()` and `to_wkt()`. Today `wxy-geozarr` refuses
  to write a CRS given as a PROJ string, because it has no `proj:` form for
  it; these would supply one.

proj4rs 0.3.0 closes much of the projection gap (polar laea, ortho, sinu,
eqearth, robin, gnom, tpers, nsper, EASE-Grid 2.0). It still takes no WKT,
PROJJSON or ESRI input, has no `ob_tran` or igh, and still hubs datums
through WGS84. Its move to `crs-definitions` 0.6 also loses EPSG:9354
(IBCSO polar stereographic), which 0.1.10 resolved.

The one case nothing passed: PROJJSON for EPSG:3031. terrio-crs main
refuses the axis `meridian` member that PROJ writes for polar CRSs
("unsupported PROJJSON: unsupported member 'meridian'"). That is a small,
specific fix to offer upstream.

## 5. What it costs

- **Footprint:** about 50 crates natively (58 with the fallback), against a few for
  proj4rs. terrio-crs embeds EPSG and ESRI tables.
- **A second engine:** rwarp's backend trait takes one implementation;
  wxylib would choose per build or per CRS. Keeping proj4rs as the small
  default and terrio-crs as the full one is the obvious split.
- **Pace:** terrio-crs main moved from 31 to 34 of these 35 cases in
  three days. Pin by revision and rerun this table at each check.

## 6. Reproduce

`scripts/crs_coverage/`: `make_cases.py` writes `cases.json` with PROJ's
answers; `harness/` is a Rust binary with a cargo feature per engine
(`p01`, `p03`, `tc`, `tc-fb`; terrio-crs main via a path or git override,
in a separate build because features unify); `judge.py` prints the grid
above from the `r-*.jsonl` result files.
