extends Node2D
## Presentation prototype. Caller owns gameplay; contact_reached is a cosmetic
## timing cue, never permission/authority to spawn, score or advance RNG.
signal contact_reached(target_x: float)
signal finished(action: StringName)

const CAT = preload("res://scripts/presentation/totolina_operator_presentation.gd")
const ENV := "res://assets/worlds/environment/"
const COLLECTION := "res://assets/worlds/kitchen/ui/collection/"
const SIZE := Vector2(500, 550)
const CONTACT_SECONDS := 0.20
const ACTIONS := [&"full_drop", &"press", &"shutter", &"nozzle", &"feeder", &"excited", &"surprised"]
const LENGTHS := [0.62, 0.44, 0.50, 0.18, 0.42, 0.56, 0.56]
const ITEM_SCALE := Vector2.ONE * 0.090
const NOZZLE_Y := 264.0
const RELEASE_Y := 269.0
const COLLECTION_VIEWPORT := Rect2(16, 454, 468, 67)
const COLLECTION_ICON_SCALE := 0.13
const COLLECTION_PITCH := 100.0
const COLLECTION_FILES := ["wheat.png", "flour.png", "cake_mix.png", "", "", "", "", "", ""]

# Set before adding to the tree. The lab keeps its approved default composition;
# production supplies the real environment, collection, items and release body.
@export_group("Integration")
## Set by the production scene. Leave false for the standalone animation lab.
@export var production_mode := false
# Read-only aliases for callers/tests; authored Sprite2D scale is authoritative.
var current_preview_scale: Vector2:
	get: return _current_base.get_scale()
var next_preview_scale: Vector2:
	get: return _next_base.get_scale()
var _current_base: Transform2D
var _next_base: Transform2D
var _incoming_base: Transform2D
var _nozzle_base: Transform2D
var current_offset := Vector2.ZERO:
	set(value):
		current_offset = value
		if is_instance_valid(current_item):
			current_item.position = _current_base.origin + value
var current_visible := true:
	set(value):
		current_visible = value
		if is_instance_valid(current_item) and production_mode:
			current_item.visible = value
var next_travel := 0.0:
	set(value):
		next_travel = value
		if is_instance_valid(next_item):
			next_item.position = _next_base.origin.lerp(_current_base.origin, value)
var next_growth := 0.0:
	set(value):
		next_growth = value
		if is_instance_valid(next_item):
			next_item.scale = _next_base.get_scale().lerp(_current_base.get_scale(), value)
var incoming_pop := 1.0:
	set(value):
		incoming_pop = value
		if is_instance_valid(incoming_item):
			incoming_item.scale = _incoming_base.get_scale() * value
var target_limits := Vector2(72.0, 428.0)

var cat: Node2D
var player: AnimationPlayer
var nozzle: Sprite2D
var current_item: Sprite2D
var next_item: Sprite2D
var incoming_item: Sprite2D
var falling_item: Sprite2D
var target_guide: Line2D
var collection_track: Node2D
var preview_size := SIZE
var buttons: Array[Sprite2D] = []
var shutters: Array[Polygon2D] = []
var item_textures: Array[Texture2D] = []
var score_text: Label
var textures: Array[Texture2D] = []
var assets_ok := true
var busy := false
var action: StringName = &""
var target_x := 350.0
var move_seconds := 0.18
var idle_enabled := true
var _contact_sent := false
var _cycle_target_x := 250.0
var _nozzle_track := -1
var _falling_track := -1
var _nozzle_only_track := -1

var button_pose := 0.0:
	set(value):
		button_pose = clampf(value, 0.0, 2.0)
		for index in range(buttons.size()):
			buttons[index].modulate.a = maxf(0.0, 1.0 - absf(button_pose - index))
var shutter_pose := 0.0:
	set(value):
		shutter_pose = clampf(value, 0.0, 5.0)
		for index in range(shutters.size()):
			shutters[index].modulate.a = maxf(0.0, 1.0 - absf(shutter_pose - index))


func _ready() -> void:
	if not production_mode:
		_build_environment()
	_bind_machine()
	_bind_animations()
	reset()
	cat.set_idle(idle_enabled)


func _texture(file: String) -> Texture2D:
	var texture := load(file) as Texture2D
	assets_ok = assets_ok and texture != null
	textures.append(texture)
	return texture


func _sprite(file: String, node_name: String, at: Vector2, factor: float, parent: Node = self) -> Sprite2D:
	var sprite := Sprite2D.new()
	sprite.name = node_name
	sprite.texture = _texture(file)
	sprite.position = at
	sprite.scale = Vector2.ONE * factor
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	parent.add_child(sprite)
	return sprite


func _label(text: String, at: Vector2, font_size: int, parent: Node = self) -> Label:
	var label := Label.new()
	label.text = text
	label.position = at
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", Color("d8e9e5"))
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label


func _build_environment() -> void:
	var backdrop := TextureRect.new()
	backdrop.name = "EnvironmentBackdrop"
	backdrop.texture = _texture(ENV + "background.png")
	backdrop.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	backdrop.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	backdrop.size = SIZE
	backdrop.z_index = -10
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(backdrop)
	# Nine-patching shortens the mock chamber without flattening the frame trim.
	# The rear and front remain separate, identically mapped image layers.
	for layer in ["machine_chamber_background.png", "machine_foreground_frame.png"]:
		var frame := NinePatchRect.new()
		frame.name = layer.get_basename()
		frame.texture = _texture(ENV + layer)
		frame.size = Vector2(859, 943)
		frame.scale = Vector2.ONE * 500.0 / 859.0
		frame.patch_margin_left = 56
		frame.patch_margin_right = 56
		frame.patch_margin_top = 425
		frame.patch_margin_bottom = 236
		frame.z_index = -9 if layer.contains("background") else 2
		frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(frame)


func _bind_machine() -> void:
	var top := $TopMachine
	# TopMachine's scene-authored z_index is shared by lab and production.
	cat = $TopMachine/Totolina
	current_item = $TopMachine/Current
	next_item = $TopMachine/Next
	incoming_item = $TopMachine/Incoming
	nozzle = $TopMachine/Nozzle
	score_text = $TopMachine/SampleScore/ScoreLabel
	_current_base = current_item.transform
	_next_base = next_item.transform
	_incoming_base = incoming_item.transform
	_nozzle_base = nozzle.transform
	for index in range(1, 4):
		buttons.append(top.get_node("Button/ButtonPose%d" % index))
	for index in range(1, 7):
		shutters.append(top.get_node("Shutter/IrisPose%d" % index))
	for node in top.find_children("*", "", true, false):
		if (node is Sprite2D or node is Polygon2D) and not cat.is_ancestor_of(node) and node not in [current_item, next_item, incoming_item]:
			textures.append(node.texture)
			assets_ok = assets_ok and node.texture != null
	assets_ok = assets_ok and cat.assets_ok
	_texture(ENV + "machine/score/score_screen_off.png")
	_texture(ENV + "machine/score/score_screen_on.png")
	if production_mode:
		return
	$TopMachine/PulseLabel.hide()
	var score_caption := _label("SAMPLE SCORE", Vector2(0, -22), 12, $TopMachine/SampleScore)
	score_caption.size = Vector2(179.2, 18)
	score_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	falling_item = _item("FallingSample", self)
	falling_item.z_index = 1
	# A static collection strip is only a composition reference.
	var strip := Node2D.new()
	strip.name = "StaticCollectionPreview"
	strip.z_index = 3
	add_child(strip)
	var collection_view := Control.new()
	collection_view.name = "Viewport"
	collection_view.position = COLLECTION_VIEWPORT.position
	collection_view.size = COLLECTION_VIEWPORT.size
	collection_view.clip_contents = true
	collection_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	strip.add_child(collection_view)
	collection_track = Node2D.new()
	collection_track.name = "ItemTrack"
	collection_view.add_child(collection_track)
	for index in range(COLLECTION_FILES.size()):
		var file: String = COLLECTION + "collection_mystery_bubble.png" if COLLECTION_FILES[index].is_empty() \
			else "res://assets/worlds/kitchen/ingredients/" + COLLECTION_FILES[index]
		_sprite(file, "CollectionItem%d" % index, Vector2(index * COLLECTION_PITCH, 0),
			COLLECTION_ICON_SCALE, collection_track)
	set_collection_preview_offset(0.0)
	add_collection_masks(collection_view)
	_label("STATIC COLLECTION PREVIEW", Vector2(132, 519), 12, strip)
	target_guide = Line2D.new()
	target_guide.name = "TargetGuide"
	target_guide.width = 1.0
	target_guide.default_color = Color(0.65, 0.91, 0.82, 0.35)
	target_guide.points = PackedVector2Array([Vector2(350, 290), Vector2(350, 398)])
	add_child(target_guide)
	_label("TAP CHAMBER TO DROP", Vector2(160, 395), 12, top)


func add_collection_masks(collection_view: Control) -> void:
	var masks := preload("res://scenes/presentation/collection_masks.tscn").instantiate()
	collection_view.add_child(masks)
	for sprite in masks.find_children("*", "Sprite2D", true, false):
		textures.append(sprite.texture)
		assets_ok = assets_ok and sprite.texture != null


func layout_preview(size_in_machine_space: Vector2) -> void:
	# Lab-only full-phone composition. Production keeps its gameplay-aligned layout.
	if production_mode:
		return
	preview_size = size_in_machine_space
	get_node("EnvironmentBackdrop").size = preview_size
	for layer in ["machine_chamber_background", "machine_foreground_frame"]:
		var art := get_node(layer) as NinePatchRect
		# One uniform scale preserves frame trim; only the empty middle nine-patch grows.
		art.size.y = preview_size.y / art.scale.y
	get_node("StaticCollectionPreview/Viewport").position.y = preview_size.y - 96.0
	for child in get_node("StaticCollectionPreview").get_children():
		if child is Label:
			child.hide()
	for child in get_node("TopMachine").get_children():
		if child is Label:
			child.hide()
	for child in get_node("TopMachine/SampleScore").get_children():
		if child is Label and child != score_text:
			child.hide()
	target_guide.hide()


func set_collection_preview_offset(fraction: float) -> void:
	# Debug composition scrub only: no drag input, discovery or gameplay state.
	if not is_instance_valid(collection_track):
		return
	var travel := (COLLECTION_FILES.size() - 1) * COLLECTION_PITCH + 88.0 - COLLECTION_VIEWPORT.size.x
	collection_track.position = Vector2(44.0 - clampf(fraction, 0.0, 1.0) * travel, 33.5)


func _item(node_name: String, parent: Node) -> Sprite2D:
	var sprite := Sprite2D.new()
	sprite.name = node_name
	sprite.scale = ITEM_SCALE
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	parent.add_child(sprite)
	return sprite


func _track(animation: Animation, path: String, keys: Array, easing := -2.0) -> int:
	return CAT.add_track(animation, NodePath(path), keys, easing)


func _bind_animations() -> void:
	player = $AnimationPlayer
	# Duplicate only the local library: destination X depends on player input.
	# Saved scene tracks remain the timing/easing authority and are never rebuilt.
	var library := player.get_animation_library(&"").duplicate(true) as AnimationLibrary
	player.remove_animation_library(&"")
	player.add_animation_library(&"", library)
	_nozzle_track = player.get_animation(&"full_drop").find_track(^"TopMachine/Nozzle:position:x", Animation.TYPE_VALUE)
	_nozzle_only_track = player.get_animation(&"nozzle").find_track(^"TopMachine/Nozzle:position:x", Animation.TYPE_VALUE)
	if not production_mode:
		# Lab-only sample body/fade: production uses its real physical handoff.
		for mode in [&"full_drop", &"feeder"]:
			var start := 0.20 if mode == &"full_drop" else 0.0
			_track(player.get_animation(mode), "TopMachine/Current:modulate:a",
				[[0.0, 1.0], [start, 1.0], [start + 0.10, 0.0]])
		var full := player.get_animation(&"full_drop")
		_falling_track = _track(full, "FallingSample:position", [[0.0, Vector2(target_x, RELEASE_Y)],
			[0.20, Vector2(target_x, RELEASE_Y)], [0.51, Vector2(target_x, 385)]], 2.0)
		_track(full, "FallingSample:modulate:a", [[0.0, 0.0], [0.20, 0.0],
			[0.23, 1.0], [0.43, 1.0], [0.55, 0.0]])
	player.animation_finished.connect(_on_finished)


func _reset_visuals() -> void:
	cat.reset_pose()
	button_pose = 0.0
	shutter_pose = 0.0
	current_item.transform = _current_base
	next_item.transform = _next_base
	incoming_item.transform = _incoming_base
	for sprite in [current_item, next_item, incoming_item]:
		sprite.visible = true
		sprite.modulate = Color.WHITE
	current_offset = Vector2.ZERO
	current_visible = true
	next_travel = 0.0
	next_growth = 0.0
	incoming_pop = 1.0
	incoming_item.modulate.a = 0.0
	if falling_item != null:
		falling_item.position = Vector2(nozzle.position.x, RELEASE_Y)
		falling_item.modulate.a = 0.0
	_apply_item_textures()
	nozzle.modulate = Color.WHITE
	nozzle.visible = true
	_contact_sent = false


func reset() -> void:
	player.stop()
	busy = false
	action = &""
	nozzle.transform = _nozzle_base
	_reset_visuals()


func set_target(value: float) -> void:
	target_x = clampf(value, target_limits.x, target_limits.y)
	if target_guide != null:
		target_guide.points = PackedVector2Array([Vector2(target_x, 290), Vector2(target_x, 398)])


func set_items(current: Texture2D, next: Texture2D, incoming: Texture2D) -> bool:
	# Caller supplies artwork; this component never chooses a creation or RNG draw.
	if busy or current == null or next == null or incoming == null:
		return false
	item_textures = [current, next, incoming]
	_apply_item_textures()
	return true


func _apply_item_textures() -> void:
	if item_textures.size() != 3:
		return
	current_item.texture = item_textures[0]
	next_item.texture = item_textures[1]
	incoming_item.texture = item_textures[2]
	if falling_item != null:
		falling_item.texture = item_textures[0]


func set_incoming(texture: Texture2D) -> void:
	# Production supplies the one newly rolled NEXT only after the real release.
	if item_textures.size() == 3:
		item_textures[2] = texture
		incoming_item.texture = texture


func set_score_preview(text: String) -> void:
	score_text.text = text


func play_action(mode: StringName) -> bool:
	if busy or not assets_ok or not player.has_animation(mode):
		return false
	# stop() can restore the previous clip's initial animated properties.
	# Retain the actual parked nozzle for consecutive moves/drop previews.
	var parked_position := nozzle.position
	player.stop(true)
	_reset_visuals()
	nozzle.position = parked_position
	action = mode
	busy = true
	_cycle_target_x = target_x
	move_seconds = lerpf(0.08, 0.18, minf(absf(target_x - nozzle.position.x) / 356.0, 1.0))
	if mode in [&"full_drop", &"nozzle"]:
		var animation := player.get_animation(mode)
		var track := _nozzle_track if mode == &"full_drop" else _nozzle_only_track
		animation.track_set_key_value(track, 0, nozzle.position.x)
		animation.track_set_key_time(track, 1, move_seconds)
		animation.track_set_key_value(track, 1, target_x)
		if mode == &"nozzle":
			animation.length = move_seconds
		elif not production_mode:
			for index in range(3):
				var point: Vector2 = animation.track_get_key_value(_falling_track, index)
				point.x = target_x
				animation.track_set_key_value(_falling_track, index, point)
	player.play(mode)
	player.advance(0.0)
	return true


func set_playback_speed(value: float) -> void:
	player.speed_scale = clampf(value, 0.25, 2.0)
	cat.set_playback_speed(value)


func _mark_contact() -> void:
	if busy and not _contact_sent:
		_contact_sent = true
		# Method tracks may run before this frame's property values are applied.
		# Emit the latched destination, never last frame's nozzle position or a
		# newly selected target for the next cycle.
		contact_reached.emit(_cycle_target_x)


func _on_finished(completed: StringName) -> void:
	if not busy or completed != action:
		return
	busy = false
	player.stop(true)
	if completed in [&"full_drop", &"feeder"] and item_textures.size() == 3:
		# Match the visual handoff. The caller supplies a replacement for the
		# following cycle with set_items(); no gameplay queue is mutated here.
		item_textures[0] = item_textures[1]
		item_textures[1] = item_textures[2]
	_reset_visuals()
	cat.set_idle(idle_enabled)
	finished.emit(completed)


func _exit_tree() -> void:
	if is_instance_valid(player):
		player.stop()
