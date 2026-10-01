@tool
extends RefCounted
## Native metadata getters only. No property reflection or resource serialization.

const MAX_NODES := 2000
const MAX_DEPTH := 64
const MAX_SELECTED := 128
const MAX_ANIMATIONS_PER_PLAYER := 128
const MAX_ANIMATIONS_TOTAL := 512
const MAX_LIBRARIES_PER_PLAYER := 512
const MAX_STRING_BYTES := 4096
const MAX_FRAME_BYTES := 262144
const PLUGIN_VERSION := "0.2.0"


func success(result: Dictionary) -> Dictionary:
	return {"ok": true, "result": result, "error": null}


func failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "result": null, "error": {"code": code, "message": message}}


func canonical_project_path() -> String:
	var path := ProjectSettings.globalize_path("res://").simplify_path().replace("\\", "/")
	while path.ends_with("/"):
		path = path.left(-1)
	return path.to_lower() if OS.get_name() == "Windows" else path


func ping(session_id: String) -> Dictionary:
	var project_name: Variant = ProjectSettings.get_setting("application/config/name", "")
	if not project_name is String:
		return failure("INSPECTION_FAILED", "Editor metadata inspection failed.")
	var result := {
		"godot_version": String(Engine.get_version_info().get("string", "")),
		"project_path": canonical_project_path(),
		"project_name": project_name,
		"plugin_version": PLUGIN_VERSION,
		"editor_session_id": session_id,
		"read_only": true,
	}
	return _bounded_success(result)


func scene_info(scene_root: Node, unsaved_paths: PackedStringArray) -> Dictionary:
	if scene_root == null:
		return {
			"exists": false, "path": null, "root_name": null,
			"has_saved_path": false, "save_state": "no_scene",
			"dirty_changes": null, "dirty_reason": "no_scene",
		}
	var saved_path := scene_root.scene_file_path
	var has_path := not saved_path.is_empty()
	var dirty := unsaved_paths.has(saved_path) if has_path else false
	return {
		"exists": true,
		"path": saved_path if has_path else null,
		"root_name": String(scene_root.name),
		"has_saved_path": has_path,
		"save_state": ("saved_dirty" if dirty else "saved_clean") if has_path else "new_unsaved",
		"dirty_changes": dirty if has_path else null,
		"dirty_reason": null if has_path else "unnamed_scene",
	}


func editor_state(scene_root: Node, selected: Array[Node], unsaved_paths: PackedStringArray, session_id: String) -> Dictionary:
	var metadata := ping(session_id)
	if not metadata.ok:
		return metadata
	var entries: Array[Dictionary] = []
	var total := 0
	if scene_root != null:
		for node in selected:
			if not is_instance_valid(node) or (node != scene_root and not scene_root.is_ancestor_of(node)):
				continue
			total += 1
			if entries.size() < MAX_SELECTED:
				entries.append({"path": String(scene_root.get_path_to(node)), "type": node.get_class()})
	var result: Dictionary = metadata.result
	result.scene = scene_info(scene_root, unsaved_paths)
	result.selected_nodes = {"total_count": total, "nodes": entries, "truncated": total > entries.size()}
	return _bounded_success(result)


func inspect_scene(scene_root: Node, unsaved_paths: PackedStringArray, session_id: String) -> Dictionary:
	var result := {"editor_session_id": session_id, "scene": scene_info(scene_root, unsaved_paths), "nodes": []}
	if scene_root == null:
		return _bounded_success(result)
	var stack: Array[Dictionary] = [{"node": scene_root, "path": ".", "parent": null, "depth": 0}]
	var names_remaining := MAX_ANIMATIONS_TOTAL
	var scheduled := 1
	var encoded_size := JSON.stringify(result).to_utf8_buffer().size()
	while not stack.is_empty():
		var entry: Dictionary = stack.pop_back()
		var node: Node = entry.node
		var child_count := node.get_child_count(false)
		if entry.depth > MAX_DEPTH or scheduled + child_count > MAX_NODES:
			return failure("SCENE_TOO_LARGE", "Scene exceeds the inspection work limit.")
		if entry.depth == MAX_DEPTH and child_count > 0:
			return failure("SCENE_TOO_LARGE", "Scene exceeds the inspection work limit.")
		var kind: Variant = null
		var animations: Variant = null
		if node is AnimationPlayer:
			kind = "animation_player"
			var found := _animation_metadata(node, names_remaining)
			if not found.ok:
				return found
			animations = found.result
			if animations.names != null:
				names_remaining -= animations.names.size()
		elif node is Skeleton2D:
			kind = "skeleton2d"
		elif node is Bone2D:
			kind = "bone2d"
		elif node is Polygon2D:
			kind = "polygon2d"
		var node_metadata := {
			"path": entry.path, "parent_path": entry.parent, "type": node.get_class(),
			"child_count": child_count, "kind": kind, "animations": animations,
		}
		result.nodes.append(node_metadata)
		encoded_size += JSON.stringify(node_metadata).to_utf8_buffer().size() + 1
		scheduled += child_count
		# Reverse push preserves native sibling order without retrieving internal children.
		for index in range(child_count - 1, -1, -1):
			var child := node.get_child(index, false)
			var path := String(scene_root.get_path_to(child))
			if path.to_utf8_buffer().size() > MAX_STRING_BYTES:
				return failure("RESPONSE_TOO_LARGE", "Editor response exceeds the size limit.")
			stack.append({"node": child, "path": path, "parent": entry.path, "depth": entry.depth + 1})
		# Check progressively so large metadata cannot accumulate beyond the frame limit.
		if not _values_bounded(node_metadata) or encoded_size > MAX_FRAME_BYTES - 512:
			return failure("RESPONSE_TOO_LARGE", "Editor response exceeds the size limit.")
	return _bounded_success(result)


func _animation_metadata(player: AnimationPlayer, remaining: int) -> Dictionary:
	var library_names := player.get_animation_library_list()
	if library_names.size() > MAX_LIBRARIES_PER_PLAYER:
		return failure("SCENE_TOO_LARGE", "Scene exceeds the inspection work limit.")
	var count := 0
	for library_name in library_names:
		var library := player.get_animation_library(library_name)
		count += library.get_animation_list_size()
	if count > MAX_ANIMATIONS_PER_PLAYER or count > remaining:
		return success({"count": count, "names": null, "omitted_reason": "limit"})
	var names: Array[String] = []
	for library_name in library_names:
		var library := player.get_animation_library(library_name)
		for animation_name in library.get_animation_list():
			var full_name := String(animation_name) if String(library_name).is_empty() else "%s/%s" % [library_name, animation_name]
			if full_name.to_utf8_buffer().size() > MAX_STRING_BYTES:
				return failure("RESPONSE_TOO_LARGE", "Editor response exceeds the size limit.")
			names.append(full_name)
	return success({"count": count, "names": names, "omitted_reason": null})


func _bounded_success(result: Dictionary) -> Dictionary:
	if not _values_bounded(result) or JSON.stringify(result).to_utf8_buffer().size() > MAX_FRAME_BYTES - 512:
		return failure("RESPONSE_TOO_LARGE", "Editor response exceeds the size limit.")
	return success(result)


func _values_bounded(value: Variant) -> bool:
	if value is String:
		return value.to_utf8_buffer().size() <= MAX_STRING_BYTES
	if value is Array:
		for item in value:
			if not _values_bounded(item):
				return false
	elif value is Dictionary:
		for key in value:
			if not _values_bounded(value[key]):
				return false
	return true
