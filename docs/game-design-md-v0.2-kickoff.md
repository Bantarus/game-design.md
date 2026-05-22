# Claude Code Kickoff Prompt — `game-design.md` v0.2

> Paste into Claude Code at the repo root, after the v0.1.1 work order is complete. Same format as the original kickoff: constraints first, then a staged work order with stop points. This pass shifts from *"is the spec well-formed?"* (answered: yes) to *"does the spec actually drive working game code, in any engine?"* (unanswered).

You are running the v0.2 pass on the `game-design.md` standard. v0.1.1 shipped a complete spec (911 lines, `spec_version: 0.1.1`), a JSON Schema (31 `$defs`), a CLI (`gdmd lint | diff | export | spec | verify`), four lint-clean examples (deckbuilder, tick-combat, party-rpg, tcg), a `DECISIONS.md` (D-001…D-006), and a benchmark harness. Read `docs/spec.md`, `DECISIONS.md`, and `examples/tick-combat/` in full before starting.

## Why this pass exists

Everything green in v0.1.1 proves the spec is *well-formed* and that an agent can author *more spec* (a card) from it. The standard's actual promise — that an AI coding agent builds the **game** from the tree, in any engine — is still unproven. No example has been implemented. `verify` is contract-only with no adapter. "Engine-neutral" is a design intention never demonstrated by instantiating one tree in two engines. v0.2 closes that gap.

## The load-bearing invariant (do not violate)

**The `game-design.md` tree never names an engine, framework, or renderer.** Implementations are *downstream consumers* of the spec, kept entirely outside the spec tree (under `examples/<game>/impl/<engine>/`). The spec's `implemented_in:` pointers point *into* those impl directories; the impl code references the spec, never the reverse. If you ever find yourself adding an engine field to a `gdd/` file, stop — that is the exact failure of the parallel research we rejected.

**The implementation is a stress-test of the spec, not a workaround for it.** When building real code reveals that the spec is ambiguous or under-determined, that is a *finding about the spec* — fix the spec (and log a decision), do not silently paper over the gap in code. The whole point of implementing is to discover where the document fails to fully determine behavior.

## The spine of v0.2

1. Implement **one** example for real — `tick-combat` (Lockstep), because it's deterministic, small, and replay-checkable — in engine A.
2. Ship a **real `verify` adapter** for it. The killer `behavioral_alignment` check writes itself: same seed → byte-identical replay. Promote `verify` from experimental.
3. Implement the **same tree** in engine B (a maximally different paradigm). Prove the tree didn't change, and that both engines produce the same seed→outcome (cross-engine spec-compliance).
4. Run a benchmark that answers *"does the doc help?"* — with-doc vs. without-doc on a real feature task, plus ambiguous briefs that test the prose-as-rationale fallback.

Clear the v0.2-tagged decision debt (D-002, D-003, D-005, D-006) along the way, in the order that serves the spine.

## Work Order (stop for review at each checkpoint)

**Phase 1 — Clear known spec/schema debt (`0.1.1` → `0.2.0-alpha`).** These are already-designed deferrals; do them before implementation because the adapter and the ratchet depend on them.

- **D-003 — typed balance-target vocabulary.** Replace the permissive `target: {}` with a small typed union: `scalar` (a number), `range` (`{ between: [lo, hi] }` / `{ near: x, tolerance: t }`), and `distribution_over_categories` (the `cards_per_rarity: { common, uncommon, rare }` shape, with a composite tolerance). Update the schema, add a `balance-target-untyped` linter finding (warning) for legacy permissive targets, and migrate the four examples' balance blocks.
- **D-005 — events as first-class tokens.** Promote state-machine transition `event:` values to `{events.<id>}` tokens with their own namespace (owned by `mechanics.md`, or a dedicated `events.md` — your call, justify it). This unlocks the deferred `undefined-event` sub-finding under `state-machine-coverage` — implement it now that events are tokens (a transition referencing an undefined event → warning; an event token defined but never used → it joins `orphaned-*` reporting). Migrate the state machines in all four examples.
- **D-006 — packaging.** Move `gdmd spec` and `gdmd export --format schema` path resolution from `Path(__file__).parents[2]` to `importlib.resources` (or hatch shared-data) so a wheel install works, not just the dev install. Add a smoke test that runs against a built wheel.

**→ STOP.** Show me the migrated examples re-linting clean and the new `undefined-event` rule firing on a deliberately-broken fixture.

**Phase 2 — First real implementation (engine A).** Pick engine A (see "Engine choices" below) and implement `tick-combat`/Lockstep in `examples/tick-combat/impl/<engineA>/`. Drive the implementation *from the spec tree* — entities, verbs, the tick loop, the `action_order` deterministic distribution, the state machines. Wire each `gdd/` entity's `implemented_in:` to the real source path and flip those entities `draft → prototyped` (then `→ implemented` as each lands). Do **not** change any `gdd/` file to suit the engine; if the spec is ambiguous, fix the spec and note it.

**→ STOP.** Show me the implementation building, a fixed-seed session running, and the list of any spec ambiguities the implementation surfaced (with how you resolved them in the *spec*).

**Phase 3 — The real `verify` adapter.** Build the project-supplied adapter for engine A: it builds the impl, runs a fixed-seed session, and emits `VerifyResult` JSON per the §9.5 contract. Wire it to the existing `verify_targets`. The headline `behavioral_alignment` target is replay reproducibility (same seed → identical replay hash), which also exercises the Graft A `determinism` invariant end-to-end. Then **promote `verify` from experimental**, and **ratchet D-002** (`broken-implementation-pointer` warning → error) — now meaningful, because real `implemented_in:` paths resolve and a broken one is a genuine defect.

**→ STOP.** Show me `gdmd verify examples/tick-combat` exiting 0 against the real adapter, and the replay-hash check passing.

**Phase 4 — Engine-neutrality, demonstrated not asserted.** Implement the *same* `tick-combat` tree in engine B (maximally different paradigm from A) under `impl/<engineB>/`, with its own adapter. Establish two things: (a) the `game-design.md` tree required **zero** changes to support engine B (diff it — it should be untouched, or the only diff is additional `implemented_in:` paths); (b) both engines, given the same seed, produce the **same** game outcome / replay hash. (b) is a strong cross-engine spec-compliance result: if the spec truly determines behavior, two independent implementations converge.

**→ STOP.** Show me the (empty-or-pointers-only) tree diff between the two implementations and the matching seed→outcome across engines.

**Phase 5 — The benchmark that answers "does it help?"** Three parts, reported honestly (no repeat of the `MEETS at N=5` overstatement):

- **Scale-up:** re-run the §11.1 card benchmark at **N ≥ 20** and report the rate with its confidence interval. Rewrite §11.1's conformance language so the claim matches the statistics.
- **Ambiguity probe:** add 2–3 deliberately under-specified briefs (e.g., "design a card that synergizes with the bellow mechanic" — no numbers). This is the real test of the spec's core principle that *prose rationale is the fallback when no token covers a case*. Score whether the agent's design choices are *defensible given the prose*, not just schema-valid.
- **With-doc vs. without-doc:** on one real feature-add task against the engine-A implementation, compare an agent given the `game-design.md` tree against an agent given a one-paragraph prompt. This directly addresses the ETH/LogicStar finding from the original research that context files can *reduce* success — measure that the doc helps rather than merely exists.

**→ STOP.** Final review: defensible benchmark numbers, updated §11.1, and a short `docs/v0.2-findings.md` summarizing what implementing the spec taught us about the spec.

## Engine choices (your call, justify it)

Engines A and B should be **maximally different paradigms** so the neutrality proof means something, and both must be **headless-runnable** so the adapter can drive them. Reasonable defaults from your stack: **Rust + Bevy ECS** (compiled, data-oriented) for A and **TypeScript** (interpreted, headless sim or canvas) for B — or Rust + Python. Pick, state why, and keep both implementations small; this is a proof, not a product.

## Loose ends to fold in (low effort)

- **TCG / `pity_floor`:** optional swap — booster packs are the textbook `pity_floor` case, slightly cleaner than party-RPG dungeon loot. Do it only if you're touching the TCG example anyway; not worth a dedicated cycle.
- **`docs/benchmark/`:** move to a CI artifact rather than committing trial outputs permanently.
- **Composite-target `verify`:** once D-003 lands, the `verify` `behavioral_alignment` axis can finally check `distribution_over_categories` balance targets — make sure at least one `verify_target` exercises that.

## Ground rules (unchanged from v0.1)

Use `web_fetch` on the real `DESIGN.md` repo if a convention question arises. Diagnose rule-vs-example (and now spec-vs-implementation) before editing either. Log every decision in `DECISIONS.md`. Commit in small reviewable units. Present ambiguous design calls as 2–3 options rather than guessing. The spec is upstream of every implementation — guard its neutrality.

Begin with Phase 1.
