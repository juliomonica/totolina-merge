extends Control

const MAIN_MENU_SCENE_PATH := "res://scenes/menu/main_menu.tscn"
const KITCHEN_CONTENT := preload("res://config/worlds/kitchen/kitchen_content.tres")
const DISCOVERY_SAVE_PATH := "user://recipe_discoveries.cfg"
const DISCOVERY_SAVE_SECTION := "recipes"
const DISCOVERY_SAVE_FORMAT_KEY := "format_version"
const DISCOVERY_SAVE_CONTENT_KEY := "content_id"
const DISCOVERY_SAVE_IDS_KEY := "discovered_creation_ids"
const CONTENT_MARGIN := 24.0

@export var locked_silhouette_material: ShaderMaterial

@onready var safe_area: MarginContainer = $SafeArea
@onready var recipe_scroll: ScrollContainer = $SafeArea/CollectionColumn/RecipeScroll
@onready var recipe_grid: GridContainer = $SafeArea/CollectionColumn/RecipeScroll/RecipeGrid
@onready var back_button: Button = $SafeArea/CollectionColumn/Back

var discovered_creation_ids: Array[StringName] = []
var _discovery_save_path := DISCOVERY_SAVE_PATH
var _scroll_touch_index := -1
var _scroll_touch_y := 0.0


func _ready() -> void:
	_load_recipe_discoveries()
	_populate_collection()
	back_button.pressed.connect(_return_to_main_menu)
	get_viewport().size_changed.connect(_layout_safe_area)
	_layout_safe_area()
	back_button.grab_focus()


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.pressed:
			if (
				_scroll_touch_index < 0
				and recipe_scroll.get_global_rect().has_point(touch.position)
				and _collection_can_scroll()
			):
				_scroll_touch_index = touch.index
				_scroll_touch_y = touch.position.y
				get_viewport().set_input_as_handled()
		elif touch.index == _scroll_touch_index:
			_scroll_touch_index = -1
			get_viewport().set_input_as_handled()
	elif event is InputEventScreenDrag:
		var drag := event as InputEventScreenDrag
		if drag.index != _scroll_touch_index:
			return
		var vertical_delta := drag.position.y - _scroll_touch_y
		_scroll_touch_y = drag.position.y
		recipe_scroll.scroll_vertical -= roundi(vertical_delta)
		get_viewport().set_input_as_handled()


func _collection_can_scroll() -> bool:
	var scroll_bar := recipe_scroll.get_v_scroll_bar()
	return scroll_bar.max_value > scroll_bar.page


func _load_recipe_discoveries() -> void:
	discovered_creation_ids.clear()
	var save_file := ConfigFile.new()
	var load_error := save_file.load(_discovery_save_path)
	if load_error == ERR_FILE_NOT_FOUND:
		return
	if load_error != OK:
		push_warning("Could not load recipe discoveries: error %d" % load_error)
		return

	var stored_format_version := int(save_file.get_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_FORMAT_KEY,
		0
	))
	var stored_content_id := StringName(str(save_file.get_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_CONTENT_KEY,
		""
	)))
	if (
		stored_format_version != KITCHEN_CONTENT.content_version
		or stored_content_id != KITCHEN_CONTENT.content_id
	):
		return
	var stored_ids: Variant = save_file.get_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_IDS_KEY,
		PackedStringArray()
	)
	if not (stored_ids is Array or stored_ids is PackedStringArray):
		return
	for stored_id_value in stored_ids:
		var stored_id := StringName(str(stored_id_value))
		if (
			KITCHEN_CONTENT.creation_for_id(stored_id) != null
			and not discovered_creation_ids.has(stored_id)
		):
			discovered_creation_ids.append(stored_id)


func _populate_collection() -> void:
	for child in recipe_grid.get_children():
		child.queue_free()
	for definition in KITCHEN_CONTENT.collection_creations():
		recipe_grid.add_child(_create_recipe_card(definition))


func _create_recipe_card(
	definition: CreationDefinition
) -> PanelContainer:
	var discovered := discovered_creation_ids.has(definition.id)
	var card := PanelContainer.new()
	card.name = "Creation_%s" % definition.id
	card.custom_minimum_size = Vector2(210.0, 174.0)
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.clip_contents = true
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.set_meta("creation_id", definition.id)
	card.set_meta("discovered", discovered)
	card.add_theme_stylebox_override("panel", _card_style(discovered))

	var margin := MarginContainer.new()
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_right", 10)
	margin.add_theme_constant_override("margin_bottom", 8)
	card.add_child(margin)

	var content := VBoxContainer.new()
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_theme_constant_override("separation", 4)
	margin.add_child(content)

	var artwork_center := CenterContainer.new()
	artwork_center.custom_minimum_size = Vector2(0.0, 108.0)
	artwork_center.size_flags_vertical = Control.SIZE_EXPAND_FILL
	artwork_center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_child(artwork_center)

	var artwork := TextureRect.new()
	artwork.name = "Artwork"
	artwork.custom_minimum_size = Vector2(104.0, 104.0)
	artwork.mouse_filter = Control.MOUSE_FILTER_IGNORE
	artwork.texture = definition.texture
	artwork.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	artwork.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	if not discovered:
		artwork.material = locked_silhouette_material
	artwork_center.add_child(artwork)

	var recipe_name := Label.new()
	recipe_name.name = "RecipeName"
	recipe_name.custom_minimum_size = Vector2(0.0, 50.0)
	recipe_name.text = (
		tr(String(definition.display_name_key))
		if discovered
		else tr("COLLECTION_UNKNOWN")
	)
	recipe_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	recipe_name.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	recipe_name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	recipe_name.mouse_filter = Control.MOUSE_FILTER_IGNORE
	recipe_name.add_theme_color_override(
		"font_color",
		Color("fff1d0") if discovered else Color("b8aabd")
	)
	recipe_name.add_theme_color_override("font_outline_color", Color("3d1f40"))
	recipe_name.add_theme_constant_override("outline_size", 3)
	recipe_name.add_theme_font_size_override("font_size", 14)
	content.add_child(recipe_name)
	return card


func _card_style(discovered: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = (
		Color(0.25, 0.08, 0.28, 0.94)
		if discovered
		else Color(0.10, 0.07, 0.13, 0.92)
	)
	style.border_color = (
		Color(1.0, 0.82, 0.40, 0.88)
		if discovered
		else Color(0.42, 0.35, 0.46, 0.82)
	)
	style.set_border_width_all(2)
	style.set_corner_radius_all(18)
	return style


func _layout_safe_area() -> void:
	var safe_insets := Vector4.ZERO
	var viewport_size := get_viewport_rect().size
	var window_size := Vector2(DisplayServer.window_get_size())
	var display_safe_area := DisplayServer.get_display_safe_area()
	if (
		window_size.x > 0.0
		and window_size.y > 0.0
		and display_safe_area.size.x > 0
		and display_safe_area.size.y > 0
	):
		var viewport_scale := viewport_size / window_size
		safe_insets = Vector4(
			display_safe_area.position.x * viewport_scale.x,
			display_safe_area.position.y * viewport_scale.y,
			maxf(0.0, window_size.x - display_safe_area.end.x) * viewport_scale.x,
			maxf(0.0, window_size.y - display_safe_area.end.y) * viewport_scale.y
		)

	safe_area.add_theme_constant_override(
		"margin_left",
		ceili(safe_insets.x + CONTENT_MARGIN)
	)
	safe_area.add_theme_constant_override(
		"margin_top",
		ceili(safe_insets.y + CONTENT_MARGIN)
	)
	safe_area.add_theme_constant_override(
		"margin_right",
		ceili(safe_insets.z + CONTENT_MARGIN)
	)
	safe_area.add_theme_constant_override(
		"margin_bottom",
		ceili(safe_insets.w + CONTENT_MARGIN)
	)


func _return_to_main_menu() -> void:
	back_button.disabled = true
	var change_error := get_tree().change_scene_to_file(MAIN_MENU_SCENE_PATH)
	if change_error != OK:
		back_button.disabled = false
		push_error("Could not return to main menu: error %d" % change_error)
