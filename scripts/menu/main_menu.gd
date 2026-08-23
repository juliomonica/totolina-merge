extends Control

const GAMEPLAY_SCENE_PATH := "res://scenes/prototype/physics_sandbox.tscn"
const RECIPE_COLLECTION_SCENE_PATH := "res://scenes/menu/recipe_collection.tscn"
const CONTENT_MARGIN := 24.0

@onready var safe_area: MarginContainer = $SafeArea
@onready var start_button: Button = $SafeArea/MenuColumn/ActionsPanel/ActionsMargin/Actions/Start
@onready var recipes_button: Button = $SafeArea/MenuColumn/ActionsPanel/ActionsMargin/Actions/Recipes


func _ready() -> void:
	start_button.pressed.connect(_start_game)
	recipes_button.pressed.connect(_open_recipes)
	get_viewport().size_changed.connect(_layout_safe_area)
	_layout_safe_area()
	start_button.grab_focus()


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


func _start_game() -> void:
	start_button.disabled = true
	var change_error := get_tree().change_scene_to_file(GAMEPLAY_SCENE_PATH)
	if change_error != OK:
		start_button.disabled = false
		push_error("Could not open gameplay scene: error %d" % change_error)


func _open_recipes() -> void:
	recipes_button.disabled = true
	var change_error := get_tree().change_scene_to_file(
		RECIPE_COLLECTION_SCENE_PATH
	)
	if change_error != OK:
		recipes_button.disabled = false
		push_error("Could not open recipe collection: error %d" % change_error)
