# Kitchen merge effect animation lab

This is a development-only scene in Totolina Merge. It loads no
gameplay scenes or content configuration, has no physics nodes, and does not
access saves, discovery, score, Push, RNG, spawning or navigation. Its approved
animation component is now shared with production; the lab itself is never
instantiated by gameplay.

Read `AGENTS.md` and `docs/ANIMATION_GUIDELINES.md` before changing animation.
The latter remains the source of truth; this document records only lab details.

## Open and run

1. Open `project.godot` at the repository root in Godot 4.7.
2. Open `res://scenes/debug/merge_effect_lab.tscn` in the FileSystem dock.
3. Choose **Run Current Scene** (F6; Fn+F6 on some Macs). F5 runs the production main scene.
4. Select Egg, Milk or Cream, then **Play / Replay**.
5. Use **Stop / Reset**, Speed (0.25×–2×), Loop and the background selector.
6. Drag the lower timeline slider to pause and inspect a blend. Replay starts
   again at time zero. Switching effects returns to clean idle.

Direct command, from the repository:

```sh
/Applications/Godot.app/Contents/MacOS/Godot --path . --scene res://scenes/debug/merge_effect_lab.tscn
```

The scene starts idle, without autoplay. It is absent from production navigation.
`OS.is_debug_build()` rejects release execution before any effect artwork or
animation is created; the scene hides and frees itself. A real release export
has not been executed as part of this work.

## Tuning

Select the scene root in the Inspector before running:

| Parameter | Default | Range |
| --- | ---: | ---: |
| Egg seconds | 0.56 | 0.45–0.60 |
| Milk seconds | 0.66 | 0.55–0.70 |
| Cream seconds | 0.64 | 0.55–0.70 |
| Crossfade seconds | 0.065 | 0.05–0.08 |
| Canvas pixels | 200 | 140–240 |

Restart the current scene after Inspector changes. Duration changes preserve
relative pose timing; the blend value remains seconds at 1×. Canvas pixels
controls the full 512px action canvas in logical project coordinates, independent
of gameplay piece sizing. The actual opaque Cream drawing is narrower.

`scripts/presentation/merge_flavor_effect.gd` builds the named Animation
resources. Adjust its `TRANSITIONS`, `PIVOTS` and `_author_pose()` for pose-level
tuning. The lab script only owns review controls and passes Inspector overrides;
production uses the approved defaults in the shared component.
One AnimationPlayer coordinates Sprite2D alpha, position, scale and rotation.
No AnimationTree, Tween chains, particles, shaders or timer-based scheduling.

## Default timelines at 1×

Every handoff overlaps outgoing and incoming sprites for **65 ms**, with
complementary eased alpha. Each bubble fades in over 65 ms; the final pose
fades out over 90 ms. No textures are swapped on a visible sprite.

| Effect | Bubble → 01 | 01 → 02 | 02 → 03 | 03 → 04 | Final fade | Total |
| --- | --- | --- | --- | --- | --- | --- |
| Egg | .100–.165 | .210–.275 | .320–.385 | — | .470–.560 | .560 s |
| Milk | .110–.175 | .220–.285 | .320–.385 | .420–.485 | .570–.660 | .660 s |
| Cream | .120–.185 | .260–.325 | .390–.455 | — | .550–.640 | .640 s |

- Egg: bubble descends 22 logical pixels above the cross. Shell poses have
  individual pivots to align their different source layouts. Crack 01 descends
  6px; Crack 02/yolk descends 14px; the splash arrives from 8px above the cross.
  Shell scales grow .76→.79 and .82→.84 of the action canvas. Splash grows
  .94→(1.06, .96) and settles to (1, 1) by .455s.
- Milk: bubble starts above/right at (28, −109), arriving at (12, −90).
  All pour frames share the same pivot (375, 478), 2px left/3px down drift and
  rotation curve. This holds the bottle and stream in place during crossfades.
  Final scale reaches (1.03, .98), settling to (1, 1) by .555s.
- Cream: bubble descends 22px. All swirl frames share pivot (305, 480) and the
  same tiny drift/rotation as Milk; the nozzle stays registered while the flow
  becomes a dollop. Final scale reaches (1.03, .98), settling by .535s.
- Bubbles softly scale .49→.57→.55 of the action canvas; no large bounce.
  Bubble rotation eases −1.43°→0°. Egg actions use −0.69°→+0.69°.
  Milk/Cream actions ease +0.46°→0°. Position/scale/alpha use easing;
  falling Egg poses accelerate gently.

Each PNG is a complete drawing. Final squash therefore affects the whole
Milk/Cream drawing, including the bottle/bag, so its amplitude is deliberately
small. This does not add independent articulation or repaint the source art.

## Playback and lifecycle

Speed uses only `AnimationPlayer.speed_scale`; all tracks and native loops
share that clock. Speed changes preserve the current phase. Base timing constants
are not duplicated or manually scaled for the runtime speed slider.

Replay, Stop, switching and backward scrubbing stop the player first, hide every
effect layer, and reset all 13 sprites' alpha, visibility, position, scale and
rotation. Each pose has a fixed texture; hiding the layers clears active pose
state. One completion connection returns playback to clean idle. Looping uses
`Animation.LOOP_LINEAR`, without extra callbacks. Teardown stops the player.
The UI's per-frame status update runs only during playback.

## Asset audit

All 13 exact files below exist and import successfully. Every image is **512×512**,
has alpha values spanning 0–255, and has fully transparent corners. The table
gives the proportion of fully transparent pixels. Partially transparent bubble
interiors are intentional. No source PNG or existing import configuration was
modified. Keep the `.png.import` sidecars for all thirteen approved images.

| File under `assets/worlds/kitchen/effects/merges/` | Fully transparent |
| --- | ---: |
| `egg_bubble_effect.png` | 30.86% |
| `egg_crack_01.png` | 55.63% |
| `egg_crack_02.png` | 55.69% |
| `egg_crack_03.png` | 63.72% |
| `milk_bubble_effect.png` | 39.95% |
| `milk_pour_01.png` | 72.41% |
| `milk_pour_02.png` | 69.30% |
| `milk_pour_03.png` | 62.98% |
| `milk_pour_04.png` | 59.16% |
| `cream_bubble_effect.png` | 32.17% |
| `cream_swirl_01.png` | 85.03% |
| `cream_swirl_02.png` | 82.50% |
| `cream_swirl_03.png` | 81.28% |

Missing assets: **none**. No baked gray, checker, dark or white background boxes
were seen in the source contact sheet or rendered backgrounds. No obvious
rectangular alpha halos were seen at the inspected phone scales.

Source-edge caveats: Egg 02 alpha reaches the bottom row; Milk 01 reaches the
left edge; Milk 02 reaches the top and left edges. These are artwork bounds,
not lab viewport clipping. The lab does not crop or repair them. Milk's cream-white
stream/pool has low contrast against the light neutral preview background.
Crossfading different silhouettes creates brief ghosting/opacity dips, most
noticeable when scrubbing or at 0.25×. Egg shell arrangements and the upright
bubble-to-pour transition differ in the original drawings.

## Validation coverage

`tests/merge_effect_lab_validation.gd` checks all thirteen imported textures and
their alpha, 25 interruption/replay cycles per effect, Stop, switching, scrubbing,
0.25×/1×/2× playback, speed changes, native looping, completion and teardown.
Node/Tween counts must stay constant. The lab test never accesses gameplay saves.

Graphical validation renders exact 390×844, 405×720 and 540×960 viewports, samples
41 times per effect/size, checks control and source-canvas bounds, and captures
all three preview backgrounds. Compare the captured lab images with approved
captures when changing the shared component. Production regression commands
below use a disposable project copy with isolated saves and fail on logged engine
errors as well as nonzero exit status.

Desktop checks do not replace **REQUIRES USER REVIEW** of pacing, pose handoffs
and subtle crossfade ghosting, or **REQUIRES ANDROID DEVICE / REQUIRES MAC/iOS**
checks of readability, touch, safe areas and sustained performance. Release
exports and hardware profiling must be reported separately when executed.

## Approved production integration

After user approval, the authored keyframes/pivots were extracted without timing
changes into `MergeFlavorEffect`. Lab and gameplay instantiate this same small
Node2D/AnimationPlayer component. The lab builds all three effects once; a
production instance creates only the four/five poses it needs. All lab controls,
speed, loop, Stop/Replay and scrubbing remain available. Before/after comparison
of all 150 captured lab PNGs was byte-identical.

Content mapping is `MergeRecipe.effect_animation`:

- Flour ×2 → Cake Mix: `egg_crack`, 0.56 seconds.
- Cake Mix ×2 → Cake Batter: `milk_pour`, 0.66 seconds.
- Sponge Cake ×2 → Frosted Cake: `cream_swirl`, 0.64 seconds.

Production retains the existing 80–140 logical-pixel action-canvas sizing cap.
One uniform visual-root scale fits the swept source canvases to the viewport;
the merge anchor is not shifted. Edge effects can be smaller. The gameplay HUD
stays above the world-space effect. The result remains visible and continues
physics throughout, so a falling result can move away from the original effect
anchor. There is no fake result, physics animation, reveal dependency or delayed
reward. Animation completion only frees the component.

Restart, Play Again, debug Clear Board and scene teardown remove/stop effects.
Game over may let an already-started effect finish cosmetically under the results
overlay; rewards/results were already committed and cannot fire again.

The asset directory contains only the thirteen approved bubble/numbered-pose
images listed above and their import sidecars. `effect_animation` is the only
flavor-presentation field on `MergeRecipe`; the shared component owns its timing
and pose textures. All five non-custom merges retain the existing normal
merge-magic effect.

Integration checks (isolated project/saves):

```sh
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --suite merge-flavor --graphical
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --suite animation-lab --graphical
```

For manual gameplay review, use Debug spawn → Flour / Cake Mix / Sponge Cake →
Spawn Pair; collapse the developer panel while watching. Clear Board between
isolated examples. These are real merges and can grant persistent discoveries.
Normal in-bowl portrait captures use real contacts after positioning source test
fixtures lower in the chamber; production/debug spawning behavior is unchanged.
Physical iPhone readability, touch and sustained GPU performance still require
user testing (REQUIRES MAC/iOS).
