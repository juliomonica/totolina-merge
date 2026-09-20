extends SceneTree
## Standalone lab checks; never instantiates gameplay or accesses user saves.
## Run with --script res://tests/merge_effect_lab_validation.gd.
## Optional graphical captures: -- --lab-output=/absolute/temporary/directory

const LAB := preload("res://scenes/debug/merge_effect_lab.tscn")
var lab: Control
var checks := 0
var failures := 0
var output_directory := ""
var capture_viewport: SubViewport


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--lab-output="):
			output_directory = argument.trim_prefix("--lab-output=")
	call_deferred("_run")


func _check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error("LAB CHECK FAILED: " + message)


func _idle() -> bool:
	if lab.player.is_playing() or lab.is_processing() or lab.scrub.value != 0.0:
		return false
	for layer in lab.layers:
		if layer.visible:
			return false
	for sprite in lab.poses:
		if sprite.modulate.a != 0.0 or sprite.position != Vector2.ZERO \
			or sprite.rotation != 0.0 or not sprite.visible \
			or not sprite.scale.is_equal_approx(Vector2.ONE * lab.canvas_pixels / 512.0):
			return false
	return true


func _all_nodes(node: Node) -> Array[Node]:
	var result: Array[Node] = [node]
	for child in node.get_children():
		result.append_array(_all_nodes(child))
	return result


func _test_playback() -> void:
	var initial_nodes := _all_nodes(lab).size()
	var initial_tweens := get_processed_tweens().size()
	_check(lab.poses.size() == 13, "all thirteen sprites created once")
	for sprite in lab.poses:
		_check(sprite.texture != null and sprite.texture.get_size() == Vector2(512, 512),
			"texture imports: " + str(sprite.texture.resource_path))
		var source: Image = sprite.texture.get_image()
		_check(source.get_pixel(0, 0).a == 0 and source.detect_alpha() != Image.ALPHA_NONE,
			"import retains alpha: " + str(sprite.texture.resource_path))
	for node in _all_nodes(lab):
		_check(not node is CollisionObject2D and not node is CollisionShape2D
			and not node is CollisionPolygon2D and not node is Timer,
			"presentation-only node: " + str(node.name))
	lab.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	for effect in range(3):
		lab.selector.item_selected.emit(effect)
		_check(_idle(), "switch clears all previous presentation")
		for repeat in range(25):
			lab.play_button.pressed.emit()
			lab.player.advance(0.035)
			_check(lab.player.is_playing() and lab.layers[effect].visible,
				"replay starts selected animation")
			lab.play_button.pressed.emit()
			_check(is_zero_approx(lab.player.current_animation_position), "replay restarts at time zero")
			lab.player.advance(0.24)
			lab.stop_button.pressed.emit()
			_check(_idle(), "stop resets every presentation channel")
		for playback_speed in [0.25, 1.0, 2.0]:
			lab.speed.value = playback_speed
			lab.replay()
			lab.player.advance(0.04)
			_check(is_equal_approx(lab.player.current_animation_position, 0.04 * playback_speed),
				"one native clock scales all tracks")
			lab.speed.value = 0.5
			lab.player.advance(0.02)
			_check(is_equal_approx(lab.player.current_animation_position, 0.04 * playback_speed + 0.01),
				"speed change during playback preserves current phase")
			lab.player.advance(2.0)
			_check(_idle(), "natural completion returns to clean idle")
		lab.speed.value = 2.0
		lab.loop_toggle.button_pressed = true
		lab.replay()
		for frame in range(600):
			lab.player.advance(1.0 / 60.0)
		_check(lab.player.is_playing() and lab.player.current_animation_position < lab._duration(effect),
			"native loop survives 20 timeline seconds at 2×")
		_check(_all_nodes(lab).size() == initial_nodes and get_processed_tweens().size() == initial_tweens,
			"loop/replay never adds nodes or Tweens")
		lab.loop_toggle.button_pressed = false
		lab.player.advance(1.0)
		_check(_idle(), "disabling loop finishes the current cycle")
		lab.inspect_time(0.28)
		_check(not lab.player.is_playing() and not lab.is_processing() and lab.layers[effect].visible,
			"scrubbing freezes a deterministic visible pose without processing")
		lab.select_effect((effect + 1) % 3)
		_check(_idle(), "switch after inspection clears old pose")
	_check(lab.player.animation_finished.get_connections().size() == 1,
		"completion callback connected only once")
	lab.speed.value = 1.0
	lab.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	lab.select_effect(0)
	lab.replay()
	await create_timer(0.75).timeout
	_check(_idle(), "real-time playback completes without manual advance")


func _bounds_fit() -> bool:
	var area: Rect2 = lab.preview.get_global_rect().grow(-2.0)
	for sprite in lab.poses:
		if not sprite.is_visible_in_tree() or sprite.modulate.a < 0.01:
			continue
		# Entire source canvas fits, a stricter check than nontransparent pixels.
		var rect: Rect2 = sprite.get_rect()
		for corner in [rect.position, Vector2(rect.end.x, rect.position.y), rect.end,
			Vector2(rect.position.x, rect.end.y)]:
			if not area.has_point(sprite.to_global(corner)):
				return false
	return true


func _capture(filename: String) -> void:
	if output_directory.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var image := capture_viewport.get_texture().get_image()
	_check(image.save_png(output_directory.path_join(filename + ".png")) == OK, "save capture " + filename)


func _portraits() -> void:
	if DisplayServer.get_name() == "headless":
		return
	if not output_directory.is_empty():
		DirAccess.make_dir_recursive_absolute(output_directory)
	# macOS may clamp a native 960px-tall window to the desktop's usable area.
	# Render exact phone pixels offscreen with equivalent canvas-items scaling.
	capture_viewport = SubViewport.new()
	capture_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	capture_viewport.size_2d_override_stretch = true
	root.add_child(capture_viewport)
	lab.reparent(capture_viewport)
	for dimensions in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		capture_viewport.size = dimensions
		capture_viewport.size_2d_override = Vector2i(540, roundi(dimensions.y * 540.0 / dimensions.x))
		await create_timer(0.1).timeout
		await RenderingServer.frame_post_draw
		_check(capture_viewport.get_texture().get_size() == Vector2(dimensions), "exact requested render size")
		var viewport: Rect2 = lab.get_viewport_rect()
		for control in [lab.selector, lab.background, lab.play_button, lab.stop_button, lab.speed,
			lab.loop_toggle, lab.scrub, lab.get_node("Margin/Column/Hint")]:
			_check(viewport.encloses(control.get_global_rect()), "mobile control fits: " + str(control.name))
		for effect in range(3):
			lab.select_effect(effect)
			for frame in range(41):
				lab.inspect_time(lab._duration(effect) * frame / 40.0)
				_check(_bounds_fit(), "all poses fit preview at every sampled time")
			for backdrop in range(3):
				lab.background.select(backdrop)
				lab.preview.queue_redraw()
				lab.inspect_time([0.40, 0.48, 0.47][effect])
				await _capture("%dx%d_%s_bg%d" % [dimensions.x, dimensions.y, lab.EFFECT_NAMES[effect], backdrop])
			if dimensions == Vector2i(405, 720) and not output_directory.is_empty():
				lab.background.select(0)
				lab.preview.queue_redraw()
				for frame in range(41):
					lab.inspect_time(lab._duration(effect) * frame / 40.0)
					await _capture("sequence_%s_%02d" % [lab.EFFECT_NAMES[effect], frame])
	lab.reparent(root)
	capture_viewport.queue_free()
	await process_frame


func _run() -> void:
	lab = LAB.instantiate()
	root.add_child(lab)
	await process_frame
	await process_frame
	_check(_idle(), "opens directly in idle")
	await _test_playback()
	await _portraits()
	for effect in range(3):
		lab.select_effect(effect)
		lab.loop_toggle.button_pressed = true
		lab.replay()
		lab.player.advance(0.15)
		lab.queue_free()
		await process_frame
		await process_frame
		_check(not is_instance_valid(lab), "teardown during active loop frees lab")
		lab = LAB.instantiate()
		root.add_child(lab)
		await process_frame
		_check(_idle(), "fresh scene has no stale playback")
	lab.queue_free()
	await process_frame
	await create_timer(0.75).timeout
	_check(get_processed_tweens().is_empty(), "no surviving Tweens after teardown")
	print("MERGE EFFECT LAB: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
