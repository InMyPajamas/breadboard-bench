"""Test-fit the whole bench in software before any of it is printed.

Run (needs numpy, trimesh, manifold3d -- see the Mac venv note):
    python cad/assembly_fit_check.py                 seated + build simulation
    python cad/assembly_fit_check.py --seated        seated check only
    python cad/assembly_fit_check.py --order         derive a build order
    python cad/assembly_fit_check.py --src=frame     which out/<src> to load

Two questions, asked of the real exported meshes:

  SEATED  With every part where it ends up, do any two parts occupy the same
          space? Reported as the shared volume and how deep the bite goes.
          Press fits (TPU pads, the rail detent) are MEANT to bite; anything
          else biting is a modelling error that would become a part that
          does not go together.

  BUILD   In build order, can each part travel to its seat along its fly-in
          vector (assembly_sequence.py) without passing through a part that
          is already there? If not, which of the axis directions is free?
          A part with no free direction is trapped: the order is wrong.

It checks geometry, not physics: a 0.25 clearance reads as "clear" whether or
not printed PLA will agree. That is what the gauge plates are for.
"""

import os
import sys

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh

from assembly_sequence import CLIP_ON, DOGLEG, rule_for

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
_src = [a.split("=", 1)[1] for a in ARGS if a.startswith("--src=")]
SRC = os.path.join(HERE, "..", "out", _src[0] if _src else "frame")

EPS_VOL = 0.02          # mm^3: below this a shared volume is facet noise
AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0),
        "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
# Offsets from seated, mm. Dense near the seat, where fits live; coarse after.
STEPS = [0.25, 0.5, 1, 2, 3, 5, 8, 12, 18, 25, 35, 50, 70, 100, 140, 200, 300]


class Part:
    def __init__(self, name, tm):
        self.name = name
        self.tm = tm
        self.lo, self.hi = tm.bounds
        self.solid = Manifold(Mesh(
            vert_properties=np.asarray(tm.vertices, np.float32),
            tri_verts=np.asarray(tm.faces, np.uint32)))
        self.ok = self.solid.status().name == "NoError" and self.solid.volume() > 0
        self.t0, self.vec, _dur = rule_for(name)


def load_parts():
    parts = []
    for fn in sorted(os.listdir(SRC)):
        if fn.endswith(".stl"):
            tm = trimesh.load(os.path.join(SRC, fn), process=True)
            parts.append(Part(fn[:-4], tm))
    return parts


def boxes_touch(a, b, off=(0, 0, 0), pad=0.0):
    lo, hi = a.lo + off, a.hi + off
    return bool(np.all(lo - pad <= b.hi) and np.all(b.lo - pad <= hi))


def shared(a, b, off=(0, 0, 0)):
    """Volume (mm^3) of a, moved by off, that lies inside b."""
    if not boxes_touch(a, b, off):
        return 0.0, None
    moved = a.solid.translate(tuple(float(v) for v in off)) if any(off) else a.solid
    both = moved ^ b.solid
    return both.volume(), both


def bite_depth(both, a, b):
    """How deep the overlap goes. Every point on the overlap's skin lies on one
    part's surface and inside the other, so its depth is the larger of the two
    signed distances; the bite is the deepest such point."""
    m = both.to_mesh()
    v = np.asarray(m.vert_properties, float)[:, :3]
    if len(v) == 0:
        return 0.0
    if len(v) > 3000:
        v = v[np.random.default_rng(0).choice(len(v), 3000, replace=False)]
    da = trimesh.proximity.signed_distance(a.tm, v)      # + = inside
    db = trimesh.proximity.signed_distance(b.tm, v)
    return float(max(np.maximum(da, db).max(), 0.0))


def seated_check(parts):
    print(f"\nSEATED: {len(parts)} parts, every pair whose boxes touch\n")
    hits = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if a.name.startswith("prop_") and b.name.startswith("prop_"):
                continue        # the breadboard model's own hole pattern
            vol, both = shared(a, b)
            if vol > EPS_VOL:
                hits.append((vol, bite_depth(both, a, b), a.name, b.name))
    hits.sort(reverse=True)
    for vol, depth, an, bn in hits:
        print(f"  {an:16s} x {bn:16s} shares {vol:9.2f} mm^3   bite {depth:5.2f} mm")
    print(f"\n  {len(hits)} pairs share volume")
    return hits


def travel_clash(p, placed, vec, seated_vol):
    """Worst extra overlap while p travels in along vec, vs. parts already in.
    Extra = beyond what the same pair shares once seated (a press fit bites at
    rest, and must not count against the path)."""
    unit = np.asarray(vec, float)
    unit /= np.linalg.norm(unit)
    worst = (0.0, None, 0.0)
    for s in STEPS:
        off = unit * s
        for q in placed:
            vol, _ = shared(p, q, off)
            extra = vol - seated_vol.get((p.name, q.name), 0.0)
            if extra > max(worst[0], EPS_VOL):
                worst = (extra, q.name, s)
    return worst


# CLIP_ON (assembly_sequence): clip modules rock onto the DIN rail and latch; no
# straight line puts them on or takes them off, so this test cannot judge them.
SOFT = ("asm_pad", "asm_foot")          # TPU 95A: gives under a passing part
# mm^3 of squeeze, beyond the seated fit, that TPU gives under a thumb. Set from
# the 2026-09-19 run: the one designed case (rail riding over its gaskets) is
# 1.96, the nearest wrong one (a frame dragged across the pad in its own
# pocket) is 42.6, and a pad pushed through a wall is 110-390.
SOFT_SQUEEZE = 5.0


def counts_as_blocking(mover, blocker, extra_mm3):
    """Does this much extra overlap, met on the way in, really stop the part?

    Rigid on rigid: any overlap at all is a collision. TPU is different -- the
    rail is MEANT to ride over gaskets standing 0.35 proud, squeezing them as
    it passes -- so a soft part only blocks once the squeeze is more than a
    thumb could supply. The limit is the same whichever of the two is moving:
    the rubber is displaced by the same amount either way.
    """
    if mover.startswith(SOFT) or blocker.startswith(SOFT):
        return extra_mm3 > SOFT_SQUEEZE
    return True


def blockers(p, others, vec, seated_vol):
    """{part: worst extra overlap, mm^3} for everything p passes through on
    its way out along vec. Extra = beyond what the pair shares once seated."""
    unit = np.asarray(vec, float)
    unit /= np.linalg.norm(unit)
    found = {}
    for s in STEPS:
        off = unit * s
        for q in others:
            vol, _ = shared(p, q, off)
            extra = vol - seated_vol.get((p.name, q.name), 0.0)
            if extra > max(EPS_VOL, found.get(q.name, 0.0)):
                found[q.name] = extra
    return found


def derive_order(parts, hits):
    """Assembly by disassembly: take the finished bench apart one free part at
    a time. Whatever comes off along a clear straight line, with everything
    else still in place, could have gone on that way; the reverse of the
    removal order is a build order the geometry allows. Parts left when
    nothing more comes free are interlocked -- no straight-line build exists
    for them, which is a design finding, not a film problem."""
    # Directions: the six axes, plus every slope the design actually uses.
    # Those are read off the screws rather than assumed -- a screw's long axis
    # IS the way its joint closes (the rail screws sit at ~37 deg, not on the
    # panel tilt), and the cross-slope direction is how a part slides along it.
    dirs = dict(AXES)
    for p in parts:
        if p.name.startswith("hw_"):
            v = p.tm.vertices - p.tm.vertices.mean(0)
            ax = np.linalg.svd(v, full_matrices=False)[2][0]
            if np.abs(ax).max() < 0.999 and not any(
                    abs(abs(np.dot(ax, d)) - 1) < 1e-3 for d in dirs.values()):
                ax = ax if ax[2] > 0 else -ax
                slope = np.cross((1, 0, 0), ax)
                k = len(dirs) // 4
                dirs.update({f"+screw{k}": tuple(ax), f"-screw{k}": tuple(-ax),
                             f"+slope{k}": tuple(slope), f"-slope{k}": tuple(-slope)})
    seated_vol = {}
    for vol, _d, an, bn in hits:
        seated_vol[(an, bn)] = seated_vol[(bn, an)] = vol
    real = [p for p in parts if not p.name.startswith("prop_")]
    print(f"\nORDER: {len(real)} printed parts and screws, {len(dirs)} directions each\n")
    clips = sorted(p.name for p in real if p.name.startswith(CLIP_ON))
    real = [p for p in real if not p.name.startswith(CLIP_ON)]
    raw = {p.name: {k: blockers(p, [q for q in real if q is not p], v, seated_vol)
                    for k, v in dirs.items()} for p in real}
    block = {n: {k: {q for q, extra in found.items() if counts_as_blocking(n, q, extra)}
                 for k, found in by_dir.items()} for n, by_dir in raw.items()}
    # A captive magnet travels with the part it is sealed or pressed into:
    # its host is whatever hems it in from the most directions. Host and
    # magnets move as one, so they never count as blocking each other.
    group = {p.name: {p.name} for p in real}
    for p in real:
        if p.name.startswith("asm_mag"):
            votes = {}
            for b in block[p.name].values():
                for q in b:
                    if not q.startswith(("asm_mag", "hw_")):
                        votes[q] = votes.get(q, 0) + 1
            if votes:
                host = max(votes, key=votes.get)
                group[host].add(p.name)
                group[p.name] = group[host]
    for host, g in sorted(group.items()):
        if len(g) > 1 and not host.startswith("asm_mag"):
            print(f"  {host} carries {len(g) - 1} magnets")
    print()
    left, rounds = {p.name for p in real}, []
    while left:
        free = {}
        for n in sorted(left):
            if n.startswith("asm_mag") and len(group[n]) > 1:
                continue                    # rides with its host
            ways = [k for k in dirs
                    if not (set().union(*(block[m][k] for m in group[n])) - group[n]) & left]
            if ways:
                free[n] = ways
        if not free:
            break
        rounds.append(free)
        for n in free:
            left -= group[n]
    for i, free in enumerate(reversed(rounds), 1):
        print(f"  step {i}")
        for n, ways in free.items():
            print(f"    {n:16s} goes in from {', '.join(ways)}")
    if clips:
        print(f"  last, by hand (clip-on, not a straight-line move, NOT checked): {', '.join(clips)}")
    # What the soft-part rule waved through, so the rule can be judged.
    used = {}
    for free in rounds:
        for n, ways in free.items():
            for m in group[n]:
                for q, extra in raw[m][ways[0]].items():
                    if q not in group[n] and not counts_as_blocking(m, q, extra):
                        used[(m, q)] = max(used.get((m, q), 0.0), extra)
    if used:
        print("\n  TPU squeezed in passing (allowed by counts_as_blocking):")
        for (m, q), extra in sorted(used.items(), key=lambda kv: -kv[1]):
            print(f"    {m:16s} past {q:16s} {extra:7.2f} mm^3 extra")
    if left:
        print("\n  INTERLOCKED -- no straight-line way in or out:")
        for n in sorted(left):
            if n.startswith("asm_mag") and len(group[n]) > 1:
                continue
            stuck = {k: (set().union(*(block[m][k] for m in group[n])) - group[n]) & left
                     for k in dirs}
            k = min(stuck, key=lambda d: len(stuck[d]))
            print(f"    {n:16s} best try {k} still blocked by {', '.join(sorted(stuck[k]))}")
    else:
        print("\n  every part has a clear straight-line path: a valid build order exists")


def dogleg_blockers(p, others, dog, seated_vol):
    """blockers() for a part that comes out round a corner: along the first
    leg for its length, then from there straight out along the second."""
    leg1, length, leg2 = dog
    u1 = np.asarray(leg1, float) / np.linalg.norm(leg1)
    u2 = np.asarray(leg2, float) / np.linalg.norm(leg2)
    offs = [u1 * s for s in np.arange(0.25, length + 1e-6, 0.25)]
    offs += [u1 * length + u2 * s for s in STEPS]
    found = {}
    for off in offs:
        for q in others:
            vol, _ = shared(p, q, off)
            extra = vol - seated_vol.get((p.name, q.name), 0.0)
            if extra > max(EPS_VOL, found.get(q.name, 0.0)):
                found[q.name] = extra
    return found


def build_check(parts, hits):
    """Play the film's own sequence (assembly_sequence.FRAME_BUILD) and test
    every move against the parts that are already in when it happens."""
    seated_vol = {}
    for vol, _d, an, bn in hits:
        seated_vol[(an, bn)] = seated_vol[(bn, an)] = vol
    order = sorted(parts, key=lambda p: p.t0)
    print("\nBUILD: each part along its film vector, against parts already in\n")
    bad = 0
    for p in order:
        if p.name.startswith(CLIP_ON):
            print(f"  {p.name:16s} clip-on module: rocks onto the rail, NOT checked")
            continue
        # Parts that start together travel together (feet and magnets ride in
        # their host), so only what arrived earlier can be in the way.
        placed = [q for q in order if q.t0 < p.t0]
        dog = next((v for k, v in DOGLEG.items() if p.name.startswith(k)), None)
        if dog:
            found = dogleg_blockers(p, placed, dog, seated_vol)
        else:
            found = blockers(p, placed, p.vec, seated_vol)
        hard = {q: e for q, e in found.items() if counts_as_blocking(p.name, q, e)}
        soft = {q: e for q, e in found.items() if q not in hard}
        vec = "(" + ", ".join(f"{c:.0f}" for c in p.vec) + ")"
        if hard:
            bad += 1
            worst = max(hard, key=hard.get)
            print(f"  {p.name:16s} from {vec:16s} COLLIDES with {worst} "
                  f"({hard[worst]:.1f} mm^3){' and ' + str(len(hard) - 1) + ' more' if len(hard) > 1 else ''}")
        elif soft:
            worst = max(soft, key=soft.get)
            print(f"  {p.name:16s} from {vec:16s} clear; squeezes TPU {worst} by {soft[worst]:.2f} mm^3")
        else:
            print(f"  {p.name:16s} from {vec:16s} clear")
    print(f"\n  {bad} moves collide" if bad else "\n  EVERY MOVE IN THE FILM IS CLEAR")


if __name__ == "__main__":
    parts = load_parts()
    bad = [p.name for p in parts if not p.ok]
    if bad:
        print("not closed solids, skipped:", ", ".join(bad))
    parts = [p for p in parts if p.ok]
    hits = seated_check(parts)
    if "--order" in ARGS:
        derive_order(parts, hits)
    elif "--seated" not in ARGS:
        build_check(parts, hits)
