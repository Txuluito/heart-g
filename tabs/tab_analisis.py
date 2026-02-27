import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import numpy as np
import logic
import database
from plotly.subplots import make_subplots


class AnalisisTab:
    def __init__(self, df_excel):
        self.df_excel = df_excel
        self.resumen_bloques = logic.calcular_resumen_bloques(df_excel)
        # self.media_3d =  self.obtener_media_3d(self.resumen_bloques)

    def render_parametros_simulacion(self):
        with st.expander("🧪 AJUSTES FARMACOCINÉTICOS", expanded=False):
            saved_hl = st.session_state.config.get("hl", 0.75)
            saved_ka = st.session_state.config.get("ka", 3.0)

            c1, c2 = st.columns(2)
            hl = c1.slider("Vida media (h)", 0.5, 4.0, float(saved_hl), help="Tiempo en el que la sustancia se reduce a la mitad")
            ka = c2.slider("Absorción (ka)", 0.5, 5.0, float(saved_ka), help="Velocidad de entrada en el sistema")

            if hl != saved_hl or ka != saved_ka:
                database.save_config({"hl": hl, "ka": ka})

            return ka, hl

    def _render_grafica_principal(self, df_completo):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=df_completo.index, y=df_completo['hr'],
                                 name="Pulso (LPM)", line=dict(color="#FF4B4B")), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_completo.index, y=df_completo['ghb_active'],
                                 name="Nivel Estimado (ml)", fill='tozeroy',
                                 line=dict(color="rgba(0,150,255,0.5)")), secondary_y=True)
        fig.update_layout(height=400, hovermode="x unified", margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width='stretch')

    def _render_grafica_tendencia(self):
        st.markdown("---")
        if len(self.resumen_bloques) >= 2:
            df_t = self.resumen_bloques.iloc[1:4].iloc[::-1]
            media_3d=self.obtener_media_3d(self.resumen_bloques)
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_t.index, y=df_t['total_ml'], name="Consumo Diario"))
            fig_bar.add_trace(go.Scatter(x=df_t.index, y=[media_3d] * len(df_t), name="Media", line=dict(dash='dash', color='red')))
            fig_bar.update_layout(height=300, title="Consumo últimos 3 días")
            st.plotly_chart(fig_bar, width='stretch')
    def render_grafica(self, hl: float, ka: float):
        try:
            df_fit = database.get_google_fit_data()
            df_completo = self.rellenar_datos_sin_frecuencia(df_fit, self.df_excel)
            df_completo['ghb_active'] = self.calcular_concentracion_dinamica(df_completo, self.df_excel, ka, hl)

            self._render_grafica_principal(df_completo)
            self._render_grafica_tendencia()

        except Exception as e:
            st.warning(f"Conecta Google Fit para ver el análisis cardíaco: {e}")
    def rellenar_datos_sin_frecuencia(self,df_fit, df_excel):
        ahora=pd.Timestamp.now(tz='Europe/Madrid')
        # Determinar el punto de inicio
        if df_fit.empty:
            inicio = df_excel['timestamp'].min() if not df_excel.empty else ahora
        else:
            inicio = df_fit.index.max()

        if ahora.floor('1min') > inicio:
            rango = pd.date_range(start=inicio + pd.Timedelta(minutes=1), end=ahora.floor('1min'), freq='1min')
            df_relleno = pd.DataFrame(index=rango)
            return pd.concat([df_fit, df_relleno]).sort_index()
        return df_fit

    def calcular_concentracion_dinamica(self,df_final, df_excel, ka_val, hl_val):
        k_el = np.log(2) / hl_val
        timeline = df_final.index
        concentracion = np.zeros(len(timeline))

        for _, row in df_excel.iterrows():
            # Calcular tiempo transcurrido desde cada toma en horas
            t = (timeline - row['timestamp']).total_seconds() / 3600
            mask = t >= 0

            # Evitar división por cero si ka == k_el
            curr_ka = ka_val if ka_val != k_el else ka_val + 0.01

            factor_escala = curr_ka / (curr_ka - k_el)
            curva = row['ml'] * factor_escala * (np.exp(-k_el * t[mask]) - np.exp(-curr_ka * t[mask]))
            concentracion[mask] += curva

        res = pd.Series(concentracion, index=timeline)
        res[res < 0.05] = 0  # Limpiar ruido visual bajo
        return res

    def obtener_media_3d(self,resumen):
        if len(resumen) >= 4:
            return resumen.iloc[1:4]['total_ml'].mean()
        elif len(resumen) >= 2:
            return resumen.iloc[1]['total_ml']
        return 15.0  # Valor por defecto
