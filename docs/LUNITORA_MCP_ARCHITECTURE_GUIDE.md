# Lunitora MCP & Character Animation Architecture Guide

**Studio:** Lunitora Games  
**Current game:** Totolina Merge  
**Engine:** Godot 4.7.2  
**Platforms:** Android + iOS  
**Status:** Architecture agreement before MCP implementation  
**Purpose:** Source of truth for how Lunitora will automate art preparation, character rigging, animation, VFX, and development workflows through one extensible MCP toolkit.

---

# 1. Goal

Build one shared local **Lunitora MCP toolkit** that both development PCs can use.

The MCP should make repetitive visual-development work faster without turning the tooling itself into a larger project than the games.

The user should eventually be able to ask Codex things such as:

- Prepare all images in this folder for the Totolina rig.
- Remove their backgrounds and export transparent PNGs.
- Put them on the correct canvas sizes and preserve alignment.
- Create a skeletal character rig from these prepared parts.
- Create or modify a press, idle, walk, run, jump, blink, reaction, or other animation.
- Create a merge effect and automatically choose the most appropriate Godot technique.
- Create a CharacterBody2D wrapper for a future platformer/runner.
- Preview and validate the result.
- Later: add sound, haptics, camera effects, remote iOS builds, and other capabilities.

The MCP is an automation layer. It does not replace human art direction.

---

# 2. Core Rules

## 2.1 One shared toolkit

Maintain one Lunitora MCP codebase.

Both Windows PCs install/use the same toolkit.

Each machine enables only the capabilities available locally.

Example:

```text
Wife PC
- Photoshop tools
- Godot animation tools
- Godot rig tools
- Android tools if configured

Development PC
- Photoshop tools when needed
- Godot animation tools
- Godot rig tools
- Character controller tools
- Android build/device tools
- Regression/validation tools
```

The Mac remains primarily for iOS build/signing/testing and may receive remote automation later.

## 2.2 Modular and extensible

The MCP must be designed as independent modules.

Adding a new capability must not require rewriting existing modules.

Planned shape:

```text
tools/
└── lunitora_mcp/
    ├── core/
    └── modules/
        ├── photoshop/
        ├── godot_inspection/
        ├── godot_rig/
        ├── godot_animation/
        ├── godot_vfx/
        ├── character_controller/
        ├── android/
        └── validation/
```

Future modules may include:

```text
audio/
haptics/
camera/
ios_remote/
store_assets/
localization/
```

Sound effects are explicitly deferred, not excluded.

## 2.3 Capabilities fail independently

Photoshop being closed must not disable Godot tools.

No Android device being connected must not disable animation tools.

Future audio support being unavailable must not disable image processing.

Every module should report its own availability clearly.

## 2.4 Small, proven operations first

Do not begin with unrestricted application control.

Build small reliable operations, validate them, then expose higher-level workflows.

Example:

```text
inspect document
→ export PNG
→ validate PNG
→ batch process
→ high-level prepare_game_asset
```

Do not build a giant framework before the first useful workflow is proven.

---

# 3. Repository Art Structure

Editable art stays inside the same Git repository but outside Godot's import pipeline.

```text
source_art/
├── .gdignore
├── ART_GUIDE.md
├── _inbox/
├── _staging/
├── characters/
│   └── totolina/
├── worlds/
│   └── kitchen/
└── ui/
```

## `_inbox/`

Temporary input waiting for MCP processing.

Examples:

```text
source_art/_inbox/totolina_new_rig/
source_art/_inbox/new_ui_icons/
source_art/_inbox/kitchen_props/
```

It may contain:

- one image
- many images
- a flat folder
- a prestructured folder

`_inbox/` is local working space and should initially be Git-ignored.

## `_staging/`

Processed candidate output awaiting review.

Examples:

- transparent PNGs
- resized/canvas-normalized assets
- previews
- contact sheets
- validation reports

MCP writes here by default.

Runtime assets should not be overwritten automatically.

`_staging/` should be Git-ignored.

## Versioned source art

Important approved references and editable masters belong under:

```text
source_art/characters/
source_art/worlds/
source_art/ui/
```

Godot runtime assets remain under existing:

```text
assets/
```

---

# 4. Photoshop / Image Processing Agreement

The Photoshop module is primarily a **batch asset-preparation system**.

It is not dependent on manually building Photoshop artboards for every existing asset.

Artboards are used only when a task benefits from them.

## Required input modes

### Flat folder

Example:

```text
totolina_head.png
totolina_torso.png
totolina_upper_arm_l.png
totolina_forearm_l.png
totolina_paw_l.png
```

MCP identifies parts using the agreed naming convention.

### Structured folder

Example:

```text
totolina/
├── body/
├── arms/
├── legs/
├── face/
└── tail/
```

MCP processes recursively and preserves/maps structure.

## Photoshop MCP v0.1 capabilities

Initial operations should support:

```text
photoshop_ping
photoshop_get_active_document
photoshop_open_image
photoshop_get_document_info
photoshop_list_layers
photoshop_remove_background
photoshop_set_canvas
photoshop_fit_subject
photoshop_export_png
photoshop_validate_export
prepare_asset_batch
```

The exact public tool names may change during implementation, but these capabilities are the agreed target.

## Batch image preparation

MCP must be able to process multiple files in one request.

Example user request:

> Prepare everything in `source_art/_inbox/totolina_new_rig`. Remove backgrounds, preserve transparency, apply the Totolina rig asset profile, export the prepared PNGs to staging, and generate a validation report.

Possible pipeline:

```text
scan input
→ classify files
→ remove background
→ validate subject bounds
→ create/resize canvas
→ scale/position according to profile
→ export transparent PNG
→ validate output
→ sort into staging structure
→ report results
```

---

# 5. Asset Profiles

Do not force Codex to reinvent dimensions/rules every time.

Support reusable asset profiles.

Examples:

```text
totolina_rig_part
totolina_face_part
ui_icon
merge_item
world_prop
full_screen_background
```

A profile may define:

- expected format
- canvas policy
- transparency requirement
- scaling policy
- padding
- naming convention
- destination mapping
- whether trimming is allowed
- validation rules

Profiles must remain editable and extendable.

---

# 6. Character Animation Architecture

## 6.1 Use a hybrid skeletal rig

Reusable Lunitora characters should primarily use:

```text
Skeleton2D
Bone2D
Polygon2D weighted meshes
AnimationPlayer
```

Use images/texture states where images are simpler or visually better.

Examples:

```text
Body/limb movement → bones
Tail motion → bones
Ear motion → bones
Walk/run/jump → bones
Reach/press → bones

Blink → image/opacity states
Mouth expressions → image/opacity states
Extreme hand/paw silhouettes → optional image variants
Rare special pose → optional image variant
```

This prevents the need for hundreds of individually drawn frames while preserving the ability to use frame-like artwork where appropriate.

## 6.2 Reusable visual rig root

The reusable character asset should be independent of gameplay physics.

Preferred shape:

```text
TotolinaRig (Node2D)
├── Meshes
│   ├── Polygon2D...
├── Skeleton2D
│   └── Bone2D...
├── Face
│   ├── Eyes
│   └── Mouth
├── Markers
└── AnimationPlayer
```

Exact node organization will be determined during the prototype.

---

# 7. CharacterBody2D Support

CharacterBody2D support is included from the beginning as an **optional gameplay wrapper**.

Do not make CharacterBody2D the root of every visual rig.

## Presentation use

For Totolina Merge:

```text
TotolinaPresentation (Node2D)
└── TotolinaRig
```

No CharacterBody2D is required just to animate Totolina at the machine.

## Movement-game use

For a future platformer/runner:

```text
TotolinaPlayer (CharacterBody2D)
├── CollisionShape2D
├── MovementController
└── TotolinaRig
```

Same visual rig.

Different gameplay wrapper.

## Initial controller profiles

Support scaffolding for:

```text
none
platformer
top_down
runner
```

### `none`

Visual/animation only.

### `platformer`

Basic support for:

- gravity
- floor/wall collision
- slopes
- horizontal movement
- jump

### `top_down`

Basic movement without floor/ceiling semantics.

### `runner`

Basic platformer-style wrapper with automatic horizontal progression.

Do not add advanced mechanics until a real game needs them.

Deferred examples:

- wall jump
- ladders
- swimming
- ledge grab
- combat
- knockback
- networking

---

# 8. Animation Strategy Selection

The MCP must not use one technique for everything.

It should inspect the target and choose the simplest appropriate technique.

## Decision table

| Target / effect | Preferred technique |
|---|---|
| Character limbs/body/tail | Skeleton2D + Bone2D |
| Blink/mouth states | Texture/opacity states |
| Character walk/run/jump | Skeleton animation |
| Machine button/door/lever | AnimationPlayer |
| UI slide/pop/pulse | Tween or AnimationPlayer |
| Merge squash/pop | Tween or AnimationPlayer |
| Sparkles/crumbs/magic burst | GPUParticles2D |
| Glow/dissolve/flash | CanvasItem shader |
| Falling/bouncing game object | Physics remains authoritative |
| Multi-system sequence/cutscene | AnimationPlayer coordination |
| Advanced state blending | AnimationTree when justified |

---

# 9. Auto Strategy Mode

High-level animation/effect tools should support:

```text
strategy = auto
```

In auto mode:

```text
request
→ inspect target
→ classify intent
→ select technique(s)
→ produce plan
→ apply
→ preview
→ validate
```

For substantial changes, the MCP should report its selected strategy before applying it.

Example:

> Make the Wheat → Flour merge more satisfying.

Possible result:

```text
Selected:
- Tween for scale pop
- GPUParticles2D for flour burst
- brief CanvasItem flash
- existing Totolina reaction animation

Not changed:
- merge physics
- scoring
- merge arbitration
```

The MCP must distinguish visual feedback from gameplay authority.

---

# 10. Merge Effects Agreement

Merge effects do not use Totolina's skeleton unless Totolina herself reacts.

A merge may coordinate:

```text
Result object scale/pop
+ particles
+ glow/flash
+ optional ring/trail
+ Totolina reaction
+ future sound
+ future haptic
```

The merge system's physics/gameplay remains authoritative.

Cosmetic effects must not grant rewards, trigger merges, or determine gameplay outcomes.

---

# 11. Animation Creation Tools

The Godot animation module should eventually support operations such as:

```text
inspect_animation
create_animation
duplicate_animation
set_animation_duration
set_key
move_key
remove_key
preview_animation
validate_animation
```

For skeletal clips:

```text
set_bone_rotation_key
set_bone_position_key
set_bone_scale_key
```

For character facial states:

```text
set_expression_state
set_blink_state
set_mouth_state
```

High-level requests should build on these primitives.

---

# 12. Rig Creation Tools

The rig module should eventually support:

```text
inspect_rig
create_skeleton
add_bone
set_rest_pose
create_polygon_mesh
assign_texture
bind_mesh_to_skeleton
set_bone_weights
create_marker
validate_rig
create_rig_preview
```

Weighting/mesh generation may require human review.

MCP should automate the mechanical first pass, not pretend every deformation is artistically correct.

---

# 13. Animation Reuse

Animations should be reusable where the rig contract remains compatible.

Potential Totolina clips:

```text
RESET
idle
blink
press
reach
excited
surprised
happy
walk
run
jump_start
jump_air
jump_land
```

Totolina Merge may use only a subset.

A future Totolina game can reuse compatible clips without duplicating the character source.

---

# 14. AnimationTree Policy

Do not introduce AnimationTree immediately.

Initial character architecture:

```text
Skeleton2D
+ AnimationPlayer
```

Add AnimationTree only when the project demonstrates a real need for:

- state machines
- animation blending
- layered motion
- simultaneous locomotion + expressions

No premature complexity.

---

# 15. VFX Module

MCP v0.1 should support basic VFX used by Totolina Merge.

Initial targets:

```text
GPUParticles2D
Tween
AnimationPlayer
basic CanvasItem shader parameters
```

Use conservative defaults suitable for mobile.

Do not assume desktop GPU performance represents phone performance.

---

# 16. Character Controller Module

Initial CharacterBody2D tooling should support:

```text
create_character_body_wrapper
configure_collision_shape
configure_motion_mode
create_basic_movement_controller
inspect_character_controller
validate_character_controller
create_movement_test_scene
```

Collision should remain simple and independent of visual mesh deformation.

Prefer simple collision shapes unless a real gameplay requirement justifies something more complex.

---

# 17. Validation Module

Every creation/edit workflow must include validation.

## Technical validation

- expected file exists
- dimensions correct
- format correct
- alpha/transparency correct
- resource paths valid
- scenes load
- no missing dependencies
- node paths valid
- animation names valid
- collision shape valid
- exported artifact exists

## Visual validation

- alignment correct
- no unexpected crop
- no halos/background
- pose looks natural
- mesh does not tear
- character silhouette remains recognizable
- animation timing feels correct
- effect fits art direction

Visual review remains human-approved.

---

# 18. Human Approval Boundaries

MCP may produce candidates automatically.

MCP should not automatically:

- overwrite the only editable master
- replace approved production assets without explicit intent
- rewrite gameplay because an effect looks wrong
- silently change permanent IDs
- publish a build
- upload to stores
- weaken tests to make a change pass

Preferred workflow:

```text
generate/process
→ staging
→ validate
→ human review
→ explicit approve/replace
```

---

# 19. Existing Production Character Migration

Do not immediately replace the current production Totolina implementation.

First build a separate skeletal prototype.

Proposed prototype:

```text
TotolinaRigV2
+ totolina_skeleton_lab
```

The exact paths/names will be chosen after inspecting the current project conventions.

The existing production character remains intact until the prototype proves itself.

## Skeletal prototype acceptance test

The new rig must demonstrate at least:

```text
idle
blink
press
```

Acceptance criteria:

- easier to edit than current pose sequencing
- visually smooth
- no mesh tearing
- button press can be aligned accurately
- both PCs can edit the rig
- Codex/MCP can inspect and modify it reliably
- mobile performance remains appropriate

Only after this passes should production migration be considered.

Walk/run/jump can follow after the core rig is proven.

---

# 20. MCP v0.1 Scope

## Included

### Core
- local server
- configuration
- module discovery
- logging
- permission/path validation
- structured errors

### Photoshop
- connection/ping
- document inspection
- one-image processing
- batch processing
- background removal
- canvas handling
- PNG export
- output validation

### Godot inspection
- inspect scenes/nodes/resources
- inspect animations
- inspect rigs

### Godot rig
- create/prototype Skeleton2D/Bone2D setup
- basic Polygon2D binding/weight workflow
- validate rig

### Godot animation
- AnimationPlayer operations
- skeletal key operations
- Tween operations
- preview/validation

### VFX
- basic GPUParticles2D
- basic shader-effect support

### Character controller
- optional CharacterBody2D wrapper
- basic profiles

### Validation
- technical checks
- preview generation where practical

## Deferred

Not part of initial implementation:

```text
sound/SFX
music
audio mixing
haptics
advanced camera effects
remote iOS automation
store publishing
advanced AnimationTree logic
advanced procedural rigging
complex IK systems
multiplayer/network tooling
```

These remain compatible with the modular architecture and can be added later.

---

# 21. Future Audio Module

Sound is explicitly planned for later.

Possible capabilities:

```text
audio_inspect
audio_import
audio_assign_bus
audio_add_sfx_event
audio_preview
audio_validate
```

Future high-level effects may combine:

```text
visual animation
+ particles
+ shader
+ sound
+ haptic
```

No audio implementation is required for MCP v0.1.

---

# 22. Versioning

Treat the toolkit as a real internal product.

Suggested milestones:

```text
lunitora-mcp-v0.1
lunitora-mcp-v0.2
...
```

Each milestone should document:

- added capabilities
- changed tools
- validation performed
- compatibility requirements
- known limitations

Avoid breaking existing tool contracts without a reason.

---

# 23. Anti-Regression Rules

Before changing working game code:

1. inspect current state
2. identify contracts that must not break
3. make the smallest reasonable change
4. avoid unrelated refactoring
5. validate
6. report what was and was not executed

The MCP must follow the same rules.

For Totolina Merge, gameplay authority must remain separated from cosmetic animation.

---

# 24. Initial Implementation Sequence

We will build the system incrementally.

## Phase 0 — Baseline

Prerequisites:

- Totolina Merge `main` is green
- repository naming finalized
- `source_art/` exists
- `ART_GUIDE.md` exists
- `_inbox/` and `_staging/` ignored
- Photoshop installed where needed
- Godot 4.7.2 available

## Phase 1 — MCP Core + Photoshop connection

Goal:

Codex can call the local Lunitora MCP and receive a response from Photoshop.

Acceptance:

```text
photoshop_ping
```

works reliably.

Then:

```text
photoshop_get_active_document
```

returns document name, dimensions, and basic layer/artboard information.

No image editing yet.

## Phase 2 — Image processing

Goal:

Process one or many source images.

Acceptance:

- flat-folder input works
- structured-folder input works
- transparent PNG export works
- exact canvas sizing works
- background removal works
- output goes to `_staging/`
- validation report generated

## Phase 3 — Skeletal rig prototype

Goal:

Create Totolina skeletal rig prototype without replacing production.

Acceptance:

- Skeleton2D/Bone2D hierarchy
- initial meshes/weights
- idle
- blink
- press
- editable on both PCs
- preview scene works

## Phase 4 — Animation/effect automation

Goal:

MCP can inspect a target and create/modify the appropriate animation/effect.

Initial strategies:

- skeleton
- AnimationPlayer
- Tween
- particles
- shader

Auto strategy begins here.

## Phase 5 — CharacterBody2D wrapper

Goal:

Wrap a reusable visual rig with optional gameplay movement.

Acceptance:

- platformer basic profile
- top-down basic profile
- runner scaffold
- collision validation
- test scene

## Phase 6 — Game-wide validation workflow

Goal:

Connect creation tools to Totolina Merge's existing tests and preview scenes.

Acceptance:

- changes can be previewed
- relevant regression checks run
- Android validation remains available

## Phase 7 — Future modules

Add only when justified:

- audio
- haptics
- camera
- remote iOS
- store tooling
- other Lunitora workflows

---

# 25. Definition of Success

The toolkit is successful when it reduces manual repetitive work without reducing control or introducing maintenance burden.

For v0.1, success means:

- wife can drop one or many source images into an inbox
- Codex can prepare them through Photoshop
- outputs are technically validated
- Godot can use the prepared assets
- a reusable skeletal character can be created/edited
- MCP can create or modify common animation/effect types
- CharacterBody2D support is available when needed
- existing gameplay remains protected
- both PCs can use the same toolkit
- new modules can be added later without redesigning the system

---

# 26. Locked Decisions

These decisions are considered agreed unless a real implementation problem proves otherwise:

1. One shared modular Lunitora MCP toolkit.
2. Same toolkit codebase on both Windows PCs.
3. Photoshop module supports batch processing.
4. Flat and structured image-folder inputs are supported.
5. `_inbox/` is input; `_staging/` is candidate output.
6. Runtime assets remain separate from source art.
7. Reusable characters use a hybrid skeletal approach.
8. Skeleton2D/Bone2D handles body motion.
9. Polygon2D weighted meshes are supported where deformation helps.
10. Image/opacity states remain valid for face/special poses.
11. Character visual rig is independent of CharacterBody2D gameplay wrapper.
12. CharacterBody2D support exists as an optional MCP capability.
13. MCP selects the best animation/effect strategy rather than forcing bones everywhere.
14. Merge effects remain separate from merge gameplay authority.
15. AnimationTree is deferred until demonstrated necessary.
16. Sound is deferred but the architecture must support a future audio module.
17. Production Totolina is not replaced until the skeletal prototype passes.
18. Human review remains required for visual quality.
19. MCP writes candidates to staging before production replacement by default.
20. The toolkit remains incremental and anti-regression focused.

---

# 27. Immediate Next Step

Start **Phase 1: MCP Core + Photoshop connection**.

The first implementation milestone is deliberately small:

```text
Codex
→ Lunitora MCP
→ Photoshop bridge
→ Photoshop replies
```

Acceptance test:

1. Start Photoshop.
2. Start the local Lunitora MCP.
3. Codex calls `photoshop_ping`.
4. Photoshop confirms availability.
5. Codex calls `photoshop_get_active_document`.
6. If a document is open, return:
   - filename
   - width
   - height
   - layer count / basic structure
7. No file is edited.

Only after this works reliably do we implement batch image processing.
