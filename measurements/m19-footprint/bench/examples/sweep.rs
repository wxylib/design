use fpbench::*;
use rwarp::approx::ApproxTransformer;
use rwarp::transform::GenImgProjTransformer;
use rwarp::warp::{warp, Footprint, ResampleAlg, SourceBuffer, WarpOptions};
use rwarp::Transformer;
use std::time::Instant;

struct Rot { s: f64, a: f64, ox: f64, oy: f64 }
impl Transformer for Rot {
    fn transform(&self, _: bool, x: &mut [f64], y: &mut [f64]) -> Vec<bool> {
        let (c, s) = (self.a.cos(), self.a.sin());
        for (x, y) in x.iter_mut().zip(y.iter_mut()) {
            let (u, v) = (*x * self.s, *y * self.s);
            *x = self.ox + c * u - s * v;
            *y = self.oy + s * u + c * v;
        }
        vec![true; x.len()]
    }
}

fn field(w: usize, h: usize) -> Vec<f32> {
    (0..w * h).map(|i| {
        let (x, y) = ((i % w) as f32, (i / w) as f32);
        (x * 0.013).sin() * 10.0 + (y * 0.021).cos() * 7.0 + ((i * 2654435761) % 1000) as f32 * 0.001
    }).collect()
}

fn maxdiff(a: &[f32], b: &[f32]) -> f64 {
    a.iter().zip(b).filter(|(x, y)| x.is_finite() && y.is_finite())
        .map(|(x, y)| (x - y).abs() as f64).fold(0.0, f64::max)
}

fn rwarp_us(t: &impl Transformer, src: &Src, n: usize, fp: Footprint) -> (f64, Vec<f32>) {
    let buf = SourceBuffer { data: src.data, ncol: src.ncol, nrow: src.nrow, nbands: 1, col_off: 0, row_off: 0 };
    let opts = WarpOptions::<f32> { alg: ResampleAlg::Average, footprint: fp, nodata: Some(f32::NAN), ..Default::default() };
    let t0 = Instant::now();
    let out = warp(t, &buf, n, n, &opts);
    (t0.elapsed().as_secs_f64() * 1e6 / (n * n) as f64, out)
}

fn us(sp: &Split, n: usize) -> String {
    let p = (n * n) as f64;
    format!("{:7.3} {:7.3} {:7.3}", sp.transform.as_secs_f64() * 1e6 / p, sp.cover.as_secs_f64() * 1e6 / p, sp.reduce.as_secs_f64() * 1e6 / p)
}

fn run(label: &str, t: &impl Transformer, src: &Src, n: usize, d: usize) {
    let (bx, _) = rwarp_us(t, src, n, Footprint::GdalBox);
    let (ex, ref_out) = rwarp_us(t, src, n, Footprint::Exact { densify: d });
    let mut s1 = Split::default();
    let a = cb_per_pixel(t, src, n, n, d, &mut s1);
    let mut s2 = Split::default();
    let b = accum_per_pixel(t, src, n, n, d, &mut s2);
    let mut s3 = Split::default();
    let c = cb_lattice(t, src, n, n, d, &mut s3);
    let mut s4 = Split::default();
    let e = accum_lattice(t, src, n, n, d, &mut s4);
    let mut pre = Prefix::new(src);
    let t0 = Instant::now();
    pre.build();
    let pre_us = t0.elapsed().as_secs_f64() * 1e6 / (n * n) as f64;
    let mut s5 = Split::default();
    let g = green_per_pixel(t, &pre, n, n, d, &mut s5);
    let mut s6 = Split::default();
    let gl = green_lattice(t, &pre, n, n, d, &mut s6);
    s5.reduce += std::time::Duration::from_secs_f64(pre_us * 1e-6 * (n * n) as f64);
    s6.reduce += std::time::Duration::from_secs_f64(pre_us * 1e-6 * (n * n) as f64);
    let tot = |s: &Split| (s.transform + s.cover + s.reduce).as_secs_f64() * 1e6 / (n * n) as f64;
    println!("{label:>22} d={d:<2} box {bx:7.3} exact {ex:7.3} ({:5.1}x) | cb/pp [{}] {:6.3} | acc/pp [{}] {:6.3} | cb/lat {:6.3} | acc/lat [{}] {:6.3} ({:4.1}x box) | green/pp {:6.3} | green/lat [{}] {:6.3} ({:4.2}x box) | cells/px {:7.1} pts/px {:5.1}->{:5.1} | diff ref {:.1e} acc {:.1e} {:.1e} green {:.1e} {:.1e}",
        ex / bx, us(&s1, n), tot(&s1), us(&s2, n), tot(&s2), tot(&s3), us(&s4, n), tot(&s4), tot(&s4) / bx, tot(&s5), us(&s6, n), tot(&s6), tot(&s6) / bx,
        s1.cells as f64 / (n * n) as f64, s1.points as f64 / (n * n) as f64, s4.points as f64 / (n * n) as f64,
        maxdiff(&ref_out, &a), maxdiff(&a, &b), maxdiff(&a, &e), maxdiff(&a, &g), maxdiff(&a, &gl));
    let _ = c;
    eprintln!("{label},{d},{bx},{ex},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
        tot(&s1), tot(&s2), tot(&s4), tot(&s6),
        s1.transform.as_secs_f64() * 1e6 / (n * n) as f64, s1.cover.as_secs_f64() * 1e6 / (n * n) as f64, s1.reduce.as_secs_f64() * 1e6 / (n * n) as f64,
        s4.transform.as_secs_f64() * 1e6 / (n * n) as f64, s4.cover.as_secs_f64() * 1e6 / (n * n) as f64, s4.reduce.as_secs_f64() * 1e6 / (n * n) as f64,
        s6.transform.as_secs_f64() * 1e6 / (n * n) as f64, s6.cover.as_secs_f64() * 1e6 / (n * n) as f64, s6.reduce.as_secs_f64() * 1e6 / (n * n) as f64,
        s1.cells as f64 / (n * n) as f64);
}

fn main() {
    let which = std::env::args().nth(1).unwrap_or_else(|| "all".into());
    if which == "all" || which == "ratio" {
        println!("# affine rotation 0.1 rad, scale = source pixels per destination pixel; us per destination pixel; [transform cover reduce]");
        for &s in &[0.5f64, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0] {
            let n = (4096.0 / s).min(256.0) as usize;
            // Source window as a planner would give it: the tile's
            // footprint plus a pixel.
            let a = 0.1f64;
            let ext = s * n as f64 * (a.cos() + a.sin());
            let w = ext.ceil() as usize + 3;
            let data = field(w, w);
            let src = Src { data: &data, ncol: w, nrow: w };
            let rot = Rot { s, a, ox: 1.3 + s * n as f64 * a.sin(), oy: 1.7 };
            for &d in &[1usize, 4] {
                run(&format!("rot s={s}"), &rot, &src, n, d);
            }
        }
    }
    if which == "all" || which == "proj" {
        println!("# EPSG:4326 0.1 deg global source -> EPSG:3031 256x256 tile; us per destination pixel");
        let (w, h) = (3600usize, 1800usize);
        let data = field(w, h);
        let src = Src { data: &data, ncol: w, nrow: h };
        let src_gt = [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1];
        for &res in &[2500.0, 5000.0, 10000.0, 25000.0, 50000.0] {
            let n = 256usize;
            let dst_gt = [1.0e6, res, 0.0, 3.0e6 + 0.0 * res, 0.0, -res];
            let exact = GenImgProjTransformer::new("EPSG:4326", src_gt, "EPSG:3031", dst_gt).unwrap();
            for &d in &[1usize, 4, 16] {
                run(&format!("3031 {}km exact", res / 1000.0), &exact, &src, n, d);
            }
            let approx = ApproxTransformer::new(GenImgProjTransformer::new("EPSG:4326", src_gt, "EPSG:3031", dst_gt).unwrap(), 0.125);
            for &d in &[1usize, 4, 16] {
                run(&format!("3031 {}km approx", res / 1000.0), &approx, &src, n, d);
            }
        }
    }
}
