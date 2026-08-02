import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ---------------------------------------------------------
# 1. GÉNÉRATION DE DONNÉES FICTIVES (Pour tester le code)
# À remplacer par : df = pd.read_csv("ton_fichier.csv", parse_dates=['date'], index_col='date')
# ---------------------------------------------------------
np.random.seed(42)
dates = pd.date_range(start='2024-01-01', end='2024-01-07', freq='15min')
df = pd.DataFrame(index=dates)

# Simulation des températures
df['T_ext'] = 5 + 5 * np.sin(np.linspace(0, 14*np.pi, len(dates))) + np.random.normal(0, 0.5, len(dates))
df['T_depart'] = 45 - 1.5 * df['T_ext'] + np.random.normal(0, 2, len(dates)) # Loi d'eau simulée
df['T_retour'] = df['T_depart'] - (5 + np.random.normal(0, 1, len(dates)))
df['Int_Nord'] = 19 + np.random.normal(0, 0.2, len(dates))
df['Int_Sud'] = 19.5 + 2 * np.maximum(0, np.sin(np.linspace(0, 14*np.pi, len(dates)))) # Apport solaire
df['Int_Est'] = 19.2 + np.random.normal(0, 0.3, len(dates))
df['Int_Ouest'] = 19.3 + np.random.normal(0, 0.3, len(dates))
df['Int_Aux1'] = 19.5 + np.random.normal(0, 0.2, len(dates))

# Simulation de tes "trous" et capteurs manquants
df.iloc[50:60, :] = np.nan # Un trou complet d'une heure et demie
df.loc['2024-01-03', 'Int_Sud'] = np.nan # Capteur Sud débranché ce jour-là

# ---------------------------------------------------------
# 2. NETTOYAGE ET PRÉPARATION DES DONNÉES
# ---------------------------------------------------------

# Forcer l'index sur 15 min exactement (crée des NaNs si des lignes manquent)
df = df.resample('15min').mean()

# Interpoler temporellement les petits trous (limit=4 correspond à 4 * 15min = 1h max)
# Au-delà d'1h sans données, on laisse le trou pour ne pas fausser l'analyse
df = df.interpolate(method='time', limit=4)

# Liste de tes capteurs intérieurs
capteurs_int = ['Int_Nord', 'Int_Sud', 'Int_Est', 'Int_Ouest', 'Int_Aux1'] 
# (Ajoute tes autres Aux ici)

# Création d'une température intérieure moyenne. 
# skipna=True permet de faire la moyenne même si 3 capteurs sur 7 sont débranchés !
df['T_int_moy'] = df[capteurs_int].mean(axis=1, skipna=True)

# Calcul du Delta T Chaufferie
df['Delta_T_Chaufferie'] = df['T_depart'] - df['T_retour']

# ---------------------------------------------------------
# 3. VISUALISATIONS (Analyses)
# ---------------------------------------------------------
sns.set_theme(style="whitegrid")

# Figure 1 : Le comportement global dans le temps
plt.figure(figsize=(15, 6))
plt.plot(df.index, df['T_depart'], label='Départ (après V3V)', color='red')
plt.plot(df.index, df['T_retour'], label='Retour', color='orange')
plt.plot(df.index, df['T_int_moy'], label='Intérieur Moyen', color='green', linewidth=2)
plt.plot(df.index, df['T_ext'], label='Extérieur', color='blue', alpha=0.5)
plt.title("Évolution des températures globales (Pas de 15 min)")
plt.ylabel("Température (°C)")
plt.legend()
plt.tight_layout()
plt.show()

# Figure 2 : La signature thermique (Loi d'eau)
plt.figure(figsize=(8, 6))
# On filtre les données pour ne garder que les moments où le chauffage tourne (ex: T_depart > 25)
df_chauffe = df[df['T_depart'] > 25]
sns.scatterplot(data=df_chauffe, x='T_ext', y='T_depart', alpha=0.5)
plt.title("Vérification de la Loi d'Eau (Vanne 3 Voies)")
plt.xlabel("Température Extérieure (°C)")
plt.ylabel("Température de Départ (°C)")
# Ajout d'une droite de tendance
if not df_chauffe.empty:
    m, b = np.polyfit(df_chauffe['T_ext'].dropna(), df_chauffe['T_depart'].dropna(), 1)
    plt.plot(df_chauffe['T_ext'], m*df_chauffe['T_ext'] + b, color='red', label=f'Tendance (Pente: {m:.2f})')
plt.legend()
plt.tight_layout()
plt.show()

# Figure 3 : Homogénéité (La bataille des orientations)
plt.figure(figsize=(10, 6))
sns.boxplot(data=df[capteurs_int])
plt.title("Dispersion des températures par orientation")
plt.ylabel("Température (°C)")
plt.tight_layout()
plt.show()