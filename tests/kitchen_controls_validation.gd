extends "res://tests/kitchen_recipe_validation.gd"

# These events traverse the actual viewport/GUI routing. No control signal is
# emitted by the fixture, and the runner isolates all saves in a disposable copy.
func _touch(index: int, pressed: bool, point: Vector2, canceled := false) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.pressed = pressed
	event.canceled = canceled
	event.position = point
	root.push_input(event, true)


func _drag(index: int, point: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = point
	event.relative = Vector2(20, 0)
	root.push_input(event, true)


func _mouse(pressed: bool, point: Vector2) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = point
	event.global_position = point
	root.push_input(event, true)


func _motion(point: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(event, true)


func _click(button: Button) -> void:
	var point := button.get_global_rect().get_center()
	_mouse(true, point)
	_mouse(false, point)


func _art_matches(button: Button, pressed: bool) -> bool:
	var base: Texture2D = button.pressed_art if pressed and button.pressed_art != null else button.normal_art
	var label: Texture2D = button.pressed_label if pressed and button.pressed_label != null else button.normal_label
	return button.get_node("Base").texture == base and button.get_node("LabelArt").texture == label


func _modal_button(name: String) -> Button:
	return sandbox.exit_run_modal.get_node("SafeBounds/Panel/" + name) as Button


func _fresh() -> void:
	paused = false
	await _reset()
	if is_instance_valid(sandbox._debug_spawn_panel):
		sandbox._debug_spawn_panel.hide()
	await process_frame


func _test_push_input() -> void:
	for use_touch in [false, true]:
		for direction in [-1, 1]:
			await _fresh()
			var piece := _spawn(&"wheat", 0.5)
			sandbox.pulse_charge = sandbox.MAX_PULSE_CHARGE
			sandbox._update_debug_ui()
			var button: Button = sandbox.pulse_left_button if direction < 0 else sandbox.pulse_right_button
			var count := [0]
			button.pressed.connect(func(): count[0] += 1)
			var point := button.get_global_rect().get_center()
			var sequence: int = sandbox._piece_sequence
			if use_touch:
				_touch(7, true, point)
			else:
				_mouse(true, point)
			_check(button.visual_pressed and _art_matches(button, true) and count[0] == 0 and sandbox.pulse_charge == 100,
				"%s Push %d shows pressed art before release" % ["touch" if use_touch else "mouse", direction])
			if use_touch:
				_touch(7, false, point)
				_touch(7, false, point) # Defensive duplicate release must be harmless.
			else:
				_mouse(false, point)
				_mouse(false, point)
			for index in range(4):
				await physics_frame
			await process_frame
			_check(count[0] == 1 and sandbox.pulse_charge == 0 and not button.visual_pressed and _art_matches(button, false),
				"one release performs exactly one Push and restores normal art")
			_check(piece.linear_velocity.x * direction > 0.0 and sandbox._piece_sequence == sequence,
				"Push impulse has requested direction; control input never drops a piece")


func _test_cancel_and_multitouch() -> void:
	await _fresh()
	sandbox.set_physics_process(false)
	sandbox.pulse_charge = 100
	sandbox._update_debug_ui()
	var button: Button = sandbox.pulse_left_button
	var point := button.get_global_rect().get_center()
	var outside: Vector2 = sandbox._chamber_rect.get_center()
	var count := [0]
	button.pressed.connect(func(): count[0] += 1)
	_touch(2, true, point)
	_touch(3, true, point)
	_touch(3, false, point)
	_check(button.visual_pressed and count[0] == 0, "secondary finger cannot release a control's owner")
	_touch(2, false, point, true)
	_check(not button.visual_pressed and _art_matches(button, false) and count[0] == 0 and sandbox.pulse_charge == 100,
		"canceled touch restores art without firing Push")
	_touch(4, true, point)
	_drag(4, outside)
	_touch(4, false, outside)
	_check(not button.visual_pressed and count[0] == 0 and not sandbox._drop_cycle_active,
		"dragging off a button cancels without leaking a chamber drop")
	_mouse(true, point)
	_motion(outside)
	_mouse(false, outside)
	_check(not button.visual_pressed and count[0] == 0, "mouse release outside restores normal art without activating")
	_mouse(true, point)
	sandbox.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	_mouse(false, point)
	_check(not button.visual_pressed and count[0] == 0 and sandbox.pulse_charge == 100,
		"focus-canceled native mouse press cannot activate on a later release inside")
	_touch(8, true, outside)
	_check(sandbox._active_drop_touch_index == 8 and sandbox._drop_cycle_active,
		"a gameplay finger can own an accepted machine cycle")
	_touch(9, true, point)
	_touch(10, true, point)
	_touch(10, false, point)
	_touch(9, false, point)
	_check(count[0] == 1 and sandbox._active_drop_touch_index == 8,
		"UI finger activates exactly once alongside an existing gameplay finger")
	sandbox._advance_machine_drop(0.63)
	_check(sandbox._piece_sequence == 1, "mixed gameplay/UI multitouch produces only the accepted gameplay drop")
	_touch(8, false, outside)
	_touch(11, true, sandbox.restart_button.get_global_rect().get_center())
	sandbox.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	_check(not sandbox.restart_button.visual_pressed and not sandbox._restart_hold_active,
		"focus loss clears pressed artwork and restart hold")
	_touch(11, false, point)


func _test_restart_hold() -> void:
	await _fresh()
	sandbox.set_process(false)
	sandbox.set_physics_process(false)
	var piece := _spawn(&"flour", 0.5)
	piece.freeze = true
	sandbox.score = 37
	var point: Vector2 = sandbox.restart_button.get_global_rect().get_center()
	var progress: TextureProgressBar = sandbox.restart_hold_progress
	_check(progress.fill_mode == TextureProgressBar.FILL_CLOCKWISE
		and is_equal_approx(progress.radial_fill_degrees, 360.0),
		"Restart indicator is a full clockwise radial fill")
	_mouse(true, point)
	sandbox._process(0.4)
	var outside: Vector2 = sandbox._chamber_rect.get_center()
	_motion(outside)
	sandbox._process(0.7)
	_check(sandbox.score == 37 and not sandbox._restart_hold_active and not sandbox.restart_button.visual_pressed,
		"moving a held mouse off Restart cancels before the one-second reset threshold")
	_mouse(false, outside)
	_touch(21, true, point)
	_check(sandbox._restart_hold_active and sandbox.restart_button.visual_pressed and progress.visible,
		"real Restart touch begins hold and shows radial feedback")
	sandbox._process(0.49)
	_check(is_equal_approx(progress.value / progress.max_value, 0.49) and sandbox.score == 37,
		"partial hold visibly fills radial progress without resetting")
	_touch(21, false, point)
	_check(not sandbox._restart_hold_active and not progress.visible and is_zero_approx(progress.value)
		and not sandbox.restart_button.visual_pressed and sandbox.score == 37 and is_instance_valid(piece),
		"early release clears radial/art and preserves the run")
	_touch(22, true, point)
	sandbox._process(0.6)
	_touch(22, false, point, true)
	_check(not sandbox._restart_hold_active and is_zero_approx(progress.value) and sandbox.score == 37,
		"canceled hold loses accumulated progress")
	_touch(23, true, point)
	sandbox._process(0.99)
	_check(sandbox.score == 37 and not piece.is_queued_for_deletion(), "0.99 second hold cannot reset")
	sandbox._process(0.01)
	await process_frame
	_check(sandbox.score == 0 and sandbox.pieces.get_child_count() == 0
		and not sandbox._restart_hold_active and not sandbox.restart_button.visual_pressed
		and not progress.visible and is_zero_approx(progress.value),
		"one full second resets run and restores normal button/radial state")
	_touch(23, false, point)
	_check(not sandbox._drop_cycle_active, "release after completed Restart cannot leak a gameplay drop")
	# Also prove native processing reaches the threshold without fixture advancement.
	sandbox.set_process(true)
	sandbox.score = 9
	_mouse(true, point)
	_check(await _wait_for(func(): return sandbox.score == 0, 1.5), "real process clock completes held mouse Restart")
	_mouse(false, point)


func _run_snapshot(piece: PrototypePiece) -> Dictionary:
	return {
		"rng": sandbox._rng.state, "score": sandbox.score, "pulse": sandbox.pulse_charge,
		"danger": sandbox.danger_timer, "danger_active": sandbox.danger_active,
		"current": sandbox._current_creation_id, "next": sandbox._raw_next_creation_id,
		"drop_active": sandbox._drop_cycle_active, "drop_elapsed": sandbox._drop_cycle_elapsed,
		"drop_creation": sandbox._drop_creation_id, "drop_target": sandbox._drop_target_x,
		"sequence": sandbox._piece_sequence, "cooldown": sandbox._merge_cooldown_remaining,
		"body_position": piece.position, "body_velocity": piece.linear_velocity,
		"machine_time": sandbox.machine_presentation.machine.player.current_animation_position,
	}


func _test_pause_and_resume() -> void:
	await _fresh()
	var piece := _spawn(&"cake_mix", 0.3, true)
	piece.linear_velocity = Vector2(15, 50)
	sandbox.score = 123
	sandbox.pulse_charge = 100
	sandbox.danger_active = true
	sandbox.danger_timer = 0.7
	sandbox._merge_cooldown_remaining = 0.22
	sandbox._update_debug_ui()
	var board: Vector2 = sandbox._chamber_rect.get_center()
	_touch(31, true, board)
	_touch(31, false, board)
	sandbox._advance_machine_drop(0.08)
	_touch(35, true, sandbox.restart_button.get_global_rect().get_center())
	_check(sandbox._restart_hold_active, "Restart can be held immediately before opening Exit")
	var before := _run_snapshot(piece)
	_click(sandbox.exit_run_button)
	_check(paused and sandbox.exit_run_modal.visible
		and sandbox.exit_run_modal.process_mode == Node.PROCESS_MODE_ALWAYS,
		"Exit opens an interactive modal and pauses the scene tree")
	_check(_run_snapshot(piece) == before, "opening Exit preserves the accepted machine transaction and run state")
	_check(not sandbox._restart_hold_active and not sandbox.restart_button.visual_pressed,
		"opening Exit cancels a partial Restart hold and clears its pressed art")
	_touch(35, false, sandbox.restart_button.get_global_rect().get_center())
	await create_timer(0.3, true).timeout
	_click(sandbox.pulse_left_button)
	_touch(32, true, board)
	_touch(32, false, board)
	_mouse(true, board)
	_mouse(false, board)
	var key := InputEventKey.new()
	key.keycode = KEY_RIGHT
	key.pressed = true
	root.push_input(key, true)
	_touch(33, true, sandbox.restart_button.get_global_rect().get_center())
	await create_timer(1.1, true).timeout
	_touch(33, false, sandbox.restart_button.get_global_rect().get_center())
	_check(_run_snapshot(piece) == before and not sandbox._restart_hold_active,
		"paused input cannot Push, drop or Restart; bodies, danger and machine time remain frozen")
	var resume := _modal_button("Resume")
	var point := resume.get_global_rect().get_center()
	_touch(34, true, point)
	_check(resume.visual_pressed and paused, "Resume has pressed feedback while the game is paused")
	_touch(34, false, point)
	_check(not paused and not sandbox.exit_run_modal.visible and _run_snapshot(piece) == before,
		"Resume closes modal and preserves exact RNG, score, previews, danger, body and accepted cycle")
	_check(await _wait_for(func(): return sandbox._piece_sequence == int(before.sequence) + 1, 1.0),
		"accepted pre-pause machine cycle continues and releases exactly one body")
	await create_timer(0.55).timeout
	_check(sandbox._piece_sequence == int(before.sequence) + 1 and not sandbox._drop_cycle_active,
		"Resume does not enqueue an extra drop")


func _test_pending_merge_pause() -> void:
	for resolve_already_deferred in [false, true]:
		await _fresh()
		sandbox.set_physics_process(false)
		var first := _spawn(&"wheat", 0.4)
		var second := _spawn(&"wheat", 0.6)
		first.freeze = true
		second.freeze = true
		# Queue the same callback used by physical contact, immediately before
		# Exit input, so the deferred work necessarily runs after tree pause.
		sandbox._on_piece_body_entered(second, first)
		if resolve_already_deferred:
			sandbox._evaluate_recipes()
			_check(sandbox._merge_resolution_pending, "merge resolver is already deferred before opening Exit")
		_click(sandbox.exit_run_button)
		await create_timer(0.15, true).timeout
		_check(paused and _live(&"wheat").size() == 2 and _live(&"flour").is_empty() and sandbox.score == 0,
			"pending %s cannot resolve or award while paused" % ["resolver" if resolve_already_deferred else "contact evaluation"])
		_click(_modal_button("Resume"))
		_check(await _wait_for(func(): return _live(&"flour").size() == 1, 1.0),
			"Resume safely completes the pending contact once")
		var awarded: int = sandbox.score
		await create_timer(0.12).timeout
		_check(awarded > 0 and sandbox.score == awarded and _live(&"wheat").is_empty(),
			"resumed deferred merge grants one reward without duplicating bodies")


func _sprite_painted_bounds(sprite: Sprite2D) -> Rect2:
	var local := Rect2(sprite.texture.get_image().get_used_rect())
	local.position += sprite.offset
	if sprite.centered:
		local.position -= sprite.texture.get_size() * 0.5
	return sprite.get_global_transform() * local


func _fitted_art_bounds(art: TextureRect) -> Rect2:
	var texture_size := art.texture.get_size()
	var fit := minf(art.size.x / texture_size.x, art.size.y / texture_size.y)
	var fitted_size := texture_size * fit
	return art.get_global_transform() * Rect2((art.size - fitted_size) * 0.5, fitted_size)


func _check_reference_controls(size: Vector2i) -> void:
	var buttons: Array = [sandbox.pulse_left_button, sandbox.restart_button, sandbox.pulse_right_button]
	var centers := [0.186, 0.5, 0.814]
	var first_art := _fitted_art_bounds(buttons[0].get_node("Base"))
	var height := first_art.size.y
	for index in range(buttons.size()):
		var button: Button = buttons[index]
		var base: TextureRect = button.get_node("Base")
		var fitted := _fitted_art_bounds(base)
		_check(base.stretch_mode == TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			and absf(fitted.size.y - height) <= 0.01
			and absf(fitted.position.y - first_art.position.y) <= 0.01,
			"%dx%d: %s has the shared painted button height and baseline" % [size.x, size.y, button.name])
		_check(absf(button.get_global_rect().get_center().x / size.x - centers[index]) <= 0.012,
			"%dx%d: %s sits at its reference horizontal position" % [size.x, size.y, button.name])
	var exit_rect: Rect2 = sandbox.exit_run_button.get_global_rect()
	var safe: Control = sandbox.gameplay_controls.get_node("SafeBounds")
	_check(exit_rect.size.is_equal_approx(Vector2(52, 52))
		and exit_rect.position.x >= safe.get_global_rect().position.x + 12.0
		and is_equal_approx(exit_rect.position.y, safe.get_global_rect().position.y),
		"%dx%d: Exit keeps its size and safe top clearance while moving inward" % [size.x, size.y])
	var top := INF
	var head_left := INF
	var head_right := -INF
	for part in ["cat_totolina_ear_left", "cat_totolina_ear_right", "cat_totolina_body"]:
		var sprite: Sprite2D = sandbox.machine_presentation.machine.cat.visual.get_node(part)
		var painted := _sprite_painted_bounds(sprite)
		top = minf(top, painted.position.y)
		if part != "cat_totolina_body":
			head_left = minf(head_left, painted.position.x)
			head_right = maxf(head_right, painted.end.x)
	var head_center := (head_left + head_right) * 0.5
	_check(absf(exit_rect.get_center().x - head_center) <= 8.0,
		"%dx%d: Exit is horizontally centered above Totolina's painted head" % [size.x, size.y])
	_check(exit_rect.end.y <= top,
		"%dx%d: Exit stays entirely above Totolina's painted ears/head" % [size.x, size.y])
	print("CONTROL LAYOUT %dx%d: Exit %s, cat top %.2f, head center %.2f, bottom height %.2f" % [size.x, size.y, exit_rect, top, head_center, height])
	_check(not sandbox.exit_run_modal.has_node("SafeBounds/Panel/Destination")
		and _modal_button("Confirm").normal_art.resource_path == "res://assets/worlds/kitchen/ui/modals/exit_run/exit_run_confirm_button.png",
		"%dx%d: modal has no destination caption and uses the replaced EXIT TO MENU artwork" % [size.x, size.y])


func _test_footer_continuity(size: Vector2i, prefix: String) -> void:
	var background: Control = sandbox.controls_panel.get_node("Background")
	var bounds := background.get_global_rect()
	var seam: float = sandbox.controls_panel.get_global_rect().position.y
	_check(bounds.is_equal_approx(Rect2(0, seam, size.x, size.y - seam)),
		"footer background fills full viewport width from controls seam to device bottom")
	for layer in [sandbox.machine_presentation.frame, sandbox.machine_presentation.rear]:
		var footer: NinePatchRect = layer.get_node("Footer")
		_check(is_equal_approx(footer.position.y + footer.size.y * footer.scale.y, bounds.position.y)
			and is_equal_approx(layer.get_global_rect().end.y, bounds.position.y),
			"machine bottom and footer background share exact edge contact")
		_check(not footer.visible, "footer layout template is not stretched or double drawn")
	for clip in sandbox.machine_presentation._footer_clips + [sandbox.machine_presentation._rear_footer]:
		for half in clip.get_children():
			if half.visible:
				var artwork: Sprite2D = half.get_node("Artwork")
				_check(artwork.scale.x == artwork.scale.y
					and artwork.region_rect == Rect2(0, 1595, 859, 236) and half.clip_contents,
					"frame footer uses uniformly scaled source artwork with disjoint crop clips")
	var art: Sprite2D = background.get_node("Artwork")
	_check(art.scale.x == art.scale.y and art.region_rect == Rect2(0, 8, 1080, 183)
		and background.clip_contents and background.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"footer artwork crops source padding and uniformly covers its input-transparent clip")
	for button in [sandbox.pulse_left_button, sandbox.restart_button, sandbox.pulse_right_button]:
		_check(bounds.encloses(button.get_global_rect()), "control remains on top of footer artwork")
	if DisplayServer.get_name() == "headless":
		return
	await _capture(prefix + "_footer_join")
	var normal := root.get_texture().get_image()
	# Expose any transparent gap with a contrasting plane BEHIND the machine.
	var probe := CanvasLayer.new()
	probe.layer = -9
	var color := ColorRect.new()
	color.color = Color.MAGENTA
	color.size = Vector2(size)
	color.mouse_filter = Control.MOUSE_FILTER_IGNORE
	probe.add_child(color)
	sandbox.add_child(probe)
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var contrasted := root.get_texture().get_image()
	var leaks := 0
	var leak_rows := {}
	for y in [floori(seam) - 1, floori(seam), floori(seam) + 1, size.y - 1]:
		for x in range(size.x):
			var a := normal.get_pixel(x, y)
			var b := contrasted.get_pixel(x, y)
			if Vector3(a.r - b.r, a.g - b.g, a.b - b.b).length() > 0.02:
				leaks += 1
				leak_rows[y] = int(leak_rows.get(y, 0)) + 1
	_check(leaks == 0, "rendered join and bottom screen row show no exposed backdrop (%d pixels, rows %s)" % [leaks, leak_rows])
	probe.queue_free()
	await process_frame


func _test_portraits() -> void:
	for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		root.size = size
		root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
		root.content_scale_size = size
		await _fresh()
		sandbox.set_process(false)
		sandbox.set_physics_process(false)
		sandbox.score = 128
		sandbox.pulse_charge = 100
		sandbox._update_debug_ui()
		var viewport := Rect2(Vector2.ZERO, Vector2(size))
		var safe: Control = sandbox.gameplay_controls.get_node("SafeBounds")
		for control in [sandbox.controls_panel, sandbox.pulse_left_button, sandbox.restart_button,
			sandbox.pulse_right_button, sandbox.exit_run_button]:
			_check(viewport.encloses(control.get_global_rect()) and safe.get_global_rect().encloses(control.get_global_rect()),
				"%dx%d: %s stays inside viewport and safe bounds" % [size.x, size.y, control.name])
		_check(sandbox.recipe_progress_panel.get_global_rect().end.y < sandbox.controls_panel.get_global_rect().position.y,
			"%dx%d: controls remain below the collection" % [size.x, size.y])
		_check_reference_controls(size)
		var prefix := "kitchen_controls_%dx%d" % [size.x, size.y]
		await _test_footer_continuity(size, prefix)
		await _capture(prefix + "_normal")
		var restart_point: Vector2 = sandbox.restart_button.get_global_rect().get_center()
		_touch(41, true, restart_point)
		sandbox._process(0.5)
		_check(is_equal_approx(sandbox.restart_hold_progress.value / sandbox.restart_hold_progress.max_value, 0.5),
			"%dx%d: half hold is a visible half radial" % [size.x, size.y])
		_check(sandbox.restart_hold_progress.get_global_rect().end.y
			<= sandbox.recipe_progress_panel.get_global_rect().position.y - 8.0 + 0.001,
			"%dx%d: Restart radial stays at least eight pixels above the collection" % [size.x, size.y])
		await _capture(prefix + "_half_hold")
		_touch(41, false, restart_point)
		_click(sandbox.exit_run_button)
		var panel: Control = sandbox.exit_run_modal.get_node("SafeBounds/Panel")
		_check(viewport.encloses(panel.get_global_rect()) and panel.is_visible_in_tree(),
			"%dx%d: Exit panel remains visible and within portrait" % [size.x, size.y])
		for name in ["Totolina", "Resume", "Confirm"]:
			var child: Control = panel.get_node(name)
			_check(viewport.encloses(child.get_global_rect()) and child.is_visible_in_tree(),
				"%dx%d: modal %s stays visible and inside viewport" % [size.x, size.y, name])
		await _capture(prefix + "_exit_modal")
		_click(_modal_button("Resume"))
		_check(not paused, "%dx%d: modal Resume remains clickable" % [size.x, size.y])
		# Logical notch/home-indicator fixture; this does not claim device QA.
		sandbox.gameplay_controls.set_safe_insets(Vector4(8, 40, 8, 32))
		await process_frame
		var inset_safe := Rect2(Vector2(8, 40), Vector2(size) - Vector2(16, 72))
		var seam: float = sandbox.gameplay_controls.layout_footer_background(Vector2(size))
		# Mirror _layout_safe_ui's collection anchors as well as its controls.
		# Moving only SafeBounds would leave the strip at its old desktop Y.
		var strip: Control = sandbox.recipe_progress_panel
		var edge: float = sandbox.GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
		strip.offset_left = 8.0 + edge
		strip.offset_right = -8.0 - edge
		strip.offset_bottom = seam - size.y - sandbox.GAMEPLAY_CONFIG.RECIPE_PROGRESS_CONTROLS_GAP_PIXELS
		strip.offset_top = strip.offset_bottom - sandbox.MACHINE_PRESENTATION.collection_height(size.x)
		sandbox.gameplay_controls.place_hold_progress(strip)
		sandbox.machine_presentation.layout(sandbox._chamber_rect, sandbox.floor.position.y,
			sandbox._wall_thickness, inset_safe.grow(-8.0), Vector2(size), seam)
		await process_frame
		_check(strip.get_global_rect().end.y < seam and inset_safe.encloses(strip.get_global_rect()),
			"simulated safe-area collection follows controls without overlap")
		await _test_footer_continuity(size, prefix + "_safe")
		for control in [sandbox.controls_panel, sandbox.exit_run_button]:
			_check(inset_safe.encloses(control.get_global_rect()),
				"%dx%d: %s respects simulated notch/home insets" % [size.x, size.y, control.name])
		_click(sandbox.exit_run_button)
		_check(inset_safe.encloses(panel.get_global_rect()),
			"%dx%d: Exit panel respects simulated safe insets" % [size.x, size.y])
		_click(_modal_button("Resume"))
		sandbox.score = 55
		sandbox._enter_game_over()
		await process_frame
		_check(sandbox.result_overlay.visible
			and sandbox.result_overlay.get_parent() == sandbox.gameplay_controls.get_parent()
			and sandbox.result_overlay.get_index() > sandbox.gameplay_controls.get_index(),
			"%dx%d: visible Game Over overlay draws above gameplay controls" % [size.x, size.y])
		_click(sandbox.play_again_button)
		await process_frame
		_check(not sandbox.game_over and not sandbox.result_overlay.visible and sandbox.score == 0,
			"%dx%d: gameplay controls cannot intercept the real Play Again click" % [size.x, size.y])


func _test_localization_and_art_alignment() -> void:
	await _fresh()
	sandbox.set_process(false)
	sandbox.set_physics_process(false)
	var original_locale := TranslationServer.get_locale()
	var restart: Button = sandbox.restart_button
	var localized: Label = restart.get_node("LocalizedLabel")
	var label_art: TextureRect = restart.get_node("LabelArt")
	for locale in ["en", "es", "zh_CN", "en"]:
		TranslationServer.set_locale(locale)
		await process_frame
		var english: bool = locale == "en"
		_check(localized.visible != english and label_art.visible == english,
			"%s Restart selects English label art or localized text" % locale)
		if not english:
			var expected := "REINICIAR" if locale == "es" else "重新开始"
			_check(localized.text == expected and localized.get_minimum_size().x <= localized.size.x,
				"%s Restart label translates and fits its authored bounds" % locale)
		var point := restart.get_global_rect().get_center()
		_touch(60, true, point)
		_check(_art_matches(restart, true) and localized.visible != english and label_art.visible == english,
			"%s pressed Restart retains the selected language presentation" % locale)
		_touch(60, false, point)
		_check(_art_matches(restart, false), "%s release restores normal Restart artwork" % locale)
	TranslationServer.set_locale(original_locale)
	await process_frame
	for button in [sandbox.pulse_left_button, sandbox.restart_button, sandbox.pulse_right_button]:
		var normal_base: Texture2D = button.normal_art
		var pressed_base: Texture2D = button.pressed_art
		var normal_label: Texture2D = button.normal_label
		var pressed_label: Texture2D = button.pressed_label
		_check(normal_base.get_size() == pressed_base.get_size() and normal_label.get_size() == pressed_label.get_size(),
			"%s normal/pressed alpha-trimmed artwork shares stable dimensions" % button.name)
		_check(button.get_node("Base").mouse_filter == Control.MOUSE_FILTER_IGNORE
			and button.get_node("LabelArt").mouse_filter == Control.MOUSE_FILTER_IGNORE
			and button.get_node("LocalizedLabel").mouse_filter == Control.MOUSE_FILTER_IGNORE,
			"%s artwork and localized text cannot intercept input" % button.name)


func _test_confirm_exit() -> void:
	await _fresh()
	current_scene = sandbox
	_spawn(&"flour", 0.5)
	_click(sandbox.exit_run_button)
	var confirm := _modal_button("Confirm")
	var point := confirm.get_global_rect().get_center()
	_touch(51, true, point)
	_check(confirm.visual_pressed and paused, "Confirm receives native touch feedback while paused")
	_touch(51, false, point)
	await process_frame
	await process_frame
	_check(not paused and is_instance_valid(current_scene)
		and current_scene.scene_file_path == "res://scenes/menu/main_menu.tscn"
		and not is_instance_valid(sandbox),
		"Confirm unpauses and returns to Main Menu, freeing gameplay without quitting the app")
	if is_instance_valid(current_scene):
		current_scene.queue_free()
		await process_frame


func _run() -> void:
	await _test_push_input()
	await _test_cancel_and_multitouch()
	await _test_restart_hold()
	await _test_pause_and_resume()
	await _test_pending_merge_pause()
	await _test_portraits()
	await _test_localization_and_art_alignment()
	await _test_confirm_exit()
	paused = false
	print("KITCHEN CONTROLS: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
