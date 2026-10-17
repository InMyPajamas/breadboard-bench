"""The recessed-ledge retention, as a picture: nothing added, nothing above the rail.

    python cad/ledge_scene.py             -> out/story/ledge_*/ + scene.json
    blender -b -P cad/story_render.py -- --only=ledge_pocket --only=ledge_seated --only=ledge_peg

The user's constraints, verbatim: "I don't want a weird wall or something that
is higher than the half rails" and "It should ideally sit into the same area
the bar/ledge consumed." So every feature here is what REMAINS of today's
ledge after its top is cut down, and the board is recessed into that cut
rather than sat on top. The rail's crown at z=8 stays the highest thing and
the ledge's outer envelope (z 0..3, out to RAIL_R + LEDGE) is unchanged.

The numbers are frame.py's plus the gauges', and they line up without moving
either rail axis -- the reasoning is in PLAN.md, "the recessed ledge":
    rail-local, axis at y=0.  RAIL_R 8  LEDGE 4.5  LEDGE_Z 3  ->  ledge z 0..3, y 0..12.5
    D 1.5        channel depth; the rim seats on FLOOR = 1.5
    LAND_Y 7.42  the arc's y at z=3; below that the arc bulges out (7.86 at the
                 floor), so a flat face is cut there from FLOOR to 3 -- the
                 pocket's back wall, and what the tab bears on
    FACE_Y 9.13  (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2 = (73.4 - 55.14) / 2:
                 the outer face of the pocket blocks and of the rear shoulder,
                 and 9.13 - 7.42 = 1.71 = the proven POCKET_D.  Not a coincidence
                 worth relying on: frame.py asserts it.
    REST_W 0.5   the board's tape is set back only 0.6 from its edge, so the
                 floor at 1.5 is a 0.5 strip outside the face, and beyond it
    SKIRT_Z 0.6  the ledge drops to a skirt the tape (0.6 thick) never touches
    front rail   two blocks of un-cut ledge flank each tab, gap 4.37 (or a slot)
    rear rail    a 1.71-wide strip of un-cut ledge along the rail is the
                 shoulder the board's far edge bears on; a 3.8 x 1.3 island of
                 it stands into the notch at the locating station
"""
import json
import math
import os

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "out", "story")

PLA = dict(colour=[0.115, 0.120, 0.132], rough=0.62)
BOARD = dict(colour=[0.82, 0.81, 0.78], rough=0.45)

RAIL_R, LEDGE, LEDGE_Z = 8.0, 4.5, 3.0
FRONT_AXIS, REAR_AXIS, RAIL_GAP = 10.0, 83.4, 55.14
BOARD_H = 9.40
TAB_W, TAB_PROUD, TAB_H, NOTCH_D, PEG_W, PEG_D = 4.07, 1.41, 5.20, 1.60, 3.8, 1.3
FIT, POCKET_D = 0.30, 1.71
D = 1.2                                                    # RECESS in PLAN.md
FLOOR = LEDGE_Z - D                                        # BOARD_Z, the rim shelf
LAND_Y = math.sqrt(RAIL_R ** 2 - LEDGE_Z ** 2)
FACE_Y = (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2
assert abs(FACE_Y - LAND_Y - POCKET_D) < 0.02, (FACE_Y, LAND_Y, POCKET_D)
REST_W, SKIRT_Z, WELL = 0.6, 0.8, 0.4                      # RIM, RELIEF_Z, POCKET_WELL in PLAN.md
RUN = 40.0                                                 # length of rail shown


def to_tm(man):
    m = man.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)


def ledge_rail(run):
    """Today's deck_rail minus its teeth, with the channel, the land and the
    skirt cut: a half-round on the bed, the ledge out to RAIL_R + LEDGE, then
    everything outboard of LAND_Y above FLOOR removed, then everything outboard
    of the rest strip above SKIRT_Z. Axis along x at y=0."""
    cyl = Manifold.cylinder(run, RAIL_R, RAIL_R, 96).rotate((0, 90, 0))
    cyl -= Manifold.cube((run + 2, 2 * RAIL_R + 4, RAIL_R + 2)).translate((-1, -RAIL_R - 2, -RAIL_R - 2))
    rail = cyl + Manifold.cube((run, RAIL_R + LEDGE, LEDGE_Z))
    rail -= Manifold.cube((run + 2, RAIL_R + LEDGE + 2, D + 1)).translate((-1, LAND_Y, FLOOR))
    return rail - Manifold.cube((run + 2, RAIL_R + LEDGE + 2, LEDGE_Z)).translate((-1, FACE_Y + REST_W, SKIRT_Z))


def front_rail(run, station, slot=0.0):
    """Two blocks of ORIGINAL ledge left standing either side of the tab, land
    to FACE_Y; the gap between them is the pocket and the land its back wall."""
    rail = ledge_rail(run)
    gap = TAB_W + FIT + 2 * slot
    for side in (-1, +1):
        x0 = station + side * (gap / 2) + (0 if side > 0 else -3.5)
        rail += Manifold.cube((3.5, FACE_Y - LAND_Y + 0.4, D)).translate((x0, LAND_Y - 0.4, FLOOR))
    # the well: the pocket floor sits WELL below the shelf, so the rim carries, never a tab with flash
    return rail - Manifold.cube((gap - 0.1, FACE_Y + REST_W - LAND_Y, WELL + 0.01)).translate(
        (station - gap / 2 + 0.05, LAND_Y, FLOOR - WELL))


def rear_rail(run, station):
    """The shoulder: a strip of original ledge from the land to FACE_Y, the
    rail's whole length, plus a peg-shaped island of it standing into the notch."""
    rail = ledge_rail(run)
    rail += Manifold.cube((run, FACE_Y - LAND_Y + 0.4, D)).translate((0, LAND_Y - 0.4, FLOOR))
    return rail + Manifold.cube((PEG_W, PEG_D, D)).translate((station - PEG_W / 2, FACE_Y, FLOOR))


def board_piece(run, station, lift, notch=False):
    """A slab of board edge, its rim at the channel floor (+ lift). Either a
    tab standing proud of the edge, or the notch cut into it, at `station`."""
    b = Manifold.cube((run, 12.0, BOARD_H)).translate((0, FACE_Y, FLOOR + lift))
    if notch:
        return b - Manifold.cube((TAB_W, NOTCH_D + 0.01, TAB_H)).translate((station - TAB_W / 2, FACE_Y - 0.01, FLOOR + lift))
    return b + Manifold.cube((TAB_W, TAB_PROUD, TAB_H)).translate((station - TAB_W / 2, FACE_Y - TAB_PROUD, FLOOR + lift))


def scene(name, objs, view, zoom=1.0):
    dest = os.path.join(OUT, name); os.makedirs(dest, exist_ok=True)
    doc = dict(out=f"renders/story/{name}.png", view=view, zoom=zoom, frame=None, objects=[])
    for label, man, look in objs:
        tm = to_tm(man)
        assert len(tm.split(only_watertight=False)) == 1, f"{label} is {len(tm.split(only_watertight=False))} pieces"
        tm.export(os.path.join(dest, label + ".stl"))
        doc["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(doc, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print(f"scene {name} -> {len(objs)} objects")


if __name__ == "__main__":
    st = RUN / 2
    print(f"D {D}  floor z {FLOOR}  land {LAND_Y:.2f}  face {FACE_Y:.2f}  pocket {FACE_Y - LAND_Y:.2f} deep  "
          f"rest strip {REST_W}  skirt z {SKIRT_Z}")
    # Camera on the RAIL side, looking over the crown: from the board side the
    # lifted board hides the very stubs the picture exists to show.
    # front rail, board lifted: the tab about to drop between the two blocks
    scene("ledge_pocket",
          [("rail", front_rail(RUN, st), PLA), ("board", board_piece(RUN, st, lift=6.0), BOARD)],
          view=[0.6, -0.9, 0.9], zoom=1.25)
    # the same, seated, end-on: the profile shows nothing stands above the rail
    scene("ledge_seated",
          [("rail", front_rail(RUN, st), PLA), ("board", board_piece(RUN, st, lift=0.0), BOARD)],
          view=[1.0, -0.35, 0.35], zoom=1.15)
    # rear rail, board lifted: the notch about to come down over the peg on the shoulder
    scene("ledge_peg",
          [("rail", rear_rail(RUN, st), PLA), ("board", board_piece(RUN, st, lift=6.0, notch=True), BOARD)],
          view=[0.6, -0.9, 0.9], zoom=1.25)
