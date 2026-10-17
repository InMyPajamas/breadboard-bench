# Breadboard Bench — Print-Readiness Review

**Date:** 2026-08-12 · **Scope:** everything the existing gates (check.py / screws.py) do not measure — thin walls, warp, dimensional drift, layer-vs-load orientation, elephant foot, seams, shrinkage, sub-2-perimeter features. **Method:** direct STL mensuration (trimesh ray/section probes) plus real headless slices on the shipping Bambu Studio 02.07.01.62 profile chain (H2S, 0.4 nozzle, 0.20 mm Standard, Bambu PLA Basic / PETG HF / TPU 95A). Report only — no CAD was changed.

---

## Verdict

**Not print-ready as it stands — but every blocker is a small, local fix.** Six blockers were found and all six were independently re-verified against the STLs by the review controller: (1) the console's four rail-mount pilots all land under solid rail web (misses of 12.5/2.5/2.5/4.5 mm to the nearest slot), so the console rail cannot be screwed on at all; (2) the shipped console STLs are stale — `out/stl/din_rail.stl` still has the ~0.2 mm sealed skin over every slot (9 holes at z=7.30, zero at z≥7.40) that the code comments say was fixed, and the coupon is two revisions behind; (3) the frame DIN rail carries a vestigial buried countersink cone under all 8 screw seats (measured void z 3.74–5.34, leaving a 0.57 mm feather ring) that will crush under preload — a leftover cutter still live at cad/bench.py:200; (4) screen_bezel's declared print pose stands the 27 g part on a 10.2 mm² release-tab footprint with its centre of mass 5.2 mm outside support — it falls over in minute one; (5) the TPU rail gasket overfills its sealed gland 120–144%, so the rail web can never seat and the entire 0.35 mm preload scheme is geometrically impossible; (6) the end_frame's front foot-pocket roof is a 0.76–0.80 mm ligament that slices to a single 0.4 mm extrusion line — the only load path from the front foot into the plate. The fixes are one-line to one-function edits plus re-exports. Beyond the blockers, the recurring themes that matter most: `safe_chamfer` fails silently (two parts shipped without their modelled chamfers), the coupon calibrates the console era and the wrong print regime (flat PLA clips vs on-edge PETG production clips), no per-part slicer spec exists (the structural rail slices at 2 walls/15% infill; brims the design depends on are left to auto_brim, which provably declines them), and the gates that passed everything have no minimum-wall check and no console screw coverage. Fix the six blockers, adopt the should-fix list (a day of CAD + a README print table), run the extended coupon, and this is a sound, printable design.

---

## Per-part readiness

| Part | Variant | Material | Pose | Verdict | Top issue |
|---|---|---|---|---|---|
| end_frame | frame | PLA | Y-90, outer face down | **BLOCKED** | Front foot-pocket roof = single-extrusion 0.8 mm ligament; cracks at ~2 N |
| deck_ladder | frame | PLA | flat | Should-fix | Lightening bores punch through foot pockets at x=52/236 |
| rear_tie | frame | PLA | flat | Should-fix | 1.58 mm sparse-backed crown over plain horizontal pilots |
| din_rail (300) | frame | PLA | web down | **BLOCKED** | Buried vestigial csk cone under all 8 screw seats |
| rear_tray | frame | PLA | upright | Should-fix | V-tail wedge starts as a mid-air knife edge (slicer flags floating regions) |
| rail_pad | frame | TPU 95A | flat | **BLOCKED** | Gland overfill 120–144%; web can never seat, preload scheme void |
| foot_pad | frame ×14 | TPU 95A | flat | Should-fix | Sealed-pocket incompressibility scatters proudness +0.24–0.53 mm |
| base_body | console | PLA | flat | **BLOCKED** | All 4 rail pilots under solid rail web; rail cannot attach |
| din_rail (276) | console | PLA | web down | **BLOCKED** | Stale STL: slots sealed by ~0.2 mm skin; plus pilot misalignment above |
| board_plate | both (module) | PETG | on edge | Should-fix | X-arm slots print across layers under a bridged ceiling — M3 binds |
| screen_bezel | both (module) | PETG | on edge (+90) | **BLOCKED** | Pose stands on the release tab; body floats, COM outside support |
| breadboard_carrier | console (unplaced) | PETG | on edge | OK w/ brim | Exported but placed in no assembly; brim mandatory |
| rail_bin | both (module) | PETG | bin bottom down | OK | Seam lands on latch tooth first layer (nice-to-have) |
| fit_coupon | calibration | PLA | flat | **STALE** | Two revisions behind; calibrates superseded geometry, wrong clip regime |

**Findings shared by BOTH variants** (fix once in `cad/bench.py`, both variants inherit): the DIN rail section constants (lip width 35.0, RAIL_CHANNEL_Z/RAIL_TOP_Z layer-grid quantisation, eave droop, csk cone geometry — the leftover buried-cone cutter lives in the shared `din_rail()` mounts loop); the `din_clip` latch beam (all four modules, both variants); the fit_coupon (calibrates both); the check.py/screws.py gate gaps. The screen_bezel pose blocker affects both variants because the module is placed on both benches.

---

## Blockers (6) — all controller-verified against the STLs

### B1. Console rail cannot be attached: all 4 pilots land on solid web
**Part:** base_body + din_rail (console). **Verified:** slots measured in `out/stl/din_rail.stl` at rail-local x centres −100..+100 on exact 25 mm pitch (each 15 × 6.2); pilot list confirmed in source at cad/bench.py:375 = bench X 30/110/190/262 = rail-local −120/−40/+40/+112. Misses to nearest slot cavity edge: **12.5 / 2.5 / 2.5 / 4.5 mm** — every M3 lands on 6.3–7.5 mm of solid web/crown. screws.py audits only the 14 frame screws; the console's 4 rail screws have zero gate coverage, which is how this shipped.
**Change:** move the pilot list to slot centres in gusset bays — `(50.0, 125.0, 175.0, 250.0)` (rail-local −100/−25/+25/+100; ribs at 76.75–81.75 / 147.5–152.5 / 218.25–223.25, so all four are mid-bay). Then add the console rail screws to screws.py.
**Effort:** one line in bench.py + ~20–30 lines in screws.py; re-export + re-gate.

### B2. Shipped console STLs are stale — rail screw paths are sealed
**Part:** din_rail (console) + fit_coupon. **Verified:** `out/stl/din_rail.stl` (2026-08-10 19:27, older than cad/bench.py 2026-08-11 05:50) has 9 interior loops at z=7.30 and **zero at z=7.40/7.45/7.49** — every slot+csk capped by a ~0.2 mm skin at the outer face, the exact "sealed-skin" bug the code comments describe as fixed. `out/stl/fit_coupon.stl` (2026-08-09) has clips 1.0 mm deeper / +12% material vs current `din_clip`, and its rail section lacks the under-lip anti-droop chamfer (4.0 mm eave vs current 2.5 mm) — it calibrates geometry that no longer exists. (Frame STLs are fresh: regenerated 2026-08-12 01:53, after frame.py.)
**Change:** re-export the console set and coupon from current code; add an export-freshness guard to check.py (fail if any `out/stl/*.stl` mtime predates `cad/bench.py|coupon.py|params.py`).
**Effort:** minutes to regenerate; ~10 lines for the guard.

### B3. Frame rail: buried countersink cone under all 8 screw seats
**Part:** din_rail (frame) — cutter lives in shared `din_rail()`. **Verified:** vertical probes at bores (±144, ±8) and (50, 8), offset r=1.72 from axis: solid 0.02–3.74, **void 3.74–5.34**, solid 5.34–5.91 — a hidden 45° conical void (Ø6.6 at bottom) directly under each countersink seat, leaving a **0.57 mm** feather ring at the bore wall. Source confirmed: cad/bench.py mounts loop cuts both the correct outer-face cone (`Pos(x,y,RAIL_TOP_Z-0.85) * Cone(1.6,3.3,1.7)`) **and** the superseded `Pos(x,y,RAIL_CHANNEL_Z-1.7) * Cone(3.3,1.6,1.7)` on the next line. Gcode prints "Floating vertical shell" around each bore. Torquing M3 csk against the 0.35 mm gasket preload crushes the ring and the head sinks, bleeding the preload at all 4 stations. Passes every existing gate (watertight, 45°, islands).
**Change:** delete the second cone line in the mounts loop; regenerate both variants' rails; re-run check.py.
**Effort:** one line + regenerate.

### B4. screen_bezel print pose is unprintable
**Part:** screen_bezel (module, placed on BOTH variants). **Verified:** at pose X+90 the bed contact is **10.2 mm²** (release tab only, footprint x −1..5, y −6.6..−5.0); model bbox confirms the tab reaches y=−26.95 vs body edge −25.85 (1.10 mm proud — the root cause); the body's cross-section at z=1.1 is only 20.3 mm²; COM (0, −11.79, 27.47) sits **5.2 mm outside** the support interval. A 27 g, 52.8 mm-tall part standing on a 9×5 mm tab tips at minute one. The island waiver covers a mid-air tab — here the tab is grounded and the whole body is the island: new evidence outside the waiver.
**Change:** flip PRINT_POSE to ('X', −90) — measured 774.3 mm² contact on the solid rim edge, COM inside support (half-width 4.29 mm), slices clean at 15.3 g / 55 min, and the islands revert to the already-waived tooth/tab set. Alternative: shorten tab reach from outer+6.0 to outer+4.5. Update check.py PRINT_POSE + re-gate.
**Effort:** one-line pose change.

### B5. rail_pad gland is overfilled 120–144% — the preload scheme cannot happen
**Part:** rail_pad (frame; mates end_frame + rear_tray lands). **Verified:** pad measured 5.000 × 24.000 × 1.350, V=132.86 mm³, holes Ø3.600, side ligaments **0.700 mm** both sides of both holes. As printed it is 7 layers = 1.40 thick → **137.8 mm³** of near-incompressible rubber in a sealed cavity of ~107–115 mm³ (pocket 5.0×24.3×1.0 = 121.5 minus M3 shank displacement; the 27 mm rail web fully covers the 24.3 pocket, so the gland is confined once the web contacts). Fill factor 120–128% at CAD nominal, 135–144% at typical +0.15/side TPU oversize; gland practice is 75–90%. Minimum possible web standoff 0.19–0.39 mm — the modelled web-seats-on-post condition is geometrically unreachable, and torquing "until it seats" strips the r1.25 pilots (~0.5–0.8 N·m strip in PLA). Every downstream fit (hook capture lip+0.25, shoulder rib web/2+0.25, 4-station coplanarity) loses 0.19–0.39 mm. Subsumes: zero width clearance (5.0 pad in 5.0 pocket), no bottom chamfer, 0.7 mm ligaments, 1.35-vs-1.40 thickness — fix all in the re-gland.
**Change:** re-gland so void ≥ rubber/0.85. Minimal: pad 20.0 × 4.2 × 1.4 (on the layer grid) with Ø3.2 holes → ~80–85% fill, 0.9 mm ligaments, 0.15/side width clearance, 0.3 chamfered bed edge. Cleaner: replace with two TPU washers per station (Ø6.0×Ø3.6×1.4 in Ø7.0×1.0 counterbores = 81% fill). Update assembly analysis to web-seats-flush.
**Effort:** medium — one function + two pocket cuts in frame.py.

### B6. end_frame front foot-pocket roof is a single-extrusion-line beam
**Part:** end_frame (frame). **Verified:** minimum ligament between the front foot-pocket top (z=3.2) and the lightening-window bottom (z=4.0) measured **0.797 mm** at plate depths x=1.5/3.0/4.5 across y 22–38 (expert's fillet-corner minimum 0.76); rear pocket roof measured 1.80 mm (fine). Sliced gcode: layers 2–30 in the region contain exactly one 0.37–0.45 mm outer-wall line — no second wall, no gap fill. This single line (16.4 mm span, ~0.4×6 mm section) is the only load path from the front TPU foot into the plate: ~50 MPa bending at 2 N; it cracks on first real load, on the show face.
**Change:** raise the front lightening-window bottom edges from z=4.0 to z=5.2 → 2.0 mm / 4-wall roof matching the rear station. Do not shallow the pocket (FOOT_D 3.2 is shared by all 14 TPU pads). Cost ~0.4 g/frame.
**Effort:** one-line CAD edit + re-export.

---

## Should-fix (by part; ★ = shared by both variants)

### DIN rail (★ section constants shared)
1. **Lip width 35.0 nominal eats clip closure.** At the README's own +0.1..+0.2/side over-extrusion the rail prints 35.2–35.4 vs clip opening 35.5; clips stop closing at +0.25/side, and it breaches the TS35 −0.3/+0 spec. *Change:* default RAIL_LIP_W = 34.85 (splits the hedge, in-spec even printed dead-on); confirm on the coupon rail section. Keep seam_position=aligned (verified: seam pins to a part-end corner, never the lip slide faces) and add a README note forbidding random seam on the rail. *(one constant)*
2. **Lip band off the 0.2 mm layer grid + eave droop + tooth clearance coin-flip (reconciled).** Two experts proposed different values (shift RAIL_CHANNEL_Z to 6.4 vs 6.2/7.4). Reconciled recommendation: **RAIL_CHANNEL_Z = 6.2, RAIL_TOP_Z = 7.4** (whole lip band on the grid: lips exactly 6 layers, deterministic datums — the 6.4 proposal leaves the top face off-grid), **plus** tooth_top = RAIL_CHANNEL_Z − 0.5 (from −0.35) to buy back the measured 0.1–0.3 mm eave droop on the 2.47 mm unsupported reach. Net tooth clearance becomes deterministic-positive instead of the current +0.35..−0.05 stack. Verify on the coupon's 40 mm rail section first. *(two params + one constant)*
3. **Csk flushness depends on which M3 csk screw is bought (reconciled).** One expert (DIN 965, head Ø5.6) computed 0.2–0.4 sub-flush; the other (DIN 7991/ISO 10642, head Ø6.0) computed 0.0–0.35 **proud** — in the clip slide path, the exact failure pan heads were banned for. Both are right for their screw. *Change:* sink the cone 0.3 deeper and widen it (e.g. top radius 3.6), which yields sub-flush for either standard, and pin the screw standard in the README BOM. *(one-line cutter change, shared by both variants' rails)*
4. **Frame rail slices at 2 walls / 15% sparse with no per-part print spec.** The structural tie prints 47% dense; screw seats and the 2.7 mm end ligaments are sparse-backed shells. *Change:* README per-part print-settings table (see item 15). *(doc + preset)*
5. **Frame rail round mount bores can't absorb differential shrink over 288 mm.** 0.1% rail-vs-ladder differential = 0.29 mm vs as-printed clearance 0.05–0.15 mm/side. *Change:* keep one end pair round as datum; make the other three pairs 3.4×4.6 X-slots. *(small code change)*

### end_frame
6. **`safe_chamfer` silently dropped the modelled 0.6 mm bed-face chamfer** (cross-section area constant 2591.44 mm² from x=0.02 to 1.0; the inner-face chamfer IS present) — first-layer spread lands raw on the shoulder-rib/hook fit faces (rib-to-hook gap 31.50 vs rail span 31.0; interference from +0.2/side squish). Same silent no-op dropped rear_tray's entire 0.5 mm bottom chamfer (verified: wall at y=0.000 at z=0.1–1.2). *Change:* fix the chamfer calls (chamfer before unioning big feature sets), and make `safe_chamfer`/`safe_fillet` in bench.py **log a warning** instead of failing silently — this pattern can mask failures on every part. Until fixed: keep elephant-foot compensation ≥0.15. *(CAD debug + one warning print)*
7. **No mirrored right-frame STL and no mirror note.** QTY=2 but the assembly mirrors Plane.YZ; two as-is prints cannot be assembled (all rail/socket features are single-sided). *Change:* export `end_frame_r.stl` or add a README line "print 1× as-is + 1× mirrored (mirror preserves the outer-face-down pose)". *(one line)*
8. **Bar-end "clearance" bores are Ø3.2 modelled → 2.9–3.1 as printed; the screw threads the plate** and holds rods proud instead of drawing them home — defeating the mechanism that takes up the 288-span shrink float. *Change:* open the three plate bores to Ø3.4 (value already used on the rail); confirm offset on the coupon's slot gauge. *(one constant)*
9. **Rail-pad pocket: zero width clearance + bridged ceiling** (24.3×1.0 ceiling sags 0.1–0.2 into the opening). Superseded by B5's re-gland if adopted; otherwise widen pocket to 5.4–5.6. *(one dimension)*

### deck_ladder + foot_pad (the TPU stance system)
10. **Lightening bores at x=54/234 punch through the foot pockets at FOOT_X=52/236** — verified void continuous from bed to z=6.4; pocket roof 71.3% solid vs 96.3% at the intact station; ~33% of the foot's squash volume escapes into the bore. *Change:* skip bore stations within 10.7 mm of any FOOT_X (drops 4–6 bores, ~1–2 g). *(one guard clause)*
11. **Sealed-pocket incompressibility scatters foot proudness.** Engaged pad volume 323.6 mm³ vs cavity 301.0 mm³: excess → +0.24 mm proud at CAD nominal, +0.38/+0.46/+0.53 at +0.10/+0.15/+0.20 per-side TPU oversize. Only 2 of 14 pockets are sealed the same way (4 ladder pockets vented by finding 10's bores, 4 end-frame pockets are open-sided slots, 4 tray + 2 mid-ladder sealed) — the Z=−1 coplanar plane scatters ~0.3–0.4 mm systematically and 20 N/foot flattens only 0.015 mm. Insertion into a sealed pocket at real interference ≈130–190 N (tool press, not thumb). *Change:* FOOT_FIT 0.25 → 0.12 + a ~18 mm³ relief groove in the pad top face so excess ≤5 mm³ at +0.15/side; make venting uniform via finding 10. *(two constants + one groove)*

### rear_tray
12. **V-tail rear wedge starts as a mid-air knife edge** — slicer warns "floating regions" (no waiver covers rear_tray); zero extrusion at z=0.2/0.4, first bead at z=0.6 laid over air, isolated wisp column for 42 layers at both stations, and the V-rod contact faces (z≈4.2) build off the ragged base. *Change:* truncate the knife edge (stop the rear V-face at z=0.8 and drop vertically to the bed) — zero functional impact; or two support dabs mirroring the clip-channel pattern. *(one polyline point)*
13. **M3 rail pilots are a 0.87 mm two-perimeter shell backed by 15% sparse**, not the 1.75 mm solid ligament the mesh implies — self-tap leaves ~0.62 mm holding the rail preload couple; blade root I drops ~28% with the sparse core. *Change:* slice rear_tray with wall_loops ≥4 (or a solid-infill modifier cylinder around each pilot); add to the README print table. *(slicer setting)*

### rear_tie
14. **1.58 mm sparse-backed crown over plain horizontal Ø2.5 pilots** — ceiling sag 0.1–0.3 shrinks the bore to ~2.2–2.4; the M3 wedges 0.3–0.4 mm radially into a 2-shell crown (source's own numbers: sparse-backed self-taps hold 120–200 N vs 300–500 N solid). *Change:* teardrop the `half_round()` end pilots (helper exists, used in rear_tray) + ≥4 walls for the bars; field fallback: 2.5 mm drill pass. Also extend brim spec here — 294×12 strip, brim_type resolves to none, and a 0.2–0.3 mm bow eats 60–85% of the V-notch preload budget. *(small code change + README)*

### Print-spec / process (★)
15. **No per-part slicer spec exists, and the defaults provably drop what the design assumes.** Measured: auto_brim emitted **zero** brim for deck_ladder despite the README instruction living only in a code comment; brim_type=none for rear_tie; board_plate/breadboard_carrier survive on-edge **only** because auto_brim happened to fire (tip angles 2.2°/2.4°, topple force ~3 mN); TPU 100% infill is not the profile default (foot_pad sliced 15% sparse; CLI override rejected — must be a saved preset); din_rail/rear_tray/rear_tie need ≥4 walls. *Change:* add a README print-settings table (part / material / pose / brim / walls / infill / seam) + ship the TPU preset. *(documentation + presets, zero CAD)*

### base_body (console)
16. **0.2 mm membrane behind 3 of 4 finger scoops slices to nothing** — verified gcode has zero extrusions in the region; as printed these are ~4–6 mm × 19 mm open slots at floor level between wells and bins 1/3/4. *Change:* scoop radius 8.5 → 7.0 (wall becomes 1.7 mm) or move scoop centre to y=58.4. *(one parameter)*
17. **Rear wall feathers 2.5 → 0 mm across all four bay spans** (0.81 at z=47, 0.42 at z=55, open above z=63.3; slicer prints a lone 66 mm free bead at z=50–54 then nothing) plus an open razor slit at z=2.02–2.05 on the plinth band. *Change:* make the bay cutter's rear boundary parallel to the raked rear face at ≥1.6 mm offset, and start it at z=4.6 instead of 2.0. *(~5 lines)*
18. **Rail-screw pilot engagement is 3.6 mm — below the project's own ≥4.0 rule** (4.1 panel − 0.4 recess), in near-horizontal Ø2.6 bores mid-bay. *Change:* when relocating pilots for B1, add a Ø8×6 boss behind the panel at each station (bays are hollow) + teardrop, matching the rear_tray pattern. *(small loop)*

### PETG clip modules (★ din_clip shared)
19. **screen_bezel window lintel is a 66–67 mm free bridge on the visible face in either on-edge pose** — the "picture frame chamfer" in the source comment does not exist in the geometry (half-rim measured identical at three heights). PETG will droop 0.5–2 mm along the aperture's top edge. *Change:* model the promised 45° chamfer on the edge that prints as a ceiling. *(small CAD edit)*
20. **screen_bezel PCB pocket can reach zero clearance as printed** (+0.35/side minus −0.1..−0.3 undersize minus PETG shrink), and the clip back plate protrudes 3.0 mm into the pocket leaving 2.2 mm for rear-side components under a seated PCB. *Change:* open to +0.55/side (80.1×37.8) and check the Waveshare rear-component envelope; relieve the clip-back zone if it fouls. *(two dims + datasheet check)*
21. **board_plate X-arm slots print their 3.4 width across layers under a bridged ceiling** — bridge sag 0.2–0.4 + undersize → effective 2.9–3.1 vs a 2.9–3.0 M3: binds. The coupon's flat slot gauge cannot calibrate this case. *Change:* widen X-arm slots only to 3.8 (or gable the slot roofs); leave Y-arms at 3.4 for location. *(one parameter)*
22. **Latch spring beam (all four modules): unsupported bridge underside + off the 0.2 layer grid in 3 of 4** — effective thickness 1.4–1.6, spring rate down up to 33%, ragged face on the max-stress fiber. *Change:* nudge plate depths so the beam band lands on 0.2 multiples; add one sanctioned support dab under the beam mid-span (non-fit, non-cosmetic face — within the waiver's spirit). If retention is weak on the coupon, go 1.8 thick. *(0.05–0.15 mm nudges + slicer dab)*

### fit_coupon
23. **Test clips calibrate RAIL_FIT in the wrong regime:** flat-printed PLA clips with tooth faces on 2.2 mm unsupported bridges (measured 1230 mm bridge + 488 mm overhang wall in the clip band, supports off) vs on-edge PETG production clips whose jaw opening is layer-quantized. Systematic offset ~0.1–0.3 mm on a 0.05-step gauge — can select RAIL_FIT 1–3 steps off. *Change:* stand the five test clips on edge in the production pose; print the clip row in PETG with the module profile. *(coupon.py rework + README)*
24. **Coupon has no frame-era coverage:** missing the r+0.2 socket/spigot fit, the 16×6×3.2 TPU foot pocket + FOOT_FIT pad, the gasket pocket/pad proudness stack, the Ø2.5 pilot (gauge starts at 2.6), and any csk-flushness check (the 40 mm rail section has zero holes). 100 mm bars extrapolate ×3 to 300 mm with a ±0.15–0.3 mm band. *Change:* add a frame annex (~15 cm³): socket block + spigot stub, foot pocket, gasket pocket, 2.4/2.5 pilot pair, one csk bore + supplied M3×16. *(one coupon.py session)*

### Gates (★ process — this is how two blockers shipped)
25. **check.py has no minimum-wall check** (the 0.2 mm membrane and 0.8 mm ligament passed ALL CLEAR) **and screws.py covers no console screws** (how B1 shipped); nothing checks export freshness (how B2 shipped). *Change:* per-slice morphological opening (−0.4/+0.4 buffer) flagging vanished regions >1 mm²; add console rail screws to screws.py; mtime freshness guard. *(~40 lines total)*

---

## Nice-to-have

1. **Teardrop parity:** end_frame rail pilots and deck_ladder end pilots are plain round horizontal bores (helper exists, rear_tray uses it) — ceiling sag vs a 0.25 mm bite annulus; torque/consistency nuisance only.
2. **Bottom chamfers:** rear_tie has none (sibling deck_rail does; margin 0.00 at +0.2/side spread — currently rides on EFC=0.15 being on); din_rail web bed edges likewise (margin 0.00 at +0.25/side).
3. **rail_bin seam:** aligned seam starts one latch-tooth layer at the tooth zone; seam-paint the clip modules onto the plate/box corner arris.
4. **Coupon plate:** 4.5 mm min inter-body gap collides with 5 mm brims; README size/time claims stale (actual 212×219 mm, 51.8 g, 1 h 22 m vs claimed 164×187, "under an hour").
5. **rear_tray dividers** 1.2 mm slice as 2 walls + 0.36 mm gap-fill wisps — printable; 1.26 mm (3×0.42) eliminates gap fill if ever revised.
6. **rail_pad thickness constant** 1.35 → 1.4 so CAD, comments, and print agree (folded into B5's fix).
7. **end_frame socket-mouth slivers:** R8.2 crowns breach the plate top edge by 0.2 mm leaving feathered sub-0.8 mm slivers where the spigots drop in — chamfer the mouth top 0.3 or deburr at assembly.

---

## Observations (verified, no action required)

- **end_frame pose is benign:** 2591 mm² contact (45% of hull), 12 mm tall, loads in-plane; hook throat exactly 0.250 over rail top, 3.50 mm lip overlap. Note: the hook's intended 0.8 lead-in chamfer is also absent (same safe_chamfer failure family); foot pads stand ~0.25 mm proud of the show face by design (open-sided slots — retention on two end faces only, ~20–25 N pull-out; glue-dot if the bench is lifted by the frames).
- **Shrink chains verified self-absorbing:** deck_ladder spigot engagement ≥2.28 mm at 0.5% shrink, screws restore 3.0 with 0.5 head-room; rear_tie chain holds to 0.5%; tray V-notch free in X as designed; base_body MB-102 well survives to ~0.45–0.55% uncompensated (the coupon scale pass is a hard prerequisite for the 244 g print — README should make it a gate). Assembly order note: drive all six bar-end screws home before torquing rail screws.
- **rear_tray warp is low-risk by geometry:** 13,729 mm² solid first layer; a 0.3 mm bow displaces the two lands only ~0.04 mm relative (gasket budget 0.35); no brim needed. Lands print as 53° staircase mating the frames' smooth side-printed lands — <0.1 mm effective offset, absorbed by the gasket. Pilot bores are post-normal (37° axis) → self-supporting 53° ceilings; record in comments so nobody "fixes" them flat.
- **As-built rail numbers:** prints 7.4 tall (not 7.5), lips 1.0 thick (not 1.2) — matching steel TS35 lips; judge clip and hook fits against 7.4/1.0. Prying a module off without releasing the latch loads the lip root across layers at ~36–51 MPa (≥ interlayer strength) — release latch-first; covered by the walls/infill spec.
- **base_body first layer is its own anchor** (98.3% of footprint, no brim); felt pads absorb residual bow; COLOUR_SWAP_Z=4.6 is exactly the layer-23 boundary; set seam=back for the console body.
- **breadboard_carrier is placed in no assembly** (bench.py places plate/screen/bin; frame.py's "all four modules" comment is wrong) — ship as optional accessory or place it; fix the comment.
- **TPU printability itself is fine:** foot_pad 21 exact layers, chamfer staircases resolve, elephant foot lands on the chamfered desk face; print all 18 TPU parts as one plate, by-object.
- **Coupon clip relief verified open** (0.9 mm gap intact) — the historic re-weld bug is not in the coupon build path; add a comment explaining why plain `+ din_clip()` is safe there.
- **Clip-channel islands** (tooth/tab mid-air, dabs in channel): waiver reviewed and upheld for all modules except screen_bezel's +90 pose (B4 — new evidence: the body, not the tab, is the island). Note the dabs are **not** in any sliced file — they are a manual Studio step; the README should say so, including for the coupon.

---

## Slicer probe outcome

**Usable.** Bambu Studio 02.07.01.62 slices fully headless on Windows (exit code + output files are the only success signals; console output is swallowed). All seven expert groups sliced their parts with the real H2S / 0.4 / 0.20 mm profile chain and judged findings from actual gcode, not heuristics. Headline masses: base_body 243.9 g / 5 h 20 m (README's "8-hour base" is 5.3 h), deck_ladder 41.95 g, rear_tray 53.75 g, frame rail 33.10 g, coupon 51.8 g / 1 h 22 m.

**Critical gotcha (measured):** system profile JSONs use `inherits` chains the CLI does not resolve for loose files — loading a leaf JSON silently half-resolves (first slice "succeeded" with filament density 0 and 0.00 g mass). All automation must flatten the chain first (flatten.py in the session scratchpad does this). Also: `sparse_infill_density` cannot be overridden on the CLI (-18 Invalid parameter) — TPU 100% infill must live in a saved preset.

**Not verified in this review (out of scope or blocked):**
- Multi-object plate arrangement / `--arrange`, and multi-filament assignment (probe scope).
- Support-dab placement for the waived clip islands — the dabs exist in no sliced file; they are a manual slicer step and were not exercised.
- Physical realities the coupon exists to measure: this machine's actual shrink %, hole undersize, first-layer squish, TPU oversize, and PETG bridge droop — all findings quote typical ranges (PLA 0.3–0.5% shrink, −0.1..−0.3 hole undersize, 0.1–0.3 bridge sag) and the coupon-first rule remains the sanctioned control.
- Seam painting behavior (only seam_position=aligned/back were sliced and inspected).
- PETG HF vs PETG Basic profile choice for the clip modules (HF was used throughout).
- Assembled-stance flatness (foot proudness scatter is computed, not measured on a built bench).

---

*Review basis: 7 expert groups, 14 parts, ~120 discrete measurements; 6 blocker claims independently re-verified by the controller with fresh trimesh probes against `out/stl` / `out/stl_frame` on 2026-08-12. No CAD files were modified.*
