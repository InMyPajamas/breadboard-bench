"""Pilot block for an O-ring rail gasket: two stations, two gland depths.

    python cad/pilot_block_oring.py   ->  out/stl_coupon/pilot_block_oring.stl

The rail joint was drawn around a printed TPU gasket (frame.rail_pad): 1.35
thick in a 1.0-deep gland, 0.35 of squeeze. Two things argue for an O-ring
instead. The TPU on hand is Bambu's "TPU for AMS", about 68D -- far too hard
to squash 0.35 mm with M3 self-tappers in printed pilots. And a 3 x 1 mm
O-ring (ID 3, section 1) is a drop-in for the gland's footprint: it rings
the M3 shank and its 5.0 OD is the gland's 5.0 width.

What it is not a drop-in for is the DEPTH: a 1.0 section in a 1.0 gland is a
spacer, not a spring. An O-ring wants its groove at 70-80% of its section, so
this block offers both ends of that: station 1 (one dimple) at 0.80 deep, 20%
squeeze; station 2 (two dimples) at 0.70, 30%. Everything else is the
production gland and pilots (coupon_frame.pilot_block): 24.3 x 5.0, two r1.25
pilots 16 apart and 11 deep, printed on its side like the frame so the pilots
load across the layers exactly as the real ones do.

The winner becomes RAIL_PAD_D in frame.py. Built with manifold3d so it can be
made on the Mac, where the CAD kernel is not installed.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

BLOCK_X, BLOCK_Z = 12.0, 14.0                # coupon_frame.pilot_block
PITCH, PILOT_R, PILOT_DEPTH = 16.0, 1.25, 11.0
GLAND_L, GLAND_W = 24.3, 5.0                 # RAIL_PAD_S + 0.3, by 5.0
AXIS_Z = 7.0
DEPTHS = (0.80, 0.70)
STATION = 32.0                               # centre-to-centre of the two stations

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon", "pilot_block_oring.stl")


def build():
    width = STATION * len(DEPTHS)
    g = Manifold.cube((BLOCK_X, width, BLOCK_Z)).translate((0, -width / 2, 0))
    for i, depth in enumerate(DEPTHS):
        yc = (i - (len(DEPTHS) - 1) / 2) * STATION
        g -= Manifold.cube((depth + 0.1, GLAND_L, GLAND_W)).translate(
            (-0.1, yc - GLAND_L / 2, AXIS_Z - GLAND_W / 2))
        for dy in (-PITCH / 2, PITCH / 2):
            bore = Manifold.cylinder(PILOT_DEPTH + 1.0, PILOT_R, PILOT_R, 48)
            g -= bore.rotate((0, 90, 0)).translate((-1.0, yc + dy, AXIS_Z))
        for k in range(i + 1):               # which station: dimples on the top face
            g -= Manifold.cylinder(0.5, 0.9, 0.9, 24).translate(
                (BLOCK_X / 2, yc + (k - i / 2) * 2.6, BLOCK_Z - 0.4))
    return g


if __name__ == "__main__":
    m = build().to_mesh()
    tm = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)
    assert tm.is_watertight, "block is not a closed solid"
    tm.export(DEST)
    print(f"{os.path.normpath(DEST)}  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3")
    xs = np.linspace(0.02, 11.98, 1197)
    for i, depth in enumerate(DEPTHS):
        yc = (i - (len(DEPTHS) - 1) / 2) * STATION
        gl = xs[~tm.contains(np.c_[xs, np.full_like(xs, yc), np.full_like(xs, AXIS_Z)])]
        pi = xs[~tm.contains(np.c_[xs, np.full_like(xs, yc + PITCH / 2), np.full_like(xs, AXIS_Z)])]
        print(f"  station {i + 1}: gland {gl.max():.2f} deep (nominal {depth:.2f}), pilot to x = {pi.max():.2f}")
