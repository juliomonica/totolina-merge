class_name CreationDefinition
extends Resource

@export var id: StringName
@export var display_name_key: StringName
@export var texture: Texture2D
@export var progression_rank := 1
@export var collection_order := 1
# Physical size sequence, independent of scoring rank and collection order.
@export_range(1, 100, 1, "or_greater") var size_order := 1
@export_range(0.0, 100.0, 0.1, "or_greater") var size_growth_percent := 0.0
@export var mass := 1.0
@export var visual_diameter_scale := 2.18
