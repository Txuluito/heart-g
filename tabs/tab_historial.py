import streamlit as st
import pandas as pd

class HistorialTab:
    def __init__(self, df):
        self.df = df

    def _formatear_delta(self, x):
        if pd.isnull(x): return "---"
        total_segundos = int(x.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        return f"{horas}h {minutos}min"

    def render_tabla_historial(self):
        if not self.df.empty:
            df_hist = self.df.copy().sort_values('timestamp', ascending=True)
            df_hist['diff'] = df_hist['timestamp'].diff()
            df_hist['Intervalo Real'] = df_hist['diff'].apply(self._formatear_delta)

            df_display = df_hist.sort_values('timestamp', ascending=False)
            df_display['Fecha'] = df_display['timestamp'].dt.strftime('%d/%m/%Y')
            df_display['Hora'] = df_display['timestamp'].dt.strftime('%H:%M')
            df_display['Dosis'] = df_display['ml'].apply(lambda x: f"{x:.2f} ml")

            st.dataframe(df_display[['Fecha', 'Hora', 'Dosis', 'Intervalo Real']], width='stretch', hide_index=True)
        else:
            st.info("No hay datos registrados todavía.")

