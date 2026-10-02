@tool
extends RefCounted
## Closed reviewed Tolina fixture. Shared session/admission/history live in RigLab.

const AnimationWriter = preload("res://addons/lunitora_godot/animation_writer.gd")
const LAB_PATH := "res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"
const ROOT_NAME := "TolinaCharacterRigLab"
const RIG_NAME := "TolinaRig"
const ACTION_NAME := "Lunitora: Create Tolina Character Rig"
const SPEC_PATH := "res://addons/lunitora_godot/specs/tolina_character_rig_v1.json"
# Reviewed bytes are pinned here, never trusted from a field inside the JSON.
const SPEC_SHA256 := "439aed4c21b6d524a875ceec3144e5a1b82d5cdece799dd6851d30f435a2be0f"
const SPEC_LIMIT := 65536
const BLINK_ACTION_NAME := "Lunitora: Create Tolina Lab Blink"
const BLINK_NAME := &"blink"
const BLINK_PATHS := [NodePath("Visual/Eyes/Rest:modulate:a"),
	NodePath("Visual/Eyes/Half:modulate:a"), NodePath("Visual/Eyes/Closed:modulate:a")]
const BLINK_VALUES := [[1.0, 0.0, 0.0, 0.0, 0.0, 1.0],
	[0.0, 1.0, 0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]]
const MANIFEST := {".": "Node2D", "Visual": "Node2D", "Visual/EarLeft": "Sprite2D",
	"Visual/EarRight": "Sprite2D", "Visual/Body": "Sprite2D", "Visual/Arms": "Node2D",
	"Visual/Arms/Idle": "Sprite2D", "Visual/Arms/Press01": "Sprite2D",
	"Visual/Arms/Press02": "Sprite2D", "Visual/Arms/Press03": "Sprite2D",
	"Visual/ShoulderOverlap": "Sprite2D", "Visual/Eyes": "Node2D",
	"Visual/Eyes/Rest": "Sprite2D", "Visual/Eyes/Half": "Sprite2D",
	"Visual/Eyes/Closed": "Sprite2D", "Visual/Eyes/Excited": "Sprite2D",
	"Visual/Eyes/Surprised": "Sprite2D", "Visual/MouthIdle": "Sprite2D",
	"Visual/MouthExcited": "Sprite2D", "Visual/MouthSurprised": "Sprite2D",
	"AnimationPlayer": "AnimationPlayer"}
const CHILDREN := {".": ["Visual", "AnimationPlayer"],
	"Visual": ["EarLeft", "EarRight", "Body", "Arms", "ShoulderOverlap", "Eyes",
		"MouthIdle", "MouthExcited", "MouthSurprised"],
	"Visual/Arms": ["Idle", "Press01", "Press02", "Press03"],
	"Visual/Eyes": ["Rest", "Half", "Closed", "Excited", "Surprised"]}
const TEXTURES := {
	"body": ["body/cat_totolina_body.png", Vector2i(768, 1024)],
	"ear_left": ["ears/cat_totolina_ear_left.png", Vector2i(192, 192)],
	"ear_right": ["ears/cat_totolina_ear_right.png", Vector2i(192, 192)],
	"arm_idle": ["arms/cat_totolina_arm_idle.png", Vector2i(384, 384)],
	"arm_press_01": ["arms/cat_totolina_arm_press_01.png", Vector2i(384, 384)],
	"arm_press_02": ["arms/cat_totolina_arm_press_02.png", Vector2i(384, 384)],
	"arm_press_03": ["arms/cat_totolina_arm_press_03.png", Vector2i(384, 384)],
	"eyes_blink_01": ["eyes/cat_totolina_eyes_blink_01.png", Vector2i(328, 128)],
	"eyes_blink_02": ["eyes/cat_totolina_eyes_blink_02.png", Vector2i(328, 128)],
	"eyes_blink_03": ["eyes/cat_totolina_eyes_blink_03.png", Vector2i(328, 128)],
	"eyes_excited": ["eyes/cat_totolina_eyes_excited.png", Vector2i(328, 128)],
	"eyes_surprised": ["eyes/cat_totolina_eyes_surprised.png", Vector2i(328, 128)],
	"mouth_idle": ["mouths/cat_totolina_mouth_idle.png", Vector2i(128, 128)],
	"mouth_excited": ["mouths/cat_totolina_mouth_excited.png", Vector2i(128, 128)],
	"mouth_surprised": ["mouths/cat_totolina_mouth_surprised.png", Vector2i(128, 128)]}
const TEXTURE_PREFIX := "res://assets/characters/totolina/"
const PRODUCTION_PATH := "res://scenes/presentation/totolina_operator.tscn"


static func read_spec() -> Dictionary:
	if not _unlinked_path(SPEC_PATH):
		return _failure("TOLINA_SPEC_INVALID", "The reviewed specification path is redirected.")
	var file := FileAccess.open(SPEC_PATH, FileAccess.READ)
	if file == null or file.get_length() > SPEC_LIMIT:
		return _failure("TOLINA_SPEC_INVALID", "The reviewed Tolina specification is missing or exceeds its bound.")
	var bytes := file.get_buffer(file.get_length())
	file.close()
	if _sha256(bytes) != SPEC_SHA256:
		return _failure("TOLINA_SPEC_INVALID", "The Tolina specification does not match its reviewed digest.")
	var json := JSON.new()
	if json.parse(bytes.get_string_from_utf8()) != OK:
		return _failure("TOLINA_SPEC_INVALID", "The reviewed specification is not valid JSON.")
	var reason := validate_spec(json.data)
	if not reason.is_empty():
		return _failure("TOLINA_SPEC_INVALID", "Invalid reviewed Tolina specification: " + reason)
	var spec: Dictionary = json.data
	if not verify_asset_files(spec):
		return _failure("TOLINA_ASSET_INVALID", "An approved source PNG, import file or import mapping changed or is missing.")
	var textures := {}
	for row in spec.textures:
		# REUSE returns the normal immutable imported production resource.
		# Assigning it to a detached Sprite2D does not mutate this resource.
		var texture := ResourceLoader.load(row.path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE)
		var config := ConfigFile.new()
		if config.load(row.path + ".import") != OK:
			return _failure("TOLINA_ASSET_INVALID", "The approved import mapping is unreadable.")
		if not texture is Texture2D or texture.get_class() != "CompressedTexture2D" \
				or texture.get_script() != null or texture.resource_path != row.path \
				or texture.get_load_path() != config.get_value("remap", "path", "") \
				or texture.get_width() != int(row.size_px[0]) or texture.get_height() != int(row.size_px[1]):
			return _failure("TOLINA_ASSET_INVALID", "An approved texture has an unexpected native type, path or dimensions.")
		textures[row.id] = texture
	return {"ok": true, "spec": spec, "textures": textures,
		"snapshots": resource_states(textures), "error": null}


static func validate_spec(value: Variant) -> String:
	if not _closed(value, ["schema_version", "rig_id", "textures", "groups", "pieces"]):
		return "top-level closed schema"
	if not _integer(value.schema_version, 1, 1) or value.rig_id != "tolina_character_rig_v1":
		return "schema version or rig identity"
	if not value.textures is Array or value.textures.size() != 15 \
			or not value.groups is Array or value.groups.size() != 3 \
			or not value.pieces is Array or value.pieces.size() != 16:
		return "bounded fixture counts"
	var textures := {}
	for row in value.textures:
		if not _closed(row, ["id", "path", "source_sha256", "import_sha256", "size_px"]) \
				or not row.id is String or not TEXTURES.has(row.id) or textures.has(row.id):
			return "texture schema or duplicate/unapproved ID"
		if not row.path is String or row.path != TEXTURE_PREFIX + TEXTURES[row.id][0] \
				or row.path.simplify_path() != row.path or not _hash(row.source_sha256) or not _hash(row.import_sha256):
			return "redirected texture path or hash"
		if not _vec(row.size_px, 1, 2048) or not _integer(row.size_px[0], 1, 2048) \
				or not _integer(row.size_px[1], 1, 2048) or _vector(row.size_px) != Vector2(TEXTURES[row.id][1]):
			return "texture dimensions"
		textures[row.id] = row
	var ids := {}
	var nodes := {".": ""}
	for row in value.groups:
		if not _closed(row, ["id", "parent", "position_px", "rotation_rad", "scale"]) \
				or not _identity(row, ids) or not _transform_valid(row):
			return "group schema, identity or transform"
		var path: String = row.id if row.parent == "." else row.parent + "/" + row.id
		if not MANIFEST.has(path) or MANIFEST[path] != "Node2D" or path == "." or nodes.has(path):
			return "unapproved group path"
		nodes[path] = row.parent
	for row in value.pieces:
		if not _closed(row, ["id", "parent", "texture", "position_px", "rotation_rad", "scale", "pivot_px", "z_index", "alpha", "region_px"]) \
				or not _identity(row, ids) or not _transform_valid(row) or not _vec(row.pivot_px, -8192, 8192):
			return "piece schema, identity or transform"
		var path: String = row.parent + "/" + row.id
		if not MANIFEST.has(path) or MANIFEST[path] != "Sprite2D" or nodes.has(path) \
				or not row.texture is String or not textures.has(row.texture):
			return "unapproved piece path or texture"
		if not _integer(row.z_index, -32, 32) or not _number(row.alpha, 0, 1):
			return "z-index or alpha"
		if row.region_px != null:
			if not row.region_px is Array or row.region_px.size() != 4:
				return "region schema"
			for number in row.region_px:
				if not _integer(number, 0, 2048):
					return "region bounds"
			var region: Array = row.region_px
			var size: Array = textures[row.texture].size_px
			if region[2] <= 0 or region[3] <= 0 or region[0] + region[2] > size[0] or region[1] + region[3] > size[1]:
				return "region outside texture"
		nodes[path] = row.parent
	# Resolve parents independently of declaration order and detect any cycle.
	for path in nodes:
		if path == ".":
			continue
		var cursor: String = path
		var seen := {}
		var depth := 0
		while cursor != ".":
			if seen.has(cursor) or not nodes.has(cursor) or depth >= 8:
				return "unresolved parent, cycle or depth"
			seen[cursor] = true
			cursor = nodes[cursor]
			depth += 1
		if not nodes.has(nodes[path]) or (nodes[path] != "." and MANIFEST[nodes[path]] != "Node2D"):
			return "non-group parent"
	return ""


static func verify_asset_files(spec: Dictionary) -> bool:
	if not validate_spec(spec).is_empty():
		return false
	for row in spec.textures:
		if not _unlinked_path(row.path) or not _unlinked_path(row.path + ".import") \
				or not FileAccess.file_exists(row.path) or not FileAccess.file_exists(row.path + ".import"):
			return false
		if FileAccess.get_sha256(row.path) != row.source_sha256 \
				or FileAccess.get_sha256(row.path + ".import") != row.import_sha256:
			return false
		var config := ConfigFile.new()
		if config.load(row.path + ".import") != OK \
				or config.get_value("remap", "type", "") != "CompressedTexture2D" \
				or config.get_value("deps", "source_file", "") != row.path \
				or config.get_value("params", "compress/mode", -1) != 0 \
				or config.get_value("params", "mipmaps/generate", true) \
				or config.get_value("params", "process/size_limit", -1) != 0:
			return false
		var imported: String = config.get_value("remap", "path", "")
		if not imported.begins_with("res://.godot/imported/") or not imported.ends_with(".ctex") \
				or imported.simplify_path() != imported or not FileAccess.file_exists(imported) or not _unlinked_path(imported) \
				or config.get_value("deps", "dest_files", []) != [imported]:
			return false
	return true


static func prepare(spec: Dictionary, textures: Dictionary) -> Node2D:
	if not validate_spec(spec).is_empty() or textures.size() != 15:
		return null
	var rig := Node2D.new()
	rig.name = RIG_NAME
	var groups := {}
	var pieces := {}
	for row in spec.groups:
		groups[row.id if row.parent == "." else row.parent + "/" + row.id] = row
	for row in spec.pieces:
		pieces[row.parent + "/" + row.id] = row
	# Manifest order is the reviewed draw/sibling order, not JSON array order.
	for path in MANIFEST:
		if path == ".":
			continue
		var node: Node
		if MANIFEST[path] == "AnimationPlayer":
			node = AnimationPlayer.new()
			node.name = "AnimationPlayer"
		elif MANIFEST[path] == "Node2D":
			var row: Dictionary = groups[path]
			node = Node2D.new()
			node.name = row.id
			_set_transform(node, row)
		else:
			var row: Dictionary = pieces[path]
			if not textures.get(row.texture) is Texture2D:
				rig.free()
				return null
			var sprite := Sprite2D.new()
			sprite.name = row.id
			_set_transform(sprite, row)
			sprite.texture = textures[row.texture]
			sprite.centered = false
			# Region pivots are local to the cropped rectangle. The crop origin
			# selects source pixels only; it is never added to destination position.
			sprite.offset = -_vector(row.pivot_px)
			sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
			sprite.z_index = int(row.z_index)
			sprite.modulate = Color(1, 1, 1, float(row.alpha))
			sprite.self_modulate = Color.WHITE
			sprite.visible = true
			sprite.region_enabled = row.region_px != null
			sprite.region_rect = _region(row.region_px)
			sprite.region_filter_clip_enabled = false
			node = sprite
		var parent_path: String = path.get_base_dir()
		var parent: Node = rig if parent_path.is_empty() else rig.get_node(NodePath(parent_path))
		parent.add_child(node)
	return rig


static func verify(rig: Node, owner_root: Node, spec: Dictionary,
		textures: Dictionary, empty_player := true) -> bool:
	if not is_instance_valid(rig) or rig.name != RIG_NAME \
			or not validate_spec(spec).is_empty() or textures.size() != 15:
		return false
	var rows := {".": {"position_px": [0, 0], "rotation_rad": 0, "scale": [1, 1]}}
	for row in spec.groups + spec.pieces:
		rows[row.id if row.parent == "." else row.parent + "/" + row.id] = row
	var stack: Array[Node] = [rig]
	var count := 0
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var path := String(rig.get_path_to(node))
		if not MANIFEST.has(path) or node.get_class() != MANIFEST[path] \
				or node.get_script() != null or node.owner != owner_root:
			return false
		var children: Array = []
		for child in node.get_children(true):
			children.append(String(child.name))
			stack.append(child)
		if children != CHILDREN.get(path, []):
			return false
		if node is Node2D:
			var row: Dictionary = rows[path]
			if not _transform_matches(node, row) or not _canvas_matches(node):
				return false
		if node is Sprite2D:
			var row: Dictionary = rows[path]
			if not _sprite_matches(node, row, textures):
				return false
		count += 1
	if count != 21:
		return false
	var body: Sprite2D = rig.get_node("Visual/Body")
	var shoulder: Sprite2D = rig.get_node("Visual/ShoulderOverlap")
	if body.texture != shoulder.texture or shoulder.get_rect() != Rect2(0, 0, 170, 95) \
			or body.to_global(Vector2(530, 325)) != shoulder.to_global(Vector2.ZERO):
		return false
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	if player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig:
		return false
	return not empty_player or (AnimationWriter.pristine(player)
		and player.get_animation_library_list().is_empty() and player.get_animation_list().is_empty()
		and not player.has_animation_library(&"") and not player.has_animation(&"RESET"))


static func resource_state(texture: Texture2D) -> Dictionary:
	if not is_instance_valid(texture):
		return {}
	var image := texture.get_image()
	return {"id": texture.get_instance_id(), "class": texture.get_class(),
		"script": texture.get_script(), "path": texture.resource_path,
		"stored": AnimationWriter.stored(texture), "metadata": _metadata(texture),
		"load_path": texture.get_load_path() if texture is CompressedTexture2D else "",
		"width": texture.get_width(), "height": texture.get_height(), "rid": texture.get_rid(),
		"production_external_id": texture.get_id_for_path(PRODUCTION_PATH),
		"image_format": image.get_format() if image != null else -1,
		"image_mipmaps": image.has_mipmaps() if image != null else false,
		"image_sha256": _sha256(image.get_data()) if image != null else ""}


static func resource_states(textures: Dictionary) -> Dictionary:
	var states := {}
	for id in textures:
		states[id] = resource_state(textures[id])
	return states


static func verify_assets(spec: Dictionary, textures: Dictionary, snapshots: Dictionary) -> bool:
	return verify_asset_files(spec) and resource_states(textures) == snapshots


static func prepare_blink() -> AnimationLibrary:
	var animation := Animation.new()
	animation.length = 0.24
	animation.step = 0.125
	animation.loop_mode = Animation.LOOP_NONE
	var times := blink_times()
	for index in range(3):
		var track := animation.add_track(Animation.TYPE_VALUE)
		animation.track_set_path(track, BLINK_PATHS[index])
		animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR)
		animation.track_set_interpolation_loop_wrap(track, false)
		animation.value_track_set_update_mode(track, Animation.UPDATE_CONTINUOUS)
		animation.track_set_enabled(track, true)
		animation.track_set_imported(track, false)
		for key in range(6):
			animation.track_insert_key(track, times[key], BLINK_VALUES[index][key], 1.0)
	var library := AnimationLibrary.new()
	return library if library.add_animation(BLINK_NAME, animation) == OK else null


static func blink_times() -> PackedFloat32Array:
	# Animation serializes key times as real_t. Canonicalize once before insertion
	# so exact native create/redo/save/reopen comparisons use the same values.
	return PackedFloat32Array([0.0, 0.05, 0.095, 0.14, 0.19, 0.24])


static func verify_blink(library: AnimationLibrary) -> String:
	if library == null or library.get_class() != "AnimationLibrary" or library.get_script() != null:
		return "library"
	var names := library.get_animation_list()
	if names.size() != 1 or names[0] != BLINK_NAME:
		return "animation names"
	var animation := library.get_animation(BLINK_NAME)
	if animation == null or animation.get_class() != "Animation" or animation.get_script() != null:
		return "animation"
	if animation.length != 0.24 or animation.step != 0.125 or animation.loop_mode != Animation.LOOP_NONE or animation.capture_included:
		return "timing"
	if animation.get_track_count() != 3 or not animation.get_marker_names().is_empty():
		return "tracks or markers"
	var times := blink_times()
	for track in range(3):
		if animation.track_get_type(track) != Animation.TYPE_VALUE or animation.track_get_path(track) != BLINK_PATHS[track]:
			return "target"
		if animation.track_get_interpolation_type(track) != Animation.INTERPOLATION_LINEAR \
				or animation.value_track_get_update_mode(track) != Animation.UPDATE_CONTINUOUS:
			return "interpolation"
		if not animation.track_is_enabled(track) or animation.track_is_imported(track) or animation.track_get_interpolation_loop_wrap(track):
			return "flags"
		if animation.track_get_key_count(track) != 6:
			return "key count"
		for key in range(6):
			var value: Variant = animation.track_get_key_value(track, key)
			if animation.track_get_key_time(track, key) != times[key] \
					or typeof(value) != TYPE_FLOAT or not _number(value, 0.0, 1.0) \
					or value != BLINK_VALUES[track][key] \
					or animation.track_get_key_transition(track, key) != 1.0:
				return "typed keys"
		for endpoint in [0, 5]:
			var value: Variant = animation.value_track_interpolate(track, times[endpoint])
			if typeof(value) != TYPE_FLOAT or not _number(value, 0.0, 1.0) \
					or value != BLINK_VALUES[track][endpoint]:
				return "rest endpoints"
	# Inspect detached interpolation data only. Never seek/play/assign a player.
	# Godot 4.7.2's approximate key lookup can extrapolate immediately before a
	# key. The approved fixture proves strict key/rest alpha bounds; it does not
	# claim bounded native playback interpolation or clamp/change the recipe.
	for sample in range(97):
		var time: float = float(times[5]) * sample / 96.0
		var sum := 0.0
		for track in range(3):
			var alpha: float = animation.value_track_interpolate(track, time)
			if not is_finite(alpha):
				return "nonfinite interpolation"
			sum += alpha
		if absf(sum - 1.0) > 0.000001:
			return "opacity sum"
	return ""


static func verify_blink_targets(rig: Node) -> bool:
	if not is_instance_valid(rig):
		return false
	var player := rig.get_node_or_null("AnimationPlayer") as AnimationPlayer
	if player == null or player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig:
		return false
	for index in range(3):
		var path: NodePath = BLINK_PATHS[index]
		var node := rig.get_node_or_null(NodePath(String(path.get_concatenated_names())))
		if not node is Sprite2D or node.get_class() != "Sprite2D" or node.get_script() != null:
			return false
		if rig.get_node_or_null(NodePath("Visual/Eyes/" + ["Rest", "Half", "Closed"][index])) != node \
				or path.get_concatenated_subnames() != "modulate:a":
			return false
		var value: Variant = node.get_indexed(NodePath(":modulate:a"))
		if typeof(value) != TYPE_FLOAT or value != BLINK_VALUES[index][0] \
				or node.modulate != Color(1, 1, 1, BLINK_VALUES[index][0]) or node.self_modulate != Color.WHITE:
			return false
	return true


static func _set_transform(node: Node2D, row: Dictionary) -> void:
	node.position = _vector(row.position_px)
	node.rotation = float(row.rotation_rad)
	node.scale = _vector(row.scale)


static func _transform_matches(node: Node2D, row: Dictionary) -> bool:
	# Compare native real_t values without epsilon. Rotation's native setter
	# also canonicalizes to real_t, unlike JSON's double-precision numbers.
	var expected := Node2D.new()
	_set_transform(expected, row)
	var same := node.position == expected.position and node.rotation == expected.rotation \
		and node.scale == expected.scale and node.transform == expected.transform and node.skew == 0.0
	expected.free()
	return same


static func _canvas_matches(node: Node2D) -> bool:
	return node.visible and node.self_modulate == Color.WHITE and node.material == null \
		and not node.use_parent_material and node.texture_repeat == CanvasItem.TEXTURE_REPEAT_PARENT_NODE \
		and (node is Sprite2D or node.texture_filter == CanvasItem.TEXTURE_FILTER_PARENT_NODE) \
		and not node.top_level and node.clip_children == CanvasItem.CLIP_CHILDREN_DISABLED \
		and node.light_mask == 1 and node.visibility_layer == 1 \
		and not node.show_behind_parent and not node.y_sort_enabled and node.z_as_relative \
		and (node is Sprite2D or (node.modulate == Color.WHITE and node.z_index == 0))


static func _sprite_matches(sprite: Sprite2D, row: Dictionary, textures: Dictionary) -> bool:
	var texture: Variant = textures.get(row.texture)
	return texture is Texture2D and texture.get_class() == "CompressedTexture2D" \
		and texture.get_script() == null and texture.resource_path == TEXTURE_PREFIX + TEXTURES[row.texture][0] \
		and sprite.texture == texture and not sprite.centered and sprite.offset == -_vector(row.pivot_px) \
		and sprite.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR and sprite.z_index == int(row.z_index) \
		and sprite.modulate == Color(1, 1, 1, float(row.alpha)) and sprite.self_modulate == Color.WHITE \
		and not sprite.flip_h and not sprite.flip_v and sprite.hframes == 1 and sprite.vframes == 1 \
		and sprite.frame == 0 and sprite.frame_coords == Vector2i.ZERO \
		and sprite.region_enabled == (row.region_px != null) and sprite.region_rect == _region(row.region_px) \
		and not sprite.region_filter_clip_enabled


static func _metadata(resource: Resource) -> Dictionary:
	var values := {}
	for name in resource.get_meta_list():
		values[name] = resource.get_meta(name)
	return values.duplicate(true)


static func _closed(value: Variant, keys: Array) -> bool:
	if not value is Dictionary or value.size() != keys.size():
		return false
	for key in keys:
		if not value.has(key):
			return false
	return true


static func _identity(row: Dictionary, ids: Dictionary) -> bool:
	if not row.id is String or not row.parent is String or row.id.is_empty() \
			or ids.has(row.id) or row.id.contains("/") or row.id.contains(":") \
			or row.id in [".", "..", "AnimationPlayer", "TolinaRig"]:
		return false
	ids[row.id] = true
	return true


static func _transform_valid(row: Dictionary) -> bool:
	return _vec(row.position_px, -8192, 8192) and _number(row.rotation_rad, -PI, PI) \
		and _vec(row.scale, 0.0001, 8)


static func _number(value: Variant, minimum: float, maximum: float) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value)) \
		and float(value) >= minimum and float(value) <= maximum


static func _integer(value: Variant, minimum: int, maximum: int) -> bool:
	return _number(value, minimum, maximum) and float(value) == floorf(float(value))


static func _vec(value: Variant, minimum: float, maximum: float) -> bool:
	return value is Array and value.size() == 2 \
		and _number(value[0], minimum, maximum) and _number(value[1], minimum, maximum)


static func _vector(value: Array) -> Vector2:
	return Vector2(float(value[0]), float(value[1]))


static func _region(value: Variant) -> Rect2:
	return Rect2() if value == null else Rect2(float(value[0]), float(value[1]), float(value[2]), float(value[3]))


static func _hash(value: Variant) -> bool:
	if not value is String or value.length() != 64:
		return false
	for character in value:
		if not "0123456789abcdef".contains(character):
			return false
	return true


static func _unlinked_path(path: String) -> bool:
	var current := ProjectSettings.globalize_path(path).simplify_path().replace("\\", "/")
	while true:
		var parent := current.get_base_dir()
		if parent == current or parent.is_empty():
			return true
		var directory := DirAccess.open(parent)
		if directory == null or directory.is_link(current):
			return false
		current = parent
	return false


static func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA256) != OK or context.update(bytes) != OK:
		return ""
	return context.finish().hex_encode()


static func _failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "spec": null, "textures": null, "snapshots": null,
		"error": {"code": code, "message": message}}
