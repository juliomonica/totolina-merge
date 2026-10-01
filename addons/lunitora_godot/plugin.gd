@tool
extends EditorPlugin
## v0.1 dispatch has exactly three read-only operations with empty parameters.

const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")
const Inspection = preload("res://addons/lunitora_godot/inspection.gd")

var _bridge: RefCounted
var _inspection: RefCounted
var _session_id := ""


func _enter_tree() -> void:
	_inspection = Inspection.new()
	_session_id = Crypto.new().generate_random_bytes(16).hex_encode()
	_bridge = BridgeClient.new()
	_bridge.start(_dispatch)
	set_process(true)


func _exit_tree() -> void:
	set_process(false)
	if _bridge != null:
		_bridge.stop()
	_bridge = null
	_inspection = null
	_session_id = ""


func _process(_delta: float) -> void:
	if _bridge != null:
		_bridge.poll()


func _dispatch(operation: String, params: Dictionary) -> Dictionary:
	if not params.is_empty():
		return _inspection.failure("INVALID_REQUEST", "Request parameters must be empty.")
	match operation:
		"godot_ping":
			return _inspection.ping(_session_id)
		"godot_get_editor_state":
			return _inspection.editor_state(
				EditorInterface.get_edited_scene_root(),
				EditorInterface.get_selection().get_selected_nodes(),
				EditorInterface.get_unsaved_scenes(), _session_id
			)
		"godot_inspect_scene":
			return _inspection.inspect_scene(
				EditorInterface.get_edited_scene_root(),
				EditorInterface.get_unsaved_scenes(), _session_id
			)
	return _inspection.failure("UNSUPPORTED_OPERATION", "Operation is not supported.")
