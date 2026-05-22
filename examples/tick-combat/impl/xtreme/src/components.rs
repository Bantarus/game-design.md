//! Realizes `{entities.*}` from `../../gdd/mechanics.md`.
//!
//! All quantities are integer-domain per `{invariants.gameplay_state_is_integer}`.
//! `Unit` carries the four stats declared in the `units` content-schema:
//! `hp`, `attack`, `speed`, `cost`. The `data_behavior_separation` invariant
//! is honored — these are pure data, no methods that mutate state.

use bevy_ecs::prelude::*;

use crate::state::UnitLifecycle;

/// `{entities.player}` — the actor. Bevy ECS treats this as a singleton-ish
/// entity; the player isn't a unit on the grid but owns the roster and gold.
#[derive(Component, Debug, Clone, Copy)]
pub struct Player;

/// `{entities.units}` — a single deployed unit. The `id` mirrors the
/// `content/units/<id>.yaml` filename stem; the stats here are the *current*
/// state during a combat, *initialized* from the content YAML at deploy time.
#[derive(Component, Debug, Clone)]
pub struct Unit {
    /// Stable id matching the content-entity filename stem.
    pub id: String,
    pub hp: i32,
    pub attack: i32,
    pub speed: i32,
    pub cost: i32,
    pub role: UnitRole,
    pub side: Side,
    /// 0-based deployment order — the tie-breaker for `{distributions.action_order}`.
    pub deploy_order: u32,
    pub lifecycle: UnitLifecycle,
}

/// `units.schema.role` enum from `gdd/content/units.md`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnitRole {
    TankMelee,
    RangedDps,
    Support,
    Hybrid,
}

/// Two-side combat. Spec says nothing explicit about side identity (encounters
/// are 1v1 squads); we name them here. This is presentational naming, not a
/// design choice.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Player,
    Enemy,
}
