"""Pictures for the hub's Catalogue and Schematics tabs.

    python cad/catalog.py                          (first: writes out/catalog.json)
    blender -b -P cad/render_catalog.py            -> renders/parts/<id>.png
                                                      renders/schematic/{front,top,side}.png
                                                      renders/schematic/views.json
    blender -b -P cad/render_catalog.py -- --only=schematic | --only=parts

Two kinds of picture. PARTS: one 3/4 view of each printed part, off its own
STL, for the catalogue cards. SCHEMATIC: three true orthographic views of the
seated assembly in out/frame, rendered at a fixed scale with a transparent
ground, plus views.json recording exactly which millimetres each image
covers. The hub lays its dimension lines over the images in an SVG whose units
ARE millimetres, so a dimension is drawn from the mesh's numbers and lands on
the mesh's pixels -- nothing is positioned by eye.
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
ONLY = ([a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")] or ["all"])[0]
PX_PER_MM = 5.0
MARGIN = 6.0

CAT = json.load(open(os.path.join(ROOT, "out", "catalog.json"), encoding="utf-8"))

PLA, PETG, TPU = (0.56, 0.55, 0.51), (0.62, 0.20, 0.07), (0.62, 0.05, 0.04)
RAIL, STEEL, PROP = (0.10, 0.11, 0.13), (0.55, 0.57, 0.60), (0.30, 0.32, 0.36)
COLOUR = {"PLA": PLA, "PETG": PETG, "TPU": TPU}
KIND = {"steel": ((0.50, 0.52, 0.55), 0.35), "nickel": ((0.72, 0.73, 0.75), 0.25),
        "rubber": ((0.035, 0.035, 0.04), 0.6), "board": ((0.70, 0.69, 0.66), 0.5)}


def colour_for(name):
    if name.startswith(("asm_foot", "asm_pad")):
        return TPU
    if name.startswith(("hw_", "asm_mag")):
        return STEEL
    if name == "asm_rail":
        return RAIL
    if name.startswith(("asm_sidebin", "asm_sidetray", "asm_post", "asm_railbin", "asm_stop")):
        return PETG
    if name.startswith("prop_"):
        return PROP
    return PLA


def reset(w, h, transparent):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = int(w), int(h)
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
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
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.82, 0.83, 0.85, 1)
    bg.inputs[1].default_value = 0.55
    sc.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy, sun.data.angle = 2.2, math.radians(14)
    sun.rotation_euler = (math.radians(46), math.radians(-10), math.radians(-32))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.clip_start, cam.data.clip_end = 1.0, 20000.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def load(path, colour, rough=0.55):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path)
    obj = (set(bpy.data.objects) - before).pop()
    m = bpy.data.materials.new(os.path.basename(path))
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = rough
    obj.data.materials.clear()
    obj.data.materials.append(m)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_auto_smooth(angle=math.radians(31))
    except Exception:
        pass
    return obj


def parts():
    out = os.path.join(ROOT, "renders", "parts")
    os.makedirs(out, exist_ok=True)
    sc, cam = reset(900, 620, False)
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "SUN"))
    fill.data.energy = 1.2
    fill.rotation_euler = (math.radians(60), 0, math.radians(140))
    sc.collection.objects.link(fill)
    ground = None
    for row in CAT["parts"] + CAT.get("gauges", []) + CAT.get("hardware", []):
        path = os.path.join(ROOT, row["stl"])                # wherever plates.py found it
        if not os.path.exists(path):
            print("missing STL for", row["id"])
            continue
        if "kind" in row:                                    # bought, not printed
            obj = load(path, *KIND[row["kind"]])
            if row["kind"] in ("steel", "nickel"):
                obj.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
        else:
            obj = load(path, RAIL if row["id"] == "din_rail" else COLOUR[row["material"]])
        if row["id"].startswith(("foot_pad", "foot_gauge")):  # pocket face up: that is the working face
            obj.rotation_euler = (math.radians(180), 0, 0)
        bpy.context.view_layer.update()
        pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        lo = Vector(min(p[i] for p in pts) for i in range(3))
        hi = Vector(max(p[i] for p in pts) for i in range(3))
        obj.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        size = hi - lo
        if ground:
            bpy.data.objects.remove(ground)
        bpy.ops.mesh.primitive_plane_add(size=max(size) * 8 + 80)
        ground = bpy.context.active_object
        gm = bpy.data.materials.new("ground")
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.075, 0.08, 0.095, 1)
        gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
        ground.data.materials.append(gm)
        # Long parts lie across the frame; the view direction swings to suit.
        d = Vector((-0.62, -1.0, 0.80)) if size.x >= size.y else Vector((-1.0, -0.62, 0.80))
        d.normalize()
        right = Vector((0, 0, 1)).cross(d).normalized() * -1
        up = d.cross(right).normalized() * -1
        corners = [Vector((sx * size.x / 2, sy * size.y / 2, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (0, size.z)]
        us, vs = [c.dot(right) for c in corners], [c.dot(up) for c in corners]
        mid = right * ((min(us) + max(us)) / 2) + up * ((min(vs) + max(vs)) / 2)
        cam.location = mid + d * (max(size) * 4 + 200)
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = max(max(us) - min(us), (max(vs) - min(vs)) * 900 / 620) * 1.2
        sc.render.filepath = os.path.join(out, row["id"] + ".png")
        bpy.ops.render.render(write_still=True)
        print("wrote", sc.render.filepath)
        bpy.data.objects.remove(obj)


def schematic():
    out = os.path.join(ROOT, "renders", "schematic")
    os.makedirs(out, exist_ok=True)
    env = CAT["envelopes"]["all"]
    lo, hi = Vector(env["lo"]), Vector(env["hi"])
    views = {
        # name: (u axis, v axis, camera euler, looking-along axis index, camera sits at +/- end)
        "front": (0, 2, (math.radians(90), 0, 0), 1, -1),
        "top": (0, 1, (0, 0, 0), 2, +1),
        "side": (1, 2, (math.radians(90), 0, math.radians(90)), 0, +1),
    }
    meta = {"px_per_mm": PX_PER_MM, "views": {}}
    src = os.path.join(ROOT, "out", "frame")
    for name, (ua, va, euler, la, sign) in views.items():
        # Snap the window to whole pixels, growing it, so PX_PER_MM is exact
        # and not "nearly": the hub draws dimensions in the same millimetres.
        u0, v0 = lo[ua] - MARGIN, lo[va] - MARGIN
        w = math.ceil((hi[ua] + MARGIN - u0) * PX_PER_MM)
        h = math.ceil((hi[va] + MARGIN - v0) * PX_PER_MM)
        u1, v1 = u0 + w / PX_PER_MM, v0 + h / PX_PER_MM
        sc, cam = reset(w, h, True)
        for f in sorted(os.listdir(src)):
            if f.endswith(".stl"):
                # catalog.py's light stand-in for a too-dense vendor mesh
                lt = os.path.join(ROOT, "out", "frame_light", f)
                load(lt if os.path.exists(lt) else os.path.join(src, f),
                     colour_for(f[:-4]), rough=0.7)
        centre = [0.0, 0.0, 0.0]
        centre[ua], centre[va] = (u0 + u1) / 2, (v0 + v1) / 2
        centre[la] = (hi[la] + 2000) if sign > 0 else (lo[la] - 2000)
        cam.location = centre
        cam.rotation_euler = euler
        cam.data.ortho_scale = (u1 - u0) if w >= h else (v1 - v0)     # Blender: the LARGER side
        # Drawing-style edges over the shaded view, in the site's bone colour.
        sc.render.use_freestyle = True
        sc.render.line_thickness = 1.6
        vl = bpy.context.view_layer
        vl.use_freestyle = True
        ls = vl.freestyle_settings.linesets.new("edges")
        ls.select_silhouette = ls.select_border = ls.select_crease = True
        ls.linestyle.color = (0.86, 0.84, 0.78)
        vl.freestyle_settings.crease_angle = math.radians(140)
        sc.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("wrote", sc.render.filepath)
        meta["views"][name] = dict(u_axis="xyz"[ua], v_axis="xyz"[va], u0=round(u0, 3), u1=round(u1, 3),
                                   v0=round(v0, 3), v1=round(v1, 3), px=[int(w), int(h)])
    json.dump(meta, open(os.path.join(out, "views.json"), "w"), indent=1)


if ONLY in ("all", "schematic"):
    schematic()
if ONLY in ("all", "parts"):
    parts()
print("render complete")
