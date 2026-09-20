extends PanelContainer

# Runtime-only developer UI; never present in the saved gameplay scene.
signal spawn_requested(creation_id: StringName, count: int)
signal clear_requested
signal layout_requested

var content: WorldContentConfiguration
var selector: OptionButton
var spawn_one: Button
var spawn_pair: Button
var clear_board: Button
var toggle: Button
var body: VBoxContainer
var status: Label


func _ready() -> void:
	if not OS.is_debug_build():
		hide()
		queue_free()
		return
	name = "DebugSpawnPanel"
	mouse_filter = Control.MOUSE_FILTER_STOP
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.07, 0.12, 0.96)
	style.set_border_width_all(1)
	style.border_color = Color("b9a8ce")
	style.set_corner_radius_all(8)
	style.content_margin_left = 6
	style.content_margin_right = 6
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	add_theme_stylebox_override("panel", style)
	add_theme_font_size_override("font_size", 14)
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(column)
	toggle = Button.new()
	toggle.text = "Debug spawn +"
	toggle.toggle_mode = true
	toggle.custom_minimum_size.y = 36
	column.add_child(toggle)
	body = VBoxContainer.new()
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.visible = false
	column.add_child(body)
	selector = OptionButton.new()
	selector.custom_minimum_size.y = 40
	selector.fit_to_longest_item = false
	for definition in content.collection_creations():
		selector.add_item(tr(String(definition.display_name_key)))
		selector.set_item_metadata(selector.item_count - 1, definition.id)
	body.add_child(selector)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(row)
	spawn_one = _button("Spawn One", row)
	spawn_pair = _button("Spawn Pair", row)
	clear_board = _button("Clear Board", row)
	status = Label.new()
	status.text = "Debug spawns; physical merges earn rewards."
	status.add_theme_font_size_override("font_size", 12)
	status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(status)
	spawn_one.pressed.connect(_request_spawn.bind(1))
	spawn_pair.pressed.connect(_request_spawn.bind(2))
	clear_board.pressed.connect(func(): clear_requested.emit())
	toggle.toggled.connect(func(open: bool):
		body.visible = open
		toggle.text = "Debug spawn -" if open else "Debug spawn +"
		reset_size()
		layout_requested.emit()
	)


func _button(text: String, parent: Control) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 40
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(button)
	return button


func _request_spawn(count: int) -> void:
	if OS.is_debug_build() and selector.selected >= 0:
		spawn_requested.emit(StringName(selector.get_item_metadata(selector.selected)), count)


func place(hud_rect: Rect2) -> void:
	size = Vector2(minf(328.0 if body.visible else 148.0, hud_rect.end.x - 16.0), 0)
	position = Vector2(hud_rect.end.x - size.x, hud_rect.end.y + 6.0)


func set_run_active(active: bool) -> void:
	spawn_one.disabled = not active
	spawn_pair.disabled = not active


func show_space_warning(blocked: bool) -> void:
	status.text = "No safe space. Clear Board first." if blocked else "Debug spawns; physical merges earn rewards."


func spawn_positions(bounds: Rect2, radius: float, count: int, pieces: Array) -> Array[Vector2]:
	# Debug-only bounded placement, not another gameplay placement system.
	# Keep a 0.1px contact overlap for a pair, never identical transforms.
	var offsets: Array[Vector2] = [Vector2.ZERO]
	if count == 2:
		var half_distance := radius - 0.05
		var offset := Vector2(half_distance, 0)
		if bounds.size.x < radius * 4.0:
			# Very large pieces cannot fit side by side: a slightly diagonal stack.
			offset.x = minf(radius * 0.25, maxf(0.0, bounds.size.x * 0.5 - radius))
			offset.y = sqrt(maxf(0.0, half_distance * half_distance - offset.x * offset.x))
		offsets = [-offset, offset]
	var inset := Vector2.ONE * radius + offsets[0].abs()
	var centers := Rect2(bounds.position + inset, bounds.size - inset * 2.0)
	if centers.size.x < 0.0 or centers.size.y < 0.0:
		return []
	var step := maxf(8.0, radius * 0.5)
	for row in range(ceili(centers.size.y / step) + 1):
		var y := minf(centers.end.y, centers.position.y + row * step)
		for column in range(ceili(centers.size.x / step) + 2):
			var side := -1.0 if column % 2 == 1 else 1.0
			var x := clampf(centers.get_center().x + ceilf(column * 0.5) * step * side,
				centers.position.x, centers.end.x)
			var candidates: Array[Vector2] = []
			var safe := true
			for offset in offsets:
				var point := Vector2(x, y) + offset
				candidates.append(point)
				for piece in pieces:
					if is_instance_valid(piece) and not piece.is_queued_for_deletion():
						if point.distance_to(piece.global_position) < radius + piece.radius + 0.5:
							safe = false
			if safe:
				return candidates
	return []
