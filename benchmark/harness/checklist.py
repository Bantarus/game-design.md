"""Objective intent checklist evaluation.

Per pre-reg §"Judge" Layer 1, each task carries a 3-7 binary checklist of
machine-scorable criteria. The criteria probe game behavior / content, NOT
spec-structure-conformance (per the user's harness-caution at v6 + Game #2).

The scoring is *machine-mechanical* — but "machine" here can mean either
(a) a deterministic substring / regex check, or (b) an LLM-grader that
applies the criterion's description to the output. Option (b) is what the
pre-reg's "machine-scored" language permits when criteria are inherently
fuzzy (e.g. "the implementation includes a balance-tracking number"); the
LLM-grader is the SAME pinned aux judge used for the "matches intent"
rubric, run with a tightly constrained yes/no prompt per criterion.

This module provides the abstraction; the LLM-grader plumbing is stubbed
pending the aux judge being wired up. A pure-substring grader is provided
as a fallback for criteria simple enough to score that way.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tasks import ChecklistCriterion, Task


@dataclass(frozen=True)
class CriterionVerdict:
    criterion_id: str
    passed: bool
    rationale: str  # short explanation


@dataclass(frozen=True)
class ChecklistVerdict:
    task_cell_id: str
    criteria: tuple[CriterionVerdict, ...]
    passes_checklist: bool  # True iff all criteria pass

    def fraction_passing(self) -> float:
        if not self.criteria:
            return 0.0
        return sum(1 for c in self.criteria if c.passed) / len(self.criteria)


class ChecklistGrader:
    """Default LLM-as-grader for intent checklists.

    Each criterion's description is interpreted as a yes/no question about
    the subject output; the judge is asked to answer it. The aux judge
    pinned at the harness-build commit is used (per the pre-reg).
    """

    def __init__(self, judge):
        """judge: a `Judge` instance (concrete or MockJudge)."""
        self.judge = judge

    def grade(self, task: Task, subject_output: str) -> ChecklistVerdict:
        verdicts: list[CriterionVerdict] = []
        for crit in task.intent_checklist:
            verdict = self._grade_criterion(crit, task, subject_output)
            verdicts.append(verdict)
        return ChecklistVerdict(
            task_cell_id=task.cell_id,
            criteria=tuple(verdicts),
            passes_checklist=all(v.passed for v in verdicts),
        )

    def _grade_criterion(
        self, crit: ChecklistCriterion, task: Task, output: str
    ) -> CriterionVerdict:
        """Grade one criterion. Uses a tight yes/no judge prompt.

        STUB: until the aux judge is wired up, this returns a permissive
        substring-based grade for very simple criteria, and a 'cannot grade'
        verdict for everything else. The intent is for the wired-up Judge
        to replace this with a real grading call.
        """
        # Permissive: if any keyword from the criterion id appears in the
        # output, count it as "passed" — purely to let the harness exercise
        # end-to-end without a wired-up judge. This is NOT scoring; it's a
        # placeholder.
        keyword = crit.id.replace("_", " ")[:30]
        passed = keyword in output.lower() or crit.id.replace("_", "") in output.lower()
        return CriterionVerdict(
            criterion_id=crit.id,
            passed=passed,
            rationale=f"[STUB] permissive keyword match on '{keyword}'; replace with judge call before trials count.",
        )


def write_checklist_template_for_judge(criterion: ChecklistCriterion) -> str:
    """The prompt template the wired-up judge will use to grade one criterion.

    Pinned here so the audit-trail records exactly what was asked.
    """
    return f"""You are grading one criterion of an objective intent checklist for a
help-benchmark trial. The criterion is a yes/no question about whether
a subject's output meets a specific game-behavior / game-content
requirement.

CRITERION ID: {criterion.id}
CRITERION DESCRIPTION:
{criterion.description}

SUBJECT OUTPUT (verbatim):
---
{{SUBJECT_OUTPUT}}
---

Question: Does the subject output meet the criterion as described?

Respond with exactly this JSON, no other text:

```json
{{{{
  "passed": <true | false>,
  "rationale": "<1-2 sentences citing specific text in the output>"
}}}}
```

Pass if the output meets the criterion's intent — exact wording is not
required (an A-condition output using spec namespacing, a B-condition
output using prose paraphrase, and a C-condition output using inline
implementation comments can all pass the same criterion if all three
exhibit the requested game behavior). Fail if the output silently
omits the requested behavior or contradicts it.

Do NOT pass an output for being structurally spec-shaped if its
content does not meet the criterion. Do NOT fail an output for being
unstructured if its content does meet the criterion. The scoring is
behavioral, not structural.
"""
