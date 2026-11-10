"""Test du tableau de bord Streamlit via le framework AppTest officiel."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

from streamlit.testing.v1 import AppTest


def click_button(at, label: str):
    button = next(b for b in at.button if b.label == label)
    button.click().run()


class TestDashboard(unittest.TestCase):
    def test_app_loads_without_exception(self):
        at = AppTest.from_file(APP_PATH, default_timeout=120)
        at.run()
        self.assertFalse(at.exception, msg=str(at.exception))

    def test_advance_100_ticks(self):
        at = AppTest.from_file(APP_PATH, default_timeout=180)
        at.run()
        click_button(at, "⏩ +100 ticks")
        self.assertFalse(at.exception)
        sim = at.session_state["sim"]
        self.assertEqual(sim.tick, 100)

    def test_new_simulation_resets_state(self):
        at = AppTest.from_file(APP_PATH, default_timeout=180)
        at.run()
        click_button(at, "⏩ +100 ticks")
        click_button(at, "🔄 Nouvelle simulation")
        self.assertFalse(at.exception)
        sim = at.session_state["sim"]
        self.assertEqual(sim.tick, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
