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
import streamlit.components.v1 as components
import constants

# --- CONFIGURACIÓN DE LOGGING --- (si no la tienes ya)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- CARGA INICIAL DEL ESTADO ---
load_config() # <-- Llama a la función aquí
# ------------------------------


st.set_page_config(page_title="Reductor GHB", layout="wide")
st.title("📉 Reductor GHB")
# try:
excel_data = database.get_excel_data()

# Definir pestañas dinámicamente
tabs_labels = ["📉 Tomas", "⏱️ Planificador", "⏱️ Reducción por Tiempos", "💊 Reducción por Dosis"]
if constants.SHOW_BIO_ANALYSIS:
    tabs_labels.append("🧬 Bio-Análisis")
tabs_labels.append("📜 Historial")

tabs = st.tabs(tabs_labels)

# Asignar pestañas a variables
t_toma = tabs[0]
t_plan = tabs[1]
t_red_tiempo = tabs[2]
t_red_dosis = tabs[3]

idx = 4
t_bio = None
if constants.SHOW_BIO_ANALYSIS:
    t_bio = tabs[idx]
    idx += 1

t_historial = tabs[idx]

with t_toma:
    tab = TomaTab(excel_data)
    tab.mostrar_registro()
    tab.mostrar_metricas()
    st.markdown("---")
with t_plan:
    st.header("⏱️ Planificación:")
    tab = ReduccionTab()
    tab.render()
with t_red_tiempo:
    st.header("⏱️ Planificación: Reducción por Tiempo")
    tab = PlanificacionTiempoTab()
    tab.render()
with t_red_dosis:
    st.header("💊 Planificación: Reducción por Dosis")
    tab = PlanificacionDosisTab()
    tab.render()

if t_bio:
    with t_bio:
        st.subheader("🧬 Bio-Análisis y Calibración")
        tab = AnalisisTab(excel_data)
        ka, hl = tab.render_parametros_simulacion()
        tab.render_grafica(hl, ka)

with t_historial:
    st.subheader("📜 Historial Detallado de Tomas")
    tab = HistorialTab(excel_data)
    tab.render_tabla_historial()

# Auto-refresco cada 5 minutos (300000 ms)
components.html(
    """
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 300000);
    </script>
    """,
    height=0,
    width=0
)
