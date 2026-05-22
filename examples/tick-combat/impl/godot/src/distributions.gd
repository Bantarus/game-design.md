# Realizes {distributions.*} from ../../gdd/systems/distributions.md.
#
# **No pre-syncing to xtreme.** This is engine B's first-pass deterministic
# sampling implementation using Godot 4's NATIVE primitives:
#
#   - RandomNumberGenerator (Godot's PCG-family PRNG; xtreme uses ChaCha20).
#   - randfn(mean, stddev) for gaussian sampling (algorithm: Marsaglia
#     polar in Godot's core; xtreme uses Rust rand crate's Normal which
#     is also Marsaglia polar but with a different state machine).
#   - randf() for uniform-in-[0,1).
#   - Cumulative-sum weighted sampling for {distributions.gold_drop}.
#
# Per the Phase-4 discipline: every divergence is adjudicated against the
# spec, not against xtreme. If the spec doesn't pin the PRNG algorithm,
# spec gap (→ docs/v0.2-phase2-spec-ambiguities.md #12+). If the spec
# does pin a normative algorithm and Godot diverges, Godot is the bug.
#
# D-010 rounding (half_to_even, apply-time) is normative — implemented
# manually below because GDScript's round() is half-away-from-zero.

class_name Distributions
extends RefCounted

var rng: RandomNumberGenerator

func _init(seed: int) -> void:
	rng = RandomNumberGenerator.new()
	rng.seed = seed

# {distributions.action_order} — ordering_rule per spec §4.7 / D-013.
# Sort by speed DESC, then deploy_order ASC. Deterministic (no PRNG).
func action_order(units: Array) -> Array:
	var alive := []
	for u in units:
		if u.lifecycle == 0:  # Lifecycle.ALIVE
			alive.append(u)
	alive.sort_custom(func(a, b):
		if a.speed != b.speed:
			return a.speed > b.speed  # speed desc
		return a.deploy_order < b.deploy_order  # deploy_order asc tie-break
	)
	return alive

# {distributions.damage_roll} — gaussian with params_from.mean = {actor.attack}.
# stddev=1, clamp [1,99], output_domain=integer, round_mode=half_to_even.
# Spec §4.7 canonical order: sample → clamp continuous → round half-to-even
# → integer clamp.
func damage_roll(actor_attack: int) -> int:
	var sample: float = rng.randfn(float(actor_attack), 1.0)
	# (1) Clamp in continuous space (spec D-010 canonical order).
	sample = clamp(sample, 1.0, 99.0)
	# (2) Round half-to-even (banker's rounding).
	var rounded: int = _round_half_to_even(sample)
	# (3) Integer clamp (belt-and-suspenders).
	return clamp(rounded, 1, 99)

# {distributions.critical_hit} — uniform [0,1) with threshold 0.10.
# Spec §4.7 normative: sample <= threshold (inclusive at threshold).
func critical_hit() -> bool:
	var sample: float = rng.randf()
	return sample <= 0.10

# {distributions.gold_drop} — weighted with value-bearing options (D-014).
# Categories: small (w=0.6, v=1), medium (w=0.3, v=3), large (w=0.1, v=10).
# Returns the value (int gold), not the category.
func gold_drop() -> int:
	var sample: float = rng.randf()
	# Cumulative-sum sampling. Order matters for cross-engine determinism:
	# spec doesn't pin the iteration order, so this is a candidate spec
	# gap (#12 territory) — declared here as alphabetical-key iteration
	# of the source map. Godot's Dictionary doesn't preserve insertion
	# order across engines either, so explicit declaration is safer.
	if sample < 0.6:
		return 1   # small
	if sample < 0.6 + 0.3:
		return 3   # medium
	return 10      # large

# {distributions.one_side_cleared} — pure predicate; non-stochastic.
# Returns true iff at least one side has zero alive units.
func one_side_cleared(units: Array) -> bool:
	var player_alive := 0
	var enemy_alive := 0
	for u in units:
		if u.lifecycle != 0:  # not Lifecycle.ALIVE
			continue
		if u.side == 0:  # Side.PLAYER
			player_alive += 1
		else:
			enemy_alive += 1
	return player_alive == 0 or enemy_alive == 0

# half_to_even (banker's rounding) per D-010. GDScript's built-in round()
# is half-away-from-zero — must implement manually for spec compliance.
static func _round_half_to_even(x: float) -> int:
	var floor_v: int = int(floor(x))
	var diff: float = x - float(floor_v)
	if diff < 0.5:
		return floor_v
	if diff > 0.5:
		return floor_v + 1
	# Exactly .5: round to even.
	if floor_v % 2 == 0:
		return floor_v
	return floor_v + 1
