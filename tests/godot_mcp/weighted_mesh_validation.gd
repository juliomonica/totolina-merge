@tool
extends RefCounted
## Native malformed-input coverage for the bounded internal mesh primitive.
## The runner supplies a reviewed fixture and an imported external texture.

const Weighted = preload("res://addons/lunitora_godot/weighted_mesh_2d.gd")


static func run(fixture: Dictionary, texture: Texture2D) -> Dictionary:
	var result := {"checks": 0, "failures": []}
	_check(result, Weighted.validate(fixture).is_empty(), "reviewed explicit fixture accepted")
	_check(result, fixture.vertices_px.size() == 561 and fixture.uv_px.size() == 561
		and fixture.triangles.size() == 1024 and fixture.internal_vertex_count == 465,
		"reviewed topology counts")
	var simple := {"vertices_px": [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]],
		"uv_px": [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]], "triangles": [[0, 1, 2]],
		"bone_paths": ["Root", "Root/Tip"], "weights": [[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]],
		"skeleton_path": "../Skeleton", "internal_vertex_count": 0}
	_check(result, Weighted.validate(simple).is_empty(), "explicit non-dyadic authored normalized input accepted")
	_reject(result, null, "null input")
	_reject(result, [], "array input")
	var bad := simple.duplicate(true)
	bad.erase("uv_px")
	_reject(result, bad, "missing field")
	bad = simple.duplicate(true)
	bad["infer_weights"] = true
	_reject(result, bad, "unknown field")
	for field in ["vertices_px", "uv_px", "triangles", "bone_paths", "weights"]:
		bad = simple.duplicate(true)
		bad[field] = "invalid"
		_reject(result, bad, "non-array " + field)
	bad = simple.duplicate(true)
	bad.vertices_px.resize(2)
	_reject(result, bad, "too few vertices")
	bad = simple.duplicate(true)
	bad.vertices_px.resize(2049)
	_reject(result, bad, "vertex upper bound")
	bad = simple.duplicate(true)
	bad.uv_px.pop_back()
	_reject(result, bad, "UV length mismatch")
	for field in ["vertices_px", "uv_px"]:
		for value in [INF, NAN, -INF, 1000001.0, "coordinate"]:
			bad = simple.duplicate(true)
			bad[field][1][0] = value
			_reject(result, bad, "nonfinite/out-of-bound/non-number " + field + " " + str(value))
		bad = simple.duplicate(true)
		bad[field][1] = [0.0]
		_reject(result, bad, "vector arity " + field)
	for value in [-1, 1, 0.5, INF, "count"]:
		bad = simple.duplicate(true)
		bad.internal_vertex_count = value
		_reject(result, bad, "invalid internal count " + str(value))
	bad = simple.duplicate(true)
	bad.triangles = []
	_reject(result, bad, "empty triangle list")
	bad = simple.duplicate(true)
	bad.triangles = []
	for index in range(4097):
		bad.triangles.append([0, 1, 2])
	_reject(result, bad, "triangle upper bound")
	for indices in [[0, 1], [0, 1, 2, 0], [-1, 1, 2], [0, 3, 2], [0, 0.5, 2], [0, INF, 2], [0, "1", 2], [0, 1, 1]]:
		bad = simple.duplicate(true)
		bad.triangles = [indices]
		_reject(result, bad, "invalid triangle " + str(indices))
	bad = simple.duplicate(true)
	bad.vertices_px[2] = [20.0, 0.0]
	_reject(result, bad, "collinear rest triangle")
	bad = simple.duplicate(true)
	bad.vertices_px.append([10.0, 10.0])
	bad.uv_px.append([10.0, 10.0])
	bad.weights[0].append(0.5)
	bad.weights[1].append(0.5)
	_reject(result, bad, "unreferenced vertex")
	bad = simple.duplicate(true)
	bad.bone_paths = []
	bad.weights = []
	_reject(result, bad, "zero bones")
	bad = simple.duplicate(true)
	bad.bone_paths = []
	bad.weights = []
	for index in range(33):
		bad.bone_paths.append("Bone" + str(index))
		bad.weights.append([1.0, 1.0, 1.0] if index == 0 else [0.0, 0.0, 0.0])
	_reject(result, bad, "bone upper bound")
	bad = simple.duplicate(true)
	bad.bone_paths[1] = "Root"
	_reject(result, bad, "duplicate bone binding")
	for path in ["", "/Root", "Root:rotation", "Root\\Tip", "Root/../Tip", "Root//Tip", "Root/not a name", 5]:
		bad = simple.duplicate(true)
		bad.bone_paths[1] = path
		_reject(result, bad, "invalid bone path " + str(path))
	for path in ["", "/Skeleton", "../Skeleton:property", "..\\Skeleton", "../Other/../Skeleton", "../not a name", 5]:
		bad = simple.duplicate(true)
		bad.skeleton_path = path
		_reject(result, bad, "invalid skeleton path " + str(path))
	bad = simple.duplicate(true)
	bad.weights.pop_back()
	_reject(result, bad, "weight/bone count mismatch")
	bad = simple.duplicate(true)
	bad.weights[0] = "weights"
	_reject(result, bad, "non-array weight row")
	bad = simple.duplicate(true)
	bad.weights[0].pop_back()
	_reject(result, bad, "weight vertex count mismatch")
	for value in [-0.000001, 1.000001, INF, NAN, "weight"]:
		bad = simple.duplicate(true)
		bad.weights[0][0] = value
		_reject(result, bad, "invalid bounded weight " + str(value))
	for value in [0.0, 0.0999995, 0.1000005]:
		bad = simple.duplicate(true)
		bad.weights[0][0] = value
		_reject(result, bad, "authored sum rejects even within native tolerance " + str(value))
	bad = simple.duplicate(true)
	bad.bone_paths = ["A", "B", "C", "D", "E"]
	bad.weights = [[0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.125, 0.125, 0.125], [0.125, 0.125, 0.125]]
	_reject(result, bad, "five normalized influences rejected")
	bad = simple.duplicate(true)
	bad.bone_paths = ["A", "B", "C", "D"]
	bad.weights = [[0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.25, 0.25, 0.25], [0.25, 0.25, 0.25]]
	_check(result, Weighted.validate(bad).is_empty(), "four normalized influences accepted by reusable primitive")
	var boundary := {"vertices_px": [], "uv_px": [], "triangles": [], "bone_paths": [],
		"weights": [], "skeleton_path": "../Skeleton", "internal_vertex_count": 0}
	for index in range(2048):
		var point := [cos(TAU * index / 2048.0) * 100.0, sin(TAU * index / 2048.0) * 100.0]
		boundary.vertices_px.append(point)
		boundary.uv_px.append(point.duplicate())
	for index in range(1, 2047):
		boundary.triangles.append([0, index, index + 1])
	while boundary.triangles.size() < 4096:
		boundary.triangles.append([0, 1, 2])
	for index in range(32):
		boundary.bone_paths.append("Bone" + str(index))
		var weights: Array = []
		weights.resize(2048)
		weights.fill(1.0 if index == 0 else 0.0)
		boundary.weights.append(weights)
	_check(result, Weighted.validate(boundary).is_empty(), "exact reusable vertex/triangle/bone upper bounds accepted")
	_check(result, Weighted.prepare(simple, null) == null, "missing external texture rejected")
	var mesh := Weighted.prepare(simple, texture)
	_check(result, mesh != null and Weighted.verify(mesh, simple, texture), "float32 weight readback tolerates native normalization roundtrip only")
	if mesh != null:
		var total := float(mesh.get_bone_weights(0)[0]) + float(mesh.get_bone_weights(1)[0])
		_check(result, total != 1.0 and absf(total - 1.0) <= Weighted.ROUNDTRIP_WEIGHT_TOLERANCE,
			"non-dyadic native sum actually exercises readback tolerance")
		mesh.set_bone_weights(0, PackedFloat32Array([0.1000005, 0.2, 0.3]))
		_check(result, not Weighted.verify(mesh, simple, texture), "tolerance never authorizes changed native weight arrays")
		mesh.free()
	mesh = Weighted.prepare(fixture, texture)
	_check(result, mesh != null and Weighted.verify(mesh, fixture, texture), "exact reviewed mesh native roundtrip")
	if mesh != null:
		_check(result, mesh.polygons.size() == 1024 and mesh.polygon.size() == 561
			and mesh.get_bone_count() == 4, "no triangulation or inferred bone rows")
		mesh.free()
	return result


static func _reject(result: Dictionary, value: Variant, label: String) -> void:
	var before := var_to_bytes(value)
	_check(result, not Weighted.validate(value).is_empty(), label)
	_check(result, var_to_bytes(value) == before, label + " does not repair input")


static func _check(result: Dictionary, condition: bool, label: String) -> void:
	result.checks += 1
	if not condition:
		result.failures.append(label)
