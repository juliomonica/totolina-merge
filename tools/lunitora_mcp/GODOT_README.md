# Lunitora Godot Animation MCP v0.5

This editor bridge exposes the three existing metadata tools, `godot_ping`,
`godot_get_editor_state`, and `godot_inspect_scene`, plus six fixed lab operations:
`godot_create_rig_lab`, `godot_create_rig_lab_animation`,
`godot_create_tolina_rig_lab`, `godot_create_tolina_lab_blink`,
`godot_create_rig_test_cat_deformation_lab`, and `godot_create_rig_test_cat_deformation_demo`.
All nine accept exactly `{}`; extra fields are rejected. Bridge and editor-plugin versions are **0.5.0**; the authenticated
transport protocol remains **1**. The Codex-owned Python stdio server listens on **127.0.0.1:43128**;
Godot's `WebSocketPeer` connects from the enabled editor plugin. Photoshop's
server, implementation, and **43127** port are separate. The Godot and Photoshop
profiles share the existing `tools/operator_launcher` implementation.

The three inspection operations retain their read-only behavior. The rig operation
creates the seven-node scaffold; the separate animation operation requires that
unchanged fixture and adds one synthetic clip in one native editor action. Neither
saves the lab, changes production scenes/artwork, or starts animation playback.
Inspection reads the current edited scene through public editor APIs and does
not instantiate production scenes or inspect arbitrary script properties.

The separate Tolina character lab adds the reviewed real-art cutout fixture and
one bounded blink; the existing synthetic lab and its contracts are preserved.
All six writers share the same session ledger, settlement rules, busy fence,
post-action fault latch and no-retry policy. See [Tolina lab v0.4](#tolina-lab-v04).

## Rig test cat deformation lab v0.5

Technical milestone acceptance is complete on Godot
`4.7.2-stable (official)`, bridge/plugin `0.5.0`, protocol `1`. Controlled live
history/persistence/replay and user visual review passed. This proves the bounded
MCP tooling capability, not production-ready artwork or physical-device behavior.

The two new parameterless tools operate only in
`res://addons/lunitora_godot/labs/rig_test_cat_deformation_lab.tscn`, with the native,
script-free `RigTestCatDeformationLab` Node2D root. Admission is semantic; normal
Godot UID metadata is allowed. Production scene paths are refused.

`godot_create_rig_test_cat_deformation_lab({})` adds exactly 19 owned native,
script-free nodes in three independent proof stations:

```text
RigTestCatRig (Node2D)
├── TailStation (Node2D)
│   ├── TailMesh (Polygon2D)
│   └── TailSkeleton (Skeleton2D)
│       └── TailRoot (Bone2D)
│           └── TailMid1 (Bone2D)
│               └── TailMid2 (Bone2D)
│                   └── TailTip (Bone2D)
├── ArmStation (Node2D)
│   └── Shoulder (Node2D)
│       └── UpperArm (Sprite2D)
│           └── Elbow (Node2D)
│               └── LowerArmPaw (Sprite2D)
├── BodyStation (Node2D)
│   ├── Torso (Sprite2D)
│   ├── HeadPivot (Node2D)
│   │   └── Head (Sprite2D)
│   └── ScarfForeground (Sprite2D)
└── AnimationPlayer
```

This fixture is not a complete character assembly. Its reviewed tooling-only
specification is `addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json`,
externally pinned by `deformation_rig.gd` to SHA-256
`459b16ecf4367ef7c9254961a223a0c7ac0d56e79bc9bbc63b5b89e47b700571`.
All 24 pinned PNG/import pairs live under `addons/lunitora_godot/test_assets/rig_test_cat/`.
The original relocation preserved PNG bytes/dimensions, import settings and UIDs; only native
path-derived `path`, `source_file` and `dest_files` changed. The old asset directory
is removed. The bounded arm-only revision replaces the four upper/lower left/right
arm inputs with approved 1254x1254 exports and pins their current import metadata.
Torso pixels/settings are unchanged; only its already-current import hash/UID is
repinned. The unchanged addon exclusion removes the complete fixture from
normal Android/iOS resource packages. Generated scenes use six immutable cached
external Texture2Ds and have no JSON runtime dependency.

The tail has 561 explicit pixel-space vertices/UVs, 1,024 triangles, 96 perimeter
vertices followed by 465 interior vertices, and four explicit normalized weight
arrays with at most two influences. No triangulation or weighting is inferred.
The four zero-rotation rest origins are `(160,1280)`, `(450,-90)`, `(180,-400)`,
`(-50,-370)`; stable bone angles and disabled automatic length calculation survive
native save/reopen. The arm uses only `UpperArm` and `LowerArmPaw` Sprite2Ds under
the unchanged Shoulder/Elbow hierarchy. The fixture instantiates the left pair;
the right pair remains approved inventory, not an added station. ArmStation scale
stays `(0.5,0.5)`. UpperArm position/rotation stay zero, scale is `(0.4,0.4)` and
offset is `(-810,-320)`. Elbow position is `(-385,680)` in UpperArm's source space,
with unchanged rest rotation `0.87026`. LowerArmPaw position is zero, scale is one,
offset is `(-860,-240)`, fixed rotation is `-0.87026` and z-index is `-1` so the
orange forearm moves behind the cream sleeve. The existing Shoulder/Elbow tracks
and all timing/easing are unchanged. No elbow sleeve-overlap node or candidate
head/neck or independently generated scarf texture is used; the body station isolates HeadPivot motion.
HeadPivot rests at `(0,306)` with unchanged scale `(0.8,0.8)` and head offset
`(-627,-1145)`. Absolute head Y keys `[306,300,294,300,306]` preserve the relative
bob `[0,-6,-12,-6,0]`. Source alpha contours at threshold `128` overlap across the
local collar band `[-210,210]` by at least `16.2` pixels at rest and `4.2` at the
highest bob. A static `ScarfForeground` Sprite2D covers the lower neck using a
288x147 transparent extraction of the approved torso pixels. It is uncentered
with offset `(-139,238)`, position `(0,0)`, rotation `0`, scale `(1,1)`, z-index `1`
and linear filtering. The source rectangle is `(422,238,288,147)`; the original
36-point recipe is preserved in archived conversion evidence, not maintained
test machinery or the runtime contract. Interior RGBA is exact, original alpha is preserved, and outside
alpha is zero. Source RGB beneath zero alpha is retained; this texture alone uses
`process/fix_alpha_border=false` to avoid importer border-color repair. The owned,
script-free sprite uses its own immutable cached texture and has no animation track.
Head transforms/bob and `head_full` artwork are unchanged; no neck node is added.
Native Polygon AA versus the baked mask has a disclosed boundary-only rasterization
difference; see the extraction evidence below. Final controlled live visual review
is accepted for the technical milestone; future production art quality is separate.

The internal `weighted_mesh_2d.gd` accepts only explicit trusted geometry,
UVs, triangle indices, relative bone paths and weights. Bounds are 1–32 bones,
2,048 vertices, 4,096 triangles and four influences. Malformed/nonfinite geometry,
degenerate triangles, invalid bindings, mismatched arrays and unnormalized or
out-of-range weights are rejected, never repaired. Authored sums equal one;
`1e-6` is reserved for native readback. It owns no transport, admission, history,
saving or global state and is not exposed as a generic MCP geometry API.

`godot_create_rig_test_cat_deformation_demo({})` requires the unchanged fixture
at rest and a pristine, detached/settled AnimationPlayer. It adds one global
AnimationLibrary containing only `deformation_demo`: 2 seconds, step `0.125`,
`LOOP_NONE`, seven enabled continuous value tracks and 35 keys at
`[0,0.5,1,1.5,2]`. Four tail rotations use amplitudes 2°/4°/6°/6°;
shoulder, elbow and head Y use the reviewed values. Six rotation tracks use
linear-angle interpolation; head Y uses linear interpolation; every transition
is `-2.0` (native quadratic ease-in-out). Angular oracle comparisons wrap angles.
First/final keys restore exact rest. There is no RESET, autoplay, assignment,
playback, seek, queue, marker or extra resource.

Each write creates one native action: `Lunitora: Create Rig Test Cat Deformation Rig`
or `Lunitora: Create Rig Test Cat Deformation Demo`. Detached preparation precedes
final admission. Rig Undo removes the subtree; Redo restores the same retained
nodes and every owner. Native bound library arguments retain the same animation
resources for Redo; no custom lifetime cache or resource node-reference API is used.
Neither writer saves scenes/resources or mutates/reimports/takes over texture paths.

Before any Skeleton2D getter can flush setup, admission checks
`bone_setup_changed`. Only the exact generated native/script-free TailMesh receiver,
its verified custom `Polygon2D::_skeleton_bone_setup_changed` callable and flags
`0` are admitted. Unknown observers return `LAB_SKELETON_EDITOR_BUSY` before an
action. Writer admission also rejects every TailMesh and ScarfForeground `draw` observer, including
the native Polygon2D editor while attached: a queued redraw can otherwise invoke
an observer after synchronous post-verification and leave a changed bone after
Undo. Deselect the mesh/detach the relevant editor and allow normal frames to
settle; admission never does this automatically. Structural validation still
works during native mesh/bone selection. Selection/Inspector changes invalidate
the shared quiet-frame barrier; a deferred callable can survive disconnection,
so an empty connection list alone is insufficient. Later normal observations
and exact rest-state validation must succeed before a fresh write. Callbacks are
never disconnected or suppressed by the writer. AnimationPlayer admission
retains the Godot **4.7.2** detached/settled rule; unknown relevant observers remain
a conservative lab-only restriction. Strict stopped/unassigned/rest replay applies
while these controlled conditions remain in place; attaching the animation editor
between Undo and Redo can invoke normal Godot editor assignment/seek behavior.

All six operations share the non-evicting 128-ID editor-session ledger, correlation,
ordered read settlement, reconnect/Python-restart protection, re-entry/committing
guards and fault latch. Final validation → action registration → commit →
post-verification → response finalization is synchronous. Build errors are strictly
pre-action; uncertain post-action state returns `WRITE_OUTCOME_UNKNOWN` and blocks
every writer for the session. Never automatically retry a write.

**VERIFIED:** the user accepted the controlled live tail/arm/head/scarf visual
result and final replay for this technical milestone. Current arm artwork is
sufficient to validate two-piece hierarchy, joint inheritance and tooling.
Better joint-ready production arm artwork remains a future art-quality
improvement; this fixed-fixture proof does not approve arbitrary rigs or final
production art. New production artwork/presentation remains **REQUIRES USER TEST**
and human visual review. Executable iOS/Xcode/device behavior remains
**REQUIRES MAC/iOS**; executable Android behavior remains **REQUIRES ANDROID DEVICE**.
No IK, AnimationTree, physics, facial work, production integration or generic writer
has been added. The distributed deformation lab remains an empty native root.

The intentionally distributed writer prerequisite is the exact captured
**120-byte empty native seed**, SHA-256
`1645fa0ad54b5f435e3b8e4a94d1e1baa1f00a9d01a44831687a904527efbb4d`,
scene UID `uid://dkuplpgst2o17`, root unique ID `963220967`:

```ini
[gd_scene format=3 uid="uid://dkuplpgst2o17"]

[node name="RigTestCatDeformationLab" type="Node2D" unique_id=963220967]
```

It has zero children, scripts or resources, UTF-8/ASCII without BOM, LF line
endings and one final LF. After the accepted manual Save/Reopen proof, only this
lab was restored byte-for-byte from its pre-writer capture. The populated
71,955-byte acceptance scene is archived evidence, not distributed content.
No UID was regenerated. The earlier pre-editor 74-byte seed was historical;
it is not the final distribution baseline.

The existing 111-byte synthetic lab and 117-byte Tolina lab remain byte-identical.

### Historical automated validation - 2026-10-01

The initial v0.5 automated validation used Godot
`4.7.2.stable.official.ed1daf0bf`; installed Android/Windows templates are
`4.7.2.stable`. The executable iOS template is absent. Tests use disposable
projects, never the real checkout's writers.

| Gate | VERIFIED evidence |
| --- | --- |
| Godot protocol/tools and export-control units | 206 tests. |
| Existing native public transport/synthetic/Tolina writers | 52 tests. |
| New deformation public writers | 25 headless/graphical cases, including observer rejection, queued-callback settlement, replay, timeout, lost reply, reload, save points and history disposal. |
| Native GDScript / weighted primitive | 1,101 existing checks plus 153 bounded-mesh checks. |
| CPU/GPU oracle | 201 geometry poses and 86 graphical comparisons on Windows Mobile/D3D12; no inverted/collapsed triangles, exact rest return. |
| Mobile resource exports | Four primary packs plus two JSON-removal controls; 14 native runs / 14,108 checks. |
| Kitchen | Two runner tests; 25 suites / 11,044 checks, including 12 graphical suites. |
| Photoshop | 171 Python tests, 165 UXP checks and four JS syntax checks. |
| Launcher | 82 checks; existing art/dev and Godot commands preserved. |

Native proof exposed the queued draw-observer mutation described above; the
writer now refuses that state before action creation. A plugin-reload readiness
race was corrected only in bounded test read polling; writer retry behavior is
unchanged. The 25-case batch passed 24 cases; the affected case and two additional
lifecycle/session cases then passed, verifying all 25 distinct cases.

Across sampled poses, triangle-area ratios are `0.649071–1.363323`, edge-length
ratios `0.708133–1.319839`, and rest error is zero. GPU/CPU pixel differences
are at most `6/255` with maximum mean `0.004375/255`; wrapped native easing error
is at most `3.782e-7` radians. All five cached texture states and all 46 fixture
source/import files remain unchanged. These bounds prove this fixed fixture,
not artistic quality or arbitrary rigs. At that stage real-checkout v0.5 writes
and executable/device exports were **NOT EXECUTED**. Later controlled live
technical/visual acceptance is complete, as recorded below; physical-device
validation remains open.

### Arm-only art revision - 2026-10-02

The approved two-piece arm replacement and bounded pivot correction used spec
`c93c92a9a21b6bb52a424297fef834000c377e2da85002da3201a0aa05c91081`;
all 19 nodes remained native/script-free. Missing legacy
`head_full` and `cape` PNG/import pairs were recovered byte-for-byte from the
previous approved disposable fixture, not replaced with candidate artwork.
Tail geometry, bones, weights, animation data and every non-arm node are deeply
equal to the captured pre-revision spec. Shared writer/safety code is byte-identical.

| Targeted Gate | VERIFIED |
| --- | --- |
| Deformation contract/transport and export-control units | 33 + 13 tests passed. |
| Native public-writer lifecycle/safety | 26 cases: 15 headless + 11 graphical; zero failures/errors/skips and strict clean logs. Native Undo/Redo, Save/Reopen, fixed lower rotation and nonrest rejection passed. |
| Rendered two-piece arm | 29 captures: elbow 0/5/10/15/20 degrees, original combined timeline keys, and 390x844 / 405x720 / 540x960; opaque joint and connected silhouette in every capture. Normal/closeup/mobile captures inspected: no visible gap, doubled sleeve contour or detached joint. |
| Actual native articulation | 65 timeline samples versus independent CPU global transforms; maximum origin error 0.0000337523 px and basis error 0.0000000394361. |
| Retained tail/head/scarf GPU regression | 201 geometry poses + 86 CPU/GPU comparisons passed; unchanged head/scarf contract and cached textures. Full combined first/final captures and arm rest captures are pixel-identical. |
| Mobile resource packages | Four primary packs + two JSON-removal controls; six native package-verification runs / 13,130 checks passed. Normal addon exclusion and compiled authored scene without tooling JSON verified. This is not device/executable export validation. |
| Source preservation | All 56 current PNG/import files unchanged during writer/render operations, including the 46 pinned inputs and ten unused candidate files. Export validation also preserved 229 production inputs. |

Only disposable projects ran the public writers and native save/history commands;
the live editor was not manipulated. The checkout's empty UID-normalized lab
remains 120 bytes, SHA-256
`1645fa0ad54b5f435e3b8e4a94d1e1baa1f00a9d01a44831687a904527efbb4d`.
No source PNG was edited, no overlap node or new head/neck/scarf layer was added,
and no stage/commit/merge/tag/push operation was performed. Android/iOS hardware
behavior and final controlled live acceptance are not established by these tests.

### Exact scarf asset extraction - 2026-10-02

The accepted Polygon foreground is replaced with the Sprite described above,
without artistic regeneration, resampling or color changes. Its one-time
deterministic recipe, extraction and frozen-reference A/B machinery were removed
after acceptance; the pinned PNG and ongoing native/GPU/export regression checks
are the maintained contract. Historical conversion evidence is archived outside
the checkout. The source was
only `rig_test_cat_torso.png`, SHA-256
`4c38f6ff82ccaf9774a50613febbbf7004feb028e3698272126a5454d396b949`.
The extracted PNG is SHA-256
`b76534ce925d736de66ad5d74ee163780968a3c63a3a5c8af02e7dd993aff4d3`;
its import file is SHA-256
`cb6b770b4ef34f80bb7a0a23e89977e4383c9104d9266c98ded3963a4afc485d`.
Native and independent CPU membership checks confirm 22,471 unchanged interior
RGBA pixels, unchanged crop RGB, zero outside alpha, and original alpha values
252/253/254. No unrelated source artwork is edited.

The frozen approved Polygon scene/spec are compared against the PNG in 35 native
Mobile/D3D12 A/B pairs: Y=306/300/294 plus 305.625/303/297/294.375, at normal and
closeup scale and all three phone sizes. This is **bounded raster equivalence,
not pixel identity**: zero changed pixels outside a two-rendered-pixel boundary
band; protected face pixels unchanged; all neck-coverage checks pass. Boundary
RGB delta reaches 183/255 at a few one-pixel neckline coverage changes; at most
56 pixels per pair exceed 4/255 and boundary mean is at most 1.456552/255.
Full-body alpha delta is at most 2/255. Isolated torso on/off RGBA/alpha delta is
at most 3/255, matching the approved Polygon and showing no extra opacity halo.
Normal/closeup/mobile captures were inspected: neck inserted, jaw/whiskers clear,
no gap, duplicated cape/scarf pixels, or new visible seam. The initial 128-channel
guard failed honestly and is retained in archived evidence; explicit reviewed
rasterization acceptance requires the exact source checks, zero outside-band
change, unchanged protected region, covered neck, <=64 pixels over 4/255 and
boundary mean <=2/255. Arbitrary scales/transforms are not covered by this proof.

| Targeted Gate | VERIFIED |
| --- | --- |
| Contract/transport and export-control units | 33 + 13 tests passed. |
| Native writer/history/persistence/safety | Fresh full 26-case batch: 11 graphical + 15 headless, no failures/errors/skips, strict clean logs. Native Undo/Redo and Save/Reopen pass with the distinct sixth scarf texture; no automatic save, assignment, playback or seek. Approved JSON numeric registration passes; six valid-bounds scarf texture/pivot/z/position/rotation/scale mutations reject. |
| Frozen Polygon versus extracted PNG | 35 A/B pairs pass explicit reviewed-raster criteria and source-byte checks; native and independent CPU audits agree. The retained raw 128-channel gate fails, and pixel identity is not claimed. |
| Fresh authored Sprite rendering | 19 nodes; 86 tail CPU/GPU comparisons and 201 geometry poses pass, unchanged max difference 6/255. Head bob error zero; protected face/neck checks pass; isolated torso difference <=3/255. Actual normal/closeup/mobile captures inspected. |
| Retained arm and rest return | 65 independent global-transform samples; 29 two-piece arm captures including mobile. No holes or doubled contours; exact rest transforms and pixel-identical rest captures. |
| Compiled resource packages | Four primary Android/iOS packs plus two JSON-removal controls; six native checks / 13,036 assertions. Six external textures and compiled 19-node rig/demo load without tooling JSON. Normal addon exclusion remains intact; not executable/device validation. |
| Preservation | All 56 current PNG/import files unchanged during writer/GPU operations; all 24 pinned pairs and 229 production inputs unchanged during exports. Compared with pre-extraction, only the requested scarf PNG/import changed; shared coordinator, transport, animation writer, weighted primitive and empty 120-byte lab remain byte-identical. |

The fresh native-authored scene is 71,953 bytes, SHA-256
`2504b5a148f0752a0a49658eea7febcfb16f6bb26bde64797114c1926283909f`.
The live editor was not manipulated. No candidate head/neck or overlap node was
integrated, and no stage/commit/merge/tag/push operation was performed. Final
controlled live acceptance and hardware/executable validation remain separate.

### Bounded scarf cleanup - 2026-10-02

The accepted runtime result and spec digest are unchanged. One-off extraction
and old-Polygon A/B tools have no current-fixture callers and are not retained as
an asset-generation framework. Removed from `tests/godot_mcp/`:
`scarf_foreground_extraction_v1.json`, `extract_scarf_foreground.gd`, its `.uid`,
`extract_scarf_foreground.py`, `scarf_extraction_validation.gd`, its `.uid`, and
`run_scarf_extraction_validation.py`.

Only four confirmed unused candidate PNG/import pairs were removed:
`body/rig_test_cat_head_main.png`, `body/rig_test_cat_neck_under_scarf.png`,
`arms/rig_test_cat_arm_elbow_sleeve_overlap_l.png` and
`arms/rig_test_cat_arm_elbow_sleeve_overlap_r.png`. Their only file/UID references
were their own import sidecars. The negative test excluding candidate IDs remains.
No superseded independently generated scarf remained in the checkout: its path
already holds the accepted extracted PNG. Historical task-local proof artifacts
remain outside the checkout, not part of maintained runtime/test machinery.

All 24 approved fixture PNG/import pairs (48 files), including the accepted scarf,
original `head_full`, torso and four revised arm inputs, remain pinned and intact.
Runtime/spec/Sprite registration/resource-identity, writer/native history and
persistence, current-fixture GPU and export-package coverage remain unchanged.

Post-cleanup validation passed:

| Targeted Gate | VERIFIED |
| --- | --- |
| Deformation and export-control units | 46/46 passed: 33 deformation + 13 export controls. |
| Native writer/history/persistence/safety | Fresh full 26/26 passed: 11 graphical + 15 headless, no failures/errors/skips; strict log guards unchanged. Undo/Redo, Save/Reopen, resource identity, registration and no-auto-save behavior remain covered. All disposable child processes completed; the live editor was not manipulated. |
| Fresh authored rendering | 86 tail CPU/GPU comparisons, 201 geometry poses, 65 arm samples, 29 arm captures and 16 head/scarf captures passed. All 287 PNG captures and semantic metrics are identical to accepted pre-cleanup Sprite evidence. |
| Android/iOS resource packages | Fresh post-cleanup authored fixture: four primary packages plus two JSON-removal controls, six native checks / 13,036 assertions. Six external textures and the compiled rig/demo load without tooling JSON. Normal packages contain zero addon entries; positive controls contain 47, with 37 compiled remap targets excluded normally. Not executable/device validation. |
| Preservation and references | All 24 PNG/import pins, dimensions, cached resource paths and node/texture references resolve. All 48 retained fixture files, 18 protected runtime/spec/test files and 229 export production inputs are unchanged. Empty disk lab remains 120 bytes. `git diff --check` passes; no stage/commit/merge/tag/push. |

The fresh post-cleanup native-authored disposable scene is 71,955 bytes, SHA-256
`64b470e512e04a552889b8c535f0783a943d7ffe00b87a4c2c50fca9fc2afa96`.
Its serialization identity differs from the earlier saved proof; runtime
semantics, spec, assets and all rendered captures are unchanged. The final spec
SHA-256 remains
`459b16ecf4367ef7c9254961a223a0c7ac0d56e79bc9bbc63b5b89e47b700571`.
Native Windows temporary-directory and certificate-store sandbox restrictions
required bounded unsandboxed validation reruns; no test/log guard was relaxed.
At the cleanup stage, final controlled live acceptance remained separate. It is
now complete, as recorded below.

### Final v0.5 acceptance and consolidated regression - 2026-10-02

Healthy live MCP reported Godot `4.7.2-stable (official)`, bridge/plugin `0.5.0`
and protocol `1`. Both public writers were invoked once in the controlled
acceptance sequence. The user then completed Undo demo, Undo rig, Redo rig,
Redo demo, manual Save, close/reopen and final replay. Native history,
Save/Reopen persistence, exact rest return and the visual result were accepted
for the technical milestone. No automatic save/playback/seek was introduced.

The final spec is
`459b16ecf4367ef7c9254961a223a0c7ac0d56e79bc9bbc63b5b89e47b700571`:
19 generated native script-free nodes and 24 pinned PNG/import pairs. The
weighted real-art tail, two-piece arm, existing `head_full`, ordinary HeadPivot
transform animation and explicit 288x147 scarf Sprite2D are the accepted contract. There is no
elbow-sleeve-overlap/neck/candidate-head node or runtime scarf Polygon crop.
`deformation_demo` remains 2.0 seconds, step `0.125`, `LOOP_NONE`, seven tracks /
35 keys, unchanged values/easing and bob `[306,300,294,300,306]`; no RESET,
autoplay, automatic playback or seek.

The consolidated batch used the exact current branch implementation and a frozen
copy of the accepted populated scene. All assertions/log guards were retained.
Counts distinguish unittest methods from native assertions:

| Gate | Final VERIFIED evidence |
| --- | --- |
| All MCP Python suites | 457/457 methods across 19 modules: 286 Godot + 171 Photoshop; zero failures/errors/skips. |
| Included native MCP methods | 78: 25 graphical + 53 headless, including 26 deformation cases (11 graphical + 15 headless). |
| Separate native inspection runner | 1,101 checks: 56 inspection + 442 rig/editor + 603 animation. |
| Operator launcher / UXP / dependencies | Launcher 43 + 39 checks; UXP 61 + 104 checks; pip check clean. |
| Normal Kitchen/game batch | Two runner unit methods; 25 native runs (13 headless + 12 graphical), 11,044 checks and 528 captures. |
| Deformation GPU/oracle | 86 tail CPU/GPU comparisons, 201 geometry poses, 65 arm transform samples, 29 arm captures and 16 head/scarf captures. All 287 PNG captures byte-identical to the accepted Sprite proof. |
| Android/iOS full-project resource controls | Four primary packages + two without-JSON diagnostic packages; eight native checker executions / 13,146 checks (13,036 deformation + 110 production Tolina). Normal packages contain zero addon entries, positive controls 47; 37 compiled/remap targets excluded normally. Compiled native rig/demo loads without tooling JSON. |
| Preservation | All 432 nonignored branch files byte-identical across the batch, including all 24 fixture pairs and 229 export production inputs; original saved-scene mtime retained. No unexpected nonignored files. |

There were no final failures or unexpected warnings. Ten expected malformed-world
warnings belonged to marked Kitchen negative controls; 66 asyncio debug timing
notices were not failures. Initial Windows sandbox Temp/fixture-setup and
certificate-store blocks required approved unchanged environment reruns; their
logs were retained. A Kitchen diagnostic encoding limitation was resolved with
`PYTHONIOENCODING=utf-8`. No behavioral/flaky test retry or log-guard relaxation
occurred. GPU validation passed on its first native execution; later private-Temp
evidence access required approved read/copy archival, not a test rerun. The
headless popup limitation was covered graphically. Release probes were simulated.

After the accepted batch, the user explicitly chose the empty-seed distribution
policy. Only the lab was restored from the captured 120-byte baseline above;
read-only checks verified exact text/hash/UID, zero children/scripts/resources,
unchanged spec and all 48 pinned asset/import files. All other 431 nonignored
files remained byte-identical, and `git diff --check` passed. The whole batch was
not rerun for that exact seed restoration or documentation-only updates.

**NOT EXECUTED:** actual APK/IPA or desktop release executable export, signing,
installation and runtime acceptance; additional real Photoshop processing and
installed operator launching/coexistence in this batch. The accepted live Godot
history/save/reopen/replay was not repeated during the regression batch.

**REQUIRES ANDROID DEVICE:** actual APK installation/replay, target GPU behavior,
touch, performance/frame pacing and pause/resume.

**REQUIRES MAC/iOS:** Xcode executable export/signing, IPA installation, Metal
hardware behavior and device touch/performance/lifecycle. Resource packages on
Windows do not establish executable iOS acceptance.

**REQUIRES USER TEST:** broader installed operator/Photoshop coexistence beyond
automated mocks, plus human review of future joint-ready production artwork and
production integration. The current tooling milestone's controlled visual and
history/persistence acceptance is complete, not an outstanding user-test gate.

## Tolina lab v0.4

The fixed empty-input tools are `godot_create_tolina_rig_lab({})` and
`godot_create_tolina_lab_blink({})`. They require the currently edited scene to
be exactly `res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn`, with
the native script-free `TolinaCharacterRigLab` Node2D root. Root identity is
semantic; normal Godot UID metadata is allowed. Production paths are rejected.
Saving remains a manual user action.

The editor-only [reviewed manifest](../../addons/lunitora_godot/specs/tolina_character_rig_v1.json)
uses schema version 1. `character_rig.gd` pins its complete byte digest outside
the JSON. Closed fields, fixed IDs/paths, PNG/import hashes, dimensions, native
resource types, parents/cycles, finite bounded transforms, regions, alpha,
z-index and count/depth limits are checked before native action creation.
Missing or changed input returns `TOLINA_SPEC_INVALID` or `TOLINA_ASSET_INVALID`;
the writer does not repair assets or imports. The manifest is tooling data;
generated scene nodes have no runtime JSON dependency.

The exact subtree has 21 nodes:

```text
TolinaRig (Node2D)
├── Visual (Node2D)
│   ├── EarLeft, EarRight, Body (Sprite2D)
│   ├── Arms (Node2D)
│   │   └── Idle, Press01, Press02, Press03 (Sprite2D)
│   ├── ShoulderOverlap (Sprite2D)
│   ├── Eyes (Node2D)
│   │   └── Rest, Half, Closed, Excited, Surprised (Sprite2D)
│   └── MouthIdle, MouthExcited, MouthSurprised (Sprite2D)
└── AnimationPlayer (empty)
```

The manifest is the exact mapping source of truth. Every Sprite2D is visible,
with white RGB and `self_modulate = Color.WHITE`; initial variant opacity is
`modulate.a`. Press01/02/03, Half/Closed/Excited/Surprised eyes, and
MouthExcited/Surprised begin at alpha 0. The other pieces begin at alpha 1.
`position = position_px`, `rotation = rotation_rad`, `scale = scale`,
`centered = false`, and `offset = -pivot_px`. Pivot is manifest data, not a
Sprite2D property. A texture-local point maps to
`position + rotation * (scale * (point - pivot))`; for a region, point and pivot
are relative to that cropped region. The region origin selects source pixels
and is not added to the destination. ShoulderOverlap uses region
`Rect2(530, 325, 170, 95)`, positioned at `(530, 325)` with zero pivot.

Textures use normal `CACHE_MODE_REUSE`; Body/ShoulderOverlap share the same
external body texture. Assignment can emit a new Sprite2D's `texture_changed`,
but production Texture2D content/properties/paths are never changed. Verification
compares native resource state and source/import hashes. Normal reference-count,
Sprite2D observer and save-time external-resource-ID bookkeeping is permitted;
production referrer IDs and resource contents remain unchanged. There is no
`take_over_path`, private texture copy, cache replacement, reimport or production
save. Static local composition follows the saved/reset production operator,
with no intentional visual difference; its production script, random blink,
reaction channels and machine-parent transform are omitted.

Rig creation is one action, `Lunitora: Create Tolina Character Rig`, with detached
preparation, ownership for all 21 nodes and native retained node references.
Undo removes the subtree; Redo reattaches the same nodes and restores ownership.
Blink uses `Lunitora: Create Tolina Lab Blink`; native bound method arguments
retain the same AnimationLibrary/Animation through Undo/Redo. No resource
do/undo-reference calls or custom history cache are used.

The reviewed blink has one global library and one `blink` Animation, length
`0.24`, step `0.125`, non-looping. Three enabled continuous linear value tracks
target `Visual/Eyes/Rest:modulate:a`, `Visual/Eyes/Half:modulate:a`, and
`Visual/Eyes/Closed:modulate:a`. Times are canonical
`PackedFloat32Array([0, 0.05, 0.095, 0.14, 0.19, 0.24])`; respective values are
`[1,0,0,0,0,1]`, `[0,1,0,0,1,0]`, `[0,0,1,1,0,0]`, with transitions 1. There
are no extra tracks, markers, RESET, autoplay, assignment, queue or playback.
Target validation resolves the exact native sprites and float alpha channels.

Authored keys, writer-written sprite alpha and rest endpoints are strictly in
`[0,1]`. **Godot 4.7.2 playback limitation:** its approximate key search can
select an upcoming segment and extrapolate with an unclamped weight just before
a key. Native tests characterize an alpha of `1.00002222` / `-0.00002222`,
including actual Color assignment; this is an observed sample, not a universal
error bound. The approved exact fixture is retained without clamps, altered
keys or automatic playback. Detached interpolation samples must remain finite
and complementary. Absolute bounds on native playback interpolation are not
claimed. See the [pinned engine interpolation implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/resources/animation.cpp#L2247-L2505).

The v0.3 Godot 4.7.2-specific AnimationPlayer-editor admission rule applies to
both animation writers: no native attachment or unclassified relevant observer,
one quiet normal plugin process observation followed by a strictly later normal
process, and a final synchronous recheck. Recursive polling cannot mature the
barrier. Changes in scene, session, selection, inspector or target invalidate it.
Admission never changes panel, selection, pin or callback state. Controlled
detached/settled cycles retain strict stopped/unassigned/rest-state guarantees;
attaching the Animation editor before a later native Redo can cause normal
Godot observer assignment/seek, which is characterized rather than intercepted.
Unknown relevant observers remain a conservative lab-only admission restriction.

These writers use the shared 128-ID editor-session ledger, operation/session
correlation, reconnect/Python-restart handling, busy/committing guard and fault
latch. Preparation failures are pre-action only. Once action creation begins,
uncertainty returns `WRITE_OUTCOME_UNKNOWN` and blocks all writers. Ordered reads
settle execution ordering; they do not establish semantic success. Never retry
a write automatically.

**VERIFIED:** real-checkout bridge/plugin `0.4.0`, successful
`godot_create_tolina_rig_lab({})` and `godot_create_tolina_lab_blink({})`, native
blink Undo/Redo and manual Save/Reopen persistence. **USER VERIFIED:** generated
Tolina matches the production idle/front appearance; the final blink returns to
normal eyes and looks good at 390×844, 405×720 and 540×960, without unacceptable
clipping, seams or ghosting. Final manual cleanup restored the clean empty
117-byte lab below. No A/B/C experiment residue remains. Tolina bones/mesh,
production integration, AnimationTree, IK and procedural animation are outside
this milestone.
Executable iOS export/device behavior remains **NOT VALIDATED / REQUIRES MAC/iOS**.

The MCP writers preserved production Texture2D resources and source/import files.
Separately, Leon intentionally replaced only
`assets/characters/totolina/eyes/cat_totolina_eyes_blink_02.png`; its final approved
SHA-256 is `7e797c9d373a0440e663286be575ebf856b185e0c62e49d7f38002fc7af63f99`.
Its `.png.import` and every other Tolina PNG/import remain unchanged. The final
rig-spec digest and external pin are
`439aed4c21b6d524a875ceec3144e5a1b82d5cdece799dd6851d30f435a2be0f`.
Targeted construction, blink, Undo/Redo, persistence, texture-preservation and
export-control validation was rerun against this approved artwork/spec pair;
five retained native/editor cases and 1,094 resource export/control checks passed.
The original public blink recipe was retained.

### v0.4 automated validation — 2026-10-01

**VERIFIED:** Godot `4.7.2.stable.official.ed1daf0bf`, bridge/plugin `0.4.0`,
protocol `1`. Implementation suite results and affected-case reruns follow;
the final artwork/spec validation is identified above.

| Gate | Result |
| --- | --- |
| Godot Python / protocol / export boundary | 168 tests: 130 existing, 32 Tolina, six export-boundary. |
| Existing native transport / public writers | 25 tests, including graphical editor cases. |
| Tolina native public writers | 27 tests: 16 headless editor and 11 graphical; 220 unique Godot tests overall. |
| Standalone editor fixture | 56 inspection + 442 synthetic rig + 603 animation assertions; 1,101 total. |
| Supplemental closed character helper proof | 76 native checks. |
| Photoshop | 171 Python tests and 165 UXP checks. |
| Launcher | 82 checks; real application/process mutations mocked. |
| Kitchen | Two runner self-tests; 25 suites / 11,044 checks, including 12 graphical suites. |
| Mobile resource exports | Four Android/iOS exclusion/control packs, two JSON-removed diagnostic packs, 1,234 native assertions. |

Native tests verify the 21-node recipe, ownership, all sixteen sprites and three
groups against the saved production composition, root/inherited modulation,
render defaults, external texture identity, cold/warm/production-loaded caches,
zero Texture2D mutation signals, combined rig/blink Undo twice/Redo twice,
retained instance lifetime/disposal, clean/dirty save points, save/reopen and
plugin reload. Admission, replay/capacity, request/session correlation,
timeout/lost response, read settlement, reconnect/Python restart/session rollover,
native committing/re-entry and both shared post-action fault cases pass.
Missing/changed specs, PNG/import/CTEX inputs, cached resource faults and wrong
lab/root/native class/script reject before action creation. The characterized
native interpolation limitation above remains explicit.

Each normal export has zero addon entries and omits all ten compiled addon
remap targets. Controls load both authored labs; Tolina remains loadable after
removing the editor JSON. All fifteen production PNG import/CTEX payloads match
between normal and control packs; export checks preserve their production-input
snapshots. Source audits use exact final addon bytes. The intended Tolina lab
baseline is the following Godot-authored empty native root, **117 bytes** with a
final newline, SHA-256
`28b3f645e60c64f4ee89e766eede0e47470053ddd61edc81c7cde0fe184eec96`:

```ini
[gd_scene format=3 uid="uid://c21k6kuywph5f"]

[node name="TolinaCharacterRigLab" type="Node2D" unique_id=140800244]
```

Keep this normal UID metadata; do not restore the earlier 71-byte representation.
The accepted synthetic lab remains unchanged at 111 bytes with its existing UID
metadata. Neither baseline contains a generated scaffold or animation.

Initial disposable-fixture publication/timer assumptions and a replay test's
missing separate read barrier were corrected in test support; affected tests
passed on rerun. Concurrent source changes were detected by export hash audits
and the final frozen-source export run passed. No safety check was weakened.
The numerical playback limitation was explicitly approved without altering the
fixture. Machine-local configuration, production scenes/scripts, export presets,
Photoshop and launcher implementation remain unchanged. The intentional artwork
exception and completed live/visual acceptance are recorded above.
**NOT EXECUTED:** executable exports/device tests. **NOT VALIDATED / REQUIRES
MAC/iOS:** executable iOS export/device behavior; `ios.zip` is absent from the
installed `4.7.2.stable` templates.

## New-computer setup

Use Windows, Python **3.12.x**, and the project-compatible Godot **4.7.2** editor.
Keep the toolkit's existing `requirements.lock`; the Godot bridge adds no package
pins or generalized transport framework. Run the following from the checkout
root in PowerShell, adjusting only the checkout and installed executables on a
different PC:

```powershell
py -3.12 -m venv tools/lunitora_mcp/.venv
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -m pip install -r ./tools/lunitora_mcp/requirements.lock
```

Reuse an existing Python 3.12 toolkit environment. Do not recreate an environment
already used by Photoshop. Check its interpreter first:

```powershell
& ./tools/lunitora_mcp/.venv/Scripts/python.exe --version
```

Add this separate entry to the user-level Codex `config.toml`. These are this
workstation's actual paths:

```toml
[mcp_servers.lunitora_godot]
command = 'D:\Development\LunitoraGames\totolina-merge\tools\lunitora_mcp\.venv\Scripts\python.exe'
args = ['-B', '-m', 'core.godot_server']
cwd = 'D:\Development\LunitoraGames\totolina-merge\tools\lunitora_mcp'
startup_timeout_sec = 15
tool_timeout_sec = 10
enabled_tools = ['godot_ping', 'godot_get_editor_state', 'godot_inspect_scene', 'godot_create_rig_lab', 'godot_create_rig_lab_animation', 'godot_create_tolina_rig_lab', 'godot_create_tolina_lab_blink']
```

On this PC the user configuration is `C:\Users\julio\.codex\config.toml`.
Preserve the existing Photoshop entry and all unrelated configuration. Do not
put credentials in the config, command arguments, or environment. Restart the
Codex connection/app as needed to discover the newly configured server; a file
edit alone does not prove this chat has loaded or called it.

For daily editor startup, configure and use the repository-local launcher below.
The equivalent direct editor command is:

```powershell
& 'C:/path/to/Godot_v4.7.2-stable_win64.exe' --editor --path 'C:/path/to/totolina-merge'
```

`project.godot` enables `addons/lunitora_godot/plugin.cfg`. Godot can start before
Codex: the plugin waits for the credential and listener, then authenticates. It
reconnects after Codex restarts or the editor is closed/reopened. Disabling the
plugin closes its connection; enabling it starts connection attempts again.
Only one owning Python listener and one authenticated editor are supported.
A port conflict returns an explicit availability error and never selects a new
port or terminates the existing listener.

## Repository-local Godot launcher v0.7

Reuse the existing launcher; no second launcher or manual Python server is needed.
From the checkout root in Git Bash, validate/save the installed Godot executable:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/setup.ps1 \
  -GodotExe 'C:\path\to\Godot_v4.7.2-stable_win64.exe'
git godot -Check
git godot
```

Setup saves optional `godotExe` in ignored
`tools/operator_launcher/config.local.json`, preserves the existing Photoshop/UDT
configuration, and installs all seven repository-local aliases. Legacy
four-field configurations remain valid for art/dev commands. `-Check` validates
configuration without starting or stopping applications.

`git godot` ensures this is the configured `totolina-merge` checkout, starts
ChatGPT/Codex Desktop if needed, and opens the configured Godot 4.7.2 editor using
`--editor --path <repo-root>`. It verifies executable path and project arguments
when detecting an already running editor; window titles alone are insufficient.
It does not open the Project Manager, Photoshop, or UXP Developer Tool, and does
not touch Photoshop port 43127. Codex owns the `lunitora_godot` stdio MCP process;
the launcher never starts `core.godot_server` manually.

Run `git godot-refresh` from external Git Bash after active Desktop work finishes.
It fully restarts Desktop, allows the old Codex-owned Godot MCP process to exit,
and verifies port 43128 becomes free before reopening Desktop. It can terminate
only a stale process positively verified as this checkout's exact Lunitora Godot
MCP process. An unknown PID is never killed. It keeps Godot open to protect
unsaved editor work and lets the editor reconnect to the new Codex-owned server.

The original five art/dev commands retain their 2026-09-30 live verification.
**VERIFIED — user-reported live validation on 2026-09-30:** `git godot` opened
Codex and the correct Totolina Merge project without Photoshop or UDT.
`git godot-refresh` restarted Codex/MCP while preserving the running Godot editor
and unsaved scene state; the Godot MCP reconnected successfully.

## Automatic local credential

Normal server startup creates the ignored, project-bound file:

```text
tools/lunitora_mcp/.local/godot-auth.json
```

The credential contains an automatically generated **256-bit secret**. Subsequent
starts preserve it. Creation is exclusive and bounded. The Windows DACL grants
the current user and SYSTEM access; unsafe ownership/permissions, symlinks,
reparse points, redirections, malformed storage, and project mismatches fail
closed. The plugin reads only this fixed local file. It does not accept a secret
from a tool argument, arbitrary path, or unauthenticated network request.

The containing `.local` directory must also have safe ownership and a protected
Windows DACL. If a pre-existing directory does not meet that policy, startup
returns `LOCAL_AUTH_UNSAFE`; it does not broadly change shared Photoshop storage
permissions or replace credentials. Review the directory's owner and ACL on the
new workstation and apply only the necessary local storage correction. This
review never requires printing a credential value.

Authentication uses fresh client/server nonces and mutual HMAC-SHA256 proofs.
Both proofs include protocol version, project identity, both nonces, and distinct
server/client role labels. Godot uses `Crypto.hmac_digest()` and
`Crypto.constant_time_compare()`. The secret is never sent over the WebSocket.
The Windows project identity is SHA256 of the lowercase absolute checkout path,
using forward slashes with no trailing slash.
An unrelated service on 43128 therefore does not receive a bearer credential.
Authentication never falls back to trusting localhost, and failed authentication
does not automatically replace an existing credential. Browser-origin requests
are rejected.

Do not copy the credential to another computer or another checkout. Let that
checkout's server generate its own. Never print, log, commit, or paste the file.
Shared local authentication cannot protect against malware running as the same
Windows user or an administrator with access to the process or credential.

## Response contract and bounds

Each response carries `ok`, `connected`, `protocol_version`, `bridge_version`,
`round_trip_ms`, `result`, and a sanitized `error`. Success has a non-null result
and null error. Failure has a null result and an explicit error code. A ping is
a fresh authenticated editor reply, rather than a cached connection flag.

- `godot_ping`: Godot/project/plugin versions and editor session identity.
- `godot_get_editor_state`: the ping metadata, scene save state, and selection.
- `godot_inspect_scene`: scene state and bounded node metadata, including safely
  available animation names.
- `godot_create_rig_lab`: the verified fixed lab scaffold, one undo action, and
  `saved_dirty`, `auto_saved=false`, `read_only=false` on success. Metadata reads
  still report `read_only=true`; this field describes the individual operation.

The limits are **2,000 nodes**, **depth 64**, **128 selected-node entries**,
**128 animation names per player**, **512 names overall**, **256 KiB per encoded
frame/response**, and **4 KiB per string**. Structural overflow returns an error;
selection truncation and omitted animation names are explicitly reported. Node
paths are relative to the edited root (`.` for the root). Legitimate instanced
descendants are included; internal editor children are excluded.

The response bound also counts the complete serialized MCP result, including
both text and structured metadata and JSON escaping. The server reserves 1 KiB
for the normal JSON-RPC envelope, allowing at most 255 KiB for the SDK result.
It can return `RESPONSE_TOO_LARGE` for metadata that fits the WebSocket frame
limit but would exceed the final MCP response budget.

There are no animation tracks/key values, mesh vertices, texture/image bytes,
arbitrary script properties, resource serialization, or filesystem contents in
tool results. A no-scene response has no nodes. The path-based editor dirty-state
API cannot distinguish all unnamed tabs: a new unsaved scene reports
`dirty_changes=null` and does not invent a clean/dirty answer.

Requests have unique IDs and bounded deadlines (five seconds by default).
Disconnects fail pending requests, which are never silently replayed on reconnect.
Malformed, oversized, stale,
wrong-project, unauthenticated, or unsupported messages are rejected. Python's
stdout carries MCP only; diagnostics belong on stderr and never include secrets.

## Fixed rig-lab scaffold v0.2

Open the saved, native, script-free `TotolinaRigLab` (`Node2D`) seed scene at
`res://addons/lunitora_godot/labs/totolina_rig_lab.tscn` in the editor. If the seed
is absent in a new setup, create and save that empty native root manually first.
Keep the lab open and call `godot_create_rig_lab` with `{}`. The operation rejects other scenes,
the wrong root name/class or a scripted root, and an existing `TotolinaRigV2`.
It appends exactly these seven native, script-free nodes; every generated node
has the lab root as its owner:

```text
TotolinaRigLab (existing Node2D)
└─ TotolinaRigV2 (Node2D)
   ├─ Meshes (Node2D)
   │  └─ TestMesh (Polygon2D)
   ├─ Skeleton2D (Skeleton2D)
   │  └─ Root (Bone2D)
   │     └─ Tip (Bone2D)
   └─ AnimationPlayer (AnimationPlayer)
```

`TestMesh` has exact `Color(0.25, 0.5, 1.0, 1.0)`, no texture, six fixed vertices
forming a 128 × 24 rectangle, and four fixed triangles. Its skeleton path is
`../../Skeleton2D`; the `Root` and `Root/Tip` weights are respectively
`[1, 0.5, 0, 0, 0.5, 1]` and `[0, 0.5, 1, 1, 0.5, 0]`. Both bones have fixed
64-pixel lengths/rest poses, with `Tip` offset by `(64, 0)`. The AnimationPlayer
is empty: no libraries, clips, tracks, RESET animation, autoplay, or playback.
This fixture proves basic native rig wiring; it does not establish a production
character or an approved animation.

The writer validates and builds the detached scaffold before starting the
single action `Lunitora: Create Totolina Rig Lab Scaffold`. It validates the lab
again immediately before action creation, commits synchronously without awaits
or deferred mutation, and then verifies the exact node recipe, owners, current
scene/session, dirty state, and native scene-history change. `commit_action()`
is not treated as a transaction or proof of success. Successful creation leaves
the lab dirty; save only when the user chooses. Native editor Undo removes the
whole subtree, and Redo restores it. Existing production resources remain outside
the writer's allowed scene.

Every write first obtains a fresh editor-state reply on the same authenticated
connection and binds its request to that editor session. Writes are
non-reentrant. A possibly sent write blocks another write until a matching reply
or a compatible later authenticated read establishes an ordering barrier. Such a
read proves that the older request cannot still execute; it does not prove the
semantic write outcome. Partial send, disconnect, timeout, or response-validation
uncertainty therefore requires scene/history inspection rather than retrying the
write. No write is replayed automatically on reconnect.

The editor keeps a separate bounded session ledger of admitted write IDs,
independent of the reconnectable read-response cache. Duplicate write IDs are
rejected rather than served from a cached success; reconnecting or restarting
the Python owner does not erase this ledger. After 128 admitted IDs the session
rejects more writes. Re-entry, a committing undo action, retired sessions, and
failed post-action verification fail closed. If an action began and its outcome
cannot be verified, the editor writer is faulted for that session and reports
`WRITE_OUTCOME_UNKNOWN`; it does not undo, save, or attempt another action as an
automatic repair.

The separate v0.3 fixture operation below proves native animation-resource
creation. The roadmap includes reusable rigs and AnimationPlayer, Tween,
AnimatedSprite2D, and lightweight effects for other characters, UI, and worlds,
following [ANIMATION_GUIDELINES.md](../../docs/ANIMATION_GUIDELINES.md). It must
remain useful beyond the current Totolina artwork. Production migration,
deformation polish, general animation editing, playback controls, and general node/resource
editing are separate future capabilities.

## Fixed rig-lab animation v0.3

`godot_create_rig_lab_animation({})` requires the exact v0.2 rig at rest in the
dedicated lab. The native, script-free player must resolve `root_node = ..` to
`TotolinaRigV2`, retain native playback defaults and have no libraries (including
an empty global library), animations, assignment, autoplay, active playback or
queue. Modified rigs, production scenes and conflicting player state reject
before action creation, preserving dirty state and redo history.

The detached global library `&""` contains only `bend_tip`: length `1.0`, step
`0.125`, `LOOP_NONE`, one enabled, non-imported `TYPE_VALUE` track at
`Skeleton2D/Root/Tip:rotation`, `INTERPOLATION_LINEAR_ANGLE`, `UPDATE_CONTINUOUS`,
loop wrap disabled, transitions `1.0`. Float keys are `0.0 → 0.0`,
`0.5 → 0.3490658503988659`, `1.0 → 0.0`. Detached interpolation at `0.25`/`0.75`
must match ten degrees within `1e-6` radians. There are no markers, RESET,
autoplay or extra resources/tracks; the writer never seeks the live player.

The one action `Lunitora: Create Rig Lab Animation` attaches the prepared library
to the existing player. Undo removes it; Redo reattaches the same resource
instances. Native bound Variant arguments retain the RefCounted resources;
there are no node-only do/undo references, plugin lifetime cache, explicit
resource frees or external `.tres` files. Final admission, action registration,
commit, complete resource/player/scene/history verification and writer epilogue
are synchronous. `RIG_LAB_ANIMATION_BUILD_FAILED` applies only before action
creation; uncertain post-action state becomes `WRITE_OUTCOME_UNKNOWN` and faults
both writers. Never automatically retry, Undo or repair that result. Both writers
share the non-evicting 128-ID editor-session ledger, guard and transport fence;
terminal settlement correlates operation, ID, connection and editor session.

AnimationPlayer-editor safety behavior is verified specifically against Godot
**4.7.2**. Admission inspects the target's `animation_list_changed`,
`current_animation_changed`, `animation_finished` and `caches_cleared`
connections. Godot's native `AnimationPlayerEditor` receiver is identifiable;
unclassified relevant observers also reject as a temporary **lab-only** limit.
`LAB_ANIMATION_EDITOR_BUSY` rejects attachment. `LAB_ANIMATION_EDITOR_SETTLING`
requires an initial quiet normal plugin process observation and a strictly later
stable normal process pass. Scene/root/player/session replacement and selection,
inspector or scene changes invalidate the observation. Same-pass recursion cannot
mature it. This normal process barrier settles copied deferred callbacks; a
disappearing connection or a bare `process_frame` await alone is insufficient.
The writer never disconnects callbacks or changes editor UI.

**Recovery:** unpin the AnimationPlayer, switch the bottom panel away from
Animation (for example to Output), manually save if needed, close/reopen the lab
and keep Animation hidden. Unpinning or selecting the root alone does not detach
Godot 4.7.2's editor. Do not automatically retry a rejected request.

The strict unassigned/stopped/rest-pose Undo/Redo guarantee requires the proven
detached and settled conditions throughout the controlled cycle. Attaching the native
AnimationPlayer editor after Undo can make ordinary Redo select/assign the clip
and seek after deferred editor frames. Native Undo/Redo remains unmodified.
General animation capabilities must support appropriate Godot-native techniques
beyond current artwork; missing source pieces should be reported explicitly.
This fixture does not define production character architecture.

The APIs and lifetime wiring follow the official
[Godot 4.7 Animation documentation](https://docs.godotengine.org/en/4.7/classes/class_animation.html),
[EditorUndoRedoManager documentation](https://docs.godotengine.org/en/4.7/classes/class_editorundoredomanager.html)
and [4.7.2 AnimationPlayer editor source](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/animation/animation_player_editor_plugin.cpp).

## Validation commands

Run the toolkit's Python tests from its directory using the environment above.
The Godot cases use disposable credentials and ephemeral ports, so they do not
claim a live Codex/editor connection or occupy Photoshop's port:

```powershell
$env:GODOT_TEST_EXE = 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe'
Push-Location tools/lunitora_mcp
& ./.venv/Scripts/python.exe -B -m unittest discover -s tests -p 'test_godot_*.py' -v
Pop-Location
```

`GODOT_TEST_EXE` is only a native test executable override. Set it to the installed
Godot path on a different workstation. Native transport cases use the actual
`WebSocketPeer` and `Crypto` against a disposable Python listener; they still do
not establish a Codex/editor live session.

The native inspection/startup fixtures live under `tests/godot_mcp/`. Validate
with the installed Godot 4.7.2 executable and use isolated project copies;
synthetic fixtures are not production rigs.

```powershell
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -B ./tests/godot_mcp/run_native_validation.py --godot 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe' --timeout 120
```

This runner copies only the addon and fixtures into a disposable project,
enables the plugin there, checks actual editor startup/import/parsing, and
requires exactly 56 successful native inspection/security checks. A second,
test-only EditorPlugin then exercises the rig writer and actual editor Undo/Redo
commands in that copy; a separate real graphical Windows editor exercises the
v0.3 admission, deterministic animation, native history/lifetime, save-point,
persistence and fault matrix. Public registered MCP tests also exercise actual
authenticated transport and graphical frames. Controllers and their callback
overrides exist only in disposable copies. Logs and editor data
remain in the printed temporary artifact directory.

Windows graphical transport fixtures start the editor before acquiring test
credential directory pins: Godot's startup replacement save of `project.godot`
conflicts with those existing security pins. The fixture then reacquires the same
protected project credential and authenticates before any MCP operation. This
bootstrap changes no production security or machine configuration.

The export gate executes Godot's real Android and iOS **data-package** exporters
using the exact repository presets in an isolated runtime-resource copy. It verifies
the emitted ZIP entries and any compiled resources reached by addon remaps.
The snapshot includes tracked and new nonignored runtime files, refuses redirected
resource paths, and omits local credentials, virtual environments, caches, and
source artwork. The initial CSV import uses the existing Kitchen runner's
translation bootstrap; actual project settings are restored for every export.
Each native process receives private `TEMP`, `TMP`, and `TMPDIR` paths under its
artifact directory, keeping Godot's `tmpproject.binary` separate from parallel
fixtures. Strict engine-error detection remains enabled.
Then it removes only the addon exclusion in each disposable preset as a positive
control and requires the actual `rig_lab.gd` and `animation_writer.gd` helpers and
`labs/totolina_rig_lab.tscn` fixture, existing addon scripts, and nested resources
to appear. `--authored-lab-scene` accepts a retained actual public-writer native
Save/Reopen artifact; only the disposable lab copy is replaced. The positive
packages are then loaded natively to verify the complete inline rig/animation
recipe. Each positive remap must point to a packaged artifact, including
compiled scripts/scenes outside the addon folder; all those targets must be
absent from the excluded package. A runtime
resource must appear in every package, and local credential probes must not.

```powershell
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -B ./tests/godot_mcp/export_validation.py --full-project --godot 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe' --timeout 600
```

The only mobile preset change is the exclusion `addons/lunitora_godot/*` on the
existing Android and iOS presets. Signing, package IDs, architectures, render
settings, and other mobile options are preserved. The gate retains four ZIPs,
local exporter logs, and a JSON report. It verifies physical package exclusion;
it does not create an APK/IPA, validate signing, or exercise a device.

Rerun the existing Photoshop MCP and operator-launcher suites, then the Kitchen
gates described in [tests/README.md](../../tests/README.md):

```powershell
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -B tests/test_merge_runner.py
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -B tests/run_kitchen_regressions.py --godot 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe' --graphical
```

For final acceptance, call the metadata tools through **Codex with this project open
in the actual Godot editor**. Check both startup orders, restart, close/reopen,
plugin disable/enable, no scene, saved/dirty/unnamed tabs, selections, and scene
switching. Compare scene/resource files, selection, dirty state, and undo history
before/after read-only calls. Keep Photoshop available during the live check.
These checks must be reported separately from fake-peer, SDK stdio, and headless
fixture tests.

For the v0.2 writer, use the dedicated seed lab through the actual Codex-owned
connection, verify exactly seven generated nodes, one native undo action and
unchanged lab-file bytes, then use the editor's Undo and Redo commands. A second
creation must refuse an existing rig. Check the empty AnimationPlayer, exact
color/weights/rest poses, ownership, scene-switch rejection, and recovery after
connection uncertainty. Never start a manual server on live port 43128 for this
acceptance. These editor checks and human visual review remain separate from
disposable native fixtures and export ZIP evidence.

## Validation status language

Use **VERIFIED** only for checks actually executed successfully, **NOT EXECUTED**
for checks not run, and **REQUIRES USER TEST** for remaining interactive acceptance.
Rendered animation quality remains **REQUIRES USER REVIEW** unless the user has
reviewed it. Mobile behavior remains **REQUIRES ANDROID DEVICE** or
**REQUIRES MAC/iOS**; desktop and ZIP tests do not establish device acceptance.

The historical v0.1 implementation contained inspection only. v0.2 added the
fixed lab scaffold; v0.3 adds only its separate fixed animation operation.
General animation editing/playback controls, generic resource writes, production
migration and new operator aliases remain outside this milestone.

## Historical implementation file manifest — v0.1

The original v0.1 implementation modified these three previously tracked files:

```text
export_presets.cfg                  Android/iOS addon exclusions only
project.godot                       New editor plugin enablement only
tools/lunitora_mcp/README.md         Link to this Godot guide only
```

It created these 25 Git-visible files:

```text
addons/lunitora_godot/bridge_client.gd
addons/lunitora_godot/bridge_client.gd.uid
addons/lunitora_godot/inspection.gd
addons/lunitora_godot/inspection.gd.uid
addons/lunitora_godot/plugin.cfg
addons/lunitora_godot/plugin.gd
addons/lunitora_godot/plugin.gd.uid
tests/godot_mcp/export_validation.py
tests/godot_mcp/inspection_validation.gd
tests/godot_mcp/inspection_validation.gd.uid
tests/godot_mcp/run_native_validation.py
tools/lunitora_mcp/GODOT_README.md
tools/lunitora_mcp/core/godot_server.py
tools/lunitora_mcp/modules/godot/__init__.py
tools/lunitora_mcp/modules/godot/bridge.py
tools/lunitora_mcp/modules/godot/config.py
tools/lunitora_mcp/modules/godot/protocol.py
tools/lunitora_mcp/modules/godot/security.py
tools/lunitora_mcp/modules/godot/tools.py
tools/lunitora_mcp/tests/fake_godot_client.py
tools/lunitora_mcp/tests/test_godot_auth.py
tools/lunitora_mcp/tests/test_godot_bridge.py
tools/lunitora_mcp/tests/test_godot_native_bridge.py
tools/lunitora_mcp/tests/test_godot_protocol.py
tools/lunitora_mcp/tests/test_godot_stdio.py
```

Local-only setup comprises the separate `lunitora_godot` entry in
`C:\Users\julio\.codex\config.toml`, the ignored toolkit `.venv`, and the ignored
automatic `.local/godot-auth.json`. Ignored `.godot/` and temporary directories
hold editor imports, isolated test copies, logs, screenshots, and export ZIPs.
These local files are not part of the Git change set. All previous user
configuration entries are preserved; no Photoshop MCP entry is modified.
The toolkit lock and production scenes, scripts, resources, and assets were
preserved. Current v0.2 adds `addons/lunitora_godot/rig_lab.gd` and its UID plus
the dedicated lab seed scene, extends only the Godot operation allowlist and
validation support, and preserves the existing launcher and Photoshop profiles.

## Historical recorded validation — v0.1, 2026-09-30

This is the historical v0.1 implementation record. Current launcher acceptance
is recorded in [Repository-local Godot launcher v0.7](#repository-local-godot-launcher-v07);
the broader GUI and device checks below retain their original validation status.

The implementation is on `tooling/godot-animation-mcp-v0.1` at unchanged HEAD
`226c4ce`. Git shows 28 implementation files: three modified and 25 new, with
nothing staged. No commits or pushes were made. The production-file audit and
`git diff --check` passed.

| VERIFIED gate | Exact executed result |
| --- | --- |
| Godot Python | 76 tests passed; zero failures/skips: 22 protocol, 13 auth/security, 28 bridge, 11 stdio, 2 native transport. |
| Native Godot 4.7.2 | Editor startup/import/GDScript parsing clean; 56 inspection/security checks passed, zero failures. |
| Existing Photoshop Python | 171 tests passed. |
| Existing Photoshop UXP | 165 tests passed: 61 plugin and 104 processing. |
| Operator launcher | 43 tests passed. |
| Existing Kitchen runner unit gate | 2 tests passed. |
| Full Kitchen gate | 25 suites and 11,044 checks passed: 13 headless suites / 4,732 checks; 12 graphical suites / 6,312 checks; zero failures and clean import. |
| Android/iOS package exclusion | 4 native data-package exports passed, zero skipped: two excluded ZIPs and two positive-control ZIPs. |
| Local dependency setup | All 30 existing lock pins installed in the toolkit Python 3.12 environment; `pip check` passed. |
| Local Codex configuration | Separate user-level Godot entry added and verified with `codex mcp get`; previous config entries preserved; exactly the three permitted tools enabled; no credentials in config. |
| Actual Codex/editor connection | Codex CLI called all three tools with `{}` through the config-backed stdio server and an actual headless Godot 4.7.2 editor on this project. The saved machine scene reported `saved_clean`, 52 nodes, blink, and the seven expected machine clips. |

Both final excluded mobile ZIPs contain **277 entries and zero addon entries**.
Each positive control contains **287 entries and eight addon entries**. Five
compiled resource targets identified through addon remaps are absent from each
excluded ZIP. The runtime main scene and resource control are present, and local
credential probes are absent. All seven v0.1 addon files matched the tested
export snapshot byte-for-byte. This is physical package evidence, rather than
an exclusion-string check.

Local evidence:

- `.godot/godot-mcp-export-verified/report.json` and its four ZIPs/export logs.
- `.godot/godot-mcp-validation/native-inspection.log` and `native-startup.log`.
- `.godot/godot-mcp-validation/live-codex.jsonl` and `live-editor.log`.
- `.godot/godot-mcp-validation/kitchen-tests.log` and `.godot/godot-mcp-kitchen-final/` captures/logs.

**NOT EXECUTED:** APK/IPA creation, signing, Android hardware, Mac/iOS/Xcode
validation, concurrent live Photoshop acceptance, and the full manual GUI
acceptance matrix. Headless editor metadata calls do not establish GUI behavior
or visual acceptance.

**REQUIRES USER TEST:** reload the desktop chat's MCP catalog; check editor/Codex
startup orders, saved/dirty/unnamed tabs, selections and scene switches,
close/reopen, plugin disable/enable, and unchanged selection/dirty/undo state
around tool calls. Run the live Photoshop tools concurrently for operator
acceptance. Graphical captures remain **REQUIRES USER REVIEW** for subjective
presentation quality; mobile behavior requires the relevant devices.

## Accepted v0.2 regression and package record — 2026-09-30

The independent regression and export run used actual Godot
`4.7.2.stable.official.ed1daf0bf` and preserved all **224** baseline tracked
production/config resource hashes. `project.godot` and `export_presets.cfg`
remained byte-for-byte unchanged. Before live acceptance, the dedicated lab
remained its initial empty native seed; that run's SHA256 was
`6F54A20542FE4530AD592FC873AB739D2322BE5B275836ABABBD8A077DFD9ADF`.

| VERIFIED gate | Executed result |
| --- | --- |
| Complete Godot MCP Python discovery | 116 tests passed in 52.937 seconds, zero failures/skips: 100 configuration/authentication/protocol/bridge/MCP tests and 16 actual native transport tests. |
| Existing Photoshop Python | 171 tests passed in 38.036 seconds; zero failures/skips. |
| Existing Photoshop UXP | 165 checks passed: 61 plugin/panel and 104 processing. |
| Existing launcher | 82 safety/workflow checks passed: 43 original and 39 Godot; no real applications started or stopped. |
| Kitchen runner self-tests | 2 tests passed. |
| Full Kitchen gate | 25 suites / 11,044 checks passed: 13 headless / 4,732 and 12 graphical / 6,312; zero failures and clean native import. |
| Full-project Android/iOS data exports | Four native ZIP exports passed, zero skipped: two exclusions and two positive controls. |
| Export source fidelity | All 10 current addon/helper/seed files matched the tested export snapshot. |
| Current isolated native editor acceptance | 56 retained inspection checks and 442 rig-editor checks passed; zero failures. |
| Actual native client transport | 16 tests passed: 9 bridge/writer cases and 7 ordered-settlement, old-peer, session/ledger, fault and reentrant-poll/shutdown safety cases. |

Each excluded ZIP contains **279 entries and zero addon entries**. Each positive
control contains **293 entries and 11 addon entries**, including the actual
compiled `rig_lab.gdc` and the lab scene's compiled `.scn` target. All **seven**
compiled resource targets reached by addon remaps are absent from each excluded
ZIP. The runtime main scene and resource control are present; local credential
probes are absent. These are physical-package checks with the actual helper and
scene, rather than preset-string checks or synthetic placeholders alone.

Evidence remains in the local temporary directory
`C:\Users\julio\AppData\Local\Temp\lunitora-godot-v02-regressions-5847612491b54ad58c779b666fac9376`:
`photoshop-python-retry.log`, `uxp-plugin.log`, `uxp-processing.log`,
`launcher-base.log`, `launcher-godot.log`, `kitchen-runner-unit-retry.log`,
`kitchen-retry-runner.log`, `kitchen-retry/` logs/captures,
`production-baseline-hashes.json`, and `exports-final-verified/` with the four
final-source ZIPs, exporter logs, private native temporary storage and
`report.json`. Earlier export attempts remain in `exports/`, `exports-final/`
and `exports-final-retry/`; the final verified run exercises the persistent
temporary-path isolation. Initial sandbox attempts were retained separately;
the clean Windows-permission retries above are the passing results. The native
editor acceptance was rerun with private process-temporary paths; final evidence
is at `C:\Users\julio\AppData\Local\Temp\lunitora-godot-native-y_cstvh9`.
Complete final Python discovery is recorded in
`C:\Users\julio\AppData\Local\Temp\lunitora-godot-v02-final-320d184fa1ce4a9a8862448f1d304658\godot-python-all.log`.
Per-case native safety logs and evidence are retained in the ignored
`tools/lunitora_mcp/.local/native-safety-logs/` directory.

The automated runs above cover unchanged-workflow regressions and physical
export exclusion; live acceptance is recorded below. Automated checks do not
establish human rig/animation approval or device behavior.
**NOT EXECUTED in this package run:** APK/IPA creation, signing, executable iOS
export, Android hardware, Mac/iOS/Xcode and device behavior. Successful iOS data
ZIP export does not establish an installed iOS executable template or build.
Captures remain **REQUIRES USER REVIEW** for subjective presentation quality.

**VERIFIED — live v0.2 acceptance:** bridge/plugin `0.2.0` was verified in the
real checkout. `godot_create_rig_lab({})` succeeded exactly once, creating the
seven-node scaffold in one editor action without saving. Normal Godot Undo
removed the complete scaffold and returned the previously clean scene to clean;
Redo restored it. Manual Save followed by scene close/reopen verified persistence.
AnimationPlayer remained empty. No unrelated scene/resource files changed.

The user restored and saved the lab as its intended empty-root baseline. Normal
Godot-authored scene/node identity metadata is retained; it is not test residue:

```ini
[gd_scene format=3 uid="uid://dbai77g0q7plj"]

[node name="TotolinaRigLab" type="Node2D" unique_id=1866938083]
```

The accepted file is 111 bytes. The writer gates on scene/root semantics, not
file size, literal bytes or absence of identity metadata. Targeted checks against
this normalized baseline passed: 33 Python/native transport tests (seven exact
baseline copies), 56 inspection plus 442 native rig checks, and four Android/iOS
data exports with exclusion/positive controls; 224 production/lab hashes and all
352 repository file hashes remained unchanged. Executable iOS export/device
behavior remains **NOT VALIDATED / REQUIRES MAC/iOS**; the executable iOS template
is missing.

## v0.3 automated acceptance — 2026-10-01

**VERIFIED:** Godot `4.7.2.stable.official.ed1daf0bf`, bridge/plugin `0.3.0`,
protocol `1`. All 155 Godot Python tests passed: 130 protocol/schema/transport
unit tests and 25 native transport/safety/public-writer tests, including three
real Windows graphical public-tool cases. The native runner passed 56 inspection,
442 v0.2 rig and 603 graphical animation assertions (1,101 total). Safe Create,
native Undo/Redo after editor frames, exact resource identity/disposal, clean and
dirty save points, disposable manual Save/Reopen, observer/queued-callback
settlement, replay/reconnect/session ordering and shared post-action faults were
verified. The entered-writer local cleanup edge was source reviewed; that exact
synchronous replacement callback was not separately fault-injected.

Attaching the native animation editor between Undo and Redo assigned `bend_tip`
after normal Redo frames: current animation remained empty, playback stopped and
Tip rotation `0`. This characterizes normal editor behavior outside the controlled
detached acceptance conditions; MCP does not intercept native history.

Regressions passed: 171 Photoshop Python tests, 165 UXP checks, 82 launcher
checks, two Kitchen runner tests, and the final Kitchen baseline (13 headless
plus 12 graphical suites; 11,044 checks). Four Android/iOS resource packages
passed exclusion/positive controls, with 140 native checks of the actual saved
public-writer inline rig/animation loaded from the controls. Both exclusion packs
contained zero addon entries and excluded all eight compiled/remap targets per
platform. Twelve addon source files matched final Kitchen/export/current copies;
230 production/config/resource hashes and the accepted empty lab were preserved.
The lab remains the 111-byte Godot-authored baseline shown above, with both UID
metadata fields intact and no generated rig or animation. New script `.uid`
files are intentional; test artifacts remain outside Git.

Windows test startup/file-publication issues were corrected in disposable test
support; final runs had zero failures. Machine-local configuration and credentials
were not edited. **NOT EXECUTED:** executable exports/device
behavior. **NOT VALIDATED / REQUIRES MAC/iOS:** executable iOS export/device
behavior; the iOS template is still missing. No production, project-settings,
export-preset, Photoshop or launcher implementation changed.

**VERIFIED — real-checkout v0.3 live acceptance:** bridge/plugin `0.3.0`,
prerequisite v0.2 rig creation and exactly one successful
`godot_create_rig_lab_animation({})` produced the exact `bend_tip` fixture above.
Native Undo removed only the animation, preserving the unsaved rig and dirty
scene; native Redo restored it. Manual Save and scene close/reopen verified
persistence. The user visually verified smooth bending and return to rest.
Final manual subtree deletion and Save restored the existing 111-byte empty
Godot-authored lab byte-for-byte, retaining `uid` / `unique_id`; no serialized
or Git-visible live-test residue remained. The controlled cycle kept the
AnimationPlayer editor detached and settled; the safety limitations above remain.
