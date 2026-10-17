"""Seated-user geometry checks.

Answers three things numerically rather than by eye:
  - how far off-normal you view a rail-mounted display from a normal seat
  - whether any rail module overhangs the bins below it
  - whether the back panel gets between you and the breadboard
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401

# A seated adult at a 740 mm desk: eyes roughly 460 mm above the desk surface,
# and the bench front edge about 350 mm away.
EYE_Z = 460.0
EYE_Y = -350.0


def deg(r):
    return math.degrees(r)


def module_front(stand_off):
    """(Y, Z) of the outermost point of a module standing `stand_off` mm proud
    of the panel face at the rail line."""
    return panel_point(RAIL_S, stand_off)


def main():
    print("seated-user geometry (eye 460 mm above desk, 350 mm in front)\n")

    # ---- display viewing angle ------------------------------------------
    ry, rz = panel_point(RAIL_S)
    los = math.atan2(EYE_Z - rz, ry - EYE_Y)          # sightline, above horiz
    normal = math.radians(PANEL_TILT)                  # panel normal elevation
    off = deg(los) - deg(normal)
    print(f"  rail centreline at Y={ry:.0f} Z={rz:.0f} mm above desk")
    print(f"  sightline to display  {deg(los):5.1f} deg below horizontal")
    print(f"  panel face normal     {deg(normal):5.1f} deg above horizontal")
    print(f"  -> viewed {off:.1f} deg off-normal")
    ideal = deg(los)
    print(f"  panel tilt that would put the display square to your eye: "
          f"{ideal:.0f} deg (currently {PANEL_TILT:.0f})")

    # ---- do modules overhang the bins? ----------------------------------
    print("\n  module reach vs the bins (bins occupy Y "
          f"{BIN_Y0:.0f}..{BIN_Y1:.0f}):")
    modules = {
        "screen_bezel": 9.0 + 3.0,
        "board_plate": 3.0 + 3.0,
        "breadboard_carrier": 3.0 + 3.0,
        "rail_bin": 15.0,
    }
    for name, out in sorted(modules.items(), key=lambda kv: -kv[1]):
        my, mz = module_front(out)
        # lowest point of the module, roughly one module half-height down-slope
        clash = my < BIN_Y1
        note = ("OVERHANGS the bins by "
                f"{BIN_Y1 - my:.0f} mm" if clash else "clear of the bins")
        print(f"    {name:20s} stands {out:4.1f} mm proud -> "
              f"front edge Y={my:5.1f}  {note}")

    # ---- reach to the breadboard ----------------------------------------
    bb_back = BB_WELL_Y + BB_WELL_D
    print(f"\n  breadboard rear row at Y={bb_back:.0f}; mid-tier wall rises at "
          f"Y={MID_Y0:.0f} to Z={MID_DECK_Z:.0f}")
    print(f"    {MID_Y0 - bb_back:.1f} mm of clearance behind the board, "
          f"wall only {MID_DECK_Z:.0f} mm tall -- hand clears it")
    print(f"  panel front face starts at Y={PANEL_Y0:.0f}, "
          f"{PANEL_Y0 - bb_back:.0f} mm behind the breadboard")


if __name__ == "__main__":
    main()
