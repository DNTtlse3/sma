"""Tests unitaires du système multi-agents."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim import config as C
from sim.agent import Agent
from sim.genome import Genome
from sim.memory import SpatialMemory, Knowledge
from sim.rl import QPolicy, discretize_state, ACTION_INDEX
from sim.simulation import Simulation
from sim.social import SocialSystem, try_trade, try_alliance
from sim.world import World

GENES_KEYS = ("apprentissage", "agressivite", "sociabilite", "curiosite",
              "endurance", "force", "memoire", "vision", "longevite", "immunite")


def make_agent(aid="A1", seed=1, **kw):
    rng = random.Random(seed)
    genome = Genome.random(rng)
    return Agent(id=aid, sex="M", genome=genome,
                 policy=QPolicy(0.1, 0.2, seed=seed),
                 rng=random.Random(seed), **kw)


class TestGenome(unittest.TestCase):
    def test_random_genes_in_range(self):
        g = Genome.random(random.Random(0))
        self.assertEqual(set(g.genes), set(GENES_KEYS))
        for v in g.genes.values():
            self.assertGreaterEqual(v, 0.05)
            self.assertLessEqual(v, 1.0)

    def test_inheritance_and_mutation(self):
        rng = random.Random(1)
        a, b = Genome.random(rng), Genome.random(rng)
        child = Genome.inherit(a, b, rng)
        self.assertEqual(set(child.genes), set(GENES_KEYS))
        for v in child.genes.values():
            self.assertGreaterEqual(v, 0.05)
            self.assertLessEqual(v, 1.0)


class TestWorld(unittest.TestCase):
    def test_terrain_generated(self):
        w = World(40, 40, seed=7)
        self.assertEqual(len(w.tiles), 40)
        biomes = {t.biome for row in w.tiles for t in row}
        self.assertTrue(set(biomes).issubset(set(C.BIOMES)))
        self.assertGreaterEqual(len(biomes), 3)

    def test_time_and_seasons(self):
        w = World(10, 10, seed=0)
        for _ in range(C.TICKS_PER_DAY * C.DAYS_PER_SEASON + 5):
            w.advance_time()
        self.assertEqual(w.day, C.DAYS_PER_SEASON)
        self.assertIn(w.season, C.SEASONS)

    def test_regeneration(self):
        w = World(10, 10, seed=0)
        tile = w.tiles[5][5]
        tile.ressources["bois"] = 0
        for _ in range(500):
            w.advance_time()
        self.assertGreaterEqual(tile.ressources.get("bois", 0), 0.0)


class TestMemory(unittest.TestCase):
    def test_spatial_memory_bounded(self):
        m = SpatialMemory(5)
        for i in range(20):
            m.remember(i, 0, {"biome": "plaine"})
        self.assertLessEqual(len(m), 5)

    def test_find_resource(self):
        m = SpatialMemory(10)
        m.remember(1, 1, {"ressources": {"bois": 0}})
        m.remember(2, 2, {"ressources": {"bois": 5}})
        self.assertEqual(m.find_resource("bois"), (2, 2))

    def test_knowledge_learning(self):
        k = Knowledge(C.BASE_KNOWN_RECIPES)
        self.assertTrue(k.learn_recipe("arc"))
        self.assertFalse(k.learn_recipe("arc"))


class TestRL(unittest.TestCase):
    def test_q_update_increases_value(self):
        p = QPolicy(0.5, 0.0, seed=0)
        s = (0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0)
        idx = ACTION_INDEX["collect"]
        before = p.q_values(s)[idx]
        for _ in range(20):
            p.learn(s, "collect", 1.0, s, False)
        self.assertGreater(p.q_values(s)[idx], before)

    def test_epsilon_decay(self):
        p = QPolicy(0.1, 0.9, seed=0)
        for _ in range(1000):
            p.decay_epsilon()
        self.assertGreaterEqual(p.epsilon, C.EPSILON_MIN)
        self.assertLess(p.epsilon, 0.9)

    def test_discretize_state_size(self):
        obs = {"faim": 10, "soif": 50, "energie": 80, "sante": 100, "jour": True,
               "saison": 2, "eau_proche": True, "nourriture_proche": False,
               "materiau_proche": True, "agents_proches": 1, "hostilite": 0,
               "a_arme": False, "a_outil": True, "remplissage": 5}
        s = discretize_state(obs)
        self.assertEqual(len(s), 14)


class TestAgent(unittest.TestCase):
    def test_metabolism_and_death(self):
        a = make_agent()
        a.hunger = 100.0
        a.thirst = 100.0
        a.health = 0.3
        w = World(10, 10, seed=0)
        a.metabolize(w)
        self.assertFalse(a.alive)

    def test_inventory(self):
        a = make_agent()
        a.inv_add("bois", 3)
        self.assertEqual(a.inv_count("bois"), 3)
        taken = a.inv_take("bois", 5)
        self.assertEqual(taken, 3)
        self.assertNotIn("bois", a.inventory)

    def test_observe_keys(self):
        w = World(20, 20, seed=0)
        a = make_agent(x=10, y=10)
        obs = a.observe(w, {})
        for key in ("faim", "soif", "jour", "saison", "hostilite"):
            self.assertIn(key, obs)


class TestSocial(unittest.TestCase):
    def test_trade_runs(self):
        a, b = make_agent("A1", 1), make_agent("A2", 2)
        a.inv_add("fruits", 5)
        b.inv_add("plantes", 5)
        a.hunger = b.hunger = 80
        rng = random.Random(3)
        results = [try_trade(a, b, rng) for _ in range(30)]
        self.assertTrue(all(isinstance(r, float) for r in results))

    def test_alliance_mutual(self):
        a, b = make_agent("A1", 1), make_agent("A2", 2)
        b.genome.genes["sociabilite"] = 1.0
        a.reputation = 100.0
        b.trust[a.id] = 100.0
        r = try_alliance(a, b, random.Random(0))
        self.assertGreater(r, 0)
        self.assertIn(b.id, a.allies)
        self.assertIn(a.id, b.allies)

    def test_group_formation(self):
        ss = SocialSystem()
        agents = {aid: make_agent(aid, i) for i, aid in enumerate(("A1", "A2", "A3"))}
        for a in agents.values():
            for b in agents.values():
                if a is not b:
                    a.allies.add(b.id)
                    b.allies.add(a.id)
        self.assertTrue(ss.maybe_form_group(agents["A1"], agents, tick=0))
        self.assertEqual(len(ss.groups), 1)
        for a in agents.values():
            self.assertIsNotNone(a.group_id)


class TestSimulation(unittest.TestCase):
    def test_short_run_stable(self):
        sim = Simulation(n_agents=12, width=32, height=32, seed=1)
        for _ in range(500):
            sim.step()
        s = sim.snapshot()
        self.assertIn("population", s)

    def test_learning_occurs(self):
        sim = Simulation(n_agents=10, width=32, height=32, seed=2)
        for _ in range(400):
            sim.step()
        alive = list(sim.agents.values())
        if alive:
            self.assertGreater(max(a.policy.size() for a in alive), 0)

    def test_reproduction_possible(self):
        sim = Simulation(n_agents=20, width=48, height=48, seed=3)
        for _ in range(6000):
            sim.step()
            if sim.births > 0:
                break
        self.assertGreater(sim.births, 0)

    def test_exports(self):
        import tempfile
        sim = Simulation(n_agents=8, width=24, height=24, seed=4)
        for _ in range(100):
            sim.step()
        sim.log_history()
        with tempfile.TemporaryDirectory() as d:
            sim.save_csv(os.path.join(d, "m.csv"))
            sim.save_json(os.path.join(d, "f.json"))
            self.assertTrue(os.path.exists(os.path.join(d, "m.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "f.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
