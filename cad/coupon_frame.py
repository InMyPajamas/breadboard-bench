"""Frame-era fit coupon:  python cad/coupon_frame.py

Gauges the joints the frame actually has, in the orientations they actually
print. Reworked after the pilot-build DFM review and coupon-coverage audit:
every fit in the build is now read by SOME printed gauge, each gauge prints
in the SAME regime as the production feature it stands in for, and the
75%-slab base plate is gone (BASE_T 4.0 -> 2.0 web).

  fit_coupon_frame (PLA, flat, brim)
    - three MORTISE blocks at RAIL_FIT_MORTISE 0.15 / 0.25 / 0.35, each a
      vertical copy of the end frame's rail mortise WITH its detent (now
      DETENT_BITE) -- drop the rail stub in; the right fit slides home by
      thumb without ploughing.  Feeds RAIL_FIT_MORTISE (frame.py).
    - three R8 SOCKETS at radial clearance 0.1 / 0.2 / 0.3 plus one R6
      tie socket at 0.2 -- the deck-ladder / tie joints.
  rail_stub      (PLA) 40 mm real rail section with the END station's
                 bore pair 6 mm from one end (mounts=[-14]) and its csk
                 cones: csk flushness + tip protrusion, and the clip target.
  spigot_stub    (PLA) 24 mm R8 bar WITH its teardrop end pilots.
  tie_stub       (PLA) 30 mm R6 bar with pilots: the thinnest pilot crown
                 in the build (1.08 mm) -- drive an M3x12 by hand, look.
  foot_gauge     (PLA, flat) 80 x 14 x 5.2 block with three NOMINAL foot
                 pockets cut UP from its bed face under a 2.0 roof -- the
                 ladder/tray regime. The trio of TPU pads below is what
                 varies; the pocket is production.  Feeds FOOT_FIT.
  pilot_block    (PLA, ON ITS SIDE like the frame) two horizontal r1.25
                 rail pilots 16 apart, 11 deep, plus the real gasket gland:
                 self-tap feel in the frame's own regime and the gasket
                 stack with two real M3x16 csk.
  ladder_station_stub (PLA, flat, brim) the first 64 mm of the real deck
                 ladder: one spigot end, both serrated strips at the true
                 spacing, one sealed foot pocket, a deck plate. Reads the
                 board-on-shelf clearance and the deck_stop mesh.
  rail_cap_615 / 625 / 635 (PLA, top face down, 100%) the cap at three
                 magnet-pocket sizes: the cap is its own top-face-down
                 magnet gauge, and a cap either drops into a frame's window
                 or it does not.
  foot_pad_006 / 012 / 018 (TPU) tagged by FILENAME, the FOOT_FIT trio.
  fit_clips_petg (PETG, ON EDGE -- the production clip orientation)
    - three clip plates at RAIL_FIT 0.15 / 0.25 / 0.35, nub-tagged, plus a
      FOURTH at 0.25 whose latch tooth carries a 1.5 x 45 lead-in chamfer:
      the review predicts the plain tooth stops dead on the lip top and
      needs a tab pull; if only the chamfered one rocks on by thumb, the
      chamfer goes into din_clip() before any module prints.
  magnet_gauge   (PETG, flat) both magnet regimes on one tile: a cell row
                 (pockets from the bed face, 0.6 skin) at D 6.10 / 6.25 /
                 6.40, and a back-wall row (horizontal seats through a head
                 pocket, 0.6 skin behind) at D 6.25 / 6.40 / 6.55.
                 Feeds MAGNET_FIT.

Each reading feeds a named constant: RAIL_FIT and MAGNET_FIT (params.py),
RAIL_FIT_MORTISE / DETENT_BITE / FOOT_FIT / socket clearance (frame.py).
"""

from __future__ import annotations

import math
import os
import sys

from build123d import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401
from bench import (box, din_rail, attach_clip, safe_chamfer,  # noqa: E402
                   safe_fillet)
from frame import (half_round, foot_pocket, foot_pad, deck_ladder,  # noqa: E402
                   rail_cap, FOOT_L, FOOT_W, RAIL_R, TIE_R, RAIL_PAD_S,
                   RAIL_PAD_D, DETENT_BITE, MAGNET_D, MAGNET_T, MAGNET_FIT,
                   END_SCREW_Z, FOOT_PROUD, BAR_HEAD_T, MAGNET_FIT_WALL)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")

BASE_T = 2.0
MORTISE_FITS = (0.15, 0.25, 0.35)
SOCKET_CLEAR = (0.1, 0.2, 0.3)
FOOT_FITS = (0.06, 0.12, 0.18)
MAGNET_FITS_CELL = (0.10, 0.25, 0.40)
MAGNET_FITS_WALL = (0.25, 0.40, 0.55)
# Buried head magnets (2026-10-09, plate 10m): the side bin's sideways seats
# are awkward, so test sealing the disc in at a pause instead. Skin = PETG
# between the head pocket and the disc face; it is a VERTICAL wall, so it is
# counted in wall lines (0.42 nozzle line): 1, ~1.5, 2.
SKIN_COUPON_SKINS = (0.45, 0.65, 0.85)
SKIN_SLOT_W = MAGNET_T + 0.3          # a printed slot closes up; 0.3 lets the disc drop
SKIN_SLOT_L = MAGNET_D + MAGNET_FIT_WALL
SKIN_PAUSE_TOP = 7.0                  # bin-local slot top = the pause plane


def tag(part, x, y, z, n):
    """n identification nubs, so a loose gauge block stays identifiable."""
    for i in range(n):
        part += Pos(x + i * 4.0, y, z) * Cylinder(1.0, 1.6)
    return part


def mortise_block(fit, detent=True):
    """A vertical slice of the end frame's rail mortise.

    The rail cutter's axis is turned vertical, so the stub drops in from
    above -- which is also the frame's own print orientation for these
    features (the frame prints on its side, mortise axis up), so every wall
    the fit depends on prints the same way here as there.
    """
    blk = box(-4.0, RAIL_TOP_Z + fit + 2.4, -20.2, 20.2, 0, 12.0)
    # din_rail runs along X; Rot(0, +90, 0) turns its axis vertical AND
    # maps the section's n to +x -- the first cut used -90, which put the
    # profile at x -7.65..0, mostly OUTSIDE the block: a malformed mortise
    # that the stub-interference test caught (845 mm3, identical at every
    # fit -- the signature of a systematic transform error, not a fit).
    cutter = Rot(0, 90, 0) * din_rail(length=40.0, grow=fit)
    blk -= Pos(0, 0, 6.0) * cutter
    if detent:
        # the frame's own detent lens, same DETENT_BITE, axis across the lip
        blk += Pos(RAIL_TOP_Z - DETENT_BITE + 1.2, -(RAIL_LIP_W / 2 - 1.5),
                   6.0) * Rot(90, 0, 0) * Cylinder(1.2, 6.0)
    # entry lead-in on the top rim
    blk = safe_chamfer(blk, blk.edges().group_by(Axis.Z)[-1], 0.6)
    return blk


def chamfered_clip_plate(fit, latch_t=None, nubs=0):
    """The clip trio's fourth member. It USED to be the only clip with a
    lead-in chamfer on the latch tooth; plate 03 (2026-10-05) chose it, so
    the chamfer is now in din_clip() itself and this is the same clip as the
    2-nub one. Kept so plate 03's record still builds; it carries nothing new.
    """
    c = box(-17.0, 17.0, -23.0, 23.0, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
    c = safe_fillet(c, c.edges().filter_by(Axis.Z), 3.0)
    c = attach_clip(c, width=30.0, fit=fit, latch_t=latch_t)
    return tag(c, -10.0, 0.0, RAIL_TOP_Z + 3.0, nubs) if nubs else c


def magnet_gauge():
    """Both magnet regimes on one PETG tile, printed flat like the bins."""
    t = box(0, 66.0, 0, 26.0, 0, 3.0)                # cell floor: 3.0
    # cell row: pockets up from the bed face, 2.4 deep, 0.6 skin above
    for i, f in enumerate(MAGNET_FITS_CELL):
        t -= Pos(11.0 + i * 22.0, 8.0, -1) * Cylinder(
            (MAGNET_D + f) / 2, 1 + MAGNET_T + 0.4,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        t = tag(t, 7.0 + i * 22.0, 14.0, 3.0, i + 1)
    # back wall: the bin's real stack -- head pocket 3.3 deep, then the
    # seat, then 0.6 of skin to the far face
    bw = 3.3 + MAGNET_T + 0.6
    t += box(0, 66.0, 26.0 - bw, 26.0, 0, 14.5)
    hz = END_SCREW_Z
    mz = (MAGNET_D + MAGNET_FIT) / 2 + 0.6
    for i, f in enumerate(MAGNET_FITS_WALL):
        x = 11.0 + i * 22.0
        t -= box(x - 3.35, x + 3.35, 26.0 - bw - 1, 26.0 - bw + 3.3,
                 -1.2, hz + 2.75 + 1.1)
        t -= Pos(x, 26.0 - bw + 3.3 - 0.1, mz) * Rot(-90, 0, 0) * Cylinder(
            (MAGNET_D + f) / 2, MAGNET_T + 0.1,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        t = tag(t, x - 4.0, 26.0 - bw + 1.0, 14.5, i + 1)
    return t


def skin_coupon(skin=None):
    """One screw-head station of the side bin's back wall, to dock onto a real
    frame bar-end head and feel the snap.

    Same stack as side_bin(): back face at x = 0 against the frame, a head
    pocket HEAD_VOID deep, open at the bottom, gabled roof. It stands on a
    FOOT_PROUD plinth so, set on the desk, it sits where the bin's body sits
    on its TPU feet.
      skin=None  today's seat: open to the head pocket, the disc is pressed in
                 sideways after printing and pulls itself onto the head.
      skin=t     a closed slot t past the head pocket, open UPWARD to the
                 pause plane: the disc drops in on edge at the pause and the
                 next layers bridge over it. 0.4 mm of slot above the disc
                 keeps the nozzle off it.
    Nubs on top: 1, 2, 3 = the three skins; none = the open seat.
    """
    hv = BAR_HEAD_T + 0.3
    z0 = -FOOT_PROUD
    w2 = 2.75 + 0.6
    blk = box(0, 13.0, -10.0, 10.0, z0, 11.0)
    blk = safe_fillet(blk, blk.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], 2.0)
    top = END_SCREW_Z + 2.75 + 1.1
    pocket = box(-1, hv, -w2, w2, z0 - 1.0, top)
    ridge = make_face(Polyline((0, top), (hv / 2, top + hv / 2), (hv, top), close=True))
    blk -= pocket + Pos(0, w2, 0) * Rot(90, 0, 0) * extrude(ridge, 2 * w2)
    if skin is None:
        mz = (MAGNET_D + MAGNET_FIT_WALL) / 2 + 0.6
        blk -= Pos(hv - 0.1, 0, mz) * Rot(0, 90, 0) * Cylinder(
            (MAGNET_D + MAGNET_FIT_WALL) / 2, MAGNET_T + 0.1,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        return blk
    x0 = hv + skin
    blk -= box(x0, x0 + SKIN_SLOT_W, -SKIN_SLOT_L / 2, SKIN_SLOT_L / 2,
               SKIN_PAUSE_TOP - (MAGNET_D + 0.4), SKIN_PAUSE_TOP)
    n = SKIN_COUPON_SKINS.index(skin) + 1
    return _nubs(blk, n)


def _nubs(blk, n):
    """n nubs in a row across the coupon's top, clear of the slot."""
    for i in range(n):
        blk += Pos(10.0, (i - (n - 1) / 2) * 4.0, 11.0) * Cylinder(1.0, 1.6)
    return blk


def build():
    plate = box(0, 152.0, 0, 84.0, 0, BASE_T)
    plate = safe_fillet(plate, plate.edges().filter_by(Axis.Z), 4.0)

    # --- mortise gauges, y band 4..48 ---------------------------------------
    for i, fit in enumerate(MORTISE_FITS):
        cx = 26.0 + i * 46.0
        blk = Pos(cx, 25.0, BASE_T) * Rot(0, 0, 90) * mortise_block(fit)
        plate += blk
        plate = tag(plate, cx - 20.0, 6.0, BASE_T + 0.8, i + 1)

    # --- socket gauges, wall at y 56..74 ------------------------------------
    wall = box(78.0, 150.0, 56.0, 74.0, 0, 12.0)
    plate += wall
    for i, cl in enumerate(SOCKET_CLEAR):
        cx = 108.0 + i * 16.0
        # pocket: vertical cylinder, centre pushed 4 mm into the wall so the
        # mouth opens through the face -- the spigot stub drops in from the
        # top and the radial fit is felt at the closed side.
        plate -= Pos(cx, 56.0 + 4.0, 8.0) * Cylinder(RAIL_R + cl, 17.0)
        plate = tag(plate, cx - 2.0, 78.0, BASE_T + 0.8, i + 1)
    # the tie's own socket, R6 + 0.2, same construction
    plate -= Pos(88.0, 56.0 + 4.0, 8.0) * Cylinder(TIE_R + 0.2, 17.0)

    parts = {
        "fit_coupon_frame": plate,
        # the real rail section, end station 6 mm from one end (mounts)
        "rail_stub": din_rail(length=40.0, mounts=[-14.0]),
        "spigot_stub": half_round(24.0, RAIL_R, pilots=True),
        "tie_stub": half_round(30.0, TIE_R, pilots=True),
    }

    # --- foot gauge: production pockets, in the production regime ----------
    fg = box(0, 80.0, 0, 14.0, 0, 5.2)
    fg = safe_fillet(fg, fg.edges().filter_by(Axis.Z), 2.0)
    for i in range(3):
        fg -= foot_pocket(16.0 + i * 24.0, 7.0)
    parts["foot_gauge"] = fg
    for f in FOOT_FITS:
        parts[f"foot_pad_{int(round(f * 100)):03d}"] = foot_pad(fit=f)
    # Plain TPU reference block: 20 x 20 x 4.2 nominal, no features. Caliper
    # it before trusting the pad trio. Without it, three pads that all read
    # tight are ambiguous -- FOOT_FIT wrong, or TPU 95A simply printing
    # oversize on this machine? This separates the two, and it is the one
    # part stage 1 asks for that was never built (caught pre-flight).
    parts["tpu_block"] = box(0, 20.0, 0, 20.0, 0, 4.2)

    # --- pilot block: the frame's rail pilots + gasket gland, on its side --
    pb = box(0, 12.0, -15.0, 15.0, 0, 14.0)
    for y in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
        pb -= Pos(-1, y, 7.0) * Rot(0, 90, 0) * Cylinder(
            1.25, 12.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    pb -= box(-0.1, RAIL_PAD_D, -(RAIL_PAD_S / 2 + 0.15),
              RAIL_PAD_S / 2 + 0.15, 7.0 - 2.5, 7.0 + 2.5)
    parts["pilot_block"] = pb

    # --- ladder station stub: the first 120 mm of the real ladder -----------
    # 120, not 64, so it carries the left stub, the datum pocket, well and
    # peg, the slot at station 2 and the plate at 52: plate 02k's gauge cut
    # from the production code rather than from ledge_ladder.py.
    parts["ladder_station_stub"] = deck_ladder() & box(-3.0, 120.0, -30.0,
                                                       120.0, -2.0, 20.0)
    # --- half-bay gauge: rail-local 176..276 of the real ladder -------------
    # The half board's bay (182..268): its datum pocket and peg at 198.19,
    # its slot at 251.70, the rear shoulder stepped out HALF_RIB, and the
    # plate at 236 joining the rails. Plate 02l, asked for 2026-10-07 so the
    # half board is proven before the 85-minute ladder is printed.
    parts["half_bay_gauge"] = deck_ladder() & box(176.0, 276.0, -30.0,
                                                  120.0, -2.0, 20.0)

    # --- rail caps at three pocket sizes -------------------------------------
    for f in (0.15, 0.25, 0.35):
        parts[f"rail_cap_{int(round((MAGNET_D + f) * 100))}"] = rail_cap(fit=f)

    # --- PETG clip trio + the chamfered fourth, printed ON EDGE -------------
    cs = []
    for i, fit in enumerate(MORTISE_FITS):
        c = box(-17.0, 17.0, -23.0, 23.0, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
        c = safe_fillet(c, c.edges().filter_by(Axis.Z), 3.0)
        c = attach_clip(c, width=30.0, fit=fit)
        c = tag(c, -6.0, 18.0, RAIL_TOP_Z + 3.0 + 0.8, i + 1)
        cs.append(Pos(i * 40.0, 0, 0) * c)
    c4 = chamfered_clip_plate(0.25)
    c4 = tag(c4, -6.0, 18.0, RAIL_TOP_Z + 3.0 + 0.8, 4)
    cs.append(Pos(3 * 40.0, 0, 0) * c4)
    # Compound, not `a + b`: algebra over disjoint solids hands back a
    # ShapeList, and export_stl cannot swallow that.
    parts["fit_clips_petg"] = Compound(cs)

    parts["magnet_gauge"] = magnet_gauge()
    # One production clip on a plain plate (2026-10-10): the full-width,
    # 2.0 mm latch, to snap on and off before any module is reprinted.
    # Two latch thicknesses to feel the difference (user, 2026-10-10):
    # 1 nub = 1.8 mm (softer, ~1.7 % strain), 2 nubs = 2.0 mm (the default).
    parts["clip_test_18"] = chamfered_clip_plate(RAIL_FIT, latch_t=1.8, nubs=1)
    parts["clip_test_20"] = chamfered_clip_plate(RAIL_FIT, latch_t=2.0, nubs=2)
    parts["skin_coupon_open"] = skin_coupon(None)
    for t in SKIN_COUPON_SKINS:
        parts[f"skin_coupon_{int(round(t * 100)):03d}"] = skin_coupon(t)
    return parts


if __name__ == "__main__":
    print("building frame coupon ...")
    parts = build()
    # NOT out/stl_frame: frame.py purges that directory before it exports,
    # so every gauge on this plate was being silently deleted the next time
    # the frame was rebuilt -- and check.py only inspects files that exist,
    # so it reported ALL CLEAR over an empty gauge set. Two producers, one
    # purged directory. Own directory removes the whole class of problem.
    dst = os.path.join(OUT, "stl_coupon")
    os.makedirs(dst, exist_ok=True)
    for name, p in parts.items():
        export_stl(p, os.path.join(dst, f"{name}.stl"),
                   tolerance=0.02, angular_tolerance=0.1)
        print(f"    {name:20s} {p.volume / 1000:6.1f} cm3  "
              f"{p.bounding_box()}")
