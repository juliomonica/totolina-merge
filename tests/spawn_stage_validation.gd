extends "res://tests/merge_integration_validation.gd"

const POOLS = [
	{&"wheat": 100.0},
	{&"wheat": 75.0, &"flour": 25.0},
	{&"wheat": 60.0, &"flour": 30.0, &"cake_mix": 10.0},
]
const SELECTION_ORDERS = [
	[&"wheat"],
	[&"wheat", &"flour"],
	[&"wheat", &"flour", &"cake_mix"],
]
var stage_changes: Array[int] = []


func _test_stage_configuration() -> void:
	_check(CONTENT.spawn_stage_errors().is_empty(), "spawn configuration validates")
	_check(CONTENT.spawn_stages.size() == 3, "exactly three spawn stages")
	_check(CONTENT.spawn_stages.map(func(s): return s.unlock_creation_id) == [&"", &"flour", &"cake_mix"],
		"only Flour and Cake Mix are configured unlock results")
	for index in range(3):
		_check(CONTENT.spawn_stages[index].weights == POOLS[index], "exact configured weights: stage %d" % (index + 1))
		_check(CONTENT.spawn_stages[index].selection_order == SELECTION_ORDERS[index],
			"historical cumulative selection order: stage %d" % (index + 1))
	_check(not CreationDefinition.new().get_property_list().any(func(p): return p.name == "spawn_weight"),
		"no competing per-creation spawn weights")
	var world: WorldContentConfiguration = CONTENT.duplicate(true)
	world.spawn_stages[1].weights[&"missing"] = 1.0
	_check(not world.spawn_stage_errors().is_empty(), "unknown weighted creation is rejected")
	world = CONTENT.duplicate(true)
	world.spawn_stages[1].weights[&"wheat"] = -1.0
	_check(not world.spawn_stage_errors().is_empty(), "negative weight rejected")
	world = CONTENT.duplicate(true)
	world.spawn_stages[0].weights.clear()
	_check(not world.spawn_stage_errors().is_empty(), "empty pool rejected")
	world = CONTENT.duplicate(true)
	world.spawn_stages[2].unlock_creation_id = &"flour"
	_check(not world.spawn_stage_errors().is_empty(), "duplicate unlock trigger rejected")
	world = CONTENT.duplicate(true)
	world.spawn_stages[1].unlock_creation_id = &"wheat"
	_check(not world.spawn_stage_errors().is_empty(), "unlock must be a valid merge result")
	world = CONTENT.duplicate(true)
	world.spawn_stages[1].selection_order.remove_at(0)
	_check(world.spawn_stage_errors().has("Spawn weight is missing from selection_order: wheat."),
		"selection order cannot omit a weighted ID")
	world = CONTENT.duplicate(true)
	world.spawn_stages[0].selection_order.clear()
	_check(world.spawn_stage_errors().has("Spawn weight is missing from selection_order: wheat."),
		"empty selection order is rejected without dictionary fallback")
	world = CONTENT.duplicate(true)
	world.spawn_stages[1].selection_order.append(&"flour")
	_check(world.spawn_stage_errors().has("Duplicate spawn selection ID: flour."),
		"selection order cannot duplicate an ID")
	world = CONTENT.duplicate(true)
	world.spawn_stages[1].selection_order.append(&"cake_mix")
	_check(world.spawn_stage_errors().has("Spawn selection ID has no weight: cake_mix."),
		"selection order cannot add an unweighted ID")


func _seeded_stage_snapshot(stage: SpawnStage) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 3245
	var sequence: Array[StringName] = []
	for index in range(256):
		sequence.append(stage.select_creation(rng))
	return [sequence, rng.state]


func _test_stage_serialization() -> void:
	var world: WorldContentConfiguration = CONTENT.duplicate(true)
	for index in range(3):
		var original := CONTENT.spawn_stages[index]
		var reordered := world.spawn_stages[index]
		var keys := original.weights.keys()
		keys.reverse()
		reordered.weights.clear()
		for creation_id in keys:
			reordered.weights[creation_id] = original.weights[creation_id]
		_check(_seeded_stage_snapshot(reordered) == _seeded_stage_snapshot(original),
			"dictionary insertion order preserves seeded sequence and RNG state: stage %d" % (index + 1))
	var path := output_dir.path_join("spawn_stages_roundtrip.tres")
	var saved := ResourceSaver.save(world, path)
	_check(saved == OK, "native ResourceSaver saves spawn configuration")
	if saved != OK:
		return
	var reloaded := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as WorldContentConfiguration
	_check(reloaded != null, "native ResourceLoader reloads spawn configuration")
	if reloaded == null:
		return
	_check(reloaded.spawn_stage_errors().is_empty(), "saved spawn configuration validates after reload")
	for index in range(3):
		_check(reloaded.spawn_stages[index].selection_order == SELECTION_ORDERS[index]
			and _seeded_stage_snapshot(reloaded.spawn_stages[index]) == _seeded_stage_snapshot(CONTENT.spawn_stages[index]),
			"native save/reload preserves explicit order, seeded sequence and RNG state: stage %d" % (index + 1))


func _selection_snapshot() -> Array:
	return [sandbox._current_creation_id, sandbox._raw_next_creation_id, sandbox._rng.state,
		sandbox.next_preview_ingredient.texture, sandbox.upcoming_preview.texture]


func _draw_pool(stage: int, count := 10000) -> Array[StringName]:
	var expected_rng := RandomNumberGenerator.new()
	expected_rng.state = sandbox._rng.state
	var counts: Dictionary = {&"wheat": 0, &"flour": 0, &"cake_mix": 0}
	var sequence: Array[StringName] = []
	var exact := true
	var allowed := true
	for index in range(count):
		var roll := expected_rng.randf() * 100.0
		var expected: StringName = &"wheat"
		if stage == 1 and roll >= 75.0:
			expected = &"flour"
		elif stage == 2:
			expected = &"wheat" if roll < 60.0 else (&"flour" if roll < 90.0 else &"cake_mix")
		var actual: StringName = sandbox._roll_spawn_creation_id()
		sequence.append(actual)
		exact = exact and actual == expected
		allowed = allowed and POOLS[stage].has(actual)
		counts[actual] = counts.get(actual, 0) + 1
	_check(exact and sandbox._rng.state == expected_rng.state,
		"stage %d: %d exact seeded draws, one RNG call per selection" % [stage + 1, count])
	_check(allowed, "stage %d never spawns locked or later creations" % (stage + 1))
	for id in POOLS[stage]:
		_check(absf(float(counts[id]) / count - POOLS[stage][id] / 100.0) < 0.025,
			"stage %d approximate distribution: %s" % [stage + 1, id])
	print("SPAWN COUNTS stage %d: %s" % [stage + 1, counts])
	return sequence


func _merge_unlock(input: StringName, result: StringName, expected_stage: int) -> void:
	var before := _baseline(result)
	var selection := _selection_snapshot()
	var old_stage: int = sandbox._spawn_stage_index
	# Real contacting bodies in flight prove that successful creation, not settling,
	# unlocks the pool. Never call the merge resolver or award hook directly.
	var first := _spawn(input, 0.4, true)
	first.linear_velocity = Vector2(0, 50)
	var second: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(input),
		first.position + Vector2(first.radius * 2.0 - 0.2, 0), Vector2(0, 50))
	_check(await _wait_for(func(): return sandbox.awards.get(result, 0) == before.awards + 1),
		"actual contact creates " + String(result))
	_check(sandbox._spawn_stage_index == expected_stage, "spawn stage advances at successful result creation")
	if sandbox._spawn_stage_index != old_stage:
		stage_changes.append(sandbox._spawn_stage_index)
	_check(_selection_snapshot() == selection, "unlock preserves current, NEXT, textures and RNG state")
	var live := _live(result)
	_check(live.size() == 1 and live[0].position.y + live[0].radius < sandbox.floor.position.y - 50
		and not live[0].sleeping, "unlock does not wait for result landing/settling")
	_assert_rewards(result, before)
	_check(not is_instance_valid(first) and not is_instance_valid(second), "merge sources consumed exactly once")
	await _frames(50)
	_check(sandbox._spawn_stage_index == expected_stage and sandbox.awards.get(result, 0) == before.awards + 1,
		"effect completion/physics do not repeat unlock or reward")
	await _capture("spawn_stage_" + str(expected_stage + 1))
	await _clear_board()


func _deliver_until(target: StringName) -> void:
	var seen: Array[StringName] = []
	for index in range(100):
		var controlled: StringName = sandbox._current_creation_id
		var buffered: StringName = sandbox._raw_next_creation_id
		sandbox._drop_piece(_x(0.5))
		sandbox._advance_machine_drop(0.63)
		seen.append(controlled)
		_check(_live(controlled).size() == 1 and sandbox._current_creation_id == buffered,
			"player drops selected piece and receives unchanged buffered NEXT")
		# Remove fixture drops before they collide; preserve this same run/RNG/stage.
		for piece in sandbox.pieces.get_children():
			piece.queue_free()
		await process_frame
		if controlled == target:
			break
	_check(seen.has(target), "newly earned pool delivers " + String(target))
	_check(seen.slice(0, 2) == [&"wheat", &"wheat"], "two previously buffered Wheats are delivered before new unlock")


func _test_continuous_run() -> void:
	await _reset()
	var scene_id: int = sandbox.get_instance_id()
	_check(sandbox._spawn_stage_index == 0 and sandbox.discovered_creation_ids.is_empty(), "fresh unsaved run starts at stage 1")
	_check(_selection_snapshot().slice(0, 2) == [&"wheat", &"wheat"], "opening DROP and NEXT are Wheat")
	_draw_pool(0)
	await _merge_unlock(&"wheat", &"flour", 1)
	_draw_pool(1)
	await _deliver_until(&"flour")
	await _merge_unlock(&"wheat", &"flour", 1) # Repeated earned result does not advance again.
	# Buffer two Wheats using real selections before testing the next unlock.
	while sandbox._current_creation_id != &"wheat" or sandbox._raw_next_creation_id != &"wheat":
		sandbox._drop_piece(_x(0.5))
		sandbox._advance_machine_drop(0.63)
		for piece in sandbox.pieces.get_children():
			piece.queue_free()
		await process_frame
	await _merge_unlock(&"flour", &"cake_mix", 2)
	_draw_pool(2)
	await _deliver_until(&"cake_mix")
	await _merge_unlock(&"flour", &"cake_mix", 2)
	await _merge_unlock(&"wheat", &"flour", 2) # Earlier trigger must not downgrade.
	for pair in PHYSICAL.slice(2):
		await _physical(pair[0], pair[1])
		_check(sandbox._spawn_stage_index == 2, "later physical result cannot unlock another spawn stage: " + String(pair[1]))
		await _clear_board()
	_draw_pool(2)
	_check(stage_changes == [1, 2], "each configured unlock occurs exactly once in the run")
	_check(sandbox.get_instance_id() == scene_id and sandbox.highest_creation_id == &"fancy_cake",
		"opening, unlocks and late-game merges all use one continuous run")
	_check(sandbox._recipe_progress_slots.map(func(s): return s.get_meta("creation_id")) == BOARD,
		"all nine canonical collection slots remain intact")
	var discoveries: Array = sandbox.discovered_creation_ids.duplicate()
	sandbox._restart_sandbox()
	await process_frame
	_check(sandbox._spawn_stage_index == 0 and _selection_snapshot().slice(0, 2) == [&"wheat", &"wheat"]
		and sandbox.discovered_creation_ids == discoveries and sandbox.score == 0,
		"restart resets stage/opening/score without clearing persistent discoveries")
	_draw_pool(0)
	await _merge_unlock(&"flour", &"cake_mix", 2)
	sandbox._enter_game_over()
	sandbox.play_again_button.pressed.emit()
	await process_frame
	_check(sandbox._spawn_stage_index == 0 and not sandbox.game_over and sandbox.pulse_charge == 0,
		"Play Again resets stage and run state")
	await _reset()
	_check(sandbox.discovered_creation_ids.has(&"cake_mix") and sandbox._spawn_stage_index == 0,
		"new scene loads permanent discoveries but not spawn unlocks")
	_draw_pool(0)
	var selection := _selection_snapshot()
	sandbox._register_creation(&"flour", Vector2.ZERO, 20.0, true)
	sandbox._register_creation(&"cake_mix", Vector2.ZERO, 20.0, false)
	sandbox.presentation.show_recipe_merge(CONTENT.recipe_for(&"flour", &"flour"), Vector2(200, 200), 50)
	await _frames(50)
	_check(sandbox._spawn_stage_index == 0 and _selection_snapshot() == selection,
		"discovery registration / effects / preview do not unlock a spawn stage")


func _test_deterministic_replay() -> void:
	var runs: Array = []
	for attempt in range(2):
		sandbox._restart_sandbox()
		await process_frame
		var sequence: Array[StringName] = _draw_pool(0, 1000)
		await _merge_unlock(&"wheat", &"flour", 1)
		sequence.append_array(_draw_pool(1, 1000))
		await _merge_unlock(&"flour", &"cake_mix", 2)
		sequence.append_array(_draw_pool(2, 1000))
		runs.append([sequence, sandbox._rng.state])
	_check(runs[0] == runs[1], "same seed + same merge/run actions = same 3000-selection sequence and RNG state")


func _run() -> void:
	_test_stage_configuration()
	_test_stage_serialization()
	await _test_continuous_run()
	await _test_deterministic_replay()
	sandbox.queue_free()
	await process_frame
	print("SPAWN STAGES: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
