"""Does it tip, and does it rack?

"Still very stable" is the stated requirement, so it should be a number rather
than an opinion. Two failure modes matter for a desktop frame:

  TIPPING   -- you press a jumper into a board mounted high on the DIN rail and
               the whole bench rotates backward about its rear ground contact.
  RACKING   -- you press into the breadboard and the two end plates lean over
               like a parallelogram, because the rods between them are pinned
               at the ends and nothing triangulates the box.

Everything is one material, so volume stands in for mass throughout.
"""

import os
import sys

import numpy as np
import trimesh

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
RHO = 1.24e-3            # g/mm^3, PLA solid
FILL = 0.45              # rough solid fraction after walls + infill
G = 9.81e-3              # N per gram


def assembly(sub):
    d = os.path.join(OUT, sub)
    parts = {}
    for fn in sorted(os.listdir(d)):
        if fn.startswith("asm_") and fn.endswith(".stl"):
            parts[fn[4:-4]] = trimesh.load(os.path.join(d, fn))
    return parts


def report(name, sub, press_z, press_y):
    parts = assembly(sub)
    vol = np.array([p.volume for p in parts.values()])
    cen = np.array([p.center_mass for p in parts.values()])
    mass = vol.sum() * RHO * FILL
    com = (cen * vol[:, None]).sum(axis=0) / vol.sum()

    ground = np.vstack([p.bounds for p in parts.values()])
    y0, y1 = ground[:, 1].min(), ground[:, 1].max()

    print(f"\n{name}")
    print(f"  mass ~{mass:.0f} g   centre of mass Y={com[1]:.0f} Z={com[2]:.0f}")
    print(f"  ground footprint Y {y0:.0f}..{y1:.0f} mm")

    # Tipping backward about the rear contact line.
    lever_com = y1 - com[1]                      # restoring arm
    lever_push = press_z                          # height you push at
    f_tip = mass * G * lever_com / lever_push
    print(f"  push BACKWARD at Z={press_z:.0f} (a rail module):")
    print(f"    restoring arm {lever_com:.0f} mm, tips at {f_tip:.1f} N "
          f"({f_tip / G / 1000:.1f} kg-force)")

    # Tipping forward about the front contact line.
    f_fwd = mass * G * (com[1] - y0) / press_z
    print(f"  push FORWARD  at Z={press_z:.0f}: "
          f"restoring arm {com[1] - y0:.0f} mm, tips at {f_fwd:.1f} N")

    # Pressing straight down on a board is the common case -- it cannot tip,
    # but it can rock if the load lands outside the footprint.
    print(f"  press DOWN at Y={press_y:.0f}: "
          f"{'inside' if y0 < press_y < y1 else 'OUTSIDE'} the footprint")
    return mass, com


def insertion(mass, com, y_rear, mod_y, mod_z, tilt_deg):
    """The real load case: pushing a connector INTO a rail-mounted board.

    You push along the module's inward normal, not horizontally. That vector
    has a backward component that tips the bench and a downward component that
    holds it down -- and the split between them is set entirely by the panel
    tilt. Upright panel: nearly all of your push is trying to tip it.
    """
    t = np.radians(tilt_deg)
    back, down = np.cos(t), np.sin(t)     # tilt measured from vertical
    tip_arm = back * mod_z - down * (y_rear - mod_y)
    restoring = mass * G * (y_rear - com[1])
    if tip_arm <= 0:
        return float("inf"), tip_arm
    return restoring / tip_arm, tip_arm


def untippable(tilt, rail_s, post_y0, y_rear, deck=8.0):
    """How much foot must sit BEHIND the post for the bench to be untippable.

    This is the constraint that should have governed the design from day one,
    so it lives here as a gate rather than as a report.

    The tipping arm is  cos(t)*Z_rail - sin(t)*(Y_rear - Y_rail).  Note what is
    NOT in it: mass. While the arm is positive, mass is silently load-bearing
    for stability and F_tip scales with it -- which means every gram removed
    this session made the bench easier to tip over. Drive the arm negative and
    mass leaves the equation: your own push holds it down, at any force.

    Tilt is the weak lever here. The strong one is decoupling the post foot
    from the rear edge of the footprint, so the foot overhangs backward.
    """
    t = np.radians(tilt)
    z = deck + rail_s * np.cos(t)
    y = post_y0 + rail_s * np.sin(t)
    need = y + z / np.tan(t)          # y_rear that makes the arm exactly zero
    arm = np.cos(t) * z - np.sin(t) * (y_rear - y)
    return dict(rail_z=z, rail_y=y, y_rear_needed=need,
                overhang_needed=need - y, arm=arm, safe=arm <= 0)


def search(m_f, c_f, DECK, tag, s_min):
    """Shallowest bench that survives a 15 N insertion, given how low the
    tallest module lets the rail sit."""
    print(f"\n\nSHALLOWEST SAFE BENCH -- {tag}")
    print("  tilt  rail_s   rail Z   depth   tips at   eye off")
    best = None
    for tilt in range(20, 61, 2):
        for s in range(s_min, 42, 2):
            t = np.radians(tilt)
            post_y0, post_h = 98.0, s + 20.0
            z_m = DECK + s * np.cos(t)
            y_m = post_y0 + s * np.sin(t)
            depth = post_y0 + post_h * np.sin(t) + 14.0 / np.cos(t)
            f, _ = insertion(m_f, c_f, depth, y_m, z_m, tilt)
            los = np.degrees(np.arctan2(460 - z_m, y_m + 350))
            off = abs(los - tilt)
            if f < 15 or off > 12:
                continue
            if best is None or depth < best[3]:
                best = (tilt, s, z_m, depth, f, off)
    if best is None:
        print("  no configuration meets 15 N under these constraints")
        return
    tilt, s, z_m, depth, f, off = best
    fs = "none" if f == float("inf") else f"{f:.0f} N"
    print(f"  {tilt:3d}    {s:4.0f}    {z_m:5.1f}   {depth:5.0f}   {fs:>6s}"
          f"    {off:4.1f} deg")
    print(f"    vs now (tilt 20, rail_s 38, depth 151, tips at 1.8 N):  "
          f"{depth - 151:+.0f} mm depth")


if __name__ == "__main__":
    print("stability (volume stands in for mass; one material throughout)")
    m_f, c_f = report("FRAME", "frame", press_z=44.0, press_y=48.0)
    m_c, c_c = report("CONSOLE", "assembly", press_z=61.0, press_y=35.0)

    print("\n\nINSERTING A CONNECTOR INTO A RAIL-MOUNTED BOARD")
    print("  (the force that actually matters -- 10 to 20 N in practice)")
    print("\n  Everything moves with the tilt, so nothing here is held fixed:")
    print("    reclining drops the module (less leverage), pushes it back")
    print("    (more restoring), and rakes the post further back (deeper bench).")
    print("\n  tilt   rail Z   rail Y   bench depth   tips at   eye off-normal")
    POST_Y0, DECK, S, POST_H = 112.0, 8.0, 38.0, 70.0
    for tilt in (20, 25, 30, 35, 40, 45, 50, 55):
        t = np.radians(tilt)
        z_m = DECK + S * np.cos(t)
        y_m = POST_Y0 + S * np.sin(t)
        depth = POST_Y0 + POST_H * np.sin(t) + 14.0 / np.cos(t)
        f, _ = insertion(m_f, c_f, depth, y_m, z_m, tilt)
        # sightline for a seated user: eye 460 above desk, 350 in front
        los = np.degrees(np.arctan2(460 - z_m, y_m + 350))
        off = abs(los - tilt)
        fs = "  none" if f == float("inf") else f"{f:6.1f}"
        flag = "  <-- both" if (f == float("inf") or f > 15) and off < 8 else ""
        print(f"  {tilt:3d}    {z_m:5.1f}    {y_m:5.1f}      {depth:5.0f}      "
              f"{fs}      {off:4.1f} deg{flag}")
    print("\n  'eye off-normal' is how far the display faces away from your")
    print("  sightline. The tilt that stops it tipping and the tilt that squares")
    print("  the screen to your eye are close to the same number.")

    # ------------------------------------------------------------------
    # Reclining fixes stability but rakes the post backward, and depth on
    # the desk is the one thing he actually complained about. Lowering the
    # rail attacks both at once -- less leverage AND less rake. Search for
    # the shallowest bench that survives a 15 N insertion.
    # ------------------------------------------------------------------
    # The tallest module sets a floor on how low the rail can sit: it hangs
    # half its own depth below the rail centreline and must clear the rear
    # deck rail. The board plate is 68 deep ONLY because Pi 4's 49 mm hole
    # spacing needs cruciform arms out to +/-27 -- so Pi 4 support is what is
    # holding the rail high, and holding it high is what makes it tip.
    for tag, s_min in (("keep Pi 4  (plate 68 deep)", 34),
                       ("drop Pi 4  (plate 50 deep)", 26)):
        search(m_f, c_f, DECK, tag, s_min)

    print("\n\nUNTIPPABLE AT ANY FORCE  (tipping arm <= 0, mass irrelevant)")
    print("  tilt  post_y0   rail Y   foot needed behind post   have   verdict")
    for tilt, p in ((20, 112), (30, 112), (42, 112), (42, 100),
                    (42, 95), (42, 90), (45, 90)):
        r = untippable(tilt, 34.0, p, 152.0)
        have = 152.0 - r["rail_y"]
        print(f"  {tilt:3d}    {p:5.0f}   {r['rail_y']:6.1f}        "
              f"{r['overhang_needed']:6.1f} mm          {have:5.1f}   "
              f"{'UNTIPPABLE' if r['safe'] else 'tips'}")
    print("\n  The lever that matters is the gap between the post and the back")
    print("  of the footprint -- not the tilt, and not the mass.")
