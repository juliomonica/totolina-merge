# Cozy Cat Creations — Gameplay Configuration

## Overview

The centralized configuration source is:

`res://scripts/config/gameplay_configuration.gd`

It is a plain constants script. Gameplay and presentation scripts preload it directly. It is not an autoload, manager, service, plugin, or save-backed system.

Use this file to tune the gameplay chamber, danger zone, magical bowl, ingredient artwork, and existing gameplay HUD layout. Avoid duplicating these values in scenes or feature scripts.

Creation size curves are world/theme data in
`res://config/worlds/kitchen/kitchen_content.tres`, using the reusable
`WorldContentConfiguration` resource and its `CreationDefinition` subresources.
Edit the world base radius and per-creation growth below, then run the game;
no separate collider or sprite edits are needed.

### Value categories

**GAMEPLAY VALUES** affect collision boundaries, spawning, piece collision sizes, danger detection, or game-over timing. Changing them can change balance and requires full gameplay regression testing.

**VISUAL VALUES** affect artwork or UI presentation only. They do not intentionally move physics bodies or change collision shapes.

Do not casually move physics materials, masses, merge timing, scoring, Push behavior, RNG settings, recipe discovery, save paths, or localization into this file. Those systems remain owned by their existing implementation because they are outside this presentation/configuration foundation.

### Safe tuning workflow

1. Change one constant or world sizing field at a time.
2. Run the project and check for parser/runtime errors.
3. Check 405×720, 390×844, and 540×960 portrait layouts.
4. For gameplay values, repeat merge, danger, Push, restart, and spawning regressions.
5. Run `git diff --check` before handing off changes.

## 1. Gameplay Chamber

The chamber rectangle is the source of truth for gameplay dimensions. Walls, floor, spawn placement, collision radii, and safe merge placement derive from the configured chamber and boundaries.

### Chamber dimensions

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `CHAMBER_WIDTH_VIEWPORT_RATIO` | Maximum chamber width as a share of viewport width. | `0.86` | GAMEPLAY | Changing this resizes horizontal play space and every creation collision radius. |
| `CHAMBER_HEIGHT_VIEWPORT_RATIO` | Chamber height as a share of viewport height. | `0.72` | GAMEPLAY | Changes available stacking height and floor position. |
| `CHAMBER_TOP_VIEWPORT_RATIO` | Chamber top position as a share of viewport height. | `0.07` | GAMEPLAY | Moves the entire physics chamber and its chamber-relative gameplay elements, including danger. |
| `CHAMBER_MAX_WIDTH_TO_HEIGHT_RATIO` | Limits chamber width on shorter portrait screens. | `0.67` | GAMEPLAY | Keep this compatible with Decorated Cake and Fancy Cake containment. |

The effective width is the smaller of:

```text
viewport width × CHAMBER_WIDTH_VIEWPORT_RATIO
chamber height × CHAMBER_MAX_WIDTH_TO_HEIGHT_RATIO
```

### Screen coordinates and chamber coordinates

Screen coordinates describe the device's logical viewport. They are used only to create the outer `_chamber_rect` and to place safe-area UI. The viewport can become taller or wider under Godot's `aspect="expand"` setting.

Chamber coordinates describe gameplay positions inside `_chamber_rect`:

```text
chamber X = chamber left + chamber width × horizontal chamber ratio
chamber Y = chamber top  + chamber height × vertical chamber ratio
```

Normalized chamber ratios are device independent: `0.0` is the chamber's top or left edge and `1.0` is its bottom or right edge. Walls, floor, spawn height, collision radii, and the danger threshold derive from these chamber coordinates. Their screen pixels change responsively, but their relationship to the chamber does not.

Pixel values such as label offsets and UI margins are presentation adjustments, not chamber gameplay coordinates. The magical bowl PNG is also presentation: its top sits a chamber-scaled gap below the shared danger threshold and its floor anchor follows the chamber floor, but the artwork never becomes a physics boundary.

### Physics boundaries

Boundary positions use normalized chamber coordinates: `0.0` is the chamber's top/left and `1.0` is its bottom/right.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `WALL_THICKNESS_MIN_PIXELS` | Minimum collision thickness for walls and floor. | `8.0` | GAMEPLAY | Do not reduce without tunneling tests. |
| `WALL_THICKNESS_VIEWPORT_WIDTH_RATIO` | Responsive collision thickness based on viewport width. | `0.018` | GAMEPLAY | The larger of this calculation and the minimum is used. |
| `LEFT_WALL_X_CHAMBER_RATIO` | Left wall X position within the chamber. | `0.0` | GAMEPLAY | Moving inward narrows the playable width. |
| `RIGHT_WALL_X_CHAMBER_RATIO` | Right wall X position within the chamber. | `1.0` | GAMEPLAY | Keep greater than the left wall value. |
| `SIDE_WALL_CENTER_Y_CHAMBER_RATIO` | Vertical center shared by the side-wall shapes. | `0.5` | GAMEPLAY | Normally leave centered. |
| `FLOOR_CENTER_X_CHAMBER_RATIO` | Horizontal center of the floor body. | `0.5` | GAMEPLAY | Normally leave centered. |
| `FLOOR_Y_CHAMBER_RATIO` | Floor body's Y position within the chamber. | `1.0` | GAMEPLAY | Changes the physical resting height. Bowl presentation follows the resulting physical floor. |

### Spawn area

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `SPAWN_HEIGHT_CHAMBER_RATIO` | Additional spawn height measured down from the chamber top. | `0.0` | GAMEPLAY | The piece radius and wall clearance are added automatically. |
| `SPAWN_HORIZONTAL_INSET_PIXELS` | Extra left/right inset inside the physical walls. | `0.0` | GAMEPLAY | Increase to keep drops farther from walls. |
| `SPAWN_WALL_CLEARANCE_MULTIPLIER` | Portion of wall thickness reserved between spawn centers and wall centers. | `0.5` | GAMEPLAY | `0.5` aligns limits with the inner wall surface. |

### Sequential creation sizes

These **GAMEPLAY VALUES** live in `config/worlds/kitchen/kitchen_content.tres`:

| Field | Owner | Purpose | Example |
| --- | --- | --- | --- |
| `base_radius_ratio` | WorldContentConfiguration, final `[resource]` section | Physical radius of size order 1 as a fraction of chamber width. | `0.046` |
| `size_order` | Each CreationDefinition subresource | Unique physical size sequence, contiguous from 1. | Flour = `2` |
| `size_growth_percent` | Each CreationDefinition subresource | Percentage increase over the immediately preceding size order. | Flour = `15.0` |

`progression_rank` still controls gameplay/scoring/progression semantics;
it does **not** control physical size. `collection_order` still controls the
collection display, independently of `size_order`. The strip and collection
always keep all 9 canonical slots; discovery only changes locked/artwork state.

Growth is **cumulative**, not calculated independently from the base:
order 1 uses `base_radius_ratio`; each later order multiplies the preceding
radius by `1 + this_creation.size_growth_percent / 100`.
For example, changing Flour from 15% to 20% leaves Wheat unchanged,
but multiplies Flour and every subsequent radius by `1.20 / 1.15`.

Designer workflow: set the world's base radius, edit one creation's growth
percentage, then rerun. Do not edit collision or sprite sizes separately.
There is only this sequential curve; no rank-size bands or independent radius
overrides. Resource array order does not define size. No result table is
hardcoded or cached. Mass and artwork calibration remain unchanged.

| Size / collection order / rank | ID | Creation | Growth % | Effective radius ratio |
| ---: | --- | --- | ---: | ---: |
| 1 | `wheat` | Wheat | 0 | 0.046000000 |
| 2 | `flour` | Flour | 15 | 0.052900000 |
| 3 | `cake_mix` | Cake Mix | 15 | 0.060835000 |
| 4 | `cake_batter` | Cake Batter | 15 | 0.069960250 |
| 5 | `sponge_cake` | Sponge Cake | 15 | 0.080454287 |
| 6 | `frosted_cake` | Frosted Cake | 15 | 0.092522431 |
| 7 | `layer_cake` | Layer Cake | 20 | 0.111026917 |
| 8 | `decorated_cake` | Decorated Cake | 25 | 0.138783646 |
| 9 | `fancy_cake` | Fancy Cake | 30 | 0.180418740 |

These are the current nine-stage ratios, not hardcoded runtime values.
Surviving growth values and base 0.046 were preserved exactly during the
nine-stage simplification; removed steps are not compensated for.

Validation requires unique contiguous orders, including order 1, with 0%
growth for order 1. Growth must be finite/nonnegative, and the base must be
positive/finite. Decimal percentages and single-creation worlds are supported.
Generic worlds may use 0% later growth; Kitchen's strict validation
(`sizing_errors(true)` and the focused sizing tests) rejects equal-size steps.
Keep all Kitchen growth percentages after order 1 positive.

Malformed sequences warn once per issue per resource and use only the valid
base radius (or `0.046` when the base is invalid), rather than guessing which
duplicate/missing creation should drive the curve. Fix those warnings before
playtesting. Nonfinite cumulative overflow also falls back to the base.
Very large finite curves are not automatically balanced to fit the chamber.

`effective_radius_ratio(definition) × chamber width` drives drop clamping,
spawn height, safe merge placement and the piece's unique `CircleShape2D.radius`.
That same pixel radius enters the existing visual fitting:
`sprite scale = radius × visual_diameter_scale × global_visual_scale / texture_extent`.
Keep `visual_diameter_scale = 2.18` and global visual scale `1.0` for the current
bubble art. Physics/body/collider node transforms and centering do not change.
The radius is not derived from the 512×512 PNG. Preview sizing uses the same
radius with its existing UI cap; collection/result icons remain UI-fitted.

Changing the curve intentionally changes physical sizes and matching artwork.
Rerun all eight physical recipes, wall/floor containment, Push, danger
and crowded merges. Existing pieces do not resize mid-run; edit the
world resource and rerun to compare curves.

### Board spawning (gameplay tuning)

`WorldContentConfiguration.spawn_stages` in
`config/worlds/kitchen/kitchen_content.tres` is the only spawn-weight source.
Each native `SpawnStage` resource has `unlock_creation_id` (empty for the opening
stage, otherwise a successful merge result) and `weights` (semantic creation IDs
to relative weights; absent IDs cannot spawn). Stages are ordered by unlock
progression; weights use their serialized entry order for deterministic selection.

| Run stage | Unlock in this run | Wheat | Flour | Cake Mix |
| --- | --- | ---: | ---: | ---: |
| 1 | New run | 100 | 0 | 0 |
| 2 | Merge-create Flour | 75 | 25 | 0 |
| 3 | Merge-create Cake Mix | 60 | 30 | 10 |

These are **GAMEPLAY** values. Change the stage subresources to tune the pools;
do not add independent weights to CreationDefinition. All six later creations
remain merge-only. Successful result creation advances the run's stage once,
without waiting for settling, and never downgrades it. Preview, effects, drops
and permanent discovery loads do not unlock stages.

The controlled DROP and buffered NEXT remain untouched on unlock. Only the next
fresh selection uses the new weights, with exactly one draw from the existing
seeded RNG (including Wheat-only). Same seed + same run actions gives the same
sequence. Restart, Play Again and a new gameplay scene reset to stage 1 before
selecting the two opening pieces; saved collection progress remains separate.
No adaptive bias, anti-streak state, crafted queue or second RNG remains.

## 2. Danger Zone

Gameplay danger and danger presentation share one runtime coordinate: `_danger_threshold_y`.

The gameplay piece check, the visible danger line, and the warning label all use that exact value. There is no separate viewport-relative or bowl-relative visual estimate. The threshold is calculated inside `_chamber_rect`, so its relationship to the gameplay chamber remains constant across aspect ratios.

### Danger gameplay values

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `DANGER_HEIGHT_CHAMBER_RATIO` | Shared gameplay and visual danger height inside the chamber. `0.0` is chamber top; `1.0` is chamber bottom. | `0.3888888889` | GAMEPLAY + VISUAL | Smaller moves the threshold, line, and warning toward chamber top; larger moves all three toward the floor. |
| `DANGER_GRACE_SECONDS` | Continuous danger time required for game over. | `3.0` | GAMEPLAY | Changes recovery time. |
| `DANGER_VERTICAL_SPEED_THRESHOLD` | Maximum vertical speed for a supported piece to count as dangerous. | `10.0` | GAMEPLAY | Prevents transient falling pieces from starting danger. |

The shared runtime coordinate is:

```text
_danger_threshold_y = chamber top
                    + chamber height × DANGER_HEIGHT_CHAMBER_RATIO
```

The current `0.3888888889` value preserves the earlier gameplay balance:

```text
(0.35 previous viewport ratio - 0.07 chamber top) / 0.72 chamber height
= 0.3888888889 chamber ratio
```

### Danger presentation values

The line is drawn at `_danger_threshold_y`. The label rectangle is anchored to the same value, with configurable offsets for readability. These offsets move only the label; they never create a second danger-line coordinate.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `DANGER_LINE_INACTIVE_COLOR` | Line color before danger is active. | `ffb020` | VISUAL | Does not affect detection. |
| `DANGER_LINE_ACTIVE_COLOR` | Line color while danger is active. | `ff3b30` | VISUAL | Keep high contrast over the kitchen background. |
| `DANGER_LINE_WIDTH` | Drawn line width in pixels. | `3.0` | VISUAL | Large values can obscure pieces near the threshold. |
| `DANGER_LABEL_TOP_OFFSET` | Label top relative to `_danger_threshold_y`. | `-42.0` | VISUAL | More negative moves only the label upward. |
| `DANGER_LABEL_BOTTOM_OFFSET` | Label bottom relative to `_danger_threshold_y`. | `2.0` | VISUAL | Adjust with the top offset to preserve label height. |
| `DANGER_LABEL_SCALE` | Additional Label node scale. | `Vector2.ONE` | VISUAL | Prefer font-size changes before nonuniform scaling. |
| `DANGER_TEXT_FONT_SIZE` | Warning font size. | `30` | VISUAL | Verify Chinese glyph readability and narrow screens. |
| `DANGER_TEXT_COLOR` | Warning text color. | `ff3b30` | VISUAL | Preserve strong contrast. |
| `DANGER_TEXT_OUTLINE_COLOR` | Warning outline color. | `230408` | VISUAL | Dark outline improves readability over ingredients. |
| `DANGER_TEXT_OUTLINE_SIZE` | Warning outline thickness. | `6` | VISUAL | Very large values can crowd the label rect. |
| `DANGER_TEXT_SHADOW_COLOR` | Warning shadow color and opacity. | black at `0.8` alpha | VISUAL | Keep sufficient contrast without obscuring the text. |
| `DANGER_TEXT_SHADOW_OFFSET` | Warning shadow X/Y displacement. | `Vector2(2, 3)` | VISUAL | Positive Y moves the shadow downward. |
| `DANGER_TEXT_SHADOW_OUTLINE_SIZE` | Extra shadow outline thickness. | `2` | VISUAL | Use small values. |

## 3. Container/Bowl Visuals

All bowl constants are visual-only. They never change `StaticBody2D` positions or collision shapes.

### Automatic chamber-matching mode

Set:

```gdscript
const BOWL_MATCH_CHAMBER_SIZE := true
```

The bowl texture is then fitted to the chamber size multiplied by `BOWL_CHAMBER_MATCH_SCALE`.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `BOWL_MATCH_CHAMBER_SIZE` | Selects chamber-matching mode. | `false` | VISUAL | Current default remains the tuned responsive/manual presentation. |
| `BOWL_CHAMBER_MATCH_SCALE` | Width/height multiplier in chamber-matching mode. | `Vector2.ONE` | VISUAL | Preserve positive values and test the full bowl silhouette. |

### Responsive/manual mode

When `BOWL_MATCH_CHAMBER_SIZE` is `false`, the existing responsive calculation remains active. Manual size components greater than zero override the corresponding responsive dimension.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `BOWL_RESPONSIVE_WIDTH_VIEWPORT_RATIO` | Responsive bowl width relative to viewport width. | `0.98` | VISUAL | Increasing can crop the side walls. |
| `DANGER_TO_BOWL_TOP_GAP_CHAMBER_WIDTH_RATIO` | Fixed visual gap from the shared danger threshold down to the bowl texture's top. | `0.035` | VISUAL | Increase to place the bowl lower while keeping danger gameplay unchanged. |
| `BOWL_MANUAL_SIZE_PIXELS` | Optional explicit width and height. Zero components keep responsive dimensions. | `Vector2.ZERO` | VISUAL | Absolute pixels are less portable across phones. |
| `BOWL_MANUAL_SCALE` | Post-scale applied in responsive/manual mode. | `Vector2.ONE` | VISUAL | Nonuniform values can distort artwork. |
| `BOWL_MANUAL_OFFSET_PIXELS` | Final X/Y bowl translation in responsive/manual mode. | `Vector2.ZERO` | VISUAL | Positive X moves right; positive Y moves down. |

### Floor alignment

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `BOWL_FLOOR_TEXTURE_Y_RATIO` | Selects the texture-height position aligned to the physics floor. | `0.80` | VISUAL | Because the bowl is one sprite, this can alter its scale or position. Tune in small increments such as `0.005`. |
| `BOWL_VISUAL_FLOOR_OFFSET_PIXELS` | Moves the bowl's visual floor anchor relative to the physics floor. | `0.0` | VISUAL | Negative lifts the bowl anchor; positive lowers it. Does not move pieces or collisions. |

`BOWL_FLOOR_TEXTURE_Y_RATIO` cannot move only the glowing floor while keeping both the complete bowl size and rim fixed. The floor is part of the single bowl PNG. Use the manual size/offset controls for composition, or separate the floor artwork in a dedicated future visual task.

In the default responsive mode, the bowl's vertical size is solved from two chamber-owned anchors:

```text
bowl top target = _danger_threshold_y
                + chamber width × DANGER_TO_BOWL_TOP_GAP_CHAMBER_WIDTH_RATIO
bowl floor target = chamber floor + BOWL_VISUAL_FLOOR_OFFSET_PIXELS
```

This avoids aspect-dependent vertical clamps that could move the bowl rim away from the danger line. Manual bowl height or scale overrides can intentionally replace this automatic relationship and therefore require all target layouts to be rechecked.

## 4. Ingredient Visual Scaling

The sequential creation-size configuration drives collision and artwork size together.
The separate visual-only values below are artwork calibration, not the size
curve; leave them at the calibrated defaults when tuning world percentages.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `INGREDIENT_GLOBAL_VISUAL_SCALE` | Multiplies all in-bowl ingredient artwork sizes. | `1.0` | VISUAL | Preview sizing follows this value. |
| `INGREDIENT_VISUAL_OFFSET_PIXELS` | Base local offset of every ingredient visual. | `Vector2.ZERO` | VISUAL | Keep this at zero for centered bubble artwork. |
| `INGREDIENT_PREVIEW_SCALE` | Additional scale for the NEXT preview only. | `1.0` | VISUAL | Keep near `1.0` so preview and spawned artwork remain comparable. |

Standardized circular bubble artwork stays centered on its physics body.
The presentation layer does not translate visuals independently for floor
contact or side containment; containment therefore follows the actual
CircleShape2D rather than a separate visual correction.

### Per-creation artwork fitting

Every Kitchen definition currently uses `visual_diameter_scale = 2.18`.
The final 512×512 artwork places a 480×480 visible bubble inside a
16-pixel transparent margin. The resulting visible bubble diameter is
approximately `2.18 × 480 / 512 = 2.044` times the collision radius,
leaving the CircleShape2D roughly 2.1% inside the visible outer edge.
Change this property per creation only if future art uses different
transparent-bound fitting.

### Physical recipes and optional merge flavor

The nine entries in the sizing table also form the board ladder: two identical
pieces create the next entry, with Fancy Cake final. All eight recipes use
actual contacts, pending-source protection and the existing 0.45-second
cooldown. Safe placement, inherited motion, controlled expansion and guarded
neighbour waking are preserved. There is no mixed-recipe execution path.

Optional visual fields live on each `MergeRecipe`:

| Field | Purpose | Current value |
| --- | --- | --- |
| `effect_animation` | Approved timeline name, or empty for ordinary merge magic. | `egg_crack`, `milk_pour`, `cream_swirl`. Unknown names also use normal magic. |

Only Flour ×2 → Cake Mix (egg), Cake Mix ×2 → Cake Batter (milk), and
Sponge Cake ×2 → Frosted Cake (cream) configure this field. Textures stay in
`assets/worlds/kitchen/effects/merges/`; they have no board identity, collision,
spawn probability or discovery slot.

The physical result and rank² × 2 score / +12 Push reward occur immediately,
once. The approved shared AnimationPlayer component in
`scripts/presentation/merge_flavor_effect.gd` plays Egg for 0.56s, Milk for
0.66s and Cream for 0.64s, with 65ms crossfades. The lab uses the exact same
implementation. Uniform visual-root fitting keeps the source canvases inside
the viewport and the anchor at the actual safe merge position; the existing HUD
CanvasLayer remains above it. The real result stays visible and moves normally
throughout; no fake result, collider or physics transform is animated. Completion
only frees the overlay. Restart/scene teardown frees/stops the component; game
over may let it finish cosmetically without further gameplay callbacks.

The existing semantic discovery format remains unchanged. Current content
filters obsolete IDs on load; surviving discoveries remain in the nine fixed
collection slots. The next normal save writes valid IDs without deleting
unrelated settings.

## 5. UI Presentation

These values control existing gameplay UI only. They do not create new UI systems.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `UI_EDGE_MARGIN_PIXELS` | Shared safe-area inset added around gameplay HUD and result overlay. | `16.0` | VISUAL | Do not reduce without notch/Dynamic Island testing. |
| `HUD_HEIGHT_PIXELS` | Top HUD panel height. | `88.0` | VISUAL | Check NEXT, Pulse, and Score at narrow widths. |
| `CONTROLS_HEIGHT_PIXELS` | Bottom Push/Restart controls height. | `52.0` | VISUAL | Preserve comfortable touch targets. |
| `RECIPE_PROGRESS_HEIGHT_PIXELS` | Recipe progress strip height. | `46.0` | VISUAL | Larger values reduce free space above controls. |
| `RECIPE_PROGRESS_CONTROLS_GAP_PIXELS` | Gap between recipe strip and controls. | `6.0` | VISUAL | Keep enough separation for readability. |
| `RECIPE_PROGRESS_SLOT_MINIMUM_SIZE` | Minimum size of each creation slot. | `Vector2(24, 34)` | VISUAL | All nine slots must still fit at 390-pixel width. |
| `RECIPE_PROGRESS_ARTWORK_INSET_PIXELS` | Padding inside every progress slot. | `2.0` | VISUAL | Large values make creation artwork too small. |
| `RECIPE_PROGRESS_UNKNOWN_FONT_SIZE` | Font size of the locked `?` marker. | `12` | VISUAL | Check English, Spanish, and Chinese layouts. |
| `TOLINA_SAFE_SIZE` | Tolina's gameplay HUD width and height. | `Vector2(90, 96)` | VISUAL | Preserve aspect/readability and HUD separation. |
| `TOLINA_HUD_GAP_PIXELS` | Horizontal gap between Tolina and the HUD panel. | `10.0` | VISUAL | Verify narrow screens after increasing. |
| `RESTART_BUTTON_MINIMUM_WIDTH_PIXELS` | Minimum width of the hold-to-restart button. | `156.0` | VISUAL | Do not reduce touch readability. |
| `RESTART_HOLD_FEEDBACK_SIZE_PIXELS` | Width and height of the temporary hold instruction above the controls. | `Vector2(190, 48)` | VISUAL | Keep wide enough for localized text without covering the recipe strip. |
| `RESTART_HOLD_FEEDBACK_GAP_PIXELS` | Gap between the hold feedback and recipe strip. | `8.0` | VISUAL | Increase to move feedback farther from the player's finger. |

## 6. Mobile Layout

Gameplay safe-area insets continue to come from Godot's platform-neutral display safe-area API. The configuration adds `UI_EDGE_MARGIN_PIXELS` inside those system-provided insets.

The current layout order is:

```text
safe area
Tolina + NEXT / Pulse / Score HUD
danger warning and shared gameplay/visual threshold line
magical bowl and pieces
recipe progress strip
Push Left / Hold Restart / Push Right
safe area
```

Always test:

- 405×720
- 390×844
- 540×960
- iPhone notch/Dynamic Island safe areas on a real device
- Android gesture/navigation insets on a real device

Confirm that the complete bowl silhouette remains visible, the danger line matches the gameplay threshold, the recipe strip does not cover grounded pieces, and all three bottom controls remain reachable.

## Verification checklist after configuration edits

- Project parses and launches without red errors.
- Chamber dimensions and boundary positions match the intended values.
- Desktop click and mobile touch spawn inside the walls.
- All eight same-item recipes resolve on contact; Fancy Cake is final.
- Higher-result-rank arbitration, reservation and sequential crafting hold under competing contacts.
- Invalid creation pairs remain non-merging.
- Score and Push charge remain unchanged for the same merge sequence.
- Danger starts, clears, and reaches game over at the configured threshold/timing.
- Bowl and ingredient visuals remain aligned without changing physics bodies.
- DROP matches the controlled piece; NEXT matches the buffered Wheat/Flour/Cake Mix selection.
- Recipe progress and Recipe Collection still reflect the existing discovery save.
- Hold Restart and Play Again reset only the current run as before.
- Localization imports, versioned discovery saves, export settings, and mobile input remain valid.
