import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Analyse Thermique Multi-Zones & ΔT Chaufferie",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ Diagnostic Thermique : Zones (N, S, E, O, Aux 1-3) & ΔT Départ/Retour")
st.caption(
    "Analyse de confort sur 7 zones et diagnostic hydraulique fin du circuit de chauffage (Départ - Retour)."
)


# ==============================================================================
# 1. FONCTIONS DE NETTOYAGE ET CALCULS
# ==============================================================================


def parse_chaufferie(series):
    """Extrait T_Depart et T_Retour en gérant tous les formats (virgules, tirets, slashs)."""
    cleaned = series.astype(str).str.replace(",", ".").str.strip()
    cleaned = cleaned.str.replace(r"[–—/]", "-", regex=True)
    split_df = cleaned.str.split("-", expand=True)

    dep = pd.to_numeric(split_df[0].str.strip(), errors="coerce")
    if split_df.shape[1] >= 2:
        ret = pd.to_numeric(split_df[1].str.strip(), errors="coerce")
    else:
        ret = pd.Series(np.nan, index=series.index)

    return dep, ret


def analyser_horaires_chauffage(df, col_date, seuil_t_depart=30.0):
    """Détecte les plages quotidiennes et hebdomadaires d'activation du chauffage."""
    df_temp = df.copy()
    df_temp["Date"] = df_temp[col_date].dt.date

    mapping_jours = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    df_temp["Jour_FR"] = df_temp[col_date].dt.day_name().map(mapping_jours)

    resultats_quotidiens = []
    for (d, jour), group in df_temp.groupby(["Date", "Jour_FR"], sort=False):
        group = group.sort_values(col_date)
        points_actifs = group[group["T_Depart"] > seuil_t_depart]

        if not points_actifs.empty:
            h_debut = points_actifs.iloc[0][col_date].strftime("%H:%M")
            h_fin = points_actifs.iloc[-1][col_date].strftime("%H:%M")
            duree = round(
                (
                    points_actifs.iloc[-1][col_date]
                    - points_actifs.iloc[0][col_date]
                ).total_seconds()
                / 3600.0,
                1,
            )
            actif = True
        else:
            h_debut = "-"
            h_fin = "-"
            duree = 0.0
            actif = False

        resultats_quotidiens.append({
            "Date": d.strftime("%d/%m/%Y"),
            "Jour": jour,
            "Heure de Mise en Route": h_debut,
            "Heure d'Arrêt": h_fin,
            "Durée (h)": duree,
            "Actif": actif,
        })

    df_quot = pd.DataFrame(resultats_quotidiens)
    ordre_jours = [
        "Lundi",
        "Mardi",
        "Mercredi",
        "Jeudi",
        "Vendredi",
        "Samedi",
        "Dimanche",
    ]
    synthese_hebdo = []

    for jour in ordre_jours:
        sub = df_quot[(df_quot["Jour"] == jour) & (df_quot["Actif"])]
        if not sub.empty:
            h_dem = sub["Heure de Mise en Route"].min()
            h_arr = sub["Heure d'Arrêt"].max()
            dur_m = round(sub["Durée (h)"].mean(), 1)
            statut = "Actif"
        else:
            h_dem = "-"
            h_arr = "-"
            dur_m = 0.0
            statut = "Inactif"

        synthese_hebdo.append({
            "Jour": jour,
            "Mise en Route": h_dem,
            "Arrêt": h_arr,
            "Durée Moyenne": f"{dur_m} h",
            "Statut": statut,
        })

    return pd.DataFrame(synthese_hebdo), df_quot


# ==============================================================================
# 2. CHARGEMENT / GENERATION DES DONNEES (7 ZONES + CHAUFFERIE)
# ==============================================================================
st.sidebar.header("📥 Importation des données")
uploaded_file = st.sidebar.file_uploader(
    "Téléverser un fichier Excel ou CSV", type=["xlsx", "csv"]
)

if uploaded_file is not None:
    if uploaded_file.name.endswith(".xlsx"):
        df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    else:
        df_raw = pd.read_csv(uploaded_file)
else:
    st.sidebar.info(
        "💡 Génération de données de démonstration avec les 7 zones (N, S, E, O, Aux 1, Aux 2, Aux 3)."
    )
    dates = pd.date_range("2026-03-02 00:00", "2026-03-08 23:45", freq="15min")
    n = len(dates)
    hours = dates.hour + dates.minute / 60.0
    is_work = (dates.weekday < 5) & (hours >= 8) & (hours < 18)

    t_ext = (
        5 + 4 * np.sin((hours - 9) * np.pi / 12) + np.random.normal(0, 0.4, n)
    )

    # Simulation des 7 zones
    t_nord = np.where(
        is_work,
        19.5 + np.random.normal(0, 0.3, n),
        16.8 + np.random.normal(0, 0.4, n),
    )
    t_sud = t_nord + np.where(
        is_work & (hours >= 11) & (hours <= 16),
        2.5 + np.random.normal(0, 0.5, n),
        0.2,
    )
    t_est = t_nord + np.where(
        is_work & (hours >= 8) & (hours <= 12),
        1.4 + np.random.normal(0, 0.3, n),
        0.1,
    )
    t_ouest = t_nord + np.where(
        is_work & (hours >= 14) & (hours <= 17),
        1.3 + np.random.normal(0, 0.3, n),
        0.0,
    )

    # 3 Zones Auxiliaires
    t_aux1 = t_nord - 1.8 + np.random.normal(0, 0.3, n)  # Sous-chauffée
    t_aux2 = t_nord + 0.3 + np.random.normal(0, 0.2, n)  # Conforme
    t_aux3 = t_nord + 2.1 + np.random.normal(0, 0.4, n)  # Surchauffée

    # Circuit Chaufferie
    heating_on = (dates.weekday < 5) & (hours >= 5.5) & (hours < 18.5)
    t_dep = np.where(
        heating_on,
        56 - 1.3 * t_ext + np.random.normal(0, 0.7, n),
        20 + np.random.normal(0, 0.2, n),
    )
    # Delta T moyen ~ 10.5 °C en fonctionnement actif
    t_ret = np.where(
        heating_on, t_dep - (10.5 + np.random.normal(0, 0.9, n)), t_dep - 0.4
    )

    chaufferie_str = [
        f"{round(d, 1)} - {round(r, 1)}" for d, r in zip(t_dep, t_ret)
    ]

    df_raw = pd.DataFrame({
        "Horodatage": dates,
        "Extérieur": np.round(t_ext, 1),
        "Nord": np.round(t_nord, 1),
        "Sud": np.round(t_sud, 1),
        "Est": np.round(t_est, 1),
        "Ouest": np.round(t_ouest, 1),
        "Aux 1": np.round(t_aux1, 1),
        "Aux 2": np.round(t_aux2, 1),
        "Aux 3": np.round(t_aux3, 1),
        "Départ - Retour Chaufferie": chaufferie_str,
    })

df = df_raw.copy()

# Traitement colonne Date
col_date_candidates = [
    c
    for c in df.columns
    if any(k in c.lower() for k in ["date", "horo", "temps", "time"])
]
col_date = col_date_candidates[0] if col_date_candidates else df.columns[0]
df[col_date] = pd.to_datetime(
    df[col_date], errors="coerce", dayfirst=True, format="mixed"
)
df = df.dropna(subset=[col_date]).copy()

# Parsing Chaufferie et calcul du Delta T
cols_chaufferie = [
    c
    for c in df.columns
    if "chaufferie" in c.lower()
    or ("départ" in c.lower() and "retour" in c.lower())
]
col_chaufferie = cols_chaufferie[0] if cols_chaufferie else df.columns[-1]

df["T_Depart"], df["T_Retour"] = parse_chaufferie(df[col_chaufferie])
df["Delta_T"] = df["T_Depart"] - df["T_Retour"]

# Horaires de chauffe
df_synth_horaires, df_quot_horaires = analyser_horaires_chauffage(df, col_date)


# ==============================================================================
# 3. STATISTIQUES DES 7 ZONES ET DE LA CHAUFFERIE
# ==============================================================================
df["Jour_Semaine"] = df[col_date].dt.weekday
df["Heure_Dec"] = df[col_date].dt.hour + df[col_date].dt.minute / 60.0
is_occ = (
    (df["Jour_Semaine"] < 5)
    & (df["Heure_Dec"] >= 8.0)
    & (df["Heure_Dec"] < 18.0)
)
is_heating_active = df["T_Depart"] > 30.0

# 7 Zones cibles
cibles_zones = ["Nord", "Sud", "Est", "Ouest", "Aux 1", "Aux 2", "Aux 3"]
zones_trouvees = []

for zone in cibles_zones:
    matches = [c for c in df.columns if zone.lower() in c.lower()]
    if matches:
        zones_trouvees.append(matches[0])

# Fallback si noms légèrement différents dans le fichier client
if not zones_trouvees:
    zones_trouvees = [
        c
        for c in df.columns
        if c not in [col_date, col_chaufferie, "T_Depart", "T_Retour", "Delta_T"]
        and "ext" not in c.lower()
    ]

# Calculs Confort Ambiance
stats_zones = []
for z in zones_trouvees:
    vals_occ = df.loc[is_occ, z]
    if not vals_occ.empty:
        stats_zones.append({
            "Zone": z,
            "Temp. Min (°C)": round(vals_occ.min(), 1),
            "Temp. Moyenne (°C)": round(vals_occ.mean(), 1),
            "Temp. Max (°C)": round(vals_occ.max(), 1),
            "Confort [19-22°C] (%)": round(
                ((vals_occ >= 19.0) & (vals_occ <= 22.0)).mean() * 100, 1
            ),
            "Sous-chauffe <19°C (%)": round(
                (vals_occ < 19.0).mean() * 100, 1
            ),
            "Surchauffe >22°C (%)": round((vals_occ > 22.0).mean() * 100, 1),
        })

df_stats_zones = pd.DataFrame(stats_zones)

# Metrics Delta T (Période active)
df_active = df[is_heating_active]
dt_moy = df_active["Delta_T"].mean() if not df_active.empty else 0.0
dt_min = df_active["Delta_T"].min() if not df_active.empty else 0.0
dt_max = df_active["Delta_T"].max() if not df_active.empty else 0.0
dep_moy = df_active["T_Depart"].mean() if not df_active.empty else 0.0
ret_moy = df_active["T_Retour"].mean() if not df_active.empty else 0.0


# ==============================================================================
# 4. AFFICHAGE DE L'INTERFACE STREAMLIT
# ==============================================================================

# ------------------------------------------------------------------------------
# SECTION 1 : DIAGNOSTIC HYDRAULIQUE ΔT (DEPART - RETOUR)
# ------------------------------------------------------------------------------
st.subheader("🔥 1. Diagnostic Hydraulique : Écart Départ - Retour (ΔT)")
st.write(
    "L'analyse du $\Delta T = T_{Départ} - T_{Retour}$ permet d'évaluer la qualité d'irrigation hydraulique du réseau de chauffage."
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Régime Moyen (Départ / Retour)", f"{dep_moy:.1f}°C / {ret_moy:.1f}°C")
kpi2.metric("ΔT Moyen (En Chauffe)", f"{dt_moy:.1f} °C")
kpi3.metric("ΔT Plage (Min / Max)", f"{dt_min:.1f}°C / {dt_max:.1f}°C")

# Diagnostic automatique du régime hydraulique
if dt_moy < 6.0:
    statut_dt = "🔴 Sur-débit / Court-circuit hydraulique"
    explication_dt = (
        "Le ΔT est trop faible (< 6°C). L'eau revient trop chaude en chaufferie sans céder ses calories aux locaux. "
        "Risques : surconsommation de pompage, mauvaise condensation de la chaudière."
    )
elif 6.0 <= dt_moy <= 15.0:
    statut_dt = "🟢 Régime Hydraulique Équilibré"
    explication_dt = (
        "Le ΔT est dans la plage optimale (6°C à 15°C). La circulation d'eau est adaptée au transfert de chaleur des émetteurs."
    )
else:
    statut_dt = "🟠 Sous-débit / Perte de charge excessive"
    explication_dt = (
        "Le ΔT est très élevé (> 15°C). L'eau refroidit trop vite dans le réseau avant d'atteindre les extrémités. "
        "Risques : sous-chauffe des zones éloignées, vitesse de circulation insuffisante."
    )

kpi4.metric("Diagnostic Hydraulique", statut_dt.split()[1])

# Box d'interprétation du Delta T
with st.container():
    st.info(f"**Analyse du régime hydraulique :** {statut_dt}\n\n{explication_dt}")

# Graphiques dédiés ΔT
col_dt1, col_dt2 = st.columns([2, 1])

with col_dt1:
    fig_dt = go.Figure()
    fig_dt.add_trace(
        go.Scatter(
            x=df[col_date],
            y=df["T_Depart"],
            name="T° Départ (°C)",
            line=dict(color="#d9534f", width=1.5),
        )
    )
    fig_dt.add_trace(
        go.Scatter(
            x=df[col_date],
            y=df["T_Retour"],
            name="T° Retour (°C)",
            line=dict(color="#f0ad4e", width=1.5),
        )
    )
    fig_dt.add_trace(
        go.Scatter(
            x=df[col_date],
            y=df["Delta_T"],
            name="ΔT (Départ - Retour)",
            line=dict(color="#0275d8", width=2, dash="dot"),
        )
    )

    fig_dt.update_layout(
        title="Évolution temporelle des températures de départ, retour et du ΔT",
        height=380,
        xaxis_title="Date",
        yaxis_title="Température / Écart (°C)",
        hovermode="x unified",
    )
    st.plotly_chart(fig_dt, use_container_width=True)

with col_dt2:
    if not df_active.empty:
        fig_hist = px.histogram(
            df_active,
            x="Delta_T",
            nbins=20,
            title="Distribution du ΔT en période de chauffe",
            labels={"Delta_T": "ΔT (°C)"},
            color_discrete_sequence=["#0275d8"],
        )
        fig_hist.add_vline(
            x=6, line_dash="dash", line_color="orange", annotation_text="Min 6°C"
        )
        fig_hist.add_vline(
            x=15, line_dash="dash", line_color="red", annotation_text="Max 15°C"
        )
        fig_hist.update_layout(
            height=380, yaxis_title="Nombre de mesures (15 min)"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 2 : BILAN DU CONFORT SUR LES 7 ZONES (N, S, E, O, AUX 1, AUX 2, AUX 3)
# ------------------------------------------------------------------------------
st.subheader("🏢 2. Bilan de Confort par Zone (Période d'Occupation : 8h-18h, Lun-Ven)")

if not df_stats_zones.empty:
    st.dataframe(df_stats_zones, use_container_width=True, hide_index=True)

    col_bon, col_mauv = st.columns(2)

    with col_bon:
        st.markdown("### 👍 Points Forts par Zone")
        conforme_85 = df_stats_zones[
            df_stats_zones["Confort [19-22°C] (%)"] >= 85.0
        ]["Zone"].tolist()
        if conforme_85:
            st.write(
                f"✔️ **Zones très bien régulées (≥85% de confort)** : **{', '.join(conforme_85)}**"
            )
        else:
            st.write("⚠️ Aucune zone ne maintient 85% du temps la plage 19°C-22°C.")

    with col_mauv:
        st.markdown("### ⚠️ Dysfonctionnements Détectés")
        sous_chauffees = df_stats_zones[
            df_stats_zones["Sous-chauffe <19°C (%)"] > 15.0
        ]
        surchauffees = df_stats_zones[
            df_stats_zones["Surchauffe >22°C (%)"] > 15.0
        ]

        if not sous_chauffees.empty:
            for _, r in sous_chauffees.iterrows():
                st.write(
                    f"❌ **Sous-chauffe sur {r['Zone']}** : **{r['Sous-chauffe <19°C (%)']}%** du temps sous 19°C (Moy : {r['Temp. Moyenne (°C)']}°C)."
                )

        if not surchauffees.empty:
            for _, r in surchauffees.iterrows():
                surconso = round((r["Temp. Moyenne (°C)"] - 19.0) * 7.0, 1)
                st.write(
                    f"❌ **Surchauffe sur {r['Zone']}** : **{r['Surchauffe >22°C (%)']}%** du temps >22°C. Surconsommation approx. : **+{surconso}%**."
                )

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 3 : HORAIRES DE MISE EN ROUTE ET D'ARRET
# ------------------------------------------------------------------------------
st.subheader("🕒 3. Plages Horaires de Chauffage Détectées")
st.dataframe(df_synth_horaires, use_container_width=True, hide_index=True)

with st.expander("📅 Consulter le détail jour par jour"):
    st.dataframe(df_quot_horaires, use_container_width=True, hide_index=True)

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 4 : GRAPHIQUE COMPARAISON TEMPORELLE MULTI-ZONES
# ------------------------------------------------------------------------------
st.subheader("📈 4. Graphique Temporel Multi-Zones")

# Sélecteur de zones interactif
selected_zones = st.multiselect(
    "Sélectionner les zones à afficher sur le graphique :",
    options=zones_trouvees,
    default=zones_trouvees,
)

col_ext_candidates = [c for c in df.columns if "ext" in c.lower()]
col_ext = col_ext_candidates[0] if col_ext_candidates else None

fig_multi = go.Figure()

# Graphique des zones sélectionnées
for z in selected_zones:
    fig_multi.add_trace(
        go.Scatter(x=df[col_date], y=df[z], name=f"Zone {z}", mode="lines")
    )

# Ajout de la T° Extérieure si disponible
if col_ext:
    fig_multi.add_trace(
        go.Scatter(
            x=df[col_date],
            y=df[col_ext],
            name="T° Extérieure",
            line=dict(color="black", dash="dash", width=1.5),
        )
    )

# Tracés Départ et Retour Chaufferie
fig_multi.add_trace(
    go.Scatter(
        x=df[col_date],
        y=df["T_Depart"],
        name="Départ Chaufferie",
        line=dict(color="red", width=1.5),
        visible="legendonly",
    )
)
fig_multi.add_trace(
    go.Scatter(
        x=df[col_date],
        y=df["T_Retour"],
        name="Retour Chaufferie",
        line=dict(color="orange", width=1.5),
        visible="legendonly",
    )
)

fig_multi.update_layout(
    height=550,
    xaxis_title="Date / Heure",
    yaxis_title="Température (°C)",
    hovermode="x unified",
)

st.plotly_chart(fig_multi, use_container_width=True)