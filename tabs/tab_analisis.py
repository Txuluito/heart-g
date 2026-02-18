import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logic
import database


def render(df_excel, resumen_bloques, media_3d):
    st.subheader("🧬 Bio-Análisis y Calibración")

    # Cargar configuración
    config = logic.load_config()
    saved_hl = config.get("hl", 0.75)
    saved_ka = config.get("ka", 3.0)

    # 1. Parámetros de simulación
    with st.expander("🧪 AJUSTES FARMACOCINÉTICOS", expanded=False):
        c1, c2 = st.columns(2)
        hl = c1.slider("Vida media (h)", 0.5, 4.0, float(saved_hl), help="Tiempo en el que la sustancia se reduce a la mitad")
        ka = c2.slider("Absorción (ka)", 0.5, 5.0, float(saved_ka), help="Velocidad de entrada en el sistema")

        if hl != saved_hl or ka != saved_ka:
            logic.save_config({"hl": hl, "ka": ka})

    # 2. Obtención de datos de Google Fit
    # Nota: Aquí llamamos a la función que ya tenías en main anteriormente
    try:
        df_fit = database.get_google_fit_data()  # Esta función debe estar en database.py
        df_completo = logic.rellenar_datos_sin_frecuencia(df_fit, df_excel)
        df_completo['ghb_active'] = logic.calcular_concentracion_dinamica(df_completo, df_excel, ka, hl)

        # 3. Gráfica Principal
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(go.Scatter(x=df_completo.index, y=df_completo['hr'],
                                 name="Pulso (LPM)", line=dict(color="#FF4B4B")), secondary_y=False)

        fig.add_trace(go.Scatter(x=df_completo.index, y=df_completo['ghb_active'],
                                 name="Nivel Estimado (ml)", fill='tozeroy',
                                 line=dict(color="rgba(0,150,255,0.5)")), secondary_y=True)

        fig.update_layout(height=400, hovermode="x unified", margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width='stretch')

        # 4. Gráfica de Tendencia (La de las barras de 3 días)
        st.markdown("---")
        if len(resumen_bloques) >= 2:
            df_t = resumen_bloques.iloc[1:4].iloc[::-1]
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_t.index, y=df_t['total_ml'], name="Consumo Diario"))
            fig_bar.add_trace(
                go.Scatter(x=df_t.index, y=[media_3d] * len(df_t), name="Media", line=dict(dash='dash', color='red')))
            fig_bar.update_layout(height=300, title="Consumo últimos 3 días")
            st.plotly_chart(fig_bar, width='stretch')

    except Exception as e:
        st.warning(f"Conecta Google Fit para ver el análisis cardíaco: {e}")