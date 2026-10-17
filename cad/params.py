"""Shared dimensions for the Breadboard Bench.

Coordinate convention for the assembled bench:
    +X  left -> right   (0 .. BENCH_W)
    +Y  front -> back    (0 = edge nearest the user)
    +Z  up               (0 = desk surface)

Everything is millimetres. Printed on a Bambu H2S, 0.4 nozzle, 0.2 layer.
"""

import math

# ---------------------------------------------------------------- overall ---
BENCH_W = 300.0          # left-right
BENCH_D = 134.0          # front-back
WALL = 4.0

# ------------------------------------------------------------ design system -
# One plan margin governs the corner radius, the panel inset and the field
# margins, so the bench end, the panel end and the rail end all show the same
# 6 mm reveal. The value was already hiding in the model (BB_WELL_X = 6,
# TROUGH_X1 = 294); this just makes everything obey it.
MODULE = 6.0
OUTER_R = MODULE         # outer vertical corners
POCKET_R = 3.0           # bins and trough
WELL_R = 2.0             # breadboard wells -- larger leaves a crescent gap at
                         # each corner of the board
EDGE = 1.5               # chamfer on top arrises you look along
RIM = 0.75               # ease on every pocket rim

# Base plinth. Printed base-down, a footprint that GROWS with height is the
# easy direction -- every layer sits on the one below. A true recessed undercut
# would need the floor plate to start at Z=3 unsupported, which cannot bridge.
BASE_INSET = 4.0         # ground footprint 292 x 126
BASE_LAND = 0.6          # vertical land at Z=0 keeps bed contact crisp
BASE_FLARE = 4.0         # 45 deg, rise == run
BASE_TOP_Z = BASE_LAND + BASE_FLARE      # 4.6 -- full section from here up
COLOUR_SWAP_Z = BASE_TOP_Z               # a filament change must land on an
                                         # edge, never mid-face
# 2.0 mm = 10 layers at 0.2, and it prints ~100% solid at 3 perimeters. This is
# the single heaviest feature in the whole bench (a 300 x 134 plate), so every
# 0.1 mm here costs ~5 g. Walls support it every ~55 mm; it does not need 3 mm.
FLOOR = 2.0

# ------------------------------------------------------------- front tier ---
# Two wells side by side: a full-size 830-point board (MB-102, 165.1 x 54.4)
# and a half-size 400-point board (83.0 x 54.4), plus a trough for probes.
FRONT_DECK_Z = 10.0      # top surface of the front bay
# 54.74 measured on a real MB-102 (StellarSource) 2026-08-28, not the 54.4
# this started from. It feeds the console's well and the render props; the
# frame's rail spacing is pinned separately (see CRADLE / FACE_Y in
# frame.py) so this number can be honest without moving REAR_AXIS.
BB_W, BB_D = 165.1, 54.74
HB_W, HB_D = 83.0, 54.4
BB_CLEAR = 0.6           # per-side print clearance

BB_WELL_W = BB_W + 2 * BB_CLEAR
BB_WELL_D = BB_D + 2 * BB_CLEAR
BB_WELL_X = 6.0          # left edge of the full-size well
BB_WELL_Y = 4.5          # front edge of both wells
BB_WELL_FLOOR = FLOOR    # 8 mm deep, so a 9-10 mm board sits ~1.4 mm proud

HB_WELL_W = HB_W + 2 * BB_CLEAR
HB_WELL_X = BB_WELL_X + BB_WELL_W + 4.0

TROUGH_X0 = HB_WELL_X + HB_WELL_W + 4.0   # probes, tweezers, snips
TROUGH_X1 = BENCH_W - 6.0
FRONT_TIER_Y1 = 66.0

# --------------------------------------------------------------- mid tier ---
MID_Y0, MID_Y1 = FRONT_TIER_Y1, 100.0
MID_DECK_Z = 25.0
BIN_COUNT = 5
BIN_WALL = 2.8
# Bins run nearly the full depth of the tier -- the solid ledges either side
# were ~55 cm3 of dead plastic for what only needs to be a 2.8 mm wall.
PANEL_SETBACK = 2.0      # panel foot sits this far behind the tier below it
# Bins run to 2.8 mm short of the panel foot, not of MID_Y1. Tying them to
# MID_Y1 left a 300 x 4.8 x 23 band of solid deck behind them once the panel
# was set back -- 14 cm3 of nothing.
BIN_Y0, BIN_Y1 = MID_Y0 + 2.8, MID_Y1 + PANEL_SETBACK - 2.8
BIN_FLOOR_Z = FLOOR      # 23 mm deep bins
BIN_X0, BIN_X1 = MODULE, BENCH_W - MODULE   # field obeys the 6 mm margin
# Internal dividers stop below the deck so the mid tier reads as a continuous
# frame with one long opening in it, rather than as a comb of five wall-tops
# alternating with voids. 21.0 is not arbitrary -- it is where the thumb scoop
# already bottoms out (MID_DECK_Z + 7 - R11), so everything inside the field
# resolves to a single line.
BIN_DIVIDER_Z = MID_DECK_Z + 7.0 - 11.0     # 21.0

# --------------------------------------------------------- back din panel ---
PANEL_TILT = 20.0                       # degrees leaned back from vertical
# 4.0 mm = 10 perimeters. Thinner than before, but the gusset spacing dropped
# from 88 mm to 68 mm at the same time, and deflection goes with span cubed --
# so the panel ends up stiffer than the 5.5 mm version despite being lighter.
PANEL_T = 4.0
# The panel is narrower than the tray and set back 2 mm from the tier below it.
# That setback IS the reveal -- made by geometry, not by a cut groove, so it has
# no overhangs and costs nothing to print. It is also what stops the tray and
# the panel reading as one continuous stepped plane in silhouette.
PANEL_W = BENCH_W - 2 * MODULE          # 288
PANEL_X0 = MODULE
PANEL_Y0 = MID_Y1 + PANEL_SETBACK       # front face, bottom edge
PANEL_Z0 = MID_DECK_Z
PANEL_H = 70.0                          # slope-run of the panel face
PANEL_TOP_Y = PANEL_Y0 + PANEL_H * math.sin(math.radians(PANEL_TILT))
PANEL_TOP_Z = PANEL_Z0 + PANEL_H * math.cos(math.radians(PANEL_TILT))

# Panel-local frame: s = distance up the sloped face from (PANEL_Y0, PANEL_Z0)
SIN_T = math.sin(math.radians(PANEL_TILT))
COS_T = math.cos(math.radians(PANEL_TILT))


def panel_point(s: float, n: float = 0.0):
    """(Y, Z) of a point s mm up the panel face and n mm along its outward normal."""
    y = PANEL_Y0 + s * SIN_T - n * COS_T
    z = PANEL_Z0 + s * COS_T + n * SIN_T
    return y, z


RAIL_S = 38.0                            # rail centreline height up the panel
RAIL_Y, RAIL_Z = panel_point(RAIL_S)
# Rotating a rail modelled in its own XY/Z frame by this angle about X lays it
# flat on the panel face with its local +Z pointing along the panel normal.
PANEL_ROT_X = 90.0 - PANEL_TILT          # = 70 deg

# -------------------------------------------------------------- din rail ----
# True EN 60715 top-hat section. Two earlier versions had this inverted: the
# 35 mm span was laid against the panel with the 27 mm section standing proud,
# which is backwards. On a real rail the 27 mm WEB lies flat on the mounting
# face and the 35 mm LIPS stand 7.5 mm off it, leaving a 6.3 mm channel behind
# each lip for clip teeth to swing into. Getting this the right way round means
# the channel comes for free (no panel relief groove needed) and a steel TS35
# offcut is a drop-in replacement.
RAIL_LEN = 276.0
RAIL_LIP_W = 34.85       # across the lips: 35.0 nominal minus the +0.15 the
                         # H2S provably adds per pair of walls (print review)
                         # -- keeps the printed part inside TS35's 35 -0.3/+0
RAIL_WEB_W = 27.0        # flat section that lies on the mounting face
RAIL_LIP_T = 1.2         # lip thickness
RAIL_TOP_Z = 7.4         # lip face: 37 x 0.2 layers exactly. 7.5 nominal put
                         # the lip band off the layer grid and the slicer
                         # rounded it part-by-part (print review)
RAIL_CHANNEL_Z = RAIL_TOP_Z - RAIL_LIP_T   # 6.3 -- underside of the lips

RAIL_FIT = 0.15          # per-side clearance between rail and clip. Plate 03, 2026-10-05:
                         # the 0.15 clip is "nice and snug with room to slide", 0.25 (the
                         # old guess) is loose on the rail. Graded 0.15 / 0.25 / 0.35.
# Two screws per support, straddling the rail's centreline. One screw makes a
# pin joint whose only resistance to a module's torque is whatever preload
# survives PLA creep; two make a couple, and the couple is what stops the rail
# rolling. 16 keeps both inside the 27 mm web with 3.8 mm of edge margin.
RAIL_END_PITCH = 16.0
RAIL_CBORE_D = 6.0       # counterbore for the rail's M3 cap heads (5.5 dia)
RAIL_CBORE_H = 3.2       # ... 3.0 tall, so the head sits 0.2 below the clip face
RAIL_CBORE_SKIN = 0.2    # one sacrificial layer across the bore at the pocket floor

# ------------------------------------------------------------- din clip -----
CLIP_W = 14.0            # width along the rail
# 3.0 matches the module plates exactly. At 4.0 the clip stood 1 mm proud of
# every module face, so the part could not be printed face-down on the bed.
CLIP_BACK_T = 3.0
CLIP_JAW_T = 3.2
CLIP_TOOTH = 2.2         # how far the tooth reaches in under the brim
CLIP_TAB_REACH = 6.0     # how far the release tab stands out past the jaw
CLIP_LEAD_IN = 1.5       # 45-degree chamfer on the latch tooth's rock-on edge (plate 03)
# The latch, rebuilt 2026-10-10 after a display post's clip broke ("a little
# brittle"). Its free beam between root and tooth was only 7 mm, because the
# 18 mm latch was mostly tooth and tab -- and the tooth has to pass the lip by
# 2.05 mm. Beam theory: ~10 % strain at the root against PETG's ~4 % yield,
# and ~80 N to snap on. It now runs the clip's full width (18 mm free beam on
# a 30 mm clip). Plate 03c, 2026-10-10: 1.8 vs 2.0 thick, the user preferred
# the 1.8 (1 nub): ~1.7 % strain, ~6-7 N to snap.
CLIP_LATCH_T = 1.8

# --------------------------------------------------------------- modules ----
# Where each clip-on module sits along the rail. Spaced so bare rail stays
# visible between them -- that gap is the whole point of the system.
MOD_X_PLATE = 72.0
MOD_X_SCREEN = 182.0
# 258, not 262: the 58-wide bin reached x=291, three millimetres into the
# end frame's mortise shroud (x 288..300) -- caught by the rail-cap probe,
# never by a gate. 258 puts its edge at 287, one clear of the shroud and
# one clear of the display crossbar's end at 228.
MOD_X_BIN = 258.0

# Waveshare 2.9" e-paper module: 79.0 x 36.7 PCB, 66.9 x 29.1 active area
EINK_PCB_W, EINK_PCB_H, EINK_PCB_T = 79.0, 36.7, 1.4
EINK_WIN_W, EINK_WIN_H = 66.9, 29.1

# ------------------------------------------------ universal display mount ---
# Open H-frame for ANY hole-mounted display up to the 7" class (sized around
# the Elecrow CrowPanel Advance 7: 180 x 105 board, ~450 g): a spine on two
# clips, two uprights, two slotted crossbars, display face never covered.
# The cruciform plate's epitaph -- "a mounting scheme is only real if the
# fastener can be installed, not just drawn" -- is honoured by construction:
# every adjustable screw runs into an M3 SQUARE nut (DIN 562, 5.5 AF x 1.8)
# captured in a T-channel that stands 11+ mm proud of the rail band, so
# there is nut access at every position of every slot.
DM_BAR_W = 16.0          # bar section, uprights and crossbars alike
DM_BAR_T = 6.0           # 3.8 clamp wall + 2.2 nut channel = 30 layers
DM_SLOT_W = 3.4          # M3 float -- same value as the frame's bar ends
DM_NUT_W = 5.8           # 5.5 AF square nut + 0.3 slide clearance
DM_NUT_T = 2.2           # 1.8 nominal + grid: keeps the clamp wall at 3.8
DM_SLOT_OFF = 3.0        # slot line 3.0 one side of the bar centreline,
DM_HOLE_OFF = 4.0        # fixed crossing holes 4.0 the other -- offset
                         # lines mean a display hole can NEVER collide with
                         # a crossing screw, so both slots run unbroken
DM_UPRIGHT_X = 50.0      # upright centrelines at +/- this from mount centre
DM_UPRIGHT_L = 130.0     # slot reach +/-55: vertical hole pitch 0-110
DM_CROSS_L = 180.0       # slot reach +/-84: spans the Elecrow's outer holes
DM_CLIP_X = 45.0         # the spine's two clips, either side of centre
DM_SPINE_W = 140.0
DM_SPINE_H = 44.25       # same grid rule as BOARD_SPECS: h/2 + 17.675 puts
                         # the latch beam on the 0.2 layer grid at pose -90
# Derived joint lines. The uprights place rotated 90 deg in plane (one +90,
# one -90 -- SAME printed part twice), which maps their local slot/hole
# offsets to these global lines; the crossbars' fixed holes and the spine's
# bosses are computed from the same constants so the three can never drift.
DM_CROSS_HOLE_X = DM_UPRIGHT_X + DM_SLOT_OFF    # 53.0 -- upright slot lines
DM_BOSS_X = DM_UPRIGHT_X - DM_HOLE_OFF          # 46.0 -- spine boss lines
DM_BOSS_PITCH = 24.0                            # two bosses per upright
MOD_X_DISPLAY = 138.0    # mount centre: the 180 crossbar spans 48..228,
                         # clear of the rail bin at 233
# The rail sits only 38 mm up a deck-level face on BOTH variants, so a bar
# centred on it reaches 65 - 38 = 27 mm through the deck (caught by eye in
# the viewer). The uprights therefore ride high: their centres sit RISE
# above the rail, which parks the bottom ends at s = 6, just proud of the
# deck. The engaged fixed-hole pair sits RISE -/+ 12 below the bar centre
# to land on the spine bosses; the bar carries the mirrored pair too, so
# one printed part serves both sides -- and flipping it hangs a display
# LOW instead of high.
DM_UPRIGHT_RISE = 33.0
DM_DEMO_CY = 20.0        # demo display centreline above the rail
DM_CROSS_STATIONS = (DM_DEMO_CY - 40.0, DM_DEMO_CY + 40.0)   # demo holes
                         # at +/-40; stations must stay inside the slots'
                         # reachable band RISE +/- 55 = -22..+88

# ---- display mount v2: two clip-on posts (see bench.display_post) -------
DM_POST_T = 5.0          # bar thickness: 2.2 nut channel + 2.8 wall
DM_POST_TOP = 116.0      # bar top, above the rail centreline
DM_POST_SLOT0 = 26.0     # slot starts above the clip plate (+-21) with margin
DM_POST_X = (MOD_X_DISPLAY - 50.0, MOD_X_DISPLAY + 50.0)   # demo spacing
DM_POST_DEMO_CY = 66.0   # demo display centreline: holes at +-40 land in
                         # the slot's 26..108 reach
# The post's rail lock (2026-10-17). Both display posts' spring latches broke
# in service: the screen leans out from the posts, so its weight -- and every
# press on the touchscreen -- tips the post's TOP into the rail and lifts its
# FOOT, and the only thing holding the foot was the latch's tooth on an 18 mm
# cantilever. Magnets were weighed and rejected (two 6 x 2 discs on the rail
# screw heads hold ~8 N a post; a firm press near the screen's top edge asks
# ~15 N). A screwed keeper worked but the user did not like it (a loose part
# and a hex key). Now a TWIST LOCK, user's pick: a thumb knob on the foot's
# front, keyed through the foot to a hook underneath; a quarter turn
# clockwise swings the hook under the rail's lower lip. Its top is a shallow
# wedge, so the last of the turn draws the foot down snug and friction holds
# it there. Clip-local: y up the post (lip edge at -17.425), z out of the face.
# SCREWLESS since 2026-10-17 (user: "Anything simpler. Less m3 screws the
# better" -- the M3 x 16 that joined knob and hook had been left out, so the
# hook just sat loose): the hook now carries its own shaft, through the
# foot's bore from behind, ending in a hex and a split, barbed tip; the knob
# pushes down over the hex and clicks onto the barbs. Two parts, no screw,
# no nut, and the posts already printed keep their 3.8 bore.
DM_LOCK_Y = -23.0        # lock axis, on the post's centreline below the rail
DM_LOCK_HUB_R = 5.4      # hook's hub: reaches -17.6, clear of the lip edge
DM_LOCK_TOOTH_IN = 4.8   # tooth sector: from this radius out to 2.2 under the lip
DM_LOCK_HALF = 30.0      # tooth's half-angle, degrees
DM_LOCK_Z0 = 1.0         # hook underside, off the rail plane
DM_LOCK_GAP = 0.3        # hub top below the foot: the turn's running clearance
DM_LOCK_WEDGE = (5.75, 6.3)   # tooth top, leading edge -> trailing (lip underside 6.2)
DM_LOCK_SHAFT_R = 3.5    # sets the foot's bore (3.8): unchanged on the printed posts
DM_LOCK_PIN_R = 3.45     # the hook's own shaft in that bore
DM_LOCK_KEY_AF = 5.4     # hex above the foot's front face, into the knob
DM_LOCK_KEY_L = 3.0
DM_LOCK_BARB = (2.6, 3.0, 2.75)   # prong radius, barb radius, knob neck hole radius
DM_LOCK_SLOT = 1.4       # gap between the two prongs: each flexes 0.25 of its 0.7
DM_LOCK_FLAT = 2.6       # printed on its side: everything flat 2.6 below the axis
DM_LOCK_KNOB = (9.0, 22.0, 5.5)   # thumb wing: across, along (locked: along the post), tall

# ---- DIN tilt adapter (2026-10-17) --------------------------------------
# User: a generic DIN device (UniFi UA-Hub-Door-Mini, 113 x 66 x 27.6) would
# not clip on: "too long to be able to clip down far enough". Measured: 39 mm
# below the rail's centreline before the rear tray, against 45-57 for a
# 90-113 mm device. User chose a tilting adapter over rotating the whole rail:
# it locks onto the rail like a display post (hook + twist lock, the same
# lock parts), stands a short TS35 stub out on a toothed hinge, and sets it
# anywhere from the rail's own angle to flat in 15-degree steps.
# Clip-local frame (x along the rail, y up the post, z out of the face).
DTA_HINGE = (14.0, 26.0)      # hinge axis (y, z), along x
DTA_KNUCKLE_R = 11.0          # both knuckle discs
DTA_TEETH = 24                # 15-degree steps
# Tooth phase: the 15-degree stops are counted from FLAT, not from the rail's
# own angle -- the frame's posts lean 37 degrees from vertical (frame.FR_TILT),
# so flat is the arm turned 53 back, and 53 + 90 = vertical is a stop too.
# Stops: flat, -38, -23, -8, +7, +22, vertical (+37).
DTA_FLAT = 53.0
DTA_TOOTH_H = 1.2
DTA_TOOTH_R = (4.0, 10.5)
DTA_BASE_FACE = -12.0         # base knuckle's toothed face (x); it is solid to +15
DTA_ARM_X = (-20.0, -13.5)    # arm knuckle; teeth on its +x face, 0.3 off the base teeth
DTA_STUB_L = 40.0             # short rail, x -20..20
DTA_CARRIER_T = 3.0
DTA_KNOB = (10.0, 5.0)        # thumb knob radius, thickness, outside the arm knuckle
DTA_SCREW_L = 20.0            # M3 x 20: head pressed into the base, nut in the knob

# ---- CrowPanel Advanced 7" ESP32-P4 (1024x600, no camera), no case ------
# From Elecrow's own STEP (ref/crowpanel7_p4/crowpanel7_p4.stp, measured
# 2026-10-15): PCB 176.9 x 104.0 x 1.7, LCD 165 wide on its front, four
# corner M3 slots (3.2 wide, centres x +-85.5, z +-47.4..+-50.6) 3 mm in
# from the edges, outside the glass. Tallest part on the back: 8.1 mm (two
# 12 x 6 parts on the bottom edge, x 42..77). The posts sit 100 apart, so
# their screws would land on the components -- hence a backplate.
CP7_HOLE_X = 85.5
CP7_HOLE_Z = 49.0          # mid-slot
CP7_PCB_W, CP7_PCB_H, CP7_PCB_T = 176.9, 104.0, 1.7
CP7_BACK_CLEAR = 8.1       # tallest part behind the PCB
DBP_STANDOFF = 9.5         # PCB back to the bars' front: 1.4 over the tallest part
DBP_BAR_T = 6.0            # vertical bars: room for a flush M3 cap counterbore
DBP_RIM_T = 4.0            # perimeter frame, flush with the bars at the back
DBP_RIM_W = 6.0
DBP_BAR_W = 14.0           # = the post bar's width
DBP_BAR_X = 50.0           # bars at +-50: the posts' DM_POST_X spacing
DBP_POST_HOLES = (-20.0, 20.0)   # M3 x 8 cap into the posts' square nuts
# Corner bosses: BOLTED, not self-tapped (2026-10-17). The printed bosses were
# 6.4 dia round a 2.5 pilot -- 1.7 of wall outside the thread, 11.5 tall,
# printed upright -- and the user's M3 x 12s split them and sheared them off
# at a layer line ("breaking in half from the stress and just spinning"). A
# thread-forming screw loads its boss in hoop tension, across the layers.
# Now: 10 dia boss from the bed up, a 3.4 clearance bore, and an M3 nut
# pressed into a hex pocket in the BACK face; an M3 x 16 from the front pulls
# the nut up against the pocket ceiling. Plastic sees only compression.
# Nearest part on the board's back is 7.0 from a hole centre (STEP), so r 5
# clears it by 2; the boss stands 1.5-2 proud of the board's corner edges.
DBP_BOSS_R = 5.0
DBP_BORE_R = 1.7
DBP_NUT_AF = 5.7           # press fit: PLA holes print ~0.2 under (foot gauge)
DBP_NUT_DEPTH = 4.0        # nut seats 1.6 deep: an M3 x 16's tip lands 0.4 past it
CP7_SCREW_L = 16.0
# Dovetail socket on the backplate's top rim for the mic crown (2026-10-17):
# a block on the rim's front, a channel open at its top end and closed at
# y 41; its walls lean in toward the front, so the crown's tongue slides down
# it from above and cannot pull forward. Leaning 30 deg off vertical, the
# walls print without support (back face on the bed).
DBP_SOCK_Y = (39.0, 55.0)       # block; the channel's closed end is 2.0 thick
DBP_SOCK_FLOOR = 1.2
DBP_SOCK_W = (18.0, 28.0)       # channel at the floor, block
DBP_SOCK_D = 4.0                # channel depth (to the block's front)
DBP_SOCK_ANG = 30.0
# v2, same evening (user: "make sure it's all nice and solid"): the channel
# TAPERS, DBP_SOCK_TAPER narrower each side at the closed end than at the
# mouth, and the tongue matches it, so the crown wedges tight as it seats --
# a sliding taper dovetail. 4 deg is self-locking for PETG on PLA (tan 0.07
# against friction ~0.3), yet a firm pull lifts it out. Each 0.1 a print runs
# fat per side seats it 1.4 higher, which the 7 mm over the screen absorbs.
DBP_SOCK_TAPER = 1.0

# ---- Mic crown: a reSpeaker XVF3800 above the screen (2026-10-17) -------
# Measured in Seeed's STEP (ref/respeaker_xvf3800): board dia 100.0, PCB
# 1.11. Everything but the LEDs is on the BACK, the deepest part 6.74; the
# logo face has the 12 LEDs at r 40 and the mics' sound ports at r 46.7 on
# the diagonals, and nothing past r 41. The mounting holes are THREE M2
# (2.2): (0, -34) and (+-21.35, 24.5) in the drawing's frame. The drawing's
# 66 x 66 square is the four mics, not holes. Mid-mount parts poke past the
# edge: USB-C at -90 deg (r 53.2), the 3.5 jack at -78..-60 (r 54.8), side
# parts at 0 / 180 (r 51.7 / 50.4), the XIAO's USB-C at 90 (r 49.7).
# No screws: the board tucks under two fixed lips and a sprung third clicks
# over it; two pins in its M2 holes stop it turning.
MIC_R = 50.0
MIC_PCB_T = 1.11
MIC_HOLES = ((0.0, -34.0), (-21.35, 24.5), (21.35, 24.5))   # drawing frame
MIC_PINNED = (0, 2)            # which holes get a pin
MIC_TURN = -90.0               # drawing -> crown: its USB-C points along -x
MIC_Y = 110.0                  # board centre, display-local (screen centre 0)
MIC_STANDOFF = 8.0             # crown face to the PCB's back: 1.26 over 6.74
CR_T = 3.7                     # the tongue (the socket is 4 deep)
CR_RING_T = 5.0                # ring and stem, thicker than the tongue (v2)
CR_STEM = (14.0, 24.0, 70.0)   # stem half-width at the socket, where it meets
                               # the ring, and that height (display-local y)
CR_BLEND = 8.0                 # fillet where the stem flares into the ring
CR_CHAMFER = 0.8               # front edges, as on the lock wing
CR_RING = (28.0, 54.0)         # the ring behind the board
CR_HOOKS = (-120.0, -60.0)     # fixed lips, crown angles (0 = +x)
CR_LATCH = 75.0                # the sprung lip
CR_LATCH_ANCHOR = 45.0         # its spring beam runs round to here
CR_COL = (3.0, 7.0)            # lip column: radial, tangential
CR_EDGE_GAP = 0.25             # board edge to the columns
CR_LIP = (1.0, 1.6)            # overlap onto the board's face, lip thickness
CR_SLIDE = 0.1                 # tongue clearance each side, seated (taper: v2)

# ----------------------------------------------------------------- colour ---
# Only used by the render script.
COL_BODY = (0.874, 0.855, 0.808)     # bone / warm off-white
COL_RAIL = (0.145, 0.152, 0.168)     # graphite
COL_ACCENT = (0.776, 0.318, 0.169)   # burnt orange

# Dedicated board plates -- hole patterns as FULL spacings (dx, dy), plate
# size (w, d). One plate per board family; screws.py audits the boss pilots
# against these same numbers.
BOARD_SPECS = {
    "esp": {"patterns": [(45.5, 22.0)],               # DOIT DevKit v1
            "size": (58.0, 44.25)},   # depth puts the latch beam on the 0.2 layer grid at pose -90
    "pi":  {"patterns": [(58.0, 49.0),                # Pi 4 / 3B+
                         (58.0, 23.0)],               # Pi Zero
            "size": (70.0, 62.25)},   # same grid rule
}
