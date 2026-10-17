"""Pieces and choreography for the screen-holder showcase film (2026-10-17).

    python cad/showcase_scene.py      ->  out/showcase/*.stl + scene.json
    blender -b -P cad/render.py -- --src=frame --anim=showcase --real --fhd --png

User: "a 30 second render of the screen attaching with your idea for the mic
board next to it and then a bunch of the sensors etc. that would run on the
breadboard / wires."

Three acts, all in assembly millimetres so they sit on the real meshes in
out/frame:

  1. The backplate and the CrowPanel go onto the posts with their real
     screws (4 x M3 x 8 into the posts' nuts, 4 x M3 x 12 into the bosses),
     at the counterbore and PCB-face heights bench.py cuts them to.
  2. The mic-array CROWN -- a CONCEPT, not in bench.py and not printed: a
     tongue behind the backplate's top rim (2 screws from behind), a
     gooseneck over the top, and a ring that holds a reSpeaker XVF3800 flat
     above the screen, logo face (the mics' sound ports) up. The board is
     Seeed's own STEP; its four holes are on a 66 x 66 square.
  3. A plausible project on the breadboards -- an ESP32 board, OLED, BME280,
     buttons, LEDs with resistors, a pot, and on the half board an HC-SR04,
     a PIR and a buzzer -- every pin in a real hole of the props' grid, and
     jumper wires grown hole to hole.

Screws are written in their OWN frame (head below z = 0, shank up +z, as
frame.m3_screw draws them) with a world matrix, so the film can drive each
one along its axis and spin it about its own centreline. Everything else is
written in world coordinates and only translates.
"""
import json
import math
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frame as F  # noqa: E402
import params as P  # noqa: E402
from build123d import export_stl, import_step  # noqa: E402

OUT = os.path.join(HERE, "..", "out", "showcase")
STEP_MIC = os.path.join(HERE, "..", "ref", "respeaker_xvf3800",
                        "respeaker_mic_array_xvf3800_1_with-xiao-0820.stp")

# ---------------------------------------------------------------- frames ----
# The display module's frame: x along the rail, y up the post, z out of its
# face (n). to_post() = Pos(x, post_point(s)) * Rot(FR_ROT_X, 0, 0).
S_DISP = F.FR_RAIL_S + P.DM_POST_DEMO_CY
_y0, _z0 = F.post_point(S_DISP)
_a = math.radians(F.FR_ROT_X)
R_DISP = np.array([[1, 0, 0], [0, math.cos(_a), -math.sin(_a)],
                   [0, math.sin(_a), math.cos(_a)]])
T_DISP = np.array([P.MOD_X_DISPLAY, _y0, _z0])
N = R_DISP @ [0, 0, 1]          # out of the panel: toward you and up
U = R_DISP @ [0, 1, 0]          # up the post


def disp(x, y, z):
    """Display-module local -> world."""
    return T_DISP + R_DISP @ np.array([x, y, z], float)


def m4(R, t):
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = R, t
    return M


def axis_frame(z_axis):
    """Rotation whose z is `z_axis` and whose x is world X (all our screw
    axes lie in the YZ plane)."""
    z = np.asarray(z_axis, float) / np.linalg.norm(z_axis)
    x = np.array([1.0, 0, 0])
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


# --------------------------------------------------------------- outputs ----
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".stl"):
        os.remove(os.path.join(OUT, f))
scene = dict(objects=[], groups={}, screws=[], wires=[], glow=[], camera=[],
             captions=[], turns=[], seconds=30.0)


def put(name, mesh, mat, group):
    mesh.export(os.path.join(OUT, name + ".stl"))
    scene["objects"].append(dict(name=name, mat=mat, group=group))


def group(name, t0, dur, frm, hidden=True):
    scene["groups"][name] = dict(t0=t0, dur=dur, frm=[round(float(v), 2) for v in frm],
                                 hidden=hidden)


def box(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)))
    b.apply_translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    return b


def cyl(r, h, x=0.0, y=0.0, z=0.0, axis="z", sections=32):
    c = trimesh.creation.cylinder(radius=r, height=h, sections=sections)
    if axis == "y":
        c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
    elif axis == "x":
        c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
    c.apply_translation((x, y, z))
    return c


def cat(*ms):
    return trimesh.util.concatenate([m for m in ms if m is not None])


# ---------------------------------------------------------------- screws ----
_screw_cache = {}


def screw_mesh(length):
    if length not in _screw_cache:
        path = os.path.join(OUT, f"_m3x{length:g}.stl")
        export_stl(F.m3_screw(length=length, head="cap"), path, tolerance=0.02)
        _screw_cache[length] = trimesh.load(path)
        os.remove(path)
    return _screw_cache[length]


def screw(name, length, origin, drive, t0, dur=1.0, travel=None):
    """`origin`: world point under the head (the bearing face), `drive`: the
    direction the shank goes in. Starts `travel` mm back along the axis and
    turns as it comes home, a thread pitch (0.5) per mm."""
    travel = travel if travel is not None else length + 6.0
    screw_mesh(length).export(os.path.join(OUT, name + ".stl"))
    M = m4(axis_frame(drive), origin)
    scene["screws"].append(dict(name=name, mat="steel_black", matrix=M.round(5).tolist(),
                                t0=t0, dur=dur, travel=travel,
                                turns=round(travel / 0.5, 1)))


# ======================================================= act 1: the screen ==
# The posts' twist locks go from open to locked first: a quarter turn
# clockwise seen from the front, about each lock's own axis (2026-10-17).
for i, x in enumerate(P.DM_POST_X):
    _py, _pz = F.post_point(F.FR_RAIL_S)
    _piv = np.array([x, _py, _pz]) + R_DISP @ np.array([0.0, P.DM_LOCK_Y, 0.0])
    scene["turns"].append(dict(names=[f"asm_lock{i}", f"asm_lockknob{i}"],
                               matrix=m4(axis_frame(N), _piv).round(5).tolist(),
                               t0=0.5, dur=1.1, deg_from=90.0, deg_to=0.0))

# Backplate: comes in along the panel normal, from in front.
group("backplate", 2.2, 1.8, N * 140)
scene["objects"].append(dict(name="asm_backplate", mat=None, group="backplate"))
# M3 x 8 at the bars' counterbores: head seated at n = 15.2 (bench.py),
# into the posts' hex nuts.
t = 4.2
for i, (sx, y) in enumerate((sx, y) for sx in (-1, 1) for y in P.DBP_POST_HOLES):
    screw(f"scr_bp{i}", 8, disp(sx * P.DBP_BAR_X, y, 15.2), -N, t + 0.35 * i, dur=1.1)

# The screen: in along the normal; then 4 x M3 x 16 from the front through
# its corner slots, heads on the PCB's front face, into the nuts pressed into
# the bosses' backs (bolted since 2026-10-17).
group("screen", 6.6, 1.8, N * 170)
for n_ in ("prop_cp7_body", "prop_cp7_glass", "prop_cp7_ui"):
    scene["objects"].append(dict(name=n_, mat=None, group="screen"))
z_pcb = P.RAIL_TOP_Z + P.DM_POST_T + P.DBP_BAR_T + P.DBP_STANDOFF
pcb_front = z_pcb + P.CP7_PCB_T
for i, (sx, sy) in enumerate((sx, sy) for sx in (-1, 1) for sy in (-1, 1)):
    screw(f"scr_cp{i}", P.CP7_SCREW_L, disp(sx * P.CP7_HOLE_X, sy * P.CP7_HOLE_Z, pcb_front),
          -N, 8.6 + 0.35 * i, dur=1.1)

# ================================================ act 2: the mic crown ======
# Tongue behind the backplate's top rim (rim: y 46.2..52.2, back face at
# n = 12.4), 24 wide, 4 thick; two screws from behind into the rim.
RIM_BACK = P.RAIL_TOP_Z + P.DM_POST_T                 # 12.4
TONGUE = (-12.0, 12.0, 40.0, 60.0, RIM_BACK - 4.0, RIM_BACK)
tongue_local = box(*TONGUE)
tongue = tongue_local.copy()
tongue.apply_transform(m4(R_DISP, T_DISP))

# The ring the board sits on: world-horizontal, centred over the screen's
# top edge, 7 mm clear above the glass.
glass_top = 153.3
MIC_C = np.array([P.MOD_X_DISPLAY, 165.0, glass_top + 9.0])     # ring top
ring = trimesh.creation.annulus(r_min=40.0, r_max=53.0, height=3.0, sections=96)
ring.apply_translation(MIC_C + [0, 0, -1.5])
STANDOFF_H = 8.0          # the XIAO hangs 6.7 under the PCB, over the ring
posts = [cyl(3.0, STANDOFF_H, MIC_C[0] + sx * 33.0, MIC_C[1] + sy * 33.0,
             MIC_C[2] + STANDOFF_H / 2) for sx in (-1, 1) for sy in (-1, 1)]
# Four little tabs from the ring in to each standoff (they sit at r 46.7,
# the ring's band is 40..53, so they already land on it).
# Gooseneck: the hull of the tongue's top edge and the ring's back edge.
tongue_top = box(-12.0, 12.0, 56.0, 60.0, RIM_BACK - 4.0, RIM_BACK)
tongue_top.apply_transform(m4(R_DISP, T_DISP))
ring_back = box(MIC_C[0] - 12.0, MIC_C[0] + 12.0, MIC_C[1] + 38.0, MIC_C[1] + 50.0,
                MIC_C[2] - 3.0, MIC_C[2])
neck = trimesh.convex.convex_hull(np.vstack([tongue_top.vertices, ring_back.vertices]))
crown = trimesh.boolean.union([tongue, neck, ring] + posts, engine="manifold")
put("mic_crown", crown, "bone", "crown")
# Comes down from above and behind, the way you would lower it over the top.
group("crown", 12.6, 1.8, U * 60 - N * 40)
for i, sx in enumerate((-1, 1)):
    screw(f"scr_cr{i}", 8, disp(sx * 7.0, 49.2, RIM_BACK - 4.0), N, 14.6 + 0.4 * i, dur=1.1)

# The XVF3800, from Seeed's STEP: PCB centre (150.05, -80.26), PCB 0..1.1
# thick in z with the logo face +z. Lifted onto the standoffs, logo up.
mic_parts = []
try:
    step = import_step(STEP_MIC)
    sols = step.solids()
    pcb = max(sols, key=lambda q: q.volume)
    tmp = os.path.join(OUT, "_mic.stl")
    for key, pick in (("pcb", [pcb]), ("parts", [q for q in sols if q is not pcb])):
        from build123d import Compound
        export_stl(Compound(pick), tmp, tolerance=0.05, angular_tolerance=0.3)
        m = trimesh.load(tmp)
        os.remove(tmp)
        m.apply_translation(-np.array([150.05, -80.26, 0.0]))
        m.apply_translation(MIC_C + [0, 0, STANDOFF_H])
        mic_parts.append((key, m))
except Exception as e:                     # no STEP: a plain disc stands in
    print("XVF3800 STEP not read, using a disc:", e)
    d = cyl(50.0, 1.2, *(MIC_C + [0, 0, STANDOFF_H + 0.6]), sections=96)
    mic_parts.append(("pcb", d))
for key, m in mic_parts:
    if len(m.faces) > 60000:
        from viewer_data import lighten
        m = lighten(m)
    put(f"mic_{key}", m, "mic_pcb" if key == "pcb" else "pin", "mic")
group("mic", 16.0, 1.6, (0, 0, 70))

# ================================================= act 3: the breadboards ===
CY = (F.FRONT_AXIS + F.REAR_AXIS) / 2
TOP = F.BOARD_Z + 9.4                               # hole mouths
BOARDS = {
    "full": dict(cx=F.FRAME_T + F.FULL_X0 + F.FULL_L / 2, cy=CY, cols=63),
    "half": dict(cx=190.0 + P.HB_W / 2, cy=CY - F.HALF_RIB / 2, cols=30),
}
ROWS = {r: s * y for r, s, y in zip("abcdefghij", [-1] * 5 + [1] * 5,
                                     (13.97, 11.43, 8.89, 6.35, 3.81,
                                      3.81, 6.35, 8.89, 11.43, 13.97))}
# Power rails: the inner back rail is +3V3 (beside the red stripe), the
# outer back rail GND.
ROWS.update({"+": 20.6, "-": 23.1, "f+": -20.6, "f-": -23.1})


def hole(board, col, row):
    b = BOARDS[board]
    x = b["cx"] + (-(b["cols"] - 1) / 2 + col) * 2.54
    return np.array([x, b["cy"] + ROWS[row], TOP])


def pins(board, cols, row, length=8.5):
    """Header pins standing in holes, 0.64 square, 2.5 above the board."""
    return cat(*[_pin(hole(board, c, row), length) for c in cols])


def _pin(p, length):
    return box(p[0] - 0.32, p[0] + 0.32, p[1] - 0.32, p[1] + 0.32, TOP - 3.0, TOP + length - 3.0)


def header(board, cols, row, h=2.5):
    a, b = hole(board, cols[0], row), hole(board, cols[-1], row)
    return box(a[0] - 1.27, b[0] + 1.27, a[1] - 1.27, a[1] + 1.27, TOP, TOP + h)


T3 = 18.8          # when the boards act starts
order = []         # (group, t0) as the parts arrive


def arrive(gname, t0, dur=0.6, drop=55.0):
    group(gname, t0, dur, (0, 0, drop))
    order.append((gname, t0))


# --- ESP32 dev board, full board cols 2..21, pins in rows c and h -----------
cols = list(range(2, 22))
c0, c1 = hole("full", 2, "c"), hole("full", 21, "h")
xc, yc = (c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2
put("esp_pins", cat(pins("full", cols, "c"), pins("full", cols, "h"),
                    header("full", cols, "c"), header("full", cols, "h")), "pin", "esp")
pcb_z = TOP + 2.5
put("esp_pcb", box(xc - 25.6, xc + 25.6, yc - 10.6, yc + 10.6, pcb_z, pcb_z + 1.6), "pcb_black", "esp")
put("esp_can", cat(box(xc + 4.0, xc + 22.0, yc - 8.0, yc + 8.0, pcb_z + 1.6, pcb_z + 4.4),
                   box(xc - 27.0, xc - 19.5, yc - 4.5, yc + 4.5, pcb_z + 1.6, pcb_z + 4.8)), "silver", "esp")
put("esp_led", box(xc - 12.0, xc - 10.4, yc + 6.0, yc + 6.8, pcb_z + 1.6, pcb_z + 2.2), "led_red", "esp")
put("esp_btn", cat(box(xc - 17.0, xc - 13.5, yc - 8.0, yc - 4.5, pcb_z + 1.6, pcb_z + 3.2),
                   box(xc - 17.0, xc - 13.5, yc + 4.5, yc + 8.0, pcb_z + 1.6, pcb_z + 3.2)), "button", "esp")
arrive("esp", T3 + 0.0)
ESP = lambda c, row: hole("full", c, row)          # noqa: E731


# Layout, full board (cols 0..62; the prop's rails only run cols 2..51):
#   ESP 2..21 rows c/h | OLED 26..29 e | BME 35..38 c | buttons 41, 46
#   across the channel | 3 mm LEDs 44, 46, 49 row h, resistors to GND col +1 |
#   pot 53..55 row b. Half board (rails cols 1..28): SR04 5..8 row h,
#   buzzer 18/21 row i, PIR 22..24 row f with its dome over the channel.
# Wires leave the strip on the side away from the part they feed, so none
# of them is drawn through a PCB or a dome.

# --- upright modules: a PCB standing on a 4-pin header, facing you -------
def upright(name, board, cols, row, w, h, colour, gname, face=None):
    a, b = hole(board, cols[0], row), hole(board, cols[-1], row)
    xm, y = (a[0] + b[0]) / 2, a[1]
    pcb = box(xm - w / 2, xm + w / 2, y - 2.4, y - 0.8, TOP + 2.0, TOP + 2.0 + h)
    parts = [(f"{name}_pcb", pcb, colour), (f"{name}_pins", cat(pins(board, cols, row, 6.0),
                                                              header(board, cols, row)), "pin")]
    if face:
        parts += face(xm, y - 2.4, TOP + 2.0, w, h)
    for n_, m, mat in parts:
        put(n_, m, mat, gname)


def oled_face(xm, yf, z0, w, h):
    glass = box(xm - 12.5, xm + 12.5, yf - 1.2, yf, z0 + 4.5, z0 + 23.0)
    # what it shows: a header bar and three readings
    lines = cat(box(xm - 11.0, xm + 11.0, yf - 1.35, yf - 1.2, z0 + 19.5, z0 + 21.5),
                *[box(xm - 11.0, xm - 11.0 + L, yf - 1.35, yf - 1.2, z0 + zz, z0 + zz + 1.6)
                  for L, zz in ((16.0, 14.5), (12.0, 11.0), (18.0, 7.5))])
    return [("oled_glass", glass, "ink"), ("oled_text", lines, "oled_glow")]


upright("oled", "full", [26, 27, 28, 29], "e", 27.3, 27.8, "pcb_blue", "oled", oled_face)
arrive("oled", T3 + 0.5)


def bme_face(xm, yf, z0, w, h):
    return [("bme_chip", box(xm - 1.3, xm + 1.3, yf - 0.9, yf, z0 + 4.5, z0 + 7.1), "silver")]


upright("bme", "full", [35, 36, 37, 38], "c", 13.0, 10.5, "pcb_purple", "bme", bme_face)
arrive("bme", T3 + 0.95)

# --- two tactile buttons across the channel --------------------------------
for i, (c, cap) in enumerate(((41, "cap_red"), (46, "cap_blue"))):
    a, b = hole("full", c, "e"), hole("full", c + 2, "f")
    xm, ym = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    put(f"btn{i}_body", cat(box(xm - 3.0, xm + 3.0, ym - 3.0, ym + 3.0, TOP, TOP + 3.5),
                            _pin(a, 4), _pin(b, 4)), "button", f"btn{i}")
    put(f"btn{i}_cap", cyl(1.75, 1.6, xm, ym, TOP + 4.3), cap, f"btn{i}")
    arrive(f"btn{i}", T3 + 1.4 + 0.35 * i)

# --- three LEDs and their resistors to GND ---------------------------------
LEDS = ((44, "led_red"), (46, "led_green"), (49, "led_blue"))
for i, (c, mat) in enumerate(LEDS):
    a, b = hole("full", c, "h"), hole("full", c + 1, "h")
    xm, y = (a[0] + b[0]) / 2, a[1]
    # 3 mm LEDs: two columns apart, a 5 mm one's 5.8 flange would collide
    body = cat(cyl(1.5, 4.0, xm, y, TOP + 5.5), cyl(1.8, 0.8, xm, y, TOP + 3.9))
    dome = trimesh.creation.icosphere(subdivisions=2, radius=1.5)
    dome.apply_translation((xm, y, TOP + 7.5))
    legs = cat(_pin(a, 6.0), _pin(b, 6.0))
    put(f"led{i}_lens", cat(body, dome), mat, f"led{i}")
    put(f"led{i}_legs", legs, "silver", f"led{i}")
    # resistor: from the LED's cathode column, row i, back to the GND rail
    p0, p1 = hole("full", c + 1, "i"), hole("full", c + 1, "-")
    leads = cat(_pin(p0, 5.0), _pin(p1, 5.0),
                box(p0[0] - 0.3, p0[0] + 0.3, p0[1], p1[1], TOP + 1.7, TOP + 2.3))
    res = cyl(1.15, 5.6, p0[0], (p0[1] + p1[1]) / 2, TOP + 2.0, axis="y")
    bands = cat(*[cyl(1.2, 0.5, p0[0], (p0[1] + p1[1]) / 2 + d, TOP + 2.0, axis="y")
                  for d in (-1.8, -0.9, 0.0, 1.8)])
    put(f"res{i}_body", res, "resistor", f"led{i}")
    put(f"res{i}_bands", bands, "band", f"led{i}")
    put(f"res{i}_leads", leads, "silver", f"led{i}")
    arrive(f"led{i}", T3 + 2.1 + 0.3 * i)

# --- a rotary pot, three pins in row b -------------------------------------
a, b = hole("full", 53, "b"), hole("full", 55, "b")
xm, y = (a[0] + b[0]) / 2, a[1] - 3.0
put("pot_body", cat(box(xm - 4.9, xm + 4.9, y - 5.0, y + 5.0, TOP, TOP + 6.5),
                    pins("full", [53, 54, 55], "b", 5.0)), "pcb_blue", "pot")
put("pot_knob", cat(cyl(3.0, 4.0, xm, y, TOP + 8.5),
                    cyl(6.0, 7.0, xm, y, TOP + 12.0, sections=24)), "button", "pot")
put("pot_mark", box(xm - 0.4, xm + 0.4, y - 5.2, y - 2.0, TOP + 15.4, TOP + 15.6), "band_white", "pot")
arrive("pot", T3 + 3.1)


# --- half board: HC-SR04, PIR, buzzer ----------------------------------------
def sr04_face(xm, yf, z0, w, h):
    eyes = cat(*[cyl(8.0, 12.0, xm + sx * 13.0, yf - 6.0, z0 + h / 2, axis="y") for sx in (-1, 1)])
    mesh = cat(*[cyl(6.6, 0.4, xm + sx * 13.0, yf - 12.05, z0 + h / 2, axis="y") for sx in (-1, 1)])
    xtal = box(xm - 5.0, xm + 5.0, yf - 3.5, yf, z0 + h - 6.0, z0 + h - 2.0)
    return [("sr04_eyes", eyes, "silver"), ("sr04_mesh", mesh, "ink"), ("sr04_xtal", xtal, "silver")]


upright("sr04", "half", [5, 6, 7, 8], "h", 45.0, 20.0, "pcb_blue", "sr04", sr04_face)
arrive("sr04", T3 + 3.7)


def pir_face(xm, yf, z0, w, h):
    dome = trimesh.creation.icosphere(subdivisions=3, radius=11.5)
    dome.vertices[:, 1] = np.minimum(dome.vertices[:, 1], 0.0)
    dome.apply_translation((xm, yf - 1.5, z0 + h / 2))
    collar = box(xm - 12.0, xm + 12.0, yf - 1.5, yf, z0 + h / 2 - 12.0, z0 + h / 2 + 12.0)
    return [("pir_dome", dome, "dome"), ("pir_collar", collar, "dome")]


upright("pir", "half", [22, 23, 24], "f", 32.0, 24.0, "pcb_green", "pir", pir_face)
arrive("pir", T3 + 4.2)

a, b = hole("half", 18, "i"), hole("half", 21, "i")
xm, y = (a[0] + b[0]) / 2, a[1]
put("buzz_body", cat(cyl(6.0, 9.5, xm, y, TOP + 4.75), _pin(a, 4.0), _pin(b, 4.0)), "button", "buzz")
put("buzz_dot", cyl(1.0, 0.2, xm, y, TOP + 9.55), "band_white", "buzz")
arrive("buzz", T3 + 4.6)


# ------------------------------------------------------------------ wires ----
def wire(name, colour, p, q, t0, lift=None):
    p, q = np.asarray(p, float), np.asarray(q, float)
    d = np.linalg.norm(q[:2] - p[:2])
    lift = lift if lift is not None else float(np.clip(0.22 * d, 7.0, 34.0))
    up = np.array([0, 0, 1.0])
    mid = (p + q) / 2 + up * lift
    pts = [p - up * 2.0, p + up * 3.0, mid, q + up * 3.0, q - up * 2.0]
    scene["wires"].append(dict(name=name, colour=colour, t0=round(t0, 2), dur=0.55,
                               pts=[[round(float(v), 2) for v in pt] for pt in pts]))


W = T3 + 4.4                                           # wiring starts
k = 0
STAGGER = 0.09


def W_(colour, p, q, lift=None):
    global k
    wire(f"w_{colour}.{k:02d}", colour, p, q, W + STAGGER * k, lift)
    k += 1


# power: ESP 3V3 and GND to the back rails, and the full board's rails over
# to the half board's
W_("red", ESP(3, "j"), hole("full", 3, "+"))
W_("black", ESP(4, "j"), hole("full", 4, "-"))
W_("red", hole("full", 30, "+"), hole("half", 1, "+"), 34)
W_("black", hole("full", 31, "-"), hole("half", 2, "-"), 36)
# OLED (row e) and BME280 (row c) share I2C: power from the FRONT rails so
# no wire crosses a standing PCB; SCL/SDA run along the front to the ESP.
for base, scl, sda in ((26, 8, 9), (35, 10, 11)):
    W_("black", hole("full", base, "a"), hole("full", base, "f-"), 7)
    W_("red", hole("full", base + 1, "a"), hole("full", base + 1, "f+"), 7)
    W_("yellow", hole("full", base + 2, "a"), ESP(scl, "a"))
    W_("green", hole("full", base + 3, "a"), ESP(sda, "a"))
# the front rails fed from the back ones
W_("red", hole("full", 2, "+"), hole("full", 2, "f+"), 30)
W_("black", hole("full", 6, "-"), hole("full", 6, "f-"), 32)
# buttons: one leg to a GPIO, the other to GND
for i, c in enumerate((41, 46)):
    W_("blue", hole("full", c, "a"), ESP(12 + i, "a"))
    W_("black", hole("full", c + 2, "j"), hole("full", c + 2, "-"), 9)
# LEDs: anode to a GPIO
for i, (c, _) in enumerate(LEDS):
    W_("orange", hole("full", c, "j"), ESP(15 + i, "j"))
# pot: ends to the back rails, wiper to an ADC pin
W_("red", hole("full", 53, "d"), hole("full", 51, "+"), 12)
W_("black", hole("full", 55, "d"), hole("full", 51, "-"), 12)
W_("white", hole("full", 54, "d"), ESP(14, "a"))
# half board: SR04 (VCC TRIG ECHO GND), PIR (VCC OUT GND), buzzer
W_("red", hole("half", 5, "j"), hole("half", 5, "+"), 9)
W_("purple", hole("half", 6, "j"), ESP(19, "j"))
W_("purple", hole("half", 7, "j"), ESP(20, "j"))
W_("black", hole("half", 8, "j"), hole("half", 9, "-"), 9)
W_("red", hole("half", 22, "j"), hole("half", 22, "+"), 9)
W_("green", hole("half", 23, "j"), ESP(21, "j"))
W_("black", hole("half", 24, "j"), hole("half", 25, "-"), 9)
W_("yellow", hole("half", 18, "j"), ESP(18, "j"))
W_("black", hole("half", 21, "j"), hole("half", 21, "-"), 9)
WIRES_END = W + STAGGER * k + 0.55

# ------------------------------------------------------------------- glow ----
# Screen comes on once it is screwed down; the project wakes when wired.
scene["glow"] = [
    dict(mat="screen_ui", t=(11.4, 12.2), strength=(0.0, 1.0)),
    dict(mat="led_red", t=(WIRES_END + 0.1, WIRES_END + 0.5), strength=(0.0, 6.0)),
    dict(mat="led_green", t=(WIRES_END + 0.4, WIRES_END + 0.8), strength=(0.0, 6.0)),
    dict(mat="led_blue", t=(WIRES_END + 0.7, WIRES_END + 1.1), strength=(0.0, 6.0)),
    dict(mat="oled_glow", t=(WIRES_END + 0.2, WIRES_END + 0.6), strength=(0.0, 4.0)),
]

# ----------------------------------------------------------------- camera ----
# (t, camera, look-at, lens) in assembly mm. Wide, in on the posts, round
# behind the top for the crown, down onto the boards, back out wide.
WIDE = ((-40, -300, 260), (150, 95, 60), 34)
POSTS = ((60, -300, 245), (138, 140, 112), 30)
CROWN = ((360, 430, 290), (138, 180, 135), 34)
MIC = ((-20, -200, 330), (138, 160, 140), 30)
BOARDS_V = ((150, -140, 230), (150, 50, 12), 32)
FINAL = ((20, -300, 280), (150, 95, 80), 34)
# opening: close on post 0's foot, where the twist lock turns
LOCKV = ((-5, -95, 95), (110, 100, 40), 36)
for t, (c, l, f) in ((0.0, LOCKV), (1.8, LOCKV), (3.8, POSTS), (11.6, POSTS),
                     (13.2, CROWN), (15.8, CROWN), (17.2, MIC), (18.0, MIC),
                     (19.2, BOARDS_V), (WIRES_END + 0.3, BOARDS_V),
                     (29.0, FINAL), (30.0, FINAL)):
    scene["camera"].append(dict(t=round(t, 2), loc=c, look=l, lens=f))

scene["captions"] = [
    dict(t=0.0, text="The two display posts are on the rail; a quarter turn of each thumb knob locks its foot."),
    dict(t=2.2, text="Backplate on: 4 x M3 x 8 through its counterbores into the posts' hex nuts."),
    dict(t=6.6, text="Screen on: 4 x M3 x 16 through its corner slots into nuts pressed into the bosses."),
    dict(t=12.4, text="Mic-array crown, a CONCEPT: a tongue behind the backplate's top rim, 2 screws from behind."),
    dict(t=16.0, text="The reSpeaker XVF3800 sits flat above the screen, mics facing up."),
    dict(t=T3, text="What could live on the boards: an ESP32 board, OLED, BME280, buttons, LEDs, a pot..."),
    dict(t=T3 + 3.7, text="...and an ultrasonic sensor, a PIR and a buzzer on the half board."),
    dict(t=W, text="Jumpers, hole to hole -- every pin sits in a real hole of the breadboard grid."),
    dict(t=WIRES_END, text="Powered up."),
]
scene["seconds"] = 30.0
json.dump(scene, open(os.path.join(OUT, "scene.json"), "w"), indent=1)
print(f"{len(scene['objects'])} objects, {len(scene['screws'])} screws, "
      f"{len(scene['wires'])} wires; wiring {W:.1f}..{WIRES_END:.1f} s")
