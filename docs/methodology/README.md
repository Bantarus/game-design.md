# Methodology

> A framework for operating a long-lived specification/standard project where claims must be made carefully, gates must be honest, and a coherent audit trail must survive across many sessions of distributed agents and humans. Extracted from the `game-design.md` project's v0.1.1 → v0.3 development arc; intended to be transferable beyond it.

This document is a framing layer. It points to the artifacts that carry the methodology operationally and names the disciplines they instantiate. It is not a complete framework — it is *the framework as observed so far*, ratcheted by what each phase of the project surfaced. The same closed-vocabulary-grows-by-observed-use discipline that governs the spec's vocabulary governs this methodology framework too: the disciplines listed below are the ones the project's history justified naming, not a speculative complete list.

## What this methodology is for

The `game-design.md` project is a specification, not a product. The deliverable is the standard itself plus tooling to validate trees against it. The project's success criterion is whether the standard *holds up* — across genres, engines, agents, and time — without drifting into engine-specific or genre-specific assumptions and without claiming validation it does not have.

That posture imposes specific discipline requirements:

1. **Claims must be precisely scoped.** "The spec is engine-neutral" is unfalsifiable as stated; "the spec is engine-neutral as demonstrated by two reference implementations in maximally different paradigms producing byte-identical trajectory at the same seed" is testable, and what the project tracks against. Imprecise claims drift into vacuous validation. Every claim should be paired with a refutation condition that names what would falsify it.

2. **Gates must be honest.** When a measurement gate returns a result the project did not want, the disciplined response is not to move the gate. It is to report what the gate measured and decide whether the gate was operationalized against the right question. Three legitimate forms of bar movement are distinguished from gerrymandering below.

3. **The audit trail must survive across sessions.** A long-lived project that involves AI agents implies many sessions, possibly across many models and humans. Decisions must be reconstructible after the fact. Every load-bearing scope reduction, every supersession of a pre-registration, every reframe of a stated bar must be recorded in a way that a future reader can trace.

4. **Vocabulary grows by observed need, not anticipation.** Closed enums extend when real cases surface the need; they do not extend speculatively. This applies to the spec's own vocabulary (entity types, lifecycle states, clock modes), to operational vocabularies (the agent template's prohibitions), and to the methodology's vocabulary (the disciplines listed below). Reflexive application is a signature of load-bearing discipline.

## The three sister disciplines for legitimate bar movement

When a stated validation gate moves, the move is legitimate exactly when it survives the diagnostic test for one of three causes. This is the core methodological framework v0.3 surfaced; each instance is grounded in a concrete moment in project history.

### 1. Result-driven gate widening (the *suspect* form — counterfactual-adoption test)

**Cause shape.** A measurement gate returns a result the project did not want, and there is post-hoc reasoning available to argue the gate should have been wider all along.

**Diagnostic test (counterfactual-adoption).** "If the result had been on the other side of the original gate, would you have adopted this new gate-shape?" If yes, the new gate-shape is principled; the original gate happened to be too narrow and the result correctly surfaced that. If no, the new gate-shape is gerrymandered to the result and the move is gate-loosening rather than gate-correction.

**Working example.** During Phase 5 pre-registration v9, a content-general sanitizer-generalization check was added that explicitly raised the bar for blinding. The test passed because the v9 check would have been adopted regardless of result direction — the project wanted to know whether the sanitizer generalized to the trial population either way. (See pre-reg commit `b9c3ecb`.) Contrast with the suspect form: silently relaxing the blinding bar when the post-hoc check fails would not have survived counterfactual-adoption.

**Recorded as:** operational memory + commit lineage. Not yet promoted to DECISIONS.md.

### 2. Constraint-driven scope reduction (the *legitimate-by-necessity* form)

**Cause shape.** A pre-committed logistical or feasibility rule fires AS DESIGNED on the working gate. The gate hasn't changed; the operationalization scope has reduced because the apparatus can't carry what the original gate called for.

**Diagnostic test (constraint-genuine + re-scoping-honest).**
- *Constraint-genuine:* the constraint that triggered the reduction was pre-committed at apparatus-design time, not invented post-hoc to justify reducing scope.
- *Re-scoping-honest:* the reduced scope carries the original ambition forward AS A NAMED LIMITATION, not silently swapped for weaker evidence. The deferred component is archived (not deleted) for future re-activation under the same design.

**Working example.** Phase 5 v12-D scope reduction (pre-reg commit `2b5d9a6`). The original pre-reg called for an Opus transfer probe alongside the Qwen-Coder headline. Mid-execution it became clear the Opus probe could not be run on the available apparatus within the trial window. The disciplined response: reduce scope to single-subject Qwen-Coder execution; archive the Opus probe code + supporting modules under `archived/` with a re-activation README; preserve deterministic identifiers (`seed_base`, bundle SHAs) as RESERVED comments; explicitly name the deferred component as a limitation in the F-009 reporting. Re-activation would run the original design unchanged.

**Recorded as:** operational memory + pre-reg commit + F-009 case study (named limitation).

### 3. Premise-correction reframe (the *premise-was-wrong* form)

**Cause shape.** The bar was set against a factual claim about project state that turns out to be false. The bar simply cannot be operationalized as written because the world it referenced doesn't exist.

**Diagnostic test (premise-genuine + re-scoping-honest + audit-lineage-preserved).**
- *Premise-genuine:* the factual correction is objectively verifiable. The premise was false at the time the bar was set; the correction is not a convenient reading.
- *Re-scoping-honest:* the restatement carries the original ambition forward as a named, future-resolvable limitation, not silently weakened to fit available evidence.
- *Audit-lineage-preserved:* the premise correction is recorded in a place future readers can trace from the original bar through the corrected bar.

**Working example.** v0.3 deployment-surface reframe (DECISIONS.md D-021, spec.md §11.2). The v0.3 kickoff set "at least one live project" as the validation bar, assuming named external projects had spec trees the v0.3 vocabulary would be deployed into. Mid-development the assumption was clarified as false — the named projects don't have spec trees. The bar was set against a factual premise that wasn't true. v0.3 reframed under the corrected premise: three claims validated from in-repo evidence (vocabulary closure, cross-engine determinism preserved, session-level maintenance), one claim queued for v0.4+ pending live adoption (longitudinal living-doc property). The longitudinal claim is *queued*, not silently dropped; the lineage from the kickoff's bar through the corrected bar is reconstructible from D-021's text + spec §11.2's text.

**Recorded as:** [DECISIONS.md D-021](../../DECISIONS.md), spec.md §11.2, operational memory.

### The diagnostic question to ask first

When a stated bar moves, the first question is *which cause shape applies*. All three causes are legitimate; gerrymandering is not a fourth cause shape but the absence of any of the three. The disciplines are protective in both directions: they license legitimate movement and they refuse illegitimate movement under cover of legitimate-sounding language.

## The supersession-chain pattern

For any pre-registered measurement (a benchmark, a calibration, a validation gate) the apparatus is usually wrong on the first pass. Each pass discovers a class of failure mode the prior pass had implicitly assumed away. The disciplined response is to supersede the pre-registration in a commit that names the gap explicitly and to lock the corrected pre-reg before the next trial fires.

The v0.2 Phase 5 supersession chain ran from v1 (`f76f4c2`) through v14-D (`f05bf0d`) over sixteen commits before trial zero ran. Each version's commit message named the discovered gap; each correction was a strictly principled fix (closed-enum extension or apparatus correction, never a result-driven loosening). The chain terminated when no more principled fixes remained — *not* when the gate passed.

Two stopping disciplines are observed:

- **The terminal condition is principled-fixes-exhausted, not gate-PASS.** A supersession chain that stopped at the first gate-PASS would be biased toward whichever pre-reg happened to pass; a chain that stops when no more diagnostic-driven fixes are available terminates at the apparatus state the project judges good-faith-ready, regardless of what trial zero will report.
- **The pre-reg locks at trial zero.** Once trials begin, no further supersessions are permitted. The locked rule reports whatever the data says. F-009 reported NULL on success-lift and FAIL on cost-lift; both were reported by the rule.

The supersession chain is the audit trail. Future readers should be able to reconstruct exactly why each apparatus correction landed where it did. The chain is not noise; it is the methodological work-in-progress made visible.

## Closed-vocabulary-grows-by-observed-use

The spec's seven core namespaces + cross-cutting + architecture namespaces are closed enums. Adding to them is a spec-level event with discipline:

- A new vocabulary item lands when real cases surface the need — typically when two or more independent trees exhibit the same friction that the current vocabulary cannot express cleanly.
- A new vocabulary item does NOT land speculatively. F-010's `{clocks.<id>}` namespace closed at two modes (`continuous`, `per_verb_delta`) — the modes the project's three real cases (tick-combat, Embergrave, Driftwood) demonstrably needed — and *did not* preemptively add a `scheduled` mode that anticipation might suggest.
- The new vocabulary item is *named for observable shape engines already have*, not *imposed as shape engines must conform to*. F-008's `instance_container` named the shape xtreme's ECS already carried; the verify-adapter PASS after the v0.3 retro-touch was unsurprising because the new vocab described existing impl reality.

The principle applies reflexively:

- To **the spec's own vocabulary** (F-008's `instance_container`, F-010's `clocks`, D-019's addressing DSL, D-020's lifecycle states).
- To **the agent template's prohibitions** ([`AGENTS.md`](../../AGENTS.md) three-mode lens: each forbidden action grounded in a concrete commit citation, not anticipated edges).
- To **the per-genre starter content** ([`templates/starters/`](../../templates/starters/): each starter inherits v0.3 vocabulary where its canonical source demonstrated the closure, not where its genre "should theoretically have" it).
- To **this methodology framework** (the disciplines named above are the ones the project's history justified naming; the next discipline lands when real cases surface the need).

Reflexive application is the strongest signal a discipline is load-bearing rather than performative. A discipline that applies to its own artifacts is a discipline that holds when no one is looking.

## The three operating modes (instantiated in AGENTS.md)

The day-to-day work of operating a long-lived spec project decomposes into three activities, each with its own prohibitions. The modes are *activity-driven*, not time-driven — they interleave throughout a session. Recognizing which mode is current is what lets the matching discipline apply.

- **Authoring** — designing or extending the vocabulary. Forbidden: adding genre-specific tokens to the core spec, preempting vocabulary growth, inventing new syntax when existing vocab + a normative semantics declaration closes the gap, calibrating defaults against the population they validate, quietly dropping validation claims.
- **Operating** — implementing the design (CLI, lint rules, example trees, cross-engine adapters). Forbidden: committing with broken refs, committing through a broken verify-adapter on a tree that has one, polluting `examples/<game>/` to drive lint coverage, shipping vocabulary without retro-touching every tree that exhibits the friction it closes, fabricating values.
- **Maintenance** — pre-commit, status hygiene, audit lineage. Forbidden: committing without a sanity sweep, shipping a new lint rule without a proof-of-fire on shaped-like-real content, committing with a what-only message, deferring memory writes.

The full instantiation lives in [`AGENTS.md`](../../AGENTS.md). The probe survey that produced the lens (10/12 adversarial temptations caught at authoring time, 2 documented as legitimate template edges) is recorded in commit `a88d490`.

## The artifacts that carry the methodology

This methodology is implemented across several public artifacts. None of them is the methodology in isolation; the methodology is the *coherence between them*.

| Artifact | Role |
|---|---|
| [`docs/spec.md`](../spec.md) | The specification itself. §11.2 carries the v0.3 validation surface and the three-sister-disciplines triangulation. |
| [`schema/game-design.schema.json`](../../schema/game-design.schema.json) | The JSON Schema. Editors validate against it; the linter consumes it. |
| [`DECISIONS.md`](../../DECISIONS.md) | Decisions-of-record running ledger. Every load-bearing scope decision, vocabulary closure, ratchet promotion, and bar reframe is recorded here with the discipline that produced it. |
| [`AGENTS.md`](../../AGENTS.md) | The three-mode operating lens. Agent companion that names mode-signal + forbidden-actions + CLI per mode. |
| [`CHANGELOG.md`](../../CHANGELOG.md) | Keep-a-Changelog log of what landed when. Audit trail at the release-grain. |
| [`docs/case-studies/F-009.md`](../case-studies/F-009.md) | Worked example: a measurement gate returning null, reported by the locked rule, with the reframe that followed. |
| [`docs/release-notes/v0.3.md`](../release-notes/v0.3.md) | Release narrative carrying the three-claim validation surface, the queued-for-v0.4 list, the reframe lineage. |
| [`docs/v0.2-findings.md`](../v0.2-findings.md) | The v0.2 findings list (F-001 → F-010), the demonstrations-not-checkmarks discipline applied. |
| Operational memories (private) | Per-discipline records carried across sessions by the agent operating the project. Not published; the disciplines themselves are surfaced into the public artifacts above when they rise to the level of decision-of-record. |

The artifacts compose so that a future reader can reconstruct any decision: read the CHANGELOG entry for what landed, follow it to the DECISIONS.md entry for why, follow that to the spec text for the normative consequence, follow that to the case study for the worked example, follow that to the AGENTS.md mode lens for the operational instantiation. The methodology is the path from any one of these to any other.

## What this methodology does NOT yet have

In the spirit of the disciplines this document names, the methodology framework's own limitations are made explicit:

- **No cross-project transfer evidence.** The framework was developed across one project. Whether the disciplines transfer to a different project, a different domain, or a different agent family is an empirical question awaiting cases. The discipline names suggest they would; the evidence does not yet exist.
- **No cross-agent transfer evidence.** All operational work was performed by Claude Code instances. Whether the three-mode operating lens carries to other agents (or to humans operating without agent assistance) is the open Phase-4+ question for the methodology itself.
- **The 12-probe adversarial survey of AGENTS.md was authored by the agent it audits.** Two of the 12 probes were documented as legitimate template edges, not defects. Whether an independent auditor would have made the same call is a v0.4+ question.
- **No falsification of the framework as a whole.** The framework's individual disciplines have falsifications named (each "diagnostic test" above is a refutation condition). The framework qua framework — does this composition of disciplines actually produce healthy long-lived spec projects — is the multi-year question only longitudinal evidence can answer.

These gaps are honest scope statements, not the framework's eventual answers. They are what live use would feed back into v0.4+ if and when it lands.

## How to use this methodology

If you are operating a similar project (a long-lived specification with an AI-agent primary consumer; a maintenance ritual that depends on humans-or-agents staying coordinated across sessions; a validation strategy that has to remain honest in the face of measurement results), the suggested starting points:

1. **Read [`docs/case-studies/F-009.md`](../case-studies/F-009.md) first** — it is the most concrete instance of the framework operating end-to-end on a real result. Understanding the F-009 reframe is the fastest way to grok what "gate correction not gate loosening" means in practice.
2. **Read [`docs/spec.md`](../spec.md) §11.2 next** — the triangulation of the three sister disciplines lives there, with worked references back to where each one fired in project history.
3. **Read [`AGENTS.md`](../../AGENTS.md)** for the three-mode operating lens. Each prohibition is grounded in a concrete commit; trace the commits to see the failure mode the prohibition was authored to prevent.
4. **Read [`DECISIONS.md`](../../DECISIONS.md) front-to-back** if you want the running ledger of every scope decision and vocabulary closure the project made. The reading order is chronological; the discipline that produced each decision is named in-line.

Borrow disciplines à la carte. The framework is not a complete methodology and does not claim to be — it is *the framework as observed so far*, and your project's history will likely justify naming disciplines this one has not yet surfaced. The closed-vocabulary-grows-by-observed-use principle applies to your borrowing too: a discipline that solves a real problem your project surfaced will hold; a discipline borrowed because it sounds good will not.

## Status

Demonstrated 2026-05-29 at v0.3 release. The three sister disciplines, the supersession-chain pattern, the closed-vocabulary-grows-by-observed-use principle, and the three-mode operating lens are the disciplines v0.1.1 → v0.3 surfaced. The transferability questions named under "What this methodology does NOT yet have" are queued for v0.4+, gated on the same observed-need principle the spec vocabulary is gated on.

**Reported by the rule, whatever the numbers say** — the methodology's own slogan, F-009's pre-reg lead-in, holds for the methodology framework itself.
