# Compare harvester CSV output against an mdim-refs fixture table.
# usage: compare.py <bin> <fixture refs parquet> <var> [maxfiles]
import subprocess, sys, time, collections
import pyarrow.parquet as pq
bin_, table, var = sys.argv[1:4]
maxfiles = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
rows = pq.read_table(table).to_pylist()
byfile = collections.OrderedDict()
for r in rows:
    if r['present']:
        byfile.setdefault(r['path'], []).append(r)
tot = ok = 0; bad = []
t0 = time.time()
for path, rs in list(byfile.items())[:maxfiles]:
    url = path.removeprefix('/vsicurl/')
    out = subprocess.run([bin_, url, var], capture_output=True, text=True)
    if out.returncode:
        bad.append((url, out.stderr.strip().splitlines()[:2])); continue
    got = set()
    for line in out.stdout.splitlines():
        _, ix, off, size, mask = line.split(',')
        got.add((ix, int(off), int(size)))
    # compare the (offset, size) sets per file; bran_check.py also checks chunk indices
    allwant = set((r['offset'], r['size']) for r in rs)
    allgot = set((o, s) for _, o, s in got)
    tot += len(allwant); ok += len(allwant & allgot)
    if allwant != allgot:
        bad.append((url, f'want {len(allwant)} got {len(allgot)} common {len(allwant & allgot)}'))
print(f'{bin_.split("/")[-1]} {var}: files {min(len(byfile), maxfiles)} refs {tot} matched {ok} mismatched-files {len(bad)} secs {time.time()-t0:.1f}')
for b in bad[:3]: print('  ', b)
