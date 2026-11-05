"""Prototype: a vector vrt:// connection string lowered to an OGR VRT document.

GDAL's vrt:// (raster) is a gdal_translate invocation written as a URI: each
query key is a gdal_translate flag. The same rule for vector data makes each
key an ogr2ogr flag. This script parses such a string, lowers it to the
OGRVRTDataSource XML that GDAL already reads, and (in check.py) compares
GDAL's reading of that XML with GDAL's own direct read using the same
filters. Nothing here needs GDAL; the check does.

Keys (ogr2ogr flag in brackets):
  layer=NAME          source layer                    [positional layer name]
  select=a,b          keep these fields               [-select]
  where=EXPR          attribute filter, OGR SQL       [-where]
  sql=STATEMENT       replace layer by an SQL result  [-sql]
  spat=x0,y0,x1,y1    spatial filter                  [-spat]
  a_srs=SRS           assign layer CRS                [-a_srs]
  t_srs=SRS           reproject                       [-t_srs]
  x=COL,y=COL         points from two columns         [-oo X_POSSIBLE_NAMES]
  name=NAME           output layer name               [-nln]
"""

from urllib.parse import parse_qsl
from xml.sax.saxutils import escape, quoteattr

VECTOR_KEYS = {"layer", "select", "where", "sql", "spat", "a_srs", "t_srs",
               "x", "y", "name"}


def parse(uri):
    """vrt://path?k=v&k=v -> (path, dict). Split at the LAST '?' so the
    source may itself be a vrt:// string with options of its own (GDAL
    splits at the first '?', so it cannot nest)."""
    if not uri.startswith("vrt://"):
        raise ValueError("not a vrt:// string")
    body = uri[len("vrt://"):]
    path, _, query = body.rpartition("?") if "?" in body else (body, "", "")
    opts = dict(parse_qsl(query, keep_blank_values=True))
    unknown = set(opts) - VECTOR_KEYS
    if unknown:
        raise ValueError("unknown vector keys: %s" % ", ".join(sorted(unknown)))
    if "sql" in opts and ({"select", "where"} & set(opts)):
        raise ValueError("sql is exclusive with select and where (as in ogr2ogr)")
    return path, opts


def lower(uri, src_layer_default=None):
    """Return OGR VRT XML equivalent to the vrt:// string."""
    path, o = parse(uri)
    if path.startswith("vrt://"):
        raise NotImplementedError("nested vrt:// lowers to a nested VRT; not in this prototype")
    layer = o.get("layer", src_layer_default)
    name = o.get("name", layer or "layer")
    inner = ["<SrcDataSource>%s</SrcDataSource>" % escape(path)]
    if "sql" in o:
        inner.append("<SrcSQL>%s</SrcSQL>" % escape(o["sql"]))
    elif "select" in o or "where" in o:
        # OGR VRT has no attribute-filter element: a filter is SQL.
        cols = o.get("select", "*")
        sql = 'SELECT %s FROM "%s"' % (cols, layer)
        if "where" in o:
            sql += " WHERE " + o["where"]
        inner.append("<SrcSQL>%s</SrcSQL>" % escape(sql))
    elif layer:
        inner.append("<SrcLayer>%s</SrcLayer>" % escape(layer))
    if "a_srs" in o:
        inner.append("<LayerSRS>%s</LayerSRS>" % escape(o["a_srs"]))
    if "x" in o or "y" in o:
        inner.append("<GeometryField encoding=\"PointFromColumns\" x=%s y=%s/>"
                     % (quoteattr(o["x"]), quoteattr(o["y"])))
    if "spat" in o:
        x0, y0, x1, y1 = [float(v) for v in o["spat"].split(",")]
        wkt = "POLYGON((%r %r,%r %r,%r %r,%r %r,%r %r))" % (
            x0, y0, x1, y0, x1, y1, x0, y1, x0, y0)
        inner.append("<SrcRegion>%s</SrcRegion>" % wkt)
    lyr = "<OGRVRTLayer name=%s>%s</OGRVRTLayer>" % (quoteattr(name), "".join(inner))
    if "t_srs" in o:
        lyr = ("<OGRVRTWarpedLayer>%s<TargetSRS>%s</TargetSRS></OGRVRTWarpedLayer>"
               % (lyr, escape(o["t_srs"])))
    return "<OGRVRTDataSource>%s</OGRVRTDataSource>" % lyr
