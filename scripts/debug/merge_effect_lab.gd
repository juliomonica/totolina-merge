extends Control
## Standalone review controls around the same approved effect used by gameplay.

const FLAVOR = preload("res://scripts/presentation/merge_flavor_effect.gd")
const EFFECT_NAMES = FLAVOR.EFFECT_NAMES

@export_group("Lab timing at 1×")
@export_range(0.45, 0.60, 0.01) var egg_seconds: float = FLAVOR.DEFAULT_DURATIONS[0]
@export_range(0.55, 0.70, 0.01) var milk_seconds: float = FLAVOR.DEFAULT_DURATIONS[1]
@export_range(0.55, 0.70, 0.01) var cream_seconds: float = FLAVOR.DEFAULT_DURATIONS[2]
@export_range(0.05, 0.08, 0.005) var crossfade_seconds := FLAVOR.DEFAULT_CROSSFADE
@export_group("Lab presentation")
@export_range(140.0, 240.0, 5.0) var canvas_pixels := FLAVOR.DEFAULT_CANVAS_PIXELS

var player: AnimationPlayer
var flavor: MergeFlavorEffect
@onready var preview: Control = $Margin/Column/Preview
@onready var merge_point: Node2D = $Margin/Column/Preview/MergePoint
@onready var selector: OptionButton = $Margin/Column/Selectors/Effect
@onready var background: OptionButton = $Margin/Column/Selectors/Background
@onready var play_button: Button = $Margin/Column/Transport/Play
@onready var stop_button: Button = $Margin/Column/Transport/Stop
@onready var speed: HSlider = $Margin/Column/SpeedRow/Speed
@onready var speed_label: Label = $Margin/Column/SpeedRow/SpeedLabel
@onready var loop_toggle: CheckButton = $Margin/Column/SpeedRow/Loop
@onready var scrub: HSlider = $Margin/Column/Scrub
@onready var status: Label = $Margin/Column/Status

var layers: Array[Node2D] = []
var poses: Array[Sprite2D] = []
var selected_effect := 0
var _assets_ok := true


func _ready() -> void:
	set_process(false)
	# Guard before loading artwork, creating sprites or connecting callbacks.
	if not OS.is_debug_build():
		hide()
		queue_free()
		return
	for label in ["Egg", "Milk", "Cream"]:
		selector.add_item(label)
	for label in ["Dark neutral", "Light neutral", "Checker"]:
		background.add_item(label)
	preview.draw.connect(_draw_preview)
	preview.resized.connect(_layout_preview)
	_create_animations()
	selector.item_selected.connect(select_effect)
	background.item_selected.connect(func(_index: int): preview.queue_redraw())
	play_button.pressed.connect(replay)
	stop_button.pressed.connect(stop_reset)
	speed.value_changed.connect(_set_speed)
	loop_toggle.toggled.connect(_set_loop)
	scrub.value_changed.connect(inspect_time)
	flavor.finished.connect(_on_animation_finished)
	_layout_preview()
	select_effect(0)
	if not _assets_ok:
		play_button.disabled = true
		scrub.editable = false
		status.text = "Missing/import-failed artwork; see Output."


func _create_animations() -> void:
	flavor = FLAVOR.new()
	flavor.egg_seconds = egg_seconds
	flavor.milk_seconds = milk_seconds
	flavor.cream_seconds = cream_seconds
	flavor.crossfade_seconds = crossfade_seconds
	flavor.canvas_pixels = canvas_pixels
	merge_point.add_child(flavor)
	flavor.build()
	player = flavor.player
	layers = flavor.layers
	poses = flavor.poses
	_assets_ok = flavor.assets_ok


func _duration(effect: int) -> float:
	return flavor._duration(effect)


func replay() -> void:
	if not OS.is_debug_build() or not _assets_ok:
		return
	stop_reset()
	flavor.play(selected_effect)
	set_process(true)
	_update_status("Playing")


func stop_reset() -> void:
	flavor.reset()
	set_process(false)
	scrub.set_value_no_signal(0.0)
	_update_status("Idle")


func select_effect(index: int) -> void:
	stop_reset()
	selected_effect = clampi(index, 0, EFFECT_NAMES.size() - 1)
	selector.select(selected_effect)
	scrub.max_value = _duration(selected_effect)
	_update_status("Idle")


func inspect_time(seconds: float) -> void:
	if not OS.is_debug_build() or not _assets_ok:
		return
	# Reinitializing all channels makes backward seeks and switches deterministic.
	stop_reset()
	layers[selected_effect].show()
	player.play(EFFECT_NAMES[selected_effect])
	player.seek(clampf(seconds, 0.0, _duration(selected_effect)), true)
	player.pause()
	scrub.set_value_no_signal(seconds)
	_update_status("Inspecting")


func _set_speed(value: float) -> void:
	player.speed_scale = value
	speed_label.text = "Speed  %.2f×" % value


func _set_loop(enabled: bool) -> void:
	# Native looping uses the same clock as every alpha/transform track.
	for effect_name in EFFECT_NAMES:
		player.get_animation(effect_name).loop_mode = Animation.LOOP_LINEAR if enabled else Animation.LOOP_NONE


func _process(_delta: float) -> void:
	scrub.set_value_no_signal(player.current_animation_position)
	_update_status("Playing")


func _on_animation_finished() -> void:
	stop_reset()
	_update_status("Finished")


func _update_status(state: String) -> void:
	status.text = "%s  ·  %s  ·  %.3f / %.2f s" % [selector.get_item_text(selected_effect),
		state, scrub.value, _duration(selected_effect)]


func _layout_preview() -> void:
	merge_point.position = preview.size * 0.5 + Vector2(0, 70)
	preview.queue_redraw()


func _draw_preview() -> void:
	var rect := Rect2(Vector2.ZERO, preview.size)
	var light := background.selected == 1
	preview.draw_rect(rect, Color("e6e2da") if light else Color("282d36"))
	if background.selected == 2:
		for y in range(0, ceili(preview.size.y), 20):
			for x in range(0, ceili(preview.size.x), 20):
				var cell := Rect2(x, y, minf(20, preview.size.x - x), minf(20, preview.size.y - y))
				preview.draw_rect(cell, Color("474c56") if (x / 20 + y / 20) % 2 == 0 else Color("373c46"))
	var guide := Color(0.27, 0.39, 0.4, 0.65) if light else Color(0.62, 0.77, 0.77, 0.55)
	var point := merge_point.position
	preview.draw_arc(point, 42.0, 0.0, TAU, 64, Color(guide, 0.2), 1.0, true)
	preview.draw_line(point - Vector2(9, 0), point + Vector2(9, 0), guide, 1.0, true)
	preview.draw_line(point - Vector2(0, 9), point + Vector2(0, 9), guide, 1.0, true)
	preview.draw_rect(rect, Color("626d7b"), false, 1.0)


func _exit_tree() -> void:
	if is_instance_valid(player):
		player.stop()
	set_process(false)
