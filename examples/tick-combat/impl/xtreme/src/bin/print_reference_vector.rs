//! Tiny utility: print the first N raw xoshiro256** outputs at canonical_seed,
//! plus the first N `uniform_int_inclusive` outputs for the two adversarial
//! reduction-layer ranges (D-018). Used to compute the spec's reference vectors
//! for §4.8 and the per-tree `prng:` declaration. Not part of the simulation;
//! lives here purely so the numbers that end up in the spec were computed by
//! the same code the engine runs at adapter startup for self-validation.

use tick_combat_xtreme::prng::Xoshiro256StarStar;

fn main() {
    let seed: u64 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0);
    let n: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(5);

    // Raw u64 stream — the existing reference_vector layer (D-015).
    println!("# raw xoshiro256** outputs at canonical_seed={}", seed);
    let mut rng_raw = Xoshiro256StarStar::from_seed(seed);
    for _ in 0..n {
        println!("0x{:016x}", rng_raw.next_u64());
    }

    // Reduction layer — D-018. Two adversarial entries: a power-of-two w
    // (validates the reduction itself, bias-free) and a non-power-of-two w
    // (catches the naive-corrected `((raw % w) + w) % w` form on signed-int64
    // hosts, because `2^64 mod w ≠ 0` for non-power-of-two w). Adversarial
    // on draw #1: first raw at seed 0 has the high bit set (0x860bfe4fec669882),
    // so a wrong reduction fails at adapter startup, not at trajectory tick N.
    let n_red = std::env::args()
        .nth(3)
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or(8);
    for &(lo, hi, label) in &[
        (0i32, 7i32, "power-of-two w=8 (bias-free)"),
        (0i32, 6i32, "non-power-of-two w=7 (catches naive-corrected form)"),
    ] {
        println!();
        println!(
            "# uniform_int_inclusive({}, {}) at canonical_seed={}  -- {}",
            lo, hi, seed, label
        );
        let mut rng = Xoshiro256StarStar::from_seed(seed);
        let outputs: Vec<i32> = (0..n_red).map(|_| rng.uniform_int_inclusive(lo, hi)).collect();
        println!("{:?}", outputs);
    }
}
