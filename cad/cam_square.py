"""Read one top-down source frame and say how square the camera is -- and what
the board in it measures, using its own calipered width as the ruler.

    python cad/cam_square.py                 # newest 4K frame in ~/OBS Recordings
    python cad/cam_square.py photo.png

The mat's grid is half-inch (12.7 mm); only its edge scales are cm. A square
camera shows the same pitch at the left, centre and right, and at the top,
middle and bottom. A gradient means the side that reads LARGER is nearer the
lens, and the camera should be nudged to look a little more toward it.

Length from the board is the length-to-width ratio times the calipered 54.74:
same object, same plane, so neither the camera height nor the tilt gradient
enters at first order. The mat scale and the 400 mm height are only used for
the cross-checks printed at the end. Honest limit at 4K: about +-0.4 mm on the
length, +-0.15 on a spacing.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

BOARD_W = 54.74          # calipered plain width, the in-plane ruler
BLOCK = 19.99            # the red TPU square, calipered
BLOCK_H = 4.38
H_CAM = 400.0            # lens to mat, tape measure 2026-09-23
GRID = 12.7              # the mat's grid pitch, mm


def newest():
    fs = glob.glob(os.path.expanduser("~/OBS Recordings/Screenshot *.png"))
    fs = [f for f in fs if Image.open(f).size[0] > 3000]
    return max(fs, key=os.path.getmtime)


def peaks(prof, lo, min_gap):
    p = prof - np.percentile(prof, 30)
    thr = np.percentile(p, 97) * 0.5
    idx = [i for i in range(2, len(p) - 2) if p[i] > thr and p[i] >= p[i-1] and p[i] >= p[i+1]
           and p[i] >= p[i-2] and p[i] >= p[i+2]]
    out = []
    for i in idx:
        if out and i - out[-1] < min_gap:
            if p[i] > p[out[-1]]:
                out[-1] = i
        else:
            out.append(i)
    return np.array(out) + lo


def pitch(cs, lo, hi):
    d = np.diff(cs)
    d = d[(d > lo) & (d < hi)]
    return (d.mean() if len(d) else float("nan")), len(d)


def main(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(float)
    hh, ww = im.shape[:2]
    lum = im.mean(axis=2)
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    s = ww / 3836.0                                  # bands below are written for the 4K frame
    px_lo, px_hi = 60 * s, 130 * s
    print(f"{os.path.basename(path)}  {ww} x {hh}")

    # --- squareness: grid pitch in three bands each way --------------------
    bands_x = (("left", 450, 1250), ("centre", 1350, 2500), ("right", 2600, 3350))
    bands_y = (("top", 150, 800), ("middle", 800, 1450), ("bottom", 1450, 2100))
    px = {}
    for name, a, b in bands_x:
        a, b = int(a * s), int(b * s)
        px[name] = pitch(peaks(lum[int(250*s):int(450*s), a:b].mean(axis=0), a, 50*s), px_lo, px_hi)[0]
    py = {}
    for name, a, b in bands_y:
        a, b = int(a * s), int(b * s)
        py[name] = pitch(peaks(lum[a:b, int(2600*s):int(3100*s)].mean(axis=1), a, 50*s), px_lo, px_hi)[0]
    print("grid pitch, px per half inch")
    print("  across:  " + "  ".join(f"{k} {v:.1f}" for k, v in px.items()))
    print("  down:    " + "  ".join(f"{k} {v:.1f}" for k, v in py.items()))
    gx = (px["right"] - px["left"]) / px["centre"] * 100
    gy = (py["bottom"] - py["top"]) / py["middle"] * 100
    print(f"  gradient: {gx:+.1f}% left->right, {gy:+.1f}% top->bottom")
    hint = []
    if abs(gx) > 1: hint.append(("right" if gx > 0 else "left") + " side is nearer")
    if abs(gy) > 1: hint.append(("bottom" if gy > 0 else "top") + " is nearer")
    print("  " + ("SQUARE within 1%" if not hint else "nudge the camera to look more toward the " +
                  " and ".join(h.split()[0] for h in hint) + f"  ({'; '.join(hint)})"))
    scale = px["centre"] / GRID                      # px/mm at mat level, centre of frame

    # --- the board: the biggest white area once thin grid lines are eroded --
    bright = Image.fromarray(((R > 170) & (G > 170) & (B > 170)).astype(np.uint8) * 255)
    k = max(3, int(9 * s) | 1)
    body = np.asarray(bright.filter(ImageFilter.MinFilter(k))) > 0
    # keep the largest 8-connected blob by bounding rows/cols with enough body pixels
    rows = np.where(body.sum(axis=1) > 300 * s)[0]
    cols = np.where(body.sum(axis=0) > 100 * s)[0]
    if len(rows) and len(cols):
        y0, y1 = rows.min() - k // 2, rows.max() + k // 2
        x0, x1 = cols.min() - k // 2, cols.max() + k // 2
        L, W = x1 - x0 + 1, y1 - y0 + 1
        length = L / W * BOARD_W
        err = BOARD_W * L / W * (1 / W + 1 / L)
        print(f"board top face: {L} x {W} px at x {x0}..{x1}, y {y0}..{y1}")
        print(f"  length = L/W x {BOARD_W} = {length:.1f} mm  (+-{err:.1f} for a pixel on each edge)")
        m = H_CAM / (H_CAM - 10.0)
        print(f"  cross-check from the centre scale {scale:.2f} px/mm and {H_CAM:.0f} mm: "
              f"length {L/scale/m:.1f}, width {W/scale/m:.1f} (caliper {BOARD_W})")

    # --- the block: red, near the frame centre -----------------------------
    cy, cx = hh // 2, ww // 2
    win = (slice(cy - int(300*s), cy + int(300*s)), slice(cx - int(400*s), cx + int(400*s)))
    red = Image.fromarray((((R > 140) & (G < 110) & (B < 120))[win]).astype(np.uint8) * 255)
    red = np.asarray(red.filter(ImageFilter.MinFilter(5))) > 0
    ys, xs = np.where(red)
    if len(xs):
        bw, bh = xs.max() - xs.min() + 1 + 4, ys.max() - ys.min() + 1 + 4
        print(f"red block: {bw} x {bh} px -> {bw/scale:.2f} x {bh/scale:.2f} mm at mat scale; "
              f"expected {BLOCK * H_CAM/(H_CAM-BLOCK_H):.2f} at its height")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else newest())
