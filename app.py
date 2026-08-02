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

    # Bouton pour déclencher les calculs
    if st.button("🚀 Lancer l'analyse", type="primary"):
        if not cols_int:
            st.warning("⚠️ Veuillez sélectionner au moins un capteur intérieur dans la 3ème colonne.")
        else:
            with st.spinner("Nettoyage et analyse des données en cours..."):
                
                # ---------------------------------------------------------
                # 3. NETTOYAGE ET PRÉPARATION (Robuste & Français)
                # ---------------------------------------------------------
                df_clean = pd.DataFrame()
                
                # Gestion de la date
                df_clean['Date'] = pd.to_datetime(df_raw[col_date], errors='coerce', dayfirst=True)
                
                # Fonction pour convertir les nombres avec des virgules (ex: 21,3 -> 21.3)
                def nettoyer_nombres(colonne):
                    if colonne.dtype == 'object':
                        colonne = colonne.astype(str).str.replace(',', '.', regex=False)
                    return pd.to_numeric(colonne, errors='coerce')
                
                # Application du nettoyage des nombres
                df_clean['T_ext'] = nettoyer_nombres(df_raw[col_text])
                df_clean['T_depart'] = nettoyer_nombres(df_raw[col_tdepart])
                df_clean['T_retour'] = nettoyer_nombres(df_raw[col_tretour])
                
                for col in cols_int:
                    df_clean[col] = nettoyer_nombres(df_raw[col])
                
                # Suppression des lignes sans date valide
                df_clean = df_clean.dropna(subset=['Date'])
                
                if df_clean.empty:
                    st.error("🚨 Impossible de lire les dates. Vérifiez votre colonne de date.")
                    st.stop()
                
                # Indexation temporelle
                df_clean = df_clean.set_index('Date')
                
                # Forcer le pas de 15 minutes et interpolation (trous jusqu'à 1h max)
                df_clean = df_clean.resample('15min').mean()
                df_clean = df_clean.interpolate(method='time', limit=4)
                
                if 'T_depart' not in df_clean.columns:
                    st.error("🚨 Erreur lors de la création de la série temporelle.")
                    st.stop()
                
                # Calculs des moyennes (ignore les capteurs débranchés via skipna=True) et du Delta T
                df_clean['T_int_moy'] = df_clean[cols_int].mean(axis=1, skipna=True)
                df_clean['Delta_T'] = df_clean['T_depart'] - df_clean['T_retour']

                # ---------------------------------------------------------
                # 4. VISUALISATIONS ET ANALYSES EXPERTES
                # ---------------------------------------------------------
                sns.set_theme(style="whitegrid")

                st.write("---")
                st.write("### 📈 1. Évolution globale des températures")
                st.info("💡 **Ce que vous regardez :** Le comportement thermique global de votre bâtiment dans le temps.")
                
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
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.success("**✅ Ce qui est bien :** La courbe verte (Intérieur) reste stable malgré les chutes de la température extérieure. Un écart net est maintenu entre le Départ (rouge) et le Retour (orange), prouvant que la chaleur est bien délivrée.")
                with col_b:
                    st.warning("**⚠️ Ce qui est anormal & Actions :** \n- *Courbe verte instable* : Régulation trop agressive.\n- *Rouge et Orange se touchent* : L'eau revient aussi chaude qu'elle est partie. **Action :** Baisser la vitesse de la pompe (circulateur).")

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
                    
                    st.success("**✅ Bien :** Les points forment une belle ligne diagonale descendante (plus il fait froid, plus l'eau est chaude).")
                    st.warning("**⚠️ Anormal :** Nuage de points dispersé ou horizontal.\n\n**🔧 Action :** Si le bâtiment surchauffe quand il gèle, baissez la 'pente' de la loi d'eau. Si c'est dispersé, vérifiez le bon fonctionnement de la vanne trois voies.")

                with col_g2:
                    st.write("### ☀️ 3. Homogénéité (Capteurs Intérieurs)")
                    st.info("💡 **Ce que vous regardez :** L'équilibre thermique entre les différentes orientations de votre bâtiment.")
                    
                    fig3 = plt.figure(figsize=(8, 6))
                    sns.boxplot(data=df_clean[cols_int])
                    plt.ylabel("Température (°C)")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig3)
                    
                    st.success("**✅ Bien :** Les boîtes sont alignées au même niveau de température avec peu de dispersion.")
                    st.warning("**⚠️ Anormal :** Grosse disparité entre le Nord et le Sud (effet des apports solaires).\n\n**🔧 Action :** Si le Sud surchauffe à cause du soleil, baissez ses robinets thermostatiques pour laisser l'excédent s'évacuer.")
else:
    st.info("En attente d'un fichier Excel. Glissez-le ci-dessus pour commencer.")