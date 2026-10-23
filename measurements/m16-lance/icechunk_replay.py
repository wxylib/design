"""icechunk_replay.py -- the same history as an Icechunk repo: bulk half-year,
one commit per day, one rescan, with a given manifest split along time.

Write side only: the array is created with the core zstd codec and no
predictor filter, so its chunks are not decodable as written; this measures
commit time and history size, not reads (render_icechunk does the readable
render, verified against GDAL).

Usage:
  python icechunk_replay.py FLAT_DIR OUT_REPO --split N [--target s3direct]
"""
import argparse
import asyncio
import json
import os
import shutil
import time

import icechunk
import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq
import zarr
from zarr.codecs import BytesCodec, ZstdCodec


def dirsize(p):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)


async def count(gen):
    n = 0
    async for _ in gen:
        n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("flat")
    p.add_argument("repo")
    p.add_argument("--split", type=int, required=True)
    p.add_argument("--target", default="s3direct")
    a = p.parse_args()
    doc = json.load(open(os.path.join(a.flat, "arrays.json")))
    meta = next(r for r in doc["arrays"] if r["storage"] == "referenced")
    rules = [r for r in doc.get("remap", []) if r["target"] == a.target]
    refs = pq.read_table(os.path.join(a.flat, f"refs_{meta['array']}.parquet"),
                         columns=["dim_0", "dim_1", "dim_2", "path", "offset", "size"])
    path = refs["path"].to_pylist()
    for r in rules:
        path = [r["replacement"] + x[len(r["prefix"]):] if x.startswith(r["prefix"]) else x for x in path]
    prefix = os.path.commonprefix(path)
    prefix = prefix[:prefix.rfind("/", 0, prefix.index("/ausantarctic/") + 1) + 1]

    cfg = icechunk.RepositoryConfig.default()
    if a.split > 0:
        cfg.manifest = icechunk.ManifestConfig(splitting=icechunk.ManifestSplittingConfig.from_dict(
            {icechunk.ManifestSplitCondition.AnyArray(): {icechunk.ManifestSplitDimCondition.Axis(0): a.split}}))
    cfg.set_virtual_chunk_container(icechunk.VirtualChunkContainer(prefix, icechunk.http_store()))
    shutil.rmtree(a.repo, ignore_errors=True)
    repo = icechunk.Repository.create(icechunk.local_filesystem_storage(a.repo), config=cfg,
                                      authorize_virtual_chunk_access={prefix: None})
    s = repo.writable_session("main")
    root = zarr.group(s.store)
    root.create_array(meta["array"], shape=meta["shape"], chunks=meta["chunks"], dtype=np.dtype(meta["dtype"]),
                      serializer=BytesCodec(endian="little"), compressors=[ZstdCodec(level=1)],
                      fill_value=int(meta["fill"]), dimension_names=meta["dims"])
    d0 = refs["dim_0"].to_numpy()
    d1, d2 = refs["dim_1"].to_numpy(), refs["dim_2"].to_numpy()
    off, size = refs["offset"].to_numpy(), refs["size"].to_numpy()

    def specs(lo, hi):
        idx = np.nonzero((d0 >= lo) & (d0 < hi))[0]
        return [icechunk.VirtualChunkSpec(index=[int(d0[i]), int(d1[i]), int(d2[i])], location=path[i],
                                          offset=int(off[i]), length=int(size[i])) for i in idx]

    log = {"split": a.split, "commits": []}
    t0 = time.time()
    for lo, hi in [(0, 182)] + [(t, t + 1) for t in range(182, 366)] + [(100, 101)]:
        sp = specs(lo, hi)
        t1 = time.time()
        failed = s.store.set_virtual_refs(meta["array"], sp, validate_containers=True)
        if failed:
            raise SystemExit(f"{len(failed)} refs rejected")
        snap = s.commit(f"days {lo}..{hi - 1}")
        log["commits"].append(round(time.time() - t1, 3))
        if (lo, hi) == (0, 182):
            repo.create_tag("first-half", snap)
        if (lo, hi) == (365, 366):
            repo.create_tag("year", snap)
        s = repo.writable_session("main")
    repo.create_tag("rescan", snap)
    log["replay_seconds"] = round(time.time() - t0, 1)
    log["bytes"] = dirsize(a.repo)
    log["bytes_manifests"] = dirsize(os.path.join(a.repo, "manifests"))
    log["n_manifests"] = len(os.listdir(os.path.join(a.repo, "manifests")))
    # time travel: refs present at each tag
    tt = {}
    for tag in ("first-half", "year", "rescan"):
        ro = repo.readonly_session(tag=tag)
        tt[tag] = asyncio.run(count(ro.chunk_coordinates("/" + meta["array"])))
    log["chunks_at_tag"] = tt
    daily = sorted(log["commits"][1:-1])
    log["daily_median_seconds"] = daily[len(daily) // 2]
    log["daily_last_seconds"] = log["commits"][-2]
    json.dump(log, open(a.repo.rstrip("/") + "-log.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in log.items() if k != "commits"}))


if __name__ == "__main__":
    main()
