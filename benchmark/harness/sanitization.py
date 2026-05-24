"""Output sanitization for the blinding-leak calibration's two-phase gate.

Per pre-reg v7 §"Judge" Layer 3 step 3, sanitization is a *pre-registered*
deterministic transformation applied to subject outputs between Phase 1
(positive control: judge predicts on RAW outputs, must be above chance)
and Phase 2 (blinding-leak gate: judge predicts on SANITIZED outputs,
must be at chance). The exact sanitization function is committed here;
its SHA is recorded with each calibration artifact.

Per pre-reg v8 §"Judge" Layer 2, sanitization ALSO runs at trial-time
on every subject output before either judge call (matches-intent +
checklist grader) — raw outputs MUST NEVER reach the scoring judge.

**Design discipline (v9):** every sanitization rule is either

  (S) a **structural** pattern (regex on shape, content-agnostic — works
      across any vocabulary the spec might evolve to use), OR

  (E) a **closed enumeration** drawn from the *spec's* declared
      vocabulary (`docs/spec.md` §3 namespaces, §5.2 + §7.1 canonical
      section headers, etc.) — NOT from observed calibration samples.

The discipline exists because v8's gate validated the sanitizer on the
90-output calibration sample; production sanitization runs on the
~660-trial population, which the calibration never saw. A denylist
drawn from calibration samples is `train_set`-shaped and will leak any
tell that appears in trials but not in calibration. A closed enumeration
drawn from spec vocabulary is content-general by construction — the
spec's vocabulary is the closed superset of what any A-condition output
can draw from. See pre-reg v8 → v9 audit-trail row #17 and project
memory `train-test-distribution-shift-sanitizer` for the standing rule.

Each rule below is labeled (S) or (E) plus its source.

**v9 ruleset:**

  1. (E, spec §3) Brace-form refs in known namespaces: replace
     `{ns.rest}` with `rest` — strip the namespace prefix, keep the
     entity-level identifier. Removes the namespace word (`entities`,
     `verbs`, `loops`, etc.) which is the spec-vocabulary tell, while
     preserving the entity name (e.g. `wall_kick`, `cards.ember_strike`)
     so the matches-intent judge can still recognize what's being
     referenced.
  2. (S) Brace-form refs in unknown namespaces (fallback): replace
     `{x.y}` with `x.y` — strip just the braces. Catches refs into
     non-standard namespaces without dropping their structure.
  3. (E, spec §3) Bare-form refs in known namespaces (no braces):
     strip the namespace prefix from any dotted path whose leading
     segment is a known spec namespace. Word-boundaries on both sides
     so legitimate identifiers without namespace prefix are unaffected.
     Catches outputs that wrote bare dotted paths or that survived
     rule 2's generic brace-strip.
  4. (E, spec §5.2 + §7.1) Canonical section headers: full-line strip.
     A condition outputs may copy the spec's canonical section sequence
     (`## Tokens` / `## Rationale` / etc.); enumerate the full closed
     set declared in the spec (NOT just the four observed in v7's
     calibration sample) so a trial-time A output mentioning any other
     canonical header (`## Schema`, `## Representative Example`, etc.)
     does not leak.
  5. (S) Remaining heading prefix: any H2/H3/H4 line keeps its text
     but loses its `##`/`###`/`####` marker. Pure structural — removes
     the hierarchical-markup tell from non-canonical headings without
     dropping their content. Runs AFTER rule 4 so canonical headers are
     already full-line-stripped and only non-canonical headings remain.
  6. (S) File-boundary markers: strip `<<< FILE: ... >>>` / `<<< END
     FILE: ... >>>` patterns. Pattern-shape rule; works for any path
     value.
  7. (E, spec terminology) Spec-reference phrases: enumerate phrases of
     the shape "{preposition} the {spec-noun}" or "{spec-noun} {verb}"
     where the spec-noun is drawn from a closed enumeration of synonyms
     for "the spec" (spec / gdd / design document / game-design.md /
     architecture invariants / pre-registration / design spec) and the
     verb is a closed list of declaration verbs. Expanded at v9 from
     v7's seven patterns to cover more spec-noun + verb combinations
     and section-number references.
  8. (S) Markdown frontmatter blocks (`---...---`) at document start.
     Pattern-shape rule.
  9. (E, spec §2.3 + §6.2 required-frontmatter-keys, spec-metadata
     subset, v11): full-line strip for lines whose leading key is one
     of `spec`, `spec_version`, `file_type`, `last_verified`,
     `last_updated`, `implemented_in`, `status`. Closes the v9 leak
     that Rule 8 missed: Rule 8 only matched `---...---`-fenced
     Markdown frontmatter, but content-entity YAML files (per spec
     §6.2) carry the same spec metadata fields *unfenced* at the top
     of a pure-YAML document — and trial outputs that take the form of
     content-entity YAML therefore retained the spec-metadata tells
     after v9 sanitization. The first step-6 run's blinding-leak judge
     correctly classified 12/12 of a sampled batch by citing exactly
     this leak ("Uses explicit 'spec: game-design.md' header" 4× for A,
     4× for B; "Lacks the 'spec:' header" 4× for C). Closed-enumeration
     scope is the spec-metadata SUBSET only — content keys (id, name,
     pillars, schema, entity, data_dir, count_target, etc.) are NOT
     stripped because the matches-intent rubric depends on them. Phase
     A scored anchors carrying these metadata fields at median 5/5,
     confirming the rubric doesn't weight them, and Phase B is the
     bidirectional counterweight that empirically verifies content is
     preserved across the strip. See pre-reg v10 → v11 audit-trail row
     #20 and project memory `sanitizer-iteration-stopping-rule` for
     the principled-iteration discipline this rule was authored under.
 10. (S) Whitespace normalization: trailing whitespace stripped per
     line; runs of 3+ blank lines collapsed to 2; trailing newline
     normalized to one. Pattern-shape rule.

**Content explicitly NOT sanitized** (so the matches-intent judge can
still discriminate good content from bad):

  - Numeric values, units, coordinates, counts.
  - Quoted code blocks beyond namespace tokens (YAML structure, list
    items, key-value pairs).
  - Identifier names (after namespace prefix removal).
  - Game-design content (mechanics, behaviors, design choices) — the
    sanitizer's job is to remove condition-distinguishing stylistic
    markers, not to flatten the content itself.

**Generalization to the trial population.** Even with rules 1+3+4
drawn from the spec's full closed enumerations, a sanitizer designed at
this commit could still fail to blind on real trial outputs that use
novel A-tells not anticipated here. v9 adds a **pre-sweep small-batch
generalization check** (pre-reg step 11b) and a **post-hoc full-sweep
sample check** (pre-reg step 14) — both run the Phase-2 at-chance
prediction on *real* trial outputs (not calibration anchors) so any
sanitizer-vs-trial-population gap is caught after ~20 trials instead of
after ~660. See `harness/calibration.py::check_blinding_generalization`.

**Changing the sanitization** after v9 requires a new pre-registration
cycle (per §"Pre-registration commit"). The sanitization function is
part of the gate's decision rule; its SHA is recorded with each
calibration and generalization-check artifact. Strengthening it (adding
more patterns) re-runs Phase 2 of blinding-leak + Phase B of
content-preservation + the small-batch generalization check; weakening
it (removing patterns) is identical structurally but with a different
diagnosis path.
"""
from __future__ import annotations

import hashlib
import re


# ---------------------------------------------------------------------------
# Closed enumerations drawn from the spec (NOT from calibration samples).
# ---------------------------------------------------------------------------

# Spec namespace names — `docs/spec.md` §3 namespace ownership table, plus
# `content_schema` from §6.1 and the context-local prefixes (`actor`, `target`)
# from §3 D-012. Any future spec-level namespace would be added here as a
# spec-versioning event.
NAMESPACE_NAMES = (
    "entities", "verbs", "resources", "states", "events", "rules",
    "loops", "distributions", "feel", "balance_targets", "invariants",
    "verify_targets", "adapters", "pillars", "player_experience_goals",
    "non_goals", "core_loop_ref", "content_schema",
    "actor", "target",
)
_NS_ALT = "|".join(NAMESPACE_NAMES)

# Canonical spec section headers — `docs/spec.md` §5.2 (core file) and §7.1
# (subfile + content-schema file). Full enumeration, NOT just those observed
# in any calibration sample.
CANONICAL_HEADER_NAMES = (
    # Core file (§5.2)
    "High Concept",
    "Pillars & Non-Goals",
    "Pillars",
    "Player Experience Goals",
    "Core Gameplay Loop",
    "Universal Surface",
    "How to Use This Document (for the Agent)",
    "How to Use This Document",
    "Glossary",
    # Subfile (§7.1)
    "Tokens",
    "Rationale",
    "Open Questions",
    "Change Log",
    # Content-schema file (§7.1)
    "Schema",
    "Representative Example",
    "Balance Notes",
)
_CANONICAL_HEADER_ALT = "|".join(re.escape(h) for h in CANONICAL_HEADER_NAMES)


# ---------------------------------------------------------------------------
# Sanitization regexes (compiled once).
# Order of application is significant — see sanitize_output below.
# ---------------------------------------------------------------------------

# Rule 1 (E, spec §3): brace-form refs in known namespaces → strip namespace.
# `{entities.cards.ember_strike}` → `cards.ember_strike`
# `{verbs.wall_kick}` → `wall_kick`
BRACE_NS_RE = re.compile(
    rf"\{{(?:{_NS_ALT})\.([a-z0-9_][a-z0-9_.\-]*?)\}}"
)

# Rule 2 (S): brace-form refs in unknown namespaces (fallback) → strip braces.
# `{foo.bar}` → `foo.bar`. Same regex as v7 REF_RE.
REF_RE = re.compile(r"\{([a-z_][a-z0-9_]*(?:\.[a-z0-9_][a-z0-9_-]*){1,5})\}")

# Rule 3 (E, spec §3): bare-form refs in known namespaces → strip namespace.
# `entities.cards.ember_strike` → `cards.ember_strike` (in prose)
# Word-boundary on left so identifiers like `my_entities.foo` aren't matched.
BARE_NS_RE = re.compile(
    rf"\b(?:{_NS_ALT})\.([a-z0-9_][a-z0-9_.\-]*?)(?=\b|$|[^a-z0-9_.\-])"
)

# Rule 4 (E, spec §5.2 + §7.1): full-line strip for canonical headers.
CANONICAL_HEADERS_RE = re.compile(
    rf"^## (?:{_CANONICAL_HEADER_ALT})\s*$",
    re.MULTILINE,
)

# Rule 5 (S): structural heading-prefix strip — any H2/H3/H4 line loses its
# `##`/`###`/`####` marker, keeps its text. Runs AFTER rule 4.
HEADING_PREFIX_RE = re.compile(r"^#{2,4}\s+", re.MULTILINE)

# Rule 6 (S): file-boundary markers.
FILE_BOUNDARY_RE = re.compile(r"<<<\s*(END\s+)?FILE:.*?>>>", re.IGNORECASE)

# Rule 7 (E, spec terminology): spec-reference phrases. The spec-noun closed
# set: spec / gdd / design document / game-design.md / architecture invariants
# / pre-registration / design spec. The declaration verbs: says / defines /
# requires / declares / specifies / states / mandates.
SPEC_REFERENCE_PHRASES = [
    r"\bper\s+the\s+spec\b",
    r"\baccording\s+to\s+the\s+spec\b",
    r"\bas\s+(the\s+)?(spec|gdd|design[-\s]?document|game[-\s]?design\.md|design[-\s]?spec)\s+(says?|defines?|requires?|declares?|specifies?|states?|mandates?)\b",
    r"\bthe\s+(spec|gdd|design[-\s]?document)\s+(says?|defines?|requires?|declares?|specifies?|states?|mandates?)\b",
    r"\bin\s+the\s+(spec|gdd|design[-\s]?document|architecture[-\s]?invariants|pre[-\s]?registration)\b",
    r"\bfrom\s+the\s+(spec|gdd|design[-\s]?document)\b",
    r"\bper\s+the\s+(architecture[-\s]?invariants|invariants|pre[-\s]?registration)\b",
    r"\b(?:per|according\s+to)\s+(?:section|§)\s*\d+(?:\.\d+)*\b",  # "per §4.7", "according to section 5.2"
    r"\bthe\s+pre[-\s]?registration\b",
]
SPEC_PHRASE_RE = re.compile("|".join(SPEC_REFERENCE_PHRASES), re.IGNORECASE)

# Rule 8 (S): Markdown frontmatter blocks at document start.
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# Rule 9 (E, spec §2.3 + §6.2, v11): spec-frontmatter-metadata keys —
# full-line strip wherever they appear (handles the unfenced YAML case
# Rule 8 doesn't cover). Closed-enumeration scope is the spec-metadata
# subset only; content keys (id, name, pillars, schema, etc.) are
# explicitly excluded because the matches-intent rubric depends on them.
SPEC_FRONTMATTER_KEYS = (
    "spec",
    "spec_version",
    "file_type",
    "last_verified",
    "last_updated",
    "implemented_in",
    "status",
)
_FM_KEY_ALT = "|".join(SPEC_FRONTMATTER_KEYS)
SPEC_FRONTMATTER_LINE_RE = re.compile(
    rf"^[ \t]*(?:{_FM_KEY_ALT})\s*:.*$",
    re.MULTILINE,
)

# Rule 10 (S): whitespace normalization.
TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
MULTI_BLANK_RE = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# sanitize_output
# ---------------------------------------------------------------------------

def sanitize_output(raw_text: str) -> str:
    """Apply the v11 sanitization to one subject output.

    Deterministic and idempotent (running twice = once). Order of rules:

      1. Brace-form ns refs (known namespaces)        — strip namespace
      2. Brace-form ns refs (fallback)                — strip braces
      3. Bare-form ns refs (known namespaces)         — strip namespace
      4. Canonical section headers (closed enum)      — full-line strip
      5. Remaining heading prefixes (structural)      — strip `##`/`###`
      6. File-boundary markers                        — strip
      7. Spec-reference phrases                       — strip
      8. Markdown frontmatter at doc start (fenced)   — strip
      9. Spec frontmatter metadata keys (v11, unfenced)— full-line strip
     10. Whitespace normalization                     — collapse

    Returns the sanitized text.
    """
    s = raw_text

    # 1. Brace-form refs in known namespaces: keep tail
    s = BRACE_NS_RE.sub(lambda m: m.group(1), s)
    # 2. Brace-form refs (fallback): keep bare path
    s = REF_RE.sub(lambda m: m.group(1), s)
    # 3. Bare-form refs in known namespaces: keep tail
    s = BARE_NS_RE.sub(lambda m: m.group(1), s)
    # 4. Canonical section headers: full-line strip
    s = CANONICAL_HEADERS_RE.sub("", s)
    # 5. Remaining heading prefixes: structural strip
    s = HEADING_PREFIX_RE.sub("", s)
    # 6. File-boundary markers
    s = FILE_BOUNDARY_RE.sub("", s)
    # 7. Spec-reference phrases
    s = SPEC_PHRASE_RE.sub("", s)
    # 8. Markdown frontmatter at document start (fenced)
    s = FRONTMATTER_RE.sub("", s)
    # 9. Spec frontmatter metadata keys (unfenced, v11) — see Rule 9 doc above
    s = SPEC_FRONTMATTER_LINE_RE.sub("", s)
    # 10. Whitespace normalization
    s = TRAILING_WS_RE.sub("", s)
    s = MULTI_BLANK_RE.sub("\n\n", s)
    s = s.strip() + "\n"

    return s


def sanitization_sha256() -> str:
    """SHA-256 of this module's source code.

    Recorded in every calibration and trial artifact so a post-hoc reviewer
    can verify the sanitizer-in-effect at the time of run.
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
`{loops.flight}` per the architecture invariants. See entities.cards.ember_strike
for the affected card. Per section 4.7, distributions follow the pinned PRNG.

<<< FILE: gdd/mechanics.md >>>
...
<<< END FILE: gdd/mechanics.md >>>


## Schema

As the design document says, the cost is 1 ember.

## My Implementation Notes

(Non-canonical heading — should lose `##` prefix, keep text.)


## Rationale

Wall kicks are committed actions. Per the invariants, no undo.
"""

    # v11 rule 9 self-test: content-entity YAML format (per spec §6.2)
    # carries the same spec-metadata fields *unfenced* — must also be
    # stripped to close the blinding-leak Phase-2 leak the v9 sanitizer
    # missed.
    sample_unfenced = """```yaml
spec: game-design.md
spec_version: 0.2.0-alpha
file_type: content-entity
id: fault_lines_07_the_chasm
status: draft
implemented_in: ["src/levels/fault_lines/07.py"]
name: "The Chasm"
region: fault_lines
difficulty_tier: 3
platforms:
  - { x: 500, y: 19500, width: 2500, status: stable }
```
"""

    print("--- RAW (fenced) ---")
    print(sample)
    print(f"--- SANITIZED (SHA={sanitization_sha256()[:16]}) ---")
    print(sanitize_output(sample))
    print("--- idempotency check ---")
    once = sanitize_output(sample)
    twice = sanitize_output(once)
    print(f"sanitize(once) == sanitize(twice): {once == twice}")
    print()
    print("--- RAW (unfenced content-entity YAML, v11 rule 9 case) ---")
    print(sample_unfenced)
    print("--- SANITIZED ---")
    print(sanitize_output(sample_unfenced))
