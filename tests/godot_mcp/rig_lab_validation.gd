@tool
extends EditorPlugin
## Test-only controller, enabled only in the runner's disposable editor project.
## Undo/Redo are dispatched through the native Scene menu's real shortcuts.

const RigLab = preload("res://addons/lunitora_godot/rig_lab.gd")
const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")
const LAB_PATH := "res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"
const OPERATION := "godot_create_rig_lab"
const ACTION_NAME := "Lunitora: Create Totolina Rig Lab Scaffold"
const MANIFEST := {
	".": "Node2D", "Meshes": "Node2D", "Meshes/TestMesh": "Polygon2D",
	"Skeleton2D": "Skeleton2D", "Skeleton2D/Root": "Bone2D",
	"Skeleton2D/Root/Tip": "Bone2D", "AnimationPlayer": "AnimationPlayer",
}

var _checks := 0
var _failures := 0
var _counter := 0
var _plugin: EditorPlugin
var _manager: EditorUndoRedoManager
var _reentrant: Array[Dictionary] = []
var _busy_writer: RefCounted
var _original_file_hash := ""
var _stopped_client: RefCounted


class PrepareFailure extends RigLab:
	func _prepare() -> Node2D:
		return null


class VerificationFailure extends RigLab:
	func _verify_after_action(_root: Node, rig: Node, _before: Dictionary,
			_undo_redo: EditorUndoRedoManager) -> bool:
		rig.get_node("Meshes/TestMesh").color = Color.RED
		return false


class ResponseFailure extends RigLab:
	func _valid_result(_value: Dictionary) -> bool:
		return false


class MalformedSuccess extends RigLab:
	func _create_guarded(scene_root: Node, manager: EditorUndoRedoManager, session: String) -> Dictionary:
		var value: Dictionary = super._create_guarded(scene_root, manager, session)
		if value.ok:
			value.result["created_node_count"] = 8
		return value


func _enter_tree() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("GODOT_MCP_RIG_CHECK_FAILED: " + label)


func _frames(count := 3) -> void:
	for _index in range(count):
		await get_tree().process_frame


func _id() -> String:
	_counter += 1
	return "%032x" % _counter


func _find_plugin() -> EditorPlugin:
	for candidate in get_tree().root.find_children("*", "EditorPlugin", true, false):
		var script: Script = candidate.get_script()
		if script != null and script.resource_path == "res://addons/lunitora_godot/plugin.gd":
			return candidate
	return null


func _root() -> Node:
	return EditorInterface.get_edited_scene_root()


func _history() -> UndoRedo:
	return _manager.get_history_undo_redo(_manager.get_object_history_id(_root()))


func _history_snapshot() -> Array:
	var history := _history()
	var names: Array[String] = []
	for index in range(history.get_history_count()):
		names.append(history.get_action_name(index))
	return [history.get_version(), history.get_current_action(), history.get_history_count(),
		history.has_redo(), history.has_undo(), names]


func _dirty() -> bool:
	return _root() != null and EditorInterface.get_unsaved_scenes().has(_root().scene_file_path)


func _write() -> Dictionary:
	return _plugin._dispatch(OPERATION, {}, _id(), _plugin._session_id, true)


func _error(response: Dictionary, code: String, label: String) -> void:
	_check(not response.ok and response.result == null and response.error.code == code, label)


func _shortcut(key: Key, shift := false) -> bool:
	# Godot's Scene menu uses ordinary shortcuts wired to EditorNode commands.
	# This intentionally never calls the underlying UndoRedo.undo()/redo().
	var event := InputEventKey.new()
	event.keycode = key
	event.ctrl_pressed = true
	event.shift_pressed = shift
	event.pressed = true
	for candidate in get_tree().root.find_children("*", "PopupMenu", true, false):
		var menu: PopupMenu = candidate
		var native_scene_menu := false
		for connection in menu.get_signal_connection_list(&"id_pressed"):
			var receiver: Object = connection.callable.get_object()
			if receiver != null and receiver.get_class() == "EditorNode":
				native_scene_menu = true
		var has_undo := false
		var has_redo := false
		for index in range(menu.item_count):
			has_undo = has_undo or menu.get_item_text(index) == "Undo"
			has_redo = has_redo or menu.get_item_text(index) == "Redo"
		if not native_scene_menu or not has_undo or not has_redo:
			continue
		# Execute the normal native menu-state update before its shortcut handler.
		menu.about_to_popup.emit()
		if menu.activate_item_by_event(event, false):
			return true
	return false


func _undo(label: String) -> void:
	var version := _history().get_version()
	_check(_shortcut(KEY_Z), label + " native Scene-menu Undo shortcut activated")
	await _frames()
	_check(_history().get_version() != version, label + " native editor history changed")


func _redo(label: String) -> void:
	var version := _history().get_version()
	_check(_shortcut(KEY_Z, true), label + " native Scene-menu Redo shortcut activated")
	await _frames()
	_check(_history().get_version() != version, label + " native editor history changed")


func _nodes(rig: Node) -> Array[Node]:
	var result: Array[Node] = []
	var pending: Array[Node] = [rig]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		result.append(node)
		for child in node.get_children(true):
			pending.append(child)
	return result


func _recipe(rig: Node, label: String) -> void:
	_check(is_instance_valid(rig), label + " rig exists")
	if not is_instance_valid(rig):
		return
	_check(_nodes(rig).size() == 7, label + " exactly seven generated nodes")
	for path in MANIFEST:
		var node: Node = rig if path == "." else rig.get_node_or_null(NodePath(path))
		_check(node != null and node.get_class() == MANIFEST[path], label + " exact class " + path)
		if node == null:
			continue
		_check(node.owner == _root(), label + " lab-root owner " + path)
		_check(node.get_script() == null, label + " no script " + path)
		if node is Node2D:
			var pose := Transform2D(0.0, Vector2(64, 0)) if path == "Skeleton2D/Root/Tip" else Transform2D.IDENTITY
			_check(node.transform == pose, label + " exact transform " + path)
	var mesh: Polygon2D = rig.get_node("Meshes/TestMesh")
	_check(mesh.polygon == PackedVector2Array([Vector2(0, -12), Vector2(64, -12), Vector2(128, -12),
		Vector2(128, 12), Vector2(64, 12), Vector2(0, 12)]), label + " exact vertices")
	_check(mesh.polygons == [PackedInt32Array([0, 1, 5]), PackedInt32Array([1, 4, 5]),
		PackedInt32Array([1, 2, 4]), PackedInt32Array([2, 3, 4])], label + " exact triangles")
	_check(mesh.color == Color(0.25, 0.5, 1, 1), label + " exact color")
	_check(mesh.texture == null and mesh.uv.is_empty() and mesh.vertex_colors.is_empty(), label + " no image assets")
	_check(mesh.skeleton == NodePath("../../Skeleton2D"), label + " polygon-relative skeleton path")
	_check(mesh.get_bone_count() == 2, label + " two bone weight entries")
	_check(mesh.get_bone_path(0) == NodePath("Root") and mesh.get_bone_path(1) == NodePath("Root/Tip"), label + " skeleton-relative bone paths")
	_check(mesh.get_bone_weights(0) == PackedFloat32Array([1, 0.5, 0, 0, 0.5, 1]), label + " root weights")
	_check(mesh.get_bone_weights(1) == PackedFloat32Array([0, 0.5, 1, 1, 0.5, 0]), label + " tip weights")
	for index in range(6):
		_check(mesh.get_bone_weights(0)[index] + mesh.get_bone_weights(1)[index] == 1.0, label + " normalized vertex " + str(index))
	var skeleton: Skeleton2D = rig.get_node("Skeleton2D")
	_check(skeleton.get_bone_count() == 2, label + " native skeleton registers both bones")
	_check(skeleton.get_node(mesh.get_bone_path(0)) == rig.get_node("Skeleton2D/Root"), label + " root bone path resolves")
	_check(skeleton.get_node(mesh.get_bone_path(1)) == rig.get_node("Skeleton2D/Root/Tip"), label + " tip bone path resolves")
	for path in ["Skeleton2D/Root", "Skeleton2D/Root/Tip"]:
		var bone: Bone2D = rig.get_node(path)
		var pose := Transform2D.IDENTITY if path == "Skeleton2D/Root" else Transform2D(0.0, Vector2(64, 0))
		_check(bone.rest == pose, label + " rest " + path)
		_check(bone.get_length() == 64.0 and bone.get_bone_angle() == 0.0, label + " bone gizmo " + path)
		_check(not bone.get_autocalculate_length_and_angle(), label + " explicit bone length " + path)
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	_empty_player(player, label)


func _empty_player(player: AnimationPlayer, label: String) -> void:
	_check(player.get_animation_library_list().is_empty() and player.get_animation_list().is_empty(), label + " AnimationPlayer has no libraries or clips")
	_check(not player.has_animation(&"RESET") and player.autoplay == &"" and not player.is_playing(), label + " no RESET autoplay or playback")
	_check(player.assigned_animation == &"" and player.current_animation == &"", label + " no assigned animation")


func _detached(rig: Node, label: String) -> void:
	_check(is_instance_valid(rig) and rig.get_parent() == null, label + " retained detached subtree")
	if not is_instance_valid(rig):
		return
	for node in _nodes(rig):
		_check(node.owner == null, label + " detached ownership cleared " + str(node.name))
	var mesh: Polygon2D = rig.get_node("Meshes/TestMesh")
	_check(mesh.polygon.size() == 6 and mesh.polygons.size() == 4 and mesh.get_bone_count() == 2,
		label + " detached polygon geometry and bone data retained")
	_check(mesh.get_bone_weights(0) == PackedFloat32Array([1, 0.5, 0, 0, 0.5, 1]) and
		mesh.get_bone_weights(1) == PackedFloat32Array([0, 0.5, 1, 1, 0.5, 0]),
		label + " detached exact weights retained")
	_empty_player(rig.get_node("AnimationPlayer"), label)


func _file_unchanged(label: String, expected_hash: String = "") -> void:
	_check(FileAccess.get_sha256(LAB_PATH) == (_original_file_hash if expected_hash.is_empty() else expected_hash), label + " lab file not auto-saved")


func _on_tree_activity(_node: Node) -> void:
	_reentrant.append(_plugin._dispatch(OPERATION, {}, _id(), _plugin._session_id, true))


func _on_history_activity() -> void:
	_reentrant.append(_plugin._dispatch(OPERATION, {}, _id(), _plugin._session_id, true))


func _during_editor_commit() -> void:
	_reentrant.append(_busy_writer.create(_root(), _manager, _plugin._session_id, _id(), true))


func _stop_during_dispatch(_operation: String, _params: Dictionary) -> Dictionary:
	_stopped_client.stop()
	return {"ok": false, "result": null, "error": {"code": "INVALID_MESSAGE", "message": "Fixture retired."}}


func _terminal_stop() -> void:
	# Native client state regression; separate actual-wire tests cover retirement
	# while real WebSocket packets are buffered in the disposable editor peer.
	_stopped_client = BridgeClient.new()
	_stopped_client.start(_stop_during_dispatch)
	_stopped_client._stage = BridgeClient.Stage.AUTHENTICATED
	var accepted: bool = _stopped_client._accept({"type": "request", "protocol_version": 1,
		"id": _id(), "operation": "godot_ping", "params": {}})
	_check(not accepted, "retired dispatch cannot send a native response")
	_stopped_client._retry(Time.get_ticks_msec())
	_check(_stopped_client._stage == BridgeClient.Stage.STOPPED,
		"reentrant stop remains terminal after response failure retry")
	_check(not _stopped_client._dispatch.is_valid() and _stopped_client._peer == null,
		"terminal stop discards native dispatch and peer references")
	_stopped_client.poll()
	_check(_stopped_client._stage == BridgeClient.Stage.STOPPED and _stopped_client._peer == null,
		"later native poll does not resurrect a stopped transport")


func _reload_plugin(label: String) -> void:
	var old_session: String = _plugin._session_id
	var old_writer: RefCounted = _plugin._writer
	EditorInterface.set_plugin_enabled("lunitora_godot", false)
	await _frames()
	_check(_find_plugin() == null, label + " plugin really disabled")
	_check(old_writer._retired, label + " old writer retired")
	EditorInterface.set_plugin_enabled("lunitora_godot", true)
	await _frames()
	_plugin = _find_plugin()
	_check(_plugin != null and _plugin._session_id != old_session, label + " reload rolls editor session")
	_error(old_writer.create(_root(), _manager, old_session, _id(), true), "INVALID_MESSAGE", label + " old queued session cannot execute")


func _close_and_open(label: String) -> void:
	_check(not _dirty(), label + " close starts at clean save point")
	_check(_shortcut(KEY_W, true), label + " native Scene-menu Close shortcut activated")
	await _frames(6)
	_check(_root() == null, label + " native editor really closed scene")
	EditorInterface.open_scene_from_path(LAB_PATH)
	await _frames(6)
	_check(_root() != null and _root().scene_file_path == LAB_PATH, label + " native editor reopened saved lab")


func _remove_rig_and_save_empty() -> void:
	var scene := _root()
	var rig: Node = scene.get_node("TotolinaRigV2")
	_manager.create_action("Fixture: remove saved rig", UndoRedo.MERGE_DISABLE, scene)
	_manager.add_do_method(scene, &"remove_child", rig)
	_manager.add_undo_method(scene, &"add_child", rig, true)
	for node in _nodes(rig):
		_manager.add_undo_property(node, &"owner", scene)
	_manager.add_undo_reference(rig)
	_manager.commit_action()
	# Native save_scene_as establishes the same editor save point. Disable only
	# the preview image because the headless renderer cannot create thumbnails.
	EditorInterface.save_scene_as(LAB_PATH, false)
	await _frames()
	_check(not scene.has_node("TotolinaRigV2") and not _dirty(), "empty baseline saved through editor")
	_original_file_hash = FileAccess.get_sha256(LAB_PATH)
	_terminal_stop()


func _run() -> void:
	await _frames(12)
	_plugin = _find_plugin()
	_check(Engine.is_editor_hint() and _plugin != null, "running inside actual native editor with production plugin")
	_manager = get_undo_redo()
	if _plugin == null:
		_finish()
		return
	if _root() == null:
		EditorInterface.open_scene_from_path(LAB_PATH)
		await _frames(8)
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() == 2 and arguments[0] == "rig-gate":
		await _run_gate(arguments[1])
		return
	_check(_root() != null and _root().scene_file_path == LAB_PATH, "isolated saved lab is current editor scene")
	if _root() == null:
		_finish()
		return
	_original_file_hash = FileAccess.get_sha256(LAB_PATH)
	_check(not _dirty() and not _root().has_node("TotolinaRigV2"), "clean empty saved baseline")
	var unrelated: Node2D = _root().get_node("Unrelated")
	var unrelated_id := unrelated.get_instance_id()
	var before := _history_snapshot()
	_error(_plugin._dispatch(OPERATION, {}), "INVALID_REQUEST", "direct dispatcher call cannot impersonate command origin")
	_error(_plugin._writer.create(_root(), _manager, "wrong-session", _id(), true), "INVALID_MESSAGE", "wrong editor session rejected")
	_error(_plugin._writer.create(null, _manager, _plugin._session_id, _id(), true), "LAB_SCENE_REQUIRED", "missing scene rejected")
	_check(_history_snapshot() == before and not _dirty(), "preflight rejection preserves clean contents history and dirty state")
	var prepare_failure := PrepareFailure.new(_plugin._session_id)
	_error(prepare_failure.create(_root(), _manager, _plugin._session_id, _id(), true), "RIG_LAB_BUILD_FAILED", "pre-create build failure code")
	_check(not prepare_failure._active and not prepare_failure._action_started, "pre-create failure safely releases busy guard")
	_check(_history_snapshot() == before, "pre-create build failure preserves existing history")

	_root().child_entered_tree.connect(_on_tree_activity)
	_manager.history_changed.connect(_on_history_activity)
	var created := _write()
	_root().child_entered_tree.disconnect(_on_tree_activity)
	_manager.history_changed.disconnect(_on_history_activity)
	_check(created.ok and created.error == null, "normal dispatcher commits scaffold")
	if not created.ok:
		print("WRITER_FAILURE=", created)
		_finish()
		return
	_check(created.result.created_node_count == 7 and created.result.undo_actions_added == 1, "bounded success count and single undo action")
	_check(created.result.undo_action_name == ACTION_NAME and created.result.auto_saved == false and created.result.read_only == false, "success advertises native undo and no automatic saving")
	_check(not _plugin._writer._active and not _plugin._writer._faulted, "successful response releases writer guard")
	_check(_reentrant.size() >= 2, "synchronous tree and history re-entry actually attempted")
	for response in _reentrant:
		_error(response, "WRITE_BUSY", "synchronous nested write rejected")
	_check(_history().get_history_count() == before[2] + 1, "re-entry creates no nested editor action")
	_check(_dirty(), "clean create marks native editor dirty")
	var rig: Node = _root().get_node("TotolinaRigV2")
	_recipe(rig, "initial create")
	_file_unchanged("initial create")
	before = _history_snapshot()
	_error(_write(), "LAB_ALREADY_CREATED", "duplicate scaffold creation rejected")
	_check(_history_snapshot() == before and _dirty() and _root().get_node("TotolinaRigV2") == rig,
		"duplicate scaffold rejection preserves history dirty state and node identity")
	await _undo("clean baseline")
	_check(not _root().has_node("TotolinaRigV2") and is_instance_valid(rig), "Undo detaches without freeing history-managed rig")
	_detached(rig, "clean Undo")
	_check(not _dirty(), "Undo reaches original clean save point")
	_file_unchanged("clean Undo")
	await _redo("clean baseline")
	_recipe(rig, "clean Redo")
	_check(_dirty(), "Redo becomes dirty again")
	_file_unchanged("clean Redo")
	await _undo("prepare existing redo")
	before = _history_snapshot()
	var rejection_id := _id()
	_error(_plugin._writer.create(null, _manager, _plugin._session_id, rejection_id, true), "LAB_SCENE_REQUIRED", "rejected write preserves existing redo")
	_error(_plugin._writer.create(_root(), _manager, _plugin._session_id, rejection_id, true), "WRITE_REPLAY_REJECTED", "duplicate rejected request is not executable")
	_check(_history_snapshot() == before and is_instance_valid(rig) and not _dirty(), "rejections preserve redo subtree history and dirty state")
	created = _write()
	_check(created.ok, "fresh Create after Undo succeeds")
	_check(not is_instance_valid(rig), "fresh Create discards and disposes abandoned redo subtree")
	rig = _root().get_node("TotolinaRigV2")
	_check(not _history().has_redo(), "fresh Create has no stale redo branch")
	await _undo("prepare dirty baseline")
	_busy_writer = RigLab.new(_plugin._session_id)
	_reentrant.clear()
	_manager.create_action("Fixture: unrelated edit", UndoRedo.MERGE_DISABLE, _root())
	_manager.add_do_property(unrelated, &"position", Vector2(17, 19))
	_manager.add_do_method(self, &"_during_editor_commit")
	_manager.add_undo_property(unrelated, &"position", Vector2(7, 9))
	_manager.commit_action()
	_check(_reentrant.size() == 1, "external native editor commit attempts one nested writer")
	_error(_reentrant[0], "WRITE_BUSY", "undo manager commit blocks inactive MCP writer")
	_check(not _busy_writer._active, "editor commit rejection does not latch busy guard")
	_check(_dirty() and unrelated.position == Vector2(17, 19), "already-dirty unrelated baseline")
	created = _write()
	_check(created.ok, "already-dirty baseline Create succeeds")
	rig = _root().get_node("TotolinaRigV2")
	await _undo("already dirty baseline")
	_check(_dirty() and unrelated.position == Vector2(17, 19), "Undo preserves unrelated edits and already-dirty baseline")
	await _redo("already dirty baseline")
	_check(unrelated.get_instance_id() == unrelated_id and unrelated.position == Vector2(17, 19), "Redo preserves unrelated node identity and properties")
	_file_unchanged("dirty Create Undo Redo")
	EditorInterface.save_scene_as(LAB_PATH, false)
	await _frames()
	_check(not _dirty(), "explicit Save establishes new clean save point")
	var saved_hash := FileAccess.get_sha256(LAB_PATH)
	_check(saved_hash != _original_file_hash, "only explicit Save writes scaffold to isolated lab file")
	await _undo("Create Save Undo")
	_check(_dirty() and not _root().has_node("TotolinaRigV2"), "Undo after Save is dirty relative to saved scaffold")
	await _redo("Create Save Redo")
	_check(not _dirty(), "Redo after Save returns to saved version and clean editor state")
	_file_unchanged("Save-point Undo Redo", saved_hash)

	await _reload_plugin("attached rig")
	_check(_root().get_node("TotolinaRigV2") == rig, "plugin reload does not free attached rig")
	await _undo("Undo after plugin reload")
	await _reload_plugin("detached rig")
	_check(is_instance_valid(rig) and rig.get_parent() == null, "plugin reload retains detached undo-history rig")
	_detached(rig, "detached plugin reload")
	await _redo("Redo after plugin reload")
	_recipe(rig, "reload Redo")
	_check(not _dirty(), "reload does not change editor save point")
	await _close_and_open("attached rig")
	_check(not is_instance_valid(rig), "scene close frees attached generated subtree")
	rig = _root().get_node("TotolinaRigV2")
	_recipe(rig, "saved reopened rig")
	await _remove_rig_and_save_empty()
	created = _write()
	_check(created.ok, "empty saved baseline accepts fresh creation")
	rig = _root().get_node("TotolinaRigV2")
	await _undo("detached scene close")
	await _close_and_open("detached rig")
	_check(not is_instance_valid(rig), "scene close releases detached redo-owned subtree")
	_check(not _root().has_node("TotolinaRigV2"), "reopened lab reflects explicit empty save")
	_original_file_hash = FileAccess.get_sha256(LAB_PATH)

	var faulty := VerificationFailure.new(_plugin._session_id)
	_plugin._writer = faulty
	before = _history_snapshot()
	_error(_write(), "WRITE_OUTCOME_UNKNOWN", "post-action verification failure has uncertain outcome")
	_check(not faulty._active and faulty._action_started and faulty._faulted, "post-action failure releases active guard and latches unsafe outcome")
	_check(_history().get_history_count() == before[1] + 2 and _root().has_node("TotolinaRigV2"), "post-action failure does not pretend to roll back native history")
	before = _history_snapshot()
	_error(_write(), "WRITE_OUTCOME_UNKNOWN", "fresh write blocked after failed post-verification")
	_check(_history_snapshot() == before, "failed outcome gate adds no further action")
	_check(_plugin._dispatch("godot_inspect_scene", {}).ok, "read-only inspection remains available after failed write")
	_file_unchanged("verification failure")
	await _undo("manual inspection recovery Undo")
	await _reload_plugin("recover faulted writer")
	var malformed := ResponseFailure.new(_plugin._session_id)
	_plugin._writer = malformed
	_error(_write(), "WRITE_OUTCOME_UNKNOWN", "response construction failure after action does not report success")
	_check(not malformed._active and malformed._faulted, "response failure safely releases busy guard")
	await _undo("response failure manual Undo")
	await _reload_plugin("recover response failure")
	var malformed_count := MalformedSuccess.new(_plugin._session_id)
	_plugin._writer = malformed_count
	_error(_write(), "WRITE_OUTCOME_UNKNOWN", "malformed success field cannot report success after action")
	_check(not malformed_count._active and malformed_count._faulted, "malformed success releases guard and latches failed outcome")
	before = _history_snapshot()
	_error(_write(), "WRITE_OUTCOME_UNKNOWN", "malformed success blocks fresh requests")
	_check(_history_snapshot() == before, "malformed response gate preserves native history")
	await _undo("malformed success manual Undo")
	await _reload_plugin("recover malformed success")
	_file_unchanged("all failures")
	_check(_root().get_node("Unrelated").position == Vector2(17, 19), "all writer and lifecycle operations preserve unrelated saved property")
	var bounded := RigLab.new(_plugin._session_id)
	var first_ledger_id := ""
	for index in range(128):
		var admitted_id := _id()
		if index == 0:
			first_ledger_id = admitted_id
		var response := bounded.create(null, _manager, _plugin._session_id, admitted_id, true)
		if index == 0 or index == 127:
			_error(response, "LAB_SCENE_REQUIRED", "bounded ledger records rejected admitted ID " + str(index))
	_error(bounded.create(_root(), _manager, _plugin._session_id, _id(), true), "SESSION_WRITE_LIMIT", "write ID ledger fails closed rather than evicting")
	_error(bounded.create(_root(), _manager, _plugin._session_id, first_ledger_id, true),
		"WRITE_REPLAY_REJECTED", "full write ledger still rejects its oldest admitted ID")
	_check(bounded._write_ids.size() == 128, "authoritative writer ledger remains bounded and non-evicting")
	_check(_plugin._dispatch("godot_ping", {}).result.plugin_version == "0.2.0", "existing ping advertises intentional plugin version")
	_check(_plugin._dispatch("godot_get_editor_state", {}).ok and _plugin._dispatch("godot_inspect_scene", {}).ok, "existing read-only tools retain behavior")
	_finish()


func _run_gate(code: String) -> void:
	_check(_root() != null, "isolated gate scene really opened in editor")
	if _root() == null:
		_finish()
		return
	var scene := _root()
	var scene_id := scene.get_instance_id()
	var unrelated: Node2D = scene.get_node("Unrelated")
	var unrelated_id := unrelated.get_instance_id()
	var original_hash := FileAccess.get_sha256(scene.scene_file_path)
	_manager.create_action("Fixture: gate baseline", UndoRedo.MERGE_DISABLE, scene)
	_manager.add_do_property(unrelated, &"position", Vector2(17, 19))
	_manager.add_undo_property(unrelated, &"position", Vector2(7, 9))
	_manager.commit_action()
	await _undo("gate clean baseline")
	_check(not _dirty() and _history().has_redo(), "gate begins clean with existing native redo")
	var before := _history_snapshot()
	_error(_write(), code, "saved isolated scene gate rejects writer")
	_check(_history_snapshot() == before and not _dirty(), "gate rejection preserves clean state and redo history")
	_check(_root().get_instance_id() == scene_id and unrelated.get_instance_id() == unrelated_id and
		unrelated.position == Vector2(7, 9) and not scene.has_node("TotolinaRigV2"), "gate rejection preserves scene and node identities")
	await _redo("gate dirty baseline")
	_check(_dirty(), "gate begins already dirty after real native Redo")
	before = _history_snapshot()
	_error(_write(), code, "already-dirty isolated scene gate rejects writer")
	_check(_history_snapshot() == before and _dirty() and unrelated.position == Vector2(17, 19),
		"gate rejection preserves dirty state native history and unrelated edit")
	_check(FileAccess.get_sha256(scene.scene_file_path) == original_hash, "gate never writes isolated saved scene file")
	_finish()


func _finish() -> void:
	print("GODOT_MCP_RIG_EDITOR_CHECKS=%d FAILURES=%d" % [_checks, _failures])
	get_tree().quit(1 if _failures else 0)
