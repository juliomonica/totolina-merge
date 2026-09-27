extends RefCounted

# Central source of truth for gameplay chamber and presentation tuning.
# See res://docs/GAMEPLAY_CONFIGURATION.md before changing gameplay values.


# GAMEPLAY VALUES: chamber, boundaries, and spawning.
const CHAMBER_WIDTH_VIEWPORT_RATIO := 0.86
const CHAMBER_HEIGHT_VIEWPORT_RATIO := 0.72
const CHAMBER_TOP_VIEWPORT_RATIO := 0.07
const CHAMBER_MAX_WIDTH_TO_HEIGHT_RATIO := 0.67

const WALL_THICKNESS_MIN_PIXELS := 8.0
const WALL_THICKNESS_VIEWPORT_WIDTH_RATIO := 0.018
const LEFT_WALL_X_CHAMBER_RATIO := 0.0
const RIGHT_WALL_X_CHAMBER_RATIO := 1.0
const SIDE_WALL_CENTER_Y_CHAMBER_RATIO := 0.5
const FLOOR_CENTER_X_CHAMBER_RATIO := 0.5
const FLOOR_Y_CHAMBER_RATIO := 1.0

const SPAWN_HEIGHT_CHAMBER_RATIO := 0.0
const SPAWN_HORIZONTAL_INSET_PIXELS := 0.0
const SPAWN_WALL_CLEARANCE_MULTIPLIER := 0.5

# GAMEPLAY VALUES: danger detection within the chamber coordinate space.
# 0.3888888889 preserves the previous 0.35 viewport-height threshold with
# the current chamber top (0.07) and height (0.72).
const DANGER_HEIGHT_CHAMBER_RATIO := 0.3888888889
const DANGER_GRACE_SECONDS := 3.0
const DANGER_VERTICAL_SPEED_THRESHOLD := 10.0


# VISUAL VALUES: danger line and warning label.
const DANGER_LINE_INACTIVE_COLOR := Color("ffb020")
const DANGER_LINE_ACTIVE_COLOR := Color("ff3b30")
const DANGER_LINE_WIDTH := 3.0
const DANGER_LABEL_TOP_OFFSET := -42.0
const DANGER_LABEL_BOTTOM_OFFSET := 2.0
const DANGER_LABEL_SCALE := Vector2.ONE
const DANGER_TEXT_FONT_SIZE := 30
const DANGER_TEXT_COLOR := Color("ff3b30")
const DANGER_TEXT_OUTLINE_COLOR := Color("230408")
const DANGER_TEXT_OUTLINE_SIZE := 6
const DANGER_TEXT_SHADOW_COLOR := Color(0.0, 0.0, 0.0, 0.8)
const DANGER_TEXT_SHADOW_OFFSET := Vector2(2.0, 3.0)
const DANGER_TEXT_SHADOW_OUTLINE_SIZE := 2


# VISUAL VALUES: magical bowl/container.
# The current presentation uses the responsive/manual branch by default.
const BOWL_MATCH_CHAMBER_SIZE := false
const BOWL_CHAMBER_MATCH_SCALE := Vector2.ONE
const BOWL_RESPONSIVE_WIDTH_VIEWPORT_RATIO := 0.98
const DANGER_TO_BOWL_TOP_GAP_CHAMBER_WIDTH_RATIO := -0.10
const BOWL_MANUAL_SIZE_PIXELS := Vector2.ZERO
const BOWL_MANUAL_SCALE := Vector2.ONE
const BOWL_MANUAL_OFFSET_PIXELS := Vector2.ZERO
const BOWL_FLOOR_TEXTURE_Y_RATIO := 0.80
const BOWL_VISUAL_FLOOR_OFFSET_PIXELS := 0.0


# VISUAL VALUES: ingredient artwork. The sequential size curve and artwork
# calibration live in res://config/worlds/kitchen/kitchen_content.tres.
const INGREDIENT_GLOBAL_VISUAL_SCALE := 1.0
const INGREDIENT_VISUAL_OFFSET_PIXELS := Vector2.ZERO
const INGREDIENT_PREVIEW_SCALE := 1.0


# VISUAL VALUES: existing gameplay HUD and mobile safe-area layout.
const UI_EDGE_MARGIN_PIXELS := 16.0
const HUD_HEIGHT_PIXELS := 88.0
const RECIPE_PROGRESS_HEIGHT_PIXELS := 46.0
const RECIPE_PROGRESS_CONTROLS_GAP_PIXELS := 6.0
const RECIPE_PROGRESS_SLOT_MINIMUM_SIZE := Vector2(24.0, 34.0)
const RECIPE_PROGRESS_ARTWORK_INSET_PIXELS := 2.0
const RECIPE_PROGRESS_UNKNOWN_FONT_SIZE := 12
const TOLINA_SAFE_SIZE := Vector2(90.0, 96.0)
const TOLINA_HUD_GAP_PIXELS := 10.0
