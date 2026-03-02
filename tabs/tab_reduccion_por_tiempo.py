import streamlit as st
import pandas as pd

class PlanificacionTiempoTab:
    def __init__(self, df_tomas):
        self.df_tomas = df_tomas

    def render(self):
        if not st.session_state.config.get("plan.fecha_inicio_plan"):
            st.info("Configura el plan para comenzar.")
            return
        df_plan = st.session_state.df_tiempos.copy()
        
        # Asegurar formato de fecha para visualización y filtrado
        df_plan['Fecha_dt'] = pd.to_datetime(df_plan['Fecha'], errors='coerce')
        df_plan['Fecha'] = df_plan['Fecha_dt'].dt.strftime('%d/%m/%Y')

        def highlight_row(row):
            if row["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%d/%m/%Y'):
                return ['background-color: rgba(255, 75, 75, 0.1)'] * len(row)
            return [''] * len(row)

        event = st.dataframe(
            df_plan.style.format({
            "Objetivo (ml)": "{:.2f}",
            "Real (ml)": "{:.2f}",
            "Dosis": "{:.2f}"
        }).apply(highlight_row, axis=1),
            width='stretch',
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            fecha_seleccionada = df_plan.iloc[idx]['Fecha_dt'].date()
            
            st.markdown(f"### 📅 Tomas del día {fecha_seleccionada.strftime('%d/%m/%Y')}")
            
            # Filtrar tomas
            if not self.df_tomas.empty:
                tomas_dia = self.df_tomas[self.df_tomas['timestamp'].dt.date == fecha_seleccionada].copy()
                if not tomas_dia.empty:
                    tomas_dia['Hora'] = tomas_dia['timestamp'].dt.strftime('%H:%M')
                    tomas_dia['Dosis'] = tomas_dia['ml'].apply(lambda x: f"{x:.2f} ml")
                    st.dataframe(tomas_dia[['Hora', 'Dosis']], hide_index=True)
                else:
                    st.info("No hay tomas registradas para este día.")
            else:
                st.info("No hay datos de tomas disponibles.")
