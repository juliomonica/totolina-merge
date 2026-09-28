extends "res://tests/merge_integration_validation.gd"

const CUSTOM := [&"flour", &"cake_mix", &"sponge_cake"]
var phone_viewport: SubViewport
var custom_merges := 0


func _flavors() -> Array:
	return sandbox.presentation.merge_effects.get_children().filter(
		func(n): return n is MergeFlavorEffect and not n.is_queued_for_deletion())


func _begin_custom(input: StringName) -> Dictionary:
	var recipe: MergeRecipe = CONTENT.recipe_for(input, input)
	var before := _baseline(recipe.result)
	var rng: int = sandbox._rng.state
	var current: StringName = sandbox._current_creation_id
	var next: StringName = sandbox._raw_next_creation_id
	var sources: Array = sandbox._debug_spawn_creations(input, 2)
	_check(sources.size() == 2, "real debug Spawn Pair accepts " + String(input))
	var source_ids: Array = sources.map(func(p): return p.spawn_sequence)
	_check(await _wait_for(func(): return sandbox.result_spawns.get(recipe.result, 0) > before.spawns),
		"physical contact creates " + String(recipe.result))
	_check(_flavors().size() == 1 and sandbox.presentation.merge_effects.get_child_count() == 1,
		"one approved effect; no old/static effect underneath")
	_check(sandbox.machine_presentation.machine.action == &"excited"
		or sandbox.machine_presentation._reaction_pending,
		"successful physical merge requests approved excited reaction without delaying rewards")
	if _flavors().is_empty():
		return {}
	var effect: MergeFlavorEffect = _flavors()[0]
	_assert_flavor(effect, recipe)
	_check(effect.scale.x > 0.0 and effect.scale.is_equal_approx(Vector2.ONE * effect.scale.x),
		"visible uniform presentation fit")
	_check(_live(recipe.result).size() == 1 and _live(recipe.result)[0].get_node("Visual/IngredientSprite").visible,
		"authoritative result is already physical and visible before completion")
	_assert_piece(_live(recipe.result)[0])
	_assert_rewards(recipe.result, before)
	_check(sandbox._rng.state == rng and sandbox._current_creation_id == current and sandbox._raw_next_creation_id == next,
		"effect/merge does not draw RNG or replace DROP/NEXT")
	_check(sources.all(func(p): return not is_instance_valid(p))
		and source_ids.all(func(id): return sandbox.exits.get(id, 0) == 1),
		"both source bodies consumed exactly once")
	custom_merges += 1
	return {"recipe": recipe, "before": before, "effect": effect}


func _stable_after(data: Dictionary) -> void:
	_assert_rewards(data.recipe.result, data.before)
	_check(sandbox.result_spawns.get(data.recipe.result, 0) == data.before.spawns + 1,
		"one result remains authoritative regardless of presentation")


func _test_interruptions() -> void:
	for input in CUSTOM:
		for action in ["finish", "free_visual", "restart", "play_again", "game_over", "scene_exit"]:
			await _reset()
			var data := await _begin_custom(input)
			if data.is_empty():
				continue
			var effect: MergeFlavorEffect = data.effect
			match action:
				"finish":
					await _frames(55)
					_stable_after(data)
				"free_visual":
					effect.queue_free()
					await _frames(55)
					_check(_live(data.recipe.result).size() == 1, "freeing presentation does not delete real result")
					_stable_after(data)
				"restart":
					sandbox._restart_sandbox()
					await _frames(55)
					_check(sandbox.score == 0 and sandbox.pulse_charge == 0 and sandbox.pieces.get_child_count() == 0,
						"restart during effect has no late result/reward")
					_check(sandbox.discovered_creation_ids.has(data.recipe.result), "restart preserves completed discovery")
				"play_again":
					sandbox._enter_game_over()
					sandbox.play_again_button.pressed.emit()
					await _frames(55)
					_check(not sandbox.game_over and sandbox.score == 0 and sandbox.pieces.get_child_count() == 0,
						"Play Again during effect clears presentation/new run")
					_check(sandbox.discovered_creation_ids.has(data.recipe.result), "Play Again retains completed discovery")
				"game_over":
					sandbox._enter_game_over()
					await _frames(55)
					_check(sandbox.game_over and sandbox.result_overlay.visible and _live(data.recipe.result).size() == 1,
						"game over lets disposable effect finish without losing result")
					_stable_after(data)
				"scene_exit":
					sandbox.queue_free()
					await _frames(55)
					_check(not is_instance_valid(sandbox), "scene teardown during effect")
			_check(not is_instance_valid(effect), "no surviving effect/player after " + action)
			if is_instance_valid(sandbox):
				_check(sandbox.presentation.merge_effects.get_child_count() == 0, "effect container returns empty")


func _test_repeat() -> void:
	await _reset()
	var instance: int = sandbox.get_instance_id()
	for cycle in range(3):
		for input in CUSTOM:
			var data := await _begin_custom(input)
			await _frames(55)
			if not data.is_empty():
				_stable_after(data)
			sandbox._debug_clear_board()
			await _frames(2)
	_check(sandbox.get_instance_id() == instance, "nine custom debug-pair merges in one continuous run")
	_check(get_processed_tweens().is_empty(), "no surviving custom-effect Tweens")


func _test_edge_fitting() -> void:
	await _reset()
	for input in CUSTOM:
		var recipe: MergeRecipe = CONTENT.recipe_for(input, input)
		var radius := _radius(recipe.result)
		var inset: float = sandbox._wall_thickness * 0.5
		var left: float = sandbox.left_wall.position.x + inset + radius
		var right: float = sandbox.right_wall.position.x - inset - radius
		var top: float = sandbox._chamber_rect.position.y + radius
		var bottom: float = sandbox.floor.position.y - inset - radius
		for point in [Vector2(left, top), Vector2(right, top), Vector2(left, bottom), Vector2(right, bottom)]:
			# Isolated presentation bounds test, separate from physical merge tests.
			sandbox.presentation.show_recipe_merge(recipe, point, radius * 3.0)
			var effect: MergeFlavorEffect = _flavors()[0]
			effect.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
			var duration := effect.player.get_animation(recipe.effect_animation).length
			var fits := true
			for sample in range(81):
				effect.player.seek(duration * sample / 80.0, true)
				fits = fits and _poses_fit(effect)
			_check(fits and effect.global_position.is_equal_approx(point) and effect.scale.x > 0.0,
				"wall/floor/top fitting preserves actual anchor without clipping")
			effect.queue_free()
			await process_frame
	await _frames(2)


func _capture(name: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var viewport: Viewport = phone_viewport if is_instance_valid(phone_viewport) else root
	_check(viewport.get_texture().get_image().save_png(output_dir.path_join(name + ".png")) == OK,
		"saved " + name)


func _poses_fit(effect: MergeFlavorEffect) -> bool:
	var area := sandbox.get_viewport_rect()
	for pose in effect.poses:
		if not pose.is_visible_in_tree() or pose.modulate.a < 0.001:
			continue
		var rect := pose.get_rect()
		for point in [rect.position, Vector2(rect.end.x, rect.position.y), rect.end,
				Vector2(rect.position.x, rect.end.y)]:
			if not area.has_point(pose.to_global(point)):
				return false
	return true


func _hold_capture_phase(effect_ref: WeakRef, target_time: float) -> bool:
	var deadline := Time.get_ticks_msec() + 6000
	while Time.get_ticks_msec() < deadline:
		var live_effect := effect_ref.get_ref() as MergeFlavorEffect
		if live_effect == null or live_effect.is_queued_for_deletion() \
			or not is_instance_valid(live_effect.player) or not live_effect.player.is_playing():
			return false
		if live_effect.player.current_animation_position >= target_time:
			# The engine reaches the phase in real time; only capture I/O is held.
			live_effect.player.pause()
			return true
		await create_timer(0.02).timeout
	return false


func _production_portraits() -> void:
	if DisplayServer.get_name() == "headless":
		return
	phone_viewport = SubViewport.new()
	phone_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	phone_viewport.size_2d_override_stretch = true
	root.add_child(phone_viewport)
	for dimensions in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		phone_viewport.size = dimensions
		phone_viewport.size_2d_override = Vector2i(540, roundi(dimensions.y * 540.0 / dimensions.x))
		for input in CUSTOM:
			await _reset()
			sandbox.reparent(phone_viewport)
			sandbox._layout_chamber()
			await _frames(2)
			# Real Spawn Pair, then real contact. Place source fixtures lower
			# before physics so captures inspect an ordinary in-bowl merge.
			var result: StringName = CONTENT.recipe_for(input, input).result
			var before := _baseline(result)
			var sources: Array = sandbox._debug_spawn_creations(input, 2)
			for source in sources:
				source.position.y = sandbox._chamber_rect.position.y + source.radius + sandbox._chamber_rect.size.y * 0.57
			_check(await _wait_for(func(): return sandbox.result_spawns.get(result, 0) > before.spawns),
				"phone capture uses real physical merge")
			if _flavors().is_empty():
				_check(false, "phone effect exists")
				continue
			var effect: MergeFlavorEffect = _flavors()[0]
			var result_piece: PrototypePiece = _live(result)[0]
			var spawn_positions: Dictionary = sandbox.result_spawn_positions
			# The flavor stays at the spawn anchor while the physical result can fall.
			_check(spawn_positions.has(result_piece.spawn_sequence)
				and effect.global_position.distance_to(spawn_positions[result_piece.spawn_sequence]) < 5.0,
				"effect anchor equals actual initial result spawn location")
			var animation: StringName = CONTENT.recipe_for(input, input).effect_animation
			var duration := effect.player.get_animation(animation).length
			var effect_ref: WeakRef = weakref(effect)
			for phase in [0.2, 0.5, 0.8]:
				var reached := await _hold_capture_phase(effect_ref, duration * phase)
				_check(reached, "real-time phase advances with a live effect")
				if reached:
					_check(_poses_fit(effect), "visible source canvases fit phone without clipping")
					_check(effect.global_position.y > sandbox.hud_panel.get_global_rect().end.y,
						"in-bowl animation stays beneath HUD layer")
					await _capture("%dx%d_%s_%02d" % [dimensions.x, dimensions.y, animation, int(phase * 100)])
					# Drain the capture's elapsed time through a complete paused frame.
					await RenderingServer.frame_post_draw
					if is_instance_valid(effect) and not effect.is_queued_for_deletion():
						effect.player.play(animation)
			await _frames(45)
			_stable_after({"recipe": CONTENT.recipe_for(input, input), "before": before})
			_check(not is_instance_valid(effect) and _live(result).size() == 1, "clear real-result payoff")
			await _capture("%dx%d_%s_payoff" % [dimensions.x, dimensions.y, animation])
			_check(phone_viewport.get_texture().get_size() == Vector2(dimensions), "exact portrait pixel dimensions")
	sandbox.queue_free()
	await process_frame
	phone_viewport.queue_free()
	await process_frame


func _run() -> void:
	await _test_interruptions()
	await _test_repeat()
	await _test_edge_fitting()
	await _production_portraits()
	if is_instance_valid(sandbox):
		sandbox.queue_free()
		await process_frame
	print("MERGE FLAVOR: %d checks, %d failures; %d custom physical merges" % [checks, failures, custom_merges])
	quit(1 if failures else 0)
