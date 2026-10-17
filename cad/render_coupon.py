"""How the plate-02 fit test works, as a film:

    blender -b -P cad/render_coupon.py --            # the MP4
    blender -b -P cad/render_coupon.py -- --still=3.0,8.4,13.5,19.0
    blender -b -P cad/render_coupon.py -- --hq

Three shots, one per question the coupon answers: which mortise takes the
rail, which socket takes the bars, which pad stays in the foot pocket. Same
studio, materials and output settings as render.py, so it sits beside the
turntable and the assembly film without looking like a different project.

Every seated pose comes from coupon_demo_poses.py, which checks them against
the meshes; nothing here is placed by eye. What IS invented is the outcome --
which slot is "too tight" and which "just right" -- because nobody knows that
until the plate is printed. The captions in bench-hub.html say so.

Run `python cad/faststart.py <file>.mp4` on the result (render.py's note).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath or __file__))
sys.path.insert(0, HERE)
import coupon_demo_poses as P  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PROJ = os.path.abspath(os.path.join(HERE, ".."))
STL = os.path.join(PROJ, "out", "stl_coupon")
RENDERS = os.path.join(PROJ, "renders")
HQ = "--hq" in ARGS
_st = [a.split("=", 1)[1] for a in ARGS if a.startswith("--still=")]
STILLS = [float(x) for x in _st[0].split(",")] if _st else []
FPS = 24
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# --- materials: render.py's, plus the red the TPU roll actually is ------------
def mat(name, base, rough=0.5, spec=0.5, sheen=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for key, val in (("Base Color", (*base, 1.0)), ("Roughness", rough), ("IOR Level", spec),
                     ("Specular IOR Level", spec), ("Sheen Weight", sheen)):
        if key in b.inputs:
            b.inputs[key].default_value = val
    return m


BONE = mat("bone_pla", (0.585, 0.560, 0.505), rough=0.62, spec=0.4, sheen=0.15)
# The loose test pieces are the same bone PLA on the real plate. Drawn in the
# hub's accent so a stub can be told from the slot it is standing in.
ACCENT = mat("accent_pla", (0.395, 0.098, 0.032), rough=0.54, spec=0.45)
TPU_RED = mat("tpu_red", (0.560, 0.045, 0.040), rough=0.80, spec=0.30, sheen=0.30)
FLOOR = mat("floor", (0.115, 0.116, 0.122), rough=0.55, spec=0.3)

# --- everything lives under one millimetre-scaled root ------------------------
root = bpy.data.objects.new("mm", None)
root.scale = (MM, MM, MM)
scene.collection.objects.link(root)


def load(stem, material):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=os.path.join(STL, stem + ".stl"))
    obj = (set(bpy.data.objects) - before).pop()
    obj.name = stem
    obj.data.materials.clear()
    obj.data.materials.append(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(31))
    except Exception:
        bpy.ops.object.shade_flat()
    obj.parent = root
    obj.rotation_mode = "QUATERNION"
    # native-space centre of the part: moves are steered by this point, not by
    # the STL origin, which for most of these is a corner
    c = sum((Vector(v) for v in obj.bound_box), Vector()) / 8
    return obj, c


coupon, _ = load("fit_coupon_frame", BONE)
rail, RAIL_C = load("rail_stub", ACCENT)
spigot, SPIGOT_C = load("spigot_stub", ACCENT)
tie, TIE_C = load("tie_stub", ACCENT)
gauge, GAUGE_C = load("foot_gauge", BONE)
pads = [load(n, TPU_RED) for n in ("foot_pad_006", "foot_pad_012", "foot_pad_018")]


# --- motion: a part's whole film is a list of timed segments ------------------
def M(pose):
    R, t = pose
    return Matrix.Translation(Vector(t)) @ Matrix(R).to_4x4()


def ease(u):
    return u * u * (3 - 2 * u)


def move(A, B, c, arc=0.0):
    """A -> B, steering the part's centre along a straight line (plus an
    optional vertical arc) while the orientation slerps."""
    A, B = M(A), M(B)
    qa, qb = A.to_quaternion(), B.to_quaternion()
    ca, cb = A @ c, B @ c

    def at(u):
        e = ease(u)
        q = qa.slerp(qb, e)
        centre = ca.lerp(cb, e) + Vector((0, 0, arc * math.sin(math.pi * e)))
        R = q.to_matrix()
        return Matrix.Translation(centre - R @ c) @ R.to_4x4()
    return at


def rock(pose, pivot, axis, degrees):
    """Rattle about a pivot: a decaying sine, so it settles where it started."""
    base, piv = M(pose), Vector(pivot)

    def at(u):
        a = math.radians(degrees) * math.sin(u * math.pi * 5) * (1 - u)
        return Matrix.Translation(piv) @ Matrix.Rotation(a, 4, axis) @ Matrix.Translation(-piv) @ base
    return at


def nudge(pose, dz, pushes):
    """Pushed at and not going in: small downward bounces on a fixed stop."""
    base = M(pose)

    def at(u):
        return Matrix.Translation((0, 0, -dz * abs(math.sin(u * math.pi * pushes)))) @ base
    return at


def sample(track, t):
    first = track[0]
    if t <= first[0]:
        return first[2](0.0)
    last = None
    for t0, t1, fn in track:
        if t0 <= t <= t1:
            return fn((t - t0) / (t1 - t0) if t1 > t0 else 1.0)
        if t1 < t:
            last = fn
        elif last is not None:
            break
    return last(1.0)


HOVER = 34.0          # clear of the 14 mm blocks with a 40 mm stub still swinging upright

rail_track = [
    (0.8, 1.5, move(P.RAIL_REST, (P.RAIL_UP, (P.RAIL_REST[1][0], P.RAIL_REST[1][1], 66.0)), RAIL_C)),
    (1.5, 2.4, move((P.RAIL_UP, (P.RAIL_REST[1][0], P.RAIL_REST[1][1], 66.0)), P.rail_in(0, HOVER), RAIL_C)),
    # 1 dot: goes a third of the way and stops
    (2.6, 3.2, move(P.rail_in(0, HOVER), P.rail_in(0, 7.5), RAIL_C)),
    (3.2, 4.2, nudge(P.rail_in(0, 7.5), 0.9, 3)),
    (4.3, 4.9, move(P.rail_in(0, 7.5), P.rail_in(0, HOVER), RAIL_C)),
    (4.9, 5.7, move(P.rail_in(0, HOVER), P.rail_in(1, HOVER), RAIL_C)),
    # 2 dots: slides home under thumb pressure
    (5.9, 7.0, move(P.rail_in(1, HOVER), P.rail_in(1), RAIL_C)),
    (7.7, 8.3, move(P.rail_in(1), P.rail_in(1, HOVER), RAIL_C)),
    (8.3, 9.1, move(P.rail_in(1, HOVER), P.rail_in(2, HOVER), RAIL_C)),
    # 3 dots: drops in on its own and rattles
    (9.2, 9.6, move(P.rail_in(2, HOVER), P.rail_in(2), RAIL_C)),
    (9.6, 11.0, rock(P.rail_in(2), (P.MORTISE_X[2], P.MORTISE_Y + 3.7, P.BASE_T), "X", 3.2)),
    # back to the keeper, which also clears the camera's line to the sockets
    (11.2, 11.7, move(P.rail_in(2), P.rail_in(2, HOVER), RAIL_C)),
    (11.7, 12.4, move(P.rail_in(2, HOVER), P.rail_in(1, HOVER), RAIL_C)),
    (12.4, 13.2, move(P.rail_in(1, HOVER), P.rail_in(1), RAIL_C)),
]
T_B = 13.6            # cut to the sockets

BAR_HOVER = 22.0
spigot_up = (P.BAR_UP, (P.SPIGOT_REST[1][0] + 12.0, P.SPIGOT_REST[1][1], 40.0))
spigot_track = [
    (T_B + 0.5, T_B + 1.2, move(P.SPIGOT_REST, spigot_up, SPIGOT_C)),
    (T_B + 1.2, T_B + 2.0, move(spigot_up, P.bar_in(P.SOCKET_X[1], BAR_HOVER), SPIGOT_C)),
    (T_B + 2.2, T_B + 3.1, move(P.bar_in(P.SOCKET_X[1], BAR_HOVER), P.bar_in(P.SOCKET_X[1]), SPIGOT_C)),
]
tie_up = (P.BAR_UP, (P.TIE_REST[1][0] + 15.0, P.TIE_REST[1][1], 40.0))
tie_track = [
    (T_B + 3.3, T_B + 4.0, move(P.TIE_REST, tie_up, TIE_C)),
    (T_B + 4.0, T_B + 4.9, move(tie_up, P.bar_in(P.TIE_X, BAR_HOVER), TIE_C)),
    (T_B + 5.0, T_B + 5.9, move(P.bar_in(P.TIE_X, BAR_HOVER), P.bar_in(P.TIE_X), TIE_C)),
]
T_C = T_B + 6.6       # cut to the foot gauge

# The gauge prints pockets-down. Roll it over, press the pads in groove-first,
# then turn it back the right way up and see which pads stay put.
gauge_track = [
    (T_C + 0.5, T_C + 1.6, move(P.gauge_printed(), P.gauge_flipped(), GAUGE_C, arc=26.0)),
]
T_PADS = T_C + 1.9
pad_tracks = []
for i, (pad, c) in enumerate(pads):
    t0 = T_PADS + i * 1.25
    pad_tracks.append([
        (t0, t0 + 0.75, move(P.pad_rest(i), P.pad_in(i, 9.0), c, arc=10.0)),
        # the tighter the pad, the slower the press
        (t0 + 0.8, t0 + 1.1 + i * 0.12, move(P.pad_in(i, 9.0), P.pad_in(i), c)),
    ])
T_TURN = T_PADS + 3 * 1.25 + 0.6
# Turned right way up the pads would be underneath and out of sight, so the
# gauge is picked up and tipped face-on to the camera, then shaken.
gauge_track.append((T_TURN, T_TURN + 1.3, move(P.gauge_flipped(), P.gauge_shown(), GAUGE_C)))
gauge_track.append((T_TURN + 1.6, T_TURN + 3.0, rock(P.gauge_shown(), P.SHOWN_AT, "X", 7.0)))
for i in range(3):
    # carried by the gauge: its pose times the pad's fixed seat in it
    rel = M(P.gauge_flipped()).inverted() @ M(P.pad_in(i))
    for t0, t1, fn in gauge_track[-2:]:
        pad_tracks[i].append((t0, t1, lambda u, fn=fn, rel=rel: fn(u) @ rel))
T_END = T_TURN + 3.0 + 1.4

TRACKS = [(rail, rail_track), (spigot, spigot_track), (tie, tie_track), (gauge, gauge_track)] + \
         [(pads[i][0], pad_tracks[i]) for i in range(3)]

frames = int(T_END * FPS)
for obj, track in TRACKS:
    prev = None
    for f in range(1, frames + 1):
        m = sample(track, (f - 1) / FPS)
        q = m.to_quaternion()
        if prev is not None and prev.dot(q) < 0:
            q.negate()                       # same rotation, no 360 spin between frames
        prev = q
        obj.location = m.to_translation()
        obj.rotation_quaternion = q
        obj.keyframe_insert("location", frame=f)
        obj.keyframe_insert("rotation_quaternion", frame=f)
coupon.location = (0, 0, 0)

# --- studio: render.py's world and lights, recentred on a 152 mm coupon -------
world = bpy.data.worlds.new("studio")
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
w_out = wn.nodes.new("ShaderNodeOutputWorld")
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
wn.links.new(bg.outputs["Background"], w_out.inputs["Surface"])
bg.inputs["Strength"].default_value = 0.30

bpy.ops.mesh.primitive_plane_add(size=8, location=(0.09, 0.02, 0))
bpy.context.active_object.data.materials.append(FLOOR)

SHIFT = Vector((-0.060, -0.040, 0.0))        # render.py lights aim at the bench centre


def area_light(name, loc, rot, size, power, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = size
    d.energy = power
    d.color = color
    o = bpy.data.objects.new(name, d)
    o.location = Vector(loc) + SHIFT
    o.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(o)


area_light("key", (-0.34, -0.46, 0.62), (48, 0, -34), (1.1, 0.8), 3.6)
area_light("fill", (0.62, -0.30, 0.28), (72, 0, 62), (1.3, 1.0), 1.8, color=(0.88, 0.92, 1.0))
area_light("rim", (0.18, 0.58, 0.44), (120, 0, 180), (1.4, 0.16), 3.2, color=(1.0, 0.95, 0.88))
area_light("bounce", (0.15, -0.34, 0.06), (96, 0, 0), (0.9, 0.28), 0.4)


def camera(name, loc, focal, look_at, at_second):
    d = bpy.data.cameras.new(name)
    d.lens = focal
    o = bpy.data.objects.new(name, d)
    o.location = loc
    scene.collection.objects.link(o)
    t = bpy.data.objects.new(name + "_t", None)
    t.location = look_at
    scene.collection.objects.link(t)
    c = o.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = t, "TRACK_NEGATIVE_Z", "UP_Y"
    # a marker bound to a camera is Blender's cut
    mk = scene.timeline_markers.new(name, frame=1 + int(at_second * FPS))
    mk.camera = o
    return o


CAMS = [
    camera("slots", (-0.030, -0.285, 0.190), 54, (0.100, 0.008, 0.020), 0.0),
    camera("sockets", (0.250, -0.150, 0.150), 45, (0.138, 0.058, 0.018), T_B),
    camera("pads", (0.020, -0.215, 0.120), 62, (0.076, -0.036, 0.016), T_C),
]
scene.camera = CAMS[0]

# --- render settings: render.py's animation tier ------------------------------
scene.render.engine = "CYCLES"
scene.cycles.samples = 128 if HQ else 48
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.render.resolution_x = 1920 if HQ else 1280
scene.render.resolution_y = 1080 if HQ else 720
scene.render.fps = FPS
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    pass
prefs = bpy.context.preferences.addons.get("cycles")
if prefs:
    cp = prefs.preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
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

scene.frame_start, scene.frame_end = 1, frames
print(f"coupon film: {frames} frames, {T_END:.1f} s at {FPS} fps; cuts at {T_B:.1f} s and {T_C:.1f} s; "
      f"pads {T_PADS:.1f} s; turn-over {T_TURN:.1f} s")

if STILLS:
    scene.render.image_settings.file_format = "PNG"
    for s in STILLS:
        f = 1 + int(s * FPS)
        scene.frame_set(f)
        # frame_set does not follow marker cameras outside a real playback
        scene.camera = [c for c, t in zip(CAMS, (0.0, T_B, T_C)) if s >= t][-1]
        scene.render.filepath = os.path.join(RENDERS, f"coupon_test_{s:05.1f}.png")
        bpy.ops.render.render(write_still=True)
        print("still", scene.render.filepath)
else:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = os.path.join(RENDERS, "coupon_test_")
    bpy.ops.render.render(animation=True)
print("render complete")
