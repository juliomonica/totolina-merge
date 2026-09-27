extends "res://tests/merge_integration_validation.gd"

const RELEASE_GUARD = preload("res://tests/debug_spawn_release_sandbox.gd")


func _snapshot() -> Array:
	return [sandbox._rng.state, sandbox._current_creation_id, sandbox._raw_next_creation_id,
		sandbox._spawn_stage_index, sandbox.score, sandbox.pulse_charge,
		sandbox.highest_creation_id, sandbox.discovered_creation_ids.duplicate(),
		sandbox._new_discoveries_this_run.duplicate(),
		FileAccess.get_sha256(save_path) if FileAccess.file_exists(save_path) else "no save"]


func _inside(piece: PrototypePiece) -> bool:
	var inset: float = sandbox._wall_thickness * 0.5
	return piece.position.x - piece.radius >= sandbox.left_wall.position.x + inset - 0.01 \
		and piece.position.x + piece.radius <= sandbox.right_wall.position.x - inset + 0.01 \
		and piece.position.y - piece.radius >= sandbox._chamber_rect.position.y + inset - 0.01 \
		and piece.position.y + piece.radius <= sandbox.floor.position.y - inset + 0.01


func _empty_board() -> void:
	sandbox._debug_clear_board()
	await _frames(2)


func _test_single_spawns() -> void:
	await _reset()
	var panel = sandbox._debug_spawn_panel
	_check(OS.has_feature("editor") and panel != null and not panel.body.visible, "editor panel exists and starts collapsed")
	var ids: Array = []
	for choice in panel.choices:
		ids.append(choice.get_meta("creation_id"))
	_check(ids == BOARD, "selector uses exactly nine canonical content IDs")
	for id in BOARD:
		var before := _snapshot()
		var spawned: Array = sandbox._debug_spawn_creations(id, 1)
		_check(spawned.size() == 1 and sandbox.pieces.get_child_count() == 1, "Spawn One creates exactly one real " + String(id))
		_check(_snapshot() == before, "debug spawn leaves RNG/previews/stage/rewards/discoveries/save unchanged")
		if spawned.size() == 1:
			_check(_inside(spawned[0]), "single spawn starts inside physics boundaries")
			_assert_piece(spawned[0])
			var y: float = spawned[0].position.y
			await _frames(10)
			_check(spawned[0].position.y > y, "debug piece uses real gravity")
		await _empty_board()
	_check(sandbox._debug_spawn_creations(&"egg", 1).is_empty()
		and sandbox._debug_spawn_creations(&"wheat", 3).is_empty(), "invalid IDs/counts cannot spawn")
	_check(panel.spawn_positions(Rect2(0, 0, 10, 10), 20.0, 2, []).is_empty(),
		"impossible pair returns no positions, never an overlapping/partial pair")


func _test_pairs_and_clear() -> void:
	for input in [&"flour", &"cake_mix", &"sponge_cake"]:
		await _empty_board()
		var result: StringName = CONTENT.recipe_for(input, input).result
		var before := _baseline(result)
		var state := _snapshot()
		var spawned: Array = sandbox._debug_spawn_creations(input, 2)
		_check(spawned.size() == 2 and sandbox.pieces.get_child_count() == 2, "Spawn Pair creates two " + String(input))
		_check(state == _snapshot(), "pair spawning itself grants nothing and consumes no RNG")
		if spawned.size() != 2:
			continue
		_check(spawned[0].position != spawned[1].position and _inside(spawned[0]) and _inside(spawned[1])
			and spawned[0].position.distance_to(spawned[1].position) >= spawned[0].radius * 2.0 - 0.11,
			"pair has distinct near-contact transforms inside the chamber")
		_check(await _wait_for(func(): return sandbox.result_spawns.get(result, 0) > before.spawns),
			"debug pair follows real physical merge: " + String(result))
		_assert_rewards(result, before)
		_check(flavor_counts.get(result, 0) == before.effects + 1, "existing Egg/Milk/Cream flavor effect plays once")
		var effects: Array = sandbox.presentation.merge_effects.get_children().filter(func(n): return n.has_meta("recipe_result"))
		var recipe: MergeRecipe = CONTENT.recipe_for(input, input)
		_check(effects.size() == 1, "one approved flavor effect per debug-pair merge")
		if effects.size() == 1:
			_assert_flavor(effects[0], recipe)
		await _capture("debug_pair_" + String(input))
		state = _snapshot()
		await _empty_board()
		await _frames(60)
		_check(state == _snapshot() and sandbox.pieces.get_child_count() == 0
			and sandbox.presentation.merge_effects.get_child_count() == 0, "Clear Board cancels visual effects but preserves earned state/save")
	await _empty_board()
	var before := _snapshot()
	var final_pair: Array = sandbox._debug_spawn_creations(&"fancy_cake", 2)
	_check(final_pair.size() == 2 and _inside(final_pair[0]) and _inside(final_pair[1]), "large Fancy pair fits via diagonal fallback when needed")
	await _frames(90)
	_check(_live(&"fancy_cake").size() == 2 and _snapshot() == before, "Fancy + Fancy remains final and non-merging")
	await _empty_board()
	# Cancel a pending physical merge, not just already-idle bodies.
	sandbox._merge_cooldown_remaining = 4.0
	sandbox._debug_spawn_creations(&"wheat", 2)
	_check(await _wait_for(func(): return not sandbox._queued_merge_pairs.is_empty()), "real contacting pair queued before debug clear")
	before = _snapshot()
	sandbox.danger_active = true
	sandbox.danger_timer = 1.0
	await _empty_board()
	await _frames(40)
	_check(_snapshot() == before and not sandbox.danger_active and sandbox.danger_timer == 0
		and sandbox._queued_merge_pairs.is_empty() and not sandbox._merge_resolution_pending
		and sandbox.pieces.get_child_count() == 0, "clear cancels pending merge and transient danger without a late result")
	var config := ConfigFile.new()
	config.load(save_path)
	config.set_value("settings", "debug_test_unrelated", "preserve")
	config.save(save_path)
	before = _snapshot()
	sandbox._enter_game_over()
	_check(sandbox._debug_spawn_creations(&"wheat", 1).is_empty()
		and sandbox._debug_spawn_panel.spawn_one.disabled, "no spawning into a game-over run")
	await _empty_board()
	_check(sandbox.game_over and sandbox.result_overlay.visible and _snapshot() == before,
		"clear during game over does not revive/reset run or erase unrelated settings")
	sandbox.play_again_button.pressed.emit()
	await process_frame
	_check(not sandbox._debug_spawn_panel.spawn_one.disabled, "Play Again reenables debug spawns")


func _mouse(pressed: bool, point: Vector2) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = point
	event.global_position = point
	root.push_input(event, true)


func _touch(index: int, pressed: bool, point: Vector2) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.pressed = pressed
	event.position = point
	root.push_input(event, true)


func _test_ui_input() -> void:
	# Match mobile embedded popups. Headless still has an artificial 64px window;
	# selection therefore needs the graphical suite's real portrait window.
	root.gui_embed_subwindows = true
	await _reset()
	var panel = sandbox._debug_spawn_panel
	var point: Vector2 = panel.toggle.get_global_rect().get_center()
	_mouse(true, point)
	_mouse(false, point)
	await process_frame
	_check(panel.body.visible and sandbox.pieces.get_child_count() == 0, "opening debug panel does not drop gameplay piece")
	panel.select_creation(4) # Sponge; selection alone must not affect gameplay.
	var before := _snapshot()
	point = panel.spawn_one.get_global_rect().get_center()
	_mouse(true, point)
	_mouse(false, point)
	_check(_live(&"sponge_cake").size() == 1 and sandbox.pieces.get_child_count() == 1 and _snapshot() == before,
		"mouse Spawn One creates selected piece only, not an extra normal DROP")
	await _empty_board()
	_touch(3, true, point)
	_touch(3, false, point)
	_check(_live(&"sponge_cake").size() == 1 and sandbox.pieces.get_child_count() == 1
		and sandbox._active_drop_touch_index == -1 and _snapshot() == before,
		"real indexed touch activates debug button without claiming gameplay finger/drop")
	await _empty_board()
	point = panel.selector.get_global_rect().get_center()
	_mouse(true, point)
	_mouse(false, point)
	_check(sandbox.pieces.get_child_count() == 0 and _snapshot() == before, "opening selector never advances current/NEXT")
	panel.picker.hide()
	await process_frame
	await process_frame
	# Native indexed touch, with touch-to-mouse emulation deliberately disabled.
	_touch(5, true, point)
	_touch(5, false, point)
	await process_frame
	_check(panel.picker.visible, "touch opens the native creation picker")
	await process_frame
	if DisplayServer.get_name() != "headless":
		_picker_touch(panel, 1)
		_check(panel.selected_index == 1 and not panel.picker.visible and _snapshot() == before,
			"touch selects Flour and closes picker without a gameplay DROP")
	else:
		print("NOT EXECUTED headless: popup selection (synthetic screen clamps it to 8px); covered by graphical suite")
	panel.select_creation(4)
	# A gameplay owner remains the owner when another finger uses developer UI.
	var chamber_point := Vector2(sandbox._chamber_rect.get_center().x, sandbox._chamber_rect.end.y - 50.0)
	_touch(8, true, chamber_point)
	sandbox._advance_machine_drop(0.63)
	before = _snapshot()
	point = panel.spawn_one.get_global_rect().get_center()
	_touch(9, true, point)
	_touch(9, false, point)
	_check(sandbox._active_drop_touch_index == 8 and sandbox.pieces.get_child_count() == 2
		and _snapshot() == before, "debug UI does not steal active gameplay touch or advance normal queue")
	_touch(8, false, chamber_point)
	await _empty_board()
	before = _snapshot()
	point = panel.spawn_pair.get_global_rect().get_center()
	_touch(12, true, point)
	_touch(12, false, point)
	_check(sandbox.pieces.get_child_count() == 2 and _live(&"sponge_cake").size() == 2
		and _snapshot() == before, "touch Spawn Pair routes exactly two selected pieces, no RNG DROP")
	point = panel.clear_board.get_global_rect().get_center()
	_touch(13, true, point)
	_touch(13, false, point)
	await _frames(2)
	_check(sandbox.pieces.get_child_count() == 0 and _snapshot() == before,
		"touch Clear Board cancels pair before physics without leaking a normal DROP")
	point = panel.get_global_rect().position + Vector2(2, 2)
	_touch(14, true, point)
	_touch(14, false, point)
	_mouse(true, point)
	_mouse(false, point)
	_check(sandbox.pieces.get_child_count() == 0 and sandbox._active_drop_touch_index == -1
		and _snapshot() == before, "blank panel padding consumes mouse/touch without gameplay ownership")


func _picker_touch(panel, index: int) -> void:
	for pressed in [true, false]:
		var event := InputEventScreenTouch.new()
		event.index = 5
		event.pressed = pressed
		event.position = panel.choices[index].get_global_rect().get_center()
		panel.picker.push_input(event, true)


func _test_release_guard() -> void:
	var script = load("res://scripts/prototype/debug_spawn_panel.gd")
	for features in [[true, false, true], [false, false, false], [false, true, true], [true, true, true]]:
		_check(script.enabled_for_features(features[0], features[1]) == features[2],
			"editor/dev_tools feature matrix: %s; debug/release alone grant nothing" % str(features))
	sandbox.queue_free()
	await process_frame
	sandbox = SANDBOX.instantiate()
	var material: ShaderMaterial = sandbox.recipe_locked_silhouette_material
	sandbox.set_script(RELEASE_GUARD)
	sandbox.recipe_locked_silhouette_material = material
	sandbox._discovery_save_path = save_path
	root.add_child(sandbox)
	await process_frame
	var before := _snapshot()
	sandbox._create_debug_spawn_panel()
	_check(sandbox._debug_spawn_panel == null and sandbox.find_child("DebugSpawnPanel", true, false) == null,
		"simulated non-debug build creates no UI, including repeated setup calls")
	_check(sandbox._debug_spawn_creations(&"fancy_cake", 1).is_empty()
		and sandbox._debug_spawn_creations(&"flour", 2).is_empty() and _snapshot() == before,
		"non-debug guard blocks direct/hidden spawn actions")
	var normal := _spawn(&"wheat", 0.5)
	sandbox._debug_clear_board()
	await process_frame
	_check(is_instance_valid(normal) and not normal.is_queued_for_deletion(), "non-debug guard blocks hidden Clear Board")
	print("RELEASE COVERAGE: build probe simulated false; actual export binary not executed")


func _portraits_debug() -> void:
	if DisplayServer.get_name() == "headless":
		return
	debug_collisions_hint = true
	await _reset()
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		await create_timer(0.1).timeout
		sandbox._debug_spawn_panel.toggle.button_pressed = true
		await process_frame
		_check(sandbox.get_viewport_rect().encloses(sandbox._debug_spawn_panel.get_global_rect()), "expanded developer panel fits portrait %s" % size)
		var panel = sandbox._debug_spawn_panel
		for index in range(9):
			panel.selector.pressed.emit()
			await process_frame
			await process_frame
			_check(panel.picker.get_visible_rect().encloses(panel.choices[index].get_global_rect())
				and panel.choices[index].size.y >= 44, "picker choice has a visible 44px touch target: %d" % index)
			if index == 8:
				await _capture("debug_picker_%sx%s" % [size.x, size.y])
			var before := _snapshot()
			_picker_touch(panel, index)
			_check(panel.selected_index == index and not panel.picker.visible and _snapshot() == before,
				"portrait touch selection works without extra drops: %d" % index)
			await process_frame
		for id in [&"wheat", &"sponge_cake", &"decorated_cake", &"fancy_cake"]:
			await _empty_board()
			sandbox._debug_spawn_panel.select_creation(BOARD.find(id))
			var spawned: Array = sandbox._debug_spawn_creations(id, 1)
			_check(spawned.size() == 1, "portrait debug spawn: " + String(id))
			if spawned.size() == 1:
				_assert_piece(spawned[0])
			await _frames(60)
			await _capture("debug_%sx%s_%s" % [size.x, size.y, id])


func _run() -> void:
	await _test_single_spawns()
	await _test_pairs_and_clear()
	await _test_ui_input()
	await _test_release_guard()
	await _portraits_debug()
	sandbox.queue_free()
	await process_frame
	print("DEBUG SPAWN: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
