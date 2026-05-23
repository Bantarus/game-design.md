//! The `Simulation` entry point — the canonical surface the verify adapter
//! (Phase 3, separate crate) will drive.
//!
//! A `Simulation` wraps a Bevy ECS `World` with a fixed seed and provides
//! `new(seed)` → `step()` → `state_snapshot()`. The snapshot shape is the
//! canonical integer trajectory referenced by D-009's Phase-4 bar — both
//! engines (xtreme and Unreal in Phase 4) emit the same shape so trajectories
//! are directly comparable.

use bevy_ecs::prelude::*;

use crate::components::{Side, Unit, UnitRole};
use crate::loops::{run_encounter, tick as tick_loop};
use crate::prng::Xoshiro256StarStar;
use crate::resources::{Gold, Rng, TickCounter};
use crate::state::{CombatPhase, Event, UnitLifecycle};

pub struct Simulation {
    pub world: World,
}

/// One per-tick snapshot row of the canonical integer trajectory. Phase 4's
/// cross-engine equality check compares vectors of `TickSnapshot`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TickSnapshot {
    pub tick: u64,
    pub phase: SnapshotPhase,
    pub gold: i32,
    pub units: Vec<UnitSnapshot>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SnapshotPhase {
    Setup,
    Ticking,
    Resolved,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnitSnapshot {
    pub id: String,
    pub side: Side,
    pub deploy_order: u32,
    pub hp: i32,
    pub lifecycle: UnitLifecycle,
}

impl Simulation {
    pub fn new(seed: u64) -> Self {
        // Self-validate PRNG against the spec's reference vectors before any
        // simulation work — catch misimplementation before it produces
        // wrong-but-consistent trajectories. Raw vector first (catches PRNG
        // / seeding bugs); then reduction-layer vector (D-018, catches host-
        // language signedness bugs in `uniform_int_inclusive` — the F-007
        // failure mode, now a spec contract instead of a comment).
        crate::prng::reference_vector_self_check();
        crate::prng::uniform_int_reference_vector_self_check();
        let mut world = World::new();
        world.insert_resource(Rng(Xoshiro256StarStar::from_seed(seed)));
        world.insert_resource(Gold(0));
        world.insert_resource(TickCounter::default());
        world.insert_resource(CombatPhase::Setup);
        Self { world }
    }

    /// Phase-2 scaffold: deploy a tiny placeholder roster so the tick loop has
    /// something to run on. Real deployment will come from a content-driven
    /// setup step.
    pub fn deploy_demo_roster(&mut self) {
        let units = [
            // player side
            (
                "volt_marine",
                Side::Player,
                0_u32,
                20_i32,
                5_i32,
                7_i32,
                3_i32,
                UnitRole::RangedDps,
            ),
            (
                "shock_titan",
                Side::Player,
                1,
                60,
                12,
                3,
                6,
                UnitRole::TankMelee,
            ),
            (
                "spark_drone",
                Side::Player,
                2,
                8,
                2,
                9,
                2,
                UnitRole::Support,
            ),
            // enemy side — mirror roster for the demo
            (
                "volt_marine",
                Side::Enemy,
                0,
                20,
                5,
                7,
                3,
                UnitRole::RangedDps,
            ),
            (
                "shock_titan",
                Side::Enemy,
                1,
                60,
                12,
                3,
                6,
                UnitRole::TankMelee,
            ),
        ];
        for (id, side, deploy_order, hp, attack, speed, cost, role) in units {
            self.world.spawn(Unit {
                id: id.to_string(),
                hp,
                attack,
                speed,
                cost,
                role,
                side,
                deploy_order,
                lifecycle: UnitLifecycle::Alive,
            });
        }
    }

    /// Transition `{states.combat_phase}` to `Ticking` via
    /// `{events.start_combat}`. Idempotent for valid prior states.
    pub fn start_combat(&mut self) {
        let phase = *self.world.resource::<CombatPhase>();
        if let Some(next) = phase.step(Event::StartCombat) {
            *self.world.resource_mut::<CombatPhase>() = next;
        }
    }

    /// Run one tick (no-op if phase isn't Ticking).
    pub fn step(&mut self) {
        tick_loop(&mut self.world);
    }

    /// Run until terminal or cap.
    pub fn run(&mut self, max_ticks: u64) -> u64 {
        run_encounter(&mut self.world, max_ticks)
    }

    /// Capture the current canonical state for trajectory comparison.
    pub fn snapshot(&mut self) -> TickSnapshot {
        let tick = self.world.resource::<TickCounter>().0;
        let phase = match *self.world.resource::<CombatPhase>() {
            CombatPhase::Setup => SnapshotPhase::Setup,
            CombatPhase::Ticking => SnapshotPhase::Ticking,
            CombatPhase::Resolved => SnapshotPhase::Resolved,
        };
        let gold = self.world.resource::<Gold>().0;
        let mut units_q = self.world.query::<&Unit>();
        let mut units: Vec<UnitSnapshot> = units_q
            .iter(&self.world)
            .map(|u| UnitSnapshot {
                id: u.id.clone(),
                side: u.side,
                deploy_order: u.deploy_order,
                hp: u.hp,
                lifecycle: u.lifecycle,
            })
            .collect();
        // Canonical ordering — keep snapshots comparable across runs.
        units.sort_by(|a, b| {
            (a.side as u8, a.deploy_order).cmp(&(b.side as u8, b.deploy_order))
        });
        TickSnapshot { tick, phase, gold, units }
    }
}

impl Side {
    /// Stable ordering for canonical snapshots. (Not a spec concern;
    /// implementation detail for the trajectory format.)
    pub fn ord(self) -> u8 {
        match self {
            Side::Player => 0,
            Side::Enemy => 1,
        }
    }
}

impl TickSnapshot {
    /// Canonical JSONL serialization per spec §9.5.5.
    ///
    /// One JSON object per tick; keys sorted alphabetically; no extra
    /// whitespace; integer values; lowercase enum strings drawn from the
    /// closed set declared in `gdd/verification.md::trajectory.schema`.
    /// `units` is already sorted by (side, deploy_order) by `snapshot()`,
    /// so the iteration order matches the canonical sort.
    ///
    /// The output is a single line (no trailing newline). Callers append
    /// `\n` to write the file. Phase 4's Unreal Blueprint adapter MUST
    /// produce byte-identical output for the same `gdd/` tree and seed —
    /// this is the D-009 cross-engine integer-trajectory bar.
    pub fn to_canonical_jsonl(&self) -> String {
        let units_json: Vec<String> = self
            .units
            .iter()
            .map(|u| {
                format!(
                    r#"{{"deploy_order":{},"hp":{},"id":"{}","lifecycle":"{}","side":"{}"}}"#,
                    u.deploy_order,
                    u.hp,
                    u.id,
                    lifecycle_canonical(u.lifecycle),
                    side_canonical(u.side),
                )
            })
            .collect();
        format!(
            r#"{{"gold":{},"phase":"{}","tick":{},"units":[{}]}}"#,
            self.gold,
            phase_canonical(self.phase),
            self.tick,
            units_json.join(","),
        )
    }
}

fn phase_canonical(p: SnapshotPhase) -> &'static str {
    match p {
        SnapshotPhase::Setup => "setup",
        SnapshotPhase::Ticking => "ticking",
        SnapshotPhase::Resolved => "resolved",
    }
}

fn side_canonical(s: Side) -> &'static str {
    match s {
        Side::Player => "player",
        Side::Enemy => "enemy",
    }
}

fn lifecycle_canonical(l: UnitLifecycle) -> &'static str {
    match l {
        UnitLifecycle::Alive => "alive",
        UnitLifecycle::Stunned => "stunned",
        UnitLifecycle::Dead => "dead",
    }
}
