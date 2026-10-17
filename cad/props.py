"""Scene props for the render -- a breadboard, an ESP32 DevKit, an e-paper panel.

These are not printed parts. They exist so the render shows the bench in use,
the way the reference images do. They are placed with the same panel transform
the real modules use, so if a module moves the prop follows it.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import trimesh
from build123d import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import *  # noqa: F403,F401

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")

BB_H = 9.4          # breadboard body height
PITCH = 2.54


def _box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
        x1 - x0, y1 - y0, z1 - z0)


# --------------------------------------------------------------------------
# breadboard
# --------------------------------------------------------------------------
def breadboard_body(w=BB_W, d=BB_D, cols=63):
    """White body with the centre channel and the two power-rail grooves."""
    body = _box(-w / 2, w / 2, -d / 2, d / 2, 0, BB_H)
    body = fillet(body.edges().filter_by(Axis.Z), 1.5)
    # centre channel
    body -= _box(-w / 2 - 1, w / 2 + 1, -3.6, 3.6, BB_H - 1.6, BB_H + 1)
    # shallow grooves separating the power rails from the terminal strips
    for sign in (1, -1):
        body -= _box(-w / 2 - 1, w / 2 + 1,
                     sign * 17.4, sign * 18.4, BB_H - 0.7, BB_H + 1)
    return body


def breadboard_holes(w=BB_W, cols=63):
    """The hole grid as a mesh. Built with trimesh -- 830 OCCT pockets is slow,
    830 little boxes is instant, and at render scale they read identically."""
    xs = [(-(cols - 1) / 2 + i) * PITCH for i in range(cols)]
    ys = [s * y for s in (1, -1) for y in (3.81, 6.35, 8.89, 11.43, 13.97)]
    rail_xs = [x for x in xs if abs(x) < w / 2 - 6][:50]
    rail_ys = [s * y for s in (1, -1) for y in (20.6, 23.1)]

    boxes = []
    for ys_set, xs_set in ((ys, xs), (rail_ys, rail_xs)):
        for y in ys_set:
            for x in xs_set:
                b = trimesh.creation.box(extents=(1.5, 1.5, 1.2))
                b.apply_translation((x, y, BB_H - 0.5))
                boxes.append(b)
    return trimesh.util.concatenate(boxes)


def rail_stripes(w=BB_W):
    """The red and blue lines silk-screened along the power rails."""
    reds, blues = [], []
    for sign, bucket in ((1, reds), (-1, blues)):
        for y in (sign * 19.4, -sign * 19.4):
            s = trimesh.creation.box(extents=(w - 14, 0.9, 0.6))
            s.apply_translation((0, y, BB_H - 0.15))
            (reds if y > 0 else blues).append(s)
    return trimesh.util.concatenate(reds), trimesh.util.concatenate(blues)


# --------------------------------------------------------------------------
# boards and displays
# --------------------------------------------------------------------------
def esp32_devkit():
    """30-pin ESP32 DevKit v1: 51.5 x 28.3 PCB with a shielded module and a
    USB connector."""
    pcb = _box(-25.75, 25.75, -14.15, 14.15, 0, 1.6)
    pcb = fillet(pcb.edges().filter_by(Axis.Z), 1.0)
    shield = _box(-8.0, 8.0, -9.0, 9.0, 1.6, 4.4)
    usb = _box(-25.75 - 1.5, -20.0, -3.6, 3.6, 1.6, 4.6)
    pins = None
    for sign in (1, -1):
        row = _box(-24.0, 24.0, sign * 12.0, sign * 13.3, -3.0, 1.6)
        pins = row if pins is None else pins + row
    return {"pcb": pcb, "shield": shield + usb, "pins": pins}


def eink_panel():
    """Waveshare 2.9in e-paper: white glass face, dark flex tail, black PCB."""
    glass = _box(-EINK_WIN_W / 2 - 1.5, EINK_WIN_W / 2 + 1.5,
                 -EINK_WIN_H / 2 - 1.5, EINK_WIN_H / 2 + 1.5, 0, 1.0)
    pcb = _box(-EINK_PCB_W / 2, EINK_PCB_W / 2,
               -EINK_PCB_H / 2, EINK_PCB_H / 2, -1.4, 0)
    # a few bars so the panel reads as "showing something" rather than blank
    ink = None
    bars = [(-24, 10, 30, 2.4), (-24, 4.5, 22, 1.6), (-24, 0, 26, 1.6),
            (-24, -4.5, 14, 1.6), (6, -9.5, 24, 5.0)]
    for x, y, ln, th in bars:
        b = _box(x, x + ln, y - th / 2, y + th / 2, 1.0, 1.15)
        ink = b if ink is None else ink + b
    return {"glass": glass, "pcb": pcb, "ink": ink}


def hmi_panel():
    """Elecrow CrowPanel Advance 7in: 180 x 105 board, 155 x 87 active area.

    Local z=0 is the BACK face -- the mount's clamp plane -- so placement is
    n = the crossbar front, unlike the eink whose datum was its glass. Body
    depth 9 covers the PCB + shield stack behind the panel.
    """
    body = _box(-90.0, 90.0, -52.5, 52.5, 0, 9.0)
    body = fillet(body.edges().filter_by(Axis.Z), 2.5)
    glass = _box(-79.5, 79.5, -45.5, 45.5, 9.0, 10.2)
    # a sparse dashboard so the screen reads as ON: sidebar, two cards, text
    ui = _box(-74, -52, -40, 40, 10.2, 10.35)
    ui += _box(-44, 8, 6, 40, 10.2, 10.35)
    ui += _box(16, 74, 6, 40, 10.2, 10.35)
    for i, ln in enumerate((88, 64, 76, 40)):
        ui += _box(-44, -44 + ln, -6 - i * 9, -2 - i * 9, 10.2, 10.35)
    return {"body": body, "glass": glass, "ui": ui}


# --------------------------------------------------------------------------
# placement -- mirrors the module positions in bench.py
# --------------------------------------------------------------------------
def on_panel(shape, x_centre, s, n):
    y, z = panel_point(s, n)
    return Pos(x_centre, y, z) * Rot(PANEL_ROT_X, 0, 0) * shape


def mesh_on_panel(mesh: trimesh.Trimesh, x_centre, s, n):
    m = mesh.copy()
    ang = np.radians(PANEL_ROT_X)
    rot = trimesh.transformations.rotation_matrix(ang, (1, 0, 0))
    m.apply_transform(rot)
    y, z = panel_point(s, n)
    m.apply_translation((x_centre, y, z))
    return m


def export(shape, name):
    path = os.path.join(OUT, "assembly", f"{name}.stl")
    if isinstance(shape, trimesh.Trimesh):
        shape.export(path)
    else:
        export_stl(shape, path, tolerance=0.02, angular_tolerance=0.1)
    return path


def build_props():
    os.makedirs(os.path.join(OUT, "assembly"), exist_ok=True)

    # ---- full-size breadboard, seated in the front well ------------------
    cx = BB_WELL_X + BB_WELL_W / 2
    cy = BB_WELL_Y + BB_WELL_D / 2
    cz = BB_WELL_FLOOR
    export(Pos(cx, cy, cz) * breadboard_body(), "prop_bb_body")

    holes = breadboard_holes()
    holes.apply_translation((cx, cy, cz))
    export(holes, "prop_bb_holes")
    red, blue = rail_stripes()
    red.apply_translation((cx, cy, cz))
    blue.apply_translation((cx, cy, cz))
    export(red, "prop_bb_red")
    export(blue, "prop_bb_blue")

    # ---- half-size breadboard, in the second front well -------------------
    hx = HB_WELL_X + HB_WELL_W / 2
    export(Pos(hx, cy, cz) * breadboard_body(w=HB_W, d=HB_D, cols=30),
           "prop_hb_body")
    hb_holes = breadboard_holes(w=HB_W, cols=30)
    hb_holes.apply_translation((hx, cy, cz))
    export(hb_holes, "prop_hb_holes")
    r2, b2 = rail_stripes(w=HB_W)
    r2.apply_translation((hx, cy, cz))
    b2.apply_translation((hx, cy, cz))
    export(r2, "prop_hb_red")
    export(b2, "prop_hb_blue")

    # ---- 7in HMI panel on the display mount -------------------------------
    # PROTOTYPE SWAP: the ESP32 and e-paper props rode asm_plate/asm_screen,
    # which are off the rail while the display mount is trialled -- exporting
    # them would leave boards floating in mid-air over bare rail. Their
    # builders above are untouched; re-place them when the modules return.
    hmi = hmi_panel()
    clamp_face = RAIL_TOP_Z + 19.0           # crossbar front: 3+4+6+6
    for key, shape in hmi.items():
        export(on_panel(shape, MOD_X_DISPLAY, RAIL_S + DM_DEMO_CY,
                        clamp_face), f"prop_hmi_{key}")

    print("  props exported")


if __name__ == "__main__":
    print("building props ...")
    build_props()
    print("done.")
