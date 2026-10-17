"""Tooth gauge: three tooth profiles side by side, each with its own rider.

    python cad/tooth_gauge.py   ->  out/stl_coupon/tooth_gauge.stl
                                    out/stl_coupon/tooth_rider_{1,2,3}.stl

Plate 02d showed the ladder's indexing teeth barely catch and barely stand up.
A triangular tooth cannot print its tip -- width at height h is
P * (H - h) / H, so the top layer falls under one 0.42 extrusion line -- and
what survives is a feather edge that folds instead of gripping.

This grades the fix. Same 2.0 mm pitch and 0.9 mm depth throughout; only the
flat on top of each tooth changes:

    1 dot   0.0   the profile as drawn today, the control
    2 dots  0.6   1.4 extrusion lines across the tip
    3 dots  0.9   2.1 lines, blunter still

Each strip is a recessed trench with the tooth tips flush at the top face,
exactly as frame.deck_rail() builds it, and each rider is the negative of its
own strip lifted by the same 0.1 mm clearance frame.py uses. Riders are tagged
with matching dimples. Built with manifold3d so it can be made on the Mac.
"""
import os

import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold

TOOTH_P, TOOTH_H = 2.0, 0.9          # frame.py
CLEAR = 0.1                          # frame.py lifts the rider's cutter by this
TOPS = (0.0, 0.6, 0.9)
STRIP_W, RUN = 6.0, 40.0             # each strip: width across, length along
BASE_H, GAP = 4.0, 8.0
RIDER_W, RIDER_H, RIDER_L = 5.0, 5.0, 24.0

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")


def tooth_profile(top, extra=0.0):
    """The zigzag as a closed polygon in x (along) and z (up), tips at z = 0,
    valleys at -TOOTH_H. `extra` lowers the whole profile, which is how the
    rider gets its clearance."""
    pts = [(-1.0, -TOOTH_H - 1.0)]
    x = -1.0
    while x < RUN + 1.0:
        pts.append((x, -TOOTH_H - extra))
        if top > 1e-9:                       # trapezoid: two apex points
            pts += [(x + (TOOTH_P - top) / 2, -extra), (x + (TOOTH_P + top) / 2, -extra)]
        else:                                # triangle: ONE apex -- a repeated
            pts.append((x + TOOTH_P / 2, -extra))   # point is a zero-length edge
        x += TOOTH_P
    pts += [(x, -TOOTH_H - extra), (x, -TOOTH_H - 1.0)]
    # Manifold wants an outer boundary wound counter-clockwise; walking the
    # teeth left to right along the top traces it clockwise, so hand it back.
    return CrossSection([pts[::-1]])


def strip(top, extra=0.0, width=STRIP_W):
    """The zigzag swept across y."""
    return Manifold.extrude(tooth_profile(top, extra), width).rotate((90, 0, 0)).translate((0, width, 0))


def dimples(solid, n, x, y, z):
    for k in range(n):
        solid -= Manifold.cylinder(0.6, 0.85, 0.85, 24).translate((x + (k - (n - 1) / 2) * 2.8, y, z - 0.35))
    return solid


def export(m, name):
    assert m.status().name == "NoError", f"{name}: {m.status().name}"
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, f"{name} is not a closed solid"
    tm.apply_translation(-tm.bounds[0])
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


if __name__ == "__main__":
    width = STRIP_W * len(TOPS) + GAP * (len(TOPS) - 1) + 12.0
    bar = Manifold.cube((RUN, width, BASE_H)).translate((0, 0, -BASE_H))
    for i, top in enumerate(TOPS):
        y = 6.0 + i * (STRIP_W + GAP)
        # trench exactly TOOTH_H deep: an over-cut leaves a sliver the
        # boolean cannot close, and the mesh comes out non-manifold
        bar -= Manifold.cube((RUN + 2, STRIP_W, TOOTH_H)).translate((-1, y, -TOOTH_H))
        bar += strip(top).translate((0, y, 0))
        # tags in the flat land beside each strip, never in the teeth
        bar = dimples(bar, i + 1, RUN - 6.0, y - 3.0, 0.0)
    tm = export(bar, "tooth_gauge")
    print(f"tooth_gauge  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3")

    for i, top in enumerate(TOPS):
        r = Manifold.cube((RIDER_L, RIDER_W, RIDER_H))
        # the rider's own valleys: the same profile, lowered by the clearance
        r -= strip(top, extra=CLEAR, width=RIDER_W + 2).translate((0, -1, 0))
        r = dimples(r, i + 1, RIDER_L / 2, RIDER_W / 2, RIDER_H)
        tm = export(r, f"tooth_rider_{i + 1}")
        print(f"tooth_rider_{i + 1}  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3   flat top {top:.1f}")
