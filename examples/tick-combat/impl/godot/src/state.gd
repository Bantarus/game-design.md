# Realizes {states.combat_phase} from ../../gdd/mechanics.md as a flat enum.
# The state machine is total (setup → ticking → resolved); transitions are
# driven by step() applied to {events.<id>} tokens.

class_name CombatPhase
extends RefCounted

const SETUP := 0
const TICKING := 1
const RESOLVED := 2

static func canonical(p: int) -> String:
	match p:
		SETUP: return "setup"
		TICKING: return "ticking"
		RESOLVED: return "resolved"
		_: return "unknown"

# Event names mirror {events.*} in mechanics.md.
class Event:
	const START_COMBAT := 0
	const ONE_SIDE_CLEARED := 1
	const STUN := 2
	const RECOVER := 3
	const HP_ZERO := 4

# CombatPhase transitions, per gdd/mechanics.md::states.combat_phase.
static func step(phase: int, event: int) -> int:
	if phase == SETUP and event == Event.START_COMBAT:
		return TICKING
	if phase == TICKING and event == Event.ONE_SIDE_CLEARED:
		return RESOLVED
	return phase  # no transition

# UnitLifecycle transitions, per gdd/mechanics.md::states.unit_lifecycle.
static func unit_step(lifecycle: int, event: int) -> int:
	# alive --stun--> stunned --recover--> alive
	# {alive, stunned} --hp_zero--> dead (terminal)
	if event == Event.HP_ZERO:
		return Lifecycle.DEAD
	if lifecycle == Lifecycle.ALIVE and event == Event.STUN:
		return Lifecycle.STUNNED
	if lifecycle == Lifecycle.STUNNED and event == Event.RECOVER:
		return Lifecycle.ALIVE
	return lifecycle


# Forward decls so we don't have to import the full Components module.
class Lifecycle:
	const ALIVE := 0
	const STUNNED := 1
	const DEAD := 2
