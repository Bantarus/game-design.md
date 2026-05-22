//! Headless CLI: `tick-combat --seed <u64> [--ticks <n>]`.
//!
//! Phase-2 deliverable: prove the spec drives a real fixed-seed simulation
//! to completion. The verify adapter (Phase 3) sits above this binary and
//! emits VerifyResult JSON per the §9.5 contract; this binary itself only
//! prints the trajectory + summary for sanity inspection.

use clap::Parser;

use tick_combat_xtreme::Simulation;

#[derive(Parser, Debug)]
#[command(name = "tick-combat", about = "tick-combat / Lockstep — xtreme/Bevy ECS reference impl")]
struct Cli {
    /// Encounter seed. Same seed → byte-identical replay (the Phase-3 bar).
    #[arg(long, default_value_t = 12345)]
    seed: u64,

    /// Max ticks before forcing termination. Phase 2 default is generous.
    #[arg(long, default_value_t = 500)]
    ticks: u64,

    /// Print every tick's snapshot, not just the final state.
    #[arg(long)]
    trace: bool,
}

fn main() {
    let args = Cli::parse();

    let mut sim = Simulation::new(args.seed);
    sim.deploy_demo_roster();
    sim.start_combat();

    if args.trace {
        // Snapshot before any ticks, then after each.
        let s0 = sim.snapshot();
        println!("{:?}", s0);
        for _ in 0..args.ticks {
            sim.step();
            let s = sim.snapshot();
            println!("{:?}", s);
            if matches!(s.phase, tick_combat_xtreme::sim::SnapshotPhase::Resolved) {
                break;
            }
        }
    } else {
        let ticks_run = sim.run(args.ticks);
        let s = sim.snapshot();
        println!("seed={} ticks={} phase={:?} gold={}", args.seed, ticks_run, s.phase, s.gold);
        println!("units (final):");
        for u in &s.units {
            println!(
                "  {:?}/{} {} hp={} {:?}",
                u.side, u.deploy_order, u.id, u.hp, u.lifecycle
            );
        }
    }
}
