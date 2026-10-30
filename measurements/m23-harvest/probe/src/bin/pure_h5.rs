// Harvest chunk refs with hdf5-pure through a sync range Source.
// usage: pure_h5 <url-or-path> <var> [<var>...]   -> CSV on stdout
use std::{collections::HashMap, sync::Mutex};
use hdf5_pure::{File, FormatError, Source};

const BLOCK: u64 = 1 << 20;

struct HttpSource { agent: ureq::Agent, url: String, len: u64, cache: Mutex<HashMap<u64, Vec<u8>>>, gets: Mutex<u64> }

impl HttpSource {
    fn new(url: &str) -> Self {
        let agent = ureq::AgentBuilder::new().try_proxy_from_env(true).build();
        let r = agent.head(url).call().unwrap();
        let len = r.header("content-length").unwrap().parse().unwrap();
        HttpSource { agent, url: url.into(), len, cache: Mutex::new(HashMap::new()), gets: Mutex::new(0) }
    }
    fn block(&self, b: u64) -> Vec<u8> {
        if let Some(v) = self.cache.lock().unwrap().get(&b) { return v.clone(); }
        let start = b * BLOCK;
        let end = (start + BLOCK).min(self.len) - 1;
        let r = self.agent.get(&self.url).set("Range", &format!("bytes={start}-{end}")).call().unwrap();
        let mut v = Vec::new();
        std::io::Read::read_to_end(&mut r.into_reader(), &mut v).unwrap();
        *self.gets.lock().unwrap() += 1;
        eprintln!("GET block {b}");
        self.cache.lock().unwrap().insert(b, v.clone());
        v
    }
}

impl Source for HttpSource {
    fn len(&self) -> u64 { self.len }
    fn read_at(&self, offset: u64, buf: &mut [u8]) -> Result<(), FormatError> {
        let mut done = 0usize;
        while done < buf.len() {
            let pos = offset + done as u64;
            let b = self.block(pos / BLOCK);
            let o = (pos % BLOCK) as usize;
            let n = (b.len() - o).min(buf.len() - done);
            buf[done..done + n].copy_from_slice(&b[o..o + n]);
            done += n;
        }
        Ok(())
    }
}


fn main() {
    let args: Vec<String> = std::env::args().collect();
    let src = &args[1];
    let t0 = std::time::Instant::now();
    let file = if src.starts_with("http") { File::from_source(HttpSource::new(src)).unwrap() } else { File::open(src).unwrap() };
    for var in &args[2..] {
        let ds = file.dataset(var).unwrap();
        let cs = ds.chunk_shape().unwrap().unwrap();
        let chunks = ds.chunks().unwrap();
        eprintln!("{var}: chunk {:?} index {:?} n={}", cs, ds.chunk_index().unwrap(), chunks.len());
        for c in chunks {
            let ix: Vec<String> = c.offset.iter().zip(cs.iter()).map(|(o, s)| (o / *s as u64).to_string()).collect();
            println!("{var},{},{},{},{}", ix.join(":"), c.address, c.storage_size, c.filter_mask);
        }
    }
    eprintln!("elapsed {:?}", t0.elapsed());
    let _ = &file;
}
