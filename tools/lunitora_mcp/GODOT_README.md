# Lunitora Godot Animation MCP v0.3

This editor bridge exposes the three existing metadata tools, `godot_ping`,
`godot_get_editor_state`, and `godot_inspect_scene`, plus two fixed lab operations:
`godot_create_rig_lab` and `godot_create_rig_lab_animation`. All five accept exactly
`{}`; extra fields are rejected. Bridge and editor-plugin versions are **0.3.0**; the authenticated
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
enabled_tools = ['godot_ping', 'godot_get_editor_state', 'godot_inspect_scene', 'godot_create_rig_lab', 'godot_create_rig_lab_animation']
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
