"""Classify each placement of a VRT by how far it lowers toward byte refs.

Tiers (m29 section 4):
  T0 regular  - integer, unresampled, no pixel op, offset on the chunk grid:
                a regular-grid virtual Zarr (kerchunk, Icechunk) holds it.
  T1 edges    - as T0 but off the regular grid and not overlapping another
                placement: needs per-axis chunk edges (rectilinear grid).
  T2 cut      - integer and unresampled but overlapping another placement:
                needs a cut first (m10), then T0 or T1.
  T3 compute  - fractional offset, size change or a pixel op: only an
                evaluator can produce the values.

Also times: whole-document XML parse, and one-window source lookup from a
Parquet table of the same placements (pyarrow, optional).

Usage: python3 tiers.py classic <file.vrt> [block]
       python3 tiers.py mdim <file.vrt>
       python3 tiers.py cop30 <cop30_sources.parquet>
"""
import json
import sys
import time
import xml.etree.ElementTree as ET


SNAP = float(__import__("os").environ.get("SNAP_PX", "1e-3"))


def is_int(v, tol=None):
    tol = SNAP if tol is None else tol
    return abs(v - round(v)) < tol


def rect(el):
    return tuple(float(el.get(k)) for k in ("xOff", "yOff", "xSize", "ySize"))


def classic_rows(path):
    t0 = time.perf_counter()
    root = ET.parse(path).getroot()
    parse_s = time.perf_counter() - t0
    rows = []
    for band in root.iter("VRTRasterBand"):
        bnodata = band.findtext("NoDataValue")
        for src in band:
            if not src.tag.endswith("Source"):
                continue
            sr, dr = src.find("SrcRect"), src.find("DstRect")
            props = src.find("SourceProperties")
            sxs = sys_ = None
            if props is not None:
                sxs, sys_ = float(props.get("RasterXSize")), float(props.get("RasterYSize"))
            bx = by = None
            if props is not None and props.get("BlockXSize"):
                bx, by = int(props.get("BlockXSize")), int(props.get("BlockYSize"))
            s = rect(sr) if sr is not None else (0, 0, sxs, sys_)
            d = rect(dr) if dr is not None else s
            ops = []
            for k in ("ScaleOffset", "ScaleRatio", "LUT", "Exponent", "ComplexSourceProperties"):
                if src.find(k) is not None:
                    ops.append(k)
            nd = src.findtext("NODATA")
            if nd is not None and nd != bnodata:
                ops.append("NODATA")
            if src.tag in ("AveragedSource", "KernelFilteredSource"):
                ops.append(src.tag)
            rows.append(dict(band=int(band.get("band")), name=src.findtext("SourceFilename"),
                             src=s, dst=d, block=(bx, by), full=(sxs, sys_), ops=ops))
    return root, rows, parse_s


def classify_classic(rows, chunk=None):
    out = []
    integral = []
    for r in rows:
        s, d = r["src"], r["dst"]
        if r["ops"] or not all(is_int(v) for v in d) or (s[2], s[3]) != (d[2], d[3]):
            out.append("T3")
            integral.append(None)
            continue
        integral.append(tuple(int(round(v)) for v in d))
        out.append(None)
    # overlap among integral placements, per band (grid hash)
    cell = 4096
    buckets = {}
    for i, (r, d) in enumerate(zip(rows, integral)):
        if d is None:
            continue
        x0, y0, w, h = d
        for gx in range(x0 // cell, (x0 + w - 1) // cell + 1):
            for gy in range(y0 // cell, (y0 + h - 1) // cell + 1):
                buckets.setdefault((r["band"], gx, gy), []).append(i)
    overl = set()
    for idx in buckets.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                ax, ay, aw, ah = integral[i]
                bx, by, bw, bh = integral[j]
                if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                    overl.add(i)
                    overl.add(j)
    for i, r in enumerate(rows):
        if out[i]:
            continue
        if i in overl:
            out[i] = "T2"
            continue
        bx, by = chunk or r["block"]
        x0, y0, w, h = integral[i]
        s = r["src"]
        on_grid = bx and x0 % bx == 0 and y0 % by == 0 and s[0] % bx == 0 and s[1] % by == 0
        out[i] = "T0" if on_grid else "T1"
    return out


def mdim_rows(path):
    t0 = time.perf_counter()
    root = ET.parse(path).getroot()
    parse_s = time.perf_counter() - t0
    rows = []
    for arr in root.iter("Array"):
        bs = arr.findtext("BlockSize")
        block = [int(v) for v in bs.split(",")] if bs else None
        for src in arr.findall("Source"):
            slab = src.find("SourceSlab")
            dest = src.find("DestSlab")
            step = [int(v) for v in slab.get("step").split(",")] if slab is not None else None
            dst = [int(v) for v in dest.get("offset").split(",")] if dest is not None else None
            soff = [int(v) for v in slab.get("offset").split(",")] if slab is not None else None
            ops = [k for k in ("SourceView",) if src.find(k) is not None]
            rows.append(dict(array=arr.get("name"), name=src.findtext("SourceFilename"),
                             block=block, step=step, dst=dst, soff=soff, ops=ops))
    return root, rows, parse_s


def classify_mdim(rows):
    out = []
    for r in rows:
        if r["ops"] or (r["step"] and any(s != 1 for s in r["step"])):
            out.append("T3")
        elif r["block"] and r["dst"] and all(o % b == 0 for o, b in zip(r["dst"], r["block"])) \
                and all(o % b == 0 for o, b in zip(r["soff"], r["block"])):
            out.append("T0")
        else:
            out.append("T1")
    return out


def census(tiers):
    n = len(tiers)
    c = {t: tiers.count(t) for t in ("T0", "T1", "T2", "T3")}
    return dict(n=n, **c, **{t + "_pct": round(100 * v / n, 1) if n else 0 for t, v in c.items()})


def table_lookup(cols, pred_col, lo, hi):
    """Write placements as Parquet in memory; time a one-window lookup."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pyarrow.compute as pc
    except ImportError:
        return None
    import io
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    t = pa.table(cols)
    buf = io.BytesIO()
    pq.write_table(t, buf, row_group_size=4096, compression="zstd")
    size = buf.tell()
    buf.seek(0)
    t0 = time.perf_counter()
    tab = pq.read_table(buf, filters=[(pred_col, ">=", lo), (pred_col, "<", hi)])
    look_s = time.perf_counter() - t0
    return dict(parquet_bytes=size, lookup_s=round(look_s, 4), hits=tab.num_rows)


def main():
    mode, path = sys.argv[1], sys.argv[2]
    res = dict(mode=mode, file=path.split("/")[-1])
    if mode == "classic":
        import os
        res["xml_bytes"] = os.path.getsize(path)
        root, rows, ps = classic_rows(path)
        chunk = None
        if len(sys.argv) > 3:
            b = int(sys.argv[3])
            chunk = (b, b)
        tiers = classify_classic(rows, chunk)
        res.update(parse_s=round(ps, 3), **census(tiers))
        ops = {}
        for r in rows:
            for o in r["ops"]:
                ops[o] = ops.get(o, 0) + 1
        frac = sum(1 for r in rows if not all(is_int(v) for v in r["dst"][:2]))
        resz = sum(1 for r in rows if (r["src"][2], r["src"][3]) != (r["dst"][2], r["dst"][3]))
        res.update(ops=ops, fractional_offset=frac, size_change=resz)
        if rows:
            look = table_lookup(dict(name=[r["name"] for r in rows],
                                     xoff=[r["dst"][0] for r in rows],
                                     yoff=[r["dst"][1] for r in rows],
                                     w=[r["dst"][2] for r in rows],
                                     h=[r["dst"][3] for r in rows]),
                                "xoff", rows[0]["dst"][0], rows[0]["dst"][0] + 4000)
            res["table"] = look
    elif mode == "mdim":
        import os
        res["xml_bytes"] = os.path.getsize(path)
        root, rows, ps = mdim_rows(path)
        tiers = classify_mdim(rows)
        res.update(parse_s=round(ps, 3), **census(tiers))
        res["arrays"] = sorted({r["array"] for r in rows})
        look = table_lookup(dict(array=[r["array"] for r in rows],
                                 name=[r["name"] for r in rows],
                                 t=[r["dst"][0] for r in rows]),
                            "t", 8000, 8001)
        res["table"] = look
    elif mode == "cop30":
        import pyarrow.parquet as pq
        t = pq.read_table(path).to_pylist()
        rows = [dict(band=1, name=r["filename"], src=(0, 0, r["src_w"], r["src_h"]),
                     dst=(r["dst_xoff"], r["dst_yoff"], r["dst_w"], r["dst_h"]),
                     block=(None, None), ops=[]) for r in t]
        tiers = classify_classic(rows, (1024, 1024))
        res.update(**census(tiers))
        res["fractional_offset"] = sum(1 for r in rows if not all(is_int(v) for v in r["dst"][:2]))
        res["size_change"] = sum(1 for r in rows if (r["src"][2], r["src"][3]) != (r["dst"][2], r["dst"][3]))
    print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
    import os
    os._exit(0)  # pyarrow's thread pools can stall interpreter exit in sandboxes
