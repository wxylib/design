"""GDAL oracle for vrtcon.py: read each lowered VRT with GDAL (pyogrio) and
compare with GDAL's direct read of the source using the same filters.

  python check.py DATA_DIR > results.txt

DATA_DIR holds ne_110m_admin_0_countries.geojson (Natural Earth v5.1.2) and
stations.csv (wxylib/web www/data/vrt).
"""
import os, sys, tempfile
import numpy as np
import pyogrio
from pyogrio.raw import read
from vrtcon import lower

d = os.path.abspath(sys.argv[1])
ne = os.path.join(d, "ne_110m_admin_0_countries.geojson")
st = os.path.join(d, "stations.csv")
L = "ne_110m_admin_0_countries"

# (vrt:// string, direct-read keyword arguments that mean the same thing)
CASES = [
    ("vrt://%s?layer=%s&select=NAME,POP_EST&where=CONTINENT='Oceania'" % (ne, L),
     dict(columns=["NAME", "POP_EST"], where="CONTINENT='Oceania'")),
    ("vrt://%s?layer=%s&select=NAME&spat=100,-50,180,0" % (ne, L),
     dict(columns=["NAME"], bbox=(100, -50, 180, 0))),
    ("vrt://%s?layer=%s&sql=SELECT NAME FROM %s WHERE POP_EST > 100000000" % (ne, L, L),
     dict(sql="SELECT NAME FROM %s WHERE POP_EST > 100000000" % L)),
    ("vrt://%s?layer=stations&x=lon&y=lat&a_srs=EPSG:4326&where=operator='Australia'" % st,
     None),
    ("vrt://%s?layer=%s&select=NAME&where=CONTINENT='Antarctica'&t_srs=EPSG:3031" % (ne, L),
     None),
]

def summary(meta, fids, geom, fields):
    return (len(geom), [list(map(str, f)) for f in fields])

ok = 0
for uri, direct in CASES:
    xml = lower(uri)
    with tempfile.NamedTemporaryFile("w", suffix=".vrt", delete=False) as f:
        f.write(xml)
    meta, fids, geom, fields = read(f.name)
    got = summary(meta, fids, geom, fields)
    print("URI :", uri.replace(d + "/", ""))
    print("XML :", xml.replace(d + "/", ""))
    if direct is not None:
        m2, f2, g2, fl2 = read(ne, **direct)
        want = summary(m2, f2, g2, fl2)
        same = got == want and all(a == b for a, b in zip(geom, g2))
        print("GDAL: %d features via VRT, %d direct, geometry and fields %s"
              % (got[0], want[0], "identical" if same else "DIFFER"))
        ok += same
    else:
        print("GDAL: %d features, crs %s, first %s"
              % (got[0], meta["crs"], [str(v[0]) for v in fields] if got[0] else None))
        ok += got[0] > 0
    print()
print("%d of %d cases pass (GDAL %s)" % (ok, len(CASES), pyogrio.__gdal_version_string__))
