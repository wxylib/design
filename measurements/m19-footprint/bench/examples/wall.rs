// A destination pixel whose edge lies exactly on a source cell wall:
// controlledburn vs accumulation vs brute-force clipping.
use controlledburn::{burn, BurnOptions, Coord, Geometry, GridSpec, Polygon};
use fpbench::Accum;

fn clip_area(ring: &[(f64, f64)], x0: f64, y0: f64) -> f64 {
    // Sutherland-Hodgman against [x0,x0+1]x[y0,y0+1], then shoelace.
    let mut p: Vec<(f64, f64)> = ring.to_vec();
    let planes: [(usize, f64, bool); 4] = [(0, x0, true), (0, x0 + 1.0, false), (1, y0, true), (1, y0 + 1.0, false)];
    for &(ax, v, lower) in &planes {
        let inside = |q: &(f64, f64)| { let c = if ax == 0 { q.0 } else { q.1 }; if lower { c >= v } else { c <= v } };
        let mut out = vec![];
        for k in 0..p.len() {
            let (a, b) = (p[k], p[(k + 1) % p.len()]);
            let (ia, ib) = (inside(&a), inside(&b));
            if ia { out.push(a); }
            if ia != ib {
                let (ca, cb) = if ax == 0 { (a.0, b.0) } else { (a.1, b.1) };
                let t = (v - ca) / (cb - ca);
                out.push((a.0 + t * (b.0 - a.0), a.1 + t * (b.1 - a.1)));
            }
        }
        p = out;
        if p.is_empty() { return 0.0; }
    }
    let mut s = 0.0;
    for k in 0..p.len() { let (a, b) = (p[k], p[(k + 1) % p.len()]); s += a.0 * b.1 - b.0 * a.1; }
    (s / 2.0).abs()
}

#[allow(dead_code)]
fn main() {
    // A 2x2 box whose right edge is the wall x = 4, plus a sliver.
    for ring in [
        vec![(2.3, 1.3), (4.0, 1.3), (4.0, 3.6), (2.3, 3.6)],
        vec![(2.3, 3.6), (2.3, 1.3), (4.0, 1.3), (4.0, 3.6)],
        vec![(2.3, 1.3), (2.3, 3.6), (4.0, 3.6), (4.0, 1.3)],
        vec![(2.0, 1.3), (4.0, 1.3), (4.0, 3.6), (2.0, 3.6)],
    ] {
        let grid = GridSpec::new(0.0, -6.0, 6.0, 0.0, 6, 6);
        let mut cr: Vec<Coord> = ring.iter().map(|&(x, y)| Coord::new(x, -y)).collect();
        cr.push(cr[0]);
        let res = burn(&[Geometry::Polygon(Polygon::new(vec![cr]))], &grid, BurnOptions::coverage()).unwrap();
        let mut cb = vec![0.0f64; 36];
        for r in &res.runs { for c in r.col_start..r.col_end { cb[r.row as usize * 6 + c as usize] += 1.0; } }
        for e in &res.edges { cb[e.row as usize * 6 + e.col as usize] += e.fraction as f64; }
        let mut acc = Accum::default();
        acc.reset(0, 6, 0, 6);
        for k in 0..ring.len() { acc.segment(ring[k], ring[(k + 1) % ring.len()]); }
        acc.resolve();
        let tot: f64 = acc.coverage().iter().sum();
        let mut worst = (0.0, 0.0, 0.0, 0usize);
        for j in 0..6 { for i in 0..6 {
            let b = clip_area(&ring, i as f64, j as f64);
            let a = acc.coverage()[j * 6 + i] * tot.signum();
            let k = j * 6 + i;
            if (cb[k] - b).abs() > worst.0 { worst = ((cb[k] - b).abs(), cb[k], b, k); }
            assert!((a - b).abs() < 1e-12, "acc {a} vs clip {b} at {i},{j}");
        }}
        let cbsum: f64 = cb.iter().sum();
        println!("ring {:?}: area {:.4}, cb sum {:.4}, worst cb cell {} = {:.4} (clip {:.4}); acc == clip", ring, tot.abs(), cbsum, worst.3, worst.1, worst.2);
    }
}

#[allow(dead_code)]
pub fn check(ring: &[(f64, f64)]) {
    let (mut minx, mut maxx, mut miny, mut maxy) = (f64::INFINITY, f64::NEG_INFINITY, f64::INFINITY, f64::NEG_INFINITY);
    for &(x, y) in ring { minx = minx.min(x); maxx = maxx.max(x); miny = miny.min(y); maxy = maxy.max(y); }
    let (c0, c1, r0, r1) = (minx.floor() as i64, maxx.ceil() as i64, miny.floor() as i64, maxy.ceil() as i64);
    let (w, h) = ((c1 - c0) as usize, (r1 - r0) as usize);
    let grid = GridSpec::new(c0 as f64, -(r1 as f64), c1 as f64, -(r0 as f64), w as u32, h as u32);
    let mut cr: Vec<Coord> = ring.iter().map(|&(x, y)| Coord::new(x, -y)).collect();
    cr.push(cr[0]);
    let res = burn(&[Geometry::Polygon(Polygon::new(vec![cr]))], &grid, BurnOptions::coverage()).unwrap();
    let mut cb = vec![0.0f64; w * h];
    for r in &res.runs { for c in r.col_start..r.col_end { cb[r.row as usize * w + c as usize] += 1.0; } }
    for e in &res.edges { cb[e.row as usize * w + e.col as usize] += e.fraction as f64; }
    println!("window {w}x{h} at ({c0},{r0}); runs {:?}", res.runs);
    for j in 0..h { for i in 0..w {
        let b = clip_area(ring, (c0 + i as i64) as f64, (r0 + j as i64) as f64);
        if (cb[j * w + i] - b).abs() > 1e-5 { println!("  cell ({i},{j}) cb {:.6} clip {:.6}", cb[j * w + i], b); }
    }}
}
