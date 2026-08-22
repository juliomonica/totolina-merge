extends Node2D

const PIECE_SCENE := preload("res://scenes/prototype/piece.tscn")
const PIECE_VISUAL_SCRIPT := preload("res://scripts/prototype/piece_visual.gd")
const INITIAL_SEED := 12345
const CHAMBER_WIDTH_RATIO := 0.86
const CHAMBER_HEIGHT_RATIO := 0.72
const CHAMBER_TOP_RATIO := 0.17
const CHAMBER_MAX_ASPECT_RATIO := 0.67
const DANGER_LINE_CHAMBER_RATIO := 0.35
const DANGER_GRACE_SECONDS := 3.0
const DANGER_VERTICAL_SPEED_THRESHOLD := 10.0
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
const DISCOVERY_SAVE_KEY := "discovered_tiers"
const MERGE_PLACEMENT_CLEARANCE := 0.5
const MERGE_PLACEMENT_SEARCH_RINGS := 16
const MERGE_PLACEMENT_SEARCH_DIRECTIONS := 16
const MERGE_EXPANSION_RADIUS_MULTIPLIER := 2.0
const MERGE_EXPANSION_BASE_IMPULSE := 40.0
const MERGE_EXPANSION_MAX_IMPULSE := 32.0
const MERGE_EXPANSION_DOWNWARD_SCALE := 0.25
const MERGE_RESOLUTION_COOLDOWN_SECONDS := 0.45
const UI_EDGE_MARGIN := 16.0
const HUD_HEIGHT := 88.0
const CONTROLS_HEIGHT := 52.0
const TOLINA_SAFE_WIDTH := 90.0
const TOLINA_SAFE_HEIGHT := 96.0
const TOLINA_HUD_GAP := 10.0
const NORMAL_SPAWN_MAX_TIER := 3
const TIER_RADIUS_RATIOS := [
	0.0460,
	0.0538,
	0.0630,
	0.0737,
	0.0862,
	0.1009,
	0.1180,
	0.1900,
	0.2600,
]
const TIER_MASSES := [
	1.00,
	1.30,
	1.69,
	2.20,
	2.86,
	3.71,
	4.83,
	6.27,
	8.16,
]
const TIER_COLORS := [
	Color("79c7ff"),
	Color("ffc857"),
	Color("ff7b89"),
	Color("72e0a1"),
	Color("b88cff"),
	Color("ff9f43"),
	Color("47e6e6"),
	Color("f368e0"),
	Color("f5f5f5"),
]
const TIER_NAME_KEYS := [
	"RECIPE_TIER_1",
	"RECIPE_TIER_2",
	"RECIPE_TIER_3",
	"RECIPE_TIER_4",
	"RECIPE_TIER_5",
	"RECIPE_TIER_6",
	"RECIPE_TIER_7",
	"RECIPE_TIER_8",
	"RECIPE_TIER_9",
]

@onready var pieces: Node2D = $Pieces
@onready var left_wall: StaticBody2D = $Chamber/LeftWall
@onready var right_wall: StaticBody2D = $Chamber/RightWall
@onready var floor: StaticBody2D = $Chamber/Floor
@onready var tolina_visual: TextureRect = $DebugUI/Tolina
@onready var hud_panel: PanelContainer = $DebugUI/HUDPanel
@onready var next_preview: Panel = $DebugUI/HUDPanel/Margin/Row/Next/PreviewCenter/Preview
@onready var next_preview_ingredient: TextureRect = $DebugUI/HUDPanel/Margin/Row/Next/PreviewCenter/Preview/Ingredient
@onready var score_label: Label = $DebugUI/HUDPanel/Margin/Row/Score
@onready var pulse_label: Label = $DebugUI/HUDPanel/Margin/Row/Pulse
@onready var controls_panel: PanelContainer = $DebugUI/ControlsPanel
@onready var pulse_left_button: Button = $DebugUI/ControlsPanel/Margin/Row/PulseLeft
@onready var restart_button: Button = $DebugUI/ControlsPanel/Margin/Row/Restart
@onready var pulse_right_button: Button = $DebugUI/ControlsPanel/Margin/Row/PulseRight
@onready var pulse_feedback_label: Label = $DebugUI/PulseFeedback
@onready var max_merge_feedback_label: Label = $DebugUI/MaxMergeFeedback
@onready var new_creation_feedback_label: Label = $DebugUI/NewCreationFeedback
@onready var danger_label: Label = $DebugUI/Danger
@onready var game_over_label: Label = $DebugUI/GameOver
@onready var run_result_label: Label = $DebugUI/RunResult
@onready var presentation: PrototypeSandboxPresentation = $Presentation

var _rng := RandomNumberGenerator.new()
var _next_tier := 1
var _chamber_rect := Rect2()
var _wall_thickness := 0.0
var _danger_line_y := 0.0
var _next_preview_style := StyleBoxFlat.new()
var _pulse_feedback_timer := 0.0
var _max_merge_feedback_timer := 0.0
var _discovery_feedback_timer := 0.0
var _merge_cooldown_remaining := 0.0
var _merge_resolution_pending := false
var _queued_merge_pairs: Array = []
var _new_discoveries_this_run: Array[int] = []
var _discovery_save_path := DISCOVERY_SAVE_PATH

var danger_active := false
var danger_timer := 0.0
var game_over := false
var pulse_charge := 0
var score := 0
var highest_creation_reached := 0
var discovered_creation_tiers: Array[int] = []


func _ready() -> void:
	Engine.physics_ticks_per_second = 60
	_load_recipe_discoveries()
	_rng.seed = INITIAL_SEED
	_next_tier = _roll_tier()
	next_preview.add_theme_stylebox_override("panel", _next_preview_style)
	restart_button.pressed.connect(_restart_sandbox)
	pulse_left_button.pressed.connect(_activate_pulse.bind(Vector2.LEFT))
	pulse_right_button.pressed.connect(_activate_pulse.bind(Vector2.RIGHT))
	get_viewport().size_changed.connect(_layout_chamber)
	_layout_chamber()
	_update_debug_ui()


func _process(delta: float) -> void:
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
	if game_over:
		return

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
		if danger_timer >= DANGER_GRACE_SECONDS:
			_enter_game_over()
	elif danger_active:
		danger_active = false
		danger_timer = 0.0
		queue_redraw()


func _input(event: InputEvent) -> void:
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
	if event is InputEventScreenTouch:
		var touch := event as InputEventScreenTouch
		if touch.pressed:
			_drop_piece(touch.position.x)
			get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton:
		var click := event as InputEventMouseButton
		if click.button_index == MOUSE_BUTTON_LEFT and click.pressed:
			_drop_piece(click.position.x)
			get_viewport().set_input_as_handled()


func _draw() -> void:
	if _chamber_rect.size == Vector2.ZERO:
		return

	var danger_line_color := Color("ff3b30") if danger_active else Color("ffb020")
	draw_line(
		Vector2(_chamber_rect.position.x, _danger_line_y),
		Vector2(_chamber_rect.end.x, _danger_line_y),
		danger_line_color,
		3.0
	)


func _layout_chamber() -> void:
	var viewport_size := get_viewport_rect().size
	if viewport_size.x <= 0.0 or viewport_size.y <= 0.0:
		return

	var chamber_height := viewport_size.y * CHAMBER_HEIGHT_RATIO
	var chamber_width := minf(
		viewport_size.x * CHAMBER_WIDTH_RATIO,
		chamber_height * CHAMBER_MAX_ASPECT_RATIO
	)
	var chamber_size := Vector2(chamber_width, chamber_height)
	_chamber_rect = Rect2(
		Vector2(
			(viewport_size.x - chamber_size.x) * 0.5,
			viewport_size.y * CHAMBER_TOP_RATIO
		),
		chamber_size
	)
	_wall_thickness = maxf(8.0, viewport_size.x * 0.018)
	_danger_line_y = (
		_chamber_rect.position.y
		+ _chamber_rect.size.y * DANGER_LINE_CHAMBER_RATIO
	)

	left_wall.position = Vector2(
		_chamber_rect.position.x,
		_chamber_rect.position.y + _chamber_rect.size.y * 0.5
	)
	right_wall.position = Vector2(
		_chamber_rect.end.x,
		_chamber_rect.position.y + _chamber_rect.size.y * 0.5
	)
	floor.position = Vector2(
		_chamber_rect.position.x + _chamber_rect.size.x * 0.5,
		_chamber_rect.end.y
	)

	var left_shape := left_wall.get_node("CollisionShape2D").shape as RectangleShape2D
	var right_shape := right_wall.get_node("CollisionShape2D").shape as RectangleShape2D
	var floor_shape := floor.get_node("CollisionShape2D").shape as RectangleShape2D
	left_shape.size = Vector2(_wall_thickness, _chamber_rect.size.y + _wall_thickness)
	right_shape.size = left_shape.size
	floor_shape.size = Vector2(_chamber_rect.size.x + _wall_thickness, _wall_thickness)
	danger_label.offset_top = _danger_line_y - 34.0
	danger_label.offset_bottom = _danger_line_y - 6.0
	_layout_safe_ui(viewport_size)
	presentation.layout(_chamber_rect)
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

	var tolina_left := safe_insets.x + UI_EDGE_MARGIN
	var tolina_top := safe_insets.y + UI_EDGE_MARGIN
	tolina_visual.offset_left = tolina_left
	tolina_visual.offset_top = tolina_top
	tolina_visual.offset_right = tolina_left + TOLINA_SAFE_WIDTH
	tolina_visual.offset_bottom = minf(
		tolina_top + TOLINA_SAFE_HEIGHT,
		_chamber_rect.position.y - UI_EDGE_MARGIN * 0.5
	)
	hud_panel.offset_left = (
		tolina_visual.offset_right + TOLINA_HUD_GAP
	)
	hud_panel.offset_top = safe_insets.y + UI_EDGE_MARGIN
	hud_panel.offset_right = -(safe_insets.z + UI_EDGE_MARGIN)
	hud_panel.offset_bottom = hud_panel.offset_top + HUD_HEIGHT
	controls_panel.offset_left = safe_insets.x + UI_EDGE_MARGIN
	controls_panel.offset_top = -(safe_insets.w + UI_EDGE_MARGIN + CONTROLS_HEIGHT)
	controls_panel.offset_right = -(safe_insets.z + UI_EDGE_MARGIN)
	controls_panel.offset_bottom = -(safe_insets.w + UI_EDGE_MARGIN)


func _update_next_preview() -> void:
	if _next_tier < 1 or _next_tier > TIER_RADIUS_RATIOS.size():
		return
	var tier_index := _next_tier - 1
	var radius: float = _chamber_rect.size.x * TIER_RADIUS_RATIOS[tier_index]
	var ingredient_texture: Texture2D = (
		PIECE_VISUAL_SCRIPT.ingredient_texture_for_tier(_next_tier)
	)
	var preview_diameter := ceilf(
		radius
		* PIECE_VISUAL_SCRIPT.ingredient_diameter_scale_for_tier(_next_tier)
	)
	next_preview.custom_minimum_size = Vector2(preview_diameter, preview_diameter)
	next_preview_ingredient.texture = ingredient_texture
	next_preview_ingredient.visible = ingredient_texture != null
	_next_preview_style.bg_color = (
		Color.TRANSPARENT if ingredient_texture != null else TIER_COLORS[tier_index]
	)
	var corner_radius := ceili(radius)
	_next_preview_style.corner_radius_top_left = corner_radius
	_next_preview_style.corner_radius_top_right = corner_radius
	_next_preview_style.corner_radius_bottom_left = corner_radius
	_next_preview_style.corner_radius_bottom_right = corner_radius


func _drop_piece(viewport_x: float) -> void:
	if game_over or _chamber_rect.size == Vector2.ZERO:
		return

	var tier_index := _next_tier - 1
	var radius: float = _chamber_rect.size.x * TIER_RADIUS_RATIOS[tier_index]
	var inner_left := _chamber_rect.position.x + _wall_thickness * 0.5
	var inner_right := _chamber_rect.end.x - _wall_thickness * 0.5
	var drop_x := clampf(viewport_x, inner_left + radius, inner_right - radius)
	var drop_y := _chamber_rect.position.y + radius + _wall_thickness * 0.5

	presentation.show_throw()
	var spawned_piece := _spawn_piece(_next_tier, Vector2(drop_x, drop_y))
	_next_tier = _roll_tier()
	_update_debug_ui()
	_register_creation(
		spawned_piece.tier,
		spawned_piece.global_position,
		spawned_piece.radius,
		false
	)


func _spawn_piece(
	tier: int,
	spawn_position: Vector2,
	initial_linear_velocity: Vector2 = Vector2.ZERO,
	initial_angular_velocity: float = 0.0,
	initial_rotation: float = 0.0
) -> PrototypePiece:
	var tier_index := tier - 1
	var piece := PIECE_SCENE.instantiate() as PrototypePiece
	piece.configure(
		tier,
		_chamber_rect.size.x * TIER_RADIUS_RATIOS[tier_index],
		TIER_MASSES[tier_index],
		TIER_COLORS[tier_index]
	)
	piece.position = pieces.to_local(spawn_position)
	piece.rotation = initial_rotation
	piece.linear_velocity = initial_linear_velocity
	piece.angular_velocity = initial_angular_velocity
	piece.body_entered.connect(_on_piece_body_entered.bind(piece))
	pieces.add_child(piece)
	piece.sleeping = false
	return piece


func _on_piece_body_entered(other_body: Node, source_piece: PrototypePiece) -> void:
	if game_over:
		return
	if not is_instance_valid(source_piece) or source_piece.merge_pending:
		return
	if not other_body is PrototypePiece:
		return

	var other_piece := other_body as PrototypePiece
	if source_piece == other_piece or other_piece.merge_pending:
		return
	if source_piece.get_parent() != pieces or other_piece.get_parent() != pieces:
		return
	if source_piece.tier != other_piece.tier:
		return
	if source_piece.tier >= TIER_RADIUS_RATIOS.size():
		return

	_queue_merge_pair(source_piece, other_piece)


func _queue_merge_pair(first_piece: PrototypePiece, second_piece: PrototypePiece) -> void:
	first_piece.merge_pending = true
	second_piece.merge_pending = true
	_queued_merge_pairs.append([first_piece, second_piece])
	_try_resolve_next_merge()


func _try_resolve_next_merge() -> void:
	if game_over or _merge_resolution_pending or _merge_cooldown_remaining > 0.0:
		return

	while not _queued_merge_pairs.is_empty():
		var pair: Array = _queued_merge_pairs.pop_front()
		var first_piece := pair[0] as PrototypePiece
		var second_piece := pair[1] as PrototypePiece
		if not _is_valid_merge_pair(first_piece, second_piece):
			_release_merge_pair(first_piece, second_piece)
			continue

		_merge_resolution_pending = true
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
			first_piece.tier + 1,
			result_position,
			result_linear_velocity,
			result_angular_velocity,
			result_rotation
		)
		return


func _is_valid_merge_pair(
	first_piece: PrototypePiece,
	second_piece: PrototypePiece
) -> bool:
	return (
		_is_active_merge_source(first_piece)
		and _is_active_merge_source(second_piece)
		and first_piece != second_piece
		and first_piece.tier == second_piece.tier
		and first_piece.tier < TIER_RADIUS_RATIOS.size()
	)


func _release_merge_pair(
	first_piece: PrototypePiece,
	second_piece: PrototypePiece
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
	result_tier: int,
	result_position: Vector2,
	result_linear_velocity: Vector2,
	result_angular_velocity: float,
	result_rotation: float
) -> void:
	if game_over:
		_merge_resolution_pending = false
		return
	if not _is_valid_merge_pair(first_piece, second_piece):
		_merge_resolution_pending = false
		_release_merge_pair(first_piece, second_piece)
		_try_resolve_next_merge()
		return
	if first_piece.tier + 1 != result_tier:
		_merge_resolution_pending = false
		_release_merge_pair(first_piece, second_piece)
		_try_resolve_next_merge()
		return

	var result_radius: float = (
		_chamber_rect.size.x * TIER_RADIUS_RATIOS[result_tier - 1]
	)
	var safe_result_position := _find_safe_merge_position(
		result_position,
		result_radius,
		first_piece,
		second_piece
	)
	first_piece.queue_free()
	second_piece.queue_free()
	var result_piece := _spawn_piece(
		result_tier,
		safe_result_position,
		result_linear_velocity,
		result_angular_velocity,
		result_rotation
	)
	_apply_merge_expansion(result_piece)
	presentation.show_merge(
		safe_result_position,
		minf(result_radius * 3.0, _chamber_rect.size.x * 0.45)
	)
	_merge_cooldown_remaining = MERGE_RESOLUTION_COOLDOWN_SECONDS
	_merge_resolution_pending = false
	score += result_tier * result_tier * 2
	pulse_charge = mini(MAX_PULSE_CHARGE, pulse_charge + PULSE_CHARGE_PER_MERGE)
	if result_tier == TIER_RADIUS_RATIOS.size():
		_max_merge_feedback_timer = MAX_MERGE_FEEDBACK_SECONDS
		max_merge_feedback_label.visible = true
	_update_debug_ui()
	_register_creation(
		result_tier,
		safe_result_position,
		result_radius,
		true
	)


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
			_chamber_rect.position.x + wall_inset + result_radius,
			_chamber_rect.end.x - wall_inset - result_radius
		),
		clampf(
			position.y,
			_chamber_rect.position.y + wall_inset + result_radius,
			_chamber_rect.end.y - wall_inset - result_radius
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


func _is_active_merge_source(piece: PrototypePiece) -> bool:
	return (
		is_instance_valid(piece)
		and not piece.is_queued_for_deletion()
		and piece.get_parent() == pieces
		and piece.merge_pending
	)


func _roll_tier() -> int:
	var roll := _rng.randf()
	if roll < 0.50:
		return 1
	if roll < 0.85:
		return 2
	return 3


func _register_creation(
	tier: int,
	world_position: Vector2,
	radius: float,
	visual_feedback_already_playing: bool
) -> bool:
	if tier < 1 or tier > TIER_NAME_KEYS.size():
		return false
	highest_creation_reached = maxi(highest_creation_reached, tier)
	if discovered_creation_tiers.has(tier):
		return false

	discovered_creation_tiers.append(tier)
	discovered_creation_tiers.sort()
	_new_discoveries_this_run.append(tier)
	_save_recipe_discoveries()
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
	discovered_creation_tiers.clear()
	var save_file := ConfigFile.new()
	var load_error := save_file.load(_discovery_save_path)
	if load_error == ERR_FILE_NOT_FOUND:
		return
	if load_error != OK:
		push_warning("Could not load recipe discoveries: error %d" % load_error)
		return

	var stored_tiers: Variant = save_file.get_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_KEY,
		[]
	)
	if not (stored_tiers is Array or stored_tiers is PackedInt32Array):
		return
	for stored_tier in stored_tiers:
		var tier := int(stored_tier)
		if (
			tier >= 1
			and tier <= TIER_NAME_KEYS.size()
			and not discovered_creation_tiers.has(tier)
		):
			discovered_creation_tiers.append(tier)
	discovered_creation_tiers.sort()


func _save_recipe_discoveries() -> void:
	var save_file := ConfigFile.new()
	save_file.set_value(
		DISCOVERY_SAVE_SECTION,
		DISCOVERY_SAVE_KEY,
		discovered_creation_tiers.duplicate()
	)
	var save_error := save_file.save(_discovery_save_path)
	if save_error != OK:
		push_warning("Could not save recipe discoveries: error %d" % save_error)


func _tier_display_name(tier: int) -> String:
	if tier < 1 or tier > TIER_NAME_KEYS.size():
		return ""
	return tr(TIER_NAME_KEYS[tier - 1])


func _show_run_result() -> void:
	if highest_creation_reached <= 0:
		run_result_label.visible = false
		return
	var result_lines := PackedStringArray([
		tr("RESULT_HIGHEST_CREATION") % _tier_display_name(highest_creation_reached),
	])
	if not _new_discoveries_this_run.is_empty():
		var highest_new_tier := 1
		for discovered_tier in _new_discoveries_this_run:
			highest_new_tier = maxi(highest_new_tier, discovered_tier)
		result_lines.append(
			tr("RESULT_NEW_RECIPE") % _tier_display_name(highest_new_tier)
		)
	run_result_label.text = "\n".join(result_lines)
	run_result_label.visible = true
	presentation.show_result()


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
			bottom_edge <= _danger_line_y
			and absf(piece.linear_velocity.y) <= DANGER_VERTICAL_SPEED_THRESHOLD
			and is_supported
		):
			return true
	return false


func _enter_game_over() -> void:
	game_over = true
	danger_active = true
	danger_timer = DANGER_GRACE_SECONDS
	game_over_label.visible = true
	for child in pieces.get_children():
		if child is PrototypePiece:
			child.set_deferred("freeze", true)
	_show_run_result()
	queue_redraw()


func _activate_pulse(direction: Vector2) -> void:
	if game_over or pulse_charge < MAX_PULSE_CHARGE:
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


func _restart_sandbox() -> void:
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
	highest_creation_reached = 0
	presentation.reset()
	pulse_feedback_label.visible = false
	max_merge_feedback_label.visible = false
	new_creation_feedback_label.visible = false
	game_over_label.visible = false
	run_result_label.visible = false
	_rng.seed = INITIAL_SEED
	_next_tier = _roll_tier()
	queue_redraw()
	_update_debug_ui()


func _update_debug_ui() -> void:
	_update_next_preview()
	score_label.text = "Score: %d" % score
	pulse_label.text = "Pulse: %d%%" % pulse_charge
	danger_label.visible = danger_active
	var pulse_available := pulse_charge >= MAX_PULSE_CHARGE and not game_over
	pulse_left_button.disabled = not pulse_available
	pulse_right_button.disabled = not pulse_available
