// Harvest chunk refs with async-hdf5 over object_store (HTTP or local).
// usage: async_h5 <url-or-path> <var> [<var>...]   -> CSV on stdout
use std::sync::Arc;
use async_hdf5::{reader::ObjectReader, HDF5File};
use object_store::{http::HttpBuilder, local::LocalFileSystem, path::Path, ObjectStore, ClientOptions};

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let src = &args[1];
    let (store, path): (Arc<dyn ObjectStore>, Path) = if src.starts_with("http") {
        let u = url::Url::parse(src).unwrap();
        let base = format!("{}://{}", u.scheme(), u.host_str().unwrap());
        let s = HttpBuilder::new().with_url(base)
            .with_client_options(ClientOptions::new().with_allow_http(true))
            .build().unwrap();
        (Arc::new(s), Path::from(u.path().trim_start_matches('/')))
    } else {
        (Arc::new(LocalFileSystem::new()), Path::from_filesystem_path(src).unwrap())
    };
    let t0 = std::time::Instant::now();
    let file = HDF5File::open(ObjectReader::new(store, path)).await.unwrap();
    let root = file.root_group().await.unwrap();
    for var in &args[2..] {
        let ds = root.dataset(var).await.unwrap();
        let idx = ds.chunk_index().await.unwrap();
        eprintln!("{var}: shape {:?} chunk {:?} filters {:?} n={}", ds.shape(), ds.chunk_shape(), ds.filters(), idx.len());
        for c in idx.iter() {
            let ix: Vec<String> = c.indices.iter().map(|i| i.to_string()).collect();
            println!("{var},{},{},{},{}", ix.join(":"), c.byte_offset, c.byte_length, c.filter_mask);
        }
    }
    eprintln!("elapsed {:?}", t0.elapsed());
}
