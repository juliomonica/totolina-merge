# Cozy Cat Creations — Gameplay Configuration

## Overview

The centralized configuration source is:

`res://scripts/config/gameplay_configuration.gd`

It is a plain constants script. Gameplay and presentation scripts preload it directly. It is not an autoload, manager, service, plugin, or save-backed system.

Use this file to tune the gameplay chamber, danger zone, magical bowl, ingredient artwork, and existing gameplay HUD layout. Avoid duplicating these values in scenes or feature scripts.

### Value categories

**GAMEPLAY VALUES** affect collision boundaries, spawning, piece collision sizes, danger detection, or game-over timing. Changing them can change balance and requires full gameplay regression testing.

**VISUAL VALUES** affect artwork or UI presentation only. They do not intentionally move physics bodies or change collision shapes.

Do not casually move physics materials, masses, merge timing, scoring, Push behavior, RNG settings, recipe discovery, save paths, or localization into this file. Those systems remain owned by their existing implementation because they are outside this presentation/configuration foundation.

### Safe tuning workflow

1. Change one constant at a time.
2. Run the project and check for parser/runtime errors.
3. Check 405×720, 390×844, and 540×960 portrait layouts.
4. For gameplay values, repeat merge, danger, Push, restart, and spawning regressions.
5. Run `git diff --check` before handing off changes.

## 1. Gameplay Chamber

The chamber rectangle is the source of truth for gameplay dimensions. Walls, floor, spawn placement, collision radii, and safe merge placement derive from the configured chamber and boundaries.

### Chamber dimensions

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `CHAMBER_WIDTH_VIEWPORT_RATIO` | Maximum chamber width as a share of viewport width. | `0.86` | GAMEPLAY | Changing this resizes horizontal play space and every tier collision radius. |
| `CHAMBER_HEIGHT_VIEWPORT_RATIO` | Chamber height as a share of viewport height. | `0.72` | GAMEPLAY | Changes available stacking height and floor position. |
| `CHAMBER_TOP_VIEWPORT_RATIO` | Chamber top position as a share of viewport height. | `0.07` | GAMEPLAY | Moves the entire physics chamber and its chamber-relative gameplay elements, including danger. |
| `CHAMBER_MAX_WIDTH_TO_HEIGHT_RATIO` | Limits chamber width on shorter portrait screens. | `0.67` | GAMEPLAY | Keep this compatible with T8/T9 containment. |

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

### Tier collision sizes

`TIER_RADIUS_RATIOS` contains the physics radius for T1–T9 relative to chamber width.

| Tier | Current ratio | Effect |
| ---: | ---: | --- |
| T1 | `0.0460` | GAMEPLAY |
| T2 | `0.0538` | GAMEPLAY |
| T3 | `0.0630` | GAMEPLAY |
| T4 | `0.0737` | GAMEPLAY |
| T5 | `0.0862` | GAMEPLAY |
| T6 | `0.1009` | GAMEPLAY |
| T7 | `0.1180` | GAMEPLAY |
| T8 | `0.1900` | GAMEPLAY |
| T9 | `0.2600` | GAMEPLAY |

These values change collision circles and merge placement clearance. They are not artwork scaling controls. After changing them, test the complete merge ladder, wall/floor containment, Push, danger, and crowded merges.

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

Ingredient artwork configuration does not change collision circles. Physics size is controlled separately by `TIER_RADIUS_RATIOS`.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `INGREDIENT_GLOBAL_VISUAL_SCALE` | Multiplies all in-bowl ingredient artwork sizes. | `1.0` | VISUAL | Preview sizing and floor support calculations follow this value. |
| `INGREDIENT_VISUAL_OFFSET_PIXELS` | Base local offset of every ingredient visual. | `Vector2.ZERO` | VISUAL | The offset rotates with the piece. Use small values. |
| `INGREDIENT_PREVIEW_SCALE` | Additional scale for the NEXT preview only. | `1.0` | VISUAL | Keep near `1.0` so preview and spawned artwork remain comparable. |
| `INGREDIENT_VISUAL_SIDE_INSET_VIEWPORT_RATIO` | Left/right visual containment inset. | `0.10` | VISUAL | Keeps artwork inside the visible bowl walls without moving physics bodies. |
| `INGREDIENT_FLOOR_CONTACT_CHAMBER_WIDTH_RATIO` | Visual resting line above the physical floor. | `0.033` | VISUAL | Increase to lift grounded artwork; decrease to lower it. |
| `INGREDIENT_ROTATED_SUPPORT_REDUCTION` | Rotation correction used by floor grounding. | `0.04` | VISUAL | Tune with rotated wide/tall artwork. |
| `INGREDIENT_FLOOR_BODY_TOLERANCE_PIXELS` | Distance within which a body is considered physically floor-supported for visual grounding. | `8.0` | VISUAL | Increasing applies grounding correction to pieces farther from the floor. |

### Per-tier artwork fitting

`INGREDIENT_TIER_DIAMETER_SCALES` sets artwork diameter relative to the tier's physics radius.

| Tier | Current visual scale | Effect |
| ---: | ---: | --- |
| T1 | `1.46` | VISUAL |
| T2 | `1.90` | VISUAL |
| T3 | `1.82` | VISUAL |
| T4 | `1.78` | VISUAL |
| T5 | `1.74` | VISUAL |
| T6 | `1.60` | VISUAL |
| T7 | `1.88` | VISUAL |
| T8 | `1.66` | VISUAL |
| T9 | `1.62` | VISUAL |

These values fit transparent artwork bounds, not just the visible dessert shape. Test rotation, floor contact, side containment, NEXT preview matching, and T8/T9 readability after changes.

## 5. UI Presentation

These values control existing gameplay UI only. They do not create new UI systems.

| Name | Purpose | Current example | Effect | Safe tuning notes |
| --- | --- | ---: | --- | --- |
| `UI_EDGE_MARGIN_PIXELS` | Shared safe-area inset added around gameplay HUD and result overlay. | `16.0` | VISUAL | Do not reduce without notch/Dynamic Island testing. |
| `HUD_HEIGHT_PIXELS` | Top HUD panel height. | `88.0` | VISUAL | Check NEXT, Pulse, and Score at narrow widths. |
| `CONTROLS_HEIGHT_PIXELS` | Bottom Push/Restart controls height. | `52.0` | VISUAL | Preserve comfortable touch targets. |
| `RECIPE_PROGRESS_HEIGHT_PIXELS` | Recipe progress strip height. | `46.0` | VISUAL | Larger values reduce free space above controls. |
| `RECIPE_PROGRESS_CONTROLS_GAP_PIXELS` | Gap between recipe strip and controls. | `6.0` | VISUAL | Keep enough separation for readability. |
| `RECIPE_PROGRESS_SLOT_MINIMUM_SIZE` | Minimum size of each T1–T9 progress slot. | `Vector2(42, 34)` | VISUAL | All nine slots must still fit at 390-pixel width. |
| `RECIPE_PROGRESS_ARTWORK_INSET_PIXELS` | Padding inside every progress slot. | `3.0` | VISUAL | Large values make tier artwork too small. |
| `RECIPE_PROGRESS_UNKNOWN_FONT_SIZE` | Font size of the locked `?` marker. | `15` | VISUAL | Check English, Spanish, and Chinese layouts. |
| `TOLINA_SAFE_SIZE` | Tolina's gameplay HUD width and height. | `Vector2(90, 96)` | VISUAL | Preserve aspect/readability and HUD separation. |
| `TOLINA_HUD_GAP_PIXELS` | Horizontal gap between Tolina and the HUD panel. | `10.0` | VISUAL | Verify narrow screens after increasing. |
| `RESTART_BUTTON_MINIMUM_WIDTH_PIXELS` | Minimum width of the hold-to-restart button. | `156.0` | VISUAL | Do not reduce touch readability. |

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
- T1+T1 through T8+T8 merge normally.
- T9 remains non-merging.
- Score and Push charge remain unchanged for the same merge sequence.
- Danger starts, clears, and reaches game over at the configured threshold/timing.
- Bowl and ingredient visuals remain aligned without changing physics bodies.
- NEXT preview matches the next spawned tier.
- Recipe progress and Recipe Collection still reflect the existing discovery save.
- Hold Restart and Play Again reset only the current run as before.
- No localization, discovery save, export, or mobile input configuration changed.
