"""Agents autonomes : physiologie, inventaire, compétences, perception."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import config as C
from .genome import Genome
from .memory import SpatialMemory, SocialMemory, Knowledge
from .rl import QPolicy


@dataclass
class Agent:
    id: str
    sex: str                       # "M" ou "F"
    genome: Genome
    policy: QPolicy
    rng: random.Random
    x: int = 0
    y: int = 0
    age: int = 0
    health: float = C.START_HEALTH
    energy: float = C.MAX_ENERGY
    hunger: float = 0.0            # 0 = rassasié, 100 = famine
    thirst: float = 0.0
    alive: bool = True
    inventory: dict = field(default_factory=dict)
    skills: dict = field(default_factory=lambda: {
        "artisanat": 0.1, "forge": 0.05, "combat": 0.1,
        "construction": 0.1, "chasse": 0.1, "survie": 0.1,
    })
    reputation: float = 50.0
    spatial_memory: SpatialMemory = None
    social_memory: SocialMemory = None
    knowledge: Knowledge = None
    group_id: str | None = None
    allies: set = field(default_factory=set)
    enemies: set = field(default_factory=set)
    trust: dict = field(default_factory=dict)          # agent_id -> confiance
    combat_cooldowns: dict = field(default_factory=dict)  # agent_id -> tick
    last_state: tuple | None = None
    last_action: str | None = None
    repro_cooldown: int = 0
    pregnancy: int = 0                                 # ticks restants (femelles)
    children: list = field(default_factory=list)
    killed_by: str | None = None
    cause_of_death: str | None = None
    pending_reward: float = 0.0
    # statistiques de vie
    stats: dict = field(default_factory=lambda: {
        "collectes": 0, "fabrications": 0, "constructions": 0,
        "attaques": 0, "fuites": 0, "echanges": 0, "transmissions": 0,
        "pieges": 0, "reproductions": 0, "blessures": 0,
    })

    def __post_init__(self):
        if self.spatial_memory is None:
            cap = int(50 + 250 * self.genome["memoire"])
            self.spatial_memory = SpatialMemory(cap)
        if self.social_memory is None:
            cap = int(10 + 90 * self.genome["memoire"])
            self.social_memory = SocialMemory(cap)
        if self.knowledge is None:
            self.knowledge = Knowledge(C.BASE_KNOWN_RECIPES)

    # ------------------------------------------------------------------ état
    @property
    def is_adult(self) -> bool:
        return self.age >= C.MATURITY_AGE

    @property
    def lifespan(self) -> int:
        return int(C.OLD_AGE_BASE * (0.6 + 0.8 * self.genome["longevite"]))

    def inv_count(self, item: str) -> float:
        return self.inventory.get(item, 0)

    def inv_add(self, item: str, qty: float) -> None:
        self.inventory[item] = self.inventory.get(item, 0.0) + qty

    def inv_take(self, item: str, qty: float) -> float:
        have = self.inventory.get(item, 0.0)
        taken = min(have, qty)
        if taken > 0:
            self.inventory[item] = have - taken
            if self.inventory[item] <= 1e-9:
                del self.inventory[item]
        return taken

    def inv_total(self) -> float:
        return sum(self.inventory.values())

    def best_weapon(self) -> str | None:
        weapons = [w for w in C.WEAPON_POWER if self.inv_count(w) > 0]
        return max(weapons, key=lambda w: C.WEAPON_POWER[w]) if weapons else None

    def best_armor(self) -> float:
        prot = 0.0
        for a, p in C.ARMOR_PROTECTION.items():
            if self.inv_count(a) > 0:
                prot = max(prot, p)
        return prot

    def has_tool(self) -> bool:
        return any(self.inv_count(t) > 0 for t in ("hache", "pioche", "marteau", "pelle", "scie"))

    # ------------------------------------------------------------------ physiologie
    def metabolize(self, world) -> None:
        self.age += C.AGING_TICKS
        if self.repro_cooldown > 0:
            self.repro_cooldown -= 1
        endurance = self.genome["endurance"]
        self.hunger = min(100.0, self.hunger + C.HUNGER_RATE * (1.3 - 0.3 * endurance))
        self.thirst = min(100.0, self.thirst + C.THIRST_RATE * (1.3 - 0.3 * endurance))
        drain = C.ENERGY_RATE * (1.4 - 0.4 * endurance)
        if not world.is_day:
            drain *= 0.6
            # rythme circadien : récupération nocturne passive
            self.energy = min(C.MAX_ENERGY, self.energy + 0.25)
        if world.weather == "secheresse":
            self.thirst = min(100.0, self.thirst + 0.05)
        self.energy = max(0.0, self.energy - drain)
        if self.hunger >= 100.0:
            self.health -= 0.15
        if self.thirst >= 100.0:
            self.health -= 0.25
        if self.health < C.START_HEALTH and self.hunger < 40 and self.thirst < 40 and self.energy > 30:
            self.health = min(C.START_HEALTH, self.health + 0.05)
        if self.age > self.lifespan:
            self.die("vieillesse")
        if self.health <= 0:
            self.die("famine" if self.hunger >= 100 else "soif" if self.thirst >= 100 else "blessures")

    def die(self, cause: str, killer: str | None = None) -> None:
        if not self.alive:
            return
        self.alive = False
        self.cause_of_death = cause
        self.killed_by = killer

    def maybe_forget_enemies(self, rng: random.Random, prob: float = 0.4) -> None:
        """Oubli progressif des rancunes : évite les vendettas éternelles."""
        for enemy in list(self.enemies):
            if rng.random() < prob:
                self.enemies.discard(enemy)

    # ------------------------------------------------------------------ perception
    def observe(self, world, agents_by_pos: dict) -> dict:
        """Observation locale limitée par la vision : base de l'état RL."""
        radius = max(2, int(C.VISION_RADIUS * (0.6 + 0.8 * self.genome["vision"])))
        water_near = food_near = mat_near = False
        for tx, ty, tile in world.visible_tiles(self.x, self.y, radius):
            snap = {
                "biome": tile.biome,
                "ressources": dict(tile.ressources),
                "building": tile.building,
            }
            self.spatial_memory.remember(tx, ty, snap)
            if tile.ressources.get("eau", 0) > 0 or tile.biome in ("riviere", "lac"):
                water_near = True
            if any(tile.ressources.get(f, 0) > 0 for f in ("fruits", "plantes", "animaux")):
                food_near = True
            if any(tile.ressources.get(m, 0) > 0 for m in ("bois", "pierre", "minerais", "argile", "sable")):
                mat_near = True

        near_agents = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                for other in agents_by_pos.get((self.x + dx, self.y + dy), ()):
                    if other is not self and other.alive:
                        near_agents.append(other)
                        self.social_memory.update(other.id, {
                            "position": (other.x, other.y),
                            "reputation": other.reputation,
                            "sexe": other.sex,
                            "groupe": other.group_id,
                        })

        hostility = 0
        for other in near_agents:
            if other.id in self.enemies or (other.group_id and self.group_id
                                            and other.group_id != self.group_id
                                            and other.id not in self.allies):
                hostility = 2
                break
            if other.id in self.allies or (self.group_id and other.group_id == self.group_id):
                hostility = 1

        fill = self.inv_total()
        return {
            "faim": self.hunger,
            "soif": self.thirst,
            "energie": self.energy,
            "sante": self.health,
            "jour": world.is_day,
            "saison": world.season_index if hasattr(world, "season_index") else C.SEASONS.index(world.season),
            "eau_proche": water_near,
            "nourriture_proche": food_near,
            "materiau_proche": mat_near,
            "agents_proches": min(2, len(near_agents)),
            "hostilite": hostility,
            "a_arme": self.best_weapon() is not None,
            "a_outil": self.has_tool(),
            "remplissage": min(100.0, fill),
            "_near_agents": near_agents,
            "_vision_radius": radius,
        }
