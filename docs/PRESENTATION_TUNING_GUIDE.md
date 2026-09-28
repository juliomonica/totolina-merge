# Presentation tuning in Godot

Open the existing `project.godot` in Godot 4.7. Do not change physics to adjust
artwork. These scenes use the current nine-creation game and existing assets.

## Open, change one thing, run

1. Open `res://scenes/prototype/physics_sandbox.tscn` for gameplay.
   Its **KitchenMachine** instance links to the production presentation.
2. For the editable machinery, open
   `res://scenes/presentation/machine_drop_presentation.tscn`.
   Expand **TopMachine**. This shared scene is used by production and the lab.
   Double-click the scene icon beside **Totolina** to open its source scene.
3. Select a Sprite2D/Node2D and use **Inspector → Transform → Position / Scale /
   Rotation**, or the 2D editor move/scale tools. Keep X/Y scales equal to avoid
   stretching. Use **Ordering → Z Index** for layering.
4. Save. On macOS use **Command + R / Run Current Scene** (toolbar).
   Run `physics_sandbox.tscn` to check real gameplay, or
   `res://scenes/debug/machine_interaction_lab.tscn` for interactive animation
   controls. The machine source scene alone displays the lab composition but
   does not provide the lab's transport buttons.
5. Check 390×844, 405×720 and 540×960 before accepting a change.

Edit the source scene for shared changes. “Editable Children” on an instance
creates overrides just for that instance; use it deliberately, not accidentally.
Do not edit the **Remote** tree expecting changes to be saved.

## Actual nodes and ownership

Paths below are relative to the named scene root. “Game” means production layout;
“Anim” means animation/pose design. The user can edit either.

| Visual element | Scene / node | Safe properties | Owner |
| --- | --- | --- | --- |
| Totolina overall | `machine_drop_presentation.tscn → TopMachine/Totolina` | Position, uniform Scale, Ordering | User / Game |
| Body | `totolina_operator.tscn → Visual/cat_totolina_body` | Position, Scale (check all overlays) | User / Anim |
| Arm base | `totolina_operator.tscn → Visual/Arms` | Position, Scale | User / Anim |
| Individual arm poses | `Visual/Arms/cat_totolina_arm_…` | Transform; Sprite Offset is its source pivot | User / Anim |
| Eyes, all expressions | `totolina_operator.tscn → Visual/Eyes` | Position, uniform Scale | User / Anim |
| Ears | `totolina_operator.tscn → Visual/cat_totolina_ear_left`, `…ear_right` | Position, Scale, Rotation | User / Anim |
| Button machine | `machine_drop_presentation.tscn → TopMachine/Button` | Position, Scale | User / Game |
| Feeder glass | `TopMachine/FeederGlass` | Position, Scale | User / Game |
| Previews | `TopMachine/Current`, `Next`, `Incoming` | Position, Scale; keep Incoming aligned with Next | User / Game |
| Shutter | `TopMachine/Shutter` | Position, Scale, Ordering | User / Game |
| Nozzle | `TopMachine/Nozzle` | Rest Position / Scale / Rotation; action X animates toward input | User / Game |
| Score housing | `TopMachine/SampleScore` | Position, Scale | User / Game |
| Score token / colon | `TopMachine/SampleScore/Token`, `Colon` | Position, Scale | User / Game |
| Score digits | `TopMachine/SampleScore/ScoreLabel` | Control offsets/size, Theme Overrides font size | User / Game |
| NEXT / DROP / Pulse labels | `TopMachine/NextLabel`, `CurrentLabel`, `PulseLabel` | Control offsets/size, font overrides | User / Game |
| Collection masks | `collection_masks.tscn → LeftMask`, `RightMask` | Control anchors/offsets | User / Game |
| Mask artwork | `LeftMask/Fit/Artwork`, `RightMask/Fit/Artwork` | Sprite Position/Scale/Offset | User / Game |
| Collection icon size/spacing | `kitchen_machine_presentation.tscn` root | Collection Layout group | User / Game |
| Floor mapping / rail width | Same production root | Chamber Artwork group | User / Game |
| Arm, button, shutter, feeder, reaction timing | `machine_drop_presentation.tscn → AnimationPlayer` | Timeline keys/curves (see restrictions below) | User / Anim |
| Blink timing | `totolina_operator.tscn → IdlePlayer` | Blink timeline keys | User / Anim |

The old runtime-generated transform constants are no longer the layout source.
Rest transforms are read from scenes once; animation applies relative motion and
reset restores those authored values, not hardcoded positions.

## Controls and calculated layout

For **Control** nodes use **Layout → Anchors / Offsets** and size settings.
Do not use Node2D-style scaling as the primary responsive UI layout mechanism.
The masks use a left-edge anchor and a right-edge anchor: change left offsets
together, or right offsets together, to move each edge without resizing it.
Defaults are −4 and +4 logical pixels. Their child **Fit** nodes adapt to strip
height; edit **Artwork**, not **Fit**, for additional art scaling. All mask
Controls intentionally have **Mouse Filter = Ignore** so scrolling works.

On `kitchen_machine_presentation.tscn`, select the root:

| Inspector group / property | Default | Meaning |
| --- | ---: | --- |
| Chamber Artwork / Floor Edge Texture Y | 1595 | Source row aligned with the unchanged physics floor surface |
| Chamber Artwork / Foreground Side Width | 56 | Source-pixel width kept in front of bodies at lower edges |
| Collection Layout / Collection Icon Scale | 0.13 | Canvas scale at 500-wide design size |
| Collection Layout / Collection Pitch | 100 | Icon center-to-center spacing at design size |
| Collection Layout / Collection End Padding | 56 | Room for first/last icon to clear masks |

No `@tool` script rebuilds the world in the editor. Run gameplay to preview
calculated settings. The responsive **Machine** root, frame patches, footer
background cover, mask **Fit** wrappers, collection slot dimensions and actual danger line remain code-owned:
they depend on viewport/safe area, physical floor, content count or real danger
threshold. Do not move the Machine root to “fix” gameplay positioning; edit its
**TopMachine** children instead. The physical release outlet remains Y=269 in
machine space. Moving the nozzle art does not move that gameplay outlet.

Score fitting uses the authored label width and font size as its maximum,
shrinking long scores as necessary. Physics bodies, piece art calibration (2.18),
collision radii, input bounds and gameplay timing are not presentation controls.

## Current visual calibration

- Totolina: position **(9,78)**, uniform scale **0.15**. These are authored
  presentation values; the physical release outlet remains Y=269.
- The hanging idle arm uses **Z=4**, local position **(-16,17)** and no rest
  rotation. The three pressing arms retain **Z=2**, below the shoulder patch
  at **Z=3**. The idle contour is continuous beside the body; the patch masks
  the pressing poses' root seam. Preserve the shared arm anchor **(650,410)**,
  source pivots, and body-texture patch **Rect(530,325,170,95)**.
- Feeder: scale **0.32**, position **(259,121)**; Current **(259,180)** / scale
  **0.110**, Next and Incoming **(259,95)** / scale **0.105**.
- Shutter: **(209,201.5)**, scale **100/1024**; its bottom at Y≈221.81
  stays inside the feeder's painted bottom at Y≈233.96. Regression checks pin
  this authored placement and retain containment and score-clearance checks.
  Its **12–16px** bottom-inset band is the former **2–6px** band shifted by the
  authored **10px** rise, with the same width. Shutter Z=0,
  previews Z=1, glass Z=2. Its timeline and the physical release outlet are unchanged.
- Nozzle rest: **(256,264)**, scale **0.15**. Stop/Reset restores the authored
  transform rather than the historical X=250. Input still supplies action targets.
- Score housing: **(339,95)**. Token scale **(0.096304685,0.09179686)** at
  **(28.654053,50.5)**; colon **(55,51)**, label X=68.
- The original mapping used source floor row 1567. The front interior edge is
  around row 1595, 28 source pixels lower: **12.71 / 13.20 / 17.60** display pixels
  at widths 390 / 405 / 540. The art mapping now aligns 1595 with the same physics
  floor; no physics position changed.
- Existing texture regions are split nondestructively with native rectangular
  clips: rear → lower interior/front lip (Z=−1) → bodies (Z=1) → top/side rails
  (Z=30). The footer's central first 70 source pixels also sit behind bodies;
  side rails and collection trim stay in front. No PNG edit or new art needed
  for this rectangular depth separation. Complex curved occlusion would need
  separately authored art, not per-piece hacks.
- The lower foreground side width is **56 source pixels**: the vertical rails
  remain in front, while inward corner bevels sit behind bodies. The previous
  96-pixel mask concealed 12–17 display pixels inside the legal resting area at
  the tested widths. The physical floor and source-row-1595 anchor are unchanged.
- Frame and controls share one seam: **BottomControls**' global top edge. The
  frame ends there; the controls background starts there and fills to the device
  bottom. Footer artwork uses uniformly scaled top/bottom copies with disjoint
  clips, preserving the floor and bottom trim while cropping/repeating only the
  dark middle. It is not squeezed vertically or tiled through decorative trim.

## Animation panel

Open the shared machine scene, select **AnimationPlayer**, choose an animation
in the **Animation** panel, and edit key timing/easing. Blink lives in Totolina's
**IdlePlayer**. Saved native tracks are shared by the lab and gameplay.

- `arm_pose`, `button_pose`, `shutter_pose` crossfade source poses.
- `current_offset` is relative to the authored Current position.
- `next_travel` / `next_growth` go from 0 to 1 between authored Next and Current.
- `incoming_pop` multiplies the authored Incoming scale.
- `reaction_offset` moves relative to Totolina Visual's authored position.

These script-backed tracks must be **run in the lab** for complete pose blending;
the editor timeline alone may not preview non-tool script setters.
Runtime input supplies nozzle X endpoints and distance-sensitive duration.
Those endpoints are intentionally not fixed designer values.

Do **not** blindly move the 0.20s contact event or change the 0.62s full cycle:
gameplay has an independent release/input clock. A timing change needs an
explicit integration/test pass. Decorative pose timing/easing can be tested in
the lab; check paw/button contact and all three target positions afterward.
The current standalone `press` arm reaches pose 01 at **0.100s**, while its button
retains the **0.075s** partial-depression key. `full_drop` retains its **0.075s**
first arm key. Independent key assertions preserve these intentional differences
without moving the shared **0.200s** full-contact event or either action's length.
Arm source pivots/rest rotations remain ordinary Sprite properties per pose,
not hidden frame-specific code. Do not move them randomly to fix the whole cat.

The separately approved `merge_effect_lab.tscn` and its flavor component were
not reauthored. Their existing timing controls remain as documented in
`MERGE_EFFECT_LAB.md`.

## Safe experiments and recovery

First three exercises:

1. FeederGlass: change uniform scale 0.32 → 0.33; run gameplay. Check compartment
   centers, shutter overlap and score clearance; Undo if worse.
2. Shutter: move Y 201.5 → 200; run the machine lab, full drop and shutter previews.
3. Open Totolina: move Visual/Eyes X 401 → 403; run blink, excited and surprised.
   One shared eye anchor should move every expression consistently.

Use editor **Undo** before saving an unwanted experiment. Inspect Git status and
diff before any checkpoint. Do not reset/revert unrelated uncommitted work.
Save a deliberate scene change, reopen it, then test Restart and Play Again.
Physical-device readability/touch/safe-area review remains necessary.

## Kitchen gameplay controls

Open `res://scenes/presentation/kitchen_gameplay_controls.tscn` to tune the new
world-specific controls. Run `physics_sandbox.tscn` to test their gameplay
actions. These are ordinary **Control** nodes: edit **Layout → Anchors / Offsets**
and the child TextureRect fitting, rather than scaling physics or the chamber.
The following paths are relative to the `GameplayControls` scene root.

| Element | Node | Safe designer properties |
| --- | --- | --- |
| Bottom group | `SafeBounds/BottomControls` | Anchors/offsets; preserve separation from the collection strip |
| Bottom background art | `SafeBounds/BottomControls/Background/Artwork` | Source region; clipping/cover size and position are runtime-owned |
| Push buttons | `SafeBounds/BottomControls/PushLeft`, `PushRight` | Anchors/offsets; child `Base`, `LabelArt` and `LocalizedLabel` fitting |
| Restart button | `SafeBounds/BottomControls/Restart` | Anchors/offsets; child `Base`, `LabelArt` and `LocalizedLabel` fitting |
| Circular hold feedback | `SafeBounds/BottomControls/Restart/HoldProgress` | Size and horizontal anchors/offsets; root `Restart Progress Gap` controls clearance above the strip |
| Top-left Exit Run | `SafeBounds/ExitRun` | Anchors/offsets; centered above Totolina's head, clear of ears |
| Exit panel | `ExitRunModal/SafeBounds/Panel` | Anchors/offsets; keep centered inside the safe area |
| Modal background | `ExitRunModal/SafeBounds/Panel/Background` | Anchors/offsets; stretch fills the complete panel |
| Modal Totolina | `ExitRunModal/SafeBounds/Panel/Totolina` | Anchors/offsets; preserve aspect ratio |
| Modal actions | `ExitRunModal/SafeBounds/Panel/Resume`, `Confirm` | Anchors/offsets and child `Base` fitting; preserve usable touch targets |

The two **SafeBounds** nodes are runtime-owned safe-inset wrappers. Edit their
children, not the wrappers: gameplay supplies the device insets whenever the
viewport changes. Current defaults are a 52-pixel-high bottom group, 16 pixels
from the safe left/right/bottom; a **52×52 Exit Run target centered at 16% of the
safe width**, top offset **0**; and modal panel anchors (0.06,0.20) through
(0.94,0.80). Exit's left/right anchors are **0.16**, offsets **−26/+26**; bottom
offset is **52**, scale remains (1,1). Edit these scene properties to move it
horizontally. It sits above Totolina's head rather than against the device corner;
increasing the height requires rechecking clearance above the ears.

`layout_footer_background` uses the bottom group's global top as the shared
machine/controls seam. Changing that group's top offset moves both edges
together. The background clip fills the full screen width and remaining bottom
height, independently of the safe button insets. **Artwork** has source region
**(0,8,1080,183)**: the original 1080×200 PNG contains eight transparent top rows
and nine bottom rows. Uniform cover scaling and a clipped one-pixel bleed avoid
padding gaps without editing the PNG. The source also contains partially
transparent interior rows; a navy **Backing** ColorRect beneath it prevents
the environment showing through. Both decorations ignore input. Buttons retain
their safe-area positions and touch sizes on top of this background.

Horizontal button anchors inside **BottomControls** are Push Left **0.055–0.265**,
Restart **0.3218–0.6782**, and Push Right **0.735–0.945**. All keep 52-pixel-high
touch targets. Their **Base** uses Keep Aspect Centered: the different source
face widths fit at the same painted height (about 42/44/52 pixels at the tested
widths), without stretching the artwork. Push **LabelArt** horizontal anchors
are 0.16–0.84 and Restart 0.10–0.90, with centered vertical offsets −14/+10.
Restart stays centered and the side buttons sit near the reference positions.

The hold indicator uses native **TextureProgressBar → Fill Mode → Clockwise**.
Its empty/full 400×400 textures fit a 64×64 Control, horizontally centered above
Restart with offsets left −32 and right 32. Size and horizontal position are
scene-authored. Its vertical position follows the responsive collection strip:
`kitchen_gameplay_controls.gd → place_hold_progress` keeps its bottom above the
strip's top by the root Inspector property **Restart Progress Gap**, default
**8** pixels. The scene's top/bottom offsets are editor seeds, not the runtime
vertical-position tuning control. This is a continuous radial fill, not a frame
animation. The existing one-second gameplay hold remains the
authority; do not tune its `value`, `max_value` or the gameplay duration to move
or resize it. Release/cancel resets the ring and pressed artwork. Push remains
an immediate button action on valid release, not a hold action.

The Button subclass handles indexed touches locally because global mouse
emulation is disabled. Decorative children ignore input; keep that setting.
Normal/pressed textures are assigned on each Button. AtlasTexture regions omit
only transparent padding, so the differently sized right pressed-label canvas
does not cause a size jump. Source PNGs are not changed. Each Push/Restart
`LocalizedLabel` displays Spanish or Simplified Chinese text instead of the
English image label when that locale is active; retain these child nodes.

Exit Run pauses the SceneTree and opens a full-viewport input blocker. The modal
uses **Process Mode → Always** so Resume and Confirm work while paused. Do not
change the modal's input-blocking or process settings as a layout adjustment.
Resume preserves the exact run, including an already accepted machine-drop
cycle and deferred merge; Confirm leaves that run and returns to Main Menu.
It never quits the application. The supplied modal artwork has baked English
**PAUSED**, **RESUME** and **EXIT TO MENU**; translated modal artwork is not yet
available. The updated confirmation image uses the same resource path,
`assets/worlds/kitchen/ui/modals/exit_run/exit_run_confirm_button.png`, with no
extra destination caption. Do not assume those image pixels change with locale.
The gameplay `ResultOverlay` draws above the controls so game-over actions are
not covered by this presentation.

After any adjustment, check normal/pressed art, a partial and completed hold,
pause/resume and exit at 390×844, 405×720 and 540×960. Confirm that collection
scrolling and gameplay touches still work without input leaking through buttons.
