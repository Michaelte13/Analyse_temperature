# -*- coding: utf-8 -*-
"""
Application Streamlit d'Audit Énergétique & QAI
Analyse Automatisée de la Courbe de Chauffe (Loi d'Eau) & Confort
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
    page_title="Audit Énergétique - Courbe de Chauffe & QAI",
    page_icon="🔥",
    layout="wide",
)

# -----------------------------------------------------------------------------
# 1. FONCTIONS DE TRAITEMENT ET CHARGEMENT DES DONNÉES
# -----------------------------------------------------------------------------


def process_custom_dataframe(df):
    """Nettoie et formate un DataFrame issu d'un feuillet Excel."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Identification de la colonne Date/Horodatage
    date_cols = [
        c
        for c in df.columns
        if "date" in str(c).lower()
        or "horodatage" in str(c).lower()
        or "time" in str(c).lower()
    ]
    if date_cols:
        df = df.rename(columns={date_cols[0]: "Horodatage"})
    else:
        df = df.rename(columns={df.columns[0]: "Horodatage"})

    # Conversion de la date (Format FR: DD/MM/YYYY HH:MM:SS)
    df["Horodatage"] = pd.to_datetime(
        df["Horodatage"], dayfirst=True, errors="coerce"
    )
    df = df.dropna(subset=["Horodatage"]).sort_values("Horodatage")

    # Traitement des valeurs numériques et des virgules françaises
    for col in list(df.columns):
        if col != "Horodatage":
            if str(col).lower().strip() == "eau":
                # Extraction du départ et retour si format "45,2 - 37,1"
                if df[col].dtype == object or str(df[col].dtype) == "string":
                    split_eau = df[col].astype(str).str.split("-", expand=True)
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
                if df[col].dtype == object or str(df[col].dtype) == "string":
                    clean_series = (
                        df[col]
                        .astype(str)
                        .str.replace(",", ".")
                        .str.strip()
                    )
                    df[col] = pd.to_numeric(clean_series, errors="coerce")
                else:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

    # Renommage explicite de la température extérieure
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ["ext.", "ext", "t_ext", "temp_ext"]:
            col_mapping[col] = "T_ext"

    df = df.rename(columns=col_mapping)

    cols_a_garder = ["Horodatage"] + [
        c
        for c in df.columns
        if c != "Horodatage" and df[c].notnull().sum() > 0
    ]
    return df[cols_a_garder]


def load_data(uploaded_file):
    """Lit toutes les feuilles de l'Excel et retourne un dictionnaire de DataFrames."""
    data_dict = {
        "Température": pd.DataFrame(),
        "Humidité": pd.DataFrame(),
        "CO2": pd.DataFrame(),
        "COV": pd.DataFrame(),
    }

    if uploaded_file.name.endswith(".csv"):
        df_csv = pd.read_csv(uploaded_file, sep=None, engine="python")
        data_dict["Température"] = process_custom_dataframe(df_csv)
        return data_dict

    xls = pd.ExcelFile(uploaded_file)
    sheets_dict = pd.read_excel(xls, sheet_name=None)

    for sheet_name, df_raw in sheets_dict.items():
        df_clean = process_custom_dataframe(df_raw)
        s_lower = sheet_name.lower().strip()

        if "temp" in s_lower:
            data_dict["Température"] = df_clean
        elif "hum" in s_lower or "hygro" in s_lower:
            data_dict["Humidité"] = df_clean
        elif "co2" in s_lower:
            data_dict["CO2"] = df_clean
        elif "cov" in s_lower or "voc" in s_lower:
            data_dict["COV"] = df_clean

    return data_dict


@st.cache_data
def generate_synthetic_data():
    """Génère des données de démo intégrant une chaufferie avec régulation."""
    start_date = datetime(2026, 3, 11, 16, 45)
    dates = [
        start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)
    ]
    salles = ["Nord", "Est", "Sud", "Aux 1", "Aux 2"]

    df_t = pd.DataFrame({"Date FR": dates})
    t_ext_vals = (
        6
        + 5 * np.sin(np.pi * df_t.index / 48)
        + np.random.normal(0, 0.5, len(df_t))
    )
    df_t["Ext."] = [f"{v:.1f}".replace(".", ",") for v in t_ext_vals]

    for i, s in enumerate(salles):
        b_t = 19 + (i * 0.4)
        v_t = np.where(
            df_t["Date FR"].dt.hour.between(7, 19), b_t + 2, b_t
        ) + np.random.normal(0, 0.2, len(df_t))
        df_t[s] = [f"{v:.1f}".replace(".", ",") for v in v_t]

    # Génération d'une loi d'eau réelle (Pente ~ 1.2)
    t_dep = np.where(
        t_ext_vals < 16,
        45 - 1.2 * (t_ext_vals - 5) + np.random.normal(0, 0.6, len(df_t)),
        20.0,
    )
    t_ret = np.where(
        t_ext_vals < 16,
        t_dep - 7.5 + np.random.normal(0, 0.3, len(df_t)),
        20.0,
    )

    df_t["Eau"] = [
        f"{d:.1f}".replace(".", ",") + " - " + f"{r:.1f}".replace(".", ",")
        for d, r in zip(t_dep, t_ret)
    ]

    # Humidité, CO2, COV
    df_h = pd.DataFrame({"Date FR": dates})
    df_h["Ext."] = [
        f"{v:.1f}".replace(".", ",")
        for v in (
            70
            + 10 * np.sin(np.pi * df_h.index / 96)
            + np.random.normal(0, 2, len(df_h))
        )
    ]
    for s in salles:
        v_h = (
            42
            + 5 * np.sin(np.pi * df_h.index / 96)
            + np.random.normal(0, 1.5, len(df_h))
        )
        df_h[s] = [f"{v:.1f}".replace(".", ",") for v in v_h]

    df_c = pd.DataFrame({"Date FR": dates})
    for s in salles:
        v_c = np.where(
            df_c["Date FR"].dt.hour.between(8, 18),
            500 + 400 * np.sin(np.pi * (df_c["Date FR"].dt.hour - 8) / 10),
            420,
        ) + np.random.normal(0, 25, len(df_c))
        df_c[s] = [f"{int(max(400, v))}" for v in v_c]

    df_v = pd.DataFrame({"Date FR": dates})
    for s in salles:
        v_v = np.where(
            df_v["Date FR"].dt.hour.between(8, 18),
            100 + 80 * np.sin(np.pi * (df_v["Date FR"].dt.hour - 8) / 10),
            60,
        ) + np.random.normal(0, 15, len(df_v))
        df_v[s] = [f"{int(max(30, v))}" for v in v_v]

    return {
        "Température": process_custom_dataframe(df_t),
        "Humidité": process_custom_dataframe(df_h),
        "CO2": process_custom_dataframe(df_c),
        "COV": process_custom_dataframe(df_v),
    }


# -----------------------------------------------------------------------------
# 2. BARRE LATÉRALE : FILTRES & CONFIGURATION COURBE DE CHAUFFE
# -----------------------------------------------------------------------------

st.sidebar.title("🛠️ Configuration & Réglages")

uploaded_file = st.sidebar.file_uploader(
    "Fichier de mesures (Excel multi-onglets)", type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:
    data_dict = load_data(uploaded_file)
    st.sidebar.success("Fichier chargé avec succès !")
else:
    st.sidebar.info("Utilisation des données de démo.")
    data_dict = generate_synthetic_data()

all_min_dates = []
all_max_dates = []
for key, df_sheet in data_dict.items():
    if not df_sheet.empty and "Horodatage" in df_sheet.columns:
        valid_dates = df_sheet["Horodatage"].dropna()
        if not valid_dates.empty:
            all_min_dates.append(valid_dates.min().date())
            all_max_dates.append(valid_dates.max().date())

if not all_min_dates:
    st.error("❌ Aucune date valide trouvée.")
    st.stop()

global_min_date = min(all_min_dates)
global_max_date = max(all_max_dates)

date_range = st.sidebar.date_input(
    "Période d'analyse",
    value=(global_min_date, global_max_date),
    min_value=global_min_date,
    max_value=global_max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_filter, end_filter = date_range
    for key in data_dict:
        if not data_dict[key].empty and "Horodatage" in data_dict[key].columns:
            df_curr = data_dict[key]
            data_dict[key] = df_curr[
                (df_curr["Horodatage"].dt.date >= start_filter)
                & (df_curr["Horodatage"].dt.date <= end_filter)
            ]

# --- PARAMÈTRES COURBE DE CHAUFFE & CONFORT ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔥 Paramètres Courbe de Chauffe")
t_coupure_chauffage = st.sidebar.slider(
    "T° Extérieure Coupure Chauffage (°C)", 12.0, 20.0, 15.0, step=0.5
)
pente_theorique = st.sidebar.slider(
    "Pente Théorique Visée", 0.5, 2.5, 1.2, step=0.1
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Confort & Seuils")
t_min_confort = st.sidebar.number_input("T° Min Confort (°C)", value=19.0)
t_max_confort = st.sidebar.number_input("T° Max Confort (°C)", value=22.0)
seuil_co2 = st.sidebar.number_input("Seuil CO2 (ppm)", value=1000)
seuil_cov = st.sidebar.number_input("Seuil COV (ppb)", value=200)


# -----------------------------------------------------------------------------
# 3. EXTRACTION ET CALCULS DE LA COURBE DE CHAUFFE
# -----------------------------------------------------------------------------

df_temp = data_dict.get("Température", pd.DataFrame())
df_hum = data_dict.get("Humidité", pd.DataFrame())
df_co2 = data_dict.get("CO2", pd.DataFrame())
df_cov = data_dict.get("COV", pd.DataFrame())


def get_room_cols(df):
    if df.empty:
        return []
    excl = ["Horodatage", "T_ext", "Eau", "V3V_Depart", "T_Retour"]
    return [c for c in df.columns if c not in excl]


salles_temp = get_room_cols(df_temp)
salles_hum = get_room_cols(df_hum)
salles_co2 = get_room_cols(df_co2)
salles_cov = get_room_cols(df_cov)


# -----------------------------------------------------------------------------
# 4. DASHBOARD PRINCIPAL
# -----------------------------------------------------------------------------

st.title("🔥 Tableau de Bord - Audit Chaufferie & Loi d'Eau")

tab_t, tab_h, tab_c, tab_v = st.tabs(
    [
        "🌡️ 1. Température & Loi d'Eau",
        "💧 2. Humidité",
        "🟢 3. CO2",
        "🧪 4. COV",
    ]
)

# =============================================================================
# ONGLET 1 : TEMPÉRATURE ET ANALYSE DÉTAILLÉE DE LA COURBE DE CHAUFFE
# =============================================================================
with tab_t:
    st.subheader("🔥 Analyse Complète de la Courbe de Chauffe (Loi d'Eau)")

    has_ext = "T_ext" in df_temp.columns
    has_dep = "V3V_Depart" in df_temp.columns
    has_ret = "T_Retour" in df_temp.columns

    if not df_temp.empty and has_ext and has_dep:
        # Filtre des données valides pour la régression
        df_chauffe = df_temp.dropna(subset=["T_ext", "V3V_Depart"]).copy()

        # Calcul de la régression linéaire (Pente réelle)
        x_vals = df_chauffe["T_ext"].values
        y_vals = df_chauffe["V3V_Depart"].values

        # Ne prendre que la période de chauffage actif (ex: T_dep > 22°C)
        mask_actif = y_vals > 22.0
        if mask_actif.sum() > 5:
            x_fit = x_vals[mask_actif]
            y_fit = y_vals[mask_actif]
            pente_reelle, intercept = np.polyfit(x_fit, y_fit, 1)
            # R2
            correlation_matrix = np.corrcoef(x_fit, y_fit)
            r_squared = (
                correlation_matrix[0, 1] ** 2
                if correlation_matrix.shape == (2, 2)
                else 0
            )
        else:
            pente_reelle, intercept, r_squared = 0, 0, 0

        pente_abs = abs(pente_reelle)

        # Calcul des anomalies
        # 1. Chauffage inutile quand T_ext > T_coupure
        inutile_mask = (df_temp["T_ext"] > t_coupure_chauffage) & (
            df_temp["V3V_Depart"] > 25.0
        )
        nb_heures_inutiles = (inutile_mask.sum() * 15) / 60.0

        # 2. Delta T moyen (Départ - Retour)
        delta_t_moyen = None
        if has_ret:
            df_temp["Delta_T"] = df_temp["V3V_Depart"] - df_temp["T_Retour"]
            delta_t_moyen = df_temp[df_temp["V3V_Depart"] > 25.0][
                "Delta_T"
            ].mean()

        # KPIs Chaufferie
        st.markdown("#### 📊 Indicateurs de Performance de la Chaufferie")
        kc1, kc2, kc3, kc4 = st.columns(4)

        kc1.metric(
            "Pente Réelle Observée",
            f"{pente_abs:.2f}",
            delta=f"Cible théorique: {pente_theorique:.1f}",
            delta_color="normal"
            if abs(pente_abs - pente_theorique) < 0.2
            else "inverse",
        )

        kc2.metric(
            "Qualité Régulation (R²)",
            f"{r_squared:.2f}",
            delta="Bonne (R² > 0.7)" if r_squared > 0.7 else "Instable",
            delta_color="normal" if r_squared > 0.7 else "inverse",
        )

        kc3.metric(
            "Delta T° Moy. (Départ - Retour)",
            f"{delta_t_moyen:.1f} °C" if delta_t_moyen is not None else "N/A",
            delta="Irrigation OK (5-10°C)"
            if (delta_t_moyen and 4 <= delta_t_moyen <= 12)
            else "Vérifier débit",
        )

        kc4.metric(
            "Chauffage Inutile (> " + str(t_coupure_chauffage) + "°C ext)",
            f"{nb_heures_inutiles:.1f} heures",
            delta="Aucun gaspillage"
            if nb_heures_inutiles == 0
            else "Surchauffe hors saison",
            delta_color="normal" if nb_heures_inutiles == 0 else "inverse",
        )

        st.divider()

        # GRAPHIQUE LOI D'EAU AUTOMATISÉ
        col_g1, col_g2 = st.columns([1.6, 1])

        with col_g1:
            st.markdown("#### 📈 Courbe de Chauffe / Loi d'Eau ($T_{ext}$ vs $T_{départ}$)")

            fig_loi = go.Figure()

            # Nuage de points réels
            fig_loi.add_trace(
                go.Scatter(
                    x=df_chauffe["T_ext"],
                    y=df_chauffe["V3V_Depart"],
                    mode="markers",
                    name="Mesures Réelles",
                    marker=dict(
                        color="#3498db", opacity=0.5, size=6
                    ),
                )
            )

            # Ligne de régression réelle
            x_line = np.linspace(
                df_chauffe["T_ext"].min(), df_chauffe["T_ext"].max(), 50
            )
            y_line = pente_reelle * x_line + intercept
            fig_loi.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_line,
                    mode="lines",
                    name=f"Régression Observée (Pente = {pente_abs:.2f})",
                    line=dict(color="#e74c3c", width=3),
                )
            )

            # Ligne théorique indicative
            y_theo = 20 + pente_theorique * (20 - x_line)
            fig_loi.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_theo,
                    mode="lines",
                    name=f"Loi d'Eau Théorique (Pente = {pente_theorique})",
                    line=dict(color="#2ecc71", dash="dash", width=2),
                )
            )

            # Seuil de coupure
            fig_loi.add_vline(
                x=t_coupure_chauffage,
                line_dash="dot",
                line_color="orange",
                annotation_text=f"Coupure ({t_coupure_chauffage}°C)",
            )

            fig_loi.update_layout(
                xaxis_title="Température Extérieure (°C)",
                yaxis_title="Température Départ Chauffage (°C)",
                height=420,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
            )
            st.plotly_chart(fig_loi, use_container_width=True)

        with col_g2:
            st.markdown("#### 🔍 Diagnostic Automatisé de la Chaufferie")

            # Moteur de règles d'analyse automatisé
            diagnostics = []

            if r_squared < 0.5:
                diagnostics.append(
                    "⚠️ **Régulation Instable** : La dispersion des points indique que la vanne 3 voies (V3V) régule mal ou subit des perturbations manuelles / horaires incohérentes."
                )

            if pente_abs > pente_theorique + 0.3:
                diagnostics.append(
                    f"🔴 **Loi d'Eau Trop Forte (Pente {pente_abs:.2f})** : La chaufferie envoie une eau trop chaude par grand froid, entraînant des risques de surchauffe et de gaspillage."
                )
            elif pente_abs < pente_theorique - 0.3:
                diagnostics.append(
                    f"🔵 **Loi d'Eau Trop Faible (Pente {pente_abs:.2f})** : Risque d'inconfort et de sous-chauffe en période hivernale rigoureuse."
                )
            else:
                diagnostics.append(
                    "✅ **Pente Optimale** : La pente observée est parfaitement cohérente avec la pente théorique."
                )

            if nb_heures_inutiles > 0:
                diagnostics.append(
                    f"🔥 **Absence de Coupure Estivale** : {nb_heures_inutiles:.1f}h de chauffage ont été enregistrées au-dessus de {t_coupure_chauffage}°C extérieurs. Ajuster la température de basculement été/hiver sur l'automate."
                )

            if delta_t_moyen and delta_t_moyen < 4.0:
                diagnostics.append(
                    "⚠️ **Delta T° trop faible (< 4°C)** : Débit circulateur trop élevé ou surdimensionné (eau revient sans échanger sa chaleur)."
                )

            for diag in diagnostics:
                st.info(diag)

        # Graphique des Températures de Zones & Ambiance
        st.markdown("---")
        st.markdown("#### 🏢 Températures Ambiantes dans les Zones")

        fig_salles = px.line(
            df_temp,
            x="Horodatage",
            y=salles_temp,
            title="Évolution des Températures Intérieures",
        )
        if "T_ext" in df_temp.columns:
            fig_salles.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["T_ext"],
                    name="T° Extérieure",
                    line=dict(color="gray", dash="dash"),
                )
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
        st.warning(
            "⚠️ Les colonnes de chaufferie ('T_ext' et 'Eau' ou 'V3V_Depart') sont nécessaires dans l'onglet 'Température' pour générer l'analyse de la courbe de chauffe."
        )


# =============================================================================
# ONGLET 2 : HUMIDITÉ
# =============================================================================
with tab_h:
    st.subheader("Analyse de l'Humidité Relative (%)")
    if not df_hum.empty and salles_hum:
        fig_hum = px.line(
            df_hum,
            x="Horodatage",
            y=salles_hum,
            title="Humidité Relative par Zone",
        )
        st.plotly_chart(fig_hum, use_container_width=True)
    else:
        st.info("Données d'humidité non disponibles.")


# =============================================================================
# ONGLET 3 : CO2
# =============================================================================
with tab_c:
    st.subheader("Analyse du Confinement CO2 (ppm)")
    if not df_co2.empty and salles_co2:
        fig_co2 = px.line(
            df_co2,
            x="Horodatage",
            y=salles_co2,
            title="Niveaux de CO2 par Zone",
        )
        fig_co2.add_hline(
            y=seuil_co2,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil ({seuil_co2} ppm)",
        )
        st.plotly_chart(fig_co2, use_container_width=True)
    else:
        st.info("Données de CO2 non disponibles.")


# =============================================================================
# ONGLET 4 : COV
# =============================================================================
with tab_v:
    st.subheader("Analyse des COV (ppb)")
    if not df_cov.empty and salles_cov:
        fig_cov = px.line(
            df_cov,
            x="Horodatage",
            y=salles_cov,
            title="Composés Organiques Volatils par Zone",
        )
        fig_cov.add_hline(
            y=seuil_cov,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil ({seuil_cov} ppb)",
        )
        st.plotly_chart(fig_cov, use_container_width=True)
    else:
        st.info("Données de COV non disponibles.")