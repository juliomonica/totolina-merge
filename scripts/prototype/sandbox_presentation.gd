class_name PrototypeSandboxPresentation
extends Node2D

const TOLINA_IDLE := preload("res://assets/cat_kitchen/tolinа_idle.png")
const TOLINA_HAPPY := preload("res://assets/cat_kitchen/tolinа_happy.png")
const TOLINA_THROW := preload("res://assets/cat_kitchen/tolinа_throw.png")
const MERGE_MAGIC := preload("res://assets/effects/merge_magic.png")
const THROW_POSE_SECONDS := 0.35
const HAPPY_POSE_SECONDS := 0.75
const MERGE_EFFECT_SECONDS := 0.45
const BOWL_WIDTH_CHAMBER_RATIO := 1.38
const BOWL_PHYSICS_FLOOR_TEXTURE_Y_RATIO := 0.75

@onready var bowl: Sprite2D = get_node("../KitchenBowl")
@onready var tolina: TextureRect = get_node("../DebugUI/Tolina")
@onready var merge_effects: Node2D = $MergeEffects

var _pose_timer := 0.0


func _ready() -> void:
	_set_tolina_pose(TOLINA_IDLE, 0.0)


func _process(delta: float) -> void:
	if _pose_timer <= 0.0:
		return
	_pose_timer = maxf(0.0, _pose_timer - delta)
	if is_zero_approx(_pose_timer):
		_set_tolina_pose(TOLINA_IDLE, 0.0)


func layout(chamber_rect: Rect2) -> void:
	if bowl.texture == null:
		return
	var bowl_texture_size := bowl.texture.get_size()
	if bowl_texture_size.x <= 0.0 or bowl_texture_size.y <= 0.0:
		return
	var visual_scale := (
		chamber_rect.size.x * BOWL_WIDTH_CHAMBER_RATIO / bowl_texture_size.x
	)
	bowl.scale = Vector2.ONE * visual_scale
	var floor_offset_from_center := (
		(BOWL_PHYSICS_FLOOR_TEXTURE_Y_RATIO - 0.5)
		* bowl_texture_size.y
		* visual_scale
	)
	bowl.position = Vector2(
		chamber_rect.get_center().x,
		chamber_rect.end.y - floor_offset_from_center
	)


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


func reset() -> void:
	_set_tolina_pose(TOLINA_IDLE, 0.0)
	for effect in merge_effects.get_children():
		effect.queue_free()


func _set_tolina_pose(texture: Texture2D, duration: float) -> void:
	_pose_timer = duration
	tolina.texture = texture
