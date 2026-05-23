# D-015 / spec §4.7 PRNG pin: xoshiro256_starstar + splitmix64.
#
# Hand-implemented in pure GDScript so the algorithm IS the spec's algorithm,
# not Godot's built-in RandomNumberGenerator (which uses a different family
# whose constants don't match the spec's reference vector). The spec's
# reference vector at canonical_seed=0 is the cross-engine self-validation
# hook — this engine asserts the first 5 raw u64 outputs match the spec
# BEFORE running any simulation (catches a misimplementation immediately).
#
# GDScript int is signed int64. Bit operations and arithmetic wrap at int64
# bounds, which is equivalent to u64 wrapping for our purposes. The only
# subtlety is right shift: GDScript `>>` on int64 is arithmetic
# (sign-extending). For u64-equivalent logical right shift, we mask the
# upper bits via _u64_shr().

class_name Xoshiro256StarStar
extends RefCounted

const SplitMixModule := preload("res://src/splitmix64.gd")

# Spec reference vector at canonical_seed=0. GDScript's hex literal parser
# rejects values with the high bit set ("too large"), so we express each
# u64 with the top bit set as its negative int64 form (same bit pattern).
# Equality comparison below is bit-pattern equality regardless of sign.
const REFERENCE_VECTOR_SEED_0: Array = [
	-0x79f401b01399677e,    # u64 0x860bfe4fec669882
	-0x7d6321bcde4200e8,    # u64 0x829cde4321bdff18
	-0x2a83151178d87d37,    # u64 0xd57ceaee872782c9
	-0x3b803700a7ca69ef,    # u64 0xc47fc8ff58359611
	0x71718b5da1661407,
]

var _s: Array = [0, 0, 0, 0]   # 4×u64 state

func _init(seed_val: int) -> void:
	# Seed via splitmix64 — call 4× to fill xoshiro256**'s state.
	var sm := SplitMixModule.new(seed_val)
	_s[0] = sm.next()
	_s[1] = sm.next()
	_s[2] = sm.next()
	_s[3] = sm.next()

# u64-equivalent rotate-left on int64. Uses logical right shift for the
# wrap-around bits so the rotation is bit-pattern correct.
static func _rotl(x: int, k: int) -> int:
	return (x << k) | _u64_shr(x, 64 - k)

# Logical (unsigned-style) right shift on int64. GDScript `>>` is arithmetic
# (sign-extending); mask off the sign-extended top bits.
static func _u64_shr(x: int, k: int) -> int:
	if k <= 0:
		return x
	if k >= 64:
		return 0
	return (x >> k) & ((1 << (64 - k)) - 1)

# One raw u64 output from xoshiro256**.
func next_u64() -> int:
	# result = rotl(s[1] * 5, 7) * 9. Wrapping multiply at int64 == u64-wrap.
	var result: int = _rotl(_s[1] * 5, 7) * 9
	var t: int = _s[1] << 17
	_s[2] = _s[2] ^ _s[0]
	_s[3] = _s[3] ^ _s[1]
	_s[1] = _s[1] ^ _s[2]
	_s[0] = _s[0] ^ _s[3]
	_s[2] = _s[2] ^ t
	_s[3] = _rotl(_s[3], 45)
	return result

# Uniform integer in [lo, hi] inclusive. Mirrors xtreme's
# prng.rs::uniform_int_inclusive (which does u64-typed `next_u64() % width`).
#
# CRITICAL: GDScript int is signed int64; `raw % width` for raw < 0 returns
# a NEGATIVE remainder (truncated-modulo), which does NOT equal the u64
# modulo Rust computes. Naive `((raw % w) + w) % w` correction also fails
# because the signed-to-unsigned reinterpretation requires adding `2^64 mod w`
# when raw is negative.
#
# Correct formula: split raw into 32-bit halves, compute modulo via
# (hi32 * 2^32 + lo32) mod width. The mask `& 0xFFFFFFFF` discards the
# sign-extended bits of the arithmetic right shift, giving the true upper
# 32 bits of the u64 bit pattern as a non-negative int.
func uniform_int_inclusive(lo: int, hi: int) -> int:
	assert(hi >= lo)
	var width: int = hi - lo + 1
	var raw: int = next_u64()
	var hi32: int = (raw >> 32) & 0xFFFFFFFF
	var lo32: int = raw & 0xFFFFFFFF
	var two32_mod: int = (1 << 32) % width
	var u_mod: int = ((hi32 % width) * two32_mod + (lo32 % width)) % width
	return lo + u_mod

# Self-check the PRNG against the spec reference vector. Called at adapter
# startup; assert-fails with diagnostic output on mismatch.
# Note: passes the script via load() instead of `Xoshiro256StarStar.new(0)`
# directly because GDScript can't self-reference class_name inside the
# class body that bears it.
static func reference_vector_self_check() -> void:
	var script := load("res://src/prng.gd")
	var rng = script.new(0)
	for i in range(REFERENCE_VECTOR_SEED_0.size()):
		var expected: int = REFERENCE_VECTOR_SEED_0[i]
		var actual: int = rng.next_u64()
		if actual != expected:
			push_error(
				"PRNG reference vector mismatch at index %d: spec wants %d, this engine produced %d" % [
					i, expected, actual
				]
			)
			assert(false, "PRNG reference vector mismatch — see push_error above")

# D-018 / Phase 4++. Reduction-layer reference vectors at canonical_seed=0.
# This is the self-check that catches the F-007 GDScript-modulo bug at
# adapter startup — exactly the failure mode that previously survived to
# trajectory tick 2. Two entries: power-of-two w=8 (range [0,7]) and
# non-power-of-two w=7 (range [0,6]). Draw #1 at seed 0 is adversarial
# under both w's because the first raw u64 (0x860bfe4fec669882) has the
# high bit set, so the GDScript signed-int64 reinterpretation matters.
const REDUCTION_VECTOR_W8_SEED_0: Array = [2, 0, 1, 1, 7, 2, 5, 6]
const REDUCTION_VECTOR_W7_SEED_0: Array = [1, 1, 5, 6, 1, 5, 0, 3]

# Self-check uniform_int_inclusive against the spec's reduction-layer vector.
# Called at adapter startup immediately after reference_vector_self_check.
static func uniform_int_reference_vector_self_check() -> void:
	var script := load("res://src/prng.gd")
	# Power-of-two w (range [0, 7]).
	var rng_w8 = script.new(0)
	for i in range(REDUCTION_VECTOR_W8_SEED_0.size()):
		var expected: int = REDUCTION_VECTOR_W8_SEED_0[i]
		var actual: int = rng_w8.uniform_int_inclusive(0, 7)
		if actual != expected:
			push_error(
				"uniform_int reduction vector mismatch at (seed=0, range=[0,7]), index %d: spec wants %d, this engine produced %d" % [
					i, expected, actual
				]
			)
			assert(false, "uniform_int reduction vector mismatch (w=8) — see push_error above")
	# Non-power-of-two w (range [0, 6]). The entry that catches the
	# naive-corrected `((raw % w) + w) % w` form (which silently equals
	# the correct u64 modulo only when 2^64 mod w = 0 — i.e. only for
	# power-of-two w).
	var rng_w7 = script.new(0)
	for i in range(REDUCTION_VECTOR_W7_SEED_0.size()):
		var expected: int = REDUCTION_VECTOR_W7_SEED_0[i]
		var actual: int = rng_w7.uniform_int_inclusive(0, 6)
		if actual != expected:
			push_error(
				"uniform_int reduction vector mismatch at (seed=0, range=[0,6]), index %d: spec wants %d, this engine produced %d" % [
					i, expected, actual
				]
			)
			assert(false, "uniform_int reduction vector mismatch (w=7) — see push_error above")
