# Build plan & handoff

The living plan is a Claude doc, readable from any machine:

https://claude.ai/code/artifact/d363e364-c081-4b05-b193-0f9051036d7b

It holds where the build stands, the next steps, the plate results, the open
questions, the CAD changes waiting for the PC, notes for working from the Mac,
and a file map. This file is only the pointer, so the two cannot drift apart.

The project's own site, `bench-hub.html`, has four tabs worth opening first:
**Storyboard** (every finding as a picture), **Catalogue** (exact sizes for
every part and every bought item), **Schematics** (dimensioned views of the
whole bench) and **Checks** (every result sheet, with how far through it you
are read live off disk).

## Where the site lives

    http://bench:8765/bench-hub.html

Since 2026-09-24 that is LXC 106 `bench-hub` on Proxmox node `pve`
(192.168.1.141), serving the same share over NFS at `/srv/bench`; the
`bench` triple in AdGuard points there. After adding a sheet key to
`measure_server.py`, restart it with
`ssh root@192.168.1.5 'pct exec 106 -- systemctl restart bench-hub.service'`.
The Mac launchd agent described below is retired. Historical note: `bench`,
`bench.localdomain` and `bench.home.spacekazak.com` were AdGuard DNS
rewrites pointing at this Mac (192.168.1.189), added 2026-09-20 and following
the house's existing triple convention. `macmini` resolves to the same machine
and works just as well. Both are house-wide, so any device resolves them with
nothing to install.

Port 80 is deliberately NOT used. Binding it needs root, which would run a
file-writing server as root, and it is a single slot on this Mac that the
print-check server (:8080) would still have to share. A pf `rdr` rule from 80
to 8765 is the way to drop the port without a root-owned server, if it ever
matters.

One server carries the whole site AND the result sheets, because a sheet can
only POST its answers back to the origin that served it. Splitting the hub onto
a second port makes every sheet cross-origin and Save fails silently.

    checklist/measure_server.py   serves checklist/ first, then falls back to
                                  the project root (see translate_path)

It runs under launchd as `com.reid.bench-hub`, `RunAtLoad` + `KeepAlive`, so it
survives both a reboot and a crash. Log at `~/Sites/bench-hub.log`.

    launchctl unload ~/Library/LaunchAgents/com.reid.bench-hub.plist   # stop it
    launchctl load   ~/Library/LaunchAgents/com.reid.bench-hub.plist   # start it

The sheets, all on that one port:

    /cleat.html     plates 02e-02i, the cleat gauges
    /fit02.html     plate 02 and its follow-ups
    /measure.html   plate 01 voice sheet -- 127.0.0.1 ONLY, a mic needs a
                    secure context and a LAN address is not one

## Cleat gauges, 2026-09-20

The board's retention is moving off the printed indexing teeth (which barely
catch) and onto the board's own dovetail cleats: a pocket on one rail takes the
male tab, a peg on the other drops into the female notch, and the board goes
straight down onto both. Plates 02e–02i grade the unknowns. Tap the results
into `cleat.html` above; they land in `out/plate2_pla/cleat_results.json`.

**Print plate 02i. It replaces both 02g and 02h.**

Two faults were found on 2026-09-20 and both are fixed on 02i:

1. 02g's cradle gauges were severed by their own tape relief and printed as two
   loose rails. `trimesh`'s `is_watertight` passed them, because two disjoint
   closed solids are each watertight. `cad/cradle_gauge.py` now cuts a
   `RELIEF = 1.2` recess instead of the full `FLOOR`, and every gauge's
   `export()` asserts a body count of one. That assert has since caught a
   second, unrelated floating-geometry bug in `span_gauge.py`.
2. 02h's span strips bracketed 68.58 to 72.39 and were all too wide. The board
   has THREE cleats per edge, not two. Two photo passes then put the spacing at
   66.13 and 02i was cut around that — and none of those fitted either. The
   number is **65.21**, the user's caliper, tip centre to tip centre.
   `span_gauge.py` is re-cut to 64.71 / 65.21 / 65.71 on **plate 02j**, plus
   `span_gauge_slot` whose second pocket is slotted so the spacing stops
   mattering.

Settled and not to be redone, both recorded in `out/plate2_pla/cleat_results.json`:

    PEG_W      3.8     plate 02h, 4 dots -> notch mouth 4.00 or wider
    RAIL_GAP   55.14   plate 02i, 2 dots across -> 0.40 on the 54.74 plain width

**Print plate 02j** (10.82 g, 18m 29s) for the last one. Why the photos were
wrong is worth keeping: both passes agreed to 0.01 mm and both were ~0.9 out,
because they shared one assumption — that the board is exactly 165.1 mm long, a
figure from our own model, never measured. Agreement between measurements only
tests what differs between them. The near-miss on a whole hole pitch was then
taken as confirmation; 65.21 is 25.67 pitches, so the cleats are not on the
grid at all. Calipers for dimensions, photographs for counting features.

## Where it stands, 2026-09-19

Plate 01 (TPU) and plate 02 (PLA gauges) are printed and fully tested, plus
follow-ups 02b (flipped rail stub + foot gauge v2), 02c (O-ring block) and 02d
(two deck stations + stops). Nine constants are settled; results are in
`out/plate2_pla/fit_results.json` and on the Storyboard tab.

## Done on the Mac, 2026-09-26: the recessed ledge is in frame.py

The section below was written for the PC. It never needed one: build123d
0.13 installs from wheels on this Mac (Python 3.14, arm64), so
`~/.venvs/breadboard-bench` now runs `frame.py` here in about nine seconds,
and every gate ran here. The PC and SSH to it are off the critical path.

What changed, all from the plan below with no re-derivation:

1. `cad/frame.py`: TOOTH_*, BB_D_MAX, DECK_STOP_X, `teeth()` and `deck_stop()`
   are gone. The recess block (RECESS 1.2 … FULL_ST / HALF_ST, read from
   `out/board_dims.json`) sits under REAR_AXIS with both asserts. `deck_rail()`
   is Appendix B verbatim; deck plates drop to RELIEF_Z with a 0.3 fillet.
2. Props: the full board is 160 long at assembly 14; the half board sits
   HALF_RIB/2 forward of centre because it registers on the rear shoulder.
3. `check.py` (11 frame parts; the 0.8 plates are waived by name),
   `catalog.py`, `plates.py` (02d and 03 without deck_stop, 02d carries the
   retirement note), `coupon_frame.py` (`ladder_station_stub` is 120 mm).

Gate results, 2026-09-26:

    frame.py            11 parts; deck_ladder 69.6 -> 59.5 cm3 (-10.1, plan said ~11); one body, watertight
    point probes        22 of 22: pocket, well, blocks, land, shelf, relief, stub, slot, shoulder, rib, pegs, nothing above z 3
    coupon_frame.py     ok, stub 24.5 cm3
    check.py            ALL CLEAR (plates waived: deck_ladder, ladder_station_stub, ledge_gauge, deck_pair)
    assembly_fit_check  EVERY MOVE CLEAR; seated: one 5.0 mm3 hit per board = the datum peg through a
                        notchless prop, exactly as predicted; nothing else new
    screws.py           ALL SCREWS OK, bar-end margins unchanged
    plates.py --verify  ALL PLATES OK, Studio accepted every plate; 07 deck_ladder 51.87 g 1h25
    catalog / viewer    regenerated; the hub's main viewer variant now IS the recessed ladder

**Plate 02k printed and judged 2026-09-26: "Yeah it fits nicely."** RECESS
stays 1.2; the result is in `out/plate2_pla/ledge_results.json` (filled from
the verbal verdict and the overhead photos, refine on `ledge.html` if wanted).
The "Ledge (proposed)" viewer variant, `out/frame_ledge/` and its viewer files
are deleted; the main viewer is the real ladder. `cad/ledge_ladder.py` and
`cad/ledge_gauge.py` stay only because plate 02k is printed history and
`plates.py` builds it from them.

Still open after this:

1. Plate 07, the deck ladder, is clear to slice: verified 51.87 g, 1h 25m.
2. `publish_site.py` and the redding-digital push were not run.
3. The seven CAD changes at the bottom of this file are also doable here now.

## 2026-10-05, plate 03 result: the latch was welded at its free end (FIXED in CAD)

**2026-10-06, plate 03 CLOSED.** Chamfer standard (`CLIP_LEAD_IN`); `RAIL_FIT` 0.15; PETG magnet pockets
`MAGNET_FIT_CELL` 0.10 / `MAGNET_FIT_WALL` 0.40, PLA rail caps keep 0.25. All gates green, plate 09
rebuilt (82.4 g, 3h39). Plate 09 still needs its modules added to `PAINT` and the PLA interface done the
plate-03 way before it prints. Results on `fit03.html` were filled from the user's verbal verdicts.

**Later the same evening:** with the welds cut, every release tab snapped off at the first lever: its root
was a 6 x 0.4 x 2.5 sliver (the tab box stopped 0.4 into the finger). Fixed: the tab runs through the
finger. Fit result from the user: 0.15 is "nice and snug with room to slide", 0.25 is loose; `RAIL_FIT = 0.15`
in params.py, plate 09 rebuilt on it. Whether the latch chamfer goes into production is still his call
(clip 4 vs 2). Both clip fixes mean the plate 03 clips in hand are NOT representative of a reprint's tab;
their latch spring and rail fit are.

The user's test: all four clips slide onto the rail stub from the end, none will rock on; forcing the
latch "would break the tab holding the clip to the piece." Cause, found by probing a rebuilt clip: the
release tab stands 6 mm past the jaw, `clip_relief()` stopped 1 mm past it, and every module plate is
wider than the jaw, so the tab's top face fused to the plate -- 6 x 1.1 mm on the gauge, the tab's whole
top on a real module. A finger held at both ends is not a spring. The print review's "a filled relief
slot is a dead latch, it has happened twice" was this same class of fault, never caught in geometry.

Fix, in `cad/bench.py`: `clip_relief()` now also slices over the tab's full reach (`CLIP_TAB_REACH` in
params.py); `din_clip()` builds the tab 0.9 short of the module face; `attach_clip()` probes the plane
under the plate along the finger and across the tab and exits if anything is solid there. All five real
modules and the gauge pass it. All gates green again; plate 03 rebuilt (146 painted triangles).

The printed clips are usable: cut the 1 mm bridge between each release tab and the plate edge with a
knife, then run the `fit03.html` test. Designed latch force is about 4 N for 1.7 mm of travel (14 mm
free length, 1.6 thick, ~2% strain), so a freed latch should feel light.

## 2026-10-17 (night): crown v2, the whole bench as one project, public repo, How I made this

- Crown v2 (user: "make sure it's all nice and solid / but still adheres to our design language"): the socket and
  tongue TAPER 1.0 per side over 14 mm (4.1 deg, self-locking; each 0.1 a print runs fat seats it 1.4 higher), so
  the crown wedges tight under its own weight; ring and stem 5.0 thick (tongue still 3.7), stem flares 28 -> 48
  wide into the ring with r 8 blends, 0.8 front chamfers, pads 7 dia on 45 deg feet, lip columns rounded. 10c is
  now 44 min / 30 g. screws.py checks the taper.
- `project_whole_bench.3mf`: 06x, 07, 08, 09, 10b (10p + 09c's rail bin), 10d, 10c, 11t on eight plates, 19 h 18,
  420 g. A plate's preset and process ride on its objects (OBJECT_KEYS: layer height, ironing, seam, speeds);
  accelerations and travel speed are project-wide and are reported as dropped. Pauses go per plate
  (MultiAsSingle). 18 TPU feet: plate 07f, own file (a third filament needs one GUI save first). Opened in the GUI:
  eight named plates, no error.
- TEMPLATE_2F moved to `ref/templates/h2s_petg_hf_pla_basic.3mf`, a copy of the user's 09 save with the
  DesignerUserId blanked, so it can be public.
- Public repo: https://github.com/InMyPajamas/breadboard-bench (cad, checklist, out/plates, out/step, docs,
  ref/templates; renders, other out/ and vendor STEPs ignored; ref/README.md says where to get them).
- Hub: new tab "How I made this" (#made). `publish_site.py` now skips renders/*_frames (4 GB of film frames).
  Published to redding.digital (www), project entry links the repo.

## 2026-10-17 (evening): mic crown (plate 10c) and the first multi-plate Studio project

User: "bring up the case for the screen. I have not printed the thicker one yet", "also add the part that will
help us get more stuff on the din rail and the part mic that sits on top of the screen", "Is there a way to put all
these parts in a 'project' for bambu". Because 10d is unprinted, the backplate gained a dovetail socket on its top
rim (block x +-14, y 39..55, channel 18 wide at a 1.2 floor, walls 30 deg off vertical, open at the top end).
`mic_crown()` (PETG, prints flat): dovetail tongue (0.25 clearance a side) + a ring r 28..54 behind the board,
board centre at display y 110 (7 mm above the screen's top). Seeed's STEP corrected the old note: the XVF3800 has
THREE M2 holes, (0, -34) and (+-21.35, 24.5); the 66 x 66 square is the mics (bottom-port, holes r 0.5). Board
turned -90 so its USB-C points along -x; pads 8.0 under the PCB (deepest back part 6.74), pins 1.8 in two holes;
fixed lips at -120/-60 deg, a sprung lip at 75 deg on a 27 mm beam cut free in the ring (bends in the layer plane,
0.9 % strain to pass the edge). Zero screws. Gates: screws.py (crown snap check), fit check (crown slides down
POST_U clear; the board's snap is CLIP_ON), check.py ALL CLEAR, plates --verify all OK.
`plates.py` now writes PROJECTS: `out/plates/project_screen_mic_din.3mf` = 10d + 10c + 11t on three named plates,
config taken whole from the PETG + PLA template (slot 1 PETG HF, slot 2 PLA Basic), each object pointed at its
plate's slot, plates laid out on Studio's grid (ceil-sqrt columns, 1.2 x bed pitch, rows toward -y; checked on a
Studio-saved 3-plate file). `verify_project()` reads Studio's own slice_info: every plate on its bed, one filament
each: 54 min / 30.7 g PLA, 44 min / 25.0 g PETG, 1 h 13 / 34.1 g PETG. Opened in the GUI: three plates, names shown.
`lighten()` now falls back to oriented boxes when hulls are not enough (the XVF3800 is 998k triangles).

## 2026-10-17 (later still): the twist lock goes screwless, plate 10L

User after printing 10p: posts "much stiffer", but the lock "a little weak ... maybe 100 grams max", then "I didn't
see we were screwing these wing clips in too. Anything simpler. Less m3 screws the better." The M3 x 16 joining
wing and hook had been left out, so the hook sat loose. Now display_lock = hook + its own shaft (r 3.45 in the
posts' unchanged 3.8 bore) + hex (AF 5.4) + split barbed tip (prongs r 2.6, barbs r 3.0, slot 1.4);
display_lock_knob = wing with a hex socket and a 5.5 neck the barbs click through (0.25 catch). No screw, no nut;
fits 10p's posts as printed. The lock prints on its side, tooth up, flat 2.6 under the axis, so the prongs flex in
the layer plane. Plate 10L (2 locks + 2 wings): 14 min, 3.9 g. Hardware drops to M3 x 16 x 4, nuts x 8.
screws.py checks the snap by sizes. 11t's lock is the same part.

## 2026-10-17 (later): DIN tilt adapter, plate 11t

User: a generic DIN device (UniFi UA-Hub-Door-Mini, 113 x 66 x 27.6) "is too long to be able to clip down far
enough"; asked for the rail to "rotate on teeth ... flat or various degrees". Measured: 39 mm below the rail's
centreline to the rear tray against 45-57 for 90-113 mm devices. User chose an adapter over rotating the whole
rail (that would reprint both frames, the rail and the tray and lose the middle supports). din_tilt_base = the
display post's foot (hook over the top lip, latch=False, the same twist lock) + a fixed 24-tooth hinge knuckle;
din_tilt_arm = moving knuckle + carrier + 40 mm TS35 stub; din_tilt_knob = thumb knob with a pressed nut. One
M3 x 20, head pressed into the base. Teeth (hirth(), radial V, 1.2 high, r 4-10.5) are phased from FLAT
(DTA_FLAT 53 = 90 - the posts' 37): stops at flat, -38, -23, -8, +7, +22, +37; mesh is exactly 0 at a stop, 46-49
mm3 between (kernel-checked). 0.3 face clearance (0.15 clashed after tessellation). At the right end (x 262, rail
bin removed) the hub clears the bench at every stop flat..+22; +37 hits the half breadboard. At the left end it
collides with the screen when tilted. Plate 11t: base, arm, knob + one lock hook/knob, PETG, no supports, 1h09.

## 2026-10-17 (later): the keeper is replaced by a TWIST LOCK

User on the keeper: "not sure I like these, magnets?" Magnets weighed: two 6 x 2 N52 per post on the rail-screw
heads (posts moved onto the buttress stations) hold ~8 N a post; a 10 N press near the screen's top edge asks
~15 N at the foot. Rejected. User picked a twist lock: display_lock_knob (thumb wing 9 x 22 on the foot's front,
shaft r 3.5 through a 3.8 bore, hex key on its end) + display_lock_hook (hub r 5.4 under the foot, tooth sector
+-30 deg, 2.2 under the lower lip, WEDGE top 5.75 -> 6.3 against the lip's 6.2: the last of the clockwise
quarter turn draws the foot down). One M3 x 16 through the wing into a nut pressed into the hook makes them one
part round the foot, 0.3 running play. Swept in CAD: 0.06 mm3 of wedge at locked, free from 20 deg open,
clear of the lip open. Wing along the post = locked. Plate 10p: 2 posts + 2 hooks + 2 knobs, 1h11, 33.5 g.
Hardware: M3 x 16 x 6 (4 screen, 2 locks), M3 x 12 x 14, nuts 10. screws.py's bolt() tests multi-part joints
part by part (a shared face fooled the ray-parity test). Film re-rendering with the lock turning at the start.

## 2026-10-17: screen bosses bolted; the posts' latches replaced by screwed keepers

Two breakages, same cause: plastic doing a job steel should do.
1. Screen bosses (plate 10d, printed): "the screw holes and cylinders that hold the screen are just too narrow.
   They end up breaking in half from the stress and just spinning." 6.4 bosses, 2.5 self-tap pilot, 1.7 wall,
   11.5 tall printed upright: a thread-forming screw loads the boss in hoop tension across the layers. Now
   DBP_BOSS_R 5 from the bed up, 3.4 bore, M3 nut pressed (DBP_NUT_AF 5.7) into a 4.0 hex pocket in the back,
   M3 x 16 from the front (tip 0.4 past the nut). Nearest part on the PCB back is 7.0 from a hole centre.
   Backplate walls 3 -> 4 so the boss rings print solid. Plate 10d: 46 min, 31 g.
2. Display posts: "Both of our clips also broke ... the one that actually clipped onto the rail from the bottom."
   The screen's weight and every touch press tip the post's top into the rail and lift its foot; the only thing
   holding the foot was the 1.8 latch finger (~30 N per tooth for a 10 N press). Posts now have NO latch
   (din_clip/attach_clip latch=False) and a keeper (display_keeper, PETG, 4 walls 100%): slides up a slot under
   the foot, tooth under the lower lip (lip edge is its stop), M3 nut pressed in its underside, M3 x 12 from the
   post's front. Install: hook the post (or the whole screen unit), rock flat, keeper in through the 12 mm gap
   between foot and tray rim, slide up, screw. Plate 10p = 2 posts + 2 keepers, PETG + PLA interface, 3h01.
Gates: screws.py has a bolted-joint check (shank clear, nut pocket >= 2.4, full thread, wall round the nut);
assembly_fit_check walks the keeper's two-leg move (DOGLEG). plates.py: pla_template plates now write
per-object overrides against the TEMPLATE's process -- they were silently dropped (09c's posts printed at
15%/no brim; 10p's keepers would have lost their 4 walls). Hardware: 4 more M3 nuts (10 total), 4 x M3 x 16
for the screen, 2 x M3 x 12 for the keepers. Film re-rendering with the new parts.
Print orientation (user: "they seem to be splitting layers ... 45 degree tilt for strength?"): the posts printed
upright (pose 90, 144 tall), so every layer line crossed the post and the screen's moment bent it across them.
Now FRONT FACE DOWN (("X", 180)): layers and 4 perimeters run the post's length; 45 degrees would only halve the
problem and need support everywhere. The foot is full 30 width to y 21.5 (was 10) so the clip plate no longer
overhangs; the one painted face is the hook tooth's (z 6.7, PLA interface). Posts 4 walls 40%, no brim. Plate 10p:
1h01, 30.7 g (was 3h01 upright). Keeper stays upright (its tooth bends along the layers); backplate stays flat.

## 2026-10-16: every screw starts straight -- start + track gate

User: "small predrilled spots with tracking so the screw doesn't end up coming out the side of the plastic."
screws.py now measures every self-tapper from the STLs (rays fanned round the real axis): pilot runs past
the tip, solid wall outside the thread crest, and something that steers the start. The 14 structural joints
already had it -- clearance bore in the clamped part, 2.5 pilot in the other: bar ends wall 1.31-1.36, bore
3.4 x 2.5; rail into frames wall 2.5+, bore 3.4/4.2 x 4.0; rail into buttresses wall 1.53, pilot 1.3 past
the tip. The screen into the backplate bosses had nothing ahead of the pilot but the PCB's 1.7 mm slot:
added a 0.6 x 45 lead-in cone (DBP_LEAD_IN, mouth 3.7 > the 3.2 slot). Plate 10d rebuilt; not printed yet.
Assembly: the posts lean back 37 degrees and their nut channels open at the back, so loose nuts fall out on
the bench -- join backplate and posts on the table, posts face-up with the clip feet off the edge so the backs lie
flat, then clip the unit on.

Field repair, same day: one rail screw into a mid-rail buttress (pilot 2.5 x 9, wall 1.5) stripped on
assembly (photo). Not reprinted -- the tray is the buttress. Fix given: superglue on the LOWER threads of an
M3x12 only, driven by hand until the head seats, cure 1 h. No bigger screw or heat insert: a 3.5 thread or a
4.0 insert hole leaves ~1 mm of wall, the blow-out the start + track gate exists to prevent.
If the rail ever has to come off, that one screw is glued: a firm twist with the hex key breaks it free.

## 2026-10-15: CrowPanel P4 backplate

Screen confirmed: Elecrow CrowPanel Advanced 7" ESP32-P4, 1024x600, no camera, no case. Elecrow's own STEP
is in ref/crowpanel7_p4 (the S3's in ref/crowpanel7_s3): PCB 176.9 x 104 x 1.7, four corner M3 slots at x
+-85.5, z +-47.4..50.6, tallest back part 8.1 mm. The posts (100 apart) cannot reach the corner holes and
their screws would land on components. display_backplate() (bench.py, constants CP7_*/DBP_* in params.py):
open rim on the hole centrelines, two 14 x 6 bars at the posts' +-50 with M3 x 8 cap counterbores on the
front at +-20, four corner bosses to the PCB at 9.5 mm standoff (1.4 clear, checked against the STEP). The
real STEP replaces the box prop (prop_cp7_body/glass/ui). Plate 10d, PLA, 48 min. Hardware: 4 M3 nuts -- the
hex nuts on hand (DIN 934, 2.4) fit the 2.2 channel standing 0.2 proud of the post's back into free air, as
established 2026-09; the M3 x 8 tip lands flush with the nut's back face, full engagement. Corrected
2026-10-16: this entry first said hex would not fit. Plus 4 x M3 x 8 cap, 4 x M3 x 12 cap.

## 2026-10-10: clip latch rebuilt after a display-post clip broke

User: "one of our rocker clips broke on the screen stands. They are definitely a little brittle." Cause, by
beam theory: the latch's FREE span between root and tooth was 7 mm (the 18 mm latch was mostly tooth and
tab), and the tooth must pass the rail lip by 2.05 mm -> ~10 % root strain against PETG's ~4 % yield and
~80 N to snap on. The docstring's "0.6 %" had used the whole 18 mm and <1 mm deflection. Now the latch
runs the clip's full width at CLIP_LATCH_T 2.0 (params.py): 18 mm free span on a 30 mm clip, ~1.9 %
strain, ~9 N. Fit surfaces (tooth, lead-in, RAIL_FIT) unchanged. Relief slot stops 0.6 past the tip so it
never notches a module body. Post support-paint window 8.5 -> 8.0 (the thicker latch's underside moved to
8.42). Plate 03c = two test clips, PETG-only supports, 53 min. 09p = replacement post, 2h51. The printed
rail bin and second post still carry the old latch: handle gently.

## 2026-10-09: buried head magnets ADOPTED, round head pockets

Plate 10m (two coupons): 0.45 skin docks firmly and holds its disc dead still; 0.85 rattles. User: three
magnets plus the parts' own feet make the 0.45 grip enough, and rattle is not acceptable. frame.py now has
HEAD_SKIN / HEAD_SLOT_* / SIDE_BW / head_pocket() / head_slot(): side_bin and side_tray seal their head
discs in an on-edge slot (the coupon's exact size) behind a one-line skin, and the head pockets are
round-topped arches (a closed circle would break through the underside; the parts drop on vertically).
Back wall 5.9 -> 6.65. plates.py takes a list of pauses and refuses one that is not a layer top; plate 09
pauses at 3.2 (floor discs) and 7.04 (head discs). All gates green. The printed side parts still work with
their open seats; reprinting 09 (2h31) gets the new design. HA pause announcement tells the two pauses apart.
Then: side tray cavity 10.4 -> 18.0 (three M3 pan heads across; user), tray 26.3 wide, nose fillet tied to
W. Found and fixed on the way: the assembly's side-part pad placements still used the old back-wall formula
(0.375 off their pockets) -- they use SIDE_BW now. Plate 09 2h37.
Then: a scoop (Gridfinity-style cove) along the inside of the tray's outer wall, full depth through the middle
cells and lofted down to 0.6 mm over the two end cells (user: taper so it doesn't end on a ledge); rim's inside
edge rounded 0.3. Then the scoop runs out to a 0.85 mm (two-line) lip at the rim (TRAY_LIP_L; wall 0.97 at
1 mm down, 1.38 at 2 mm); the cavity's corner radius is now tied to the body's, after the thin wall broke
through the nose in a render. Plate 09 2h37.

## Queued 2026-10-09: buried head magnets -- test coupon first

User: the sideways head-magnet seats in the side tray and side bin are "a bit awkward"; they would
rather the parts just snap on with nothing to fit after the print. Burying a disc puts PETG between it
and the steel screw head, and pull falls fast with gap (D6x2 N52, image-method model):
0.4 mm -> 46 % kept, 0.6 -> 35 %, 0.8 -> 27 %. Both parts stand on their own TPU feet, so the magnets
only dock them -- a weaker snap may still be enough. Correction from the real section (hub
Storyboard 34): the head pocket already keeps 0.3 mm over the head and the skin is a VERTICAL wall
(one 0.45 line minimum), so the realistic gap is 0.75 mm -> about 29 %. Decide by test, not by model:
a small PETG coupon, discs dropped in at a pause, sealed under 0.4 / 0.6 / 0.8 mm plus one open
(contact) seat, tried against a real M3 DIN 7985 pan head. If one skin docks well, re-cut the head
seats as pause-and-insert (a second pause in plates.py `pause_z`, disc on edge or re-oriented).
BUILT 2026-10-09 as plate 10m (`skin_coupon()` in coupon_frame.py): 4 coupons, a slice of the bin's back
wall each on a 1.0 plinth; nubs 1/2/3 = skin 0.45/0.65/0.85 (measured on the STL), no nubs = today's open
seat. Pause 8.0 baked in; 23 min at 0.20 Standard, 15% infill (skin is a wall, so layers and infill do not change the test), pause 17 min in.

Result 1 (2026-10-09, cut to 2 coupons): the 0.85 coupon's disc rattles in its slot (the designed 0.3 / 0.4 play);
the 0.45 one is solid -- a one-line skin prints slightly into the slot and takes the play out. Snap test on a
real head still to do.
## 2026-10-08: ladder passed, frames + tie + rail printed, post window closed

Plate 07 (ladder, 0.08 mm, ironed) lifted: "both boards fit great". Plate 06x (both frames, tie, caps,
rail on one bed, 2h20) printed; the frames flexed at the bar-end screw hole: the foot bar's three lightening windows left a 5.2 mm
bar with the 3.4 mm screw bore through it. `end_frame()` now has `BAR_WINDOWS = ()` and `POST_WINDOWS = ()`
(both closed; the frame is 20.3 cm3, was 17.2) and plate **04x** (both frames only) reprints them. Hub gained an **Assembly** tab: the 1080p build film
(`renders/build_frame_fhd.mp4`, 426 frames, collision-checked order, rendered half on the Mac and half
on the PC's 5070 Ti over SSH -- RDPC4 has OpenSSH since today), nine step stills, a CAD-to-real slider
waiting for `renders/assembly/real_final.jpg`. Plate 09 is painted and ready except the PLA interface.
Left: 04x, 07b, 08, assemble, 09, stills + morph.

## 2026-10-07: plate 07 printing; what is left, in order

02l (half-bay gauge) passed; plate 03 closed (RAIL_FIT 0.15, chamfer standard, PETG magnet pockets
6.10 floor / 6.40 wall); side bin's return and tongues removed. Plate 07 is printing at 0.08 mm with
ironed tops (height-range modifier 3.1-8 mm un-ironed, added in Studio), along Y, seam Back, no brim.

    07  deck ladder        PRINTING 2026-10-07, 4h46      test: both boards, a pad in a pocket, 288.00
    06  DIN rail           ready, 1h03                     counterbores + skin layer
    04  left frame+tie+caps ready                          first article; mortise 0.15, O-ring glands 0.80
    05  right frame        ready
    07b TPU pads x14       ready, 28m                      the +0.30 pockets are in every part now
    08  rear tray          ready, 1h06
    09  PETG modules       NOT ready: add the five modules to PAINT in plates.py, then the PLA Basic
                           interface the plate-03 way (edit values in a Studio-saved file), door closed

The hub's Overview, Build plan (state chips per stage) and Storyboard (panels 32-33) say the same.

## 2026-10-05: all parked CAD changes are in; plate 03 printed; plates 04-08 unblocked

Every row of the living doc's "CAD changes waiting for the PC" table is now closed, on the Mac:

    RAIL_FIT_MORTISE      0.15, its own constant (was tied to RAIL_FIT 0.25)                     done
    Foot pocket           pad nominal + FOOT_POCKET_OVER 0.30 -> 16.3 x 6.3, mouth flared 0.3;   done
                          measured off the STLs on ladder, tray, bin; frame notch 16.3 long
    RAIL_PAD_D            0.80 gland for two 3 x 1 O-rings per station; rail_pad() and the TPU   done
                          gasket are gone (frame parts 11 -> 10), plate 01 carries a history note
    Rail screw seat       6.0 x 3.2 counterbore, M3x12 cap, one sacrificial layer (2026-10-04)   done
    Ladder end pilots     re-cut after the ledge fill; all four clear to 18 mm (probed)          done
    Side bin foot pocket  pad placed on the pocket's centre (W/2 = 17.75, was a literal 17.5)    done
    Ladder teeth, BB_D_MAX                                                                       obsolete (recessed ledge)
    Foot pad size tags                                                                           not done, nice-to-have

Gates after all of it: frame.py 10 parts, no chamfer warnings (deck_rail now chamfers BEFORE cutting the
flared pockets, or OCCT drops the chamfer); screws.py ALL OK (ladder end screws read 7.92 mm of bite, the
true figure -- the old 10.80 counted the plastic that blocked the pilot); check.py ALL CLEAR; fit check
EVERY MOVE CLEAR; plates.py --verify ALL OK. Catalogue, renders, viewer and hub re-injected. One screw
(M3x12 cap x14), 17 magnets (D6 x 2 N52, confirmed by the user), 8 O-rings.

**Printed:** plate 03 (PETG clips + magnet gauge, PLA Basic interface), 2026-10-05, no errors. Sheet
`fit03.html` (key `plate3`) awaits the user's clip test; the 02b stub was thrown away, so plate **02r**
(the rail stub alone, 7 g, 10 min) exists as the clip target.

**Next prints, all unblocked:** 07 (ladder: half-bay test + a pad in a pocket), 06 (rail), 04, 05, 07b, 08.
Plate 09 waits for plate 03's RAIL_FIT and latch-chamfer answers, and needs its clip modules added to
`PAINT` plus a PLA interface made the plate-03 way (edit values in a Studio-saved file).

## 2026-10-04: rail counterbore done; plate 03 with PLA interface; Director's order

**Rail screws (one of the seven parked changes) are DONE.** `bench.din_rail` now cuts a 6.0 x 3.2
counterbore per mount hole (`RAIL_CBORE_*` in params.py) with a one-layer sacrificial membrane across the
bore at the pocket floor, because the rail prints clip-face down and the seat is a roof. All eight rail
screws are M3x12 cap (`RAIL_SCREW_L = 12`), seated on the pocket floor. Gates: frame.py 11 parts,
screws.py ALL OK (6.8 mm bite in the frames, 6.0 in the buttresses; the membrane is allowed by name),
check.py ALL CLEAR, fit check clear, plates verified. catalog.py now lists one screw, M3x12 cap x14.
NOT yet done from the parked list: foot pockets +0.30 (FOOT_L/W still 16.0 x 6.0 -- blocks plate 07),
RAIL_PAD_D 1.0 -> 0.80 for the O-rings, RAIL_FIT_MORTISE 0.25 -> 0.15, and whatever else the living doc
lists. Site refresh (catalog/render/inject/viewer) not rerun after this change.

**Plate 03** ships single-filament with the support paint written in (`PAINT` in plates.py). The PLA
interface is added by hand in Studio; the two-filament file plates.py can write is rejected by the GUI
(see `interface=` note on the plate). The finished two-filament plate is `ref/studio_saved/03_petg_gauges_READY.3mf`, made by editing values in the user's own Studio save; plates.py rescues Studio saves before wiping out/plates. Bambu's guide and preset: `ref/bambu_mutual_support/`. PLA BASIC,
230 C, bed 60 C both, door open, 3 interface layers. The user is printing 03 with the full rail added.

**Systems Director, 2026-10-04:** plate 03 + the CAD changes now; then plate 07 as the half-bay test
(not before the foot-pocket fix); then 04, 05, 06, 07b, 08; plate 09 last, after 03's clip results;
public site refresh once at the end. No half-bay gauge.

## The one thing to do next, 2026-09-23: the recessed ledge — the plan for Opus

Written by the Fable session that drew the pictures, for whichever session does
the CAD on the PC. Pictures first, then the numbers, then the steps in order.
Everything marked DECIDE is a judgement left open on purpose; everything else
is settled by a gauge, by frame.py's own arithmetic, or by the Plan agent's
grep of every file that touches the ladder (its full report is at the end).
The living doc at the top of this file should get a pointer to this section.

**Pictures:** `renders/story/ledge_pocket.png`, `ledge_seated.png`,
`ledge_peg.png` — Storyboard panel 28 and the Gallery's cleat row on the hub.
Scene source `cad/ledge_scene.py` (manifold3d, runs on the Mac). The hub's
3D viewer has a **Ledge (proposed)** variant, staged by `cad/ledge_ladder.py`
into `out/frame_ledge/` from these numbers -- delete that script and rebuild
the variant from `out/frame` once frame.py exports the real ladder. The real
build123d edit is `cad/frame.py`, PC only.

### What the user asked for, in their words

1. Delete the teeth; the board slots straight down between the rails, held by its own dovetail cleats.
2. Keep a small rest, so the tabs are not holding all the weight.
3. Keep it minimal — "simply squishing the rails basically".
4. "If it's easier to keep the ledge that held the grooves/teeth and just put the slots / teeth there that is fine too."
5. "I don't want a weird wall or something that is 'higher' than the half rails."
6. "It should ideally sit into the same area the bar/ledge consumed."

### Confirm with the user first — two caliper readings already on record

1. The board's tape is 0.6 thick and set back 0.6 from the edge (user's caliper, 2026-09-20, in memory), so the bare rim is only 0.6 wide. Both numbers shape the floor below; re-check them, it takes a minute.
2. Add TAPE_T and TAPE_SET fields to the Boards tab so they land in `out/board_dims.json` and the CAD reads them instead of carrying literals.
3. The full board is ~160 long, not 165.10: the ruler said so on 2026-09-23 and the photo, corrected for parallax off the 20 mm block, agrees (159-162). Seeded into the Boards tab.
4. Nobody has measured the first cleat's distance from the board's end, and the user has said the measuring is done. So the design tolerates it instead: the full board's left end sits 3 mm clear of the 5 mm ledge stub (FULL_X0 8), and a ±2 error there only moves the board along the rail, because the pocket finds the tab wherever it is. END_TAB on the Boards tab is optional and overrides the centred-cleats assumption if it is ever taken.

### The design in seven lines

1. The ledge stays exactly where it is (z 0..3, out to RAIL_R + LEDGE = 12.5 rail-local) and so do both rail axes. Its top is cut down 1.2 from the arc outward; that cut is the channel, the board sinks into it, and its underside becomes BOARD_Z = 1.8.
2. Where the arc meets that floor it bulges to y 7.79, past the tab tip, so a flat **land** is cut at y 7.42 (the arc's own y at z 3) from the floor up to z 3 — a sliver 0.37 deep at the floor tapering to nothing. It is the pocket's back wall.
3. The bare rim is 0.6 wide before the tape starts, so the floor at 1.8 is a 0.6 **rim shelf** just outside each bearing face — the small rest — and beyond it the ledge drops to a 0.8 **relief** the tape never touches. The pocket floor between the blocks is 0.4 lower still, so a tab with flash can never carry the board; the rim does.
4. Front rail: at each station two 3.5-wide blocks of un-cut ledge stand from the land out to y 9.13, flanking the tab; the gap between them is the pocket (4.37 at the datum station, a slot elsewhere). Their outer faces are the front stop.
5. Rear rail: a 1.71-wide strip of un-cut ledge (y 7.42..9.13) runs the rail's length — the **shoulder**, the rear stop the board's far edge bears on at every point — and at the datum station a 3.8 × 1.3 peg of it stands into the notch. In the half board's bay the shoulder stands 0.8 further out, because that board is 0.8 narrower.
6. Nothing is above z 3 except the rail's own crown. 9.13 is (REAR_AXIS − FRONT_AXIS − RAIL_GAP) / 2 = (73.4 − 55.14) / 2 and it is also BOARD_EDGE − PLAY = 9.33 − 0.2; 9.13 − 7.42 = 1.71 = the proven POCKET_D. `frame.py` asserts both identities so nothing can drift.
7. The three deck plates drop from z 3.0 to 0.8 (the relief plane). `deck_stop`, `teeth` and every TOOTH_ constant go; the pockets are the stops. Only `deck_ladder.stl` and its coupon change — frames, tray, bin, screws and sockets are untouched.

### The numbers

Settled (`out/plate2_pla/cleat_results.json`, `out/board_dims.json`, memory):

    RAIL_GAP 55.14   POCKET_W 4.37   POCKET_D 1.71   FIT 0.30   PEG_W 3.8   PEG_D 1.3   RIM 0.6
    tab 4.07 tip / 3.85 base / 1.41 proud / 5.20 tall        notch 1.60 deep      tape 0.6 thick, set back 0.6
    full board ~160 x 54.74, 3 cleats at 65.21               half 81.89 x 53.94, 2 at 53.51
    (full length: ruler + photo 2026-09-23, ~160. The 165.10 carried until then was our model's number,
    never measured -- the caliper only reaches 150. Measure END_TAB instead, see 'Confirm with the user')

Derived — compute in code, never type the literals:

    RECESS     1.2                                   D: tab and notch engagement  (DECIDE, step 1)
    BOARD_Z    LEDGE_Z - RECESS              = 1.8   board underside = the rim shelf
    RELIEF_Z   BOARD_Z - TAPE_T - 0.4        = 0.8   floor under the tape zone, four layers
    PLATE_Z    RELIEF_Z                      = 0.8   deck plates, fillet 0.3 (1.4 cannot exist on 0.8)
    LAND_Y     sqrt(RAIL_R^2 - LEDGE_Z^2)    = 7.42  the land; tab tip 7.72 at the front stop, 0.30 clear
    BOARD_EDGE _HALF_SPAN - BB_D / 2         = 9.33  board edge, centred
    PLAY       0.2                                   per side; 0.4 total, the 55.14 gauge's clearance
    FACE_Y     BOARD_EDGE - PLAY             = 9.13  block outer faces AND the rear shoulder face
                                                     assert FACE_Y == (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2
                                                     assert FACE_Y - LAND_Y == POCKET_D, both +-0.02
    SHELF_Y1   FACE_Y + RIM                  = 9.73  rim shelf ends; rim overlap 0.6..0.2 over the play, never tape
    POCKET_WELL 0.4                                  pocket floor at BOARD_Z - 0.4 between the blocks
    BLOCK_L    3.5                                   each flanking block, along the rail
    SLOT_REACH 3.0 at station 2, 4.0 at station 3    slots 10.37 and 12.37; station 3's error is twice station 2's
    HALF_RIB   BB_D - HALF_W                 = 0.80  shoulder and shelf step out by this in the half bay, x 182..269
    END_STUB   5.0                                   full ledge kept at x 0..5 and 283..288: the frame shoulders. 5, not 6:
                                                     the full board starts at rail-local 6, and a recessed board needs its end face clear of the stub
    bays       FULL_X0 8.0    HALF_X0 184.0          RAIL-LOCAL. build() places the ladder at assembly x 6 (asm_ladder.stl spans
                                                     3..297 with ENGAGE). The half board is today's prop (assembly 190); the full board
                                                     moves 2 mm right (assembly 14) so its end clears the 5 mm stub by 3, not 1

Stations, rail-local x = X0 + L/2 + (k − (N−1)/2)·SP, read L / SP / N from
`out/board_dims.json` the way `cad/board_dims.py` does, with the literals as fallbacks:

    full    22.79  datum: pocket 4.37 + peg 3.8      88.00  slot 10.37      153.21  slot 12.37   (L 160, cleats assumed centred)
    half   198.19  datum: pocket 4.37 + peg 3.8     251.70  slot 10.37
    (rail-local; add 6 for assembly coordinates: 28.79 / 94.00 / 159.21 and 204.19 / 257.70)
    The full board's stations assume its cleats are centred, which nobody has measured; FULL_X0 8 gives
    its end 3 mm of stub clearance so a ±2 error only moves the board along the rail. END_TAB on the
    Boards tab overrides the assumption if it is ever taken.

One exact pair locates each board. The slots exist because the caliper said
65.21 and every strip cut to 65.21 missed while the slotted strip fit: the
spacing lives somewhere in 62–68 and the slot absorbs it.

### frame.py, in order

1. **DECIDE RECESS.** 1.2 (the Plan agent's number) keeps the relief floor and the plates at 0.8 = four layers; the advisor's 1.5 would put both at 0.5. If the station-stub gauge shows tabs climbing out at 1.2, the 1.5 route is: cut the relief to z 0 between the stubs and move the deck plates into the bay gaps (x 2..10, 179..192, 278..284) at full 3.0 thickness. Not below 1.2.
2. Constants (lines 74–122): delete TOOTH_P/H/Y0/Y1, BB_D_MAX (it only fed TOOTH_Y1), DECK_STOP_X; keep `_HALF_SPAN` (it feeds BOARD_EDGE); replace `BOARD_Z = LEDGE_Z`; add the derived block above, with its two asserts. Appendix B has it typed out.
3. `deck_rail(ledge_side)` keeps its signature (front +y, rear −y). Build: the half_round exactly as today (`holes_skip=FOOT_X`, unchanged — see step 6); + the ledge box exactly as today; then ONE compound cutter: (x 5..283, y LAND_Y → past the ledge, z BOARD_Z..LEDGE_Z + 1) — the channel and the land in one box — plus (x 5..283, y SHELF_Y1 → past the ledge, z RELIEF_Z..LEDGE_Z + 1), the relief; in the half bay on the rear rail both start HALF_RIB further out. Every feature is then a box SUBTRACTED FROM THE CUTTER (kept ledge), never added to the rail; that is the whole design. If OCCT chokes on the compound, apply the cuts sequentially and re-add the keep boxes — same result, they lie entirely inside the original ledge.
4. Front keeps, per station: two blocks (x station ± gap/2 outward by BLOCK_L; y 0..FACE_Y). Then the well: box(x station ∓ (gap/2 − 0.05), y LAND_Y..SHELF_Y1, z BOARD_Z − POCKET_WELL..BOARD_Z + 0.1) subtracted from the rail. gap = POCKET_W at the datum, POCKET_W + 2·SLOT_REACH elsewhere.
5. Rear keeps: the shoulder (x 5..283, y 0..FACE_Y); the half rib (x 182..269, y 0..FACE_Y + HALF_RIB); the datum pegs (x station ± PEG_W/2, y 0..local face + PEG_D). Nothing at the other rear stations.
6. Cross-bores: **nothing to do.** In `deck_rail()` the bores are cut inside `half_round()` before `rail += box(ledge)`, and the ledge box refills every bore within y 0..12.5, z 0..3; shelf, blocks, shoulder and pegs are all refilled material. Only the bore mouths above z 3 show on the arc, as today. Optional cosmetic: add the station x's to `holes_skip` so no mouth sits behind a tab.
7. `BOARD_Z` is picked up by `props()` automatically. `props()` line 1569 (`190.0 + HB_W / 2`) stays; the full board's prop moves from assembly 12 to 14 (FULL_X0 8 + the ladder's 6) and its 165.1 length becomes the measured 160.
8. Delete `teeth()` (527–543) and `deck_stop()` (684–717); in `build()` remove `"deck_stop": deck_stop()` (1438) and the `asm_stop{i}` placements (1484–1486); remove `"deck_stop": 2` from QTY (1622).
9. `deck_ladder()`: plates `box(..., 0, LEDGE_Z)` → `(..., 0, RELIEF_Z)` (671); fillet 1.4 → 0.3 (673); rewrite both docstrings (547–562, 647–660): the plates are rungs under the tape zone now, never touched.

### Every other file that names the old design (the Plan agent's grep)

1. `check.py`: delete the `"deck_stop": ("Y", 90)` pose (117); FRAME expected count 12 → 11 (437).
2. `catalog.py`: delete line 103 — it forces a `deck_stop` row and `resolve_stl` would SystemExit; delete 47 / 62 for tidiness; fix the prose at 55 ("sit on its toothed ledges" → "drop into pockets and onto pegs cut into its ledges"), 70 ("indexing teeth" → "first pocket, first peg"), 260–261 ("On the ladder's toothed ledges" → "Recessed into the ladder's ledges").
3. `plates.py`: plate 03 (424) remove `("deck_stop", 2)`; plate 02d (262) remove it too and add a hand line "deck stops retired 2026-09-23: the board's cleats locate it now" — 02d is printed history, the record stays but the object must go or `build()` exits; plate 07 (466) add the seam note below.
4. `assembly_sequence.py:50`, `viewer_data.py:80-81,179`, `render.py:190-191`, `render_catalog.py:48` are name-keyed and become dead entries; no edit.
5. `coupon_frame.py:218` `ladder_station_stub` is a trim of the real ladder; no edit, but trim it to 120 mm so station 2's slot is on it (see First print).
6. Site: retire panel 22's stops and panel 14's list; panel 28 is the design.

### The print advisor's twelve findings, and where each landed

1. Cross-bores at stations → step 6: a non-issue once the ledge box's refill was noticed.
2. One locating pair, slot the rest → the stations table.
3. Deck plates under the tape → RELIEF_Z, PLATE_Z; step 1.
4. Pocket floor relief → POCKET_WELL 0.4, step 4.
5. Peg 4.8 tall → cannot be; nothing stands above z 3. The peg is RECESS tall and only locates. One peg per board, at its datum station.
6. Rest 0.6 → RIM 0.6, the rim shelf, exactly the cradle gauge's shelf; the finding was right that the rest can be no wider than the bare rim.
7. Land geometry → the flat land at 7.42 (design line 2). The arc as back wall was rejected because it bulges past the tab at the floor.
8. FIT 0.30 ok → kept.
9. Seam painting → slicing notes.
10. Keep the 6 mm ledge stubs → END_STUB.
11. Half-bay rib as solid shoulder → HALF_RIB 0.8, step 5.
12. REAR_AXIS ripple → avoided entirely: the axes do not move; only the ladder and its coupon re-export.

### Three things the Plan agent proposed that this plan does NOT take

1. Free 2.8-wide pegs at the non-datum rear stations, with the peg tips as the rear stop. A 2.8 peg tolerates ±0.6 of spacing error and the slotted strip showed the error can be ±1.5; a peg that lands on the board's edge instead of in its notch stops the board dropping at all — the exact failure the front slots exist to avoid. And with one peg only, the board could yaw about it. The full-length shoulder is the rear stop at every point along the board, independent of spacing, and it is what the cradle gauge's second wall was. Cost: a 1.2-tall strip at the foot of the rear rail, inside the ledge's old envelope. If the user refuses even that, the agent's version is in its report.
2. CHAN_Y0 = 7.5 for the channel wall. 7.42 is the same face derived rather than chosen (the arc's y at LEDGE_Z, so the land meets the arc with no step) and it makes the pocket exactly the gauge's 1.71.
3. Its station numbers (29.34 …) and bay origins (12 / 194). They are assembly coordinates read as rail-local: build() places the ladder at assembly x 6, so today's boards start at rail-local 6 and 184, and the stubs shrink to 5 so the full board's end clears the left one. The table above is rail-local; the agent's numbers are the same stations in assembly coordinates, which is what the fit check reports.

### Gates, in this order (ran on the Mac 2026-09-26, all passed)

1. `python cad/frame.py` — expect 11 parts in `out/stl_frame`; `deck_ladder` volume drops ~11 cm³. A boolean exception naming deck_rail means split the compound cutter (step 3).
2. `python cad/coupon_frame.py` — re-exports the coupons so check.py's freshness guard (COUPON_SOURCES lists frame.py) does not flag them stale.
3. `python cad/check.py` — FRAME 11/11, COUPON 16/16, deck_ladder pose 0 with no overhang faces (an overhang means a keep box or well mis-signed for ledge_side).
4. `python cad/assembly_fit_check.py` — EXPECTED new hits: prop_bb_body × asm_ladder at assembly x 28.79 / 94.00 / 159.21 (L 160, prop at 14) and prop_hb_body × asm_ladder at 204.19 / 257.70 — the props have no notches, so the datum pegs pass through them (or cut the notches into `props.breadboard_body`). Anything else is real: asm_ladder × asm_sidebin (the rear-right stub grew; it must not), asm_ladder × asm_frame_* (a shoulder or socket changed; it must not), a prop hit at a non-peg x (a block or stub under the board: FACE_Y or END_STUB wrong).
5. `python cad/screws.py` — both rail ends unchanged; any change in the bar-end margins is an error.
6. `python cad/plates.py --verify` — 02d and 03 build without deck_stop; 07 slices; hand notes present.
7. `python cad/catalog.py`, Blender `cad/render_catalog.py`, `python cad/catalog.py --inject`; then `python cad/publish_site.py` and push redding-digital.

### First print: the ladder station stub, not the ladder

1. `ladder_station_stub` (coupon_frame.py:218) is the first 64 mm of the real ladder; trim it to 120 mm instead so it carries the left stub, the datum pocket and well, the datum peg, the slot at 88.00, and the plate at 52. Both rails, joined — about 15 g.
2. It is cut from frame.py's own functions, so it tests the code that prints the ladder.
3. Results sheet `checklist/ledge.html`, key `ledge` in `checklist/measure_server.py` → `out/plate2_pla/ledge_results.json`. Never POST to a live sheet to test it; that overwrote `cleat_results.json` once.
4. Pass = the full board's left end drops on by hand: tab in the pocket, rim on the shelf both sides, no rock, notch over the peg, second tab in its slot, tape not touching the relief floor or the plate, 0.4 across, and a shove along the rail meets the pocket, not friction.
5. Only then plate 07 with the ladder.

### Slicing notes, from the advisor and the agent

1. Ladder flat, as today, with a brim — 288 long, thin, flat.
2. Seam: paint a stripe down each rail's OUTER face, or lay the ladder along Y with seam position Back. With aligned seams the pockets are the only concave corners on the front rail and every seam blob lands inside a pocket; a blob is bigger than the 0.30 fit.
3. 0.2 layers: the 1.2 recess, the 0.4 well, the 0.8 relief and the 0.8 plates are all whole layers.

### Appendix A — "squish the rails", the literal version, not chosen

REAR_AXIS = FRONT_AXIS + RAIL_GAP + 2·LAND_Y = 79.97, the rear edge bearing
on the rear land with no shoulder, pockets cut into the crown below z 3 and
pegs standing 4.8 proud with a 2.0 root. It is one feature fewer and it moves
every REAR_AXIS dependent 3.43 forward — frame sockets, tray depth, head
pockets, magnet discs, end screws, screws.py — so both frames, the tray, the
bin and the side tray re-export and plate 04 is gated on the full re-run; the
rear-right ledge stub also becomes impossible against the side bin's tongue.
The agent's report below has the boxes. Keeping the axes costs the shoulder
strip and nothing else.

### Appendix B — the Plan agent's build123d sketch, amended to this plan

Constants, after `REAR_AXIS` (line 100); replace `BOARD_Z = LEDGE_Z`:

```python
# --- board recess: the board sinks RECESS into the flat ledge ---------------
RECESS = 1.2                                  # tab / notch engagement = this  (DECIDE)
BOARD_Z = LEDGE_Z - RECESS                    # 1.8  board underside = rim shelf
TAPE_T, RIM = 0.6, 0.6                        # tape thickness; bare rim inside it (caliper)
RELIEF_Z = BOARD_Z - TAPE_T - 0.4             # 0.8  floor under the tape, 0.4 clear
LAND_Y = math.sqrt(RAIL_R ** 2 - LEDGE_Z ** 2)   # 7.42 the land: the arc's y at the ledge top
BOARD_EDGE = _HALF_SPAN - BB_D / 2            # 9.33 board edge, centred, rail-local
PLAY = 0.2                                    # per side
FACE_Y = BOARD_EDGE - PLAY                    # 9.13 block outer faces = shoulder face
SHELF_Y1 = FACE_Y + RIM                       # 9.73 rim shelf ends here, never under tape
END_STUB = 5.0                                # full ledge kept at each end: the frame shoulder; the full board starts at 8, 3 clear
TAB_W, TAB_PROUD, TAB_H = 4.07, 1.41, 5.20    # measured MB-102 cleat
FIT, POCKET_D = 0.30, 1.71
POCKET_W = TAB_W + FIT                        # 4.37 locating pocket
SLOT_REACH = (0.0, 3.0, 4.0)                  # per station: datum exact, then +-3, +-4
BLOCK_L = 3.5                                 # each flanking block, along the rail
POCKET_WELL = 0.4                             # pocket floor below the rim shelf
PEG_W, PEG_D = 3.8, 1.3                       # the datum peg, into the 1.6 notch
FULL_L, FULL_SP, FULL_N = 160.0, 65.21, 3     # fallbacks; read out/board_dims.json first (165.10 was never measured)
HALF_L, HALF_W, HALF_SP, HALF_N = 81.89, 53.94, 53.51, 2
HALF_RIB = BB_D - HALF_W                      # 0.80 half board is this much narrower
FULL_X0, HALF_X0 = 8.0, 184.0                 # left end of each board, RAIL-LOCAL (assembly 14 and 190)
assert abs(FACE_Y - (REAR_AXIS - FRONT_AXIS - RAIL_GAP) / 2) < 0.02
assert abs(FACE_Y - LAND_Y - POCKET_D) < 0.02
assert RELIEF_Z >= 0.8 - 1e-6                 # four layers under the tape zone

def _stations(x0, L, sp, n):
    return tuple(round(x0 + L / 2 + (k - (n - 1) / 2) * sp, 2) for k in range(n))
FULL_ST = _stations(FULL_X0, FULL_L, FULL_SP, FULL_N)   # (22.79, 88.00, 153.21) -- or x0 + END_TAB + k*SP if ever measured
HALF_ST = _stations(HALF_X0, HALF_L, HALF_SP, HALF_N)   # (198.19, 251.70)
```

`deck_rail()` body (546–574):

```python
def deck_rail(ledge_side=+1):
    s = ledge_side
    rail = half_round(SPAN, RAIL_R, holes=(20.0, 4.6), engage=ENGAGE,
                      holes_skip=FOOT_X)                       # unchanged
    rail += box(0, SPAN, 0, s * (RAIL_R + LEDGE), 0, LEDGE_Z)  # unchanged ledge
    x0, x1 = END_STUB, SPAN - END_STUB                         # 5 .. 283
    hx0, hx1 = HALF_X0 - 2.0, HALF_X0 + HALF_L + 2.0           # 182 .. 267.89
    yin = s * (RAIL_R + LEDGE + 1.0)                           # past the ledge's inner edge
    zt = LEDGE_Z + 1.0
    rib = HALF_RIB if s < 0 else 0.0                           # the rear rail steps out in the half bay
    # the channel + the land in one box, then the tape relief beyond the rim shelf
    cut = box(x0, x1, s * LAND_Y, yin, BOARD_Z, zt)
    cut += box(x0, hx0, s * SHELF_Y1, yin, RELIEF_Z, zt)
    cut += box(hx1, x1, s * SHELF_Y1, yin, RELIEF_Z, zt)
    cut += box(hx0, hx1, s * (SHELF_Y1 + rib), yin, RELIEF_Z, zt)
    # every feature is ledge the cutter LEAVES: keep boxes subtracted from the cutter
    if s > 0:                                                  # front: flanking blocks
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                for d in (-1, 1):
                    cut -= box(sx + d * half, sx + d * (half + BLOCK_L),
                               0, s * FACE_Y, BOARD_Z - 1.0, LEDGE_Z + 2.0)
    else:                                                      # rear: shoulder, rib, datum pegs
        cut -= box(x0, x1, 0, s * FACE_Y, BOARD_Z - 1.0, LEDGE_Z + 2.0)
        cut -= box(hx0, hx1, 0, s * (FACE_Y + HALF_RIB), BOARD_Z - 1.0, LEDGE_Z + 2.0)
        for sx, face in ((FULL_ST[0], FACE_Y), (HALF_ST[0], FACE_Y + HALF_RIB)):
            cut -= box(sx - PEG_W / 2, sx + PEG_W / 2, 0, s * (face + PEG_D),
                       BOARD_Z - 1.0, LEDGE_Z + 2.0)
    rail -= cut
    if s > 0:                                                  # pocket wells, after the cut
        for st in (FULL_ST, HALF_ST):
            for i, sx in enumerate(st):
                half = POCKET_W / 2 + SLOT_REACH[i]
                rail -= box(sx - half + 0.05, sx + half - 0.05, s * LAND_Y, s * SHELF_Y1,
                            BOARD_Z - POCKET_WELL, BOARD_Z + 0.1)
    for x in FOOT_X:
        rail -= foot_pocket(x, 0.0)
    return safe_chamfer(rail, rail.edges().group_by(Axis.Z)[0], 0.5)
```

Resulting front rail at station sx: blocks = un-cut ledge at x [sx + half, sx + half + 3.5] and mirror, y 7.42..9.13, z 1.8..3.0; pocket floor z 1.4 between them; rim shelf z 1.8 from 7.42 to 9.73; relief z 0.8 from 9.73 to 12.5. Rear rail: shoulder y 7.42..9.13 (9.93 in the half bay) z 1.8..3.0 the whole length between the stubs; datum peg from the arc out to 9.13 + 1.3 = 10.43 (half bay 11.23); shelf and relief beyond as the front. All new faces vertical or upward: pose 0 unchanged, no overhang. `deck_ladder()` plates: `box(..., y0, y1, 0, RELIEF_Z)`, fillet 0.3.

The agent's unamended report (its free-peg rear stop, CHAN_Y0 7.5, PEG_D 1.4, and the full squish appendix with every REAR_AXIS dependent listed) is in this session's transcript under agent `a6ec35017f186d617`; nothing in it is needed beyond what is above.

## Still to do on the PC, from 2026-09-19: the seven CAD changes

Make the seven CAD changes on the PC, then slice plate 04. They are listed with
their values, their reasons and the plate each one blocks in the living doc,
under "CAD changes waiting for the PC". The rail counterbore is now DECIDED
(2026-09-22, yes): in `din_rail()`, replace the countersink with a 6.0 mm
counterbore 3.2 deep and change the rail's eight screws from M3x16 csk to
M3x12 cap. That leaves 4.2 mm of rail under the head, reaches 7.8 mm into the
pilot — inside both the 11 mm frame and 9 mm buttress pilots — and makes one
screw, M3x12 cap, serve all 14 structural joints, all from the kit and all
magnetic for the rail caps. Doable on this Mac since 2026-09-26 (build123d is in
`~/.venvs/breadboard-bench`); "on the PC" below just means "in frame.py".

1. On the PC, open `cad/frame.py` and `cad/bench.py` and make the listed edits.
2. Re-export the STLs, then run `python cad/check.py`.
3. Run `python cad/assembly_fit_check.py` and confirm every move still clears.
4. Rebuild and verify the plates: `python cad/plates.py --verify`.
5. Refresh the site: `python cad/catalog.py`, then Blender on
   `cad/render_catalog.py`, then `python cad/catalog.py --inject`.
6. Only then slice plate 04.

Do not print plate 04 before step 1: the frame on disk is still cut at the old
rail-slot clearance.
