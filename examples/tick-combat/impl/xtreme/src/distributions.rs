//! Realizes `{distributions.*}` from `../../gdd/systems/distributions.md`.
//!
//! All sampling pulls from a single `ChaCha20Rng` keyed by the encounter
//! seed (see [`crate::resources::Rng`]). Per D-009 / D-010:
//!
//!   - Gameplay state is integer-domain. The gaussian below is the *only*
//!     real-valued sampler; its output is rounded half-to-even at apply.
//!   - PRNG output is platform-portable: identical seed → identical bit-stream
//!     across machines. ChaCha20 is the canonical choice for that.
//!
//! Each function takes `&mut ChaCha20Rng` rather than `&mut World` so the
//! call site decides when to advance the stream — order-of-sampling matters
//! for determinism.

use rand::Rng;
use rand_chacha::ChaCha20Rng;
use rand_distr::{Distribution as _, Normal};

use crate::components::{Side, Unit};
use bevy_ecs::entity::Entity;

// ---- `{distributions.action_order}` -----------------------------------------
//
// `type: deterministic`. The spec's `sequence:` is a *rule* ("highest_speed_first",
// "tie_break_by_deployment_order"), not a literal list of unit ids. Spec
// ambiguity #1 (logged): the `deterministic` distribution type is documented as
// "literal sequence" in the spec but is used here as "deterministic ordering
// rule." We realize it as a sort.

/// Order the alive (or stunned) roster by speed desc, tie-break by deployment
/// order asc. Dead units are excluded — they don't act.
/// Returns (Entity, &Unit) pairs in action order for one tick.
pub fn action_order<'a>(units: impl IntoIterator<Item = (Entity, &'a Unit)>) -> Vec<Entity> {
    let mut alive: Vec<(Entity, &Unit)> = units
        .into_iter()
        .filter(|(_e, u)| matches!(u.lifecycle, crate::state::UnitLifecycle::Alive))
        .collect();
    // Stable sort: speed desc, then deploy_order asc.
    alive.sort_by(|(_a, ua), (_b, ub)| {
        ub.speed
            .cmp(&ua.speed)
            .then_with(|| ua.deploy_order.cmp(&ub.deploy_order))
    });
    alive.into_iter().map(|(e, _)| e).collect()
}

// ---- `{distributions.damage_roll}` ------------------------------------------
//
// `type: gaussian, mean: 5, stddev: 1, clamp: [1, 99]`,
// `output_domain: integer, round_mode: half_to_even`.
//
// Order of operations (spec is silent on clamp-before-round vs round-before-clamp;
// logged as spec ambiguity #2):
//   1. sample float from N(5, 1)
//   2. clamp to [1.0, 99.0]    ← clamp on the continuous sample
//   3. round half-to-even      ← apply-time rounding per D-010
//   4. clamp to [1, 99]        ← belt-and-suspenders post-round
//
// The clamp-first ordering preserves the gaussian's tail behavior near the
// boundaries without pinning ties weirdly.

pub fn damage_roll(rng: &mut ChaCha20Rng) -> i32 {
    // Normal is constructed only once per call to avoid allocation; safe
    // because parameters are constants.
    let normal = Normal::new(5.0_f64, 1.0_f64).expect("stddev > 0");
    let sample: f64 = normal.sample(rng);
    let clamped: f64 = sample.clamp(1.0, 99.0);
    let rounded: f64 = clamped.round_ties_even();
    (rounded as i32).clamp(1, 99)
}

// ---- `{distributions.critical_hit}` -----------------------------------------
//
// `type: uniform, range: [0.0, 1.0], threshold: 0.10`. Returns true iff
// sample <= threshold (10% crit rate).
//
// Spec ambiguity #3 (logged): <= vs <. We pick <=, the conventional choice;
// at the boundary the probability mass is zero for a continuous uniform, but
// for finite-precision floats this matters at the edge cases. The integer
// reformulation (D-010 follow-up) would make it unambiguous.

pub fn critical_hit(rng: &mut ChaCha20Rng) -> bool {
    let sample: f64 = rng.random_range(0.0_f64..1.0_f64);
    sample <= 0.10
}

// ---- `{distributions.gold_drop}` --------------------------------------------
//
// `type: weighted, options: {small: 0.6, medium: 0.3, large: 0.1}`.
//
// Spec ambiguity #4 (logged): the weighted distribution returns a category
// label (small/medium/large) — what gold value does each map to? The spec
// doesn't say. We pick (1, 3, 10) here as an interpretation that averages
// 0.6*1 + 0.3*3 + 0.1*10 = 2.5 gold per drop. Total per-encounter expectation
// depends on how many drops per encounter, also unspecified. Phase 2 forces
// the question to be answered; the answer belongs in the spec, not here.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GoldDrop {
    Small,
    Medium,
    Large,
}

impl GoldDrop {
    /// Provisional gold value per category. SPEC AMBIGUITY #4 — these numbers
    /// are an interpretation, not a normative quote.
    pub fn provisional_gold(self) -> i32 {
        match self {
            GoldDrop::Small => 1,
            GoldDrop::Medium => 3,
            GoldDrop::Large => 10,
        }
    }
}

pub fn gold_drop(rng: &mut ChaCha20Rng) -> GoldDrop {
    // Uniform [0.0, 1.0). The weights are bucketed: 0..0.6 small, 0.6..0.9 medium, 0.9..1.0 large.
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
