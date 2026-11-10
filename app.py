"""Tableau de bord Streamlit : visualisation en direct de la simulation.

Lancement :
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import streamlit as st

from sim import config as C
from sim.simulation import Simulation

st.set_page_config(page_title="Survie évolutive — MAS RL", page_icon="🧬",
                   layout="wide")

BIOME_COLORS = {
    "foret": (34, 102, 34),
    "plaine": (150, 200, 100),
    "montagne": (125, 125, 125),
    "riviere": (60, 120, 220),
    "lac": (30, 80, 180),
    "grotte": (92, 78, 62),
    "desert": (232, 202, 138),
    "fertile": (178, 220, 80),
}
BUILDING_COLOR = (40, 40, 40)
FIRE_COLOR = (220, 60, 20)
AGENT_M_COLOR = (255, 255, 255)
AGENT_F_COLOR = (255, 105, 180)

LEGEND_HTML = """
<div style="font-size:0.85rem; line-height:1.7">
<span style="color:rgb(34,102,34)">■</span> forêt&nbsp;&nbsp;
<span style="color:rgb(150,200,100)">■</span> plaine&nbsp;&nbsp;
<span style="color:rgb(125,125,125)">■</span> montagne&nbsp;&nbsp;
<span style="color:rgb(60,120,220)">■</span> rivière&nbsp;&nbsp;
<span style="color:rgb(30,80,180)">■</span> lac&nbsp;&nbsp;
<span style="color:rgb(92,78,62)">■</span> grotte&nbsp;&nbsp;
<span style="color:rgb(232,202,138)">■</span> désert&nbsp;&nbsp;
<span style="color:rgb(178,220,80)">■</span> fertile&nbsp;&nbsp;|&nbsp;&nbsp;
<span style="color:rgb(40,40,40)">■</span> bâtiment&nbsp;&nbsp;
<span style="color:rgb(220,60,20)">■</span> feu&nbsp;&nbsp;|&nbsp;&nbsp;
<span style="color:rgb(255,255,255)">■</span> agent M&nbsp;&nbsp;
<span style="color:rgb(255,105,180)">■</span> agent F
</div>
"""


def render_map(world, agents, scale: int = 8) -> np.ndarray:
    """Carte RGB : biomes, bâtiments, feux, agents (M blanc, F rose)."""
    img = np.zeros((world.height, world.width, 3), dtype=np.uint8)
    for y in range(world.height):
        for x in range(world.width):
            tile = world.tiles[y][x]
            if tile.fire > 0:
                img[y, x] = FIRE_COLOR
            elif tile.building:
                img[y, x] = BUILDING_COLOR
            else:
                img[y, x] = BIOME_COLORS.get(tile.biome, (0, 0, 0))
    for a in agents:
        if a.alive:
            img[a.y, a.x] = AGENT_F_COLOR if a.sex == "F" else AGENT_M_COLOR
    return np.kron(img, np.ones((scale, scale, 1), dtype=np.uint8))


def new_simulation(seed: int, n_agents: int, size: int, max_pop: int) -> Simulation:
    return Simulation(n_agents=n_agents, width=size, height=size,
                      seed=seed, max_population=max_pop)


# ----------------------------------------------------------------- état
if "sim" not in st.session_state:
    st.session_state.sim = new_simulation(42, 30, 64, C.MAX_POPULATION)
    st.session_state.running = False

sim = st.session_state.sim

# ----------------------------------------------------------------- barre latérale
with st.sidebar:
    st.title("🧬 Survie évolutive")
    st.caption("Agents Q-learning : tout le comportement social est appris.")

    seed = st.number_input("Graine", 0, 10**9, 42)
    n_agents = st.slider("Population initiale", 5, 100, 30)
    size = st.slider("Taille de la carte", 24, 128, 64, step=8)
    max_pop = st.slider("Population maximale", 20, 300, C.MAX_POPULATION)

    col1, col2 = st.columns(2)
    if col1.button("▶️ Play", use_container_width=True):
        st.session_state.running = True
    if col2.button("⏸ Pause", use_container_width=True):
        st.session_state.running = False

    col3, col4 = st.columns(2)
    if col3.button("⏩ +100 ticks", use_container_width=True):
        for _ in range(100):
            sim.step()
        sim.log_history()
    if col4.button("⏩ +1000 ticks", use_container_width=True):
        for _ in range(1000):
            sim.step()
        sim.log_history()

    if st.button("🔄 Nouvelle simulation", use_container_width=True):
        st.session_state.sim = new_simulation(int(seed), int(n_agents),
                                              int(size), int(max_pop))
        st.session_state.running = False
        st.rerun()

    ticks_per_frame = st.slider("Ticks par image", 1, 50, 5)
    delay = st.slider("Pause entre images (s)", 0.0, 1.0, 0.05, 0.05)

    st.divider()
    st.caption("L'apprentissage est visible : les agents meurent moins et "
               "coopèrent davantage au fil des générations.")

# ----------------------------------------------------------------- boucle temps réel
if st.session_state.running:
    for _ in range(ticks_per_frame):
        sim.step()
    sim.log_history()
    if delay:
        time.sleep(delay)
    st.rerun()

# ----------------------------------------------------------------- indicateurs
s = sim.snapshot()
season_emoji = {"printemps": "🌸", "ete": "☀️", "automne": "🍂", "hiver": "❄️"}

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Population", s["population"], f"max {sim.max_population}")
m2.metric("Jour", s["jour"], f"{season_emoji.get(s['saison'], '')} {s['saison']}")
m3.metric("Naissances", s["naissances"])
m4.metric("Décès", s["deces"])
m5.metric("Groupes", s["groupes"], ", ".join(s["types_groupes"]) or "—")
m6.metric("Alliances", s["alliances"])

st.divider()

# ----------------------------------------------------------------- carte + activité
col_map, col_charts = st.columns([3, 2])

with col_map:
    st.subheader("Carte du monde")
    agents = list(sim.agents.values())
    st.image(render_map(sim.world, agents), use_container_width=True)
    st.markdown(LEGEND_HTML, unsafe_allow_html=True)
    st.caption(f"Tick {s['tick']} | météo : {sim.world.weather} | "
               f"bâtiments : {s['batiments']} | pièges : {s['pieges']} | "
               f"échanges : {s['echanges']} | attaques : {s['attaques']}")

with col_charts:
    st.subheader("Dynamique de population")
    if sim.history:
        df = pd.DataFrame(sim.history)
        st.line_chart(df.set_index("tick")[["population", "naissances", "deces"]],
                      height=220)
        st.subheader("Social et technique")
        st.line_chart(df.set_index("tick")[["alliances", "echanges",
                                            "attaques", "recettes_connues_moy"]],
                      height=220)
    else:
        st.info("Lancez la simulation (▶️ ou ⏩) pour voir les courbes.")

st.divider()

# ----------------------------------------------------------------- groupes et agents
col_groups, col_inspect, col_deaths = st.columns([2, 2, 1])

with col_groups:
    st.subheader("Groupes émergents")
    if sim.social.groups:
        rows = []
        for g in sim.social.groups.values():
            rows.append({
                "Groupe": g.id,
                "Type": g.kind,
                "Membres": len(g.members),
                "Bâtiments": len(g.buildings),
                "Relations": ", ".join(f"{k}:{v:.1f}" for k, v in g.relations.items()) or "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun groupe : les alliances mutuelles ne sont pas encore "
                "suffisamment nombreuses (seuil : 3).")

with col_inspect:
    st.subheader("Inspecteur d'agent")
    alive_ids = sorted(sim.agents.keys())
    if alive_ids:
        aid = st.selectbox("Agent", alive_ids)
        a = sim.agents[aid]
        i1, i2, i3 = st.columns(3)
        i1.metric("Santé", f"{a.health:.0f}")
        i2.metric("Énergie", f"{a.energy:.0f}")
        i3.metric("Réputation", f"{a.reputation:.0f}")
        i4, i5, i6 = st.columns(3)
        i4.metric("Faim", f"{a.hunger:.0f}")
        i5.metric("Soif", f"{a.thirst:.0f}")
        i6.metric("Âge", a.age)
        st.write(f"**Sexe** {a.sex} | **Groupe** {a.group_id or 'aucun'} | "
                 f"**Alliés** {len(a.allies)} | **Ennemis** {len(a.enemies)}")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Inventaire")
            st.write(dict(a.inventory) or "vide")
            st.caption("Compétences")
            st.write({k: round(v, 2) for k, v in a.skills.items()})
        with c2:
            st.caption("Recettes connues")
            st.write(", ".join(sorted(a.knowledge.recipes)))
            st.caption("Politique RL")
            st.write(f"{a.policy.size()} états | ε = {a.policy.epsilon:.3f} | "
                     f"α = {a.policy.alpha:.2f}")
    else:
        st.warning("Tous les agents sont morts — lancez une nouvelle simulation.")

with col_deaths:
    st.subheader("Causes de décès")
    if sim.death_causes:
        st.bar_chart(pd.Series(sim.death_causes, name="décès"), height=260)
    else:
        st.caption("Aucun décès pour l'instant.")
