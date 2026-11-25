"""Minimal COG reader: IFDs (base + overviews), tile offsets and sizes, and
tile decode for ZSTD + horizontal predictor int16. Standard library plus
numpy and zstandard; one range GET for the header, one per tile."""
import struct
import urllib.request

import numpy as np
import zstandard

HEAD = 1 << 17


def get(url, start, size):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + size - 1}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise


class Cog:
    def __init__(self, url):
        self.url = url
        self.buf = get(url, 0, HEAD)
        b = self.buf
        self.e = "<" if b[:2] == b"II" else ">"
        magic = struct.unpack(self.e + "H", b[2:4])[0]
        self.big = magic == 43
        off = struct.unpack(self.e + "Q", b[8:16])[0] if self.big else struct.unpack(self.e + "I", b[4:8])[0]
        self.ifds = []
        while off:
            ifd, off = self._ifd(off)
            if ifd.get(254, 0) & 4:  # mask
                continue
            self.ifds.append(ifd)

    def _bytes(self, start, size):
        if start + size <= len(self.buf):
            return self.buf[start:start + size]
        return get(self.url, start, size)

    def _ifd(self, off):
        e, big = self.e, self.big
        n = struct.unpack(e + ("Q" if big else "H"), self._bytes(off, 8 if big else 2))[0]
        ent = 20 if big else 12
        base = off + (8 if big else 2)
        raw = self._bytes(base, n * ent + (8 if big else 4))
        sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 11: 4, 12: 8, 16: 8, 17: 1, 18: 8}
        fmts = {1: "B", 3: "H", 4: "I", 16: "Q", 12: "d", 11: "f", 2: "c", 7: "B"}
        out = {}
        for i in range(n):
            r = raw[i * ent:(i + 1) * ent]
            tag, typ = struct.unpack(e + "HH", r[:4])
            cnt = struct.unpack(e + ("Q" if big else "I"), r[4:12] if big else r[4:8])[0]
            valraw = r[12:20] if big else r[8:12]
            nbytes = sizes.get(typ, 1) * cnt
            if nbytes > len(valraw):
                voff = struct.unpack(e + ("Q" if big else "I"), valraw)[0]
                data = self._bytes(voff, nbytes)
            else:
                data = valraw[:nbytes]
            f = fmts.get(typ)
            if f and typ != 2:
                vals = struct.unpack(e + f * cnt, data)
                out[tag] = vals[0] if cnt == 1 else list(vals)
            else:
                out[tag] = data
        nxt = struct.unpack(e + ("Q" if big else "I"), raw[n * ent:])[0]
        return out, nxt

    def level(self, k):
        d = self.ifds[k]
        return dict(width=d[256], height=d[257], tw=d[322], th=d[323],
                    offsets=np.atleast_1d(d[324]), sizes=np.atleast_1d(d[325]),
                    predictor=d.get(317, 1), compression=d[259])

    def tile(self, k, col, row):
        lv = self.level(k)
        ncol = -(-lv["width"] // lv["tw"])
        i = row * ncol + col
        off, size = int(lv["offsets"][i]), int(lv["sizes"][i])
        if size == 0:
            return None, 0
        raw = zstandard.ZstdDecompressor().decompress(get(self.url, off, size), max_output_size=lv["tw"] * lv["th"] * 2)
        a = np.frombuffer(raw, dtype="<i2").reshape(lv["th"], lv["tw"])
        if lv["predictor"] == 2:
            a = np.cumsum(a, axis=1, dtype=np.int16)
        return a, size
