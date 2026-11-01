# Watch: pyinterp conservative regridding

Status: tracking note, 2026-11-01, for pyinterp 2026.11.0 (CNES, C++ with
Python bindings, BSD-3-Clause). Checked at the monthly landscape refresh
with [rewrites.md](rewrites.md).
Context: [m21](../m21-conservative-examples.md) (rwarp conservative
weights in wxylib), [m20](../m20-movement-crates.md) section 8, rwarp
`design/conservative.md`, [04 landscape](../04-landscape.md) section 9.
Script: [scripts/pyinterp_vs_rwarp](../../scripts/pyinterp_vs_rwarp).

## 1. Summary

1. **pyinterp 2026.11.0 ships first-order conservative regridding between
   rectilinear grids**, from NumPy (`pyinterp.regrid.conservative`) and
   from xarray (`da.pyinterp.regrid`). Cells are lon/lat boxes bounded by
   meridians and parallels; areas are on the sphere, or exact on an
   ellipsoid through the authalic latitude. The default normalisation is
   the mean over the covered part (ESMF `fracarea`, xESMF
   `conservative_normed`), with an optional minimum covered fraction.
2. **It is built on separable weights.** The overlap of two lon/lat boxes
   is the product of a longitude overlap and an overlap in sin(latitude),
   so the 2D weights are the tensor product of two sparse 1D CSR
   matrices, applied one axis at a time. No 2D weight table is formed.
   This is the structure m21 found for axis-aligned pairs (item 1 of its
   recommendations) and proposed for rwarp; pyinterp is a working
   implementation with published timings.
3. **On the cells both libraries define the same way, rwarp and pyinterp
   agree to 1.3e-15** (section 3). That makes pyinterp a light,
   pip-installable oracle for rwarp's spherical measure on lon/lat boxes,
   next to ESMF, which draws great-circle edges and so differs by design.
4. **The scope is narrow on purpose.** Rectilinear grids only: no
   projected, rotated, curvilinear or mesh cells, and the weights are not
   exposed as a table. Everything else rwarp's weights cover (m21 E2 to
   E5) stays with rwarp and ESMF.

## 2. What else 2026.11.0 carries that touches wxylib

| Feature | What it is | Relevance |
|---|---|---|
| Outer-product interpolation (`bivariate_outer` and friends) | bilinear, IDW and nearest at all combinations of 1D target coordinates; each coordinate is located once per axis | the separable case of rwarp's kernels for rectilinear to rectilinear; reported 10x over point by point |
| Reduced Gaussian grids | ECMWF reduced Gaussian interpolation from parallels, counts and values, no GRIB library; a `Zone` holds the flat index ranges a box or track needs, computed before any value is read | a mesh-like source the curvilinear and mesh stages could test against; the `Zone` is a planned extraction (byte ranges from geometry) in the bytes-in-place sense |
| Optional xarray, dask, numba | NumPy is the only required dependency | an oracle that installs in seconds in CI |
| Periodic longitudes in regridding | source and target can use different conventions ([0, 360) and [-180, 180)) | an explicit periodic-axis option; rwarp's weights get the seam from the transformer |

## 3. Measured against rwarp

Global regular lon/lat to regular lon/lat, field `2 + cos^2(lat) cos(2 lon)`
(amplitude 1), rwarp main at 56d2297 with `lonlat_measure` and
`FracArea`, pyinterp 2026.11.0 with cell bounds, on the same 4-core cloud
container.

| Case | max abs difference | rwarp weights + apply | rwarp entries | pyinterp (1 thread; all) |
|---|---|---|---|---|
| 1 deg to 5 deg, sphere | 1.3e-15 | 3 ms + 2 ms | 64,800 | 0.25 ms; 0.23 ms |
| 0.25 deg to 1 deg, sphere | 1.3e-15 | 54 ms + 37 ms | 1,036,800 | 4.4 ms; 3.5 ms |
| 0.25 deg to 1 deg, pyinterp on WGS84 vs rwarp sphere | 3.2e-7 | | | 4.4 ms; 3.3 ms |

- The agreement is rounding: both measure exact box overlaps on the
  sphere, rwarp through controlledburn's `Measure::CosLatitude` and the
  general polygon path, pyinterp through two 1D overlaps.
- The speed gap (about 20x here) is the separable shortcut, not code
  quality: rwarp clips every destination cell as a polygon and stores
  16 entries per destination cell; pyinterp stores two short 1D
  matrices. The gap grows as the coarsening ratio squared (m21 measured
  650 entries per cell at 0.01 to 0.25 degrees).
- The ellipsoid changes this smooth field by 3.2e-7 of its amplitude at
  1 degree. Small next to the great-circle versus parallel difference
  pyinterp reports against ESMF (2e-5 at 1 degree, 4e-4 at 5 degrees),
  which matches rwarp's own ESMF oracle (rwarp `design/conservative.md`
  section 5.1).

## 4. What to borrow

| # | Idea | Where | Cost | If not |
|---|---|---|---|---|
| B1 | A separable weights type: two 1D CSR overlap matrices, recognised when source and destination are both axis-aligned in the same CRS, expanded to the `Weights` table only on request | rwarp `weights` (m21 recommendation 1) | one module; the 1D overlap is a sort and a sweep | E1 global stays a 16 GB table; pyinterp stays 20x faster on the commonest case |
| B2 | An authalic-latitude measure for boxes: replace sin(lat) by q(lat)/q(90) | controlledburn `Measure`, box case only | a few lines for axis-aligned cells; general edges need quadrature, since x weighted by the ellipsoid area element has no closed form | spherical areas only, a 3e-7 effect at 1 degree; fine for now |
| B3 | A minimum covered fraction on apply | rwarp `ApplyOptions` | one option | callers mask by `dst_covered` themselves |
| B4 | A fast path for rows with no missing values (fraction known from the axis coverage) | rwarp `Weights::apply` | small | none needed until apply is profiled |
| B5 | pyinterp as a second conservative oracle for the lon/lat box case, at 1e-14, beside ESMF for great circles | fixtures `oracles` workflow; rwarp `tests/esmf.rs` pattern | a pip install and one script (this note's) | box cases are checked only against rwarp's own closed form |

## 5. Not taken

- **The rectilinear-only engine as wxylib's regridder.** It cannot carry
  rotated, projected, curvilinear or mesh cells, which are the reason
  rwarp's weights exist. B1 keeps its speed for the case it covers.
- **Weights hidden inside the apply.** wxylib wants weights as values
  (files, `wxy weights`, m20 section 8). A separable type should still
  write the ESMF-style table on request.

## 6. Log

- **2026-11-01.** Note started from the 2026.11.0 release (changelog,
  `cxx/include/pyinterp/regrid/conservative.hpp`, `pyinterp/regrid.py`
  read from source). Section 3 measured with
  [scripts/pyinterp_vs_rwarp](../../scripts/pyinterp_vs_rwarp). The
  release announcement on the Pangeo forum was not reachable from the
  cloud session; the changelog was used instead.
