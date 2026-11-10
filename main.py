#!/usr/bin/env python3
"""Point d'entrée CLI du système multi-agents de survie évolutive.

Exemples :
    python main.py --steps 3000 --agents 40 --seed 42
    python main.py --steps 5000 --agents 60 --map 96x96 --log-every 100 --out results
    python main.py --steps 500 --agents 20 --map-snapshot
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim import config as C
from sim.simulation import Simulation


def parse_args():
    p = argparse.ArgumentParser(description="Système multi-agents de survie évolutive par RL")
    p.add_argument("--steps", type=int, default=3000, help="nombre de ticks simulés")
    p.add_argument("--agents", type=int, default=30, help="population initiale")
    p.add_argument("--map", type=str, default=f"{C.MAP_WIDTH}x{C.MAP_HEIGHT}", help="taille LxH")
    p.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    p.add_argument("--log-every", type=int, default=200, help="période d'enregistrement des métriques")
    p.add_argument("--print-every", type=int, default=500, help="période d'affichage console")
    p.add_argument("--out", type=str, default="results", help="répertoire de sortie")
    p.add_argument("--map-snapshot", action="store_true", help="afficher la carte ASCII au début")
    p.add_argument("--max-pop", type=int, default=C.MAX_POPULATION, help="population maximale")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if "x" in args.map:
        w, h = (int(v) for v in args.map.split("x", 1))
    else:
        w = h = int(args.map)

    sim = Simulation(n_agents=args.agents, width=w, height=h,
                     seed=args.seed, max_population=args.max_pop)
    print(f"=== Simulation de survie évolutive ===")
    print(f"Carte {w}x{h} | agents initiaux : {args.agents} | graine : {args.seed}")
    if args.map_snapshot:
        print(sim.world.ascii_map())

    os.makedirs(args.out, exist_ok=True)
    log_every = max(1, args.log_every)

    for step in range(1, args.steps + 1):
        sim.step()
        if step % log_every == 0:
            sim.log_history()
        if step % args.print_every == 0 or step == args.steps:
            s = sim.snapshot()
            print(f"[t={s['tick']:>6} j={s['jour']:>3} {s['saison']:<10}] "
                  f"pop={s['population']:>3} naiss={s['naissances']:>3} "
                  f"décès={s['deces']:>3} groupes={s['groupes']:>2} "
                  f"alliances={s['alliances']:>3} échanges={s['echanges']:>4} "
                  f"attaques={s['attaques']:>4} bâtiments={s['batiments']:>3} "
                  f"recettes={s['recettes_connues_moy']:.1f}")

    csv_path = os.path.join(args.out, "metriques.csv")
    json_path = os.path.join(args.out, "etat_final.json")
    sim.save_csv(csv_path)
    sim.save_json(json_path)
    s = sim.snapshot()
    print("\n--- État final ---")
    for k, v in s.items():
        print(f"  {k}: {v}")
    print(f"\nCauses de décès : {dict(sim.death_causes)}")
    if sim.social.groups:
        print("Groupes émergents :")
        for g in sim.social.groups.values():
            print(f"  {g.id} ({g.kind}) : {len(g.members)} membres, "
                  f"{len(g.buildings)} bâtiments")
    print(f"\nMétriques : {csv_path}")
    print(f"État final : {json_path}")


if __name__ == "__main__":
    main()
