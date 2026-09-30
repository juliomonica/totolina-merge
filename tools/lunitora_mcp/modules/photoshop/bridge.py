"""Authenticated, bounded WebSocket transport. This is not a general command runner."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hmac
import logging
import sys
from time import perf_counter
from uuid import uuid4

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from core.config import Config, HOST, PORT, valid_token
from .protocol import (BridgeError, MAX_PAYLOAD_BYTES, OPERATIONS, PROTOCOL_VERSION,
                       PROCESS_OPERATION, decode, encode, error_info, validate_response,
                       validate_processing_parameters, peer_failure)

LOG = logging.getLogger("lunitora.bridge")
MAX_CONNECTIONS = 4
MAX_PENDING = 16


@dataclass
class Pending:
    connection: ServerConnection
    operation: str
    future: asyncio.Future


class PhotoshopBridge:
    def __init__(self, config: Config, token: str | None, *, diagnostics: bool = False):
        self.config = config
        self.diagnostics = diagnostics
        self._token = token
        self._server = None
        self._connection = None
        self._connections = set()
        self._pending: dict[str, Pending] = {}
        self.startup_error: BridgeError | None = None

    def _diagnostic(self, message: str) -> None:
        # Callers supply fixed text and validated operation/error names only.
        if self.diagnostics:
            print(f"[Lunitora bridge] {message}", file=sys.stderr, flush=True)

    async def start(self) -> None:
        if self._server is not None:
            return
        if not valid_token(self._token):
            self.startup_error = BridgeError("UNPAIRED")
            return
        try:
            self._server = await serve(
                self._handle_connection, HOST, PORT,
                max_size=MAX_PAYLOAD_BYTES, max_queue=4, write_limit=32768,
                compression=None, open_timeout=5, close_timeout=1,
                ping_interval=20, ping_timeout=20,
            )
        except OSError:
            self.startup_error = BridgeError("PORT_IN_USE")
            LOG.warning("Bridge unavailable: %s", self.startup_error.code)
        else:
            self.startup_error = None
            LOG.info("Read-only Photoshop bridge listening at ws://%s:%s", HOST, PORT)
            self._diagnostic(f"Bridge listening on {HOST}:{PORT}")

    async def stop(self) -> None:
        self._fail_pending(None)
        self._connection = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def _fail_pending(self, connection: ServerConnection | None, code: str = "DISCONNECTED") -> None:
        for pending in list(self._pending.values()):
            if (connection is None or pending.connection is connection) and not pending.future.done():
                pending.future.set_exception(BridgeError(code))

    async def _handle_connection(self, connection: ServerConnection) -> None:
        if len(self._connections) >= MAX_CONNECTIONS or connection.remote_address[0] != HOST:
            await connection.close(1008, "Connection limit")
            return
        self._connections.add(connection)
        self._diagnostic("Incoming WebSocket connection accepted")
        authenticated = False
        try:
            async with asyncio.timeout(self.config.authentication_timeout_seconds):
                raw = await connection.recv()
                self._diagnostic("Authentication message received")
                if not isinstance(raw, str) or len(raw.encode("utf-8")) > 1024:
                    raise BridgeError("AUTH_FAILED")
                auth = decode(raw)
                if (set(auth) != {"type", "protocol_version", "token"} or auth["type"] != "auth"
                        or not valid_token(auth.get("token"))
                        or not hmac.compare_digest(auth["token"], self._token)):
                    raise BridgeError("AUTH_FAILED")
                await connection.send(encode({"type": "auth_result", "protocol_version": PROTOCOL_VERSION,
                                              "ok": True, "error": None}))
                # Publish only after auth_result: no request may precede authentication.
                previous = self._connection
                self._connection = connection
                authenticated = True
                self._diagnostic("Authentication accepted")
                if previous is not None:
                    self._fail_pending(previous)
                    await previous.close(1000, "Replaced by authenticated reconnect")
            async for raw in connection:
                message = decode(raw)
                validate_response(message)
                self._diagnostic(f"WebSocket response received: operation={message['operation']}")
                pending = self._pending.get(message["id"])
                # Late replies for requests already timed out cannot satisfy a later call.
                if pending is None:
                    continue
                if pending.connection is not connection or message["operation"] != pending.operation:
                    raise BridgeError("INVALID_MESSAGE")
                if not pending.future.done():
                    pending.future.set_result(message)
        except (TimeoutError, BridgeError) as error:
            code = error.code if isinstance(error, BridgeError) else "AUTH_FAILED"
            self._diagnostic(f"{'Protocol error' if authenticated else 'Authentication rejected'}: code={code}")
            self._fail_pending(connection, code)
            try:
                if not authenticated:
                    await connection.send(encode({"type": "auth_result", "protocol_version": PROTOCOL_VERSION,
                                                  "ok": False, "error": error_info(code)}))
                await connection.close(1008, code)
            except ConnectionClosed:
                pass
        except ConnectionClosed:
            pass
        except Exception:
            # Peer-controlled data must never be interpolated into logs or exceptions.
            self._fail_pending(connection, "INVALID_MESSAGE")
            LOG.error("Peer protocol failure; connection closed.")
            await connection.close(1008, "INVALID_MESSAGE")
        finally:
            self._diagnostic("WebSocket connection closed")
            if self._connection is connection:
                self._connection = None
            self._connections.discard(connection)
            self._fail_pending(connection)

    async def request(self, operation: str, parameters: dict | None = None) -> tuple[dict, float]:
        if operation not in OPERATIONS:
            raise BridgeError("UNSUPPORTED_OPERATION")
        if operation == PROCESS_OPERATION:
            validate_processing_parameters(parameters)
        elif parameters is not None:
            raise BridgeError("INVALID_MESSAGE")
        self._diagnostic(f"MCP protocol request received: operation={operation}")
        if self.startup_error:
            raise self.startup_error
        connection = self._connection
        if connection is None:
            raise BridgeError("DISCONNECTED")
        if len(self._pending) >= MAX_PENDING:
            raise BridgeError("BUSY")
        request_id = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = Pending(connection, operation, future)
        started = perf_counter()
        try:
            timeout = 30.0 if operation == PROCESS_OPERATION else self.config.request_timeout_seconds
            async with asyncio.timeout(timeout):
                request = {
                    "type": "request", "protocol_version": PROTOCOL_VERSION,
                    "id": request_id, "operation": operation,
                }
                if parameters is not None:
                    request["parameters"] = parameters
                await connection.send(encode(request))
                message = await future
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            if not message["ok"]:
                raise peer_failure(message["error"])
            return message["result"], elapsed_ms
        except TimeoutError:
            raise BridgeError("TIMEOUT") from None
        except ConnectionClosed:
            raise BridgeError("DISCONNECTED") from None
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
