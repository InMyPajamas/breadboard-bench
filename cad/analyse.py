"""Where is the plastic? Slices the base body into bands to find the mass.

Solid volume is not print weight -- a thin wall prints ~100% solid while a thick
block gets hollowed by infill. So this also estimates filament using a crude
shell model, which is what actually decides whether slimming a feature pays.
"""

import os
import sys

import numpy as np
import trimesh

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
DENSITY = 1.24e-3          # PLA, g/mm^3
WALL = 1.2                 # 3 perimeters at 0.4 nozzle
INFILL = 0.15


def band_volumes(mesh, axis, edges, label):
    """Volume of the mesh within each slab along `axis`."""
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        box = trimesh.creation.box(
            extents=(
                1000 if axis != 0 else hi - lo,
                1000 if axis != 1 else hi - lo,
                1000 if axis != 2 else hi - lo,
            ))
        centre = [0, 0, 0]
        centre[axis] = (lo + hi) / 2
        for a in range(3):
            if a != axis:
                centre[a] = mesh.bounds[:, a].mean()
        box.apply_translation(centre)
        try:
            piece = mesh.intersection(box)
            vol = piece.volume if piece is not None and piece.volume else 0.0
        except Exception:
            vol = 0.0
        rows.append((lo, hi, vol / 1000.0))
    total = sum(r[2] for r in rows)
    print(f"\n  {label}  (total {total:.1f} cm3)")
    for lo, hi, v in rows:
        bar = "#" * int(round(v / max(1e-9, max(r[2] for r in rows)) * 44))
        print(f"    {lo:6.1f}..{hi:6.1f}  {v:7.1f} cm3  {bar}")


def print_estimate(mesh, name):
    """Rough filament mass. Thin features are all shell; thick ones get infill."""
    vol = mesh.volume
    area = mesh.area
    shell = min(vol, area * WALL / 2.0)     # /2: area counts both faces
    core = max(0.0, vol - shell)
    used = shell + core * INFILL
    print(f"  {name:22s} solid {vol/1000:7.1f} cm3   "
          f"est. filament {used * DENSITY:6.0f} g")
    return used * DENSITY


if __name__ == "__main__":
    src = os.path.join(OUT, "stl")
    total = 0.0
    print("filament estimate per part (PLA, 3 perimeters, 15% infill):")
    for fn in sorted(os.listdir(src)):
        if fn.endswith(".stl"):
            m = trimesh.load(os.path.join(src, fn))
            total += print_estimate(m, fn[:-4])
    print(f"  {'TOTAL':22s} {'':21s}{total:19.0f} g")

    base = trimesh.load(os.path.join(src, "base_body.stl"))
    band_volumes(base, 1, np.arange(0, 141, 10), "base body by DEPTH (Y, front->back)")
    band_volumes(base, 2, np.arange(0, 100, 10), "base body by HEIGHT (Z)")
