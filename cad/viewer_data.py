"""Pack the assembly into a compact blob the web viewer can eat.

Positions only -- the shader derives face normals from screen-space derivatives,
so shipping normals would double the payload for nothing. Coordinates are
quantised to uint16 per part with a per-part box, which is another 2x and is
well inside the tolerance of something you look at rather than measure.
"""

import base64
import json
import math
import os
import sys

import numpy as np
import trimesh

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")

# `python viewer_data.py console` packs the console assembly instead;
# `posts` packs the frame with the v2 two-post display mount. Same blob
# format, own manifest, written beside the frame's.
VARIANT = ("console" if "console" in sys.argv[1:]
           else "mountv1" if "mountv1" in sys.argv[1:]
           else "tievee" if "tievee" in sys.argv[1:]
           # the proposed recessed-ledge deck, staged by cad/ledge_ladder.py
           else "ledge" if "ledge" in sys.argv[1:] else "frame")

# name -> (label, group, colour). Groups drive the viewer's toggles.
# Parts sharing a label merge into one manifest row with a quantity, which is
# what you actually queue on the printer -- the two end frames are one part
# printed twice, not two parts.
PARTS = {
    "asm_frame_l":  ("End frame", "structure", "#c9c3b6"),
    "asm_frame_r":  ("End frame", "structure", "#c9c3b6"),
    "asm_ladder":   ("Deck ladder", "structure", "#c9c3b6"),
    "asm_tie":      ("Rear tie rod", "structure", "#c9c3b6"),
    "asm_tray":     ("Rear tray", "structure", "#bdb7ab"),
    # All sixteen, one manifest row -- 4 tray, 6 ladder, 4 end frame, 2 side
    # bin. They used to be a footnote ("aren't shown here"); now they are
    # just shown.
    **{f"asm_foot{i}": ("TPU foot pad", "tpu", "#4e565e")
       for i in range(18)},
    "asm_rail":     ("DIN rail (TS35)", "rail", "#2e3338"),
    "asm_pad0":     ("Rail gasket", "tpu", "#4e565e"),
    "asm_pad1":     ("Rail gasket", "tpu", "#4e565e"),
    "asm_pad2":     ("Rail gasket", "tpu", "#4e565e"),
    "asm_pad3":     ("Rail gasket", "tpu", "#4e565e"),
    # The steel. Six through the frames into the bar-end pilots, eight through
    # the DIN rail into the frames and buttresses. One screw everywhere, on
    # purpose: since the rail counterbore (2026-10-04) all fourteen are the
    # same M3 x 12 cap, so they share one manifest row.
    **{f"hw_end{i}": ("M3 x 12 socket cap (magnetic)", "hardware", "#2a2c30")
       for i in range(6)},
    **{f"hw_rail{i}": ("M3 x 12 socket cap (magnetic)", "hardware", "#2a2c30")
       for i in range(8)},
    # The N52 discs -- bought, not printed, so they never appear in the
    # printable parts. One manifest row; they ride in the hardware group so
    # they toggle with the steel they are there to grab.
    **{f"asm_mag{i}": ("N52 magnet, D6 x 2", "hardware", "#c2c7cd")
       for i in range(17)},
    # asm_plate / asm_screen stay listed but are off the rail while the
    # display mount is prototyped -- absent STLs are skipped, so these rows
    # come back the moment frame.py places them again.
    "asm_plate":    ("Board plate (ESP32)", "modules", "#b4501f"),
    "asm_screen":   ("Screen bezel", "modules", "#b4501f"),
    "asm_railbin":  ("Rail bin", "modules", "#b4501f"),
    # v2 ships: two posts, one part printed twice. The five v1 rows stay
    # listed because absent STLs are skipped -- they light up only in the
    # retired mountv1 variant, and would come straight back if frame.py
    # ever placed them again.
    "asm_post0":    ("Display post (v2)", "modules", "#b4501f"),
    "asm_post1":    ("Display post (v2)", "modules", "#b4501f"),
    # The screen's backplate (plate 10d). PLA, so it wears the structure's
    # colour and MAT_OF overrides the group's PETG -- but it rides in the
    # modules group because it comes off the rail with the posts.
    "asm_backplate": ("Display backplate", "modules", "#c9c3b6"),
    # each post's twist lock, PETG like the post (2026-10-17)
    "asm_lock0":     ("Twist lock", "modules", "#b4501f"),
    "asm_lock1":     ("Twist lock", "modules", "#b4501f"),
    "asm_lockknob0": ("Twist lock wing", "modules", "#b4501f"),
    "asm_lockknob1": ("Twist lock wing", "modules", "#b4501f"),
    # the mic crown (plate 10c), PETG, slid down the backplate's socket
    "asm_crown":     ("Mic crown", "modules", "#b4501f"),
    "asm_dspine":   ("Display mount spine (v1)", "modules", "#b4501f"),
    "asm_dupright0": ("Display mount upright (v1)", "modules", "#b4501f"),
    "asm_dupright1": ("Display mount upright (v1)", "modules", "#b4501f"),
    "asm_dcross0":  ("Display mount crossbar (v1)", "modules", "#b4501f"),
    "asm_dcross1":  ("Display mount crossbar (v1)", "modules", "#b4501f"),
    "asm_sidebin":  ("Side bin", "modules", "#b4501f"),
    "asm_sideblank": ("Base skid (left)", "structure", "#c9c3b6"),
    "asm_sidetray": ("Screw tray (left)", "modules", "#b4501f"),
    "asm_railcap_l": ("Rail cap", "structure", "#c9c3b6"),
    "asm_railcap_r": ("Rail cap", "structure", "#c9c3b6"),
    "asm_stop0":     ("Deck stop", "modules", "#b4501f"),
    "asm_stop1":     ("Deck stop", "modules", "#b4501f"),
    "prop_bb_body": ("Breadboard, 830pt", "fitted", "#e8e6e0"),
    "prop_bb_holes": ("", "fitted", "#3a3a3e"),
    "prop_bb_red":  ("", "fitted", "#a8231f"),
    "prop_bb_blue": ("", "fitted", "#1e3f8f"),
    "prop_hb_body": ("Breadboard, 400pt", "fitted", "#e8e6e0"),
    "prop_hb_holes": ("", "fitted", "#3a3a3e"),
    "prop_hb_red":  ("", "fitted", "#a8231f"),
    "prop_hb_blue": ("", "fitted", "#1e3f8f"),
    "prop_esp_pcb": ("ESP32 DevKit", "fitted", "#16202b"),
    "prop_esp_shield": ("", "fitted", "#9aa3ad"),
    "prop_esp_pins": ("", "fitted", "#2a2a2e"),
    "prop_eink_glass": ("2.9in e-paper", "fitted", "#e6e4de"),
    "prop_eink_pcb": ("", "fitted", "#16202b"),
    "prop_eink_ink": ("", "fitted", "#22242a"),
    "prop_hmi_body": ("7in HMI display", "fitted", "#16202b"),
    "prop_hmi_glass": ("", "fitted", "#0c0f14"),
    "prop_hmi_ui": ("", "fitted", "#3a7ba8"),
    # The real screen, from Elecrow's STEP (frame.py places it on the
    # backplate's bosses). Replaces the 7in HMI box above, which frame.py no
    # longer exports.
    "prop_cp7_body": ("CrowPanel P4, 7in", "fitted", "#16202b"),
    "prop_cp7_glass": ("", "fitted", "#0c0f14"),
    "prop_cp7_ui": ("", "fitted", "#3a7ba8"),
    # the reSpeaker XVF3800 in the crown, from Seeed's STEP (2026-10-17)
    "prop_mic_pcb": ("reSpeaker XVF3800", "fitted", "#121417"),
    "prop_mic_parts": ("", "fitted", "#9aa0a8"),
}

# The console's manifest: a moulded base instead of the five frame parts,
# no TPU stance system, and the rail screws straight to the panel.
CONSOLE_PARTS = {
    "asm_base":     ("Console base", "structure", "#c9c3b6"),
    "asm_rail":     ("DIN rail (TS35)", "rail", "#2e3338"),
    "asm_bin":      ("Rail bin", "modules", "#b4501f"),
    "asm_dspine":   ("Display mount spine", "modules", "#b4501f"),
    "asm_dupright0": ("Display mount upright", "modules", "#b4501f"),
    "asm_dupright1": ("Display mount upright", "modules", "#b4501f"),
    "asm_dcross0":  ("Display mount crossbar", "modules", "#b4501f"),
    "asm_dcross1":  ("Display mount crossbar", "modules", "#b4501f"),
    "prop_bb_body": ("Breadboard, 830pt", "fitted", "#e8e6e0"),
    "prop_bb_holes": ("", "fitted", "#3a3a3e"),
    "prop_bb_red":  ("", "fitted", "#a8231f"),
    "prop_bb_blue": ("", "fitted", "#1e3f8f"),
    "prop_hb_body": ("Breadboard, 400pt", "fitted", "#e8e6e0"),
    "prop_hb_holes": ("", "fitted", "#3a3a3e"),
    "prop_hb_red":  ("", "fitted", "#a8231f"),
    "prop_hb_blue": ("", "fitted", "#1e3f8f"),
    "prop_hmi_body": ("7in HMI display", "fitted", "#16202b"),
    "prop_hmi_glass": ("", "fitted", "#0c0f14"),
    "prop_hmi_ui": ("", "fitted", "#3a7ba8"),
}

# Recommended filament per group, not what the exporter currently tags.
# Structure wants PLA's stiffness, the snap-fit clips want PETG's strain
# budget, and the feet want TPU's grip.
MATERIAL = {"structure": "PLA", "rail": "PLA", "modules": "PETG",
            "tpu": "TPU", "hardware": "Steel", "fitted": "", }
# Parts whose filament is not their group's.
MAT_OF = {"asm_backplate": "PLA"}

# The vendor STEP's screen body is 540k triangles -- 13 MB of viewer for a
# part you look at rather than measure. Anything over this is lightened.
MAX_TRIS = 40000


def lighten(m):
    """Swap each dense component for its convex hull, where the hull still
    reads as the part. Quadric decimation stalls at ~170k on this mesh: the
    STEP tessellates every pin and pad as its own open shell, and boundary
    edges do not collapse. Hulls turn a 160k-triangle pin header into a
    block, which at viewing distance it is. A component whose hull is more
    than 3x its volume (a folded FPC, a hooked bracket) keeps its triangles,
    since its hull would be a solid wedge that is not there.
    A board of many small parts (the XVF3800: 580 components, each under
    1500 triangles) stays heavy after that pass, so the size floor drops
    until the whole mesh fits the budget, and at the last step a part
    becomes its oriented box (a round part's hull keeps every facet)."""
    parts = m.split(only_watertight=False)
    for floor, box in ((1500, False), (200, False), (24, True)):
        out = []
        for c in parts:
            if len(c.faces) > floor:
                h = c.bounding_box_oriented if box else c.convex_hull
                if box or not c.is_watertight or h.volume < 3.0 * abs(c.volume):
                    c = h
            out.append(c)
        res = trimesh.util.concatenate(out)
        if len(res.faces) <= 2 * MAX_TRIS:      # the screen's 40,140 is fine as it is
            break
    return res


# A breadboard is four meshes (body, hole grid, two rails) but one object you
# pick up. `row` is what the manifest groups and highlights on; `name` is set
# only on the mesh that stands for the whole item, so quantities count objects
# rather than meshes.
SUBMESH_OF = (
    ("prop_bb", "Breadboard, 830pt"),
    ("prop_hb", "Breadboard, 400pt"),
    ("prop_esp", "ESP32 DevKit"),
    ("prop_eink", "2.9in e-paper"),
    ("prop_hmi", "7in HMI display"),
    ("prop_cp7", "CrowPanel P4, 7in"),
    ("prop_mic", "reSpeaker XVF3800"),
)


def row_of(name, label):
    for prefix, row in SUBMESH_OF:
        if name.startswith(prefix):
            return row
    return label


def explode_dir(name, group, c):
    """Where each part flies when the assembly is pulled apart.

    Pure radial-from-centre reads as an explosion rather than an assembly
    drawing: parts cross each other's paths and the eye loses which came from
    where. Instead each subassembly gets its own horizontal band -- ribs drop
    below the deck, the frame spreads in the ground plane, the rail lifts, and
    the modules lift clear above it -- so nothing overlaps anything it did not
    come from.
    """
    if name.startswith(("prop_bb", "prop_hb")):
        return [0.0, 40.0, 34.0]              # boards lift off the deck
    if name == "asm_base":
        return [0.0, 0.0, -34.0]              # the moulding drops away below
    if VARIANT == "console":
        # The console's panel leans back, so everything on it unclips up
        # and FORWARD (toward -y) instead of the frame's rearward post.
        if group == "modules" or name.startswith("prop_hmi"):
            return [c[0] * 0.18, -62.0, 62.0]
        if group == "rail":
            return [0.0, -44.0, 48.0]
    if name == "asm_sidebin":
        return [64.0, 8.0, 0.0]               # slides off the side face
    if name in ("asm_sideblank", "asm_sidetray"):
        return [-64.0, 8.0, 0.0]              # off the left face
    if name.startswith("asm_railcap"):
        return [0.0, 26.0, 22.0]              # lifts out of the shroud window
    if name.startswith("asm_stop"):
        return [0.0, 30.0, 0.0]               # stops lift out of the cradle
    # The screen stack lifts with the posts, then pulls apart along the glass
    # normal -- the panel leans back 37 deg, so that is up and forward
    # (viewer y up, +z toward you): backplate off the posts, screen off it.
    if name == "asm_backplate":
        return [0.0, 88.0 + 18 * 0.60, 8.0 + 18 * 0.80]
    if name.startswith("prop_cp7"):
        return [0.0, 88.0 + 46 * 0.60, 8.0 + 46 * 0.80]
    if name == "asm_crown":                   # lifts up its socket, off the top
        return [0.0, 88.0 + 30 * 0.80, 8.0 - 30 * 0.60]
    if name.startswith("prop_mic"):
        return [0.0, 88.0 + 30 * 0.80 + 30 * 0.60, 8.0 - 30 * 0.60 + 30 * 0.80]
    if group == "modules" or name.startswith(("prop_esp", "prop_eink",
                                              "prop_hmi")):
        return [c[0] * 0.18, 88.0, 8.0]       # modules unclip up off the rail
    if name.startswith("hw_end"):             # bar-end screws back out axially
        return [44.0 if c[0] > 0 else -44.0, 6.0, 0.0]
    if name.startswith("hw_rail"):            # rail screws rise off the post
        return [0.0, 34.0, 30.0]
    if name.startswith("asm_foot"):
        return [c[0] * 0.15, -52.0, -20.0]    # feet drop out below
    if group == "tpu":
        return [c[0] * 0.20, 52.0, 46.0]      # gaskets come off with the joint
    if group == "rail":
        return [0.0, 58.0, -26.0]             # rail lifts up and back
    if name == "asm_tray":
        return [0.0, -16.0, -74.0]            # tray slides out the back
    if name == "asm_ladder":
        return [0.0, -30.0, 44.0]             # the deck drops down and forward
    span = math.hypot(c[0], c[2]) or 1.0      # end frames out, deck rails apart
    return [c[0] / span * 58.0, 4.0, c[2] / span * 42.0]


def main():
    # Emit in PARTS order, not filename order, so the viewer's parts schedule
    # reads as a build sequence -- frame, rail, modules, then what sits on it --
    # rather than an alphabetical accident of how the STLs were named.
    manifest = CONSOLE_PARTS if VARIANT == "console" else dict(PARTS)
    src = os.path.join(OUT, {"console": "assembly",
                             "mountv1": "frame_mountv1",
                             "tievee": "frame_vee",
                             "ledge": "frame_ledge"}.get(VARIANT, "frame"))
    have = {fn[:-4] for fn in os.listdir(src) if fn.endswith(".stl")}
    meshes = {n: trimesh.load(os.path.join(src, n + ".stl"))
              for n in manifest if n in have}
    for n, m in list(meshes.items()):
        if len(m.faces) > MAX_TRIS:
            meshes[n] = lighten(m)
            print(f"  {n}: {len(m.faces)} -> {len(meshes[n].faces)} triangles")

    allv = np.vstack([m.vertices for m in meshes.values()])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    centre = (lo + hi) / 2

    parts, tris = [], 0
    for name, m in meshes.items():
        label, group, colour = manifest[name]
        v = m.triangles.reshape(-1, 3).astype(np.float64)
        # Y-up for the viewer, and centred on the object
        v = v - centre
        v = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
        pmin, pmax = v.min(axis=0), v.max(axis=0)
        span = np.maximum(pmax - pmin, 1e-6)
        q = np.round((v - pmin) / span * 65535).astype(np.uint16)
        tris += len(v) // 3
        cen = (pmin + pmax) / 2
        parts.append({
            "name": label, "row": row_of(name, label),
            "group": group, "colour": colour,
            "mat": MAT_OF.get(name, MATERIAL[group]),
            "min": [round(x, 3) for x in pmin],
            "span": [round(x, 3) for x in span],
            "ex": [round(x, 1) for x in explode_dir(name, group, cen)],
            "n": len(v),
            "p": base64.b64encode(q.tobytes()).decode("ascii"),
        })

    blob = {"size": [round(x, 1) for x in (hi - lo)], "parts": parts}
    path = os.path.join(OUT, {"console": "viewer_data_console.json",
                              "mountv1": "viewer_data_mountv1.json",
                              "tievee": "viewer_data_tievee.json",
                              "ledge": "viewer_data_ledge.json"}
                        .get(VARIANT, "viewer_data.json"))
    with open(path, "w") as f:
        json.dump(blob, f, separators=(",", ":"))
    kb = os.path.getsize(path) / 1024
    print(f"  {len(parts)} parts, {tris} triangles, {kb:.0f} KB")
    print(f"  bench {blob['size'][0]:.0f} x {blob['size'][1]:.0f} x "
          f"{blob['size'][2]:.0f} mm")
    print(f"  -> {path}")


if __name__ == "__main__":
    main()
