class_name WorldContentConfiguration
extends Resource

@export var content_id: StringName
@export var content_version := 1
@export var creations: Array[CreationDefinition] = []
@export var recipes: Array[MergeRecipe] = []
@export var spawn_stages: Array[SpawnStage] = []
@export var final_creation_id: StringName

const DEFAULT_BASE_RADIUS_RATIO := 0.046

@export_range(0.001, 0.5, 0.001, "or_greater") var base_radius_ratio := DEFAULT_BASE_RADIUS_RATIO

var _sizing_warnings: Dictionary = {}


func sizing_errors(require_strict_growth := false) -> PackedStringArray:
	var errors := PackedStringArray()
	if not is_finite(base_radius_ratio) or base_radius_ratio <= 0.0:
		errors.append("base_radius_ratio must be positive and finite.")
	var orders: Dictionary = {}
	for creation in creations:
		if creation == null:
			errors.append("Missing creation in size sequence.")
			continue
		var order := creation.size_order
		if order < 1:
			errors.append("size_order must be positive: %s." % creation.id)
		if orders.has(order):
			errors.append("Duplicate size_order %d." % order)
		orders[order] = true
		var growth := creation.size_growth_percent
		if not is_finite(growth) or growth < 0.0:
			errors.append("size_growth_percent must be nonnegative and finite: %s." % creation.id)
		elif order == 1 and growth != 0.0:
			errors.append("size_order 1 must have 0% growth.")
		elif require_strict_growth and order > 1 and growth == 0.0:
			errors.append("Strict size growth requires more than 0%% at size_order %d." % order)
	if not orders.has(1):
		errors.append("Missing size_order 1.")
	for order in range(2, creations.size() + 1):
		if not orders.has(order):
			errors.append("Missing size_order %d." % order)
	return errors


func effective_radius_ratio(creation: CreationDefinition) -> float:
	var fallback := base_radius_ratio if is_finite(base_radius_ratio) and base_radius_ratio > 0.0 else DEFAULT_BASE_RADIUS_RATIO
	var errors := sizing_errors()
	if not errors.is_empty():
		for error in errors:
			_warn_sizing_once(error, error + " Invalid size sequence uses base radius only.")
		return fallback
	if creation == null or not creations.has(creation):
		_warn_sizing_once("creation", "Requested creation is not in this world; using base radius.")
		return fallback
	var ordered := creations.duplicate()
	ordered.sort_custom(func(first: CreationDefinition, second: CreationDefinition) -> bool:
		return first.size_order < second.size_order
	)
	var radius := base_radius_ratio
	for definition in ordered:
		if definition.size_order > 1:
			radius *= 1.0 + definition.size_growth_percent / 100.0
		if not is_finite(radius):
			_warn_sizing_once("overflow", "Size curve overflow; using base radius.")
			return fallback
		if definition == creation:
			return radius
	return fallback


func _warn_sizing_once(field: String, message: String) -> void:
	# Preview reads sizing every frame; malformed content must not flood the log.
	if not _sizing_warnings.has(field):
		_sizing_warnings[field] = true
		push_warning("World sizing (%s): %s" % [field, message])


func creation_for_id(creation_id: StringName) -> CreationDefinition:
	for creation in creations:
		if creation.id == creation_id:
			return creation
	return null


func recipe_for(
	first_id: StringName,
	second_id: StringName
) -> MergeRecipe:
	for recipe in recipes:
		if recipe.matches(first_id, second_id):
			return recipe
	return null


func spawn_stage_after_merge(current_stage: int, result_id: StringName) -> int:
	# Monotonic and run-only: repeated results never downgrade or repeat an unlock.
	for index in range(current_stage + 1, spawn_stages.size()):
		if spawn_stages[index].unlock_creation_id == result_id:
			return index
	return current_stage


func spawn_stage_errors() -> PackedStringArray:
	var errors := PackedStringArray()
	if spawn_stages.is_empty():
		errors.append("At least one spawn stage is required.")
	var triggers: Dictionary = {}
	for index in range(spawn_stages.size()):
		var stage := spawn_stages[index]
		if stage == null:
			errors.append("Missing spawn stage %d." % index)
			continue
		var trigger := stage.unlock_creation_id
		if index == 0:
			if not trigger.is_empty():
				errors.append("Opening spawn stage must have no unlock creation.")
		elif creation_for_id(trigger) == null or not recipes.any(func(recipe: MergeRecipe) -> bool:
			return recipe.result == trigger):
			errors.append("Spawn stage unlock must be a merge result: %s." % trigger)
		if triggers.has(trigger):
			errors.append("Duplicate spawn stage unlock: %s." % trigger)
		triggers[trigger] = true
		var ordered_ids: Dictionary = {}
		for creation_id in stage.selection_order:
			if ordered_ids.has(creation_id):
				errors.append("Duplicate spawn selection ID: %s." % creation_id)
			if not stage.weights.has(creation_id):
				errors.append("Spawn selection ID has no weight: %s." % creation_id)
			ordered_ids[creation_id] = true
		var total := 0.0
		for creation_id in stage.weights:
			if not ordered_ids.has(creation_id):
				errors.append("Spawn weight is missing from selection_order: %s." % creation_id)
			var weight := stage.weights[creation_id]
			if creation_for_id(creation_id) == null or not is_finite(weight) or weight < 0.0:
				errors.append("Invalid spawn stage weight: %s." % creation_id)
			total += weight
		if not is_finite(total) or total <= 0.0:
			errors.append("Spawn stage %d needs a positive finite total weight." % index)
	return errors


func collection_creations() -> Array[CreationDefinition]:
	var ordered := creations.duplicate()
	ordered.sort_custom(_sort_by_collection_order)
	return ordered


func _sort_by_collection_order(
	first: CreationDefinition,
	second: CreationDefinition
) -> bool:
	return first.collection_order < second.collection_order
