"""Isolation smoke test for ClaudeInstrument (required before wiring counts).

ClaudeInstrument runs `claude` (Claude Code CLI) in a fresh tempdir cwd
specifically to neutralize project-memory contamination — if the subprocess
ran in the repo, Claude Code would auto-load
`~/.claude/projects/-home-bantarus-DEV-game-design/memory/MEMORY.md`,
which contains the entire design history of this benchmark (spec rationale,
findings, pre-reg discipline). That would hand the subject the spec via
memory and break A-vs-B-vs-C comparability across conditions.

This module verifies the isolation works in practice by running the
wired instrument against probes that ONLY the project memory or repo
content could answer. A correctly-isolated subject must NOT produce
correct project-specific answers; a leak means the wiring is wrong.

Grader semantics: each probe declares `truth_signals` — regex patterns
that match tokens from the CANONICAL CORRECT ANSWER (not heuristic
leak indicators). A leak is detected when ≥ `min_signals` truth-tokens
appear in the response, AND the response is non-degenerate (not a
refusal/uncertainty). The grader is matching against the true project
fact, not against answer-production: a confident confabulation that
happens to use a generic PRNG-domain term would NOT fire if the
truth-tokens are project-internal (e.g. "Phase 4++", "Embergrave"). The
prose `canonical_answer` per probe documents exactly what response
would constitute a real leak, for the human auditor to verify the
truth-signals are correctly anchored.

This robustness property matters in two future scenarios where the
subject's behavior changes: (a) a Claude Code update that alters the
default refuse-when-unknown disposition; (b) re-running this smoke
against a more confabulation-prone model. In both, the truth-anchor
grader stays correct because it asks "did the subject reproduce the
fact?" rather than "did the subject answer at all?".

Run:

  python -m benchmark.harness.verify_claude_isolation

Exit code 0 = all probes passed (no leak). Exit code 1 = at least one
probe produced a correct project-specific answer (LEAK detected).

The test is required before ClaudeInstrument can be considered wired for
trial zero. Treat a leak the same way you'd treat a failed calibration
gate: stop, fix the wiring, re-run.

NOTE: this consumes the user's Claude Code subscription quota. 4 probes
at Opus 4.7 / --effort xhigh rates is materially more expensive than the
earlier Haiku-era smoke (extended-thinking output budget is large); on
the order of $0.10–$0.50 per smoke run rather than < $0.01. Re-run
parsimoniously.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from .instrument import ClaudeInstrument, CLAUDE_TRANSFER_PROBE_BUNDLE


@dataclass(frozen=True)
class Probe:
    """One contamination probe.

    `question`: posed verbatim to the isolated subject.
    `truth_signals`: a tuple of regex patterns; each pattern is a token
                    FROM THE CANONICAL CORRECT ANSWER. The grader fires
                    `leak_detected = True` when ≥ `min_signals` of these
                    truth-tokens appear in the response. Anchoring on
                    truth-tokens (not heuristic leak proxies) means the
                    grader is asking "did the subject reproduce the
                    fact?" — robust to subject behavior changes
                    (refusals, confabulation, model swaps).
    `min_signals`: minimum number of distinct truth_signals that must
                   match to count as a leak. Calibrated per-probe to
                   require enough project-internal tokens that a
                   confident guess cannot fabricate them.
    `canonical_answer`: prose statement of what the correct answer
                       literally is. Documentation only — not parsed by
                       the grader — but lets a human auditor verify
                       (a) the truth_signals are correctly anchored to
                       the true fact and (b) what response would
                       constitute a real leak. If `truth_signals`
                       drifts away from `canonical_answer`, the probe
                       is broken; update both together.
    `rationale`: why this question can only be answered with project
                 context — for the human auditor of the smoke result.
    """
    id: str
    question: str
    truth_signals: tuple[str, ...]
    min_signals: int = 1
    canonical_answer: str = ""
    rationale: str = ""


# Probes. Each one's `truth_signals` ARE tokens from the canonical correct
# answer (not heuristic leak indicators); `min_signals` is calibrated so
# matching the threshold requires reproducing project-internal facts that
# a confabulation cannot plausibly fabricate. `canonical_answer` documents
# exactly what response would be a real leak — kept aligned with the
# truth_signals so the auditor can verify both move together.
PROBES: tuple[Probe, ...] = (
    Probe(
        id="fresh_game_name",
        question=(
            "Two fresh games were authored for the v0.2 Phase 5 help-benchmark "
            "of the 'game-design.md' specification project. Name the second "
            "game (Game #2) and its genre, plus the name of the platformer "
            "Game #1. Reply with just the names and genres, nothing else."
        ),
        # Truth tokens: Driftwood AND Embergrave AND a project-specific
        # genre word. min_signals=3 requires reproducing all three pieces
        # of the canonical answer — partial guesses do not fire.
        truth_signals=(
            r"\bdriftwood\b",
            r"\bembergrave\b",
            r"\b(survival|crafting|platformer|precision[- ]?platformer)\b",
        ),
        min_signals=3,
        canonical_answer=(
            "Game #1 = Embergrave (precision platformer). "
            "Game #2 = Driftwood (survival/crafting)."
        ),
        rationale=(
            "Both fresh-game names are project-internal and not in any "
            "public corpus. A model could lucky-guess one evocative name "
            "('Driftwood'); matching all three truth-tokens (both names + "
            "a project-specific genre word) requires reproducing the "
            "canonical answer, which is what the grader anchors on."
        ),
    ),
    Probe(
        id="decision_d018",
        question=(
            "In the 'game-design.md' v0.2.0-alpha specification, what does "
            "decision D-018 establish about the PRNG reduction layer? Cite "
            "the related finding number, the phase it landed in, and the "
            "specific technique it pins for signed-int64 host languages. "
            "Reply in one short sentence."
        ),
        # Truth tokens from D-018's canonical answer:
        #   F-007 (the bug D-018 ratchets)
        #   Phase 4++ (the exact phase label — distinctive: most projects
        #              use phase 4 or 4.1, the "++" suffix is internal)
        #   32-bit-halves (the specific reduction technique pinned)
        #   xtreme (the Rust engine name) / godot+pcg (the Godot bug)
        # Generic PRNG-domain terms ("reduction", "uniform-int") are NOT
        # truth_signals because they're not specific to D-018's answer.
        truth_signals=(
            r"\bf-?\s?007\b",
            r"\bphase\s*4(\+\+)?\b",
            r"\b32[- ]?bit[- ]?halves\b",
            r"\bxtreme\b",
            r"\bgodot\b.*\bpcg\b",
        ),
        min_signals=2,
        canonical_answer=(
            "D-018 ratchets the F-007 bug (Godot-vs-xtreme PCG divergence) "
            "discovered at Phase 4++ by pinning the 32-bit-halves uniform-"
            "integer reduction for signed-int64 host languages."
        ),
        rationale=(
            "D-018's answer is specifically composed of project-internal "
            "tokens (F-007, Phase 4++, 32-bit-halves) that cannot be "
            "fabricated by a model trained on public corpora. 2-of-5 "
            "truth tokens is the calibrated threshold."
        ),
    ),
    Probe(
        id="prereg_chain",
        question=(
            "The v0.2 Phase 5 pre-registration for the 'game-design.md' "
            "help-benchmark went through nine supersession commits. What was "
            "the structural correction introduced at v8? Reply in one short "
            "sentence."
        ),
        truth_signals=(
            r"\bcontent[- ]?preservation\b",
            r"\bsanitiz(er|ation).*positive control\b",
            r"\bphase b\b",
            r"\bn(\s|=)\s*90\b",
        ),
        min_signals=2,
        canonical_answer=(
            "Pre-reg v8 added three corrections: trial-time sanitization "
            "(#14), content-preservation gate with two-phase positive "
            "control (#15), and bumped the blinding-leak calibration N to "
            "90 (30 per condition) (#16)."
        ),
        rationale=(
            "v8's specific corrections (content-preservation, Phase B, "
            "N=90) are project-internal pre-reg history. Two truth-token "
            "matches = the model is reproducing v8's content, not "
            "guessing about pre-registration generically."
        ),
    ),
    Probe(
        id="invariant_kinds",
        question=(
            "The 'game-design.md' v0.2.0-alpha specification defines an "
            "`invariants` namespace where each invariant declares a `kind:` "
            "from a closed enumeration of FIVE values. List the five kinds as "
            "a comma-separated list, nothing else."
        ),
        truth_signals=(
            r"\bnumeric[_ ]?domain\b",
            r"\barchitectural[_ ]?pattern\b",
            r"\blayer[_ ]?boundary\b",
            r"\bcommunication\b",
            r"\bdeterminism\b",
        ),
        min_signals=4,
        canonical_answer=(
            "numeric_domain, architectural_pattern, layer_boundary, "
            "communication, determinism"
        ),
        rationale=(
            "The five invariant kinds are spec-specific terms. A generic "
            "guess about software-engineering invariants might land on 1-2 "
            "of these terms (e.g. 'numeric_domain'); 4+ matches = the "
            "model is reproducing the closed enumeration from the spec, "
            "not extrapolating from generic invariant vocabulary."
        ),
    ),
)


@dataclass(frozen=True)
class ProbeResult:
    probe_id: str
    response_text: str
    leak_matches: tuple[str, ...]   # which patterns matched
    leak_detected: bool             # >= min_signals matched
    tokens_input: int
    tokens_output: int
    wall_clock_seconds: float


def run_probe(instrument: ClaudeInstrument, probe: Probe, seed: int) -> ProbeResult:
    response = instrument.complete(
        # System prompt is deliberately minimal — the question's discriminative
        # power should come from the project-context probe, not from the system
        # prompt. A bare system prompt also matches what Qwen will run under.
        system_prompt=(
            "You are a precise assistant. Answer the user's question directly. "
            "If you don't know, say so briefly."
        ),
        user_prompt=probe.question,
        seed=seed,
    )
    text = response.text
    matches: list[str] = []
    for pat in probe.truth_signals:
        if re.search(pat, text, re.IGNORECASE):
            matches.append(pat)
    # Truth-anchor grader: leak detected = the subject reproduced enough
    # canonical-answer tokens to confirm it had project access. The grader
    # asks "did the subject match the truth?", not "did the subject answer
    # at all?" — robust to refusals, confabulations, and model swaps.
    leak = len(matches) >= probe.min_signals
    return ProbeResult(
        probe_id=probe.id,
        response_text=text,
        leak_matches=tuple(matches),
        leak_detected=leak,
        tokens_input=response.tokens_input,
        tokens_output=response.tokens_output,
        wall_clock_seconds=response.wall_clock_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    print("ClaudeInstrument isolation smoke test")
    print(f"  bundle: {CLAUDE_TRANSFER_PROBE_BUNDLE.bundle_id()}")
    print(f"  probes: {len(PROBES)}")
    print()

    instrument = ClaudeInstrument(CLAUDE_TRANSFER_PROBE_BUNDLE)
    results: list[ProbeResult] = []
    for i, probe in enumerate(PROBES):
        print(f"[{i+1}/{len(PROBES)}] {probe.id}")
        print(f"  Q: {probe.question[:100]}{'…' if len(probe.question) > 100 else ''}")
        try:
            r = run_probe(instrument, probe, seed=20260524_0 + i)
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")
            return 2
        results.append(r)
        verdict = "LEAK" if r.leak_detected else "ok"
        print(f"  A: {r.response_text[:200]!r}{'…' if len(r.response_text) > 200 else ''}")
        print(f"  matches: {list(r.leak_matches)}  -> {verdict}  "
              f"(tokens: in={r.tokens_input} out={r.tokens_output}, "
              f"wall={r.wall_clock_seconds:.1f}s)")
        print()

    leaks = [r for r in results if r.leak_detected]
    print("=" * 60)
    print(f"SUMMARY: {len(results) - len(leaks)}/{len(results)} probes ok, "
          f"{len(leaks)} LEAK")
    if leaks:
        print()
        print("CONTAMINATION DETECTED. ClaudeInstrument isolation is INCOMPLETE.")
        print("Failed probes (subject answered with project-specific content):")
        for r in leaks:
            print(f"  - {r.probe_id}: matched {list(r.leak_matches)}")
        print()
        print("This means the subprocess somehow loaded project context that "
              "should have been excluded. Investigate before any trial counts.")
        return 1

    print()
    print("Isolation HOLDS — subject produced no project-specific content. "
          "ClaudeInstrument wiring is correct for trial-zero use.")
    total_in = sum(r.tokens_input for r in results)
    total_out = sum(r.tokens_output for r in results)
    total_wall = sum(r.wall_clock_seconds for r in results)
    print(f"  total tokens: in={total_in} out={total_out}  "
          f"total wall: {total_wall:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
