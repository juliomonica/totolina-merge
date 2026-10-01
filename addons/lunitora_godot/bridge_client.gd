@tool
extends RefCounted
## Fixed loopback WebSocket client. This object owns transport state only.

const URL := "ws://127.0.0.1:43128"
const AUTH_PATH := "res://tools/lunitora_mcp/.local/godot-auth.json"
const MAX_FRAME_BYTES := 262144
const MAX_AUTH_BYTES := 4096
const MAX_QUEUED_PACKETS := 8
const MAX_JSON_DEPTH := 16
const MAX_STRING_BYTES := 4096
const CONNECT_TIMEOUT_MS := 5000
const MAX_RETRY_MS := 8000
const OPERATIONS := ["godot_ping", "godot_get_editor_state", "godot_inspect_scene"]

enum Stage { STOPPED, CONNECTING, CHALLENGE, READY_PROOF, AUTHENTICATED }

var _stage := Stage.STOPPED
var _dispatch := Callable()
var _peer: WebSocketPeer
var _crypto := Crypto.new()
var _secret := PackedByteArray()
var _project_id := ""
var _client_nonce := ""
var _server_nonce := ""
var _deadline_ms := 0
var _retry_at_ms := 0
var _retry_delay_ms := 250
var _recent_requests: Array[String] = []


func start(dispatch: Callable) -> void:
	_dispatch = dispatch
	_stage = Stage.CONNECTING
	_retry_at_ms = Time.get_ticks_msec()


func stop() -> void:
	_stage = Stage.STOPPED
	_clear_connection()
	_dispatch = Callable()


func poll() -> void:
	if _stage == Stage.STOPPED:
		return
	var now := Time.get_ticks_msec()
	if _peer == null:
		if now >= _retry_at_ms:
			_connect(now)
		return
	_peer.poll()
	var state := _peer.get_ready_state()
	if state == WebSocketPeer.STATE_CLOSED or state == WebSocketPeer.STATE_CLOSING:
		_retry(now)
		return
	if _stage != Stage.AUTHENTICATED and now > _deadline_ms:
		_retry(now)
		return
	if state != WebSocketPeer.STATE_OPEN:
		return
	# Flush the previous response/proof before consuming another request. This
	# supports simultaneous Codex calls without overfilling the bounded output.
	if _peer.get_current_outbound_buffered_amount() != 0:
		return
	if _stage == Stage.CONNECTING:
		_stage = Stage.CHALLENGE
		if not _send({"type": "hello", "protocol_version": 1, "project_id": _project_id, "client_nonce": _client_nonce}):
			_retry(now)
			return
	for _index in range(MAX_QUEUED_PACKETS):
		if _peer == null or _peer.get_available_packet_count() == 0:
			break
		var packet := _peer.get_packet()
		if not _peer.was_string_packet() or packet.size() > MAX_FRAME_BYTES:
			_retry(now)
			return
		# Round-trip UTF-8 rejects invalid/replacement sequences before JSON parsing.
		var source := packet.get_string_from_utf8()
		if source.to_utf8_buffer() != packet:
			_retry(now)
			return
		var parser := JSON.new()
		if not _unambiguous_json(source) or parser.parse(source) != OK or not parser.data is Dictionary:
			_retry(now)
			return
		if not _accept(parser.data):
			_retry(now)
			return
		if _peer.get_current_outbound_buffered_amount() != 0:
			break


func _connect(now: int) -> void:
	# Windows ACL enforcement and stable ancestor handles belong to the Python owner.
	# The editor additionally rejects links, validates the canonical project binding,
	# and authenticates the listener before sending any editor metadata.
	if OS.get_name() != "Windows" or not _read_credential():
		_retry(now)
		return
	_client_nonce = _crypto.generate_random_bytes(32).hex_encode()
	if not _hex(_client_nonce, 64):
		_retry(now)
		return
	_peer = WebSocketPeer.new()
	_peer.inbound_buffer_size = MAX_FRAME_BYTES
	_peer.outbound_buffer_size = MAX_FRAME_BYTES
	_peer.max_queued_packets = MAX_QUEUED_PACKETS
	_stage = Stage.CONNECTING
	_deadline_ms = now + CONNECT_TIMEOUT_MS
	if _peer.connect_to_url(URL) != OK:
		_retry(now)


func _read_credential() -> bool:
	var absolute := ProjectSettings.globalize_path(AUTH_PATH).simplify_path().replace("\\", "/")
	if not _unlinked_path(absolute) or not FileAccess.file_exists(absolute):
		return false
	var file := FileAccess.open(absolute, FileAccess.READ)
	if file == null or file.get_length() < 1 or file.get_length() > MAX_AUTH_BYTES:
		return false
	var packet := file.get_buffer(file.get_length())
	file.close()
	var source := packet.get_string_from_utf8()
	if source.to_utf8_buffer() != packet:
		return false
	var parser := JSON.new()
	if not _unambiguous_json(source) or parser.parse(source) != OK or not parser.data is Dictionary:
		return false
	var credential: Dictionary = parser.data
	if not _keys(credential, ["schema_version", "project_path", "project_id", "secret"]):
		return false
	if not _version(credential.schema_version) or not credential.project_path is String:
		return false
	var project_path := ProjectSettings.globalize_path("res://").simplify_path().replace("\\", "/").to_lower()
	while project_path.ends_with("/"):
		project_path = project_path.left(-1)
	if credential.project_path != project_path or credential.project_id != project_path.sha256_text():
		return false
	if not _hex(credential.secret, 64) or not _hex(credential.project_id, 64):
		return false
	_secret = String(credential.secret).hex_decode()
	_project_id = credential.project_id
	return _secret.size() == 32


func _unlinked_path(path: String) -> bool:
	var current := path
	while true:
		var parent := current.get_base_dir()
		if parent == current or parent.is_empty():
			return true
		var directory := DirAccess.open(parent)
		if directory == null or directory.is_link(current):
			return false
		current = parent
	return false


func _accept(message: Dictionary) -> bool:
	if not message.has("type") or not message.has("protocol_version") or not _version(message.protocol_version):
		return false
	if _stage == Stage.CHALLENGE:
		if not _keys(message, ["type", "protocol_version", "server_nonce", "proof"]) or message.type != "challenge":
			return false
		if not _hex(message.server_nonce, 64) or not _hex(message.proof, 64):
			return false
		_server_nonce = message.server_nonce
		if not _crypto.constant_time_compare(_proof("server"), String(message.proof).hex_decode()):
			return false
		_stage = Stage.READY_PROOF
		return _send({"type": "authenticate", "protocol_version": 1, "proof": _proof("client").hex_encode()})
	if _stage == Stage.READY_PROOF:
		if not _keys(message, ["type", "protocol_version"]) or message.type != "ready":
			return false
		_stage = Stage.AUTHENTICATED
		_retry_delay_ms = 250
		_secret.fill(0)
		_secret.clear()
		return true
	if _stage != Stage.AUTHENTICATED:
		return false
	if not _keys(message, ["type", "protocol_version", "id", "operation", "params"]) or message.type != "request":
		return false
	if not _hex(message.id, 32) or not message.operation is String or not message.params is Dictionary:
		return false
	if _recent_requests.has(message.id):
		return false
	_recent_requests.append(message.id)
	if _recent_requests.size() > 128:
		_recent_requests.pop_front()
	var result: Dictionary
	if not message.params.is_empty():
		result = _failure("INVALID_REQUEST", "Request parameters must be empty.")
	elif not OPERATIONS.has(message.operation):
		result = _failure("UNSUPPORTED_OPERATION", "Operation is not supported.")
	else:
		result = _dispatch.call(message.operation, message.params)
	var response := {
		"type": "response", "protocol_version": 1, "id": message.id,
		"operation": message.operation, "ok": result.ok,
		"result": result.result, "error": result.error,
	}
	if JSON.stringify(response).to_utf8_buffer().size() > MAX_FRAME_BYTES:
		response.ok = false
		response.result = null
		response.error = {"code": "RESPONSE_TOO_LARGE", "message": "Editor response exceeds the size limit."}
	return _send(response)


func _proof(role: String) -> PackedByteArray:
	var transcript := "lunitora-godot\n1\n%s\n%s\n%s\n%s\n" % [_project_id, _client_nonce, _server_nonce, role]
	return _crypto.hmac_digest(HashingContext.HASH_SHA256, _secret, transcript.to_utf8_buffer())


func _send(message: Dictionary) -> bool:
	if _peer == null or _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return false
	var encoded := JSON.stringify(message)
	if encoded.to_utf8_buffer().size() > MAX_FRAME_BYTES or _peer.get_current_outbound_buffered_amount() != 0:
		return false
	return _peer.send_text(encoded) == OK


func _retry(now: int) -> void:
	_clear_connection()
	_stage = Stage.CONNECTING
	_retry_at_ms = now + _retry_delay_ms
	_retry_delay_ms = mini(_retry_delay_ms * 2, MAX_RETRY_MS)


func _clear_connection() -> void:
	if _peer != null:
		_peer.close()
	_peer = null
	_secret.fill(0)
	_secret.clear()
	_project_id = ""
	_client_nonce = ""
	_server_nonce = ""
	_recent_requests.clear()


func _failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "result": null, "error": {"code": code, "message": message}}


func _version(value: Variant) -> bool:
	return (typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT) and value == 1


func _keys(value: Dictionary, expected: Array) -> bool:
	if value.size() != expected.size():
		return false
	for key in expected:
		if not value.has(key):
			return false
	return true


func _hex(value: Variant, length: int) -> bool:
	if not value is String or value.length() != length:
		return false
	for character in value:
		if not "0123456789abcdef".contains(character):
			return false
	return true


func _unambiguous_json(source: String) -> bool:
	# Godot's JSON parser accepts duplicate object fields. Inspect only lexical
	# structure here, then let the native parser validate complete JSON syntax.
	# Decoding key tokens detects duplicates written with different escapes.
	var objects: Array[Dictionary] = []
	var depth := 0
	var index := 0
	while index < source.length():
		var character := source[index]
		if character == '"':
			var start := index
			index += 1
			var closed := false
			while index < source.length():
				if source[index] == "\\":
					index += 2
				elif source[index] == '"':
					index += 1
					closed = true
					break
				else:
					index += 1
			if not closed:
				return false
			var token := JSON.new()
			if token.parse(source.substr(start, index - start)) != OK or not token.data is String:
				return false
			if String(token.data).to_utf8_buffer().size() > MAX_STRING_BYTES:
				return false
			var next := index
			while next < source.length() and " \t\n\r".contains(source[next]):
				next += 1
			if next < source.length() and source[next] == ":":
				if objects.is_empty() or objects.back().has(token.data):
					return false
				objects.back()[token.data] = true
			continue
		if character == "{" or character == "[":
			depth += 1
			if depth > MAX_JSON_DEPTH:
				return false
			if character == "{":
				objects.append({})
		elif character == "}" or character == "]":
			depth -= 1
			if depth < 0:
				return false
			if character == "}":
				if objects.is_empty():
					return false
				objects.pop_back()
		index += 1
	return depth == 0 and objects.is_empty()
