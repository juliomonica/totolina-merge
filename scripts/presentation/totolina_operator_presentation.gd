extends Node2D
## Layered, gameplay-independent operator. All pivots are source-image pixels.
## Private blink RNG never consumes the gameplay/global random stream.

# Layout/pivots are authored in scenes/presentation/totolina_operator.tscn.
# Crossfade channels are animated by the shared machine AnimationPlayer.
var visual: Node2D
var idle_player: AnimationPlayer
var arms: Array[Sprite2D] = []
var eyes: Array[Sprite2D] = []
var expression_eyes: Array[Sprite2D] = []
var mouths: Array[Sprite2D] = []
var textures: Array[Texture2D] = []
var assets_ok := true
var idle_enabled := false
var blink_wait := 0.0
var playback_speed := 1.0
var _blink_rng := RandomNumberGenerator.new()

var arm_pose := 0.0:
	set(value):
		arm_pose = clampf(value, 0.0, 3.0)
		_blend(arms, arm_pose)
var blink_pose := 0.0:
	set(value):
		blink_pose = clampf(value, 0.0, 2.0)
		_update_face()
var expression_weights := Vector2.ZERO:
	set(value):
		expression_weights = value.clamp(Vector2.ZERO, Vector2.ONE)
		_update_face()


var _visual_base: Transform2D
var reaction_offset := 0.0:
	set(value):
		reaction_offset = value
		if is_instance_valid(visual):
			visual.position = _visual_base.origin + Vector2(0, value)


func _ready() -> void:
	visual = $Visual
	_visual_base = visual.transform
	arms.assign($Visual/Arms.get_children())
	for sprite in $Visual/Eyes.get_children():
		if sprite.name.contains("blink"):
			eyes.append(sprite)
		else:
			expression_eyes.append(sprite)
	for sprite in visual.get_children():
		if sprite.name.begins_with("cat_totolina_mouth"):
			mouths.append(sprite)
	for sprite in find_children("*", "Sprite2D", true, false):
		textures.append(sprite.texture)
		assets_ok = assets_ok and sprite.texture != null
	idle_player = $IdlePlayer
	idle_player.animation_finished.connect(_blink_finished)
	_blink_rng.randomize()
	reset_pose()


func _blend(sprites: Array[Sprite2D], value: float, opacity := 1.0) -> void:
	for index in range(sprites.size()):
		sprites[index].modulate.a = maxf(0.0, 1.0 - absf(value - index)) * opacity


func _update_face() -> void:
	if mouths.is_empty():
		return
	var normal := maxf(0.0, 1.0 - expression_weights.x - expression_weights.y)
	_blend(eyes, blink_pose, normal)
	expression_eyes[0].modulate.a = expression_weights.x
	expression_eyes[1].modulate.a = expression_weights.y
	mouths[0].modulate.a = normal
	mouths[1].modulate.a = expression_weights.x
	mouths[2].modulate.a = expression_weights.y


func reset_pose() -> void:
	set_idle(false)
	arm_pose = 0.0
	blink_pose = 0.0
	expression_weights = Vector2.ZERO
	visual.transform = _visual_base
	reaction_offset = 0.0
	visual.modulate = Color.WHITE
	visual.show()


func set_idle(enabled: bool) -> void:
	idle_enabled = enabled
	set_process(enabled)
	if idle_player != null:
		idle_player.stop()
	blink_pose = 0.0
	if enabled:
		blink_wait = _blink_rng.randf_range(2.5, 5.0)


func set_playback_speed(value: float) -> void:
	playback_speed = clampf(value, 0.25, 2.0)
	idle_player.speed_scale = playback_speed


func _process(delta: float) -> void:
	if idle_player.is_playing():
		return
	blink_wait -= delta * playback_speed
	if blink_wait <= 0.0:
		idle_player.play(&"blink")


func _blink_finished(_animation: StringName) -> void:
	blink_wait = _blink_rng.randf_range(2.5, 5.0)


static func add_track(animation: Animation, path: NodePath, keys: Array, easing := -2.0) -> int:
	var track := animation.add_track(Animation.TYPE_VALUE)
	animation.track_set_path(track, path)
	animation.track_set_interpolation_loop_wrap(track, false)
	for key in keys:
		animation.track_insert_key(track, key[0], key[1], easing)
	return track


func _exit_tree() -> void:
	if is_instance_valid(idle_player):
		idle_player.stop()
	set_process(false)
