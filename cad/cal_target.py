"""Plate 02m: the camera calibration target -- a dot grid at mat level and two
raised dot rows at known heights, three flat parts that need no support.

    python cad/cal_target.py  ->  out/stl_coupon/cal_target.stl, cal_step5.stl, cal_step20.stl

What each part is for:
    cal_target  140 x 90 x 2 plate; calipered after printing (140 fits the 150 caliper),
                which sets the true hole pitch to +-0.02 and every scale after it.
                84 holes, 4 mm on a 10 mm pitch: dark dots on a bright plate (print it in a
                LIGHT colour, the mat shows through), sub-pixel centroids for scale, tilt
                and lens distortion in one photo of the top-down camera. One 6 mm marker
                hole off the lattice, so the grid's orientation is never ambiguous. Two
                0.6-deep recesses over windows, where the cups sit.
    cal_step5   open cups, 35 x 25, printed floor-down so the dotted face is the bed
    cal_step20  face and the walls rise open -- no roof, no bridge, no support. Flipped
                and dropped into the recesses they put three dots at 5 and at 20 mm above
                the plate: the same dots at two known heights give the camera height and
                the lens centre, and their faces give the side camera a height scale.
                Magnification against height is a line through a known point, so the two
                extremes fix it.

The first cut had hollow steps with bridged roofs. Studio called the roofs
floating cantilevers and asked for supports; the user did not want them.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon")

PLATE_L, PLATE_W, PLATE_T = 140.0, 90.0, 2.0
HOLE, PITCH = 4.0, 10.0
GRID_X = [10.0 + 10.0 * i for i in range(13)]            # 10 .. 130
GRID_Y = [10.0 + 10.0 * j for j in range(6)]             # 10 .. 60
EXTRA = [(x, 77.5) for x in (45.0, 55.0, 65.0, 75.0, 85.0, 95.0)]   # the strip between the cups
MARK = (135.0, 55.0, 6.0)                                # x, y, diameter: inside the body, off the lattice
CUP_L, CUP_W, WALL, FLOOR = 35.0, 25.0, 1.6, 2.4
RECESS, CLEAR, RIM = 0.6, 0.2, 2.7                       # recess depth, fit per side, rim the cup stands on
STEPS = {"cal_step5": (5.0, 62.0, 5.0), "cal_step20": (100.0, 62.0, 20.0)}   # x0, y0 of the recess, height above the plate
SEG = 64


def box(x0, x1, y0, y1, z0, z1):
    lo = np.minimum((x0, y0, z0), (x1, y1, z1)); hi = np.maximum((x0, y0, z0), (x1, y1, z1))
    return Manifold.cube(tuple(hi - lo)).translate(tuple(lo))


def hole(x, y, d, z0, z1):
    return Manifold.cylinder(z1 - z0, d / 2, d / 2, SEG).translate((x, y, z0))


def plate():
    t = box(0, PLATE_L, 0, PLATE_W, 0, PLATE_T)
    for x in GRID_X:
        for y in GRID_Y:
            t -= hole(x, y, HOLE, -1, PLATE_T + 1)
    for x, y in EXTRA:
        t -= hole(x, y, HOLE, -1, PLATE_T + 1)
    t -= hole(MARK[0], MARK[1], MARK[2], -1, PLATE_T + 1)
    for x0, y0, _ in STEPS.values():
        # the recess locates the cup; the window under it lets the cup's holes see the mat
        t -= box(x0 - CLEAR, x0 + CUP_L + CLEAR, y0 - CLEAR, y0 + CUP_W + CLEAR, PLATE_T - RECESS, PLATE_T + 1)
        t -= box(x0 + RIM, x0 + CUP_L - RIM, y0 + RIM, y0 + CUP_W - RIM, -1, PLATE_T + 1)
    return t


def cup(height):
    """Floor on the bed (the dotted face), walls rising open. Seated in its
    recess the floor's top sits `height` above the plate."""
    h = height - (PLATE_T - RECESS) + PLATE_T          # floor-to-rim: recess floor to the dot face
    c = box(0, CUP_L, 0, CUP_W, 0, h)
    c -= box(WALL, CUP_L - WALL, WALL, CUP_W - WALL, FLOOR, h + 1)
    for k in range(3):
        c -= hole(7.5 + 10.0 * k, CUP_W / 2, HOLE, -1, FLOOR + 1)
    return c


def export(m, name):
    assert m.status().name == "NoError", f"{name}: {m.status().name}"
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=True)
    assert tm.is_watertight, f"{name} is not a closed solid"
    bodies = len(tm.split(only_watertight=False))
    assert bodies == 1, f"{name} came out as {bodies} loose pieces, not one solid"
    tm.apply_translation(-tm.bounds[0])
    os.makedirs(DEST, exist_ok=True)
    tm.export(os.path.join(DEST, name + ".stl"))
    return tm


if __name__ == "__main__":
    total = 0.0
    for name, m in [("cal_target", plate())] + [(n, cup(h)) for n, (_, _, h) in STEPS.items()]:
        tm = export(m, name)
        lo, hi = tm.bounds; total += tm.volume
        print(f"{name:11s} {hi[0]-lo[0]:6.1f} x {hi[1]-lo[1]:5.1f} x {hi[2]-lo[2]:5.1f} mm, {tm.volume/1000:5.1f} cm3, one body")
    print(f"total {total/1000:.1f} cm3 solid; {len(GRID_X)*len(GRID_Y)+len(EXTRA)} plate dots, marker at {MARK[:2]}, "
          f"cup dot faces at {[PLATE_T + h for _, _, h in STEPS.values()]} above the mat once seated")
