"""Two deck stations cut out of the real ladder, so a board sits on TWO supports.

    python cad/deck_pair.py     ->  out/stl_coupon/deck_pair.stl

`ladder_station_stub` is one station, 64 mm: enough to show a board is cradled,
not enough to show it sits FLAT across the span, and not enough to slide a
deck_stop along and see whether the indexing teeth catch. This is the same
deck_ladder mesh trimmed to its first two stations (plates centred 51 and 141,
90 mm apart), which a 165 mm board covers with margin.

It is a TRIM of the exported part, not a new design: every tooth, ledge and
rail section is exactly what plate 07 will print. Cut with manifold3d so it
can be made on the Mac, where the CAD kernel is not installed.
"""
import os

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "out", "stl_frame", "deck_ladder.stl")
DEST = os.path.join(ROOT, "out", "stl_coupon", "deck_pair.stl")
CUT_X = 175.0                    # past the second deck plate (spans 131..151)


def solid(tm):
    return Manifold(Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                         tri_verts=np.asarray(tm.faces, np.uint32)))


if __name__ == "__main__":
    src = trimesh.load(SRC, process=True)
    cut = solid(src).trim_by_plane((-1.0, 0.0, 0.0), -CUT_X).to_mesh()
    tm = trimesh.Trimesh(np.asarray(cut.vert_properties)[:, :3], np.asarray(cut.tri_verts), process=True)
    assert tm.is_watertight, "cut is not a closed solid"
    tm.apply_translation(-tm.bounds[0])
    tm.export(DEST)
    print(f"{os.path.normpath(DEST)}  {np.round(tm.extents, 2)}  {tm.volume / 1000:.2f} cm3 "
          f"({tm.volume / src.volume * 100:.0f}% of the full ladder)")
