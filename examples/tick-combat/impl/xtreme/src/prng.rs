//! D-015 / spec §4.7 PRNG pin: `xoshiro256_starstar + splitmix64`.
//!
//! Hand-implemented (no `rand` crate dependency) so the algorithm is
//! exactly the spec's algorithm, not whichever variant the crate ships
//! at any given version. This makes the engine self-validate against
//! the spec's reference vector before any trajectory comparison.
//!
//! - xoshiro256** — Blackman & Vigna, 2018. State: 4×u64. Output:
//!   `rotl(s1 * 5, 7) * 9`. Update: see `next_u64`. Reference at
//!   https://prng.di.unimi.it/xoshiro256starstar.c.
//! - splitmix64 — same authors. Seeds xoshiro from a single u64.

/// xoshiro256** PRNG state. 4×u64.
#[derive(Debug, Clone)]
pub struct Xoshiro256StarStar {
    s: [u64; 4],
}

impl Xoshiro256StarStar {
    /// Seed the PRNG from a single u64 via `splitmix64`. Calling four times
    /// from the initial seed fills the 4×u64 state.
    pub fn from_seed(seed: u64) -> Self {
        let mut sm = SplitMix64::new(seed);
        Self {
            s: [sm.next(), sm.next(), sm.next(), sm.next()],
        }
    }

    /// One raw u64 output. The spec's reference_vector compares the first N
    /// of these at `canonical_seed: 0`.
    pub fn next_u64(&mut self) -> u64 {
        let result = self.s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        result
    }

    /// Uniform integer in `[lo, hi]` inclusive, drawn from one `next_u64`.
    /// Bias-uniform via modulo on a u64 — exact across engines that share
    /// the same `next_u64`. Range up to `i32::MAX − i32::MIN + 1` is safe.
    pub fn uniform_int_inclusive(&mut self, lo: i32, hi: i32) -> i32 {
        debug_assert!(hi >= lo, "uniform_int_inclusive: hi >= lo required");
        let width: u64 = (hi as i64 - lo as i64 + 1) as u64;
        let r: u64 = self.next_u64() % width;
        (lo as i64 + r as i64) as i32
    }
}

/// splitmix64 (Blackman & Vigna). Seeds xoshiro from a single u64.
pub struct SplitMix64 {
    state: u64,
}

impl SplitMix64 {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    pub fn next(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E1B5);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
}

/// Spec reference vector at `canonical_seed: 0`. Both engines MUST produce
/// these first 5 raw u64s — divergence here means the PRNG or seeding is
/// misimplemented, not a trajectory bug.
pub const REFERENCE_VECTOR_SEED_0: [u64; 5] = [
    0x860bfe4fec669882,
    0x829cde4321bdff18,
    0xd57ceaee872782c9,
    0xc47fc8ff58359611,
    0x71718b5da1661407,
];

/// Self-check the PRNG against the spec's reference vector. Called at adapter
/// startup; panics on mismatch with diagnostic output.
pub fn reference_vector_self_check() {
    let mut rng = Xoshiro256StarStar::from_seed(0);
    for (i, expected) in REFERENCE_VECTOR_SEED_0.iter().enumerate() {
        let actual = rng.next_u64();
        assert_eq!(
            actual, *expected,
            "PRNG reference vector mismatch at index {}: spec wants {:#018x}, this engine produced {:#018x}",
            i, expected, actual
        );
    }
}

/// D-018: reduction-layer reference vectors at `canonical_seed: 0`. Two
/// entries — one power-of-two `w` (validates the reduction itself, bias-free)
/// and one non-power-of-two `w` (catches the naive-corrected form on a
/// signed-int64 host, which silently equals u64 modulo only when 2^64 mod w
/// = 0). Draw #1 is adversarial under both `w`s: first raw at seed 0 has
/// the high bit set, so a wrong reduction fails at adapter startup rather
/// than at trajectory tick N (the failure mode F-007 caught at tick 2).
pub const REDUCTION_REFERENCE_VECTOR_W8_SEED_0: [i32; 8] = [2, 0, 1, 1, 7, 2, 5, 6];
pub const REDUCTION_REFERENCE_VECTOR_W7_SEED_0: [i32; 8] = [1, 1, 5, 6, 1, 5, 0, 3];

/// Self-check `uniform_int_inclusive` against the spec's reduction-layer
/// reference vectors. Called at adapter startup immediately after
/// `reference_vector_self_check`. Panics on mismatch with diagnostic output.
pub fn uniform_int_reference_vector_self_check() {
    // Power-of-two w (range [0, 7]; w = 8).
    {
        let mut rng = Xoshiro256StarStar::from_seed(0);
        for (i, expected) in REDUCTION_REFERENCE_VECTOR_W8_SEED_0.iter().enumerate() {
            let actual = rng.uniform_int_inclusive(0, 7);
            assert_eq!(
                actual, *expected,
                "uniform_int reduction vector mismatch at (seed=0, range=[0,7]), index {}: spec wants {}, this engine produced {}",
                i, expected, actual
            );
        }
    }
    // Non-power-of-two w (range [0, 6]; w = 7). This is the entry that catches
    // the naive-corrected `((raw % w) + w) % w` form on signed-int64 hosts.
    {
        let mut rng = Xoshiro256StarStar::from_seed(0);
        for (i, expected) in REDUCTION_REFERENCE_VECTOR_W7_SEED_0.iter().enumerate() {
            let actual = rng.uniform_int_inclusive(0, 6);
            assert_eq!(
                actual, *expected,
                "uniform_int reduction vector mismatch at (seed=0, range=[0,6]), index {}: spec wants {}, this engine produced {}",
                i, expected, actual
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_vector_matches() {
        reference_vector_self_check();
    }

    #[test]
    fn uniform_int_reference_vector_matches() {
        uniform_int_reference_vector_self_check();
    }

    #[test]
    fn same_seed_same_stream() {
        let mut a = Xoshiro256StarStar::from_seed(12345);
        let mut b = Xoshiro256StarStar::from_seed(12345);
        for _ in 0..100 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn different_seeds_diverge_immediately() {
        let mut a = Xoshiro256StarStar::from_seed(12345);
        let mut b = Xoshiro256StarStar::from_seed(99999);
        // First outputs differ — proves the seed actually parameterizes state.
        assert_ne!(a.next_u64(), b.next_u64());
    }
}
