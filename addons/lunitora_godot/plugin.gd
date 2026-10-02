@tool
extends EditorPlugin
## Three unchanged read-only operations and four fixed, gated undoable writes.

const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")
const Inspection = preload("res://addons/lunitora_godot/inspection.gd")
const RigLab = preload("res://addons/lunitora_godot/rig_lab.gd")

var _bridge: RefCounted
var _inspection: RefCounted
var _session_id := ""
var _writer: RefCounted


func _enter_tree() -> void:
	_inspection = Inspection.new()
	_session_id = Crypto.new().generate_random_bytes(16).hex_encode()
	_writer = RigLab.new(_session_id)
	_bridge = BridgeClient.new()
	_bridge.start(_dispatch)
	EditorInterface.get_selection().selection_changed.connect(_invalidate_animation_admission)
	EditorInterface.get_inspector().edited_object_changed.connect(_invalidate_animation_admission)
	scene_changed.connect(_invalidate_animation_admission)
	set_process(true)


func _exit_tree() -> void:
	set_process(false)
	EditorInterface.get_selection().selection_changed.disconnect(_invalidate_animation_admission)
	EditorInterface.get_inspector().edited_object_changed.disconnect(_invalidate_animation_admission)
	scene_changed.disconnect(_invalidate_animation_admission)
	if _writer != null:
		_writer.retire()
	if _bridge != null:
		_bridge.stop()
	_bridge = null
	_inspection = null
	_writer = null
	_session_id = ""


func _process(_delta: float) -> void:
	var writer: RefCounted = _writer
	if writer == null or writer._in_editor_process:
		return
	writer.begin_editor_process(EditorInterface.get_edited_scene_root(), Engine.get_process_frames())
	_poll_editor_commands()
	# A synchronous dispatch can retire/reload the plugin. End the context that
	# was actually entered, never a replacement session's writer.
	writer.end_editor_process()


func _poll_editor_commands() -> void:
	if _bridge != null:
		_bridge.poll()


func _invalidate_animation_admission(_root: Node = null) -> void:
	if _writer != null:
		_writer.invalidate_animation_admission()


func _dispatch(operation: String, params: Dictionary, request_id := "",
		expected_session_id := "", command_origin := false) -> Dictionary:
	if not params.is_empty():
		return _inspection.failure("INVALID_REQUEST", "Request parameters must be empty.")
	match operation:
		"godot_create_tolina_rig_lab":
			return _writer.create_tolina(EditorInterface.get_edited_scene_root(), get_undo_redo(),
				expected_session_id, request_id, command_origin)
		"godot_create_tolina_lab_blink":
			return _writer.create_tolina_blink(EditorInterface.get_edited_scene_root(), get_undo_redo(),
				expected_session_id, request_id, command_origin)
		"godot_create_rig_lab_animation":
			return _writer.create_animation(EditorInterface.get_edited_scene_root(), get_undo_redo(),
				expected_session_id, request_id, command_origin)
		"godot_create_rig_lab":
			return _writer.create(EditorInterface.get_edited_scene_root(), get_undo_redo(),
				expected_session_id, request_id, command_origin)
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
