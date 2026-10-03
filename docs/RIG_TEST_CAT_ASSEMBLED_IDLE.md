# Rig Test Cat assembled idle proof

The isolated native scene is
`res://addons/lunitora_godot/labs/rig_test_cat_assembled_idle_lab.tscn`.
It contains 25 nodes, ten existing accepted textures, and no runtime scripts.
Open the scene, select `CharacterRoot/AnimationPlayer`, and preview `idle`.
Playback is opt-in; `RESET` restores the measured rest pose.

Milestone `animation/rig-test-cat-assembled-idle-v0.1` is visually accepted by
the user. The accepted timing, transforms, pivots, artwork, hierarchy and tail
deformation are frozen for this review.

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
    │   └── ScarfForeground
    └── AnimationPlayer
```

All textures are immutable external resources under
`addons/lunitora_godot/test_assets/rig_test_cat/`: `body/rig_test_cat_torso.png`,
`body/rig_test_cat_head_full.png`, `body/rig_test_cat_scarf_foreground.png`,
the four `arms/rig_test_cat_arm_upper_{l,r}.png` and
`arms/rig_test_cat_arm_lower_paw_{l,r}.png` files,
`legs/rig_test_cat_leg_lower_foot_{l,r}.png`, and `tail/rig_test_cat_tail.png`.
The existing full-front image is a visual reference only. The torso already
contains sleeves, upper trousers, scarf and visible cloak; separate upper-leg
or cape sprites would duplicate artwork.

Body-local coordinates use torso texture origin `(561,0)`. The common exclusive
sole baseline is torso-source `Y=1652`. `BodyMotion` rests at `(0,-1652)` beneath
the fixed ground origin. Default 540x960 preview placement is
`CharacterRoot.position=(270,850)`, uniform scale `0.3`.

| Registration | Left | Right |
| --- | --- | --- |
| Shoulder, body-local | `(-205.5,416)` | `(191,419)` |
| Shoulder, torso-source | `(355.5,416)` | `(752,419)` |
| Shoulder uniform scale | `0.75` | `0.75` |
| Upper sprite uniform scale | `0.4` | `0.4` |
| Upper source pivot | `(810,320)` | `(440,320)` |
| Elbow, upper-local | `(-385,680)` | `(410,670)` |
| Elbow measured rest rotation, radians | `0.87026` | `-0.507098504392337` |
| Lower source pivot | `(860,240)` | `(380,210)` |
| Lower fixed compensation, radians | `-0.87026` | `0.507098504392337` |
| Static foot, ground-local | `(-424,-477)` | `(87,-477)` |
| Foot scale / offset | `1` / `(0,0)` | `1` / `(0,0)` |

Right registration was measured independently. Its lower-art axis landmarks
`(380,210)` and `(780,930)` define `-atan2(400,720)` for the elbow rest frame;
the lower sprite cancels that frame at rest. Both lower sprites draw behind
their upper sleeves. The torso then occludes the shoulder attachments.
The authored right elbow uses the native positive equivalent
`5.776086807250976` radians. This canonical representation avoids angular
interpolation changing its float32 rest matrix during RESET; it preserves the
measured orientation and all motion deltas modulo one full turn.
Graphical source measurements retain upper/lower opaque intersection of at
least 2,568 pixels on the left and 3,025 on the right over the proposed keys.

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
rest key at time zero for each of the ten animated properties.
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

No animation tracks target feet, scarf or facial properties. There is no IK,
physics, facial animation, cape deformation, AnimationTree or generic rig
authoring framework. Source PNGs are unchanged.

## Focused validation and visual review

The focused runner uses the same NumPy/Pillow test dependencies as the existing
deformation graphical oracle. Supply an installed Godot executable and a fresh
output directory outside the repository:

```text
python tests/godot_mcp/run_assembled_idle_validation.py --godot <godot-executable> --output <fresh-evidence-directory>
```

It imports only a disposable project with isolated userdata and no MCP plugin.
It checks the closed native hierarchy/timeline, unchanged tail payload, static
feet/scarf, native interpolation, CPU/GPU tail deformation, RESET/replay, native
Save/Reopen/replay and 20 continuous normal-playback loops. `--quick` is only an
iteration aid and does not establish the realtime loop proof.

Required evidence includes 390x844, 405x720 and 540x960 phone poses, both sides
of the loop boundary, shoulder/elbow/neck/boot/tail-attachment closeups and a
six-second review GIF. Generated evidence and caches are outside the repository.

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

The arm exports remain accepted technical placeholder artwork. Baked torso
sleeves conceal much upper-arm movement; sleeve contour duplication and the
small paw proportions remain documented future art-quality work. They do not
block this accepted animation milestone or justify additional rig complexity.
Subjective timing, silhouette and overlap are USER ACCEPTED. Android hardware
and Mac/iOS behavior remain separate device validation; this lab provides
desktop animation evidence only.
