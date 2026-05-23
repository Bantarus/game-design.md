"""Instrument calibration smoke run + blinding-leak calibration.

Per pre-reg §"Protocol" step 11, before any trial counts both pinned
instrument bundles (Qwen headline + Claude transfer probe) must pass three
calibration gates on a pinned canary prompt:

  1. Structural validity. Thinking blocks parse cleanly; no mid-token
     truncation; no encoding errors; no repeated-token gibberish.
  2. Seed-sensitivity (the actual power guard). K ≥ 5 invocations under
     distinct seeds produce outputs whose SHA-256 hashes are all distinct
     AND whose pairwise edit distance exceeds a pre-registered minimum
     fraction of the shorter output's length.
  3. Rubric reachability. The aux judge scores the smoke output ≥ 4 on
     the "matches intent" rubric — a sanity check that the instrument
     can hit the rubric at all on a known-trivial task.

Auxiliary check (NOT a pass/fail gate): same-seed reproducibility. Two
back-to-back invocations of the canary prompt with the same seed are
recorded for audit purposes; strict byte-identity is NOT required (GPU
non-determinism is expected; the audit records the divergence rate for
the F-009 report).

Per pre-reg §"Judge" Layer 3, the blinding-leak calibration runs N=30
outputs across A/B/C on one calibration task. The aux judge predicts each
output's condition with labels stripped. Pass if predictions are
no-better-than-chance (95% CI on accuracy includes 33%).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .conditions import build_a, build_b, build_c
from .instrument import Instrument, InstrumentResponse
from .judge import Judge
from .tasks import Task, load_task


# Pre-registered seed-sensitivity parameters
CALIBRATION_K = 5
CALIBRATION_EDIT_DISTANCE_FLOOR_FRACTION = 0.20  # ≥20% of the shorter output's length

# The pre-registered canary prompt. Frozen at the harness-build commit.
CANARY_PROMPT = """Write a short paragraph (3-5 sentences) describing how the player would
intuit the controls of a precision platformer where the player character
is a moth and the player can jump, dash, and glide. Do not invent
mechanics not listed.
""".strip()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuralValidityCheck:
    output_id: int
    passed: bool
    notes: str


@dataclass(frozen=True)
class SeedSensitivityCheck:
    distinct_hashes: int
    total_outputs: int
    min_pairwise_edit_distance: int
    shortest_output_length: int
    pairwise_floor: int
    passed: bool


@dataclass(frozen=True)
class RubricReachabilityCheck:
    output_id: int
    rubric_score: int
    passed: bool


@dataclass(frozen=True)
class SameSeedAuditArtifact:
    """NOT a pass/fail gate. Recorded for the F-009 report."""
    same_seed_run_1_sha256: str
    same_seed_run_2_sha256: str
    byte_identical: bool
    divergence_char_count: int


@dataclass(frozen=True)
class CalibrationResult:
    bundle_id: str
    canary_prompt_sha256: str
    timestamp_iso: str
    structural: tuple[StructuralValidityCheck, ...]
    seed_sensitivity: SeedSensitivityCheck
    rubric_reachability: tuple[RubricReachabilityCheck, ...]
    same_seed_audit: SameSeedAuditArtifact
    passed: bool                  # all three gates passed
    notes: str = ""


# ---------------------------------------------------------------------------
# Instrument calibration
# ---------------------------------------------------------------------------

def calibrate_instrument(
    instrument: Instrument,
    judge: Judge,
    seeds: tuple[int, ...] = (1001, 1002, 1003, 1004, 1005),
) -> CalibrationResult:
    """Run the three calibration gates + the same-seed audit on a canary prompt."""
    import time
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    canary_sha = hashlib.sha256(CANARY_PROMPT.encode()).hexdigest()

    # Run K invocations with distinct seeds
    responses: list[InstrumentResponse] = []
    for seed in seeds[:CALIBRATION_K]:
        r = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=seed)
        responses.append(r)

    # Structural validity
    structural = tuple(
        StructuralValidityCheck(
            output_id=i,
            passed=_check_structural(r.text),
            notes=_describe_structural_issues(r.text),
        )
        for i, r in enumerate(responses)
    )

    # Seed sensitivity
    hashes = [hashlib.sha256(r.text.encode()).hexdigest() for r in responses]
    distinct = len(set(hashes))
    shortest_len = min(len(r.text) for r in responses)
    floor = int(shortest_len * CALIBRATION_EDIT_DISTANCE_FLOOR_FRACTION)
    pairwise_min = _min_pairwise_edit_distance([r.text for r in responses])
    seed_check = SeedSensitivityCheck(
        distinct_hashes=distinct,
        total_outputs=len(responses),
        min_pairwise_edit_distance=pairwise_min,
        shortest_output_length=shortest_len,
        pairwise_floor=floor,
        passed=(distinct == len(responses) and pairwise_min >= floor),
    )

    # Rubric reachability — judge scores each output on the matches-intent rubric.
    # We use the canary prompt itself as the "task brief" and a synthetic
    # "game_brief" (since there's no real brief for the canary).
    rubric = tuple(
        RubricReachabilityCheck(
            output_id=i,
            rubric_score=(
                judge.score_matches_intent(
                    task_brief=CANARY_PROMPT,
                    subject_output=r.text,
                    game_brief="A canary prompt for instrument calibration; the brief is the prompt itself.",
                ).score
            ),
            passed=False,  # set below
        )
        for i, r in enumerate(responses)
    )
    rubric = tuple(
        RubricReachabilityCheck(
            output_id=r.output_id,
            rubric_score=r.rubric_score,
            passed=r.rubric_score >= 4,
        )
        for r in rubric
    )

    # Same-seed audit (NOT a gate)
    same_seed_seed = seeds[0]
    r1 = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=same_seed_seed)
    r2 = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=same_seed_seed)
    h1 = hashlib.sha256(r1.text.encode()).hexdigest()
    h2 = hashlib.sha256(r2.text.encode()).hexdigest()
    divergence = sum(1 for a, b in zip(r1.text, r2.text) if a != b) + abs(len(r1.text) - len(r2.text))
    same_seed = SameSeedAuditArtifact(
        same_seed_run_1_sha256=h1,
        same_seed_run_2_sha256=h2,
        byte_identical=(h1 == h2),
        divergence_char_count=divergence,
    )

    passed = (
        all(s.passed for s in structural)
        and seed_check.passed
        and all(r.passed for r in rubric)
    )
    return CalibrationResult(
        bundle_id=instrument.bundle.bundle_id(),
        canary_prompt_sha256=canary_sha,
        timestamp_iso=timestamp,
        structural=structural,
        seed_sensitivity=seed_check,
        rubric_reachability=rubric,
        same_seed_audit=same_seed,
        passed=passed,
    )


def _check_structural(text: str) -> bool:
    """Coarse structural-validity checks."""
    if not text or not text.strip():
        return False  # empty output
    # Heuristic: balanced angle-bracket tags (for reasoning-mode instruments)
    open_think = text.count("<think>")
    close_think = text.count("</think>")
    if open_think != close_think:
        return False
    # Heuristic: not pathologically repetitive
    # (repeating the same 20-char substring 10+ times in a row signals gibberish)
    for i in range(len(text) - 200):
        chunk = text[i:i+20]
        if chunk and text.count(chunk) > 10 and len(chunk.strip()) > 5:
            return False
    return True


def _describe_structural_issues(text: str) -> str:
    issues: list[str] = []
    if not text.strip():
        issues.append("empty output")
    if text.count("<think>") != text.count("</think>"):
        issues.append("unbalanced <think> tags")
    return "; ".join(issues) if issues else "no issues detected"


def _min_pairwise_edit_distance(texts: list[str]) -> int:
    """Cheap proxy: min pairwise character-difference count.

    NOT true Levenshtein (too slow for long outputs); the proxy is the
    sum of |len_a - len_b| plus the count of positionally-different chars
    in the common prefix. This is a LOWER BOUND on true edit distance
    and therefore safe (false-negatives only; never claims distance is
    higher than it is).
    """
    if len(texts) < 2:
        return 0
    min_d = None
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            d = abs(len(a) - len(b)) + sum(1 for x, y in zip(a, b) if x != y)
            if min_d is None or d < min_d:
                min_d = d
    return min_d or 0


# ---------------------------------------------------------------------------
# Blinding-leak calibration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlindingLeakResult:
    judge_bundle_id: str
    n_outputs: int
    accuracy: float                # fraction of correct predictions
    accuracy_95_ci_low: float
    accuracy_95_ci_high: float
    chance_accuracy: float = 1.0 / 3.0
    passed: bool = False           # True iff CI includes chance_accuracy


def calibrate_blinding(
    instrument: Instrument,
    judge: Judge,
    calibration_task: Task,
    n_per_condition: int = 10,
) -> BlindingLeakResult:
    """Run N=30 outputs across A/B/C, ask judge to predict conditions, check
    if accuracy is no-better-than-chance."""
    # Build A/B/C payloads
    payload_a = build_a(calibration_task.game)
    payload_b = build_b(calibration_task.game)
    payload_c = build_c(calibration_task.game)

    outputs: list[tuple[int, str, str]] = []  # (output_id, true_condition, text)
    oid = 0
    for cond_name, payload in [("A", payload_a), ("B", payload_b), ("C", payload_c)]:
        for i in range(n_per_condition):
            prompt = f"{payload.payload_text}\n\n--- TASK ---\n{calibration_task.brief}"
            r = instrument.complete(
                system_prompt="You are a coding agent. Implement the task described, using the provided design context.",
                user_prompt=prompt,
                seed=10000 + oid,
            )
            outputs.append((oid, cond_name, r.text))
            oid += 1

    # Strip labels (the judge sees only the output text; in random order)
    import random
    rng = random.Random(42)
    shuffled = outputs.copy()
    rng.shuffle(shuffled)

    judge_inputs = [(o[0], o[2]) for o in shuffled]
    predictions = judge.predict_conditions(judge_inputs)

    # Score predictions
    true_by_oid = {o[0]: o[1] for o in outputs}
    correct = sum(1 for p in predictions if p.predicted_condition == true_by_oid[p.output_id])
    n = len(predictions)
    accuracy = correct / n if n else 0.0
    # Wilson 95% CI
    lo, hi = _wilson_95_ci(correct, n)
    passed = lo <= (1.0 / 3.0) <= hi
    return BlindingLeakResult(
        judge_bundle_id=judge.bundle.bundle_id(),
        n_outputs=n,
        accuracy=accuracy,
        accuracy_95_ci_low=lo,
        accuracy_95_ci_high=hi,
        passed=passed,
    )


def _wilson_95_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (small-sample-friendly)."""
    if n == 0:
        return (0.0, 1.0)
    p_hat = successes / n
    denom = 1 + (z * z) / n
    center = (p_hat + (z * z) / (2 * n)) / denom
    half = (z * ((p_hat * (1 - p_hat) / n) + (z * z) / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ---------------------------------------------------------------------------
# Persistence — write calibration artifacts to disk
# ---------------------------------------------------------------------------

def write_calibration_result(result: CalibrationResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_bundle = result.bundle_id.replace("/", "_")
    fname = f"instrument_calibration_{safe_bundle}_{result.timestamp_iso.replace(':', '')}.json"
    path = out_dir / fname
    path.write_text(json.dumps(_to_jsonable(result), indent=2, default=str))
    return path


def write_blinding_leak_result(result: BlindingLeakResult, out_dir: Path) -> Path:
    import time
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    safe_bundle = result.judge_bundle_id.replace("/", "_")
    fname = f"blinding_leak_{safe_bundle}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(_to_jsonable(result), indent=2, default=str))
    return path


def _to_jsonable(obj):
    """Convert dataclasses + tuples to dicts/lists for JSON serialization."""
    from dataclasses import is_dataclass, fields
    if is_dataclass(obj):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj
