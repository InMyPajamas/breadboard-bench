"""Draw each plate-01 part with the dimensions the measurement sheet asks for.

    python checklist/measure_pics.py   ->   checklist/img/<part>.png

The parts are drawn from their real STLs, in print pose (flat side down, the
way they come off the plate), so "length / width / height" on the sheet can
be matched to a face by eye. Colours match the sheet's column headers.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from PIL import Image
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
DEST = os.path.join(HERE, "img")

# One colour per kind of reading; mid-tones that hold up on the sheet's light
# and dark cards alike, since the PNGs are transparent.
COL = {"length": "#3d7fd9", "width": "#e0862a", "height": "#2fa36b", "thickness": "#2fa36b", "skip": "#8a8580"}
BODY = np.array([0.85, 0.20, 0.17])          # the TPU on the plate is red

# part -> (stl, [(axis, reading, shown value)])
PARTS = {
    "tpu_block": ("stl_coupon/tpu_block.stl", [("x", "length", "20.00"), ("y", "width", "20.00"), ("z", "height", "4.20")]),
    "foot_pad": ("stl_frame/foot_pad.stl", [("x", "length", "16.24"), ("y", "width", "6.24"), ("z", "height", "4.20")]),
    "rail_pad": ("stl_frame/rail_pad.stl", [("x", "width", "4.20"), ("y", "skip", "≈19.6 · not measured"), ("z", "thickness", "1.35")]),
}


def draw(name, stl, dims):
    m = trimesh.load(os.path.join(OUT, stl), process=False)
    m.apply_translation(-m.bounds[0])
    X, Y, Z = m.extents
    big = max(X, Y)
    off = 0.16 * big                          # how far a dimension line stands off the part
    tick = 0.035 * big

    fig = plt.figure(figsize=(9.0, 6.0), dpi=150)
    ax = fig.add_subplot(projection="3d", proj_type="ortho")
    ax.view_init(elev=26, azim=-58)

    light = np.array([0.35, -0.55, 0.76]); light /= np.linalg.norm(light)
    shade = 0.45 + 0.55 * np.clip(m.face_normals @ light, 0, 1)
    # Draw only the faces turned toward the camera. matplotlib sorts whole
    # triangles by depth, and on a 12-face block a hidden face wins that sort
    # and paints a dark wedge across the top.
    e, a = np.radians(26), np.radians(-58)
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    front = m.face_normals @ eye > 1e-6
    ax.add_collection3d(Poly3DCollection(m.triangles[front], facecolors=np.outer(shade[front], BODY).clip(0, 1),
                                         edgecolors="none", antialiased=False))

    def dim(p0, p1, tdir, label, colour, ha, va, push):
        p0, p1, tdir = map(np.asarray, (p0, p1, tdir))
        ax.plot(*zip(p0, p1), color=colour, lw=2.6, solid_capstyle="round")
        for p in (p0, p1):
            ax.plot(*zip(p - tdir * tick, p + tdir * tick), color=colour, lw=2.6, solid_capstyle="round")
        mid = (p0 + p1) / 2 + np.asarray(push)
        ax.text(*mid, label, color=colour, fontsize=15, fontweight="bold", ha=ha, va=va)

    for axis, reading, shown in dims:
        c = COL[reading]
        label = shown if reading == "skip" else f"{reading}  {shown}"
        if axis == "x":      # along the front edge, stood off toward the viewer
            dim((0, -off, 0), (X, -off, 0), (0, 1, 0), label, c, "center", "top", (0, -off * 1.0, 0))
        elif axis == "y":    # along the right-hand edge
            dim((X + off, 0, 0), (X + off, Y, 0), (1, 0, 0), label, c, "left", "center", (off * 0.45, 0, 0))
        else:                # up the near-left corner
            dim((-off, 0, 0), (-off, 0, Z), (1, 0, 0), label, c, "right", "center", (-off * 0.45, 0, 0))

    pad = off * 1.6
    ax.set_xlim(-pad, X + pad); ax.set_ylim(-pad, Y + pad); ax.set_zlim(0, max(Z, 0.001))
    ax.set_box_aspect((X + 2 * pad, Y + 2 * pad, max(Z, 0.001)))
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    os.makedirs(DEST, exist_ok=True)
    path = os.path.join(DEST, name + ".png")
    fig.savefig(path, transparent=True)
    plt.close(fig)
    # bbox_inches="tight" does not see 3D text and clips the labels, so crop
    # to whatever actually got ink instead.
    im = Image.open(path)
    box = im.getchannel("A").getbbox()
    im.crop((max(box[0] - 14, 0), max(box[1] - 14, 0), min(box[2] + 14, im.width), min(box[3] + 14, im.height))).save(path)
    print(f"{name}: {X:.2f} x {Y:.2f} x {Z:.2f} -> {os.path.normpath(path)}")


if __name__ == "__main__":
    for name, (stl, dims) in PARTS.items():
        draw(name, stl, dims)
