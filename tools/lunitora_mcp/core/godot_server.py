"""Run the separate read-only Godot MCP using the toolkit's locked environment."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import sys

from modules.godot.bridge import GodotBridge
from modules.godot.config import Config, ConfigurationError, Credential, PORT, ensure_credential
from modules.godot.protocol import BRIDGE_VERSION, BridgeError
from modules.godot.tools import GodotMCPServer, register_tools


def create_server(config: Config, credential: Credential | None, *,
                  startup_error: BridgeError | None = None, port: int = PORT) -> GodotMCPServer:
    bridge = GodotBridge(config, credential, startup_error=startup_error, port=port)

    @asynccontextmanager
    async def lifespan(_server):
        await bridge.start()
        try:
            yield
        finally:
            await bridge.stop()

    server = GodotMCPServer(
        "Lunitora Godot", version=BRIDGE_VERSION, lifespan=lifespan, log_level="WARNING",
        instructions="Exactly three strictly read-only Godot editor operations. Each takes exactly {}. "
                     "No node/resource/selection/playback/project-settings/save/undo modifications exist. "
                     "Tool discovery remains available when the editor or local bridge is unavailable.",
    )
    register_tools(server, bridge)
    return server


def main() -> int:
    # No endpoint, secret, auth-disable, filesystem or operation flags exist.
    if len(sys.argv) != 1:
        print("The Godot MCP entrypoint accepts no command-line options.", file=sys.stderr)
        return 2
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s: %(message)s")
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    credential = None
    startup_error = None
    try:
        try:
            credential = ensure_credential()
        except (ConfigurationError, OSError, ValueError):
            startup_error = BridgeError("LOCAL_AUTH_UNSAFE")
        create_server(Config(), credential, startup_error=startup_error).run(transport="stdio")
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        if credential is not None:
            credential.close()


if __name__ == "__main__":
    raise SystemExit(main())
