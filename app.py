import streamlit as st
import logic
import database
from tabs import tab_analisis
from tabs import tab_historial
from tabs import tab_reductor

# Configuración
st.set_page_config(page_title="Reductor GHB", layout="wide")
st.title("📉 Reductor GHB")

df = database.get_excel_data()
resumen = logic.calcular_resumen_bloques(df)
media_3d = logic.obtener_media_3d(resumen)

# Interfaz de Tabs
t1, t2, t3 = st.tabs(["📉 Reductor", "📊 Análisis", "📜 Historial"])
with t1:
    tab_reductor.render(df)
with t2:
    tab_analisis.render(df, resumen, media_3d)
with t3:
    tab_historial.render(df)
