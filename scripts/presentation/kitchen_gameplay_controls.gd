extends Control
## Scene-authored controls, with responsive safe insets and full-bleed footer art.

@export_range(0.0, 40.0) var restart_progress_gap := 8.0

func set_safe_insets(insets: Vector4) -> void:
	for bounds in [$SafeBounds, $ExitRunModal/SafeBounds]:
		bounds.offset_left = insets.x
		bounds.offset_top = insets.y
		bounds.offset_right = -insets.z
		bounds.offset_bottom = -insets.w


func place_hold_progress(strip: Control) -> void:
	# The strip's height is responsive. Keep the ring above it at every width;
	# its size/horizontal placement remain scene-authored, gap is in the Inspector.
	var progress: Control = $SafeBounds/BottomControls/Restart/HoldProgress
	progress.global_position.y = strip.get_global_rect().position.y - restart_progress_gap - progress.size.y


func layout_footer_background(viewport_size: Vector2) -> float:
	# The buttons stay in the safe area; decoration reaches the device bottom.
	# Return this SAME seam for the machine frame, not a second height ratio.
	var seam_y: float = $SafeBounds/BottomControls.get_global_rect().position.y
	var background: Control = $SafeBounds/BottomControls/Background
	background.set_anchors_preset(Control.PRESET_TOP_LEFT)
	background.global_position = Vector2(0.0, seam_y)
	background.size = Vector2(viewport_size.x, viewport_size.y - seam_y)
	var art: Sprite2D = background.get_node("Artwork")
	# The scene region omits 8 top / 9 bottom transparent source rows.
	# A one-screen-pixel clipped bleed also excludes the antialiased outer edge.
	# The scene's navy Backing is opaque beneath the artwork's translucent rows.
	var factor := maxf(background.size.x / art.region_rect.size.x,
		(background.size.y + 2.0) / art.region_rect.size.y)
	art.scale = Vector2.ONE * factor
	art.position = Vector2((background.size.x - art.region_rect.size.x * factor) * 0.5, -1.0)
	return seam_y


func clear_press_states() -> void:
	for button in [$SafeBounds/BottomControls/PushLeft, $SafeBounds/BottomControls/Restart,
		$SafeBounds/BottomControls/PushRight, $SafeBounds/ExitRun,
		$ExitRunModal/SafeBounds/Panel/Resume, $ExitRunModal/SafeBounds/Panel/Confirm]:
		button.cancel_press()
