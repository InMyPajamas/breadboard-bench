"""The deck ladder as PLAN.md's "recessed ledge" describes it, built with
manifold3d on the Mac so the hub's 3D viewer can show the proposal before the
PC re-exports the real part from frame.py.

    python cad/ledge_ladder.py          -> out/frame_ledge/   a copy of out/frame with the
                                           ladder swapped, the deck stops gone and the
                                           boards sunk RECESS into the ledges
    python cad/viewer_data.py ledge     -> out/viewer_data_ledge.json
    python cad/build_viewer.py          -> out/ledge-viewer.html  (the "Ledge" variant)

Nothing here is a source of truth. frame.py is, and this file goes the day
frame.py exports the same geometry. Skipped as invisible in a viewer: the
foot pockets, the end pilots, the bottom chamfers, the plate crowns.

Coordinates: each rail is built rail-local (axis at y=0, ledge on side s),
placed at FRONT_AXIS / REAR_AXIS, and the whole ladder then moves to
LADDER_X, where build() puts it -- asm_ladder.stl spans x 3..297 because the
arcs engage 3 mm past each end of the 288 span. The boards therefore start at
rail-local 6 and 184, which is assembly 12 and 190, today's props.
"""
import math
import os
import shutil

import numpy as np
import trimesh
from manifold3d import Manifold

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "out", "frame")
DST = os.path.join(ROOT, "out", "frame_ledge")

# frame.py, unchanged by the plan
SPAN, ENGAGE = 288.0, 3.0
RAIL_R, LEDGE, LEDGE_Z = 8.0, 4.5, 3.0
FRONT_AXIS, REAR_AXIS = 10.0, 83.4
FOOT_X = (52.0, 144.0, 236.0)
DECK_PLATE_W = 20.0
LADDER_X = 6.0
BB_D = 54.74

# the gauges and the plan
RAIL_GAP, POCKET_D, FIT = 55.14, 1.71, 0.30
TAB_W, PEG_W, PEG_D = 4.07, 3.8, 1.3
RECESS, TAPE_T, RIM = 1.2, 0.6, 0.6
BOARD_Z = LEDGE_Z - RECESS
RELIEF_Z = BOARD_Z - TAPE_T - 0.4
LAND_Y = math.sqrt(RAIL_R ** 2 - LEDGE_Z ** 2)
FACE_Y = (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2
assert abs(FACE_Y - LAND_Y - POCKET_D) < 0.02, (FACE_Y, LAND_Y, POCKET_D)
SHELF_Y1 = FACE_Y + RIM
POCKET_W, SLOT_REACH, BLOCK_L, POCKET_WELL = TAB_W + FIT, (0.0, 3.0, 4.0), 3.5, 0.4
END_STUB = 5.0


def _measured(board, **fallback):
    """The board as punched in on the hub's Boards tab, else these fallbacks.
    The full board's 165.10 was our model's number and the ruler says ~160."""
    import json
    try:
        with open(os.path.join(ROOT, "out", "board_dims.json"), encoding="utf-8") as f:
            got = (json.load(f) or {}).get(board) or {}
    except Exception:
        got = {}
    out = dict(fallback)
    out.update({k: v for k, v in got.items() if isinstance(v, (int, float))})
    return out


_f = _measured("full", L=160.0, W=BB_D, SP=65.21, N=3)
_h = _measured("half", L=81.89, W=53.94, SP=53.51, N=2)
# the full board starts 3 clear of the 5 mm stub (was today's 6): its first cleat's
# distance from the end is unmeasured, and this makes a +-2 error harmless
FULL_L, FULL_SP, FULL_N, FULL_X0 = _f["L"], _f["SP"], int(_f["N"]), 8.0
HALF_L, HALF_W, HALF_SP, HALF_N, HALF_X0 = _h["L"], _h["W"], _h["SP"], int(_h["N"]), 184.0
HALF_RIB = BB_D - HALF_W


def stations(x0, b):
    """END_TAB (left end to the first tab's centre, calipered) places the
    datum directly; without it the cleats are assumed centred on the board."""
    first = b["END_TAB"] if isinstance(b.get("END_TAB"), (int, float)) else b["L"] / 2 - (int(b["N"]) - 1) / 2 * b["SP"]
    return tuple(round(x0 + first + k * b["SP"], 2) for k in range(int(b["N"])))


FULL_ST = stations(FULL_X0, _f)      # 20.79, 86.00, 151.21 with L 160 and centred cleats
HALF_ST = stations(HALF_X0, _h)      # 198.19, 251.70


def box(x0, x1, y0, y1, z0, z1):
    lo = np.minimum((x0, y0, z0), (x1, y1, z1))
    hi = np.maximum((x0, y0, z0), (x1, y1, z1))
    return Manifold.cube(tuple(hi - lo)).translate(tuple(lo))


def half_round(length):
    """frame.py's half_round: a cylinder on a flat, engaged past both ends,
    with the cross-bores it cuts (r 2.4 at z 4, every 20, none near a foot)."""
    bar = Manifold.cylinder(length + 2 * ENGAGE, RAIL_R, RAIL_R, 96).rotate((0, 90, 0)).translate((-ENGAGE, 0, 0))
    bar -= box(-ENGAGE - 1, length + ENGAGE + 1, -RAIL_R - 1, RAIL_R + 1, -RAIL_R - 2, 0)
    hz, hr, pitch = RAIL_R * 0.5, 2.4, 20.0
    n = int((length - 2 * pitch) // pitch)
    start = (length - (n - 1) * pitch) / 2
    for i in range(n):
        x = start + i * pitch
        if any(abs(x - sx) < 10.7 for sx in FOOT_X):
            continue
        bar -= Manifold.cylinder(2 * RAIL_R + 6, hr, hr, 48).rotate((90, 0, 0)).translate((x, RAIL_R + 3, hz))
    return bar


def deck_rail(s):
    """Rail-local, ledge on side s. Every feature is ledge the cutter LEAVES."""
    rail = half_round(SPAN) + box(0, SPAN, 0, s * (RAIL_R + LEDGE), 0, LEDGE_Z)
    x0, x1 = END_STUB, SPAN - END_STUB
    hx0, hx1 = HALF_X0 - 2.0, HALF_X0 + HALF_L + 2.0
    yin = s * (RAIL_R + LEDGE + 1.0)
    zt = LEDGE_Z + 1.0
    rib = HALF_RIB if s < 0 else 0.0
    cut = box(x0, x1, s * LAND_Y, yin, BOARD_Z, zt)                    # channel + land
    cut += box(x0, hx0, s * SHELF_Y1, yin, RELIEF_Z, zt)               # tape relief
    cut += box(hx1, x1, s * SHELF_Y1, yin, RELIEF_Z, zt)
    cut += box(hx0, hx1, s * (SHELF_Y1 + rib), yin, RELIEF_Z, zt)
    if s > 0:                                                          # front: flanking blocks
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                for d in (-1, 1):
                    cut -= box(sx + d * half, sx + d * (half + BLOCK_L), 0, s * FACE_Y, BOARD_Z - 1, LEDGE_Z + 2)
    else:                                                              # rear: shoulder, rib, datum pegs
        cut -= box(x0, x1, 0, s * FACE_Y, BOARD_Z - 1, LEDGE_Z + 2)
        cut -= box(hx0, hx1, 0, s * (FACE_Y + HALF_RIB), BOARD_Z - 1, LEDGE_Z + 2)
        for sx, face in ((FULL_ST[0], FACE_Y), (HALF_ST[0], FACE_Y + HALF_RIB)):
            cut -= box(sx - PEG_W / 2, sx + PEG_W / 2, 0, s * (face + PEG_D), BOARD_Z - 1, LEDGE_Z + 2)
    rail -= cut
    if s > 0:                                                          # pocket wells
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                rail -= box(sx - half + 0.05, sx + half - 0.05, s * LAND_Y, s * SHELF_Y1,
                            BOARD_Z - POCKET_WELL, BOARD_Z + 0.1)
    return rail


def ladder():
    lad = deck_rail(+1).translate((0, FRONT_AXIS, 0)) + deck_rail(-1).translate((0, REAR_AXIS, 0))
    y0 = FRONT_AXIS + RAIL_R + LEDGE - 0.5
    y1 = REAR_AXIS - RAIL_R - LEDGE + 0.5
    for fx in FOOT_X:
        lad += box(fx - DECK_PLATE_W / 2, fx + DECK_PLATE_W / 2, y0, y1, 0, RELIEF_Z)
    return lad.translate((LADDER_X, 0, 0))


def to_tm(man):
    m = man.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)


def main():
    os.makedirs(DST, exist_ok=True)
    lad = to_tm(ladder())
    bodies = len(lad.split(only_watertight=False))
    assert bodies == 1, f"ladder is {bodies} pieces"
    lad.export(os.path.join(DST, "asm_ladder.stl"))
    lo, hi = lad.bounds
    print(f"asm_ladder  x {lo[0]:.2f}..{hi[0]:.2f}  y {lo[1]:.2f}..{hi[1]:.2f}  z {lo[2]:.2f}..{hi[2]:.2f}"
          f"  {len(lad.faces)} faces, one body, {lad.volume / 1000:.1f} cm3")
    print(f"stations rail-local  full {FULL_ST}  half {HALF_ST}")

    copied = sunk = 0
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".stl") or fn == "asm_ladder.stl":
            continue
        name = fn[:-4]
        if name.startswith("asm_stop"):
            continue                                       # the stops are retired
        if name.startswith(("prop_bb", "prop_hb")):
            m = trimesh.load(os.path.join(SRC, fn))
            # the boards sit RECESS lower; the full board also moves with FULL_X0
            # (its prop is still 165.1 long, so it overhangs the real 160 by 5)
            dx = FULL_X0 - 6.0 if name.startswith("prop_bb") else 0.0
            m.apply_translation((dx, 0, -RECESS))
            m.export(os.path.join(DST, fn))
            sunk += 1
            continue
        shutil.copyfile(os.path.join(SRC, fn), os.path.join(DST, fn))
        copied += 1
    for fn in os.listdir(DST):                             # a stale stop from an earlier run
        if fn.startswith("asm_stop"):
            os.remove(os.path.join(DST, fn))
    print(f"{copied} parts copied, {sunk} board meshes sunk {RECESS}, stops dropped -> {os.path.relpath(DST, ROOT)}")


if __name__ == "__main__":
    main()
