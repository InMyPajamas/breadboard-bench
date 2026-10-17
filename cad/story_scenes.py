"""3D scenes for the hub's Storyboard: the parts of one joint, posed and exported.

    python cad/story_scenes.py                     -> out/story/<scene>/*.stl + scene.json
    blender -b -P cad/story_render.py              -> renders/story/<scene>.png

A storyboard diagram that does not read gets a rendered picture instead. Each
scene here poses real meshes (the gauge STLs, the catalogue's hardware) in one
coordinate frame and writes a small scene.json -- objects, colours, camera
direction -- that story_render.py turns into an image. Geometry stays honest:
parts are the exported ones, positions come from the same numbers the parts
were cut with, and a "cut" scene is a true section (manifold trim), not a
painted one.

Scenes
  oring_exploded   plate 02c's block, gland face up: two 3 x 1 O-rings, the
                   rail stub and two M3 x 16 cap screws, lifted apart in the
                   order they go on. The second station is left empty so the
                   pocket itself can be seen.
  oring_section    the same joint assembled and sliced through both screws.
  sockets_test     the coupon's four round sockets, with the two bars going in.
  ladder_test      a real breadboard sitting on the ladder stub's toothed shelf.
  screwtip_test    how far a screw reaches past the rail, against the 9.0 mm
                   the shallowest pilot allows.
"""
import json
import os

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "out", "story")

# The parts are BLACK Matte PLA, so that is what these show -- lifted off zero
# far enough to keep their form, and the steel made bright so a screw never
# disappears into the part it is in.
PLA = dict(colour=[0.115, 0.120, 0.132], rough=0.62)
RAIL = dict(colour=[0.055, 0.060, 0.070], rough=0.5)
RUBBER = dict(colour=[0.012, 0.012, 0.015], rough=0.32)
STEEL = dict(colour=[0.72, 0.74, 0.77], rough=0.22, metal=True)
BOARD = dict(colour=[0.82, 0.81, 0.78], rough=0.45)
HOLE = dict(colour=[0.02, 0.02, 0.025], rough=0.7)
RED = dict(colour=[0.55, 0.05, 0.05], rough=0.5)
BLUE = dict(colour=[0.04, 0.10, 0.45], rough=0.5)

# plate 02c's block (pilot_block_oring.py): gland face is x = 0, pilots run
# along +x at z = 7, stations 32 apart in y, station 1 (0.80 deep) at y = -16.
YC, PITCH, AXIS_Z, GLAND = -16.0, 16.0, 7.0, 0.80
STUB_HOLE_X = -14.0                      # rail_stub: its bore pair sits 6 mm from one end
RAIL_T = 7.4


def gland_up(mesh):
    """Turn the block so its gland face (x = 0) is the top, at z = 0:
    (x, y, z) -> (z, y, -x)."""
    T = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]], float)
    m = mesh.copy()
    m.apply_transform(T)
    return m


def cap_screw(length=16.0):
    head = trimesh.creation.cylinder(radius=2.75, height=3.0, sections=48)
    head.apply_translation((0, 0, 1.5))
    socket = trimesh.creation.cylinder(radius=1.45, height=2.0, sections=6)
    socket.apply_translation((0, 0, 2.2))
    head = head.difference(socket, engine="manifold")
    shank = trimesh.creation.cylinder(radius=1.5, height=length, sections=32)
    shank.apply_translation((0, 0, -length / 2))
    return trimesh.util.concatenate([head, shank])          # underside of the head at z = 0


def keep_beyond(mesh, x):
    """True section: keep what lies at x' >= x, capped."""
    m = trimesh.Trimesh(mesh.vertices, mesh.faces, process=True)
    solid = Manifold(Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
    cut = solid.trim_by_plane((1.0, 0.0, 0.0), float(x)).to_mesh()
    return trimesh.Trimesh(np.asarray(cut.vert_properties)[:, :3], np.asarray(cut.tri_verts), process=True)


def build(name, lift_ring, lift_stub, lift_screw, section, view, squash=1.0, frame=None, zoom=1.0):
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    block = gland_up(trimesh.load(os.path.join(ROOT, "out", "stl_coupon", "pilot_block_oring.stl"), process=True))
    stub = trimesh.load(os.path.join(ROOT, "out", "stl_coupon", "rail_stub.stl"), process=True)
    # stub: web face (its z = 0) down on the block, bores over the pilots
    stub.apply_translation((AXIS_Z - STUB_HOLE_X, YC, lift_stub))
    objs = [("block", block, PLA), ("rail_stub", stub, RAIL)]
    for i, dy in enumerate((-PITCH / 2, PITCH / 2)):
        ring = trimesh.creation.torus(major_radius=2.0, minor_radius=0.5, major_sections=72, minor_sections=28)
        ring.apply_scale((1, 1, squash))
        ring.apply_translation((AXIS_Z, YC + dy, -GLAND + 0.5 * squash + lift_ring))
        screw = cap_screw()
        # a cap head rests on the countersink's rim, about 0.7 below the rail's face
        screw.apply_translation((AXIS_Z, YC + dy, lift_stub + RAIL_T - 0.72 + lift_screw))
        objs += [(f"oring{i}", ring, RUBBER), (f"screw{i}", screw, STEEL)]
    # `frame`: the box the camera fits, when that is not the whole scene.
    scene = dict(out=f"renders/story/{name}.png", view=view, zoom=zoom, frame=frame, objects=[])
    for label, mesh, look in objs:
        if section:
            mesh = keep_beyond(mesh, AXIS_Z)
        mesh.export(os.path.join(dest, label + ".stl"))
        scene["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(scene, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print("scene", name, "->", len(objs), "objects")


def coupon_scene():
    """The four round sockets: the fat bar lowered into one and held over the
    other two, the thin bar over its own. Poses come from coupon_demo_poses,
    the same module the fit-test film uses and trimesh checks."""
    import coupon_demo_poses as CP
    name = "sockets_test"
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    load = lambda n: trimesh.load(os.path.join(ROOT, "out", "stl_coupon", n + ".stl"), process=True)  # noqa: E731
    objs = [("coupon", load("fit_coupon_frame"), PLA)]
    for i, lift in enumerate((0.0, 26.0, 40.0)):                  # seated, then held above
        m = load("spigot_stub")
        R, t = CP.bar_in(CP.SOCKET_X[i], lift)
        T = np.eye(4); T[:3, :3] = np.array(R, float); T[:3, 3] = t
        m.apply_transform(T)
        objs.append((f"spigot{i}", m, RAIL))
    m = load("tie_stub")
    R, t = CP.bar_in(CP.TIE_X, 33.0)
    T = np.eye(4); T[:3, :3] = np.array(R, float); T[:3, 3] = t
    m.apply_transform(T)
    objs.append(("tie", m, RAIL))
    scene = dict(out=f"renders/story/{name}.png", view=[-0.55, -1.0, 0.62], zoom=1.0,
                 frame=[[80, 35, 0], [150, 85, 45]], objects=[])
    for label, mesh, look in objs:
        mesh.export(os.path.join(dest, label + ".stl"))
        scene["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(scene, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print("scene", name, "->", len(objs), "objects")


def ladder_scene():
    """A real breadboard resting on the ladder stub's toothed shelf. The board
    is the assembly's own model; the stub is the printed test part. The shelf
    strips sit at z = 3.0 and 57 mm apart, measured off the stub itself."""
    name = "ladder_test"
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    stub = trimesh.load(os.path.join(ROOT, "out", "stl_coupon", "ladder_station_stub.stl"), process=True)
    objs = [("ladder_stub", stub, PLA)]
    src = os.path.join(ROOT, "out", "frame")
    ref = trimesh.load(os.path.join(src, "prop_bb_body.stl"), process=True)
    blo, bhi = ref.bounds
    shift = (-blo[0] - 6.0, -(blo[1] + bhi[1]) / 2 + 46.7, -blo[2] + 3.0)
    for part, look in (("body", BOARD), ("holes", HOLE), ("red", RED), ("blue", BLUE)):
        m = trimesh.load(os.path.join(src, f"prop_bb_{part}.stl"), process=True)
        m.apply_translation(shift)
        m = keep_beyond(m, -3.0)
        # crop the length that overhangs the 64 mm stub, so the picture is not
        # mostly empty board
        m.apply_transform(np.diag([-1, 1, 1, 1])); m.invert()
        m = keep_beyond(m, -74.0)
        m.apply_transform(np.diag([-1, 1, 1, 1])); m.invert()
        if len(m.faces):
            objs.append((f"board_{part}", m, look))
    scene = dict(out=f"renders/story/{name}.png", view=[-0.75, -1.0, 0.70], zoom=1.0, frame=None, objects=[])
    for label, mesh, look in objs:
        mesh.export(os.path.join(dest, label + ".stl"))
        scene["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(scene, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print("scene", name, "->", len(objs), "objects")


def screwtip_scene():
    """One screw through the rail, nothing else: what sticks out the back is
    exactly what has to fit the post's pilot. The shallowest pilot on the
    bench is the tray buttress at 9.0 mm."""
    name = "screwtip_test"
    dest = os.path.join(OUT, name)
    os.makedirs(dest, exist_ok=True)
    stub = trimesh.load(os.path.join(ROOT, "out", "stl_coupon", "rail_stub.stl"), process=True)
    screw = cap_screw(16.0)
    screw.apply_translation((STUB_HOLE_X, 8.0, RAIL_T - 0.72))
    objs = [("rail_stub", keep_beyond(stub, STUB_HOLE_X), RAIL),
            ("screw", keep_beyond(screw, STUB_HOLE_X), STEEL)]
    scene = dict(out=f"renders/story/{name}.png", view=[-1.0, -0.06, 0.10], zoom=1.0,
                 frame=[[STUB_HOLE_X, -2, -11], [STUB_HOLE_X, 18, 12]], objects=[])
    for label, mesh, look in objs:
        mesh.export(os.path.join(dest, label + ".stl"))
        scene["objects"].append(dict(stl=f"out/story/{name}/{label}.stl", **look))
    json.dump(scene, open(os.path.join(dest, "scene.json"), "w"), indent=1)
    print("scene", name, "->", len(objs), "objects")


if __name__ == "__main__":
    build("oring_exploded", lift_ring=9.0, lift_stub=24.0, lift_screw=26.0, section=False,
          view=[-0.85, -1.0, 0.75], zoom=1.45)
    build("oring_section", lift_ring=0.0, lift_stub=0.0, lift_screw=0.0, section=True, view=[-1.0, -0.12, 0.22],
          squash=GLAND / 1.0, frame=[[AXIS_Z, YC - 20, -13], [AXIS_Z, YC + 20, 12]])
    # the point of the whole joint, close enough to see: one ring in its pocket
    build("oring_closeup", lift_ring=0.0, lift_stub=0.0, lift_screw=0.0, section=True, view=[-1.0, -0.05, 0.10],
          squash=GLAND / 1.0, frame=[[AXIS_Z, YC + 2.5, -2.6], [AXIS_Z, YC + 13.5, 3.4]])
    coupon_scene()
    ladder_scene()
    screwtip_scene()
