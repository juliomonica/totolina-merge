class_name MergeRecipe
extends Resource

@export var input_a: StringName
@export var input_b: StringName
@export var result: StringName
# Optional name in the shared approved flavor component; no gameplay timing.
@export var effect_animation: StringName


func matches(first_id: StringName, second_id: StringName) -> bool:
	return (
		(first_id == input_a and second_id == input_b)
		or (first_id == input_b and second_id == input_a)
	)
