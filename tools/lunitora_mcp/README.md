# Lunitora Photoshop MCP — v0.6 operator convenience

Separate read-only Godot editor bridge: [Godot Animation MCP v0.1 setup](GODOT_README.md).

Repository-controlled Photoshop bridge with two compatible read-only tools,
photoshop_ping and photoshop_get_active_document, plus photoshop_process_image
for one explicitly selected inbox image and one staging candidate.

Architecture: [Lunitora MCP guide](../../docs/LUNITORA_MCP_ARCHITECTURE_GUIDE.md).
Bridge/plugin version: 0.1.0. Bridge protocol version: 1.
The plugin targets Photoshop 27.10+ with UXP manifest v5 and Photoshop API v2.
The audited installation is Photoshop 2026 27.10.0.26 on Windows x64.
UDT loading, authenticated live Photoshop connectivity and Codex MCP activation
are verified on this workstation. Both read-only tools succeeded through the real
Codex MCP integration on 2026-09-29 with the restricted localhost configuration
below.

## Operator convenience v0.6

Daily operator reference: [LUNITORA_COMMANDS.md](../LUNITORA_COMMANDS.md).
This section and the workstation setup below describe the current workflow;
older phase/live-test records later in this file are historical technical evidence.

### Repository-local launcher setup

From the checkout root in **Git Bash**:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/setup.ps1
```

Setup discovers the registered `OpenAI.Codex` Windows desktop package (whose UI
may be named `ChatGPT.exe`), Photoshop under Program Files/Adobe, and UXP Developer
Tool. It validates absolute local executable paths before installing the five
aliases with `git config --local`. It never selects the `codex` CLI from PATH.
Multiple discovered installations require an explicit selection. Photoshop/UDT
may be absent on a Codex-only workstation; commands that require them fail clearly.
Existing valid overrides are preserved. After an app update moves its executable,
rerun setup to discover its current location. For nonstandard installations:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/setup.ps1 \
  -DesktopExe 'C:\path\to\ChatGPT.exe' \
  -PhotoshopExe 'C:\path\to\Photoshop.exe' \
  -UdtExe 'C:\path\to\Adobe UXP Developer Tools.exe'
```

Machine paths and the expected checkout root live only in ignored
`tools/operator_launcher/config.local.json`; the tracked example documents its
four fields. No secrets belong there. Moving/copying the checkout requires fresh
setup (remove the old ignored configuration first). There is no global Git change,
scheduled task, Python dependency, shell-profile edit, or MCP configuration edit.
Git shell aliases run from the repository root even when invoked in a subdirectory.
Each alias calls the tracked `launch.ps1` with its matching mode:

```text
!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 art
!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 art-refresh
!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 art-dev
!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 dev
!powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/launch.ps1 dev-refresh
```

Use `git art -Check` (or any alias with `-Check`) to validate paths without starting
or stopping applications. The ordinary commands report application startup status,
not verified Photoshop connectivity. Desktop owns configured stdio MCP processes;
the launcher never runs `core.server` itself. Do not run a parallel manual server.

Run refresh from **external Git Bash**, after active Desktop tasks finish. It
closes every process at the configured desktop executable path, first requesting
window close and allowing eight seconds, then terminating only verified remaining
desktop processes. Process creation time/path are rechecked using a held process
handle. It waits ten seconds for the captured Desktop-owned descendants to exit.
`dev-refresh` never cleans ports or kills those descendants; if they remain, it
reports them and stops before reopening. It never touches Photoshop or UDT.

`art-refresh` also waits up to ten seconds for port 43127. It reports remaining
owners by PID/name/executable (never arbitrary command lines). Automatic cleanup
requires exact repository venv Python and exact `-B -m core.server` arguments, or
its Windows base-Python child with a still-verifiable venv parent and matching
`pyvenv.cfg` executable. It must also have belonged to the closing Desktop, or
have an absent parent, to count as stale. Missing inspection access, an orphaned
base-Python child without provable ancestry, another live client, or an unknown
listener stops recovery without killing it. No process-name-wide kill or process
tree kill is used. The launcher confirms the listener is gone and an exclusive
IPv4 bind succeeds before ensuring Photoshop is running and reopening Desktop.
It never closes Photoshop or interacts with UDT controls.

### One-time private .ccx installation

Official documentation checked on 2026-09-30:

- [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
  documents shared desktop/CLI configuration and stdio `command`, `args`, `cwd`,
  timeouts and tool allowlists. Keep MCP startup under the client.
- [Adobe manifest v5](https://developer.adobe.com/photoshop/uxp/2022/guides/uxp-guide/uxp-misc/manifest-v5/)
  requires Photoshop 23.3+ and retains earlier host metadata.
- [Photoshop-specific loadEvent](https://developer.adobe.com/photoshop/uxp/2022/guides/uxp-guide/uxp-misc/manifest-v4/photoshop-manifest/)
  documents `host.data.loadEvent: "startup"` since Photoshop 23.1. This covers our
  27.10 minimum. The plugin loads shortly after Photoshop starts, even without
  opening the panel; the JavaScript begins connection on plugin load.
- [Adobe packaging](https://developer.adobe.com/uxp/guides/how-to/distribution/package/)
  requires a stable ID and single host object for independent distribution, and
  recommends UDT packaging. The Photoshop-specific
  [packaging guide](https://developer.adobe.com/photoshop/uxp/guides/distribution/packaging-your-plugin/)
  also documents `.ccx` and UDT's Package action. A Marketplace listing requires
  its portal-generated ID; this private package retains
  `com.lunitora.photoshop.bridge`. Its registration/Marketplace ownership was not
  checked, and no Marketplace submission is part of this work.
- [Adobe installation](https://developer.adobe.com/uxp/guides/how-to/distribution/install/)
  supports independent `.ccx` installation through Creative Cloud Desktop;
  unpackaged development loading is a separate UDT workflow.

The manifest is suitable for private packaging: v5, one `PS` host at 27.10.0,
API v2, stable plugin/panel IDs and exactly `ws://localhost/` network permission.
No filesystem, launch-process, or wider network permission was added. The existing
plugin/protocol versions remain 0.1.0/1; v0.6 names this tooling milestone.

Developer packaging and one-time operator installation:

1. Open UDT with `git art-dev`. Add
   `tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json` if necessary. Unload a
   development copy with the same ID before testing an installed copy.
2. In UDT's plugin Actions menu choose **Package**. Select
   `tools/lunitora_mcp/dist/` (create it if absent), outside the plugin source
   directory. The plugin need not be loaded to package. Package only the plugin
   directory; it contains no pairing file, local config, environment or tests.
   Never create an ad-hoc renamed ZIP as a substitute for UDT validation.
3. Double-click the generated `.ccx`; Creative Cloud Desktop handles installation.
   Review the independent-plugin notice and permissions. Verify it is installed
   in Manage Plugins and available in Photoshop. If Adobe rejects the ID/package,
   record the exact installer error; do not silently change the ID or permissions.
4. Save work and restart Photoshop yourself for the startup test. The launcher
   never closes it. Close UDT. Open the installed Lunitora panel for first pairing,
   privately enter this machine's token, and choose **Connect / Reconnect**.
5. After pairing, daily `git art` and direct image requests need no UDT or ping.
   Verify cold Photoshop startup with the panel closed, then a Desktop restart
   while Photoshop stays open. Verify reconnection and a new staging candidate.

`dist/` and `.ccx` files are ignored; do not commit generated installers. For an
update, package the edited source again and reinstall through Creative Cloud;
if its installer requires a higher plugin version, make a deliberate release
version update before packaging. Reloading in UDT changes only the development
copy, not the installed package. Never run both copies as bridge clients.

### Pairing and reconnect behavior

The token keeps its existing UXP secure-storage key and is saved only after
successful authentication. It is never put in local launcher settings, logged,
or included in the package. [Adobe secureStorage](https://developer.adobe.com/photoshop/uxp/2022/uxp/reference-js/Modules/uxp/Key-Value%20Storage/SecureStorage/)
encrypts per-plugin values but describes this storage as a recoverable cache.
Expect one pairing per installation/storage reset; a development-to-installed
transition may require pairing again. If storage is unavailable the panel explains
the session-only connection. Never claim storage is permanent.

On startup, the saved token triggers a connection to `ws://localhost:43127`.
Connection errors/closures retry after five seconds; a hung connection/auth attempt
has a ten-second deadline. Only one socket attempt and one retry timer are active.
Manual reconnect retires the old attempt; plugin destruction clears all timers
and ignores pending storage results. Missing/invalid credentials or explicit
authentication rejection require operator pairing and do not loop. No token or
raw authentication payload is logged.

When Photoshop starts before Codex Desktop/MCP, the plugin may make several
failed localhost connection attempts while the server is starting. This is
expected and acceptable: after one-time pairing, it connects automatically once
the Codex-owned MCP listener appears. This startup sequence does not require
manual reconnect or another token entry.

Real Photoshop calls wait for authentication for up to eight seconds, bounded by
their original deadline (five seconds by default for document inspection, thirty
for processing). The wait consumes the deadline, so it cannot extend a processing
request beyond thirty seconds. Invalid parameters and startup errors fail first;
`photoshop_ping` retains immediate diagnostic behavior. An operation already sent
to Photoshop is never automatically replayed after a disconnect. After a cold
Photoshop launch takes longer than the grace period, wait for Photoshop to finish
opening and retry the request. Staging no-overwrite protection still applies.

Bare-filename natural-language defaults are defined in the root `AGENTS.md`.
For character/fine detail, prefer removal, human visual review, copying the approved
candidate to `_inbox`, then resizing. Combined operations remain supported.

### v0.6 validation — 2026-09-30

**VERIFIED live (operator-confirmed):** `git dev`, `git dev-refresh`, `git art`,
`git art-refresh`, and `git art-dev`; packaged `.ccx` installation; Photoshop and
packaged-plugin startup without UXP Developer Tool; one-time pairing-token setup;
secure token reuse after restart; automatic reconnect when Photoshop starts before
the Codex-owned MCP server; and direct Photoshop processing without a preliminary
`photoshop_ping`. Several failed localhost attempts before the listener appears
are expected and acceptable. These confirmations complete the v0.6 live operator
workflow checks previously marked as pending here.

**VERIFIED automated:** the complete suite passes with port 43127 free. The
listener's executable, exact repository server command, Windows venv parent and
Codex Desktop ancestry were verified before stopping only the bridge processes.
Desktop and Photoshop stayed open. Exclusive-bind checks passed before and after
validation. No manual bridge was launched alongside the tests.

| Suite | Passed | Failures | Errors | Skips |
| --- | ---: | ---: | ---: | ---: |
| Python Phase 1, including packaging icons | 50 | 0 | 0 | 0 |
| Python Phase 2A/2B | 76 | 0 | 0 | 0 |
| Python validation diagnostics | 12 | 0 | 0 | 0 |
| Python background removal | 25 | 0 | 0 | 0 |
| Python authenticated reconnect | 8 | 0 | 0 | 0 |
| JavaScript plugin/panel, including packaged startup | 61 | 0 | 0 | 0 |
| JavaScript image processing | 104 | 0 | 0 | 0 |
| PowerShell launcher safety/workflow | 43 | 0 | 0 | 0 |
| Automated tests/checks | **379** | **0** | **0** | **0** |

Python discovery ran all **171 tests in 34.162 seconds**, with no expected failures
or unexpected successes. This supersedes the earlier partial 123-test and
168-test records; all previously deferred fixed-port tests now execute. Current
totals also include the packaging-icon, packaged-startup and launcher checks added
since those records. Launcher process mutations and Photoshop segmentation are
mocked in the automated suites.

All **112 supplemental checks** pass: syntax compilation for 20 Python, four
JavaScript and four PowerShell files; 30 installed dependency pins; one `pip check`;
six Git Bash alias checks (all five commands with `-Check`, plus a subdirectory);
32 ignore probes; and 15 repository/port audit checks. Combined final result:
**491 passed, zero failures, errors or skips**. The first six alias probes failed
because Git Bash inherited this runner's incompatible PowerShell module path.
They passed when rerun with the native Windows PowerShell module path scoped only
to the test process. No launcher code or persistent environment setting changed;
the initial failed-probe logs are retained separately.

The full diff and all untracked candidates were reviewed, including the four icon
PNGs. No regression or unintended change was found. Only
`tools/LUNITORA_COMMANDS.md` and this README changed during this pass. The existing
implementation and tests were preserved. Generated `.ccx`, `.local`, pairing
tokens, caches, virtual environments and local configuration are ignored and are
not commit candidates; no ignored file is already tracked. Credential scans found
no local pairing value in the working candidates or index and no credential
patterns in changed/new files. All ten protected artwork/package/token/config
files are unchanged. HEAD and the index are unchanged, nothing is staged, and
`git diff --check` passes. Nothing was committed or pushed. Logs and audit scripts
remain in ignored `.local/v06-live-validation-20260930-014335/`.

**NOT EXECUTED in this automated rerun:** additional live application launches,
refreshes, installation or Photoshop processing; the operator-confirmed checks
above supply that live evidence. Godot/game tests and the additional v0.5
Device/Cloud, cancellation, cleanup and near-limit cases were not rerun.

**REQUIRES USER TEST:** no outstanding v0.6 operator workflow checks from the list
confirmed above. Every generated staging candidate still requires human visual
approval, especially character edges and fine detail. Additional v0.5 processing
cases listed in the historical validation section remain outside this operator
workflow confirmation.

For a full automated rerun, first finish Desktop tasks and close Desktop yourself,
then confirm port 43127 is free. Do not kill an unknown listener. Run from Git Bash:

```bash
# From the repository root; the launcher tests do not touch real applications.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/tests/test_launcher.ps1
cd tools/lunitora_mcp
./.venv/Scripts/python.exe -B -m unittest discover -s tests -t . -v
node tests/test_plugin.js
node tests/test_processing.js
./.venv/Scripts/python.exe -B -m pip check
```

The transport tests use disposable credentials. If a running installed plugin
attempts to pair with a test server and reports rejection, use its Connect button
after the test run and normal Desktop restart. Do not replace its real token.

## New Windows Workstation Setup

Follow this sequence on each new PC. Replace placeholders before running commands.
Shell examples use **Git Bash**: `<repo-path-bash>` is the checkout's absolute
Bash path, such as `/d/Development/totolina-merge`. In TOML, `<repo-path>` is the
same checkout's Windows path, such as `D:\Development\totolina-merge`.
Each machine uses its own paths.

1. **Install prerequisites.** Use Windows x64, the platform of the dependency
   lock and verified installation. Install **Photoshop 27.10.0 or newer**
   (manifest minimum; live verification used 27.10), **Creative Cloud Desktop**
   for packaged plugin installation, standalone **Python 3.12.x
   x64** (`==3.12.*` in the project; verified with 3.12.10), **Git for Windows
   with Git Bash**, and **Codex Desktop for Windows**, signed in and able to run
   local stdio MCP servers. The project pins no Git, UXP Developer Tool, or Codex
   Desktop version. UXP Developer Tool is needed only on a developer/packaging
   machine. Node is only needed for optional JavaScript mock tests.

2. **Clone or update `totolina-merge`.** Use the repository URL you already have
   access to and a branch containing the current toolkit files. For a new checkout:

   ~~~bash
   git clone '<repository-url>' '<repo-path-bash>'
   ~~~

   For an existing checkout, preserve local work and update its branch:

   ~~~bash
   git -C '<repo-path-bash>' pull --ff-only
   ~~~

3. **Create the environment and install the lock.** Replace
   `<python-3.12-exe-bash>` with this PC's standalone Python executable in Bash
   form, such as `/c/Users/<username>/AppData/Local/Programs/Python/Python312/python.exe`.
   Confirm it reports 3.12.x; do not reuse another application's bundled Python.

   ~~~bash
   cd '<repo-path-bash>/tools/lunitora_mcp'
   '<python-3.12-exe-bash>' --version
   '<python-3.12-exe-bash>' -m venv .venv
   ./.venv/Scripts/python.exe -m pip install --no-cache-dir -r requirements.lock
   ./.venv/Scripts/python.exe -m pip check
   ~~~

   All subsequent shell commands run from `tools/lunitora_mcp`. Activation is
   unnecessary; use `.venv/Scripts/python.exe` directly. The lock pins all 30
   dependencies, including `mcp==2.2.0` and `websockets==17.1`.

4. **Generate this machine's pairing token.**

   ~~~bash
   ./.venv/Scripts/python.exe -B -m core.server --setup
   ~~~

   On a fresh checkout this creates `.local/pairing-token.txt` with a new random
   token. It prints only the file location, never the token. Repeating setup
   preserves an existing valid token. Never copy or share another workstation's
   token, `.local` directory, or Python environment.

5. **Keep local files out of Git.** `.local/` (including the token), `.venv/`,
   `__pycache__/`, `*.py[cod]`, `*.log`, `*.egg-info/`, and `config.local.toml`
   are ignored by the toolkit's `.gitignore`. Keep other local diagnostics under
   `.local/`; never commit or force-add these files. Check without reading contents:

   ~~~bash
   git check-ignore -v .local/pairing-token.txt .venv/pyvenv.cfg core/__pycache__/config.cpython-312.pyc config.local.toml
   ~~~

6. **Install the UXP plugin.** Follow the private `.ccx` steps above. Open Photoshop's
   **Plugins > Lunitora Photoshop Bridge** panel for first pairing. Keep the permission
   `{"network":{"domains":["ws://localhost/"]}}`; the plugin connects to
   `ws://localhost:43127` and Python binds only to `127.0.0.1:43127`.

7. **Configure the current user's Codex.** Edit
   `C:\Users\<username>\.codex\config.toml` (create the directory/file if absent).
   Add this table, or update its existing entry without duplicating it; preserve
   unrelated settings. Replace `<repo-path>` with this PC's absolute Windows
   checkout path, keeping single quotes so backslashes remain literal:

   ~~~toml
   [mcp_servers.lunitora_photoshop]
   command = '<repo-path>\tools\lunitora_mcp\.venv\Scripts\python.exe'
   args = ['-B', '-m', 'core.server']
   cwd = '<repo-path>\tools\lunitora_mcp'
   startup_timeout_sec = 15
   tool_timeout_sec = 35
   enabled_tools = ['photoshop_ping', 'photoshop_get_active_document', 'photoshop_process_image']
   ~~~

   This user-local configuration stays outside the repository. Do not put the
   pairing token in it or use Bash `/c/` or `/d/` paths for `command`/`cwd`.
   See the [Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp).

8. **Fully restart Codex Desktop and open a new Codex chat** in this repository
   to load the configuration. Let Codex own the server; do not also run
   `core.server` or `--live-test` manually alongside it.

9. **Open the repository in Desktop.** Codex owns the configured MCP process.
   No preliminary ping is required. `photoshop_ping` remains an optional diagnostic.

10. **Pair Photoshop on this workstation.** Open the local token privately:

    ~~~bash
    notepad.exe './.local/pairing-token.txt'
    ~~~

    Copy it into the panel's **Pairing token** password input, close Notepad
    without edits, and click **Connect / Reconnect**. Expect
    **Connected · inspection and staging candidates**. Never print the token in a terminal or paste it
    into chat, logs, screenshots, or Git. The plugin caches it in UXP
    secureStorage when available; otherwise pairing lasts for that connection.

11. **Verify both tools.** Call `photoshop_ping` again. Require `ok=true`,
    `connected=true`, `error=null`, version information (UXP may be null), and a
    measured `round_trip_ms`. Then call `photoshop_get_active_document` and
    compare its name, dimensions, layers, artboards, and saved state with
    Photoshop. No open document is a successful
    `has_document=false, document=null` result, not a disconnect. These tools
    only inspect; they do not edit, save, or export.

12. **Troubleshoot.** Install the launcher aliases above, then use `git art-refresh`
    from external Git Bash for `PORT_IN_USE` recovery. There is no alternate-port
    fallback. To inspect a listener manually:

    ~~~bash
    netstat.exe -ano -p tcp | findstr.exe ':43127'
    ~~~

    Do not terminate unknown PIDs, unrelated Python or Photoshop processes.
    Stop a known manual bridge with Ctrl+C in its own terminal. Unknown owners
    require developer investigation; the launcher fails safely.

    For `DISCONNECTED`, keep Photoshop open, confirm the plugin is loaded,
    allow automatic reconnect, or use **Connect / Reconnect** for diagnostics.
    Re-enter the local token only if pairing is rejected or the cache is lost.
    Repackage/reinstall installed plugin updates; UDT Reload is developer-only.
    If tools are missing,
    check the user config's absolute executable and working-directory paths,
    then repeat step 8. Keep the localhost permission and fixed endpoint; use
    the sanitized diagnostics described below for further investigation.

## Phase 2B — normalize one inbox image into one staging candidate

This is an opt-in Windows-only processing slice. The two Phase 1 tools keep their
existing arguments, read-only annotations and response envelopes. The existing
**photoshop_process_image** tool opens a private temporary copy in
Photoshop and exports a candidate. It never opens the source file in Photoshop,
deletes or saves over that source, or writes into runtime assets/.
Human review and approval remain mandatory; this tool cannot promote candidates.
Follow [ART_GUIDE.md](../../source_art/ART_GUIDE.md) for staging review.

1. Put one user-selected **non-interlaced, 8-bit RGB or RGBA PNG**
   in source_art/_inbox/. Input and exported PNG must each be at most **24 MiB
   (25,165,824 bytes, inclusive)**. Source and canvas dimensions remain limited
   to 1..2048 px per axis. JPEG, indexed/grayscale PNG, 16-bit PNG, interlaced PNG,
   APNG, PNG tRNS color keys and PSD remain outside this slice.
2. Install the current packaged plugin (developers may reload in UDT). In this user's local Codex config,
   opt into the new tool by replacing only the existing enabled_tools line:

   ~~~toml
   enabled_tools = ['photoshop_ping', 'photoshop_get_active_document', 'photoshop_process_image']
   ~~~

   Keep the existing command/cwd, token, endpoint and permissions. Fully restart
   Codex Desktop and open a new chat. The paired plugin reconnects automatically;
   no preliminary ping is needed. The current setup enables all three tools.
3. Ask Codex to process the selected source into a **new** staging filename,
   providing integer canvas dimensions. Use mode="fit" to shrink larger artwork
   proportionally, or omit mode for the existing preserve_size behavior.
   Fit defaults to resample="bicubic"; request "nearest" explicitly for pixel art:

   ~~~json
   {
     "source_relative_path": "source_art/_inbox/selected.png",
     "staging_relative_path": "source_art/_staging/selected-candidate.png",
     "width_px": 384,
     "height_px": 384,
     "remove_background": false,
     "mode": "fit",
     "resample": "bicubic"
   }
   ~~~

4. Require ok=true, inspect the result and visually review the actual staging PNG
   for alpha edges, proportions, placement, padding and color. A staging file is
   **not an approved production asset**. This phase performs no runtime replacement.
   Existing files fail with DESTINATION_EXISTS; choose another name explicitly.

The optional mode parameter is an enum with default **preserve_size**:

| Mode | Behavior |
| --- | --- |
| preserve_size | Retain original pixel dimensions; smaller canvases fail with CANVAS_TOO_SMALL. |
| fit | Shrink only when necessary, proportionally, to fit the entire source within the canvas; never upscale. |

Fit uses one scale factor, min(1, canvas_width/source_width,
canvas_height/source_height), then rounds the resulting artwork dimensions to
the nearest whole pixel (half-up, minimum one pixel). This preserves aspect ratio
within unavoidable pixel rounding. The full source rectangle, including existing
transparent margins, participates in the fit. There is no trim, crop, independent
axis stretching or flattening. Offsets are floor((canvas - artwork) / 2), leaving
any odd extra padding pixel on the right/bottom. The plugin first adds symmetric
padding, then adds any odd extra pixel with a top-left canvas anchor.

The optional resample enum is **bicubic | nearest**, defaulting to **bicubic**.
It only affects fit when artwork actually shrinks; preserve_size, exact-size and
smaller inputs do not call resizeImage. Both choices use Photoshop's native
Document.resizeImage(width, height, undefined, ResampleMethod.BICUBIC or
ResampleMethod.NEARESTNEIGHBOR). No custom raster resampler is implemented.
Nearest can alias edges and lose fine detail; use it intentionally for pixel art.

With remove_background=false, Python verifies exact source alpha for unscaled artwork, exact sampled source alpha
for nearest (including full opacity for RGB), and zero alpha for every padding pixel.
Bicubic can produce partial edge alpha even from opaque RGB artwork. Both RGB and
RGBA downscales use the native alpha checksum. After the native resize and before
padding/export, the plugin reads the private document through imaging.getPixels
with applyAlpha=false, no targetSize, and 8-bit RGB components. It reconstructs
any trimmed empty borders for a bounded CRC-32 over the artwork alpha bytes,
then disposes the pixel buffer. Python independently decodes the exported PNG and
requires the artwork alpha checksum to match before publishing. Missing/invalid
checksums, changed alpha or opaque padding fail closed. No alpha is flattened or
replaced with a matte. CRC-32 checks padding/export integrity, not authenticity or
Adobe's interpolation kernel; the authenticated local plugin is trusted to perform
the native resize. Original source bytes remain independently checked unchanged.

The success field validation.alpha_validation distinguishes source_exact,
nearest_exact, and photoshop_bicubic_crc32. source_alpha_preserved means the
original/unscaled or selected resampled alpha survives padding/export; bicubic
does not claim byte identity with source alpha or independent kernel validation.
Visual review remains mandatory, and RGB/profile identity across Photoshop is
not promised.

RGB source pixels start fully opaque; native bicubic edge alpha is preserved.
An imported RGB Background layer is
duplicated into a regular pixel layer and the Background removed only in the
private document before resizing, so added padding stays transparent. Unexpected
Background layers on RGBA input remain rejected. Output is always RGBA8. If
Photoshop encodes an opaque export as RGB, Python adds an opaque alpha channel
without changing RGB pixel values or color profiles. It retains ancillary metadata
and extends sBIT significant-bits metadata for the new alpha channel, then repeats
PNG validation and enforces the 24 MiB publication limit. Exact-size
opaque artwork can therefore have has_transparency=false while still being RGBA;
the tool does not erase source pixels just to create transparency.

Background removal is an explicit **remove_background=true** opt-in; the default
false retains the existing normalization path. See the v0.5 contract below.
Opaque RGB exports are converted to RGBA only on the false path. Intentional
removal requires a real RGBA8 export with validated subject transparency.

Paths must be repository-relative, use forward slashes, and start with exactly
source_art/_inbox/ for input or source_art/_staging/ for output. Subdirectories
are allowed; safe missing staging subdirectories are created. Each component
must start with an ASCII letter, digit, underscore or hyphen, then contain only
those characters or dots (up to 128 characters/component, 512/path). The filename
must end in .png. Spaces, absolute/drive/UNC paths, backslashes, traversal,
empty/dot components, trailing dots, Windows device names and alternate streams
are rejected. Production assets/ and other source_art/ directories are rejected.

Python pins each parent and the source with Windows handles that deny write/delete
sharing, rejects symlinks/junctions/reparse points and hard-linked source files,
and holds those locks throughout processing. It checks PNG structure, CRCs,
bounded decompression, dimensions, original alpha and transparent padding before
publication. CREATE_NEW with exclusive sharing prevents overwrite even if another
process creates the destination during processing. Write/readback failures mark
the exclusive candidate for deletion before closing it. All candidates, input
files, .local/, .venv/ and caches remain Git-ignored; never force-add them.

The processing tool advertises readOnlyHint=false, destructiveHint=false,
idempotentHint=false and openWorldHint=false. Its success result is:

~~~text
{
  source_relative_path, staging_relative_path,
  width_px, height_px,
  mode, resample, source_color_type, artwork_width_px, artwork_height_px,
  offset_x_px, offset_y_px,
  background_removal_requested: false,
  background_removal_completed: false,
  validation: {
    format: "PNG", bit_depth: 8, color_type: "RGBA",
    has_transparency: boolean, dimensions_verified: true,
    source_alpha_preserved: true, alpha_validation,
    padding_verified: true,
    source_unchanged: true, bytes_written, sha256,
    human_approval_required: true
  }
}
~~~

Failures use the existing structured error envelope (ok=false, result=null,
isError=true). Processing errors include INVALID_PATH, PATH_UNSAFE,
UNSUPPORTED_PLATFORM, SOURCE_NOT_FOUND, DESTINATION_EXISTS, INVALID_DIMENSIONS, INVALID_MODE, INVALID_RESAMPLE,
CANVAS_TOO_SMALL, IMAGE_TOO_LARGE, INVALID_IMAGE, BACKGROUND_REMOVAL_UNAVAILABLE,
PHOTOSHOP_PROCESSING_FAILED, PHOTOSHOP_CANCELLED, OUTPUT_VALIDATION_FAILED and STAGING_WRITE_FAILED.
DISCONNECTED, PORT_IN_USE, TIMEOUT and BUSY retain their transport meanings.
Invalid MCP mode/resample arguments are rejected by the SDK's enum schemas before
the tool body; direct processor/wire validation uses INVALID_MODE/INVALID_RESAMPLE.
Invalid arguments never contact Photoshop or publish a file. New public result fields are additive;
Phase 1 tool schemas and the existing processing fields remain compatible.
Only one processing call runs at a time. A timeout/disconnect cannot publish a
late reply; Photoshop may still finish cleaning up its private temporary copy.

### v0.5 native background-removal contract

The existing tool's inputs are unchanged. No ActionJSON, command names, selections,
targets or execution options are accepted from MCP callers. With removal enabled,
the plugin checks that its private imported document has one intended active pixel
layer, then runs these fixed internal commands inside the existing executeAsModal scope:

~~~javascript
await photoshop.action.batchPlay([
  { _obj: "autoCutout", sampleAllLayers: false },
  { _obj: "make", new: { _class: "channel" },
    at: { _ref: "channel", _enum: "channel", _value: "mask" },
    using: { _enum: "userMaskEnabled", _value: "revealSelection" } }
], {});
~~~

Descriptor provenance: captured through **Actions > Copy As JavaScript** on
Photoshop **27.10 (20260824.r.26 9d9635d)** by recording Select Subject followed by
Layer > Layer Mask > Reveal Selection. It matches Adobe's shipped
removeBackgroundTalent.applyFnc mutation sequence in
`C:/Program Files/Adobe/Adobe Photoshop 2026/Required/UXP/com.adobe.unifiedpanel/js/524.js`
(SHA-256 `DC4B2E47EC038C2D21EB8BF634B1F2DD4970AD83709DC969833DA7BC717BF3A7`).
Neither recorded mutation has `_target`, `_options`, layer IDs or document IDs;
they operate on the active private document/layer. The helper's later layerID get
is bookkeeping. Its separate preview descriptors are not used here. A direct
Properties-panel Remove Background recording instead yielded the single wrapper
`{_obj:"removeBackground"}`; that wrapper's internals are not inferred or used.
See Adobe's [batchPlay and descriptor-discovery documentation](https://developer.adobe.com/photoshop/uxp/ps_reference/media/batchplay/).
DOM APIs continue to handle opening, normalization, export and cleanup.

**Device/Cloud disclosure:** Lunitora adds no external network integration,
Firefly Services, HTTP API, credentials or cloud storage. Photoshop's native
Select Subject/Remove Background follows its own **Preferences > Image Processing**
Device/Cloud setting; Adobe documents Device as the default. Cloud can use
Adobe-hosted processing. Lunitora neither overrides that preference nor promises
offline processing. See [Adobe's processing guidance](https://helpx.adobe.com/photoshop/desktop/make-selections/automatic-color-based-selections/improved-select-subject-and-remove-background-results.html).

Validation uses full-canvas composited 8-bit alpha captured immediately before
and after removal, **before any resize or padding**. getPixels uses applyAlpha=false;
trimmed empty bounds are reconstructed as zeros and pixel buffers are disposed.
RGB begins fully opaque. Originally visible means alpha >=16. The acceptance
floor is max(1, ceil(originally_visible_pixels / 1000)), or 0.1% rounded up.
A newly removed pixel must decrease by at least 16 and end at alpha <=8.
At least the same floor of foreground pixels must remain at alpha >=16.
Alpha increases are rejected. Existing transparent pixels on RGBA sources count
as zero removal evidence. An already-cut-out source with unchanged or insignificant
additional removal is a no-op, even if Photoshop successfully created a mask.
These are conservative internal validation thresholds, not Adobe quality guarantees.

Only passing removal proceeds to preserve_size/fit. The bridge carries bounded
scalar evidence (original/post-removal alpha CRC-32, visible/removed/foreground counts)
plus the artwork alpha checksum after any resize and before padding. Python checks
the original checksum/count against decoded source bytes and validates the count
bounds and thresholds. Without resizing it independently recomputes all removal
evidence from the exported artwork. With resizing, the authenticated plugin is
trusted for the original-resolution segmentation measurements; Python does not
recreate Photoshop's segmentation or interpolation. In every removal mode, Python
checks final artwork alpha against the native pre-padding checksum, RGBA8 PNG
structure/dimensions, every padding pixel, and unchanged source bytes before
exclusive staging publication. CRC-32 is an integrity check, not authentication.
Final artwork must retain both cleared pixels (alpha <=8) and visible foreground
(alpha >=16), using the original visible-area floor scaled to the fitted area,
rounded up to at least one. Padding alone cannot satisfy this check.

Successful intentional removal reports background_removal_requested=true,
background_removal_completed=true, source_alpha_preserved=false and
validation.alpha_validation="background_removal_native_crc32". The false path's
flags, alpha modes and wire fields remain unchanged. No-op, opaque or invalid
results never report successful completion and never publish a candidate.

| Failure | Structured code / diagnostic |
| --- | --- |
| Required native action/imaging API unavailable | BACKGROUND_REMOVAL_UNAVAILABLE |
| Native action rejection or returned action error | PHOTOSHOP_PROCESSING_FAILED |
| Confirmed modal cancellation or Photoshop error -128 | PHOTOSHOP_CANCELLED |
| Insignificant newly cleared alpha | OUTPUT_VALIDATION_FAILED / BACKGROUND_REMOVAL_NO_OP |
| Empty or near-empty subject | OUTPUT_VALIDATION_FAILED / BACKGROUND_REMOVAL_EMPTY_SUBJECT |
| Increased alpha or inconsistent removal evidence | OUTPUT_VALIDATION_FAILED / BACKGROUND_REMOVAL_ALPHA_INCREASED or BACKGROUND_REMOVAL_EVIDENCE_MISMATCH |
| Opaque fitted artwork / invalid host export | OUTPUT_VALIDATION_FAILED / BACKGROUND_REMOVAL_OUTPUT_OPAQUE or BACKGROUND_REMOVAL_OUTPUT_INVALID |
| Export checksum, padding, dimensions or source mismatch | OUTPUT_VALIDATION_FAILED / existing specific validation reason |

Unclassified native failures remain processing failures; localized error text is
not used to guess unsupported capability. Transport errors retain their meanings.
The processing deadline remains **30 seconds**. Temporary documents close without
saving, host auto-close remains registered if normal close fails, previous active
documents are restored where feasible, and both private files are attempted for
deletion. Cleanup failures cannot replace an earlier classified error. Cleanup-only
failure prevents success; a host/filesystem failure may still require manual cleanup.

**Production limitation — thin detached details can be lost:** native Photoshop
Remove Background may remove whiskers, individual hairs, fur wisps, wires or
similarly delicate edges along with the background. Live visual review on
Photoshop 27.10 confirmed loss of very thin detached whiskers/fur strokes in the
difficult fine-edge fixture. Passing alpha, checksum and dimension checks does
not establish that those details survived.

**Human visual approval remains mandatory:** automated alpha checks cannot verify
that Photoshop retained the correct subject, fine edges, shadows or color. Inspect
the actual staging PNG, especially delicate details, before approving it for
production; a successful tool response is not production approval.
No production promotion, arbitrary selection, crop/trim, replacement, generative
fill or new batch tool is included.
The v0.4 sequential batch workflow remains orchestration of individual calls.

### v0.5 live Photoshop validation — 2026-09-29

VERIFIED through the live Codex MCP integration on **Photoshop 27.10**, with visual
review confirmed by the user. All six calls requested remove_background=true.
Sources were in source_art/_inbox/ and candidates in source_art/_staging/; every
destination was absent before its call and no existing file was overwritten.
The first five cases used a 1024 x 1024 canvas with mode="preserve_size". The last
case used mode="fit", a 384 x 384 canvas and default bicubic resampling.

| Source PNG | Staging candidate | Verified live result |
| --- | --- | --- |
| bgremove_easy_plain_cat_1024.png | bgremove_easy_plain_cat_removed.png | Removal succeeded; visual result was good. |
| bgremove_medium_pattern_cat_1024.png | bgremove_medium_pattern_cat_removed.png | Removal succeeded; visual result was good. |
| bgremove_difficult_fine_edges_cat_1024.png | bgremove_difficult_fine_edges_cat_removed.png | Removal succeeded; visual review confirmed that very thin detached details such as whiskers/fur strokes can be lost. |
| bgremove_existing_alpha_cat_1024.png | bgremove_existing_alpha_cat_removed.png | Existing-alpha RGBA removal succeeded; pre-existing transparency alone was not treated as success. |
| bgremove_control_no_subject_1024.png | None (requested bgremove_control_no_subject_removed.png) | Native processing failed safely with PHOTOSHOP_PROCESSING_FAILED; no staging candidate was published. |
| bgremove_easy_plain_cat_1024.png (384 x 384 fit) | bgremove_easy_plain_cat_removed_fit_384.png | Removal and bicubic normalization succeeded together. |

All five successful responses reported RGBA8 output, verified dimensions,
transparent pixels, unchanged source bytes, background_removal_completed=true,
alpha_validation="background_removal_native_crc32" and human_approval_required=true.
The no-subject control's safe native processing failure is the observed live
result; it is not evidence of a live BACKGROUND_REMOVAL_EMPTY_SUBJECT diagnostic.

These cases verify the v0.5 plugin integration and the stated outcomes, not
universal segmentation quality. The Device/Cloud preference used was not recorded,
so this record does not claim separate verification of both processing modes.
The Device/Cloud disclosure above still applies: Lunitora adds no external network
service; Photoshop follows its own Image Processing preference.

### Historical Phase 2A live validation

**Live Phase 2A processing through Codex is verified on 2026-09-29.** A real
256 x 256 RGBA PNG from source_art/_inbox/phase2a_test.png produced the new
512 x 512 source_art/_staging/phase2a_test_512.png candidate. The tool reported
successful transparency, padding and source preservation, without background
removal. An identical second request returned DESTINATION_EXISTS without overwrite.
The final validation record below distinguishes this live result from mock tests.

That Phase 2A run did not verify same-size or odd canvas dimensions, restoration
of an existing unsaved document, cancellation, temporary-file cleanup or near-limit
runtime/memory on the actual host. Alpha edges and profile/color-management
behavior require visual review; alpha validation does not promise identical RGB
values. This historical Phase 2A record predates Phase 2B RGB conversion,
fit resampling and v0.5 background removal; current v0.5 live results are recorded
above. Cropping, upscaling, a dedicated batch MCP tool and production promotion
remain outside the implemented scope.

## Supported sequential batch workflow

Codex may process multiple selected `source_art/_inbox/` images by calling the
existing `photoshop_process_image` tool sequentially, once per image. Each image
remains an independent operation with its own source, staging destination,
arguments and result. Wait for each call to finish before starting the next;
only one processing call runs at a time.

1. Call `photoshop_process_image` for each selected source and its intended
   `source_art/_staging/` destination.
2. Record each success or failure and continue processing the remaining files
   if an item fails. A failed item must not undo successful candidates from
   earlier calls; there is no batch rollback.
3. At the end, report one aggregate table with source, destination, success or
   failure, error code, and successful artwork dimensions/offsets, plus total
   attempted, succeeded and failed counts.

All existing no-overwrite rules, path restrictions, staging-only behavior,
input/output validation and human review/approval requirements apply independently
to every item. Successful candidates remain unapproved staging files until human
approval; the workflow does not promote them to production. Rerunning a valid
source against an existing destination returns `DESTINATION_EXISTS`. Do not
delete, rename or overwrite an existing candidate to make a rerun succeed.

**Live validation through Codex:** four sequential calls used `mode="fit"`,
default bicubic resampling (the `resample` argument was omitted), a 384x384 canvas
and `remove_background=false`. Sources were in `source_art/_inbox/` and
destinations in `source_art/_staging/`:

| Source | Destination | Result | Artwork (W x H px) | Offset (X, Y px) |
| --- | --- | --- | --- | --- |
| batch_rgb_portrait_941x1672.png | batch_rgb_portrait_fit_384.png | Success | 216 x 384 | 84, 0 |
| batch_rgb_landscape_1600x900.png | batch_rgb_landscape_fit_384.png | Success | 384 x 216 | 0, 84 |
| batch_rgba_alpha_640x480.png | batch_rgba_alpha_fit_384.png | Success | 384 x 288 | 0, 48 |
| batch_invalid_grayscale_512x512.png | batch_invalid_grayscale_fit_384.png | Failure: `INVALID_IMAGE` | N/A | N/A |

Initial total: **4 attempted, 3 succeeded, 1 failed**. The unsupported grayscale
image failed independently and the three valid RGB/RGBA candidates remained intact.
Repeating the same four calls against the same destinations continued after every
failure: the first three returned `DESTINATION_EXISTS`, and grayscale again
returned `INVALID_IMAGE` (**4 attempted, 0 succeeded, 4 failed**). SHA-256 checks
confirmed all three existing candidates were unchanged; no new output was created.

This workflow intentionally uses repeated calls to the existing tool. A separate
batch MCP tool is not needed unless future scale or performance evidence justifies
adding one. No implementation, schema, dependency or functionality change is required.

## Files and local setup

Git Bash is required for Windows development instructions and manual commands.
Run the Windows Python executable directly as shown below; virtual-environment
activation is unnecessary. Quoted /c/ paths handle executable paths with spaces.

- core/: configuration, stdio MCP entry point and manual test driver.
- modules/photoshop/: tool schemas, bounded protocol and WebSocket bridge.
- bridges/photoshop_uxp/: plain HTML/JavaScript plugin; no frontend build.
- tests/: fake Photoshop peer, Python integration tests and mocked UXP getter tests.
- .local/: ignored pairing file and temporary local test data.
- .venv/: ignored isolated Python environment.
- ../.gdignore: keeps the entire tools directory outside Godot imports.

This workstation's environment and pairing file have already been created.
Reproduction on another PC uses its own local token. Do not copy credentials:

~~~bash
cd <repo-path-bash>/tools/lunitora_mcp
'<python-3.12-exe-bash>' -m venv .venv
./.venv/Scripts/python.exe -m pip install --no-cache-dir -r requirements.lock
./.venv/Scripts/python.exe -B -m core.server --setup
~~~

The base interpreter is standalone Python 3.12.10 x64. Neither ComfyUI Python is used.
Direct dependencies are exactly mcp==2.2.0 and websockets==17.1.
requirements.lock pins all 30 resolved distributions for this Windows/Python environment.
No global packages, Node packages, bundlers or frontend frameworks are installed.

Setup is idempotent: it creates .local/pairing-token.txt once and preserves it.
Normal startup never generates or prints a token.
An optional --config path accepts only the two timeout settings shown in
config.example.toml; endpoint and secret location cannot be configured.

## Transport and authentication

MCP uses stdio; stdout is reserved for MCP protocol traffic. Diagnostics use stderr.
The Python process binds explicitly to IPv4 127.0.0.1:43127.
The UXP plugin and test clients connect to ws://localhost:43127. The client
hostname matches the UXP manifest allowlist; it does not change the listener's
explicit IPv4 bind address. The listener has no LAN, wildcard, IPv6 or
alternate-port fallback. An occupied port leaves MCP discovery available and
returns PORT_IN_USE when a tool is called.

The 384-bit random pairing token lives in the ignored .local/pairing-token.txt.
After manual pairing, the plugin stores its user-supplied copy using UXP
secureStorage; if that cache is unavailable, pairing lasts for the current
connection and the panel reports that limitation. No token goes into tracked
configuration, command arguments, normal logs or the Codex configuration.
Never paste it into a chat, screenshot, commit or issue.

The first message must authenticate using the token and protocol version.
Python uses constant-time comparison. Only authenticated sockets receive requests.
Each authenticated session carries only the three allowlisted operations. A valid
reconnect replaces the old session and fails its pending calls; an invalid token
cannot replace a paired session. Panel reconnect detaches previous callbacks,
cancels the authentication timer and ignores stale callbacks.

This is a local bearer-token trust boundary: it prevents unauthenticated use and
LAN access. Plain loopback WebSocket transport is not protection against a
malicious process already able to read this user's files or memory. No firewall,
antivirus or Windows ACL settings are changed.

| Bound | Value |
| --- | --- |
| WebSocket JSON message | 33,555,456 UTF-8 bytes; inspection remains 262,144 bytes |
| Authentication message | 1,024 UTF-8 bytes |
| Python authentication / request timeout | 5 seconds each; configurable 0.05–30 |
| Processing request timeout | 30 seconds; one processing call at a time |
| Input / output PNG | 24 MiB (25,165,824 bytes) each; source/canvas 1–2048 pixels per dimension |
| Plugin connect/authentication timeout | 10 seconds |
| Accepted open WebSockets / authenticated session | 4 / 1 |
| Pending requests | 16 |
| Recursive layer count / nesting depth | 2,000 / 64 |

No partial document result is returned when an inspection limit is exceeded.
Inspection returns no file paths or document contents. Document/layer names are
returned and therefore appear in the manual test's output. Processing returns
repository-relative paths and validation metadata; image bytes travel only on
the authenticated local bridge.

## UXP manifest permissions

The entire requiredPermissions object is:

~~~json
{"network":{"domains":["ws://localhost/"]}}
~~~

Photoshop UXP 27.10 rejected the raw IPv4 allowlist with "Manifest entry not
found" during live diagnosis. The manifest now allows the localhost WebSocket
origin, while the plugin fixes its connection URL to ws://localhost:43127.
The temporary `"domains": "all"` permission is no longer used. Reload the plugin
in UDT before retrying the live test so the new manifest and client URL apply.

No additional filesystem, clipboard, process launching, WebView or user-information
permission is requested. Local token caching uses UXP secureStorage. The two
inspection operations use DOM getters only. Processing uses UXP's default private
temporary storage and executeAsModal to open a copy, optionally convert an RGB
Background and shrink the image, resize its canvas and export PNG. It closes that
copy without saving and restores the previous active document;
host auto-close registration also covers cancellation. No batchPlay or arbitrary
Photoshop action descriptor is accepted.

The manifest requires Photoshop 27.10.0 and host.data.apiVersion 2.
The panel also checks the running version. Older Photoshop releases are untested.
Restricted localhost permission acceptance is verified in this installation's
UXP runtime through the successful live Codex MCP calls. Automated tests also
verify the exact manifest allowlist, client URL, and IPv4-only listener binding.

## Version 1 bridge protocol

Authentication (the value below is a placeholder, not a usable token):

~~~json
{"type":"auth","protocol_version":1,"token":"<local-pairing-token>"}
{"type":"auth_result","protocol_version":1,"ok":true,"error":null}
~~~

Inspection requests contain exactly type, protocol_version, id and operation.
Python generates a unique ID for every call; responses must match both that ID
and operation. Unknown late response IDs cannot satisfy another request.

~~~json
{"type":"request","protocol_version":1,"id":"<unique-id>","operation":"photoshop_ping"}
{"type":"response","protocol_version":1,"id":"<same-id>","operation":"photoshop_ping","ok":true,"result":{"photoshop_version":"27.10.0","host_version":null,"uxp_version":null,"plugin_version":"0.1.0"},"error":null}
~~~

Failure responses use ok=false, result=null and an error object with code/message.
All error messages exposed to MCP are fixed text; peer exception details are not
forwarded. Binary frames, malformed JSON, duplicate JSON keys on the Python side,
unsupported protocol versions, inconsistent document data and unsupported
operations are rejected. Allowed operations are exactly the three public tool names.

Processing requests add one parameters object containing image_base64, width_px,
height_px, remove_background and optional mode/resample. Omitted mode means preserve_size;
omitted resample means bicubic. Existing calls need no new argument.
Python omits both fields for preserve_size to retain the exact Phase 2A wire request. Fit
always sends both mode and resample, including the default, and requires both the
updated Python server and UXP plugin. Older plugins reject the additional field
instead of silently using nearest. Reload UXP and restart/reconnect the MCP server
after updating both sides. The wire reply contains png_base64, width_px, height_px,
background_removal_requested and background_removal_completed, plus optional
resampled_alpha_crc32 (an unsigned 32-bit integer) for bicubic RGB/RGBA downscales.
Removal replies additionally require removal_evidence and resampled_alpha_crc32
even when not resized or when using nearest. removal_evidence contains only the
five bounded integers before_alpha_crc32, after_alpha_crc32, visible_pixels,
removed_pixels and foreground_pixels. These fields are internal and are not
returned as image payloads to MCP callers. Error replies may carry one allowlisted
removal reason; arbitrary peer diagnostics and error text are never forwarded.
Temporary native_diagnostics probes have been removed. Reload the UXP plugin and
restart the Python server together; RGB bicubic now supplies the same required
pre-canvas checksum as RGBA. Legacy replies remain valid for unscaled/nearest output.
Bicubic RGB/RGBA
downscales without a native checksum fail output validation. The byte fields
use canonical base64; neither repository paths nor arbitrary host paths reach UXP.
Python validates the returned PNG before writing it to staging and returns only
the public metadata above. Protocol version 1 and the inspection schemas remain
compatible. Limits are inclusive and checked in both Python and UXP:

| Bound | Bytes | Calculation / scope |
| --- | ---: | --- |
| Input or output PNG | 25,165,824 | 24 × 1024 × 1024 |
| Canonical Base64 PNG | 33,554,432 | 4 × ceil(25,165,824 / 3), exactly 32 MiB |
| Processing JSON / WebSocket message | 33,555,456 | Base64 maximum + 1,024 bytes for protocol metadata |
| Inspection JSON message | 262,144 | Original Phase 1 limit, unchanged |
| Authentication request | 1,024 | Original application-level authentication limit, unchanged |

The 1 KiB allowance covers either envelope, including four-digit dimensions and
the maximum 64-character ID even when every character needs six JSON escape
bytes. The boundary tests include both mode/resample and the maximum native alpha
checksum and removal evidence in the response, and require metadata to remain within the same 1 KiB.
Limits count
UTF-8 bytes, not JavaScript character count. WebSocket framing
headers are separate from its message payload limit. A single unfragmented frame
at the maximum has a 10-byte header (server) or 14-byte header (masked client).
Compression remains disabled; each direction carries one image in one JSON
message, with no application chunking or batching. Larger files/messages fail.

The old 128 KiB PNG bound expanded to 174,764 Base64 bytes inside the old
262,144-byte transport bound. Increasing only the PNG bound would fail at the
Base64, protocol and WebSocket gates. Python's server max_size now uses the same
33,555,456-byte bound as the UXP message gate. Authentication, IPv4-only binding,
four-connection limit, four-frame receive queue, 16 pending-request limit and
single active image processor remain unchanged. UXP's Base64 codec uses bounded
buffers and iterative validation; the former whole-string regex overflows the
stack at this new size. This changes only in-memory encoding, not the transport.

## MCP schemas

Both inspection tools accept an empty arguments object, {}. Both advertise readOnlyHint=true,
destructiveHint=false, idempotentHint=true and openWorldHint=false.
The SDK publishes their JSON input/output schemas through tools/list from the
TypedDict definitions in modules/photoshop/protocol.py.

All tools return structuredContent using this envelope (and a matching JSON text block):

~~~text
{
  ok: boolean,
  connected: boolean,
  protocol_version: integer,        // 1
  bridge_version: string,           // "0.1.0"
  round_trip_ms: number | null,
  result: operation result | null,
  error: {code: string, message: string} | null
}
~~~

Errors also set the standard MCP isError field. A successful ping requires a fresh
Photoshop reply; cached connection/process state is insufficient. connected=true
means the operation received an authenticated reply; it can also accompany a
Photoshop-side read error. Transport timeout/disconnect failures report false.
This existing boolean schema cannot represent an unknown/not-contacted state;
it is not a live connection-status query. Local preflight failures such as
IMAGE_TOO_LARGE return connected=false and round_trip_ms=null because Photoshop
was not contacted for that request, even when its authenticated socket is still
connected. Do not interpret that validation error as DISCONNECTED. No cached or
invented host state is substituted; use a fresh photoshop_ping to check it.

photoshop_ping result:

~~~text
{
  photoshop_version: string,
  host_version: string | null,
  uxp_version: string | null,
  plugin_version: string
}
~~~

photoshop_get_active_document result:

~~~text
{
  has_document: boolean,
  document: null | {
    id: integer,
    name: string,
    width_px: number,
    height_px: number,
    saved: boolean | null,
    top_level_layer_count: integer,
    recursive_layer_count: integer,
    layers: [
      {id: integer, name: string, kind: string, children: [same layer shape]}
    ],
    artboard_count: integer,
    artboards: [{id: integer, name: string}]
  }
}
~~~

No open document is a successful {has_document:false, document:null} result.
Layer arrays preserve Photoshop DOM order; names need not be unique. IDs identify
layers/artboards. Recursive counts include groups and their descendants.
saved reflects Photoshop's saved/modified getter, not a filesystem existence check.
It is null if the optional getter is unavailable. Reading it does not save anything.

Error codes: UNPAIRED, PORT_IN_USE, DISCONNECTED, TIMEOUT, BUSY, AUTH_FAILED,
INVALID_MESSAGE, PAYLOAD_TOO_LARGE, UNSUPPORTED_OPERATION, PHOTOSHOP_READ_FAILED,
DOCUMENT_TOO_LARGE and UNSUPPORTED_HOST. The server still initializes and lists
all three tools when unpaired, disconnected or unable to bind the fixed port.

## Automated validation without Photoshop

### v0.5 validation status after live processing — 2026-09-29

VERIFIED: the complete Phase 1 + Phase 2A + Phase 2B + v0.5 automated suite
passes after releasing the fixed localhost test port. The repository bridge was
identified before being stopped, and a bind preflight confirmed port 43127 was
free. Python unittest discovery ran **160 tests in 26.102 seconds: 0 failures,
0 errors, 0 skips**.

| Suite | Passed | Failures | Errors | Skips |
| --- | ---: | ---: | ---: | ---: |
| Python Phase 1 | 47 | 0 | 0 | 0 |
| Python Phase 2A/2B | 76 | 0 | 0 | 0 |
| Python validation diagnostics | 12 | 0 | 0 | 0 |
| Python v0.5 background removal | 25 | 0 | 0 | 0 |
| JavaScript Phase 1 plugin/panel | 53 | 0 | 0 | 0 |
| JavaScript Phase 2 processing, including v0.5 | 104 | 0 | 0 | 0 |
| Total tests/checks | **317** | **0** | **0** | **0** |

All previously blocked integration tests executed, including authenticated
MCP/WebSocket success and error classification, timeout/late-reply isolation,
real stdio, reconnect, protocol/file size boundaries and Windows path protections.
Segmentation remains deterministic and mocked. The suites also cover RGB/RGBA,
removal thresholds, pre-existing alpha, empty subjects, padding-only transparency,
evidence mismatches, destination races, fixed descriptors, cancellation and cleanup.
Four additional validation commands pass: Python compilation (19 source files),
pip check (no broken requirements), and syntax checks for both UXP JavaScript
modules. No functionality change or new dependency was needed for this rerun.
This clean run supersedes the earlier port-conflict attempt; no validation is
deferred because of port 43127.

All **14 repository/port audit checks pass**. The full current diff, including the
untracked background-removal test file, was reviewed with no unintended changes
found. Only this README changed during the post-live validation pass; the existing
v0.5 implementation and tests were preserved. No credential literals or current
local pairing-token values were found in commit candidates. All 22 ignore probes
pass for .local, .venv, caches, logs, _inbox, _staging and live artifacts. The ten
live source/candidate files are unchanged, no ignored files are already tracked,
the index is unchanged and empty of staged changes, and git diff --check passes.
Port 43127 is free after validation. Nothing was staged, committed or pushed.
Audit scripts and logs remain under ignored .local/v05-live-validation-20260929-final/.

VERIFIED live: the six Photoshop 27.10 cases recorded above, including RGB and
existing-alpha RGBA removal, preserve_size, bicubic fit, safe no-subject failure
without publication, and the fine-detail loss confirmed by human visual review.

NOT EXECUTED in this automated rerun: additional live Photoshop requests, a
separate Device-versus-Cloud comparison, real cancellation, active unsaved-document
restoration/temporary-file cleanup inspection, or near-limit runtime/memory
measurement. The selected six live cases were completed before this rerun.
Godot/game tests are outside this toolkit validation.

REQUIRES USER TEST before relying on those additional cases: an already-cut-out
unchanged-alpha/no-op input; removal with nearest fit, partially transparent RGBA
fit and odd padding; real cancellation and active-document restoration/cleanup;
and near-limit performance within the unchanged 30-second deadline. Record and
exercise the intended Device/Cloud preference without an automatic preference
change. Every production candidate still requires human visual approval,
especially for thin detached details; the completed six-case live validation
does not remove that requirement.

Run from the toolkit directory with no other bridge occupying port 43127:

~~~bash
./.venv/Scripts/python.exe -m compileall -q core modules tests
./.venv/Scripts/python.exe -B -m unittest discover -v -s tests
./.venv/Scripts/python.exe -m pip check
'/c/Program Files/nodejs/node.exe' --check bridges/photoshop_uxp/index.js
'/c/Program Files/nodejs/node.exe' --check bridges/photoshop_uxp/processing.js
'/c/Program Files/nodejs/node.exe' tests/test_plugin.js
'/c/Program Files/nodejs/node.exe' tests/test_processing.js
git diff --check
~~~

Node is used only for mock tests through an already installed interpreter and
built-in modules; it is not a plugin/server runtime dependency. Do not install
Node/npm packages for this toolkit.

The Python suite uses temporary generated credentials and a fake WebSocket peer.
It covers MCP initialization and exact registration, real stdio protocol/stdout
purity, successful fresh pings, errors, timeouts, bad/no authentication, unsupported
operations, disconnects, occupied port, no document, Unicode/duplicate names,
nested groups/artboards, reconnect, malformed/oversized replies and bounded
pending work. Temporary test files stay under ignored .local.

The Phase 1 JavaScript suite runs the actual plugin getter code against read-only mocks
that throw on writes. This verifies response shape, ordering, Unicode, bounds,
safe errors and version checks without interacting with Photoshop.

Phase 2A adds generated PNG fixtures, real Windows path/handle and publication
checks, independent alpha/padding validation, and new-tool calls through MCP plus
an authenticated fake WebSocket peer. Its JavaScript suite runs the actual
processing/dispatch modules with mocked Photoshop documents and private storage,
covering canvas/export options, resource cleanup, cancellation and safe failures.
Phase 2B adds RGB decoding/conversion, fit geometry, sampled-alpha verification,
no-upscale/exact-size cases, explicit odd centering, enum/schema validation and
cleanup failures during background conversion or image resizing. Resampling tests
cover omitted/default bicubic, explicit bicubic/nearest, invalid enum values,
legacy callers, native alpha capture/disposal, checksum validation and safe failure.
The original
Phase 1 tests and UXP getter/panel suite remain unchanged.

Loopback tests must run in a normal Windows user context. The audit found the
Codex offline sandbox blocks loopback; no firewall workaround is implemented.
Run only one test suite/bridge at a time. Tests never stop another process.

## Phase 1 validation record — 2026-09-29

Live verification through the real Codex MCP integration succeeded before the
automated validation run:

- photoshop_ping returned ok=true and connected=true, Photoshop/host version
  27.10.0, UXP uxp-9.4.1-0, plugin/bridge version 0.1.0, protocol version 1,
  and a measured round-trip time of 1.326 ms.
- photoshop_get_active_document returned ok=true and connected=true with the
  active document's name, 384 x 384 pixel dimensions, one pixel layer, no
  artboards, and saved=true; its round-trip time was 15.588 ms.
- These calls verify live Photoshop connectivity and Codex MCP activation.

The complete automated rerun passed after the live bridge was stopped to free
the fixed test port: 47 Python tests and 51 UXP/plugin tests (37 getter/protocol
checks and 14 panel checks), with zero failures or skips. Python/JavaScript
syntax checks, pip check, all 30 locked dependency versions, manifest/security
checks, the 127.0.0.1:43127 binding test, 11 Git ignore checks, and whitespace
checks passed. No credentials or local/generated files were found among the
22 commit candidates. Automated tests use fake peers and mocked UXP; they do
not replace the live verification above or establish every manual scenario below.

## Phase 2A automated validation record — 2026-09-29

79 Python tests pass: 47 Phase 1 tests and 32 Phase 2A tests. The UXP mock suites
pass 79 checks: 51 existing checks and 28 processing checks. There are no failures
or skips. Syntax checks cover 16 Python files and four JavaScript files.
pip check and all 30 locked versions pass, as do 15 Git-ignore checks, manifest/
loopback contracts, README checks and the credential/whitespace review of the
14 changed/new files. The original two MCP functions are unchanged.

This historical record verified automated behavior only. At that point, Phase 2A
had not run in live Photoshop or through an activated Codex processing tool; no
user artwork was processed. The user's Codex configuration and loaded plugin
were not changed during that run. The later live result is recorded below.

## Phase 2A 24 MiB limit validation — 2026-09-29

After the first live tool request rejected a 1,872,343-byte source at the former
128 KiB preflight limit, the image limit was raised to 24 MiB and the processing
message limit to 32 MiB plus 1 KiB. The existing authenticated localhost transport,
permissions, source/staging protections, no-overwrite publication, canvas limit,
protocol version and inspection schemas remain in place.

The complete suites pass **87 Python tests (47 Phase 1 + 40 Phase 2A)** and
**89 JavaScript checks (53 getter/panel + 36 processing)**, with no failures or
skips. Coverage includes generated valid PNGs one byte below, exactly at and one
byte above the image limit; input and output through MCP and authenticated
WebSockets; exact UTF-8 message boundaries; over-limit WebSocket closure (1009);
canonical Base64/padding; preserved inspection limits; and an oversized-source
preflight error followed by a successful fresh ping on the same connection.
No large fixtures are checked in. Syntax checks pass for all 16 Python and four
JavaScript files, along with pip check and git diff --check.

The initial Python run encountered the already-running repository MCP listener
on the fixed port. After stopping that verified bridge process (without stopping
Photoshop), the complete suite passed. Restart the MCP server and reload the UXP
plugin, then reconnect before live testing the new limits; both endpoints need
the updated code. The large transfers were tested with fake peers/private-storage
mocks, not live Photoshop. Verify actual export, alpha/padding, unsaved-document
restoration, cancellation/cleanup, and near-limit runtime/memory within the
unchanged 30-second deadline on Photoshop 27.10.

At the time of that limit audit, the original phase2a_test.png header was
941 × 1672, 8-bit RGB (PNG color type 2), not RGBA. Its former 384 × 384 request
would also require cropping. The raised
byte limit does not relax either restriction: use a user-selected transparent
RGBA8 PNG and a canvas at least its original width and height, up to 2048 per axis.
No candidate was produced from that original source during this limit update.

## Final Phase 1 + Phase 2A validation after live processing — 2026-09-29

VERIFIED: the live Codex processing request returned ok=true and connected=true
with a 1,620.815 ms round trip. The 256 x 256 RGBA source is 96,910 bytes; the
512 x 512 candidate is 107,877 bytes. Its SHA-256 is
`c0a129bec42a6d1d3bac2e4f59af7dd1b63744ddc8b0fc997b25a35940065346`.
The response confirmed dimensions, transparency, preserved source alpha,
transparent padding and an unchanged source. Background removal was neither
requested nor completed. The repeated request returned DESTINATION_EXISTS.
The final read-only artifact audit independently confirmed alpha/padding and
that the existing candidate still matches the successful response's hash/size.

The final automated run passed **255 tests/checks**, with **0 failures, 0 errors
and 0 skips**. Counts are test cases/check groups, not individual assertions or
parameterized subcases:

| Validation | Count |
| --- | ---: |
| Phase 1 Python tests | 47 |
| Phase 2A Python tests | 40 |
| UXP getter/panel checks | 53 |
| UXP processing checks | 36 |
| Python syntax checks | 16 |
| JavaScript syntax checks | 4 |
| Installed versions against requirements.lock | 30 |
| pip check | 1 |
| Git-ignore path checks | 15 |
| Security and scope checks | 10 |
| Whitespace check, including new files | 1 |
| Existing live candidate checks | 2 |
| Total | 255 |

The sandbox could not launch the configured Python. The first run in the normal
Windows context then encountered the live bridge on port 43127: 87 tests ran
with 25 failures and 20 errors, with no skips. After verifying its executable,
repository launcher and listener ownership, only that MCP bridge was stopped;
Photoshop remained open. The full Python rerun passed all 87 tests in 25.160 s.
No functional changes were needed. Restart the MCP server and reconnect the
panel before the next live tool call.

The complete current diff, including six new files, was reviewed: 16 paths are
confined to tools/lunitora_mcp (10 modified, six untracked), with no unintended
functional or runtime-asset changes found. This final pass changes only this
README among commit candidates. The original two read-only tool functions are
unchanged from HEAD. Manifest permissions remain localhost-only; automated tests
verify IPv4-only binding, authentication, safe paths, no-overwrite races and
sanitized failures. All 30 installed dependency versions match the lock.

The security audit found no credential patterns in the 16 changed/new files and
no copy of the actual local pairing token in 300 tracked files plus six untracked
commit candidates. No ignored files are already tracked. Pairing tokens, .local,
.venv, generated bytecode/caches, logs, local configuration, _inbox inputs and
_staging outputs are excluded from ordinary Git addition. The real test input
and candidate are ignored and untracked. Audit scripts/results/logs stay in
ignored .local. The index is unchanged from HEAD; nothing was staged, committed
or pushed. Ignore rules do not protect files deliberately force-added.

NOT EXECUTED in this final pass: another live processing/export request, Godot
game regression tests, fresh-workstation setup, or other Photoshop/OS versions.
The 24 MiB boundary transfers used authenticated fake peers and UXP mocks.

REQUIRES USER TEST: visually review the candidate's edges, placement and colors;
exercise same-size/odd canvases, unsaved-document restoration, cancellation and
temporary cleanup in Photoshop; and assess near-limit speed/memory against the
30-second processing deadline. Human approval is still required before any
separately authorized production promotion.

## Phase 2B validation record — 2026-09-29

This historical record covers the original nearest-only implementation. The
resampling-quality update below supersedes its interpolation and live-test status.

VERIFIED: the existing tool now accepts optional mode="preserve_size"|"fit",
defaulting to preserve_size, and bounded RGB/RGBA8 sources. The complete suite
passes **108 Python tests** (47 Phase 1 and 61 Phase 2) and **109 JavaScript
checks** (53 getter/panel and 56 processing), with no failures, errors or skips.
This adds 21 Python tests and 20 JavaScript checks to the merged Phase 2A suite.
Cases include portrait/landscape fit, exact and smaller inputs, proportional
pixel rounding, no upscale, odd centering, retained alpha values, RGB-to-RGBA
output, profile/significant-bits metadata, invalid modes, SDK schemas, real MCP
transport with fake peers, and cleanup of failed private-document operations.
Phase 2 was rerun after the final RGB metadata correction.

An additional **79 audit checks** pass: 16 Python and four JavaScript syntax
checks, 30 locked dependency versions, pip check, 15 ignore paths, 10 security/
scope checks, whitespace, and two checks on the untouched Phase 2A live candidate.
The total is **296 distinct tests/checks, 0 failures, 0 errors and 0 skips**;
parameterized subcases and repeated runs are not counted twice.

The diff contains only the nine announced files: this README, UXP index.js and
processing.js, Python png_validation.py/processing.py/protocol.py/tools.py, and
test_phase2.py/test_processing.js. The manifest, authentication/configuration,
transport, path_security.py, both ignore files, dependency lock, core server and
Phase 1 test files are unchanged. The original two MCP function bodies are
unchanged, and no new tool, dependency, background removal, batching, cropping,
production promotion or Godot integration was added.

No credential patterns were found in changed files; the actual local pairing
token is absent from all 306 tracked working-tree files. No ignored files are
tracked. Local credentials/environments/caches, inbox inputs and staging outputs
remain ignored. The existing Phase 2A candidate's SHA-256 is unchanged. Audit
scripts and logs remain under ignored .local. Nothing was staged or committed.

NOT EXECUTED: live Photoshop Phase 2B RGB conversion or fit, live near-limit
runtime/memory tests, fresh-workstation/other-host validation, or Godot tests.
Automated UXP tests use mocks; they do not establish actual Photoshop sampling
alignment, background-layer conversion or visual quality.

REQUIRES USER TEST: reload the UXP plugin and restart the MCP server, reconnect,
then use selected RGB and RGBA sources with fresh staging filenames. Verify fit
for portrait/landscape images, no upscale for smaller images, exact-size opaque
RGB-to-RGBA output, odd padding placement, partial/zero alpha, color/edge quality,
unsaved-document restoration, cancellation and temporary cleanup. Confirm the
host's nearest-neighbor sample alignment agrees with independent validation and
that a repeated destination is rejected. Keep human review before any separately
authorized production promotion. Limits remain 24 MiB per PNG, 2048 pixels per
source/canvas axis and a 30-second processing request deadline.

## Phase 2B resampling-quality update

Before implementation, the current official Adobe UXP documentation was checked:
Document.resizeImage is documented since Photoshop 23.0, and ResampleMethod
BICUBIC/NEARESTNEIGHBOR since 22.5, covering the required Photoshop 27.10 host.
The Imaging API documents getPixels, applyAlpha=false, trimmed sourceBounds,
full-resolution reads without targetSize, getData({chunky:true}), and dispose().
These native APIs preserve the existing private-document/modal architecture and
require no additional manifest permissions or dependencies.

The user verified the previous nearest-only portrait/landscape RGB fits, RGBA
no-upscale and odd-centering cases live in Photoshop 27.10, but found degraded
edges/detail during reduction. Bicubic is now the default for fit; explicit nearest
retains the previous sampling behavior. The new bicubic path still requires live
visual comparison and RGBA alpha/edge review after both endpoints are reloaded.
In particular, confirm native alpha capture for partial/zero alpha and trimmed
borders, cancellation/cleanup, and near-limit performance within the unchanged
30-second deadline. Automated UXP mocks do not establish live visual quality.

VERIFIED automated validation: **117 Python tests** (47 Phase 1, 70 Phase 2)
and **120 JavaScript checks** (53 getter/panel, 67 processing), with no failures,
errors or suite skips. Python completed in 24.895 seconds. The update adds nine
Python tests and eleven JavaScript checks; parameterized subcases are not counted
separately. The supplemental audit passed **96 checks**: 16 Python/four JavaScript
syntax checks, 30 dependency pins, pip check, 24 ignore paths, 10 security/scope
checks, whitespace and 10 existing-artifact checks. Total: **333 passed**.

NOT EXECUTED: two historical alpha/source comparisons because phase2a_test.png
and phase2b_rgb_test.png are no longer in the inbox. All six existing candidate
hashes still match their prior live results. Thus 335 tests/checks were planned,
333 passed, zero failed, and two supplemental checks were skipped. The new
bicubic path was not run live; the four previously confirmed live Phase 2B cases
used nearest. No Godot tests or other-host/fresh-workstation checks were run.

The change remains confined to the same nine toolkit files. Security/ignore rules,
manifest permissions, authentication, binding, source/staging locks, no-overwrite
publication, dependencies and all size/deadline limits remain unchanged. No
credential patterns were found in the changed files; the actual pairing token is
absent from all 306 tracked files. Test artifacts and audit logs remain ignored.
Nothing was staged, committed or pushed. REQUIRES USER TEST: reload/reconnect both
endpoints and compare fresh bicubic/nearest candidates in Photoshop 27.10,
including partially transparent RGBA and fine edges, before approving quality.

## Phase 2B validation-failure diagnostics

The instrumented live default-bicubic RGB portrait fit (941x1672 to 384x384)
failed with OUTPUT_VALIDATION_FAILED / ARTWORK_ALPHA_MISMATCH. The expected
216x384 artwork rectangle at (84,0) and nonzero-alpha bounds agreed. All 1,196
partial-alpha pixels were on its edge, alpha ranged from 220 to 255, and padding
passed. Native pre-canvas and exported artwork alpha CRC32 both equaled 233626159.
The source was unchanged and no Background layer existed before/after resize or
after canvas expansion. No failed candidate was published.

Failures now include error.diagnostics with the original failed condition,
expected/actual output dimensions, expected artwork rectangle, observed nonzero
and fully opaque alpha bounds, exported/normalized color type, transparency,
independent padding/alpha/source-unchanged failure flags, and bounded alpha counts
and first mismatches. Null means evidence was unavailable. Observed alpha bounds
are not claimed to locate artwork with transparent borders. Failed images are
never published, and no tokens, Base64 payloads or pixel buffers are logged.

RGB bicubic shrinking now uses the existing RGBA native-alpha validation path.
The plugin captures resampled_alpha_crc32 once after resizeImage and before
resizeCanvas/export, with the existing bounded Imaging API read and disposal.
Missing/unreadable native evidence fails closed. Python independently checks
output dimensions, the expected centered artwork rectangle, zero alpha everywhere
outside it, matching native/exported artwork alpha CRC32, and unchanged source.
Unscaled RGB and nearest remain exactly opaque; bicubic RGBA behavior is unchanged.
Native resize, canvas expansion and export calls are unchanged; no edge alpha is
forced to 255. The temporary Background/alpha-summary host probes and their wire
field have been removed. Failure diagnostics retain expected/actual checksums,
observed bounds, alpha extrema/counts and independent failure flags. Checksum
validation cannot report individual native pixel mismatches without native pixels;
those fields correctly remain null.

Official Adobe documentation was rechecked:
- [Document](https://developer.adobe.com/photoshop/uxp/ps_reference/classes/document/)
  specifies resizeImage(width, height, resolution, resampleMethod, amount), and
  resizeCanvas(width, height, anchor), with centered expansion by default.
- [Constants](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/modules/constants)
  lists ResampleMethod.BICUBIC/NEARESTNEIGHBOR for Document.resizeImage and
  AnchorPosition.TOPLEFT. The current native calls match those signatures.
- [Canvas behavior](https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/change-the-canvas-size.html)
  distinguishes colored extension with a Background layer from transparency on
  regular layers. The live reproduction ruled out a residual Background layer
  and located the partial edge alpha before padding/export.

Regression coverage uses a synthetic opaque RGB 941x1672 source with a 216x384
native-alpha fixture and 1,196 partial edge pixels. Matching checksum passes;
missing/invalid checksum, changed exported alpha, wrong dimensions, shifted
artwork and nonzero padding fail. In-memory MCP checks require native proof before
publishing. This fixture reproduces the observed geometry and alpha characteristics,
not Photoshop's interpolation kernel or the exact live pixels.

Validation of the fix: 94 Python tests pass, including all validator/diagnostic
regressions and in-memory MCP publication checks. The full discovery run before
the final in-memory regression ran 134 tests: 93 passed and 41 test methods were
affected by the active bridge occupying 127.0.0.1:43127 (25 failure and 23 error
records, including subtests). The final suite contains 135 tests; the 94 without
those recorded port conflicts pass. The 41 transport/integration methods still
require a clean rerun with that fixed port free; this is not a fully passing
Python suite. No listener was stopped or endpoint changed. Both JavaScript suites
pass 126 checks (53 plugin/panel and 73 processing). Syntax checks pass for 18
Python and four JavaScript files, all 30 locked dependency versions match,
pip check reports no broken requirements, and git diff --check passes.

After automated validation, live verification still requires restarting the Python
MCP server and reloading/reconnecting UXP. Re-run the existing 941x1672 RGB portrait,
384x384 canvas, fit, default bicubic, no background removal, and a new absent staging
filename. Require ok=true with alpha_validation=photoshop_bicubic_crc32, then
visually review the candidate. Check bicubic RGBA and explicit nearest/preserve_size
controls after reload. Automated mocks do not establish live Photoshop success.

## Manual UDT loading and pre-Codex live test procedure

1. Keep Photoshop 2026 27.10 open. Confirm Developer Mode is enabled.
   If Photoshop requires a restart, handle any unsaved work yourself first.
2. In Adobe UXP Developer Tool, choose Add Plugin and select:
   <repo-path>\tools\lunitora_mcp\bridges\photoshop_uxp\manifest.json
3. Select the Photoshop 27.10 host and Load the added plugin.
4. In Photoshop, open Plugins > Lunitora Photoshop Bridge. Confirm the panel
   shows Bridge 0.1.0, the Photoshop version and its disconnected status.
5. Open a normal Git Bash terminal and prepare the local pairing value:

~~~bash
cd <repo-path-bash>/tools/lunitora_mcp
notepad.exe './.local/pairing-token.txt'
~~~

Copy the token into the panel's password input and close Notepad without changes.
Do not print the token in the terminal. On later connections, a successfully
stored UXP secureStorage token lets the input remain empty.

6. In that Git Bash terminal, start the supplied pre-Codex test driver:

~~~bash
./.venv/Scripts/python.exe -B -m core.server --live-test --wait-seconds 120
~~~

This driver owns one actual stdio MCP child process, initializes it, verifies
the exact registered tool list and prints that it is waiting for Photoshop. It retries
DISCONNECTED or transient TIMEOUT results every 300 ms until --wait-seconds
expires. The deadline also bounds an in-flight ping. Expiry reports a clear
TIMEOUT failure; other errors, including authentication/protocol errors returned
by the tool, fail immediately. A successful fresh ping ends the wait and triggers
one active-document call. The child process and bridge close on success or failure.
Do not start a second server alongside it.

7. While the driver waits, select Connect / Reconnect in the Photoshop panel.
   Confirm Connected · inspection and staging candidates. If authentication fails, check the local token.
8. The driver calls photoshop_ping through MCP. Confirm ok=true, connected=true,
   protocol_version=1, bridge/plugin versions, the actual Photoshop version and
   a measured round_trip_ms. UXP/host version fields may be null if unavailable.
9. The driver then calls photoshop_get_active_document. Compare its name,
   pixel dimensions, ordered layers, counts, artboards and saved state with the
   existing document. Confirm selection, history and dirty state are unchanged.
   With no document open, expect has_document=false and document=null.
10. The driver exits after printing both structured results to stderr, closes its
    MCP child and frees port 43127. The panel becoming disconnected is expected.
    To repeat, rerun the driver and select Reconnect.

A normal stdio server is launched with:

~~~bash
./.venv/Scripts/python.exe -B -m core.server
~~~

That command waits for an MCP client on stdin; it is not a human command prompt.
Use --live-test for the supplied manual pre-Codex test.

The manual driver reads only the same two operations. It does not open documents,
alter images, save/export files, auto-load UXP, or update Codex configuration.

## Codex configuration — activation verified

Codex MCP activation is verified on this workstation. Reference configuration:

~~~toml
[mcp_servers.lunitora_photoshop]
command = '<repo-path>\tools\lunitora_mcp\.venv\Scripts\python.exe'
args = ['-B', '-m', 'core.server']
cwd = '<repo-path>\tools\lunitora_mcp'
startup_timeout_sec = 15
tool_timeout_sec = 35
enabled_tools = ['photoshop_ping', 'photoshop_get_active_document']
~~~

Codex launches the Python executable directly without a terminal shell.
Keep the Windows absolute command/cwd paths above; /c/ and /d/ paths are for
Git Bash commands only.

No token belongs in this block. Its process must run in the normal Windows user
context that passed the loopback audit. The automated validation run does not
change the existing Codex configuration.

## Connection diagnostics and manual retry

The UXP console uses the prefix [Lunitora UXP]. The panel's small read-only detail
shows the latest diagnostic, including sanitized constructor errors, onerror,
close code/reason/wasClean and authentication outcomes. Full exception
name/message/stack details, when supplied by UXP, go to the console as sanitized
strings. Message diagnostics contain only recognized type/operation names.
Tokens, authentication payloads and raw event/error objects are never logged.
Sensitive-looking error text is redacted before truncation or display.

For --live-test only, its child receives LUNITORA_LIVE_TEST_DIAGNOSTICS=1 in its
own environment. Stderr then records listener startup, accepted WebSocket
connections, authentication receipt/outcome, operation names and connection
closure. Normal MCP startup does not enable these extra diagnostics, and stdout
remains MCP protocol traffic. The WebSocket library's wire logging stays disabled.

1. Stop any previous manual live-test with Ctrl+C in its Git Bash terminal.
2. In UXP Developer Tool, open the existing Lunitora Photoshop Bridge plugin's
   Debug console, then Reload the plugin so the updated JavaScript and HTML load.
3. Open the plugin panel in Photoshop. Expect a plugin initialization diagnostic
   and a typeof WebSocket value in the console/panel.
4. In Git Bash run:

~~~bash
cd <repo-path-bash>/tools/lunitora_mcp
./.venv/Scripts/python.exe -B -m core.server --live-test --wait-seconds 120
~~~

5. Confirm stderr says Bridge listening on 127.0.0.1:43127 and Waiting for Photoshop.
   Use the existing cached pairing token, or paste the existing local token into
   the password input. Select Connect / Reconnect once.
6. Compare the panel detail and [Lunitora UXP] console events with
   [Lunitora bridge] stderr. A constructor failure before a Python accepted-event
   identifies a failure before the WebSocket session was accepted; an onopen
   followed by Authentication rejected identifies the authentication stage.
   Preserve the sanitized error name/message/stack or close code/reason for review.
   Do not include the password input or pairing file in screenshots or copied output.

This retry does not change the endpoint, manifest permissions, protocol or token.
The diagnostics identify the failure stage; they do not assume its cause.

## Live-test child startup failures

The live-test launches the absolute .venv Python executable with the toolkit's
absolute working directory. Its monitored stdio transport gives the child a
stderr pipe, relays sanitized diagnostics through the parent's stderr, and
retains the last 32 sanitized lines in memory. It writes no raw stderr log file.
MCP negotiation and tool calls still use the SDK Client. Normal server startup
and the Photoshop bridge protocol are unchanged.

This fixes a reproduced Git Bash startup failure: the detached child inherited
an unusable console stderr handle, and its first bridge-listening diagnostic
raised OSError: [Errno 9] Bad file descriptor inside bridge.start(). Capturing
stderr allowed the same child to initialize normally. This was not a port
conflict or diagnostic output on stdout.

If startup fails, the live-test reports the executable, cwd, observed exit code
(or unavailable if spawning failed), whether cleanup had to terminate the child,
the port-occupancy snapshot taken before spawn, any observed non-MCP stdout,
and sanitized child stderr. Invalid stdout is identified without echoing it.
Long stderr lines are omitted; credentials and token-shaped strings are redacted
before display. All diagnostics go to stderr.

A preexisting listener on 127.0.0.1:43127 is reported but never stopped. The child
still initializes and discovers tools; a ping returns PORT_IN_USE. The occupancy
probe is a point-in-time observation, not proof that a port conflict caused an exit.

## References and remaining checks

- [Architecture source of truth](../../docs/LUNITORA_MCP_ARCHITECTURE_GUIDE.md)
- [MCP Python SDK 2.2.0](https://pypi.org/project/mcp/2.2.0/)
- [websockets 17.1](https://pypi.org/project/websockets/17.1/)
- [Adobe manifest v5](https://developer.adobe.com/photoshop/uxp/2022/guides/uxp-guide/uxp-misc/manifest-v5/)
- [Photoshop Document DOM](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/document/)
- [Photoshop Layer DOM](https://developer.adobe.com/photoshop/uxp/ps_reference/classes/layer/)
- [Photoshop resampling constants](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/modules/constants/)
- [Photoshop Imaging API](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/media/imaging)
- [PNG format and significant-bits metadata](https://www.w3.org/TR/png-3/#11sBIT)
- [Photoshop modal execution and automatic document cleanup](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/media/executeasmodal/)
- [UXP private temporary storage](https://developer.adobe.com/photoshop/uxp/2022/uxp/reference-js/Modules/uxp/Persistent%20File%20Storage/FileSystemProvider/)
- [UXP secureStorage](https://developer.adobe.com/photoshop/uxp/2022/uxp/reference-js/Modules/uxp/Key-Value%20Storage/SecureStorage/)
- [Adobe's 2026 Photoshop plugin compatibility notice](https://blog.developer.adobe.com/en/publish/2026/06/upcoming-photoshop-ui-changes-test-your-uxp-plugin-now)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

Photoshop's recent UI/backend changes are a reason to validate on the actual 27.10
host before enabling Codex. Mock tests do not prove UDT host discovery, panel
rendering, runtime network permission acceptance or actual DOM behavior.
Loading is user-verified; authenticated live pairing, a real-document call and
Codex activation are verified through the real integration as recorded above.
Automated checks additionally cover mock UXP events and fake WebSocket peers.
The historical Phase 1 record covers inspection only; it does not verify Phase 2A
processing or export. Game files and the existing Godot test suite are untouched.
