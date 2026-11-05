"""Write the three m29 figures as plain SVG (stdlib only).

    python3 figures.py results.jsonl ../../docs/img
"""
import json
import os
import sys

FONT = 'font-family="Helvetica, Arial, sans-serif"'
INK = "#2b3a4f"
GREY = "#555"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" {FONT} font-size="13">\n'
            '  <defs>\n'
            '    <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            'markerHeight="7" orient="auto-start-reverse">\n'
            '      <path d="M0,0 L10,5 L0,10 z" fill="#444"/>\n'
            '    </marker>\n'
            '  </defs>\n'
            f'  <rect width="{w}" height="{h}" fill="#ffffff"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def text(x, y, s, size=13, anchor="start", weight=None, fill=INK, rotate=None):
    extra = f' font-weight="{weight}"' if weight else ""
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'  <text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
            f'fill="{fill}"{extra}{tr}>{esc(s)}</text>')


# ---------------------------------------------------------------- figure 1
SYSTEMS = [
    "VRT XML", "vrt://", "GDALG pipeline", "Zarr v3", "kerchunk, VirtualiZarr",
    "Icechunk", "Iceberg, Delta, Lance", "DuckDB, Polars, SedonaDB", "JAX",
    "Arrow", "mirai, mori, mizu",
]
# 2 full, 1 partial, 0 none. One string per property, one digit per system.
PROPS = [
    ("Closure: the result opens like any input", "22201112200"),
    ("Names: sources from any format by name", "22201111000"),
    ("Placement of misaligned windows", "21100000000"),
    ("Assertion: state what a source lacks", "22111110000"),
    ("Deferral: plan before any byte", "22222222201"),
    ("Emission: tools write it", "20212221000"),
    ("Byte-level references", "00002210000"),
    ("History: commits, snapshots, tags", "00000220000"),
    ("Sources as rows with statistics", "00001122020"),
    ("Plan as a value an engine optimises", "11100000220"),
    ("Several independent implementations", "10022122021"),
    ("Zero-copy memory across languages", "00000001022"),
    ("Runs in a browser today", "11021111020"),
]


def fig_properties():
    left, top, cw, rh = 300, 150, 52, 26
    w = left + cw * len(SYSTEMS) + 110
    h = top + rh * len(PROPS) + 70
    b = [text(20, 28, "Six of VRT's properties, and what has been built since, one ecosystem at a time",
              14, weight="bold")]
    for j, s in enumerate(SYSTEMS):
        x = left + cw * j + cw / 2
        b.append(text(x + 4, top - 12, s, 12, rotate=-45))
    for i, (p, marks) in enumerate(PROPS):
        y = top + rh * i
        if i % 2 == 0:
            b.append(f'  <rect x="16" y="{y}" width="{w - 32}" height="{rh}" fill="#f4f7fb"/>')
        if i == 6:
            b.append(f'  <line x1="16" y1="{y}" x2="{w - 16}" y2="{y}" stroke="#7a9cbf" stroke-dasharray="4 3"/>')
        b.append(text(24, y + 17, p, 12, fill=INK if i < 6 else GREY))
        for j, m in enumerate(marks):
            cx, cy = left + cw * j + cw / 2, y + rh / 2
            if m == "2":
                b.append(f'  <circle cx="{cx}" cy="{cy}" r="7" fill="{INK}"/>')
            elif m == "1":
                b.append(f'  <circle cx="{cx}" cy="{cy}" r="7" fill="#ffffff" stroke="{INK}" stroke-width="1.5"/>')
                b.append(f'  <path d="M{cx},{cy - 7} A7,7 0 0,0 {cx},{cy + 7} z" fill="{INK}"/>')
            else:
                b.append(f'  <circle cx="{cx}" cy="{cy}" r="2" fill="#bbb"/>')
    b.append(f'  <rect x="{left - 4}" y="{top}" width="{cw + 8}" height="{rh * len(PROPS)}" '
             'fill="none" stroke="#c0504d" stroke-width="1.5" rx="4"/>')
    y = top + rh * len(PROPS) + 26
    b.append(text(24, y, "Above the dashed line: VRT's own properties. Below: what VRT lacks.", 12, fill=GREY))
    b.append(text(24, y + 18, "Filled: yes. Half: partly or in one family. Dot: no. "
             "A reading of each project's documentation, 2026-11-05, not a test.", 12, fill=GREY))
    return svg(w, h, b)


# ---------------------------------------------------------------- figure 2
def box(x, y, w, h, fill, stroke, lines, size=12):
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}"/>']
    n = len(lines)
    for k, (s, bold) in enumerate(lines):
        yy = y + h / 2 + (k - (n - 1) / 2) * 15 + 4
        out.append(text(x + w / 2, yy, s, size if not bold else 13, "middle",
                        "bold" if bold else None, INK if bold else GREY))
    return out


def fig_levels():
    w, h = 860, 580
    b = [text(20, 28, "One model on three levels; every existing form is a projection at one level",
              14, weight="bold")]
    # header column
    b += box(20, 60, 150, 370, "#fff8e8", "#c9a54a",
             [("Header", True), ("dimensions, types", False), ("CRS and grid", False),
              ("fill, packing, units", False), ("the m17 description", False),
              ("assertions live here", False)])
    levels = [
        ("Steps", "whole-array operations",
         "rows: step, inputs, parameters",
         ["DerivedArray, pixel functions", "Warped VRT, GDALG pipeline", "ArrIR chain (m22)"]),
        ("Placements", "windows of named sources",
         "rows: source name, source window, dest window, ops",
         ["VRT sources, vrt://", "GTI rows", "mdim-refs placements"]),
        ("Refs", "byte ranges by chunk key",
         "rows: key, uri, offset, size, codecs, etag",
         ["mdim-refs chunk tables", "kerchunk", "Icechunk manifests"]),
    ]
    ys = [60, 195, 330]
    for (name, sub, rows, forms), y in zip(levels, ys):
        b += box(200, y, 300, 100, "#eef4fa", "#7a9cbf", [(name, True), (sub, False), (rows, False)])
        b += box(560, y + 8, 280, 84, "#f7f7f7", "#bbbbbb", [(f, False) for f in forms])
        b.append(f'  <line x1="500" y1="{y + 50}" x2="556" y2="{y + 50}" stroke="#999" stroke-dasharray="3 3"/>')
    b.append(text(700, 54, "written forms and stores", 12, "middle", fill=GREY))
    # lowering and raising arrows between levels
    for y0, lo, hi in ((160, "lower: only re-indexing steps", "raise"),
                       (295, "lower: tiers T0 and T1 only", "raise: group refs by source")):
        y1 = y0 + 35
        b.append(f'  <line x1="300" y1="{y0}" x2="300" y2="{y1}" stroke="#444" marker-end="url(#a)"/>')
        b.append(f'  <line x1="400" y1="{y1}" x2="400" y2="{y0}" stroke="#444" marker-end="url(#a)"/>')
        b.append(text(294, y0 + 22, lo, 11, "end", fill="#444"))
        b.append(text(408, y0 + 22, hi, 11, fill="#444"))
    # bytes
    b += box(200, 470, 640, 50, "#f0f0f0", "#999999",
             [("bytes in place: COG tiles, netCDF/HDF5 chunks, Zarr chunks, GRIB messages", False)])
    b.append('  <line x1="350" y1="430" x2="350" y2="468" stroke="#444" marker-end="url(#a)"/>')
    b.append(text(358, 453, "fetch, decode", 11, fill="#444"))
    b.append(text(20, 555, "Every level is a table with the header beside it, so each is Arrow-native and planning "
                  "at any level is a filter and a join.", 12, fill=GREY))
    return svg(w, h, b)


# ---------------------------------------------------------------- figure 3
COLORS = {"T0": "#3a7d44", "T1": "#9cc59a", "T2": "#e0a43a", "T3": "#c0504d"}
LABELS = {"T0": "T0 regular refs", "T1": "T1 refs with chunk edges",
          "T2": "T2 needs a cut (overlap)", "T3": "T3 needs computing (resample, op)"}


def fig_tiers(results):
    rows = []
    rs = [json.loads(l) for l in open(results)]
    by = {}
    for r in rs:
        by.setdefault(r["file"], []).append(r)
    rows.append(("GHRSST MUR mdim.vrt (38,360)", by["ghrsst.vrt"][0]))
    rows.append(("COP30, OpenTopography (26,475)", by["cop30_sources.parquet"][0]))
    rows.append(("USGS 3DEP 1 arcsec, as written (3,817)", by["3dep.vrt"][0]))
    rows.append(("USGS 3DEP, offsets snapped at 0.15 px", by["3dep.vrt"][1]))
    corpus = {"T0": 0, "T1": 0, "T2": 0, "T3": 0, "n": 0}
    for f, lst in by.items():
        if f.startswith("c0"):
            for k in corpus:
                corpus[k] += lst[0][k]
    rows.append((f"fixtures/vrt corpus c01-c09 ({corpus['n']})", corpus))
    left, top, bw, bh, gap = 290, 70, 520, 26, 16
    w = left + bw + 30
    h = top + len(rows) * (bh + gap) + 100
    b = [text(20, 28, "How far real VRT placements lower toward byte references", 14, weight="bold")]
    b.append(text(20, 48, "share of placements per tier (measurements/m29-vrt-rework)", 12, fill=GREY))
    for i, (lab, r) in enumerate(rows):
        y = top + i * (bh + gap)
        b.append(text(left - 10, y + 17, lab, 12, "end"))
        x = left
        for t in ("T0", "T1", "T2", "T3"):
            frac = r[t] / r["n"] if r["n"] else 0
            ww = bw * frac
            if ww > 0:
                b.append(f'  <rect x="{x:.1f}" y="{y}" width="{ww:.1f}" height="{bh}" fill="{COLORS[t]}"/>')
                if ww > 40:
                    b.append(text(x + ww / 2, y + 17, f"{100 * frac:.0f}%", 11, "middle", fill="#ffffff"))
            x += ww
    y = top + len(rows) * (bh + gap) + 10
    for k, t in enumerate(("T0", "T1", "T2", "T3")):
        x, yy = 20 + 300 * (k % 2), y + 22 * (k // 2)
        b.append(f'  <rect x="{x}" y="{yy}" width="14" height="14" fill="{COLORS[t]}"/>')
        b.append(text(x + 20, yy + 12, LABELS[t], 12))
    b.append(text(20, y + 62, "3DEP's offsets drift by up to 0.10 px across the mosaic because its pixel size "
                  "is written as 2.777778e-4, not 1/3600 degree.", 12, fill=GREY))
    return svg(w, h, b)


def main():
    results, out = sys.argv[1], sys.argv[2]
    for name, s in (("m29-properties.svg", fig_properties()),
                    ("m29-levels.svg", fig_levels()),
                    ("m29-tiers.svg", fig_tiers(results))):
        with open(os.path.join(out, name), "w") as f:
            f.write(s)
        print(name)


if __name__ == "__main__":
    main()
