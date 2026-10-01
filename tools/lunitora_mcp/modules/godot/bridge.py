"""One Codex-owned IPv4 listener, one mutually authenticated read-only editor."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from functools import partial
import hmac
import logging
import secrets
import socket
from time import perf_counter

from websockets.asyncio.server import ServerConnection, serve
from websockets.asyncio.connection import Connection
from websockets.exceptions import ConnectionClosed

from .config import Config, Credential, HOST, PORT
from .protocol import (BridgeError, MAX_PAYLOAD_BYTES, OPERATIONS, PROTOCOL_VERSION,
                       decode, encode, error_info, proof, validate_authenticate,
                       validate_hello, validate_response)

MAX_CONNECTIONS = 4
MAX_PENDING = 8
MAX_REMEMBERED_NONCES = 4096
_WIRE_LOG = logging.getLogger("lunitora.godot.websocket")
# Never enable library wire logging: authentication proofs must not be logged.
_WIRE_LOG.disabled = True


@dataclass
class Pending:
    connection: ServerConnection
    operation: str
    future: asyncio.Future


class _BoundedConnection(ServerConnection):
    """Count TCP transports before HTTP/WebSocket upgrade or auth can allocate work."""
    def __init__(self, *args, bridge, **kwargs):
        self._bridge = bridge
        self._admitted = False
        super().__init__(*args, **kwargs)

    def connection_made(self, transport):
        if len(self._bridge._transports) >= MAX_CONNECTIONS:
            # Initialize the base protocol so connection_lost can safely clean up,
            # but do not schedule a WebSocket handshake/server handler task.
            Connection.connection_made(self, transport)
            transport.abort()
            return
        self._bridge._transports.add(transport)
        self._admitted = True
        super().connection_made(transport)

    def connection_lost(self, exc):
        if self._admitted:
            self._bridge._transports.discard(self.transport)
        super().connection_lost(exc)


class GodotBridge:
    def __init__(self, config: Config, credential: Credential | None, *,
                 startup_error: BridgeError | None = None, port: int = PORT):
        self.config = config
        self._credential = credential
        # Only direct test construction injects an ephemeral port. The entrypoint
        # exposes no endpoint flags, environment variables, or configuration keys.
        self._port = port
        self._server = None
        self._connection = None
        self._connections = set()
        self._transports = set()
        self._pending: dict[str, Pending] = {}
        self._session_id: str | None = None
        self._nonce_order = deque()
        self._nonces = set()
        self.startup_error = startup_error

    @property
    def port(self) -> int:
        return self._server.sockets[0].getsockname()[1] if self._server else self._port

    async def start(self) -> None:
        if self._server is not None or self.startup_error is not None:
            return
        if self._credential is None:
            self.startup_error = BridgeError("LOCAL_AUTH_UNSAFE")
            return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind((HOST, self._port))
            listener.listen(MAX_CONNECTIONS)
            listener.setblocking(False)
            self._server = await serve(
                self._handle_connection, sock=listener, origins=[None],
                max_size=MAX_PAYLOAD_BYTES, max_queue=4, write_limit=32768,
                compression=None, open_timeout=5, close_timeout=1,
                ping_interval=20, ping_timeout=20, logger=_WIRE_LOG,
                create_connection=partial(_BoundedConnection, bridge=self),
            )
        except OSError:
            listener.close()
            self.startup_error = BridgeError("PORT_IN_USE")
        except BaseException:
            listener.close()
            raise

    async def stop(self) -> None:
        self._fail_pending(None)
        self._connection = None
        self._session_id = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def _fail_pending(self, connection: ServerConnection | None, code: str = "DISCONNECTED") -> None:
        for pending in list(self._pending.values()):
            if (connection is None or pending.connection is connection) and not pending.future.done():
                pending.future.set_exception(BridgeError(code, connected=code != "DISCONNECTED"))

    def _remember_nonce(self, nonce: str) -> None:
        if nonce in self._nonces:
            raise BridgeError("AUTH_FAILED")
        self._nonce_order.append(nonce)
        self._nonces.add(nonce)
        if len(self._nonce_order) > MAX_REMEMBERED_NONCES:
            self._nonces.remove(self._nonce_order.popleft())

    async def _handle_connection(self, connection: ServerConnection) -> None:
        if len(self._connections) >= MAX_CONNECTIONS or connection.remote_address[0] != HOST:
            await connection.close(1008, "BUSY")
            return
        self._connections.add(connection)
        authenticated = False
        try:
            async with asyncio.timeout(self.config.authentication_timeout_seconds):
                hello = decode(await connection.recv())
                validate_hello(hello)
                if hello["project_id"] != self._credential.project_id:
                    raise BridgeError("PROJECT_MISMATCH")
                self._remember_nonce(hello["client_nonce"])
                server_nonce = secrets.token_hex(32)
                await connection.send(encode({
                    "type": "challenge", "protocol_version": PROTOCOL_VERSION,
                    "server_nonce": server_nonce,
                    "proof": proof(self._credential.secret, self._credential.project_id,
                                   hello["client_nonce"], server_nonce, "server"),
                }))
                authentication = decode(await connection.recv())
                validate_authenticate(authentication)
                expected = proof(self._credential.secret, self._credential.project_id,
                                 hello["client_nonce"], server_nonce, "client")
                if not hmac.compare_digest(authentication["proof"], expected):
                    raise BridgeError("AUTH_FAILED")
                if self._connection is not None:
                    raise BridgeError("BUSY")
                # Reserve before awaiting ready; concurrent handshakes cannot replace
                # an authenticated editor, even when the first send yields.
                self._connection = connection
                self._session_id = None
                await connection.send(encode({"type": "ready", "protocol_version": PROTOCOL_VERSION}))
                authenticated = True
            async for raw in connection:
                message = decode(raw)
                validate_response(message)
                pending = self._pending.get(message["id"])
                # Late or duplicate replies cannot satisfy a different request.
                if pending is None:
                    continue
                if pending.connection is not connection or message["operation"] != pending.operation:
                    raise BridgeError("INVALID_MESSAGE", connected=True)
                if message["ok"]:
                    data = message["result"]
                    if "project_path" in data and data["project_path"] != self._credential.project_path:
                        raise BridgeError("PROJECT_MISMATCH", connected=True)
                    session_id = data["editor_session_id"]
                    if self._session_id is not None and session_id != self._session_id:
                        raise BridgeError("INVALID_MESSAGE", connected=True)
                    self._session_id = session_id
                if not pending.future.done():
                    pending.future.set_result(message)
        except (TimeoutError, BridgeError) as error:
            code = error.code if isinstance(error, BridgeError) else "AUTH_FAILED"
            self._fail_pending(connection, code)
            try:
                if not authenticated:
                    await connection.send(encode({"type": "rejected", "protocol_version": PROTOCOL_VERSION,
                                                  "error": error_info(code)}))
                await connection.close(1008, code)
            except ConnectionClosed:
                pass
        except ConnectionClosed:
            pass
        except Exception:
            # Never echo exceptions, peer payloads, close reasons, or proof material.
            self._fail_pending(connection, "INVALID_MESSAGE")
            await connection.close(1008, "INVALID_MESSAGE")
        finally:
            if self._connection is connection:
                self._connection = None
                self._session_id = None
            self._connections.discard(connection)
            self._fail_pending(connection)

    async def request(self, operation: str, params: dict | None = None) -> tuple[dict, float]:
        if type(operation) is not str or operation not in OPERATIONS:
            raise BridgeError("UNSUPPORTED_OPERATION")
        if params is not None and (type(params) is not dict or params != {}):
            raise BridgeError("INVALID_REQUEST")
        if self.startup_error:
            raise self.startup_error
        connection = self._connection
        if connection is None:
            raise BridgeError("DISCONNECTED")
        if len(self._pending) >= MAX_PENDING:
            raise BridgeError("BUSY", connected=True)
        started = perf_counter()
        request_id = secrets.token_hex(16)
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = Pending(connection, operation, future)
        try:
            async with asyncio.timeout(self.config.request_timeout_seconds):
                await connection.send(encode({
                    "type": "request", "protocol_version": PROTOCOL_VERSION,
                    "id": request_id, "operation": operation, "params": {},
                }))
                message = await future
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            if not message["ok"]:
                raise BridgeError(message["error"]["code"], connected=True)
            return message["result"], elapsed_ms
        except TimeoutError:
            raise BridgeError("TIMEOUT", connected=True) from None
        except ConnectionClosed:
            raise BridgeError("DISCONNECTED") from None
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
