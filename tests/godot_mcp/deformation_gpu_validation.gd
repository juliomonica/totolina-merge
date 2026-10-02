extends SceneTree
## CPU skinning oracle against the real public-writer saved native scene.
var specimen: Node2D
var rig: Node2D
var cpu: Polygon2D
var gpu_view: SubViewport
var cpu_view: SubViewport
var bones: Array[Bone2D] = []
var vertices := PackedVector2Array()
var weights: Array = []
var triangles: Array = []
var origins: Array[Vector2] = []
var textures: Array[Texture2D] = []
var texture_before: Array = []
var min_area := INF
var max_area := -INF
var min_edge := INF
var max_edge := -INF
var rest_error := 0.0
var scarf_evidence: Array = []
var arm_evidence: Array = []

func node_count(node: Node) -> int:
	var count := 1
	for child in node.get_children():
		count += node_count(child)
	return count

func verify_scarf(specification: Dictionary) -> void:
	assert(node_count(rig) == 19)
	var body: Node2D = rig.get_node("BodyStation")
	var torso: Sprite2D = body.get_node("Torso")
	var pivot: Node2D = body.get_node("HeadPivot")
	var head: Sprite2D = pivot.get_node("Head")
	var scarf: Sprite2D = body.get_node("ScarfForeground")
	assert(body.get_children().map(func(node): return String(node.name)) == ["Torso", "HeadPivot", "ScarfForeground"])
	assert(body.scale == Vector2(0.375, 0.375))
	assert(torso.position == Vector2.ZERO and torso.scale == Vector2.ONE and torso.rotation == 0.0 and torso.offset == Vector2(-561, 0))
	assert(pivot.position == Vector2(0, 306) and pivot.scale == Vector2(0.8, 0.8) and pivot.rotation == 0.0)
	assert(head.position == Vector2.ZERO and head.scale == Vector2.ONE and head.rotation == 0.0 and head.offset == Vector2(-627, -1145))
	assert(scarf.position == Vector2.ZERO and scarf.scale == Vector2.ONE and scarf.rotation == 0.0)
	assert(scarf.offset == Vector2(-139, 238) and not scarf.centered)
	assert(scarf.texture != torso.texture and scarf.texture.get_size() == Vector2(288, 147))
	assert(scarf.texture == ResourceLoader.load("res://addons/lunitora_godot/test_assets/rig_test_cat/body/rig_test_cat_scarf_foreground.png"))
	assert(scarf.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR)
	assert(scarf.z_index == 1 and scarf.z_as_relative and scarf.get_script() == null and scarf.owner == specimen)
	var row: Dictionary
	for candidate in specification.nodes:
		if candidate.path == "BodyStation/ScarfForeground":
			row = candidate
	assert(not row.is_empty())
	assert(row["class"] == "Sprite2D" and row.texture == "scarf_foreground")
	assert(Vector2(row.pivot_px[0], row.pivot_px[1]) == Vector2(139, -238))
	assert(not row.has("vertices_px") and not row.has("uv_px"))
	var animation: Animation = rig.get_node("AnimationPlayer").get_animation(&"deformation_demo")
	assert(animation.get_track_count() == 7)
	var key_count := 0
	for track in range(animation.get_track_count()):
		assert(not String(animation.track_get_path(track)).contains("ScarfForeground"))
		key_count += animation.track_get_key_count(track)
	assert(key_count == 35)

func capture_scarf(body: Node2D) -> void:
	# Presentation-only copies of the public-writer saved fixture. No source,
	# authored scene, animation resource or original transform is modified.
	for presentation in ["normal", "closeup"]:
		var render_scale := 0.375 if presentation == "normal" else 1.0
		var origin := Vector2(256, 270) if presentation == "normal" else Vector2(320, -80)
		var size := Vector2i(512, 820) if presentation == "normal" else Vector2i(640, 400)
		var viewport := view(size)
		var copy: Node2D = body.duplicate()
		copy.visible = true
		copy.position = origin
		copy.scale = Vector2.ONE * render_scale
		viewport.add_child(copy)
		var foreground: Sprite2D = copy.get_node("ScarfForeground")
		assert(foreground.texture != copy.get_node("Torso").texture)
		assert(foreground.texture == ResourceLoader.load("res://addons/lunitora_godot/test_assets/rig_test_cat/body/rig_test_cat_scarf_foreground.png"))
		for y in [306, 300, 294]:
			copy.get_node("HeadPivot").position.y = y
			for enabled in [false, true]:
				foreground.visible = enabled
				await settle()
				var suffix := "on" if enabled else "off"
				assert(viewport.get_texture().get_image().save_png("res://gpu_evidence/scarf_%s_y%d_%s.png" % [presentation, y, suffix]) == OK)
			scarf_evidence.append({"presentation": presentation, "head_y": y, "origin": [origin.x, origin.y],
				"render_scale": render_scale, "protected_above_body_y": 238})
		# Isolate double-render opacity from intended neck occlusion. It measures
		# the existing torso pixels with/without the extracted source foreground.
		copy.get_node("HeadPivot").visible = false
		for enabled in [false, true]:
			foreground.visible = enabled
			await settle()
			var suffix := "on" if enabled else "off"
			assert(viewport.get_texture().get_image().save_png("res://gpu_evidence/scarf_%s_torso_%s.png" % [presentation, suffix]) == OK)
		viewport.free()

func verify_arm() -> void:
	var station: Node2D = rig.get_node("ArmStation")
	var shoulder: Node2D = station.get_node("Shoulder")
	var upper: Sprite2D = shoulder.get_node("UpperArm")
	var elbow: Node2D = upper.get_node("Elbow")
	var lower: Sprite2D = elbow.get_node("LowerArmPaw")
	assert(station.scale == Vector2(0.5, 0.5) and shoulder.position == Vector2.ZERO)
	assert(upper.position == Vector2.ZERO and upper.scale == Vector2(0.4, 0.4))
	assert(upper.rotation == 0.0 and upper.offset == Vector2(-810, -320) and not upper.centered and upper.z_index == 0)
	assert(elbow.position == Vector2(-385, 680) and elbow.scale == Vector2.ONE)
	assert(is_equal_approx(elbow.rotation, 0.87026) and shoulder.rotation == 0.0)
	assert(lower.position == Vector2.ZERO and lower.scale == Vector2.ONE)
	assert(is_equal_approx(lower.rotation, -0.87026) and lower.offset == Vector2(-860, -240) and not lower.centered and lower.z_index == -1)
	assert(upper.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR and lower.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR)
	assert(upper.get_script() == null and lower.get_script() == null)
	assert(upper.get_children().map(func(node): return String(node.name)) == ["Elbow"])
	assert(elbow.get_children().map(func(node): return String(node.name)) == ["LowerArmPaw"])
	# Measure the native inherited transform, independently of the source-pivot
	# declarations. Scaling UpperArm must also scale its Elbow and lower art.
	var relative := station.transform * shoulder.transform * upper.transform * elbow.transform
	assert((relative.origin - station.position).is_equal_approx(Vector2(-77, 136)))

func capture_arm(station: Node2D, player: AnimationPlayer) -> void:
	# Clone the actual authored ArmStation. All artwork, pivots, hierarchy and
	# static compensation come from the public writer, not a reconstructed rig.
	for presentation in ["normal", "closeup"]:
		var zoom := 1.0 if presentation == "normal" else 2.6
		var origin := Vector2(275, 85) if presentation == "normal" else Vector2(390, -200)
		var size := Vector2i(420, 480) if presentation == "normal" else Vector2i(400, 340)
		var viewport := view(size)
		var copy: Node2D = station.duplicate()
		copy.visible = true
		copy.position = origin
		copy.scale = station.scale * zoom
		viewport.add_child(copy)
		var shoulder: Node2D = copy.get_node("Shoulder")
		var elbow: Node2D = shoulder.get_node("UpperArm/Elbow")
		var rest_elbow := elbow.rotation
		for index in range(5):
			shoulder.rotation = 0.0
			elbow.rotation = rest_elbow + deg_to_rad(index * 5.0)
			await settle()
			var name := "arm_%s_elbow_%02d" % [presentation, index]
			assert(viewport.get_texture().get_image().save_png("res://gpu_evidence/%s.png" % name) == OK)
			arm_evidence.append({"name": name, "presentation": presentation, "sample": "elbow",
				"elbow_delta_degrees": index * 5, "joint_px": [elbow.global_position.x, elbow.global_position.y],
				"joint_radius_px": 6 * zoom})
		for index in range(5):
			player.seek(index * 0.5, true)
			shoulder.rotation = station.get_node("Shoulder").rotation
			elbow.rotation = station.get_node("Shoulder/UpperArm/Elbow").rotation
			await settle()
			var name := "arm_%s_demo_%02d" % [presentation, index]
			assert(viewport.get_texture().get_image().save_png("res://gpu_evidence/%s.png" % name) == OK)
			arm_evidence.append({"name": name, "presentation": presentation, "sample": "demo",
				"time": index * 0.5, "joint_px": [elbow.global_position.x, elbow.global_position.y],
				"joint_radius_px": 6 * zoom})
		viewport.free()
	player.seek(2.0, true)
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		var viewport := view(size)
		var copy: Node2D = station.duplicate()
		copy.visible = true
		copy.position = Vector2(size.x * 0.68, size.y * 0.24)
		viewport.add_child(copy)
		var shoulder: Node2D = copy.get_node("Shoulder")
		var elbow: Node2D = shoulder.get_node("UpperArm/Elbow")
		for index in range(3):
			player.seek(index * 0.5, true)
			shoulder.rotation = station.get_node("Shoulder").rotation
			elbow.rotation = station.get_node("Shoulder/UpperArm/Elbow").rotation
			await settle()
			var presentation := "%dx%d" % [size.x, size.y]
			var name := "arm_%s_demo_%02d" % [presentation, index]
			assert(viewport.get_texture().get_image().save_png("res://gpu_evidence/%s.png" % name) == OK)
			arm_evidence.append({"name": name, "presentation": presentation, "sample": "demo", "time": index * 0.5,
				"viewport_px": [size.x, size.y], "joint_px": [elbow.global_position.x, elbow.global_position.y], "joint_radius_px": 6})
		viewport.free()
	player.seek(2.0, true)

func _initialize() -> void:
	call_deferred("run")

func view(size: Vector2i) -> SubViewport:
	var result := SubViewport.new()
	result.size = size
	result.disable_3d = true
	result.transparent_bg = true
	result.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(result)
	return result

func fingerprint(texture: Texture2D) -> Array:
	return [texture.get_instance_id(), texture.resource_path, texture.get_rid().get_id(),
		texture.get_image().get_data().hex_encode().sha256_text()]

func transform_sample(node: Node2D) -> Dictionary:
	var actual := node.global_transform
	return {"origin": [actual.origin.x, actual.origin.y], "x": [actual.x.x, actual.x.y], "y": [actual.y.x, actual.y.y]}

func deform(rotations: Array) -> PackedVector2Array:
	var pose := Transform2D.IDENTITY
	var rest := Transform2D.IDENTITY
	var skin: Array[Transform2D] = []
	for index in range(4):
		pose = pose * Transform2D(rotations[index], origins[index])
		rest = rest * Transform2D(0.0, origins[index])
		skin.append(pose * rest.affine_inverse())
	var points := PackedVector2Array()
	for index in range(vertices.size()):
		var point := Vector2.ZERO
		for bone in range(4):
			point += (skin[bone] * vertices[index]) * weights[bone][index]
		points.append(point)
	for triangle in triangles:
		var a: int = triangle[0]
		var b: int = triangle[1]
		var c: int = triangle[2]
		var ratio := (points[b]-points[a]).cross(points[c]-points[a]) / (vertices[b]-vertices[a]).cross(vertices[c]-vertices[a])
		assert(ratio > 0.0)
		min_area = minf(min_area,ratio)
		max_area = maxf(max_area,ratio)
		for pair in [[a,b],[b,c],[c,a]]:
			var stretch := points[pair[0]].distance_to(points[pair[1]]) / vertices[pair[0]].distance_to(vertices[pair[1]])
			min_edge = minf(min_edge,stretch)
			max_edge = maxf(max_edge,stretch)
	if rotations.all(func(angle): return angle == 0.0):
		for index in range(vertices.size()):
			rest_error = maxf(rest_error, points[index].distance_to(vertices[index]))
	return points

func settle() -> void:
	for index in range(3):
		await process_frame
		await RenderingServer.frame_post_draw

func capture(prefix: String, index: int) -> void:
	assert(gpu_view.get_texture().get_image().save_png("res://gpu_evidence/%s_gpu_%02d.png" % [prefix,index]) == OK)
	assert(cpu_view.get_texture().get_image().save_png("res://gpu_evidence/%s_cpu_%02d.png" % [prefix,index]) == OK)

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://gpu_evidence"))
	var packed: PackedScene = ResourceLoader.load("res://authored.tscn")
	specimen = packed.instantiate()
	rig = specimen.get_node("RigTestCatRig")
	var specification: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fixture_spec.json"))
	verify_scarf(specification)
	verify_arm()
	var mesh: Polygon2D = rig.get_node("TailStation/TailMesh")
	vertices = mesh.polygon
	triangles = mesh.polygons
	assert(vertices.size() == 561 and triangles.size() == 1024 and mesh.get_bone_count() == 4)
	var skeleton: Skeleton2D = rig.get_node("TailStation/TailSkeleton")
	for index in range(4):
		weights.append(mesh.get_bone_weights(index))
		var bone: Bone2D = rig.get_node("TailStation/TailSkeleton").get_node(mesh.get_bone_path(index))
		bones.append(bone)
		origins.append(bone.rest.origin)
	for node in [mesh, rig.get_node("ArmStation/Shoulder/UpperArm"), rig.get_node("ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw"), rig.get_node("BodyStation/Torso"), rig.get_node("BodyStation/HeadPivot/Head"), rig.get_node("BodyStation/ScarfForeground")]:
		textures.append(node.texture)
		texture_before.append(fingerprint(node.texture))
	gpu_view = view(Vector2i(512,650))
	cpu_view = view(Vector2i(512,650))
	specimen.position = Vector2(30,30)
	gpu_view.add_child(specimen)
	# Render only the tail in the oracle view; the full fixture is rendered below.
	rig.get_node("ArmStation").visible = false
	rig.get_node("BodyStation").visible = false
	cpu = Polygon2D.new()
	cpu.texture = mesh.texture
	cpu.polygon = vertices
	cpu.uv = mesh.uv
	cpu.polygons = triangles
	cpu.internal_vertex_count = mesh.internal_vertex_count
	cpu.texture_filter = mesh.texture_filter
	cpu.position = Vector2(30,30)
	cpu.scale = Vector2(0.375,0.375)
	cpu_view.add_child(cpu)
	await settle()
	for index in range(201):
		var m := (index-100)/100.0
		deform([deg_to_rad(2*m),deg_to_rad(4*m),deg_to_rad(6*m),deg_to_rad(6*m)])
	var amplitude_samples: Array = []
	for index in range(21):
		var m := (index-10)/10.0
		var angles := [deg_to_rad(2*m),deg_to_rad(4*m),deg_to_rad(6*m),deg_to_rad(6*m)]
		for bone in range(4):
			bones[bone].rotation = angles[bone]
		cpu.polygon = deform(angles)
		await settle()
		capture("amplitude",index)
		amplitude_samples.append(m)
	for bone in bones: bone.rotation = 0.0
	cpu.polygon = deform([0.0,0.0,0.0,0.0])
	await settle()
	assert(gpu_view.get_texture().get_image().save_png("res://gpu_evidence/rest.png") == OK)
	gpu_view.remove_child(specimen)
	await settle()
	assert(gpu_view.get_texture().get_image().save_png("res://gpu_evidence/detached.png") == OK)
	gpu_view.add_child(specimen)
	await settle()
	assert(gpu_view.get_texture().get_image().save_png("res://gpu_evidence/reattached.png") == OK)
	var player: AnimationPlayer = rig.get_node("AnimationPlayer")
	assert(player.get_animation_list() == PackedStringArray(["deformation_demo"]))
	player.play(&"deformation_demo")
	player.pause()
	var combined_view := view(Vector2i(1024,600))
	var combined := packed.instantiate()
	combined.position = Vector2(20,20)
	combined.scale = Vector2(0.55,0.55)
	combined_view.add_child(combined)
	var combined_player: AnimationPlayer = combined.get_node("RigTestCatRig/AnimationPlayer")
	combined_player.play(&"deformation_demo")
	combined_player.pause()
	var samples: Array = []
	for index in range(65):
		var time := index*0.03125
		player.seek(time,true)
		combined_player.seek(time,true)
		var segment := mini(int(time/0.5),3)
		var u := (time-segment*0.5)/0.5
		var q := 2*u*u if u < 0.5 else 1-2*(1-u)*(1-u)
		var m: float = [q,1-2*q,-1+1.5*q,0.5-0.5*q][segment]
		cpu.polygon = deform([deg_to_rad(2*m),deg_to_rad(4*m),deg_to_rad(6*m),deg_to_rad(6*m)])
		await settle()
		capture("animation",index)
		assert(combined_view.get_texture().get_image().save_png("res://gpu_evidence/combined_%02d.png" % index) == OK)
		samples.append({"time":time,"amplitude":m,"rotations":bones.map(func(bone):return bone.rotation),
			"shoulder":rig.get_node("ArmStation/Shoulder").rotation,
			"elbow":rig.get_node("ArmStation/Shoulder/UpperArm/Elbow").rotation,
			"head_y":rig.get_node("BodyStation/HeadPivot").position.y,
			"arm_elbow_global":transform_sample(rig.get_node("ArmStation/Shoulder/UpperArm/Elbow")),
			"arm_lower_global":transform_sample(rig.get_node("ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw"))})
	assert(bones.all(func(bone):return bone.rotation == 0.0))
	assert(rig.get_node("ArmStation/Shoulder").rotation == 0.0)
	assert(rig.get_node("ArmStation/Shoulder/UpperArm/Elbow").rotation == PackedFloat32Array([0.87026])[0])
	assert(rig.get_node("BodyStation/HeadPivot").position.y == 306.0)
	await capture_scarf(rig.get_node("BodyStation"))
	await capture_arm(rig.get_node("ArmStation"), player)
	verify_scarf(specification)
	verify_arm()
	for index in range(textures.size()): assert(fingerprint(textures[index]) == texture_before[index])
	var result := {"version":Engine.get_version_info(), "renderer":RenderingServer.get_current_rendering_method(),
		"driver":RenderingServer.get_current_rendering_driver_name(),"gpu":RenderingServer.get_video_adapter_name(),
		"vertices":vertices.size(),"triangles":triangles.size(),"cpu_poses":201,
		"min_area_ratio":min_area,"max_area_ratio":max_area,"min_edge_ratio":min_edge,"max_edge_ratio":max_edge,
		"rest_error_px":rest_error,"textures_unchanged":true,"amplitude_samples":amplitude_samples,"animation_samples":samples,
		"generated_node_count":node_count(rig),"scarf_separate_texture":true,"scarf_exact_sprite_spec":true,
		"scarf_not_animated":true,"scarf_captures":scarf_evidence,"arm_captures":arm_evidence,
		"arm_two_piece_hierarchy":true,"arm_effective_rest_elbow_px":[-77,136]}
	var file := FileAccess.open("res://gpu_evidence/result.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"\t"))
	file.close()
	combined_view.free()
	cpu_view.free()
	gpu_view.free()
	print("DEFORMATION_GPU_FINISHED ",JSON.stringify(result))
	quit()
