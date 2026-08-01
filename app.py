# -*- coding: utf-8 -*-
"""
Created on Sat Aug  1 10:10:54 2026

@author: m.petit
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Audit Énergétique & QAI", page_icon="📊", layout="wide"
)

# -----------------------------------------------------------------------------
# 1. FONCTIONS DE CHARGEMENT ET TRAITEMENT DES DONNÉES
# -----------------------------------------------------------------------------


def process_custom_dataframe(df):
    """Nettoie et formate les colonnes issues du format de fichier client."""
    # Identification de la colonne Date
    date_col = [c for c in df.columns if "date" in str(c).lower()]
    if date_col:
        df = df.rename(columns={date_col[0]: "Horodatage"})
    else:
        df = df.rename(columns={df.columns[0]: "Horodatage"})

    # Conversion en Datetime (Format FR: DD/MM/YYYY HH:MM:SS)
    df["Horodatage"] = pd.to_datetime(
        df["Horodatage"], dayfirst=True, errors="coerce"
    )
    # Suppression stricte des lignes dont la date est invalide (NaT)
    df = df.dropna(subset=["Horodatage"]).sort_values("Horodatage")

    # Traitement des valeurs texte / virgules françaises
    for col in list(df.columns):
        if col != "Horodatage":
            if df[col].dtype == object:
                # Traitement spécial pour la colonne Eau sous forme "Départ - Retour" (ex: "31,5 - 31,2")
                if str(col).lower().strip() == "eau":
                    split_eau = (
                        df[col].astype(str).str.split("-", expand=True)
                    )
                    if split_eau.shape[1] >= 2:
                        df["V3V_Depart"] = pd.to_numeric(
                            split_eau[0].str.replace(",", ".").str.strip(),
                            errors="coerce",
                        )
                        df["T_Retour"] = pd.to_numeric(
                            split_eau[1].str.replace(",", ".").str.strip(),
                            errors="coerce",
                        )
                else:
                    clean_series = (
                        df[col]
                        .astype(str)
                        .str.replace(",", ".")
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(clean_series, errors="coerce")
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # Renommage explicite des colonnes connues
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ["ext.", "ext", "t_ext", "temp_ext"]:
            col_mapping[col] = "T_ext"

    df = df.rename(columns=col_mapping)
    return df


@st.cache_data
def generate_synthetic_data():
    """Génère 15 jours de données fictives (Température, Humidité, CO2, COV)."""
    start_date = datetime(2026, 3, 11, 16, 45)
    dates = [
        start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)
    ]
    df = pd.DataFrame({"Date FR": dates})

    # Température extérieure
    df["Ext."] = (
        5
        + 4 * np.sin(np.pi * df.index / 48)
        + np.random.normal(0, 0.5, len(df))
    )
    df["Ext."] = df["Ext."].apply(lambda x: f"{x:.1f}".replace(".", ","))

    # Températures Salles / Orientations
    salles = ["Nord", "Est", "Sud", "Ouest", "Aux 1", "Aux 2", "Aux 3"]
    for i, s in enumerate(salles):
        base_t = 19 + (i * 0.4)
        t_vals = np.where(
            df["Date FR"].dt.hour.between(7, 19), base_t + 2, base_t
        ) + np.random.normal(0, 0.2, len(df))
        df[s] = [f"{v:.1f}".replace(".", ",") for v in t_vals]

    # Chauffe Eau Départ / Retour
    t_ext_num = df["Ext."].str.replace(",", ".").astype(float)
    t_dep = 45 - 1.2 * t_ext_num + np.random.normal(0, 0.3, len(df))
    t_ret = t_dep - 8 + np.random.normal(0, 0.2, len(df))
    df["Eau"] = [
        f"{d:.1f}".replace(".", ",") + " - " + f"{r:.1f}".replace(".", ",")
        for d, r in zip(t_dep, t_ret)
    ]

    # Humidité Relative (%)
    hr_vals = (
        45
        + 10 * np.sin(np.pi * df.index / 96)
        + np.random.normal(0, 2, len(df))
    )
    df["Humidité_HR (%)"] = [f"{v:.1f}".replace(".", ",") for v in hr_vals]

    # CO2 (ppm)
    co2_vals = np.where(
        df["Date FR"].dt.hour.between(8, 18),
        600 + 450 * np.sin(np.pi * (df["Date FR"].dt.hour - 8) / 10),
        420,
    ) + np.random.normal(0, 30, len(df))
    df["CO2 (ppm)"] = [f"{int(max(400, v))}" for v in co2_vals]

    # COV (ppb)
    cov_vals = np.where(
        df["Date FR"].dt.hour.between(8, 18),
        120 + 150 * np.sin(np.pi * (df["Date FR"].dt.hour - 8) / 10),
        70,
    ) + np.random.normal(0, 20, len(df))
    df["COV (ppb)"] = [f"{int(max(40, v))}" for v in cov_vals]

    return process_custom_dataframe(df)


def load_data(uploaded_file):
    """Charge et traite le fichier importé (CSV ou Excel)."""
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, sep=None, engine="python")
    else:
        df = pd.read_excel(uploaded_file)

    return process_custom_dataframe(df)


# -----------------------------------------------------------------------------
# 2. BARRE LATÉRALE (SIDEBAR) & FILTRES
# -----------------------------------------------------------------------------

st.sidebar.title("🛠️ Configuration Audit")

uploaded_file = st.sidebar.file_uploader(
    "Fichier de mesures (Excel/CSV)", type=["csv", "xlsx"]
)

if uploaded_file is not None:
    df = load_data(uploaded_file)
    st.sidebar.success("Fichier chargé avec succès !")
else:
    st.sidebar.info("Aucun fichier importé. Utilisation des données de démo.")
    df = generate_synthetic_data()

# Sécurité : vérification qu'il reste des dates valides après nettoyage
valid_dates = df["Horodatage"].dropna()
if valid_dates.empty:
    st.error(
        "❌ Aucune date valide n'a été trouvée dans le fichier. Vérifiez le format de la colonne Date."
    )
    st.stop()

# Filtre de dates sécurisé contre les erreurs NaT
min_date = valid_dates.min().date()
max_date = valid_dates.max().date()

date_range = st.sidebar.date_input(
    "Période d'analyse",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_filter, end_filter = date_range
    df = df[
        (df["Horodatage"].dt.date >= start_filter)
        & (df["Horodatage"].dt.date <= end_filter)
    ]

# Configuration des seuils dans la barre latérale
st.sidebar.subheader("🎯 Seuils d'alerte & Confort")
t_min_confort = st.sidebar.number_input(
    "Température Min Confort (°C)", value=19.0, step=0.5
)
t_max_confort = st.sidebar.number_input(
    "Température Max Confort (°C)", value=22.0, step=0.5
)
hr_min_confort = st.sidebar.number_input(
    "Humidité Min Confort (%)", value=40, step=5
)
hr_max_confort = st.sidebar.number_input(
    "Humidité Max Confort (%)", value=60, step=5
)
seuil_co2 = st.sidebar.number_input("Seuil CO2 max (ppm)", value=1000, step=50)
seuil_cov = st.sidebar.number_input("Seuil COV max (ppb)", value=200, step=20)


# -----------------------------------------------------------------------------
# 3. DÉTECTION ET CLASSIFICATION DES COLONNES
# -----------------------------------------------------------------------------

# Calcul du Delta T Chaufferie si disponible
if "V3V_Depart" in df.columns and "T_Retour" in df.columns:
    df["Delta_T_Chaufferie"] = df["V3V_Depart"] - df["T_Retour"]

# Détection automatique des colonnes par paramètre
cols_co2 = [c for c in df.columns if "co2" in str(c).lower()]
cols_hr = [
    c
    for c in df.columns
    if "hr" in str(c).lower()
    or "hum" in str(c).lower()
    or "hygro" in str(c).lower()
]
cols_cov = [
    c
    for c in df.columns
    if "cov" in str(c).lower() or "voc" in str(c).lower()
]

# Exclusion des colonnes techniques / QAI pour garder uniquement les colonnes de température de zone
cols_exclues_temp = (
    [
        "Horodatage",
        "T_ext",
        "Eau",
        "V3V_Depart",
        "T_Retour",
        "Delta_T_Chaufferie",
    ]
    + cols_co2
    + cols_hr
    + cols_cov
)
salles_cols_t = [c for c in df.columns if c not in cols_exclues_temp]


# -----------------------------------------------------------------------------
# 4. DASHBOARD PRINCIPAL (STRUCTURE EN 4 ONGLETS)
# -----------------------------------------------------------------------------

st.title("🏛️ Tableau de Bord - Audit Énergétique & QAI")
st.markdown("Analyse multi-paramètres des conditions intérieures et de la performance thermique")

# KPI Synthétiques en haut de page
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

avg_indoor_temp = df[salles_cols_t].mean().mean() if salles_cols_t else None
avg_hr = df[cols_hr].mean().mean() if cols_hr else None
max_co2 = df[cols_co2].max().max() if cols_co2 else None
max_cov = df[cols_cov].max().max() if cols_cov else None

kpi1.metric(
    "Température Intérieure Moy.",
    f"{avg_indoor_temp:.1f} °C" if avg_indoor_temp is not None else "N/A",
)
kpi2.metric(
    "Humidité Relative Moy.",
    f"{avg_hr:.1f} %" if avg_hr is not None else "N/A",
)
kpi3.metric(
    "Pic CO2 Max",
    f"{int(max_co2)} ppm" if max_co2 is not None else "N/A",
)
kpi4.metric(
    "Pic COV Max",
    f"{int(max_cov)} ppb" if max_cov is not None else "N/A",
)

st.divider()

# Création des 4 Onglets demandés
tab_temp, tab_hr, tab_co2, tab_cov = st.tabs(
    [
        "🌡️ 1. Température",
        "💧 2. Humidité",
        "🟢 3. CO2",
        "🧪 4. COV",
    ]
)


# =============================================================================
# ONGLET 1 : TEMPÉRATURE
# =============================================================================
with tab_temp:
    st.subheader("Analyse Thermique Globale & Chaufferie")

    # Superposition des signaux principaux
    fig_global = go.Figure()

    if "T_ext" in df.columns:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df["T_ext"],
                name="T° Extérieure",
                line=dict(color="blue", dash="dash"),
            )
        )

    if "V3V_Depart" in df.columns:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df["V3V_Depart"],
                name="Départ Chaufferie (V3V)",
                line=dict(color="red"),
            )
        )

    if "T_Retour" in df.columns:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df["T_Retour"],
                name="Retour Chaufferie",
                line=dict(color="darkred", dash="dot"),
            )
        )

    if salles_cols_t:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df[salles_cols_t].mean(axis=1),
                name="Moyenne des Zones Intérieures",
                line=dict(color="orange", width=2.5),
            )
        )

    fig_global.update_layout(
        xaxis_title="Date / Heure",
        yaxis_title="Température (°C)",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_global, use_container_width=True)

    col_loi, col_zones = st.columns(2)

    with col_loi:
        st.markdown("#### Loi d'Eau (T° Ext vs T° Départ)")
        if "T_ext" in df.columns and "V3V_Depart" in df.columns:
            fig_loi_eau = px.scatter(
                df,
                x="T_ext",
                y="V3V_Depart",
                color="Delta_T_Chaufferie"
                if "Delta_T_Chaufferie" in df.columns
                else None,
                labels={
                    "T_ext": "T° Extérieure (°C)",
                    "V3V_Depart": "Départ V3V (°C)",
                },
                title="Comportement Régulation Loi d'Eau",
            )
            st.plotly_chart(fig_loi_eau, use_container_width=True)
        else:
            st.info("Données de chaufferie non suffisantes pour la loi d'eau.")

    with col_zones:
        st.markdown("#### Détail par Zone / Salle")
        if salles_cols_t:
            fig_salles = px.line(
                df,
                x="Horodatage",
                y=salles_cols_t,
                title="Équilibrage thermique des zones",
            )
            fig_salles.add_hline(
                y=t_min_confort,
                line_dash="dash",
                line_color="blue",
                annotation_text="Min Confort",
            )
            fig_salles.add_hline(
                y=t_max_confort,
                line_dash="dash",
                line_color="red",
                annotation_text="Max Confort",
            )
            st.plotly_chart(fig_salles, use_container_width=True)
        else:
            st.info("Aucune colonne de température de zone détectée.")

    # Tableau de synthèse des dépassements de températures
    if salles_cols_t:
        st.markdown("#### Bilan du Confort Thermique")
        stats_list = []
        for col in salles_cols_t:
            t_moy = df[col].mean()
            h_sous_chauffe = (df[col] < t_min_confort).sum() * 0.25  # en heures (pas de 15 min)
            h_sur_chauffe = (df[col] > t_max_confort).sum() * 0.25
            stats_list.append(
                {
                    "Zone / Salle": col,
                    "T° Moyenne (°C)": round(t_moy, 2) if pd.notnull(t_moy) else "-",
                    f"Heures Sous-chauffe (<{t_min_confort}°C)": h_sous_chauffe,
                    f"Heures Sur-chauffe (>{t_max_confort}°C)": h_sur_chauffe,
                }
            )
        st.dataframe(pd.DataFrame(stats_list), use_container_width=True)


# =============================================================================
# ONGLET 2 : HUMIDITÉ
# =============================================================================
with tab_hr:
    st.subheader("Analyse de l'Humidité Relative (%)")

    if cols_hr:
        fig_hr = px.line(
            df,
            x="Horodatage",
            y=cols_hr,
            title="Évolution de l'Humidité Relative",
            labels={"value": "Humidité (%)", "variable": "Capteur"},
        )
        fig_hr.add_hline(
            y=hr_min_confort,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"Min Confort ({hr_min_confort}%)",
        )
        fig_hr.add_hline(
            y=hr_max_confort,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Max Confort ({hr_max_confort}%)",
        )
        st.plotly_chart(fig_hr, use_container_width=True)

        col_hr_left, col_hr_right = st.columns(2)

        with col_hr_left:
            st.markdown("#### Statistiques Humidité")
            hr_stats = []
            for col in cols_hr:
                hr_stats.append(
                    {
                        "Capteur": col,
                        "Moyenne (%)": round(df[col].mean(), 1),
                        "Min (%)": round(df[col].min(), 1),
                        "Max (%)": round(df[col].max(), 1),
                        "Temps Trop Sec (<40%)": f"{(df[col] < hr_min_confort).mean()*100:.1f} %",
                        "Temps Trop Humide (>60%)": f"{(df[col] > hr_max_confort).mean()*100:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(hr_stats), use_container_width=True)

        with col_hr_right:
            st.markdown("#### Distribution de l'Humidité")
            fig_hist_hr = px.histogram(
                df,
                x=cols_hr[0],
                nbins=30,
                title="Répartition des mesures d'humidité",
                color_discrete_sequence=["teal"],
            )
            st.plotly_chart(fig_hist_hr, use_container_width=True)
    else:
        st.warning(
            "⚠️ Aucune donnée d'humidité détectée dans le fichier. Importez une colonne contenant 'HR' ou 'Humidité'."
        )


# =============================================================================
# ONGLET 3 : CO2
# =============================================================================
with tab_co2:
    st.subheader("Analyse du Confinement et du CO2 (ppm)")

    if cols_co2:
        fig_co2 = px.line(
            df,
            x="Horodatage",
            y=cols_co2,
            title="Évolution des concentrations en CO2",
            labels={"value": "CO2 (ppm)", "variable": "Zone"},
        )
        fig_co2.add_hline(
            y=seuil_co2,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil d'Alerte ({seuil_co2} ppm)",
        )
        fig_co2.add_hline(
            y=800,
            line_dash="dot",
            line_color="orange",
            annotation_text="Seuil de Confort (800 ppm)",
        )
        st.plotly_chart(fig_co2, use_container_width=True)

        col_co2_left, col_co2_right = st.columns(2)

        with col_co2_left:
            st.markdown("#### Bilan par Zone / Capteur")
            co2_summary = []
            for col in cols_co2:
                heures_depassement = (df[col] > seuil_co2).sum() * 0.25
                co2_summary.append(
                    {
                        "Capteur": col,
                        "Moyenne (ppm)": int(df[col].mean()),
                        "Max (ppm)": int(df[col].max()),
                        f"Heures > {seuil_co2} ppm": heures_depassement,
                        "Taux d'Alerte (%)": f"{(df[col] > seuil_co2).mean()*100:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(co2_summary), use_container_width=True)

        with col_co2_right:
            st.markdown("#### Répartition des Niveaux de Confinement")
            co2_first = df[cols_co2[0]]
            bon = (co2_first < 800).sum()
            moyen = ((co2_first >= 800) & (co2_first <= seuil_co2)).sum()
            eleve = (co2_first > seuil_co2).sum()

            fig_pie_co2 = px.pie(
                names=["Confort (<800 ppm)", "Moyen (800-1000 ppm)", "Élevé (>1000 ppm)"],
                values=[bon, moyen, eleve],
                color_discrete_sequence=["green", "orange", "red"],
                title=f"Répartition Qualité Air ({cols_co2[0]})",
            )
            st.plotly_chart(fig_pie_co2, use_container_width=True)
    else:
        st.warning(
            "⚠️ Aucune donnée de CO2 détectée dans le fichier. Importez une colonne contenant 'CO2'."
        )


# =============================================================================
# ONGLET 4 : COV
# =============================================================================
with tab_cov:
    st.subheader("Analyse des Composés Organiques Volatils (COV)")

    if cols_cov:
        fig_cov = px.line(
            df,
            x="Horodatage",
            y=cols_cov,
            title="Évolution de la Pollution Chimique (COV)",
            labels={"value": "COV (ppb)", "variable": "Zone"},
        )
        fig_cov.add_hline(
            y=seuil_cov,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil d'Alerte ({seuil_cov} ppb)",
        )
        st.plotly_chart(fig_cov, use_container_width=True)

        col_cov_left, col_cov_right = st.columns(2)

        with col_cov_left:
            st.markdown("#### Bilan des Niveaux de COV")
            cov_summary = []
            for col in cols_cov:
                cov_summary.append(
                    {
                        "Capteur": col,
                        "Moyenne (ppb)": int(df[col].mean()),
                        "Max (ppb)": int(df[col].max()),
                        f"Heures > {seuil_cov} ppb": (df[col] > seuil_cov).sum() * 0.25,
                        "Qualité Globale": "Bonne" if df[col].mean() < seuil_cov else "Attention",
                    }
                )
            st.dataframe(pd.DataFrame(cov_summary), use_container_width=True)

        with col_cov_right:
            st.markdown("#### Profil Moyen Journalier des COV")
            df_cov_hourly = df.groupby(df["Horodatage"].dt.hour)[cols_cov[0]].mean().reset_index()
            fig_hourly_cov = px.bar(
                df_cov_hourly,
                x="Horodatage",
                y=cols_cov[0],
                labels={"Horodatage": "Heure de la journée", cols_cov[0]: "COV Moyen (ppb)"},
                title="Moyenne par heure de la journée",
            )
            st.plotly_chart(fig_hourly_cov, use_container_width=True)
    else:
        st.warning(
            "⚠️ Aucune donnée COV détectée dans le fichier. Importez une colonne contenant 'COV' ou 'VOC'."
        )