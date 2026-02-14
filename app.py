import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as px
from plotly.subplots import make_subplots

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Caffeine & Heart Rate Analyzer", layout="wide")
st.title("☕ Bio-Análisis: Cafeína vs. Frecuencia Cardíaca")

# --- SIDEBAR: CARGA DE DATOS ---
with st.sidebar:
    st.header("Configuración")
    file_hr = st.file_uploader("Subir CSV de Reloj (HR)", type=['csv'])
    file_caf = st.file_uploader("Subir Excel de Cafeína", type=['xlsx'])
    half_life = st.slider("Vida media cafeína (horas)", 3.0, 7.0, 5.0)

# --- LÓGICA DE PROCESAMIENTO ---
if file_hr and file_caf:
    # 1. Cargar y limpiar
    df_hr = pd.read_csv(file_hr, parse_dates=['timestamp']).set_index('timestamp')
    df_hr = df_hr.resample('1T').mean().interpolate()  # Normalizar a 1 min

    df_caf = pd.read_excel(file_caf)
    df_caf['hora'] = pd.to_datetime(df_caf['hora'])

    # 2. Calcular decaimiento (Vectorizado para velocidad)
    k = np.log(2) / half_life
    timeline = df_hr.index
    concentracion = np.zeros(len(timeline))

    for _, event in df_caf.iterrows():
        delta_t = (timeline - event['hora']).total_seconds() / 3600
        mask = delta_t >= 0
        concentracion[mask] += event['mg'] * np.exp(-k * delta_t[mask])

    df_hr['caf_active'] = concentracion

    # --- VISUALIZACIÓN ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Línea de Ritmo Cardíaco
    fig.add_trace(
        go.Scatter(x=df_hr.index, y=df_hr['hr'], name="Pulsaciones (LPM)", line=dict(color="#FF4B4B")),
        secondary_y=False
    )

    # Área de Cafeína
    fig.add_trace(
        go.Scatter(x=df_hr.index, y=df_hr['caf_active'], name="Cafeína Activa (mg)",
                   fill='tozeroy', line=dict(color="rgba(139, 69, 19, 0.4)")),
        secondary_y=True
    )

    fig.update_layout(title_text="Correlación Temporal")
    st.plotly_chart(fig, use_container_width=True)

    # --- MÉTRICAS PRO ---
    col1, col2 = st.columns(2)
    correlation = df_hr['hr'].corr(df_hr['caf_active'])
    col1.metric("Correlación de Pearson", f"{correlation:.2f}")
    col2.metric("Pico de Cafeína", f"{df_hr['caf_active'].max():.1f} mg")

else:
    st.info("Por favor, sube tus archivos en el panel lateral para comenzar el análisis.")


# def calcular_cafeina_activa(timeline, dosis_events, half_life=5):
#     k = np.log(2) / half_life
#     concentracion = np.zeros(len(timeline))
#
#     for _, evento in dosis_events.iterrows():
#         t_dosis = evento['hora']
#         mg = evento['mg']
#         # Calcular decaimiento desde el momento de la dosis en adelante
#         delta_t = (timeline - t_dosis).total_seconds() / 3600
#         mask = delta_t >= 0
#         concentracion[mask] += mg * np.exp(-k * delta_t[mask])
#
#     return concentracion
#
#
# # Aplicar al dataframe maestro
# df_hr['caf_mg_active'] = calcular_cafeina_activa(df_hr.index, df_caf)