//! m36: a Hovmoller from the same planner as a map slice.
//!
//! The GHRSST MUR store is (time, lat, lon), 17999 x 36000 cells at 0.01
//! degree, 512 x 512 chunks, one chunk deep in time, and its COGs carry
//! five overviews that halve lon and lat (never time). A map slice is a 2D
//! source over (lon, lat) at one time. A Hovmoller is a 2D source over
//! (lon, time) at one latitude. Both go through `rwarp::view::plan_view`
//! unchanged; only the axes and the placement differ.
//!
//! Prints one JSON object per case on stdout.

use rwarp::view::{plan_view, Level, Need, Source, View, ViewOptions};
use rwarp::CrsTransform;
use serde_json::json;

struct Same;
impl CrsTransform for Same {
    fn convert(&self, x: f64, y: f64) -> Option<(f64, f64)> {
        Some((x, y))
    }
}

const NLEV: usize = 6;
const WIDTHS: [usize; NLEV] = [36000, 18000, 9000, 4500, 2250, 1125];
const SCREEN: [usize; 2] = [1024, 512];

/// The map slice: lon by lat, both axes halving per level.
fn map_source() -> Source {
    let base = Level::new([-180.0, 0.01, 0.0, 90.0, 0.0, -0.01], [36000, 17999], [512, 512]);
    Source::geographic(base.pyramid(NLEV))
}

/// The Hovmoller: lon by time. Lon halves per level, time does not; one
/// chunk per time step. `unit` is the length of one time step in the
/// placement's units (1 for days, 24 for hours).
fn hov_source(days: usize, unit: f64) -> Source {
    let levels = (0..NLEV)
        .map(|k| {
            let dx = 0.01 * (1 << k) as f64;
            Level::new([-180.0, dx, 0.0, 0.0, 0.0, unit], [WIDTHS[k], days], [512, 1])
        })
        .collect();
    // Lon wraps; time has no poles.
    Source { period: Some(360.0), ..Source::new(levels) }
}

fn summary(name: &str, rule: &str, unit: &str, source: &Source, plan_keys: Vec<(usize, usize, usize)>) -> serde_json::Value {
    let mut levels: Vec<usize> = plan_keys.iter().map(|k| k.0).collect();
    levels.sort();
    levels.dedup();
    let cells: u64 = plan_keys.iter().map(|&(l, c, r)| source.levels[l].chunk_cells(c, r) as u64).sum();
    let mut cols: Vec<(usize, usize)> = plan_keys.iter().map(|k| (k.0, k.1)).collect();
    cols.sort();
    cols.dedup();
    let mut rows: Vec<usize> = plan_keys.iter().map(|k| k.2).collect();
    rows.sort();
    rows.dedup();
    json!({
        "case": name, "rule": rule, "time_unit": unit,
        "levels": levels, "chunks": plan_keys.len(), "cells": cells,
        "cols": cols, "rows": rows.len(),
    })
}

fn rwarp_plan(view: &View, source: &Source, need: Need) -> Vec<(usize, usize, usize)> {
    let opts = ViewOptions::default().with_need(need);
    let plan = plan_view(view, source, &Same, Some(&Same), &opts);
    plan.keys().map(|k| (k.level, k.col, k.row)).collect()
}

/// Per-axis rule: the level from the axes that have levels (lon), a
/// nearest-neighbour stride on the axis that has none (time).
fn per_axis(view: &View, source: &Source, unit: f64) -> Vec<(usize, usize, usize)> {
    let px_lon = (view.extent[2] - view.extent[0]) / view.size[0] as f64;
    let px_t = (view.extent[3] - view.extent[1]) / view.size[1] as f64 / unit; // in steps
    let level = (0..NLEV).rev().find(|&k| 0.01 * (1 << k) as f64 <= px_lon).unwrap_or(0);
    let lv = &source.levels[level];
    let stride = px_t.floor().max(1.0) as usize;
    let c0 = (((view.extent[0] + 180.0) / lv.gt[1]).floor().max(0.0) as usize) / 512;
    let c1 = ((((view.extent[2] + 180.0) / lv.gt[1]).ceil() as usize).min(lv.size[0]) - 1) / 512;
    let t0 = (view.extent[1] / unit).floor().max(0.0) as usize;
    let t1 = ((view.extent[3] / unit).ceil() as usize).min(lv.size[1]);
    let mut keys = Vec::new();
    for t in (t0..t1).step_by(stride) {
        for c in c0..=c1 {
            keys.push((level, c, t));
        }
    }
    keys
}

fn main() {
    // Map slice: the world in lon/lat on a 1024 x 512 screen, one day.
    let ms = map_source();
    let mv = View::new([-180.0, -90.0, 180.0, 90.0], SCREEN);
    println!("{}", summary("map-world", "rwarp-area", "-", &ms, rwarp_plan(&mv, &ms, Need::Area)));

    // Hovmollers: all longitudes, 30 days, a year, ten years.
    for days in [30usize, 366, 3653] {
        for (unit_name, unit) in [("day", 1.0), ("hour", 24.0)] {
            let hs = hov_source(days, unit);
            let hv = View::new([-180.0, 0.0, 180.0, days as f64 * unit], SCREEN);
            let name = format!("hov-world-{days}d");
            println!("{}", summary(&name, "rwarp-area", unit_name, &hs, rwarp_plan(&hv, &hs, Need::Area)));
            println!("{}", summary(&name, "rwarp-shortest", unit_name, &hs, rwarp_plan(&hv, &hs, Need::Shortest)));
            println!("{}", summary(&name, "per-axis", unit_name, &hs, per_axis(&hv, &hs, unit)));
        }
    }
}
