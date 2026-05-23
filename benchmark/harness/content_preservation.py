"""Content-preservation calibration — the sanitizer's positive control (v8).

Per pre-reg v8 §"Judge" Layer 3 step 4: the blinding-leak gate pressures the
sanitizer in exactly one direction — more aggressive stripping makes Phase 2
(judge at chance) easier to pass. There is no counterweight in the v7 gate,
so an over-aggressive sanitizer that reduces every output to mush passes
Phase 2 (the judge is genuinely blind because there is nothing to read) while
having destroyed the functional content the matches-intent judge needs. All
three conditions then score uniformly low, the A-vs-B difference washes out,
and the benchmark detects nothing — a power loss masquerading as a passed
gate.

This module is the symmetric guard. The sanitizer's positive control validates
that a known-correct output still scores high *after* sanitization, and a
known-incorrect output still scores low *after* sanitization. Tells-removed
(Phase 2 of blinding-leak) AND content-preserved (this gate) — both required
before trial zero.

Two phases:

  Phase A — anchor sanity check (on RAW anchors).
    The matches-intent judge scores K known-correct and K known-incorrect
    pre-authored anchors per (game, calibration task) on the raw (un-sanitized)
    form. PASS iff median(correct) ≥ ANCHOR_SANITY_CORRECT_FLOOR AND
    median(incorrect) ≤ ANCHOR_SANITY_INCORRECT_CEILING AND
    gap = median(correct) − median(incorrect) ≥ ANCHOR_SANITY_GAP_FLOOR.
    This validates the anchors were authored discriminably enough that any
    failure of Phase B is attributable to the sanitizer, not to indistinct
    anchors. A Phase-A fail means the anchors must be re-authored.

  Phase B — content-preservation gate (on SANITIZED anchors).
    Same judge scores the same anchors after sanitization. PASS iff
    median(sanitized_correct) ≥ CONTENT_PRESERVATION_CORRECT_FLOOR AND
    gap = median(sanitized_correct) − median(sanitized_incorrect) ≥
    CONTENT_PRESERVATION_GAP_FLOOR. The gap floor is lower than Phase A's
    (sanitization is allowed to compress the dynamic range somewhat) but the
    correct-floor still requires sanitized-correct anchors to score as decent
    in absolute terms. A Phase-B fail means the sanitizer is destroying
    content; tune it down in a new pre-reg cycle.

The anchors are committed in this file as Python constants. Their SHA-256 is
recorded with each calibration artifact (alongside the sanitization SHA), so
a reviewer of a failed gate can pinpoint which artifact was scored against
which sanitizer. Changing the anchor set requires a pre-reg supersession per
§"Pre-registration commit".

Anchor authoring discipline:
  - K=3 correct + K=3 incorrect per (game, calibration task).
  - Correct anchors span A/B/C styles (YAML-with-refs, prose, inline) so the
    gap is about CONTENT recognition, not style recognition. If only A-style
    anchors were correct and B-style anchors were incorrect, the judge could
    appear to discriminate content while actually reading style — and that
    apparent discrimination would collapse under sanitization for the wrong
    reason.
  - Incorrect anchors fail on different dimensions: off-topic, hand-waving,
    wrong-on-specifics. A single failure mode would over-fit the gate.

See pre-reg v7 → v8 audit-trail row #14 for the rationale, and project memory
`sanitizer-content-preservation` for the general "every sanitization-style
gate needs a content-preservation counterweight" rule.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .judge import Judge
from .sanitization import sanitize_output, sanitization_sha256


# Pre-registered thresholds (v8). Changes require a pre-reg cycle.
ANCHOR_SANITY_CORRECT_FLOOR = 4.0      # median(correct, raw)    >= 4 / 5
ANCHOR_SANITY_INCORRECT_CEILING = 2.0  # median(incorrect, raw)  <= 2 / 5
ANCHOR_SANITY_GAP_FLOOR = 3.0          # raw gap                 >= 3 / 5

CONTENT_PRESERVATION_CORRECT_FLOOR = 3.0  # median(correct, sanitized) >= 3 / 5
CONTENT_PRESERVATION_GAP_FLOOR = 2.0      # sanitized gap              >= 2 / 5


# ---------------------------------------------------------------------------
# Pre-registered anchor texts (v8).
#
# Each entry under CONTENT_PRESERVATION_ANCHORS keys (game, task_cell_id) to
# K=3 correct + K=3 incorrect anchor outputs. Anchors are authored to span
# A/B/C styles on the correct side and span failure modes (off-topic /
# hand-waving / wrong-on-specifics) on the incorrect side.
# ---------------------------------------------------------------------------

PLATFORMER_EASY_CORRECT_A_STYLE = """Here is the level file conforming to `{content.levels}` schema.

<<< FILE: content/levels/fault_lines_07_the_chasm.yaml >>>
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: fault_lines_07_the_chasm
status: draft
implemented_in: ["src/levels/fault_lines/07.py"]
region: fault_lines
tier: 3
entry: {x: 12, y: 96}
exit:  {x: 18, y: 8}
platforms:
  - {id: p1, x: 14, y: 88, width: 8, height: 1}
  - {id: p2, x: 8,  y: 76, width: 6, height: 1, kind: ledge}
  - {id: p3, x: 22, y: 64, width: 10, height: 1}
  - {id: p4, x: 6,  y: 50, width: 4, height: 1, kind: ledge}
  - {id: p5, x: 16, y: 36, width: 8, height: 1}
  - {id: p6, x: 14, y: 18, width: 6, height: 1}
checkpoints:
  - {id: cp1, x: 24, y: 64}
  - {id: cp2, x: 8,  y: 36}
ember_pickups:
  - {id: e1, x: 10, y: 86, value: 2}
  - {id: e2, x: 24, y: 62, value: 2}
  - {id: e3, x: 6,  y: 48, value: 2}
  - {id: e4, x: 16, y: 16, value: 2}
hazards:
  - {kind: void, region: {x: 0, y: 0, width: 32, height: 6}}
<<< END FILE: content/levels/fault_lines_07_the_chasm.yaml >>>

Per the spec, the entry is at y=96 and the exit at y=8 — descending; the
void at y<6 makes a fall past the exit lethal. Six platforms alternate
side-of-shaft for descent rhythm. Two checkpoints land on the natural
descent path (after p3 and after p5). Four ember pickups at value 2 each
total 8 ember per the brief.
"""


PLATFORMER_EASY_CORRECT_PROSE_STYLE = """A new level for the fault_lines region, level id fault_lines_07_the_chasm.
The brief calls for a vertical descent: the player enters at the top of a
shaft and exits at the bottom, with a lethal void below the exit so
falling past it is fatal.

Layout: entry at world coordinate (12, 96), exit at (18, 8) — entry is
far above the exit, so the level naturally descends. Six platforms span
the shaft at decreasing heights: a wide platform at y=88, a narrow ledge
at y=76 on the left, a wide platform at y=64 on the right, a narrow ledge
at y=50 on the left, a wide platform at y=36 in the center, and a final
platform at y=18 leading to the exit. The alternating wide/narrow shape
gives the descent a natural rhythm.

Two checkpoints sit on the descent path — one at (24, 64) on the third
platform, another at (8, 36) on the fifth — both placed mid-shaft so a
death doesn't undo all the progress. Four ember pickups are distributed
across the descent, each worth 2 ember, total 8 ember per the brief.

The bottom of the shaft below y=6 is a void hazard. Falling into it ends
the run, which is the intended consequence of falling past the exit.

Tier: 3, matching the brief's tier-3 fault-lines requirement.
"""


PLATFORMER_EASY_CORRECT_INLINE_STYLE = """new level: fault_lines_07_the_chasm
tier 3, region fault_lines

# Layout (vertical shaft, descent)
entry: top of shaft at (12, 96)
exit:  bottom of shaft at (18, 8)

# 6 platforms, alternating axis-aligned wide and narrow ledges
platforms:
  1. (14, 88) wide, 8 tiles
  2. (8,  76) narrow ledge, 6 tiles
  3. (22, 64) wide, 10 tiles
  4. (6,  50) narrow ledge, 4 tiles
  5. (16, 36) wide, 8 tiles
  6. (14, 18) wide, 6 tiles  -- final, leads to exit

# 2 checkpoints on the natural descent path
checkpoints: (24, 64) after platform 3; (8, 36) after platform 5

# 4 ember pickups, value 2 each (total = 8)
embers: (10, 86), (24, 62), (6, 48), (16, 16) -- each worth 2 ember

# lethal void below exit (any fall past y=6 = death)
hazard: void at y < 6, full shaft width
"""


PLATFORMER_EASY_INCORRECT_OFFTOPIC = """Here's the level YAML for fault_lines_03_the_overlook, a tier-2 platforming
section.

id: fault_lines_03_the_overlook
tier: 2
entry: (5, 40)
exit:  (45, 50)
platforms:
  - (10, 30) wide
  - (20, 35) narrow
  - (30, 45) wide
checkpoints:
  - (15, 32)
pickups:
  - (12, 28) ember=1
  - (22, 32) ember=1

The overlook section gives the player a vista of the lava lake below. The
camera zooms out briefly on entry. Three platforms, one checkpoint, two
ember pickups. The player exits to the south via a one-way drop.
"""


PLATFORMER_EASY_INCORRECT_HANDWAVE = """Sure, I can author that level. Let me think about it.

The level is a vertical descent in the fault_lines region. The player
starts at the top and needs to get to the bottom. There will be platforms
to land on, checkpoints to make the descent forgiving, and ember pickups
to reward exploration. A void at the bottom punishes falling past the
exit.

I'll need to make sure the platforms are spaced correctly so the player
can always reach the next one. The checkpoints should be on the natural
path. The ember pickups should be a small detour to reward exploration.

Let me know if you want me to flesh this out into actual coordinates.
"""


PLATFORMER_EASY_INCORRECT_WRONG_SPECS = """fault_lines_07_the_chasm
tier 5

This level is a horizontal traversal across the chasm. The player enters
on the west side and travels east across 12 floating platforms over a
wide gap. Two checkpoints divide the traversal. Three ember pickups
along the path, each worth 5 ember.

There are no hazards — falling between platforms drops the player onto
the safety net below, which bounces them back up.

content/levels/fault_lines_07_the_chasm.yaml:
id: fault_lines_07_the_chasm
tier: 5
direction: east
platforms_count: 12
checkpoints_count: 2
ember_pickups_count: 3
ember_per_pickup: 5
hazard: none
"""


SURVIVAL_EASY_CORRECT_A_STYLE = """Per `{content.recipes}` schema, here is the new recipe entity:

<<< FILE: content/recipes/cooked_fish.yaml >>>
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: cooked_fish
status: draft
implemented_in: ["src/recipes/cooked_fish.py"]
tier: 2
station: "{entities.campfire}"
inputs:
  - {item: raw_fish, count: 1}
outputs:
  - {item: cooked_fish, count: 1}
craft_time_minutes: 30
output_properties:
  cooked_fish:
    tags: [food, edible, cooked]
    hunger_restore: 6
<<< END FILE: content/recipes/cooked_fish.yaml >>>

Per the spec, tier-2 means the wooden axe tool tier gates discovery, the
campfire `{entities.campfire}` is the crafting station, and the food tag
makes the output edible (refills 6 hunger when consumed).
"""


SURVIVAL_EASY_CORRECT_PROSE_STYLE = """A new recipe for Driftwood: cooked_fish, a tier-2 food recipe.

The recipe takes one raw_fish as its only input and produces one
cooked_fish as its only output. The crafting station is the campfire —
the player needs to have built a campfire and be standing within its
crafting radius to access this recipe. The craft time is approximately
30 in-game minutes, in line with the brief's specification.

The cooked_fish output is tagged as food, meaning it's edible. When the
player eats it, hunger restores by 6 points. This is meaningful in the
survival loop because raw fish on its own is risky to eat (small hunger
gain, parasite chance), so the recipe is a clear utility upgrade: spend
the time at the campfire, get more hunger value per fish, no risk.

Tier 2 places this recipe behind the wooden axe gate — the player has
to have crafted a wooden axe before this recipe shows up in the recipe
list, even though the cooked_fish recipe itself doesn't require the
axe as a tool input.
"""


SURVIVAL_EASY_CORRECT_INLINE_STYLE = """new recipe: cooked_fish
tier: 2 (gates: wooden_axe must exist to unlock)

inputs:  1 x raw_fish
outputs: 1 x cooked_fish
station: campfire
craft_time: 30 in-game minutes

cooked_fish item properties:
  tags: food, edible
  hunger_restore: 6  (eating it restores 6 hunger)
"""


SURVIVAL_EASY_INCORRECT_OFFTOPIC = """Here's a new recipe: smoked_meat.

inputs: 2 x raw_meat
outputs: 1 x smoked_meat
station: smoker
craft_time: 60 minutes
tier: 3

smoked_meat tags: food, preserved
smoked_meat hunger_restore: 10

The smoker is a new station built from 4 stone and 2 fiber_rope, costing
the player an early-game investment. Once built, the player can smoke
meat for long-term storage — smoked meat doesn't spoil even in summer,
unlike fresh meat. This recipe is a key bridge between the hunting and
storage loops.
"""


SURVIVAL_EASY_INCORRECT_HANDWAVE = """OK, cooking fish makes sense for a survival game with a hunger system.

The recipe should take raw fish and produce cooked fish at a campfire.
Cooked fish should give more hunger than raw fish. The craft time should
be reasonable — not instant, but not punishing either.

I would author the YAML conforming to the recipes schema, with appropriate
input and output declarations, a campfire station reference, and a tier
that fits the early-game pacing. Let me know if you'd like me to write
out the full file.
"""


SURVIVAL_EASY_INCORRECT_WRONG_SPECS = """cooked_fish recipe (tier 4)

inputs: 5 x raw_fish, 2 x wood, 1 x salt
outputs: 1 x cooked_fish_premium
station: stone_oven
craft_time: 4 hours

cooked_fish_premium item:
  tags: luxury_food
  hunger_restore: 25
  buff: well_fed (15 minutes)

The premium variant is a luxury endgame recipe unlocked at tier 4. The
stone_oven is a tier-3 station the player must build first. The buff
gives a temporary stamina boost — not just hunger restoration.
"""


# Anchor library keyed by (game, task_cell_id).
# Each entry: {"correct": [text, text, text], "incorrect": [text, text, text]}.
CONTENT_PRESERVATION_ANCHORS: dict[tuple[str, str], dict[str, list[str]]] = {
    ("platformer", "easy_platformer"): {
        "correct": [
            PLATFORMER_EASY_CORRECT_A_STYLE,
            PLATFORMER_EASY_CORRECT_PROSE_STYLE,
            PLATFORMER_EASY_CORRECT_INLINE_STYLE,
        ],
        "incorrect": [
            PLATFORMER_EASY_INCORRECT_OFFTOPIC,
            PLATFORMER_EASY_INCORRECT_HANDWAVE,
            PLATFORMER_EASY_INCORRECT_WRONG_SPECS,
        ],
    },
    ("survival", "easy_survival"): {
        "correct": [
            SURVIVAL_EASY_CORRECT_A_STYLE,
            SURVIVAL_EASY_CORRECT_PROSE_STYLE,
            SURVIVAL_EASY_CORRECT_INLINE_STYLE,
        ],
        "incorrect": [
            SURVIVAL_EASY_INCORRECT_OFFTOPIC,
            SURVIVAL_EASY_INCORRECT_HANDWAVE,
            SURVIVAL_EASY_INCORRECT_WRONG_SPECS,
        ],
    },
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentPreservationPerSetResult:
    """One (game, task_cell_id) anchor set's two-phase result."""
    game: str
    task_cell_id: str
    n_correct: int
    n_incorrect: int

    # Phase A — raw / anchor sanity
    raw_correct_scores: tuple[int, ...]
    raw_incorrect_scores: tuple[int, ...]
    raw_median_correct: float
    raw_median_incorrect: float
    raw_gap: float
    anchor_sanity_passed: bool
    anchor_sanity_failure_reasons: tuple[str, ...]

    # Phase B — sanitized / content-preserved
    sanitized_correct_scores: tuple[int, ...]
    sanitized_incorrect_scores: tuple[int, ...]
    sanitized_median_correct: float
    sanitized_median_incorrect: float
    sanitized_gap: float
    content_preservation_passed: bool
    content_preservation_failure_reasons: tuple[str, ...]

    set_passed: bool  # both phases for this set


@dataclass(frozen=True)
class ContentPreservationResult:
    """Combined content-preservation calibration result (v8).

    overall_passed iff every per-set result has set_passed = True.
    A reviewer of a failed run inspects per_set to see which (game, task)
    set failed which phase.
    """
    judge_bundle_id: str
    sanitization_sha256: str
    anchor_set_sha256: str
    per_set: tuple[ContentPreservationPerSetResult, ...]
    overall_passed: bool


# ---------------------------------------------------------------------------
# Calibration entry point
# ---------------------------------------------------------------------------

def calibrate_content_preservation(
    judge: Judge,
    anchor_sets: dict[tuple[str, str], dict[str, list[str]]] | None = None,
) -> ContentPreservationResult:
    """Run the two-phase content-preservation calibration (pre-reg v8).

    Phase A (raw): the judge scores the K correct + K incorrect anchors
      from each (game, task_cell_id) set. PASS iff
      median(correct, raw)   >= ANCHOR_SANITY_CORRECT_FLOOR (4)
      median(incorrect, raw) <= ANCHOR_SANITY_INCORRECT_CEILING (2)
      raw gap                >= ANCHOR_SANITY_GAP_FLOOR (3)

    Phase B (sanitized): same judge scores the same anchors after
      `sanitize_output` is applied. PASS iff
      median(correct, sanitized) >= CONTENT_PRESERVATION_CORRECT_FLOOR (3)
      sanitized gap              >= CONTENT_PRESERVATION_GAP_FLOOR (2)

    Overall pass iff every per-set result has both phases passing.

    The judge's matches-intent rubric is the score for each anchor (the
    same rubric used in trial scoring). The task brief and game brief are
    looked up per (game, task_cell_id) from the on-disk anchor library.
    """
    if anchor_sets is None:
        anchor_sets = CONTENT_PRESERVATION_ANCHORS

    san_sha = sanitization_sha256()
    anchor_sha = _anchor_set_sha256(anchor_sets)

    per_set_results: list[ContentPreservationPerSetResult] = []

    for (game, task_cell_id), anchors in anchor_sets.items():
        correct_texts = anchors["correct"]
        incorrect_texts = anchors["incorrect"]

        # Load the task brief + game brief once per set.
        task_brief, game_brief = _load_briefs(game, task_cell_id)

        # Phase A — score raw anchors
        raw_correct = tuple(
            _score(judge, task_brief, t, game_brief) for t in correct_texts
        )
        raw_incorrect = tuple(
            _score(judge, task_brief, t, game_brief) for t in incorrect_texts
        )
        raw_med_c = _median(raw_correct)
        raw_med_i = _median(raw_incorrect)
        raw_gap = raw_med_c - raw_med_i

        sanity_reasons: list[str] = []
        if raw_med_c < ANCHOR_SANITY_CORRECT_FLOOR:
            sanity_reasons.append(
                f"median(correct, raw) = {raw_med_c} < {ANCHOR_SANITY_CORRECT_FLOOR}"
            )
        if raw_med_i > ANCHOR_SANITY_INCORRECT_CEILING:
            sanity_reasons.append(
                f"median(incorrect, raw) = {raw_med_i} > {ANCHOR_SANITY_INCORRECT_CEILING}"
            )
        if raw_gap < ANCHOR_SANITY_GAP_FLOOR:
            sanity_reasons.append(
                f"raw gap = {raw_gap} < {ANCHOR_SANITY_GAP_FLOOR}"
            )
        sanity_passed = not sanity_reasons

        # Phase B — sanitize, score sanitized anchors
        san_correct = tuple(
            _score(judge, task_brief, sanitize_output(t), game_brief)
            for t in correct_texts
        )
        san_incorrect = tuple(
            _score(judge, task_brief, sanitize_output(t), game_brief)
            for t in incorrect_texts
        )
        san_med_c = _median(san_correct)
        san_med_i = _median(san_incorrect)
        san_gap = san_med_c - san_med_i

        preservation_reasons: list[str] = []
        if san_med_c < CONTENT_PRESERVATION_CORRECT_FLOOR:
            preservation_reasons.append(
                f"median(correct, sanitized) = {san_med_c} < "
                f"{CONTENT_PRESERVATION_CORRECT_FLOOR}"
            )
        if san_gap < CONTENT_PRESERVATION_GAP_FLOOR:
            preservation_reasons.append(
                f"sanitized gap = {san_gap} < {CONTENT_PRESERVATION_GAP_FLOOR}"
            )
        preservation_passed = not preservation_reasons

        per_set_results.append(ContentPreservationPerSetResult(
            game=game,
            task_cell_id=task_cell_id,
            n_correct=len(correct_texts),
            n_incorrect=len(incorrect_texts),
            raw_correct_scores=raw_correct,
            raw_incorrect_scores=raw_incorrect,
            raw_median_correct=raw_med_c,
            raw_median_incorrect=raw_med_i,
            raw_gap=raw_gap,
            anchor_sanity_passed=sanity_passed,
            anchor_sanity_failure_reasons=tuple(sanity_reasons),
            sanitized_correct_scores=san_correct,
            sanitized_incorrect_scores=san_incorrect,
            sanitized_median_correct=san_med_c,
            sanitized_median_incorrect=san_med_i,
            sanitized_gap=san_gap,
            content_preservation_passed=preservation_passed,
            content_preservation_failure_reasons=tuple(preservation_reasons),
            set_passed=(sanity_passed and preservation_passed),
        ))

    overall = all(r.set_passed for r in per_set_results)
    return ContentPreservationResult(
        judge_bundle_id=judge.bundle.bundle_id(),
        sanitization_sha256=san_sha,
        anchor_set_sha256=anchor_sha,
        per_set=tuple(per_set_results),
        overall_passed=overall,
    )


def write_content_preservation_result(
    result: ContentPreservationResult,
    out_dir: Path,
) -> Path:
    import time
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    safe_bundle = result.judge_bundle_id.replace("/", "_")
    fname = f"content_preservation_{safe_bundle}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(_to_jsonable(result), indent=2, default=str))
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(judge: Judge, task_brief: str, output: str, game_brief: str) -> int:
    """Score one anchor with the matches-intent rubric. Returns the 0-5 score."""
    return judge.score_matches_intent(
        task_brief=task_brief,
        subject_output=output,
        game_brief=game_brief,
    ).score


def _median(scores: tuple[int, ...]) -> float:
    if not scores:
        return 0.0
    s = sorted(scores)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _load_briefs(game: str, task_cell_id: str) -> tuple[str, str]:
    """Load the task brief + game brief for one anchor set."""
    here = Path(__file__).resolve().parent
    repo_root = here.parent.parent  # benchmark/.. = repo root
    tasks_dir = here.parent / "tasks"
    games_dir = here.parent / "games"

    task_path = tasks_dir / f"{task_cell_id}.yaml"
    game_brief_path = games_dir / game / "design-brief.md"

    # Parse just the `brief:` field out of the task YAML (lightweight; avoid
    # importing the loader which would re-trigger the full registry).
    from .tasks import load_task
    task_type = task_cell_id.split("_")[0]  # "easy" | "medium" | "hard" | "ambiguity"
    task = load_task(task_type, game)
    task_brief = task.brief

    game_brief = (
        game_brief_path.read_text() if game_brief_path.exists() else ""
    )
    return task_brief, game_brief


def _anchor_set_sha256(
    anchor_sets: dict[tuple[str, str], dict[str, list[str]]],
) -> str:
    """SHA-256 of the anchor library — canonicalized so the SHA is stable."""
    # Canonical form: sort sets by (game, task_cell_id); within each, sort by
    # role ("correct" / "incorrect"); anchor texts in their declared order
    # (declaration order is part of the pinned artifact).
    canonical: list[tuple[str, str, str, tuple[str, ...]]] = []
    for (game, task_cell_id) in sorted(anchor_sets.keys()):
        a = anchor_sets[(game, task_cell_id)]
        for role in sorted(a.keys()):
            canonical.append((game, task_cell_id, role, tuple(a[role])))
    blob = json.dumps(canonical, sort_keys=False, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _to_jsonable(obj):
    """Convert dataclasses + tuples to dicts/lists for JSON serialization."""
    from dataclasses import is_dataclass, fields
    if is_dataclass(obj):
        return {f.name: _to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    return obj


# Self-test under `python -m benchmark.harness.content_preservation`
if __name__ == "__main__":
    from .judge import MockJudge
    print(
        f"Anchor library SHA: "
        f"{_anchor_set_sha256(CONTENT_PRESERVATION_ANCHORS)[:16]}..."
    )
    print(
        f"Anchor sets: {len(CONTENT_PRESERVATION_ANCHORS)} "
        f"({sum(len(a['correct']) + len(a['incorrect']) for a in CONTENT_PRESERVATION_ANCHORS.values())} anchors total)"
    )
    print(f"Sanitization SHA: {sanitization_sha256()[:16]}...")
    print(
        "Running MockJudge against anchors — expect FAIL "
        "(mock scores by length, can't read correctness):"
    )
    result = calibrate_content_preservation(MockJudge())
    print(f"  overall_passed: {result.overall_passed}")
    for ps in result.per_set:
        print(
            f"  [{ps.game}/{ps.task_cell_id}] "
            f"raw_gap={ps.raw_gap:.1f} (sanity {'PASS' if ps.anchor_sanity_passed else 'FAIL'}) "
            f"sanitized_gap={ps.sanitized_gap:.1f} (preserve {'PASS' if ps.content_preservation_passed else 'FAIL'})"
        )
        if not ps.anchor_sanity_passed:
            for r in ps.anchor_sanity_failure_reasons:
                print(f"    sanity_fail: {r}")
        if not ps.content_preservation_passed:
            for r in ps.content_preservation_failure_reasons:
                print(f"    preserve_fail: {r}")
