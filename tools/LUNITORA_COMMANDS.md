# Lunitora daily commands

Open **Git Bash** in your `totolina-merge` checkout.

| Command | When to use it |
| --- | --- |
| `git art` | Daily art work: opens Photoshop and ChatGPT/Codex Desktop. |
| `git art-refresh` | Clean Codex/MCP restart: closes/reopens Desktop, waits for its MCP processes to exit, and checks the Photoshop bridge port. Keeps Photoshop open. |
| `git art-dev` | **Developer only:** opens UXP Developer Tool for plugin development/packaging, plus Photoshop and Desktop. |
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

**First time on this PC:** have a developer follow the
[MCP setup and packaged installation guide](lunitora_mcp/README.md#operator-convenience-v06).
Install the aliases from the repository root:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/setup.ps1
```

For Godot, save its installed executable in the ignored local launcher config:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./tools/operator_launcher/setup.ps1 \
  -GodotExe 'C:\path\to\Godot_v4.7.2-stable_win64.exe'
```

Existing Photoshop/UDT settings are preserved. Setup installs all seven aliases.
Use any command with `-Check` to validate its configuration without starting or
stopping applications.

Pair the installed Photoshop plugin once with this PC's local token. It saves
the token securely and reconnects automatically; no preliminary ping is needed.
Re-pair after an installation/storage reset if requested. Never paste the token
into chat. After packaged installation, **UXP Developer Tool is developer-only**.
Run setup again if an application update moves its executable.

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
