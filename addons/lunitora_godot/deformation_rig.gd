@tool
extends RefCounted
## Reviewed three-station fixture. Shared editor admission/history/session state
## belongs to RigLab; the weighted primitive owns only explicit mesh data.

const WeightedMesh = preload("res://addons/lunitora_godot/weighted_mesh_2d.gd")
const AnimationWriter = preload("res://addons/lunitora_godot/animation_writer.gd")
const CharacterRig = preload("res://addons/lunitora_godot/character_rig.gd")
const LAB_PATH := "res://addons/lunitora_godot/labs/rig_test_cat_deformation_lab.tscn"
const ROOT_NAME := "RigTestCatDeformationLab"
const RIG_NAME := "RigTestCatRig"
const ACTION_NAME := "Lunitora: Create Rig Test Cat Deformation Rig"
const DEMO_ACTION_NAME := "Lunitora: Create Rig Test Cat Deformation Demo"
const DEMO_NAME := &"deformation_demo"
const SPEC_PATH := "res://addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
# Pin reviewed bytes outside the JSON; no MCP client can provide a recipe.
const SPEC_SHA256 := "459b16ecf4367ef7c9254961a223a0c7ac0d56e79bc9bbc63b5b89e47b700571"
const SPEC_LIMIT := 262144
const TEXTURE_PREFIX := "res://addons/lunitora_godot/test_assets/rig_test_cat/"
const USED_TEXTURES := ["tail", "arm_upper_l", "arm_lower_paw_l", "torso", "head_full", "scarf_foreground"]
const TEXTURES := {
	"full_front": ["reference/rig_test_cat_full_front.png", Vector2i(1122, 1402)],
	"torso": ["body/rig_test_cat_torso.png", Vector2i(1122, 1402)],
	"head_full": ["body/rig_test_cat_head_full.png", Vector2i(1254, 1254)],
	"scarf_foreground": ["body/rig_test_cat_scarf_foreground.png", Vector2i(288, 147)],
	"cape": ["body/rig_test_cat_cape.png", Vector2i(1086, 1448)],
	"arm_upper_l": ["arms/rig_test_cat_arm_upper_l.png", Vector2i(1254, 1254)],
	"arm_upper_r": ["arms/rig_test_cat_arm_upper_r.png", Vector2i(1254, 1254)],
	"arm_lower_paw_l": ["arms/rig_test_cat_arm_lower_paw_l.png", Vector2i(1254, 1254)],
	"arm_lower_paw_r": ["arms/rig_test_cat_arm_lower_paw_r.png", Vector2i(1254, 1254)],
	"leg_upper_l": ["legs/rig_test_cat_leg_upper_l.png", Vector2i(383, 454)],
	"leg_upper_r": ["legs/rig_test_cat_leg_upper_r.png", Vector2i(383, 454)],
	"leg_lower_foot_l": ["legs/rig_test_cat_leg_lower_foot_l.png", Vector2i(331, 477)],
	"leg_lower_foot_r": ["legs/rig_test_cat_leg_lower_foot_r.png", Vector2i(331, 477)],
	"tail": ["tail/rig_test_cat_tail.png", Vector2i(1086, 1448)],
	"eyes_idle": ["eyes/rig_test_cat_eyes_idle.png", Vector2i(700, 291)],
	"eyes_open": ["eyes/rig_test_cat_eyes_open.png", Vector2i(700, 291)],
	"eyes_blink_mid": ["eyes/rig_test_cat_eyes_blink_mid.png", Vector2i(700, 291)],
	"eyes_closed": ["eyes/rig_test_cat_eyes_closed.png", Vector2i(700, 291)],
	"eyes_surprised": ["eyes/rig_test_cat_eyes_surprised.png", Vector2i(700, 291)],
	"mouth_neutral": ["mouths/rig_test_cat_mouth_neutral.png", Vector2i(445, 306)],
	"mouth_smile": ["mouths/rig_test_cat_mouth_smile.png", Vector2i(445, 306)],
	"mouth_frown": ["mouths/rig_test_cat_mouth_frown.png", Vector2i(445, 306)],
	"mouth_talk_open": ["mouths/rig_test_cat_mouth_talk_open.png", Vector2i(445, 306)],
	"mouth_surprised": ["mouths/rig_test_cat_mouth_surprised.png", Vector2i(445, 306)]}
const MANIFEST := {".": "Node2D", "TailStation": "Node2D",
	"TailStation/TailMesh": "Polygon2D", "TailStation/TailSkeleton": "Skeleton2D",
	"TailStation/TailSkeleton/TailRoot": "Bone2D",
	"TailStation/TailSkeleton/TailRoot/TailMid1": "Bone2D",
	"TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2": "Bone2D",
	"TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip": "Bone2D",
	"ArmStation": "Node2D", "ArmStation/Shoulder": "Node2D",
	"ArmStation/Shoulder/UpperArm": "Sprite2D",
	"ArmStation/Shoulder/UpperArm/Elbow": "Node2D",
	"ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw": "Sprite2D",
	"BodyStation": "Node2D", "BodyStation/Torso": "Sprite2D",
	"BodyStation/HeadPivot": "Node2D", "BodyStation/HeadPivot/Head": "Sprite2D",
	"BodyStation/ScarfForeground": "Sprite2D",
	"AnimationPlayer": "AnimationPlayer"}
const CHILDREN := {".": ["TailStation", "ArmStation", "BodyStation", "AnimationPlayer"],
	"TailStation": ["TailMesh", "TailSkeleton"], "TailStation/TailSkeleton": ["TailRoot"],
	"TailStation/TailSkeleton/TailRoot": ["TailMid1"],
	"TailStation/TailSkeleton/TailRoot/TailMid1": ["TailMid2"],
	"TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2": ["TailTip"],
	"ArmStation": ["Shoulder"], "ArmStation/Shoulder": ["UpperArm"],
	"ArmStation/Shoulder/UpperArm": ["Elbow"],
	"ArmStation/Shoulder/UpperArm/Elbow": ["LowerArmPaw"],
	"BodyStation": ["Torso", "HeadPivot", "ScarfForeground"], "BodyStation/HeadPivot": ["Head"]}
const BONE_PATHS := ["TailRoot", "TailRoot/TailMid1", "TailRoot/TailMid1/TailMid2",
	"TailRoot/TailMid1/TailMid2/TailTip"]
const BONE_ORIGINS := [Vector2(160, 1280), Vector2(450, -90), Vector2(180, -400), Vector2(-50, -370)]
const BONE_ANCHORS := [Vector2(160, 1280), Vector2(610, 1190), Vector2(790, 790), Vector2(740, 420)]
const BONE_LENGTHS := [458.9117562233506, 438.63424398922615, 373.3630940518894, 276.81221071332817]
const BONE_ANGLES := [-0.19739553332328796, -1.1479424238204956, -1.7051178216934204, -1.2204819917678833]
const DEMO_PATHS := [NodePath("TailStation/TailSkeleton/TailRoot:rotation"),
	NodePath("TailStation/TailSkeleton/TailRoot/TailMid1:rotation"),
	NodePath("TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2:rotation"),
	NodePath("TailStation/TailSkeleton/TailRoot/TailMid1/TailMid2/TailTip:rotation"),
	NodePath("ArmStation/Shoulder:rotation"),
	NodePath("ArmStation/Shoulder/UpperArm/Elbow:rotation"), NodePath("BodyStation/HeadPivot:position:y")]
const DEMO_VALUES := [[0.0, 0.03490658503988659, -0.03490658503988659, 0.01745329251994329, 0.0],
	[0.0, 0.06981317007977318, -0.06981317007977318, 0.03490658503988659, 0.0],
	[0.0, 0.10471975511965978, -0.10471975511965978, 0.05235987755982989, 0.0],
	[0.0, 0.10471975511965978, -0.10471975511965978, 0.05235987755982989, 0.0],
	[0.0, 0.20943951023931956, 0.10471975511965978, 0.05235987755982989, 0.0],
	[0.87026, 1.044792925199433, 1.219325850398866, 1.044792925199433, 0.87026],
	[306.0, 300.0, 294.0, 300.0, 306.0]]


static func load_spec() -> Dictionary:
	if not CharacterRig._unlinked_path(SPEC_PATH):
		return _failure("DEFORMATION_SPEC_INVALID", "The reviewed specification path is redirected.")
	var file := FileAccess.open(SPEC_PATH, FileAccess.READ)
	if file == null or file.get_length() > SPEC_LIMIT:
		return _failure("DEFORMATION_SPEC_INVALID", "The reviewed deformation specification is missing or exceeds its bound.")
	var bytes := file.get_buffer(file.get_length())
	file.close()
	if CharacterRig._sha256(bytes) != SPEC_SHA256:
		return _failure("DEFORMATION_SPEC_INVALID", "The deformation specification does not match its reviewed digest.")
	var parser := JSON.new()
	if parser.parse(bytes.get_string_from_utf8()) != OK:
		return _failure("DEFORMATION_SPEC_INVALID", "The reviewed deformation specification is not valid JSON.")
	var reason := validate_spec(parser.data)
	if not reason.is_empty():
		return _failure("DEFORMATION_SPEC_INVALID", "Invalid reviewed deformation specification: " + reason)
	return {"ok": true, "spec": parser.data, "textures": null, "snapshots": null, "error": null}


static func load_assets(spec: Dictionary) -> Dictionary:
	if not verify_asset_files(spec):
		return _failure("DEFORMATION_ASSET_INVALID", "An approved fixture PNG, import file, UID, setting or mapping changed or is missing.")
	var textures := {}
	for row in spec.textures:
		if not row.id in USED_TEXTURES:
			continue
		var texture := ResourceLoader.load(row.path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE)
		if not _texture_matches(texture, row):
			return _failure("DEFORMATION_ASSET_INVALID", "An approved fixture texture has an unexpected native type, path or dimensions.")
		textures[row.id] = texture
	return {"ok": true, "spec": spec, "textures": textures, "snapshots": resource_states(textures), "error": null}


static func read_spec() -> Dictionary:
	var loaded := load_spec()
	return loaded if not loaded.ok else load_assets(loaded.spec)


static func validate_spec(value: Variant) -> String:
	if not CharacterRig._closed(value, ["schema_version", "rig_id", "textures", "nodes", "mesh", "bones", "animation"]):
		return "top-level closed schema"
	if not CharacterRig._integer(value.schema_version, 1, 1) or value.rig_id != "rig_test_cat_deformation_v1":
		return "schema or fixture identity"
	if not value.textures is Array or value.textures.size() != 24 \
			or not value.nodes is Array or value.nodes.size() != 19 \
			or not value.bones is Array or value.bones.size() != 4:
		return "exact fixture counts"
	var ids := {}
	var uids := {}
	for row in value.textures:
		if not CharacterRig._closed(row, ["id", "path", "source_sha256", "import_sha256", "size_px", "uid", "import_path", "import_settings"]) \
				or not row.id is String or not TEXTURES.has(row.id) or ids.has(row.id):
			return "texture schema/ID"
		if not row.path is String or row.path != TEXTURE_PREFIX + TEXTURES[row.id][0] \
				or row.path.simplify_path() != row.path or not CharacterRig._hash(row.source_sha256) \
				or not CharacterRig._hash(row.import_sha256) or not CharacterRig._vec(row.size_px, 1, 2048) \
				or WeightedMesh.vector(row.size_px) != Vector2(TEXTURES[row.id][1]):
			return "texture path/hash/dimensions"
		if not row.uid is String or ResourceUID.text_to_id(row.uid) == ResourceUID.INVALID_ID \
				or uids.has(row.uid) or not row.import_settings is Dictionary or row.import_settings.is_empty():
			return "UID or import settings"
		var expected_import: String = "res://.godot/imported/" + row.path.get_file() + "-" + row.path.md5_text() + ".ctex"
		if row.import_path != expected_import:
			return "path-derived imported resource"
		ids[row.id] = true
		uids[row.uid] = true
	var paths := {}
	for row in value.nodes:
		if not row is Dictionary or not row.has("class"):
			return "node schema"
		var keys := ["path", "class", "position_px", "rotation_rad", "scale"]
		if row.class == "Sprite2D":
			keys.append_array(["texture", "pivot_px", "z_index"])
		if not CharacterRig._closed(row, keys) or not row.path is String \
				or not MANIFEST.has(row.path) or MANIFEST[row.path] != row.class or paths.has(row.path) \
				or not CharacterRig._vec(row.position_px, -8192, 8192) \
				or not CharacterRig._number(row.rotation_rad, -PI, PI) or not CharacterRig._vec(row.scale, 0.0001, 8):
			return "node identity or transform"
		if row.class == "Sprite2D" and (not row.texture is String or not row.texture in USED_TEXTURES \
				or not CharacterRig._vec(row.pivot_px, -8192, 8192) or not CharacterRig._integer(row.z_index, -32, 32)):
			return "sprite texture/pivot/layer"
		if row.path == "BodyStation/ScarfForeground" and (row.texture != "scarf_foreground" \
				or WeightedMesh.vector(row.pivot_px) != Vector2(139, -238) or row.z_index != 1 \
				or WeightedMesh.vector(row.position_px) != Vector2.ZERO \
				or row.rotation_rad != 0.0 or WeightedMesh.vector(row.scale) != Vector2.ONE):
			return "fixed scarf foreground sprite registration/layer"
		paths[row.path] = true
	if paths.size() != MANIFEST.size():
		return "incomplete fixture hierarchy"
	var mesh_reason := WeightedMesh.validate(value.mesh)
	if not mesh_reason.is_empty():
		return "explicit mesh: " + mesh_reason
	if value.mesh.vertices_px.size() != 561 or value.mesh.uv_px != value.mesh.vertices_px \
			or value.mesh.triangles.size() != 1024 or value.mesh.internal_vertex_count != 465 \
			or value.mesh.bone_paths != BONE_PATHS or value.mesh.weights.size() != 4 \
			or value.mesh.skeleton_path != "../TailSkeleton":
		return "exact tail topology/bindings"
	for vertex in range(561):
		var influences := 0
		for row in value.mesh.weights:
			if float(row[vertex]) > 0.0:
				influences += 1
		if influences > 2:
			return "fixture influence count"
	for index in range(4):
		var bone: Variant = value.bones[index]
		if not CharacterRig._closed(bone, ["path", "origin_px", "length", "angle_rad"]) \
				or bone.path != BONE_PATHS[index] or not CharacterRig._vec(bone.origin_px, -8192, 8192) \
				or WeightedMesh.vector(bone.origin_px) != BONE_ORIGINS[index] \
				or bone.length != BONE_LENGTHS[index] or bone.angle_rad != BONE_ANGLES[index]:
			return "bone origin/length/angle"
	var animation: Variant = value.animation
	if not CharacterRig._closed(animation, ["name", "length", "step", "times", "transition", "paths", "values"]) \
			or animation.name != String(DEMO_NAME) or animation.length != 2.0 or animation.step != 0.125 \
			or animation.times != [0.0, 0.5, 1.0, 1.5, 2.0] or animation.transition != -2.0 \
			or animation.values != DEMO_VALUES or not animation.paths is Array or animation.paths.size() != 7:
		return "fixed animation recipe"
	for index in range(7):
		if animation.paths[index] != String(DEMO_PATHS[index]):
			return "fixed animation path"
	return ""


static func verify_asset_files(spec: Dictionary) -> bool:
	if not validate_spec(spec).is_empty():
		return false
	for row in spec.textures:
		if not CharacterRig._unlinked_path(row.path) or not CharacterRig._unlinked_path(row.path + ".import") \
				or FileAccess.get_sha256(row.path) != row.source_sha256 \
				or FileAccess.get_sha256(row.path + ".import") != row.import_sha256:
			return false
		var config := ConfigFile.new()
		if config.load(row.path + ".import") != OK or config.get_value("remap", "importer", "") != "texture" \
				or config.get_value("remap", "type", "") != "CompressedTexture2D" \
				or config.get_value("remap", "uid", "") != row.uid \
				or config.get_value("remap", "path", "") != row.import_path \
				or config.get_value("deps", "source_file", "") != row.path \
				or config.get_value("deps", "dest_files", []) != [row.import_path] \
				or not FileAccess.file_exists(row.import_path) or not CharacterRig._unlinked_path(row.import_path):
			return false
		if config.get_section_keys("params").size() != row.import_settings.size():
			return false
		for key in row.import_settings:
			if not config.has_section_key("params", key) or config.get_value("params", key) != row.import_settings[key]:
				return false
	return true


static func prepare(spec: Dictionary, textures: Dictionary) -> Node2D:
	if not validate_spec(spec).is_empty() or not _loaded_assets_match(spec, textures):
		return null
	var rig := Node2D.new()
	rig.name = RIG_NAME
	rig.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	var rows := _node_rows(spec)
	for path in MANIFEST:
		if path == ".":
			continue
		var node: Node
		var row: Dictionary = rows[path]
		match MANIFEST[path]:
			"AnimationPlayer":
				node = AnimationPlayer.new()
			"Polygon2D":
				node = WeightedMesh.prepare(spec.mesh, textures.tail)
			"Skeleton2D":
				node = Skeleton2D.new()
			"Bone2D":
				var index := BONE_PATHS.find(path.trim_prefix("TailStation/TailSkeleton/"))
				var bone := Bone2D.new()
				bone.set_autocalculate_length_and_angle(false)
				bone.rest = Transform2D(0.0, BONE_ORIGINS[index])
				bone.set_length(BONE_LENGTHS[index])
				bone.set_bone_angle(BONE_ANGLES[index])
				node = bone
			"Sprite2D":
				var sprite := Sprite2D.new()
				sprite.texture = textures[row.texture]
				sprite.centered = false
				sprite.offset = -WeightedMesh.vector(row.pivot_px)
				sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
				sprite.z_index = int(row.z_index)
				node = sprite
			_:
				node = Node2D.new()
		if node == null:
			rig.free()
			return null
		node.name = path.get_file()
		if node is Node2D:
			_set_transform(node, row)
		var parent_path: String = path.get_base_dir()
		var parent: Node = rig if parent_path.is_empty() else rig.get_node(NodePath(parent_path))
		parent.add_child(node)
	return rig


static func observer_gate(rig: Node) -> Dictionary:
	if not is_instance_valid(rig):
		return _observer_failure("The deformation fixture is unavailable.")
	var mesh := rig.get_node_or_null("TailStation/TailMesh") as Polygon2D
	var skeleton := rig.get_node_or_null("TailStation/TailSkeleton") as Skeleton2D
	if mesh == null or skeleton == null or mesh.get_class() != "Polygon2D" \
			or skeleton.get_class() != "Skeleton2D" or mesh.get_script() != null \
			or skeleton.get_script() != null or mesh.skeleton != NodePath("../TailSkeleton") \
			or mesh.get_node_or_null(mesh.skeleton) != skeleton:
		return _observer_failure("The exact native deformation fixture identity is required.")
	# This inspection must precede Skeleton2D count/index getters, which may
	# flush queued setup and synchronously emit bone_setup_changed.
	for connection in skeleton.get_signal_connection_list(&"bone_setup_changed"):
		var callback: Callable = connection.callable
		if not callback.is_valid() or not callback.is_custom() or callback.get_object() != mesh \
				or String(callback.get_method()) != "Polygon2D::_skeleton_bone_setup_changed" \
				or connection.flags != 0 or callback.get_bound_arguments_count() != 0 \
				or callback.get_unbound_arguments_count() != 0:
			return _observer_failure("An unknown skeletal setup observer is attached; detach it before writing.")
	return {"ok": true, "error": null}


static func writer_observer_gate(rig: Node) -> Dictionary:
	# A setup getter can queue redraw, and a draw observer can mutate the rig
	# after synchronous post-verification. Structural inspection remains valid
	# with native editor UI attached, but writing admits no fixture draw observer.
	# Detachment must also pass the coordinator's normal-process quiet barrier.
	var setup := observer_gate(rig)
	if not setup.ok:
		return setup
	for path in ["TailStation/TailMesh", "BodyStation/ScarfForeground"]:
		var visual := rig.get_node_or_null(NodePath(path)) as CanvasItem
		if visual == null or visual.get_class() != MANIFEST[path] or visual.get_script() != null:
			return _observer_failure("The exact native fixture visuals are required.")
		if not visual.get_signal_connection_list(&"draw").is_empty():
			return _observer_failure("A " + String(visual.name) + " draw observer is attached. Deselect the item, detach relevant observers and allow normal editor frames to settle before a fresh request.")
	return {"ok": true, "error": null}


static func verify(rig: Node, owner_root: Node, spec: Dictionary,
		textures: Dictionary, empty_player := true) -> bool:
	if not is_instance_valid(rig) or rig.name != RIG_NAME or not validate_spec(spec).is_empty() \
			or not _loaded_assets_match(spec, textures) or not observer_gate(rig).ok:
		return false
	var rows := _node_rows(spec)
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
		if node.physics_interpolation_mode != (Node.PHYSICS_INTERPOLATION_MODE_OFF if path == "." else Node.PHYSICS_INTERPOLATION_MODE_INHERIT):
			return false
		if node is Node2D and (not _transform_matches(node, rows[path]) or not _canvas_matches(node)):
			return false
		if node is Sprite2D and not _sprite_matches(node, rows[path], textures):
			return false
		count += 1
	if count != 19:
		return false
	var mesh: Polygon2D = rig.get_node("TailStation/TailMesh")
	var skeleton: Skeleton2D = rig.get_node("TailStation/TailSkeleton")
	if not WeightedMesh.verify(mesh, spec.mesh, textures.tail) \
			or not WeightedMesh.verify_bindings(mesh, skeleton) or skeleton.get_modification_stack() != null:
		return false
	# observer_gate above has established that a setup flush can only notify
	# this fixture's exact native mesh redraw callback, never arbitrary code.
	if rig.is_inside_tree() and skeleton.get_bone_count() != 4:
		return false
	for index in range(4):
		var bone: Bone2D = skeleton.get_node(NodePath(BONE_PATHS[index]))
		var rest := Transform2D(0.0, BONE_ORIGINS[index])
		if bone.rest != rest or bone.transform != rest or bone.get_autocalculate_length_and_angle() \
				or bone.get_length() != _float32(BONE_LENGTHS[index]) \
				or bone.get_bone_angle() != _float32(BONE_ANGLES[index]):
			return false
		if rig.is_inside_tree() and (bone.get_index_in_skeleton() != index or skeleton.get_bone(index) != bone \
				or skeleton.to_local(bone.global_position) != BONE_ANCHORS[index]):
			return false
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	if player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig:
		return false
	return not empty_player or (AnimationWriter.pristine(player) \
		and player.get_animation_library_list().is_empty() and player.get_animation_list().is_empty() \
		and not player.has_animation_library(&"") and not player.has_animation(&"RESET"))


static func resource_states(textures: Dictionary) -> Dictionary:
	var states := {}
	for id in textures:
		var texture: Texture2D = textures[id]
		var image := texture.get_image()
		var metadata := {}
		for key in texture.get_meta_list():
			metadata[key] = texture.get_meta(key)
		states[id] = {"id": texture.get_instance_id(), "class": texture.get_class(),
			"script": texture.get_script(), "path": texture.resource_path,
			"stored": AnimationWriter.stored(texture), "metadata": metadata.duplicate(true),
			"load_path": texture.get_load_path() if texture is CompressedTexture2D else "",
			"width": texture.get_width(), "height": texture.get_height(), "rid": texture.get_rid(),
			"image_format": image.get_format() if image != null else -1,
			"image_mipmaps": image.has_mipmaps() if image != null else false,
			"image_sha256": CharacterRig._sha256(image.get_data()) if image != null else ""}
	return states


static func verify_assets(spec: Dictionary, textures: Dictionary, snapshots: Dictionary) -> bool:
	return verify_asset_files(spec) and _loaded_assets_match(spec, textures) and resource_states(textures) == snapshots


static func prepare_demo() -> AnimationLibrary:
	var animation := Animation.new()
	animation.length = 2.0
	animation.step = 0.125
	animation.loop_mode = Animation.LOOP_NONE
	for index in range(7):
		var track := animation.add_track(Animation.TYPE_VALUE)
		animation.track_set_path(track, DEMO_PATHS[index])
		animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR_ANGLE if index < 6 else Animation.INTERPOLATION_LINEAR)
		animation.track_set_interpolation_loop_wrap(track, false)
		animation.value_track_set_update_mode(track, Animation.UPDATE_CONTINUOUS)
		animation.track_set_enabled(track, true)
		animation.track_set_imported(track, false)
		for key in range(5):
			animation.track_insert_key(track, key * 0.5, DEMO_VALUES[index][key], -2.0)
	var library := AnimationLibrary.new()
	return library if library.add_animation(DEMO_NAME, animation) == OK else null


static func verify_demo(library: AnimationLibrary) -> String:
	if library == null or library.get_class() != "AnimationLibrary" or library.get_script() != null \
			or library.get_animation_list() != [DEMO_NAME]:
		return "library/names"
	var animation := library.get_animation(DEMO_NAME)
	if animation == null or animation.get_class() != "Animation" or animation.get_script() != null:
		return "native animation"
	if animation.length != 2.0 or animation.step != 0.125 or animation.loop_mode != Animation.LOOP_NONE \
			or animation.capture_included or not animation.get_marker_names().is_empty() or animation.get_track_count() != 7:
		return "timing/markers/tracks"
	for track in range(7):
		if animation.track_get_type(track) != Animation.TYPE_VALUE or animation.track_get_path(track) != DEMO_PATHS[track] \
				or animation.track_get_interpolation_type(track) != (Animation.INTERPOLATION_LINEAR_ANGLE if track < 6 else Animation.INTERPOLATION_LINEAR) \
				or animation.value_track_get_update_mode(track) != Animation.UPDATE_CONTINUOUS \
				or not animation.track_is_enabled(track) or animation.track_is_imported(track) \
				or animation.track_get_interpolation_loop_wrap(track) or animation.track_get_key_count(track) != 5:
			return "track target/settings/keys"
		for key in range(5):
			var value: Variant = animation.track_get_key_value(track, key)
			if animation.track_get_key_time(track, key) != key * 0.5 or typeof(value) != TYPE_FLOAT \
					or value != DEMO_VALUES[track][key] or animation.track_get_key_transition(track, key) != -2.0:
				return "exact typed key recipe"
		for segment in range(4):
			for fraction in [0.25, 0.5, 0.75]:
				var actual: float = animation.value_track_interpolate(track, segment * 0.5 + fraction * 0.5)
				var start: float = DEMO_VALUES[track][segment]
				var end: float = DEMO_VALUES[track][segment + 1]
				var expected := lerp_angle(start, end, ease(fraction, -2.0)) if track < 6 else lerpf(start, end, ease(fraction, -2.0))
				var difference := absf(wrapf(actual - expected, -PI, PI)) if track < 6 else absf(actual - expected)
				if not is_finite(actual) or difference > 0.000001:
					return "detached eased interpolation"
	return ""


static func verify_demo_targets(rig: Node) -> bool:
	if not is_instance_valid(rig) or not observer_gate(rig).ok:
		return false
	var player := rig.get_node_or_null("AnimationPlayer") as AnimationPlayer
	if player == null or player.root_node != NodePath("..") or player.get_node_or_null(player.root_node) != rig:
		return false
	for index in range(7):
		var path: NodePath = DEMO_PATHS[index]
		var node := rig.get_node_or_null(NodePath(String(path.get_concatenated_names())))
		if not node is Node2D or node.get_script() != null \
				or node.get_class() != ("Bone2D" if index < 4 else "Node2D"):
			return false
		var actual: Variant = node.get_indexed(NodePath(":" + String(path.get_concatenated_subnames())))
		var expected: float = _float32(DEMO_VALUES[index][0])
		if typeof(actual) != TYPE_FLOAT or actual != expected:
			return false
	return true


static func _loaded_assets_match(spec: Dictionary, textures: Dictionary) -> bool:
	for id in USED_TEXTURES:
		if not textures.has(id):
			return false
	for row in spec.textures:
		if textures.has(row.id) and not _texture_matches(textures[row.id], row):
			return false
	for id in textures:
		if not TEXTURES.has(id):
			return false
	return true


static func _texture_matches(texture: Variant, row: Dictionary) -> bool:
	return texture is Texture2D and texture.get_class() == "CompressedTexture2D" \
		and texture.get_script() == null and texture.resource_path == row.path \
		and texture.get_load_path() == row.import_path \
		and texture.get_size() == WeightedMesh.vector(row.size_px)


static func _node_rows(spec: Dictionary) -> Dictionary:
	var rows := {}
	for row in spec.nodes:
		rows[row.path] = row
	return rows


static func _set_transform(node: Node2D, row: Dictionary) -> void:
	node.position = WeightedMesh.vector(row.position_px)
	node.rotation = float(row.rotation_rad)
	node.scale = WeightedMesh.vector(row.scale)


static func _transform_matches(node: Node2D, row: Dictionary) -> bool:
	var expected := Node2D.new()
	_set_transform(expected, row)
	var same := node.position == expected.position and node.rotation == expected.rotation \
		and node.scale == expected.scale and node.transform == expected.transform and node.skew == 0.0
	expected.free()
	return same


static func _canvas_matches(node: Node2D) -> bool:
	return node.visible and node.modulate == Color.WHITE and node.self_modulate == Color.WHITE \
		and node.material == null and not node.use_parent_material and not node.top_level \
		and node.clip_children == CanvasItem.CLIP_CHILDREN_DISABLED and node.light_mask == 1 \
		and node.visibility_layer == 1 and not node.show_behind_parent and not node.y_sort_enabled \
		and node.z_as_relative and node.texture_repeat == CanvasItem.TEXTURE_REPEAT_PARENT_NODE \
		and (node is Sprite2D or node is Polygon2D or (node.z_index == 0 and node.texture_filter == CanvasItem.TEXTURE_FILTER_PARENT_NODE))


static func _sprite_matches(sprite: Sprite2D, row: Dictionary, textures: Dictionary) -> bool:
	return sprite.texture == textures[row.texture] and not sprite.centered \
		and sprite.offset == -WeightedMesh.vector(row.pivot_px) and sprite.z_index == int(row.z_index) \
		and sprite.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR and not sprite.flip_h and not sprite.flip_v \
		and sprite.hframes == 1 and sprite.vframes == 1 and sprite.frame == 0 \
		and sprite.frame_coords == Vector2i.ZERO and not sprite.region_enabled \
		and sprite.region_rect == Rect2() and not sprite.region_filter_clip_enabled


static func _float32(value: float) -> float:
	return PackedFloat32Array([value])[0]


static func _observer_failure(message: String) -> Dictionary:
	return {"ok": false, "error": {"code": "LAB_SKELETON_EDITOR_BUSY", "message": message}}


static func _failure(code: String, message: String) -> Dictionary:
	return {"ok": false, "spec": null, "textures": null, "snapshots": null,
		"error": {"code": code, "message": message}}
