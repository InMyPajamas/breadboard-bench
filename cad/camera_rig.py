"""The two-camera rig, drawn: where each camera goes, what it sees, what to set.

    python cad/camera_rig.py  ->  renders/story/camera_rig.png

Plan view of the mat with the 4K frame, the target, the ledge gauge and the
side camera's line of sight; an elevation of the same; and the adjustment list
that turns the pair into a measuring instrument. Numbers are the ones measured
on 2026-09-23: lens 400 mm over the mat, 540 x 304 mm in the 4K frame, the
mat 450 x 300 with a half-inch grid. Drawn with Pillow like the other sheets.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "renders", "story")

PAPER = (246, 245, 241); INK = (27, 28, 31); DIM = (110, 116, 126); HOT = (194, 65, 12)
BLUE = (29, 78, 216); GOOD = (21, 128, 61); MAT = (52, 54, 58); GRID = (86, 89, 95)
PLATE = (236, 234, 228); BOARD = (233, 231, 225); RAIL = (96, 100, 108); RED = (200, 50, 45)

MAT_W, MAT_H = 450.0, 300.0
FRAME_W, FRAME_H = 540.0, 304.0          # what the 4K frame covers at 400 mm
CAM_H = 400.0
TARGET = (155.0, 150.0, 140.0, 90.0)     # x, y, w, h on the mat (y up), just above the centre
GAUGE = (40.0, 15.0, 120.0, 89.4)        # the 02k ledge gauge, bottom left, rails along x
SIDE_CAM = (-110.0, 59.7, 30.0)          # x, y on the mat plane (off its left edge), lens height
LIGHT = (222, 224, 228)                  # text on the dark mat


def F(sz, bold=False):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
              else "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


class Sheet:
    def __init__(self, w, h):
        self.im = Image.new("RGB", (w, h), PAPER); self.d = ImageDraw.Draw(self.im)

    def txt(self, x, y, s, colour=INK, size=15, bold=False, anchor="mm"):
        self.d.text((x, y), s, font=F(size, bold), fill=colour, anchor=anchor)

    def box(self, x, y, w, h, fill, outline=INK, width=2):
        self.d.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=width)

    def dash(self, x0, y0, x1, y1, colour=DIM, width=2, seg=9):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / seg))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n)
            self.d.line([(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0), (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)], fill=colour, width=width)

    def arrow(self, x0, y0, x1, y1, colour=HOT, width=2, L=10):
        self.d.line([(x0, y0), (x1, y1)], fill=colour, width=width)
        a = math.atan2(y1 - y0, x1 - x0)
        self.d.polygon([(x1, y1), (x1 - L * math.cos(a - 0.4), y1 - L * math.sin(a - 0.4)),
                        (x1 - L * math.cos(a + 0.4), y1 - L * math.sin(a + 0.4))], fill=colour)

    def camera(self, x, y, colour=BLUE, r=9):
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=colour, outline=INK, width=2)
        self.d.ellipse([x - r / 2.5, y - r / 2.5, x + r / 2.5, y + r / 2.5], fill=PAPER)


def plan(sh, ox, oy, S):
    """Top view. Mat coordinates: x right, y up; origin at the mat's bottom-left."""
    px = lambda x, y: (ox + x * S, oy + (MAT_H - y) * S)
    sh.txt(ox + MAT_W * S / 2, oy - 46, "PLAN  —  looking down, the overhead camera's view", INK, 19, True)
    # the 4K frame, dashed, centred on the mat
    fx, fy = (MAT_W - FRAME_W) / 2, (MAT_H - FRAME_H) / 2
    a, b = px(fx, fy + FRAME_H), px(fx + FRAME_W, fy)
    sh.dash(a[0], a[1], b[0], a[1], BLUE); sh.dash(a[0], b[1], b[0], b[1], BLUE)
    sh.dash(a[0], a[1], a[0], b[1], BLUE); sh.dash(b[0], a[1], b[0], b[1], BLUE)
    sh.txt(b[0] - 4, b[1] + 14, f"4K frame at {CAM_H:.0f} mm: {FRAME_W:.0f} × {FRAME_H:.0f} mm, 7.1 px/mm", BLUE, 13, True, "rm")
    # the mat and a faint 1-inch grid
    sh.box(*px(0, MAT_H), MAT_W * S, MAT_H * S, MAT, outline=INK, width=3)
    g = 25.4
    x = g
    while x < MAT_W:
        sh.d.line([px(x, 0), px(x, MAT_H)], fill=GRID, width=1); x += g
    y = g
    while y < MAT_H:
        sh.d.line([px(0, y), px(MAT_W, y)], fill=GRID, width=1); y += g
    sh.txt(*px(8, 6), "mat 450 × 300, grid is HALF-INCH (12.7), cm only on the edge scales", LIGHT, 12, False, "ld")
    # the target
    tx, ty, tw, th = TARGET
    sh.box(*px(tx, ty + th), tw * S, th * S, PLATE)
    for i in range(13):
        for j in range(6):
            cx, cy = px(tx + 10 + 10 * i, ty + 10 + 10 * j); sh.d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=INK)
    for k, h in ((0, 5), (1, 20)):
        sx = tx + (5 if k == 0 else 100)
        sh.box(*px(sx, ty + 87), 35 * S, 25 * S, (214, 210, 200))
        sh.txt(*px(sx + 17.5, ty + 74.5), f"cup {h}", INK, 11, True)
    mx, my = px(tx + 135, ty + 55); sh.d.ellipse([mx - 4, my - 4, mx + 4, my + 4], fill=INK)
    sh.txt(*px(tx + tw / 2, ty - 9), "target 02m, marker (big hole) top right", LIGHT, 12, True)
    # the overhead camera, over the mat centre
    cx, cy = px(MAT_W / 2, MAT_H / 2)
    sh.d.line([(cx - 16, cy), (cx + 16, cy)], fill=BLUE, width=2); sh.d.line([(cx, cy - 16), (cx, cy + 16)], fill=BLUE, width=2)
    sh.camera(cx, cy)
    sh.txt(ox, oy - 22, f"Insta360 Link 2C, lens {CAM_H:.0f} mm above the mat centre, looking straight down", BLUE, 13, True, "lm")
    # the gauge and the board on it
    gx, gy, gw, gh = GAUGE
    sh.box(*px(gx, gy + gh), gw * S, gh * S, RAIL)
    sh.box(*px(gx + 8, gy + 17.3 + 54.7), 100 * S, 54.7 * S, BOARD)
    sh.txt(*px(gx + gw / 2, gy + 6), "02k ledge gauge, rails along x", LIGHT, 11, True)
    sh.txt(*px(gx + 58, gy + 45), "board", INK, 11, True)
    # the side camera, off the mat's left edge, looking along the rails
    sx, sy, _ = SIDE_CAM
    scx, scy = px(sx, sy)
    for ang in (-35, 35):
        ex, ey = px(sx + 130 * math.cos(math.radians(ang)), sy + 130 * math.sin(math.radians(ang)))
        sh.dash(scx, scy, ex, ey, GOOD, 1)
    sh.arrow(scx, scy, *px(gx - 6, sy), GOOD, 3)
    sh.camera(scx, scy, GOOD)
    bx, by = px(0, 0)
    sh.txt(bx, by + 44, "C922 side camera: on the table off the mat's left edge, its own legs out of frame,", GOOD, 12, True, "lm")
    sh.txt(bx, by + 62, f"aimed along the rail axis at the gauge's end, {gx - sx - 6:.0f} mm away", GOOD, 12, False, "lm")
    sh.txt(*px(gx - 60, sy + 9), f"{gx - sx - 6:.0f} mm", LIGHT, 12, True)


def elevation(sh, ox, oy, S):
    """Side view from the front: x right, z up; oy is the mat surface."""
    px = lambda x, z: (ox + x * S, oy - z * S)
    sh.txt(ox + MAT_W * S / 2, oy - CAM_H * S - 40, "ELEVATION  —  from the front, heights to scale", INK, 19, True)
    sh.box(*px(0, 3), MAT_W * S, 3 * S, MAT, outline=INK, width=2)
    sh.txt(*px(MAT_W / 2, -14), "mat, 450 wide, 3 thick", DIM, 12)
    # overhead camera and its cone
    cx, cz = MAT_W / 2, CAM_H
    half = math.degrees(math.atan2(FRAME_W / 2, CAM_H))
    for s in (-1, 1):
        sh.dash(*px(cx, cz), *px(cx + s * FRAME_W / 2, 0), BLUE, 1)
    sh.camera(*px(cx, cz))
    sh.txt(*px(cx, cz + 22), f"Insta360 Link 2C, {CAM_H:.0f} mm up, {2 * half:.0f}° across", BLUE, 13, True)
    sh.arrow(*px(cx + 150, cz), *px(cx + 150, 0), DIM, 1)
    sh.txt(*px(cx + 158, cz / 2), f"{CAM_H:.0f}", DIM, 13, True, "lm")
    # the target with its two cups
    tx = TARGET[0]
    sh.box(*px(tx, 2), 140 * S, 2 * S, PLATE)
    sh.box(*px(tx + 5, 7), 35 * S, 5 * S, (214, 210, 200)); sh.box(*px(tx + 100, 22), 35 * S, 20 * S, (214, 210, 200))
    sh.txt(*px(tx + 70, 34), "target: plate 2, cups to 7 and 22", INK, 11, True)
    # the gauge, in front of the target in this view: rail half-round + ledge + the board
    gx = GAUGE[0] + 30
    sh.d.pieslice([px(gx - 8, 8)[0], px(gx, 8)[1], px(gx + 8, 0)[0], px(gx, -8)[1]], 180, 360, fill=RAIL, outline=INK)
    sh.box(*px(gx + 8, 1.8), 4.5 * S, 1.8 * S, RAIL)
    sh.box(*px(gx + 9.2, 11.8), 55 * S, 10 * S, BOARD)
    sh.txt(*px(gx + 36, 20), "board on the ledge gauge, top at 11.8", INK, 11)
    # the side camera: low, off the mat's left edge, aimed at the gauge end
    sx, _, sz = SIDE_CAM
    sh.camera(*px(sx, sz), GOOD)
    sh.arrow(*px(sx + 10, sz), *px(gx - 12, 6), GOOD, 3)
    for dz in (-18, 18):
        sh.dash(*px(sx, sz), *px(gx - 12, 6 + dz), GOOD, 1)
    sh.txt(*px(sx - 8, sz + 26), "C922, lens ~30 mm up, looks along the rails", GOOD, 12, True, "lm")
    sh.txt(*px(sx - 8, sz + 42), "at rim height: it sees the gap under the board", GOOD, 11, False, "lm")


def main():
    sh = Sheet(1700, 1180)
    sh.txt(850, 40, "THE CAMERA RIG  —  where the two cameras go, and what to set", INK, 24, True)
    sh.txt(850, 66, "overhead = x and y (the 4K camera)  ·  side = heights and seating  ·  both on the target = true 3D", DIM, 14)
    plan(sh, 250, 150, 1.45)
    elevation(sh, 1120, 590, 1.0)

    y = 700
    sh.txt(70, y, "ADJUSTMENTS, in order", HOT, 18, True, "lm")
    steps = [
        "1.  Insta360 Link Controller app (not installed on this Mac yet): auto-framing, tracking, gesture control and digital zoom OFF; focus and exposure MANUAL.",
        "2.  OBS: right-click 'Video Capture Device 2' → Screenshot (Source). Never an output screenshot — the canvas is 1080p and carries the scene's scale.",
        "3.  Square the overhead camera: python cad/cam_square.py on the newest 4K frame. Nudge toward the side that reads LARGER until both gradients are under 1 %.",
        "4.  Side camera: on the table beyond the mat's left edge, legs out of its own frame, lens as low as the mount allows, aimed along the rail axis at the gauge's end.",
        "5.  Target: flat near the centre, cups seated (short left, tall right), marker top right. Caliper its 140 and 90 first. One source frame from each camera.",
        "6.  Then any top-down frame reads mm at any height (±0.1), and the side camera reads gaps and seating (±0.2). Strips still decide a 0.15 mm pocket.",
    ]
    for i, s in enumerate(steps):
        sh.txt(70, y + 34 + i * 30, s, INK, 14, False, "lm")
    sh.txt(70, y + 34 + len(steps) * 30 + 8, "Lens height 400 (tape), frame 540 × 304 at 4K (grid), mat 450 × 300 — all measured 2026-09-23. The red block stays in frame as the in-plane scale check (19.99 × 19.99).", DIM, 12, False, "lm")

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "camera_rig.png"); sh.im.save(dst)
    print("  wrote", os.path.relpath(dst, os.path.join(HERE, "..")), sh.im.size)


if __name__ == "__main__":
    main()
