//! m21: weights for two planned examples, at the size of the real grids'
//! windows, with rwarp's exact footprint (planar measure in source pixel
//! space). Prints entry counts and conservation, and writes the entries of
//! one target cell for the figure.
//!
//!   cargo run --release > ../../measurements/m21-conservative/log.txt

use rwarp::transform::GenImgProjTransformer;
use rwarp::weights::{exact_weights, GridWindow, WeightOptions, Weights};

fn report(name: &str, w: &Weights, src: (usize, usize), dst: (usize, usize), secs: f64) {
    let n_dst = dst.0 * dst.1;
    let n = w.frac.len();
    // column sums over source cells
    let mut col = vec![0.0f64; src.0 * src.1];
    for i in 0..n {
        col[w.src_row[i] as usize * src.0 + w.src_col[i] as usize] += w.frac[i];
    }
    // overlaps would push a sum past 1; gaps show as interior cells below 1
    let over = col.iter().map(|s| s - 1.0).fold(f64::MIN, f64::max);
    let full = col.iter().filter(|&&s| (s - 1.0).abs() < 1e-9).count();
    let touched = col.iter().filter(|&&s| s > 0.0).count();
    let noise = w.frac.iter().filter(|&&f| f < 1e-9).count();
    println!(
        "{name} ({secs:.2} s): dst {}x{} = {n_dst} cells, {n} entries ({:.1} per cell, {:.1} MB as 4 u32 + f64), \
         source cells touched {touched}, summing to 1 within 1e-9 {full}, max(sum frac) - 1 = {over:.2e}, entries below 1e-9 {noise}",
        dst.0, dst.1, n as f64 / n_dst as f64, n as f64 * 24.0 / 1e6
    );
}

fn main() {
    // A. GHRSST MUR-like 0.01 degree onto 0.25 degree, a 20 x 10 degree
    //    window (the Tasman Sea, 140E to 160E, 48S to 38S).
    let src_gt = [140.0, 0.01, 0.0, -38.0, 0.0, -0.01];
    let dst_gt = [140.0, 0.25, 0.0, -38.0, 0.0, -0.25];
    let t = GenImgProjTransformer::new("EPSG:4326", src_gt, "EPSG:4326", dst_gt).unwrap();
    let t0 = std::time::Instant::now();
    let w = exact_weights(&t, &GridWindow::new(2000, 1000), 80, 40, &WeightOptions::new(1));
    report("A ghrsst 0.01 -> 0.25 deg", &w, (2000, 1000), (80, 40), t0.elapsed().as_secs_f64());

    // B. BRAN2023-like 0.1 degree onto EPSG:3031 at 25 km over Prydz Bay
    //    (60E to 90E, 72S to 60S of source; target 1.5e6..3.3e6 x, -0.2e6..1.6e6 y).
    let src_gt = [60.0, 0.1, 0.0, -60.0, 0.0, -0.1];
    let dst_gt = [1.5e6, 25_000.0, 0.0, 1.6e6, 0.0, -25_000.0];
    let t = GenImgProjTransformer::new("EPSG:4326", src_gt, "EPSG:3031", dst_gt).unwrap();
    for densify in [1, 4] {
        let t0 = std::time::Instant::now();
        let w = exact_weights(&t, &GridWindow::new(300, 120), 72, 72, &WeightOptions::new(densify));
        report(&format!("B bran 0.1 deg -> 3031 25 km, densify {densify}"), &w, (300, 120), (72, 72), t0.elapsed().as_secs_f64());
        if densify == 4 {
            // one target cell for the figure: entries as src_col src_row frac
            let (r, c) = (40u32, 30u32);
            let mut s = String::from("src_col src_row frac\n");
            for i in 0..w.frac.len() {
                if w.dst_row[i] == r && w.dst_col[i] == c {
                    s += &format!("{} {} {:.6e}\n", w.src_col[i], w.src_row[i], w.frac[i]);
                }
            }
            std::fs::write("cell.txt", s).unwrap();
            // its outline in source pixel space, densify 16, through the transformer
            let mut xs = Vec::new();
            let mut ys = Vec::new();
            let k = 16;
            let corners = [(c as f64, r as f64), (c as f64 + 1.0, r as f64), (c as f64 + 1.0, r as f64 + 1.0), (c as f64, r as f64 + 1.0)];
            for e in 0..4 {
                let (a, b) = (corners[e], corners[(e + 1) % 4]);
                for j in 0..k {
                    let f = j as f64 / k as f64;
                    xs.push(a.0 + f * (b.0 - a.0));
                    ys.push(a.1 + f * (b.1 - a.1));
                }
            }
            use rwarp::Transformer;
            t.transform(true, &mut xs, &mut ys);
            let o: String = xs.iter().zip(&ys).map(|(x, y)| format!("{x} {y}\n")).collect();
            std::fs::write("outline.txt", o).unwrap();
        }
    }
}

