extends "res://scripts/prototype/physics_sandbox.gd"

# Test-only simulation of the native release-build probe returning false.
# Simulates an export with neither editor nor dev_tools (debug OR release).
func _debug_tools_enabled() -> bool:
	return false
