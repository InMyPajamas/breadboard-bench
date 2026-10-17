"""Slot gauge: three rail sections that a breadboard's edge tab slides into.

    python cad/slot_gauge.py  ->  out/stl_coupon/slot_gauge_{1,2,3}.stl

The ladder's printed indexing teeth barely catch (plate 02d). The alternative
is to stop making a feature and start using one the board already has: the
male tab on its long edge slides into a slot down the rail, and the SLOT'S
ROOF is what stops the board lifting. That roof is a 5.2 mm feature, an order
of magnitude above this printer's error -- unlike the tab's own 0.11 mm per
side undercut, which is smaller than the pocket error measured today.

Measured off the user's board (no datasheet exists for these; see
ref/mb102/):

    tab height          5.20   bottom flush with the board's rigid underside
    tab width           3.85 at the base, 4.07 at the tip (a 3.0 deg undercut)
    tab stands proud    2.09
    tab spacing         about 71 = 28 hole pitches
    adhesive tape       0.6 thick, set back 0.6 from the edge

The tab's bottom is flush with the board's rigid underside, so the slot FLOOR
is what the board rests on -- there is no ledge here at all, and none is
needed: the tape is set back 0.6 INSIDE the board's edge, so it never reaches
the rail face. (The real deck_rail still needs that clearance, because its
ledge does run under the board.)

Three sections, tagged 1-3 dimples, differing only in slot height, since that
is what decides between "will not go in" and "lifts out":

    1 dot   5.4   0.2 clearance
    2 dots  5.6   0.4
    3 dots  5.8   0.6

Each is 60 mm long, enough to capture one tab wherever it falls. Built with
manifold3d so it can be made on the Mac.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

TAB_H, TAB_PROUD = 5.20, 2.09
HEIGHTS = (5.4, 5.6, 5.8)
DEPTH = TAB_PROUD + 0.4          # generous: height is the variable, not depth
RUN, WALL, LEDGE = 60.0, 4.0, 0.6
BASE = 3.0                       # plinth under the slot, so it stands up

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")


def export(m, name):
    assert m.status().name == "NoError", f"{name}: {m.status().name}"
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, f"{name} is not a closed solid"
    tm.apply_translation(-tm.bounds[0])
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


if __name__ == "__main__":
    for i, h in enumerate(HEIGHTS):
        total = BASE + h + 2.0                     # 2 mm of roof over the slot
        body = Manifold.cube((RUN, WALL + DEPTH, total))
        # the slot: open toward -y, running the full length so a board slides in
        body -= Manifold.cube((RUN + 2, DEPTH, h)).translate((-1, -0.01, BASE))
        for k in range(i + 1):
            body -= Manifold.cylinder(0.7, 0.85, 0.85, 24).translate(
                (RUN - 8.0 + (k - i / 2) * 2.8, WALL + DEPTH - 2.0, total - 0.6))
        tm = export(body, f"slot_gauge_{i + 1}")
        print(f"slot_gauge_{i + 1}  {np.round(tm.extents, 2)}  {tm.volume / 1000:5.2f} cm3   "
              f"slot {h:.1f} tall = {h - TAB_H:.1f} clearance")
