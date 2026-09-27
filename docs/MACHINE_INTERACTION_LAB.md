# Totolina + Machine Interaction Lab

Development-only animation review inside the existing game01 project. The
approved shared components now also power production Kitchen gameplay; the lab
itself remains isolated from production state/navigation. Old asset paths and the
existing merge-effect lab are deliberately retained for a later cleanup audit.

`AGENTS.md` and `docs/ANIMATION_GUIDELINES.md` were read and followed. The latter
remains the animation architecture source of truth. This document describes only
this experimental presentation and its validation.

## Current designer-editable presentation

Layout and shared production animation tracks now live in
`scenes/presentation/machine_drop_presentation.tscn`, with nested
`totolina_operator.tscn` and its saved blink timeline. Scripts bind those nodes,
capture authored rest transforms, and animate relative motion.
The lab uses the same scene, plus its existing cosmetic falling-sample preview.
See [PRESENTATION_TUNING_GUIDE.md](PRESENTATION_TUNING_GUIDE.md) for actual node paths,
Inspector values, animation ownership and save/reopen validation.

Current calibration: feeder scale **0.32**, center **(240,121)**; Next
**(240,95)**, Current **(240,180)**; shutter **(190,221)** overlaps the feeder foot.
Score token **0.061**; masks use editable Control offsets **−4 / +4**.
The production visual floor now aligns source row **1595**, rather than 1567,
with the unchanged physics floor. The central lower interior AND first 70
footer-source pixels draw behind bodies; side rails/collection trim remain front.
This section supersedes earlier dated layout values below; approved pose/timing
values are unchanged.

## Open / run

1. Open the existing `game01/project.godot` in Godot 4.7.
2. Open `res://scenes/debug/machine_interaction_lab.tscn`.
3. On your **Mac**, press **Command + R** or click **Run Current Scene** in the
   top-right toolbar. Command + B runs the production main scene, which has no
   navigation entry for this lab. These are the [documented macOS shortcuts](https://docs.godotengine.org/en/4.4/getting_started/step_by_step/nodes_and_scenes.html#running-the-scene).
4. Open **Lab controls** for **Full drop**, or tap/click the chamber to select X
   and simulate a drop. Hide controls for the full-phone composition.
5. Inspect **Cat + button**, **Shutter**, **Nozzle move**, **Feeder**, **Excited**,
   **Surprised**, and **Blink / Idle** independently.
6. Adjust Target X and 0.25×–2.0× speed. Loop repeats the selected action after a
   0.35s review rest (also affected by speed). Blink / Idle uses its own natural
   interval. Stop / Reset cancels both pending repeats and idle motion, and returns
   to Wheat CURRENT / Flour NEXT with the nozzle at X=250. The **Collection preview**
   slider scrubs a fixed nine-position sample track; it does not access discoveries.

```sh
/Applications/Godot.app/Contents/MacOS/Godot --path . --scene res://scenes/debug/machine_interaction_lab.tscn
```

The scene starts with calm idle enabled. A debug-build check runs before UI,
artwork or presentation construction; release execution hides/frees the lab.
No real release export was executed.

## Files and reuse boundary

- Scene: `scenes/debug/machine_interaction_lab.tscn`
- Review UI and fixed sample choices: `scripts/debug/machine_interaction_lab.gd`
- Layered character: `scripts/presentation/totolina_operator_presentation.gd`
- Machine timeline/composition: `scripts/presentation/machine_drop_presentation.gd`
- Focused native checks: `tests/machine_interaction_lab_validation.gd`

The reusable scripts depend on artwork and Godot presentation nodes, not lab UI,
production controllers, creation definitions, recipes, saves or reward systems.
The machine accepts `set_items(current_texture, next_texture, replacement_texture)`
and `set_score_preview(text)`. It exposes `set_target(x)`, `set_playback_speed(rate)`,
`play_action(name)`, `reset()`, `contact_reached(target_x)` and `finished(action)`.
`set_items` rejects changes during an active cycle. A visual slot handoff updates
only the displayed textures; the caller supplies future artwork. Only the lab
chooses/cycles Wheat → Flour → Cake Mix. It never draws gameplay RNG.

`contact_reached` is a cosmetic timing cue, **not authority to spawn an item**.
The signal exists for the lab marker; no production signal is connected to it.
Full and press actions emit it once. Other previews do not emit a drop/contact cue.
Production retains gameplay authority as described below.

## Production integration

`scripts/presentation/kitchen_machine_presentation.gd` lays out the shared
machine over separate rear/front frame layers, fitted to the **unchanged**
header and physics floor while filling the portrait viewport. Each layer maps
the existing image through three NinePatchRect regions (header, chamber, footer);
no source image is changed. The original character poses, button tracks, shutter
tracks, distance-sensitive nozzle travel, feeder timeline, and excited reaction
are reused from `machine_drop_presentation.gd`; production never loads the debug
lab scene. `production_mode` omits mock environment/UI and the fake falling item.
Its default is false, retaining the approved lab output.

`physics_sandbox.gd` accepts one chamber press and latches CURRENT + clamped X.
Its own physics-step clock uses the shared `CONTACT_SECONDS = 0.20` and full-drop
length `0.62`. At contact it creates one real body, promotes the existing NEXT,
and draws exactly one new NEXT using the existing unlocked stage/seed. It does
not connect gameplay to `contact_reached` or animation completion. Long ticks
are split at release so the incoming artwork is supplied before feeder motion
continues. CURRENT artwork disappears exactly at the physical handoff; there is
no duplicate falling sprite. Extra touches do not queue drops or promote held
secondary fingers. Header/UI touches do not drop.

The new physical release **position** is the displayed nozzle outlet (shared
`RELEASE_Y = 269` in machine-local coordinates). The previous chamber-top spawn
height cannot visibly exit this larger top assembly; no wall, floor, body size,
gravity, danger threshold or merge physics was moved to accommodate it. Nozzle
targets include both collider clearance and the nozzle's visual half-width.
The danger line still marks the exact gameplay threshold, not an invented visual
threshold; its distance below the upper frame varies with aspect ratio.

Draw order: backdrop → rear (-5) → lower interior floor (-1) → nozzle (0) → real
Pieces (1) → existing merge effects (20+) → foreground rails (30) → top machinery
(40+) → CanvasLayer UI/results.
Only the empty center of rear/front art stretches vertically. The visible front-interior floor
anchor is 236 source pixels above its bottom, at source Y=1595.
No source images are edited. Old bowl/Tolina/HUD nodes remain hidden as recovery
resources pending the separately requested cleanup audit; the result card keeps
its existing character image and behavior.

Feeder preview scales are scene-authored Sprite2D transforms:
CURRENT `0.110`, NEXT `0.105`, shared by lab and production.
NEXT grows smoothly into CURRENT during the shared handoff. Glass stays above
previews; shutter stays below them. The score monitor uses a live Label padded
to at least five digits; longer totals fit by reducing only the digit font size.
Pulse remains visible above it. Existing localized
`DROP_NEXT` and `DROP_CURRENT` labels are reused. Off/on and surprised assets
remain available without new gameplay behavior.

A successful real merge requests the shared excited reaction. Press has priority:
merges during press coalesce into one pending reaction. A new player press can
interrupt a cosmetic reaction immediately. No animation affects rewards or
physics. Idle blink uses the cat's private cosmetic RNG. Restart, Play Again,
game over, focus loss/pause, viewport relayout, debug Clear Board and teardown
cancel the pending cycle/reaction.
Before contact, cancellation creates nothing and consumes no RNG; after contact,
the released body/queue advancement remain authoritative (a normal Restart then
clears the run as before). No delayed gameplay callback survives teardown.
The visible danger line draws above the foreground trim while staying at the
exact existing gameplay threshold; on short portraits it can cross that trim.

Collection reuses the approved **larger, clipped track** proportions with fixed
shared foreground masks. A horizontal ScrollContainer browses all nine canonical
slots; discovery only changes artwork. A local indexed-touch adapter is needed
because Godot 4.7's scrolling expects mouse-emulated touch and this project's
emulation is disabled. It updates native scrollbar position, with no custom
inertia or snapping; wheel/trackpad behavior remains native. Recipe Collection
navigation and persistence are unchanged. The development spawn toggle appears
only with the `editor` or explicit `dev_tools` feature, not every debug export.

Run `python3 tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --suite machine --graphical`
for real-drop, seeded handoff, cancellation, timing, reaction and portrait checks
plus the preserved lab tests. Full regressions additionally cover touch routing,
all eight merges/rewards, spawn unlocks, discovery, sizing and the merge-effect
lab. Physical-device feel, safe areas and sustained performance still require
user testing; desktop captures are not iPhone validation.

### Latest approved presentation sync

The arm/shoulder overlap, `EYE_SCALE = 1.10`, and `EAR_SCALE = 1.05` already
propagated through the shared Totolina component. Cat/button positioning, feeder,
shutter, nozzle, score monitor, and every animation track were already shared;
the production sync does not duplicate or retune them. Preview scaling remains
the existing production 0.110 / 0.105 for readable actual CURRENT/NEXT items.

The production-only frame layout now covers the full viewport. Three regions
of each existing rear/front image retain a safe header, unchanged nozzle
transform, and the source Y=1595 front-interior floor aligned to the physics floor. Empty
header/middle/trough portions absorb different portrait heights. This preserves
drop/input/debug-spawn coordinates and fixed bottom control touch areas rather
than relocating the physical chamber to match a non-physical lab mockup.

The collection uses shared 0.13 icon scale, 100-unit pitch and 67-unit height at
500 design-width units. Its clip viewport stays above the existing controls;
unknown slots use mystery artwork and known slots use their CreationDefinition
texture. Edge masks are drawn above the scrolling row and cannot intercept input
(Control anchors use Mouse Filter Ignore). Endpoint padding clears the first/last
bubble from the masks. No automatic compaction or discovery-based scrolling is
used. At 405×720, canvases are ~54px, with four full icons at the initial position
and a partial fifth during browsing, depending on scroll offset.

### Production polish (2026-09-21)

- Shared eye anchor moves from (390,173) to **(401,173)**, matching the face/mouth
  axis. All three blink poses and both expressions share it, pivot (164,64),
  scale **1.10**. Body, ears, arms, contact and reaction timing remain unchanged.
- Shared feeder scale **0.252 → 0.29**, center (246,117); NEXT (246,99), CURRENT
  (246,171). Glass remains above both previews and the shutter. Labels follow the
  feeder's X. The score housing remains at (320,95); the glass ends before it.
- Shutter housing is **100px** wide at (196,190), inside the feeder silhouette.
  Its iris is visible through the lower glass; housing is covered by the foot.
  All shutter keyframes, release .200s, nozzle and .620s cycle are unchanged.
- Production uses disjoint native rectangular clips of the existing Chamber
  nine-patch: upper area, two lower side rails, and lower interior. Only the
  middle of the bottom 128-source-pixel band (X=96…763) draws at Z=-1. The same
  texture mapping is used in every clip, without double-alpha overlap, shaders,
  source PNG edits, physics movement, or globally raising bodies above rails.
- Debug selector uses a PopupPanel with nine native 44px-high Buttons, rather
  than PopupMenu's mouse-dependent activation. All nine fit the supported phone
  sizes. See `tests/README.md` for explicit export feature setup and limitations.

Older dated lab notes below are historical; current constants and this section
supersede their feeder/eye/carousel values. The lab's collection remains a
scrubbable visual sample; the production collection is interactive.

The supplied reference is actually `docs/gameplay_machine_layout_reference.jpg`
in this working tree (not `docs/reference/…`); it is used unchanged. Historical
lab-only notes below describe the earlier animation pass, before this sync.

Totolina exposes idle/reset/speed and pose properties; `author_press()` and
`author_reaction()` append the same small authored tracks to a caller's timeline.
Machine animations use these helpers, rather than maintaining a second copy of
cat timing. The cat's idle AnimationPlayer is stopped during coordinated actions.

The standalone machine retains its 500×550 default mock composition. The lab
calls `layout_preview()` to fit a 500-unit design width to the entire portrait
viewport, extending the chamber vertically. Separate environment/rear/front
images remain distinct; matching nine-patch mapping preserves decorative trim.
The cosmetic falling item renders above the nozzle and below the foreground
frame. The animated arm renders above the body and button cap, below the fixed
button housing. A small body-texture region covers only the shoulder's root seam.
The latest reference-matching details below supersede earlier layout history.

## Actual asset paths

The supplied files differ from the requested directory layout:

- Cat: `assets/characters/totolina/` — 15 PNGs, including the four locked arm images.
- Environment/machine: `assets/worlds/environment/` — 19 PNGs; the replacement
  machine artwork is **not** under `assets/worlds/kitchen/environment/`.
- Collection: `assets/worlds/kitchen/ui/collection/` — 3 PNGs; there is no replacement
  collection folder under `assets/worlds/kitchen/ui/`.
- The right mask is literally `├── collection_mask_right.png`. The plain
  `collection_mask_right.png` basename is absent. The lab references the existing
  literal name; it does not rename, copy or migrate it.

Missing required artwork: **none after resolving actual paths**. All 37 current presentation PNGs
and the three existing sample-creation textures load in Godot. Exact filenames,
dimensions and alpha percentages appear in the inventory below.

## Source-art and alignment findings

- The full-screen 1080×1920 background is intentionally opaque. All other new
  images have real alpha. Source contact sheets and phone renders showed no baked
  checker, gray, dark or white rectangular backgrounds. Artwork was not repainted,
  cropped on disk, renamed or deleted.
- Ears retain independent Sprite2D layers behind the head. Their source-space
  base pivots are left (130,155), right (62,155), attached at body-space
  (240,176) and (552,176). The padded canvases are compensated with sprite offsets;
  each base now overlaps the head, suitable for a future small twitch. Cat scale
  remains 0.17; both ears now use uniform scale 1.05 (previously 1.3).
- The locked arm set contains exactly four 384×384 images: idle, press 01,
  press 02 and press 03. Press 03 is full button contact. `ARM_FILES` explicitly
  lists these files; loading and pose clamping use that list's length.
- All four arms use one uniform 1.10 scale and body-space shoulder anchor
  (650,410). Source pivots are idle (110,60), 01 (130,30), 02 (130,30), 03 (130,20).
  Sprite offsets are the negatives of these pivots; press sprites use the shared
  anchor, with an idle-only position correction below. This replaces the large
  negative-Y optical pivots with attachment points on the painted forearm roots.
  Fixed rest rotations are -20.1°, -37.2°,
  0°, 0°: idle clears the upper button edge and inward-curled 01 exposes its paw.
  A small body-texture overlap hides only the root seam. No animated rotation or per-frame scale change
  is used. Totolina is at (6,58.4); its overall scale remains 0.17.
- The new painted pale-paw widths are approximately 99/116/119/128 source pixels.
  This is much closer than the previous artwork; some drawn perspective/shape
  variation remains. Phone renders show no obvious inflation or positional pop.
  Short alpha blends can still show two faint silhouettes at slow review speed;
  final subjective smoothness requires user review. No source pixels were edited.
- Eye canvases are consistently 328×128, with visible bounds agreeing within
  about 1px. `blink_01` is half-open, 02 almost closed, 03 closed. No separate fully
  open neutral eye asset was supplied. Idle uses 01; excited/surprised stay reserved
  for their expressions. Eyes use the same placement and scale for all states.
- Mouths share 128×128 canvases but have different visible heights (54–87px) and
  touch the top source edge. A common nose attachment aligns them without trimming.
- Button chassis drawings differ slightly across the 1024×384 frames. Fixed
  chassis regions come from 01; only the button region (560,0,340,230) crossfades.
  This holds the broad chassis and left post still. Minor variation inside that
  local region remains subject to review.
- Shutters are 1024×208, **01 closed → 06 open**. Gold housing bounds vary by a
  few source pixels (up to 7px on the right edge). A fixed 01 housing plus a shared
  interior Polygon2D mask confines animation to the iris. The source PNGs are
  intact; only displayed geometry is masked. Small iris shape differences remain.
- Nozzle 512×256 and glass 512×768 are aspect-preserved. Rear and foreground use
  aligned 859×1831 canvases; their different transparent regions are intentional.
- Token/colon artwork reaches some source edges; warm glow is part of that art.
  The displayed score itself is a Godot Label, not baked digits.

## Timelines at 1×

| Behavior | Timeline |
| --- | --- |
| Calm idle | Hold normal pose; private RandomNumberGenerator waits 2.5–5s between blinks. No breathing bounce or ear twitch. |
| Blink | 01 at .000 → 02 at .050 → 03 at .095, hold through .140 → 02 at .190 → 01 at .240s. |
| Arm press | Idle .000 → 01 .075 → 02 .135 → 03 .200, hold to .235 → 02 .305 → 01 .370 → idle .440s. |
| Red button | Up through .040 → slight depression .075 (pose 0.25) → intermediate .135 → fully down .200, hold to .235 → intermediate .305 → slight depression .370 → up .440s. |
| Shutter | Opening .020–.170 in five 30ms steps; hold open to .350; close .350–.500 in five 30ms steps. Each direction takes .150s. |
| Nozzle | Ease-out X motion; duration interpolates .080–.180s over the 356px travel range. X clamps to 72–428. No overshoot. Consecutive moves start at the parked X. |
| Feeder alone | Current travels 53px into the shutter/fades over .000–.120; Next moves downward .035–.240; replacement Next fades/scales .80→1.00 over .200–.360; cycle ends .420s. |
| Excited | Normal → excited eyes/mouth .000–.070; hold to .380; return by .560. Whole character lifts 16 source px at .140, settles through +3px at .320, returns at .560. At 0.17 cat scale this is only 2.72 logical px before preview fitting. |
| Surprised | Same .560s review-only expression/lift envelope, using the supplied surprised eyes/mouth. No danger/game-over behavior. |

Arm/face poses overlap with eased alpha; small mechanical frame steps blend
inside their fixed housing. No large rotations, repeated bouncing, particles,
AnimationTree or nested Tween sequence is used.

### Full drop: 0.620 seconds

| Time | Visible action |
| --- | --- |
| .000 | Latch target X; nozzle moves; cat begins reaching. |
| .020–.170 | Shutter opens while the paw approaches. |
| ≤ .180 | Nozzle has arrived; arm approaches full contact. |
| **.200** | **Arm press 03 and red button fully down, shutter open, DROP MOMENT marker fires once.** |
| .200–.320 | Current sample exits glass and fades. |
| .200–.550 | A cosmetic copy appears in front of the nozzle, descends through the mock chamber, and fades. No body/physics spawning. |
| .235–.440 | Next slides down into Current. |
| .235–.440 | Paw withdraws through 02/01/idle; red button returns up by .440. |
| .350–.500 | Shutter closes. |
| .400–.560 | New sample Next fades/scales into the upper slot. |
| .620 | Complete; final item slots remain populated; idle may resume. |

The cosmetic drop occurs at .200s, before the full sequence ends. Target changes
during a cycle affect only the next cycle. The contact event reports the latched
destination even on a long render frame. A running action rejects additional
full-cycle commands. The lab disables action buttons while busy; Stop remains
available. This is lab simulation, not production input locking.

## Speed, replay and teardown

The machine uses one AnimationPlayer clock for all coordinated tracks. Speed uses
`speed_scale`, including mid-cycle changes. Idle's player and private countdown,
plus the lab's between-loop rest, use the same selected rate. No global time scale
or gameplay RNG is changed.

Reset stops players, clears expression/arm/button/shutter poses, restores item
positions/scales/rotation/alpha/visibility, resets the nozzle, and cancels pending
lab repeats. Sprites are built once. There are no Tween instances or Timer nodes.
Method-track callbacks are immediate, avoiding deferred contact callbacks after
stop/free. Teardown stops playback; signal connections do not accumulate.

Tune authored values in `PRESS_KEYS`, `author_reaction()`, `_build_animations()`,
`_author_feeder()`, and the source pivots/composition values. The lab's target and
speed sliders support immediate review; there is no large tuning framework.

## Score / collection preview

The active monitor contains the supplied token, supplied colon, and a Godot Label
set to `00128` by the lab. Off/on monitor assets also load for validation. There
is no score calculation, reward pulse or production score connection.

A fixed nine-position sample track contains Wheat, Flour and Cake Mix artwork,
then six mystery bubbles representing the remaining canonical creations. The
lab's slider scrubs it for edge-mask review; there is no gameplay scrolling,
discovery or collection-state implementation. All icons use uniform scale 0.13
(previously 0.08), at 100 design-unit spacing. At 405×720, three bubbles are fully
visible and two are partly covered at the edges; four are offscreen.

The clipped viewport is 468×67 at X=16 and Y=`preview_size.y - 96`, anchored to
the bottom panel. Mask **painted alpha bounds**, rather than padded 128px canvases,
align with its outer edges: left position (0,0), offset (-17,-3); right position
(468,1), offset (-109,-5). Both retain uniform scale 0.55 and local Z=1 above
the icon track's Z=0. Horizontal mask placement is unchanged. No source art is
flattened, repainted or resized on disk.

## Layout refinement (2026-09-20)

The feeder's outer feet end around Y=204, but its center underside is near Y=200.
The shutter is 130px wide, centered at X=265 and starting at Y=197, overlapping
the center underside as well as the feet. CURRENT travels to Y=221 with ease-out
positioning, reaching the gate
while still visible; every feeder timestamp and alpha key is unchanged.

The nozzle center is Y=264, with its upper lip tucked behind the foreground
rail. Its absolute Z=0, released item Z=1, and foreground frame Z=2 establish
nozzle → item → edge masking. The item's release center is Y=269. Nozzle X
range, duration calculation, easing and all timeline keys remain unchanged.

TopMachine Z=3; the body inherits that layer. The arm's local Z=-1 gives effective
Z=2, followed by body Z=3, button cap Z=4, and fixed housing Z=6. The body masks
the shoulder seam, and the machine can cover the lower paw naturally. The CURRENT
label is centered on the upper rail below the gate, clear of the score feet.

The top-row size pass enlarges the feeder glass by 20% (0.21 → 0.252), anchored
at (265,115) so its painted bottom remains at Y≈204. NEXT (265,99) and CURRENT
(265,168) are centered in the enlarged compartments. The shutter follows the
feeder's X; the later attachment pass lifts its Y by 4px, retaining width and
timing. Preview/falling item sizes
and nozzle movement remain unchanged. Feeder local layers remain shutter 0,
item previews 1, glass 2; chamber layers remain nozzle 0, falling item 1, frame 2.

The score housing and both legs use one aspect-preserving 0.35 sprite scale,
25% larger than 0.28, at (320,95). Its painted soles reach Y≈225 on the platform.
The score root stays at scale 1: content is tuned independently, with token
scale 0.048 at (34,51), colon scale 0.16 at (59,51), and a 28px score font at
(72,31). The score caption is centered above the housing. The size pass preserved
Totolina and the button; the later shoulder pass below moves only the button. No separate visual reference
was available for this pass; these proportions were tuned against the supplied
machine artwork and the user's 1.20–1.30 monitor-size guidance.

Full-drop timing remains **0.20s contact / 0.62s total**. Earlier layout passes
refined both presentation scripts, this document, and the existing validation
script. The top-row size pass changes only `machine_drop_presentation.gd` and
this document. The lab scene and UI script, all assets, and all production/merge
files are unchanged.

## Shoulder / button alignment refinement (2026-09-20)

This earlier pass set all four arm roots to (650,430), 23 source pixels below
the previous anchor. The short curled poses no longer float on large negative-Y pivots.
Arm local Z changes from 2 to -1 so the body covers the root seam throughout
the unchanged idle → 01 → 02 → 03 → 02 → 01 → idle alpha blends.

The complete Button assembly moves from (42,166) to (32,166): 10 logical pixels
left. Its Y, uniform 180/1024 scale, fixed chassis regions and cap layering remain
unchanged, so it stays seated on the platform. The natural 03 reach now meets
the button without stretching its artwork. Contact remains .200s, press ends
.440s and full drop ends .620s. No timing, reparenting, source-art or production
changes were needed.

Only the two presentation scripts and this document change in this pass. The
existing validation script remains unchanged. Exact renders at all three phone
sizes and 1×/0.25× frame sequences were inspected. The idle paw is partly
occluded by the upper button edge; raised poses and contact remain readable.
Source paw widths still vary with the drawing (99/116/119/128px), and short alpha
blends can show faint double silhouettes at slow speed. These require subjective
review; no per-frame scaling was added to disguise the source proportions.

## Left-edge / feeder attachment refinement (2026-09-20)

Totolina moves from (26,55) to (6,58.4), and the complete Button assembly moves
from (32,166) to (12,166). Both move 20 logical pixels left together, preserving
horizontal paw/button alignment and bringing the composition close to the left
frame edge. Only Totolina moves down, by 3.4 logical pixels.

The shared shoulder anchor moves from body-space (650,430) to (650,410) to
compensate for that body lowering: 20 source pixels × 0.17 = 3.4 logical pixels.
All arm frames therefore keep their previous contact height and path relative
to the button while the body sits lower behind their roots. No individual frame
pivots, rest angles, scales or timing keys change. Ear/face offsets within the
character stay unchanged. The body masks the roots throughout the press/return.

The shutter moves from Y=201 to Y=197. At its horizontal center, the feeder's
painted bottom reaches Y≈199.7; the gate's painted top now begins at Y≈197.5,
providing about 2.2px of overlap instead of the old 1.8px gap. The feeder remains
in front: local shutter Z=0 → item previews Z=1 → glass Z=2. Feeder position,
scale and Current/Next centers are unchanged. Nozzle Z=0 → released item Z=1 →
foreground frame Z=2 remains intact, with all X movement and drop timing intact.

Score assembly, collection masks, production and merge-effect files are
unchanged. Native renders at 390×844, 405×720 and 540×960 cover idle, every arm
pose, full drop, blink, excited and surprised. The existing 678 headless and 873
graphical checks pass. Review the final left margin and shoulder contour by eye;
the changes use the requested spatial relationships and existing machine art.
All 21 captured states compare pixel-identically outside the repositioned
Totolina/button and shutter regions; the score, feeder contents and chamber
composition remain unchanged.

The subsequent idle-only refinement adds body-space offset (-48,-12) to the
hanging arm: position (650,410) → (602,398), equivalent to 8.16 logical pixels
inward and 2.04 pixels upward at the unchanged 0.17 cat scale. This closes the
torso/arm gap while preserving the body's Z masking. The sprite's texture offset
(-110,-60), rotation -0.35 radians and scale 1.10 stay unchanged. Press 01 needs
no correction; press 02/03, body, machine layout and all timing remain unchanged.
Normal and quarter-speed renders cover the idle → 01 crossfade and full drop.

## Reference-matching layout (2026-09-21)

Reference: `docs/gameplay_machine_layout_reference.jpg` (the supplied file is in
`docs/`, not `docs/reference/`). Its bytes are preserved. Earlier dated sections
above describe prior passes, not the current arm layering or eye/ear sizes.

- Arm local Z changes **-1 → 2** for all four poses. In the lab, effective draw
  order is body 3 → cap 4 → arm 5 → fixed button housing 6. The body stays at
  (6,58.4), scale 0.17. Arm scale 1.10, anchor (650,410), idle correction
  (-48,-12), pivots, rotations and every keyframe are unchanged. The idle arm
  remains at (602,398); press 01/02/03 receive no position changes.
- `ShoulderOverlap` reuses the existing body texture's 170×95 region at
  (530,325), local Z=3. It covers the small upper root seam under the cheek;
  the arm and paw remain visible in front of the torso. This adds one Sprite2D,
  without a new image, mask shader or animation track.
- All blink/excited/surprised eye overlays use uniform **1.45 → 1.10** scale.
  The paired artwork retains its shared (390,173) center and (164,64) pivot;
  no independent pupil edits. Both ears use **1.30 → 1.05**, preserving their
  separate base pivots and attachment positions. Rendered alternatives were
  compared against the supplied reference before choosing these values.
- The lab preview now occupies its entire viewport. Width fits the existing
  500-unit design; one uniform parent scale is used. Front and rear use identical
  NinePatchRect bounds with unchanged 56/56/425/236 source margins and uniform
  500/859 art scale. Only the empty chamber middle changes height; decorative
  corners, top rail and bottom panel retain their proportions. The collection
  follows the bottom panel. The foreground's painted bounds reach all edges of
  its 859×1831 source canvas; no outer alpha padding prevents edge-to-edge use.
  The rear's transparent margins outside its chamber are intentional.
- The root fallback background moves to Z=-20 so it no longer covers the
  negative-Z environment (-10) and chamber rear (-9). Nozzle 0 → falling item 1
  → foreground 2 → top machine 3 remains intact. Feeder local order stays
  shutter 0 → Current/Next/Incoming 1 → glass 2. No reparenting at DROP MOMENT.
- Review controls are in an opaque drawer, collapsed by default, instead of
  shrinking the machine into a card. `set_preview_safe_insets()` accepts logical
  insets for an explicit safe-area preview. This is not hardware safe-area
  detection or a production device integration.
- Collection icons grow **0.08 → 0.13 (+62.5%)**. At 405×720 their 512px source
  canvas occupies about 54px; painted bubbles are about 49–51px depending on
  source padding. The reference trough contains no bubbles, so icon size is
  tuned to the trough's available height, not a claimed reference measurement.
  The track is visual-only and uses the unchanged foreground masks.

The full-phone frame, collection preview, labels and drawer changes are **lab
only**. Shared Totolina cosmetics also appear in the existing production
presenter. The pre-existing production layout, nine-slot collection row, physical
geometry, touch routing, save data and gameplay state are not edited. Top-machine
positions/sizes and all timeline functions remain unchanged: contact .200s,
press .440s, full drop .620s. No feeder, shutter, nozzle or score retiming.

## Validation and limitations

- **VERIFIED:** 693 headless lab checks, 900 native rendered lab checks, and 163
  quarter-speed capture/completion/reset checks pass with zero failures.
- **VERIFIED:** 390×844, 405×720 and 540×960 native captures cover idle, all press
  poses, drop/release/feeder exit, blink, excited and surprised. Normal-speed
  and quarter-speed frame sequences cover shoulder attachment, button contact,
  feeder/nozzle depth and return. No new layer-switch pop or clipping observed.
- **VERIFIED:** repeated completion/interruption, reset/replay, constant node
  count, no Tweens, 0.25×/1×/2× and live rate changes, three nozzle destinations,
  one .200s contact per cycle, long-frame contact, and active teardown.
- **VERIFIED:** engine-routed mouse/touch input and Stop button; drawer controls
  fit all three viewports. Full-phone rear/front bounds match. Collection was
  rendered at beginning/middle/end of the sample track; icons are clipped and
  edge masks remain in front. A simulated 32px top / 24px bottom logical safe
  inset was rendered. Desktop insets do not validate a physical notch.
- **VERIFIED:** 72 focused native gameplay checks pass in an isolated temporary
  project copy with isolated save data: physical release/seeded queue/RNG,
  cancellations, scoring display, reactions, real-time cycle and all portraits.
  Across all 15 before/after gameplay captures, pixel differences are confined
  to Totolina. No gameplay file or production presenter was edited by this pass.
- **VERIFIED:** starting hashes preserve every asset, import sidecar, scene,
  production/configuration script and unrelated test. Only the five files listed
  below change. The supplied reference is unchanged. Tracked git changes remain
  identical to the user's starting diff. `git diff --check` plus whitespace
  checks for the five untracked task files pass. No commit or tag was created.
- **NOT EXECUTED:** physical Android/iOS testing, automatic device safe-area
  integration, release export, full unrelated gameplay suite, sustained GPU,
  memory or battery profiling. No final gameplay carousel was implemented.
- **REQUIRES USER REVIEW:** final reference likeness, smaller eyes/ears, arm
  silhouette blends, shoulder contour, collection size and whole-phone balance.
  Existing alpha crossfades can show faint double outlines in slow review;
  this pass deliberately preserves their timing and source art.

Historical import caveat: the user's new `assets/worlds/effects/` copies contained
duplicate import UIDs from the old Kitchen effect paths. Godot's import scan
automatically rewrote 14 of those pre-existing sidecars. Only that tool-induced
change was undone after verifying original bytes against the starting hashes;
the user's copies and production paths were preserved. Further editor rescans
could warn/rewrite them while both copies existed; this was outside that
animation task. New Cat/Machine asset
sidecars import successfully. An initial sandboxed process also logged a macOS
certificate-access error; the final authorized headless/graphical runs are clean.

Current asset-deletion audit: the user removed those 14 duplicate global effect
PNGs and their import sidecars. The canonical `assets/worlds/kitchen/effects/`
assets remain, including merge magic and all 13 approved merge-animation images.
Each removed PNG was byte-identical to its retained Kitchen counterpart. Runtime
effect references already use those canonical Kitchen paths; the duplicate-UID
condition described above no longer applies to this removed copy set.

For the four-image arm update, the three replaced press PNGs had stale imported
textures. The four current images were imported in an isolated temporary Godot
project, with identical resource paths and import settings, then their verified
texture caches were refreshed. This avoided rescanning unrelated assets. Source
PNGs and their current sidecars are unchanged. The old extra arm PNG was already
absent; only its orphan import sidecar was removed.

```sh
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --log-file /tmp/machine-lab-headless.log --script res://tests/machine_interaction_lab_validation.gd
/Applications/Godot.app/Contents/MacOS/Godot --path . --log-file /tmp/machine-lab-graphical.log --script res://tests/machine_interaction_lab_validation.gd -- --lab-output=/tmp/machine-lab-review
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . --log-file /tmp/merge-lab-regression.log --script res://tests/merge_effect_lab_validation.gd
git diff --check
```

Check logs as well as exit codes: Godot can return 0 for a script parse error.
The lab tests instantiate only presentation scenes and write captures to the
explicit temporary output directory. The focused gameplay run uses a disposable
project copy with its user directory and test save path redirected under `/tmp`.

## Changes

The original lab added its scene, three implementation scripts, one focused test,
this document, and the original PNG import sidecars. The subsequent layout refinement edits
only the two presentation scripts, this document, and the existing test. The four-image arm update changes those same four lab files and removes one
orphan import sidecar whose source image was already absent. Source PNGs,
production gameplay, current merge effects and old production paths remain intact.
The subsequent shoulder/button alignment pass changes only the two presentation
scripts and this document; all asset files, tests and scenes are preserved.

The reference-matching pass changes exactly five existing, untracked files:

- `scripts/presentation/totolina_operator_presentation.gd`
- `scripts/presentation/machine_drop_presentation.gd`
- `scripts/debug/machine_interaction_lab.gd`
- `tests/machine_interaction_lab_validation.gd`
- `docs/MACHINE_INTERACTION_LAB.md`

The user's 12 tracked modifications and other untracked integration/art files
are preserved. `git diff --stat` does not include these five untracked files;
use a comparison with the task-start snapshot for this pass's own delta.

## Exact new PNG inventory

The percentages below are fully transparent pixels; all non-background PNGs also
contain partially transparent pixels. No files in this inventory were edited.

| Actual path | Dimensions | Alpha range | Fully transparent |
| --- | --- | --- | ---: |
| `assets/characters/totolina/arms/cat_totolina_arm_idle.png` | 384×384 | 0–255 | 75.64% |
| `assets/characters/totolina/arms/cat_totolina_arm_press_01.png` | 384×384 | 0–255 | 84.15% |
| `assets/characters/totolina/arms/cat_totolina_arm_press_02.png` | 384×384 | 0–255 | 84.61% |
| `assets/characters/totolina/arms/cat_totolina_arm_press_03.png` | 384×384 | 0–255 | 78.99% |
| `assets/characters/totolina/body/cat_totolina_body.png` | 768×1024 | 0–255 | 32.61% |
| `assets/characters/totolina/ears/cat_totolina_ear_left.png` | 192×192 | 0–255 | 52.47% |
| `assets/characters/totolina/ears/cat_totolina_ear_right.png` | 192×192 | 0–255 | 53.73% |
| `assets/characters/totolina/eyes/cat_totolina_eyes_blink_01.png` | 328×128 | 0–255 | 62.06% |
| `assets/characters/totolina/eyes/cat_totolina_eyes_blink_02.png` | 328×128 | 0–255 | 61.52% |
| `assets/characters/totolina/eyes/cat_totolina_eyes_blink_03.png` | 328×128 | 0–255 | 61.25% |
| `assets/characters/totolina/eyes/cat_totolina_eyes_excited.png` | 328×128 | 0–255 | 65.8% |
| `assets/characters/totolina/eyes/cat_totolina_eyes_surprised.png` | 328×128 | 0–255 | 65.8% |
| `assets/characters/totolina/mouths/cat_totolina_mouth_excited.png` | 128×128 | 0–255 | 88.06% |
| `assets/characters/totolina/mouths/cat_totolina_mouth_idle.png` | 128×128 | 0–255 | 86.44% |
| `assets/characters/totolina/mouths/cat_totolina_mouth_surprised.png` | 128×128 | 0–255 | 82.05% |
| `assets/worlds/environment/background.png` | 1080×1920 | 255–255 | 0.0% |
| `assets/worlds/environment/machine/button/drop_button_press_01.png` | 1024×384 | 0–255 | 35.81% |
| `assets/worlds/environment/machine/button/drop_button_press_02.png` | 1024×384 | 0–255 | 36.61% |
| `assets/worlds/environment/machine/button/drop_button_press_03.png` | 1024×384 | 0–255 | 39.18% |
| `assets/worlds/environment/machine/feeder/item_drop_nozzle.png` | 512×256 | 0–255 | 53.25% |
| `assets/worlds/environment/machine/feeder/item_feeder_glass.png` | 512×768 | 0–255 | 29.99% |
| `assets/worlds/environment/machine/score/score_screen_active.png` | 512×384 | 0–255 | 30.31% |
| `assets/worlds/environment/machine/score/score_screen_off.png` | 512×384 | 0–255 | 30.31% |
| `assets/worlds/environment/machine/score/score_screen_on.png` | 512×384 | 0–255 | 30.31% |
| `assets/worlds/environment/machine/score/score_separator_colon.png` | 64×128 | 0–255 | 49.5% |
| `assets/worlds/environment/machine/score/score_token_icon.png` | 512×512 | 0–255 | 26.2% |
| `assets/worlds/environment/machine/shutter/drop_shutter_01.png` | 1024×208 | 0–255 | 12.01% |
| `assets/worlds/environment/machine/shutter/drop_shutter_02.png` | 1024×208 | 0–255 | 12.12% |
| `assets/worlds/environment/machine/shutter/drop_shutter_03.png` | 1024×208 | 0–255 | 12.17% |
| `assets/worlds/environment/machine/shutter/drop_shutter_04.png` | 1024×208 | 0–255 | 11.86% |
| `assets/worlds/environment/machine/shutter/drop_shutter_05.png` | 1024×208 | 0–255 | 11.72% |
| `assets/worlds/environment/machine/shutter/drop_shutter_06.png` | 1024×208 | 0–255 | 12.54% |
| `assets/worlds/environment/machine_chamber_background.png` | 859×1831 | 0–255 | 41.03% |
| `assets/worlds/environment/machine_foreground_frame.png` | 859×1831 | 0–255 | 53.65% |
| `assets/worlds/kitchen/ui/collection/collection_mask_left.png` | 128×128 | 0–255 | 43.6% |
| `assets/worlds/kitchen/ui/collection/collection_mystery_bubble.png` | 512×512 | 0–255 | 50.95% |
| `assets/worlds/kitchen/ui/collection/├── collection_mask_right.png` | 128×128 | 0–255 | 47.68% |
