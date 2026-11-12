# Chunks of one GOES-16 ABI-L2-LSTC file touched by the four regions of the ganymede notebook
# (pixel centre inside a lon/lat box, as the notebook selects), and the LST+DQF bytes they hold.
# Usage: python3 -I goes_lst_chunks.py OR_ABI-L2-LSTC-M6_G16_s20231962001177_...nc
import h5py, numpy as np, pyproj, sys
REGIONS = {"Sonoran":(32.5,33.5,-113.5,-112.5),"CentralValley":(36.0,36.8,-120.3,-119.5),"Cascade":(44.0,45.0,-122.5,-121.5),"CornBelt":(41.5,42.5,-94.5,-93.5)}
with h5py.File(sys.argv[1]) as f:
    a = {k:(v.decode() if isinstance(v,bytes) else (v[0] if hasattr(v,'__len__') and not isinstance(v,str) else v)) for k,v in f['goes_imager_projection'].attrs.items()}
    xs = f['x'][:]*f['x'].attrs['scale_factor'][0]+f['x'].attrs['add_offset'][0]
    ys = f['y'][:]*f['y'].attrs['scale_factor'][0]+f['y'].attrs['add_offset'][0]
    lst = f['LST']; dqf=f['DQF']
    # chunk byte sizes
    def sizes(ds):
        out={}
        for i in range(ds.id.get_num_chunks()):
            c=ds.id.get_chunk_info(i); out[c.chunk_offset]=c.size
        return out
    sl, sd = sizes(lst), sizes(dqf)
print("x step rad", xs[1]-xs[0], "y step", ys[1]-ys[0])
h=float(a['perspective_point_height'])
crs=pyproj.CRS.from_cf({k:a[k] for k in a if k!='long_name'})
print(crs.to_proj4())
X,Y=np.meshgrid(xs*h,ys*h)
lon,lat=pyproj.Transformer.from_crs(crs,"EPSG:4326",always_xy=True).transform(X,Y)
tot=set()
for n,(s,nn,w,e) in REGIONS.items():
    ins=(lat>=s)&(lat<=nn)&(lon>=w)&(lon<=e)
    r,c=np.nonzero(ins)
    ch=set(zip(r//250*250,c//250*250)); tot|=ch
    print(n, ins.sum(), "chunks", len(ch))
b=sum(sl[k]+sd[k] for k in tot)
print("chunks touched", len(tot), "of", len(sl), "bytes LST+DQF", b, "vs file 3151232")
print("offdisk pixels", np.sum(~np.isfinite(lon)))
# pixel ground size variation (approx) at region centres
