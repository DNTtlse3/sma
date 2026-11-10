"""Apprentissage par renforcement : Q-learning tabulaire, epsilon-glouton.

Chaque agent possède sa propre politique. L'état est une discrétisation
de l'environnement local et de l'état interne ; aucune connaissance
globale du monde n'est utilisée.
"""

from __future__ import annotations

import random

from . import config as C

# Espace d'actions discrètes : navigation relative aux buts connus
# (l'agent apprend QUAND poursuivre chaque but, pas comment marcher)
ACTIONS = (
    "move_eau", "move_nourriture", "move_materiau", "explore",
    "collect", "drink", "eat", "craft", "build",
    "rest", "social", "attack", "flee", "mate", "set_trap", "transmit",
)
N_ACTIONS = len(ACTIONS)
ACTION_INDEX = {a: i for i, a in enumerate(ACTIONS)}


def discretize_state(obs: dict) -> tuple:
    """Discrétisation compacte de l'observation locale en état tabulaire."""
    return (
        min(3, int(obs["faim"] // 25)),
        min(3, int(obs["soif"] // 25)),
        min(2, int(obs["energie"] // 34)),
        min(2, int(obs["sante"] // 34)),
        1 if obs["jour"] else 0,
        1 if obs["saison"] == 3 else 0,        # hiver ou non
        1 if obs["eau_proche"] else 0,
        1 if obs["nourriture_proche"] else 0,
        1 if obs["materiau_proche"] else 0,
        min(1, obs["agents_proches"]),
        min(1, obs["hostilite"]),              # 0 paisible, 1 menacé
        1 if obs["a_arme"] else 0,
        1 if obs["a_outil"] else 0,
        min(1, int(obs["remplissage"] // 50)),
    )


class QPolicy:
    """Politique Q-learning individuelle."""

    def __init__(self, alpha: float, epsilon: float,
                 gamma: float = C.GAMMA, seed: int | None = None):
        self.alpha = alpha
        self.epsilon = epsilon
        self.gamma = gamma
        self.rng = random.Random(seed)
        self.q: dict = {}
        self.steps = 0

    def q_values(self, state) -> list:
        vals = self.q.get(state)
        if vals is None:
            vals = [0.0] * N_ACTIONS
            self.q[state] = vals
        return vals

    def act(self, state, exploit: bool = False) -> str:
        self.steps += 1
        if not exploit and self.rng.random() < self.epsilon:
            return ACTIONS[self.rng.randrange(N_ACTIONS)]
        vals = self.q_values(state)
        best = max(vals)
        best_actions = [ACTIONS[i] for i, v in enumerate(vals) if v == best]
        return self.rng.choice(best_actions)

    def learn(self, state, action: str, reward: float, next_state, done: bool) -> None:
        i = ACTION_INDEX[action]
        vals = self.q_values(state)
        next_max = 0.0 if done else max(self.q_values(next_state))
        target = reward + self.gamma * next_max
        vals[i] += self.alpha * (target - vals[i])

    def decay_epsilon(self) -> None:
        self.epsilon = max(C.EPSILON_MIN, self.epsilon * C.EPSILON_DECAY)

    def size(self) -> int:
        return len(self.q)
