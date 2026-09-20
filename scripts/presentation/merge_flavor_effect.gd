class_name MergeFlavorEffect
extends Node2D
## Approved lab timelines shared with production. Presentation only.
## No gameplay references, timers, physics or reward callbacks.
signal finished

const ASSET_DIRECTORY := "res://assets/worlds/kitchen/effects/merges/"
const EFFECT_NAMES := [&"egg_crack", &"milk_pour", &"cream_swirl"]
const FILES := [
	["egg_bubble_effect.png", "egg_crack_01.png", "egg_crack_02.png", "egg_crack_03.png"],
	["milk_bubble_effect.png", "milk_pour_01.png", "milk_pour_02.png", "milk_pour_03.png", "milk_pour_04.png"],
	["cream_bubble_effect.png", "cream_swirl_01.png", "cream_swirl_02.png", "cream_swirl_03.png"],
]
const DEFAULT_DURATIONS := [0.56, 0.66, 0.64]
const TRANSITIONS := [[0.10, 0.21, 0.32], [0.11, 0.22, 0.32, 0.42], [0.12, 0.26, 0.39]]
# Common source-canvas pivots keep the bottle/stream and piping bag registered.
# Egg shell poses need individual offsets because their source layouts differ.
const PIVOTS := [
	[Vector2(256, 256), Vector2(256, 256), Vector2(256, 170), Vector2(256, 256)],
	[Vector2(256, 256), Vector2(375, 478), Vector2(375, 478), Vector2(375, 478), Vector2(375, 478)],
	[Vector2(256, 256), Vector2(305, 480), Vector2(305, 480), Vector2(305, 480)],
]
const DEFAULT_CROSSFADE := 0.065
const DEFAULT_CANVAS_PIXELS := 200.0

var egg_seconds: float = DEFAULT_DURATIONS[0]
var milk_seconds: float = DEFAULT_DURATIONS[1]
var cream_seconds: float = DEFAULT_DURATIONS[2]
var crossfade_seconds := DEFAULT_CROSSFADE
var canvas_pixels := DEFAULT_CANVAS_PIXELS
var player: AnimationPlayer
var layers: Array[Node2D] = []
var poses: Array[Sprite2D] = []
var assets_ok := true
static var _bounds_cache: Dictionary = {}


func build(effects: Array = [0, 1, 2]) -> void:
	# Lab creates all three once; a production instance builds only its effect.
	assert(player == null)
	player = AnimationPlayer.new()
	player.name = "AnimationPlayer"
	add_child(player)
	player.animation_finished.connect(_on_finished)
	layers.resize(EFFECT_NAMES.size())
	var library := AnimationLibrary.new()
	for effect in effects:
		var layer := Node2D.new()
		layer.name = String(EFFECT_NAMES[effect])
		add_child(layer)
		layers[effect] = layer
		var animation := Animation.new()
		animation.length = _duration(effect)
		for frame in range(FILES[effect].size()):
			var sprite := Sprite2D.new()
			sprite.name = "Pose%d" % frame
			var asset_path: String = ASSET_DIRECTORY + FILES[effect][frame]
			if ResourceLoader.exists(asset_path):
				sprite.texture = load(asset_path) as Texture2D
			if sprite.texture == null:
				assets_ok = false
				push_error("Merge flavor cannot load: " + asset_path)
			sprite.centered = false
			sprite.offset = -PIVOTS[effect][frame]
			sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
			layer.add_child(sprite)
			poses.append(sprite)
			_author_pose(animation, sprite, effect, frame)
		library.add_animation(EFFECT_NAMES[effect], animation)
	player.add_animation_library(&"", library)
	reset()


func _duration(effect: int) -> float:
	return [egg_seconds, milk_seconds, cream_seconds][effect]


func _author_pose(animation: Animation, sprite: Sprite2D, effect: int, frame: int) -> void:
	var duration := DEFAULT_DURATIONS[effect] as float
	var ratio := animation.length / duration
	var blend := crossfade_seconds / ratio # Blend stays the Inspector's actual seconds.
	var starts: Array = TRANSITIONS[effect]
	var last: bool = frame == FILES[effect].size() - 1
	var begin := 0.0 if frame == 0 else float(starts[frame - 1])
	var end := duration - 0.09 if last else float(starts[frame])
	var alpha_keys: Array = [[0.0, 0.0]]
	if begin > 0.0:
		alpha_keys.append([begin, 0.0])
	alpha_keys.append([begin + (0.065 if frame == 0 else blend), 1.0])
	alpha_keys.append([end, 1.0])
	alpha_keys.append([duration if last else end + blend, 0.0])
	_track(animation, sprite, "modulate:a", alpha_keys, ratio, -2.0)
	var base := canvas_pixels / 512.0
	if frame == 0:
		var arrival := Vector2(0, -87)
		var start := Vector2(0, -109)
		if effect == 1:
			start = Vector2(28, -109)
			arrival = Vector2(12, -90)
		_track(animation, sprite, "position", [[0.0, start], [end + blend, arrival]], ratio, -2.0)
		_track(animation, sprite, "scale", [[0.0, Vector2.ONE * base * 0.49],
			[0.07, Vector2.ONE * base * 0.57], [end + blend, Vector2.ONE * base * 0.55]], ratio, 0.5)
		_track(animation, sprite, "rotation", [[0.0, -0.025], [end + blend, 0.0]], ratio, -2.0)
		return
	var position_keys: Array
	var scale_keys: Array
	var rotation_keys: Array
	if effect == 0:
		# Shell alignment is intentional; the yolk then travels toward the cross.
		var from := Vector2(0, -85) if frame == 1 else Vector2(0, -79)
		var to := Vector2(0, -79) if frame == 1 else Vector2(0, -65)
		if last:
			from = Vector2(0, -8)
			to = Vector2.ZERO
		position_keys = [[begin, from], [end, to]]
		scale_keys = [[begin, Vector2.ONE * (0.76 if frame == 1 else 0.82)],
			[end, Vector2.ONE * (0.79 if frame == 1 else 0.84)]]
		rotation_keys = [[begin, -0.012], [end, 0.012]]
	else:
		# All pour/swirl poses share one motion curve, including during overlaps.
		# This avoids a second bottle/nozzle wandering away in the crossfade.
		position_keys = [[0.0, Vector2(2, -3)], [float(starts[0]), Vector2(2, -3)],
			[duration - 0.15, Vector2.ZERO], [duration, Vector2.ZERO]]
		scale_keys = [[0.0, Vector2.ONE], [duration, Vector2.ONE]]
		rotation_keys = [[0.0, 0.008], [duration - 0.15, 0.0], [duration, 0.0]]
	if last:
		# One soft impact, no repeated bounce. For milk/cream the full drawing
		# is kept intact, so overshoot is deliberately only two to three percent.
		var strength := 1.0 if effect == 0 else 0.5
		scale_keys = [[begin, Vector2.ONE * (0.94 if effect == 0 else 1.0)],
			[begin + blend, Vector2(1.0 + 0.06 * strength, 1.0 - 0.04 * strength)],
			[end - 0.015, Vector2.ONE], [duration, Vector2.ONE]]
	for key in scale_keys:
		key[1] *= base
	_track(animation, sprite, "position", position_keys, ratio, -2.0 if effect != 0 or last else 2.0)
	_track(animation, sprite, "scale", scale_keys, ratio, -2.0)
	_track(animation, sprite, "rotation", rotation_keys, ratio, -2.0)


func _track(animation: Animation, sprite: Sprite2D, property: String, keys: Array,
		time_ratio: float, easing: float) -> void:
	var index := animation.add_track(Animation.TYPE_VALUE)
	animation.track_set_path(index, NodePath(String(get_path_to(sprite)) + ":" + property))
	animation.value_track_set_update_mode(index, Animation.UPDATE_CONTINUOUS)
	animation.track_set_interpolation_loop_wrap(index, false)
	for key in keys:
		animation.track_insert_key(index, float(key[0]) * time_ratio, key[1], easing)


func play(effect: int) -> void:
	reset()
	if not assets_ok:
		return
	layers[effect].show()
	player.play(EFFECT_NAMES[effect])
	player.advance(0.0)


func reset() -> void:
	player.stop()
	for layer in layers:
		if layer != null:
			layer.hide()
	for sprite in poses:
		sprite.modulate = Color(1, 1, 1, 0)
		sprite.visible = true
		sprite.position = Vector2.ZERO
		sprite.scale = Vector2.ONE * canvas_pixels / 512.0
		sprite.rotation = 0.0


func _on_finished(_animation: StringName) -> void:
	reset()
	finished.emit()


func fit_scale(effect: int, origin: Vector2, area: Rect2, diameter: float) -> float:
	# Scale the entire visual uniformly; keep its merge-point anchor exact.
	# Cache a conservative swept source-canvas bound, never crop/retime poses.
	var key := "%d/%f/%f/%f" % [effect, _duration(effect), crossfade_seconds, canvas_pixels]
	if not _bounds_cache.has(key):
		var animation := player.get_animation(EFFECT_NAMES[effect])
		var bounds := Rect2(Vector2.ZERO, Vector2.ZERO)
		for sample in range(81):
			var time := animation.length * sample / 80.0
			for frame in range(FILES[effect].size()):
				var track := frame * 4
				if float(animation.value_track_interpolate(track, time)) < 0.001:
					continue
				var point: Vector2 = animation.value_track_interpolate(track + 1, time)
				var stretch: Vector2 = animation.value_track_interpolate(track + 2, time)
				var angle: float = animation.value_track_interpolate(track + 3, time)
				var transform := Transform2D(angle, stretch, 0.0, point)
				var rect := Rect2(-PIVOTS[effect][frame], Vector2(512, 512))
				for corner in [rect.position, Vector2(rect.end.x, rect.position.y),
						rect.end, Vector2(rect.position.x, rect.end.y)]:
					bounds = bounds.expand(transform * corner)
		_bounds_cache[key] = bounds.grow(2.0)
	var bounds: Rect2 = _bounds_cache[key]
	var factor := diameter / DEFAULT_CANVAS_PIXELS
	factor = minf(factor, (origin.x - area.position.x) / -bounds.position.x)
	factor = minf(factor, (area.end.x - origin.x) / bounds.end.x)
	factor = minf(factor, (origin.y - area.position.y) / -bounds.position.y)
	factor = minf(factor, (area.end.y - origin.y) / bounds.end.y)
	return maxf(0.0, factor)


func _exit_tree() -> void:
	if is_instance_valid(player):
		player.stop()

