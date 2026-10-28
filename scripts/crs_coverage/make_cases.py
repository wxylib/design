"""Write cases.json: the CRS cases wxylib needs, each with PROJ's answer.

The oracle is pyproj (PROJ), network off, no extra grids, always_xy.
Run: python3 make_cases.py
"""
import json

import pyproj
from pyproj import CRS

W = "EPSG:4326"
CASES = [
    # id, group, src, dst, lon, lat
    ("3031", "epsg-polar", W, "EPSG:3031", 147, -75),
    ("3412", "epsg-polar", W, "EPSG:3412", 0, -70),
    ("3413", "epsg-polar", W, "EPSG:3413", -45, 75),
    ("3976", "epsg-polar", W, "EPSG:3976", 100, -65),
    ("9354", "epsg-polar", W, "EPSG:9354", 30, -68),
    ("3577", "epsg-other", W, "EPSG:3577", 147, -35),
    ("32755", "epsg-other", W, "EPSG:32755", 147, -42),
    ("3857", "epsg-other", W, "EPSG:3857", 147, -42),
    ("6933", "epsg-other", W, "EPSG:6933", 147, -42),
    ("3112", "epsg-other", W, "EPSG:3112", 133, -25),
    ("4283-7844", "datum", "EPSG:4283", "EPSG:7844", 147, -42),
    ("4269-26711", "datum", "EPSG:4269", "EPSG:26711", -117, 34),
    ("laea-south", "proj-polar", W, "+proj=laea +lat_0=-90 +lon_0=0 +datum=WGS84 +units=m", 147, -70),
    ("laea-north", "proj-polar", W, "+proj=laea +lat_0=90 +lon_0=0 +datum=WGS84 +units=m", 10, 70),
    ("aeqd-south", "proj-polar", W, "+proj=aeqd +lat_0=-90 +lon_0=0 +datum=WGS84 +units=m", 147, -60),
    ("aeqd-oblique", "proj-local", W, "+proj=aeqd +lat_0=-42 +lon_0=147 +datum=WGS84 +units=m", 150, -40),
    ("stere-south", "proj-polar", W, "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +datum=WGS84 +units=m", 147, -75),
    ("ob_tran-cordex", "proj-rotated", W, "+proj=ob_tran +o_proj=longlat +o_lon_p=-162 +o_lat_p=39.25 +lon_0=180 +datum=WGS84", 10, 50),
    ("ortho", "proj-local", W, "+proj=ortho +lat_0=-42 +lon_0=147 +ellps=WGS84 +units=m", 140, -30),
    ("geos-himawari", "proj-sat", W, "+proj=geos +h=35785831 +lon_0=140.7 +sweep=y +datum=WGS84 +units=m", 147, -42),
    ("geos-goes", "proj-sat", W, "+proj=geos +h=35786023 +lon_0=-75 +sweep=x +ellps=GRS80 +units=m", -80, 30),
    ("sinu-modis", "proj-world", W, "+proj=sinu +R=6371007.181 +units=m", 147, -42),
    ("moll", "proj-world", W, "+proj=moll +datum=WGS84 +units=m", 147, -42),
    ("eqearth", "proj-world", W, "+proj=eqearth +datum=WGS84 +units=m", 147, -42),
    ("robin", "proj-world", W, "+proj=robin +datum=WGS84 +units=m", 147, -42),
    ("igh", "proj-world", W, "+proj=igh +datum=WGS84 +units=m", 147, -42),
    ("eqc", "proj-world", W, "+proj=eqc +datum=WGS84 +units=m", 147, -42),
    ("gnom-south", "proj-polar", W, "+proj=gnom +lat_0=-90 +lon_0=0 +R=6371000 +units=m", 147, -60),
    ("tpers", "proj-local", W, "+proj=tpers +h=5500000 +lat_0=-42 +lon_0=147 +tilt=10 +azi=20 +ellps=WGS84 +units=m", 145, -40),
    ("nsper", "proj-local", W, "+proj=nsper +h=3000000 +lat_0=-42 +lon_0=147 +ellps=WGS84 +units=m", 145, -40),
]
FORMS = [
    ("3031-wkt2", "form", W, CRS("EPSG:3031").to_wkt(), 147, -75),
    ("3031-projjson", "form", W, CRS("EPSG:3031").to_json(), 147, -75),
    ("3031-crs84", "form", "OGC:CRS84", "EPSG:3031", 147, -75),
    ("102020-esri", "form", W, "ESRI:102020", 147, -75),
    ("3031-wkt1", "form", W, CRS("EPSG:3031").to_wkt("WKT1_GDAL"), 147, -75),
]

out = []
for cid, group, src, dst, lon, lat in CASES + FORMS:
    fwd = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    x, y = fwd.transform(lon, lat)
    ilon, ilat = pyproj.Transformer.from_crs(dst, src, always_xy=True).transform(x, y)
    out.append(dict(id=cid, group=group, src=src, dst=dst, lon=lon, lat=lat,
                    oracle=[x, y], oracle_inv=[ilon, ilat], op=fwd.description))
with open("cases.json", "w") as f:
    json.dump(dict(proj=pyproj.proj_version_str, pyproj=pyproj.__version__, cases=out), f, indent=1)
