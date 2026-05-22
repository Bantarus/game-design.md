//! tick-combat (Lockstep) — xtreme/Bevy ECS implementation.
//!
//! Every public type/function in this crate maps to a token in the sibling
//! `gdd/` tree. The crate contains no design value; reading the design
//! requires reading `../../gdd/`, not the source here.
//!
//! Module map:
//!   - [`components`] : `{entities.*}` data-only structures
//!   - [`resources`]  : `{resources.*}` global ECS resources
//!   - [`distributions`] : the four `{distributions.*}` + shared PRNG
//!   - [`state`]      : `{states.*}` machines + `{events.*}` enum
//!   - [`rules`]      : `{rules.*}` — pure functions over the world
//!   - [`loops`]      : `{loops.*}` schedule wiring
//!   - [`sim`]        : the `Simulation` entry point the verify adapter drives

pub mod components;
pub mod distributions;
pub mod loops;
pub mod prng;
pub mod resources;
pub mod rules;
pub mod sim;
pub mod state;

pub use sim::Simulation;
