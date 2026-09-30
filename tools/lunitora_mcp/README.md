# Lunitora Photoshop MCP — Phase 2A staging slice

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

## New Windows Workstation Setup

Follow this sequence on each new PC. Replace placeholders before running commands.
Shell examples use **Git Bash**: `<repo-path-bash>` is the checkout's absolute
Bash path, such as `/d/Development/totolina-merge`. In TOML, `<repo-path>` is the
same checkout's Windows path, such as `D:\Development\totolina-merge`.
Each machine uses its own paths.

1. **Install prerequisites.** Use Windows x64, the platform of the dependency
   lock and verified installation. Install **Photoshop 27.10.0 or newer**
   (manifest minimum; live verification used 27.10), **Adobe UXP Developer Tool**
   able to load a Photoshop manifest-v5/API-v2 plugin, standalone **Python 3.12.x
   x64** (`==3.12.*` in the project; verified with 3.12.10), **Git for Windows
   with Git Bash**, and **Codex Desktop for Windows**, signed in and able to run
   local stdio MCP servers. The project pins no Git, UXP Developer Tool, or Codex
   Desktop version. Node is only needed for optional JavaScript mock tests.

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

6. **Load the UXP plugin.** Open Photoshop and enable Developer Mode, restarting
   Photoshop if requested after saving your work. In Adobe UXP Developer Tool,
   choose **Add Plugin**, select
   `<repo-path>\tools\lunitora_mcp\bridges\photoshop_uxp\manifest.json`, select the
   Photoshop host, and choose **Load**. Open Photoshop's
   **Plugins > Lunitora Photoshop Bridge** panel. Keep the checked-in permission
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
   enabled_tools = ['photoshop_ping', 'photoshop_get_active_document']
   ~~~

   This user-local configuration stays outside the repository. Do not put the
   pairing token in it or use Bash `/c/` or `/d/` paths for `command`/`cwd`.
   See the [Codex MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp).

8. **Fully restart Codex Desktop and open a new Codex chat** in this repository
   to load the configuration. Let Codex own the server; do not also run
   `core.server` or `--live-test` manually alongside it.

9. **Start the bridge from Codex.** Ask the new chat: `Use photoshop_ping.`
   This lets Codex start/use the configured MCP process. An initial
   `DISCONNECTED` response is expected before the Photoshop panel is paired.

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

12. **Troubleshoot.** For `PORT_IN_USE`, stop an old manual bridge with Ctrl+C
    or fully quit an older Codex instance first. There is no alternate-port
    fallback. Identify the listener:

    ~~~bash
    netstat.exe -ano -p tcp | findstr.exe ':43127'
    ~~~

    Use the **LISTENING** row's PID and confirm in Task Manager's Details/
    Command line that it belongs to a stale Lunitora bridge. If that confirmed
    process cannot be closed normally, replace `<pid>` with its numeric PID:

    ~~~bash
    MSYS_NO_PATHCONV=1 taskkill.exe /PID '<pid>' /F
    ~~~

    Git Bash can convert `/PID` into `C:/Program Files/Git/PID`. The command-local
    `MSYS_NO_PATHCONV=1` prevents that conversion without changing global shell
    settings; see [Git for Windows' path-conversion notes](https://github.com/git-for-windows/build-extra/blob/main/ReleaseNotes.md#known-issues).
    Do not terminate unrelated Python or Photoshop processes. After freeing the
    port, restart Codex Desktop, open a new chat, and repeat steps 9–11; an
    already-started server with a bind error must be restarted.

    For `DISCONNECTED`, keep Photoshop open, confirm the plugin is loaded,
    call `photoshop_ping` to start the bridge, then click **Connect / Reconnect**
    with this machine's token. Re-enter the local token if pairing is rejected.
    Reload the plugin in UDT after plugin/manifest updates. If tools are missing,
    check the user config's absolute executable and working-directory paths,
    then repeat step 8. Keep the localhost permission and fixed endpoint; use
    the sanitized diagnostics described below for further investigation.

## Phase 2A — one inbox image to one staging candidate

This is an opt-in Windows-only processing slice. The two Phase 1 tools keep their
existing arguments, read-only annotations and response envelopes. A new tool and
bridge operation, **photoshop_process_image**, opens a private temporary copy in
Photoshop and exports a candidate. It never opens the source file in Photoshop,
deletes or saves over that source, or writes into runtime assets/.
Human review and approval remain mandatory; this tool cannot promote candidates.
Follow [ART_GUIDE.md](../../source_art/ART_GUIDE.md) for staging review.

1. Put one user-selected **non-interlaced, 8-bit RGBA PNG with transparency**
   in source_art/_inbox/. Input and exported PNG must each be at most **24 MiB
   (25,165,824 bytes, inclusive)**. Canvases remain limited to 1..2048 px per axis;
   the requested canvas must be at least as large as the source in both axes.
   JPEG, indexed/RGB PNG, 16-bit PNG, APNG and PSD are outside this slice.
2. Reload the plugin in UXP Developer Tool. In this user's local Codex config,
   opt into the new tool by replacing only the existing enabled_tools line:

   ~~~toml
   enabled_tools = ['photoshop_ping', 'photoshop_get_active_document', 'photoshop_process_image']
   ~~~

   Keep the existing command/cwd, token, endpoint and permissions. Fully restart
   Codex Desktop, open a new chat, call photoshop_ping, then pair/reconnect the
   Photoshop panel. The setup examples above deliberately enable inspection only.
3. Ask Codex to process the selected source into a **new** staging filename,
   providing integer canvas dimensions. Example arguments (replace the filenames
   and choose a canvas at least as large as the source):

   ~~~json
   {
     "source_relative_path": "source_art/_inbox/selected.png",
     "staging_relative_path": "source_art/_staging/selected-candidate.png",
     "width_px": 384,
     "height_px": 384,
     "remove_background": false
   }
   ~~~

4. Require ok=true, inspect the result and visually review the actual staging PNG
   for alpha edges, proportions, placement, padding and color. A staging file is
   **not an approved production asset**. This phase performs no runtime replacement.
   Existing files fail with DESTINATION_EXISTS; choose another name explicitly.

Width and height must each be **1–2048 pixels** and no smaller than the source.
Only centered canvas expansion (or the same canvas size) is supported: no
resampling, stretching, cropping, flattening or automatic transparent trim.
Artwork scale and existing padding remain intact. Python checks source alpha
at the centered offset (any odd extra pixel goes to the right/bottom) and requires
all added padding to be transparent. Smaller canvases return CANVAS_TOO_SMALL.
An opaque imported Photoshop background layer is rejected.

Background removal is **not enabled**: a reliable offline implementation has
not been established for this slice. remove_background defaults to false;
true returns BACKGROUND_REMOVAL_UNAVAILABLE without publishing a candidate.
There is no cloud/API fallback or silent success when removal was requested.

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

The new tool advertises readOnlyHint=false, destructiveHint=false,
idempotentHint=false and openWorldHint=false. Its success result is:

~~~text
{
  source_relative_path, staging_relative_path,
  width_px, height_px,
  background_removal_requested: false,
  background_removal_completed: false,
  validation: {
    format: "PNG", bit_depth: 8, color_type: "RGBA",
    has_transparency: true, dimensions_verified: true,
    source_alpha_preserved: true, padding_verified: true,
    source_unchanged: true, bytes_written, sha256,
    human_approval_required: true
  }
}
~~~

Failures use the existing structured error envelope (ok=false, result=null,
isError=true). Processing errors include INVALID_PATH, PATH_UNSAFE,
UNSUPPORTED_PLATFORM, SOURCE_NOT_FOUND, DESTINATION_EXISTS, INVALID_DIMENSIONS,
CANVAS_TOO_SMALL, IMAGE_TOO_LARGE, INVALID_IMAGE, BACKGROUND_REMOVAL_UNAVAILABLE,
PHOTOSHOP_PROCESSING_FAILED, OUTPUT_VALIDATION_FAILED and STAGING_WRITE_FAILED.
DISCONNECTED, PORT_IN_USE, TIMEOUT and BUSY retain their transport meanings.
Only one processing call runs at a time. A timeout/disconnect cannot publish a
late reply; Photoshop may still finish cleaning up its private temporary copy.

**Live Phase 2A processing through Codex is verified on 2026-09-29.** A real
256 x 256 RGBA PNG from source_art/_inbox/phase2a_test.png produced the new
512 x 512 source_art/_staging/phase2a_test_512.png candidate. The tool reported
successful transparency, padding and source preservation, without background
removal. An identical second request returned DESTINATION_EXISTS without overwrite.
The final validation record below distinguishes this live result from mock tests.

Still verify same-size and odd canvas dimensions, restoration of an existing
unsaved document, cancellation and temporary-file cleanup on the actual host.
Alpha edges and profile/color-management behavior require visual review; alpha
validation does not promise identical RGB values. Near-limit runtime/memory also
needs a live test. Background removal and smaller-canvas resizing, batching and
production promotion are not implemented.

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
cd /d/Development/LunitoraGames/totolina-merge/tools/lunitora_mcp
'/c/Users/lunam/AppData/Local/Programs/Python/Python312/python.exe' -m venv .venv
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
| Phase 2A processing request timeout | 30 seconds; one processing call at a time |
| Phase 2A input / output PNG | 24 MiB (25,165,824 bytes) each; canvas 1–2048 pixels per dimension |
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
inspection operations use DOM getters only. Phase 2A uses UXP's default private
temporary storage and executeAsModal to open a copy, resize its canvas and export
PNG. It closes that copy without saving and restores the previous active document;
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
height_px and remove_background. The reply contains png_base64, width_px, height_px,
background_removal_requested and background_removal_completed. The byte fields
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
bytes: 561 metadata bytes for a request and 627 for a successful response, leaving
463 and 397 bytes of headroom respectively. At the PNG limit those envelopes total
33,554,993 and 33,555,059 bytes. Limits count UTF-8 bytes, not JavaScript character count. WebSocket framing
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

Run from the toolkit directory with no other bridge occupying port 43127:

~~~bash
./.venv/Scripts/python.exe -m compileall -q core modules tests
./.venv/Scripts/python.exe -B -m unittest -v tests.test_phase1 tests.test_phase2
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

## Manual UDT loading and pre-Codex live test procedure

1. Keep Photoshop 2026 27.10 open. Confirm Developer Mode is enabled.
   If Photoshop requires a restart, handle any unsaved work yourself first.
2. In Adobe UXP Developer Tool, choose Add Plugin and select:
   D:\Development\LunitoraGames\totolina-merge\tools\lunitora_mcp\bridges\photoshop_uxp\manifest.json
3. Select the Photoshop 27.10 host and Load the added plugin.
4. In Photoshop, open Plugins > Lunitora Photoshop Bridge. Confirm the panel
   shows Bridge 0.1.0, the Photoshop version and its disconnected status.
5. Open a normal Git Bash terminal and prepare the local pairing value:

~~~bash
cd /d/Development/LunitoraGames/totolina-merge/tools/lunitora_mcp
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
command = 'D:\Development\LunitoraGames\totolina-merge\tools\lunitora_mcp\.venv\Scripts\python.exe'
args = ['-B', '-m', 'core.server']
cwd = 'D:\Development\LunitoraGames\totolina-merge\tools\lunitora_mcp'
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
cd /d/Development/LunitoraGames/totolina-merge/tools/lunitora_mcp
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
