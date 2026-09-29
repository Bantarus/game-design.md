"""Step 4 — fairness audit on flattened B briefs (pre-reg §B-construction Layer 3).

Runs the auxiliary LLM judge against each fresh game's flattened B brief
to check that the flattener produces a *fair* prose summary, not a
strawman. The flattener's SHA is frozen for trial use ONLY at score ≥ 4
on both games (per pre-reg `fairness_audit_prompt.md`).

Run:
  python -m benchmark.tools.run_fairness_audit
  # or, restricted to one game:
  python -m benchmark.tools.run_fairness_audit --game platformer

Outputs per game:
  benchmark/harness/audits/<game>_fairness_audit_<timestamp>.json
    { judge_bundle, flattener_sha, prompt_sha, brief_sha,
      game_name, game_pitch, audited_text_first_500, judge_output, pass }

Plus a console summary + final `flattener_sha_frozen` line if both
games pass (the SHA to record in the harness-build commit / pre-reg's
B-construction lock).

Pre-reg discipline backstop:
- Judge bundle: GEMMA_JUDGE_BUNDLE from harness/judge.py — pinned at the
  harness-build commit, reasoning-off; validated for discrimination via
  a Phase-A-style mini check before this driver ran (see commit message).
- Prompt template: benchmark/tools/fairness_audit_prompt.md — frozen,
  SHA recorded in each artifact.
- Pass threshold: 4 (per the prompt's rubric).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from benchmark.harness.judge import (
    GemmaJudge,
    GEMMA_JUDGE_BUNDLE,
    Judge,
)
from benchmark.tools.flattener import flatten_tree


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GAMES_DIR = REPO_ROOT / "benchmark" / "games"
AUDITS_DIR = REPO_ROOT / "benchmark" / "harness" / "audits"
FLATTENER_PATH = REPO_ROOT / "benchmark" / "tools" / "flattener.py"
PROMPT_PATH = REPO_ROOT / "benchmark" / "tools" / "fairness_audit_prompt.md"

PASS_THRESHOLD = 4


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _load_game_meta(game: str) -> tuple[str, str]:
    """Read the game's root game-design.md frontmatter for name + short_pitch.

    Returns (name, short_pitch). Falls back to game-id if frontmatter
    can't be parsed.
    """
    root = GAMES_DIR / game / "game-design.md"
    if not root.exists():
        return (game, "")
    import yaml
    text = root.read_text()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
                return (fm.get("name", game), fm.get("short_pitch", ""))
            except Exception:
                pass
    return (game, "")


def audit_one(judge: Judge, game: str) -> dict:
    """Audit one game's flattened B brief. Returns the artifact dict."""
    tree_root = GAMES_DIR / game
    if not tree_root.exists():
        raise FileNotFoundError(f"Game tree not found: {tree_root}")

    flattened = flatten_tree(tree_root)
    brief_sha = _sha256_bytes(flattened.encode("utf-8"))
    flattener_sha = _sha256(FLATTENER_PATH)
    prompt_sha = _sha256(PROMPT_PATH)

    name, pitch = _load_game_meta(game)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    print(f"[+] {game}: flattening tree at {tree_root}", file=sys.stderr)
    print(f"[+] {game}: flattened brief: {len(flattened):,} bytes "
          f"(sha {brief_sha[:12]}...)", file=sys.stderr)
    print(f"[+] {game}: name={name!r} pitch={pitch[:60]!r}", file=sys.stderr)
    print(f"[+] {game}: auditing via judge {judge.bundle.bundle_id()}...", file=sys.stderr)

    t0 = time.monotonic()
    result = judge.audit_fairness(
        flattened_b_text=flattened,
        game_name=name,
        game_pitch=pitch,
    )
    wall = time.monotonic() - t0
    print(f"[+] {game}: score={result.score}/5  wall={wall:.1f}s", file=sys.stderr)

    artifact = {
        "step": "B-construction Layer 3 fairness audit",
        "game": game,
        "game_name": name,
        "game_pitch": pitch,
        "timestamp": timestamp,
        "judge_bundle_id": judge.bundle.bundle_id(),
        "flattener_path": str(FLATTENER_PATH.relative_to(REPO_ROOT)),
        "flattener_sha256": flattener_sha,
        "prompt_template_path": str(PROMPT_PATH.relative_to(REPO_ROOT)),
        "prompt_template_sha256": prompt_sha,
        "brief_sha256": brief_sha,
        "brief_length_bytes": len(flattened.encode("utf-8")),
        "audited_text_first_500": flattened[:500],
        "judge_output": {
            "score": result.score,
            "rationale": result.rationale,
            "specific_issues": list(result.specific_issues),
        },
        "pass_threshold": PASS_THRESHOLD,
        "passes": result.score >= PASS_THRESHOLD,
        "wall_clock_seconds": wall,
    }
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--game",
        action="append",
        choices=["platformer", "survival"],
        help="Game(s) to audit (repeat for multiple; default: both).",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print artifacts to stdout instead of writing to "
             "benchmark/harness/audits/.",
    )
    args = parser.parse_args(argv)

    games = args.game or ["platformer", "survival"]

    AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    artifacts: list[dict] = []
    with GemmaJudge(GEMMA_JUDGE_BUNDLE) as judge:
        for game in games:
            art = audit_one(judge, game)
            artifacts.append(art)
            if args.no_write:
                print(json.dumps(art, indent=2))
            else:
                out_path = AUDITS_DIR / f"{game}_fairness_audit_{art['timestamp']}.json"
                out_path.write_text(json.dumps(art, indent=2))
                print(f"[+] {game}: wrote {out_path.relative_to(REPO_ROOT)}",
                      file=sys.stderr)

    # Summary
    print("", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print("FAIRNESS AUDIT SUMMARY", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    for art in artifacts:
        verdict = "PASS" if art["passes"] else "FAIL"
        print(f"  {art['game']:<12} score={art['judge_output']['score']}/5  "
              f"[{verdict}]   issues={len(art['judge_output']['specific_issues'])}",
              file=sys.stderr)

    all_pass = all(art["passes"] for art in artifacts)
    if all_pass and len(artifacts) == 2:
        # Both games audited and both passed — emit the flattener SHA
        # to record in the harness-build / pre-reg lock.
        flattener_sha = artifacts[0]["flattener_sha256"]
        # Sanity: both artifacts should reference the same flattener SHA
        # (they computed it from the same file).
        assert all(a["flattener_sha256"] == flattener_sha for a in artifacts), (
            "Flattener SHA mismatch across artifacts — concurrent edit?"
        )
        print("", file=sys.stderr)
        print(f"FLATTENER SHA (frozen for trial use): {flattener_sha}",
              file=sys.stderr)
        print("Record this in the harness-build commit + pre-reg's "
              "B-construction lock.", file=sys.stderr)
        return 0
    elif all_pass:
        print("", file=sys.stderr)
        print("Subset audit passed; full freeze requires both games.",
              file=sys.stderr)
        return 0
    else:
        print("", file=sys.stderr)
        print("AT LEAST ONE GAME FAILED. Revise the flattener and re-audit.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
