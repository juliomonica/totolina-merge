# GAME DESIGN INPUT DOCUMENT

**Product:** Totolina Merge
**Studio:** Lunitora Games
**Current world:** Kitchen
**Current character:** Tolina
**Document purpose:** Input for UX flows, wireframes, visual prototypes, UI systems, player-experience design, and developer handoff
**Source of truth:** The current playable project, its assets, localization, configuration, and approved P7.0 product-scope decisions

## How to Use This Document

This document describes both the game that exists now and the product direction approved or considered around it. Designers must keep those categories separate.

| Label | Meaning |
| --- | --- |
| **IMPLEMENTED** | Present in the current project and should be represented accurately. |
| **CONFIRMED** | Approved product identity or design direction, even if implementation is incomplete. |
| **RECOMMENDED** | A UX/design response to a current gap. It requires approval before becoming implementation scope. |
| **CANDIDATE** | A product direction worth designing or testing, but not automatically required for version 1.0. |
| **POSSIBLE FUTURE** | An expansion idea, not a requirement for current flows or prototypes. |
| **OUT OF SCOPE** | Explicitly absent from the current product direction. Do not introduce it through UI concepts. |

The current project is the authority when this document conflicts with
older design examples. The Kitchen now uses nine semantic creations,
eight physical same-item recipes, and nine progression ranks in one
linear board ladder.

---

## 1. Game Identity

### Product identity

| Topic | Design input |
| --- | --- |
| Game name | **Totolina Merge** |
| Studio/brand | **Lunitora Games** |
| Main character | **Tolina** |
| First gameplay world | **Kitchen** |
| Genre | Cozy mobile physics-merging creation puzzle |
| Format | Portrait, touch-first, short-session, offline-first mobile game |
| Fantasy/theme | Help Tolina combine simple ingredients into increasingly magical cakes inside an enchanted Kitchen. |

### Main player promise

Every drop can become part of something more delightful. The player helps an expressive cat transform familiar treats into spectacular magical creations through understandable, tactile physics.

### Intended emotional experience

The experience should move through a gentle emotional rhythm:

1. **Welcome and warmth** — Tolina and the environment make the player feel invited.
2. **Curiosity** — the next piece, locked creations, Tolina’s ambient behaviors, and visual recipe evolution create anticipation.
3. **Satisfaction** — matching pieces, chain reactions, score increases, and creation reveals feel rewarding.
4. **Tension without hostility** — the rising pile and danger zone create pressure, but the presentation remains playful rather than punitive.
5. **Pride** — the result experience celebrates the player’s highest creation, score, discoveries, and major accomplishments.
6. **“One more try” optimism** — failure should feel like the end of a cooking attempt, not a harsh loss.
7. **Character attachment** — the player should occasionally wonder what Tolina is doing when the app opens.

### Main differentiators

- A physics-merging loop framed as helping a named, expressive character rather than manipulating abstract objects.
- A visible recipe-discovery ladder that turns merges into collectible creation moments.
- A strong transformation arc from Wheat, Flour, and Cake Mix to the Fancy Cake.
- A limited directional **Push** that gives players a rescue and pile-shaping decision without removing physics.
- A warm, storybook magical Kitchen with an ornate bowl that makes the playfield part of the fantasy.
- A result presentation that showcases what was created rather than emphasizing failure alone.
- A **Living Tolina Home** that makes the character feel active and expressive without introducing pet-simulation mechanics.
- Tolina reactions tied to meaningful creation and collection accomplishments.
- Cosmetic presentation themes that can alter the Home and selected gameplay presentation without altering gameplay balance.

### Identity guardrails

- Tolina is a friendly helper and emotional companion, not a pet-maintenance system.
- The game is not a restaurant manager, farming game, decoration simulator, or social/live-service game.
- Cozy does not mean consequence-free: spatial planning, danger, and recovery remain meaningful.
- Kitchen is the only gameplay world required for version 1.0.
- A cosmetic theme is not automatically a new gameplay world.
- Tolina may feel alive through authored ambient behaviors, but the game must not become an autonomous pet simulation.

---

## 2. Target Player

### Target audience

**Design hypothesis pending formal audience research:**

- Mobile players who enjoy cozy games, merge puzzles, light spatial strategy, cute characters, collection completion, and short replayable sessions.
- Broad teen and adult casual audience, with family-friendly subject matter and presentation.
- Players who want immediate play without accounts, extensive tutorials, or long-term management obligations.
- Secondary audience: score-oriented puzzle players attracted by placement mastery, chain reactions, and recovery decisions.

No child-directed product classification, age rating target, or demographic segmentation is currently defined. These require separate product and compliance decisions.

### Player motivations

- Discover the next creation and reveal its artwork/name.
- Complete the nine-creation Kitchen collection.
- Reach a higher progression rank than in the previous run.
- Improve score and make efficient merge chains.
- Keep the bowl safe under increasing spatial pressure.
- See Tolina react positively to successful creations.
- Discover different Tolina Home behaviors.
- Create a visually impressive final pile and result showcase.

### Expected session length

The game has no timer; a run ends when the pile remains in danger through the grace period. Session length therefore depends on player skill and merge efficiency.

**Recommended initial design target:** approximately **3–8 minutes per run**, with first attempts potentially shorter and skilled runs longer. This is a product assumption, not a measured result. Validate it through device playtests before designing retention pacing around it.

### Player expectations

- Immediate, responsive control after choosing a drop position.
- Consistent collision and merge behavior that feels physically credible.
- Clear correspondence between the visible danger line and actual danger.
- Understandable feedback for discoveries, Push readiness, game over, and restart.
- Progress retained between sessions without requiring a login.
- Legible UI on notched portrait phones and in all supported languages.
- No surprise interruption during an active physics moment.
- Cosmetic purchases, if implemented, must not affect gameplay advantage.

### Casual/core classification

**Casual with light skill mastery.** The input is simple enough for one-handed play, while drop placement, next-piece planning, Push direction, pile reading, and danger recovery support repeated skill improvement.

---

## 3. Core Gameplay Loop

### Repeating moment-to-moment loop

1. Read the **DROP** (current piece), **NEXT** (upcoming piece) and current pile.
2. Tap a horizontal location over the bowl.
3. Tolina presents a throwing reaction and the creation drops.
4. Physics determines its fall, rotation, collisions, and resting position.
5. Two identical board pieces merge into the next creation through physical contact; Fancy Cake is final. Three merges receive visual-only baking flavor.
6. Receive score, +12 Push charge and discovery feedback once per physical merge.
7. Tolina may react more strongly to meaningful accomplishments.
8. Reassess the pile, danger state, and next preview.
9. Use Push when fully charged if reshaping or rescue is valuable.
10. Repeat until the danger condition persists and the run ends.

### Main action

Choose where to drop the next creation into the bowl.

### Short-term goal

Create matching-piece contacts while preserving space and avoiding a dangerous pile near the top of the bowl. Every non-final identical pair follows the same next-creation rule.

### Long-term goal

- Within a run: reach higher progression ranks, maximize score, and create the Fancy Cake.
- Across runs: discover all nine Kitchen creations in the persistent Recipe Collection.
- Across sessions: see Tolina react to accomplishments and experience a small variety of Living Home behaviors.

### Why players continue

- The next merge is always visually and mechanically close.
- Locked recipe slots create clear curiosity gaps.
- Higher-rank creations become larger and more elaborate.
- A failed run preserves discoveries and provides a clear personal target for replay.
- Score, highest creation, pile variation, and Push decisions support self-improvement after the collection is known.
- Tolina’s personality adds a second layer of curiosity without requiring pet-management mechanics.

---

## 4. Main Gameplay Mechanics

### Core mechanics — implemented

| Mechanic | Player-facing behavior | Design implication |
| --- | --- | --- |
| Horizontal drop placement | A tap/click chooses the horizontal spawn point; the piece is clamped inside the chamber. | The valid drop region must be visually obvious without requiring a cursor guide. UI must not steal intended bowl taps. |
| Physics simulation | Creations fall, rotate, collide, stack, and settle immediately. | Artwork must remain readable at varied rotations and in dense overlaps. Visuals must not imply a different collision boundary. |
| Recipe-driven creation | Nine board stages; eight identical-input contact recipes, one result per 0.45-second cooldown. Safe placement and neighbour waking remain. | One rule throughout: same + same = next, with Fancy Cake final. |
| Paced chain reactions | Merge resolution is paced by a 0.45-second global cooldown; physics continues. | Feedback should help players perceive each step without making the sequence feel stalled. |
| Score | A merge awards `result progression rank² × 2`; score resets each run. | Score feedback should communicate progress without dominating discovery and survival. |
| Recipe discovery | The first appearance of a semantic creation permanently unlocks it locally. | Discovery feedback must feel special and must not repeat for already unlocked creations. |
| Danger and grace | A supported/settled piece above the visible threshold starts danger. Continuous danger for 3 seconds ends the run; recovery cancels it. | Danger communication must distinguish a temporary warning from a completed game over. |
| Directional Push | Every merge adds 12 charge. At 100%, the player can Push left or right; charge returns to 0. | Disabled, charging, ready, pressed, and consumed states must be visually distinct. |
| Hold-to-restart | Restart requires a one-second hold. Releasing early cancels. Active feedback appears above the finger area. | The button stays visually clean while idle; hold progress must be legible during touch. |

### Kitchen recipe graph — implemented

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
These configurable stages teach the opening through actual matching merges.
Unlocks happen when a merge result is created, without a settling delay.
Permanent collection progress never unlocks a fresh run's pool; Restart,
Play Again and new runs return to Wheat-only.
The controlled DROP and buffered NEXT do not change on unlock. Only future
selections use the new weights through the existing seeded RNG, with no rerolls,
adaptive spawn bias or crafted-result queue. No new teaching UI is required.

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

### Supporting mechanics

- DROP preview for the current creation; NEXT for the buffered board ingredient.
- Short visual-only Egg/Milk/Cream flavor on three same-item merges.
- Tolina pose changes: idle, throw, and happy.
- Brief merge-magic effect.
- Brief **NEW CREATION!** feedback for first discoveries.
- Brief **MAX MERGE!** feedback when Fancy Cake is created.
- In-game nine-slot neutral discovery progress strip.
- Result overlay showing the run’s highest creation and an applicable new recipe.
- Persistent offline Recipe Collection.

### Player decisions

- Where to place the next piece horizontally.
- Whether to create an immediate match or prepare a future one.
- Which side of the bowl can safely absorb more mass.
- How to use the next-piece information.
- Whether to spend a full Push charge now or preserve it for danger.
- Which Push direction creates useful space or contacts.
- Whether to continue the run or intentionally hold Restart.

### Failure condition

Game over occurs when the qualifying pile remains above the danger threshold continuously for three seconds. New spawning and Push activation stop; physics bodies are safely frozen and the result overlay appears.

### Success conditions

There is no terminal “win” state in the current game. Success is layered:

- Complete a useful merge.
- Discover a new recipe.
- Reach a new personal highest progression rank.
- Create Fancy Cake, the final Kitchen creation.
- Improve the run score.
- Discover all nine Kitchen creations.

Fancy Cake creation is a major milestone, but the run continues and multiple Fancy Cake pieces may exist.

---

## 5. Player States

| State | What the player sees/knows | UX need |
| --- | --- | --- |
| First launch | Main Menu; Recipe Collection may be entirely locked. No account or setup flow. | The value of **Start** and **Recipes** must be immediately clear. Brand, Tolina, and Kitchen should establish context in seconds. |
| New player | Enters gameplay with no dedicated tutorial. Wheat, Flour, and Cake Mix may unlock as they first appear. | Core drop action, recipe rules, danger, Push charge, and hold Restart currently rely heavily on inference. A lightweight onboarding concept is recommended for testing. |
| Active gameplay | Next preview, score, Push percentage, bowl, recipe strip, and controls are visible. | Maintain a strong visual hierarchy: pile first, next/danger second, progress and score third. |
| Merge resolution | A valid recipe pair transforms; score and charge increase; magic/Tolina feedback plays. | Preserve spatial continuity and make the resulting creation legible. |
| First discovery | **NEW CREATION!**, happy Tolina, magic, and progress-strip reveal. | Celebrate without pausing or obscuring the next required action. |
| Push charging | Push buttons unavailable until 100%. | Make progress and unavailable state understandable without looking broken. |
| Push ready | Charge shows 100%; left/right Push become actionable. | Readiness should be obvious in peripheral vision. |
| Near failure | **DANGER** appears at the exact threshold while the pile remains physically active. | Communicate urgency, remaining recoverability, and line meaning without panic-heavy styling. |
| Recovered | Danger feedback disappears when the pile clears the condition. | Recovery should feel relieving; avoid implying the run was reset or rewarded. |
| Game over | Dimmed gameplay and a dedicated result showcase with Tolina, highest artwork/name, optional new recipe, and Play Again. | Emphasize achievement first, then replay. Clearly explain what persisted. |
| Returning player | Main Menu and Recipe Collection reflect locally saved discoveries. | The collection should provide continuity without requiring a profile or account. |
| Living Home — planned 1.0 | Tolina appears in the Home performing one of several authored ambient behaviors. Existing recipe progress may influence available behaviors. | Create variety and emotional connection without implying hunger, friendship meters, schedules, or persistent simulation. |
| Collection complete | All nine creations show artwork and names. | Explore a one-time celebration and/or special Tolina response. Do not add another progression system solely to extend the collection. |

---

## 6. Level / Session States

Totolina Merge currently has one endless-style Kitchen session rather than authored levels.

### Initial state

- Score: 0.
- Push charge: 0%.
- No active pieces.
- Danger inactive.
- Highest creation for the run reset.
- Seeded next-piece sequence reset to its initial state.
- Persistent recipe discoveries retained.

### Active gameplay state

- The player repeatedly drops Wheat, Flour, and Cake Mix pieces.
- Merges generate deeper recipe creations, points, and Push charge.
- The pile becomes denser and harder to manage through natural spatial accumulation.
- First discoveries update the persistent collection and in-game strip.

### Difficulty changes

There is no level-based difficulty curve. Pressure emerges from:

- Decreasing free space as the pile grows.
- Increasing physical size at higher progression ranks, especially Decorated Cake and Fancy Cake.
- The need to preserve match opportunities in an irregular pile.
- The danger threshold and three-second recovery window.
- Limited Push availability, earned only through merging.

The drop distribution, gravity, threshold, grace duration, and merge rules do not ramp during a run.

### End state

- Continuous danger reaches three seconds.
- New drops and Push activation stop.
- Gameplay pieces freeze.
- Result overlay presents Game Over, Tolina, highest creation artwork/name, optional newly discovered recipe, and Play Again.
- Discoveries remain saved; run score and run state do not persist.

### Replay state

**Play Again** or a completed hold Restart starts a fresh run using the same deterministic initial sequence. Discoveries persist; score, pieces, danger, Push charge, and highest creation reset.

---

## 7. Progression Systems

### Implemented progression

| System | Persistence | Current scope |
| --- | --- | --- |
| Recipe discovery | Persistent offline | One semantic-ID unlock per nine Kitchen creations. |
| Recipe Collection | Persistent offline presentation | Discovered creations show artwork and localized names; unknown creations show locked silhouettes and an unknown label. |
| In-run recipe graph | Per run | Ten unordered recipes across nine progression ranks, with Fancy Cake as the final creation. |
| In-run highest creation | Per run | Used in the result showcase. |
| Score | Per run | Resets on replay/restart; no best-score persistence. |
| Push charge | Per run | Earned through merges, consumed by Push, reset on replay/restart. |

The save format is intentionally lightweight and local. A fresh player
has no forced unlocks; Wheat, Flour, and Cake Mix remain locked until each
actually appears in gameplay. Versioned semantic IDs prevent the retired
integer-tier save from unlocking unrelated new creations.

### Characters

**CONFIRMED:** Tolina is the main character and emotional face of Totolina Merge.

**CONFIRMED 1.0 DIRECTION:** Tolina may gain additional ambient Home behaviors and accomplishment reactions. Existing recipe discoveries may influence which presentation behaviors are available.

This is presentation progression, not character-stat progression.

**NOT IMPLEMENTED / OUT OF SCOPE:** Character stats, friendship XP, feeding, hunger, growth stages, relationship maintenance, wardrobes, or pet-management progression.

### Worlds

**CONFIRMED:** Kitchen is the first and only gameplay world required for version 1.0.

Cosmetic presentation themes are separate from gameplay worlds. A theme may change the Living Home, background, decorative chamber treatment, bowl presentation, ambience, or selected Tolina props while preserving identical gameplay.

**NOT IMPLEMENTED:** Additional gameplay worlds, world selection, world map, or cross-world progression.

### Achievements

No achievement system exists or is confirmed. Discovery milestones and Fancy Cake creation already supply achievement-like moments without a separate system.

### Progression design guardrails

- Do not invent currency, experience points, energy, stars, quests, or daily streaks in current prototypes.
- Do not imply cloud synchronization or account-bound gameplay progression.
- Do not add a separate friendship/progression system merely to make Tolina feel more alive.
- If future worlds are explored, preserve the understandable relationship of **world → themed creation ladder → collection**.

---

## 8. Rewards Systems

### Current player rewards

| Reward | Timing | Feedback |
| --- | --- | --- |
| Successful merge | Immediate | Result artwork, merge magic, Tolina happy pose, rank-based points, and +12 Push charge. |
| First recipe discovery | Immediate, once per semantic creation | **NEW CREATION!**, creation reveal in the progress strip, saved collection unlock, happy Tolina. |
| Maximum creation | On creating Fancy Cake | **MAX MERGE!** for approximately one second. |
| Push readiness | At 100% charge | Push controls become available. |
| Danger recovery | When the pile becomes safe | Warning clears and play continues. |
| End-of-run showcase | At game over | Highest creation artwork and localized name; applicable new recipe; Tolina reaction; Play Again. |
| Collection completion | Across sessions | All nine artwork/name cards visible. Dedicated completion treatment remains to be designed. |

### Celebration principles

- Celebrate transformation, discovery, and craftsmanship—not only score.
- Keep active-play celebrations brief and non-blocking.
- Preserve the physical location and identity of the result so the player understands what happened.
- Reserve the strongest hierarchy for first discoveries, Fancy Cake, and collection completion.
- Avoid stacking multiple banners so heavily that they obscure the next drop or danger state.
- Tolina should react more strongly to meaningful accomplishments than to ordinary merges.

### Retention hooks currently present

- Nine-slot curiosity gap.
- Persistent recipe reveals.
- Score and highest-rank self-improvement.
- Variable physics outcomes from player placement.
- Tolina’s reactions and the desire to create the final magical cake.

### Retention hooks planned or being explored

- Living Tolina Home with authored ambient behavior variety.
- Achievement-sensitive Tolina reactions.
- Collection-completion celebration.
- Cosmetic themes that change presentation without changing gameplay.

### Retention hooks not present

No daily reward, streak, quest, battle pass, time gate, energy, rotating event, social leaderboard, or live content exists. Do not show these in baseline wireframes.

---

## 9. Required Screens

### Current required screen inventory

| Screen | Status | Purpose | User goal | Main components | Important interactions | Required information |
| --- | --- | --- | --- | --- | --- | --- |
| Main Menu / Kitchen Entrance | IMPLEMENTED | Establish identity and provide entry routes. | Start playing or view recipes. | Kitchen background, Lunitora Games, Totolina Merge title, Kitchen subtitle, Tolina, magical bowl, Start, Recipes. | Tap Start; tap Recipes. | Game identity, current world, two clear destinations. |
| Gameplay | IMPLEMENTED | Host the full drop/merge survival session. | Resolve recipes, discover creations, score, and avoid overflow. | Tolina, Next preview, Score, Push %, danger line/label, bowl and pieces, creation progress strip, left/right Push, hold Restart. | Tap drop position; activate Push left/right when ready; hold Restart for one second. | Next piece, score, Push charge/readiness, danger state, collection progress. |
| Game Over / Result Overlay | IMPLEMENTED | Turn failure into a creation showcase and replay decision. | Review achievement and begin a fresh run. | Dim layer, Game Over, Tolina reaction, highest creation image/name, optional new recipe, Play Again. | Tap Play Again. | Highest creation and any newly discovered recipe. Current overlay does not include run score. |
| Recipe Collection | IMPLEMENTED | Show persistent Kitchen discoveries. | Review unlocked creations and understand what remains unknown. | Title, vertically scrollable two-column card grid, nine cards, fixed Back button. | Touch-drag or mouse-wheel scroll; tap Back. | Discovered art/name; locked silhouette and localized Unknown state. |

### Screens to explore or evolve for production

| Screen or overlay | Status | Why it may be needed | Scope boundary |
| --- | --- | --- | --- |
| Living Tolina Home evolution | CONFIRMED 1.0 DIRECTION | The current Main Menu should evolve into a more expressive Home where Tolina can perform varied ambient behaviors. | One controlled portrait environment; no exploration, pet simulation, feeding, or autonomous world AI. |
| First-run teaching overlay | RECOMMENDED FOR TESTING | The game currently has no explicit explanation of drop, merge, danger, Push, or hold Restart. | Use progressive, dismissible instruction in context; do not build a tutorial campaign. |
| Pause / system-interruption treatment | RECOMMENDED | Mobile interruptions and an intentional route out of an active run are not currently designed. | Requires product decision about whether pausing is allowed and whether exiting abandons a run. |
| Settings | RECOMMENDED BEFORE PRODUCTION | A production mobile game needs final audio/accessibility/language/legal treatment. | Do not include fake toggles before the supporting systems exist. |
| Collection-complete moment | RECOMMENDED FOR EXPLORATION | The nine-creation goal currently ends without a dedicated acknowledgment. | Celebration only unless future progression is separately approved. |
| Theme selection | CANDIDATE | Cosmetic themes may require a simple way to preview/select owned themes. | Do not design a full Store/economy system until the theme catalog and monetization implementation are approved. |

### Screens not required in the current product

- Currency or rewards wallet.
- Character selection.
- World map.
- Achievement list.
- Daily missions.
- Account/login.
- Social/leaderboard screens.

A lightweight theme selection or purchase surface may be added later if cosmetic IAP is approved for implementation.

---

## 10. Screen Navigation Flow

### Current hierarchy

```text
Application launch
└── Main Menu / Kitchen Entrance
    ├── START
    │   └── Gameplay
    │       ├── Hold Restart complete ──> Fresh Gameplay Run
    │       └── Game Over
    │           └── Result Overlay
    │               └── PLAY AGAIN ─────> Fresh Gameplay Run
    └── RECIPES
        └── Recipe Collection
            └── BACK ───────────────────> Main Menu
```

There is currently no in-game route to Main Menu and no Result Overlay route to Main Menu or Recipe Collection.

### Planned Home evolution

For version 1.0, the Main Menu is expected to evolve into the **Living Tolina Home** while preserving simple navigation into gameplay and Recipes.

The Home must remain a controlled presentation screen, not an explorable pet-simulation level.

### Primary user journeys

#### First-session journey

1. Launch to Main Menu / Living Home.
2. Understand game title, Kitchen setting, and Tolina.
3. Tap Start.
4. Learn through play: place, merge, discover, and respond to danger.
5. Reach Game Over.
6. Review highest creation, final score once added, and any newly discovered recipe.
7. Tap Play Again or use the future approved route back Home.

#### Collection-curiosity journey

1. Launch or return to Home.
2. Tap Recipes.
3. Scroll through nine Kitchen slots.
4. Compare discovered artwork with locked unknown cards.
5. Tap Back.
6. Start a run to pursue unknown recipes.

#### Returning-player journey

1. Launch to a familiar but slightly varied Living Home.
2. Tolina performs an authored ambient behavior chosen from available behaviors.
3. Optionally review saved Recipe Collection.
4. Start a new run with collection progress retained.
5. Pursue a missing creation, higher rank, or better score.

#### Danger-recovery journey

1. Pile crosses into visible danger.
2. Danger warning appears while physics continues.
3. Player makes a strategic drop or uses a charged directional Push.
4. If the pile clears the condition, warning disappears and the run continues.
5. If danger persists for three seconds, Result Overlay appears.

### Transition principles

- Home → Gameplay should feel like entering the bowl activity, with minimal loading or ceremony.
- Gameplay → Result should preserve context by overlaying the final bowl rather than visually discarding it.
- Result → Play Again should be immediate.
- Home ↔ Collection should share the same product identity.
- Any future transition to Home from an active run must explicitly handle accidental run loss.
- Cosmetic theme selection must not delay access to gameplay.

---

## 11. UI Components

| Component | Purpose | Behavior | Required states |
| --- | --- | --- | --- |
| Primary button | Highest-priority navigation or replay action. | Large touch target; clear pressed feedback; localized label. | Default, pressed, focused if relevant, disabled if needed. |
| Secondary button | Lower-priority navigation such as Recipes or Back. | Visually subordinate but fully legible and accessible. | Default, pressed, focused, disabled if used. |
| Directional Push button | Applies Push left or right when charge is full. | Does nothing while unavailable; activates once per full charge; must communicate direction. | Charging/disabled, ready, pressed, consumed, blocked by Game Over. |
| Hold Restart control | Prevents accidental run reset. | Quick tap does nothing; hold shows instruction/progress above the finger; early release cancels; completion resets run. | Idle clean label, holding/progress, cancelled, completed. |
| Next-piece preview | Allows placement planning. | Updates immediately after each spawn from the same weighted Kitchen content data used by gameplay. | Wheat, Flour, Cake Mix. |
| Score HUD | Shows current run score. | Updates after every merge; resets on replay/restart. | Zero, updating, large-number layout. |
| Push charge indicator | Shows progress toward 100%. | Adds 12 per merge, clamps at 100%, resets on Push/restart. | 0–99%, ready at 100%, consumed. |
| Danger threshold line | Shows the exact gameplay threshold. | Fixed to chamber coordinates and device-independent relative to the bowl/chamber. | Normal line, danger-active emphasis if designed. |
| Danger warning label | Communicates active recoverable risk. | Appears only while danger is active; disappears on recovery; must remain legible over varied artwork. | Hidden, active, Game Over superseded. |
| Tolina presentation — current | Gives emotional context and action acknowledgment. | Current implementation uses idle, throw, and happy pose swaps. | Idle, throw, happy. |
| Tolina animation playback | CONFIRMED 1.0 DIRECTION | Plays authored ambient and reaction animations using native Godot `AnimatedSprite2D` / `SpriteFrames`. | Idle/looping, one-shot reaction, celebration, interruption/transition behavior, reduced-motion response if required. |
| Creation body visual | Represents one semantic creation inside a circular bubble. | Rotates and moves with physics; art is replaceable independently from the explicit circular collision. | Nine creation identities; normal or physically merge-pending. |
| Current / upcoming drop | Preserves player placement and planning. | DROP retains the controlled piece. NEXT shows buffered board ingredient. | Current and upcoming. |
| Optional merge flavor | Adds baking character without changing the matching rule. | Approved Egg on Flour ×2 (0.56s), Milk on Cake Mix ×2 (0.66s), Cream on Sponge ×2 (0.64s). Shared lab/production timelines; physical result/rewards are immediate. | Arrival, blended action poses, fade, cleaned up. |
| Merge magic effect | Brief visual confirmation at merge position. | Appears briefly; no physical effect. | Hidden, playing. |
| Discovery notification | Announces a first-time unlock. | Brief, non-modal, localized, does not pause play. | Hidden, New Creation. |
| Final-creation notification | Announces Fancy Cake creation. | Brief, non-modal, does not pause play. | Hidden, Max Merge. |
| Creation progress slot | Shows persistent discovery progress during gameplay without implying a linear merge chain. | Reveals art when unlocked and briefly highlights on discovery. | Locked silhouette/?, discovered, newly discovered highlight. |
| Recipe collection card | Displays one persistent recipe entry. | Discovered shows art/name; locked hides identity and shows Unknown. | Locked, discovered; selected state not currently needed. |
| Scroll container | Makes all nine creation cards reachable. | Supports touch drag and mouse wheel while Back remains fixed. | Top, middle, bottom; drag interaction. |
| Result overlay/panel | Summarizes the run and blocks underlying gameplay interaction. | Appears after Game Over and remains until Play Again or future approved navigation. | Highest actual creation identity; with or without a new recipe. |
| Safe-area container | Keeps important UI clear of notches, Dynamic Island, home indicator, and edges. | Recalculates from platform-safe bounds. | Narrow/tall phone, wider phone, tablet-like aspect. |

### Component-system guidance

- Use a small semantic hierarchy: primary action, secondary action, gameplay action, status, warning, reward.
- Preserve large rounded shapes, dark translucent plum surfaces, gold accents, cream text, and pink/magenta action emphasis.
- Define text styles by role rather than per screen: title, section title, HUD value, button, body, warning, reward, card label, unknown label.
- Define consistent outline/shadow behavior for text over illustrated backgrounds.
- Do not rely on color alone for locked, ready, danger, or disabled states.
- Specify touch hit areas separately from visible button bounds when needed.
- Tolina animation controls should remain semantic: gameplay/UI requests a behavior such as `happy` or `dance`, not individual image frames.

---

## 12. Visual Design Direction

### Art style

- Cute 2D storybook illustration with a polished mobile-game finish.
- Rounded silhouettes, expressive faces, soft materials, and handcrafted detail.
- Cozy fantasy rather than realistic cooking.
- Rich illustrated assets paired with simple, legible UI geometry.

### Color direction

- Warm amber, honey, caramel, and golden-orange environment base for the default Kitchen presentation.
- Pink, magenta, lavender, and pearlescent highlights for magic and interaction.
- Deep plum/brown translucent UI panels for contrast without breaking the mood.
- Cream/white primary text with strong outlines or shadows.
- Gold trim for reward, quality, and magical emphasis.
- Red/orange danger treatment, always reinforced by text/symbol/position rather than color alone.

Future cosmetic themes may use different environment palettes while preserving interaction readability and semantic UI hierarchy.

### Mood

Welcoming, whimsical, celebratory, tactile, and slightly mischievous. Pressure should feel like an overflowing magical cooking experiment—not an emergency alarm from another genre.

### Character style

Tolina is a gray-and-white, large-eyed, rounded cat with an immediately readable face and compact chibi proportions. She should feel like she is watching and helping. Her expressions carry warmth and feedback, but should not obscure the gameplay bowl or HUD.

Current pose set:

- Idle: normal observing state.
- Throw: brief spawn/action state.
- Happy: merge, discovery, and result celebration.

Planned expressive behaviors may include:

- blink/look
- subtle breathing
- tail movement
- sleep
- wake
- stretch
- run
- hide
- peek
- play with a prop
- happy bounce
- dance
- major creation celebration

Avoid dressing Tolina in systems-heavy identity signals such as equipment rarity, stats, or unlockable roles unless a future character direction is approved.

### Environment style

- A warm, lived-in magical Kitchen with shelves, jars, plants, ingredients, wood, and softly textured walls.
- The magical bowl is the dominant play object: glossy, pearlescent, pink/lavender, glowing, with gold and cat-paw details.
- The danger zone sits visibly above the bowl rim to communicate overflow.
- Decorative background detail must not compete with creation recognition, danger, or controls.
- The Living Home should be a beautiful controlled portrait composition rather than an explorable environment.

### Creation style

- Wheat is the opening drop; Flour and Cake Mix become normal spawnables only after being merge-created in the current run (ranks 1–3).
- Derived creations should become visually more elaborate and celebratory as recipe depth increases.
- The common glass-like bubble is the physical silhouette; the ingredient inside is decorative.
- Bubble size and progression rank should remain understandable even when internal ingredient colors overlap.
- Artwork remains centered, uncropped, transparent, and readable while rotated.

### Animation and feedback style

Current P6.2 motion remains lightweight:

- Physics supplies most object animation.
- Tolina currently uses idle, throw, and happy static pose changes.
- Merge magic is a short visual-only effect.
- Notifications are brief and non-modal.

The approved production direction for Tolina is:

**Spine authoring → rendered transparent PNG frames or sprite sheets → native Godot `AnimatedSprite2D` playback**

Spine is an art-production tool only and should not become a runtime dependency of the shipped game.

Initial animation proof:

- subtle breathing
- blink/look behavior
- tail movement
- clean idle looping

Future animation candidates include:

- sleep
- wake
- stretch
- run
- hide
- peek
- play with a prop
- happy bounce
- dance
- major creation celebration

Animation should reinforce personality without blocking gameplay information.

Tolina should react more strongly to meaningful accomplishments than to ordinary merges.

Large frame sets, export resolution, frame rate, texture memory, and application-size impact must be profiled on representative mobile devices before the full animation library is produced.

### Visual priorities during gameplay

1. Current pieces, their contacts, and available space.
2. Danger threshold and active danger state.
3. Next-piece preview and Push readiness.
4. Tolina reaction and merge/discovery feedback.
5. Score and collection progress.
6. Decorative environment detail.

---

## 13. Required Visual Assets

### Existing production/prototype assets

| Asset group | Current assets | Purpose | Required variations | Priority |
| --- | --- | --- | --- | --- |
| Tolina | `idle`, `happy`, `throw` transparent PNGs | Brand anchor and immediate emotional feedback. | Current three poses. Future production animation will extend or replace static-only presentation. | Critical |
| Kitchen background | One 1024×1536 portrait illustration | Establish World 01 and support Kitchen screens. | Responsive crops for supported portrait ratios may be documented without editing the source. | Critical |
| Magical bowl | One 1312×1199 transparent illustration | Visually contains the physics chamber and communicates overflow/floor. | Responsive fitting rules; no alternate bowl currently required. | Critical |
| Creation artwork | Nine 512×512 transparent bubble PNGs | Gameplay bodies, Next preview, progress strip, collection cards, and result showcase. | Full semantic creation set; common bubble-aligned fitting by context. | Critical |
| Merge flavor | Thirteen approved PNGs under effects/merges | Egg/Milk/Cream presentation only; never board pieces | Three bubbles and ordered crack/pour/swirl poses; original aspect/transparency | High |
| Merge magic | One transparent PNG | Brief merge and discovery feedback. | Current single effect; animation variants optional only if later approved. | High |
| CJK-capable font | Noto Sans CJK Simplified Chinese | Ensures English, Spanish, and Simplified Chinese glyph support. | Weights are limited; hierarchy may rely on size, outline, shadow, and color. | Critical |

### Creation asset mapping

| Creation | File role | Used in |
| ---: | --- | --- |
| Wheat | `wheat.png` | Physics piece, Next, progress strip, collection, result |
| Flour | `flour.png` | Physics piece, Next, progress strip, collection, result |
| Cake Mix | `cake_mix.png` | Physics piece, Next, progress strip, collection, result |
| Cake Batter | `cake_batter.png` | Physics piece, progress strip, collection, result |
| Sponge Cake | `sponge_cake.png` | Physics piece, progress strip, collection, result |
| Frosted Cake | `frosted_cake.png` | Physics piece, progress strip, collection, result |
| Layer Cake | `layer_cake.png` | Physics piece, progress strip, collection, result |
| Decorated Cake | `decorated_cake.png` | Physics piece, progress strip, collection, result |
| Fancy Cake | `fancy_cake.png` | Physics piece, progress strip, collection, result |

### UI and production assets/design specifications still needed

| Deliverable | Purpose | Variations/states | Priority |
| --- | --- | --- | --- |
| UI style sheet | Standardize panel, border, corner, shadow, spacing, and text rules. | Surface levels, normal/reward/warning treatments. | Critical |
| Button system | Unify Main Menu, Back, Play Again, Push, Restart, future Home/Settings actions. | Primary, secondary, gameplay, disabled, pressed, hold progress. | Critical |
| Recipe card specification | Keep collection and progress strip visually related. | Locked, discovered, newly unlocked. | High |
| Warning/reward banners | Make Danger, New Creation, Max Merge, and Push feedback coherent. | Warning, discovery, final creation, brief action confirmation. | High |
| Lock/unknown symbol | Reinforce hidden recipes without revealing identity. | Compact strip and full collection-card forms. | High |
| Tolina production animation set | Replace/extend static pose presentation with expressive authored animation. | Spine editable master plus exported transparent frame sequences or sprite sheets for approved animations. | Critical for Living Home |
| App icon and store identity set | Represent Totolina Merge outside gameplay. | Platform icon, adaptive-safe composition, store key art. | Future production need |
| Optional onboarding illustrations | Explain drop, pair merge, danger, and Push with minimal text. | One contextual visual per concept. | Recommended after UX testing |

### Asset handoff rules

- Provide transparent bounds and intended visual center for every creation and Tolina asset.
- Document target scale separately for gameplay body, Next preview, recipe strip, collection card, result showcase, and Living Home.
- Do not bake collision guides or UI labels into creation artwork.
- Supply localization-independent art whenever possible.
- Test assets against both warm background areas and bright bowl glow.
- Keep higher-rank detail readable after mobile downscaling.
- Preserve editable Spine source separately from exported runtime assets.
- Godot gameplay/runtime code must not depend on `.spine` files.
- Exported Tolina animations must use semantic animation names such as `idle`, `sleep`, `happy`, `dance`, and `play_with_prop`.
- Define FPS, loop behavior, transparent bounds, frame dimensions, visual center, and trimming rules before mass-producing animations.
- Avoid duplicate final frames in seamless loops when they reproduce the first frame.

---

## 14. Mobile UX Constraints

### Orientation and target layouts

- Portrait-first and portrait-locked.
- Current logical design base: **540×960**.
- Required layout checks: **405×720**, **390×844**, and **540×960**.
- Include at least one tablet/iPad-like portrait aspect in visual QA even though the phone experience is primary.
- Layout expands dynamically; do not assume one fixed phone-pixel canvas.

### Touch controls

- Primary play input is a single touch choosing horizontal drop position.
- Desktop mouse mirrors the same player action for development/testing.
- Left and right Push are explicit buttons; there is no swipe gesture.
- Restart requires a one-second hold; quick tap does nothing and early release cancels.
- Recipe Collection requires touch-drag scrolling; all nine cards must be reachable.
- Do not reduce current touch targets when refining visual size.

### Safe areas

- Keep Tolina, Next, score, Push charge, navigation, collection Back, progress strip, and bottom controls clear of notches, Dynamic Island, rounded corners, and home indicators.
- Safe-area handling must be platform-neutral and responsive.
- Decorative art may bleed outside safe areas; essential information and controls may not.
- The bowl must remain visually dominant without covering the recipe strip or controls.
- Living Home ambient motion must also remain safe-area aware.

### Accessibility considerations

- Never communicate danger, locked state, readiness, or selection by color alone.
- Maintain strong text contrast and outlines/shadows over illustrated backgrounds.
- Avoid very small labels in the nine-slot progress strip; use imagery and state symbols first.
- Ensure pressed/disabled states differ in brightness, shape treatment, and/or iconography.
- Avoid rapid flashing; the game’s magic should feel soft and readable.
- Preserve a clear focus order if keyboard/controller accessibility is considered later.
- Audio and haptic alternatives do not currently exist, so critical feedback must remain visually complete.
- Text-size controls, reduced motion, color-vision options, and screen-reader support are not implemented; treat them as production accessibility decisions, not assumed features.
- Tolina animation should degrade gracefully if reduced-motion support is later added.

### Localization considerations

- Supported languages: English, Spanish, and Simplified Chinese (`zh_CN`).
- Use localized string keys; do not bake words into art.
- Allow Spanish labels to expand substantially beyond English.
- Allow Chinese line breaking without relying on spaces.
- Highest-creation names must wrap across multiple lines for expanded Spanish and Chinese labels.
- Use the existing CJK-capable font or verify full glyph coverage before proposing another.
- Avoid uppercase-only hierarchy as the only solution because it does not transfer equally across scripts.

---

## 15. Technical Constraints Relevant to UI Design

Only constraints that affect design and handoff are included here.

### Platform and runtime

- Built in Godot 4.7 for Android and iOS.
- Mobile-first renderer and portrait presentation.
- Android and iOS export configuration already exists and must be preserved.
- The game is currently offline-first; Android does not request Internet access.
- No accounts, server, cloud synchronization, telemetry architecture, or external content service exists.

### Responsive layout

- UI and chamber layout derive from the available viewport and safe area.
- The gameplay chamber is the coordinate source for walls, floor, spawn region, and danger threshold.
- The visible danger line uses the same chamber-relative threshold as gameplay; mockups must not place it independently for visual convenience.
- Bowl artwork is a presentation layer aligned to chamber anchors. It may scale responsively, but it must continue to show full side containment, rim, and floor.
- The visual bowl and physical collision chamber are separate; changes to art scale do not authorize changes to physics.

### Gameplay visual separation

- Creation artwork is separate from the physics body and explicit collision circle.
- The common 512×512 bubble canvas does not determine physics size. The world base radius and each CreationDefinition's `size_order` / cumulative `size_growth_percent` drive collision and matching artwork size. `progression_rank` remains separate for gameplay/scoring; it does not determine physical size. Mass and the 2.18 artwork-fitting calibration remain unchanged.
- Replacing or resizing a sprite must not change collision radius, mass, merge rules, or resting behavior.
- Creation art rotates with its physics body.
- Transparent padding and off-center art can make objects appear to float or escape even when physics is correct; asset bounds are a handoff concern.

### Tolina animation architecture

- Spine is an external authoring tool only.
- Production animation is exported as rendered transparent frames or sprite sheets.
- Godot playback uses native `AnimatedSprite2D` / `SpriteFrames`.
- Do not introduce a Spine runtime dependency.
- Tolina animation playback must remain presentation-layer functionality and must not own physics, scoring, merging, danger, Push, or recipe progression.
- Gameplay/UI should request semantic animation states rather than individual frame assets.

### Performance considerations

- Active runs can contain many physics bodies at once.
- The gameplay screen already combines a full-screen illustrated background, a large translucent bowl, rotating high-resolution sprites, UI overlays, and brief effects.
- Avoid full-screen blur, multiple stacked translucent passes, continuous heavy particles, or large frame-by-frame animation sets unless profiled on representative Android/iOS devices.
- Design effects that can be brief, pooled/reused, and visually effective at small sizes.
- Tolina's production animation pipeline uses rendered frames, so animation resolution, frame count, FPS, texture memory, and atlas packing must be budgeted and profiled on mobile.

### Save and data limitations

- Persistent data currently contains versioned semantic creation discoveries only.
- Score, highest creation, Push charge, pieces, and danger state reset with a new run.
- Future Living Home behavior history may require a very small local persistence extension.
- Theme ownership, if IAP is implemented, should rely on platform store entitlements rather than a proprietary player account.
- Do not design account, cloud-save, conflict-resolution, or multi-profile UI without new product scope.

### Architecture guardrails for handoff

- Keep screen/component concepts lightweight; no large UI framework is implied.
- No autoload/manager-based design dependency is assumed.
- Do not require third-party runtime plugins solely to reproduce animation or visual prototypes.
- Provide implementable measurements, responsive rules, state behavior, and assets rather than only one static idealized screenshot.
- A cosmetic theme must alter presentation only; gameplay rules remain unchanged.

### Known localization implementation gap

The overall project has English, Spanish, and Simplified Chinese localization, but several current prototype HUD/action labels still appear as direct English presentation text, including forms of **Next**, **Score**, **Pulse**, **Danger**, **Push**, and short merge confirmations. Production designs and handoff must include localized variants for all player-facing text. This document identifies the gap; it does not change the current localization architecture.

---

## 16. Monetization Constraints

### Current implementation state

No ads, in-app purchases, Store UI, economy, paid currency, or monetization SDK exists in the current project.

Monetization implementation is deferred until the core product, UX, retention, and release architecture are sufficiently validated.

### Confirmed product direction

The preferred commercial model is:

- Free download.
- Carefully controlled interstitial advertising.
- Permanent optional Remove Ads purchase.
- Optional permanent cosmetic theme purchases.
- Rewarded advertising only if a genuinely useful and non-predatory player benefit is later approved.

Cosmetic purchases must not affect gameplay balance.

Themes must not modify:

- scoring
- physics
- collision
- spawn probabilities
- Push
- danger behavior
- merge behavior
- recipe requirements
- difficulty

### Advertising principles

Advertising must never interrupt:

- a falling creation
- active physics resolution
- a merge chain
- danger recovery
- a first-discovery celebration
- a Fancy Cake celebration

Game Over is a possible interstitial opportunity, but advertising after every run is not approved. Frequency and placement must be validated against retention and replay behavior.

### Purchase principles

Remove Ads and cosmetic themes are intended as permanent purchases rather than consumable gameplay resources.

No Lunitora account, login, proprietary server, or player-facing cloud account should be required for normal play.

Cross-platform purchase transfer between Apple and Google ecosystems is not assumed without a separate account/backend entitlement system.

### UX guardrails

- Never make Tolina disappointed because the player declines a purchase.
- Never obscure or delay Play Again solely to increase advertising exposure.
- Keep rewarded advertising visibly optional.
- Avoid false scarcity, countdown pressure, or manipulative purchase prompts.
- Do not create currencies or an economy simply to support monetization.
- Preserve offline core play.

---

## 17. Cosmetic Theme Direction

### CONFIRMED commercial/product direction

Totolina Merge may offer cosmetic presentation themes.

The default theme is included with the game.

A theme may change:

- Living Home environment
- gameplay background
- decorative chamber presentation
- magical bowl presentation
- ambient particles
- selected Tolina props or theme-specific ambient animations
- music or ambience when justified

A theme must not change:

- physics
- collision sizes
- masses
- scoring
- spawn distribution
- Push strength
- danger logic
- merge rules
- recipe requirements
- gameplay difficulty

### Theme scope guardrail

A theme is not automatically a new gameplay world.

Examples of possible cosmetic themes:

- default cozy Kitchen/Home
- Space
- Cloud Kingdom
- Sakura Garden

The architecture may support multiple themes, but version 1.0 should not require producing many themes before the game is validated.

One premium theme may be considered for launch if production cost, player testing, schedule, and commercial strategy justify it.

Additional themes should primarily be content production rather than new gameplay development.

---

## 18. Future Expansion Possibilities

### CONFIRMED product foundation

- **Totolina Merge** is the game identity.
- **Lunitora Games** is the studio/brand.
- **Tolina** is the main character.
- **Kitchen** is the only gameplay world required for version 1.0.
- The Kitchen contains nine semantic creations, eight same-item recipes, nine progression ranks, and a persistent Recipe Collection.
- Living Tolina Home is a confirmed version 1.0 product direction.
- Tolina accomplishment reactions are a confirmed version 1.0 product direction.
- Cosmetic theme support is a confirmed commercial/product direction, although the number of launch themes is not yet fixed.
- The core player experience remains approachable physics merging, discovery, character reaction, and replay.

### POSSIBLE FUTURE IDEAS — not current requirements

#### New gameplay worlds

- **Cat Garage:** combine wheels, parts, engines, and vehicles.
- **Sakura Garden:** combine seeds, flowers, plants, and trees.
- **Space Cat:** combine celestial objects into planets, stars, and galaxies.

These are post-launch gameplay-world possibilities, not version 1.0 requirements.

Each would need its own fantasy, creation ladder, environment, visual container, collection treatment, and character/world relationship. Do not assume the Kitchen bowl or cake terminology transfers unchanged.

#### Characters

- Additional character companions associated with new worlds.
- Additional Tolina reaction animations.
- Character selection or unlocks only if a clear player benefit and progression model are approved.

#### Collections and content

- Additional world-specific recipe/creation collections.
- Limited new creation graphs or variants, provided identity and recipe compatibility remain clear.

#### Feedback and presentation

- Cozy background music.
- Merge, discovery, Push, and UI sound design.
- Optional light haptics.
- More expressive motion and restrained magic effects.

#### Systems requiring separate approval

- Best-score tracking or personal records.
- Achievements.
- World map and world unlock progression.
- Events or challenges.

These are possibilities, not promises. Baseline prototypes must not make them appear committed.

### OUT OF SCOPE direction

- Pet care meters, hunger, or relationship maintenance.
- Farm simulation.
- Restaurant management.
- Decoration-management gameplay.
- Multiplayer/social competition.
- Live-service obligations.
- Currency/economy layers added only to manufacture retention.
- Pay-to-win purchases.

---

## 19. Design Risks

### UX risks

| Risk | Why it matters | Design response to explore |
| --- | --- | --- |
| Merge / preview readability | Players may confuse DROP with NEXT or miss a short flavor effect, danger, Push or hold Restart. | Test the universal matching rule and visual-only flavor; keep the current piece and upcoming preview distinct. |
| Push purpose is not self-evident | Percentage and directional buttons show availability but not necessarily the rescue/strategy value. | Prototype concise first-ready guidance and stronger ready-state affordance without permanent clutter. |
| Danger mental model may be ambiguous | A falling piece passing the line does not necessarily count; supported/settled pieces do. | Ensure visual language communicates sustained overflow, not momentary crossing. Consider a recoverable-state cue without exposing technical rules. |
| Restart is intentionally clean while idle | A quick tap doing nothing can seem broken to a first-time user. | During press, reveal instruction/progress immediately above the finger; test whether onset is fast enough. |
| No route to Main Menu during/after play | Players cannot intentionally leave a run or return from results without replay/system navigation. | Product must decide whether to add a safe exit and how to protect the current run. |
| Result overlay omits score | Score is visible during play but not part of the final showcase. | Add final score during UX completion without reducing creation pride. |
| Collection scrolling and density | Nine illustrated cards and a fixed Back button must remain usable on narrow/tall phones. | Validate drag capture, content height, card readability, and end-of-list affordance on real devices. |
| Tolina behavior repetition | Seeing the same Home animation repeatedly will make the Living Home feel artificial. | Use weighted selection with recent-behavior suppression and a modest behavior library. |

### Visual and responsive risks

| Risk | Why it matters | Design response to explore |
| --- | --- | --- |
| Bowl art vs. physics mismatch | A beautiful bowl can imply walls/floor in different places from actual collisions, making pieces look floating or outside. | Annotate chamber anchors and validate art at every target ratio with Decorated and Fancy Cake. |
| Crowded portrait hierarchy | Tolina, HUD, danger, bowl, progress strip, and controls compete for limited vertical space. | Use responsive constraints and importance hierarchy, not proportional shrinking of everything. |
| Higher-rank visual complexity | Decorated Cake and Fancy Cake are large and can obscure the pile or become visually noisy. | Preserve strong bubble silhouettes, controlled effects, and high contrast against the bowl interior. |
| Nine-slot progress strip | Slots can become too small to distinguish art or lock state. | Prioritize shape/art and state over recipe text; verify at 390 px width. |
| Warm-on-warm contrast | Golden UI or ingredients can disappear against the Kitchen. | Use plum surfaces, outlines, rim lighting, and contrast checks. |
| Text expansion and CJK layout | English-centric one-line designs can fail in Spanish or Chinese. | Design flexible widths, wrapping, and script-appropriate hierarchy from the first prototype. |
| Animation asset growth | Rendered frame animation can increase texture memory and install size quickly. | Establish resolution/FPS/frame budgets from the first Spine proof and profile on mobile. |
| Theme scope creep | A cosmetic theme could accidentally become an entire new gameplay world. | Define a fixed theme asset contract; gameplay rules and creation ladder stay unchanged. |

### Gameplay communication risks

| Risk | Why it matters | Design response to explore |
| --- | --- | --- |
| Rank-8/9 size spike | Decorated and Fancy Cake pressure may feel abrupt or unfair even when mechanically intended. | Playtest perceived fairness; improve preview and pile readability before changing balance. |
| Deterministic restart sequence | Repeated early runs may feel predictable if players notice the same opening. | Treat as a balancing/product question; do not alter RNG through UX work. |
| Chain pacing vs. responsiveness | The merge cooldown improves readability but can make touching matches appear temporarily ignored. | Feedback should show that resolution is continuing without implying an invalid match. |
| Visual-only celebration overload | New Creation, Max Merge, Push feedback, Tolina, score, and magic can coincide. | Establish priority and queuing/overlap rules in the motion specification. |

### Monetization risks

| Risk | Why it matters | Design response to explore |
| --- | --- | --- |
| Monetization harming replay | An interstitial at every Game Over could interrupt the strongest “Play Again” moment. | Validate frequency and placement through beta behavior rather than maximizing impressions. |
| Theme value too weak | A paid theme that only replaces one background may not feel worth buying. | Define a controlled but meaningful presentation package across Home and selected gameplay surfaces. |
| Theme production too expensive | Rebuilding every asset for each theme would destroy the low-maintenance business model. | Preserve reusable gameplay/UI assets and constrain each theme to a defined presentation asset contract. |

### Retention risks

- The persistent collection has nine items; after completion, replay depends on score mastery, physics enjoyment, and Tolina attachment.
- There is no persistent best score or additional gameplay world in version 1.0 by default.
- Living Tolina can improve emotional retention, but too few ambient behaviors could become repetitive.
- Adding progression solely to fix retention could dilute the simple cozy promise. Validate whether the core loop sustains replay before layering systems.

### Scope risks

- Designing world maps, currencies, achievements, multiple characters, or live events before product approval would prematurely define architecture and expectations.
- A highly animated visual prototype may imply physics changes or performance cost not compatible with the current implementation.
- Treating the retired pre-release linear ladder as current would create asset, localization, save, and discovery inconsistencies.
- Broad internal renaming or a generic UI framework is not required to deliver current screen designs.
- Cosmetic themes must not silently become new gameplay worlds.

### Accessibility and trust risks

- Critical feedback is visual-only because audio/haptics are absent.
- Danger uses a strong red/orange convention that must remain readable for color-vision differences.
- Some current prototype HUD labels are not yet localized.
- No explicit privacy, accessibility, legal, or parental-information screen exists; production requirements remain undefined.

---

## Designer Deliverables and Developer Handoff Checklist

The Game Design Workspace should produce artifacts that are directly actionable without redefining gameplay.

### UX flow deliverables

- Current-state screen map matching the implemented navigation.
- First-session, returning-player, discovery, danger-recovery, collection, and replay journeys.
- Living Home flow showing entry into Gameplay and Recipes.
- Clearly separated optional flows for onboarding, Settings, Pause/Exit, theme selection, or future worlds.
- Transition and back-navigation rules, including what happens to an active run.

### Wireframe deliverables

- Current Main Menu and proposed Living Tolina Home evolution.
- Living Tolina Home: several representative ambient states using the same responsive composition.
- Gameplay: empty/early pile, active merge, Push charging, Push ready, danger, discovery, maximum tier, hold Restart, and dense late-game states.
- Result Overlay: with and without a newly discovered recipe; short and long creation names; final score included in the planned 1.0 hierarchy.
- Recipe Collection: fresh all-locked, partially discovered, fully discovered, scrolled-to-bottom.
- Collection-complete Home/result treatment.
- Theme-selection concept only if the first premium theme is approved.
- Responsive frames for 405×720, 390×844, 540×960, and one iPad-like portrait ratio.

### Visual prototype deliverables

- Defined color, type, spacing, corner, border, shadow, and icon rules.
- Full component state sheet.
- Living Home visual hierarchy.
- Tolina pose/animation usage and timing map.
- Tolina ambient-behavior placement and safe movement bounds.
- Tolina reaction intensity map: ordinary event, meaningful accomplishment, major accomplishment.
- Default-theme specification identifying which visual surfaces a future cosmetic theme may replace.
- Creation fitting examples for each shared progression rank, especially Decorated and Fancy Cake, in every UI context.
- Gameplay hierarchy test using a dense, colorful late-game pile—not only an empty bowl.
- Safe-area overlays and chamber/bowl/danger anchor annotations.
- English, expanded Spanish, and Simplified Chinese stress-test screens.

### Interaction specification

For every interactive component, provide:

- Visible bounds and minimum touch target.
- Default, pressed, disabled, ready, holding, cancelled, and completed states where applicable.
- Gesture type and activation timing.
- Feedback location, especially under finger occlusion.
- Whether gameplay continues behind the interaction.
- Behavior during danger and Game Over.
- Localization and accessibility notes.

### Asset export handoff

For general assets:

- File name and intended screen/context.
- Pixel dimensions or scalable/vector format.
- Transparent padding and visual-center guidance.
- Reference scale at each target viewport.
- Color space and alpha expectations.
- Confirmation that art contains no baked localized text.

For Tolina animations:

- Spine source location and source-version information.
- Animation name.
- Loop or one-shot behavior.
- Export FPS.
- Frame dimensions.
- Frame count.
- Pivot/visual center.
- Transparent padding/trimming rules.
- Sprite-sheet/atlas packing requirements if used.
- Confirmation that the exported runtime asset does not require the Spine runtime.

### Acceptance checks for design handoff

- The visible bowl agrees with the physical chamber at all target ratios.
- The visible danger line represents the actual gameplay threshold.
- Pieces remain identifiable while rotated, overlapped, and scaled down.
- All essential controls are outside unsafe screen areas.
- All nine creations are reachable and readable in the collection.
- Locked recipes do not reveal names or full-color artwork.
- Push, danger, discovery, restart, and result states are distinguishable without audio.
- Spanish and Simplified Chinese layouts are intentional, not afterthoughts.
- Living Home ambient animation does not obscure navigation or create unsafe touch overlap.
- Tolina animation playback remains presentation-only.
- Proposed visuals do not imply unapproved currency, accounts, pet-care progression, or gameplay advantages.
- Theme concepts preserve identical gameplay rules and collision behavior.

---

## Open Product Questions for Design Review

1. What is the minimum first-run teaching needed for drop, merge, danger, Push, and hold Restart?
2. What is the exact pause / return-to-Home behavior during an active run?
3. Should persistent best score be added, or should persistent progression remain recipe-focused?
4. What exact one-time experience should occur when all nine Kitchen creations are discovered?
5. How many Living Tolina ambient behaviors are required for version 1.0 to avoid obvious repetition?
6. Which recipe/accomplishment milestones should unlock or trigger specific Tolina reactions?
7. What should the final default Living Home environment look like?
8. Is one premium cosmetic theme justified for launch, or should paid themes begin after release validation?
9. If one premium launch theme is produced, which concept should be prototyped first?
10. What advertising cadence preserves retention and immediate replay?
11. Is rewarded advertising useful enough to justify implementation in version 1.0?
12. What is the formally validated target session length and target audience/age rating?
13. Which accessibility and Settings options are required for version 1.0?
14. Which currently direct-English HUD labels must be localized before beta?
