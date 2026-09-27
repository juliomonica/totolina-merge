extends Control
## Only the Fit wrappers adapt to row height. Authored edge Control offsets
## and Artwork transforms are never reset, including after scrolling/resizing.

func _ready() -> void:
	resized.connect(_fit)
	_fit()


func _fit() -> void:
	var factor := size.y / 67.0
	$LeftMask/Fit.scale = Vector2.ONE * factor
	$RightMask/Fit.scale = Vector2.ONE * factor
