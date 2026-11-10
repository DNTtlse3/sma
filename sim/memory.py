"""Mémoires des agents : spatiale, sociale, connaissances transmises."""

from __future__ import annotations

from collections import OrderedDict


class SpatialMemory:
    """Mémoire spatiale bornée : dernières cases observées (LRU)."""

    def __init__(self, capacity: int):
        self.capacity = max(1, capacity)
        self._cells: OrderedDict = OrderedDict()

    def remember(self, x: int, y: int, snapshot: dict) -> None:
        key = (x, y)
        self._cells[key] = snapshot
        self._cells.move_to_end(key)
        while len(self._cells) > self.capacity:
            self._cells.popitem(last=False)

    def recall(self, x: int, y: int) -> dict | None:
        return self._cells.get((x, y))

    def find_resource(self, resource: str, x: int = 0, y: int = 0):
        """Case mémorisée la plus proche contenant la ressource."""
        best, best_d = None, float("inf")
        for (cx, cy), snap in self._cells.items():
            if snap.get("ressources", {}).get(resource, 0) > 0:
                d = (cx - x) ** 2 + (cy - y) ** 2
                if d < best_d:
                    best, best_d = (cx, cy), d
        return best

    def find_building(self, building: str):
        for key in reversed(self._cells):
            if self._cells[key].get("building") == building:
                return key
        return None

    def __len__(self) -> int:
        return len(self._cells)


class SocialMemory:
    """Mémoire sociale : ce que l'agent croit savoir des autres."""

    def __init__(self, capacity: int):
        self.capacity = max(10, capacity)
        self._known: OrderedDict = OrderedDict()

    def update(self, agent_id: str, info: dict) -> None:
        entry = self._known.setdefault(agent_id, {})
        entry.update(info)
        self._known.move_to_end(agent_id)
        while len(self._known) > self.capacity:
            self._known.popitem(last=False)

    def known_agents(self) -> list:
        return list(self._known.keys())

    def get(self, agent_id: str) -> dict:
        return self._known.get(agent_id, {})

    def __len__(self) -> int:
        return len(self._known)


class Knowledge:
    """Connaissances techniques transmises culturellement."""

    def __init__(self, base_recipes):
        self.recipes: set = set(base_recipes)

    def learn_recipe(self, name: str) -> bool:
        if name in self.recipes:
            return False
        self.recipes.add(name)
        return True

    def shareable(self) -> list:
        return sorted(self.recipes)
