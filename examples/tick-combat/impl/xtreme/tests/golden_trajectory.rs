//! Golden trajectory test — the Phase-3 in-engine determinism floor.
//!
//! Locks the seed-12345 demo encounter's per-tick trajectory as a canonical
//! JSONL fixture per spec §9.5.5. Each tick is one JSON object on one line;
//! keys are sorted alphabetically; values are integers; enum strings are
//! lowercased. Phase 4's Unreal Blueprint adapter MUST produce byte-identical
//! output for the same seed — the D-009 cross-engine integer-trajectory bar.
//!
//! The Simulation API is driven directly (no binary spawn); each TickSnapshot
//! is rendered via `to_canonical_jsonl()` (the same serializer the
//! verify-adapter binary uses). Equality against
//! `tests/golden_seed_12345.jsonl` proves:
//!
//!   - PRNG is platform-portable (ChaCha20 keyed by seed).
//!   - All spec resolutions land identically in each Rust build.
//!   - No floating-point divergence (integer-domain state per D-009).
//!   - The canonical JSONL serializer is stable.
//!
//! When the spec changes in a way that intentionally shifts the trajectory
//! (e.g. damage_roll parameters), regenerate the fixture by running:
//!
//!   cd examples/tick-combat
//!   ./tools/verify-adapter --target '{loops.combat_turn}' --seed 12345 \
//!     --trajectory impl/xtreme/tests/golden_seed_12345.jsonl

use std::fs;

use tick_combat_xtreme::sim::SnapshotPhase;
use tick_combat_xtreme::Simulation;

const SEED: u64 = 12345;
const MAX_TICKS: u64 = 100;
const GOLDEN_PATH: &str = "tests/golden_seed_12345.jsonl";

/// Render a trajectory in canonical JSONL: one snapshot per line, trailing
/// newline. Matches the `verify-adapter` binary's output byte-for-byte.
fn run_trajectory(seed: u64, max_ticks: u64) -> String {
    let mut sim = Simulation::new(seed);
    sim.deploy_demo_roster();
    sim.start_combat();
    let mut out = String::new();
    out.push_str(&sim.snapshot().to_canonical_jsonl());
    out.push('\n');
    for _ in 0..max_ticks {
        sim.step();
        let s = sim.snapshot();
        let resolved = matches!(s.phase, SnapshotPhase::Resolved);
        out.push_str(&s.to_canonical_jsonl());
        out.push('\n');
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
        "tests/golden_seed_12345.jsonl missing — regenerate via \
         `./tools/verify-adapter --target '{loops.combat_turn}' --seed 12345 \
         --trajectory impl/xtreme/tests/golden_seed_12345.jsonl` from \
         examples/tick-combat",
    );
    if actual != expected {
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
    // Belt-and-suspenders: two back-to-back runs with the same seed produce
    // the exact same trajectory string (byte-identical).
    let a = run_trajectory(SEED, MAX_TICKS);
    let b = run_trajectory(SEED, MAX_TICKS);
    assert_eq!(a, b, "two runs at the same seed produced different trajectories");
}

#[test]
fn different_seeds_diverge() {
    // Negative control (spec §9.5.7 in miniature): different seeds must not
    // produce identical trajectories. Without this assertion the determinism
    // test would pass vacuously if the implementation ignored the seed.
    let a = run_trajectory(1, MAX_TICKS);
    let b = run_trajectory(2, MAX_TICKS);
    assert_ne!(a, b, "two runs at different seeds produced identical trajectories");
}
