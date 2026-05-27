"""ChecklistGrader wiring tests (v14-D).

Verifies that `ChecklistGrader._grade_criterion` routes through
`Judge.grade_checklist_criterion` rather than the pre-v14-D stub (keyword
match inside ChecklistGrader). The wiring is the load-bearing change at
v14-D — these tests prevent a silent regression to the stub.
"""
from __future__ import annotations

from benchmark.harness.checklist import (
    ChecklistGrader,
    CriterionVerdict,
)
from benchmark.harness.judge import (
    ConditionPrediction,
    FairnessScore,
    IntentScore,
    Judge,
    JudgeBundle,
    MockJudge,
)
from benchmark.harness.tasks import ChecklistCriterion, Task


class _RecordingJudge(Judge):
    """A judge that records every grade_checklist_criterion call. Used to
    verify ChecklistGrader routes through Judge.grade_checklist_criterion.
    Returns canned (passed, rationale) per the controlled probe.
    """

    def __init__(self):
        bundle = JudgeBundle(
            family="test", model_name="recording-judge", version="v0",
            notes="Test fixture; records calls.",
        )
        super().__init__(bundle)
        self.calls: list[dict] = []

    def score_matches_intent(self, task_brief, subject_output, game_brief):
        return IntentScore(score=4, rationale="[TEST]", bundle_id=self.bundle.bundle_id())

    def audit_fairness(self, flattened_b_text, game_name, game_pitch):
        return FairnessScore(score=5, rationale="[TEST]", specific_issues=(),
                             bundle_id=self.bundle.bundle_id())

    def predict_conditions(self, outputs):
        return [
            ConditionPrediction(output_id=oid, predicted_condition="A",
                                confidence=1.0, rationale="[TEST]")
            for oid, _ in outputs
        ]

    def grade_checklist_criterion(self, criterion_id, criterion_description,
                                    subject_output):
        self.calls.append({
            "criterion_id": criterion_id,
            "criterion_description": criterion_description,
            "subject_output_chars": len(subject_output),
        })
        # Canned: pass iff the criterion_id appears verbatim in the output
        passed = criterion_id in subject_output
        return (passed, f"[TEST] saw '{criterion_id}' in output? {passed}")


def _make_task(criteria: list[tuple[str, str]]) -> Task:
    return Task(
        task_type="medium",
        game="survival",
        n_per_cell=1,
        headline=False,
        brief="Test brief.",
        intent_checklist=tuple(
            ChecklistCriterion(id=i, description=d) for (i, d) in criteria
        ),
        notes="",
        source_sha256="0" * 64,
    )


def test_checklist_grader_routes_through_judge_grade_checklist_criterion():
    """v14-D wiring: ChecklistGrader._grade_criterion MUST call
    self.judge.grade_checklist_criterion (NOT the pre-v14-D inline stub).
    Verified via a recording judge that captures every grade call.
    """
    judge = _RecordingJudge()
    grader = ChecklistGrader(judge)
    task = _make_task([
        ("alpha_present", "the output contains 'alpha_present' verbatim"),
        ("beta_present", "the output contains 'beta_present' verbatim"),
        ("gamma_absent", "the output contains 'gamma_absent' verbatim"),
    ])
    subject_output = (
        "Implementation of alpha_present and beta_present, "
        "but gamma is absent without the underscore form."
    )
    verdict = grader.grade(task, subject_output)

    # Judge.grade_checklist_criterion called once per criterion (3 calls)
    assert len(judge.calls) == 3
    seen_ids = [c["criterion_id"] for c in judge.calls]
    assert seen_ids == ["alpha_present", "beta_present", "gamma_absent"]
    # Each call received the full subject_output
    for call in judge.calls:
        assert call["subject_output_chars"] == len(subject_output)
    # Verdicts match the recording judge's canned logic
    by_id = {v.criterion_id: v for v in verdict.criteria}
    assert by_id["alpha_present"].passed is True
    assert by_id["beta_present"].passed is True
    assert by_id["gamma_absent"].passed is False
    # Overall pass requires ALL criteria pass (per pre-reg)
    assert verdict.passes_checklist is False
    assert verdict.fraction_passing() == 2 / 3


def test_checklist_grader_with_mockjudge_preserves_stub_keyword_behavior():
    """MockJudge.grade_checklist_criterion preserves the pre-v14-D keyword-
    match behavior so existing tests continue passing AND the harness
    remains exercisable end-to-end without external infra.
    """
    judge = MockJudge()
    grader = ChecklistGrader(judge)
    task = _make_task([
        ("inspect_tool", "the implementation defines an inspect_tool action"),
        ("never_appears", "the implementation defines never_appears criterion"),
    ])
    subject_output = "I implemented the inspect tool action."

    verdict = grader.grade(task, subject_output)
    by_id = {v.criterion_id: v for v in verdict.criteria}
    # MockJudge does permissive keyword-match: "inspect_tool" → "inspect tool"
    # which IS in the output (lowercased).
    assert by_id["inspect_tool"].passed is True
    # "never_appears" → "never appears" which is NOT in the output.
    assert by_id["never_appears"].passed is False
    # Mock rationales are tagged [MOCK]
    assert "[MOCK]" in by_id["inspect_tool"].rationale


def test_pre_v14d_stub_marker_gone():
    """Regression guard: the pre-v14-D `[STUB] permissive keyword match ...
    replace with judge call before trials count.` rationale MUST NOT appear
    in any verdict. If this test fires, ChecklistGrader has regressed back
    to its pre-v14-D stub. The v14-D wiring routes through
    Judge.grade_checklist_criterion which (a) on MockJudge returns
    '[MOCK] ...' (b) on GemmaJudge returns the judge's own rationale.
    """
    judge = MockJudge()
    grader = ChecklistGrader(judge)
    task = _make_task([("x_y", "test criterion")])
    verdict = grader.grade(task, "any output")
    for c in verdict.criteria:
        assert "[STUB]" not in c.rationale, (
            f"v14-D regression: stub marker reappeared in '{c.criterion_id}': "
            f"{c.rationale}"
        )
        assert "replace with judge call" not in c.rationale, (
            f"v14-D regression: stub marker reappeared in '{c.criterion_id}'"
        )
