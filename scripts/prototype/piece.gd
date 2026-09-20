class_name PrototypePiece
extends RigidBody2D

var definition: CreationDefinition
var creation_id: StringName
var radius := 24.0
var merge_pending := false
var spawn_sequence := 0


func configure(
	new_definition: CreationDefinition,
	new_radius: float
) -> void:
	definition = new_definition
	creation_id = definition.id
	radius = new_radius
	mass = definition.mass

	var circle_shape := CircleShape2D.new()
	circle_shape.radius = radius
	$CollisionShape2D.shape = circle_shape
	$Visual.configure(definition, radius)
