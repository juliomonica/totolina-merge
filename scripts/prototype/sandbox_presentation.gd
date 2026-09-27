class_name PrototypeSandboxPresentation
extends Node2D

# Character reactions belong to the current Kitchen machine presentation.
# Merge/discovery effects must not depend on the retired static Tolina poses.
const MERGE_MAGIC := preload("res://assets/worlds/kitchen/effects/merge_magic.png")
const MERGE_FLAVOR := preload("res://scripts/presentation/merge_flavor_effect.gd")
const MERGE_EFFECT_SECONDS := 0.45

@onready var merge_effects: Node2D = $MergeEffects

func show_recipe_merge(recipe: MergeRecipe, world_position: Vector2, effect_diameter: float) -> void:
	var animation := MERGE_FLAVOR.EFFECT_NAMES.find(recipe.effect_animation) if recipe != null else -1
	if animation < 0:
		show_merge(world_position, effect_diameter)
		return
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


func reset() -> void:
	for effect in merge_effects.get_children():
		effect.queue_free()
