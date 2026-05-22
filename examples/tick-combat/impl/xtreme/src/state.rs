//! Realizes `{states.*}` machines and `{events.*}` from `../../gdd/mechanics.md`.
//!
//! State machines are typed enums with explicit transitions. The transition
//! tables here are the *truthful realization* of the YAML in the spec; if
//! they disagree, the YAML wins and this file is wrong.

use bevy_ecs::prelude::*;

/// `{states.unit_lifecycle}` — per-unit machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnitLifecycle {
    Alive,
    Stunned,
    Dead, // terminal
}

impl Default for UnitLifecycle {
    fn default() -> Self {
        // `initial: alive` per the spec.
        UnitLifecycle::Alive
    }
}

/// `{states.combat_phase}` — global per-combat machine, stored as a Bevy
/// `Resource`.
#[derive(Resource, Debug, Clone, Copy, PartialEq, Eq)]
pub enum CombatPhase {
    Setup,
    Ticking,
    Resolved, // terminal
}

impl Default for CombatPhase {
    fn default() -> Self {
        // `initial: setup` per the spec.
        CombatPhase::Setup
    }
}

/// `{events.*}` — emitted by verbs/rules, consumed by state-machine transitions.
/// One enum holds the events from both machines because Bevy ECS event types
/// are independent regardless of which state they target.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Event {
    // unit_lifecycle
    Stun,
    Recover,
    HpZero,
    // combat_phase
    StartCombat,
    OneSideCleared,
}

impl UnitLifecycle {
    /// Apply an event; return Some(new_state) if the transition is declared,
    /// else None (the event is irrelevant in this state).
    pub fn step(self, ev: Event) -> Option<Self> {
        use UnitLifecycle::*;
        match (self, ev) {
            (Alive, Event::Stun) => Some(Stunned),
            (Stunned, Event::Recover) => Some(Alive),
            (Alive, Event::HpZero) => Some(Dead),
            (Stunned, Event::HpZero) => Some(Dead),
            // Dead is terminal; no transitions out.
            _ => None,
        }
    }
}

impl CombatPhase {
    pub fn step(self, ev: Event) -> Option<Self> {
        use CombatPhase::*;
        match (self, ev) {
            (Setup, Event::StartCombat) => Some(Ticking),
            (Ticking, Event::OneSideCleared) => Some(Resolved),
            _ => None,
        }
    }
}
