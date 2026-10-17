"""Audit every screw in the frame assembly:  python cad/screws.py

Interference sweeps prove parts do not overlap; they cannot prove a part can
ARRIVE. A screw modelled inside a sealed cavity measures 0.000 mm3 against
everything and still cannot be installed -- which is exactly how the DIN
rail shipped a revision whose mount bores were capped by a 0.2 mm skin with
the head recesses buried mid-solid. This audit exists so that class of bug
dies here. Per screw, three geometric tests against the real STLs:

  FIT       in-place interference vs every part; only the designed self-tap
            bite (shank r1.5 in a r1.25 pilot) may overlap, only in the far
            part
  APPROACH  a head-diameter cylinder swept 45 mm along the insertion axis
            from the seat outward -- any solid in it means the screw cannot
            physically get to its seat (clip-on modules are reported but
            not fatal: they clip on after the screws are driven)
  ENGAGE    thread bite in the far part, from intersection volume over the
            2.16 mm2 shank-pilot annulus (NOT a thin core probe -- a r1.2
            core fits inside the r1.25 pilot void and measures nothing)

Run it after any change to screw lines, sockets, pockets, or the rail.
"""
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import trimesh
import trimesh.boolean as tb
import trimesh.creation as tc
import trimesh.transformations as tt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import frame as F  # noqa: E402  (params only; build guarded by __main__)

SRC = os.path.join(REPO, "out", "frame")
parts = {}
for fn in os.listdir(SRC):
    # The N52 discs are deliberately parked right over the screw heads --
    # that is the whole mechanism. They live inside side_bin / side_tray /
    # rail_cap, which are already MODULES, so counting them separately
    # would double-report one obstruction as two.
    if fn.startswith("asm_mag"):
        continue
    if fn.startswith("asm_") and fn.endswith(".stl"):
        parts[fn[:-4]] = trimesh.load(os.path.join(SRC, fn))
# Clip-on modules come off the rail without tools, so a screw path through
# one is a soft note, not a blocker -- you unclip, drive, re-clip.
#
# The v2 posts sit over the buttress rail screws at X=100/200 (the clip
# plate is 30 wide and the demo spacing puts post centres at 88/188), and
# with the mount centred at 138 inside the usable 48..228 span there is NO
# post spacing wider than 120 mm that clears both stations -- so this is
# not something to design around, it is something the posts have to be
# removable for. They are: each unclips on its own, where v1's five pieces
# had to come off as one unit via the spine.
MODULES = {"asm_plate", "asm_screen", "asm_railbin",
           "asm_post0", "asm_post1",
           # v1, still built for the retired mountv1 viewer variant
           "asm_dspine",
           "asm_dupright0", "asm_dupright1", "asm_dcross0", "asm_dcross1",
           # lift off the heads without tools -- same as unclipping
           "asm_sidebin", "asm_sideblank", "asm_sidetray",
           # the rail caps lift out of the shroud windows by hand
           "asm_railcap_l", "asm_railcap_r"}

# post outward normal (unit, in +n direction of post_point)
nrm = np.array([0.0, -F.FR_COS, F.FR_SIN])
nrm /= np.linalg.norm(nrm)


def post_pt(x, s, n):
    y, z = F.post_point(s, n)
    return np.array([x, y, z])


def cyl_along(p0, axis, r, length):
    """Cylinder of radius r from p0 extending `length` along axis."""
    c = tc.cylinder(radius=r, height=length, sections=48)
    c.apply_translation([0, 0, length / 2])
    R = tt.rotation_matrix(
        np.arccos(np.clip(np.dot([0, 0, 1], axis), -1, 1)),
        np.cross([0, 0, 1], axis) if abs(np.dot([0, 0, 1], axis)) < 0.9999
        else [1, 0, 0])
    c.apply_transform(R)
    c.apply_translation(p0)
    return c


SCREWS = []
# --- six bar-end screws: axis +X (left) / -X (right), seat on outer faces
ends = ((F.FRONT_AXIS, F.END_SCREW_Z, "asm_ladder"),
        (F.REAR_AXIS, F.END_SCREW_Z, "asm_ladder"),
        (F.TIE_Y, F.END_SCREW_Z, "asm_tie"))
for i, (y, z, far) in enumerate(ends):
    SCREWS.append(dict(name=f"hw_end{i}", seat=np.array([0.0, y, z]),
                       axis=np.array([-1.0, 0, 0]), far=far,
                       near="asm_frame_l", head_r=2.75, L=12.0))
    SCREWS.append(dict(name=f"hw_end{i+3}", seat=np.array([300.0, y, z]),
                       axis=np.array([1.0, 0, 0]), far=far,
                       near="asm_frame_r", head_r=2.75, L=12.0))
# --- eight rail screws: axis = post normal, seat flush at RAIL_TOP_Z
stations = [(F.RAIL_END_ST, "asm_frame_l"), (F.FR_W - F.RAIL_END_ST, "asm_frame_r"),
            (F.BUTTRESS_X[0], "asm_tray"), (F.BUTTRESS_X[1], "asm_tray")]
k = 0
for x, far in stations:
    for dy in (-F.RAIL_END_PITCH / 2, F.RAIL_END_PITCH / 2):
        SCREWS.append(dict(name=f"hw_rail{k}",
                           seat=post_pt(x, F.FR_RAIL_S + dy, F.RAIL_TOP_Z),
                           axis=nrm.copy(), far=far, near="asm_rail",
                           head_r=3.0, L=16.0))
        k += 1

print(f"{'screw':10s} {'far part':12s} {'engage':>7s} {'approach':>9s} "
      f"{'bad-fit':>8s}  verdict")
all_ok = True
for s in SCREWS:
    ax = s["axis"]
    # ENGAGE: the screw prop itself vs the far part. A r1.2 core proved
    # nothing -- it fits inside the r1.25 pilot void. The self-tap bite is
    # the annulus between shank r1.5 and pilot r1.25: area 2.16 mm2, so
    # engaged length = intersection volume / 2.16.
    scr_mesh = parts.get(s["name"]) or trimesh.load(
        os.path.join(SRC, s["name"] + ".stl"))
    far = parts[s["far"]]
    try:
        inter = tb.intersection([scr_mesh, far], engine="manifold")
        vol = inter.volume if inter is not None and len(inter.faces) else 0.0
    except Exception:
        vol = -1
    engage = vol / (np.pi * (1.5 ** 2 - 1.25 ** 2))

    # APPROACH: head-radius sweep outward from just above the seat
    sweep = cyl_along(s["seat"] + ax * 0.3, ax, s["head_r"] + 0.15, 45.0)
    blockers = []
    for name, m in parts.items():
        bb_gap = np.maximum(m.bounds[0] - sweep.bounds[1],
                            sweep.bounds[0] - m.bounds[1]).max()
        if bb_gap > 0:
            continue
        try:
            iv = tb.intersection([sweep, m], engine="manifold")
            v = iv.volume if iv is not None and len(iv.faces) else 0.0
        except Exception:
            v = 0.0
        if v > 0.1:
            blockers.append((name, v))

    # FIT: the placed screw prop vs every part except designed pilot bite
    scr = parts.get(s["name"]) or trimesh.load(
        os.path.join(SRC, s["name"] + ".stl"))
    bad = []
    for name, m in parts.items():
        if name == s["name"] or name.startswith("hw_"):
            continue
        bb_gap = np.maximum(m.bounds[0] - scr.bounds[1],
                            scr.bounds[0] - m.bounds[1]).max()
        if bb_gap > 0:
            continue
        try:
            iv = tb.intersection([scr, m], engine="manifold")
            v = iv.volume if iv is not None and len(iv.faces) else 0.0
        except Exception:
            v = 0.0
        if name == s["far"]:
            continue          # pilot bite belongs here; engagement covers it
        # The rail's bores carry one sacrificial layer at the counterbore
        # floor (bench.din_rail, RAIL_CBORE_SKIN) that the screw pushes
        # through. Allow exactly that disc and nothing more: a shank-sized
        # plug one layer thick, with 15% for the mesh.
        skin = (math.pi * 1.5 ** 2 * 0.2 * 1.15
                if s["name"].startswith("hw_rail") and name == "asm_rail" else 0.0)
        if v > 0.05 + skin:
            bad.append((name, v))

    hard = [b for b in blockers if b[0] not in MODULES]
    soft = [b for b in blockers if b[0] in MODULES]
    ok = engage >= 4.0 and not hard and not bad
    all_ok &= ok
    verdict = "ok" if ok else "PROBLEM"
    if soft and ok:
        verdict += f" (module in path: {', '.join(n for n, _ in soft)})"
    detail = ""
    if hard:
        detail += "  BLOCKED by " + ", ".join(f"{n}({v:.1f})" for n, v in hard)
    if bad:
        detail += "  BAD FIT vs " + ", ".join(f"{n}({v:.1f})" for n, v in bad)
    print(f"{s['name']:10s} {s['far']:12s} {engage:6.2f}mm "
          f"{len(blockers):9d} {len(bad):8d}  {verdict}{detail}")

# ---- console rail alignment guard ------------------------------------------
# The console's four rail pilots sat on solid web (missing every 25 mm slot
# by 2.5-12.5 mm) through every prior gate, because nothing checked the two
# hole systems against each other. Recomputed from the same constants
# bench.py uses; fails if any pilot leaves its slot's usable span.
import params as P

n_slots = int((P.RAIL_LEN - 40) // 25)
slot_centres = [P.BENCH_W / 2 + (-(n_slots - 1) * 25 / 2 + i * 25)
                for i in range(n_slots)]
CONSOLE_PILOTS = (50.0, 125.0, 175.0, 250.0)   # keep in sync with bench.py
print("\nconsole rail pilots vs 25 mm slots + thread bite:")
_body_path = os.path.join(REPO, "out", "stl", "base_body.stl")
_body = trimesh.load(_body_path) if os.path.exists(_body_path) else None
_tilt = np.radians(P.PANEL_TILT)
_pn = np.array([0.0, -np.cos(_tilt), np.sin(_tilt)])
_uy = np.cross(_pn, [1.0, 0, 0])
for x in CONSOLE_PILOTS:
    miss = min(abs(x - c) for c in slot_centres)
    bite = 0.0
    if _body is not None:
        # thread-bite annulus: first material band along offset rays at
        # r=1.45 (between the 1.3 pilot and the 1.5 thread). Ray down the
        # pilot CENTRE reads the hole, not the bite -- the first version of
        # this measurement did exactly that and saw nothing.
        y0, z0 = P.panel_point(P.RAIL_S, 5.0)
        bands = []
        for a in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            off = 1.45 * (np.cos(a) * np.array([1.0, 0, 0]) + np.sin(a) * _uy)
            p0 = np.array([x, y0, z0]) + off
            hits, _, _ = _body.ray.intersects_location(
                np.array([p0]), np.array([-_pn]))
            ds = sorted(np.dot(h - p0, -_pn) for h in hits)
            band = 0.0
            for i in range(0, len(ds) - 1, 2):
                if ds[i] < 6.0:
                    band = ds[i + 1] - ds[i]
                    break
            bands.append(band)
        bite = min(bands)
    ok = miss <= 7.5 - 1.7 and bite >= 4.0
    all_ok &= ok
    print(f"  pilot x={x:5.1f}  slot miss {miss:4.1f} mm  bite {bite:4.1f} mm  "
          f"{'ok' if ok else 'PROBLEM'}")

# ---- board-plate boss pilots ------------------------------------------------
# The universal plate's nut-behind scheme died because nothing checked
# fastener access against the mounting surface. The dedicated plates use
# front-entry self-tappers into bosses; verify each pilot exists, is deep
# enough for an M3 x 8 (>= 6.0), and does NOT breach the plate's back face
# -- a proud tip would hold the clip off the rail lips.
print("\nboard-plate boss pilots (M3 x 8 self-tap, front entry):")
for kind in ("esp", "pi"):
    path = os.path.join(REPO, "out", "stl", f"board_plate_{kind}.stl")
    if not os.path.exists(path):
        print(f"  board_plate_{kind}: STL MISSING")
        all_ok = False
        continue
    mesh = trimesh.load(path)
    spec = P.BOARD_SPECS[kind]
    worst, breach = 99.0, False
    for dx, dy in spec["patterns"]:
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = sx * dx / 2, sy * dy / 2
                hits, _, _ = mesh.ray.intersects_location(
                    np.array([[cx, cy, 30.0]]), np.array([[0, 0, -1.0]]))
                zs = sorted(h[2] for h in hits)
                if not zs:
                    breach = True
                    continue
                worst = min(worst, (P.RAIL_TOP_Z + 7.0) - max(zs))
                if min(zs) > P.RAIL_TOP_Z + 0.05:
                    breach = True
    ok = worst >= 6.0 and not breach
    all_ok &= ok
    print(f"  board_plate_{kind}: min pilot depth {worst:4.1f} mm  "
          f"back skin {'intact' if not breach else 'BREACHED'}  "
          f"{'ok' if ok else 'PROBLEM'}")

# ---- display-mount spine bosses ---------------------------------------------
# Same idiom, same audit: the uprights bolt front-entry into four gabled
# bosses (M3 x 12 through the 6 mm bar leaves 6 mm of engagement, against a
# 6.4 mm pilot). Positions recomputed from the DM_* constants the CAD uses.
print("\ndisplay-mount spine bosses (M3 x 12 self-tap through the upright):")
_spine_path = os.path.join(REPO, "out", "stl", "display_spine.stl")
if not os.path.exists(_spine_path):
    print("  display_spine: STL MISSING")
    all_ok = False
else:
    mesh = trimesh.load(_spine_path)
    worst, breach = 99.0, False
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * P.DM_BOSS_X, sy * P.DM_BOSS_PITCH / 2
            hits, _, _ = mesh.ray.intersects_location(
                np.array([[cx, cy, 30.0]]), np.array([[0, 0, -1.0]]))
            zs = sorted(h[2] for h in hits)
            if not zs:
                breach = True
                continue
            worst = min(worst, (P.RAIL_TOP_Z + 7.0) - max(zs))
            if min(zs) > P.RAIL_TOP_Z + 0.05:
                breach = True
    ok = worst >= 6.0 and not breach
    all_ok &= ok
    print(f"  display_spine: min pilot depth {worst:4.1f} mm  "
          f"back skin {'intact' if not breach else 'BREACHED'}  "
          f"{'ok' if ok else 'PROBLEM'}")

# ---- side bin vs the right-face bar-end heads -------------------------------
# The bin's whole promise is "drops over the heads, hides them, touches
# nothing". Two measurements per head against the placed STL: every point on
# the head's surface must sit >= 0.25 mm OUTSIDE the bin (clearance), and a
# ray fired outward from the head tip must strike bin material (hidden).
HEAD_R, HEAD_PROUD = 2.75, F.BAR_HEAD_T
for label, part_name, face_x, out in (
        ("side bin vs right-face bar-end heads", "asm_sidebin", F.FR_W, 1.0),
        ("side tray vs left-face bar-end heads", "asm_sidetray", 0.0, -1.0)):
    print(f"\n{label} (clear + hidden):")
    _sb = parts.get(part_name)
    if _sb is None:
        print(f"  {part_name}: STL MISSING")
        all_ok = False
        continue
    for y, z in ((F.FRONT_AXIS, F.END_SCREW_Z),
                 (F.REAR_AXIS, F.END_SCREW_Z),
                 (F.TIE_Y, F.END_SCREW_Z)):
        # sample the head's rim and tip-edge circles
        pts = []
        for a in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            oy, oz = HEAD_R * np.cos(a), HEAD_R * np.sin(a)
            pts.append([face_x + out * 0.1, y + oy, z + oz])
            pts.append([face_x + out * HEAD_PROUD, y + oy, z + oz])
        pts.append([face_x + out * HEAD_PROUD, y, z])
        d = trimesh.proximity.signed_distance(_sb, np.array(pts))
        margin = -float(d.max())          # positive = outside the part
        hits, _, _ = _sb.ray.intersects_location(
            np.array([[face_x + out * (HEAD_PROUD + 0.2), y, z]]),
            np.array([[out, 0, 0]]))
        hidden = len(hits) >= 1
        ok = margin >= 0.25 and hidden
        all_ok &= ok
        print(f"  head y={y:5.1f}: clearance {margin:5.2f} mm  "
              f"{'hidden' if hidden else 'VISIBLE'}  "
              f"{'ok' if ok else 'PROBLEM'}")

# ---- start + track: every self-tapper -------------------------------------
# User, 2026-10-16: "small predrilled spots with tracking so the screw doesn't
# end up coming out the side of the plastic". ENGAGE above proves a screw
# bites; it says nothing about whether it STARTS straight or what is left
# beside the thread if it doesn't. Per screw, along its real axis, against
# the real STLs:
#   pilot  the far part's bore runs >= 0.5 past the screw tip, so the tip
#          never has to cut its own way (the rail-pilot refill bug, again)
#   wall   solid material outside the thread crest (r 1.5), measured by
#          rays fanned round the axis every 0.25 mm of engagement. >= 1.2 is
#          three 0.42 perimeters -- fused plastic, no infill for the thread
#          to wander into
#   start  something that steers the tip into the pilot: a clearance bore
#          in the part being clamped (<= 4.3 dia, >= 2.5 long), or a lead-in
#          cone at the pilot mouth when nothing is ahead of it (the screen)
# "drift" is the worst case if the screw leans as far as the guide lets it,
# pivoting on the pilot mouth -- reported, not gated: a thread-forming screw
# follows a 2.5 pilot far harder than this assumes.
print("\nstart + track (pilot past the tip, wall outside the thread, a guide):")


def _hits(mesh, origins, dirs):
    loc, ray, _ = mesh.ray.intersects_location(origins, dirs,
                                               multiple_hits=True)
    out = [[] for _ in origins]
    for p, i in zip(loc, ray):
        d = float(np.dot(p - origins[i], dirs[i]))
        if d > 1e-6:
            out[i].append(round(d, 4))
    return [sorted(set(o)) for o in out]


def track(name, start, ax, length, near, far, guide=None):
    t0 = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(ax, t0)
    u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    # Fan and stations sit off the round numbers features are cut on: a ray
    # lying exactly in a cone/bore seam plane grazes an edge and comes back
    # with one hit instead of two.
    fan = [math.cos(a) * u + math.sin(a) * v
           for a in np.linspace(0, 2 * np.pi, 24, endpoint=False) + 0.131]
    # far-part face: rays parallel to the axis at r 2.2, outside the pilot
    o = np.array([start - 5 * ax + 2.2 * d for d in fan])
    entry = float(np.median([h[0] for h in _hits(far, o, np.tile(ax, (24, 1)))
                             if h])) - 5.0
    ts = np.arange(entry + 0.1, entry + 40, 0.1)
    solid = far.contains(start + np.outer(ts, ax))
    bottom = float(ts[np.argmax(solid)]) if solid.any() else 1e9
    wall, mouth, deep = 99.0, None, None
    for t in np.arange(entry + 0.137, min(length, bottom) - 0.2, 0.25):
        hs = _hits(far, np.tile(start + t * ax, (24, 1)), np.array(fan))
        if mouth is None:
            mouth = min(h[0] for h in hs if h)
        if deep is None and t >= entry + 2.0:
            deep = min(h[0] for h in hs if h)
        # a ray leaving the void crosses the far part an EVEN number of
        # times; none = open to air (wall 0), odd = a grazed edge, skipped
        wall = min([wall] + [0.0 if not h else h[1] - 1.5
                             for h in hs if len(h) % 2 == 0])
    lead = mouth is not None and deep is not None and mouth - deep > 0.25
    if guide is None:                 # measure the near part's bore
        rb, lg = 99.0, 0.0
        for t in np.arange(0.05, entry, 0.1):
            c = start + t * ax
            if near.contains([c + 2.6 * u, c - 2.6 * u]).any():
                r = min(h[0] for h in _hits(near, np.tile(c, (24, 1)),
                                            np.array(fan)) if h)
                if r < 2.6:
                    rb, lg = min(rb, r), lg + 0.1
    else:
        rb, lg = guide
    guided = 2 * rb <= 4.3 and lg >= 2.5
    tilt = math.atan2(max(rb - 1.5, 0.0), max(lg, 1e-3))
    drift = (length - entry) * math.tan(tilt) if guided else float("nan")
    over = bottom - length
    ok = over >= 0.5 and wall >= 1.2 and (guided or lead)
    start_s = (f"bore {2 * rb:3.1f} x {lg:3.1f}" if guided else
               "lead-in cone" if lead else "NOTHING")
    print(f"  {name:13s} pilot +{min(over, 99):4.1f} past tip  "
          f"wall {wall:4.2f}  start: {start_s:13s} "
          f"{'' if drift != drift else f'(lean drift {drift:3.1f}) '}"
          f"{'ok' if ok else 'PROBLEM'}")
    return ok


for i, (y, z, far) in enumerate(ends):
    for side, x0, sgn, near in (("L", 0.0, 1.0, "asm_frame_l"),
                                ("R", F.FR_W, -1.0, "asm_frame_r")):
        all_ok &= track(f"bar end {side}{i}", np.array([x0, y, z]),
                        np.array([sgn, 0, 0]), F.SCREW_L, parts[near],
                        parts[far])
for x, far in stations:
    for dy in (-F.RAIL_END_PITCH / 2, F.RAIL_END_PITCH / 2):
        st = post_pt(x, F.FR_RAIL_S + dy, F.RAIL_TOP_Z - P.RAIL_CBORE_H)
        all_ok &= track(f"rail x{x:.0f}{'+' if dy > 0 else '-'}", st, -nrm,
                        F.RAIL_SCREW_L, parts["asm_rail"], parts[far])
# ---- bolted joints: screw + nut, no thread in the plastic ------------------
# 2026-10-17: the screen's self-tap bosses split and sheared ("breaking in
# half ... and just spinning"), and both display posts' spring latches broke.
# Both are bolted now -- the screen through 3.4 bores into nuts pressed into
# the bosses' backs, each post's keeper by an M3 x 12 from the post's front
# into a nut pressed into the keeper. Per joint, along the real axis of the
# real STLs (part-local, as built):
#   clear  the shank (r 1.55) meets no plastic between head and nut except
#          the one sacrificial 0.2 layer over the pocket
#   seat   the nut pocket is >= 2.4 deep beyond its ceiling
#   reach  the tip passes the nut's far face (full thread)
#   wall   plastic round the hex pocket, rays fanned at nut mid-height >= 1.2
print("\nbolted joints (clear shank, nut seated, full thread, wall round the nut):")


def bolt(name, head, ax, length, mesh, nut_t=2.4):
    """`mesh` may be a list of parts in one frame (the lock's knob and hook).
    They are tested one by one and OR-ed: concatenated, two parts sharing a
    face (knob shoulder on hook top) confuse the ray-parity inside test."""
    parts_ = mesh if isinstance(mesh, (list, tuple)) else [mesh]
    mesh = trimesh.util.concatenate(parts_)

    class _Any:
        @staticmethod
        def contains(pts):
            pts = np.asarray(pts, float)
            out = np.zeros(len(pts), bool)
            for m in parts_:
                out |= m.contains(pts)
            return out
    inside = _Any()
    head, ax = np.asarray(head, float), np.asarray(ax, float)
    t0 = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(ax, t0); u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    fan = [math.cos(a) * u + math.sin(a) * v
           for a in np.linspace(0, 2 * np.pi, 12, endpoint=False) + 0.131]
    ts = np.arange(0.05, length + 12.0, 0.05)
    line = head + np.outer(ts, ax)
    # plastic just outside the bore and inside the hex: the clamped stack
    # ends where the nut pocket begins
    ring = inside.contains(line + 2.3 * fan[0]) | inside.contains(line + 2.3 * fan[6])
    if not ring.any():
        print(f"  {name:13s} NO PLASTIC on the axis  PROBLEM")
        return False
    ceil = float(ts[np.where(ring)[0].max()]) + 0.05
    # where the part itself ends beyond the ceiling (r 4.2, round the pocket)
    outer = inside.contains(line + 4.2 * fan[0]) | inside.contains(line + 4.2 * fan[6])
    after = np.where(outer & (ts > ceil))[0]
    exit_t = float(ts[after.max()]) + 0.05 if after.size else ceil
    depth = exit_t - ceil
    shank = inside.contains(np.vstack([head + np.outer(ts[ts < ceil], ax) + 1.55 * d
                                       for d in fan]))
    solid_mm = shank.reshape(len(fan), -1).any(axis=0).sum() * 0.05
    clear = solid_mm <= 0.3
    nut_far = ceil + nut_t
    reach = length - nut_far
    mid = head + (ceil + nut_t / 2) * ax
    hs = _hits(mesh, np.tile(mid, (len(fan), 1)), np.array(fan))
    wall = min([h[1] - h[0] for h in hs if len(h) >= 2] or [0.0])
    ok = clear and depth >= nut_t and reach >= 0.0 and wall >= 1.2
    proud = length - exit_t
    print(f"  {name:13s} shank {'clear' if clear else f'HITS {solid_mm:.1f} mm'}  "
          f"nut pocket {depth:3.1f} deep  tip {reach:+4.1f} past nut"
          f"{f', {proud:3.1f} out the back' if proud > 0 else ''}  "
          f"wall {wall:4.2f}  {'ok' if ok else 'PROBLEM'}")
    return ok


_bp_path = os.path.join(REPO, "out", "stl", "display_backplate.stl")
_post_path = os.path.join(REPO, "out", "stl", "display_post.stl")
missing = [p for p in (_bp_path, _post_path) if not os.path.exists(p)]
if missing:
    print("  STL MISSING:", missing)
    all_ok = False
else:
    _bp = trimesh.load(_bp_path)
    _zf = (P.RAIL_TOP_Z + P.DM_POST_T + P.DBP_BAR_T + P.DBP_STANDOFF
           + P.CP7_PCB_T)
    for sx in (-1, 1):
        for sy in (-1, 1):
            all_ok &= bolt(f"screen {sx:+d}{sy:+d}",
                           (sx * P.CP7_HOLE_X, sy * P.CP7_HOLE_Z, _zf),
                           (0, 0, -1.0), P.CP7_SCREW_L, _bp)
    # the twist lock is screwless since 2026-10-17: its snap is checked by
    # sizes -- the barbs must pass the foot's bore going in, catch the knob's
    # neck, and the prongs' slot must leave room for them to close
    r_p, r_b, r_n = P.DM_LOCK_BARB
    bore = P.DM_LOCK_SHAFT_R + 0.3
    hex_c = P.DM_LOCK_KEY_AF / math.sqrt(3)
    snap_ok = (r_b < bore - 0.3 and hex_c < bore - 0.3 and P.DM_LOCK_PIN_R < bore
               and r_b - r_n >= 0.2 and P.DM_LOCK_SLOT / 2 >= 2 * (r_b - r_n))
    all_ok &= snap_ok
    print(f"  post lock     snap: barbs {2 * r_b:.1f} through the {2 * bore:.1f} bore, "
          f"{r_b - r_n:.2f} catch on the knob's {2 * r_n:.1f} neck, prongs close "
          f"{r_b - r_n:.2f} of {P.DM_LOCK_SLOT / 2:.2f}  {'ok' if snap_ok else 'PROBLEM'}")
    # the mic crown holds its board with no screws (2026-10-17): the sprung
    # lip's beam must bend far enough to pass the board's edge at a strain
    # PETG takes every time (cantilever: 3 b d / 2 L^2, kept under 2 %), the
    # lips must cover the edge, the pins clear the board's M2 holes, and the
    # pads clear its deepest part (6.74, Seeed's STEP)
    _b = P.CR_RING[1] - (P.MIC_R + P.CR_EDGE_GAP)
    _L = math.radians(P.CR_LATCH - P.CR_LATCH_ANCHOR) * (P.MIC_R + P.CR_EDGE_GAP + _b / 2)
    _d = P.CR_LIP[0] + P.CR_EDGE_GAP
    _eps = 3 * _b * _d / (2 * _L ** 2)
    # v2: the tongue wedges in a tapered socket -- self-locking needs the
    # taper's tangent well under PETG-on-PLA friction (~0.3), and each 0.1 a
    # print runs fat must not lift the seat more than the 7 mm of air over
    # the screen can take
    _run = P.DBP_SOCK_Y[1] - P.DBP_SOCK_Y[0] - 2.0
    _tan = P.DBP_SOCK_TAPER / _run
    _lift = 0.1 / _tan
    crown_ok = (_eps < 0.02 and P.CR_LIP[0] >= 0.8 and 2.2 - 1.8 >= 0.3
                and P.MIC_STANDOFF >= 6.74 + 1.0 and _tan < 0.15 and _lift < 3.0)
    all_ok &= crown_ok
    print(f"  mic crown     snap: sprung lip {_d:.2f} out on a {_L:.0f} mm beam, strain "
          f"{_eps * 100:.1f} %, lips {P.CR_LIP[0]:.1f} over the edge, pins 1.8 in 2.2, "
          f"pads {P.MIC_STANDOFF - 6.74:.2f} over the deepest part, socket taper "
          f"{math.degrees(math.atan(_tan)):.1f} deg (self-locking, seat +{_lift:.1f} per 0.1 fat)  "
          f"{'ok' if crown_ok else 'PROBLEM'}")
    # the DIN tilt adapter's hinge: head pressed into the base 7 mm short of
    # the teeth, through both knuckles into the nut in the thumb knob
    _tilt = [trimesh.load(os.path.join(REPO, "out", "stl", f"din_tilt_{n}.stl"))
             for n in ("base", "arm", "knob")]
    all_ok &= bolt("tilt hinge", (P.DTA_BASE_FACE + 7.0, *P.DTA_HINGE),
                   (-1.0, 0, 0), P.DTA_SCREW_L, _tilt)

print("\nALL SCREWS OK" if all_ok else "\nPROBLEMS FOUND")
