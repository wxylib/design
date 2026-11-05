"""Write docs/img/m25-coverage.svg: which VRT families each implementation reads.

F = reads it as GDAL does (for the elements in the family), P = a subset,
- = not at all, T = target of the proposed model (section 6). Sources for
each cell are in m25 section 3.
"""
import sys

COLS = ["Mosaic\nplacement", "Source ops\n(window,\nscale, LUT)",
        "Derived,\npixel\nfunctions", "Warped", "vrt://\nstrings",
        "mdim\nVRT", "Vector\nVRT"]
ROWS = [
    ("GDAL 3.13 (C++)", "FFFFFFF"),
    ("GDAL in wasm (gdal3.js, Pyodide, webR; all 3.8.x)", "FFFFPFF"),
    ("terrio 0.7 (Rust, inside terrio)", "FFPF---"),
    ("OxiGeo vrt (Rust)", "FPPP---"),
    ("deck.gl-raster parseVRT (TS, 2026-11)", "P------"),
    ("maplibre-gl-raster parseVrt (TS, 2026-07)", "P------"),
    ("wxylib web mdim-vrt.js (JS)", "-----P-"),
    ("wxylib web ogrvrt.js (JS)", "------P"),
    ("Proposed: VRT model + planner (Rust, wasm)", "TTTTTTT"),
]
FILL = {"F": "#2f6f9f", "P": "#9cc3de", "-": "#f1f1f1", "T": "#ffffff"}
LABEL = {"F": "full", "P": "subset", "-": "", "T": "target"}

x0, y0, cw, rh = 330, 96, 78, 30
W = x0 + cw * len(COLS) + 20
H = y0 + rh * len(ROWS) + 76
o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
     'font-family="Helvetica, Arial, sans-serif" font-size="12">' % (W, H, W, H),
     '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
     '<text x="20" y="24" font-weight="bold" font-size="14" fill="#2b3a4f">'
     'Who reads which VRT family, 2026-11-05</text>']
for j, c in enumerate(COLS):
    lines = c.split("\n")
    for k, ln in enumerate(lines):
        o.append('<text x="%d" y="%d" text-anchor="middle" fill="#2b3a4f">%s</text>'
                 % (x0 + j * cw + cw / 2, y0 - 8 - 14 * (len(lines) - 1 - k), ln))
for i, (name, cells) in enumerate(ROWS):
    y = y0 + i * rh
    bold = ' font-weight="bold"' if name.startswith("Proposed") else ""
    o.append('<text x="20" y="%d"%s fill="#222">%s</text>' % (y + rh / 2 + 4, bold, name))
    for j, ch in enumerate(cells):
        x = x0 + j * cw
        dash = ' stroke-dasharray="4,3"' if ch == "T" else ""
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" fill="%s" stroke="#7a8a9a"%s/>'
                 % (x + 3, y + 3, cw - 6, rh - 6, FILL[ch], dash))
        col = "#ffffff" if ch == "F" else "#2b3a4f"
        o.append('<text x="%d" y="%d" text-anchor="middle" font-size="11" fill="%s">%s</text>'
                 % (x + cw / 2, y + rh / 2 + 4, col, LABEL[ch]))
o.append('<text x="20" y="%d" font-size="11" fill="#555">full: reads the family as GDAL does; '
         'subset: some elements or options; target: modelled and planned by the proposed crate.</text>' % (H - 46))
o.append('<text x="20" y="%d" font-size="11" fill="#555">Derived and warped bands are planned '
         'by the crate and evaluated by rwarp and wxy, not by it.</text>' % (H - 30))
o.append('<text x="20" y="%d" font-size="11" fill="#555">GDAL in wasm has vrt:// options up '
         'to 3.8 only (missing a_nodata, sd, sd_name from 3.9, transpose 3.12, block 3.13).</text>'
         % (H - 14))
o.append("</svg>")
open(sys.argv[1], "w").write("\n".join(o) + "\n")
