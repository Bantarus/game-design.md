"""Instrument calibration smoke run + blinding-leak calibration.

Per pre-reg §"Protocol" step 11 (v10 supersession of step-11 wording),
before any trial counts both pinned instrument bundles (Qwen headline +
Claude transfer probe) must pass three calibration gates on a pinned
canary prompt:

  1. Structural validity. Thinking blocks parse cleanly; no mid-token
     truncation; no encoding errors; no repeated-token gibberish.
  2. Seed-sensitivity (the actual power guard). K ≥ 5 invocations under
     distinct seeds produce outputs whose SHA-256 hashes are all distinct
     AND whose pairwise edit distance exceeds a pre-registered minimum
     fraction of the shorter output's length.
  3. Rubric reachability — AGGREGATE (v10). The auxiliary judge scores
     each of the K outputs on the matches-intent rubric. PASS iff the
     median score is ≥ 4 AND the min score is ≥ 1. The median captures
     "the instrument can hit the rubric at all on a known-trivial task"
     (pre-reg WHY); the min captures the "0/5 = instrument broken at
     the output layer" failure mode literally. Per-output ≥ 4 was the
     pre-v10 implementation; it was internally contradictory with the
     seed-sensitivity gate above — seed-sensitivity REQUIRES stochastic
     variation across draws, per-output ≥ 4 FORBIDS any variation below
     4. See v10 supersession in docs/v0.2-phase5-pre-registration.md
     for the gate-correction reasoning + the canary change that
     accompanies it.

Auxiliary check (NOT a pass/fail gate, v9 wording — but v10 records
an upgrade): same-seed reproducibility. Two back-to-back invocations
of the canary with the same seed are recorded; strict byte-identity
was NOT required by the v9 pre-reg (GPU non-determinism is expected).
v10 observation: at QWEN_HEADLINE_BUNDLE's pinned stochastic sampling
(temperature=0.7), Qwen + same seed + fixed build IS byte-identical
on the same hardware — a stronger auditability property than the v9
pre-reg's "recorded, not gated" stance assumed. Recorded as the
better-than-expected artifact it is.

Per pre-reg §"Judge" Layer 3 (v8 — was v7), the blinding-leak calibration
runs N=90 outputs across A/B/C (30 per condition) on one calibration task,
then evaluates the judge in TWO PHASES. N was bumped from 30 → 90 at v8
because at N=30 the Wilson CI is wide enough that "includes 1/3" only
rules out a *large* leak (a small residual leak at, say, 45% passes
because the CI spans both 33% and 45%). At N=90 the half-width tightens
to ~0.10, catching ~10pp-or-larger leaks. Blinding-leak calibration is
just the judge predicting condition on stored outputs (no instrument
generation per evaluation phase), so the larger N is nearly free.

Per pre-reg §"Judge" Layer 3c (v9), an additional **sanitizer-generalization
check** is run on REAL trial outputs (not calibration anchors). The
blinding-leak gate above validates the sanitizer on the 90-output
calibration sample; the sanitizer is applied to the ~660-trial population,
which the calibration never saw. A pre-sweep small-batch check (after
instrument calibration but before the full sweep) catches sanitizer leaks
on the trial population early; a post-hoc full-sweep sample check is
recorded alongside F-009. See `check_blinding_generalization` below and
project memory `train-test-distribution-shift-sanitizer` for the standing
rule.

  Phase 1 (positive control / judge fitness): judge predicts conditions
  on RAW outputs (no sanitization). PASS iff above chance with
  statistical significance — lower bound of 95% Wilson CI exceeds 1/3.
  This proves the judge is a fair adversary that CAN detect tells.

  Phase 2 (blinding-leak gate proper): same judge predicts conditions
  on SANITIZED outputs (sanitization function pinned in
  `benchmark/harness/sanitization.py`). PASS iff at chance —
  95% Wilson CI on accuracy INCLUDES 1/3. This proves sanitization
  REMOVED the tells.

Overall pass requires BOTH phases. A Phase-1 fail invalidates the JUDGE
(too weak — re-pin); a Phase-2 fail invalidates the SANITIZATION
(strengthen sanitizer + re-run Phase 2 only). Pre-reg v7 added the
positive control to close a false-pass-from-weak-judge hole in the v6
gate. See memory `calibration-positive-control` for the general rule.
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
#
# v10 supersession: replaced the v9-era "moth precision platformer
# controls" prose prompt with a small fixed CODING task. Rationale: the
# headline instrument (Qwen3-Coder-30B-A3B-Instruct) is code-specialized
# and the trial workload is entirely code/spec implementation. A prose
# canary tested an off-axis capability — it could confirm the output
# layer wasn't broken (the gate's stated purpose) but told us little
# about coding-trial readiness, the property the smoke is actually
# proxy for.
#
# Canary-shape requirement (discovered post-first-revision): the task
# must elicit ~100+ line outputs with multiple legitimate implementation
# choices, so the seed-sensitivity gate's 20%-of-shortest threshold —
# calibrated for trial-sized outputs — is reachable. A trivial
# single-function canary (e.g. `chunk(lst, n)`) converges to one
# canonical implementation under stochastic sampling, leaving variance
# only in trailing prose explanation; the gate then fails not because
# the instrument is broken but because the canary is too narrow. The
# CSV-summary script below forces a multi-stage implementation (read /
# filter / group / aggregate / sort / write) with multiple natural
# library-usage patterns (csv.reader vs csv.DictReader; pre-read vs
# stream; manual aggregation vs collections.defaultdict / Counter /
# itertools.groupby), producing trial-shaped outputs that exercise the
# 20% variance floor honestly.
CANARY_PROMPT = """Write a complete Python script that:

1. Reads a CSV file at the path 'data.csv' with columns 'name',
   'score', and 'team'.
2. Filters to rows where the score is at least 80.
3. Groups the remaining rows by team and computes, for each team,
   the member count and the average score.
4. Writes a summary CSV at the path 'summary.csv' with columns
   'team', 'member_count', and 'avg_score', sorted alphabetically
   by team.

Constraints: use only the Python standard library. Show the full
runnable script including imports and an `if __name__ == "__main__":`
guard.
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
    """Per-output rubric score. Diagnostic only — the gate is the aggregate
    below (v10 supersession). Per-output ≥4 was internally contradictory
    with the seed-sensitivity gate: seed-sensitivity REQUIRES stochastic
    variation across draws; per-output ≥4 FORBIDS any of that variation
    from dipping below 4. The pre-reg's stated failure mode for this
    gate is `0/5` ("instrument broken at the output layer"), which the
    aggregate captures via `min_score >= 1`."""
    output_id: int
    rubric_score: int


@dataclass(frozen=True)
class RubricReachabilityAggregate:
    """Aggregate gate per pre-reg v10 supersession.

    Adopted because per-output ≥4 was a gate-internal contradiction with
    the seed-sensitivity gate, and the pre-reg's stated failure mode
    ("0/5 = instrument broken at the output layer") is an aggregate
    statement about the *output layer*, not a per-draw quality bound.

    PASS iff:
      - median(rubric_scores) >= median_threshold (default 4) — the
        instrument can hit the rubric on a majority of draws (the
        "can hit the rubric at all" the pre-reg's WHY names).
      - min(rubric_scores) >= min_threshold (default 1) — no draw was
        catastrophically zero (the 0/5 failure mode the pre-reg names
        literally).

    Both thresholds chosen pre-result-aware: median ≥ 4 matches the
    pre-reg's quoted "≥ 4 on the matches intent rubric"; min ≥ 1
    matches the "0/5 here would mean the instrument is broken"
    failure-mode language literally. They aren't reverse-engineered to
    a specific instrument's numbers — an instrument scoring
    [3, 3, 4, 3, 3] (median 3) still fails the corrected gate, so the
    bar still has teeth."""
    median_score: float
    min_score: int
    n_outputs: int
    median_threshold: int = 4
    min_threshold: int = 1
    passed: bool = False


@dataclass(frozen=True)
class SameSeedAuditArtifact:
    """NOT a pass/fail gate. Recorded for the F-009 report."""
    same_seed_run_1_sha256: str
    same_seed_run_2_sha256: str
    byte_identical: bool
    divergence_char_count: int


@dataclass(frozen=True)
class CanaryGather:
    """All instrument outputs needed for the calibration gates.

    Gathered with the instrument up; passed to a separate scoring step
    once the instrument is torn down (the Qwen+Gemma sequential-load
    pattern — they cannot coexist in 24 GB VRAM)."""
    bundle_id: str
    seeds: tuple[int, ...]
    distinct_seed_responses: tuple[InstrumentResponse, ...]
    same_seed_run_1: InstrumentResponse
    same_seed_run_2: InstrumentResponse


@dataclass(frozen=True)
class CalibrationResult:
    bundle_id: str
    canary_prompt_sha256: str
    timestamp_iso: str
    structural: tuple[StructuralValidityCheck, ...]
    seed_sensitivity: SeedSensitivityCheck
    rubric_reachability: tuple[RubricReachabilityCheck, ...]
    rubric_aggregate: RubricReachabilityAggregate
    same_seed_audit: SameSeedAuditArtifact
    passed: bool                  # all three gates passed
    notes: str = ""


# ---------------------------------------------------------------------------
# Instrument calibration — split into gather (instrument up) and compute
# (judge up). The two-stage shape lets the driver swap llama-server
# processes between the Qwen instrument and the Gemma judge, which is
# required because Qwen Q4_K_M (18.6 GB) + Gemma UD-Q4_K_M (16.9 GB) do
# not coexist in 24 GB VRAM. Claude does not need a llama-server, so the
# `calibrate_instrument` one-shot path remains valid for Claude+Gemma.
# ---------------------------------------------------------------------------

def gather_canary_responses(
    instrument: Instrument,
    seeds: tuple[int, ...] = (1001, 1002, 1003, 1004, 1005),
) -> CanaryGather:
    """Run K distinct-seed invocations + 2 same-seed invocations on the canary.

    Call with the instrument's llama-server (if any) already loaded.
    The returned CanaryGather is enough to compute every gate downstream
    — the instrument can then be torn down before the judge runs."""
    distinct: list[InstrumentResponse] = []
    for seed in seeds[:CALIBRATION_K]:
        r = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=seed)
        distinct.append(r)
    same_seed_seed = seeds[0]
    r1 = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=same_seed_seed)
    r2 = instrument.complete(system_prompt="", user_prompt=CANARY_PROMPT, seed=same_seed_seed)
    return CanaryGather(
        bundle_id=instrument.bundle.bundle_id(),
        seeds=tuple(seeds[:CALIBRATION_K]),
        distinct_seed_responses=tuple(distinct),
        same_seed_run_1=r1,
        same_seed_run_2=r2,
    )


def score_canary_with_judge(
    gather: CanaryGather,
    judge: Judge,
) -> tuple[RubricReachabilityCheck, ...]:
    """Rubric-reachability: judge scores each distinct-seed response.

    Call with the judge's llama-server (if any) already loaded. The
    instrument's responses were captured by `gather_canary_responses`
    and stored on `gather`; the instrument process may be torn down.

    Returns per-output scores only — the aggregate gate (median/min)
    is computed by `compute_calibration_result` per v10 supersession."""
    return tuple(
        RubricReachabilityCheck(
            output_id=i,
            rubric_score=(
                judge.score_matches_intent(
                    task_brief=CANARY_PROMPT,
                    subject_output=r.text,
                    game_brief="A canary prompt for instrument calibration; the brief is the prompt itself.",
                ).score
            ),
        )
        for i, r in enumerate(gather.distinct_seed_responses)
    )


def compute_calibration_result(
    gather: CanaryGather,
    rubric_scores: tuple[RubricReachabilityCheck, ...],
    timestamp_iso: str | None = None,
) -> CalibrationResult:
    """Compute the three gates + same-seed audit from a gather + rubric scores."""
    import statistics
    import time
    timestamp = timestamp_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    canary_sha = hashlib.sha256(CANARY_PROMPT.encode()).hexdigest()

    responses = list(gather.distinct_seed_responses)

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

    # Rubric reachability — aggregate gate per v10 supersession.
    # Per-output ≥4 was internally contradictory with seed-sensitivity
    # (which requires stochastic variation across draws); the aggregate
    # captures the pre-reg's WHY ("can hit the rubric at all" + "0/5 =
    # broken output layer") without forbidding the variation upstream
    # gates require.
    scores = [r.rubric_score for r in rubric_scores]
    median_s = statistics.median(scores) if scores else 0
    min_s = min(scores) if scores else 0
    rubric_aggregate = RubricReachabilityAggregate(
        median_score=median_s,
        min_score=min_s,
        n_outputs=len(scores),
        median_threshold=4,
        min_threshold=1,
        passed=(median_s >= 4 and min_s >= 1),
    )

    # Same-seed audit (NOT a gate) — from the gather
    h1 = hashlib.sha256(gather.same_seed_run_1.text.encode()).hexdigest()
    h2 = hashlib.sha256(gather.same_seed_run_2.text.encode()).hexdigest()
    divergence = (
        sum(1 for a, b in zip(gather.same_seed_run_1.text, gather.same_seed_run_2.text) if a != b)
        + abs(len(gather.same_seed_run_1.text) - len(gather.same_seed_run_2.text))
    )
    same_seed = SameSeedAuditArtifact(
        same_seed_run_1_sha256=h1,
        same_seed_run_2_sha256=h2,
        byte_identical=(h1 == h2),
        divergence_char_count=divergence,
    )

    passed = (
        all(s.passed for s in structural)
        and seed_check.passed
        and rubric_aggregate.passed
    )
    return CalibrationResult(
        bundle_id=gather.bundle_id,
        canary_prompt_sha256=canary_sha,
        timestamp_iso=timestamp,
        structural=structural,
        seed_sensitivity=seed_check,
        rubric_reachability=rubric_scores,
        rubric_aggregate=rubric_aggregate,
        same_seed_audit=same_seed,
        passed=passed,
    )


def calibrate_instrument(
    instrument: Instrument,
    judge: Judge,
    seeds: tuple[int, ...] = (1001, 1002, 1003, 1004, 1005),
) -> CalibrationResult:
    """One-shot calibration — valid when instrument + judge can coexist.

    For Claude+Gemma this works directly (Claude does not consume GPU).
    For Qwen+Gemma the driver must sequence (gather → tear down Qwen →
    bring up Gemma → score → compute), because the two GGUFs do not
    fit together in 24 GB VRAM.
    """
    gather = gather_canary_responses(instrument, seeds)
    rubric_unscored = score_canary_with_judge(gather, judge)
    return compute_calibration_result(gather, rubric_unscored)


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
class BlindingPhaseResult:
    """Result of one phase of the blinding-leak calibration (raw or sanitized)."""
    phase: str                     # "positive_control" | "blinding_gate"
    n_outputs: int
    accuracy: float                # fraction of correct predictions
    accuracy_95_ci_low: float
    accuracy_95_ci_high: float
    chance_accuracy: float = 1.0 / 3.0
    passed: bool = False           # phase-specific pass criterion


@dataclass(frozen=True)
class BlindingLeakResult:
    """Combined two-phase result (v7).

    overall_passed iff BOTH:
      - positive_control.passed (judge above chance on raw outputs)
      - blinding_gate.passed     (judge at chance on sanitized outputs)
    """
    judge_bundle_id: str
    sanitization_sha256: str       # SHA of harness/sanitization.py
    positive_control: BlindingPhaseResult
    blinding_gate: BlindingPhaseResult
    overall_passed: bool


@dataclass(frozen=True)
class BlindingOutputs:
    """Instrument-generated outputs for blinding-leak calibration.

    Gathered with the instrument up; passed to score_blinding once the
    instrument is torn down (the Qwen+Gemma sequential-load pattern —
    they cannot coexist in 24 GB VRAM). Stores the (oid, true_condition,
    raw_text) tuples so both phases can re-evaluate the same outputs."""
    instrument_bundle_id: str
    task_game: str
    task_cell_id: str
    n_per_condition: int
    schedule_seed: int
    outputs: tuple[tuple[int, str, str], ...]   # (oid, true_condition, raw_text)

    def to_json(self) -> dict:
        return {
            "instrument_bundle_id": self.instrument_bundle_id,
            "task_game": self.task_game,
            "task_cell_id": self.task_cell_id,
            "n_per_condition": self.n_per_condition,
            "schedule_seed": self.schedule_seed,
            "outputs": [
                {"oid": oid, "true_condition": cond, "raw_text": text}
                for (oid, cond, text) in self.outputs
            ],
        }

    @classmethod
    def from_json(cls, data: dict) -> "BlindingOutputs":
        return cls(
            instrument_bundle_id=data["instrument_bundle_id"],
            task_game=data["task_game"],
            task_cell_id=data["task_cell_id"],
            n_per_condition=int(data["n_per_condition"]),
            schedule_seed=int(data["schedule_seed"]),
            outputs=tuple(
                (int(o["oid"]), str(o["true_condition"]), str(o["raw_text"]))
                for o in data["outputs"]
            ),
        )


def write_blinding_outputs(outputs: BlindingOutputs, out_dir: Path) -> Path:
    """Persist a gather to disk so a Gemma-side failure doesn't lose the
    instrument generation work. Replay via `BlindingOutputs.from_json`."""
    import time
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    safe_bundle = outputs.instrument_bundle_id.replace("/", "_")
    fname = f"blinding_outputs_{safe_bundle}_{outputs.task_cell_id}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(outputs.to_json(), indent=2))
    return path


def read_blinding_outputs(path: Path) -> BlindingOutputs:
    return BlindingOutputs.from_json(json.loads(path.read_text()))


def gather_blinding_outputs(
    instrument: Instrument,
    calibration_task: Task,
    n_per_condition: int = 30,  # v8: bumped from 10 → 30 (total N=90)
    schedule_seed: int = 20260524,
) -> BlindingOutputs:
    """Generate the K-per-condition outputs in pairing-integrity order.

    Call with the instrument's llama-server (if any) already loaded.
    The returned BlindingOutputs is everything the judge needs; the
    instrument can be torn down before score_blinding runs.

    Generation order: interleaved across conditions, not blocked. The
    same pairing-integrity discipline that protects the trial sweep
    (see harness/sweep_plan.py) applies here at smaller N: if all A
    samples are generated first and all C samples last, a time-correlated
    nuisance (Claude rate-limit posture, Qwen drift) lands on one
    condition more than the others. The judge's at-chance gate would
    then INCORRECTLY flag time artifacts as content-leak signals.
    Schedule is shuffled with `schedule_seed` for determinism."""
    payload_a = build_a(calibration_task.game)
    payload_b = build_b(calibration_task.game)
    payload_c = build_c(calibration_task.game)

    schedule: list[tuple[str, "ConditionPayload"]] = []  # noqa: F821
    for cond_name, payload in [("A", payload_a), ("B", payload_b), ("C", payload_c)]:
        for _ in range(n_per_condition):
            schedule.append((cond_name, payload))
    import random as _random_for_schedule
    schedule_rng = _random_for_schedule.Random(schedule_seed)
    schedule_rng.shuffle(schedule)

    outputs: list[tuple[int, str, str]] = []  # (output_id, true_condition, raw_text)
    for oid, (cond_name, payload) in enumerate(schedule):
        prompt = f"{payload.payload_text}\n\n--- TASK ---\n{calibration_task.brief}"
        r = instrument.complete(
            system_prompt="You are a coding agent. Implement the task described, using the provided design context.",
            user_prompt=prompt,
            seed=10000 + oid,
        )
        outputs.append((oid, cond_name, r.text))

    return BlindingOutputs(
        instrument_bundle_id=instrument.bundle.bundle_id(),
        task_game=calibration_task.game,
        task_cell_id=calibration_task.cell_id,
        n_per_condition=n_per_condition,
        schedule_seed=schedule_seed,
        outputs=tuple(outputs),
    )


def score_blinding(
    blinding_outputs: BlindingOutputs,
    judge: Judge,
    shuffle_seed: int = 42,
) -> BlindingLeakResult:
    """Two-phase blinding-leak scoring (Phase 1 raw, Phase 2 sanitized).

    Call with the judge's llama-server (if any) already loaded. The
    instrument-generated outputs were captured by gather_blinding_outputs
    and stored on `blinding_outputs`; the instrument process may be
    torn down."""
    from .sanitization import sanitize_output, sanitization_sha256
    import random

    chance = 1.0 / 3.0
    outputs = list(blinding_outputs.outputs)
    n = len(outputs)
    true_by_oid = {o[0]: o[1] for o in outputs}

    # --- Phase 1: positive control on RAW outputs ----------------------------
    rng = random.Random(shuffle_seed)
    shuffled_raw = outputs.copy()
    rng.shuffle(shuffled_raw)
    raw_inputs = [(o[0], o[2]) for o in shuffled_raw]
    raw_predictions = judge.predict_conditions(raw_inputs)

    correct_raw = sum(1 for p in raw_predictions if p.predicted_condition == true_by_oid[p.output_id])
    acc_raw = correct_raw / n if n else 0.0
    lo_raw, hi_raw = _wilson_95_ci(correct_raw, n)
    pc_passed = lo_raw > chance  # strict above-chance
    positive_control = BlindingPhaseResult(
        phase="positive_control",
        n_outputs=n,
        accuracy=acc_raw,
        accuracy_95_ci_low=lo_raw,
        accuracy_95_ci_high=hi_raw,
        passed=pc_passed,
    )

    # --- Phase 2: blinding gate on SANITIZED outputs -------------------------
    # Same RNG seed so the shuffle order is identical (controls for ordering
    # confounds between the two phases).
    rng2 = random.Random(shuffle_seed)
    sanitized_outputs = [(oid, cond, sanitize_output(text)) for (oid, cond, text) in outputs]
    shuffled_san = sanitized_outputs.copy()
    rng2.shuffle(shuffled_san)
    san_inputs = [(o[0], o[2]) for o in shuffled_san]
    san_predictions = judge.predict_conditions(san_inputs)

    correct_san = sum(1 for p in san_predictions if p.predicted_condition == true_by_oid[p.output_id])
    acc_san = correct_san / n if n else 0.0
    lo_san, hi_san = _wilson_95_ci(correct_san, n)
    bg_passed = lo_san <= chance <= hi_san  # CI includes chance
    blinding_gate = BlindingPhaseResult(
        phase="blinding_gate",
        n_outputs=n,
        accuracy=acc_san,
        accuracy_95_ci_low=lo_san,
        accuracy_95_ci_high=hi_san,
        passed=bg_passed,
    )

    return BlindingLeakResult(
        judge_bundle_id=judge.bundle.bundle_id(),
        sanitization_sha256=sanitization_sha256(),
        positive_control=positive_control,
        blinding_gate=blinding_gate,
        overall_passed=(positive_control.passed and blinding_gate.passed),
    )


def calibrate_blinding(
    instrument: Instrument,
    judge: Judge,
    calibration_task: Task,
    n_per_condition: int = 30,
) -> BlindingLeakResult:
    """One-shot calibrate — valid when instrument + judge can coexist.

    For Qwen+Gemma the driver MUST sequence (gather → tear down Qwen →
    bring up Gemma → score), because the two GGUFs do not fit together
    in 24 GB VRAM. Call gather_blinding_outputs + score_blinding
    directly in that case (see benchmark/tools/run_step6_calibrations.py).
    """
    outputs = gather_blinding_outputs(instrument, calibration_task, n_per_condition)
    return score_blinding(outputs, judge)


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
# Sanitizer-generalization check (v9) — Phase-2-equivalent on REAL trial outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeneralizationCheckResult:
    """Result of running the Phase-2 at-chance check on REAL trial outputs.

    Distinct from BlindingPhaseResult because the input is real trial outputs
    (not calibration anchors), and the result is recorded as evidence that
    the sanitizer generalized from calibration sample to trial population
    (or failed to generalize). Pass criterion identical to Phase 2.
    """
    label: str                         # "pre_sweep" | "post_hoc" | freeform
    judge_bundle_id: str
    sanitization_sha256: str
    n_outputs: int
    accuracy: float                    # fraction of correct predictions
    accuracy_95_ci_low: float
    accuracy_95_ci_high: float
    chance_accuracy: float = 1.0 / 3.0
    passed: bool = False               # CI includes 1/3
    notes: str = ""


def check_blinding_generalization(
    judge: Judge,
    trial_outputs: list[tuple[int, str, str]],
    label: str = "pre_sweep",
    rng_seed: int = 42,
) -> GeneralizationCheckResult:
    """Run the Phase-2 at-chance check on REAL trial outputs (post-sanitization).

    Per pre-reg v9 §"Judge" Layer 3c. Use this in two places:

      (a) Pre-sweep (label="pre_sweep"). After instrument calibration
          (§"Protocol" step 11) and before the full trial sweep
          (§"Protocol" step 12), generate a small batch of real trials
          (a handful per condition per game; typically N=12-30 total) and
          run this check on them. Catches sanitizer leaks on the trial
          population that the calibration sample never saw. Failure at
          pre-sweep means the sanitizer needs strengthening BEFORE
          committing to the ~9-hour full sweep. The Wilson CI is wide
          at small N (it's an early-warning flag, not a statistical
          guarantee), but a clearly above-chance accuracy here is a
          strong signal of generalization failure.

      (b) Post-hoc (label="post_hoc"). On a sample of the full sweep
          (typically N=60-120, drawn uniformly across conditions × games
          × tasks), recorded alongside F-009. The CI tightens; provides
          real statistical power on the question "did the sanitizer
          generalize to the trial population we actually ran?"

    Input contract (trial_outputs): list of `(trial_id, true_condition, raw_text)`
    tuples. `true_condition` is one of "A" | "B" | "C". `raw_text` is the
    instrument's raw response.text — this function applies sanitization
    internally so the same SHA-locked transform Phase 2 validated is what
    gets evaluated.

    Pass criterion: 95% Wilson CI on judge accuracy INCLUDES 1/3. Identical
    to Phase 2 of calibrate_blinding. The sanitization SHA is recorded so a
    Phase-2 fail (calibration) and a generalization-check fail can be
    cross-attributed to the same or different sanitizer versions.

    Failure modes:
      - Pre-sweep fail → sanitizer leaks on the trial population. Strengthen
        sanitizer in a pre-reg cycle (re-runs Phase 2 of calibrate_blinding
        + Phase B of calibrate_content_preservation + this check at
        pre-sweep). Do NOT proceed to the full trial sweep.
      - Post-hoc fail (small leak detected only at the larger-N post-hoc) →
        recorded with F-009 as a stated limitation: "blinding-leak
        generalization passed at pre-sweep N=X with CI [...,...] but
        failed at post-hoc N=Y with CI [...,...]." F-009 reports the
        observed leak magnitude alongside the headline.
    """
    import random
    from .sanitization import sanitize_output, sanitization_sha256

    chance = 1.0 / 3.0

    # Shuffle so the prediction order doesn't reveal the source order.
    rng = random.Random(rng_seed)
    shuffled = list(trial_outputs)
    rng.shuffle(shuffled)

    # Sanitize and pass to the judge.
    sanitized_inputs = [
        (oid, sanitize_output(text))
        for (oid, _true_cond, text) in shuffled
    ]
    predictions = judge.predict_conditions(sanitized_inputs)

    true_by_oid = {oid: cond for (oid, cond, _text) in shuffled}
    correct = sum(
        1 for p in predictions
        if p.predicted_condition == true_by_oid[p.output_id]
    )
    n = len(predictions)
    acc = correct / n if n else 0.0
    lo, hi = _wilson_95_ci(correct, n)
    passed = lo <= chance <= hi

    notes_parts = []
    if not passed:
        if lo > chance:
            notes_parts.append(
                f"sanitizer LEAKS on trial population: judge accuracy "
                f"{acc:.3f} above chance with 95% CI lower bound {lo:.3f} > 1/3"
            )
        elif hi < chance:
            notes_parts.append(
                f"judge predicts BELOW chance (CI upper {hi:.3f} < 1/3); "
                "anti-correlation suggests judge is inverted or sanitizer "
                "introduced anti-tells"
            )

    return GeneralizationCheckResult(
        label=label,
        judge_bundle_id=judge.bundle.bundle_id(),
        sanitization_sha256=sanitization_sha256(),
        n_outputs=n,
        accuracy=acc,
        accuracy_95_ci_low=lo,
        accuracy_95_ci_high=hi,
        passed=passed,
        notes="; ".join(notes_parts),
    )


def load_trial_records_for_generalization_check(
    trials_dir: Path,
) -> list[tuple[int, str, str]]:
    """Load trial records and convert to the (oid, condition, raw_text) tuples
    that `check_blinding_generalization` expects.

    Reads every `*.json` file in `trials_dir`; each is a serialized
    `TrialRecord` (see `run_trial.py`). Uses the file's `subject_output`
    (the RAW form — generalization check sanitizes internally) and the
    record's `condition` field. The `oid` is the integer index into the
    sorted file list (deterministic across calls).

    The caller is responsible for selecting which records to include
    (a small pre-sweep batch — typically the first ~20 trials run; or a
    uniform-sample from the full sweep for post-hoc).
    """
    paths = sorted(trials_dir.glob("*.json"))
    out: list[tuple[int, str, str]] = []
    for i, p in enumerate(paths):
        rec = json.loads(p.read_text())
        cond = rec.get("condition")
        raw = rec.get("subject_output")
        if cond and raw:
            out.append((i, cond, raw))
    return out


def write_generalization_check_result(
    result: GeneralizationCheckResult,
    out_dir: Path,
) -> Path:
    import time
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    safe_bundle = result.judge_bundle_id.replace("/", "_")
    fname = f"generalization_check_{result.label}_{safe_bundle}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(_to_jsonable(result), indent=2, default=str))
    return path


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
