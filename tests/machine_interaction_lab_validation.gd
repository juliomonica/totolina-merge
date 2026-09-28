extends SceneTree
## Native presentation-only checks. No gameplay scenes, physics or save writes.
const LAB = preload("res://scenes/debug/machine_interaction_lab.tscn")
var lab: Control
var checks := 0
var failures := 0
var contacts := 0
var contact_x := 0.0
var output := ""
var phone: SubViewport
var authored_nozzle_transform: Transform2D


func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--lab-output="):
			output = argument.trim_prefix("--lab-output=")
	call_deferred("_run")


func _check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error("MACHINE LAB CHECK: " + message)


func _nodes(node: Node) -> Array[Node]:
	var result: Array[Node] = [node]
	for child in node.get_children():
		result.append_array(_nodes(child))
	return result


func _contact(x: float) -> void:
	contacts += 1
	contact_x = x


func _reset_ok() -> bool:
	var m: Node2D = lab.machine
	return not m.busy and not m.player.is_playing() and not m.cat.idle_player.is_playing() \
		and not m.cat.idle_enabled and is_zero_approx(m.cat.arm_pose) and is_zero_approx(m.cat.blink_pose) \
		and m.cat.expression_weights == Vector2.ZERO and m.cat.visual.position == Vector2.ZERO \
		and m.button_pose == 0.0 and m.shutter_pose == 0.0 and m.nozzle.transform == authored_nozzle_transform \
		and m.falling_item.modulate.a == 0.0 and m.incoming_item.modulate.a == 0.0 \
		and m.current_item.position == m._current_base.origin and m.next_item.position == m._next_base.origin \
		and m.current_item.modulate.a == 1.0 and m.next_item.modulate.a == 1.0 and lab.sample_index == 0


func _test_actions() -> void:
	var m: Node2D = lab.machine
	m.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var count := _nodes(lab).size()
	var unique: Dictionary = {}
	for texture in m.textures + m.cat.textures + lab.sample_textures:
		_check(texture != null and texture.get_size().x > 0, "texture loads")
		unique[texture.resource_path] = true
	_check(unique.size() == 40, "all 37 current presentation assets plus three sample creation textures load")
	var arm_files := ["cat_totolina_arm_idle.png", "cat_totolina_arm_press_01.png",
		"cat_totolina_arm_press_02.png", "cat_totolina_arm_press_03.png"]
	var loaded_arms: Array[String] = []
	for arm in m.cat.arms:
		loaded_arms.append(arm.texture.resource_path.get_file())
		_check(arm.scale == Vector2.ONE * 1.10, "all arm poses share one uniform scale")
	_check(loaded_arms == arm_files, "only the four locked arm images are instantiated")
	_test_press_sequence()
	for node in _nodes(lab):
		_check(not node is CollisionObject2D and not node is CollisionShape2D
			and not node is CollisionPolygon2D and not node is Timer, "presentation-only tree")
	for mode in m.ACTIONS:
		for repeat in range(12):
			lab.stop_button.pressed.emit()
			_check(_reset_ok(), "complete reset before replay")
			lab.action_buttons[mode].pressed.emit()
			_check(m.busy and m.player.is_playing(), "action starts: " + String(mode))
			m.player.advance(0.075)
			_check(not m.play_action(&"full_drop"), "busy action rejects another full cycle")
			if repeat % 2 == 0:
				lab.stop_button.pressed.emit()
				m.player.advance(1.0)
				_check(_reset_ok(), "interrupted action has no late track/callback")
			else:
				m.player.advance(1.0)
				_check(not m.busy, "action completes")
			_check(_nodes(lab).size() == count and get_processed_tweens().is_empty(), "constant nodes/no Tweens")
	for x in [72.0, 250.0, 428.0]:
		lab.stop_reset()
		lab.target.value = x
		contacts = 0
		lab.play(&"full_drop")
		m.player.advance(0.075)
		_check(is_equal_approx(m.cat.arm_pose, 1.0) and is_equal_approx(m.button_pose, 0.25)
			and contacts == 0, "full-drop arm/button first poses remain at 0.075s before contact")
		m.player.advance(0.115)
		_check(contacts == 0 and is_equal_approx(m.nozzle.position.x, x), "nozzle arrives before contact")
		m.player.advance(0.02)
		_check(contacts == 1 and is_equal_approx(contact_x, x), "exactly one contact at chosen X")
		_check(is_equal_approx(m.cat.arm_pose, 3.0) and is_equal_approx(m.button_pose, 2.0)
			and is_equal_approx(m.shutter_pose, 5.0), "paw fully down, red button down, shutter open at drop")
		m.player.advance(0.16)
		_check(m.current_item.modulate.a == 0.0 and m.next_item.position.y > m._next_base.origin.y
			and m.falling_item.modulate.a > 0.9, "current exits, next descends, cosmetic drop is visible")
		m.player.advance(0.4)
		_check(contacts == 1 and lab.sample_index == 1
			and m.current_item.texture == lab.sample_textures[1]
			and m.next_item.texture == lab.sample_textures[2], "one sample-only feeder advance, correct final slots")
		m.player.advance(0.1)
		m.player.advance(0.1)
		_check(lab.sample_index == 1 and contacts == 1, "advancing a finished clip cannot repeat its handoff")
	# A long render frame must report this cycle's destination, not stale X.
	lab.stop_reset()

	lab.target.value = 428.0
	contacts = 0
	lab.play(&"full_drop")
	lab.target.value = 72.0
	m.player.advance(0.21)
	_check(contacts == 1 and is_equal_approx(contact_x, 428.0)
		and is_equal_approx(m.nozzle.position.x, 428.0), "contact is correct after long frame and target change")
	for rate in [0.25, 1.0, 2.0]:
		lab.stop_reset()
		lab.speed.value = rate
		lab.play(&"full_drop")
		m.player.advance(0.05)
		_check(is_equal_approx(m.player.current_animation_position, 0.05 * rate), "native complete-sequence speed")
		lab.speed.value = 0.5
		m.player.advance(0.02)
		_check(is_equal_approx(m.player.current_animation_position, 0.05 * rate + 0.01), "mid-sequence rate preserves phase")
		lab.stop_reset()
	lab.speed.value = 1.0
	# Native looping is deliberately a lab restart with a short scaled rest.
	lab.loop_toggle.button_pressed = true
	lab.play(&"full_drop")
	for cycle in range(20):
		m.player.advance(0.70)
		lab._process(0.36)
		_check(m.busy and _nodes(lab).size() == count, "repeat loop restarts only after completion")
	lab.stop_reset()
	lab._process(2.0)
	_check(_reset_ok(), "stop also cancels pending loop restart")
	lab.loop_toggle.button_pressed = false
	m.cat.set_idle(true)
	for repetition in range(12):
		_check(m.cat.blink_wait >= 2.5 and m.cat.blink_wait <= 5.0, "private idle delay stays in range")
		m.cat.idle_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		m.cat.blink_wait = 0.0
		m.cat._process(0.01)
		m.cat.idle_player.advance(0.12)
		_check(is_equal_approx(m.cat.blink_pose, 2.0), "blink reaches closed pose")
		m.cat.idle_player.advance(0.2)
		_check(is_zero_approx(m.cat.blink_pose), "blink returns to normal")
	_check(m.player.animation_finished.get_connections().size() == 1, "one completion connection")
	lab.stop_reset()
	m.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	m.cat.idle_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	lab.play(&"full_drop")
	await create_timer(0.8).timeout
	_check(not m.busy and lab.sample_index == 1, "real-time full sequence completes")
	lab.stop_reset()


func _test_press_sequence() -> void:
	lab.stop_reset()
	contacts = 0
	lab.play(&"press")
	var previous := 0.0
	# Standalone press eases the arm to pose 1 at 0.10s; the button keeps its
	# 0.075s key. Both still reach full contact at 0.20s and finish at 0.44s.
	for pose in [[0.0, 0.0, 0.0], [0.04, null, 0.0], [0.075, null, 0.25],
		[0.10, 1.0, null], [0.135, 2.0, 1.0],
		[0.20, 3.0, 2.0], [0.235, 3.0, 2.0], [0.305, 2.0, 1.0],
		[0.37, 1.0, 0.25], [0.44, 0.0, 0.0]]:
		lab.machine.player.advance(pose[0] - previous)
		if pose[1] != null:
			_check(is_equal_approx(lab.machine.cat.arm_pose, pose[1]), "standalone press arm key pose at %.3fs" % pose[0])
		if pose[2] != null:
			_check(is_equal_approx(lab.machine.button_pose, pose[2]), "standalone press button key pose at %.3fs" % pose[0])
		_check(contacts == (0 if pose[0] < 0.20 else 1), "contact fires once at the fully pressed pose")
		previous = pose[0]
	lab.machine.player.advance(0.01)
	_check(not lab.machine.busy, "four-image press completes in 0.44s")
	lab.stop_reset()


func _mouse(point: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = point
	event.global_position = point
	root.push_input(event, true)


func _test_preview_input() -> void:
	lab.stop_reset()
	lab.machine.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	var point: Vector2 = lab.machine.to_global(Vector2(110, 355))
	_mouse(point, true)
	_mouse(point, false)
	_check(lab.machine.busy and lab.machine.action == &"full_drop"
		and is_equal_approx(lab.target.value, 110.0), "viewport-routed mouse selects X and starts full sequence")
	var other: Vector2 = lab.machine.to_global(Vector2(400, 355))
	_mouse(other, true)
	_mouse(other, false)
	_check(is_equal_approx(lab.target.value, 110.0), "busy preview ignores extra clicks")
	# Real Control hit testing for Stop, independent of signal-emission checks.
	lab.controls_toggle.pressed.emit()
	await process_frame
	var stop_point: Vector2 = lab.stop_button.get_global_rect().get_center()
	_mouse(stop_point, true)
	_mouse(stop_point, false)
	_check(_reset_ok(), "viewport-routed Stop button cancels current cycle")
	lab.controls_toggle.pressed.emit()
	await process_frame
	for pressed in [true, false]:
		var touch := InputEventScreenTouch.new()
		touch.index = 0
		touch.pressed = pressed
		touch.position = other
		root.push_input(touch, true)
	_check(lab.machine.busy and is_equal_approx(lab.target.value, 400.0),
		"viewport-routed touch chooses X and simulates drop")
	lab.stop_reset()
	lab.target.value = 72.0
	lab.play(&"nozzle")
	lab.machine.player.advance(0.2)
	_check(is_equal_approx(lab.machine.nozzle.position.x, 72.0), "nozzle holds completed destination")
	lab.target.value = 428.0
	lab.play(&"nozzle")
	_check(is_equal_approx(lab.machine.move_seconds, 0.18), "longest nozzle travel takes 0.18s")
	lab.machine.player.advance(0.2)
	lab.play(&"nozzle")
	_check(is_equal_approx(lab.machine.move_seconds, 0.08), "same-target preview uses minimum 0.08s")
	lab.stop_reset()

func _capture(filename: String) -> void:
	if output.is_empty():
		return
	await RenderingServer.frame_post_draw
	_check(phone.get_texture().get_image().save_png(output.path_join(filename + ".png")) == OK,
		"capture " + filename)


func _portraits() -> void:
	if DisplayServer.get_name() == "headless":
		return
	if not output.is_empty():
		DirAccess.make_dir_recursive_absolute(output)
	phone = SubViewport.new()
	phone.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	phone.size_2d_override_stretch = true
	root.add_child(phone)
	lab.reparent(phone)
	for dimensions in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
		phone.size = dimensions
		phone.size_2d_override = Vector2i(540, roundi(dimensions.y * 540.0 / dimensions.x))
		await create_timer(0.1).timeout
		await RenderingServer.frame_post_draw
		_check(phone.get_texture().get_size() == Vector2(dimensions), "exact phone pixel size")
		var view: Rect2 = lab.get_viewport_rect()
		lab.set_controls_visible(true)
		await process_frame
		for control in lab.action_buttons.values() + [lab.stop_button, lab.speed, lab.target, lab.idle_toggle]:
			_check(view.encloses(control.get_global_rect()), "controls fit phone")
		lab.set_controls_visible(false)
		lab.controls_toggle.hide() # Clean composition captures; drawer input is tested above.
		var machine_rect := Rect2(lab.machine.position, lab.machine.preview_size * lab.machine.scale)
		_check(machine_rect.position.is_equal_approx(Vector2.ZERO)
			and machine_rect.size.is_equal_approx(lab.preview.size), "machine composition fills phone bounds")
		var rear: NinePatchRect = lab.machine.get_node("machine_chamber_background")
		var foreground: NinePatchRect = lab.machine.get_node("machine_foreground_frame")
		_check(foreground.scale.x == foreground.scale.y and foreground.size == rear.size and foreground.scale == rear.scale,
			"matching rear/front mapping uses one uniform decorative scale")
		var collection: Control = lab.machine.get_node("StaticCollectionPreview/Viewport")
		_check(collection.clip_contents and lab.machine.collection_track.get_child_count() == 9,
			"nine visual collection positions remain clipped to a subset")
		lab.stop_reset()
		await _capture("%dx%d_idle" % [dimensions.x, dimensions.y])
		lab.machine.cat.blink_pose = 2.0
		await _capture("%dx%d_blink_closed" % [dimensions.x, dimensions.y])
		lab.machine.cat.blink_pose = 0.0
		lab.machine.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		for mode in [&"full_drop", &"excited", &"surprised"]:
			lab.stop_reset()
			lab.target.value = 428.0
			lab.play(mode)
			lab.machine.player.advance(0.21)
			await _capture("%dx%d_%s" % [dimensions.x, dimensions.y, mode])
			if mode == &"full_drop":
				lab.machine.player.advance(0.04)
				await _capture("%dx%d_release" % [dimensions.x, dimensions.y])
				lab.machine.player.advance(0.03)
				await _capture("%dx%d_feeder_exit" % [dimensions.x, dimensions.y])
		lab.stop_reset()
		lab.play(&"press")
		var previous_time := 0.0
		for pose_time in [0.075, 0.135, 0.20, 0.37]:
			lab.machine.player.advance(pose_time - previous_time)
			await _capture("%dx%d_press_%03dms" % [dimensions.x, dimensions.y, roundi(pose_time * 1000)])
			previous_time = pose_time
		if dimensions == Vector2i(405, 720):
			for mode in [&"full_drop", &"excited", &"press"]:
				lab.stop_reset()
				lab.target.value = 72.0
				lab.play(mode)
				for frame in range(40):
					await _capture("sequence_%s_%02d" % [mode, frame])
					lab.machine.player.advance(1.0 / 60.0)
			lab.stop_reset()
			for fraction in [0.0, 0.5, 1.0]:
				lab.collection_offset.value = fraction
				await _capture("405x720_collection_%03d" % roundi(fraction * 100))
			lab.collection_offset.value = 0.0
			lab.set_controls_visible(true)
			await _capture("405x720_controls")
			lab.set_controls_visible(false)
			lab.set_preview_safe_insets(Vector4(0, 32, 0, 24))
			_check(is_equal_approx(lab.machine.position.y, 32.0)
				and is_equal_approx(lab.machine.position.y + lab.machine.preview_size.y * lab.machine.scale.y, lab.preview.size.y - 24.0),
				"explicit safe-area preview protects top and bottom content")
			await _capture("405x720_safe_area")
			lab.set_preview_safe_insets(Vector4.ZERO)
	lab.reparent(root)
	phone.queue_free()
	await process_frame


func _run() -> void:
	# Read the authored rest before _ready()/reset() can alter an instance.
	var authored_machine := preload("res://scenes/presentation/machine_drop_presentation.tscn").instantiate()
	authored_nozzle_transform = authored_machine.get_node("TopMachine/Nozzle").transform
	authored_machine.free()
	lab = LAB.instantiate()
	root.add_child(lab)
	await process_frame
	await process_frame
	lab.machine.contact_reached.connect(_contact)
	await _test_actions()
	await _test_preview_input()
	await _portraits()
	for mode in [&"full_drop", &"excited", &"shutter"]:
		lab.stop_reset()
		lab.play(mode)
		lab.machine.player.advance(0.1)
		lab.queue_free()
		await process_frame
		await process_frame
		_check(not is_instance_valid(lab), "teardown during active presentation")
		lab = LAB.instantiate()
		root.add_child(lab)
		await process_frame
	lab.queue_free()
	await process_frame
	await create_timer(0.75).timeout
	_check(get_processed_tweens().is_empty(), "no orphaned Tweens")
	print("MACHINE INTERACTION LAB: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
