"""Bambu Studio plate projects -- one .3mf per stage of the staged pilot build.

The build plan already says what goes on each plate and at what settings, but
it said it only as prose in bench-hub.html. That left every plate a manual
arrange-and-retype in Bambu Studio, and retyping is exactly where the per-part
table gets lost: the stock `0.20mm Standard @BBL H2S` process resolves to
wall_loops 2 with brim_type unset, so a plate loaded as bare STLs prints the
structural DIN rail at two walls and the deck ladder with no brim -- the two
defaults the print review called out by name.

Each .3mf written here carries:

  * the H2S 0.4 machine profile, the 0.20mm Standard process and the plate's
    filament, resolved through their `inherits` chains the same way Bambu
    Studio resolves them out of resources/profiles/BBL;
  * every part already rotated into the print pose check.py gates it in. The
    poses are read out of check.py's own PRINT_POSE with ast, never retyped,
    so a pose cannot drift between the printability gate and the plate that
    actually gets printed;
  * per-object wall / infill / brim overrides wherever parts on one plate
    disagree -- plate 4 alone carries three regimes (3/15 frame, 4/25 tie,
    3/100 caps);
  * a shelf-packed arrangement with the brim allowance already in the gaps.

The override direction is deliberate. A plate's own process is set to the most
demanding STRUCTURAL setting on it and per-object metadata only relaxes or
specialises from there, so if Studio ever ignored an object override the part
would come out over-built rather than under-built. 100% infill parts (the
magnet caps) are excluded from that maximum -- they are 0.7 g each and would
otherwise drag a whole plate to solid.

Clip modules get support_type normal(manual): supports enabled but generated
ONLY where painted. That is the mechanism behind "two dabs, never global
supports" -- with support disabled outright, a painted enforcer does nothing.

The dabs CAN be carried: Studio stores support paint as a per-triangle
attribute, paint_supports="4" (enforcer), and reads it back from a plain 3mf.
PAINT below names the faces per part and build() writes them, so plate 03
arrives pre-painted (proved 2026-10-04 by slicing through the CLI and finding
support under the four clips' teeth and tabs and nowhere else). The plate 09
modules are not in PAINT yet and still say so on their cards. The one thing a
.3mf still cannot carry is the Z = 3.2 magnet pause on stage 9.

    python cad/plates.py            # -> out/plates/*.3mf and out/plates/PLATES.md
    python cad/plates.py --verify   # ...then slice every plate through Studio's CLI
"""
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, datetime

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
DEST = os.path.join(OUT, "plates")
def _profiles():
    """Bambu Studio's BBL profile tree. Studio keeps an updated copy of the
    system profiles in its user-data folder and loads that in preference to
    the set shipped inside the app, so look there first, on either platform."""
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, "Library", "Application Support", "BambuStudio", "system", "BBL"),
        "/Applications/BambuStudio.app/Contents/Resources/profiles/BBL",
        os.path.join(os.environ.get("APPDATA", ""), "BambuStudio", "system", "BBL"),
        r"C:\Program Files\Bambu Studio\resources\profiles\BBL",
    ]
    for c in cands:
        if os.path.isfile(os.path.join(c, "machine", MACHINE + ".json")):
            return c
    raise SystemExit("Bambu Studio profiles not found; looked in:\n  " + "\n  ".join(cands))



MACHINE = "Bambu Lab H2S 0.4 nozzle"
# The two-filament config every PETG + PLA plate and project takes whole: the
# user's GUI-saved plate 09 (2026-10-09), copied with its account id blanked so
# it can live in the public repo. Studio's GUI rejects such a config written
# from scratch; edit values in it, never its structure.
TEMPLATE_2F = "ref/templates/h2s_petg_hf_pla_basic.3mf"
PROCESS = "0.20mm Standard @BBL H2S"
# PLA is Matte, not Basic (2026-09-19): that is the black the user has in
# quantity -- the structure slices to ~204 g and only ~70 g of Basic is on
# hand. Same 220/55 and 0.98 flow as Basic, so fits carry over; what changes
# is density (1.32 vs 1.26), a 100% minimum fan, and Bambu's own figure for
# layer-to-layer impact strength, 6.6 against Basic's 13.8 -- which is why
# the pilot_block result on plate 02 is the go/no-go for self-tapped pilots.
FILAMENT = {"PLA": "Bambu PLA Matte @BBL H2S",
            "PETG": "Bambu PETG HF @BBL H2S",
            "TPU": "Bambu TPU for AMS @BBL H2S"}   # the roll actually on hand (68D, AMS-fed) -- not 95A
BBL = _profiles()

# The spools on the shelf, so Studio's AMS mapping proposes the right slot:
# black Matte PLA, red TPU. PETG is still open (black, white or translucent).
COLOUR = {"PLA": "#161616", "PETG": "#3F4550", "TPU": "#C8261C"}

BED = (340.0, 320.0)     # printable_area of the H2S 0.4 -- not the 350 in README
EDGE = 14.0              # keep-out from the plate edge

# Preset bookkeeping that must not survive into a project config. Studio's
# loader reads the header keys (name, version, description, filament_id, ...)
# as bare strings before it looks anything up, so a header key that arrives
# as a vector -- which every filament key becomes below -- aborts the load
# with "type must be string, but is array" and the project never opens.
DENY = {"from", "inherits", "include", "instantiation", "name", "setting_id",
        "type", "version", "description", "filament_id",
        "compatible_printers", "compatible_printers_condition",
        "compatible_prints", "compatible_prints_condition",
        "filament_settings_id", "print_settings_id", "printer_settings_id"}

# --- per-part print regime: walls, infill, brim -----------------------------
# Straight out of the README's per-part slicer table and the build plan's
# stage notes. rail_stub and pilot_block deliberately carry the DIN rail's
# regime rather than a gauge regime: a stub printed at 3/15 cannot predict a
# rail printed at 5/25, which is the whole reason the stub exists.
PART = {
    "end_frame":            (3, "15%", False),
    "end_frame_r":          (3, "15%", False),
    "deck_ladder":          (3, "15%", False),  # no brim: the user's call, 2026-10-06
    "rear_tie":             (4, "25%", False),  # no brim: the user's call, 2026-10-06
    # No brim since the rail went lips-down: a brim would weld to the lip
    # edge -- the 34.85 width every clip closes over -- and the flipped rail
    # has 9,100 mm2 on the bed without one.
    "din_rail":             (5, "25%", False),
    "rear_tray":            (4, "15%", False),
    "rail_cap":             (3, "100%", False),
    "side_bin":             (3, "15%", False),
    "side_tray":            (3, "15%", False),
    "deck_stop":            (3, "15%", False),
    "rail_bin":             (3, "15%", False),
    # flat now (2026-10-17): 4 walls run the post's length -- in bending
    # they are most of its strength -- and 30 x 144 on the bed needs no brim
    "display_post":         (4, "40%", False),
    "display_lock":         (4, "100%", False),  # tooth, shaft and prongs: solid
    "display_lock_knob":    (4, "100%", False),
    "din_tilt_base":        (4, "40%", False),
    "din_tilt_arm":         (4, "40%", False),
    "din_tilt_knob":        (4, "100%", False),
    # 4 walls: the bolted bosses' ring round the nut pocket (1.7) and round
    # the bore (3.3) close up solid instead of a 25% core (2026-10-17)
    "display_backplate":    (4, "25%", False),
    # a 3.7 plate with the lip columns and pins standing on it: 4 walls make
    # the thin features solid; flat 108 x 123 on the bed needs no brim
    "mic_crown":            (4, "40%", False),
    "fit_coupon_frame":     (3, "15%", False),   # 12,000 mm2 of contact: no brim needed
    "rail_stub":            (5, "25%", False),
    "half_bay_gauge":       (3, "15%", False),
    "ladder_station_stub":  (3, "15%", False),
    "deck_pair":            (3, "15%", False),
    "tooth_gauge":          (3, "15%", False),
    "tooth_rider_1":        (3, "15%", False),
    "tooth_rider_2":        (3, "15%", False),
    "tooth_rider_3":        (3, "15%", False),
    "slot_gauge_1":         (3, "15%", False),
    "slot_gauge_2":         (3, "15%", False),
    "slot_gauge_3":         (3, "15%", False),
    "cradle_gauge_1":       (3, "15%", False),
    "cradle_gauge_2":       (3, "15%", False),
    "cradle_gauge_3":       (3, "15%", False),
    "span_gauge_1":         (3, "15%", False),
    "span_gauge_2":         (3, "15%", False),
    "span_gauge_3":         (3, "15%", False),
    "span_gauge_slot":      (3, "15%", False),
    "ledge_gauge":          (3, "15%", False),
    "cal_target":           (3, "15%", False),
    "cal_step5":            (3, "15%", False),
    "cal_step20":           (3, "15%", False),
    "peg_gauge":            (3, "15%", False),
    "pilot_block":          (5, "25%", False),
    "pilot_block_oring":    (5, "25%", False),
    "foot_gauge":           (3, "15%", False),
    "foot_gauge_v2":        (3, "15%", False),
    "spigot_stub":          (3, "15%", False),
    "tie_stub":             (3, "15%", False),
    "rail_cap_615":         (3, "100%", False),
    "rail_cap_625":         (3, "100%", False),
    "rail_cap_635":         (3, "100%", False),
    "fit_clips_petg":       (3, "15%", False),
    "magnet_gauge":         (3, "15%", False),
    "clip_test_18":         (3, "15%", False),
    "clip_test_20":         (3, "15%", False),
    "skin_coupon_open":     (3, "15%", False),
    "skin_coupon_045":      (3, "15%", False),
    "skin_coupon_065":      (3, "15%", False),
    "skin_coupon_085":      (3, "15%", False),
    "foot_pad":             (3, "100%", False),
    "foot_pad_006":         (3, "100%", False),
    "foot_pad_012":         (3, "100%", False),
    "foot_pad_018":         (3, "100%", False),
    "rail_pad":             (3, "100%", False),
    "tpu_block":            (3, "100%", False),
}

SRC_DIRS = ["stl_frame", "stl_coupon", "stl"]

# Settings Bambu Studio has but the BBL preset chain never spells out, so they
# arrive from Studio's compiled-in defaults rather than from any JSON. brim_type
# is the one that matters: unset it reads as auto_brim, and the print review
# proved auto_brim declines the brims the long parts depend on. Seeding the
# default here is what lets apply() below reject a genuinely misspelt key
# without also rejecting a real setting that simply has no preset entry.
# brim_object_gap 0.2, not Bambu's 0.1: at 0.1 the brim fuses to the part's
# first layer, and tearing it off lifts the bottom layers at the edge with it
# (the user's plate 02 experience). At 0.2 it still pins the corners of the
# long bars down but lets go in one piece. Kept only on the ladder, the tie
# and the tall PETG posts -- long thin parts and a tower; nothing else.
EXTRA_DEFAULTS = {"brim_type": "auto_brim"}
# Applied to every plate AFTER the stock snapshot is taken, never in
# base_config(): a key set before the snapshot looks like stock to
# mark_modified(), stays off `different_settings_to_system`, and Studio's
# window then quietly reloads the preset's value over it.
PLATE_DEFAULTS = {"brim_object_gap": "0.2"}

# --- the plates -------------------------------------------------------------
# `objects` is the build plan's file list verbatim. `process` is what this
# plate needs on top of the resolved 0.20mm Standard. `hand` is everything a
# .3mf cannot express and a human therefore has to do in Studio.
PLATES = [
    dict(n="01", slug="tpu_regime", stage=1, mat="TPU", gap=6.0,
         title="TPU regime and every pad",
         proves="FOOT_FIT, and how much TPU for AMS actually over-prints here.",
         objects=[("tpu_block", 1), ("foot_pad_006", 2), ("foot_pad_012", 2),
                  ("foot_pad_018", 2), ("foot_pad", 4)],
         process=dict(initial_layer_print_height="0.24", outer_wall_speed="30",
                      inner_wall_speed="40", top_shell_layers="4",
                      bottom_shell_layers="4"),
         filament=dict(filament_retraction_length="0.4"),
         hand=["Rail gaskets retired 2026-10-05: the four printed TPU rail pads"
               " this plate carried are replaced by eight bought 3 x 1 O-rings"
               " (plate 02c). The plate is printed history; the pads are gone"
               " from the build so the record stays and the object goes.",
               "Run the roll through the AMS in the OUTERMOST slot -- shortest,"
               " straightest PTFE run.",
               "Chamber heater OFF. Nothing on this plate wants heat soak.",
               "No brim: on a 6 mm-wide pad a brim is worse than none."]),

    dict(n="02", slug="pla_gauges", stage=2, mat="PLA", gap=10.0,
         title="PLA gauges",
         proves="Every PLA fit in the build, on 3-53 g parts instead of 21-87 g.",
         objects=[("fit_coupon_frame", 1), ("rail_stub", 1),
                  ("ladder_station_stub", 1), ("pilot_block", 1),
                  ("foot_gauge", 1), ("spigot_stub", 1), ("tie_stub", 1),
                  ("rail_cap_615", 1), ("rail_cap_625", 1), ("rail_cap_635", 1)],
         process=dict(),
         hand=["rail_stub and pilot_block are set to the DIN rail's 5 walls /"
               " 25% on purpose -- a stub in the gauge regime cannot predict"
               " the rail.",
               "Write every measured number down before slicing anything in"
               " stage 4."]),

    dict(n="02b", slug="stub_and_foot_gauge", stage=2, mat="PLA", gap=10.0,
         title="Plate 02 follow-up: rail stub lips-down, foot gauge v2",
         proves="That the flipped pose prints a clean lip: plate 02's stub "
                "printed web-down and sagged strands off both lips.",
         objects=[("rail_stub", 1), ("foot_gauge_v2", 1)],
         process=dict(),
         hand=["FOOT GAUGE v2: no pad of the 006/012/018 trio would enter v1's"
               " 16.00 x 6.00 pockets, so the pocket is the variable. Five"
               " pockets, +0.10 to +0.50 on length and width, tagged 1-5"
               " dimples. Test with a PRODUCTION pad (caliper it: 16.24 x"
               " 6.24), groove in, thumb only, then invert and shake. The"
               " winner is the smallest pocket that passes both.",
               "RAIL STUB: lips on the bed, web up. No support, no brim.",
               "Caliper the lip band before the slot test: 34.85 wide, 1.20"
               " thick, the same at both ends and the middle.",
               "Then rerun test 2 (rail slots), and keep this stub for the"
               " stage 3 clips -- they hook the same lips."]),

    dict(n="02l", slug="half_bay_gauge", stage=2, mat="PLA", gap=10.0,
         title="Half-bay gauge: the small board's 100 mm of the real ladder",
         proves="That the half board drops into ITS bay: datum pocket and peg"
                " at 198.19, slot at 251.70, the rear shoulder stepped out 0.8"
                " for the narrower board. Cut from frame.py's deck_ladder, so"
                " it is exactly what plate 07 prints there.",
         objects=[("half_bay_gauge", 1)],
         edge=12.0,
         process=dict(seam_position="back"),
         hand=["Drop the HALF board straight down: one tab into the exact"
               " pocket near the left end of the gauge, the other into the"
               " slot, its notch over the peg on the far rail. Do not slide.",
               "Pass: rim down on the shelf both sides, no rock, about 0.4 of"
               " play across, a shove along the rail meets the pocket wall.",
               "If it sits off-centre along the rail that is the unmeasured"
               " end-to-cleat distance, not a fault; note which way and how far.",
               "Lies along Y with Seam position = Back, like the ladder."]),

    dict(n="02r", slug="rail_stub_clip_target", stage=2, mat="PLA", gap=10.0,
         title="Rail stub on its own: the clip target for plate 03",
         proves="Nothing new: a fresh 40 mm slice of the real DIN rail to snap"
                " plate 03's clips onto. The 02b stub was thrown away.",
         objects=[("rail_stub", 1)],
         process=dict(),
         hand=["Lips on the bed, web up. No support, no brim. About 15 minutes.",
               "It carries the rail's new M3 cap-head counterbores at one end;"
               " they are irrelevant to the clip test.",
               "Hook each plate 03 clip over one lip and rock it down. One clip"
               " at a time: the stub is 40 long and a clip is 30 wide."]),

    dict(n="02c", slug="oring_pilot_block", stage=2, mat="PLA", gap=10.0,
         title="O-ring rail gasket test",
         proves="Whether a 3 x 1 mm O-ring around each rail screw can replace"
                " the printed TPU gasket, and how deep its gland must be: the"
                " TPU on hand (TPU for AMS, ~68D) is too hard to squash.",
         objects=[("pilot_block_oring", 1)],
         process=dict(),
         hand=["Station 1 (one dimple): gland 0.80 deep, 20% squeeze. Station"
               " 2 (two dimples): 0.70 deep, 30%.",
               "One 3 x 1 O-ring flat in the gland around each pilot, the"
               " rail_stub from plate 02b over them, two M3x16 csk driven"
               " alternately by hand.",
               "Pass: the stub's web pulls down flat (0.05 feeler will not"
               " enter), backing one screw out a turn lifts the web, and the"
               " pilots still bite after three cycles. The winner becomes"
               " RAIL_PAD_D in frame.py."]),

    dict(n="02d", slug="deck_pair", stage=2, mat="PLA", gap=10.0,
         title="Two deck stations, and the stops to hold a board",
         proves="Whether a board sits FLAT across two supports, and whether the"
                " ladder's 2 mm indexing teeth catch a deck stop at all -- they"
                " print as a ~0.4 mm ripple because their tips are thinner than"
                " one extrusion line.",
         objects=[("deck_pair", 1)],
         process=dict(),
         hand=["Deck stops retired 2026-09-23: the board's own cleats locate it"
               " now (plates 02e-02k). This plate is printed history; its stops"
               " are gone from the build so the record stays and the object goes.",
               "deck_pair is the real deck_ladder trimmed to its first two"
               " stations (plates centred 51 and 141), so every tooth and ledge"
               " is exactly what plate 07 will print.",
               "The deck stops are PETG in the real build; printed here in PLA"
               " on purpose, to avoid a material swap. Tooth engagement is what"
               " is being tested, not the clip's flex.",
               "Set a full-size board across both stations: it must sit flat"
               " with no rock. Then push a stop along the strip -- you should"
               " feel a step every 2 mm and it should resist a shove.",
               "If the stop slides freely, the teeth need redrawing before"
               " plate 07, or replacing with sockets for the board's own"
               " cleats (4.42 wide, 2.09 proud, about 65 mm apart)."]),

    dict(n="02e", slug="tooth_gauge", stage=2, mat="PLA", gap=8.0,
         title="Tooth gauge: how blunt does a tooth need to be?",
         proves="Plate 02d's teeth barely catch and barely stand up. Same 2.0"
                " pitch and 0.9 depth on all three strips; only the flat on"
                " top of each tooth changes.",
         objects=[("tooth_gauge", 1), ("tooth_rider_1", 1),
                  ("tooth_rider_2", 1), ("tooth_rider_3", 1)],
         process=dict(),
         hand=["1 dot = flat 0.0, the profile drawn today (the control)."
               " 2 dots = 0.6, about 1.4 extrusion lines across the tip."
               " 3 dots = 0.9, about 2.1 lines.",
               "Each rider is the negative of its OWN strip, with the same 0.1"
               " clearance frame.py uses. Match the dimples: rider 2 on strip"
               " 2.",
               "Slide each rider along its strip. You want a felt step every"
               " 2 mm, a rider that resists a shove, and teeth that do not"
               " fold over when you push sideways on them.",
               "The winner becomes TOOTH_TOP in frame.py. Both halves of the"
               " real joint call teeth(), so one change fixes the ladder and"
               " the deck stop together."]),

    dict(n="02f", slug="slot_gauge", stage=2, mat="PLA", gap=8.0,
         title="Slot gauge: slide the board in by its own tab",
         proves="Whether a slot down the rail can replace the indexing teeth"
                " entirely. The board's edge tab slides in and the slot's ROOF"
                " stops it lifting -- a 5.2 mm feature doing the work instead"
                " of a 0.9 mm tooth that prints short and folds.",
         objects=[("slot_gauge_1", 1), ("slot_gauge_2", 1), ("slot_gauge_3", 1)],
         process=dict(),
         hand=["Slot heights against a 5.20 tab: 1 dot 5.4, 2 dots 5.6,"
               " 3 dots 5.8. Depth is 2.5 on all three against a 2.09 tab.",
               "Slide a board's TAB edge into each from the end -- it cannot"
               " be dropped in from above, that is the whole point.",
               "Wanted: slides without forcing, no slop up and down, and the"
               " board cannot be lifted out. Then hold the gauge and let the"
               " board hang from it -- does the slot carry it?",
               "The winner sets the slot height for deck_rail. Tab spacing"
               " does not matter: the slot runs the full length, so the board"
               " can stop anywhere."]),

    dict(n="02g", slug="cradle_gauge", stage=2, mat="PLA", gap=8.0,
         title="Cradle gauge: drop the board in by its own tab and notch",
         proves="The gap between the rails, for a board that DROPS IN rather"
                " than slides: one rail carries an open pocket its tab falls"
                " into, the other a peg that falls into the notch opposite.",
         objects=[("cradle_gauge_1", 1), ("cradle_gauge_2", 1),
                  ("cradle_gauge_3", 1)],
         process=dict(),
         hand=["One station each. Gaps against the board's 54.74 plain width:"
               " 1 dot 54.94, 2 dots 55.14, 3 dots 55.34.",
               "Drop a board straight down into each, lining the tab up with"
               " the open pocket and the notch with the peg.",
               "Wanted: drops in without forcing, does not rattle sideways,"
               " and cannot slide along once seated.",
               "Neither feature holds the board DOWN -- both locate it and"
               " gravity does the rest. Judge whether that is enough.",
               "The winner sets the rail gap. Then a skeletal full-length"
               " piece checks that two or three stations line up at once."]),

    dict(n="02h", slug="span_gauge", stage=2, mat="PLA", gap=8.0,
         title="Span gauge, and how wide a peg the notch will take",
         proves="Which station spacing the board's tabs really sit at. With"
                " discrete pockets this decides everything -- a pocket is 4.37"
                " wide, so 2 mm out and the second tab misses. Only a photo"
                " estimate of 69-71 exists.",
         objects=[("peg_gauge", 1)],
         process=dict(),
         hand=["PRINTED 2026-09-20, and its span strips were WRONG -- all four"
               " bracketed 68.58 to 72.39 when the board's cleats sit at about"
               " 66.04. They have been re-cut on plate 02i. Only peg_gauge"
               " remains here, and its answer stands: PEG_W = 3.8.",
               "Drop the board's TAB edge onto each strip. Only the one whose"
               " spacing matches will take both tabs at once; the others will"
               " seat one and miss the other.",
               "If two strips both take it, the board has slop -- say which"
               " felt tighter.",
               "Nothing but two pads and a spine on purpose: the least"
               " material that can hold two pockets a fixed distance apart.",
               "peg_gauge rides along: five pegs 3.2 to 4.0 wide, 1 to 5"
               " dimples. Lower a board's NOTCH edge onto each. The widest"
               " that drops in cleanly is the peg width -- and it shows where"
               " the notch's mouth really is, which is the one dimension on"
               " that side still being assumed."]),

    dict(n="02i", slug="cleat_rework", stage=2, mat="PLA", gap=8.0,
         title="Cleat rework: the fixed cradle, and the span re-cut to 66.04",
         proves="Everything still open on board retention, on one plate."
                " 02g's cradles were severed by their own tape relief and"
                " printed as two loose rails; 02h's spans were all too wide,"
                " bracketing 68.58-72.39 when the board sits at 66.04.",
         objects=[("cradle_gauge_1", 1), ("cradle_gauge_2", 1),
                  ("cradle_gauge_3", 1), ("span_gauge_1", 1),
                  ("span_gauge_2", 1), ("span_gauge_3", 1),
                  ("span_gauge_slot", 1)],
         process=dict(),
         hand=["This plate replaces 02g and 02h. Do not print either of those:"
               " 02g was severed, 02h's spacing was wrong.",
               "CRADLES, 1 to 3 dots: rail gaps 54.94 / 55.14 / 55.34 against"
               " the board's 54.74 plain width. Drop a board straight down,"
               " tab into the open pocket, notch onto the peg. The tightest"
               " one that seats flush without rattling sets the rail gap.",
               "Each cradle is now ONE piece. The first version cut its tape"
               " relief the full depth of the floor, which severed the two"
               " rails, and trimesh's is_watertight passed it because two"
               " disjoint closed solids are each watertight.",
               "SPANS, 1 to 3 dots: 64.77 / 66.04 / 67.31, half a hole pitch"
               " apart, bracketing the measured 66.13. The board has THREE"
               " cleats per edge at about 66, not two at about 71.",
               "span_gauge_slot is the production candidate and has no dots:"
               " its first pocket is exact, its second is slotted 63.04 to"
               " 69.04. One pocket locates, the other only stops rotation, so"
               " a spacing error stops mattering. Notches across its top face"
               " mark every half hole pitch -- read off where the second tab"
               " lands and that IS the spacing, no caliper needed.",
               "If the slotted one seats easily and a graded one does not,"
               " that settles the design: slot the second pocket and stop"
               " chasing the constant."]),

    dict(n="02j", slug="span_recut", stage=2, mat="PLA", gap=8.0,
         title="Span, re-cut to the calipered 65.21",
         proves="The last open constant. 02i's spans were cut around 66.04,"
                " off a photo; the caliper says 65.21, so none of them could"
                " fit. These bracket the real number 0.5 mm apart.",
         objects=[("span_gauge_1", 1), ("span_gauge_2", 1),
                  ("span_gauge_3", 1), ("span_gauge_slot", 1)],
         process=dict(),
         hand=["Pocket centres: 1 dot 64.71, 2 dots 65.21 (the caliper"
               " reading), 3 dots 65.71. Half a millimetre apart, because a"
               " pocket only has 0.3 of slack -- a coarser step cannot tell"
               " the right answer from a near miss.",
               "Drop the board's TAB edge straight down so both tabs go for"
               " both pockets at once. Do not slide it along.",
               "span_gauge_slot has no dots and is the production candidate:"
               " its first pocket is exact, its second slotted 62.21 to 68.21."
               " One pocket locates the board, the other only stops it"
               " rotating, so a spacing error is absorbed rather than jamming"
               " the first tab.",
               "Notches across the slotted pad's top face mark every half hole"
               " pitch; the deep one is 65.21. Where the second tab lands IS"
               " the spacing -- read it off instead of calipering again.",
               "If the slotted strip seats and a graded one does not, that"
               " settles the design: slot the second pocket in deck_rail and"
               " stop chasing the constant."]),

    dict(n="02k", slug="ledge_gauge", stage=2, mat="PLA", gap=8.0,
         title="Ledge gauge: the recessed deck, one datum station and one slot",
         proves="Storyboard panel 28 in plastic. The first 120 mm of the"
                " proposed deck -- both rails with their ledges cut down 1.2,"
                " the datum pocket and peg, the slot at station 2 and the"
                " plate at 52 -- so the real board can be dropped on it before"
                " frame.py is touched.",
         objects=[("ledge_gauge", 1)],
         process=dict(),
         hand=["Built on the Mac from PLAN.md's numbers (cad/ledge_gauge.py),"
               " not exported from frame.py: it tests the design. The station"
               " stub coupon, cut from frame.py later, tests the code.",
               "Drop the full board's LEFT end straight down: first tab into"
               " the pocket near the left end, second tab into the slot, notch"
               " over the peg on the far rail. Do not slide it along.",
               "Pass: rim down on the 0.6 shelf both sides with no rock, tape"
               " clear of the relief floor and the plate, about 0.4 of play"
               " across, and a shove along the rail meets the pocket wall,"
               " not friction.",
               "Nothing stands above the rail crown. If anything on a ledge"
               " reads as a wall, that is a build error, not the design.",
               "Tap the result into ledge.html on the Checks tab."]),

    dict(n="02m", slug="cal_target", stage=2, mat="PLA", gap=8.0,
         title="Camera calibration target: dot grid and staircase",
         proves="Turns the 4K top-down camera into a measuring instrument:"
                " 84 dark dots on a 10 mm pitch at mat level for scale, tilt"
                " and lens distortion, and two drop-in cups that put dots at"
                " 5 and 20 mm for the camera height and lens centre."
                " The side camera reads the step faces for its height scale.",
         objects=[("cal_target", 1), ("cal_step5", 1), ("cal_step20", 1)],
         process=dict(),
         hand=["Print it in a LIGHT colour -- the holes work by showing the"
               " dark mat through them. Black PLA makes it useless.",
               "Three flat parts, no bridges, no supports: the plate, and two"
               " open cups printed floor-down. After printing, flip each cup"
               " and drop it into its recess on the plate, open side down --"
               " the short one at the left end, the tall one at the right."
               " Their dotted faces then sit 5 and 20 mm above the plate."
               "After printing, caliper the plate's long side (nominal 140.00)"
               " and its short side (90.00) and tap them into the sheet: the"
               " true pitch is scaled from those, everything else follows.",
               "Lay it flat on the mat near the centre under the overhead"
               " camera, marker hole at the top right, and take one"
               " Screenshot (Source) at 4K. Then one shot where the side"
               " camera sees the staircase edge-on."]),

    dict(n="03", slug="petg_gauges", stage=3, mat="PETG", gap=10.0,
         # interface="PLA" is what the user wants, but the two-filament project
         # this writes is REJECTED BY STUDIO'S GUI ("Invalid configuration
         # file") although the CLI slices it. Four attempts on 2026-10-04 did
         # not find the rule. Until that is solved the PLA slot is added by
         # hand, three clicks, per the card below. Do not re-enable blind.
         title="PETG gauges",
         proves="RAIL_FIT for clips, the latch chamfer decision, MAGNET_FIT.",
         objects=[("fit_clips_petg", 1), ("magnet_gauge", 1)],
         process=dict(enable_support="1", support_type="normal(manual)",
                      support_on_build_plate_only="1"),
         hand=["Supports are ALREADY PAINTED on fit_clips_petg: under each"
               " clip's tooth and release tab, written into the file. Support"
               " is normal(manual), so nothing else is generated. Just slice;"
               " the preview should show a thin column inside each of the"
               " four clips and none on the magnet gauge.",
"PLA SUPPORT INTERFACE, three clicks (the file cannot carry it yet):"
               " 1. In Project Filaments click + and pick your PLA."
               " 2. Process > Support > Support/raft interface: choose filament 2."
               " 3. Studio offers to set the matching zero-gap settings: click Yes."
               " PLA does not bond to PETG, so the tooth and tab faces come out"
               " clean. Expect a prime tower and about 2h 45m.",
               "A filled relief slot is a dead latch. It has happened twice."]),

    dict(n="04", slug="first_article_a", stage=4, mat="PLA", gap=12.0,
         title="First article A -- left frame, tie, caps",
         proves="The first structural parts, and the mating part everything"
                " later needs.",
         objects=[("end_frame", 1), ("rear_tie", 1), ("rail_cap", 2)],
         process=dict(),
         hand=["Three regimes on one plate. Check each object's overrides in"
               " the object list before slicing (see the table below).",
               "Do not slice end_frame_r until every check on this plate has"
               " passed."]),

    dict(n="05", slug="right_frame", stage=5, mat="PLA", gap=12.0,
         title="Right frame -- the mirror export",
         proves="The mirror export, and closes the pair.",
         objects=[("end_frame_r", 1)],
         process=dict(),
         hand=["end_frame_r is a genuinely different STL, not the same file"
               " twice. Its pose is Y+90 where the left frame is Y-90."]),

    dict(n="06", slug="din_rail", stage=6, mat="PLA", gap=12.0,
         title="The DIN rail",
         proves="The first big part. Nothing downstream can compensate if it"
                " warps.",
         objects=[("din_rail", 1)],
         process=dict(brim_width="5"),
         hand=["Only print this after both frames have accepted the stub.",
               "Same flow and seam settings the stage 2 stub used."]),

    dict(n="04x", slug="both_frames", stage=4, mat="PLA", gap=12.0,
         title="Both end frames, reprinted with a solid post",
         proves="Nothing new: the frames from plate 06x flexed at the post's"
                " lightening window (3 mm ribs over an 18 mm opening), so the"
                " window is closed and both frames print again (2026-10-08).",
         objects=[("end_frame", 1), ("end_frame_r", 1)],
         process=dict(),
         hand=["Outer face down, no brim. Everything else from plate 06x"
               " (tie, caps, rail) is already printed and stays."]),

    dict(n="06x", slug="pla_structure_one_plate", stage=6, mat="PLA", gap=10.0,
         title="Both frames, the tie, both caps and the rail -- one plate",
         proves="Nothing new: plates 04, 05 and 06 together, because the user"
                " asked for the PLA Matte parts on one bed (2026-10-07). Same"
                " per-object walls and infill as the separate plates.",
         objects=[("end_frame", 1), ("end_frame_r", 1), ("rear_tie", 1),
                  ("rail_cap", 2), ("din_rail", 1)],
         process=dict(),
         hand=["This breaks the stop rule 'one of each part before its second"
               " copy' on purpose: if the left frame's mortise binds, the right"
               " frame is already printed too. Print plate 04 alone first if"
               " that risk matters more than the bed time.",
               "The rail's eight counterbores carry a one-layer skin at the"
               " seat: push the M3x12 cap screw through it.",
               "No brim anywhere. The frames print on their outer face, the"
               " rail lips-down, the caps top-face down."]),

    dict(n="07", slug="deck_ladder", stage=7, mat="PLA", gap=12.0,
         title="The deck ladder",
         proves="Largest single print. Gated on board width, socket clearance"
                " and the tie's shrink.",
         objects=[("deck_ladder", 1)],
         # along Y with the seam at the back: every seam at a rail end (TURN).
         # 294 along Y needs 13 of the 320: a 12 mm keep-out instead of 14,
         # the skirt (2 out, 2 loops) still stays 8 clear of the plate edge.
         edge=12.0,
         # The real part, so it gets the finish the gauges did not: 0.08 mm
         # layers (the rails' arcs read as curves, not steps; every feature
         # height divides by 0.08) and ironing on
         # every top surface -- the deck plates, the ledge floors the boards
         # sit in, the pocket blocks and shoulder. User's ask, 2026-10-07.
         preset="0.08mm High Quality @BBL H2S",
         process=dict(seam_position="back", ironing_type="top"),
         hand=["Shoulder to shoulder must read 288.00 and agree with the tie's"
               " shrink within 0.15.",
               "The ladder lies along Y on purpose, with Seam position = Back:"
               " that puts every layer's seam at a rail end. Leave both alone;"
               " on Aligned the seams land in the board pockets."]),

    dict(n="07b", slug="tpu_pads_held", stage=7, mat="TPU", gap=6.0,
         title="TPU production pads -- the 14 held back",
         proves="Nothing. This is the balance of the 18 feet, released once"
                " FOOT_FIT is confirmed.",
         objects=[("foot_pad", 14)],
         # 6 skirt loops, not the standing 2: TPU goes in straight after PLA,
         # and the extra loops purge whatever PLA is left in the hot end
         # before the first pad wall (user request 2026-10-08).
         process=dict(initial_layer_print_height="0.24", outer_wall_speed="30",
                      inner_wall_speed="40", top_shell_layers="4",
                      bottom_shell_layers="4", skirt_loops="6"),
         filament=dict(filament_retraction_length="0.4"),
         hand=["Do not print this until stage 2's foot_gauge has confirmed"
               " FOOT_FIT. If the constant moved, regenerate first."]),

    dict(n="07c", slug="tpu_pads_side_parts", stage=7, mat="TPU", gap=6.0,
         title="TPU pads for the side tray and side bin (4)",
         proves="Nothing new: 07b's 14 went into the ladder, frames and rear tray;"
                " plate 01's 4 are not assumed to exist (user, 2026-10-09).",
         objects=[("foot_pad", 4)],
         # 6 skirt loops, not the standing 2: TPU goes in straight after PLA,
         # and the extra loops purge whatever PLA is left in the hot end
         # before the first pad wall (user request 2026-10-08).
         process=dict(initial_layer_print_height="0.24", outer_wall_speed="30",
                      inner_wall_speed="40", top_shell_layers="4",
                      bottom_shell_layers="4", skirt_loops="6"),
         filament=dict(filament_retraction_length="0.4"),
         hand=["2 under the side tray, 2 under the side bin, grooved face in."]),

    dict(n="07f", slug="tpu_feet_all", stage=7, mat="TPU", gap=6.0,
         title="All 18 TPU feet, for a whole bench",
         proves="07b and 07c on one plate: the TPU file that goes with the whole-bench"
                " project (one project cannot hold a third filament yet).",
         objects=[("foot_pad", 18)],
         process=dict(initial_layer_print_height="0.24", outer_wall_speed="30",
                      inner_wall_speed="40", top_shell_layers="4", bottom_shell_layers="4",
                      skirt_loops="6"),
         filament=dict(filament_retraction_length="0.4"),
         hand=["Same regime as 07b: TPU 95A HF, slow walls, 4 top and bottom layers.",
               "14 go under the frames, ladder and tray; 4 under the side tray and bin."]),

    dict(n="08", slug="rear_tray", stage=8, mat="PLA", gap=12.0,
         title="The rear tray",
         proves="Last of the PLA structure, and the only part with a real"
                " cooling problem.",
         objects=[("rear_tray", 1)],
         # 0.12 High Quality + ironing, not 0.28 plain (user, 2026-10-08:
         # "lots of exposed parts with 0.28 layer lines"). Ironing takes the
         # cell floors, boss tops and wall tops; the finer layers take the
         # walls and fins. Flow 10% sits between the ladder's 8% at 0.08 and
         # the 0.20 default. Sliced 3h05 vs 1h12 at 0.28.
         preset="0.12mm High Quality @BBL H2S",
         process=dict(ironing_type="top", ironing_flow="10%"),
         filament=dict(fan_max_speed="100", fan_cooling_layer_time="8",
                       chamber_temperatures="0"),
         hand=["~190 layers of two isolated fins. That is what the 8 s fan"
               " threshold and 100% part fan are for.",
               "Before any rail screw: a csk dropped into each buttress pilot"
               " must stand at least 7.75 mm proud."]),

    dict(n="10m", slug="buried_magnet_coupons", stage=10, mat="PETG", gap=14.0,
         title="Buried head-magnet coupons: how much skin still snaps",
         proves="Whether a side magnet sealed in at a pause (0.3 head clearance"
                " + 0.45 / 0.65 / 0.85 skin) still docks the side parts, against"
                " today's open seat. Model: 29 / 25 / 22 % of contact pull.",
         # Two, not four (user, 2026-10-09): the finished side parts are the
         # open-seat reference, and 0.65 sits between the two that matter --
         # the best a buried disc can do (one wall line) and the sturdy one
         # (two lines). The other two coupons stay buildable.
         objects=[("skin_coupon_045", 1), ("skin_coupon_085", 1)],
         # 0.20 Standard, 15% infill: the skin is a WALL (wall lines in XY), so
         # neither layer height nor infill changes what is being tested, and
         # 8.0 is a layer boundary at 0.20 too. 0.12 HQ + solid was 1h04.
         process=dict(enable_support="0"),
         # 7.0 bin-local + the 1.0 plinth; a layer boundary at 0.12 and 0.20.
         pause_z=8.0,
         hand=["Pause at 8.0 mm is in the file. Drop one disc ON EDGE into the"
               " slot of each coupon (1 nub = 0.45 skin, 3 nubs = 0.85). Each"
               " must sit below the top. Resume.",
               "Reference: the finished side tray / bin with its open seats.",
               "Test: set each on the desk against a bar-end screw head on the"
               " frame and feel the snap; tug it off sideways."]),

    dict(n="03c", slug="clip_test", stage=3, mat="PETG", gap=14.0,
         title="Two test clips: full-width latch at 1.8 and 2.0 mm",
         proves="The 2026-10-10 latch: full clip width, 2.0 thick (~1.9% strain"
                " against the old ~10%). Snap on and off the rail stub many times;"
                " one to keep, one to abuse.",
         objects=[("clip_test_18", 1), ("clip_test_20", 1)],
         # PETG-only supports with the standard gap, NOT the PLA interface:
         # the interface's 24 filament swaps made two small clips a 1h50
         # print. For a test, a support that needs a knife is fine.
         process=dict(enable_support="1", support_type="normal(manual)",
                      support_on_build_plate_only="0", brim_width="5"),
         hand=["Support paint is in the file (PETG support, no PLA): trim it"
               " off the tooth and the tab with a knife.",
               "Test on the rail: rock on, lever off by the tab, twenty times."
               " Should flex like a keyboard key and never whiten at the root."]),

    dict(n="10d", slug="display_backplate", stage=10, mat="PLA", gap=12.0,
         title="CrowPanel P4 backplate",
         proves="The screen on the bench: four bolted corner bosses (pressed M3"
                " nuts, rebuilt 2026-10-17 after the self-tap bosses split) take"
                " the panel's own M3 slots, two bars screw to the posts, and a"
                " dovetail socket on the top edge takes the mic crown (10c). Clearance"
                " to the tallest part on the board's back: 1.4 mm (Elecrow's STEP).",
         objects=[("display_backplate", 1)],
         hand=["Back face down, no supports.",
               "Press an M3 hex nut into the hex pocket in the back of each corner"
               " boss (4). A screw from the front and a few turns pulls a stiff"
               " one home.",
               "On the TABLE, not the rail: posts face-up, clip feet hanging off"
               " the edge so the backs lie flat. Slide 2 M3 hex nuts down each"
               " post's channel from the top, under the holes.",
               "Backplate onto the posts: 4 x M3 x 8 cap from the front, heads in"
               " the counterbores. Hook the unit onto the rail, rock it flat, and"
               " turn each post's snap lock wing (plate 10L) a quarter turn so it"
               " points along the post. Then the screen: 4 x M3 x 16 cap from the front"
               " through its corner slots into the boss nuts, snug only."]),

    dict(n="10c", slug="mic_crown", stage=10, mat="PETG", gap=12.0,
         title="Mic crown for the reSpeaker XVF3800",
         proves="The mic array above the screen with no screws (2026-10-17): a"
                " dovetail tongue down the backplate's top socket, the board on three"
                " pads under its M2 holes, two fixed lips and one sprung lip on its"
                " edge, pins in two holes so it cannot turn.",
         objects=[("mic_crown", 1)],
         hand=["Back face down, no supports. The lips' undersides are 1.5 mm"
               " overhangs; they print as they are.",
               "Board in, logo face out: tuck its bottom edge under the two lower"
               " lips, lay it on the pads with the pins in its holes, press the top"
               " edge until the sprung lip clicks. Out: pull that lip's tab outward.",
               "Crown on: tongue into the socket on the backplate's top edge, slide"
               " it down to the stop. It lifts straight back out."]),

    dict(n="09", slug="petg_side_parts", stage=9, mat="PETG", gap=12.0,
         title="PETG side tray and side bin -- no supports, no PLA",
         proves="Everything left is a repeat of a proven regime with settled"
                " constants.",
         # The two end-of-bench parts only (user, 2026-10-09: "print the ends
         # without the clip so we don't need the PLA"). Neither needs support,
         # so this plate is PETG alone: no interface swaps, which is what made
         # finer layers affordable. The clip parts moved to 09c.
         objects=[("side_tray", 1), ("side_bin", 1)],
         preset="0.12mm High Quality @BBL H2S",
         process=dict(enable_support="0", brim_width="5"),
         # 3.2 is a layer boundary at 0.12 (0.2 + 25 x 0.12); 0.08 is not.
         # 7.04: the first 0.12 layer top at or above HEAD_SLOT_TOP (7.0) --
         # the head-disc slots are still open there, and the next layer
         # bridges them (buried head discs, 2026-10-09).
         pause_z=[3.2, 7.04],
         hand=["Pause 1 at 3.2 mm (in the file): 5 discs flat into the side"
               " tray's cells, 2 into the side bin's. Resume.",
               "Pause 2 at 7.04 mm (in the file): 3 discs ON EDGE into each"
               " part's slots behind the head pockets (6 in all). Resume.",
               "Nothing to fit after the print: every disc is sealed in."]),

    dict(n="09c", slug="petg_clip_parts", stage=9, mat="PETG", gap=12.0,
         title="PETG clip parts: rail bin + both display posts",
         proves="Both clip-on modules together: their interface windows sit at"
                " the same heights, so they share the PLA swaps.",
         # Both posts on this plate, not one here and one on 09p (user,
         # 2026-10-10): the posts' PLA interface sits at the same heights, so
         # the second post shares every swap and the prime tower instead of
         # paying for them again.
         objects=[("rail_bin", 1), ("display_post", 2)],
         # support on the model is allowed here on purpose: the hook's tooth
         # is reached only from the latch finger inside the clip channel
         process=dict(enable_support="1", support_type="normal(manual)",
                      support_on_build_plate_only="0", brim_width="5",
                      support_top_z_distance="0", support_interface_spacing="0",
                      support_interface_top_layers="3"),
         pla_template=TEMPLATE_2F,  # PETG HF + PLA Basic, 230/60, purge 223/450
         hand=["Support paint is already in the file (PAINT table): the clip"
               " channels only.",
               "PLA interface is already in the file (pla_template): PLA Basic"
               " in slot 2 at 230, bed 60, purge 223/450. Never press Sync info.",
               "Both posts at once (user's call): watch the last hour, when"
               " only the two 144 mm posts are printing."]),

    dict(n="10p", slug="display_posts_locks", stage=10, mat="PETG", gap=12.0,
         title="Display posts with twist locks (replaces 09c's posts)",
         proves="The screen unit stays on the rail under its own weight and a"
                " finger on the touchscreen: no spring latch, a quarter-turn"
                " twist lock under the lower lip instead (both latches broke,"
                " 2026-10-17).",
         objects=[("display_post", 2), ("display_lock", 2), ("display_lock_knob", 2)],
         process=dict(enable_support="1", support_type="normal(manual)",
                      support_on_build_plate_only="0", brim_width="5",
                      support_top_z_distance="0", support_interface_spacing="0",
                      support_interface_top_layers="3"),
         pla_template=TEMPLATE_2F,  # PETG HF + PLA Basic, 230/60, purge 223/450
         hand=["Posts lie FRONT FACE DOWN (2026-10-17): layers run along the post, so"
               " the screen's lever bends them along the extrusions, not across them.",
               "Support paint is already in the file: under the hook's tooth only.",
               "PLA interface is already in the file, as on 09c. Never press Sync info.",
               "Lock, no screws: push each lock's shaft through the foot's bore from"
               " behind, then press the wing down over the hex until it clicks.",
               "Use: hook the post over the rail's top lip, rock it flat, turn the"
               " knob a quarter clockwise (knob along the post = locked)."]),

    dict(n="10L", slug="twist_locks_screwless", stage=10, mat="PETG", gap=8.0,
         title="Screwless twist locks for the posts already printed",
         proves="The lock with its own shaft and a snap-on wing: no M3 screw, no nut"
                " (2026-10-17, user: 'Less m3 screws the better'). Fits plate 10p's"
                " posts as printed -- same 3.8 bore.",
         objects=[("display_lock", 2), ("display_lock_knob", 2)],
         hand=["No supports: the locks lie on their flat side, tooth up; the wings"
               " stand on their underside.",
               "Push each lock's shaft through the foot's bore from behind, then press"
               " the wing down over the hex until it clicks. Wing along the post ="
               " locked; a quarter turn back = open."]),

    dict(n="11t", slug="din_tilt_adapter", stage=11, mat="PETG", gap=10.0,
         title="DIN tilt adapter, with its twist lock",
         proves="A generic DIN device too tall for the raked rail (the UniFi"
                " UA-Hub-Door-Mini, 113 mm) clips onto a short TS35 stub stood"
                " 40 mm off the rail on a 24-tooth hinge, from the rail's angle"
                " to flat in 15-degree steps (2026-10-17).",
         objects=[("din_tilt_base", 1), ("din_tilt_arm", 1), ("din_tilt_knob", 1),
                  ("display_lock", 1), ("display_lock_knob", 1)],
         hand=["No supports: every part stands on an end face, profiles in the layer"
               " plane, hinge teeth facing up.",
               "Hinge: press an M3 x 20's head down the well in the base's end into its"
               " seat (a drop of super glue if it spins), arm on, M3 nut pressed into"
               " the thumb knob, knob onto the screw. Loosen 3 turns to swing, retighten.",
               "Lock: as on the display posts -- shaft through the foot from behind,"
               " wing pressed on until it clicks."]),

    dict(n="09p", slug="display_post", stage=9, mat="PETG", gap=12.0,
         title="The second display post",
         proves="Repeat of 09c's post, once the first has stood.",
         objects=[("display_post", 1)],
         process=dict(enable_support="1", support_type="normal(manual)",
                      support_on_build_plate_only="0", brim_width="5",
                      support_top_z_distance="0", support_interface_spacing="0",
                      support_interface_top_layers="3"),
         pla_template=TEMPLATE_2F,  # PETG HF + PLA Basic, 230/60, purge 223/450
         hand=["Support paint is already in the file: the clip channel only.",
               "PLA interface is already in the file, as on 09c."]),
]


def template_globals(rel):
    """wall_loops / sparse_infill_density / brim_type of a saved Studio
    project's own process -- what a pla_template plate actually prints with."""
    with zipfile.ZipFile(os.path.join(HERE, "..", rel)) as t:
        tcfg = json.loads(t.read("Metadata/project_settings.config"))
    one = lambda v: v[0] if isinstance(v, list) else v  # noqa: E731
    return {k: str(one(tcfg[k])) for k in ("wall_loops", "sparse_infill_density", "brim_type")}


def resolve_stl(name):
    for d in SRC_DIRS:
        p = os.path.join(OUT, d, name + ".stl")
        if os.path.exists(p):
            return p
    raise SystemExit(f"no STL anywhere for {name!r} (looked in {SRC_DIRS})")


def print_poses():
    """PRINT_POSE lifted out of check.py without importing it.

    check.py runs its whole gate at import time, so `import check` would
    re-run every mesh test just to read a dict. ast reads the literal.
    """
    tree = ast.parse(open(os.path.join(HERE, "check.py"), encoding="utf-8-sig").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PRINT_POSE":
            return ast.literal_eval(node.value)
    raise SystemExit("PRINT_POSE not found in check.py")


POSE = print_poses()
# A turn about Z on the bed, applied after POSE. It changes nothing about
# overhangs, only where the slicer's "Back" seam lands: the ladder's rails
# lie along Y so every seam stacks at a rail END, never in a pocket. On
# "Aligned" the seams went to the concave corners, which on this part are
# the board pockets, and a seam blob is bigger than the pocket's 0.30 fit.
TURN = {"deck_ladder": 90, "half_bay_gauge": 90}


def flat(kind, name):
    """Resolve a system preset's `inherits` chain, base first."""
    chain, n = [], name
    while n:
        f = os.path.join(BBL, kind, n + ".json")
        if not os.path.exists(f):
            raise SystemExit(f"missing {kind} preset: {n}")
        j = json.load(open(f, encoding="utf-8"))
        chain.append(j)
        n = j.get("inherits")
    d = {}
    for j in reversed(chain):
        # 2.x presets also pull in per-extruder-variant templates by
        # `include`; those sit under the file's own keys, above its parents.
        inc = j.get("include", [])
        for t in [inc] if isinstance(inc, str) else inc:
            d.update(flat(kind, t))
        d.update(j)
    return d


def base_config(material, process=PROCESS):
    """machine + process + filament, flattened the way a project stores it.
    `process` is the Studio process preset; a plate may name a finer one."""
    cfg = {}
    for src in (flat("machine", MACHINE), flat("process", process)):
        cfg.update({k: v for k, v in src.items() if k not in DENY})
    # Every filament option is a per-slot vector. One slot here, so one entry;
    # the system presets carry two because the H2 family shares them with the
    # dual-nozzle machines.
    fil = flat("filament", FILAMENT[material])
    for k, v in fil.items():
        if k in DENY:
            continue
        if isinstance(v, list):
            cfg[k] = [str(v[0])] if v else []
        else:
            cfg[k] = [str(v)]
    cfg.update(EXTRA_DEFAULTS)
    cfg.update({
        "from": "project", "name": "project_settings",
        "printer_settings_id": MACHINE,
        "print_settings_id": process,
        "filament_settings_id": [FILAMENT[material]],
        "filament_ids": [str(fil.get("filament_id", ""))],
        "default_print_profile": process,
        "default_filament_profile": [FILAMENT[material]],
        "filament_colour": [COLOUR[material]],
        "curr_bed_type": "Textured PEI Plate",
        "version": "02.07.01.62",
    })
    return cfg


# Settings that go with a dissimilar-material support interface. PLA and PETG
# do not bond, so the interface can touch the part: no Z gap, no spacing, and
# the supported face comes out flat instead of rough. Three dense layers so
# the PETG support body below never shows through.
INTERFACE_PROCESS = {
    "support_interface_filament": "2",
    "support_top_z_distance": "0",
    "support_interface_spacing": "0",
    "support_interface_top_layers": "3",
}
INTERFACE_COLOUR = "#FFFFFF"


def add_interface_filament(cfg, base, material):
    """Give the project a second filament slot, used ONLY for support interface.

    Chosen 2026-10-04 for the clip gauge: PETG-on-PETG supports scar the tooth
    and tab faces the plate exists to measure; a PLA interface releases clean.
    It costs filament swaps (plate 03: 1h14 / 36 g becomes about 2h43 / 69 g),
    which the user accepted for the cleaner faces.

    The vectors here are FULL length, unlike base_config's. On the H2 family a
    filament option holds one entry per extruder variant (three on the H2S:
    Standard, High Flow, E3D High Flow), so two filaments are six entries, not
    two. One filament collapsed to a single entry happens to load in the GUI;
    two collapsed to two does not -- the GUI reads them as one filament with
    two variants and reports "Invalid configuration file", although the CLI
    slices the same file without complaint. So both slots are rebuilt from
    their presets whole, and the multi-filament keys the GUI writes itself
    (flush volumes, filament map) are supplied rather than left to default.
    """
    def whole(v):
        return [str(x) for x in v] if isinstance(v, list) else [str(v)]
    a, b = flat("filament", FILAMENT[base]), flat("filament", FILAMENT[material])
    for k in set(a) | set(b):
        if k in DENY or not isinstance(cfg.get(k), list):
            continue
        cfg[k] = whole(a.get(k, b.get(k))) + whole(b.get(k, a.get(k)))
    cfg["filament_settings_id"] = [FILAMENT[base], FILAMENT[material]]
    cfg["filament_ids"] = [str(a.get("filament_id", "")), str(b.get("filament_id", ""))]
    cfg["filament_colour"] = [COLOUR[base], INTERFACE_COLOUR]
    cfg["filament_map"] = ["1", "1"]                    # both on the one nozzle
    # mm3 purged when changing FROM row TO column; Studio's own figures for
    # this pair, read back from a CLI slice of this plate
    cfg["flush_volumes_matrix"] = ["0", "602", "212", "0"]
    cfg["flush_volumes_vector"] = ["140"] * 4
    cfg["flush_multiplier"] = ["1"]
    # Legacy override keys the filament presets still carry but Studio 2.8's
    # GUI never writes into a project. They arrive one entry per filament
    # (2) beside per-variant vectors (6); with a single filament both collapse
    # to 1 and agree, with two they disagree. Dropped rather than padded: the
    # live keys are long_retractions_when_ec / retraction_distances_when_ec.
    for k in ("filament_long_retractions_when_ec",
              "filament_retraction_distances_when_ec"):
        cfg.pop(k, None)


def apply(cfg, overrides, where):
    """Set overrides, refusing any key the resolved config does not have.

    A typo'd setting name is otherwise invisible: Studio ignores keys it does
    not know and the plate quietly prints at the default. This turns that into
    a build failure instead.
    """
    bad = [k for k in overrides if k not in cfg]
    if bad:
        raise SystemExit(f"plate {where}: unknown setting(s) {bad}")
    for k, v in overrides.items():
        # Keep a vector's length. Several process options are per-extruder
        # vectors inherited from the dual-nozzle H2 profiles (outer_wall_speed
        # arrives as ["200", "500"]); writing a shorter vector is how Studio
        # gets handed a config it has to resize, and a resized option falls
        # back to its default rather than to the value asked for here.
        cfg[k] = [str(v)] * max(len(cfg[k]), 1) if isinstance(cfg[k], list) else str(v)


def mark_modified(cfg, stock, material):
    """Tell Studio's GUI which keys differ from the presets the project names.

    The GUI does not read a project config verbatim the way the CLI does. It
    loads the system preset named by print_settings_id / filament_settings_id
    and re-applies ONLY the keys listed in `different_settings_to_system`; a
    project with no list opens as the stock preset, every override dropped
    (plate 01 came up 2 walls / 15% grid while --verify sliced it 3 / 100%).
    One ';'-joined entry per preset, in Studio's order: process, each
    filament slot, printer.
    """
    changed = [k for k in cfg if k in stock and cfg[k] != stock[k]]
    fil_keys = set(flat("filament", FILAMENT[material]))
    proc = sorted(k for k in changed if k not in fil_keys)
    fila = sorted(k for k in changed if k in fil_keys)
    # one entry per filament slot: a second slot (support interface) is stock
    slots = len(cfg["filament_settings_id"])
    cfg["different_settings_to_system"] = ([";".join(proc), ";".join(fila)]
                                           + [""] * (slots - 1) + [""])
    cfg["inherits_group"] = [""] * (slots + 2)


# --- geometry ---------------------------------------------------------------

# Support paint, per part: z windows (mm above the bed, in the print pose)
# whose DOWNWARD faces get a support enforcer. These are the undersides of the
# features that start in mid-air -- the clip tooth and the release tab -- and
# nothing else: the latch's relief slot roof (z 40.8 on the gauge) must stay
# unpainted, because a filled relief slot is a dead latch.
PAINT = {
    "fit_clips_petg": ((38.2, 39.8),      # tooth underside, square and chamfered
                       (44.6, 45.3)),     # release tab underside
    # same windows as the gauge: same clip, same pose, tooth and tab z unchanged
    "clip_test_18":   ((38.2, 39.8), (44.6, 45.3)),
    "clip_test_20":   ((38.2, 39.8), (44.6, 45.3)),
    # The modules stand the other way up from the gauge: hook on top, latch
    # at the bottom. Top window = the hook's tooth and jaw undersides, held
    # up by support standing on the latch finger inside the channel (so
    # plate 09 is NOT build-plate-only); bottom window = the latch finger
    # and tab undersides, reached from the bed.
    # Printed front face down since 2026-10-17: the only overhang is the hook
    # tooth's bearing face (z 6.7, 2.2 out from the jaw, 1.7 over the post's
    # back face), so support stands on the post and PLA interface leaves the
    # face that hooks the rail clean. Nothing else is painted.
    "display_post": ((6.4, 7.0),),
    "rail_bin":     ((43.7, 46.3), (7.5, 11.5)),
}


def paint_faces(name, m):
    """Indices of the faces PAINT selects on a posed mesh (min corner at 0)."""
    if name not in PAINT:
        return frozenset()
    z = m.triangles_center[:, 2]
    pick = m.face_normals[:, 2] < -0.5
    win = np.zeros(len(z), dtype=bool)
    for lo, hi in PAINT[name]:
        win |= (z > lo) & (z < hi)
    idx = frozenset(np.where(pick & win)[0].tolist())
    if not idx:
        raise SystemExit(f"{name}: PAINT selected no faces -- the part or its pose changed")
    return idx


def posed_mesh(name):
    m = trimesh.load(resolve_stl(name), process=False)
    # STL is triangle soup: every face owns its three corners. Written to a
    # 3mf unmerged, Studio counts every edge as open (5388 "open edges" on a
    # 1796-face foot pad) and offers to "fix" a mesh that was already closed.
    m.merge_vertices()
    pose = POSE.get(name, 0)
    axis, ang = pose if isinstance(pose, tuple) else ("X", pose)
    if ang:
        vec = {"X": [1, 0, 0], "Y": [0, 1, 0], "Z": [0, 0, 1]}[axis]
        m.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(ang), vec))
    if TURN.get(name):
        m.apply_transform(trimesh.transformations.rotation_matrix(
            math.radians(TURN[name]), [0, 0, 1]))
    m.apply_translation(-m.bounds[0])          # min corner to the origin
    return m


def shelf_pack(sizes, gap, edge=EDGE):
    """Left-to-right shelves, deepest-in-Y first. Returns min-corner offsets."""
    limit = BED[0] - 2 * edge
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    places = [None] * len(sizes)
    x = y = shelf_d = 0.0
    for i in order:
        w, d = sizes[i]
        if x and x + w > limit:
            x, y, shelf_d = 0.0, y + shelf_d + gap, 0.0
        places[i] = (x, y)
        x += w + gap
        shelf_d = max(shelf_d, d)
    used_w = max(places[i][0] + sizes[i][0] for i in range(len(sizes)))
    used_d = y + shelf_d
    if used_w > limit or used_d > BED[1] - 2 * edge:
        raise SystemExit(f"packing overflows the plate: {used_w:.0f} x {used_d:.0f}")
    ox, oy = (BED[0] - used_w) / 2, (BED[1] - used_d) / 2
    return [(px + ox, py + oy) for px, py in places], (used_w, used_d)


# --- 3mf writing ------------------------------------------------------------

def model_xml(meshes, meta=None):
    """meta: extra (name, value) model metadata -- Studio's Project tab reads
    Title, Designer, Description and the rest from here."""
    from xml.sax.saxutils import escape
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<model unit="millimeter" xml:lang="en-US" '
         'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
         'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">',
         ' <metadata name="Application">BambuStudio-02.07.01.62</metadata>',
         ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
         f' <metadata name="CreationDate">{date.today().isoformat()}</metadata>']
    o += [f' <metadata name="{k}">{escape(v)}</metadata>' for k, v in (meta or [])]
    o += [' <resources>']
    for i, (_, m) in enumerate(meshes, start=1):
        o.append(f'  <object id="{i}" type="model">')
        o.append('   <mesh>')
        o.append('    <vertices>')
        o += ['     <vertex x="%.6f" y="%.6f" z="%.6f"/>' % tuple(v)
              for v in m.vertices]
        o.append('    </vertices>')
        o.append('    <triangles>')
        paint = m.metadata.get("paint", frozenset())
        o += ['     <triangle v1="%d" v2="%d" v3="%d"%s/>' % (
                  *t, ' paint_supports="4"' if j in paint else "")
              for j, t in enumerate(m.faces)]
        o.append('    </triangles>')
        o.append('   </mesh>')
        o.append('  </object>')
    o.append(' </resources>')
    o.append(' <build>')
    for i, (_, m) in enumerate(meshes, start=1):
        cx, cy, cz = m.metadata["plate_centre"]
        o.append(f'  <item objectid="{i}" '
                 f'transform="1 0 0 0 1 0 0 0 1 {cx:.6f} {cy:.6f} {cz:.6f}" '
                 'printable="1"/>')
    o.append(' </build>')
    o.append('</model>')
    return "\n".join(o)


def settings_xml(meshes, overrides, plates=None):
    """Per-object settings, and which objects sit on which plate: plates is
    [(plate name, [object ids from 1])], default one plate holding them all.
    An object's filament slot rides in its mesh's metadata (default 1), and
    an override set can be keyed by object id instead of name."""
    o = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for i, (name, m) in enumerate(meshes, start=1):
        o.append(f'  <object id="{i}">')
        o.append(f'    <metadata key="name" value="{name}"/>')
        o.append(f'    <metadata key="extruder" value="{m.metadata.get("extruder", 1)}"/>')
        for k, v in overrides.get(i, overrides.get(name, {})).items():
            o.append(f'    <metadata key="{k}" value="{v}"/>')
        o.append('    <part id="1" subtype="normal_part">')
        o.append(f'      <metadata key="name" value="{name}"/>')
        o.append('      <metadata key="matrix" '
                 'value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>')
        o.append(f'      <mesh_stat face_count="{len(m.faces)}" edges_fixed="0" '
                 'degenerate_facets="0" facets_removed="0" '
                 'facets_reversed="0" backwards_edges="0"/>')
        o.append('    </part>')
        o.append('  </object>')
    for k, (pname, ids) in enumerate(plates or [(None, range(1, len(meshes) + 1))],
                                     start=1):
        o.append('  <plate>')
        o.append(f'    <metadata key="plater_id" value="{k}"/>')
        if pname:
            o.append(f'    <metadata key="plater_name" value="{pname}"/>')
        o.append('    <metadata key="locked" value="false"/>')
        for i in ids:
            o.append('    <model_instance>')
            o.append(f'      <metadata key="object_id" value="{i}"/>')
            o.append('      <metadata key="instance_id" value="0"/>')
            o.append('    </model_instance>')
        o.append('  </plate>')
    o.append('</config>')
    return "\n".join(o)


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

SLICE_INFO = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.07.01.62"/>
  </header>
</config>
"""


PAUSE_XML = """<?xml version="1.0" encoding="utf-8"?>
<custom_gcodes_per_layer>
<plate>
<plate_info id="1"/>
{layers}<mode value="SingleExtruder"/>
</plate>
</custom_gcodes_per_layer>
"""
PAUSE_LAYER = '<layer top_z="{z}" type="1" extruder="1" color="" extra="" gcode="M400 U1"/>\n'


def plate_meshes(plate):
    """A plate's objects, posed, painted and packed: (names, [(name, mesh)]),
    each mesh centred on its origin with its spot on the plate in metadata."""
    names = [n for n, q in plate["objects"] for _ in range(q)]
    meshes = []
    cache = {}
    for n in names:
        if n not in cache:
            cache[n] = posed_mesh(n)
        m = cache[n].copy()
        m.metadata["paint"] = paint_faces(n, m)      # before the re-centring below
        meshes.append((n, m))

    places, used = shelf_pack([(m.extents[0], m.extents[1]) for _, m in meshes],
                              plate["gap"], plate.get("edge", EDGE))
    # Studio's own convention: each object's mesh centred on its local origin,
    # the plate position carried by the build item's transform. Positions
    # baked into the vertices under an identity transform get re-centred on
    # load, and the right-hand end of a long row lands "Outside" the plate.
    for (px, py), (_, m) in zip(places, meshes):
        w, d, h = m.extents
        m.apply_translation(-m.bounds.mean(axis=0))
        m.metadata["plate_centre"] = (px + w / 2, py + d / 2, h / 2)
    return names, meshes, used


def object_overrides(names, base_w, base_f, base_b):
    """Per-object walls / infill / brim wherever PART differs from what the
    plate's process really is. Returns (overrides by name, card rows)."""
    overrides, rows = {}, []
    for n in dict.fromkeys(names):
        w, f, b = PART[n]
        ov = {}
        if w != base_w:
            ov["wall_loops"] = w
        if f != base_f:
            ov["sparse_infill_density"] = f
            if f == "100%":
                ov["sparse_infill_pattern"] = "zig-zag"
        if b != base_b:
            ov["brim_type"] = "outer_only" if b else "no_brim"
        if b:
            ov["brim_width"] = "5"
        if ov:
            overrides[n] = ov
        rows.append((n, names.count(n), w, f, "yes" if b else "no",
                     "plate" if not ov else ", ".join(f"{k}={v}" for k, v in ov.items())))
    return overrides, rows


def build(plate):
    """One plate -> one .3mf, plus the row of facts its card needs."""
    names, meshes, used = plate_meshes(plate)

    # Plate defaults: the most demanding structural regime present, so an
    # ignored object override over-builds rather than under-builds. 100%
    # infill is a magnet-cap special case and never sets the plate.
    regimes = [PART[n] for n in dict.fromkeys(names)]
    walls = max(r[0] for r in regimes)
    fills = [int(r[1].rstrip("%")) for r in regimes if r[1] != "100%"]
    fill = f"{max(fills)}%" if fills else "100%"
    brim = any(r[2] for r in regimes)

    cfg = base_config(plate["mat"], plate.get("preset", PROCESS))
    if plate.get("interface"):
        add_interface_filament(cfg, plate["mat"], plate["interface"])
    stock = dict(cfg)
    apply(cfg, PLATE_DEFAULTS, plate["n"])
    apply(cfg, {"wall_loops": walls, "sparse_infill_density": fill,
                "brim_type": "outer_only" if brim else "no_brim"}, plate["n"])
    # Studio refuses to slice grid at 100% ("grid doesn't work at 100%
    # density"); the GUI offers to switch the pattern, the CLI just exits.
    # Solid parts get line infill, which 2.8 spells "zig-zag": the old
    # "rectilinear" is no longer a recognised value and gets silently
    # substituted with cubic, which fails the same check.
    if fill == "100%":
        apply(cfg, {"sparse_infill_pattern": "zig-zag"}, plate["n"])
    # Reid's standing habit: a couple of skirt loops to clear the nozzle
    # before the first real line. With brim off on the small parts, that first
    # line is otherwise a measured wall. 2 mm out, so it never touches a part.
    apply(cfg, {"skirt_loops": 2}, plate["n"])
    apply(cfg, plate.get("process", {}), plate["n"])
    apply(cfg, plate.get("filament", {}), plate["n"])
    if plate.get("interface"):
        if plate.get("filament"):
            raise SystemExit(f"plate {plate['n']}: filament overrides would be copied "
                             "onto the interface slot too; set them per slot first")
        apply(cfg, INTERFACE_PROCESS, plate["n"])
    mark_modified(cfg, stock, plate["mat"])

    # Overrides are relative to what the plate's process REALLY is. A
    # pla_template plate ships the template's own process (3 walls, 15%, no
    # brim), not the regime computed above, so measuring against the computed
    # one dropped every key that matched it: 10p's keepers lost their 4 walls
    # and 09c's posts their 25% and brim (verify's MISMATCH, 2026-10-17).
    base_w, base_f, base_b = walls, fill, brim
    if plate.get("pla_template"):
        tg = template_globals(plate["pla_template"])
        base_w, base_f, base_b = int(tg["wall_loops"]), tg["sparse_infill_density"], \
            tg["brim_type"] != "no_brim"
    overrides, rows = object_overrides(names, base_w, base_f, base_b)

    path = os.path.join(DEST, f"{plate['n']}_{plate['slug']}.3mf")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", model_xml(meshes))
        z.writestr("Metadata/model_settings.config", settings_xml(meshes, overrides))
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
        # A two-filament (PLA interface) config written here is rejected by
        # Studio's GUI, so plates that need one take it whole from a project
        # the user saved in Studio and that was then patched (temps, purge):
        # the meshes, paint and per-object settings stay ours.
        if plate.get("pla_template"):
            with zipfile.ZipFile(os.path.join(HERE, "..", plate["pla_template"])) as t:
                tcfg = json.loads(t.read("Metadata/project_settings.config"))
            assert len(tcfg["filament_settings_id"]) == 2, "template is not two-filament"
            z.writestr("Metadata/project_settings.config",
                       json.dumps(tcfg, indent=4, ensure_ascii=False))
        else:
            z.writestr("Metadata/project_settings.config",
                       json.dumps(cfg, indent=4, ensure_ascii=False))
        # A print pause DOES travel in a .3mf: Studio saves it here, and the
        # CLI honours it (checked 2026-10-09 on the user's saved plate 09).
        # The old "a .3mf cannot carry it" hand step was wrong.
        if plate.get("pause_z") is not None:
            zs = plate["pause_z"]
            zs = list(zs) if isinstance(zs, (list, tuple)) else [zs]
            # Every pause must sit on a real layer top for THIS plate's
            # layers, or Studio may move or drop it. Layer tops are
            # first + k * layer.
            lh = float(cfg.get("layer_height", "0.2"))
            fl = float(cfg.get("initial_layer_print_height", "0.2"))
            for pz in zs:
                k = (pz - fl) / lh
                if abs(k - round(k)) > 1e-6:
                    raise SystemExit(f"plate {plate['n']}: pause at {pz} is not a layer "
                                     f"top at {lh} layers (nearest {fl + round(k) * lh:.2f})")
            z.writestr("Metadata/custom_gcode_per_layer.xml", PAUSE_XML.format(
                layers="".join(PAUSE_LAYER.format(z=pz) for pz in sorted(zs))))

    vol = sum(m.volume for _, m in meshes) / 1000.0     # cm3
    return dict(path=path, rows=rows, used=used, cfg=cfg, n_obj=len(meshes),
                vol=vol, walls=walls, fill=fill, brim=brim,
                bytes=os.path.getsize(path))


# --- projects: several plates in one Studio file ----------------------------
# User, 2026-10-17: "Is there a way to put all these parts in a project for
# bambu". One .3mf, one plate per entry, each plate keeping its own parts,
# pose, packing and per-object regime. A two-filament config written here is
# rejected by Studio's GUI (see build), so a project takes the saved PETG +
# PLA template's whole config and points each object at its plate's slot.
SLOT = {"PETG": 1, "PLA": 2}            # the template's filament order

PROJECTS = [
    dict(slug="screen_mic_din", title="Screen case, mic crown, DIN tilt adapter",
         about="The 7-inch screen's backplate, the mic crown that sits above it, and the"
               " DIN tilt adapter for devices too tall for the raked rail.",
         plates=["10d", "10c", "11t"], optional=["10c", "11t"]),
    # The whole bench, every PLA and PETG part (user, 2026-10-17: "the entire
    # breadboard bench"). The gauges stay out; 09c's posts are superseded by
    # 10p's, so its rail bin rides with them. TPU feet: plate 07f, own file.
    dict(slug="whole_bench", title="The whole Breadboard Bench, PLA + PETG",
         about="A 3D-printed electronics workbench: two breadboards in a cradle, a DIN rail"
               " across the back for clip-on modules, a 7-inch touchscreen on posts, and an"
               " optional mic array above it. Every part is Python code (build123d), checked"
               " by scripts before it prints, and written out as this project.",
         optional=["10c", "11t"], extra_file="07f_tpu_feet_all.3mf (the 18 TPU feet)",
         plates=["06x", "07", "08", "09",
                 dict(n="10b", slug="posts_locks_rail_bin", stage=10, mat="PETG", gap=12.0,
                      title="Display posts, twist locks and the rail bin",
                      proves="10p plus 09c's rail bin: every PETG clip part, PLA interface"
                             " under the painted hooks.",
                      objects=[("display_post", 2), ("display_lock", 2),
                               ("display_lock_knob", 2), ("rail_bin", 1)], hand=[]),
                 "10d", "10c", "11t"]),
]
# Settings a project can carry per object. A plate's preset and process ride
# on its objects as these; anything else that differs from the template is a
# project-wide setting and is reported as dropped, never silently lost.
OBJECT_KEYS = {
    "layer_height", "wall_loops", "sparse_infill_density", "sparse_infill_pattern",
    "top_shell_layers", "bottom_shell_layers", "top_shell_thickness",
    "ironing_type", "ironing_flow", "seam_position", "brim_type", "brim_width",
    "enable_support", "outer_wall_speed", "inner_wall_speed", "sparse_infill_speed",
    "internal_solid_infill_speed", "top_surface_speed", "gap_infill_speed",
    "overhang_1_4_speed", "overhang_2_4_speed", "overhang_3_4_speed",
}


def _norm(v):
    return ",".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)


def plate_object_settings(plate, tcfg):
    """A plate's own process -- its preset's differences from the standard
    one, then its process dict -- split into what its objects can carry and
    what a shared project config cannot (returned as dropped)."""
    std = flat("process", PROCESS)
    want = {}
    if plate.get("preset"):
        pre = flat("process", plate["preset"])
        want.update({k: v for k, v in pre.items() if std.get(k) != v and k not in DENY})
    want.update(plate.get("process", {}))
    keep = {k: _norm(v) for k, v in want.items() if k in OBJECT_KEYS}
    dropped = sorted(k for k, v in want.items()
                     if k not in OBJECT_KEYS and k in tcfg and _norm(tcfg[k]) != _norm(v))
    slot = SLOT[plate["mat"]]
    for k, v in plate.get("filament", {}).items():
        have = tcfg.get(k)
        n = len(have) // len(tcfg["filament_type"]) if isinstance(have, list) else 0
        if not n or any(str(x) != str(v) for x in have[(slot - 1) * n:slot * n]):
            dropped.append(f"{k} (filament)")
    return keep, dropped


def plate_grid(i, count):
    """Where Studio puts plate i (0-based) of count: a grid ceil(sqrt) wide
    (exactly round(sqrt) when count is a square), one plate width plus a
    fifth between columns, rows running toward -y. Checked against a
    Studio-saved three-plate project (X1C, 256 bed: plates at 0 and 307.2
    across, the third 307.2 down)."""
    root = math.sqrt(count)
    cols = int(round(root)) + (1 if root > round(root) else 0)
    return ((i % cols) * BED[0] * 1.2, -(i // cols) * BED[1] * 1.2)


REPO = "https://github.com/InMyPajamas/breadboard-bench"
HUB = "https://www.redding.digital/bench-hub.html"
PICTURES = ["hero", "mic_crown", "din_tilt", "whole_bench_project"]   # docs/images/*.webp


def hardware_lines():
    """The bought parts, off the catalogue (it counts them on the assembly)."""
    try:
        hw = json.load(open(os.path.join(OUT, "catalog.json")))["hardware"]
    except Exception:
        return []
    lines = [f"{h['qty']} x {h['name']}" for h in hw]
    lines.append("1 x M3 x 20 socket head cap screw and 1 M3 hex nut (DIN tilt adapter hinge)")
    lines.append("Optional: Seeed reSpeaker XVF3800 USB 4-mic array (for the mic crown)")
    return lines


def project_info(proj, plates):
    """What Studio's Project tab shows: model metadata, and the Auxiliaries
    folder's pictures, bill of materials and guide. Returns (meta, files)."""
    import html as H
    opt = set(proj.get("optional", []))
    rows = "".join(f"<li>Plate {k}: {H.escape(p['title'])} ({p['mat']})"
                   f"{' <strong>optional</strong>' if p['n'] in opt else ''}</li>"
                   for k, p in enumerate(plates, start=1))
    hw = hardware_lines()
    desc = (f"<h3>{H.escape(proj['title'])}</h3><p>{H.escape(proj.get('about', ''))}</p>"
            f"<h3>Plates</h3><ol>{rows}</ol>"
            "<h3>Filaments</h3><p>Slot 1 is PETG HF, slot 2 is PLA Basic. Map them in the"
            " Print dialog; pressing Sync info resets this project's filament settings.</p>")
    if opt:
        desc += ("<h3>Optional add-ons</h3><p>Plates marked optional are extras: the mic crown"
                 " holds a reSpeaker XVF3800 above the screen, and the DIN tilt adapter carries"
                 " DIN devices too tall for the raked rail (it swaps in for the rail bin at the"
                 " rail's right end). Skip them if you don't need them.</p>")
    if proj.get("extra_file"):
        desc += f"<h3>Also print</h3><p>{H.escape(proj['extra_file'])}</p>"
    if hw:
        desc += "<h3>Hardware</h3><ul>" + "".join(f"<li>{H.escape(x)}</li>" for x in hw) + "</ul>"
    desc += (f'<p>Code and every file: <a href="{REPO}">{REPO}</a><br>'
             f'Build hub with a 3D viewer: <a href="{HUB}">{HUB}</a></p>')
    meta = [("Title", f"Breadboard Bench: {proj['title']}"), ("Designer", "InMyPajamas"),
            ("Description", H.escape(desc)), ("Origin", "original"),
            ("ProfileTitle", "H2S 0.4, PETG HF + PLA Basic, per-plate settings"),
            ("ProfileDescription", "Generated by cad/plates.py; each plate carries its own"
                                   " layer height, walls, infill and pauses."),
            ("ModificationDate", date.today().isoformat())]
    files = {}
    img = os.path.join(HERE, "..", "docs", "images")
    for n in PICTURES:
        src = os.path.join(img, n + ".webp")
        if os.path.exists(src):
            files[f"Auxiliaries/Model Pictures/{n}.webp"] = open(src, "rb").read()
    hero = os.path.join(img, "hero.webp")
    if os.path.exists(hero):
        import io
        from PIL import Image
        im = Image.open(hero).convert("RGB")
        for name, w in (("thumbnail_3mf", 512), ("thumbnail_middle", 1024), ("thumbnail_small", 256)):
            t = im.copy()
            t.thumbnail((w, w))
            b = io.BytesIO()
            t.save(b, "PNG")
            files[f"Auxiliaries/.thumbnails/{name}.png"] = b.getvalue()
    if hw:
        files["Auxiliaries/Bill of Materials/hardware.txt"] = (
            "Breadboard Bench -- hardware\n\n" + "\n".join(hw) + "\n").encode()
    guide = os.path.join(DEST, "PLATES.md")
    if os.path.exists(guide):
        files["Auxiliaries/Assembly Guide/plates_and_hand_steps.txt"] = open(guide, "rb").read()
    return meta, files


PROJECT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
 <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_3mf.png" Id="rel-2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>
 <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_middle.png" Id="rel-4" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"/>
 <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_small.png" Id="rel-5" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small"/>
</Relationships>
"""
PROJECT_TYPES = CONTENT_TYPES.replace(
    "</Types>", ' <Default Extension="webp" ContentType="image/webp"/>\n'
                ' <Default Extension="txt" ContentType="text/plain"/>\n</Types>')


def build_project(proj):
    by_n = {p["n"]: p for p in PLATES}
    plates = [p if isinstance(p, dict) else by_n[p] for p in proj["plates"]]
    bad = [p["n"] for p in plates if p.get("interface") or p["mat"] not in SLOT
           or p.get("pla_template", TEMPLATE_2F) != TEMPLATE_2F]
    if bad:
        raise SystemExit(f"project {proj['slug']}: plates {bad} need a filament or "
                         "template this project does not have")
    with zipfile.ZipFile(os.path.join(HERE, "..", TEMPLATE_2F)) as t:
        tcfg = json.loads(t.read("Metadata/project_settings.config"))
    assert tcfg["filament_type"] == ["PETG", "PLA"], "template's slots moved"
    tg = template_globals(TEMPLATE_2F)
    base = (int(tg["wall_loops"]), tg["sparse_infill_density"], tg["brim_type"] != "no_brim")
    meshes, groups, overrides, cards, pauses = [], [], {}, [], []
    lh0 = float(tcfg["initial_layer_print_height"])
    for k, plate in enumerate(plates):
        names, ms, used = plate_meshes(plate)
        ox, oy = plate_grid(k, len(plates))
        ov, rows = object_overrides(names, *base)
        keep, dropped = plate_object_settings(plate, tcfg)
        ids = []
        for name, m in ms:
            cx, cy, cz = m.metadata["plate_centre"]
            m.metadata["plate_centre"] = (cx + ox, cy + oy, cz)
            m.metadata["extruder"] = SLOT[plate["mat"]]
            meshes.append((name, m))
            ids.append(len(meshes))
            if keep or name in ov:
                overrides[len(meshes)] = {**keep, **ov.get(name, {})}
        if plate.get("pause_z") is not None:
            zs = plate["pause_z"]
            zs = list(zs) if isinstance(zs, (list, tuple)) else [zs]
            lh = float(keep.get("layer_height", tcfg["layer_height"]))
            for pz in zs:
                q = (pz - lh0) / lh
                if abs(q - round(q)) > 1e-6:
                    raise SystemExit(f"project {proj['slug']}, plate {plate['n']}: pause "
                                     f"at {pz} is not a layer top at {lh}")
            pauses.append((k + 1, sorted(zs)))
        # Studio rejects a plate name holding any of <>:/\|?* with an error
        # dialog on open (2026-10-17: "Optional: ..." did), so strip them
        tag = " (optional)" if plate["n"] in proj.get("optional", []) else ""
        pname = re.sub(r'[<>:/\\|?*"]', "", f"{plate['n']} {plate['title']}{tag}")
        groups.append((pname, ids))
        cards.append((plate, rows, used, sum(m.volume for _, m in ms) / 1000.0, keep, dropped))

    path = os.path.join(DEST, f"project_{proj['slug']}.3mf")
    meta, aux = project_info(proj, plates)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("[Content_Types].xml", PROJECT_TYPES)
        z.writestr("_rels/.rels", PROJECT_RELS if any(".thumbnails" in k for k in aux) else RELS)
        z.writestr("3D/3dmodel.model", model_xml(meshes, meta))
        for name, data in aux.items():
            z.writestr(name, data)
        z.writestr("Metadata/model_settings.config",
                   settings_xml(meshes, overrides, groups))
        z.writestr("Metadata/slice_info.config", SLICE_INFO)
        z.writestr("Metadata/project_settings.config",
                   json.dumps(tcfg, indent=4, ensure_ascii=False))
        # pauses, one block per plate, in the mode Studio saves for a
        # multi-filament project (the template's own file says MultiAsSingle)
        if pauses:
            z.writestr("Metadata/custom_gcode_per_layer.xml",
                       '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n'
                       + "".join(f'<plate>\n<plate_info id="{k}"/>\n'
                                 + "".join(PAUSE_LAYER.format(z=pz) for pz in zs)
                                 + '<mode value="MultiAsSingle"/>\n</plate>\n'
                                 for k, zs in pauses)
                       + "</custom_gcodes_per_layer>\n")
    return dict(path=path, cards=cards, n_obj=len(meshes),
                vol=sum(m.volume for _, m in meshes) / 1000.0,
                bytes=os.path.getsize(path))


def verify_project(r):
    """Slice every plate of a project through Studio's CLI and read its own
    slice report: each plate must be inside its bed ("outside" false) and burn
    only its plate's filament."""
    import xml.etree.ElementTree as ET
    exe = next((p for p in STUDIO if os.path.isfile(p)), None)
    if not exe:
        print("  --verify: Bambu Studio not found, skipped")
        return False
    d = tempfile.mkdtemp(prefix="project_verify_")
    p = subprocess.run([exe, "--debug", "2", "--slice", "0", "--export-3mf", "out.3mf",
                        "--outputdir", d, r["path"]],
                       cwd=d, capture_output=True, text=True, errors="replace")
    ok = p.returncode == 0
    r["sliced"] = []
    try:
        with zipfile.ZipFile(os.path.join(d, "out.3mf")) as z:
            root = ET.fromstring(z.read("Metadata/slice_info.config"))
        info = {}
        for pl in root.iter("plate"):
            meta = {m.get("key"): m.get("value") for m in pl.findall("metadata")}
            fil = {int(f.get("id")): float(f.get("used_g")) for f in pl.findall("filament")}
            info[int(meta["index"])] = (meta, fil)
        for k, (plate, rows, used, vol, keep, dropped) in enumerate(r["cards"], start=1):
            meta, fil = info.get(k, ({}, {}))
            slot = SLOT[plate["mat"]]
            # a PETG plate with painted hooks takes PLA (slot 2) as interface
            allowed = {slot} | ({SLOT["PLA"]} if plate["mat"] == "PETG" and any(
                n in PAINT for n, _ in plate["objects"]) else set())
            secs = int(float(meta.get("prediction", 0)))
            good = (meta.get("outside") == "false" and slot in fil and set(fil) <= allowed)
            ok &= good
            hm = f"{secs // 3600} h {secs % 3600 // 60:02d}" if secs >= 3600 else f"{secs // 60} min"
            r["sliced"].append((plate, hm, meta.get("weight", "?")))
            print(f"  plate {k} ({plate['n']}, {plate['mat']} in slot {slot}): {hm}, "
                  f"{meta.get('weight', '?')} g, on its bed: {meta.get('outside') == 'false'}, "
                  f"filaments {sorted(fil)}, pauses {meta.get('pause_count', '?')}  "
                  f"{'ok' if good else 'PROBLEM'}")
            if dropped:
                print(f"      project-wide, not carried: {', '.join(dropped)}")
    except Exception as e:                     # noqa: BLE001
        ok = False
        print(f"  project slice unreadable: rc={p.returncode} {e}")
    shutil.rmtree(d, ignore_errors=True)
    return ok


# g/cm3, read from the filament profile Studio itself weighs the plate with.
# The hand-typed table this replaces had TPU at 1.21 against the profile's
# 1.26 -- enough to make a 2.01 g block look 98% dense when it was 94%.
DENSITY = {mat: float(flat("filament", name)["filament_density"][0])
           for mat, name in FILAMENT.items()}

# Bambu Studio's CLI, by platform. The macOS binary slices headless, and so
# does Windows from 02.08.02; the 02.07 Windows build was a GUI-subsystem exe
# whose CLI returned -2/-3 with no output.
STUDIO = ["/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
          r"C:\Program Files\Bambu Studio\bambu-studio.exe"]


def verify(built):
    """Slice every plate through Studio itself and read the answer back.

    The parser readback in main() proves the geometry survived the trip; only
    Studio can say whether it accepts the project and keeps its settings. The
    CLI returns 0 only after a full slice, and the config block at the end of
    the exported G-code is the config Studio actually resolved -- so walls,
    infill and brim are checked there, not in the file this script wrote.
    """
    exe = next((p for p in STUDIO if os.path.isfile(p)), None)
    if not exe:
        print("\n  --verify: Bambu Studio not found, skipped")
        return False
    tmp = tempfile.mkdtemp(prefix="plates_verify_")
    version, rows, ok = "?", [], True
    print("\nslicing through Bambu Studio:")
    for plate, r in built:
        d = os.path.join(tmp, plate["n"])
        os.makedirs(d)
        p = subprocess.run([exe, "--debug", "2", "--slice", "0",
                            "--export-3mf", "out.3mf", "--outputdir", d, r["path"]],
                           cwd=d, capture_output=True, text=True, errors="replace")
        m = re.search(r"Current BambuStudio Version (\S+)", p.stdout + p.stderr)
        version = m.group(1) if m else version
        want = {"wall_loops": str(r["walls"]), "sparse_infill_density": r["fill"],
                "brim_type": "outer_only" if r["brim"] else "no_brim"}
        if plate.get("pla_template"):
            # the G-code header shows the template's process; the plate's own
            # regime rides on the objects (see the overrides in build_plate)
            want = template_globals(plate["pla_template"])
        got, weight, mins, why = {}, "?", "?", ""
        try:
            res = json.load(open(os.path.join(d, "result.json")))
            why = res.get("error_string", "")
            with zipfile.ZipFile(os.path.join(d, "out.3mf")) as z:
                for line in z.read("Metadata/plate_1.gcode").decode(errors="replace").splitlines():
                    mm = re.match(r"; (\w+) = (.*)$", line)
                    if mm and mm.group(1) in want:
                        got[mm.group(1)] = mm.group(2)
                    elif line.startswith("; total filament weight [g] : "):
                        weight = line.rsplit(": ", 1)[1].strip()
                    elif line.startswith("; model printing time: "):
                        mins = line.split(": ", 1)[1].split(";")[0].strip()
        except Exception as e:
            why = why or str(e)
        bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        good = p.returncode == 0 and not bad
        ok = ok and good
        verdict = "ok" if good else (f"MISMATCH {bad}" if bad else f"rc={p.returncode} {why}")
        print(f"  {plate['n']:>3s} {plate['slug']:18s} {weight:>6s} g  {mins:>10s}  {verdict}")
        rows.append((plate, p.returncode, got, weight, mins, verdict))
    shutil.rmtree(tmp, ignore_errors=True)

    L = ["", f"## Verified by Bambu Studio {version} — {date.today().isoformat()}",
         "",
         "`python cad/plates.py --verify` sliced every plate through Studio's",
         "own CLI and read walls / infill / brim back out of the exported",
         "G-code. Weight and time are Studio's estimates for the whole plate.",
         "",
         "| plate | rc | walls | infill | brim | filament | print time | result |",
         "|---|---|---|---|---|---|---|---|"]
    for plate, rc, got, weight, mins, verdict in rows:
        L.append(f"| {plate['n']} | {rc} | {got.get('wall_loops', '?')} | "
                 f"{got.get('sparse_infill_density', '?')} | {got.get('brim_type', '?')} | "
                 f"{weight} g | {mins} | {verdict} |")
    L.append("")
    with open(os.path.join(DEST, "PLATES.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n  STUDIO ACCEPTED EVERY PLATE" if ok else "\n  STUDIO REJECTED A PLATE")
    return ok


def rescue_studio_saves():
    """Copy anything the user saved from Studio's window out of DEST before it
    is wiped. main() rebuilds out/plates from scratch, and on 2026-10-04 that
    folder held a project the user had spent an hour setting up by hand (plate
    03 with a PLA support interface) -- the only GUI-valid two-filament file
    in the project. A Studio-written 3mf keeps its meshes under 3D/Objects/;
    the ones this script writes do not, which is how the two are told apart.
    """
    keep = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ref", "studio_saved")
    if not os.path.isdir(DEST):
        return
    for f in sorted(os.listdir(DEST)):
        p = os.path.join(DEST, f)
        try:
            with zipfile.ZipFile(p) as z:
                if not any(n.startswith("3D/Objects/") for n in z.namelist()):
                    continue
        except Exception:
            continue
        os.makedirs(keep, exist_ok=True)
        stamp = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d_%H%M")
        out = os.path.join(keep, f"{os.path.splitext(f)[0]}_SAVED_{stamp}.3mf")
        if not os.path.exists(out):
            shutil.copy2(p, out)
            print(f"  kept a Studio-saved project: ref/studio_saved/{os.path.basename(out)}")


def main():
    rescue_studio_saves()
    if os.path.isdir(DEST):
        shutil.rmtree(DEST)
    os.makedirs(DEST)

    built = []
    for plate in PLATES:
        r = build(plate)
        built.append((plate, r))
        print(f"  {plate['n']:>3s} {plate['slug']:18s} "
              f"{r['n_obj']:2d} obj  {r['used'][0]:5.0f} x {r['used'][1]:5.0f} mm  "
              f"{r['vol'] * DENSITY[plate['mat']]:5.1f} g solid  "
              f"{r['bytes'] / 1e6:5.2f} MB")

    # Re-read every file we just wrote. A 3mf that trimesh cannot parse is a
    # 3mf Studio will not open either, and this is the only check available
    # without a working CLI.
    print("\nre-reading:")
    ok = True
    for plate, r in built:
        try:
            scene = trimesh.load(r["path"])
            n = len(scene.geometry) if hasattr(scene, "geometry") else 1
            back = sum(g.volume for g in scene.geometry.values()) / 1000.0 \
                if hasattr(scene, "geometry") else scene.volume / 1000.0
            drift = abs(back - r["vol"]) / max(r["vol"], 1e-9)
            # The two things Studio flagged on first open: open edges, and
            # objects off the plate. Checked in world space, after transforms.
            leaky = [g for g in scene.geometry.values() if not g.is_watertight]
            off = 0
            for node in scene.graph.nodes_geometry:
                tf, gname = scene.graph[node]
                pts = trimesh.transform_points(scene.geometry[gname].vertices, tf)
                lo, hi = pts.min(0), pts.max(0)
                if lo[0] < 0 or lo[1] < 0 or hi[0] > BED[0] or hi[1] > BED[1] or abs(lo[2]) > 1e-4:
                    off += 1
            good = n == r["n_obj"] and drift < 1e-6 and not leaky and not off
            ok &= good
            print(f"  {plate['n']:>3s} {n:2d}/{r['n_obj']:2d} objects  "
                  f"volume drift {drift:.2e}  open meshes {len(leaky)}  "
                  f"off plate {off}  {'ok' if good else 'MISMATCH'}")
        except Exception as e:                     # noqa: BLE001
            ok = False
            print(f"  {plate['n']:>3s} UNREADABLE: {e}")

    write_card(built)
    print("\n  ALL PLATES OK" if ok else "\n  PLATE READBACK FAILED")
    if ok and "--verify" in sys.argv[1:]:
        ok = verify(built)

    print("\nprojects:")
    L = ["", "## Projects: several plates in one Studio file", "",
         "Slot 1 PETG HF, slot 2 PLA Basic (the saved two-filament template). Map them",
         "in the Print dialog; do not press Sync info.", ""]
    for proj in PROJECTS:
        r = build_project(proj)
        scene = trimesh.load(r["path"])
        n = len(scene.geometry)
        print(f"  {proj['slug']}: {len(proj['plates'])} plates, {n}/{r['n_obj']} objects, "
              f"{r['bytes'] / 1e6:.2f} MB")
        ok &= n == r["n_obj"]
        if "--verify" in sys.argv[1:]:
            ok &= verify_project(r)
        L += [f"### `project_{proj['slug']}.3mf` — {proj['title']}", "",
              "| plate | from | material | carried per object | time | filament |",
              "|---|---|---|---|---|---|"]
        sliced = {pl["n"]: (hm, g) for pl, hm, g in r.get("sliced", [])}
        for k, (plate, rows, used, vol, keep, dropped) in enumerate(r["cards"], start=1):
            hm, g = sliced.get(plate["n"], ("?", "?"))
            carried = ", ".join(f"{a}={keep[a]}" for a in ("layer_height", "ironing_type",
                                                          "seam_position") if a in keep) or "-"
            L.append(f"| {k} | {plate['n']} {plate['title']} | {plate['mat']} | {carried} | "
                     f"{hm} | {g} g |")
        L.append("")
    with open(os.path.join(DEST, "PLATES.md"), "a", encoding="utf-8") as f:
        f.write("\n".join(L))
    return 0 if ok else 1


def write_card(built):
    L = ["# Plates — Bambu Studio projects, one per stage",
         "",
         "Generated by `python cad/plates.py`. Each `.3mf` opens with the H2S",
         "0.4 machine, the 0.20mm Standard process and the plate's filament",
         "already selected, every part in its gated print pose, and per-object",
         "wall / infill / brim overrides applied.",
         "",
         "## Verified through Studio — and three things to still eyeball",
         "",
         "These projects are written directly rather than exported by Studio.",
         "`python cad/plates.py --verify` slices every one through Studio's own",
         "CLI and checks walls / infill / brim in the G-code it produces; the",
         "last run is recorded at the end of this file. (It runs on the macOS",
         "build and on Windows from 02.08; the 02.07 Windows CLI returned −2/−3",
         "with no output.) A slice proves the *CLI* accepts the file and keeps",
         "its settings. It proves nothing about the GUI, which loads the named",
         "system preset and re-applies only the keys listed in",
         "`different_settings_to_system` — plate 01 once opened at the stock",
         "2 walls / 15% grid while the CLI sliced it at 3 / 100%. Nor can it",
         "look at the arrangement for you, so on first open:",
         "",
         "1. Open `01_tpu_regime.3mf`. Fifteen objects should land in one row.",
         "   That is the canary for *does Studio accept the file at all*.",
         "2. Open `06_din_rail.3mf` and read the right-hand sidebar: it must say",
         "   **5 walls, 25% infill, brim outer-only 5 mm**. That is the canary",
         "   for *did the settings survive the load* — the one part where a",
         "   silent reset to the stock 2-wall default would actually cost you.",
         "3. On `04_first_article_a.3mf`, right-click `rear_tie` → object",
         "   settings. It should carry its own brim. That is the canary for",
         "   *per-object overrides*.",
         "",
         "If any of the three is wrong, say so — the generator is one file",
         "(`cad/plates.py`) and a re-run is seconds. Two of its rules exist",
         "because Studio 2.8 rejected the first cut: the header keys a preset",
         "carries (`description`, `filament_id`) must not reach a project as",
         "vectors, and solid parts must use `zig-zag` infill — `rectilinear` is",
         "no longer a value 2.8 recognises and `grid` is refused at 100%.",
         "",
         "A plate's own process is set to the most demanding structural regime",
         "on it, and object overrides only relax from there — so a missed",
         "override over-builds a part, it never under-builds one. Check the",
         "override column against the object list in Studio before slicing.",
         "",
         "## Contradictions these plates had to settle",
         "",
         "Building a real plate forces a decision where two documents disagree.",
         "Three did:",
         "",
         "- **DIN rail brim.** README's per-part table says brim `no`; the build",
         "  plan's stage 6 note says `5 mm brim`. The build plan is the working",
         "  document, so the rail gets the brim.",
         "- **Plate size.** README says the H2S plate is 350 × 320. The machine",
         "  profile's own `printable_area` is **340 × 320**; packing uses 340.",
         "- **Stage 9 weight.** The build plan's stage header says 91 g, but its",
         "  own file list (19 + 39 + 16 + 16 + 18) sums to 108. The plate is",
         f"  108 g. The header is the error.",
         ""]
    for plate, r in built:
        g = r["vol"] * DENSITY[plate["mat"]]
        L += [f"## {plate['n']} — {plate['title']}",
              "",
              f"*Stage {plate['stage']} · {plate['mat']} · {r['n_obj']} objects · "
              f"{g:.0f} g solid-equivalent · packs into {r['used'][0]:.0f} × "
              f"{r['used'][1]:.0f} mm*",
              "",
              f"**Proves:** {plate['proves']}",
              "",
              f"Plate process: **{r['walls']} walls · {r['fill']} infill · "
              f"brim {'on' if r['brim'] else 'off'}**",
              "",
              "| object | qty | walls | infill | brim | override |",
              "|---|---|---|---|---|---|"]
        for n, q, w, f, b, ov in r["rows"]:
            L.append(f"| `{n}` | {q} | {w} | {f} | {b} | {ov} |")
        L += ["", "**By hand in Studio:**", ""]
        L += [f"{i}. {h}" for i, h in enumerate(plate["hand"], start=1)]
        L.append("")
    open(os.path.join(DEST, "PLATES.md"), "w", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
