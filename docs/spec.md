---
spec: game-design.md
spec_version: 0.2.0-alpha
status: draft
last_updated: 2026-05-22
license: Apache-2.0
---

# The `game-design.md` Specification

> **Status: draft / alpha (v0.2.0-alpha).** Expect the format to change as it matures. Modeled on Google Labs' [`DESIGN.md`](https://github.com/google-labs-code/design.md).

`game-design.md` is a plain-text, LLM-first, engine-neutral, genre-agnostic standard for describing a video game to an AI coding agent as a living source of truth. A `game-design.md` tree pairs **normative YAML tokens** (the truth an agent compiles against) with **prose rationale** (why, and fallback when no token covers a case). The primary reader is an AI coding agent; a human is the second reader.

The rest of this document is normative. Where this spec is silent, the corresponding rule in `DESIGN.md` upstream applies; where the two disagree, this document wins for `game-design.md` trees.

---

## 1. Philosophy & Principles

These seven principles are non-negotiable. The linter exists to enforce them; the spec exists to motivate them.

1. **LLM-first, human-readable.** A `game-design.md` tree contains only plain Markdown with YAML frontmatter (`---`-fenced) and sibling `*.yaml` data files. No proprietary formats, no hidden state, no binary blobs. The format must be readable cold by any frontier LLM in any IDE and any human in any text editor — no tooling required to consume it.

2. **Engine-neutral.** The standard makes no assumption about Unity, Godot, Unreal, Bevy, Tauri, Flutter, or any other engine, runtime, or rendering pipeline. Platform fields are abstract (`desktop`, `handheld`, `web`, `console`, `mobile`, `mixed-reality`). Engine-specific concerns belong in `gdd/technical-constraints.md` as prose, never in the schema.

3. **Genre-neutral core.** The core schema encodes a *universal probabilistic surface* (§4) that fits any genre. Deckbuilder, party RPG, tick-combat, TCG, roguelike, platformer, simulation — every game reduces to instances of the same seven primitives. **Adding a genre-specific token to the core schema is a spec bug.** Genre-specific concepts live in an example's own subfiles as prose conventions.

4. **Tokens normative, prose rationale.** YAML frontmatter values are the authoritative truth — the numbers and structure an agent compiles against. Markdown prose explains *why* and serves as fallback when no token covers a case. **Tokens win on conflict.** Authoritative numbers must not appear in prose; rationale must not appear in tokens. The two layers exist for two different readers and two different purposes.

5. **Modular with a short core entry file.** The root `game-design.md` stays under ~200 lines and acts as a navigation index pointing to `gdd/` subfiles via a `files:` map in frontmatter — modeled on the `llms.txt` convention (Howard, 2024). The agent reads the root file first, then opens only the subfiles the current task needs. This is *progressive disclosure*; it is what makes the standard scale to AAA-sized designs without exploding context.

6. **Deterministic structure.** Section order is canonical and linter-enforced. Token namespaces are stable. Any concept is locatable by a single deterministic path: `{loops.combat_turn}` lives in `gdd/loops.md` frontmatter under `loops.combat_turn`, full stop. The agent never has to guess where a concept is.

7. **Living, status-tracked, anti-drift.** Every section and content entity carries a `status:` field, an `implemented_in:` source pointer, and a `last_verified:` date. The linter detects drift (`stale-section`, `broken-ref`, `orphaned-entity`); the workflow (§8.2) re-validates on every change. The traditional GDD failure mode — write once, never update, drift from the implementation — is what this standard exists to prevent.

> **Design lineage.** The standard borrows from five canonical frames in game design: **MDA** (Hunicke/LeBlanc/Zubek, 2004) supplies the mechanics → dynamics → aesthetics decomposition and the canonical aesthetic vocabulary (sensation, fantasy, narrative, challenge, fellowship, discovery, expression, submission); the **Elemental Tetrad** (Schell, *The Art of Game Design*) supplies the mechanics/story/aesthetics/technology division that motivates subfile decomposition; **Formal Elements** (Fullerton, *Game Design Workshop*) supplies the genre-agnostic enumeration that maps almost 1:1 to the seven core namespaces; **Theory of Fun** (Koster) supplies the framing of learning curve as design surface; **Game Feel** (Swink) supplies the six-dimension vocabulary for the `feel` cross-cutting namespace (§4.8). Citations belong in `gdd/glossary.md` of any example; they are not required in the root file.

---

## 2. File Model

### 2.1 Two-layer file

Every `.md` file in the standard is exactly:

```
---
{YAML frontmatter — normative tokens}
---

{Markdown prose body — rationale}
```

**Precedence.** Where token and prose appear to disagree, the token wins; the prose is treated as stale and must be updated. The linter does not parse prose for token assertions, but the spec-author workflow (§8.2) requires it on every change.

`*.yaml` files in `content/<entity>/*.yaml` are pure data: no prose body, just YAML.

### 2.2 The tree

Canonical layout for any conformant example:

```
<root>/
  game-design.md            # core entry, < ~200 lines (required)
  gdd/
    pillars.md              # required
    loops.md                # required
    mechanics.md            # required (entities, verbs, resources, states)
    architecture-invariants.md  # required (invariants — codebase contract)
    systems/
      _index.md             # optional
      combat.md             # optional (genre may not need it)
      progression.md        # optional
      distributions.md      # required
      ai-behavior.md        # optional
    content/
      _index.md             # required iff any content-schema file exists
      cards.md              # content-schema file (genre-dependent)
      enemies.md            # content-schema file (genre-dependent)
      items.md              # content-schema file (genre-dependent)
      levels.md             # content-schema file (genre-dependent)
    narrative.md            # optional
    economy-balance.md      # required (balance_targets)
    ux.md                   # optional
    art-direction.md        # optional
    audio.md                # optional
    feel.md                 # required iff any verb declares feel:
    verification.md         # optional (verify_targets + adapters; experimental in v0.1)
    technical-constraints.md # optional
    milestones.md           # optional
    glossary.md             # optional but strongly recommended
  content/
    cards/*.yaml            # one file per entity, referenced via data_source
    enemies/*.yaml
    items/*.yaml
    levels/*.yaml
```

**Required vs optional.** *Required* files must exist for the linter to pass. *Optional* files are accepted if present and ignored if absent — the linter never errors on absence of an optional file, only on broken references into one. The four conditionally-required files (`distributions.md`, `economy-balance.md`, `feel.md`, `content/_index.md`) are required exactly when the conditions in the comments above hold.

**The `files:` map contract.** The root `game-design.md` frontmatter declares a `files:` map whose keys are stable logical names (e.g. `loops`, `mechanics`, `cards`) and whose values are workspace-relative paths to subfiles. The linter validates that every value resolves to a real file. Any subfile not listed in `files:` is *orphaned* (rule `orphaned-entity`, severity warning). The map is the agent's navigation index — if it's not in `files:`, the agent will not find it.

### 2.3 Required frontmatter keys per file type

There are four file types. Every `.md` file in the tree declares its type explicitly via the `file_type:` field. (This is a v0.1 convention that makes the JSON Schema robust to validation from any IDE.)

| Field | core | subfile | content-schema | content-entity (`*.yaml`) |
| --- | --- | --- | --- | --- |
| `spec` | required (`game-design.md`) | required | required | required |
| `spec_version` | required (semver) | required | required | required |
| `file_type` | required (`core`) | required (`subfile`) | required (`content-schema`) | required (`content-entity`) |
| `name` | required | — | — | — |
| `short_pitch` | required | — | — | — |
| `genre_tags` | required (array) | — | — | — |
| `status` | required | required | required | required |
| `version` | required (semver) | — | — | — |
| `last_updated` | required (ISO date) | — | — | — |
| `last_verified` | — | required (ISO date) | required (ISO date) | required (ISO date) |
| `target_platforms_neutral` | required (array) | — | — | — |
| `pillars` | required (array of 3–5 strings) | — | — | — |
| `non_goals` | required (array) | — | — | — |
| `player_experience_goals` | required (object) | — | — | — |
| `core_loop_ref` | required (`{loops.<id>}`) | — | — | — |
| `files` | required (map) | — | — | — |
| `implementation_pointers` | optional (map) | optional | optional | — |
| `implemented_in` | — | optional (array of globs) | optional | required (array) |
| `id` | — | — | — | required |
| `entity` | — | — | required (kind name) | — |
| `schema` | — | — | required (object) | — |
| `data_dir` | — | — | required (path) | — |
| `count_target` | — | — | required (integer) | — |
| `balance_refs` | — | — | optional (array of refs) | — |

Subfiles have a free per-namespace top-level key in their frontmatter (e.g. `loops.md` carries a top-level `loops:` map, `mechanics.md` carries `entities:`, `verbs:`, `resources:`). The JSON Schema (§10) enumerates the namespace-to-file mapping.

---

## 3. Reference Syntax

Tokens are referenced inline as `{namespace.id}` with literal curly braces. Examples: `{loops.combat_turn}`, `{resources.energy}`, `{verbs.play_card}`, `{distributions.card_draw}`, `{entities.cards.ember_strike}`.

**Namespace ownership.** Each namespace is owned by exactly one subfile:

| Namespace | Owning subfile |
| --- | --- |
| `entities` | `gdd/mechanics.md` (and `content/<kind>/*.yaml` for content-heavy types) |
| `verbs` | `gdd/mechanics.md` |
| `resources` | `gdd/mechanics.md` |
| `states` | `gdd/mechanics.md` |
| `events` | `gdd/mechanics.md` |
| `rules` | `gdd/mechanics.md` or a `gdd/systems/*.md` |
| `loops` | `gdd/loops.md` |
| `distributions` | `gdd/systems/distributions.md` |
| `feel` | `gdd/feel.md` |
| `balance_targets` | `gdd/economy-balance.md` |
| `invariants` | `gdd/architecture-invariants.md` |
| `verify_targets` / `adapters` | `gdd/verification.md` |
| `pillars` | `gdd/pillars.md` (and the root `game-design.md`) |
| `player_experience_goals` | the root `game-design.md` |

**Resolution.** A reference `{ns.id}` resolves by looking up `ns` in the namespace table above, opening the owning subfile, and reading the value at `ns.id` in its frontmatter. References may chain through dot paths into nested objects (e.g. `{entities.cards.ember_strike.cost}`).

**Primitive vs composite.** A reference may resolve to either a *primitive* (number, string, boolean) or a *composite* (object, array). Composite refs are legal anywhere; primitive refs are required only where the consuming field declares a scalar type (e.g. a `cost:` field must resolve to a number or to a composite that itself contains a number under a documented sub-path).

**References into `content/*/*.yaml`.** A reference whose path starts with `{entities.<kind>.<id>...}` resolves through the `data_source:` of the matching content-schema file. Example: `{entities.cards.ember_strike}` first reads `gdd/content/cards.md` frontmatter, finds `data_source: ../content/cards`, and resolves the rest of the path against `../content/cards/ember_strike.yaml`. The linter computes these resolutions during `lint`.

**Nesting / depth.** Maximum reference depth is 6 dot-separated segments. References inside references (`{foo.{bar.baz}}`) are not supported in v0.1.

**Unresolved references.** A reference whose namespace, id, or sub-path does not resolve fires rule `broken-ref` at severity error.

**Context-local prefixes (D-012, v0.2.0-alpha).** Two reference prefixes are *not* globally-resolvable namespaces but reserved placeholders bound at rule-evaluation time:

- `{actor.<field>}` — the acting unit / entity in the current rule firing.
- `{target.<field>}` — the rule's target (resolved per `target_selection:`).

The linter's `broken-ref` rule skips refs starting with these prefixes; they are interpreted at rule-evaluation time against the live ECS world, not at lint time. Adding new context-local prefixes is a spec-level event (a v0.3 ratchet may close the set or extend it). Engines MUST treat these prefixes identically — divergence here defeats cross-engine determinism.

**Binding moment (D-012, normative at v0.2.0-alpha).** Both prefixes are bound at **apply-time** — at each `do:` step that references `{actor.<field>}` or `{target.<field>}`, the value is read live from the world at that step. Two rules follow:

1. **Symmetry.** `{actor.<field>}` and `{target.<field>}` resolve the same way. Neither is snapshotted at action-start or tick-start. The intuitive "target HP is live so accumulated damage kills" semantics extends to actor fields too.
2. **Composability.** A rule's `do:` array may mutate `{actor.<field>}` in step N and read the mutated value in step N+1. There is no implicit per-firing snapshot.

Engines MAY internally snapshot when they can prove no in-firing mutations affect the reads (e.g., tick-combat's xtreme reads `actor.attack` from a tick-start snapshot because tick-combat has no mid-tick attack mutations — the snapshot is provably equivalent to a live read). The normative contract is "produces the value of a live read at the step." When a future engine or future content introduces mid-firing mutations, the live-read semantics is what wins; snapshot-based engines must refactor. An explicit `snapshot:` step kind for use-the-frozen-value cases is a v0.3+ concern; at v0.2.0-alpha the only binding is apply-time. See `DECISIONS.md` D-012 and the v0.2 Phase-2 ambiguity #11.

---

## 4. The Universal Probabilistic Surface

The seven core namespaces, plus two cross-cutting namespaces, plus a tenth architecture-level namespace (`invariants`, §4.10). This is the heart of the spec. Every game, any genre, instantiates these.

### 4.1 `entities`

Anything addressable in game state: players, units, cards, items, enemies, tiles, projectiles, NPCs, levels, currencies-as-objects.

```yaml
entities:
  player:
    type: actor
    properties:
      hp: { from: "{resources.health}" }
      hand_size: 5
    status: implemented
    implemented_in: ["src/player.py"]
  cards:
    type: content_collection
    data_source: ../../content/cards
    schema_ref: "{content_schema.cards}"
    status: balanced
    count_target: 220
```

**Required keys per entity (top-level):** `type` (`actor | content_collection | terrain | currency | system_object`), `status`, `implemented_in` (omit only for `content_collection` types — those carry it per-entity-file). `properties` is required for non-`content_collection` types; `data_source` is required for `content_collection` types and must point to an existing directory.

### 4.2 `verbs`

Actions an actor performs. Verbs are the moment-to-moment vocabulary of the game.

```yaml
verbs:
  play_card:
    actor: "{entities.player}"
    cost: { resource: "{resources.energy}", amount: "varies_by_card" }
    target_schema:
      type: "{entities.cards}"
      filter: "{states.cards.in_hand}"
    effects:
      - resolve: "{rules.card_effect_resolution}"
    feel: "{feel.play_card}"
    status: implemented
    implemented_in: ["src/play_card.py"]
```

**Required keys per verb:** `actor`, `cost`, `target_schema`, `effects` (array), `status`, `implemented_in`. `feel` is optional but strongly recommended; if any verb declares `feel:`, then `gdd/feel.md` is required.

A verb that is defined but never referenced from a `loop` or another `verb`/`rule` fires rule `unreferenced-verb` at severity warning.

### 4.3 `resources`

Quantities that flow and constrain verbs. Resources are the bookkeeping layer of the game.

```yaml
resources:
  energy:
    scope: per_turn
    min: 0
    max: 3
    velocity_target: "{balance_targets.energy_per_turn}"
    visibility: hud
    status: balanced
    implemented_in: ["src/resources.py"]
```

**Required keys per resource:** `scope` (`per_turn | per_run | permanent`), `min`, `max`, `visibility` (`hud | inferred | hidden`), `status`, `implemented_in`. `velocity_target` is optional but strongly recommended for balance-sensitive resources; if present, it must reference a `balance_targets.*`.

### 4.4 `states` and `events`

Named finite-state *machines* on entities or on the game. Each `states` entry is a named machine with an explicit `initial` node, an explicit set of `nodes` (each optionally `terminal`), and an explicit set of `transitions`. **Totality is checkable**: every non-terminal node must have at least one outgoing transition — see `state-machine-coverage` in §9.1.

```yaml
states:
  card_lifecycle:
    initial: in_deck
    nodes:
      - id: in_deck
      - id: in_hand
      - id: in_play
      - id: in_discard
      - id: exhausted
        terminal: true                # absorbing; exempt from the dead-end check
    transitions:
      - { from: in_deck,    event: "{events.draw}",      to: in_hand }
      - { from: in_hand,    event: "{events.play_card}", to: in_play,   side_effects: ["{resources.energy} -= cost"] }
      - { from: in_play,    event: "{events.resolve}",   to: in_discard }
      - { from: in_hand,    event: "{events.exhaust}",   to: exhausted }
      - { from: in_discard, event: "{events.reshuffle}", to: in_deck }
events:
  draw:
    status: draft
    description: "A card moves from in_deck to in_hand; emitted by {verbs.draw_cards}."
  play_card:
    status: draft
    description: "A card moves from in_hand to in_play; emitted by {verbs.play_card}."
  resolve:        { status: draft, description: "A card finishes its in_play effects." }
  exhaust:        { status: draft, description: "A one-shot card moves to the exhausted terminal node." }
  reshuffle:      { status: draft, description: "discard pile is shuffled back into in_deck." }
```

**Required keys per machine:** `initial` (id of starting node), `nodes` (array of `{ id, terminal? }` — at least one), `transitions` (array of `{ from, event, to, side_effects? }`). `side_effects` is an array of prose-readable strings that may contain `{token.path}` references but is not normatively interpreted by `lint`.

**Required keys per event (v0.2.0-alpha):** `status` (from the §8.1 lifecycle). `implemented_in:` (array of globs) is required for `status >= prototyped` and is the hook for declaring where the event is *emitted* in code. `description:` (string) is recommended — explain what the event means and which verb/rule emits it.

**Events as first-class tokens (D-005 ratchet at v0.2).** Every `transitions[*].event` value is a `{events.<id>}` reference — events live in their own namespace, owned by `gdd/mechanics.md`. Bare-string events (v0.1.1 legacy) fire `state-machine-coverage` sub-finding `undefined-event` at severity warning; they ratchet to error in v0.3 once the migration window closes. Three further linter behaviors follow from events being tokens:

- An `{events.<id>}` reference that does not resolve fires `broken-ref` at error.
- An event defined but referenced by no transition fires `orphaned-entity` at warning (events join the standard orphan check).
- A `transitions[*].event` value that *is* a bare string is the `undefined-event` warning above.

> **Why `event:` and not `on:`.** YAML 1.1 — still the default behavior in most loaders, including PyYAML's `safe_load` — implicitly coerces unquoted `on`, `off`, `yes`, `no` to booleans. An unquoted `on: draw` would parse as `True: draw` and silently break the schema's required-key check. We use `event:` so that authors who forget to quote get a clear, working key. **Do not "tidy" this back to `on:`.** Tracked as decision D-001 in `DECISIONS.md`.

**Breaking change at v0.1.1.** The flat-enum form (`{ <state_name>: { transitions: [...] } }`) of v0.1.0 is removed; all `states` entries must be machines. Migration is mechanical: lift each old `<event> -> <next>` string into a `{ from: <state>, event: <event>, to: <next> }` transition, choose an `initial`, and mark any absorbing states `terminal: true`.

### 4.5 `rules`

Functions mapping `(state + verb) → (new state, outputs)`. Rules may invoke distributions and may compose other rules.

```yaml
rules:
  card_draw:
    given:
      verb: "{verbs.draw_cards}"
      state: "{states.cards.in_deck}"
    do:
      - sample: "{distributions.card_draw}"
        count: 1
        transition: "in_deck -> in_hand"
      - if_pile_empty: "{rules.reshuffle_discard_into_deck}"
    outputs: [card_drawn_event]
    status: implemented
    implemented_in: ["src/rules/card_draw.py"]
```

**Required keys per rule:** `given` (object with at least `verb`), `do` (array of operations), `outputs` (array), `status`, `implemented_in`. Any `do:` step whose semantics include randomness must reference a `{distributions.<id>}` — otherwise rule `undefined-distribution` fires at severity **error** (v0.1 design decision).

**Optional at v0.2.0-alpha: `target_selection:` (D-013).** When a rule applies effects to a target (e.g. damage), the rule must declare *how* the target is chosen. The field's value is drawn from a closed vocabulary: `none | first_alive_opposite | lowest_hp_opposite | highest_hp_opposite | random_alive_opposite | self | explicit`. `none` means the rule has no target (it affects global state or the actor itself implicitly). `explicit` defers selection to a `do:` step's `target:` field. Cross-engine rule: two engines that pick different targets for the same seed produce different integer trajectories — make this selection deterministic by declaring it in the spec, not in each implementation. See `DECISIONS.md` D-013 and the v0.2 Phase-2 ambiguity #5.

**Computable form on deterministic loop paths (D-011, advisory at v0.2.0-alpha; ratchets to error in v0.3).** Every item in a `do:` array SHOULD be a structured object (a YAML map), not a bare string. Bare-string steps like `resolve_unit_action` or `award_gold_to_winner` are *prose labels*, not computable procedures — two engines may interpret them differently, defeating the cross-engine determinism bar. The linter emits the advisory finding `determinism-undetermined-rule` for every bare-string item in a rule's `do:` whose enclosing rule is reachable from a deterministic loop (any `{loops.<id>}` whose `timescale: moment`). The intent is to catch the failure mode where spec authors leave resolution as prose — the "Phase-2 archaeology" pattern. See `DECISIONS.md` D-011.

### 4.6 `loops`

Repeating verb sequences. Every game has at least one loop; most have three (moment / session / meta).

```yaml
loops:
  combat_turn:
    timescale: moment
    duration: "~45s"
    sequence:
      - draw: "{verbs.draw_cards}"
      - play: "{verbs.play_card}"     # repeated until energy exhausted
      - end_turn: "{verbs.end_turn}"
    intended_dynamics:
      - "energy scarcity forces hand-shape decisions"
      - "synergy between two cards rewards combos"
    intended_aesthetics: [challenge, expression]
    feel_priority: high
    balance_targets:
      - "{balance_targets.turn_decision_time}"
      - "{balance_targets.average_combo_length}"
    status: balanced
    implemented_in: ["src/combat_loop.py"]
```

**Required keys per loop:** `timescale` (`moment | session | meta`), `duration` (string, prose-readable), `sequence` (array of verb refs), `intended_dynamics` (array of strings), `intended_aesthetics` (array drawn from the eight MDA aesthetics), `status`, `implemented_in`. `feel_priority` is optional (`low | medium | high`); `balance_targets` is optional but strongly recommended.

The root `game-design.md` must reference exactly one loop as `core_loop_ref:`. If absent, rule `missing-core-loop` fires at severity error.

### 4.7 `distributions`

First-class randomness. **Every random outcome anywhere in a `game-design.md` tree must reference a named distribution.** Naming randomness is the difference between a game whose balance is auditable and a game whose balance is hidden in source code.

**PRNG pin (D-015, normative at v0.2.0-alpha).** Cross-engine determinism (D-009) requires that every engine implementing a `game-design.md` tree produces *the same* sequence of raw PRNG outputs for the same seed. Distribution type alone (`gaussian`, `uniform`, …) does not constrain the underlying random source — two engines using different PRNGs (e.g. ChaCha20 vs PCG vs xoshiro) draw different sample streams from the same seed and the cross-engine integer trajectory desyncs at the very first sample. Phase 4 demonstrated this failure mode in tick-combat against Godot's PCG-family vs xtreme's ChaCha20.

Every tree (or per-distribution override) MUST declare:

```yaml
prng:
  algorithm: xoshiro256_starstar    # the default at v0.2.0-alpha
  seeding:   splitmix64              # how an integer seed initializes the state
  reference_vector:                  # MUST be shipped — first N raw u64 outputs at canonical_seed
    canonical_seed: 0
    outputs: [
      "0x860bfe4fec669882",
      "0x829cde4321bdff18",
      "0xd57ceaee872782c9",
      "0xc47fc8ff58359611",
      "0x71718b5da1661407"
    ]
```

Closed vocabulary at v0.2.0-alpha:

- **`xoshiro256_starstar`** (default) — Blackman & Vigna, 2018. 4×u64 state, output `rotl(s1 * 5, 7) * 9`. Trivially identical across Rust / GDScript / a Blueprint visual graph: a handful of shifts/rotates/xors on u64s, zero math-library dependency. The recommended default for any tree whose cross-engine trajectory contract matters.
- **`chacha20`** — D. J. Bernstein, 2008. Cryptographic-quality, reversible-resistant, broadly implemented. Use this *override* when a game needs the PRNG to be unpredictable to a player (e.g. two-player TCG where seed prediction could become an exploit). Tradeoff: implementing ChaCha20's quarter-rounds correctly in a Blueprint visual graph is materially harder than xoshiro's shift/xor ladder.
- **`pcg32` / `pcg64`** — O'Neill, 2014. Reserved for future per-game opt-in; not the default because "PCG" is a family with multiple variants and constants vary across libraries.

The default is **`xoshiro256_starstar` + `splitmix64` seeding**. A per-distribution `prng:` override is legal at v0.2.0-alpha for distributions that need a different generator (e.g. a card-shuffle distribution that wants cryptographic unpredictability while damage rolls stay on the cheap pinned PRNG); the override declares the same three fields.

**Reference vector requirement.** Every PRNG declaration MUST ship a `reference_vector:` of the first 5 raw u64 outputs at a `canonical_seed:`. Engines self-validate against the vector at adapter startup (or in a unit test) — divergence in the vector means the engine has misimplemented the PRNG or seeding, surfacing the bug before any trajectory comparison runs. The vector lives in the spec, not in each adapter; an adapter that disagrees with the vector is incorrect *regardless* of whether its trajectory happens to match.

**Seeding (`splitmix64`).** Given a single u64 seed `S`, `splitmix64` produces the four u64s used to initialize xoshiro256**'s state. The algorithm (Blackman & Vigna's reference): `z = (S += 0x9E3779B97F4A7C15); z = (z ^ (z >> 30)) * 0xBF58476D1CE4E1B5; z = (z ^ (z >> 27)) * 0x94D049BB133111EB; z = z ^ (z >> 31); return z`. Call four times to fill `(s0, s1, s2, s3)`. All arithmetic is wrapping u64. The canonical `seed: deterministic_per_run` field on a distribution is the input S to this procedure.

---

**Distribution types at v0.2.0-alpha** (eight total: seven probabilistic + one ordering-rule):

```yaml
distributions:
  card_draw:
    type: shuffle_bag
    of: "{entities.cards}"
    refill_when: empty
    seed: deterministic_per_run
    status: implemented
    implemented_in: ["src/rng/card_draw.py"]

  enemy_pack_size:
    type: weighted
    options: { small: 0.5, medium: 0.35, large: 0.15 }
    status: balanced
    implemented_in: ["src/rng/encounters.py"]

  critical_hit:
    type: uniform
    range: [0, 9]                # integer-native (D-016) — 0..9 inclusive
    threshold: 1                 # crit when sample < threshold (1-in-10 = 10% crit)
    output_domain: integer
    selection_rule: less_than    # see "Threshold comparison" below
    status: implemented
    implemented_in: ["src/rng/combat.py"]

  loot_rarity:
    type: pity_floor
    table: [common, uncommon, rare, epic]
    weights: [60, 30, 8, 2]      # integer weights (D-016); total_weight = 100
    pity: { rare_within: 12, epic_within: 40 }
    status: prototyped
    implemented_in: ["src/rng/loot.py"]

  damage_roll:
    # Integer-native gaussian-like (D-016). sum 3 PRNG draws each uniform
    # int in [-1, +1], then add params_from.mean. Result in [mean-3, mean+3]
    # with stddev ≈ √2 (close to gaussian(stddev=1)) — zero transcendentals,
    # bit-identical across engines that share the pinned PRNG.
    type: discrete_sum
    samples: 3
    range: [-1, 1]               # integer uniform per draw, inclusive
    params_from:
      mean: "{actor.attack}"
    clamp: [1, 99]
    output_domain: integer
    status: implemented
    implemented_in: ["src/rng/damage.py"]

  # `gaussian` is RESERVED for non-cross-engine, non-state-affecting uses
  # (cosmetic jitter, presentation noise). Its real-valued output depends on
  # libm transcendentals (`log`, `sin`/`cos`) which are NOT IEEE-754
  # correctly-rounded — even with the same PRNG and the same method, two
  # engines drift in the last ULP and `round_mode: half_to_even` will
  # eventually flip near `.5` boundaries. For determinism-critical
  # integer-state randomness, use `discrete_sum` instead. See D-016.
  cosmetic_jitter:
    type: gaussian
    mean: 0
    stddev: 1
    output_domain: real          # cosmetic-only; cross-engine non-binding
    status: prototyped
    implemented_in: ["src/fx/jitter.py"]

  scripted_event:
    type: deterministic
    sequence: [a, b, c, a, b, c]
    status: implemented
    implemented_in: ["src/scripted/intro.py"]

  # ordering_rule (added v0.2.0-alpha) — a *deterministic ordering procedure* over
  # a collection, distinct from `deterministic` (which is a literal sequence).
  # Use this when the order is computable from state, not pre-baked. Required
  # fields: `over` (the collection), `sort` (an ordered list of sort clauses).
  # Optional: `filter` (object).
  action_order:
    type: ordering_rule
    over: "{entities.units}"
    filter: { lifecycle: alive }
    sort:
      - { by: speed,        direction: desc }
      - { by: deploy_order, direction: asc }   # tie-breaker
    seed: deterministic_per_run
    status: implemented
    implemented_in: ["src/ordering.py"]
```

**Required keys per distribution:** `type` (one of the eight above), plus type-specific keys as shown, plus `status` and `implemented_in`. The `seed:` key is optional and defaults to `deterministic_per_run`; a value of `nondeterministic` requires prose justification.

**`discrete_sum` (D-016).** The integer-native alternative to `gaussian` for cross-engine state-affecting randomness. Result = `(params_from.mean or 0) + sum(uniform_int(range[0], range[1]) for _ in 0..samples)`, then `clamp`. Required: `samples` (positive integer), `range` (`[lo, hi]` integer pair, inclusive on both ends), and either `params_from.mean` or a fixed `mean:` field. Optional: `clamp: [min, max]`. Pure integer arithmetic; no `log`, `exp`, `sin`, `cos`, `sqrt`, or `pow` involved — bit-identical by construction on any engine that agrees on the pinned PRNG (§4.7 PRNG pin). The variance of the resulting distribution is `samples × (range[1] − range[0] + 1)² − 1) / 12` for integer uniforms; pick `samples` and `range` to land in the gameplay-feel band you want. (For tick-combat: `samples: 3, range: [-1, 1]` → stddev ≈ √2 ≈ 1.41, a close-enough discretization of the previous continuous `gaussian(stddev=1)`.)

**Output domain & rounding (D-010, deprecated for state-affecting use at v0.2.0-alpha Phase 4+; superseded by D-016).** The original D-010 contract — sample a continuous distribution at full float precision, clamp in real space, round to integer with `round_mode: half_to_even` — was correct in its ordering but incomplete in its determinism contract. Every continuous-then-rounded path depends on `log` / `exp` / `sin` / `cos` somewhere in the sampling code, and IEEE-754 does NOT mandate correctly-rounded transcendentals — real libm implementations (Rust's, Godot's, MSVC's under Unreal) differ in the last ULP. The integer rounding occasionally flips when a sample lands within ULP-distance of an x.5 boundary. Rare, unpredictable, and exactly the "almost always deterministic" posture this project refuses.

**For state-affecting, cross-engine-deterministic randomness, use `discrete_sum` (D-016) — not `gaussian` + `round_mode`.** The `output_domain` and `round_mode` fields remain in the schema for backward compatibility and for legitimate cosmetic/non-cross-engine uses, but they MUST NOT be the path by which integer simulation state is produced in any tree that declares cross-engine `verify_targets`. The legacy worked example at `examples/tick-combat/gdd/systems/distributions.md::damage_roll` was migrated to `discrete_sum` in Phase 4+ (see D-016).

**Canonical order of operations for `discrete_sum` (Phase 4+, normative):**

1. Draw `samples` uniform integers from the pinned PRNG in `range[0]..range[1]` (inclusive both ends). Each draw is `(rng.next_u64() mod (range[1] - range[0] + 1)) + range[0]` — pure integer arithmetic.
2. Sum the draws and add `params_from.mean` (or the fixed `mean`) if present.
3. Apply integer `clamp` to the result.

No floating-point arithmetic at any step. No transcendentals. Bit-identical across every engine that agrees on the PRNG (§4.7 PRNG pin) and applies these three steps. The "clamp first then round" question of D-010 no longer applies because there is nothing to round.

**Threshold comparison direction (uniform-with-threshold idiom, Phase 4+).** When a `uniform` distribution carries a `threshold:` field used to derive a boolean (the Bernoulli-via-uniform idiom — e.g. `critical_hit: { range: [0, 9], threshold: 1, selection_rule: less_than }`), the boolean output is the result of comparing the integer sample to the integer threshold via `selection_rule:` — `less_than` (`sample < threshold`) is the recommended default. Per-distribution `selection_rule:` MAY also take `less_than_or_equal`, `greater_than`, `greater_than_or_equal`, `equal`. The legacy float form (`range: [0.0, 1.0], threshold: 0.10`) is reserved for non-cross-engine use; for the cross-engine bar, integer uniforms with explicit `selection_rule:` are normative. Two engines that interpret `<` vs `<=` differently desync at exactly the threshold sample — the convention is now structurally declared, not implicit.

**Value-bearing `weighted` options (D-014, optional at v0.2.0-alpha).** Bare-number `weighted.options` (`{ small: 60, medium: 30, large: 10 }`) declare *only* probability mass. When the weighted distribution's category labels need to carry an associated value (e.g. `gold_drop` returns "small" with weight 60 *and* "small" is worth 1 gold), the option shape may be expanded to `{ <category>: { weight: <int>, value: <any> } }`:

```yaml
gold_drop:
  type: weighted
  options:
    small:  { weight: 60, value: 1 }     # integer weights (D-016)
    medium: { weight: 30, value: 3 }
    large:  { weight: 10, value: 10 }
  selection_rule: declaration_order_first_above   # D-017
  status: implemented
```

Either shape is schema-legal; mixed shapes within a single `options:` map are not (all-bare or all-objects). When values are absent and consuming code needs them, the resolution belongs in the spec, not in the implementation (see `DECISIONS.md` D-014 and the v0.2 Phase-2 ambiguity #4).

**Weighted selection rule (D-017, Phase 4+, normative).** `weighted.options` MUST declare `selection_rule:`. The single normative value at v0.2.0-alpha Phase 4+ is `declaration_order_first_above`:

1. Compute the integer total weight `W = sum(options[k].weight for k in declaration order)`. Integer weights are normative for cross-engine determinism; float weights are forbidden in any tree with cross-engine `verify_targets`.
2. Draw `d = rng.next_u64() mod W`.
3. Walk options in YAML declaration order, maintaining a running cumulative sum `c`.
4. Select the **first** option whose `c > d` (strict greater-than).

The "strict greater-than" is the same class of decision as the `<` vs `<=` boundary on the threshold idiom — `c >= d` would shift mass at the cumulative boundary by one slot, divergent across engines that pick the other comparison. The selection rule lives in the spec because it MUST be identical across engines; per-option behavior is fully determined by `(W, declaration order, running cumulative sum, strict >)`.

**On YAML declaration order.** The standard's loader (`GdmdLoader` in `src/game_design_md/loader.py`) preserves YAML map insertion order via Python 3.7+ dict semantics. Engines reading `weighted.options` MUST honor that order — never re-sort by key, never iterate via a hash-map. Phase 4 found that both xtreme and Godot happened to honor declaration order accidentally; the rule now requires it.

**Templated distribution parameters (D-012, optional at v0.2.0-alpha).** A distribution may parameterize its sampling theory from rule-evaluation-time context via a `params_from:` map:

```yaml
damage_roll:
  type: gaussian
  params_from:
    mean: "{actor.attack}"      # resolved from the acting unit's `attack` stat
  stddev: 1
  clamp: [1, 99]
  output_domain: integer
  round_mode: half_to_even
  status: implemented
```

Keys in `params_from:` match the distribution's parameter names (`mean`, `stddev`, `threshold`, …); values are `{namespace.id}`-shaped strings drawn from a context-local vocabulary the *consuming rule* binds (e.g. `{actor.<field>}` resolves to the acting unit's `<field>` value). The static schema accepts `params_from:` as an object of string-valued entries; the *semantics* of which contexts are bound is rule-local and project-defined at v0.2.0-alpha (a closed vocabulary ratchets in v0.3). A distribution with `params_from:` overrides its inline parameter values for any key present.

**Binding moment for `params_from:` reads.** Each parameter sourced via `params_from:` is read at **apply-time** — at the `do:` step that calls `sample:` on this distribution, the context refs are resolved live against the world. This is the same rule as for context-local refs anywhere else (see §3). Two engines that read `{actor.attack}` at different moments (e.g. one at action-start, one at the sample step) produce different integer trajectories the moment any mid-firing mutation is added — the canonical timing must live in the spec, not in each engine. Tick-combat's xtreme reads `actor.attack` from a tick-start snapshot, which is provably equivalent under tick-combat's no-mid-tick-mutation invariant; this is permitted as an optimization, not a different semantics.

### 4.8 Cross-cutting: `feel`

Game feel per Steve Swink's six dimensions: input, response, context, polish, metaphor, rules. Authored per verb.

```yaml
feel:
  play_card:
    input:    "drag and release with momentum; snap-back on illegal target"
    response: "card translates to play zone over 180ms cubic-ease-out"
    context:  "energy meter pulses red when card is over the play zone"
    polish:   "screen flash on resolve; shake amplitude scales with damage"
    metaphor: "playing a card feels like a definitive commit; no undo"
    rules:    "during resolve, no other verbs are accepted"
    status: prototyped
    implemented_in: ["src/feel/play_card.py"]
```

**Required keys per feel entry:** all six dimensions as strings, plus `status` and `implemented_in`. Empty-string is permitted for dimensions that genuinely do not apply (e.g. `metaphor: ""` for a UI verb) — but every key must be present.

### 4.9 Cross-cutting: `balance_targets`

Designer-intended outcomes the game must satisfy at ship. Loops and content reference these so that balance lives in one place and the `diff` regression check (§9.2) can detect when they shift.

**At v0.2 every target declares a `target_kind:` discriminator** (D-003 ratchet from v0.1.1's permissive `target: {}`). Three kinds, each with a fixed shape:

```yaml
balance_targets:
  # scalar — a single number or string with a [low, high] tolerance band.
  energy_per_turn:
    target_kind: scalar
    target: 3
    tolerance: [3, 3]
    measure: "average energy budget per combat turn"
    status: balanced

  # range — the target itself is a band. Two matcher shorthands:
  #   { between: [lo, hi] }      — explicit closed interval
  #   { near: v, tolerance: t }  — v ± t (i.e. [v-t, v+t])
  median_turns_per_combat:
    target_kind: range
    target: { near: 6, tolerance: 2 }
    measure: "median turns to clear a non-boss encounter, Ascension 0"
    status: balanced

  # distribution_over_categories — a composite map; tolerance is per-category.
  cards_per_rarity:
    target_kind: distribution_over_categories
    target:    { common: 110, uncommon: 80, rare: 30 }
    tolerance: { common: 10,  uncommon: 10, rare: 5 }
    measure: "designed card count per rarity"
    status: balanced
```

**Required keys per target:** `target_kind` (one of the three above), `target`, `measure`, `status`. `tolerance` is required for `scalar` and `distribution_over_categories`; `range` carries its band inside `target`. Shape rules per kind are enforced by the JSON Schema and reiterated below:

| `target_kind` | `target` shape | `tolerance` shape |
| --- | --- | --- |
| `scalar` | number or string | `[low, high]` — 2-element array of comparables |
| `range` | `{ between: [lo, hi] }` *or* `{ near: v, tolerance: t }` | *(omitted — band is in target)* |
| `distribution_over_categories` | `{ <category>: <value>, ... }` (object, ≥1 key) | `{ <category>: <tolerance>, ... }` (object, ≥1 key) |

A `diff` between two trees emits an entry for any target whose `target` value changed; if a `scalar` target's value left its previous `tolerance` band (or a `distribution_over_categories` shifted any category outside its per-category tolerance), exit code 1.

**Legacy permissive targets.** A `balance_targets.<id>` missing `target_kind:` fires rule `balance-target-untyped` at severity warning. This is the v0.1.1 → v0.2 migration backstop; in v0.3 the rule ratchets to error and `target_kind` becomes structurally required by the loader.

If the example tree contains no `balance_targets`, rule `missing-balance-targets` fires at severity error.

### 4.10 Architecture invariants

A tenth namespace, `invariants`, owned by `gdd/architecture-invariants.md`. Each invariant declares a verifiable property of the *generated codebase* — a numeric domain, a structural pattern, a layer boundary, an inter-layer communication rule, or a determinism guarantee. **Invariants are how the design document tells the agent which assumptions the code must satisfy.** They are deliberately *engine-neutral*: an invariant declares a rule, never a tool.

```yaml
invariants:
  damage_is_integer:
    kind: numeric_domain
    rule: "All damage, health, and resource quantities resolve to integers."
    applies_to: ["{resources}", "{rules.damage_resolution}"]
    enforcement: lint
    severity: error
  data_behavior_separation:
    kind: architectural_pattern
    rule: "Entities are composed of data-only structures; logic lives in stateless systems that query them. No gameplay logic inside presentation/render code."
    applies_to: ["{entities}", "{rules}"]
    enforcement: advisory
    severity: warning
  state_not_in_presentation:
    kind: layer_boundary
    rule: "Persistent game state is never stored on presentation/render nodes."
    applies_to: ["{states}"]
    enforcement: lint
    severity: error
  cross_layer_via_events:
    kind: communication
    rule: "Communication between simulation and presentation layers uses asynchronous events, not direct references."
    enforcement: advisory
    severity: warning
  deterministic_given_seed:
    kind: determinism
    rule: "Given a fixed seed, all distribution draws are reproducible."
    applies_to: ["{distributions}"]
    enforcement: verify
    severity: error
```

**Required keys per invariant:** `kind`, `rule`, `enforcement`, `severity`. `applies_to` is optional (an array of `{namespace.id}` refs the invariant governs).

- `kind` enum: `numeric_domain | architectural_pattern | layer_boundary | communication | determinism`.
- `enforcement` enum: `lint` (statically checkable now), `verify` (checked at runtime by `gdmd verify` — §9.5), `advisory` (declared, human/agent-reviewed, never auto-failed).
- `severity` enum: `error | warning | info`.

**Linter behavior.** For each invariant with `enforcement: lint`, `lint` runs an associated static check and emits an `invariant-violation` finding at the invariant's declared severity. Invariants with `enforcement: verify` are deferred to `verify` and are a no-op for `lint`. Invariants with `enforcement: advisory` produce an `info`-level reminder in the `lint` summary; they never affect exit code.

The full prose rationale for each invariant lives in `gdd/architecture-invariants.md`'s Markdown body, keyed by the invariant `id`. **Invariants must never name an engine, framework, renderer, or platform** — they describe properties of the *generated codebase*, not the tools used to build it.

---

## 5. Core Entry File

The root `game-design.md`. Under ~200 lines, llms.txt-style navigation.

### 5.1 Required frontmatter

```yaml
---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: core
name: "Ember Ascent"
short_pitch: "A 30-minute deckbuilder roguelike about reshaping your hand each turn."
genre_tags: [deckbuilder, roguelike, single-player]
status: prototyped
version: 0.4.2
last_updated: 2026-05-18
target_platforms_neutral: [desktop, handheld]
pillars:
  - "Every turn, a meaningful hand-shape decision"
  - "Synergy is discoverable, not memorizable"
  - "A run is short enough to finish on a lunch break"
non_goals:
  - "Multiplayer"
  - "Real-time combat"
  - "Persistent meta-progression unlocks"
player_experience_goals:
  primary: [challenge, expression]    # MDA aesthetics
  secondary: [discovery]
  explicit_non_goals: [submission, fellowship]
core_loop_ref: "{loops.combat_turn}"
files:
  pillars: gdd/pillars.md
  loops: gdd/loops.md
  mechanics: gdd/mechanics.md
  distributions: gdd/systems/distributions.md
  combat: gdd/systems/combat.md
  progression: gdd/systems/progression.md
  cards: gdd/content/cards.md
  enemies: gdd/content/enemies.md
  feel: gdd/feel.md
  balance: gdd/economy-balance.md
  glossary: gdd/glossary.md
implementation_pointers:
  combat_loop: "src/combat/**/*.py"
  card_system: "src/cards/**/*.py"
  rng: "src/rng/**/*.py"
---
```

The four fields `pillars`, `non_goals`, `player_experience_goals`, and `core_loop_ref` are the **stability guarantee** — they are the only frontmatter values agreed to remain stable for the lifetime of the project. Everything else may drift, but must be re-validated when it does.

### 5.2 Canonical prose section order

```
# {name}
> {short_pitch}

## High Concept
## Pillars & Non-Goals
## Player Experience Goals
## Core Gameplay Loop
## Universal Surface         # short, with links into gdd/*.md
## How to Use This Document (for the Agent)
## Glossary                  # optional but recommended; or link to gdd/glossary.md
```

Sections beyond these are accepted (preserved verbatim) but must come *after* `Glossary`. Unknown sections inside the canonical block fire rule `section-order` at severity error.

The root file MUST NOT contain authoritative numbers in its prose; all numbers live in the subfiles.

---

## 6. Content-Heavy Data Pattern

A "content-heavy type" is an `entities` kind whose `count_target` is ≥ 20. (In a deckbuilder: cards, enemies, items, relics, events. In a party RPG: classes, skills, items, encounters. In a TCG: cards, archetypes.) For these types, inlining the full set in Markdown is a context-window disaster.

**Rule (v0.1, mandatory):** if `count_target >= 20`, the entries MUST be split into a sibling `content/<entity>/*.yaml` tree referenced via `data_source` on the content-schema file. The `gdd/content/<entity>.md` subfile contains only the **schema + one representative example** as prose. Violating this fires rule `inline-content-over-threshold` at severity error.

For `count_target < 20`, the split is recommended but optional.

### 6.1 Content-schema file frontmatter

```yaml
---
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-schema
status: balanced
last_verified: 2026-05-18
entity: cards
schema:
  required: [id, name, cost, type, rarity, effects]
  properties:
    id:      { type: string, pattern: "^[a-z][a-z0-9_]*$" }
    name:    { type: string }
    cost:    { type: integer, minimum: 0, maximum: 5 }
    type:    { enum: [attack, skill, power] }
    rarity:  { enum: [common, uncommon, rare] }
    effects: { type: array }
data_dir: ../../content/cards
count_target: 220
balance_refs:
  - "{balance_targets.cards_per_rarity}"
  - "{balance_targets.average_card_cost}"
---
```

### 6.2 Per-entity file (`content/<kind>/<id>.yaml`)

```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: ember_strike
status: balanced
implemented_in: ["src/cards/ember_strike.py"]
name: "Ember Strike"
cost: 1
type: attack
rarity: common
effects:
  - { kind: damage, amount: 6, distribution: "{distributions.damage_roll}" }
  - { kind: apply_state, state: "{states.enemies.burning}", duration: 2 }
```

The linter (a) validates each entity against the content-schema-file `schema:`, (b) requires `id` to match the filename stem, and (c) enforces presence of `status` and `implemented_in`.

---

## 7. Canonical Section Order & Unknown Content

### 7.1 Canonical `##` order per file type

**Core file (`game-design.md`):** as enumerated in §5.2.

**Subfile (`gdd/*.md`):** the canonical order is
```
## Tokens                  # short table-of-contents into the frontmatter; optional but recommended
## Rationale
## Open Questions          # optional
## Change Log              # optional
```
Sections beyond these are accepted but must come after `Change Log`.

**Content-schema file (`gdd/content/*.md`):**
```
## Schema
## Representative Example
## Balance Notes
## Open Questions          # optional
```

### 7.2 Unknown content handling

| Situation | Behavior |
| --- | --- |
| Unknown `##` section *after* the canonical block | Preserved without error. |
| Unknown `##` section *inside* the canonical block | `section-order` rule, severity error. |
| Unknown frontmatter key | Accepted; ignored by the linter; preserved by `export`. |
| Unknown enum value (e.g. a new MDA aesthetic) | Accepted with warning. |
| Unknown component-style nested property | Accepted with warning. |
| Duplicate `##` heading in the same file | **Hard error; file rejected.** Same rule as upstream `DESIGN.md`. |
| Frontmatter parse error | Hard error; file rejected. |

---

## 8. Status Lifecycle & Anti-Drift

### 8.1 Status values

Every section and content entity declares a `status:` from this lifecycle:

```
draft → prototyped → implemented → balanced → shipped
                                              ↘ cut
```

| Value | Meaning |
| --- | --- |
| `draft` | Written but no code exists. `implemented_in:` may be empty or point to planned paths that do not yet exist. |
| `prototyped` | First-pass code exists; the section may be wrong but is wired up end-to-end. `implemented_in:` paths exist. |
| `implemented` | Code is complete and correct against the spec, but balance is unverified. |
| `balanced` | Code matches spec AND any referenced `balance_targets` measure within tolerance. |
| `shipped` | Released to players. Implies `balanced`. |
| `cut` | Removed from the design. The entity is retained in the doc for historical reference but excluded from `lint`'s normal rules; instead, `lint` errors if anything else still references it (rule: `broken-ref` against a cut target). |

**Allowed transitions:** strictly left-to-right along the arrows above, plus any node may transition to `cut`. Backward transitions are permitted in the same commit (the spec is a living document and walking a status back is sometimes correct), but `gdmd diff` (§9.2) emits a `status-regression` finding for `balanced → implemented`, `shipped → balanced`, or any other backward step, so the author has a chance to confirm it is intentional. `lint` does not check status regression because it has no baseline to compare against — the check belongs to `diff`.

### 8.2 Anti-drift mechanisms

The standard exists because GDDs drift. These four mechanisms keep the doc and the code in sync:

1. **`implemented_in` existence check.** For every entity with status ≥ `prototyped`, every path/glob in `implemented_in:` must resolve to at least one real file in the repo. If a glob resolves to zero files, the linter fires `broken-implementation-pointer`. **Entities at status `draft` are silent** — the code isn't written yet; that's not a defect, it's the expected state of a design doc. **Severity is `error` at v0.2.0-alpha** (ratcheted from `warning` at v0.1.1 once the tick-combat / xtreme reference implementation shipped real source; see `DECISIONS.md` D-002). The intended discipline: the moment a designer advances an entity's `status:` to `prototyped` or higher, the linter verifies code exists at the declared paths — drift is caught at the boundary.

2. **`last_verified` staleness.** For every subfile, content-schema file, and content-entity file, the linter compares the `last_verified:` date against the most recent `mtime` of the files in its `implemented_in:`. If any source file is newer than `last_verified:` by more than 30 days, rule `stale-section` fires at severity warning.

3. **`{token.path}` broken-ref and orphan detection.** Every `{ns.id}` reference resolves, or `broken-ref` fires (error). Every token defined in the tree is referenced at least once, or `orphaned-entity` fires (warning) — except for top-level `entities` of `type: actor` (the player) and any explicit `cut` entries.

4. **The session-end agent ritual.** Documented in `AGENTS.md`: on every change, update affected `status:`, update `implemented_in:`, touch `last_verified:` on touched sections, bump `version:` in the root file, update `last_updated:`, re-run `lint`, fix findings, optionally re-run `diff` against the last release. This ritual is the contract between human designers and AI agents that keeps the standard living.

**Stability guarantee.** Only `pillars`, `non_goals`, `player_experience_goals`, and `core_loop_ref` are immutable for the life of a project. Changing any of them is a project-wide event and must be accompanied by a `version:` *major* bump in the root file and a corresponding entry in `gdd/glossary.md`'s change log if one exists.

---

## 9. The CLI

Verbs: `lint | diff | export | spec`. Installed binaries: `game-design.md` and the short alias `gdmd`. Reference implementation in Python ≥ 3.10.

### 9.1 `lint`

```
gdmd lint <path-to-example-tree>
```

Emits structured JSON to stdout:

```json
{
  "findings": [
    {
      "rule": "broken-ref",
      "severity": "error",
      "file": "gdd/loops.md",
      "location": "loops.combat_turn.sequence[1]",
      "message": "Reference {verbs.play_card} does not resolve.",
      "suggestion": "Did you mean {verbs.play_a_card}?"
    }
  ],
  "summary": { "files": 14, "errors": 1, "warnings": 3 }
}
```

Exit code: `0` if zero findings of severity `error`; `1` otherwise. Warnings never affect exit code.

**Linter rules in v0.1:**

| Rule | Severity | Trigger |
| --- | --- | --- |
| `broken-ref` | error | A `{ns.id}` reference does not resolve. |
| `broken-implementation-pointer` | error (v0.2+) | An `implemented_in:` path/glob resolves to zero files. Entities at `status: draft` are exempt. See §8.2 mechanism 1 and `DECISIONS.md` D-002. |
| `orphaned-entity` | warning | A token is defined but never referenced. |
| `unreferenced-verb` | warning | A verb is defined but no loop or rule invokes it. |
| `missing-pillars` | error | Root file `pillars:` is absent or has fewer than 3 entries. |
| `missing-core-loop` | error | Root `core_loop_ref:` is absent or does not resolve. |
| `missing-balance-targets` | error | No `balance_targets:` defined anywhere in the tree. |
| `undefined-distribution` | **error** | A `rule.do[].sample` or any other stochastic operation does not reference a `{distributions.<id>}`. |
| `inline-content-over-threshold` | error | A content-schema file with `count_target >= 20` does not declare `data_dir:` (i.e. entries are inlined). |
| `stale-section` | warning | A subfile's `last_verified:` is more than 30 days older than the mtime of any file in its `implemented_in:`. |
| `balance-target-untyped` | warning (v0.2.0-alpha), error (v0.3+) | A `balance_targets.<id>` lacks the `target_kind:` discriminator (v0.1.1 legacy shape). See `DECISIONS.md` D-003. |
| `determinism-undetermined-rule` | info (advisory) at v0.2.0-alpha; warning in v0.3; error in v0.4 | A `do:` step inside a `{rules.<id>}` reachable from a deterministic loop (`{loops.<id>}` with `timescale: moment`) is a bare string instead of a structured object. Surfaces the "Phase-2 archaeology" pattern — prose labels for resolution procedures don't constrain implementations. See `DECISIONS.md` D-011. |
| `section-order` | error | A `##` section appears before its canonical predecessor, or duplicate `##` heading (hard error). |
| `invariant-violation` | varies | An `enforcement: lint` invariant's static check failed; finding severity matches the invariant's declared `severity`. |
| `state-machine-coverage` | varies | A `states` machine violates totality. Sub-findings: `dead-end` (error — non-terminal node with no outgoing transition), `undeclared-destination` (error — `to:` a node not in `nodes`), `unreachable-node` (warning — node not reachable from `initial`), `missing-initial` (error — no `initial`, or `initial` not in `nodes`), `undefined-event` (warning at v0.2.0-alpha, error in v0.3 — transition `event:` is a bare string instead of a `{events.<id>}` token). |
| `verify-result-regression` | error/warning | A prior `verify` axis result regressed. `build_health` and `behavioral_alignment` regressions are error; `presentation_usability` regressions are warning. Emitted only by `gdmd verify` (§9.5), not by `lint`. |

### 9.2 `diff`

```
gdmd diff <old-tree> <new-tree>
```

Emits structured JSON describing token-level changes:

```json
{
  "added": [...],
  "removed": [...],
  "changed": [
    { "path": "balance_targets.win_rate_normal.target",
      "from": 0.55, "to": 0.62 }
  ],
  "balance_regressions": [],
  "status_regressions": []
}
```

**Diff-only findings** (these have no `lint` analogue because `lint` has no baseline):

- `balance_regressions` — `balance_targets.<id>.target` moved *outside* its previous `tolerance` band.
- `status_regressions` — `status:` regressed from `balanced` or `shipped` to an earlier lifecycle state (per §8.1). The rule formerly listed as `status-regression` in §9.1 lives here.

Exit code: `0` if both `balance_regressions` and `status_regressions` are empty; `1` otherwise.

### 9.3 `export`

```
gdmd export <path> --format {schema|tokens}
```

- `--format schema` emits the JSON Schema at `schema/game-design.schema.json` to stdout.
- `--format tokens` walks the tree and emits a single flat JSON object: every resolved `{ns.id}` keyed by its dotted path. Useful as an embedding-friendly snapshot of the design.

### 9.4 `spec`

```
gdmd spec
```

Prints this document (`docs/spec.md`) to stdout, with frontmatter stripped, for injection into an agent prompt.

### 9.5 `verify`

```
gdmd verify <path> [--adapter <name>] [--baseline <prior-result.json>]
```

**Status: stable at v0.2.0-alpha.** `verify` is the dynamic-loop complement to `lint`'s static checks. It does not itself build or launch anything — instead it declares a *contract*, a *result schema*, and a *canonical trajectory format* that the project's own adapter must satisfy.

`verify` reads:

1. The `verification` block — either `gdd/verification.md` frontmatter (`file_type: subfile`), or `verify_targets:` directly in the core file.
2. The project-supplied **adapter** (an executable the project declares under `adapters:`) which knows how to build the project, run an automated session, and emit observations as JSON conforming to the `VerifyResult` schema (§9.5.3) plus, when declared, a canonical trajectory file (§9.5.5).

The standard owns the **contract, the result schema, and the trajectory format**; the project owns the **adapter** (only the project knows its engine). This is the engine-neutral form of "headless playability" — the spec never names a runner.

The reference adapter at `examples/tick-combat/tools/verify-adapter` exercises the full contract: `behavioral_alignment` via canonical JSONL trajectory comparison against a locked golden, negative-control via alt-seed divergence (§9.5.7), and `build_health` via successful adapter invocation. Phase 4's Unreal adapter will implement the *same* contract; the trajectory format and `VerifyResult` shape are normative and engine-neutral, exactly as the `gdd/` tree is engine-neutral.

#### 9.5.1 Three audit axes

- **`build_health`** — the project builds and starts without errors or unresolved asset/token references.
- **`behavioral_alignment`** — declared `loops`, `rules`, and `balance_targets` produce the expected observable outcomes over an automated session (e.g., a fixed-seed run lands within the declared `win_rate` band; a state machine reaches its terminal node).
- **`presentation_usability`** — optional, pluggable. If a `presentation` adapter is supplied (vision model, pixel diffing, layout assertions — the standard doesn't care which), it audits for overlap/clipping/contrast. Absent an adapter, this axis is *skipped*, not failed.

#### 9.5.2 `verify_targets` shape

```yaml
verify_targets:
  - axis: behavioral_alignment
    target: "{loops.combat_turn}"
    seed: 12345
    expect:
      trajectory: { matches_golden: ./tests/golden_seed_12345.jsonl }
    negative_control:
      seeds: [99999]
      expect: { trajectory_diverges_from_primary: true }
  - axis: behavioral_alignment
    target: "{balance_targets.win_rate_ascension_0}"
    sessions: 200
    expect: { win_rate: { near: 0.55, tolerance: 0.05 } }
  - axis: build_health
    expect: { builds: true, unresolved_refs: 0 }
adapters:
  default: "./tools/verify-adapter"        # project-supplied executable; the engine lives HERE, not in the spec
  presentation: null                        # optional; skipped if null
```

`expect:` is a free-form object; the adapter is responsible for matching observed values against it. The standard normatively interprets two expectation shapes — `{ trajectory: { matches_golden: <path> } }` (§9.5.5) and the matcher shorthands `{ between: [low, high] }`, `{ near: v, tolerance: t }`, `{ equals: v }`. Other keys are pass-through to the adapter.

`negative_control:` is the spec-level mechanism for catching adapters that pass vacuously (§9.5.7). It declares one or more alternative seeds the adapter must also run, and the divergence assertion `verify` makes against the primary run.

#### 9.5.3 Result schema

The adapter emits, on stdout, a JSON document conforming to `$defs.VerifyResult`:

```json
{
  "results": [
    {
      "axis": "behavioral_alignment",
      "target": "{balance_targets.win_rate_ascension_0}",
      "observed": { "win_rate": 0.572 },
      "expected": { "win_rate": { "near": 0.55, "tolerance": 0.05 } },
      "pass": true,
      "notes": "200 fixed-seed sessions"
    }
  ],
  "summary": { "runs": 3, "passed": 3, "failed": 0, "skipped": 0 }
}
```

#### 9.5.4 Exit code

- `0` if every non-`presentation_usability` target passed.
- `1` if any `build_health` or `behavioral_alignment` target failed.
- `0` (with warnings in `notes`) if only `presentation_usability` regressed.

When invoked with `--baseline <prior-result.json>`, `verify` additionally fires `verify-result-regression` findings for any tracked axis that worsens versus the baseline (severity: error for `build_health`/`behavioral_alignment`; warning for `presentation_usability`).

#### 9.5.5 Trajectory format (engine-neutral, canonical JSONL)

A `behavioral_alignment` verify_target MAY declare a trajectory expectation. When present, the adapter writes a *trajectory file* in canonical JSONL to the path supplied via `--trajectory` (§9.5.6). The format is normative across engines:

- **One JSON object per simulation unit per line.** The simulation unit (tick, turn, frame, beat) is declared by the game in `gdd/verification.md` under `trajectory.unit:`.
- **UTF-8 encoding, LF line endings, trailing newline on the last line.** No CRLF, no leading BOM.
- **Canonical JSON per line.** No extra whitespace inside objects or arrays. **JSON object keys MUST be ASCII** (`[a-zA-Z0-9_]`); they are emitted in **ASCII codepoint order** (which is byte-wise sort order for ASCII). No exceptions — non-ASCII keys are a schema-author bug.
- **Integer values for all gameplay-state fields.** Default integer width is **int32** (range `−2,147,483,648 .. 2,147,483,647`). A game's `trajectory.schema:` MAY declare `width: int64` per field for values that genuinely need a wider range; engines MUST use a representation that round-trips the declared width without precision loss. Mixing widths within a trajectory is permitted only by per-field schema declaration; the default for every numeric field is int32. Float fields are NOT permitted in the trajectory (see the `gameplay_state_is_integer` invariant family).
- **Enum values are ASCII lowercase**, drawn from the closed set declared in the game's `trajectory.schema:`. Lowercasing is **ASCII-only**: codepoints `U+0041..U+005A` (`A-Z`) map to `U+0061..U+007A` (`a-z`); every other codepoint passes through unchanged. **Locale-aware case conversion is forbidden** — Rust's `str::to_lowercase`, C++ `std::tolower(int)` under a non-C locale, and .NET `string.ToLower()` without `CultureInfo.InvariantCulture` will silently diverge on certain inputs (Turkish `İ → i̇`, German `ß → ss`, etc.). Engines MUST implement ASCII-only lowercasing for trajectory enum serialization.
- **Sorted element ordering inside arrays.** Every array in the schema MUST declare a `sort_by:` key list that produces a **total order** over the array's elements — meaning the declared keys, applied lexicographically, *uniquely* order every pair of elements in any valid trajectory. (Conventional "stable" sort — insertion-order-preserving — is **NOT** the contract: two engines build their arrays in different insertion orders and would desync.) The array is sorted *before* serialization. **String sort keys compare byte-wise on the UTF-8 representation** (which equals codepoint order for valid UTF-8); locale-aware collation is forbidden. If a declared `sort_by:` does not produce a total order on some valid trajectory (any tie remains), the schema is malformed and the cross-engine desync will surface as a sort-instability bug rather than a simulation bug.

**Cross-engine bar (D-009).** Byte-identical trajectory files given the same seed and the same `gdd/` tree, across all engines implementing the game. Two engines producing *structurally* equivalent but *byte* different trajectories (different enum spellings, key reordering, whitespace, sort tie-break) have diverged in the *trajectory serialization*, not the simulation — the spec rules it a failure either way. The trajectory format is itself spec; the trajectory is data.

**Per-game declaration in `gdd/verification.md`:**

```yaml
trajectory:
  unit: tick                          # what one line represents
  schema:                             # canonical JSONL shape per line
    tick:        { type: integer, minimum: 0 }                    # int32 default
    phase:       { enum: [setup, ticking, resolved] }
    gold:        { type: integer, minimum: 0 }
    units:
      type: array
      sort_by: [side, deploy_order]   # total-order key — see below
      items:
        id:           { type: string }
        side:         { enum: [player, enemy] }
        deploy_order: { type: integer, minimum: 0 }
        hp:           { type: integer, minimum: 0 }
        lifecycle:    { enum: [alive, stunned, dead] }
```

**Why `sort_by: [side, deploy_order]` is a total order for tick-combat.** `side` has two values (`player`, `enemy`, comparing as ASCII strings so `enemy < player`); `deploy_order` is a 0-based integer that is unique within a side per the deploy-roster contract. The pair `(side, deploy_order)` is therefore unique across every valid trajectory — no two units can collide, so sorting is total. If a future content type allowed two units on the same side at the same `deploy_order`, this `sort_by:` would no longer be a total order and would have to be extended (e.g. tie-break by `id`).

The schema is per-game, not per-engine. Both xtreme (engine A) and a future Unreal port (engine B) emit trajectories conforming to this same schema. The reference golden lives in the engine A directory under `tests/`; future engines test against the *same* golden, not a per-engine fixture. **At v0.2.0-alpha the `schema:` body is advisory** — `verify` does not validate trajectory line-by-line against it; trajectory equality is checked byte-for-byte against the golden fixture, and the schema serves as the canonical human reference. A `trajectory-schema-validation` lint rule ratchets in v0.3.

**Why JSONL.** Any frontier language has a JSON parser. Each line is independent (so partial-progress trajectories from a crashed run are still consumable). The format diffs cleanly under git (one tick per line). Canonicalization (sorted keys, no whitespace) makes byte-identity the natural equality.

#### 9.5.6 Adapter invocation contract

`gdmd verify` invokes the project's adapter executable **once per `verify_target`** (and additionally once per negative-control seed, §9.5.7):

```
<adapter> --target <token-ref> --seed <int> [--trajectory <path>] [--max-steps <int>]
```

- `--target` — the token ref of the verify_target (e.g. `{loops.combat_turn}`, `{balance_targets.win_rate_neutral_formation}`, or the literal `build_health` axis when no `target:` ref is declared). Adapters use this to decide which simulation to run.
- `--seed` — the seed declared on the target. For negative-control invocations, `gdmd verify` substitutes each negative-control seed in turn.
- `--trajectory` — optional path to write the canonical JSONL trajectory to. Supplied by `gdmd verify` whenever the target's `expect:` declares `trajectory:`; absent otherwise.
- `--max-steps` — optional cap on simulation length. Per-game default; the spec recommends a generous cap so deterministic-but-slow runs don't get prematurely truncated.

The adapter writes:

- **stdout** — a single `VerifyResult` JSON object (§9.5.3). The adapter MAY also include a `trajectory` key inside `results[*].observed` if it wants to convey trajectory metadata (line count, terminal phase, terminal-state hash), but the *authoritative* trajectory is the JSONL file at `--trajectory`.
- **`<trajectory-path>` if supplied** — canonical JSONL trajectory (§9.5.5).
- **stderr** — human-readable progress / diagnostics. `verify` does not parse it.

Exit code per §9.5.4. The adapter is *stateless across invocations*: each call handles exactly one target × seed combination. `gdmd verify` aggregates the per-call results into a single `VerifyResult` and computes the overall exit code.

**Why per-target invocation.** Each call is the smallest reproducible unit. A user reproducing a failure runs the same adapter command `verify` would have run, with the same args. The trajectory file is produced where the user can inspect it. There is no batch protocol the adapter has to implement.

#### 9.5.7 Negative-control idiom

A `behavioral_alignment` target whose expectation is "this trajectory matches the golden" is one positive test. Without a paired *negative control*, the test passes vacuously when the adapter ignores the seed entirely (it always produces the same trajectory). Negative control declares one or more alternative seeds the adapter must also run, expecting a *different* outcome.

```yaml
verify_targets:
  - axis: behavioral_alignment
    target: "{loops.combat_turn}"
    seed: 12345
    expect:
      trajectory: { matches_golden: ./tests/golden_seed_12345.jsonl }
    negative_control:
      seeds: [99999]
      expect: { trajectory_diverges_from_primary: true }
```

`gdmd verify` runs the adapter once with the primary seed (writing the trajectory to a temp path, then comparing to the golden) and once per negative-control seed (writing each to its own temp path). It then asserts that every negative-control trajectory **differs byte-for-byte** from the primary trajectory. If a negative-control trajectory equals the primary, the target fails — the adapter is provably not responding to the seed.

The discipline belongs in the spec, not in each adapter: an adapter that doesn't ship a negative control passes vacuously, and the spec has no leverage to require one. Declaring `negative_control:` in the verify_target makes the discipline first-class and engine-neutral.

**Why byte-identity.** Same reason as cross-engine: structural-vs-byte equivalence is exactly the failure mode the trajectory format exists to eliminate. If two seeds produce structurally-equivalent-but-byte-different trajectories, the trajectory serialization is non-canonical — fix that.

---

## 10. JSON Schema

The normative frontmatter schema lives at `schema/game-design.schema.json`. It is the machine-readable companion to §4–§6 and is what editors validate against live.

The schema is a discriminated union over `file_type:` with one variant per file type (`core`, `subfile`, `content-schema`, `content-entity`) sharing common `$defs` for `Status`, `TokenRef`, `Distribution`, `Loop`, `Verb`, `Resource`, `Entity`, `BalanceTarget`, `Feel`, `Invariant`, `StateMachine` (with `StateNode` + `StateTransition`), `VerifyTarget`, and `VerifyResult`.

VS Code's YAML extension picks up the schema via the YAML language server's standard mapping. Add this to a workspace `.vscode/settings.json`:

```json
{
  "yaml.schemas": {
    "./schema/game-design.schema.json": [
      "game-design.md",
      "gdd/**/*.md",
      "content/**/*.yaml"
    ]
  }
}
```

---

## 11. Conformance

A `game-design.md` tree is **conformant at v0.2.0-alpha** if:

1. `gdmd lint <tree>` returns exit code `0` (no findings of severity `error`).
2. The root `game-design.md` has all required frontmatter keys (§5.1) and the canonical prose section order (§5.2).
3. Every subfile has `spec`, `spec_version`, `file_type`, `status`, `last_verified` in its frontmatter.
4. Every `content/*/*.yaml` validates against its referencing content-schema file's `schema:`.
5. Every random outcome resolves to a named `distributions.<id>`.

### 11.1 Success benchmark

The schema is working if, from a cold context, an AI coding agent can implement a correct new content entity (e.g. a new card) from `gdd/content/<kind>.md`'s schema + one representative `*.yaml` example in a single session, ≥80% of the time. The `examples/deckbuilder/` tree is designed to be testable against this benchmark. If success drops below 80%, the schema is over- or under-specified for the type — surface the gap rather than working around it.

---

## Appendix A — Worked Examples

| Tree | Genre | Notes |
| --- | --- | --- |
| `examples/deckbuilder/` | Roguelike deckbuilder | The reference example — most complete; designed for the §11.1 benchmark. |
| `examples/party-rpg/` | Party-based RPG | Multi-actor `verbs:` and richer `entities:`. |
| `examples/tick-combat/` | Auto-battler tick combat | `loops.timescale: moment` is sub-second; distributions dominate. |
| `examples/tcg/` | Trading card game | Two-player, asymmetric, `balance_targets` heavy on win-rate bands. |

## Appendix B — Relationship to `DESIGN.md`

| Aspect | Inherited verbatim | Extended / new |
| --- | --- | --- |
| Two-layer file (YAML + prose) | ✓ | |
| `{namespace.id}` reference syntax | ✓ | depth ≤ 6; refs into `content/*/*.yaml` via `data_source` |
| Canonical `##` order, linter-enforced | ✓ | per-file-type orders (§7.1) |
| Unknown-content handling | ✓ | + `status-regression`, `inline-content-over-threshold` |
| CLI verb set | ✓ | `diff` exit-codes balance regressions |
| Apache-2.0 licensing | ✓ | |
| Modular tree + `files:` map | | **new** (§2.2, §5.1) |
| `status:` + `implemented_in:` + `last_verified:` | | **new** (§8) |
| Seven core namespaces + `feel` + `balance_targets` | | **new** (§4) — the entire surface |
| Named distributions for all randomness | | **new** (§4.7) — strict at v0.1 |
| Content-heavy data pattern (`data_source:`) | | **new** (§6) |
| Architecture invariants, state-machine totality, `verify` adapter contract | | **new** (§4.10, §4.4, §9.5) — adapted from a parallel research effort and re-grounded engine-neutral (the source assumed a web engine; we express codebase properties and a pluggable adapter contract instead). |

## Appendix C — Glossary of Spec Terms

- **Token** — a value in YAML frontmatter. Normative.
- **Namespace** — a top-level key in frontmatter that owns a category of tokens (e.g. `loops`, `verbs`, `distributions`).
- **Reference** — `{namespace.id}` syntax pointing from one token (or prose) to another.
- **Surface** — the seven core namespaces (`entities`, `verbs`, `resources`, `states`, `rules`, `loops`, `distributions`) plus the two cross-cutting namespaces (`feel`, `balance_targets`). The universal probabilistic surface.
- **Primitive** (in a reference) — a scalar resolution (number/string/boolean).
- **Composite** (in a reference) — an object or array resolution.
- **Content-heavy type** — an `entities` kind with `count_target >= 20`, which MUST live in `content/<kind>/*.yaml`.
- **Drift** — divergence between what the doc says and what the code does. The anti-drift mechanisms (§8.2) exist to detect and prevent it.
- **The seven primitives** — `entities`, `verbs`, `resources`, `states`, `rules`, `loops`, `distributions`. Plus `feel` and `balance_targets` as cross-cutting concerns, the universal surface is nine total.
- **Stability guarantee** — `pillars`, `non_goals`, `player_experience_goals`, `core_loop_ref` are the only fields agreed to remain stable for the life of a project.
