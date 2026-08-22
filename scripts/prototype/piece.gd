class_name PrototypePiece
extends RigidBody2D

var tier: int = 1
var radius: float = 24.0
var debug_color := Color("79c7ff")
var merge_pending := false


func configure(
	new_tier: int,
	new_radius: float,
	new_mass: float,
	new_color: Color
) -> void:
	tier = new_tier
	radius = new_radius
	mass = new_mass
	debug_color = new_color

	var circle_shape := CircleShape2D.new()
	circle_shape.radius = radius
	$CollisionShape2D.shape = circle_shape
	$Visual.configure(tier, radius, debug_color)
