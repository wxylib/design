// rwarp 0.2 (burn per pixel) against the lattice + CoverageWindow patch.
use rwarp::transform::GenImgProjTransformer;
use std::time::Instant;
macro_rules! run {
    ($m:ident, $t:expr, $data:expr, $w:expr, $h:expr, $n:expr, $alg:ident, $d:expr) => {{
        let buf = $m::warp::SourceBuffer { data: $data, ncol: $w, nrow: $h, nbands: 1, col_off: 0, row_off: 0 };
        let opts = $m::warp::WarpOptions::<f32> { alg: $m::warp::ResampleAlg::$alg, footprint: $m::warp::Footprint::Exact { densify: $d }, nodata: Some(f32::NAN), ..Default::default() };
        let t0 = Instant::now();
        let o = $m::warp::warp($t, &buf, $n, $n, &opts);
        (o, t0.elapsed().as_secs_f64() * 1e6 / ($n * $n) as f64)
    }};
}
fn main() {
    let (w, h) = (3600usize, 1800usize);
    let data: Vec<f32> = (0..w * h).map(|i| { let (x, y) = (i % w, i / w); if (x / 50 + y / 37) % 7 == 0 { f32::NAN } else { ((x / 3 + y / 5) % 9) as f32 } }).collect();
    for res in [2500.0, 10000.0, 50000.0] {
        let gt = [1.0e6, res, 0.0, 3.0e6, 0.0, -res];
        let tn = GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1], "EPSG:3031", gt).unwrap();
        let to = rwarp_orig::transform::GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1], "EPSG:3031", gt).unwrap();
        for d in [1usize, 4] {
            let n = 128;
            let (a, ta) = run!(rwarp_orig, &to, &data, w, h, n, Average, d);
            let (b, tb) = run!(rwarp, &tn, &data, w, h, n, Average, d);
            let (ma, _) = run!(rwarp_orig, &to, &data, w, h, n, Mode, d);
            let (mb, tm) = run!(rwarp, &tn, &data, w, h, n, Mode, d);
            let md = a.iter().zip(&b).filter(|(x, y)| x.is_finite() && y.is_finite()).map(|(x, y)| (x - y).abs()).fold(0f32, f32::max);
            let nanmis = a.iter().zip(&b).filter(|(x, y)| x.is_finite() != y.is_finite()).count();
            let modemis = ma.iter().zip(&mb).filter(|(x, y)| x.to_bits() != y.to_bits()).count();
            let ap = rwarp::approx::ApproxTransformer::new(GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1], "EPSG:3031", gt).unwrap(), 0.125);
            let (c, tc) = run!(rwarp, &ap, &data, w, h, n, Average, d);
            let cd = a.iter().zip(&c).filter(|(x, y)| x.is_finite() && y.is_finite()).map(|(x, y)| (x - y).abs()).fold(0f32, f32::max);
            println!("{}km d={d}: average old {ta:.2} us new {tb:.2} us ({:.1}x), max diff {md:.1e}, nan mismatch {nanmis}; mode new {tm:.2} us, {modemis} of {} differ", res / 1000.0, ta / tb, n * n);
            println!("    with ApproxTransformer(0.125): new {tc:.2} us ({:.1}x old exact), max diff vs exact {cd:.2}", ta / tc);
        }
    }
}
