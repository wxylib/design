"""Band census and seam-chunk fractions for COP30 (OpenTopography).

Reads cop30_sources.parquet (written by cop30_summary.R) and prints, per
band width, the file counts per hemisphere and the share of pixels whose
chunks cannot be byte references under the origin cut with 512 x 512
blocks and no truncate codec (m10 section 5).

    python3 cop30_bands.py cop30_sources.parquet
"""
import math
import sys

import pyarrow.parquet as pq

BLOCK = 512
ROWS = 3600  # kept rows per file: 3601 less the shared line

t = pq.read_table(sys.argv[1]).to_pandas()
# lat is the paste's top edge; the file's southern edge is one degree below
t["south"] = (t["lat"] - 1).round().astype(int)
t["width"] = (t["src_w"] - 1).astype(int)

print("src_h values:", sorted(t["src_h"].unique()))
print("VRT ratios:", sorted(t["ratio_x"].round(3).unique()))
print("upsampled sources:", int((t["ratio_x"] > 1).sum()), "of", len(t))

total = whole = 0
print("width  north  south  chunks  computed  computed_pixels")
for w, sub in t.groupby("width"):
    n_north = int((sub["south"] >= 0).sum())
    n_south = len(sub) - n_north
    nx, ny = math.ceil(w / BLOCK), math.ceil(ROWS / BLOCK)
    n_whole = (w // BLOCK) * (ROWS // BLOCK)
    kept = (w // BLOCK) * BLOCK * (ROWS // BLOCK) * BLOCK
    frac = 1 - kept / (w * ROWS)
    total += len(sub) * w * ROWS
    whole += len(sub) * kept
    print(f"{w:5d}  {n_north:5d}  {n_south:5d}  {nx * ny:6d}  "
          f"{nx * ny - n_whole:8d}  {100 * frac:6.1f}%")
print(f"archive: {100 * (1 - whole / total):.1f}% of pixels in computed chunks")
print("cells present:", len(t), "of", 360 * 174)
