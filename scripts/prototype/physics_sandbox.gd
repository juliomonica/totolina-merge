extends Node2D

const PIECE_SCENE := preload("res://scenes/prototype/piece.tscn")
const INITIAL_SEED := 12345
const CHAMBER_WIDTH_RATIO := 0.86
const CHAMBER_HEIGHT_RATIO := 0.72
const CHAMBER_TOP_RATIO := 0.17
const CHAMBER_MAX_ASPECT_RATIO := 0.67
const DANGER_LINE_CHAMBER_RATIO := 0.30
const DANGER_GRACE_SECONDS := 3.0
const DANGER_VERTICAL_SPEED_THRESHOLD := 10.0
const NORMAL_SPAWN_MAX_TIER := 3
const TIER_RADIUS_RATIOS := [
	0.0460,
	0.0538,
	0.0630,
	0.0737,
	0.0862,
	0.1009,
	0.1180,
	0.1381,
	0.1615,
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

@onready var pieces: Node2D = $Pieces
@onready var left_wall: StaticBody2D = $Chamber/LeftWall
@onready var right_wall: StaticBody2D = $Chamber/RightWall
@onready var floor: StaticBody2D = $Chamber/Floor
@onready var seed_label: Label = $DebugUI/Panel/Margin/Row/Seed
@onready var body_count_label: Label = $DebugUI/Panel/Margin/Row/BodyCount
@onready var next_tier_label: Label = $DebugUI/Panel/Margin/Row/NextTier
@onready var fps_label: Label = $DebugUI/Panel/Margin/Row/FPS
@onready var restart_button: Button = $DebugUI/Panel/Margin/Row/Restart
@onready var game_over_label: Label = $DebugUI/GameOver

var _rng := RandomNumberGenerator.new()
var _next_tier := 1
var _chamber_rect := Rect2()
var _wall_thickness := 0.0
var _danger_line_y := 0.0

var danger_active := false
var danger_timer := 0.0
var game_over := false


func _ready() -> void:
	Engine.physics_ticks_per_second = 60
	_rng.seed = INITIAL_SEED
	_next_tier = _roll_tier()
	restart_button.pressed.connect(_restart_sandbox)
	get_viewport().size_changed.connect(_layout_chamber)
	_layout_chamber()
	_update_debug_ui()


func _process(_delta: float) -> void:
	_update_debug_ui()


func _physics_process(delta: float) -> void:
	if game_over:
		return

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

	draw_rect(_chamber_rect, Color("101722"), true)
	var wall_color := Color("7f8fa6")
	draw_rect(
		Rect2(
			Vector2(
				_chamber_rect.position.x - _wall_thickness * 0.5,
				_chamber_rect.position.y - _wall_thickness * 0.5
			),
			Vector2(_wall_thickness, _chamber_rect.size.y + _wall_thickness)
		),
		wall_color,
		true
	)
	var danger_line_color := Color("ff3b30") if danger_active else Color("ffb020")
	draw_line(
		Vector2(_chamber_rect.position.x, _danger_line_y),
		Vector2(_chamber_rect.end.x, _danger_line_y),
		danger_line_color,
		3.0
	)
	draw_rect(
		Rect2(
			Vector2(
				_chamber_rect.end.x - _wall_thickness * 0.5,
				_chamber_rect.position.y - _wall_thickness * 0.5
			),
			Vector2(_wall_thickness, _chamber_rect.size.y + _wall_thickness)
		),
		wall_color,
		true
	)
	draw_rect(
		Rect2(
			Vector2(
				_chamber_rect.position.x - _wall_thickness * 0.5,
				_chamber_rect.end.y - _wall_thickness * 0.5
			),
			Vector2(_chamber_rect.size.x + _wall_thickness, _wall_thickness)
		),
		wall_color,
		true
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
	queue_redraw()


func _drop_piece(viewport_x: float) -> void:
	if game_over or _chamber_rect.size == Vector2.ZERO:
		return

	var tier_index := _next_tier - 1
	var radius: float = _chamber_rect.size.x * TIER_RADIUS_RATIOS[tier_index]
	var inner_left := _chamber_rect.position.x + _wall_thickness * 0.5
	var inner_right := _chamber_rect.end.x - _wall_thickness * 0.5
	var drop_x := clampf(viewport_x, inner_left + radius, inner_right - radius)
	var drop_y := _chamber_rect.position.y + radius + _wall_thickness * 0.5

	_spawn_piece(_next_tier, Vector2(drop_x, drop_y))
	_next_tier = _roll_tier()
	_update_debug_ui()


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

	source_piece.merge_pending = true
	other_piece.merge_pending = true
	var result_position := (source_piece.global_position + other_piece.global_position) * 0.5
	var result_linear_velocity := (
		source_piece.linear_velocity + other_piece.linear_velocity
	) * 0.5
	var result_angular_velocity := (
		source_piece.angular_velocity + other_piece.angular_velocity
	) * 0.5
	var result_rotation := lerp_angle(
		source_piece.global_rotation,
		other_piece.global_rotation,
		0.5
	)
	call_deferred(
		"_resolve_merge",
		source_piece,
		other_piece,
		source_piece.tier + 1,
		result_position,
		result_linear_velocity,
		result_angular_velocity,
		result_rotation
	)


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
		return
	if not _is_active_merge_source(first_piece):
		return
	if not _is_active_merge_source(second_piece):
		return
	if first_piece.tier + 1 != result_tier or second_piece.tier + 1 != result_tier:
		return

	first_piece.queue_free()
	second_piece.queue_free()
	_spawn_piece(
		result_tier,
		result_position,
		result_linear_velocity,
		result_angular_velocity,
		result_rotation
	)
	_update_debug_ui()


func _is_active_merge_source(piece: PrototypePiece) -> bool:
	return (
		is_instance_valid(piece)
		and not piece.is_queued_for_deletion()
		and piece.get_parent() == pieces
		and piece.merge_pending
	)


func _roll_tier() -> int:
	return _rng.randi_range(1, NORMAL_SPAWN_MAX_TIER)


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
	queue_redraw()


func _restart_sandbox() -> void:
	for piece in pieces.get_children():
		piece.queue_free()

	danger_active = false
	danger_timer = 0.0
	game_over = false
	game_over_label.visible = false
	_rng.seed = INITIAL_SEED
	_next_tier = _roll_tier()
	queue_redraw()
	_update_debug_ui()


func _update_debug_ui() -> void:
	seed_label.text = "Seed: %d" % INITIAL_SEED
	body_count_label.text = "Bodies: %d" % pieces.get_child_count()
	next_tier_label.text = "Next: T%d" % _next_tier
	fps_label.text = "FPS: %d" % Engine.get_frames_per_second()
