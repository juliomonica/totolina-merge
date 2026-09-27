extends Button
## Native mouse/keyboard Button plus indexed touch (project mouse emulation is off).
## Art children never intercept GUI events. No gameplay or pause authority here.

@export var normal_art: Texture2D
@export var pressed_art: Texture2D
@export var normal_label: Texture2D
@export var pressed_label: Texture2D
@export var localized_label_key: StringName
var visual_pressed := false
var _touch_index := -1


func _ready() -> void:
	button_down.connect(_show_pressed.bind(true))
	button_up.connect(_show_pressed.bind(false))
	_show_pressed(false)
	_update_localized_label()


func _show_pressed(value: bool) -> void:
	visual_pressed = value
	$Base.texture = pressed_art if value and pressed_art != null else normal_art
	$LabelArt.texture = pressed_label if value and pressed_label != null else normal_label
	queue_redraw()


func _update_localized_label() -> void:
	var label := get_node_or_null("LocalizedLabel") as Label
	if label == null:
		return
	label.visible = not TranslationServer.get_locale().begins_with("en")
	label.text = tr(String(localized_label_key))
	$LabelArt.visible = not label.visible


func _draw() -> void:
	# Availability is still controlled by the existing Push charge/game-over rules.
	var tint := Color(0.6, 0.6, 0.6, 1.0) if disabled else Color.WHITE
	$Base.modulate = tint
	$LabelArt.modulate = tint


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		accept_event()
		if event.pressed and not event.canceled and not disabled and _touch_index == -1:
			_touch_index = event.index
			button_down.emit()
	elif event is InputEventScreenDrag:
		accept_event()


func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and visual_pressed and _touch_index == -1:
		if event.button_mask & MOUSE_BUTTON_MASK_LEFT and not get_global_rect().has_point(event.position):
			cancel_press()
			get_viewport().set_input_as_handled()
	if _touch_index == -1:
		return
	# Endings can arrive outside the original Control or over another UI node.
	if event is InputEventScreenTouch and event.index == _touch_index and (not event.pressed or event.canceled):
		var activate: bool = not event.canceled and not disabled and get_global_rect().has_point(event.position)
		cancel_press()
		get_viewport().set_input_as_handled()
		if activate:
			pressed.emit()
	elif event is InputEventScreenDrag and event.index == _touch_index:
		if not get_global_rect().has_point(event.position):
			cancel_press()
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.device == InputEvent.DEVICE_ID_EMULATION:
		get_viewport().set_input_as_handled()


func cancel_press() -> void:
	_touch_index = -1
	# For a non-toggle BaseButton, set_pressed_no_signal does not clear the
	# native mouse press attempt. Disabling does, preventing a late release from
	# activating a canceled control after Resume/focus loss/full Restart.
	var was_disabled := disabled
	disabled = true
	disabled = was_disabled
	if visual_pressed:
		button_up.emit()
	_show_pressed(false)


func _notification(what: int) -> void:
	if is_node_ready() and what == NOTIFICATION_TRANSLATION_CHANGED:
		_update_localized_label()
	if is_node_ready() and what in [NOTIFICATION_APPLICATION_FOCUS_OUT, NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_PAUSED]:
		cancel_press()
