extends Node2D

const PIECE_SCENE := preload("res://scenes/prototype/piece.tscn")
const INITIAL_SEED := 12345
const CHAMBER_WIDTH_RATIO := 0.86
const CHAMBER_HEIGHT_RATIO := 0.72
const CHAMBER_TOP_RATIO := 0.17
const CHAMBER_MAX_ASPECT_RATIO := 0.67
const TIER_RADIUS_RATIOS := [0.046, 0.0538, 0.0630]
const TIER_MASSES := [1.0, 1.30, 1.69]
const TIER_COLORS := [
	Color("79c7ff"),
	Color("ffc857"),
	Color("ff7b89"),
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

var _rng := RandomNumberGenerator.new()
var _next_tier := 1
var _chamber_rect := Rect2()
var _wall_thickness := 0.0


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
	if _chamber_rect.size == Vector2.ZERO:
		return

	var tier_index := _next_tier - 1
	var radius: float = _chamber_rect.size.x * TIER_RADIUS_RATIOS[tier_index]
	var inner_left := _chamber_rect.position.x + _wall_thickness * 0.5
	var inner_right := _chamber_rect.end.x - _wall_thickness * 0.5
	var drop_x := clampf(viewport_x, inner_left + radius, inner_right - radius)
	var drop_y := _chamber_rect.position.y + radius + _wall_thickness * 0.5

	var piece := PIECE_SCENE.instantiate() as PrototypePiece
	piece.configure(
		_next_tier,
		radius,
		TIER_MASSES[tier_index],
		TIER_COLORS[tier_index]
	)
	piece.position = Vector2(drop_x, drop_y)
	pieces.add_child(piece)
	piece.sleeping = false

	_next_tier = _roll_tier()
	_update_debug_ui()


func _roll_tier() -> int:
	return _rng.randi_range(1, TIER_RADIUS_RATIOS.size())


func _restart_sandbox() -> void:
	for piece in pieces.get_children():
		piece.queue_free()

	_rng.seed = INITIAL_SEED
	_next_tier = _roll_tier()
	_update_debug_ui()


func _update_debug_ui() -> void:
	seed_label.text = "Seed: %d" % INITIAL_SEED
	body_count_label.text = "Bodies: %d" % pieces.get_child_count()
	next_tier_label.text = "Next: T%d" % _next_tier
	fps_label.text = "FPS: %d" % Engine.get_frames_per_second()
