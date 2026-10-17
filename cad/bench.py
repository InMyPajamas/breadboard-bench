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
    x1 = width / 2 - 1.0                   # full-width latch, as din_clip()
    # Out to x1 + 0.6: past the latch tip so it is free, but short of the
    # clip's end so the slice never notches the module body beyond it.
    c = box(x0 + 4.0, x1 + 0.6, -outer - 1, -inner + 0.25,
            RAIL_TOP_Z - 0.9, RAIL_TOP_Z + 0.9)
    # ...and the same slice over the RELEASE TAB, all the way out. The tab
    # stands CLIP_TAB_REACH past the jaw, the slot above stopped 1 mm past
    # it, and any module plate wider than the jaw (every one of them) then
    # met the tab's top face and welded the latch's FREE END to the plate:
    # a finger held at both ends is not a spring. Plate 03, 2026-10-05: all
    # four clips slid on from the end and none would rock on -- "trying to
    # get that clip to move basically would break the tab holding the clip
    # to the piece." On the gauge the weld was 6 x 1.1 mm; on a real module
    # it would have been the tab's whole top. attach_clip() now asserts it.
    c += box(x1 - 6.0 - 0.6, x1 + 0.6, -(outer + CLIP_TAB_REACH) - 1, -outer - 0.9,
             RAIL_TOP_Z - 0.9, RAIL_TOP_Z + 0.9)
    # Round the slot's ROOT end -- the machinist's drilled-slot-end move.
    # A square-ended relief slot is a crack starter at the latch root, and
    # the post-hoc fillet that used to soften it was an OCCT edge-filter
    # blend that failed on every module (exact-half tangency on the slot's
    # 1.6 cross edges). Rounding the CUTTER cannot fail to build, and both
    # cuts of this slot (din_clip and attach_clip's re-cut) inherit it.
    c = safe_fillet(c, c.edges().filter_by(Axis.Y).group_by(Axis.X)[0], 0.85)
    return c


def attach_clip(body, width=CLIP_W, fit=None, latch_t=None, latch=True):
    """Union the clip onto a module, then re-cut the relief. Modules must use
    this rather than `body + din_clip(...)`. latch=False: hook and plate
    only -- the module holds its foot down some other way (display_post)."""
    if not latch:
        return body + din_clip(width, fit, latch_t, latch=False)
    out = (body + din_clip(width, fit, latch_t)) - clip_relief(width, fit)
    # The latch must touch the module at its ROOT and nowhere else. Probe the
    # plane just under the plate along the finger and across the tab: any
    # solid there is a weld, and a welded latch prints, looks right, and
    # cannot be used. (Clip-local coordinates; callers place it afterwards.)
    f = RAIL_FIT if fit is None else fit
    inner = RAIL_LIP_W / 2 + f
    outer = inner + CLIP_JAW_T
    x0 = -width / 2
    x1 = width / 2 - 1.0                   # full-width latch (2026-10-10)
    z = RAIL_TOP_Z - 0.05
    probes = [(x, -inner - 0.8) for x in (x0 + 6.0, x0 + 10.0, (x0 + x1) / 2 + 2.0,
                                          x1 - 4.0, x1 - 1.0)]
    probes += [(x1 - 3.0, -outer - d) for d in (0.5, 1.5, 2.5, 4.0, CLIP_TAB_REACH - 0.3)]
    welded = [p for p in probes if out.is_inside(Vector(p[0], p[1], z))]
    if welded:
        raise SystemExit(f"attach_clip: latch welded to the module at {welded}; "
                         "the relief slot does not reach it")
    return out


def din_clip(width=CLIP_W, fit=None, latch_t=None, latch=True):
    """Hook-and-rock clip: one rigid hook, one sprung latch.

    The previous version was two symmetric cantilevers, each asked to deflect
    2.45 mm over a beam 4.05 mm long and 3.2 mm thick. That is L/t = 1.3 and
    72% strain, against a PETG yield of about 4% -- a block, not a spring. It
    could not have gone on, and forcing it would have broken the module. Two of
    the three clips had no spring at all besides, because the module body
    re-welded the relief slot downstream.

    Real DIN accessories hook one lip and rotate on. That drops the deflection
    below 1 mm, and it lets the latch run ALONG the rail where there is room for
    a real beam. (It was 18 x 1.6 with a 7 mm FREE span, about 10% strain; now
    the full clip width at CLIP_LATCH_T, an 18 mm free span on a 30 mm clip,
    about 1.9% -- see params.py.) It also flexes in the module's local Y, which keeps the bending
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
    if not latch:
        return clip

    # --- sprung latch, -y. Runs along the rail, so it can be long. --------
    # Full width, not 18 mm capped (2026-10-10, see CLIP_LATCH_T): the free
    # beam from root to tooth is what bends, and at 7 mm it could only yield.
    LT, ROOT = (CLIP_LATCH_T if latch_t is None else latch_t), 4.0
    x0 = -width / 2
    x1 = width / 2 - 1.0
    clip += box(x0, x1, -inner - LT, -inner, tooth_bot - 0.6, RAIL_TOP_Z)
    clip += box(x1 - 7.0, x1, -inner, -(inner - CLIP_TOOTH),
                tooth_bot, tooth_top)
    # Lead-in on the latch tooth: a 1.5 x 45 chamfer on its inner-bottom
    # arris, the edge that meets the rail lip during rock-on. Plate 03,
    # 2026-10-05: the chamfered clip "rocks on easier" than its square twin
    # at the same clearance, so it is standard on every clip (was the
    # coupon's fourth member only). Cut as a wedge along the tooth's length.
    yi = -(inner - CLIP_TOOTH)
    wedge = make_face(Polyline((yi + 0.01, tooth_bot - 0.01), (yi - CLIP_LEAD_IN, tooth_bot - 0.01),
                               (yi + 0.01, tooth_bot + CLIP_LEAD_IN), close=True))
    clip -= Pos(x1 - 7.5, 0, 0) * Rot(0, 90, 0) * Rot(0, 0, 90) * extrude(wedge, 8.0)

    # Free the finger from the back plate everywhere but its root. Without
    # this it is not a cantilever, just a thickening of the plate -- which is
    # exactly what the old relief slot became once the module body closed it.
    clip -= clip_relief(width, fit)

    # Root crack relief now lives in clip_relief() itself -- the slot end
    # is rounded in the cutter, so there is no post-hoc blend to fail.

    # Release tab on the sprung tip, so you lever the latch rather than the
    # hook. Doubles as the visual cue for which side comes off.
    # Its top stops 0.9 SHORT of the module face (the relief slot's own gap),
    # so the tab cannot weld to a plate even where a caller unions this clip
    # on directly instead of going through attach_clip().
    # It runs THROUGH the finger to the finger's inner face. It used to stop
    # 0.4 into the finger's outer face, so its whole root was a 6 x 0.4 x 2.5
    # sliver: the tab was really hanging on the weld to the plate, and on
    # plate 03 every tab snapped at the first lever once that weld was cut
    # (2026-10-05, white stress marks at the root in the user's photo). Now
    # the root is the finger's full 1.6 mm section.
    tab = box(x1 - 6.0, x1, -(outer + CLIP_TAB_REACH), -inner,
              RAIL_TOP_Z - 3.4, RAIL_TOP_Z - 0.9)
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
    # Full foot width up to 21.5, past the clip plate's top edge (20.8), then
    # a 45-degree taper (2026-10-17). Printed face down, a taper starting at
    # 10 left 108 mm2 of the 30-wide clip plate hanging 2 mm over air; full
    # width there also puts the most section where the screen's moment peaks.
    prof = make_face(Polyline(
        (-W_FOOT / 2, -28.0), (W_FOOT / 2, -28.0), (W_FOOT / 2, 21.5),
        (W_BAR / 2, 29.5), (W_BAR / 2, DM_POST_TOP), (-W_BAR / 2, DM_POST_TOP),
        (-W_BAR / 2, 29.5), (-W_FOOT / 2, 21.5), close=True))
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
    # No spring latch (2026-10-17, both broke in service -- see DM_LOCK_Y):
    # hook and plate only, and the foot is held down by the twist lock, whose
    # shaft turns in this bore.
    post = attach_clip(bar, width=30.0, latch=False)
    post -= Pos(0, DM_LOCK_Y, z0 - 1) * Cylinder(
        DM_LOCK_SHAFT_R + 0.3, T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return post


def display_lock():
    """The twist lock's hook WITH its shaft, one part (2026-10-17, screwless).
    Same frame as display_post, drawn LOCKED: the tooth points up the post,
    2.2 under the rail's lower lip like the clip hook's own tooth, its top a
    wedge (DM_LOCK_WEDGE) low on the leading (+x) edge so the clockwise turn
    finishes snug. A hex hub behind the foot; a shaft up through the foot's
    bore; a hex above the front face for the knob to drive; a split tip whose
    two barbs click through the knob's neck. Prints lying on its side, tooth
    up, flat DM_LOCK_FLAT under the axis: the prongs then flex in the layer
    plane, and the shaft carries its tension along the layers.
    """
    ya = DM_LOCK_Y
    reach = RAIL_LIP_W / 2 + RAIL_FIT - CLIP_TOOTH          # 15.375
    r_tip = -reach - ya
    z0, zt = DM_LOCK_Z0, RAIL_TOP_Z - 0.15                  # 0.15 under the foot
    zf = RAIL_TOP_Z + DM_POST_T                             # the foot's front
    C = (Align.CENTER, Align.CENTER, Align.MIN)
    # hub: a hexagon (corners at DM_LOCK_HUB_R, clear of the lip at any turn),
    # flat down when printed on its side
    hub = Pos(0, ya, z0) * extrude(Rot(0, 0, 30) * RegularPolygon(DM_LOCK_HUB_R, 6), zt - z0)
    a, R = math.radians(DM_LOCK_HALF), r_tip + 3.0
    pie = make_face(Polyline((0, 0), (R * math.sin(a), R * math.cos(a)), (0, 1.5 * R),
                             (-R * math.sin(a), R * math.cos(a)), close=True))
    sector = (Circle(r_tip) - Circle(DM_LOCK_TOOTH_IN)) & pie
    lo, hi = DM_LOCK_WEDGE
    tooth = Pos(0, ya, z0) * extrude(sector, hi - z0 + 1.0)
    half_w = r_tip * math.sin(a)
    tilt = math.degrees(math.atan((hi - lo) / (2 * half_w)))
    tooth -= Pos(0, ya, (lo + hi) / 2) * Rot(0, tilt, 0) * Box(60, 60, 10, align=C)
    lock = hub + tooth
    lock += Pos(0, ya, zt) * Cylinder(DM_LOCK_PIN_R, zf - zt, align=C)
    zk = zf + DM_LOCK_KEY_L
    lock += Pos(0, ya, zf) * extrude(Rot(0, 0, 30) * RegularPolygon(DM_LOCK_KEY_AF / math.sqrt(3), 6),
                                     DM_LOCK_KEY_L)
    # split, barbed tip: prongs r_p, barbs only on the two flexing (+-x)
    # sides, square shoulder down, 45-degree lead-in up
    r_p, r_b, r_n = DM_LOCK_BARB
    neck_t = 1.2
    sh = zk + neck_t + 0.05                                 # barb shoulder
    tip = sh + 1.4
    lock += Pos(0, ya, zk) * Cylinder(r_p, tip - zk, align=C)
    for sx in (-1, 1):
        barb = make_face(Polyline((sx * (r_p - 0.6), sh), (sx * r_b, sh), (sx * r_b, sh + 0.6),
                                  (sx * (r_p - 0.6), tip), close=True))
        lock += Pos(0, ya + 1.0, 0) * (Rot(90, 0, 0) * extrude(barb, 2.0))
    lock -= Pos(0, ya, zf + 0.6) * Box(DM_LOCK_SLOT, 20, 20, align=C)
    # printed on its side: one flat 2.6 under the axis (the -y side; the tooth
    # points +y, up)
    lock -= Pos(0, ya - DM_LOCK_FLAT - 10, 0) * Box(40, 20, 80, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    return lock


def display_lock_knob():
    """The twist lock's thumb wing (2026-10-17, screwless): long axis up the
    post when LOCKED (as drawn), across it when open. Pushes down over the
    lock's hex and clicks onto its barbs through a neck hole; the barbs sit in
    a counterbore, flush with the top. Prints as drawn, underside down."""
    ya = DM_LOCK_Y
    zf = RAIL_TOP_Z + DM_POST_T
    w, l, h = DM_LOCK_KNOB
    zb = zf + 0.1                                           # 0.1 off the front face
    C = (Align.CENTER, Align.CENTER, Align.MIN)
    blk = Pos(0, ya, zb) * Box(w, l, h, align=C)
    blk = safe_fillet(blk, blk.edges().filter_by(Axis.Z), w / 2 - 0.3)
    blk = safe_chamfer(blk, blk.edges().group_by(Axis.Z)[-1], 0.8)
    zk = zf + DM_LOCK_KEY_L
    r_p, r_b, r_n = DM_LOCK_BARB
    knob = blk - Pos(0, ya, zb - 1) * extrude(
        Rot(0, 0, 30) * RegularPolygon((DM_LOCK_KEY_AF + 0.2) / math.sqrt(3), 6), zk - zb + 1)
    knob -= Pos(0, ya, zk - 0.5) * Cylinder(r_n, 3.0, align=C)
    knob -= Pos(0, ya, zk + 1.2) * Cylinder(r_b + 0.4, h, align=C)
    return knob


def hirth(n, r_in, r_out, h, phase_deg=0.0):
    """n radial V-teeth on the XY plane, crests rising to z = h: tooth k's
    crest runs out along angle phase + k * 360/n, its roots on the half-pitch
    lines either side. Two sets, one turned half a pitch and facing the other,
    mesh crest-in-root: the indexing face of the tilt adapter's hinge."""
    a = math.pi / n
    teeth = None
    for k in range(n):
        secs = []
        for r in (r_in, r_out):
            pts = [Vector(r * math.cos(a), r * math.sin(a), 0.0),
                   Vector(r * math.cos(a), -r * math.sin(a), 0.0),
                   Vector(r, 0.0, h)]
            secs.append(Wire.make_polygon(pts, close=True))
        t = Rot(0, 0, phase_deg + math.degrees(2 * a * k)) * Solid.make_loft(secs)
        teeth = t if teeth is None else teeth + t
    return teeth


def din_tilt_base():
    """DIN tilt adapter, the part on the rail (2026-10-17). The display post's
    foot and interface verbatim -- hook over the top lip, no latch, the twist
    lock's bore -- so the same lock knob and hook hold it down. On the foot, the
    hinge's fixed knuckle: a disc round DTA_HINGE, solid from the foot's +x end
    to its toothed face at DTA_BASE_FACE, so it prints with that face up. The
    M3 x 20's head drops down a 5.6 well from the +x end and presses into a
    seat 7 mm short of the teeth.
    """
    z0 = RAIL_TOP_Z
    foot = box(-15.0, 15.0, -28.0, 21.5, z0, z0 + DM_POST_T)
    foot = safe_fillet(foot, foot.edges().filter_by(Axis.Z), 2.0)
    base = attach_clip(foot, width=30.0, latch=False)
    base -= Pos(0, DM_LOCK_Y, z0 - 1) * Cylinder(
        DM_LOCK_SHAFT_R + 0.3, DM_POST_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    yh, zh = DTA_HINGE
    x0, x1 = DTA_BASE_FACE, 15.0
    disc = Pos(x0, yh, zh) * Rot(0, 90, 0) * Cylinder(
        DTA_KNUCKLE_R, x1 - x0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    ear = box(x0, x1, yh - DTA_KNUCKLE_R, yh + DTA_KNUCKLE_R, z0 + DM_POST_T - 0.5, zh)
    base += disc + ear
    # teeth on the -x face, pointing -x: local Z -> world -x
    # phased so the arm meshes at FLAT (-DTA_FLAT) and every 15 from there
    base += Pos(x0, yh, zh) * Rot(0, -90, 0) * hirth(
        DTA_TEETH, *DTA_TOOTH_R, DTA_TOOTH_H, phase_deg=DTA_FLAT % (360.0 / DTA_TEETH))
    # the screw: 3.4 bore along the axis, the head's well from the +x end,
    # its seat (5.4, a press on a 5.5 head) 7 mm from the teeth
    seat = x0 + 7.0
    base -= Pos(x0 - 3, yh, zh) * Rot(0, 90, 0) * Cylinder(
        1.7, x1 - x0 + 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    base -= Pos(seat, yh, zh) * Rot(0, 90, 0) * Cylinder(
        2.7, 3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    base -= Pos(seat + 3.0, yh, zh) * Rot(0, 90, 0) * Cylinder(
        2.85, x1 - seat, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return base


def din_tilt_arm(angle=0.0):
    """DIN tilt adapter, the moving half: the hinge's toothed knuckle at the
    -x end, a carrier plate, and a DTA_STUB_L TS35 stub that real DIN devices
    clip onto. Drawn at `angle` degrees about the hinge (0 = parallel to the
    bench rail; -53 = flat, stub face straight up). Prints standing on its
    knuckle's outer face: teeth up, everything else rising off them.
    """
    yh, zh = DTA_HINGE
    xa0, xa1 = DTA_ARM_X
    R = DTA_KNUCKLE_R
    knuckle = Pos(xa0, yh, zh) * Rot(0, 90, 0) * Cylinder(
        R, xa1 - xa0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    zc = zh + R + 0.3                                  # carrier underside
    knuckle += box(xa0, xa1, yh - R, yh + R, zh, zc + DTA_CARRIER_T)
    arm = knuckle + box(xa0, xa0 + DTA_STUB_L, yh - 17.5, yh + 17.5, zc, zc + DTA_CARRIER_T)
    stub = din_rail(length=DTA_STUB_L)
    arm += Pos(xa0 + DTA_STUB_L / 2, yh, zc + DTA_CARRIER_T) * stub
    # teeth on the +x face, pointing +x, half a pitch round from the base's
    arm += Pos(xa1, yh, zh) * Rot(0, 90, 0) * hirth(
        DTA_TEETH, *DTA_TOOTH_R, DTA_TOOTH_H, phase_deg=180.0 / DTA_TEETH)
    arm -= Pos(xa0 - 1, yh, zh) * Rot(0, 90, 0) * Cylinder(
        1.7, xa1 - xa0 + 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if angle:
        arm = Pos(0, yh, zh) * Rot(angle, 0, 0) * Pos(0, -yh, -zh) * arm
    return arm


def din_tilt_knob():
    """The tilt adapter's thumb knob: a knurled disc outside the arm's
    knuckle with an M3 nut pressed into its outer face. Loosen ~3 turns to
    lift the teeth apart, swing the stub, tighten. Prints outer face down."""
    yh, zh = DTA_HINGE
    r, t = DTA_KNOB
    xo = DTA_ARM_X[0] - t
    k = Pos(xo, yh, zh) * Rot(0, 90, 0) * Cylinder(
        r, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for i in range(12):                                # grip flutes
        a = math.radians(i * 30)
        k -= Pos(xo - 1, yh + r * math.sin(a), zh + r * math.cos(a)) * Rot(0, 90, 0) * \
            Cylinder(1.2, t + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    k -= Pos(xo - 1, yh, zh) * Rot(0, 90, 0) * Cylinder(
        1.7, t + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    k -= Pos(xo - 1, yh, zh) * Rot(0, 90, 0) * extrude(
        RegularPolygon(DBP_NUT_AF / math.sqrt(3), 6), 2.6 + 1)
    return k


def display_backplate():
    """Backplate for the CrowPanel Advanced 7" ESP32-P4 (2026-10-15).

    The screen's only mounting holes are four corner slots 171 x 98 apart;
    the posts stand 100 apart, so screws through the posts would land on the
    components. This open frame bridges the two: its two vertical bars
    screw to the posts (M3 x 8 cap, heads in flush counterbores on the
    FRONT, into the posts' captured square nuts), and four corner bosses
    take the screen (M3 x 16 cap from the front through its corner slots,
    into nuts pressed into the bosses' backs -- 2026-10-17).
    The bosses hold the PCB DBP_STANDOFF off the bars, clear of the 8.1 mm
    parts on its back; the middle stays open for cables and the connectors.

    Module-local, like display_post: x along the rail, y up (0 = screen
    centre), z = n out from the rail face, back face on the posts' front
    face (RAIL_TOP_Z + DM_POST_T). Prints back-face down: everything rises
    from the bed, counterbores open upward, no support.
    """
    zb = RAIL_TOP_Z + DM_POST_T                   # back face, on the posts
    zf_bar = zb + DBP_BAR_T                       # bars' front face
    zf_rim = zb + DBP_RIM_T
    z_pcb = zf_bar + DBP_STANDOFF                 # PCB back face
    hx, hy = CP7_HOLE_X, CP7_HOLE_Z
    # perimeter rim on the hole centrelines
    rim = box(-hx - DBP_RIM_W / 2, hx + DBP_RIM_W / 2, -hy - DBP_RIM_W / 2,
              hy + DBP_RIM_W / 2, zb, zf_rim)
    rim -= box(-hx + DBP_RIM_W / 2, hx - DBP_RIM_W / 2, -hy + DBP_RIM_W / 2,
               hy - DBP_RIM_W / 2, zb - 1, zf_rim + 1)
    plate = safe_fillet(rim, rim.edges().filter_by(Axis.Z), 2.0)
    for sx in (-1, 1):
        bar = box(sx * DBP_BAR_X - DBP_BAR_W / 2, sx * DBP_BAR_X + DBP_BAR_W / 2,
                  -hy - DBP_RIM_W / 2, hy + DBP_RIM_W / 2, zb, zf_bar)
        plate += bar
    # Corner bosses, BOLTED (2026-10-17, see DBP_BOSS_R): full height from
    # the bed, a clearance bore, and a pressed nut in a hex pocket in the
    # back. The old 6.4 bosses round a self-tap pilot split and sheared.
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate += Pos(sx * hx, sy * hy, zb) * Cylinder(
                DBP_BOSS_R, z_pcb - zb, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sx in (-1, 1):
        for sy in (-1, 1):
            at = (sx * hx, sy * hy)
            ceil = zb + DBP_NUT_DEPTH
            plate -= Pos(*at, zb - 1) * extrude(
                RegularPolygon(DBP_NUT_AF / math.sqrt(3), 6), DBP_NUT_DEPTH + 1)
            # one sacrificial layer over the nut: the pocket ceiling prints
            # as a plain bridge, and the screw punches it on assembly
            plate -= Pos(*at, ceil + RAIL_CBORE_SKIN) * Cylinder(
                DBP_BORE_R, z_pcb, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # small lead at the top: the PCB's slot is 3.2, the bore 3.4
            plate -= Pos(*at, z_pcb - 0.5) * Cone(
                DBP_BORE_R, DBP_BORE_R + 0.6, 0.6,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
    # post screws: clearance through, cap-head counterbore on the FRONT
    for sx in (-1, 1):
        for py in DBP_POST_HOLES:
            plate -= Pos(sx * DBP_BAR_X, py, zb - 1) * Cylinder(
                1.7, DBP_BAR_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
            plate -= Pos(sx * DBP_BAR_X, py, zf_bar - 3.2) * Cylinder(
                3.0, 3.3, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # The mic crown's socket (2026-10-17): a block on the top rim's front with
    # a dovetail channel down it, open at the top end. Its top stays under
    # the screen's back parts (zb + 5.2 against 27.9 - 8.1).
    y0, y1 = DBP_SOCK_Y
    wc, wb = DBP_SOCK_W
    zfl = zb + DBP_SOCK_FLOOR
    blk = box(-wb / 2, wb / 2, y0, y1, zb, zfl + DBP_SOCK_D)
    blk = safe_fillet(blk, blk.edges().filter_by(Axis.Z).group_by(Axis.Y)[-1], 2.0)
    plate += blk
    # v2: the channel tapers, so the crown's tongue wedges as it seats
    plate -= sock_dovetail(0.0, zfl, DBP_SOCK_D + 1.0, y0 + 2.0, y1 + 1.0)
    return plate


def sock_hw(y):
    """The crown socket's half-width at its floor, at height y: tapered,
    DBP_SOCK_TAPER narrower each side at the closed end (y0 + 2) than at
    the mouth (y1)."""
    y0, y1 = DBP_SOCK_Y
    return DBP_SOCK_W[0] / 2 - DBP_SOCK_TAPER * (y1 - y) / (y1 - (y0 + 2.0))


def sock_dovetail(inset, z0, h, ya, yb, zlo=None):
    """The socket's tapered dovetail between ya and yb, inset each side, from
    the floor level z0 up h. zlo starts the solid higher (the tongue rides
    0.1 off the floor); the walls' lean is measured from z0 either way."""
    lean = math.tan(math.radians(DBP_SOCK_ANG))
    zl = z0 if zlo is None else zlo
    secs = []
    for y in (ya, yb):
        hb = sock_hw(y) - inset
        w0, w1 = hb - (zl - z0) * lean, hb - h * lean
        secs.append(Wire.make_polygon([Vector(-w0, y, zl), Vector(w0, y, zl),
                                       Vector(w1, y, z0 + h), Vector(-w1, y, z0 + h)],
                                      close=True))
    return Solid.make_loft(secs)


def y_prism(pts_xz, y0, y1):
    """A prism along y from y0 to y1 whose section is the polygon pts_xz,
    given as (x, z) pairs."""
    face = make_face(Polyline(*[(x, y1, z) for x, z in pts_xz], close=True))
    return extrude(face, y1 - y0, dir=(0, -1, 0))


def sector(r_in, r_out, a0, a1, z0, h, step=1.0):
    """Annular sector from angle a0 to a1 (degrees, 0 = +x), z0..z0 + h."""
    n = max(2, int(math.ceil(abs(a1 - a0) / step)) + 1)
    angs = [math.radians(a0 + (a1 - a0) * i / (n - 1)) for i in range(n)]
    pts = [(r_out * math.cos(a), r_out * math.sin(a), z0) for a in angs]
    pts += [(r_in * math.cos(a), r_in * math.sin(a), z0) for a in reversed(angs)]
    return extrude(make_face(Polyline(*pts, close=True)), h)


def mic_xy(x, y):
    """A point in the XVF3800 drawing's frame (board centre 0) -> crown x, y."""
    t = math.radians(MIC_TURN)
    return (x * math.cos(t) - y * math.sin(t), MIC_Y + x * math.sin(t) + y * math.cos(t))


def mic_crown():
    """Mic crown: a reSpeaker XVF3800 held above the screen (2026-10-17).

    One flat PETG part in the backplate's plane, no screws. Its foot is a
    tapered dovetail tongue that slides down the socket on the backplate's
    top rim and wedges tight as it seats (v2; the panel leans back, so the
    crown's own weight drives the wedge home). A stem flares into a ring
    behind the board -- one profile, its inside corners blended and its
    front edges chamfered like the rest of the bench. The board sits
    MIC_STANDOFF off the ring, logo face out, on three pads under its M2
    holes, pins in two of them so it cannot turn. Two fixed lips at the
    bottom and a sprung one at the top hold its edge: tuck the bottom edge
    under the fixed lips, press the top until the third clicks. The sprung
    lip stands on a beam cut free in the ring, so it flexes in the layer
    plane, never across the layers.

    Module-local like display_backplate: x along the rail, y up (screen
    centre 0), z = n out of the rail face. Prints back face down.
    """
    zb = RAIL_TOP_Z + DM_POST_T
    zfl = zb + DBP_SOCK_FLOOR
    zc = zfl + 0.1                                # back face, 0.1 off the socket floor
    zf = zc + CR_RING_T                           # ring's front face
    z_pcb = zf + MIC_STANDOFF                     # board's back
    z_lip = z_pcb + MIC_PCB_T + 0.1               # lips' underside
    yc = MIC_Y
    r0, r1 = CR_RING
    y0, y1 = DBP_SOCK_Y
    C = (Align.CENTER, Align.CENTER, Align.MIN)
    # one profile: the ring's disc and a stem flaring up into it
    s0, s1, ys = CR_STEM
    stem = extrude(make_face(Polyline((-s0, y1 + 0.5, zc), (s0, y1 + 0.5, zc), (s1, ys, zc),
                                      (s1, yc, zc), (-s1, yc, zc), (-s1, ys, zc), close=True)),
                   CR_RING_T)
    body = Pos(0, yc, zc) * Cylinder(r1, CR_RING_T, align=C) + stem
    # the inside corners, where the stem's flanks run into the ring's edge
    blend = [e for e in body.edges().filter_by(Axis.Z)
             if y1 + 1.0 < e.center().Y < ys and abs(e.center().X) > s0 + 0.5]
    body = safe_fillet(body, blend, CR_BLEND)
    foot = body.edges().filter_by(Axis.Z).filter_by_position(Axis.Y, y1, y1 + 1.0)
    body = safe_fillet(body, foot, 2.0)
    body -= Pos(0, yc, zc - 1) * Cylinder(r0, CR_RING_T + 2, align=C)
    body = safe_chamfer(body, body.edges().group_by(Axis.Z)[-1], CR_CHAMFER)
    # the tongue: the socket's taper, CR_SLIDE in on each side when seated
    crown = body + sock_dovetail(CR_SLIDE, zfl, CR_T + 0.1, y0 + 2.1, y1 + 1.0, zlo=zc)
    # pads under the M2 holes, each on a 45 deg foot; pins in two
    for i, (hx, hy) in enumerate(MIC_HOLES):
        px, py = mic_xy(hx, hy)
        crown += Pos(px, py, zf - 0.5) * Cylinder(3.5, MIC_STANDOFF + 0.5, align=C)
        crown += Pos(px, py, zf - 0.5) * Cone(5.5, 3.5, 2.5, align=C)
        if i in MIC_PINNED:
            pin = Pos(px, py, z_pcb - 0.5) * Cylinder(0.9, MIC_PCB_T + 0.9, align=C)
            crown += safe_chamfer(pin, pin.edges().group_by(Axis.Z)[-1], 0.3)
    # the lips: a column outside the board's edge, a lip over its face
    r_in = MIC_R + CR_EDGE_GAP
    cr, cw = CR_COL
    ov, lt = CR_LIP
    r_lip = MIC_R - ov

    def lip(theta, sprung):
        sec = [(r_lip, z_lip), (r_in + cr, z_lip), (r_in + cr, z_lip + lt),
               (r_in, z_lip + lt)]
        # the sprung lip gets a 45 deg lead-in: pressing the board cams it out
        sec.append((r_lip, z_lip + lt - (r_in - r_lip)) if sprung else (r_lip, z_lip + lt))
        part = box(r_in, r_in + cr, -cw / 2, cw / 2, zc, z_lip) + y_prism(sec, -cw / 2, cw / 2)
        if sprung:          # a pull tab on the outer half, to unlatch it
            part += box(r_in + cr / 2, r_in + cr, -cw / 2, cw / 2, z_lip, z_lip + lt + 2.5)
        part = safe_fillet(part, part.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], 1.0)
        return Pos(0, yc, 0) * Rot(0, 0, theta) * part

    for a in CR_HOOKS:
        crown += lip(a, False)
    # the sprung lip's beam: an arc slot inside it and a cut at its free end
    half = math.degrees((cw / 2) / r_in)
    a_end = CR_LATCH + half + 1.0
    crown -= Pos(0, yc, 0) * sector(MIC_R - 0.8, r_in, CR_LATCH_ANCHOR, a_end + 1.6,
                                    zc - 1, CR_RING_T + 2)
    crown -= Pos(0, yc, 0) * sector(MIC_R - 0.8, r1 + 1, a_end, a_end + 1.6,
                                    zc - 1, CR_RING_T + 2)
    crown += lip(CR_LATCH, True)
    return crown


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
    PARTS["display_lock"] = display_lock()             # the post's twist lock, x2
    PARTS["display_lock_knob"] = display_lock_knob()
    print("  DIN tilt adapter ...", flush=True)
    PARTS["din_tilt_base"] = din_tilt_base()
    PARTS["din_tilt_arm"] = din_tilt_arm()
    PARTS["din_tilt_knob"] = din_tilt_knob()
    print("  display backplate ...", flush=True)
    PARTS["display_backplate"] = display_backplate()   # CrowPanel P4
    print("  mic crown ...", flush=True)
    PARTS["mic_crown"] = mic_crown()                   # reSpeaker XVF3800
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
