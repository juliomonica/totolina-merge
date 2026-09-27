# Totolina's Mystery Journey — Animation Guidelines

This document is the source of truth for animation work in Totolina's Mystery Journey.

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
