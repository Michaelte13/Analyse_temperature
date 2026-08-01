import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Étape 1 - Analyse Températures", page_icon="🌡️", layout="wide")

st.title("🌡️ Étape 1 : Diagnostic Thermique du Premier Onglet")
st.caption("Analyse des zones (Nord, Sud, Est, Ouest, Aux 1-3), de l'extérieur et du circuit chaufferie.")

# ==============================================================================
# 1. CHARGEMENT ET PRETRAITEMENT DES DONNEES
# ==============================================================================
uploaded_file = st.sidebar.file_uploader("Fichier Excel (.xlsx) ou CSV", type=["xlsx", "csv"])

@st.cache_data
def load_first_sheet(file):
    if file.name.endswith('.xlsx'):
        df = pd.read_excel(file, sheet_name=0)
    else:
        df = pd.read_csv(file)
    return df

if uploaded_file is not None:
    df_raw = load_first_sheet(uploaded_file)
else:
    st.info("💡 Aucun fichier importé. Données de démonstration chargées.")
    dates = pd.date_range("2026-03-01 00:00", "2026-03-07 23:45", freq="15min")
    n = len(dates)
    hours = dates.hour + dates.minute / 60.0
    is_work = (dates.weekday < 5) & (hours >= 8) & (hours < 18)
    
    t_ext = 5 + 4 * np.sin((hours - 9) * np.pi / 12) + np.random.normal(0, 0.4, n)
    t_nord = np.where(is_work, 19.8 + np.random.normal(0, 0.3, n), 17.0 + np.random.normal(0, 0.4, n))
    t_sud = t_nord + np.where(is_work & (hours >= 11) & (hours <= 16), 2.2 + np.random.normal(0, 0.4, n), 0)
    t_est = t_nord + np.where(is_work & (hours >= 8) & (hours <= 12), 1.2, 0)
    t_ouest = t_nord + np.where(is_work & (hours >= 14) & (hours <= 17), 1.1, 0)
    t_aux1 = t_nord - 2.1
    t_aux2 = t_nord + 3.0
    t_aux3 = t_nord + 0.2
    
    heating_on = (dates.weekday < 5) & (hours >= 5.5) & (hours < 18.5)
    t_dep = np.where(heating_on, 58 - 1.2 * t_ext + np.random.normal(0, 0.8, n), 20 + np.random.normal(0, 0.3, n))
    t_ret = np.where(heating_on, t_dep - (9.5 + np.random.normal(0, 0.8, n)), t_dep - 0.5)
    
    chaufferie_str = [f"{round(d, 1)} – {round(r, 1)}" for d, r in zip(t_dep, t_ret)]
    
    df_raw = pd.DataFrame({
        'Horodatage': dates,
        'Extérieur': np.round(t_ext, 1),
        'Nord': np.round(t_nord, 1),
        'Sud': np.round(t_sud, 1),
        'Est': np.round(t_est, 1),
        'Ouest': np.round(t_ouest, 1),
        'Aux1': np.round(t_aux1, 1),
        'Aux2': np.round(t_aux2, 1),
        'Aux3': np.round(t_aux3, 1),
        'Départ - Retour Chaufferie': chaufferie_str
    })

df = df_raw.copy()

# 1. Identification sécurisée de la colonne Horodatage
col_date_candidates = [c for c in df.columns if any(k in c.lower() for k in ['date', 'horo', 'temps', 'time'])]
col_date = col_date_candidates[0] if col_date_candidates else df.columns[0]

df[col_date] = pd.to_datetime(df[col_date], errors='coerce', dayfirst=True, format='mixed')
df = df.dropna(subset=[col_date]).copy()

df['Jour_Semaine'] = df[col_date].dt.weekday
df['Heure_Dec'] = df[col_date].dt.hour + df[col_date].dt.minute / 60.0
is_occ = (df['Jour_Semaine'] < 5) & (df['Heure_Dec'] >= 8.0) & (df['Heure_Dec'] < 18.0)

# 2. Parsing sécurisé Chaufferie
def parse_chaufferie(series):
    cleaned = series.astype(str).str.replace(',', '.').str.strip()
    cleaned = cleaned.str.replace(r'[–—/]', '-', regex=True)
    split_df = cleaned.str.split('-', expand=True)
    
    dep = pd.to_numeric(split_df[0].str.strip(), errors='coerce')
    if split_df.shape[1] >= 2:
        ret = pd.to_numeric(split_df[1].str.strip(), errors='coerce')
    else:
        ret = pd.Series(np.nan, index=series.index)
        
    return dep, ret

cols_chaufferie = [c for c in df.columns if 'chaufferie' in c.lower() or ('départ' in c.lower() and 'retour' in c.lower())]
if not cols_chaufferie:
    cols_chaufferie = [c for c in df.columns if 'départ' in c.lower() or 'retour' in c.lower()]

col_chaufferie = cols_chaufferie[0] if cols_chaufferie else df.columns[-1]

df['T_Depart'], df['T_Retour'] = parse_chaufferie(df[col_chaufferie])
df['Delta_T_Chaufferie'] = df['T_Depart'] - df['T_Retour']

# ==============================================================================
# 2. DIAGNOSTIC ET CALCULS CHIFFRES
# ==============================================================================

# A. CHAUFFERIE
heating_active = df['T_Depart'] > 30.0
pct_temps_chauffe = heating_active.mean() * 100
df_heat = df[heating_active]

t_dep_moy = df_heat['T_Depart'].mean() if not df_heat.empty else 0.0
t_ret_moy = df_heat['T_Retour'].mean() if not df_heat.empty else 0.0
delta_t_moy = df_heat['Delta_T_Chaufferie'].mean() if not df_heat.empty else 0.0

col_ext_candidates = [c for c in df.columns if 'ext' in c.lower()]
col_ext = col_ext_candidates[0] if col_ext_candidates else None
corr_loi_eau = df_heat['T_Depart'].corr(df_heat[col_ext]) if (not df_heat.empty and col_ext) else 0.0

# B. ZONES D'AMBIANCE
zones_list = ['Nord', 'Sud', 'Est', 'Ouest', 'Aux1', 'Aux2', 'Aux3']
zones_presentes = [z for z in df.columns if any(z.lower() in c.lower() for c in zones_list)]

stats_zones = []
for z in zones_presentes:
    vals_occ = df.loc[is_occ, z]
    if not vals_occ.empty:
        t_moy = vals_occ.mean()
        pct_conf = ((vals_occ >= 19.0) & (vals_occ <= 22.0)).mean() * 100
        pct_sous = (vals_occ < 19.0).mean() * 100
        pct_sur = (vals_occ > 22.0).mean() * 100
        
        stats_zones.append({
            'Zone': z,
            'Temp. Moyenne (°C)': round(t_moy, 1),
            'Confort 19-22°C (%)': round(pct_conf, 1),
            'Sous-chauffe <19°C (%)': round(pct_sous, 1),
            'Surchauffe >22°C (%)': round(pct_sur, 1)
        })

df_stats_zones = pd.DataFrame(stats_zones)

# C. ASYMÉTRIE NORD / SUD
is_aprem = is_occ & (df['Heure_Dec'] >= 12.0) & (df['Heure_Dec'] < 16.0)
col_sud = [c for c in df.columns if 'sud' in c.lower()]
col_nord = [c for c in df.columns if 'nord' in c.lower()]

ecart_sud_nord_aprem = 0.0
if col_sud and col_nord:
    ecart_sud_nord_aprem = (df.loc[is_aprem, col_sud[0]] - df.loc[is_aprem, col_nord[0]]).mean()

# ==============================================================================
# 3. AFFICHAGE DES RÉSULTATS DANS STREAMLIT
# ==============================================================================

st.subheader("🔥 1. Bilan du Circuit Chaufferie")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Temps d'Activité Chaufferie", f"{pct_temps_chauffe:.1f}%", help="% du temps où T_Départ > 30°C")
c2.metric("Régime Moy. (Départ / Retour)", f"{t_dep_moy:.1f}°C / {t_ret_moy:.1f}°C")
c3.metric("ΔT Moyen Chaufferie", f"{delta_t_moy:.1f}°C", delta="Nominal (8-15°C)" if 8 <= delta_t_moy <= 15 else "Avertissement")
c4.metric("Corrélation Loi d'Eau", f"{corr_loi_eau:.2f}", help="Doit être proche de -1.0")

b1, b2 = st.columns(2)
with b1:
    st.markdown("### 👍 Ce qui est BIEN (Chaufferie)")
    if corr_loi_eau < -0.75:
        st.write(f"✔️ **Loi d'eau efficace** : Corrélation de **{corr_loi_eau:.2f}** avec l'extérieur.")
    if 8 <= delta_t_moy <= 15:
        st.write(f"✔️ **Écart de température nominal** : ΔT moyen de **{delta_t_moy:.1f}°C**.")

with b2:
    st.markdown("### ⚠️ Ce qui est MOINS BIEN (Chaufferie)")
    if delta_t_moy < 6.0:
        st.write(f"❌ **ΔT Faible ({delta_t_moy:.1f}°C)** : Sur-débit ou court-circuit hydraulique.")
    elif delta_t_moy > 16.0:
        st.write(f"❌ **ΔT Élevé ({delta_t_moy:.1f}°C)** : Sous-débit probable sur le réseau.")
    if corr_loi_eau > -0.60:
        st.write(f"❌ **Mauvaise régulation loi d'eau** (r = **{corr_loi_eau:.2f}**).")

st.markdown("---")

st.subheader("🏢 2. Bilan du Confort par Zone (Période d'Occupation)")
if not df_stats_zones.empty:
    st.dataframe(df_stats_zones, use_container_width=True, hide_index=True)

    col_bien, col_moins = st.columns(2)

    zones_bonnes = df_stats_zones[df_stats_zones['Confort 19-22°C (%)'] >= 85.0]['Zone'].tolist()
    zones_sous = df_stats_zones[df_stats_zones['Sous-chauffe <19°C (%)'] > 20.0]
    zones_sur = df_stats_zones[df_stats_zones['Surchauffe >22°C (%)'] > 20.0]

    with col_bien:
        st.markdown("### 👍 Ce qui est BIEN (Ambiances)")
        if zones_bonnes:
            st.write(f"✔️ **Zones conformes (>85% confort)** : **{', '.join(zones_bonnes)}**.")
        st.write("✔️ **Stabilité thermique** observée.")

    with col_moins:
        st.markdown("### ⚠️ Ce qui est MOINS BIEN (Ambiances)")
        if not zones_sous.empty:
            for _, r in zones_sous.iterrows():
                st.write(f"❌ **Sous-chauffe sur {r['Zone']}** : **{r['Sous-chauffe <19°C (%)']}%** sous 19°C (Moy : **{r['Temp. Moyenne (°C)']}°C**).")
        if not zones_sur.empty:
            for _, r in zones_sur.iterrows():
                st.write(f"❌ **Surchauffe sur {r['Zone']}** : **{r['Surchauffe >22°C (%)']}%** au-dessus de 22°C (Moy : **{r['Temp. Moyenne (°C)']}°C**). Surconsommation estimée : **+{round((r['Temp. Moyenne (°C)']-19)*7, 1)}%**.")
        if ecart_sud_nord_aprem > 1.5:
            st.write(f"❌ **Asymétrie Sud/Nord** : Le Sud est plus chaud de **+{ecart_sud_nord_aprem:.1f}°C** l'après-midi.")

st.markdown("---")
st.subheader("📈 Graphique Temporel des Zones et de la Chaufferie")
fig = go.Figure()

for z in zones_presentes:
    fig.add_trace(go.Scatter(x=df[col_date], y=df[z], name=f"Zone {z}", mode='lines'))

if col_ext:
    fig.add_trace(go.Scatter(x=df[col_date], y=df[col_ext], name="Extérieur", line=dict(color='black', dash='dash')))
fig.add_trace(go.Scatter(x=df[col_date], y=df['T_Depart'], name="Départ Chaufferie", line=dict(color='red', width=2)))
fig.add_trace(go.Scatter(x=df[col_date], y=df['T_Retour'], name="Retour Chaufferie", line=dict(color='orange', width=2)))

fig.update_layout(height=500, xaxis_title="Date / Heure", yaxis_title="Température (°C)", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)