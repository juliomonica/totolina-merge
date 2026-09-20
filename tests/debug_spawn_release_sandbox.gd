extends "res://scripts/prototype/physics_sandbox.gd"

# Test-only simulation of the native release-build probe returning false.
# Production always asks OS.is_debug_build(); no setting enables this feature.
func _debug_tools_enabled() -> bool:
	return false
