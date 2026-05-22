---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: subfile
status: draft
last_verified: "2026-05-21"
---

## Tokens

This file contributes no tokens. It is a glossary of in-game and design-vocabulary terms used elsewhere in the tree.

## Rationale

### In-game vocabulary

- **Bellow.** A verb category (not a token in v0.1.1) for cards that multiply burn stacks on enemies. Bellow cards include `bellows`; planned: `roar`, `inhale`, `forge_breath`.
- **Burn.** A `{states.enemy_lifecycle.burning}` node; while burning, an enemy takes 1 damage per burn stack at end-of-turn (`{rules.end_of_turn}` step 1).
- **Salamander.** The player avatar. Not a separate `entities.salamander` — the player entity in `gdd/mechanics.md` *is* the salamander.
- **Ascension.** Difficulty modifier applied at run start. Ascension 0 = Normal; higher ascensions unlock post-win (deferred to v0.5).

### Design-vocabulary

- **Hand-shape decision.** Per `{pillars}`: the choice of *which combination* of drawn cards to play and which to hold/exhaust, as distinct from the choice of *which single best card* to play.
- **Exhaust.** A `card_lifecycle` transition (`in_hand -> exhausted`) for one-shot cards that do not return to the deck for the rest of the run. The `exhausted` node is `terminal: true`.
- **Intent.** The enemy's next-turn action, shown to the player in advance. Implemented via `{rules.encounter_setup}` step 3 (reveal_intent) and the per-enemy YAML files in `content/enemies/`.

### Design framework citations

- **MDA** — Hunicke, LeBlanc, Zubek, 2004. *Mechanics, Dynamics, Aesthetics: A Formal Approach to Game Design and Game Research.* The eight-aesthetic vocabulary is what `player_experience_goals` enumerates.
- **Game Feel** — Steve Swink, 2008. *Game Feel: A Game Designer's Guide to Virtual Sensation.* The six dimensions in `{feel.play_card}` are Swink's.
- **Game Design Workshop** — Tracy Fullerton. The Formal Elements decomposition motivates the seven core namespaces.
