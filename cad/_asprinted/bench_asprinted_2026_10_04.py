"""Breadboard Bench - parametric geometry.

Run:  python cad/bench.py
Writes STL (mesh, for rendering/printing) and STEP (exact, for editing) into out/.

Architecture: a tiered console. Front bay holds a full-size breadboard in a
recessed well; the middle tier is a row of scoop-front component bins; the back
is a 20-degree panel carrying a printed TS35 DIN rail that everything else
clips onto.
"""

from __future__ import annotations

import math
import os
import sys

from build123d import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box from two opposite corners, in any order."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0
    )


def to_panel(shape, x_centre=BENCH_W / 2, s=RAIL_S, n=0.0):
    """Move a shape modelled in a flat local frame onto the tilted back panel.

    Local frame: length along X, cross-section in Y (across the rail) and
    Z (out of the panel face, 0 = the face itself).
    """
    y, z = panel_point(s, n)
    return Pos(x_centre, y, z) * Rot(PANEL_ROT_X, 0, 0) * shape


def safe_fillet(shape, edges, r):
    """Fillet that degrades gracefully -- OCCT blends fail on awkward edge
    sets. Degrading is fine; degrading SILENTLY is not: two parts shipped
    without their modelled chamfers and nothing said a word (print review).
    """
    try:
        return fillet(edges, r)
    except Exception as e:
        import inspect
        ln = inspect.currentframe().f_back.f_lineno
        print(f"    WARNING safe_fillet dropped r={r} at caller line {ln}: "
              f"{type(e).__name__}")
        return shape


def safe_chamfer(shape, edges, d):
    try:
        return chamfer(edges, d)
    except Exception as e:
        import inspect
        ln = inspect.currentframe().f_back.f_lineno
        print(f"    WARNING safe_chamfer dropped d={d} at caller line {ln}: "
              f"{type(e).__name__}")
        return shape


# Five 5 mm gussets spread across the inset panel, and one cable pass-through
# centred in each bay -- so the slots sit on a stated rhythm symmetric about
# the centreline instead of wherever they happened to land.
_RIB = 5.0
_BAY_W = (PANEL_W - 5 * _RIB) / 4
BAYS = [(PANEL_X0 + _RIB + i * (_BAY_W + _RIB),
         PANEL_X0 + (i + 1) * (_RIB + _BAY_W)) for i in range(4)]
SLOT_X = [round((a + b) / 2, 1) for a, b in BAYS]


def rim_cutter(x0, x1, y0, y1, deck, r, rim=RIM):
    """Pocket cutter carrying a chamfered rim.

    Easing every opening by 0.75 mm draws a thin highlight around it, so the
    pockets read as cut rather than moulded. Built into the cutter instead of
    selected as edges afterwards -- edge selection on this many pockets is
    exactly the kind of filter that breaks when a dimension moves.
    """
    c = box(x0 - rim, x1 + rim, y0 - rim, y1 + rim, deck - rim, deck + 2.0)
    c = safe_fillet(c, c.edges().filter_by(Axis.Z), r + rim)
    return safe_chamfer(c, c.edges().group_by(Axis.Z)[0], rim * 0.98)


def plinth_envelope(w=BENCH_W, d=BENCH_D, inset=BASE_INSET, rev=BASE_LAND,
                    cham=BASE_FLARE, r_out=OUTER_R):
    """Silhouette the body gets intersected with.

    Three stacked footprints: the real one above `rev + cham`, one inset by
    `inset` below `rev`, and a 45-degree flare between them. Intersecting with
    this does two things at once -- it puts a consistent `r_out` radius on every
    outer corner, and it undercuts the base so the object reads as sitting on a
    recessed plinth rather than as a slab meeting the desk. The shadow line that
    creates is the cheapest way to stop a printed object looking like a lump.
    """
    # r_out - inset is the geometrically correct lower radius: offsetting an
    # R6 corner inward by 4 mm gives R2 concentric with it, so the plinth's
    # corners are true parallels of the body's rather than a second radius.
    lo = box(inset, w - inset, inset, d - inset, -1.0, rev)
    lo = safe_fillet(lo, lo.edges().filter_by(Axis.Z), max(1.0, r_out - inset))

    mid = box(0, w, 0, d, rev, rev + cham)
    mid = safe_fillet(mid, mid.edges().filter_by(Axis.Z), r_out)
    mid = safe_chamfer(mid, mid.edges().group_by(Axis.Z)[0], cham - 0.05)

    hi = box(0, w, 0, d, rev + cham, 300.0)
    hi = safe_fillet(hi, hi.edges().filter_by(Axis.Z), r_out)
    return lo + mid + hi


# --------------------------------------------------------------------------
# DIN rail
# --------------------------------------------------------------------------
# Mount screws: M3 socket head CAP screws in a counterbore, decided 2026-09-22
# and cut 2026-10-04. A cap head is 5.5 dia x 3.0 tall; the 6.0 x 3.2 pocket
# puts its top 0.2 BELOW the face the clips slide on. Countersunk heads were
# flush too, but they forced a second screw type (x16 / x14) and a cone that
# feathered the web; one M3x12 cap now does every structural joint in the
# bench, and it is magnetic steel, which the rail caps' magnets sit on.
# RAIL_CBORE_D / RAIL_CBORE_H live in params.py: frame.py seats the screws on them.


def din_rail(length=RAIL_LEN, grow=0.0, mounts=()):
    """TS35-compatible printed rail, centred on the origin, mounting face at Z=0.

    `grow` inflates the section to make a pocket cutter.

    `mounts` lists rail-local X stations that get a PAIR of screw holes
    straddling the centreline, for fixing the rail to whatever supports it.
    These are separate from the 25 mm slots because the 25 mm pitch is a
    real-DIN-rail convention that has nothing to do with where this frame's
    supports stand: on a 300 mm rail the slots run X 30..270, both end frames
    sit at X 0..6 and 294..300, and the screw pilots drilled into those posts
    came out against 214 mm2 of solid web. The rail was resting on two 191 mm2
    patches of face contact and held by nothing at all.
    """
    g = grow
    # True top-hat: 27 mm web on the mounting face, 35 mm lips standing 7.5 mm
    # proud. The 4 mm eave under each lip is the channel a DIN clip hooks into;
    # printed web-down it is a 4 mm overhang, which droops a little on the
    # underside and does not matter -- clips grip the lip's front face and edge.
    web = box(-length / 2 - g, length / 2 + g,
              -RAIL_WEB_W / 2 - g, RAIL_WEB_W / 2 + g,
              -g, RAIL_CHANNEL_Z + g)
    lips = box(-length / 2 - g, length / 2 + g,
               -RAIL_LIP_W / 2 - g, RAIL_LIP_W / 2 + g,
               RAIL_CHANNEL_Z - g, RAIL_TOP_Z + g)
    rail = web + lips

    # A 45-degree fillet in the inside corner where each lip meets the web.
    # The lip's underside is a 4 mm horizontal overhang printed web-down and
    # droops 0.3-0.5 mm in PETG, exactly where the clip tooth engages. This
    # cuts the unsupported reach to 2.5 mm. It stops 0.55 mm short of where the
    # tooth reaches (|y| = 15.55), so the channel keeps its depth at the tip
    # where it matters -- and buying a steel rail is off the table, so the
    # printed one has to be right.
    # The eave fillets are part of the SECTION, so the grown pocket-cutter
    # form must carry them too -- guarded behind grow==0 they were absent
    # from the frame's rail mortise cutter, and the mortise cheeks collided
    # with them by ~12 mm3 per end. Grown copies skip the 45-degree chamfer:
    # over-cutting that corner by a hair just eases the slide-in.
    for sign in (1, -1):
        f = box(-length / 2 - g, length / 2 + g,
                sign * (RAIL_WEB_W / 2 - g), sign * (RAIL_WEB_W / 2 + 1.5 + g),
                RAIL_CHANNEL_Z - 1.5 - g, RAIL_CHANNEL_Z + g)
        if grow == 0.0:
            f = safe_chamfer(f, f.edges().filter_by(Axis.X).filter_by(
                lambda e: abs(e.center().Z - (RAIL_CHANNEL_Z - 1.5)) < 0.01
                and abs(abs(e.center().Y) - (RAIL_WEB_W / 2 + 1.5)) < 0.01),
                1.49)
        rail += f

    if grow == 0.0:
        # Oblong mounting slots straight through the web, on the real 25 mm
        # pitch. Screws go through these into the panel, as on a steel rail.
        n = int((length - 40) // 25)
        start = -(n - 1) * 25 / 2
        for i in range(n):
            x = start + i * 25
            # Through the FULL section, not RAIL_CHANNEL_Z + 2. This printed
            # rail is solid to z = 7.5 at the centre (a steel top-hat is open
            # there; the closed crown is what makes the printed one stiff
            # enough to be a structural tie), and a cutter sized for the web
            # alone left every slot and every mount hole capped by a 0.2 mm
            # skin at the outer face -- screws could not pass at all. Caught
            # by the user in the viewer, not by any gate: an interference
            # sweep sees nothing wrong with a screw sealed inside a cavity.
            slot = Pos(x, 0, RAIL_TOP_Z / 2) * Box(15.0, 6.2,
                                                   RAIL_TOP_Z + 2)
            slot = fillet(slot.edges().filter_by(Axis.Z), 3.0)
            rail -= slot
            # Countersink opening at the OUTER face (7.5), where a screw can
            # actually arrive -- the old one opened at 6.3, which at the
            # centreline is buried mid-solid.
            rail -= Pos(x, 0, RAIL_TOP_Z - 0.85) * Cone(1.6, 3.6, 2.0)
        # Long outer edges only: the through-slots put short X-edges on the
        # top face whose neighbours are csk cones, and OCCT refuses the
        # blend for the whole selection -- which silently dropped this
        # fillet for a revision.
        rail = safe_fillet(rail, rail.edges().filter_by(Axis.X)
                           .group_by(Axis.Z)[-1]
                           .filter_by(lambda e: e.length > min(
                               100, length * 0.75)), 0.5)

    if grow == 0.0:
        # Round, not oblong: these locate the rail as well as fix it, so the
        # slop that makes the 25 mm slots forgiving is exactly wrong here.
        # 3.4 clearance against a 2.5 pilot in the support -- the screw has to
        # pull the two together, not thread itself into both.
        # FIRST station is the 3.4 datum; the rest open to 4.2 so
        # differential PLA shrink over 300 mm (rail vs frame chain) has
        # somewhere to go. The rail is located by its mortises and lands;
        # these screws only clamp, and a flat-seated cap head (unlike the
        # old countersunk cone) does not fight a bore that is off-centre.
        for i, x in enumerate(mounts):
            for y in (-RAIL_END_PITCH / 2, RAIL_END_PITCH / 2):
                # Full-section bore + counterbore from the outer face, the
                # plane the clips slide on -- see the slot comment for why
                # RAIL_CHANNEL_Z-based cuts here were blind holes.
                r = 1.7 if i == 0 else 2.1
                floor = RAIL_TOP_Z - RAIL_CBORE_H
                # Flat-floored pocket for the cap head: floor at
                # RAIL_TOP_Z - RAIL_CBORE_H, leaving 4.2 of rail under it.
                rail -= Pos(x, y, floor + RAIL_CBORE_H / 2 + 0.5) * \
                    Cylinder(RAIL_CBORE_D / 2, RAIL_CBORE_H + 1.0)
                # The bore, in two pieces with ONE LAYER left between them.
                # The rail prints clip-face down, so the pocket's floor is a
                # roof: with the bore open through it, that roof is a ring
                # hanging in air around a hole and the head seats on sag.
                # A 0.2 membrane makes the layer a plain 6 mm bridge. The
                # screw pushes through it on assembly (sacrificial layer).
                rail -= Pos(x, y, (floor - RAIL_CBORE_SKIN) / 2 - 0.5) * \
                    Cylinder(r, floor - RAIL_CBORE_SKIN + 1.0)
    return rail


# --------------------------------------------------------------------------
# DIN clip - the shared mount on the back of every module
# --------------------------------------------------------------------------
def clip_relief(width=CLIP_W, fit=None):
    """The cut that frees the latch, as a separate cutter on purpose.

    It has to be applied AFTER the clip is unioned into a module. Cut inside
    din_clip() alone, the module body simply fills it back in -- which is what
    happened to the previous design and left two of its three clips with no
    spring whatever. It is a 1.8 mm slice sitting just under the module face
    rather than a slot through the module, so it costs 0.9 mm off a 3 mm plate
    and nothing visible.
    """
    f = RAIL_FIT if fit is None else fit
    inner = RAIL_LIP_W / 2 + f
    outer = inner + CLIP_JAW_T
    x0 = -width / 2
    x1 = min(x0 + 18.0, width / 2 - 1.0)
    c = box(x0 + 4.0, x1 + 2.0, -outer - 1, -inner + 0.25,
            RAIL_TOP_Z - 0.9, RAIL_TOP_Z + 0.9)
    # Round the slot's ROOT end -- the machinist's drilled-slot-end move.
    # A square-ended relief slot is a crack starter at the latch root, and
    # the post-hoc fillet that used to soften it was an OCCT edge-filter
    # blend that failed on every module (exact-half tangency on the slot's
    # 1.6 cross edges). Rounding the CUTTER cannot fail to build, and both
    # cuts of this slot (din_clip and attach_clip's re-cut) inherit it.
    c = safe_fillet(c, c.edges().filter_by(Axis.Y).group_by(Axis.X)[0], 0.85)
    return c


def attach_clip(body, width=CLIP_W, fit=None):
    """Union the clip onto a module, then re-cut the relief. Modules must use
    this rather than `body + din_clip(...)`."""
    return (body + din_clip(width, fit)) - clip_relief(width, fit)


def din_clip(width=CLIP_W, fit=None):
    """Hook-and-rock clip: one rigid hook, one sprung latch.

    The previous version was two symmetric cantilevers, each asked to deflect
    2.45 mm over a beam 4.05 mm long and 3.2 mm thick. That is L/t = 1.3 and
    72% strain, against a PETG yield of about 4% -- a block, not a spring. It
    could not have gone on, and forcing it would have broken the module. Two of
    the three clips had no spring at all besides, because the module body
    re-welded the relief slot downstream.

    Real DIN accessories hook one lip and rotate on. That drops the deflection
    below 1 mm, and it lets the latch run ALONG the rail where there is room for
    a real beam: 18 x 1.6 mm, so L/t = 11 and about 0.6% strain on the rock-on
    stroke. It also flexes in the module's local Y, which keeps the bending
    stress along the layers whichever way up the part prints.

    `fit` is the per-side clearance against the rail lips -- the one dimension
    most likely to need tuning after a test print. See cad/coupon.py.
    """
    f = RAIL_FIT if fit is None else fit
    inner = RAIL_LIP_W / 2 + f
    outer = inner + CLIP_JAW_T
    top = RAIL_TOP_Z + CLIP_BACK_T
    # 0.5, not 0.35: the lip eave droops 0.3-0.5 printed web-down, and the
    # tooth meets exactly that surface (print review).
    tooth_top = RAIL_CHANNEL_Z - 0.5
    tooth_bot = tooth_top - 1.9

    clip = box(-width / 2, width / 2, -outer, outer, RAIL_TOP_Z, top)

    # --- rigid hook, +y (uphill). Carries the load; never flexes. ---------
    clip += box(-width / 2, width / 2, inner, outer, tooth_bot - 0.6,
                RAIL_TOP_Z)
    clip += box(-width / 2, width / 2, inner - CLIP_TOOTH, outer,
                tooth_bot, tooth_top)

    # --- sprung latch, -y. Runs along the rail, so it can be long. --------
    LT, LL, ROOT = 1.6, 18.0, 4.0
    x0 = -width / 2
    x1 = min(x0 + LL, width / 2 - 1.0)
    clip += box(x0, x1, -inner - LT, -inner, tooth_bot - 0.6, RAIL_TOP_Z)
    clip += box(x1 - 7.0, x1, -inner, -(inner - CLIP_TOOTH),
                tooth_bot, tooth_top)

    # Free the finger from the back plate everywhere but its root. Without
    # this it is not a cantilever, just a thickening of the plate -- which is
    # exactly what the old relief slot became once the module body closed it.
    clip -= clip_relief(width, fit)

    # Root crack relief now lives in clip_relief() itself -- the slot end
    # is rounded in the cutter, so there is no post-hoc blend to fail.

    # Release tab on the sprung tip, so you lever the latch rather than the
    # hook. Doubles as the visual cue for which side comes off.
    tab = box(x1 - 6.0, x1, -(outer + 6.0), -inner - LT + 0.4,
              RAIL_TOP_Z - 3.4, RAIL_TOP_Z)
    clip += safe_fillet(tab, tab.edges().filter_by(Axis.X)
                        .group_by(Axis.Y)[0], 1.2)
    return clip


# --------------------------------------------------------------------------
# Part A - the base console
# --------------------------------------------------------------------------
def base_body():
    # Side profile in (Y, Z), extruded across the full width.
    pf_y0, pf_z0 = PANEL_Y0, PANEL_Z0
    pf_y1, pf_z1 = PANEL_TOP_Y, PANEL_TOP_Z
    pb_y1 = pf_y1 + PANEL_T / COS_T
    profile = [
        (0.0, 0.0),
        (BENCH_D, 0.0),
        # The rear wall used to rise to 30 mm before sloping in -- a solid
        # 300 x 4 x 18 block of nothing. Starting the taper at 12 mm gives the
        # same footprint for anti-tip with ~22 cm3 less plastic.
        (BENCH_D, 12.0),
        (pb_y1, pf_z1),
        (pf_y1, pf_z1),
        (pf_y0, pf_z0),
        (MID_Y0, MID_DECK_Z),
        (MID_Y0, FRONT_DECK_Z),
        (0.0, FRONT_DECK_Z),
    ]
    face = make_face(Polyline(*profile, close=True))
    body = Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(face, BENCH_W))

    # ---- front tier: two breadboard wells + a tool trough ------------------
    for x0, w in ((BB_WELL_X, BB_WELL_W), (HB_WELL_X, HB_WELL_W)):
        y0, y1 = BB_WELL_Y, BB_WELL_Y + BB_WELL_D
        well = box(x0, x0 + w, y0, y1, BB_WELL_FLOOR, FRONT_DECK_Z + 1)
        well = fillet(well.edges().filter_by(Axis.Z), WELL_R)
        body -= well
        body -= rim_cutter(x0, x0 + w, y0, y1, FRONT_DECK_Z, WELL_R)
        # Finger scoops so the board can be popped back out. Only on the rear
        # wall -- scooping the front edge too would notch the outer face.
        for frac in (0.28, 0.72):
            # align MIN so the scoop starts at the well floor instead of
            # boring straight through the 3 mm base
            body -= Pos(x0 + w * frac, BB_WELL_Y + BB_WELL_D,
                        BB_WELL_FLOOR) * Cylinder(
                7.0, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # r 7.0, not 8.5: at 8.5 the scoop left a 0.2 mm membrane in the
            # rear wall that slices to nothing (print review)

    ty0, ty1 = BB_WELL_Y, BB_WELL_Y + BB_WELL_D
    trough = box(TROUGH_X0, TROUGH_X1, ty0, ty1, FLOOR, FRONT_DECK_Z + 1)
    trough = fillet(trough.edges().filter_by(Axis.Z), POCKET_R)
    body -= trough
    body -= rim_cutter(TROUGH_X0, TROUGH_X1, ty0, ty1, FRONT_DECK_Z, POCKET_R)

    # ---- middle tier: scoop-front component bins ---------------------------
    span = BIN_X1 - BIN_X0
    bin_w = (span - (BIN_COUNT - 1) * BIN_WALL) / BIN_COUNT
    # One field opening in the deck, eased once around its perimeter...
    field = box(BIN_X0, BIN_X1, BIN_Y0, BIN_Y1, BIN_DIVIDER_Z, MID_DECK_Z + 1)
    field = fillet(field.edges().filter_by(Axis.Z), POCKET_R)
    body -= field
    body -= rim_cutter(BIN_X0, BIN_X1, BIN_Y0, BIN_Y1, MID_DECK_Z, POCKET_R)
    # ...with the dividers sunk inside it.
    for i in range(BIN_COUNT):
        x0 = BIN_X0 + i * (bin_w + BIN_WALL)
        pocket = box(x0, x0 + bin_w, BIN_Y0, BIN_Y1,
                     BIN_FLOOR_Z, BIN_DIVIDER_Z + 1)
        pocket = fillet(pocket.edges().filter_by(Axis.Z), POCKET_R)
        body -= pocket
        # Only the divider tops need easing -- in Y the pocket edge IS the field
        # edge, already eased at the deck. Inset by RIM + 0.3 rather than RIM
        # exactly: landing the grown cutter flush with the field boundary makes
        # the two faces coincident, and the boolean comes out non-manifold.
        body -= rim_cutter(x0, x0 + bin_w, BIN_Y0 + RIM + 0.3,
                           BIN_Y1 - RIM - 0.3, BIN_DIVIDER_Z, POCKET_R)
        # scoop the front lip down so you can sweep parts out with a thumb
        scoop = Pos(x0 + bin_w / 2, BIN_Y0 - 1.0, MID_DECK_Z + 7.0) * \
            Rot(0, 90, 0) * Cylinder(11.0, bin_w - 2)
        body -= scoop

    # ---- back panel: rail pocket, jaw relief, cable slots ------------------
    # Shallow locating recess for the rail web only. The relief grooves that
    # used to run either side are gone -- with the section the right way up,
    # the rail's own 6.3 mm channel is where the clip teeth go.
    body -= to_panel(box(-(RAIL_LEN + 1) / 2, (RAIL_LEN + 1) / 2,
                         -RAIL_WEB_W / 2 - 0.35, RAIL_WEB_W / 2 + 0.35,
                         -0.4, 0.4))
    # M3 pilots for the rail's mounting slots -- ON the 25 mm slot pitch.
    # The old stations (30/110/190/262) missed every slot by 2.5-12.5 mm and
    # landed on solid web: the rail could not be attached at all. Slots sit
    # at 150 +/- n*25, so pilots go to slot centres with the widest spread.
    for x in (50.0, 125.0, 175.0, 250.0):
        body -= to_panel(Rot(0, 0, 0) * Pos(0, 0, -6) * Cylinder(1.3, 14),
                         x_centre=x, s=RAIL_S)
    # Cable pass-throughs under the rail, one centred in each gusset bay --
    # putting them on the old pitch would have driven a rib through the middle
    # slot and blocked it.
    for x in SLOT_X:
        slot = box(-16, 16, -5, 5, -14, 14)
        slot = fillet(slot.edges().filter_by(Axis.Z), 4.5)
        body -= to_panel(slot, x_centre=x, s=12.0)
    # Hollow the buttress behind the panel. The cutter is trimmed by a slab that
    # follows the panel, so the panel itself survives at full thickness while
    # everything behind it is scooped out between three gusset ribs.
    # Five 5 mm gussets instead of four 8 mm ones: 7 mm less rib material, and
    # the unsupported panel span drops from 88 mm to 68 mm.
    panel_slab = to_panel(box(-260, 260, -90, 320, -PANEL_T - 0.1, 0.1), s=0.0)
    # Rear guard: the bay cutter used to run flat to BENCH_D - 2.5, but the
    # outer wall SLOPES inward above z=12, so the wall thinned from 2.5 at
    # the bottom to NOTHING where the slope crossed the cutter plane -- a
    # feather edge over every bay (print review). The guard is a slab that
    # follows the outer slope 2.6 inside it, so the wall keeps its gauge
    # all the way up.
    def _y_out(z):
        return BENCH_D + (z - 12.0) * (pb_y1 - BENCH_D) / (pf_z1 - 12.0)
    guard = make_face(Polyline(
        (BENCH_D - 2.6, 7.0), (BENCH_D + 30.0, 7.0),
        (BENCH_D + 30.0, PANEL_TOP_Z + 10.0),
        (_y_out(PANEL_TOP_Z + 10.0) - 2.6, PANEL_TOP_Z + 10.0),
        close=True))
    guard = Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(guard, BENCH_W + 2))
    guard = Pos(-1, 0, 0) * guard
    for x0, x1 in BAYS:
        # Cut right through the top: stopping short left a 1.9 mm wide, 243 mm
        # long sliver of unsupported ledge behind the panel's top edge.
        body -= (box(x0, x1, PANEL_Y0 + 1.0, BENCH_D + 20, FLOOR,
                     PANEL_TOP_Z + 2) - panel_slab - guard)

    # Rail-pilot bosses on the panel's BACK face -- added AFTER the buttress
    # hollowing, because the bay cutter scoops exactly the space they occupy
    # (the first attempt put them before it, and the measurement stayed at
    # 3.7 mm because the bosses had been silently hollowed away). The 4.0 mm
    # panel alone gives 3.7 mm of thread bite, under the 4.0 minimum; the
    # boss takes it to ~6.7, hidden in the bay. Pilots re-cut through them.
    for x in (50.0, 125.0, 175.0, 250.0):
        body += to_panel(Pos(0, 0, -PANEL_T - 1.5) * Cylinder(4.0, 3.0),
                         x_centre=x, s=RAIL_S)
        # Under-gusset: the panel leans back 20, so a plain boss protrudes
        # rear-DOWNWARD and its tip starts in mid-air -- the island gate
        # caught it on the first build. A steep wedge from the panel face up
        # to the boss tip gives every slice something to stand on.
        # Overlapping 0.4 into both the boss and the panel -- kiss-tangent
        # unions are exactly the touching-solid booleans OCCT fails on, and
        # the first cut of this came back non-watertight.
        gusset = make_face(Polyline((-3.6, -PANEL_T + 0.4),
                                    (-3.6, -PANEL_T - 3.0),
                                    (-9.5, -PANEL_T + 0.4), close=True))
        gusset = Rot(0, 0, 90) * (Rot(90, 0, 0) * extrude(gusset, 8.0))
        body += to_panel(Pos(-4.0, 0, 0) * gusset, x_centre=x, s=RAIL_S)
        body -= to_panel(Pos(0, 0, -6) * Cylinder(1.3, 14),
                         x_centre=x, s=RAIL_S)

    # Inset the panel to PANEL_W, leaving the tray full width. The 6 mm ledge
    # this exposes at each end of the panel base is the joint that stops the
    # tray and the panel reading as one continuous stepped plane.
    for x0, x1 in ((-1, PANEL_X0), (PANEL_X0 + PANEL_W, BENCH_W + 1)):
        body -= box(x0, x1, MID_Y1, BENCH_D + 1, MID_DECK_Z, PANEL_TOP_Z + 5)

    # ---- feet --------------------------------------------------------------
    # Felt-pad recesses. Only 0.8 mm deep: the floor is 2.0 mm now, and the old
    # 1.5 mm recess would have left 0.5 mm of material over each one.
    for fx in (16, BENCH_W - 16):
        for fy in (14, BENCH_D - 14):
            body -= Pos(fx, fy, 0.0) * Cylinder(7.0, 1.6)
    body -= box(-1, BENCH_W + 1, -1, BENCH_D + 1, -1, 0.0)

    # ---- edge treatment ----------------------------------------------------
    # The silhouette comes from the envelope: 7 mm outer corners and a recessed
    # plinth, in one intersection.
    body = body & plinth_envelope()

    # A reveal groove under the deck lip was tried here and cut. In a 10 mm
    # front wall it put a fourth horizontal line within the plinth's shadow and
    # the lip chamfer, and the 1.8 mm band it left above read as a slicing
    # artefact rather than a detail. One strong line beats three weak ones.

    # The edge family: EDGE on the two arrises you look along, RIM on every
    # pocket (already built into the cutters above). Top arrises shrink the
    # cross-section as they rise, so all of these print free.
    # Deliberately NOT filter_by(Axis.X), and no length guard. Once the envelope
    # puts an R6 on the corners, this arris is three edges -- a 288 mm straight
    # plus a 7.07 mm quarter arc at each corner, centred at Y=2.82. Both guards
    # excluded the arcs, so the chamfer stopped dead at each corner and left the
    # corner arris raw. The Y bound is derived from the nearest competing edge
    # (the well rim chamfer at BB_WELL_Y - RIM) rather than picked.
    lip = body.edges().filter_by(
        lambda e: abs(e.center().Z - FRONT_DECK_Z) < 0.3
        and e.center().Y < BB_WELL_Y - RIM - 0.5)
    body = safe_chamfer(body, lip, EDGE)

    # Both arrises of the panel top, leaving a 1.0 mm land between them. This is
    # the best light event on the object -- a hard bright line across the full
    # width, at the highest point, on a leaning surface, for nothing.
    # FRONT arris only. The console-era spec was 1.5 on both arrises of the
    # panel top, but the bay hollowing now cuts through the top, so the rear
    # arris runs along alternating solid/void and no chamfer can wrap it
    # (OCCT refused at every radius; diagnosed edge-by-edge). The front
    # arris is the one a seated user sees.
    top = body.edges().filter_by(Axis.X).filter_by(
        lambda e: e.length > 100 and abs(e.center().Z - PANEL_TOP_Z) < 0.6)
    if len(top):
        front = sorted(top, key=lambda e: e.center().Y)[0:1]
        body = safe_chamfer(body, front, EDGE)
    return body


# --------------------------------------------------------------------------
# Part C - half-size breadboard carrier
# --------------------------------------------------------------------------
def breadboard_carrier():
    """Flat backing plate for a half-size breadboard, peel-and-stick.

    Deliberately featureless on the face. An earlier version had a recessed
    pocket, which meant that printed face-down only the 1.6 mm rim touched the
    bed and the pocket floor became an 84 mm bridge. A plain plate lies flat,
    prints with no supports, and matches how breadboards actually get mounted --
    they all ship with adhesive backing.
    """
    # +7.35, not +7.0: at pose +90 the bed edge is -d/2, and this 0.35
    # lands the latch beam's 1.6 section on the 0.2 layer grid (same rule as
    # the bezel and plates; rail_bin is the documented exception -- its bed
    # edge is the release tab's chamfered tip, and chasing 0.15 of grid by
    # reshaping a lever is worse than the +/-1-layer spring quantisation).
    w, d = HB_W + 8.0, HB_D + 7.35
    plate = box(-w / 2, w / 2, -d / 2, d / 2, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
    plate = fillet(plate.edges().filter_by(Axis.Z), 3.0)
    # Slots for a cable tie, in case you want the board positively retained.
    for sy in (-1, 1):
        slot = box(-w / 2 + 5, -w / 2 + 8, sy * (d / 2 - 9), sy * (d / 2 - 3),
                   RAIL_TOP_Z - 1, RAIL_TOP_Z + 4)
        plate -= slot
        plate -= Pos(w - 10, 0, 0) * slot
    return attach_clip(plate, width=34.0)


# --------------------------------------------------------------------------
# Part D - board plates, one per board family
# --------------------------------------------------------------------------
def board_plate(kind="esp"):
    """Dedicated plate: standoff bosses at the board's own hole pattern.

    The universal cruciform plate died on measurement, not on principle: its
    nut side lies flat against the rail's closed crown, so every hole
    position over the rail band (|y| < ~18) had nowhere for a nut -- the
    ESP32 it was named for could not be bolted on at all. Dedicated plates
    need no nuts: the holes are KNOWN, so each one gets a 7 x 4 standoff
    boss and an M3 x 8 self-tapper goes straight in from the front. The
    4 mm standoff is also where a DevKit's underside pin headers live.

    Bosses are gabled on the -y side: modules print on edge (+90, so -y is
    print-down) and a plain cylindrical boss would hang a 3.5 mm half-round
    overhang; the 45-degree gable prints clean, same trick as teardrop().
    Pilots stop 0.6 above the back face -- the back lies ON the rail, and a
    screw tip proud of it would hold the clip off the lips.
    """
    spec = BOARD_SPECS[kind]
    w, d = spec["size"]
    plate = box(-w / 2, w / 2, -d / 2, d / 2, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
    plate = fillet(plate.edges().filter_by(Axis.Z), 3.0)

    # Gable points +y: the plates print at -90 (face on the bed) where
    # print-down is +y. At +90 they stood on their release TABS -- the
    # dedicated plates are narrower than the old universal, so the tab
    # became the lowest point: the bezel's B4 failure, back for the plates.
    k = 3.5 / math.sqrt(2.0)
    roof = make_face(Polyline((-k, k), (0.0, 3.5 * math.sqrt(2.0)),
                              (k, k), close=True))
    for dx, dy in spec["patterns"]:
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = sx * dx / 2, sy * dy / 2
                boss = extrude(Circle(3.5), 4.5) + extrude(roof, 4.5)
                plate += Pos(cx, cy, RAIL_TOP_Z + 2.5) * boss
                plate -= Pos(cx, cy, RAIL_TOP_Z + 6.6) * Cylinder(1.25, 12)

    return attach_clip(plate, width=30.0)


# --------------------------------------------------------------------------
# Part E - screen bezel (Waveshare 2.9" e-paper)
# --------------------------------------------------------------------------
def screen_bezel():
    # +15.15, not +15.0: at pose -90 the bed edge is the +y body face, and
    # this 0.15 lands the latch beam's 1.6 section on the 0.2 layer grid --
    # off-grid, the slicer quantises the spring to 1.4-1.8 (rate +/-25%).
    w, h = EINK_PCB_W + 13.0, EINK_PCB_H + 15.15
    face_t = 2.4
    z0 = RAIL_TOP_Z
    body = box(-w / 2, w / 2, -h / 2, h / 2, z0, z0 + 9.0)
    body = fillet(body.edges().filter_by(Axis.Z), 3.5)

    # rear pocket for the PCB
    # +1.1 total (0.55/side), not +0.7: PETG shrinks the pocket onto the PCB
    # and elephant-foots its mouth (print review).
    pocket = box(-(EINK_PCB_W + 1.1) / 2, (EINK_PCB_W + 1.1) / 2,
                 -(EINK_PCB_H + 0.7) / 2, (EINK_PCB_H + 0.7) / 2,
                 z0, z0 + 9.0 - face_t)
    body -= pocket
    # ribbon cable exit
    body -= box(-9, 9, -h / 2 - 1, -(EINK_PCB_H / 2) + 2,
                z0, z0 + 9.0 - face_t)
    # viewing aperture, chamfered outward like a picture frame
    win = box(-EINK_WIN_W / 2, EINK_WIN_W / 2,
              -EINK_WIN_H / 2 + 2.0, EINK_WIN_H / 2 + 2.0,
              z0 + 4.0, z0 + 12.0)
    win = fillet(win.edges().filter_by(Axis.Z), 1.5)
    body -= win

    return attach_clip(body, width=26.0)


# --------------------------------------------------------------------------
# Part F - rail-mounted parts bin
# --------------------------------------------------------------------------
def rail_bin():
    """Wall-mounted parts bin. Its mouth faces up the panel, so the 20-degree
    lean tips the opening toward you rather than spilling."""
    # Shallow on purpose. At 32 mm proud its front lip reached Y=83, which is
    # 14 mm out over the tier bins below (they end at Y=97) -- you could not get
    # a hand into the bin underneath. 15 mm clears them. The deep storage is the
    # tier bins; this one holds whatever part you are working with right now, so
    # it trades depth for width and height.
    w = 58.0        # along the rail
    up = 46.0       # extent up the panel face
    out = 15.0      # how far it stands off the panel
    z0 = RAIL_TOP_Z
    y0, y1 = -up * 0.62, up * 0.38

    shell = box(-w / 2, w / 2, y0, y1, z0, z0 + out)
    shell = fillet(shell.edges().filter_by(Axis.Z), 3.0)

    cavity = box(-w / 2 + 2.4, w / 2 - 2.4, y0 + 2.6, y1 + 1,
                 z0 + 2.4, z0 + out - 2.4)
    cavity = fillet(cavity.edges().filter_by(Axis.Z), 2.0)
    shell -= cavity
    # drop the outward wall over most of the width so you can see and reach in
    scoop = box(-w / 2 + 2.4, w / 2 - 2.4, y0 + 16.0, y1 + 1,
                z0 + out - 6.0, z0 + out + 1)
    # 3.4, not 3.5: the cutter is 7.0 tall and a fillet at exactly half the
    # height is a tangent case OCCT rejects -- silently, until the helpers
    # learnt to talk.
    scoop = safe_fillet(scoop, scoop.edges().filter_by(Axis.X), 3.4)
    shell -= scoop

    return attach_clip(shell, width=30.0)


# --------------------------------------------------------------------------
# Part G - universal display mount (open H-frame, hole-mounted displays)
# --------------------------------------------------------------------------
def display_bar(length, slot_reach, holes):
    """Common bar stock for the mount's uprights and crossbars.

    A T-slot bar, printed FLAT so both the through-slot and the nut channel
    get bed-quality widths -- the print review showed slots printed across
    layers under a bridged ceiling bind on M3 (board_plate finding 21), and
    these slots are the whole mechanism. Front face (z=0) is the bed face
    and the clamp face; the square-nut channel opens through BOTH bar ends
    on the back, which is where nuts enter. The through-slot keeps closed
    ends on purpose: run it out and the bar falls into two strips.
    """
    bar = box(-length / 2, length / 2, -DM_BAR_W / 2, DM_BAR_W / 2,
              0, DM_BAR_T)
    bar = fillet(bar.edges().filter_by(Axis.Z), 3.0)
    bar -= box(-slot_reach, slot_reach, -DM_SLOT_OFF - DM_SLOT_W / 2,
               -DM_SLOT_OFF + DM_SLOT_W / 2, -1, DM_BAR_T + 1)
    bar -= box(-length / 2 - 1, length / 2 + 1,
               -DM_SLOT_OFF - DM_NUT_W / 2, -DM_SLOT_OFF + DM_NUT_W / 2,
               DM_BAR_T - DM_NUT_T, DM_BAR_T + 1)
    # Fixed crossing holes, counterbored so the pan head sinks below the
    # front face -- the display's back lies ON that face, and a proud head
    # would hold it off (the same class of failure as the rail screws that
    # once stood proud under the clips).
    for hx, hy in holes:
        bar -= Pos(hx, hy, DM_BAR_T / 2) * Cylinder(1.7, DM_BAR_T + 2)
        bar -= Pos(hx, hy, 1.3) * Cylinder(3.25, 2.6)
    return bar


def display_upright(length=None):
    """Vertical riser, TWO of the same print: the -90-rotated placement of
    the second one maps its slot/hole lines to the mirrored positions, so
    the part needs no handed twin (unlike the end frames).

    The bar mounts OFF-CENTRE: it rides DM_UPRIGHT_RISE above the rail so
    its bottom end clears the deck (centred, it speared 27 mm through it).
    Four fixed holes, not two -- the engaged pair sits RISE -/+ 12 below
    the bar centre; the mirrored pair keeps the bar symmetric so one part
    serves both sides, and doubles as the flip option: rotate the bar
    180 deg in plane and a display hangs BELOW the rail instead of above.
    """
    length = DM_UPRIGHT_L if length is None else length
    return display_bar(length, slot_reach=(length - 20.0) / 2,
                       holes=[(sx * (DM_UPRIGHT_RISE + sp * DM_BOSS_PITCH / 2),
                               DM_HOLE_OFF)
                              for sx in (-1, 1) for sp in (-1, 1)])


def display_crossbar():
    """Horizontal display bar, two of the same print. Its fixed holes land
    on the uprights' slot lines; its own slot line carries the display."""
    return display_bar(DM_CROSS_L, slot_reach=DM_CROSS_L / 2 - 6.0,
                       holes=[(sx * DM_CROSS_HOLE_X, DM_HOLE_OFF)
                              for sx in (-1, 1)])


def display_spine():
    """The mount's only rail-facing part: a plate on TWO clips (450 g needs
    a couple, not a pin), with four gabled bosses the uprights screw to --
    front-entry M3 x 12 self-tap, the dedicated-plate idiom, because these
    four holes are KNOWN and known holes need no nuts."""
    w, h = DM_SPINE_W, DM_SPINE_H
    plate = box(-w / 2, w / 2, -h / 2, h / 2, RAIL_TOP_Z, RAIL_TOP_Z + 3.0)
    plate = fillet(plate.edges().filter_by(Axis.Z), 3.0)

    # Bosses gabled +y, exactly like board_plate: pose is -90, print-down
    # is +y. Pilots are cut LAST, below.
    k = 3.5 / math.sqrt(2.0)
    roof = make_face(Polyline((-k, k), (0.0, 3.5 * math.sqrt(2.0)),
                              (k, k), close=True))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * DM_BOSS_X, sy * DM_BOSS_PITCH / 2
            boss = extrude(Circle(3.5), 4.5) + extrude(roof, 4.5)
            plate += Pos(cx, cy, RAIL_TOP_Z + 2.5) * boss

    # Two clips: union BOTH before cutting EITHER relief -- a clip unioned
    # after a relief cut re-fills it, the exact re-weld that once shipped
    # springless clips (see attach_clip).
    for cx in (-DM_CLIP_X, DM_CLIP_X):
        plate += Pos(cx, 0, 0) * din_clip(width=30.0)
    for cx in (-DM_CLIP_X, DM_CLIP_X):
        plate -= Pos(cx, 0, 0) * clip_relief(width=30.0)

    # Boss pilots AFTER the clips: the bosses stand over the clip back
    # plates, and a pilot cut first gets re-filled through the plate band
    # when the clip unions in -- the re-weld failure yet again, caught by
    # the screws.py boss audit at 4.0 mm depth instead of 6.4. Pilots stop
    # 0.6 above the back face (a proud tip would hold the clip off the
    # lips); screws.py audits depth and back skin both.
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate -= Pos(sx * DM_BOSS_X, sy * DM_BOSS_PITCH / 2,
                         RAIL_TOP_Z + 6.6) * Cylinder(1.25, 12)
    return plate


def display_post():
    """Display mount v2: ONE part, printed twice, clipped on twice.

    The v1 H-frame (spine + 2 uprights + 2 crossbars, ~63 cm3) existed
    because the uprights sat at a fixed spacing and needed something to
    bolt to. The DIN rail already solves both: a post is a T-slot bar with
    its own clip at the foot, and you clip two of them on at whatever
    spacing the display's holes want -- x-adjustment from the rail, y from
    the slot, no spine, no crossbars. Display screws run through the flange
    into the centred slot with captive square nuts, end-loaded at the top.
    The foot flares to the clip plate's 30 mm so post and clip read as one
    piece, and so it stands on a real face when printed on edge (+90; the
    release tab floats 1.1 above the bed like every clip module -- waived).
    Foot reaches y=-28: s=10 above the deck on both variants, and lower
    than the tab so the part never stands on the tab (the bezel's old B4).
    """
    T, W_FOOT, W_BAR = DM_POST_T, 30.0, 14.0
    z0 = RAIL_TOP_Z
    prof = make_face(Polyline(
        (-W_FOOT / 2, -28.0), (W_FOOT / 2, -28.0), (W_FOOT / 2, 10.0),
        (W_BAR / 2, 18.0), (W_BAR / 2, DM_POST_TOP), (-W_BAR / 2, DM_POST_TOP),
        (-W_BAR / 2, 18.0), (-W_FOOT / 2, 10.0), close=True))
    bar = Pos(0, 0, z0) * extrude(prof, T)
    bar = safe_fillet(bar, bar.edges().filter_by(Axis.Z)
                      .filter_by(lambda e: abs(e.center().Y - DM_POST_TOP)
                                 < 0.1 or abs(e.center().Y + 28.0) < 0.1), 3.0)
    # centred through-slot for the display screws; nut channel at the back
    # (panel side), open at the top end for loading
    bar -= box(-DM_SLOT_W / 2, DM_SLOT_W / 2, DM_POST_SLOT0, DM_POST_TOP - 8.0,
               z0 - 1, z0 + T + 1)
    bar -= box(-DM_NUT_W / 2, DM_NUT_W / 2, DM_POST_SLOT0, DM_POST_TOP + 1,
               z0 - 1, z0 + DM_NUT_T)
    return attach_clip(bar, width=30.0)


def display_mount_placed(parts=None):
    """The five pieces in module-local coordinates, ready for to_panel /
    to_post. z-stack: plate 3 + boss 4 + upright 6 + crossbar 6 -- the
    display's back lands 19 mm off the rail crown. Both variants place
    this dict, so the stack can only be wrong in one place. Pass a built
    PARTS dict to reuse its solids instead of rebuilding them."""
    parts = parts or {}
    up = parts.get("display_upright") or display_upright()
    cross = parts.get("display_crossbar") or display_crossbar()
    z_up = RAIL_TOP_Z + 7.0
    z_cross = z_up + DM_BAR_T
    rise = DM_UPRIGHT_RISE
    return {
        "dspine": parts.get("display_spine") or display_spine(),
        # +90 / -90 in plane: one printed part serves both sides. Bars sit
        # RISE above the rail so their bottom ends clear the deck; the
        # engaged hole pair lands back on the spine bosses at y = +/-12.
        "dupright0": Pos(DM_UPRIGHT_X, rise, z_up) * Rot(0, 0, 90) * up,
        "dupright1": Pos(-DM_UPRIGHT_X, rise, z_up) * Rot(0, 0, -90) * up,
        "dcross0": Pos(0, DM_CROSS_STATIONS[0], z_cross) * cross,
        "dcross1": Pos(0, DM_CROSS_STATIONS[1], z_cross) * cross,
    }


# --------------------------------------------------------------------------
# assembly + export
# --------------------------------------------------------------------------
def module_on_rail(part, x, extra_s=0.0):
    """Place a clip-mounted module onto the panel rail at position x."""
    return to_panel(part, x_centre=x, s=RAIL_S + extra_s)


PARTS = {}


def build():
    print("  base body ...", flush=True)
    PARTS["base_body"] = base_body()
    print("  din rail ...", flush=True)
    PARTS["din_rail"] = din_rail()
    print("  breadboard carrier ...", flush=True)
    PARTS["breadboard_carrier"] = breadboard_carrier()
    print("  board plates ...", flush=True)
    PARTS["board_plate_esp"] = board_plate("esp")
    PARTS["board_plate_pi"] = board_plate("pi")
    print("  screen bezel ...", flush=True)
    PARTS["screen_bezel"] = screen_bezel()
    print("  rail bin ...", flush=True)
    PARTS["rail_bin"] = rail_bin()
    print("  display mount ...", flush=True)
    PARTS["display_spine"] = display_spine()
    PARTS["display_upright"] = display_upright()
    PARTS["display_crossbar"] = display_crossbar()
    PARTS["display_post"] = display_post()      # mount v2, print x2
    return PARTS


def export_all():
    stl_dir = os.path.join(OUT, "stl")
    step_dir = os.path.join(OUT, "step")
    asm_dir = os.path.join(OUT, "assembly")
    for d in (stl_dir, step_dir, asm_dir):
        os.makedirs(d, exist_ok=True)
        # Purge first, same lesson frame.py learnt: a pose that stops being
        # emitted leaves its last STL behind, and every downstream tool
        # reads it as current (that is how the retired asm_plate/asm_screen
        # poses would otherwise haunt the renders).
        for f in os.listdir(d):
            if f.endswith((".stl", ".step")):
                os.remove(os.path.join(d, f))

    for name, part in PARTS.items():
        export_stl(part, os.path.join(stl_dir, f"{name}.stl"), tolerance=0.02,
                   angular_tolerance=0.1)
        try:
            export_step(part, os.path.join(step_dir, f"{name}.step"))
        except Exception as exc:
            print(f"    ! STEP failed for {name}: {exc}")
        print(f"    {name}: {part.volume / 1000:.1f} cm3  {part.bounding_box()}")

    # Assembly poses, exported separately so the renderer can colour them.
    # PROTOTYPE SWAP: the display mount occupies the rail span the board
    # plate and bezel used to sit on (48..228), so those two are out of the
    # assembly views for now. Their part exports above are untouched --
    # nothing is lost, they are just not shown on the rail.
    placed = {
        "asm_base": PARTS["base_body"],
        "asm_rail": to_panel(PARTS["din_rail"]),
        "asm_bin": module_on_rail(PARTS["rail_bin"], MOD_X_BIN),
        **{f"asm_{k}": module_on_rail(v, MOD_X_DISPLAY)
           for k, v in display_mount_placed(PARTS).items()},
    }
    for name, part in placed.items():
        export_stl(part, os.path.join(asm_dir, f"{name}.stl"), tolerance=0.02,
                   angular_tolerance=0.1)

    # Parts-family layout: everything you print, spread out on one ground plane.
    lay_dir = os.path.join(OUT, "layout")
    os.makedirs(lay_dir, exist_ok=True)
    for f in os.listdir(lay_dir):
        if f.endswith(".stl"):
            os.remove(os.path.join(lay_dir, f))
    layout = {
        "lay_base": Pos(0, 118, 0) * Pos(-BENCH_W / 2, -BENCH_D / 2, 0) *
        PARTS["base_body"],
        "lay_rail": Pos(0, 26, 0) * PARTS["din_rail"],
        "lay_carrier": Pos(-158, -46, 0) * PARTS["breadboard_carrier"],
        "lay_plate": Pos(-58, -46, 0) * PARTS["board_plate_esp"],
        "lay_bezel": Pos(35, -46, 0) * PARTS["screen_bezel"],
        "lay_bin": Pos(126, -46, 0) * PARTS["rail_bin"],
        # Display mount family: bars lie flat as printed; the spine keeps
        # the module family's face-up layout pose.
        "lay_dspine": Pos(-100, -102, 0) * PARTS["display_spine"],
        "lay_dupright": Pos(30, -102, 0) * PARTS["display_upright"],
        "lay_dcross": Pos(30, -128, 0) * PARTS["display_crossbar"],
    }
    for name, part in layout.items():
        export_stl(part, os.path.join(lay_dir, f"{name}.stl"), tolerance=0.02,
                   angular_tolerance=0.1)
    print(f"  wrote {len(PARTS)} parts, {len(placed)} assembly poses, "
          f"{len(layout)} layout poses")


if __name__ == "__main__":
    print("building Breadboard Bench ...")
    build()
    export_all()
    print("done.")
