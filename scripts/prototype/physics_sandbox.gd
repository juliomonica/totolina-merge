extends Node2D

const PIECE_SCENE := preload("res://scenes/prototype/piece.tscn")
const GAMEPLAY_CONFIG := preload("res://scripts/config/gameplay_configuration.gd")
const KITCHEN_CONTENT := preload("res://config/worlds/kitchen/kitchen_content.tres")
const MACHINE_PRESENTATION := preload("res://scripts/presentation/kitchen_machine_presentation.gd")
const MACHINE_TIMELINE := preload("res://scripts/presentation/machine_drop_presentation.gd")
const INITIAL_SEED := 12345
const MAX_PULSE_CHARGE := 100
const PULSE_CHARGE_PER_MERGE := 12
const PULSE_BASE_IMPULSE := 300.0
const PULSE_SEPARATION_RADIUS_RATIO := 0.32
const PULSE_SEPARATION_BASE_IMPULSE := 36.0
const PULSE_SEPARATION_MAX_IMPULSE := 24.0
const PULSE_SEPARATION_DOWNWARD_SCALE := 0.20
const PULSE_FEEDBACK_SECONDS := 0.65
const MAX_MERGE_FEEDBACK_SECONDS := 1.0
const DISCOVERY_FEEDBACK_SECONDS := 1.25
const DISCOVERY_SAVE_PATH := "user://recipe_discoveries.cfg"
const DISCOVERY_SAVE_SECTION := "recipes"
const DISCOVERY_SAVE_FORMAT_KEY := "format_version"
const DISCOVERY_SAVE_CONTENT_KEY := "content_id"
const DISCOVERY_SAVE_IDS_KEY := "discovered_creation_ids"
const MERGE_PLACEMENT_CLEARANCE := 0.5
const MERGE_PLACEMENT_SEARCH_RINGS := 16
const MERGE_PLACEMENT_SEARCH_DIRECTIONS := 16
const MERGE_EXPANSION_RADIUS_MULTIPLIER := 2.0
const MERGE_EXPANSION_BASE_IMPULSE := 40.0
const MERGE_EXPANSION_MAX_IMPULSE := 32.0
const MERGE_EXPANSION_DOWNWARD_SCALE := 0.25
const MERGE_RESOLUTION_COOLDOWN_SECONDS := 0.45
const RESTART_HOLD_SECONDS := 1.0

@export var recipe_locked_silhouette_material: ShaderMaterial

@onready var pieces: Node2D = $Pieces
@onready var left_wall: StaticBody2D = $Chamber/LeftWall
@onready var right_wall: StaticBody2D = $Chamber/RightWall
@onready var floor: StaticBody2D = $Chamber/Floor
@onready var tolina_visual: TextureRect = $DebugUI/Tolina
@onready var hud_panel: PanelContainer = $DebugUI/HUDPanel
@onready var next_preview: Panel = $DebugUI/HUDPanel/Margin/Row/Next/PreviewCenter/Preview
@onready var next_preview_ingredient: TextureRect = $DebugUI/HUDPanel/Margin/Row/Next/PreviewCenter/Preview/Ingredient
@onready var score_label: Label = $DebugUI/HUDPanel/Margin/Row/Information/Stats/Score
@onready var pulse_label: Label = $DebugUI/HUDPanel/Margin/Row/Information/Stats/Pulse
@onready var upcoming_preview: TextureRect = $DebugUI/HUDPanel/Margin/Row/Information/Upcoming/Ingredient
@onready var recipe_progress_panel: PanelContainer = $DebugUI/RecipeProgressPanel
@onready var recipe_progress_row: HBoxContainer = $DebugUI/RecipeProgressPanel/Margin/Row
@onready var gameplay_controls: Control = $DebugUI/GameplayControls
@onready var controls_panel: Control = $DebugUI/GameplayControls/SafeBounds/BottomControls
@onready var pulse_left_button: Button = $DebugUI/GameplayControls/SafeBounds/BottomControls/PushLeft
@onready var restart_button: Button = $DebugUI/GameplayControls/SafeBounds/BottomControls/Restart
@onready var pulse_right_button: Button = $DebugUI/GameplayControls/SafeBounds/BottomControls/PushRight
@onready var restart_hold_progress: TextureProgressBar = $DebugUI/GameplayControls/SafeBounds/BottomControls/Restart/HoldProgress
@onready var exit_run_button: Button = $DebugUI/GameplayControls/SafeBounds/ExitRun
@onready var exit_run_modal: Control = $DebugUI/GameplayControls/ExitRunModal
@onready var pulse_feedback_label: Label = $DebugUI/PulseFeedback
@onready var max_merge_feedback_label: Label = $DebugUI/MaxMergeFeedback
@onready var new_creation_feedback_label: Label = $DebugUI/NewCreationFeedback
@onready var danger_label: Label = $DebugUI/Danger
@onready var result_overlay: Control = $DebugUI/ResultOverlay
@onready var result_safe_margin: MarginContainer = $DebugUI/ResultOverlay/SafeMargin
@onready var result_tolina: TextureRect = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/Showcase/Tolina
@onready var result_creation: TextureRect = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/Showcase/Creation
@onready var result_highest_heading: Label = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/HighestHeading
@onready var result_creation_name: Label = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/CreationName
@onready var result_new_recipe: Label = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/NewRecipe
@onready var play_again_button: Button = $DebugUI/ResultOverlay/SafeMargin/Center/Panel/ResultMargin/Content/PlayAgain
@onready var presentation: PrototypeSandboxPresentation = $Presentation

var _rng := RandomNumberGenerator.new()
# Ephemeral progression, independent of permanent creation discoveries.
var _spawn_stage_index := 0
# The large preview is the controlled DROP; the small preview is buffered NEXT.
var _current_creation_id: StringName
var _raw_next_creation_id: StringName
var _piece_sequence := 0
var _recipe_evaluation_pending := false
var _physical_contacts: Dictionary = {}
var _resolving_merge_pair: Array = []
var _merge_generation := 0
var _chamber_rect := Rect2()
var _wall_thickness := 0.0
var _danger_threshold_y := 0.0
var _next_preview_style := StyleBoxFlat.new()
var _pulse_feedback_timer := 0.0
var _max_merge_feedback_timer := 0.0
var _discovery_feedback_timer := 0.0
var _merge_cooldown_remaining := 0.0
var _merge_resolution_pending := false
var _queued_merge_pairs: Array = []
var _new_discoveries_this_run: Array[StringName] = []
var _discovery_save_path := DISCOVERY_SAVE_PATH
var _recipe_progress_slots: Array[PanelContainer] = []
var _restart_hold_active := false
var _restart_hold_elapsed := 0.0
# Ownership lasts until this finger ends; press accepts one timed machine cycle.
var _active_drop_touch_index := -1
var _held_drop_touch_indices: Dictionary = {}
var _debug_spawn_panel: Control
var machine_presentation: Node2D
var _drop_cycle_active := false
var _drop_cycle_elapsed := 0.0
var _drop_released := false
var _drop_target_x := 0.0
var _drop_creation_id: StringName
var _exit_run_paused := false

var danger_active := false
var danger_timer := 0.0
var game_over := false
var pulse_charge := 0
var score := 0
var highest_creation_id: StringName
var discovered_creation_ids: Array[StringName] = []


func _ready() -> void:
	Engine.physics_ticks_per_second = 60
	_apply_presentation_configuration()
	_load_recipe_discoveries()
	for error in KITCHEN_CONTENT.spawn_stage_errors():
		push_error("World spawning: " + error)
	_spawn_stage_index = 0
	_rng.seed = INITIAL_SEED
	_current_creation_id = _roll_spawn_creation_id()
	_raw_next_creation_id = _roll_spawn_creation_id()
	machine_presentation = $KitchenMachine
	# Retain legacy resources/nodes for the separate, later cleanup audit.
	$KitchenBowl.hide()
	tolina_visual.hide()
	hud_panel.hide()
	$BackgroundCanvas/KitchenBackground.texture = load(MACHINE_TIMELINE.ENV + "background.png")
	pieces.z_index = 1
	next_preview.add_theme_stylebox_override("panel", _next_preview_style)
	_build_recipe_progress_strip()
	machine_presentation.decorate_collection(recipe_progress_panel, recipe_progress_row)
	_reset_restart_hold_feedback()
	restart_button.button_down.connect(_begin_restart_hold)
	restart_button.button_up.connect(_cancel_restart_hold)
	play_again_button.pressed.connect(_restart_sandbox)
	pulse_left_button.pressed.connect(_activate_pulse.bind(Vector2.LEFT))
	pulse_right_button.pressed.connect(_activate_pulse.bind(Vector2.RIGHT))
	exit_run_button.pressed.connect(_open_exit_run)
	exit_run_modal.get_node("SafeBounds/Panel/Resume").pressed.connect(_resume_run)
	exit_run_modal.get_node("SafeBounds/Panel/Confirm").pressed.connect(_confirm_exit_run)
	get_viewport().size_changed.connect(_layout_chamber)
	_layout_chamber()
	_create_debug_spawn_panel()
	_update_debug_ui()
	_request_recipe_evaluation()


func _process(delta: float) -> void:
	if _exit_run_paused:
		return
	if _restart_hold_active:
		_restart_hold_elapsed = minf(
			RESTART_HOLD_SECONDS,
			_restart_hold_elapsed + delta
		)
		restart_hold_progress.value = (
			_restart_hold_elapsed / RESTART_HOLD_SECONDS * 100.0
		)
		if _restart_hold_elapsed >= RESTART_HOLD_SECONDS:
			_restart_sandbox()
	if _pulse_feedback_timer > 0.0:
		_pulse_feedback_timer = maxf(0.0, _pulse_feedback_timer - delta)
		pulse_feedback_label.visible = _pulse_feedback_timer > 0.0
	if _max_merge_feedback_timer > 0.0:
		_max_merge_feedback_timer = maxf(0.0, _max_merge_feedback_timer - delta)
		max_merge_feedback_label.visible = _max_merge_feedback_timer > 0.0
	if _discovery_feedback_timer > 0.0:
		_discovery_feedback_timer = maxf(0.0, _discovery_feedback_timer - delta)
		new_creation_feedback_label.visible = _discovery_feedback_timer > 0.0
	_update_debug_ui()


func _physics_process(delta: float) -> void:
	if game_over or _exit_run_paused:
		return
	_advance_machine_drop(delta)

	if _merge_cooldown_remaining > 0.0:
		_merge_cooldown_remaining = maxf(0.0, _merge_cooldown_remaining - delta)
		if is_zero_approx(_merge_cooldown_remaining):
			_try_resolve_next_merge()

	if _has_dangerous_piece():
		if not danger_active:
			danger_active = true
			danger_timer = 0.0
			queue_redraw()
		danger_timer += delta
		if danger_timer >= GAMEPLAY_CONFIG.DANGER_GRACE_SECONDS:
			_enter_game_over()
	elif danger_active:
		danger_active = false
		danger_timer = 0.0
		queue_redraw()


func _input(event: InputEvent) -> void:
	if _exit_run_paused:
		return
	if event is InputEventScreenTouch:
		# Observe endings BEFORE GUI routing: a finger may finish over a button.
		# Do not consume here; Controls keep their ordinary touch behavior.
		if event.device != InputEvent.DEVICE_ID_EMULATION and (not event.pressed or event.canceled):
			_held_drop_touch_indices.erase(event.index)
			if event.index == _active_drop_touch_index:
				_active_drop_touch_index = -1
		return
	if not event is InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return
	if key_event.keycode == KEY_LEFT:
		_activate_pulse(Vector2.LEFT)
		get_viewport().set_input_as_handled()
	elif key_event.keycode == KEY_RIGHT:
		_activate_pulse(Vector2.RIGHT)
		get_viewport().set_input_as_handled()


func _unhandled_input(event: InputEvent) -> void:
	if _exit_run_paused:
		return
	if event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.device == InputEvent.DEVICE_ID_EMULATION:
			return # A real desktop mouse click owns its own drop, not its touch copy.
		if touch.pressed and not touch.canceled:
			if not _held_drop_touch_indices.has(touch.index):
				_held_drop_touch_indices[touch.index] = true
				if _active_drop_touch_index == -1 and not game_over and not _drop_cycle_active and _is_drop_area(touch.position):
					_active_drop_touch_index = touch.index
					_drop_piece(touch.position.x)
			get_viewport().set_input_as_handled()
	elif event is InputEventScreenDrag:
		# There is no post-press aiming stage in this game. Neither the owner nor
		# ignored fingers may move a committed body, advance NEXT or drop again.
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton:
		var click := event as InputEventMouseButton
		if click.device == InputEvent.DEVICE_ID_EMULATION:
			return # Ignore touchscreen mouse copies only here, AFTER normal GUI input.
		if click.button_index == MOUSE_BUTTON_LEFT and click.pressed and _active_drop_touch_index == -1 and _is_drop_area(click.position):
			_drop_piece(click.position.x)
			get_viewport().set_input_as_handled()


func _clear_drop_touch_state() -> void:
	_active_drop_touch_index = -1
	_held_drop_touch_indices.clear()


func _is_drop_area(point: Vector2) -> bool:
	return _chamber_rect.has_point(point) and point.y >= machine_presentation.release_position(point.x).y


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT or what == NOTIFICATION_APPLICATION_PAUSED:
		_clear_drop_touch_state()
		if is_node_ready():
			_cancel_restart_hold()
			gameplay_controls.clear_press_states()
		if not _exit_run_paused:
			_cancel_machine_drop()


func _draw() -> void:
	if _chamber_rect.size == Vector2.ZERO:
		return

	var danger_line_color: Color = (
		GAMEPLAY_CONFIG.DANGER_LINE_ACTIVE_COLOR
		if danger_active
		else GAMEPLAY_CONFIG.DANGER_LINE_INACTIVE_COLOR
	)
	machine_presentation.show_danger_line(
		_chamber_rect.position.x,
		_chamber_rect.end.x,
		_danger_threshold_y,
		danger_line_color,
		GAMEPLAY_CONFIG.DANGER_LINE_WIDTH
	)


func _apply_presentation_configuration() -> void:
	danger_label.scale = GAMEPLAY_CONFIG.DANGER_LABEL_SCALE
	danger_label.add_theme_font_size_override(
		"font_size",
		GAMEPLAY_CONFIG.DANGER_TEXT_FONT_SIZE
	)
	danger_label.add_theme_color_override(
		"font_color",
		GAMEPLAY_CONFIG.DANGER_TEXT_COLOR
	)
	danger_label.add_theme_color_override(
		"font_outline_color",
		GAMEPLAY_CONFIG.DANGER_TEXT_OUTLINE_COLOR
	)
	danger_label.add_theme_color_override(
		"font_shadow_color",
		GAMEPLAY_CONFIG.DANGER_TEXT_SHADOW_COLOR
	)
	danger_label.add_theme_constant_override(
		"outline_size",
		GAMEPLAY_CONFIG.DANGER_TEXT_OUTLINE_SIZE
	)
	danger_label.add_theme_constant_override(
		"shadow_offset_x",
		roundi(GAMEPLAY_CONFIG.DANGER_TEXT_SHADOW_OFFSET.x)
	)
	danger_label.add_theme_constant_override(
		"shadow_offset_y",
		roundi(GAMEPLAY_CONFIG.DANGER_TEXT_SHADOW_OFFSET.y)
	)
	danger_label.add_theme_constant_override(
		"shadow_outline_size",
		GAMEPLAY_CONFIG.DANGER_TEXT_SHADOW_OUTLINE_SIZE
	)


func _layout_chamber() -> void:
	var viewport_size := get_viewport_rect().size
	if viewport_size.x <= 0.0 or viewport_size.y <= 0.0:
		return
	if _drop_cycle_active:
		_cancel_machine_drop() # Do not deliver to an old viewport's latched target.

	var chamber_height := (
		viewport_size.y * GAMEPLAY_CONFIG.CHAMBER_HEIGHT_VIEWPORT_RATIO
	)
	var chamber_width := minf(
		viewport_size.x * GAMEPLAY_CONFIG.CHAMBER_WIDTH_VIEWPORT_RATIO,
		chamber_height
			* GAMEPLAY_CONFIG.CHAMBER_MAX_WIDTH_TO_HEIGHT_RATIO
	)
	var chamber_size := Vector2(chamber_width, chamber_height)
	_chamber_rect = Rect2(
		Vector2(
			(viewport_size.x - chamber_size.x) * 0.5,
			viewport_size.y * GAMEPLAY_CONFIG.CHAMBER_TOP_VIEWPORT_RATIO
		),
		chamber_size
	)
	_wall_thickness = maxf(
		GAMEPLAY_CONFIG.WALL_THICKNESS_MIN_PIXELS,
		viewport_size.x
			* GAMEPLAY_CONFIG.WALL_THICKNESS_VIEWPORT_WIDTH_RATIO
	)
	_danger_threshold_y = (
		_chamber_rect.position.y
		+ _chamber_rect.size.y
			* GAMEPLAY_CONFIG.DANGER_HEIGHT_CHAMBER_RATIO
	)

	left_wall.position = Vector2(
		_chamber_rect.position.x
			+ _chamber_rect.size.x
				* GAMEPLAY_CONFIG.LEFT_WALL_X_CHAMBER_RATIO,
		_chamber_rect.position.y
			+ _chamber_rect.size.y
				* GAMEPLAY_CONFIG.SIDE_WALL_CENTER_Y_CHAMBER_RATIO
	)
	right_wall.position = Vector2(
		_chamber_rect.position.x
			+ _chamber_rect.size.x
				* GAMEPLAY_CONFIG.RIGHT_WALL_X_CHAMBER_RATIO,
		_chamber_rect.position.y
			+ _chamber_rect.size.y
				* GAMEPLAY_CONFIG.SIDE_WALL_CENTER_Y_CHAMBER_RATIO
	)
	floor.position = Vector2(
		_chamber_rect.position.x
			+ _chamber_rect.size.x
				* GAMEPLAY_CONFIG.FLOOR_CENTER_X_CHAMBER_RATIO,
		_chamber_rect.position.y
			+ _chamber_rect.size.y
				* GAMEPLAY_CONFIG.FLOOR_Y_CHAMBER_RATIO
	)

	var left_shape := left_wall.get_node("CollisionShape2D").shape as RectangleShape2D
	var right_shape := right_wall.get_node("CollisionShape2D").shape as RectangleShape2D
	var floor_shape := floor.get_node("CollisionShape2D").shape as RectangleShape2D
	left_shape.size = Vector2(_wall_thickness, _chamber_rect.size.y + _wall_thickness)
	right_shape.size = left_shape.size
	floor_shape.size = Vector2(_chamber_rect.size.x + _wall_thickness, _wall_thickness)
	danger_label.offset_top = (
		_danger_threshold_y + GAMEPLAY_CONFIG.DANGER_LABEL_TOP_OFFSET
	)
	danger_label.offset_bottom = (
		_danger_threshold_y + GAMEPLAY_CONFIG.DANGER_LABEL_BOTTOM_OFFSET
	)
	_layout_safe_ui(viewport_size)
	presentation.layout(
		_chamber_rect,
		floor.position.y,
		_danger_threshold_y
	)
	_update_next_preview()
	queue_redraw()


func _layout_safe_ui(viewport_size: Vector2) -> void:
	var safe_insets := Vector4.ZERO
	var window_size := Vector2(DisplayServer.window_get_size())
	var safe_area := DisplayServer.get_display_safe_area()
	if (
		window_size.x > 0.0
		and window_size.y > 0.0
		and safe_area.size.x > 0
		and safe_area.size.y > 0
	):
		var viewport_scale := viewport_size / window_size
		safe_insets = Vector4(
			safe_area.position.x * viewport_scale.x,
			safe_area.position.y * viewport_scale.y,
			maxf(0.0, window_size.x - safe_area.end.x) * viewport_scale.x,
			maxf(0.0, window_size.y - safe_area.end.y) * viewport_scale.y
		)

	var tolina_left := (
		safe_insets.x + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	var tolina_top := (
		safe_insets.y + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	tolina_visual.offset_left = tolina_left
	tolina_visual.offset_top = tolina_top
	tolina_visual.offset_right = (
		tolina_left + GAMEPLAY_CONFIG.TOLINA_SAFE_SIZE.x
	)
	tolina_visual.offset_bottom = (
		tolina_top + GAMEPLAY_CONFIG.TOLINA_SAFE_SIZE.y
	)
	hud_panel.offset_left = (
		tolina_visual.offset_right + GAMEPLAY_CONFIG.TOLINA_HUD_GAP_PIXELS
	)
	hud_panel.offset_top = (
		safe_insets.y + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	hud_panel.offset_right = -(
		safe_insets.z + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	hud_panel.offset_bottom = (
		hud_panel.offset_top + GAMEPLAY_CONFIG.HUD_HEIGHT_PIXELS
	)
	gameplay_controls.set_safe_insets(safe_insets)
	recipe_progress_panel.offset_left = (
		safe_insets.x + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	recipe_progress_panel.offset_top = (
		controls_panel.get_global_rect().position.y - viewport_size.y
		- GAMEPLAY_CONFIG.RECIPE_PROGRESS_CONTROLS_GAP_PIXELS
		- MACHINE_PRESENTATION.collection_height(viewport_size.x)
	)
	recipe_progress_panel.offset_right = -(
		safe_insets.z + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS
	)
	recipe_progress_panel.offset_bottom = (
		controls_panel.get_global_rect().position.y - viewport_size.y
		- GAMEPLAY_CONFIG.RECIPE_PROGRESS_CONTROLS_GAP_PIXELS
	)
	gameplay_controls.place_hold_progress(recipe_progress_panel)
	result_safe_margin.add_theme_constant_override(
		"margin_left",
		ceili(safe_insets.x + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS)
	)
	result_safe_margin.add_theme_constant_override(
		"margin_top",
		ceili(safe_insets.y + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS)
	)
	result_safe_margin.add_theme_constant_override(
		"margin_right",
		ceili(safe_insets.z + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS)
	)
	result_safe_margin.add_theme_constant_override(
		"margin_bottom",
		ceili(safe_insets.w + GAMEPLAY_CONFIG.UI_EDGE_MARGIN_PIXELS)
	)
	machine_presentation.layout(_chamber_rect, floor.position.y, _wall_thickness,
		Rect2(Vector2(safe_insets.x + 8.0, safe_insets.y + 8.0),
			viewport_size - Vector2(safe_insets.x + safe_insets.z + 16.0, safe_insets.y + safe_insets.w + 16.0)), viewport_size,
		gameplay_controls.layout_footer_background(viewport_size))
	_layout_debug_spawn_panel()


func _debug_tools_enabled() -> bool:
	# Explicit feature tags, never a generic debug build or saved player setting.
	return preload("res://scripts/prototype/debug_spawn_panel.gd").tools_enabled()


func _create_debug_spawn_panel() -> void:
	if not _debug_tools_enabled() or is_instance_valid(_debug_spawn_panel):
		return
	_debug_spawn_panel = load("res://scripts/prototype/debug_spawn_panel.gd").new()
	_debug_spawn_panel.content = KITCHEN_CONTENT
	_debug_spawn_panel.spawn_requested.connect(_debug_spawn_creations)
	_debug_spawn_panel.clear_requested.connect(_debug_clear_board)
	_debug_spawn_panel.layout_requested.connect(_layout_debug_spawn_panel)
	$DebugUI.add_child(_debug_spawn_panel)
	_layout_debug_spawn_panel()


func _layout_debug_spawn_panel() -> void:
	if is_instance_valid(_debug_spawn_panel):
		var header_end := maxf(_danger_threshold_y + 8.0,
			machine_presentation.release_position(0).y + 30.0)
		_debug_spawn_panel.place(Rect2(Vector2.ZERO,
			Vector2(recipe_progress_panel.get_global_rect().end.x, header_end)))


func _debug_spawn_creations(creation_id: StringName, count: int) -> Array[PrototypePiece]:
	# Guard actions as well as UI creation: hidden controls cannot spawn in release.
	if not _debug_tools_enabled() or game_over or not is_instance_valid(_debug_spawn_panel):
		return []
	var definition := KITCHEN_CONTENT.creation_for_id(creation_id)
	if definition == null or count < 1 or count > 2 or not _chamber_rect.has_area():
		return []
	var radius := _chamber_rect.size.x * KITCHEN_CONTENT.effective_radius_ratio(definition)
	var inset := _wall_thickness * 0.5
	# Developer pieces should be visible below the new machinery too. Very large
	# pairs may need the original upper chamber space; never resize the physics.
	var visible_top := minf(machine_presentation.release_position(0).y,
		floor.position.y - radius * 2.0 * count - inset * 2.0)
	var spawn_top := maxf(_chamber_rect.position.y, visible_top)
	var bounds := Rect2(Vector2(left_wall.position.x + inset, spawn_top + inset),
		Vector2(right_wall.position.x - left_wall.position.x - 2.0 * inset,
			floor.position.y - spawn_top - 2.0 * inset))
	var active := pieces.get_children().filter(func(piece): return piece is PrototypePiece)
	var positions: Array[Vector2] = _debug_spawn_panel.spawn_positions(bounds, radius, count, active)
	_debug_spawn_panel.show_space_warning(positions.size() != count)
	var spawned: Array[PrototypePiece] = []
	# All positions are validated before creating anything; no partial pair.
	for point in positions:
		spawned.append(_spawn_piece(definition, point))
	return spawned


func _debug_clear_board() -> void:
	if not _debug_tools_enabled():
		return
	_cancel_machine_drop() # Clear Board must not leave a scheduled real drop behind.
	_clear_recipe_resolution()
	for piece in pieces.get_children():
		if piece is PrototypePiece:
			piece.queue_free()
	_merge_cooldown_remaining = 0.0
	presentation.reset()
	_discovery_feedback_timer = 0.0
	_max_merge_feedback_timer = 0.0
	new_creation_feedback_label.hide()
	max_merge_feedback_label.hide()
	if not game_over:
		danger_active = false
		danger_timer = 0.0
	# Keep score, charge, discoveries, stage, DROP/NEXT and RNG; never restart here.
	queue_redraw()
	_update_debug_ui()


func _update_next_preview() -> void:
	var definition: CreationDefinition = KITCHEN_CONTENT.creation_for_id(
		_current_creation_id
	)
	if definition == null:
		next_preview_ingredient.texture = null
		next_preview_ingredient.visible = false
		return
	var radius := (
		_chamber_rect.size.x * KITCHEN_CONTENT.effective_radius_ratio(definition)
	)
	var preview_diameter := ceilf(
		radius
		* definition.visual_diameter_scale
		* GAMEPLAY_CONFIG.INGREDIENT_GLOBAL_VISUAL_SCALE
		* GAMEPLAY_CONFIG.INGREDIENT_PREVIEW_SCALE
	)
	# Derived drops use the same artwork without allowing large radii to expand the HUD.
	preview_diameter = minf(preview_diameter, 58.0)
	next_preview.custom_minimum_size = Vector2(preview_diameter, preview_diameter)
	var upcoming := KITCHEN_CONTENT.creation_for_id(_raw_next_creation_id)
	upcoming_preview.texture = upcoming.texture if upcoming != null else null
	if is_instance_valid(machine_presentation) and upcoming != null:
		machine_presentation.sync_items(definition.texture, upcoming.texture)
	next_preview_ingredient.texture = definition.texture
	next_preview_ingredient.visible = true
	_next_preview_style.bg_color = Color.TRANSPARENT
	var corner_radius := ceili(radius)
	_next_preview_style.corner_radius_top_left = corner_radius
	_next_preview_style.corner_radius_top_right = corner_radius
	_next_preview_style.corner_radius_bottom_left = corner_radius
	_next_preview_style.corner_radius_bottom_right = corner_radius


func _build_recipe_progress_strip() -> void:
	for child in recipe_progress_row.get_children():
		child.queue_free()
	_recipe_progress_slots.clear()
	for definition in KITCHEN_CONTENT.collection_creations():
		var slot := PanelContainer.new()
		slot.name = "Creation_%s" % definition.id
		slot.custom_minimum_size = (
			GAMEPLAY_CONFIG.RECIPE_PROGRESS_SLOT_MINIMUM_SIZE
		)
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		slot.set_meta("creation_id", definition.id)
		recipe_progress_row.add_child(slot)
		_recipe_progress_slots.append(slot)

		var visual_layer := Control.new()
		visual_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		slot.add_child(visual_layer)

		var artwork := TextureRect.new()
		artwork.name = "Artwork"
		artwork.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		var artwork_inset := (
			GAMEPLAY_CONFIG.RECIPE_PROGRESS_ARTWORK_INSET_PIXELS
		)
		artwork.offset_left = artwork_inset
		artwork.offset_top = artwork_inset
		artwork.offset_right = -artwork_inset
		artwork.offset_bottom = -artwork_inset
		artwork.mouse_filter = Control.MOUSE_FILTER_IGNORE
		artwork.texture = definition.texture
		artwork.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		artwork.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		visual_layer.add_child(artwork)

		var unknown_marker := TextureRect.new()
		unknown_marker.name = "Unknown"
		unknown_marker.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		unknown_marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
		unknown_marker.texture = MACHINE_PRESENTATION.MYSTERY
		unknown_marker.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		unknown_marker.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		visual_layer.add_child(unknown_marker)
	_update_recipe_progress()


func _update_recipe_progress(
	highlight_creation_id: StringName = &""
) -> void:
	var definitions := KITCHEN_CONTENT.collection_creations()
	for index in range(definitions.size()):
		var definition: CreationDefinition = definitions[index]
		var discovered := discovered_creation_ids.has(definition.id)
		var slot := _recipe_progress_slots[index]
		var artwork := slot.find_child("Artwork", true, false) as TextureRect
		var unknown_marker := slot.find_child("Unknown", true, false) as TextureRect
		slot.set_meta("discovered", discovered)
		slot.tooltip_text = (
			tr(String(definition.display_name_key))
			if discovered
			else tr("COLLECTION_UNKNOWN")
		)
		artwork.material = (
			null if discovered else recipe_locked_silhouette_material
		)
		artwork.visible = discovered
		unknown_marker.visible = not discovered
		slot.add_theme_stylebox_override(
			"panel",
			_recipe_progress_slot_style(discovered)
		)
		if definition.id == highlight_creation_id:
			slot.modulate = Color("fff0a8")
			var tween := slot.create_tween()
			tween.tween_property(slot, "modulate", Color.WHITE, 0.45)


func _recipe_progress_slot_style(_discovered: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	# The approved bubble/mystery textures carry their own outline. No small
	# legacy card behind them; discovery/highlight behavior remains unchanged.
	style.bg_color = Color.TRANSPARENT
	return style


func _drop_piece(viewport_x: float) -> void:
	if game_over or _exit_run_paused or _drop_cycle_active or _chamber_rect.size == Vector2.ZERO:
		return

	var definition: CreationDefinition = KITCHEN_CONTENT.creation_for_id(
		_current_creation_id
	)
	if definition == null:
		return
	var radius := (
		_chamber_rect.size.x * KITCHEN_CONTENT.effective_radius_ratio(definition)
	)
	var wall_clearance := (
		_wall_thickness
		* GAMEPLAY_CONFIG.SPAWN_WALL_CLEARANCE_MULTIPLIER
	)
	var inner_left := (
		left_wall.position.x
		+ wall_clearance
		+ GAMEPLAY_CONFIG.SPAWN_HORIZONTAL_INSET_PIXELS
	)
	var inner_right := (
		right_wall.position.x
		- wall_clearance
		- GAMEPLAY_CONFIG.SPAWN_HORIZONTAL_INSET_PIXELS
	)
	# Keep both the nozzle and the actual body inside the existing drop bounds.
	var inset := maxf(radius, 38.4 * machine_presentation.machine.scale.x)
	_drop_target_x = clampf(viewport_x, inner_left + inset, inner_right - inset)
	_drop_creation_id = definition.id
	_drop_cycle_active = true
	_drop_cycle_elapsed = 0.0
	_drop_released = false
	machine_presentation.begin_drop(_drop_target_x)


func _advance_machine_drop(delta: float) -> void:
	if not _drop_cycle_active:
		machine_presentation.advance(delta)
		return
	# Split long ticks at the contact moment so the feeder receives newly selected
	# artwork before advancing its incoming-preview track. No animation callback
	# owns this transaction, and it runs once even if cosmetics have been stopped.
	var remaining := delta
	if not _drop_released:
		var before_contact := minf(remaining, maxf(0.0, MACHINE_TIMELINE.CONTACT_SECONDS - _drop_cycle_elapsed))
		machine_presentation.advance(before_contact)
		_drop_cycle_elapsed += before_contact
		remaining -= before_contact
		if _drop_cycle_elapsed + 0.000001 >= MACHINE_TIMELINE.CONTACT_SECONDS:
			_drop_released = true
			_commit_machine_drop()
	machine_presentation.advance(remaining)
	_drop_cycle_elapsed += remaining
	if _drop_cycle_elapsed >= MACHINE_TIMELINE.LENGTHS[0]:
		_drop_cycle_active = false
		machine_presentation.finish_drop()
		_update_next_preview()


func _commit_machine_drop() -> void:
	var definition := KITCHEN_CONTENT.creation_for_id(_drop_creation_id)
	var spawned_piece := _spawn_piece(definition, machine_presentation.release_position(_drop_target_x))
	if spawned_piece == null:
		return
	_current_creation_id = _raw_next_creation_id
	_raw_next_creation_id = _roll_spawn_creation_id()
	machine_presentation.machine.set_incoming(KITCHEN_CONTENT.creation_for_id(_raw_next_creation_id).texture)
	_update_debug_ui()
	_request_recipe_evaluation()
	_register_creation(
		spawned_piece.creation_id,
		spawned_piece.global_position,
		spawned_piece.radius,
		false
	)


func _cancel_machine_drop() -> void:
	_drop_cycle_active = false
	_drop_cycle_elapsed = 0.0
	_drop_released = false
	_drop_creation_id = &""
	if is_instance_valid(machine_presentation):
		machine_presentation.reset(not game_over)
		if is_node_ready():
			_update_next_preview()


func _spawn_piece(
	definition: CreationDefinition,
	spawn_position: Vector2,
	initial_linear_velocity: Vector2 = Vector2.ZERO,
	initial_angular_velocity: float = 0.0,
	initial_rotation: float = 0.0
) -> PrototypePiece:
	if definition == null or KITCHEN_CONTENT.creation_for_id(definition.id) != definition:
		return null
	var piece := PIECE_SCENE.instantiate() as PrototypePiece
	piece.configure(
		definition,
		_chamber_rect.size.x * KITCHEN_CONTENT.effective_radius_ratio(definition)
	)
	piece.position = pieces.to_local(spawn_position)
	piece.rotation = initial_rotation
	piece.linear_velocity = initial_linear_velocity
	piece.angular_velocity = initial_angular_velocity
	_piece_sequence += 1
	piece.spawn_sequence = _piece_sequence
	piece.body_entered.connect(_on_piece_body_entered.bind(piece))
	piece.body_exited.connect(_on_piece_body_exited.bind(piece))
	piece.tree_exiting.connect(_on_piece_exiting.bind(piece))
	pieces.add_child(piece)
	piece.sleeping = false
	_request_recipe_evaluation()
	return piece


func _on_piece_body_entered(other_body: Node, source_piece: PrototypePiece) -> void:
	if game_over or not other_body is PrototypePiece:
		return
	var other_piece := other_body as PrototypePiece
	if source_piece == other_piece or not _is_live_piece(source_piece) or not _is_live_piece(other_piece):
		return
	var recipe := KITCHEN_CONTENT.recipe_for(source_piece.creation_id, other_piece.creation_id)
	if recipe == null:
		return
	if source_piece.creation_id == other_piece.creation_id:
		var pair := _ordered_pair(source_piece, other_piece)
		_physical_contacts[_contact_key(pair[0], pair[1])] = pair
		# Resolve batched contacts outside the physics callback.
		_request_recipe_evaluation()


func _on_piece_body_exited(other_body: Node, source_piece: PrototypePiece) -> void:
	if other_body is PrototypePiece:
		if _physical_contacts.erase(_contact_key(source_piece, other_body)):
			_request_recipe_evaluation()


func _ordered_pair(first: PrototypePiece, second: PrototypePiece) -> Array:
	return [first, second] if first.spawn_sequence < second.spawn_sequence else [second, first]


func _contact_key(first: PrototypePiece, second: PrototypePiece) -> Vector2i:
	return Vector2i(mini(first.spawn_sequence, second.spawn_sequence),
		maxi(first.spawn_sequence, second.spawn_sequence))


func _is_live_piece(piece: Variant) -> bool:
	return is_instance_valid(piece) and not piece.is_queued_for_deletion() and piece.get_parent() == pieces


func _queue_merge_pair(
	first_piece: PrototypePiece,
	second_piece: PrototypePiece,
	result_creation_id: StringName
) -> void:
	first_piece.merge_pending = true
	second_piece.merge_pending = true
	_queued_merge_pairs.append(
		[first_piece, second_piece, result_creation_id]
	)


func _try_resolve_next_merge() -> void:
	if game_over or _exit_run_paused or _recipe_evaluation_pending or _merge_resolution_pending or _merge_cooldown_remaining > 0.0:
		return

	while not _queued_merge_pairs.is_empty():
		var pair: Array = _queued_merge_pairs.pop_front()
		var first_piece := pair[0] as PrototypePiece
		var second_piece := pair[1] as PrototypePiece
		var result_creation_id := StringName(pair[2])
		if not _is_valid_merge_pair(
			first_piece,
			second_piece,
			result_creation_id
		):
			_release_merge_pair(first_piece, second_piece)
			continue

		_merge_resolution_pending = true
		_resolving_merge_pair = pair
		var result_position := (
			first_piece.global_position + second_piece.global_position
		) * 0.5
		var result_linear_velocity := (
			first_piece.linear_velocity + second_piece.linear_velocity
		) * 0.5
		var result_angular_velocity := (
			first_piece.angular_velocity + second_piece.angular_velocity
		) * 0.5
		var result_rotation := lerp_angle(
			first_piece.global_rotation,
			second_piece.global_rotation,
			0.5
		)
		call_deferred(
			"_resolve_merge",
			first_piece,
			second_piece,
			result_creation_id,
			result_position,
			result_linear_velocity,
			result_angular_velocity,
			result_rotation,
			_merge_generation
		)
		return


func _is_valid_merge_pair(
	first_piece: PrototypePiece,
	second_piece: PrototypePiece,
	result_creation_id: StringName
) -> bool:
	if not (
		_is_active_merge_source(first_piece)
		and _is_active_merge_source(second_piece)
		and first_piece != second_piece
	):
		return false
	var recipe: MergeRecipe = KITCHEN_CONTENT.recipe_for(
		first_piece.creation_id,
		second_piece.creation_id
	)
	return recipe != null and first_piece.creation_id == second_piece.creation_id and recipe.result == result_creation_id


func _release_merge_pair(
	first_piece: Variant,
	second_piece: Variant
) -> void:
	for piece in [first_piece, second_piece]:
		if (
			is_instance_valid(piece)
			and not piece.is_queued_for_deletion()
			and piece.get_parent() == pieces
		):
			piece.merge_pending = false


func _resolve_merge(
	first_piece: PrototypePiece,
	second_piece: PrototypePiece,
	result_creation_id: StringName,
	result_position: Vector2,
	result_linear_velocity: Vector2,
	result_angular_velocity: float,
	result_rotation: float,
	generation: int
) -> void:
	if game_over or generation != _merge_generation:
		return
	if _exit_run_paused:
		return # Keep the latched pair; Resume reevaluates it once, without rewards now.
	if _recipe_evaluation_pending:
		_evaluate_recipes()
		return
	if not _is_valid_merge_pair(
		first_piece,
		second_piece,
		result_creation_id
	):
		_merge_resolution_pending = false
		_release_merge_pair(first_piece, second_piece)
		_try_resolve_next_merge()
		return
	var result_definition: CreationDefinition = (
		KITCHEN_CONTENT.creation_for_id(result_creation_id)
	)
	if result_definition == null:
		_merge_resolution_pending = false
		_release_merge_pair(first_piece, second_piece)
		_try_resolve_next_merge()
		return

	_resolving_merge_pair.clear()
	var result_radius: float = (
		_chamber_rect.size.x * KITCHEN_CONTENT.effective_radius_ratio(result_definition)
	)
	var safe_result_position := _find_safe_merge_position(
		result_position,
		result_radius,
		first_piece,
		second_piece
	)
	var recipe := KITCHEN_CONTENT.recipe_for(first_piece.creation_id, second_piece.creation_id)
	_wake_merge_neighbours(first_piece, second_piece)
	first_piece.queue_free()
	second_piece.queue_free()
	var result_piece := _spawn_piece(
		result_definition,
		safe_result_position,
		result_linear_velocity,
		result_angular_velocity,
		result_rotation
	)
	_apply_merge_expansion(result_piece)
	presentation.show_recipe_merge(
		recipe,
		safe_result_position,
		minf(result_radius * 3.0, _chamber_rect.size.x * 0.45)
	)
	machine_presentation.show_merge_reaction()
	_merge_cooldown_remaining = MERGE_RESOLUTION_COOLDOWN_SECONDS
	_merge_resolution_pending = false
	_award_creation(result_definition, safe_result_position, result_radius)
	_request_recipe_evaluation()


func _award_creation(definition: CreationDefinition, world_position: Vector2, radius: float) -> void:
	# Called only after the physical merge result exists, before any settling wait.
	# Advance future selections only: never reroll the controlled/buffered drops.
	_spawn_stage_index = KITCHEN_CONTENT.spawn_stage_after_merge(_spawn_stage_index, definition.id)
	score += definition.progression_rank * definition.progression_rank * 2
	pulse_charge = mini(MAX_PULSE_CHARGE, pulse_charge + PULSE_CHARGE_PER_MERGE)
	if definition.id == KITCHEN_CONTENT.final_creation_id:
		_max_merge_feedback_timer = MAX_MERGE_FEEDBACK_SECONDS
		max_merge_feedback_label.visible = true
	_register_creation(definition.id, world_position, radius, true)
	_update_debug_ui()


func _find_safe_merge_position(
	desired_position: Vector2,
	result_radius: float,
	first_piece: PrototypePiece,
	second_piece: PrototypePiece
) -> Vector2:
	var clamped_position := _clamp_merge_position(desired_position, result_radius)
	var best_position := clamped_position
	var best_movement_squared := desired_position.distance_squared_to(clamped_position)
	var best_vertical_movement := absf(clamped_position.y - desired_position.y)
	var best_clearance := _merge_position_clearance(
		clamped_position,
		result_radius,
		first_piece,
		second_piece
	)
	if best_clearance >= MERGE_PLACEMENT_CLEARANCE:
		return clamped_position

	var found_safe_position := false
	var nearest_safe_position := clamped_position
	var nearest_safe_movement_squared := INF
	var nearest_safe_vertical_movement := INF
	var search_step := maxf(6.0, result_radius * 0.25)
	for ring in range(1, MERGE_PLACEMENT_SEARCH_RINGS + 1):
		var search_distance := search_step * ring
		for direction_index in range(MERGE_PLACEMENT_SEARCH_DIRECTIONS):
			var angle := TAU * direction_index / MERGE_PLACEMENT_SEARCH_DIRECTIONS
			var candidate := _clamp_merge_position(
				desired_position + Vector2.from_angle(angle) * search_distance,
				result_radius
			)
			var candidate_clearance := _merge_position_clearance(
				candidate,
				result_radius,
				first_piece,
				second_piece
			)
			var movement_squared := desired_position.distance_squared_to(candidate)
			var vertical_movement := absf(candidate.y - desired_position.y)
			if candidate_clearance >= MERGE_PLACEMENT_CLEARANCE:
				var same_distance := is_equal_approx(
					movement_squared,
					nearest_safe_movement_squared
				)
				if (
					not found_safe_position
					or (not same_distance and movement_squared < nearest_safe_movement_squared)
					or (same_distance and vertical_movement < nearest_safe_vertical_movement)
				):
					found_safe_position = true
					nearest_safe_position = candidate
					nearest_safe_movement_squared = movement_squared
					nearest_safe_vertical_movement = vertical_movement
				continue
			var same_clearance := is_equal_approx(candidate_clearance, best_clearance)
			var same_fallback_distance := is_equal_approx(
				movement_squared,
				best_movement_squared
			)
			if (
				(not same_clearance and candidate_clearance > best_clearance)
				or (
					same_clearance
					and (
						(not same_fallback_distance and movement_squared < best_movement_squared)
						or (
							same_fallback_distance
							and vertical_movement < best_vertical_movement
						)
					)
				)
			):
				best_clearance = candidate_clearance
				best_position = candidate
				best_movement_squared = movement_squared
				best_vertical_movement = vertical_movement
	if found_safe_position:
		return nearest_safe_position
	return best_position


func _clamp_merge_position(position: Vector2, result_radius: float) -> Vector2:
	var wall_inset := _wall_thickness * 0.5
	return Vector2(
		clampf(
			position.x,
			left_wall.position.x + wall_inset + result_radius,
			right_wall.position.x - wall_inset - result_radius
		),
		clampf(
			position.y,
			_chamber_rect.position.y + wall_inset + result_radius,
			floor.position.y - wall_inset - result_radius
		)
	)


func _merge_position_clearance(
	position: Vector2,
	result_radius: float,
	first_piece: PrototypePiece,
	second_piece: PrototypePiece
) -> float:
	var minimum_clearance := INF
	for child in pieces.get_children():
		if not child is PrototypePiece:
			continue
		var piece := child as PrototypePiece
		if piece == first_piece or piece == second_piece:
			continue
		if piece.is_queued_for_deletion() or piece.merge_pending:
			continue
		var clearance := (
			position.distance_to(piece.global_position)
			- result_radius
			- piece.radius
		)
		minimum_clearance = minf(minimum_clearance, clearance)
	return minimum_clearance


func _apply_merge_expansion(result_piece: PrototypePiece) -> void:
	var influence_radius := result_piece.radius * MERGE_EXPANSION_RADIUS_MULTIPLIER
	for child in pieces.get_children():
		if not child is PrototypePiece:
			continue
		var piece := child as PrototypePiece
		if piece == result_piece:
			continue
		if piece.is_queued_for_deletion() or piece.merge_pending:
			continue

		var offset := piece.global_position - result_piece.global_position
		var distance := offset.length()
		if distance <= 0.001 or distance >= influence_radius:
			continue
		var expansion_direction := offset / distance
		expansion_direction.y = (
			maxf(0.0, expansion_direction.y) * MERGE_EXPANSION_DOWNWARD_SCALE
		)
		if expansion_direction.is_zero_approx():
			continue
		var distance_influence := 1.0 - distance / influence_radius
		var impulse_strength := minf(
			MERGE_EXPANSION_MAX_IMPULSE,
			MERGE_EXPANSION_BASE_IMPULSE * distance_influence / piece.mass
		)
		piece.apply_central_impulse(expansion_direction * impulse_strength)


func _is_active_merge_source(piece: Variant) -> bool:
	return (
		is_instance_valid(piece)
		and not piece.is_queued_for_deletion()
		and piece.get_parent() == pieces
		and piece.merge_pending
	)


func _request_recipe_evaluation() -> void:
	if _recipe_evaluation_pending or game_over or not is_inside_tree():
		return
	_recipe_evaluation_pending = true
	_evaluate_recipes.call_deferred()


func _evaluate_recipes() -> void:
	if not _recipe_evaluation_pending or game_over or _exit_run_paused or not is_inside_tree():
		return
	_recipe_evaluation_pending = false
	# Batch contacts outside the physics callback; preserve pending contact pairs
	# across the existing cooldown with deterministic oldest-pair arbitration.
	_merge_generation += 1
	var contact_pairs := _physical_contacts.duplicate()
	var latched_pairs := _queued_merge_pairs.duplicate()
	if not _resolving_merge_pair.is_empty():
		latched_pairs.append(_resolving_merge_pair.duplicate())
	for pair in latched_pairs:
		if _is_live_piece(pair[0]) and _is_live_piece(pair[1]):
			var ordered := _ordered_pair(pair[0], pair[1])
			contact_pairs[_contact_key(ordered[0], ordered[1])] = ordered
		_release_merge_pair(pair[0], pair[1])
	_queued_merge_pairs.clear()
	_resolving_merge_pair.clear()
	_merge_resolution_pending = false

	var contacts: Array = contact_pairs.values()
	contacts.sort_custom(func(a: Array, b: Array) -> bool:
		if not _is_live_piece(a[0]) or not _is_live_piece(a[1]):
			return false
		if not _is_live_piece(b[0]) or not _is_live_piece(b[1]):
			return true
		if a[0].spawn_sequence != b[0].spawn_sequence:
			return a[0].spawn_sequence < b[0].spawn_sequence
		return a[1].spawn_sequence < b[1].spawn_sequence
	)
	for pair in contacts:
		var first := pair[0] as PrototypePiece
		var second := pair[1] as PrototypePiece
		if not _is_live_piece(first) or not _is_live_piece(second):
			continue
		if first.merge_pending or second.merge_pending or first.creation_id != second.creation_id:
			continue
		var recipe := KITCHEN_CONTENT.recipe_for(first.creation_id, second.creation_id)
		if recipe != null:
			_queue_merge_pair(first, second, recipe.result)
	_try_resolve_next_merge()


func _wake_merge_neighbours(first: PrototypePiece, second: PrototypePiece) -> void:
	# Replacement runs outside collision callbacks. Wake actual live
	# contacts before their support disappears, including vertical neighbours
	# that intentionally receive no controlled-expansion impulse.
	for source in [first, second]:
		if not _is_live_piece(source):
			continue
		for body in source.get_colliding_bodies():
			if not is_instance_valid(body) or not body is PrototypePiece:
				continue
			if body != first and body != second and _is_live_piece(body) and not body.merge_pending:
				body.sleeping = false


func _on_piece_exiting(piece: PrototypePiece) -> void:
	for key in _physical_contacts.keys():
		if key.x == piece.spawn_sequence or key.y == piece.spawn_sequence:
			_physical_contacts.erase(key)
	_request_recipe_evaluation()


func _clear_recipe_resolution() -> void:
	_merge_generation += 1
	_recipe_evaluation_pending = false
	for child in pieces.get_children():
		if child is PrototypePiece:
			child.merge_pending = false
	_physical_contacts.clear()
	_queued_merge_pairs.clear()
	_resolving_merge_pair.clear()
	_merge_resolution_pending = false


func _exit_tree() -> void:
	if _exit_run_paused:
		_exit_run_paused = false
		get_tree().paused = false
	_cancel_machine_drop()
	_clear_drop_touch_state()
	_clear_recipe_resolution()


func _roll_spawn_creation_id() -> StringName:
	if _spawn_stage_index < 0 or _spawn_stage_index >= KITCHEN_CONTENT.spawn_stages.size():
		return &""
	return KITCHEN_CONTENT.spawn_stages[_spawn_stage_index].select_creation(_rng)


func _register_creation(
	creation_id: StringName,
	world_position: Vector2,
	radius: float,
	visual_feedback_already_playing: bool
) -> bool:
	var definition: CreationDefinition = KITCHEN_CONTENT.creation_for_id(
		creation_id
	)
	if definition == null:
		return false
	var highest_definition: CreationDefinition = (
		KITCHEN_CONTENT.creation_for_id(highest_creation_id)
	)
	if (
		highest_definition == null
		or definition.progression_rank > highest_definition.progression_rank
		or (
			definition.progression_rank == highest_definition.progression_rank
			and definition.collection_order > highest_definition.collection_order
		)
	):
		highest_creation_id = creation_id
	if discovered_creation_ids.has(creation_id):
		return false

	discovered_creation_ids.append(creation_id)
	_sort_discovered_creation_ids()
	_new_discoveries_this_run.append(creation_id)
	_save_recipe_discoveries()
	_update_recipe_progress(creation_id)
	_discovery_feedback_timer = DISCOVERY_FEEDBACK_SECONDS
	new_creation_feedback_label.text = tr("NEW_CREATION")
	new_creation_feedback_label.visible = true
	if not visual_feedback_already_playing:
		presentation.show_discovery(
			world_position,
			minf(radius * 3.0, _chamber_rect.size.x * 0.45)
		)
	return true


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
	_sort_discovered_creation_ids()


func _save_recipe_discoveries() -> void:
	var save_file := ConfigFile.new()
	var load_error := save_file.load(_discovery_save_path)
	if load_error != OK and load_error != ERR_FILE_NOT_FOUND:
		push_warning(
			"Could not preserve existing discovery save data: error %d"
			% load_error
		)
		save_file = ConfigFile.new()
	save_file.set_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_FORMAT_KEY,
		KITCHEN_CONTENT.content_version
	)
	save_file.set_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_CONTENT_KEY,
		String(KITCHEN_CONTENT.content_id)
	)
	save_file.set_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_IDS_KEY,
		PackedStringArray(discovered_creation_ids)
	)
	var save_error := save_file.save(_discovery_save_path)
	if save_error != OK:
		push_warning("Could not save recipe discoveries: error %d" % save_error)


func _sort_discovered_creation_ids() -> void:
	var ordered_ids: Array[StringName] = []
	for definition in KITCHEN_CONTENT.collection_creations():
		if discovered_creation_ids.has(definition.id):
			ordered_ids.append(definition.id)
	discovered_creation_ids = ordered_ids


func _creation_display_name(creation_id: StringName) -> String:
	var definition: CreationDefinition = KITCHEN_CONTENT.creation_for_id(
		creation_id
	)
	if definition == null:
		return ""
	return tr(String(definition.display_name_key))


func _show_run_result() -> void:
	result_highest_heading.text = (
		tr("RESULT_HIGHEST_CREATION") % ""
	).strip_edges()
	var highest_definition: CreationDefinition = (
		KITCHEN_CONTENT.creation_for_id(highest_creation_id)
	)
	var has_creation := highest_definition != null
	result_creation.visible = has_creation
	result_creation_name.visible = has_creation
	if has_creation:
		result_creation.texture = highest_definition.texture
		result_creation_name.text = _creation_display_name(highest_creation_id)
	else:
		result_creation.texture = null
		result_creation_name.text = ""

	var highest_new_creation_id: StringName
	if not _new_discoveries_this_run.is_empty():
		for discovered_creation_id in _new_discoveries_this_run:
			var discovered_definition: CreationDefinition = (
				KITCHEN_CONTENT.creation_for_id(discovered_creation_id)
			)
			var current_highest_definition: CreationDefinition = (
				KITCHEN_CONTENT.creation_for_id(highest_new_creation_id)
			)
			if (
				current_highest_definition == null
				or discovered_definition.progression_rank
					> current_highest_definition.progression_rank
				or (
					discovered_definition.progression_rank
						== current_highest_definition.progression_rank
					and discovered_definition.collection_order
						> current_highest_definition.collection_order
				)
			):
				highest_new_creation_id = discovered_creation_id
	result_new_recipe.visible = not highest_new_creation_id.is_empty()
	result_new_recipe.text = (
		tr("RESULT_NEW_RECIPE")
			% _creation_display_name(highest_new_creation_id)
		if not highest_new_creation_id.is_empty()
		else ""
	)
	presentation.show_result()
	result_tolina.texture = tolina_visual.texture
	result_overlay.visible = true
	play_again_button.grab_focus()


func _has_dangerous_piece() -> bool:
	for child in pieces.get_children():
		if not child is PrototypePiece:
			continue
		var piece := child as PrototypePiece
		if piece.is_queued_for_deletion() or piece.merge_pending:
			continue
		var bottom_edge := piece.global_position.y + piece.radius
		var is_supported := piece.sleeping or not piece.get_colliding_bodies().is_empty()
		if (
			bottom_edge <= _danger_threshold_y
			and absf(piece.linear_velocity.y)
				<= GAMEPLAY_CONFIG.DANGER_VERTICAL_SPEED_THRESHOLD
			and is_supported
		):
			return true
	return false


func _enter_game_over() -> void:
	_clear_drop_touch_state()
	_reset_restart_hold_feedback()
	gameplay_controls.clear_press_states()
	game_over = true
	_cancel_machine_drop()
	_clear_recipe_resolution()
	danger_active = true
	danger_timer = GAMEPLAY_CONFIG.DANGER_GRACE_SECONDS
	for child in pieces.get_children():
		if child is PrototypePiece:
			child.set_deferred("freeze", true)
	_show_run_result()
	if is_instance_valid(_debug_spawn_panel):
		_debug_spawn_panel.set_run_active(false)
	queue_redraw()


func _activate_pulse(direction: Vector2) -> void:
	if game_over or _exit_run_paused or pulse_charge < MAX_PULSE_CHARGE:
		return
	var horizontal_direction := signf(direction.x)
	if is_zero_approx(horizontal_direction):
		return

	pulse_charge = 0
	_pulse_feedback_timer = PULSE_FEEDBACK_SECONDS
	pulse_feedback_label.visible = true
	var active_pieces: Array[PrototypePiece] = []
	var push_center := Vector2.ZERO
	for child in pieces.get_children():
		if not child is PrototypePiece:
			continue
		var piece := child as PrototypePiece
		if piece.is_queued_for_deletion() or piece.merge_pending:
			continue
		active_pieces.append(piece)
		push_center += piece.global_position

	if not active_pieces.is_empty():
		push_center /= active_pieces.size()
	var separation_radius := (
		_chamber_rect.size.x * PULSE_SEPARATION_RADIUS_RATIO
	)
	for piece in active_pieces:
		var impulse := Vector2(
			horizontal_direction * PULSE_BASE_IMPULSE / piece.mass,
			0.0
		)
		var offset := piece.global_position - push_center
		var distance := offset.length()
		if distance > 0.001 and distance < separation_radius:
			var separation_direction := offset / distance
			separation_direction.y = (
				maxf(0.0, separation_direction.y)
				* PULSE_SEPARATION_DOWNWARD_SCALE
			)
			if not separation_direction.is_zero_approx():
				var distance_influence := 1.0 - distance / separation_radius
				var separation_strength := minf(
					PULSE_SEPARATION_MAX_IMPULSE,
					PULSE_SEPARATION_BASE_IMPULSE * distance_influence
				) / piece.mass
				impulse += separation_direction * separation_strength
		piece.apply_central_impulse(impulse)
	_update_debug_ui()


func _begin_restart_hold() -> void:
	if game_over or _exit_run_paused:
		return
	_restart_hold_active = true
	_restart_hold_elapsed = 0.0
	restart_hold_progress.value = 0.0
	restart_hold_progress.visible = true


func _cancel_restart_hold() -> void:
	if not _restart_hold_active:
		return
	_reset_restart_hold_feedback()


func _reset_restart_hold_feedback() -> void:
	_restart_hold_active = false
	_restart_hold_elapsed = 0.0
	restart_hold_progress.value = 0.0
	restart_hold_progress.visible = false


func _restart_sandbox() -> void:
	if _exit_run_paused:
		return
	_cancel_machine_drop()
	_clear_drop_touch_state()
	_reset_restart_hold_feedback()
	gameplay_controls.clear_press_states()
	_clear_recipe_resolution()
	for piece in pieces.get_children():
		piece.queue_free()

	danger_active = false
	danger_timer = 0.0
	game_over = false
	pulse_charge = 0
	score = 0
	_pulse_feedback_timer = 0.0
	_max_merge_feedback_timer = 0.0
	_discovery_feedback_timer = 0.0
	_merge_cooldown_remaining = 0.0
	_merge_resolution_pending = false
	_queued_merge_pairs.clear()
	_new_discoveries_this_run.clear()
	highest_creation_id = &""
	if is_instance_valid(_debug_spawn_panel):
		_debug_spawn_panel.set_run_active(true)
	presentation.reset()
	result_overlay.visible = false
	result_creation.texture = null
	result_creation_name.text = ""
	result_new_recipe.visible = false
	result_new_recipe.text = ""
	play_again_button.release_focus()
	pulse_feedback_label.visible = false
	max_merge_feedback_label.visible = false
	new_creation_feedback_label.visible = false
	_spawn_stage_index = 0
	_rng.seed = INITIAL_SEED
	_current_creation_id = _roll_spawn_creation_id()
	_raw_next_creation_id = _roll_spawn_creation_id()
	machine_presentation.reset()
	_update_recipe_progress()
	_request_recipe_evaluation()
	queue_redraw()
	_update_debug_ui()


func _update_debug_ui() -> void:
	_update_next_preview()
	score_label.text = "Score: %d" % score
	pulse_label.text = "Pulse: %d%%" % pulse_charge
	machine_presentation.update_hud(score, pulse_charge)
	danger_label.visible = danger_active
	var pulse_available := pulse_charge >= MAX_PULSE_CHARGE and not game_over
	pulse_left_button.disabled = not pulse_available
	pulse_right_button.disabled = not pulse_available
	restart_button.disabled = game_over
	exit_run_button.disabled = game_over


func _open_exit_run() -> void:
	if _exit_run_paused or game_over:
		return
	_cancel_restart_hold()
	_clear_drop_touch_state()
	gameplay_controls.clear_press_states()
	_exit_run_paused = true
	exit_run_modal.show()
	get_tree().paused = true


func _resume_run() -> void:
	if not _exit_run_paused:
		return
	gameplay_controls.clear_press_states()
	exit_run_modal.hide()
	_exit_run_paused = false
	get_tree().paused = false
	# Deferred calls also run in a paused SceneTree. Retain their inputs and
	# resume arbitration here instead of letting them consume/reward behind UI.
	if _recipe_evaluation_pending or _merge_resolution_pending:
		_recipe_evaluation_pending = true
		_evaluate_recipes.call_deferred()


func _confirm_exit_run() -> void:
	if not _exit_run_paused:
		return
	# Scene teardown releases contacts and accepted drops; it also releases our
	# pause. No reset/save deletion and no application quit.
	get_tree().change_scene_to_file("res://scenes/menu/main_menu.tscn")
