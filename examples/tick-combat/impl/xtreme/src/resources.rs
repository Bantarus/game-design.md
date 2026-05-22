//! Realizes `{resources.*}` from `../../gdd/mechanics.md` and the spec's
//! global state. Bevy ECS `Resource` types — singletons in the world.
//!
//! `{resources.gold}` is integer-domain per `{invariants.gameplay_state_is_integer}`.

use bevy_ecs::prelude::*;

/// `{resources.gold}` — permanent, [0, 9999], hud-visible.
/// The bounds are normative; this struct just stores the current value.
/// Mutations clamp to [Gold::MIN, Gold::MAX].
#[derive(Resource, Debug, Clone, Copy)]
pub struct Gold(pub i32);

impl Gold {
    pub const MIN: i32 = 0;
    pub const MAX: i32 = 9999;

    pub fn add(&mut self, delta: i32) {
        self.0 = (self.0 + delta).clamp(Self::MIN, Self::MAX);
    }
}

/// Tick counter. The spec implies this exists (`{loops.tick}` is a per-tick
/// loop and "tick number" is named in `{invariants.gameplay_state_is_integer}`)
/// but doesn't declare a token for it. See `docs/v0.2-phase2-spec-ambiguities.md`.
#[derive(Resource, Debug, Clone, Copy, Default)]
pub struct TickCounter(pub u64);

/// The shared deterministic PRNG state. Wraps a single `ChaCha20Rng` seeded
/// once per encounter. Every distribution sample pulls from this — there is
/// only one stream of random bits per encounter, which is what makes the
/// Phase-3 byte-identical replay bar reachable.
#[derive(Resource)]
pub struct Rng(pub rand_chacha::ChaCha20Rng);
