# Kitchen regression gate

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
- Gameplay input: one press-committed drop owned by the first valid finger index;
  1/2/4 fingers, repeated begins/drags, cancellation, GUI-consumed releases, no
  already-held secondary promotion, and restart/Play Again/scene-exit cleanup.
- Desktop clicks, synthetic duplicate input, actual engine mouse/touch emulation
  enabled in the test process, and GUI Push/Restart while gameplay touch is held.

Touch tests inject indexed events through Godot's viewport/GUI input routing;
emulation tests also use `Input.parse_input_event`. They preserve the existing
press-to-drop behavior (no post-press drag aiming) and do not represent physical
iPhone testing. Emulation flags are changed only within isolated test processes.

`--graphical` also captures the three effects and late results with debug
collision circles, sparse collection states and sizing at 390×844, 405×720,
540×960. This is desktop rendering, not physical Android/iOS testing.

Tests write only explicit temporary discovery files. The audit sandbox delegates
to the production resolver and is never referenced by production scenes.

## Developer-only spawn panel

Approved Egg/Milk/Cream integration:
`--suite merge-flavor --graphical` checks actual Spawn Pair merges, exact-once
rewards, interruption/teardown, edge fitting and all three portrait sizes.
`--suite animation-lab --graphical` checks the retained review controls and
approved shared timeline output. Both are included in the full suite.
See `docs/MERGE_EFFECT_LAB.md` for timing/source ownership.

Run gameplay from the editor or a **debug** development export. Open **Debug spawn +**
below the upper-right HUD; tap it again to collapse the panel. The selector uses
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

Release safety: PhysicsSandbox asks native `OS.is_debug_build()` before creating
any panel and again at every spawn/clear entry point. The panel also rejects a
non-debug engine if instantiated independently. There is no saved toggle or scene
node to accidentally leave enabled. Scripts may be included in the export pack,
but the UI is never instantiated and actions are inert in a release build.

The focused test covers all nine single spawns, the three flavor-effect pairs,
Fancy Cake's non-merging pair, state/save isolation, clear/pending-merge cleanup,
mouse and indexed-touch UI routing, and 12 collision-debug captures at the three
portrait sizes. `debug_spawn_release_sandbox.gd` is a test-only override returning
false from the build probe to exercise the disabled path; this is **not** a real
release-export test. Validate a release build on-device before distribution.
