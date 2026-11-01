use rwarp::transform::Transformer;
use rwarp::warp::SourceBuffer;
use rwarp::weights::*;
use std::io::Write;

// Global regular lon/lat to regular lon/lat, spherical measure, FracArea.
// Usage: pyinterp_vs_rwarp SRC_RES DST_RES (degrees); writes rwarp_out.bin
// (little-endian f64, dst rows north to south).
struct LonLat { s: [f64; 6], d: [f64; 6] }
impl Transformer for LonLat {
    fn transform(&self, _: bool, x: &mut [f64], y: &mut [f64]) -> Vec<bool> {
        for (x, y) in x.iter_mut().zip(y.iter_mut()) {
            let (lon, lat) = (self.d[0] + *x * self.d[1], self.d[3] + *y * self.d[5]);
            *x = (lon - self.s[0]) / self.s[1]; *y = (lat - self.s[3]) / self.s[5];
        }
        vec![true; x.len()]
    }
}
fn main() {
    let a: Vec<f64> = std::env::args().skip(1).map(|v| v.parse().unwrap()).collect();
    let (sres, dres) = (a[0], a[1]);
    let (sw, sh) = ((360.0 / sres) as usize, (180.0 / sres) as usize);
    let (dw, dh) = ((360.0 / dres) as usize, (180.0 / dres) as usize);
    let s = [-180.0, sres, 0.0, 90.0, 0.0, -sres];
    let d = [-180.0, dres, 0.0, 90.0, 0.0, -dres];
    let data: Vec<f64> = (0..sh).flat_map(|r| (0..sw).map(move |c| {
        let lon = (-180.0 + (c as f64 + 0.5) * sres).to_radians();
        let lat = (90.0 - (r as f64 + 0.5) * sres).to_radians();
        2.0 + lat.cos().powi(2) * (2.0 * lon).cos()
    })).collect();
    let t = LonLat { s, d };
    let m = lonlat_measure(s).unwrap();
    let t0 = std::time::Instant::now();
    let w = exact_weights(&t, &GridWindow::new(sw, sh), dw, dh, &WeightOptions::new(1).with_measure(m));
    let tw = t0.elapsed().as_secs_f64();
    let buf = SourceBuffer { data: &data, ncol: sw, nrow: sh, nbands: 1, col_off: 0, row_off: 0 };
    let t1 = std::time::Instant::now();
    let out: Vec<f64> = w.apply(&buf, Normalization::FracArea, &ApplyOptions::new());
    let ta = t1.elapsed().as_secs_f64();
    eprintln!("entries {} weights {:.3}s apply {:.4}s", w.len(), tw, ta);
    let mut f = std::fs::File::create("rwarp_out.bin").unwrap();
    for v in &out { f.write_all(&v.to_le_bytes()).unwrap(); }
}
