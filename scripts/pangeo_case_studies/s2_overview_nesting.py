# Compare 10 m -> 60 m reductions using the COG's own levels (no GDAL): exact 6x6 block mean of
# level 0, 3x3 block mean of the 20 m overview (nests into 60 m), area-weighted mean of the 40 m
# overview (does not nest), and nearest. Window from the notebook: (432540, 4661520, 438540, 4667520).
# Usage: python3 -I s2_overview_nesting.py https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/sentinel-2-c1-l2a/15/T/VG/2024/8/S2A_T15TVG_20240818T171118_L2A
# Needs numpy and tifffile (header parsing only); tiles are fetched with HTTP range requests.
import sys, zlib, urllib.request, numpy as np, tifffile
B = sys.argv[1]
L, Bm, R, T = 432540, 4661520, 438540, 4667520
X0, Y0 = 399960.0, 4700040.0
def get(url, a, b):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{b}"})
    return urllib.request.urlopen(req, timeout=60).read()
def levels(url):
    head = get(url, 0, 262143)
    import io
    t = tifffile.TiffFile(io.BytesIO(head + b"\0" * 0))
    out = []
    for p in t.pages:
        tg = p.tags
        out.append(dict(shape=p.shape, tile=(tg['TileLength'].value, tg['TileWidth'].value),
                        off=tg['TileOffsets'].value, cnt=tg['TileByteCounts'].value))
    return out
def window(url, lev, res, nbytes):
    tl, tw = lev['tile']; H, W = lev['shape']; ntx = -(-W // tw)
    c0, c1 = int(round((L - X0) / res * 2)) / 2, (R - X0) / res
    r0, r1 = (Y0 - T) / res, (Y0 - Bm) / res
    ci0, ci1, ri0, ri1 = int(np.floor(c0)), int(np.ceil(c1)), int(np.floor(r0)), int(np.ceil(r1))
    out = np.zeros((ri1 - ri0, ci1 - ci0), "float64")
    for ty in range(ri0 // tl, (ri1 - 1) // tl + 1):
        for tx in range(ci0 // tw, (ci1 - 1) // tw + 1):
            k = ty * ntx + tx; o, n = lev['off'][k], lev['cnt'][k]
            raw = zlib.decompress(get(url, o, o + n - 1)); nbytes[0] += n
            a = np.frombuffer(raw, "<u2").reshape(tl, tw).cumsum(axis=1, dtype=np.uint16)  # predictor 2
            ys, xs = ty * tl, tx * tw
            rs, re = max(ri0, ys), min(ri1, ys + tl); cs, ce = max(ci0, xs), min(ci1, xs + tw)
            out[rs - ri0:re - ri0, cs - ci0:ce - ci0] = a[rs - ys:re - ys, cs - xs:ce - xs]
    return out, (c0 - ci0, r0 - ri0, c1 - ci0, r1 - ri0)
def area_weights(n_out, start, step):
    # weights of source cells [i, i+1) for target cells [start + j*step, start + (j+1)*step)
    n_src = int(np.ceil(start + n_out * step)) + 1
    Wt = np.zeros((n_out, n_src))
    for j in range(n_out):
        a, b = start + j * step, start + (j + 1) * step
        for i in range(int(np.floor(a)), int(np.ceil(b))):
            Wt[j, i] = max(0, min(b, i + 1) - max(a, i))
    return Wt / Wt.sum(1, keepdims=True)
res = {}
for band in ("B04", "B08"):
    url = f"{B}/{band}.tif"; levs = levels(url); r = {}
    nb = [0]; a10, _ = window(url, levs[0], 10, nb); r["l0_bytes"] = nb[0]
    r["exact"] = a10.reshape(100, 6, 100, 6).mean(axis=(1, 3))
    r["nearest"] = a10[3::6, 3::6]
    nb = [0]; a20, _ = window(url, levs[1], 20, nb); r["l1_bytes"] = nb[0]
    r["nested20"] = a20.reshape(100, 3, 100, 3).mean(axis=(1, 3))
    nb = [0]; a40, (c0, r0, c1, r1) = window(url, levs[2], 40, nb); r["l2_bytes"] = nb[0]
    Wc = area_weights(100, c0, 1.5)[:, :a40.shape[1]]; Wr = area_weights(100, r0, 1.5)[:, :a40.shape[0]]
    r["area40"] = Wr @ a40 @ Wc.T
    res[band] = r
s, o = 1e-4, -0.1
nd = lambda m: ((res["B08"][m] * s + o) - (res["B04"][m] * s + o)) / ((res["B08"][m] * s + o) + (res["B04"][m] * s + o))
ref = nd("exact")
for m in ("nearest", "nested20", "area40"):
    print(f"{m:9s} mean |NDVI - exact 6x6| = {np.mean(np.abs(nd(m) - ref)):.5f}   max = {np.max(np.abs(nd(m) - ref)):.5f}")
for band in res:
    print(band, "compressed bytes read: 10 m", res[band]["l0_bytes"], "| 20 m ovr", res[band]["l1_bytes"], "| 40 m ovr", res[band]["l2_bytes"])
print("exact NDVI mean", ref.mean())
