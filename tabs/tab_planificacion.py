import streamlit as st
import pandas as pd
import database
import logic
import reduccion_plan
from state import invalidate_config
class PlanificacionTab:
    def __init__(self, df):
        self.df = df

    def render_configurar_plan(self):
        with st.expander("📈 CONFIGURAR PLAN DE REDUCCIÓN"):
            c1, c2, c3 = st.columns(3)

            # Control para la cantidad inicial
            c1.number_input(
                "Cantidad Inicial (ml/día)",
                value=float(st.session_state.config.get("ml_iniciales_plan", 15.0)),
                step=0.5,
                key = "cantidad_inicial"
            )

            # Control para la reducción diaria
            c2.number_input(
                "Reducción Diaria (ml)",
                value=float(st.session_state.config.get("reduccion_diaria", 1)),
                step=0.05,
                format="%.2f",
                key = "reduccion_diaria"
            )

            # Control para la dosis por defecto

            c3.number_input(
                "Dosis Defecto (ml)",
                value= float(st.session_state.config.get("dosis_media", 3.2)),
                step=0.1,
                key = "dosis_media"
            )

            c1, c2 = st.columns(2)

            if c1.button("💾 ACTUALIZAR PLAN"):
                reduccion_plan.replanificar(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"),
                    logic.mlAcumulados())
                st.success("Configuración del plan guardada.")
                invalidate_config()
                st.cache_data.clear()
                st.rerun()
            if c2.button("💾 NUEVO PLAN"):
                reduccion_plan.crear_nuevo_plan(
                    st.session_state.get("dosis_media"),
                    st.session_state.get("reduccion_diaria"),
                    st.session_state.get("cantidad_inicial"))
                # logic.crear_plan(self.df,config)
                invalidate_config()
                st.cache_data.clear()
                st.rerun()

    def render(self):
        st.header("📅 Planificación de Reducción")
        self.render_configurar_plan()
        self.render_tabla_plan()

    def render_tabla_plan(self):
        if st.session_state.config.get("fecha_inicio_plan"):
            df_seg = reduccion_plan.obtener_datos_tabla()
            df_seg['Fecha'] = df_seg['Fecha'].dt.strftime('%d/%m/%Y')
            st.dataframe(
                df_seg.style.apply(
                    lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == pd.Timestamp.now(tz='Europe/Madrid').strftime(
                        '%d/%m/%Y') else [''] * len(r), axis=1
                ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
                width='stretch', hide_index=True
            )
        else:
            st.warning("No se ha definido plan")
