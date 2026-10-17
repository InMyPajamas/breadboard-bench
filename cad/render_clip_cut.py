"""Free the latch, as a film: the plate-03 clip, the knife cut, the spring, the rock-on.

    blender -b -P cad/render_clip_cut.py --                      # renders/clip_free_frames/f_0001..0576.png
    ffmpeg -framerate 24 -i renders/clip_free_frames/f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart renders/clip_free.mp4
    blender -b -P cad/render_clip_cut.py -- --still=2,7.5,12,19   # framing checks -> renders/clip_free_<t>.png
    blender -b -P cad/render_clip_cut.py -- --hq

Pieces come from `cad/clip_cut_scene.py --film`: the AS-PRINTED clip split into
body / latch / weld, the corrected latch, and a 40 mm rail stub. Shots 1-3 are
plate-down (how the piece lies on a table); shot 4 is rail-down (how it goes on
the bench). What is INVENTED: the exact angle the clip rocks on at and how far
the latch springs; both are drawn from the CAD numbers (1.7 mm at the tooth),
not measured. Captions live in bench-hub.html, driven by currentTime.
"""
import math
import os
import sys

import bpy
from mathutils import Euler, Vector

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath or __file__))
PROJ = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(PROJ, "out", "story", "clip_film")
RENDERS = os.path.join(PROJ, "renders")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HQ = "--hq" in ARGS
_st = [a.split("=", 1)[1] for a in ARGS if a.startswith("--still=")]
STILLS = [float(x) for x in _st[0].split(",")] if _st else []
FPS = 24

# clip numbers, as in clip_cut_scene.py (fit 0.25, 30 wide)
INNER, OUTER = 17.425 + 0.25, 17.425 + 0.25 + 3.2
X0, X1 = -15.0, 3.0
ZT = 7.4                              # plate underside; tab top; the weld plane
ROOT_X = X0 + 4.0                     # latch root: it bends about here

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def mat(name, base, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


PETG = mat("petg", (0.50, 0.54, 0.60), 0.5)
TAB = mat("tab", (0.96, 0.52, 0.10), 0.5)
WELD = mat("weld", (0.92, 0.06, 0.06), 0.5)
STEEL = mat("steel", (0.80, 0.81, 0.84), 0.22, 1.0)
RAIL = mat("rail", (0.16, 0.16, 0.18), 0.6)


def load(stem, material, parent=None, name=None):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=os.path.join(SRC, stem + ".stl"))
    o = (set(bpy.data.objects) - before).pop()
    o.name = name or stem
    o.data.materials.append(material)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except Exception:
        pass
    if parent is not None:
        o.parent = parent
    return o


def empty(name, loc, parent=None, rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    e.rotation_euler = Euler([math.radians(a) for a in rot])
    if parent is not None:
        e.parent = parent
    sc.collection.objects.link(e)
    return e


def box(name, size, loc, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.location = loc
    o.data.materials.append(material)
    if parent is not None:
        o.parent = parent
    return o


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def seg(t, a, b):
    """0..1 as t runs a..b, eased."""
    return ease((t - a) / (b - a)) if b > a else 1.0


# ---------------------------------------------------------------- world A: plate down
# Flip the whole as-printed clip over (rotate 180 about x) so the plate lies on the
# ground and the latch side faces +y. Everything in world A hangs off this empty.
A = empty("A", (0, 0, 0), rot=(180, 0, 0))
ground_z = -(ZT + 3.0)                # the plate's top surface after the flip
body = load("old_body", PETG, A)
latch_piv = empty("latch_pivot", (ROOT_X, -INNER - 0.8, 0), A)     # root of the finger
latch = load("old_latch", TAB, latch_piv, "latch")
latch.location = (-ROOT_X, INNER + 0.8, 0)
weld = load("old_weld", WELD, A)
# the blade: 0.45 thick, lying on the plate's top (which is z = -ZT after the flip),
# pointing -x, parked off to +x. In A's frame (pre-flip) that is z = ZT.
blade = box("blade", (34.0, 9.0, 0.45), (X1 + 36.0, -(23.0 + 1.0), ZT + 0.22), STEEL, A)

# ---------------------------------------------------------------- world B: rail down
B = empty("B", (400, 0, 0))
rail = load("rail", RAIL, B)
# the clip hangs off a pivot on the hook lip's edge; rocking about x brings the latch down
rock = empty("rock", (0, INNER - 2.2, 6.2), B)
clipB = empty("clipB", (0, -(INNER - 2.2), -6.2), rock)
bodyB = load("new_body", PETG, clipB, "bodyB")
latchB_piv = empty("latchB_pivot", (ROOT_X, -INNER - 0.8, 0), clipB)
latchB = load("new_latch", TAB, latchB_piv, "latchB")
latchB.location = (-ROOT_X, INNER + 0.8, 0)

# ---------------------------------------------------------------- timeline
T1, T2, T3, T4, T_END = 0.0, 4.5, 11.0, 16.0, 24.0


def pose(t):
    # blade: parked until 5 s, then slides -x under the tab, 5.0 -> 8.0 s, then withdraws 9.5 -> 10.5
    u = seg(t, 5.0, 8.0) - seg(t, 9.5, 10.8)
    blade.location.x = (X1 + 36.0) - 28.0 * u
    # the weld parts as the blade reaches it (its leading edge crosses x = X1 at u ~ 0.68)
    weld.hide_render = weld.hide_viewport = (5.0 + 3.0 * 0.62) <= t < T4
    # the freed latch springs: nothing until the cut, then two presses in shot 3
    flex = 0.0
    if T3 <= t < T4:
        for a in (11.8, 13.8):
            flex += 7.0 * (seg(t, a, a + 0.7) - seg(t, a + 0.9, a + 1.5))
    latch_piv.rotation_euler = Euler((0, 0, math.radians(-flex)))   # tip moves -y (away from the rail)
    # shot 4: rock on. 17 -> 21 s, clip rotates from 24 deg (latch side raised) to 0 about the hook lip
    r = seg(t, 17.0, 21.0)
    rock.rotation_euler = Euler((math.radians(-24.0 * (1 - r)), 0, 0))
    # the latch tooth meets the lip near the end: it flexes out 7 deg over r 0.72..0.93 and snaps home
    bump = seg(r, 0.72, 0.86) - seg(r, 0.90, 0.97)
    latchB_piv.rotation_euler = Euler((0, 0, math.radians(-7.0 * bump)))


# ---------------------------------------------------------------- studio + cameras
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.77, 0.80, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
sc.world = world
for rot, energy in (((48, -8, -30), 2.6), ((62, 0, 150), 0.9)):
    L = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    L.data.energy, L.data.angle = energy, math.radians(16)
    L.rotation_euler = tuple(math.radians(a) for a in rot)
    sc.collection.objects.link(L)
gm = mat("ground", (0.30, 0.31, 0.34), 0.9)
# Two grounds, one per world, each only as big as its own shot needs: a plane
# wide enough to reach the other world sits ABOVE that world's parts (world A
# lies below z = 0) and the camera sees nothing but floor.
for gz, gx in ((ground_z - 0.02, 0.0), (-0.02, 400.0)):
    bpy.ops.mesh.primitive_plane_add(size=300, location=(gx, 0, gz))
    bpy.context.active_object.data.materials.append(gm)


def camera(name, loc, look, focal, at):
    c = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    c.data.lens = focal
    c.data.clip_start, c.data.clip_end = 1.0, 5000.0
    c.location = Vector(loc)
    c.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(c)
    m = sc.timeline_markers.new(name, frame=int(round(at * FPS)) + 1)
    m.camera = c
    return c


# shot 1: the whole clip, plate down, drifting in toward the tab
tab_w = Vector((X1 - 3.0, 23.0, -ZT + 1.7))          # the tab, world A
c1 = camera("cam1", (38.0, 62.0, 34.0), (0.0, 2.0, -6.0), 50, T1)
c2 = camera("cam2", (48.0, 56.0, 22.0), (X1 + 6.0, 22.0, -8.0), 55, T2)
c3 = camera("cam3", (34.0, 54.0, 18.0), (X1 - 2.0, 22.0, -8.0), 55, T3)
c4 = camera("cam4", (400.0 - 48.0, -78.0, 50.0), (400.0, 0.0, 4.0), 45, T4)
sc.camera = c1


def cam_drift(t):
    if t < T2:                                       # push in on the tab
        u = seg(t, 0.4, T2 - 0.2)
        c1.location = Vector((38.0, 62.0, 34.0)).lerp(Vector((30.0, 44.0, 22.0)), u)
        c1.rotation_euler = (Vector((0.0, 2.0, -6.0)).lerp(tab_w, u) - c1.location).to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------- bake
frames = int(T_END * FPS)
sc.frame_start, sc.frame_end = 1, frames
movers = [blade, latch_piv, rock, latchB_piv, weld, c1]
for f in range(1, frames + 1):
    t = (f - 1) / FPS
    pose(t)
    cam_drift(t)
    for o in movers:
        o.keyframe_insert("location", frame=f)
        o.keyframe_insert("rotation_euler", frame=f)
    weld.keyframe_insert("hide_render", frame=f)
    weld.keyframe_insert("hide_viewport", frame=f)

sc.render.engine = "CYCLES"
sc.cycles.samples = 128 if HQ else 48
sc.cycles.use_denoising = True
sc.render.resolution_x = 1920 if HQ else 1280
sc.render.resolution_y = 1080 if HQ else 720
sc.render.fps = FPS
sc.view_settings.view_transform = "AgX"
prefs = bpy.context.preferences.addons.get("cycles")
if prefs:
    cp = prefs.preferences
    for backend in ("METAL", "OPTIX", "CUDA", "HIP"):
        try:
            cp.compute_device_type = backend
            cp.get_devices()
            if any(d.type == backend for d in cp.devices):
                for d in cp.devices:
                    d.use = d.type in (backend, "CPU")
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue

print(f"clip film: {frames} frames, {T_END:.0f} s at {FPS} fps; shots at {T1}, {T2}, {T3}, {T4} s")
if STILLS:
    sc.render.image_settings.file_format = "PNG"
    for s in STILLS:
        f = int(round(s * FPS)) + 1
        sc.frame_set(f)
        for m in sorted(sc.timeline_markers, key=lambda m: m.frame):
            if m.frame <= f and m.camera:
                sc.camera = m.camera
        sc.render.filepath = os.path.join(RENDERS, f"clip_free_{s:05.1f}.png")
        bpy.ops.render.render(write_still=True)
        print("still", sc.render.filepath)
else:
    # PNG frames, then ffmpeg: Blender 5 moved video output behind
    # image_settings.media_type and the old FFMPEG file_format is gone.
    # Frames also survive a crash and let a shot be re-rendered alone.
    #   ffmpeg -framerate 24 -i renders/clip_free_frames/f_%04d.png -c:v libx264 \
    #          -pix_fmt yuv420p -crf 20 -movflags +faststart renders/clip_free.mp4
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(RENDERS, "clip_free_frames", "f_")
    bpy.ops.render.render(animation=True)
    print("frames written")
