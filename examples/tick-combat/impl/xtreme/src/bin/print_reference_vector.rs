//! Tiny utility: print the first N raw xoshiro256** outputs at canonical_seed.
//! Used to compute the spec's reference_vector for §4.7 and the per-tree
//! `prng:` declaration. Not part of the simulation; lives here purely so the
//! number that ends up in the spec was computed by the same code the engine
//! runs at adapter startup for self-validation.

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
    let mut rng = Xoshiro256StarStar::from_seed(seed);
    for _ in 0..n {
        println!("0x{:016x}", rng.next_u64());
    }
}
