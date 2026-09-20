extends "res://tests/kitchen_recipe_validation.gd"

# Synthetic events go through Viewport input -> GUI -> unhandled input, not
# direct calls to the drop method. This is not a physical iPhone test.
func _point() -> Vector2:
	return sandbox._chamber_rect.get_center()


func _touch(index: int, pressed: bool, position: Vector2, canceled := false, device := 0) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.pressed = pressed
	event.canceled = canceled
	event.position = position
	event.device = device
	root.push_input(event, true)


func _drag(index: int, position: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = position
	event.relative = Vector2(10, 0)
	root.push_input(event, true)


func _mouse(pressed: bool, position: Vector2, device := 0, button := MOUSE_BUTTON_LEFT) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = button
	event.pressed = pressed
	event.position = position
	event.global_position = position
	event.device = device
	root.push_input(event, true)


func _reproduce() -> void:
	await _reset()
	for index in [7, 3, 9, 2]:
		_touch(index, true, _point())
	print("MULTITOUCH REPRODUCTION: four presses produced %d drops" % sandbox._piece_sequence)
	_check(sandbox._piece_sequence == 1, "four simultaneous fingers produce only one drop")


func _test_touch_ownership() -> void:
	for count in [1, 2, 4]:
		await _reset()
		var position := _point()
		for index in range(7, 7 + count):
			_touch(index, true, position + Vector2((index - 7) * 20, 0))
		_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == 7,
			"%d fingers: first valid nonzero index owns exactly one press-committed drop" % count)
		var piece: PrototypePiece = sandbox.pieces.get_child(0)
		var initial_position := piece.position
		var current_id: StringName = sandbox._current_creation_id
		var next_id: StringName = sandbox._raw_next_creation_id
		for step in range(10):
			for index in range(7, 7 + count):
				_drag(index, position + Vector2(step * 8, 0))
		_touch(7, true, position) # Defensive duplicate begin, not a new gesture.
		_check(sandbox._piece_sequence == 1 and piece.position == initial_position
			and sandbox._current_creation_id == current_id and sandbox._raw_next_creation_id == next_id,
			"drag/repeated begin never drop, re-aim a committed body, or advance previews")
		_touch(8, false, position)
		_check(sandbox._active_drop_touch_index == 7, "secondary release does not end primary")
		_touch(11, true, position)
		_touch(7, false, position)
		_check(sandbox._active_drop_touch_index == -1, "primary release clears ownership")
		_drag(11, position)
		_touch(11, true, position) # Already held: no promotion even on duplicate begin.
		_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == -1,
			"already-held secondary cannot be handed ownership")
		_touch(11, false, position)
		_touch(11, true, position)
		_check(sandbox._piece_sequence == 2 and sandbox._active_drop_touch_index == 11,
			"release and NEW press starts the next drop")
		_touch(11, false, position, true)
		_check(sandbox._active_drop_touch_index == -1, "cancellation clears active finger without another drop")
		_touch(15, true, position, true)
		_check(sandbox._piece_sequence == 2, "canceled begin cannot commit a drop")


func _test_mouse_and_emulation() -> void:
	await _reset()
	var position := _point()
	_mouse(true, position, InputEvent.DEVICE_ID_EMULATION)
	_touch(4, true, position)
	_mouse(true, position, InputEvent.DEVICE_ID_EMULATION)
	_mouse(false, position, InputEvent.DEVICE_ID_EMULATION)
	_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == 4,
		"emulated mouse copies before/after real touch cannot double-drop or cancel")
	_touch(4, false, position)
	_mouse(true, position, InputEvent.DEVICE_ID_EMULATION)
	_check(sandbox._piece_sequence == 1, "late emulated mouse copy also ignored")
	_mouse(true, position)
	_mouse(false, position)
	_touch(0, true, position, false, InputEvent.DEVICE_ID_EMULATION)
	_touch(0, false, position, false, InputEvent.DEVICE_ID_EMULATION)
	_check(sandbox._piece_sequence == 2 and sandbox._active_drop_touch_index == -1,
		"physical mouse remains one click/one drop; synthetic touch copy ignored")
	_mouse(true, position, 0, MOUSE_BUTTON_RIGHT)
	_mouse(true, position, 0, MOUSE_BUTTON_WHEEL_UP)
	_check(sandbox._piece_sequence == 2, "other mouse buttons retain no-drop behavior")
	_touch(0, true, position)
	_touch(0, false, position, false, InputEvent.DEVICE_ID_EMULATION)
	_check(sandbox._active_drop_touch_index == 0, "synthetic touch release cannot cancel a real finger with the same index")


func _test_engine_emulation() -> void:
	# Unlike the tagged-copy tests above, Input generates the counterpart events
	# itself here. Only runtime test settings change; project.godot stays untouched.
	var previous_mouse := Input.emulate_mouse_from_touch
	var previous_touch := Input.emulate_touch_from_mouse
	var previous_accumulation := Input.use_accumulated_input
	Input.use_accumulated_input = false
	Input.emulate_mouse_from_touch = true
	Input.emulate_touch_from_mouse = false
	await _reset()
	for index in range(4):
		var event := InputEventScreenTouch.new()
		event.window_id = root.get_window_id()
		event.position = _point()
		event.index = index
		event.pressed = true
		Input.parse_input_event(event)
	Input.flush_buffered_events()
	await process_frame
	_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == 0,
		"actual engine mouse-from-touch emulation: four fingers still one drop")
	for index in range(4):
		var event := InputEventScreenTouch.new()
		event.window_id = root.get_window_id()
		event.position = _point()
		event.index = index
		Input.parse_input_event(event)
	Input.flush_buffered_events()
	await process_frame
	_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == -1,
		"engine-generated release copies cannot create more drops")
	Input.emulate_mouse_from_touch = false
	Input.emulate_touch_from_mouse = true
	await _reset()
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.window_id = root.get_window_id()
		event.button_index = MOUSE_BUTTON_LEFT
		event.position = _point()
		event.global_position = event.position
		event.pressed = pressed
		Input.parse_input_event(event)
	Input.flush_buffered_events()
	await process_frame
	_check(sandbox._piece_sequence == 1 and sandbox._active_drop_touch_index == -1,
		"actual engine touch-from-mouse emulation: one physical click still one drop")
	Input.emulate_mouse_from_touch = previous_mouse
	Input.emulate_touch_from_mouse = previous_touch
	Input.use_accumulated_input = previous_accumulation


func _test_gui_and_cleanup() -> void:
	await _reset()
	var position := _point()
	# Make an existing HUD Control explicitly consume its touch events in this
	# fixture, proving cleanup is not dependent on reaching unhandled input.
	sandbox.hud_panel.gui_input.connect(func(event: InputEvent):
		if event is InputEventScreenTouch:
			sandbox.hud_panel.accept_event()
	)
	var hud_position: Vector2 = sandbox.hud_panel.get_global_rect().get_center()
	_touch(1, true, hud_position)
	_check(sandbox._active_drop_touch_index == -1 and sandbox._piece_sequence == 0,
		"GUI-handled touch never claims gameplay ownership")
	_touch(1, false, hud_position)
	_touch(5, true, position)
	_touch(5, false, hud_position)
	_check(sandbox._active_drop_touch_index == -1, "primary release over consuming HUD still clears ownership")
	_touch(6, true, position)
	sandbox.pulse_charge = 100
	sandbox._update_debug_ui()
	var push_position: Vector2 = sandbox.pulse_right_button.get_global_rect().get_center()
	_mouse(true, push_position, InputEvent.DEVICE_ID_EMULATION)
	_mouse(false, push_position, InputEvent.DEVICE_ID_EMULATION)
	_check(sandbox.pulse_charge == 0 and sandbox._piece_sequence == 2
		and sandbox._active_drop_touch_index == 6,
		"GUI Push still accepts emulated mouse while a gameplay finger is held")
	var restart_position: Vector2 = sandbox.restart_button.get_global_rect().get_center()
	_mouse(true, restart_position)
	_check(sandbox._restart_hold_active, "GUI Restart still begins hold while gameplay finger held")
	_mouse(false, restart_position)
	_check(not sandbox._restart_hold_active and sandbox._piece_sequence == 2, "short GUI hold cancels without drop/reset")
	sandbox._restart_sandbox()
	_check(sandbox._active_drop_touch_index == -1 and sandbox._held_drop_touch_indices.is_empty(),
		"restart clears all gameplay touch state")
	await process_frame
	var before: int = sandbox._piece_sequence
	_drag(6, position)
	_check(sandbox._piece_sequence == before, "held finger cannot re-drop after restart via drag")
	_touch(20, true, position)
	_check(sandbox._piece_sequence == before + 1, "new press works after restart")
	sandbox._enter_game_over()
	_check(sandbox._active_drop_touch_index == -1, "game over clears ownership")
	_touch(21, true, position)
	_check(sandbox._active_drop_touch_index == -1 and sandbox._piece_sequence == before + 1,
		"game over cannot claim/drop")
	sandbox.play_again_button.pressed.emit()
	_check(sandbox._active_drop_touch_index == -1 and sandbox._held_drop_touch_indices.is_empty(),
		"Play Again clears touch state")
	await process_frame
	_touch(25, true, position)
	sandbox.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	_check(sandbox._active_drop_touch_index == -1, "application focus loss clears ownership")
	_touch(27, true, position)
	sandbox.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
	_check(sandbox._active_drop_touch_index == -1, "application pause clears ownership")
	_touch(30, true, position)
	root.remove_child(sandbox)
	_check(sandbox._active_drop_touch_index == -1 and sandbox._held_drop_touch_indices.is_empty(),
		"scene exit clears touch state")
	sandbox.free()


func _run() -> void:
	if OS.get_cmdline_user_args().has("--reproduce"):
		await _reproduce()
	else:
		await _test_touch_ownership()
		await _test_mouse_and_emulation()
		await _test_engine_emulation()
		await _test_gui_and_cleanup()
		await _reset()
		await _test_navigation()
	print("TOUCH INPUT: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
