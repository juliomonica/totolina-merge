class_name PrototypeSandboxPresentation
extends Node2D

const GAMEPLAY_CONFIG := preload("res://scripts/config/gameplay_configuration.gd")
const TOLINA_IDLE := preload("res://assets/worlds/kitchen/characters/tolinа_idle.png")
const TOLINA_HAPPY := preload("res://assets/worlds/kitchen/characters/tolinа_happy.png")
const TOLINA_THROW := preload("res://assets/worlds/kitchen/characters/tolinа_throw.png")
const MERGE_MAGIC := preload("res://assets/worlds/kitchen/effects/merge_magic.png")
const THROW_POSE_SECONDS := 0.35
const HAPPY_POSE_SECONDS := 0.75
const RESULT_POSE_SECONDS := 1.5
const MERGE_EFFECT_SECONDS := 0.45

@onready var bowl: Sprite2D = get_node("../KitchenBowl")
@onready var tolina: TextureRect = get_node("../DebugUI/Tolina")
@onready var pieces: Node2D = get_node("../Pieces")
@onready var merge_effects: Node2D = $MergeEffects

var _pose_timer := 0.0
var _visual_left_bound := 0.0
var _visual_right_bound := 0.0
var _physics_floor_y := 0.0
var _visual_floor_contact_y := 0.0


func _ready() -> void:
	_set_tolina_pose(TOLINA_IDLE, 0.0)


func _process(delta: float) -> void:
	if _pose_timer > 0.0:
		_pose_timer = maxf(0.0, _pose_timer - delta)
		if is_zero_approx(_pose_timer):
			_set_tolina_pose(TOLINA_IDLE, 0.0)
	_contain_piece_visuals()


func layout(chamber_rect: Rect2, physics_floor_y: float) -> void:
	if bowl.texture == null:
		return
	var bowl_texture_size := bowl.texture.get_size()
	if bowl_texture_size.x <= 0.0 or bowl_texture_size.y <= 0.0:
		return
	var viewport_size := get_viewport_rect().size
	var viewport_width := viewport_size.x
	_visual_left_bound = (
		viewport_width
		* GAMEPLAY_CONFIG.INGREDIENT_VISUAL_SIDE_INSET_VIEWPORT_RATIO
	)
	_visual_right_bound = viewport_width - _visual_left_bound
	_physics_floor_y = physics_floor_y
	_visual_floor_contact_y = (
		_physics_floor_y
		- chamber_rect.size.x
			* GAMEPLAY_CONFIG.INGREDIENT_FLOOR_CONTACT_CHAMBER_WIDTH_RATIO
	)
	var responsive_width := (
		viewport_width
		* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_WIDTH_VIEWPORT_RATIO
	)
	var minimum_vertical_scale := (
		chamber_rect.size.x
		* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_MIN_HEIGHT_CHAMBER_WIDTH_RATIO
		/ bowl_texture_size.x
	)
	var maximum_vertical_scale := (
		chamber_rect.size.x
		* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_MAX_HEIGHT_CHAMBER_WIDTH_RATIO
		/ bowl_texture_size.x
	)
	var target_bowl_top := (
		viewport_size.y
			* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_TOP_VIEWPORT_HEIGHT_RATIO
		+ chamber_rect.size.x
			* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_TOP_GAP_CHAMBER_WIDTH_RATIO
	)
	var target_vertical_scale := (
		(_physics_floor_y - target_bowl_top)
		/ (
			bowl_texture_size.y
			* GAMEPLAY_CONFIG.BOWL_FLOOR_TEXTURE_Y_RATIO
		)
	)
	var responsive_vertical_scale := clampf(
		target_vertical_scale,
		minimum_vertical_scale,
		maximum_vertical_scale
	)
	var responsive_size := Vector2(
		responsive_width,
		bowl_texture_size.y * responsive_vertical_scale
	)
	var bowl_size := responsive_size
	var bowl_offset := Vector2.ZERO
	if GAMEPLAY_CONFIG.BOWL_MATCH_CHAMBER_SIZE:
		bowl_size = (
			chamber_rect.size * GAMEPLAY_CONFIG.BOWL_CHAMBER_MATCH_SCALE
		)
	else:
		var manual_size: Vector2 = GAMEPLAY_CONFIG.BOWL_MANUAL_SIZE_PIXELS
		if manual_size.x > 0.0:
			bowl_size.x = manual_size.x
		if manual_size.y > 0.0:
			bowl_size.y = manual_size.y
		bowl_size *= GAMEPLAY_CONFIG.BOWL_MANUAL_SCALE
		bowl_offset = GAMEPLAY_CONFIG.BOWL_MANUAL_OFFSET_PIXELS
	bowl.scale = bowl_size / bowl_texture_size
	var floor_offset_from_center := (
		(GAMEPLAY_CONFIG.BOWL_FLOOR_TEXTURE_Y_RATIO - 0.5)
		* bowl_texture_size.y
		* bowl.scale.y
	)
	bowl.position = Vector2(
		chamber_rect.get_center().x,
		_physics_floor_y
			+ GAMEPLAY_CONFIG.BOWL_VISUAL_FLOOR_OFFSET_PIXELS
			- floor_offset_from_center
	) + bowl_offset


func _contain_piece_visuals() -> void:
	if _visual_right_bound <= _visual_left_bound:
		return
	for child in pieces.get_children():
		if not child is PrototypePiece:
			continue
		var piece := child as PrototypePiece
		if piece.is_queued_for_deletion():
			continue
		var visual := piece.get_node("Visual") as Node2D
		var ingredient := visual.get_node("IngredientSprite") as Sprite2D
		visual.position = GAMEPLAY_CONFIG.INGREDIENT_VISUAL_OFFSET_PIXELS
		if not ingredient.visible or ingredient.texture == null:
			continue
		var floor_distance := absf(
			piece.global_position.y + piece.radius - _physics_floor_y
		)
		var floor_tolerance := maxf(
			GAMEPLAY_CONFIG.INGREDIENT_FLOOR_BODY_TOLERANCE_PIXELS,
			piece.radius * 0.08
		)
		if floor_distance <= floor_tolerance:
			var diameter_scale := (
				PrototypePieceVisual.ingredient_diameter_scale_for_tier(piece.tier)
			)
			var rotation_reduction := (
				GAMEPLAY_CONFIG.INGREDIENT_ROTATED_SUPPORT_REDUCTION
				* absf(sin(piece.global_rotation * 2.0))
			)
			var visual_support := (
				piece.radius
				* maxf(
					0.0,
					diameter_scale
						* GAMEPLAY_CONFIG.INGREDIENT_GLOBAL_VISUAL_SCALE
						* 0.5
						- rotation_reduction
				)
			)
			var target_visual_center_y := (
				_visual_floor_contact_y - visual_support
			)
			visual.global_position += Vector2(
				0.0,
				target_visual_center_y - piece.global_position.y
			)
		var visual_rect := _global_sprite_rect(ingredient)
		var horizontal_offset := 0.0
		if visual_rect.position.x < _visual_left_bound:
			horizontal_offset = _visual_left_bound - visual_rect.position.x
		elif visual_rect.end.x > _visual_right_bound:
			horizontal_offset = _visual_right_bound - visual_rect.end.x
		if not is_zero_approx(horizontal_offset):
			visual.global_position += Vector2(horizontal_offset, 0.0)


func _global_sprite_rect(sprite: Sprite2D) -> Rect2:
	var local_rect := sprite.get_rect()
	var sprite_transform := sprite.get_global_transform()
	var corners: Array[Vector2] = [
		sprite_transform * local_rect.position,
		sprite_transform * Vector2(local_rect.end.x, local_rect.position.y),
		sprite_transform * local_rect.end,
		sprite_transform * Vector2(local_rect.position.x, local_rect.end.y),
	]
	var global_rect := Rect2(corners[0], Vector2.ZERO)
	for corner in corners.slice(1):
		global_rect = global_rect.expand(corner)
	return global_rect


func show_throw() -> void:
	_set_tolina_pose(TOLINA_THROW, THROW_POSE_SECONDS)


func show_merge(world_position: Vector2, effect_diameter: float) -> void:
	_set_tolina_pose(TOLINA_HAPPY, HAPPY_POSE_SECONDS)
	var effect := Sprite2D.new()
	effect.texture = MERGE_MAGIC
	effect.global_position = world_position
	effect.z_index = 1
	var texture_extent := maxf(MERGE_MAGIC.get_width(), MERGE_MAGIC.get_height())
	var target_scale := effect_diameter / texture_extent
	effect.scale = Vector2.ONE * target_scale * 0.65
	merge_effects.add_child(effect)
	var tween := effect.create_tween()
	tween.set_parallel(true)
	tween.tween_property(
		effect,
		"scale",
		Vector2.ONE * target_scale,
		MERGE_EFFECT_SECONDS
	).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(
		effect,
		"modulate:a",
		0.0,
		MERGE_EFFECT_SECONDS
	).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tween.chain().tween_callback(effect.queue_free)


func show_discovery(world_position: Vector2, effect_diameter: float) -> void:
	show_merge(world_position, effect_diameter)


func show_result() -> void:
	_set_tolina_pose(TOLINA_HAPPY, RESULT_POSE_SECONDS)


func reset() -> void:
	_set_tolina_pose(TOLINA_IDLE, 0.0)
	for effect in merge_effects.get_children():
		effect.queue_free()


func _set_tolina_pose(texture: Texture2D, duration: float) -> void:
	_pose_timer = duration
	tolina.texture = texture
