"""Where to cut a plate-03 clip free, as pictures.

    python cad/clip_cut_scene.py
    blender -b -P cad/story_render.py -- --only=clip_cut_where --only=clip_cut_blade \\
                                         --only=clip_cut_section --only=clip_fixed_section

Plate 03's clips (printed 2026-10-05) came out with the latch's release tab
fused to the plate: the relief slot stopped 1 mm short of the plate's edge.
The user can free each one with a knife; these four stills show where.

The AS-PRINTED geometry comes from the bench.py that built that plate, kept
at cad/_asprinted/, so the pictures show the part in the user's hand and not
today's corrected clip. The last still is the corrected clip, same view.

Everything is drawn PLATE DOWN, jaws up: that is how the piece lies on a
table, and it puts the weld on top of the plate where a flat blade reaches it.
"""
import importlib.util
import json
import os

from build123d import *

import bench as NEW
from params import *

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
spec = importlib.util.spec_from_file_location(
    "bench_asprinted", os.path.join(HERE, "_asprinted", "bench_asprinted_2026_10_04.py"))
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

FIT, WIDTH = 0.25, 30.0
INNER = RAIL_LIP_W / 2 + FIT
OUTER = INNER + CLIP_JAW_T
X0 = -WIDTH / 2
X1 = min(X0 + 18.0, WIDTH / 2 - 1.0)
ZT = RAIL_TOP_Z                      # the plate's underside: where tab meets plate
PLATE_Y = 23.0                       # the gauge's plate half-width

PETG = (0.50, 0.54, 0.60)
TAB = (0.96, 0.52, 0.10)
WELD = (0.92, 0.06, 0.06)
STEEL = (0.78, 0.79, 0.82)
RAIL = (0.13, 0.13, 0.15)


def clip(mod):
    c = mod.box(-17.0, 17.0, -PLATE_Y, PLATE_Y, ZT, ZT + 3.0)
    c = mod.safe_fillet(c, c.edges().filter_by(Axis.Z), 3.0)
    return mod.attach_clip(c, width=WIDTH, fit=FIT)


def pieces(mod):
    """The clip split into body / release tab / weld, so each takes a colour."""
    c = clip(mod)
    tabbox = NEW.box(X1 - 6.0 - 0.02, X1 + 0.02, -(OUTER + 6.0) - 0.02, -INNER - 1.6 + 0.4,
                     ZT - 3.4 - 0.02, ZT - 0.12)
    weldbox = NEW.box(X1 - 6.0 - 0.02, X1 + 0.02, -PLATE_Y - 0.02, -OUTER - 1.0 + 0.02, ZT - 0.12, ZT + 0.12)
    weld = c & weldbox
    tab = c & tabbox
    body = c - tabbox - weldbox
    return body, tab, weld


FLIP = Rot(180, 0, 0)                # plate down, jaws up; the latch side lands on +y


def write(name, objs, view, zoom=1.0, frame=None):
    d = os.path.join(ROOT, "out", "story", name)
    os.makedirs(d, exist_ok=True)
    out = []
    for key, shape, colour, extra in objs:
        if shape is None or (hasattr(shape, "volume") and shape.volume < 1e-6):
            continue
        p = os.path.join(d, key + ".stl")
        export_stl(FLIP * shape, p, tolerance=0.01, angular_tolerance=0.1)
        out.append({"stl": os.path.relpath(p, ROOT), "colour": list(colour), **extra})
    json.dump({"out": f"renders/story/{name}.png", "view": view, "zoom": zoom, "frame": frame, "objects": out},
              open(os.path.join(d, "scene.json"), "w"), indent=1)
    print("scene", name, len(out), "objects")


def half(shape, keep_neg_x=True):
    """A thin SLICE through the middle of the tab (x = X1 - 3), 2.4 thick.

    A slice, not a half: the relief slot only spans the tab's own width, so
    with a whole half kept, un-notched plate further back shows through the
    gap under the tab and reads as a weld that is not there.
    """
    cx = X1 - 3.0
    return shape & NEW.box(cx - 2.4, cx, -60, 60, -60, 60)


def film_pieces():
    """For the film: body / latch (finger + tooth + tab, one moving piece) /
    weld, from the AS-PRINTED clip, plus the corrected clip's latch and a
    40 mm rail stub. Unflipped clip coordinates; the film flips what it needs."""
    out = {}
    for tag, mod in (("old", OLD), ("new", NEW)):
        c = clip(mod)
        latchbox = NEW.box(X0 + 4.0 + 0.02, X1 + 0.02, -(OUTER + 6.0) - 0.02, -(INNER - CLIP_TOOTH) + 0.02,
                           RAIL_TOP_Z - 4.1, ZT - 0.12)
        weldbox = NEW.box(X1 - 6.0 - 0.02, X1 + 0.02, -PLATE_Y - 0.02, -OUTER - 1.0 + 0.02, ZT - 0.12, ZT + 0.12)
        out[tag + "_latch"] = c & latchbox
        out[tag + "_weld"] = c & weldbox
        out[tag + "_body"] = c - latchbox - weldbox
    out["rail"] = NEW.din_rail(length=40.0)
    d = os.path.join(ROOT, "out", "story", "clip_film")
    os.makedirs(d, exist_ok=True)
    for k, v in out.items():
        if v.volume > 1e-6:
            export_stl(v, os.path.join(d, k + ".stl"), tolerance=0.01, angular_tolerance=0.1)
    print("film pieces:", sorted(k for k, v in out.items() if v.volume > 1e-6))


if __name__ == "__main__":
    if "--film" in os.sys.argv:
        film_pieces()
        raise SystemExit
    body, tab, weld = pieces(OLD)
    m = {"rough": 0.5}
    # In FLIPPED coordinates: y -> -y, z -> -z. Tab is at y +18.9..+26.9, plate top at z -7.4.
    tab_frame = [[X1 - 13.0, 14.0, -11.5], [X1 + 9.0, 29.0, -2.0]]

    # 1. where it is, whole clip
    write("clip_cut_where", [("body", body, PETG, m), ("tab", tab, TAB, m), ("weld", weld, WELD, m)],
          view=[0.55, 0.85, 0.62], zoom=1.0)

    # 2. the cut: a blade lying flat on the plate, pushed sideways under the tab
    blade = NEW.box(X1 - 4.5, X1 + 34.0, -(PLATE_Y + 5.5), -(PLATE_Y - 3.5), ZT - 0.02, ZT + 0.45)
    tip = NEW.box(X1 - 9.0, X1 - 4.5, -(PLATE_Y + 5.5), -(PLATE_Y - 3.5), ZT - 0.02, ZT + 0.45)
    tip = tip & (Pos(X1 - 4.5, -(PLATE_Y + 5.5), 0) * Rot(0, 0, 153) * NEW.box(0, 30, -30, 0, -20, 20))
    write("clip_cut_blade", [("body", body, PETG, m), ("tab", tab, TAB, m), ("weld", weld, WELD, m),
                             ("blade", blade + tip, STEEL, {"rough": 0.25, "metal": True})],
          view=[0.80, 0.62, 0.55], zoom=1.0, frame=[[X1 - 14.0, 12.0, -11.5], [X1 + 36.0, 30.0, -2.0]])

    # 3. cut through the tab, as printed: the weld in red
    write("clip_cut_section", [("body", half(body), PETG, m), ("tab", half(tab), TAB, m), ("weld", half(weld), WELD, m)],
          view=[1.0, 0.22, 0.16], zoom=1.0, frame=[[X1 - 4.0, 13.5, -11.0], [X1 - 2.0, 28.5, -2.5]])

    # 4. the same cut through the corrected clip: daylight under the tab
    nb, nt, nw = pieces(NEW)
    write("clip_fixed_section", [("body", half(nb), PETG, m), ("tab", half(nt), TAB, m)],
          view=[1.0, 0.22, 0.16], zoom=1.0, frame=[[X1 - 4.0, 13.5, -11.0], [X1 - 2.0, 28.5, -2.5]])
