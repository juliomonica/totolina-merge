class_name PrototypePieceVisual
extends Node2D

const INGREDIENT_TEXTURES: Array[Texture2D] = [
	preload("res://assets/ingredients/strawberry.png"),
	preload("res://assets/ingredients/milk.png"),
	preload("res://assets/ingredients/cookie.png"),
]
const INGREDIENT_DIAMETER_SCALE := 1.84

var _radius := 24.0
var _fallback_color := Color("79c7ff")
var _uses_ingredient := false


static func ingredient_texture_for_tier(tier: int) -> Texture2D:
	if tier < 1 or tier > INGREDIENT_TEXTURES.size():
		return null
	return INGREDIENT_TEXTURES[tier - 1]


func configure(tier: int, radius: float, fallback_color: Color) -> void:
	_radius = radius
	_fallback_color = fallback_color
	var ingredient_sprite := $IngredientSprite as Sprite2D
	var ingredient_texture := ingredient_texture_for_tier(tier)
	ingredient_sprite.texture = ingredient_texture
	ingredient_sprite.visible = ingredient_texture != null
	_uses_ingredient = ingredient_texture != null
	if ingredient_texture != null:
		var texture_size := ingredient_texture.get_size()
		var texture_extent := maxf(texture_size.x, texture_size.y)
		var visual_scale := radius * INGREDIENT_DIAMETER_SCALE / texture_extent
		ingredient_sprite.scale = Vector2.ONE * visual_scale
	queue_redraw()


func _draw() -> void:
	if _uses_ingredient:
		return
	draw_circle(Vector2.ZERO, _radius, _fallback_color)
	draw_arc(
		Vector2.ZERO,
		_radius,
		0.0,
		TAU,
		48,
		_fallback_color.lightened(0.35),
		2.0
	)
	draw_line(
		Vector2.ZERO,
		Vector2(_radius * 0.72, 0.0),
		_fallback_color.darkened(0.35),
		2.0
	)
