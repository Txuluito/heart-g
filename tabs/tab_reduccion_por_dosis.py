import streamlit as st
import pandas as pd
import database
import reduccion_por_dosis
import logic
import time
from datetime import datetime

class PlanificacionDosisTab:
    def __init__(self, df):
        self.df = df
        if 'config' not in st.session_state:
            st.session_state.config = database.get_config()
        self.config = st.session_state.config

    def render(self):
        self.render_configuracion()
        self.render_tabla()

    def render_configuracion(self):
        with st.expander("⚙️ CONFIGURAR PARÁMETROS", expanded=False):
            ahora = pd.Timestamp.now(tz='Europe/Madrid')
            c1, c2, c3, c4 = st.columns(4)
            
            # Fecha Inicio
            current_date_str = self.config.get("plan_fijo_start_date")
            try:
                val_date = pd.to_datetime(current_date_str).date() if current_date_str else ahora.date()
            except:
                val_date = ahora.date()

            new_date = c1.date_input("Fecha Inicio", value=val_date, key="fijo_date")

            # Intervalo (en horas)
            current_interval = float(self.config.get("dosis.intervalo_horas", 2.0))
            new_interval = c2.number_input("Intervalo (horas)", min_value=0.5, max_value=24.0, value=current_interval, step=0.25, key="fijo_interval")

            # Dosis Inicial
            current_dosis = float(self.config.get("dosis.dosis_inicial", 3.0))
            new_dosis = c3.number_input("Dosis Inicial (ml)", min_value=0.1, max_value=20.0, value=current_dosis, step=0.1, key="fijo_dosis")

            # Reducción de dosis diaria
            current_red = float(self.config.get("dosis.reduccion_dosis", 0.05))
            new_red = c4.number_input("Reducción Dosis/Día (ml)", min_value=0.0, max_value=5.0, value=current_red, step=0.05, format="%.2f", key="fijo_red")

            if st.button("💾 GUARDAR PLAN FIJO"):
                reduccion_por_dosis.crear_nuevo_plan(
                    new_dosis,
                    new_red,
                    new_interval
                )
                st.success("Configuración guardada")
                time.sleep(1)
                st.rerun()

    def render_tabla(self):
        if not self.config.get("plan_fijo_start_date"):
            st.info("Configura el plan para comenzar.")
            return

        df_plan = reduccion_por_dosis.obtener_datos_tabla()

        if df_plan.empty:
            st.warning("No hay datos para mostrar.")
            return

        # Formatear la fecha para visualización si es necesario
        df_plan['Fecha_Display'] = df_plan['Fecha'].dt.strftime("%d/%m/%Y")

        # Resaltar fila de hoy
        hoy_str = pd.Timestamp.now(tz='Europe/Madrid').ahora.strftime("%d/%m/%Y")

        def highlight_row(row):
            if row["Fecha"].strftime("%d/%m/%Y") == hoy_str:
                return ['background-color: rgba(255, 255, 0, 0.1)'] * len(row)
            return [''] * len(row)

        # Ocultar la columna Fecha original si solo queremos mostrar la formateada, o usar la formateada
        st.dataframe(
            df_plan.style.format({
                "Dosis Obj (ml)": "{:.3f}",
                "Objetivo (ml)": "{:.2f}",
                "Real (ml)": "{:.2f}"
            }).apply(highlight_row, axis=1),
            use_container_width=True,
            hide_index=True,
            height=500
        )
