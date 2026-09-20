class_name SpawnStage
extends Resource

# Empty for the opening stage; later stages unlock on a successful merge result.
@export var unlock_creation_id: StringName
# Relative weights, in serialized selection order. Missing entries cannot spawn.
@export var weights: Dictionary[StringName, float] = {}


func select_creation(rng: RandomNumberGenerator) -> StringName:
	var total := 0.0
	for weight in weights.values():
		total += weight
	if total <= 0.0:
		return &""
	# Still draw once for a one-item pool, preserving the RNG call contract.
	var roll := rng.randf() * total
	var cumulative := 0.0
	var last_positive: StringName
	for creation_id in weights:
		var weight := weights[creation_id]
		if weight <= 0.0:
			continue
		last_positive = creation_id
		cumulative += weight
		if roll < cumulative:
			return creation_id
	return last_positive
