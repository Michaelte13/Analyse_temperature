# -*- coding: utf-8 -*-
"""
Application Streamlit d'Audit Énergétique & QAI
Analyse Automatisée de la Courbe de Chauffe (Loi d'Eau) avec colonnes Départs et Retours
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
    """Nettoie et formate un DataFrame issu d'un feuillet Excel avec détection auto des colonnes."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # 1. Identification de la colonne Date/Horodatage
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

    # 2. Renommage intelligent des colonnes clés
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()

        # Température extérieure
        if col_lower in [
            "ext.",
            "ext",
            "t_ext",
            "temp_ext",
            "t ext",
            "temp ext",
            "température ext",
        ]:
            col_mapping[col] = "T_ext"

        # Température de départ chauffage
        elif any(
            k in col_lower
            for k in [
                "eau départ",
                "eau depart",
                "t_depart",
                "temp_depart",
                "départ",
                "depart",
                "v3v_depart",
                "t_départ",
                "température départ",
            ]
        ):
            col_mapping[col] = "V3V_Depart"

        # Température de retour chauffage
        elif any(
            k in col_lower
            for k in [
                "température retour",
                "temperature retour",
                "t_retour",
                "temp_retour",
                "retour",
                "eau retour",
                "t retour",
            ]
        ):
            col_mapping[col] = "T_Retour"

    df = df.rename(columns=col_mapping)

    # Rétrocompatibilité : gestion d'une ancienne colonne combinée "Eau" ("45,2 - 37,1")
    if "V3V_Depart" not in df.columns:
        for col in df.columns:
            if str(col).lower().strip() == "eau":
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

    # 3. Conversion numérique de toutes les colonnes de mesures (virgules FR)
    for col in df.columns:
        if col != "Horodatage":
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
    """Génère des données de démo avec colonnes Eau départ et Température retour séparées."""
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

    # Génération séparée du Départ et du Retour Chauffage
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

    df_t["Eau départ"] = [f"{d:.1f}".replace(".", ",") for d in t_dep]
    df_t["Température retour"] = [f"{r:.1f}".replace(".", ",") for r in t_ret]

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
# 3. EXTRACTION ET CALCULS
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

st.title("🔥 Audit Énergétique — Analyse Courbe de Chauffe & QAI")

tab_t, tab_h, tab_c, tab_v = st.tabs(
    [
        "🌡️ 1. Température & Loi d'Eau",
        "💧 2. Humidité",
        "🟢 3. CO2",
        "🧪 4. COV",
    ]
)

# =============================================================================
# ONGLET 1 : TEMPÉRATURE ET ANALYSE DE LA COURBE DE CHAUFFE
# =============================================================================
with tab_t:
    st.subheader("🔥 Analyse Automatisée de la Courbe de Chauffe (Loi d'Eau)")

    has_ext = "T_ext" in df_temp.columns
    has_dep = "V3V_Depart" in df_temp.columns
    has_ret = "T_Retour" in df_temp.columns

    if not df_temp.empty and has_ext and has_dep:
        # Filtre des données valides pour la régression
        df_chauffe = df_temp.dropna(subset=["T_ext", "V3V_Depart"]).copy()

        # Calcul de la régression linéaire (Pente réelle)
        x_vals = df_chauffe["T_ext"].values
        y_vals = df_chauffe["V3V_Depart"].values

        mask_actif = y_vals > 22.0
        if mask_actif.sum() > 5:
            x_fit = x_vals[mask_actif]
            y_fit = y_vals[mask_actif]
            pente_reelle, intercept = np.polyfit(x_fit, y_fit, 1)

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
        inutile_mask = (df_temp["T_ext"] > t_coupure_chauffage) & (
            df_temp["V3V_Depart"] > 25.0
        )
        nb_heures_inutiles = (inutile_mask.sum() * 15) / 60.0

        delta_t_moyen = None
        if has_ret:
            df_temp["Delta_T"] = df_temp["V3V_Depart"] - df_temp["T_Retour"]
            delta_t_moyen = df_temp[df_temp["V3V_Depart"] > 25.0][
                "Delta_T"
            ].mean()

        # KPIs Chaufferie
        st.markdown("#### 📊 Indicateurs de Performance Chaufferie")
        kc1, kc2, kc3, kc4 = st.columns(4)

        kc1.metric(
            "Pente Réelle Observée",
            f"{pente_abs:.2f}",
            delta=f"Pente visée: {pente_theorique:.1f}",
            delta_color="normal"
            if abs(pente_abs - pente_theorique) < 0.2
            else "inverse",
        )

        kc2.metric(
            "Qualité Régulation (R²)",
            f"{r_squared:.2f}",
            delta="Stabilité OK" if r_squared > 0.7 else "Instable / Dispersé",
            delta_color="normal" if r_squared > 0.7 else "inverse",
        )

        kc3.metric(
            "Delta T° Moy. (Départ - Retour)",
            f"{delta_t_moyen:.1f} °C" if delta_t_moyen is not None else "N/A",
            delta="Échange optimal (5-10°C)"
            if (delta_t_moyen and 4 <= delta_t_moyen <= 12)
            else "Débit à vérifier",
        )

        kc4.metric(
            "Chauffage Hors Saison (> " + str(t_coupure_chauffage) + "°C ext)",
            f"{nb_heures_inutiles:.1f} heures",
            delta="Aucun gaspillage"
            if nb_heures_inutiles == 0
            else "Risque de surchauffe",
            delta_color="normal" if nb_heures_inutiles == 0 else "inverse",
        )

        st.divider()

        # GRAPHIQUE LOI D'EAU
        col_g1, col_g2 = st.columns([1.6, 1])

        with col_g1:
            st.markdown(
                "#### 📈 Nuage de Points & Régression ($T_{ext}$ vs $T_{départ}$)"
            )

            fig_loi = go.Figure()

            # Nuage de points
            fig_loi.add_trace(
                go.Scatter(
                    x=df_chauffe["T_ext"],
                    y=df_chauffe["V3V_Depart"],
                    mode="markers",
                    name="Mesures Eau Départ",
                    marker=dict(color="#3498db", opacity=0.5, size=6),
                )
            )

            # Optionnel : Ajout du nuage de points de Retour Chauffage si disponible
            if has_ret:
                fig_loi.add_trace(
                    go.Scatter(
                        x=df_chauffe["T_ext"],
                        y=df_chauffe["T_Retour"],
                        mode="markers",
                        name="Mesures Eau Retour",
                        marker=dict(color="#9b59b6", opacity=0.3, size=5),
                    )
                )

            # Ligne de régression
            x_line = np.linspace(
                df_chauffe["T_ext"].min(), df_chauffe["T_ext"].max(), 50
            )
            y_line = pente_reelle * x_line + intercept
            fig_loi.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_line,
                    mode="lines",
                    name=f"Loi d'eau Réelle (Pente = {pente_abs:.2f})",
                    line=dict(color="#e74c3c", width=3),
                )
            )

            # Ligne théorique
            y_theo = 20 + pente_theorique * (20 - x_line)
            fig_loi.add_trace(
                go.Scatter(
                    x=x_line,
                    y=y_theo,
                    mode="lines",
                    name=f"Loi d'eau Théorique ({pente_theorique})",
                    line=dict(color="#2ecc71", dash="dash", width=2),
                )
            )

            fig_loi.add_vline(
                x=t_coupure_chauffage,
                line_dash="dot",
                line_color="orange",
                annotation_text=f"Coupure ({t_coupure_chauffage}°C)",
            )

            fig_loi.update_layout(
                xaxis_title="Température Extérieure (°C)",
                yaxis_title="Température Eau (°C)",
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
            st.markdown("#### 🔍 Diagnostic Régulation")

            diagnostics = []
            if r_squared < 0.5:
                diagnostics.append(
                    "⚠️ **Dispersion Élevée** : La régulation manque de stabilité. Vérifier si la vanne 3 voies oscille ou est manipulée manuellement."
                )

            if pente_abs > pente_theorique + 0.3:
                diagnostics.append(
                    f"🔴 **Pente Réelle Élevée ({pente_abs:.2f})** : L'eau est trop chaude par grand froid. Risque de gaspillage énergétique."
                )
            elif pente_abs < pente_theorique - 0.3:
                diagnostics.append(
                    f"🔵 **Pente Réelle Faible ({pente_abs:.2f})** : Risque d'inconfort dans les locaux par basse température extérieure."
                )
            else:
                diagnostics.append(
                    "✅ **Pente Optimale** : La pente calculée concorde avec la consigne théorique."
                )

            if nb_heures_inutiles > 0:
                diagnostics.append(
                    f"🔥 **Consigne de Coupure à Réglée** : {nb_heures_inutiles:.1f}h d'envoi d'eau chaude au-delà de {t_coupure_chauffage}°C extérieurs."
                )

            if delta_t_moyen and delta_t_moyen < 4.0:
                diagnostics.append(
                    "⚠️ **Delta T° Faible (< 4°C)** : Le circulateur tourne probablement trop vite (vitesse trop élevée)."
                )

            for diag in diagnostics:
                st.info(diag)

        st.markdown("---")
        st.markdown("#### 🏢 Évolution Chronologique des Températures")

        fig_salles = px.line(
            df_temp,
            x="Horodatage",
            y=salles_temp,
            title="Températures d'Ambiance par Zone",
        )
        if "V3V_Depart" in df_temp.columns:
            fig_salles.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["V3V_Depart"],
                    name="T° Départ Eau",
                    line=dict(color="#e74c3c", width=1.5),
                )
            )
        if "T_Retour" in df_temp.columns:
            fig_salles.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["T_Retour"],
                    name="T° Retour Eau",
                    line=dict(color="#9b59b6", width=1.5),
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
            "⚠️ Assurez-vous d'avoir une colonne pour la température extérieure ('Ext.') et le départ chauffage ('Eau départ') dans votre fichier."
        )


# =============================================================================
# ONGLET 2 : HUMIDITÉ
# =============================================================================
with tab_h:
    st.subheader("Humidité Relative (%)")
    if not df_hum.empty and salles_hum:
        fig_hum = px.line(
            df_hum,
            x="Horodatage",
            y=salles_hum,
            title="Évolution de l'Humidité par Zone",
        )
        st.plotly_chart(fig_hum, use_container_width=True)
    else:
        st.info("Données d'humidité indisponibles.")


# =============================================================================
# ONGLET 3 : CO2
# =============================================================================
with tab_c:
    st.subheader("Niveaux de Confinement CO2 (ppm)")
    if not df_co2.empty and salles_co2:
        fig_co2 = px.line(
            df_co2,
            x="Horodatage",
            y=salles_co2,
            title="Évolution du CO2 par Zone",
        )
        fig_co2.add_hline(
            y=seuil_co2,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil ({seuil_co2} ppm)",
        )
        st.plotly_chart(fig_co2, use_container_width=True)
    else:
        st.info("Données de CO2 indisponibles.")


# =============================================================================
# ONGLET 4 : COV
# =============================================================================
with tab_v:
    st.subheader("Composés Organiques Volatils COV (ppb)")
    if not df_cov.empty and salles_cov:
        fig_cov = px.line(
            df_cov,
            x="Horodatage",
            y=salles_cov,
            title="Évolution des COV par Zone",
        )
        fig_cov.add_hline(
            y=seuil_cov,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil ({seuil_cov} ppb)",
        )
        st.plotly_chart(fig_cov, use_container_width=True)
    else:
        st.info("Données de COV indisponibles.")