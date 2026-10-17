"""Display mount v1 staged as a full frame assembly:
    python cad/display_mount_v1.py

The frame now ships v2 -- two clip-on posts -- so v1's H-frame (spine, two
uprights, two crossbars) no longer appears anywhere in the assembly. This
copies the current frame (out/frame) to out/frame_mountv1, drops the two
posts, and puts the five v1 pieces and the display back at the v1 height,
so the hub's viewer can still show what was replaced.

This is display_posts.py turned around. That script existed while v1 was
the shipped mount and v2 was on trial; now the roles are swapped and the
old one is retired, since staging the shipped design as a "variant" of
itself would be a no-op. Run AFTER frame.py.
"""

import os
import shutil
import sys

from build123d import *  # noqa: F403

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from params import *  # noqa: E402,F403,F401
from bench import display_mount_placed  # noqa: E402
import frame as F  # noqa: E402
import props as P  # noqa: E402

OUT = os.path.join(HERE, "..", "out")


def main():
    src = os.path.join(OUT, "frame")
    dst = os.path.join(OUT, "frame_mountv1")
    os.makedirs(dst, exist_ok=True)
    for fn in os.listdir(dst):
        os.remove(os.path.join(dst, fn))
    for fn in os.listdir(src):
        # everything but the v2 posts and the display prop they carry
        if fn.endswith(".stl") and not fn.startswith(("asm_post", "prop_hmi")):
            shutil.copy(os.path.join(src, fn), os.path.join(dst, fn))

    total = 0.0
    for k, v in display_mount_placed().items():
        total += v.volume
        export_stl(F.to_post(v, x_centre=MOD_X_DISPLAY),
                   os.path.join(dst, f"asm_{k}.stl"),
                   tolerance=0.02, angular_tolerance=0.1)
    # v1 stand-off: plate 3 + boss 4 + upright 6 + crossbar 6 = 19 mm
    for k, shp in P.hmi_panel().items():
        export_stl(F.to_post(shp, x_centre=MOD_X_DISPLAY,
                             s=F.FR_RAIL_S + DM_DEMO_CY,
                             n=RAIL_TOP_Z + 19.0),
                   os.path.join(dst, f"prop_hmi_{k}.stl"),
                   tolerance=0.02, angular_tolerance=0.1)
    print(f"  v1 mount, 5 pieces, {total / 1000:.1f} cm3 "
          f"-> {os.path.normpath(dst)}")


if __name__ == "__main__":
    main()
