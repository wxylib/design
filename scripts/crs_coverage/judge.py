"""Judge the engine results (r-*.jsonl) against cases.json; print a markdown grid.

exact: forward and inverse within 1 mm of PROJ; close: within 1 m; OFF: further;
no: refused or failed. Run: python3 judge.py
"""
import json, math, sys
S=sys.argv[1] if len(sys.argv) > 1 else "."
cases={c['id']:c for c in json.load(open(f'{S}/cases.json'))['cases']}
rows=[json.loads(l) for f in ('r-a','r-m','r-mf') for l in open(f'{S}/{f}.jsonl')]
engines=[]
for r in rows:
    if r['engine'] not in engines: engines.append(r['engine'])
def verdict(c,r):
    if r['fwd'] is None:
        e=r['fwd_err'] or ''
        return 'no', e
    o=c['oracle']; f=r['fwd']
    geo = c['dst'].startswith('EPSG:4') or 'ob_tran' in c['dst'] or c['id']=='4283-7844'
    if geo:
        d=math.hypot((f[0]-o[0])*math.cos(math.radians(o[1])),f[1]-o[1])*111320
    else:
        d=math.hypot(f[0]-o[0],f[1]-o[1])
    inv=r['inv']
    di = None if inv is None else math.hypot((inv[0]-c['oracle_inv'][0])*math.cos(math.radians(c['lat'])),inv[1]-c['oracle_inv'][1])*111320
    if d<1e-3 and (di is None or di<1e-3): v='exact'
    elif d<1: v='close'
    else: v='OFF'
    s=f"{d:.3g} m" if v!='exact' else ''
    if inv is None: s+=' (no inverse)'
    elif di is not None and di>=1e-3: s+=f' inv {di:.3g} m'
    return v, s.strip()
grid={}
for r in rows: grid[(r['id'],r['engine'])]=verdict(cases[r['id']],r)
print('| case | group | '+' | '.join(engines)+' |')
print('|---|---|'+'---|'*len(engines))
for cid,c in cases.items():
    cells=[]
    for e in engines:
        v,s=grid[(cid,e)]
        cells.append(v if v=='exact' else (f'{v} {s}' if v!='no' else 'no'))
    print(f'| {cid} | {c["group"]} | '+' | '.join(cells)+' |')
print()
for e in engines:
    vs=[grid[(cid,e)][0] for cid in cases]
    print(e, {k:vs.count(k) for k in ('exact','close','OFF','no')})
print()
for (cid,e),(v,s) in grid.items():
    if v=='no': print('NO',cid,e,s[:110])
