//! Realizes `{loops.*}` from `../../gdd/loops.md`.
//!
//! Three nested loops: `tick` (~100ms) inside `encounter` (~30-90s) inside
//! `campaign` (~20min). At the implementation level we only need to drive
//! `tick` and `encounter` — `campaign` is a meta-loop over encounters and is
//! the harness's responsibility, not this crate's.
//!
//! The tick loop's `sequence:` in the spec is `[{verbs.advance_tick}]` — a
//! single verb. We realize that verb by calling `rules::tick_resolution`.

use crate::resources::TickCounter;
use crate::rules::{combat_resolution, tick_resolution};
use crate::state::CombatPhase;
use bevy_ecs::prelude::*;

/// `{loops.tick}` — advance one tick. Single-rule wrapper for readability.
pub fn tick(world: &mut World) {
    if *world.resource::<CombatPhase>() != CombatPhase::Ticking {
        return;
    }
    tick_resolution(world);
    combat_resolution(world); // checks if one_side_cleared after the tick
}

/// `{loops.encounter}` — run ticks until the combat resolves OR the cap is hit.
/// Returns the tick count at termination.
pub fn run_encounter(world: &mut World, max_ticks: u64) -> u64 {
    while *world.resource::<CombatPhase>() == CombatPhase::Ticking {
        if world.resource::<TickCounter>().0 >= max_ticks {
            break;
        }
        tick(world);
    }
    world.resource::<TickCounter>().0
}
