"""Catalogue pictures of the gauge parts, rendered from the STLs themselves.

    blender -b -P checklist/part_pics.py        ->  checklist/img/part_<name>.png

One 3/4 view per part on a plain light ground, lit to read shape rather than
to look good: these sit in the fit-test sheet (fit02.html) beside the test
that uses the part, so "pilot_block" is a picture, not a word. Each part is
shown the way up that shows its working feature, which is not always the way
it printed -- the foot gauges are rolled pockets-up, the pilot block is turned
to show its screw holes.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
IMG = os.path.join(HERE, "img")

# name: (folder, colour, rotation applied first as (axis, degrees) or None)
PLA, TPU = (0.30, 0.32, 0.36), (0.55, 0.04, 0.03)
PARTS = {
    "fit_coupon_frame": ("stl_coupon", PLA, None),
    "rail_stub": ("stl_coupon", PLA, None),
    "spigot_stub": ("stl_coupon", PLA, None),
    "tie_stub": ("stl_coupon", PLA, None),
    "foot_gauge": ("stl_coupon", PLA, ("X", 180)),        # pockets up
    "foot_gauge_v2": ("stl_coupon", PLA, ("X", 180)),
    "foot_pad": ("stl_frame", TPU, ("X", 180)),           # groove (pocket) face up
    "pilot_block": ("stl_coupon", PLA, None),             # its screw-hole face is -x: toward the camera
    "rail_pad": ("stl_frame", TPU, None),
    "ladder_station_stub": ("stl_coupon", PLA, None),
    "rail_cap_615": ("stl_coupon", PLA, None),
    # the cleat gauges (plates 02e-02h). All are modelled the way they print
    # AND the way they are used -- pockets, teeth and pegs all face up, because
    # the board drops onto them from above -- so none of them needs turning.
    "tooth_gauge": ("stl_coupon", PLA, None),
    "slot_gauge_1": ("stl_coupon", PLA, None),
    "cradle_gauge_1": ("stl_coupon", PLA, None),
    "cradle_gauge_2": ("stl_coupon", PLA, None),
    "cradle_gauge_3": ("stl_coupon", PLA, None),
    "span_gauge_1": ("stl_coupon", PLA, None),
    "span_gauge_2": ("stl_coupon", PLA, None),
    "span_gauge_3": ("stl_coupon", PLA, None),
    "span_gauge_slot": ("stl_coupon", PLA, None),
    "peg_gauge": ("stl_coupon", PLA, None),
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1000, 700
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
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
                break
        except Exception:
            continue

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.80, 0.81, 0.83, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.45
scene.world = world

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy, sun.data.angle = 2.4, math.radians(10)
sun.rotation_euler = (math.radians(48), math.radians(-12), math.radians(-35))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam

ground = None
for name, (folder, colour, turn) in PARTS.items():
    path = os.path.join(OUT, folder, name + ".stl")
    if not os.path.exists(path):
        print("missing", path)
        continue
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path)
    obj = (set(bpy.data.objects) - before).pop()
    if turn:
        obj.matrix_world = Matrix.Rotation(math.radians(turn[1]), 4, turn[0]) @ obj.matrix_world
    bpy.context.view_layer.update()
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector(min(p[i] for p in pts) for i in range(3))
    hi = Vector(max(p[i] for p in pts) for i in range(3))
    obj.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))   # centred, standing on z = 0
    size = hi - lo

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = 0.55
    obj.data.materials.clear()
    obj.data.materials.append(m)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_auto_smooth(angle=math.radians(31))
    except Exception:
        pass

    if ground:
        bpy.data.objects.remove(ground)
    reach = max(size) * 6 + 50
    bpy.ops.mesh.primitive_plane_add(size=reach)
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.63, 0.64, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    ground.data.materials.append(gm)

    # 3/4 view from the front-left, above, framed on the part itself: project
    # the bounding box onto the camera plane and fit the ortho window to it.
    direction = Vector((-0.62, -1.0, 0.80)).normalized()
    right = Vector((0, 0, 1)).cross(direction).normalized() * -1
    up = direction.cross(right).normalized() * -1
    half = Vector((size.x / 2, size.y / 2, 0))
    corners = [Vector((sx * half.x, sy * half.y, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, size.z)]
    us, vs = [c.dot(right) for c in corners], [c.dot(up) for c in corners]
    mid = right * ((min(us) + max(us)) / 2) + up * ((min(vs) + max(vs)) / 2)
    cam.location = mid + direction * (max(size) * 4 + 100)
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    aspect = scene.render.resolution_x / scene.render.resolution_y
    cam.data.ortho_scale = max(max(us) - min(us), (max(vs) - min(vs)) * aspect) * 1.18
    cam.data.clip_end = 5000

    scene.render.filepath = os.path.join(IMG, f"part_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("wrote", scene.render.filepath)
    bpy.data.objects.remove(obj)
