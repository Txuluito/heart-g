import streamlit as st

import database
import logic
import pandas as pd

import reduccion_plan
from config import config
from logic import ahora
import time

class PlanificacionTab:
    def __init__(self, df):
        self.df = df

    def render_configurar_plan(self):
        with st.expander("📈 CONFIGURAR PLAN DE REDUCCIÓN"):
            c1, c2, c3, c4 = st.columns(4)

            # Control para la cantidad inicial
            c2.number_input(
                "Cantidad Inicial (ml/día)",
                value=float(config.get("plan_start_amount", 15.0)),
                step=0.5,
                key = "cantidad_inicial"
            )

            # Control para la reducción diaria
            c3.number_input(
                "Reducción Diaria (ml)",
                value=float(config.get("reduction_rate", 0.5)),
                step=0.05,
                format="%.2f",
                key = "reduccion_diaria"
            )

            # Control para la dosis por defecto

            c4.number_input(
                "Dosis Defecto (ml)",
                value= float(config.get("dosis", 3.2)),
                step=0.1,
                key = "dosis_media"
            )
            if st.button("💾 GUARDAR CONFIGURACIÓN DEL PLAN"):
                logic.mlAcumulados()
                reduccion_plan.replanificar(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"),
                    logic.mlAcumulados())
                st.success("Configuración del plan guardada.")
                time.sleep(1)
                st.rerun()
            if config.get("plan_start_date") and st.button("💾 REINICIAR PLAN / BALANCE A 0"):
               database.save_config({
                    "plan_start_date": ahora.isoformat(),
                    "checkpoint_ml": 0.0,
                    "checkpoint_fecha": ahora.isoformat()
               })
               st.rerun()
            if st.button("💾 CREAR PLAN"):
                reduccion_plan.crear_nuevo_plan(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"),
                    logic.mlAcumulados())
                # logic.crear_plan(self.df,config)
                st.rerun()

    def render(self):
        st.header("📅 Planificación de Reducción")
        self.render_configurar_plan()
        self.render_tabla_plan()

    def render_tabla_plan(self):
        if config.get("plan_start_date"):
            df_seg = reduccion_plan.obtener_datos_tabla()
            st.dataframe(
                df_seg.style.apply(
                    lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == ahora.strftime(
                        '%d/%m/%Y') else [''] * len(r), axis=1
                ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
                width='stretch', hide_index=True
            )
        else:
            st.warning("No se ha definido plan")
