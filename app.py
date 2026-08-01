# -*- coding: utf-8 -*-
"""
Application Streamlit d'Audit Énergétique & Qualité de l'Air Intérieur (QAI)
Analyses Automatisées & Filtres par Taux et Variations
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
    page_title="Audit Énergétique & QAI - Analyses Automatisées",
    page_icon="⚡",
    layout="wide",
)

# -----------------------------------------------------------------------------
# 1. NETTOYAGE ET CHARGEMENT DES DONNÉES
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

    # Conservation des colonnes non vides
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
    """Génère 4 feuillets de démo si aucun fichier n'est chargé."""
    start_date = datetime(2026, 3, 11, 16, 45)
    dates = [
        start_date + timedelta(minutes=15 * i) for i in range(15 * 24 * 4)
    ]
    salles = ["Nord", "Est", "Sud", "Aux 1", "Aux 2"]

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
# 2. BARRE LATÉRALE : FILTRES ET CURSEURS D'ANALYSE
# -----------------------------------------------------------------------------

st.sidebar.title("🛠️ Paramètres & Curseurs")

uploaded_file = st.sidebar.file_uploader(
    "Fichier de mesures (Excel multi-onglets)", type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:
    data_dict = load_data(uploaded_file)
    st.sidebar.success("Fichier chargé avec succès !")
else:
    st.sidebar.info("Utilisation des données de démo.")
    data_dict = generate_synthetic_data()

# Extraction des bornes temporelles
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

# Filtre Heures d'occupation
st.sidebar.markdown("---")
st.sidebar.subheader("🕒 Horaires d'Occupation")
filtre_occupation = st.sidebar.checkbox(
    "Filtrer uniquement pendant l'occupation (08h - 18h)", value=False
)

# Application des filtres de date et d'heure
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_filter, end_filter = date_range
    for key in data_dict:
        if not data_dict[key].empty and "Horodatage" in data_dict[key].columns:
            df_curr = data_dict[key]
            cond = (df_curr["Horodatage"].dt.date >= start_filter) & (
                df_curr["Horodatage"].dt.date <= end_filter
            )
            if filtre_occupation:
                cond = cond & (df_curr["Horodatage"].dt.hour.between(8, 18))
            data_dict[key] = df_curr[cond]

# --- CURSEURS POUR L'ANALYSE ET SEUILS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Curseurs & Seuils d'Analyse")

# Température
with st.sidebar.expander("🌡️ Température & Chutes", expanded=True):
    t_min_confort = st.slider(
        "T° Min Confort (°C)", 16.0, 22.0, 19.0, step=0.5
    )
    t_max_confort = st.slider(
        "T° Max Confort (°C)", 20.0, 26.0, 22.0, step=0.5
    )
    seuil_chute_temp = st.slider(
        "Chute rapide de T° (°C / heure)", 0.5, 4.0, 1.5, step=0.1
    )

# Humidité
with st.sidebar.expander("💧 Humidité & Variations", expanded=False):
    hr_min_confort = st.slider("Humidité Min (%)", 20, 50, 40, step=5)
    hr_max_confort = st.slider("Humidité Max (%)", 50, 80, 60, step=5)
    seuil_choc_hum = st.slider(
        "Variation rapide d'Humidité (% / 1h)", 5, 25, 10, step=1
    )

# Qualité de l'air (CO2 & COV)
with st.sidebar.expander("🟢 CO2 & 🧪 COV", expanded=False):
    seuil_co2 = st.slider("Seuil Alerte CO2 (ppm)", 800, 2000, 1000, step=50)
    seuil_cov = st.slider("Seuil Alerte COV (ppb)", 100, 500, 200, step=10)
    seuil_pic_percent = st.slider(
        "Seuil de Pic de Pollution (% au-dessus de la moy.)",
        20,
        200,
        50,
        step=10,
    )


# -----------------------------------------------------------------------------
# 3. EXTRACTION DES DONNÉES ET DÉTECTION DES ANOMALIES
# -----------------------------------------------------------------------------

df_temp = data_dict.get("Température", pd.DataFrame())
df_hum = data_dict.get("Humidité", pd.DataFrame())
df_co2 = data_dict.get("CO2", pd.DataFrame())
df_cov = data_dict.get("COV", pd.DataFrame())


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

# --- CALCUL DES ANOMALIES AUTOMATIQUES ---
chutes_temp_detectees = []
if not df_temp.empty and salles_temp:
    for s in salles_temp:
        # Différence sur 1h (4 pas de 15 min)
        diff_1h = df_temp[s].diff(4)
        nb_chutes = (diff_1h <= -seuil_chute_temp).sum()
        if nb_chutes > 0:
            chutes_temp_detectees.append((s, nb_chutes))

pct_co2_depasse = 0
if not df_co2.empty and salles_co2:
    vals_co2 = df_co2[salles_co2].values.flatten()
    vals_co2 = vals_co2[~np.isnan(vals_co2)]
    if len(vals_co2) > 0:
        pct_co2_depasse = (vals_co2 > seuil_co2).mean() * 100

pct_cov_depasse = 0
if not df_cov.empty and salles_cov:
    vals_cov = df_cov[salles_cov].values.flatten()
    vals_cov = vals_cov[~np.isnan(vals_cov)]
    if len(vals_cov) > 0:
        pct_cov_depasse = (vals_cov > seuil_cov).mean() * 100


# -----------------------------------------------------------------------------
# 4. EN-TÊTE ET DIAGNOSTIC AUTOMATIQUE D'ALERTE
# -----------------------------------------------------------------------------

st.title("⚡ Audit Énergétique & QAI — Diagnostic Automatisé")

# Bandeau de synthèse automatique
with st.container():
    st.subheader("🚨 Synthèse Automatique des Anomalies & Taux")
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)

    # 1. Chutes de Température
    total_chutes = sum(count for _, count in chutes_temp_detectees)
    if total_chutes > 0:
        col_a1.metric(
            "Chutes de T° Brutales",
            f"{total_chutes} évènements",
            delta=f"📉 > {seuil_chute_temp}°C/h",
            delta_color="inverse",
        )
    else:
        col_a1.metric(
            "Chutes de T° Brutales",
            "0 détectée",
            delta="✅ Stable",
            delta_color="normal",
        )

    # 2. Taux d'inconfort Thermique
    if not df_temp.empty and salles_temp:
        vals_t = df_temp[salles_temp].values.flatten()
        vals_t = vals_t[~np.isnan(vals_t)]
        pct_inconfort_t = (
            ((vals_t < t_min_confort) | (vals_t > t_max_confort)).mean() * 100
            if len(vals_t) > 0
            else 0
        )
        col_a2.metric(
            "Inconfort Thermique",
            f"{pct_inconfort_t:.1f} % du temps",
            delta=f"Plage: {t_min_confort}-{t_max_confort}°C",
            delta_color="inverse" if pct_inconfort_t > 15 else "normal",
        )
    else:
        col_a2.metric("Inconfort Thermique", "N/A")

    # 3. Taux d'inconfort CO2
    col_a3.metric(
        "Dépassement CO2",
        f"{pct_co2_depasse:.1f} % du temps",
        delta=f"> {seuil_co2} ppm",
        delta_color="inverse" if pct_co2_depasse > 10 else "normal",
    )

    # 4. Taux d'inconfort COV
    col_a4.metric(
        "Dépassement COV",
        f"{pct_cov_depasse:.1f} % du temps",
        delta=f"> {seuil_cov} ppb",
        delta_color="inverse" if pct_cov_depasse > 10 else "normal",
    )

st.divider()

# -----------------------------------------------------------------------------
# 5. ONGLETS DE DÉTAIL DES ANALYSES
# -----------------------------------------------------------------------------

tab_t, tab_h, tab_c, tab_v = st.tabs(
    [
        "🌡️ 1. Température & Chutes",
        "💧 2. Humidité & Chocs",
        "🟢 3. Confinement CO2",
        "🧪 4. Pollution COV",
    ]
)

# =============================================================================
# ONGLET 1 : TEMPÉRATURE & CHUTES RAPIDES
# =============================================================================
with tab_t:
    st.subheader("📊 Analyse Thermique & Détection des Pertes de Chaleur")

    if not df_temp.empty and salles_temp:
        # Visualisation principale
        fig_temp = go.Figure()

        if "T_ext" in df_temp.columns:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["T_ext"],
                    name="T° Extérieure",
                    line=dict(color="#3498db", dash="dash"),
                )
            )

        if "V3V_Depart" in df_temp.columns:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp["V3V_Depart"],
                    name="Départ Eau V3V",
                    line=dict(color="#e74c3c"),
                )
            )

        for s in salles_temp:
            fig_temp.add_trace(
                go.Scatter(
                    x=df_temp["Horodatage"],
                    y=df_temp[s],
                    name=f"Zone {s}",
                    opacity=0.8,
                )
            )

        fig_temp.add_hline(
            y=t_min_confort,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"Min ({t_min_confort}°C)",
        )
        fig_temp.add_hline(
            y=t_max_confort,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Max ({t_max_confort}°C)",
        )

        fig_temp.update_layout(
            xaxis_title="Date / Heure",
            yaxis_title="Température (°C)",
            height=420,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.markdown("#### 📉 Détection Automatique des Chutes Rapides")
            st.caption(
                f"Détecte les baisses de plus de **{seuil_chute_temp}°C en 1h** (ex: fenêtres ouvertes / pannes)."
            )

            chute_data = []
            for s in salles_temp:
                diff_1h = df_temp[s].diff(4)
                chutes_idx = df_temp[diff_1h <= -seuil_chute_temp]
                for idx, row in chutes_idx.iterrows():
                    val_diff = diff_1h.loc[idx]
                    chute_data.append(
                        {
                            "Date / Heure": row["Horodatage"].strftime(
                                "%d/%m/%Y %H:%M"
                            ),
                            "Zone": s,
                            "T° Actuelle": f"{row[s]:.1f} °C",
                            "Variation sur 1h": f"{val_diff:.1f} °C",
                        }
                    )

            if chute_data:
                st.dataframe(pd.DataFrame(chute_data), use_container_width=True)
            else:
                st.success(
                    f"✅ Aucune chute rapide (> {seuil_chute_temp}°C/h) n'a été détectée."
                )

        with col_t2:
            st.markdown("#### 📊 Taux de Conformité Thermique par Zone")
            t_stats = []
            for col in salles_temp:
                t_moy = df_temp[col].mean()
                pct_sous = (df_temp[col] < t_min_confort).mean() * 100
                pct_sur = (df_temp[col] > t_max_confort).mean() * 100
                pct_ok = 100 - pct_sous - pct_sur

                t_stats.append(
                    {
                        "Zone": col,
                        "Moyenne": f"{t_moy:.1f} °C",
                        "% Confort OK": f"{pct_ok:.1f} %",
                        "% Sous-chauffe": f"{pct_sous:.1f} %",
                        "% Sur-chauffe": f"{pct_sur:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(t_stats), use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée de température disponible.")


# =============================================================================
# ONGLET 2 : HUMIDITÉ & VARIATIONS
# =============================================================================
with tab_h:
    st.subheader("📊 Analyse Hygrométrique & Chocs d'Humidité")

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
            annotation_text=f"Min ({hr_min_confort}%)",
        )
        fig_hum.add_hline(
            y=hr_max_confort,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Max ({hr_max_confort}%)",
        )
        st.plotly_chart(fig_hum, use_container_width=True)

        col_h1, col_h2 = st.columns(2)

        with col_h1:
            st.markdown("#### ⚡ Variations Brutales d'Humidité (>1h)")
            choc_hum_data = []
            for s in salles_hum:
                diff_1h = df_hum[s].diff(4).abs()
                chocs = df_hum[diff_1h >= seuil_choc_hum]
                for idx, row in chocs.iterrows():
                    v_diff = df_hum[s].diff(4).loc[idx]
                    choc_hum_data.append(
                        {
                            "Date / Heure": row["Horodatage"].strftime(
                                "%d/%m/%Y %H:%M"
                            ),
                            "Zone": s,
                            "Humidité": f"{row[s]:.1f} %",
                            "Variation (1h)": f"{v_diff:+.1f} %",
                        }
                    )

            if choc_hum_data:
                st.dataframe(
                    pd.DataFrame(choc_hum_data), use_container_width=True
                )
            else:
                st.success(
                    f"✅ Aucune variation supérieure à {seuil_choc_hum}% en 1h."
                )

        with col_h2:
            st.markdown("#### 📈 Bilan du Taux d'Humidité")
            h_stats = []
            for col in salles_hum:
                pct_sec = (df_hum[col] < hr_min_confort).mean() * 100
                pct_humide = (df_hum[col] > hr_max_confort).mean() * 100
                pct_ok = 100 - pct_sec - pct_humide
                h_stats.append(
                    {
                        "Zone": col,
                        "Moyenne": f"{df_hum[col].mean():.1f} %",
                        "% Conforme": f"{pct_ok:.1f} %",
                        "% Trop Sec": f"{pct_sec:.1f} %",
                        "% Trop Humide": f"{pct_humide:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(h_stats), use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée d'humidité disponible.")


# =============================================================================
# ONGLET 3 : CO2 & CONFINEMENT AUTOMATISÉ
# =============================================================================
with tab_c:
    st.subheader("📊 Analyse du Confinement et Renouvellement d'Air (CO2)")

    if not df_co2.empty and salles_co2:
        fig_co2 = px.line(
            df_co2,
            x="Horodatage",
            y=salles_co2,
            title="Niveaux de CO2 (ppm)",
            labels={"value": "CO2 (ppm)", "variable": "Zone"},
        )
        fig_co2.add_hline(
            y=seuil_co2,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil Alerte ({seuil_co2} ppm)",
        )
        st.plotly_chart(fig_co2, use_container_width=True)

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("#### 🚨 Taux de Dépassement par Zone")
            c_stats = []
            for col in salles_co2:
                pct_dep = (df_co2[col] > seuil_co2).mean() * 100
                pic_max = df_co2[col].max()
                moyenne = df_co2[col].mean()

                c_stats.append(
                    {
                        "Zone": col,
                        "Moyenne": f"{int(moyenne)} ppm",
                        "Pic Max": f"{int(pic_max)} ppm",
                        f"% Temps > {seuil_co2} ppm": f"{pct_dep:.1f} %",
                        "Diagnostic Ventilation": "⚠️ Insuffisante"
                        if pct_dep > 15
                        else "✅ Correcte",
                    }
                )
            st.dataframe(pd.DataFrame(c_stats), use_container_width=True)

        with col_c2:
            st.markdown("#### 🏆 Indice de Confinement (Sévérité)")
            co2_vals_clean = df_co2[salles_co2].values.flatten()
            co2_vals_clean = co2_vals_clean[~np.isnan(co2_vals_clean)]

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
                title="Répartition des heures de présence",
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée de CO2 disponible.")


# =============================================================================
# ONGLET 4 : COV & PICS DE POLLUTION
# =============================================================================
with tab_v:
    st.subheader("📊 Analyse des Composés Organiques Volatils (COV)")

    if not df_cov.empty and salles_cov:
        fig_cov = px.line(
            df_cov,
            x="Horodatage",
            y=salles_cov,
            title="Composés Organiques Volatils (ppb)",
            labels={"value": "COV (ppb)", "variable": "Zone"},
        )
        fig_cov.add_hline(
            y=seuil_cov,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Seuil ({seuil_cov} ppb)",
        )
        st.plotly_chart(fig_cov, use_container_width=True)

        col_v1, col_v2 = st.columns(2)

        with col_v1:
            st.markdown("#### 🧪 Détection des Pics de Pollution")
            st.caption(
                f"Recherche des valeurs dépassant la moyenne de la zone de plus de **+{seuil_pic_percent}%**."
            )

            pics_cov = []
            for s in salles_cov:
                moy_zone = df_cov[s].mean()
                seuil_pic = moy_zone * (1 + seuil_pic_percent / 100)
                df_pics = df_cov[df_cov[s] >= seuil_pic]

                for idx, row in df_pics.iterrows():
                    pics_cov.append(
                        {
                            "Date / Heure": row["Horodatage"].strftime(
                                "%d/%m/%Y %H:%M"
                            ),
                            "Zone": s,
                            "Valeur COV": f"{int(row[s])} ppb",
                            "Écart / Moyenne": f"+{((row[s]/moy_zone)-1)*100:.0f} %",
                        }
                    )

            if pics_cov:
                st.dataframe(
                    pd.DataFrame(pics_cov).head(20), use_container_width=True
                )
            else:
                st.success("✅ Aucun pic soudain de COV n'a été détecté.")

        with col_v2:
            st.markdown("#### 📋 Synthèse COV par Zone")
            v_stats = []
            for col in salles_cov:
                pct_dep = (df_cov[col] > seuil_cov).mean() * 100
                v_stats.append(
                    {
                        "Zone": col,
                        "Moyenne": f"{int(df_cov[col].mean())} ppb",
                        "Max": f"{int(df_cov[col].max())} ppb",
                        f"% > {seuil_cov} ppb": f"{pct_dep:.1f} %",
                    }
                )
            st.dataframe(pd.DataFrame(v_stats), use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée de COV disponible.")