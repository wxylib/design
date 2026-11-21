# m34: The suite, reviewed

Status: assessment, 2026-11-21. A review of every wxylib repository and
the crates beside it, five weeks after the first foundation assessment
(m06) and four after its recheck (m06 section 8). It proposes an order of
work in section 7 and leaves three choices open in section 8. Based on
wxylib/core at `61de824`, design at `7702fb3`, fixtures at `3000119`,
docs at `fd61fb4`, web at `0875241`, images at `d82ad08`, py at
`0018cdc`, r at `24cb3cc`, refharvest at `4932c52`, wxylib/async-hdf5 at
`5754c09`, hypertidy/bigcurve-rs at `0e8ff60`, and the crates.io releases
rwarp 0.5.0, controlledburn 0.3.3, bigcurve 0.3.0, proj4rs 0.3.1 and
terrio-crs 0.2.4. Builds on m06, m09, m20, m25, m26, m31, m32 and the
[commit criteria](commit-criteria.md).

## Summary

- **The foundation holds.** Core's CI is green on main, there is no open
  pull request in any repository, and every reader still answers the same
  as GDAL on the fixtures. The reference-table path (read a byte-reference
  table directly, cache inside, checked on live BRAN2023 and GHRSST
  stores) is the strongest thing wxylib has, and since the recheck it has
  gained a scale fix, the byterefs/0.1 identifier, a second harvester
  (`refharvest`) and a CI fixture shaped like the real archive.
- **Building has stopped and thinking has not.** Core took 23, 28, 19 and
  23 commits in its first four weeks, 2 in the fifth and none in the
  sixth. Design took 52 to 59 a week through the middle of that period.
  Eighteen musings (m16 to m33) and ten watch notes were written in four
  weeks; of the fifteen from m19 on, about half led to merged code.
- **The layer below moved on without us.** rwarp went from 0.3.1 to 0.5.0
  and controlledburn from 0.3.1 to 0.3.3 in three weeks. Core still builds
  on rwarp 0.3.1, and everything a user touches (the browser pages, the
  images, the R and Python packages) is pinned behind core in turn.
- **The commit test is half closed.** Criterion 1 is met and in CI.
  Criterion 2 is shown by bytes read but not by rows compared. Criterion 3
  (an R user without Rust) has not started. Criterion 4 (no new format) is
  holding, and the format moved to a neutral home (byterefs/spec), which
  is the best thing that could have happened to it; four musings now each
  carry something that could become a format if written carelessly.
- **The pieces nobody else has are still mostly unbuilt.** What was built
  first of the VRT engine is the family three other projects already read
  (classic mosaics). The view-to-chunk planner, measured at 5.6 to 8.5
  times fewer bytes for polar and antimeridian views, has no code.
- **Recommended order:** catch up (one short block), close the commit
  test, then build the unbuilt modules one at a time, with a pause on new
  musings until three open ones are picked up or closed.

## 1. Where everything stands

![Which release or commit each part of the suite builds on, and how far
behind it is](img/m34-pins.svg)

| Repository | State | Last change | Open |
|---|---|---|---|
| core | 13 crates, about 19,700 lines with tests; CLI verbs `warp`, `points`, `zonal`; CI green | 13 Nov (#37) | issues #27 (LERC codec), #28 (COG writer, COPC reads, when needed) |
| fixtures | 12 sets; `oracle-case/0` format with per-version GDAL answers; VRT, warp-grid and rasterwise sets | 8 Nov (#19) | none |
| design | docs 01 to 05, m01 to m33, ten watch notes, eleven measurement folders | 19 Nov (#92, a watch check) | issues #29 (blog follow-up), #56 (proj-core column) |
| docs | site at wxylib.org/docs: five examples, nine explainers, four how-tos | 6 Nov (#30) | sidebar stops at m29 |
| web | eight pages: COG warp, Sentinel-2, vector, BRAN, edit canvas, mdim VRT, vector VRT, VRT explorer | 10 Nov (#27) | none |
| images | `wxy`, `wxy-py`, `wxy-r` on GHCR | 5 Nov (#10) | CLI image 25 core commits behind |
| py, r | spikes that bind an in-memory warp | 5 Nov (pin bumps) | no source change since 17 Oct |
| refharvest | stage 1: HDF5 chunk rows identical to libhdf5, on the wxylib async-hdf5 fork | 16 Nov (#7) | issues #5 (TIFF stage 2), #2 (third oracle) |
| async-hdf5 (fork) | v3 attributes, dense attributes, level-parallel walk; fold-back upstream pending | 2 Nov (#5) | fold-back not yet negotiated |
| bigcurve-rs | 0.3.0 on crates.io, geodesic placement, canon tables | 5 Nov (#9) | none |

Outside wxylib but underneath it: rwarp 0.5.0 (18 Nov) and controlledburn
0.3.3 (19 Nov).

## 2. What changed since the recheck

Against m06 section 8 (core `4b74450`, 2026-10-22); core has taken 48
commits and 22 merges since.

**Built.**

- The warp moved down. `wxy-resample` and the chunk planner left core;
  every warp method runs through rwarp, which now owns chunk planning, the
  exact retry and the geolocation inverse (core #24 to #26). This is m20's
  first move, done.
- The reference path hardened. `RefsStore` holds 22.8 million references
  in 3.0 GB instead of about 21 GB; a plain `--dry-run` reports stored
  bytes for a table; the synthetic Bluelink fixture runs in CI (core #31,
  fixtures #16). `wxy-refs` accepts byterefs/0.1 and applies the table's
  default target (core #35, #36). A 403 on an absent key reads as absent
  (core #18), which made the Copernicus Marine comparison pass.
- Two geo-free crates appeared in the core workspace: `oracle-case`
  (questions apart from per-version answers; core #30) and `vrt-model`
  (classic VRT and `vrt://` model and planner, 32 of 32 reads identical to
  GDAL; world-box footprints and a fetch URL added in core #34).
- A CRS backend trial: `terrio-crs` behind a feature, 34 of 35 cases
  against proj4rs's 24 (core #32).
- controlledburn 0.3.1 in zonal statistics, with each feature burned as
  one multipolygon (core #37).
- A harvester outside core: `refharvest` on a forked async-hdf5, a 5.3 GB
  BRAN file walked in 21 s instead of 690 s.
- Three browser pages for VRT (mdim, vector, explorer), merged range
  requests for COG tiles (92 requests and 30 s down to 13 and 7 s), and
  an edit canvas.

**Decided, not built.** byterefs position (m32, eight choices waiting on
the implementers' meeting); bindings on Rust (m26, the gated R route);
conservative weights as files and a verb (m20 section 8, m21); warp
output-grid rules (m28; the fixture set exists, the rule does not).

**Written, nothing built.** m22 (array plan IR), m29 (VRT reimagined),
m30 (legacy corpus, beyond a pilot fixture set), m31 (view-to-chunk
planner), m33 (warp meshes).

**Moved underneath.** rwarp 0.4.0 took controlledburn 0.3 into its API;
0.5.0 added whole ocean-model grids as mesh sets, world-coordinate
measures for curvilinear sources, and threads. controlledburn 0.3.3
added first moments for second-order conservative remapping. proj4rs
0.3.1 and terrio-crs 0.2.4 are out. None of this is in core.

**Activity, commits a week on main** (ISO weeks, merges included):

| Week of | core | design | docs | web | fixtures |
|---|---|---|---|---|---|
| 12 Oct | 23 | 9 | 38 | 10 | 30 |
| 19 Oct | 28 | 52 | 18 | 10 | 11 |
| 26 Oct | 19 | 59 | 20 | 22 | 8 |
| 2 Nov | 23 | 56 | 2 | 15 | 16 |
| 9 Nov | 2 | 14 | 0 | 2 | 0 |
| 16 Nov | 0 | 4 | 0 | 0 | 0 |

Since 13 Nov the only commits anywhere in wxylib are watch checks and
housekeeping.

## 3. What is stale

Pins and versions:

| What | Builds on | Current | Missing as a result |
|---|---|---|---|
| core | rwarp 0.3.1 | 0.5.0 | mesh sets, threads, the cheaper antimeridian split, world-area exact footprint |
| core | controlledburn 0.3.1, and 0.2.4 through rwarp | 0.3.3 | one copy instead of two; first moments |
| core | proj4rs 0.3.0; terrio-crs 0.2.2 | 0.3.1; 0.2.4 | point releases, contents not checked here; a retest of the pole workaround in `crs.rs` |
| core CI | fixtures `aed9d1e` | `3000119` | the rasterwise set and BRAN oracle hashes |
| web | core `14aa692` | `61de824`, 10 commits on | byterefs/0.1 tables, zonal fix |
| images, CLI | core `caba7b2` | 25 commits on | everything from core #29 to #37: the 3 GB store, byterefs/0.1, the terrio-crs feature, footprints |
| py, r | core `caba7b2` | 25 commits on | nothing a user would see: they bind the warp only |
| refharvest | async-hdf5 fork `0c2ad80`; object_store 0.13 | fork `5754c09`; core is on object_store 0.14 | lint fixes only; the object_store gap matters the day the two meet in one build |

Pages that no longer say what is true:

- The commit criteria page is dated 2026-10-22 and still lists criterion
  1's CI case as open. It closed with core #31 on 2026-11-05. (Corrected
  with this document.)
- The design README's musing statuses were checked on 2026-10-28. Five
  were wrong by this review: m06, m09, m24, m25 and m27. (Corrected with
  this document.)
- Doc 03's crate table still lists `wxy-resample` and a `wxy info` verb,
  and has no row for `wxy-refs`, `wxy-cache`, `wxy-predictor`,
  `vrt-model` or `oracle-case`.
- The docs site sidebar stops at m29, and nothing on the site mentions
  the VRT crate, the oracle harness or byterefs.

## 4. The commit test

| # | Criterion | Now | What closes it |
|---|---|---|---|
| 1 | Reads the table directly, cache inside, BRAN checked against GDAL | **Met**, and the many-chunks-per-file case is in CI | nothing |
| 2 | Reads a table from a producer wxylib does not own | **Shown by bytes, not by rows.** Unchanged since 2026-10-22 | one producer's rows equal to the fixture rows on offset, size and presence. This is now cheap: `refharvest` gives a second, independent set of rows for the same files, so a three-way comparison (fixture, raad.virtualize, refharvest) is one script |
| 3 | An R user reads a table without Rust, or the R surface is declared not the goal | **Not started.** The R and Python packages still bind only an in-memory warp, which the rwarp packages now own (m26) | a decision first (section 8, choice 1), then either a CRAN feasibility check or a sentence in the criteria page |
| 4 | No new file format | **Holding.** The table is byterefs/0.1 in a repository wxylib does not own, and wxylib's stated position is reader, second producer, fixtures and oracle, owning no format (m32) | the per-axis chunk edges of m10 agreed in byterefs/spec before any wxylib code writes them |

Criterion 4 has new pressure from four directions. Each is sound as an
idea and each becomes a format the moment wxylib writes it to disk on its
own terms:

- the conservative weights file pair (m20 section 8);
- the plan as a table (m29);
- assertion records keyed by sha256 (m30);
- the warp mesh contract (m33).

The rule that has worked so far is the one to keep: spec first, in a home
wxylib does not own, or an existing form (ESMF weights netCDF, STAC, the
mesh spec annex m33 already names) before a new one.

**Reading.** wxylib is past "is this a strong reader": it is. Whether it
is the engine now rests on criteria 2 and 3, and neither needs new
design. Both have waited a month behind work that was more interesting.

## 5. The guardrail: are we overbuilding

The aim is modules that do not yet exist, not GDAL parity. Each part of
the suite against that:

| Part | Exists elsewhere? | Verdict |
|---|---|---|
| `wxy-refs` with `wxy-cache` inside | No. Other readers go through Icechunk or kerchunk | Keep, and keep it small (2,300 lines). It is the crate held to "own every line" |
| `refharvest` | Parsers exist (async-hdf5, async-tiff); the row contract, fetch plan and walk cost record do not | Keep geo-free and separate, as it is. Do not write parsers |
| `oracle-case` | No | Already has no wxy dependency. It is its own crate in all but address |
| `vrt-model`, classic family | **Yes**: deck.gl-raster, maplibre-gl-raster, terrio and OxiGeo each read classic mosaics | Enough is built. Stop adding to the classic family |
| `vrt-model`, mdim and vector families, `vrt://` keys as translate flags | No | This is the part worth building, and it is the part not started |
| View-to-chunk planner (m31) | No. Viewers use one box and one mean scale | Unbuilt. The clearest missing module in the suite |
| Operation registry (m09) | No, as a geo-free crate | Unbuilt. Becomes timely before a fourth CLI verb: `main.rs` is one 2,000-line file for three verbs |
| `wxy-warp` | Mostly rwarp now | **Shrink.** 3,600 lines of source remain. m20 named `cover.rs` and `rasterize.rs` (700 lines together) as belonging below; rwarp 0.5's mesh module and controlledburn 0.3's relations now cover both. After the bump, what should be left is the glue: domain mappings, plans, fetch, CRS choice |
| `wxy-virtual` (Icechunk sink) | Icechunk itself, VirtualiZarr | Keep as an optional sink, off the default path. It carries the heaviest dependency tree in the workspace and is not on any read path that matters |
| `wxy-predictor` | No zarrs TIFF predictor codec elsewhere | Keep; a candidate to offer to zarrs when a second predictor is wanted |
| py, r | The warp they bind now has its own packages (rwarp) | As they stand they duplicate a neighbour. Either they bind what is unique to wxylib (open a source, read a table) or they stay parked |
| Watch notes | n/a | Ten notes and a twice-weekly check. Worth having; too frequent for what it changes (section 7, step 6) |

Two patterns worth naming:

- **We built the familiar half first.** In the VRT engine, and earlier in
  the warp, the first thing written was the part with a GDAL oracle ready
  to hand, which is also the part others already have. The oracle makes
  that work safe and quick; it does not make it the missing module. The
  check for each new stage should be "who else reads this", asked before
  the first line, not only "does a crate exist".
- **Parity work migrated to where it belongs.** rwarp tracks GDAL 3.14's
  warper, kernel by kernel, and that is right for a warp kernel crate.
  Core no longer carries that weight. The remaining parity surface in
  core is the readers (COG, Zarr, tables), which is small and is the test,
  not the goal.

## 6. What the suite uniquely has, in one list

Ranked by how sure the evidence is that nobody else has it and somebody
wants it:

1. A byte-reference table read directly, at archive scale, checked
   against GDAL on live stores, with the cache in the reader. Built.
2. Harvest at 30 times the stock speed with the cost recorded as
   metadata. Built for HDF5; TIFF is next.
3. A view-to-chunk planner for any CRS. Measured, not built.
4. An oracle format that keeps questions apart from per-version answers.
   Built; three of the twelve fixture sets use it (`cog`, `warpgrid`,
   `rasterwise`).
5. mdim and vector VRT read without GDAL, with `vrt://` keys for both.
   Prototyped in JavaScript on three browser pages; no Rust model.
6. Conservative weights as plain values and files. The values exist in
   rwarp; the files and verb do not exist in wxylib.

Items 3, 5 and 6 are where new code goes. Items 1, 2 and 4 are where the
existing code needs consolidating so that others can use it.

## 7. Recommended order of work

**Step 1. Catch up.** One short block, mechanical, before anything else.

- core onto rwarp 0.5, controlledburn 0.3.3, proj4rs 0.3.1 and
  terrio-crs 0.2.4; remove from `wxy-warp` what rwarp's mesh module and
  controlledburn's relations now do; retest the pole workaround.
- Then the pins, in order: core's fixtures pin, web, the CLI image, py and
  r, the py and r images.
- Doc 03's crate table and the docs sidebar.
- Get: every surface a user touches runs the code the documents describe;
  `wxy-warp` shrinks; mesh sets and threads are there for step 4.
- Cost: rwarp 0.4 was a breaking release, so this is a real port, not a
  version edit; one oracle run to confirm values (the exact footprint
  over geolocation sources changes by design).
- Without it: each later step starts by discovering this one.

**Step 2. Close the commit test.**

- Criterion 2: the three-way row comparison (fixtures, raad.virtualize,
  refharvest) on OISST and the BRAN month, recorded in fixtures.
- Criterion 3: take choice 1 in section 8, then do what it says.
- Get: the question the first month was run to answer, answered.
- Cost: small. The row check is a script; the R decision is a paragraph
  or a feasibility check of a day or two.
- Without it: the commitment question is answered by default, which the
  criteria page was written to prevent.

**Step 3. The view-to-chunk planner (m31).** `rwarp::view` beside
`source_window`, exported to wasm, with a thin `zarr.html` on top.

- Get: the suite's clearest missing module, small and with no I/O, and a
  Zarr viewer as the picture that explains it.
- Cost: it lives in rwarp, so it needs a go-ahead there; BRAN has no
  overviews, so the viewer is honest only on stores that have them.
- Without it: viewers keep reading 5 to 8 times the bytes at the poles
  and the seam, and the measurement stays a document.

**Step 4. The VRT families nobody else reads.** mdim and vector models
and planners in `vrt-model`, their corpus moved onto `oracle-case`, the
three browser pages switched from hand-written JavaScript to the wasm
build.

- Get: the claim of m25 made true (four families, one model), and
  `oracle-case` used by a second and third fixture set.
- Cost: mdim answers must be recorded through the fixtures answers
  workflow, since a current osgeo.gdal does not install in the cloud
  sessions.
- Without it: `vrt-model` is a fourth classic-mosaic reader.

**Step 5. One registry, then one verb.** The operation registry of m09
as a geo-free crate, `warp`, `points` and `zonal` moved onto it, then
`wxy weights` (m21) as the first verb written against it. refharvest
stage 2 (TIFF tile rows, refharvest #5) fits beside this step and feeds
criterion 2 for COG stores.

- Get: the fourth verb costs a registration, not another 600 lines of
  `main.rs`; bindings and the browser can list operations instead of
  mirroring them by hand.
- Cost: a refactor of a working CLI with no new capability on the day it
  lands.
- Without it: each verb is written three times (CLI, R, Python) and the
  three drift.

**Step 6. Housekeeping that buys attention back.**

- A pause on new musings until three of the open ones are picked up or
  closed. Nine still read as open, with decision sections waiting: m09, m25, m27, m28,
  m29, m30, m31, m32 and m33. A single pass over those nine, answering
  each with the recommended default or "not now", clears most of them.
- The watch check from twice weekly to weekly. In the last two weeks it
  produced the only commits in the organisation, and none changed a plan.
- Extract `oracle-case` and `vrt-model` to their own repositories when
  step 4 lands (with the VRT corpus on `oracle-case`), not before: both are already free of wxy dependencies,
  and neither should be offered to anyone until the unique half exists.

## 8. Choices left open

1. **The R and Python surface.** (a) Rebind py and r to what is unique
   to wxylib (open a source, read a table, plan and explain), leave the
   in-memory warp to the rwarp packages, and run the CRAN feasibility
   check on that; (b) declare the R surface not the goal: R users reach
   the tables through GDAL, zaro and the rwarp packages, and py and r
   stay parked as spikes; (c) wait for rwarp's R package to clear CRAN
   and decide then. Recommended: (c) for the CRAN question, since that
   submission is the cheapest route test there is, and (a) as the
   direction, because bindings that duplicate rwarp's are the one thing
   that should not be kept.
2. **What leads after the catch-up.** The order above puts the commit
   test (step 2) before the planner (step 3) and the VRT families
   (step 4). Steps 3 and 4 are independent of each other and of step 2,
   and either could lead if a use calls for it.
3. **Whether rwarp moves into wxylib.** Still pending from the first
   week. The last month argues against: rwarp, controlledburn and
   bigcurve released more than a dozen versions between them while wxylib's pins
   stood still, and that independence is what let them move.
   Recommended: leave them in hypertidy and treat "wxylib keeps up with
   the movement layer" as a standing task instead.

## 9. Follow-up (2026-11-21)

Steps 1 and 2 were started the same day.

- **Step 1.** Core builds and passes its suite on rwarp 0.5.0,
  controlledburn 0.3.3, proj4rs 0.3.1 and terrio-crs 0.2.4 with no source
  change ([core #38](https://github.com/wxylib/core/pull/38)); the port
  expected in section 7 was not needed, because core uses none of the
  types rwarp 0.4 changed. `cover.rs` and `rasterize.rs` stay:
  `rasterize.rs` is GDAL's centre and all-touched rule behind the default
  zonal mode, and controlledburn's exact all-touched is a different rule,
  so dropping it changes default values; `cover.rs` is the comparison
  the non-affine example is built on. Section 5's "shrink" for `wxy-warp`
  is a choice about defaults, not a clean-up.
- **Criterion 2.** The live Bluelink `temp` table from raad.virtualize
  equals the BRAN fixture on all 97,920 rows
  ([fixtures #20](https://github.com/wxylib/fixtures/pull/20)). Left: a
  never-written chunk from an outside producer.
- **Criterion 3.** A wxylib R package that reads tables vendors 356
  crates, 36.6 MB compressed, against CRAN's 5 MB. CRAN is out for it
  whatever happens to rwarp's own submission. Choice 1 in section 8 is
  decided on that evidence: the R surface is declared not the goal. R
  users read the tables through GDAL and zaro and warp through the rwarp
  R package, and wxylib/r stays a parked spike. Criterion 3 closes by
  declaration, which the test allows.

## 10. What we get, what it costs, what if we didn't

- Get: the suite brought back to one state (code, pins and pages
  agreeing), the commitment question answered on evidence, and the next
  three builds chosen because nobody else has them.
- Cost: a block of unglamorous work first, and a pause on the thing that
  has been most productive lately, which is writing musings.
- Without it: wxylib drifts into a design archive over a core that is
  two releases behind its own foundation, and the modules that were the
  point stay measured and unbuilt.
