"""A dimensioned drawing of both breadboards, so a number cannot be ambiguous.

    python cad/board_dims.py  ->  renders/story/board_dims.png

Four readings of this board have been wrong in a row -- a photo estimate, a
shared scale assumption, a hole-pitch coincidence and an unset caliper zero --
and at least one survived because "the spacing" was never pinned to a specific
pair of faces. This draws each dimension against the feature it spans, top
view, so the user can point at whichever line is not what they measured.

Drawn with Pillow rather than matplotlib: matplotlib is not installed on this
Mac and one diagram does not justify the dependency.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "renders", "story")

PAPER = (246, 245, 241)
INK = (27, 28, 31)
DIM = (110, 116, 126)
HOT = (194, 65, 12)
VIO = (109, 40, 217)
BODY = (233, 231, 225)
TABF = (212, 208, 199)

S = 5.2          # pixels per mm
PAD = 70


def F(sz, bold=False):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
              else "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


_F = dict(L=160.0, W=54.74, SP=65.21, N=3)      # L by ruler 2026-09-23; 165.10 was never measured
_H = dict(L=81.89,  W=53.94, SP=53.51, N=2)


def _measured(board, fallback):
    """Dimensions as punched in on board.html, if they are there."""
    import json
    p = os.path.join(HERE, "..", "out", "board_dims.json")
    try:
        with open(p, encoding="utf-8") as f:
            got = (json.load(f) or {}).get(board) or {}
    except Exception:
        return dict(fallback), "built-in defaults"
    out = dict(fallback)
    out.update({k: v for k, v in got.items() if isinstance(v, (int, float))})
    return out, "out/board_dims.json"


_fv, SRC = _measured("full", _F)
_hv, _ = _measured("half", _H)
FULL = dict(name="FULL board", tips=_fv["W"] + 1.41, **_fv)
HALF = dict(name="HALF board", tips=None, **_hv)
TAB_W_TIP, TAB_W_BASE, TAB_PROUD, TAB_H, NOTCH_D = 4.07, 3.85, 1.41, 5.20, 1.60


class Sheet:
    def __init__(self, w_mm, h_mm):
        self.w, self.h = int(w_mm * S) + PAD * 2, int(h_mm * S) + PAD * 2
        self.im = Image.new("RGB", (self.w, self.h), PAPER)
        self.d = ImageDraw.Draw(self.im)
        self.h_mm = h_mm

    def px(self, x, y):
        return PAD + x * S, PAD + (self.h_mm - y) * S      # y up

    def rect(self, x, y, w, h, fill, outline=INK, width=2):
        a = self.px(x, y + h); b = self.px(x + w, y)
        self.d.rectangle([a, b], fill=fill, outline=outline, width=width)

    def line(self, x0, y0, x1, y1, colour=DIM, width=1, dash=False):
        a, b = self.px(x0, y0), self.px(x1, y1)
        if not dash:
            self.d.line([a, b], fill=colour, width=width); return
        n = max(2, int(((b[0]-a[0])**2 + (b[1]-a[1])**2) ** 0.5 / 7))
        for i in range(n):
            if i % 2: continue
            t0, t1 = i / n, (i + 0.55) / n
            self.d.line([(a[0]+(b[0]-a[0])*t0, a[1]+(b[1]-a[1])*t0),
                         (a[0]+(b[0]-a[0])*t1, a[1]+(b[1]-a[1])*t1)], fill=colour, width=width)

    def arrow_head(self, at, toward, colour):
        import math
        ax, ay = at; bx, by = toward
        ang = math.atan2(by - ay, bx - ax)
        L, spread = 9, 0.42
        p1 = (ax + L * math.cos(ang - spread), ay + L * math.sin(ang - spread))
        p2 = (ax + L * math.cos(ang + spread), ay + L * math.sin(ang + spread))
        self.d.polygon([at, p1, p2], fill=colour)

    def dim(self, x0, y0, x1, y1, text, colour=HOT, size=15, dx=0, dy=0, anchor="mm"):
        a, b = self.px(x0, y0), self.px(x1, y1)
        self.d.line([a, b], fill=colour, width=2)
        self.arrow_head(a, b, colour); self.arrow_head(b, a, colour)
        mx, my = (a[0] + b[0]) / 2 + dx, (a[1] + b[1]) / 2 + dy
        for ln_i, ln in enumerate(text.split("\n")):
            self.d.text((mx, my + ln_i * (size + 2)), ln, font=F(size, True),
                        fill=colour, anchor=anchor)

    def text(self, x, y, s, colour=INK, size=15, bold=False, anchor="mm"):
        self.d.text(self.px(x, y), s, font=F(size, bold), fill=colour, anchor=anchor)


def draw_board(sh, b, y):
    L, W, SP, N = b["L"], b["W"], b["SP"], b["N"]
    # END_TAB (left end to the first tab's centre, calipered) places the
    # datum directly; without it the cleats are assumed centred on the board
    end_tab = b.get("END_TAB")
    first = end_tab if isinstance(end_tab, (int, float)) and end_tab > 0 else (L - SP * (N - 1)) / 2
    st = [first + i * SP for i in range(N)]
    sh.rect(0, y, L, W, BODY)
    sh.line(0, y + W / 2, L, y + W / 2, colour=(160, 166, 175), width=1)
    for x in st:
        sh.rect(x - TAB_W_TIP / 2, y - TAB_PROUD, TAB_W_TIP, TAB_PROUD, TABF)
        sh.rect(x - TAB_W_TIP / 2, y + W - NOTCH_D, TAB_W_TIP, NOTCH_D, PAPER)
    sh.text(L / 2, y + W + 9, b["name"], size=19, bold=True)
    return st, first


def main():
    # generous bands: each board needs room for its dimension lines above
    # AND below, and the first attempt had the full board's spacing dims
    # landing on top of the half board's length.
    sh = Sheet(300, 250)
    yF, yH = 160.0, 34.0
    stF, mF = draw_board(sh, FULL, yF)
    stH, mH = draw_board(sh, HALF, yH)

    L, W = FULL["L"], FULL["W"]
    sh.line(0, yF + W, 0, yF + W + 22, dash=True); sh.line(L, yF + W, L, yF + W + 22, dash=True)
    sh.dim(0, yF + W + 19, L, yF + W + 19, f'LENGTH  {L:.2f}', dy=-13)

    sh.line(L, yF, L + 16, yF, dash=True); sh.line(L, yF + W, L + 16, yF + W, dash=True)
    sh.dim(L + 13, yF, L + 13, yF + W, f'WIDTH\n{W:.2f}', dx=40)

    sh.line(L, yF - TAB_PROUD, L + 34, yF - TAB_PROUD, dash=True)
    sh.dim(L + 31, yF - TAB_PROUD, L + 31, yF + W, f'ACROSS\nTIPS\n{FULL["tips"]:.2f}',
           colour=VIO, dx=42)

    for a, bx in zip(stF, stF[1:]):
        sh.line(a, yF - TAB_PROUD, a, yF - 17, dash=True)
        sh.line(bx, yF - TAB_PROUD, bx, yF - 17, dash=True)
        sh.dim(a, yF - 15, bx, yF - 15, f'{FULL["SP"]:.2f}', dy=16)
    sh.text(L / 2, yF - 26, "CLEAT SPACING   —   tip centre to tip centre",
            colour=HOT, size=15, bold=True)
    sh.dim(0, yF - 7, stF[0], yF - 7, f'{mF:.2f}', colour=DIM, size=12, dy=13)

    L2, W2 = HALF["L"], HALF["W"]
    sh.line(0, yH + W2, 0, yH + W2 + 22, dash=True); sh.line(L2, yH + W2, L2, yH + W2 + 22, dash=True)
    sh.dim(0, yH + W2 + 19, L2, yH + W2 + 19, f'LENGTH  {L2:.2f}', dy=-13)
    sh.line(L2, yH, L2 + 16, yH, dash=True); sh.line(L2, yH + W2, L2 + 16, yH + W2, dash=True)
    sh.dim(L2 + 13, yH, L2 + 13, yH + W2, f'WIDTH\n{W2:.2f}', dx=40)
    sh.line(stH[0], yH - TAB_PROUD, stH[0], yH - 17, dash=True)
    sh.line(stH[1], yH - TAB_PROUD, stH[1], yH - 17, dash=True)
    sh.dim(stH[0], yH - 15, stH[1], yH - 15, f'{HALF["SP"]:.2f}', dy=16)
    sh.text(L2 / 2, yH - 26, "CLEAT SPACING", colour=HOT, size=15, bold=True)

    # magnified cleat
    bx, by, m = 205.0, 46.0, 6.5
    sh.text(bx + TAB_W_TIP * m * 1.1, by + 40, "ONE CLEAT, magnified", size=17, bold=True)
    sh.rect(bx, by, TAB_W_TIP * m * 2.2, 22, BODY)
    sh.rect(bx + TAB_W_TIP * m * 0.6, by - TAB_PROUD * m, TAB_W_TIP * m, TAB_PROUD * m, TABF)
    sh.dim(bx + TAB_W_TIP * m * 0.6, by - TAB_PROUD * m - 6,
           bx + TAB_W_TIP * m * 1.6, by - TAB_PROUD * m - 6, f'tip {TAB_W_TIP}', size=13, dy=14)
    sh.dim(bx - 8, by - TAB_PROUD * m, bx - 8, by, f'proud\n{TAB_PROUD}', size=13, dx=-42)
    sh.text(bx + TAB_W_TIP * m * 1.1, by + 10,
            f'base {TAB_W_BASE}   ·   tall {TAB_H}   ·   notch {NOTCH_D} deep',
            colour=DIM, size=13)

    sh.text(150, 112, "Point at whichever line is not what you measured.", size=18, bold=True)
    sh.text(150, 104, "Top view. Tabs drawn on the near edge, notches directly opposite.",
            colour=DIM, size=14)

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, "board_dims.png")
    sh.im.save(dst)
    print("  wrote", os.path.relpath(dst, os.path.join(HERE, "..")), sh.im.size)
    print("  dimensions from:", SRC)


if __name__ == "__main__":
    main()
