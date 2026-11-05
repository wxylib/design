"""odc-geo's compute_output_geobox on the m26 source/target pairs.

    python measurements/m26-output-grid/odc_cases.py > measurements/m26-output-grid/odc_cases.json

Needs odc-geo (pip install odc-geo); defaults throughout (resolution
"auto", pixel edges snapped to 0, 0).
"""

import json
import sys

from odc.geo.geobox import GeoBox
from odc.geo.overlap import compute_output_geobox
from affine import Affine

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cases import SOURCES, TARGETS  # noqa: E402

out = {}
for sname, (crs, ext, size) in SOURCES.items():
    xmin, xmax, ymin, ymax = ext
    gt = Affine((xmax - xmin) / size[0], 0, xmin, 0, -(ymax - ymin) / size[1], ymax)
    g = GeoBox((size[1], size[0]), gt, crs)
    for tname, tcrs in TARGETS.items():
        if sname.startswith("world") and tname == "32755":
            continue
        key = f"{sname} -> {tname}"
        try:
            o = compute_output_geobox(g, tcrs)
            b = o.boundingbox
            out[key] = {"extent": [b.left, b.bottom, b.right, b.top],
                        "res": [o.resolution.x, -o.resolution.y],
                        "size": [o.shape.x, o.shape.y]}
        except Exception as e:  # noqa: BLE001
            out[key] = {"error": f"{type(e).__name__}: {e}"[:200]}
print(json.dumps(out, indent=1))
