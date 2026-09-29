"""Monitored stdio transport for the manual live-test only.

The child receives pipes, never the Git Bash console's stderr handle. The SDK
Client still negotiates and validates MCP; this adapter exposes the process
status and sanitizes stderr before relaying it to the parent terminal.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
import errno
import re
import socket
import subprocess
import sys

import anyio
from anyio.abc import ObjectReceiveStream, ObjectSendStream
from mcp import StdioServerParameters, types
from mcp.client.stdio import get_default_environment
from mcp.os.win32.utilities import create_windows_process, close_process_job, terminate_windows_process_tree
from mcp.shared.message import SessionMessage

from core.config import HOST, PORT


def sanitize_diagnostic(text: str) -> str:
    """Redact before truncating, including token-shaped values in tracebacks."""
    if re.search(r"(token|password|secret|authorization)[\"'\\\s]*[:=]", text, re.I):
        return "[sensitive diagnostic line redacted]"
    text = re.sub(r"[A-Za-z0-9_-]{64,}", "[redacted]", text)
    return re.sub(r"[\x00-\x1f\x7f]", " ", text)[:2048]


def port_occupancy() -> str:
    """Snapshot availability without connecting to or stopping another listener."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((HOST, PORT))
        return "no"
    except OSError as error:
        if error.errno == errno.EADDRINUSE or getattr(error, "winerror", None) == 10048:
            return "yes"
        return "unknown (port probe unavailable)"


class _Reader(ObjectReceiveStream):
    def __init__(self, owner):
        self.owner = owner
        self.buffer = b""

    async def receive(self):
        while b"\n" not in self.buffer:
            self.buffer += await self.owner.process.stdout.receive()
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            message = types.jsonrpc_message_adapter.validate_json(line, by_name=False)
        except ValueError:
            self.owner.invalid_stdout = True
            # Never expose an invalid raw line through a validation exception.
            return ValueError("Child stdout contained non-MCP data (contents withheld).")
        return SessionMessage(message)

    async def aclose(self):
        # Session tasks are cancelled by Client; the transport owns pipe cleanup.
        pass


class _Writer(ObjectSendStream):
    def __init__(self, owner):
        self.owner = owner

    async def send(self, message):
        data = message.message.model_dump_json(by_alias=True, exclude_unset=True)
        await self.owner.process.stdin.send((data + "\n").encode("utf-8"))

    async def aclose(self):
        pass


class LiveTestChild:
    def __init__(self, parameters: StdioServerParameters):
        self.parameters = parameters
        self.phase = "initialization"
        self.port_was_occupied = port_occupancy()
        self.process = None
        self.stderr_task = None
        self.stderr_tail = deque(maxlen=32)
        self.invalid_stdout = False
        self.forced_stop = False

    async def __aenter__(self):
        kwargs = dict(command=self.parameters.command, args=self.parameters.args,
                      env=get_default_environment() | (self.parameters.env or {}),
                      cwd=self.parameters.cwd)
        if sys.platform == "win32":
            # Preserve the SDK's Windows job-object/process-tree cleanup.
            self.process = await create_windows_process(**kwargs, errlog=subprocess.PIPE)
        else:
            command = kwargs.pop("command")
            args = kwargs.pop("args")
            self.process = await anyio.open_process([command, *args], stderr=subprocess.PIPE, **kwargs)
        self.stderr_task = asyncio.create_task(self._drain_stderr())
        return _Reader(self), _Writer(self)

    def _stderr_line(self, raw: bytes):
        line = sanitize_diagnostic(raw.decode("utf-8", errors="replace"))
        self.stderr_tail.append(line)
        print(line, file=sys.stderr, flush=True)

    async def _drain_stderr(self):
        pending = b""
        discarding = False
        try:
            while True:
                chunk = await self.process.stderr.receive()
                for index, piece in enumerate(chunk.split(b"\n")):
                    if index:
                        if not discarding:
                            self._stderr_line(pending)
                        pending, discarding = b"", False
                    if not discarding:
                        pending += piece
                        if len(pending) > 65536:
                            self._stderr_line(b"[overlong child stderr line omitted]")
                            pending, discarding = b"", True
        except (anyio.EndOfStream, anyio.ClosedResourceError, anyio.BrokenResourceError):
            if pending and not discarding:
                self._stderr_line(pending)

    async def __aexit__(self, *_):
        # Match the SDK's bounded graceful exit before terminating this child.
        with anyio.CancelScope(shield=True):
            with suppress(OSError, anyio.ClosedResourceError, anyio.BrokenResourceError):
                await self.process.stdin.aclose()
            with anyio.move_on_after(2):
                await self.process.wait()
            if self.process.returncode is None:
                self.forced_stop = True
                if sys.platform == "win32":
                    await terminate_windows_process_tree(self.process)
                else:
                    self.process.kill()
                with anyio.move_on_after(2):
                    await self.process.wait()
            if sys.platform == "win32":
                close_process_job(self.process)
            with anyio.move_on_after(1):
                await self.stderr_task
            if not self.stderr_task.done():
                self.stderr_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.stderr_task
            for stream in (self.process.stdout, self.process.stderr):
                with suppress(OSError, anyio.ClosedResourceError, anyio.BrokenResourceError):
                    await stream.aclose()

    def report_failure(self, error: Exception, *, phase: str):
        def leaves(exception):
            if isinstance(exception, BaseExceptionGroup):
                for nested in exception.exceptions:
                    yield from leaves(nested)
            else:
                yield sanitize_diagnostic(f"{type(exception).__name__}: {exception}")

        exit_code = self.process.returncode if self.process is not None else None
        print(f"Live-test MCP child failed during {phase}.", file=sys.stderr)
        print("Child executable: " + sanitize_diagnostic(self.parameters.command), file=sys.stderr)
        print("Child cwd: " + sanitize_diagnostic(str(self.parameters.cwd)), file=sys.stderr)
        print(f"Child exit code: {exit_code if exit_code is not None else 'unavailable'}", file=sys.stderr)
        print(f"Child terminated by wrapper: {'yes' if self.forced_stop else 'no'}", file=sys.stderr)
        print(f"Port {HOST}:{PORT} already occupied before spawn: {self.port_was_occupied}", file=sys.stderr)
        print(f"Non-MCP stdout observed: {'yes' if self.invalid_stdout else 'no'}", file=sys.stderr)
        print("Failure: " + "; ".join(list(leaves(error))[:4]), file=sys.stderr)
        print("Child stderr (sanitized, last 32 lines):", file=sys.stderr)
        print("\n".join(self.stderr_tail) if self.stderr_tail else "(no child stderr captured)", file=sys.stderr,
              flush=True)
