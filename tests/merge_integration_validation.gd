extends "res://tests/kitchen_recipe_validation.gd"

const AUDIT = preload("res://tests/merge_audit_sandbox.gd")
var physical_completed := 0
var flavor_counts: Dictionary = {}


func _reset() -> void:
	if is_instance_valid(sandbox):
		sandbox.queue_free()
		await process_frame
	sandbox = SANDBOX.instantiate()
	var locked_material: ShaderMaterial = sandbox.recipe_locked_silhouette_material
	sandbox.set_script(AUDIT)
	# Attaching the observer resets exported script fields; preserve scene art.
	sandbox.recipe_locked_silhouette_material = locked_material
	sandbox._discovery_save_path = save_path
	root.add_child(sandbox)
	sandbox.presentation.merge_effects.child_entered_tree.connect(func(node: Node):
		if node.has_meta("recipe_result"):
			var id: StringName = node.get_meta("recipe_result")
			flavor_counts[id] = flavor_counts.get(id, 0) + 1
	)
	await create_timer(0.1).timeout


func _frames(count := 60) -> void:
	for i in range(count):
		await physics_frame
	await process_frame


func _assert_piece(piece: PrototypePiece) -> void:
	var definition: CreationDefinition = CONTENT.creation_for_id(piece.creation_id)
	_check(definition != null and piece.definition == definition and definition.texture != null,
		"result has valid creation and texture: " + String(piece.creation_id))
	var expected := _radius(piece.creation_id)
	var collider: CollisionShape2D = piece.get_node("CollisionShape2D")
	var sprite: Sprite2D = piece.get_node("Visual/IngredientSprite")
	_check(is_finite(expected) and expected > 0 and collider.shape is CircleShape2D
		and is_equal_approx(collider.shape.radius, expected) and is_equal_approx(piece.radius, expected),
		"positive finite effective CircleShape2D radius")
	_check(piece.scale.is_equal_approx(Vector2.ONE) and collider.scale.is_equal_approx(Vector2.ONE)
		and collider.position == Vector2.ZERO and sprite.centered and sprite.offset == Vector2.ZERO
		and sprite.position == Vector2.ZERO and sprite.get_parent().position == Vector2.ZERO,
		"body/collider transforms unchanged and artwork concentric")
	_check(sprite.texture == definition.texture and definition.visual_diameter_scale == 2.18
		and is_equal_approx(sprite.scale.x * 512.0, expected * 2.18)
		and is_equal_approx(sprite.scale.x, sprite.scale.y) and is_equal_approx(piece.mass, definition.mass),
		"matching visual diameter / aspect / mass; 2.18 calibration")


func _baseline(result: StringName) -> Dictionary:
	return {"score": sandbox.score, "push": sandbox.pulse_charge,
		"awards": sandbox.awards.get(result, 0), "spawns": sandbox.result_spawns.get(result, 0),
		"registers": sandbox.registrations.get(result, 0), "discoveries": sandbox.discoveries.get(result, 0),
		"known": sandbox.discovered_creation_ids.has(result), "highest": sandbox.highest_creation_id,
		"effects": flavor_counts.get(result, 0)}


func _assert_flavor(effect: MergeFlavorEffect, recipe: MergeRecipe) -> void:
	var index := effect.EFFECT_NAMES.find(recipe.effect_animation)
	_check(index >= 0 and effect.poses.size() == effect.FILES[index].size()
		and effect.player.current_animation == recipe.effect_animation,
		"one shared AnimationPlayer runs the approved poses")
	for frame in range(effect.poses.size()):
		_check(effect.poses[frame].texture.resource_path == effect.ASSET_DIRECTORY + effect.FILES[index][frame],
			"exact approved pose texture")
	_check(effect.find_children("*", "CollisionObject2D", true, false).is_empty()
		and effect.find_children("*", "CollisionShape2D", true, false).is_empty()
		and effect.find_children("*", "Timer", true, false).is_empty(),
		"effect contains no physics/collision/timers")


func _assert_rewards(result: StringName, before: Dictionary) -> void:
	var definition: CreationDefinition = CONTENT.creation_for_id(result)
	_check(sandbox.score == before.score + definition.progression_rank * definition.progression_rank * 2
		and sandbox.pulse_charge == mini(100, before.push + 12)
		and sandbox.awards.get(result, 0) == before.awards + 1,
		"score and +12 Push awarded exactly once: " + String(result))
	_check(sandbox.registrations.get(result, 0) == before.registers + 1
		and sandbox.discoveries.get(result, 0) == before.discoveries + int(not before.known)
		and sandbox.discovered_creation_ids.count(result) == 1,
		"discovery registered once, no repeat unlock: " + String(result))
	var highest: CreationDefinition = CONTENT.creation_for_id(sandbox.highest_creation_id)
	_check(highest != null and highest.progression_rank >= definition.progression_rank,
		"highest creation remains valid")


func _physical(input: StringName, result: StringName, existing: PrototypePiece = null) -> PrototypePiece:
	var before := _baseline(result)
	var first := existing
	if first == null:
		first = _spawn(input, 0.5)
		first.position.x -= first.radius - 0.1
	var second: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(input),
		first.position + Vector2(first.radius * 2.0 - 0.2, 0))
	# Keep large late-game fixture inputs inside the unchanged chamber.
	if second.position.x + second.radius > sandbox.right_wall.position.x:
		second.position = first.position - Vector2(first.radius * 2.0 - 0.2, 0)
	var first_seq: int = first.spawn_sequence
	var second_seq: int = second.spawn_sequence
	var contacts_before: int = sandbox.contact_events
	_check(await _wait_for(func(): return sandbox.result_spawns.get(result, 0) > before.spawns, 5.0),
		"physical completion: %s + %s -> %s" % [input, input, result])
	var recipe: MergeRecipe = CONTENT.recipe_for(input, input)
	if not recipe.effect_animation.is_empty():
		_check(flavor_counts.get(result, 0) == before.effects + 1, "one optional flavor effect for physical result")
		var flavors: Array = sandbox.presentation.merge_effects.get_children().filter(func(n): return n.has_meta("recipe_result"))
		_check(flavors.size() == 1, "one active flavor instance")
		if flavors.size() == 1:
			var effect: MergeFlavorEffect = flavors[0]
			_assert_flavor(effect, recipe)
			await _capture("flavor_intro_" + String(result) + "_" + str(root.get_texture().get_size()))
			await create_timer(0.22).timeout
			_check(effect.poses[0].modulate.a < 0.01
				and effect.poses.slice(1).any(func(p): return p.modulate.a > 0.01), "approved bubble transitions into action poses")
			var action: Sprite2D = effect.poses[1]
			_check(sandbox.get_viewport_rect().encloses(action.get_global_transform() * action.get_rect()), "action visual stays inside logical viewport")
			await _capture("flavor_action_" + String(result) + "_" + str(root.get_texture().get_size()))
	else:
		_check(flavor_counts.get(result, 0) == before.effects, "normal presentation when optional effect absent")
	await _frames(90)
	_check(sandbox.presentation.merge_effects.get_child_count() == 0, "presentation nodes/tweens clean up")
	_check(sandbox.contact_events > contacts_before, "real monitored physical contact, no direct resolver call")
	_check(not is_instance_valid(first) and not is_instance_valid(second)
		and sandbox.exits.get(first_seq, 0) == 1 and sandbox.exits.get(second_seq, 0) == 1,
		"both live inputs removed exactly once")
	var results := _live(result)
	_check(results.size() == 1 and sandbox.result_spawns.get(result, 0) == before.spawns + 1,
		"exactly one physical result; no double spawn")
	_assert_rewards(result, before)
	_check(not sandbox.game_over and not sandbox._merge_resolution_pending
		and sandbox._resolving_merge_pair.is_empty() and sandbox._queued_merge_pairs.is_empty(),
		"physics continues after cleanup; no stale physical reservation")
	_check(sandbox.merge_snapshots.all(func(snapshot): return snapshot.callback_depth == 0),
		"all replacements run outside collision callbacks")
	physical_completed += 1
	if results.size() != 1:
		print("MERGE TRACE: ", sandbox.merge_snapshots)
		return null
	_assert_piece(results[0])
	await _capture("merge_" + String(result) + "_" + str(root.get_texture().get_size()))
	return results[0]



func _clear_board() -> void:
	for piece in sandbox.pieces.get_children():
		piece.queue_free()
	await _frames(35)


func _test_repeated_and_chain() -> void:
	await _reset()
	var scene_id: int = sandbox.get_instance_id()
	for cycle in range(3):
		for pair in PHYSICAL:
			await _physical(pair[0], pair[1])
			await _clear_board()
	_check(sandbox.get_instance_id() == scene_id and physical_completed == 24, "24 physical merges in one continuous run")
	await _reset()
	scene_id = sandbox.get_instance_id()
	var piece: PrototypePiece
	for pair in PHYSICAL:
		piece = await _physical(pair[0], pair[1], piece)
		if piece == null:
			break
	_check(piece != null and piece.creation_id == &"fancy_cake" and sandbox.get_instance_id() == scene_id,
		"full eight-step ladder reaches Fancy Cake without scene reset")
	_check(sandbox.score == 568 and sandbox.pulse_charge == 96, "full ladder exact total rewards")


func _test_dense_sponge() -> void:
	await _reset()
	sandbox._merge_cooldown_remaining = 2.0 # Stage fixture only, not production tuning.
	var first := _spawn(&"sponge_cake", 0.5)
	var second: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(&"sponge_cake"),
		first.position - Vector2(0, first.radius * 2.0 + 0.1))
	var neighbour: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(&"flour"),
		second.position - Vector2(0, second.radius + _radius(&"flour") + 0.1))
	_spawn(&"wheat", 0.1)
	_spawn(&"cake_mix", 0.9)
	_check(await _wait_for(func(): return neighbour.sleeping, 1.6), "neighbour really sleeps on source before replacement")
	var previous_y := neighbour.position.y
	var before := _baseline(&"frosted_cake")
	_check(await _wait_for(func(): return _live(&"frosted_cake").size() == 1), "dense Sponge merge completes")
	await _frames(180)
	_check(not is_instance_valid(first) and not is_instance_valid(second), "dense sources consumed")
	_check(is_instance_valid(neighbour) and neighbour.position.y > previous_y + 5.0, "guarded wake lets unsupported sleeping neighbour descend")
	_check(_live(&"frosted_cake").size() == 1 and not sandbox.game_over, "dense pile stable after replacement")
	_assert_rewards(&"frosted_cake", before)
	_assert_piece(_live(&"frosted_cake")[0])
	await _capture("dense_sponge_" + str(root.get_texture().get_size()))


func _test_negative_contacts() -> void:
	for pair in [[&"wheat", &"flour"], [&"flour", &"cake_mix"], [&"sponge_cake", &"frosted_cake"], [&"fancy_cake", &"fancy_cake"]]:
		await _reset()
		var first := _spawn(pair[0], 0.5)
		var second: PrototypePiece = sandbox._spawn_piece(CONTENT.creation_for_id(pair[1]),
			first.position - Vector2(0, first.radius + _radius(pair[1]) - 0.1))
		await _frames(90)
		_check(is_instance_valid(first) and is_instance_valid(second) and sandbox.score == 0
			and sandbox.pulse_charge == 0 and sandbox.awards.is_empty(), "invalid different items / final pair stay physical and silent")
	# No contact must mean no merge, even for identical inputs.
	await _reset()
	_spawn(&"flour", 0.15)
	_spawn(&"flour", 0.85)
	await _frames(100)
	_check(_live(&"flour").size() == 2 and sandbox.score == 0, "separated identical pieces never merge remotely")


func _test_fallback_cleanup_and_pacing() -> void:
	await _reset()
	var recipe: MergeRecipe = CONTENT.recipe_for(&"flour", &"flour")
	var action := recipe.effect_animation
	recipe.effect_animation = &""
	await _physical(&"flour", &"cake_mix")
	recipe.effect_animation = action
	await _reset()
	var first := _spawn(&"flour", 0.45)
	sandbox._spawn_piece(CONTENT.creation_for_id(&"flour"), first.position + Vector2(first.radius * 1.99, 0))
	_check(await _wait_for(func(): return sandbox.presentation.merge_effects.get_child_count() > 0), "effect active before restart")
	sandbox._restart_sandbox()
	await _frames(50)
	_check(sandbox.presentation.merge_effects.get_child_count() == 0 and sandbox.score == 0
		and sandbox.pieces.get_child_count() == 0, "restart clears visuals and pending work without late reward")
	await _reset()
	var left := _spawn(&"wheat", 0.2)
	sandbox._spawn_piece(CONTENT.creation_for_id(&"wheat"), left.position + Vector2(left.radius * 1.99, 0))
	var right := _spawn(&"flour", 0.7)
	sandbox._spawn_piece(CONTENT.creation_for_id(&"flour"), right.position + Vector2(right.radius * 1.99, 0))
	_check(await _wait_for(func(): return sandbox.score > 0), "first simultaneous pair resolves")
	var score_after_first: int = sandbox.score
	await create_timer(0.20).timeout
	_check(sandbox.score == score_after_first, "second pair remains paced, no instant chain spam")
	_check(await _wait_for(func(): return sandbox.score == 26), "second contact resolves after cooldown")
	sandbox._enter_game_over()
	await _frames(60)
	_check(sandbox.score == 26 and sandbox.result_overlay.visible, "game over during presentation cannot duplicate rewards")


func _portraits() -> void:
	debug_collisions_hint = true
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		for pair in [[&"flour", &"cake_mix"], [&"cake_mix", &"cake_batter"], [&"sponge_cake", &"frosted_cake"], [&"decorated_cake", &"fancy_cake"]]:
			await _reset()
			await _physical(pair[0], pair[1])
			_check(root.get_texture().get_image().get_size() == size, "exact portrait dimensions")


func _run() -> void:
	if OS.get_cmdline_user_args().has("--portraits"):
		await _portraits()
	elif OS.get_cmdline_user_args().has("--sponge-only"):
		await _test_dense_sponge()
	else:
		_test_content()
		await _test_repeated_and_chain()
		await _test_dense_sponge()
		await _test_negative_contacts()
		await _test_fallback_cleanup_and_pacing()
	if is_instance_valid(sandbox):
		sandbox.queue_free()
		await process_frame
	print("MERGE INTEGRATION: %d checks, %d failures; %d physical observed" % [checks, failures, physical_completed])
	quit(1 if failures else 0)
