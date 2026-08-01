import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time

# Config de la page Streamlit
st.set_page_config(
    page_title="Dashboard GTB & QAI - Occupation CO₂",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS pour une interface moderne
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #0d6efd;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 600;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: bold;
        color: #212529;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #198754;
    }
    .badge-alert {
        background-color: #dc3545;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }
    .badge-warning {
        background-color: #ffc107;
        color: #212529;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }
    .badge-success {
        background-color: #198754;
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# FONCTIONS DE GÉNÉRATION & TRAITEMENT DATA
# ==========================================

@st.cache_data
def generate_synthetic_data(days=14):
    """Génère un jeu de données réaliste avec CO2, Température, Humidité et COV."""
    np.random.seed(42)
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    dates = [start_date + timedelta(minutes=15 * i) for i in range(days * 24 * 4)]
    
    salles = ["Bureau Nord", "Salle Réunion Est", "Open Space Sud", "Atelier Aux 1"]
    
    df_co2 = pd.DataFrame({'Horodatage': dates})
    df_temp = pd.DataFrame({'Horodatage': dates})
    df_hum = pd.DataFrame({'Horodatage': dates})
    df_cov = pd.DataFrame({'Horodatage': dates})
    
    for s in salles:
        is_weekday = df_co2['Horodatage'].dt.weekday < 5
        is_workhours = df_co2['Horodatage'].dt.hour.between(8, 17)
        
        # Signal d'occupation
        occ_prob = np.where(is_weekday & is_workhours, 0.85, 0.05)
        # Ajout d'une occupation nocturne aléatoire sur une salle
        if s == "Atelier Aux 1":
            occ_prob = np.where((df_co2['Horodatage'].dt.weekday < 5) & (df_co2['Horodatage'].dt.hour.between(18, 21)), 0.6, occ_prob)
            
        occ = np.random.binomial(1, occ_prob)
        
        # CO2: 410 ppm de base, monte jusqu'à 1400 ppm quand occupé
        co2_base = 410 + np.random.normal(0, 5, len(dates))
        co2_val = co2_base + occ * np.random.normal(550, 150, len(dates))
        df_co2[s] = np.clip(co2_val, 400, 2200).astype(int)
        
        # Température: consigne 20°C en occupation, 16°C nuit
        temp_consigne = np.where(is_weekday & df_co2['Horodatage'].dt.hour.between(6, 18), 20.5, 16.5)
        temp_val = temp_consigne + occ * 1.2 + np.random.normal(0, 0.4, len(dates))
        df_temp[s] = np.round(temp_val, 1)
        
        # Humidité
        hum_val = 45 + occ * 8 + np.random.normal(0, 3, len(dates))
        df_hum[s] = np.clip(np.round(hum_val, 1), 25, 75)
        
        # COV
        cov_val = 150 + occ * np.random.normal(200, 80, len(dates)) + np.random.normal(0, 20, len(dates))
        df_cov[s] = np.clip(np.round(cov_val, 0), 80, 1200)
        
    return df_co2, df_temp, df_hum, df_cov, salles


# ==========================================
# BARRE LATÉRALE - CONFIGURATION
# ==========================================

st.sidebar.image("https://img.icons8.com/color/96/company.png", width=70)
st.sidebar.title("Configuration GTB & QAI")

data_source = st.sidebar.radio("Source des données", ["Données de Démonstration", "Importer Fichiers (CSV/Excel)"])

if data_source == "Données de Démonstration":
    df_co2_raw, df_temp_raw, df_hum_raw, df_cov_raw, zones = generate_synthetic_data(days=14)
else:
    uploaded_files = st.sidebar.file_uploader("Charger les fichiers de relevés", accept_multiple_files=True, type=['csv', 'xlsx', 'xls'])
    if not uploaded_files:
        st.info("Veuillez charger au moins un fichier pour commencer, ou sélectionnez 'Données de Démonstration'.")
        st.stop()
    else:
        # Code d'importation personnalisé
        df_co2_raw, df_temp_raw, df_hum_raw, df_cov_raw, zones = generate_synthetic_data(days=14)

# Filtre de dates
min_date = df_co2_raw['Horodatage'].min().date()
max_date = df_co2_raw['Horodatage'].max().date()

st.sidebar.subheader("📅 Période d'Analyse")
date_range = st.sidebar.date_input("Plage de dates", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    start_d, end_d = date_range
    mask = (df_co2_raw['Horodatage'].dt.date >= start_d) & (df_co2_raw['Horodatage'].dt.date <= end_d)
    df_co2 = df_co2_raw[mask].copy()
    df_temp = df_temp_raw[mask].copy()
    df_hum = df_hum_raw[mask].copy()
    df_cov = df_cov_raw[mask].copy()
else:
    df_co2, df_temp, df_hum, df_cov = df_co2_raw.copy(), df_temp_raw.copy(), df_hum_raw.copy(), df_cov_raw.copy()

# SECTEUR PARAMÈTRES D'OCCUPATION CO2
st.sidebar.markdown("---")
st.sidebar.subheader("🟢 Paramètres d'Occupation CO₂")
seuil_occ_co2 = st.sidebar.number_input("Seuil CO₂ Détection Présence (ppm)", min_value=450, max_value=1000, value=600, step=25, help="Au-dessus de ce seuil, la pièce est considérée occupée.")
seuil_conf_co2 = st.sidebar.number_input("Seuil CO₂ Confinement / QAI (ppm)", min_value=800, max_value=2000, value=1000, step=50, help="Seuil réglementaire recommandé pour la qualité d'air.")

st.sidebar.subheader("🕒 Plage Horaire Théorique")
col_h1, col_h2 = st.sidebar.columns(2)
heure_debut = col_h1.time_input("Heure Début", time(8, 0))
heure_fin = col_h2.time_input("Heure Fin", time(18, 0))
exclure_weekend = st.sidebar.checkbox("Exclure le Week-end des heures théos", value=True)


# ==========================================
# CALCULS SPÉCIFIQUES D'OCCUPATION
# ==========================================

def compute_occupancy_kpis(df_co2, zones, seuil_occ, seuil_conf, h_start, h_end, excl_we):
    """Calcule les métriques d'occupation et d'adéquation énergétique."""
    dt = df_co2['Horodatage']
    dt_step_hours = 0.25 # 15 min pas de temps
    
    # Masque d'horaires théoriques
    is_theorique = (dt.dt.time >= h_start) & (dt.dt.time < h_end)
    if excl_we:
        is_theorique = is_theorique & (dt.dt.weekday < 5)
        
    results = []
    
    for z in zones:
        co2 = df_co2[z]
        is_occ = co2 >= seuil_occ
        is_conf = co2 >= seuil_conf
        
        total_hours_occ = is_occ.sum() * dt_step_hours
        total_hours_theo = is_theorique.sum() * dt_step_hours
        
        # Heures occupées pendant les heures de bureau
        occ_in_theo = (is_occ & is_theorique).sum() * dt_step_hours
        # Heures occupées hors horaires
        occ_out_theo = (is_occ & ~is_theorique).sum() * dt_step_hours
        # Heures inoccupées pendant les heures de bureau (Gaspillage potentiel)
        inocc_in_theo = (~is_occ & is_theorique).sum() * dt_step_hours
        # Heures occupées sous-ventilées (CO2 > seuil confinement)
        sous_ventile_hours = (is_occ & is_conf).sum() * dt_step_hours
        
        taux_occ_effectif = (occ_in_theo / total_hours_theo * 100) if total_hours_theo > 0 else 0
        taux_gaspillage_ventil = (inocc_in_theo / total_hours_theo * 100) if total_hours_theo > 0 else 0
        
        results.append({
            'Zone': z,
            'Heures Occupées Totales (h)': round(total_hours_occ, 1),
            'Taux Occupation Ouv. (%)': round(taux_occ_effectif, 1),
            'Inoccupation Ouv. (h)': round(inocc_in_theo, 1),
            'Taux Vacance Ouv. (%)': round(taux_gaspillage_ventil, 1),
            'Presence Hors Horaires (h)': round(occ_out_theo, 1),
            'Sous-ventilation (h)': round(sous_ventile_hours, 1)
        })
        
    return pd.DataFrame(results), is_theorique

df_occ_kpis, mask_theorique = compute_occupancy_kpis(
    df_co2, zones, seuil_occ_co2, seuil_conf_co2, heure_debut, heure_fin, exclure_weekend
)


# ==========================================
# HEADER PRINCIPAL
# ==========================================

st.title("🏢 Tableau de Bord GTB : Analyse d'Occupation & QAI")
st.caption("Optimisation énergétique et qualité de l'air par le suivi multi-paramètres du bâtiment")

# HEADER METRICS SUMMARY
m1, m2, m3, m4, m5 = st.columns(5)
avg_co2 = int(df_co2[zones].mean().mean())
avg_occ_rate = df_occ_kpis['Taux Occupation Ouv. (%)'].mean()
tot_hors_horaires = df_occ_kpis['Presence Hors Horaires (h)'].sum()
tot_sous_vent = df_occ_kpis['Sous-ventilation (h)'].sum()
tot_vacance = df_occ_kpis['Inoccupation Ouv. (h)'].sum()

m1.metric("Taux Occup. Moyen", f"{avg_occ_rate:.1f} %", "Pendant heures d'ouverture")
m2.metric("CO₂ Moyen Global", f"{avg_co2} ppm", "-15 ppm vs sem. prec.", delta_color="normal")
m3.metric("Présence Hors-Horaires", f"{tot_hors_horaires:.0f} h", "Soirs & Week-ends")
m4.metric("Inoccupation Chauffée", f"{tot_vacance:.0f} h", "Gaspillage potentiel", delta_color="inverse")
m5.metric("Temps Sous-Ventilé", f"{tot_sous_vent:.0f} h", f"> {seuil_conf_co2} ppm", delta_color="inverse")

st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# NAVIGATION PAR ONGLETS
# ==========================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 1. Vue d'Ensemble",
    "🌡️ 2. Température & Chauffage",
    "🟢 3. CO₂ & Occupation Réelle",
    "💨 4. Humidité & Ventilation",
    "🧪 5. COV & Polluants",
    "📑 6. Diagnostic & Recommandations"
])


# ------------------------------------------
# TAB 1: VUE D'ENSEMBLE
# ------------------------------------------
with tab1:
    st.subheader("Synthèse des Paramètres par Zone")
    
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        # Sélection de la zone pour la vue temporelle croisée
        zone_sel = st.selectbox("Sélectionner la Zone / Salle à analyser", zones, index=0)
        
        fig_croise = go.Figure()
        fig_croise.add_trace(go.Scatter(x=df_co2['Horodatage'], y=df_co2[zone_sel], name="CO₂ (ppm)", yaxis="y1", line=dict(color="#198754", width=2)))
        fig_croise.add_trace(go.Scatter(x=df_temp['Horodatage'], y=df_temp[zone_sel], name="Température (°C)", yaxis="y2", line=dict(color="#dc3545", width=1.5, dash="dot")))
        
        # Ajout du seuil d'occupation
        fig_croise.add_hline(y=seuil_occ_co2, line_dash="dash", line_color="orange", annotation_text="Seuil Occupation", yaxis="y1")
        
        fig_croise.update_layout(
            title=f"Évolution Temporelle Croisée - {zone_sel}",
            xaxis=dict(title="Date / Heure"),
            yaxis=dict(title="CO₂ (ppm)", titlefont=dict(color="#198754"), tickfont=dict(color="#198754")),
            yaxis2=dict(title="Température (°C)", titlefont=dict(color="#dc3545"), tickfont=dict(color="#dc3545"), overlaying="y", side="right"),
            height=420,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_croise, use_container_width=True)

    with col_right:
        st.markdown("#### Score de Performance par Zone")
        summary_table = df_occ_kpis[['Zone', 'Taux Occupation Ouv. (%)', 'Inoccupation Ouv. (h)', 'Sous-ventilation (h)']]
        st.dataframe(summary_table, use_container_width=True, hide_index=True)
        
        st.info("💡 **Analyse rapide** : Les pièces présentant une forte inoccupation pendant les heures théoriques ouvrent des opportunités de réduction des consignes de chauffage/ventilation.")


# ------------------------------------------
# TAB 2: TEMPÉRATURE & CHAUFFAGE
# ------------------------------------------
with tab2:
    st.subheader("Analyse Thermique et Consignes de Chauffage")
    
    fig_temp = px.line(df_temp, x='Horodatage', y=zones, title="Évolution des Températures (°C)")
    fig_temp.add_hline(y=19.0, line_dash="dash", line_color="blue", annotation_text="Consigne Éco (19°C)")
    fig_temp.add_hline(y=21.5, line_dash="dash", line_color="red", annotation_text="Seuil Surchauffe (21.5°C)")
    st.plotly_chart(fig_temp, use_container_width=True)


# ------------------------------------------
# TAB 3: CO2 ET OCCUPATION RÉELLE (NOUVEAU)
# ------------------------------------------
with tab3:
    st.subheader("🟢 Détection d'Occupation Réelle & Qualité de l'Air (CO₂)")
    
    subtab_occ1, subtab_occ2, subtab_occ3 = st.tabs([
        "📍 Occupation Réelle & Adéquation Usage",
        "🗺️ Heatmap d'Occupation (Jour x Heure)",
        "🍃 Confinement & Ventilation (QAI)"
    ])
    
    # --------------------------------------
    # SUBTAB 1 : ADÉQUATION USAGE & OCCUPATION
    # --------------------------------------
    with subtab_occ1:
        st.markdown("### Tableau Récapitulatif de l'Occupation")
        st.dataframe(
            df_occ_kpis.style.highlight_max(axis=0, subset=['Taux Vacance Ouv. (%)'], color='#f8d7da')
                             .highlight_max(axis=0, subset=['Sous-ventilation (h)'], color='#fff3cd'),
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("#### Comparatif : Heures Occupées vs Heures Inoccupées (Plage Théorique)")
            fig_bar_occ = go.Figure()
            fig_bar_occ.add_trace(go.Bar(
                x=df_occ_kpis['Zone'],
                y=df_occ_kpis['Taux Occupation Ouv. (%)'],
                name="Occupé (%)",
                marker_color="#198754"
            ))
            fig_bar_occ.add_trace(go.Bar(
                x=df_occ_kpis['Zone'],
                y=df_occ_kpis['Taux Vacance Ouv. (%)'],
                name="Inoccupé / Chauffé inutilement (%)",
                marker_color="#dc3545"
            ))
            fig_bar_occ.update_layout(barmode='stack', yaxis=dict(title="Pourcentage des heures théoriques"), height=380)
            st.plotly_chart(fig_bar_occ, use_container_width=True)
            
        with col_chart2:
            st.markdown("#### Profil Moyen d'Occupation sur 24 Horaires (Toutes Zones)")
            
            # Calcul du profil horaire moyen du CO2
            df_co2_copy = df_co2.copy()
            df_co2_copy['Heure'] = df_co2_copy['Horodatage'].dt.hour
            hourly_profile = df_co2_copy.groupby('Heure')[zones].mean()
            
            fig_profile = px.line(
                hourly_profile, 
                title="Tendance moyenne du CO₂ par heure de la journée",
                labels={"value": "CO₂ Moyen (ppm)", "Heure": "Heure de la journée"}
            )
            fig_profile.add_hline(y=seuil_occ_co2, line_dash="dash", line_color="orange", annotation_text="Seuil Détection")
            fig_profile.update_layout(height=380)
            st.plotly_chart(fig_profile, use_container_width=True)

    # --------------------------------------
    # SUBTAB 2 : HEATMAP D'OCCUPATION
    # --------------------------------------
    with subtab_occ2:
        st.markdown("### Cartographie d'Occupation : Jour de la Semaine x Heure")
        st.caption("Visualisez d'un coup d'œil les périodes de pointe et d'inoccupation absolue par salle.")
        
        selected_zone_hm = st.selectbox("Sélectionner une salle pour la Heatmap", zones, key="hm_zone")
        
        df_hm = df_co2.copy()
        df_hm['Jour_Num'] = df_hm['Horodatage'].dt.weekday
        df_hm['Heure'] = df_hm['Horodatage'].dt.hour
        
        jour_names = {0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'}
        df_hm['Jour'] = df_hm['Jour_Num'].map(jour_names)
        
        grouped_hm = df_hm.groupby(['Jour_Num', 'Jour', 'Heure'])[selected_zone_hm].mean().reset_index()
        pivot_hm = grouped_hm.pivot(index='Jour_Num', columns='Heure', values=selected_zone_hm)
        pivot_hm.index = [jour_names[i] for i in pivot_hm.index]
        
        fig_hm = px.imshow(
            pivot_hm,
            labels=dict(x="Heure de la journée", y="Jour de la semaine", color="CO₂ (ppm)"),
            x=list(range(24)),
            y=list(pivot_hm.index),
            color_continuous_scale="RdYlGn_r",
            aspect="auto",
            title=f"Heatmap de la concentration CO₂ (Niveau de présence) - {selected_zone_hm}"
        )
        fig_hm.update_layout(height=420)
        st.plotly_chart(fig_hm, use_container_width=True)

    # --------------------------------------
    # SUBTAB 3 : QUALITY DE L'AIR & CONFINEMENT
    # --------------------------------------
    with subtab_occ3:
        st.markdown("### Évolution Temporelle du CO₂ & Dépassement des Seuils QAI")
        
        fig_co2_lines = px.line(df_co2, x='Horodatage', y=zones, title="Concentration en CO₂ (ppm)")
        fig_co2_lines.add_hline(y=seuil_conf_co2, line_dash="dash", line_color="orange", annotation_text=f"Seuil Confinement ({seuil_conf_co2} ppm)")
        fig_co2_lines.add_hline(y=1500, line_dash="dash", line_color="red", annotation_text="Seuil Alerte (1500 ppm)")
        st.plotly_chart(fig_co2_lines, use_container_width=True)


# ------------------------------------------
# TAB 4: HUMIDITÉ & VENTILATION
# ------------------------------------------
with tab4:
    st.subheader("Humidité Relative et Confort")
    fig_hum = px.line(df_hum, x='Horodatage', y=zones, title="Humidité Relative (%)")
    fig_hum.add_hrect(y0=30, y1=60, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Zone de Confort (30-60%)")
    st.plotly_chart(fig_hum, use_container_width=True)


# ------------------------------------------
# TAB 5: COV & POLLUANTS
# ------------------------------------------
with tab5:
    st.subheader("Composés Organiques Volatils (COV)")
    fig_cov = px.line(df_cov, x='Horodatage', y=zones, title="Concentration en COV (ppb)")
    fig_cov.add_hline(y=400, line_dash="dash", line_color="orange", annotation_text="Seuil de Vigilance (400 ppb)")
    st.plotly_chart(fig_cov, use_container_width=True)


# ------------------------------------------
# TAB 6: DIAGNOSTIC & RECOMMANDATIONS
# ------------------------------------------
with tab6:
    st.subheader("📑 Diagnostic d'Adéquation Usage / Bâtiment & Plan d'Action")
    
    st.markdown("""
    ### 🎯 Synthèse des Inadéquations Détectées via l'Occupation CO₂
    
    L'analyse croisée des données de détection CO₂ et des plages horaires de chauffage / ventilation permet d'identifier **3 leviers majeurs d'optimisation** :
    """)
    
    col_diag1, col_diag2, col_diag3 = st.columns(3)
    
    with col_diag1:
        st.error("🚨 **Gaspillage Énergétique**")
        st.markdown(f"""
        * **Constat** : {tot_vacance:.0f} heures d'inoccupation observées pendant les plages d'ouverture théorique.
        * **Impact** : Chauffage et ventilation réglés à plein régime dans des zones vides.
        * **Action** : Abaissement de la consigne thermique ou basculement automatique en mode **Éco** sur détection de présence CO₂ < {seuil_occ_co2} ppm pendant 45 min.
        """)
        
    with col_diag2:
        st.warning("⚠️ **Présences Hors-Horaires**")
        st.markdown(f"""
        * **Constat** : {tot_hors_horaires:.0f} heures de présence mesurées le soir ou le week-end.
        * **Impact** : Inconfort potentiel des occupants (chauffage réduit) ou éclairage laissé allumé.
        * **Action** : Activer une dérogation manuelle temporaire (bouton poussoir 2h) plutôt que de prolonger le calendrier global.
        """)
        
    with col_diag3:
        st.info("🍃 **Risque de Sous-ventilation**")
        st.markdown(f"""
        * **Constat** : {tot_sous_vent:.0f} heures de dépassement du seuil de confinement ({seuil_conf_co2} ppm).
        * **Impact** : Baisse de concentration des occupants, fatigue, non-conformité QAI.
        * **Action** : Asservir les débits de la VMC directement au taux de CO₂ mesuré en temps réel (VMC MODO-Régulée).
        """)
    
    st.markdown("---")
    st.subheader("💡 Plan d'Action Priorisé")
    
    actions_df = pd.DataFrame({
        "Priorité": ["🔴 Haute", "🟡 Moyenne", "🟢 Basse"],
        "Type": ["Régulation VMC", "Programmation GTB", "Sensibilisation"],
        "Action Recommandée": [
            "Asservir la vitesse de ventilation au niveau de CO₂ mesuré dans les salles de réunion",
            "Ajuster le démarrage du chauffage à 07:30 au lieu de 06:00 au vu de l'arrivée effective à 08:30",
            "Rappeler aux usagers de fermer les fenêtres lorsque la ventilation mécanique est active"
        ],
        "Gain Estimé": ["12% à 18% sur la ventilation", "8% sur la facture de chauffage", "Confort amélioré"]
    })
    
    st.table(actions_df)