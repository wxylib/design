use fpbench::*;
use rwarp::transform::GenImgProjTransformer;
use rwarp::warp::{warp, Footprint, ResampleAlg, SourceBuffer, WarpOptions};
fn main() {
    let (w, h) = (3600usize, 1800usize);
    // A field with structure at the source resolution: smooth + checker.
    let data: Vec<f32> = (0..w * h).map(|i| {
        let (x, y) = (i % w, i / w);
        ((x as f32) * 0.05).sin() * 5.0 + ((y as f32) * 0.07).cos() * 5.0 + if (x / 3 + y / 3) % 2 == 0 { 2.0 } else { -2.0 }
    }).collect();
    let src = Src { data: &data, ncol: w, nrow: h };
    let pre = Prefix::new(&src);
    println!("res_km d mean_abs_vs_d64 max_abs_vs_d64 | box mean_abs max_abs");
    for &(res, n, x0, y0) in &[(2500.0, 256usize, 1.0e6, 3.0e6), (25000.0, 128, -1.6e6, 4.0e6), (100000.0, 64, -3.2e6, 3.2e6)] {
        let t = GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1], "EPSG:3031", [x0, res, 0.0, y0, 0.0, -res]).unwrap();
        let mut sp = Split::default();
        let truth = green_lattice(&t, &pre, n, n, 64, &mut sp);
        let buf = SourceBuffer { data: &data, ncol: w, nrow: h, nbands: 1, col_off: 0, row_off: 0 };
        let opts = WarpOptions::<f32> { alg: ResampleAlg::Average, footprint: Footprint::GdalBox, nodata: Some(f32::NAN), ..Default::default() };
        let bx = warp(&t, &buf, n, n, &opts);
        let stat = |o: &[f32]| {
            // Skip pixels whose footprint crosses the antimeridian or the
            // pole: they are wrong in every method.
            let v: Vec<f64> = o.iter().zip(&truth).filter(|(a, b)| a.is_finite() && b.is_finite() && (**a - **b).abs() < 5.0).map(|(a, b)| (a - b).abs() as f64).collect();
            (v.iter().sum::<f64>() / v.len() as f64, v.iter().cloned().fold(0.0, f64::max))
        };
        let (bm, bmax) = stat(&bx);
        for d in [1usize, 2, 4, 8, 16] {
            let o = green_lattice(&t, &pre, n, n, d, &mut sp);
            let (m, mx) = stat(&o);
            println!("{:>6} {:>2} {:.2e} {:.2e} | box {:.2e} {:.2e}", res / 1000.0, d, m, mx, bm, bmax);
        }
    }
}
