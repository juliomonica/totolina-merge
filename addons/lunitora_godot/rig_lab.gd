@tool
extends RefCounted
## Four fixed operations share one editor-session writer. No automatic saving.

const AnimationWriter = preload("res://addons/lunitora_godot/animation_writer.gd")
const CharacterRig = preload("res://addons/lunitora_godot/character_rig.gd")
const WRITE_OPERATIONS := ["godot_create_rig_lab", "godot_create_rig_lab_animation",
	"godot_create_tolina_rig_lab", "godot_create_tolina_lab_blink"]

const LAB_PATH := "res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"
const ROOT_NAME := "TotolinaRigLab"
const RIG_NAME := "TotolinaRigV2"
const ACTION_NAME := "Lunitora: Create Totolina Rig Lab Scaffold"
const COLOR := Color(0.25, 0.5, 1.0, 1.0)
const MAX_WRITE_IDS := 128
const MANIFEST := {
	".": "Node2D",
	"Meshes": "Node2D",
	"Meshes/TestMesh": "Polygon2D",
	"Skeleton2D": "Skeleton2D",
	"Skeleton2D/Root": "Bone2D",
	"Skeleton2D/Root/Tip": "Bone2D",
	"AnimationPlayer": "AnimationPlayer",
}

var _session_id: String
var _write_ids: Dictionary = {}
var _active := false
var _faulted := false
var _retired := false
var _action_started := false
var _animation_quiet_frame := -1
var _animation_process_frame := -1
var _in_editor_process := false
var _animation_observation: Dictionary = {}
var _tolina_context: Dictionary = {}


func _init(session_id: String) -> void:
	_session_id = session_id


func retire() -> void:
	# Transport shutdown must not free nodes retained by native editor history.
	_retired = true
	invalidate_animation_admission()


func create(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin := false) -> Dictionary:
	return _run_write(scene_root, undo_redo, expected_session_id, request_id, command_origin, "godot_create_rig_lab")


func create_animation(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin := false) -> Dictionary:
	return _run_write(scene_root, undo_redo, expected_session_id, request_id, command_origin, "godot_create_rig_lab_animation")


func create_tolina(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin := false) -> Dictionary:
	return _run_write(scene_root, undo_redo, expected_session_id, request_id, command_origin, "godot_create_tolina_rig_lab")


func create_tolina_blink(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin := false) -> Dictionary:
	return _run_write(scene_root, undo_redo, expected_session_id, request_id, command_origin, "godot_create_tolina_lab_blink")


func _run_write(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin: bool, operation: String) -> Dictionary:
	if not command_origin or not _hex_id(request_id) or operation not in WRITE_OPERATIONS:
		return _failure("INVALID_REQUEST", "The writer requires an authenticated editor command.")
	if _retired or expected_session_id != _session_id:
		return _failure("INVALID_MESSAGE", "The write belongs to a different editor session.")
	if _write_ids.has(request_id):
		return _failure("WRITE_REPLAY_REJECTED", "Duplicate write rejected; original outcome is not established.")
	if _write_ids.size() >= MAX_WRITE_IDS:
		return _failure("SESSION_WRITE_LIMIT", "The editor session write request limit has been reached.")
	# Unlike the transport's read cache, this ledger is never evicted or cleared
	# by a socket reconnect or a restart of the Python MCP owner.
	_write_ids[request_id] = "admitted"
	if _active or undo_redo == null or undo_redo.is_committing_action():
		_write_ids[request_id] = "rejected"
		return _failure("WRITE_BUSY", "A write or editor undo action is already active.")
	if _faulted:
		_write_ids[request_id] = "rejected"
		return _failure("WRITE_OUTCOME_UNKNOWN", "This editor session requires manual inspection and recovery.")
	_active = true
	_action_started = false
	# A single outer epilogue owns the flag. Inner controlled failures return to
	# here, including validation/verification and fixed response construction.
	var value: Variant
	match operation:
		"godot_create_rig_lab": value = _create_guarded(scene_root, undo_redo, expected_session_id)
		"godot_create_rig_lab_animation": value = _create_animation_guarded(scene_root, undo_redo, expected_session_id)
		"godot_create_tolina_rig_lab": value = _create_tolina_guarded(scene_root, undo_redo, expected_session_id)
		"godot_create_tolina_lab_blink": value = _create_tolina_blink_guarded(scene_root, undo_redo, expected_session_id)
	var result: Dictionary
	var valid := value is Dictionary and _valid_operation_result(value, operation)
	if not valid:
		var build_error: String = {"godot_create_rig_lab": "RIG_LAB_BUILD_FAILED",
			"godot_create_rig_lab_animation": "RIG_LAB_ANIMATION_BUILD_FAILED",
			"godot_create_tolina_rig_lab": "TOLINA_RIG_BUILD_FAILED",
			"godot_create_tolina_lab_blink": "TOLINA_BLINK_BUILD_FAILED"}[operation]
		result = _failure("WRITE_OUTCOME_UNKNOWN" if _action_started else build_error,
			"The write could not produce a verified response.")
	else:
		result = value
	if _action_started and not result.ok:
		_faulted = true
		result = _failure("WRITE_OUTCOME_UNKNOWN", "An editor action began; inspect the scene and history before recovery.")
	_write_ids[request_id] = "finished"
	_active = false
	return result


func _create_guarded(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String) -> Dictionary:
	var gate := _gate(scene_root, expected_session_id)
	if not gate.ok:
		return gate
	var rig := _prepare()
	if rig == null or not _verify_recipe(rig, null):
		if is_instance_valid(rig):
			rig.free()
		return _failure("RIG_LAB_BUILD_FAILED", "Detached rig preparation failed.")
	var history_id := undo_redo.get_object_history_id(scene_root)
	if history_id <= 0:
		rig.free()
		return _failure("RIG_LAB_BUILD_FAILED", "The lab has no editor scene history.")
	var history := undo_redo.get_history_undo_redo(history_id)
	if history == null:
		rig.free()
		return _failure("RIG_LAB_BUILD_FAILED", "The lab history is unavailable.")
	var before := {
		"history_id": history_id, "history": history,
		"version": history.get_version(), "current": history.get_current_action(),
		"count": history.get_history_count(), "max_steps": history.get_max_steps(),
		"dirty": EditorInterface.get_unsaved_scenes().has(LAB_PATH),
		"session": _session_id, "root_id": scene_root.get_instance_id(),
	}
	# The final gate is BEFORE create_action: after action creation, even an
	# uncommitted action may have discarded the previous redo branch.
	gate = _gate(scene_root, expected_session_id)
	if not gate.ok or undo_redo.is_committing_action():
		rig.free()
		return gate if not gate.ok else _failure("WRITE_BUSY", "The editor undo manager is committing an action.")
	# No await, deferred call, timer, or early return in this critical block.
	_action_started = true
	undo_redo.create_action(ACTION_NAME, UndoRedo.MERGE_DISABLE, scene_root, false, true)
	undo_redo.add_do_method(scene_root, &"add_child", rig, true)
	for path in MANIFEST:
		var node: Node = rig if path == "." else rig.get_node(NodePath(path))
		undo_redo.add_do_property(node, &"owner", scene_root)
	undo_redo.add_undo_method(scene_root, &"remove_child", rig)
	undo_redo.add_do_reference(rig)
	undo_redo.commit_action(true)
	# commit_action is void, not a transaction or proof of successful execution.
	if not _verify_after_action(scene_root, rig, before, undo_redo):
		return _failure("WRITE_OUTCOME_UNKNOWN", "Post-action verification failed; inspect the scene and history.")
	return {"ok": true, "result": _success_data(), "error": null}


func _success_data() -> Dictionary:
	return {
		"editor_session_id": _session_id,
		"project_path": _canonical_project_path(),
		"scene_path": LAB_PATH, "root_name": ROOT_NAME, "created_root": RIG_NAME,
		"created_node_count": 7, "undo_action_name": ACTION_NAME,
		"undo_actions_added": 1, "save_state": "saved_dirty",
		"auto_saved": false, "read_only": false,
	}


func _gate(root: Node, expected_session_id: String) -> Dictionary:
	var result := _root_gate(root, expected_session_id)
	if not result.ok:
		return result
	if root.has_node(NodePath(RIG_NAME)):
		return _failure("LAB_ALREADY_CREATED", "The lab already contains TotolinaRigV2.")
	return {"ok": true, "result": {}, "error": null}


func _root_gate(root: Node, expected_session_id: String) -> Dictionary:
	if _retired or expected_session_id != _session_id:
		return _failure("INVALID_MESSAGE", "The write belongs to a retired editor session.")
	if not is_instance_valid(root) or root != EditorInterface.get_edited_scene_root() or root.scene_file_path != LAB_PATH:
		return _failure("LAB_SCENE_REQUIRED", "Open the dedicated saved Totolina rig lab scene.")
	if root.name != ROOT_NAME or root.get_class() != "Node2D" or root.get_script() != null:
		return _failure("LAB_ROOT_MISMATCH", "The lab root must be the native script-free TotolinaRigLab Node2D.")
	return {"ok": true, "result": {}, "error": null}


func _prepare() -> Node2D:
	var rig := Node2D.new()
	rig.name = RIG_NAME
	var meshes := Node2D.new()
	meshes.name = "Meshes"
	rig.add_child(meshes)
	var mesh := Polygon2D.new()
	mesh.name = "TestMesh"
	mesh.color = COLOR
	mesh.polygon = _vertices()
	mesh.polygons = _triangles()
	mesh.skeleton = NodePath("../../Skeleton2D")
	mesh.add_bone(NodePath("Root"), PackedFloat32Array([1, 0.5, 0, 0, 0.5, 1]))
	mesh.add_bone(NodePath("Root/Tip"), PackedFloat32Array([0, 0.5, 1, 1, 0.5, 0]))
	meshes.add_child(mesh)
	var skeleton := Skeleton2D.new()
	skeleton.name = "Skeleton2D"
	rig.add_child(skeleton)
	var root := _bone("Root", Transform2D.IDENTITY)
	skeleton.add_child(root)
	root.add_child(_bone("Tip", Transform2D(0.0, Vector2(64, 0))))
	var player := AnimationPlayer.new()
	player.name = "AnimationPlayer"
	player.autoplay = &""
	rig.add_child(player)
	return rig


func _bone(node_name: String, pose: Transform2D) -> Bone2D:
	var bone := Bone2D.new()
	bone.name = node_name
	bone.set_autocalculate_length_and_angle(false)
	bone.set_length(64.0)
	bone.set_bone_angle(0.0)
	bone.rest = pose
	bone.transform = pose
	return bone


func _verify_after_action(root: Node, rig: Node, before: Dictionary,
		undo_redo: EditorUndoRedoManager) -> bool:
	if _retired or before.session != _session_id or not is_instance_valid(root):
		return false
	if root.get_instance_id() != before.root_id or root != EditorInterface.get_edited_scene_root():
		return false
	if root.scene_file_path != LAB_PATH or root.name != ROOT_NAME or root.get_class() != "Node2D" or root.get_script() != null:
		return false
	if not is_instance_valid(rig) or root.get_node_or_null(NodePath(RIG_NAME)) != rig or rig.get_parent() != root:
		return false
	if not _verify_recipe(rig, root) or undo_redo.get_object_history_id(root) != before.history_id:
		return false
	var history: UndoRedo = before.history
	if not is_instance_valid(history) or undo_redo.is_committing_action():
		return false
	var count: int = before.current + 2 # prefix before create, plus this action
	if before.max_steps > 0:
		count = mini(count, before.max_steps)
	return history.get_version() == before.version + 1 \
		and history.get_history_count() == count \
		and history.get_current_action() == count - 1 \
		and history.get_current_action_name() == ACTION_NAME \
		and not history.has_redo() \
		and EditorInterface.get_unsaved_scenes().has(LAB_PATH)


func _verify_recipe(rig: Node, owner_root: Node, empty_player := true) -> bool:
	if not is_instance_valid(rig) or rig.name != RIG_NAME:
		return false
	var stack: Array[Node] = [rig]
	var count := 0
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var path := String(rig.get_path_to(node))
		if not MANIFEST.has(path) or node.get_class() != MANIFEST[path] or node.get_script() != null or node.owner != owner_root:
			return false
		if node is Node2D and path != "Skeleton2D/Root/Tip" and node.transform != Transform2D.IDENTITY:
			return false
		count += 1
		for child in node.get_children(true):
			stack.append(child)
	if count != 7:
		return false
	var mesh: Polygon2D = rig.get_node("Meshes/TestMesh")
	if mesh.polygon != _vertices() or mesh.polygons != _triangles() or mesh.color != COLOR:
		return false
	if mesh.texture != null or not mesh.vertex_colors.is_empty() or mesh.skeleton != NodePath("../../Skeleton2D"):
		return false
	if mesh.get_bone_count() != 2 or mesh.get_bone_path(0) != NodePath("Root") or mesh.get_bone_path(1) != NodePath("Root/Tip"):
		return false
	if mesh.get_bone_weights(0) != PackedFloat32Array([1, 0.5, 0, 0, 0.5, 1]) or mesh.get_bone_weights(1) != PackedFloat32Array([0, 0.5, 1, 1, 0.5, 0]):
		return false
	for path in ["Skeleton2D/Root", "Skeleton2D/Root/Tip"]:
		var bone: Bone2D = rig.get_node(NodePath(path))
		var pose := Transform2D.IDENTITY if path == "Skeleton2D/Root" else Transform2D(0.0, Vector2(64, 0))
		if bone.transform != pose or bone.rest != pose or bone.get_length() != 64.0 or bone.get_bone_angle() != 0.0 or bone.get_autocalculate_length_and_angle():
			return false
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	if not empty_player:
		return true
	return player.get_animation_library_list().is_empty() and player.get_animation_list().is_empty() \
		and not player.has_animation_library(&"") and not player.has_animation(&"RESET") \
		and player.autoplay == &"" and player.assigned_animation == &"" \
		and player.current_animation == &"" and not player.is_playing()


func _vertices() -> PackedVector2Array:
	return PackedVector2Array([Vector2(0, -12), Vector2(64, -12), Vector2(128, -12),
		Vector2(128, 12), Vector2(64, 12), Vector2(0, 12)])


func invalidate_animation_admission() -> void:
	_animation_quiet_frame = -1
	_animation_observation = {}


func begin_editor_process(scene_root: Node, frame: int) -> void:
	# Only the plugin's normal process pass supplies this context. Re-entry and
	# same-frame polling cannot turn a first quiet sample into a later sample.
	if _in_editor_process:
		return
	_in_editor_process = true
	_animation_process_frame = frame
	var observation := _animation_signature(scene_root)
	if observation.is_empty():
		invalidate_animation_admission()
	elif observation != _animation_observation:
		_animation_observation = observation
		_animation_quiet_frame = frame


func end_editor_process() -> void:
	_in_editor_process = false


func _animation_signature(root: Node) -> Dictionary:
	var tolina := is_instance_valid(root) and root.scene_file_path == CharacterRig.LAB_PATH
	if not (_tolina_root_gate(root, _session_id) if tolina else _root_gate(root, _session_id)).ok:
		return {}
	var rig := root.get_node_or_null(NodePath(CharacterRig.RIG_NAME if tolina else RIG_NAME))
	if rig == null:
		return {}
	if tolina and _tolina_context.is_empty():
		var context: Dictionary = CharacterRig.read_spec()
		if not context.ok:
			return {}
		_tolina_context = context
	if rig == null or not (CharacterRig.verify(rig, root, _tolina_context.spec, _tolina_context.textures, false) if tolina else _verify_recipe(rig, root, false)):
		return {}
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	if not AnimationWriter.observers(player).is_empty():
		return {}
	var inspected := EditorInterface.get_inspector().get_edited_object()
	var selected: Array = []
	for node in EditorInterface.get_selection().get_selected_nodes():
		selected.append(node.get_instance_id())
	return {"session": _session_id, "root": root.get_instance_id(),
		"rig": rig.get_instance_id(), "player": player.get_instance_id(),
		"scene": root.scene_file_path, "state": AnimationWriter.scene_state(root, player),
		"player_state": AnimationWriter.player_state(player),
		"libraries": player.get_animation_library_list(), "animations": player.get_animation_list(),
		"selected": selected, "inspected": inspected.get_instance_id() if is_instance_valid(inspected) else 0}


func _animation_gate(root: Node, expected_session_id: String) -> Dictionary:
	var gate := _root_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var rig := root.get_node_or_null(NodePath(RIG_NAME))
	if rig == null:
		return _failure("LAB_RIG_REQUIRED", "Create the v0.2 rig fixture first.")
	if not _verify_recipe(rig, root, false):
		return _failure("LAB_RIG_MISMATCH", "The lab must contain the exact native v0.2 rig fixture at rest.")
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	var tip: Bone2D = rig.get_node("Skeleton2D/Root/Tip")
	if player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig or rig.get_node_or_null(NodePath("Skeleton2D/Root/Tip")) != tip:
		return _failure("LAB_RIG_MISMATCH", "The animation root and target must resolve to the exact rig and Tip bone.")
	if not AnimationWriter.observers(player).is_empty():
		invalidate_animation_admission()
		return _failure("LAB_ANIMATION_EDITOR_BUSY", "AnimationPlayer editor or an unclassified observer is attached. Unpin, switch away from Animation, save manually if needed, then close/reopen the lab with that panel hidden.")
	if player.has_animation(AnimationWriter.NAME):
		return _failure("LAB_ANIMATION_ALREADY_CREATED", "The lab already contains bend_tip.")
	if not player.get_animation_library_list().is_empty() or not player.get_animation_list().is_empty() or not AnimationWriter.pristine(player):
		return _failure("LAB_ANIMATION_CONFLICT", "The player must have no libraries, animations, assignment, playback or queue and retain native playback defaults.")
	if not _in_editor_process or _animation_process_frame != Engine.get_process_frames() or _animation_quiet_frame < 0 or _animation_process_frame <= _animation_quiet_frame or _animation_signature(root) != _animation_observation:
		return _failure("LAB_ANIMATION_EDITOR_SETTLING", "The lab requires two stable normal editor process observations; wait for editor settlement before a fresh request.")
	return {"ok": true, "result": {}, "error": null}


func _prepare_animation() -> AnimationLibrary:
	return AnimationWriter.prepare()


func _verify_animation_recipe(library: AnimationLibrary) -> String:
	return AnimationWriter.verify(library)


func _create_animation_guarded(root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String) -> Dictionary:
	var gate := _animation_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var library := _prepare_animation()
	if library == null or not _verify_animation_recipe(library).is_empty():
		return _failure("RIG_LAB_ANIMATION_BUILD_FAILED", "Detached animation preparation failed.")
	var history_id := undo_redo.get_object_history_id(root)
	var history := undo_redo.get_history_undo_redo(history_id) if history_id > 0 else null
	if history == null:
		return _failure("RIG_LAB_ANIMATION_BUILD_FAILED", "The lab has no available editor scene history.")
	var rig := root.get_node(NodePath(RIG_NAME))
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	var tip: Bone2D = rig.get_node("Skeleton2D/Root/Tip")
	var before := {
		"history_id": history_id, "history": history, "version": history.get_version(),
		"current": history.get_current_action(), "count": history.get_history_count(),
		"max_steps": history.get_max_steps(), "session": _session_id,
		"root_id": root.get_instance_id(), "rig_id": rig.get_instance_id(),
		"player_id": player.get_instance_id(), "tip_id": tip.get_instance_id(),
		"scene_state": AnimationWriter.scene_state(root, player),
		"player_state": AnimationWriter.player_state(player),
		"animation": library.get_animation(AnimationWriter.NAME),
	}
	# Everything from this final check through the shared outer epilogue is
	# synchronous. The boundary is create_action, not commit_action.
	gate = _animation_gate(root, expected_session_id)
	if not gate.ok or undo_redo.is_committing_action():
		return gate if not gate.ok else _failure("WRITE_BUSY", "The editor undo manager is committing an action.")
	_action_started = true
	undo_redo.create_action(AnimationWriter.ACTION_NAME, UndoRedo.MERGE_DISABLE, root, false, true)
	# Bound Variant arguments in native UndoRedo retain these RefCounted
	# resources. Do NOT register node-only do/undo references or free them.
	undo_redo.add_do_method(player, &"add_animation_library", &"", library)
	undo_redo.add_undo_method(player, &"remove_animation_library", &"")
	undo_redo.commit_action(true)
	if not _verify_animation_after_action(root, rig, player, tip, library, before, undo_redo):
		return _failure("WRITE_OUTCOME_UNKNOWN", "Post-action animation verification failed; inspect scene and history.")
	return {"ok": true, "result": _animation_success_data(), "error": null}


func _verify_animation_after_action(root: Node, rig: Node, player: AnimationPlayer,
		tip: Bone2D, library: AnimationLibrary, before: Dictionary,
		undo_redo: EditorUndoRedoManager) -> bool:
	if not _root_gate(root, before.session).ok or undo_redo.is_committing_action():
		return false
	for pair in [[root, before.root_id], [rig, before.rig_id], [player, before.player_id], [tip, before.tip_id]]:
		if not is_instance_valid(pair[0]) or pair[0].get_instance_id() != pair[1]:
			return false
	if root.get_node_or_null(NodePath(RIG_NAME)) != rig or not _verify_recipe(rig, root, false):
		return false
	if player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig or rig.get_node_or_null(NodePath("Skeleton2D/Root/Tip")) != tip:
		return false
	var libraries := player.get_animation_library_list()
	var names := player.get_animation_list()
	if libraries.size() != 1 or libraries[0] != &"" or names.size() != 1 or names[0] != AnimationWriter.NAME:
		return false
	if player.get_animation_library(&"") != library or player.get_animation(AnimationWriter.NAME) != before.animation or not _verify_animation_recipe(library).is_empty():
		return false
	if not AnimationWriter.observers(player).is_empty() or not AnimationWriter.pristine(player) or AnimationWriter.player_state(player) != before.player_state or AnimationWriter.scene_state(root, player) != before.scene_state:
		return false
	if undo_redo.get_object_history_id(root) != before.history_id:
		return false
	var history: UndoRedo = before.history
	if not is_instance_valid(history):
		return false
	var count: int = before.current + 2
	if before.max_steps > 0:
		count = mini(count, before.max_steps)
	return history.get_version() == before.version + 1 and history.get_history_count() == count \
		and history.get_current_action() == count - 1 \
		and history.get_current_action_name() == AnimationWriter.ACTION_NAME \
		and not history.has_redo() and EditorInterface.get_unsaved_scenes().has(LAB_PATH)


func _animation_success_data() -> Dictionary:
	return {"editor_session_id": _session_id, "project_path": _canonical_project_path(),
		"scene_path": LAB_PATH, "root_name": ROOT_NAME,
		"animation_player_path": "TotolinaRigV2/AnimationPlayer", "library_name": "",
		"animation_name": "bend_tip", "animation_key": "bend_tip", "length_seconds": 1.0,
		"track_count": 1, "key_count": 3, "undo_action_name": AnimationWriter.ACTION_NAME,
		"undo_actions_added": 1, "save_state": "saved_dirty", "auto_saved": false, "read_only": false}


func _valid_animation_result(value: Dictionary) -> bool:
	if value.size() != 3 or not value.get("ok") is bool or not value.has("result") or not value.has("error"):
		return false
	if not value.get("ok", false):
		return _valid_result(value)
	return value.size() == 3 and value.has("error") and value.error == null \
		and value.get("result") is Dictionary and value.result == _animation_success_data() \
		and typeof(value.result.track_count) == TYPE_INT and typeof(value.result.key_count) == TYPE_INT \
		and typeof(value.result.undo_actions_added) == TYPE_INT and typeof(value.result.length_seconds) == TYPE_FLOAT


func _triangles() -> Array:
	return [PackedInt32Array([0, 1, 5]), PackedInt32Array([1, 4, 5]),
		PackedInt32Array([1, 2, 4]), PackedInt32Array([2, 3, 4])]


func _tolina_root_gate(root: Node, expected_session_id: String) -> Dictionary:
	if _retired or expected_session_id != _session_id:
		return _failure("INVALID_MESSAGE", "The write belongs to a retired editor session.")
	if not is_instance_valid(root) or root != EditorInterface.get_edited_scene_root() or root.scene_file_path != CharacterRig.LAB_PATH:
		return _failure("LAB_SCENE_REQUIRED", "Open the dedicated saved Tolina character rig lab scene.")
	if root.name != CharacterRig.ROOT_NAME or root.get_class() != "Node2D" or root.get_script() != null:
		return _failure("LAB_ROOT_MISMATCH", "The lab root must be the native script-free TolinaCharacterRigLab Node2D.")
	return {"ok": true, "result": {}, "error": null}


func _tolina_gate(root: Node, expected_session_id: String) -> Dictionary:
	var gate := _tolina_root_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	if root.has_node(NodePath(CharacterRig.RIG_NAME)):
		return _failure("LAB_ALREADY_CREATED", "The lab already contains TolinaRig.")
	return gate


func _tolina_preflight() -> Dictionary:
	var context: Dictionary = CharacterRig.read_spec()
	if not context.ok:
		return _failure(context.error.code, context.error.message)
	_tolina_context = context
	return {"ok": true, "result": context, "error": null}


func _tolina_history_before(root: Node, undo_redo: EditorUndoRedoManager) -> Dictionary:
	var history_id := undo_redo.get_object_history_id(root)
	var history := undo_redo.get_history_undo_redo(history_id) if history_id > 0 else null
	if history == null:
		return {}
	return {"history_id": history_id, "history": history, "version": history.get_version(),
		"current": history.get_current_action(), "count": history.get_history_count(),
		"max_steps": history.get_max_steps(), "session": _session_id,
		"root_id": root.get_instance_id()}


func _tolina_history_after(root: Node, before: Dictionary,
		undo_redo: EditorUndoRedoManager, action: String) -> bool:
	if not _tolina_root_gate(root, before.session).ok or root.get_instance_id() != before.root_id or undo_redo.is_committing_action() or undo_redo.get_object_history_id(root) != before.history_id:
		return false
	var history: UndoRedo = before.history
	if not is_instance_valid(history):
		return false
	var count: int = before.current + 2
	if before.max_steps > 0:
		count = mini(count, before.max_steps)
	return history.get_version() == before.version + 1 and history.get_history_count() == count \
		and history.get_current_action() == count - 1 and history.get_current_action_name() == action \
		and not history.has_redo() and EditorInterface.get_unsaved_scenes().has(CharacterRig.LAB_PATH)


func _create_tolina_guarded(root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String) -> Dictionary:
	var gate := _tolina_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var preflight := _tolina_preflight()
	if not preflight.ok:
		return preflight
	var context: Dictionary = preflight.result
	var textures_before: Dictionary = CharacterRig.resource_states(context.textures)
	var rig: Node2D = CharacterRig.prepare(context.spec, context.textures)
	if rig == null or not CharacterRig.verify(rig, null, context.spec, context.textures):
		if is_instance_valid(rig):
			rig.free()
		return _failure("TOLINA_RIG_BUILD_FAILED", "Detached Tolina rig preparation failed.")
	var before := _tolina_history_before(root, undo_redo)
	if before.is_empty():
		rig.free()
		return _failure("TOLINA_RIG_BUILD_FAILED", "The lab has no available editor scene history.")
	before.scene_state = AnimationWriter.scene_state(root, null)
	before.textures = textures_before
	before.context = context
	# A fresh, bounded specification/asset read is part of the final synchronous
	# boundary. Cached normal-process observations never replace this validation.
	preflight = _tolina_preflight()
	gate = _tolina_gate(root, expected_session_id)
	if not preflight.ok or not gate.ok or undo_redo.is_committing_action() or CharacterRig.resource_states(context.textures) != textures_before or not CharacterRig.verify(rig, null, context.spec, context.textures):
		rig.free()
		if not preflight.ok:
			return preflight
		return gate if not gate.ok else _failure("WRITE_BUSY" if undo_redo.is_committing_action() else "TOLINA_RIG_BUILD_FAILED", "Final detached rig or resource validation failed.")
	_action_started = true
	undo_redo.create_action(CharacterRig.ACTION_NAME, UndoRedo.MERGE_DISABLE, root, false, true)
	undo_redo.add_do_method(root, &"add_child", rig, true)
	for path in CharacterRig.MANIFEST:
		var node: Node = rig if path == "." else rig.get_node(NodePath(path))
		undo_redo.add_do_property(node, &"owner", root)
	undo_redo.add_undo_method(root, &"remove_child", rig)
	undo_redo.add_do_reference(rig)
	undo_redo.commit_action(true)
	if not _verify_tolina_after_action(root, rig, before, undo_redo):
		return _failure("WRITE_OUTCOME_UNKNOWN", "Post-action Tolina rig verification failed; inspect the scene and history.")
	return {"ok": true, "result": _tolina_success_data(), "error": null}


func _verify_tolina_after_action(root: Node, rig: Node, before: Dictionary,
		undo_redo: EditorUndoRedoManager) -> bool:
	if not _tolina_history_after(root, before, undo_redo, CharacterRig.ACTION_NAME):
		return false
	if not is_instance_valid(rig) or root.get_node_or_null(NodePath(CharacterRig.RIG_NAME)) != rig or rig.get_parent() != root or not CharacterRig.verify(rig, root, before.context.spec, before.context.textures):
		return false
	var original: Array = []
	for row in AnimationWriter.scene_state(root, null):
		var node := instance_from_id(row.id) as Node
		if node != rig and not rig.is_ancestor_of(node):
			original.append(row)
	return original == before.scene_state and CharacterRig.resource_states(before.context.textures) == before.textures and CharacterRig.verify_asset_files(before.context.spec)


func _tolina_animation_gate(root: Node, expected_session_id: String) -> Dictionary:
	var gate := _tolina_root_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var rig := root.get_node_or_null(NodePath(CharacterRig.RIG_NAME))
	if rig == null:
		return _failure("LAB_RIG_REQUIRED", "Create the reviewed Tolina rig fixture first.")
	if _tolina_context.is_empty() or not CharacterRig.verify(rig, root, _tolina_context.spec, _tolina_context.textures, false) or not CharacterRig.verify_blink_targets(rig):
		return _failure("LAB_RIG_MISMATCH", "The lab must contain the exact native Tolina fixture at rest with resolved alpha targets.")
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	if not AnimationWriter.observers(player).is_empty():
		invalidate_animation_admission()
		return _failure("LAB_ANIMATION_EDITOR_BUSY", "AnimationPlayer editor or an unclassified observer is attached. Unpin and close/reopen the lab with the Animation panel hidden.")
	if player.has_animation(CharacterRig.BLINK_NAME):
		return _failure("LAB_ANIMATION_ALREADY_CREATED", "The lab already contains blink.")
	if not player.get_animation_library_list().is_empty() or not player.get_animation_list().is_empty() or not AnimationWriter.pristine(player):
		return _failure("LAB_ANIMATION_CONFLICT", "The player must have no libraries, animation assignment, playback or queue and retain native defaults.")
	if not _in_editor_process or _animation_process_frame != Engine.get_process_frames() or _animation_quiet_frame < 0 or _animation_process_frame <= _animation_quiet_frame or _animation_signature(root) != _animation_observation:
		return _failure("LAB_ANIMATION_EDITOR_SETTLING", "The lab requires two stable normal editor process observations before a fresh request.")
	return {"ok": true, "result": {}, "error": null}


func _create_tolina_blink_guarded(root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String) -> Dictionary:
	var gate := _tolina_root_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var preflight := _tolina_preflight()
	if not preflight.ok:
		return preflight
	gate = _tolina_animation_gate(root, expected_session_id)
	if not gate.ok:
		return gate
	var context: Dictionary = preflight.result
	var library: AnimationLibrary = CharacterRig.prepare_blink()
	if library == null or not CharacterRig.verify_blink(library).is_empty():
		return _failure("TOLINA_BLINK_BUILD_FAILED", "Detached blink preparation failed.")
	var before := _tolina_history_before(root, undo_redo)
	if before.is_empty():
		return _failure("TOLINA_BLINK_BUILD_FAILED", "The lab has no available editor scene history.")
	var rig := root.get_node(NodePath(CharacterRig.RIG_NAME))
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	before.rig_id = rig.get_instance_id()
	before.player_id = player.get_instance_id()
	before.scene_state = AnimationWriter.scene_state(root, player)
	before.player_state = AnimationWriter.player_state(player)
	before.animation = library.get_animation(CharacterRig.BLINK_NAME)
	before.context = context
	before.textures = CharacterRig.resource_states(context.textures)
	# No yield between final admission and post-verification. Native synchronous
	# callbacks are fenced by the shared guard and checked after the commit.
	preflight = _tolina_preflight()
	gate = _tolina_animation_gate(root, expected_session_id)
	if not preflight.ok or not gate.ok or undo_redo.is_committing_action() or CharacterRig.resource_states(context.textures) != before.textures or not CharacterRig.verify_blink(library).is_empty():
		if not preflight.ok:
			return preflight
		return gate if not gate.ok else _failure("WRITE_BUSY" if undo_redo.is_committing_action() else "TOLINA_BLINK_BUILD_FAILED", "Final blink or resource validation failed.")
	_action_started = true
	undo_redo.create_action(CharacterRig.BLINK_ACTION_NAME, UndoRedo.MERGE_DISABLE, root, false, true)
	# Native bound arguments retain both RefCounted resources across history.
	undo_redo.add_do_method(player, &"add_animation_library", &"", library)
	undo_redo.add_undo_method(player, &"remove_animation_library", &"")
	undo_redo.commit_action(true)
	if not _verify_tolina_blink_after_action(root, rig, player, library, before, undo_redo):
		return _failure("WRITE_OUTCOME_UNKNOWN", "Post-action blink verification failed; inspect the scene and history.")
	return {"ok": true, "result": _tolina_blink_success_data(), "error": null}


func _verify_tolina_blink_after_action(root: Node, rig: Node, player: AnimationPlayer,
		library: AnimationLibrary, before: Dictionary, undo_redo: EditorUndoRedoManager) -> bool:
	if not _tolina_history_after(root, before, undo_redo, CharacterRig.BLINK_ACTION_NAME):
		return false
	if not is_instance_valid(rig) or rig.get_instance_id() != before.rig_id or not is_instance_valid(player) or player.get_instance_id() != before.player_id or root.get_node_or_null(NodePath(CharacterRig.RIG_NAME)) != rig:
		return false
	if not CharacterRig.verify(rig, root, before.context.spec, before.context.textures, false) or not CharacterRig.verify_blink_targets(rig) or not CharacterRig.verify_blink(library).is_empty():
		return false
	if player.get_animation_library_list() != [&""] or player.get_animation_list() != PackedStringArray([CharacterRig.BLINK_NAME]) or player.get_animation_library(&"") != library or player.get_animation(CharacterRig.BLINK_NAME) != before.animation:
		return false
	return AnimationWriter.observers(player).is_empty() and AnimationWriter.pristine(player) \
		and AnimationWriter.player_state(player) == before.player_state and AnimationWriter.scene_state(root, player) == before.scene_state \
		and CharacterRig.resource_states(before.context.textures) == before.textures and CharacterRig.verify_asset_files(before.context.spec)


func _tolina_success_data() -> Dictionary:
	return {"editor_session_id": _session_id, "project_path": _canonical_project_path(),
		"scene_path": CharacterRig.LAB_PATH, "root_name": CharacterRig.ROOT_NAME,
		"created_root": CharacterRig.RIG_NAME, "created_node_count": 21,
		"undo_action_name": CharacterRig.ACTION_NAME, "undo_actions_added": 1,
		"save_state": "saved_dirty", "auto_saved": false, "read_only": false}


func _tolina_blink_success_data() -> Dictionary:
	return {"editor_session_id": _session_id, "project_path": _canonical_project_path(),
		"scene_path": CharacterRig.LAB_PATH, "root_name": CharacterRig.ROOT_NAME,
		"animation_player_path": "TolinaRig/AnimationPlayer", "library_name": "",
		"animation_name": "blink", "animation_key": "blink", "length_seconds": 0.24,
		"track_count": 3, "key_count": 18, "undo_action_name": CharacterRig.BLINK_ACTION_NAME,
		"undo_actions_added": 1, "save_state": "saved_dirty", "auto_saved": false, "read_only": false}


func _valid_operation_result(value: Dictionary, operation: String) -> bool:
	match operation:
		"godot_create_rig_lab": return _valid_result(value)
		"godot_create_rig_lab_animation": return _valid_animation_result(value)
	if value.size() != 3 or not value.get("ok") is bool or not value.has("result") or not value.has("error"):
		return false
	if not value.ok:
		return _valid_result(value)
	var expected := _tolina_success_data() if operation == "godot_create_tolina_rig_lab" else _tolina_blink_success_data()
	return value.error == null and value.result is Dictionary and value.result == expected \
		and typeof(value.result.undo_actions_added) == TYPE_INT \
		and (typeof(value.result.created_node_count) == TYPE_INT if operation == "godot_create_tolina_rig_lab" else typeof(value.result.track_count) == TYPE_INT and typeof(value.result.key_count) == TYPE_INT and typeof(value.result.length_seconds) == TYPE_FLOAT)


func _hex_id(value: String) -> bool:
	if value.length() != 32:
		return false
	for character in value:
		if not "0123456789abcdef".contains(character):
			return false
	return true


func _canonical_project_path() -> String:
	var path := ProjectSettings.globalize_path("res://").simplify_path().replace("\\", "/").to_lower()
	while path.ends_with("/"):
		path = path.left(-1)
	return path


func _valid_result(value: Dictionary) -> bool:
	if value.size() != 3 or not value.has("ok") or not value.ok is bool \
			or not value.has("result") or not value.has("error"):
		return false
	if value.ok:
		return value.error == null and value.result is Dictionary \
			and value.result == _success_data() \
			and typeof(value.result.created_node_count) == TYPE_INT \
			and typeof(value.result.undo_actions_added) == TYPE_INT
	return value.result == null and value.error is Dictionary \
		and value.error.size() == 2 and value.error.has("code") and value.error.code is String \
		and value.error.has("message") and value.error.message is String


func _failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "result": null, "error": {"code": code, "message": message}}
