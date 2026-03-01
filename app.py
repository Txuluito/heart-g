import streamlit as st
import database
from tabs.tab_analisis import AnalisisTab
from tabs.tab_historial import HistorialTab
from tabs.tab_reduccion import ReduccionTab
from tabs.tab_reduccion_por_tiempo import PlanificacionTiempoTab
from tabs.tab_reduccion_por_dosis import PlanificacionDosisTab
from tabs.tab_toma import TomaTab
import logging
from state import load_config # <-- Importa la nueva función

# --- CONFIGURACIÓN DE LOGGING --- (si no la tienes ya)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- CARGA INICIAL DEL ESTADO ---
load_config() # <-- Llama a la función aquí
# ------------------------------


st.set_page_config(page_title="Reductor GHB", layout="wide")
st.title("📉 Reductor GHB")
# try:
excel_data = database.get_excel_data()
t1, t2, t3, t4, t5, t6 = st.tabs(["📉 Tomas", "⏱️ Planificador","⏱️ Reducción por Tiempos", "💊 Reducción por Dosis", "🧬 Bio-Análisis", "📜 Historial"])
with t1:
    tab = TomaTab(excel_data)
    st.header("📉 Panel de Tomas")
    tab.mostrar_registro()
    tab.mostrar_metricas()
    st.markdown("---")
with t2:
    st.header("⏱️ Planificación:")
    tab = ReduccionTab()
    tab.render()
with t3:
    st.header("⏱️ Planificación: Reducción por Tiempo")
    tab = PlanificacionTiempoTab()
    tab.render()
with t4:
    st.header("💊 Planificación: Reducción por Dosis")
    tab = PlanificacionDosisTab()
    tab.render()
with t5:
    st.subheader("🧬 Bio-Análisis y Calibración")
    tab = AnalisisTab(excel_data)
    ka, hl = tab.render_parametros_simulacion()
    tab.render_grafica(hl, ka)
with t6:
    st.subheader("📜 Historial Detallado de Tomas")
    tab = HistorialTab(excel_data)
    tab.render_tabla_historial()
