"""First-time Art guidance only; no application launch or credential reads."""
from pathlib import Path

UDT_DESCRIPTION = "UXP Developer Tool (UDT) is Adobe's utility for loading, developing, debugging and packaging UXP plugins."
MANIFEST = Path('tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json')


def first_time_steps(root, credential):
    return (
        'Install/open Adobe Creative Cloud Desktop and sign in with your Adobe ID.',
        'Install supported Adobe Photoshop (repository manifest minimum 27.10.0; validated host 27.10) through Creative Cloud. Photoshop runs Art; Lunitora never silently installs it. Core/Game do not require Photoshop.',
        'In Creative Cloud, All apps, search for UXP Developer Tools and choose Install. ' + UDT_DESCRIPTION + ' UDT is needed for development loading and git art-dev; daily use of an installed packaged plugin does not require UDT. Core/Game do not require UDT.',
        "Launch UDT and enable Developer Mode when prompted. Adobe currently requires administrator privileges for UDT and elevated permission to enable Developer Mode. Approve Adobe's prompt yourself; Lunitora does not elevate Adobe applications.",
        'Launch Photoshop. For development loading, enable Edit > Preferences > Plugins > Enable Developer Mode if needed; protect unsaved work before any requested restart.',
        'With Photoshop running, in UDT choose Add Plugin, select ' + str(root / MANIFEST) + ', select the Photoshop host, then Load. Require successful loading.',
        'In Photoshop open Plugins > Lunitora Photoshop Bridge.',
        'From the repository root run python tools/lunitora_setup.py. Local credential setup is separate from Photoshop-panel pairing. Follow the reported command: --migrate-photoshop-auth for valid legacy mixed-directory storage, --repair-photoshop-auth for repairable protection, or --pair-photoshop for first-time private create/import or valid-token reuse. Run each command separately.',
        'The protected Lunitora bridge credential is normally configured once per machine (one-time pairing per machine). Existing valid protected credentials are preserved; no rotation is needed for this workflow.',
        'Privately open ' + str(credential) + ' in a local editor after setup; do not print it. The file is normally tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt. If setup confirms an existing reviewed protected legacy credential is in use, privately open ' + str(root / 'tools/lunitora_mcp/.local/pairing-token.txt') + ' instead; do not create a second token.',
        "Manually enter the SAME bridge password/token once into the Photoshop panel's password input, currently labelled Pairing token. The panel only accepts a token; it does not generate or reveal one. Close the editor without changes and clear the clipboard. Never paste the credential into chat, logs, screenshots, tracked JSON/TOML/configuration or environment files.",
        'Choose Connect / Reconnect in the panel. A listener may not be available until the next step; startup retry/disconnected status is not proof of bad pairing.',
        'After active Codex Desktop work finishes, run git art-refresh from external Git Bash. Review project trust/reload explicitly if requested. This restarts Desktop/MCP; Photoshop stays open. Require panel Connected; reconnect if needed. Require Pairing saved securely on this computer when Adobe secure storage is available.',
        'From Codex through the configured Photoshop MCP run one read-only photoshop_ping({}). Require ok=true, connected=true and the expected Photoshop host/version. Setup/check do not run this operation.',
        'Confirm Art readiness only after applications, development loading (or packaged installation), protected local credential, panel pairing and live MCP verification are accepted independently. Installation or local credential success alone is not full Art readiness.',
    )


def emit_first_time(root, credential, emit=print):
    emit('First-Time Photoshop / Art Machine Setup (Windows): ' + UDT_DESCRIPTION)
    for number, step in enumerate(first_time_steps(root, credential), 1):
        emit(str(number) + '. ' + step)
