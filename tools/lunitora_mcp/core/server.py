"""Run with .venv/Scripts/python.exe -m core.server from the toolkit directory."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters
from mcp.server import MCPServer

from core.config import Config, ConfigurationError, ROOT, load_config, load_token, setup_token
from core.live_test_child import LiveTestChild
from modules.photoshop.bridge import PhotoshopBridge
from modules.photoshop.protocol import BRIDGE_VERSION, BridgeError, OPERATIONS, envelope
from modules.photoshop.tools import register_tools


def create_server(config: Config, token: str | None, *, diagnostics: bool = False) -> MCPServer:
    bridge = PhotoshopBridge(config, token, diagnostics=diagnostics)

    @asynccontextmanager
    async def lifespan(_server):
        await bridge.start()
        try:
            yield
        finally:
            await bridge.stop()

    server = MCPServer(
        "Lunitora Photoshop", version=BRIDGE_VERSION, lifespan=lifespan, log_level="WARNING",
        instructions="Photoshop inspection plus one explicit inbox-to-staging PNG candidate operation. "
                     "Never replace production assets. Candidates require human approval. "
                     "A disconnected host returns a bounded error; it does not disable tool discovery.",
    )
    register_tools(server, bridge)
    return server


async def live_test(config_path: Path | None, wait_seconds: float) -> int:
    """Act as the MCP client; own/close one actual stdio server subprocess."""
    args = ["-B", "-m", "core.server"]
    if config_path:
        args += ["--config", str(config_path.resolve())]
    parameters = StdioServerParameters(command=str(Path(sys.executable).resolve()), args=args,
                                      cwd=str(ROOT.resolve()),
                                      env={"LUNITORA_LIVE_TEST_DIAGNOSTICS": "1"})
    child = LiveTestChild(parameters)
    try:
        return await _run_live_test(child, wait_seconds)
    except Exception as error:
        child.report_failure(error, phase=child.phase)
        return 1


async def _run_live_test(child: LiveTestChild, wait_seconds: float) -> int:
    print("Starting the real MCP process and loopback bridge.", file=sys.stderr, flush=True)
    async with Client(child, read_timeout_seconds=35) as client:
        child.phase = "tool discovery"
        tools = await client.list_tools()
        if {tool.name for tool in tools.tools} != OPERATIONS:
            raise RuntimeError("Unexpected MCP tool registration.")
        child.phase = "live test"
        print(f"Waiting for Photoshop for up to {wait_seconds:g} seconds. "
              "Load/pair the UXP panel and select Connect / Reconnect.",
              file=sys.stderr, flush=True)
        try:
            # One deadline covers retries, sleeps and an in-flight ping.
            async with asyncio.timeout(wait_seconds):
                while True:
                    reply = await client.call_tool("photoshop_ping", {})
                    data = reply.structured_content
                    if not reply.is_error:
                        break
                    error = data.get("error") if isinstance(data, dict) else None
                    if not isinstance(error, dict) or error.get("code") not in {"DISCONNECTED", "TIMEOUT"}:
                        print(json.dumps({"photoshop_ping": data}, ensure_ascii=False, indent=2),
                              file=sys.stderr)
                        return 1
                    await asyncio.sleep(0.3)
        except TimeoutError:
            print(f"Timed out after {wait_seconds:g} seconds waiting for a fresh authenticated Photoshop ping.",
                  file=sys.stderr, flush=True)
            print(json.dumps({"photoshop_ping": envelope(error=BridgeError("TIMEOUT"))}, indent=2),
                  file=sys.stderr)
            return 1
        print(json.dumps({"photoshop_ping": data}, ensure_ascii=False, indent=2), file=sys.stderr)
        reply = await client.call_tool("photoshop_get_active_document", {})
        print(json.dumps({"photoshop_get_active_document": reply.structured_content},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 1 if reply.is_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lunitora read-only Photoshop MCP")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--setup", action="store_true", help="Create ignored local pairing token once.")
    mode.add_argument("--live-test", action="store_true", help="Start a real stdio MCP child and call both tools.")
    parser.add_argument("--config", type=Path, help="Optional TOML containing timeout settings only.")
    parser.add_argument("--wait-seconds", type=float, default=120, help="Live-test connection wait (1–300).")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s: %(message)s")
    # Never enable wire-level logging: auth frames contain the local token.
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    try:
        if args.setup:
            path = setup_token()
            print(f"Local pairing file ready: {path}. Token contents are not logged.", file=sys.stderr)
            return 0
        config = load_config(args.config)
        token = load_token()
        if args.live_test:
            if not 1 <= args.wait_seconds <= 300:
                raise ConfigurationError("Live-test wait must be between 1 and 300 seconds.")
            if token is None:
                raise ConfigurationError("Run --setup before pairing.")
            return asyncio.run(live_test(args.config, args.wait_seconds))
        # Only the live-test parent enables diagnostics in its own child environment.
        diagnostics = os.environ.get("LUNITORA_LIVE_TEST_DIAGNOSTICS") == "1"
        create_server(config, token, diagnostics=diagnostics).run(transport="stdio")
        return 0
    except (ConfigurationError, OSError, ValueError):
        # Do not echo config contents, peer payloads, or exception objects.
        print("Local configuration error. Check timeout settings and the ignored pairing file; see README.",
              file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
