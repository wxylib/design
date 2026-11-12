# Which streamflow chunks of one NWM medium-range channel file hold the five gauges used in the
# ganymede notebook, and what the float32 scale_factor does to the decoded value.
# Usage: python3 -I nwm_chunks.py nwm.t00z.medium_range.channel_rt_1.f024.conus.nc
import sys, h5py, numpy as np
GAUGE_REACHES = [19266232, 1840025, 6013072, 947070191, 15048349]
with h5py.File(sys.argv[1]) as f:
    fid = f["feature_id"][:]
    s = f["streamflow"]
    idx = [int(np.nonzero(fid == g)[0][0]) for g in GAUGE_REACHES]
    cs = s.chunks[0]
    print("streamflow", s.shape, "chunks", s.chunks, "gzip", s.compression_opts, "shuffle", s.shuffle)
    print("gauge indices", idx, "-> chunks", sorted({i // cs for i in idx}), "of", s.id.get_num_chunks())
    print("chunk bytes", [s.id.get_chunk_info(i).size for i in range(s.id.get_num_chunks())])
    print("feature_id sorted:", bool(np.all(np.diff(fid) > 0)))
    raw = int(s[idx[0]])
    sf = s.attrs["scale_factor"]
    print("raw", raw, "scale dtype", sf.dtype, "raw*float32(sf) =", raw * float(sf[0]), "raw*0.01 =", raw * 0.01)
