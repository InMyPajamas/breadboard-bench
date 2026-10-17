"""Move an MP4's moov atom to the front (qt-faststart), in pure Python.

Blender writes the moov index at the END of the file. That plays fine off
disk, but streamed over a server without Range support (python -m
http.server, most artifact hosts) the browser can never reach the index and
buffers forever. Run this on every --anim output:

    python cad/faststart.py renders/turntable_frame.mp4 [more.mp4 ...]

In-place, atomic (writes .tmp then replaces), and idempotent -- a file whose
moov already leads is left untouched. Chunk-offset tables (stco/co64) inside
moov are patched by the size of the moved atom, which is the whole trick.
"""

import os
import struct
import sys


def atoms(buf, start, end):
    """Yield (offset, size, type) for top-level boxes in buf[start:end]."""
    o = start
    while o + 8 <= end:
        size, kind = struct.unpack(">I4s", buf[o:o + 8])
        if size == 1:                      # 64-bit largesize
            size = struct.unpack(">Q", buf[o + 8:o + 16])[0]
        elif size == 0:                    # box runs to EOF
            size = end - o
        if size < 8:
            raise ValueError(f"bad atom size {size} at {o}")
        yield o, size, kind
        o += size


def patch_offsets(moov, delta):
    """Return moov bytes with every stco/co64 entry shifted by delta.

    Scan rather than parse the box tree: stco/co64 headers are unambiguous
    (fourcc + version/flags + entry count that must fit inside the box), and
    a scan cannot be defeated by an unknown container box the tree-walk
    would refuse to descend into.
    """
    out = bytearray(moov)
    for fourcc, fmt, width in ((b"stco", ">I", 4), (b"co64", ">Q", 8)):
        pos = 0
        while True:
            pos = out.find(fourcc, pos)
            if pos < 0:
                break
            body = pos + 4
            count = struct.unpack(">I", out[body + 4:body + 8])[0]
            box_size = struct.unpack(">I", out[pos - 4:pos])[0]
            if box_size == 16 + count * width:   # genuine table, not noise
                for i in range(count):
                    at = body + 8 + i * width
                    v = struct.unpack(fmt, out[at:at + width])[0]
                    out[at:at + width] = struct.pack(fmt, v + delta)
            pos += 4
    return bytes(out)


def faststart(path):
    with open(path, "rb") as f:
        buf = f.read()
    boxes = list(atoms(buf, 0, len(buf)))
    kinds = [k for _, _, k in boxes]
    if b"moov" not in kinds or b"mdat" not in kinds:
        return f"{path}: not a usable mp4 ({kinds})"
    if kinds.index(b"moov") < kinds.index(b"mdat"):
        return f"{path}: already faststart"

    moov_o, moov_s = next((o, s) for o, s, k in boxes if k == b"moov")
    moov = patch_offsets(buf[moov_o:moov_o + moov_s], moov_s)

    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        for o, s, k in boxes:
            if k == b"ftyp":
                f.write(buf[o:o + s])
                f.write(moov)
            elif k != b"moov":
                f.write(buf[o:o + s])
    os.replace(tmp, path)
    return f"{path}: moov ({moov_s / 1024:.0f} KB) moved to front"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python cad/faststart.py file.mp4 [...]")
    for p in sys.argv[1:]:
        print(" ", faststart(p))
