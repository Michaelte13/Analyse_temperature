import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# ==============================================================================
# 1. CONFIGURATION DE LA PAGE STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Optimisation Chauffage & Occupation",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 Optimisation GTB : Chauffage vs. Occupation Réelle")
st.markdown("""
Ce module croise les relevés de **CO₂** (présence des occupants) et de **Température** (mise en route du chauffage) 
afin de réduire le temps de préchauffage à vide et recalculer la consigne horaire optimale.
""")

# ==============================================================================
# 2. GÉNÉRATION DE DONNÉES DE DÉMONSTRATION (Si pas de données externes)
# ==============================================================================
@st.cache_data
def generate_sample_data(days=14):
    start_date = datetime(2026, 3, 1, 0, 0)
    dates = [start_date + timedelta(minutes=15 * i) for i in range(days * 24 * 4)]
    
    zones = ["Bureau Nord (Individuel)", "Open Space Sud", "Salle Réunion Est", "Atelier Logistique"]
    
    df_co2 = pd.DataFrame({'Horodatage': dates})
    df_temp = pd.DataFrame({'Horodatage': dates})
    
    np.random.seed(42)
    
    # Plages d'arrivées types par zone (en heure décimale)
    schedules = {
        "Bureau Nord (Individuel)": {"heat_start": 6.0, "occ_start": 8.5},  # Arrivée 8h30
        "Open Space Sud":           {"heat_start": 6.0, "occ_start": 8.0},  # Arrivée 8h00
        "Salle Réunion Est":       {"heat_start": 6.0, "occ_start": 9.5},  # Arrivée 9h30
        "Atelier Logistique":       {"heat_start": 5.5, "occ_start": 7.0}   # Arrivée 7h00
    }
    
    for z in zones:
        heat_h = schedules[z]["heat_start"]
        occ_h = schedules[z]["occ_start"]
        
        is_weekday = df_co2['Horodatage'].dt.weekday < 5
        hours = df_co2['Horodatage'].dt.hour + df_co2['Horodatage'].dt.minute / 60.0
        
        # CO2 : monte quand les gens arrivent
        occ_active = is_weekday & (hours >= occ_h) & (hours < 18.0)
        co2_base = 420
        co2_add = np.where(occ_active, np.random.normal(550, 80, len(dates)), 0)
        df_co2[z] = np.clip(co2_base + co2_add, 400, 1800).astype(int)
        
        # Température : monte quand le chauffage démarre à `heat_h`
        heat_active = is_weekday & (hours >= heat_h) & (hours < 18.5)
        temp_val = np.where(heat_active, 20.0 + np.random.normal(0, 0.2, len(dates)), 16.0 + np.random.normal(0, 0.3, len(dates)))
        df_temp[z] = np.round(temp_val, 1)
        
    return df_co2, df_temp, zones

df_co2, df_temp, zones_list = generate_sample_data()

# ==============================================================================
# 3. PANNEAU DE CONFIGURATION DES PARAMS METIER
# ==============================================================================
st.sidebar.header("⚙️ Paramètres d'Analyse")

seuil_co2 = st.sidebar.slider("Seuil Détection Occupation (CO₂ ppm)", 500, 900, 600, 25)
seuil_temp_confort = st.sidebar.slider("Seuil Déclenchement Chauffage (°C)", 17.5, 20.0, 18.5, 0.5)
inertie_minutes = st.sidebar.slider("Inertie du bâtiment (Minutes pour atteindre le confort)", 15, 120, 45, 15)
jours_ouvres_an = st.sidebar.number_input("Jours de chauffe / an", 150, 250, 210)

# ==============================================================================
# 4. ALGORITHME DE CALCUL D'ADÉQUATION
# ==============================================================================
def analyser_chauffage_vs_presence(df_co2, df_temp, zones, seuil_co2, seuil_temp, inertie_min):
    df_base = pd.DataFrame({'Horodatage': df_co2['Horodatage']})
    df_base['Date'] = df_base['Horodatage'].dt.date
    df_base['Jour_Semaine'] = df_base['Horodatage'].dt.weekday
    df_base['Heure_Decimal'] = df_base['Horodatage'].dt.hour + df_base['Horodatage'].dt.minute / 60.0

    # Filtrer uniquement les jours ouvrés
    df_wk = df_base[df_base['Jour_Semaine'] < 5].copy()
    
    resultats = []
    
    for z in zones:
        df_wk['CO2'] = df_co2.loc[df_wk.index, z]
        df_wk['Temp'] = df_temp.loc[df_wk.index, z]
        
        df_wk['Is_Occ'] = df_wk['CO2'] >= seuil_co2
        df_wk['Is_Heating'] = df_wk['Temp'] >= seuil_temp

        daily_metrics = []
        
        for date_jour, group in df_wk.groupby('Date'):
            # Analyse uniquement la matinée (avant 12h)
            group_matin = group[group['Heure_Decimal'] < 12.0]
            
            rows_heat = group_matin[group_matin['Is_Heating']]
            rows_occ = group_matin[group_matin['Is_Occ']]

            if not rows_heat.empty and not rows_occ.empty:
                t_heat = rows_heat['Heure_Decimal'].min()
                t_occ = rows_occ['Heure_Decimal'].min()
                
                daily_metrics.append({
                    'Heure_Heat': t_heat,
                    'Heure_Occ': t_occ,
                    'Ecart_Heures': t_occ - t_heat
                })

        df_daily = pd.DataFrame(daily_metrics)
        
        if not df_daily.empty:
            avg_heat = df_daily['Heure_Heat'].mean()
            avg_occ = df_daily['Heure_Occ'].mean()
            avg_ecart = df_daily['Ecart_Heures'].mean()
            
            inertie_h = inertie_min / 60.0
            sur_prechauffage = max(0.0, avg_ecart - inertie_h)
            
            # Nouvel horaire recommandé = Heure arrivée - Inertie
            horaire_recommande_dec = max(0.0, avg_occ - inertie_h)
            
            # Formattage Heures:Minutes
            format_time = lambda dec: f"{int(dec):02d}h{int((dec % 1) * 60):02d}"

            resultats.append({
                'Zone': z,
                'Start Chauffage Constaté': format_time(avg_heat),
                'Première Arrivée (CO₂)': format_time(avg_occ),
                'Préchauffage Constaté': f"{avg_ecart:.2f} h",
                'Sur-Préchauffage Inutile': f"{sur_prechauffage:.2f} h/jour",
                'Réglage GTB Cible': format_time(horaire_recommande_dec),
                'Heat_Dec': avg_heat,
                'Occ_Dec': avg_occ,
                'Rec_Dec': horaire_recommande_dec,
                'Gachis_H': sur_prechauffage
            })
            
    return pd.DataFrame(resultats)

df_res = analyser_chauffage_vs_presence(df_co2, df_temp, zones_list, seuil_co2, seuil_temp_confort, inertie_minutes)

# ==============================================================================
# 5. AFFICHAGE DES KPIS CLÉS
# ==============================================================================
st.subheader("📊 Métriques & Économies Potentielles")

gachis_total_jour = df_res['Gachis_H'].sum()
heures_an_economisables = gachis_total_jour * jours_ouvres_an

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Gaspillage Quotidien Cumulé", f"{gachis_total_jour:.2f} h/jour", delta="Heures à vide", delta_color="inverse")
kpi2.metric("Heures de Chauffe Économisables", f"{heures_an_economisables:.0f} h/an", help="Basé sur la saison de chauffe paramétrée")
kpi3.metric("Gain Énergétique Estimé", f"~{min(25, int(heures_an_economisables / 10))}%", help="Estimation de réduction de consommation de préchauffage")

st.markdown("---")

# ==============================================================================
# 6. TABLEAU RECAPITULATIF DES RECOMMANDATIONS GTB
# ==============================================================================
st.subheader("📋 Tableau de Recommandation des Horloges GTB")

st.dataframe(
    df_res[['Zone', 'Start Chauffage Constaté', 'Première Arrivée (CO₂)', 
            'Préchauffage Constaté', 'Sur-Préchauffage Inutile', 'Réglage GTB Cible']],
    use_container_width=True,
    hide_index=True
)

# ==============================================================================
# 7. VISUALISATION DES ÉCARTS ET OPTIMISATION HORAIRE
# ==============================================================================
st.subheader("⏱️ Comparatif Visuel : Horaires Actuels vs. Réglage Cible")

fig = go.Figure()

for idx, row in df_res.iterrows():
    # Barre actuelle (Chauffage -> Arrivée)
    fig.add_trace(go.Scatter(
        x=[row['Heat_Dec'], row['Occ_Dec']],
        y=[row['Zone'], row['Zone']],
        mode='lines+markers',
        name=f"Actuel : {row['Zone']}",
        line=dict(color='crimson', width=6),
        marker=dict(size=10, symbol=['circle', 'square'])
    ))
    
    # Point vert = Horaire cible recommandé
    fig.add_trace(go.Scatter(
        x=[row['Rec_Dec']],
        y=[row['Zone']],
        mode='markers',
        name=f"Cible : {row['Zone']}",
        marker=dict(color='mediumseagreen', size=14, symbol='star')
    ))

fig.update_layout(
    xaxis=dict(
        title="Heures de la journée",
        tickmode='array',
        tickvals=[5, 6, 7, 8, 9, 10],
        ticktext=['05:00', '06:00', '07:00', '08:00', '09:00', '10:00']
    ),
    yaxis=dict(autorange="reversed"),
    height=400,
    showlegend=False,
    margin=dict(l=20, r=20, t=30, b=30)
)

st.plotly_chart(fig, use_container_width=True)

st.caption("🔴 Ligne rouge : Période de préchauffage actuelle | ⭐ Étoile verte : Nouvel horaire d'allumage optimal recommandé.")

# ==============================================================================
# 8. PLAN D'ACTION ET GUIDE DE DÉPLOIEMENT
# ==============================================================================
with st.expander("🛠️ **Plan d'Action : Comment appliquer ces résultats dans votre GTB ?**", expanded=True):
    st.markdown("""
    1. **Saisir les nouvelles horloges de programmation** :
       - Ne conservez plus un horaire de démarrage global unique (ex: 06h00 pour tout le bâtiment).
       - Modifiez les calendriers de démarrage zone par zone selon la colonne **`Réglage GTB Cible`**.
    2. **Intégrer le Relance Optimisée (Auto-adaptative)** :
       - Si votre système GTB possède la fonction *Relance Optimisée*, renseignez l'inertie mesurée (**{inertie_minutes} minutes**) dans la boucle de régulation PID.
    3. **Prendre en compte les Salles de Réunion** :
       - Les salles de réunion présentent souvent les plus grands écarts (occupation ponctuelle ou tardive). Mettez-les en consigne *Inoccupation / Éco* par défaut et asservissez le passage en confort au détecteur de présence/CO₂.
    """)