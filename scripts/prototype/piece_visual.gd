class_name PrototypePieceVisual
extends Node2D

const GAMEPLAY_CONFIG := preload("res://scripts/config/gameplay_configuration.gd")

func configure(definition: CreationDefinition, radius: float) -> void:
	position = GAMEPLAY_CONFIG.INGREDIENT_VISUAL_OFFSET_PIXELS
	var sprite: Sprite2D = $IngredientSprite
	sprite.texture = definition.texture
	var texture_size := definition.texture.get_size()
	var texture_extent := maxf(texture_size.x, texture_size.y)
	sprite.scale = Vector2.ONE * radius * definition.visual_diameter_scale \
		* GAMEPLAY_CONFIG.INGREDIENT_GLOBAL_VISUAL_SCALE / texture_extent
