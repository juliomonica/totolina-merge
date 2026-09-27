extends "res://tests/merge_integration_validation.gd"

# One real result transaction must reach every consumer. Fixtures create only
# the matching physical input; they never call reward/discovery/unlock methods.
const EXPECTED_POOLS = [
	{&"wheat": 100.0},
	{&"wheat": 75.0, &"flour": 25.0},
	{&"wheat": 60.0, &"flour": 30.0, &"cake_mix": 10.0},
]
var expected_ids: Array[StringName] = []
var slot_instances: Array = []
var capture_prefix := ""


func _touch(index: int, pressed: bool, point: Vector2) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.pressed = pressed
	event.position = point
	root.push_input(event, true)


func _check_strip(label: String) -> void:
	var slots: Array = sandbox._recipe_progress_slots
	_check(slots.size() == 9 and slots == slot_instances
		and sandbox.recipe_progress_row.get_child_count() == 9,
		label + ": nine original fixed collection slots")
	for index in range(BOARD.size()):
		var slot: Control = slots[index]
		var id: StringName = BOARD[index]
		var known := expected_ids.has(id)
		var artwork: TextureRect = slot.find_child("Artwork", true, false)
		var unknown: TextureRect = slot.find_child("Unknown", true, false)
		_check(slot.get_meta("creation_id") == id and slot.get_meta("discovered") == known
			and artwork.texture == CONTENT.creation_for_id(id).texture
			and artwork.visible == known and unknown.visible != known
			and unknown.texture == sandbox.MACHINE_PRESENTATION.MYSTERY
			and artwork.material == (null if known else sandbox.recipe_locked_silhouette_material),
			"%s: slot %d immediately reflects %s" % [label, index + 1, id])


func _check_saved(label: String) -> void:
	var saved := ConfigFile.new()
	_check(saved.load(save_path) == OK
		and saved.get_value("recipes", "format_version", -1) == CONTENT.content_version
		and saved.get_value("recipes", "content_id", "") == String(CONTENT.content_id)
		and saved.get_value("recipes", "discovered_creation_ids", PackedStringArray()) == PackedStringArray(expected_ids)
		and saved.get_value("settings", "unrelated", "") == "preserved",
		label + ": semantic discovery persisted immediately, unrelated setting preserved")


func _check_consumers(label: String, capture := false) -> void:
	_check(sandbox.discovered_creation_ids == expected_ids,
		label + ": authoritative discoveries match canonical expected IDs")
	_check_strip(label)
	_check_saved(label)
	if capture:
		await _capture(capture_prefix + "_strip_" + label)
	# Recipe Collection is a separate scene, intentionally loaded when opened.
	# Read the exact save just written by the merge, never inject its discoveries.
	var collection: Control = load("res://scenes/menu/recipe_collection.tscn").instantiate()
	collection._discovery_save_path = save_path
	root.add_child(collection)
	await process_frame
	_check(collection.discovered_creation_ids == expected_ids
		and collection.recipe_grid.get_child_count() == 9,
		label + ": Recipe Collection independently loads the successful result save")
	for index in range(BOARD.size()):
		var card: Control = collection.recipe_grid.get_child(index)
		var id: StringName = BOARD[index]
		var known := expected_ids.has(id)
		var artwork: TextureRect = card.find_child("Artwork", true, false)
		var title: Label = card.find_child("RecipeName", true, false)
		_check(card.get_meta("creation_id") == id and card.get_meta("discovered") == known
			and artwork.texture == CONTENT.creation_for_id(id).texture
			and artwork.material == (null if known else collection.locked_silhouette_material)
			and title.text == tr(String(CONTENT.creation_for_id(id).display_name_key) if known else "COLLECTION_UNKNOWN"),
			"%s: saved Recipe Collection card %d has correct icon/name/state" % [label, index + 1])
	if capture:
		await _capture(capture_prefix + "_recipes_" + label)
	collection.queue_free()
	await process_frame


func _check_pool(stage: int, label: String) -> void:
	_check(sandbox._spawn_stage_index == stage and CONTENT.spawn_stages[stage].weights == EXPECTED_POOLS[stage],
		label + ": exact unchanged run spawn stage and weights")
	var expected_rng := RandomNumberGenerator.new()
	expected_rng.state = sandbox._rng.state
	var exact := true
	var seen: Array[StringName] = []
	for index in range(256):
		var roll := expected_rng.randf() * 100.0
		var expected: StringName = &"wheat"
		if stage == 1 and roll >= 75.0:
			expected = &"flour"
		elif stage == 2:
			expected = &"wheat" if roll < 60.0 else (&"flour" if roll < 90.0 else &"cake_mix")
		var actual: StringName = sandbox._roll_spawn_creation_id()
		exact = exact and actual == expected
		if not seen.has(actual):
			seen.append(actual)
	_check(exact and sandbox._rng.state == expected_rng.state
		and seen.all(func(id): return EXPECTED_POOLS[stage].has(id)),
		label + ": 256 real selections match the seeded pool, one RNG draw each")
	if stage > 0:
		_check(seen.has(&"flour") and (stage < 2 or seen.has(&"cake_mix")),
			label + ": newly unlocked creations actually appear in selections")


func _contact_result(input: StringName, result: StringName, existing: PrototypePiece = null,
		capture := false) -> PrototypePiece:
	var before := _baseline(result)
	var selection := [sandbox._current_creation_id, sandbox._raw_next_creation_id, sandbox._rng.state]
	var previous_stage: int = sandbox._spawn_stage_index
	var discoveries_before: int = sandbox._new_discoveries_this_run.count(result)
	var first := existing
	if first == null:
		first = _spawn(input, 0.5)
		first.position.x -= first.radius - 0.1
	var second: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(input),
		first.position + Vector2(first.radius * 2.0 - 0.2, 0))
	if second.position.x + second.radius > sandbox.right_wall.position.x:
		second.position = first.position - Vector2(first.radius * 2.0 - 0.2, 0)
	var contacts_before: int = sandbox.contact_events
	var first_sequence: int = first.spawn_sequence
	var second_sequence: int = second.spawn_sequence
	var completed := await _wait_for(func(): return sandbox.result_spawns.get(result, 0) > before.spawns, 5.0)
	_check(completed, "actual monitored contact creates " + String(result))
	if not completed:
		return null
	# Check from physical result existence, not from reward/discovery completion:
	# this catches a cosmetic failure between creating the body and awarding it.
	_check(sandbox.contact_events > contacts_before and _live(result).size() == 1
		and sandbox.result_spawns.get(result, 0) == before.spawns + 1,
		String(result) + ": exactly one physical result from actual contact")
	_check(not is_instance_valid(first) and not is_instance_valid(second)
		and sandbox.exits.get(first_sequence, 0) == 1 and sandbox.exits.get(second_sequence, 0) == 1,
		String(result) + ": both sources consumed exactly once")
	_assert_rewards(result, before)
	_check([sandbox._current_creation_id, sandbox._raw_next_creation_id, sandbox._rng.state] == selection,
		String(result) + ": merge leaves buffered drops and RNG untouched")
	if not expected_ids.has(result):
		expected_ids.append(result)
		var ordered: Array[StringName] = []
		for id in BOARD:
			if expected_ids.has(id):
				ordered.append(id)
		expected_ids = ordered
	var stage := maxi(previous_stage, 2 if result == &"cake_mix" else (1 if result == &"flour" else 0))
	_check(sandbox._spawn_stage_index == stage,
		String(result) + ": current-run stage updates with the same successful result")
	await _check_consumers(String(result), capture)
	await _frames(65)
	_assert_rewards(result, before)
	_check(sandbox.result_spawns.get(result, 0) == before.spawns + 1
		and sandbox._new_discoveries_this_run.count(result) == discoveries_before + int(not before.known),
		String(result) + ": later animation/physics never repeats result or discovery")
	var results := _live(result)
	if results.size() != 1:
		return null
	return results[0]


func _fresh_run(label: String) -> void:
	var settings := ConfigFile.new()
	settings.set_value("settings", "unrelated", "preserved")
	_check(settings.save(save_path) == OK, "isolated fresh discovery fixture: " + label)
	await _reset()
	expected_ids.clear()
	slot_instances = sandbox._recipe_progress_slots.duplicate()
	capture_prefix = "creation_result_" + label
	_check(sandbox.discovered_creation_ids.is_empty() and sandbox._spawn_stage_index == 0,
		"fresh run has no saved discoveries and only Wheat: " + label)
	_check_pool(0, "opening")
	var point: Vector2 = sandbox._chamber_rect.get_center()
	_touch(41, true, point)
	_touch(41, false, point)
	_check(await _wait_for(func(): return sandbox._piece_sequence == 1 and not sandbox._drop_cycle_active, 2.0),
		"real indexed-touch machine cycle drops first Wheat")
	expected_ids.append(&"wheat")
	_check(sandbox.registrations.get(&"wheat", 0) == 1 and sandbox.discoveries.get(&"wheat", 0) == 1
		and sandbox.score == 0 and sandbox.pulse_charge == 0 and sandbox._spawn_stage_index == 0,
		"normal Wheat drop discovers once without merge rewards or run unlock")
	await _check_consumers("wheat", true)
	_check(await _wait_for(func(): return _live(&"wheat").size() == 1 and _live(&"wheat")[0].sleeping, 4.0),
		"first dropped Wheat settles before continuous physical ladder")


func _test_scroll() -> void:
	var scroll: ScrollContainer = sandbox.machine_presentation.collection_scroll
	var rect := scroll.get_global_rect()
	var before := [sandbox._piece_sequence, sandbox._rng.state, sandbox._current_creation_id]
	scroll.scroll_horizontal = 0
	var point := rect.get_center() + Vector2(rect.size.x * 0.3, 0)
	_touch(42, true, point)
	for index in range(8):
		var drag := InputEventScreenDrag.new()
		drag.index = 42
		drag.relative = Vector2(-24, 0)
		point += drag.relative
		drag.position = point
		root.push_input(drag, true)
		await process_frame
	_touch(42, false, point)
	_check(scroll.scroll_horizontal > 60 and scroll.scroll_vertical == 0
		and [sandbox._piece_sequence, sandbox._rng.state, sandbox._current_creation_id] == before,
		"discovered collection remains touch-scrollable without gameplay drops or RNG changes")
	scroll.scroll_horizontal = 0
	var wheel := InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	wheel.pressed = true
	wheel.position = Vector2(rect.position.x + 2, rect.get_center().y)
	root.push_input(wheel, true)
	_check(scroll.scroll_horizontal > 0
		and [sandbox._piece_sequence, sandbox._rng.state, sandbox._current_creation_id] == before,
		"discovered collection also accepts a mouse wheel through its edge mask")
	scroll.scroll_horizontal = 100000
	await process_frame
	_check(rect.grow(1).encloses(sandbox._recipe_progress_slots[-1].get_global_rect()),
		"discovered Fancy Cake is reachable at canonical slot nine")
	await _capture(capture_prefix + "_strip_fancy_cake_scrolled")


func _test_ladder(label: String, comprehensive: bool) -> void:
	await _fresh_run(label)
	var scene_id: int = sandbox.get_instance_id()
	var piece: PrototypePiece = _live(&"wheat")[0] if _live(&"wheat").size() == 1 else null
	for pair in PHYSICAL:
		piece = await _contact_result(pair[0], pair[1], piece, true)
		if piece == null:
			return
		_check_pool(mini(2, BOARD.find(pair[1])), String(pair[1]))
	_check(sandbox.get_instance_id() == scene_id and expected_ids == BOARD
		and sandbox.score == 568 and sandbox.pulse_charge == 96,
		"same continuous run creates all nine semantic IDs with exact ladder rewards")
	_check(BOARD.all(func(id): return sandbox.discoveries.get(id, 0) == 1),
		"every semantic creation ID is newly discovered exactly once")
	await _test_scroll()
	if not comprehensive:
		return
	var saved_hash := FileAccess.get_sha256(save_path)
	for pair in PHYSICAL:
		await _clear_board()
		await _contact_result(pair[0], pair[1])
		_check(FileAccess.get_sha256(save_path) == saved_hash
			and BOARD.all(func(id): return sandbox.discoveries.get(id, 0) == 1),
			"repeat " + String(pair[1]) + " rewards once but never rediscovers or rewrites the save")
	sandbox._restart_sandbox()
	await process_frame
	_check_pool(0, "Restart")
	await _check_consumers("restart")
	_check(FileAccess.get_sha256(save_path) == saved_hash and sandbox.score == 0 and sandbox.pulse_charge == 0,
		"Restart preserves saved discoveries while clearing current-run rewards")
	await _contact_result(&"wheat", &"flour")
	_check(sandbox._spawn_stage_index == 1, "already discovered Flour still unlocks this new run")
	sandbox._enter_game_over()
	sandbox.play_again_button.pressed.emit()
	await process_frame
	_check_pool(0, "Play Again")
	await _check_consumers("play_again")
	_check(not sandbox.game_over and sandbox.score == 0 and sandbox.pulse_charge == 0
		and FileAccess.get_sha256(save_path) == saved_hash, "Play Again resets only run state")
	await _reset()
	slot_instances = sandbox._recipe_progress_slots.duplicate()
	_check_pool(0, "scene reload")
	await _check_consumers("scene_reload")
	_check(FileAccess.get_sha256(save_path) == saved_hash, "new scene loads all discoveries without rewriting save")


func _test_missing_optional_presentation() -> void:
	await _fresh_run("missing_optional_presentation")
	await _clear_board()
	sandbox.presentation.free()
	await _contact_result(&"wheat", &"flour")
	_check(sandbox._spawn_stage_index == 1 and sandbox.score == 8 and sandbox.pulse_charge == 12,
		"absent optional presentation cannot block result rewards, discovery or spawn unlock")
	# This fixture removes only disposable merge/discovery visuals, not the
	# required machine transaction. Do not rebuild presentation in production.
	sandbox.queue_free()
	await process_frame


func _run() -> void:
	var base_save_path := save_path
	var sizes := [Vector2i(540, 960)] if DisplayServer.get_name() == "headless" else [
		Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]
	for index in range(sizes.size()):
		var size: Vector2i = sizes[index]
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		save_path = base_save_path + "_%sx%s.cfg" % [size.x, size.y]
		await _test_ladder("%sx%s" % [size.x, size.y], index == sizes.size() - 1)
	save_path = base_save_path + "_missing_presentation.cfg"
	await _test_missing_optional_presentation()
	print("CREATION RESULT FLOW: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
