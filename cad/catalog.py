"""Measure every printed part and the assembled bench, for the hub's
Catalogue and Schematics tabs.

    python cad/catalog.py            ->  out/catalog.json
    python cad/catalog.py --inject   ->  ... and writes it into bench-hub.html

The hub is a single file opened straight off the disk, where a page cannot
fetch a JSON file beside it, so the data is embedded between two marker
comments. --inject replaces what is between them; nothing else in the hub is
touched. Run render_catalog.py first so renders/schematic/views.json exists.

Nothing here is typed in by hand. Part sizes, volumes and bed contact come off
the exported STLs (out/stl_frame), in the pose plates.py prints them in;
quantities, materials, walls and infill come from plates.py's own tables; the
assembly dimensions come off the seated meshes in out/frame, the same ones
assembly_fit_check.py test-fits. Design constants are read out of params.py
and frame.py with the comment that explains each one.

The bench stands on TPU pads that sit FOOT_PROUD below the printed parts, so
the desk is at z = -FOOT_PROUD in model coordinates; heights are given from
the desk, which is what a tape measure would read.
"""
import json
import math
import os
import re
import sys

import numpy as np
import trimesh

from viewer_data import MAX_TRIS, lighten

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ARGV = sys.argv[1:]
sys.argv = [sys.argv[0]]
_src = open(os.path.join(HERE, "plates.py"), encoding="utf-8").read().replace(
    'if __name__ == "__main__":', "if False:")
P = {"__name__": "plates", "__file__": os.path.join(HERE, "plates.py")}
exec(compile(_src, "plates.py", "exec"), P)

BUILD = ("04", "05", "06", "07", "07b", "08", "09", "09c", "10d", "10c", "10p", "11t")   # the bench itself, not the gauges
# Parts a later BUILD plate reprints: counted on the later plate only. 10p's
# posts (no latch, keeper) replace 09c's (2026-10-17).
SUPERSEDED = {("09c", "display_post")}
NICE = {
    "end_frame": "End frame, left", "end_frame_r": "End frame, right",
    "rear_tie": "Rear tie", "rail_cap": "Rail cap", "din_rail": "DIN rail",
    "deck_ladder": "Deck ladder", "foot_pad": "Foot pad", "rear_tray": "Rear tray",
    "side_tray": "Side tray (screws)", "side_bin": "Side bin", "display_post": "Display post", "display_backplate": "Display backplate",
    "rail_bin": "Rail bin", "display_lock": "Twist lock (hook + shaft)", "display_lock_knob": "Twist lock wing",
    "din_tilt_base": "DIN tilt adapter base", "din_tilt_arm": "DIN tilt adapter arm", "din_tilt_knob": "DIN tilt adapter knob",
    "mic_crown": "Mic crown",
}
ROLE = {
    "end_frame": "Carries every joint: rail mortise, three bar sockets, two foot pockets.",
    "end_frame_r": "Mirror of the left frame.",
    "rear_tie": "Half-round bar tying the frames together at the back; the rear tray sits on it.",
    "rail_cap": "Closes the frame's roof window over the rail end; two magnets pressed in.",
    "din_rail": "35 mm top-hat rail. Slides through both frame mortises; every clip module hangs on it.",
    "deck_ladder": "Two half-round rails and three deck plates, one part. The breadboards drop into pockets and onto pegs cut into its recessed ledges.",
    "foot_pad": "Press-fit TPU foot. Eighteen of them put the whole bench on rubber.",
    "rear_tray": "Parts tray behind the deck, with the two buttresses that carry the rail mid-span.",
    "side_tray": "Shallow tray that hangs on the left frame's screw heads by magnets.",
    "side_bin": "Deep bin that hangs on the right frame's screw heads by magnets.",
    "display_post": "Hooks over the rail's top lip and carries the display; its twist lock holds the foot down. Two, identical.",
    "display_lock": "Hook under a display post's foot with its own shaft through the foot: a quarter turn swings it under the rail's lower lip, its wedge top drawing the foot down. No screw.",
    "display_lock_knob": "The thumb wing: presses over the lock's hex and clicks onto its barbs. Along the post = locked.",
    "din_tilt_base": "Locks onto the rail like a display post (hook + twist lock); carries the hinge's fixed 24-tooth knuckle.",
    "din_tilt_arm": "A short TS35 stub on the hinge's moving knuckle: generic DIN devices clip here, at 15-degree steps from the rail's angle to flat.",
    "din_tilt_knob": "Thumb knob with a pressed M3 nut: loosen three turns, swing the arm, retighten.",
    "display_backplate": "Bridges the two posts to the CrowPanel P4's corner holes, clear of its components; a dovetail socket on its top edge takes the mic crown.",
    "mic_crown": "Holds the reSpeaker XVF3800 mic array above the screen, logo face out. Slides down the backplate's socket; the board clicks in under three lips. No screws.",
    "rail_bin": "Small bin that clips to the rail.",
}


GAUGE_ROLE = {
    "fit_coupon_frame": "The big test plate: three graded rail slots in front, four graded round sockets behind.",
    "rail_stub": "A 40 mm slice of the real DIN rail. Tests the slots, the gasket joint and, later, the clips.",
    "ladder_station_stub": "The first 64 mm of the real deck ladder: board shelf, first pocket, first peg, end screw holes.",
    "pilot_block": "A slice of the frame's post: two screw pilots in the 1.0 mm gasket pocket (TPU gasket version).",
    "pilot_block_oring": "The O-ring version: two stations, pockets 0.80 and 0.70 deep, pilots lying the way the real frame's do.",
    "foot_gauge": "First foot gauge: three identical 16.00 x 6.00 pockets. No pad would go in.",
    "foot_gauge_v2": "Second foot gauge: five pockets, +0.10 to +0.50. Pocket 3 won.",
    "spigot_stub": "A short length of the fat half-round bar (R8), with its end screw holes.",
    "tie_stub": "A short length of the thin half-round bar (R6).",
    "rail_cap_615": "Rail cap with 6.15 mm magnet pockets.", "rail_cap_625": "Rail cap with 6.25 mm magnet pockets.",
    "rail_cap_635": "Rail cap with 6.35 mm magnet pockets.",
    "fit_clips_petg": "Four test clips for the rail, the fourth with a chamfered latch.",
    "magnet_gauge": "Graded magnet pockets, both the sealed-in kind and the pushed-in-sideways kind.",
    "foot_pad_006": "Foot pad 0.06 oversize per side (16.12 x 6.12).", "foot_pad_012": "Foot pad 0.12 oversize (16.24 x 6.24), the production size.",
    "foot_pad_018": "Foot pad 0.18 oversize (16.36 x 6.36).", "tpu_block": "Plain 20 x 20 TPU block: the control that proved TPU prints on size.",
}


def round2(v):
    return [round(float(x), 2) for x in v]


def parts():
    qty, plate_of, mat_of = {}, {}, {}
    for pl in P["PLATES"]:
        if pl["n"] not in BUILD:
            continue
        for name, q in pl["objects"]:
            if (pl["n"], name) in SUPERSEDED:
                continue
            qty[name] = qty.get(name, 0) + q
            plate_of.setdefault(name, pl["n"])
            mat_of.setdefault(name, pl["mat"])
    # Three parts of the bench print on gauge plates rather than build plates:
    # the first four feet on plate 01 (the TPU rail gaskets are retired: O-rings).
    qty["foot_pad"] = qty.get("foot_pad", 0) + 4
    rows = []
    # Build order, structure first; the three parts that ride on gauge plates last.
    for name in sorted(qty, key=lambda n: (plate_of[n] not in BUILD, plate_of[n], n)):
        raw = trimesh.load(P["resolve_stl"](name), process=True)
        posed = P["posed_mesh"](name)
        walls, fill, brim = P["PART"].get(name, (3, "15%", False))
        n, a, zc = posed.face_normals, posed.area_faces, posed.triangles_center[:, 2]
        bed = float(a[(n[:, 2] < -0.99) & (zc < 0.05)].sum())
        pose = P["POSE"].get(name, 0)
        rows.append(dict(
            id=name, name=NICE.get(name, name), role=ROLE.get(name, ""),
            stl=os.path.relpath(P["resolve_stl"](name), ROOT).replace(os.sep, "/"),
            qty=qty[name], material=mat_of[name], plate=plate_of[name],
            size=round2(raw.extents), printed=round2(posed.extents),
            volume_cm3=round(raw.volume / 1000, 2),
            solid_g=round(raw.volume / 1000 * P["DENSITY"][mat_of[name]], 1),
            bed_mm2=round(bed), walls=walls, infill=fill, brim=bool(brim),
            pose="as modelled" if not pose else f"turned {pose[1]:+d} about {pose[0]}" if isinstance(pose, tuple) else f"turned {pose:+d} about X",
            watertight=bool(raw.is_watertight)))
    return rows


def assembly():
    src = os.path.join(ROOT, "out", "frame")
    meshes = {f[:-4]: trimesh.load(os.path.join(src, f), process=True)
              for f in sorted(os.listdir(src)) if f.endswith(".stl")}
    # Light stand-ins for the schematic renders. The vendor screen is 540k
    # triangles of pins and pads, and Freestyle's edge pass on it ran past
    # 29 GB and ten minutes for a single view. render_catalog.py takes a mesh
    # from out/frame_light when one is there; sizes here still come off the
    # real mesh, and hulls do not change a bounding box.
    light = os.path.join(ROOT, "out", "frame_light")
    os.makedirs(light, exist_ok=True)
    for k, m in meshes.items():
        if len(m.faces) > MAX_TRIS:
            lighten(m).export(os.path.join(light, k + ".stl"))

    def env(pred):
        pick = [m.bounds for k, m in meshes.items() if pred(k)]
        return np.array([np.min([b[0] for b in pick], 0), np.max([b[1] for b in pick], 0)])

    own_feet = {f"asm_foot{i}" for i in range(14)}           # 14..17 belong to the side modules
    core = lambda k: (k.startswith(("asm_frame", "asm_ladder", "asm_tie", "asm_tray", "asm_pad", "hw_"))  # noqa: E731
                      or k in own_feet or k in ("asm_rail", "asm_railcap_l", "asm_railcap_r"))
    sides = lambda k: core(k) or k.startswith(("asm_sidebin", "asm_sidetray", "asm_mag", "asm_stop", "asm_foot"))  # noqa: E731
    printed = lambda k: not k.startswith("prop_")  # noqa: E731
    everything = lambda k: True  # noqa: E731
    out = {}
    for key, label, pred in (("core", "Structure only: frames, ladder, tie, tray, rail, feet", core),
                             ("sides", "With the side tray and side bin", sides),
                             ("printed", "Everything printed, display posts up", printed),
                             ("all", "With the display and breadboards fitted", everything)):
        b = env(pred)
        out[key] = dict(label=label, lo=round2(b[0]), hi=round2(b[1]), size=round2(b[1] - b[0]))
    part = {k: dict(lo=round2(m.bounds[0]), hi=round2(m.bounds[1])) for k, m in meshes.items()}
    return out, part


def gauges():
    """The test pieces: everything on a plate that is not part of the bench."""
    # Bench parts also ride on reprint plates (04x, 06x, 09p): seed them as
    # seen, or each gets a second card under the gauges with the same id.
    seen = {name for pl in P["PLATES"] if pl["n"] in BUILD for name, _ in pl["objects"]}
    rows = []
    for pl in P["PLATES"]:
        if pl["n"] in BUILD:
            continue
        for name, q in pl["objects"]:
            if name in seen or name in ("foot_pad",):      # bench parts riding on gauge plates
                continue
            seen.add(name)
            raw = trimesh.load(P["resolve_stl"](name), process=True)
            posed = P["posed_mesh"](name)
            walls, fill, brim = P["PART"].get(name, (3, "15%", False))
            rows.append(dict(id=name, name=name.replace("_", " "), role=GAUGE_ROLE.get(name, ""), qty=q,
                             material=pl["mat"], plate=pl["n"],
                             stl=os.path.relpath(P["resolve_stl"](name), ROOT).replace(os.sep, "/"),
                             size=round2(raw.extents), printed=round2(posed.extents),
                             volume_cm3=round(raw.volume / 1000, 2),
                             solid_g=round(raw.volume / 1000 * P["DENSITY"][pl["mat"]], 1),
                             walls=walls, infill=fill, brim=bool(brim)))
    return rows


def hardware():
    """Everything that goes into the bench that is NOT printed.

    Where the assembly carries a model of the item (screws, magnets, boards,
    display) its size is measured off that mesh and its count is the number of
    copies in out/frame, so the list cannot drift from the model. Items the
    assembly does not model (O-rings, square nuts, the display's flange screws)
    are drawn here to their standard's nominal size, and say so.
    """
    src = os.path.join(ROOT, "out", "frame")
    dest = os.path.join(ROOT, "out", "hardware")
    os.makedirs(dest, exist_ok=True)
    names = sorted(f[:-4] for f in os.listdir(src) if f.endswith(".stl"))
    load = lambda n: trimesh.load(os.path.join(src, n + ".stl"), process=True)  # noqa: E731

    def laid_flat(mesh):
        """Own axes, longest along x, standing on z = 0 -- and its true size."""
        m = mesh.copy()
        m.apply_transform(np.linalg.inv(m.bounding_box_oriented.primitive.transform))
        order = np.argsort(-m.extents)                      # longest, middle, shortest -> x, y, z
        R = np.eye(4); R[:3, :3] = np.eye(3)[order]
        m.apply_transform(R)
        if np.linalg.det(R[:3, :3]) < 0:                    # keep it a rotation, not a mirror
            m.apply_transform(np.diag([1, 1, -1, 1])); m.invert()
        m.apply_translation(-m.bounds[0])
        return m

    rows = []

    def add(id_, name, qty, spec, where, mesh, kind, source, note="", length=None):
        m = laid_flat(mesh)
        m.export(os.path.join(dest, id_ + ".stl"))
        size = round2(m.extents)
        if length is not None:                              # pictured by a longer sibling
            size[0] = float(length)
        rows.append(dict(id=id_, name=name, qty=qty, spec=spec, where=where, kind=kind, source=source, note=note,
                         stl=f"out/hardware/{id_}.stl", size=size))

    ends = [n for n in names if n.startswith("hw_end")]
    rails = [n for n in names if n.startswith("hw_rail")]
    mags = [n for n in names if n.startswith("asm_mag")]
    add("screw_m3x12_cap", "M3 x 12 socket head cap screw", len(ends) + len(rails),
        "ISO 4762, black-oxide ALLOY steel (not stainless)",
        "Every structural joint, one screw: six bar ends through the frames into the ladder and tie, and eight "
        "holding the DIN rail to the frames and the rear-tray buttresses, heads sunk in counterbores below the "
        "clip face. The bar-end heads are what the side tray and side bin hang on by magnet, and the rail caps' "
        "magnets sit on the rail screws, which is why they must be magnetic steel.",
        load(ends[0]), "steel", "measured off the model")
    add("magnet_6x2", "N52 neodymium disc, dia 6 x 2", len(mags), "N52, nickel plated",
        "5 in the side bin and 8 in the side tray (dropped in at the Z = 3.2 print pause, or pushed in through the "
        "head pockets), 2 pressed into each rail cap. Never heat one: N52 fades above about 80 C.",
        load(mags[0]), "nickel", "measured off the model")
    ring = trimesh.creation.torus(major_radius=2.0, minor_radius=0.5, major_sections=64, minor_sections=24)
    add("oring_3x1", "O-ring, 3 ID x 1 section", 8, "NBR 70A or similar, from the ZDBB kit",
        "Proposed rail gasket: one around each of the eight rail screws, in the gasket pocket between rail and post. "
        "Replaces the four printed TPU gaskets if the plate 02c test passes; the pocket then becomes 0.70-0.80 deep.",
        ring, "rubber", "drawn to nominal size", note="Confirmed on plate 02c, 2026-09-19: two per screw station in a 0.80 gland replace the printed TPU gasket.")
    # Hex, because that is what is on hand. The posts' nut channel was drawn for
    # a DIN 562 square nut (5.5 AF x 1.8) at 5.8 wide x 2.2 deep, open on the
    # post's back face. A hex nut is the same 5.5 across flats, so it slides in;
    # it is 6.01-6.35 across corners, so it cannot turn in a 5.8 channel; and it
    # is 2.4 thick, so it stands 0.2 proud of the back face -- into free air,
    # since the slot starts above the rail. Checked against display_post.stl.
    af, thick = 5.5, 2.4
    nut = trimesh.creation.cylinder(radius=af / math.sqrt(3), height=thick, sections=6).difference(
        trimesh.creation.cylinder(radius=1.5, height=4.0, sections=48), engine="manifold")
    add("nut_m3_hex", "M3 hex nut", 8, "DIN 934 / ISO 4032, 5.5 across flats x 2.4",
        "Two in the nut channel on the back of each display post, slid in from the top with the posts lying "
        "face-up on the table, for the backplate's M3 x 8s (flats against the channel walls, so it cannot turn); "
        "four pressed into the hex pockets in the backs of the backplate's corner bosses, for the screen's "
        "M3 x 16s.",
        nut, "steel", "drawn to nominal size",
        note="The channel was drawn for a DIN 562 square nut (5.5 x 1.8). A hex nut fits and cannot spin in the 5.8 mm "
             "channel; it stands 0.2 mm proud of the post's back face, which touches nothing. It bears on about 40% "
             "less ledge than a square nut, so snug the display screws, do not crank them.")
    head = trimesh.creation.cylinder(radius=2.8, height=2.4, sections=48); head.apply_translation((0, 0, 1.2))
    shank = trimesh.creation.cylinder(radius=1.5, height=8.0, sections=32); shank.apply_translation((0, 0, -4.0))
    add("screw_m3x8_cap", "M3 x 8 socket head cap screw", 4, "ISO 4762",
        "Backplate to the display posts, two per post: heads in the backplate's counterbores, through the posts' "
        "slots into the hex nuts. The tip lands flush with the nut's back face. Stainless is fine here: no magnet "
        "touches these.",
        trimesh.util.concatenate([head, shank]), "steel", "drawn to nominal size")
    shank16 = trimesh.creation.cylinder(radius=1.5, height=16.0, sections=32); shank16.apply_translation((0, 0, -8.0))
    add("screw_m3x16_cap", "M3 x 16 socket head cap screw", 4, "ISO 4762",
        "Four for the screen: through its corner slots and the backplate's 3.4 bores into the nuts pressed into the "
        "bosses' backs (2026-10-17 -- the self-tapping bosses split). The twist locks need none: they snap.",
        trimesh.util.concatenate([head, shank16]), "steel", "drawn to nominal size")
    for id_, name, prefix, where in (
            ("breadboard_full", "Full-size solderless breadboard", "prop_bb_", "Recessed into the ladder's ledges, left bay."),
            ("breadboard_half", "Half-size solderless breadboard", "prop_hb_", "Recessed into the ladder's ledges, right bay."),
            ("display_cp7", "CrowPanel Advanced 7in ESP32-P4 display", "prop_cp7_",
             "Four M3 x 16 through its corner slots into nuts in the backplate's bosses; the backplate bolts to "
             "the two display posts, tilted back 37 degrees.")):
        group = [load(n) for n in names if n.startswith(prefix)]
        body = max(group, key=lambda m: m.volume)
        if len(body.faces) > MAX_TRIS:                      # the vendor STEP: 540k triangles
            body = lighten(body)
        add(id_, name, 1, "as modelled in the assembly; check against the unit in hand", where, body, "board", "measured off the model")
    return rows


def dims(env, part):
    """Dimension lines for the three schematic views, in world millimetres.

    Each is (view, direction, a, b, tier, from, label): a..b is the span along
    the view's horizontal ('h') or vertical ('v') axis, `tier` stacks the lines
    outward from the drawing, and `from` is where the extension lines start (the
    feature's own edge on the other axis). The hub draws them; nothing here or
    there is positioned by eye.
    """
    desk = env["core"]["lo"][2]                       # -FOOT_PROUD: the pads' desk faces
    fl, fr = part["asm_frame_l"], part["asm_frame_r"]
    lad, tie, tray, rail = part["asm_ladder"], part["asm_tie"], part["asm_tray"], part["asm_rail"]
    sbin, stray, post = part["asm_sidebin"], part["asm_sidetray"], part["asm_post0"]
    bb, hb = part["prop_bb_body"], part["prop_hb_body"]
    out = []

    def add(view, d, a, b, tier, frm, label):
        out.append(dict(view=view, dir=d, a=round(a, 2), b=round(b, 2), tier=tier, frm=round(frm, 2), label=label))

    # front: x across, z up
    add("front", "h", env["sides"]["lo"][0], env["sides"]["hi"][0], 3, desk, "overall, side tray to side bin")
    add("front", "h", fl["lo"][0], fr["hi"][0], 2, desk, "frame to frame, outer faces = rail length")
    add("front", "h", lad["lo"][0], lad["hi"][0], 1, desk, "deck ladder and rear tie")
    add("front", "v", desk, env["all"]["hi"][2], 3, env["all"]["hi"][0], "desk to top of display")
    add("front", "v", desk, post["hi"][2], 2, env["all"]["hi"][0], "desk to top of display posts")
    add("front", "v", desk, env["core"]["hi"][2], 1, env["all"]["hi"][0], "desk to top of frames")
    # top: x across, y back
    add("top", "h", env["sides"]["lo"][0], env["sides"]["hi"][0], 3, env["all"]["lo"][1], "overall width")
    add("top", "h", bb["lo"][0], bb["hi"][0], 2, env["all"]["lo"][1], "full-size breadboard")
    add("top", "h", hb["lo"][0], hb["hi"][0], 1, env["all"]["lo"][1], "half-size breadboard")
    add("top", "h", stray["lo"][0], stray["hi"][0], 1, env["all"]["lo"][1], "side tray")
    add("top", "h", sbin["lo"][0], sbin["hi"][0], 2, env["all"]["lo"][1], "side bin")
    add("top", "v", env["all"]["lo"][1], env["all"]["hi"][1], 3, env["all"]["hi"][0], "overall depth, display posts up")
    add("top", "v", env["core"]["lo"][1], env["core"]["hi"][1], 2, env["all"]["hi"][0], "frame depth")
    add("top", "v", lad["lo"][1], lad["hi"][1], 1, env["all"]["hi"][0], "deck ladder")
    # side: y across (front of the bench to the left), z up
    add("side", "h", env["all"]["lo"][1], env["all"]["hi"][1], 2, desk, "overall depth")
    add("side", "h", env["core"]["lo"][1], env["core"]["hi"][1], 1, desk, "frame depth")
    add("side", "v", desk, env["all"]["hi"][2], 3, env["all"]["hi"][1], "desk to top of display")
    add("side", "v", desk, rail["hi"][2], 2, env["all"]["hi"][1], "desk to top edge of rail")
    add("side", "v", desk, lad["hi"][2], 1, env["all"]["hi"][1], "desk to top of deck rails")
    return out


def constants():
    rows = []
    for fn in ("params.py", "frame.py"):
        for line in open(os.path.join(HERE, fn), encoding="utf-8-sig"):
            m = re.match(r"^([A-Z][A-Z0-9_]+)\s*=\s*(-?\d+(?:\.\d+)?)\s*(?:#\s*(.*))?$", line.rstrip())
            if m:
                rows.append(dict(name=m.group(1), value=float(m.group(2)), note=(m.group(3) or "").strip(), file=fn))
    return rows


def inject(data):
    hub = os.path.join(ROOT, "bench-hub.html")
    views = json.load(open(os.path.join(ROOT, "renders", "schematic", "views.json"), encoding="utf-8"))
    html = open(hub, encoding="utf-8").read()
    start, end = "<!-- CATALOG-DATA:START", "<!-- CATALOG-DATA:END -->"
    a, b = html.index(start), html.index(end)
    # "</" inside a JSON string would end the script element early.
    pack = lambda o: json.dumps(o, separators=(",", ":")).replace("</", "<\\/")  # noqa: E731
    block = (start + " (written by: python cad/catalog.py --inject) -->\n"
             f'<script type="application/json" id="catalog-data">{pack(data)}</script>\n'
             f'<script type="application/json" id="schematic-views">{pack(views)}</script>\n')
    open(hub, "w", encoding="utf-8").write(html[:a] + block + html[b:])
    print("injected into", os.path.normpath(hub))


if __name__ == "__main__":
    want_inject = "--inject" in ARGV
    env, part = assembly()
    data = dict(parts=parts(), gauges=gauges(), hardware=hardware(), envelopes=env, dims=dims(env, part),
                constants=constants())
    dest = os.path.join(ROOT, "out", "catalog.json")
    json.dump(data, open(dest, "w", encoding="utf-8"), indent=1)
    print(os.path.normpath(dest))
    for r in data["parts"]:
        print(f"  {r['name']:22s} x{r['qty']:<3d} {r['material']:5s} {r['size'][0]:7.2f} x {r['size'][1]:7.2f} x {r['size'][2]:6.2f}   {r['volume_cm3']:6.2f} cm3  {r['solid_g']:5.1f} g   plate {r['plate']}")
    for h in data["hardware"]:
        print(f"  {h['name']:36s} x{h['qty']:<3d} {h['size'][0]:7.2f} x {h['size'][1]:6.2f} x {h['size'][2]:5.2f}   {h['source']}")
    for k, e in env.items():
        print(f"  {e['label']:55s} {e['size'][0]:7.2f} W x {e['size'][1]:7.2f} D x {e['size'][2]:7.2f} H   z {e['lo'][2]:.2f}..{e['hi'][2]:.2f}")
    print(f"  {len(data['constants'])} design constants")
    if want_inject:
        inject(data)
