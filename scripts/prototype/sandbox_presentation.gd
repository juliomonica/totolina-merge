class_name PrototypeSandboxPresentation
extends Node2D

const GAMEPLAY_CONFIG := preload("res://scripts/config/gameplay_configuration.gd")
const TOLINA_IDLE := preload("res://assets/worlds/kitchen/characters/tolinа_idle.png")
const TOLINA_HAPPY := preload("res://assets/worlds/kitchen/characters/tolinа_happy.png")
const TOLINA_THROW := preload("res://assets/worlds/kitchen/characters/tolinа_throw.png")
const MERGE_MAGIC := preload("res://assets/worlds/kitchen/effects/merge_magic.png")
const MERGE_FLAVOR := preload("res://scripts/presentation/merge_flavor_effect.gd")
const THROW_POSE_SECONDS := 0.35
const HAPPY_POSE_SECONDS := 0.75
const RESULT_POSE_SECONDS := 1.5
const MERGE_EFFECT_SECONDS := 0.45

@onready var bowl: Sprite2D = get_node("../KitchenBowl")
@onready var tolina: TextureRect = get_node("../DebugUI/Tolina")
@onready var merge_effects: Node2D = $MergeEffects

var _pose_timer := 0.0


func _ready() -> void:
	_set_tolina_pose(TOLINA_IDLE, 0.0)


func _process(delta: float) -> void:
	if _pose_timer > 0.0:
		_pose_timer = maxf(0.0, _pose_timer - delta)
		if is_zero_approx(_pose_timer):
			_set_tolina_pose(TOLINA_IDLE, 0.0)


func layout(
	chamber_rect: Rect2,
	physics_floor_y: float,
	danger_threshold_y: float
) -> void:
	if bowl.texture == null:
		return
	var bowl_texture_size := bowl.texture.get_size()
	if bowl_texture_size.x <= 0.0 or bowl_texture_size.y <= 0.0:
		return
	var viewport_size := get_viewport_rect().size
	var viewport_width := viewport_size.x
	var responsive_width := (
		viewport_width
		* GAMEPLAY_CONFIG.BOWL_RESPONSIVE_WIDTH_VIEWPORT_RATIO
	)
	var target_bowl_top := (
		danger_threshold_y
		+ chamber_rect.size.x
			* GAMEPLAY_CONFIG.DANGER_TO_BOWL_TOP_GAP_CHAMBER_WIDTH_RATIO
	)
	var target_vertical_scale := (
		(physics_floor_y - target_bowl_top)
		/ (
			bowl_texture_size.y
			* GAMEPLAY_CONFIG.BOWL_FLOOR_TEXTURE_Y_RATIO
		)
	)
	var responsive_vertical_scale := maxf(target_vertical_scale, 0.001)
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
		physics_floor_y
			+ GAMEPLAY_CONFIG.BOWL_VISUAL_FLOOR_OFFSET_PIXELS
			- floor_offset_from_center
	) + bowl_offset


func show_throw() -> void:
	_set_tolina_pose(TOLINA_THROW, THROW_POSE_SECONDS)


func show_recipe_merge(recipe: MergeRecipe, world_position: Vector2, effect_diameter: float) -> void:
	var animation := MERGE_FLAVOR.EFFECT_NAMES.find(recipe.effect_animation) if recipe != null else -1
	if animation < 0:
		show_merge(world_position, effect_diameter)
		return
	_set_tolina_pose(TOLINA_HAPPY, HAPPY_POSE_SECONDS)
	var effect := MERGE_FLAVOR.new()
	effect.name = "MergeFlavor"
	effect.set_meta("recipe_result", recipe.result)
	effect.z_index = 2
	merge_effects.add_child(effect)
	effect.build([animation])
	if not effect.assets_ok:
		effect.queue_free()
		show_merge(world_position, effect_diameter)
		return
	effect.global_position = world_position
	# Existing CanvasLayer HUD stays above world-space effects. Never shift an
	# effect away from its real merge anchor just to accommodate screen edges.
	var area := get_viewport_rect().grow(-4.0)
	var diameter := clampf(effect_diameter, 80.0, minf(140.0, get_viewport_rect().size.x * 0.35))
	effect.scale = Vector2.ONE * effect.fit_scale(animation, world_position, area, diameter)
	# The real result stays visible/physical throughout. Completion only frees
	# this disposable overlay; never owns result/reward/discovery authority.
	effect.finished.connect(effect.queue_free)
	effect.play(animation)




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
