#!/usr/bin/env python3
"""Checker for tasks/authoring_new_card.md (the spec §11.1 benchmark shape).

Success: exactly one new card, content/cards/kindle.yaml, that validates
against the tree's card content-schema, matches the brief field-for-field, is
`draft` (no code exists), leaves every other token untouched, and the tree
lints 0/0. Lint alone isn't enough: it doesn't validate entities against their
schema (OI-005), so this checker does.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checklib as cl  # noqa: E402
import jsonschema  # noqa: E402

TREE = "examples/deckbuilder"
CARD = f"{TREE}/content/cards/kindle.yaml"
SCHEMA_FILE = f"{TREE}/gdd/content/cards.md"
EXPECTED_FIELDS = {"name": "Kindle", "cost": 1, "type": "skill", "rarity": "uncommon"}
EXPECTED_EFFECTS = [
    {"kind": "apply_state", "state": "{states.enemy_lifecycle.burning}",
     "duration": 3, "stacks": 2},
    {"kind": "gain_block", "amount": 4},
]


def main() -> None:
    a = cl.parse_args()
    r = cl.Report("authoring_new_card")
    changes = cl.changed_paths(a.root, a.base)
    r.check("card_added", changes.get(CARD) in ("A", "?"), changes.get(CARD))
    handled = cl.check_ritual_metadata(r, a.root, TREE, a.base, changes,
                                       run_date=a.run_date, check_date=a.check_date)
    unexpected = sorted(p for p in changes if p != CARD and p not in handled)
    r.check("no_unexpected_changes", not unexpected, unexpected)

    card, _ = cl.doc_at(a.root, CARD)
    if card is None:
        r.check("card_parses", False, "missing, or not a YAML mapping")
        r.finish()
    root_fm, _ = cl.doc_at(a.root, f"{TREE}/game-design.md", a.base)
    header = {k: card.get(k) for k in ("spec", "spec_version", "file_type", "id")}
    r.check("entity_header", header == {
        "spec": "game-design.md", "spec_version": root_fm.get("spec_version"),
        "file_type": "content-entity", "id": Path(CARD).stem,
    }, header)
    r.check("status_draft", card.get("status") == "draft", card.get("status"))
    r.check("implemented_in_is_list", isinstance(card.get("implemented_in"), list),
            card.get("implemented_in"))
    schema_fm, _ = cl.doc_at(a.root, SCHEMA_FILE, a.base)
    errors = sorted(e.message for e in
                    jsonschema.Draft202012Validator(schema_fm["schema"]).iter_errors(card))
    r.check("validates_against_schema", not errors, errors[:10])
    fields = {k: card.get(k) for k in EXPECTED_FIELDS}
    r.check("fields_match_brief", fields == EXPECTED_FIELDS, fields)
    r.check("effects_match_brief", card.get("effects") == EXPECTED_EFFECTS, card.get("effects"))
    r.lint_clean(a.root, TREE)
    r.finish()


if __name__ == "__main__":
    main()
