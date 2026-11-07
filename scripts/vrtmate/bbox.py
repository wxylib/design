"""Compare a corner-in-box intersection test (as in VRTMate.rastersByBBox)
with an interval overlap test, on random query boxes over CONUS.

Usage: python3 bbox.py <file.vrt>
"""
import sys, random, xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot()
x0, xr, _, y0, _, yr = [float(v) for v in r.findtext('GeoTransform').split(',')]
tiles = []
for s in r.find('VRTRasterBand'):
    if not s.tag.endswith('Source'): continue
    d = s.find('DstRect'); xo, yo, xs, ys = (float(d.get(k)) for k in ('xOff','yOff','xSize','ySize'))
    xmin = x0 + xo*xr; ymax = y0 + yo*yr
    tiles.append((xmin, xmin + xs*xr, ymax + ys*yr, ymax))
def inside(px, py, b): return b[0] <= px <= b[1] and b[2] <= py <= b[3]
def corners(a, b): return any(inside(px, py, b) for px in (a[0], a[1]) for py in (a[2], a[3]))
def vrtmate(a, b): return corners(a, b) or corners(b, a)
def overlap(a, b): return a[0] <= b[1] and b[0] <= a[1] and a[2] <= b[3] and b[2] <= a[3]
random.seed(1)
for label, wmin, wmax, aspect in [("map-like 1-8 deg, aspect 0.5-2", 1, 8, (0.5, 2)),
                                  ("phone portrait 0.5-2 deg wide, 2x tall", 0.5, 2, (2, 2.5)),
                                  ("strips 0.2-1 deg wide, 3-10 deg tall", 0.2, 1, (3, 50))]:
    nq = 2000; nmiss_q = 0; tot = 0; miss = 0
    for _ in range(nq):
        w = random.uniform(wmin, wmax); h = w*random.uniform(*aspect)
        if label.startswith("strips"): h = random.uniform(3, 10)
        cx = random.uniform(-120, -75); cy = random.uniform(30, 47)
        q = (cx - w/2, cx + w/2, cy - h/2, cy + h/2)
        good = [t for t in tiles if overlap(q, t)]; got = [t for t in good if vrtmate(q, t)]
        tot += len(good); miss += len(good) - len(got); nmiss_q += len(got) < len(good)
    print(f"{label}: queries with a missed tile {nmiss_q}/{nq} ({100*nmiss_q/nq:.1f}%), tiles missed {miss}/{tot} ({100*miss/tot:.2f}%)")
print("tiles", len(tiles))
