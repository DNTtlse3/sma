"""Génome des agents : caractéristiques héritées et mutables."""

from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

GENES = (
    "apprentissage",   # taux d'apprentissage RL
    "agressivite",     # modulateur de récompense de conflit
    "sociabilite",     # probabilité d'initier des interactions
    "curiosite",       # exploration / epsilon de base
    "endurance",       # drain d'énergie réduit
    "force",           # dégâts de combat et capacité de collecte
    "memoire",         # taille mémoire spatiale / sociale
    "vision",          # rayon de perception
    "longevite",       # âge maximal
    "immunite",        # résistance aux maladies et catastrophes
)

GENE_RANGE = (0.05, 1.0)
MUTATION_RATE = 0.15
MUTATION_SIGMA = 0.08


def _clamp(v: float) -> float:
    return max(GENE_RANGE[0], min(GENE_RANGE[1], v))


@dataclass
class Genome:
    genes: dict = field(default_factory=dict)

    @staticmethod
    def random(rng: random.Random) -> "Genome":
        return Genome({g: rng.uniform(*GENE_RANGE) for g in GENES})

    @staticmethod
    def inherit(parent_a: "Genome", parent_b: "Genome",
                rng: random.Random) -> "Genome":
        """Croisement uniforme + mutations aléatoires."""
        genes = {}
        for g in GENES:
            value = rng.choice((parent_a.genes[g], parent_b.genes[g]))
            if rng.random() < MUTATION_RATE:
                value += rng.gauss(0.0, MUTATION_SIGMA)
            genes[g] = _clamp(value)
        return Genome(genes)

    def mutate_alone(self, rng: random.Random) -> None:
        for g in GENES:
            if rng.random() < MUTATION_RATE * 0.5:
                self.genes[g] = _clamp(self.genes[g] + rng.gauss(0.0, MUTATION_SIGMA))

    def __getitem__(self, gene: str) -> float:
        return self.genes[gene]

    def to_dict(self) -> dict:
        return asdict(self)
