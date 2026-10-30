# Check a harvester's CSV for one BRAN2023 file against the fixture table
# by chunk index, offset and size.
# usage: bran_check.py <fixture refs_temp.parquet> <url> <harvest.csv>
import sys
import pyarrow.parquet as pq
table, url, csv = sys.argv[1:4]
rows = [r for r in pq.read_table(table).to_pylist() if r['path'] == url and r['present']]
got = {}
for line in open(csv):
    _, ix, off, size, mask = line.strip().split(',')
    got[tuple(map(int, ix.split(':')))] = (int(off), int(size), int(mask))
ok = sum(1 for r in rows if got.get((r['dim_0'], r['dim_1'], r['dim_2'], r['dim_3'])) == (r['offset'], r['size'], 0))
print(f'fixture rows {len(rows)} harvested {len(got)} exact {ok} nonzero masks {sum(1 for v in got.values() if v[2])}')
