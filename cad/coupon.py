"""Fit-test coupon -- print this BEFORE the bench.

The CAD model is exact. The printed part will not be. Roughly 40 minutes of
printing here tells you your machine's actual error, which you then feed back
into params.py, instead of finding out after an 8-hour base print that the
clips do not snap on.

What is on the plate and what each piece answers:

  1. Two 100.00 mm reference bars, one along X and one along Y.
     Measure both with calipers at mid-height (not at the first layer -- that
     is squished). The difference from 100.00 is your shrinkage plus flow
     error, and it scales: whatever percentage you see here, the 300 mm bench
     will be out by three times as much in mm. PLA is typically 0.3-0.5%,
     which on a 300 mm part is 0.9-1.5 mm.

  2. A 40 mm section of the DIN rail.
     Measure across the lips. Nominal is 35.00 and EN 60715 allows 35.0 -0.3/+0,
     so anything over 35.0 is out of spec on the side that stops clips closing.
     A 0.4 nozzle usually lands +0.1 to +0.2 per side.

  3. Five clips at fits of 0.15 / 0.20 / 0.25 / 0.30 / 0.35 mm.
     Identified by the number of nubs on the face. Snap each onto the rail
     section. You want the one that clicks on with firm thumb pressure and
     holds a shake -- not the one that slides on freely. Put that number into
     RAIL_FIT in params.py.

  4. A slot gauge: 3.0 / 3.2 / 3.4 / 3.6 / 3.8 mm slots.
     Push a real M3 screw through each. Holes and slots print undersize by
     0.1-0.3 mm, so the 3.4 the board plate uses may well come out at 3.1-3.2
     and bind. The narrowest one an M3 passes freely tells you the offset to
     apply.

  5. A pilot-hole gauge: 2.6 / 2.8 / 3.0 mm.
     For M3 self-tappers into the rail mounts.
"""

from __future__ import annotations

import os
import sys

from build123d import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401
from bench import (box, din_clip, din_rail, plinth_envelope,  # noqa: E402
                   rim_cutter, safe_chamfer, safe_fillet)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")

FITS = (0.15, 0.20, 0.25, 0.30, 0.35)
SLOTS = (3.0, 3.2, 3.4, 3.6, 3.8)
PILOTS = (2.6, 2.8, 3.0)


def reference_bars():
    """100.00 mm exactly, in both axes, 6 mm tall so you can measure clear of
    the squished first layer."""
    a = box(0, 100, 0, 12, 0, 6)      # measures X
    b = box(0, 12, 0, 100, 0, 6)      # measures Y
    return Pos(-50, 100, 0) * a + Pos(60, -10, 0) * b


def clip_coupons():
    """One tab per fit value, tagged with 1-5 nubs."""
    out = None
    for i, f in enumerate(FITS):
        # i+1 dimples so you can tell them apart once they are off the plate.
        # Dimples, not nubs: raised nubs would touch the bed first when the tab
        # prints face-down and leave the whole face floating 1 mm in mid-air.
        plate = box(-14, 14, -24, 24, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
        plate = fillet(plate.edges().filter_by(Axis.Z), 3.0)
        piece = plate + din_clip(width=22.0, fit=f)
        for n in range(i + 1):
            piece -= Pos(-9 + n * 4.5, 19, RAIL_TOP_Z + 2.2) * \
                Cylinder(1.6, 2.0, align=(Align.CENTER, Align.CENTER,
                                          Align.MIN))
        # Flip face-down. As modelled the plate floats 9 mm up on the jaws and
        # would not print at all. These tabs are testing fit, not jaw strength,
        # so the face-down layer direction does not matter here -- but the real
        # modules must still print on edge (see cad/check.py).
        piece = Rot(180, 0, 0) * piece
        piece = Pos(0, 0, -piece.bounding_box().min.Z) * piece
        placed = Pos((i - 2) * 34, -51, 0) * piece
        out = placed if out is None else out + placed
    return out


def gauges():
    """Slot and pilot-hole gauge blocks."""
    g = box(-40, 40, -11, 11, 0, 4)
    g = fillet(g.edges().filter_by(Axis.Z), 2.0)
    for i, w in enumerate(SLOTS):
        x = -32 + i * 16
        s = box(x - 6, x + 6, -w / 2, w / 2, -1, 5)
        g -= fillet(s.edges().filter_by(Axis.Z), w / 2 - 0.01)
    p = box(-24, 24, -9, 9, 0, 4)
    p = fillet(p.edges().filter_by(Axis.Z), 2.0)
    for i, d in enumerate(PILOTS):
        p -= Pos(-16 + i * 16, 0, -1) * Cylinder(
            d / 2, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return Pos(0, 31, 0) * g + Pos(0, 4, 0) * p


def finish_tile():
    """The whole appearance system in one 60 x 40 tile.

    The fit pieces above validate every functional dimension and none of the
    surfaces, and the surfaces are the ones with no tolerance to absorb error.
    Two are genuinely uncertain until printed: the 4 mm plinth flare is 20
    layers each stepping out 0.20 mm, right where over-extrusion turns a clean
    45-degree face blobby -- and it carries both the plinth read and the colour
    boundary. The 0.75 mm rim chamfer is under 4 layers, so it may render as a
    stair rather than a bevel, eight times over.

    Run the filament change at COLOUR_SWAP_Z on this tile and you get a physical
    preview of graphite-under-bone for fifteen minutes instead of betting an
    eight-hour base print on a taste call.
    """
    w, d = 60.0, 40.0
    t = box(0, w, 0, d, 0, FRONT_DECK_Z)
    t = safe_fillet(t, t.edges().filter_by(Axis.Z), OUTER_R)
    t = t & plinth_envelope(w, d)

    px0, px1, py0, py1 = 12.0, 48.0, 12.0, 32.0
    p = box(px0, px1, py0, py1, FLOOR, FRONT_DECK_Z + 1)
    p = safe_fillet(p, p.edges().filter_by(Axis.Z), POCKET_R)
    t -= p
    t -= rim_cutter(px0, px1, py0, py1, FRONT_DECK_Z, POCKET_R)

    lip = t.edges().filter_by(
        lambda e: abs(e.center().Z - FRONT_DECK_Z) < 0.3
        and e.center().Y < py0 - RIM - 0.5)
    return safe_chamfer(t, lip, EDGE)


def build():
    plate = reference_bars()
    plate += Pos(70, 100, 0) * finish_tile()
    plate += Pos(0, 78, 0) * din_rail(length=40.0)
    plate += clip_coupons()
    plate += gauges()
    return plate


if __name__ == "__main__":
    print("building fit-test coupon ...")
    part = build()
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    path = os.path.join(OUT, "stl", "fit_coupon.stl")
    export_stl(part, path, tolerance=0.02, angular_tolerance=0.1)
    bb = part.bounding_box()
    print(f"  volume {part.volume / 1000:.1f} cm3")
    print(f"  footprint {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm")
    print(f"  -> {path}")
