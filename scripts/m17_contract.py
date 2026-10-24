"""Description contract check for published byte-reference stores (design m17).

Reads a store's own description and reports, per data array, whether each
contract item is stated (explicit), follows a format convention, has to be
derived or inferred, is missing, or conflicts with itself. Two inputs are
understood:

- kerchunk Parquet: the store's `.zmetadata` (a local path or a URL; a
  directory or `.parq` store path gets `/.zmetadata` appended);
- mdim-refs/0.2 export: `arrays.json` (with `manifest.json` beside it when
  there is one).

Options:

  --oracle FILE   compare fill, packing, units and calendar with what
                  osgeo.gdal's multidimensional API reads from one source
                  file (netCDF or HDF5). Byte checks compare stored
                  integers, so they cannot catch a wrong scale_factor;
                  this does.
  --json          print one JSON record per array instead of a table.

Two or more stores are compared on their packing and fill, the cheapest
way to find two builds of the same data that decode differently.

Exit status is 1 when any conflict row is found (or an oracle mismatch),
so the script can gate CI or a publish step. Standard library only, apart
from osgeo.gdal for --oracle.
"""

import argparse
import json
import math
import os
import sys
import urllib.request

STATES = ("explicit", "convention", "derived", "inferred", "missing", "conflict")


def _reject(token):
    raise ValueError("bare %s in JSON (not strict JSON)" % token)


def fetch(loc):
    if "://" in loc:
        with urllib.request.urlopen(loc) as r:
            return r.read().decode("utf-8")
    with open(loc, encoding="utf-8") as f:
        return f.read()


def load(loc):
    """(kind, text) for a store location."""
    if loc.endswith("arrays.json"):
        return "mdimrefs", fetch(loc)
    if not loc.endswith(".zmetadata"):
        loc = loc.rstrip("/") + "/.zmetadata"
    return "kerchunk", fetch(loc)


def parse(text):
    """(document, strict) where strict says whether it parsed as strict JSON."""
    try:
        return json.loads(text, parse_constant=_reject), True
    except ValueError:
        return json.loads(text), False


def unwrap(v):
    # R writers keep CF attributes as one-element lists
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def arrays_from_kerchunk(doc):
    meta = doc.get("metadata", {})

    def get(k):
        v = meta.get(k, {})
        return json.loads(v) if isinstance(v, str) else v

    out = {}
    for key in meta:
        if not key.endswith("/.zarray"):
            continue
        name = key[: -len("/.zarray")]
        za = get(key)
        at = {k: unwrap(v) for k, v in get(name + "/.zattrs").items()}
        out[name] = {
            "dims": at.pop("_ARRAY_DIMENSIONS", None),
            "shape": za.get("shape"),
            "chunks": za.get("chunks"),
            "dtype": za.get("dtype"),
            "fill": za.get("fill_value"),
            "codec": {"compressor": za.get("compressor"), "filters": za.get("filters")},
            "attrs": at,
            "storage": None,
            "affine": None,
            "values": None,
        }
    return out


def arrays_from_mdimrefs(doc):
    out = {}
    for a in doc.get("arrays", []):
        fill = a.get("fill")
        if isinstance(fill, str):
            try:
                fill = float(fill)
            except ValueError:
                pass
        out[a["array"]] = {
            "dims": a.get("dims"),
            "shape": a.get("shape"),
            "chunks": a.get("chunks"),
            "dtype": a.get("dtype"),
            "fill": fill,
            "codec": a.get("codec"),
            "attrs": {k: unwrap(v) for k, v in (a.get("attrs") or {}).items()},
            "storage": a.get("storage"),
            "affine": a.get("affine"),
            "values": a.get("values"),
            "kind": a.get("kind"),
        }
    return out


def num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None  # base64 fills and the like are not compared
    return None


def same(a, b):
    return a == b or (math.isnan(a) and math.isnan(b))


def axis_role(name, at):
    """(role, state) of a dimension from its coordinate's attributes."""
    for k in ("axis", "cartesian_axis"):
        v = at.get(k)
        if isinstance(v, str) and v.upper() in ("X", "Y", "Z", "T", "N"):
            return v.upper(), "explicit"
    units = str(at.get("units", "")).lower()
    sn = str(at.get("standard_name", "")).lower()
    n = name.lower()
    if "since" in units or n in ("time", "t"):
        return "T", "inferred"
    if sn == "latitude" or units.startswith("degrees_n") or n.startswith("lat"):
        return "Y", "inferred"
    if sn == "longitude" or units.startswith("degrees_e") or n.startswith("lon"):
        return "X", "inferred"
    if "positive" in at or n in ("depth", "z", "lev", "zlev"):
        return "Z", "inferred"
    return None, "missing"


def check_array(name, a, arrays, kind, strict, manifest):
    rows = {}

    def put(item, state, note=""):
        rows[item] = {"state": state, "note": note}

    at = a["attrs"]
    put("strict_json", "explicit" if strict else "inferred",
        "" if strict else "bare NaN/Infinity tokens; repaired before parsing")
    if kind == "mdimrefs":
        put("chunk_to_row", "explicit", "each row carries its chunk key")
        put("missing_chunks", "explicit", "present = 0 row (spec, Presence rule)")
    else:
        put("chunk_to_row", "convention",
            "kerchunk Parquet: C order, file floor(i / record_size), row i mod record_size")
        put("missing_chunks", "convention", "row with null path and null raw")

    dims = a["dims"]
    put("dims", "explicit" if dims else "missing", ",".join(dims or []))

    roles, worst = [], "explicit"
    for d in dims or []:
        c = arrays.get(d)
        role, st = axis_role(d, c["attrs"] if c else {})
        roles.append("%s=%s" % (d, role))
        if STATES.index(st) > STATES.index(worst):
            worst = st
    put("axis_roles", worst, " ".join(roles))

    # fill: the format's fill and the CF attributes must agree
    seen = []
    for label, v in (("fill", a["fill"]), ("_FillValue", at.get("_FillValue")),
                     ("missing_value", at.get("missing_value"))):
        x = num(v)
        if x is not None:
            seen.append((label, x))
    if not seen:
        put("fill", "missing")
    elif all(same(x, seen[0][1]) for _, x in seen):
        put("fill", "explicit", " ".join("%s=%g" % s for s in seen))
    else:
        note = " ".join("%s=%g" % s for s in seen)
        vr = at.get("valid_range")
        if isinstance(vr, list) and any(num(v) in (x for _, x in seen) for v in vr):
            note += " (one of them is a valid_range bound)"
        put("fill", "conflict", note)

    sf, ao = num(at.get("scale_factor")), num(at.get("add_offset"))
    if sf is None and ao is None:
        put("packing", "explicit", "unpacked")
    else:
        put("packing", "explicit", "scale_factor=%r add_offset=%r" % (sf, ao))

    put("codec", "explicit" if a["codec"] else "missing", json.dumps(a["codec"]))

    missing = [d for d in dims or [] if d not in arrays]
    put("coordinates", "missing" if missing else "explicit",
        ("no coordinate for " + ",".join(missing)) if missing else "")

    t = [d for d, r in zip(dims or [], roles) if r.endswith("=T")]
    if t:
        ta = arrays[t[0]]["attrs"] if t[0] in arrays else {}
        units, cal = ta.get("units"), ta.get("calendar")
        if units and cal:
            put("time", "explicit", "%s, %s" % (units, cal))
        elif units:
            put("time", "convention", "%s, no calendar (CF default: standard)" % units)
        else:
            put("time", "missing")

    prov = []
    if manifest:
        prov = [k for k in ("source_index", "files", "producer", "created") if k in manifest]
    put("provenance", "explicit" if {"producer", "created"} <= set(prov) else
        ("inferred" if prov else "missing"), ",".join(prov))

    # orientation and longitude range follow from regular coordinates
    for role, item in (("Y", "orientation"), ("X", "lon_convention")):
        d = [dd for dd, r in zip(dims or [], roles) if r.endswith("=" + role)]
        c = arrays.get(d[0]) if d else None
        if c and c.get("affine"):
            s, st, n = c["affine"]["start"], c["affine"]["step"], c["shape"][0]
            if role == "Y":
                put(item, "derived", "Y %s" % ("ascending" if st > 0 else "descending"))
            else:
                lo, hi = min(s, s + (n - 1) * st), max(s, s + (n - 1) * st)
                periodic = abs(abs(n * st) - 360.0) < 1e-6 * 360
                put(item, "derived", "%.6g to %.6g%s" % (lo, hi, ", periodic" if periodic else ""))
        elif c and c.get("values"):
            v = c["values"]
            put(item, "derived", "from inline values: %g .. %g" % (v[0], v[-1]))
        else:
            put(item, "inferred", "needs the coordinate values")

    z = [d for d, r in zip(dims or [], roles) if r.endswith("=Z")]
    if z:
        pos = arrays[z[0]]["attrs"].get("positive") if z[0] in arrays else None
        put("vertical", "explicit" if pos else "missing", pos or "")

    put("content_summary", "derived" if kind == "mdimrefs" else "missing",
        "computable from the table" if kind == "mdimrefs" else "")
    return rows


def oracle(path, arrays):
    """Compare data arrays with osgeo.gdal's multidim reading of one source."""
    from osgeo import gdal

    gdal.UseExceptions()
    ds = gdal.OpenEx(path, gdal.OF_MULTIDIM_RASTER)
    rg = ds.GetRootGroup()
    out = []
    for name, a in arrays.items():
        try:
            md = rg.OpenMDArrayFromFullname("/" + name.lstrip("/"))
        except RuntimeError:
            continue
        got = {
            "scale_factor": md.GetScale(),
            "add_offset": md.GetOffset(),
            "fill": md.GetNoDataValueAsDouble(),
            "units": md.GetUnit() or None,
        }
        want = {
            "scale_factor": num(a["attrs"].get("scale_factor")),
            "add_offset": num(a["attrs"].get("add_offset")),
            "fill": num(a["fill"]) if a["fill"] is not None else num(a["attrs"].get("_FillValue")),
            "units": a["attrs"].get("units"),
        }
        for k in got:
            g, w = got[k], want[k]
            if g is None and w is None:
                continue
            if k in ("scale_factor", "add_offset") and g is not None and w is None:
                if (k == "scale_factor" and g == 1) or (k == "add_offset" and g == 0):
                    continue
            ok = (g == w) if not isinstance(g, float) or w is None else same(g, float(w))
            out.append({"array": name, "item": k, "source": g, "store": w, "ok": ok})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("stores", nargs="+")
    p.add_argument("--oracle")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    bad = False
    packing = {}
    for loc in args.stores:
        kind, text = load(loc)
        doc, strict = parse(text)
        arrays = arrays_from_kerchunk(doc) if kind == "kerchunk" else arrays_from_mdimrefs(doc)
        manifest = None
        if kind == "mdimrefs":
            m = os.path.join(os.path.dirname(loc), "manifest.json")
            if "://" not in loc and os.path.exists(m):
                manifest = json.loads(fetch(m))
        data = [n for n, a in arrays.items()
                if a.get("kind") == "data" or (a.get("kind") is None and a["dims"]
                                               and len(a["dims"]) >= 2 and n not in a["dims"])]
        for name in sorted(data):
            rows = check_array(name, arrays[name], arrays, kind, strict, manifest)
            a = arrays[name]
            packing.setdefault(name, []).append(
                (loc, num(a["attrs"].get("scale_factor")), num(a["attrs"].get("add_offset")),
                 num(a["fill"]), num(a["attrs"].get("_FillValue"))))
            bad |= any(r["state"] == "conflict" for r in rows.values())
            if args.json:
                print(json.dumps({"store": loc, "kind": kind, "array": name, "items": rows}))
            else:
                print("\n%s  [%s]  %s" % (loc, kind, name))
                for item, r in rows.items():
                    print("  %-16s %-10s %s" % (item, r["state"], r["note"]))
        if args.oracle:
            for r in oracle(args.oracle, {n: arrays[n] for n in data}):
                bad |= not r["ok"]
                if args.json:
                    print(json.dumps(r))
                else:
                    print("  oracle %-6s %-12s %-6s source=%r store=%r" % (
                        r["array"], r["item"], "ok" if r["ok"] else "DIFFER", r["source"], r["store"]))

    for name, seen in packing.items():
        if len(seen) < 2:
            continue
        ref = seen[0]
        for s in seen[1:]:
            for i, label in ((1, "scale_factor"), (2, "add_offset"), (3, "fill"), (4, "_FillValue")):
                if ref[i] != s[i]:
                    bad = True
                    print("\nDIFFER %s %s: %r (%s) vs %r (%s)" % (name, label, ref[i], ref[0], s[i], s[0]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
