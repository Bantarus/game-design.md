# Realizes {loops.tick} + {rules.tick_resolution} + {rules.combat_resolution}
# from ../../gdd/. Engine-B reference implementation in Godot 4 / GDScript.
#
# Architecture is deliberately NOT ECS: Unit is a plain RefCounted (the
# closest Godot has to a data record). The Simulation holds the unit array
# directly, mirroring xtreme's snapshot strategy at tick start. Rules read
# the snapshot for actor selection (D-012 tick-start optimization, provably
# equivalent under tick-combat's no-mid-tick-mutation invariant).
#
# D-008 §6 audit hook: keep methods OUT of Unit (see components.gd). All
# behavior lives here in Simulation + Distributions (stateless functions
# with explicit data inputs). If a method creeps onto Unit, log it.

class_name Simulation
extends RefCounted

const Components := preload("res://src/components.gd")
const StateModule := preload("res://src/state.gd")
const DistributionsModule := preload("res://src/distributions.gd")
const PRNGModule := preload("res://src/prng.gd")

var units: Array            # Array[Unit]
var combat_phase: int = StateModule.SETUP
var tick_counter: int = 0
var gold: int = 0
var rng: DistributionsModule

func _init(seed: int) -> void:
	# Self-validate PRNG against the spec's reference vector before any
	# simulation work — catch misimplementation before it produces
	# wrong-but-consistent trajectories. Matches xtreme's `Simulation::new`.
	PRNGModule.reference_vector_self_check()
	rng = DistributionsModule.new(seed)

# Phase-2 demo roster — same content as xtreme's deploy_demo_roster() to
# keep the engine-A vs engine-B comparison apples-to-apples. Stats are
# from content/units/*.yaml.
func deploy_demo_roster() -> void:
	# (id, side, deploy_order, hp, attack, speed, cost, role)
	var spec := [
		["volt_marine", Components.Side.PLAYER, 0, 20, 5, 7, 3, Components.UnitRole.RANGED_DPS],
		["shock_titan", Components.Side.PLAYER, 1, 60, 12, 3, 6, Components.UnitRole.TANK_MELEE],
		["spark_drone", Components.Side.PLAYER, 2, 8, 2, 9, 2, Components.UnitRole.SUPPORT],
		["volt_marine", Components.Side.ENEMY, 0, 20, 5, 7, 3, Components.UnitRole.RANGED_DPS],
		["shock_titan", Components.Side.ENEMY, 1, 60, 12, 3, 6, Components.UnitRole.TANK_MELEE],
	]
	for s in spec:
		units.append(Components.new(s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7]))

# Transition {states.combat_phase} via {events.start_combat}.
func start_combat() -> void:
	combat_phase = StateModule.step(combat_phase, StateModule.Event.START_COMBAT)

# Advance one tick — {rules.tick_resolution}. Stateless: reads world, mutates world.
func step() -> void:
	if combat_phase != StateModule.TICKING:
		return
	# (1) action_order — D-013 first_alive_opposite target. Snapshot units for
	# the tick (D-012 binding-moment optimization).
	var snapshot := []
	for u in units:
		snapshot.append(u.clone())
	var order := rng.action_order(snapshot)
	if order.is_empty():
		tick_counter += 1
		return
	# (2) select_actor by rotation (resolves spec-ambiguity #9).
	var actor: Components = order[tick_counter % order.size()]
	# Find the actor's live record (need to mutate target, not snapshot).
	var actor_live: Components = null
	for u in units:
		if u.side == actor.side and u.deploy_order == actor.deploy_order:
			actor_live = u
			break
	if actor_live == null:
		tick_counter += 1
		return
	# (3) target_selection: first_alive_opposite (D-013).
	var opposite_side: int = (Components.Side.ENEMY
		if actor.side == Components.Side.PLAYER
		else Components.Side.PLAYER)
	var target: Components = null
	var lowest_deploy: int = 1 << 30
	for u in units:
		if u.side == opposite_side and u.lifecycle == Components.Lifecycle.ALIVE:
			if u.deploy_order < lowest_deploy:
				lowest_deploy = u.deploy_order
				target = u
	if target == null:
		# combat_resolution will detect cleared side next pass; just advance.
		tick_counter += 1
		return
	# (4) sample damage_roll with templated mean = actor.attack (D-012).
	var damage: int = rng.damage_roll(actor.attack)
	# (5) sample critical_hit.
	var crit: bool = rng.critical_hit()
	# (6) apply_damage.
	var final_damage: int = damage * 2 if crit else damage
	target.hp = max(0, target.hp - final_damage)
	if target.hp == 0:
		target.lifecycle = StateModule.unit_step(target.lifecycle, StateModule.Event.HP_ZERO)
	tick_counter += 1

# {rules.combat_resolution}: when one_side_cleared, draw 6 gold_drop samples
# (D-014), accumulate value into {resources.gold}, transition to Resolved.
func combat_resolution() -> void:
	if combat_phase == StateModule.RESOLVED:
		return
	if not rng.one_side_cleared(units):
		return
	for i in range(6):
		gold += rng.gold_drop()
	combat_phase = StateModule.RESOLVED

# Run until terminal or cap.
func run(max_ticks: int) -> int:
	var steps := 0
	for i in range(max_ticks):
		step()
		combat_resolution()
		steps += 1
		if combat_phase == StateModule.RESOLVED:
			break
	return steps

# --- Canonical trajectory serialization per spec §9.5.5 ----------------
#
# One JSON object per line. Keys sorted alphabetically. Integer values.
# Enum strings lowercased (ASCII-only — guaranteed by canonical() funcs).
# units array sorted by (side, deploy_order). No extra whitespace.

func canonical_jsonl() -> String:
	# Sort units by (side, deploy_order) total order.
	var sorted := units.duplicate()
	sorted.sort_custom(func(a, b):
		if a.side != b.side:
			return a.side < b.side
		return a.deploy_order < b.deploy_order
	)
	var unit_parts := []
	for u in sorted:
		# Keys alphabetical: deploy_order, hp, id, lifecycle, side.
		unit_parts.append('{"deploy_order":%d,"hp":%d,"id":"%s","lifecycle":"%s","side":"%s"}' % [
			u.deploy_order,
			u.hp,
			u.id,
			Components.Lifecycle.canonical(u.lifecycle),
			Components.Side.canonical(u.side),
		])
	# Keys alphabetical at top level: gold, phase, tick, units.
	return '{"gold":%d,"phase":"%s","tick":%d,"units":[%s]}' % [
		gold,
		StateModule.canonical(combat_phase),
		tick_counter,
		",".join(unit_parts),
	]
