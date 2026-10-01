"""One authenticated editor; reads stay concurrent and one lab write is fenced."""
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
from .protocol import (BridgeError, MAX_PAYLOAD_BYTES, OPERATIONS, PROTOCOL_VERSION, READ_OPERATIONS,
                       WRITE_OPERATION,
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
    sequence: int = 0


@dataclass
class UnresolvedWrite:
    request_id: str
    connection: ServerConnection
    session_id: str
    sequence: int = 0
    possibly_sent: bool = False
    send_completed: bool = False


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
        self._send_lock = asyncio.Lock()
        self._send_sequence = 0
        self._write_active = False
        # At most one tombstone, no queued writes or persistent recovery storage.
        self._unresolved_write: UnresolvedWrite | None = None
        self._last_write_receipt: UnresolvedWrite | None = None
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
                unresolved = self._unresolved_write
                writer = message["operation"] == WRITE_OPERATION
                # A terminal writer reply must match its original socket, ID and
                # target session. Replay rejection cannot settle original work.
                if writer:
                    if (unresolved is None or message["id"] != unresolved.request_id
                            or unresolved.connection is not connection):
                        continue
                    if message["editor_session_id"] != unresolved.session_id:
                        raise BridgeError("INVALID_MESSAGE", connected=True)
                    if message["ok"] and message["result"]["project_path"] != self._credential.project_path:
                        raise BridgeError("PROJECT_MISMATCH", connected=True)
                settles_writer = writer and (message["ok"] or
                    message["error"]["code"] != "WRITE_REPLAY_REJECTED")
                if pending is None:
                    if settles_writer:
                        self._unresolved_write = None
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
                    if not writer:
                        self._settle_from_read(pending, data)
                if settles_writer:
                    self._unresolved_write = None
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
        if operation == WRITE_OPERATION:
            return await self._request_write()
        return await self._exchange(operation)

    def _settle_from_read(self, pending: Pending, data: dict) -> None:
        unresolved = self._unresolved_write
        if unresolved is None:
            return
        if pending.connection is unresolved.connection:
            # FIFO peer consumption and synchronous dispatch make a later read
            # reply a temporal fence. It says nothing about semantic success.
            if (unresolved.send_completed and pending.sequence > unresolved.sequence
                    and data["editor_session_id"] == unresolved.session_id):
                self._unresolved_write = None
        elif (pending.connection is self._connection
              and pending.operation in {"godot_ping", "godot_get_editor_state"}
              and data["editor_session_id"] == unresolved.session_id):
            # Godot discards its old peer before connecting a replacement. A
            # compatible fresh reply therefore proves old work now incapable.
            self._unresolved_write = None

    def retain_unknown_write(self) -> None:
        # The editor reply may be valid while constructing the public MCP result
        # fails. Preserve that request's admission fence until a separate read.
        if self._last_write_receipt is not None and self._unresolved_write is None:
            self._unresolved_write = self._last_write_receipt

    async def _retire(self, connection: ServerConnection) -> None:
        if self._connection is connection:
            self._connection = None
            self._session_id = None
        # Closing Python alone isn't settlement. Keep the tombstone until the
        # editor sends a fresh read from its replacement peer.
        await connection.close(1008, "WRITE_OUTCOME_UNKNOWN")

    async def _request_write(self) -> tuple[dict, float]:
        if self._write_active or self._unresolved_write is not None:
            raise BridgeError("WRITE_BUSY", connected=self._connection is not None)
        connection = self._connection
        if connection is None:
            raise BridgeError("DISCONNECTED")
        self._write_active = True
        self._last_write_receipt = None
        started = perf_counter()
        try:
            # Required on EVERY call, including first connection/Python restart.
            # No cached read, automatic write retry, or replacement-socket send.
            data, _ = await self._exchange("godot_get_editor_state", connection=connection)
            if self._connection is not connection:
                raise BridgeError("DISCONNECTED")
            unresolved = UnresolvedWrite(secrets.token_hex(16), connection, data["editor_session_id"])
            self._unresolved_write = unresolved
            try:
                result, _ = await self._exchange(WRITE_OPERATION, connection=connection, writer=unresolved)
                self._last_write_receipt = unresolved
                return result, round((perf_counter() - started) * 1000, 3)
            except asyncio.CancelledError:
                if unresolved.possibly_sent:
                    if not unresolved.send_completed:
                        await asyncio.shield(self._retire(connection))
                    # Report uncertainty to any caller which still awaits us.
                    raise BridgeError("WRITE_OUTCOME_UNKNOWN", connected=self._connection is connection) from None
                self._unresolved_write = None
                raise
            except Exception as error:
                if unresolved.possibly_sent:
                    if not unresolved.send_completed:
                        await self._retire(connection)
                    if (not isinstance(error, BridgeError) or error.code not in
                            {"LAB_SCENE_REQUIRED", "LAB_ROOT_MISMATCH", "LAB_ALREADY_CREATED",
                             "RIG_LAB_BUILD_FAILED", "WRITE_REPLAY_REJECTED", "SESSION_WRITE_LIMIT",
                             "WRITE_OUTCOME_UNKNOWN", "WRITE_BUSY"}):
                        raise BridgeError("WRITE_OUTCOME_UNKNOWN", connected=self._connection is connection) from None
                else:
                    self._unresolved_write = None
                raise
        except BridgeError as error:
            if error.code == "BUSY":
                raise BridgeError("WRITE_BUSY", connected=error.connected) from None
            raise
        finally:
            self._write_active = False

    async def _exchange(self, operation: str, *, connection: ServerConnection | None = None,
                        writer: UnresolvedWrite | None = None) -> tuple[dict, float]:
        connection = connection if connection is not None else self._connection
        if connection is None:
            raise BridgeError("DISCONNECTED")
        if len(self._pending) >= MAX_PENDING:
            raise BridgeError("BUSY", connected=True)
        started = perf_counter()
        request_id = writer.request_id if writer is not None else secrets.token_hex(16)
        future = asyncio.get_running_loop().create_future()
        pending = Pending(connection, operation, future)
        self._pending[request_id] = pending
        try:
            async with asyncio.timeout(self.config.request_timeout_seconds):
                message = {
                    "type": "request", "protocol_version": PROTOCOL_VERSION,
                    "id": request_id, "operation": operation, "params": {},
                }
                if writer is not None:
                    message["editor_session_id"] = writer.session_id
                encoded = encode(message)
                async with self._send_lock:
                    if self._connection is not connection:
                        raise BridgeError("DISCONNECTED")
                    self._send_sequence += 1
                    pending.sequence = self._send_sequence
                    if writer is not None:
                        writer.sequence = pending.sequence
                        writer.possibly_sent = True
                    await connection.send(encoded)
                    if writer is not None:
                        writer.send_completed = True
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
