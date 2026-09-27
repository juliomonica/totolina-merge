extends "res://tests/kitchen_recipe_validation.gd"

const DISPLAY_IDS = BOARD
const SPARSE_STATES = [[], [&"flour"], [&"cake_mix"], [&"wheat", &"cake_batter"],
	[&"wheat", &"flour"], [&"cake_batter"], [&"cake_batter", &"flour", &"wheat"], DISPLAY_IDS]

func _check_strip(ids: Array) -> void:
	var slots: Array = sandbox._recipe_progress_slots
	_check(slots.size() == 9 and sandbox.recipe_progress_row.get_child_count() == 9, "all nine strip slots remain")
	_check(slots.all(func(slot): return not REMOVED.has(slot.get_meta("creation_id"))),
		"retired Egg / Beaten Eggs / Milk / Cream never appear")
	for index in range(DISPLAY_IDS.size()):
		var slot: PanelContainer = slots[index]
		var id: StringName = DISPLAY_IDS[index]
		var discovered: bool = ids.has(id)
		var artwork: TextureRect = slot.find_child("Artwork", true, false)
		var unknown: TextureRect = slot.find_child("Unknown", true, false)
		_check(slot.is_visible_in_tree() and slot.get_meta("creation_id") == id and slot.get_meta("discovered") == discovered
			and artwork.texture == CONTENT.creation_for_id(id).texture
			and artwork.material == (null if discovered else sandbox.recipe_locked_silhouette_material)
			and artwork.visible == discovered and unknown.texture == sandbox.MACHINE_PRESENTATION.MYSTERY
			and unknown.visible != discovered,
			"canonical slot %d / discovery state: %s" % [index + 1, id])


func _test_collection_order() -> void:
	_check(CONTENT.collection_creations().map(func(d): return d.id) == DISPLAY_IDS, "canonical collection metadata")
	_check(CONTENT.collection_creations().map(func(d): return d.collection_order) == range(1, 10),
		"explicit collection_order is exactly 1 through 9")
	await _reset()
	var original_slots: Array = sandbox._recipe_progress_slots.duplicate()
	for ids in SPARSE_STATES:
		sandbox.discovered_creation_ids.assign(ids)
		sandbox._update_recipe_progress()
		_check_strip(ids)
		_check(sandbox._recipe_progress_slots == original_slots, "discoveries only update visuals; slot identities never move")
	# Save out-of-order sparse IDs, then reload through both existing consumers.
	sandbox.discovered_creation_ids.assign([&"cake_batter", &"flour", &"wheat"])
	sandbox._save_recipe_discoveries()
	await _reset()
	_check_strip([&"wheat", &"flour", &"cake_batter"])
	var collection: Control = load("res://scenes/menu/recipe_collection.tscn").instantiate()
	collection._discovery_save_path = save_path
	root.add_child(collection)
	await process_frame
	_check(collection.recipe_grid.get_child_count() == 9, "collection reload retains all cards")
	for index in range(DISPLAY_IDS.size()):
		var card: Control = collection.recipe_grid.get_child(index)
		_check(card.get_meta("creation_id") == DISPLAY_IDS[index]
			and card.get_meta("discovered") == [&"wheat", &"flour", &"cake_batter"].has(DISPLAY_IDS[index]),
			"collection reload canonical sparse card %d" % (index + 1))
	collection.queue_free()
	await process_frame
	for locale in ["en", "es", "zh_CN"]:
		TranslationServer.set_locale(locale)
		sandbox._update_recipe_progress()
		_check(sandbox._recipe_progress_slots[2].tooltip_text == tr("COLLECTION_UNKNOWN")
			and tr("COLLECTION_UNKNOWN") != "COLLECTION_UNKNOWN", "localized mystery slot: " + locale)
		for id in DISPLAY_IDS:
			var key := String(CONTENT.creation_for_id(id).display_name_key)
			_check(tr(key) != key, "localized creation: %s / %s" % [locale, id])
	TranslationServer.set_locale("en")
	if DisplayServer.get_name() != "headless":
		for size in [Vector2i(390, 844), Vector2i(405, 720), Vector2i(540, 960)]:
			root.size = size
			# Render the requested canvas even if the desktop clamps the window.
			root.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
			root.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
			root.content_scale_size = size
			await create_timer(0.1).timeout
			sandbox.machine_presentation.collection_scroll.scroll_horizontal = 0
			for ids in [[&"cake_mix"], [&"wheat", &"cake_batter"], DISPLAY_IDS]:
				sandbox.discovered_creation_ids.assign(ids)
				sandbox._update_recipe_progress()
				await _capture("strip_%sx%s_%d_discovered" % [size.x, size.y, ids.size()])
				_check(root.get_texture().get_image().get_size() == size, "exact portrait render size: %s" % size)
				_check_strip(ids)
				var panel: Rect2 = sandbox.recipe_progress_panel.get_global_rect()
				_check(sandbox.get_viewport_rect().encloses(panel)
					and panel.end.y <= sandbox.controls_panel.get_global_rect().position.y,
					"whole strip fits viewport above fixed controls: %s" % size)
				for slot in sandbox._recipe_progress_slots:
					var expected_diameter: float = 512.0 * sandbox.machine_presentation.collection_icon_scale * size.x / 500.0
					_check(absf(slot.size.x - expected_diameter) <= 1.0 and slot.size.x >= 50.0,
						"approved large icon size is not reduced to fit all nine: %s" % size)
				var clip: Control = sandbox.machine_presentation.collection_viewport
				_check(clip.clip_contents and panel.encloses(clip.get_global_rect())
					and sandbox.recipe_progress_row.get_global_rect().end.x > panel.end.x,
					"canonical track intentionally extends beyond the masked viewport")
				_check(clip.get_node("CollectionMasks").z_index > sandbox.recipe_progress_row.z_index
					and is_equal_approx(clip.get_node("CollectionMasks/RightMask").position.x, clip.size.x + 4.0),
					"approved masks remain above icons at both viewport edges")
			await _test_carousel_input("%sx%s" % [size.x, size.y])
		sandbox.discovered_creation_ids.assign([&"wheat", &"flour", &"cake_batter"])
	sandbox._restart_sandbox()
	await process_frame
	_check_strip([&"wheat", &"flour", &"cake_batter"])
	sandbox._enter_game_over()
	sandbox.play_again_button.pressed.emit()
	await process_frame
	_check(not sandbox.game_over and sandbox.score == 0, "Play Again resets run")
	_check_strip([&"wheat", &"flour", &"cake_batter"])


func _test_carousel_input(label: String) -> void:
	var view = sandbox.machine_presentation
	var scroll: ScrollContainer = view.collection_scroll
	var rect: Rect2 = scroll.get_global_rect()
	var before := [sandbox._piece_sequence, sandbox._rng.state, sandbox._current_creation_id]
	_check(scroll.horizontal_scroll_mode == ScrollContainer.SCROLL_MODE_SHOW_NEVER
		and scroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED
		and not scroll.get_h_scroll_bar().visible, "horizontal-only native carousel, no visible scrollbar")
	scroll.scroll_horizontal = 0
	await process_frame
	var point := rect.get_center() + Vector2(rect.size.x * 0.35, 0)
	var touch := InputEventScreenTouch.new()
	touch.index = 27
	touch.position = point
	touch.pressed = true
	root.push_input(touch, true)
	for index in range(8):
		var drag := InputEventScreenDrag.new()
		drag.index = 27
		drag.relative = Vector2(-24, 2)
		point += drag.relative
		drag.position = point
		root.push_input(drag, true)
		await process_frame
	touch.position = point
	touch.pressed = false
	root.push_input(touch, true)
	_check(scroll.scroll_horizontal > 60 and scroll.scroll_vertical == 0, "indexed touch browses horizontally, never vertically: " + label)
	await _capture("carousel_" + label + "_drag")
	# Wheel over the MASK itself must still reach the underlying ScrollContainer.
	scroll.scroll_horizontal = 0
	var wheel := InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_DOWN
	wheel.pressed = true
	wheel.position = Vector2(rect.position.x + 2, rect.get_center().y)
	root.push_input(wheel, true)
	_check(scroll.scroll_horizontal > 0, "fixed mask does not intercept mouse wheel")
	var pan := InputEventPanGesture.new()
	pan.position = rect.get_center()
	pan.delta = Vector2(4, 0)
	var previous := scroll.scroll_horizontal
	root.push_input(pan, true)
	_check(scroll.scroll_horizontal > previous, "native trackpad pan browses carousel")
	scroll.scroll_horizontal = 100000
	await process_frame
	var last: Control = sandbox._recipe_progress_slots[-1]
	_check(rect.encloses(last.get_global_rect()), "final Fancy Cake bubble fully reachable inside viewport")
	await _capture("carousel_" + label + "_last")
	# Start a drag ON the left mask, and move back toward the first slot.
	point = Vector2(rect.position.x + 2, rect.get_center().y)
	touch.position = point
	touch.pressed = true
	root.push_input(touch, true)
	previous = scroll.scroll_horizontal
	for index in range(6):
		var drag := InputEventScreenDrag.new()
		drag.index = 27
		drag.relative = Vector2(24, 0)
		point += drag.relative
		drag.position = point
		root.push_input(drag, true)
	touch.position = point
	touch.pressed = false
	root.push_input(touch, true)
	_check(scroll.scroll_horizontal < previous, "mask edge also passes indexed touch drag")
	_check([sandbox._piece_sequence, sandbox._rng.state, sandbox._current_creation_id] == before
		and sandbox._active_drop_touch_index == -1 and not sandbox._drop_cycle_active,
		"all carousel input leaves gameplay drops, queue and RNG untouched")
	scroll.scroll_horizontal = 0
	await process_frame
	_check(rect.encloses(sandbox._recipe_progress_slots[0].get_global_rect()), "first Wheat bubble fully reachable")


func _check_wheat_only_run() -> void:
	_check(sandbox._spawn_stage_index == 0 and sandbox._current_creation_id == &"wheat"
		and sandbox._raw_next_creation_id == &"wheat", "new-run DROP / NEXT / spawn stage reset to Wheat-only")
	var only_wheat := true
	for index in range(1000):
		only_wheat = only_wheat and sandbox._roll_spawn_creation_id() == &"wheat"
	_check(only_wheat, "1000 fresh-run selections remain Wheat despite previous discoveries")


func _test_discovery_spawn_independence() -> void:
	for ids in [[&"fancy_cake"], DISPLAY_IDS]:
		sandbox.discovered_creation_ids.assign(ids)
		sandbox._save_recipe_discoveries()
		var saved_hash := FileAccess.get_sha256(save_path)
		await _reset()
		_check_strip(ids)
		_check_wheat_only_run()
		_check(FileAccess.get_sha256(save_path) == saved_hash, "scene initialization does not alter discovery save")
		# Fixture an already-unlocked run. Earning the stage via real contact merges
		# is covered by spawn_stage_validation; here check reset/save separation.
		sandbox._spawn_stage_index = 2
		sandbox._restart_sandbox()
		await process_frame
		_check_strip(ids)
		_check_wheat_only_run()
		sandbox._spawn_stage_index = 2
		sandbox._enter_game_over()
		sandbox.play_again_button.pressed.emit()
		await process_frame
		_check_strip(ids)
		_check_wheat_only_run()
		_check(FileAccess.get_sha256(save_path) == saved_hash, "Restart / Play Again leave persistent save byte-for-byte unchanged")
		await _reset()
		_check_strip(ids)
		_check_wheat_only_run()



func _test_legacy_filter() -> void:
	var config := ConfigFile.new()
	config.set_value("settings", "unrelated", "preserved")
	config.set_value("recipes", "format_version", 2)
	config.set_value("recipes", "content_id", "kitchen_recipe_graph")
	config.set_value("recipes", "discovered_creation_ids", PackedStringArray(["milk", "cream", "egg", "beaten_eggs", "flour", "fancy_cake"]))
	_check(config.save(save_path) == OK, "legacy semantic fixture saved")
	await _reset()
	_check(sandbox.discovered_creation_ids == [&"flour", &"fancy_cake"], "obsolete IDs filtered; surviving discoveries retained")
	_check_strip([&"flour", &"fancy_cake"])
	sandbox._save_recipe_discoveries()
	_check(config.load(save_path) == OK and config.get_value("settings", "unrelated") == "preserved"
		and config.get_value("recipes", "discovered_creation_ids") == PackedStringArray(["flour", "fancy_cake"]),
		"next normal save drops obsolete IDs without touching unrelated settings")

func _run() -> void:
	await _test_legacy_filter()
	await _test_collection_order()
	await _test_carousel_input("native")
	await _test_discovery_spawn_independence()
	await _test_navigation()
	print("COLLECTION LIFECYCLE: %d checks, %d failures" % [checks, failures])
	quit(1 if failures else 0)
