"""What gdalwarp infers for the target grid, case by case (m28).

    python measurements/m28-output-grid/gdal_matrix.py > measurements/m28-output-grid/gdal_matrix.json

Each source is an empty in-memory raster (only its grid and CRS matter).
Each case runs gdal.Warp to a VRT, which computes the output grid without
warping any pixels, and records the geotransform and size, or the error.
With only the target CRS given, the grid is GDALSuggestedWarpOutput2's
(then rounded by gdalwarp); a centre local-scale estimate sits beside it.
"""

import json
import math
import os
import sys

from osgeo import gdal, osr

gdal.UseExceptions()


def source(name, crs, extent, size):
    xmin, xmax, ymin, ymax = extent
    ds = gdal.GetDriverByName("MEM").Create(name, size[0], size[1], 1, gdal.GDT_Byte)
    ds.SetGeoTransform([xmin, (xmax - xmin) / size[0], 0, ymax, 0, -(ymax - ymin) / size[1]])
    s = osr.SpatialReference()
    s.SetFromUserInput(crs)
    ds.SetProjection(s.ExportToWkt())
    return ds


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import SOURCES, TARGETS  # noqa: E402


def grid(ds):
    gt = ds.GetGeoTransform()
    nx, ny = ds.RasterXSize, ds.RasterYSize
    return {
        "extent": [gt[0], gt[3] + ny * gt[5], gt[0] + nx * gt[1], gt[3]],
        "res": [gt[1], -gt[5]],
        "size": [nx, ny],
    }


LIMIT = 1e9  # cells; past this GDAL 3.8 aborts the process (std::length_error)


def run(src, dst_crs, **kw):
    if "xRes" in kw and "outputBounds" not in kw:
        g = run(src, dst_crs)
        e = g["extent"]
        n = (e[2] - e[0]) / kw["xRes"] * (e[3] - e[1]) / kw["yRes"]
        if n > LIMIT:
            return {"error": f"not run: {n:.3g} cells at this -tr over the "
                             "suggested extent (GDAL 3.8 aborts the process)"}
    try:
        out = gdal.Warp("", src, format="VRT", dstSRS=dst_crs, **kw)
        return grid(out)
    except RuntimeError as e:
        return {"error": str(e).strip()}


def local_scale(src, dst_crs):
    """Cell size at the source centre, mapped to the target: the length of
    one source cell step in x and in y, as target units (the m28 rule)."""
    t = gdal.Transformer(src, None, [f"DST_SRS={dst_crs}"])
    nx, ny = src.RasterXSize, src.RasterYSize
    cx, cy = nx / 2, ny / 2
    p, ok = t.TransformPoints(0, [(cx, cy), (cx + 1, cy), (cx, cy + 1)])
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = p
    dx = math.hypot(x1 - x0, y1 - y0)
    dy = math.hypot(x2 - x0, y2 - y0)
    return {"centre": [x0, y0], "step_x": dx, "step_y": dy,
            "res_geomean": math.sqrt(dx * dy)}


out = {"gdal": gdal.__version__, "suggested": {}, "matrix": {}}

for sname, (crs, ext, size) in SOURCES.items():
    src = source(sname, crs, ext, size)
    for tname, tcrs in TARGETS.items():
        if sname.startswith("world") and tname == "32755":
            continue
        key = f"{sname} -> {tname}"
        out["suggested"][key] = {
            "gdal": run(src, tcrs),
            "local_scale": local_scale(src, tcrs),
            "source_cells": size[0] * size[1],
        }

# The option matrix, on one well-behaved pair and one awkward pair.
PAIRS = {
    "utm55s-10m -> 4326": ("utm55s-10m", "EPSG:4326",
                           [146.99, -43.42, 148.36, -42.4], 0.0001, "EPSG:4326"),
    "world-0.5 -> 3031": ("world-0.5", "EPSG:3031",
                          [-4e6, -4e6, 4e6, 4e6], 25000, "EPSG:3031"),
}
for pname, (sname, tcrs, te, tr, _) in PAIRS.items():
    crs, ext, size = SOURCES[sname]
    src = source(sname, crs, ext, size)
    m = {}
    m["t_srs only"] = run(src, tcrs)
    m["-tr"] = run(src, tcrs, xRes=tr, yRes=tr)
    m["-tr -tap"] = run(src, tcrs, xRes=tr, yRes=tr, targetAlignedPixels=True)
    m["-ts 1000 1000"] = run(src, tcrs, width=1000, height=1000)
    m["-ts 1000 0"] = run(src, tcrs, width=1000, height=0)
    m["-te"] = run(src, tcrs, outputBounds=te)
    m["-te -tr"] = run(src, tcrs, outputBounds=te, xRes=tr, yRes=tr)
    m["-te -tr (not a multiple)"] = run(src, tcrs, outputBounds=te,
                                        xRes=tr * 1.37, yRes=tr * 1.37)
    m["-te -tr -tap"] = run(src, tcrs, outputBounds=te, xRes=tr * 1.37,
                            yRes=tr * 1.37, targetAlignedPixels=True)
    m["-te -ts 1000 1000"] = run(src, tcrs, outputBounds=te, width=1000, height=1000)
    m["-te -ts 1000 0"] = run(src, tcrs, outputBounds=te, width=1000, height=0)
    m["-tr -ts"] = run(src, tcrs, xRes=tr, yRes=tr, width=1000, height=1000)
    m["-tap without -tr"] = run(src, tcrs, targetAlignedPixels=True)
    m["-te_srs EPSG:4326"] = run(src, tcrs, outputBounds=[140, -70, 160, -60],
                                 outputBoundsSRS="EPSG:4326")
    out["matrix"][pname] = m

print(json.dumps(out, indent=1))
