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

Run:

  python -m benchmark.harness.verify_claude_isolation

Exit code 0 = all probes passed (no leak). Exit code 1 = at least one
probe produced a correct project-specific answer (LEAK detected).

The test is required before ClaudeInstrument can be considered wired for
trial zero. Treat a leak the same way you'd treat a failed calibration
gate: stop, fix the wiring, re-run.

NOTE: this consumes the user's Claude Code subscription quota. 4 probes
at Haiku rates is negligible (< 1 cent total at typical pricing).
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
    `leak_signals`: a list of regex patterns; if ANY match the response
                    (case-insensitive), the probe FAILED — the subject
                    answered with project-specific content it should not
                    have had access to.
    `min_signals`: minimum number of distinct leak_signals that must match
                   to count as a leak. Default 1. Use a higher value for
                   probes whose answer is a list (so a partial guess
                   doesn't false-positive).
    `rationale`: why this question can only be answered with project
                 context — for the human auditor of the smoke result.
    """
    id: str
    question: str
    leak_signals: tuple[str, ...]
    min_signals: int = 1
    rationale: str = ""


# Probes. Each one's correct answer exists ONLY in the project's memory or
# repo content; the answer is specific enough that a hallucination is
# unlikely to match the leak signals.
PROBES: tuple[Probe, ...] = (
    Probe(
        id="fresh_game_name",
        question=(
            "Two fresh games were authored for the v0.2 Phase 5 help-benchmark "
            "of the 'game-design.md' specification project. Name the second "
            "game (Game #2) and its genre, plus the name of the platformer "
            "Game #1. Reply with just the names and genres, nothing else."
        ),
        # Require Driftwood AND Embergrave (the platformer fresh game) AND a
        # genre word. A lucky guess of one survival-game name is plausible
        # ('Driftwood' is evocative); guessing the platformer's specific name
        # too is essentially impossible without project access. min_signals=3
        # requires real leakage to trigger.
        leak_signals=(
            r"\bdriftwood\b",
            r"\bembergrave\b",
            r"\b(survival|crafting|platformer|precision[- ]?platformer)\b",
        ),
        min_signals=3,
        rationale=(
            "'Driftwood' (survival/crafting) and 'Embergrave' (precision "
            "platformer) are the fresh-game names authored for this project. "
            "A model could lucky-guess one name; matching all three signals "
            "(both game names AND a project-specific genre word) requires "
            "actual project access."
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
        # Project-specific tokens that a guess cannot fabricate:
        #   F-007 (the bug D-018 ratchets)
        #   Phase 4++ (the exact phase label)
        #   32-bit-halves (the specific reduction technique)
        # A generic guess uses 'reduction' / 'uniform-int' — those are NOT
        # leak signals here (too plausible). Require 2 of these specific
        # terms; trip only on actual access.
        leak_signals=(
            r"\bf-?\s?007\b",
            r"\bphase\s*4(\+\+)?\b",
            r"\b32[- ]?bit[- ]?halves\b",
            r"\bxtreme\b",
            r"\bgodot\b.*\bpcg\b",
        ),
        min_signals=2,
        rationale=(
            "D-018 ratchets the F-007 bug at Phase 4++ with the 32-bit-halves "
            "reduction for signed-int64 hosts. These specific tokens (F-007, "
            "Phase 4++, 32-bit-halves) exist only in this project. Generic "
            "PRNG-domain terms (uniform-int, reduction) are NOT leak signals "
            "because a model can guess them; project-specific tokens are the "
            "leak signature."
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
        leak_signals=(
            r"\bcontent[- ]?preservation\b",
            r"\bsanitiz(er|ation).*positive control\b",
            r"\bphase b\b",
            r"\bn(\s|=)\s*90\b",
        ),
        min_signals=2,
        rationale=(
            "v8's three corrections (trial-time sanitization #14, content-"
            "preservation gate #15, blinding-leak N=30->90 #16) are "
            "project-internal pre-reg history. Two or more of the specific "
            "terms = clear leak from project memory."
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
        leak_signals=(
            r"\bnumeric[_ ]?domain\b",
            r"\barchitectural[_ ]?pattern\b",
            r"\blayer[_ ]?boundary\b",
            r"\bcommunication\b",
            r"\bdeterminism\b",
        ),
        min_signals=4,
        rationale=(
            "The five invariant kinds (numeric_domain, architectural_pattern, "
            "layer_boundary, communication, determinism) are spec-specific. "
            "A generic guess might land on 1-2 of these terms; 4+ matches "
            "indicates the spec content is accessible."
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
    for pat in probe.leak_signals:
        if re.search(pat, text, re.IGNORECASE):
            matches.append(pat)
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
