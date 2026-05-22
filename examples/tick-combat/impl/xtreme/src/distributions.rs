//! Realizes `{distributions.*}` from `../../gdd/systems/distributions.md`.
//!
//! Phase-4+ rewrite (D-015 + D-016 + D-017):
//!
//!   - PRNG is `xoshiro256_starstar + splitmix64` per D-015. Hand-rolled in
//!     `crate::prng`; no external rand crate. The reference vector at
//!     canonical_seed=0 is the cross-engine self-validation hook.
//!   - `damage_roll` is integer-native `discrete_sum` per D-016. Sum 3 PRNG
//!     draws each uniform int in [-1, +1], add `params_from.mean` (the
//!     actor's attack stat), clamp [1, 99]. No transcendentals → no IEEE-754
//!     ULP drift → no #15-class boundary flips.
//!   - `critical_hit` is integer uniform on [0, 9] with `selection_rule:
//!     less_than` threshold 1 (10% crit; semantically identical to the prior
//!     [0.0, 1.0] threshold 0.10 but no floats).
//!   - `gold_drop` uses integer weights (60/30/10 summing to 100) and the
//!     normative `declaration_order_first_above` selection rule (D-017):
//!     walk options in declaration order, first option whose cumulative
//!     running sum strictly exceeds the draw wins.
//!   - `action_order` (ordering_rule) unchanged — no PRNG involvement.
//!
//! All sampling pulls from a single `Xoshiro256StarStar` keyed by the
//! encounter seed via `splitmix64`. Identical seed → identical bit-stream
//! across every engine that implements the same algorithm.

use crate::components::{Side, Unit};
use crate::prng::Xoshiro256StarStar;
use bevy_ecs::entity::Entity;

// ---- `{distributions.action_order}` (ordering_rule) -------------------------
//
// Pure deterministic sort — no PRNG involvement. Spec declares:
//   over:   "{entities.units}"
//   filter: { lifecycle: alive }
//   sort:   [{by: speed, direction: desc}, {by: deploy_order, direction: asc}]

/// Returns alive entities in canonical order. Empty if no alive units.
pub fn action_order<'a>(units: impl IntoIterator<Item = (Entity, &'a Unit)>) -> Vec<Entity> {
    let mut alive: Vec<(Entity, &Unit)> = units
        .into_iter()
        .filter(|(_e, u)| matches!(u.lifecycle, crate::state::UnitLifecycle::Alive))
        .collect();
    alive.sort_by(|(_a, ua), (_b, ub)| {
        ub.speed
            .cmp(&ua.speed)
            .then_with(|| ua.deploy_order.cmp(&ub.deploy_order))
            // Cross-side tie-break (spec is silent; we pick Player < Enemy
            // as the canonical extension consistent with §9.5.5's
            // (side, deploy_order) trajectory sort).
            .then_with(|| (ua.side as u8).cmp(&(ub.side as u8)))
    });
    alive.into_iter().map(|(e, _)| e).collect()
}

// ---- `{distributions.damage_roll}` (discrete_sum) ---------------------------
//
// D-016 integer-native. Sum 3 PRNG draws each uniform int in [-1, +1], add
// `mean` (the actor's attack stat per D-012), clamp [1, 99]. Pure integer
// arithmetic — bit-identical across engines sharing xoshiro256**+splitmix64.

pub fn damage_roll(rng: &mut Xoshiro256StarStar, mean: i32) -> i32 {
    let mut sum: i32 = 0;
    for _ in 0..3 {
        sum += rng.uniform_int_inclusive(-1, 1);
    }
    (mean + sum).clamp(1, 99)
}

// ---- `{distributions.critical_hit}` (uniform + selection_rule) -------------
//
// D-016 + D-017 integer reformulation: integer uniform on [0, 9] inclusive,
// crit when `sample < threshold(1)`. 1-in-10 = 10% crit, semantically
// identical to the prior float [0.0, 1.0] threshold 0.10.

pub fn critical_hit(rng: &mut Xoshiro256StarStar) -> bool {
    let sample = rng.uniform_int_inclusive(0, 9);
    sample < 1
}

// ---- `{distributions.gold_drop}` (weighted, integer weights + D-017) -------
//
// Integer weights summing to 100; `selection_rule: declaration_order_first_above`.
// Declaration order: small (60), medium (30), large (10).
// Cumulative running sum: 60, 90, 100. Draw d = rng.next_u64() mod 100.
// First option whose c > d wins (strict greater-than).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GoldDrop {
    Small,
    Medium,
    Large,
}

impl GoldDrop {
    /// Per-category value per D-014.
    pub fn value(self) -> i32 {
        match self {
            GoldDrop::Small => 1,
            GoldDrop::Medium => 3,
            GoldDrop::Large => 10,
        }
    }
}

pub fn gold_drop(rng: &mut Xoshiro256StarStar) -> GoldDrop {
    // Integer weights in declaration order: small=60, medium=30, large=10.
    // total_weight = 100; draw in [0, 99].
    let draw: u64 = rng.next_u64() % 100;
    // Cumulative sums in declaration order.
    if 60u64 > draw {
        return GoldDrop::Small;
    }
    if 90u64 > draw {
        return GoldDrop::Medium;
    }
    GoldDrop::Large
}

// ---- Combat outcome helper (not a spec token) -------------------------------

/// `{invariants.units_act_only_when_alive}` — used by the tick loop to detect
/// `{events.one_side_cleared}`. Pure helper; advisory-status invariant.
pub fn one_side_cleared<'a>(units: impl IntoIterator<Item = &'a Unit>) -> bool {
    let mut p = 0;
    let mut e = 0;
    for u in units {
        if matches!(u.lifecycle, crate::state::UnitLifecycle::Dead) {
            continue;
        }
        match u.side {
            Side::Player => p += 1,
            Side::Enemy => e += 1,
        }
    }
    p == 0 || e == 0
}
