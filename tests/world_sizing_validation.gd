extends "res://tests/kitchen_recipe_validation.gd"

# Reference-curve expectations only. Current designer tuning is validated
# separately, so editing world percentages does not invalidate the test fixture.
const SIZE_IDS = BOARD
const GROWTH = [0.0, 15.0, 15.0, 15.0, 15.0, 15.0, 20.0, 25.0, 30.0]
const RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
const EXPECTED = [0.046, 0.052899999999999996, 0.06083499999999999, 0.06996024999999999, 0.08045428749999999, 0.09252243062499997, 0.11102691674999997, 0.13878364593749995, 0.18041873971874994]


func _world(growth_values: Array) -> WorldContentConfiguration:
	var world := WorldContentConfiguration.new()
	for index in range(growth_values.size()):
		var creation := CreationDefinition.new()
		creation.id = StringName("test_%d" % index)
		creation.size_order = index + 1
		creation.size_growth_percent = growth_values[index]
		world.creations.append(creation)
	return world


func _near(actual: float, expected: float, description: String) -> void:
	_check(absf(actual - expected) < 0.000000001, description)


func _configured_ratio(id: StringName) -> float:
	var ratio: float = CONTENT.base_radius_ratio
	for index in range(SIZE_IDS.size()):
		var definition: CreationDefinition = CONTENT.creation_for_id(SIZE_IDS[index])
		if index > 0:
			ratio *= 1.0 + definition.size_growth_percent / 100.0
		if definition.id == id:
			return ratio
	return 0.0


func _test_curve() -> void:
	_check(CONTENT.creations.size() == 9 and CONTENT.sizing_errors(true).is_empty(),
		"Kitchen has 9 contiguous unique size orders with strict growth")
	var previous := 0.0
	for index in range(SIZE_IDS.size()):
		var definition: CreationDefinition = CONTENT.creation_for_id(SIZE_IDS[index])
		_check(definition.size_order == index + 1, "exact size order: " + String(definition.id))
		_check(definition.progression_rank == RANKS[index], "progression rank unchanged: " + String(definition.id))
		var ratio: float = CONTENT.effective_radius_ratio(definition)
		_near(ratio, _configured_ratio(definition.id), "current cumulative Kitchen radius: " + String(definition.id))
		_check(ratio > previous, "strictly ascending: " + String(definition.id))
		previous = ratio
		print("RADIUS TABLE: %d %s growth %.1f%% = %.12f" %
			[definition.size_order, definition.id, definition.size_growth_percent, ratio])
	_check(CONTENT.effective_radius_ratio(CONTENT.creation_for_id(&"wheat")) == CONTENT.base_radius_ratio,
		"first size exactly equals base")
	var reference_world := _world(GROWTH)
	for index in range(SIZE_IDS.size()):
		_near(reference_world.effective_radius_ratio(reference_world.creations[index]),
			EXPECTED[index], "original reference curve still matches: " + String(SIZE_IDS[index]))
	# Changing one input scales that creation and only its downstream sequence.
	for changed_index in [1, 2, 8]:
		var world := _world(GROWTH)
		world.creations[changed_index].size_growth_percent += 4.0
		var multiplier: float = (1.0 + (GROWTH[changed_index] + 4.0) / 100.0) / (1.0 + GROWTH[changed_index] / 100.0)
		for index in range(SIZE_IDS.size()):
			_near(world.effective_radius_ratio(world.creations[index]),
				EXPECTED[index] * (multiplier if index >= changed_index else 1.0),
				"changing %s affects correct downstream size: %s" % [SIZE_IDS[changed_index], SIZE_IDS[index]])
	var world := _world(GROWTH)
	world.base_radius_ratio = 0.05
	for index in range(SIZE_IDS.size()):
		_near(world.effective_radius_ratio(world.creations[index]), EXPECTED[index] * 0.05 / 0.046,
			"base radius scales whole curve: " + String(SIZE_IDS[index]))
	world.base_radius_ratio = 0.046
	# Neither recipe progression, collection order nor array order defines physical size.
	for definition in world.creations:
		definition.progression_rank = 100 - definition.size_order
		definition.collection_order = 100 - definition.size_order
	world.creations.reverse()
	for definition in world.creations:
		_near(world.effective_radius_ratio(definition), EXPECTED[definition.size_order - 1],
			"size order independent of rank/collection/array order: " + String(definition.id))


func _test_edge_cases() -> void:
	var world := _world([0.0])
	_check(world.sizing_errors(true).is_empty(), "single-creation world is valid")
	_near(world.effective_radius_ratio(world.creations[0]), 0.046, "single-creation world uses base")
	world = _world([0.0, 0.0, 0.0])
	_check(world.sizing_errors().is_empty(), "generic future world allows zero growth")
	_check(world.sizing_errors(true) == PackedStringArray([
		"Strict size growth requires more than 0% at size_order 2.",
		"Strict size growth requires more than 0% at size_order 3."]),
		"Kitchen strict validation rejects equal-size steps with readable diagnostics")
	for definition in world.creations:
		_near(world.effective_radius_ratio(definition), 0.046, "generic zero growth is cumulative")
	world = _world([0.0, 12.5, 17.75, 22.125])
	_near(world.effective_radius_ratio(world.creations[3]), 0.046 * 1.125 * 1.1775 * 1.22125,
		"decimal percentages")
	# Check structural errors without changing any production resources.
	world = _world([0.0, 8.0, 8.0])
	world.creations[2].size_order = 2
	_check(world.sizing_errors().has("Duplicate size_order 2."), "duplicate order rejected")
	_check(world.sizing_errors().has("Missing size_order 3."), "missing order rejected")
	world.creations[0].size_order = 4
	_check(world.sizing_errors().has("Missing size_order 1."), "missing smallest creation rejected")
	world = _world([])
	_check(world.sizing_errors().has("Missing size_order 1."), "empty world rejected")
	world.creations.append(null)
	_check(world.sizing_errors().has("Missing creation in size sequence."), "null definition rejected")
	world = _world([0.0, 8.0])
	world.creations[0].size_order = 0
	_check(not world.sizing_errors().is_empty(), "nonpositive order rejected")
	world = _world([1.0, 8.0])
	_check(world.sizing_errors().has("size_order 1 must have 0% growth."), "first creation growth must be zero")
	for growth in [-1.0, INF, NAN]:
		world = _world([0.0, growth])
		_check(not world.sizing_errors().is_empty(), "negative/nonfinite growth rejected")
	for base in [-1.0, 0.0, INF, NAN]:
		world = _world([0.0, 8.0])
		world.base_radius_ratio = base
		_check(not world.sizing_errors().is_empty(), "invalid base rejected")
	print("EXPECTED VALIDATION WARNINGS BEGIN (malformed test resources only)")
	world = _world([0.0, 8.0, 8.0])
	world.creations[2].size_order = 2
	_near(world.effective_radius_ratio(world.creations[1]), 0.046, "invalid sequence returns base safely")
	var warning_count := world._sizing_warnings.size()
	world.effective_radius_ratio(world.creations[1])
	_check(warning_count == 2 and world._sizing_warnings.size() == warning_count, "warnings do not repeat per frame")
	world = _world([0.0, 8.0])
	world.base_radius_ratio = -1
	_near(world.effective_radius_ratio(world.creations[1]), 0.046, "invalid base fallback is safe")
	world = _world([0.0, -8.0])
	_near(world.effective_radius_ratio(world.creations[1]), 0.046, "invalid growth cannot produce negative collider")
	world = _world([0.0, 8.0])
	_near(world.effective_radius_ratio(null), 0.046, "null request safely uses base")
	_near(world.effective_radius_ratio(CreationDefinition.new()), 0.046, "foreign creation safely uses base")
	print("EXPECTED VALIDATION WARNINGS END")


func _test_runtime_sizing() -> void:
	var physical_sizes: Array[float] = []
	var visual_sizes: Array[float] = []
	for id in SIZE_IDS:
		var definition: CreationDefinition = CONTENT.creation_for_id(id)
		await _reset()
		var piece := _spawn(definition.id, 0.5)
		piece.freeze = true # Isolate visual effects from ordinary motion in this fixture.
		await create_timer(0.05).timeout # Synchronize the initial body/viewport state first.
		var collider: CollisionShape2D = piece.get_node("CollisionShape2D")
		var sprite: Sprite2D = piece.get_node("Visual/IngredientSprite")
		var radius: float = _configured_ratio(definition.id) * sandbox._chamber_rect.size.x
		_check(is_equal_approx(piece.radius, radius) and is_equal_approx(collider.shape.radius, radius),
			"effective radius reaches actual CircleShape2D: " + String(definition.id))
		_check(is_equal_approx(sprite.scale.x * 512.0, radius * 2.18) and sprite.scale.x == sprite.scale.y,
			"same effective radius drives artwork: " + String(definition.id))
		physical_sizes.append(collider.shape.radius)
		visual_sizes.append(sprite.scale.x * 512.0)
		_check(piece.scale == Vector2.ONE and collider.scale == Vector2.ONE and collider.position == Vector2.ZERO
			and sprite.centered and sprite.offset == Vector2.ZERO and sprite.position == Vector2.ZERO
			and sprite.global_position.is_equal_approx(collider.global_position), "unit physics transforms / concentric: " + String(definition.id))
		_check(is_equal_approx(sprite.scale.x * 240.0 / collider.shape.radius, 1.021875)
			and definition.visual_diameter_scale == 2.18, "480/512 bubble inset and 2.18 preserved")
	for index in range(1, 6):
		_check(physical_sizes[index] > physical_sizes[index - 1]
			and visual_sizes[index] > visual_sizes[index - 1], "first six physically and visually ascending: " + String(SIZE_IDS[index]))
	# Change Flour only; normal drop and downstream creation sizes follow automatically.
	var flour: CreationDefinition = CONTENT.creation_for_id(&"flour")
	var original := flour.size_growth_percent
	var original_flour_ratio := _configured_ratio(&"flour")
	var original_sponge_ratio := _configured_ratio(&"sponge_cake")
	flour.size_growth_percent = 12.0
	await _reset()
	var changed := _spawn(&"flour", 0.5)
	var multiplier := 1.12 / (1.0 + original / 100.0)
	_check(is_equal_approx(changed.radius, sandbox._chamber_rect.size.x * original_flour_ratio * multiplier),
		"Flour percentage edit reaches runtime body")
	var downstream := _spawn(&"sponge_cake", 0.8)
	_check(is_equal_approx(downstream.radius, sandbox._chamber_rect.size.x * original_sponge_ratio * multiplier),
		"Flour edit also reaches downstream runtime body")
	sandbox._current_creation_id = &"flour"
	sandbox._update_next_preview()
	var expected_preview := minf(58.0, ceilf(changed.radius * 2.18))
	_check(sandbox.next_preview.custom_minimum_size == Vector2.ONE * expected_preview, "DROP preview shares effective radius and existing cap")
	_check(changed.get_node("CollisionShape2D").shape != downstream.get_node("CollisionShape2D").shape,
		"pieces retain unique CircleShape2D resources")
	flour.size_growth_percent = original
	await _reset()
	sandbox._current_creation_id = &"fancy_cake"
	sandbox._drop_piece(-10000)
	var dropped: PrototypePiece = _live(&"fancy_cake")[0]
	_check(dropped.position.x - dropped.radius >= sandbox.left_wall.position.x + sandbox._wall_thickness * 0.5 - 0.001,
		"drop clamp uses effective large radius")
	_check(is_equal_approx(dropped.position.y, sandbox._chamber_rect.position.y + dropped.radius
		+ sandbox._wall_thickness * CONFIG.SPAWN_WALL_CLEARANCE_MULTIPLIER), "spawn height uses same effective radius")


func _render_representatives() -> void:
	if DisplayServer.get_name() == "headless":
		return
	debug_collisions_hint = true
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		await _reset()
		var width: float = sandbox._chamber_rect.size.x
		var total_diameter := 0.0
		for index in range(6):
			total_diameter += _radius(SIZE_IDS[index]) * 2.18
		var gap := width * 0.025
		var x: float = _x(0.5) - (total_diameter + gap * 5.0) * 0.5
		for index in range(6):
			var piece := _spawn(SIZE_IDS[index], 0.5)
			piece.freeze = true
			piece.position.x = x + piece.radius * 1.09
			# Shared visual baseline; frozen fixtures keep their measured positions.
			piece.position.y = sandbox.floor.position.y - width * 0.35 - piece.radius
			x += piece.radius * 2.18 + gap
		await create_timer(0.12).timeout
		await _capture("sizes_%sx%s_first_six" % [size.x, size.y])
		_check(root.get_texture().get_image().get_size() == size, "exact sizing portrait dimensions: %s" % size)


func _run() -> void:
	_test_curve()
	_test_edge_cases()
	await _test_runtime_sizing()
	await _render_representatives()
	await _test_navigation()
	print("WORLD SIZING: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
