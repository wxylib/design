# Pilot scan of one rasterwise release bundle with osgeo.gdal.
# usage: python3 -I pilot.py <extracted bundle dir> <rasterwise manifest.csv> > pilot.jsonl
# Records, per file: manifest match by sha256, case, sniffed format, classic
# open (driver, subdatasets, size, geotransform, CRS) and multidim open.
import sys, csv, hashlib, os, json
from osgeo import gdal
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')
root, man = sys.argv[1], sys.argv[2]
m = {r['sha256']: r for r in csv.DictReader(open(man))}
rows=[]
for dp,_,fs in os.walk(root):
  for f in sorted(fs):
    p=os.path.join(dp,f); h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    r=m.get(h,{}); rec={'path':os.path.relpath(p,root),'in_manifest':bool(r),'case':r.get('case',''),'format':r.get('format','')}
    try:
      ds=gdal.Open(p); rec['classic']=ds.GetDriver().ShortName
      sds=ds.GetMetadata('SUBDATASETS'); rec['nsds']=len(sds)//2
      if ds.RasterCount: rec['size']=(ds.RasterXSize,ds.RasterYSize,ds.RasterCount); rec['gt']=ds.GetGeoTransform(can_return_null=True) is not None; rec['srs']=bool(ds.GetProjectionRef())
    except Exception as e: rec['classic']='refused'
    try:
      md=gdal.OpenEx(p,gdal.OF_MULTIDIM_RASTER); rg=md.GetRootGroup()
      rec['mdim_arrays']=len(rg.GetMDArrayNames() or [])
    except Exception as e: rec['mdim_arrays']='refused'
    rows.append(rec)
for r in rows: print(json.dumps(r))
