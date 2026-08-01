import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Analyse Températures & Horaires Chauffage",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ Étape 1 : Diagnostic Thermique & Horaires de Chauffage")
st.caption(
    "Analyse des zones (Nord, Sud, Est, Ouest, Aux), du circuit chaufferie et détection des créneaux de chauffe."
)


# ==============================================================================
# 1. FONCTIONS DE TRAITEMENT ET DE DETECTION
# ==============================================================================


def parse_chaufferie(series):
    """Extrait T_Depart et T_Retour en gérant tous les formats de tirets et virgules."""
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
    """Détecte les heures de démarrage/arrêt du chauffage et génère la synthèse hebdomadaire."""
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
            "Durée de Chauffe (h)": duree,
            "Actif": actif,
        })

    df_quot = pd.DataFrame(resultats_quotidiens)

    # Synthèse par jour de la semaine (horaires les plus fréquents / limites)
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
            dur_m = round(sub["Durée de Chauffe (h)"].mean(), 1)
            statut = "Chauffe active"
        else:
            h_dem = "-"
            h_arr = "-"
            dur_m = 0.0
            statut = "Inactif / Réduit"

        synthese_hebdo.append({
            "Jour de la semaine": jour,
            "Heure de Mise en Route": h_dem,
            "Heure d'Arrêt": h_arr,
            "Durée Moyenne (h)": f"{dur_m} h",
            "Statut Habituel": statut,
        })

    df_synth = pd.DataFrame(synthese_hebdo)

    # Stockage en session pour réutilisation future
    st.session_state["horaires_chauffage"] = df_synth
    st.session_state["horaires_quotidiens"] = df_quot

    return df_synth, df_quot


# ==============================================================================
# 2. CHARGEMENT OU GENERATION DES DONNEES
# ==============================================================================
uploaded_file = st.sidebar.file_uploader(
    "Fichier Excel (.xlsx) ou CSV", type=["xlsx", "csv"]
)

if uploaded_file is not None:
    if uploaded_file.name.endswith(".xlsx"):
        df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    else:
        df_raw = pd.read_csv(uploaded_file)
else:
    st.info("💡 Aucun fichier importé. Données de démonstration chargées.")
    dates = pd.date_range("2026-03-02 00:00", "2026-03-08 23:45", freq="15min")
    n = len(dates)
    hours = dates.hour + dates.minute / 60.0
    is_work = (dates.weekday < 5) & (hours >= 8) & (hours < 18)

    t_ext = (
        5 + 4 * np.sin((hours - 9) * np.pi / 12) + np.random.normal(0, 0.4, n)
    )
    t_nord = np.where(
        is_work,
        19.8 + np.random.normal(0, 0.3, n),
        17.0 + np.random.normal(0, 0.4, n),
    )
    t_sud = t_nord + np.where(
        is_work & (hours >= 11) & (hours <= 16),
        2.2 + np.random.normal(0, 0.4, n),
        0,
    )
    t_est = t_nord + np.where(is_work & (hours >= 8) & (hours <= 12), 1.2, 0)
    t_ouest = t_nord + np.where(is_work & (hours >= 14) & (hours <= 17), 1.1, 0)
    t_aux1 = t_nord - 2.1

    heating_on = (dates.weekday < 5) & (hours >= 5.5) & (hours < 18.5)
    t_dep = np.where(
        heating_on,
        58 - 1.2 * t_ext + np.random.normal(0, 0.8, n),
        20 + np.random.normal(0, 0.3, n),
    )
    t_ret = np.where(
        heating_on, t_dep - (9.5 + np.random.normal(0, 0.8, n)), t_dep - 0.5
    )

    chaufferie_str = [
        f"{round(d, 1)} – {round(r, 1)}" for d, r in zip(t_dep, t_ret)
    ]

    df_raw = pd.DataFrame({
        "Horodatage": dates,
        "Extérieur": np.round(t_ext, 1),
        "Nord": np.round(t_nord, 1),
        "Sud": np.round(t_sud, 1),
        "Est": np.round(t_est, 1),
        "Ouest": np.round(t_ouest, 1),
        "Aux1": np.round(t_aux1, 1),
        "Départ - Retour Chaufferie": chaufferie_str,
    })

df = df_raw.copy()

# Identification Horodatage
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

# Identification et Parsing Chaufferie
cols_chaufferie = [
    c
    for c in df.columns
    if "chaufferie" in c.lower()
    or ("départ" in c.lower() and "retour" in c.lower())
]
if not cols_chaufferie:
    cols_chaufferie = [
        c for c in df.columns if "départ" in c.lower() or "retour" in c.lower()
    ]
col_chaufferie = cols_chaufferie[0] if cols_chaufferie else df.columns[-1]

df["T_Depart"], df["T_Retour"] = parse_chaufferie(df[col_chaufferie])
df["Delta_T_Chaufferie"] = df["T_Depart"] - df["T_Retour"]

# Horaires de chauffage
df_synth_horaires, df_quot_horaires = analyser_horaires_chauffage(df, col_date)

# ==============================================================================
# 3. CALCULS DIAGNOSTICS & STATISTIQUES
# ==============================================================================
df["Jour_Semaine"] = df[col_date].dt.weekday
df["Heure_Dec"] = df[col_date].dt.hour + df[col_date].dt.minute / 60.0
is_occ = (
    (df["Jour_Semaine"] < 5)
    & (df["Heure_Dec"] >= 8.0)
    & (df["Heure_Dec"] < 18.0)
)

# Chaufferie
heating_active = df["T_Depart"] > 30.0
pct_temps_chauffe = heating_active.mean() * 100
df_heat = df[heating_active]

t_dep_moy = df_heat["T_Depart"].mean() if not df_heat.empty else 0.0
t_ret_moy = df_heat["T_Retour"].mean() if not df_heat.empty else 0.0
delta_t_moy = (
    df_heat["Delta_T_Chaufferie"].mean() if not df_heat.empty else 0.0
)

col_ext_candidates = [c for c in df.columns if "ext" in c.lower()]
col_ext = col_ext_candidates[0] if col_ext_candidates else None
corr_loi_eau = (
    df_heat["T_Depart"].corr(df_heat[col_ext])
    if (not df_heat.empty and col_ext)
    else 0.0
)

# Zones d'ambiance
zones_list = ["Nord", "Sud", "Est", "Ouest", "Aux1", "Aux2", "Aux3"]
zones_presentes = [
    z for z in df.columns if any(z.lower() in c.lower() for c in zones_list)
]

stats_zones = []
for z in zones_presentes:
    vals_occ = df.loc[is_occ, z]
    if not vals_occ.empty:
        t_moy = vals_occ.mean()
        pct_conf = ((vals_occ >= 19.0) & (vals_occ <= 22.0)).mean() * 100
        pct_sous = (vals_occ < 19.0).mean() * 100
        pct_sur = (vals_occ > 22.0).mean() * 100

        stats_zones.append({
            "Zone": z,
            "Temp. Moyenne (°C)": round(t_moy, 1),
            "Confort 19-22°C (%)": round(pct_conf, 1),
            "Sous-chauffe <19°C (%)": round(pct_sous, 1),
            "Surchauffe >22°C (%)": round(pct_sur, 1),
        })

df_stats_zones = pd.DataFrame(stats_zones)

# Asymétrie Nord/Sud
is_aprem = is_occ & (df["Heure_Dec"] >= 12.0) & (df["Heure_Dec"] < 16.0)
col_sud = [c for c in df.columns if "sud" in c.lower()]
col_nord = [c for c in df.columns if "nord" in c.lower()]
ecart_sud_nord_aprem = (
    (df.loc[is_aprem, col_sud[0]] - df.loc[is_aprem, col_nord[0]]).mean()
    if (col_sud and col_nord)
    else 0.0
)


# ==============================================================================
# 4. AFFICHAGE DE L'INTERFACE STREAMLIT
# ==============================================================================

# SECTION 1 : HORAIRES DE CHAUFFAGE DETECTES
st.subheader("🕒 1. Horaires de Démarrage et d'Arrêt du Chauffage")
st.write(
    "Détection automatique basée sur les valeurs de température de départ chaufferie (> 30°C)."
)

st.dataframe(df_synth_horaires, use_container_width=True, hide_index=True)

with st.expander("📅 Voir le détail des horaires jour par jour"):
    st.dataframe(df_quot_horaires, use_container_width=True, hide_index=True)

st.markdown("---")

# SECTION 2 : CHAUFFERIE
st.subheader("🔥 2. Bilan du Circuit Chaufferie")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temps d'Activité Chaufferie", f"{pct_temps_chauffe:.1f}%")
c2.metric(
    "Régime Moy. (Départ / Retour)", f"{t_dep_moy:.1f}°C / {t_ret_moy:.1f}°C"
)
c3.metric(
    "ΔT Moyen Chaufferie",
    f"{delta_t_moy:.1f}°C",
    delta="Nominal" if 8 <= delta_t_moy <= 15 else "Attention",
)
c4.metric("Corrélation Loi d'Eau", f"{corr_loi_eau:.2f}")

b1, b2 = st.columns(2)
with b1:
    st.markdown("### 👍 Points forts (Chaufferie)")
    if corr_loi_eau < -0.75:
        st.write(
            f"✔️ **Loi d'eau réactive** : Corrélation de **{corr_loi_eau:.2f}** avec l'extérieur."
        )
    if 8 <= delta_t_moy <= 15:
        st.write(
            f"✔️ **Écart ΔT nominal** : Réseau équilibré avec un ΔT moyen de **{delta_t_moy:.1f}°C**."
        )

with b2:
    st.markdown("### ⚠️ Points à surveiller (Chaufferie)")
    if delta_t_moy < 6.0:
        st.write(
            f"❌ **ΔT Faible ({delta_t_moy:.1f}°C)** : Risque de sur-débit ou court-circuit hydraulique."
        )
    elif delta_t_moy > 16.0:
        st.write(
            f"❌ **ΔT Élevé ({delta_t_moy:.1f}°C)** : Risque de sous-débit sur le réseau."
        )
    if corr_loi_eau > -0.60:
        st.write(
            f"❌ **Loi d'eau peu réactive** (r = **{corr_loi_eau:.2f}** avec la T° extérieure)."
        )

st.markdown("---")

# SECTION 3 : CONFORT PAR ZONE
st.subheader("🏢 3. Bilan du Confort par Zone (Période d'Occupation)")
if not df_stats_zones.empty:
    st.dataframe(df_stats_zones, use_container_width=True, hide_index=True)

    col_bien, col_moins = st.columns(2)
    zones_bonnes = df_stats_zones[
        df_stats_zones["Confort 19-22°C (%)"] >= 85.0
    ]["Zone"].tolist()
    zones_sous = df_stats_zones[df_stats_zones["Sous-chauffe <19°C (%)"] > 20.0]
    zones_sur = df_stats_zones[df_stats_zones["Surchauffe >22°C (%)"] > 20.0]

    with col_bien:
        st.markdown("### 👍 Points forts (Ambiances)")
        if zones_bonnes:
            st.write(
                f"✔️ **Zones conformes (>85% confort)** : **{', '.join(zones_bonnes)}**."
            )
        else:
            st.write("Aucune zone n'atteint 85% de confort continu.")

    with col_moins:
        st.markdown("### ⚠️ Points à surveiller (Ambiances)")
        if not zones_sous.empty:
            for _, r in zones_sous.iterrows():
                st.write(
                    f"❌ **Sous-chauffe ({r['Zone']})** : **{r['Sous-chauffe <19°C (%)']}%** du temps sous 19°C."
                )
        if not zones_sur.empty:
            for _, r in zones_sur.iterrows():
                surco = round((r["Temp. Moyenne (°C)"] - 19) * 7, 1)
                st.write(
                    f"❌ **Surchauffe ({r['Zone']})** : **{r['Surchauffe >22°C (%)']}%** du temps > 22°C. Surconsommation estimée : **+{surco}%**."
                )
        if ecart_sud_nord_aprem > 1.5:
            st.write(
                f"❌ **Asymétrie Sud/Nord** : Le Sud est plus chaud de **+{ecart_sud_nord_aprem:.1f}°C** l'après-midi."
            )

st.markdown("---")

# SECTION 4 : GRAPHIQUE TEMPOREL
st.subheader("📈 4. Graphique Temporel Interactif")
fig = go.Figure()

for z in zones_presentes:
    fig.add_trace(
        go.Scatter(x=df[col_date], y=df[z], name=f"Zone {z}", mode="lines")
    )

if col_ext:
    fig.add_trace(
        go.Scatter(
            x=df[col_date],
            y=df[col_ext],
            name="Extérieur",
            line=dict(color="black", dash="dash"),
        )
    )

fig.add_trace(
    go.Scatter(
        x=df[col_date],
        y=df["T_Depart"],
        name="Départ Chaufferie",
        line=dict(color="red", width=2),
    )
)
fig.add_trace(
    go.Scatter(
        x=df[col_date],
        y=df["T_Retour"],
        name="Retour Chaufferie",
        line=dict(color="orange", width=2),
    )
)

fig.update_layout(
    height=550,
    xaxis_title="Date / Heure",
    yaxis_title="Température (°C)",
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)