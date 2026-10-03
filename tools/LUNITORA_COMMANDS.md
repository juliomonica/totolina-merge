# Lunitora daily commands

Open **Git Bash** in your `totolina-merge` checkout.

Photoshop is required for the Art workflow. **UXP Developer Tool (UDT)** is
Adobe's developer utility for loading, developing and debugging the Lunitora UXP
Photoshop plugin. It is required for development loading and `git art-dev`, but
not for daily use of an already installed packaged plugin. Missing Photoshop or
UDT does not block unrelated Game workflows.

| Command | When to use it |
| --- | --- |
| `git art` | Daily art work: opens Photoshop and ChatGPT/Codex Desktop. |
| `git art-refresh` | Clean Codex/MCP restart: closes/reopens Desktop, waits for its MCP processes to exit, and checks the Photoshop bridge port. Keeps Photoshop open. |
| `git art-dev` | **Developer only:** opens UDT for plugin loading/development/packaging, plus Photoshop and Desktop. |
| `git dev` | Gameplay, Godot or other coding work: opens Desktop only. |
| `git dev-refresh` | Restarts Desktop only; leaves Photoshop and UXP Developer Tool alone. |
| `git godot` | Godot/MCP work: opens Desktop and the configured Godot editor on this checkout. |
| `git godot-refresh` | Restarts Desktop and recovers the Godot MCP listener on 43128. Keeps Godot open to protect unsaved editor work. |

Run refresh commands from an **external Git Bash window**, after active Desktop
work finishes. They close all windows of the configured Desktop application.
If recovery reports an unknown port owner, ask a developer; it will not kill it.

If both MCP/Python and UXP code changed, run **`git art-refresh` followed by
`git art-dev`**, then manually reload the development plugin in UXP Developer
Tool. Opening UDT does not reload code. For an installed packaged plugin,
repackage/reinstall the update as described in the technical guide.
No `git art-dev-refresh` command is needed.

`git godot` checks the expected checkout, verifies the configured Godot executable
and project arguments, and starts the editor with `--editor --path <repo-root>`
when that project is not already open. It does not open the Project Manager.
The visible editor launches asynchronously. New editor stdout and stderr go to
separate `godot-<GUID32>.stdout.log` and `godot-<GUID32>.stderr.log` files in
`%TEMP%\lunitora-godot-launcher\`, not the invoking Git Bash terminal. The launcher
reports both paths. Reusing an already running matching editor creates no logs.
Before a new launch, best-effort cleanup removes only this launcher's matching
top-level log files older than seven days; locked or unreadable files do not
prevent launch. No files outside that dedicated directory are cleaned.
Both Godot commands use the existing repository launcher and do not open
Photoshop or UXP Developer Tool, or touch Photoshop port 43127. Codex owns the
`lunitora_godot` stdio MCP process; the launcher never starts a Python MCP server.

`git godot-refresh` leaves Godot running and reconnecting while Desktop restarts.
It waits for the old Godot MCP process to exit and verifies port 43128 is free.
Automatic stale cleanup requires proof that the process is this checkout's exact
Lunitora Godot MCP server; an unknown PID is never killed. It never force-closes
Godot, because the editor may contain unsaved work.

Put your PNG in `source_art/_inbox/`, run `git art`, and ask:

- Remove the background from cat.png
- Resize cat.png to 384x384
- Remove the background and resize cat.png to 384x384

Results go to `source_art/_staging/` for review. Existing candidates are never
overwritten. For characters/fine detail, prefer **remove background → visually
review → copy the approved candidate back to `_inbox` → resize**.

**First time on this PC:** with Git and Python installed, run the repository-owned
bootstrap from the repository root. It detects external applications; it never
downloads or installs them. See the [machine setup guide](../docs/MACHINE_SETUP.md).

```bash
python tools/lunitora_setup.py
```

For a read-only readiness report:

```bash
python tools/lunitora_setup.py --check
```

Valid existing application selections are preserved. Setup prepares the local
MCP Python environment and all seven local aliases. Setup and daily aliases use
validated standalone host Python, with standard-library-only operator code;
only MCP server entries use `tools/lunitora_mcp/.venv`. A missing/broken venv
therefore cannot prevent the launcher from reporting an actionable setup error.
No Desktop launch occurs until the MCP environment is healthy.
Daily aliases never prompt for
configuration; if discovery cannot repair a path deterministically, they ask you
to rerun setup. Setup now prepares available MCP configuration and reviewed local
authentication without launching servers. Compatible existing entries and
credentials are preserved; project trust and first Photoshop pairing remain
explicit user actions. `--check` reports proposals without changing anything.
Windows Core/Game and Art Python workflows are live accepted. The obsolete
PowerShell launcher/setup implementation and its tests are removed in v0.10.
Use Python setup and the seven repository-local Git aliases; recovery uses
reviewed corrections or Git history. Legacy non-secret configuration import
remains available for older machines.

When dependencies need repair, setup may ask permission to stop only strictly
verified MCP processes belonging to this checkout. It never closes Godot or
Desktop for environment repair, and never stops unknown/ambiguous Python.
Decline or uncertain identity defers repair and reports configured Core/Game as
`PARTIAL`. Read-only `--check` never offers process shutdown or changes anything.

The **bridge token** is the one-time machine pairing/authentication credential
for the Lunitora Photoshop bridge. If missing/invalid in safe protected storage,
normal setup asks for it using a **hidden** prompt: paste an existing valid token
or press **Enter** to generate this machine's token. It never echoes the token
and stops pairing if secret input is unavailable. With a valid stored token,
setup reports **Photoshop bridge authentication: OK** and does not ask again;
this is local readiness, not proof of a live connection. The existing plugin
does not generate, display or copy a token. The private protected file is
`tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt`, not a Codex setting. Open it privately
in a local editor, copy it into Photoshop's **Plugins > Lunitora Photoshop Bridge**
panel's **Pairing token** password input, and choose **Connect / Reconnect**.
Do not copy it into chat, logs, screenshots, TOML, JSON or environment files.
Close the editor without changes and clear the clipboard after pasting.

Normally this is **one-time pairing per machine**. The panel confirms
**Connected · inspection and staging candidates** and, when Adobe secure storage
is available, **Pairing saved securely on this computer.** It reconnects
automatically; no preliminary ping is needed. A plugin installation/storage reset
may require pairing again. See the [exact setup/loading and troubleshooting
procedure](lunitora_mcp/README.md#first-photoshop-plugin-loading-and-pairing).
After packaged installation, **UDT is developer-only**.
Run setup again if an application update moves its executable.

For first-time pairing or reuse of a valid protected token, run:

```bash
python tools/lunitora_setup.py --pair-photoshop
```

An existing valid protected token is reused without a prompt or rotation.
Missing tokens use the hidden create/import prompt. Then, after Desktop
work finishes, run `git art-refresh` from external Git Bash and privately pair the
panel with the current protected token again. Unsafe storage fails closed.
`--check` never prompts or changes credentials and rejects `--pair-photoshop`.

For valid legacy credentials with unsafe ownership/DACLs, explicitly run:

```bash
python tools/lunitora_setup.py --repair-photoshop-auth
```

This separate command requests consent and preserves token bytes exactly. It
applies current-user ownership and protected current-user/SYSTEM full-access
DACLs only to `.local` and `pairing-token.txt`. It does not repair unrelated
children. If directory inheritance would change unrelated child ACLs, it stops
before mutation and reports that a separate reviewed migration is required.
Normal setup never performs this repair. `--check` cannot be combined with repair.

If Photoshop starts before Codex Desktop/MCP, several failed localhost connection
attempts during startup are expected. The paired plugin connects automatically
once the Codex-owned MCP listener appears; no manual reconnect is needed for this
startup sequence.

**Live verified on 2026-09-30:** the original five art/dev commands, packaged `.ccx`
installation, Photoshop and packaged-plugin startup without UXP Developer Tool,
one-time pairing, secure token reuse after restart, automatic reconnect to a late
MCP listener, and direct Photoshop processing without a preliminary ping.

**VERIFIED — user-reported live validation on 2026-09-30:** `git godot` opened
Codex and the correct Totolina Merge project without Photoshop or UXP Developer
Tool. `git godot-refresh` restarted Codex/MCP, preserved the running Godot editor
and unsaved scene state, and the Godot MCP reconnected successfully.
This is historical v0.7 evidence, not acceptance of the v0.8 terminal change.

**Windows Core/Game: LIVE ACCEPTED, 2026-10-02.** The host-Python migration,
clean Git Bash terminal behavior, matching-editor reuse and `git godot-refresh`
editor/unsaved-work preservation with MCP reconnect are accepted. One configured
`lunitora_godot` read-only `godot_ping({})` succeeded with `ok=true`,
`connected=true`, Godot `4.7.2-stable (official)`, bridge/plugin `0.5.0`, protocol
`1`, project `Totolina Merge`, round trip `34.456 ms`, and no error.

**REQUIRES ART MACHINE:** current Art launch/refresh/developer-loading parity and
private Photoshop pairing/processing await the Photoshop machine. Missing
Photoshop/UDT on the Game machine did not block Windows Core/Game. **REQUIRES
MAC:** macOS native launcher/authentication behavior. Android executable export
and **REQUIRES ANDROID DEVICE** validation remain separate. Fresh-machine network
installation and actual lingering-MCP recovery are **NOT EXECUTED**.
See the [milestone acceptance record](../docs/MACHINE_SETUP.md#v08-milestone-acceptance).


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
