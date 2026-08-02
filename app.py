import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

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
    # 2. ASSOCIATION DES COLONNES (Mapping)
    # ---------------------------------------------------------
    st.write("---")
    st.write("### 2. Configuration des capteurs")
    st.write("Associez vos colonnes Excel aux données nécessaires pour l'analyse :")
    
    colonnes_dispo = df_raw.columns.tolist()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        col_date = st.selectbox("📅 Colonne Date/Heure", options=colonnes_dispo)
        col_text = st.selectbox("🌡️ Température Extérieure", options=colonnes_dispo)
    with col2:
        col_tdepart = st.selectbox("🔥 Temp. Départ Chaufferie (après V3V)", options=colonnes_dispo)
        col_tretour = st.selectbox("❄️ Temp. Retour Chaufferie", options=colonnes_dispo)
    with col3:
        cols_int = st.multiselect("🏠 Capteurs Intérieurs (Sélectionnez-en plusieurs)", options=colonnes_dispo)

    # Bouton pour déclencher les calculs une fois la configuration terminée
    if st.button("🚀 Lancer l'analyse", type="primary"):
        if not cols_int:
            st.warning("⚠️ Veuillez sélectionner au moins un capteur intérieur dans la 3ème colonne.")
        else:
            with st.spinner("Nettoyage et analyse des données en cours..."):
                # ---------------------------------------------------------
                # 3. NETTOYAGE ET PRÉPARATION
                # ---------------------------------------------------------
                # Création d'un nouveau dataframe propre
                df_clean = pd.DataFrame()
                
                # Gestion de la date
                df_clean['Date'] = pd.to_datetime(df_raw[col_date])
                df_clean = df_clean.set_index('Date')
                
                # Conversion des valeurs en nombres (ignore le texte parasite)
                df_clean['T_ext'] = pd.to_numeric(df_raw[col_text].values, errors='coerce')
                df_clean['T_depart'] = pd.to_numeric(df_raw[col_tdepart].values, errors='coerce')
                df_clean['T_retour'] = pd.to_numeric(df_raw[col_tretour].values, errors='coerce')
                
                for col in cols_int:
                    df_clean[col] = pd.to_numeric(df_raw[col].values, errors='coerce')
                
                # Lissage : on force le pas à 15 minutes et on bouche les trous jusqu'à 1 heure
                df_clean = df_clean.resample('15min').mean()
                df_clean = df_clean.interpolate(method='time', limit=4)
                
                # Calculs des moyennes et Delta
                df_clean['T_int_moy'] = df_clean[cols_int].mean(axis=1, skipna=True)
                df_clean['Delta_T'] = df_clean['T_depart'] - df_clean['T_retour']

                # ---------------------------------------------------------
                # 4. VISUALISATIONS
                # ---------------------------------------------------------
                sns.set_theme(style="whitegrid")

                st.write("---")
                st.write("### 📈 Évolution globale des températures")

                # Figure 1
                fig1 = plt.figure(figsize=(15, 6))
                plt.plot(df_clean.index, df_clean['T_depart'], label='Départ (après V3V)', color='red')
                plt.plot(df_clean.index, df_clean['T_retour'], label='Retour', color='orange')
                plt.plot(df_clean.index, df_clean['T_int_moy'], label='Intérieur Moyen', color='green', linewidth=2)
                plt.plot(df_clean.index, df_clean['T_ext'], label='Extérieur', color='blue', alpha=0.5)
                plt.ylabel("Température (°C)")
                plt.legend()
                plt.tight_layout()
                st.pyplot(fig1)

                st.write("---")
                col_g1, col_g2 = st.columns(2)

                with col_g1:
                    st.write("#### 🔥 Vérification de la Loi d'Eau")
                    st.caption("Température d'envoi de l'eau en fonction de la température extérieure")
                    fig2 = plt.figure(figsize=(8, 6))
                    
                    # On ne garde que les moments où la chaudière tourne (ex: Départ > 25°C)
                    df_chauffe = df_clean[df_clean['T_depart'] > 25]
                    sns.scatterplot(data=df_chauffe, x='T_ext', y='T_depart', alpha=0.5)
                    plt.xlabel("Température Extérieure (°C)")
                    plt.ylabel("Température de Départ (°C)")
                    
                    # Calcul de la droite de tendance (si on a des données valides)
                    mask = ~np.isnan(df_chauffe['T_ext']) & ~np.isnan(df_chauffe['T_depart'])
                    if mask.sum() > 2:
                        m, b = np.polyfit(df_chauffe.loc[mask, 'T_ext'], df_chauffe.loc[mask, 'T_depart'], 1)
                        plt.plot(df_chauffe['T_ext'], m*df_chauffe['T_ext'] + b, color='red', label=f'Tendance (Pente: {m:.2f})')
                    
                    plt.legend()
                    plt.tight_layout()
                    st.pyplot(fig2)

                with col_g2:
                    st.write("#### ☀️ Homogénéité et Capteurs")
                    st.caption("Dispersion des températures selon l'orientation")
                    fig3 = plt.figure(figsize=(8, 6))
                    sns.boxplot(data=df_clean[cols_int])
                    plt.ylabel("Température (°C)")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig3)
else:
    st.info("En attente d'un fichier Excel. Glissez-le ci-dessus pour commencer.")