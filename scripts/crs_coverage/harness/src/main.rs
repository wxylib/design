//! Runs each case through whichever CRS engines this build has, printing one
//! JSON line per (case, engine). Judging happens in judge.py.
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
struct Case { id: String, src: String, dst: String, lon: f64, lat: f64, oracle: [f64; 2] }
#[derive(Deserialize)]
struct Cases { cases: Vec<Case> }

type R = Result<[f64; 2], String>;

macro_rules! p4 {
    ($m:ident, $krate:ident) => {
        mod $m {
            use super::R;
            use $krate::proj::Proj;
            fn mk(s: &str) -> Result<Proj, String> { Proj::from_user_string(s).map_err(|e| e.to_string()) }
            fn go(a: &Proj, b: &Proj, x: f64, y: f64) -> R {
                let (x, y) = if a.is_latlong() { (x.to_radians(), y.to_radians()) } else { (x, y) };
                let mut p = (x, y, 0.0);
                $krate::transform::transform(a, b, &mut p).map_err(|e| e.to_string())?;
                let (x, y) = if b.is_latlong() { (p.0.to_degrees(), p.1.to_degrees()) } else { (p.0, p.1) };
                if x.is_finite() && y.is_finite() { Ok([x, y]) } else { Err("non-finite".into()) }
            }
            pub fn run(src: &str, dst: &str, lon: f64, lat: f64, o: [f64; 2]) -> (R, R) {
                let (a, b) = match (mk(src), mk(dst)) {
                    (Ok(a), Ok(b)) => (a, b),
                    (Err(e), _) => return (Err(format!("src: {e}")), Err(String::new())),
                    (_, Err(e)) => return (Err(format!("dst: {e}")), Err(String::new())),
                };
                (go(&a, &b, lon, lat), go(&b, &a, o[0], o[1]))
            }
        }
    };
}
#[cfg(feature = "p01")]
p4!(e01, proj4rs01);
#[cfg(feature = "p03")]
p4!(e03, proj4rs03);

#[cfg(feature = "tc")]
mod etc {
    use super::R;
    use terrio_crs::{SpatialRef, Transformer};
    fn go(a: &SpatialRef, b: &SpatialRef, x: f64, y: f64) -> R {
        let t = Transformer::new(a, b).map_err(|e| e.to_string())?;
        let (x, y) = t.transform(x, y).map_err(|e| e.to_string())?;
        if x.is_finite() && y.is_finite() { Ok([x, y]) } else { Err("non-finite".into()) }
    }
    pub fn run(src: &str, dst: &str, lon: f64, lat: f64, o: [f64; 2]) -> (R, R) {
        let (a, b) = match (SpatialRef::parse(src), SpatialRef::parse(dst)) {
            (Ok(a), Ok(b)) => (a, b),
            (Err(e), _) => return (Err(format!("src: {e}")), Err(String::new())),
            (_, Err(e)) => return (Err(format!("dst: {e}")), Err(String::new())),
        };
        (go(&a, &b, lon, lat), go(&b, &a, o[0], o[1]))
    }
}

fn main() {
    let path = std::env::args().nth(1).expect("cases.json");
    let label = std::env::args().nth(2).unwrap_or_default();
    let cs: Cases = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let mut engines: Vec<(String, fn(&str, &str, f64, f64, [f64; 2]) -> (R, R))> = vec![];
    #[cfg(feature = "p01")]
    engines.push(("proj4rs 0.1.10".into(), e01::run));
    #[cfg(feature = "p03")]
    engines.push(("proj4rs 0.3.0".into(), e03::run));
    #[cfg(feature = "tc")]
    engines.push((label.clone(), etc::run));
    for c in &cs.cases {
        for (name, f) in &engines {
            let r = std::panic::catch_unwind(|| f(&c.src, &c.dst, c.lon, c.lat, c.oracle));
            let (fwd, inv) = r.unwrap_or_else(|_| (Err("panic".into()), Err(String::new())));
            println!("{}", json!({"id": c.id, "engine": name,
                "fwd": fwd.as_ref().ok(), "fwd_err": fwd.as_ref().err(),
                "inv": inv.as_ref().ok(), "inv_err": inv.as_ref().err()}));
        }
    }
}
