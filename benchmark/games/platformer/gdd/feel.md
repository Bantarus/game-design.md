---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-23"
implemented_in: ["src/embergrave/feel/**/*"]
feel:
  jump:
    input:    "tap-or-hold spacebar/A-button; impulse magnitude is fixed by tap-vs-hold at press time, NOT modulated by hold duration after the first frame"
    response: "vertical velocity set on the frame of input; visible vertical motion begins next render frame (≤17ms); ember dims 4% per second while airborne"
    context:  "moth's wing-flutter animation accelerates 30% during the upward arc; landing reverberation tightens when the next-jump-ready window opens (16 frames after land)"
    polish:   "screen y-axis offset of -2 micro_units on jump frame (subtle camera-anticipation); micro-particle burst at moth's foot anchor on launch; haptic tick (180ms duration) on controller"
    metaphor: "the moth's jump feels like a wingbeat that commits to its arc — once airborne, the moth is reading the cave, not steering"
    rules:    "during the first 8 frames of airborne, jump input is dropped (no double-jump); jump input during dashing or gliding is buffered until those states end"
    status: draft
    implemented_in: ["src/embergrave/feel/jump.py"]
  dash:
    input:    "shift+direction tap; direction locked at press time (no mid-dash steering); requires {resources.ember} >= 3 or input is rejected with a dim-flash visual"
    response: "horizontal velocity set on input frame; dash duration is fixed at 12 ticks (200ms at 60Hz); during dash the moth ignores gravity"
    context:  "the moth's silhouette stretches 20% along dash direction during the 12-tick window; the ember dims 50% then re-brightens on dash end; world camera lags 3 ticks behind the moth to amplify perceived speed"
    polish:   "afterimage trail (4 frames of position history rendered at 40% opacity); screen flash (3% white, 60ms) on dash start; haptic burst (40ms, sharp)"
    metaphor: "dash feels like a held breath released — directional, irrevocable, and over before the moth can rethink"
    rules:    "ember check is at press time, not during; insufficient ember produces NO state change (the dash is rejected entirely, not partially applied); dash ends on land OR on dash_duration_expired event, whichever fires first"
    status: draft
    implemented_in: ["src/embergrave/feel/dash.py"]
  glide:
    input:    "hold spacebar (the same button as jump, but held past frame 8 of airborne); requires {resources.ember} >= 1 per second; releasing the button cancels glide immediately"
    response: "vertical velocity damping multiplier of 0.3 applied each tick while held; horizontal velocity unchanged; ember drains at 1 per 60 ticks (1 per second) while gliding"
    context:  "moth's wing arc widens to a parallel-to-ground glide pose; the ember casts a wider light cone (1.5× radius) during glide; ambient cave sound becomes muffled (like the moth is listening for the next ledge)"
    polish:   "wing-arc animation interpolated smoothly over 4 frames at glide start; particle trail (3 ember sparks per second) follows the moth's tail; haptic low-frequency rumble (continuous, 15% strength)"
    metaphor: "glide feels like a held breath sustained — the moth is buying time at the cost of light, watching for the route"
    rules:    "glide is the ONLY in-air verb that costs ember-per-tick (jump is free, dash is a discrete-cost-at-press); glide cancels on the same frame as ember_depleted event; glide cannot be re-entered for 8 frames after release (anti-spam buffer)"
    status: draft
    implemented_in: ["src/embergrave/feel/glide.py"]
---

## Tokens

Three feel entries — one per input verb (`{verbs.jump}`, `{verbs.dash}`, `{verbs.glide}`). The other six verbs in `gdd/mechanics.md` deliberately do not declare `feel:` — they are system actor verbs (`refuel_ember`, `touch_checkpoint`, `restart_at_checkpoint`, `enter_level`, `exit_level`, `select_region`, `reach_summit`) that resolve game state without a haptic moment the player commits to. `feel.md` is only required by the spec when at least one verb declares `feel:` (§4.2), so these three entries are what trigger this file's existence.

## Rationale

**`jump` is the most-touched verb in the game** — a 90-minute expedition is ~600 jumps. Every dimension of Swink's six is tuned individually here, in YAML, because each value is normative. The "no mid-air modulation" of jump arc is the *load-bearing feel decision* — it is what makes the pillar "every jump is a commitment" mechanically true rather than aspirational.

**`dash` is the precision-platformer's signature move.** The 12-tick (200ms) fixed duration is the entire feel of dash — long enough to clear a 4-tile gap, short enough that the moth cannot reconsider. The 3-ember cost makes dash a budgeted resource rather than a free movement primitive; the ember check at *press time* (not during) is what makes a rejected dash feel different from a successful one without ambiguity.

**`glide` is the only continuous-cost verb.** Jump is free; dash is a discrete cost at press. Glide drains ember per-tick while held, making it a fundamentally different *feel* — the player is *sustaining* light rather than *spending* light. The wider light cone during glide is the most important `context:` line in this file: it tells the player "you are gaining vision at the cost of ember," which is the entire glide-vs-dash decision.

**The `metaphor:` lines connect mechanics to fiction.** "Wingbeat that commits," "held breath released," "held breath sustained" — these are the three verbs as breath-control metaphors, aligned with the moth's biology and the volcano-shaft setting. Feel is where mechanics and fiction meet.

## Open Questions

- Whether `restart_at_checkpoint` should grow a `feel:` block. Argument for: the respawn is a moment the player feels (the fade-out / fade-in transition). Argument against: at <200ms respawn time, the moment is more "absence of moment" than haptic. Currently no — the cheapness of death is itself the feel.
- Whether `refuel_ember` (the collection of an ember pickup) should have feel. Argument for: collecting is a small reward that deserves a moment. Argument against: it's automatic on overlap, not a player-committed input — and the spec's `feel:` lives on verbs the player consciously *issues*, not on system-triggered events. Currently no; the visual/audio reward is presentation-layer, not feel-layer.
- Whether the buffered-jump-during-dash rule (`rules:` line on `dash`) introduces enough complexity to warrant its own event in `{events}`. Currently the buffer is implicit; if it becomes confusing in playtest, an explicit `jump_buffered` event might be added.
