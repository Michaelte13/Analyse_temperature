import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import io

# ==============================================================================
# 1. CONFIGURATION DE LA PAGE
# ==============================================================================
st.set_page_config(
    page_title="Optimisation Chauffage & Occupation",
    page_icon="🔥",
    layout="wide"
)

# ==============================================================================
# 2. GENERATION DE DONNEES PAR DEFAUT (DEMO)
# ==============================================================================
@st.cache_data
def generate_sample_data(days=14):
    start_date = datetime(2026, 3, 1, 0, 0)
    dates = [start_date + timedelta(minutes=15 * i) for i in range(days * 24 * 4)]
    
    zones = ["Bureau Nord (Individuel)", "Open Space Sud", "Salle Réunion Est", "Atelier Logistique"]
    
    df_co2 = pd.DataFrame({'Horodatage': dates})
    df_temp = pd.DataFrame({'Horodatage': dates})
    
    np.random.seed(42)
    schedules = {
        "Bureau Nord (Individuel)": {"heat_start": 6.0, "occ_start": 8.5},
        "Open Space Sud":           {"heat_start": 6.0, "occ_start": 8.0},
        "Salle Réunion Est":       {"heat_start": 6.0, "occ_start": 9.5},
        "Atelier Logistique":       {"heat_start": 5.5, "occ_start": 7.0}
    }
    
    for z in zones:
        heat_h = schedules[z]["heat_start"]
        occ_h = schedules[z]["occ_start"]
        
        is_weekday = df_co2['Horodatage'].dt.weekday < 5
        hours = df_co2['Horodatage'].dt.hour + df_co2['Horodatage'].dt.minute / 60.0
        
        occ_active = is_weekday & (hours >= occ_h) & (hours < 18.0)
        co2_base = 420
        co2_add = np.where(occ_active, np.random.normal(550, 80, len(dates)), 0)
        df_co2[z] = np.clip(co2_base + co2_add, 400, 1800).astype(int)
        
        heat_active = is_weekday & (hours >= heat_h) & (hours < 18.5)
        temp_val = np.where(
            heat_active, 
            20.0 + np.random.normal(0, 0.2, len(dates)), 
            16.0 + np.random.normal(0, 0.3, len(dates))
        )
        df_temp[z] = np.round(temp_val, 1)
        
    return df_co2, df_temp, zones

# ==============================================================================
# 3. MOTEUR D'ANALYSE ET DE CALCUL
# ==============================================================================
def analyser_chauffage_vs_presence(df_co2, df_temp, zones, seuil_co2, seuil_temp, inertie_min):
    df_base = pd.DataFrame({'Horodatage': pd.to_datetime(df_co2['Horodatage'])})
    df_base['Date'] = df_base['Horodatage'].dt.date
    df_base['Jour_Semaine'] = df_base['Horodatage'].dt.weekday
    df_base['Heure_Decimal'] = df_base['Horodatage'].dt.hour + df_base['Horodatage'].dt.minute / 60.0

    df_wk = df_base[df_base['Jour_Semaine'] < 5].copy()
    resultats = []
    
    for z in zones:
        if z not in df_co2.columns or z not in df_temp.columns:
            continue

        df_wk['CO2'] = df_co2.loc[df_wk.index, z]
        df_wk['Temp'] = df_temp.loc[df_wk.index, z]
        
        df_wk['Is_Occ'] = df_wk['CO2'] >= seuil_co2
        df_wk['Is_Heating'] = df_wk['Temp'] >= seuil_temp

        daily_metrics = []
        
        for date_jour, group in df_wk.groupby('Date'):
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
            horaire_recommande_dec = max(0.0, avg_occ - inertie_h)
            
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

# ==============================================================================
# 4. BARRE LATERALE (PARAMETRES & CHARGEMENT FICHIERS)
# ==============================================================================
st.sidebar.title("🛠️ Configuration")

st.sidebar.subheader("1. Source des données")
source_mode = st.sidebar.radio("Choix de la source :", ["Données de démonstration", "Importer mes fichiers CSV"])

if source_mode == "Importer mes fichiers CSV":
    file_co2 = st.sidebar.file_uploader("Fichier CO₂ (CSV)", type=["csv"])
    file_temp = st.sidebar.file_uploader("Fichier Températures (CSV)", type=["csv"])
    
    if file_co2 and file_temp:
        df_co2 = pd.read_csv(file_co2)
        df_temp = pd.read_csv(file_temp)
        zones_list = [c for c in df_co2.columns if c != 'Horodatage']
    else:
        st.sidebar.warning("Veuillez charger les 2 fichiers CSV. Passage automatique en mode démo.")
        df_co2, df_temp, zones_list = generate_sample_data()
else:
    df_co2, df_temp, zones_list = generate_sample_data()

st.sidebar.subheader("2. Paramètres Métier")
seuil_co2 = st.sidebar.slider("Seuil Détection Occupation (CO₂ ppm)", 450, 900, 600, 25)
seuil_temp_confort = st.sidebar.slider("Seuil Déclenchement Chauffage (°C)", 17.5, 20.0, 18.5, 0.5)
inertie_minutes = st.sidebar.slider("Inertie du bâtiment (Minutes pour chauffer)", 15, 120, 45, 15)
jours_ouvres_an = st.sidebar.number_input("Jours de chauffe / an", 100, 250, 210)

# ==============================================================================
# 5. CONTENU PRINCIPAL & CALCULS
# ==============================================================================
st.title("🔥 Optimisation GTB : Chauffage vs. Occupation Réelle")
st.markdown("Croisement automatique des données de **Température** et de **CO₂** pour éliminer le sur-préchauffage à vide.")

df_res = analyser_chauffage_vs_presence(
    df_co2, df_temp, zones_list, seuil_co2, seuil_temp_confort, inertie_minutes
)

if df_res.empty:
    st.error("Aucune donnée disponible ou seuils inadaptés pour détecter les déclenchements.")
    st.stop()

# --- TABULATION ---
tab1, tab2 = st.tabs(["📊 Diagnostic GTB & Plan d'Action", "📈 Courbes Température & CO₂"])

with tab1:
    # --- KPIS ---
    gachis_total_jour = df_res['Gachis_H'].sum()
    heures_an_economisables = gachis_total_jour * jours_ouvres_an

    k1, k2, k3 = st.columns(3)
    k1.metric("Gaspillage Quotidien Cumulé", f"{gachis_total_jour:.2f} h/jour", delta="Heures à vide", delta_color="inverse")
    k2.metric("Heures de Chauffe Économisables", f"{heures_an_economisables:.0f} h/an", help="Volume d'heures gagné sur la saison")
    k3.metric("Gain Énergétique Estimé", f"~{min(30, int(heures_an_economisables / 10))}%", help="Réduction estimée des kWhe de préchauffage")

    st.markdown("---")

    # --- TABLEAU DES CONSIGNES GTB ---
    st.subheader("📋 Planning de Programmation Cible pour la GTB")
    
    df_display = df_res[['Zone', 'Start Chauffage Constaté', 'Première Arrivée (CO₂)', 
                         'Préchauffage Constaté', 'Sur-Préchauffage Inutile', 'Réglage GTB Cible']].copy()
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Bouton d'export CSV
    csv_buffer = io.StringIO()
    df_display.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 Télécharger la table de programmation GTB (CSV)",
        data=csv_buffer.getvalue(),
        file_name="consignes_optimisees_gtb.csv",
        mime="text/csv"
    )

    st.markdown("---")

    # --- GRAPHIC VISUEL ---
    st.subheader("⏱️ Alignement Temporel : Actuel (Ligne) vs Optimal (Étoile)")
    
    fig = go.Figure()
    for idx, row in df_res.iterrows():
        fig.add_trace(go.Scatter(
            x=[row['Heat_Dec'], row['Occ_Dec']],
            y=[row['Zone'], row['Zone']],
            mode='lines+markers',
            name=f"Actuel : {row['Zone']}",
            line=dict(color='crimson', width=5),
            marker=dict(size=9, symbol=['circle', 'square'])
        ))
        
        fig.add_trace(go.Scatter(
            x=[row['Rec_Dec']],
            y=[row['Zone']],
            mode='markers',
            name=f"Cible : {row['Zone']}",
            marker=dict(color='mediumseagreen', size=15, symbol='star')
        ))

    fig.update_layout(
        xaxis=dict(
            title="Heure de la journée",
            tickmode='array',
            tickvals=[4, 5, 6, 7, 8, 9, 10, 11, 12],
            ticktext=['04h', '05h', '06h', '07h', '08h', '09h', '10h', '11h', '12h']
        ),
        yaxis=dict(autorange="reversed"),
        height=380,
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("🔍 Inspection détaillée d'une zone")
    selected_zone = st.selectbox("Sélectionner une salle / zone :", zones_list)
    
    df_co2['Horodatage'] = pd.to_datetime(df_co2['Horodatage'])
    df_temp['Horodatage'] = pd.to_datetime(df_temp['Horodatage'])

    fig_detail = go.Figure()
    
    # Courbe Température
    fig_detail.add_trace(go.Scatter(
        x=df_temp['Horodatage'], y=df_temp[selected_zone],
        name="Température (°C)", line=dict(color='firebrick', width=2)
    ))
    
    # Courbe CO2 (Axe secondaire)
    fig_detail.add_trace(go.Scatter(
        x=df_co2['Horodatage'], y=df_co2[selected_zone],
        name="CO₂ (ppm)", line=dict(color='royalblue', width=1.5, dash='dot'),
        yaxis="y2"
    ))

    fig_detail.update_layout(
        title=f"Évolution de la Température et du CO₂ - {selected_zone}",
        xaxis=dict(title="Date / Heure"),
        yaxis=dict(title="Température (°C)", side="left"),
        yaxis2=dict(title="CO₂ (ppm)", side="right", overlaying="y"),
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_detail, use_container_width=True)