# splitmix64 (Blackman & Vigna) — used to seed xoshiro256** from a single u64.
# See prng.gd for context. Sits in its own file because GDScript inner classes
# don't cleanly cross-reference outer class_names.

class_name SplitMix64
extends RefCounted

# Constants expressed as negative int64s (same bit pattern as the u64 originals,
# because GDScript's hex literal parser rejects values with the high bit set).
const GOLDEN_GAMMA: int = -0x61c8864680b583eb    # u64 0x9E3779B97F4A7C15
const M1: int = -0x40a7b892e31b1e4b              # u64 0xBF58476D1CE4E1B5
const M2: int = -0x6b2fb644ecceee15              # u64 0x94D049BB133111EB

var state: int = 0

func _init(seed_val: int) -> void:
	state = seed_val

func next() -> int:
	state = state + GOLDEN_GAMMA       # wraps at int64 == u64 wrap
	var z: int = state
	z = (z ^ _u64_shr(z, 30)) * M1
	z = (z ^ _u64_shr(z, 27)) * M2
	return z ^ _u64_shr(z, 31)

# Logical (unsigned-style) right shift on int64. GDScript `>>` is arithmetic
# (sign-extending); mask off the sign-extended top bits.
static func _u64_shr(x: int, k: int) -> int:
	if k <= 0:
		return x
	if k >= 64:
		return 0
	return (x >> k) & ((1 << (64 - k)) - 1)
