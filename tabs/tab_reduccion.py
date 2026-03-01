import streamlit as st
import pandas as pd
import database
import reduccion
import reduccion_por_dosis
import logic
import time
from datetime import datetime

from state import invalidate_config


class ReduccionTab:
    def render(self):
        c1, c2, c3, c4 = st.columns(4)

        c1.number_input("Consumo diario actual (ml/día)", value=float(st.session_state.config.get("plan.ml_dia", 15.0)),
                        step=0.5, key="ml_dia_actual")

        # 2. Convertir a datetime.time para Streamlit
        # Sumamos el intervalo a una fecha base (00:00:00) y extraemos la hora (.time())
        intervalo_time = (pd.to_datetime(0) + pd.to_timedelta(st.session_state.config.get("consumo.intervalo_minutos", 120), unit='m')).time()

        c2.time_input("Intervalo en horas actual (horas)", value=intervalo_time, key="intervalo_dia_actual")

        c3.number_input("Dosis por toma actual (ml)", value=float(st.session_state.config.get("consumo.ml_dosis", 3.2)), step=0.1,
                        key="ml_dosis_actual")
        c4.number_input("Reducción Diaria deseada (ml)",
                        value=float(st.session_state.config.get("plan.reduccion_diaria", 1)), step=0.05,
                        format="%.2f", key="reduccion_diaria")

        c1, c2, c3, c4 = st.columns(4)
        if not st.session_state.config.get("plan.fecha_inicio_plan")  and c4.button("💾 NUEVO PLAN"):
            reduccion.crear_nuevo_plan(
                st.session_state.get("ml_dia_actual"),
                st.session_state.get("ml_dosis_actual"),
                st.session_state.get("intervalo_dia_actual"),
                st.session_state.get("reduccion_diaria"))
            st.success("Configuración del plan guardada.")
            invalidate_config()
            st.cache_data.clear()
            st.rerun()

        if st.session_state.config.get("plan.fecha_inicio_plan") and c4.button("💾 ACTUALIZAR PLAN"):
            reduccion.replanificar(
                st.session_state.get("ml_dia_actual"),
                st.session_state.get("ml_dosis_actual"),
                st.session_state.get("intervalo_dia_actual"),
                st.session_state.get("reduccion_diaria"))
            st.success("Configuración del plan guardada.")
            invalidate_config()
            st.cache_data.clear()
            st.rerun()
