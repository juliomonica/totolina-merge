extends Node2D
## Responsive production composition only. No physics, queue, RNG or rewards.
const MACHINE = preload("res://scripts/presentation/machine_drop_presentation.gd")
const MYSTERY = preload("res://assets/worlds/kitchen/ui/collection/collection_mystery_bubble.png")

@export_group("Chamber Artwork")
## Source-image Y aligned with the fixed physics floor. Visual mapping only.
@export_range(1467.0, 1595.0, 1.0) var floor_edge_texture_y := 1595.0
## Keep vertical rails in front, but let bodies cover the lower corner bevels.
## Wider masks can occlude the legal resting area without moving any collider.
@export_range(56.0, 128.0, 1.0) var foreground_side_width := 56.0
@export_group("Collection Layout")
## Bubble diameter relative to its source canvas, at the 500-wide design size.
@export_range(0.05, 0.25, 0.005) var collection_icon_scale := 0.13
## Center-to-center spacing at design size.
@export_range(70.0, 140.0, 1.0) var collection_pitch := 100.0
## End padding lets endpoint bubbles clear the fixed mask artwork.
@export_range(40.0, 90.0, 1.0) var collection_end_padding := 56.0

var machine: Node2D
var rear: Control
var frame: Control
var _rear_footer: Control
var collection_viewport: Control
var collection_scroll: ScrollContainer
var collection_padding: MarginContainer
var _frame_clips: Array[Control] = []
var _footer_clips: Array[Control] = []
var next_label: Label
var current_label: Label
var pulse_label: Label
var danger_line: Line2D
var _reaction_pending := false
var _score_font_size := 28


func _ready() -> void:
	for filename in ["machine_chamber_background.png", "machine_foreground_frame.png"]:
		var layer := Control.new()
		layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(layer)
		# Split the existing texture at its trim seams, not the source artwork.
		# This lets the header/floor keep their gameplay anchors while the frame
		# extends to every viewport edge and the lower UI trough absorbs height.
		for section in [["Header", 0, 425, 1, 96], ["Chamber", 425, 1170, 96, 128], ["Footer", 1595, 236, 70, 35]]:
			var patch := NinePatchRect.new()
			patch.name = section[0]
			patch.texture = load(MACHINE.ENV + filename)
			patch.region_rect = Rect2(0, section[1], 859, section[2])
			patch.patch_margin_left = 56
			patch.patch_margin_right = 56
			patch.patch_margin_top = section[3]
			patch.patch_margin_bottom = section[4]
			patch.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
			patch.mouse_filter = Control.MOUSE_FILTER_IGNORE
			layer.add_child(patch)
		if filename.contains("background"):
			rear = layer
			rear.name = "ChamberRear"
			rear.z_index = -5
		else:
			frame = layer
			frame.name = "ChamberForeground"
			frame.z_index = 30
	# Disjoint clips of the SAME nine-patch mapping: only the lower interior is
	# behind bodies. No altered PNG, shader, duplicate-alpha overlap or physics move.
	var chamber_patch := frame.get_node("Chamber") as NinePatchRect
	for part in ["UpperRails", "LowerLeftRail", "LowerInterior", "LowerRightRail"]:
		var clip := Control.new()
		clip.name = part
		clip.clip_contents = true
		clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if part == "LowerInterior":
			clip.z_as_relative = false
			clip.z_index = -1
		frame.add_child(clip)
		clip.add_child(chamber_patch.duplicate())
		_frame_clips.append(clip)
	chamber_patch.hide() # Retained solely as the shared layout template.
	var footer_patch := frame.get_node("Footer") as NinePatchRect
	for part in ["FooterLeftRail", "LowerFrontLip", "FooterRightRail", "CollectionFrame"]:
		var clip := Control.new()
		clip.name = part
		clip.clip_contents = true
		clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if part == "LowerFrontLip":
			clip.z_as_relative = false
			clip.z_index = -1
		frame.add_child(clip)
		_add_footer_halves(clip, footer_patch.texture)
		_footer_clips.append(clip)
	footer_patch.hide()
	_rear_footer = Control.new()
	_rear_footer.name = "FooterArtwork"
	_rear_footer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rear.add_child(_rear_footer)
	_add_footer_halves(_rear_footer, rear.get_node("Footer").texture)
	rear.get_node("Footer").hide()
	machine = $Machine
	# Gameplay advances the shared timeline and its independent release clock in
	# the same physics tick. Missing/stopped cosmetics cannot lose a committed drop.
	machine.player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	machine.finished.connect(_on_finished)
	next_label = machine.get_node("TopMachine/NextLabel")
	current_label = machine.get_node("TopMachine/CurrentLabel")
	pulse_label = machine.get_node("TopMachine/PulseLabel")
	_score_font_size = machine.score_text.get_theme_font_size("font_size")
	danger_line = Line2D.new()
	danger_line.name = "DangerThreshold"
	danger_line.z_index = 35 # Never conceal the actual threshold behind frame trim.
	add_child(danger_line)


func layout(chamber: Rect2, floor_y: float, wall_thickness: float, safe: Rect2, viewport_size: Vector2, footer_bottom_y := -1.0) -> void:
	# Keep the approved safe header transform exactly: its nozzle also defines
	# the existing release/input/debug-spawn boundary. Full bleed is art only.
	var width := minf(safe.size.x, chamber.size.x + 52.0)
	var origin := Vector2(chamber.get_center().x - width * 0.5, safe.position.y)
	var art_scale := viewport_size.x / 859.0
	var header_end := origin.y + 425.0 * width / 859.0
	# Align the source inner-front edge, not the rear wall/floor seam.
	var footer_top := floor_y - wall_thickness * 0.5 + (1595.0 - floor_edge_texture_y) * art_scale
	var frame_bottom := viewport_size.y if footer_bottom_y < 0.0 else footer_bottom_y
	for layer in [rear, frame]:
		layer.position = Vector2.ZERO
		layer.size = Vector2(viewport_size.x, frame_bottom)
		var boundaries := [0.0, header_end, footer_top, frame_bottom]
		for index in range(3):
			var patch := layer.get_child(index) as NinePatchRect
			patch.position = Vector2(0, boundaries[index])
			patch.scale = Vector2.ONE * art_scale
			patch.size = Vector2(859, (boundaries[index + 1] - boundaries[index]) / art_scale)
	var chamber_patch := frame.get_node("Chamber") as NinePatchRect
	var lip_top := footer_top - 128.0 * art_scale
	var side := foreground_side_width * art_scale
	var regions := [Rect2(0, header_end, viewport_size.x, lip_top - header_end),
		Rect2(0, lip_top, side, footer_top - lip_top),
		Rect2(side, lip_top, viewport_size.x - side * 2.0, footer_top - lip_top),
		Rect2(viewport_size.x - side, lip_top, side, footer_top - lip_top)]
	for index in range(_frame_clips.size()):
		var clip := _frame_clips[index]
		clip.position = regions[index].position
		clip.size = regions[index].size
		var patch := clip.get_child(0) as NinePatchRect
		patch.position = chamber_patch.position - clip.position
		patch.scale = chamber_patch.scale
		patch.size = chamber_patch.size
	# The first 70 footer-source pixels are the inner-front lip. Its center
	# stays behind the visible bubble edge; side rails and collection trim don't.
	var front_lip_height := 70.0 * art_scale
	var footer_regions := [Rect2(0, footer_top, side, front_lip_height),
		Rect2(side, footer_top, viewport_size.x - side * 2.0, front_lip_height),
		Rect2(viewport_size.x - side, footer_top, side, front_lip_height),
		Rect2(0, footer_top + front_lip_height, viewport_size.x, maxf(0.0, frame_bottom - footer_top - front_lip_height))]
	for index in range(_footer_clips.size()):
		var clip := _footer_clips[index]
		clip.position = footer_regions[index].position
		clip.size = footer_regions[index].size
		_layout_footer_halves(clip, footer_top, frame_bottom, art_scale, viewport_size.x)
	_rear_footer.position = Vector2(0, footer_top)
	_rear_footer.size = Vector2(viewport_size.x, frame_bottom - footer_top)
	_layout_footer_halves(_rear_footer, footer_top, frame_bottom, art_scale, viewport_size.x)
	machine.position = origin
	machine.scale = Vector2.ONE * width / MACHINE.SIZE.x


func _add_footer_halves(clip: Control, texture: Texture2D) -> void:
	# Reuse the source twice with disjoint clips: top stays at the floor, bottom
	# stays at the controls seam. Crop/overlap only the dark middle, not the trims.
	for part in ["Top", "Bottom"]:
		var half := Control.new()
		half.name = part
		half.clip_contents = true
		half.mouse_filter = Control.MOUSE_FILTER_IGNORE
		clip.add_child(half)
		var art := Sprite2D.new()
		art.name = "Artwork"
		art.texture = texture
		art.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		art.centered = false
		art.region_enabled = true
		art.region_rect = Rect2(0, 1595, 859, 236)
		half.add_child(art)


func _layout_footer_halves(clip: Control, top: float, bottom: float, factor: float, width: float) -> void:
	var split := (top + bottom) * 0.5
	if bottom - top >= 105.0 * factor:
		split = clampf(split, top + 70.0 * factor, bottom - 35.0 * factor)
	var bands := [Rect2(0, top, width, split - top), Rect2(0, split, width, bottom - split)]
	for index in range(2):
		var half := clip.get_child(index) as Control
		var region := clip.get_rect().intersection(bands[index])
		half.visible = region.has_area()
		if not half.visible:
			continue
		half.position = region.position - clip.position
		half.size = region.size
		var art := half.get_node("Artwork") as Sprite2D
		art.scale = Vector2.ONE * factor
		var origin_y := top if index == 0 else bottom - 236.0 * factor
		art.position = Vector2(0, origin_y) - region.position


func release_position(world_x: float) -> Vector2:
	return Vector2(world_x, machine.to_global(Vector2(0, MACHINE.RELEASE_Y)).y)


static func collection_height(viewport_width: float) -> float:
	return MACHINE.COLLECTION_VIEWPORT.size.y * viewport_width / MACHINE.SIZE.x


func decorate_collection(panel: PanelContainer, row: HBoxContainer) -> void:
	# Keep the nine authoritative slots. A non-container clip viewport prevents
	# their minimum width expanding the HUD or shrinking the icons to fit nine.
	panel.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	var margin := panel.get_node("Margin") as MarginContainer
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 0)
	collection_viewport = Control.new()
	collection_viewport.name = "CollectionClip"
	collection_viewport.clip_contents = true
	collection_viewport.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(collection_viewport)
	collection_scroll = preload("res://scripts/presentation/touch_scroll_container.gd").new()
	collection_scroll.name = "CollectionScroll"
	collection_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	collection_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	collection_scroll.mouse_filter = Control.MOUSE_FILTER_STOP
	collection_viewport.add_child(collection_scroll)
	collection_scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	collection_padding = MarginContainer.new()
	collection_padding.mouse_filter = Control.MOUSE_FILTER_IGNORE
	collection_padding.size_flags_vertical = Control.SIZE_EXPAND_FILL
	collection_scroll.add_child(collection_padding)
	row.reparent(collection_padding)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	machine.add_collection_masks(collection_viewport)
	collection_viewport.resized.connect(_layout_collection.bind(row))
	_layout_collection(row)


func _layout_collection(row: HBoxContainer) -> void:
	var factor := collection_viewport.size.y / MACHINE.COLLECTION_VIEWPORT.size.y
	var diameter := MYSTERY.get_width() * collection_icon_scale * factor
	row.add_theme_constant_override("separation", roundi(collection_pitch * factor - diameter))
	# Endpoint padding lets the first AND final bubble clear the fixed edge masks.
	for side in ["left", "right"]:
		collection_padding.add_theme_constant_override("margin_" + side, ceili(collection_end_padding * factor))
	row.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	for slot in row.get_children():
		slot.custom_minimum_size = Vector2.ONE * diameter
		slot.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		slot.find_child("Artwork", true, false).set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.size = Vector2(row.get_combined_minimum_size().x, diameter)


func sync_items(current: Texture2D, next: Texture2D) -> void:
	if not machine.busy:
		machine.set_items(current, next, next)


func begin_drop(world_x: float) -> void:
	# A player drop interrupts a cosmetic reaction immediately. Press wins;
	# merges during a press coalesce into one reaction after the return to idle.
	var parked: Vector2 = machine.nozzle.position
	machine.reset()
	machine.nozzle.position = parked
	var local_x: float = machine.to_local(Vector2(world_x, 0)).x
	machine.target_limits = Vector2(local_x, local_x) # Already collider-safe in gameplay.
	machine.set_target(local_x)
	machine.play_action(&"full_drop")


func advance(delta: float) -> void:
	if machine.busy:
		machine.player.advance(delta)


func finish_drop() -> void:
	# Cosmetic completion is not a prerequisite for gameplay becoming ready.
	if machine.busy and machine.action == &"full_drop":
		machine._on_finished(&"full_drop")


func show_danger_line(left: float, right: float, y: float, color: Color, width: float) -> void:
	danger_line.points = PackedVector2Array([Vector2(left, y), Vector2(right, y)])
	danger_line.default_color = color
	danger_line.width = width


func show_merge_reaction() -> void:
	if machine.busy:
		_reaction_pending = true
	else:
		machine.play_action(&"excited")


func _on_finished(_action: StringName) -> void:
	if _reaction_pending:
		_reaction_pending = false
		machine.play_action(&"excited")


func reset(run_active := true) -> void:
	_reaction_pending = false
	machine.reset()
	machine.cat.set_idle(run_active)


func update_hud(score: int, pulse: int) -> void:
	var digits := "%05d" % score
	if machine.score_text.text != digits:
		machine.set_score_preview(digits)
		var font: Font = machine.score_text.get_theme_font("font")
		var width := font.get_string_size(digits, HORIZONTAL_ALIGNMENT_LEFT, -1, _score_font_size).x
		machine.score_text.add_theme_font_size_override("font_size",
			clampi(floori(_score_font_size * machine.score_text.size.x / maxf(width, 1.0)), 8, _score_font_size))
	pulse_label.text = "Pulse: %d%%" % pulse
	next_label.text = tr("DROP_NEXT")
	current_label.text = tr("DROP_CURRENT")
