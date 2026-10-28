// One destination pixel in source pixel space: outlines, GDAL box, coverage.
use fpbench::*;
use rwarp::transform::GenImgProjTransformer;
use rwarp::Transformer;
fn main() {
    let res = 300000.0;
    let t = GenImgProjTransformer::new("EPSG:4326", [-180.0, 0.5, 0.0, 90.0, 0.0, -0.5], "EPSG:3031", [0.9e6, res, 0.0, 2.9e6, 0.0, -res]).unwrap();
    let ring = |d: usize| {
        let mut xs = vec![]; let mut ys = vec![];
        ring_points(1, 0, d, &mut xs, &mut ys);
        t.transform(true, &mut xs, &mut ys);
        (xs, ys)
    };
    let (x1, y1) = ring(1);
    let (x16, y16) = ring(16);
    let mut acc = Accum::default();
    let (minx, maxx) = (x16.iter().cloned().fold(f64::MAX, f64::min), x16.iter().cloned().fold(f64::MIN, f64::max));
    let (miny, maxy) = (y16.iter().cloned().fold(f64::MAX, f64::min), y16.iter().cloned().fold(f64::MIN, f64::max));
    let (c0, c1, r0, r1) = (minx.floor() as i64, maxx.ceil() as i64, miny.floor() as i64, maxy.ceil() as i64);
    acc.reset(c0, c1, r0, r1);
    for k in 0..x16.len() { let k1 = (k + 1) % x16.len(); acc.segment((x16[k], y16[k]), (x16[k1], y16[k1])); }
    acc.resolve();
    let tot: f64 = acc.coverage().iter().sum();
    let cov: Vec<f64> = acc.coverage().iter().map(|v| v * tot.signum()).collect();
    println!("{{\"x1\":{:?},\"y1\":{:?},\"x16\":{:?},\"y16\":{:?},\"c0\":{c0},\"r0\":{r0},\"w\":{},\"h\":{},\"cov\":{:?}}}", x1, y1, x16, y16, acc.w, acc.h, cov);
}
