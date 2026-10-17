"""The build order of the bench, and the direction each part goes in from.

Pure data, no dependencies: imported by render.py (inside Blender) for the
assemble film and by assembly_fit_check.py (outside, with trimesh) for the
interference test, so the film and the fit check can never disagree about
which way a part travels.

All millimetres, bench coordinates. Every assembled STL carries its seated
position baked into the mesh, so a part's pose during the build is just
seated + vector * (1 - progress).

A rule is (start seconds, fly-in vector, travel seconds). The vector is where
the part comes FROM, relative to seated.
"""

# The way the rail joints close: the long axis of the rail screws, measured
# off the hw_rail meshes by assembly_fit_check.py. NOT the panel tilt -- the
# post face has its own slope (~37 deg from vertical).
POST_N = (0.0, -0.7986, 0.6018)
POST_U = (0.0, 0.6018, 0.7986)        # up the post face


def _along(v, mm):
    return tuple(c * mm for c in v)


# --- out/frame: the order the geometry allows ---------------------------------
# Derived by taking the finished bench apart in software (assembly_fit_check.py
# --order) and reversing it; every move here is then re-checked by the default
# run of that script. What the meshes said, that the old film got wrong:
#   - the bar sockets are open downward: ladder and tie do not drop into
#     standing frames, the frames close onto the bars along x;
#   - the DIN rail does not descend onto the posts, it slides in along x
#     through both frame mortises, over gaskets already in their glands;
#   - the rail screws travel along POST_N, not the panel normal.
FRAME_BUILD = [
    ("asm_ladder", 0.0, (0, 0, 80), 0.9),
    ("asm_tie", 0.8, (0, 0, 80), 0.9),
    ("asm_tray", 1.6, (0, 0, 90), 0.9),
    ("asm_frame_l", 2.6, (-90, 0, 0), 0.9),
    ("asm_frame_r", 2.6, (90, 0, 0), 0.9),
    ("hw_end0", 3.6, (-70, 0, 0), 0.9), ("hw_end1", 3.6, (-70, 0, 0), 0.9),
    ("hw_end2", 3.6, (-70, 0, 0), 0.9), ("hw_end3", 3.6, (70, 0, 0), 0.9),
    ("hw_end4", 3.6, (70, 0, 0), 0.9), ("hw_end5", 3.6, (70, 0, 0), 0.9),
    ("asm_pad", 4.4, _along(POST_N, 45), 0.9),
    ("asm_railbin", 10.8, _along(POST_N, 80), 0.9),      # clip-on: see CLIP_ON
    ("asm_railcap_l", 8.4, (-60, 0, 0), 0.9),
    ("asm_railcap_r", 8.4, (60, 0, 0), 0.9),
    ("asm_rail", 5.2, (-330, 0, 0), 2.2),                # the long slide
    ("hw_rail", 7.6, _along(POST_N, 50), 0.9),
    ("asm_stop", 9.2, (0, 0, 60), 0.9),
    ("asm_sidetray", 9.8, (0, 0, 90), 0.9),
    ("asm_sidebin", 9.8, (0, 0, 90), 0.9),
    ("asm_post", 10.8, _along(POST_N, 80), 0.9),         # clip-on: see CLIP_ON
    # the twist lock is built onto its post on the table and goes on with it
    # (2026-10-17): see CLIP_ON
    ("asm_lock", 10.8, _along(POST_N, 80), 0.9),
    # CrowPanel backplate onto the posts, then the screen onto its bosses,
    # both straight in along the posts' normal (2026-10-15)
    ("asm_backplate", 11.4, _along(POST_N, 60), 0.9),
    ("prop_cp7", 12.0, _along(POST_N, 60), 0.9),
    # the mic crown slides down the backplate's socket from above; its board
    # then tucks under the two fixed lips and clicks past the sprung one, a
    # snap the fit check cannot model (see CLIP_ON) (2026-10-17)
    ("asm_crown", 12.6, _along(POST_U, 70), 0.9),
    ("prop_mic", 13.2, _along(POST_N, 50), 0.9),
    ("prop_", 11.8, (0, 0, 70), 0.9),
]

# Pressed or sealed into a host before the host goes on, so they travel with
# it: TPU feet by thumb with the part upside down in the hand, magnets at the
# print pause or pressed into the caps.
RIDES_WITH = {
    **{f"asm_foot{i}": "asm_tray" for i in (0, 1, 2, 3)},
    **{f"asm_foot{i}": "asm_ladder" for i in (4, 5, 6, 7, 8, 9)},
    **{f"asm_foot{i}": "asm_frame_l" for i in (10, 11)},
    **{f"asm_foot{i}": "asm_frame_r" for i in (12, 13)},
    **{f"asm_foot{i}": "asm_sidebin" for i in (14, 15)},
    **{f"asm_foot{i}": "asm_sidetray" for i in (16, 17)},
    **{f"asm_mag{i}": "asm_sidebin" for i in (0, 1, 2, 3, 4)},
    **{f"asm_mag{i}": "asm_sidetray" for i in (5, 6, 7, 8, 9, 10, 11, 12)},
    **{f"asm_mag{i}": "asm_railcap_l" for i in (13, 15)},
    **{f"asm_mag{i}": "asm_railcap_r" for i in (14, 16)},
}

# Clip modules rock onto the DIN rail and latch. The film moves them in a
# straight line because it has to move them somehow; the fit check skips them.
CLIP_ON = ("asm_post", "asm_railbin", "asm_lock", "prop_mic")

# Parts that go in round a corner, as (first leg, its length mm, way out);
# assembly_fit_check.py walks both legs. (The post keeper that needed one was
# replaced by the twist lock, 2026-10-17.)
DOGLEG = {}

# --- every other --src (console, mountv1, ...): the original cinematic order ---
# First match wins -- keep longer prefixes above their stems.
LEGACY = [
    ("asm_frame_l", 0.0, (-90, 0, 0)),
    ("asm_frame_r", 0.0, (90, 0, 0)),
    ("asm_base", 0.0, (0, 0, 70)),
    ("asm_ladder", 0.8, (0, 0, 80)),
    ("asm_tie", 1.4, (0, 0, 80)),
    ("hw_end", 2.0, (70, 0, 0)),
    ("asm_foot", 2.6, (0, -70, 0)),
    ("asm_tray", 3.2, (0, 90, 0)),
    ("asm_pad", 3.8, (0, -25, 55)),
    ("asm_railbin", 5.6, (0, -40, 75)),
    ("asm_rail", 4.4, (0, -35, 70)),
    ("hw_rail", 5.0, (0, -30, 60)),
    ("asm_screen", 5.6, (0, -40, 75)),
    ("asm_plate", 5.6, (0, -40, 75)),
    ("asm_bin", 5.6, (0, -40, 75)),
    ("asm_sidebin", 6.2, (110, 0, 0)),
    ("asm_dspine", 6.6, (0, -35, 70)),
    ("asm_dupright", 7.0, (0, -50, 95)),
    ("asm_dcross", 7.4, (0, -65, 120)),
    ("prop_hmi", 8.0, (0, -80, 145)),
    ("prop_esp", 8.6, (0, -40, 80)),
    ("prop_eink", 8.6, (0, -40, 80)),
    ("prop_", 8.6, (0, 0, 70)),
    ("w_", 9.2, (0, 0, 60)),
]
ASSEMBLE_DUR = 0.9
DEFAULT_RULE = (0.5, (0, 0, 70), ASSEMBLE_DUR)


def rule_for(name, src="frame"):
    """(start seconds, fly-in vector, travel seconds) for a part."""
    if src == "frame":
        name = RIDES_WITH.get(name, name)
        hit = next((r[1:] for r in FRAME_BUILD if name.startswith(r[0])), None)
        if hit:
            return hit
    return next(((t0, v, ASSEMBLE_DUR) for p, t0, v in LEGACY if name.startswith(p)),
                DEFAULT_RULE)
