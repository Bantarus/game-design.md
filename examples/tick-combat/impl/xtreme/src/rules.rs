//! Realizes `{rules.tick_resolution}` and `{rules.combat_resolution}` from
//! `../../gdd/mechanics.md`. Phase-2.5 re-aligned to the *resolved* spec —
//! computable structured `do[]` items (D-011) drive the procedure here.
//!
//! Resolved spec shape (mechanics.md):
//!
//!   tick_resolution:
//!     given.driver: {clocks.tick}                # F-010 v0.3 resolution
//!     target_selection: first_alive_opposite     # D-013
//!     do:
//!       - kind: select_actor
//!         from: {distributions.action_order}
//!         index_by: tick_number                  # rotation, resolves #9
//!       - kind: sample
//!         from: {distributions.damage_roll}      # params_from actor.attack, D-012
//!         into: damage
//!       - kind: sample
//!         from: {distributions.critical_hit}
//!         into: crit
//!       - kind: apply_damage
//!         target: target
//!         amount: { base: damage, multiplier_if: { crit: 2 } }
//!         domain: integer
//!
//!   combat_resolution:
//!     given.verb: {verbs.resolve_combat}
//!     target_selection: none
//!     do:
//!       - kind: sample
//!         from: {distributions.gold_drop}
//!         count: 6                                # D-014, resolves #6
//!         accumulate: value
//!         into: total_gold
//!       - kind: gain_resource
//!         resource: {resources.gold}
//!         amount: total_gold

use bevy_ecs::prelude::*;

use crate::components::{Side, Unit};
use crate::distributions::{action_order, critical_hit, damage_roll, gold_drop, one_side_cleared};
use crate::resources::{Gold, Rng, TickCounter};
use crate::state::{CombatPhase, Event, UnitLifecycle};

/// `{rules.tick_resolution}` — advance one tick. Per the resolved spec:
///   1. select_actor by rotation through action_order (one unit per tick)
///   2. sample damage_roll with mean = actor.attack (D-012)
///   3. sample critical_hit
///   4. apply_damage to target (target_selection: first_alive_opposite, D-013)
pub fn tick_resolution(world: &mut World) {
    // Compute action_order snapshot for this tick.
    let mut units_q = world.query::<(Entity, &Unit)>();
    let snapshot: Vec<(Entity, Unit)> = units_q
        .iter(world)
        .map(|(e, u)| (e, u.clone()))
        .collect();
    let order = action_order(snapshot.iter().map(|(e, u)| (*e, u)));
    if order.is_empty() {
        return;
    }

    // (1) select_actor: rotation by tick_number. The actor at tick T is
    // order[T mod len(order)]. The rotation uses the *current* alive order;
    // when a unit dies the order shrinks and the rotation naturally moves on.
    let tick_n = world.resource::<TickCounter>().0 as usize;
    let actor = order[tick_n % order.len()];
    let actor_unit = snapshot
        .iter()
        .find(|(e, _)| *e == actor)
        .map(|(_, u)| u.clone())
        .expect("actor in order must exist in snapshot");

    // target_selection: first_alive_opposite (D-013). Pick the lowest
    // deploy_order alive unit on the opposite side.
    let opposite = match actor_unit.side {
        Side::Player => Side::Enemy,
        Side::Enemy => Side::Player,
    };
    let target: Option<Entity> = snapshot
        .iter()
        .filter(|(_e, u)| u.side == opposite && matches!(u.lifecycle, UnitLifecycle::Alive))
        .min_by_key(|(_e, u)| u.deploy_order)
        .map(|(e, _)| *e);
    let Some(target) = target else {
        // No alive opposite-side unit: combat_resolution will pick this up.
        // Still advance the tick counter so rotation moves on.
        world.resource_mut::<TickCounter>().0 += 1;
        return;
    };

    // (2) sample damage_roll with templated mean = actor.attack (D-012).
    let mut rng_guard = world.resource_mut::<Rng>();
    let damage = damage_roll(&mut rng_guard.0, actor_unit.attack);
    // (3) sample critical_hit.
    let crit = critical_hit(&mut rng_guard.0);
    drop(rng_guard);

    // (4) apply_damage.
    let final_damage = if crit { damage * 2 } else { damage };
    if let Some(mut t) = world.get_mut::<Unit>(target) {
        t.hp = (t.hp - final_damage).max(0);
        if t.hp == 0 {
            t.lifecycle = t.lifecycle.step(Event::HpZero).unwrap_or(t.lifecycle);
        }
    }

    world.resource_mut::<TickCounter>().0 += 1;
}

/// `{rules.combat_resolution}` — emit `{events.one_side_cleared}` when one
/// side has no live units, draw 6 gold_drop samples accumulating their
/// per-category values, award the total to gold, transition combat_phase
/// to Resolved.
pub fn combat_resolution(world: &mut World) {
    let mut units_q = world.query::<&Unit>();
    let cleared = one_side_cleared(units_q.iter(world));
    if !cleared {
        return;
    }
    // Skip if already resolved (idempotent).
    if *world.resource::<CombatPhase>() == CombatPhase::Resolved {
        return;
    }
    // 6 drops accumulating value (D-014, resolves #6).
    let mut total_gold: i32 = 0;
    {
        let mut rng_guard = world.resource_mut::<Rng>();
        for _ in 0..6 {
            let drop = gold_drop(&mut rng_guard.0);
            total_gold += drop.value();
        }
    }
    world.resource_mut::<Gold>().add(total_gold);
    *world.resource_mut::<CombatPhase>() = CombatPhase::Resolved;
}
