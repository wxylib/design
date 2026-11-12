# Watch: decoding GeoTIFF to GPU memory

Status: tracking note, 2026-11-12. Checked at the monthly landscape
refresh with [rewrites.md](rewrites.md).
Context: the Pangeo Discourse thread
[Decode GeoTIFF to GPU memory](https://discourse.pangeo.io/t/decode-geotiff-to-gpu-memory/5214)
(2025 to 2026), Wei Ji Leong's
[cog3pio](https://github.com/weiji14/cog3pio) and its blog series
"GeoTIFFs to GPUs" (parts 1 to 3), the
[rumi](https://github.com/asterisk-labs/rumi) format posted later in the
same thread, and the decode benchmark in
[mdsumner/rumi](https://github.com/mdsumner/rumi), which splits rumi's
speed-up on the same Sentinel-2 scene into codec, layout, tile size and
GDAL settings. [04 landscape](../04-landscape.md) section 6.2;
[03 architecture](../03-architecture.md) S2 (the plan, fetch, decode
seam).

## 1. Summary

1. **The headline claim is a 3x win for GPU decode over GDAL.** cog3pio
   decodes a Sentinel-2 true-colour COG with nvTIFF and nvCOMP in about
   0.35 s against about 1.05 s for GDAL and 1.75 s for image-tiff
   (blog part 1, cog3pio `benches/read_cog.rs`).
2. **Most of that gap is the CPU baseline, not the GPU.** The same scene,
   measured with every band read in one call, LIBERTIFF and four threads,
   decodes in 326 ms (mdsumner/rumi). That is already faster than the
   nvTIFF figure. A later post in the thread reports the same reversal on
   GDAL 3.11: about 0.2 s for LIBERTIFF against 0.35 s for nvTIFF.
3. **The next factor is the codec.** The scene is DEFLATE with
   Predictor=2. Re-encoded as band-interleaved ZSTD in a plain GTiff, GDAL
   decodes it in 166 ms on four threads and 55 ms on sixteen, and the file
   is smaller. Uncompressed, the floor is 85 ms on one thread. DEFLATE is
   also the codec GPUs handle worst (section 3).
4. **What is genuinely GPU-specific is where the pixels land.** A GPU
   decode leaves the array in device memory, frees the CPU, and suits
   batches of many scenes feeding a model. Those are real gains, and none
   of them is "GDAL is slow".
5. **For wxylib: no GPU work now.** Keep decode a separate, swappable
   stage that can take a batch of tiles and write into a caller's buffer;
   record a benchmark protocol so claims against GDAL are matched; and
   keep recommending ZSTD with a predictor for new stores (section 5).

## 2. The claims, and what each compares

All rows are the same scene,
`sentinel-s2-l2a-cogs/37/M/BV/2024/10/S2A_37MBV_20241029_0_L2A/TCI.tif`:
3 x 10980 x 10980 uint8, pixel-interleaved, DEFLATE + Predictor=2, 121
tiles of 1024 x 1024 at full resolution and four overview levels. The file
is 318.0 MB; the full-resolution tiles are 236.7 MB of it (read from the
file's IFDs, 2026-11-12), and the decoded array is 361.7 MB.

| Source | Reader | Setup | Time |
|---|---|---|---:|
| blog part 1, cog3pio bench | nvTIFF + nvCOMP (GPU) | file read from disk into memory, decode to device | ~0.35 s |
| blog part 1, cog3pio bench | GDAL (LIBERTIFF, `NUM_THREADS=4`) | band at a time, to host | ~1.05 s |
| blog part 1, cog3pio bench | image-tiff (CPU) | to host | ~1.75 s |
| Pangeo thread, later post | GDAL 3.11 LIBERTIFF | | ~0.2 s |
| mdsumner/rumi, GDAL 3.13.3 | LIBERTIFF, original COG | encoded bytes in RAM, all bands in one read | 1199 ms (1 thr), 326 (4), 93 (16), 73 (32) |
| mdsumner/rumi | LIBERTIFF, ZSTD band-interleaved re-encode | same | 622 (1), 166 (4), 55 (16), 35 (32) |
| mdsumner/rumi | uncompressed band-interleaved | same | 85 (1), 38 (4), 27 (16), 20 (32) |
| mdsumner/rumi | rumi pfor, one chunk per band | same | 444 (1), 119 (4), 43 (16), 33 (32) |

The machines differ between rows, so only ratios within a source are
safe. Within mdsumner/rumi the ratios are the point: DEFLATE to ZSTD
halves the time, and layout (pixel- or band-interleaved) changes almost
nothing for a full read (1199 against 1159 ms).

### 2.1 Why the cog3pio GDAL arm is slow

Read from `benches/read_cog.rs` at cog3pio main (2026-11-12):

- **It reads band at a time from a pixel-interleaved file.** Each band
  read decodes the tiles that hold all three bands, so unless the block
  cache keeps the other two, every tile is inflated more than once. The
  all-bands read that mdsumner/rumi times is the fair comparison, and
  nvTIFF decodes all bands in one pass.
- **The loop is `for b in 1..3`,** which in Rust is bands 1 and 2. So the
  GDAL figure covers two of the three bands, yet still loses. With the
  `cuda` feature, the arm also creates a CUDA context and allocates a
  full 3-band device buffer inside that loop, once per band.
- **Throughput is computed on the file size (318 MB),** which includes
  about 81 MB of overviews that neither reader decodes. The 900 and
  300 MB/s figures are therefore file bytes per second, not tile bytes or
  pixels.
- **Four threads, against a whole GPU.** The CPU has more cores than
  that, and mdsumner/rumi shows LIBERTIFF still scaling at 16.

None of this is a criticism of nvTIFF's speed. It means the 3x is a
comparison against one particular way of calling GDAL.

## 3. GPU-specific gains versus compression and IO choices

| Factor | Kind | Size of effect on this scene |
|---|---|---|
| Codec (DEFLATE vs ZSTD vs none) | compression choice | about 2x CPU time from DEFLATE to ZSTD; about 14x from DEFLATE to none on one thread |
| Predictor=2 | compression choice | sequential along a row, parallel across rows; cheap on CPU, a row-per-thread kernel on GPU |
| Read pattern (all bands at once vs band at a time) | API use | likely most of the 1.05 s against 326 ms gap; not measured separately |
| Threads | configuration | 1199 to 93 ms from 1 to 16 threads (LIBERTIFF) |
| GDAL settings | configuration | most make little difference; `GDAL_CACHEMAX` and thread option style none; `GTIFF_DIRECT_IO` and `GTIFF_VIRTUAL_MEM_IO` make in-memory reads 3 to 4x slower (mdsumner/rumi) |
| Output in device memory | **GPU-specific** | saves one host-to-device copy, about 362 MB here (tens of ms over PCIe 4) |
| Freeing the CPU for other work | **GPU-specific** | matters in a training data loader, not in a timed read |
| Batch decode of many tiles in one launch | **GPU-specific** | nvTIFF's model; pays off with many scenes, less with one |

On codecs: DEFLATE's bit-serial Huffman stage is hard to parallelise
within a stream, so a GPU gains mostly by decoding many tiles at once.
nvCOMP's faster GPU codecs (LZ4, Snappy, Bitcomp, its ANS, and its own
batched ZSTD) are not what existing COGs use. The CPU and GPU arguments
point the same way: the stored codec sets the ceiling, and ZSTD, or a
codec built for wide decode such as rumi's planar pfor, beats DEFLATE on
both.

rumi itself has not shown a GPU path yet; its author notes that the
planar predictor decodes row by row in parallel, which suits a GPU, but
needs a newer OpenZL frame format. mdsumner/rumi finds pfor's real
advantage at about 1.4x on one thread over the best GeoTIFF GDAL can
already read, with the gap mostly closing at 16 or more threads.

## 4. What the thread does not test

- **Remote reads.** Every figure holds the bytes locally or in RAM. For
  COGs on object storage, fetch latency and request count usually
  dominate decode, on either device.
- **Many scenes.** The GPU case is strongest for batches; no batch
  benchmark is posted.
- **A matched GPU baseline.** No row times GDAL plus the
  host-to-device copy with all bands in one read and many threads, which
  is the honest CPU-then-GPU path. That copy is the only cost the GPU
  path removes outright.
- **Other codecs on the GPU.** nvTIFF on a ZSTD or uncompressed copy of
  the scene is not reported.

## 5. What wxylib should do

1. **No GPU decode in wxylib now.** It needs CUDA, Linux and NVIDIA
   hardware, and cog3pio already exists for it. If wanted later, it slots
   in as a decode backend, not a reader.
2. **Keep decode a separate stage that a batch decoder can replace.**
   wxy-tiff already splits fetch from decode (`ChunkSource::fetch` and
   `::decode`, over async-tiff's decoder registry), one tile at a time,
   to host memory. A GPU decoder wants the whole batch of encoded tiles
   and a destination buffer. When the decode stage is next touched, add
   a batch form that takes encoded tiles and writes into a caller-owned
   buffer; that also helps CPU decode (the preallocated-buffer gain of 10
   to 20% in mdsumner/rumi) and is the shape a device buffer needs.
3. **DLPack beside Arrow as an interchange aspiration.** cog3pio and
   rumi both hand arrays out through DLPack, which carries device
   location. It belongs in the bindings layer (doc 03), next to the Arrow
   C data interface, not in core. No work now.
4. **A benchmark protocol for claims against GDAL.** Record in the oracle
   harness notes ([m27](../m27-oracle-harness.md)) the rules
   mdsumner/rumi follows: same file and codec on both sides, all bands in
   one read, thread count stated and run in its own process, dataset
   reopened each repeat, output hashed against GDAL, throughput on tile
   bytes or pixels rather than file size, and where the result lands
   (host or device) stated with the copy timed. This is cheap and keeps
   wxylib's own speed claims honest.
5. **Store advice stays as it is.** New byte-referenced stores should
   prefer ZSTD with a predictor over DEFLATE, as the GHRSST COGs already
   do. A faster decode device does not change that.
6. **Track cog3pio and rumi.** cog3pio (Rust, image-tiff and nvTIFF,
   DLPack, an xarray engine through cupy-xarray) and rumi (OpenZL frames
   in a TIFF-shaped container) are added to the landscape (section 6.2)
   and to the monthly check.

## 6. Not verified

- The Pangeo posts and the blog series could not be fetched from this
  environment; their figures are taken from search excerpts and agree
  with the cog3pio bench source, which was read directly.
- The block-cache behaviour of LIBERTIFF on band-at-a-time reads of a
  pixel-interleaved file is inferred, not measured here.
- No benchmark was run for this note; the CPU figures are those of
  mdsumner/rumi on GDAL 3.13.3.
