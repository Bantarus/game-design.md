# Realizes {entities.units} from ../../gdd/mechanics.md.
#
# Pure data — no behavior on the Unit class. This is the D-008 §6
# data_behavior_separation test in a non-ECS, GC'd-actor engine: keep
# logic OUT of the entity class even when the language makes it natural
# to put it there. If we end up adding methods to Unit, that goes in the
# findings as a partial failure of the invariant in this engine.

class_name Unit
extends RefCounted

# Stable id matching the content-entity filename stem
# (content/units/<id>.yaml).
var id: String
var hp: int
var attack: int
var speed: int
var cost: int
# UnitRole and Side and Lifecycle are namespaced enums to keep the data
# pure. The dispatching logic lives in src/rules.gd, not here.
var role: int
var side: int
# 0-based deployment order — tie-breaker for {distributions.action_order}.
var deploy_order: int
var lifecycle: int

func _init(p_id: String, p_side: int, p_deploy_order: int,
		p_hp: int, p_attack: int, p_speed: int, p_cost: int,
		p_role: int) -> void:
	id = p_id
	hp = p_hp
	attack = p_attack
	speed = p_speed
	cost = p_cost
	role = p_role
	side = p_side
	deploy_order = p_deploy_order
	lifecycle = Lifecycle.ALIVE

# Shallow copy for tick-start snapshotting (D-012 binding-moment optimization).
# Read-only after creation — callers MUST NOT mutate snapshot units.
# Use get_script().new(...) instead of Unit.new(...) to avoid GDScript's
# self-reference compile error inside the class body that bears class_name.
func clone():
	var u = get_script().new(id, side, deploy_order, hp, attack, speed, cost, role)
	u.lifecycle = lifecycle
	return u


# Closed enums for the gameplay-state surface. Values match the canonical
# JSONL strings declared in gdd/verification.md::trajectory.schema.
class Side:
	const PLAYER := 0
	const ENEMY := 1
	static func canonical(s: int) -> String:
		match s:
			PLAYER: return "player"
			ENEMY: return "enemy"
			_: return "unknown"


class Lifecycle:
	const ALIVE := 0
	const STUNNED := 1
	const DEAD := 2
	static func canonical(l: int) -> String:
		match l:
			ALIVE: return "alive"
			STUNNED: return "stunned"
			DEAD: return "dead"
			_: return "unknown"


class UnitRole:
	const TANK_MELEE := 0
	const RANGED_DPS := 1
	const SUPPORT := 2
	const HYBRID := 3
