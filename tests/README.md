# Totolina's Mystery Journey — Kitchen regression gate

Use the installed project-compatible Godot version. No plugins or new dependencies.
The runner uses Python's standard library and native Godot SceneTree tests.

```sh
python3 -B tests/test_merge_runner.py
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --graphical
```

Focused guarded-neighbour validation: use `--suite sponge`.
Focused gameplay touch validation: use `--suite touch --graphical`.
Focused progressive spawn validation: use `--suite spawn --graphical`.
Focused nine-slot discovery validation: use `--suite collection --graphical`.
Focused developer-spawn validation: use `--suite debug-spawn --graphical`.
Focused production machine + approved machine lab: use `--suite machine --graphical`.
Focused Kitchen gameplay controls: use `--suite controls --graphical`.
Focused authoritative creation/discovery flow: use `--suite creation-result --graphical`.
The runner copies the current working tree into a temporary directory and isolates
all discovery saves and imports. It reports the artifact directory and retains logs.
It fails on parser/resource/runtime errors even when the engine returns exit 0.

## Current locked coverage

- Nine board creations; eight physical same-item recipes; Fancy Cake final.
- Three repetitions of all eight actual contact merges in one run, plus a
  continuous ladder carrying each result to Fancy Cake (one extra matching
  input supplied by the fixture at each step).
- Exact source consumption, result creation, score, +12 Push and discovery;
  post-merge physics frames, paced pairs, invalid different-item/final contacts.
- Guarded neighbour wake after removing a sleeping piece's support.
- Three approved flavor animations: exact bubble/numbered-pose textures, no
  physics nodes, one shared component per merge, cleanup, viewport bounds and
  ordinary merge magic when no flavor animation is selected.
- Run-based spawn stages: Wheat-only → Wheat75/Flour25 → Wheat60/Flour30/Mix10;
  actual contact-merge unlocks before settling, repeated results, later creations
  excluded, no DROP/NEXT rerolls, one seeded draw per selection, deterministic
  replay, restart/Play Again/new-scene reset independent of persistent discoveries.
- Nine fixed collection slots, sparse mystery states, filtering former semantic
  discoveries, preservation of unrelated settings, restart and Play Again.
  Exact sparse cases include Cake Mix only (slot 3), Wheat + Cake Batter
  (slots 1 and 4), and all nine. Slot identities never move on discovery.
  Fancy Cake-only and full persistent saves still start new runs Wheat-only;
  restart/Play Again do not write or erase that saved discovery state.
- Current cumulative sizing, generic validation, unchanged 2.18 concentric art.
- Main Menu, gameplay, Recipe Collection, localization, danger/grace and Push.
- Gameplay input: one press-accepted machine cycle owned by the first valid finger index;
  1/2/4 fingers, repeated begins/drags, cancellation, GUI-consumed releases, no
  already-held secondary promotion, and restart/Play Again/scene-exit cleanup.
- Desktop clicks, synthetic duplicate input, actual engine mouse/touch emulation
  enabled in the test process, and GUI Push/Restart while gameplay touch is held.

Touch tests inject indexed events through Godot's viewport/GUI input routing;
emulation tests also use `Input.parse_input_event`. They preserve the existing
press-to-drop behavior (0.20s shared contact release, no post-press drag aiming)
and do not represent physical
iPhone testing. Emulation flags are changed only within isolated test processes.

`--graphical` also captures the three effects and late results with debug
collision circles, sparse collection states and sizing at 390×844, 405×720,
540×960. This is desktop rendering, not physical Android/iOS testing.

Tests write only explicit temporary discovery files. The audit sandbox delegates
to the production resolver and is never referenced by production scenes.

## Successful creation → every discovery consumer

`creation_result_validation.gd` follows a real indexed-touch Wheat drop and all
eight actual contact merges through one continuous run. As soon as the physical
result exists, it verifies exact-once score/Push, semantic discovery, the fixed
nine-slot bottom strip, the on-disk save, a freshly opened Recipe Collection, and
the unchanged run spawn stages (100% Wheat → 75/25 → 60/30/10). It does not call
the resolver or reward/discovery hooks to simulate success. Existing test-only
observers delegate to production behavior.

Repeated results cannot rediscover an ID or rewrite its unchanged save. Restart,
Play Again and a newly loaded gameplay scene preserve all discoveries but reset
the run to Wheat-only. The gate also removes the optional presentation node and
requires a real merge to retain all authoritative outcomes. Graphical runs check
390×844, 405×720 and 540×960, capture the newly earned strip/Recipe Collection,
and exercise horizontal collection touch scrolling. Saves remain isolated;
these synthetic desktop checks do not replace physical-device testing.

Both headless and graphical passes are included in the full suite. For a focused
run, add `--suite creation-result` (and optionally `--graphical`) to the runner.

## Production machine integration

`machine_gameplay_validation.gd` verifies the real 0.20s release / 0.62s input
cycle, at-most-once body creation, current/next/RNG handoff including long ticks,
no fake falling item, depth order, live score, preview scales, press/reaction
priority, native physics-step playback and lifecycle cancellation before/after
release. Native scene save/reopen checks edit feeder/shutter/token/cat/eyes/arms/
previews/nozzle properties, replay every action and confirm reset preserves the
saved transforms. Mask Control offsets survive resizing at all three portrait
widths. These are Inspector-equivalent serialization tests, not automated editor
clicks. Portrait captures show idle, release, feeder, reaction and results;
rendered depth probes cover the inner floor and front lip without covering rails.
They also check shared front-arm/shoulder and eye/ear proportions, full-bleed
rear/front bounds, unchanged floor/nozzle anchors, and a logical safe-inset fixture.
Collection portrait checks now require the approved larger shared scale with
nine fixed canonical slots on a clipped track, rather than nine shrunken icons
all visible at once. Mask position/depth and sparse discovery remain covered;
native touch/wheel/pan scrolling reaches both endpoints without dropping pieces.
Existing touch tests advance the accepted machine cycle before inspecting the
body; they still route actual indexed events through GUI/unhandled input.
`machine_interaction_lab_validation.gd` retains the independently approved lab
timeline/pose/render coverage. Both are in the full suite; no production test
loads the lab as gameplay. See `docs/MACHINE_INTERACTION_LAB.md` for integration
ownership, nozzle release-height change and temporary collection presentation.

## Developer-only spawn panel

Approved Egg/Milk/Cream integration:
`--suite merge-flavor --graphical` checks actual Spawn Pair merges, exact-once
rewards, interruption/teardown, edge fitting and all three portrait sizes.
`--suite animation-lab --graphical` checks the retained review controls and
approved shared timeline output. Both are included in the full suite.
See `docs/MERGE_EFFECT_LAB.md` for timing/source ownership.

Run gameplay from the editor or an export explicitly tagged **dev_tools**. Open **Debug spawn +**
below the new machine header/danger line; tap it again to collapse the panel. The selector uses
the nine current CreationDefinitions in collection order, with existing localized
creation names. No new player-facing strings or permanent settings are involved.

- **Spawn One:** places the selected real physics piece near the chamber's top,
  using its current effective radius, texture, collider and mass.
- **Spawn Pair:** places two real matching pieces at near-contact horizontal
  offsets. Oversized pairs use a slightly diagonal vertical arrangement if they
  cannot fit side by side. Existing bodies are avoided with a bounded search.
  If no safe space exists, nothing is spawned; clear the board first.
- **Clear Board:** cancels pending merges, removes pieces and merge effects, and
  clears transient danger in a live run. It preserves score, Push charge, highest
  creation, spawn stage, current DROP/NEXT, RNG and all saved data. It does not
  revive a game-over run; use Play Again. Spawning is disabled during game over.

Debug creation itself never draws RNG, advances previews/unlocks, grants score or
Push, or registers discovery. **Subsequent real physical merges do earn their
normal rewards and persistent discoveries.** Use an isolated test save if those
discoveries should not affect your development profile. The permanent test runner
isolates saves automatically. Enable Godot's Visible Collision Shapes/debug
collision display to compare actual collider/art sizes.

Export safety: PhysicsSandbox and the panel require `OS.has_feature("editor")`
**or** `OS.has_feature("dev_tools")` at creation/action entry points. A normal
debug export and a normal release export both omit UI and reject actions. A
deliberately tagged development export enables tools even if exported in release
mode. No saved setting enables them.

Existing Android/iOS presets/signing are untouched. In **Project → Export**,
duplicate the intended platform preset for development, select the duplicate,
open **Features → Custom Features**, and add `dev_tools` (comma-separated if
other features exist). Keep it OUT of production presets. Remove the tag and
re-export for an ordinary build. Merely checking “Export With Debug” does not
enable this panel. Actual exported-device feature checks remain a manual test.

The selector is a touch-aware Button opening a native PopupPanel with nine
44px-high creation Buttons; no global touch-to-mouse emulation is enabled.
Tests use embedded popups (the mobile path), verify real indexed selection,
and confirm no extra gameplay drops. Headless has a synthetic 64px screen that
clips the popup even when embedded: actual popup selection is explicitly skipped
there and exercised by the graphical suite at all three portrait sizes.

The focused test covers all nine single spawns, the three flavor-effect pairs,
Fancy Cake's non-merging pair, state/save isolation, clear/pending-merge cleanup,
mouse and indexed-touch UI routing, and 12 collision-debug captures at the three
portrait sizes. `debug_spawn_release_sandbox.gd` is a test-only override returning
false from the feature probe to exercise the disabled path, alongside the
editor/dev_tools truth table; this is **not** a real exported-binary test.
Validate both tagged development and untagged builds on-device before distribution.

Production collection tests additionally inject horizontal touch drags (including
starting on edge masks), wheel and pan gestures at 390×844, 405×720 and 540×960.
They check fixed canonical slots, mystery/real artwork, endpoint reachability,
hidden scrollbar, no vertical motion, and unchanged drop/RNG state. The native
ScrollContainer keeps desktop scrolling; a local touch adapter updates its
scroll position because this project's Godot 4.7 input has mouse emulation off.
There is no custom inertia or snap system. Machine tests also render a body-layer
depth probe proving lower-floor overlap while side rails remain foreground.

## Kitchen gameplay-control integration

Run the dedicated controls gate in the same isolated-copy workflow:

```sh
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --suite controls
python3 -B tests/run_kitchen_regressions.py --godot /Applications/Godot.app/Contents/MacOS/Godot --suite controls --graphical
```

`kitchen_controls_validation.gd` exercises the scene-authored Push, radial
Restart and Exit Run controls through Godot mouse/indexed-touch routing:

- Push normal/pressed textures, valid release exactly once, directional impulse,
  cancellation outside the target and multi-finger ownership without extra drops.
- The unchanged one-second Restart hold, continuous clockwise TextureProgressBar,
  early-release cancellation/reset, complete hold once and real process-clock
  completion. The radial textures replace the horizontal progress presentation.
- Exit Run pauses gameplay and blocks background drops, Push, Restart and
  collection input. Resume preserves score, RNG, pieces and accepted machine
  transactions; deferred merge pairs remain paused and continue once on resume.
- Confirm returns to Main Menu through existing scene navigation, unpauses the
  tree and does not terminate the application.
- Portrait layout and safe-inset fixtures at 390×844, 405×720 and 540×960, with
  idle/hold/modal captures when graphical rendering is enabled.
- Footer join captures and contrasting-backdrop pixel probes verify frame/background
  edge contact and coverage to the screen bottom, including simulated safe insets.
  Footer sprites retain uniform scale; Exit retains its 52px target above Totolina.

The focused suite is included in the full regression gate. Keep the separate
touch, collection, machine and merge-effect lab gates: control integration must
not change their gameplay/timing behavior. Graphical captures are desktop checks,
not physical iPhone/Android testing. Test on-device finger coverage, safe areas,
scrolling and press cancellation before release. Supplied controls/modal art
contains baked English lettering, including **EXIT TO MENU** for the Main Menu
action. Tooltips do not translate those image pixels; the extra destination
caption is intentionally absent.
See `docs/PRESENTATION_TUNING_GUIDE.md` for the editable scene/node paths.

The machine graphical gate also renders real resting bubbles at both wall/floor
corners. An opaque-pixel comparison with/without foreground artwork detects
overwide masks, while the existing body-layer probes verify that vertical rails
still occlude correctly. The physical floor and artwork calibration stay fixed.
