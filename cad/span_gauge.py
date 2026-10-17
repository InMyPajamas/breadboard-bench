"""Span gauge: which station spacing do the board's tabs actually sit at?

    python cad/span_gauge.py  ->  out/stl_coupon/span_gauge_{1..3}.stl
                                  out/stl_coupon/span_gauge_slot.stl

RE-CUT TWICE. The first version bracketed 68.58 to 72.39 from a photo estimate
of "about 71 = 28 hole pitches"; every strip was too wide. The second bracketed
66.04 off a calibrated photo; the user reported none fit and 2 dots was short.
The third is built on a CALIPER reading instead:

    STATION_SPAN  65.21   tip centre to tip centre, user's iGaging
    THREE cleats per edge, not two

Both photo passes agreed with each other to 0.01 mm and both were wrong by
about 0.9, because they shared the same scale assumption -- that the board is
exactly 165.1 mm long, a number taken from our own model rather than measured.
Agreement between measurements only tests what differs between them. Worse, the
result landed near a whole hole pitch and that coincidence was taken as
confirmation; 65.21 is 25.67 pitches, so the cleats are not on the grid at all.

Use the caliper. Photographs are for counting features and seeing shape; they
are not for a dimension that a 0.3 mm pocket depends on.

THE TOLERANCE PROBLEM, and why this file now prints two different things.

A pocket is TAB_W + FIT = 4.37 for a 4.07 tab, so 0.3 of total slack. For two
pockets to BOTH receive tabs the spacing has to be right to about +/-0.15 --
tighter than a photo can measure and tighter than the moulding is likely to
hold across a batch. Chasing that number is the wrong move.

    span_gauge_1..3   a tight bracket 0.5 mm apart, to confirm the caliper in
                      plastic: 64.71 / 65.21 / 65.71. Half a millimetre, not
                      half a hole pitch: the pocket only has 0.3 of slack, so
                      a coarser step cannot tell the right answer from a near
                      miss.
    span_gauge_slot   the production candidate: first pocket exact, second
                      pocket SLOTTED along the board. One pocket locates, the
                      other only stops rotation -- the classic round-hole /
                      slotted-hole pair -- so spacing error stops mattering.

The slot also MEASURES: its mouth carries witness ribs every 1.27 (half a hole
pitch), so where the second tab sits reads off directly.

Built with manifold3d so it can be made on the Mac.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

TAB_W, TAB_H, TAB_PROUD = 4.07, 5.20, 1.41
FIT = 0.3
PITCH = 2.54                         # the board's hole grid
# 65.21, the user's caliper across two adjacent cleats, tip centre to tip
# centre. NOT a whole hole pitch (25.67), which retires the earlier argument
# that the spacing must land on the 2.54 grid -- the cleats are moulded into
# the case and owe the grid nothing. The photo estimate that argument rested on
# read 66.13 and was 0.92 too high.
NOMINAL = 65.21
SPANS = (NOMINAL - 0.5, NOMINAL, NOMINAL + 0.5)   # 64.71 / 65.21 / 65.71
SLOT_REACH = 3.0                     # the slotted pocket accepts NOMINAL +/- this
PAD_L, WALL, FLOOR = 14.0, 5.0, 3.0
SPINE_W, SPINE_H = 3.0, 6.0

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")


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
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


def strip(span, slot=0.0, dimples=0):
    """Two pads on a thin spine. `slot` elongates the SECOND pocket along the
    board by that much either side of nominal; 0 gives the plain graded strip."""
    run = span + PAD_L + slot
    wall_h = FLOOR + TAB_H + 2.0
    body = Manifold.cube((run, SPINE_W, SPINE_H)).translate((0, WALL - SPINE_W, 0))
    for k in (0, 1):
        x0 = k * span
        pad = PAD_L + (slot * 2 if k else 0)
        body += Manifold.cube((pad, WALL, wall_h)).translate((x0 - (slot if k else 0), 0, 0))
        # the pocket the tab falls into, open at the top. The second one is
        # stretched by `slot` each way, so a spacing error is absorbed here
        # instead of jamming the first tab.
        pw = TAB_W + FIT + (slot * 2 if k else 0)
        body -= Manifold.cube((pw, TAB_PROUD + FIT, TAB_H + 4.0)).translate(
            (x0 + (PAD_L - TAB_W - FIT) / 2 - (slot if k else 0), WALL - TAB_PROUD - FIT, FLOOR))
    if slot:
        # Witness marks every half hole pitch, so where the tab lands reads off
        # the gauge instead of needing a caliper. These are NOTCHES CUT into the
        # pad's top face, not ribs added across the slot: the pocket cut has
        # already removed everything on the slot side, so an added rib there
        # floats free and the part ships as loose pieces. The export assert
        # catches exactly that, and did.
        for i in range(-2, 3):
            x = span + (PAD_L - TAB_W - FIT) / 2 + TAB_W / 2 + i * (PITCH / 2)
            deep = 1.2 if i == 0 else 0.6          # the centre mark is the nominal
            body -= Manifold.cube((0.6, WALL - TAB_PROUD - FIT, deep)).translate(
                (x - 0.3, 0, wall_h - deep))
    for k in range(dimples):
        body -= Manifold.cylinder(0.7, 0.85, 0.85, 24).translate((3.0 + k * 3.0, WALL / 2, wall_h - 0.6))
    return body


if __name__ == "__main__":
    for i, span in enumerate(SPANS):
        tm = export(strip(span, dimples=i + 1), f"span_gauge_{i + 1}")
        print(f"span_gauge_{i + 1}  {np.round(tm.extents, 2)}  {tm.volume / 1000:5.2f} cm3   "
              f"pocket centres {span:.2f} apart  ({span / PITCH:.1f} hole pitches)")
    tm = export(strip(NOMINAL, slot=SLOT_REACH), "span_gauge_slot")
    print(f"span_gauge_slot  {np.round(tm.extents, 2)}  {tm.volume / 1000:5.2f} cm3   "
          f"first pocket exact, second slotted {NOMINAL - SLOT_REACH:.2f} to {NOMINAL + SLOT_REACH:.2f}")
