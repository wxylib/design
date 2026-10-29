use fpbench::*;
use rwarp::transform::GenImgProjTransformer;
use rwarp::warp::{warp, Footprint, ResampleAlg, SourceBuffer, WarpOptions};
fn main() {
    let (w, h) = (3600usize, 1800usize);
    let data: Vec<f32> = (0..w * h).map(|i| {
        let (x, y) = (i % w, i / w);
        if (x * 7 + y * 13) % 11 == 0 || (x / 40 + y / 40) % 5 == 0 { f32::NAN } else { (x as f32 * 0.05).sin() * 5.0 + y as f32 * 0.01 }
    }).collect();
    let src = Src { data: &data, ncol: w, nrow: h };
    let pre = Prefix::new(&src);
    let t = GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.1, 0.0, 90.0, 0.0, -0.1], "EPSG:3031", [1.0e6, 10000.0, 0.0, 3.0e6, 0.0, -10000.0]).unwrap();
    let n = 128;
    let buf = SourceBuffer { data: &data, ncol: w, nrow: h, nbands: 1, col_off: 0, row_off: 0 };
    for d in [1usize, 4] {
        let opts = WarpOptions::<f32> { alg: ResampleAlg::Average, footprint: Footprint::Exact { densify: d }, nodata: Some(f32::NAN), ..Default::default() };
        let r = warp(&t, &buf, n, n, &opts);
        let mut sp = Split::default();
        let g = green_lattice(&t, &pre, n, n, d, &mut sp);
        let both = r.iter().zip(&g).filter(|(a, b)| a.is_finite() && b.is_finite()).count();
        let mism = r.iter().zip(&g).filter(|(a, b)| a.is_finite() != b.is_finite()).count();
        let md = r.iter().zip(&g).filter(|(a, b)| a.is_finite() && b.is_finite()).map(|(a, b)| (a - b).abs()).fold(0.0f32, f32::max);
        println!("d={d}: {both} valid in both, {mism} valid in one only, max diff {md:.2e}");
    }
}
