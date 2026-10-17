"""The two ways a tab fails to seat, drawn — because they look identical from above.

    python cad/fit_modes.py  ->  renders/story/fit_modes.png

"One tab drops in, the other misses" has two completely different causes and
they cannot be told apart by looking down at the board:

  SPACING   the tab is in the wrong PLACE along the board, so it lands beside
            its pocket. This is what the slot exists to absorb.
  DEPTH     the tab is in the right place but stands PROUDER than the pocket is
            cut, so it bottoms on the pocket's back wall and never drops. No
            amount of slot helps.

Three panels: the spacing miss in plan, the slot absorbing it in plan, and the
depth miss in section. Drawn with Pillow; matplotlib is not installed here.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "renders", "story")

PAPER = (246, 245, 241)
INK = (27, 28, 31)
DIM = (110, 116, 126)
HOT = (194, 65, 12)
GOOD = (21, 128, 61)
BAD = (185, 28, 28)
RAIL = (96, 100, 108)
BOARD = (233, 231, 225)
TAB = (205, 200, 190)

TAB_W, TAB_PROUD, TAB_H = 4.07, 1.41, 5.20
POCKET_W, POCKET_D = 4.37, 1.71
SLOT_W = 10.30
SPAN = 65.21


def F(sz, bold=False):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
              else "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


class Sheet:
    def __init__(self, w, h):
        self.im = Image.new("RGB", (w, h), PAPER)
        self.d = ImageDraw.Draw(self.im)

    def box(self, x, y, w, h, fill, outline=INK, width=2):
        self.d.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=width)

    def txt(self, x, y, s, colour=INK, size=15, bold=False, anchor="mm"):
        self.d.text((x, y), s, font=F(size, bold), fill=colour, anchor=anchor)

    def head(self, at, toward, colour, L=9):
        import math
        ang = math.atan2(toward[1] - at[1], toward[0] - at[0])
        p1 = (at[0] + L * math.cos(ang - 0.42), at[1] + L * math.sin(ang - 0.42))
        p2 = (at[0] + L * math.cos(ang + 0.42), at[1] + L * math.sin(ang + 0.42))
        self.d.polygon([at, p1, p2], fill=colour)

    def dim(self, x0, y0, x1, y1, text, colour=HOT, size=13, dx=0, dy=0):
        self.d.line([(x0, y0), (x1, y1)], fill=colour, width=2)
        self.head((x0, y0), (x1, y1), colour); self.head((x1, y1), (x0, y0), colour)
        for i, ln in enumerate(text.split("\n")):
            self.txt((x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy + i * (size + 2), ln,
                     colour, size, True)

    def dash(self, x0, y0, x1, y1, colour=DIM):
        n = max(2, int(((x1-x0)**2 + (y1-y0)**2) ** 0.5 / 7))
        for i in range(n):
            if i % 2: continue
            t0, t1 = i/n, (i+0.55)/n
            self.d.line([(x0+(x1-x0)*t0, y0+(y1-y0)*t0),
                         (x0+(x1-x0)*t1, y0+(y1-y0)*t1)], fill=colour, width=1)


def plan(sh, ox, oy, slot, title, verdict, colour, miss=2.6):
    """Looking DOWN: the rail's two pockets, and the board's two tabs over them.
    `oy` is the RAIL's top; the board is drawn 78 px above it and the title
    above that again -- the first attempt put the title at oy-34, which is
    inside the board and therefore invisible."""
    S = 5.0
    sh.txt(ox + 200, oy - 118, title, INK, 18, True)
    # rail with its two pockets
    sh.box(ox, oy, SPAN * S + 90, 46, RAIL, outline=INK)
    p1 = ox + 28
    p2 = ox + 28 + SPAN * S
    w1 = POCKET_W * S
    w2 = (SLOT_W if slot else POCKET_W) * S
    sh.box(p1 - w1 / 2, oy - 1, w1, 20, PAPER, outline=INK)
    sh.box(p2 - w2 / 2, oy - 1, w2, 20, PAPER, outline=INK)
    sh.txt(p1, oy + 60, "exact pocket 4.37", DIM, 13, True)
    sh.txt(p2, oy + 60, ("SLOT 10.30  \u2014 nearly 3 tab widths" if slot
                         else "exact pocket 4.37"), DIM, 13, True)

    # the board above, with tabs hanging down
    by = oy - 78
    sh.box(ox - 10, by, SPAN * S + 110, 52, BOARD, outline=INK)
    sh.txt(ox + 210, by + 26, "BOARD  (seen from above)", DIM, 13)
    t1, t2 = p1, p2 + miss * S
    for tx in (t1, t2):
        sh.box(tx - TAB_W * S / 2, by + 50, TAB_W * S, 22, TAB, outline=INK)

    # does the second tab land inside its opening?
    inside = abs(miss) * S <= (w2 - TAB_W * S) / 2
    sh.dash(t2, by + 72, t2, oy + 2)
    sh.dim(p2, oy + 86, t2, oy + 86, f"tab is {miss:.1f} out of position",
           colour=BAD if not inside else GOOD, dy=18)
    sh.txt(ox + 200, oy + 124, verdict, colour, 16, True)


def section(sh, ox, oy, proud, title, verdict, colour):
    """Looking along the board: the tab going INTO the pocket, side on."""
    S = 26.0
    sh.txt(ox + 150, oy - 96, title, INK, 17, True)
    rail_w = 150
    # rail block, with the pocket cut into its right face
    sh.box(ox, oy, rail_w, 150, RAIL, outline=INK)
    pd = POCKET_D * S
    sh.box(ox + rail_w - pd, oy + 34, pd, TAB_H * S, PAPER, outline=INK)
    sh.dim(ox + rail_w - pd, oy + 16, ox + rail_w, oy + 16, f"pocket {POCKET_D} deep",
           dy=-19)

    # board edge and its tab, pushed up if the tab is too proud to bottom out
    lift = max(0.0, (proud - POCKET_D)) * S
    bx = ox + rail_w - pd + proud * S
    sh.box(bx, oy + 34 - lift, 132, 150, BOARD, outline=INK)
    sh.box(bx - proud * S, oy + 34 - lift, proud * S, TAB_H * S, TAB, outline=INK)
    sh.dim(bx - proud * S, oy - 48, bx, oy - 48,
           f"tab stands {proud:.2f} proud", colour=colour, dy=-19)
    if lift > 0:
        sh.dash(ox + rail_w - pd, oy + 34, bx + 132, oy + 34)
        sh.dim(bx + 150, oy + 34 - lift, bx + 150, oy + 34,
               f"held {proud - POCKET_D:.2f} high", colour=BAD, dx=96)
    sh.txt(ox + 150, oy + 200, verdict, colour, 16, True)


def main():
    sh = Sheet(1500, 1130)
    sh.txt(750, 38, "WHY A TAB DOES NOT SEAT  —  two causes that look the same from above",
           INK, 23, True)

    plan(sh, 150, 250, slot=False,
         title="1.  SPACING MISS — exact pockets",
         verdict="second tab lands BESIDE its pocket → board props up",
         colour=BAD)
    plan(sh, 150, 530, slot=True,
         title="2.  THE SLOT ABSORBS IT",
         verdict="same 2.6 mm error, but the slot is 10.30 wide → it drops in",
         colour=GOOD)

    section(sh, 210, 820, proud=TAB_PROUD,
            title="3.  DEPTH OK  — tab 1.41 into a 1.71 pocket",
            verdict="bottoms out, board sits down", colour=GOOD)
    section(sh, 880, 820, proud=2.30,
            title="4.  DEPTH MISS — tab prouder than the pocket is deep",
            verdict="tab jams on the back wall → board never drops\nNO slot can fix this",
            colour=BAD)

    sh.txt(750, 1098, "If the slotted strip also fails, the cause is 4, not 1 — and the number to "
           "re-measure is how far a tab stands proud.", DIM, 15)

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "fit_modes.png")
    sh.im.save(dst)
    print("  wrote", os.path.relpath(dst, os.path.join(HERE, "..")), sh.im.size)


if __name__ == "__main__":
    main()
