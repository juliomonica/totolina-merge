# Rig Test Cat assembled idle proof

The isolated native scene is
`res://addons/lunitora_godot/labs/rig_test_cat_assembled_idle_lab.tscn`.
It contains 31 nodes, sixteen external textures, and no runtime scripts.
Open the scene, select `CharacterRoot/AnimationPlayer`, and preview `idle`.
Playback is opt-in; `RESET` restores the measured rest pose.

The original 25-node milestone `animation/rig-test-cat-assembled-idle-v0.1`
was visually accepted by the user. On 2026-10-03, the user gave final visual
approval to the complete sleeve decomposition and finished proximal-fur
treatment for this technical test character. The approved arms are
`READY_STRUCTURAL + READY_VISUAL` for this reviewed lab. Tiny proximal side-edge
flecks visible only at high magnification are an accepted, nonblocking test-art
limitation; this approval does not establish production-art readiness.

The final construction retains the current manually improved arm placement,
timing, keys, pivots and tail deformation. Three static attachment sprites per
side replace the earlier two cuff-only overlays. The approved physical stack
is frozen unless a new blocking visual defect is discovered.

This is an assembled animation proof using the accepted v0.5 techniques. The
v0.5 writers, public MCP schemas, pinned deformation specification and existing
deformation lab are unchanged. The existing addon export exclusion also covers
this scene. It is not integrated into gameplay.

## Assembly and measured registration

The hierarchy is:

```text
RigTestCatAssembledIdleLab
└── CharacterRoot
    ├── LowerFootL
    ├── LowerFootR
    ├── BodyMotion
    │   ├── TailRig
    │   │   ├── TailMesh
    │   │   └── TailSkeleton
    │   │       └── TailRoot
    │   │           └── TailMid1
    │   │               └── TailMid2
    │   │                   └── TailTip
    │   ├── ShoulderL
    │   │   └── UpperArmL
    │   │       └── ElbowL
    │   │           └── LowerArmPawL
    │   ├── ShoulderR
    │   │   └── UpperArmR
    │   │       └── ElbowR
    │   │           └── LowerArmPawR
    │   ├── Torso
    │   ├── HeadPivot
    │   │   └── Head
    │   ├── ScarfForeground
    │   ├── ArmSocketBackL
    │   ├── ArmSocketBackR
    │   ├── ArmCuffLipFrontL
    │   ├── ArmCuffLipFrontR
    │   ├── ArmSleeveNearWallL
    │   └── ArmSleeveNearWallR
    └── AnimationPlayer
```

All textures are external resources under
`addons/lunitora_godot/test_assets/rig_test_cat/`: `body/rig_test_cat_torso.png`,
`body/rig_test_cat_head_full.png`, `body/rig_test_cat_scarf_foreground.png`,
the four `arms/rig_test_cat_arm_upper_{l,r}.png` and
`arms/rig_test_cat_arm_lower_paw_{l,r}.png` files, the six attachments
`arms/rig_test_cat_arm_socket_back_{l,r}.png`,
`arms/rig_test_cat_arm_sleeve_near_wall_{l,r}.png` and
`arms/rig_test_cat_arm_cuff_lip_front_{l,r}.png`,
`legs/rig_test_cat_leg_lower_foot_{l,r}.png`, and `tail/rig_test_cat_tail.png`.
The existing full-front image is a visual reference only. The torso already
contains sleeves, upper trousers, scarf and visible cloak; separate upper-leg
or cape sprites would duplicate artwork.

Body-local coordinates use torso texture origin `(561,0)`. The common exclusive
sole baseline is torso-source `Y=1652`. `BodyMotion` rests at `(0,-1652)` beneath
the fixed ground origin. Default 540x960 preview placement is
`CharacterRoot.position=(270,850)`, uniform scale `0.3`.

The `L`/`R` labels preserve the existing node and source filenames; the current
manual placement displays the `L` lower arm on screen right and `R` on screen
left. They must not be mirrored or reassigned blindly.

| Registration | L source/node | R source/node |
| --- | --- | --- |
| Shoulder, body-local | `(-205.5,416)` | `(191,419)` |
| Shoulder, torso-source | `(355.5,416)` | `(752,419)` |
| Shoulder uniform scale | `0.75` | `0.75` |
| Upper sprite uniform scale | `0.4` | `0.4` |
| Upper source pivot | `(810,320)` | `(440,320)` |
| Elbow, upper-local | `(-385,680)` | `(410,670)` |
| Elbow measured rest rotation, radians | `0.87026` | `-0.507098504392337` |
| Lower source pivot | `(860,240)` | `(380,210)` |
| Lower accepted local position | `(1396.7734,-1646.1658)` | `(-1844.1476,-1055.0321)` |
| Lower accepted local rotation, radians | `-1.9765847` | `1.4105227` |
| Lower sprite uniform scale / z-index | `1` / `1` | `1` / `1` |
| Static foot, ground-local | `(-424,-477)` | `(87,-477)` |
| Foot scale / offset | `1` / `(0,0)` | `1` / `(0,0)` |

Right registration was measured independently. The accepted manual lower-sprite
placements above supersede the original v0.1 compensations, while preserving
the shoulder/elbow frames, source pivots and sprite scales. The torso, upper
sleeve and socket back remain behind the moving forearm; the sleeve near wall
and front cuff lip draw in front. The torso continues to occlude the shoulder
attachments.
The authored right elbow uses the native positive equivalent
`5.776086807250976` radians. This canonical representation avoids angular
interpolation changing its float32 rest matrix during RESET; it preserves the
measured orientation and all motion deltas modulo one full turn.

## Approved sleeve decomposition and artwork

Both arms use this back-to-front physical stack:

```text
sleeve exterior
→ socket back / far wall
→ moving forearm
→ near sleeve exterior wall
→ front cuff lip
```

The unchanged torso and upper-arm art supply the sleeve exterior. The socket
back supplies cavity depth, inner shading and the far wall behind the moving
forearm. The near wall supplies the foreground fabric that covers the inserted
forearm; the separate front lip contains only the near rim and minimal side
wrap. The lip has an open, transparent passage and no far/bottom inner rim,
rear cavity bowl or complete elliptical contour. Bringing the complete sleeve
forward remains a rejected construction because it reads as a closed tube.

| Attachment registration | L source/node | R source/node |
| --- | --- | --- |
| Canvas for each of the three PNGs | `153x163` | `143x162` |
| Top-left under BodyMotion | `(267,525)` | `(-412,526)` |
| Scale / offset / centered | `1` / `(0,0)` / `false` | `1` / `(0,0)` / `false` |

| Layer | L node | R node | Z-index |
| --- | --- | --- | --- |
| Socket back / far wall | `ArmSocketBackL` | `ArmSocketBackR` | `0`, after `Torso` |
| Moving forearm | `LowerArmPawL` | `LowerArmPawR` | `1` |
| Near sleeve exterior wall | `ArmSleeveNearWallL` | `ArmSleeveNearWallR` | `2` |
| Front cuff lip | `ArmCuffLipFrontL` | `ArmCuffLipFrontR` | `3` |

All six attachment sprites are uncentered, unanimated siblings under
`BodyMotion`, using the same fixed top-left registration per side. They inherit
breathing movement while remaining aligned with the unchanged torso sleeve.
They have no elbow or shoulder animation tracks. The old `CuffLipL`/`CuffLipR`
nodes and `rig_test_cat_arm_cuff_lip_{l,r}.png` assets are superseded by this
complete construction.

The lower-arm canvases remain exactly `1254x1254`, preserving the accepted
pivots, offsets, forearm axes and manual registration. Shaped hidden fur
extensions continue beneath the sleeve without an exposed planar cutoff or
terminating outline. The final fur treatment removes the unnatural transverse
brown band and smooths the earlier sliced/serrated interior markings. The final
RGB-only cleanup preserves every alpha byte, protected side-outline pixels and
all distal pixels at source `y >= 520` from the approved extended candidate.
Wrist and paw artwork remain unchanged. Tiny protected side-edge flecks remain
visible only at high magnification and were explicitly accepted for this test
character on 2026-10-03.

The final approved lower-arm PNG identities are:

| Filename | SHA-256 |
| --- | --- |
| `rig_test_cat_arm_lower_paw_l.png` | `0201892afb8d3a41af1951609ddf09c43104dc4e7a181a93a72512ef79421fbb` |
| `rig_test_cat_arm_lower_paw_r.png` | `fbff47d1986b088f0fca53a865a8df9972720b223a8c20f165fc647719128d51` |

No shader, per-frame mask, extra moving joint or generic authoring capability
is used. The accepted physical stack is frozen; asset count is not a target.

The fixed feet are outside `BodyMotion`. Torso/boot overlap is 85 rows left and
84 right at rest, retaining 81 and 80 rows at maximum breathing displacement.
The central boot attachment remains at least 62 pixels deep on both sides.

`TailRig.position=(174,410)` and uniform scale `0.5` transform the unchanged
source tail root `(160,1280)` to body-local `(254,1050)`, torso-source
`(815,1050)`. That point lies inside torso alpha 252, with a measured 54.23-pixel
opaque margin. Mesh and skeleton share this transform behind the body.
All 561 vertices/UVs, 1,024 ordered triangles, four weight arrays, bone paths,
rest transforms, explicit lengths and angles are reused from the v0.5 payload.
Native save/readback retains their normal Godot scalar precision.

Head registration stays `(0,306)`, scale `0.8`, source pivot `(627,1145)`.
The torso offset remains `(-561,0)`. The unanimated scarf sprite stays at offset
`(-139,238)`, unit scale, z-index `1`, with the accepted texture and import
settings. The face is baked into the unchanged head texture.

## Native timeline

`idle` is 6.0 seconds, `LOOP_LINEAR`, ten continuous value tracks and 50 keys.
Every track has keys at `0 / 1.5 / 3 / 4.5 / 6` seconds and transition `-2.0`
(the accepted quadratic ease-in-out). Angular interpolation uses
`INTERPOLATION_LINEAR_ANGLE`; the two Y tracks use linear interpolation with
that easing. Explicit first/final keys are identical. `RESET` has one exact
rest key at time zero for each of the ten animated properties: ten tracks and
ten keys, restoring the exact authored rest pose.
RESET uses matching interpolation types. Angular-oracle comparisons wrap
equivalent angles and respect native float32 storage; RESET must restore the
authored native matrices exactly.

| Animated property | Rest | Key deltas in timeline order |
| --- | --- | --- |
| BodyMotion Y | `-1652` px | `0,-2,-4,-2,0` px |
| HeadPivot Y | `306` px | `0,0,-2,-1,0` px |
| Left shoulder rotation | `0` | `0,1.5,0,-1.5,0` degrees |
| Left elbow rotation | `0.87026` radians | `0,2,1,0,0` degrees |
| Right shoulder rotation | `0` | `0,-1,0,1,0` degrees |
| Right elbow rotation | `5.776086807250976` radians | `0,-2,-1,0,0` degrees |
| TailRoot rotation | `0` | `0,1,0,-1,0` degrees |
| TailMid1 rotation | `0` | `0,2,0,-2,0` degrees |
| TailMid2 rotation | `0` | `0,3,0,-3,0` degrees |
| TailTip rotation | `0` | `0,4,0,-4,0` degrees |

No animation tracks target feet, scarf, sleeve attachments or facial properties.
There is no IK,
physics, facial animation, cape deformation, AnimationTree or generic rig
authoring framework. Upper arms, torso, head, scarf, tail and feet PNGs are
unchanged by the final arm integration. Only the two lower-arm PNGs and the
six arm-specific attachment PNGs supply the approved artwork correction.

## Focused validation and visual review

The focused runner uses the same NumPy/Pillow test dependencies as the existing
deformation graphical oracle. Supply an installed Godot executable and a fresh
output directory outside the repository:

```text
python tests/godot_mcp/run_assembled_idle_validation.py --godot <godot-executable> --output <fresh-evidence-directory>
```

It imports only a disposable project with isolated userdata and no MCP plugin.
It checks the closed 31-node hierarchy/timeline, accepted manual lower-arm
placement, registered attachment identity/size/ordering, unchanged tail payload,
static feet/scarf/sleeve attachments, native interpolation, CPU/GPU tail
deformation, RESET/replay, native
Save/Reopen/replay and 20 continuous normal-playback loops. `--quick` is only an
iteration aid and does not establish the realtime loop proof.

Required evidence includes 390x844, 405x720 and 540x960 phone poses, both sides
of the loop boundary, shoulder/elbow/neck/boot/tail-attachment closeups and a
six-second review GIF. Elbow closeups target the actual sleeve/forearm sockets
at torso-source `(890,650)` and `(217,650)`, rather than the displaced technical
elbow origins. Generated evidence and caches are outside the repository.

### Historical v0.1 validation

The completed Windows run on Godot 4.7.2, Mobile/D3D12, passed 1,736,788 native
assertions, 19,262 native interpolation samples, 1,373 tail geometry samples
and 25 GPU/CPU tail comparisons. Normal playback completed 20 continuous loops
over 17,274 checked frames (approximately 120 seconds), followed by full replay
cycles after RESET and after native Save/Reopen.

All feet transforms stayed fixed. RESET and replay restored exact native rest
transforms; Save/Reopen retained identical rest pixels and replay transforms.
Tail triangle area ratios remained positive between 0.76466 and 1.24104, with
no collapsed or inverted triangles. The maximum native property comparison
error was one float32 step at body Y (0.0001220703125 pixels); GPU/CPU raster
comparisons differed by at most 5/255 per channel.

The run captured 168 PNGs, including 21 phone poses and 35 attachment closeups,
plus the review GIF and two contact sheets. All three phone sizes passed
connected-silhouette, unclipped-bounds and static-feet checks. Twenty shoulder/
elbow coverage checks and five scarf/neck checks passed. First/final poses were
pixel-identical at every phone size. Frames at 6 seconds +/- 1/60 second showed
only small raster changes (maximum 9/255 per channel; mean below 0.002/255),
passing the loop-pop check. Graphical inspection found the attachments covered;
the subsequent user visual review passed and accepted the assembled idle.

The original placeholder art limitations motivated the later artwork and
registration review. They are historical v0.1 findings, not a requirement to
retain a closed sleeve or exposed forearm cap.

### Historical initial cuff-sandwich integration

Before integration, the disposable candidate was graphically compared with a
thin lip, a bounded mask and a complete foreground sleeve. The selected two
sparse overlays passed 6,001 numeric time samples and 3,510,585 complete-cap
ray samples. Native captures covered all three phone sizes, intermediate poses
and loop boundaries; continuous playback, exact RESET and native
Save/Reopen/replay passed. The user approved this candidate for implementation.

The initial integrated Windows scene passed the full focused runner on Godot 4.7.2,
Mobile/D3D12: 1,813,887 native assertions, 19,261 interpolation samples,
1,373 tail geometry samples and 25 GPU/CPU comparisons. Twenty continuous
loops checked 17,271 frames over 119.948 seconds. Replays after RESET and after
Save/Reopen checked 857/865 frames over 5.963/5.987 seconds. The run captured
168 PNGs. RESET restored exact rest, Save/Reopen retained identical rest pixels
and replay transforms, feet and cuff overlays stayed static, and all three
phone sizes retained pixel-identical loop endpoints. Unchanged timing/keys and
the v0.5 tail topology/weights passed the native contract checks.

Its supplemental captures matched that approved candidate pixel-for-pixel
at all 171 compared views: 30 phone poses, 20 sleeve/forearm closeups and 121
full-cycle frames. A further 242 native arm-closeup frames show both complete
six-second cycles. Existing manual placement and all original 25 node
transforms were preserved through playback, RESET and Save/Reopen/replay.
All generated evidence and caches remain outside the repository.

### Historical proximal-retouch validation

The retouched scene passed the full Windows native runner: 1,813,740 assertions,
19,254 interpolation samples, 1,373 tail geometry samples and 25 GPU/CPU
comparisons, with 168 PNG captures. Twenty continuous loops checked 17,265
frames over 119.947 seconds. Replays after RESET and Save/Reopen checked
857/864 frames over 5.956/5.999 seconds. Exact rest restoration, identical
Save/Reopen rest pixels, fixed feet/cuff overlays, unchanged manual placement
and pixel-identical loop endpoints passed again.

The two PNGs retain every original alpha value; the complete 27-node scene is
byte-identical to the accepted geometry version. A further 242 native
arm-closeup frames show both full cycles with the installed fur treatment.
Earlier Codex inspection reported connected forearms and removal of the former
dark rails. The user's subsequent rejection of the visible proximal line
overrides that visual assessment. These results establish structural readiness;
both lower-arm PNGs were then `READY_STRUCTURAL + NEEDS_ART_EDIT`. This rejected
27-node treatment is superseded by the final approved 31-node construction and
finished fur artwork above; its numeric checks did not establish visual
acceptance.

### Final approved disposable proof

The complete 31-node candidate was reviewed at rest, 1.5 seconds, intermediate
poses, extrema and both sides of the loop boundary at all three phone sizes.
Native high-resolution elbow captures sampled every 0.1 seconds from 0 through
6 seconds: 61 poses per arm. The proof produced 412 captures, passed 3,058
checks and inspected 1,147 ordinary playback frames. All generated candidates,
evidence, scripts and caches remain outside the repository.

Rendered review found continuous fur entering a hollow sleeve, with no exposed
proximal cutoff, transverse band, gap, duplicate cuff contour or new pouch
collision. The final human visual approval on 2026-10-03 accepts this complete
decomposition and fur treatment for the technical test character, including the
small high-magnification side-edge flecks described above. The integrated
repository scene now reproduces this approved candidate exactly, as verified
by the native comparisons below.

### Final integrated validation

The actual 31-node repository scene passed native graphical validation with
685 PNG captures and 8,229 assertions. All 183 representative and complete-cycle
pixel comparisons matched the approved disposable candidate exactly, including
61 high-resolution poses per arm. At each phone size, ordinary playback passed
an initial six-second loop, replay after RESET and replay after native
Save/Reopen: nine loops and 3,463 checked frames. RESET restored exact rest;
Save/Reopen preserved rest pixels, registration and animation signatures.

The full repository oracle passed 1,891,015 native assertions, 1,373 tail
geometry samples and 25 GPU/CPU comparisons, producing 168 PNGs. Twenty
continuous normal-playback loops checked 17,271 frames over 119.958 seconds.
Replay after RESET checked 857 frames over 5.965 seconds; replay after
Save/Reopen checked 865 frames over 5.985 seconds. Tail triangle area ratios
stayed positive from 0.7646575292 to 1.2410356127, with no collapsed or inverted
triangles. Together, the two integrated batches produced 853 PNG captures,
passed 1,899,244 assertions and checked 22,456 frames across 31 ordinary cycles.

The unchanged six-second `LOOP_LINEAR` idle retains ten tracks / 50 keys;
RESET retains ten tracks / ten keys. Accepted transforms, static feet and
sleeve attachments, head/scarf behavior and the v0.5 tail payload passed the
native contracts. Independent rendered inspection of both full arm cycles and
all phone key poses found no new gap, cutoff, full-ring/closed-tube appearance,
duplicate cuff contour or pouch collision. The approved tiny high-magnification
edge flecks remain unchanged. Final human approval for this test character
therefore remains applicable to the integrated result.

All repository inputs retained their expected hashes through validation.
Evidence, disposable projects and caches remain outside the repository. An
external adapter filtered only the pre-existing Windows root-certificate
discovery diagnostic for the oracle run; raw logs were retained and the
repository Python runner was unchanged.

Further production-art refinement remains separate work. Revisit the frozen
decomposition only if a new blocking visual defect is discovered.
Android hardware and Mac/iOS behavior remain separate device validation; this
lab provides desktop animation evidence only.
