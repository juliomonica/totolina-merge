extends Control
## Development-only review controls. No production navigation or state access.
const MACHINE = preload("res://scripts/presentation/machine_drop_presentation.gd")
const SAMPLE_FILES := ["wheat.png", "flour.png", "cake_mix.png"]

var machine: Node2D
var preview: Control
var controls_panel: PanelContainer
var controls_toggle: Button
var collection_offset: HSlider
var preview_safe_insets := Vector4.ZERO
var status: Label
var speed: HSlider
var speed_label: Label
var target: HSlider
var target_label: Label
var loop_toggle: CheckButton
var idle_toggle: CheckButton
var action_buttons: Dictionary = {}
var stop_button: Button
var last_action: StringName = &""
var loop_wait := -1.0
var contact_count := 0
var _contact_text := ""
var sample_textures: Array[Texture2D] = []
var sample_index := 0


func _ready() -> void:
	set_process(false)
	if not OS.is_debug_build():
		hide()
		queue_free()
		return
	_build_ui()
	machine = preload("res://scenes/presentation/machine_drop_presentation.tscn").instantiate()
	machine.name = "MachinePresentation"
	preview.add_child(machine)
	for file in SAMPLE_FILES:
		sample_textures.append(load("res://assets/worlds/kitchen/ingredients/" + file) as Texture2D)
	_set_sample_items()
	machine.set_score_preview("00128")
	preview.resized.connect(_layout)
	preview.gui_input.connect(_preview_input)
	machine.contact_reached.connect(_contact)
	machine.finished.connect(_finished)
	_layout()
	_set_target(target.value)
	status.text = "Idle · NEXT above CURRENT · fixed sample items"
	if not machine.assets_ok:
		status.text = "Asset load failed. See Godot Output."
		for button in action_buttons.values():
			button.disabled = true


func _build_ui() -> void:
	var background := ColorRect.new()
	background.color = Color("101922")
	background.z_index = -20 # Behind both environment layers, including their negative Z.
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)
	preview = Control.new()
	preview.name = "Preview"
	preview.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	preview.clip_contents = true
	add_child(preview)
	controls_panel = PanelContainer.new()
	controls_panel.name = "LabControls"
	controls_panel.z_index = 100
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = Color("14232d")
	panel_style.set_corner_radius_all(10)
	controls_panel.add_theme_stylebox_override("panel", panel_style)
	controls_panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	controls_panel.offset_left = 12
	controls_panel.offset_right = -12
	controls_panel.offset_top = -440
	controls_panel.offset_bottom = -60
	controls_panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	add_child(controls_panel)
	var margin := MarginContainer.new()
	for side in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	controls_panel.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	margin.add_child(column)
	_label("MACHINE LAB / PREVIEW ONLY", 17, column).modulate = Color("9dc7bf")
	status = _label("Idle", 17, column)
	status.custom_minimum_size.y = 24
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 6)
	column.add_child(grid)
	var modes := [&"full_drop", &"press", &"shutter", &"nozzle", &"feeder", &"excited", &"surprised", &"blink"]
	var labels := ["Full drop", "Cat + button", "Shutter", "Nozzle move", "Feeder", "Excited", "Surprised", "Blink / Idle"]
	for index in range(modes.size()):
		var button := _button(labels[index], grid)
		button.pressed.connect(play.bind(modes[index]))
		action_buttons[modes[index]] = button
	stop_button = _button("Stop / Reset", grid)
	stop_button.pressed.connect(stop_reset)
	var target_row := HBoxContainer.new()
	column.add_child(target_row)
	target_label = _label("Target X: 350", 17, target_row)
	target_label.custom_minimum_size.x = 137
	target = _slider(72, 428, 1, 350, target_row)
	target.value_changed.connect(_set_target)
	var collection_row := HBoxContainer.new()
	column.add_child(collection_row)
	_label("Collection preview", 17, collection_row).custom_minimum_size.x = 164
	collection_offset = _slider(0, 1, 0.01, 0, collection_row)
	collection_offset.value_changed.connect(func(value: float): machine.set_collection_preview_offset(value))
	var playback_row := HBoxContainer.new()
	column.add_child(playback_row)
	speed_label = _label("1.00×", 17, playback_row)
	speed_label.custom_minimum_size.x = 58
	speed = _slider(0.25, 2.0, 0.05, 1.0, playback_row)
	speed.value_changed.connect(_set_speed)
	loop_toggle = CheckButton.new()
	loop_toggle.text = "Loop"
	loop_toggle.add_theme_font_size_override("font_size", 17)
	playback_row.add_child(loop_toggle)
	loop_toggle.toggled.connect(_set_loop)
	idle_toggle = CheckButton.new()
	idle_toggle.text = "Idle"
	idle_toggle.button_pressed = true
	idle_toggle.add_theme_font_size_override("font_size", 17)
	playback_row.add_child(idle_toggle)
	idle_toggle.toggled.connect(_set_idle)
	_label("Tap chamber: choose X + simulate one drop. No physics.", 15, column).modulate = Color("9db3bf")
	controls_toggle = _button("Lab controls", self)
	controls_toggle.z_index = 101
	controls_toggle.pressed.connect(func(): set_controls_visible(not controls_panel.visible))
	set_controls_visible(false)


func _label(text: String, font_size: int, parent: Node) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	parent.add_child(label)
	return label


func _button(text: String, parent: Node) -> Button:
	var button := Button.new()
	button.text = text
	button.add_theme_font_size_override("font_size", 17)
	button.custom_minimum_size.y = 40
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(button)
	return button


func _slider(low: float, high: float, step_size: float, initial: float, parent: Node) -> HSlider:
	var slider := HSlider.new()
	slider.min_value = low
	slider.max_value = high
	slider.step = step_size
	slider.value = initial
	slider.custom_minimum_size = Vector2(70, 36)
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	parent.add_child(slider)
	return slider


func _layout() -> void:
	# Full-bleed at zero insets; explicit logical insets can preview a future notch/home area.
	var usable := preview.size - Vector2(preview_safe_insets.x + preview_safe_insets.z,
		preview_safe_insets.y + preview_safe_insets.w)
	var factor := usable.x / MACHINE.SIZE.x
	machine.scale = Vector2.ONE * factor
	machine.position = Vector2(preview_safe_insets.x, preview_safe_insets.y)
	machine.layout_preview(Vector2(MACHINE.SIZE.x, usable.y / factor))
	controls_toggle.position = Vector2(preview.size.x - 156, preview.size.y - 170 * factor - preview_safe_insets.w)
	controls_toggle.size = Vector2(144, 40)


func set_controls_visible(enabled: bool) -> void:
	controls_panel.visible = enabled
	controls_toggle.text = "Hide controls" if enabled else "Lab controls"


func set_preview_safe_insets(insets: Vector4) -> void:
	preview_safe_insets = insets
	_layout()


func play(mode: StringName) -> void:
	if not OS.is_debug_build() or machine.busy:
		return
	loop_wait = -1.0
	if mode == &"blink":
		idle_toggle.button_pressed = true
		machine.cat.set_idle(true)
		machine.cat.blink_wait = 0.0
		status.text = "Blink · then calm idle at 2.5–5s intervals"
		return
	if machine.play_action(mode):
		last_action = mode
		_contact_text = ""
		_lock_buttons(true)
		set_process(true)


func stop_reset() -> void:
	loop_wait = -1.0
	last_action = &""
	machine.reset()
	sample_index = 0
	_set_sample_items()
	collection_offset.value = 0.0
	idle_toggle.set_pressed_no_signal(false)
	machine.idle_enabled = false
	contact_count = 0
	_contact_text = ""
	_lock_buttons(false)
	set_process(false)
	status.text = "Reset · Wheat CURRENT / Flour NEXT · idle paused"


func _contact(x: float) -> void:
	if machine.action == &"full_drop":
		contact_count += 1
		_contact_text = "DROP MOMENT #%d · X %.0f" % [contact_count, x]
	else:
		_contact_text = "PAW / BUTTON CONTACT · 0.20s"


func _finished(mode: StringName) -> void:
	if mode in [&"full_drop", &"feeder"]:
		sample_index = (sample_index + 1) % SAMPLE_FILES.size()
		_set_sample_items()
	_lock_buttons(false)
	status.text = "Finished · " + String(mode).replace("_", " ")
	if not _contact_text.is_empty():
		status.text += " · " + _contact_text
	loop_wait = 0.35 if loop_toggle.button_pressed else -1.0
	set_process(loop_wait >= 0.0)


func _set_sample_items() -> void:
	if not machine.set_items(sample_textures[sample_index], sample_textures[(sample_index + 1) % 3],
		sample_textures[(sample_index + 2) % 3]):
		machine.assets_ok = false


func _lock_buttons(locked: bool) -> void:
	for button in action_buttons.values():
		button.disabled = locked


func _process(delta: float) -> void:
	if machine.busy:
		status.text = "%s · %.2fs" % [String(machine.action).replace("_", " "), machine.player.current_animation_position]
		if not _contact_text.is_empty():
			status.text = _contact_text
	elif loop_wait >= 0.0:
		loop_wait -= delta * speed.value
		if loop_wait <= 0.0:
			play(last_action)


func _set_speed(value: float) -> void:
	machine.set_playback_speed(value)
	speed_label.text = "%.2f×" % value


func _set_target(value: float) -> void:
	machine.set_target(value)
	target_label.text = "Target X: %.0f" % value


func _set_idle(enabled: bool) -> void:
	machine.idle_enabled = enabled
	if not machine.busy:
		machine.cat.set_idle(enabled)


func _set_loop(enabled: bool) -> void:
	if not enabled:
		loop_wait = -1.0
	elif not machine.busy and not last_action.is_empty():
		loop_wait = 0.35
	set_process(machine.busy or loop_wait >= 0.0)


func _preview_input(event: InputEvent) -> void:
	if machine.busy:
		return
	var point := Vector2.ZERO
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed \
		and event.device != InputEvent.DEVICE_ID_EMULATION:
		point = event.position
	elif event is InputEventScreenTouch and event.pressed and not event.canceled \
		and event.device != InputEvent.DEVICE_ID_EMULATION:
		point = event.position
	else:
		return
	point = (point - machine.position) / machine.scale
	if Rect2(42, 315, 416, 93).has_point(point):
		target.value = point.x
		play(&"full_drop")
		preview.accept_event()


func _exit_tree() -> void:
	set_process(false)
	if is_instance_valid(machine):
		machine.reset()
