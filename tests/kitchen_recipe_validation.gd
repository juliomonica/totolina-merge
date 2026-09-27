extends SceneTree

const CONTENT = preload("res://config/worlds/kitchen/kitchen_content.tres")
const SANDBOX = preload("res://scenes/prototype/physics_sandbox.tscn")
const CONFIG = preload("res://scripts/config/gameplay_configuration.gd")
const BOARD = [&"wheat", &"flour", &"cake_mix", &"cake_batter", &"sponge_cake",
	&"frosted_cake", &"layer_cake", &"decorated_cake", &"fancy_cake"]
const PHYSICAL = [
	[&"wheat", &"flour"], [&"flour", &"cake_mix"], [&"cake_mix", &"cake_batter"],
	[&"cake_batter", &"sponge_cake"], [&"sponge_cake", &"frosted_cake"],
	[&"frosted_cake", &"layer_cake"], [&"layer_cake", &"decorated_cake"], [&"decorated_cake", &"fancy_cake"],
]
const REMOVED = [&"egg", &"beaten_eggs", &"milk", &"cream"]

var sandbox: Node2D
var checks := 0
var failures := 0
var output_dir := ""
var save_path := ""


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--test-output-dir="):
			output_dir = argument.trim_prefix("--test-output-dir=")
	if not output_dir.is_absolute_path() or not DirAccess.dir_exists_absolute(output_dir):
		push_error("Pass --test-output-dir with an existing absolute temporary directory.")
		quit(2)
		return
	save_path = output_dir.path_join("discoveries_%s.cfg" % Time.get_ticks_usec())
	_run.call_deferred()


func _check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("PASS: ", description)
	else:
		failures += 1
		push_error("FAIL: " + description)


func _reset() -> void:
	if is_instance_valid(sandbox):
		sandbox.queue_free()
		await process_frame
	sandbox = SANDBOX.instantiate()
	sandbox._discovery_save_path = save_path
	root.add_child(sandbox)
	await process_frame


func _x(ratio: float) -> float:
	return sandbox._chamber_rect.position.x + sandbox._chamber_rect.size.x * ratio


func _radius(id: StringName) -> float:
	return CONTENT.effective_radius_ratio(CONTENT.creation_for_id(id)) * sandbox._chamber_rect.size.x


func _spawn(id: StringName, ratio: float, airborne := false) -> PrototypePiece:
	var y: float = sandbox.floor.position.y - sandbox._wall_thickness * 0.5 - _radius(id) - 0.1
	if airborne:
		y = sandbox._chamber_rect.position.y + 100.0
	return sandbox._spawn_piece(CONTENT.creation_for_id(id), Vector2(_x(ratio), y))


func _live(id: StringName) -> Array:
	return sandbox.pieces.get_children().filter(func(piece: Node) -> bool:
		return not piece.is_queued_for_deletion() and piece.creation_id == id)


func _wait_for(predicate: Callable, seconds := 6.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await create_timer(0.02).timeout
	return predicate.call()


func _capture(name: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(output_dir.path_join(name + ".png"))


func _test_content() -> void:
	_check(CONTENT.creations.size() == 9 and CONTENT.recipes.size() == 8, "exactly nine board creations / eight recipes")
	_check(CONTENT.collection_creations().map(func(d): return d.id) == BOARD, "canonical collection order")
	for index in range(BOARD.size()):
		var definition: CreationDefinition = CONTENT.creation_for_id(BOARD[index])
		_check(definition != null and definition.progression_rank == index + 1
			and definition.size_order == index + 1 and definition.collection_order == index + 1
			and definition.visual_diameter_scale == 2.18 and definition.texture.get_size() == Vector2(512, 512),
			"board definition / rank / orders / art: %s" % BOARD[index])
	for pair in PHYSICAL:
		var recipe: MergeRecipe = CONTENT.recipe_for(pair[0], pair[0])
		_check(recipe != null and recipe.result == pair[1] and recipe.input_a == recipe.input_b, "same + same = next: %s" % str(pair))
	_check(CONTENT.recipes.all(func(r): return r.input_a == r.input_b), "zero mixed or automatic recipes")
	for id in REMOVED:
		_check(CONTENT.creation_for_id(id) == null and CONTENT.recipes.all(func(r):
			return r.input_a != id and r.input_b != id and r.result != id), "retired identity absent from board: %s" % id)
	_check(CONTENT.recipe_for(&"fancy_cake", &"fancy_cake") == null and CONTENT.final_creation_id == &"fancy_cake", "final creation")
	_check(CONTENT.spawn_stage_errors().is_empty() and CONTENT.spawn_stages.size() == 3,
		"three valid run-based spawn stages")
	var effects := 0
	var expected_effects := {&"cake_mix": &"egg_crack", &"cake_batter": &"milk_pour", &"frosted_cake": &"cream_swirl"}
	for recipe in CONTENT.recipes:
		if not recipe.effect_animation.is_empty():
			effects += 1
			_check(expected_effects.get(recipe.result, &"") == recipe.effect_animation,
				"exact approved flavor mapping: " + String(recipe.result))
	_check(effects == 3, "exactly three flavor effects")


func _test_reset_and_rng() -> void:
	await _reset()
	var rng := RandomNumberGenerator.new()
	rng.seed = sandbox.INITIAL_SEED
	var expected: Array[StringName] = []
	for index in range(1002):
		rng.randf()
		expected.append(&"wheat")
	_check([sandbox._current_creation_id, sandbox._raw_next_creation_id] == expected.slice(0, 2), "seeded DROP and buffered NEXT")
	var actual: Array[StringName] = []
	for index in range(1000):
		actual.append(sandbox._roll_spawn_creation_id())
	_check(actual == expected.slice(2) and sandbox._rng.state == rng.state, "1000 fresh-run Wheat draws; one RNG call each")
	sandbox._restart_sandbox()
	var repeated: Array[StringName] = []
	for index in range(1000):
		repeated.append(sandbox._roll_spawn_creation_id())
	_check(repeated == actual, "restart repeats RNG")
	for id in REMOVED:
		var foreign := CreationDefinition.new()
		foreign.id = id
		_check(sandbox._spawn_piece(foreign, Vector2.ZERO) == null, "cannot spawn removed board creation: %s" % id)
	sandbox._restart_sandbox()
	var next: StringName = sandbox._raw_next_creation_id
	sandbox._drop_piece(_x(0.5))
	sandbox._advance_machine_drop(0.63)
	_check(sandbox._current_creation_id == next
		and sandbox.next_preview_ingredient.texture == CONTENT.creation_for_id(next).texture, "drop advances buffered preview")
	_check(not sandbox.get_script().get_script_method_list().any(func(m): return m.name == "_complete_auto_craft"), "no automatic execution path")
	sandbox._begin_restart_hold()
	sandbox._cancel_restart_hold()
	_check(sandbox.pieces.get_child_count() == 1, "quick/partial hold does not reset")
	sandbox._begin_restart_hold()
	await create_timer(1.1).timeout
	_check(sandbox.pieces.get_child_count() == 0 and sandbox.score == 0 and sandbox.pulse_charge == 0, "full hold resets run")


func _test_danger_push() -> void:
	await _reset()
	var piece := _spawn(&"wheat", 0.5)
	sandbox.pulse_charge = 100
	sandbox._activate_pulse(Vector2.RIGHT)
	# Observe integrated physics, not an idle timer that can include the long
	# scene-instantiation frame on a cold/headless renderer.
	for index in range(4):
		await physics_frame
	await process_frame
	_check(sandbox.pulse_charge == 0 and piece.linear_velocity.x > 0, "Push still applies horizontal impulse and consumes charge")
	piece.freeze = true
	piece.position.y = sandbox._danger_threshold_y - piece.radius - 1
	piece.sleeping = true
	piece.linear_velocity = Vector2.ZERO
	await create_timer(CONFIG.DANGER_GRACE_SECONDS + 0.2).timeout
	_check(sandbox.game_over and sandbox.result_overlay.visible, "unchanged danger/grace reaches game over")
	sandbox.play_again_button.pressed.emit()
	await process_frame
	_check(not sandbox.game_over and sandbox.pieces.get_child_count() == 0 and sandbox.score == 0, "Play Again clears run")

func _test_navigation() -> void:
	sandbox.queue_free()
	await process_frame
	change_scene_to_file(ProjectSettings.get_setting("application/run/main_scene"))
	await process_frame
	await process_frame
	_check(current_scene.scene_file_path == "res://scenes/menu/main_menu.tscn", "Main Menu loads")
	current_scene.recipes_button.pressed.emit()
	await process_frame
	await process_frame
	_check(current_scene.recipe_grid.get_child_count() == 9, "Recipes navigation loads 9 cards")
	current_scene.back_button.pressed.emit()
	await process_frame
	await process_frame
	current_scene.start_button.pressed.emit()
	await process_frame
	await process_frame
	_check(current_scene.scene_file_path == "res://scenes/prototype/physics_sandbox.tscn", "Back / Start enter gameplay")
	current_scene.queue_free()
	await process_frame


func _run() -> void:
	_test_content()
	await _test_reset_and_rng()
	await _test_danger_push()
	await _test_navigation()
	print("LOCKED KITCHEN RECIPES: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
