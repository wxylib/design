use fpbench::*;
use rwarp::warp::{warp, Footprint, ResampleAlg, SourceBuffer, WarpOptions};
use rwarp::Transformer;
use std::time::Instant;
struct Rot { s: f64, ox: f64 }
impl Transformer for Rot {
    fn transform(&self, _: bool, x: &mut [f64], y: &mut [f64]) -> Vec<bool> {
        let (c, s) = (0.1f64.cos(), 0.1f64.sin());
        for (x, y) in x.iter_mut().zip(y.iter_mut()) { let (u, v) = (*x * self.s, *y * self.s); *x = self.ox + c * u - s * v; *y = 1.7 + s * u + c * v; }
        vec![true; x.len()]
    }
}
fn main() {
    let s = 2.0;
    println!("n box_us rwarp_exact_us green_lat_us(incl prefix)");
    for n in [16usize, 64, 256, 1024] {
        let w = (s * n as f64 * 1.1) as usize + 4;
        let data: Vec<f32> = (0..w * w).map(|i| (i % 97) as f32).collect();
        let src = Src { data: &data, ncol: w, nrow: w };
        let t = Rot { s, ox: 1.3 + s * n as f64 * 0.1f64.sin() };
        let buf = SourceBuffer { data: &data, ncol: w, nrow: w, nbands: 1, col_off: 0, row_off: 0 };
        let mut best = [f64::MAX; 3];
        for _ in 0..3 {
            for (k, fp) in [Footprint::GdalBox, Footprint::Exact { densify: 1 }].into_iter().enumerate() {
                let opts = WarpOptions::<f32> { alg: ResampleAlg::Average, footprint: fp, ..Default::default() };
                let t0 = Instant::now(); let _ = warp(&t, &buf, n, n, &opts);
                best[k] = best[k].min(t0.elapsed().as_secs_f64() * 1e6 / (n * n) as f64);
            }
            let t0 = Instant::now();
            let pre = Prefix::new(&src);
            let mut sp = Split::default();
            let _ = green_lattice(&t, &pre, n, n, 1, &mut sp);
            best[2] = best[2].min(t0.elapsed().as_secs_f64() * 1e6 / (n * n) as f64);
        }
        println!("{n} {:.3} {:.3} {:.3}", best[0], best[1], best[2]);
    }
}
