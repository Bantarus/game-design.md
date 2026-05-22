//! Realizes `{distributions.*}` from `../../gdd/systems/distributions.md`.
//!
//! Phase-2.5 re-alignment: each function now implements the *resolved* spec
//! (not Phase-2's interpretations). Specifically:
//!
//!   - `action_order` is an `ordering_rule` (D-011/#1), not a `deterministic`
//!     literal sequence. Sort by speed desc, tie-break deploy_order asc,
//!     filter to alive. The rotation index (one unit per tick) is applied by
//!     `rules::tick_resolution`, not here.
//!   - `damage_roll` uses templated `mean = actor.attack` per D-012 / #8.
//!     The acting unit's `attack` stat is now load-bearing.
//!   - `critical_hit` uses normative `sample <= threshold` per spec §4.7.
//!   - `gold_drop` returns a `GoldDrop` *with its declared per-category value*
//!     drawn from the weighted options' `{ weight, value }` shape (D-014 / #4).
//!     `combat_resolution` requests `count: 6` drops (resolves #6) and
//!     accumulates the values.
//!
//! All sampling pulls from a single `ChaCha20Rng` keyed by the encounter
//! seed. Identical seed → identical bit-stream across machines.

use rand::Rng;
use rand_chacha::ChaCha20Rng;
use rand_distr::{Distribution as _, Normal};

use crate::components::{Side, Unit};
use bevy_ecs::entity::Entity;

// ---- `{distributions.action_order}` (ordering_rule) -------------------------
//
// D-011 / #1 resolution: this is now an *ordering procedure*, not a prose
// label. The spec declares:
//
//   over:   "{entities.units}"
//   filter: { lifecycle: alive }
//   sort:   [{by: speed, direction: desc}, {by: deploy_order, direction: asc}]
//
// Below is the executable realization.

/// Compute the deterministic action order. Returns alive Entities in the
/// canonical order. Empty if no alive units.
pub fn action_order<'a>(units: impl IntoIterator<Item = (Entity, &'a Unit)>) -> Vec<Entity> {
    let mut alive: Vec<(Entity, &Unit)> = units
        .into_iter()
        .filter(|(_e, u)| matches!(u.lifecycle, crate::state::UnitLifecycle::Alive))
        .collect();
    alive.sort_by(|(_a, ua), (_b, ub)| {
        ub.speed
            .cmp(&ua.speed)
            .then_with(|| ua.deploy_order.cmp(&ub.deploy_order))
            // Side is a stable secondary tie-break so player and enemy units
            // with identical (speed, deploy_order) get a fixed order.
            // (Spec is silent on cross-side tie-break; this is the canonical
            // choice — Player < Enemy.)
            .then_with(|| (ua.side as u8).cmp(&(ub.side as u8)))
    });
    alive.into_iter().map(|(e, _)| e).collect()
}

// ---- `{distributions.damage_roll}` ------------------------------------------
//
// `params_from: { mean: "{actor.attack}" }` per D-012. The `mean` argument
// below is the resolved actor-stat value at call site. stddev fixed at 1.
//
// Canonical order of operations (spec §4.7): sample → clamp continuous →
// round half-to-even → integer clamp.
pub fn damage_roll(rng: &mut ChaCha20Rng, mean: i32) -> i32 {
    let normal = Normal::new(mean as f64, 1.0_f64).expect("stddev > 0");
    let sample: f64 = normal.sample(rng);
    let clamped: f64 = sample.clamp(1.0, 99.0);
    let rounded: f64 = clamped.round_ties_even();
    (rounded as i32).clamp(1, 99)
}

// ---- `{distributions.critical_hit}` -----------------------------------------
//
// `range: [0.0, 1.0], threshold: 0.10`. Normative `sample <= threshold`
// per spec §4.7 (resolves #3).
pub fn critical_hit(rng: &mut ChaCha20Rng) -> bool {
    let sample: f64 = rng.random_range(0.0_f64..1.0_f64);
    sample <= 0.10
}

// ---- `{distributions.gold_drop}` --------------------------------------------
//
// Weighted with `{ weight, value }` options per D-014 (resolves #4):
//   small:  { weight: 0.6, value: 1 }
//   medium: { weight: 0.3, value: 3 }
//   large:  { weight: 0.1, value: 10 }
// Per-encounter count: 6 (declared on combat_resolution.do[].count).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GoldDrop {
    Small,
    Medium,
    Large,
}

impl GoldDrop {
    /// Per-category value, normatively declared in the spec (D-014).
    pub fn value(self) -> i32 {
        match self {
            GoldDrop::Small => 1,
            GoldDrop::Medium => 3,
            GoldDrop::Large => 10,
        }
    }
}

pub fn gold_drop(rng: &mut ChaCha20Rng) -> GoldDrop {
    let r: f64 = rng.random_range(0.0_f64..1.0_f64);
    if r < 0.6 {
        GoldDrop::Small
    } else if r < 0.9 {
        GoldDrop::Medium
    } else {
        GoldDrop::Large
    }
}

// ---- Combat outcome helpers (not a spec token) ------------------------------

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
