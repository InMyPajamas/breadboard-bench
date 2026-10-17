"""Calibrate the overhead camera from one 4K source frame of the printed target,
then measure things in later frames in millimetres at any height.

    python cad/cam_calib.py calib <frame.png> [--plate 140.00x90.00]   -> out/camera_calib.json
    python cad/cam_calib.py board <frame.png> [--h 10.0]                -> the board's length and width

The target (cad/cal_target.py, plate 02m): 84 holes on a 10 mm pitch plus a
6 mm marker at (135, 55), on a black plate over white paper, and two cups
that put three holes each at 5 and 20 mm above the plate. Everything the
fit needs is where the holes ARE, so the plate's calipered outside size
scales the whole pattern (--plate) and nothing else is typed in.

What is fitted, and why it removes each error:
    homography  plate plane -> image, from the 84 + 1 plate dots. Absorbs scale,
                rotation, and the camera's tilt (5 % across the frame today), so
                the camera does not have to be square to be right.
    k1          one radial distortion term about the image centre, chosen to
                minimise the homography's residual. Webcam barrel, ~1-3 %.
    H, nadir    from the six raised dots: a dot h above the plane at P images
                where the plane point P + h/(H-h) * (P - N) would, N being the
                point straight below the lens. Fitting H and N from two known
                heights is what lets any later feature at height h be measured.

Coordinates are the plate's: x along its 140, y along its 90, origin at the
corner nearest the short cup. Dots are found as bright blobs on a dark
surround, so the paper and the board (bright, on bright) never count as dots.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out", "camera_calib.json")

PITCH, HOLE, MARK_D = 10.0, 4.0, 6.0
GRID = [(10.0 + 10.0 * i, 10.0 + 10.0 * j) for i in range(13) for j in range(6)]
EXTRA = [(x, 77.5) for x in (45.0, 55.0, 65.0, 75.0, 85.0, 95.0)]
MARK = (135.0, 55.0)
CUPS = {5.0: [(5.0 + 7.5 + 10.0 * k, 62.0 + 12.5) for k in range(3)],
        20.0: [(100.0 + 7.5 + 10.0 * k, 62.0 + 12.5) for k in range(3)]}
PLATE_NOM = (140.0, 90.0)


# ---------------------------------------------------------------- blobs ----
def blobs(path):
    """Bright blobs on a dark surround: centroid, area, bbox. Returns the frame size too."""
    im = Image.open(path).convert("L")
    L = np.asarray(im).astype(np.float32)
    local = np.asarray(im.filter(ImageFilter.BoxBlur(24))).astype(np.float32)
    # bright RELATIVE to the surround: the cups shade their own paper (a tall-cup
    # dot peaks near 160), and the marker sits 5 mm from the bright paper's edge
    mask = (L > local + 45) & (local < 185)
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    ys, xs = np.where(mask)
    out, loose = [], []
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True; pts = []
        while stack:
            y, x = stack.pop(); pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        p = np.array(pts); area = len(p)
        bw, bh = np.ptp(p[:, 1]) + 1, np.ptp(p[:, 0]) + 1
        if area < 60 or area > 4000 or bw > 80 or bh > 80:
            continue
        wts = np.maximum(L[p[:, 0], p[:, 1]] - local[p[:, 0], p[:, 1]], 1.0)   # surround-relative weights
        cx = (p[:, 1] * wts).sum() / wts.sum(); cy = (p[:, 0] * wts).sum() / wts.sum()
        loose.append((cx, cy, area))
        # a plate dot is round: near-square bbox, filled like a disc (pi/4 = 0.79). Raised
        # dots seen off the nadir are partial discs and only live in `loose`.
        if 120 <= area and area / (bw * bh) >= 0.6 and 0.7 < bw / bh < 1.4:
            out.append((cx, cy, area))
    return np.array(out), np.array(loose), (w, h)


# ------------------------------------------------------------ geometry ----
def undistort(p, k1, c):
    d = p - c; r2 = (d ** 2).sum(axis=1, keepdims=True)
    return c + d * (1 + k1 * r2)


def homography(src, dst):
    """DLT: src (plane mm) -> dst (image px), least squares over all pairs."""
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.array(A))
    Hm = vt[-1].reshape(3, 3)
    return Hm / Hm[2, 2]


def apply(Hm, pts):
    p = np.c_[pts, np.ones(len(pts))] @ Hm.T
    return p[:, :2] / p[:, 2:3]


def fit_plane(design, img, c):
    """Homography + k1, k1 chosen by scanning for the smallest residual."""
    best = None
    for k1 in np.linspace(-3e-7, 3e-7, 61):
        u = undistort(img, k1, c)
        Hm = homography(design, u)
        res = np.linalg.norm(apply(Hm, design) - u, axis=1)
        if best is None or res.mean() < best[0]:
            best = (res.mean(), res.max(), k1, Hm)
    return best


# ------------------------------------------------------------- matching ----
def index_lattice(pts):
    """Integer lattice indices for the grid dots, GROWN outward from a central
    dot one neighbour at a time. A single straight lattice cannot index this
    grid: with the camera 5 % off square the pitch changes across the plate
    and a global basis is more than half a pitch wrong by the far end. Each
    step here is predicted from the dot just crossed, so it follows the
    perspective. Dots off the lattice (the extras, the cups) stay unassigned."""
    n = len(pts)
    d = pts[:, None, :] - pts[None, :, :]
    dist = np.linalg.norm(d, axis=2) + np.eye(n) * 1e9
    nn = np.median(dist.min(axis=1))
    vec = d[(dist > 0.85 * nn) & (dist < 1.15 * nn)]
    ang = np.degrees(np.arctan2(vec[:, 1], vec[:, 0])) % 180.0
    ang[ang > 135] -= 180.0                            # wrap so "nearly horizontal" is one cluster
    horiz = ang[np.abs(ang) < 45]
    a0 = np.median(horiz) if len(horiz) else np.median(ang) - 90.0
    ax = np.array([np.cos(np.radians(a0)), np.sin(np.radians(a0))]) * nn
    ay = np.array([-ax[1], ax[0]])
    seed = int(np.argmin(np.linalg.norm(pts - pts.mean(axis=0), axis=1)))
    idx = {seed: (0, 0)}; pos = {(0, 0): seed}; queue = [seed]
    tol = 0.35 * nn
    while queue:
        k = queue.pop(0); i, j = idx[k]; p = pts[k]
        for di, dj, base in ((1, 0, ax), (-1, 0, -ax), (0, 1, ay), (0, -1, -ay)):
            if (i + di, j + dj) in pos:
                continue
            opp = pos.get((i - di, j - dj))
            step = (p - pts[opp]) if opp is not None else base
            dd = np.linalg.norm(pts - (p + step), axis=1); m = int(dd.argmin())
            if dd[m] < tol and m not in idx:
                idx[m] = (i + di, j + dj); pos[(i + di, j + dj)] = m; queue.append(m)
    ij = np.full((n, 2), -999, dtype=int)
    for k, (i, j) in idx.items():
        ij[k] = (i, j)
    good = ij[:, 0] > -999
    ij[good] -= ij[good].min(axis=0)
    return ij, good, ax, ay


def match(design, img_pts, Hm, k1, c, radius):
    """Nearest detected blob to each projected design point, one blob per point."""
    proj = apply(Hm, np.array(design))
    und = undistort(img_pts, k1, c)
    pairs = []
    for i, p in enumerate(proj):
        dd = np.linalg.norm(und - p, axis=1); j = dd.argmin()
        if dd[j] < radius:
            pairs.append((i, j))
    return pairs


def calibrate(path, plate_mm):
    pts, loose, (w, h) = blobs(path)
    c = np.array([w / 2.0, h / 2.0])
    sx, sy = plate_mm[0] / PLATE_NOM[0], plate_mm[1] / PLATE_NOM[1]
    area = pts[:, 2]
    med = np.median(area)
    main = pts[(area > 0.5 * med) & (area < 1.6 * med)]
    marker = pts[area > 1.8 * med]
    print(f"{os.path.basename(path)}: {len(pts)} blobs, {len(main)} dot-sized, {len(marker)} marker-sized")
    assert len(marker) >= 1, "no 6 mm marker found: is the paper under the plate, and the plate in frame?"
    marker = marker[np.argmax(marker[:, 2])][:2]
    # the plate's dots all lie within ~135 mm of the marker; the rest of the frame is not our business
    near = np.linalg.norm(main[:, :2] - marker, axis=1)
    main = main[near < 1100]
    print(f"  {len(main)} dot-sized blobs within reach of the marker")

    # 1. index the main grid (13 x 6, plus stragglers that will not fit integers)
    ij, good, ax, ay = index_lattice(main[:, :2])
    # keep dots that sit on integer lattice points of a 13 x 6 block
    ok = good & (ij[:, 0] >= 0) & (ij[:, 0] <= 12) & (ij[:, 1] >= 0) & (ij[:, 1] <= 5)
    # 2. orientation from the marker: it sits just past the (12, 4.5) corner of the grid
    grid_pts = main[ok, :2]; grid_ij = ij[ok]
    corners = {(0, 0): None, (12, 0): None, (0, 5): None, (12, 5): None}
    for key in corners:
        sel = (grid_ij[:, 0] == key[0]) & (grid_ij[:, 1] == key[1])
        corners[key] = grid_pts[sel][0] if sel.any() else None
    near = min((k for k in corners if corners[k] is not None), key=lambda k: np.linalg.norm(corners[k] - marker))
    flip_i, flip_j = near[0] == 0, near[1] == 0
    di = np.where(flip_i, 12 - grid_ij[:, 0], grid_ij[:, 0]); dj = np.where(flip_j, 5 - grid_ij[:, 1], grid_ij[:, 1])
    # the lattice axes may be swapped (plate turned 90): the long side has 13 dots
    if ij[:, 0].max() < ij[:, 1].max():
        di, dj = dj, di
    design = np.c_[10.0 + 10.0 * di, 10.0 + 10.0 * dj] * (sx, sy)
    res_mean, res_max, k1, Hm = fit_plane(design, grid_pts, c)
    print(f"  grid fit, {len(design)} dots: residual mean {res_mean:.2f} px, max {res_max:.2f}, k1 {k1:.2e}")

    # 3. bring in every plate-level dot (grid, extras, marker) through the provisional fit and refit
    all_design = [(x * sx, y * sy) for x, y in GRID + EXTRA] + [(MARK[0] * sx, MARK[1] * sy)]
    pairs = match(all_design, pts[:, :2], Hm, k1, c, 0.3 * PITCH * np.linalg.norm(ax) / PITCH)
    D = np.array([all_design[i] for i, _ in pairs]); I = np.array([pts[j, :2] for _, j in pairs])
    res_mean, res_max, k1, Hm = fit_plane(D, I, c)
    print(f"  full fit, {len(D)} of {len(all_design)} plate dots matched: residual mean {res_mean:.2f} px, max {res_max:.2f}, k1 {k1:.2e}")
    Hinv = np.linalg.inv(Hm)

    # 4. the raised dots: unproject to the plane, then fit H and the nadir
    rows = []
    for hgt, dots in CUPS.items():
        for x, y in dots:
            P = np.array([x * sx, y * sy])
            proj = apply(Hm, P[None])[0]
            und = undistort(loose[:, :2], k1, c)
            dd = np.linalg.norm(und - proj, axis=1); j = dd.argmin()
            if dd[j] < 1.2 * np.linalg.norm(ax) and loose[j, 2] >= 100:
                Pp = apply(Hinv, und[j][None])[0]
                rows.append((hgt, P, Pp))
    print(f"  raised dots matched: {len(rows)} of 6  (heights {sorted(set(r[0] for r in rows))})")
    if len(rows) < 2:
        raise SystemExit("  not enough raised dots to fit the camera height; check the cups are seated and lit")
    best = None
    for Hc in np.arange(250.0, 700.0, 0.5):
        A, b = [], []
        for hgt, P, Pp in rows:
            k = hgt / (Hc - hgt)
            # Pp - P = k (P - N)  ->  k N = k P - (Pp - P)
            A.append([k, 0]); b.append(k * P[0] - (Pp[0] - P[0]))
            A.append([0, k]); b.append(k * P[1] - (Pp[1] - P[1]))
        N, r, *_ = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)
        err = np.sqrt(((np.array(A) @ N - np.array(b)) ** 2).mean())
        if best is None or err < best[0]:
            best = (err, Hc, N)
    err, Hc, N = best
    print(f"  camera height {Hc:.0f} mm, nadir at plate ({N[0]:.1f}, {N[1]:.1f}) mm, height-fit rms {err:.2f} mm")

    scale = np.linalg.norm(apply(Hm, np.array([[70.0, 45.0], [80.0, 45.0]])).T[:, 1] - apply(Hm, np.array([[70.0, 45.0], [80.0, 45.0]])).T[:, 0]) / 10.0
    cal = dict(frame=os.path.basename(path), size=[w, h], plate_mm=list(plate_mm), H=Hm.tolist(), k1=float(k1),
               centre=c.tolist(), cam_height=float(Hc), nadir=N.tolist(), residual_px=[float(res_mean), float(res_max)],
               height_rms_mm=float(err), px_per_mm_at_plate=float(scale))
    json.dump(cal, open(OUT, "w"), indent=1)
    print(f"  {scale:.2f} px/mm at the plate; saved -> {os.path.relpath(OUT, os.path.join(HERE, '..'))}")
    return cal


# ------------------------------------------------------------ measuring ----
def to_plane(cal, img_pts, hgt):
    """Image points of a feature `hgt` mm above the plate -> plate-frame mm."""
    Hm = np.array(cal["H"]); c = np.array(cal["centre"]); N = np.array(cal["nadir"])
    Pp = apply(np.linalg.inv(Hm), undistort(np.asarray(img_pts, float), cal["k1"], c))
    k = hgt / (cal["cam_height"] - hgt)
    return (Pp + k * N) / (1 + k)


def components(mask):
    """4-connected components of a small boolean mask: list of (area, x0, x1, y0, y1)."""
    h, w = mask.shape; seen = np.zeros_like(mask, dtype=bool); out = []
    for y0, x0 in zip(*np.where(mask)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True; xs, ys = [], []
        while stack:
            y, x = stack.pop(); xs.append(x); ys.append(y)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        out.append((len(xs), min(xs), max(xs), min(ys), max(ys)))
    return out


def edge(profile, lo, rising):
    """Sub-pixel 50 % crossing of a bright edge along a short profile."""
    a, b = profile.min(), profile.max(); half = (a + b) / 2
    idx = np.where((profile[:-1] < half) & (profile[1:] >= half))[0] if rising else np.where((profile[:-1] >= half) & (profile[1:] < half))[0]
    if len(idx) == 0:
        return np.nan
    i = idx[0] if rising else idx[-1]
    return lo + i + (half - profile[i]) / (profile[i + 1] - profile[i])


def board(path, cal, hgt, aspect=(2.2, 3.5)):
    """The board: the bright component whose outline has a breadboard's aspect,
    found on a 4x downsampled frame, edges then refined to sub-pixel at full
    size and unprojected at height `hgt` (its top face: 9.4 + the tape liner)."""
    im = Image.open(path).convert("L")
    L = np.asarray(im).astype(float)
    # 8x box downsample: the hole rows average away instead of cutting the board into strips
    small = im.resize((im.width // 8, im.height // 8), Image.BOX)
    mask = np.asarray(small).astype(float) > 195          # the board and the paper; the mat, its lines and the ruler fall below
    comps = components(mask)
    cands = [c for c in comps if c[0] > 400 and aspect[0] < (c[2] - c[1] + 1) / (c[4] - c[3] + 1) < aspect[1]]
    if not cands:
        big = sorted(comps, key=lambda c: -c[0])[:6]
        raise SystemExit("no board-shaped bright area; largest bright areas (area, w x h at 1/8): " +
                         str([(a, x1 - x0 + 1, y1 - y0 + 1) for a, x0, x1, y0, y1 in big]))
    _, x0, x1, y0, y1 = max(cands, key=lambda c: c[0])
    x0, x1, y0, y1 = x0 * 8 - 8, x1 * 8 + 15, y0 * 8 - 8, y1 * 8 + 15
    # Within that coarse box, count board pixels per row and per column on an eroded
    # mask: an appendage (a label, the mat's edge scale) never fills a whole row or
    # column the way the board does, so the counts find the board's true extent.
    sub = Image.fromarray((L[y0:y1, x0:x1] > 185).astype(np.uint8) * 255).filter(ImageFilter.MinFilter(9))
    body = np.asarray(sub) > 0
    rows = np.where(body.sum(axis=1) > 0.6 * body.sum(axis=1).max())[0]
    cols = np.where(body.sum(axis=0) > 0.6 * body.sum(axis=0).max())[0]
    yt0, yb0 = y0 + rows.min() - 4, y0 + rows.max() + 4
    xl0, xr0 = x0 + cols.min() - 4, x0 + cols.max() + 4
    xm0, xm1 = xl0 + (xr0 - xl0) // 5, xr0 - (xr0 - xl0) // 5
    ym0, ym1 = yt0 + (yb0 - yt0) // 5, yb0 - (yb0 - yt0) // 5
    lefts = [edge(L[y, xl0 - 12:xl0 + 12], xl0 - 12, True) for y in range(ym0, ym1, 4)]
    rights = [edge(L[y, xr0 - 12:xr0 + 12], xr0 - 12, False) for y in range(ym0, ym1, 4)]
    tops = [edge(L[yt0 - 12:yt0 + 12, x], yt0 - 12, True) for x in range(xm0, xm1, 4)]
    bots = [edge(L[yb0 - 12:yb0 + 12, x], yb0 - 12, False) for x in range(xm0, xm1, 4)]
    xl, xr, yt, yb = (np.nanmedian(v) for v in (lefts, rights, tops, bots))
    corners = to_plane(cal, [[xl, yt], [xr, yt], [xr, yb], [xl, yb]], hgt)
    Ln = (np.linalg.norm(corners[1] - corners[0]) + np.linalg.norm(corners[2] - corners[3])) / 2
    Wn = (np.linalg.norm(corners[3] - corners[0]) + np.linalg.norm(corners[2] - corners[1])) / 2
    print(f"board top face at {hgt} mm: image x {xl:.1f}..{xr:.1f}, y {yt:.1f}..{yb:.1f}  ->  {Ln:.2f} x {Wn:.2f} mm")
    return Ln, Wn


if __name__ == "__main__":
    args = sys.argv[1:]
    plate = PLATE_NOM
    if "--plate" in args:
        i = args.index("--plate"); plate = tuple(float(v) for v in args[i + 1].split("x")); del args[i:i + 2]
    hgt = 10.0
    if "--h" in args:
        i = args.index("--h"); hgt = float(args[i + 1]); del args[i:i + 2]
    cmd, path = args[0], args[1]
    if cmd == "calib":
        calibrate(path, plate)
    elif cmd == "board":
        board(path, json.load(open(OUT)), hgt)
