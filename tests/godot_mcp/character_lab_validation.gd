@tool
extends "res://tests/godot_mcp/animation_lab_validation.gd"
## Test-only controls in disposable native editors. Public writes still traverse
## the registered MCP tool, authenticated transport and production plugin.
const CHARACTER_LAB := "res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"
const PRODUCTION := "res://scenes/presentation/totolina_operator.tscn"
const SPEC := "res://addons/lunitora_godot/specs/tolina_character_rig_v1.json"
const Character = preload("res://addons/lunitora_godot/character_rig.gd")
const TIMES := [0.0, 0.05, 0.095, 0.14, 0.19, 0.24]
const VALUES := [[1.0, 0.0, 0.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]]
const PATHS := ["Visual/Eyes/Rest:modulate:a", "Visual/Eyes/Half:modulate:a", "Visual/Eyes/Closed:modulate:a"]
var _retained_rig: WeakRef
var _textures := {}
var _texture_before := {}
var _texture_emissions := 0
var _production: Node
var _production_before := {}
var _cache_initial := []
var _last_texture_comparison := true
var _sprite_assignment_signals := 0
var _spec_results := {}
var _numeric_results := {}
var _committing_results: Array[Dictionary] = []
var _fake_texture: Texture2D
var _cache_fault := {}


func _enter_tree() -> void:
	# Explicit readiness evidence must precede importing credential ancestor pins.
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPEC))
	for item in spec.textures:
		if ResourceLoader.has_cached(item.path):
			_cache_initial.append(item.path)


func _player() -> AnimationPlayer:
	var scene := _root()
	return scene.get_node_or_null("TolinaRig/AnimationPlayer") if scene != null else null


func _dirty() -> bool:
	return EditorInterface.get_unsaved_scenes().has(CHARACTER_LAB)


func _texture_changed() -> void:
	_texture_emissions += 1


func _sprite_changed() -> void:
	_sprite_assignment_signals += 1


func _texture_state(texture: Texture2D) -> Dictionary:
	var image := texture.get_image()
	return {"id": texture.get_instance_id(), "class": texture.get_class(),
		"path": texture.resource_path, "name": texture.resource_name,
		"script": texture.get_script(), "local": texture.resource_local_to_scene,
		"scene_id": texture.resource_scene_unique_id, "stored": _storage(texture),
		"size": texture.get_size(), "rid": texture.get_rid().get_id(),
		"load_path": texture.get_load_path(), "image_format": image.get_format(),
		"image_mips": image.has_mipmaps(), "pixels": image.get_data().hex_encode().sha256_text(),
		"production_id": texture.get_id_for_path(PRODUCTION)}


func _watch_textures() -> void:
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPEC))
	for item in spec.textures:
		var texture: Texture2D = ResourceLoader.load(item.path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE)
		if not _textures.has(item.id):
			_textures[item.id] = texture
			_texture_before[item.id] = _texture_state(texture)
			texture.changed.connect(_texture_changed)


func _compare_textures() -> bool:
	for id in _textures:
		if _texture_state(_textures[id]) != _texture_before[id]:
			return false
	return _texture_emissions == 0


func _visual_properties(node: CanvasItem) -> Dictionary:
	var names := [&"position", &"rotation", &"scale", &"skew", &"transform",
		&"modulate", &"self_modulate", &"visible", &"z_index", &"z_as_relative",
		&"show_behind_parent", &"y_sort_enabled", &"texture_filter", &"material",
		&"texture_repeat", &"use_parent_material", &"top_level", &"clip_children",
		&"light_mask", &"visibility_layer"]
	if node is Sprite2D:
		names.append_array([&"texture", &"centered", &"offset", &"flip_h", &"flip_v",
			&"hframes", &"vframes", &"frame", &"frame_coords", &"region_enabled",
			&"region_rect", &"region_filter_clip_enabled"])
	var result := {}
	for property in names:
		result[property] = node.get(property)
	var children: Array[String] = []
	for child in node.get_children():
		children.append(String(child.name))
	result.children = children
	return result


func _effective_color(node: CanvasItem, local_root: Node) -> Color:
	var value := node.self_modulate
	var current: Node = node
	while current is CanvasItem:
		value *= current.modulate
		if current == local_root:
			break
		current = current.get_parent()
	return value


func _production_snapshot() -> Dictionary:
	var result := {}
	if is_instance_valid(_production):
		for node in [_production] + _production.find_children("*", "", true, false):
			if node is CanvasItem:
				result[String(_production.get_path_to(node))] = _visual_properties(node)
	return result


func _composition() -> Dictionary:
	var packed: PackedScene = ResourceLoader.load(PRODUCTION, "PackedScene", ResourceLoader.CACHE_MODE_REUSE)
	var comparison := packed.instantiate()
	var rig := _root().get_node_or_null("TolinaRig") if _root() != null else null
	var failures: Array[String] = []
	var compared := 0
	if rig != null:
		if rig.modulate != Color.WHITE or rig.self_modulate != Color.WHITE or rig.modulate != comparison.modulate or rig.self_modulate != comparison.self_modulate:
			failures.append("local-root modulation")
		# Production uses asset-basename node names; normalize only this detached
		# comparison instance to the approved logical IDs before comparing order.
		var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPEC))
		for item in spec.pieces:
			var basename := "ShoulderOverlap"
			if item.id != "ShoulderOverlap":
				for texture in spec.textures:
					if texture.id == item.texture:
						basename = String(texture.path).get_file().get_basename()
			comparison.get_node(NodePath(item.parent + "/" + basename)).name = item.id
		for path in ["Visual", "Visual/Arms", "Visual/Eyes"]:
			compared += 1
			if _visual_properties(rig.get_node(path)) != _visual_properties(comparison.get_node(path)):
				failures.append(path)
			if _effective_color(rig.get_node(path), rig) != _effective_color(comparison.get_node(path), comparison):
				failures.append(path + " effective modulation")
		for node in rig.find_children("*", "Sprite2D", true, false):
			var path := String(rig.get_path_to(node))
			compared += 1
			if _visual_properties(node) != _visual_properties(comparison.get_node(path)):
				failures.append(path)
			if _effective_color(node, rig) != _effective_color(comparison.get_node(path), comparison):
				failures.append(path + " effective modulation")
	comparison.free()
	return {"compared": compared, "failures": failures}


func _rig_validation() -> Dictionary:
	var scene := _root()
	var rig := scene.get_node_or_null("TolinaRig") if scene != null else null
	var problems: Array[String] = []
	if rig == null:
		return {"count": 0, "sprites": 0, "problems": [], "composition": {"compared": 0, "failures": []}}
	var spec: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPEC))
	var nodes := [rig] + rig.find_children("*", "", true, false)
	var sprites := rig.find_children("*", "Sprite2D", true, false)
	if nodes.size() != 21 or sprites.size() != 16:
		problems.append("node counts")
	for node in nodes:
		if node.get_script() != null or node.owner != scene:
			problems.append("native/owner " + String(node.name))
	for item in spec.pieces:
		var node: Sprite2D = rig.get_node(NodePath(item.parent + "/" + item.id))
		var position_value := Vector2(item.position_px[0], item.position_px[1])
		var scale_value := Vector2(item.scale[0], item.scale[1])
		var offset_value := -Vector2(item.pivot_px[0], item.pivot_px[1])
		var rotation_value := Transform2D(item.rotation_rad, Vector2.ZERO).get_rotation()
		if node.position != position_value or node.scale != scale_value or node.rotation != rotation_value or node.offset != offset_value or node.centered:
			problems.append("transforms " + item.id)
		if node.modulate != Color(1, 1, 1, item.alpha) or node.self_modulate != Color.WHITE or not node.visible or node.z_index != item.z_index:
			problems.append("alpha/z " + item.id)
		var texture_path := ""
		for texture in spec.textures:
			if texture.id == item.texture:
				texture_path = texture.path
		if node.texture.get_class() != "CompressedTexture2D" or node.texture.resource_path != texture_path or node.texture != ResourceLoader.load(texture_path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE):
			problems.append("external texture " + item.id)
	var body: Sprite2D = rig.get_node("Visual/Body")
	var shoulder: Sprite2D = rig.get_node("Visual/ShoulderOverlap")
	if body.texture != shoulder.texture or shoulder.get_rect() != Rect2(0, 0, 170, 95) or body.to_global(Vector2(530, 325)) != shoulder.to_global(Vector2.ZERO):
		problems.append("region-local shoulder alignment")
	return {"count": nodes.size(), "sprites": sprites.size(), "problems": problems, "composition": _composition()}


func _recipe(player: AnimationPlayer) -> Dictionary:
	var value := {"libraries": [], "animations": [], "tracks": [], "markers": [], "exact": true}
	if player == null:
		return value
	value.libraries = player.get_animation_library_list()
	value.animations = player.get_animation_list()
	value.assigned = player.assigned_animation
	value.current = player.current_animation
	value.playing = player.is_playing()
	value.autoplay = player.autoplay
	value.queue = player.get_queue()
	value.root_node = player.root_node
	value.rest = [_root().get_node("TolinaRig/Visual/Eyes/Rest").modulate.a,
		_root().get_node("TolinaRig/Visual/Eyes/Half").modulate.a,
		_root().get_node("TolinaRig/Visual/Eyes/Closed").modulate.a]
	if not player.has_animation(&"blink"):
		return value
	var library := player.get_animation_library(&"")
	var animation := library.get_animation(&"blink")
	value.library_id = library.get_instance_id()
	value.animation_id = animation.get_instance_id()
	value.length = animation.length
	value.step = animation.step
	value.loop = animation.loop_mode
	value.markers = animation.get_marker_names()
	value.reset = player.has_animation(&"RESET")
	value.exact = animation.length == 0.24 and animation.step == 0.125 and animation.loop_mode == Animation.LOOP_NONE and animation.get_track_count() == 3
	var canonical := PackedFloat32Array(TIMES)
	for track in range(animation.get_track_count()):
		var row := {"type": animation.track_get_type(track), "path": String(animation.track_get_path(track)),
			"interpolation": animation.track_get_interpolation_type(track), "update": animation.value_track_get_update_mode(track),
			"enabled": animation.track_is_enabled(track), "imported": animation.track_is_imported(track),
			"loop_wrap": animation.track_get_interpolation_loop_wrap(track), "keys": []}
		value.exact = value.exact and track < 3 and row.type == Animation.TYPE_VALUE and row.path == PATHS[track] and row.interpolation == Animation.INTERPOLATION_LINEAR and row.update == Animation.UPDATE_CONTINUOUS and row.enabled and not row.imported and not row.loop_wrap and animation.track_get_key_count(track) == 6
		for key in range(animation.track_get_key_count(track)):
			var time := animation.track_get_key_time(track, key)
			var alpha: Variant = animation.track_get_key_value(track, key)
			row.keys.append([time, alpha, animation.track_get_key_transition(track, key)])
			value.exact = value.exact and key < 6 and time == canonical[key] and typeof(alpha) == TYPE_FLOAT and alpha == VALUES[track][key] and animation.track_get_key_transition(track, key) == 1.0
		for index in range(25):
			var sampled: float = animation.value_track_interpolate(track, 0.24 * index / 24.0)
			value.exact = value.exact and is_finite(sampled)
		value.tracks.append(row)
	return value


func _spec_cases() -> void:
	var original: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(SPEC))
	_spec_results.clear()
	_spec_results["valid"] = Character.validate_spec(original).is_empty()
	var changes := ["closed", "version", "counts", "duplicate", "parent", "cycle",
		"nonfinite", "position", "rotation", "scale_zero", "scale_high", "pivot",
		"z", "alpha", "region", "texture_path", "texture_id", "dimensions", "hash"]
	for change in changes:
		var value: Dictionary = original.duplicate(true)
		match change:
			"closed": value.extra = true
			"version": value.schema_version = 2
			"counts": value.pieces.append(value.pieces[0])
			"duplicate": value.pieces[1].id = value.pieces[0].id
			"parent": value.pieces[0].parent = "Missing"
			"cycle": value.groups[0].parent = "Visual/Eyes"
			"nonfinite": value.pieces[0].position_px[0] = INF
			"position": value.pieces[0].position_px[0] = 8193.0
			"rotation": value.pieces[0].rotation_rad = 4.0
			"scale_zero": value.pieces[0].scale[0] = 0.0
			"scale_high": value.pieces[0].scale[0] = 9.0
			"pivot": value.pieces[0].pivot_px[0] = 8193.0
			"z": value.pieces[0].z_index = 33
			"alpha": value.pieces[0].alpha = -0.1
			"region": value.pieces[0].region_px = [0, 0, 2048, 2048]
			"texture_path": value.textures[0].path = "res://assets/characters/totolina/../redirect.png"
			"texture_id": value.textures[0].id = "unknown"
			"dimensions": value.textures[0].size_px[0] = 1
			"hash": value.textures[0].source_sha256 = "invalid"
		_spec_results[change] = not Character.validate_spec(value).is_empty()
	var loaded := Character.read_spec()
	if loaded.ok:
		var textures: Dictionary = loaded.textures.duplicate()
		var rig := Character.prepare(loaded.spec, textures)
		textures.body = ImageTexture.new()
		_spec_results["native_type"] = not Character.verify(rig, null, loaded.spec, textures)
		textures.body = loaded.textures.ear_left
		_spec_results["native_path_dimensions"] = not Character.verify(rig, null, loaded.spec, textures)
		rig.free()


func _numeric_characterization() -> void:
	var library := Character.prepare_blink()
	var animation := library.get_animation(&"blink")
	var times := PackedFloat32Array(TIMES)
	var first := times[1] - 0.000001
	var second := times[3] - 0.000001
	var half_first: float = animation.value_track_interpolate(1, first)
	var closed_first: float = animation.value_track_interpolate(2, first)
	var half_second: float = animation.value_track_interpolate(1, second)
	var closed_second: float = animation.value_track_interpolate(2, second)
	var sprite := Sprite2D.new()
	var property := NodePath(":modulate:a")
	sprite.set_indexed(property, closed_first)
	_numeric_results = {"first_time": first, "half_first": half_first,
		"closed_first": closed_first, "second_time": second,
		"half_second": half_second, "closed_second": closed_second,
		"color_alpha": sprite.modulate.a, "helper_verification": Character.verify_blink(library),
		"exact_key_alphas": true, "sum_partition": true}
	for index in range(6):
		var sum := 0.0
		for track in range(3):
			var value: float = animation.track_get_key_value(track, index)
			_numeric_results.exact_key_alphas = _numeric_results.exact_key_alphas and value >= 0.0 and value <= 1.0 and value == VALUES[track][index]
			sum += value
		_numeric_results.sum_partition = _numeric_results.sum_partition and sum == 1.0
	sprite.free()


func _during_commit() -> void:
	var plugin := _plugin()
	for operation in ["godot_create_rig_lab", "godot_create_rig_lab_animation", "godot_create_tolina_rig_lab", "godot_create_tolina_lab_blink"]:
		_committing_results.append(plugin._dispatch(operation, {}, Crypto.new().generate_random_bytes(16).hex_encode(), plugin._session_id, true))


func _command(command: String) -> void:
	_command_ok = true
	match command:
		"save":
			EditorInterface.save_scene_as(CHARACTER_LAB, false)
			_saved_hash = FileAccess.get_sha256(CHARACTER_LAB)
		"open": EditorInterface.open_scene_from_path(CHARACTER_LAB)
		"warm": _watch_textures()
		"production":
			var packed: PackedScene = ResourceLoader.load(PRODUCTION, "PackedScene", ResourceLoader.CACHE_MODE_REUSE)
			_production = packed.instantiate()
			_production_before = _production_snapshot()
			_watch_textures()
		"watch": _watch_textures()
		"assignment_signals":
			_watch_textures()
			for index in range(16):
				var sprite := Sprite2D.new()
				sprite.texture_changed.connect(_sprite_changed)
				sprite.texture = _textures.values()[index % 15]
				sprite.free()
		"spec_cases": _spec_cases()
		"numeric": _numeric_characterization()
		"fake_type", "fake_load_path_dimensions":
			var path := "res://assets/characters/totolina/body/cat_totolina_body.png"
			_command_ok = not ResourceLoader.has_cached(path) and _fake_texture == null
			if _command_ok:
				_fake_texture = ImageTexture.new() if command == "fake_type" else CompressedTexture2D.new()
				if command == "fake_load_path_dimensions":
					var config := ConfigFile.new()
					_command_ok = config.load("res://assets/characters/totolina/ears/cat_totolina_ear_left.png.import") == OK
					if _command_ok:
						_command_ok = _fake_texture.load(config.get_value("remap", "path")) == OK
				# Only this brand-new disposable fake receives a cache key. Never
				# take_over_path and never alter any loaded production resource.
				_fake_texture.resource_path = path
				_cache_fault = {"class": _fake_texture.get_class(), "path": _fake_texture.resource_path,
					"size": _fake_texture.get_size(), "load_path": _fake_texture.get_load_path() if _fake_texture is CompressedTexture2D else "",
					"cached": ResourceLoader.has_cached(path)}
		"clear_fake":
			if _fake_texture != null:
				_fake_texture.resource_path = ""
				_fake_texture = null
		"reentry_on": get_undo_redo().history_changed.connect(_during_commit)
		"reentry_off": get_undo_redo().history_changed.disconnect(_during_commit)
		"unrelated":
			var node := Node2D.new()
			node.name = "Unrelated"
			node.position = Vector2(7, 9)
			var manager := get_undo_redo()
			manager.create_action("Fixture: unrelated child", UndoRedo.MERGE_DISABLE, _root())
			manager.add_do_method(_root(), &"add_child", node)
			manager.add_do_property(node, &"owner", _root())
			manager.add_undo_method(_root(), &"remove_child", node)
			manager.add_do_reference(node)
			manager.commit_action()
		"retain_rig": _retained_rig = weakref(_root().get_node("TolinaRig"))
		"retain":
			_retained_library = weakref(_player().get_animation_library(&""))
			_retained_animation = weakref(_player().get_animation(&"blink"))
		"wrong_root": _root().name = "WrongRoot"
		"restore_root": _root().name = "TolinaCharacterRigLab"
		"script_root":
			var script := GDScript.new()
			script.source_code = "@tool\nextends Node2D\n"
			_command_ok = script.reload() == OK
			_root().set_script(script)
		"restore_root_script": _root().set_script(null)
		"wrong_scene": _root().scene_file_path = "res://scenes/presentation/totolina_operator.tscn"
		"restore_scene": _root().scene_file_path = CHARACTER_LAB
		"modified_sprite": _root().get_node("TolinaRig/Visual/Eyes/Rest").offset.x += 1.0
		"restore_sprite": _root().get_node("TolinaRig/Visual/Eyes/Rest").offset.x -= 1.0
		"same_pass":
			var plugin := _plugin()
			for index in range(3):
				_observations.append(plugin._dispatch("godot_create_tolina_lab_blink", {}, Crypto.new().generate_random_bytes(16).hex_encode(), plugin._session_id, true))
		"retarget":
			if not is_instance_valid(_other):
				_other = AnimationPlayer.new()
				_other.name = "ObserverControlPlayer"
				_other.root_node = NodePath(".")
				_root().add_child(_other)
				_other.owner = _root()
			_select(_player())
			_player().animation_list_changed.emit()
			_sentinel.call_deferred("queued real editor callback")
			_select(_other)
			var animation := Animation.new()
			var library := AnimationLibrary.new()
			library.add_animation(&"blink", animation)
			_command_ok = _other.add_animation_library(&"", library) == OK
		"quit":
			if is_instance_valid(_production):
				_production.free()
				_production = null
			get_tree().quit()
		_: super._command(command)


func _evidence() -> void:
	var plugin := _plugin()
	if plugin == null:
		return
	var scene := _root()
	var settings_timer_found := false
	var settings_save_pending := false
	for timer in get_tree().root.find_children("*", "Timer", true, false):
		if timer.get_parent().get_class() == "ProjectSettingsEditor":
			settings_timer_found = true
			settings_save_pending = settings_save_pending or not timer.is_stopped()
	var data := {"ack": _ack, "ok": _command_ok, "frame": Engine.get_process_frames(),
		"display": DisplayServer.get_name(), "session": plugin._session_id,
		"root": scene.get_instance_id() if scene != null else 0,
		"scene": scene.scene_file_path if scene != null else "", "dirty": _dirty(),
		"snapshot": _snapshot(), "history": _history_state() if scene != null else [],
		"connections": _connections(_player()), "recipe": _recipe(_player()),
		"rig": _rig_validation(), "file_hash": FileAccess.get_sha256(CHARACTER_LAB),
		"retained_rig": _retained_rig.get_ref().get_instance_id() if _retained_rig != null and _retained_rig.get_ref() != null else 0,
		"retained_library": _retained_library.get_ref().get_instance_id() if _retained_library != null and _retained_library.get_ref() != null else 0,
		"retained_animation": _retained_animation.get_ref().get_instance_id() if _retained_animation != null and _retained_animation.get_ref() != null else 0,
		"textures_unchanged": _compare_textures(), "texture_changed": _texture_emissions,
		"texture_count": _textures.size(), "cache_initial": _cache_initial,
		"sprite_assignment_signals": _sprite_assignment_signals,
		"spec_results": _spec_results, "numeric": _numeric_results,
		"committing_results": _committing_results,
		"cache_fault": _cache_fault,
		"project_settings_timer_found": settings_timer_found,
		"project_settings_save_pending": settings_save_pending,
		"production_unchanged": not is_instance_valid(_production) or _production_snapshot() == _production_before,
		"ledger": plugin._writer._write_ids.size(), "faulted": plugin._writer._faulted,
		"active": plugin._writer._active, "quiet_frame": plugin._writer._animation_quiet_frame,
		"observations": _observations, "sentinels": _sentinels}
	_sequence += 1
	var file := FileAccess.open("res://.godot/animation_evidence_%08d.json" % _sequence, FileAccess.WRITE)
	file.store_string(JSON.stringify(data))
	file.close()
