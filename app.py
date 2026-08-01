<<<<<<< HEAD
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

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Audit Énergétique & QAI", page_icon="📊", layout="wide"
)

# -----------------------------------------------------------------------------
# 1. FONCTION DE CONVERSION ET CHARGEMENT DES DONNÉES
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
    df = df.dropna(subset=["Horodatage"]).sort_values("Horodatage")

    # Traitement des valeurs texte / virgules françaises
    for col in df.columns:
        if col != "Horodatage":
            # Si la colonne contient des chaînes avec des virgules (ex: "21,3")
            if df[col].dtype == object:
                # Traitement spécial pour la colonne Eau si elle contient "Départ - Retour" (ex: "31,5 - 31,2")
                if col.lower() == "eau":
                    split_eau = (
                        df[col].astype(str).str.split("-", expand=True)
                    )
                    if split_eau.shape[1] >= 2:
                        df["V3V_Depart"] = (
                            split_eau[0]
                            .str.replace(",", ".")
                            .str.strip()
                            .astype(float)
                        )
                        df["T_Retour"] = (
                            split_eau[1]
                            .str.replace(",", ".")
                            .str.strip()
                            .astype(float)
                        )
                else:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(",", ".")
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # Renommage explicite des colonnes connues pour faciliter la suite
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in ["ext.", "ext", "t_ext"]:
            col_mapping[col] = "T_ext"

    df = df.rename(columns=col_mapping)
    return df


@st.cache_data
def generate_synthetic_data():
    """Génère 15 jours de données fictives selon le format du tableau client."""
    start_date = datetime(2026, 3, 11, 16, 45)
    dates = [
        start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)
    ]
    df = pd.DataFrame({"Date FR": dates})

    df["Ext."] = (
        5
        + 4 * np.sin(np.pi * df.index / 48)
        + np.random.normal(0, 0.5, len(df))
    )
    df["Ext."] = df["Ext."].apply(lambda x: f"{x:.1f}".replace(".", ","))

    # Salles / Orientations
    salles = ["Nord", "Est", "Sud", "Ouest", "Aux 1", "Aux 2", "Aux 3"]
    for i, s in enumerate(salles):
        base_t = 19 + (i * 0.4)
        t_vals = np.where(
            df["Date FR"].dt.hour.between(7, 19), base_t + 2, base_t
        ) + np.random.normal(0, 0.2, len(df))
        df[s] = [f"{v:.1f}".replace(".", ",") for v in t_vals]

    # Colonne Eau sous forme "Départ - Retour"
    t_dep = (
        45
        - 1.2
        * df["Ext."].str.replace(",", ".").astype(float)
        + np.random.normal(0, 0.3, len(df))
    )
    t_ret = t_dep - 8 + np.random.normal(0, 0.2, len(df))
    df["Eau"] = [
        f"{d:.1f}".replace(".", ",") + " - " + f"{r:.1f}".replace(".", ",")
        for d, r in zip(t_dep, t_ret)
    ]

    return process_custom_dataframe(df)


def load_data(uploaded_file):
    """Charge et traite le fichier importé."""
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

# Filtre de dates
min_date = df["Horodatage"].min().date()
max_date = df["Horodatage"].max().date()

date_range = st.sidebar.date_input(
    "Période d'analyse",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date,
)

if len(date_range) == 2:
    start_filter, end_filter = date_range
    df = df[
        (df["Horodatage"].dt.date >= start_filter)
        & (df["Horodatage"].dt.date <= end_filter)
    ]

# Identification dynamique des zones / salles
colonnes_exclues = [
    "Horodatage",
    "T_ext",
    "Eau",
    "V3V_Depart",
    "T_Retour",
    "Delta_T_Chaufferie",
]
salles_cols_t = [c for c in df.columns if c not in colonnes_exclues]

# Seuils paramétrables
st.sidebar.subheader("🎯 Seuils d'alerte")
seuil_co2 = st.sidebar.number_input("Seuil CO2 max (ppm)", value=1000, step=50)
t_min_confort = st.sidebar.number_input(
    "Température Min Confort (°C)", value=19.0, step=0.5
)
t_max_confort = st.sidebar.number_input(
    "Température Max Confort (°C)", value=22.0, step=0.5
)

# -----------------------------------------------------------------------------
# 3. CALCUL DES KPIS
# -----------------------------------------------------------------------------

if "V3V_Depart" in df.columns and "T_Retour" in df.columns:
    df["Delta_T_Chaufferie"] = df["V3V_Depart"] - df["T_Retour"]
else:
    df["Delta_T_Chaufferie"] = 0

avg_indoor_temp = df[salles_cols_t].mean().mean() if salles_cols_t else 0
delta_t_moyen = (
    df["Delta_T_Chaufferie"].mean() if "Delta_T_Chaufferie" in df.columns else 0
)

# -----------------------------------------------------------------------------
# 4. DASHBOARD - DASHBOARD PRINCIPAL (ONGLETS)
# -----------------------------------------------------------------------------

st.title("🏛️ Tableau de Bord - Audit Énergétique & QAI")
st.markdown("Analyse des campagnes de mesure par zones")

# Métriques rapides (Cards)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Température Intérieure Moy.", f"{avg_indoor_temp:.1f} °C")
col2.metric(
    "Delta T Chaufferie Moyen",
    f"{delta_t_moyen:.1f} °C" if delta_t_moyen else "N/A",
)
col3.metric(
    "Température Extérieure Moy.",
    f"{df['T_ext'].mean():.1f} °C" if "T_ext" in df.columns else "N/A",
)
col4.metric("Nombre de Zones Analysées", f"{len(salles_cols_t)}")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📈 Vue Globale",
        "🔥 Chaufferie & Loi d'Eau",
        "🌡️ Confort (Zones/Salles)",
        "🍃 Qualité d'Air (QAI)",
    ]
)

# --- TAB 1 : VUE GLOBALE ---
with tab1:
    st.subheader("Superposition des signaux clés")
    fig_global = go.Figure()

    if "T_ext" in df.columns:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df["T_ext"],
                name="T° Extérieure",
                line=dict(color="gray", dash="dash"),
            )
        )

    if "V3V_Depart" in df.columns:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df["V3V_Depart"],
                name="Départ V3V",
                line=dict(color="red"),
            )
        )

    if salles_cols_t:
        fig_global.add_trace(
            go.Scatter(
                x=df["Horodatage"],
                y=df[salles_cols_t].mean(axis=1),
                name="Moyenne des Zones",
                line=dict(color="orange"),
            )
        )

    fig_global.update_layout(
        xaxis_title="Date/Heure", yaxis_title="Température (°C)", height=450
    )
    st.plotly_chart(fig_global, use_container_width=True)

# --- TAB 2 : CHAUFFERIE & LOI D'EAU ---
with tab2:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Analyse de la Loi d'Eau Réelle")
        if "T_ext" in df.columns and "V3V_Depart" in df.columns:
            fig_loi_eau = px.scatter(
                df,
                x="T_ext",
                y="V3V_Depart",
                color="Delta_T_Chaufferie"
                if "Delta_T_Chaufferie" in df.columns
                else None,
                labels={
                    "T_ext": "Température Extérieure (°C)",
                    "V3V_Depart": "Départ V3V (°C)",
                },
                title="Nuage de points : T° Ext vs T° Départ V3V",
            )
            st.plotly_chart(fig_loi_eau, use_container_width=True)
        else:
            st.info(
                "Données de chaufferie non disponibles (Colonnes 'Ext.' ou 'Eau' absentes)."
            )

    with col_right:
        st.subheader("Régime Hydraulique (Delta T = Départ - Retour)")
        if "Delta_T_Chaufferie" in df.columns and df["Delta_T_Chaufferie"].sum() > 0:
            fig_delta_t = px.line(
                df,
                x="Horodatage",
                y="Delta_T_Chaufferie",
                title="Évolution du Delta T Chaufferie",
            )
            st.plotly_chart(fig_delta_t, use_container_width=True)
        else:
            st.info("Information Delta T non disponible.")

# --- TAB 3 : CONFORT ET ÉQUILIBRAGE (ZONES / SALLES) ---
with tab3:
    st.subheader("Comparaison des Températures des Zones / Salles")

    if salles_cols_t:
        fig_salles = px.line(
            df,
            x="Horodatage",
            y=salles_cols_t,
            title="Équilibrage thermique par zone",
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

        # Statistiques par salle / zone
        st.subheader("Statistiques de Confort Thermique par Zone")
        stats_list = []
        for col in salles_cols_t:
            t_moy = df[col].mean()
            h_sous_chauffe = (df[col] < t_min_confort).sum() * 0.25  # en heures
            h_sur_chauffe = (df[col] > t_max_confort).sum() * 0.25
            stats_list.append(
                {
                    "Zone / Salle": col,
                    "T° Moyenne (°C)": round(t_moy, 2)
                    if pd.notnull(t_moy)
                    else "-",
                    f"Heures Sous-chauffe (<{t_min_confort}°C)": h_sous_chauffe,
                    f"Heures Sur-chauffe (>{t_max_confort}°C)": h_sur_chauffe,
                }
            )
        st.dataframe(pd.DataFrame(stats_list), use_container_width=True)
    else:
        st.info("Aucune donnée de température de zone disponible.")

# --- TAB 4 : QUALITÉ DE L'AIR (QAI) ---
with tab4:
    st.subheader("Qualité de l'Air Intérieur (CO2, HR, COV)")

    # Détection de colonnes QAI si présentes dans les données
    cols_co2 = [c for c in df.columns if "co2" in c.lower()]
    cols_hr = [
        c
        for c in df.columns
        if "hr" in c.lower() or "hum" in c.lower() or "%" in c
    ]
    cols_cov = [
        c
        for c in df.columns
        if "cov" in c.lower() or "voc" in c.lower()
    ]

    if cols_co2:
        st.subheader("Concentration en CO2 (ppm)")
        fig_co2 = px.line(
            df, x="Horodatage", y=cols_co2, title="Évolution du CO2"
        )
        fig_co2.add_hline(
            y=seuil_co2,
            line_dash="dash",
            line_color="orange",
            annotation_text="Seuil Alerte",
        )
        st.plotly_chart(fig_co2, use_container_width=True)
    else:
        st.info(
            "Aucune colonne CO2 détectée dans les données actuelles. Importez un fichier avec des données de CO2 pour afficher cette rubrique."
        )

    col_cov, col_hr = st.columns(2)
    with col_cov:
        st.subheader("Composés Organiques Volatils (COV)")
        if cols_cov:
            fig_cov = px.line(df, x="Horodatage", y=cols_cov)
            st.plotly_chart(fig_cov, use_container_width=True)
        else:
            st.info("Données COV non détectées.")

    with col_hr:
        st.subheader("Humidité Relative (%)")
        if cols_hr:
            fig_hr = px.line(df, x="Horodatage", y=cols_hr)
            st.plotly_chart(fig_hr, use_container_width=True)
        else:
            st.info("Données d'Humidité non détectées.")
=======
# -*- coding: utf-8 -*-
"""
Created on Sat Aug  1 10:10:54 2026

@author: m.petit
"""


import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Audit Énergétique & QAI",
    page_icon="📊",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 1. FONCTIONS DE CHARGEMENT ET SOURCAGE DES DONNÉES
# -----------------------------------------------------------------------------

@st.cache_data
def generate_synthetic_data():
    """Génère 15 jours de données fictives (15 min) pour tester le dashboard."""
    start_date = datetime(2026, 1, 15, 0, 0)
    dates = [start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)]
    df = pd.DataFrame({'Horodotage': dates})
    
    # Température extérieure (cycle quotidien + variation)
    df['T_ext'] = 5 + 4 * np.sin(np.pi * df.index / 48) + np.random.normal(0, 0.5, len(df))
    
    # Réseau chauffage
    df['V3V_Depart'] = np.where(df['Horodotage'].dt.hour.between(6, 21), 45 - 1.2 * df['T_ext'], 30)
    df['T_Retour'] = df['V3V_Depart'] - np.where(df['Horodotage'].dt.hour.between(6, 21), 8, 3) + np.random.normal(0, 0.3, len(df))
    
    # Données pour les 7 salles
    for i in range(1, 8):
        # Température intérieure
        base_t = 19 + (i * 0.4)
        df[f'Salle_{i}_T'] = np.where(df['Horodotage'].dt.hour.between(7, 19), base_t + 2, base_t) + np.random.normal(0, 0.2, len(df))
        
        # CO2 (présence humaine la journée en semaine)
        is_weekend = df['Horodotage'].dt.dayofweek >= 5
        is_occupied = (df['Horodotage'].dt.hour.between(8, 18)) & (~is_weekend)
        df[f'Salle_{i}_CO2'] = np.where(is_occupied, 400 + np.random.randint(400, 900, len(df)), 420)
        
        # COV et Humidité
        df[f'Salle_{i}_COV'] = np.random.uniform(100, 350, len(df))
        df[f'Salle_{i}_HR'] = np.random.uniform(40, 55, len(df))
        
    return df

def load_data(uploaded_file):
    """Charge le fichier Excel ou CSV déposé par l'utilisateur."""
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Conversion automatique de la 1ère colonne en Datetime
    first_col = df.columns[0]
    df[first_col] = pd.to_datetime(df[first_col])
    df = df.rename(columns={first_col: 'Horodotage'})
    return df

# -----------------------------------------------------------------------------
# 2. BARRE LATÉRALE (SIDEBAR) & FILTRES
# -----------------------------------------------------------------------------

st.sidebar.title("🛠️ Configuration Audit")

uploaded_file = st.sidebar.file_uploader("Fichier de mesures (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    st.sidebar.success("Fichier chargé avec succès !")
else:
    st.sidebar.info("Aucun fichier importé. Utilisation des données de démo.")
    df = generate_synthetic_data()

# Filtre de dates
min_date = df['Horodotage'].min().date()
max_date = df['Horodotage'].max().date()

date_range = st.sidebar.date_input("Période d'analyse", [min_date, max_date], min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    start_filter, end_filter = date_range
    df = df[(df['Horodotage'].dt.date >= start_filter) & (df['Horodotage'].dt.date <= end_filter)]

# Seuils paramétrables
st.sidebar.subheader("🎯 Seuils d'alerte")
seuil_co2 = st.sidebar.number_input("Seuil CO2 max (ppm)", value=1000, step=50)
t_min_confort = st.sidebar.number_input("Température Min Confort (°C)", value=19.0, step=0.5)
t_max_confort = st.sidebar.number_input("Température Max Confort (°C)", value=22.0, step=0.5)

# -----------------------------------------------------------------------------
# 3. CALCUL DES KPIS
# -----------------------------------------------------------------------------

df['Delta_T_Chaufferie'] = df['V3V_Depart'] - df['T_Retour']

salles_cols_t = [c for c in df.columns if c.endswith('_T')]
salles_cols_co2 = [c for c in df.columns if c.endswith('_CO2')]

avg_indoor_temp = df[salles_cols_t].mean().mean() if salles_cols_t else 0
co2_depassement_pct = ((df[salles_cols_co2] > seuil_co2).sum().sum() / df[salles_cols_co2].size) * 100 if salles_cols_co2 else 0
delta_t_moyen = df['Delta_T_Chaufferie'].mean()

# -----------------------------------------------------------------------------
# 4. DASHBOARD - DASHBOARD PRINCIPAL (ONGLETS)
# -----------------------------------------------------------------------------

st.title("🏛️ Tableau de Bord - Audit Énergétique & QAI")
st.markdown("Analyse des campagnes de mesure 15 jours (Pas 15 min)")

# Métriques rapides (Cards)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Température Intérieure Moy.", f"{avg_indoor_temp:.1f} °C")
col2.metric("Dépassement CO2 (> threshold)", f"{co2_depassement_pct:.1f} %")
col3.metric("Delta T Chaufferie Moyen", f"{delta_t_moyen:.1f} °C")
col4.metric("Température Extérieure Moy.", f"{df['T_ext'].mean():.1f} °C")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Vue Globale", 
    "🔥 Chaufferie & Loi d'Eau", 
    "🌡️ Confort (7 Salles)", 
    "🍃 Qualité d'Air (QAI)"
])

# --- TAB 1 : VUE GLOBALE ---
with tab1:
    st.subheader("Superposition des signaux clés")
    fig_global = go.Figure()
    fig_global.add_trace(go.Scatter(x=df['Horodotage'], y=df['T_ext'], name="T° Extérieure", line=dict(color='gray', dash='dash')))
    fig_global.add_trace(go.Scatter(x=df['Horodotage'], y=df['V3V_Depart'], name="Départ V3V", line=dict(color='red')))
    
    if salles_cols_t:
        fig_global.add_trace(go.Scatter(x=df['Horodotage'], y=df[salles_cols_t].mean(axis=1), name="Moyenne 7 Salles", line=dict(color='orange')))
        
    fig_global.update_layout(xaxis_title="Date/Heure", yaxis_title="Température (°C)", height=450)
    st.plotly_chart(fig_global, use_container_width=True)

# --- TAB 2 : CHAUFFERIE & LOI D'EAU ---
with tab2:
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("Analyse de la Loi d'Eau Réelle")
        fig_loi_eau = px.scatter(
            df, x='T_ext', y='V3V_Depart', 
            color='Delta_T_Chaufferie',
            labels={'T_ext': 'Température Extérieure (°C)', 'V3V_Depart': 'Départ V3V (°C)'},
            title="Nuage de points : T° Ext vs T° Départ V3V"
        )
        st.plotly_chart(fig_loi_eau, use_container_width=True)
        
    with col_right:
        st.subheader("Régime Hydraulique (Delta T = Départ - Retour)")
        fig_delta_t = px.line(
            df, x='Horodotage', y='Delta_T_Chaufferie',
            title="Évolution du Delta T Chaufferie"
        )
        st.plotly_chart(fig_delta_t, use_container_width=True)

# --- TAB 3 : CONFORT ET ÉQUILIBRAGE (7 SALLES) ---
with tab3:
    st.subheader("Comparaison des Températures des 7 Salles")
    
    if salles_cols_t:
        fig_salles = px.line(df, x='Horodotage', y=salles_cols_t, title="Équilibrage thermique des salles")
        fig_salles.add_hline(y=t_min_confort, line_dash="dash", line_color="blue", annotation_text="Min Confort")
        fig_salles.add_hline(y=t_max_confort, line_dash="dash", line_color="red", annotation_text="Max Confort")
        st.plotly_chart(fig_salles, use_container_width=True)
        
        # Statistiques par salle
        st.subheader("Statistiques de Confort Thermal par Salle")
        stats_list = []
        for col in salles_cols_t:
            salle_name = col.replace('_T', '')
            t_moy = df[col].mean()
            h_sous_chauffe = (df[col] < t_min_confort).sum() * 0.25 # en heures
            h_sur_chauffe = (df[col] > t_max_confort).sum() * 0.25
            stats_list.append({
                'Salle': salle_name,
                'T° Moyenne (°C)': round(t_moy, 2),
                'Heures Sous-chauffe (<19°C)': h_sous_chauffe,
                'Heures Sur-chauffe (>22°C)': h_sur_chauffe
            })
        st.dataframe(pd.DataFrame(stats_list), use_container_width=True)

# --- TAB 4 : QUALITÉ DE L'AIR (QAI) ---
with tab4:
    st.subheader("Suivi des concentrations en CO2 (Confinement)")
    if salles_cols_co2:
        fig_co2 = px.line(df, x='Horodotage', y=salles_cols_co2, title="Évolution du CO2 par Salle")
        fig_co2.add_hline(y=seuil_co2, line_dash="dash", line_color="orange", annotation_text="Seuil Alerte")
        st.plotly_chart(fig_co2, use_container_width=True)
        
    col_cov, col_hr = st.columns(2)
    salles_cols_cov = [c for c in df.columns if c.endswith('_COV')]
    salles_cols_hr = [c for c in df.columns if c.endswith('_HR')]
    
    with col_cov:
        st.subheader("Composés Organiques Volatils (COV)")
        if salles_cols_cov:
            fig_cov = px.line(df, x='Horodotage', y=salles_cols_cov)
            st.plotly_chart(fig_cov, use_container_width=True)
            
    with col_hr:
        st.subheader("Humidité Relative (%)")
        if salles_cols_hr:
            fig_hr = px.line(df, x='Horodotage', y=salles_cols_hr)
            st.plotly_chart(fig_hr, use_container_width=True)
>>>>>>> c7a69a33e8518a0629c2be2af84c0543f9ccc8d8
