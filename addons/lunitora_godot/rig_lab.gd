@tool
extends RefCounted
## One fixed, editor-session-owned writer. No saving or deferred mutation.

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


func _init(session_id: String) -> void:
	_session_id = session_id


func retire() -> void:
	# Transport shutdown must not free nodes retained by native editor history.
	_retired = true


func create(scene_root: Node, undo_redo: EditorUndoRedoManager,
		expected_session_id: String, request_id: String, command_origin := false) -> Dictionary:
	if not command_origin or not _hex_id(request_id):
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
	var value: Variant = _create_guarded(scene_root, undo_redo, expected_session_id)
	var result: Dictionary
	if not value is Dictionary or not _valid_result(value):
		result = _failure("WRITE_OUTCOME_UNKNOWN" if _action_started else "RIG_LAB_BUILD_FAILED",
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
	if _retired or expected_session_id != _session_id:
		return _failure("INVALID_MESSAGE", "The write belongs to a retired editor session.")
	if not is_instance_valid(root) or root != EditorInterface.get_edited_scene_root() or root.scene_file_path != LAB_PATH:
		return _failure("LAB_SCENE_REQUIRED", "Open the dedicated saved Totolina rig lab scene.")
	if root.name != ROOT_NAME or root.get_class() != "Node2D" or root.get_script() != null:
		return _failure("LAB_ROOT_MISMATCH", "The lab root must be the native script-free TotolinaRigLab Node2D.")
	if root.has_node(NodePath(RIG_NAME)):
		return _failure("LAB_ALREADY_CREATED", "The lab already contains TotolinaRigV2.")
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


func _verify_recipe(rig: Node, owner_root: Node) -> bool:
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
	return player.get_animation_library_list().is_empty() and player.get_animation_list().is_empty() \
		and not player.has_animation_library(&"") and not player.has_animation(&"RESET") \
		and player.autoplay == &"" and player.assigned_animation == &"" \
		and player.current_animation == &"" and not player.is_playing()


func _vertices() -> PackedVector2Array:
	return PackedVector2Array([Vector2(0, -12), Vector2(64, -12), Vector2(128, -12),
		Vector2(128, 12), Vector2(64, 12), Vector2(0, 12)])


func _triangles() -> Array:
	return [PackedInt32Array([0, 1, 5]), PackedInt32Array([1, 4, 5]),
		PackedInt32Array([1, 2, 4]), PackedInt32Array([2, 3, 4])]


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
