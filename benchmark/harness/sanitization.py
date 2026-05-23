"""Output sanitization for the blinding-leak calibration's two-phase gate.

Per pre-reg v7 §"Judge" Layer 3 step 3, sanitization is a *pre-registered*
deterministic transformation applied to subject outputs between Phase 1
(positive control: judge predicts on RAW outputs, must be above chance)
and Phase 2 (blinding-leak gate: judge predicts on SANITIZED outputs,
must be at chance). The exact sanitization function is committed here;
its SHA is recorded with each calibration artifact.

**At v7 the sanitization includes:**

  1. Strip `{namespace.id}` curly-brace syntax (keep the bare token paths).
     A-condition outputs may use the spec's `{verbs.wall_kick}` syntax;
     stripping the braces removes the most obvious A-tell.
  2. Strip canonical section headers (`## Tokens`, `## Rationale`,
     `## Open Questions`, `## Change Log`). A outputs may copy the
     spec's structural headers when summarizing what they did.
  3. Strip file-boundary markers (`<<< FILE: ... >>>` / `<<< END FILE: >>>`)
     that A outputs may have copied from condition A's payload encoding.
  4. Strip explicit references to "the spec" / "the design document" /
     "the gdd" / "the game-design.md" / "the architecture invariants" —
     these are A/B tells in both directions (A says "per the spec"; C
     says nothing of the sort).
  5. Normalize whitespace (collapse runs of 3+ blank lines into 2; strip
     trailing whitespace on every line).
  6. Strip Markdown frontmatter fences (`---` ... `---`) that A outputs
     may have copied from the spec's YAML frontmatter pattern.

**The sanitization is NOT meant to make outputs identical** — that would
defeat the harness. It's meant to remove the *condition-identifying
stylistic markers* the judge could use to predict condition without
actually reading the content. Content-level differences between A/B/C
outputs (different design choices, different numerical answers, etc.)
remain visible to the judge and to the human scorer.

**To change the sanitization** after v7: a new pre-registration cycle
is required (per §"Pre-registration commit"). The sanitization function
is part of the gate's decision rule, not the harness-build commit. The
expected workflow if Phase 2 keeps failing at v7-sanitization is:
strengthen the sanitizer in a pre-reg v8 commit, re-run the calibration
from Phase 2 (Phase 1 result holds — the judge already passed fitness).
"""
from __future__ import annotations

import hashlib
import re


# Sanitization regexes (compiled once)

# Match `{namespace.id...}` references — the same pattern as the spec's
# token-reference grammar (spec §3, 2-6 dot-separated segments)
REF_RE = re.compile(r"\{([a-z_][a-z0-9_]*(?:\.[a-z0-9_][a-z0-9_-]*){1,5})\}")

# Match canonical section headers (at start of line)
SECTION_HEADERS_RE = re.compile(
    r"^(## Tokens|## Rationale|## Open Questions|## Change Log)\s*$",
    re.MULTILINE,
)

# Match file-boundary markers
FILE_BOUNDARY_RE = re.compile(r"<<<\s*(END\s+)?FILE:.*?>>>", re.IGNORECASE)

# Match explicit "as per the spec" type phrases (case-insensitive)
SPEC_REFERENCE_PHRASES = [
    r"\bper\s+the\s+spec\b",
    r"\baccording\s+to\s+the\s+spec\b",
    r"\bas\s+(the\s+)?(spec|gdd|design[-\s]?document|game[-\s]?design\.md|design[-\s]?spec)\s+(says?|defines?|requires?|declares?)\b",
    r"\bthe\s+(spec|gdd|design[-\s]?document)\s+(says?|defines?|requires?|declares?|specifies?)\b",
    r"\bin\s+the\s+(spec|gdd|design[-\s]?document|architecture[-\s]?invariants)\b",
    r"\bfrom\s+the\s+(spec|gdd|design[-\s]?document)\b",
    r"\bper\s+the\s+(architecture[-\s]?invariants|invariants)\b",
]
SPEC_PHRASE_RE = re.compile("|".join(SPEC_REFERENCE_PHRASES), re.IGNORECASE)

# Match Markdown frontmatter (--- delimited YAML at the start of a doc)
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# Whitespace normalization
TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
MULTI_BLANK_RE = re.compile(r"\n{3,}")


def sanitize_output(raw_text: str) -> str:
    """Apply the v7 sanitization to one subject output.

    Returns the sanitized text. The function is deterministic and idempotent
    (running it twice gives the same result as once).
    """
    s = raw_text

    # 1. Strip `{namespace.id}` braces (keep the bare path)
    s = REF_RE.sub(lambda m: m.group(1), s)

    # 2. Strip canonical section headers
    s = SECTION_HEADERS_RE.sub("", s)

    # 3. Strip file-boundary markers
    s = FILE_BOUNDARY_RE.sub("", s)

    # 4. Strip "as the spec says" phrases
    s = SPEC_PHRASE_RE.sub("", s)

    # 5. Strip Markdown frontmatter blocks (--- ... ---) at the document start
    s = FRONTMATTER_RE.sub("", s)

    # 6. Normalize whitespace
    s = TRAILING_WS_RE.sub("", s)
    s = MULTI_BLANK_RE.sub("\n\n", s)
    s = s.strip() + "\n"

    return s


def sanitization_sha256() -> str:
    """SHA-256 of this module's source code.

    Recorded in every calibration artifact so a Phase-2 fail can be
    re-evaluated against the exact sanitization function in effect at
    the time of the run. If this file changes, the SHA changes; the
    calibration must be re-run.
    """
    from pathlib import Path
    here = Path(__file__).resolve()
    return hashlib.sha256(here.read_bytes()).hexdigest()


# Self-test under `python -m benchmark.harness.sanitization`
if __name__ == "__main__":
    sample = """---
spec: game-design.md
file_type: subfile
---

## Tokens

I implemented `{verbs.wall_kick}` per the spec. The verb is wired through
`{loops.flight}` per the architecture invariants.

<<< FILE: gdd/mechanics.md >>>
...
<<< END FILE: gdd/mechanics.md >>>


As the design document says, the cost is 1 ember.



## Rationale

Wall kicks are committed actions.
"""
    print("--- RAW ---")
    print(sample)
    print(f"--- SANITIZED (SHA={sanitization_sha256()[:16]}) ---")
    print(sanitize_output(sample))
