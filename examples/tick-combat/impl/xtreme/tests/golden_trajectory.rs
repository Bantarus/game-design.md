//! Golden trajectory test — the Phase-3 in-engine determinism floor.
//!
//! Locks the seed-12345 demo encounter's per-tick trajectory as a text
//! fixture. The Simulation API is driven directly (no binary spawn); each
//! TickSnapshot is rendered via Debug and concatenated into one trajectory
//! string. Equality against `tests/golden_seed_12345.txt` proves:
//!
//!   - PRNG is platform-portable (ChaCha20 keyed by seed).
//!   - All spec resolutions land identically in each Rust build.
//!   - No floating-point divergence (integer-domain state per D-009).
//!
//! When the spec changes in a way that intentionally shifts the trajectory
//! (e.g. damage_roll parameters), regenerate the fixture by running:
//!
//!   ./target/debug/tick-combat --seed 12345 --ticks 100 --trace \
//!     > tests/golden_seed_12345.txt
//!
//! Phase 4's Unreal Blueprint implementation will produce its own canonical
//! integer trajectory that this Rust trajectory must match modulo serialization
//! format (see D-009 cross-engine bar).

use std::fs;

use tick_combat_xtreme::Simulation;
use tick_combat_xtreme::sim::SnapshotPhase;

const SEED: u64 = 12345;
const MAX_TICKS: u64 = 100;
const GOLDEN_PATH: &str = "tests/golden_seed_12345.txt";

fn run_trajectory(seed: u64, max_ticks: u64) -> String {
    let mut sim = Simulation::new(seed);
    sim.deploy_demo_roster();
    sim.start_combat();
    let mut out = String::new();
    out.push_str(&format!("{:?}\n", sim.snapshot()));
    for _ in 0..max_ticks {
        sim.step();
        let s = sim.snapshot();
        let resolved = matches!(s.phase, SnapshotPhase::Resolved);
        out.push_str(&format!("{:?}\n", s));
        if resolved {
            break;
        }
    }
    out
}

#[test]
fn golden_trajectory_seed_12345() {
    let actual = run_trajectory(SEED, MAX_TICKS);
    let expected = fs::read_to_string(GOLDEN_PATH).expect(
        "tests/golden_seed_12345.txt missing — regenerate via `./target/debug/tick-combat --seed 12345 --ticks 100 --trace > tests/golden_seed_12345.txt`",
    );
    if actual != expected {
        // Surface the first divergent line for fast debugging.
        let a_lines: Vec<&str> = actual.lines().collect();
        let e_lines: Vec<&str> = expected.lines().collect();
        for (i, (a, e)) in a_lines.iter().zip(e_lines.iter()).enumerate() {
            if a != e {
                panic!(
                    "trajectory diverged at line {} (tick {}):\n  expected: {}\n  actual:   {}",
                    i + 1,
                    i,
                    e,
                    a
                );
            }
        }
        panic!(
            "trajectory differs in length: actual={} lines, expected={} lines",
            a_lines.len(),
            e_lines.len()
        );
    }
}

#[test]
fn determinism_two_runs_match() {
    // Sanity belt-and-suspenders: two back-to-back runs with the same seed
    // produce the exact same trajectory string.
    let a = run_trajectory(SEED, MAX_TICKS);
    let b = run_trajectory(SEED, MAX_TICKS);
    assert_eq!(a, b, "two runs at the same seed produced different trajectories");
}

#[test]
fn different_seeds_diverge() {
    // Negative control: different seeds should not produce identical trajectories.
    let a = run_trajectory(1, MAX_TICKS);
    let b = run_trajectory(2, MAX_TICKS);
    assert_ne!(a, b, "two runs at different seeds produced identical trajectories");
}
