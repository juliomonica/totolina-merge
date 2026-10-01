# Lunitora Godot Animation MCP v0.1

This editor bridge exposes exactly three metadata tools: `godot_ping`,
`godot_get_editor_state`, and `godot_inspect_scene`. Every tool accepts exactly
`{}`. The Codex-owned Python stdio server listens on **127.0.0.1:43128**;
Godot's `WebSocketPeer` connects from the enabled editor plugin. Photoshop's
server, implementation, operator launcher, and **43127** port are separate.

The v0.1 editor operation allowlist contains no writes. It cannot change nodes,
resources, selection, animation playback, project settings, or undo/redo history;
it cannot create, delete, reparent, or save anything. Inspection reads the current
edited scene through public editor APIs. It does not instantiate production
scenes or inspect arbitrary script properties. Nothing in this bridge replaces
the existing Totolina presentation or gameplay architecture.

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
enabled_tools = ['godot_ping', 'godot_get_editor_state', 'godot_inspect_scene']
```

On this PC the user configuration is `C:\Users\julio\.codex\config.toml`.
Preserve the existing Photoshop entry and all unrelated configuration. Do not
put credentials in the config, command arguments, or environment. Restart the
Codex connection/app as needed to discover the newly configured server; a file
edit alone does not prove this chat has loaded or called it.

Open this project using:

```powershell
& 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64.exe' --editor --path 'D:/Development/LunitoraGames/totolina-merge'
```

`project.godot` enables `addons/lunitora_godot/plugin.cfg`. Godot can start before
Codex: the plugin waits for the credential and listener, then authenticates. It
reconnects after Codex restarts or the editor is closed/reopened. Disabling the
plugin closes its connection; enabling it starts connection attempts again.
Only one owning Python listener and one authenticated editor are supported.
A port conflict returns an explicit availability error and never selects a new
port or terminates the existing listener.

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
& ./tools/lunitora_mcp/.venv/Scripts/python.exe -B ./tests/godot_mcp/run_native_validation.py --godot 'D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64_console.exe'
```

This runner copies only the addon and fixture into a disposable project, enables
the plugin there, checks actual editor startup/import/parsing, and requires
exactly 56 successful native inspection/security checks. Logs and editor data
remain in the printed temporary artifact directory.

The export gate executes Godot's real Android and iOS **data-package** exporters
using the exact repository presets in an isolated runtime-resource copy. It verifies
the emitted ZIP entries and any compiled resources reached by addon remaps.
The snapshot includes tracked and new nonignored runtime files, refuses redirected
resource paths, and omits local credentials, virtual environments, caches, and
source artwork. The initial CSV import uses the existing Kitchen runner's
translation bootstrap; actual project settings are restored for every export.
Then it removes only the addon exclusion in each disposable preset as a positive
control and requires the addon scripts and nested resources to appear. A runtime
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

For final acceptance, call the three tools through **Codex with this project open
in the actual Godot editor**. Check both startup orders, restart, close/reopen,
plugin disable/enable, no scene, saved/dirty/unnamed tabs, selections, and scene
switching. Compare scene/resource files, selection, dirty state, and undo history
before/after read-only calls. Keep Photoshop available during the live check.
These checks must be reported separately from fake-peer, SDK stdio, and headless
fixture tests.

## Validation status language

Use **VERIFIED** only for checks actually executed successfully, **NOT EXECUTED**
for checks not run, and **REQUIRES USER TEST** for remaining interactive acceptance.
Rendered animation quality remains **REQUIRES USER REVIEW** unless the user has
reviewed it. Mobile behavior remains **REQUIRES ANDROID DEVICE** or
**REQUIRES MAC/iOS**; desktop and ZIP tests do not establish device acceptance.

No TotolinaRigV2, node rigging, animation playback/authoring, resource writes,
production migration, new operator aliases, Git staging, commits, or pushes are
part of v0.1.

## Implementation file manifest

The implementation modifies exactly these three previously tracked files:

```text
export_presets.cfg                  Android/iOS addon exclusions only
project.godot                       New editor plugin enablement only
tools/lunitora_mcp/README.md         Link to this Godot guide only
```

It creates these 25 Git-visible files:

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
The toolkit lock and production scenes, scripts, resources, and assets are
preserved.

## Recorded validation — 2026-09-30

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
credential probes are absent. All seven current addon files matched the tested
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
