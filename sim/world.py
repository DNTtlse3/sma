"""Monde : terrain, ressources, temps, météo, saisons, catastrophes."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import config as C


@dataclass
class Tile:
    biome: str
    ressources: dict = field(default_factory=dict)
    building: str | None = None          # nom du bâtiment présent
    building_owner: str | None = None    # id du groupe propriétaire
    traps: list = field(default_factory=list)  # pièges posés
    fire: int = 0                        # ticks de feu restants

    def regen(self, season: str, weather: str, rng: random.Random) -> None:
        if self.fire > 0:
            self.fire -= 1
            for r in self.ressources:
                self.ressources[r] = max(0.0, self.ressources[r] * 0.98)
            return
        base = C.BIOMES[self.biome]["regen"]
        if weather == "secheresse":
            base *= 0.15
        elif weather == "pluie":
            base *= 1.4
        if season == "hiver":
            base *= 0.3
        elif season == "printemps":
            base *= 1.3
        for r, cap in C.BIOMES[self.biome]["ressources"].items():
            if self.ressources.get(r, 0.0) < cap:
                self.ressources[r] = min(cap, self.ressources.get(r, 0.0) + base * cap * 0.1)


class World:
    """Carte 2D dynamique avec cycle jour/nuit, saisons, météo, catastrophes."""

    def __init__(self, width: int = C.MAP_WIDTH, height: int = C.MAP_HEIGHT,
                 seed: int | None = 42):
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        self.tick = 0
        self.weather = "clair"
        self.tiles: list[list[Tile]] = []
        self._generate_terrain()
        self.buildings_destroyed = 0

    # ------------------------------------------------------------------ terrain
    def _generate_terrain(self) -> None:
        rng = self.rng
        # bruit de valeur grossier : points de semence + interpolation bicubique simple
        seeds = {}
        for biome, prob in C.BIOME_PROBS.items():
            seeds[biome] = [(rng.randrange(self.width), rng.randrange(self.height))
                            for _ in range(int(prob * 40) + 2)]
        # rivières : tracés aléatoires
        rivers = []
        for _ in range(max(2, self.width // 24)):
            x, y = rng.randrange(self.width), 0
            path = []
            while y < self.height:
                path.append((x, y))
                y += 1
                x = max(0, min(self.width - 1, x + rng.choice((-1, 0, 0, 1))))
            rivers.append(path)

        self.tiles = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                best, best_d = None, float("inf")
                for biome, pts in seeds.items():
                    for (sx, sy) in pts:
                        d = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
                        if d < best_d:
                            best, best_d = biome, d
                row.append(Tile(biome=best, ressources=dict(C.BIOMES[best]["ressources"])))
            self.tiles.append(row)
        for path in rivers:
            for (x, y) in path:
                t = self.tiles[y][x]
                t.biome = "riviere"
                t.ressources = dict(C.BIOMES["riviere"]["ressources"])
            # lacs aux coudes
            for (x, y) in path:
                if self.rng.random() < 0.02:
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                t = self.tiles[ny][nx]
                                if t.biome != "riviere":
                                    t.biome = "lac"
                                    t.ressources = dict(C.BIOMES["lac"]["ressources"])

    # ------------------------------------------------------------------ temps
    @property
    def day(self) -> int:
        return self.tick // C.TICKS_PER_DAY

    @property
    def is_day(self) -> bool:
        return (self.tick % C.TICKS_PER_DAY) < (C.TICKS_PER_DAY * 2 // 3)

    @property
    def season(self) -> str:
        day = self.day
        return C.SEASONS[(day // C.DAYS_PER_SEASON) % 4]

    def advance_time(self) -> None:
        self.tick += 1
        if self.tick % 30 == 0:
            probs = C.WEATHER_PROBS[self.season]
            r = self.rng.random()
            acc = 0.0
            for w, p in probs:
                acc += p
                if r <= acc:
                    self.weather = w
                    break
        if self.tick % 10 == 0:
            self._regenerate()
        if self.rng.random() < 1.0 / C.DISASTER_INTERVAL:
            self._disaster()

    def _regenerate(self) -> None:
        for row in self.tiles:
            for tile in row:
                tile.regen(self.season, self.weather, self.rng)

    # ------------------------------------------------------------------ catastrophes
    def _disaster(self) -> None:
        cx = self.rng.randrange(self.width)
        cy = self.rng.randrange(self.height)
        kind = self.rng.choice(("incendie", "inondation", "secheresse", "seisme"))
        r = self.rng.randint(3, C.DISASTER_RADIUS)
        for y in range(max(0, cy - r), min(self.height, cy + r + 1)):
            for x in range(max(0, cx - r), min(self.width, cx + r + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                    continue
                tile = self.tiles[y][x]
                if kind == "incendie":
                    tile.fire = self.rng.randint(20, 60)
                elif kind == "inondation":
                    for res in ("plantes", "fruits"):
                        tile.ressources[res] = tile.ressources.get(res, 0) * 0.5
                elif kind == "secheresse":
                    for res in ("eau", "plantes", "fruits"):
                        tile.ressources[res] = tile.ressources.get(res, 0) * 0.3
                elif kind == "seisme":
                    if tile.building:
                        tile.building = None
                        tile.building_owner = None
                        self.buildings_destroyed += 1

    # ------------------------------------------------------------------ requêtes
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile(self, x: int, y: int) -> Tile:
        return self.tiles[y][x]

    def move_cost(self, x: int, y: int) -> float:
        biome = self.tiles[y][x].biome
        return C.MOVE_ENERGY_COST.get(biome, C.MOVE_ENERGY_COST["default"])

    def neighbors(self, x: int, y: int):
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny

    def visible_tiles(self, x: int, y: int, radius: int):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    nx, ny = x + dx, y + dy
                    if self.in_bounds(nx, ny):
                        yield nx, ny, self.tiles[ny][nx]

    def ascii_map(self) -> str:
        chars = {"foret": "T", "plaine": ".", "montagne": "^", "riviere": "~",
                 "lac": "=", "grotte": "C", "desert": "d", "fertile": "f"}
        lines = []
        for row in self.tiles:
            lines.append("".join(chars[t.biome] for t in row))
        return "\n".join(lines)
