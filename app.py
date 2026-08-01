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
# 1. FONCTIONS DE TRAITEMENT ET CHARGEMENT DES ONGLETS EXCEL
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
                # Traitement spécial colonne Eau ("31,5 - 31,2")
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

    # Renommage explicite de la température extérieure si présente
    col_mapping = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ["ext.", "ext", "t_ext", "temp_ext"]:
            col_mapping[col] = "T_ext"

    df = df.rename(columns=col_mapping)

    # Suppression des colonnes entièrement vides
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
        # Si fichier CSV unique
        df_csv = pd.read_csv(uploaded_file, sep=None, engine="python")
        df_clean = process_custom_dataframe(df_csv)
        data_dict["Température"] = df_clean
        return data_dict

    # Fichier Excel multi-onglets
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
    """Génère 4 feuillets de démo si aucun fichier n'est chargé."""
    start_date = datetime(2026, 3, 11, 16, 45)
    dates = [
        start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)
    ]
    salles = ["Nord", "Est", "Sud", "Aux 1", "Aux 2"]

    # 1. Température
    df_t = pd.DataFrame({"Date FR": dates})
    t_ext_vals = (
        5
        + 4 * np.sin(np.pi * df_t.index / 48)
        + np.random.normal(0, 0.5, len(df_t))
    )
    df_t["Ext."] = [f"{v:.1f}".replace(".", ",") for v in t_ext_vals]
    for i, s in enumerate(salles):
        b_t = 19 + (i * 0.4)
        v_t = np.where(
            df_t["Date FR"].dt.hour.between(7, 19), b_t + 2, b_t
        ) + np.random.normal(0, 0.2, len(df_t))
        df_t[s] = [f"{v:.1f}".replace(".", ",") for v in v_t]

    t_dep = 45 - 1.2 * t_ext_vals + np.random.normal(0, 0.3, len(df_t))
    t_ret = t_dep - 8 + np.random.normal(0, 0.2, len(df_t))
    df_t["Eau"] = [
        f"{d:.1f}".replace(".", ",") + " - " + f"{r:.1f}".replace(".", ",")
        for d, r in zip(t_dep, t_ret)
    ]

    # 2. Humidité
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

    # 3. CO2
    df_c = pd.DataFrame({"Date FR": dates})
    for s in salles:
        v_c = np.where(
            df_c["Date FR"].dt.hour.between(8, 18),
            500 + 400 * np.sin(np.pi * (df_c["Date FR"].dt.hour - 8) / 10),
            420,
        ) + np.random.normal(0, 25, len(df_c))
        df_c[s] = [f"{int(max(400, v))}" for v in v_c]

    # 4. COV
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
# 2. BARRE LATÉRALE (SIDEBAR) & FILTRES
# -----------------------------------------------------------------------------

st.sidebar.title("🛠️ Configuration Audit")

uploaded_file = st.sidebar.file_uploader(
    "Fichier de mesures (Excel multi-onglets)", type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:
    data_dict = load_data(uploaded_file)
    st.sidebar.success("Fichier Excel chargé avec succès !")
else:
    st.sidebar.info("Aucun fichier importé. Utilisation des données de démo.")
    data_dict = generate_synthetic_data()

# Recherche des dates min et max globales sur l'ensemble des DataFrames
all_min_dates = []
all_max_dates = []

for key, df_sheet in data_dict.items():
    if not df_sheet.empty and "Horodatage" in df_sheet.columns:
        valid_dates = df_sheet["Horodatage"].dropna()
        if not valid_dates.empty:
            all_min_dates.append(valid_dates.min().date())
            all_max_dates.append(valid_dates.max().date())

if not all_min_dates:
    st.error(
        "❌ Aucune date valide n'a été trouvée dans le fichier Excel. Vérifiez le format de vos colonnes de dates."
    )
    st.stop()

global_min_date = min(all_min_dates)
global_max_date = max(all_max_dates)

date_range = st.sidebar.date_input(
    "Période d'analyse",
    value=(global_min_date, global_max_date),
    min_value=global_min_date,
    max_value=global_max_date,
)

# Application du filtre temporel à chacun des onglets
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_filter, end_filter = date_range
    for key in data_dict:
        if not data_dict[key].empty and "Horodatage" in data_dict[key].columns:
            df_curr = data_dict[key]
            data_dict[key] = df_curr[
                (df_curr["Horodatage"].dt.date >= start_filter)
                & (df_curr["Horodatage"].dt.date <= end_filter)
            ]

# Paramétrage des seuils dans la barre latérale
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
# 3. EXTRACTION ET CALCULS DES KPIS
# -----------------------------------------------------------------------------

df_temp = data_dict.get("Température", pd.DataFrame())
df_hum = data_dict.get("Humidité", pd.DataFrame())
df_co2 = data_dict.get("CO2", pd.DataFrame())
df_cov = data_dict.get("COV", pd.DataFrame())

# Helper pour récupérer les colonnes des zones (salles)
def get_room_cols(df, extra_excl=None):
    if df.empty:
        return []
    excl = ["Horodatage", "T_ext", "Eau", "V3V_Depart", "T_Retour"]
    if extra_excl:
        excl.extend(extra_excl)
    return [c for c in df.columns if c not in excl]


salles_temp = get_room_cols(df_temp)
salles_hum = get_room_cols(df_hum)
salles_co2 = get_room_cols(df_co2)
salles_cov = get_room_cols(df_cov)

avg_temp = (
    df_temp[salles_temp].mean().mean()
    if not df_temp.empty and salles_temp
    else None
)
avg_hum = (
    df_hum[salles_hum].mean().mean()
    if not df_hum.empty and salles_hum
    else None
)
max_co2 = (
    df_co2[salles_co2].max().max() if not df_co2.empty and salles_co2 else None
)
max_cov = (
    df_cov[salles_cov].max().max() if not df_cov.empty and salles_cov else None
)


# -----------------------------------------------------------------------------
# 4. DASHBOARD PRINCIPAL (STRUCTURE EN 4 ONGLETS)
# -----------------------------------------------------------------------------

st.title("🏛️ Tableau de Bord - Audit Énergétique & QAI")
st.markdown("Analyse multi-onglets : Température, Humidité, CO2 et COV")

# KPIs synthétiques
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric(
    "Température Intérieure Moy.",
    f"{avg_temp:.1f} °C" if avg_temp is not None else "N/A",
)
kpi2.metric(
    "Humidité Relative Moy.",
    f"{avg_hum:.1f} %" if avg_hum is not None else "N/A",
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

tab_t, tab_h, tab_c, tab_v = st.tabs(
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
with tab_t:
    st.subheader("Analyse Thermique (Onglet 'Température')")

    if not df_temp.empty:
        # Superposition des signaux principaux
        fig_temp = go.Figure()

        if "T_ext" in df_temp.columns:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["T_ext"],
                    name="T° Extérieure",
                    line=dict(color="blue", dash="dash"),
                )
            )

        if "V3V_Depart" in df_temp.columns:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["V3V_Depart"],
                    name="Départ V3V (Eau)",
                    line=dict(color="red"),
                )
            )

        if "T_Retour" in df_temp.columns:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["T_Retour"],
                    name="Retour Chaufferie",
                    line=dict(color="darkred", dash="dot"),
                )
            )

        if salles_temp:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp[salles_temp].mean(axis=1),
                    name="Moyenne des Zones",
                    line=dict(color="orange", width=2.5),
                )
            )

        fig_temp.update_layout(
            xaxis_title="Date / Heure",
            yaxis_title="Température (°C)",
            height=400,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        col_loi, col_zones = st.columns(2)

        with col_loi:
            st.markdown("#### Loi d'Eau (T° Ext vs T° Départ)")
            if "T_ext" in df_temp.columns and "V3V_Depart" in df_temp.columns:
                fig_loi = px.scatter(
                    df_temp,
                    x="T_ext",
                    y="V3V_Depart",
                    labels={
                        "T_ext": "T° Extérieure (°C)",
                        "V3V_Depart": "Départ V3V (°C)",
                    },
                    title="Régulation de la Chaufferie",
                )
                st.plotly_chart(fig_loi, use_container_width=True)
            else:
                st.info("Données de chaufferie (Eau) non disponibles.")

        with col_zones:
            st.markdown("#### Équilibrage par Zone")
            if salles_temp:
                fig_salles = px.line(
                    df_temp,
                    x="Horodatage",
                    y=salles_temp,
                    title="Températures par Zone / Salle",
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

        # Bilan
        if salles_temp:
            st.markdown("#### Statistiques de Confort Thermique")
            t_stats = []
            for col in salles_temp:
                t_moy = df_temp[col].mean()
                h_sous = (df_temp[col] < t_min_confort).sum() * 0.25
                h_sur = (df_temp[col] > t_max_confort).sum() * 0.25
                t_stats.append(
                    {
                        "Zone / Salle": col,
                        "T° Moyenne (°C)": round(t_moy, 2)
                        if pd.notnull(t_moy)
                        else "-",
                        f"Sous-chauffe (<{t_min_confort}°C)": f"{h_sous:.1f} h",
                        f"Sur-chauffe (>{t_max_confort}°C)": f"{h_sur:.1f} h",
                    }
                )
            st.dataframe(pd.DataFrame(t_stats), use_container_width=True)
    else:
        st.warning("⚠️ Onglet 'Température' introuvable ou vide.")


# =============================================================================
# ONGLET 2 : HUMIDITÉ
# =============================================================================
with tab_h:
    st.subheader("Analyse de l'Humidité Relative (Onglet 'Humidité')")

    if not df_hum.empty and salles_hum:
        fig_hum = px.line(
            df_hum,
            x="Horodatage",
            y=salles_hum,
            title="Évolution de l'Humidité Relative (%)",
            labels={"value": "Humidité (%)", "variable": "Zone"},
        )
        fig_hum.add_hline(
            y=hr_min_confort,
            line_dash="dash",
            line_color="orange",
            annotation_text=f"Min Confort ({hr_min_confort}%)",
        )
        fig_hum.add_hline(
            y=hr_max_confort,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Max Confort ({hr_max_confort}%)",
        )
        st.plotly_chart(fig_hum, use_container_width=True)

        col_h_left, col_h_right = st.columns(2)

        with col_h_left:
            st.markdown("#### Bilan par Zone")
            h_stats = []
            for col in salles_hum:
                h_stats.append(
                    {
                        "Zone / Salle": col,
                        "Humidité Moyenne (%)": round(df_hum[col].mean(), 1),
                        "Min (%)": round(df_hum[col].min(), 1),
                        "Max (%)": round(df_hum[col].max(), 1),
                        f"Trop Sec (<{hr_min_confort}%)": f"{(df_hum[col] < hr_min_confort).mean()*100:.1f} %",
                        f"Trop Humide (>{hr_max_confort}%)": f"{(df_hum[col] > hr_max_confort).mean()*100:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(h_stats), use_container_width=True)

        with col_h_right:
            st.markdown("#### Distribution des valeurs d'Humidité")
            fig_hist = px.histogram(
                df_hum,
                x=salles_hum,
                nbins=25,
                barmode="overlay",
                title="Répartition des mesures d'humidité",
            )
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.warning("⚠️ Onglet 'Humidité' introuvable ou ne contenant pas de données de zone.")


# =============================================================================
# ONGLET 3 : CO2
# =============================================================================
with tab_c:
    st.subheader("Analyse du CO2 et du Confinement (Onglet 'CO2')")

    if not df_co2.empty and salles_co2:
        fig_co2 = px.line(
            df_co2,
            x="Horodatage",
            y=salles_co2,
            title="Évolution du CO2 (ppm)",
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

        col_c_left, col_c_right = st.columns(2)

        with col_c_left:
            st.markdown("#### Bilan du Confinement par Zone")
            c_stats = []
            for col in salles_co2:
                h_dep = (df_co2[col] > seuil_co2).sum() * 0.25
                c_stats.append(
                    {
                        "Zone / Salle": col,
                        "Moyenne (ppm)": int(df_co2[col].mean()),
                        "Max (ppm)": int(df_co2[col].max()),
                        f"Temps > {seuil_co2} ppm": f"{h_dep:.1f} h",
                        "Taux d'Alerte (%)": f"{(df_co2[col] > seuil_co2).mean()*100:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(c_stats), use_container_width=True)

        with col_c_right:
            st.markdown("#### Répartition Globale de la Qualité d'Air")
            co2_vals_all = df_co2[salles_co2].values.flatten()
            co2_vals_clean = co2_vals_all[~np.isnan(co2_vals_all)]

            bon = (co2_vals_clean < 800).sum()
            moyen = ((co2_vals_clean >= 800) & (co2_vals_clean <= seuil_co2)).sum()
            eleve = (co2_vals_clean > seuil_co2).sum()

            fig_pie = px.pie(
                names=[
                    "Bon (<800 ppm)",
                    f"Moyen (800-{seuil_co2} ppm)",
                    f"Élevé (>{seuil_co2} ppm)",
                ],
                values=[bon, moyen, eleve],
                color_discrete_sequence=["#2ecc71", "#f39c12", "#e74c3c"],
                title="Sévérité du Confinement (Toutes Zones)",
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning("⚠️ Onglet 'CO2' introuvable ou ne contenant pas de données de zone.")


# =============================================================================
# ONGLET 4 : COV
# =============================================================================
with tab_v:
    st.subheader("Analyse des COV / Pollution Chimique (Onglet 'COV')")

    if not df_cov.empty and salles_cov:
        fig_cov = px.line(
            df_cov,
            x="Horodatage",
            y=salles_cov,
            title="Évolution des Composés Organiques Volatils (ppb)",
            labels={"value": "COV (ppb)", "variable": "Zone"},
        )
        fig_cov.add_hline(
            y=seuil_cov,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil d'Alerte ({seuil_cov} ppb)",
        )
        st.plotly_chart(fig_cov, use_container_width=True)

        col_v_left, col_v_right = st.columns(2)

        with col_v_left:
            st.markdown("#### Bilan par Zone")
            v_stats = []
            for col in salles_cov:
                v_stats.append(
                    {
                        "Zone / Salle": col,
                        "Moyenne (ppb)": int(df_cov[col].mean()),
                        "Max (ppb)": int(df_cov[col].max()),
                        f"Temps > {seuil_cov} ppb": f"{(df_cov[col] > seuil_cov).sum() * 0.25:.1f} h",
                        "Statut": "Conforme"
                        if df_cov[col].mean() < seuil_cov
                        else "Élevé",
                    }
                )
            st.dataframe(pd.DataFrame(v_stats), use_container_width=True)

        with col_v_right:
            st.markdown("#### Profil Moyen Journalier des COV")
            df_cov_hourly = (
                df_cov.groupby(df_cov["Horodatage"].dt.hour)[salles_cov]
                .mean()
                .mean(axis=1)
                .reset_index()
            )
            df_cov_hourly.columns = ["Heure", "COV_Moyen"]

            fig_hourly = px.bar(
                df_cov_hourly,
                x="Heure",
                y="COV_Moyen",
                labels={"Heure": "Heure de la journée", "COV_Moyen": "Moyenne (ppb)"},
                title="Variations moyennes selon l'heure",
            )
            st.plotly_chart(fig_hourly, use_container_width=True)
    else:
        st.warning("⚠️ Onglet 'COV' introuvable ou ne contenant pas de données de zone.")