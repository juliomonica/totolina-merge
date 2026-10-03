# Lunitora Machine Setup

This is the source of truth for the portable machine setup/check workflow.
The small [requirements catalog](../tools/lunitora_requirements.json) describes
application purpose, supported platforms, required/optional capabilities, version
policies and manual actions. Python package pins remain in the existing
[toolkit project](../tools/lunitora_mcp/pyproject.toml) and
[dependency lock](../tools/lunitora_mcp/requirements.lock); the catalog does not
replace them or install desktop applications/mobile SDKs.

## First-Time Photoshop / Art Machine Setup (Windows)

UXP Developer Tool (UDT) is Adobe's utility for loading, developing, debugging and packaging UXP plugins.

This workflow covers application installation, development-plugin loading, local
credential setup, manual panel pairing and live MCP verification as separate stages.
Lunitora detects applications; it never installs Adobe software or enables Developer
Mode. Run repository commands from Git Bash at the checkout root.
`<repo-root>` below means your actual checkout, for example
`D:\Development\LunitoraGames\totolina-merge` on the current Art machine.

1. Install/open Adobe Creative Cloud Desktop and sign in with your Adobe ID.
2. Install supported Adobe Photoshop (repository manifest minimum 27.10.0; validated host 27.10) through Creative Cloud. Photoshop runs Art; Lunitora never silently installs it. Core/Game do not require Photoshop.
3. In Creative Cloud, All apps, search for UXP Developer Tools and choose Install. UXP Developer Tool (UDT) is Adobe's utility for loading, developing, debugging and packaging UXP plugins. UDT is needed for development loading and git art-dev; daily use of an installed packaged plugin does not require UDT. Core/Game do not require UDT.
4. Launch UDT and enable Developer Mode when prompted. Adobe currently requires administrator privileges for UDT and elevated permission to enable Developer Mode. Approve Adobe's prompt yourself; Lunitora does not elevate Adobe applications.
5. Launch Photoshop. For development loading, enable Edit > Preferences > Plugins > Enable Developer Mode if needed; protect unsaved work before any requested restart.
6. With Photoshop running, in UDT choose Add Plugin, select <repo-root>\tools\lunitora_mcp\bridges\photoshop_uxp\manifest.json, select the Photoshop host, then Load. Require successful loading.
7. In Photoshop open Plugins > Lunitora Photoshop Bridge.
8. From the repository root run python tools/lunitora_setup.py. Local credential setup is separate from Photoshop-panel pairing. Follow the reported command: --migrate-photoshop-auth for valid legacy mixed-directory storage, --repair-photoshop-auth for repairable protection, or --pair-photoshop for first-time private create/import or valid-token reuse. Run each command separately.
9. The protected Lunitora bridge credential is normally configured once per machine (one-time pairing per machine). Existing valid protected credentials are preserved; no rotation is needed for this workflow.
10. Privately open tools\lunitora_mcp\.local\photoshop-auth\pairing-token.txt in a local editor after setup; do not print it. The file is normally tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt. If setup confirms an existing reviewed protected legacy credential is in use, privately open `<repo-root>/tools/lunitora_mcp/.local/pairing-token.txt` instead; do not create a second token.
11. Manually enter the SAME bridge password/token once into the Photoshop panel's password input, currently labelled Pairing token. The panel only accepts a token; it does not generate or reveal one. Close the editor without changes and clear the clipboard. Never paste the credential into chat, logs, screenshots, tracked JSON/TOML/configuration or environment files.
12. Choose Connect / Reconnect in the panel. A listener may not be available until the next step; startup retry/disconnected status is not proof of bad pairing.
13. After active Codex Desktop work finishes, run git art-refresh from external Git Bash. Review project trust/reload explicitly if requested. This restarts Desktop/MCP; Photoshop stays open. Require panel Connected; reconnect if needed. Require Pairing saved securely on this computer when Adobe secure storage is available.
14. From Codex through the configured Photoshop MCP run one read-only photoshop_ping({}). Require ok=true, connected=true and the expected Photoshop host/version. Setup/check do not run this operation.
15. Confirm Art readiness only after applications, development loading (or packaged installation), protected local credential, panel pairing and live MCP verification are accepted independently. Installation or local credential success alone is not full Art readiness.

The manifest is `tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json`; it declares
Photoshop (`PS`), minimum host `27.10.0`, API version 2, panel **Lunitora Photoshop
Bridge**, and main file `index.html`. The existing panel uses a password input
labelled **Pairing token**, not a visible field literally labelled Password.
Installing a packaged plugin is a separate alternative to development loading;
UDT is needed for development and packaging, not daily packaged-plugin use.

Read-only doctor:

```bash
python tools/lunitora_setup.py --check
```

The report separates Photoshop installation, UDT installation, Developer
Mode/plugin loading, protected bridge credential, Photoshop-panel pairing and
live MCP connection. Installation detection and local credential validation can
be observed locally. Developer Mode/loading, panel pairing and live authentication
remain **NOT CHECKED** until manually accepted. `next first time step` identifies
missing apps/credential preparation or the manual steps requiring verification;
an unobserved manual state is not reported as missing or complete. `CONFIGURED`
means local configuration, not full Art readiness. Missing Photoshop/UDT never
block unrelated Core/Game workflows. Doctor does not launch applications, change
configuration, request secrets or call Photoshop MCP.

For migration/repair follow only the specific command reported by setup. Never
rotate a valid token to complete this checklist, and leave a migrated legacy
credential untouched until separate cleanup is authorized after live acceptance.
Native macOS credential protection remains **REQUIRES MAC**; these Windows
instructions do not imply portable Windows ACL protection.

Verified against repository implementation and Adobe guidance on 2026-10-03:
[Set up developer tools](https://developer.adobe.com/uxp/guides/how-to/developer-tools/)
(Creative Cloud installation, first-launch Developer Mode and admin/elevation),
and [Use the UXP Developer Tool](https://developer.adobe.com/uxp/guides/how-to/udt-deep-dive/)
(running host required for development loading).


## v0.8 Milestone Acceptance

The accepted migration status for `tooling/godot-launcher-v0.8` is:

| Area | Status |
| --- | --- |
| Windows Core/Game | **LIVE ACCEPTED** |
| Art workflow | **REQUIRES ART MACHINE** — validate on the Photoshop machine |
| macOS live behavior | **REQUIRES MAC** |
| Android executable/device behavior | Separate validation; **REQUIRES ANDROID DEVICE** |
| Legacy PowerShell | Temporary rollback/reference code until Art parity is proven; outside the supported operator workflow |

Windows acceptance on 2026-10-02 covers the host-Python migration, clean Git Bash
output, the visible correct-checkout Godot editor, matching-editor reuse and
`git godot-refresh` preservation of the editor/unsaved work with MCP reconnect.
The configured `lunitora_godot` MCP also completed one read-only
`godot_ping({})` in this review conversation: `ok=true`, `connected=true`,
`read_only=true`, protocol `1`, Godot `4.7.2-stable (official)`, bridge/plugin
`0.5.0`, project `Totolina Merge`, round trip `34.456 ms`, no error.
That call invoked no writer and changed no files or editor state.

This supersedes earlier pending Windows workstation acceptance below. Historical
phase counts and execution boundaries remain labeled as such. Fresh-machine
network installation, actual lingering-MCP recovery, Art pairing/processing,
macOS native behavior and executable mobile/device tests remain separate.
Do not remove or rewrite the retained PowerShell implementation before Art parity
is proven and its retirement is separately reviewed.
No current Git alias invokes it: all seven use host Python and
`tools/lunitora_launcher.py`. Normal setup and operation require no manual
PowerShell commands. If Art-machine validation exposes a Python blocker, handle
recovery deliberately through Git/version history and a reviewed correction or
rollback; do not introduce user-facing PowerShell commands as a recovery workflow.

### Final Scope Pruning

The v0.8 commit candidate restores these files byte-for-byte to current `main`:
`tools/lunitora_mcp/modules/godot/protocol.py`,
`tools/lunitora_mcp/tests/test_godot_deformation_lab.py`,
`tools/operator_launcher/common.ps1`, and
`tools/operator_launcher/tests/test_godot_launcher.ps1`.
The untracked `tools/operator_launcher/tests/test_godot_output_detachment.ps1`
is removed. The retained PowerShell implementation stays at its baseline; clean
Godot stdout/stderr detachment and log cleanup belong to the Python launcher.
Python depends only on the legacy local configuration for migration, not these
PowerShell implementation or test changes. Accepted host-Python functionality
and Windows Core/Game live evidence remain applicable.
The complete candidate against `main` has 5 modified, 43 new/untracked and zero
deleted files (48 total); no PowerShell or Godot P3 implementation diff remains.

### Deferred Tiny Tooling Follow-Up

Clarify `LAB_SKELETON_EDITOR_BUSY` wording to name both `TailMesh` and
`ScarfForeground`, with a targeted diagnostic regression in
`tools/lunitora_mcp/tests/test_godot_deformation_lab.py`. This behavior-neutral,
nonblocking Godot P3 correction is deferred and excluded from the host-Python
bootstrap/launcher milestone; `protocol.py` retains the current `main` wording.

## Setup And Check

Install these two bootstrap prerequisites first:

- **Git**, available to the command shell. Git for Windows with Git Bash is the
  validated Windows workflow.
- **Supported standalone Python 3.12 x64**; the managed MCP venv is not a substitute.

After those prerequisites exist, `python tools/lunitora_setup.py` is the
one-command Lunitora bootstrap from the current checkout root. The second command
below is the read-only doctor:

```sh
python tools/lunitora_setup.py
python tools/lunitora_setup.py --check
```

Setup detects missing Git and instructs the user to install Git, then rerun the
bootstrap. It probes Python version and architecture (64-bit), rejecting host
candidates outside Python 3.12 or with 32-bit architecture. If no supported
standalone host exists, it instructs the user to install Python 3.12 x64 alongside
the current Python, then rerun the bootstrap. It never downloads or installs Git
or Python, or changes PATH. Python must already exist to start the command at all.

Setup validates the standalone host independently of the toolkit environment.
Select installed
application paths explicitly when discovery is ambiguous. Do not use Python
bundled with another application or copy another machine's virtual environment.

Setup is an explicit operation. Check reports existing configuration and readiness
without creating an environment, installing dependencies, launching/closing
applications, changing aliases, or provisioning credentials. Neither operation
proves live MCP connectivity or device behavior.

Setup, the launcher and their operator modules use only the standard library.
An initial invocation from another Python/venv may hand off once to the validated
standalone host, never to the managed MCP environment. Windows COM/process
discovery and protected credential storage use native APIs through `ctypes`.

The managed MCP payload remains `tools/lunitora_mcp/.venv`; a healthy
Python 3.12 environment is reused, not recreated. Explicit environment setup uses
the checked-in lock and checks dependency/import readiness. Windows-specific
dependencies have platform markers; that alone does not port Windows MCP
authentication or native application control to macOS.

Machine-specific configuration is ignored at `tools/.lunitora/config.json`.
Schema version 1 records `schema_version`, `repository_root`, `platform`, and
`applications`. Nullable entries keyed by `desktop`, `godot`, `photoshop`, and
`udt` contain validated `kind`, `path`, `version`, `identity`, and optional
Desktop `aumid` metadata. Missing optional
applications are reported as capabilities, not a failure of Core setup. Paths and
local configuration never belong in the committed requirements catalog.
If local configuration is malformed or belongs to a different checkout/platform,
explicit setup offers a confirmed rebuild. It preserves the exact prior bytes in
an ignored `config-invalid-<unique-id>.json` backup and validates fresh selections;
it never imports unverified fields. Declining, daily commands and `--check` leave
that configuration untouched. An invalid legacy configuration is also retained.

Setup installs only repository-local aliases for these existing commands:

```text
git art
git art-refresh
git art-dev
git dev
git dev-refresh
git godot
git godot-refresh
```

All seven aliases call host Python plus `tools/lunitora_launcher.py`. Existing
PowerShell scripts are retained temporarily as rollback/reference code until Art
parity is proven. Current aliases do not invoke them, and they are not part of the
supported operator workflow. No manual PowerShell commands are required for normal
setup or operation. No global Git
configuration, shell profile, startup service or scheduled task is changed.
Application ownership, safe reconnect and one-attempt launch behavior remain
part of the launcher contract.

Windows alias values use the same pattern for each of the seven modes:

```text
!'C:/installed host Python/Python312/python.exe' -B "./tools/lunitora_launcher.py" godot
```

The absolute host path is validated and shell-quoted; the launcher path is
checkout-relative. Paths containing spaces work. No alias references the MCP venv,
and no activation or
shell PATH changes are needed. `-Check`/`--check` on a daily alias is also read-only;
the authoritative whole-machine doctor remains the setup command with `--check`.
Runtime repair is deterministic and noninteractive. A valid saved selection wins;
an invalid selection is repaired only when exactly one validated installation is
found. Otherwise the command stops and directs the user to rerun setup.

### Managed Environment Repair

| Environment state | Setup behavior |
| --- | --- |
| Absent | First-time creation with validated host Python, pinned installation and verification |
| Healthy / reuse | Reuse without recreation or reinstalling packages, including while MCP servers use it |
| Unhealthy / repair | Repair only with verified metadata/base-Python provenance and a proven unused environment |
| In use / ambiguous | Defer required repair; only explicitly approved, verified MCP-only recovery can unblock it |

An absent venv is created using validated host Python, then the exact MCP lock is
installed and imports/`pip check` verified. An unhealthy unused venv is repaired;
healthy reruns do not recreate it or reinstall packages. Missing/unsafe venv
metadata is not guessed or overwritten. A broken managed interpreter can be
repaired only with verified standalone base-Python provenance.

Process-use inspection itself runs on host Python. Setup/current probe processes,
unrelated Python and incidental repository path arguments are not blockers.
Live exact-checkout venv users are blockers; unavailable/changing identity is an
explicit ambiguous state and remains fail-closed. Diagnostics list only role,
PID and executable, never arbitrary command lines or secrets.

When a repair is needed, interactive setup can offer one bounded recovery pass
for strictly proven same-checkout Godot/Photoshop MCP processes. It pins every
PID/birth/image/argv identity before asking `Stop these verified Lunitora MCP
processes and continue? [y/N]`. Only explicit `y`/`yes` permits shutdown. All
identities are revalidated before any stop; child-before-wrapper termination and
a shared five-second exit wait are bounded. A fresh complete use-inspection must
prove the environment free before mutation. Unknown processes, ambiguous identity,
unrelated Python, Godot Editor and Desktop are never recovery targets. Decline,
noninteractive input or uncertainty defers repair without retry loops.

Deferred repair performs only read-only local readiness inspection; configured
Core/Game remain `PARTIAL`, not falsely missing. Daily aliases remain executable
when the managed venv is absent/broken but return an actionable setup instruction
without launching Desktop into it. They never prompt for recovery. `--check`
never stops processes, requests credentials or writes configuration.

## Capability Boundaries

| Capability | Configuration Requirements | Separate Acceptance |
| --- | --- | --- |
| Core | Git and standalone Python 3.12; checked toolkit environment | Actual Desktop-owned MCP startup/configuration/authentication |
| Game | Official Godot 4.7.2 stable editor | Editor/MCP connectivity, gameplay and graphical review |
| Android | Godot, compatible JDK, Android SDK and matching executable export templates | Signing, APK/AAB creation, installation and physical device behavior |
| iOS | macOS, full Xcode/iOS SDK, Godot and matching executable export templates | Apple account/team, signing/provisioning, native build and devices |
| Art | Photoshop 27.10+ and reviewed UXP bridge; pairing remains manual | Live processing and human review of every staging candidate |

Codex Desktop owns configured stdio MCP processes, including `lunitora_godot`.
Desktop is required for the seven Desktop-owned launch/refresh workflows; it is
not required merely to prepare/check the repository Python environment.
The launcher never starts a parallel Python MCP server. Photoshop being absent
does not prevent Game use; no connected Android device does not prevent Core/Game
use. UXP Developer Tool (UDT) is Adobe's developer utility for loading, developing
and debugging the Lunitora UXP Photoshop plugin. Photoshop is required to run
Art; UDT is required for developer plugin loading and `git art-dev`, but not daily
use of an already installed packaged plugin. Node is optional for JavaScript mock tests and requires no
npm packages. Git LFS is required only for files actually tracked with LFS.

`READY`/`CONFIGURED` in the checker mean configuration readiness only. They do not
mean a live application, MCP request, export or physical-device test passed.
Android/iOS resource-package controls use Godot's `--export-pack`; these controls
need no SDK, signing, device or executable template and must not be reported as
APK/IPA proof.

## Phases 1-3 Scope

The bounded implementation provides shared configuration/requirements policy,
Windows-native launcher support, a macOS metadata boundary, explicit Python
environment setup, repository-local aliases and configuration checks.

Phases 1-3 preserved existing MCP configuration and credentials. Windows live
Git Bash acceptance subsequently passed on 2026-10-02: clean terminal output,
matching editor reuse and `godot-refresh` preservation/reconnect were accepted.
Missing Photoshop and UDT are correct on this machine and did not block Game.
Phase 4 now adds the bounded provisioning below. Install/pair the installed
Photoshop bridge explicitly using the applicable
[Photoshop](../tools/lunitora_mcp/README.md) or
[Godot](../tools/lunitora_mcp/GODOT_README.md) guide.

## Phase 4 Provisioning

The same setup command may now configure available Godot/Photoshop MCP
capabilities and their reviewed local authentication. No daily launcher runs setup
or starts a parallel MCP server. Missing Photoshop/UDT skips Art provisioning
without blocking Godot. External applications and account sign-in remain manual.

### Codex Configuration Ownership

Fresh entries go into ignored `.codex/config.toml`, using direct repository venv
Python and toolkit cwd. Godot runs `-B -m core.godot_server` with the reviewed
nine-tool allowlist; Photoshop runs `-B -m core.server` with the reviewed three.
Startup timeout is 15 seconds; tool timeouts remain 10/35 seconds respectively.
No approval policy, sandbox setting, project trust or tool permission is granted.
Codex loads project configuration only after user trust; see the official
[MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and
[configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic).

Structural writes use stdlib `tomllib` parsing plus a bounded source-aware writer.
Only admitted setup-owned MCP table spans can change; unrelated source bytes and
custom compatible entries are preserved. The complete output must parse to the
intended structure before any write. Unsupported layouts fail closed for user
review instead of broad reformatting. No TOML third-party package is required by
the operator runtime or MCP lock.

New blocks have semantic fingerprints in ignored
`tools/.lunitora/codex-owned.json`. Only demonstrably setup-owned transport paths
can be repaired; user-edited/deleted blocks are conflicts, not overwritten.
Compatible existing project entries remain unowned. Compatible user-level entries
remain inherited with no project override and no global write. Narrow allowlists,
empty allowlists, deny lists, disabled servers and approval rules stay intact.
No existing environment secret is copied from global configuration into the repo.

Conflicting transports, named-profile overrides, remote placement or broader
project policy stop only the affected capability. Other capabilities may proceed.
Unknown CLI/profile/cloud-managed/deeper project overrides remain user-controlled;
configuration checks are not proof of an effective live client policy. Files must
be ignored, untracked, regular and not redirected/hardlinked. Atomic writes,
concurrent-content checks and a local OS lock guard updates. If the ownership
write fails, exact prior project bytes are restored only while still owned;
concurrent user edits are never rolled back. Interrupted/ambiguous ownership
fails closed rather than adopting custom entries.

### Local Authentication

Windows reuses the reviewed Godot project-bound schema-1 credential at
`tools/lunitora_mcp/.local/godot-auth.json` (256-bit secret). Photoshop retains
the reviewed `pairing-token.txt` format (48 random bytes, 64 URL-safe characters).
Creation establishes protected current-user/SYSTEM DACLs before writing secret
bytes; this is ACL-protected storage, not DPAPI encryption. Existing valid
protected credentials are preserved byte-for-byte and are never rotated just
because setup reruns. No secret is printed, returned in status or put in Codex
configuration, ownership metadata, command arguments or environment variables.

Tracked, nonignored, linked, malformed or permissive storage fails closed.
Normal setup does not repair ACLs or silently replace credentials. Valid legacy
Photoshop tokens with unsafe ownership/DACLs require the separate consent-gated
`python tools/lunitora_setup.py --repair-photoshop-auth` command. It preserves
token bytes exactly and never recursively repairs unrelated local artifacts.
If changing directory inheritance would affect unrelated children, it stops
before mutation and directs you to `--migrate-photoshop-auth`.
Photoshop UXP first pairing uses the private workflow below; Codex sign-in and any unrelated
OAuth/API/store/Apple signing credentials are not provisioned or migrated.
macOS authentication remains **REQUIRES MAC**, with no credential inspection/write.

### Photoshop Pairing

The bridge token is the one-time machine pairing/authentication credential for
the Lunitora Photoshop bridge. It is not an Adobe password. The current plugin
only accepts a token; it has no generation, reveal or copy UI. The actual flow is
**setup -> protected local file -> Photoshop panel**, not panel -> setup.

1. Install supported Photoshop through Adobe Creative Cloud. In Creative Cloud
   Desktop's **All apps**, find **UXP Developer Tools** and choose **Install**.
   This is the Adobe catalog name for UDT. Follow
   [Adobe's UDT installation guide](https://developer.adobe.com/uxp/guides/how-to/developer-tools/).
2. Start UDT and enable its first-run **Developer Mode** prompt yourself. In
   Windows Photoshop enable **Edit > Preferences > Plugins > Enable Developer
   Mode**, then restart Photoshop after protecting unsaved work. Keep Photoshop
   running so UDT can connect. Setup never enables Developer Mode or elevates
   Adobe applications. See [Adobe's host steps](https://developer.adobe.com/firefly-services/docs/photoshop/guides/actionjson-endpoint/).
3. In UDT choose **Add Plugin...** / **Add Existing Plugin...**, select the actual
   repository `tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json`, then choose
   **Load** for the Photoshop host. The existing plugin is **Lunitora Photoshop
   Bridge**, ID `com.lunitora.photoshop.bridge`. Do not create another plugin.
4. Run `python tools/lunitora_setup.py`. When the token is missing or invalid in
   safe protected storage, setup shows these instructions and a hidden prompt.
   Paste an existing valid 64-character token privately, or press **Enter** to
   generate this machine's token. Hidden-input failure/cancellation stops pairing
   without echoing the value. No token is accepted through arguments, environment
   variables, JSON or Codex configuration.
5. In Photoshop open **Plugins > Lunitora Photoshop Bridge**. The current panel
   has **Pairing token** (password input) and **Connect / Reconnect**. Privately
   open setup's ignored, protected
   `tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt`, copy its value into that input,
   close the file without edits, and clear the clipboard. This file, not a plugin
   display, is the current token source. Never print it or put it in chat,
   screenshots, logs, tracked configuration or another machine.
6. Explicitly trust/reload the project in Codex so its configured MCP server
   starts, then choose **Connect / Reconnect**. Require **Connected · inspection
   and staging candidates** and **Pairing saved securely on this computer.**
   These are the current implementation's exact statuses; secureStorage caches
   the panel's copy only after authentication succeeds. A session-only storage
   message does not prove durable pairing.

Normally this is **one-time pairing per machine**. Later setup/check runs with a
valid protected token report **Photoshop bridge authentication: OK** and never
ask again. This means local authentication appears configured, not that a live
connection was tested. `--check` never prompts, reveals, creates, rotates or
changes the token; missing/invalid data reports the required setup action.

For first-time pairing or reuse of the existing protected token run:

```sh
python tools/lunitora_setup.py --pair-photoshop
```

Valid protected tokens are reused without a prompt. A missing token uses hidden
import/generation. Unsafe storage points to explicit protection repair; pairing
never rotates a valid token because permissions are wrong.
Afterward run `git art-refresh` from external
Git Bash after finishing Desktop work, then privately update the panel and
reconnect. Setup does not launch/reconnect applications automatically.
`--check --pair-photoshop` is rejected before any setup operation.

### Pairing Troubleshooting

| Symptom | Action |
| --- | --- |
| Plugin not loaded in UDT | Add the exact repository manifest above and choose **Load**; `git art-dev` opens UDT but does not load/reload plugin code. |
| Photoshop not running/connected | Start supported Photoshop, confirm UDT's host connection, and let the Codex-owned MCP server start. Never run a parallel server. |
| Developer Mode disabled | Enable UDT's prompt and Photoshop's **Edit > Preferences > Plugins > Enable Developer Mode**, then restart Photoshop safely. |
| Token missing/invalid | Rerun normal setup and use its hidden prompt; safe invalid data can be replaced only after private input. Do not edit a config file. |
| Token rejected/stale | The panel says **Pairing failed. Re-enter the local token.** Re-pair with this machine's current protected token, refresh MCP and reconnect the panel. `--pair-photoshop` reuses a valid token. |
| Secure credential unavailable | Setup blocks unsafe/locked storage without weakening ACLs. Review the storage problem; for panel-only session pairing restore Adobe secureStorage and reconnect. |

### Setup And Doctor Readiness

Setup/check ends with Core, Game, Android, iOS and Art, and separates local
configuration, Python environment, MCP configuration, authentication and live
connection acceptance. Local preparation or MCP authentication never means a
live connection passed. Setup starts no applications. A user-disabled server
remains disabled and does not cause unrelated setup failure. Conflicts/unsafe
requested authentication return a nonzero result while retaining ready local
capabilities. Doctor returns nonzero for required proposed preparation.

`--check` creates no credentials, lock files, directories or config changes. It
reports creation/repair proposals without installing anything. The host operator
runtime uses stdlib `tomllib`; no third-party TOML dependency is needed.
The environment update safeguard remains: proven active repository-venv users
(including redirected base-Python MCP children) defer package updates. Unrelated
processes sharing the standalone base interpreter do not prove repository use.
When repair is pending, use normal setup from external Git Bash and follow the
bounded verified-MCP recovery policy above. No ad-hoc PowerShell or manual config
editing is needed.

Windows Core/Game live migration and the authenticated read-only ping are
accepted. Real fresh-machine provisioning remains separate from automated
fixtures. Legacy PowerShell remains temporary rollback/reference code until Art
parity is proven on the Photoshop machine, outside the supported operator workflow.

## macOS And Mobile

macOS support in these phases is limited to bounded application-bundle metadata
inspection under `/Applications` and `~/Applications`, plus portable configuration
and Python environment policy. Native activation, process ownership/termination,
port recovery, refresh and Godot credential security remain **REQUIRES MAC**.
The future POSIX detached-process flag is not a validated macOS launcher. Do not
substitute a generic kill/port command or relax authentication to make it appear
supported. Native Godot Game/Kitchen workflows remain independent of this MCP
boundary; see the [regression guide](../tests/README.md).

Android executable export setup follows the
[Godot 4.7 Android guide](https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_android.html):
OpenJDK 17 is recommended; SDK installation, licenses, user-local Godot SDK paths,
keystore handling and device authorization remain manual. Android Studio is one
installation route, not an additional requirement when a suitable SDK exists.

iOS executable export follows the
[Godot 4.7 iOS guide](https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_ios.html):
macOS, full Xcode and matching export templates are required. Xcode license/SDK
selection, Apple account/team/bundle settings, certificates, provisioning,
signing and device testing remain explicit user work. Do not modify the existing
export presets or copy signing material into the requirements catalog/config.
The repository does not pin an Xcode version. Resource-package success on Windows
does not prove executable iOS export. Physical-device behavior remains
**REQUIRES ANDROID DEVICE** and **REQUIRES MAC/iOS** as applicable.

## Historical Phases 1-3 Validation

The final Windows automated batch passed 262 checks without skips:

| Suite | Passed |
| --- | ---: |
| Python bootstrap/configuration/environment/discovery | 43 |
| Python workflow/ownership/reconnect policy | 35 |
| Python Windows adapter (including three native read-only probes) | 31 |
| Python detachment/log cleanup (including one native disposable child) | 13 |
| Metadata-only macOS/mobile/catalog readiness | 14 |
| Retained PowerShell base launcher | 43 |
| Retained PowerShell Godot launcher | 49 |
| Focused deformation/P3 diagnostic regression | 34 |

Fixtures demonstrate setup/rerun, local Git aliases including a real invocation
from a nested checkout containing spaces, no global Git changes, read-only check,
strict application/process identity, exact seven-workflow effects, one-attempt
failure and constrained nonfatal stale-log cleanup. The native child proof
requires launcher exit before releasing delayed stdout/stderr, then checks each
external log and unchanged invoking-shell captures. No live applications are used.

Four developmental attempts with a compiled C# child blocked inside Windows
`CreateProcess`; that cause was not established. The final proof uses the installed
trusted base Python executable and a disposable stdlib handshake child, preserving
all production process flags/kwargs and asserting exact Godot argv before its
fixture-only translation. The final batch passed without retries. Known failed
fixture directories were removed after exact-target/process checks.

The actual read-only doctor verified the existing 30-package Windows lock and
imports, found the official Godot 4.7.2 editor, and reported pending local
configuration/alias migration without applying it. Its nonzero result means Core
setup has not yet been applied, not that missing optional Art applications fail
Game. Existing venv/configuration/aliases and live apps were not changed.

The later user-reported Windows Phases 1-3 live acceptance passed as recorded
above. The preceding doctor/counts are the original automated phase evidence,
not a claim that later Phase 4 dependency installation or MCP provisioning ran.
Real fresh-machine package installation, live Art portability, and the retained
PowerShell native compiled-child rerun remain unexecuted. Full game/mobile
regression batches are outside these phases.

**REQUIRES MAC:** actual environment installation/update, app activation,
ownership, process/port control, refresh, MCP authentication and Xcode/iOS behavior.
**REQUIRES ANDROID DEVICE:** executable export/install/device behavior.
Windows Git Bash prompt cleanliness, normal visible editor, reuse, unsaved-work
preservation and existing MCP reconnect were accepted by the user. This historical
record predates the current Windows Core/Game live acceptance recorded above.

Manual Windows acceptance uses only these commands, in order:

```sh
python tools/lunitora_setup.py
git godot
git godot
git godot-refresh
```

The first Godot command must return a clean prompt while the visible editor runs.
The second must reuse that checkout's editor without allocating new logs.
Refresh must preserve the editor and unsaved state while Desktop-owned MCP
reconnects. It must not start a parallel `lunitora_godot` server.

## Historical Initial Phase 4 Validation

The final automated batch passed 363 checks without skips or retries:

| Suite | Passed |
| --- | ---: |
| Existing Python Phases 1-3 regression tests | 136 |
| Structural Codex configuration/ownership/conflict tests | 39 |
| Authentication provisioning/security (20 contracts, 15 native Windows checks) | 35 |
| Integration/check/readiness policy | 14 |
| Existing Godot protected-authentication regression | 13 |
| Retained PowerShell base launcher | 43 |
| Retained PowerShell Godot launcher | 49 |
| Focused deformation/P3 diagnostic regression | 34 |

The Python discovery run executed all 224 Phase 1-4 tests together. Fixtures cover
fresh project MCP creation, exact-byte idempotence, unrelated TOML/comment
preservation, compatible inherited/custom entries, per-capability conflicts,
owned-path repair, concurrency/rollback, no trust/global writes, restrictive tool
policy, paths with spaces, credential preservation/redaction, native protected
storage and zero-write doctor behavior. No actual application was launched or
actual credential provisioned during this batch.

The actual workstation doctor was also run read-only. Configuration/credential
bytes and timestamps, repository Git configuration and selected user Codex
configuration were unchanged. It retained the compatible inherited Godot entry
and valid protected Godot credential, with live connection explicitly
`NOT CHECKED`. Local configuration/aliases are ready; Core/Game are `PARTIAL`
because pinned `tomlkit==0.15.1` is pending in the active environment. The expected
doctor exit was 1 for that dependency, not missing optional Photoshop/UDT.
The new dependency was installed only into a disposable test directory, not the
active MCP environment. Windows now has 31 pinned packages (macOS has 30).

That dependency/runtime arrangement was superseded by the host-Python correction
above: `tomlkit` is no longer needed, and the MCP lock returns to 30 Windows / 29
macOS platform-qualified pins. The initial validation below is historical, not
acceptance of the corrected bootstrap architecture.

**NOT EXECUTED:** actual Phase 4 workstation dependency update/provisioning,
fresh-machine installation, live Art portability, full game/mobile batches and
the retained PowerShell compiled-child proof. **REQUIRES USER TEST:** project
trust/reload, fresh project MCP startup/authentication and private Photoshop
pairing. **REQUIRES MAC:** native launcher/configuration/authentication behavior
and executable iOS/Xcode validation. **REQUIRES ANDROID DEVICE:** executable
export/install/device behavior. Phases 1-3 Windows live acceptance remains valid;
these automated results do not claim additional live acceptance.

## Final Host-Python Automated Validation

The corrected bootstrap/launcher runs on standalone Python 3.12 x64, independent
of the managed MCP venv. The final scope-pruned batch passes **620 tests/checks**:

| Suite | Passed |
| --- | ---: |
| Setup/configuration/discovery | 43 |
| Seven-workflow policy/parity | 35 |
| Retained Python Windows adapter | 31 |
| Host-only Windows COM/API proofs | 21 |
| Godot output detachment/cleanup | 13 |
| Platform/prerequisite boundaries | 14 |
| Codex configuration/ownership | 39 |
| Structural stdlib TOML | 15 |
| Authentication contracts/native regression | 35 |
| Host native protected credentials/interoperability | 19 |
| Photoshop pairing | 38 |
| Integration/read-only setup | 14 |
| Environment-use/provenance | 53 |
| Deferred readiness | 9 |
| Bounded MCP recovery | 39 |
| Host-driven environment lifecycle | 21 |
| Host-runtime/aliases/real interpreter handoff | 20 |
| Baseline PowerShell base/Godot launcher from main | 43 + 39 |
| MCP Godot protected authentication/configuration | 13 |
| MCP Godot protocol | 22 |
| MCP SDK/stdio | 11 |
| Restored baseline deformation regression | 33 |

All **459 Python operator tests** run with host `-I -S -B` and no site packages.
One isolated bidirectional credential-compatibility test uses the installed MCP
interpreter only to validate fake disposable storage with the unchanged runtime
security implementation. The operator code itself does not need pywin32, MCP,
WebSockets or a third-party TOML package. Tests cover absent/broken venv execution,
actual first-time venv creation, mocked pinned installation, idempotent reuse,
inactive repair, native disposable recovery accept/decline, unknown/PID-reused
process rejection, fresh proof before mutation, all aliases in paths with spaces,
and zero-write doctor behavior. The prior completed correction batch had no
failures or skips.

Final scope-pruning validation reran all 459 host operator tests with standalone
Python `3.12` (`-I -S -B`), both restored baseline PowerShell suites (43 + 39),
and 79 managed-payload MCP authentication/configuration, protocol, SDK/stdio and
baseline deformation tests. All 620 tests/checks passed with zero failures,
errors or skips; temporary fixtures cleaned successfully. The deferred P3
wording-only test is excluded, returning deformation coverage to main's 33 tests.
No live application, bootstrap/doctor, credential provisioning, MCP request or
editor writer was run during pruning. The earlier Windows live evidence remains
applicable because the accepted Python implementation is unchanged.

The previous, pre-pruning milestone review reran 598 tests/checks with host Python
`3.12.10` x64 (`-I -S -B` for the 459 operator tests), both retained PowerShell
mock suites and the managed-payload Godot authentication/deformation regressions.
The completed batch had zero failures, errors or skips. An initial sandboxed
operator run failed on disposable temporary-directory access; a scoped execution
rerun passed without changing tests or guards. Its empty temporary residue was
verified and removed. That review ran no live applications, setup, credential
provisioning or editor writer; the ping evidence above came from the earlier
single read-only acceptance call in this conversation.

The pre-acceptance workstation `python tools/lunitora_setup.py --check` completed
read-only, including initial Python 3.14-to-host-3.12 handoff. Machine/project/global
configuration and protected credential hashes/timestamps stayed unchanged.
Python/Godot/MCP configuration/authentication are present; Core/Game are `PARTIAL`
because the old local aliases need the explicit host-Python setup update. Missing
Photoshop/UDT remains the expected Art-only limitation. Live connectivity is
`NOT CHECKED`, not inferred from configuration.

That doctor result predates acceptance. The milestone review confirmed all seven
current repository-local aliases use validated standalone host Python plus
`tools/lunitora_launcher.py`; none targets the managed MCP venv.

**LIVE ACCEPTED:** Windows Core/Game host-runtime migration, launcher/reuse/
refresh behavior and authenticated `godot_ping({})`, as recorded above.
**NOT EXECUTED:** network dependency installation on a fresh machine, recovery of
actual lingering MCP processes and full game/mobile batches. The historical
compiled PowerShell child proof is excluded from this candidate and was not
rerun. **REQUIRES ART MACHINE:** Adobe installation,
Developer Mode/UDT loading, private first pairing/reset, live Art processing and
Art launcher parity. **REQUIRES MAC:** native activation/ownership/refresh/
authentication and executable iOS/Xcode/device work. **REQUIRES ANDROID DEVICE:**
executable export/install/device behavior. PowerShell remains temporary
rollback/reference code until Art parity is proven; current aliases never invoke it.

### Historical Correction File Inventory

This correction adds 11 files and updates 24 existing working-tree files. Many
pre-existing Phase 1-4 files are still untracked; this inventory distinguishes
changes made by this correction, not the complete milestone diff.

Added host modules:
`tools/lunitora_machine/host_runtime.py`,
`tools/lunitora_machine/environment_recovery.py`,
`tools/lunitora_machine/native_credentials.py`,
`tools/lunitora_machine/structural_toml.py`,
`tools/lunitora_machine/platforms/windows_com.py`.

Added tests:
`tools/tests/test_lunitora_host_runtime.py`,
`tools/tests/test_lunitora_host_environment.py`,
`tools/tests/test_lunitora_environment_recovery.py`,
`tools/tests/test_lunitora_native_credentials.py`,
`tools/tests/test_lunitora_structural_toml.py`,
`tools/tests/test_lunitora_windows_host.py`.

Updated entrypoints/operator modules:
`tools/lunitora_setup.py`, `tools/lunitora_launcher.py`,
`tools/lunitora_machine/bootstrap.py`,
`tools/lunitora_machine/configuration.py`,
`tools/lunitora_machine/environment.py`,
`tools/lunitora_machine/environment_usage.py`,
`tools/lunitora_machine/authentication.py`,
`tools/lunitora_machine/codex_config.py`,
`tools/lunitora_machine/readiness.py`,
`tools/lunitora_machine/platforms/windows.py`.

Updated regression fixtures:
`tools/tests/test_lunitora_setup.py`,
`tools/tests/test_lunitora_windows.py`,
`tools/tests/test_lunitora_authentication.py`,
`tools/tests/test_lunitora_codex_config.py`,
`tools/tests/test_lunitora_photoshop_pairing.py`,
`tools/tests/test_lunitora_integration.py`,
`tools/tests/test_lunitora_environment_readiness.py`,
`tools/tests/test_lunitora_environment_usage.py`.

Updated documentation/dependencies:
`docs/MACHINE_SETUP.md`, `tools/LUNITORA_COMMANDS.md`,
`tools/lunitora_mcp/README.md`, `tools/lunitora_mcp/GODOT_README.md`,
`tools/lunitora_mcp/pyproject.toml`, `tools/lunitora_mcp/requirements.lock`.
The setup-only `tomlkit` addition is removed; `pyproject.toml` now matches HEAD.
No MCP dependency version changed. At this historical checkpoint the earlier
PowerShell/P3 changes were still present; final scope pruning above removes them
from the milestone candidate.

## Historical Phases 1-3 File Inventory

Added (22 files):

```text
docs/MACHINE_SETUP.md
tools/lunitora_setup.py
tools/lunitora_launcher.py
tools/lunitora_requirements.json
tools/lunitora_machine/__init__.py
tools/lunitora_machine/applications.py
tools/lunitora_machine/bootstrap.py
tools/lunitora_machine/configuration.py
tools/lunitora_machine/environment.py
tools/lunitora_machine/logs.py
tools/lunitora_machine/policy.py
tools/lunitora_machine/prerequisites.py
tools/lunitora_machine/readiness.py
tools/lunitora_machine/workflows.py
tools/lunitora_machine/platforms/__init__.py
tools/lunitora_machine/platforms/windows.py
tools/lunitora_machine/platforms/macos.py
tools/tests/test_lunitora_setup.py
tools/tests/test_lunitora_windows.py
tools/tests/test_lunitora_workflows.py
tools/tests/test_lunitora_detachment.py
tools/tests/test_lunitora_portability.py
```

Updated (5 files): `.gitignore`, `tools/LUNITORA_COMMANDS.md`,
`tools/lunitora_mcp/README.md`, `tools/lunitora_mcp/GODOT_README.md`, and
`tools/lunitora_mcp/requirements.lock`. The lock changes only the Windows marker
on the existing `pywin32==312` pin; no dependency versions changed.

Pre-existing uncommitted changes at that historical checkpoint:
`tools/operator_launcher/common.ps1`,
`tools/operator_launcher/tests/test_godot_launcher.ps1`,
`tools/operator_launcher/tests/test_godot_output_detachment.ps1`,
`tools/lunitora_mcp/modules/godot/protocol.py`, and
`tools/lunitora_mcp/tests/test_godot_deformation_lab.py`.
These changes are excluded by final scope pruning above. The four tracked files
now equal `main`, the untracked PowerShell test is removed, and the text-only P3
correction is deferred. No Godot runtime, fixture, art or spec changed.

## Historical Phase 4 File Inventory

Added in Phase 4 (6 files):

```text
tools/lunitora_machine/authentication.py
tools/lunitora_machine/codex_config.py
tools/lunitora_machine/integration.py
tools/tests/test_lunitora_authentication.py
tools/tests/test_lunitora_codex_config.py
tools/tests/test_lunitora_integration.py
```

Updated in Phase 4 (12 files, including earlier uncommitted phase files):

```text
.gitignore
docs/MACHINE_SETUP.md
tools/LUNITORA_COMMANDS.md
tools/lunitora_requirements.json
tools/lunitora_machine/bootstrap.py
tools/lunitora_machine/environment.py
tools/lunitora_machine/readiness.py
tools/lunitora_mcp/pyproject.toml
tools/lunitora_mcp/requirements.lock
tools/lunitora_mcp/README.md
tools/lunitora_mcp/GODOT_README.md
tools/tests/test_lunitora_setup.py
```

The narrow Codex atomic-temp ignore rule prevents interrupted local writes from
appearing as repository candidates. No launcher workflow/discovery, PowerShell,
Godot runtime, fixture, source artwork or deformation spec changed in Phase 4.
No global configuration, project trust or actual machine credentials were changed.

## Historical Photoshop Pairing Follow-Up

The follow-up adds hidden import/generation and explicit protected replacement,
truthful plugin-derived instructions, full UDT terminology and troubleshooting.
It adds `tools/tests/test_lunitora_photoshop_pairing.py`; updates are bounded to
the machine authentication/integration/bootstrap/application-message/workflow-
message/readiness modules, requirements catalog and four operator/setup guides.
Photoshop plugin/protocol and Godot behavior remain unchanged.

Follow-up validation passed 507 checks without failures or skips:
262 Python machine/bootstrap/launcher tests (including 38 new pairing checks),
50 existing Photoshop phase-1 tests, 76 phase-2 tests, eight reconnect tests,
12 diagnostic tests, 25 background-removal tests, 13 Godot authentication tests
and 61 unchanged UXP plugin mock checks. The MCP batch emitted expected
port-collision diagnostics and asyncio slow-task notices; all assertions passed.
The actual workstation doctor retained configuration/credential bytes and
timestamps, reported full UDT terminology and kept Art missing without blocking
unrelated configuration. Its expected exit 1 remains the unapplied new TOML
dependency. Actual Git Bash hidden input, Adobe installation/Developer Mode/UDT
loading, live Photoshop pairing and reset/reconnect require user acceptance;
macOS remains **REQUIRES MAC**. No actual token was provisioned or replaced.

## Historical Environment-Use Correction

Live Phase 4 acceptance exposed a false blocker after Desktop/Godot were closed.
The old stdlib inspector counted its own waiting Windows venv redirector, and
also counted unrelated Python processes using the same base interpreter.
A read-only native probe confirmed the inspector's actual base-Python child had
the repository `.venv/Scripts/python.exe` redirector as its waiting parent.
There was no persisted stale PID ledger involved.

The replacement uses held process handles, creation time, live status, exact
interpreter identity and privately parsed arguments. Known setup/probe processes
and their proven forwarded redirectors are exempt. Only exact live repository
venv interpreters or proven redirected users block mutation. Other-checkout
redirectors with verified provenance and unrelated standalone Python are ignored.
A repository path in data arguments, Git Bash ancestry or inherited terminal
handles is not evidence of environment use. Exited processes are ignored;
unreadable/reused identities and mismatched ancestry remain fail-closed.

Normal deferral reports each admitted blocker using only role, PID and executable,
never arbitrary command-line contents. Unclassified state says
`environment-use state ambiguous`, not that Desktop/MCP is definitely open.
The inspector terminates no process; explicit setup now offers only the bounded,
confirmed verified-MCP recovery described above. Operator setup/diagnostics remain
Python/Git commands.

When baseline imports permit safe inspection, a deferred normal setup continues
through the same read-only application/configuration/MCP/authentication checks as
`--check`, without aliases, credential or local-config writes. Otherwise capabilities
are `NOT CHECKED`, not falsely missing. Configured Core/Game report `PARTIAL`
while dependency repair is pending. Missing Photoshop during `--pair-photoshop`
reports pairing unavailable on this machine and Core/Game unaffected.

Files added:

```text
tools/lunitora_machine/environment_usage.py
tools/tests/test_lunitora_environment_usage.py
tools/tests/test_lunitora_environment_readiness.py
```

Files updated:

```text
tools/lunitora_machine/environment.py
tools/lunitora_machine/bootstrap.py
tools/lunitora_machine/readiness.py
tools/tests/test_lunitora_setup.py
docs/MACHINE_SETUP.md
```

Validation passed 416 checks: 324 Python machine/bootstrap/launcher checks,
including 53 environment-use cases (46 pure admission, four sanitized diagnostic,
three native Windows proofs) and nine deferred-readiness cases, plus retained
PowerShell base/Godot launcher suites (43/49). Final suites had no failures or
skips. Developmental sandbox temp-access errors and one output-capture fixture
assertion were corrected; a strengthened native free-state assertion also caught
and fixed another-checkout redirector's base-interpreter argv identity. The failed
empty fixtures were verified and removed.
The retained standalone compiled-child PowerShell proof was not rerun; native
Python detachment coverage is included in the complete Python batch.

Actual normal setup was exercised while the real Godot MCP was live. It admitted
the server's base-Python child and venv redirector, deferred mutation, reported
Core/Game `PARTIAL` and preserved inspected config/credential bytes and timestamps.
No applications were launched/stopped and no actual venv dependency was changed.
Native disposable fixtures prove free state with no target users, live MCP use,
and absence after process exit. Closed-Desktop Git Bash acceptance was pending
at this historical correction:

```sh
python tools/lunitora_setup.py
```

No manual process killing or PowerShell diagnostics are required. macOS native
environment-use admission remains **REQUIRES MAC**.


## Explicit Photoshop credential storage migration

New Windows credentials use `tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt`.
This dedicated ignored directory extends the Lunitora local root and contains only
Photoshop credentials. Its owner/DACL can be secured independently of unrelated
`.local` artifacts. Existing reviewed protected legacy credentials remain usable
and unchanged. A present dedicated token takes precedence; invalid dedicated
storage never falls back to the legacy credential. Fresh setup and
`--pair-photoshop` create tokens directly in the dedicated directory.

For a valid legacy token blocked by mixed-directory inheritance, run alone:

```bash
python tools/lunitora_setup.py --migrate-photoshop-auth
```

The command diagnoses without showing secrets and requires explicit `y` consent.
It verifies ignored/untracked provenance, rejects redirects/reparse points and
hard links, pins ancestor/source identities, checks for concurrent changes after
consent, and creates the destination with current-user ownership and protected
current-user/SYSTEM explicit full-access DACLs. It copies the original bytes
without normalization or rotation, reopens and verifies identity/security and
exact equality. It never modifies the legacy token, legacy directory ACL, or
unrelated children. An existing protected byte-identical destination is a no-op;
conflicting or unsafe destinations fail closed. If a post-creation verification
fails, inspect the destination before retrying; the original remains recoverable.
No automatic source cleanup is implemented.

`legacy credential remains; cleanup available after live pairing acceptance`

`--check` stays strictly read-only and cannot be combined with migration. Normal
setup/check prefer the migrated protected token and no longer need legacy ACL
repair. Repair remains available for repairable protected storage; mixed legacy
inheritance directs operators to migration. **REQUIRES MAC:** native macOS
credential protection is separate and not implemented by Windows ACL migration.

Art-machine acceptance after automated validation:

1. In external Git Bash at the repository root, run the migration command above;
   review its source/destination explanation and enter `y`. Require verified
   byte-identical migration and the legacy-remains message.
2. Run `python tools/lunitora_setup.py --check`, then normal setup and
   `python tools/lunitora_setup.py --pair-photoshop`. Require valid preserved
   authentication without a hidden token prompt, rotation or legacy ACL repair.
3. After active Desktop work finishes, run `git art-refresh` externally to restart
   Codex/MCP with the new lookup. Preserve unsaved Photoshop work. Run `git art`
   and, for development loading, `git art-dev` and manually reload the plugin in
   UDT when needed. Do not start a parallel manual server.
4. Use the plugin's cached secure pairing and require Connected. If re-entry is
   needed, privately open the new credential file in a local editor, paste into
   the panel password input, close without changes and clear the clipboard.
   Never print/capture the token or place it in chat/configuration.
5. Through the configured Photoshop MCP, perform one read-only
   `photoshop_ping({})`; require `ok=true`, authenticated connection and the
   expected Photoshop 27.10 host. Check one read-only active-document response
   against the open document, with no document/history/dirty-state changes.
6. Record sanitized live acceptance. Only then consider a separate explicitly
   authorized legacy-token cleanup operation; do not delete it as part of migration.


### v0.9 Windows Art acceptance (2026-10-03)

The Art machine's Python 3.12.10 repository environment is healthy: all 43 setup
tests pass and `pip check` reports no broken requirements. Earlier bundled-runtime
import failures and sandbox interpreter-launch restrictions do not describe the
accepted machine environment.

Acceptance is recorded separately for each stage:

- **Installed/configured:** Photoshop 27.10 detected and launched; UXP Developer
  Tool (UDT) 2.3.0.5 detected and launched. `git art`, `git art-refresh` and
  `git art-dev` are live accepted.
- **Credential ready:** protected, byte-preserving Photoshop credential migration
  is live accepted. The legacy credential remains untouched.
- **Panel paired:** pairing with the protected machine credential is live accepted.
- **Live MCP accepted:** `photoshop_ping({})` succeeded with `ok=true`,
  `connected=true` and Photoshop `27.10.0`. The authenticated reconnect-loop fix
  and stable panel connection after refresh are live accepted.

After `git art-refresh`, the Desktop-owned Photoshop MCP may start lazily on the
first Photoshop MCP tool call. A transient `1006` while the server is not yet
listening is acceptable; once connected, the panel must remain stable. A startup
disconnect alone does not invalidate credentials or require token rotation.
Read-only setup/doctor still report panel pairing and live MCP as NOT CHECKED:
local installation/configuration and credential readiness cannot prove them.

Focused validation passes: 87 Photoshop pairing/recovery/migration tests,
35 authentication tests, 7 Art guidance tests, 43 setup tests, 22 isolated
protocol/reconnect tests and 63 JavaScript plugin checks. `git diff --check` passes.
Fixed-port Phase 1 failures caused by the accepted live bridge already owning
`127.0.0.1:43127` are environment/live-port conflicts, not product regressions.

Baseline follow-up: `test_native_accepted_exact_fixture_exit_is_proven_before_return`
and `test_native_declined_exact_fixture_remains_running` both fail at the same
`ambiguous` versus `in_use` assertion on v0.9 and clean main
`374dc75163bef68b2e65544aaa0329cd45e29605`, using the same repository Python 3.12
runtime, working directory and environment (only the source import path differs).
Disposition: **PRE-EXISTING / NOT INTRODUCED BY v0.9**. Investigate native process
classification separately; recovery implementation/tests are unchanged here.

Explicitly deferred: legacy Photoshop credential cleanup, legacy PowerShell
removal, macOS validation and Photoshop asset-registration tooling. No credential
cleanup or PowerShell removal is part of this milestone.
