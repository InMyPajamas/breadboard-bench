"""Pre-print sanity check: watertightness, overhangs, and unsupported area.

Slimming a part is only safe if it is still printable. This flags the two things
that bite after a thickness reduction -- meshes that stopped being manifold, and
downward-facing faces that now need support.
"""

import math
import os

import numpy as np
import trimesh

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
OVERHANG_LIMIT = 45.0     # degrees from vertical; steeper than this needs support

# Parts are modelled in assembly orientation, which is not how they print.
# Degrees of rotation about X to reach the print pose.
#   base_body  - sits on its own base already
#   din_rail   - FLAT, web on the bed. An earlier note here said 'on its side'
#                from a version whose section was inverted; the pose below is
#                0 and that is the one being validated.
#   modules    - face down, so the visible face gets the bed finish and the
#                clip jaws point up.
# Modules print ON EDGE (90), not face-down. The clip's sprung jaw is a
# cantilever whose beam axis is the module's local Z. Face-down puts print-Z
# along that axis, so every snap-on cycle loads the interlayer bond at the jaw
# root in pure tension -- the classic way printed snap-fits shear off. On edge,
# the same stress runs along the layers instead.
# Waived floating islands -- REAL, understood, and accepted with mitigation.
# The clip's hook tooth (and the bezel's release tab) begin mid-air in the
# on-edge pose: a tooth that reaches under the rail lip must protrude toward
# the bed with nothing beneath it, and no orientation fixes every feature at
# once -- flipping the module saves the hook tooth but floats the latch
# tooth, and standing it on end puts the latch spring's bending stress
# across the layers (the failure on-edge printing exists to avoid). The
# mitigation is in the README: enable supports ONLY in the clip channel (two
# small dabs per module), or split the clip per its bolt-on escape hatch.
_CLIP_WAIVER = "clip tooth/tab; print with two support dabs in the channel"
# Thin plates that are the POINT of the part: the magnet gauge prints the
# 0.6 mm skin the trays and bins rely on, so a gate that fails it would
# fail the thing it exists to test.
_PLATE_WAIVER = ("0.8 mm deck plates by design: four 0.2 layers, rungs under "
                 "the board's tape zone that nothing ever touches (recessed "
                 "ledge, 2026-09-23); the board carries on the rails' rim shelves")
THIN_WAIVED = {
    "magnet_gauge": "0.6 mm magnet skin by design (cell row) -- the "
                    "regime the trays print; flag it in the slicer, "
                    "not here",
    "deck_ladder": _PLATE_WAIVER,
    **{f"skin_coupon_{n}": "the buried-magnet skin IS the test (plate 10m): "
                           "one to two wall lines between head pocket and disc"
       for n in ("045", "065", "085")},
    "ladder_station_stub": _PLATE_WAIVER + " (the 02k coupon cut from it)",
    "ledge_gauge": _PLATE_WAIVER + " (plate 02k, the manifold stand-in)",
    "deck_pair": _PLATE_WAIVER + " (plate 02d's two-station trim, printed history)",
    "half_bay_gauge": _PLATE_WAIVER + " (plate 02l, the half board's 100 mm of the real ladder)",
}

ISLAND_WAIVED = {
    "board_plate_esp": _CLIP_WAIVER,
    "board_plate_pi": _CLIP_WAIVER,
    "screen_bezel": _CLIP_WAIVER,
    "breadboard_carrier": _CLIP_WAIVER,
    "rail_bin": _CLIP_WAIVER,
    "fit_coupon": _CLIP_WAIVER + " (test clips, same geometry)",
    "fit_clips_petg": _CLIP_WAIVER + " (the on-edge gauge trio)",
    "clip_test_18": _CLIP_WAIVER + " (test clip, 1.8 latch, plate 03c)",
    "clip_test_20": _CLIP_WAIVER + " (test clip, 2.0 latch, plate 03c)",
    "display_spine": _CLIP_WAIVER + " (TWO clips -- four dabs)",
    "display_post": _CLIP_WAIVER + " (v2 post)",
}

PRINT_POSE = {
    "base_body": 0,
    # LIPS on the bed, web up (flipped 2026-09-19). Web-down left a 2.5 mm flat
    # eave under each lip printing over air; the README accepted that because
    # "nothing touches" the underside -- true of the console, false since the
    # frame's mortises slide on it. Plate 02's rail_stub sagged strands off
    # both lips and jammed all three slots. Flipped, the section only narrows
    # going up: no overhang anywhere, the csk cones close upward at 45 degrees,
    # and the outer face's 0.2 edge chamfer becomes elephant-foot relief on
    # the 34.85 lip width the clips close over.
    "din_rail": ("X", 180),
    # -90 like the bezel: at +90 these narrow plates stand on their release
    # tabs (body edge inboard of the tab reach) -- the stance gate below now
    # catches that class.
    "board_plate_esp": -90,
    "board_plate_pi": -90,
    # -90, not +90: +90 stood the 27 g part on the release tab's 10.2 mm2
    # with its centre of mass 5.2 mm outside support (print review blocker).
    # -90 lands 774 mm2 of bezel face on the bed and slices clean.
    "screen_bezel": -90,
    "breadboard_carrier": 90,
    "rail_bin": 90,
    # Spine like the other clip plates. The mount's bars print FLAT on
    # purpose -- their T-slots are the mechanism, and slots printed across
    # layers bind (the board_plate X-arm lesson).
    "display_spine": -90,
    "display_upright": 0,
    "display_crossbar": 0,
    # v2 post: FRONT FACE DOWN since 2026-10-17 (was on edge, +90, 144 tall).
    # Upright, every layer line ran across the post, and the screen's lever
    # bends the post exactly across them -- the user saw layers splitting.
    # Flat, the layers and perimeters run the post's whole length, so bending
    # is carried along the extrusions (several times the strength), the nut
    # channel and keeper slot open upward, and only the hook's tooth (its
    # bearing face, 2.2 x 30) needs support -- painted, with PLA interface.
    "display_post": ("X", 180),
    # twist lock: the hook as modelled (underside and nut pocket on the bed,
    # tooth at hub height, wedge top); the knob top down, shaft and key up
    # screwless lock (2026-10-17): the lock on its side, tooth up, so the
    # prongs flex in the layer plane; the wing as drawn, socket on the bed
    "display_lock": ("X", 90),
    "display_lock_knob": 0,
    # DIN tilt adapter: each part stands on an x face, so every profile (the
    # clip hook, the TS35 stub, the knuckles) lies in the layer plane and the
    # hinge teeth face up: base on its +x end, arm and knob on their -x ends
    "din_tilt_base": ("Y", 90),
    "din_tilt_arm": ("Y", -90),
    "din_tilt_knob": ("Y", -90),
    # back face on the bed: bars, rim and bosses all rise from it,
    # counterbores open upward (CrowPanel P4 backplate, 2026-10-15)
    "display_backplate": 0,
    # mic crown (2026-10-17): back face on the bed like the backplate; the
    # tongue narrows upward, pads, pins and lip columns rise from it, and the
    # sprung lip's beam lies in the plate, so it flexes in the layer plane
    "mic_crown": 0,
    # --- frame variant ---
    # The rails are half-round with the flat on the bed, so pose 0 by
    # construction. The end frame is a 2.5D extrusion laid on its side --
    # and since the rail-screw landing boss grew on the INNER face (x 6..9),
    # the OUTER face (x=0) must be the bed face: at +90 the plate stood on
    # its own 3 mm boss and the rest of it floated.
    "end_frame": ("Y", -90),
    # The mirrored right frame flips with its geometry: its boss now grows
    # toward -x, so +90 is what puts the outer face on the bed.
    "end_frame_r": ("Y", 90),
    # Rails plus rungs as one flat part; every section is arc-over-flat and
    # the rungs are 3 mm bars, so pose 0 by construction.
    "deck_ladder": 0,
    "rear_tie": 0,
    # Upright, buttress blades and all: the blades' faces are all 45 degrees
    # or steeper by construction (rake and V-notch exactly 45, post plane 53,
    # rear lean ~6 off vertical), pilots are teardropped, and the shoulder
    # rib grows from the face on a 45-degree chamfer.
    "rear_tray": 0,
    "side_bin": 0,          # floor down; head pockets are open-bottom slots
    "side_blank": ("Y", -90),   # outer face down, like the left frame
    "side_tray": 0,             # floor down; pockets are blind from the top
    "rail_cap": ("X", 180),     # top face down: the 0.45 skin is the bed
                                # layers, magnet pockets open upward
    # frame coupon family
    "fit_coupon_frame": 0,
    "rail_stub": ("X", 180),    # follows din_rail: lips on the bed
    "spigot_stub": 0,
    "tie_stub": 0,
    "foot_gauge": 0,
    # Pose 0, NOT the end frame's ("Y", -90). The block is modelled with x as
    # the pilot depth and z as the frame's thickness, so it is ALREADY "on its
    # side like the frame": as exported its pilots lie in the layer plane,
    # which is how the real frame's rail pilots print (the screw wedges the
    # layers apart -- the weak way, and the one worth testing). Copying the
    # frame's -90 stood the pilots vertical, through the layers: the strong
    # way, so plate 02's block flattered every screw test (found 2026-09-19).
    "pilot_block": 0,
    "ladder_station_stub": 0,
    "magnet_gauge": 0,
    # spelled out, not a comprehension: plates.py reads this dict with
    # ast.literal_eval, which only takes literals
    "skin_coupon_open": 0,
    "skin_coupon_045": 0,
    "skin_coupon_065": 0,
    "skin_coupon_085": 0,
    "rail_cap_615": ("X", 180),
    "rail_cap_625": ("X", 180),
    "rail_cap_635": ("X", 180),
    "foot_pad_006": 0,
    "foot_pad_012": 0,
    "foot_pad_018": 0,
    "tpu_block": 0,
    # -90 like every clip-carrying narrow plate: at +90 the gauge trio
    # stood on its release tabs.
    "fit_clips_petg": -90,
    "clip_test_18": -90,
    "clip_test_20": -90,
}


def check(path):
    name = os.path.basename(path)[:-4]
    m = trimesh.load(path)

    pose = PRINT_POSE.get(name, 0)
    axis, ang = pose if isinstance(pose, tuple) else ("X", pose)
    if ang:
        vec = {"X": (1, 0, 0), "Y": (0, 1, 0)}[axis]
        m.apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(ang), vec))
    m.apply_translation((0, 0, -m.bounds[0][2]))

    watertight = m.is_watertight
    winding = m.is_winding_consistent
    vol_ok = m.volume > 0

    # Face normals pointing down, excluding the flat bed face itself.
    n = m.face_normals
    areas = m.area_faces
    down = n[:, 2] < 0
    zmin = m.bounds[0][2]
    tri_z = m.triangles[:, :, 2].mean(axis=1)
    on_bed = tri_z < zmin + 0.35

    # Angle from the build plate: 90 deg = vertical wall, 0 deg = flat overhang.
    with np.errstate(invalid="ignore"):
        angle = np.degrees(np.arcsin(np.clip(np.abs(n[:, 2]), 0, 1)))
    steep = down & ~on_bed & (angle > OVERHANG_LIMIT)
    steep_area = areas[steep].sum()
    bridge = down & ~on_bed & (angle > 80)
    bridge_area = areas[bridge].sum()

    # Area alone cannot tell a printable overhang from a droopy one. A 2.9 x 54
    # strip and a 12.5 x 12.5 patch are both 158 mm2, and the first bridges
    # perfectly while the second sags. What matters is SPAN -- how far the
    # nozzle flies unsupported -- so measure the narrow dimension of each
    # connected flat region and flag on that.
    span = 0.0
    if bridge.any():
        idx = np.flatnonzero(bridge)
        try:
            groups = trimesh.graph.connected_components(
                m.face_adjacency, nodes=idx, min_len=1)
        except Exception:
            groups = [idx]
        for g in groups:
            ga = areas[g].sum()
            if ga < 20:
                continue
            pts = m.triangles[g].reshape(-1, 3)[:, :2]
            ext = pts.max(axis=0) - pts.min(axis=0)
            # Effective width = area / longest dimension. The bounding box's
            # narrow side lies on thin diagonal slivers -- it reported a 126 mm
            # "span" on the console from a strip with almost no area in it.
            # area/length gives 2.9 for a 2.9 x 54 strip and 12.5 for a square.
            span = max(span, ga / max(ext.max(), 1e-6))

    # A part in two pieces is still "watertight" -- trimesh reports two disjoint
    # closed shells as a valid manifold. That is how a clip jaw got severed from
    # its own back plate and shipped through every gate I had: it only held
    # together because the module body happened to re-weld it downstream.
    bodies = len(m.split(only_watertight=False))

    # Floating islands: a cross-section component with NOTHING under it. The
    # overhang gates above are face-local and blind to this -- the rear_tray's
    # V-tail wedge passed every one of them while being a 7.5 mm ribbon whose
    # first layer sat on air (its bottom floated 1 mm off the bed and it only
    # joined the body above the notch apex). Slice every 1 mm; each component
    # must overlap the previous slice grown by 1.3 (a 45-degree lean moves
    # 1.0 per slice, plus tolerance), or sit on the bed. Component-level on
    # purpose: an overhang WITH support beside it still passes.
    # Rings come straight from the 3D section dropped to XY -- to_2D()
    # re-centres each slice on its own origin (and its transform= kwarg is
    # gone in this trimesh), which silently breaks comparison BETWEEN
    # slices. Nesting is done here by even-odd depth: without it every screw
    # hole became a phantom solid disk that "floated" wherever the slice
    # below was void. The first version of this check swallowed a TypeError
    # from to_2D and skipped every slice -- an ALL CLEAR that checked
    # nothing, caught only because a synthetic floating cube sailed through.
    import shapely.geometry
    import shapely.ops
    island_z = None
    prev_union = None
    min_wall_z = None
    thin_prev = []
    zmax = m.bounds[1][2]
    # 0.637, not 0.5: model faces live at halves and integers, and a slice
    # exactly ON a planar face emits degenerate rings that read as floating
    # islands (the end frame's socket floor at model x=2.5 did exactly that).
    # An irrational-ish offset never lands on designed geometry.
    for z in np.arange(0.637, zmax, 1.0):
        s = m.section(plane_origin=[0, 0, float(z)],
                      plane_normal=[0, 0, 1])
        rings = []
        if s is not None:
            rings = [shapely.geometry.Polygon(line[:, :2]).buffer(0)
                     for line in s.discrete if len(line) >= 3]
            rings = [r for r in rings if not r.is_empty and r.area > 0.01]
        solids, holes = [], []
        for i, r in enumerate(rings):
            depth = sum(1 for j, q in enumerate(rings)
                        if j != i and q.contains(r.representative_point()))
            (holes if depth % 2 else solids).append(r)
        # Thin VERTICAL walls: erode-dilate each slice by two perimeters
        # (0.42 per side); whatever vanishes is thinner than 0.84. One slice
        # alone is noise (chamfer bands, arris slivers) -- flag only regions
        # that persist across two consecutive slices at the same spot.
        thin_now = []
        if solids:
            u_s = shapely.ops.unary_union(solids)
            gone = u_s.difference(u_s.buffer(-0.42).buffer(0.42))
            thin_now = [g for g in
                        (gone.geoms if hasattr(gone, "geoms") else [gone])
                        if g.area >= 6.0]
        if thin_prev and thin_now and min_wall_z is None:
            for a in thin_now:
                if any(a.intersects(b) for b in thin_prev):
                    min_wall_z = z
        thin_prev = thin_now

        if prev_union is not None and z > 1.0:
            for p in solids:
                if not p.intersects(prev_union):
                    # Confirm against the mesh itself before flagging. The 2D
                    # route can under-report support: a section ring that
                    # fails to polygonize (self-touching boundary, sliver)
                    # silently vanishes from the union, and everything above
                    # it then reads as floating -- the end frame's landing
                    # boss got flagged exactly that way while sitting on
                    # 6 mm of solid plate. Sample points inside the
                    # component; material one slice below ANY of them means
                    # it is supported.
                    pts = [p.representative_point()]
                    b = p.bounds
                    for gx in np.linspace(b[0], b[2], 4):
                        for gy in np.linspace(b[1], b[3], 4):
                            q = shapely.geometry.Point(gx, gy)
                            if p.contains(q):
                                pts.append(q)
                    probe = np.array([[q.x, q.y, z - 1.0] for q in pts])
                    try:
                        below = m.contains(probe)
                    except Exception:
                        below = []
                    if not any(below):
                        island_z = z if island_z is None else island_z
        if solids:
            u = shapely.ops.unary_union(solids)
            if holes:
                u = u.difference(shapely.ops.unary_union(holes))
            prev_union = u.buffer(1.3)
        else:
            prev_union = None

    flags = []
    # fit_coupon and fit_clips_petg are deliberately plates of loose pieces.
    # side_bin / side_tray carry SEALED magnet cavities -- a fully enclosed
    # void is a second closed surface in the mesh, so trimesh counts it as
    # another body. That is the pause-and-insert design working as intended
    # (the printer roofs the disc in), not a modelling error. The count is
    # 1 + one void per cell magnet: bin 1+2, tray 1+5.
    # + 3 sealed head-disc slots each since 2026-10-09 (buried head discs)
    SEALED_VOIDS = {"side_bin": 6, "side_tray": 9,
                    # plate 10m: one sealed on-edge disc slot each
                    "skin_coupon_045": 2, "skin_coupon_065": 2, "skin_coupon_085": 2}
    if bodies != SEALED_VOIDS.get(name, 1) and \
            name not in ('fit_coupon', 'fit_clips_petg'):
        flags.append(f"{bodies} DISCONNECTED BODIES")
    if not watertight:
        flags.append("NOT WATERTIGHT")
    if not winding:
        flags.append("winding inconsistent")
    if not vol_ok:
        flags.append("non-positive volume")
    # 20 mm. PETG bridges 15 mm through-holes cleanly; sag only shows up well
    # past that. A threshold that flags every window is as useless as one that
    # flags nothing.
    if span > 20.0:
        flags.append(f"{span:.1f} mm unsupported span")
    # Thin HORIZONTAL plates (roofs/floors): slicing cannot see them, so a
    # 5 mm ray grid measures the first material band from below -- the
    # 0.8 mm foot-pocket roof class. Two adjacent thin samples = a real
    # plate, one alone = an edge artefact. Parts thinner than 2.5 overall
    # (the TPU gasket) are exempt: thin IS their design.
    roof_z = None
    if m.bounds[1][2] - m.bounds[0][2] >= 2.5:
        xs = np.arange(m.bounds[0][0] + 2, m.bounds[1][0] - 1, 5.0)
        ys = np.arange(m.bounds[0][1] + 2, m.bounds[1][1] - 1, 5.0)
        if len(xs) and len(ys):
            grid = np.array([[x, y, m.bounds[0][2] - 5.0]
                             for x in xs for y in ys])
            dirs = np.tile([0.0, 0, 1.0], (len(grid), 1))
            try:
                locs, ridx, _ = m.ray.intersects_location(grid, dirs)
            except Exception:
                locs, ridx = [], []
            from collections import defaultdict
            byray = defaultdict(list)
            for pt, r in zip(locs, ridx):
                byray[r].append(pt[2])
            thin_pts = []
            for r, zs2 in byray.items():
                zs2 = sorted(zs2)
                if len(zs2) >= 2 and 0.05 < zs2[1] - zs2[0] < 0.9:
                    thin_pts.append((grid[r][0], grid[r][1], zs2[0]))
            for i, (x1, y1, z1) in enumerate(thin_pts):
                for x2, y2, z2 in thin_pts[i + 1:]:
                    if abs(x1 - x2) <= 5.5 and abs(y1 - y2) <= 5.5                             and abs(z1 - z2) < 1.0:
                        roof_z = z1
                        break
                if roof_z is not None:
                    break

    # Stance: enough bed contact, and the centre of mass over it. The bezel
    # shipped a pose that stood 27 g on a 10.2 mm2 release tab with the COM
    # 5 mm outside support -- found by the slicer, not by any gate -- and
    # the dedicated board plates then repeated it. This is that gate.
    stance = "ok"
    try:
        s0 = m.section(plane_origin=[0, 0, 0.25], plane_normal=[0, 0, 1])
        if s0 is not None:
            rings0 = [shapely.geometry.Polygon(l[:, :2]).buffer(0)
                      for l in s0.discrete if len(l) >= 3]
            contact = shapely.ops.unary_union(
                [r for r in rings0 if not r.is_empty])
            com = m.center_mass
            if contact.area < 25.0:
                stance = f"BED CONTACT {contact.area:.0f} mm2"
            elif not contact.convex_hull.buffer(1.0).contains(
                    shapely.geometry.Point(com[0], com[1])):
                stance = "COM OUTSIDE SUPPORT"
    except Exception:
        pass
    if stance != "ok":
        flags.append(f"UNSTABLE STANCE: {stance}")

    if min_wall_z is not None:
        flags.append(f"WALL UNDER 0.84 at z={min_wall_z:.1f}")
    if roof_z is not None:
        if name in THIN_WAIVED:
            print(f"  {name:22s} waived thin plate at z={roof_z:.1f}: "
                  f"{THIN_WAIVED[name]}")
        else:
            flags.append(f"PLATE UNDER 0.9 at z={roof_z:.1f}")
    if island_z is not None:
        if name in ISLAND_WAIVED:
            print(f"  {name:22s} waived island at z={island_z:.1f}: "
                  f"{ISLAND_WAIVED[name]}")
        else:
            flags.append(f"FLOATING ISLAND at z={island_z:.1f}")

    status = "  ".join(flags) if flags else "ok"
    print(f"  {name:22s} pose {axis}{ang:3d}  watertight={str(watertight):5s} "
          f"overhang {steep_area:7.0f} mm2   flat {bridge_area:6.0f} mm2   "
          f"max span {span:5.1f} mm   {status}")
    return not flags


# Export freshness: every geometry gate below reads out/, so its verdict is
# only as current as the exports. The print review's B2 was exactly this
# failure -- the sealed-slot rail bug was fixed in bench.py, out/stl was never
# regenerated, and the stale mesh passed every gate. Sources follow the
# import chain: frame.py takes the shared rail from bench.py, everything
# reads params.py. The coupon scripts import the part modules too (a gauge
# measures the same geometry) but nothing imports THEM, so they gate only
# their own outputs -- a coupon-script edit must not stale the parts.
GEOMETRY_SOURCES = {
    "stl": ("bench.py", "params.py"),
    "stl_frame": ("frame.py", "bench.py", "params.py"),
    # The frame coupon has its own directory because frame.py purges
    # stl_frame -- see the note in coupon_frame.py. Its gauges are built
    # from frame/bench geometry, so they go stale with those too.
    "stl_coupon": ("coupon_frame.py", "frame.py", "bench.py", "params.py"),
}
COUPON_SOURCES = {
    "fit_coupon": ("coupon.py",),
    # NOT just coupon_frame.py: every gauge on this plate is built from
    # frame.py / bench.py geometry (deck_ladder, rail_cap, foot_pad,
    # half_round, din_clip), so a change there can silently invalidate a
    # printed gauge. Watching only the coupon script was the same class of
    # miss the export-freshness guard exists to catch.
    **{n: ("coupon_frame.py", "frame.py", "bench.py", "params.py") for n in (
        "fit_coupon_frame", "rail_stub", "spigot_stub", "tie_stub",
        "foot_gauge", "pilot_block", "ladder_station_stub", "half_bay_gauge", "magnet_gauge",
        "rail_cap_615", "rail_cap_625", "rail_cap_635",
        "foot_pad_006", "foot_pad_012", "foot_pad_018", "tpu_block",
        "fit_clips_petg", "clip_test_18", "clip_test_20", "skin_coupon_open", "skin_coupon_045",
        "skin_coupon_065", "skin_coupon_085")},
}


if __name__ == "__main__":
    ok = True
    cad_dir = os.path.dirname(os.path.abspath(__file__))
    for label, sub, expect in (("FRAME", "stl_frame", 10),
                               ("COUPON", "stl_coupon", 17),
                               ("CONSOLE", "stl", 0)):
        src = os.path.join(OUT, sub)
        if not os.path.isdir(src):
            # An absent directory is not "nothing to check" when parts are
            # expected from it -- that is the loudest possible staleness.
            if expect:
                print(f"\n  {sub}: DIRECTORY MISSING -- expected {expect} "
                      f"STLs; rerun the builder for this directory")
                ok = False
            continue
        # A gate that only measures the files it finds cannot see a part
        # that vanished. The frame coupon's fifteen gauges were deleted by
        # frame.py's purge and this printed ALL CLEAR over the hole, so
        # each directory now declares how many parts it should hold.
        have = len([f for f in os.listdir(src) if f.endswith(".stl")])
        if expect and have < expect:
            print(f"\n  {sub}: MISSING PARTS -- {have} STLs, expected "
                  f"{expect}; rerun the builder for this directory")
            ok = False
        print(f"\n{label} -- printability (flat overhang = would need support):")
        for fn in sorted(os.listdir(src)):
            if fn.endswith(".stl"):
                path = os.path.join(src, fn)
                name = fn[:-4]
                sources = (GEOMETRY_SOURCES[sub]
                           + COUPON_SOURCES.get(name, ()))
                newest_src, culprit = max(
                    (os.path.getmtime(os.path.join(cad_dir, f)), f)
                    for f in sources)
                # A stale mesh is not worth measuring -- its geometry is
                # superseded, and an "ok" row for it reads as a pass.
                if os.path.getmtime(path) < newest_src:
                    print(f"  {name:22s} STALE EXPORT -- older than "
                          f"{culprit}; regenerate")
                    ok = False
                    continue
                ok &= check(path)
    print("\n  ALL CLEAR" if ok else "\n  ISSUES ABOVE")





