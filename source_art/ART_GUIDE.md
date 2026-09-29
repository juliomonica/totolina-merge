# Totolina Merge — Art Guide

**Project:** Totolina Merge  
**Studio:** Lunitora Games  
**Purpose:** Source-of-truth rules for creating, editing, reviewing, exporting, and versioning all visual assets used by the game.

---

## 1. Purpose

This document defines the shared art workflow for **Totolina Merge**.

It applies to:

- character artwork
- animation source artwork
- world/environment artwork
- machine and prop artwork
- UI artwork
- icons and decorative graphics
- AI-generated visual references
- Photoshop source files
- exported runtime images used by Godot

The goals are:

- keep artwork consistent across both development PCs
- make source files easy to hand off through Git
- prevent alignment and animation regressions
- prevent Godot from importing editable source files
- preserve editable masters
- keep runtime assets lightweight and mobile-friendly
- support Android and iOS from the same asset pipeline
- allow future Photoshop/MCP automation without changing the art rules

This document contains **global rules**. Character-, world-, or UI-specific notes should only be added when a real need appears.

---

## 2. Core Principles

### 2.1 Source art and runtime art are different

Editable source files belong under:

```text
source_art/
```

Game-ready files used by Godot remain under:

```text
assets/
```

Example:

```text
source_art/characters/totolina/photoshop/totolina_master.psd
                            ↓ export
assets/characters/totolina/cat_totolina_arm_press_02.png
```

Never make Godot depend directly on a PSD/PSB or temporary working file.

### 2.2 Never overwrite the only editable master

Editable master files must remain recoverable.

Do not flatten the only copy of a PSD/PSB. Do not replace a layered master with an exported PNG.

Prefer reversible Photoshop techniques such as layers, masks, adjustment layers, smart objects, and editable transforms. A destructive edit is acceptable only when intentional and a recoverable prior version exists in Git/LFS.

### 2.3 Preserve working runtime paths

Do not reorganize existing `assets/` paths merely to make the source-art structure look cleaner.

Runtime paths may already be referenced by scenes, scripts, imported resources, tests, animation tracks, and documentation.

Source-art organization must adapt around working game paths, not the other way around.

### 2.4 One approved visual change at a time

When updating an asset:

1. start from the latest approved source
2. make the intended visual change
3. export only the required runtime file(s)
4. review the Git diff
5. preview the asset in Godot
6. run the relevant validation
7. commit source + runtime output together when appropriate

Avoid combining unrelated character, UI, environment, and gameplay changes in one art commit.

---

## 3. Repository Structure

Recommended structure:

```text
source_art/
├── .gdignore
├── ART_GUIDE.md
│
├── characters/
│   └── totolina/
│       ├── photoshop/
│       ├── references/
│       ├── concepts/
│       │   └── approved/
│       └── notes/
│
├── worlds/
│   └── kitchen/
│       ├── photoshop/
│       ├── references/
│       ├── concepts/
│       │   └── approved/
│       └── notes/
│
├── ui/
│   ├── photoshop/
│   ├── references/
│   ├── concepts/
│   │   └── approved/
│   └── notes/
│
└── _staging/
```

### 3.1 `.gdignore`

`source_art/.gdignore` must exist.

Godot must ignore the complete editable-source tree. Editable source files are not runtime game content and must not be included in game exports.

### 3.2 `_staging/`

`source_art/_staging/` is temporary local working space.

Examples:

- background-removal experiments
- temporary exports
- contact sheets
- previews
- test crops
- MCP intermediate files
- before/after comparisons

`_staging/` must be Git-ignored.

Do not use staging files directly from Godot scenes. Only approved outputs should enter `assets/`.

---

## 4. File Naming

Use lowercase `snake_case` for runtime assets whenever practical.

Examples:

```text
cat_totolina_body.png
cat_totolina_arm_idle.png
cat_totolina_arm_press_01.png
cat_totolina_arm_press_02.png
cat_totolina_arm_press_03.png
cat_totolina_eyes_blink_01.png
machine_foreground_frame.png
bottom_controls_background.png
```

Avoid spaces, inconsistent capitalization, accented characters in filenames, Unicode lookalike characters, case-only duplicates, and names such as `final_final_v2_really_final.png`.

Editable Photoshop files may use descriptive names, but they should still be predictable.

Example:

```text
totolina_master.psd
kitchen_machine_master.psd
main_menu_master.psd
```

For numbered sequences, use zero-padded numbers where useful:

```text
arm_press_01
arm_press_02
arm_press_03
```

---

## 5. Photoshop Master Rules

### 5.1 Master files

Use PSD or PSB for editable Photoshop masters.

Store them under:

```text
source_art/.../photoshop/
```

Large PSD/PSB files should use Git LFS when enabled for the project.

Runtime PNGs should remain normal Git files unless repository size later justifies a different policy.

### 5.2 Layers

Use clear, descriptive layer/group names.

Prefer names that match the runtime asset or logical character part.

Examples:

```text
body
arm_idle
arm_press_01
arm_press_02
arm_press_03
eyes_idle
eyes_blink_01
eyes_blink_02
eyes_blink_03
eyes_excited
mouth_idle
mouth_excited
```

Avoid unnamed layers such as `Layer 12 copy 3` before committing a master file.

### 5.3 Preserve alpha

Character parts and other transparent runtime assets must retain clean transparency.

Check for:

- white/black halos
- semi-transparent fringe pixels
- leftover background pixels
- accidental opaque corners
- holes in intended solid areas
- clipped shadows, fur, or whiskers

Background removal is not considered complete just because the file contains an alpha channel.

Visual inspection is required.

### 5.4 Color

Default working color space for standard 2D game assets:

- sRGB
- normal screen-oriented RGB workflow

Do not introduce CMYK source assets into the runtime pipeline.

Avoid unnecessary HDR/wide-gamut complexity unless the game later demonstrates a real need.

---

## 6. Character Art — Totolina

Totolina currently uses layered 2D artwork and native Godot animation/presentation logic.

The character source and runtime implementation may include separate:

- body
- arm poses
- eyes
- blink states
- facial expression states
- mouth states

These are individual visual states, not automatically individual Godot animation clips.

### 6.1 Character consistency

When creating or editing Totolina, preserve the approved:

- face shape
- eye placement
- eye style
- fur/color pattern
- body proportions
- head/body scale relationship
- paw proportions
- line/rendering style
- overall visual identity

AI generations are references until reviewed.

Do not replace canonical character traits solely because a generated image looks attractive.

### 6.2 Shared alignment is critical

Animation frames/parts must preserve a consistent spatial reference.

For related pose images:

```text
arm_idle
arm_press_01
arm_press_02
arm_press_03
```

do **not** independently trim each image to its visible pixels unless the Godot offsets are deliberately updated and validated.

Preferred approach:

- preserve a shared canvas/reference frame, or
- preserve explicit, documented offsets

The goal is: replacing one pose with another must not cause an unintended jump.

### 6.3 Do not move the whole character to repair one pose

If Totolina's overall placement in a world is correct but one arm misses a button, adjust the pose/art/alignment responsible for that action, not the whole character.

Likewise, do not change gameplay contact timing just to compensate for artwork that is visually misaligned.

### 6.4 Character placement vs character source

Keep this distinction:

```text
Totolina source scene
= what the character artwork/poses look like

World/machine presentation scene
= where Totolina is placed and when interaction poses occur
```

Changing the reusable character source can affect every scene that uses it.

Changing the world instance placement affects only that composition.

Choose intentionally.

---

## 7. Animation Art Rules

### 7.1 Artwork and animation timing are separate

For the current machine button interaction:

- Totolina arm artwork defines the available poses
- the machine presentation animation determines when each pose appears
- machine/button animation controls its own visual state
- gameplay remains authoritative for gameplay consequences

Do not casually move gameplay/contact events to make an art edit look correct.

Align the visuals to the intended event timing wherever possible.

### 7.2 Preview in context

An animation is not approved only because it looks correct in the isolated character scene.

Review:

1. isolated character/source scene if useful
2. relevant animation/presentation scene
3. debug interaction lab where available
4. actual gameplay

For important interactions, validate on a physical mobile device before final release.

### 7.3 Preserve animation contracts

Do not rename or reorder nodes used by animation/presentation scripts without a specific reviewed migration.

Preserve:

- animation property names
- expected child/node names
- resource paths
- UIDs
- pivots
- authored offsets
- gameplay-event contracts

Art improvements must not silently change gameplay.

---

## 8. World and Environment Art

World art must support:

- portrait-first layout
- mobile safe areas
- multiple phone aspect ratios
- character readability
- gameplay readability
- foreground/background depth
- clear interaction zones

Totolina Merge currently validates important presentation across portrait configurations including:

- 390 × 844
- 405 × 720
- 540 × 960

These are validation references, not the only supported resolutions.

Artwork must remain responsive outside those exact dimensions.

### 8.1 Foreground/background separation

If an object must cover only part of a character, split visual layers appropriately.

Example:

```text
machine_background
Totolina body
machine_foreground / chamber lip
Totolina arm if it must reach in front
```

Do not rely on one giant flattened machine image when different parts need different draw order.

Use dedicated foreground layers when necessary.

### 8.2 Occlusion

When feet/body should appear behind a chamber, table, rail, or machine:

- prefer correct foreground layering
- avoid shrinking/moving a character purely to hide an occlusion problem
- avoid using broad Z-index changes that incorrectly hide the head/arms

Visual depth should match the physical composition.

---

## 9. UI Art

UI must remain:

- touch-first
- readable on phones
- safe-area aware
- localization friendly
- scalable across supported portrait layouts

### 9.1 Do not bake normal UI text into artwork

Avoid embedding English UI text into images.

UI text should normally come from Godot localization strings.

Initial launch languages:

- English
- Spanish
- Simplified Chinese (`zh-CN`)

Artwork that includes unavoidable decorative text requires explicit review because it creates localization work.

### 9.2 Button states

When creating button graphics, clearly identify states such as:

```text
normal
pressed
disabled
selected
```

Do not create visually different states with inconsistent canvas dimensions/alignment unless intentional.

Touch target size is a gameplay/UI concern and must not depend only on visible artwork bounds.

---

## 10. AI-Generated Image Workflow

AI-generated images are **source material**, not automatically approved game assets.

Recommended flow:

```text
ChatGPT generation
        ↓
reference / concept review
        ↓
approved source candidate
        ↓
Photoshop cleanup and alignment
        ↓
runtime export
        ↓
Godot preview
        ↓
validation
```

### 10.1 Save meaningful references

Approved or important AI generations should be stored under the relevant:

```text
references/
```

or:

```text
concepts/approved/
```

folder.

Do not version every failed generation.

### 10.2 Character references

For recurring Totolina generation, preserve useful canonical references such as:

- original character reference
- face reference
- pose reference
- approved expression references

A generated image must be checked against canonical Totolina features before being used as production art.

### 10.3 AI must not silently redefine the character

Do not accept:

- changed fur markings
- different eye design
- inconsistent proportions
- missing recurring traits
- unexplained clothing/accessory changes

unless the design change is intentionally approved.

---

## 11. Runtime Export Rules

Runtime assets must be exported deliberately.

Default for transparent 2D assets:

- PNG
- RGBA transparency where required
- original approved pixel dimensions
- no accidental resizing
- no background unless intentional

Do not repeatedly resample an already-resampled runtime PNG.

Prefer returning to the editable source and exporting again.

### 11.1 Exact size means exact size

If an asset specification requires a specific pixel size, verify the exported file after export.

Do not trust the prompt, Photoshop canvas, or MCP command alone.

Validation should independently confirm:

- width
- height
- format
- transparency where expected

### 11.2 Canvas resize vs image resize

Treat these as different operations:

- **image resize** changes artwork scale
- **canvas resize** changes available space around artwork

Do not scale character artwork just because the required export canvas changes.

### 11.3 Padding

When multiple animation frames must align, preserve consistent padding/canvas reference.

Do not automatically trim transparency unless the asset type explicitly allows it.

---

## 12. Mobile Performance Rules

Visual quality matters, but Totolina Merge targets Android and iOS.

Before adding very large assets, consider:

- texture dimensions
- memory use
- number of textures
- import compression
- draw calls
- overdraw
- transparency
- battery/thermal impact

Do not optimize blindly.

First validate a representative scene on real devices.

The desktop RTX/RX GPUs are not representative of mobile performance.

---

## 13. Localization Rules for Art

All normal user-facing text belongs in localization resources, not baked artwork.

Art must allow for:

- English
- Spanish
- Simplified Chinese

Consider:

- longer Spanish text
- different CJK glyph proportions
- button width
- label padding
- line wrapping

If a decorative image contains language-specific text, create a documented localized asset strategy before adding it.

---

## 14. Git and Collaboration Rules

### 14.1 Editable source + runtime output

When a committed source master produces a committed runtime asset, prefer committing them together.

Example:

```text
source_art/characters/totolina/photoshop/totolina_master.psd
assets/characters/totolina/cat_totolina_arm_press_02.png
```

This makes it possible to identify which editable source created the runtime asset.

### 14.2 One active editor per binary master

PSD/PSB files do not merge like code.

Avoid both people editing the same PSD simultaneously.

Before editing a shared master:

- pull latest changes
- confirm the working tree/branch
- coordinate ownership of that master during the edit

### 14.3 Branches

Use short-lived branches for meaningful art changes.

Examples:

```text
art/totolina-arm-update
art/kitchen-machine-pass
art/main-menu-polish
```

Merge reviewed art back into `main`.

Do not use one long-lived art branch for unrelated changes.

### 14.4 Git LFS

Use Git LFS for large editable binary source files when enabled.

Initial candidates:

```text
*.psd
*.psb
```

Do not automatically move every PNG into LFS.

Both Windows PCs must have Git LFS installed before working with LFS-tracked files.

---

## 15. Approval States

### Working

Still being edited. May contain experiments. Not approved for runtime replacement.

### Candidate

Ready to preview in Godot. May be exported into a branch for testing.

### Approved

Reviewed visually in context. Required tests/checks pass. Safe to merge.

### Runtime

The actual file currently referenced by the game under `assets/`.

An approved source asset is not automatically the runtime asset until its export is merged.

---

## 16. Photoshop / MCP Automation Rules

Future MCP/Photoshop tools must follow this guide.

Automation must not bypass these rules.

Initial automation should be narrow and reversible.

Preferred early operations:

```text
inspect document
list layers
validate canvas
export PNG copy
validate exported dimensions
```

Later operations may include:

```text
replace named layer artwork
remove background
export named character part
generate contact sheet
```

Avoid unrestricted execute-anything tooling when a scoped operation is sufficient.

### 16.1 Originals are protected

Automated tools should:

- avoid overwriting source masters by default
- write previews/temporary files to `_staging/`
- require explicit intent before replacing approved runtime assets
- report exactly which files changed

### 16.2 Validation is separate from editing

A tool saying "export succeeded" does not prove the asset is correct.

Separate:

**Technical validation**
- dimensions
- format
- alpha
- file exists
- expected destination

**Visual review**
- character is intact
- alignment is correct
- no halos
- no unwanted crop
- pose works in animation
- layering looks correct

---

## 17. Two-PC Handoff

Both PCs use the same repository and the same art rules.

Typical flow:

```text
Artist PC
ChatGPT → Photoshop → Godot animation preview
        ↓
Git branch / commit
        ↓
GitHub
        ↓
Development PC
Godot integration → validation → adjustment
        ↓
Git branch / commit
        ↓
GitHub
        ↓
Artist PC
continues from latest editable source
```

Every approved correction must return to the shared editable source.

Do not make a permanent fix only in an exported PNG if the underlying master would later overwrite it.

---

## 18. Art Change Checklist

Before committing an art change:

- [ ] Started from latest `main`/approved branch.
- [ ] Editable source preserved.
- [ ] Only intended assets changed.
- [ ] Runtime path was not unnecessarily changed.
- [ ] Canvas/alignment preserved.
- [ ] Transparency visually checked.
- [ ] No accidental baked UI text.
- [ ] Character identity remains consistent.
- [ ] Animation poses do not jump unexpectedly.
- [ ] Foreground/background layering looks correct.
- [ ] Relevant Godot scene previewed.
- [ ] Relevant interaction/debug lab tested when applicable.
- [ ] `git diff` reviewed.
- [ ] Temporary staging files are not tracked.
- [ ] PSD/PSB is stored correctly if part of the committed source.
- [ ] Mobile/device review performed when the change materially affects presentation/performance.

---

## 19. Do Not Do These

Do not:

- overwrite the only master PSD
- use source PSD files directly as runtime assets
- independently trim animation pose frames without preserving offsets
- bake normal English UI text into artwork
- rename runtime files casually
- reorganize working asset paths without a migration reason
- change gameplay timing to compensate for bad art alignment
- hide occlusion problems by moving the entire character unnecessarily
- commit staging experiments
- commit Photoshop cache/temp files
- add hundreds of AI generations to Git
- modify the same PSD simultaneously on two computers
- assume a desktop preview proves mobile quality
- assume an automated export proves visual correctness

---

## 20. Project-Specific Current Baseline

Current product direction:

```text
Studio: Lunitora Games
Character: Totolina
Game: Totolina Merge
Engine: Godot 4.7.2
Platforms: Android + iOS
Primary orientation: Portrait
First world: Kitchen
```

Current presentation architecture includes native Godot layered 2D character artwork and animation/presentation scenes.

Important global product priorities remain:

```text
FUN
→ RETENTION
→ MONETIZATION
→ OPTIMIZATION
```

Art should support the game rather than create unnecessary maintenance, oversized content pipelines, or fragile runtime dependencies.

---

## 21. Future Specialized Notes

Create specialized documents only when real requirements justify them.

Possible future files:

```text
source_art/characters/totolina/CHARACTER_NOTES.md
source_art/worlds/kitchen/WORLD_NOTES.md
source_art/ui/UI_NOTES.md
```

They should extend this guide rather than duplicate it.

`ART_GUIDE.md` remains the global source of truth.
