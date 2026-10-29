//! Footprint experiments: rwarp's exact footprint (controlledburn per
//! destination pixel) against alternatives, weights-only, one band, mean.

use controlledburn::{burn, BurnOptions, Coord, Geometry, GridSpec, Polygon};
use rwarp::Transformer;
use std::time::{Duration, Instant};

pub struct Src<'a> {
    pub data: &'a [f32],
    pub ncol: usize,
    pub nrow: usize,
}

#[derive(Default, Debug, Clone, Copy)]
pub struct Split {
    pub transform: Duration,
    pub cover: Duration,
    pub reduce: Duration,
    pub cells: u64,
    pub points: u64,
}

/// Per-pixel densified rings, all transformed in one call per row, exactly
/// as rwarp 0.2 builds them.
pub fn ring_points(dst_ncol: usize, row: usize, d: usize, xs: &mut Vec<f64>, ys: &mut Vec<f64>) {
    xs.clear();
    ys.clear();
    let y0 = row as f64;
    for c in 0..dst_ncol {
        let x0 = c as f64;
        for k in 0..d {
            let t = k as f64 / d as f64;
            xs.push(x0 + t);
            ys.push(y0);
        }
        for k in 0..d {
            let t = k as f64 / d as f64;
            xs.push(x0 + 1.0);
            ys.push(y0 + t);
        }
        for k in 0..d {
            let t = k as f64 / d as f64;
            xs.push(x0 + 1.0 - t);
            ys.push(y0 + 1.0);
        }
        for k in 0..d {
            let t = k as f64 / d as f64;
            xs.push(x0);
            ys.push(y0 + 1.0 - t);
        }
    }
}

/// rwarp 0.2's `area_row_exact`, weights only, with the time split into
/// transform, controlledburn, reduce.
pub fn cb_per_pixel(t: &impl Transformer, src: &Src, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let (ncol, nrow) = (src.ncol as i64, src.nrow as i64);
    let per = 4 * d;
    let (mut xs, mut ys) = (Vec::new(), Vec::new());
    for row in 0..dst_nrow {
        ring_points(dst_ncol, row, d, &mut xs, &mut ys);
        let t0 = Instant::now();
        let ok = t.transform(true, &mut xs, &mut ys);
        sp.transform += t0.elapsed();
        sp.points += xs.len() as u64;
        for c in 0..dst_ncol {
            let r = c * per..(c + 1) * per;
            if !ok[r.clone()].iter().all(|&v| v) {
                continue;
            }
            let t1 = Instant::now();
            let mut ring: Vec<Coord> = xs[r.clone()].iter().zip(&ys[r]).map(|(&x, &y)| Coord::new(x, -y)).collect();
            let (mut minx, mut maxx, mut miny, mut maxy) = (f64::INFINITY, f64::NEG_INFINITY, f64::INFINITY, f64::NEG_INFINITY);
            for p in &ring {
                minx = minx.min(p.x);
                maxx = maxx.max(p.x);
                miny = miny.min(-p.y);
                maxy = maxy.max(-p.y);
            }
            let c0 = (minx.floor() as i64).max(0);
            let c1 = (maxx.ceil() as i64).min(ncol);
            let r0 = (miny.floor() as i64).max(0);
            let r1 = (maxy.ceil() as i64).min(nrow);
            if c0 >= c1 || r0 >= r1 {
                continue;
            }
            ring.push(ring[0]);
            let grid = GridSpec::new(c0 as f64, -(r1 as f64), c1 as f64, -(r0 as f64), (c1 - c0) as u32, (r1 - r0) as u32);
            let Ok(res) = burn(&[Geometry::Polygon(Polygon::new(vec![ring]))], &grid, BurnOptions::coverage()) else { continue };
            let t2 = Instant::now();
            sp.cover += t2 - t1;
            let at = |row: i32, col: i64| ((r0 + row as i64) * ncol + c0 + col) as usize;
            let (mut s, mut w) = (0.0f64, 0.0f64);
            for run in &res.runs {
                for col in run.col_start..run.col_end {
                    s += src.data[at(run.row, col as i64)] as f64;
                    w += 1.0;
                    sp.cells += 1;
                }
            }
            for e in &res.edges {
                if e.fraction > 0.0 {
                    s += e.fraction as f64 * src.data[at(e.row, e.col as i64)] as f64;
                    w += e.fraction as f64;
                    sp.cells += 1;
                }
            }
            if w > 0.0 {
                out[row * dst_ncol + c] = (s / w) as f32;
            }
            sp.reduce += t2.elapsed();
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Signed-area accumulation (FreeType "gray" / font-rs style).
// ---------------------------------------------------------------------------

/// Dense window of `(area, cover)` cells for one polygon. Each boundary
/// piece in cell `(i, j)` adds `(xm - (i + 1)) * dy` to `area` and `dy` to
/// `cover`; a cell's signed coverage is then its `area` minus the cover of
/// everything left of it in its row. Exact for straight segments, any
/// simple ring, no traversal chaining, no allocation once warm.
#[derive(Default)]
pub struct Accum {
    pub c0: i64,
    pub r0: i64,
    pub w: usize,
    pub h: usize,
    area: Vec<f64>,
    cover: Vec<f64>,
}

impl Accum {
    pub fn reset(&mut self, c0: i64, c1: i64, r0: i64, r1: i64) {
        self.c0 = c0;
        self.r0 = r0;
        self.w = (c1 - c0) as usize;
        self.h = (r1 - r0) as usize;
        let n = self.w * self.h;
        self.area.clear();
        self.area.resize(n, 0.0);
        self.cover.clear();
        self.cover.resize(n, 0.0);
    }

    #[inline]
    fn put(&mut self, xm: f64, ym: f64, dy: f64) {
        // A piece on the window's far wall (x = c1 exactly) belongs to the
        // last column: on a wall x = k a piece adds the same to cell k
        // whether it is booked to cell k - 1 or k, so clamping is exact as
        // long as the area term uses the clamped column.
        let li = (xm.floor() as i64 - self.c0).clamp(0, self.w as i64 - 1);
        let lj = (ym.floor() as i64 - self.r0).clamp(0, self.h as i64 - 1) as usize;
        let i = (self.c0 + li) as f64;
        let k = lj * self.w + li as usize;
        self.area[k] += (xm - (i + 1.0)) * dy;
        self.cover[k] += dy;
    }

    /// Add segment p -> q, split at every integer x and y crossing.
    pub fn segment(&mut self, (x0, y0): (f64, f64), (x1, y1): (f64, f64)) {
        let (dx, dy) = (x1 - x0, y1 - y0);
        if dy == 0.0 {
            return; // horizontal pieces carry neither area nor cover
        }
        let (mut kx, sx) = if dx > 0.0 { (x0.floor() + 1.0, 1.0) } else if dx < 0.0 { (x0.ceil() - 1.0, -1.0) } else { (f64::NAN, 0.0) };
        let (mut ky, sy) = if dy > 0.0 { (y0.floor() + 1.0, 1.0) } else { (y0.ceil() - 1.0, -1.0) };
        let mut t = 0.0f64;
        loop {
            let tx = if sx != 0.0 { (kx - x0) / dx } else { f64::INFINITY };
            let ty = (ky - y0) / dy;
            let tn = tx.min(ty).min(1.0);
            if tn > t {
                let tm = 0.5 * (t + tn);
                let (xm, ym) = (x0 + tm * dx, y0 + tm * dy);
                self.put(xm, ym, (tn - t) * dy);
            }
            if tn >= 1.0 {
                break;
            }
            if tx <= tn {
                kx += sx;
            }
            if ty <= tn {
                ky += sy;
            }
            t = tn;
        }
    }

    /// Resolve to signed coverage in place (stored in `area`).
    pub fn resolve(&mut self) {
        for j in 0..self.h {
            let mut acc = 0.0;
            for i in 0..self.w {
                let k = j * self.w + i;
                let c = self.cover[k];
                self.area[k] -= acc;
                acc += c;
            }
        }
    }

    #[inline]
    pub fn coverage(&self) -> &[f64] {
        &self.area
    }
}

/// Signed area of a ring (`ring[0]` not repeated), y down.
fn ring_sign(xs: &[f64], ys: &[f64]) -> f64 {
    let n = xs.len();
    let mut a = 0.0;
    for k in 0..n {
        let k1 = (k + 1) % n;
        a += 0.5 * (xs[k] + xs[k1]) * (ys[k1] - ys[k]);
    }
    a
}

/// Coverage of one ring into `acc`, then the mean of `src` over it.
#[inline]
fn accum_ring(acc: &mut Accum, src: &Src, rx: &[f64], ry: &[f64], sp: &mut Split) -> Option<f32> {
    let t1 = Instant::now();
    let (mut minx, mut maxx, mut miny, mut maxy) = (f64::INFINITY, f64::NEG_INFINITY, f64::INFINITY, f64::NEG_INFINITY);
    for (&x, &y) in rx.iter().zip(ry) {
        minx = minx.min(x);
        maxx = maxx.max(x);
        miny = miny.min(y);
        maxy = maxy.max(y);
    }
    if !(minx.is_finite() && maxx.is_finite() && miny.is_finite() && maxy.is_finite()) {
        return None;
    }
    let (ncol, nrow) = (src.ncol as i64, src.nrow as i64);
    let c0 = minx.floor() as i64;
    let c1 = (maxx.ceil() as i64).max(c0 + 1);
    let r0 = miny.floor() as i64;
    let r1 = (maxy.ceil() as i64).max(r0 + 1);
    if c1 <= 0 || c0 >= ncol || r1 <= 0 || r0 >= nrow {
        return None;
    }
    acc.reset(c0, c1, r0, r1);
    let n = rx.len();
    for k in 0..n {
        let k1 = if k + 1 == n { 0 } else { k + 1 };
        acc.segment((rx[k], ry[k]), (rx[k1], ry[k1]));
    }
    acc.resolve();
    let sgn = if ring_sign(rx, ry) < 0.0 { -1.0 } else { 1.0 };
    let t2 = Instant::now();
    sp.cover += t2 - t1;
    let (mut s, mut w) = (0.0f64, 0.0f64);
    let cov = acc.coverage();
    // Only the window rows/cols inside the buffer.
    let (ja, jb) = ((r0.max(0) - r0) as usize, (r1.min(nrow) - r0) as usize);
    let (ia, ib) = ((c0.max(0) - c0) as usize, (c1.min(ncol) - c0) as usize);
    for j in ja..jb {
        let srow = ((r0 + j as i64) * ncol + c0) as usize;
        let crow = &cov[j * acc.w..(j + 1) * acc.w];
        for i in ia..ib {
            let f = sgn * crow[i];
            if f > 1e-9 {
                s += f * src.data[srow + i] as f64;
                w += f;
                sp.cells += 1;
            }
        }
    }
    sp.reduce += t2.elapsed();
    if w > 0.0 { Some((s / w) as f32) } else { None }
}

/// Per-pixel rings transformed as rwarp does, coverage by accumulation.
pub fn accum_per_pixel(t: &impl Transformer, src: &Src, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let per = 4 * d;
    let (mut xs, mut ys) = (Vec::new(), Vec::new());
    let mut acc = Accum::default();
    for row in 0..dst_nrow {
        ring_points(dst_ncol, row, d, &mut xs, &mut ys);
        let t0 = Instant::now();
        let ok = t.transform(true, &mut xs, &mut ys);
        sp.transform += t0.elapsed();
        sp.points += xs.len() as u64;
        for c in 0..dst_ncol {
            let r = c * per..(c + 1) * per;
            if !ok[r.clone()].iter().all(|&v| v) {
                continue;
            }
            if let Some(v) = accum_ring(&mut acc, src, &xs[r.clone()], &ys[r], sp) {
                out[row * dst_ncol + c] = v;
            }
        }
    }
    out
}

/// The destination lattice transformed once: each row line as a real
/// scanline (so an approximate transformer can interpolate it), plus the
/// interior points of the column lines. Every corner and edge point is
/// transformed once instead of two to four times.
pub struct Lattice {
    pub d: usize,
    pub ncol: usize,
    top: (Vec<f64>, Vec<f64>, Vec<bool>),
    bot: (Vec<f64>, Vec<f64>, Vec<bool>),
    /// Column line c, interior point k (1..d), at `c * (d - 1) + k - 1`.
    vert: (Vec<f64>, Vec<f64>, Vec<bool>),
}

impl Lattice {
    fn line(t: &impl Transformer, ncol: usize, d: usize, y: f64) -> (Vec<f64>, Vec<f64>, Vec<bool>) {
        let n = ncol * d + 1;
        let mut xs: Vec<f64> = (0..n).map(|k| k as f64 / d as f64).collect();
        let mut ys = vec![y; n];
        let ok = t.transform(true, &mut xs, &mut ys);
        (xs, ys, ok)
    }

    pub fn new(t: &impl Transformer, ncol: usize, d: usize) -> Self {
        let top = Self::line(t, ncol, d, 0.0);
        Lattice { d, ncol, top, bot: (vec![], vec![], vec![]), vert: (vec![], vec![], vec![]) }
    }

    /// Prepare row `row`: its bottom line and column-line interiors.
    pub fn row(&mut self, t: &impl Transformer, row: usize) {
        if row > 0 {
            std::mem::swap(&mut self.top, &mut self.bot);
        }
        self.bot = Self::line(t, self.ncol, self.d, row as f64 + 1.0);
        let d = self.d;
        if d > 1 {
            let mut xs = Vec::with_capacity((self.ncol + 1) * (d - 1));
            let mut ys = Vec::with_capacity(xs.capacity());
            for c in 0..=self.ncol {
                for k in 1..d {
                    xs.push(c as f64);
                    ys.push(row as f64 + k as f64 / d as f64);
                }
            }
            let ok = t.transform(true, &mut xs, &mut ys);
            self.vert = (xs, ys, ok);
        }
    }

    pub fn points(&self) -> usize {
        self.bot.0.len() + self.vert.0.len()
    }

    /// Ring of pixel `c`, clockwise in pixel space as rwarp builds it.
    pub fn ring(&self, c: usize, rx: &mut Vec<f64>, ry: &mut Vec<f64>) -> bool {
        rx.clear();
        ry.clear();
        let d = self.d;
        let mut ok = true;
        let mut push = |v: &(Vec<f64>, Vec<f64>, Vec<bool>), k: usize| {
            rx.push(v.0[k]);
            ry.push(v.1[k]);
            ok &= v.2[k];
        };
        for k in 0..d {
            push(&self.top, c * d + k);
        }
        push(&self.top, (c + 1) * d);
        for k in 1..d {
            push(&self.vert, (c + 1) * (d - 1) + k - 1);
        }
        for k in 0..d {
            push(&self.bot, (c + 1) * d - k);
        }
        push(&self.bot, c * d);
        for k in (1..d).rev() {
            push(&self.vert, c * (d - 1) + k - 1);
        }
        ok
    }
}

/// Lattice transform, coverage by accumulation.
pub fn accum_lattice(t: &impl Transformer, src: &Src, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let t0 = Instant::now();
    let mut lat = Lattice::new(t, dst_ncol, d);
    sp.transform += t0.elapsed();
    sp.points += (dst_ncol * d + 1) as u64;
    let mut acc = Accum::default();
    let (mut rx, mut ry) = (Vec::new(), Vec::new());
    for row in 0..dst_nrow {
        let t0 = Instant::now();
        lat.row(t, row);
        sp.transform += t0.elapsed();
        sp.points += lat.points() as u64;
        for c in 0..dst_ncol {
            if !lat.ring(c, &mut rx, &mut ry) {
                continue;
            }
            if let Some(v) = accum_ring(&mut acc, src, &rx, &ry, sp) {
                out[row * dst_ncol + c] = v;
            }
        }
    }
    out
}

/// Lattice transform, coverage by controlledburn (to separate the two
/// gains).
pub fn cb_lattice(t: &impl Transformer, src: &Src, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let (ncol, nrow) = (src.ncol as i64, src.nrow as i64);
    let t0 = Instant::now();
    let mut lat = Lattice::new(t, dst_ncol, d);
    sp.transform += t0.elapsed();
    let (mut rx, mut ry) = (Vec::new(), Vec::new());
    for row in 0..dst_nrow {
        let t0 = Instant::now();
        lat.row(t, row);
        sp.transform += t0.elapsed();
        sp.points += lat.points() as u64;
        for c in 0..dst_ncol {
            if !lat.ring(c, &mut rx, &mut ry) {
                continue;
            }
            let t1 = Instant::now();
            let mut ring: Vec<Coord> = rx.iter().zip(&ry).map(|(&x, &y)| Coord::new(x, -y)).collect();
            let (mut minx, mut maxx, mut miny, mut maxy) = (f64::INFINITY, f64::NEG_INFINITY, f64::INFINITY, f64::NEG_INFINITY);
            for p in &ring {
                minx = minx.min(p.x);
                maxx = maxx.max(p.x);
                miny = miny.min(-p.y);
                maxy = maxy.max(-p.y);
            }
            let c0 = (minx.floor() as i64).max(0);
            let c1 = (maxx.ceil() as i64).min(ncol);
            let r0 = (miny.floor() as i64).max(0);
            let r1 = (maxy.ceil() as i64).min(nrow);
            if c0 >= c1 || r0 >= r1 {
                continue;
            }
            ring.push(ring[0]);
            let grid = GridSpec::new(c0 as f64, -(r1 as f64), c1 as f64, -(r0 as f64), (c1 - c0) as u32, (r1 - r0) as u32);
            let Ok(res) = burn(&[Geometry::Polygon(Polygon::new(vec![ring]))], &grid, BurnOptions::coverage()) else { continue };
            let t2 = Instant::now();
            sp.cover += t2 - t1;
            let at = |row: i32, col: i64| ((r0 + row as i64) * ncol + c0 + col) as usize;
            let (mut s, mut w) = (0.0f64, 0.0f64);
            for run in &res.runs {
                for col in run.col_start..run.col_end {
                    s += src.data[at(run.row, col as i64)] as f64;
                    w += 1.0;
                }
            }
            for e in &res.edges {
                if e.fraction > 0.0 {
                    s += e.fraction as f64 * src.data[at(e.row, e.col as i64)] as f64;
                    w += e.fraction as f64;
                }
            }
            if w > 0.0 {
                out[row * dst_ncol + c] = (s / w) as f32;
            }
            sp.reduce += t2.elapsed();
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Boundary integral over row prefix sums (Green's theorem).
// ---------------------------------------------------------------------------

/// Row prefix sums of a source buffer: `s[j][i]` is the sum of valid values
/// left of column `i` in row `j`, `m[j][i]` the count of valid pixels.
/// With `F(x, y) = s[j][i] + (x - i) v[j][i]` (the x-antiderivative of the
/// piecewise-constant field), the area-weighted sum over any polygon is the
/// boundary integral of `F dy`, and its valid area that of the mask's `F`.
pub struct Prefix<'a> {
    pub ncol: usize,
    pub nrow: usize,
    data: &'a [f32],
    s: Vec<f64>,
    m: Vec<f64>,
}

impl<'a> Prefix<'a> {
    pub fn new(src: &Src<'a>) -> Self {
        let mut p = Prefix { ncol: src.ncol, nrow: src.nrow, data: src.data, s: Vec::new(), m: Vec::new() };
        p.build();
        p
    }

    /// (Re)compute the sums in place, reusing the buffers.
    pub fn build(&mut self) {
        let (w, h) = (self.ncol, self.nrow);
        let mut s = std::mem::take(&mut self.s);
        let mut m = std::mem::take(&mut self.m);
        s.resize(h * (w + 1), 0.0);
        m.resize(h * (w + 1), 0.0);
        for j in 0..h {
            let (mut a, mut b) = (0.0f64, 0.0f64);
            let o = j * (w + 1);
            s[o] = 0.0;
            m[o] = 0.0;
            for i in 0..w {
                let v = self.data[j * w + i];
                if v.is_finite() {
                    a += v as f64;
                    b += 1.0;
                }
                s[o + i + 1] = a;
                m[o + i + 1] = b;
            }
        }
        self.s = s;
        self.m = m;
    }

    /// `(F dy, G dy)` for a straight piece inside one cell, by its midpoint.
    #[inline]
    fn piece(&self, xm: f64, ym: f64, dy: f64) -> (f64, f64) {
        let j = ym.floor();
        if j < 0.0 || j >= self.nrow as f64 {
            return (0.0, 0.0);
        }
        let j = j as usize;
        let o = j * (self.ncol + 1);
        let i = xm.floor();
        if i < 0.0 {
            return (0.0, 0.0);
        }
        if i >= self.ncol as f64 {
            return (self.s[o + self.ncol] * dy, self.m[o + self.ncol] * dy);
        }
        let i = i as usize;
        let v = self.data[j * self.ncol + i];
        let f = xm - i as f64;
        if v.is_finite() {
            ((self.s[o + i] + f * v as f64) * dy, (self.m[o + i] + f) * dy)
        } else {
            (self.s[o + i] * dy, self.m[o + i] * dy)
        }
    }

    /// Integral of `(F dy, G dy)` along the segment p -> q.
    pub fn segment(&self, (x0, y0): (f64, f64), (x1, y1): (f64, f64)) -> (f64, f64) {
        let (dx, dy) = (x1 - x0, y1 - y0);
        if dy == 0.0 {
            return (0.0, 0.0);
        }
        let (mut kx, sx) = if dx > 0.0 { (x0.floor() + 1.0, 1.0) } else if dx < 0.0 { (x0.ceil() - 1.0, -1.0) } else { (f64::NAN, 0.0) };
        let (mut ky, sy) = if dy > 0.0 { (y0.floor() + 1.0, 1.0) } else { (y0.ceil() - 1.0, -1.0) };
        let (mut a, mut b) = (0.0, 0.0);
        let mut t = 0.0f64;
        loop {
            let tx = if sx != 0.0 { (kx - x0) / dx } else { f64::INFINITY };
            let ty = (ky - y0) / dy;
            let tn = tx.min(ty).min(1.0);
            if tn > t {
                let tm = 0.5 * (t + tn);
                let (p, q) = self.piece(x0 + tm * dx, y0 + tm * dy, (tn - t) * dy);
                a += p;
                b += q;
            }
            if tn >= 1.0 {
                break;
            }
            if tx <= tn {
                kx += sx;
            }
            if ty <= tn {
                ky += sy;
            }
            t = tn;
        }
        (a, b)
    }

    pub fn polyline(&self, xs: &[f64], ys: &[f64]) -> (f64, f64) {
        let (mut a, mut b) = (0.0, 0.0);
        for k in 1..xs.len() {
            let (p, q) = self.segment((xs[k - 1], ys[k - 1]), (xs[k], ys[k]));
            a += p;
            b += q;
        }
        (a, b)
    }
}

/// Per-pixel rings from the lattice, mean by boundary integral.
pub fn green_per_pixel(t: &impl Transformer, pre: &Prefix, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let t0 = Instant::now();
    let mut lat = Lattice::new(t, dst_ncol, d);
    sp.transform += t0.elapsed();
    let (mut rx, mut ry) = (Vec::new(), Vec::new());
    for row in 0..dst_nrow {
        let t0 = Instant::now();
        lat.row(t, row);
        sp.transform += t0.elapsed();
        sp.points += lat.points() as u64;
        let t1 = Instant::now();
        for c in 0..dst_ncol {
            if !lat.ring(c, &mut rx, &mut ry) {
                continue;
            }
            rx.push(rx[0]);
            ry.push(ry[0]);
            let (a, b) = pre.polyline(&rx, &ry);
            if b.abs() > 1e-9 {
                out[row * dst_ncol + c] = (a / b) as f32;
            }
        }
        sp.cover += t1.elapsed();
    }
    out
}

/// Shared edges: every lattice edge is integrated once and added to the
/// pixel on one side and subtracted from the pixel on the other.
pub fn green_lattice(t: &impl Transformer, pre: &Prefix, dst_ncol: usize, dst_nrow: usize, d: usize, sp: &mut Split) -> Vec<f32> {
    let mut out = vec![f32::NAN; dst_ncol * dst_nrow];
    let t0 = Instant::now();
    let mut lat = Lattice::new(t, dst_ncol, d);
    sp.transform += t0.elapsed();
    // Horizontal edge integrals of the current top line, left to right.
    let horiz = |lat: &Lattice, top: bool| -> Vec<(f64, f64, bool)> {
        (0..dst_ncol).map(|c| lat.hedge(top, c, pre)).collect()
    };
    let mut top = horiz(&lat, true);
    for row in 0..dst_nrow {
        let t0 = Instant::now();
        lat.row(t, row);
        sp.transform += t0.elapsed();
        sp.points += lat.points() as u64;
        let t1 = Instant::now();
        let bot = horiz(&lat, false);
        // Vertical edges, downwards.
        let vert: Vec<(f64, f64, bool)> = (0..=dst_ncol).map(|c| lat.vedge(c, pre)).collect();
        for c in 0..dst_ncol {
            let (h0, h1, v0, v1) = (top[c], bot[c], vert[c], vert[c + 1]);
            if !(h0.2 && h1.2 && v0.2 && v1.2) {
                continue;
            }
            // top L->R, right down, bottom R->L, left up
            let a = h0.0 + v1.0 - h1.0 - v0.0;
            let b = h0.1 + v1.1 - h1.1 - v0.1;
            if b.abs() > 1e-9 {
                out[row * dst_ncol + c] = (a / b) as f32;
            }
        }
        top = bot;
        sp.cover += t1.elapsed();
    }
    out
}

impl Lattice {
    /// Integral along horizontal edge `c` of the top or bottom line.
    pub fn hedge(&self, top: bool, c: usize, pre: &Prefix) -> (f64, f64, bool) {
        let v = if top { &self.top } else { &self.bot };
        let r = c * self.d..(c + 1) * self.d + 1;
        let ok = v.2[r.clone()].iter().all(|&o| o);
        if !ok {
            return (0.0, 0.0, false);
        }
        let (a, b) = pre.polyline(&v.0[r.clone()], &v.1[r]);
        (a, b, true)
    }

    /// Integral along column line `c` of the current row band, downwards.
    pub fn vedge(&self, c: usize, pre: &Prefix) -> (f64, f64, bool) {
        let d = self.d;
        let mut xs = Vec::with_capacity(d + 1);
        let mut ys = Vec::with_capacity(d + 1);
        let mut ok = self.top.2[c * d] && self.bot.2[c * d];
        xs.push(self.top.0[c * d]);
        ys.push(self.top.1[c * d]);
        for k in 1..d {
            let i = c * (d - 1) + k - 1;
            xs.push(self.vert.0[i]);
            ys.push(self.vert.1[i]);
            ok &= self.vert.2[i];
        }
        xs.push(self.bot.0[c * d]);
        ys.push(self.bot.1[c * d]);
        if !ok {
            return (0.0, 0.0, false);
        }
        let (a, b) = pre.polyline(&xs, &ys);
        (a, b, true)
    }
}
