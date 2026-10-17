"""Render the Storyboard's 3D scenes.

    python cad/story_scenes.py                 (first: poses the parts)
    blender -b -P cad/story_render.py          -> renders/story/<scene>.png
    blender -b -P cad/story_render.py -- --only=oring_section

Reads every out/story/<scene>/scene.json: a list of STLs with a colour each,
and the direction the camera looks from. Orthographic, framed on the parts,
soft even light on a mid-grey ground, so dark parts (the rail, the O-rings)
still read against it.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ONLY = [a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")]
W, H = 1600, 1000


def render(scene_file):
    spec = json.load(open(scene_file, encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = "AgX"
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
                    sc.cycles.device = "GPU"
                    break
            except Exception:
                continue
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.77, 0.80, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    sc.world = world
    for rot, energy in (((48, -8, -30), 2.6), ((62, 0, 150), 0.9)):
        light = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
        light.data.energy, light.data.angle = energy, math.radians(16)
        light.rotation_euler = tuple(math.radians(a) for a in rot)
        sc.collection.objects.link(light)

    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in spec["objects"]:
        before = set(bpy.data.objects)
        bpy.ops.wm.stl_import(filepath=os.path.join(ROOT, o["stl"]))
        obj = (set(bpy.data.objects) - before).pop()
        m = bpy.data.materials.new(o["stl"])
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*o["colour"], 1)
        b.inputs["Roughness"].default_value = o.get("rough", 0.5)
        b.inputs["Metallic"].default_value = 1.0 if o.get("metal") else 0.0
        obj.data.materials.append(m)
        try:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        except Exception:
            pass
        for c in obj.bound_box:
            p = obj.matrix_world @ Vector(c)
            lo = Vector(min(a, b_) for a, b_ in zip(lo, p))
            hi = Vector(max(a, b_) for a, b_ in zip(hi, p))

    bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, lo.z - 0.02))
    gm = bpy.data.materials.new("ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.31, 0.34, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    bpy.context.active_object.data.materials.append(gm)

    d = Vector(spec["view"]).normalized()
    right = Vector((0, 0, 1)).cross(d).normalized() * -1
    up = d.cross(right).normalized() * -1
    if spec.get("frame"):
        flo, fhi = Vector(spec["frame"][0]), Vector(spec["frame"][1])
    else:
        flo, fhi = lo, hi
    corners = [Vector((x, y, z)) for x in (flo.x, fhi.x) for y in (flo.y, fhi.y) for z in (flo.z, fhi.z)]
    us, vs = [c.dot(right) for c in corners], [c.dot(up) for c in corners]
    mid = right * ((min(us) + max(us)) / 2) + up * ((min(vs) + max(vs)) / 2) + d * ((lo + hi) / 2).dot(d)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.clip_start, cam.data.clip_end = 1.0, 20000.0
    cam.location = mid + d * 3000
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = max(max(us) - min(us), (max(vs) - min(vs)) * W / H) * 1.14 / spec.get("zoom", 1.0)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.filepath = os.path.join(ROOT, spec["out"])
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)


base = os.path.join(ROOT, "out", "story")
for name in sorted(os.listdir(base)):
    f = os.path.join(base, name, "scene.json")
    if os.path.exists(f) and (not ONLY or name in ONLY):
        render(f)
print("render complete")
