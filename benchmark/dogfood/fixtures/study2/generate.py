#!/usr/bin/env python3
"""Study-2 fixture generator (D-026): the "Lanternfall" tree, its planted
reference graph, the six task prompts, the fixture patches and the frozen
answers.

    python generate.py            # (re)write the frozen output next to this file
    python generate.py --check    # regenerate in memory; exit 1 if the frozen output differs
    python generate.py --leaks    # the D-026 §7 leak check against this repository

Deterministic (D-026 §5): seed 20260930, fixed word lists, no wall-clock
input, no dependency on the repository's state. Every `{ns.id}` reference in
a YAML value is written through `Gen.ref`, which records it in the planted
edge list (`edges.json`). The answers are computed from that list alone,
never by parsing the tree with `gdmd` code (D-026 §8, the frozen-fixtures
rule); `tests/test_dogfood_study2.py` cross-checks them once against
`gdmd graph` / `gdmd view` and `refs.walk_refs`.

Output (relative to this directory):
    tree/              the tree; fixture.py places it at examples/lanternfall/ in each copy
    prompts/<task>.md  the task prompts, given to the subject verbatim
    patches/<task>.patch   teammate commits for the two guarded tasks
    answers/<task>.json    frozen answers (with each question's parameters)
    edges.json         the planted edge list
"""
from __future__ import annotations

import argparse
import difflib
import json
import random
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

SEED = 20260930
HERE = Path(__file__).resolve().parent
PLACED_AT = "examples/lanternfall"
SPEC_VERSION = "0.3.0"
# Copies normalize every mtime to 2026-05-01 (fixture.FIXTURE_MTIME), and
# stale-section fires when an implementation file is > 30 days newer than
# last_verified. Prototyped files are verified a week before that date, so a
# fresh copy lints clean and the maintenance patch (a fresh mtime) is stale.
LV_DRAFT = "2026-04-18"
LV_PROTO = "2026-04-24"
LAST_UPDATED = "2026-04-24"

KINDS = {"items": 140, "skills": 90, "monsters": 60, "encounters": 30}
ADJS = ["ashen", "barrow", "briny", "candle", "dusk", "fen", "gloam", "grave", "hollow",
        "iron", "knell", "lich", "moth", "murk", "ochre", "pale", "rust", "sable", "soot",
        "tallow", "umber", "vesper", "wick", "yew"]
ITEM_NOUNS = ["buckler", "censer", "dirk", "flask", "gauntlet", "hood", "lens", "mantle",
              "phial", "ring", "sigil", "torc", "charm", "brand"]
SKILL_NOUNS = ["bolt", "chant", "cleave", "hex", "lash", "pulse", "rite", "snare", "veil",
               "ward", "wail", "sear"]
MONSTER_NOUNS = ["crawler", "ghoul", "hound", "husk", "lurker", "mite", "revenant", "shade",
                 "stalker", "wight", "wisp", "drudge"]
ENCOUNTER_NOUNS = ["alcove", "barrow", "crypt", "den", "gallery", "hollow", "nave",
                   "ossuary", "pit", "vault", "warren"]
BOSSES = {"lamp_warden": 3, "knell_mother": 4, "soot_king": 5}
SANCTUM = "soot_sanctum"
ROLLS = ["ashveil_roll", "barrowchill_roll", "candlegrit_roll", "duskbite_roll",
         "fenmurk_roll", "gravetide_roll", "hollowknell_roll", "ironsap_roll",
         "lichwick_roll", "mothglow_roll", "nightbrine_roll", "ossuary_dust_roll",
         "palecoil_roll", "rustmire_roll", "sablegleam_roll", "tallowgrin_roll"]
# Fan-in weights for the rolls beyond the first skill each (varied on purpose:
# some rolls are rare, some common).
ROLL_WEIGHTS = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10]
PACK_BY_DEPTH = {1: ["shallows_pack"], 2: ["gallery_pack", "ossuary_pack"],
                 3: ["undercroft_pack"], 4: ["deepvault_pack"], 5: ["sanctum_pack"]}
AFFLICTIONS = {"chilled": "chill_applied", "hexed": "hex_applied",
               "bleeding": "wound_opened", "dazed": "daze_applied"}
SCHOOLS = ["lumen", "umbral", "iron", "brine"]
RARITIES = ["worn", "sound", "gleaming", "relic"]
SLOTS = ["lantern", "weapon", "ward", "trinket", "tonic"]
TIERS = {"minion": (8, 50), "brute": (22, 35), "elite": (38, 15)}   # base vigor, weight

ITEM_PHRASES = ["scorched black on the rim", "wrapped in grave-linen", "that hums near open flame",
                "etched with a drowned saint's mark", "that smells of old tallow",
                "cold even in the lamplight", "stitched from moth-silk",
                "pitted by the brine seeps", "that remembers its last owner",
                "with a wick-cut groove along one edge"]
SKILL_PHRASES = ["the dark leans away from it", "it costs a breath of lamp-smoke",
                 "it leaves frost on the caster's teeth", "the flame gutters as it lands",
                 "it echoes down the stair", "it is learned from a knell-bell's crack"]
MONSTER_PHRASES = ["hunts by the sound of a trimmed wick", "sleeps in cold ash",
                   "follows the smell of lamp oil", "avoids direct light",
                   "gathers where the stairs turn", "wears the rags of lamplighters"]
ENCOUNTER_PHRASES = ["a low room where the lantern throws long shadows",
                     "a flooded passage with a single dry ledge",
                     "an ossuary shelf that shifts when touched",
                     "a stair landing littered with snuffed candles",
                     "a gallery of cracked knell-bells", "a warren of burrows in the soot"]


class BuildError(RuntimeError):
    pass


# ---- a small YAML emitter (the hand-authored trees' style) ---------------------------

class Flow(dict):
    """Emit this mapping in flow style: `{ a: 1, b: "x" }`."""


class FlowList(list):
    """Emit this list in flow style: `[a, "b/c"]`."""


_PLAIN = re.compile(r"^(?:[A-Za-z_.][A-Za-z0-9_ .,()'/-]*|\d+\.\d+\.\d+)$")
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n"}


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def scalar(v, flow: bool = False) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if s.lower() in _RESERVED:
        return _quote(s)
    if flow:
        return s if _IDENT.match(s) else _quote(s)
    return s if _PLAIN.match(s) and not s.endswith(" ") else _quote(s)


def _flow(v) -> str:
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k}: {_flow(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_flow(x) for x in v) + "]"
    return scalar(v, flow=True)


def emit(obj: dict, indent: int = 0) -> list[str]:
    pad = " " * indent
    out: list[str] = []
    for k, v in obj.items():
        if isinstance(v, (Flow, FlowList)):
            out.append(f"{pad}{k}: {_flow(v)}")
        elif isinstance(v, dict):
            out.append(f"{pad}{k}:" if v else f"{pad}{k}: {{}}")
            out += emit(v, indent + 2)
        elif isinstance(v, list):
            if not v:
                out.append(f"{pad}{k}: []")
            else:
                out.append(f"{pad}{k}:")
                out += emit_list(v, indent + 2)
        else:
            out.append(f"{pad}{k}: {scalar(v)}")
    return out


def emit_list(items: list, indent: int) -> list[str]:
    pad = " " * indent
    out: list[str] = []
    for it in items:
        if isinstance(it, (Flow, FlowList)):
            out.append(f"{pad}- {_flow(it)}")
        elif isinstance(it, dict):
            sub = emit(it, indent + 2)
            sub[0] = f"{pad}- " + sub[0].lstrip()
            out += sub
        else:
            out.append(f"{pad}- {scalar(it)}")
    return out


def md(frontmatter: dict, body: str) -> str:
    return "---\n" + "\n".join(emit(frontmatter)) + "\n---\n\n" + body.strip("\n") + "\n"


def yaml_doc(doc: dict) -> str:
    return "\n".join(emit(doc)) + "\n"


def a_(word: str) -> str:
    return ("an " if word[0] in "aeiou" else "a ") + word


def title(ident: str) -> str:
    return " ".join(w.capitalize() for w in ident.split("_"))


# ---- the planted graph ------------------------------------------------------------

@dataclass(frozen=True)
class Edge:
    src: str    # "ns.id", "entities.<kind>.<id>", or "meta:<path>" (a file-level value)
    dst: str    # the token the reference resolves to (its longest registered prefix)
    ref: str    # the text inside the braces
    path: str   # tree-relative file carrying it


def is_content(node: str) -> bool:
    parts = node.split(".")
    return len(parts) == 3 and parts[0] == "entities" and parts[1] in KINDS


class Gen:
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.edges: list[Edge] = []
        self.files: dict[str, str] = {}          # tree-relative path -> text
        self.node_file: dict[str, str] = {}      # node -> defining file
        self.subfiles: list[str] = []
        self.file_impl: dict[str, list[str]] = {}          # subfile -> file-level globs
        self.token_impl: dict[str, tuple[str, list[str]]] = {}  # token -> (file, globs)
        self.root_pointers: dict[str, str] = {}

    # -- references -------------------------------------------------------------------

    def ref(self, src: str, dst: str, path: str, sub: str | None = None) -> str:
        text = dst + (f".{sub}" if sub else "")
        self.edges.append(Edge(src, dst, text, path))
        return "{" + text + "}"

    def refs(self, src: str, dsts: list[str], path: str) -> list[str]:
        return [self.ref(src, d, path) for d in dsts]

    def define(self, node: str, path: str) -> None:
        if node in self.node_file:
            raise BuildError(f"{node} defined twice")
        self.node_file[node] = path

    def impl(self, token: str, path: str, globs: list[str]) -> FlowList:
        self.token_impl[token] = (path, list(globs))
        return FlowList(globs)

    # -- ids ----------------------------------------------------------------------------

    def names(self, nouns: list[str], n: int, taken: set[str]) -> list[str]:
        combos = [f"{a}_{b}" for a in ADJS for b in nouns if a != b and f"{a}_{b}" not in taken]
        self.rng.shuffle(combos)
        out = sorted(combos[:n])
        taken.update(out)
        return out

    # -- content ------------------------------------------------------------------------

    def content(self) -> None:
        rng = self.rng
        taken: set[str] = set()
        self.items = self.names(ITEM_NOUNS, KINDS["items"], taken)
        self.skills = self.names(SKILL_NOUNS, KINDS["skills"], taken)
        self.regular = self.names(MONSTER_NOUNS, KINDS["monsters"] - len(BOSSES), taken)
        self.monsters = sorted(self.regular + list(BOSSES))
        regular_enc = self.names(ENCOUNTER_NOUNS, KINDS["encounters"] - 1, taken)
        self.encounters = sorted(regular_enc + [SANCTUM])

        self.skill: dict[str, dict] = {}
        order = self.skills[:]
        rng.shuffle(order)
        for i, s in enumerate(order):
            roll = ROLLS[i] if i < len(ROLLS) else rng.choices(ROLLS, ROLL_WEIGHTS)[0]
            inflicts = rng.choice(sorted(AFFLICTIONS)) if rng.random() < 0.4 else None
            self.skill[s] = {"school": rng.choice(SCHOOLS), "focus_cost": rng.randint(1, 6),
                             "roll": roll, "inflicts": inflicts,
                             "phrase": rng.choice(SKILL_PHRASES)}

        self.item: dict[str, dict] = {}
        for it in self.items:
            rarity = rng.choices(RARITIES, [50, 30, 15, 5])[0]
            grants = rng.choice(self.skills) if rng.random() < 0.35 else None
            self.item[it] = {"rarity": rarity, "slot": rng.choice(SLOTS),
                             "weight": rng.randint(1, 8),
                             "value": {"worn": 5, "sound": 20, "gleaming": 60, "relic": 150}[rarity]
                             + rng.randint(0, 20),
                             "grants": grants, "phrase": rng.choice(ITEM_PHRASES)}

        self.monster: dict[str, dict] = {}
        for m in self.regular:
            tier = rng.choices(list(TIERS), [w for _, w in TIERS.values()])[0]
            self.monster[m] = {"tier": tier, "vigor": TIERS[tier][0] + rng.randint(0, 10),
                               "skills": sorted(rng.sample(self.skills, rng.choice([1, 2]))),
                               "drops": sorted(rng.sample(self.items, rng.randint(1, 3))),
                               "phrase": rng.choice(MONSTER_PHRASES)}
        relics = [i for i in self.items if self.item[i]["rarity"] in ("gleaming", "relic")]
        for b in sorted(BOSSES):
            self.monster[b] = {"tier": "boss", "vigor": 90 + 30 * BOSSES[b],
                               "skills": sorted(rng.sample(self.skills, 2)),
                               "drops": sorted(rng.sample(relics, 3)),
                               "phrase": rng.choice(MONSTER_PHRASES)}

        # Encounters: every regular monster appears at least once (a shuffled
        # deck, refilled when empty), 2-4 distinct monsters each.
        shuffled = regular_enc[:]
        rng.shuffle(shuffled)
        depth = {e: 1 + (i * 4) // len(shuffled) for i, e in enumerate(shuffled)}
        deck: list[str] = []
        self.encounter: dict[str, dict] = {}
        for e in regular_enc:
            k, chosen = rng.randint(2, 4), []
            while len(chosen) < k:
                if not deck:
                    deck = self.regular[:]
                    rng.shuffle(deck)
                m = deck.pop()
                if m in chosen:
                    deck.insert(0, m)
                    continue
                chosen.append(m)
            self.encounter[e] = {"depth": depth[e], "monsters": sorted(chosen),
                                 "pack": rng.choice(PACK_BY_DEPTH[depth[e]]),
                                 "phrase": rng.choice(ENCOUNTER_PHRASES)}
        # One lair per spawnable boss, at the boss's depth; the sanctum holds the last.
        for b, d in sorted(BOSSES.items()):
            if d == 5:
                continue
            lair = sorted(e for e in regular_enc if depth[e] == d)[0]
            ms = self.encounter[lair]["monsters"]
            self.encounter[lair]["monsters"] = sorted(ms[:3] + [b])
        guards = sorted(m for m in self.regular if self.monster[m]["tier"] == "elite")[:2]
        self.encounter[SANCTUM] = {"depth": 5, "monsters": sorted(guards + ["soot_king"]),
                                   "pack": "sanctum_pack", "phrase": ENCOUNTER_PHRASES[3]}
        if not any(v["pack"] == "ossuary_pack" for v in self.encounter.values()):
            first = sorted(e for e in regular_enc if depth[e] == 2)[0]
            self.encounter[first]["pack"] = "ossuary_pack"

    def write_content(self) -> None:
        for it in self.items:
            node, path = f"entities.items.{it}", f"content/items/{it}.yaml"
            self.define(node, path)
            a = self.item[it]
            doc = self._entity_head(it)
            doc.update({"name": title(it), "rarity": a["rarity"], "slot": a["slot"],
                        "weight": a["weight"], "value": a["value"]})
            if a["grants"]:
                doc["grants"] = self.ref(node, f"entities.skills.{a['grants']}", path)
            doc["description"] = f"{a_(a['rarity']).capitalize()} {a['slot']} {a['phrase']}."
            self.files[path] = yaml_doc(doc)
        for s in self.skills:
            node, path = f"entities.skills.{s}", f"content/skills/{s}.yaml"
            self.define(node, path)
            a = self.skill[s]
            doc = self._entity_head(s)
            doc.update({"name": title(s), "school": a["school"], "focus_cost": a["focus_cost"],
                        "roll": self.ref(node, f"distributions.{a['roll']}", path)})
            if a["inflicts"]:
                doc["inflicts"] = self.ref(node, "states.affliction", path, a["inflicts"])
            doc["description"] = f"{a_(a['school']).capitalize()} {s.split('_')[-1]}; {a['phrase']}."
            self.files[path] = yaml_doc(doc)
        for m in self.monsters:
            node, path = f"entities.monsters.{m}", f"content/monsters/{m}.yaml"
            self.define(node, path)
            a = self.monster[m]
            doc = self._entity_head(m)
            doc.update({"name": title(m), "tier": a["tier"], "max_vigor": a["vigor"],
                        "skills": self.refs(node, [f"entities.skills.{x}" for x in a["skills"]],
                                            path),
                        "drops": self.refs(node, [f"entities.items.{x}" for x in a["drops"]],
                                           path),
                        "description": f"{a_(a['tier']).capitalize()} that {a['phrase']}."})
            self.files[path] = yaml_doc(doc)
        for e in self.encounters:
            node, path = f"entities.encounters.{e}", f"content/encounters/{e}.yaml"
            self.define(node, path)
            a = self.encounter[e]
            doc = self._entity_head(e)
            doc.update({"name": title(e), "depth": a["depth"],
                        "monsters": self.refs(node, [f"entities.monsters.{x}"
                                                     for x in a["monsters"]], path),
                        "spawn_roll": self.ref(node, f"distributions.{a['pack']}", path),
                        "description": f"{title(e)}: {a['phrase']}."})
            self.files[path] = yaml_doc(doc)

    @staticmethod
    def _entity_head(ident: str) -> dict:
        return {"spec": "game-design.md", "spec_version": SPEC_VERSION,
                "file_type": "content-entity", "id": ident, "status": "draft",
                "last_verified": LV_DRAFT, "implemented_in": FlowList([])}

    # -- subfiles -----------------------------------------------------------------------

    def subfile(self, path: str, status: str, globs: list[str] | None, tokens: dict,
                body: str) -> None:
        fm = {"spec": "game-design.md", "spec_version": SPEC_VERSION, "file_type": "subfile",
              "status": status, "last_verified": LV_PROTO if status == "prototyped" else LV_DRAFT}
        if globs:
            fm["implemented_in"] = FlowList(globs)
            self.file_impl[path] = list(globs)
        fm.update(tokens)
        self.subfiles.append(path)
        self.files[path] = md(fm, body)

    def tokens(self) -> None:
        self.pillars()
        self.mechanics()
        self.loops()
        self.clocks()
        self.distributions()
        self.spawning()
        self.bosses()
        self.loot()
        self.combat()
        self.lantern()
        self.balance()
        self.feel()
        self.invariants()
        self.glossary()
        self.content_index()
        self.content_schemas()
        self.core()

    def pillars(self) -> None:
        self.subfile("gdd/pillars.md", "draft", None, {
            "pillars": ["Light is the only currency that matters",
                        "Every floor is a readable risk",
                        "Loot tells you what the dark is hiding"],
            "non_goals": ["Multiplayer", "Real-time twitch combat", "Procedural narrative"],
        }, """
## Tokens

Three pillars and three non-goals, mirrored in the root file. Any change here is a major-version bump.

## Rationale

**Light is the only currency.** Every action burns lantern oil, so the question on each floor is never "can I win this fight" but "is this fight worth the oil". Coin and loot matter only because they buy more light.

**Readable risk.** An encounter's depth, pack and inhabitants are all knowable before the lamplighter commits. Surprise comes from the wandering spawns a guttering lantern invites, never from hidden numbers.

**Loot tells you what the dark is hiding.** What a monster drops says where it has been. A drop table is a map for players who read it.
""")

    def mechanics(self) -> None:
        p = "gdd/mechanics.md"
        L = "entities.lamplighter"
        for n in ("entities.lamplighter", "entities.items", "entities.skills", "entities.monsters",
                  "entities.encounters", "entities.satchel"):
            self.define(n, p)
        entities = {
            "lamplighter": {
                "type": "actor",
                "properties": {
                    "vigor": Flow({"from": self.ref(L, "resources.vigor", p)}),
                    "ward_focus": Flow({"from": self.ref(L, "resources.ward_focus", p)}),
                    "lantern_oil": Flow({"from": self.ref(L, "resources.lantern_oil", p)}),
                    "grave_coin": Flow({"from": self.ref(L, "resources.grave_coin", p)}),
                    "load": Flow({"from": self.ref(L, "resources.satchel_load", p)}),
                    "satchel": Flow({"from": self.ref(L, "entities.satchel", p)}),
                    "might": 3,
                },
                "status": "draft",
                "implemented_in": self.impl(L, p, ["impl/lanternfall/core/lamplighter.py"]),
            },
            **{k: {"type": "content_collection", "data_source": f"../../content/{k}",
                   "count_target": n, "status": "draft"} for k, n in KINDS.items()},
            "satchel": {
                "type": "instance_container",
                "capacity": 16,
                "holds_template_from": self.ref("entities.satchel", "entities.items", p),
                "per_instance_state": {
                    "charges": Flow({"type": "integer", "minimum": 0}),
                    "wear": Flow({"type": "integer", "minimum": 0, "maximum": 5}),
                    "quantity": Flow({"type": "integer", "minimum": 1, "default": 1}),
                },
                "status": "draft",
                "implemented_in": self.impl("entities.satchel", p,
                                            ["impl/lanternfall/core/satchel.py"]),
            },
        }
        verb_specs = [
            # id, cost, target, filter, rule, feel, oil
            ("descend_stair", 0, "entities.encounters", "unexplored_stair", "spawn_encounter",
             True, 4),
            ("strike_foe", 0, "entities.monsters", "adjacent_and_revealed", "resolve_strike",
             True, 1),
            ("invoke_skill", ("resources.ward_focus", "varies_by_skill"), "entities.skills",
             "known_and_affordable", "resolve_skill", False, 1),
            ("use_relic", 0, "entities.satchel", "has_charges", "apply_relic", False, 1),
            ("loot_remains", 0, "entities.monsters", "defeated_this_floor", "roll_drops",
             False, 2),
            ("salvage_gear", 0, "entities.satchel", "worn_quality", "resolve_salvage", False, 2),
            ("trim_wick", 0, None, None, "refill_lantern", False, 0),
            ("ring_the_knell", 0, "entities.monsters.knell_mother", "at_the_bell",
             "boss_awakening", True, 3),
            ("breach_sanctum", 0, f"entities.encounters.{SANCTUM}", "all_knells_rung",
             "sanctum_trial", False, 6),
            ("flee_upward", 0, None, None, "resolve_flight", False, 8),
            ("make_camp", 0, None, None, None, False, 0),
        ]
        verbs = {}
        for vid, cost, target, filt, rule, feel, oil in verb_specs:
            v = f"verbs.{vid}"
            self.define(v, p)
            body: dict = {"actor": self.ref(v, L, p)}
            if isinstance(cost, tuple):
                body["cost"] = Flow({"resource": self.ref(v, cost[0], p), "amount": cost[1]})
            else:
                body["cost"] = cost
            if target:
                ts = {"type": self.ref(v, target, p)}
                if filt:
                    ts["filter"] = filt
                body["target_schema"] = Flow(ts)
            else:
                body["target_schema"] = Flow({"type": "system"})
            if rule:
                body["effects"] = [Flow({"resolve": self.ref(v, f"rules.{rule}", p)})]
            else:
                body["effects"] = [Flow({"kind": "restore",
                                         "resource": self.ref(v, "resources.vigor", p)})]
            if feel:
                body["feel"] = self.ref(v, f"feel.{vid}", p)
            body["oil_cost"] = oil
            body["status"] = "draft"
            body["implemented_in"] = self.impl(v, p, [f"impl/lanternfall/core/verbs/{vid}.py"])
            verbs[vid] = body
        resources = {}
        for rid, scope, lo, hi, vis, vel in [
                ("lantern_oil", "per_run", 0, 120, "hud", "oil_per_floor"),
                ("vigor", "per_run", 0, 40, "hud", None),
                ("ward_focus", "per_turn", 0, 12, "hud", None),
                ("grave_coin", "permanent", 0, 9999, "hud", "coin_per_expedition"),
                ("satchel_load", "per_run", 0, 30, "inferred", None)]:
            r = f"resources.{rid}"
            self.define(r, p)
            body = {"scope": scope, "min": lo, "max": hi}
            if vel:
                body["velocity_target"] = self.ref(r, f"balance_targets.{vel}", p)
            body.update({"visibility": vis, "status": "draft",
                         "implemented_in": self.impl(r, p, [f"impl/lanternfall/core/{rid}.py"])})
            resources[rid] = body
        for s in ("states.affliction", "states.lantern_state"):
            self.define(s, p)
        A = "states.affliction"
        aff_t = []
        for node, ev in AFFLICTIONS.items():
            aff_t.append(Flow({"from": "clear", "event": self.ref(A, f"events.{ev}", p),
                               "to": node}))
        for node in AFFLICTIONS:
            aff_t.append(Flow({"from": node, "event": self.ref(A, "events.affliction_faded", p),
                               "to": "clear"}))
        S = "states.lantern_state"
        states = {
            "affliction": {"initial": "clear",
                           "nodes": [Flow({"id": "clear"})] + [Flow({"id": n})
                                                                for n in AFFLICTIONS],
                           "transitions": aff_t},
            "lantern_state": {"initial": "lit",
                              "nodes": [Flow({"id": "lit"}), Flow({"id": "dim"}),
                                        Flow({"id": "guttered", "terminal": True})],
                              "transitions": [
                                  Flow({"from": "lit", "event": self.ref(S, "events.oil_low", p),
                                        "to": "dim"}),
                                  Flow({"from": "dim",
                                        "event": self.ref(S, "events.oil_refilled", p),
                                        "to": "lit"}),
                                  Flow({"from": "dim", "event": self.ref(S, "events.flame_out", p),
                                        "to": "guttered"})]},
        }
        event_text = {
            "chill_applied": "The lamplighter or a monster becomes chilled.",
            "hex_applied": "A hex takes hold.",
            "wound_opened": "A wound opens and starts to bleed.",
            "daze_applied": "A blow or a knell leaves its target dazed.",
            "affliction_faded": "Any affliction wears off at the end of its span.",
            "oil_low": "Lantern oil falls below the dim threshold.",
            "oil_refilled": "The wick is trimmed and the lantern refilled.",
            "flame_out": "The lantern runs dry and gutters out.",
        }
        events = {}
        for eid, text in event_text.items():
            self.define(f"events.{eid}", p)
            events[eid] = {"status": "draft", "description": text}
        self.subfile(p, "draft", ["impl/lanternfall/core/**/*.py"], {
            "entities": entities, "verbs": verbs, "resources": resources,
            "states": states, "events": events,
        }, """
## Tokens

This file owns `entities`, `verbs`, `resources`, `states` and `events`. Rules live in `gdd/systems/*.md`, distributions in `gdd/systems/distributions.md`. The four content collections keep their entries in `content/<kind>/*.yaml`; their schemas are in `gdd/content/<kind>.md`.

## Rationale

**One actor.** The lamplighter is the only actor; monsters are content, instantiated per encounter. The satchel is an `instance_container`: relics carry charges and wear per copy, while the item template stays immutable.

**Verbs burn oil.** Every verb declares `oil_cost:`, which the lantern clock reads after the verb fires. Most verbs cost nothing else; only skills spend ward focus. Descending is the expensive choice by design.

**Two state machines.** `affliction` is the status a skill can inflict, and every affliction fades back to `clear`. `lantern_state` is the lantern itself: `guttered` is terminal for the expedition.

## Open Questions

- Whether satchel wear should be a resource rather than per-instance state. Current call: per-instance, because two copies of the same relic wear independently.
""")

    def loops(self) -> None:
        p = "gdd/loops.md"
        for n in ("loops.delve_turn", "loops.floor_sweep", "loops.expedition"):
            self.define(n, p)
        D, F, E = "loops.delve_turn", "loops.floor_sweep", "loops.expedition"
        loops = {
            "delve_turn": {
                "timescale": "moment", "duration": "~20s",
                "sequence": [Flow({"strike": self.ref(D, "verbs.strike_foe", p)}),
                             Flow({"skill": self.ref(D, "verbs.invoke_skill", p)}),
                             Flow({"relic": self.ref(D, "verbs.use_relic", p)})],
                "clock": self.ref(D, "clocks.lantern_burn", p),
                "intended_dynamics": ["every action is weighed against the oil it burns",
                                      "afflictions reward finishing fights quickly"],
                "intended_aesthetics": FlowList(["challenge"]),
                "feel_priority": "high",
                "balance_targets": [self.ref(D, "balance_targets.turns_per_fight", p)],
                "status": "draft",
                "implemented_in": self.impl(D, p, ["impl/lanternfall/core/loops/delve_turn.py"]),
            },
            "floor_sweep": {
                "timescale": "session", "duration": "~4 min",
                "sequence": [Flow({"descend": self.ref(F, "verbs.descend_stair", p)}),
                             Flow({"fight": self.ref(F, "loops.delve_turn", p)}),
                             Flow({"loot": self.ref(F, "verbs.loot_remains", p)}),
                             Flow({"salvage": self.ref(F, "verbs.salvage_gear", p)}),
                             Flow({"trim": self.ref(F, "verbs.trim_wick", p)})],
                "intended_dynamics": ["depth choice trades oil for better drops",
                                      "salvage turns worn gear back into light"],
                "intended_aesthetics": FlowList(["challenge", "discovery"]),
                "feel_priority": "medium",
                "balance_targets": [self.ref(F, "balance_targets.oil_per_floor", p)],
                "status": "draft",
                "implemented_in": self.impl(F, p, ["impl/lanternfall/core/loops/floor_sweep.py"]),
            },
            "expedition": {
                "timescale": "meta", "duration": "~45 min",
                "sequence": [Flow({"camp": self.ref(E, "verbs.make_camp", p)}),
                             Flow({"floors": self.ref(E, "loops.floor_sweep", p)}),
                             Flow({"knell": self.ref(E, "verbs.ring_the_knell", p)}),
                             Flow({"sanctum": self.ref(E, "verbs.breach_sanctum", p)}),
                             Flow({"flee": self.ref(E, "verbs.flee_upward", p)})],
                "intended_dynamics": ["the decision to flee is as important as the decision to fight",
                                      "bosses are optional until the sanctum"],
                "intended_aesthetics": FlowList(["challenge", "discovery", "fantasy"]),
                "feel_priority": "medium",
                "balance_targets": [self.ref(E, "balance_targets.expedition_length", p),
                                    self.ref(E, "balance_targets.clear_rate", p)],
                "status": "draft",
                "implemented_in": self.impl(E, p, ["impl/lanternfall/core/loops/expedition.py"]),
            },
        }
        self.subfile(p, "draft", ["impl/lanternfall/core/loops/**/*.py"], {"loops": loops}, """
## Tokens

Three nested loops: `{loops.delve_turn}` (a moment loop, driven by the lantern clock) inside `{loops.floor_sweep}` (one floor) inside `{loops.expedition}` (one descent and return).

## Rationale

**The clock is the lantern.** `delve_turn` declares `clock:`; every verb in it burns oil through `{clocks.lantern_burn}`. There is no turn timer.

**Floors are the unit of risk.** A floor sweep is where the player decides whether to go deeper. Salvage and trimming the wick close the floor; both are optional, both cost oil.

**Expeditions end by choice.** Fleeing upward is a verb, not a failure state: `{loops.expedition}` ends when the lamplighter flees, clears the sanctum, or the lantern gutters.
""")

    def clocks(self) -> None:
        p = "gdd/clocks.md"
        C = "clocks.lantern_burn"
        self.define(C, p)
        clocks = {"lantern_burn": {
            "mode": "per_verb_delta",
            "delta_source": "verb.oil_cost",
            "drives": [self.ref(C, "rules.gutter_check", p),
                       self.ref(C, "rules.affliction_tick", p),
                       self.ref(C, "rules.wandering_spawn", p)],
            "status": "prototyped",
            "implemented_in": self.impl(C, p, ["impl/lanternfall/lantern/wick.py"]),
        }}
        self.subfile(p, "prototyped", ["impl/lanternfall/lantern/wick.py"], {"clocks": clocks}, """
## Tokens

One clock, `lantern_burn`, in `per_verb_delta` mode: after each verb fires, the clock advances by the verb's `oil_cost:` and drives its rules in the declared order.

## Rationale

**Oil is time.** A per-verb delta, not a real-time rate: a careful player and a hasty one burn the same oil for the same actions. The three driven rules run in order: the lantern checks its oil, afflictions tick, and a dim lantern may draw a wandering spawn.
""")

    def distributions(self) -> None:
        p = "gdd/systems/distributions.md"
        dists: dict = {}
        shapes = [
            {"type": "discrete_sum", "samples": 2, "range": FlowList([1, 6]),
             "clamp": FlowList([2, 12])},
            {"type": "gaussian", "mean": 8, "stddev": 2, "clamp": FlowList([1, 20])},
            {"type": "uniform", "range": FlowList([0.0, 1.0]), "threshold": 0.35,
             "selection_rule": "less_than"},
            {"type": "weighted", "options": {"graze": 50, "hit": 35, "crit": 15},
             "selection_rule": "declaration_order_first_above"},
        ]
        for i, r in enumerate(ROLLS):
            self.define(f"distributions.{r}", p)
            dists[r] = {**shapes[i % 4], "seed": "deterministic_per_expedition",
                        "status": "draft",
                        "implemented_in": self.impl(f"distributions.{r}", p,
                                                    ["impl/lanternfall/rng/skill_rolls.py"])}
        pack_opts = {"shallows_pack": (60, 35, 5), "gallery_pack": (45, 40, 15),
                     "ossuary_pack": (30, 50, 20), "undercroft_pack": (25, 50, 25),
                     "deepvault_pack": (15, 50, 35), "sanctum_pack": (0, 40, 60)}
        for pack, (a, b, c) in pack_opts.items():
            self.define(f"distributions.{pack}", p)
            dists[pack] = {"type": "weighted",
                           "options": {"pair": a, "trio": b, "quartet": c},
                           "selection_rule": "declaration_order_first_above",
                           "seed": "deterministic_per_expedition", "status": "draft",
                           "implemented_in": self.impl(f"distributions.{pack}", p,
                                                       ["impl/lanternfall/rng/packs.py"])}
        misc = {
            "depth_band": ({"type": "weighted",
                            "options": {"depth_1": 35, "depth_2": 30, "depth_3": 20,
                                        "depth_4": 15},
                            "selection_rule": "declaration_order_first_above"}, "draft",
                           ["impl/lanternfall/rng/depth_band.py"]),
            "drop_quality": ({"type": "weighted",
                              "options": {"worn": 60, "sound": 30, "gleaming": 10},
                              "selection_rule": "declaration_order_first_above"}, "prototyped",
                             ["impl/lanternfall/loot/drop_tables.py"]),
            "salvage_yield": ({"type": "discrete_sum", "samples": 2, "range": FlowList([1, 4]),
                               "clamp": FlowList([2, 8])}, "draft",
                              ["impl/lanternfall/rng/salvage_yield.py"]),
            "strike_roll": ({"type": "discrete_sum", "samples": 3, "range": FlowList([1, 4]),
                             "clamp": FlowList([3, 12])}, "prototyped",
                            ["impl/lanternfall/rng/tables.py"]),
            "flight_chance": ({"type": "uniform", "range": FlowList([0.0, 1.0]),
                               "threshold": 0.6, "selection_rule": "less_than"}, "draft",
                              ["impl/lanternfall/rng/flight_chance.py"]),
            "wander_chance": ({"type": "uniform", "range": FlowList([0.0, 1.0]),
                               "threshold": 0.15, "selection_rule": "less_than"}, "draft",
                              ["impl/lanternfall/rng/wander_chance.py"]),
        }
        for did, (shape, status, globs) in misc.items():
            self.define(f"distributions.{did}", p)
            dists[did] = {**shape, "seed": "deterministic_per_expedition", "status": status,
                          "implemented_in": self.impl(f"distributions.{did}", p, globs)}
        self.subfile(p, "prototyped", ["impl/lanternfall/rng/**/*.py",
                                       "impl/lanternfall/loot/drop_tables.py"],
                     {"distributions": dists}, """
## Tokens

Every random outcome in Lanternfall resolves through one of these distributions. Sixteen are skill rolls (each skill's `roll:` names one), six are encounter packs (each encounter's `spawn_roll:`), and six serve the systems rules.

## Rationale

**Skill rolls come in four shapes.** Dice sums for steady damage, a clamped normal for heavy blows, a threshold roll for all-or-nothing effects, and a weighted graze/hit/crit table. A skill picks the shape that matches its fantasy; several skills share a roll.

**Packs grow with depth.** A pack roll decides how many of an encounter's monsters wake. The deeper packs weight toward quartets.

**Drop quality is shared with the loot code.** `drop_quality` is sampled inside `impl/lanternfall/loot/drop_tables.py`, so this file lists that module in its `implemented_in:` alongside the RNG package.

## Open Questions

- Whether the four shapes should be tuned per school. Currently the shape follows the skill, not the school.
""")

    def rule(self, rid: str, path: str, given: dict, do: list, outputs: list[str],
             status: str, globs: list[str], target_selection: str = "none") -> dict:
        return {"given": given, "target_selection": target_selection, "do": do,
                "outputs": FlowList(outputs), "status": status,
                "implemented_in": self.impl(f"rules.{rid}", path, globs)}

    def spawning(self) -> None:
        p = "gdd/systems/spawning.md"
        R, W = "rules.spawn_encounter", "rules.wandering_spawn"
        self.define(R, p)
        self.define(W, p)
        do = [{"sample": self.ref(R, "distributions.depth_band", p), "into": "band"}]
        for d in (1, 2, 3, 4):
            encs = sorted(e for e, a in self.encounter.items() if a["depth"] == d)
            do.append({"when_band": d,
                       "spawn_one_of": self.refs(R, [f"entities.encounters.{e}" for e in encs],
                                                 p)})
        rules = {
            "spawn_encounter": self.rule(
                "spawn_encounter", p, {"verb": self.ref(R, "verbs.descend_stair", p)}, do,
                ["encounter_spawned"], "draft", ["impl/lanternfall/spawning/spawn_encounter.py"]),
            "wandering_spawn": self.rule(
                "wandering_spawn", p,
                {"driver": self.ref(W, "clocks.lantern_burn", p),
                 "state": self.ref(W, "states.lantern_state", p, "dim")},
                [{"sample": self.ref(W, "distributions.wander_chance", p), "into": "roll"},
                 Flow({"on_hit_spawn_from": self.ref(W, "entities.monsters", p),
                       "tier": "minion"})],
                ["wanderer_spawned"], "draft", ["impl/lanternfall/spawning/wandering_spawn.py"]),
        }
        self.subfile(p, "draft", ["impl/lanternfall/spawning/**/*.py"], {"rules": rules}, """
## Tokens

Two rules. `spawn_encounter` fires when the lamplighter descends: it samples a depth band, then one of that band's encounters. `wandering_spawn` fires on the lantern clock while the lantern is dim.

## Rationale

**Encounters are authored, spawns are rolled.** Every encounter in `content/encounters/` belongs to exactly one depth band here, except the sanctum, which is entered only through `{verbs.breach_sanctum}`.

**A dim lantern invites company.** Wandering spawns draw any minion from `{entities.monsters}`; they never carry the floor's loot, so fleeing from them is always an option.
""")

    def bosses(self) -> None:
        p = "gdd/systems/bosses.md"
        B, T = "rules.boss_awakening", "rules.sanctum_trial"
        self.define(B, p)
        self.define(T, p)
        rules = {
            "boss_awakening": self.rule(
                "boss_awakening", p, {"verb": self.ref(B, "verbs.ring_the_knell", p)},
                [Flow({"awaken": self.ref(B, "entities.monsters.lamp_warden", p),
                       "at_depth": BOSSES["lamp_warden"]}),
                 Flow({"awaken": self.ref(B, "entities.monsters.knell_mother", p),
                       "at_depth": BOSSES["knell_mother"]})],
                ["boss_awakened"], "draft", ["impl/lanternfall/bosses/awakening.py"]),
            "sanctum_trial": self.rule(
                "sanctum_trial", p, {"verb": self.ref(T, "verbs.breach_sanctum", p)},
                [Flow({"enter": self.ref(T, f"entities.encounters.{SANCTUM}", p)}),
                 Flow({"awaken": self.ref(T, "entities.monsters.soot_king", p)}),
                 Flow({"seal_exit_until": self.ref(T, "states.lantern_state", p, "guttered")})],
                ["sanctum_entered"], "draft", ["impl/lanternfall/bosses/sanctum.py"]),
        }
        self.subfile(p, "draft", ["impl/lanternfall/bosses/**/*.py"], {"rules": rules}, """
## Tokens

Two rules. Ringing the knell wakes the two lair bosses at their depths; breaching the sanctum seals the lamplighter in with the last one.

## Rationale

**Bosses are opt-in until the end.** The lair bosses sleep until the knell is rung, so a cautious expedition can sweep their floors without waking them. The sanctum trial cannot be fled: its exit stays sealed until the lantern gutters or the king falls.
""")

    def loot(self) -> None:
        p = "gdd/systems/loot.md"
        D, S = "rules.roll_drops", "rules.resolve_salvage"
        self.define(D, p)
        self.define(S, p)
        rules = {
            "roll_drops": self.rule(
                "roll_drops", p, {"verb": self.ref(D, "verbs.loot_remains", p)},
                [{"for_each_drop_of": "{target.drops}", "keep_one_in": 3},
                 {"sample": self.ref(D, "distributions.drop_quality", p), "into": "quality"}],
                ["items_dropped"], "prototyped", ["impl/lanternfall/loot/drop_tables.py"],
                target_selection="explicit"),
            "resolve_salvage": self.rule(
                "resolve_salvage", p, {"verb": self.ref(S, "verbs.salvage_gear", p)},
                [{"sample": self.ref(S, "distributions.salvage_yield", p), "into": "coins"},
                 Flow({"credit": self.ref(S, "resources.grave_coin", p),
                       "amount_from": "coins"})],
                ["gear_salvaged"], "prototyped", ["impl/lanternfall/loot/salvage.py"],
                target_selection="explicit"),
        }
        self.subfile(p, "prototyped", ["impl/lanternfall/loot/**/*.py"], {"rules": rules}, """
## Tokens

Two rules. `roll_drops` walks a defeated monster's `drops:` list and keeps each entry on a one-in-three roll, then rolls its quality. `resolve_salvage` turns worn satchel gear into grave coin.

## Rationale

**Drops are a map.** A monster's `drops:` list is authored, not random: the randomness is only whether each listed item survives the fight and in what condition. Players who learn the lists learn where to hunt.

**One in three.** The keep odds are fixed at one in three for every monster. Tuning them per tier was tried and made bosses feel like loot piñatas.
""")

    def combat(self) -> None:
        p = "gdd/systems/combat.md"
        rules = {}
        for rid in ("resolve_strike", "resolve_skill", "apply_relic", "resolve_flight",
                    "affliction_tick"):
            self.define(f"rules.{rid}", p)
        r = "rules.resolve_strike"
        rules["resolve_strike"] = self.rule(
            "resolve_strike", p, {"verb": self.ref(r, "verbs.strike_foe", p)},
            [{"sample": self.ref(r, "distributions.strike_roll", p), "plus": "{actor.might}"},
             {"apply_damage_to": "{target.max_vigor}"}],
            ["damage_dealt"], "prototyped", ["impl/lanternfall/combat/strike.py"],
            target_selection="explicit")
        r = "rules.resolve_skill"
        rules["resolve_skill"] = self.rule(
            "resolve_skill", p, {"verb": self.ref(r, "verbs.invoke_skill", p)},
            [Flow({"spend": self.ref(r, "resources.ward_focus", p),
                   "amount_from": "{target.focus_cost}"}),
             {"roll_via": "{target.roll}"},
             {"inflict_if_present": "{target.inflicts}"}],
            ["skill_resolved"], "draft", ["impl/lanternfall/combat/skills.py"],
            target_selection="explicit")
        r = "rules.apply_relic"
        rules["apply_relic"] = self.rule(
            "apply_relic", p, {"verb": self.ref(r, "verbs.use_relic", p)},
            [{"field": "charges", "decrement": 1},
             Flow({"restore": self.ref(r, "resources.vigor", p), "amount": 6})],
            ["relic_used"], "draft", ["impl/lanternfall/combat/relics.py"],
            target_selection="explicit")
        r = "rules.resolve_flight"
        rules["resolve_flight"] = self.rule(
            "resolve_flight", p, {"verb": self.ref(r, "verbs.flee_upward", p)},
            [{"sample": self.ref(r, "distributions.flight_chance", p), "into": "escaped"},
             Flow({"on_failure_spend": self.ref(r, "resources.vigor", p), "amount": 5})],
            ["flight_resolved"], "draft", ["impl/lanternfall/combat/flight.py"])
        r = "rules.affliction_tick"
        rules["affliction_tick"] = self.rule(
            "affliction_tick", p, {"driver": self.ref(r, "clocks.lantern_burn", p)},
            [Flow({"for_each_in": self.ref(r, "states.affliction", p)}),
             Flow({"damage_while": self.ref(r, "states.affliction", p, "bleeding"),
                   "amount": 1})],
            ["affliction_ticked"], "draft", ["impl/lanternfall/combat/afflictions.py"],
            target_selection="self")
        self.subfile(p, "prototyped", ["impl/lanternfall/combat/**/*.py"], {"rules": rules}, """
## Tokens

Five rules: strikes, skills, relics, flight and the affliction tick. Only `resolve_strike` has code so far.

## Rationale

**Skills read their own content.** `resolve_skill` spends the skill's `focus_cost`, rolls its `roll:` and applies its `inflicts:` node, all bound from the targeted skill at apply time. The rule itself names no skill.

**Afflictions tick on oil, not turns.** Bleeding costs vigor each time the lantern clock advances, so a wounded lamplighter who dawdles bleeds more.
""")

    def lantern(self) -> None:
        p = "gdd/systems/lantern.md"
        G, F = "rules.gutter_check", "rules.refill_lantern"
        self.define(G, p)
        self.define(F, p)
        rules = {
            "gutter_check": self.rule(
                "gutter_check", p, {"driver": self.ref(G, "clocks.lantern_burn", p)},
                [Flow({"burn": self.ref(G, "resources.lantern_oil", p),
                       "amount_from": "verb.oil_cost"}),
                 Flow({"below": 20, "transition": self.ref(G, "states.lantern_state", p, "dim")}),
                 Flow({"at_zero": True,
                       "transition": self.ref(G, "states.lantern_state", p, "guttered")})],
                ["oil_checked"], "prototyped", ["impl/lanternfall/lantern/wick.py"],
                target_selection="self"),
            "refill_lantern": self.rule(
                "refill_lantern", p, {"verb": self.ref(F, "verbs.trim_wick", p)},
                [Flow({"restore": self.ref(F, "resources.lantern_oil", p), "amount": 30}),
                 Flow({"transition": self.ref(F, "states.lantern_state", p, "lit")})],
                ["lantern_refilled"], "draft", ["impl/lanternfall/lantern/refill.py"],
                target_selection="self"),
        }
        self.subfile(p, "prototyped", ["impl/lanternfall/lantern/**/*.py"], {"rules": rules}, """
## Tokens

Two rules: the per-verb oil check the lantern clock drives, and the refill a trimmed wick grants.

## Rationale

**Dim before dark.** The lantern dims at 20 oil, a full floor's warning before it gutters. Dimming is what invites wandering spawns, so the warning is also a threat.
""")

    def balance(self) -> None:
        p = "gdd/economy-balance.md"
        targets = {
            "oil_per_floor": {"target_kind": "scalar", "target": 18,
                              "tolerance": FlowList([14, 22]),
                              "measure": "median oil burned per floor sweep, depth 1-4"},
            "coin_per_expedition": {"target_kind": "scalar", "target": 240,
                                    "tolerance": FlowList([180, 320]),
                                    "measure": "median grave coin banked per expedition"},
            "turns_per_fight": {"target_kind": "range", "target": Flow({"near": 5, "tolerance": 2}),
                                "measure": "median delve turns to clear a non-boss encounter"},
            "expedition_length": {"target_kind": "scalar", "target": "45 min",
                                  "tolerance": FlowList(["35 min", "60 min"]),
                                  "measure": "median wall-clock length of an expedition"},
            "clear_rate": {"target_kind": "scalar", "target": 0.4,
                           "tolerance": FlowList([0.3, 0.5]),
                           "measure": "share of expeditions that clear the sanctum"},
            "items_per_rarity": {"target_kind": "distribution_over_categories",
                                 "target": Flow({"worn": 70, "sound": 42, "gleaming": 21,
                                                 "relic": 7}),
                                 "tolerance": Flow({"worn": 10, "sound": 8, "gleaming": 5,
                                                    "relic": 3}),
                                 "measure": "designed item count per rarity in content/items/"},
            "skill_focus_cost": {"target_kind": "scalar", "target": 3.5,
                                 "tolerance": FlowList([2.5, 4.5]),
                                 "measure": "mean focus_cost across content/skills/"},
            "monster_vigor_curve": {"target_kind": "range",
                                    "target": Flow({"between": FlowList([10, 60])}),
                                    "measure": "max_vigor of non-boss monsters"},
            "encounter_pack_size": {"target_kind": "range",
                                    "target": Flow({"near": 3, "tolerance": 1}),
                                    "measure": "monsters listed per encounter"},
        }
        for t in targets.values():
            t["status"] = "draft"
        for t in targets:
            self.define(f"balance_targets.{t}", p)
        self.subfile(p, "draft", ["impl/lanternfall/balance/**/*.py"],
                     {"balance_targets": targets}, """
## Tokens

Nine balance targets: five on the loops and resources, four on the content collections (referenced from each content-schema's `balance_refs:`).

## Rationale

**Oil per floor is the headline.** At 18 oil a floor and 120 oil a lantern, an unrefilled expedition sees about six floors. Everything else is tuned so that the sixth floor is where the sanctum becomes reachable.
""")

    def feel(self) -> None:
        p = "gdd/feel.md"
        entries = {
            "descend_stair": ("hold to descend; release early to stay on the landing",
                              "the lantern swings and the stairwell darkens over 400ms",
                              "the oil gauge ticks down by the stair's cost as the camera settles",
                              "dust falls from the ceiling; the knell-bells hum at depth 3 and below",
                              "a descent is a promise you cannot take back",
                              "no input is accepted during the 400ms transition"),
            "strike_foe": ("tap to strike the highlighted foe",
                           "the blow lands within 120ms; damage numbers rise from the target",
                           "the lantern flares on a crit",
                           "a short screen shake scaled to damage dealt",
                           "every strike is a spark struck in the dark",
                           "a second tap during the strike is queued, not dropped"),
            "ring_the_knell": ("hold for one full second to ring",
                               "a low toll rolls outward; every lit sconce flickers",
                               "the boss markers on the depth map pulse",
                               "the controller rumbles once per toll",
                               "ringing the knell wakes what should have stayed asleep",
                               "cannot be cancelled once the toll starts"),
        }
        feel = {}
        for fid, (i, r, c, po, m, ru) in entries.items():
            self.define(f"feel.{fid}", p)
            feel[fid] = {"input": i, "response": r, "context": c, "polish": po, "metaphor": m,
                         "rules": ru, "status": "draft",
                         "implemented_in": self.impl(f"feel.{fid}", p,
                                                     [f"impl/lanternfall/feel/{fid}.py"])}
        self.subfile(p, "draft", ["impl/lanternfall/feel/**/*.py"], {"feel": feel}, """
## Tokens

Three feel entries, one for each verb that declares `feel:`. The rest are mechanical glue.

## Rationale

**Commitment is the common thread.** Descending, striking and ringing the knell are the three moments the player cannot undo; each is tuned to feel like a commitment.
""")

    def invariants(self) -> None:
        p = "gdd/architecture-invariants.md"
        specs = {
            "vigor_is_integer": ("numeric_domain",
                                 "Vigor, ward focus and every monster's max_vigor resolve to integers.",
                                 ["resources.vigor", "resources.ward_focus", "entities.monsters"],
                                 "lint", "error"),
            "oil_only_via_clock": ("architectural_pattern",
                                   "Lantern oil changes only through the lantern clock and the rules it drives; no verb writes oil directly.",
                                   ["clocks.lantern_burn", "resources.lantern_oil"],
                                   "advisory", "warning"),
            "seeded_rolls": ("determinism",
                             "Given a fixed expedition seed, strikes, drop quality and depth bands are reproducible.",
                             ["distributions.strike_roll", "distributions.drop_quality",
                              "distributions.depth_band"],
                             "verify", "error"),
            "sim_owns_lantern_state": ("layer_boundary",
                                       "The simulation owns the lantern state machine; presentation only reads it.",
                                       ["states.lantern_state"], "lint", "error"),
            "events_one_way": ("communication",
                               "The simulation emits events to presentation; presentation never calls back into it.",
                               [], "advisory", "warning"),
        }
        invs = {}
        for iid, (kind, text, applies, enf, sev) in specs.items():
            node = f"invariants.{iid}"
            self.define(node, p)
            body = {"kind": kind, "rule": text}
            if applies:
                body["applies_to"] = self.refs(node, applies, p)
            body.update({"enforcement": enf, "severity": sev})
            invs[iid] = body
        self.subfile(p, "draft", None, {"invariants": invs}, """
## Tokens

Five invariants: one numeric domain, one architectural pattern, one determinism contract, one layer boundary and one communication rule.

## Rationale

**Oil is sacred.** Every design decision in Lanternfall assumes oil moves only through the clock. A verb that refilled oil directly would break the per-verb delta and with it every balance target on this tree.
""")

    def glossary(self) -> None:
        self.subfile("gdd/glossary.md", "draft", None, {}, """
## Tokens

This file contributes no tokens. It is a glossary of the in-game vocabulary used across the tree.

## Rationale

- **Lamplighter.** The player character, and the only actor.
- **Knell.** The cracked bell at depth 4; ringing it wakes the lair bosses.
- **Guttering.** The lantern running dry. A guttered lantern ends the expedition.
- **Sanctum.** The sealed final encounter below depth 4.
- **Wick.** Trimming the wick refills the lantern at the cost of a verb.
""")

    def content_index(self) -> None:
        self.subfile("gdd/content/_index.md", "draft", None, {}, """
## Tokens

Index of the content subtree. No tokens; this file exists because spec §2.2 requires `content/_index.md` whenever a content-schema file exists.

## Rationale

Four content-schema files, one per content-heavy kind:

- [`items.md`](items.md): 140 items under `content/items/*.yaml`.
- [`skills.md`](skills.md): 90 skills under `content/skills/*.yaml`.
- [`monsters.md`](monsters.md): 60 monsters under `content/monsters/*.yaml`.
- [`encounters.md`](encounters.md): 30 encounters under `content/encounters/*.yaml`.
""")

    def content_schemas(self) -> None:
        schemas = {
            "items": ({"required": FlowList(["id", "name", "rarity", "slot", "weight", "value"]),
                       "properties": {
                           "id": Flow({"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}),
                           "name": Flow({"type": "string", "minLength": 1}),
                           "rarity": Flow({"enum": FlowList(RARITIES)}),
                           "slot": Flow({"enum": FlowList(SLOTS)}),
                           "weight": Flow({"type": "integer", "minimum": 1}),
                           "value": Flow({"type": "integer", "minimum": 0}),
                           "grants": Flow({"type": "string"}),
                           "description": Flow({"type": "string"})}},
                      "items_per_rarity",
                      "An item is a YAML object under `content/items/<id>.yaml` whose filename stem matches its `id`. `grants:` optionally names one skill (`{entities.skills.<id>}`) that the item teaches while carried."),
            "skills": ({"required": FlowList(["id", "name", "school", "focus_cost", "roll"]),
                        "properties": {
                            "id": Flow({"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}),
                            "name": Flow({"type": "string", "minLength": 1}),
                            "school": Flow({"enum": FlowList(SCHOOLS)}),
                            "focus_cost": Flow({"type": "integer", "minimum": 1}),
                            "roll": Flow({"type": "string"}),
                            "inflicts": Flow({"type": "string"}),
                            "description": Flow({"type": "string"})}},
                       "skill_focus_cost",
                       "A skill names the distribution it rolls (`roll:`, a `{distributions.<id>}`) and optionally the affliction node it inflicts (`inflicts:`, a `{states.affliction.<node>}`)."),
            "monsters": ({"required": FlowList(["id", "name", "tier", "max_vigor", "skills",
                                                "drops"]),
                          "properties": {
                              "id": Flow({"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}),
                              "name": Flow({"type": "string", "minLength": 1}),
                              "tier": Flow({"enum": FlowList(["minion", "brute", "elite",
                                                              "boss"])}),
                              "max_vigor": Flow({"type": "integer", "minimum": 1}),
                              "skills": Flow({"type": "array", "minItems": 1, "maxItems": 2}),
                              "drops": Flow({"type": "array", "minItems": 1, "maxItems": 3}),
                              "description": Flow({"type": "string"})}},
                         "monster_vigor_curve",
                         "A monster lists the skills it uses (`skills:`, one or two `{entities.skills.<id>}`) and the items it can drop (`drops:`, one to three `{entities.items.<id>}`)."),
            "encounters": ({"required": FlowList(["id", "name", "depth", "monsters",
                                                  "spawn_roll"]),
                            "properties": {
                                "id": Flow({"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}),
                                "name": Flow({"type": "string", "minLength": 1}),
                                "depth": Flow({"type": "integer", "minimum": 1, "maximum": 5}),
                                "monsters": Flow({"type": "array", "minItems": 2,
                                                  "maxItems": 4}),
                                "spawn_roll": Flow({"type": "string"}),
                                "description": Flow({"type": "string"})}},
                           "encounter_pack_size",
                           "An encounter lists its monsters (`monsters:`, two to four `{entities.monsters.<id>}`) and the pack distribution that decides how many wake (`spawn_roll:`)."),
        }
        examples = {"items": sorted(i for i in self.items if self.item[i]["grants"])[0],
                    "skills": sorted(s for s in self.skills if self.skill[s]["inflicts"])[0],
                    "monsters": self.regular[0], "encounters": sorted(self.encounter)[0]}
        for kind, (schema, bref, prose) in schemas.items():
            path = f"gdd/content/{kind}.md"
            meta = f"meta:{path}"
            fm = {"spec": "game-design.md", "spec_version": SPEC_VERSION,
                  "file_type": "content-schema", "status": "draft", "last_verified": LV_DRAFT,
                  "entity": kind, "schema": schema, "data_dir": f"../../content/{kind}",
                  "count_target": KINDS[kind],
                  "balance_refs": [self.ref(meta, f"balance_targets.{bref}", path)]}
            ex = examples[kind]
            body = f"""
## Schema

{prose} Every entry also carries the content-entity header (`spec`, `spec_version`, `file_type`, `id`, `status`, `last_verified`, `implemented_in`).

## Representative Example

`content/{kind}/{ex}.yaml`:

```yaml
{self.files[f"content/{kind}/{ex}.yaml"].rstrip()}
```

## Balance Notes

Tuned against `{{balance_targets.{bref}}}` in `gdd/economy-balance.md`.
"""
            self.files[path] = md(fm, body)

    def core(self) -> None:
        p = "game-design.md"
        files = {"pillars": "gdd/pillars.md", "loops": "gdd/loops.md", "clocks": "gdd/clocks.md",
                 "mechanics": "gdd/mechanics.md",
                 "architecture_invariants": "gdd/architecture-invariants.md",
                 "distributions": "gdd/systems/distributions.md",
                 "spawning": "gdd/systems/spawning.md", "bosses": "gdd/systems/bosses.md",
                 "loot": "gdd/systems/loot.md", "combat": "gdd/systems/combat.md",
                 "lantern": "gdd/systems/lantern.md", "economy_balance": "gdd/economy-balance.md",
                 "feel": "gdd/feel.md", "glossary": "gdd/glossary.md",
                 "content_index": "gdd/content/_index.md", "items": "gdd/content/items.md",
                 "skills": "gdd/content/skills.md", "monsters": "gdd/content/monsters.md",
                 "encounters": "gdd/content/encounters.md"}
        self.root_pointers = {"loot": "impl/lanternfall/loot/**/*.py",
                              "lantern": "impl/lanternfall/lantern/**/*.py",
                              "combat": "impl/lanternfall/combat/**/*.py",
                              "rng": "impl/lanternfall/rng/**/*.py"}
        fm = {
            "spec": "game-design.md", "spec_version": SPEC_VERSION, "file_type": "core",
            "name": "Lanternfall",
            "short_pitch": "A dungeon crawler where your lantern's oil is the clock: descend, "
                           "fight what the light reveals, and climb out before the flame gutters.",
            "genre_tags": FlowList(["dungeon-crawler", "rpg", "single-player"]),
            "status": "draft", "version": "0.3.1", "last_updated": LAST_UPDATED,
            "target_platforms_neutral": FlowList(["desktop", "handheld"]),
            "pillars": ["Light is the only currency that matters",
                        "Every floor is a readable risk",
                        "Loot tells you what the dark is hiding"],
            "non_goals": ["Multiplayer", "Real-time twitch combat", "Procedural narrative"],
            "player_experience_goals": {"primary": FlowList(["challenge", "discovery"]),
                                        "secondary": FlowList(["fantasy"]),
                                        "explicit_non_goals": FlowList(["fellowship"])},
            "core_loop_ref": self.ref("meta:game-design.md", "loops.delve_turn", p),
            "files": files,
            "implementation_pointers": self.root_pointers,
        }
        missing = sorted(set(files.values()) - set(self.files))
        if missing:
            raise BuildError(f"files: map names missing files {missing}")
        self.files[p] = md(fm, """
# Lanternfall

> A dungeon crawler where your lantern's oil is the clock: descend, fight what the light reveals, and climb out before the flame gutters.

## High Concept

You are a lamplighter descending the Lanternfall catacombs. Every action burns oil from a single lantern; when it gutters, the expedition is over. Monsters, loot and bosses are authored content, a few hundred entries deep, and the interesting decision is always the same one: how much light is this worth?

## Pillars & Non-Goals

Three pillars and three non-goals (see frontmatter), immutable for the life of the project.

## Player Experience Goals

Challenge and discovery are primary; fantasy is secondary. Fellowship is an explicit non-goal: Lanternfall is a solitary descent.

## Core Gameplay Loop

The core loop is `{loops.delve_turn}`: strike, invoke a skill or use a relic, and watch the oil. It nests inside `{loops.floor_sweep}` and `{loops.expedition}`. See `gdd/loops.md`.

## Universal Surface

The design lives in subfiles, linked through the `files:` map. Content is external: 140 items, 90 skills, 60 monsters and 30 encounters under `content/<kind>/*.yaml`, each kind described by `gdd/content/<kind>.md`. Rules are split by system under `gdd/systems/`.

## How to Use This Document (for the Agent)

- **YAML is normative.** Token values are the truth; prose is rationale.
- **Content references are values.** A monster's `drops:` and `skills:`, an item's `grants:`, a skill's `roll:` and an encounter's `monsters:` are token references like any other.
- **Use the `files:` map.** Open only the subfiles a task needs.

## Glossary

See `gdd/glossary.md`.
""")

    # -- implementation stubs -------------------------------------------------------------

    DROP_TABLES = '''"""Drop-table sampling (rules.roll_drops, distributions.drop_quality)."""
from __future__ import annotations

QUALITY_WEIGHTS = {"worn": 60, "sound": 30, "gleaming": 10}


def roll_quality(rng) -> str:
    """Sample drop_quality: declaration order, first bucket above the roll."""
    roll = rng.randrange(100)
    for quality, weight in QUALITY_WEIGHTS.items():
        if roll < weight:
            return quality
        roll -= weight
    return "worn"


def roll_drops(monster: dict, rng) -> list[tuple[str, str]]:
    """Keep each listed drop on a one-in-three roll, then roll its quality."""
    kept = []
    for item in monster["drops"]:
        if rng.randrange(3) == 0:
            kept.append((item, roll_quality(rng)))
    return kept
'''

    TEST_DROP_TABLES = '''"""Smoke tests for loot/drop_tables.py."""
import random

from lanternfall.loot import drop_tables


def test_quality_is_a_known_bucket():
    rng = random.Random(7)
    assert drop_tables.roll_quality(rng) in drop_tables.QUALITY_WEIGHTS


def test_drops_come_from_the_list():
    rng = random.Random(11)
    kept = drop_tables.roll_drops({"drops": ["a", "b", "c"]}, rng)
    assert all(item in ("a", "b", "c") for item, _ in kept)
'''

    def impl_stubs(self) -> None:
        stubs = {
            "impl/lanternfall/__init__.py": '"""Lanternfall simulation (prototype)."""\n',
            "impl/lanternfall/loot/__init__.py": '"""Loot rules."""\n',
            "impl/lanternfall/loot/drop_tables.py": self.DROP_TABLES,
            "impl/lanternfall/loot/salvage.py": '''"""Salvage (rules.resolve_salvage)."""
from __future__ import annotations


def resolve_salvage(rng) -> int:
    """Grave coin for one worn item: two d4, clamped to 2..8."""
    return max(2, min(8, rng.randint(1, 4) + rng.randint(1, 4)))
''',
            "impl/lanternfall/rng/__init__.py": '"""Named distributions."""\n',
            "impl/lanternfall/rng/tables.py": '''"""Strike roll (distributions.strike_roll)."""
from __future__ import annotations


def strike_roll(rng) -> int:
    """Three d4, clamped to 3..12."""
    return max(3, min(12, sum(rng.randint(1, 4) for _ in range(3))))
''',
            "impl/lanternfall/combat/__init__.py": '"""Combat rules."""\n',
            "impl/lanternfall/combat/strike.py": '''"""Strike resolution (rules.resolve_strike)."""
from __future__ import annotations

from lanternfall.rng.tables import strike_roll


def resolve_strike(actor: dict, target: dict, rng) -> int:
    """Damage = strike_roll + the actor's might; returns the target's remaining vigor."""
    damage = strike_roll(rng) + actor["might"]
    target["vigor"] = max(0, target["vigor"] - damage)
    return target["vigor"]
''',
            "impl/lanternfall/lantern/__init__.py": '"""The lantern."""\n',
            "impl/lanternfall/lantern/wick.py": '''"""The lantern clock and its oil check (clocks.lantern_burn, rules.gutter_check)."""
from __future__ import annotations

DIM_BELOW = 20


def burn(lantern: dict, oil_cost: int) -> str:
    """Advance the clock by one verb's oil cost; return the lantern state."""
    lantern["oil"] = max(0, lantern["oil"] - oil_cost)
    if lantern["oil"] == 0:
        return "guttered"
    return "dim" if lantern["oil"] < DIM_BELOW else "lit"
''',
            "impl/lanternfall/tests/test_drop_tables.py": self.TEST_DROP_TABLES,
        }
        self.files.update(stubs)

    # -- the tree ---------------------------------------------------------------------------

    def build(self) -> None:
        self.content()
        self.write_content()
        self.tokens()
        self.impl_stubs()
        self.check_graph()

    def check_graph(self) -> None:
        nodes = set(self.node_file)
        for e in self.edges:
            if e.dst not in nodes:
                raise BuildError(f"edge to undefined {e.dst} from {e.src}")
        subfiles = [p for p in self.subfiles]
        if len(subfiles) < 12:
            raise BuildError(f"{len(subfiles)} subfiles < 12")
        non_content = [n for n in nodes if not is_content(n)]
        namespaces = {n.split(".")[0] for n in non_content}
        if len(non_content) < 60 or len(namespaces) < 8:
            raise BuildError(f"{len(non_content)} non-content tokens in {len(namespaces)} namespaces")
        out = defaultdict(list)
        for e in self.edges:
            out[e.src].append(e.dst)

        def deg(kind: str, dst_prefix: str) -> list[int]:
            return [sum(1 for d in out[f"entities.{kind}.{x}"] if d.startswith(dst_prefix))
                    for x in getattr(self, kind)]
        bounds = [("monsters", "entities.items.", 1, 3), ("monsters", "entities.skills.", 1, 2),
                  ("items", "entities.skills.", 0, 1), ("skills", "distributions.", 1, 1),
                  ("skills", "states.", 0, 1), ("encounters", "entities.monsters.", 2, 4),
                  ("encounters", "distributions.", 1, 1)]
        for kind, prefix, lo, hi in bounds:
            d = deg(kind, prefix)
            if min(d) < lo or max(d) > hi:
                raise BuildError(f"{kind} -> {prefix}: degrees {min(d)}..{max(d)} not in {lo}..{hi}")


# ---- the oracle (planted edges only) ------------------------------------------------

class Oracle:
    def __init__(self, gen: Gen):
        self.gen = gen
        self.fwd: dict[str, set[str]] = defaultdict(set)
        self.rev: dict[str, set[str]] = defaultdict(set)
        self.edge_files: dict[tuple[str, str], set[str]] = defaultdict(set)
        for e in gen.edges:
            self.fwd[e.src].add(e.dst)
            self.rev[e.dst].add(e.src)
            self.edge_files[(e.src, e.dst)].add(e.path)

    @staticmethod
    def identity(n: str) -> bool:
        return not n.startswith("meta:")

    def walk_exactly(self, start: str, k: int) -> set[str]:
        frontier = {start}
        for _ in range(k):
            frontier = set().union(*(self.fwd[n] for n in frontier)) if frontier else set()
        return frontier

    def dist(self, start: str, adj: dict[str, set[str]], max_k: int | None = None
             ) -> dict[str, int]:
        seen, frontier, hop = {start: 0}, [start], 0
        while frontier and (max_k is None or hop < max_k):
            hop += 1
            nxt = []
            for n in frontier:
                for m in sorted(adj[n]):
                    if m not in seen:
                        seen[m] = hop
                        nxt.append(m)
            frontier = nxt
        del seen[start]
        return seen

    def walks(self, start: str, k: int, ends: set[str]) -> set[tuple[str, str]]:
        """Edges on walks of exactly k steps from start that end in `ends`."""
        used: set[tuple[str, str]] = set()

        def go(n: str, path: list[tuple[str, str]]) -> None:
            if len(path) == k:
                if n in ends:
                    used.update(path)
                return
            for m in sorted(self.fwd[n]):
                go(m, path + [(n, m)])
        go(start, [])
        return used

    def back_paths(self, target: str, k: int, starts: set[str]) -> set[tuple[str, str]]:
        """Edges on paths of at most k steps from any of `starts` to `target`."""
        used: set[tuple[str, str]] = set()

        def go(n: str, path: list[tuple[str, str]]) -> None:
            if n in starts:
                used.update(path)
            if len(path) == k:
                return
            for m in sorted(self.rev[n]):
                go(m, path + [(m, n)])
        go(target, [])
        return used

    def closure(self, x: str) -> set[str]:
        return {n for n in self.dist(x, self.rev) if self.identity(n)}

    def files_of(self, edges: set[tuple[str, str]]) -> set[str]:
        return set().union(*(self.edge_files[e] for e in edges)) if edges else set()


def kind_of(n: str) -> str:
    parts = n.split(".")
    return f"entities.{parts[1]}" if is_content(n) else parts[0]


def select_questions(gen: Gen, o: Oracle) -> dict:
    rng, used = gen.rng, set()
    regular_enc = [f"entities.encounters.{e}" for e in gen.encounters if e != SANCTUM]
    rolls = [f"distributions.{r}" for r in ROLLS]

    def pick(label: str, cands: list[str], ok) -> tuple[str, dict]:
        good = []
        for c in sorted(cands):
            if c in used:
                continue
            info = ok(c)
            if info is not None:
                good.append((c, info))
        if not good:
            raise BuildError(f"no candidate satisfies {label}")
        c, info = good[rng.randrange(len(good))]
        used.add(c)
        info["candidates"] = len(good)
        return c, info

    def forward(kind: str, k: int):
        def ok(start: str):
            walk = {n for n in o.walk_exactly(start, k) if kind_of(n) == kind}
            layer = {n for n, d in o.dist(start, o.fwd, k).items() if d == k and kind_of(n) == kind}
            if walk != layer or not 3 <= len(walk) <= 12:
                return None
            files = o.files_of(o.walks(start, k, walk))
            if len(files) < 3:
                return None
            return {"answer": sorted(walk), "evidence_files": sorted(files)}
        return ok

    def backward(k: int):
        def ok(target: str):
            ans = {n for n, d in o.dist(target, o.rev, k).items() if is_content(n)}
            if not 3 <= len(ans) <= 15:
                return None
            files = o.files_of(o.back_paths(target, k, ans))
            if len(files) < 3:
                return None
            return {"answer": sorted(ans), "evidence_files": sorted(files)}
        return ok

    def closure_evidence(x: str, clo: set[str]) -> set[str]:
        return o.files_of({(u, v) for u in clo for v in o.fwd[u] if v in clo | {x}})

    def impact_tokens(x: str):
        clo = o.closure(x)
        kinds = {kind_of(n) for n in clo if is_content(n)}
        files = {gen.node_file[n] for n in clo}
        if not 10 <= len(clo) <= 40 or len(files) < 3 or len(kinds) < 2:
            return None
        ev = closure_evidence(x, clo)
        if len(ev) < 3:
            return None
        return {"answer": sorted(clo), "evidence_files": sorted(ev)}

    def impact_files(y: str):
        clo = o.closure(y)
        subs = {gen.node_file[n] for n in clo if not is_content(n)
                and gen.node_file[n] in gen.subfiles}
        if not 4 <= len(subs) <= 10:
            return None
        ev = closure_evidence(y, clo)
        if len(ev) < 3:
            return None
        return {"answer": sorted(subs), "closure": sorted(clo), "evidence_files": sorted(ev)}

    q: dict = {}
    s, info = pick("s2_lookup_forward Q1", regular_enc, forward("entities.items", 2))
    q["s2_lookup_forward"] = {"Q1": {"start": s, "relation": "forward_exactly", "k": 2,
                                     "kind": "entities.items", **info}}
    s, info = pick("s2_lookup_forward Q2", regular_enc, forward("distributions", 3))
    q["s2_lookup_forward"]["Q2"] = {"start": s, "relation": "forward_exactly", "k": 3,
                                    "kind": "distributions", **info}
    s, info = pick("s2_lookup_backward Q1", rolls, backward(2))
    q["s2_lookup_backward"] = {"Q1": {"start": s, "relation": "backward_within", "k": 2,
                                      "kind": "content", **info}}
    s, info = pick("s2_lookup_backward Q2", [f"entities.skills.{x}" for x in gen.skills],
                   backward(3))
    q["s2_lookup_backward"]["Q2"] = {"start": s, "relation": "backward_within", "k": 3,
                                     "kind": "content", **info}
    s, info = pick("s2_impact_tokens", rolls, impact_tokens)
    q["s2_impact_tokens"] = {"Q1": {"start": s, "relation": "value_reverse_closure", **info}}
    s, info = pick("s2_impact_files", [f"entities.items.{x}" for x in gen.items], impact_files)
    q["s2_impact_files"] = {"Q1": {"start": s, "relation": "subfiles_of_value_reverse_closure",
                                   **info}}
    depth = max(max(o.dist(n, o.rev).values(), default=0) for n in gen.node_file)
    if depth < 4:
        raise BuildError(f"deepest reverse closure is {depth} < 4")
    return q


# ---- maintenance fixtures ---------------------------------------------------------------

def glob_re(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def covering_subfiles(gen: Gen, rel: str) -> set[str]:
    hit = {p for p, globs in gen.file_impl.items() if any(glob_re(g).match(rel) for g in globs)}
    hit |= {p for p, globs in gen.token_impl.values() if any(glob_re(g).match(rel) for g in globs)}
    return hit


MAINT_FILE = "impl/lanternfall/loot/drop_tables.py"
CONTROL_FILE = "impl/lanternfall/tests/test_drop_tables.py"


def patch(rel: str, old: str, new: str, subject: str, body: str, date: str) -> str:
    path = f"{PLACED_AT}/{rel}"
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{path}",
                                     f"b/{path}", n=3, lineterm=""))
    plus = sum(1 for ln in diff[2:] if ln.startswith("+"))
    minus = sum(1 for ln in diff[2:] if ln.startswith("-"))
    return (f"From 0000000000000000000000000000000000000000 Mon Sep 17 00:00:00 2001\n"
            f"From: Sam Teammate <sam@example.invalid>\n"
            f"Date: {date}\n"
            f"Subject: [PATCH] {subject}\n\n{body}\n---\n"
            f" {path} | {plus + minus} {'+' * plus}{'-' * minus}\n"
            f" 1 file changed, {plus} insertion{'s' if plus != 1 else ''}(+), "
            f"{minus} deletion{'s' if minus != 1 else ''}(-)\n\n"
            f"diff --git a/{path} b/{path}\n" + "\n".join(diff) + "\n")


def fixture_patches(gen: Gen) -> dict[str, str]:
    if covering_subfiles(gen, MAINT_FILE) != {"gdd/systems/loot.md",
                                              "gdd/systems/distributions.md"}:
        raise BuildError(f"{MAINT_FILE} covered by {covering_subfiles(gen, MAINT_FILE)}")
    pointers = [g for g in gen.root_pointers.values() if glob_re(g).match(CONTROL_FILE)]
    if covering_subfiles(gen, CONTROL_FILE) or pointers:
        raise BuildError(f"{CONTROL_FILE} is covered")
    old = gen.files[MAINT_FILE]
    new = old.replace('QUALITY_WEIGHTS = {"worn": 60, "sound": 30, "gleaming": 10}\n',
                      'QUALITY_WEIGHTS = {"worn": 60, "sound": 30, "gleaming": 10}\n'
                      '# One-in-N odds that a listed drop survives the fight.\n'
                      'DROP_KEEP_ODDS = 3\n')
    new = new.replace("rng.randrange(3) == 0", "rng.randrange(DROP_KEEP_ODDS) == 0")
    new = new.replace('"""Keep each listed drop on a one-in-three roll, then roll its quality."""',
                      '"""Keep each listed drop on a one-in-DROP_KEEP_ODDS roll, then roll its '
                      'quality."""')
    if new == old:
        raise BuildError("maintenance refactor did not apply")
    old_t = gen.files[CONTROL_FILE]
    new_t = old_t.replace('"""Smoke tests for loot/drop_tables.py."""',
                          '"""Smoke tests for loot/drop_tables.py.\n\n'
                          'Seeds are arbitrary; the assertions hold for any seed.\n"""')
    return {
        "s2_maintenance": patch(
            MAINT_FILE, old, new, "loot: name the drop keep-odds in roll_drops",
            "Behavior-preserving refactor: replace the literal 3 with a named constant.",
            "Wed, 30 Sep 2026 09:12:00 +0200"),
        "s2_negative_control": patch(
            CONTROL_FILE, old_t, new_t, "tests: note that the drop-table seeds are arbitrary",
            "Docstring only; no test changes.", "Wed, 30 Sep 2026 09:12:00 +0200"),
    }


# ---- prompts ------------------------------------------------------------------------------

REFERENCE_NOTE = (
    "Here a *reference* is a `{namespace.id}` token reference written in a YAML value: in a "
    "subfile's frontmatter, or in a content entity file under `examples/lanternfall/content/`. "
    "References in Markdown prose don't count. A reference to a sub-path (such as "
    "`{ns.id.field}`) is a reference to `{ns.id}`. A content entity's id is "
    "`{entities.<kind>.<id>}`.")


def answer_intro(task: str, n: int) -> str:
    what = "two questions" if n == 2 else "a question"
    return (f"Answer {what} about the Lanternfall design tree at `examples/lanternfall/`, and "
            f"write your answer{'s' if n == 2 else ''} to the file `answers/{task}.txt` "
            f"(relative to the repository root). Don't modify any other file.\n\n"
            f"{REFERENCE_NOTE}\n")


def answer_format(headers: list[str], example: str) -> str:
    lines = "\n".join(f"{h}:\n{example}\n{example}\n..." for h in headers)
    return ("Write the file in this format: each question's header on its own line, then one "
            f"id per line, and nothing else:\n\n{lines}\n")


def prompts(q: dict) -> dict[str, str]:
    f, b = q["s2_lookup_forward"], q["s2_lookup_backward"]
    x, y = q["s2_impact_tokens"]["Q1"]["start"], q["s2_impact_files"]["Q1"]["start"]
    out = {
        "s2_lookup_forward": answer_intro("s2_lookup_forward", 2) + f"""
Q1. Start at `{{{f['Q1']['start']}}}`. Which items do you reach by following exactly 2 references in a row?

Q2. Start at `{{{f['Q2']['start']}}}`. Which distributions do you reach by following exactly 3 references in a row?

""" + answer_format(["Q1", "Q2"], "{ns.id}"),
        "s2_lookup_backward": answer_intro("s2_lookup_backward", 2) + f"""
Q1. Which content entities (items, skills, monsters and encounters) reach `{{{b['Q1']['start']}}}` by following at most 2 references in a row?

Q2. Which content entities reach `{{{b['Q2']['start']}}}` by following at most 3 references in a row?

""" + answer_format(["Q1", "Q2"], "{entities.<kind>.<id>}"),
        "s2_impact_tokens": answer_intro("s2_impact_tokens", 1) + f"""
Q1. The value of `{{{x}}}` is about to change. List every token and content entity whose value references `{{{x}}}`, directly or transitively (through the values of other tokens and content entities). Don't list `{{{x}}}` itself. Use top-level token ids (for example `{{verbs.<id>}}`, not `{{verbs.<id>.effects}}`).

""" + answer_format(["Q1"], "{ns.id}"),
        "s2_impact_files": answer_intro("s2_impact_files", 1) + f"""
Q1. `{{{y}}}` is about to change. List every subfile (a file whose frontmatter declares `file_type: subfile`) that contains a token whose value references `{{{y}}}`, directly or transitively (through the values of other tokens and content entities). Write each path relative to `examples/lanternfall/`.

""" + answer_format(["Q1"], "<path>"),
    }
    maint = """A teammate has just committed a change under `examples/lanternfall/impl/` (it is the most recent commit in this repository).

Bring the Lanternfall design tree (`examples/lanternfall/`) back in sync with its implementation, following this repository's anti-drift ritual. If nothing in the design tree needs to change, leave it untouched.

Don't modify the implementation, and don't modify anything outside `examples/lanternfall/`. When you are done, the tree must lint clean (no errors, no warnings).
"""
    out["s2_maintenance"] = maint
    out["s2_negative_control"] = maint
    return out


# ---- output --------------------------------------------------------------------------------

PROVENANCE = ("Frozen answers for dogfood study 2 (D-026). Computed by generate.py from its "
              "planted edge list (edges.json), never by parsing the tree with gdmd code. "
              "tests/test_dogfood_study2.py cross-checks them once against gdmd graph / gdmd "
              "view and refs.walk_refs; a disagreement is fixed at its source, never by editing "
              "these files. Checkers compare against this file only.")


def render() -> dict[str, str]:
    """{path relative to this directory: text} for every generated file."""
    gen = Gen()
    gen.build()
    o = Oracle(gen)
    q = select_questions(gen, o)
    out = {f"tree/{p}": t for p, t in gen.files.items()}
    for task, text in prompts(q).items():
        out[f"prompts/{task}.md"] = text
    for task, text in fixture_patches(gen).items():
        out[f"patches/{task}.patch"] = text
    for task, questions in q.items():
        out[f"answers/{task}.json"] = json.dumps(
            {"_provenance": PROVENANCE, "task": task, "questions": questions},
            indent=2, sort_keys=True) + "\n"
    out["answers/s2_maintenance.json"] = json.dumps(
        {"_provenance": PROVENANCE, "task": "s2_maintenance",
         "patched": f"{PLACED_AT}/{MAINT_FILE}",
         "touched": sorted(f"{PLACED_AT}/{p}" for p in covering_subfiles(gen, MAINT_FILE))},
        indent=2, sort_keys=True) + "\n"
    out["answers/s2_negative_control.json"] = json.dumps(
        {"_provenance": PROVENANCE, "task": "s2_negative_control",
         "patched": f"{PLACED_AT}/{CONTROL_FILE}", "touched": []},
        indent=2, sort_keys=True) + "\n"
    out["edges.json"] = json.dumps(
        {"seed": SEED, "nodes": dict(sorted(gen.node_file.items())),
         "subfiles": sorted(gen.subfiles),
         "edges": [asdict(e) for e in gen.edges]}, indent=1, sort_keys=True) + "\n"
    return out


GENERATED_DIRS = ("tree", "prompts", "patches", "answers")


def frozen(base: Path = HERE) -> dict[str, str]:
    out = {}
    for d in GENERATED_DIRS:
        for p in sorted((base / d).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[p.relative_to(base).as_posix()] = p.read_text(encoding="utf-8")
    if (base / "edges.json").is_file():
        out["edges.json"] = (base / "edges.json").read_text(encoding="utf-8")
    return out


def write(out: dict[str, str], base: Path = HERE) -> None:
    for d in GENERATED_DIRS:
        for p in sorted((base / d).rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    for rel, text in out.items():
        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


# ---- D-026 §7: no leak from the in-context spec -------------------------------------------

V03_TAG = "v0.3.0"
V03_OVERLAY = ("CLAUDE.md", "AGENTS.md", "docs/spec.md", "schema", "src", "pyproject.toml")
IMPORT_RE = re.compile(r"(?:^|\s)@([\w./-]+)")
# The collection token names D-026 §3 fixes. They are never a question's
# start or answer, and no closure passes through them (they carry no
# references). The freeze amendment records this exemption.
LEAK_EXEMPT = {"entities.items", "entities.skills", "entities.monsters", "entities.encounters"}


def _read(repo: Path, rel: str, world: str) -> str | None:
    if world == "v0.3" and (rel in V03_OVERLAY or rel.split("/", 1)[0] in V03_OVERLAY):
        proc = subprocess.run(["git", "-C", str(repo), "show", f"{V03_TAG}:{rel}"],
                              capture_output=True, text=True)
        return proc.stdout if proc.returncode == 0 else None
    p = repo / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def imported_files(repo: Path, world: str) -> dict[str, str]:
    """Files CLAUDE.md @-imports (recursively) in a world. The matrix world
    includes both the full spec and the card: C2 imports one or the other."""
    seen: dict[str, str] = {}
    stack = ["CLAUDE.md"]
    if world == "matrix":
        stack += ["docs/spec.md", "docs/spec-card.md"]
    while stack:
        rel = stack.pop()
        if rel in seen:
            continue
        text = _read(repo, rel, world)
        if text is None:
            continue
        seen[rel] = text
        if rel.endswith(".md"):
            stack += [m.group(1).rstrip(".") for m in IMPORT_RE.finditer(text)]
    return seen


def leak_check(repo: Path, edges_json: dict) -> dict:
    ids = set(edges_json["nodes"])
    hits: dict[str, list[str]] = {}
    exempt: dict[str, list[str]] = {}
    for world in ("v0.3", "matrix"):
        for rel, text in imported_files(repo, world).items():
            for n in sorted(ids):
                bare = n.split(".")[-1]
                found = n in text or ("_" in bare and re.search(rf"\b{re.escape(bare)}\b", text))
                if found:
                    (exempt if n in LEAK_EXEMPT else hits).setdefault(n, []).append(
                        f"{world}:{rel}")
    return {"hits": hits, "exempt": exempt}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and compare with the frozen output")
    ap.add_argument("--leaks", action="store_true", help="run the D-026 §7 leak check")
    a = ap.parse_args(argv)
    if a.leaks:
        res = leak_check(HERE.parents[3], json.loads((HERE / "edges.json").read_text()))
        print(json.dumps(res, indent=2))
        return 1 if res["hits"] else 0
    out = render()
    if a.check:
        have = frozen()
        diff = sorted(set(out) ^ set(have)) + sorted(k for k in out if k in have
                                                      and out[k] != have[k])
        print("frozen output reproduced byte-for-byte" if not diff
              else f"differs: {diff[:10]} ({len(diff)} paths)")
        return 1 if diff else 0
    write(out)
    print(f"wrote {len(out)} files under {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
