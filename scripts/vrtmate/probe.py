"""Count source kinds, path forms and fractional DstRect in a classic VRT.

Usage: python3 probe.py <file.vrt>
"""
import sys, collections, xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot()
gt = [float(v) for v in r.findtext('GeoTransform').split(',')]
print('size', r.get('rasterXSize'), r.get('rasterYSize'), 'gt', gt)
print('srs head', (r.findtext('SRS') or '')[:80])
bands = r.findall('VRTRasterBand'); print('bands', len(bands))
kinds = collections.Counter(); rel = collections.Counter(); frac = 0; srcrect_full = 0; n = 0
prefixes = collections.Counter(); ov = r.findall('.//Overview')
for b in bands:
    for s in b:
        if s.tag.endswith('Source'):
            kinds[s.tag] += 1; n += 1
            f = s.find('SourceFilename'); rel[f.get('relativeToVRT')] += 1
            prefixes[f.text.split('/')[1] if f.text.startswith('/') else f.text[:8]] += 1
            d = s.find('DstRect'); vals = [float(d.get(k)) for k in ('xOff','yOff','xSize','ySize')]
            if any(v != int(v) for v in vals): frac += 1
print('sources', n, dict(kinds)); print('relativeToVRT', dict(rel)); print('prefix', dict(prefixes))
print('fractional DstRect', frac, 'overviews', len(ov))
print('other band children', collections.Counter(c.tag for b in bands for c in b if not c.tag.endswith('Source')))
