"""Where every piece of the plate-02 fit test sits, at rest and seated.

Pure data + 3x3 rotations, no dependencies: imported by render_coupon.py
(inside Blender) and by its own __main__ check (outside, with trimesh), so the
animation and the interference test can never disagree about a pose.

All millimetres, in the fit coupon's own coordinates: the coupon STL is used
exactly as exported, table at z = 0.

A pose is (R, t): world = R @ native + t, native being the part's STL coords.
"""

# --- rotations, written as the image of the part's x / y / z axes -------------
def _R(ex, ey, ez):
    return [[ex[0], ey[0], ez[0]], [ex[1], ey[1], ez[1]], [ex[2], ey[2], ez[2]]]

FLAT = _R((1, 0, 0), (0, 1, 0), (0, 0, 1))          # as printed
FLAT_Y = _R((0, 1, 0), (-1, 0, 0), (0, 0, 1))       # as printed, turned 90 on the table
FLIPPED = _R((1, 0, 0), (0, -1, 0), (0, 0, -1))     # rolled over about x: bed face up

# Rail stub standing in a mortise. coupon_frame.mortise_block turns the rail
# section with Rot(0, 90, 0), build() turns the block with Rot(0, 0, 90):
#   native (x, y, z) -> block (z, y, -x) -> world (cx - y, 25 + z, h - x)
RAIL_UP = _R((0, 0, -1), (-1, 0, 0), (0, 1, 0))

# Half-round stub standing in a socket: bar axis up, arc toward the closed
# side of the socket (+y), flat facing out of the open mouth (-y).
BAR_UP = _R((0, 0, 1), (1, 0, 0), (0, 1, 0))

# --- the coupon's features (coupon_frame.build) -------------------------------
MORTISE_X = [26.0, 72.0, 118.0]        # RAIL_FIT_MORTISE 0.15 / 0.25 / 0.35
MORTISE_Y = 25.0
SOCKET_X = [108.0, 124.0, 140.0]       # R8 + 0.1 / 0.2 / 0.3
TIE_X = 88.0                           # R6 + 0.2
SOCKET_Y = 60.0                        # 4 mm inside the wall's y = 56 face

# The sockets are cut out of the finished plate, base and all, so a bar stands
# on the table. The mortises are cut into each block BEFORE it is added to the
# plate, so they keep the 2 mm base as a floor and the rail stub stands on that.
BASE_T = 2.0
RAIL_HALF = 20.0                       # rail stub is 40 long, centred on its origin


def rail_in(i, lift=0.0):
    return RAIL_UP, (MORTISE_X[i], MORTISE_Y, BASE_T + RAIL_HALF + lift)


def bar_in(x, lift=0.0):
    return BAR_UP, (x, SOCKET_Y, lift)


# --- the foot gauge, rolled pockets-up in front of the coupon -----------------
GAUGE_AT = (36.0, -34.0)               # min corner of its 80 x 14 footprint
GAUGE_H, POCKET_D, PAD_H = 5.2, 3.2, 4.2
POCKET_X = [16.0, 40.0, 64.0]          # pocket centres along the gauge, y = 7


def gauge_printed():
    return FLAT, (GAUGE_AT[0], GAUGE_AT[1], 0.0)


def gauge_flipped(lift=0.0):
    return FLIPPED, (GAUGE_AT[0], GAUGE_AT[1] + 14.0, GAUGE_H + lift)


SHOWN_AT = (76.0, -46.0, 25.0)         # held up in front of the coupon, mid-frame for the pads camera


def gauge_shown(tilt_deg=100.0, centre=SHOWN_AT):
    """Picked up and tipped pocket-face toward a camera on -y: the 'do the pads
    stay in?' look. Rolled-over pose, turned a further tilt_deg about x."""
    import math
    c, s = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
    R = [[1, 0, 0], [0, -c, s], [0, -s, -c]]             # Rx(tilt) @ FLIPPED
    mid = (40.0, 7.0, GAUGE_H / 2)                        # the gauge's own centre
    t = tuple(centre[k] - sum(R[k][j] * mid[j] for j in range(3)) for k in range(3))
    return R, t


def pad_in(i, lift=0.0):
    # Groove face first: foot_pad() calls the grooved face "the pocket face".
    floor = GAUGE_H - POCKET_D         # pocket floor once the gauge is rolled over
    return FLIPPED, (GAUGE_AT[0] + POCKET_X[i], GAUGE_AT[1] + 7.0, floor + PAD_H + lift)


def pad_rest(i):
    return FLAT, (GAUGE_AT[0] + POCKET_X[i], GAUGE_AT[1] - 16.0, 0.0)


# --- where the loose pieces wait ----------------------------------------------
RAIL_REST = (FLAT_Y, (180.0, 30.0, 0.0))
SPIGOT_REST = (FLAT, (168.0, 66.0, 0.0))
TIE_REST = (FLAT, (165.0, 88.0, 0.0))


if __name__ == "__main__":
    # Seat every piece in every place it goes and ask the meshes whether that
    # is physically possible: nothing may be inside the coupon, and a seated
    # piece must actually be in its hole, not hovering beside it.
    import os

    import numpy as np
    import trimesh

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "stl_coupon")
    load = lambda n: trimesh.load(os.path.join(out, n + ".stl"), process=True)

    def place(mesh, pose):
        R, t = pose
        m = mesh.copy()
        T = np.eye(4); T[:3, :3] = np.array(R, float); T[:3, 3] = t
        m.apply_transform(T)
        return m

    def report(label, piece, host):
        pts = piece.sample(4000)
        sd = trimesh.proximity.signed_distance(host, pts)      # + = inside the host
        bite = max(float(sd.max()), 0.0)
        # The mortise detent is DESIGNED to bite the rail (DETENT_BITE 0.05);
        # anything deeper than a snap feature is a pose error.
        verdict = "ok" if bite <= 0.10 else "INTERFERES"
        print(f"  {label:26s} z {piece.bounds[0][2]:6.2f}..{piece.bounds[1][2]:6.2f}   "
              f"deepest bite {bite:.2f} mm   nearest wall {float(np.abs(sd).min()):.2f} mm   {verdict}")
        return bite <= 0.10

    coupon, rail, spigot, tie = map(load, ("fit_coupon_frame", "rail_stub", "spigot_stub", "tie_stub"))
    good = True
    for i, fit in enumerate((0.15, 0.25, 0.35)):
        good &= report(f"rail in mortise {i + 1} ({fit})", place(rail, rail_in(i)), coupon)
    for i, cl in enumerate((0.1, 0.2, 0.3)):
        good &= report(f"spigot in socket {i + 1} ({cl})", place(spigot, bar_in(SOCKET_X[i])), coupon)
    good &= report("tie in tie socket (0.2)", place(tie, bar_in(TIE_X)), coupon)

    gauge = place(load("foot_gauge"), gauge_flipped())
    print(f"  gauge rolled over          z {gauge.bounds[0][2]:6.2f}..{gauge.bounds[1][2]:6.2f}")
    for i, nm in enumerate(("foot_pad_006", "foot_pad_012", "foot_pad_018")):
        pad = place(load(nm), pad_in(i))
        # The pads are MEANT to interfere -- that is FOOT_FIT -- so report the
        # bite instead of failing on it.
        pts = pad.sample(4000)
        inside = int(gauge.contains(pts).sum())
        print(f"  {nm} in pocket {i + 1}     z {pad.bounds[0][2]:6.2f}..{pad.bounds[1][2]:6.2f}   "
              f"proud of gauge {pad.bounds[1][2] - GAUGE_H:.2f} mm   points biting {inside}")
    print("ALL SEATED POSES CLEAR" if good else "POSE ERROR")
