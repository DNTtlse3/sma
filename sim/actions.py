"""Exécution des actions discrètes choisies par les politiques RL."""

from __future__ import annotations

import random

from . import config as C
from .social import update_reputation


def _step_toward(agent, world, target) -> float:
    """Un pas de navigation vers une case cible connue."""
    if target is None:
        return do_explore(agent, world)
    tx, ty = target
    dx = (tx > agent.x) - (tx < agent.x)
    dy = (ty > agent.y) - (ty < agent.y)
    options = [(dx, dy)]
    if dx and dy:
        options.append((dx, 0))
        options.append((0, dy))
    else:
        options.append(agent.rng.choice(((0, -1), (0, 1), (-1, 0), (1, 0))))
    for ddx, ddy in options:
        nx, ny = agent.x + ddx, agent.y + ddy
        if world.in_bounds(nx, ny):
            cost = world.move_cost(nx, ny)
            if agent.energy >= cost:
                agent.x, agent.y = nx, ny
                agent.energy -= cost
                tile = world.tile(nx, ny)
                for trap in list(tile.traps):
                    if trap["owner"] == agent.id or trap["owner"] in agent.allies:
                        continue
                    if _owner_enemies(agent, trap["owner"]) \
                            or agent.rng.random() < 0.15:
                        _trigger_trap(agent, world, tile, trap)
                return -0.02
    return -0.05


def _goal_target(agent, world, goal: str):
    """Case cible la plus utile pour un but : vision puis mémoire."""
    radius = max(2, int(C.VISION_RADIUS * (0.6 + 0.8 * agent.genome["vision"])))
    best, best_d = None, float("inf")
    if goal == "eau":
        wanted = lambda tile: tile.ressources.get("eau", 0) > 0 or tile.biome in ("riviere", "lac")
    elif goal == "nourriture":
        wanted = lambda tile: any(tile.ressources.get(f, 0) > 0
                                  for f in ("fruits", "plantes", "animaux"))
    else:
        wanted = lambda tile: any(tile.ressources.get(m, 0) > 0
                                  for m in ("bois", "pierre", "minerais", "argile", "sable"))
    for tx, ty, tile in world.visible_tiles(agent.x, agent.y, radius):
        if wanted(tile):
            d = (tx - agent.x) ** 2 + (ty - agent.y) ** 2
            if d < best_d:
                best, best_d = (tx, ty), d
    if best is None:
        if goal == "eau":
            best = agent.spatial_memory.find_resource("eau", agent.x, agent.y)
        elif goal == "nourriture":
            best = (agent.spatial_memory.find_resource("fruits", agent.x, agent.y)
                    or agent.spatial_memory.find_resource("plantes", agent.x, agent.y)
                    or agent.spatial_memory.find_resource("animaux", agent.x, agent.y))
        else:
            for m in ("bois", "pierre", "minerais"):
                best = agent.spatial_memory.find_resource(m, agent.x, agent.y)
                if best:
                    break
    return best


def do_move(agent, world, goal: str) -> float:
    """Navigation orientée : move_eau / move_nourriture / move_materiau.

    Façonnage : chaque pas qui réduit la distance à la cible utile est
    récompensé selon le besoin courant de l'agent.
    """
    kind = goal.split("_", 1)[1]
    target = _goal_target(agent, world, kind)
    d0 = ((agent.x - target[0]) ** 2 + (agent.y - target[1]) ** 2) if target else None
    reward = _step_toward(agent, world, target)
    if target and d0 is not None:
        d1 = (agent.x - target[0]) ** 2 + (agent.y - target[1]) ** 2
        if d1 < d0:
            if kind == "eau" and agent.thirst > 30:
                reward += 0.15
            elif kind == "nourriture" and agent.hunger > 30:
                reward += 0.12
            elif kind == "materiau" and agent.inv_total() < 20:
                reward += 0.08
    return reward


def _owner_enemies(agent, owner_id: str) -> bool:
    """Le piégeur est-il un ennemi connu de l'agent qui marche ?"""
    if owner_id in agent.enemies:
        return True
    info = agent.social_memory.get(owner_id)
    return bool(info.get("hostile"))


def _trigger_trap(agent, world, tile, trap: dict) -> None:
    tile.traps.remove(trap)
    spec = C.TRAPS[trap["type"]]
    protection = agent.best_armor()
    dmg = spec["damage"] * (1.0 - protection) * (1.2 - 0.2 * agent.genome["immunite"])
    agent.health -= dmg
    agent.stats["blessures"] += 1
    if agent.health <= 0:
        agent.die("piege", killer=trap["owner"])


def do_explore(agent, world) -> float:
    """Déplacement biaisé vers les cases peu connues."""
    best, best_score = None, -1.0
    for nx, ny in world.neighbors(agent.x, agent.y):
        known = agent.spatial_memory.recall(nx, ny) is not None
        score = (0.0 if known else 1.0) + agent.rng.random()
        if score > best_score:
            best, best_score = (nx, ny), score
    if best is None:
        return -0.02
    nx, ny = best
    cost = world.move_cost(nx, ny)
    if agent.energy < cost:
        return -0.1
    agent.x, agent.y = nx, ny
    agent.energy -= cost
    return 0.05


def do_collect(agent, world) -> float:
    tile = world.tile(agent.x, agent.y)
    collectable = [r for r in C.NATURAL_RESOURCES
                   if r not in ("eau",) and tile.ressources.get(r, 0) > 0]
    if not collectable:
        return -0.05
    resource = agent.rng.choice(collectable)
    tool_bonus = 1.0
    if resource == "bois" and agent.inv_count("hache") > 0:
        tool_bonus = 2.0
    if resource in ("pierre", "minerais") and agent.inv_count("pioche") > 0:
        tool_bonus = 2.0
    if resource == "animaux":
        w = agent.best_weapon()
        tool_bonus = C.WEAPON_POWER.get(w, 0.8) / 1.5
        agent.skills["chasse"] = min(1.0, agent.skills["chasse"] + 0.005)
    amount = min(tile.ressources[resource],
                 (1.0 + 2.0 * agent.genome["force"]) * tool_bonus)
    tile.ressources[resource] -= amount
    agent.inv_add(resource, amount)
    agent.stats["collectes"] += 1
    agent.energy = max(0.0, agent.energy - 0.4)
    return C.REWARDS["collecte"] + amount * 0.02


def do_drink(agent, world) -> float:
    tile = world.tile(agent.x, agent.y)
    if tile.ressources.get("eau", 0) > 0 or tile.biome in ("riviere", "lac"):
        if tile.ressources.get("eau", 0) > 0:
            tile.ressources["eau"] -= 1
        agent.thirst = max(0.0, agent.thirst - C.WATER_VALUE)
        return C.REWARDS["eau"] if agent.thirst > 20 else 0.2
    if tile.building == "puits":
        agent.thirst = max(0.0, agent.thirst - C.WATER_VALUE)
        return C.REWARDS["eau"] if agent.thirst > 20 else 0.2
    return -0.05


def do_eat(agent) -> float:
    for food, value in sorted(C.FOOD_VALUE.items(), key=lambda kv: -kv[1]):
        if agent.inv_count(food) >= 1:
            agent.inv_take(food, 1)
            agent.hunger = max(0.0, agent.hunger - value)
            return C.REWARDS["nourriture"] if agent.hunger > 20 else 0.2
    return -0.05


def do_craft(agent, world) -> float:
    """Fabrique le meilleur objet possible parmi les recettes connues.

    À défaut, l'expérimentation permet de DÉCOUVRIR une recette inconnue
    (innovation technique, favorisée par curiosité et apprentissage) —
    c'est la source de l'évolution technologique émergente.
    """
    candidates = []
    for name in agent.knowledge.recipes:
        recipe = C.RECIPES.get(name)
        if not recipe:
            continue
        if recipe["needs"] and not _near_building(agent, world, recipe["needs"]):
            continue
        if all(agent.inv_count(i) >= q for i, q in recipe["inputs"].items()):
            candidates.append(name)
    if not candidates:
        unknown = [r for r in C.RECIPES if r not in agent.knowledge.recipes]
        p_innov = 0.004 * (0.5 + agent.genome["curiosite"] + agent.genome["apprentissage"])
        if unknown and agent.rng.random() < p_innov:
            discovery = agent.rng.choice(unknown)
            recipe = C.RECIPES[discovery]
            if all(agent.inv_count(i) >= q for i, q in recipe["inputs"].items()) \
                    and (not recipe["needs"] or _near_building(agent, world, recipe["needs"])):
                agent.knowledge.learn_recipe(discovery)
                for item, qty in recipe["inputs"].items():
                    agent.inv_take(item, qty)
                agent.inv_add(discovery, 1)
                agent.stats["fabrications"] += 1
                return 1.5
        return -0.05
    priority = ("arme_a_feu", "epee", "arbalete", "arc", "lance", "couteau", "baton",
                "armure_metal", "armure_cuir", "armure_bois",
                "hache", "pioche", "marteau", "pelle", "scie",
                "acier", "poudre_explosive", "carburant",
                "planches", "briques", "cordes", "cuir")
    for name in priority:
        if name in candidates:
            recipe = C.RECIPES[name]
            for item, qty in recipe["inputs"].items():
                agent.inv_take(item, qty)
            agent.inv_add(name, 1)
            skill = recipe["skill"]
            agent.skills[skill] = min(1.0, agent.skills[skill] + 0.01)
            agent.stats["fabrications"] += 1
            return C.REWARDS["fabrication"] * (0.5 + agent.skills[skill])
    return -0.05


def _near_building(agent, world, building: str) -> bool:
    if world.tile(agent.x, agent.y).building == building:
        return True
    for nx, ny in world.neighbors(agent.x, agent.y):
        if world.tile(nx, ny).building == building:
            return True
    return False


def do_build(agent, world, group_registry: dict) -> float:
    """Construit le meilleur bâtiment abordable sur la case courante."""
    tile = world.tile(agent.x, agent.y)
    if tile.building:
        return -0.05
    candidates = [name for name, spec in C.BUILDINGS.items()
                  if all(agent.inv_count(i) >= q for i, q in spec["cost"].items())]
    if not candidates:
        return -0.05
    priority = ("forge", "maison", "grenier", "entrepot", "ferme", "puits",
                "tour_de_garde", "rempart", "atelier", "scierie", "moulin",
                "irrigation", "porte_fortifiee", "palissade", "mur",
                "tente", "fosse")
    for name in priority:
        if name in candidates:
            for item, qty in C.BUILDINGS[name]["cost"].items():
                agent.inv_take(item, qty)
            tile.building = name
            owner = agent.group_id or agent.id
            tile.building_owner = owner
            group = group_registry.get(agent.group_id) if agent.group_id else None
            if group is not None:
                group.buildings.append((agent.x, agent.y, name))
            agent.skills["construction"] = min(1.0, agent.skills["construction"] + 0.02)
            agent.stats["constructions"] += 1
            return C.REWARDS["construction"] * (0.5 + agent.skills["construction"])
    return -0.05


def do_rest(agent, world) -> float:
    tile = world.tile(agent.x, agent.y)
    shelter = 0.0
    if tile.building:
        shelter = C.BUILDINGS[tile.building].get("shelter", 0.0)
    rate = 1.0 + 1.5 * shelter + (0.3 if not world.is_day else 0.0)
    agent.energy = min(C.MAX_ENERGY, agent.energy + rate)
    return 0.2 if agent.energy < 50 else 0.0


def do_set_trap(agent, world) -> float:
    tile = world.tile(agent.x, agent.y)
    if len(tile.traps) >= 2:
        return -0.05
    candidates = [name for name, spec in C.TRAPS.items()
                  if all(agent.inv_count(i) >= q for i, q in spec["cost"].items())]
    if not candidates:
        return -0.05
    name = "piege_explosif" if "piege_explosif" in candidates else candidates[0]
    for item, qty in C.TRAPS[name]["cost"].items():
        agent.inv_take(item, qty)
    tile.traps.append({"type": name, "owner": agent.id})
    agent.stats["pieges"] += 1
    return C.REWARDS["piege_pose"]


def do_attack(agent, world, target, group_registry: dict,
              provoked: bool = True) -> float:
    """Combat : dégâts selon force, arme, compétence ; protection par armure.

    Une agression non provoquée coûte cher en réputation : la valeur du
    conflit gratuit est donc apprise comme négative, sauf pillage réussi.
    """
    if agent.health < 25 or agent.energy < 5:
        # incapacité : trop blessé ou épuisé pour combattre
        return -0.1
    weapon = agent.best_weapon()
    power = C.WEAPON_POWER.get(weapon, 0.8)
    damage = (2.0 + 6.0 * agent.genome["force"]) * power \
        * (0.2 + agent.skills["combat"]) * agent.rng.uniform(0.7, 1.3)
    defense = target.best_armor()
    tile = world.tile(target.x, target.y)
    if tile.building and tile.building_owner:
        defense += C.BUILDINGS[tile.building].get("defense", 0.0)
    damage *= max(0.15, 1.0 - defense)
    agent.energy = max(0.0, agent.energy - 4.0)
    target.health -= damage
    target.stats["blessures"] += 1
    agent.stats["attaques"] += 1
    agent.skills["combat"] = min(1.0, agent.skills["combat"] + 0.01)
    target.enemies.add(agent.id)
    target.social_memory.update(agent.id, {"hostile": True})
    reward = 0.02 * damage - 0.3
    if target.health > 0 and target.rng.random() < 0.8:
        # riposte immédiate : attaquer comporte un risque réel
        counter = (2.0 + 6.0 * target.genome["force"]) * 0.8 \
            * (0.2 + target.skills["combat"]) * target.rng.uniform(0.7, 1.2)
        counter *= max(0.2, 1.0 - agent.best_armor())
        agent.health -= counter
        agent.stats["blessures"] += 1
        reward -= 0.03 * counter
        if agent.health <= 0:
            agent.die("combat", killer=target.id)
            return C.REWARDS["mort"]
    if target.health > 0 and target.health < 50 and target.energy > 5:
        # réflexe de survie : le blessé rompt l'engagement et s'éloigne
        dx = -1 if target.x < agent.x else 1 if target.x > agent.x else 0
        dy = -1 if target.y < agent.y else 1 if target.y > agent.y else 0
        for _ in range(3):
            fx, fy = target.x + dx, target.y + dy
            if world.in_bounds(fx, fy):
                target.x, target.y = fx, fy
                target.energy = max(0.0, target.energy - 1.0)
                dx, dy = dx or agent.rng.choice((-1, 0, 1)), dy or agent.rng.choice((-1, 0, 1))
    if target.group_id and agent.group_id and target.group_id != agent.group_id:
        ga = group_registry.get(agent.group_id)
        gt = group_registry.get(target.group_id)
        if ga and gt:
            ga.relations[gt.id] = ga.relations.get(gt.id, 0.0) - 0.5
            gt.relations[ga.id] = gt.relations.get(ga.id, 0.0) - 1.0
    if target.health <= 0:
        target.die("combat", killer=agent.id)
        # pillage partiel du vaincu
        loot = 0.0
        for item in list(target.inventory):
            qty = target.inventory.pop(item) * 0.5
            agent.inv_add(item, qty)
            loot += qty
        # représailles collectives : les alliés de la victime se vengent
        if target.group_id and agent.group_id != target.group_id:
            gt = group_registry.get(target.group_id)
            if gt:
                gt.relations[agent.group_id or agent.id] = \
                    gt.relations.get(agent.group_id or agent.id, 0.0) - 5.0
        return C.REWARDS["defense_reussie"] * 0.6 \
            + 1.5 * agent.genome["agressivite"] + loot * 0.02
    if not provoked:
        reward -= 0.8
        update_reputation(agent, -5.0)
    return reward


def do_flee(agent, world, threat_pos) -> float:
    dx = -1 if threat_pos[0] > agent.x else 1 if threat_pos[0] < agent.x else 0
    dy = -1 if threat_pos[1] > agent.y else 1 if threat_pos[1] < agent.y else 0
    nx, ny = agent.x + dx, agent.y + dy
    if not world.in_bounds(nx, ny):
        nx, ny = agent.x, agent.y
    cost = world.move_cost(nx, ny)
    if agent.energy >= cost:
        agent.x, agent.y = nx, ny
        agent.energy -= cost
    agent.stats["fuites"] += 1
    return 0.15
