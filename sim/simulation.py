"""Moteur de simulation : boucle principale, apprentissage, reproduction, métriques."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict

from . import config as C
from . import actions as A
from .agent import Agent
from .genome import Genome
from .rl import QPolicy, discretize_state
from .social import (SocialSystem, try_trade, try_alliance, try_betrayal,
                     try_transmit, update_reputation)
from .world import World


class Simulation:
    def __init__(self, n_agents: int = 30, width: int = C.MAP_WIDTH,
                 height: int = C.MAP_HEIGHT, seed: int = 42,
                 max_population: int = C.MAX_POPULATION):
        self.rng = random.Random(seed)
        self.world = World(width, height, seed=seed)
        self.social = SocialSystem()
        self.max_population = max_population
        self.tick = 0
        self.agents: dict = {}
        self.births = 0
        self.deaths = 0
        self.death_causes: dict = defaultdict(int)
        self.trades_count = 0
        self.attacks_count = 0
        self.war_events = 0
        self.history: list = []
        self._next_id = 0
        for _ in range(n_agents):
            self._spawn_agent(near_water=True)

    # ------------------------------------------------------------------ création
    def _random_position(self, near_water: bool = False):
        for _ in range(300):
            x = self.rng.randrange(self.world.width)
            y = self.rng.randrange(self.world.height)
            if self.world.tile(x, y).biome in ("lac", "montagne"):
                continue
            if near_water:
                if not any(self.world.tile(nx, ny).biome in ("riviere", "lac", "fertile")
                           for nx, ny in self.world.neighbors(x, y)):
                    continue
            return x, y
        return self.world.width // 2, self.world.height // 2

    def _spawn_agent(self, genome: Genome | None = None,
                     pos: tuple | None = None, parents: tuple | None = None,
                     near_water: bool = False) -> Agent:
        self._next_id += 1
        aid = f"A{self._next_id}"
        x, y = pos if pos else self._random_position(near_water)
        if genome is None:
            genome = Genome.random(self.rng)
        alpha = C.LEARNING_RATE_RANGE[0] + genome["apprentissage"] * \
            (C.LEARNING_RATE_RANGE[1] - C.LEARNING_RATE_RANGE[0])
        epsilon = 0.2 + 0.3 * genome["curiosite"]
        policy = QPolicy(alpha=alpha, epsilon=epsilon, seed=self.rng.randrange(2**31))
        if parents:
            # transmission culturelle : l'enfant hérite d'une partie des
            # connaissances pratiques (Q-valeurs) de ses parents
            for p in parents:
                for state, vals in p.policy.q.items():
                    cur = policy.q.setdefault(state, [0.0] * len(vals))
                    for i, v in enumerate(vals):
                        cur[i] = 0.5 * cur[i] + 0.25 * v
            policy.epsilon = 0.1 + 0.2 * genome["curiosite"]
        agent = Agent(
            id=aid, sex=self.rng.choice(("M", "F")), genome=genome,
            policy=policy, rng=random.Random(self.rng.randrange(2**31)),
            x=x, y=y,
        )
        agent.pregnancy = 0
        if parents:
            agent.trust[parents[0].id] = 70.0
            agent.trust[parents[1].id] = 70.0
            agent.allies.update((parents[0].id, parents[1].id))
        self.agents[aid] = agent
        return agent

    # ------------------------------------------------------------------ boucle
    def step(self) -> None:
        self.tick += 1
        self.world.advance_time()

        if self.tick % 300 == 0:
            for agent in self.agents.values():
                if agent.alive:
                    agent.maybe_forget_enemies(agent.rng, prob=0.6)

        agents_by_pos: dict = defaultdict(list)
        for a in self.agents.values():
            if a.alive:
                agents_by_pos[(a.x, a.y)].append(a)

        for agent in list(self.agents.values()):
            if not agent.alive:
                continue
            self._agent_step(agent, agents_by_pos)

        self._pregnancies()
        self._offspring_rewards()
        self._group_formation()
        self._building_production()
        self._trap_passive_hunting()
        self.social.dissolve_empty(self.agents)
        self._cleanup_deaths()

    def _group_formation(self) -> None:
        for agent in self.agents.values():
            if agent.alive and not agent.group_id and len(agent.allies) >= C.ALLIANCE_THRESHOLD - 1:
                self.social.maybe_form_group(agent, self.agents, self.tick)

    def _building_production(self) -> None:
        """Les fermes, puits et moulins produisent passivement."""
        if self.tick % 10 != 0:
            return
        for row in self.world.tiles:
            for tile in row:
                if not tile.building:
                    continue
                produces = C.BUILDINGS[tile.building].get("produces")
                if not produces:
                    continue
                if tile.building == "ferme" and (self.world.season == "hiver" or tile.fire > 0):
                    continue
                for res in produces:
                    cap = C.BIOMES[tile.biome]["ressources"].get(res, 10) * 1.5
                    if tile.ressources.get(res, 0) < cap:
                        tile.ressources[res] = tile.ressources.get(res, 0) + 0.4

    def _trap_passive_hunting(self) -> None:
        """Les pièges capturent des animaux : la chasse devient une stratégie."""
        if self.tick % 10 != 0:
            return
        for row in self.world.tiles:
            for tile in row:
                if not tile.traps or tile.ressources.get("animaux", 0) < 1:
                    continue
                for trap in list(tile.traps):
                    if self.rng.random() < 0.05:
                        tile.ressources["animaux"] -= 1
                        tile.traps.remove(trap)
                        spec = C.TRAPS[trap["type"]]
                        if spec["capture"]:
                            owner = self.agents.get(trap["owner"])
                            if owner and owner.alive:
                                owner.inv_add("animaux", 1)
                                owner.pending_reward += C.REWARDS["collecte"] + 0.3

    def _offspring_rewards(self) -> None:
        """Récompense évolutive : descendance atteignant l'âge adulte."""
        for agent in self.agents.values():
            if not agent.alive or not agent.is_adult:
                continue
            for cid in agent.children:
                child = self.agents.get(cid)
                if child and child.alive and child.is_adult \
                        and cid not in agent.stats.setdefault("adult_children", set()):
                    agent.stats.setdefault("adult_children", set()).add(cid)
                    agent.pending_reward += C.REWARDS["descendance_adulte"]

    def _agent_step(self, agent: Agent, agents_by_pos: dict) -> None:
        obs = agent.observe(self.world, agents_by_pos)
        near = obs.pop("_near_agents")
        state = discretize_state(obs)

        reward = C.REWARDS["survie_tick"] + agent.pending_reward
        agent.pending_reward = 0.0
        if agent.hunger >= 90:
            reward += C.REWARDS["famine"]
        if agent.thirst >= 90:
            reward += C.REWARDS["soif"]

        action = agent.policy.act(state)
        action = self._survival_reflex(agent, obs, action) or action
        r_extra = self._execute(agent, action, near, obs)
        reward += r_extra

        next_obs = None
        next_state = state
        done = not agent.alive
        if not done:
            next_obs = agent.observe(self.world, agents_by_pos)
            next_obs.pop("_near_agents")
            next_state = discretize_state(next_obs)

        agent.policy.learn(state, action, reward, next_state, done)
        agent.policy.decay_epsilon()
        agent.metabolize(self.world)

    def _survival_reflex(self, agent: Agent, obs: dict, action: str) -> str | None:
        """Réflexes homéostatiques aux seuils critiques uniquement.

        Le comportement général reste entièrement appris ; ces réflexes
        empêchent seulement les morts absurdes pendant que la politique
        converge (agent sur l'eau mourant de soif, etc.).
        """
        tile = self.world.tile(agent.x, agent.y)
        on_water = tile.ressources.get("eau", 0) > 0 \
            or tile.biome in ("riviere", "lac") or tile.building == "puits"
        if agent.thirst > 85 and on_water:
            return "drink"
        if agent.thirst > 92 and obs["eau_proche"]:
            return "move_eau"
        if agent.hunger > 85 and any(agent.inv_count(f) > 0 for f in C.FOOD_VALUE):
            return "eat"
        if agent.hunger > 92 and obs["nourriture_proche"]:
            return "move_nourriture"
        if agent.energy < 8:
            return "rest"
        return None

    def _execute(self, agent: Agent, action: str, near: list, obs: dict) -> float:
        """Exécute l'action et retourne la récompense immédiate."""
        w = self.world
        if action in ("move_eau", "move_nourriture", "move_materiau"):
            return A.do_move(agent, w, action)
        if action == "explore":
            return A.do_explore(agent, w)
        if action == "collect":
            return A.do_collect(agent, w)
        if action == "drink":
            return A.do_drink(agent, w)
        if action == "eat":
            return A.do_eat(agent)
        if action == "craft":
            return A.do_craft(agent, w)
        if action == "build":
            return A.do_build(agent, w, self.social.groups)
        if action == "rest":
            return A.do_rest(agent, w)
        if action == "set_trap":
            return A.do_set_trap(agent, w)

        if action == "attack":
            enemies = [o for o in near if o.id in agent.enemies
                       or (agent.group_id and o.group_id and o.group_id != agent.group_id
                           and self._at_war(agent, o))]
            provoked = bool(enemies)
            if not enemies:
                # agression opportuniste : pillage potentiel, pleine santé,
                # fort génotype agressif — sinon le conflit n'est pas rentable
                if (agent.genome["agressivite"] > 0.85 and agent.health > 70
                        and agent.best_weapon() is not None
                        and any(o.inv_total() > 3 and o.health < agent.health
                                for o in near)):
                    if agent.rng.random() > agent.genome["agressivite"] * 0.3:
                        return -0.02
                    enemies = [o for o in near
                               if o.inv_total() > 3 and o.health < agent.health]
                else:
                    return -0.05
            target = min(enemies, key=lambda o: o.health)
            # on n'attaque que si l'issue semble favorable
            if agent.health <= target.health + 10:
                return -0.05
            # cooldown de combat : un même adversaire ne peut être frappé
            # qu'une fois tous les COMBAT_COOLDOWN ticks
            last = agent.combat_cooldowns.get(target.id, -10**9)
            if self.tick - last < C.COMBAT_COOLDOWN:
                return -0.02
            agent.combat_cooldowns[target.id] = self.tick
            self.attacks_count += 1
            result = A.do_attack(agent, w, target, self.social.groups, provoked)
            # défense mutuelle : les alliés proches identifient l'agresseur
            for ally_id in target.allies:
                ally = self.agents.get(ally_id)
                if ally and ally.alive and ally.rng.random() < 0.3 and \
                        abs(ally.x - target.x) <= 8 and abs(ally.y - target.y) <= 8:
                    ally.enemies.add(agent.id)
            return result

        if action == "flee":
            threats = [o for o in near if o.id in agent.enemies]
            if not threats:
                return -0.02
            threat = min(threats, key=lambda o: (o.x - agent.x) ** 2 + (o.y - agent.y) ** 2)
            return A.do_flee(agent, w, (threat.x, threat.y))

        if action == "social":
            if not near:
                # recherche de compagnie : aller vers le dernier agent vu
                known = agent.social_memory.known_agents()
                if not known:
                    return -0.02
                other_id = known[-1]
                info = agent.social_memory.get(other_id)
                pos = info.get("position")
                if not pos:
                    return -0.02
                r = A._step_toward(agent, w, pos)
                return r + 0.03
            other = self.rng.choice(near)
            roll = self.rng.random()
            sociability = agent.genome["sociabilite"]
            # cour : l'interaction sociale peut déboucher sur une reproduction
            if other.sex != agent.sex and agent.is_adult and other.is_adult:
                r = self._try_mate(agent, [other])
                if r > 0:
                    return r
            if other.id in agent.allies and roll < 0.15 * agent.genome["agressivite"]:
                return try_betrayal(agent, other, agent.rng)
            if roll < 0.45 * (0.4 + sociability):
                r = try_trade(agent, other, agent.rng)
                if r > 0.1:
                    self.trades_count += 1
                return r
            if roll < 0.75:
                return try_alliance(agent, other, agent.rng)
            return try_transmit(agent, near) if roll < 0.9 else -0.01

        if action == "transmit":
            return try_transmit(agent, [o for o in near
                                        if o.id in agent.allies
                                        or (agent.group_id and o.group_id == agent.group_id)])

        if action == "mate":
            return self._try_mate(agent, near)

        return -0.01

    def _at_war(self, agent: Agent, other: Agent) -> bool:
        ga = self.social.groups.get(agent.group_id)
        gt = self.social.groups.get(other.group_id)
        if ga and gt:
            return ga.relations.get(gt.id, 0.0) <= -2.0
        return False

    # ------------------------------------------------------------------ reproduction
    def _try_mate(self, agent: Agent, near: list) -> float:
        """Proposition d'accouplement : le partenaire accepte selon confiance,
        réputation et conditions physiologiques (mécanisme non intime,
        simple création d'une nouvelle génération)."""
        if not agent.is_adult or agent.repro_cooldown > 0 or agent.pregnancy > 0:
            return -0.05
        if agent.health < 40 or agent.energy < 20 or agent.hunger > 70:
            return -0.05
        if len(self.agents) >= self.max_population:
            return -0.05
        candidates = [o for o in near
                      if o.sex != agent.sex and o.is_adult and o.alive
                      and o.repro_cooldown == 0 and o.pregnancy == 0
                      and o.health > 40 and o.energy > 20]
        if not candidates:
            return -0.05
        # acceptation : confiance mutuelle, réputation ou lien de groupe
        def accepts(o: Agent) -> bool:
            trust = o.trust.get(agent.id, 0.0)
            p = 0.2 * (trust / 100.0) + 0.35 * (agent.reputation / 100.0) \
                + 0.25 * o.genome["sociabilite"]
            if agent.id in o.allies or (agent.group_id and o.group_id == agent.group_id):
                p += 0.4
            return o.rng.random() < p
        partners = [o for o in candidates if accepts(o)]
        if not partners:
            return -0.05
        partner = partners[0]
        agent.repro_cooldown = C.REPRO_COOLDOWN
        partner.repro_cooldown = C.REPRO_COOLDOWN
        female = agent if agent.sex == "F" else partner
        female.pregnancy = C.PREGNANCY_TICKS
        agent.stats["reproductions"] += 1
        partner.stats["reproductions"] += 1
        return C.REWARDS["reproduction"]

    def _pregnancies(self) -> None:
        for agent in list(self.agents.values()):
            if not agent.alive or agent.pregnancy <= 0:
                continue
            agent.pregnancy -= 1
            if agent.pregnancy == 0:
                if len(self.agents) < self.max_population:
                    father = None
                    for a in self.agents.values():
                        if a.sex == "M" and a.is_adult and a.alive \
                                and agent.id in a.allies:
                            father = a
                            break
                    genome = Genome.inherit(agent.genome,
                                            father.genome if father else agent.genome,
                                            self.rng)
                    child = self._spawn_agent(genome=genome, pos=(agent.x, agent.y),
                                              parents=(agent, father) if father else None)
                    # l'enfant naît dans le groupe de sa mère : les clans
                    # grandissent en tribus au fil des générations
                    if agent.group_id and agent.group_id in self.social.groups:
                        child.group_id = agent.group_id
                        self.social.groups[agent.group_id].members.add(child.id)
                    self.births += 1
                    agent.children.append(child.id)
                    if father:
                        father.children.append(child.id)

    # ------------------------------------------------------------------ décès
    def _cleanup_deaths(self) -> None:
        for aid, agent in list(self.agents.items()):
            if not agent.alive:
                self.deaths += 1
                self.death_causes[agent.cause_of_death or "inconnue"] += 1
                for gid in list(self.social.groups):
                    self.social.groups[gid].members.discard(aid)
                del self.agents[aid]

    # ------------------------------------------------------------------ métriques
    def snapshot(self) -> dict:
        alive = [a for a in self.agents.values() if a.alive]
        n = max(1, len(alive))
        return {
            "tick": self.tick,
            "jour": self.world.day,
            "saison": self.world.season,
            "population": len(alive),
            "naissances": self.births,
            "deces": self.deaths,
            "causes_deces": dict(self.death_causes),
            "groupes": len(self.social.groups),
            "types_groupes": sorted({g.kind for g in self.social.groups.values()}),
            "alliances": sum(len(a.allies) for a in alive) // 2,
            "echanges": self.trades_count,
            "attaques": self.attacks_count,
            "guerres": sum(1 for g in self.social.groups.values()
                           for s in g.relations.values() if s <= -2.0) // 2,
            "age_moyen": sum(a.age for a in alive) / n,
            "sante_moyenne": sum(a.health for a in alive) / n,
            "reputation_moyenne": sum(a.reputation for a in alive) / n,
            "recettes_connues_moy": sum(len(a.knowledge.recipes) for a in alive) / n,
            "q_etats_moy": sum(a.policy.size() for a in alive) / n,
            "batiments": sum(1 for row in self.world.tiles for t in row if t.building),
            "pieges": sum(len(t.traps) for row in self.world.tiles for t in row),
            "objets_fabriques": sum(a.stats["fabrications"] for a in alive),
        }

    def log_history(self) -> None:
        self.history.append(self.snapshot())

    # ------------------------------------------------------------------ export
    def save_csv(self, path: str) -> None:
        if not self.history:
            return
        keys = list(self.history[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in self.history:
                writer.writerow(row)

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "final": self.snapshot(),
                "catastrophes_batiments_detruits": self.world.buildings_destroyed,
                "groupes": [
                    {"id": g.id, "type": g.kind, "membres": len(g.members),
                     "batiments": len(g.buildings), "relations": g.relations}
                    for g in self.social.groups.values()
                ],
                "historique": self.history,
            }, f, indent=2, ensure_ascii=False, default=str)
