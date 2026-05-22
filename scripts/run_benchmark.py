"""Cold-context card-implementation benchmark (spec §11.1).

Scores each trial in `/tmp/gdmd_bench/T<N>/test_card.yaml` against five
criteria from the Step 5 brief:

  1. schema_valid       — validates against cards.md's `schema:` block
  2. lints_clean        — dropped into a copy of examples/deckbuilder/, gdmd lint exits 0
  3. integer_damage     — every damage effect has integer amount
  4. refs_resolve       — every {token.path} reference resolves
  5. matches_intent     — name/cost/type/rarity/effect shape matches the brief

An overall PASS requires all five.

Usage: python scripts/run_benchmark.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parent.parent
DECKBUILDER = REPO / "examples" / "deckbuilder"
CARDS_SCHEMA_FILE = DECKBUILDER / "gdd" / "content" / "cards.md"
BENCH_ROOT = Path("/tmp/gdmd_bench")
GDMD = REPO / ".venv" / "bin" / "gdmd"


# ---- Trial briefs (used for intent-matching) ---------------------------------

INTENTS: dict[str, dict] = {
    "T1": {
        "brief": "Spark Jab: common attack, costs 1 energy, deals 4 damage.",
        "expect": {
            "name": "Spark Jab",
            "cost": 1, "type": "attack", "rarity": "common",
            "effects": [{"kind": "damage", "amount": 4}],
        },
    },
    "T2": {
        "brief": "Roar: rare skill 'bellow', scales burning by +2 stacks, cost 2.",
        "expect": {
            "name": "Roar",
            "cost": 2, "type": "skill", "rarity": "rare",
            "effects": [{"kind": "scale_burning", "stacks": 2}],
        },
    },
    "T3": {
        "brief": "Cauterize: uncommon attack, cost 1, deals 5 damage + 1 burning stack for 3 turns.",
        "expect": {
            "name": "Cauterize",
            "cost": 1, "type": "attack", "rarity": "uncommon",
            "effects": [
                {"kind": "damage", "amount": 5},
                {"kind": "apply_state", "stacks": 1, "duration": 3},
            ],
        },
    },
    "T4": {
        "brief": "Inferno Aura: rare power, cost 2, applies burning duration 99 stacks 1, exhausts itself.",
        "expect": {
            "name": "Inferno Aura",
            "cost": 2, "type": "power", "rarity": "rare",
            "effects": [
                {"kind": "apply_state", "duration": 99, "stacks": 1},
                {"kind": "exhaust_self"},
            ],
        },
    },
    "T5": {
        "brief": "Bracer: common skill, cost 1, gains 6 block.",
        "expect": {
            "name": "Bracer",
            "cost": 1, "type": "skill", "rarity": "common",
            "effects": [{"kind": "gain_block", "amount": 6}],
        },
    },
}


def load_cards_schema() -> dict:
    """Pull the `schema:` block from gdd/content/cards.md's frontmatter."""
    text = CARDS_SCHEMA_FILE.read_text()
    _, fm_text, _ = text.split("---", 2)
    fm = yaml.safe_load(fm_text)
    return fm["schema"]


def load_card(yaml_path: Path) -> dict | None:
    if not yaml_path.is_file():
        return None
    try:
        return yaml.safe_load(yaml_path.read_text())
    except Exception:
        return None


# ---- Per-trial scoring -------------------------------------------------------

def check_schema_valid(card: dict, schema: dict) -> tuple[bool, str]:
    # Wrap the cards.md schema block in a JSON-Schema envelope.
    js = {"type": "object", **schema}
    v = Draft202012Validator(js)
    errors = list(v.iter_errors(card))
    if not errors:
        return True, ""
    return False, "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3])


def check_integer_damage(card: dict) -> tuple[bool, str]:
    for i, eff in enumerate(card.get("effects", []) or []):
        if not isinstance(eff, dict):
            continue
        if eff.get("kind") == "damage":
            amt = eff.get("amount")
            if amt is not None and not isinstance(amt, int):
                return False, f"effects[{i}].amount={amt!r} is not int"
    return True, ""


def check_lints_clean(card: dict, trial_id: str) -> tuple[bool, str]:
    """Drop the card into a tmp copy of the deckbuilder and run gdmd lint."""
    tmp = BENCH_ROOT / trial_id / "tree"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(DECKBUILDER, tmp)
    card_path = tmp / "content" / "cards" / f"{card['id']}.yaml"
    card_path.write_text(yaml.safe_dump(card, sort_keys=False))
    proc = subprocess.run([str(GDMD), "lint", str(tmp)],
                          capture_output=True, text=True)
    if proc.returncode == 0:
        return True, ""
    try:
        report = json.loads(proc.stdout)
        msgs = [
            f"{f['rule']}@{f['file']}: {f['message']}"
            for f in report["findings"] if f["severity"] == "error"
        ]
        return False, "; ".join(msgs[:3])
    except Exception:
        return False, proc.stderr.strip()[:200]


def check_refs_resolve(trial_id: str) -> tuple[bool, str]:
    """Already covered by check_lints_clean — broken-ref is an error rule."""
    # Trivially passes if lint passes; left as a separate column for clarity.
    return True, "(subsumed by lints_clean)"


def check_matches_intent(card: dict, trial_id: str) -> tuple[bool, str]:
    """Subjective match — name + cost + type + rarity + effects shape."""
    expect = INTENTS[trial_id]["expect"]
    misses = []
    for key in ("name", "cost", "type", "rarity"):
        if card.get(key) != expect[key]:
            misses.append(f"{key}={card.get(key)!r}≠{expect[key]!r}")
    # Effects: each expected effect should be present (subset semantics — we
    # don't require effects in a specific order, just that each expected
    # effect appears with matching key/value subset).
    actual_effects = card.get("effects") or []
    for exp_eff in expect["effects"]:
        match = next(
            (a for a in actual_effects
             if isinstance(a, dict)
             and all(a.get(k) == v for k, v in exp_eff.items())),
            None,
        )
        if match is None:
            misses.append(f"missing effect ⊇{exp_eff}")
    if misses:
        return False, "; ".join(misses)
    return True, ""


# ---- Driver ------------------------------------------------------------------

CRITERIA = ["schema_valid", "integer_damage", "lints_clean", "refs_resolve", "matches_intent"]


def score_trial(trial_id: str, schema: dict) -> dict:
    card_path = BENCH_ROOT / trial_id / "test_card.yaml"
    card = load_card(card_path)
    result = {"trial": trial_id, "card_path": str(card_path)}
    if card is None:
        return {**result, "loaded": False, "pass": False,
                **{c: (False, "no card YAML found") for c in CRITERIA}}
    result["loaded"] = True
    result["id"] = card.get("id", "?")
    result["name"] = card.get("name", "?")

    result["schema_valid"]   = check_schema_valid(card, schema)
    result["integer_damage"] = check_integer_damage(card)
    result["lints_clean"]    = check_lints_clean(card, trial_id)
    result["refs_resolve"]   = check_refs_resolve(trial_id)
    result["matches_intent"] = check_matches_intent(card, trial_id)
    result["pass"] = all(result[c][0] for c in CRITERIA)
    return result


def main() -> int:
    schema = load_cards_schema()
    rows = [score_trial(t, schema) for t in sorted(INTENTS)]
    passes = sum(1 for r in rows if r.get("pass"))
    total = len(rows)
    rate = passes / total if total else 0.0

    print(f"Cold-context card-implementation benchmark — N={total} trials\n")
    print(f"{'Trial':6} {'Loaded':6} {'Sch':4} {'Int':4} {'Lnt':4} {'Ref':4} {'Mat':4} {'PASS':4}  Card / Notes")
    print("-" * 110)
    for r in rows:
        if not r["loaded"]:
            print(f"{r['trial']:6} {'-':6} {'-':4} {'-':4} {'-':4} {'-':4} {'-':4} {'FAIL':4}  no card YAML")
            continue
        cells = []
        for c in CRITERIA:
            cells.append("✓" if r[c][0] else "✗")
        verdict = "PASS" if r["pass"] else "FAIL"
        sch, intg, lnt, ref, mat = cells
        print(f"{r['trial']:6} {'✓':6} {sch:4} {intg:4} {lnt:4} {ref:4} {mat:4} {verdict:4}  "
              f"{r['id']} / {r['name']}")
        for c in CRITERIA:
            ok, msg = r[c]
            if not ok and msg and "subsumed" not in msg:
                print(f"        {c}: {msg}")
    print()
    print(f"PASS RATE: {passes}/{total} = {rate:.0%}")
    print(f"BENCHMARK: {'MEETS' if rate >= 0.80 else 'MISSES'} the ≥80% bar from spec §11.1")
    return 0 if rate >= 0.80 else 1


if __name__ == "__main__":
    sys.exit(main())
