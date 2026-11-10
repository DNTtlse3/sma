"""Configuration globale du système multi-agents de survie évolutive.

Toutes les constantes de simulation, biomes, ressources, recettes,
bâtiments, pièges et pondérations de récompense sont centralisés ici.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Monde
# ---------------------------------------------------------------------------
MAP_WIDTH = 64
MAP_HEIGHT = 64

TICKS_PER_DAY = 120
DAYS_PER_SEASON = 20
SEASONS = ("printemps", "ete", "automne", "hiver")

WEATHERS = ("clair", "pluie", "orage", "secheresse", "neige")
WEATHER_PROBS = {
    "printemps": [("clair", 0.6), ("pluie", 0.3), ("orage", 0.1)],
    "ete": [("clair", 0.7), ("secheresse", 0.2), ("orage", 0.1)],
    "automne": [("clair", 0.6), ("pluie", 0.3), ("orage", 0.1)],
    "hiver": [("clair", 0.4), ("neige", 0.4), ("pluie", 0.2)],
}

DISASTER_INTERVAL = 900          # ticks moyens entre deux catastrophes
DISASTER_RADIUS = 6

VISION_RADIUS = 5
MAX_POPULATION = 120

# ---------------------------------------------------------------------------
# Biomes : ressources de base et régénération par tick
# ---------------------------------------------------------------------------
BIOMES = {
    "foret":    {"ressources": {"bois": 8, "plantes": 6, "fruits": 6, "animaux": 3}, "regen": 0.08},
    "plaine":   {"ressources": {"plantes": 8, "animaux": 4, "pierre": 1}, "regen": 0.06},
    "montagne": {"ressources": {"pierre": 6, "minerais": 3}, "regen": 0.01},
    "riviere":  {"ressources": {"eau": 200, "argile": 3, "plantes": 2}, "regen": 0.5},
    "lac":      {"ressources": {"eau": 300, "animaux": 2}, "regen": 0.5},
    "grotte":   {"ressources": {"pierre": 4, "minerais": 4, "sable": 1}, "regen": 0.005},
    "desert":   {"ressources": {"sable": 8}, "regen": 0.002},
    "fertile":  {"ressources": {"plantes": 9, "fruits": 8, "eau": 5, "animaux": 3}, "regen": 0.12},
}

BIOME_PROBS = {
    "plaine": 0.30, "foret": 0.22, "montagne": 0.12, "desert": 0.10,
    "fertile": 0.10, "riviere": 0.08, "lac": 0.05, "grotte": 0.03,
}

# Vitesse de déplacement (coût énergétique par case)
MOVE_ENERGY_COST = {"montagne": 0.9, "desert": 0.6, "default": 0.35}

# ---------------------------------------------------------------------------
# Ressources
# ---------------------------------------------------------------------------
NATURAL_RESOURCES = ("bois", "pierre", "sable", "argile", "eau", "plantes",
                     "fruits", "minerais", "animaux")
TRANSFORMED_RESOURCES = ("planches", "briques", "cordes", "cuir", "acier",
                         "poudre_explosive", "carburant")
ALL_RESOURCES = NATURAL_RESOURCES + TRANSFORMED_RESOURCES

# Valeur alimentaire / hydratation
FOOD_VALUE = {"fruits": 35, "plantes": 25, "animaux": 60}
WATER_VALUE = 30

# ---------------------------------------------------------------------------
# Fabrication : recettes
#   inputs : ressources consommées
#   skill  : compétence améliorée par la pratique
#   needs  : bâtiment requis (facultatif)
# ---------------------------------------------------------------------------
RECIPES = {
    # Ressources transformées
    "planches":          {"inputs": {"bois": 2}, "skill": "artisanat", "needs": None},
    "briques":           {"inputs": {"argile": 2}, "skill": "artisanat", "needs": None},
    "cordes":            {"inputs": {"plantes": 2}, "skill": "artisanat", "needs": None},
    "cuir":              {"inputs": {"animaux": 1}, "skill": "artisanat", "needs": None},
    "acier":             {"inputs": {"minerais": 2, "bois": 1}, "skill": "forge", "needs": "forge"},
    "poudre_explosive":  {"inputs": {"sable": 2, "minerais": 1}, "skill": "forge", "needs": "forge"},
    "carburant":         {"inputs": {"plantes": 3, "animaux": 1}, "skill": "forge", "needs": "forge"},
    # Outils
    "hache":             {"inputs": {"bois": 1, "pierre": 2, "cordes": 1}, "skill": "artisanat", "needs": None},
    "pioche":            {"inputs": {"bois": 1, "pierre": 2, "cordes": 1}, "skill": "artisanat", "needs": None},
    "marteau":           {"inputs": {"bois": 1, "pierre": 2, "cordes": 1}, "skill": "artisanat", "needs": None},
    "pelle":             {"inputs": {"bois": 1, "pierre": 1, "cordes": 1}, "skill": "artisanat", "needs": None},
    "scie":              {"inputs": {"bois": 2, "acier": 1}, "skill": "forge", "needs": "forge"},
    # Armes
    "baton":             {"inputs": {"bois": 1}, "skill": "artisanat", "needs": None},
    "lance":             {"inputs": {"bois": 2, "pierre": 1, "cordes": 1}, "skill": "artisanat", "needs": None},
    "couteau":           {"inputs": {"pierre": 1, "cordes": 1}, "skill": "artisanat", "needs": None},
    "arc":               {"inputs": {"bois": 1, "cordes": 2}, "skill": "artisanat", "needs": None},
    "arbalete":          {"inputs": {"bois": 2, "cordes": 2, "acier": 1}, "skill": "forge", "needs": "forge"},
    "epee":              {"inputs": {"acier": 2, "cordes": 1}, "skill": "forge", "needs": "forge"},
    "arme_a_feu":        {"inputs": {"acier": 2, "bois": 1, "poudre_explosive": 1}, "skill": "forge", "needs": "forge"},
    # Armures
    "armure_cuir":       {"inputs": {"cuir": 3, "cordes": 1}, "skill": "artisanat", "needs": None},
    "armure_bois":       {"inputs": {"planches": 3, "cordes": 1}, "skill": "artisanat", "needs": None},
    "armure_metal":      {"inputs": {"acier": 3, "cuir": 1}, "skill": "forge", "needs": "forge"},
}

WEAPON_POWER = {"baton": 1.2, "couteau": 1.5, "lance": 1.8, "arc": 2.0,
                "arbalete": 2.6, "epee": 3.0, "arme_a_feu": 4.5}
ARMOR_PROTECTION = {"armure_cuir": 0.15, "armure_bois": 0.20, "armure_metal": 0.35}

# Recettes connues à la naissance (le reste se transmet socialement)
BASE_KNOWN_RECIPES = ("baton", "couteau", "cordes", "hache")

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
BUILDINGS = {
    # Défense
    "mur":                {"cost": {"pierre": 4}, "defense": 0.10, "storage": 0, "shelter": 0},
    "palissade":          {"cost": {"bois": 4}, "defense": 0.08, "storage": 0, "shelter": 0},
    "fosse":              {"cost": {"sable": 3}, "defense": 0.06, "storage": 0, "shelter": 0},
    "rempart":            {"cost": {"pierre": 8, "briques": 4}, "defense": 0.20, "storage": 0, "shelter": 0},
    "tour_de_garde":      {"cost": {"bois": 6, "pierre": 6}, "defense": 0.25, "storage": 0, "shelter": 0},
    "porte_fortifiee":    {"cost": {"bois": 4, "acier": 1}, "defense": 0.15, "storage": 0, "shelter": 0},
    # Habitat
    "tente":              {"cost": {"cuir": 2, "cordes": 2}, "defense": 0.0, "storage": 5, "shelter": 0.3},
    "maison":             {"cost": {"bois": 6, "planches": 4, "pierre": 2}, "defense": 0.05, "storage": 15, "shelter": 0.7},
    "ferme":              {"cost": {"bois": 4, "planches": 2, "eau": 5}, "defense": 0.0, "storage": 10, "shelter": 0.2, "produces": ("fruits", "plantes")},
    "atelier":            {"cost": {"bois": 5, "pierre": 3}, "defense": 0.0, "storage": 10, "shelter": 0.4},
    "grenier":            {"cost": {"bois": 5, "planches": 3}, "defense": 0.0, "storage": 25, "shelter": 0.3},
    "entrepot":           {"cost": {"bois": 8, "pierre": 4}, "defense": 0.0, "storage": 40, "shelter": 0.3},
    # Production
    "forge":              {"cost": {"pierre": 6, "bois": 4, "minerais": 2}, "defense": 0.0, "storage": 5, "shelter": 0.3},
    "scierie":            {"cost": {"bois": 6, "pierre": 2}, "defense": 0.0, "storage": 5, "shelter": 0.2},
    "moulin":             {"cost": {"bois": 6, "pierre": 4}, "defense": 0.0, "storage": 10, "shelter": 0.2},
    "puits":              {"cost": {"pierre": 5, "bois": 2}, "defense": 0.0, "storage": 0, "shelter": 0.0, "produces": ("eau",)},
    "irrigation":         {"cost": {"pierre": 4, "argile": 4, "eau": 10}, "defense": 0.0, "storage": 0, "shelter": 0.0},
}

# ---------------------------------------------------------------------------
# Pièges
# ---------------------------------------------------------------------------
TRAPS = {
    "piege_a_fosse":     {"cost": {"pelle": 1, "bois": 1}, "damage": 15, "capture": False},
    "piege_a_pointes":   {"cost": {"bois": 2, "pierre": 2}, "damage": 25, "capture": False},
    "collet":            {"cost": {"cordes": 2}, "damage": 5, "capture": True},
    "piege_explosif":    {"cost": {"poudre_explosive": 1, "cordes": 1}, "damage": 60, "capture": False},
    "piege_mecanique":   {"cost": {"bois": 3, "cordes": 1, "pierre": 1}, "damage": 20, "capture": True},
}

# ---------------------------------------------------------------------------
# Récompenses (apprentissage par renforcement)
# ---------------------------------------------------------------------------
REWARDS = {
    "survie_tick": 0.02,
    "nourriture": 1.0,
    "eau": 1.0,
    "collecte": 0.3,
    "fabrication": 1.0,
    "construction": 1.5,
    "piege_pose": 0.6,
    "defense_reussie": 1.2,
    "cooperation": 0.5,
    "transmission": 0.3,
    "descendance_adulte": 5.0,
    "reproduction": 3.0,
    "blessure": -1.0,
    "famine": -0.4,
    "soif": -0.4,
    "perte_ressources": -0.5,
    "batiment_detruit": -1.0,
    "allie_blesse": -0.8,
    "mort": -10.0,
}

# ---------------------------------------------------------------------------
# Agents : constantes physiologiques
# ---------------------------------------------------------------------------
START_HEALTH = 100.0
MAX_ENERGY = 100.0
HUNGER_RATE = 0.08          # par tick
THIRST_RATE = 0.10
ENERGY_RATE = 0.02
AGING_TICKS = 1             # 1 tick = 1 unité d'âge fine
MATURITY_AGE = 2400         # ~20 jours simulés
OLD_AGE_BASE = 24000
REPRO_COOLDOWN = 900
PREGNANCY_TICKS = 600

# ---------------------------------------------------------------------------
# Apprentissage par renforcement
# ---------------------------------------------------------------------------
GAMMA = 0.95
EPSILON_DECAY = 0.9995
EPSILON_MIN = 0.05
LEARNING_RATE_RANGE = (0.1, 0.35)

# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------
COMBAT_COOLDOWN = 12        # ticks entre deux coups sur la même cible

ALLIANCE_THRESHOLD = 3      # alliances mutuelles nécessaires pour former un groupe
TRUST_ALLY = 40.0
BETRAY_REPUTATION = -15.0
DEFECT_REPUTATION = -8.0
COOP_REPUTATION = 3.0
