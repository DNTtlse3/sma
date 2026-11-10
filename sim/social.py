"""Système social : réputation, confiance, échanges, alliances, groupes.

Aucune morale n'est imposée : honnêteté, trahison et agressivité sont
des comportements dont la valeur est apprise par renforcement (la
réputation agit comme pression environnementale, pas comme règle).
"""

from __future__ import annotations

import random

from . import config as C


def update_reputation(agent, delta: float) -> None:
    agent.reputation = max(0.0, min(100.0, agent.reputation + delta))


def _need_value(agent, item: str) -> float:
    """Valeur subjective d'une ressource selon l'état interne de l'agent."""
    base = {"fruits": 1.0, "plantes": 0.8, "animaux": 1.6, "eau": 1.2}.get(item, 0.5)
    if item in C.FOOD_VALUE:
        base *= 1.0 + agent.hunger / 50.0
    if item == "eau":
        base *= 1.0 + agent.thirst / 50.0
    return base


def try_trade(agent, other, rng: random.Random) -> float:
    """Échange direct : chaque agent cède ce dont l'autre a le plus besoin.

    Un agent « malhonnête » (appris) peut trahir et voler au prix d'une
    chute de réputation — les partenaires futurs refuseront alors.
    """
    if other.inv_total() <= 0 or agent.inv_total() <= 0:
        return -0.02
    # décision d'acceptation basée sur réputation et confiance
    trust = agent.trust.get(other.id, 25.0)
    if rng.random() > (0.2 + 0.7 * other.reputation / 100.0 + trust / 200.0):
        return -0.01
    # trahison possible : l'apprentissage arbitre via la réputation perdue
    defect_prob = 0.15 * agent.genome["agressivite"] * (1.0 - trust / 100.0)
    if rng.random() < defect_prob:
        stolen = max(other.inventory.items(), key=lambda kv: kv[1])[0] if other.inventory else None
        if stolen:
            qty = other.inv_take(stolen, 1)
            agent.inv_add(stolen, qty)
            update_reputation(agent, C.DEFECT_REPUTATION)
            other.trust[agent.id] = max(0.0, other.trust.get(agent.id, 25.0) - 30.0)
            other.enemies.add(agent.id)
            return 0.8 * agent.genome["agressivite"] - 0.5
    # échange honnête
    give = max(agent.inventory.items(), key=lambda kv: _need_value(other, kv[0]) - _need_value(agent, kv[0]))
    take = max(other.inventory.items(), key=lambda kv: _need_value(agent, kv[0]) - _need_value(other, kv[0]))
    if give[1] < 1 or take[1] < 1:
        return -0.02
    if _need_value(other, give[0]) - _need_value(agent, give[0]) <= 0:
        return -0.02
    agent.inv_take(give[0], 1)
    other.inv_add(give[0], 1)
    other.inv_take(take[0], 1)
    agent.inv_add(take[0], 1)
    agent.stats["echanges"] += 1
    other.stats["echanges"] += 1
    update_reputation(agent, C.COOP_REPUTATION)
    update_reputation(other, C.COOP_REPUTATION)
    agent.trust[other.id] = min(100.0, agent.trust.get(other.id, 25.0) + 5.0)
    other.trust[agent.id] = min(100.0, other.trust.get(agent.id, 25.0) + 5.0)
    return C.REWARDS["cooperation"]


def try_alliance(agent, other, rng: random.Random) -> float:
    """Proposition d'alliance : acceptée selon réputation, confiance et génome."""
    if other.id in agent.allies:
        return 0.05
    trust = other.trust.get(agent.id, 25.0)
    accept_p = (0.1 + 0.6 * agent.reputation / 100.0 + trust / 150.0) \
        * (0.5 + other.genome["sociabilite"])
    if rng.random() < accept_p:
        agent.allies.add(other.id)
        other.allies.add(agent.id)
        agent.trust[other.id] = min(100.0, agent.trust.get(other.id, 25.0) + C.TRUST_ALLY * 0.4)
        other.trust[agent.id] = min(100.0, other.trust.get(agent.id, 25.0) + C.TRUST_ALLY * 0.4)
        update_reputation(agent, C.COOP_REPUTATION)
        return C.REWARDS["cooperation"] * 1.5
    return -0.02


def try_betrayal(agent, other, rng: random.Random) -> float:
    """Rupture hostile : gain immédiat, coût de réputation durable."""
    if other.id not in agent.allies:
        return -0.05
    agent.allies.discard(other.id)
    other.allies.discard(agent.id)
    other.enemies.add(agent.id)
    other.trust[agent.id] = 0.0
    update_reputation(agent, C.BETRAY_REPUTATION)
    stolen = 0.0
    for item in list(other.inventory):
        if rng.random() < 0.5:
            qty = other.inv_take(item, other.inventory[item] * 0.5)
            agent.inv_add(item, qty)
            stolen += qty
    return 0.5 + stolen * 0.05 - 1.0 * (1.0 - agent.genome["agressivite"])


def try_transmit(agent, near_agents) -> float:
    """Transmission culturelle : recettes et localisations de ressources."""
    shared = 0
    for other in near_agents:
        if other.id not in agent.allies and not (agent.group_id and other.group_id == agent.group_id):
            continue
        for recipe in agent.knowledge.recipes:
            if other.knowledge.learn_recipe(recipe):
                shared += 1
        for (x, y), snap in list(agent.spatial_memory._cells.items())[-15:]:
            if snap.get("ressources"):
                other.spatial_memory.remember(x, y, snap)
                shared += 1
    if shared:
        agent.stats["transmissions"] += 1
        return C.REWARDS["transmission"] * min(3.0, shared * 0.1)
    return -0.02


class Group:
    """Famille, clan, tribu ou société : entité collective émergente."""

    def __init__(self, gid: str, founder_ids: list):
        self.id = gid
        self.members: set = set(founder_ids)
        self.relations: dict = {}        # group_id -> score de relation
        self.buildings: list = []        # (x, y, type)
        self.kind = "famille"
        self.created_tick = 0

    def update_kind(self, tick: int) -> None:
        n = len(self.members)
        self.kind = "famille" if n < 5 else "clan" if n < 12 else "tribu" if n < 25 else "societe"
        self.created_tick = self.created_tick or tick

    def territory_center(self, agents_by_id: dict):
        xs, ys = [], []
        for mid in self.members:
            a = agents_by_id.get(mid)
            if a and a.alive:
                xs.append(a.x)
                ys.append(a.y)
        if not xs:
            return None
        return (sum(xs) // len(xs), sum(ys) // len(ys))


class SocialSystem:
    """Registre des groupes et gestion des alliances collectives."""

    def __init__(self):
        self.groups: dict = {}
        self._next_gid = 0

    def maybe_form_group(self, agent, agents_by_id: dict, tick: int) -> bool:
        """Un groupe émerge quand un agent a >= ALLIANCE_THRESHOLD alliés mutuels."""
        if agent.group_id:
            return False
        mutual = [aid for aid in agent.allies
                  if aid in agents_by_id and agent.id in agents_by_id[aid].allies]
        if len(mutual) + 1 < C.ALLIANCE_THRESHOLD:
            return False
        gid = f"G{self._next_gid}"
        self._next_gid += 1
        members = [agent.id] + mutual
        for mid in members:
            a = agents_by_id.get(mid)
            if a and a.alive and not a.group_id:
                a.group_id = gid
        group = Group(gid, [m for m in members])
        group.update_kind(tick)
        self.groups[gid] = group
        return True

    def dissolve_empty(self, agents_by_id: dict) -> None:
        for gid in list(self.groups):
            group = self.groups[gid]
            alive = [mid for mid in group.members
                     if mid in agents_by_id and agents_by_id[mid].alive]
            group.members = set(alive)
            group.update_kind(0)
            if len(alive) < 2:
                for mid in alive:
                    agents_by_id[mid].group_id = None
                del self.groups[gid]
