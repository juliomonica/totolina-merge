extends "res://scripts/prototype/physics_sandbox.gd"

# Test-only observer. Every override delegates to the real gameplay lifecycle.
# Store IDs/counters, not references that could keep dead contact state around.
var callback_depth := 0
var resolving_depth := 0
var contact_events := 0
var result_spawns: Dictionary = {}
var awards: Dictionary = {}
var registrations: Dictionary = {}
var discoveries: Dictionary = {}
var exits: Dictionary = {}
var merge_snapshots: Array[Dictionary] = []


func _on_piece_body_entered(other: Node, source: PrototypePiece) -> void:
	callback_depth += 1
	if other is PrototypePiece:
		contact_events += 1
	super._on_piece_body_entered(other, source)
	callback_depth -= 1


func _resolve_merge(first: PrototypePiece, second: PrototypePiece, result_id: StringName,
		position: Vector2, velocity: Vector2, angular: float, angle: float, generation: int) -> void:
	merge_snapshots.append({"result": result_id, "callback_depth": callback_depth,
		"first": _source_snapshot(first), "second": _source_snapshot(second),
		"generation": generation, "current_generation": _merge_generation})
	resolving_depth += 1
	super._resolve_merge(first, second, result_id, position, velocity, angular, angle, generation)
	resolving_depth -= 1


func _source_snapshot(piece: Variant) -> Dictionary:
	if not is_instance_valid(piece):
		return {"valid": false}
	return {"valid": true, "id": piece.creation_id, "sequence": piece.spawn_sequence,
		"queued": piece.is_queued_for_deletion(), "pending": piece.merge_pending,
		"radius": piece.radius, "position": str(piece.position)}


func _spawn_piece(definition: CreationDefinition, position: Vector2,
		velocity := Vector2.ZERO, angular := 0.0, angle := 0.0) -> PrototypePiece:
	var piece := super._spawn_piece(definition, position, velocity, angular, angle)
	if resolving_depth > 0 and piece != null:
		result_spawns[definition.id] = result_spawns.get(definition.id, 0) + 1
	return piece


func _award_creation(definition: CreationDefinition, position: Vector2, radius: float) -> void:
	awards[definition.id] = awards.get(definition.id, 0) + 1
	super._award_creation(definition, position, radius)


func _register_creation(id: StringName, position: Vector2, radius: float, feedback: bool) -> bool:
	registrations[id] = registrations.get(id, 0) + 1
	var newly_discovered := super._register_creation(id, position, radius, feedback)
	if newly_discovered:
		discoveries[id] = discoveries.get(id, 0) + 1
	return newly_discovered


func _on_piece_exiting(piece: PrototypePiece) -> void:
	exits[piece.spawn_sequence] = exits.get(piece.spawn_sequence, 0) + 1
	super._on_piece_exiting(piece)
