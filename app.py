"""Interface graphique du projet (Streamlit).

Lit les sorties précalculées par `python scenarios.py --all`
(sectors/<slug>/resultats.json + carte_<scenario>.png) pour un affichage instantané.
Lancement : streamlit run app.py
"""
import json
import os

import pandas as pd
import streamlit as st

from scenarios import SECTORS, SECTORS_DIR

st.set_page_config(page_title="Déneiger Montréal", layout="wide")
st.title("Déneiger Montréal — priorisation des tournées")

slug = st.sidebar.selectbox("Secteur", list(SECTORS.keys()))
scenario = st.sidebar.selectbox(
    "Scénario", ["arteriel", "services", "transport", "baseline"]
)

results_path = os.path.join(SECTORS_DIR, slug, "resultats.json")
if not os.path.exists(results_path):
    st.warning("Résultats absents. Lance d'abord : python scenarios.py --all")
    st.stop()

with open(results_path, encoding="utf-8") as f:
    results = json.load(f)

r = results[scenario]

col1, col2, col3 = st.columns(3)
col1.metric("Coût total ($)", r["cout_total"])
col2.metric("Km parcourus", r["km_total"])
col3.metric("Heures totales", r["heures_total"])
if "T1_reseau_prioritaire_h" in r:
    st.metric("T1 — réseau prioritaire dégagé (h)", r["T1_reseau_prioritaire_h"])

st.subheader("Carte du réseau prioritaire")
png = os.path.join(SECTORS_DIR, slug, f"carte_{scenario}.png")
if os.path.exists(png):
    st.image(png, use_container_width=True)
else:
    st.info("Carte non disponible pour ce scénario.")

st.subheader("Coût en fonction du nombre de véhicules")
curve = pd.DataFrame(r["courbe_cout"], columns=["N", "coût ($)"]).set_index("N")
st.line_chart(curve)

st.subheader("Comparatif des scénarios (ce secteur)")
st.table([
    {"scénario": s, "coût": v["cout_total"], "km": v["km_total"],
     "heures": v["heures_total"], "à vide %": round(v["part_a_vide"] * 100, 1)}
    for s, v in results.items()
])
