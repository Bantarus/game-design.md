//! Engine-A verify adapter for tick-combat (xtreme / Bevy ECS reference impl).
//!
//! Implements the §9.5.6 invocation contract:
//!
//!     verify-adapter --target <token-ref> --seed <int>
//!                    [--trajectory <path>] [--max-steps <int>]
//!
//! Writes canonical JSONL trajectory (§9.5.5) to `--trajectory` when supplied;
//! emits a `VerifyResult` JSON object (§9.5.3) to stdout. The shape and the
//! exit code are the engine-neutral contract — Phase 4's Unreal adapter must
//! implement the same contract and produce a byte-identical trajectory for
//! the same seed (the D-009 cross-engine bar).
//!
//! The adapter is *stateless across invocations*: one call = one target ×
//! seed. `gdmd verify` aggregates per-call results and decides pass/fail by
//! comparing the trajectory file against the declared golden fixture. The
//! adapter itself only OBSERVES — comparison logic lives in `gdmd verify`.

use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

use clap::Parser;
use tick_combat_xtreme::sim::SnapshotPhase;
use tick_combat_xtreme::Simulation;

#[derive(Parser, Debug)]
#[command(name = "verify-adapter", about = "tick-combat engine-A verify adapter (§9.5.6)")]
struct Cli {
    /// Token ref (e.g. {loops.combat_turn}) or literal axis name
    /// (e.g. build_health) when the verify_target has no target ref.
    #[arg(long)]
    target: String,

    /// Seed for the deterministic run. Same seed → byte-identical trajectory.
    #[arg(long)]
    seed: u64,

    /// Path to write canonical JSONL trajectory to (§9.5.5).
    #[arg(long)]
    trajectory: Option<PathBuf>,

    /// Cap on simulation length. Per-game default; generous so deterministic
    /// runs don't get prematurely truncated.
    #[arg(long, default_value_t = 500)]
    max_steps: u64,
}

fn main() {
    let args = Cli::parse();
    let result = if args.target == "build_health" {
        run_build_health()
    } else {
        run_behavioral_alignment(&args)
    };
    println!("{}", result);
}

fn run_build_health() -> String {
    // Reaching this point means cargo built the binary, the binary started,
    // and no asset/token resolution errors occurred. That IS build_health.
    let line = ResultLine {
        axis: "build_health",
        target: "build_health".to_string(),
        observed: r#"{"builds":true,"unresolved_refs":0}"#.to_string(),
        expected: "{}".to_string(),
        pass: true,
        notes: "adapter built and invoked".to_string(),
    };
    verify_result(vec![line])
}

fn run_behavioral_alignment(args: &Cli) -> String {
    let mut sim = Simulation::new(args.seed);
    sim.deploy_demo_roster();
    sim.start_combat();

    // tick=0 is the pre-step state at combat start; subsequent step()s yield
    // tick 1..N. The Resolved phase terminates the sim.
    let s0 = sim.snapshot();
    let mut lines: Vec<String> = vec![s0.to_canonical_jsonl()];
    let mut steps: u64 = 0;
    for _ in 0..args.max_steps {
        sim.step();
        steps += 1;
        let s = sim.snapshot();
        let resolved = matches!(s.phase, SnapshotPhase::Resolved);
        lines.push(s.to_canonical_jsonl());
        if resolved {
            break;
        }
    }
    let final_snap = sim.snapshot();

    if let Some(path) = &args.trajectory {
        let mut f = File::create(path)
            .unwrap_or_else(|e| panic!("verify-adapter: create {:?}: {}", path, e));
        for line in &lines {
            writeln!(f, "{}", line)
                .unwrap_or_else(|e| panic!("verify-adapter: write {:?}: {}", path, e));
        }
    }

    let observed = format!(
        r#"{{"terminal_gold":{},"terminal_phase":"{}","terminal_tick":{},"trajectory_lines":{}}}"#,
        final_snap.gold,
        phase_canonical(final_snap.phase),
        final_snap.tick,
        lines.len(),
    );
    let line = ResultLine {
        axis: "behavioral_alignment",
        target: args.target.clone(),
        observed,
        expected: "{}".to_string(),
        pass: true,
        notes: format!(
            "seed={} steps={} trajectory_lines={}",
            args.seed,
            steps,
            lines.len()
        ),
    };
    verify_result(vec![line])
}

struct ResultLine {
    axis: &'static str,
    target: String,
    observed: String,
    expected: String,
    pass: bool,
    notes: String,
}

fn verify_result(results: Vec<ResultLine>) -> String {
    let passed = results.iter().filter(|r| r.pass).count();
    let failed = results.iter().filter(|r| !r.pass).count();
    let runs = results.len();
    let parts: Vec<String> = results
        .iter()
        .map(|r| {
            format!(
                r#"{{"axis":"{}","expected":{},"notes":"{}","observed":{},"pass":{},"target":"{}"}}"#,
                r.axis,
                r.expected,
                escape_json_string(&r.notes),
                r.observed,
                r.pass,
                escape_json_string(&r.target),
            )
        })
        .collect();
    format!(
        r#"{{"results":[{}],"summary":{{"failed":{},"passed":{},"runs":{},"skipped":0}}}}"#,
        parts.join(","),
        failed,
        passed,
        runs,
    )
}

fn escape_json_string(s: &str) -> String {
    // Minimal escaping for the strings we emit. No control chars expected.
    s.replace('\\', r"\\").replace('"', "\\\"")
}

fn phase_canonical(p: SnapshotPhase) -> &'static str {
    match p {
        SnapshotPhase::Setup => "setup",
        SnapshotPhase::Ticking => "ticking",
        SnapshotPhase::Resolved => "resolved",
    }
}
