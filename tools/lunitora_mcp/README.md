# Lunitora Photoshop MCP — Phase 1A

Repository-controlled foundation for exactly two read-only tools:
photoshop_ping and photoshop_get_active_document.

Architecture: [Lunitora MCP guide](../../docs/LUNITORA_MCP_ARCHITECTURE_GUIDE.md).
Bridge/plugin version: 0.1.0. Bridge protocol version: 1.
The plugin targets Photoshop 27.10+ with UXP manifest v5 and Photoshop API v2.
The audited installation is Photoshop 2026 27.10.0.26 on Windows x64.
UDT loading, authenticated live Photoshop connectivity and Codex MCP activation
are verified on this workstation. Both read-only tools succeeded through the real
Codex MCP integration on 2026-09-29 with the restricted localhost configuration
below.

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
Each authenticated session carries only the two allowlisted operations. A valid
reconnect replaces the old session and fails its pending calls; an invalid token
cannot replace a paired session. Panel reconnect detaches previous callbacks,
cancels the authentication timer and ignores stale callbacks.

This is a local bearer-token trust boundary: it prevents unauthenticated use and
LAN access. Plain loopback WebSocket transport is not protection against a
malicious process already able to read this user's files or memory. No firewall,
antivirus or Windows ACL settings are changed.

| Bound | Value |
| --- | --- |
| WebSocket JSON message | 262,144 UTF-8 bytes |
| Authentication message | 1,024 UTF-8 bytes |
| Python authentication / request timeout | 5 seconds each; configurable 0.05–30 |
| Plugin connect/authentication timeout | 10 seconds |
| Accepted open WebSockets / authenticated session | 4 / 1 |
| Pending requests | 16 |
| Recursive layer count / nesting depth | 2,000 / 64 |

No partial document result is returned when an inspection limit is exceeded.
No file paths or document contents are returned. Document/layer names are returned
and therefore appear in the manual test's output.

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

No filesystem, clipboard, process launching, WebView or user-information permission
is requested. Local token caching uses UXP secureStorage. Photoshop data access uses
DOM getters only: no batchPlay, executeAsModal, selection changes, history entries,
save, export or document-editing operations.

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

Requests contain exactly type, protocol_version, id and operation.
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
operations are rejected. Allowed operations are exactly the two public tool names.

## MCP schemas

Both tools accept an empty arguments object, {}. Both advertise readOnlyHint=true,
destructiveHint=false, idempotentHint=true and openWorldHint=false.
The SDK publishes their JSON input/output schemas through tools/list from the
TypedDict definitions in modules/photoshop/protocol.py.

Both return structuredContent using this envelope (and a matching JSON text block):

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
both tools when unpaired, disconnected or unable to bind the fixed port.

## Automated validation without Photoshop

Run from the toolkit directory with no other bridge occupying port 43127:

~~~bash
./.venv/Scripts/python.exe -m compileall -q core modules tests
./.venv/Scripts/python.exe -B -m unittest -v tests.test_phase1
./.venv/Scripts/python.exe -m pip check
'/c/Program Files/nodejs/node.exe' --check bridges/photoshop_uxp/index.js
'/c/Program Files/nodejs/node.exe' tests/test_plugin.js
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

The JavaScript suite runs the actual plugin getter code against read-only mocks
that throw on writes. This verifies response shape, ordering, Unicode, bounds,
safe errors and version checks without interacting with Photoshop.

Loopback tests must run in a normal Windows user context. The audit found the
Codex offline sandbox blocks loopback; no firewall workaround is implemented.
Run only one test suite/bridge at a time. Tests never stop another process.

## Validation record — 2026-09-29

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
the exact two-tool list and prints that it is waiting for Photoshop. It retries
DISCONNECTED or transient TIMEOUT results every 300 ms until --wait-seconds
expires. The deadline also bounds an in-flight ping. Expiry reports a clear
TIMEOUT failure; other errors, including authentication/protocol errors returned
by the tool, fail immediately. A successful fresh ping ends the wait and triggers
one active-document call. The child process and bridge close on success or failure.
Do not start a second server alongside it.

7. While the driver waits, select Connect / Reconnect in the Photoshop panel.
   Confirm Connected · read-only. If authentication fails, check the local token.
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
- [UXP secureStorage](https://developer.adobe.com/photoshop/uxp/2022/uxp/reference-js/Modules/uxp/Key-Value%20Storage/SecureStorage/)
- [Adobe's 2026 Photoshop plugin compatibility notice](https://blog.developer.adobe.com/en/publish/2026/06/upcoming-photoshop-ui-changes-test-your-uxp-plugin-now)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

Photoshop's recent UI/backend changes are a reason to validate on the actual 27.10
host before enabling Codex. Mock tests do not prove UDT host discovery, panel
rendering, runtime network permission acceptance or actual DOM behavior.
Loading is user-verified; authenticated live pairing, a real-document call and
Codex activation are verified through the real integration as recorded above.
Automated checks additionally cover mock UXP events and fake WebSocket peers.
Image processing, filesystem access from Photoshop, editing and export remain
outside Phase 1A. Game files and the existing Godot test suite are untouched.
