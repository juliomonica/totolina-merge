# Totolina's Mystery Journey GDD

## Identity

**Studio:** Lunitora Games

**Game:** Totolina's Mystery Journey

**First gameplay world:** Kitchen

**Main character:** Tolina

**Genre:** Cozy portrait mobile physics-merging puzzle

**Platforms:**

- Android
- iOS

**Engine:** Godot 4.7 project baseline

**Product direction:**

- Portrait-first
- Touch-first
- Mobile-first
- Offline-first
- No player account required

---

# 1. Vision

Help Tolina the cat create increasingly elaborate magical cakes through a
satisfying physics-based merging puzzle.

The player drops creations into a magical bowl, combines valid recipe
pairs, discovers new creations, manages the growing pile, and tries to
reach the ultimate Fancy Cake.

Tolina is more than static presentation. She should feel expressive and
alive through reactions, animations, and a Living Home presentation,
without turning the game into a pet simulator.

The game should feel:

- cozy
- satisfying
- charming
- lightly strategic
- expressive
- rewarding to replay
- polished on mobile

---

# 2. Player Fantasy

The player helps Tolina create increasingly magical desserts while trying
to discover the complete Kitchen recipe collection.

The player should enjoy:

- discovering new creations
- improving previous attempts
- seeing satisfying physics interactions
- managing danger and using Push strategically
- completing the recipe collection
- seeing Tolina react to important accomplishments
- occasionally discovering what Tolina is doing when the game opens

The emotional connection with Tolina should come through personality and
presentation rather than maintenance mechanics.

---

# 3. Main Character

## Tolina

Tolina is the main character and mascot.

She is:

- cute
- friendly
- playful
- expressive
- slightly mischievous

Tolina communicates through:

- animations
- expressions
- gameplay reactions
- ambient Home behaviors
- celebration behaviors
- contextual interactions with simple props

The player helps Tolina.

The player does not manage Tolina as a virtual pet.

Avoid:

- hunger mechanics
- feeding systems
- relationship meters
- friendship XP
- cat health systems
- cat growth systems
- daily care obligations
- punishment for not playing
- autonomous pet simulation
- player-maintained schedules

---

# 4. Tolina Character Design

## Appearance

Tolina is inspired by a gray-and-white tabby cat.

Visual characteristics:

- soft gray fur
- darker gray tabby markings
- white chest
- white muzzle
- white paws
- large expressive eyes
- rounded cute proportions

She should feel like a beloved house cat transformed into a magical
storybook character.

## Art Style

Cute 2D storybook illustration style.

Characteristics:

- warm colors
- rounded shapes
- charming handcrafted feeling
- expressive characters
- cozy fantasy atmosphere
- readable mobile silhouettes

No required clothing or chef outfit.

The magic comes from Tolina, the environment, creations, and presentation.

---

# 5. Tolina Animation Direction

Tolina should use real animation rather than relying only on static pose
replacement.

Approved production direction:

**Spine authoring → rendered transparent PNG frames or sprite sheets →
native Godot AnimatedSprite2D playback**

Spine is an art-production tool only.

The shipped game should not require the Spine runtime.

Editable Spine source files should be preserved separately from exported
game-ready assets.

Gameplay code should trigger semantic animation names rather than depend
on individual exported frame filenames.

Examples:

- idle
- blink
- look
- happy
- throw
- sleep
- wake
- stretch
- run
- hide
- peek
- dance
- celebrate
- play_with_prop

The initial technology proof should validate:

- subtle breathing
- blinking
- tail movement
- clean looping
- mobile readability
- acceptable texture memory
- acceptable application-size impact
- correct playback through Godot AnimatedSprite2D

Tolina animations must remain presentation-only unless a future gameplay
feature explicitly requires otherwise.

Animation failure must never affect merge logic, physics, scoring, Push,
danger, or recipe progression.

---

# 6. Core Gameplay Loop

Living Home → Start Kitchen Run → Check Next Creation → Choose Drop
Position → Creation Falls Through Physics → Matching Creations Merge /
Visual-Only Baking Flavor →
Score / Push / Recipe Progress → Tolina Reacts to Meaningful Events →
Manage Growing Pile → Use Push Strategically → Game Over → Results →
Play Again or Return Home

The core gameplay remains:

**Drop → Merge → Discover → Manage → Create**

---

# 7. Gameplay Mechanics

The game uses physics-based merging.

Current core mechanics:

- horizontal drop placement
- physics-based falling and stacking
- eight physical same-item recipes
- physics-driven chain reactions
- nine semantic Kitchen creations across nine progression ranks
- score
- recipe discovery
- visible danger threshold
- three-second continuous danger grace period
- Game Over
- directional Push rescue mechanic
- deterministic seeded spawning
- data-driven run-based spawn unlocks: Wheat-only → 75/25 → 60/30/10
- three short visual-only merge flavor effects
- hold-to-restart protection

Physical same-item merges retain the validated pair replacement behavior:

- one physical pair resolves per 0.45-second cooldown
- safe placement, inherited motion and controlled expansion remain
- chains continue through actual physics contacts
- guarded live-neighbour waking prevents unsupported sleeping pieces

Do not redesign validated gameplay without testing evidence.

---

# 8. Creation Progression

## Kitchen

The Kitchen board uses one rule: **two identical pieces merge into the next
creation**, except Fancy Cake, which is final. There are nine semantic board
creations and eight physical same-item recipes; there are no mixed or automatic
board recipes.

The native `CreationDefinition`, `MergeRecipe` and
`WorldContentConfiguration` resources in
`res://config/worlds/kitchen/kitchen_content.tres` remain the source of truth.

| Size / collection order / rank | ID | Creation | Preserved growth % | Effective radius ratio |
| ---: | --- | --- | ---: | ---: |
| 1 | `wheat` | Wheat | 0 | 0.046000000 |
| 2 | `flour` | Flour | 15 | 0.052900000 |
| 3 | `cake_mix` | Cake Mix | 15 | 0.060835000 |
| 4 | `cake_batter` | Cake Batter | 15 | 0.069960250 |
| 5 | `sponge_cake` | Sponge Cake | 15 | 0.080454287 |
| 6 | `frosted_cake` | Frosted Cake | 15 | 0.092522431 |
| 7 | `layer_cake` | Layer Cake | 20 | 0.111026917 |
| 8 | `decorated_cake` | Decorated Cake | 25 | 0.138783646 |
| 9 | `fancy_cake` | Fancy Cake | 30 | 0.180418740 |

Each adjacent pair of rows defines one recipe: two of the earlier creation
produce one of the next. Results award rank² × 2: 8, 18, 32, 50, 72, 98, 128,
162 points, and +12 Push. One physical result resolves per 0.45-second cooldown.
Actual contacts, pending-source protection, safe result placement, inherited
motion, controlled expansion and guarded neighbour waking remain.

Normal drops unlock per run: **Wheat 100** initially; after merge-creating Flour,
**Wheat 75 / Flour 25**; after merge-creating Cake Mix,
**Wheat 60 / Flour 30 / Cake Mix 10**. Later creations never normally spawn.
The three configurable spawn stages live in the Kitchen world resource.
Unlocks occur at successful merge-result creation, not after settling or from
saved discoveries. Restart, Play Again and new runs always begin Wheat-only.
The existing seeded generator selects current DROP and buffered NEXT. Stage
changes never reroll either piece or consume RNG; the new weights apply only
to future selections. There is no adaptive spawn bias or crafted-result queue.

The nine collection slots always remain in `collection_order`; discovery only
changes real artwork versus the locked/mystery state. The existing semantic
save format/version remains. Both save consumers filter IDs against current
content, retaining surviving discoveries and ignoring removed identities;
the next ordinary save writes valid IDs and preserves unrelated settings.

Egg, Milk and Cream exist only as merge-flavor artwork, never as board bodies,
colliders, spawnables, recipes or discovery slots. Three recipes have optional
approved `effect_animation` names in their `MergeRecipe`:

- Flour ×2 → Cake Mix: egg bubble, then egg crack.
- Cake Mix ×2 → Cake Batter: milk bubble, then milk pour.
- Sponge Cake ×2 → Frosted Cake: cream bubble, then cream swirl.

Each effect uses the approved shared AnimationPlayer timeline: Egg 0.56s,
Milk 0.66s, Cream 0.64s, with 65ms crossfades. The lab and production use the same
pose/pivot implementation. The physical result remains visible and moves normally;
animation never delays a result/reward, moves physics nodes or makes a fake
creation. Ordinary merges retain normal merge magic. Completion only removes
the visual overlay; Restart/scene teardown stops/frees it safely.

All surviving `size_growth_percent` values were intentionally preserved, as
were base radius 0.046 and visual calibration 2.18. Removing intermediate size
steps changes effective radii cumulatively; this migration does not compensate.
See GAMEPLAY_CONFIGURATION.md before tuning.

---

# 9. Scoring and Run Rewards

Current scoring:

**result progression rank × result progression rank × 2**

Score is currently run-based.

Current persistent progression:

- discovered semantic creation IDs

Current non-persistent run state includes:

- score
- Push charge
- current pieces
- danger state
- highest creation
- seeded sequence position
- current drop and buffered NEXT
- pending physical merge pairs

For version 1.0:

- the Result Screen should display final score
- recipe discoveries should remain meaningful progression
- significant discoveries may trigger stronger Tolina reactions

Persistent best score remains a product decision until explicitly
approved.

Do not create currencies, XP, or additional progression systems merely
to increase reward complexity.

---

# 10. Living Tolina Home

The current Main Menu should evolve into a Living Tolina Home.

Purpose:

- create emotional connection
- provide the main entry point into the game
- make Tolina feel alive
- provide occasional visual surprise
- reflect player accomplishments without creating a pet simulator

The Home should remain a controlled portrait composition rather than a
large explorable environment.

Tolina may appear performing different ambient behaviors when the
application opens.

Examples:

- sleeping
- looking around
- playing with a creation bubble
- running briefly
- hiding
- peeking
- stretching
- inspecting a creation
- relaxing beside the magical bowl
- performing a rare celebration

Behavior selection should avoid obvious immediate repetition.

The system may locally remember recently displayed behaviors.

No server, account, cloud save, or online simulation is required.

---

# 11. Accomplishment Reactions

Tolina should react to player accomplishments with different levels of
intensity.

Ordinary events should receive subtle reactions or no reaction.

Examples:

### Small reaction

- ears perk up
- brief happy expression
- looks toward the bowl

### Meaningful accomplishment

- happy bounce
- excited movement
- short celebration

### Major accomplishment

Examples:

- first high-rank discovery
- first Fancy Cake creation
- completing all nine Kitchen creations

Possible responses:

- special celebration
- dance
- unique animation
- enhanced visual effect
- new Home behavior

Tolina should not perform large celebrations after every normal merge.

Important reactions should remain special and readable.

---

# 12. Progression Through Tolina Presentation

Existing recipe discovery may influence Tolina's presentation.

Examples may include:

- new ambient behavior becoming available
- new prop interaction
- stronger celebration
- subtle Home visual detail

This should reuse existing recipe progression rather than create a
separate friendship or character-level system.

Avoid:

- visible relationship meters
- friendship XP
- daily affection
- login streaks
- relationship decay

---

# 13. Game Screens

## Living Home / Main Menu

Contains or may contain:

- Tolina
- default Home environment
- ambient Tolina behavior
- Start
- Recipes
- future Settings access
- future theme selection access if approved

The Home is presentation-focused and should remain simple.

---

## Gameplay

Contains:

- Tolina presentation
- next-piece preview
- score
- Push percentage
- danger threshold and warning
- magical bowl
- physical creations
- compact nine-creation discovery strip
- Push Left
- Hold Restart
- Push Right
- temporary gameplay messages

---

## Result Screen

Current purpose:

Reward and summarize the completed run.

Current presentation includes:

- Game Over
- Tolina reaction
- highest creation artwork
- localized highest creation name
- newly discovered recipe when applicable
- Play Again

Planned for version 1.0:

- final score
- improved information hierarchy
- suitable Tolina celebration/reaction

---

## Recipe Collection

Contains:

- all nine Kitchen creation slots
- artwork for discovered recipes
- localized creation names
- silhouettes for undiscovered recipes
- Unknown state
- touch scrolling
- mouse-wheel scrolling
- Back navigation

Fresh players begin with all recipes undiscovered.

---

# 14. Audio Direction

Audio is required for production polish before release unless testing
demonstrates a strong reason otherwise.

Direction:

- satisfying merge sounds
- creation/discovery feedback
- Push feedback
- danger feedback
- cute Tolina sounds where appropriate
- cozy background music
- restrained UI sounds

Audio should reinforce:

- satisfaction
- discovery
- success
- danger readability
- warmth
- Tolina's personality

Audio must support player mute/volume controls as defined during UX
completion.

---

# 15. Cosmetic Theme Direction

Totolina's Mystery Journey may support cosmetic themes.

A theme must never provide gameplay advantage.

Themes may change selected presentation elements such as:

- Living Home environment
- gameplay background
- decorative chamber presentation
- magical bowl presentation
- ambient particles
- selected Tolina props or theme-specific ambient animations
- music or ambience where justified

Themes must not modify:

- physics
- collision sizes
- masses
- scoring
- spawn probabilities
- Push strength
- danger behavior
- merge rules
- recipe requirements
- gameplay difficulty

The default theme is included with the game.

The architecture may support multiple themes, but version 1.0 should not
require producing many themes before the game is validated.

One premium theme may be considered for launch if production cost,
testing, and schedule justify it.

Additional themes should primarily be content production rather than new
gameplay development.

---

# 16. Monetization Direction

Monetization is not currently implemented.

Preferred direction for evaluation:

- free download
- carefully controlled interstitial advertising
- optional rewarded advertising only if it provides genuine player value
- permanent Remove Ads purchase
- optional permanent cosmetic theme purchases

Principles:

**FUN → RETENTION → MONETIZATION → OPTIMIZATION**

Avoid:

- pay-to-win
- paid score advantages
- paid Push advantages
- paid spawn advantages
- energy systems
- forced waiting
- required consumables
- intrusive advertisements during active gameplay
- excessive Game Over advertising
- unnecessary currencies

Advertising placement and frequency must be validated before release.

The game should remain playable offline apart from store purchasing,
restoration, advertising, or other explicitly approved platform
services.

No Lunitora account should be required for normal gameplay.

---

# 17. Theme and World Separation

A cosmetic theme is not automatically a new gameplay world.

Examples of possible cosmetic presentation themes:

- default cozy Kitchen/Home
- Space
- Cloud Kingdom
- Sakura Garden

These may visually alter Home and selected gameplay presentation while
preserving identical gameplay.

Future gameplay worlds such as Cat Garage, Sakura Garden, or Space Cat
would represent significantly larger content expansions and are not
required for version 1.0.

Kitchen is the only required gameplay world for version 1.0.

Do not build additional gameplay worlds until the first release is
validated.

---

# 18. What Totolina's Mystery Journey Is NOT

Totolina's Mystery Journey is NOT:

- a pet simulator
- a farming game
- a restaurant management game
- a decoration-management game
- a multiplayer game
- a social game
- a currency-heavy live service
- an account-dependent game

The focus remains:

**Drop → Merge → Discover → Create**

Tolina adds personality and emotional connection without replacing the
physics puzzle as the main game.

---

# 19. Version 1.0 Product Boundary

## Existing foundation to preserve

- Tolina character
- Kitchen gameplay world
- nine Kitchen creations and eight same-item recipes
- physics merge gameplay
- Push mechanic
- danger/grace system
- score
- Recipe Collection
- persistent recipe discovery
- Android and iOS export foundation
- English, Spanish, and Simplified Chinese localization
- portrait responsive layout
- touch-first input
- offline-first behavior

## Planned release-completion work

- Living Tolina Home
- ambient Tolina animations
- meaningful accomplishment reactions
- Tolina animation pipeline validation
- lightweight onboarding
- pause / return-to-menu decision and implementation
- final score on Result Screen
- collection-completion experience
- complete gameplay localization
- audio
- settings
- accessibility review
- optional haptics
- gameplay/user testing
- mobile device QA
- release engineering
- store/compliance preparation
- beta distribution
- Android and iOS submission

## Candidate, not automatically required

- persistent best score
- one premium cosmetic theme
- rewarded ads
- theme-specific Tolina animations
- subtle automatic Home progression

These require explicit approval before implementation.

---

# 20. Explicitly Deferred Systems

Do not add to version 1.0 without a new product decision:

- hunger
- feeding
- Paw Coins
- gameplay currency
- furniture placement
- friendship levels
- cat growth
- pet-care systems
- autonomous cat simulation
- quests
- daily rewards
- login streaks
- accounts
- cloud save
- proprietary servers
- multiplayer
- additional playable characters
- additional gameplay worlds
- complex progression systems
- pay-to-win purchases

---

# 21. Product Success Criteria

The game succeeds if players feel:

> "I want to see what I create next."

and:

> "I want to see what Tolina is doing."

Primary retention drivers should be:

- satisfying physics interactions
- curiosity
- recipe discovery
- improvement across repeated runs
- meaningful high-tier accomplishments
- emotional connection with Tolina
- occasional visual surprise
- collection completion

These assumptions must eventually be validated through real player
testing rather than treated as proven.
