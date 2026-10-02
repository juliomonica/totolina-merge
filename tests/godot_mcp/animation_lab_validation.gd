@tool
extends EditorPlugin
## Disposable-editor acceptance driver. Never enabled in the repository project.
## Python uses the registered public MCP tool; this driver only supplies native
## editor shortcuts, explicit test saves, adverse fixtures and evidence.

const LAB := "res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"
const ANGLE := 0.3490658503988659
const SIGNALS := [&"animation_list_changed", &"current_animation_changed", &"animation_finished", &"caches_cleared"]
signal normal_tick
var _checks := 0
var _failures := 0
var _request_counter := 0
var _ack := ""
var _pending_ack := ""
var _countdown := 0
var _sequence := 0
var _previous := ""
var _command_ok := true
var _saved_hash := ""
var _old_session := ""
var _sentinels: Array[Dictionary] = []
var _observations: Array[Dictionary] = []
var _other: AnimationPlayer
var _retained_library: WeakRef
var _retained_animation: WeakRef
var _unclassified := false
var _reentrant_results: Array[Dictionary] = []
var _fault_requested := false
var _removed_tip: Bone2D
var _retarget_next_write := false


class PrepareFailure extends "res://addons/lunitora_godot/rig_lab.gd":
	func _prepare_animation() -> AnimationLibrary:
		return null


class VerifyFailure extends "res://addons/lunitora_godot/rig_lab.gd":
	func _verify_animation_after_action(_scene: Node, _rig: Node, _player: AnimationPlayer,
			_tip_node: Bone2D, _library: AnimationLibrary, _before: Dictionary,
			_manager: EditorUndoRedoManager) -> bool:
		return false


class ResponseFailure extends "res://addons/lunitora_godot/rig_lab.gd":
	func _valid_animation_result(_value: Dictionary) -> bool:
		return false


func _enter_tree() -> void:
	if OS.get_cmdline_user_args().has("animation-native"):
		call_deferred("_run")


func _normal_process_tick() -> void:
	# Called solely by the copied plugin's _poll_editor_commands test hook, after
	# production begin_editor_process and before production end_editor_process.
	# Await continuations here are genuine normal editor passes, never fake polls.
	normal_tick.emit()


func _frames(count := 8) -> void:
	for _index in range(count):
		await normal_tick


func _check(value: bool, label: String) -> void:
	_checks += 1
	if not value:
		_failures += 1
		push_error("GODOT_MCP_ANIMATION_CHECK_FAILED: " + label)


func _write(operation := "godot_create_rig_lab_animation") -> Dictionary:
	_request_counter += 1
	var plugin := _plugin()
	return plugin._dispatch(operation, {}, "%032x" % _request_counter, plugin._session_id, true)


func _history_state() -> Array:
	var manager := get_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(_root()))
	var names: Array[String] = []
	for index in range(history.get_history_count()):
		names.append(history.get_action_name(index))
	return [history.get_version(), history.get_current_action(), history.get_history_count(), history.has_redo(), history.has_undo(), names]


func _dirty() -> bool:
	return EditorInterface.get_unsaved_scenes().has(LAB)


func _reject(code: String, label: String) -> void:
	var scene := _snapshot()
	var history := _history_state()
	var was_dirty := _dirty()
	var saved := FileAccess.get_sha256(LAB)
	var reply := _write()
	_check(not reply.ok and reply.error.code == code, label + " exact error " + code)
	_check(_snapshot() == scene, label + " exact scene/resource properties and identities unchanged")
	_check(_history_state() == history, label + " native history and redo preserved")
	_check(_dirty() == was_dirty, label + " dirty/save point preserved")
	_check(FileAccess.get_sha256(LAB) == saved, label + " no automatic save")


func _assert_recipe(label: String) -> void:
	var player := _player()
	_check(player.get_animation_library_list() == [&""], label + " only global library")
	_check(player.get_animation_list() == PackedStringArray(["bend_tip"]), label + " only bend_tip")
	if not player.has_animation(&"bend_tip"):
		return
	var animation := player.get_animation(&"bend_tip")
	_check(animation.length == 1.0 and animation.step == 0.125 and animation.loop_mode == Animation.LOOP_NONE, label + " length step and loop")
	_check(animation.get_track_count() == 1 and animation.track_get_type(0) == Animation.TYPE_VALUE, label + " one value track")
	_check(animation.track_get_path(0) == NodePath("Skeleton2D/Root/Tip:rotation"), label + " exact path")
	_check(player.get_node(player.root_node) == _root().get_node("TotolinaRigV2"), label + " player root resolves to rig")
	_check(player.get_node(player.root_node).get_node(NodePath(animation.track_get_path(0).get_concatenated_names())) == _tip(), label + " track resolves to exact native Tip")
	_check(animation.track_get_interpolation_type(0) == Animation.INTERPOLATION_LINEAR_ANGLE, label + " angle interpolation")
	_check(animation.value_track_get_update_mode(0) == Animation.UPDATE_CONTINUOUS, label + " continuous updates")
	_check(animation.track_is_enabled(0) and not animation.track_is_imported(0) and not animation.track_get_interpolation_loop_wrap(0), label + " exact flags")
	_check(animation.track_get_key_count(0) == 3, label + " three keys")
	for index in range(3):
		_check(animation.track_get_key_time(0, index) == [0.0, 0.5, 1.0][index], label + " key time " + str(index))
		_check(typeof(animation.track_get_key_value(0, index)) == TYPE_FLOAT and animation.track_get_key_value(0, index) == [0.0, ANGLE, 0.0][index], label + " exact float key " + str(index))
		_check(animation.track_get_key_transition(0, index) == 1.0, label + " transition " + str(index))
	for time in [0.25, 0.75]:
		_check(absf(animation.value_track_interpolate(0, time) - deg_to_rad(10.0)) < 0.000001, label + " detached +10-degree interpolation " + str(time))
	_check(not player.has_animation(&"RESET") and animation.get_marker_names().is_empty(), label + " no RESET or markers")
	_check(player.autoplay == &"" and player.assigned_animation == &"" and player.current_animation == &"" and not player.is_playing() and player.get_queue().is_empty(), label + " pristine stopped unassigned player")
	_check(_tip().transform == Transform2D(0.0, Vector2(64, 0)) and _tip().rest == Transform2D(0.0, Vector2(64, 0)), label + " exact unchanged rest/current pose")
	var rig := _root().get_node("TotolinaRigV2")
	_check(rig.find_children("*", "", true, false).size() == 6, label + " unchanged exact seven nodes")
	for node in [rig] + rig.find_children("*", "", true, false):
		_check(node.owner == _root() and node.get_script() == null, label + " native script-free lab ownership " + str(node.name))


func _cycle(label: String) -> void:
	var before := _snapshot()
	var was_dirty := _dirty()
	var saved := FileAccess.get_sha256(LAB)
	var history := _history_state()
	_reentrant_results.clear()
	get_undo_redo().history_changed.connect(_during_commit)
	var reply := _write()
	get_undo_redo().history_changed.disconnect(_during_commit)
	_check(reply.ok, label + " fixed writer success")
	if not reply.ok:
		print("ANIMATION_WRITER_FAILURE=", reply)
		return
	_check(reply.result.undo_actions_added == 1 and reply.result.auto_saved == false, label + " one action and no saving")
	_check(_reentrant_results.size() == 2, label + " actual native history signal attempted both writers")
	for response in _reentrant_results:
		_check(not response.ok and response.error.code == "WRITE_BUSY", label + " shared guard rejects cross-writer reentry")
	_check(_history_state()[2] == history[1] + 2, label + " one new unmerged action")
	var library := _player().get_animation_library(&"")
	var animation := _player().get_animation(&"bend_tip")
	_retained_library = weakref(library)
	_retained_animation = weakref(animation)
	await _frames()
	_assert_recipe(label + " Create after frames")
	_check(_dirty(), label + " Create dirty")
	_check(_shortcut(KEY_Z), label + " native Undo")
	await _frames()
	_check(_snapshot() == before, label + " Undo exact original scene state after frames")
	_check(_dirty() == was_dirty, label + " Undo original save point")
	_check(_shortcut(KEY_Z, true), label + " native Redo")
	await _frames()
	_assert_recipe(label + " Redo after frames")
	_check(_player().get_animation_library(&"") == library and _player().get_animation(&"bend_tip") == animation, label + " Redo same retained resource instances")
	_check(FileAccess.get_sha256(LAB) == saved, label + " Create Undo Redo filesystem unchanged")
	_check(_shortcut(KEY_Z), label + " return to pre-animation state")
	await _frames()
	_check(_snapshot() == before, label + " final Undo exact pristine scene")


func _reload(label: String) -> void:
	# Retire between native processing passes, not while this test hook's copied
	# EditorPlugin is itself executing on the C++ notification stack.
	await get_tree().process_frame
	var old: String = _plugin()._session_id
	var old_writer: RefCounted = _plugin()._writer
	EditorInterface.set_plugin_enabled("lunitora_godot", false)
	_check(old_writer._retired, label + " old session writer retired")
	EditorInterface.set_plugin_enabled("lunitora_godot", true)
	await _frames()
	_check(_plugin()._session_id != old, label + " fresh editor session")


func _save(label: String) -> void:
	EditorInterface.save_scene_as(LAB, false)
	_check(not _dirty(), label + " native save point")


func _run() -> void:
	await _frames(16)
	_check(Engine.is_editor_hint() and _plugin() != null, "actual editor production writer")
	_check(DisplayServer.get_name() == "Windows", "real graphical Windows editor admission proof")
	_check(_root() != null and _root().scene_file_path == LAB, "dedicated disposable lab open")
	if _root() == null:
		_finish()
		return
	var original := FileAccess.get_sha256(LAB)
	_reject("LAB_RIG_REQUIRED", "empty v2 baseline")
	var rig_reply := _write("godot_create_rig_lab")
	_check(rig_reply.ok and rig_reply.result.created_node_count == 7, "unchanged v2 writer creates seven-node prerequisite")
	_save("explicit disposable rig save")
	await _frames()
	_check(not _dirty() and FileAccess.get_sha256(LAB) != original, "saved pristine rig baseline clean")
	_check(_connections(_player()).is_empty(), "never selected player really detached")
	var baseline := FileAccess.get_sha256(LAB)
	await _cycle("clean baseline")
	_check(FileAccess.get_sha256(LAB) == baseline, "full clean native cycle never saved")
	# Existing redo must survive every rejection below.
	_command("wrong_root")
	_reject("LAB_ROOT_MISMATCH", "wrong root")
	_command("restore_root")
	var scene_path := _root().scene_file_path
	_root().scene_file_path = "res://scenes/production_like.tscn"
	_reject("LAB_SCENE_REQUIRED", "production scene path")
	_root().scene_file_path = scene_path
	await _frames()
	_command("modified_tip")
	_reject("LAB_RIG_MISMATCH", "modified deterministic rest")
	_command("restore_tip")
	_command("wrong_owner")
	_reject("LAB_RIG_MISMATCH", "generated node ownership mismatch")
	_command("restore_owner")
	_command("script_tip")
	_reject("LAB_RIG_MISMATCH", "generated native node script mismatch")
	_command("restore_script")
	_command("wrong_class")
	await _frames()
	_reject("LAB_RIG_MISMATCH", "generated native Bone2D class mismatch")
	_command("restore_class")
	await _frames()
	_command("wrong_path")
	_reject("LAB_RIG_MISMATCH", "wrong AnimationPlayer root path")
	_command("restore_path")
	_command("speed")
	_reject("LAB_ANIMATION_CONFLICT", "modified default playback setting")
	_command("restore_speed")
	_command("empty_library")
	_reject("LAB_ANIMATION_CONFLICT", "existing empty global library")
	_command("remove_library")
	_command("observer")
	_reject("LAB_ANIMATION_EDITOR_BUSY", "unclassified relevant observer")
	_command("remove_observer")
	await _frames()
	_check(_history_state()[3], "pre-action rejection preserves native redo branch")
	var reply := _write()
	_check(reply.ok, "fresh Create after Undo")
	if not reply.ok:
		print("ANIMATION_WRITER_FAILURE=", reply)
		_finish()
		return
	_check(_retained_library.get_ref() == null and _retained_animation.get_ref() == null, "fresh Create releases abandoned redo library and animation with only WeakRefs retained")
	_check(not _history_state()[3], "fresh Create discards abandoned native redo")
	await _frames()
	_assert_recipe("fresh Create")
	_reject("LAB_ANIMATION_ALREADY_CREATED", "duplicate animation")
	_check(_shortcut(KEY_Z), "fresh Create native Undo")
	await _frames()
	_command("dirty")
	_check(_dirty(), "already-dirty unrelated baseline")
	await _frames()
	await _cycle("already dirty baseline")
	_check(_root().position == Vector2(7, 9), "unrelated dirty property preserved")
	_save("explicit save pristine rig plus unrelated edit")
	await _frames()
	_check(not _dirty(), "new clean save point")
	# Actual native attachment persists through deselection. No writer UI changes.
	_command("attach")
	await _frames()
	var attached := _connections(_player())
	_check(attached.size() >= 3, "actual native AnimationPlayerEditor connections")
	var identified := false
	for entry in attached:
		identified = identified or (entry.class == "AnimationPlayerEditor" and entry.custom and entry.signal == "animation_list_changed" and entry.flags == CONNECT_DEFERRED)
	_check(identified, "actual native CustomCallable receiver and deferred connection identified")
	_reject("LAB_ANIMATION_EDITOR_BUSY", "native editor attached")
	_check(_pin(true), "native pin control activates")
	_command("root")
	await _frames()
	_reject("LAB_ANIMATION_EDITOR_BUSY", "pinned native editor with root selected")
	_check(_pin(false), "native unpin control activates")
	_reject("LAB_ANIMATION_EDITOR_BUSY", "unpin and root selection alone remain unsafe")
	_check(_hide_animation_panel(), "normal Output panel recovery")
	_check(not _connections(_player()).is_empty(), "hiding panel alone remains attached")
	_check(_shortcut(KEY_W, true), "native close clean rig for recovery")
	await _frames()
	_check(_root() == null, "normal editor really closed scene")
	EditorInterface.open_scene_from_path(LAB)
	await _frames()
	_select(_root())
	await _frames()
	_check(_connections(_player()).is_empty(), "hidden-panel close/reopen yields genuine detachment")
	await _cycle("native recovery")
	# Queue an actual native callback, retarget its receiver, then prove drain.
	_command("retarget")
	_check(_connections(_player()).is_empty(), "real native retarget disconnected target")
	_reject("LAB_ANIMATION_EDITOR_SETTLING", "same normal-pass retarget")
	var quiet_before: int = _plugin()._writer._animation_quiet_frame
	_plugin()._process(0.0)
	_plugin()._bridge.poll()
	_check(_plugin()._writer._animation_quiet_frame == quiet_before, "recursive plugin process and bridge poll cannot manufacture a later normal pass")
	for _index in range(3):
		_reject("LAB_ANIMATION_EDITOR_SETTLING", "same-pass recursion cannot mature")
	await _frames(1)
	_reject("LAB_ANIMATION_EDITOR_SETTLING", "first genuine quiet normal pass")
	await _frames(4)
	_check(not _sentinels.is_empty() and _sentinels[-1].other_assigned == "bend_tip", "old disconnected native callback drained and affected retargeted receiver before sentinel")
	_check(_player().assigned_animation == &"" and _tip().rotation == 0.0, "old callback did not mutate protected lab")
	await _cycle("queued old native callback settled")
	# Remove only disposable observer controls before persistence/export controls.
	_root().remove_child(_other)
	_other.free()
	_other = null
	await _frames()
	# Preserve resource identity across plugin reload, save-point Undo/Redo, reopen.
	reply = _write()
	_check(reply.ok, "persistence writer success")
	await _frames()
	var library_ref: WeakRef = weakref(_player().get_animation_library(&""))
	var animation_ref: WeakRef = weakref(_player().get_animation(&"bend_tip"))
	_save("explicit disposable animation save")
	await _frames()
	var saved := FileAccess.get_sha256(LAB)
	_check(not _dirty() and saved != baseline, "only explicit save persists animation")
	_check(_shortcut(KEY_Z), "native Undo after animation Save")
	await _frames()
	_check(_dirty() and _player().get_animation_library_list().is_empty(), "Undo saved animation becomes dirty")
	await _reload("history-owned detached resources")
	_check(library_ref.get_ref() != null and animation_ref.get_ref() != null, "native history retains resources through writer/plugin reload")
	_check(_shortcut(KEY_Z, true), "native Redo after plugin reload")
	await _frames()
	_assert_recipe("reload Redo")
	_check(not _dirty() and _player().get_animation_library(&"") == library_ref.get_ref() and _player().get_animation(&"bend_tip") == animation_ref.get_ref(), "reload Redo same instances and saved clean point")
	_check(_hide_animation_panel(), "hide native Animation panel before persistence reopen")
	_check(_shortcut(KEY_W, true), "native close saved animation")
	await _frames()
	_check(_root() == null and library_ref.get_ref() == null and animation_ref.get_ref() == null, "scene close releases history-owned native resources")
	EditorInterface.open_scene_from_path(LAB)
	await _frames()
	_select(_root())
	await _frames()
	_assert_recipe("saved reopened animation")
	_check(not _dirty() and FileAccess.get_sha256(LAB) == saved, "reopened persistence clean and saved bytes unchanged")
	# Return to empty AnimationPlayer in this disposable scene for fault tests.
	var manager := get_undo_redo()
	var persisted := _player().get_animation_library(&"")
	manager.create_action("Fixture: remove persisted animation", UndoRedo.MERGE_DISABLE, _root())
	manager.add_do_method(_player(), &"remove_animation_library", &"")
	manager.add_undo_method(_player(), &"add_animation_library", &"", persisted)
	manager.commit_action()
	persisted = null
	_save("explicit save empty player fault baseline")
	await _frames()
	var old_writer: RefCounted = _plugin()._writer
	_plugin()._writer = PrepareFailure.new(_plugin()._session_id)
	await _frames()
	_reject("RIG_LAB_ANIMATION_BUILD_FAILED", "strict detached pre-action preparation failure")
	_plugin()._writer = VerifyFailure.new(_plugin()._session_id)
	await _frames()
	var before := _history_state()
	reply = _write()
	_check(not reply.ok and reply.error.code == "WRITE_OUTCOME_UNKNOWN", "post-action verification fault is uncertain")
	_check(_plugin()._writer._faulted and not _plugin()._writer._active, "post-action fault latches shared session fence and releases active guard")
	_check(_history_state()[2] == before[1] + 2 and _player().has_animation(&"bend_tip"), "fault does not pretend to undo committed action")
	_reject("WRITE_OUTCOME_UNKNOWN", "fault rejects second animation write")
	var rig_fault := _write("godot_create_rig_lab")
	_check(not rig_fault.ok and rig_fault.error.code == "WRITE_OUTCOME_UNKNOWN", "shared fault also rejects v2 writer")
	_check(_plugin()._dispatch("godot_ping", {}).ok and _plugin()._dispatch("godot_inspect_scene", {}).ok, "reads remain healthy after fault")
	_check(_shortcut(KEY_Z), "native user Undo after fault")
	await _frames()
	await _reload("fault session recovery")
	await _frames()
	_plugin()._writer = ResponseFailure.new(_plugin()._session_id)
	await _frames()
	reply = _write()
	_check(not reply.ok and reply.error.code == "WRITE_OUTCOME_UNKNOWN", "malformed animation result is uncertain after action")
	_check(_plugin()._writer._faulted and not _plugin()._writer._active, "malformed animation result latches shared fault and releases guard")
	_reject("WRITE_OUTCOME_UNKNOWN", "malformed animation result disables both writers")
	_check(_shortcut(KEY_Z), "native Undo malformed response action")
	await _frames()
	await _reload("malformed response session recovery")
	reply = _write()
	_check(reply.ok, "fresh-session animation Create after manual inspection Undo")
	await _frames()
	_check(_shortcut(KEY_Z), "characterization native Undo while detached")
	await _frames()
	_command("attach")
	await _frames()
	_check(not _connections(_player()).is_empty(), "characterization user attaches editor before Redo")
	_check(_shortcut(KEY_Z, true), "characterization normal native Redo unaffected by MCP")
	await _frames()
	_check(_player().has_animation(&"bend_tip") and _player().assigned_animation == &"bend_tip", "native attached Redo observer assigns bend_tip after frames")
	print("GODOT_MCP_ANIMATION_ATTACHED_REDO=", JSON.stringify({"assigned": _player().assigned_animation, "current": _player().current_animation, "playing": _player().is_playing(), "rotation": _tip().rotation}))
	# Persist accepted public fixture artifact only through an explicit editor save.
	_save("explicit final export-control fixture save")
	await _frames()
	_check(_plugin()._dispatch("godot_ping", {}).result.plugin_version == "0.4.0", "intentional live plugin version")
	_finish()


func _finish() -> void:
	print("GODOT_MCP_ANIMATION_EDITOR_CHECKS=%d FAILURES=%d" % [_checks, _failures])
	get_tree().quit(1 if _failures else 0)


func _plugin() -> EditorPlugin:
	for node in get_tree().root.find_children("*", "EditorPlugin", true, false):
		var script: Script = node.get_script()
		if script != null and script.resource_path in ["res://addons/lunitora_godot/plugin.gd", "res://addons/lunitora_godot/native_editor_transport.gd", "res://addons/lunitora_godot/native_animation_plugin.gd"]:
			return node
	return null


func _root() -> Node:
	return EditorInterface.get_edited_scene_root()


func _player() -> AnimationPlayer:
	var scene := _root()
	return scene.get_node_or_null("TotolinaRigV2/AnimationPlayer") if scene != null else null


func _tip() -> Bone2D:
	var scene := _root()
	return scene.get_node_or_null("TotolinaRigV2/Skeleton2D/Root/Tip") as Bone2D if scene != null else null


func _connections(player: AnimationPlayer) -> Array[Dictionary]:
	var values: Array[Dictionary] = []
	if player == null:
		return values
	for signal_name in SIGNALS:
		for entry in player.get_signal_connection_list(signal_name):
			var callback: Callable = entry.callable
			var receiver := callback.get_object()
			values.append({"signal": signal_name, "method": callback.get_method(),
				"custom": callback.is_custom(), "object": callback.get_object_id(),
				"class": receiver.get_class() if receiver != null else "null", "flags": entry.flags})
	return values


func _storage(object: Object) -> Dictionary:
	var values := {}
	for entry in object.get_property_list():
		if entry.usage & PROPERTY_USAGE_STORAGE:
			values[entry.name] = object.get(entry.name)
	return values


func _snapshot() -> Dictionary:
	var values := {}
	var scene := _root()
	if scene == null:
		return values
	var pending: Array[Node] = [scene]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		values[str(scene.get_path_to(node))] = {"id": node.get_instance_id(), "class": node.get_class(),
			"owner": node.owner.get_instance_id() if node.owner != null else 0,
			"script": node.get_script() != null, "properties": _storage(node)}
		for child in node.get_children(true):
			pending.append(child)
	return values


func _recipe(player: AnimationPlayer) -> Dictionary:
	var values := {"libraries": [], "animations": [], "tracks": [], "markers": []}
	if player == null:
		return values
	values.libraries = player.get_animation_library_list()
	values.animations = player.get_animation_list()
	values.assigned = player.assigned_animation
	values.current = player.current_animation
	values.playing = player.is_playing()
	values.autoplay = player.autoplay
	values.queue = player.get_queue()
	values.root_node = player.root_node
	values.root_resolves = player.get_node_or_null(player.root_node) == _root().get_node_or_null("TotolinaRigV2")
	values.storage = _storage(player)
	if _tip() != null:
		values.tip_transform = _tip().transform
		values.tip_rest = _tip().rest
		values.tip_rotation = _tip().rotation
	if not player.has_animation_library(&"") or not player.has_animation(&"bend_tip"):
		return values
	var library := player.get_animation_library(&"")
	var animation := library.get_animation(&"bend_tip")
	values.library_id = library.get_instance_id()
	values.animation_id = animation.get_instance_id()
	values.length = animation.length
	values.step = animation.step
	values.loop_mode = animation.loop_mode
	values.markers = animation.get_marker_names()
	values.reset = player.has_animation(&"RESET")
	for index in range(animation.get_track_count()):
		var track := {"type": animation.track_get_type(index), "path": animation.track_get_path(index),
			"interpolation": animation.track_get_interpolation_type(index),
			"enabled": animation.track_is_enabled(index), "imported": animation.track_is_imported(index),
			"loop_wrap": animation.track_get_interpolation_loop_wrap(index), "keys": []}
		if animation.track_get_type(index) == Animation.TYPE_VALUE:
			track.update = animation.value_track_get_update_mode(index)
			track.samples = [animation.value_track_interpolate(index, 0.25), animation.value_track_interpolate(index, 0.75)]
		for key in range(animation.track_get_key_count(index)):
			track.keys.append({"time": animation.track_get_key_time(index, key),
				"value": animation.track_get_key_value(index, key), "value_type": typeof(animation.track_get_key_value(index, key)),
				"transition": animation.track_get_key_transition(index, key)})
		values.tracks.append(track)
	return values


func _shortcut(key: Key, shift := false) -> bool:
	var event := InputEventKey.new()
	event.keycode = key
	event.ctrl_pressed = true
	event.shift_pressed = shift
	event.pressed = true
	for candidate in get_tree().root.find_children("*", "PopupMenu", true, false):
		var menu: PopupMenu = candidate
		var native := false
		for entry in menu.get_signal_connection_list(&"id_pressed"):
			var receiver: Object = entry.callable.get_object()
			native = native or (receiver != null and receiver.get_class() == "EditorNode")
		var undo := false
		var redo := false
		for index in range(menu.item_count):
			undo = undo or menu.get_item_text(index) == "Undo"
			redo = redo or menu.get_item_text(index) == "Redo"
		if native and undo and redo:
			menu.about_to_popup.emit()
			if menu.activate_item_by_event(event, false):
				return true
	return false


func _select(node: Node) -> void:
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(node)
	EditorInterface.edit_node(node)


func _hide_animation_panel() -> bool:
	for node in get_tree().root.find_children("*", "TabContainer", true, false):
		if node.get_class() == "EditorBottomPanel":
			for index in range(node.get_tab_count()):
				if node.get_tab_title(index) == "Output":
					node.current_tab = index
					return true
	return false


func _pin(value: bool) -> bool:
	for node in get_tree().root.find_children("*", "Button", true, false):
		if node.tooltip_text == "Pin AnimationPlayer":
			node.button_pressed = value
			node.pressed.emit()
			return node.button_pressed == value
	return false


func _during_commit() -> void:
	_reentrant_results.append(_write())
	_reentrant_results.append(_write("godot_create_rig_lab"))


func _observer() -> void:
	pass


func _sentinel(label: String) -> void:
	_sentinels.append({"label": label, "frame": Engine.get_process_frames(),
		"assigned": _player().assigned_animation if _player() != null else "gone",
		"other_assigned": _other.assigned_animation if is_instance_valid(_other) else "gone"})


func _command(command: String) -> void:
	_command_ok = true
	match command:
		"save":
			EditorInterface.save_scene_as(LAB, false)
			_saved_hash = FileAccess.get_sha256(LAB)
		"undo": _command_ok = _shortcut(KEY_Z)
		"redo": _command_ok = _shortcut(KEY_Z, true)
		"close": _command_ok = _shortcut(KEY_W, true)
		"open": EditorInterface.open_scene_from_path(LAB)
		"attach": _select(_player())
		"root": _select(_root())
		"hide": _command_ok = _hide_animation_panel()
		"pin": _command_ok = _pin(true)
		"unpin": _command_ok = _pin(false)
		"retain":
			_retained_library = weakref(_player().get_animation_library(&""))
			_retained_animation = weakref(_player().get_animation(&"bend_tip"))
		"dirty":
			var manager := get_undo_redo()
			manager.create_action("Fixture: unrelated dirty edit", UndoRedo.MERGE_DISABLE, _root())
			manager.add_do_property(_root(), &"position", Vector2(7, 9))
			manager.add_undo_property(_root(), &"position", Vector2.ZERO)
			manager.commit_action()
		"wrong_root": _root().name = "WrongLabRoot"
		"restore_root": _root().name = "TotolinaRigLab"
		"modified_tip": _tip().rest = Transform2D(0.1, Vector2(64, 0))
		"restore_tip": _tip().rest = Transform2D(0.0, Vector2(64, 0))
		"wrong_owner": _tip().owner = null
		"restore_owner": _tip().owner = _root()
		"script_tip":
			var script := GDScript.new()
			script.source_code = "@tool\nextends Bone2D\n"
			_command_ok = script.reload() == OK
			_tip().set_script(script)
		"restore_script": _tip().set_script(null)
		"wrong_class":
			_removed_tip = _tip()
			var parent := _removed_tip.get_parent()
			parent.remove_child(_removed_tip)
			var replacement := Node2D.new()
			replacement.name = "Tip"
			replacement.transform = Transform2D(0.0, Vector2(64, 0))
			parent.add_child(replacement)
			replacement.owner = _root()
		"restore_class":
			var replacement := _root().get_node("TotolinaRigV2/Skeleton2D/Root/Tip")
			var parent := replacement.get_parent()
			parent.remove_child(replacement)
			replacement.free()
			parent.add_child(_removed_tip)
			_removed_tip.owner = _root()
			_removed_tip = null
		"wrong_path": _player().root_node = NodePath(".")
		"restore_path": _player().root_node = NodePath("..")
		"speed": _player().speed_scale = 2.0
		"restore_speed": _player().speed_scale = 1.0
		"empty_library": _command_ok = _player().add_animation_library(&"", AnimationLibrary.new()) == OK
		"remove_library": _player().remove_animation_library(&"")
		"observer":
			_player().animation_list_changed.connect(_observer)
			_unclassified = true
		"remove_observer":
			_player().animation_list_changed.disconnect(_observer)
			_unclassified = false
		"reload":
			_old_session = _plugin()._session_id
			EditorInterface.set_plugin_enabled("lunitora_godot", false)
			EditorInterface.set_plugin_enabled("lunitora_godot", true)
		"retarget":
			if not is_instance_valid(_other):
				_other = AnimationPlayer.new()
				_other.name = "ObserverControlPlayer"
				_other.root_node = NodePath(".")
				_root().add_child(_other)
				_other.owner = _root()
				var target := Node2D.new()
				target.name = "ControlTip"
				_other.add_child(target)
				target.owner = _root()
			_select(_player())
			_player().animation_list_changed.emit()
			_sentinel.call_deferred("old native callback retarget")
			_select(_other)
			var animation := Animation.new()
			animation.length = 1.0
			var track := animation.add_track(Animation.TYPE_VALUE)
			animation.track_set_path(track, NodePath("ControlTip:rotation"))
			animation.track_insert_key(track, 0.0, 0.0)
			animation.track_insert_key(track, 1.0, ANGLE)
			var library := AnimationLibrary.new()
			library.add_animation(&"bend_tip", animation)
			_command_ok = _other.add_animation_library(&"", library) == OK
		"same_pass":
			var plugin := _plugin()
			for index in range(3):
				_observations.append(plugin._dispatch("godot_create_rig_lab_animation", {},
					Crypto.new().generate_random_bytes(16).hex_encode(), plugin._session_id, true))
		"retarget_on_write": _retarget_next_write = true
		"snapshot": pass
		"quit": get_tree().quit()
		_: _command_ok = false


func _process(_delta: float) -> void:
	if not _pending_ack.is_empty():
		_countdown -= 1
		if _countdown <= 0:
			_ack = _pending_ack
			_pending_ack = ""
	if _pending_ack.is_empty() and FileAccess.file_exists("res://.godot/animation_control.json"):
		var packet: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://.godot/animation_control.json"))
		if packet is Dictionary:
			DirAccess.remove_absolute(ProjectSettings.globalize_path("res://.godot/animation_control.json"))
			_command(packet.command)
			_pending_ack = packet.id
			_countdown = int(packet.get("frames", 8))
	_evidence()


func _evidence() -> void:
	var plugin := _plugin()
	if plugin == null:
		return
	var scene := _root()
	var player := _player()
	var manager := get_undo_redo()
	var history: UndoRedo = manager.get_history_undo_redo(manager.get_object_history_id(scene)) if scene != null else null
	var names: Array[String] = []
	if history != null:
		for index in range(history.get_history_count()):
			names.append(history.get_action_name(index))
	var data := {"ack": _ack, "ok": _command_ok, "frame": Engine.get_process_frames(),
		"display": DisplayServer.get_name(), "version": Engine.get_version_info().string,
		"session": plugin._session_id, "old_session": _old_session,
		"root": scene.get_instance_id() if scene != null else 0,
		"scene": scene.scene_file_path if scene != null else "",
		"dirty": EditorInterface.get_unsaved_scenes().has(LAB),
		"connections": _connections(player), "recipe": _recipe(player), "snapshot": _snapshot(),
		"history": [history.get_version(), history.get_current_action(), history.get_history_count(), history.has_redo(), history.has_undo(), names] if history != null else [],
		"file_hash": FileAccess.get_sha256(LAB), "saved_hash": _saved_hash,
		"retained_library": _retained_library.get_ref().get_instance_id() if _retained_library != null and _retained_library.get_ref() != null else 0,
		"retained_animation": _retained_animation.get_ref().get_instance_id() if _retained_animation != null and _retained_animation.get_ref() != null else 0,
		"sentinels": _sentinels, "observations": _observations,
		"ledger": plugin._writer._write_ids.size(), "faulted": plugin._writer._faulted, "active": plugin._writer._active,
		"quiet_frame": plugin._writer._animation_quiet_frame, "process_frame": plugin._writer._animation_process_frame,
		"in_editor_process": plugin._writer._in_editor_process}
	var encoded := JSON.stringify(data)
	if encoded == _previous:
		return
	_previous = encoded
	_sequence += 1
	var file := FileAccess.open("res://.godot/animation_evidence_%08d.json" % _sequence, FileAccess.WRITE)
	file.store_string(encoded)
	file.close()
