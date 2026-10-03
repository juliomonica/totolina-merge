extends SceneTree
## Fixed assembled-cat proof oracle. Runs only in the runner's disposable project.

const SCENE := "res://addons/lunitora_godot/labs/rig_test_cat_assembled_idle_lab.tscn"
const BODY := "CharacterRoot/BodyMotion"
const TAIL := BODY + "/TailRig"
const BONE_PATHS := ["TailRoot", "TailRoot/TailMid1", "TailRoot/TailMid1/TailMid2", "TailRoot/TailMid1/TailMid2/TailTip"]
const TIMES := [0.0, 1.5, 3.0, 4.5, 6.0]
const DELTAS := [[0.0, -2.0, -4.0, -2.0, 0.0], [0.0, 0.0, -2.0, -1.0, 0.0],
	[0.0, 1.5, 0.0, -1.5, 0.0], [0.0, 2.0, 1.0, 0.0, 0.0],
	[0.0, -1.0, 0.0, 1.0, 0.0], [0.0, -2.0, -1.0, 0.0, 0.0],
	[0.0, 1.0, 0.0, -1.0, 0.0], [0.0, 2.0, 0.0, -2.0, 0.0],
	[0.0, 3.0, 0.0, -3.0, 0.0], [0.0, 4.0, 0.0, -4.0, 0.0]]

var scene: Node2D
var player: AnimationPlayer
var mesh: Polygon2D
var bones: Array[Bone2D] = []
var vertices := PackedVector2Array()
var weights: Array = []
var origins: Array[Vector2] = []
var triangles: Array = []
var rest: Dictionary = {}
var report: Dictionary = {"captures": [], "geometry_samples": 0, "native_interpolation_samples": 0,
	"min_triangle_area_ratio": INF, "max_triangle_area_ratio": 0.0, "max_native_value_error": 0.0}
var checks := 0
var alpha_bounds: Dictionary
var failed := false

func _initialize() -> void:
	call_deferred("run")

func require(condition: bool, description: String) -> void:
	if failed:
		return
	checks += 1
	if not condition:
		failed = true
		push_error(description)
		quit(1)
		assert(condition, description)

func f32(value: float) -> float:
	return PackedFloat32Array([value])[0]

func count_nodes(node: Node) -> int:
	var result := 1
	for child in node.get_children():
		result += count_nodes(child)
	return result

func nodes(node: Node) -> Array:
	var result: Array = [node]
	for child in node.get_children():
		result.append_array(nodes(child))
	return result

func transforms(specimen: Node) -> Dictionary:
	var result: Dictionary = {}
	for node in nodes(specimen):
		if node is Node2D:
			var local: Transform2D = node.transform
			result[String(specimen.get_path_to(node))] = [local.x.x, local.x.y, local.y.x, local.y.y, local.origin.x, local.origin.y]
	return result

func value_at(specimen: Node, path: NodePath) -> float:
	return float(specimen.get_node(NodePath(path.get_concatenated_names())).get_indexed(NodePath(path.get_concatenated_subnames())))

func verify_structure(specimen: Node2D) -> void:
	var expected := {".": "Node2D", "CharacterRoot": "Node2D", "CharacterRoot/LowerFootL": "Sprite2D", "CharacterRoot/LowerFootR": "Sprite2D",
		BODY: "Node2D", TAIL: "Node2D", TAIL + "/TailMesh": "Polygon2D", TAIL + "/TailSkeleton": "Skeleton2D",
		BODY + "/Torso": "Sprite2D", BODY + "/HeadPivot": "Node2D", BODY + "/HeadPivot/Head": "Sprite2D", BODY + "/ScarfForeground": "Sprite2D", "CharacterRoot/AnimationPlayer": "AnimationPlayer"}
	for path in BONE_PATHS:
		expected[TAIL + "/TailSkeleton/" + path] = "Bone2D"
	for side in ["L", "R"]:
		var shoulder: String = BODY + "/Shoulder" + side
		expected[shoulder] = "Node2D"
		expected[shoulder + "/UpperArm" + side] = "Sprite2D"
		expected[shoulder + "/UpperArm" + side + "/Elbow" + side] = "Node2D"
		expected[shoulder + "/UpperArm" + side + "/Elbow" + side + "/LowerArmPaw" + side] = "Sprite2D"
		for layer in ["ArmSocketBack", "ArmSleeveNearWall", "ArmCuffLipFront"]:
			expected[BODY + "/" + layer + side] = "Sprite2D"
	require(count_nodes(specimen) == 31, "Assembled scene must contain exactly31 nodes")
	require(String(specimen.name) == "RigTestCatAssembledIdleLab", "Unexpected lab root")
	for path in expected:
		require(specimen.has_node(path), "Missing fixed node: " + path)
		require(specimen.get_node(path).get_class() == expected[path], "Wrong node class: " + path)
	for node in nodes(specimen):
		require(node.get_script() == null, "Authored scene must have no runtime scripts")
		if node is Sprite2D or node is Polygon2D:
			require(node.texture != null and node.texture.resource_path.begins_with("res://addons/lunitora_godot/test_assets/rig_test_cat/"), "Unexpected artwork")
			require(node.material == null, "Cuff sandwich must not require shader masking")
	var overlay_contract := {
		"L": {"position": Vector2(267, 525), "size": Vector2(153, 163), "lower_position": Vector2(1396.7734, -1646.1658), "lower_rotation": -1.9765847, "lower_offset": Vector2(-860, -240)},
		"R": {"position": Vector2(-412, 526), "size": Vector2(143, 162), "lower_position": Vector2(-1844.1476, -1055.0321), "lower_rotation": 1.4105227, "lower_offset": Vector2(-380, -210)}}
	var layers := {"ArmSocketBack": ["socket_back", 0], "ArmSleeveNearWall": ["sleeve_near_wall", 2], "ArmCuffLipFront": ["cuff_lip_front", 3]}
	for side in overlay_contract:
		var contract: Dictionary = overlay_contract[side]
		var lower: Sprite2D = specimen.get_node(BODY + "/Shoulder" + side + "/UpperArm" + side + "/Elbow" + side + "/LowerArmPaw" + side)
		for layer in layers:
			var attachment: Sprite2D = specimen.get_node(BODY + "/" + layer + side)
			require(attachment.position == contract.position and attachment.scale == Vector2.ONE and attachment.rotation == 0.0, "Sleeve attachment registration changed: " + layer + side)
			require(not attachment.centered and attachment.offset == Vector2.ZERO and attachment.z_index == layers[layer][1] and attachment.z_as_relative, "Sleeve attachment ordering changed: " + layer + side)
			require(attachment.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR, "Sleeve attachment filtering changed: " + layer + side)
			require(attachment.texture.resource_path == "res://addons/lunitora_godot/test_assets/rig_test_cat/arms/rig_test_cat_arm_" + layers[layer][0] + "_" + side.to_lower() + ".png", "Sleeve attachment texture identity changed: " + layer + side)
			require(attachment.texture.get_size() == contract.size, "Sleeve attachment canvas changed: " + layer + side)
			if layer == "ArmSocketBack":
				require(attachment.get_index() > specimen.get_node(BODY + "/Torso").get_index(), "Socket back must draw after the sleeve exterior: " + side)
		require(lower.position == contract.lower_position and lower.rotation == f32(contract.lower_rotation), "Accepted manual arm placement changed: " + side)
		require(lower.scale == Vector2.ONE and not lower.centered and lower.offset == contract.lower_offset and lower.z_index == 1, "Accepted lower sprite registration/order changed: " + side)
		require(lower.texture.get_size() == Vector2(1254, 1254), "Lower-arm canvas must remain1254 square: " + side)
	report["manual_arm_placement_preserved"] = true
	report["cuff_overlays_static"] = true
	report["sleeve_attachment_layers_static"] = true
	var animation_player: AnimationPlayer = specimen.get_node("CharacterRoot/AnimationPlayer")
	require(animation_player.get_animation_list() == PackedStringArray(["RESET", "idle"]), "Only idle and RESET are allowed")
	require(animation_player.autoplay.is_empty(), "Idle must be opt-in")
	var idle: Animation = animation_player.get_animation("idle")
	require(idle.length == 6.0 and idle.loop_mode == Animation.LOOP_LINEAR, "Idle must be6s LOOP_LINEAR")
	require(idle.get_track_count() == 10, "Idle must have10 tracks")
	var paths: Array[String] = [BODY + ":position:y", BODY + "/HeadPivot:position:y",
		BODY + "/ShoulderL:rotation", BODY + "/ShoulderL/UpperArmL/ElbowL:rotation",
		BODY + "/ShoulderR:rotation", BODY + "/ShoulderR/UpperArmR/ElbowR:rotation"]
	for path in BONE_PATHS:
		paths.append(TAIL + "/TailSkeleton/" + path + ":rotation")
	var tracks: Array = []
	for index in range(10):
		var path := NodePath(paths[index].trim_prefix("CharacterRoot/"))
		var track := idle.find_track(path, Animation.TYPE_VALUE)
		require(track >= 0, "Missing approved track: " + str(path))
		var expected_interpolation := Animation.INTERPOLATION_LINEAR if index < 2 else Animation.INTERPOLATION_LINEAR_ANGLE
		require(idle.track_get_interpolation_type(track) == expected_interpolation, "Unexpected idle interpolation mode")
		require(idle.track_get_key_count(track) == 5, "Each idle track must have five keys")
		require(idle.value_track_get_update_mode(track) == Animation.UPDATE_CONTINUOUS, "Continuous value tracks required")
		var values: Array = []
		var start: float = idle.track_get_key_value(track, 0)
		var sign := 1.0
		# Independent registration may reverse either arm's motion signs only.
		if index in [2, 3, 4, 5]:
			sign = signf((float(idle.track_get_key_value(track, 1)) - start) / float(DELTAS[index][1]))
			require(absf(sign) == 1.0, "Arm amplitude/sign invalid")
		for key in range(5):
			require(idle.track_get_key_time(track, key) == TIMES[key], "Incorrect key time")
			require(idle.track_get_key_transition(track, key) == -2.0, "Approved ease-in-out required")
			var value: float = idle.track_get_key_value(track, key)
			var delta: float = DELTAS[index][key] * sign
			if index >= 2:
				delta = deg_to_rad(delta)
			require(absf(value - (start + delta)) < 0.000001, "Unapproved idle amplitude")
			values.append(value)
		require(values[0] == values[4], "Loop endpoints must match exactly")
		require(absf(value_at(specimen.get_node("CharacterRoot"), path) - start) < 0.000001, "First key must equal authored rest")
		tracks.append({"path": str(path), "times": TIMES, "values": values, "transition": -2.0})
	var reset: Animation = animation_player.get_animation("RESET")
	require(reset.loop_mode == Animation.LOOP_NONE and reset.get_track_count() == 10, "RESET must restore all ten authored properties")
	for track in range(10):
		require(reset.track_get_type(track) == Animation.TYPE_VALUE and reset.track_get_key_count(track) == 1, "RESET must use one native rest key per property")
		var path := reset.track_get_path(track)
		var idle_track := idle.find_track(path, Animation.TYPE_VALUE)
		require(idle_track >= 0, "Unexpected RESET property")
		require(reset.track_get_interpolation_type(track) == idle.track_get_interpolation_type(idle_track), "RESET interpolation must match idle for deterministic native blending")
		require(reset.track_get_key_time(track, 0) == 0.0, "RESET key must be at zero")
		require(float(reset.track_get_key_value(track, 0)) == float(idle.track_get_key_value(idle.find_track(path, Animation.TYPE_VALUE), 0)), "RESET differs from idle rest")
		require(absf(value_at(specimen.get_node("CharacterRoot"), path) - f32(float(reset.track_get_key_value(track, 0)))) < 0.000001, "RESET key differs from authored nativefloat rest property")
	report["tracks"] = tracks
	report["node_count"] = 31
	report["idle_key_count"] = 50
	report["reset_key_count"] = 10

func verify_tail(specification: Dictionary) -> void:
	mesh = scene.get_node(TAIL + "/TailMesh")
	vertices = mesh.polygon
	triangles = mesh.polygons
	var original: Dictionary = specification.mesh
	require(vertices.size() == 561 and triangles.size() == 1024 and mesh.get_bone_count() == 4, "Tail topology count changed")
	require(mesh.internal_vertex_count == int(original.internal_vertex_count), "Tail internal vertex count changed")
	require(mesh.skeleton == NodePath("../TailSkeleton"), "Tail skeleton binding changed")
	for index in range(vertices.size()):
		require(vertices[index] == Vector2(original.vertices_px[index][0], original.vertices_px[index][1]), "Tail vertex changed")
		require(mesh.uv[index] == Vector2(original.uv_px[index][0], original.uv_px[index][1]), "Tail UV changed")
	for index in range(triangles.size()):
		require(triangles[index] == PackedInt32Array(original.triangles[index]), "Tail triangle order changed")
	for index in range(4):
		require(mesh.get_bone_path(index) == NodePath(original.bone_paths[index]), "Tail bone path changed")
		var bone: Bone2D = scene.get_node(TAIL + "/TailSkeleton/" + BONE_PATHS[index])
		bones.append(bone)
		origins.append(bone.rest.origin)
		weights.append(mesh.get_bone_weights(index))
		require(weights[index] == PackedFloat32Array(original.weights[index]), "Tail weights changed")
		var origin := Vector2(specification.bones[index].origin_px[0], specification.bones[index].origin_px[1])
		require(bone.rest == Transform2D(0.0, origin) and bone.position == origin, "Tail rest transform changed")
		require(not bone.get_autocalculate_length_and_angle(), "Tail must retain explicit bone dimensions")
		require(is_equal_approx(bone.get_length(), float(specification.bones[index].length)), "Tail bone length changed")
		require(is_equal_approx(bone.get_bone_angle(), float(specification.bones[index].angle_rad)), "Tail bone display angle changed")
	for vertex in range(vertices.size()):
		var total := 0.0
		for index in range(4):
			total += weights[index][vertex]
		require(absf(total - 1.0) < 0.000001, "Tail weights must remain normalized")
	report["tail_topology_spec_identical"] = true
	report["tail_vertices"] = vertices.size()
	report["tail_triangles"] = triangles.size()

func deformed() -> PackedVector2Array:
	if failed:
		return vertices
	var pose := Transform2D.IDENTITY
	var bind := Transform2D.IDENTITY
	var skin: Array[Transform2D] = []
	for index in range(4):
		pose = pose * Transform2D(bones[index].rotation, origins[index])
		bind = bind * Transform2D(0.0, origins[index])
		skin.append(pose * bind.affine_inverse())
	var points := PackedVector2Array()
	for vertex in range(vertices.size()):
		var point := Vector2.ZERO
		for index in range(4):
			point += (skin[index] * vertices[vertex]) * weights[index][vertex]
		points.append(point)
	for triangle in triangles:
		var a: int = triangle[0]
		var b: int = triangle[1]
		var c: int = triangle[2]
		var ratio := (points[b] - points[a]).cross(points[c] - points[a]) / (vertices[b] - vertices[a]).cross(vertices[c] - vertices[a])
		require(ratio > 0.5 and ratio < 1.5, "Tail collapsed/inverted or excessive deformation")
		report.min_triangle_area_ratio = minf(report.min_triangle_area_ratio, ratio)
		report.max_triangle_area_ratio = maxf(report.max_triangle_area_ratio, ratio)
	report.geometry_samples += 1
	return points

func check_pose(time: float) -> void:
	if failed:
		return
	var current := transforms(scene)
	for path in [".", "CharacterRoot", "CharacterRoot/LowerFootL", "CharacterRoot/LowerFootR", BODY + "/ScarfForeground", BODY + "/HeadPivot/Head",
		BODY + "/ArmSocketBackL", BODY + "/ArmSocketBackR", BODY + "/ArmSleeveNearWallL", BODY + "/ArmSleeveNearWallR", BODY + "/ArmCuffLipFrontL", BODY + "/ArmCuffLipFrontR",
		BODY + "/ShoulderL/UpperArmL/ElbowL/LowerArmPawL", BODY + "/ShoulderR/UpperArmR/ElbowR/LowerArmPawR"]:
		require(current[path] == rest[path], "Static authored part moved: " + path)
	var segment := mini(int(fposmod(time, 6.0) / 1.5), 3)
	var u := (fposmod(time, 6.0) - segment * 1.5) / 1.5
	var q := 2 * u * u if u < 0.5 else 1 - 2 * (1 - u) * (1 - u)
	for track in report.tracks:
		var expected := f32(lerpf(track.values[segment], track.values[segment + 1], q))
		var actual := value_at(scene.get_node("CharacterRoot"), NodePath(track.path))
		var error := absf(wrapf(actual - expected, -PI, PI)) if String(track.path).ends_with(":rotation") else absf(actual - expected)
		report.max_native_value_error = maxf(report.max_native_value_error, error)
		# Node2D properties use native float32. Position Y near-1652 has a
		# .000122px ULP; allow two ULPs, not a double-precision comparison.
		var tolerance := 0.00025 if String(track.path).ends_with("position:y") else 0.000001
		require(error <= tolerance, "Native interpolation differs: path=%s time=%.9f actual=%.9f expected_f32=%.9f error=%.9f tolerance=%.9f" % [track.path, time, actual, expected, error, tolerance])
	report.native_interpolation_samples += 1

func viewport(size: Vector2i) -> SubViewport:
	var result := SubViewport.new()
	result.size = size
	result.disable_3d = true
	result.transparent_bg = true
	result.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(result)
	return result

func settle() -> void:
	for frame in range(3):
		await process_frame
		await RenderingServer.frame_post_draw

func visible_bounds() -> Rect2:
	var result := Rect2()
	var first := true
	for node in nodes(scene):
		if not node is Sprite2D:
			continue
		var image_rect: Array = alpha_bounds[node.texture.resource_path]
		var offset: Vector2 = node.offset
		if node.centered:
			offset -= node.texture.get_size() * 0.5
		for point in [Vector2(image_rect[0], image_rect[1]), Vector2(image_rect[2], image_rect[1]), Vector2(image_rect[2], image_rect[3]), Vector2(image_rect[0], image_rect[3])]:
			var actual: Vector2 = node.global_transform * (point + offset)
			if first:
				result = Rect2(actual, Vector2.ZERO)
				first = false
			else:
				result = result.expand(actual)
	# Tail polygon bounds may include transparent padding; use source-alpha corners.
	var tail_rect: Array = alpha_bounds[mesh.texture.resource_path]
	for point in [Vector2(tail_rect[0], tail_rect[1]), Vector2(tail_rect[2], tail_rect[1]), Vector2(tail_rect[2], tail_rect[3]), Vector2(tail_rect[0], tail_rect[3])]:
		result = result.expand(mesh.global_transform * point)
	return result

func capture(view: SubViewport, name: String, time: float, description: Dictionary) -> void:
	await settle()
	require(view.get_texture().get_image().save_png("res://evidence/" + name + ".png") == OK, "Capture failed")
	var entry := description.duplicate()
	entry["name"] = name
	entry["time"] = time
	entry["viewport"] = [view.size.x, view.size.y]
	report.captures.append(entry)

func sample(time: float) -> void:
	player.seek(time, true)
	check_pose(time)
	deformed()

func capture_phones(view: SubViewport, bounds: Rect2) -> void:
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		view.size = size
		var zoom := minf((size.x - 48.0) / bounds.size.x, (size.y - 112.0) / bounds.size.y)
		var origin := Vector2(size.x * 0.5, size.y - 56.0) - Vector2(bounds.get_center().x, bounds.end.y) * zoom
		view.canvas_transform = Transform2D(0.0, Vector2.ONE * zoom, 0.0, origin)
		for entry in [["rest", 0.0], ["quarter", 1.5], ["breath_extreme", 3.0], ["three_quarter", 4.5], ["end", 6.0], ["boundary_before", 6.0 - 1.0 / 60.0], ["boundary_after", 6.0 + 1.0 / 60.0]]:
			sample(entry[1])
			var feet: Array = []
			for side in ["L", "R"]:
				var foot: Sprite2D = scene.get_node("CharacterRoot/LowerFoot" + side)
				var transform := view.canvas_transform * foot.global_transform
				feet.append([transform.x.x, transform.x.y, transform.y.x, transform.y.y, transform.origin.x, transform.origin.y])
			await capture(view, "%dx%d_%s" % [size.x, size.y, entry[0]], entry[1], {"kind": "phone", "phase": entry[0], "feet_canvas_transforms": feet, "zoom": zoom})
		if size == Vector2i(405, 720):
			for frame in range(61):
				sample(frame * 0.1)
				await capture(view, "motion_%02d" % frame, frame * 0.1, {"kind": "motion"})

func capture_closeups(view: SubViewport) -> void:
	view.size = Vector2i(640, 480)
	for part in ["shoulder_l", "elbow_l", "shoulder_r", "elbow_r", "neck", "feet", "tail_attachment"]:
		for index in range(5):
			sample(TIMES[index])
			var center := Vector2.ZERO
			var zoom := 1.0
			if part in ["shoulder_l", "elbow_l", "shoulder_r", "elbow_r"]:
				var side := "L" if part.ends_with("_l") else "R"
				var node: Node2D = scene.get_node(BODY + "/Shoulder" + side)
				center = node.global_position
				if part.begins_with("elbow"):
					# Manual art placement moves the visible socket away from the
					# technical elbow origin. Inspect the accepted cuff/forearm seam.
					var torso: Sprite2D = scene.get_node(BODY + "/Torso")
					var socket := Vector2(890, 650) if side == "L" else Vector2(217, 650)
					center = torso.global_transform * (socket + torso.offset)
				zoom = 2.0 / scene.get_node("CharacterRoot").scale.x
			elif part == "neck":
				center = scene.get_node(BODY + "/HeadPivot").global_position
				zoom = 1.4 / scene.get_node("CharacterRoot").scale.x
			elif part == "feet":
				var foot_bounds := Rect2()
				var first_foot_point := true
				for side in ["L", "R"]:
					var foot: Sprite2D = scene.get_node("CharacterRoot/LowerFoot" + side)
					var opaque: Array = alpha_bounds[foot.texture.resource_path]
					for point in [Vector2(opaque[0], opaque[1]), Vector2(opaque[2], opaque[1]), Vector2(opaque[2], opaque[3]), Vector2(opaque[0], opaque[3])]:
						var local_point: Vector2 = point + foot.offset
						if foot.centered:
							local_point -= foot.texture.get_size() * 0.5
						var global_point: Vector2 = foot.global_transform * local_point
						if first_foot_point:
							foot_bounds = Rect2(global_point, Vector2.ZERO)
							first_foot_point = false
						else:
							foot_bounds = foot_bounds.expand(global_point)
				center = foot_bounds.get_center()
				zoom = minf((view.size.x - 48.0) / foot_bounds.size.x, (view.size.y - 48.0) / foot_bounds.size.y)
			else:
				center = bones[0].global_position
				zoom = 1.6 / scene.get_node("CharacterRoot").scale.x
			view.canvas_transform = Transform2D(0.0, Vector2.ONE * zoom, 0.0, Vector2(view.size) * 0.5 - center * zoom)
			await capture(view, "closeup_%s_%02d" % [part, index], TIMES[index], {"kind": "closeup", "part": part, "zoom": zoom, "joint_px": [320, 240], "joint_radius_px": 3})

func compare_cpu_gpu() -> void:
	var gpu_view := viewport(Vector2i(512, 650))
	var cpu_view := viewport(Vector2i(512, 650))
	var tail_copy: Node2D = scene.get_node(TAIL).duplicate()
	tail_copy.position = Vector2(30, 30)
	tail_copy.scale = Vector2.ONE * 0.375
	tail_copy.rotation = 0.0
	gpu_view.add_child(tail_copy)
	var cpu := Polygon2D.new()
	cpu.texture = mesh.texture
	cpu.uv = mesh.uv
	cpu.polygons = triangles
	cpu.internal_vertex_count = mesh.internal_vertex_count
	cpu.texture_filter = mesh.texture_filter
	cpu.position = Vector2(30, 30)
	cpu.scale = Vector2.ONE * 0.375
	cpu_view.add_child(cpu)
	for index in range(25):
		var time := index * 0.25
		sample(time)
		cpu.polygon = deformed()
		for bone in range(4):
			tail_copy.get_node("TailSkeleton/" + BONE_PATHS[bone]).rotation = bones[bone].rotation
		await settle()
		require(gpu_view.get_texture().get_image().save_png("res://evidence/tail_gpu_%02d.png" % index) == OK, "GPU tail capture failed")
		require(cpu_view.get_texture().get_image().save_png("res://evidence/tail_cpu_%02d.png" % index) == OK, "CPU tail capture failed")
	gpu_view.free()
	cpu_view.free()
	report["gpu_cpu_samples"] = 25

func continuous_playback() -> void:
	var quick := "--quick" in OS.get_cmdline_user_args()
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL if quick else AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	player.play("idle")
	player.advance(0.0)
	var started := Time.get_ticks_msec()
	var wraps := 0
	var frames := 0
	var previous := 0.0
	var geometry_clock := 0.0
	var last_tick := Time.get_ticks_msec()
	while wraps < 20:
		if quick:
			player.advance(1.0 / 60.0)
		else:
			await process_frame
		var time := player.current_animation_position
		if time < previous:
			wraps += 1
		previous = time
		check_pose(time)
		frames += 1
		var now := Time.get_ticks_msec()
		geometry_clock += 1.0 / 60.0 if quick else (now - last_tick) / 1000.0
		last_tick = now
		if geometry_clock >= 0.1:
			deformed()
			geometry_clock = 0.0
		if not quick:
			require(now - started < 180000, "Continuous playback timed out")
	player.pause()
	var seconds := (Time.get_ticks_msec() - started) / 1000.0
	require(quick or seconds >= 119.9, "Realtime20-loop playback did not run120s")
	report["continuous_playback"] = {"mode": "manual_advance_iteration_only" if quick else "normal_realtime", "completed_loops": wraps, "wall_seconds": seconds, "frames_checked": frames, "static_parts_unchanged": true}

func replay_cycle(label: String) -> void:
	# Use native processing, rather than only seeking authored key poses. This
	# helper intentionally avoids mesh/bone references after the original frees.
	var quick := "--quick" in OS.get_cmdline_user_args()
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL if quick else AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	player.play("idle")
	player.seek(0.0, true)
	player.advance(0.0)
	var started := Time.get_ticks_msec()
	var previous := 0.0
	var frames := 0
	var wrapped := false
	while not wrapped:
		if quick:
			player.advance(1.0 / 60.0)
		else:
			await process_frame
		var time := player.current_animation_position
		wrapped = time < previous
		previous = time
		check_pose(time)
		frames += 1
		require(quick or Time.get_ticks_msec() - started < 15000, "Native replay timed out: " + label)
	player.pause()
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var seconds := (Time.get_ticks_msec() - started) / 1000.0
	require(quick or seconds >= 5.9, "Native replay did not complete6s: " + label)
	if not report.has("replay_cycles"):
		report["replay_cycles"] = []
	report.replay_cycles.append({"stage": label, "mode": "manual_advance_iteration_only" if quick else "normal_realtime", "completed_loops": 1, "wall_seconds": seconds, "frames_checked": frames})

func reset_replay_save_reopen(view: SubViewport) -> void:
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("RESET")
	player.advance(0.0)
	player.pause()
	require(transforms(scene) == rest, "RESET did not restore exact authored transforms")
	await settle()
	var reset_image := view.get_texture().get_image()
	require(reset_image.save_png("res://evidence/reset.png") == OK, "RESET capture failed")
	var values: Array = []
	player.play("idle")
	player.pause()
	for time in TIMES:
		sample(time)
		values.append(transforms(scene))
	await replay_cycle("after_reset")
	player.play("RESET")
	player.advance(0.0)
	player.stop(true)
	require(transforms(scene) == rest, "Replay/reset drift")
	var saved := PackedScene.new()
	require(saved.pack(scene) == OK, "Native scene packing failed")
	require(ResourceSaver.save(saved, "res://saved_reopened.tscn") == OK, "Native scene save failed")
	view.remove_child(scene)
	scene.free()
	var reopened: PackedScene = ResourceLoader.load("res://saved_reopened.tscn", "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
	scene = reopened.instantiate()
	view.add_child(scene)
	verify_structure(scene)
	require(transforms(scene) == rest, "Save/reopen changed authored rest")
	player = scene.get_node("CharacterRoot/AnimationPlayer")
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("idle")
	player.pause()
	for index in range(5):
		player.seek(TIMES[index], true)
		require(transforms(scene) == values[index], "Save/reopen/replay drift")
	await replay_cycle("after_save_reopen")
	player.play("RESET")
	player.advance(0.0)
	player.pause()
	require(transforms(scene) == rest, "Reopened RESET drift")
	await settle()
	require(view.get_texture().get_image().get_data() == reset_image.get_data(), "Save/reopen changed rendered rest pixels")
	report["reset_exact_rest"] = true
	report["replay_exact_native_transforms"] = true
	report["save_reopen_replay_exact"] = true
	report["save_reopen_rest_pixels_identical"] = true

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://evidence"))
	alpha_bounds = JSON.parse_string(FileAccess.get_file_as_string("res://alpha_bounds.json"))
	var packed: PackedScene = ResourceLoader.load(SCENE)
	require(packed != null, "Assembled scene failed to load")
	scene = packed.instantiate()
	verify_structure(scene)
	var view := viewport(Vector2i(405, 720))
	view.add_child(scene)
	player = scene.get_node("CharacterRoot/AnimationPlayer")
	# Capture authored matrices before AnimationPlayer can normalize angles.
	rest = transforms(scene)
	report["rest_transforms"] = rest
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("idle")
	player.pause()
	player.seek(0.0, true)
	var idle_start := transforms(scene)
	var normalization: Array = []
	for path in rest:
		if idle_start[path] != rest[path]:
			var largest_basis_error := 0.0
			var largest_origin_error := 0.0
			for component in range(6):
				var error: float = absf(idle_start[path][component] - rest[path][component])
				if component < 4:
					largest_basis_error = maxf(largest_basis_error, error)
				else:
					largest_origin_error = maxf(largest_origin_error, error)
			require(largest_basis_error <= 0.000001 and largest_origin_error <= 0.00025, "Idle start exceeds nativefloat rest tolerance: " + path)
			normalization.append({"path": path, "max_basis_component_difference": largest_basis_error, "max_origin_difference_px": largest_origin_error})
	report["idle_start_float32_angle_normalization"] = normalization
	var specification: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fixture_spec.json"))
	verify_tail(specification)
	var bounds := visible_bounds()
	report["source_alpha_world_bounds"] = [bounds.position.x, bounds.position.y, bounds.end.x, bounds.end.y]
	for index in range(121):
		sample(index * 0.05)
	await capture_phones(view, bounds)
	await capture_closeups(view)
	await compare_cpu_gpu()
	# Continuous playback and RESET/reopen evidence show the complete character.
	view.size = Vector2i(405, 720)
	var zoom := minf((view.size.x - 48.0) / bounds.size.x, (view.size.y - 112.0) / bounds.size.y)
	var origin := Vector2(view.size.x * 0.5, view.size.y - 56.0) - Vector2(bounds.get_center().x, bounds.end.y) * zoom
	view.canvas_transform = Transform2D(0.0, Vector2.ONE * zoom, 0.0, origin)
	await continuous_playback()
	await reset_replay_save_reopen(view)
	report["renderer"] = RenderingServer.get_current_rendering_method()
	report["driver"] = RenderingServer.get_current_rendering_driver_name()
	report["gpu"] = RenderingServer.get_video_adapter_name()
	report["engine"] = Engine.get_version_info()
	report["native_assertions"] = checks
	var file := FileAccess.open("res://evidence/native-report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	view.free()
	print("ASSEMBLED_IDLE_VALIDATION_FINISHED checks=", checks)
	quit(0)
