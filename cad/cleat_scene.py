"""The board-retention rework, as pictures: pocket, peg, and a board dropping in.

    python cad/cleat_scene.py              -> out/story/cleat_*/ + scene.json
    blender -b -P cad/story_render.py      -> renders/story/cleat_*.png

Why this file exists. The assembly's breadboard prop is 165.10 x 54.74 x 9.40 --
the PLAIN width, with no dovetail cleats on it at all. Every picture of the new
retention drawn against that prop would show a board dropping into pockets it
does not have, which is worse than no picture. So the cleats get modelled here,
from the measured board, and the rails are cut to the constants the gauges
settled:

    RAIL_GAP      55.14   settled on plate 02i, 2 dots ("nice")
    PEG_W          3.8    settled on plate 02h, 4 dots
    STATION_SPAN  65.21   user's caliper, tip centre to tip centre
    tab           5.20 tall, 4.07 at the tip, 1.41 proud
    notch         1.60 deep, directly opposite a tab

THREE cleats per edge, not two -- counted off an overhead photo of the board.
They are placed symmetrically about the board's centre at the measured spacing,
which puts them within about 1 mm of where the photo found them (16.5 / 82.1 /
148.8 along a 165.1 board).

Two scenes:
    cleat_drop      the board held above its rails, tabs over their pockets and
                    notches over their pegs, about to go straight down
    cleat_seated    the same, seated, sectioned through the middle station so
                    the tab-in-pocket and peg-in-notch are both visible at once
"""
import json
import os

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "out", "story")
SRC = os.path.join(ROOT, "out", "frame")

PLA = dict(colour=[0.115, 0.120, 0.132], rough=0.62)
BOARD = dict(colour=[0.82, 0.81, 0.78], rough=0.45)
HOLE = dict(colour=[0.02, 0.02, 0.025], rough=0.7)
RED = dict(colour=[0.55, 0.05, 0.05], rough=0.5)
BLUE = dict(colour=[0.04, 0.10, 0.45], rough=0.5)

def _measured(board, fallback):
    """Whatever was punched in on board.html, else the last known values.

    The page writes out/board_dims.json and the CAD reads it, so a number the
    user corrects at the bench reaches the geometry without editing a file.
    """
    import json
    p = os.path.join(ROOT, "out", "board_dims.json")
    try:
        with open(p, encoding="utf-8") as f:
            got = (json.load(f) or {}).get(board) or {}
    except Exception:
        return dict(fallback), "built-in defaults"
    out = dict(fallback)
    out.update({k: v for k, v in got.items() if isinstance(v, (int, float))})
    return out, "out/board_dims.json"


_B, DIM_SRC = _measured("full", dict(L=165.10, W=54.74, H=9.40, N=3, SP=65.21,
                                     TAB_W=4.07, TAB_BASE=3.85, TAB_H=5.20,
                                     TAB_PROUD=1.41, NOTCH_D=1.60))
BOARD_L, BOARD_W, BOARD_H = _B["L"], _B["W"], _B["H"]
TAB_W_TIP, TAB_W_BASE = _B["TAB_W"], _B["TAB_BASE"]
TAB_H, TAB_PROUD = _B["TAB_H"], _B["TAB_PROUD"]
NOTCH_D = _B["NOTCH_D"]
SPAN = _B["SP"]
N_STATIONS = int(round(_B["N"]))
RAIL_GAP = 55.14
PEG_W, PEG_D = 3.8, 1.3
FIT = 0.3
RAIL_W, RAIL_H, FLOOR = 6.0, 10.2, 3.0
RIM = 0.6
STATIONS = [BOARD_L / 2 + (k - (N_STATIONS - 1) / 2) * SPAN
            for k in range(N_STATIONS)]


def to_manifold(m):
    return Manifold(Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                         tri_verts=np.asarray(m.faces, np.uint32)))


def to_trimesh(man):
    msh = man.to_mesh()
    return trimesh.Trimesh(np.asarray(msh.vert_properties)[:, :3],
                           np.asarray(msh.tri_verts), process=True)


def tab_solid(x, y_face, outward):
    """One dovetail tab: narrower at the board, wider at the tip. Built as a
    thin loft by stacking two slabs -- enough at render scale, and it keeps the
    3 degree undercut visible without a full loft."""
    parts = []
    steps = 6
    for i in range(steps):
        f = i / (steps - 1)
        w = TAB_W_BASE + (TAB_W_TIP - TAB_W_BASE) * f
        d = TAB_PROUD / steps
        # a cube spans [origin, origin + d], so the origin is the FAR edge of
        # this slice: -(i+1)*d, not -i*d. With -i*d the innermost slab sits
        # inside the board and the tab ends up one slice short of TAB_PROUD.
        slab = Manifold.cube((w, d, TAB_H)).translate(
            (x - w / 2, y_face + outward * ((i + 1) * d), 0))
        parts.append(slab)
    out = parts[0]
    for p in parts[1:]:
        out += p
    return out


def board_with_cleats():
    """The assembly's own board prop, with its cleats cut in: tabs on the -y
    edge, notches directly opposite on +y, at the same three stations."""
    body = to_manifold(trimesh.load(os.path.join(SRC, "prop_bb_body.stl"), process=True))
    lo = trimesh.load(os.path.join(SRC, "prop_bb_body.stl"), process=True).bounds[0]
    body = body.translate((-lo[0], -lo[1], -lo[2]))          # origin at the corner
    for x in STATIONS:
        # male tab on the -y edge, its bottom flush with the board's underside
        body += tab_solid(x, 0.0, -1).translate((0, 0, 0))
        # female notch on the +y edge, mirroring it
        body -= Manifold.cube((TAB_W_TIP, NOTCH_D + 0.01, TAB_H)).translate(
            (x - TAB_W_TIP / 2, BOARD_W - NOTCH_D, 0))
    return to_trimesh(body)


def rails():
    """Two deck rails at the settled gap: pockets on the tab side, pegs on the
    notch side, at the same three stations."""
    run = BOARD_L + 40.0
    x0 = -20.0
    # pocket rail sits just outboard of the board's -y face
    pocket = Manifold.cube((run, RAIL_W, RAIL_H)).translate((x0, -RAIL_W, 0))
    for x in STATIONS:
        pocket -= Manifold.cube((TAB_W_TIP + FIT, TAB_PROUD + FIT + 0.5, TAB_H + 6.0)).translate(
            (x - (TAB_W_TIP + FIT) / 2, -(TAB_PROUD + FIT), FLOOR))
    peg = Manifold.cube((run, RAIL_W, RAIL_H)).translate((x0, BOARD_W + (RAIL_GAP - BOARD_W), 0))
    y_inner = BOARD_W + (RAIL_GAP - BOARD_W)
    for x in STATIONS:
        peg += Manifold.cube((PEG_W, PEG_D, TAB_H - FIT)).translate(
            (x - PEG_W / 2, y_inner - PEG_D, FLOOR))
    # the shelf the board's bare rim lands on, relieved so it never sits on tape
    for r in (pocket, peg):
        pass
    return to_trimesh(pocket), to_trimesh(peg)


def crop(mesh, x_lo, x_hi):
    """Keep the slab between two planes, capped. Cropping the geometry beats
    zooming the camera: a close crop of a 165 mm board otherwise fills the
    frame with contact holes and the joint itself is nowhere to be seen."""
    man = to_manifold(mesh).trim_by_plane((1.0, 0.0, 0.0), float(x_lo))
    man = man.trim_by_plane((-1.0, 0.0, 0.0), float(-x_hi))
    return to_trimesh(man)


def build(name, lift, view, zoom, section=None, window=None, ywindow=None):
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    pocket_rail, peg_rail = rails()
    objs = [("rail_pocket", pocket_rail, PLA), ("rail_peg", peg_rail, PLA)]

    board = board_with_cleats()
    board.apply_translation((0, 0, FLOOR + lift))
    objs.append(("board", board, BOARD))
    # the printed detail rides along, shifted the same way
    ref = trimesh.load(os.path.join(SRC, "prop_bb_body.stl"), process=True).bounds[0]
    for part, look in (("holes", HOLE), ("red", RED), ("blue", BLUE)):
        m = trimesh.load(os.path.join(SRC, f"prop_bb_{part}.stl"), process=True)
        m.apply_translation((-ref[0], -ref[1], -ref[2] + FLOOR + lift))
        if len(m.faces):
            objs.append((f"board_{part}", m, look))

    if window is not None:
        keep = []
        for label, mesh, look in objs:
            tm = crop(mesh, window[0], window[1])
            if len(tm.faces):
                keep.append((label, tm, look))
        objs = keep
    if ywindow is not None:
        # Crop across the board too. A full cross-section is 55 mm wide and the
        # engagement is 4 mm of it, so without this the joint is 7% of the
        # frame and the picture answers nothing.
        keep = []
        for label, mesh, look in objs:
            man = to_manifold(mesh).trim_by_plane((0.0, 1.0, 0.0), float(ywindow[0]))
            man = man.trim_by_plane((0.0, -1.0, 0.0), float(-ywindow[1]))
            tm = to_trimesh(man)
            if len(tm.faces):
                keep.append((label, tm, look))
        objs = keep
    if section is not None:
        # A CROSS-section, across the board's length at the station. Cutting
        # ALONG the length instead throws one rail away entirely and shows
        # nothing of the joint -- which is exactly what the first attempt did.
        keep = []
        for label, mesh, look in objs:
            tm = to_trimesh(to_manifold(mesh).trim_by_plane((-1.0, 0.0, 0.0), -section))
            if len(tm.faces):
                keep.append((label, tm, look))
        objs = keep

    scene = dict(out=f"renders/story/{name}.png", view=view, zoom=zoom, frame=None, objects=[])
    for label, mesh, look in objs:
        mesh.export(os.path.join(dest, label + ".stl"))
        scene["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(scene, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print(f"scene {name} -> {len(objs)} objects"
          + (f", sectioned at x = {section:.1f}" if section is not None else ""))


if __name__ == "__main__":
    print(f"  dimensions from: {DIM_SRC}")
    print(f"  {N_STATIONS} stations at {', '.join(f'{x:.2f}' for x in STATIONS)} along a {BOARD_L} board")
    mid = STATIONS[1]
    # the whole board, lifted, so the three stations line up with their rails
    build("cleat_drop", lift=15.0, view=[-0.55, -1.0, 0.80], zoom=1.0)
    # one station, close: the tab standing over its open pocket and the notch
    # over its peg, which is the whole mechanism in one picture
    build("cleat_station", lift=11.0, view=[-0.45, -1.0, 0.55], zoom=1.0,
          window=(mid - 24.0, mid + 24.0))
    # the same station seated and cut lengthwise down the board's centre, so
    # both engagements are visible at once instead of hidden inside the joint
    # cut across the station and look down the board's axis: pocket and tab on
    # one side, peg in its notch on the other, both in one picture
    build("cleat_section", lift=0.0, view=[1.0, -0.22, 0.30], zoom=1.0,
          window=(mid - 20.0, mid + 20.0), section=mid)
    # the two engagements, each cropped so it fills the frame
    # Lifted, not sectioned. A cut through the station centre leaves the tab
    # flush with the cut face, where it reads as part of the board's outline
    # and not as a feature at all. Lifting it 7 mm shows the tab hanging under
    # the board directly above the pocket it drops into.
    # steep, because the pocket is cut into the rail's INNER face: from a low
    # angle outside the rail its own 4.3 mm of wall hides the whole feature
    build("cleat_pocket", lift=13.0, view=[0.30, -0.55, 2.10], zoom=1.0,
          window=(mid - 13.0, mid + 13.0), ywindow=(-RAIL_W - 1.0, 12.0))
    build("cleat_peg", lift=13.0, view=[0.30, 0.55, 2.10], zoom=1.0,
          window=(mid - 13.0, mid + 13.0), ywindow=(BOARD_W - 12.0, RAIL_GAP + RAIL_W + 1.0))
