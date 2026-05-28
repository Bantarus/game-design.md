# Realizes {distributions.*} from ../../gdd/systems/distributions.md.
#
# Phase 4+ rewrite (D-015 + D-016 + D-017):
#
#   - PRNG is xoshiro256_starstar + splitmix64 per D-015. Hand-rolled in
#     src/prng.gd; NOT Godot's built-in RandomNumberGenerator. Reference
#     vector at canonical_seed=0 is the cross-engine self-validation hook.
#   - damage_roll is integer-native discrete_sum per D-016. Sum 3 PRNG
#     draws each uniform int in [-1, +1], add params_from.mean (the actor
#     attack stat), clamp [1, 99]. Zero transcendentals → bit-identical to
#     xtreme on the same seed.
#   - critical_hit is integer uniform [0, 9] with selection_rule: less_than
#     and threshold 1 (10% crit).
#   - gold_drop uses integer weights (60/30/10) summing to 100, with the
#     normative declaration_order_first_above selection rule (D-017):
#     walk options in declaration order, first option whose cumulative
#     running sum strictly exceeds the draw wins.

class_name Distributions
extends RefCounted

const PRNG := preload("res://src/prng.gd")

var rng

func _init(seed_val: int) -> void:
	rng = PRNG.new(seed_val)

# {distributions.action_order} — ordering_rule (D-013 / spec §4.8).
# Sort alive units by speed DESC, deploy_order ASC, side ASC tie-break.
# Pure deterministic — no PRNG involvement.
func action_order(units: Array) -> Array:
	var alive := []
	for u in units:
		if u.lifecycle == 0:  # Lifecycle.ALIVE
			alive.append(u)
	alive.sort_custom(func(a, b):
		if a.speed != b.speed:
			return a.speed > b.speed
		if a.deploy_order != b.deploy_order:
			return a.deploy_order < b.deploy_order
		return a.side < b.side
	)
	return alive

# {distributions.damage_roll} — discrete_sum per D-016.
# Sum 3 PRNG draws of uniform int [-1, +1], add mean (actor.attack per D-012),
# clamp [1, 99]. Variance = 3 * ((1-(-1)+1)^2 - 1)/12 = 2; stddev ≈ √2.
func damage_roll(actor_attack: int) -> int:
	var sum: int = 0
	for _i in range(3):
		sum += rng.uniform_int_inclusive(-1, 1)
	return clamp(actor_attack + sum, 1, 99)

# {distributions.critical_hit} — uniform [0, 9] + selection_rule: less_than.
# Crit when sample < 1 (i.e. sample == 0). 1-in-10 = 10% crit rate.
func critical_hit() -> bool:
	var sample: int = rng.uniform_int_inclusive(0, 9)
	return sample < 1

# {distributions.gold_drop} — weighted, integer weights, declaration_order_first_above.
# Declaration order: small (60), medium (30), large (10). total_weight = 100.
# Draw = rng.next_u64() mod 100; first option whose running cumulative sum
# strictly exceeds the draw wins. Cumulative sums: 60, 90, 100. Returns the
# integer value associated with the selected option.
func gold_drop() -> int:
	# u64(raw) mod 100 via 32-bit-halves split (see prng.gd::uniform_int_inclusive
	# for why naive `((raw % 100) + 100) % 100` is WRONG for negative raw).
	var raw: int = rng.next_u64()
	var hi32: int = (raw >> 32) & 0xFFFFFFFF
	var lo32: int = raw & 0xFFFFFFFF
	var two32_mod_100: int = (1 << 32) % 100
	var draw: int = ((hi32 % 100) * two32_mod_100 + (lo32 % 100)) % 100
	if 60 > draw:
		return 1   # small
	if 90 > draw:
		return 3   # medium
	return 10      # large

# {distributions.one_side_cleared} — pure predicate; non-stochastic.
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
