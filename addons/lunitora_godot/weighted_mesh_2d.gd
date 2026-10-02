@tool
extends RefCounted
## Bounded construction of explicit trusted data. No transport, history, save,
## triangulation, weight generation, repair, normalization or global state.

const MAX_BONES := 32
const MAX_VERTICES := 2048
const MAX_TRIANGLES := 4096
const MAX_INFLUENCES := 4
const ROUNDTRIP_WEIGHT_TOLERANCE := 0.000001
const KEYS := ["vertices_px", "uv_px", "triangles", "bone_paths", "weights",
	"skeleton_path", "internal_vertex_count"]


static func validate(value: Variant) -> String:
	if not value is Dictionary or value.size() != KEYS.size():
		return "closed mesh schema"
	for key in KEYS:
		if not value.has(key):
			return "missing mesh field"
	if not value.vertices_px is Array or value.vertices_px.size() < 3 \
			or value.vertices_px.size() > MAX_VERTICES or not value.uv_px is Array \
			or value.uv_px.size() != value.vertices_px.size():
		return "vertex/UV count"
	var count: int = value.vertices_px.size()
	if not _integer(value.internal_vertex_count, 0, count - 3):
		return "internal vertex count"
	for index in range(count):
		if not _vector_valid(value.vertices_px[index]) or not _vector_valid(value.uv_px[index]):
			return "finite geometry/UV"
	if not value.triangles is Array or value.triangles.is_empty() \
			or value.triangles.size() > MAX_TRIANGLES:
		return "triangle count"
	var used := {}
	for row in value.triangles:
		if not row is Array or row.size() != 3:
			return "triangle arity"
		for index in row:
			if not _integer(index, 0, count - 1):
				return "triangle index"
			used[int(index)] = true
		var a := vector(value.vertices_px[int(row[0])])
		var b := vector(value.vertices_px[int(row[1])])
		var c := vector(value.vertices_px[int(row[2])])
		var area := (b - a).cross(c - a)
		if not is_finite(area) or area == 0.0:
			return "degenerate rest triangle"
	if used.size() != count:
		return "unreferenced vertex"
	if not value.bone_paths is Array or value.bone_paths.is_empty() \
			or value.bone_paths.size() > MAX_BONES or not value.weights is Array \
			or value.weights.size() != value.bone_paths.size():
		return "bone/weight count"
	if not _skeleton_path(value.skeleton_path):
		return "relative skeleton path"
	var paths := {}
	for index in range(value.bone_paths.size()):
		var path: Variant = value.bone_paths[index]
		if not _bone_path(path) or paths.has(path):
			return "bone path or duplicate binding"
		paths[path] = true
		if not value.weights[index] is Array or value.weights[index].size() != count:
			return "weight array length"
	for vertex in range(count):
		var total := 0.0
		var influences := 0
		for weights in value.weights:
			var weight: Variant = weights[vertex]
			if not _number(weight) or float(weight) < 0.0 or float(weight) > 1.0:
				return "finite bounded weight"
			total += float(weight)
			if float(weight) > 0.0:
				influences += 1
		# Authored trusted inputs must already be normalized. The tolerance is
		# solely for native readback; the builder never repairs authored data.
		if total != 1.0 or influences > MAX_INFLUENCES:
			return "authored weight normalization/influences"
	return ""


static func prepare(data: Dictionary, texture: Texture2D) -> Polygon2D:
	if not validate(data).is_empty() or not is_instance_valid(texture) \
			or texture.get_script() != null or texture.resource_path.is_empty():
		return null
	var mesh := Polygon2D.new()
	mesh.polygon = vectors(data.vertices_px)
	mesh.uv = vectors(data.uv_px)
	mesh.polygons = triangles(data.triangles)
	mesh.internal_vertex_count = int(data.internal_vertex_count)
	mesh.skeleton = NodePath(data.skeleton_path)
	mesh.texture = texture
	mesh.texture_offset = Vector2.ZERO
	mesh.texture_rotation = 0.0
	mesh.texture_scale = Vector2.ONE
	mesh.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	mesh.color = Color.WHITE
	mesh.modulate = Color.WHITE
	mesh.self_modulate = Color.WHITE
	mesh.invert_enabled = false
	for index in range(data.bone_paths.size()):
		mesh.add_bone(NodePath(data.bone_paths[index]), PackedFloat32Array(data.weights[index]))
	return mesh


static func verify(mesh: Polygon2D, data: Dictionary, texture: Texture2D) -> bool:
	if not is_instance_valid(mesh) or mesh.get_class() != "Polygon2D" \
			or mesh.get_script() != null or not validate(data).is_empty():
		return false
	if mesh.texture != texture or mesh.polygon != vectors(data.vertices_px) \
			or mesh.uv != vectors(data.uv_px) or mesh.polygons != triangles(data.triangles) \
			or mesh.internal_vertex_count != int(data.internal_vertex_count) \
			or mesh.skeleton != NodePath(data.skeleton_path) \
			or mesh.texture_offset != Vector2.ZERO or mesh.texture_rotation != 0.0 \
			or mesh.texture_scale != Vector2.ONE or mesh.texture_filter != CanvasItem.TEXTURE_FILTER_LINEAR \
			or mesh.color != Color.WHITE or not mesh.vertex_colors.is_empty() \
			or mesh.offset != Vector2.ZERO or mesh.invert_enabled:
		return false
	if mesh.get_bone_count() != data.bone_paths.size():
		return false
	for index in range(data.bone_paths.size()):
		if mesh.get_bone_path(index) != NodePath(data.bone_paths[index]) \
				or mesh.get_bone_weights(index) != PackedFloat32Array(data.weights[index]):
			return false
	for vertex in range(mesh.polygon.size()):
		var total := 0.0
		for bone in range(mesh.get_bone_count()):
			total += mesh.get_bone_weights(bone)[vertex]
		if absf(total - 1.0) > ROUNDTRIP_WEIGHT_TOLERANCE:
			return false
	return true


static func verify_bindings(mesh: Polygon2D, skeleton: Skeleton2D) -> bool:
	# Node/path inspection cannot flush Skeleton2D setup. The editor coordinator
	# must inspect observers before its separate native count/index getters.
	if not is_instance_valid(mesh) or not is_instance_valid(skeleton) \
			or skeleton.get_class() != "Skeleton2D" or skeleton.get_script() != null \
			or mesh.get_node_or_null(mesh.skeleton) != skeleton:
		return false
	for index in range(mesh.get_bone_count()):
		var bone := skeleton.get_node_or_null(mesh.get_bone_path(index))
		if not bone is Bone2D or bone.get_class() != "Bone2D" or bone.get_script() != null:
			return false
	return true


static func vector(value: Array) -> Vector2:
	return Vector2(float(value[0]), float(value[1]))


static func vectors(value: Array) -> PackedVector2Array:
	var result := PackedVector2Array()
	for row in value:
		result.append(vector(row))
	return result


static func triangles(value: Array) -> Array[PackedInt32Array]:
	var result: Array[PackedInt32Array] = []
	for row in value:
		result.append(PackedInt32Array(row))
	return result


static func _number(value: Variant) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value))


static func _integer(value: Variant, minimum: int, maximum: int) -> bool:
	return _number(value) and float(value) == floorf(float(value)) \
		and float(value) >= minimum and float(value) <= maximum


static func _vector_valid(value: Variant) -> bool:
	return value is Array and value.size() == 2 and _number(value[0]) and _number(value[1]) \
		and absf(float(value[0])) <= 1000000.0 and absf(float(value[1])) <= 1000000.0


static func _bone_path(value: Variant) -> bool:
	if not value is String or value.is_empty() or value.begins_with("/") \
			or value.contains(":") or value.contains("\\") or value.simplify_path() != value:
		return false
	for name in value.split("/"):
		if not name.is_valid_identifier():
			return false
	return true


static func _skeleton_path(value: Variant) -> bool:
	if not value is String or value.is_empty() or value.begins_with("/") \
			or value.contains(":") or value.contains("\\") or value.simplify_path() != value:
		return false
	for name in value.split("/"):
		if name != ".." and not name.is_valid_identifier():
			return false
	return true
