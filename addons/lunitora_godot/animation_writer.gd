@tool
extends RefCounted
## Closed fixture helpers. Admission, history and session state live in RigLab.

const ACTION_NAME := "Lunitora: Create Rig Lab Animation"
const NAME := &"bend_tip"
const TRACK_PATH := NodePath("Skeleton2D/Root/Tip:rotation")
const ANGLE := 0.3490658503988659
const SIGNALS := [&"animation_list_changed", &"current_animation_changed",
	&"animation_finished", &"caches_cleared"]


static func prepare() -> AnimationLibrary:
	var animation := Animation.new()
	animation.length = 1.0
	animation.step = 0.125
	animation.loop_mode = Animation.LOOP_NONE
	var track := animation.add_track(Animation.TYPE_VALUE)
	animation.track_set_path(track, TRACK_PATH)
	animation.track_set_interpolation_type(track, Animation.INTERPOLATION_LINEAR_ANGLE)
	animation.track_set_interpolation_loop_wrap(track, false)
	animation.value_track_set_update_mode(track, Animation.UPDATE_CONTINUOUS)
	animation.track_set_enabled(track, true)
	animation.track_set_imported(track, false)
	animation.track_insert_key(track, 0.0, 0.0, 1.0)
	animation.track_insert_key(track, 0.5, ANGLE, 1.0)
	animation.track_insert_key(track, 1.0, 0.0, 1.0)
	var library := AnimationLibrary.new()
	if library.add_animation(NAME, animation) != OK:
		return null
	return library


static func verify(library: AnimationLibrary) -> String:
	if library == null or library.get_class() != "AnimationLibrary" or library.get_script() != null:
		return "library"
	var names := library.get_animation_list()
	if names.size() != 1 or names[0] != NAME:
		return "animation names"
	var animation := library.get_animation(NAME)
	if animation == null or animation.get_class() != "Animation" or animation.get_script() != null:
		return "animation"
	if animation.length != 1.0 or animation.step != 0.125 or animation.loop_mode != Animation.LOOP_NONE or animation.capture_included:
		return "timing"
	if animation.get_track_count() != 1 or not animation.get_marker_names().is_empty():
		return "tracks or markers"
	if animation.track_get_type(0) != Animation.TYPE_VALUE or animation.track_get_path(0) != TRACK_PATH:
		return "target"
	if animation.track_get_interpolation_type(0) != Animation.INTERPOLATION_LINEAR_ANGLE or animation.value_track_get_update_mode(0) != Animation.UPDATE_CONTINUOUS:
		return "interpolation"
	if not animation.track_is_enabled(0) or animation.track_is_imported(0) or animation.track_get_interpolation_loop_wrap(0):
		return "flags"
	if animation.track_get_key_count(0) != 3:
		return "key count"
	var times := [0.0, 0.5, 1.0]
	var values := [0.0, ANGLE, 0.0]
	for index in range(3):
		if animation.track_get_key_time(0, index) != times[index] or typeof(animation.track_get_key_value(0, index)) != TYPE_FLOAT or animation.track_get_key_value(0, index) != values[index] or animation.track_get_key_transition(0, index) != 1.0:
			return "typed keys"
	# Interpolate the detached data, never seek or assign the live player.
	for time in [0.25, 0.75]:
		if absf(animation.value_track_interpolate(0, time) - ANGLE / 2.0) > 0.000001:
			return "interpolation samples"
	return ""


static func observers(player: AnimationPlayer) -> Array:
	var rows: Array = []
	for signal_name in SIGNALS:
		for connection in player.get_signal_connection_list(signal_name):
			var callback: Callable = connection.callable
			var receiver := callback.get_object()
			var receiver_class := receiver.get_class() if is_instance_valid(receiver) else "unknown"
			# CustomCallable method spelling may be unavailable in release builds.
			# Native receiver identity is definitive; every unclassified observer
			# also fails closed for this lab-only fixture.
			rows.append({"signal": signal_name, "class": receiver_class,
				"method": String(callback.get_method()), "flags": connection.flags,
				"native_editor": receiver_class == "AnimationPlayerEditor"})
	return rows


static func stored(object: Object, omit_libraries := false) -> Dictionary:
	var values := {}
	for property in object.get_property_list():
		if property.usage & PROPERTY_USAGE_STORAGE:
			if omit_libraries and (property.name == &"libraries" or String(property.name).begins_with("libraries/")):
				continue
			values[property.name] = object.get(property.name)
	return values.duplicate(true)


static func player_state(player: AnimationPlayer) -> Dictionary:
	return {"stored": stored(player, true), "assigned": player.assigned_animation,
		"current": player.current_animation, "playing": player.is_playing(),
		"queue": player.get_queue(), "active_animation": player.is_animation_active(),
		"position": player.current_animation_position if player.is_animation_active() else 0.0,
		"autoplay": player.autoplay}


static func pristine(player: AnimationPlayer) -> bool:
	if player.root_node != NodePath("..") or player.autoplay != &"" or player.assigned_animation != &"" or player.current_animation != &"" or player.is_playing() or not player.get_queue().is_empty():
		return false
	var defaults := AnimationPlayer.new()
	# Compare native serialized playback settings, excluding identity/metadata
	# and the separately gated library container.
	var actual := stored(player, true)
	var expected := stored(defaults, true)
	defaults.free()
	for key in expected:
		if key in [&"name", &"unique_name_in_owner", &"scene_file_path", &"owner", &"script"] or String(key).begins_with("metadata/"):
			continue
		if not actual.has(key) or actual[key] != expected[key]:
			return false
	return not player.is_animation_active()


static func scene_state(root: Node, player: AnimationPlayer) -> Array:
	var result: Array = []
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		result.append({"id": node.get_instance_id(), "path": root.get_path_to(node),
			"class": node.get_class(), "owner": node.owner, "script": node.get_script(),
			"stored": stored(node, node == player)})
		for child in node.get_children(true):
			stack.append(child)
	return result
