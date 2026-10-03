# Totolina Merge — Animation Guidelines

This document is the source of truth for animation work in Totolina Merge.

It applies to:

- character animation
- merge/cooking effects
- background and environment animation
- UI animation
- props
- particles/VFX
- future worlds/themes
- development animation previews and labs

The objective is polished, readable mobile animation with low technical and
maintenance cost.

---

# 1. Core Principles

Animation should support gameplay and presentation, not control gameplay state.

Prefer:

- simple
- readable
- responsive
- reusable
- mobile-efficient
- non-destructive

Avoid:

- animation systems more complex than the feature requires
- presentation code controlling core gameplay
- unnecessary dependencies
- large animation frameworks before reuse is demonstrated
- excessive particles/shaders
- animation that delays interaction without player value

When multiple approaches are possible, prefer the smallest one that produces
the required visual quality.

---

# 2. Godot Animation Tool Selection

Use Godot-native systems.

Choose the simplest appropriate tool.

## AnimatedSprite2D

Prefer for:

- sequential sprite frames
- hand-drawn frame animation
- simple looping environmental animation
- frame-by-frame VFX

Examples:

- blinking
- simple flame/water frames
- frame-based character details
- sprite-frame merge effects

## AnimationPlayer

Prefer for:

- coordinated multi-property animations
- position
- scale
- rotation
- opacity/modulate
- visibility
- sprite/frame changes
- multiple nodes moving together
- character cutout animation
- UI animation
- merge-effect timelines

AnimationPlayer is the preferred default when an animation has a defined
timeline involving multiple properties.

## Tween

Prefer for:

- small procedural transitions
- short one-off movement
- fades
- scale pops
- UI transitions
- simple runtime-generated motion

Do not build long or complicated animation sequences entirely from deeply
nested Tween code when AnimationPlayer would be clearer and easier to tune.

## Skeleton2D / Bone2D

Prefer for:

- reusable articulated 2D character animation
- Tolina body/head/ears/tail/legs
- animation where several poses reuse the same layered art
- smooth deformation when Polygon2D weighting is justified

Keep rigid pieces as Sprite2D where deformation is unnecessary.

Use Polygon2D deformation only where it creates meaningful visual benefit.

## AnimationTree

Do NOT use AnimationTree by default.

Use it only when there is a demonstrated need for:

- advanced animation blending
- state-machine transitions
- directional blends
- layered/blended character states
- complex character animation playback

Simple effects, UI motion and short character animations should generally not
need AnimationTree.

---

# 3. Presentation Must Be Independent From Gameplay State

Gameplay must never depend on a cosmetic animation reaching its final frame.

Conceptually:

gameplay action accepted
-> gameplay state updated safely
-> presentation animation plays

NOT:

animation reaches frame 7
-> gameplay state finally changes

Examples:

A merge should already be logically accepted before its flavor effect plays.

A reward should not disappear because an animation was interrupted.

Restarting or leaving a scene during an animation must not corrupt gameplay.

Presentation should be disposable.

---

# 4. Mobile-First Animation

All animation must be evaluated as phone content first.

Check at minimum:

- 390x844
- 405x720
- 540x960

Consider:

- small-screen readability
- safe areas
- notches / Dynamic Island
- UI overlap
- effect scale
- visual clutter
- battery usage
- GPU/CPU cost
- draw calls
- texture memory

An effect that looks good only when enlarged in the editor is not sufficient.

---

# 5. Timing Philosophy

Animations should feel responsive.

For ordinary gameplay feedback:

- favor short timings
- avoid unnecessary pauses
- maintain player control
- do not block input merely for presentation

Typical short effects may fall around:

0.1–0.8 seconds

but timing must be chosen by context, not by rigid global rules.

Character idle/background animation can naturally be longer.

Major celebration moments may be longer if justified.

---

# 6. Easing

Avoid visible linear motion unless linear movement is intentionally correct.

Prefer natural easing:

- ease-out when arriving
- ease-in when accelerating/falling
- ease-in-out for smooth travel
- subtle back/overshoot for soft impact

Avoid excessive:

- elastic bouncing
- extreme overshoot
- repeated wobbling

The intended feel is cozy and polished rather than hyperactive.

---

# 7. Squash and Stretch

Use squash/stretch selectively.

Good uses:

- merge impacts
- ingredient splashes
- soft UI pops
- character anticipation/reaction
- cream/frosting settling

Keep distortion subtle unless the art direction specifically calls for more.

Example:

0.92, 1.07
-> 1.03, 0.97
-> 1.00, 1.00

Do not permanently distort source artwork.

---

# 8. Crossfades and Key Poses

When only a few drawn poses exist, treat them as KEY POSES rather than abrupt
slideshow frames.

Use:

- overlapping alpha fades
- position interpolation
- scale interpolation
- subtle rotation
- squash/stretch

Typical short crossfade:

0.05–0.10 seconds

Avoid leaving two incompatible images fully visible for too long.

---

# 9. Character Animation

Character animation should prioritize:

- readable silhouette
- consistent pivots
- reusable layered artwork
- limited deformation
- expressive timing

For Tolina-style cutout rigs:

Prefer:

- Sprite2D for rigid layers
- Skeleton2D / Bone2D for hierarchy
- AnimationPlayer for authored motion
- Polygon2D only when smooth bending/deformation is genuinely needed

Potential rigid pieces include:

- body
- head
- ears
- tail
- front legs/paws
- face variants

Do not split character artwork into excessive pieces unless animation requires
it.

Every additional rig component increases setup and maintenance cost.

---

# 10. Character Pivot Rules

Pivots must be placed intentionally before animation work.

Examples:

- head pivot near neck
- ear pivot near ear base
- tail pivot at tail root
- leg pivot near shoulder/hip
- paw subdivision only if required

Do not compensate for bad pivots with complicated animation tracks.

When changing source artwork or pivots, verify existing animations before
accepting the change.

---

# 11. Character Source-Art Safety

Do not destructively alter master character artwork simply to make one animation
easier.

Preserve source/master files separately from runtime exports when appropriate.

Do not overwrite working character sprites without deliberate approval.

If a source asset must change:

1. identify affected animations
2. preserve previous working state
3. make the smallest change
4. retest relevant animations

---

# 12. Merge / Cooking Effects

Merge effects are presentation-only.

They must not use gameplay physics.

Do NOT use:

- RigidBody2D
- gameplay CollisionShape2D
- physical merge logic
- recipe state as presentation state

Prefer:

- Sprite2D
- AnimatedSprite2D
- AnimationPlayer
- Tween
- lightweight particles when justified

Merge effects should explain or enhance the transformation without confusing the
core gameplay rule.

---

# 13. UI Animation

UI animation should improve clarity.

Good uses:

- button press feedback
- panel transitions
- score feedback
- discovery reveal
- progress updates
- result presentation

Avoid:

- slow menu transitions
- motion that delays taps
- unnecessary bouncing everywhere
- constant decorative motion competing with gameplay

UI controls must remain usable while animations occur unless blocking is
deliberately required.

---

# 14. Background / Environment Animation

Background animation should support atmosphere without distracting from the
board.

Prefer:

- subtle loops
- low-frequency movement
- small prop motion
- layered parallax when useful
- occasional ambient details

Avoid making large high-contrast background elements move continuously behind
the gameplay area.

Background animation should be cheap enough for sustained mobile play.

---

# 15. VFX / Particles

Particles are optional, not the default solution.

Use particles when they significantly improve:

- merge satisfaction
- magic
- celebration
- impact
- environmental atmosphere

Keep:

- particle counts low
- lifetimes short
- textures small
- overdraw controlled

Avoid expensive full-screen particle effects on ordinary merges.

Prefer simple sprites/tweens when they communicate the same effect.

---

# 16. Transparency and Asset Preparation

Presentation PNGs should use real alpha transparency.

Do not accept:

- checkerboard backgrounds baked into artwork
- gray/white boxes
- accidental dark rectangles
- unwanted edge halos

Report bad transparency rather than hiding it with code.

Do not destructively repair user source artwork unless explicitly requested.

---

# 17. Texture and Frame Naming

Use descriptive, ordered names.

Examples:

idle_01.png
idle_02.png

egg_crack_01.png
egg_crack_02.png

milk_pour_01.png
milk_pour_02.png

Avoid ambiguous names such as:

final2.png
new_animation.png
test3.png

Once referenced by production scenes/resources, do not casually rename assets.

---

# 18. Animation Naming

Animation names should describe behavior.

Examples:

idle
blink
happy
merge_reveal
milk_pour
cream_swirl
button_press
panel_open

Avoid names based only on implementation sequence:

anim1
anim2
test
new

---

# 19. Reuse Without Premature Frameworks

Reuse is encouraged when demonstrated.

Do not create a large generic animation system before multiple animations
actually need it.

Prefer:

small reusable scene
+
clear configuration

over:

global animation manager
+
large abstraction layer

Move functionality into shared architecture only when reuse is real or highly
probable.

---

# 20. Reset and Replay Safety

Animations must survive repeated playback cleanly.

Before replay/reset where relevant:

- stop previous animation/tween
- reset alpha
- reset position
- reset scale
- reset rotation
- reset visibility/frame state

Do not:

- stack duplicate Tweens
- leak timers
- accumulate callback connections
- leave sprites visible after reset

Scene teardown must not leave callbacks trying to access freed nodes.

---

# 21. Scene Lifecycle Safety

Animation-related timers, tweens and callbacks must clean up safely when:

- scene changes
- restart occurs
- Play Again occurs
- gameplay ends
- node is freed

Never assume an animation will always finish.

---

# 22. Performance Guidelines

Prefer lightweight animation.

Avoid:

- unnecessary per-frame allocations
- large numbers of animated nodes
- large particle systems
- excessive shaders
- duplicated textures
- continuously running debug animations

Favor animation systems that can become idle when not in use.

Measure before optimizing aggressively, but do not knowingly introduce
expensive presentation for minor effects.

---

# 23. Debug / Animation Lab Workflow

Complex or experimental animation should first be tested in an isolated debug
scene when practical.

Recommended workflow:

1. create/adjust source assets
2. preview in animation lab
3. tune timing/motion
4. review visually
5. integrate into production
6. run gameplay regression tests
7. remove obsolete implementation only after replacement is verified

Do not repeatedly rewrite gameplay code merely to tune presentation timing.

---

# 24. Production Integration

Before integrating an experimental animation into production:

- visual direction approved
- assets load correctly
- transparency verified
- repeated playback stable
- mobile-size preview reviewed
- performance acceptable

Production integration should be a controlled change.

Do not remove the previous working implementation until the replacement is
validated.

---

# 25. Accessibility / Readability

Do not rely exclusively on rapid motion or subtle animation to communicate
important state.

Important gameplay information should remain understandable when:

- animation is missed
- animation is interrupted
- player attention is elsewhere
- motion is reduced

Avoid intense flashing or excessive rapid visual changes.

---

# 26. Validation Requirements

After meaningful animation changes, validate as relevant:

## Syntax / structure
- scene loads
- animation resources load
- referenced textures exist
- paths resolve

## Playback
- animation starts correctly
- animation completes correctly
- replay works
- interruption/reset works

## Visual
- no clipping
- no accidental backgrounds
- pivots correct
- scale correct
- animation readable on phone

## Regression
- gameplay behavior unchanged unless intentionally modified
- physics unchanged for presentation-only work
- scoring/progression unchanged
- navigation unchanged

## Performance
- no obvious runaway timers/tweens
- no persistent debug effects
- no excessive particle/animation cost

---

# 27. Validation Status Language

Reports must distinguish:

VERIFIED
- actually tested successfully

NOT EXECUTED
- not tested

REQUIRES USER REVIEW
- subjective animation quality/timing

REQUIRES ANDROID DEVICE
- Android hardware behavior

REQUIRES MAC/iOS
- iOS/Xcode/device behavior

Never claim visual quality was verified if it was not actually rendered/viewed.

---

# 28. Anti-Regression Rules

Before changing working animation:

1. inspect current implementation
2. identify what currently works
3. preserve behavior not targeted by the change
4. make the smallest reasonable modification
5. avoid unrelated refactors
6. validate affected scenes
7. report anything unverified

Do not broadly rewrite working animation simply because another implementation
looks cleaner.

---

# 29. Project Priorities

Animation quality should support:

FUN
-> RETENTION
-> MONETIZATION
-> OPTIMIZATION

Polish matters, but animation must not create unnecessary maintenance,
dependencies or technical debt.

Prefer a small number of polished animations over a large number of mediocre
ones.

---

# 30. Documentation

When a reusable animation convention is established, update this file rather
than duplicating the same rule across many documents.

World/feature-specific animation details may live in their own local
documentation if necessary.

This file remains the general animation source of truth.

## Shared lab/production timelines

Approved Kitchen flavor timelines live in
`scripts/presentation/merge_flavor_effect.gd`. The debug lab and gameplay both
instantiate that small presentation-only component; do not copy its keyframes
into a second implementation. Keep review controls in the lab, recipe-to-effect
names in content data, and merge/reward authority in gameplay. Production may
uniformly fit the visual root to the available viewport without changing pose
timing, source pivots, or any physics transform. Compare lab captures before/after
structural changes to ensure the approved output has not drifted.

---

# 31. Visual Animation Problem-Solving

These lessons from the assembled rig-test-cat apply to future Lunitora
characters and games across engines and tools.

## Decision Ownership

### Codex

Codex is responsible for visual and technical problem-solving. When an assembled
character or animation looks unnatural, Codex should:

- inspect the complete character and full animation, not only the rest pose;
- identify likely root causes without waiting for the user to diagnose individual
  transforms;
- test multiple bounded solutions when appropriate, comparing transforms,
  pivots, hierarchy, layering, z-order, underlap, clipping and artwork changes;
- reject fixes that work in one pose but fail during motion, and prefer the
  smallest solution that stays visually correct throughout the animation;
- distinguish art-preparation problems from rig/animation problems, avoiding
  unnecessary rig complexity to compensate for bad artwork;
- present the best validated candidate for human visual approval.

Codex should not require the user to prescribe every pixel-level or
transform-level correction.

### MCP / Tooling

MCP/tooling provides deterministic capabilities and safety. It should:

- inspect exact scene/resource state and expose exact transforms, pivots,
  animation values and resource identity;
- apply allowed deterministic edits;
- measure geometry, gaps, collisions, bounds and registration;
- capture/render representative poses where supported;
- preserve native Undo/Redo and no-auto-save guarantees where applicable;
- validate deterministic contracts and fail closed when state is unsafe or
  ambiguous.

MCP/tooling should not make subjective artistic decisions about whether an arm,
pose, silhouette or movement looks natural. These responsibilities describe
tooling where supported, not a requirement to expand its capabilities.

### Human

The user provides final artistic and product approval. Human review decides
whether motion feels natural, silhouettes and proportions read correctly,
overlaps look convincing, an artistic compromise is acceptable, and the
animation is visually ready to ship or proceed.

## Pre-Animation Asset Readiness Gate

Before rigging or animation begins, Codex must inspect the complete character
artwork and proposed motion to determine whether the available assets are
sufficient.

Animation should not proceed merely because each major body part has an image.

For every moving attachment, Codex must determine:

- moving hierarchy;
- intended pivot;
- motion envelope;
- required hidden underlap;
- foreground/background occlusion;
- whether a moving part must pass between back and front artwork layers;
- whether terminating outlines could become visible during motion;
- whether additional overlay, socket, mask, or split artwork is required.

Codex should reason about the represented physical structure first.

Examples:

- sleeve: sleeve back → forearm → sleeve front lip;
- collar: back collar → neck → front collar;
- hair: back hair → head → bangs/front hair;
- hand holding object: back fingers → object → front fingers;
- eyelids: face/eye base → eye → foreground eyelid as required.

Before animation implementation, Codex must provide an **Asset Readiness Report**
classifying each relevant asset as:

- `READY`
- `MISSING_REQUIRED`
- `NEEDS_REGISTRATION`
- `NEEDS_ART_EDIT`
- `OPTIONAL`

For every missing required asset, specify:

- filename;
- purpose;
- front/back layer relationship;
- expected canvas/registration;
- pivot/anchor relationship;
- required overlap region;
- whether it can be derived safely from existing artwork.

Do not begin full animation until all `MISSING_REQUIRED`, `NEEDS_REGISTRATION`,
and blocking `NEEDS_ART_EDIT` items are resolved or explicitly accepted by the
user as temporary limitations.

Codex owns this analysis and the identification of missing art pieces. The user
should not be expected to know every required overlay or source-art split
beforehand. MCP/tooling provides measurements and deterministic validation but
does not make subjective artistic decisions. Technical validity alone does not
establish visual readiness.

Where practical, Codex should provide registration guides and specifications for
any required new artwork, including canvas dimensions, pivots, placement,
layering, overlap and motion-clearance requirements.

Animation may proceed with a known limitation only when the user explicitly
accepts it as temporary. Document that limitation and the remaining art work;
temporary acceptance does not establish final artistic approval. This gate
precedes rigging/animation implementation and complements the full-motion
validation and human visual approval below. Preserve the source-art safety
requirements in sections 11 and 16 while preparing or testing candidates.

## Minimum Sufficient Decomposition

Do not minimize artwork pieces, sprites or layers at the expense of visual
plausibility. The correct decomposition is the smallest set of layers that
convincingly represents the intended physical relationship throughout the
complete animation. Asset count is not a success metric; visual plausibility
across the complete motion range is.

A moving joint may require additional front/back artwork when one part must
pass inside, behind, through or around another part. Examples, back to front:

- sleeve: sleeve/socket back → forearm → front cuff lip;
- boot: boot back → leg → boot front;
- collar: collar back → neck → collar front;
- hair: back hair → head → front hair/bangs;
- hand holding object: back fingers → object → front fingers.

If a simpler decomposition produces visible seams, flat intersections,
impossible occlusion, exposed terminating edges, repeated art/transform hacks,
or remains visually rejected after bounded corrections, Codex must reconsider
the artwork decomposition rather than force the simpler structure. Codex may
conclude that additional artwork is **REQUIRED** before animation continues.

Do not assume two pieces are better than three, three better than four, or fewer
nodes inherently preferable. Prefer fewer pieces only when the visual result
remains correct throughout the intended motion.

The Pre-Animation Asset Readiness Gate must determine the required decomposition
before final rig values and animation are frozen. Human visual rejection
overrides an earlier simpler decomposition when it cannot convincingly represent
the intended physical relationship.

## Foreground Lip Must Not Be a Full Ring

When a moving part passes through an opening, Codex must determine the physical
front/back relationship before rigging or painting around the problem. The
typical back-to-front structure is:

```text
rear/socket-back → moving inserted part → front lip / foreground overlap
```

This applies to sleeve/socket → forearm → front cuff lip, collar back → neck →
collar front, back fingers → object → front fingers, and back hair → head →
bangs/front hair.

A foreground lip must contain **only the near/front rim** that overlaps the
moving part, matching fabric edge/shading and any minimal side return required
for occlusion. The passage must remain open/transparent so the moving part can
visually pass through it. For sleeves/cuffs, the bottom/far inner line must be
**absent** from the foreground lip.

The foreground asset must not contain:

- the far/back/bottom inner rim or a back-side interior contour;
- a complete ellipse, hollow oval, ring or empty-circle/closed-tube appearance;
- the rear cavity bowl, socket depth or back-side interior shading.

These rear features belong to the socket-back layer, which may contain cavity
depth, the far wall and interior sleeve/socket shading. The rear asset must
**not duplicate the foreground/front lip**.

Codex must inspect the foreground asset **alone before animation testing**. If
it reads as a complete sleeve opening, full ring/oval, empty cuff or closed
tube, reject it immediately. It must read as a foreground overlap strip/lip,
not a complete sleeve by itself. Structural validity cannot override this
isolation rejection test.

Apply Minimum Sufficient Decomposition: there is no maximum asset count or
fixed piece/node count to preserve. Use the minimum pieces that represent the
physical relationship convincingly throughout the full motion; visual
plausibility, not asset count, is the success metric.

After one or two failed bounded corrections for the same defect, apply the
Decomposition Escalation Rule: stop repeated RGB, alpha, offset, transform,
masking or small paint patches and re-evaluate the physical/layer model.
Codex owns identifying and specifying missing socket backs, front lips,
collar/hair layers, finger splits, overlaps and hidden extensions before
animation is considered ready; the user must not have to discover them.

Keep structural and visual readiness separate under Visual Defect Override.
Human visual rejection is authoritative. A joint with a user-rejected seam,
impossible line, flat insertion, floating edge, duplicate contour, closed-tube
effect or unrealistic overlap must not be classified as `READY_VISUAL`, even
when technical checks pass.

## Decomposition Escalation Rule

Codex must not repeatedly patch a visually rejected construction indefinitely.
If one or two bounded corrections fail to resolve the same user-visible defect,
stop local tweaking and re-evaluate the physical/layer decomposition from first
principles. Ask:

- what physically exists behind the moving part;
- what physically exists in front of it;
- what part must move between those layers;
- whether the current artwork can represent that relationship;
- whether additional split artwork or layers are required.

Repeated transform, RGB, alpha, masking or offset corrections are evidence that
the decomposition itself may be wrong. Codex may increase artwork assets,
sprites, overlay layers or socket/back/front pieces when necessary for visual
plausibility. There is **no fixed maximum asset count**. Fewer pieces are
preferable only when they remain visually correct throughout the full motion.
Do not preserve a simpler decomposition merely because it was previously
accepted technically.

### Codex Owns Asset-Decomposition Design

The user may provide source artwork, but Codex owns determining whether it is
sufficiently decomposed for the intended animation. Proactively identify,
request and specify any additional artwork pieces needed before animation
proceeds. The user should not have to discover missing sleeve backs, cuff lips,
socket interiors, foreground overlays, hair layers, hand/finger splits or
similar pieces during playback.

Solve the represented physical relationship correctly rather than forcing the
available art into an unsuitable structure.

### Required Occlusion Stack

Before rigging or animating a moving attachment, Codex must explicitly state its
intended back-to-front layer stack. Examples:

```text
sleeve back/interior → forearm → front cuff lip
```

```text
collar back → neck → collar front
```

```text
back hair → head → bangs/front hair
```

If the physical stack is unclear or cannot be represented by the current
assets, animation remains blocked until the art decomposition is resolved or
the user explicitly accepts a temporary limitation.

### Efficient Visual Problem-Solving

For a persistent visual defect:

1. identify the user-visible defect;
2. test at most one or two small bounded corrections;
3. if the defect remains, stop patching;
4. re-evaluate the physical/layer decomposition;
5. compare alternative decompositions;
6. choose the minimum sufficient structure that is visually correct throughout
   the full motion;
7. specify missing art before further animation work;
8. only then resume implementation and validation, subject to the readiness gate.

Do not spend repeated cycles proving a structurally valid but visually rejected
construction.

### Human Visual Override

Human visual rejection remains authoritative. If the user says a joint,
overlap, seam or silhouette still looks wrong, Codex must not treat the same
decomposition as accepted solely because technical tests pass. The next action
must be a bounded visual correction or decomposition escalation if prior bounded
corrections failed.

## Visual Defect Override

Structural validity does not imply visual readiness. An asset may pass geometry,
registration, overlap/underlap coverage, motion-envelope, collision, hierarchy
and loop/reset checks and still be visually unacceptable.

Codex must actively inspect rendered output for visual artifacts and evaluate
and report **structural readiness** and **visual readiness** separately.
Technical validation supports visual review but does not replace it.

A visible seam, cutoff, terminating line, duplicate contour, shading
discontinuity, floating edge, unnatural overlap or other artifact that does not
correspond to the intended physical structure prevents the affected asset or
animated joint from being visually ready, even when technical checks pass.

A user-reported visual defect is authoritative evidence that the affected
result is not visually accepted. Human visual rejection overrides a prior Codex
`READY` classification for that issue. Codex must not dismiss the defect because
overlap measurements are sufficient, no geometric gap exists, the hierarchy is
valid, the animation technically loops or the asset is structurally usable.
Do not report an asset or animated joint as fully `READY` while a user-rejected
visual artifact remains visible.

When the user identifies a visual defect:

1. inspect the reported region across the full animation, not only the rest pose;
2. determine whether the artifact comes from source artwork, layering, masking,
   registration, transforms or animation;
3. classify the affected asset/state accordingly;
4. test a bounded correction, or apply the Decomposition Escalation Rule if prior
   bounded corrections failed;
5. present the corrected rendered result for human approval.

Where useful, distinguish:

- `READY_STRUCTURAL`
- `READY_VISUAL`
- `NEEDS_ART_EDIT`
- `NEEDS_REGISTRATION`
- `MISSING_REQUIRED`
- `OPTIONAL`

An asset may be `READY_STRUCTURAL + NEEDS_ART_EDIT` at the same time. For example,
a forearm may remain geometrically covered by a sleeve throughout the full
motion range yet show an unnatural dark cutoff/shading line under the sleeve.
That forearm is structurally valid but visually requires art editing.

In the readiness report above, unqualified `READY` requires both structural
readiness and human visual acceptance; otherwise report structural and visual
statuses separately. `READY_VISUAL` records human visual acceptance of the
reviewed asset/state and motion. Final visual acceptance belongs to the user.
Explicit temporary acceptance permits work under the readiness gate but does
not turn an unresolved visual defect into final visual readiness.

## Visual Registration Before Freezing Rig Values

Initial pivots, offsets and transforms are not authoritative merely because
they pass technical validation. Intentional initial pivot placement (section 10)
establishes provisional technical registration; freezing the accepted contract
requires visual approval.

For character assembly:

1. establish approximate technical registration;
2. inspect the complete assembled character;
3. review movement across the full intended animation range;
4. correct registration, overlap, layering or artwork as needed;
5. obtain human visual approval;
6. only then freeze pivots/transforms as the accepted contract.

A technically valid registration is not automatically a visually correct one.

## Full-Motion Validation

Never approve a joint or overlap based only on the rest pose. Validate at:

- rest;
- animation extrema;
- intermediate poses;
- loop boundaries where relevant;
- complete continuous playback.

Replacement art or transform corrections must remain visually connected
throughout motion, not merely at one sampled frame.

## 2D Joint Overlap / Underlap

For cutout character joints, use hidden overlap where appropriate:

- moving lower pieces may extend underneath foreground clothing;
- hidden proximal edges should generally have no visible terminating outline;
- a foreground sleeve, cuff or layer may conceal the moving attachment;
- sufficient underlap should cover the entire intended motion envelope.

Prefer the smallest construction that remains visually convincing throughout
the full motion, as defined by Minimum Sufficient Decomposition. Add required
front/back artwork and overlap sprites or nodes when graphical evidence shows
that the simpler construction cannot represent the physical relationship.

## Art vs Rig Responsibility

Prefer better source-art separation, proper hidden overlap, sensible pivots and
registration-compatible replacement assets over increasingly complicated rig
logic. The rig should not be expected to rescue fundamentally poor asset
preparation.

Conversely, do not redraw assets when a bounded transform or layering correction
clearly solves the visual problem. Preserve the source-art safety requirements
in sections 11 and 16 while testing candidates.

## Problem-Solving Workflow

For visual animation defects:

1. describe the user-visible defect;
2. inspect and measure current state;
3. identify plausible root causes;
4. test at most one or two bounded corrections for the same defect, then apply
   the Decomposition Escalation Rule if it remains;
5. evaluate candidates through the full motion;
6. reject solutions that introduce new problems;
7. implement the smallest robust solution;
8. validate technically;
9. request human visual approval.
