extends ScrollContainer
## Godot 4.7's native mouse/pan scrolling is retained. With this project's
## touch-to-mouse emulation disabled, indexed touch drives the same scrollbars.
## No custom inertia, global input injection, snapping or gameplay touch owner.
var _finger := -1
var _last := Vector2.ZERO
var _remainder := Vector2.ZERO


func _gui_input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed and _finger == -1:
			_finger = event.index
			_last = event.position
			_remainder = Vector2.ZERO
		elif not event.pressed and event.index == _finger:
			_finger = -1
		accept_event()
	elif event is InputEventScreenDrag:
		if event.index == _finger:
			_remainder += _last - event.position
			_last = event.position
			var movement := Vector2i(_remainder)
			_remainder -= Vector2(movement)
			if horizontal_scroll_mode != SCROLL_MODE_DISABLED:
				scroll_horizontal += movement.x
			if vertical_scroll_mode != SCROLL_MODE_DISABLED:
				scroll_vertical += movement.y
		accept_event()


func _notification(what: int) -> void:
	if what == NOTIFICATION_VISIBILITY_CHANGED or what == NOTIFICATION_WM_WINDOW_FOCUS_OUT:
		_finger = -1
