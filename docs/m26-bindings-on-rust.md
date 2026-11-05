# m26: R and Python bindings on the Rust crates

Status: musing with decisions, 2026-11-05. It settles the open part of
m24 section 9, item 1 (bindings onto the Rust crate) and places wxylib's
own `wxy` packages beside the foundation packages. Based on
hypertidy/controlledburn at main (R 0.3.2.9000, Python 0.4.0 on the
crate), hypertidy/rwarp at main (crate 0.3.2, `rwarp-r` 0.1.0.9000),
hypertidy/bigcurve at main (R 0.6.0, header frozen), crates.io
(controlledburn 0.2.4, rwarp 0.3.2, bigcurve 0.3.0) and wxylib/r and
wxylib/py at their main branches.

## Summary

The question is whether the R and Python packages over controlledburn,
bigcurve and rwarp should build from the Rust crates that are now the
canon, in what order, what happens to the C++ cores, and how wxylib's own
`wxy` R and Python packages relate to them. Nothing here changes a
package; it sets the route and its gates.

- **Half of it has already happened.** Python controlledburn builds from
  the crate (controlledburn#38, parity mode, byte-identical to the old C++
  binding on the 240 canonical cases). rwarp's R package was born on the
  crate (`rwarp-r`, extendr). bigcurve-rs is the canon, and the R move is
  filed (bigcurve#16). What is left is R controlledburn, R bigcurve, the
  C++ cores, and a few shared conventions.
- **The R move for controlledburn is small.** The R package calls one
  native entry point, `cpp_scanline_burn`, through a 185-line cpp11 shim.
  Everything else in R is R code. The crate already returns the same four
  tables (runs, edges, lines, points) plus notes, and the Python binding
  shows the column mapping. The risk is the build (vendored crates,
  offline cargo, the Windows toolchain, the rustc version on CRAN's
  machines), not the code.
- **rwarp-r is the route test.** Its first CRAN submission is in progress
  (rwarp#42, win-builder submitted 2026-11-05, 5.3 MB with vendored
  crates). Whatever it meets, the other two will meet. It also answers
  the feasibility check that wxylib's commit criterion 3 asks for (crate
  size, rustc version, build time), at no extra cost.
- **Recommendation: a gated sequence.** controlledburn 0.3.2 goes to CRAN
  on the C++ core as planned (due 16 Nov). R controlledburn moves to the
  crate in its next release, after rwarp-r has cleared CRAN, in parity
  mode with the same API and the canonical tables as the acceptance test.
  The `f64` fraction change follows once, in all bindings together.
  bigcurve R moves last. The C++ cores stop being built by any binding
  and stay only as checked references until nobody needs them.
- **wxylib's `wxy` packages stay separate and bind wxy crates directly.**
  Rust has no stable ABI, so R packages cannot share compiled Rust
  through `LinkingTo:`; each package links its own copy. The packages
  meet through data (plain data frames, Arrow tables), not through
  linking. `wxy` grows the verbs that carry I/O (stores, plans, warp from
  a source); in-memory warp, burn and densify belong to rwarp,
  controlledburn and bigcurve.

## 1. Where each package stands

| package | language | engine today | native surface | status |
|---|---|---|---|---|
| controlledburn (R) | R, cpp11 | C++ core (1515 lines) + vendored exactextract (132 KB) | one `.Call`: `cpp_scanline_burn` | CRAN 0.3.1; 0.3.2 fixes the GCC 16 `-Warray-bounds` WARN, due 16 Nov (controlledburn#34) |
| controlledburn (Python) | PyO3 0.30, maturin | crate 0.2.4 | `burn_wkb`, `burn_wkb_arrow`, `bbox_wkb`, `bbox_wkb_arrow`, `materialize` | merged (controlledburn#38); not on PyPI, parked until the R release (controlledburn#22) |
| rwarp (R) | extendr-api 0.7 | crate 0.3.2, `proj-sys` 0.27 | `warp_plan`, `warp_exec`, `warp_resample`, `pixel_transform`, `crs_describe` | first CRAN submission in progress (rwarp#42) |
| bigcurve (R) | R, cpp11 | frozen C++ header (205 lines), PROJ injected | densify family | CRAN 0.6.0; move filed as bigcurve#16, gated on one package clearing CRAN with extendr |
| wxy (R) | extendr-api 0.9 | wxy crates at core 39b07bb (before rwarp 0.3) | `wxy_regular`, `wxy_affine`, `wxy_warp` | spike, not for CRAN yet |
| wxy (Python) | PyO3 0.30, abi3-py39 | wxy crates at core 39b07bb | same three verbs | spike, not for PyPI yet |

Minimum Rust versions declared on crates.io: controlledburn and bigcurve
1.70, rwarp 1.86. rwarp-r's `SystemRequirements` now says rustc >= 1.86,
which matches.

## 2. The questions

1. Does R controlledburn move onto the crate, and when?
2. In what order do the three R packages move?
3. What happens to the C++ cores?
4. When does the `f64` fraction change (controlledburn#24 item 8, rwarp
   design/decisions.md) land, relative to the R move?
5. How do wxylib's `wxy` packages relate to the per-crate packages?
6. Which conventions are shared across the Rust-built packages?

## 3. The R route (questions 1 and 2)

### Option A: a gated sequence (recommended)

1. **controlledburn 0.3.2 to CRAN on the C++ core.** No build change
   before the 16 Nov deadline. The fix is ready (controlledburn#35).
2. **rwarp-r clears CRAN.** "Cleared" means accepted, then a clean first
   round of CRAN's own checks on every flavour, Windows and macOS
   included. If it stalls on PROJ (the >= 9.6.2 requirement on a
   builder) rather than on Rust, the Rust parts still count as proven.
3. **R controlledburn onto the crate**, as the release after 0.3.2
   (0.4.0). The shim is replaced by an extendr function that takes the
   WKB list, the grid and the mode, calls
   `BurnOptions::parity(mode)` (no coalescing), and returns the same four
   data frames and the notes. R's API, defaults and column types stay as
   they are. Acceptance: the testthat suite unchanged, plus a test that
   reads `fixtures/canon-tables.txt` and matches every record, as the
   Python binding does. The `src/` C++ files leave the R build.
4. **One schema change, `f64` fractions** (section 5), in the crate's
   next minor release, with R and Python following together.
5. **bigcurve R onto the crate** (bigcurve#16), copying rwarp-r's PROJ
   linkage. `ellipsoid = TRUE` moves from R geographiclib to the crate's
   `geodesic` feature.
6. **Python controlledburn to PyPI** after step 3, since its sequencing
   follows the R release. controlledburn#22 was written for the CMake
   build and needs rewriting for maturin: wheels are pure Rust, so
   `maturin-action` or cibuildwheel builds them without repair, and the
   sdist problem (core outside `python/`) goes away because the crate
   comes from crates.io.

What we get: one implementation behind every language, R gains what so
far exists only in Rust (`CoverageWindow`, `Measure`, coalescing, crop in
the core, the crate's materializer), and the port tax ends. Each step
risks one thing at a time: the deadline release changes no build, the
new package proves the build, and the established package moves only
once the build is proven. Cost: a CRAN review of a changed build for an
established package, Rust in the R package's system requirements, a
larger source tarball (vendored crates; controlledburn has no
dependencies, so this is mostly extendr's), and waiting on a review queue
we do not control. If we did not gate: a first Rust build for an
established package would meet the review under a deadline, and a
problem would block the fix CRAN asked for.

### Option B: move R controlledburn now, inside 0.3.2

Fewer releases, and R gains the Rust features sooner. But it
mixes a requested fix with a new build system under a deadline, and the
first Rust build CRAN sees from this family would be on a package with
users. Not recommended.

### Option C: keep the C++ core for R indefinitely

This is what m20 assumed before Python moved. Nothing changes for R
users, and the canonical tables keep the port honest. But every feature
is written twice, R never gets the Rust-only features without a port, and
the `f64` change needs the C++ core to change in step. With Python
already on the crate, R would be the only reason the C++ core is still
built. Not recommended, unless CRAN refuses the Rust build outright.

### Option D: one R package for everything

Fold burn, densify and warp into `wxy`, or into one hypertidy package.
One build and one vendored tree. But it breaks the three existing CRAN
packages and their users, and it puts no-I/O engines inside a package
whose purpose is I/O (m20 section 2). Not recommended.

### If the route fails

If CRAN's Rust policy or a builder blocks rwarp-r for a long time,
controlledburn is the cleaner test case: no PROJ, no system
dependencies, so a failure there is about Rust alone. In that case, swap
steps 2 and 3, or stay on option C for R while Python carries the
crate.

## 4. The C++ cores (question 3)

| core | after its R package moves | retired when |
|---|---|---|
| controlledburn `cpp/` | not built by R or Python; the canonical-table check stays in CI as a reference for C++ readers | no `LinkingTo:` user or C++ consumer has appeared after one release cycle; then archive `cpp/` with a note |
| bigcurve `src/bigcurve.h` | removed from the R build; `canon/check.cpp` kept only if still useful (bigcurve#16 asks the same) | at bigcurve#16 |

The no-FMA lesson stays recorded where it was learnt (controlledburn
NEWS, the `no_fma.h` header). The Rust crates never fuse, so it does not
travel with the move.

## 5. The `f64` fraction change (question 4)

Fractions are `f32` today in the crate, the C++ core, R and Python.
rwarp's exact footprint works in `f64` and rounds only for
compatibility. The change alters the output schema in every binding, so
it should happen once.

Recommended: after R moves (step 4 above). Then it is one crate release
(0.3.0) and two binding releases that change a column type, with no C++
core to change in step. That also settles the condition in rwarp's
decisions.md ("if the C++ sibling can follow"): it no longer has to.
Doing it before the R move would mean changing the C++ core once more,
only to retire it.

## 6. wxylib's own packages (question 5)

| option | what it means | verdict |
|---|---|---|
| **A. separate packages, meeting through data** (recommended) | `wxy` R and Python bind wxy crates directly; wxy crates depend on rwarp, controlledburn and bigcurve as Rust crates; the R and Python packages exchange plain tables | keeps every existing package intact; no ABI coupling |
| B. `wxy` R imports rwarp R, controlledburn R at the R level | `wxy` calls their R functions | ties wxy's release to three CRAN packages and still compiles the same crates twice, since wxy's Rust needs them anyway |
| C. `wxy` as the only binding | the per-crate packages are retired | breaks existing users (option D above) |

Rust has no stable ABI, so a compiled crate cannot be shared between R
packages the way a C++ header is shared through `LinkingTo:`. Each
package links its own copy, and two packages loaded together carry two
copies of, say, controlledburn. That is fine: they are small, and they
are kept in step by version. What matters is that the data they return
agree, which the canonical tables already guarantee.

The division of surface that follows from m20:

- **rwarp, controlledburn, bigcurve** own the in-memory engines: warp a
  matrix, burn geometry into tables, densify edges.
- **wxy** owns the verbs that carry I/O or stored plans: open a store or
  refs table, plan and run a warp from a source to a GeoZarr, zonal
  statistics over a source, weights files. `wxy_warp` on an in-memory
  matrix stays as a spike, and does not grow into a second rwarp R API.
- **Interchange** is the controlledburn table shape (runs, edges, lines,
  points, with each language's usual index base) and
  Arrow for anything large. A `controlledburn::burn()` result should be a
  valid `wxy` input and the reverse; that is a test to write when `wxy`
  first takes one.

The spikes stay pinned at core 39b07bb until they gain a verb that
needs a newer core (m06 recheck, still open). For CRAN or PyPI, `wxy`
would also need its crates either published to crates.io or vendored
from git; `cargo vendor` handles git dependencies, so publishing is not a
prerequisite.

## 7. Shared conventions (question 6)

Decide once, apply to every Rust-built R and Python package:

| convention | proposal |
|---|---|
| R binding | extendr. rwarp-r is on 0.7 and `wxy` on 0.9; do not change rwarp-r before acceptance, then move both to the newest release that has cleared CRAN, and start controlledburn R and bigcurve R there |
| Python binding | PyO3 0.30 with maturin, as both controlledburn and `wxy` already use; abi3 wheels where the binding allows it (`wxy` already builds abi3; check whether controlledburn's numpy dependency allows it before PyPI) |
| crate source | crates.io versions only in anything bound for CRAN or PyPI; git pins only in spikes |
| vendoring | rwarp-r's `tools/vendor.sh` and Makevars pattern, copied, with the tarball size stated in `cran-comments.md` |
| rustc | declare each crate's minimum in `SystemRequirements`; keep controlledburn and bigcurve at 1.70 unless a dependency forces more, since a lower floor costs nothing and widens CRAN's reach |
| PROJ | `proj-sys` at the same version in rwarp-r and bigcurve R, so both link libproj the same way |
| acceptance | parity mode first, then features; every move is byte-identical on its canonical tables before anything new is exposed |

## 8. Order of work

1. controlledburn 0.3.2 to CRAN (maintainer, by 16 Nov).
2. rwarp-r: win-builder result, `cran-comments.md`, release version,
   submit (rwarp#42, maintainer).
3. When rwarp-r has cleared: controlledburn R onto the crate, as a PR on
   hypertidy/controlledburn. Done when testthat and the canonical-table
   test pass on the R-CMD-check matrix and on win-builder.
4. controlledburn crate 0.3.0 with `f64` fractions; R and Python follow
   in one PR.
5. bigcurve#16.
6. controlledburn#22 rewritten for maturin, then TestPyPI, then PyPI.
7. The `wxy` spikes: pin bump when they gain a verb that needs it, and
   an extendr version aligned with step 3.

## 9. Decisions for the maintainer

1. **The R route** (section 3): option A, the gated sequence
   (recommended); B, move inside 0.3.2; C, keep the C++ core for R.
2. **When the C++ controlledburn core is retired** (section 4): after
   one release cycle with no C++ consumer (recommended), or kept
   indefinitely as a reference.
3. **`f64` fractions after the R move** (section 5): recommended.
4. **`wxy` stays separate and meets the others through data** (section
   6): recommended; taken provisionally.
5. **Shared conventions** (section 7): taken provisionally.
