"""Plate 02k: the recessed ledge as a gauge -- the first 120 mm of the proposed
deck, cut from the same construction the viewer's Ledge variant is staged
from, so the real board can be dropped on it before frame.py is touched.

    python cad/ledge_gauge.py  ->  out/stl_coupon/ledge_gauge.stl

Rail-local x 0..120: the left ledge stubs (0..5), the full board's datum
station (pocket 4.37 + peg 3.8 at 22.79), its second station's slot (10.37 at
88.00), and the deck plate at 52 joining the rails into one piece. Built on
the Mac with manifold3d from PLAN.md's numbers (the geometry is
cad/ledge_ladder.py's); it tests the DESIGN. frame.py's ladder_station_stub,
cut from the production code, later tests the code. Delete this and
ledge_ladder.py when that exists.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

import ledge_ladder as L

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")
RUN = 120.0


def export(m, name):
    assert m.status().name == "NoError", f"{name}: {m.status().name}"
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, f"{name} is not a closed solid"
    # Closure is not connectivity: two disjoint closed solids are each
    # watertight. cradle_gauge shipped as two loose rails behind that gap.
    bodies = len(tm.split(only_watertight=False))
    assert bodies == 1, f"{name} came out as {bodies} loose pieces, not one solid"
    tm.apply_translation(-tm.bounds[0])
    os.makedirs(DEST, exist_ok=True)
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


def gauge():
    lad = (L.deck_rail(+1).translate((0, L.FRONT_AXIS, 0))
           + L.deck_rail(-1).translate((0, L.REAR_AXIS, 0)))
    y0 = L.FRONT_AXIS + L.RAIL_R + L.LEDGE - 0.5
    y1 = L.REAR_AXIS - L.RAIL_R - L.LEDGE + 0.5
    fx = L.FOOT_X[0]
    lad += L.box(fx - L.DECK_PLATE_W / 2, fx + L.DECK_PLATE_W / 2, y0, y1, 0, L.RELIEF_Z)
    # the slice: from the ledge's end face (the 3 mm engage is trimmed) to RUN
    return lad ^ L.box(0, RUN, -1, L.REAR_AXIS + L.RAIL_R + 1, -1, L.RAIL_R + 1)


if __name__ == "__main__":
    st1, st2 = L.FULL_ST[0], L.FULL_ST[1]
    assert st2 + L.POCKET_W / 2 + L.SLOT_REACH[1] + L.BLOCK_L < RUN, "slot 2's blocks run off the gauge"
    tm = export(gauge(), "ledge_gauge")
    lo, hi = tm.bounds
    print(f"ledge_gauge  {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm, "
          f"{tm.volume / 1000:.1f} cm3 solid, one body")
    print(f"datum pocket + peg at {st1}, slot at {st2}, plate at {L.FOOT_X[0]}  (rail-local)")
    print(f"recess {L.RECESS}  shelf {L.RIM} wide at z {L.BOARD_Z}  relief z {L.RELIEF_Z}  land {L.LAND_Y:.2f}  face {L.FACE_Y:.2f}")
