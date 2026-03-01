import streamlit as st
import pandas as pd

class PlanificacionDosisTab:
    def render(self):
        if not st.session_state.config.get("plan.fecha_inicio_plan"):
            st.info("Configura el plan para comenzar.")
            return
        df_plan = st.session_state.df_dosis.copy()
        df_plan['Fecha'] = pd.to_datetime(df_plan['Fecha'], errors='coerce')
        df_plan['Fecha'] = df_plan['Fecha'].dt.strftime('%d/%m/%Y')

        def highlight_row(row):
            if row["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%d/%m/%Y'):
                return ['background-color: rgba(255, 255, 0, 0.1)'] * len(row)
            return [''] * len(row)

        st.dataframe(
            df_plan.style.format({
            "Objetivo (ml)": "{:.2f}",
            "Real (ml)": "{:.2f}",
            "Dosis": "{:.2f}"
        }).apply(highlight_row, axis=1),
            width='stretch',
            hide_index=True
        )
