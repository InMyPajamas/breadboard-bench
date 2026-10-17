"""Peg gauge: how wide can a peg be and still drop into the board's notch?

    python cad/peg_gauge.py  ->  out/stl_coupon/peg_gauge.stl

The pocket side of the cradle is easy: the tab falls into an open hole and the
hole can be as generous as we like. The NOTCH side is the one with an
assumption in it. If the notch mirrors the tab -- and the tab is 3.85 at its
base widening to 4.07 at the tip -- then the notch is NARROWER AT ITS MOUTH
(3.85) and wider at the floor. A peg coming down from above has to pass the
mouth, not the floor, so it cannot simply be sized off the 4.07.

Five pegs on one bar, 3.2 to 4.0 in 0.2 steps, tagged 1-5 dimples. Lower a
board's notch edge onto each: the widest one that drops in cleanly is the
peg width, and it also tells us where the notch's mouth really is.

Depth is fixed at 1.3 on all five -- the notch is 1.60 deep and the peg only
has to locate the board, never to fill it. Height is fixed at 4.9 against a
5.20 notch.

Built with manifold3d so it can be made on the Mac.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

WIDTHS = (3.2, 3.4, 3.6, 3.8, 4.0)
PEG_D, PEG_H = 1.3, 4.9
PITCH, BAR_W, BAR_T = 26.0, 12.0, 4.0
MARGIN = 10.0

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")

if __name__ == "__main__":
    run = PITCH * (len(WIDTHS) - 1) + 2 * MARGIN
    bar = Manifold.cube((run, BAR_W, BAR_T))
    for i, w in enumerate(WIDTHS):
        x = MARGIN + i * PITCH
        # the peg stands on the bar's edge, so a board's notch can come
        # straight down onto it with the board overhanging clear of the bar
        bar += Manifold.cube((w, PEG_D, PEG_H)).translate((x - w / 2, BAR_W - PEG_D, BAR_T))
        for k in range(i + 1):
            bar -= Manifold.cylinder(0.7, 0.85, 0.85, 24).translate(
                (x + (k - i / 2) * 2.6, 3.0, BAR_T - 0.6))
    mesh = bar.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, "peg_gauge is not a closed solid"
    tm.apply_translation(-tm.bounds[0])
    tm.export(os.path.join(DEST, "peg_gauge.stl"))
    print(f"peg_gauge  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3   "
          f"pegs {', '.join(f'{w:.1f}' for w in WIDTHS)} wide x {PEG_D} deep x {PEG_H} tall")
