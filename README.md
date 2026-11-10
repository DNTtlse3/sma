# Système Multi-Agents de Survie Évolutive par Apprentissage par Renforcement

Simulation d'un monde ouvert peuplé d'agents autonomes qui apprennent
exclusivement par interaction avec l'environnement (Q-learning tabulaire,
epsilon-glouton). Aucun comportement social complexe n'est programmé :
coopération, alliances, commerce, conflits, groupes et technologies
**émergent** de l'apprentissage individuel et de la sélection naturelle.

## Installation

Aucune dépendance externe — Python 3.10+ uniquement (bibliothèque standard).

```bash
python main.py --steps 8000 --agents 30 --seed 7
```

## Utilisation

```
python main.py --help

Options principales :
  --steps N         nombre de ticks simulés (défaut 3000)
  --agents N        population initiale (défaut 30)
  --map LxH         taille de la carte (défaut 64x64)
  --seed N          graine aléatoire (reproductibilité)
  --log-every N     période d'enregistrement des métriques (CSV)
  --print-every N   période d'affichage console
  --max-pop N       population maximale (régulation malthusienne)
  --map-snapshot    affiche la carte ASCII au démarrage
  --out DIR         répertoire de sortie (métriques CSV + état JSON)
```

Tests :

```bash
python -m unittest tests.test_sim -v
```

## Architecture

```
main.py                 CLI : lance la simulation, affiche et exporte
sim/
  config.py             constantes : biomes, ressources, recettes, bâtiments,
                        pièges, récompenses, physiologie, social
  world.py              carte 2D (8 biomes), ressources, régénération,
                        jour/nuit, saisons, météo, catastrophes naturelles
  genome.py             génome (10 gènes) : héritage croisé + mutations
  memory.py             mémoires spatiale (LRU), sociale, connaissances
  rl.py                 Q-learning tabulaire : état discrétisé, 16 actions
  agent.py              agent : physiologie, inventaire, compétences,
                        perception locale limitée (vision + mémoire)
  actions.py            exécution des actions : navigation, collecte, eau,
                        alimentation, fabrication, construction, pièges,
                        combat (riposte, pillage), fuite
  social.py             réputation, confiance, échanges (honnêtes ou trahis),
                        alliances, trahisons, transmission culturelle,
                        groupes (famille → clan → tribu → société)
  simulation.py         boucle principale : perception → décision → action →
                        récompense → apprentissage ; reproduction, génétique,
                        groupes, production agricole, métriques
tests/test_sim.py       21 tests unitaires et d'intégration
```

## Couverture de la spécification

| § | Exigence | Implémentation |
|---|----------|----------------|
| 1 | Survie maximisée par RL, zéro comportement programmé | Politique Q individuelle par agent ; seuls des réflexes homéostatiques aux seuils critiques évitent les morts absurdes pendant la convergence |
| 2 | Monde 2D, 8 biomes, dynamique | `world.py` : forêts, plaines, montagnes, rivières, lacs, grottes, déserts, zones fertiles ; jour/nuit, 4 saisons, météo, régénération, 4 catastrophes |
| 3 | Attributs agents | id, sexe, âge, santé, énergie, faim, soif, mémoires, inventaire, compétences, réputation, politique RL |
| 4 | Capacités | 16 actions : navigation orientée, exploration, collecte, fabrication, construction, interactions, combat, fuite, piégeage, transmission, reproduction |
| 5-8 | Ressources, fabrication, construction, pièges | 9 ressources naturelles + 7 transformées ; 22 recettes (outils, armes, armures) ; 17 bâtiments (défense/habitat/production) ; 5 pièges (chasse, protection, embuscade) |
| 9 | Perception limitée | vision bornée par génome, mémoire spatiale LRU, mémoire sociale ; aucune connaissance globale |
| 10-13 | Social, réputation, alliances, groupes | dialogues/échanges/alliances/trahisons appris ; réputation évolutive (honnêteté, agressivité, coopération, trahisons, utilité) ; familles → clans → tribus → sociétés avec bâtiments et relations |
| 14-15 | Reproduction, génétique | accouplement par proposition/acceptation (maturité, santé, ressources, confiance) ; croisement uniforme + mutations sur 10 gènes |
| 16-17 | Apprentissage, récompenses | Q-learning par agent (α hérité, ε lié à la curiosité) ; récompenses positives (survie, nourriture, fabrication, construction, défense, coopération, descendance adulte) et négatives (blessure, famine, pertes, mort) |
| 18 | Conflits | attaques opportunistes si rentables, représailles collectives, guerres inter-groupes émergentes (relations ≤ -2) |
| 19 | Transmission | partage de recettes et de souvenirs spatiaux aux alliés/membres du groupe ; héritage partiel des Q-valeurs parentales (culture cumulative) |
| 20 | Phénomènes émergents observables | métriques : population, naissances/décès par cause, groupes et types, alliances, échanges, attaques, guerres, bâtiments, pièges, recettes moyennes |

## Décisions de conception importantes

1. **Actions relatives aux buts** (`move_eau`, `move_nourriture`, `move_materiau`) :
   la navigation vers une ressource connue est une capacité fondamentale ;
   l'agent apprend *quand* poursuivre chaque but. Un espace d'actions
   directionnelles rendrait l'état trop fragmenté pour un Q-learning tabulaire.

2. **Façonnage de progression** : chaque pas réduisant la distance à une
   ressource utile est légèrement récompensé selon le besoin courant —
   sinon le crédit d'arrivée est trop différé pour être appris.

3. **Réflexes homéostatiques** (boire/manger/se reposer aux seuils critiques) :
   évitent les morts absurdes pendant la convergence ; tout le reste du
   comportement reste appris.

4. **Économie du combat** : attaquer coûte de l'énergie, expose à une riposte,
   dégrade la réputation si non provoqué ; le pillage partiel est le seul gain.
   Les blessés graves rompent l'engagement. La guerre n'est donc apprise
   que lorsqu'elle est rentable — elle émerge avec les armes et les groupes.

5. **Culture cumulative** : l'innovation (découverte de recettes par
   expérimentation, favorisée par curiosité/apprentissage) + transmission
   sociale + héritage partiel des Q-valeurs parentales → évolution
   technologique inter-générationnelle.

## Sorties

- `results/metriques.csv` — historique des métriques à chaque période de log
- `results/etat_final.json` — état final détaillé + groupes + historique
- console — carte ASCII, suivi périodique, causes de décès, groupes émergents

## Exemple de résultats observés (graine 7, 8000 ticks)

- population 30 → 90, quasi zéro mortalité précoce
- 17 groupes : familles, clans, **tribus** (jusqu'à 15 membres)
- 468 alliances mutuelles, 367 échanges de ressources
- diffusion technologique : 4 recettes de base → 6.6 en moyenne
- 413 bâtiments (dont forges, greniers, tours de garde)
- violence résiduelle (46 attaques) — le conflit coûte plus qu'il ne rapporte
  en temps de paix
