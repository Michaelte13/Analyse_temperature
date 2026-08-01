import numpy as np
import pandas as pd
import streamlit as st

# ==============================================================================
# CONFIGURATION DE LA PAGE STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Rapport & Diagnostic Thermique Multi-Zones",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Diagnostic Thermique & Hydraulique (Analyse Données Brutes)")
st.caption(
    "Synthèse quantitative et explicative complète pour l'aide à l'analyse de vos courbes (Zones N, S, E, O, Aux 1-3 & Circuit Chaufferie)."
)

# ==============================================================================
# 1. FONCTIONS DE TRAITEMENT DES DONNÉES
# ==============================================================================


def parse_chaufferie(series):
    """Extrait T_Depart et T_Retour en gérant les formats (virgules, tirets, slashs)."""
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
            "Statut": "Actif" if actif else "Inactif",
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
        sub = df_quot[(df_quot["Jour"] == jour) & (df_quot["Statut"] == "Actif")]
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
            "Durée Moyenne (h)": dur_m,
            "Statut": statut,
        })

    return pd.DataFrame(synthese_hebdo), df_quot


def calculer_stats_periode(df_sub, zones):
    """Calcule les métriques clés de température et de confort pour un sous-ensemble de données."""
    stats = []
    for z in zones:
        vals = df_sub[z].dropna()
        if not vals.empty:
            stats.append({
                "Zone": z,
                "Min (°C)": round(vals.min(), 1),
                "Moyenne (°C)": round(vals.mean(), 1),
                "Max (°C)": round(vals.max(), 1),
                "Écart-type (°C)": round(vals.std(), 2),
                "Sous-chauffe <19°C (%)": round(
                    (vals < 19.0).mean() * 100, 1
                ),
                "Confort 19-22°C (%)": round(
                    ((vals >= 19.0) & (vals <= 22.0)).mean() * 100, 1
                ),
                "Surchauffe >22°C (%)": round((vals > 22.0).mean() * 100, 1),
            })
    return pd.DataFrame(stats)


# ==============================================================================
# 2. CHARGEMENT DES DONNÉES
# ==============================================================================
st.sidebar.header("📥 Fichier de Données")
uploaded_file = st.sidebar.file_uploader(
    "Téléverser votre fichier Excel ou CSV", type=["xlsx", "csv"]
)

if uploaded_file is not None:
    if uploaded_file.name.endswith(".xlsx"):
        df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    else:
        df_raw = pd.read_csv(uploaded_file)
else:
    st.sidebar.info("💡 Fichier de démonstration chargé (7 zones + chaufferie).")
    dates = pd.date_range("2026-03-02 00:00", "2026-03-08 23:45", freq="15min")
    n = len(dates)
    hours = dates.hour + dates.minute / 60.0
    is_work = (dates.weekday < 5) & (hours >= 8) & (hours < 18)

    t_ext = (
        5 + 4 * np.sin((hours - 9) * np.pi / 12) + np.random.normal(0, 0.4, n)
    )

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

    t_aux1 = t_nord - 1.8 + np.random.normal(0, 0.3, n)
    t_aux2 = t_nord + 0.3 + np.random.normal(0, 0.2, n)
    t_aux3 = t_nord + 2.1 + np.random.normal(0, 0.4, n)

    heating_on = (dates.weekday < 5) & (hours >= 5.5) & (hours < 18.5)
    t_dep = np.where(
        heating_on,
        56 - 1.3 * t_ext + np.random.normal(0, 0.7, n),
        20 + np.random.normal(0, 0.2, n),
    )
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
df = df.dropna(subset=[col_date]).sort_values(col_date).reset_index(drop=True)

# Traitement Chaufferie
cols_chaufferie = [
    c
    for c in df.columns
    if "chaufferie" in c.lower()
    or ("départ" in c.lower() and "retour" in c.lower())
]
col_chaufferie = cols_chaufferie[0] if cols_chaufferie else df.columns[-1]

df["T_Depart"], df["T_Retour"] = parse_chaufferie(df[col_chaufferie])
df["Delta_T"] = df["T_Depart"] - df["T_Retour"]

# Détection automatique de TOUTES les colonnes de zones
cols_exclues = [
    col_date,
    col_chaufferie,
    "T_Depart",
    "T_Retour",
    "Delta_T",
]
col_ext_candidates = [c for c in df.columns if "ext" in c.lower()]
if col_ext_candidates:
    cols_exclues.append(col_ext_candidates[0])

# Toutes les autres colonnes numériques sont traitées comme des zones
zones_détectées = [
    c
    for c in df.columns
    if c not in cols_exclues and pd.api.types.is_numeric_dtype(df[c])
]

# Définition des périodes temporelles
df["Jour_Semaine"] = df[col_date].dt.weekday
df["Heure_Dec"] = df[col_date].dt.hour + df[col_date].dt.minute / 60.0

is_occupation = (
    (df["Jour_Semaine"] < 5)
    & (df["Heure_Dec"] >= 8.0)
    & (df["Heure_Dec"] < 18.0)
)
is_inoccupation = ~is_occupation
is_chauffe_active = df["T_Depart"] > 30.0

# Synthese des horaires
df_synth_horaires, df_quot_horaires = analyser_horaires_chauffage(df, col_date)


# ==============================================================================
# 3. INTERFACE STREAMLIT - ANALYSE ET EXPLICATIONS
# ==============================================================================

# ------------------------------------------------------------------------------
# RESUME DU PERIMETRE DES DONNEES
# ------------------------------------------------------------------------------
st.info(
    f"📌 **Périmètre d'analyse complet** : **{len(df)} points de mesure** du **{df[col_date].min().strftime('%d/%m/%Y %H:%M')}** au **{df[col_date].max().strftime('%d/%m/%Y %H:%M')}**.\n\n"
    f"• **Zones identifiées ({len(zones_détectées)})** : {', '.join(zones_détectées)}\n\n"
    f"• **100% des pas de temps sont pris en compte** dans l'analyse globale ci-dessous."
)

st.markdown("---")

# ------------------------------------------------------------------------------
# SECTION 1 : DIAGNOSTIC HYDRAULIQUE ΔT (DEPART - RETOUR)
# ------------------------------------------------------------------------------
st.header("🔥 1. Diagnostic Hydraulique : Écart Départ - Retour (ΔT)")
st.write(
    """
    **Pourquoi cette valeur est essentielle pour votre analyse de courbe ?**  
    Le $\Delta T = T_{Départ} - T_{Retour}$ mesure la quantité de chaleur cédée par l'eau du réseau au bâtiment. 
    En comparant la courbe de départ et la courbe de retour sur votre graphique, observez l'écart vertical entre les deux tracés.
    """
)

dt_glob_moy = df["Delta_T"].mean()
dt_act_moy = (
    df.loc[is_chauffe_active, "Delta_T"].mean()
    if not df[is_chauffe_active].empty
    else 0.0
)
dt_act_min = (
    df.loc[is_chauffe_active, "Delta_T"].min()
    if not df[is_chauffe_active].empty
    else 0.0
)
dt_act_max = (
    df.loc[is_chauffe_active, "Delta_T"].max()
    if not df[is_chauffe_active].empty
    else 0.0
)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric(
    "T° Départ Moy. (En chauffe)",
    f"{df.loc[is_chauffe_active, 'T_Depart'].mean():.1f} °C",
)
col_m2.metric(
    "T° Retour Moy. (En chauffe)",
    f"{df.loc[is_chauffe_active, 'T_Retour'].mean():.1f} °C",
)
col_m3.metric("ΔT Moy. (Période Active)", f"{dt_act_moy:.1f} °C")
col_m4.metric("ΔT Min / Max (Active)", f"{dt_act_min:.1f} / {dt_act_max:.1f} °C")

# Analyse textuelle du régime hydraulique
st.subheader("💡 Diagnostic du Régime Hydraulique")

if dt_act_moy < 6.0:
    st.error(
        f"🔴 **Diagnostic : Sur-débit ou court-circuit hydraulique ($\Delta T = {dt_act_moy:.1f}^\circ\text{C}$)**\n\n"
        "**Ce que vous devez observer sur vos courbes :** La courbe de retour est presque collée à la courbe de départ.\n\n"
        "**Explication technique :** L'eau circule trop vite dans la boucle ou passe par une bouteille de mélange/vanne 3 voies sans irriguer correctement les émetteurs. "
        "L'eau revient trop chaude en chaufferie.\n\n"
        "**Conséquences :** Surconsommation électrique des pompes de circulation, impossibilité pour une chaudière à condensation ou une PAC de condenser efficacement."
    )
elif 6.0 <= dt_act_moy <= 15.0:
    st.success(
        f"🟢 **Diagnostic : Régime hydraulique équilibré ($\Delta T = {dt_act_moy:.1f}^\circ\text{C}$)**\n\n"
        "**Ce que vous devez observer sur vos courbes :** Un écart régulier et stable entre départ et retour (entre 6°C et 15°C).\n\n"
        "**Explication technique :** Le débit de la pompe est bien dimensionné par rapport à l'émission. Les radiateurs / planchers chauffants cèdent correctement leurs calories."
    )
else:
    st.warning(
        f"🟠 **Diagnostic : Sous-débit ou perte de charge excessive ($\Delta T = {dt_act_moy:.1f}^\circ\text{C}$)**\n\n"
        "**Ce que vous devez observer sur vos courbes :** Un très grand écart vertical entre la courbe de départ et de retour.\n\n"
        "**Explication technique :** L'eau met trop de temps à parcourir le réseau et refroidit excessivement avant de revenir en chaufferie.\n\n"
        "**Conséquences :** Risque fort de sous-chauffer les zones situées en bout de réseau (les radiateurs les plus éloignés sont froids)."
    )

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 2 : ANALYSE DES TEMPERATURES DE ZONES (TOUTES LES DONNEES)
# ------------------------------------------------------------------------------
st.header("🏢 2. Analyse Complète des Températures de Zones")
st.write(
    "Pour vous aider à interpréter vos courbes d'ambiance, les données ci-dessous prennent en compte **l'intégralité des enregistrements** découpés en 3 filtres distincts."
)

tab_occ, tab_inocc, tab_glob = st.tabs([
    "👔 Période d'Occupation (8h-18h, Lun-Ven)",
    "🌙 Période d'Inoccupation (Nuits & WE)",
    "🌐 Globale (24h/24 - 100% des données)",
])

with tab_occ:
    st.subheader("Statistiques en Période d'Occupation")
    df_stats_occ = calculer_stats_periode(df[is_occupation], zones_détectées)
    st.dataframe(df_stats_occ, use_container_width=True, hide_index=True)

with tab_inocc:
    st.subheader("Statistiques en Période d'Inoccupation / Réduit")
    df_stats_inocc = calculer_stats_periode(df[is_inoccupation], zones_détectées)
    st.dataframe(df_stats_inocc, use_container_width=True, hide_index=True)

with tab_glob:
    st.subheader("Statistiques Globales sur l'Ensemble de la Plage Temporelle")
    df_stats_glob = calculer_stats_periode(df, zones_détectées)
    st.dataframe(df_stats_glob, use_container_width=True, hide_index=True)

# Diagnostic détaillé zone par zone
st.subheader("🔍 Explications et Synthèse Zone par Zone")

if not df_stats_occ.empty:
    for _, row in df_stats_occ.iterrows():
        z_name = row["Zone"]
        tmoy_occ = row["Moyenne (°C)"]
        tmoy_inocc = (
            df_stats_inocc.loc[
                df_stats_inocc["Zone"] == z_name, "Moyenne (°C)"
            ].values[0]
            if not df_stats_inocc.empty
            else 0.0
        )
        sous_c = row["Sous-chauffe <19°C (%)"]
        sur_c = row["Surchauffe >22°C (%)"]

        with st.expander(
            f"📍 Zone : {z_name} — Moyenne Occupation : {tmoy_occ}°C | Inoccupation : {tmoy_inocc}°C",
            expanded=True,
        ):
            c_text1, c_text2 = st.columns(2)

            with c_text1:
                st.markdown("**Bilan de Confort (8h-18h)** :")
                st.write(
                    f"• Confort (19-22°C) : **{row['Confort 19-22°C (%)']}%**"
                )
                st.write(f"• Temps en sous-chauffe (<19°C) : **{sous_c}%**")
                st.write(f"• Temps en surchauffe (>22°C) : **{sur_c}%**")

            with c_text2:
                st.markdown("**Que vérifier sur vos courbes visuelles ?**")
                if sous_c > 15.0:
                    st.write(
                        f"❌ **Courbe trop basse** : La zone est sous-chauffée. Vérifiez sur la courbe si la montée en température du matin est trop lente (manque d'anticipation ou débit insuffisant sur cette zone)."
                    )
                elif sur_c > 15.0:
                    surconso = round((tmoy_occ - 19.0) * 7.0, 1)
                    st.write(
                        f"⚠️ **Courbe trop haute** : La courbe dépasse souvent 22°C. Surchauffe générant environ **+{surconso}%** de surconsommation. Observez si les apports solaires (Sud/Est) ou un problème d'équilibrage/thermostat en sont la cause."
                    )
                else:
                    st.write(
                        "🟢 **Courbe stable** : La température oscille bien dans la plage de confort recommandée."
                    )

                delta_reduit = round(tmoy_occ - tmoy_inocc, 1)
                st.write(
                    f"• **Écart Confort / Réduit** : **{delta_reduit} °C** de baisse moyenne la nuit. "
                    f"*(Si < 1.5°C : le réduit de nuit est mal appliqué sur cette zone. Si > 4°C : inertie faible ou déperditions fortes).* "
                )

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 3 : PLAGES HORAIRES DE CHAUFFAGE (FONCTIONNEMENT RÉEL)
# ------------------------------------------------------------------------------
st.header("🕒 3. Analyse de la Régulation Temporelle Chaufferie")
st.write(
    "Cette section analyse à quels moments la température de départ dépasse 30°C pour identifier la logique de régulation."
)

c_h1, c_h2 = st.columns([1, 1])

with c_h1:
    st.subheader("Synthèse Hebdomadaire")
    st.dataframe(df_synth_horaires, use_container_width=True, hide_index=True)

with c_h2:
    st.subheader("Explications pour l'Analyse des Courbes")
    st.markdown(
        """
        **Éléments à vérifier lors de la lecture de vos courbes :**
        
        1. **Heure d'anticipation le matin** :
           * Comparez l'heure de mise en route de la chaufferie avec l'heure à laquelle les zones atteignent 19°C.
           * Si la température de zone atteint 19°C seulement à 10h du matin, la relance doit être anticipée plus tôt.
        
        2. **Coupure anticipée le soir** :
           * Vérifiez si la chaufferie s'arrête vers 16h-17h sans impacter le confort des occupants avant 18h (utilisation de l'inertie du bâtiment).
        
        3. **Fonctionnement le Week-End** :
           * Si les jours de week-end affichent le statut **Actif**, vérifiez sur vos courbes s'il s'agit d'un maintien de réduit hors gel ou d'un chauffage inutile à température de confort.
        """
    )

with st.expander("📅 Voir le détail quotidien d'activation de la chaufferie"):
    st.dataframe(df_quot_horaires, use_container_width=True, hide_index=True)

st.markdown("---")


# ------------------------------------------------------------------------------
# SECTION 4 : GUIDE D'AIDE À LA LECTURE MANUELLE DE VOS COURBES
# ------------------------------------------------------------------------------
st.header("💡 4. Guide Pratique pour Analyser vos Courbes Visuelles")

st.markdown(
    """
Sur la base des résultats chiffrés ci-dessus, voici la méthodologie pas à pas pour contrôler vos graphiques :

### Step 1 : Comparer l'orientation des zones (N, S, E, O)
* **Zones Nord & Auxiliaires défavorisées** : Vérifiez sur votre courbe si ces zones restent systématiquement sous le plateau des autres zones. Si oui, l'équilibrage du réseau est à revoir (augmenter le débit sur ces antennes).
* **Zones Sud & Est** : Recherchez les pics de température l'après-midi ou le matin. Si la courbe monte au-delà de 23°C alors que le chauffage tourne, la régulation ne prend pas en compte les **apports gratuits solaires** (besoin de sondes d'ambiance ou de robinets thermostatiques).

### Step 2 : Analyser la pente des courbes de chaufferie
* **Loi d'eau** : Comparez la courbe de départ chaufferie avec la courbe de température extérieure. Lorsque la température extérieure chute, la température de départ doit monter proportionnellement.
* **Cycles courts (Pompage / Oscillations)** : Si la courbe de départ fait des "dents de scie" très rapprochées (montées et descentes en moins de 15 min), la chaudière ou la pompe est en sur-puissance par rapport au besoin réel.

### Step 3 : Valider le comportement global des zones Aux 1, Aux 2, Aux 3
* Comparez l'écart permanent entre la zone la plus chaude et la zone la plus froide. Si cet écart dépasse **3°C à 4°C** au même instant t, le réseau hydraulique présente un défaut d'équilibrage majeur.
"""
)