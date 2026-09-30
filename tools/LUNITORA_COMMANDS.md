# Lunitora daily commands

Open **Git Bash** in your `totolina-merge` checkout.

| Command | When to use it |
| --- | --- |
| `git art` | Daily art work: opens Photoshop and ChatGPT/Codex Desktop. |
| `git art-refresh` | Clean Codex/MCP restart: closes/reopens Desktop, waits for its MCP processes to exit, and checks the Photoshop bridge port. Keeps Photoshop open. |
| `git art-dev` | **Developer only:** opens UXP Developer Tool for plugin development/packaging, plus Photoshop and Desktop. |
| `git dev` | Gameplay, Godot or other coding work: opens Desktop only. |
| `git dev-refresh` | Restarts Desktop only; leaves Photoshop and UXP Developer Tool alone. |

Run refresh commands from an **external Git Bash window**, after active Desktop
work finishes. They close all windows of the configured Desktop application.
If recovery reports an unknown port owner, ask a developer; it will not kill it.

If both MCP/Python and UXP code changed, run **`git art-refresh` followed by
`git art-dev`**, then manually reload the development plugin in UXP Developer
Tool. Opening UDT does not reload code. For an installed packaged plugin,
repackage/reinstall the update as described in the technical guide.
No `git art-dev-refresh` command is needed.

Future `git godot` / `git godot-refresh` commands will be added only when the
Lunitora Godot MCP actually exists. They are not available yet; `git dev` opens
Desktop only and does not launch Godot.

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

Pair the installed Photoshop plugin once with this PC's local token. It saves
the token securely and reconnects automatically; no preliminary ping is needed.
Re-pair after an installation/storage reset if requested. Never paste the token
into chat. After packaged installation, **UXP Developer Tool is developer-only**.
Run setup again if an application update moves its executable.

If Photoshop starts before Codex Desktop/MCP, several failed localhost connection
attempts during startup are expected. The paired plugin connects automatically
once the Codex-owned MCP listener appears; no manual reconnect is needed for this
startup sequence.

**Live verified on 2026-09-30:** all five commands above, packaged `.ccx`
installation, Photoshop and packaged-plugin startup without UXP Developer Tool,
one-time pairing, secure token reuse after restart, automatic reconnect to a late
MCP listener, and direct Photoshop processing without a preliminary ping.
