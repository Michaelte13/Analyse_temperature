import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Configuration de la page Streamlit
st.set_page_config(page_title="Analyse Thermique", layout="wide")
st.title("📊 Analyse des températures du bâtiment")

# ---------------------------------------------------------
# 1. ZONE DE DÉPÔT DU FICHIER
# ---------------------------------------------------------
st.write("### 1. Importer les données")
uploaded_file = st.file_uploader("Déposez votre fichier Excel ici (.xlsx, .xls)", type=['xlsx', 'xls'])

if uploaded_file is not None:
    # Lecture du fichier Excel
    df_raw = pd.read_excel(uploaded_file)
    
    st.write("**Aperçu de vos données brutes :**")
    st.dataframe(df_raw.head())
    
    # ---------------------------------------------------------
    # 2. DÉTECTION AUTOMATIQUE DES COLONNES
    # ---------------------------------------------------------
    colonnes_dispo = df_raw.columns.tolist()
    
    def trouver_colonne(mots_cles):
        for col in colonnes_dispo:
            col_lower = str(col).lower()
            for mot in mots_cles:
                if mot in col_lower:
                    return col
        return colonnes_dispo[0]

    col_date_auto = trouver_colonne(['date', 'heure', 'time'])
    col_ext_auto = trouver_colonne(['ext', 'exterieur', 'extérieur'])
    col_depart_auto = trouver_colonne(['depart', 'départ'])
    col_retour_auto = trouver_colonne(['retour'])
    
    mots_interieurs = ['nord', 'sud', 'est', 'ouest', 'aux', 'int', 'intérieur']
    cols_int_auto = [col for col in colonnes_dispo if any(m in str(col).lower() for m in mots_interieurs)]
    if not cols_int_auto:
        cols_int_auto = [col for col in colonnes_dispo if col not in [col_date_auto, col_ext_auto, col_depart_auto, col_retour_auto]]

    st.write("---")
    st.write("### 2. Configuration automatique des capteurs")
    st.info("💡 *Les colonnes ont été détectées automatiquement. Vous pouvez les modifier ci-dessous si nécessaire.*")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        col_date = st.selectbox("📅 Colonne Date/Heure", options=colonnes_dispo, index=colonnes_dispo.index(col_date_auto))
        col_text = st.selectbox("🌡️ Température Extérieure", options=colonnes_dispo, index=colonnes_dispo.index(col_ext_auto))
    with col2:
        col_tdepart = st.selectbox("🔥 Temp. Départ Chaufferie (après V3V)", options=colonnes_dispo, index=colonnes_dispo.index(col_depart_auto))
        col_tretour = st.selectbox("❄️ Temp. Retour Chaufferie", options=colonnes_dispo, index=colonnes_dispo.index(col_retour_auto))
    with col3:
        cols_int = st.multiselect("🏠 Capteurs Intérieurs & Auxiliaires", options=colonnes_dispo, default=cols_int_auto)

    # Bouton pour déclencher les calculs
    if st.button("🚀 Lancer l'analyse", type="primary"):
        if not cols_int:
            st.warning("⚠️ Veuillez sélectionner au moins un capteur intérieur dans la 3ème colonne.")
        else:
            with st.spinner("Nettoyage et analyse des données en cours..."):
                
                # ---------------------------------------------------------
                # 3. NETTOYAGE ET PRÉPARATION
                # ---------------------------------------------------------
                df_clean = pd.DataFrame()
                df_clean['Date'] = pd.to_datetime(df_raw[col_date], errors='coerce', dayfirst=True)
                
                def nettoyer_nombres(colonne):
                    if colonne.dtype == 'object':
                        colonne = colonne.astype(str).str.replace(',', '.', regex=False)
                    return pd.to_numeric(colonne, errors='coerce')
                
                df_clean['T_ext'] = nettoyer_nombres(df_raw[col_text])
                df_clean['T_depart'] = nettoyer_nombres(df_raw[col_tdepart])
                df_clean['T_retour'] = nettoyer_nombres(df_raw[col_tretour])
                
                for col in cols_int:
                    df_clean[col] = nettoyer_nombres(df_raw[col])
                
                df_clean = df_clean.dropna(subset=['Date'])
                if df_clean.empty:
                    st.error("🚨 Impossible de lire les dates. Vérifiez votre colonne de date.")
                    st.stop()
                
                df_clean = df_clean.set_index('Date')
                df_clean = df_clean.resample('15min').mean()
                df_clean = df_clean.interpolate(method='time', limit=4)
                
                if 'T_depart' not in df_clean.columns:
                    st.error("🚨 Erreur lors de la création de la série temporelle.")
                    st.stop()
                
                df_clean['T_int_moy'] = df_clean[cols_int].mean(axis=1, skipna=True)
                df_clean['Delta_T'] = df_clean['T_depart'] - df_clean['T_retour']

                # ---------------------------------------------------------
                # 4. VISUALISATIONS ET ANALYSES EXPERTES
                # ---------------------------------------------------------
                sns.set_theme(style="whitegrid")

                st.write("---")
                st.write("### 📈 1. Évolution globale des températures")
                st.info("💡 **Ce que vous regardez :** Le comportement thermique global de votre bâtiment dans le temps.")
                
                fig1 = plt.figure(figsize=(15, 6))
                plt.plot(df_clean.index, df_clean['T_depart'], label='Départ (après V3V)', color='red')
                plt.plot(df_clean.index, df_clean['T_retour'], label='Retour', color='orange')
                plt.plot(df_clean.index, df_clean['T_int_moy'], label='Intérieur Moyen', color='green', linewidth=2)
                plt.plot(df_clean.index, df_clean['T_ext'], label='Extérieur', color='blue', alpha=0.5)
                plt.ylabel("Température (°C)")
                plt.legend()
                plt.tight_layout()
                st.pyplot(fig1)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.success("**✅ Ce qui est bien :** La courbe verte (Intérieur) reste stable malgré les chutes de la température extérieure. Un écart net est maintenu entre le Départ (rouge) et le Retour (orange).")
                with col_b:
                    st.warning("**⚠️ Ce qui est anormal & Actions :** \n- *Courbe verte instable* : Régulation trop agressive.\n- *Rouge et Orange se touchent* : L'eau revient aussi chaude qu'elle est partie. **Action :** Baisser la vitesse du circulateur.")

                st.write("---")
                col_g1, col_g2 = st.columns(2)

                with col_g1:
                    st.write("### 🔥 2. Vérification de la Loi d'Eau")
                    st.info("💡 **Ce que vous regardez :** La capacité de votre chaufferie à adapter la température de l'eau au froid extérieur.")
                    
                    fig2 = plt.figure(figsize=(8, 6))
                    df_chauffe = df_clean[df_clean['T_depart'] > 25]
                    sns.scatterplot(data=df_chauffe, x='T_ext', y='T_depart', alpha=0.5)
                    plt.xlabel("Température Extérieure (°C)")
                    plt.ylabel("Température de Départ (°C)")
                    
                    mask = ~np.isnan(df_chauffe['T_ext']) & ~np.isnan(df_chauffe['T_depart'])
                    if mask.sum() > 2:
                        m, b = np.polyfit(df_chauffe.loc[mask, 'T_ext'], df_chauffe.loc[mask, 'T_depart'], 1)
                        plt.plot(df_chauffe['T_ext'], m*df_chauffe['T_ext'] + b, color='red', label=f'Tendance (Pente: {m:.2f})')
                    
                    plt.legend()
                    plt.tight_layout()
                    st.pyplot(fig2)
                    
                    st.success("**✅ Bien :** Les points forment une belle ligne diagonale descendante.")
                    st.warning("**⚠️ Anormal :** Nuage de points dispersé ou horizontal.\n\n**🔧 Action :** Ajustez la pente de la loi d'eau ou vérifiez la vanne 3 voies.")

                with col_g2:
                    st.write("### ☀️ 3. Homogénéité (Capteurs Intérieurs)")
                    st.info("💡 **Ce que vous regardez :** L'équilibre thermique entre les différentes orientations du bâtiment.")
                    
                    fig3 = plt.figure(figsize=(8, 6))
                    sns.boxplot(data=df_clean[cols_int])
                    plt.ylabel("Température (°C)")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig3)
                    
                    st.success("**✅ Bien :** Les boîtes sont alignées au même niveau de température.")
                    st.warning("**⚠️ Anormal :** Grosse disparité Nord/Sud (apports solaires).\n\n**🔧 Action :** Régulez via les robinets thermostatiques au Sud.")

                # ---------------------------------------------------------
                # 5. ANALYSE AVANCÉE : HORAIRES, 19°C ET ÉCARTS PAR CAPTEUR
                # ---------------------------------------------------------
                st.write("---")
                st.write("### 🕒 4. Analyse des performances de montée en température (Consigne : 19°C)")
                st.info("💡 **Ce que vous regardez :** Comparaison entre l'heure à laquelle le chauffage s'allume et l'heure à laquelle les salles atteignent la température normalisée de **19°C**.")

                df_clean['Is_Heating'] = df_clean['T_depart'] > 25
                df_clean['Day'] = df_clean.index.date
                target_temp = 19.0
                
                daily_schedule = []
                for day, group in df_clean.groupby('Day'):
                    heating_times = group[group['Is_Heating']].index
                    if not heating_times.empty:
                        start_time = heating_times.min().strftime('%H:%M')
                        stop_time = heating_times.max().strftime('%H:%M')
                    else:
                        start_time = 'Non chauffé'
                        stop_time = '-'
                    
                    # Heure où la température intérieure moyenne atteint 19°C
                    int_moy_series = group['T_int_moy']
                    reaching_19 = int_moy_series[int_moy_series >= target_temp].index
                    if not reaching_19.empty and start_time != 'Non chauffé':
                        # On cherche la première fois dans la journée
                        time_19 = reaching_19.min().strftime('%H:%M')
                    else:
                        time_19 = 'Non atteint'
                        
                    daily_schedule.append({
                        'Date': day.strftime('%d/%m/%Y'),
                        '🚀 Démarrage Chauffage': start_time,
                        '🎯 Atteinte 19°C (Moy)': time_19,
                        '🛑 Coupure Chauffage': stop_time
                    })
                
                df_res_schedule = pd.DataFrame(daily_schedule)
                st.dataframe(df_res_schedule, use_container_width=True)

                col_c, col_d = st.columns(2)
                with col_c:
                    st.success("**✅ Ce qui est bien :** Le bâtiment atteint 19°C rapidement après le démarrage du chauffage (montée en régime cohérente avec l'inertie).")
                with col_d:
                    st.warning("**⚠️ Ce qui est anormal & Actions :** \n- *19°C atteint trop tard* (plus de 3h après l'allumage) : Le chauffage démarre trop tard ou la puissance est insuffisante.\n- *19°C atteint trop tôt* : Le chauffage s'allume inutilement tôt dans la nuit.")

                # Analyse des écarts par capteur par rapport à 19°C
                st.write("### 📐 5. Écart de température par capteur (Objectif : 19°C)")
                st.info("💡 **Ce que vous regardez :** La différence entre la température réelle mesurée par chaque capteur et la consigne de référence de 19°C.")

                sensor_stats = []
                for col in cols_int:
                    val_col = df_clean[col].dropna()
                    if not val_col.empty:
                        moy_temp = val_col.mean()
                        max_temp = val_col.max()
                        delta_moy = moy_temp - target_temp
                        sensor_stats.append({
                            'Capteur': col,
                            'Temp. Moyenne': f"{round(moy_temp, 2)} °C",
                            'Temp. Maximale': f"{round(max_temp, 2)} °C",
                            'Écart vs 19°C (Moy)': f"{'+' if delta_moy > 0 else ''}{round(delta_moy, 2)} °C"
                        })
                
                df_sensor_stats = pd.DataFrame(sensor_stats)
                st.dataframe(df_sensor_stats, use_container_width=True)

                st.info("🔎 **Guide d'interprétation :** Un écart positif (ex: *+1.5 °C*) indique une **surchauffe** chronique de la pièce (souvent lié au soleil ou à un déséquilibrage hydraulique). Un écart négatif (ex: *-1.0 °C*) indique une **sous-chauffe** (pièce froide ou mal irriguée).")

else:
    st.info("En attente d'un fichier Excel. Glissez-le ci-dessus pour commencer.")