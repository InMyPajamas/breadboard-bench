"""Blender render of the Breadboard Bench.

Run:
    blender -b -P cad/render.py -- [--fast] [--views hero,front,top,detail]
    blender -b -P cad/render.py -- --src=frame --anim=turn [--seconds=8]
    blender -b -P cad/render.py -- --src=frame --anim=assemble [--hq | --4k]
    blender -b -P cad/render.py -- --src=frame --anim=assemble --4k --still=2.0,6.5
    blender -b -P cad/render.py -- --src=frame --anim=assemble --4k --png [--from=120]

Imports the assembly STLs, shades them, builds a studio set, and renders --
stills by default, an H.264 MP4 with --anim (turn = studio turntable,
assemble = the build sequence flying together). Model units are millimetres;
everything is scaled to metres on import so light falloff behaves like a
real tabletop shot.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath or __file__))
if "--" in sys.argv:
    ARGS = sys.argv[sys.argv.index("--") + 1:]
else:
    ARGS = []
FAST = "--fast" in ARGS

PROJ = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))
if not os.path.isdir(os.path.join(PROJ, "out")):
    PROJ = os.getcwd()
ASM = os.path.join(PROJ, "out", "assembly")
RENDERS = os.path.join(PROJ, "renders")
os.makedirs(RENDERS, exist_ok=True)
sys.path.insert(0, os.path.join(PROJ, "cad"))

from params import (  # noqa: E402
    BENCH_W, BENCH_D, PANEL_ROT_X, RAIL_S, RAIL_TOP_Z, panel_point,
    BB_WELL_X, BB_WELL_W, BB_WELL_Y, BB_WELL_D, BB_WELL_FLOOR,
    MOD_X_PLATE, MOD_X_SCREEN,
)

MM = 0.001
CT = math.cos(math.radians(PANEL_ROT_X))
ST = math.sin(math.radians(PANEL_ROT_X))


def to_world(lx, ly, lz, xc, s, n=0.0):
    """Local module coordinates -> world millimetres on the tilted panel."""
    y0, z0 = panel_point(s, n)
    return (xc + lx, y0 + ly * CT - lz * ST, z0 + ly * ST + lz * CT)


# --------------------------------------------------------------------------
# scene reset
# --------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------
def mat(name, base, rough=0.5, metallic=0.0, spec=0.5, sheen=0.0,
        emission=None, clearcoat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]

    def put(key, val):
        if key in b.inputs:
            b.inputs[key].default_value = val

    put("Base Color", (*base, 1.0))
    put("Roughness", rough)
    put("Metallic", metallic)
    put("IOR Level", spec)
    put("Specular IOR Level", spec)
    put("Sheen Weight", sheen)
    put("Coat Weight", clearcoat)
    if emission:
        put("Emission Color", (*emission, 1.0))
        put("Emission Strength", 1.0)
    return m


BONE = mat("bone_pla", (0.585, 0.560, 0.505), rough=0.62, spec=0.4, sheen=0.15)
GRAPHITE = mat("graphite_pla", (0.030, 0.033, 0.040), rough=0.44, spec=0.5)
ACCENT = mat("accent_pla", (0.395, 0.098, 0.032), rough=0.54, spec=0.45)
# TPU reads as rubber rather than plastic: much rougher than the PLA, almost
# no specular, and a little sheen so the edges catch light the way a soft
# elastomer does. Without that the gaskets just look like dark PLA chips.
TPU = mat("tpu", (0.052, 0.058, 0.068), rough=0.80, spec=0.30, sheen=0.30)
# --real: the filament actually on the shelf (2026-09-19) instead of the
# presentation colourway -- PLA black, PETG black, TPU red. Two blacks only
# read apart by surface: PLA Basic prints satin, PETG prints glossy, so the
# PETG modules get a much tighter highlight. Black is lifted just off zero or
# the parts become holes in the picture with no form at all.
#   --petg=black|white|clear picks which PETG spool the modules are drawn in.
if "--real" in ARGS:
    _petg = ([a.split("=", 1)[1] for a in ARGS if a.startswith("--petg=")] or ["black"])[0]
    BONE = mat("black_pla", (0.026, 0.027, 0.030), rough=0.52, spec=0.5, sheen=0.10)
    TPU = mat("red_tpu", (0.520, 0.030, 0.026), rough=0.78, spec=0.30, sheen=0.30)
    if _petg == "white":
        ACCENT = mat("white_petg", (0.760, 0.765, 0.760), rough=0.24, spec=0.6)
    elif _petg == "clear":
        # Printed translucent PETG is frosted, not glass: layer lines and
        # infill scatter the light, so rough transmission, not a clean one.
        ACCENT = mat("clear_petg", (0.860, 0.890, 0.900), rough=0.38, spec=0.55)
        _b = ACCENT.node_tree.nodes["Principled BSDF"]
        for _k, _v in (("Transmission Weight", 0.82), ("IOR", 1.57)):
            if _k in _b.inputs:
                _b.inputs[_k].default_value = _v
    else:
        ACCENT = mat("black_petg", (0.018, 0.019, 0.022), rough=0.20, spec=0.65)
# Zinc-plated steel: the only material here that is actually metal.
STEEL = mat("steel", (0.420, 0.435, 0.460), rough=0.32, metallic=1.0, spec=0.5)
WHITE_BB = mat("breadboard", (0.700, 0.694, 0.672), rough=0.42, spec=0.5)
HOLE = mat("bb_hole", (0.022, 0.022, 0.026), rough=0.75)
RED = mat("bb_red", (0.58, 0.055, 0.055), rough=0.5)
BLUE = mat("bb_blue", (0.045, 0.115, 0.480), rough=0.5)
PCB = mat("pcb", (0.014, 0.019, 0.026), rough=0.52, spec=0.45)
METAL = mat("shield", (0.700, 0.715, 0.735), rough=0.28, metallic=1.0)
PIN = mat("pin", (0.075, 0.075, 0.082), rough=0.42)
EPAPER = mat("epaper", (0.880, 0.872, 0.848), rough=0.55, spec=0.35)
INK = mat("ink", (0.022, 0.022, 0.025), rough=0.8)
FLOOR = mat("floor", (0.115, 0.116, 0.122), rough=0.55, spec=0.3)

def two_tone(m, z_mm, lower_rgb):
    """Recolour a material below a height, to preview an AMS filament change.

    Costs nothing in the model -- a colour change at a layer height is a slicer
    setting. Object texture coordinates are in the mesh's own units, which here
    are millimetres, so `z_mm` is the layer height you would set.
    """
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = z_mm
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    upper = bsdf.inputs["Base Color"].default_value[:3]
    mix.inputs[6].default_value = (*lower_rgb, 1.0)
    mix.inputs[7].default_value = (*upper, 1.0)
    nt.links.new(tex.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], gt.inputs[0])
    nt.links.new(gt.outputs[0], mix.inputs[0])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return m


_tt = [a.split("=", 1)[1] for a in ARGS if a.startswith("--twotone=")]
if _tt:
    two_tone(BONE, float(_tt[0]), (0.055, 0.058, 0.066))
    print(f"two-tone preview: filament change at Z = {_tt[0]} mm")

MATMAP = {
    "asm_base": BONE,
    "asm_tray": BONE,
    "asm_ladder": BONE,
    "asm_pad0": TPU,
    "asm_pad1": TPU,
    "asm_pad2": TPU,
    "asm_pad3": TPU,
    **{f"asm_foot{i}": TPU for i in range(18)},
    **{f"hw_end{i}": STEEL for i in range(6)},
    **{f"hw_rail{i}": STEEL for i in range(8)},
    "asm_rail": GRAPHITE,
    "asm_screen": ACCENT,
    "asm_plate": ACCENT,
    "asm_carrier": ACCENT,
    "asm_bin": ACCENT,
    "asm_railbin": ACCENT,
    "asm_dspine": ACCENT,
    "asm_dupright0": ACCENT,
    "asm_dupright1": ACCENT,
    "asm_dcross0": ACCENT,
    "asm_dcross1": ACCENT,
    "asm_sidebin": ACCENT,
    "asm_post0": ACCENT,
    "asm_post1": ACCENT,
    "asm_lock0": ACCENT,
    "asm_lock1": ACCENT,
    "asm_lockknob0": ACCENT,
    "asm_lockknob1": ACCENT,
    "asm_sidetray": ACCENT,
    # board-retention study props
    "asm_stop0": ACCENT,
    "asm_stop1": ACCENT,
    "asm_fence": ACCENT,
    "asm_rack": BONE,
    **{f"asm_mag{i}": METAL for i in range(17)},
    **{f"asm_grip{i}": TPU for i in range(14)},
    "prop_cp7_body": PCB,
    "prop_cp7_glass": INK,
    "prop_cp7_ui": BLUE,
    "asm_backplate": BONE,
    "prop_hmi_body": PCB,
    "prop_hmi_glass": INK,
    "prop_hmi_ui": BLUE,
    "prop_esp_posts": PIN,
    "prop_bb_body": WHITE_BB,
    "prop_hb_body": WHITE_BB,
    "prop_bb_holes": HOLE,
    "prop_hb_holes": HOLE,
    "prop_bb_red": RED,
    "prop_hb_red": RED,
    "prop_bb_blue": BLUE,
    "prop_hb_blue": BLUE,
    "prop_esp_pcb": PCB,
    "prop_esp_shield": METAL,
    "prop_esp_pins": PIN,
    "prop_eink_glass": EPAPER,
    "prop_eink_pcb": PCB,
    "prop_eink_ink": INK,
}


# --------------------------------------------------------------------------
# import the model
# --------------------------------------------------------------------------
def import_stl(path):
    before = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=path)
    except AttributeError:
        bpy.ops.import_mesh.stl(filepath=path)
    new = list(set(bpy.data.objects) - before)
    return new


# Study aid: --hl=asm_tie,asm_tiepad0 recolours named parts to the accent.
# Close-ups of a joint between two BONE parts have no edge to read -- the
# whole point of a joint study is seeing which faces touch.
for _nm in [a.split("=", 1)[1] for a in ARGS if a.startswith("--hl=")]:
    for _n in _nm.split(","):
        MATMAP[_n] = ACCENT

LAYOUT = "--layout" in ARGS
_src = [a.split("=", 1)[1] for a in ARGS if a.startswith("--src=")]
SRC = (os.path.join(PROJ, "out", _src[0]) if _src
       else os.path.join(PROJ, "out", "layout") if LAYOUT else ASM)
LAYOUT_MATS = {"lay_rail": GRAPHITE, "lay_base": BONE}

# --light: take catalog.py's hull stand-ins (out/frame_light) for the vendor
# meshes. The CrowPanel STEP is 540k triangles; animated, Cycles rebuilt its
# BVH every frame at ~11 s/frame on the 5070 Ti.
LIGHT = os.path.join(PROJ, "out", "frame_light") if "--light" in ARGS else None
imported = []
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".stl"):
        continue
    stem = fn[:-4]
    if LAYOUT:
        MATMAP[stem] = LAYOUT_MATS.get(stem, ACCENT)
    src_fn = os.path.join(SRC, fn)
    if LIGHT and os.path.exists(os.path.join(LIGHT, fn)):
        src_fn = os.path.join(LIGHT, fn)
    for obj in import_stl(src_fn):
        obj.name = stem
        obj.scale = (MM, MM, MM)
        obj.data.materials.clear()
        obj.data.materials.append(MATMAP.get(stem, BONE))
        # Printed parts read better with smoothing above ~30 degrees, so that
        # filleted corners round off but the flat faceted surfaces stay crisp.
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(31))
        except Exception:
            bpy.ops.object.shade_flat()
        imported.append(obj)

bpy.ops.object.select_all(action="DESELECT")
print(f"imported {len(imported)} objects")


# --------------------------------------------------------------------------
# optional cutaway -- slice everything at a plane so the internals show
# --------------------------------------------------------------------------
CUT = "--cut" in ARGS
CUT_X = 110.0
if CUT:
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cutter = bpy.context.active_object
    cutter.name = "cutter"
    cutter.scale = (0.6, 0.6, 0.6)
    cutter.location = (CUT_X * MM + 0.3, 0.06, 0.05)
    for obj in imported:
        m = obj.modifiers.new("section", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.object = cutter
        m.solver = "EXACT"
    cutter.hide_render = True
    cutter.hide_viewport = True
    print(f"cutaway at X={CUT_X} mm")


# --------------------------------------------------------------------------
# jumper wires -- bezier curves from the breadboard up to the ESP32
# --------------------------------------------------------------------------
WIRE_COLS = {
    "w_red": (0.70, 0.10, 0.09),
    "w_black": (0.055, 0.055, 0.060),
    "w_yellow": (0.85, 0.68, 0.10),
    "w_green": (0.10, 0.52, 0.22),
    "w_blue": (0.10, 0.24, 0.68),
    "w_orange": (0.88, 0.42, 0.08),
    "w_white": (0.88, 0.88, 0.86),
}
WIRE_MATS = {k: mat(k, v, rough=0.34, spec=0.6) for k, v in WIRE_COLS.items()}

BB_TOP = BB_WELL_FLOOR + 9.4
ESP_X = MOD_X_PLATE


def esp_pin(i, side=1):
    """World point just above an ESP32 header pin."""
    return to_world(-22 + i * 3.6, side * 12.6, 2.0, ESP_X, RAIL_S,
                    RAIL_TOP_Z + 3.0 + 4.0)


def bb_hole(col, row):
    """World point just above a breadboard hole in the front well."""
    cx = BB_WELL_X + BB_WELL_W / 2
    cy = BB_WELL_Y + BB_WELL_D / 2
    return (cx + (col - 31) * 2.54, cy + row * 2.54, BB_TOP + 1.0)


def make_wire(name, p0, p1, lift=34.0, sag=0.35, radius=0.75):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius * MM
    cu.bevel_resolution = 4
    cu.resolution_u = 24
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(3)
    a, b = Vector(p0), Vector(p1)
    mid = a.lerp(b, 0.5)
    c1 = a.lerp(b, 0.28) + Vector((0, -6, lift))
    c2 = a.lerp(b, 0.72) + Vector((0, -2, lift * sag + 6))
    for bp, co in zip(sp.bezier_points, (a, c1, c2, b)):
        bp.co = Vector(co) * MM
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, cu)
    obj.data.materials.append(WIRE_MATS[name.rsplit(".", 1)[0]])
    scene.collection.objects.link(obj)
    return obj


WIRE_PLAN = [] if (LAYOUT or _src) else [
    ("w_red", (48, 7), esp_pin(1, -1), 30),
    ("w_black", (46, -7), esp_pin(3, -1), 26),
    ("w_yellow", (40, 5), esp_pin(5, -1), 34),
    ("w_green", (36, -5), esp_pin(7, -1), 30),
    ("w_blue", (30, 6), esp_pin(9, -1), 38),
    ("w_orange", (26, -6), esp_pin(11, -1), 32),
]
for i, (col_name, bb, tgt, lift) in enumerate(WIRE_PLAN):
    make_wire(f"{col_name}.{i:02d}", bb_hole(*bb), tgt, lift=lift)

# a couple of short jumpers living on the breadboard itself
if not (LAYOUT or _src):
    for i, (a, b) in enumerate((((14, 5), (20, -5)), ((8, -7), (16, 7)))):
        name = ["w_white", "w_green"][i]
        make_wire(f"{name}.s{i}", bb_hole(*a), bb_hole(*b), lift=9, sag=1.0,
                  radius=0.7)


# --------------------------------------------------------------------------
# studio set
# --------------------------------------------------------------------------
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
out = wn.nodes.new("ShaderNodeOutputWorld")
bg = wn.nodes.new("ShaderNodeBackground")
grad = wn.nodes.new("ShaderNodeTexGradient")
ramp = wn.nodes.new("ShaderNodeValToRGB")
mapn = wn.nodes.new("ShaderNodeMapping")
tex = wn.nodes.new("ShaderNodeTexCoord")
mapn.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
ramp.color_ramp.elements[0].color = (0.055, 0.058, 0.066, 1)
ramp.color_ramp.elements[1].color = (0.330, 0.340, 0.360, 1)
wn.links.new(tex.outputs["Generated"], mapn.inputs["Vector"])
wn.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
wn.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
wn.links.new(ramp.outputs["Color"], bg.inputs["Color"])
wn.links.new(bg.outputs["Background"], out.inputs["Surface"])
bg.inputs["Strength"].default_value = 0.30

bpy.ops.mesh.primitive_plane_add(size=8, location=(0.15, 0.05, 0))
floor = bpy.context.active_object
floor.name = "floor"
floor.data.materials.append(FLOOR)


def area_light(name, loc, rot, size, power, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = size
    d.energy = power
    d.color = color
    o = bpy.data.objects.new(name, d)
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(o)
    return o


# The bench is only 300 mm across, so lights sit close and stay low-powered.
# key: big soft source up and to the front-left
area_light("key", (-0.34, -0.46, 0.62), (48, 0, -34), (1.1, 0.8), 3.6)
# fill: lower, wider, cooler, from the right
area_light("fill", (0.62, -0.30, 0.28), (72, 0, 62), (1.3, 1.0), 1.8,
           color=(0.88, 0.92, 1.0))
# rim: narrow strip behind to separate the panel from the background
area_light("rim", (0.18, 0.58, 0.44), (120, 0, 180), (1.4, 0.16), 3.2,
           color=(1.0, 0.95, 0.88))
# bounce under the front lip so the breadboard well is not black
area_light("bounce", (0.15, -0.34, 0.06), (96, 0, 0), (0.9, 0.28), 0.4)
# Soft wash down into the rear bay. Kept low and broad: from behind it is the
# key light for the tray, and from the front it only deepens the existing rim,
# so the other views keep the look they already had.
area_light("bay", (0.15, 0.46, 0.40), (36, 0, 180), (1.0, 0.7), 1.6,
           color=(1.0, 0.97, 0.93))


# --------------------------------------------------------------------------
# cameras
# --------------------------------------------------------------------------
target = bpy.data.objects.new("target", None)
target.location = (0.152, 0.070, 0.040)
scene.collection.objects.link(target)

VIEWS = {
    #                 location                  focal  look-at
    "hero":   ((-0.064, -0.373, 0.178), 50, (0.150, 0.055, 0.046)),
    "front":  ((0.150, -0.491, 0.116), 55, (0.150, 0.055, 0.048)),
    "top":    ((0.137, -0.218, 0.381), 40, (0.150, 0.055, 0.022)),
    "detail": ((0.010, -0.150, 0.150), 60, (0.086, 0.096, 0.062)),
    # Behind the bench, high enough to look down into the tray cells. Every
    # other camera sits on -Y, where the post and the modules hide the whole
    # rear bay.
    "rear":   ((0.055, 0.440, 0.255), 40, (0.150, 0.110, 0.015)),
    # Right side, where the side bin lives -- every -Y camera has it on the
    # far side of the bench.
    "right":  ((0.478, -0.190, 0.150), 50, (0.295, 0.078, 0.028)),
    # Left side, mirror of "right": the base skid's face.
    "left":   ((-0.178, -0.190, 0.150), 50, (0.005, 0.078, 0.028)),
    # Close on the cradle where the 830 and 400 boards meet: board ends,
    # ledges, deck plates -- the board-retention study's view.
    "deck":   ((0.215, -0.085, 0.105), 60, (0.183, 0.046, 0.008)),
    # Animation camera: hero's angle pulled back, so a rotating model's
    # corners (336 wide with the side bin) never leave frame.
    "orbit":  ((-0.075, -0.430, 0.210), 48, (0.150, 0.072, 0.040)),
    # One buttress rising out of the tray, and the rail joint it carries.
    "bay":    ((0.052, 0.300, 0.140), 65, (0.100, 0.115, 0.025)),
    # Hard in on where the buttress tail meets the rear tie rod -- the
    # joint study's view. Behind and above, close enough to read a 0.2 gap.
    "tie":    ((0.045, 0.268, 0.098), 60, (0.100, 0.147, 0.010)),
    # --layout only: everything you print, laid out on one plane
    "parts":  ((-0.055, -0.360, 0.475), 50, (0.000, 0.030, 0.000)),
    # --cut only: looks square at the sectioned face
    "section": ((0.390, -0.105, 0.150), 45, (0.090, 0.055, 0.040)),
}


def make_camera(name, loc, focal, look_at):
    d = bpy.data.cameras.new(name)
    d.lens = focal
    o = bpy.data.objects.new(name, d)
    o.location = loc
    scene.collection.objects.link(o)
    t = bpy.data.objects.new(f"{name}_t", None)
    t.location = look_at
    scene.collection.objects.link(t)
    c = o.constraints.new("TRACK_TO")
    c.target = t
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return o


# --------------------------------------------------------------------------
# render settings
# --------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.samples = 48 if FAST else 320
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6 if FAST else 12
scene.render.resolution_x = 1280 if FAST else 2000
scene.render.resolution_y = 960 if FAST else 1500
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass

prefs = bpy.context.preferences.addons.get("cycles")
if prefs:
    cp = prefs.preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            cp.compute_device_type = backend
            cp.get_devices()
            if any(d.type == backend for d in cp.devices):
                for d in cp.devices:
                    d.use = d.type in (backend, "CPU")
                scene.cycles.device = "GPU"
                print(f"cycles: using {backend}")
                break
        except Exception:
            continue

# --------------------------------------------------------------------------
# animation -- the same scene, moving. Output: H.264 MP4 in renders/.
#
#   --anim=turn      studio turntable. The MODEL rotates under fixed lights,
#                    so the key/fill/rim rake across the surfaces; orbiting
#                    the camera instead keeps every face in constant light,
#                    which reads flat. Loop-perfect (linear 360).
#   --anim=assemble  the build sequence: each subassembly flies in along its
#                    real service direction, in assembly order, then holds.
#   --fps=30 --seconds=8 (turn only; assemble derives its own length)
#
# Animations render at the fast quality tier unless --hq: 300 frames at
# stills quality is an overnight job, not an iteration.
# --------------------------------------------------------------------------
_anim = [a.split("=", 1)[1] for a in ARGS if a.startswith("--anim=")]
ANIM = _anim[0] if _anim else None
_fps = [a.split("=", 1)[1] for a in ARGS if a.startswith("--fps=")]
FPS = int(_fps[0]) if _fps else 30
_sec = [a.split("=", 1)[1] for a in ARGS if a.startswith("--seconds=")]
SECONDS = float(_sec[0]) if _sec else 8.0
HQ = "--hq" in ARGS

# Assembly choreography lives in assembly_sequence.py, shared with
# assembly_fit_check.py so the film only ever shows moves the meshes allow.
from assembly_sequence import rule_for  # noqa: E402

# --4k     3840 x 2160, 128 samples. 16:9, where --hq and the draft are 4:3.
# --still  render these moments (seconds) as PNGs instead of the film: check
#          framing and time one frame before committing to hundreds.
# --png    write numbered PNG frames, not an MP4, so a long render that is
#          interrupted resumes with --from=<frame> instead of starting over.
UHD = "--4k" in ARGS
# --fhd    1920 x 1080 at 128 samples: the 4K framing at a quarter of the
#          pixels, for the hub's films (a 16:9 player; --hq is 4:3).
FHD = "--fhd" in ARGS
PNG_SEQ = "--png" in ARGS
_still = [a.split("=", 1)[1] for a in ARGS if a.startswith("--still=")]
STILLS = [float(t) for t in _still[0].split(",")] if _still else []
_from = [a.split("=", 1)[1] for a in ARGS if a.startswith("--from=")]
_samples = [a.split("=", 1)[1] for a in ARGS if a.startswith("--samples=")]


def _movables():
    return imported + [o for o in scene.objects if o.name.startswith("w_")]


if ANIM:
    scene.render.fps = FPS
    # keep the static scene's BVH between frames; only moving parts rebuild
    scene.render.use_persistent_data = True
    scene.cycles.samples = 128 if (HQ or UHD or FHD) else 48
    scene.render.resolution_x = 3840 if UHD else 1920 if (HQ or FHD) else 1280
    scene.render.resolution_y = 2160 if UHD else 1080 if FHD else 1440 if HQ else 960
    if _samples:
        scene.cycles.samples = int(_samples[0])
    loc, focal, look = VIEWS["orbit"]
    if UHD or FHD:
        # The orbit view was framed for 4:3. At 16:9 the same lens loses a
        # quarter of its height (the display posts leave the top of frame), so
        # widen it by the ratio of the two aspect ratios to keep the height.
        # Then come back in 11% and aim 35 mm higher: the bench plus the
        # display fills the frame instead of floating above empty floor.
        focal *= (9 / 16) / (3 / 4) * 1.11
        look = (look[0], look[1], look[2] + 0.035)
    scene.camera = make_camera("orbit", loc, focal, look)

    if ANIM == "turn":
        frames = int(FPS * SECONDS)
        pivot = bpy.data.objects.new("pivot", None)
        # Geometry is baked into the meshes (every object's location is the
        # origin), so centre on the known bench footprint rather than any
        # object-location bbox.
        pivot.location = (0.152, 0.078, 0)
        scene.collection.objects.link(pivot)
        for o in _movables():
            o.parent = pivot
            o.matrix_parent_inverse = pivot.matrix_world.inverted()
        pivot.rotation_euler = (0, 0, 0)
        pivot.keyframe_insert("rotation_euler", frame=1)
        pivot.rotation_euler = (0, 0, math.radians(360))
        pivot.keyframe_insert("rotation_euler", frame=frames + 1)
        for fc in pivot.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        scene.frame_start, scene.frame_end = 1, frames

    elif ANIM == "assemble":
        last = 0.0
        for obj in _movables():
            t0, vec, dur = rule_for(obj.name, _src[0] if _src else "")
            if obj.name.startswith("hw_end") and not _src:
                # screws back out axially, each toward its own side; the
                # bound box is in local units, which are millimetres here
                side = 1 if sum(b[0] for b in obj.bound_box) / 8 > 150 else -1
                vec = (70 * side, 0, 0)
            last = max(last, t0 + dur)
            base = obj.location.copy()
            start = base + Vector(vec) * MM
            f0 = 1 + int(t0 * FPS)
            obj.location = start
            obj.keyframe_insert("location", frame=f0)
            obj.location = base
            obj.keyframe_insert("location", frame=f0 + int(dur * FPS))
            if _src and _src[0] == "frame" and f0 > 1:
                # A build, not an exploded view: a part is not in the shot
                # until its move begins, so nothing hovers over the work.
                obj.hide_render = True
                obj.keyframe_insert("hide_render", frame=f0 - 1)
                obj.hide_render = False
                obj.keyframe_insert("hide_render", frame=f0)
        scene.frame_start = 1
        scene.frame_end = int((last + 1.5) * FPS)

    elif ANIM == "sides":
        # The two side parts going on, and what is inside them (2026-10-09):
        # the wider left tray and the right bin drop onto the frames' bar-end
        # heads, then each goes see-through in a close-up so the buried
        # magnets show, three of them lined up on the three steel heads.
        # Everything else is already built. Pair with --src=frame --real.
        from assembly_sequence import RIDES_WITH  # noqa: E402
        groups = {"asm_sidetray": (0.8, 1.8), "asm_sidebin": (2.4, 1.8)}
        xray = ACCENT.copy()
        xray.name = "petg_xray"
        bsdf = xray.node_tree.nodes["Principled BSDF"]

        def F(t):
            return 1 + int(round(t * FPS))
        for obj in _movables():
            host = obj.name if obj.name in groups else RIDES_WITH.get(obj.name)
            if host not in groups:
                continue
            if obj.name in groups:
                obj.data.materials.clear()
                obj.data.materials.append(xray)
            t0, dur = groups[host]
            base = obj.location.copy()
            obj.location = base + Vector((0, 0, 90)) * MM
            obj.keyframe_insert("location", frame=F(t0))
            obj.location = base
            obj.keyframe_insert("location", frame=F(t0 + dur))
            obj.hide_render = True
            obj.keyframe_insert("hide_render", frame=F(t0) - 1)
            obj.hide_render = False
            obj.keyframe_insert("hide_render", frame=F(t0))
        # see-through: solid -> ghost for the close-ups -> solid
        for t, a in ((6.0, 1.0), (7.0, 0.18), (12.4, 0.18), (13.2, 1.0)):
            bsdf.inputs["Alpha"].default_value = a
            bsdf.inputs["Alpha"].keyframe_insert("default_value", frame=F(t))
        # camera: wide -> left close-up -> right close-up -> wide
        cam = scene.camera
        tgt = cam.constraints["Track To"].target
        wide = (cam.location.copy(), Vector(tgt.location), cam.data.lens)
        left = (Vector((-0.205, -0.070, 0.115)), Vector((-0.012, 0.080, 0.004)), 50.0)
        right = (Vector((0.510, -0.070, 0.125)), Vector((0.318, 0.080, 0.006)), 50.0)
        for t, (cl, tl, lens) in ((4.8, wide), (6.6, left), (8.8, left),
                                  (10.6, right), (12.4, right), (14.2, wide)):
            cam.location, tgt.location, cam.data.lens = cl, tl, lens
            cam.keyframe_insert("location", frame=F(t))
            tgt.keyframe_insert("location", frame=F(t))
            cam.data.keyframe_insert("lens", frame=F(t))
        scene.frame_start, scene.frame_end = 1, F(15.2)
    elif ANIM == "showcase":
        # The screen holder going on, the mic-array crown CONCEPT on top, and
        # a project growing on the breadboards (2026-10-17). Pieces and timing
        # come from cad/showcase_scene.py (out/showcase/scene.json), in
        # assembly millimetres. Pair with --src=frame --real --fps=24.
        import json as _json
        SHOW_DIR = os.path.join(PROJ, "out", "showcase")
        sc_ = _json.load(open(os.path.join(SHOW_DIR, "scene.json")))

        def F(t):
            return 1 + int(round(t * FPS))

        def glow_mat(name, rgb, emit_rgb, rough=0.3):
            m = mat(name, rgb, rough=rough)
            b = m.node_tree.nodes["Principled BSDF"]
            b.inputs["Emission Color"].default_value = (*emit_rgb, 1.0)
            b.inputs["Emission Strength"].default_value = 0.0
            return m
        SHOW = {
            "bone": BONE, "pin": PIN, "silver": METAL, "ink": INK, "pcb_black": PCB,
            "steel_black": mat("black_oxide", (0.045, 0.046, 0.050), rough=0.34, metallic=1.0),
            "pcb_blue": mat("pcb_blue", (0.020, 0.090, 0.330), rough=0.45),
            "pcb_purple": mat("pcb_purple", (0.170, 0.040, 0.280), rough=0.45),
            "pcb_green": mat("pcb_green", (0.025, 0.170, 0.060), rough=0.45),
            "mic_pcb": mat("mic_pcb", (0.020, 0.021, 0.024), rough=0.40),
            "button": mat("button", (0.030, 0.030, 0.034), rough=0.55),
            "cap_red": mat("cap_red", (0.60, 0.04, 0.04), rough=0.4),
            "cap_blue": mat("cap_blue", (0.04, 0.10, 0.55), rough=0.4),
            "resistor": mat("resistor", (0.72, 0.58, 0.38), rough=0.5),
            "band": mat("band", (0.32, 0.10, 0.04), rough=0.5),
            "band_white": mat("band_white", (0.88, 0.88, 0.86), rough=0.5),
            "dome": mat("dome", (0.90, 0.90, 0.88), rough=0.62, sheen=0.2),
            "led_red": glow_mat("led_red", (0.55, 0.03, 0.03), (1.0, 0.08, 0.05), 0.15),
            "led_green": glow_mat("led_green", (0.04, 0.45, 0.08), (0.15, 1.0, 0.25), 0.15),
            "led_blue": glow_mat("led_blue", (0.03, 0.08, 0.60), (0.15, 0.35, 1.0), 0.15),
            "oled_glow": glow_mat("oled_glow", (0.02, 0.02, 0.025), (0.55, 0.85, 1.0)),
            "screen_ui": glow_mat("screen_ui", (0.05, 0.10, 0.20), (0.30, 0.55, 1.0)),
        }
        WIRE_MATS.setdefault("w_purple", mat("w_purple", (0.40, 0.12, 0.62), rough=0.34, spec=0.6))
        byname = {o.name: o for o in imported}
        byname["prop_cp7_ui"].data.materials.clear()
        byname["prop_cp7_ui"].data.materials.append(SHOW["screen_ui"])

        def appear(o, t0):
            if t0 <= 0:
                return
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=F(t0) - 1)
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=F(t0))

        # parts: new ones from out/showcase, existing ones (the backplate and
        # the screen) picked out of the imported assembly by name
        for rec in sc_["objects"]:
            if rec["mat"] is None:
                o = byname[rec["name"]]
            else:
                o = import_stl(os.path.join(SHOW_DIR, rec["name"] + ".stl"))[0]
                o.name = rec["name"]
                o.scale = (MM, MM, MM)
                o.data.materials.clear()
                o.data.materials.append(SHOW[rec["mat"]])
            g = sc_["groups"][rec["group"]]
            base = o.location.copy()
            o.location = base + Vector(g["frm"]) * MM
            o.keyframe_insert("location", frame=F(g["t0"]))
            o.location = base
            o.keyframe_insert("location", frame=F(g["t0"] + g["dur"]))
            if g["hidden"]:
                appear(o, g["t0"])

        # screws: each in its own frame -- drive along local +z, and turn
        from mathutils import Matrix
        for rec in sc_["screws"]:
            o = import_stl(os.path.join(SHOW_DIR, rec["name"] + ".stl"))[0]
            o.name = rec["name"]
            o.data.materials.clear()
            o.data.materials.append(SHOW[rec["mat"]])
            M = Matrix(rec["matrix"])
            M.translation = M.translation * MM
            holder = bpy.data.objects.new(rec["name"] + "_axis", None)
            scene.collection.objects.link(holder)
            holder.matrix_world = M
            o.parent = holder
            o.scale = (MM, MM, MM)
            t0, t1 = rec["t0"], rec["t0"] + rec["dur"]
            o.location = (0, 0, -rec["travel"] * MM)
            o.rotation_euler = (0, 0, 0)
            o.keyframe_insert("location", frame=F(t0))
            o.keyframe_insert("rotation_euler", frame=F(t0))
            o.location = (0, 0, 0)
            # a few visible turns, not the real 20-odd: at 24 fps those strobe
            o.rotation_euler = (0, 0, math.radians(360 * min(rec["turns"], 3.0)))
            o.keyframe_insert("location", frame=F(t1))
            o.keyframe_insert("rotation_euler", frame=F(t1))
            appear(o, t0)

        # jumper wires grow hole to hole
        for rec in sc_["wires"]:
            cu = bpy.data.curves.new(rec["name"], "CURVE")
            cu.dimensions = "3D"
            cu.bevel_depth = 0.75 * MM
            cu.bevel_resolution = 3
            cu.resolution_u = 20
            cu.use_fill_caps = True
            sp = cu.splines.new("BEZIER")
            sp.bezier_points.add(len(rec["pts"]) - 1)
            for bp, co in zip(sp.bezier_points, rec["pts"]):
                bp.co = Vector(co) * MM
                bp.handle_left_type = bp.handle_right_type = "AUTO"
            o = bpy.data.objects.new(rec["name"], cu)
            o.data.materials.append(WIRE_MATS["w_" + rec["colour"]])
            scene.collection.objects.link(o)
            cu.bevel_factor_end = 0.0
            cu.keyframe_insert("bevel_factor_end", frame=F(rec["t0"]))
            cu.bevel_factor_end = 1.0
            cu.keyframe_insert("bevel_factor_end", frame=F(rec["t0"] + rec["dur"]))
            appear(o, rec["t0"])

        # twist locks turning: a fixed pivot on the lock's axis, a spinner
        # under it keyed about local z, the knob and hook riding the spinner
        from mathutils import Matrix as _Mx
        for k, rec in enumerate(sc_.get("turns", [])):
            Mp = _Mx(rec["matrix"])
            Mp.translation = Mp.translation * MM
            piv = bpy.data.objects.new(f"turn_piv{k}", None)
            scene.collection.objects.link(piv)
            piv.matrix_world = Mp
            spin = bpy.data.objects.new(f"turn_spin{k}", None)
            scene.collection.objects.link(spin)
            spin.parent = piv
            bpy.context.view_layer.update()
            for n in rec["names"]:
                o = byname[n]
                o.parent = spin
                o.matrix_parent_inverse = spin.matrix_world.inverted()
            spin.rotation_euler = (0, 0, math.radians(rec["deg_from"]))
            spin.keyframe_insert("rotation_euler", frame=F(rec["t0"]))
            spin.rotation_euler = (0, 0, math.radians(rec["deg_to"]))
            spin.keyframe_insert("rotation_euler", frame=F(rec["t0"] + rec["dur"]))

        # lights coming on
        for rec in sc_["glow"]:
            b = SHOW[rec["mat"]].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
            for t, v in zip(rec["t"], rec["strength"]):
                b.default_value = v
                b.keyframe_insert("default_value", frame=F(t))

        # camera path
        cam = scene.camera
        tgt = cam.constraints["Track To"].target
        for rec in sc_["camera"]:
            cam.location = Vector(rec["loc"]) * MM
            tgt.location = Vector(rec["look"]) * MM
            cam.data.lens = rec["lens"]
            cam.keyframe_insert("location", frame=F(rec["t"]))
            tgt.keyframe_insert("location", frame=F(rec["t"]))
            cam.data.keyframe_insert("lens", frame=F(rec["t"]))
        scene.frame_start, scene.frame_end = 1, F(sc_["seconds"]) - 1
    else:
        raise SystemExit(f"unknown --anim={ANIM}")

    tag = (f"_{_src[0]}" if _src else "") + ("_4k" if UHD else "_fhd" if FHD else "") + (
        f"_real_{_petg}" if "--real" in ARGS else "")
    if STILLS:
        for t in STILLS:
            scene.frame_set(1 + int(t * FPS))
            scene.render.filepath = os.path.join(RENDERS, f"anim_{ANIM}{tag}_t{t:g}.png")
            print(f"still at {t:g} s -> {scene.render.filepath}")
            bpy.ops.render.render(write_still=True)
        print("render complete")
        raise SystemExit(0)
    if PNG_SEQ:
        frames_dir = os.path.join(RENDERS, f"anim_{ANIM}{tag}_frames")
        os.makedirs(frames_dir, exist_ok=True)
        scene.render.filepath = os.path.join(frames_dir, "f_")
        if _from:
            scene.frame_start = int(_from[0])
    else:
        try:                                   # Blender 5: video is a media type
            scene.render.image_settings.media_type = "VIDEO"
        except (AttributeError, TypeError):
            pass
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.filepath = os.path.join(RENDERS, f"anim_{ANIM}{tag}_")
    print(f"animating {ANIM}: frames {scene.frame_start}-{scene.frame_end} "
          f"at {FPS} fps -> {scene.render.filepath}*.mp4")
    bpy.ops.render.render(animation=True)
    print("render complete")
    raise SystemExit(0)

wanted = [a.split("=", 1)[1] for a in ARGS if a.startswith("--views=")]
views = wanted[0].split(",") if wanted else list(VIEWS)

for name in views:
    loc, focal, look = VIEWS[name]
    cam = make_camera(name, loc, focal, look)
    scene.camera = cam
    suffix = "_fast" if FAST else ""
    scene.render.filepath = os.path.join(RENDERS, f"{name}{suffix}.png")
    print(f"rendering {name} -> {scene.render.filepath}")
    bpy.ops.render.render(write_still=True)

print("render complete")




