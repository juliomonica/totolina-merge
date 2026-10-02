@tool
extends "res://tests/godot_mcp/animation_lab_validation.gd"
## Disposable editor controls. Writes enter the registered authenticated MCP.
const Deformation = preload("res://addons/lunitora_godot/deformation_rig.gd")
const DEFORMATION_LAB := "res://addons/lunitora_godot/labs/rig_test_cat_deformation_lab.tscn"
var _retained_rig: WeakRef
var _retained_scarf: WeakRef
var _textures := {}
var _texture_before := {}
var _texture_signals := 0
var _cache_initial: Array = []
var _unknown_skeleton_observer := false
var _selection_expected: Node
var _selection_attempt := 0
var _native_observations: Array = []
var _helper_results := {}
var _other_polygon: Polygon2D
var _draw_poison_armed := false
var _draw_observer_calls := 0


func _enter_tree() -> void:
	var spec: Variant = JSON.parse_string(FileAccess.get_file_as_string(Deformation.SPEC_PATH))
	if spec is Dictionary:
		for row in spec.textures:
			if ResourceLoader.has_cached(row.path):
				_cache_initial.append(row.path)


func _rig() -> Node:
	return _root().get_node_or_null("RigTestCatRig") if _root() != null else null


func _player() -> AnimationPlayer:
	return _rig().get_node_or_null("AnimationPlayer") as AnimationPlayer if _rig() != null else null


func _fingerprint(texture: Texture2D) -> Dictionary:
	var image := texture.get_image()
	return {"id": texture.get_instance_id(), "class": texture.get_class(),
		"path": texture.resource_path, "load": texture.get_load_path(),
		"rid": texture.get_rid().get_id(), "size": texture.get_size(),
		"name": texture.resource_name, "local": texture.resource_local_to_scene,
		"pixels": image.get_data().hex_encode().sha256_text()}


func _watch() -> void:
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(Deformation.SPEC_PATH))
	for row in spec.textures:
		var texture: Texture2D = ResourceLoader.load(row.path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE)
		if not _textures.has(row.id):
			_textures[row.id] = texture
			_texture_before[row.id] = _fingerprint(texture)
			texture.changed.connect(_texture_changed)


func _texture_changed() -> void:
	_texture_signals += 1


func _textures_unchanged() -> bool:
	for key in _textures:
		if _fingerprint(_textures[key]) != _texture_before[key]:
			return false
	return _texture_signals == 0


func _recipe(player: AnimationPlayer) -> Dictionary:
	var result := {"libraries": [], "animations": [], "tracks": [], "markers": [], "exact": false}
	if player == null:
		return result
	result.merge({"libraries": player.get_animation_library_list(), "animations": player.get_animation_list(),
		"assigned": player.assigned_animation, "current": player.current_animation,
		"playing": player.is_playing(), "autoplay": player.autoplay, "queue": player.get_queue(),
		"reset": player.has_animation(&"RESET")}, true)
	var rest: Array = []
	for path in ["TailStation/TailSkeleton/TailRoot", "TailStation/TailSkeleton/TailRoot/TailMid1",
		"TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2", "TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip",
		"ArmStation/Shoulder", "ArmStation/Shoulder/UpperArm/Elbow"]:
		rest.append(_rig().get_node(NodePath(path)).rotation)
	rest.append(_rig().get_node("BodyStation/HeadPivot").position.y)
	result.rest = rest
	if not player.has_animation_library(&"") or not player.has_animation(&"deformation_demo"):
		return result
	var library := player.get_animation_library(&"")
	var animation := library.get_animation(&"deformation_demo")
	result.merge({"library_id": library.get_instance_id(), "animation_id": animation.get_instance_id(),
		"length": animation.length, "step": animation.step, "loop": animation.loop_mode,
		"markers": animation.get_marker_names(), "exact": Deformation.verify_demo(library).is_empty()}, true)
	for index in range(animation.get_track_count()):
		var track := {"type": animation.track_get_type(index), "path": animation.track_get_path(index),
			"interpolation": animation.track_get_interpolation_type(index),
			"update": animation.value_track_get_update_mode(index), "enabled": animation.track_is_enabled(index),
			"imported": animation.track_is_imported(index), "loop_wrap": animation.track_get_interpolation_loop_wrap(index), "keys": []}
		for key in range(animation.track_get_key_count(index)):
			track.keys.append([animation.track_get_key_time(index, key), animation.track_get_key_value(index, key),
				animation.track_get_key_transition(index, key)])
		result.tracks.append(track)
	return result


func _fixture() -> Dictionary:
	var result := {"count": 0, "exact": false, "vertices": 0, "triangles": 0, "bones": 0, "observers": []}
	var rig := _rig()
	if rig == null:
		return result
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(Deformation.SPEC_PATH))
	var used := {}
	for node in rig.find_children("*", "Sprite2D", true, false):
		for row in spec.textures:
			if node.texture != null and node.texture.resource_path == row.path:
				used[row.id] = node.texture
	var mesh: Polygon2D = rig.get_node("TailStation/TailMesh")
	for row in spec.textures:
		if mesh.texture.resource_path == row.path:
			used[row.id] = mesh.texture
	result.count = 1 + rig.find_children("*", "", true, false).size()
	result.vertices = mesh.polygon.size()
	result.triangles = mesh.polygons.size()
	result.bones = mesh.get_bone_count()
	result.observers = _observer_rows()
	result.scarf = _scarf_fixture(rig)
	result.arm = _arm_fixture(rig)
	# The evidence path follows the same admission ordering as the writer.
	if not _unknown_skeleton_observer:
		result.exact = Deformation.verify(rig, _root(), spec, used, false)
	return result


func _transform_evidence(node: Node2D) -> Dictionary:
	return {"position": [node.position.x, node.position.y], "rotation": node.rotation,
		"scale": [node.scale.x, node.scale.y], "z": node.z_index}


func _arm_fixture(rig: Node) -> Dictionary:
	var station: Node2D = rig.get_node("ArmStation")
	var shoulder: Node2D = station.get_node("Shoulder")
	var upper: Sprite2D = shoulder.get_node("UpperArm")
	var elbow: Node2D = upper.get_node("Elbow")
	var lower: Sprite2D = elbow.get_node("LowerArmPaw")
	var result := {"station": _transform_evidence(station), "shoulder": _transform_evidence(shoulder),
		"elbow": _transform_evidence(elbow),
		"upper_children": upper.get_children().map(func(node): return String(node.name)),
		"elbow_children": elbow.get_children().map(func(node): return String(node.name))}
	for piece in [upper, lower]:
		var row := _transform_evidence(piece)
		row.merge({"offset": [piece.offset.x, piece.offset.y], "centered": piece.centered,
			"texture_id": piece.texture.get_instance_id(), "texture_path": piece.texture.resource_path,
			"texture_size": [piece.texture.get_width(), piece.texture.get_height()],
			"filter": piece.texture_filter, "z_relative": piece.z_as_relative,
			"flip_h": piece.flip_h, "flip_v": piece.flip_v}, true)
		result["upper" if piece == upper else "lower"] = row
	return result


func _scarf_fixture(rig: Node) -> Dictionary:
	var scarf := rig.get_node_or_null("BodyStation/ScarfForeground") as Sprite2D
	if scarf == null:
		return {"exists": false}
	var torso: Sprite2D = rig.get_node("BodyStation/Torso")
	var head: Sprite2D = rig.get_node("BodyStation/HeadPivot/Head")
	var path := scarf.texture.resource_path if scarf.texture != null else ""
	var cached: Texture2D = ResourceLoader.load(path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE) if not path.is_empty() else null
	var imported := ConfigFile.new()
	var import_error := imported.load(path + ".import") if not path.is_empty() else ERR_FILE_NOT_FOUND
	var result := {"exists": true, "id": scarf.get_instance_id(), "class": scarf.get_class(),
		"script": scarf.get_script() != null, "owner": scarf.owner.get_instance_id() if scarf.owner != null else 0,
		"texture_id": scarf.texture.get_instance_id() if scarf.texture != null else 0,
		"torso_texture_id": torso.texture.get_instance_id() if torso.texture != null else 0,
		"texture_path": path, "cached_texture_id": cached.get_instance_id() if cached != null else 0,
		"texture_class": scarf.texture.get_class() if scarf.texture != null else "",
		"texture_script": scarf.texture.get_script() != null if scarf.texture != null else false,
		"texture_local": scarf.texture.resource_local_to_scene if scarf.texture != null else false,
		"texture_size": [scarf.texture.get_width(), scarf.texture.get_height()] if scarf.texture != null else [],
		"source_sha256": FileAccess.get_sha256(path), "import_sha256": FileAccess.get_sha256(path + ".import"),
		"import_error": import_error, "import_uid": imported.get_value("remap", "uid", ""),
		"import_path": imported.get_value("remap", "path", ""),
		"fix_alpha_border": imported.get_value("params", "process/fix_alpha_border", true),
		"offset": [scarf.offset.x, scarf.offset.y], "centered": scarf.centered,
		"filter": scarf.texture_filter, "z_relative": scarf.z_as_relative,
		"flip_h": scarf.flip_h, "flip_v": scarf.flip_v, "hframes": scarf.hframes, "vframes": scarf.vframes,
		"frame": scarf.frame, "region_enabled": scarf.region_enabled,
		"region_rect": [scarf.region_rect.position.x, scarf.region_rect.position.y, scarf.region_rect.size.x, scarf.region_rect.size.y],
		"body_children": rig.get_node("BodyStation").get_children().map(func(node): return String(node.name)),
		"body": _transform_evidence(rig.get_node("BodyStation")),
		"torso": _transform_evidence(torso), "head_pivot": _transform_evidence(head.get_parent()),
		"head": _transform_evidence(head), "head_offset": [head.offset.x, head.offset.y],
		"torso_offset": [torso.offset.x, torso.offset.y]}
	result.merge(_transform_evidence(scarf), true)
	return result


func _observer_rows() -> Array:
	var rows: Array = []
	if _rig() == null:
		return rows
	var skeleton: Skeleton2D = _rig().get_node("TailStation/TailSkeleton")
	for connection in skeleton.get_signal_connection_list(&"bone_setup_changed"):
		var callback: Callable = connection.callable
		var receiver := callback.get_object()
		rows.append({"method": String(callback.get_method()), "class": receiver.get_class() if receiver != null else "null",
			"id": callback.get_object_id(), "flags": connection.flags})
	return rows


func _skeletal_observer() -> void:
	pass


func _draw_observer() -> void:
	_draw_observer_calls += 1
	if _draw_poison_armed and _rig() != null:
		_rig().get_node("TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip").rotation = 0.125


func _attach_draw_observer(deferred: bool, path := "TailStation/TailMesh") -> void:
	_rig().get_node(NodePath(path)).draw.connect(_draw_observer, Object.CONNECT_DEFERRED if deferred else 0)


func _queue_draw_disconnect_select_root() -> void:
	var mesh: Polygon2D = _rig().get_node("TailStation/TailMesh")
	_attach_draw_observer(true)
	_draw_poison_armed = true
	# A real deferred callable remains queued after disconnect. The normal
	# selection/Inspector invalidation must prevent same-frame admission.
	mesh.draw.emit()
	mesh.draw.disconnect(_draw_observer)
	_select(_root())


func _draw_rows(path := "TailStation/TailMesh") -> Array:
	var rows: Array = []
	if _rig() == null:
		return rows
	for connection in _rig().get_node(NodePath(path)).get_signal_connection_list(&"draw"):
		var callback: Callable = connection.callable
		var receiver := callback.get_object()
		rows.append({"method": String(callback.get_method()), "class": receiver.get_class() if receiver != null else "null",
			"id": callback.get_object_id(), "flags": connection.flags})
	return rows


func _during_commit() -> void:
	for operation in _plugin()._writer.WRITE_OPERATIONS:
		_reentrant_results.append(_write(operation))


func _command(command: String) -> void:
	_command_ok = true
	if not command.begins_with("select_"):
		_selection_expected = null
	match command:
		"save":
			EditorInterface.save_scene_as(DEFORMATION_LAB, false)
			_saved_hash = FileAccess.get_sha256(DEFORMATION_LAB)
		"open": EditorInterface.open_scene_from_path(DEFORMATION_LAB)
		"restore_root": _root().name = "RigTestCatDeformationLab"
		"wrong_scene": _root().scene_file_path = "res://production_scene.tscn"
		"restore_scene": _root().scene_file_path = DEFORMATION_LAB
		"watch", "warm": _watch()
		"weighted_validation":
			var context := Deformation.read_spec()
			var validation: Script = load("res://tests/godot_mcp/weighted_mesh_validation.gd")
			_helper_results = validation.run(context.spec.mesh, context.textures.tail)
			_helper_results.scarf_spec_valid = Deformation.validate_spec(context.spec).is_empty()
			_helper_results.scarf_registration = []
			var mutations := {"texture": "torso", "pivot_px": [138, -238], "z_index": 2,
				"position_px": [1, 0], "rotation_rad": 0.01, "scale": [1, 0.99]}
			for property in mutations:
				var changed: Dictionary = context.spec.duplicate(true)
				for row in changed.nodes:
					if row.path == "BodyStation/ScarfForeground":
						row[property] = mutations[property]
				_helper_results.scarf_registration.append({"property": property,
					"rejected": not Deformation.validate_spec(changed).is_empty()})
		"retain_rig":
			_retained_rig = weakref(_rig())
			_retained_scarf = weakref(_rig().get_node("BodyStation/ScarfForeground"))
		"retain":
			_retained_library = weakref(_player().get_animation_library(&""))
			_retained_animation = weakref(_player().get_animation(&"deformation_demo"))
		"skeletal_observer":
			_rig().get_node("TailStation/TailSkeleton").bone_setup_changed.connect(_skeletal_observer)
			_unknown_skeleton_observer = true
		"remove_skeletal_observer":
			_rig().get_node("TailStation/TailSkeleton").bone_setup_changed.disconnect(_skeletal_observer)
			_unknown_skeleton_observer = false
		"draw_observer": _attach_draw_observer(false)
		"deferred_draw_observer": _attach_draw_observer(true)
		"remove_draw_observer": _rig().get_node("TailStation/TailMesh").draw.disconnect(_draw_observer)
		"scarf_draw_observer": _attach_draw_observer(false, "BodyStation/ScarfForeground")
		"deferred_scarf_draw_observer": _attach_draw_observer(true, "BodyStation/ScarfForeground")
		"remove_scarf_draw_observer": _rig().get_node("BodyStation/ScarfForeground").draw.disconnect(_draw_observer)
		"restore_tip_test_only":
			_draw_poison_armed = false
			_rig().get_node("TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip").rotation = 0.0
		"other_polygon_observer":
			_other_polygon = Polygon2D.new()
			_other_polygon.name = "OtherPolygon"
			_other_polygon.polygon = PackedVector2Array([Vector2.ZERO,Vector2(10,0),Vector2(0,10)])
			_other_polygon.polygons = [PackedInt32Array([0,1,2])]
			_other_polygon.add_bone(NodePath("TailRoot"),PackedFloat32Array([1,1,1]))
			_other_polygon.skeleton = NodePath("../RigTestCatRig/TailStation/TailSkeleton")
			_root().add_child(_other_polygon)
			_other_polygon.owner = _root()
			_unknown_skeleton_observer = true
		"remove_other_polygon_observer":
			_other_polygon.free()
			_other_polygon = null
			_unknown_skeleton_observer = false
		"queue":
			var bone: Bone2D = _rig().get_node("TailStation/TailSkeleton/TailRoot")
			bone.rest = bone.rest
			_rig().get_node("TailStation/TailMesh").queue_redraw()
		"queued_undo_redo":
			_command("queue")
			_command_ok = _shortcut(KEY_Z) and _shortcut(KEY_Z, true)
		"clear_history": get_undo_redo().clear_history(get_undo_redo().get_object_history_id(_root()), true)
		"unrelated":
			var node := Node2D.new()
			node.name = "Unrelated"
			node.position = Vector2(7,9)
			_root().add_child(node)
			node.owner = _root()
		"modified_mesh": _rig().get_node("TailStation/TailMesh").color = Color.RED
		"restore_mesh": _rig().get_node("TailStation/TailMesh").color = Color.WHITE
		"modified_scarf": _rig().get_node("BodyStation/ScarfForeground").z_index = 2
		"restore_scarf": _rig().get_node("BodyStation/ScarfForeground").z_index = 1
		"modified_scarf_texture": _rig().get_node("BodyStation/ScarfForeground").texture = _rig().get_node("BodyStation/Torso").texture
		"restore_scarf_texture": _rig().get_node("BodyStation/ScarfForeground").texture = ResourceLoader.load("res://addons/lunitora_godot/test_assets/rig_test_cat/body/rig_test_cat_scarf_foreground.png")
		"modified_scarf_offset": _rig().get_node("BodyStation/ScarfForeground").offset = Vector2(-138, 238)
		"restore_scarf_offset": _rig().get_node("BodyStation/ScarfForeground").offset = Vector2(-139, 238)
		"modified_scarf_region": _rig().get_node("BodyStation/ScarfForeground").region_enabled = true
		"restore_scarf_region": _rig().get_node("BodyStation/ScarfForeground").region_enabled = false
		"modified_lower_rotation": _rig().get_node("ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw").rotation = 0.0
		"restore_lower_rotation": _rig().get_node("ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw").rotation = -0.87026
		"posed_elbow": _rig().get_node("ArmStation/Shoulder/UpperArm/Elbow").rotation = 0.87026 + deg_to_rad(10.0)
		"restore_elbow": _rig().get_node("ArmStation/Shoulder/UpperArm/Elbow").rotation = 0.87026
		"reentry": get_undo_redo().history_changed.connect(_during_commit)
		"remove_reentry": get_undo_redo().history_changed.disconnect(_during_commit)
		"select_mesh", "select_scarf", "select_skeleton", "select_root_bone", "select_mid1", "select_mid2", "select_tip":
			var paths := {"select_mesh": "TailStation/TailMesh", "select_skeleton": "TailStation/TailSkeleton",
				"select_scarf": "BodyStation/ScarfForeground",
				"select_root_bone": "TailStation/TailSkeleton/TailRoot", "select_mid1": "TailStation/TailSkeleton/TailRoot/TailMid1",
				"select_mid2": "TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2",
				"select_tip": "TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip"}
			_selection_expected = _rig().get_node(NodePath(paths[command]))
			_selection_attempt = 0
			EditorInterface.set_main_screen_editor("2D")
			_select(_selection_expected)
		_: super._command(command)


func _evidence() -> void:
	var plugin := _plugin()
	if plugin == null:
		return
	if is_instance_valid(_selection_expected) and EditorInterface.get_inspector().get_edited_object() != _selection_expected:
		_selection_attempt += 1
		if _selection_attempt % 4 == 0 and _selection_attempt < 120:
			_select(_selection_expected)
	elif is_instance_valid(_selection_expected):
		_selection_expected = null
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
		"root": scene.get_instance_id() if scene != null else 0, "scene": scene.scene_file_path if scene != null else "",
		"dirty": EditorInterface.get_unsaved_scenes().has(DEFORMATION_LAB),
		"connections": _connections(player), "recipe": _recipe(player), "snapshot": _snapshot(), "rig": _fixture(),
		"history": [history.get_version(), history.get_current_action(), history.get_history_count(), history.has_redo(), history.has_undo(), names] if history != null else [],
		"file_hash": FileAccess.get_sha256(DEFORMATION_LAB), "saved_hash": _saved_hash,
		"retained_rig": _retained_rig.get_ref().get_instance_id() if _retained_rig != null and _retained_rig.get_ref() != null else 0,
		"retained_scarf": _retained_scarf.get_ref().get_instance_id() if _retained_scarf != null and _retained_scarf.get_ref() != null else 0,
		"retained_library": _retained_library.get_ref().get_instance_id() if _retained_library != null and _retained_library.get_ref() != null else 0,
		"retained_animation": _retained_animation.get_ref().get_instance_id() if _retained_animation != null and _retained_animation.get_ref() != null else 0,
		"ledger": plugin._writer._write_ids.size(), "faulted": plugin._writer._faulted, "active": plugin._writer._active,
		"quiet_frame": plugin._writer._animation_quiet_frame, "process_frame": plugin._writer._animation_process_frame,
		"draw_connections": _draw_rows(), "draw_observer_calls": _draw_observer_calls,
		"scarf_draw_connections": _draw_rows("BodyStation/ScarfForeground"),
		"cache_initial": _cache_initial, "textures_unchanged": _textures_unchanged(), "texture_changed": _texture_signals,
		"selected": EditorInterface.get_selection().get_selected_nodes().map(func(n):return n.get_instance_id()),
		"inspected": EditorInterface.get_inspector().get_edited_object().get_instance_id() if EditorInterface.get_inspector().get_edited_object() != null else 0,
		"reentrant_results": _reentrant_results, "helper_results": _helper_results}
	var timer_found := false
	var timer_pending := false
	for settings in get_tree().root.find_children("*", "", true, false):
		if settings.get_class() == "ProjectSettingsEditor":
			for timer in settings.find_children("*", "Timer", true, false):
				if timer.one_shot and timer.wait_time == 1.5:
					timer_found = true
					timer_pending = timer_pending or not timer.is_stopped()
	data.project_settings_timer_found = timer_found
	data.project_settings_save_pending = timer_pending
	_sequence += 1
	var file := FileAccess.open("res://.godot/animation_evidence_%08d.json" % _sequence, FileAccess.WRITE)
	file.store_string(JSON.stringify(data))
	file.close()
