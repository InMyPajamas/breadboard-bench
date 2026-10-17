"""Breadboard Bench Mk2 -- skeletal frame variant.

The console version is a solid tray doing four jobs at once: holding
breadboards, storing parts, supporting the panel, and providing the footprint.
That is why it reads as a block -- one mass has to be thick enough for the
worst of those jobs everywhere.

This version separates them. Two end frames define the geometry, three rails
span between them and do the work, and storage becomes clip-on parts rather
than moulded-in volumes. The DIN rail stops being a passenger screwed to a
panel and becomes a structural member -- which deletes the panel entirely, and
the panel was the single heaviest feature at ~84 cm3.

    end frame x2      the shape: foot, raked post, braced, lightened
    deck ladder       both cradle rails plus two rungs, printed as one part
    din rail          structural tie AND the module mount
    rear tie          stops the frames splaying
    rear tray         divided storage behind the post; grows two integral
                      buttresses that back the DIN rail at mid-span
    rail pad x4       TPU gasket that keeps the rail joints preloaded

Mk3 note: Mk2 had a strut that visited the tray (through slots cut in its
wall and dividers) and a rib that visited the rails (a loose chip resting
between them, 1 mm below the board line once the TPU feet lifted everything
else). Both guests are now absorbed by their hosts -- the tray grows the
strut as an integral buttress, the rails grow the ribs as ladder rungs --
and zero loose parts remain.

Run:  python cad/frame.py
"""

from __future__ import annotations

import math
import os
import sys

from build123d import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401
from bench import (box, din_clip, din_rail, board_plate,  # noqa: E402
                   screen_bezel, rail_bin, rim_cutter, safe_chamfer,
                   safe_fillet, display_mount_placed, display_post,
                   display_backplate, display_lock, display_lock_knob,
                   mic_crown)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")

# ---------------------------------------------------------------- layout ----
FR_W = 300.0             # overall width
FR_D = 165.0             # overall depth
FRAME_T = 6.0            # end frame thickness
SPAN = FR_W - 2 * FRAME_T                      # 288, rails span between frames
# How far each bar's end reaches INTO its frame socket. The sockets are cut
# 3.5 deep, and for two whole revisions the bars were built at SPAN exactly --
# stopping flush at the socket MOUTH, engaging nothing. Worse than the SPAN-2
# bug it echoes: the socket opening is r+0.2, bigger than the bar, so the end
# face bore on air and the whole deck was located axially by screw shanks.
# Caught in the exploded viewer, where the mouth reads as a mate that never
# happens. 3.0 into a 3.5 socket leaves 0.5 of end float per side -- the
# shrinkage allowance (0.3-0.5% is ~1 mm at 288) that the screws take up.
ENGAGE = 3.0

# Rails are half-round: a full-radius arc on top, a flat on the bed. The flat is
# the print surface and the arc is everything you see and touch, so there is no
# support anywhere and no square-bar reading. A ledge fills the section below
# LEDGE_Z, which means the section still narrows with height.
RAIL_R = 8.0
# 4.5, not 3.0: the boards bear on these ledges, and at 3.0 the bearing
# was 1.5 mm per edge -- a knife-edge that 288 mm of shrink plus a board a
# few tenths undersize could halve. 4.5 gives 3.0 mm per edge. The 1.5
# comes OUT of the cradle (below), so REAR_AXIS -- and every socket, the
# tray, the frames -- stays exactly where it was.
LEDGE = 4.5              # how far the ledge projects past the arc
LEDGE_Z = 3.0            # ledge top; the board sinks RECESS into it
# The indexing teeth are gone (plate 02d: a triangular tooth cannot print
# its own tip, and what survives folds). The board is located by its own
# dovetail cleats instead: see the recess block below REAR_AXIS.

FRONT_AXIS = 10.0        # centreline of the front deck rail
# CRADLE is the clear gap between the LEDGE inner faces, so it must be NARROWER
# than the board or the board drops straight through. At BB_D + 1.0 it was 1 mm
# wider and the boards had exactly zero bearing on either ledge -- each one was
# balanced on a single 10 mm cross rib, a see-saw. BB_D - 6.0 gives 3.0 mm of
# ledge under each edge; the arcs sit at y=16.2 at ledge height against a
# board edge at 19.5, so the board still drops in from above with 3.3 mm
# clearance a side.
CRADLE = 48.4            # pinned, NOT BB_D - 6.0 -- see the note under REAR_AXIS
REAR_AXIS = FRONT_AXIS + LEDGE + CRADLE + LEDGE + 2 * RAIL_R   # 83.4

# CRADLE is pinned at 48.4 rather than tracking BB_D, because BB_D feeds
# REAR_AXIS and moving that would drag the tie, tray, side bin, side tray
# and every head-pocket station with it. Measured 2026-08-28: a real
# MB-102 is 54.74 across; it sits centred with 9.33 of ledge under each edge.
_HALF_SPAN = (REAR_AXIS - FRONT_AXIS) / 2                      # 36.7

# --- board recess: the board sinks RECESS into the flat ledge ---------------
# Decided 2026-09-23 (PLAN.md, "the recessed ledge"). The ledge stays exactly
# where it is (z 0..3, out to RAIL_R + LEDGE) and so do both rail axes. Its
# top is cut down RECESS from the arc outward; the board sinks into that
# channel and its own dovetail cleats locate it: the first tab drops into an
# exact POCKET between two blocks of un-cut ledge on the front rail, the
# notch opposite drops over a PEG standing off a full-length SHOULDER of
# un-cut ledge on the rear rail, and every other station is a SLOT so the
# cleat spacing stops mattering. The board rests on a RIM-wide shelf just
# outside each bearing face -- the bare rim inside its tape -- and beyond
# that the ledge drops to a relief the tape never touches. Nothing stands
# above LEDGE_Z: every feature is ledge the cutter LEAVES.
RECESS = 1.2                                  # tab / notch engagement = this  (DECIDE on plate 02k)
BOARD_Z = LEDGE_Z - RECESS                    # 1.8  board underside = the rim shelf
TAPE_T, RIM = 0.6, 0.6                        # tape thickness; bare rim inside it (caliper 2026-09-20)
RELIEF_Z = BOARD_Z - TAPE_T - 0.4             # 0.8  floor under the tape zone, 0.4 clear
LAND_Y = math.sqrt(RAIL_R ** 2 - LEDGE_Z ** 2)   # 7.42 the land: the arc's own y at the ledge top
BOARD_EDGE = _HALF_SPAN - BB_D / 2            # 9.33 board edge, centred, rail-local
PLAY = 0.2                                    # per side; 0.4 total = the 55.14 gauge's clearance
FACE_Y = BOARD_EDGE - PLAY                    # 9.13 block outer faces = the rear shoulder face
SHELF_Y1 = FACE_Y + RIM                       # 9.73 rim shelf ends here, never under tape
END_STUB = 5.0                                # full ledge kept at each end: the frame shoulder
TAB_W, TAB_PROUD, TAB_H = 4.07, 1.41, 5.20    # measured MB-102 cleat
FIT, POCKET_D = 0.30, 1.71                    # proven on plates 02i / 02j
POCKET_W = TAB_W + FIT                        # 4.37 the locating pocket
SLOT_REACH = (0.0, 3.0, 4.0)                  # per station: datum exact, then +-3, +-4
BLOCK_L = 3.5                                 # each flanking block, along the rail
POCKET_WELL = 0.4                             # pocket floor below the rim shelf: flash never carries the board
PEG_W, PEG_D = 3.8, 1.3                       # the datum peg, into the 1.6 notch (plate 02h)
RAIL_GAP = 55.14                              # face to face across the rails (plate 02i)
assert abs(FACE_Y - (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2) < 0.02, FACE_Y
assert abs(FACE_Y - LAND_Y - POCKET_D) < 0.02, (FACE_Y, LAND_Y)
assert RELIEF_Z >= 0.8 - 1e-6, RELIEF_Z       # four layers under the tape zone


def _measured_board(board, **fallback):
    """The board as punched in on the hub's Boards tab (out/board_dims.json),
    else these fallbacks. The full board's 165.10 was our model's number;
    the ruler says ~160 and the caliper only reaches 150."""
    import json
    try:
        with open(os.path.join(OUT, "board_dims.json"), encoding="utf-8") as f:
            got = (json.load(f) or {}).get(board) or {}
    except Exception:
        got = {}
    out = dict(fallback)
    out.update({k: v for k, v in got.items() if isinstance(v, (int, float))})
    return out


_FULL = _measured_board("full", L=160.0, W=BB_D, SP=65.21, N=3)
_HALF = _measured_board("half", L=81.89, W=53.94, SP=53.51, N=2)
FULL_L, FULL_SP, FULL_N = _FULL["L"], _FULL["SP"], int(_FULL["N"])
HALF_L, HALF_W, HALF_SP, HALF_N = _HALF["L"], _HALF["W"], _HALF["SP"], int(_HALF["N"])
HALF_RIB = BB_D - HALF_W                      # 0.80 the half board is this much narrower
# Left end of each board, RAIL-LOCAL (build() places the ladder at assembly
# FRAME_T, so add 6 for assembly coordinates). The full board starts 3 clear
# of the 5 mm stub: its first cleat's distance from the end is unmeasured,
# and this makes a +-2 error harmless -- the pocket finds the tab wherever
# it is and the board only moves along the rail.
FULL_X0, HALF_X0 = 8.0, 184.0


def _stations(x0, b):
    """Rail-local x of each cleat. END_TAB (left end to the first tab's
    centre, calipered) places the datum directly; without it the cleats are
    assumed centred on the board."""
    n, sp = int(b["N"]), b["SP"]
    first = b["END_TAB"] if isinstance(b.get("END_TAB"), (int, float)) else b["L"] / 2 - (n - 1) / 2 * sp
    return tuple(round(x0 + first + k * sp, 2) for k in range(n))


FULL_ST = _stations(FULL_X0, _FULL)          # (22.79, 88.00, 153.21) with L 160, centred cleats
HALF_ST = _stations(HALF_X0, _HALF)          # (198.19, 251.70)
DECK_Z = RAIL_R          # top of the rail arc

# --- stability geometry -----------------------------------------------------
# The bench tips backward when you push a connector into a rail-mounted board.
# The governing term is
#     C = DECK_Z*cos(T) + s - (R - POST_Y0)*sin(T)      [N.mm of tip per N]
# and what dominates it is (R - POST_Y0): the distance from the post to the
# rear edge of the footprint. Mass is NOT in it, which is why every gram removed
# earlier in this design made the tipping worse rather than better.
#
# Pi 4/5 support fixes rail_s at 38 (the board plate is 68 mm deep because a
# Pi's 49 mm hole spacing needs cruciform arms out to +/-27, and it has to clear
# the rear deck rail). So the stability has to come from the post and the rake:
#   post forward 112 -> 103, footprint back 152 -> 165, rake 20 -> 37 degrees.
# That takes the loaded threshold from 9 N to 48 N against a ~25 N insertion,
# for 13 mm of depth. 37 degrees is also the honest upper limit before an
# e-paper starts catching ceiling glare.
FR_TILT = 37.0           # degrees from vertical -- frame-local, NOT params.PANEL_TILT
FR_SIN = math.sin(math.radians(FR_TILT))
FR_COS = math.cos(math.radians(FR_TILT))
FR_ROT_X = 90.0 - FR_TILT

POST_Y0 = 103.0          # front face of the raked post, at deck level
POST_T = 14.0            # post thickness, measured horizontally
POST_H = 60.0            # slope-run of the post face
FR_RAIL_S = 38.0         # rail centreline up the post face
# End rail-screw stations sit at x=6, NOT centred on the 6 mm plate at x=3.
# At x=3 the countersink rim (r 3.3) reached x=-0.3 -- clean through the
# rail's end face -- and the bore left a 1.3 mm wall for the cone to wedge
# apart, the classic csk-near-a-free-edge split. Caught by the user. x=6
# gives the rim 2.7 mm of rail; the pilot's cover comes from a landing boss
# grown on the plate's inner face.
RAIL_END_ST = 6.0
DETENT_BITE = 0.05       # was 0.15; see the detent comment in end_frame()
# The mortise's fit is its own knob. RAIL_FIT also sets the PETG clips'
# jaws, printed on edge; the mortise prints in flat PLA with vertical-wall
# undersize. The coupon reads them separately (mortise blocks vs clip
# trio) -- one constant for two regimes was a guaranteed miss on one side.
# 0.15, decided 2026-09-19 on plate 02b: the clean lips-down stub is the right
# fit in the 1-dot slot. (The first stub read 0.25 only because its sagged
# lips made it fat.) No longer tied to RAIL_FIT, the clips' clearance, which
# plate 03 decides.
RAIL_FIT_MORTISE = 0.15

TIE_Y = FR_D - 2 * RAIL_R
TIE_R = 6.0
# One screw line for all six bar-end heads. Per-rod "as high as the rod
# allows" (r - 2.85) put the rail screws at 5.15 and the tie's at 3.15 --
# each correct alone, ragged together: three heads per face at two heights
# reads as drift, not decision. The smallest rod sets the datum; the rail
# rods give up 2 mm of plate cover they never needed (pan heads exert no
# wedge, and 1.55 mm over a clearance bore is plenty), and every visible
# head lands on one line.
END_SCREW_Z = TIE_R - 2.85

# Gasket gland under the DIN rail's foot, at each of the four screw stations.
# It holds two 3 x 1 O-rings, one round each screw -- not the printed TPU pad
# it was drawn for (plate 02c, 2026-09-19: two rings, the clean stub and two
# cap screws make a solid joint). 0.80 deep squeezes a 1.0 ring 20%; the 0.70
# station was not needed. Eight bought O-rings replace four printed gaskets.
RAIL_PAD_S = 24.0        # along the post slope, straddling both screws
RAIL_PAD_D = 0.80        # gland depth in the post face

# ------------------------------------------------------------- rear bay -----
# The dead volume behind the post: 288 wide, 50 deep, and roofed only by the
# clip-on modules at Z=15.7. Nothing was using it. Filling it does three jobs
# at once -- storage with 45x the old bay trays, a shear panel tying the two
# end frames together, and mass at Y~120 which adds directly to the restoring
# moment about the rear edge.
TRAY_Y0 = REAR_AXIS + RAIL_R + 0.6       # clear of the rear deck rail's arc
# The rear wall lands ON the tie rod rather than stopping 2 mm short of it.
# That 2 mm was a slot running the whole 288 mm, and it -- not the tail's
# fit -- was the gap the eye reads; the buttress tails existed only to
# bridge it, which is why every attempt to restyle them still looked like a
# bracket bolted to the back. With the wall seated on the rod the tails go
# away entirely and contact goes from two 6 mm lines to ~1340 mm2.
#
# How far back the wall may come is set by the printer, not by taste: the
# tray prints upright, so the wall's underside may not exceed 45 degrees --
# and 45 degrees is exactly the rod's tangent point. The design line is
# handed over by the constraint.
TIE_FIT = 0.15                           # mating gap, rod to seat
TRAY_Y1 = TIE_Y - (TIE_R + TIE_FIT) / math.sqrt(2.0)
TRAY_H = 14.5                            # ducks under the lowest module
TRAY_WALL = 1.6
# 1.2 was the thinnest face in the whole design -- a 288-wide sheet that
# reads (and oil-cans) like foil from below, against a console precedent of
# 2.0 minimum for any floor. 1.6 matches the walls, so the box reads as one
# gauge of material; the dividers keep each unsupported field under ~46 mm.
TRAY_FLOOR = 1.6
# Wire passthrough per cell, sized so a USB plug's overmold fits through --
# micro-B runs to ~11 x 7, USB-C ~12 x 6.5. Height is the binding constraint
# in a 14.5 mm wall, so the slot is a wide stadium rather than a circle.
PASS_W = 13.0
PASS_H = 7.0
TRAY_CELLS = 6

# Mid-span supports for the DIN rail. An open top-hat section has J ~ 27 mm4,
# which over a 288 mm span is torsionally soft enough that a module pushed at
# mid-span rolls the rail rather than loading its end joints. Mk2 stood two
# separate strut blades on the tray here, passing through slots cut in the
# tray's wall and dividers -- the slots read as cheap notches and breached the
# rear wall, opening two cells to the back. Mk3 deletes both: at each station
# the tray's own divider thickens to 6 mm and continues upward past the rim as
# an integral buttress, so the support IS the tray and there is nothing to cut
# a slot for. The rail is still backed by four coplanar faces (two frames, two
# buttresses): free spans 91/94/91 mm, a (288/94)^3 ~ 29x stiffness gain over
# an unsupported 288.
# X=100 and 200 land midway between the rail's 25 mm slots, so the buttress's
# own screw pair has 5 mm of solid web either side.
BUTTRESS_X = (100.0, 200.0)
BUTTRESS_T = 6.0
# The top must clear the shoulder rib (rail-local s 51.75..54.15); stopping at
# 50 left the rib hanging off the end of its face -- Mk2's lesson, kept.
BUT_TOP_S = 56.0         # = FR_RAIL_S + RAIL_WEB_W / 2 + 4.5, land top
BUT_TOE_S = 20.0         # where the post-plane face hands over to the 45 rake
# V-notch apex above the tie axis: exactly TIE_R * sqrt(2) puts both 45-degree
# faces tangent to the R6 rod -- two line contacts that self-centre the tray
# in Y and Z but leave it free in X, so 288 mm of print shrinkage cannot bind.
# (TIE_V_APEX lived here: the V-notch tail's apex at TIE_R*sqrt(2), which
#  made both faces tangent to the rod. Retired with the tails -- the rear
#  wall's conforming seat replaces it. See TRAY_Y1.)


def post_point(s, n=0.0):
    """(Y, Z) s mm up the post face, n mm along its outward normal.

    Uses the frame's own rake, not the console's PANEL_TILT -- the two designs
    need different angles and sharing the constant would silently re-cut the
    console's panel, gussets and bins every time this one moved.
    """
    y = POST_Y0 + s * FR_SIN - n * FR_COS
    z = DECK_Z + s * FR_COS + n * FR_SIN
    return y, z


FR_RAIL_Y, FR_RAIL_Z = post_point(FR_RAIL_S)
POST_TOP_Y, POST_TOP_Z = post_point(POST_H)


def to_post(shape, x_centre=FR_W / 2, s=FR_RAIL_S, n=0.0):
    y, z = post_point(s, n)
    return Pos(x_centre, y, z) * Rot(FR_ROT_X, 0, 0) * shape


# ------------------------------------------------------------- end frame ----
def end_frame():
    """Foot bar + raked post, braced by a diagonal, then lightened.

    Drawn as one closed profile and extruded, so it is a single stiff plate
    rather than an assembly of struts -- then the holes take the mass back out.
    A truss made of holes prints far better than a truss made of struts: no
    joints, no stress risers, and every edge is vertical in the print.
    """
    pb_y = POST_TOP_Y + POST_T / FR_COS
    profile = [
        (0.0, 0.0),
        (FR_D, 0.0),
        (FR_D, 14.0),
        (pb_y, POST_TOP_Z),
        (POST_TOP_Y, POST_TOP_Z),
        # DECK_Z exactly, not +2: raising this point tilted the profile's post face
        # off the post_point line, so the DIN rail cut ~0.7 mm into the plate.
        (POST_Y0, DECK_Z),
        (0.0, DECK_Z),
    ]
    face = make_face(Polyline(*profile, close=True))
    frame = Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(face, FRAME_T))

    def window(y0, y1, z0, z1, r):
        w = box(-1, FRAME_T + 1, y0, y1, z0, z1)
        return safe_fillet(w, w.edges().filter_by(Axis.X), r)

    # Lighten the wedge BEHIND the post -- cut in the post's own frame, so the
    # window leans with it. Axis-aligned rectangles were the bug here: the post
    # shifts 0.36 mm in Y for every 1 mm of height, so a window that cleared it
    # at the bottom cut straight through it further up. It left 1.3 mm of post
    # at Z=40 and nothing at all at Z=50 -- the DIN rail was hanging off the
    # plate's back edge.
    # Window 2 starts at 44, not 36. At 36 it swallowed the DIN rail's own
    # mounting pilot at s=38 -- the screw passed through 3 mm of front skin,
    # 8 mm of air, then 3 mm of rear skin, and 3 mm of engagement will not hold
    # a rail carrying two cantilevered modules. 44 leaves a 14 mm solid land.
    # One window, not two. The second ran s = 44..56 and left only a 14 mm
    # solid land at the rail station -- not enough to straddle the centreline
    # with two screws. Deleting it makes the post solid from s = 26 up, which
    # Finishing blends happen HERE, straight after the windows and before
    # every functional feature: at the end of the function they had to
    # survive the detent's tangent cylinder; after the brace cut they choked
    # on its (now-working) corner fillets. OCCT dropped BOTH ops for the
    # whole part either way -- the review's "end frame shipped without its
    # modelled chamfers". Everything cut after this line -- brace window,
    # sockets, mortise, boss, pockets -- stays crisp on purpose: those are
    # fit surfaces, and fit surfaces want edges, not softening.
    frame = safe_fillet(frame, frame.edges().filter_by(Axis.X), 2.0)
    frame = safe_chamfer(frame, frame.edges().filter_by(
        lambda e: abs(e.center().X) < 0.01
        or abs(e.center().X - FRAME_T) < 0.01), 0.6)

    # costs about 1 g per plate and buys a real bolted couple.
    # Top edge 24.4, not 26.0: the buttress base sits on the s=26 line, and
    # a window run to 26 put its rim COINCIDENT with the buttress face
    # (measured 0.00..-0.5 mm over n -5..-9, tapering to a 0.8 sliver at
    # the corner fillet -- the user circled it). 24.4 gives a constant
    # >= 1.4 mm reveal, so rim and buttress read as two decisions.
    # The post window is CLOSED (2026-10-08). It left 3 mm ribs either side
    # of an 18 mm opening in the one member that carries the rail into the
    # frame, and the first printed frames flexed there under their own
    # weight ("almost bending under its own weight at that one open screen
    # hole"). Solid costs about 1 g per frame. The old cutter is kept here,
    # disabled, so the window's reasoning above still reads.
    POST_WINDOWS = ()
    for s0, s1 in POST_WINDOWS:
        cut = box(-1, FRAME_T + 1, -(s1 - s0) / 2, (s1 - s0) / 2,
                  -POST_T + 3.0, -3.0)
        # 3.9, not 4.0: the cutter is 8.0 deep and a fillet at exactly half
        # is a tangent case OCCT rejects.
        cut = safe_fillet(cut, cut.edges().filter_by(Axis.X), 3.9)
        frame -= to_post(cut, x_centre=FRAME_T / 2, s=(s0 + s1) / 2)

    # Window bottoms at 5.2, not 4.0: the front foot pocket tops out at 3.2,
    # and 4.0 left a 0.8 mm roof -- ONE extrusion line carrying the whole
    # front foot load (print review blocker, measured 0.797). 5.2 gives a
    # 2.0 mm / 10-line roof for ~1 g.
    # The foot bar's three lightening windows are CLOSED (2026-10-08). They
    # left a 5.2 mm tall bar between them with the bar-end screw's 3.4 mm
    # bore through it, and the printed frames flexed there under their own
    # weight ("almost bending under its own weight at that one open screw
    # hole"). Solid costs about 7 g per frame. Kept here, disabled.
    BAR_WINDOWS = ()
    for w in BAR_WINDOWS:
        frame -= window(*w)
    # was: window(16, 60, 5.2, 14.0, 4.0); window(68, 98, 5.2, 14.0, 4.0);
    #      window(112, 140, 5.0, 16.0, 5.0)
    # The deeper foot is a solid triangle under the raked post. It is the mass
    # furthest from the front, and mass at the rear pivot contributes nothing
    # to the restoring moment -- so it is the cheapest place to take grams out.

    # Seats for the round rails -- a half-round socket locates a half-round bar
    # in both axes at once, which a rectangular pocket cannot.
    for y, r in ((FRONT_AXIS, RAIL_R), (REAR_AXIS, RAIL_R), (TIE_Y, TIE_R)):
        seat = Pos(FRAME_T - 1.5, y, 0) * Rot(0, 90, 0) * \
            Cylinder(r + 0.2, 4.0)
        frame -= seat - box(-1, FRAME_T + 1, y - r - 2, y + r + 2, -r - 2, 0)
        # 3.2 clearance through the PLATE, not a 2.5 pilot. A single 2.5 hole
        # threads the screw into the plate as well as the rod, so it cannot
        # draw the two together -- if the rod sits 0.2 mm proud in its socket
        # the screw just holds it there. Clearance in the near part, pilot in
        # the far one, is what makes a screw a clamp instead of a peg.
        # All three holes on END_SCREW_Z, the shared screw datum -- see the
        # constant. (History: r * 0.4 broke a countersink through the
        # plate's bottom edge; r - 2.85 fixed that but scattered the heads
        # across two heights. Pan heads on one line is where it settled.)
        # r 1.7 (3.4), not 1.6: printed holes arrive 0.1-0.3 undersize and a
        # 3.2 bore self-threads on the M3, defeating the clamp's shrink
        # take-up (print review).
        frame -= Pos(0, y, END_SCREW_Z) * Rot(0, 90, 0) * Cylinder(1.7, 14)
    # ---- rail mortise: the rail's own profile IS the socket ----------------
    # Mk3 held the rail against the post with a shoulder rib and one small
    # hook -- two fingers doing a socket's job, and they read that way (the
    # user's verdict, with a linear-slide rail as the reference). Now the
    # land grows a full shroud and the rail's own grown cross-section is
    # subtracted straight through it -- din_rail(grow=RAIL_FIT) exists for
    # exactly this. The rail END slides in along X and is captured by shape
    # on every other axis, the same spigot-in-socket grammar as the round
    # bars. The roof is windowed over the web so the two screws stay
    # reachable, which leaves an L-cheek wrapped over each lip -- the
    # carriage-on-a-slide-rail section, full 12 mm deep instead of 6.
    SHROUD_S = RAIL_LIP_W / 2 + RAIL_FIT_MORTISE + 2.4    # cheek outer edge
    shroud = box(0, FRAME_T + 6.0, -SHROUD_S, SHROUD_S,
                 0, RAIL_TOP_Z + RAIL_FIT_MORTISE + 2.2)
    frame += to_post(shroud, x_centre=0.0)
    frame -= to_post(din_rail(length=40.0, grow=RAIL_FIT_MORTISE),
                     x_centre=RAIL_END_ST)
    # Window the roof over the web band: screws and driver come in here.
    frame -= to_post(box(-1, FRAME_T + 7.0, -12.5, 12.5,
                         RAIL_CHANNEL_Z, RAIL_TOP_Z + RAIL_FIT_MORTISE + 3.2),
                     x_centre=0.0)
    # The CLICK: a 0.15-bite detent lens on the down-slope cheek's roof,
    # ramped in X by its own curvature. The rail's 1.2 mm lip cams under it
    # on the way in and relaxes home -- tactile, and it holds the rail
    # against sliding back out before the screws go in. Bite is deliberately
    # shy: XY over-extrusion adds to it, and a too-proud detent would plough.
    # Bite DETENT_BITE, not 0.15: the DFM review measured the stack rigid
    # (lip backed solid, roof 2.2 thick) -- a 0.15 lens cannot cam, it
    # ploughs the rail's slide face or shears. 0.05 is a witness, not a
    # latch; the coupon's mortise blocks decide whether it survives.
    frame += to_post(
        Pos(RAIL_END_ST, -(RAIL_LIP_W / 2 - 1.5),
            RAIL_TOP_Z - DETENT_BITE + 1.2) *
        Rot(90, 0, 0) * Cylinder(1.2, 6.0), x_centre=0.0)

    # Landing buttress for the rail screws -- the boss, EXPRESSED. Chosen
    # from the workflow's four double-verified options (renders in the
    # hub's Joint study tab). Same structural envelope as the old
    # 6 x 26 x 11 block: s 26..52 footprint, 11 mm deep over both pilots,
    # z=0 seating land, tip coplanar with the shroud so the two read as
    # ONE bracket the rail passes through. The expression: 45-degree back
    # -corner facets gathering mass behind the screw band, a prow rake off
    # the outboard half echoing the tray buttresses, a gabled window
    # between the pilots (the tray buttress's own lightening cut, floored
    # by 6 mm of plate), and 1.0 eased arrises matching the plate. Facets
    # start at z=-9, the rake plane's own tip line -- earlier -8.5 facets
    # left 0.71 mm slivers OCCT refused to chamfer. Extrudes along X, so
    # every wall is vertical in the print pose.
    prof = [(-12.0, 0.0), (14.0, 0.0), (14.0, -9.0), (12.0, -11.0),
            (-10.0, -11.0), (-12.0, -9.0)]
    but = Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(
        make_face(Polyline(*prof, close=True)), 6.0))
    # prow: 45-degree wedge off the back, from x=3.5 to the tip
    rake = make_face(Polyline((3.5, -11.5), (7.0, -8.0), (7.0, -11.5),
                              close=True))
    but -= Pos(0, 15.0, 0) * (Rot(90, 0, 0) * extrude(rake, 28.0))
    # gabled lightening window between the pilots
    win = make_face(Polyline((-1.6, -7.4), (3.6, -7.4), (3.6, -4.4),
                             (1.0, -2.5), (-1.6, -4.4), close=True))
    win = safe_fillet(win, win.vertices(), 1.2)
    but -= Pos(-0.5, 0, 0) * (Rot(0, 0, 90) * (Rot(90, 0, 0) *
                                               extrude(win, 8.0)))
    # Ease the free arrises only -- not the z=0 seating land, not the root
    # seam, not the window rim. Three sequential passes: one combined set
    # makes OCCT resolve every shared vertex at once and it throws.
    but = safe_chamfer(but, but.edges().filter_by(
        lambda e: abs(e.center().X - 6.0) < 0.05 and e.center().Z < -0.5
        and e.length > 3.0
        and (abs(e.center().Y - 1.0) > 4.6 or e.center().Z < -7.9)), 1.0)
    but = safe_chamfer(but, but.edges().filter_by(
        lambda e: e.length > 15.0 and abs(e.center().Z + 11.0) < 0.6
        and abs(e.center().X - 3.5) < 1.2), 1.0)
    but = safe_chamfer(but, but.edges().filter_by(
        lambda e: abs(abs(e.center().Y - 1.0) - 13.0) < 0.3
        and abs(e.center().Z + 9.0) < 0.3 and e.length > 3.0), 1.0)
    frame += to_post(but, x_centre=FRAME_T)

    # A TPU gasket sits in this pocket and stands 0.35 mm proud of it, so the
    # screws squeeze it while the hook takes the reaction. That makes the joint
    # preloaded rather than merely tightened: PLA creeps under a sustained
    # bolt load and a hard-faced plastic joint goes slack over months, where a
    # compressed elastomer keeps pushing. It also puts TPU-on-PLA friction
    # across the whole faying surface instead of PLA on PLA. Centred on the
    # screw station, so it spans plate and boss.
    pad = box(0, 5.0, -(RAIL_PAD_S / 2 + 0.15),
              RAIL_PAD_S / 2 + 0.15, -RAIL_PAD_D, 0.1)
    frame -= to_post(pad, x_centre=RAIL_END_ST - 2.5)

    # Two M3 pilots straddling the centreline, into 11 mm of solid post.
    for y in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
        frame -= to_post(Pos(0, y, -11) * Cylinder(1.25, 24),
                         x_centre=RAIL_END_ST)

    # (The side faces stay clean: the side bin holds on magnetically to the
    # bar-end screw heads -- see side_bin() -- so the frame carries nothing
    # for it. An earlier revision cut J-slot keyholes here.)

    # TPU feet at the front and rear of each plate. In the print pose (laid
    # on its side) this face is vertical, so the pocket is a plain horizontal
    # slot -- no bridge.
    # Foot stations moved from 18/147: those Mk2 positions predate the
    # bar-end screws, and both pockets crossed one -- the front pocket ran
    # over the front rail's screw at y=10 and the rear pocket over the tie's
    # at y=149. 30/132 clear every screw hole and every rail socket; the
    # rear stance gives up 15 mm, which the tray's own rear feet cover.
    for y in FR_FOOT_Y:
        # Open on both faces (wider than the 6 mm plate), so only the LENGTH
        # can pinch the pad: it takes the same +0.30 as every closed pocket.
        fl = (FOOT_L + FOOT_POCKET_OVER) / 2
        frame -= box(FRAME_T / 2 - FOOT_W / 2 - FOOT_FIT,
                     FRAME_T / 2 + FOOT_W / 2 + FOOT_FIT,
                     y - fl, y + fl, -1.0, FOOT_D)

    return frame


# ------------------------------------------------------------- deck rail ----
def half_round(length, r, holes=None, engage=0.0, pilots=True,
               holes_skip=None):
    """A bar that is a cylinder above the bed and a flat on it.

    Everything above Z=0 is arc, so the eye reads a turned rod; everything the
    printer sees is a flat first layer and a section that only ever narrows
    going up. No supports, no square-bar reading.

    `engage` extends the arc past x=0 and x=length so the ends live inside the
    frame sockets; every feature keyed to 0..length (holes, feet, rungs, the
    deck rails' ledges) stays where it was, and the ledge end faces become the
    shoulders that butt the frame.
    """
    bar = Pos(length / 2, 0, 0) * Rot(0, 90, 0) * \
        Cylinder(r, length + 2 * engage)
    bar -= box(-engage - 1, length + engage + 1, -r - 1, r + 1, -r - 2, 0)
    if holes:
        pitch, hr = holes
        skip = holes_skip or ()
        # Keep the hole strictly inside the arc. The clamp has to be a real
        # wall, not a token: at 0.6 the hole's top sat at Z=7.4 in a rod whose
        # surface only reaches 7.4 at y=0, so the cap over each hole tapered
        # from 0.6 mm at the centre to NOTHING at y=+/-3.04 and broke out the
        # crown. 1.6 keeps the break-out point (y=4.8) outside the hole.
        hz = r * 0.5
        hr = min(hr, hz - 1.6, r - hz - 1.6)
        n = int((length - 2 * pitch) // pitch)
        start = (length - (n - 1) * pitch) / 2
        for i in range(n):
            x = start + i * pitch
            # holes_skip was dead code for three revisions (assigned, never
            # read): four bores vented the ladder's foot pockets, exactly
            # print-review finding 10. A bore within 10.7 of a foot station
            # (8 half-pocket + 2.4 bore radius + margin) is skipped.
            if any(abs(x - sx) < 10.7 for sx in skip):
                continue
            bar -= Pos(x, 0, hz) * Rot(90, 0, 0) * Cylinder(hr, 2 * r + 6)
    # M3 pilots in the rod ends, matching the clearance holes in the plates.
    # 2.5 is M3's minor diameter; self-tapping into solid PETG at this size
    # holds 300-500 N, against 120-200 N if the screw finds sparse infill.
    # All pilots sit on END_SCREW_Z, the one screw line every bar-end head
    # shares (see the constant) -- crown cover in the smallest rod is the
    # binding constraint and the bigger rods simply inherit the datum.
    # `pilots=False` for members whose ends weld into another part (the
    # ladder rungs) -- a pilot there just hollows the joint.
    if pilots:
        # Teardropped, not round: a horizontal bore in a flat-printed bar has
        # an unsupported crown ring, and the tie's sat under 1.58 mm of
        # sparse-backed material (print review). Apex up, axis along X.
        for x, sgn in ((-engage, 1), (length + engage, -1)):
            bar -= Pos(x, 0, END_SCREW_Z) * Rot(90, 0, 0) *                 Rot(0, sgn * 90, 0) * teardrop(1.25, 26)
    return bar


def deck_rail(ledge_side=+1):
    """Half-round cradle rail with an integral, RECESSED ledge.

    The ledge fills the section below LEDGE_Z out past the arc, so the board
    lands on a shelf rather than balancing on a curve -- and because the
    fill is at the BOTTOM, the section still narrows with height.

    The shelf is cut down RECESS from the arc outward and the board sinks
    into it. Where the arc meets that floor it bulges past the tab tip, so
    a flat LAND is cut at LAND_Y (the arc's own y at the ledge top): it is
    the back wall of every pocket. Outside the bearing face the floor is a
    RIM-wide shelf -- the small rest, the board's bare rim -- and beyond
    that a relief the tape never touches. Everything that locates the board
    is ledge the cutter LEAVES: on the front rail (+y) two blocks flank each
    station, the gap between them the pocket (exact at the datum, a slot
    elsewhere); on the rear rail (-y) a full-length shoulder is the rear
    stop, stepping out HALF_RIB in the half board's bay, and one peg per
    board stands off it into the notch. The pocket floor is POCKET_WELL
    lower still, so a tab with flash can never carry the board.
    """
    s = 1 if ledge_side > 0 else -1
    rail = half_round(SPAN, RAIL_R, holes=(20.0, 4.6), engage=ENGAGE,
                      holes_skip=FOOT_X)
    # The ledge box refills every cross-bore below LEDGE_Z, so shelf, blocks,
    # shoulder and pegs are all solid; only the bore mouths above z 3 show.
    rail += box(0, SPAN, 0, s * (RAIL_R + LEDGE), 0, LEDGE_Z)
    # ...and the same box refills the lower, ledge-side half of both END
    # pilots beyond 3 mm deep (they sit at END_SCREW_Z 3.15, the box tops out
    # at 3.0 and starts where the engage ends). Found by the software test
    # fit: an M3 would have had to cut its own way through. Cut them again,
    # exactly as half_round does.
    for px, sgn in ((-ENGAGE, 1), (SPAN + ENGAGE, -1)):
        rail -= Pos(px, 0, END_SCREW_Z) * Rot(90, 0, 0) * \
            Rot(0, sgn * 90, 0) * teardrop(1.25, 26)
    x0, x1 = END_STUB, SPAN - END_STUB                         # 5 .. 283
    hx0, hx1 = HALF_X0 - 2.0, HALF_X0 + HALF_L + 2.0           # the half bay
    yin = s * (RAIL_R + LEDGE + 1.0)                           # past the ledge's outer edge
    zt = LEDGE_Z + 1.0
    rib = HALF_RIB if s < 0 else 0.0                           # the rear rail steps out in the half bay
    # the channel and the land in one box, then the tape relief beyond the
    # rim shelf, in three runs so the half bay can step out
    cut = box(x0, x1, s * LAND_Y, yin, BOARD_Z, zt)
    cut += box(x0, hx0, s * SHELF_Y1, yin, RELIEF_Z, zt)
    cut += box(hx1, x1, s * SHELF_Y1, yin, RELIEF_Z, zt)
    cut += box(hx0, hx1, s * (SHELF_Y1 + rib), yin, RELIEF_Z, zt)
    # every feature is ledge the cutter LEAVES: keep boxes come off the cutter
    if s > 0:                                                  # front: flanking blocks
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                for d in (-1, 1):
                    cut -= box(sx + d * half, sx + d * (half + BLOCK_L),
                               0, s * FACE_Y, BOARD_Z - 1.0, LEDGE_Z + 2.0)
    else:                                                      # rear: shoulder, rib, datum pegs
        cut -= box(x0, x1, 0, s * FACE_Y, BOARD_Z - 1.0, LEDGE_Z + 2.0)
        cut -= box(hx0, hx1, 0, s * (FACE_Y + HALF_RIB), BOARD_Z - 1.0, LEDGE_Z + 2.0)
        for sx, face in ((FULL_ST[0], FACE_Y), (HALF_ST[0], FACE_Y + HALF_RIB)):
            cut -= box(sx - PEG_W / 2, sx + PEG_W / 2, 0, s * (face + PEG_D),
                       BOARD_Z - 1.0, LEDGE_Z + 2.0)
    rail -= cut
    if s > 0:                                                  # pocket wells, after the cut
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                rail -= box(sx - half + 0.05, sx + half - 0.05, s * LAND_Y, s * SHELF_Y1,
                            BOARD_Z - POCKET_WELL, BOARD_Z + 0.1)
    # Chamfer FIRST, pockets after. The pockets' flared mouths put small
    # edges on the bed plane; selected with the rest they make OCCT refuse
    # the whole chamfer, and the rail silently loses its elephant-foot relief.
    rail = safe_chamfer(rail, rail.edges().group_by(Axis.Z)[0], 0.5)
    for x in FOOT_X:
        rail -= foot_pocket(x, 0.0)
    return rail


# ------------------------------------------------------------- TPU feet -----
FOOT_L, FOOT_W, FOOT_D = 16.0, 6.0, 3.2   # the PAD's nominal; pocket depth
# The pocket is the pad's nominal PLUS this, on length and on width. Decided
# 2026-09-19 on foot_gauge_v2 with a production pad calipered at 16.24: no
# pad at all would enter a 16.00 x 6.00 pocket (a small internal feature in
# PLA closes up), +0.20 only went in forced, +0.30 fits and holds through an
# invert-and-shake and with the gauge bent. FOOT_FIT and the pads already
# printed stay exactly as they are. The mouth is flared 0.3 at the bed face,
# as on the gauge, so the pad starts square and first-layer squish has
# somewhere to go.
FOOT_POCKET_OVER = 0.30
FOOT_MOUTH = 0.3
FOOT_PROUD = 1.0                          # how far the pad stands below
FOOT_FIT = 0.12                           # interference per side. 0.25 made a
                                          # sealed pocket 2 of 14 behave alike:
                                          # incompressible TPU scattered stance
                                          # 0.24-0.53 mm (print review)
FOOT_X = (52.0, 144.0, 236.0)             # along each deck rail
FR_FOOT_Y = (30.0, 132.0)                 # along each end frame; clears the
                                          # bar-end screws at y=10/149 and
                                          # every rail socket

# Tray feet (Mk3). Mk2's tray sat flat on its floor while everything around it
# rode FOOT_PROUD above the desk on TPU -- so the tray either floated 1 mm or
# carried the bench on a hard corner. Four floor bosses with standard pockets
# put the tray on the same stance as everything else. Stations: under both
# buttresses (a module shoved onto the rail now has a compression path
# straight down the blade into the desk, which Mk2's hovering strut never
# had), plus two outboard so the 288 mm floor cannot drum.
# Outer stations hug the end walls (mid stations already sit on the
# dividers), so every boss reads as a wall plinth instead of a random block
# in the middle of a cell floor -- which is exactly what the first pass
# looked like from above.
TRAY_FOOT_X = (12.0,) + tuple(x - FRAME_T for x in BUTTRESS_X) + (276.0,)
TRAY_FOOT_Y = 41.0                        # tray-local; keeps the mass rearward
TRAY_BOSS_T = 4.5                         # local floor under each pocket
# The tray reaches the post plane through its own feet, so differential squash
# between frame pads and tray pads would tilt the buttress land. Cutting the
# tray pockets 0.1 deeper starts its pads 0.1 shy of the frame-pad plane; the
# 0.35-proud rail gasket absorbs the difference.
TRAY_FOOT_SHY = 0.1


def foot_pocket(x, y, ang=0.0):
    """Pocket for a TPU pad, cut up into a part's bed face: a filleted prism
    FOOT_POCKET_OVER larger than the pad's nominal, with a short flared mouth.
    Same construction as foot_gauge_v2's winning pocket."""
    L, W, R, M = FOOT_L + FOOT_POCKET_OVER, FOOT_W + FOOT_POCKET_OVER, 1.5, FOOT_MOUTH
    body = Pos(0, 0, (FOOT_D - 1.0) / 2) * extrude(
        RectangleRounded(L, W, R), amount=(FOOT_D + 1.0) / 2, both=True)
    flare = loft([RectangleRounded(L + 2 * M, W + 2 * M, R + M),
                  Pos(0, 0, M) * RectangleRounded(L, W, R)])
    below = Pos(0, 0, -0.5) * extrude(
        RectangleRounded(L + 2 * M, W + 2 * M, R + M), amount=0.5, both=True)
    return Pos(x, y, 0) * (body + flare + below)


def foot_pad(fit=None):
    """TPU insert. Oversize on every face that goes in the pocket.

    Feet under the END PLATES ONLY would lift the deck rails clear of the desk,
    and a 288 mm unsupported rail sags ~10 mm under a firm press. So the pads go
    under the RAILS as well, at 52/144/236 -- that keeps every span under 92 mm
    and puts the whole bench on TPU, which also fixes the over-constrained
    5-coplanar-contact stance that made it rock on an uneven desk.
    """
    ff = FOOT_FIT if fit is None else fit    # coupon prints a tagged trio
    p = box(-FOOT_L / 2 - ff, FOOT_L / 2 + ff,
            -FOOT_W / 2 - ff, FOOT_W / 2 + ff,
            0, FOOT_D + FOOT_PROUD)
    p = safe_fillet(p, p.edges().filter_by(Axis.Z), 1.5)
    # Relief groove across the pocket face: displaced rubber needs an escape
    # or the pad hydraulic-locks and the stance scatters (print review).
    p -= box(-FOOT_L / 2 - 1, FOOT_L / 2 + 1, -0.6, 0.6,
             FOOT_D + FOOT_PROUD - 0.8, FOOT_D + FOOT_PROUD + 1)
    # lead-in so it starts square, and a soft face on the desk side.
    # Outer rim only at 0.5: the relief groove leaves 0.9-wide top strips,
    # and an 0.8 chamfer on both sides of one is impossible.
    p = safe_chamfer(p, p.edges().group_by(Axis.Z)[-1]
                     .filter_by(lambda e: abs(e.center().Y) > 0.8), 0.5)
    return safe_chamfer(p, p.edges().group_by(Axis.Z)[0], 0.6)


DECK_PLATE_W = 20.0      # each deck plate, along the rails


def deck_ladder():
    """Both cradle rails plus three deck plates, printed flat as one part.

    Mk2's cross_rib was a loose 10 x 3 chip that just rested between the
    rails; Mk3 bridged two R3 half-round rungs rigidly between the ledges
    as see-saw insurance. They were honest about being insurance, and the
    user read them as what they were: flimsy. The rail feet at FOOT_X
    already cap every vertical span at 92 mm (0.18 mm under a 20 N press,
    span-cubed), so what the deck wants is not more rungs but a few places
    that read as DECK: three 20 mm plates, one over each foot station, so
    a board pressed at mid-span bears straight down onto a TPU foot. Tops
    at RELIEF_Z, the relief plane: the plates are rungs under the tape zone
    now, never touched -- the board carries on the rails' rim shelves and
    the plates only stiffen the ladder. 288 x 89.4 flat -- fits the plate;
    give the slicer a brim, long thin flat parts warp.
    """
    lad = Pos(0, FRONT_AXIS, 0) * deck_rail(+1) + \
        Pos(0, REAR_AXIS, 0) * deck_rail(-1)
    # Plates land 0.5 INTO each ledge, not against it -- a coplanar-face
    # union is exactly the kind of touching-solids booleans OCCT fails
    # quietly on.
    y0 = FRONT_AXIS + RAIL_R + LEDGE - 0.5
    y1 = REAR_AXIS - RAIL_R - LEDGE + 0.5
    for fx in FOOT_X:
        plate = box(fx - DECK_PLATE_W / 2, fx + DECK_PLATE_W / 2,
                    y0, y1, 0, RELIEF_Z)
        plate = safe_fillet(plate, plate.edges().filter_by(Axis.Y)
                            .group_by(Axis.Z)[-1], 0.3)   # 1.4 cannot exist on 0.8
        lad += plate
    return lad


def rear_tie():
    return half_round(SPAN, TIE_R, holes=(24.0, 3.0), engage=ENGAGE)


# ------------------------------------------------------- rail hardware ------
def teardrop(r, depth):
    """Round hole with a 45-degree gabled roof, apex along local +Y.

    A horizontal bore in an upright print has an unsupported ceiling; the
    gable lets each layer of the crown lean on the one below. The frames
    print on their side so their pilots stay plain cylinders -- this is only
    for holes drilled into parts that print standing up.
    """
    k = r / math.sqrt(2.0)
    roof = make_face(Polyline((-k, k), (0.0, r * math.sqrt(2.0)), (k, k),
                              close=True))
    return extrude(Circle(r), depth) + extrude(roof, depth)


def buttress(bx):
    """Integral tray buttress backing the DIN rail at X=bx. ASSEMBLY coords;
    rear_tray() shifts it into its own frame before the union.

    The blade is what Mk2's rail_strut was trying to be: front face on the
    post plane -- the same plane the end frames present -- carrying the
    identical interface (shoulder rib, gasket pocket, two M3 pilots at the
    16 mm couple). But its root is moulded into the tray floor, rear wall and
    its own divider, so the tray box (288 mm of closed 1.6 walls) is the
    shear panel that braces it in X -- the job Mk2 did by letting the walls
    pinch a separate blade through slots. Above the rim it is a fixed-root
    cantilever only ~30 mm tall: I = 25*6^3/12 ~ 450 mm4, so 20 N sideways at
    rail height moves the land ~0.17 mm.
    """
    toe_y, toe_z = post_point(BUT_TOE_S)
    top_y, top_z = post_point(BUT_TOP_S)
    # 45-degree rake from the tray rim to the toe -- exactly at the print
    # limit by construction (rise == run), so the blade grows straight out of
    # the tray with no support. Root overlaps TRAY_H by 0.5 for a solid union.
    rake_y = toe_y + (toe_z - (TRAY_H - 0.5))
    profile = [
        (toe_y, toe_z),
        (top_y, top_z),
        # 3 mm cap, then a rear face that leans ~6 degrees off vertical --
        # its top is FORWARD of its bottom, so it faces upward and prints.
        (top_y + 3.0, top_z),
        (TRAY_Y1, 41.0),
        (TRAY_Y1, TRAY_H - 0.5),
        (rake_y, TRAY_H - 0.5),
    ]
    face = make_face(Polyline(*profile, close=True))
    b = Pos(bx - BUTTRESS_T / 2, 0, 0) * \
        (Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(face, BUTTRESS_T)))

    # Root: the 1.2 divider thickens to the blade's full 6.0 over the rear
    # 16.5 mm and runs floor to rim, so wall, divider and blade are one
    # moulding. Costs ~2.3 cm3 of cells 2 and 5; resealing the slot-breached
    # rear wall gives most of that back.
    b += box(bx - BUTTRESS_T / 2, bx + BUTTRESS_T / 2,
             rake_y, TRAY_Y1, 0.0, TRAY_H)

    # No tail. The blade stops at the tray's rear wall, and the wall itself
    # meets the tie rod along its whole length (see TRAY_Y1 and the seat cut
    # at the end of rear_tray). What used to hang off the back here was a
    # 6 x 18 x 11.5 slab with a V-notch in it, holding the rod on two 6 mm
    # tangent lines -- a bracket doing badly what the wall now does for the
    # full 288 mm, for less material and one fewer feature.

    # Root gussets, riding the rear wall top so their undersides are
    # supported -- NOT the 6 mm-thick pair first sketched, which would have
    # hovered over the open cells either side. 45 degrees, 8 mm run.
    for side in (-1.0, 1.0):
        xf = bx + side * (BUTTRESS_T / 2 - 0.3)
        tri = make_face(Polyline((xf, 13.4), (xf + side * 8.3, 13.4),
                                 (xf, 21.7), close=True))
        b += Pos(0, TRAY_Y1, 0) * (Rot(90, 0, 0) * extrude(tri, 1.7))

    # Lightening window -- the end frames' own grammar, one closed profile
    # with the mass taken back out. Gabled apex-up (sides ~57 degrees): the
    # tray prints upright, and a horizontal window ceiling here would be an
    # unsupported overhang. Small because the blade is only ~16 mm deep at
    # this height and the lower pilot bore dives diagonally through the
    # belly: ~5 mm to the rake and rear faces, >6 mm to either pilot bore.
    # R1.2, not the frames' R4: at this size a soft fillet rounds the gable
    # into an anonymous drill hole (caught in the bay render, iteration 2).
    win = make_face(Polyline((129.5, 17.5), (132.75, 23.0), (136.0, 17.5),
                             close=True))
    win = safe_fillet(win, win.vertices(), 1.2)
    b -= Pos(bx - BUTTRESS_T / 2 - 1.0, 0, 0) * \
        (Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(win, BUTTRESS_T + 2.0)))

    # Top interface, verbatim from Mk2's rail_strut, with two print-pose
    # changes: the shoulder rib grows from the face on a 45-degree chamfer
    # (its square underside was a 37-degree overhang in this pose -- the
    # frames get away with it because they print on their side), and the
    # pilots are teardropped. The chamfer costs ~0.9 mm of shoulder-face
    # height; the screws and the frames' square shoulders do the locating,
    # this rib is belt and braces.
    s0 = RAIL_WEB_W / 2 + RAIL_FIT
    rib = make_face(Polyline((s0, -0.5), (s0, 0.3), (s0 + 2.3, 2.6),
                             (s0 + 2.4, 2.6), (s0 + 2.4, -0.5), close=True))
    b += to_post(Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(rib, BUTTRESS_T)),
                 x_centre=bx - BUTTRESS_T / 2)
    pad = box(0.5, BUTTRESS_T - 0.5, -(RAIL_PAD_S / 2 + 0.15),
              RAIL_PAD_S / 2 + 0.15, -RAIL_PAD_D, 0.1)
    b -= to_post(pad, x_centre=bx - BUTTRESS_T / 2)
    # 10 deep, not Mk2's 24: an M3x10 through web and gasket engages ~7 mm,
    # and the shorter bore keeps its far end 6 mm clear of the window above.
    for dy in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
        b -= to_post(Pos(0, dy, -9.0) * teardrop(1.25, 10.0), x_centre=bx)
    return b


# ------------------------------------------------------------- rear tray ----
def rear_tray(w=None, cells=TRAY_CELLS):
    """Divided tray filling the dead space behind the post.

    Replaces the five bay trays, which were a 50 x 10 x 9 mm pocket each
    because they were squeezed into the 11.6 mm of free floor between the rear
    deck rail and the post. This sits behind the post instead, where nothing
    was competing for the volume, and gets 50 mm of depth instead of 14.6.
    """
    w = SPAN if w is None else w
    d = TRAY_Y1 - TRAY_Y0
    t = box(0, w, 0, d, 0, TRAY_H)
    t = safe_fillet(t, t.edges().filter_by(Axis.Z), 3.0)

    cav = box(TRAY_WALL, w - TRAY_WALL, TRAY_WALL, d - TRAY_WALL,
              TRAY_FLOOR, TRAY_H + 1)
    t -= safe_fillet(cav, cav.edges().filter_by(Axis.Z), 2.0)

    # Dividers land ON the buttress stations, not at an even pitch that misses
    # them by 2.6 mm. In Mk2 the divider and the strut slot fought over the
    # same station; now the two are literally the same wall -- the buttress is
    # the rear half of that divider, made 6 mm thick and continued upward.
    stations = sorted(x - FRAME_T for x in BUTTRESS_X)
    edges = [TRAY_WALL] + stations + [w - TRAY_WALL]
    walls = stations + [(a + b) / 2 for a, b in zip(edges[:-1], edges[1:])]
    for x in walls:
        div = box(x - 0.6, x + 0.6, TRAY_WALL, d - TRAY_WALL, TRAY_FLOOR,
                  TRAY_H - 1.5)
        t += safe_chamfer(div, div.edges().filter_by(Axis.Y)
                          .group_by(Axis.Z)[-1], 0.5)

    # Wire passthroughs: one stadium slot per cell, straight through BOTH
    # long walls, so a board can live in a cell with its leads out the front
    # to the deck and its power lead out the back of the bench. 13 x 7
    # passes a USB-C or micro-B overmold; the flat over each slot is a ~6 mm
    # bridge, the same span the boss pockets already print. z 5..12 rides
    # clear over the 4.5 wall-hugging foot bosses (at 3.5 the outer slots
    # nicked their corners) and still leaves 2.5 of wall below the rim.
    bounds = sorted([TRAY_WALL] + walls + [w - TRAY_WALL])
    for a, b in zip(bounds[:-1], bounds[1:]):
        cx = (a + b) / 2
        slot = box(cx - PASS_W / 2, cx + PASS_W / 2, -1, d + 1,
                   5.0, 5.0 + PASS_H)
        t -= safe_fillet(slot, slot.edges().filter_by(Axis.Y),
                         PASS_H / 2 - 0.1)

    t -= rim_cutter(0, w, 0, d, TRAY_H, 3.0)

    # The buttresses go on AFTER the rim cutter -- it planes off everything
    # above TRAY_H - 0.75 across the whole footprint, which would sever a
    # 53 mm blade at its root. No slots anywhere: Mk2's slot loop breached the
    # rear wall and opened cells 2 and 5 to the back; the wall is closed again.
    # Bottom chamfer BEFORE the buttresses, tails and bosses join: applied
    # last, the perimeter edge chains into their blend surfaces and OCCT
    # drops the whole operation (the review's dropped 0.5). The features
    # added below keep square bed edges -- small, and hidden under the tray.
    t = safe_chamfer(t, t.edges().group_by(Axis.Z)[0], 0.5)

    for bx in BUTTRESS_X:
        t += Pos(-FRAME_T, -TRAY_Y0, 0) * buttress(bx)

    # Floor bosses with standard TPU pockets, 0.1 shy of the frame-pad plane
    # (see TRAY_FOOT_SHY). Roof of each pocket bridges 6 mm, same as the deck
    # rails do today.
    for fx in TRAY_FOOT_X:
        # Outer bosses extend INTO the end walls so boss and wall are one
        # moulding -- a plinth growing from the wall, not an island.
        b0 = 0.0 if fx < 50 else fx - 10.0
        b1 = w if fx > w - 50 else fx + 10.0
        boss = box(b0, b1, TRAY_FOOT_Y - 6.0, TRAY_FOOT_Y + 6.0,
                   0, TRAY_BOSS_T)
        t += safe_fillet(boss, boss.edges().filter_by(Axis.Z), 2.0)
        t -= Pos(0, 0, TRAY_FOOT_SHY) * foot_pocket(fx, TRAY_FOOT_Y)

    # Seat for the rear tie, cut LAST so the buttress roots get it too: the
    # rod's own section grown by TIE_FIT, swept the full width. Cutting the
    # mating part rather than modelling a socket makes the seat conforming
    # by construction -- there is no socket geometry to keep in sync with
    # the rod, and no fit to get wrong beyond the one number.
    ry = TIE_Y - TRAY_Y0
    seat = Pos(w / 2, ry, 0) * Rot(0, 90, 0) * \
        Cylinder(TIE_R + TIE_FIT, w + 40)
    seat -= box(-20, w + 20, ry - 20, ry + 20, -20, 0)   # half-round: the
    t -= seat                                            # rod's flat is the bed
    return t


# ------------------------------------------------------------- hardware -----
# Fourteen M3 self-tappers, two kinds -- each forced by geometry.
# Six BAR-END screws, M3 x 12 SOCKET HEAD CAP, black-oxide alloy steel
# (ISO 4762): a countersink there broke through the plate's bottom edge
# (the tie screw line is only 3.15 above it), and a proud head on the outer
# face collides with nothing since the foot pads moved to 30/132.
# Engagement 12 - 6 plate = 6 mm in a 13 mm pilot. Cap screws, not pan
# heads, because the side bin holds on to these six heads MAGNETICALLY:
# alloy steel grips far harder than plated mild steel (the user's magnet
# said so), and the cap's flat top meets the disc as a plane, not a dome.
# Head 5.5 dia x 3.0 tall -- BAR_HEAD_T is what the bin's pockets, the
# screws.py clearance gate and the render props all read.
BAR_HEAD_T = 3.0
# Eight RAIL screws, M3 x 12 socket head CAP, heads sunk in 6.0 x 3.2
# counterbores (bench.din_rail) so they sit 0.2 below the face the clips
# slide on. Seated on the counterbore floor the screw spends 4.2 in the
# rail and reaches ~7.8 into the pilot -- inside both the 11 mm frame and
# the 9 mm buttress pilots, so ONE screw serves all 14 structural joints.
# (Was M3 x 16 countersunk at the frames and x14 at the buttresses.)
SCREW_L = 12.0
RAIL_SCREW_L = 12.0


def m3_screw(length=SCREW_L, head="pan"):
    """M3 self-tapper, simplified to what the eye needs.

    Head at/below Z=0, shank rising +Z -- so Rot(0, 90, 0) lays it along +X
    with the head on the face it enters, and Rot(180, 0, 0) sinks it straight
    down. "csk" carries its flat top at Z=0, flush with the surface; "pan"
    stands 2.2 proud. Not a printed part: the screw IS the peg, in steel,
    which is why the printed parts only ever show a pair of holes.
    """
    if head == "csk":
        h = Pos(0, 0, 0.85) * Cone(2.75, 1.5, 1.7)
    elif head == "cap":
        # socket head cap: flat-topped cylinder, hex socket suggested
        h = Pos(0, 0, -BAR_HEAD_T / 2) * Cylinder(2.75, BAR_HEAD_T)
        h = safe_chamfer(h, h.edges().group_by(Axis.Z)[0], 0.4)
        h -= Pos(0, 0, -BAR_HEAD_T - 1) * extrude(
            RegularPolygon(1.45, 6), 2.8)
    else:
        h = Pos(0, 0, -1.1) * Cylinder(2.75, 2.2)
        h = safe_chamfer(h, h.edges().group_by(Axis.Z)[0], 0.6)
    return h + Pos(0, 0, length / 2) * Cylinder(1.5, length)


# ------------------------------------------------------------- side bin -----
SIDEBIN_FOOT_Y = (20.0, 136.0)            # its two TPU stations. 136, not
                                          # 144: the tie screw at y=149 sweeps
                                          # a driver path to y 146.25, and the
                                          # pad at 144 reached 147 -- screws.py
                                          # flagged the approach BLOCKED
# (SIDEBIN_HOOKS, the saddle tongues over the frame, were retired 2026-10-07: see side_bin().)
# THE connection: three N52 neodymium discs (D6 x 2, the user's stock)
# pressed into the bin's back wall, one dead over each zinc-plated steel
# bar-end pan head. The bin drops on and SNAPS -- self-centring, silent,
# no visible hardware, no notches in the frame. Lifting straight off
# shears the magnets free: that is the removal gesture. This replaced a
# hook-slide-click of T-studs in frame-cut J-slots: mechanically honest
# (the workflow verified it) but four features doing one job, with slots
# carved into the frame's clean side face -- the accretion the user
# called out. One mechanism, reusing steel that is already there.
# BOM consequence: the six bar-end screws MUST be zinc-plated carbon
# steel (DIN 7985) -- stainless is barely magnetic and would hold nothing.
MAGNET_D, MAGNET_T = 6.0, 2.0
# Pocket oversize, per material and pocket kind, each from a gauge:
#   MAGNET_FIT       0.25  PLA, flat pocket (rail caps) -- plate 02, 2026-09-19
#   MAGNET_FIT_CELL  0.10  PETG, flat floor cell (side tray / bin cells) -- plate 03,
#                          2026-10-05: 6.10 held, the first PETG reading
#   MAGNET_FIT_WALL  0.40  PETG, sideways seat behind a screw-head pocket (bin and
#                          tray back walls) -- plate 03: 6.25 would not sit down,
#                          6.40 right, 6.55 "just flops out"
# PETG floor pockets come out larger than PLA's and the sideways seats
# smaller, so one number for all three was always going to miss two.
MAGNET_FIT_CELL = 0.10
MAGNET_FIT_WALL = 0.40
MAGNET_FIT = 0.25         # pocket oversize: printed holes arrive 0.1-0.3
                          # under, so D6.25 prints as a snug press
MAGNET_SKIN = 0.6         # PETG between the magnet seat and the cavity --
                          # the bin's inside face stays unbroken
# The HEAD discs (three per side wall) go in sideways through the head
# pockets and end up sandwiched between the skin and a steel screw head --
# captive by assembly, nothing to do.
#
# The CELL discs are PAUSE-AND-INSERT: the pocket opens UPWARD, the print
# pauses, the disc drops in, and the next layers seal it under. Fully
# encapsulated, so there is no press fit to get right, nothing to fall out
# of the underside, and no CA. It also puts the disc CLOSER to the screws
# it holds (1.7 mm of plastic, against 2.5 when it was inserted from
# below), so it pulls harder.
#
# Two rules make the pause safe, and both are geometry, not procedure:
#   * the pocket is MAGNET_T + 0.2 deep, so a seated disc's top sits 0.2
#     BELOW the pause plane. The nozzle never sweeps at disc height.
#   * the disc is buried, not surfaced: MAG_PAUSE_Z is below the finished
#     floor, so the resume layers bridge over it.
# Worth knowing on this machine: the H2S ships a HARDENED STEEL nozzle,
# which unlike brass is ferromagnetic -- a proud disc could jump to it.
# The 0.2 recess is what makes that impossible. N52 is also the most
# heat-sensitive neodymium grade (~80 C), so keep the chamber at 0.
MAG_INSERT_Z = 1.0                        # pocket floor, above the bed face
                                          # (1.0, not 0.8: check.py wants a
                                          # 0.9 minimum plate under a void)
MAG_POCKET_D = MAGNET_T + 0.2             # 0.2 recess under the pause plane
MAG_PAUSE_Z = MAG_INSERT_Z + MAG_POCKET_D  # 3.0 -- pause the print here
SIDEBIN_BOSS_T = 4.5                      # local floor under each pocket

# HEAD DISCS, BURIED (2026-10-09). The side tray's and bin's three head discs
# used to press in sideways through the head pocket after printing -- awkward,
# and the user wanted the parts to "just snap on". Now each sits in a closed
# slot just past the head pocket, dropped in ON EDGE at a second pause and
# sealed over. Plate 10m proved the numbers: a ONE-LINE skin (0.45) docks the
# coupon firmly on a real head and holds the disc with no rattle (a single
# line prints slightly into the slot and takes up its play); the two-line
# 0.85 skin left the disc rattling. Pull at 0.3 head clearance + 0.45 skin is
# ~29 % of contact (image-method model) -- plenty with three discs and the
# parts' weight on their own TPU feet (user, 2026-10-09). Rattle is NOT
# acceptable ("fit and finish"), so these slot sizes are the coupon's, exactly.
HEAD_VOID = BAR_HEAD_T + 0.3              # screws.py wants >= 0.25 over the head
HEAD_SKIN = 0.45                          # one wall line: proven, no rattle
HEAD_SLOT_W = MAGNET_T + 0.3              # as plate 10m
HEAD_SLOT_L = MAGNET_D + MAGNET_FIT_WALL  # 6.4, as plate 10m
HEAD_SLOT_H = MAGNET_D + 0.4              # 6.4, as plate 10m
HEAD_SLOT_TOP = 7.0                       # bench z; the head pause is the first
                                          # layer top at or above this
SIDE_BW = HEAD_VOID + HEAD_SKIN + HEAD_SLOT_W + MAGNET_SKIN   # back wall, 6.65
# Head pockets: a ROUND top over each head, open at the bottom (user,
# 2026-10-09: "nice circles that would fit over the screws"). A closed circle
# cannot work: the head's centre is only 3.15 above the part's underside, so
# any clearance circle breaks through the bottom face -- and the parts drop
# on and lift off vertically, which needs the open bottom. Same 0.6 radial
# clearance the square pocket had. Its arch prints like a 6.7 horizontal hole.
HEAD_POCKET_R = 2.75 + 0.6


def head_pocket(yh):
    """U-shaped pocket over one bar-end head: round top, open bottom."""
    hz = END_SCREW_Z
    u = box(-1, HEAD_VOID, yh - HEAD_POCKET_R, yh + HEAD_POCKET_R, -1.2, hz)
    return u + Pos((HEAD_VOID - 1) / 2, yh, hz) * Rot(0, 90, 0) * Cylinder(
        HEAD_POCKET_R, HEAD_VOID + 1)


def head_slot(yh):
    """Closed slot for one head disc, on edge, open UPWARD to HEAD_SLOT_TOP
    until the pause; HEAD_SKIN of PETG between it and the head pocket."""
    x0 = HEAD_VOID + HEAD_SKIN
    return box(x0, x0 + HEAD_SLOT_W, yh - HEAD_SLOT_L / 2, yh + HEAD_SLOT_L / 2,
               HEAD_SLOT_TOP - HEAD_SLOT_H, HEAD_SLOT_TOP)
SIDEBIN_CAV = 28.0                        # cavity width; with the walls it sets
                                          # the bin's W, and so where its pads sit
# Screw cells at both ends of the trough: divider positions (each wall
# starts here, TRAY_WALL thick) and the magnet centre in each cell, placed
# over the plinth (front plinth y 14..26, rear 130..142).
SIDEBIN_DIVIDERS = (27.0, 129.8)
SIDEBIN_CELL_MAGNET_Y = (20.0, 137.0)
SIDEBIN_WINDOW_Y = (47.0, 79.0, 111.0)    # outer-wall windows, mid-trough only


def side_bin():
    """Long parts trough for the RIGHT face -- it hangs on nothing.

    The three bar-end pan heads sit at Z = 3.15, far too low for any keyhole
    to slide over, so the bin does not try: it stands on its own two TPU
    feet -- the standard pad in the standard pocket -- which puts it on
    EXACTLY the bench's stance (bin body FOOT_PROUD above the desk, level
    with the frames), and three open-bottom pockets in its back wall drop
    straight down over the heads. The pockets locate the bin fore-aft and
    swallow the heads completely -- a 1.8 mm outer skin hides them from
    view -- and lifting the bin off needs no tools. Clearance to every head
    is gated in screws.py, not assumed. Local z=0 is BENCH zero (pads reach
    to -FOOT_PROUD); placed at Pos(FR_W, 0, 0). A left-side twin is
    mirror(part, Plane.YZ), same rule as the end frames.
    """
    # A low LIP, not a box: height and gauge come straight from the rear
    # tray (TRAY_H, 1.6 walls and floor), so the two storage rims read as
    # one family and nothing towers over the deck. Only the back wall stays
    # thick -- it is what swallows and hides the screw heads.
    # Back wall = head void 2.4 + skin + magnet: 5.0. Everything the wall
    # does happens inside it; the cavity face is plain.
    BW = SIDE_BW                           # head pocket + skin + slot + skin
    CAV, FW = SIDEBIN_CAV, TRAY_WALL       # cavity, front wall
    W, H = BW + CAV + FW, TRAY_H
    L0, L1 = 2.0, 163.0
    b = box(0, W, L0, L1, 0, H)
    # Stadium nose: the two FRONT corners sweep at R15, so the tray reads
    # as a scoop flowing around the bench corner (chosen from the rendered
    # form studies over a flared wall and a truss-windowed wall). The back
    # corners stay square -- that face seats against the bench.
    b = fillet(b.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], 15.0)
    cav = box(BW, BW + CAV, L0 + TRAY_WALL, L1 - TRAY_WALL,
              TRAY_FLOOR, H + 1)
    cav = fillet(cav.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], 13.0)
    cav = fillet(cav.edges().filter_by(Axis.Z), 2.0)
    b -= cav
    # elephant-foot ease BEFORE the pockets, tray-style -- a chamfer on a
    # foot-pocket rim would loosen FOOT_FIT
    b = safe_chamfer(b, b.edges().group_by(Axis.Z)[0], 0.5)
    # Lightening windows in the outer wall -- the end frame's truss-of-holes
    # grammar, chosen from the rendered form studies. Upper half only, and
    # only over the long middle trough (never over the screw cells), so
    # nothing lying on the floor can find its way out.
    for wy in SIDEBIN_WINDOW_Y:
        win = box(W - FW - 1, W + 1, wy - 14.0, wy + 14.0, 6.5, H - 2.5)
        win = safe_fillet(win, win.edges().filter_by(Axis.X), 2.4)
        b -= win
    # ...and one in the rear end wall, same top line. Its sill is at 8.5,
    # not 6.5: this wall backs the rear screw cell, whose floor is the 4.5
    # plinth, so the sill stays 4 mm above anything lying in the cell.
    win = box(BW + 4.0, W - FW - 4.0, L1 - FW - 1, L1 + 1, 8.5, H - 2.5)
    win = safe_fillet(win, win.edges().filter_by(Axis.Y), 1.6)
    b -= win

    # Floor bosses with standard TPU pockets, rear_tray's grammar: a plinth
    # band tied into the front wall, held 0.8 clear of the back wall's
    # inner face so it can never re-fill the head pockets cut below (x
    # <= 2.8), and overlapped 0.9 into the front wall -- kiss-tangent
    # unions are the touching-solid booleans OCCT fails on.
    for fy in SIDEBIN_FOOT_Y:
        boss = box(BW - 0.8, W - FW + 0.9, fy - 6.0, fy + 6.0,
                   0, SIDEBIN_BOSS_T)
        b += safe_fillet(boss, boss.edges().filter_by(Axis.Z), 2.0)
        b -= foot_pocket(W / 2, fy)

    # Screw cells. The two foot plinths already thicken the floor to 4.5 at
    # each end of the trough, which is exactly what a magnet seat needs: a
    # divider walls each end off into a small cell, and an N52 disc sits
    # flush in the plinth floor -- the screws you are working with land
    # there and stay put. The disc is offset in x from the TPU pocket
    # beneath the plinth (x 16..22) so the two voids never meet; 2.5 mm of
    # plinth stays under it. The long middle stays open for tools and wire.
    for yd in SIDEBIN_DIVIDERS:
        b += box(BW - 0.5, W - FW + 0.5, yd, yd + TRAY_WALL, 0, H - 1.0)
    # Cell magnets: UPWARD-opening, pause-and-insert, sealed under (see the
    # MAG_* constants). The pocket used to open onto the underside and rely
    # on a press fit; a disc could drop out of a loose one, and the bin's
    # bottom face carried two visible holes. Buried, neither is possible.
    # The seat stays at the CAVITY'S FAR side (x = W - FW - 4.5): the TPU
    # foot pocket runs 16 mm ALONG the bin (x 9.75..25.75), and the first
    # placement at x = 9.9 bored straight into it (DFM review).
    for my in SIDEBIN_CELL_MAGNET_Y:
        b -= Pos(W - FW - 4.5, my, MAG_INSERT_Z) * Cylinder(
            (MAGNET_D + MAGNET_FIT_CELL) / 2, MAG_POCKET_D,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

    # Head pockets + magnet seats, one stack per bar-end screw. From the
    # bench face inward: a pocket that swallows the pan head (open at the
    # bottom -- that is how the bin drops on; gabled roof, ridge along the
    # pocket, so it prints as 45s on this vertical face), then MAGNET_SKIN
    # of PETG, then the magnet seat opening into the CAVITY. The disc is
    # pressed in from inside the bin; its own pull then seats it against
    # the skin, 0.2 + skin = 0.8 mm off the steel. Same y as the head; the
    # disc rides 0.55 higher than the head axis so 0.6 of floor stays under
    # it (coaxial, its rim would have broken through the bin's bottom face
    # by 0.03) -- a 6 mm disc over a 5.5 mm head barely notices.
    for y in (FRONT_AXIS, REAR_AXIS, TIE_Y):
        b -= head_pocket(y)
        b -= head_slot(y)

    # No rolled edge and no tongues over the frame any more (removed
    # 2026-10-07, the user: "I thought when we added the magnets we got rid
    # of this bucktooth over the top piece"). They were the pre-magnet
    # location and a "mechanical backup" that nothing needed: the bin's
    # weight is on its own two feet, the three magnets over the bar-end
    # heads locate it and hold it to the face, and the return was the only
    # feature on this part that needed painted support (8 mm cantilever).

    # Relief over the end frame's side foot pads: their TPU FLANKS sit
    # FOOT_FIT proud of the through-thickness pockets over the pads' full
    # 16 mm length (the first relief assumed the short side and left
    # 1.7 mm3 of contact -- measured, twice). A flush bin face would ride
    # on rubber instead of plate; 0.5 deep is void, not a fit.
    for fy in FR_FOOT_Y:
        b -= box(-1, 0.5, fy - 8.5, fy + 8.5, -1.2, 4.5)
    return b


# ------------------------------------------------------------- rail cap -----
def magnet_discs():
    """Every N52 D6x2 disc on the bench, in ASSEMBLY coordinates.

    Bought hardware, not printed -- these go into the assembly dict only,
    never into the printable parts, so the gates and the build sheet are
    unaffected.

    Each disc is built in its HOST part's local frame and then given that
    host's exact placement transform, so a disc cannot drift away from its
    pocket when a host moves. Every one is modelled at the face its working
    pull drives it onto, which is where it actually ends up once the bench
    is together -- the same rule the pockets are cut to.
    """
    disc = Cylinder(MAGNET_D / 2, MAGNET_T,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))
    wall = Rot(0, 90, 0) * disc          # axis along +X, for the back walls
    BW = SIDE_BW
    # head discs: against the skin (their pull is toward the head), resting
    # on the slot floor
    hx = HEAD_VOID + HEAD_SKIN
    mz = HEAD_SLOT_TOP - HEAD_SLOT_H + MAGNET_D / 2
    HEADS = (FRONT_AXIS, REAR_AXIS, TIE_Y)
    out = []

    # --- side bin, placed at Pos(FR_W, 0, 0) --------------------------------
    W_BIN = BW + 28.0 + TRAY_WALL
    for my in SIDEBIN_CELL_MAGNET_Y:                 # sealed in at the pause
        out.append(Pos(FR_W, 0, 0) *
                   Pos(W_BIN - TRAY_WALL - 4.5, my, MAG_INSERT_Z) * disc)
    for y in HEADS:                                  # seated against the skin
        out.append(Pos(FR_W, 0, 0) * Pos(hx, y, mz) * wall)

    # --- side tray, built right-handed and MIRRORED onto the left face ------
    y = 2.0 + TRAY_WALL
    bounds = []
    for ln in TRAY_CELLS:
        bounds.append((y, y + ln))
        y += ln + TRAY_WALL
    bounds.append((y, 163.0 - TRAY_WALL))
    for a, b in bounds:
        out.append(mirror(
            Pos(BW + TRAY_W_CAV / 2, (a + b) / 2, MAG_INSERT_Z) * disc,
            Plane.YZ))
    for yh in HEADS:
        out.append(mirror(Pos(hx, yh, mz) * wall, Plane.YZ))

    # --- rail caps, in the shroud windows on the rail's top face ------------
    for sy in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
        d = Pos(RAIL_END_ST, sy, 0) * disc
        out.append(to_post(d, x_centre=0.0, n=RAIL_TOP_Z))
        out.append(Pos(FR_W, 0, 0) * mirror(
            to_post(d, x_centre=0.0, n=RAIL_TOP_Z), Plane.YZ))

    return {f"asm_mag{i}": m for i, m in enumerate(out)}


def rail_cap(fit=None):
    """Cover for the two rail screws at each end frame.

    The mortise shroud's roof is windowed over the rail's web band so the
    two M3x12 cap screws can be driven; their heads sit 0.2 below the
    rail's top face, in counterbores, 2.65 below the shroud's roof line. This cap drops into
    that window and its top comes flush with the roof, so the shroud reads
    as one solid socket with nothing in it. Two N52 discs in its underside
    sit directly on the two steel heads (pocket floor 0.45 = the printed
    top skin), so the cap pulls itself down onto the screws it hides. Lift
    with a nail to service. Same part both ends (symmetric in x and s).
    Local frame: x along the rail from the shroud's outer end, y = s
    across the rail, z up from the rail's top face. Prints top face down.
    """
    f = MAGNET_FIT if fit is None else fit
    L, S, T = 12.0, 25.0, RAIL_FIT_MORTISE + 2.2   # window is 12 x 25 x 2.45
    c = box(0.15, L - 0.15, -S / 2 + 0.15, S / 2 - 0.15, 0, T)
    c = safe_chamfer(c, c.edges().group_by(Axis.Z)[-1], 0.3)
    for sy in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
        c -= Pos(RAIL_END_ST, sy, -1) * Cylinder(
            (MAGNET_D + f) / 2, MAGNET_T + 1,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    return c


# ------------------------------------------------------------ side tray -----
# Left-side screw tray: half the bin's width, half its height, no feet (it
# hangs on the three head magnets like the skid did), five cells of three
# sizes for sorting, one flush N52 disc in every cell floor.
# 18.0, not 10.4 (user, 2026-10-09): 10.4 held one M3 head across; the user
# wants two to three side by side (pan head 5.6 -> 3 x 5.6 + slack), still
# well short of the bin's 28.
TRAY_W_CAV = 18.0                         # cavity width
TRAY_LIP_L = 0.85                         # outer rim: two 0.42 wall lines
TRAY_H_L = 8.0
# 4.0, not 3.0: the cell discs are now buried instead of opening onto the
# underside, and a sealed disc needs 1.0 of floor under it + 2.2 of pocket
# + 0.8 of seal over it = 4.0. The seal was 0.6 (3 layers at 0.2) -- the
# thinnest sealed span in the build, and the one thing standing between a
# screwdriver and a magnet, so it gets a fourth layer for ~0.6 cm3. Cells
# go from 5.0 to 4.0 deep, still more than a run of M3s needs.
TRAY_FLOOR_L = 4.0
# Two TPU stations. The tray had NONE -- it hung off its three magnets
# alone and its bare underside met the desk, while the bin next to it
# stood on rubber.
#
# NOT the bin's (20, 136): this tray's five cell magnets sit at y 14.6,
# 38.2, 65.8, 97.4 and 137.7, and a 16 x 6 foot pocket plus its 4.5 boss
# needs 7.1 mm of clearance from a magnet centre. 20 and 136 land almost
# exactly on the first and last of them -- the boss refilled two pockets
# and the magnet probe caught it (57% and 23% embedded in plastic).
# 26 and 120 sit in the gaps, clear of the head pockets at 10 / 83.4 / 149
# as well.
TRAY_FOOT_Y_L = (26.0, 120.0)
TRAY_BOSS_T_L = 4.5                       # local floor: 3.2 pocket + 1.3
TRAY_CELLS = (22.0, 22.0, 30.0, 30.0)     # front to back; the last cell
                                          # takes what is left (~47)


def side_tray():
    """Left screw tray -- the skid, grown a few cells.

    Same idea as the skid (hides the three heads magnetically, hangs 1 mm
    off the desk, lifts straight off), but 26.3 wide and 8 tall with five
    compartments -- 22 / 22 / 30 / 30 / ~47 mm, a run of sizes for sorting
    -- each with an N52 disc flush in its floor so the screws stay where
    they are dropped. Nose is a full semicircle (R 8.95), so it reads as
    the bin's small sibling. Built right-handed like the bin and MIRRORED
    into place on the left frame.
    """
    BW = SIDE_BW
    W, H = BW + TRAY_W_CAV + TRAY_WALL, TRAY_H_L
    L0, L1 = 2.0, 163.0
    t = box(0, W, L0, L1, 0, H)
    # W/2 - 0.95, not W/2: two fillets meeting exactly at the centreline is
    # the tangent case OCCT rejects; 0.95 of flat between them is invisible.
    # (Was a literal 8.0 when W was 17.9 -- tied to W now it has grown.)
    t = safe_fillet(t, t.edges().filter_by(Axis.Z).group_by(Axis.X)[-1],
                    W / 2 - 0.95)
    # The outer wall is only TRAY_LIP_L thick at the rim (user, 2026-10-09:
    # "take it all the way to the edge so there is only a thin lip"): the
    # cavity runs out to it, and the scoop below thickens the wall again
    # within a millimetre or two of the rim.
    xo = BW + TRAY_W_CAV + TRAY_WALL - TRAY_LIP_L
    cav = box(BW, xo, L0 + TRAY_WALL, L1 - TRAY_WALL, TRAY_FLOOR_L, H + 1)
    # Cavity corner radius = the body's corner radius - TRAY_WALL: the wall
    # then runs from TRAY_WALL at the ends to TRAY_LIP_L along the side,
    # never thinner. A fixed 7.0 broke through the nose once the side wall
    # went thin (render, 2026-10-09).
    cav = safe_fillet(cav, cav.edges().filter_by(Axis.Z).group_by(Axis.X)[-1],
                      W / 2 - 0.95 - TRAY_WALL)
    t -= cav
    t = safe_chamfer(t, t.edges().group_by(Axis.Z)[0], 0.5)
    # SCOOP (user, 2026-10-09: "scoop the outside ledge so I can slide screws
    # out"): a cove along the inside of the OUTER long wall, the Gridfinity
    # scoop -- a finger sweeps screws up the curve and over the lip. Full
    # depth (floor to rim) through the middle cells, TAPERED down over the
    # two end cells (user: "taper the ends so only a small part of the last
    # [cells] are scooped rather than make an awkward fall off / ledge"), so
    # it dies out into the rounded ends instead of stopping on a cliff.
    # Clipped to the cavity.
    R = H - TRAY_FLOOR_L
    F = TRAY_FLOOR_L
    # round the rim's inside edge first, while it is still one clean edge
    t = safe_fillet(t, t.edges().filter_by(Axis.Y).filter_by(
        lambda e: abs(e.center().Z - H) < 0.01 and abs(e.center().X - xo) < 0.05), 0.3)

    def cove_profile(y, r):
        """The corner fill under a radius-r cove, as a face in the plane y."""
        c = (xo - r, F + r)
        m = (c[0] + r * math.cos(math.radians(45)), c[1] - r * math.sin(math.radians(45)))
        w = Wire([Edge.make_line((xo - r, F), (xo, F)),
                  Edge.make_line((xo, F), (xo, F + r)),
                  Edge.make_three_point_arc((xo, F + r), m, (xo - r, F))])
        return Pos(0, y, 0) * (Rot(90, 0, 0) * Face(w))

    y0, y1 = L0 + TRAY_WALL, L1 - TRAY_WALL
    first_div = y0 + TRAY_CELLS[0]                    # end of the first cell
    last_div = y0 + sum(TRAY_CELLS) + len(TRAY_CELLS) * TRAY_WALL   # nose cell starts
    stations = [(y0 - 1.0, 0.6), (first_div - 4.0, R), (last_div + 12.0, R),
                (y1 + 1.0, 0.6)]
    cove = None
    for (ya, ra), (yb, rb) in zip(stations, stations[1:]):
        seg = loft([cove_profile(ya, ra), cove_profile(yb, rb)], ruled=True)
        cove = seg if cove is None else cove + seg
    t += cove & cav

    # cells: dividers front to back, a magnet pocket centred in each
    y = L0 + TRAY_WALL
    bounds = []
    for ln in TRAY_CELLS:
        bounds.append((y, y + ln))
        y += ln
        t += box(BW - 0.5, W - TRAY_WALL + 0.5, y, y + TRAY_WALL, 0, H - 0.8)
        y += TRAY_WALL
    bounds.append((y, L1 - TRAY_WALL))
    # TPU feet. Bosses first (the floor is only 3.8 and the pocket is 3.2),
    # spanning the cavity width so boss and wall are one moulding, exactly
    # as the bin does it.
    for fy in TRAY_FOOT_Y_L:
        boss = box(BW - 0.8, W - TRAY_WALL + 0.9, fy - 6.0, fy + 6.0,
                   0, TRAY_BOSS_T_L)
        t += safe_fillet(boss, boss.edges().filter_by(Axis.Z), 2.0)
        t -= foot_pocket(W / 2, fy)

    # Cell discs LAST: upward-opening, pause-and-insert, sealed under --
    # the bin's stack exactly, so one pause height serves both parts.
    # Last on purpose. Cut before the foot bosses, two of these pockets got
    # unioned shut again; a cavity that a later `+=` can refill is the same
    # trap the display spine's pilots fell into.
    for a, b_ in bounds:
        t -= Pos(BW + TRAY_W_CAV / 2, (a + b_) / 2, MAG_INSERT_Z) * Cylinder(
            (MAGNET_D + MAGNET_FIT_CELL) / 2, MAG_POCKET_D,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

    # head pockets + magnet seats, exactly the bin's stack
    for yh in (FRONT_AXIS, REAR_AXIS, TIE_Y):
        t -= head_pocket(yh)
        t -= head_slot(yh)
    for fy in FR_FOOT_Y:
        t -= box(-1, 0.5, fy - 8.5, fy + 8.5, -1.2, 4.5)
    return t


# ------------------------------------------------------------ side blank ----
def side_blank():
    """The LEFT frame's base skid -- a magnetic cover for the three bar-end
    heads that does not look like one.

    A cover plate over three screws reads as a cover plate. A skid the full
    length of the deck band, the same 6 mm as the plate, top edge flush with
    the band's, reads as the frame standing on a 12 mm base rail with the
    truss plate rising from it -- a plinth, a shape with a reason to exist.
    Same bone PLA as the frame. Held exactly as the side bin is: three N52
    discs over the three alloy-steel cap heads, self-centring; it hangs
    1 mm above the desk like the bench does, and lifts straight off to
    service the screws. Head pockets open only to the underside (a head
    3.15 off the bottom edge leaves no room for a closed floor), which
    faces the desk 1 mm away -- nothing shows. Prints outer face down: every
    pocket is a blind hole from the top, no bridges.
    Local frame: x -6..0 (inner face at x=0 against the plate's outer face),
    placed at the origin on the left frame; the right side has the bin.
    """
    T = 6.0
    HEAD_VOID = BAR_HEAD_T + 0.3
    y0, y1 = 2.0, 163.0
    s = box(-T, 0, y0, y1, 0, 8.0)
    # the plate's own corner grammar (r2 on the end corners), plus a 1.5
    # chamfer on the outer top arris so the skid reads bevelled, not slab
    s = safe_fillet(s, s.edges().filter_by(Axis.X), 2.0)
    s = safe_chamfer(s, s.edges().filter_by(Axis.Y)
                     .group_by(Axis.Z)[-1].group_by(Axis.X)[0], 1.5)
    hz = END_SCREW_Z
    mz = (MAGNET_D + MAGNET_FIT) / 2 + 0.6
    for y in (FRONT_AXIS, REAR_AXIS, TIE_Y):
        # head pocket (open to the underside), then the magnet seat behind
        # it. The disc goes in through the pocket and presses into its
        # seat; skin 0.7 to the outer face.
        s -= box(-HEAD_VOID, 0.1, y - 3.1, y + 3.1, -1.2, hz + 2.75 + 0.35)
        s -= Pos(-HEAD_VOID, y, mz) * Rot(0, -90, 0) * Cylinder(
            (MAGNET_D + MAGNET_FIT) / 2, MAGNET_T,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
    # relief over the frame's TPU foot-pad flanks (0.12 proud), as the bin
    for fy in FR_FOOT_Y:
        s -= box(-0.5, 1, fy - 8.5, fy + 8.5, -1.2, 4.5)
    return s


# ------------------------------------------------------------- assembly -----
def build():
    parts = {
        "end_frame": end_frame(),
        "deck_ladder": deck_ladder(),
        "rear_tie": rear_tie(),
        "rear_tray": rear_tray(),
        "foot_pad": foot_pad(),
        "side_bin": side_bin(),
        "side_tray": side_tray(),
        "rail_cap": rail_cap(),
        # Full width, so it lands on both post faces. At SPAN-2 it stopped 1 mm
        # short of each frame and was a beam supported by nothing.
        "din_rail": din_rail(length=FR_W, mounts=[
            x - FR_W / 2 for x in
            (RAIL_END_ST, FR_W - RAIL_END_ST) + BUTTRESS_X]),
    }
    placed = {
        "asm_frame_l": parts["end_frame"],
        # MIRRORED, not translated. The rail seats are cut opening on the
        # plate's +X face; simply moving the same part to X=294 pointed them at
        # X=300 -- the outside of the bench -- so the rails arrived at 294 and
        # butted a flat face with no seat at all.
        "asm_frame_r": Pos(FR_W, 0, 0) * mirror(parts["end_frame"], Plane.YZ),
        # The ladder carries both rails at their Y stations already, so it
        # places with a single X shift -- one part, one transform, and the
        # rungs can never be left out or put in backwards.
        "asm_ladder": Pos(FRAME_T, 0, 0) * parts["deck_ladder"],
        "asm_tie": Pos(FRAME_T, TIE_Y, 0) * parts["rear_tie"],
        "asm_rail": to_post(parts["din_rail"]),
        # PROTOTYPE SWAP: the universal display mount takes the rail span
        # the board plate and screen bezel sat on (48..228). Both retired
        # poses still exist as parts and one-line placements -- nothing is
        # deleted, they are just off the rail while the mount is trialled.
        "asm_railbin": to_post(rail_bin(), x_centre=MOD_X_BIN),
        # Display mount v2: two clip-on posts, ONE part printed twice.
        # v1's H-frame (spine + 2 uprights + 2 crossbars) was 5 parts and
        # 63.4 cm3 against 2 parts and 25.1 -- 60% less plastic -- and it
        # only existed because the uprights sat at a fixed spacing and
        # needed something to bolt to. The rail already does both jobs:
        # x-adjustment from the rail, y from each post's slot.
        # display_mount_placed() is still imported and still builds v1;
        # cad/display_mount_v1.py stages it as the retired viewer variant.
        **{f"asm_post{i}": to_post(display_post(), x_centre=x)
           for i, x in enumerate(DM_POST_X)},
        # Each post's twist lock, LOCKED: knob on the foot's front, hook
        # under the rail's lower lip (2026-10-17, the latches broke -- see
        # params DM_LOCK_Y).
        **{f"asm_lock{i}": to_post(display_lock(), x_centre=x)
           for i, x in enumerate(DM_POST_X)},
        **{f"asm_lockknob{i}": to_post(display_lock_knob(), x_centre=x)
           for i, x in enumerate(DM_POST_X)},
        # The CrowPanel P4's backplate, screwed to both posts' fronts
        # (2026-10-15): the screen's corner holes are 171 apart, the posts 100.
        "asm_backplate": to_post(display_backplate(), x_centre=MOD_X_DISPLAY,
                                 s=FR_RAIL_S + DM_POST_DEMO_CY),
        # The mic crown, slid down the backplate's top socket (2026-10-17).
        "asm_crown": to_post(mic_crown(), x_centre=MOD_X_DISPLAY,
                             s=FR_RAIL_S + DM_POST_DEMO_CY),
        # On its own TPU feet at bench zero -- same stance as the frames.
        "asm_sidebin": Pos(FR_W, 0, 0) * parts["side_bin"],
        # Left screw tray: built right-handed, mirrored onto the left
        # frame's outer face at x=0 (the end-frame rule).
        "asm_sidetray": mirror(parts["side_tray"], Plane.YZ),
        # Rail caps in the shroud windows, seated on the rail's top face.
        "asm_railcap_l": to_post(parts["rail_cap"], x_centre=0.0,
                                 n=RAIL_TOP_Z),
        "asm_railcap_r": Pos(FR_W, 0, 0) * mirror(
            to_post(parts["rail_cap"], x_centre=0.0, n=RAIL_TOP_Z),
            Plane.YZ),
        # Bought hardware, shown where it lives: the N52 discs.
        **magnet_discs(),
    }
    placed["asm_tray"] = Pos(FRAME_T, TRAY_Y0, 0) * parts["rear_tray"]
    # Shown seated in its pocket. The printed pad is 1.35 thick against a 1.0
    # pocket, so in the assembly it reads as 0.35 of interference -- that IS
    # the compression, not a modelling error. Four stations: two frames, two
    # buttresses -- the buttress pads now press on tray-grown lands.
    # End pads centre on the moved screw stations (RAIL_END_ST), spanning
    # plate and landing boss; buttress pads unchanged.
    # (No gasket part is placed any more: the four glands hold two bought
    # 3 x 1 O-rings each, which the assembly does not model.)
    # Tray feet, seated 0.1 shy of the frame-pad plane (TRAY_FOOT_SHY).
    for i, fx in enumerate(TRAY_FOOT_X):
        placed[f"asm_foot{i}"] = Pos(
            FRAME_T + fx, TRAY_Y0 + TRAY_FOOT_Y,
            -FOOT_PROUD + TRAY_FOOT_SHY) * parts["foot_pad"]
    # The other ten foot pads, which the viewer used to wave away in a
    # footnote: six under the ladder rails, four under the end frames' foot
    # bars (those pockets run cross-ways, hence the Rot).
    k = len(TRAY_FOOT_X)
    for ry in (FRONT_AXIS, REAR_AXIS):
        for fx in FOOT_X:
            placed[f"asm_foot{k}"] = \
                Pos(FRAME_T + fx, ry, -FOOT_PROUD) * parts["foot_pad"]
            k += 1
    for x in (FRAME_T / 2, FR_W - FRAME_T / 2):
        for y in FR_FOOT_Y:
            placed[f"asm_foot{k}"] = \
                Pos(x, y, -FOOT_PROUD) * Rot(0, 0, 90) * parts["foot_pad"]
            k += 1
    # ...two under the side bin, which stands level with the frames...
    for fy in SIDEBIN_FOOT_Y:
        # On the pocket's own centre, the bin's W / 2 (SIDE_BW-based). A literal 17.5
        # here left each pad 0.25 off its pocket (software test fit).
        placed[f"asm_foot{k}"] = \
            Pos(FR_W + (SIDE_BW + SIDEBIN_CAV + TRAY_WALL) / 2, fy,
                -FOOT_PROUD) \
            * parts["foot_pad"]
        k += 1
    # ...and two under the left screw tray, which had none: it hung off its
    # three magnets alone with a bare underside on the desk, while the bin
    # opposite stood on rubber. x is mirrored, so negate the tray's W/2.
    for fy in TRAY_FOOT_Y_L:
        placed[f"asm_foot{k}"] = mirror(
            Pos((SIDE_BW + TRAY_W_CAV + TRAY_WALL) / 2, fy, -FOOT_PROUD)
            * parts["foot_pad"], Plane.YZ)
        k += 1
    # Hardware. Bar ends: pan heads on the frames' outer faces, shanks
    # reaching through the plates into the end pilots at z = r - 2.85.
    pan = m3_screw(head="cap")     # the magnetic six; see BAR_HEAD_T
    rcap = m3_screw(length=RAIL_SCREW_L, head="cap")
    for i, (y, z) in enumerate(((FRONT_AXIS, END_SCREW_Z),
                                (REAR_AXIS, END_SCREW_Z),
                                (TIE_Y, END_SCREW_Z))):
        placed[f"hw_end{i}"] = Pos(0, y, z) * Rot(0, 90, 0) * pan
        placed[f"hw_end{i + 3}"] = Pos(FR_W, y, z) * Rot(0, -90, 0) * pan
    # DIN rail: two per station, cap heads seated on the counterbore floor
    # at n = RAIL_TOP_Z - RAIL_CBORE_H, entering from the rail's OUTER face
    # -- the only open side.
    for i, x in enumerate((RAIL_END_ST, FR_W - RAIL_END_ST) + BUTTRESS_X):
        for j, dy in enumerate((-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2)):
            placed[f"hw_rail{i * 2 + j}"] = to_post(
                Pos(0, dy, 0) * Rot(180, 0, 0) * rcap,
                x_centre=x, n=RAIL_TOP_Z - RAIL_CBORE_H)
    return parts, placed


def props():
    """Breadboards sitting in the cradle, and the boards on the rail modules.

    The cradle is a continuous 55.4 mm slot rather than fixed wells, so a
    full-size board, a half-size board and a parts tray can sit anywhere along
    it in any combination. That flexibility is a side effect of going skeletal
    -- the console had to commit to well positions in the mould.
    """
    import props as P

    cy = (FRONT_AXIS + REAR_AXIS) / 2
    out = {}
    # The full board is the MEASURED one (~160, not the model's 165.1) and
    # starts at rail-local FULL_X0 -- assembly FRAME_T + FULL_X0 = 14.
    # Each prop at its MEASURED width: the half board is HALF_RIB narrower,
    # which is exactly why the rear shoulder steps out in its bay. The datum
    # pegs still pass through both props (they have no notches), so the
    # seated check shows one ~5 mm^3 hit per board -- expected, not a fault.
    # The half board is not centred: it registers on the rear shoulder,
    # which steps out HALF_RIB in its bay, so it sits HALF_RIB / 2 forward
    # of the cradle's centreline with the same 0.4 of play as the full one.
    for tag, w, d, cols, cx, dy in (
            ("bb", FULL_L, BB_D, 63, FRAME_T + FULL_X0 + FULL_L / 2, 0.0),
            ("hb", HB_W, HALF_W, 30, 190.0 + HB_W / 2, -HALF_RIB / 2)):
        out[f"prop_{tag}_body"] = Pos(cx, cy + dy, BOARD_Z) * \
            P.breadboard_body(w=w, d=d, cols=cols)
        h = P.breadboard_holes(w=w, cols=cols)
        h.apply_translation((cx, cy + dy, BOARD_Z))
        out[f"prop_{tag}_holes"] = h
        r, b = P.rail_stripes(w=w)
        r.apply_translation((cx, cy + dy, BOARD_Z))
        b.apply_translation((cx, cy + dy, BOARD_Z))
        out[f"prop_{tag}_red"], out[f"prop_{tag}_blue"] = r, b

    # PROTOTYPE SWAP: the ESP32 and e-paper props rode the plate and bezel;
    # with those off the rail, the fitted prop is the 7" HMI panel sitting
    # on the display mount's crossbars (back face on the clamp plane).
    # v2 posts: the display's back lands on the posts' front face, so the
    # stand-off is one bar thickness instead of v1's plate+boss+upright+
    # crossbar stack (19 mm).
    # 2026-10-15: the REAL screen -- Elecrow's own STEP of the CrowPanel
    # Advanced 7" ESP32-P4 -- on its backplate, instead of the 180 x 105 box.
    # STEP frame: x across, y out of the glass (PCB back at y = -5.7), z up.
    # Into module-local (x along the rail, y up, z = n): (-x, z, y + n_off),
    # a proper rotation, so connectors land on the correct side. Its touch
    # panel and FPC tails are drawn unfolded 50-100 mm above the board in the
    # STEP; everything is clipped to the board's outline.
    from build123d import import_step, Location, Plane, Compound
    step = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ref",
                        "crowpanel7_p4", "crowpanel7_p4.stp")
    if os.path.exists(step):
        z_pcb = RAIL_TOP_Z + DM_POST_T + DBP_BAR_T + DBP_STANDOFF
        n_off = z_pcb + 5.7
        loc = Location(Plane(origin=(0, 0, n_off), x_dir=(-1, 0, 0), z_dir=(0, 1, 0)))
        clip = box(-90, 90, -20, 5, -53, 53)
        sols = sorted(import_step(step).solids(), key=lambda q: -q.volume)
        glass = [q & clip for q in sols[:1]]          # the LCD module
        body = [q & clip for q in sols[1:] if q.volume > 0.5
                and q.bounding_box().max.Y < 0.4]     # board side, not the cover tail
        body = [q for q in body if q.volume > 0.01]
        for key, group in (("glass", glass), ("body", body)):
            out[f"prop_cp7_{key}"] = to_post(loc * Compound(group), x_centre=MOD_X_DISPLAY,
                                             s=FR_RAIL_S + DM_POST_DEMO_CY)
        ui = P.hmi_panel()["ui"]                       # the "screen is on" overlay
        out["prop_cp7_ui"] = to_post(Pos(0, 0, n_off - 10.2 + 0.05) * ui,
                                     x_centre=MOD_X_DISPLAY, s=FR_RAIL_S + DM_POST_DEMO_CY)
    # The reSpeaker XVF3800 in the mic crown, from Seeed's STEP: drawing
    # centre (150, -80), PCB z 0..1.11, logo face +z, so it goes in turned
    # MIC_TURN with its back on the crown's pads.
    step = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ref",
                        "respeaker_xvf3800", "respeaker_mic_array_xvf3800_1_with-xiao-0820.stp")
    if os.path.exists(step):
        sols = import_step(step).solids()
        pcb = max(sols, key=lambda q: q.volume)
        z_pcb = RAIL_TOP_Z + DM_POST_T + DBP_SOCK_FLOOR + 0.1 + CR_RING_T + MIC_STANDOFF
        loc = Pos(0, MIC_Y, z_pcb) * Rot(0, 0, MIC_TURN) * Pos(-150.0, 80.0, 0)
        for key, group in (("pcb", [pcb]), ("parts", [q for q in sols if q is not pcb])):
            out[f"prop_mic_{key}"] = to_post(loc * Compound(group), x_centre=MOD_X_DISPLAY,
                                             s=FR_RAIL_S + DM_POST_DEMO_CY)
    return out


if __name__ == "__main__":
    print("building skeletal frame ...")
    parts, placed = build()
    placed.update(props())
    # Purge first. A part that stops being emitted leaves its last STL behind,
    # and every downstream tool -- the checker, the interference sweep, the
    # viewer -- happily reads it as current. That is exactly how a right end
    # frame from three hours earlier passed every gate while the real one was
    # never written at all.
    for d in ("stl_frame", "frame"):
        p = os.path.join(OUT, d)
        os.makedirs(p, exist_ok=True)
        for f in os.listdir(p):
            if f.endswith((".stl", ".step")):
                os.remove(os.path.join(p, f))
    # Real quantities, so the ledger is honest: measure, don't estimate --
    # this is how Mk3's first "-5 g" claim got corrected to about -1.5 g.
    # foot_pad: 6 under the ladder rails, 4 under the frames, 4 under the tray.
    # end_frame is SINGLE-SIDED (boss, hook, shoulder ribs) -- printing the
    # same STL twice yields two LEFT frames. The right one is a mirrored
    # part in its own file (print review).
    parts["end_frame_r"] = mirror(parts["end_frame"], Plane.YZ)
    # side_tray is built right-handed and PLACED mirrored; the printed part
    # must be the mirror too, or the head pockets land at the wrong end
    # (DFM review). Same rule as end_frame_r: export the mirror.
    parts["side_tray"] = mirror(parts["side_tray"], Plane.YZ)
    QTY = {"end_frame": 1, "end_frame_r": 1,
           "foot_pad": 18,   # 6 ladder, 4 end frame, 4 tray, 2 bin, 2 left tray
           "rail_cap": 2}
    STRUCTURE = ("end_frame", "end_frame_r", "deck_ladder", "rear_tie",
                 "rear_tray")
    # STEP alongside STL: exact B-rep for round-tripping into Fusion (or
    # any CAD) once a part graduates from prototyping -- same OCCT solids
    # the STLs are meshed from, so nothing is lost in translation.
    os.makedirs(os.path.join(OUT, "step_frame"), exist_ok=True)
    total = struct = 0.0
    for name, p in parts.items():
        export_stl(p, os.path.join(OUT, "stl_frame", f"{name}.stl"),
                   tolerance=0.02, angular_tolerance=0.1)
        try:
            export_step(p, os.path.join(OUT, "step_frame", f"{name}.step"))
        except Exception as exc:
            print(f"    ! STEP failed for {name}: {exc}")
        qty = QTY.get(name, 1)
        total += p.volume / 1000 * qty
        if name in STRUCTURE:
            struct += p.volume / 1000 * qty
        print(f"    {name:18s} x{qty}  {p.volume / 1000:6.1f} cm3")
    print(f"    {'PLA STRUCTURE':18s}     {struct:6.1f} cm3 "
          f"(Mk2 was 150.5 with struts and ribs)")
    import trimesh
    for name, p in placed.items():
        path = os.path.join(OUT, "frame", f"{name}.stl")
        if isinstance(p, trimesh.Trimesh):
            p.export(path)          # hole grids are meshes, not B-rep
        else:
            export_stl(p, path, tolerance=0.02, angular_tolerance=0.1)
    print(f"    {'FRAME TOTAL':18s}     {total:6.1f} cm3 "
          f"(console base alone was 308)")










