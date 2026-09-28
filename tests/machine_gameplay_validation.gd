extends "res://tests/kitchen_recipe_validation.gd"


func _test_authored_tuning() -> void:
	# Exercise the same native properties/serialization as Inspector edits,
	# never changing production scenes or the user's saves.
	var source := load("res://scenes/presentation/machine_drop_presentation.tscn") as PackedScene
	var edited := source.instantiate()
	edited.production_mode = true
	edited.set_editable_instance(edited.get_node("TopMachine/Totolina"), true)
	var changes := {
		"TopMachine/FeederGlass": {"scale": Vector2(0.34, 0.34), "position": Vector2(244, 123)},
		"TopMachine/Shutter": {"position": Vector2(196, 224)},
		"TopMachine/SampleScore/Token": {"scale": Vector2(0.065, 0.065)},
		"TopMachine/Totolina": {"position": Vector2(8, 60), "scale": Vector2(0.175, 0.175)},
		"TopMachine/Totolina/Visual/Eyes": {"position": Vector2(403, 171), "scale": Vector2(1.08, 1.08)},
		"TopMachine/Totolina/Visual": {"position": Vector2(2, 3)},
		"TopMachine/Totolina/Visual/Arms": {"position": Vector2(652, 410)},
		"TopMachine/Button": {"position": Vector2(13, 166)},
		"TopMachine/Current": {"position": Vector2(245, 182), "scale": Vector2(0.115, 0.115)},
		"TopMachine/Next": {"position": Vector2(245, 97), "scale": Vector2(0.106, 0.106)},
		"TopMachine/Nozzle": {"position": Vector2(248, 265), "scale": Vector2(0.151, 0.151)}
	}
	for path in changes:
		for property in changes[path]:
			edited.get_node(path).set(property, changes[path][property])
	var packed := PackedScene.new()
	_check(packed.pack(edited) == OK, "Inspector-equivalent machine edits pack")
	_check(ResourceSaver.save(packed, "user://tuned_machine.tscn") == OK, "tuned scene saves")
	edited.free()
	var reopened := ResourceLoader.load("user://tuned_machine.tscn", "", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	var m := reopened.instantiate()
	root.add_child(m)
	m.cat.set_idle(false)
	m.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	_check_tuned_properties(m, changes, "ready after save/reopen")
	for mode in m.ACTIONS:
		m.play_action(mode)
		m.player.advance(0.15)
		if mode == &"excited":
			_check(m.cat.visual.position.y < 3.0, "reaction moves relative to edited base")
		m.player.advance(1.0)
		m.reset()
		_check_tuned_properties(m, changes, "reset after " + String(mode))
	var other := source.instantiate()
	other.production_mode = true
	root.add_child(other)
	other.cat.set_idle(false)
	var untouched: Animation = other.player.get_animation(&"full_drop")
	m.set_target(90)
	m.play_action(&"full_drop")
	_check(untouched.track_get_key_value(other._nozzle_track, 1) == 350.0,
		"input-driven nozzle endpoints cannot mutate another scene's timeline")
	m.queue_free()
	other.queue_free()
	await process_frame
	var masks := load("res://scenes/presentation/collection_masks.tscn").instantiate() as Control
	masks.get_node("LeftMask").offset_left = -8.0
	masks.get_node("LeftMask").offset_right = -8.0
	masks.get_node("RightMask").offset_left = 8.0
	masks.get_node("RightMask").offset_right = 8.0
	packed = PackedScene.new()
	_check(packed.pack(masks) == OK and ResourceSaver.save(packed, "user://tuned_masks.tscn") == OK,
		"mask Control anchor/offset edits save")
	masks.free()
	masks = (ResourceLoader.load("user://tuned_masks.tscn", "", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate()
	var holder := Control.new()
	holder.size = Vector2(405, 67)
	root.add_child(holder)
	holder.add_child(masks)
	await process_frame
	for width in [390.0, 405.0, 540.0]:
		holder.size = Vector2(width, width * 67.0 / 500.0)
		await process_frame
		_check(is_equal_approx(masks.get_node("LeftMask").position.x, -8.0)
			and is_equal_approx(masks.get_node("RightMask").position.x, width + 8.0),
			"mask authored offsets survive resize at %s" % width)
		_check(masks.mouse_filter == Control.MOUSE_FILTER_IGNORE
			and masks.get_node("LeftMask").mouse_filter == Control.MOUSE_FILTER_IGNORE
			and masks.get_node("RightMask").mouse_filter == Control.MOUSE_FILTER_IGNORE,
			"edited foreground masks remain input transparent")
	holder.queue_free()
	await process_frame


func _check_tuned_properties(node: Node, changes: Dictionary, phase: String) -> void:
	for path in changes:
		for property in changes[path]:
			var actual: Vector2 = node.get_node(path).get(property)
			_check(actual.is_equal_approx(changes[path][property]), "%s preserves %s.%s" % [phase, path, property])


func _test_release_transaction() -> void:
	await _reset()
	sandbox.set_physics_process(false)
	var view = sandbox.machine_presentation
	var machine = view.machine
	_check(machine.production_mode and machine.assets_ok and machine.falling_item == null
		and not machine.has_node("StaticCollectionPreview"), "shared production machine has no fake drop or lab UI")
	_check(machine.current_preview_scale == Vector2.ONE * 0.110 and machine.next_preview_scale == Vector2.ONE * 0.105,
		"production previews enlarged independently of physics")
	_check(machine.get_node("TopMachine/FeederGlass").z_index > machine.current_item.z_index,
		"glass in front of previews")
	_check(machine.get_node("TopMachine/Shutter").z_index < machine.current_item.z_index,
		"shutter behind previews")
	var idle_arm: Sprite2D = machine.cat.arms[0]
	var shoulder: Sprite2D = machine.cat.visual.get_node("ShoulderOverlap")
	# The authored idle arm now hangs beside the body above the overlap patch;
	# the three reaching poses still pass below that patch at the shoulder root.
	_check(machine.cat.arms.map(func(arm): return arm.z_index) == [4, 2, 2, 2]
		and idle_arm.position == Vector2(-16, 17) and is_zero_approx(idle_arm.rotation)
		and idle_arm.scale == Vector2.ONE * 1.10 and idle_arm.offset == Vector2(-110, -60)
		and idle_arm.get_parent().position == Vector2(650, 410)
		and shoulder.z_index == 3 and shoulder.visible and not shoulder.centered
		and shoulder.position == Vector2(530, 325) and shoulder.region_enabled
		and shoulder.region_rect == Rect2(530, 325, 170, 95)
		and shoulder.texture == machine.cat.visual.get_node("cat_totolina_body").texture,
		"authored idle contour and press-arm shoulder overlap preserve pose-specific layering")
	_check(machine.cat.eyes.all(func(eye): return eye.scale == Vector2.ONE)
		and machine.cat.expression_eyes.all(func(eye): return eye.scale == Vector2.ONE),
		"blink and both expressions reuse approved eye scale")
	_check((machine.cat.eyes + machine.cat.expression_eyes).all(func(eye):
		return (eye.position == Vector2.ZERO and eye.offset == -Vector2(164, 64) and eye.scale == Vector2.ONE
			and eye.get_parent().position == Vector2(401, 173) and eye.get_parent().scale == Vector2.ONE * 1.10)),
		"all five eye overlays share the face center, pivot and approved smaller scale")
	_check(machine.cat.scale == Vector2.ONE * 0.15 and machine.cat.position == Vector2(9, 78)
		and machine.cat.z_index == -4, "authored cat/body transform and machine depth unchanged")
	var feeder: Sprite2D = machine.get_node("TopMachine/FeederGlass")
	var shutter: Node2D = machine.get_node("TopMachine/Shutter")
	var painted := feeder.texture.get_image().get_used_rect()
	var feeder_bounds := Rect2(feeder.position + (Vector2(painted.position) - feeder.texture.get_size() * 0.5) * feeder.scale,
		Vector2(painted.size) * feeder.scale)
	var shutter_bounds := Rect2(shutter.position, Vector2(1024, 208) * shutter.scale)
	# The art pass raised the shutter by 10px (211.5 -> 201.5); translate the
	# original 2..6px bottom-inset band by that rise without widening its tolerance.
	_check(feeder.scale == Vector2.ONE * 0.32
		and shutter.position.is_equal_approx(Vector2(209, 201.5))
		and shutter.scale == Vector2.ONE * (100.0 / 1024.0)
		and shutter_bounds.position.y < feeder_bounds.end.y
		and shutter_bounds.end.y <= feeder_bounds.end.y - 12.0
		and shutter_bounds.end.y > feeder_bounds.end.y - 16.0
		and feeder_bounds.end.x < machine.get_node("TopMachine/SampleScore").position.x,
		"authored shutter remains inset within glass and clears score housing")
	_check(view.frame.get_node("LowerInterior").z_index < sandbox.pieces.z_index
		and not view.frame.get_node("LowerInterior").z_as_relative
		and not view.frame.get_node("Chamber").visible,
		"only lower interior uses rear depth; template is never double drawn")
	_check(machine.cat.visual.get_node("cat_totolina_ear_left").scale == Vector2.ONE * 1.05
		and machine.cat.visual.get_node("cat_totolina_ear_right").scale == Vector2.ONE * 1.05,
		"shared approved ear scale and source pivots retained")
	_check(view.rear.z_index < machine.nozzle.z_index and machine.nozzle.z_index < sandbox.pieces.z_index
		and sandbox.pieces.z_index < sandbox.presentation.z_index and sandbox.presentation.z_index < view.frame.z_index,
		"rear < nozzle < real bodies < approved merge effects < front frame")
	# Use the existing earned stage, not an independent test preview queue.
	sandbox._spawn_stage_index = 2
	sandbox._current_creation_id = &"flour"
	sandbox._raw_next_creation_id = &"cake_mix"
	sandbox._update_next_preview()
	var rng := RandomNumberGenerator.new()
	rng.state = sandbox._rng.state
	var expected_next := CONTENT.spawn_stages[2].select_creation(rng)
	var previous_rng: int = sandbox._rng.state
	var sequence: int = sandbox._piece_sequence
	sandbox._drop_piece(-1000)
	var x: float = sandbox._drop_target_x
	sandbox._drop_piece(1000)
	sandbox._advance_machine_drop(0.19)
	_check(sandbox._piece_sequence == sequence and sandbox._rng.state == previous_rng,
		"no body or RNG advancement before 0.20s")
	_check(is_equal_approx(machine.nozzle.global_position.x, x), "nozzle arrives before release; later taps cannot retarget")
	sandbox._advance_machine_drop(0.01)
	var bodies := _live(&"flour")
	_check(bodies.size() == 1 and sandbox._piece_sequence == sequence + 1, "exactly one CURRENT real body at 0.20s")
	_check(bodies[0].global_position.is_equal_approx(view.release_position(x)), "body at clamped nozzle outlet")
	_check(is_equal_approx(machine.cat.arm_pose, 3.0) and is_equal_approx(machine.button_pose, 2.0)
		and is_equal_approx(machine.shutter_pose, 5.0), "approved paw/button contact and open shutter at release")
	_check(not machine.current_item.visible, "no duplicate CURRENT artwork after physical handoff")
	_check(sandbox._current_creation_id == &"cake_mix" and sandbox._raw_next_creation_id == expected_next
		and sandbox._rng.state == rng.state, "one buffered handoff, one new seeded NEXT draw")
	sandbox._advance_machine_drop(0.40)
	_check(sandbox._drop_cycle_active, "cycle protects remaining button return through 0.60s")
	sandbox._advance_machine_drop(0.03)
	_check(not sandbox._drop_cycle_active and not machine.busy and sandbox._piece_sequence == sequence + 1,
		"ready after 0.62s; no duplicate release")
	_check(machine.current_item.texture == CONTENT.creation_for_id(&"cake_mix").texture
		and machine.next_item.texture == CONTENT.creation_for_id(expected_next).texture, "real queue matches feeder after handoff")
	sandbox.score = 128
	sandbox._update_debug_ui()
	_check(machine.score_text.text == "00128", "monitor uses padded real score")
	sandbox.score = 1234567
	sandbox._update_debug_ui()
	_check(machine.score_text.text == "1234567" and machine.score_text.get_theme_font_size("font_size") < 28,
		"long scores fit monitor without truncating digits or changing score")
	for index in range(12):
		var current: StringName = sandbox._current_creation_id
		var next: StringName = sandbox._raw_next_creation_id
		var expected := CONTENT.spawn_stages[2].select_creation(rng)
		sandbox._drop_piece(_x(0.7 if index % 2 else 0.3))
		sandbox._advance_machine_drop(0.9) # Long tick must cross contact before feeder completion.
		_check(sandbox._piece_sequence == sequence + index + 2 and sandbox._current_creation_id == next
			and sandbox._raw_next_creation_id == expected and sandbox._rng.state == rng.state,
			"successive long-tick drop %d advances exactly once, preserves RNG" % index)
		_check(machine.current_item.texture == CONTENT.creation_for_id(next).texture,
			"long-tick preview has no stale sample handoff %s" % current)
		for piece in sandbox.pieces.get_children():
			piece.queue_free()
		await process_frame
	# Gameplay never relies on AnimationPlayer's contact method track finishing.
	sandbox._drop_piece(_x(0.5))
	machine.player.stop()
	var count: int = sandbox._piece_sequence
	sandbox._advance_machine_drop(0.63)
	_check(sandbox._piece_sequence == count + 1 and not machine.busy, "stopped cosmetics cannot lose accepted gameplay release or leave a stale busy flag")


func _test_interruptions_and_reaction() -> void:
	for elapsed in [0.08, 0.20, 0.45]:
		await _reset()
		sandbox.set_physics_process(false)
		sandbox._drop_piece(_x(0.4))
		sandbox._advance_machine_drop(elapsed)
		var rng_state: int = sandbox._rng.state
		var count: int = sandbox._piece_sequence
		sandbox._enter_game_over()
		_check(not sandbox._drop_cycle_active and not sandbox.machine_presentation.machine.busy,
			"game over clears cycle at %.2f" % elapsed)
		# Normal physics tick must not advance after game over.
		sandbox._physics_process(1.0)
		_check(sandbox._piece_sequence == count and sandbox._rng.state == rng_state,
			"game over neither invents nor undoes an already committed drop")
		sandbox.play_again_button.pressed.emit()
		await process_frame
		_check(not sandbox.game_over and not sandbox._drop_cycle_active and sandbox.pieces.get_child_count() == 0,
			"Play Again cleans machine + board")
		sandbox._drop_piece(_x(0.5))
		sandbox._advance_machine_drop(elapsed)
		sandbox._restart_sandbox()
		await process_frame
		_check(not sandbox._drop_cycle_active and sandbox.pieces.get_child_count() == 0
			and sandbox._current_creation_id == &"wheat", "Restart during each machine phase is safe")
	await _reset()
	sandbox.set_physics_process(false)
	sandbox._drop_piece(_x(0.5))
	sandbox.machine_presentation.show_merge_reaction()
	sandbox.machine_presentation.show_merge_reaction()
	_check(sandbox.machine_presentation.machine.action == &"full_drop", "press has priority over merge reactions")
	sandbox._advance_machine_drop(0.63)
	_check(sandbox.machine_presentation.machine.action == &"excited", "multiple merges coalesce to one approved excited reaction")
	sandbox._drop_piece(_x(0.6))
	_check(sandbox._drop_cycle_active and sandbox.machine_presentation.machine.action == &"full_drop",
		"new player drop interrupts reaction without delaying input")
	sandbox._cancel_machine_drop()
	sandbox.machine_presentation.show_merge_reaction()
	sandbox._advance_machine_drop(0.57)
	_check(not sandbox.machine_presentation.machine.busy, "excited returns to idle")
	var rng: int = sandbox._rng.state
	sandbox._drop_piece(_x(0.4))
	sandbox._debug_clear_board()
	sandbox._advance_machine_drop(0.7)
	await process_frame
	_check(sandbox.pieces.get_child_count() == 0 and not sandbox._drop_cycle_active and sandbox._rng.state == rng,
		"debug Clear Board cancels a pending release without advancing queue/RNG")
	sandbox._drop_piece(_x(0.4))
	sandbox.queue_free()
	await process_frame
	await create_timer(0.7).timeout
	_check(true, "teardown during active cycle leaves no timed callback")


func _test_realtime() -> void:
	await _reset()
	# Drain scene-loading delta before measuring live physics ticks. SceneTree's
	# idle timer can include the long import/instantiation frame in headless runs.
	for index in range(3):
		await physics_frame
	var count: int = sandbox._piece_sequence
	sandbox._drop_piece(_x(0.5))
	for index in range(6):
		await physics_frame
	_check(sandbox._piece_sequence == count, "native runtime: no early body")
	for index in range(8):
		await physics_frame
	_check(sandbox._piece_sequence == count + 1, "native runtime: body falling before full sequence ends")
	for index in range(25):
		await physics_frame
	_check(not sandbox._drop_cycle_active, "native runtime: next cycle ready")


func _portraits() -> void:
	if DisplayServer.get_name() == "headless":
		return
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		await _reset()
		sandbox.set_physics_process(false)
		if is_instance_valid(sandbox._debug_spawn_panel):
			sandbox._debug_spawn_panel.hide()
		sandbox.score = 128
		sandbox.pulse_charge = 84
		sandbox._current_creation_id = &"cake_mix"
		sandbox._raw_next_creation_id = &"flour"
		sandbox._update_debug_ui()
		sandbox.discovered_creation_ids.assign([&"wheat", &"cake_mix", &"sponge_cake"])
		sandbox._update_recipe_progress()
		_check(is_equal_approx(sandbox.machine_presentation.danger_line.points[0].y, sandbox._danger_threshold_y)
			and sandbox.machine_presentation.danger_line.z_index > sandbox.machine_presentation.frame.z_index,
			"danger line matches gameplay threshold and remains above frame trim")
		for item in [[&"wheat", 0.15], [&"cake_batter", 0.36], [&"sponge_cake", 0.70]]:
			var piece := _spawn(item[0], item[1])
			piece.freeze = true
		await process_frame
		var view = sandbox.machine_presentation
		var seam: float = sandbox.controls_panel.get_global_rect().position.y
		_check(view.frame.get_global_rect().is_equal_approx(Rect2(0, 0, size.x, seam))
			and view.rear.get_global_rect() == view.frame.get_global_rect(),
			"rear/front fill width and end at the full-bleed controls seam")
		var footer := view.frame.get_node("Footer") as NinePatchRect
		_check(is_equal_approx(footer.position.y - (1595.0 - view.floor_edge_texture_y) * footer.scale.y,
			sandbox.floor.position.y - sandbox._wall_thickness * 0.5),
			"visible inner floor remains anchored to unchanged physics floor")
		var header := view.frame.get_node("Header") as NinePatchRect
		_check(is_equal_approx(header.size.y * header.scale.y,
			view.machine.position.y + 425.0 * view.machine.scale.y * 500.0 / 859.0),
			"frame top trim retains existing header attachment height")
		_check(sandbox.recipe_progress_panel.get_global_rect().position.y >= sandbox.floor.position.y,
			"larger collection stays below physics floor")
		var prefix := "machine_gameplay_%dx%d" % [size.x, size.y]
		await _capture(prefix + "_idle")
		await _test_floor_depth(prefix)
		await _test_corner_depth(prefix)
		_check(sandbox.recipe_progress_panel.get_global_rect().end.y < sandbox.controls_panel.get_global_rect().position.y,
			"portrait collection does not overlap controls")
		_check(sandbox._recipe_progress_slots.size() == 9, "portrait keeps all canonical collection slots")
		sandbox._drop_piece(_x(0.62))
		sandbox._advance_machine_drop(0.20)
		for piece in sandbox.pieces.get_children():
			piece.freeze = true
		await _capture(prefix + "_release")
		sandbox._advance_machine_drop(0.20)
		await _capture(prefix + "_feeder")
		sandbox._advance_machine_drop(0.24)
		sandbox.machine_presentation.show_merge_reaction()
		sandbox._advance_machine_drop(0.15)
		await _capture(prefix + "_excited")
		for pose in ["blink", "surprised"]:
			view.machine.reset()
			view.machine.cat.set_idle(false)
			if pose == "blink":
				view.machine.cat.blink_pose = 2.0
			else:
				view.machine.play_action(&"surprised")
				view.machine.player.advance(0.15)
			await _capture(prefix + "_" + pose)
		sandbox._enter_game_over()
		await _capture(prefix + "_result")
		# Explicit logical notch/home-inset fixture. No hardware-safe-area claim.
		var safe := Rect2(Vector2(8, 40), Vector2(size) - Vector2(16, 72))
		var width := minf(safe.size.x, sandbox._chamber_rect.size.x + 52.0)
		view.layout(sandbox._chamber_rect, sandbox.floor.position.y, sandbox._wall_thickness, safe, Vector2(size), seam)
		_check(view.frame.get_global_rect() == Rect2(0, 0, size.x, seam)
			and is_equal_approx(view.release_position(0).y, safe.position.y + width / 500.0 * 269.0),
			"safe header retains original release transform while backdrop is full bleed")


func _test_floor_depth(prefix: String) -> void:
	# Render a diagnostic patch on the REAL bodies' layer, crossing the lower
	# interior and both side rails. This isolates compositing from art transparency.
	for part in ["LowerInterior", "LowerFrontLip"]:
		var floor_layer: Control = sandbox.machine_presentation.frame.get_node(part)
		var marker := Polygon2D.new()
		var y := floor_layer.position.y + floor_layer.size.y * 0.5
		var width := root.get_visible_rect().size.x
		marker.polygon = PackedVector2Array([Vector2(0, y), Vector2(width, y), Vector2(width, y + 4), Vector2(0, y + 4)])
		marker.color = Color.MAGENTA
		sandbox.pieces.add_child(marker)
		await _capture(prefix + "_depth_probe_" + part)
		var image := root.get_texture().get_image()
		var middle := image.get_pixel(roundi(width * 0.5), roundi(y + 2))
		var rail := image.get_pixel(roundi(width * 0.035), roundi(y + 2))
		_check(middle.is_equal_approx(Color.MAGENTA) and not rail.is_equal_approx(Color.MAGENTA),
			"rendered body layer covers %s but remains masked by side rails" % part)
		marker.queue_free()
		await process_frame


func _test_corner_depth(prefix: String) -> void:
	# Real resting bubbles at both legal wall limits, not just the chamber center.
	# Compare opaque artwork pixels with/without the foreground masks. Any difference
	# inside the legal lower-corner area exposes an overly wide foreground mask.
	var corner_pieces: Array[PrototypePiece] = []
	var surface: float = sandbox.floor.position.y - sandbox._wall_thickness * 0.5
	var left: float = sandbox.left_wall.position.x + sandbox._wall_thickness * 0.5
	var right: float = sandbox.right_wall.position.x - sandbox._wall_thickness * 0.5
	for edge in [left, right]:
		var piece := _spawn(&"wheat", 0.5)
		piece.freeze = true
		piece.position = Vector2(edge + (piece.radius if edge == left else -piece.radius), surface - piece.radius)
		corner_pieces.append(piece)
	var view = sandbox.machine_presentation
	var interior: Control = view.frame.get_node("LowerInterior")
	_check(interior.position.x < left and interior.get_rect().end.x > right,
		"lower foreground masks stay outside legal resting area")
	await _capture(prefix + "_corner_bubbles")
	var foreground_image := root.get_texture().get_image()
	# Keep rear floor/lip clips visible in BOTH images. Hiding them as well
	# changes the background seen through antialiased bubble pixels, not masking.
	var masks: Array[Control] = []
	for node in view.frame.get_children():
		if node is Control and node.visible and node.z_as_relative:
			masks.append(node)
			node.hide()
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var unobscured_image := root.get_texture().get_image()
	for node in masks:
		node.show()
	for piece in corner_pieces:
		var sprite: Sprite2D = piece.get_node("Visual/IngredientSprite")
		var art := sprite.texture.get_image()
		var checked_pixels := 0
		var occluded_pixels := 0
		var bottom_pixel := -1
		for y in range(floori(surface - piece.radius), ceili(surface) + 2):
			for x in range(floori(piece.position.x - piece.radius), ceili(piece.position.x + piece.radius)):
				var local := sprite.to_local(Vector2(x + 0.5, y + 0.5)) + sprite.texture.get_size() * 0.5
				if not Rect2(Vector2.ZERO, sprite.texture.get_size()).has_point(local):
					continue
				var alpha := art.get_pixel(floori(local.x), floori(local.y)).a
				if alpha > 0.1:
					bottom_pixel = maxi(bottom_pixel, y)
				if alpha < 0.995:
					continue
				checked_pixels += 1
				var a := foreground_image.get_pixel(x, y)
				var b := unobscured_image.get_pixel(x, y)
				if Vector3(a.r - b.r, a.g - b.g, a.b - b.b).length() > 0.02:
					occluded_pixels += 1
		_check(checked_pixels > 10 and occluded_pixels == 0,
			"actual resting corner bubble is not concealed by lower bevel (%d/%d pixels)" % [occluded_pixels, checked_pixels])
		_check(absf(bottom_pixel - surface) < 2.0,
			"visible corner bubble reaches unchanged physical floor within raster tolerance")
		piece.queue_free()
	await process_frame


func _run() -> void:
	await _test_authored_tuning()
	await _test_release_transaction()
	await _test_interruptions_and_reaction()
	await _test_realtime()
	await _portraits()
	if is_instance_valid(sandbox):
		sandbox.queue_free()
		await process_frame
	print("MACHINE GAMEPLAY: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
