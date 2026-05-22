//! Realizes `{rules.tick_resolution}` and `{rules.combat_resolution}` from
//! `../../gdd/mechanics.md`. Stateless functions over the world, per
//! `{invariants.data_behavior_separation}` (advisory; this codebase honors it
//! by routing all state through Bevy ECS resources and components rather than
//! hiding state inside the rule functions).

use bevy_ecs::prelude::*;

use crate::components::{Side, Unit};
use crate::distributions::{action_order, critical_hit, damage_roll, gold_drop, one_side_cleared};
use crate::resources::{Gold, Rng, TickCounter};
use crate::state::{CombatPhase, Event, UnitLifecycle};

/// `{rules.tick_resolution}` — advance one tick.
///
/// Per the spec (gdd/mechanics.md tick_resolution.do):
///   1. sample {distributions.action_order}
///   2. resolve_unit_action            ← apply damage from first-acting unit to its target
///   3. sample {distributions.damage_roll} with round half_to_even
///   4. sample {distributions.critical_hit} on_hit_multiply_by 2
///   5. apply_damage_to_target integer_only
///
/// Spec ambiguity #5 (logged): step (2) "resolve_unit_action" is a step name,
/// not a defined rule. What is "the target"? The spec doesn't define target
/// selection. We pick: the first alive enemy on the opposite side, in
/// deployment order. Hand-rolled because nothing else is offered.
pub fn tick_resolution(world: &mut World) {
    // 1. action_order: rebuild every tick so it reflects deaths/stuns.
    let mut units_q = world.query::<(Entity, &Unit)>();
    let snapshot: Vec<(Entity, Unit)> = units_q
        .iter(world)
        .map(|(e, u)| (e, u.clone()))
        .collect();
    let order = action_order(snapshot.iter().map(|(e, u)| (*e, u)));
    let Some(&actor) = order.first() else {
        return; // no alive units; defer to combat_resolution
    };

    // 2. resolve_unit_action: pick a target.
    let Some(actor_unit) = snapshot.iter().find(|(e, _)| *e == actor).map(|(_, u)| u) else {
        return;
    };
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
        return;
    };

    // 3 & 4. roll damage + crit. Single PRNG stream; order matters.
    let mut rng_guard = world.resource_mut::<Rng>();
    let damage_raw = damage_roll(&mut rng_guard.0);
    let crit = critical_hit(&mut rng_guard.0);
    drop(rng_guard);

    // 5. apply (integer-only) — crit multiplies, hp clamps at 0.
    let final_damage = if crit { damage_raw * 2 } else { damage_raw };
    if let Some(mut t) = world.get_mut::<Unit>(target) {
        let new_hp = (t.hp - final_damage).max(0);
        t.hp = new_hp;
        if t.hp == 0 {
            t.lifecycle = t.lifecycle.step(Event::HpZero).unwrap_or(t.lifecycle);
        }
    }

    // Tick advances.
    world.resource_mut::<TickCounter>().0 += 1;
}

/// `{rules.combat_resolution}` — emit `{events.one_side_cleared}` when one
/// side has no live units, award gold, transition combat_phase to Resolved.
pub fn combat_resolution(world: &mut World) {
    let mut units_q = world.query::<&Unit>();
    let cleared = one_side_cleared(units_q.iter(world));
    if !cleared {
        return;
    }
    // Award gold via {distributions.gold_drop}. One drop per encounter for
    // now — spec ambiguity #6 (logged): the spec doesn't say how many drops.
    let drop = gold_drop(&mut world.resource_mut::<Rng>().0);
    world.resource_mut::<Gold>().add(drop.provisional_gold());
    *world.resource_mut::<CombatPhase>() = CombatPhase::Resolved;
}
