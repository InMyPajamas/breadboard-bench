"""Foot gauge v2: five pockets of graded size for ONE pad, the production one.

    python cad/foot_gauge_v2.py      ->  out/stl_coupon/foot_gauge_v2.stl

Why a second gauge. v1 (coupon_frame.py) cut three identical 16.00 x 6.00
pockets and graded the PADS, 006 / 012 / 018. Plate 01 showed the TPU pads
print dead on nominal; plate 02 showed no pad of the trio will enter a PLA
pocket, even with the mouth scraped to a chamfer. So the pads are not the
variable -- the pocket is: a small internal feature in PLA closes up, and by
more than the whole range the trio spanned. This gauge grades the pocket and
is tested with a production pad (foot_pad.stl, 16.24 x 6.24), six of which
already exist.

Pocket n is FOOT_L + over, FOOT_W + over, over = 0.10 * n, tagged with n
dimples on the top face. The winner sets how much frame.foot_pocket() must
grow; FOOT_FIT and the pads already printed stay as they are.

Built with manifold3d, not build123d, because it has to be buildable on the
Mac where the CAD kernel is not installed. Dimensions mirror frame.py and
coupon_frame.py; if FOOT_L / FOOT_W / FOOT_D change there, change them here.
"""
import os

import numpy as np
import trimesh
from manifold3d import CrossSection, JoinType, Manifold

FOOT_L, FOOT_W, FOOT_D = 16.0, 6.0, 3.2      # frame.py: the pocket
POCKET_R = 1.5                               # frame.py: foot_pocket's corner fillet
GAUGE_W, GAUGE_H = 14.0, 5.2                 # coupon_frame.py: the v1 gauge strip
PITCH, FIRST = 24.0, 16.0                    # v1 pocket spacing
OVERS = (0.10, 0.20, 0.30, 0.40, 0.50)       # total growth on length AND width
MOUTH = 0.3                                  # lead-in chamfer at the bed face

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "..", "out", "stl_coupon", "foot_gauge_v2.stl")


def rounded(length, width, r):
    core = CrossSection.square((length - 2 * r, width - 2 * r), center=True)
    return core.offset(r, JoinType.Round, 2.0, 48)


def pocket(over):
    """The pocket void: a filleted prism up from below the bed face, plus a
    short flared mouth so the pad starts square and first-layer squish has
    somewhere to go."""
    L, W = FOOT_L + over, FOOT_W + over
    body = Manifold.extrude(rounded(L, W, POCKET_R), FOOT_D + 1.0).translate((0, 0, -1.0))
    flare = Manifold.extrude(rounded(L + 2 * MOUTH, W + 2 * MOUTH, POCKET_R + MOUTH), MOUTH,
                             0, 0.0, (L / (L + 2 * MOUTH), W / (W + 2 * MOUTH)))
    return body + flare


def build():
    length = FIRST + PITCH * (len(OVERS) - 1) + FIRST
    g = Manifold.cube((length, GAUGE_W, GAUGE_H))
    for i, over in enumerate(OVERS):
        x = FIRST + PITCH * i
        g -= pocket(over).translate((x, GAUGE_W / 2, 0))
        # n dimples in the top face, over the strip's front margin: which
        # pocket this is, readable with the gauge either way up.
        for k in range(i + 1):
            dot = Manifold.cylinder(0.5, 0.9, 0.9, 24).translate(
                (x + (k - i / 2) * 2.6, 2.0, GAUGE_H - 0.4))
            g -= dot
    return g


if __name__ == "__main__":
    m = build().to_mesh()
    tm = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)
    assert tm.is_watertight, "gauge is not a closed solid"
    tm.export(DEST)
    print(f"{os.path.normpath(DEST)}  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3")
    for i, over in enumerate(OVERS):
        x, z = FIRST + PITCH * i, 1.6
        ys = np.linspace(0, GAUGE_W, 1401)
        free_w = ys[~tm.contains(np.c_[np.full_like(ys, x), ys, np.full_like(ys, z)])]
        xs = np.linspace(x - 10, x + 10, 2001)
        free_l = xs[~tm.contains(np.c_[xs, np.full_like(xs, GAUGE_W / 2), np.full_like(xs, z)])]
        print(f"  pocket {i + 1}: {free_l.max() - free_l.min():.2f} x {free_w.max() - free_w.min():.2f}"
              f"   (nominal {FOOT_L + over:.2f} x {FOOT_W + over:.2f})")
