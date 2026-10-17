"""Cradle gauge: drop a board in by its own tab and notch.

    python cad/cradle_gauge.py  ->  out/stl_coupon/cradle_gauge_{1,2,3}.stl

The design the user arrived at, after a slot was ruled out because a roof that
stops a tab lifting also stops it entering from above: the board DROPS IN, one
rail carrying an open-topped POCKET that its male tab falls into, the other a
small PEG that falls into the matching female notch on the opposite edge. Tabs
and notches sit at the same stations, so both engage together.

Everything here is measured off the user's board -- no datasheet exists for
these (see ref/mb102/):

    board plain width   54.74
    tab                 5.20 tall, 4.07 at the tip, 1.41 proud (56.15 across
                        the tips minus the 54.74 plain width), bottom flush
                        with the board's rigid underside
    notch               1.60 deep, so a tab bottoms out with 0.19 to spare and
                        two boards gang up tight
    tape                0.6 thick, set back 0.6 inside the edge

Neither feature holds the board DOWN; both locate it, and gravity does the
rest. That is the thing this gauge is really asking about.

One station each, three gaps between the rail faces, since that is what
decides between "will not drop in" and "rattles":

    1 dot   54.94   0.2 clearance on the plain width
    2 dots  55.14   0.4
    3 dots  55.34   0.6

Built with manifold3d so it can be made on the Mac.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

BOARD_W = 54.74
TAB_W, TAB_H, TAB_PROUD = 4.07, 5.20, 1.41
NOTCH_D = 1.6
PEG_D = 1.3                 # 0.3 clear of the notch floor: the peg only has to
                            # locate the board, never to fill the notch
GAPS = (54.94, 55.14, 55.34)
RUN = 24.0                  # along the board: one station, with margin
WALL, FLOOR = 5.0, 3.0
RIM = 0.6                   # the board's bare rim; the tape starts inboard of it
RELIEF = 1.2                # how deep the tape recess is cut into the floor. It
                            # must be LESS than FLOOR: cutting the full floor
                            # depth severs the two rails and the gauge becomes
                            # two loose pieces that cannot hold the gap they
                            # exist to measure. 1.2 clears the 0.6 tape twice over.
FIT = 0.3                   # clearance on the pocket and around the peg

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")


def export(m, name):
    assert m.status().name == "NoError", f"{name}: {m.status().name}"
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, f"{name} is not a closed solid"
    # is_watertight is NOT enough: two disjoint closed solids are each
    # watertight, so a cut that severs the part passes it silently. This gauge
    # is only a gauge while its two rails are one piece.
    bodies = len(tm.split(only_watertight=False))
    assert bodies == 1, f"{name} came out as {bodies} loose pieces, not one solid"
    tm.apply_translation(-tm.bounds[0])
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


if __name__ == "__main__":
    for i, gap in enumerate(GAPS):
        total_y = gap + 2 * WALL
        wall_h = FLOOR + TAB_H + 2.0
        body = Manifold.cube((RUN, total_y, FLOOR))                      # the floor tying the rails together
        for sgn, y in ((-1, WALL / 2), (+1, total_y - WALL / 2)):
            body += Manifold.cube((RUN, WALL, wall_h)).translate((0, y - WALL / 2, 0))
        # the board's bare rim lands on a narrow shelf; the rest is relieved so
        # it never rests on its adhesive tape. RELIEF deep, not FLOOR deep, so
        # what is left under the recess still ties the two rails together.
        body -= Manifold.cube((RUN + 2, gap - 2 * RIM, RELIEF)).translate(
            (-1, WALL + RIM, FLOOR - RELIEF))

        # POCKET side: open at the top, the tab falls in
        body -= Manifold.cube((TAB_W + FIT, TAB_PROUD + FIT, TAB_H + 4.0)).translate(
            ((RUN - TAB_W - FIT) / 2, WALL - TAB_PROUD - FIT, FLOOR))
        # PEG side: stands proud into the board's notch, same station
        body += Manifold.cube((TAB_W - FIT, PEG_D, TAB_H - FIT)).translate(
            ((RUN - TAB_W + FIT) / 2, WALL + gap - PEG_D, FLOOR))
        for k in range(i + 1):
            body -= Manifold.cylinder(0.7, 0.85, 0.85, 24).translate(
                (4.0 + k * 3.0, WALL / 2, wall_h - 0.6))
        tm = export(body, f"cradle_gauge_{i + 1}")
        print(f"cradle_gauge_{i + 1}  {np.round(tm.extents, 2)}  {tm.volume / 1000:5.2f} cm3   "
              f"gap {gap:.2f} = {gap - BOARD_W:.1f} clearance")
