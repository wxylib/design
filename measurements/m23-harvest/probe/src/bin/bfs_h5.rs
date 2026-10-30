// Level-parallel walk of an HDF5 v1 chunk B-tree (type 1) over object_store.
// async-hdf5 reads the metadata (superblock, object headers, layout message);
// the index walk is ours: every node of one level is fetched concurrently.
// usage: bfs_h5 <url-or-path> <var> [concurrency]  -> CSV on stdout
use std::{collections::HashMap, sync::{atomic::{AtomicU64, Ordering}, Arc}};
use async_hdf5::{messages::data_layout::{ChunkIndexType, StorageLayout}, reader::ObjectReader, HDF5File};
use futures::{stream, StreamExt, TryStreamExt};
use object_store::{http::HttpBuilder, local::LocalFileSystem, path::Path, ObjectStore, ObjectStoreExt, ClientOptions};

const NODE_READ: u64 = 8192;
static GETS: AtomicU64 = AtomicU64::new(0);
static BYTES: AtomicU64 = AtomicU64::new(0);

fn le(b: &[u8], n: usize) -> u64 { b[..n].iter().rev().fold(0u64, |a, x| (a << 8) | *x as u64) }

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (src, var) = (&args[1], &args[2]);
    let conc: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(32);
    let (store, path): (Arc<dyn ObjectStore>, Path) = if src.starts_with("http") {
        let u = url::Url::parse(src).unwrap();
        let s = HttpBuilder::new().with_url(format!("{}://{}", u.scheme(), u.host_str().unwrap()))
            .with_client_options(ClientOptions::new().with_allow_http(true)).build().unwrap();
        (Arc::new(s), Path::from(u.path().trim_start_matches('/')))
    } else {
        (Arc::new(LocalFileSystem::new()), Path::from_filesystem_path(src).unwrap())
    };
    let t0 = std::time::Instant::now();
    let file = HDF5File::open(ObjectReader::new(store.clone(), path.clone())).await.unwrap();
    let sb = file.superblock().clone();
    let ds = file.root_group().await.unwrap().dataset(var).await.unwrap();
    let t_meta = t0.elapsed();
    let StorageLayout::Chunked { chunk_shape, index_address, indexing_type, .. } = ds.layout().clone() else { panic!("not chunked") };
    assert!(matches!(indexing_type, ChunkIndexType::BTreeV1), "only v1 B-tree here: {indexing_type:?}");
    let o = sb.size_of_offsets as usize;
    let nd = chunk_shape.len() + 1; // keys carry a trailing element-size offset
    let key = 8 + 8 * nd;
    let base = sb.base_address;

    let mut level: Vec<u64> = vec![index_address];
    let mut rows: Vec<(Vec<u64>, u64, u64, u32)> = Vec::new();
    let mut depth = 0;
    while !level.is_empty() {
        let fetched: Vec<(u64, bytes::Bytes)> = stream::iter(level.iter().copied())
            .map(|addr| { let (s, p) = (store.clone(), path.clone()); async move {
                let r = s.get_range(&p, (base + addr)..(base + addr + NODE_READ)).await?;
                GETS.fetch_add(1, Ordering::Relaxed); BYTES.fetch_add(r.len() as u64, Ordering::Relaxed);
                Ok::<_, object_store::Error>((addr, r)) } })
            .buffer_unordered(conc).try_collect().await.unwrap();
        let mut next = Vec::new();
        for (_addr, b) in fetched {
            assert_eq!(&b[0..4], b"TREE");
            assert_eq!(b[4], 1, "raw data chunk tree");
            let lvl = b[5];
            let n = le(&b[6..], 2) as usize;
            let need = 8 + 2 * o + (n + 1) * key + n * o;
            assert!(need <= b.len(), "node larger than {NODE_READ} bytes ({need}); widen the read");
            let mut p = 8 + 2 * o;
            for _ in 0..n {
                let k = &b[p..p + key];
                let child = le(&b[p + key..], o);
                if lvl == 0 {
                    let size = le(k, 4);
                    let mask = le(&k[4..], 4) as u32;
                    let idx: Vec<u64> = (0..nd - 1).map(|d| le(&k[8 + 8 * d..], 8) / chunk_shape[d]).collect();
                    rows.push((idx, base + child, size, mask));
                } else {
                    next.push(child);
                }
                p += key + o;
            }
        }
        eprintln!("level {depth}: {} nodes", level.len());
        level = next; depth += 1;
    }
    let mut seen = HashMap::new();
    for (idx, off, size, mask) in &rows {
        assert!(seen.insert(idx.clone(), *off).is_none(), "duplicate chunk {idx:?}");
        let ix: Vec<String> = idx.iter().map(|i| i.to_string()).collect();
        println!("{var},{},{off},{size},{mask}", ix.join(":"));
    }
    eprintln!("chunks {} metadata {:?} total {:?} index GETs {} index bytes {}", rows.len(), t_meta, t0.elapsed(), GETS.load(Ordering::Relaxed), BYTES.load(Ordering::Relaxed));
}
