import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Configuration de la page Streamlit (optionnel mais plus joli)
st.set_page_config(page_title="Analyse Thermique", layout="wide")

st.title("📊 Analyse des températures du bâtiment")

# ---------------------------------------------------------
# 1. GÉNÉRATION DE DONNÉES FICTIVES 
# (À remplacer plus tard par ta lecture de CSV)
# ---------------------------------------------------------
@st.cache_data # Permet à Streamlit de ne pas regénérer les données à chaque clic
def load_data():
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', end='2024-01-07', freq='15min')
    df = pd.DataFrame(index=dates)

    df['T_ext'] = 5 + 5 * np.sin(np.linspace(0, 14*np.pi, len(dates))) + np.random.normal(0, 0.5, len(dates))
    df['T_depart'] = 45 - 1.5 * df['T_ext'] + np.random.normal(0, 2, len(dates))
    df['T_retour'] = df['T_depart'] - (5 + np.random.normal(0, 1, len(dates)))
    df['Int_Nord'] = 19 + np.random.normal(0, 0.2, len(dates))
    df['Int_Sud'] = 19.5 + 2 * np.maximum(0, np.sin(np.linspace(0, 14*np.pi, len(dates))))
    df['Int_Est'] = 19.2 + np.random.normal(0, 0.3, len(dates))
    df['Int_Ouest'] = 19.3 + np.random.normal(0, 0.3, len(dates))
    df['Int_Aux1'] = 19.5 + np.random.normal(0, 0.2, len(dates))

    df.iloc[50:60, :] = np.nan
    df.loc['2024-01-03', 'Int_Sud'] = np.nan

    # Nettoyage
    df = df.resample('15min').mean()
    df = df.interpolate(method='time', limit=4)
    
    capteurs_int = ['Int_Nord', 'Int_Sud', 'Int_Est', 'Int_Ouest', 'Int_Aux1'] 
    df['T_int_moy'] = df[capteurs_int].mean(axis=1, skipna=True)
    df['Delta_T_Chaufferie'] = df['T_depart'] - df['T_retour']
    
    return df, capteurs_int

df, capteurs_int = load_data()

# Affichage d'un aperçu des données sur la page
st.write("### Aperçu des données")
st.dataframe(df.head())

# ---------------------------------------------------------
# 2. VISUALISATIONS STREAMLIT
# ---------------------------------------------------------
sns.set_theme(style="whitegrid")

st.write("---")
st.subheader("📈 Évolution globale des températures")

# Figure 1
fig1 = plt.figure(figsize=(15, 6))
plt.plot(df.index, df['T_depart'], label='Départ (après V3V)', color='red')
plt.plot(df.index, df['T_retour'], label='Retour', color='orange')
plt.plot(df.index, df['T_int_moy'], label='Intérieur Moyen', color='green', linewidth=2)
plt.plot(df.index, df['T_ext'], label='Extérieur', color='blue', alpha=0.5)
plt.ylabel("Température (°C)")
plt.legend()
plt.tight_layout()
st.pyplot(fig1) # <--- C'est ICI la magie Streamlit

st.write("---")
col1, col2 = st.columns(2) # On crée deux colonnes pour un bel affichage

with col1:
    st.subheader("🔥 Vérification de la Loi d'Eau")
    fig2 = plt.figure(figsize=(8, 6))
    df_chauffe = df[df['T_depart'] > 25]
    sns.scatterplot(data=df_chauffe, x='T_ext', y='T_depart', alpha=0.5)
    plt.xlabel("Température Extérieure (°C)")
    plt.ylabel("Température de Départ (°C)")
    if not df_chauffe.empty:
        m, b = np.polyfit(df_chauffe['T_ext'].dropna(), df_chauffe['T_depart'].dropna(), 1)
        plt.plot(df_chauffe['T_ext'], m*df_chauffe['T_ext'] + b, color='red', label=f'Pente: {m:.2f}')
    plt.legend()
    plt.tight_layout()
    st.pyplot(fig2)

with col2:
    st.subheader("☀️ Homogénéité et apports solaires")
    fig3 = plt.figure(figsize=(8, 6))
    sns.boxplot(data=df[capteurs_int])
    plt.ylabel("Température (°C)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig3)