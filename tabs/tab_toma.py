import streamlit as st
import pandas as pd

import database
import logic
import reduccion
import reduccion_por_dosis
import reduccion_por_tiempo
from reduccion_por_tiempo import intervalo
from state import invalidate_config

import time

class TomaTab:
    def __init__(self, df):
        self.df = df

    def mostrar_registro(self):
        with st.expander("➕ REGISTRAR TOMA", expanded=False):
            c1, c2, c3 = st.columns(3)
            ml_dosis=self.df.iloc[-1]['ml'].max() if not self.df.empty else 3.2
            c1.number_input(
                "Dosis Consumida (ml):",
                0.1, 10.0,
                ml_dosis,
                help="...",
                key="dosis_toma"  # <--- Agregamos esta clave
            )
            c2.date_input("Fecha:", pd.Timestamp.now(tz='Europe/Madrid').date(), key="fecha_toma_input")
            c3.time_input("Hora:", pd.Timestamp.now(tz='Europe/Madrid').time(), key="hora_toma_input")

            if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
               try:
                   reduccion.guardar_toma(st.session_state.get("fecha_toma_input"),
                                               st.session_state.get("hora_toma_input"),
                                               st.session_state.get("dosis_toma"))
                   st.success("Registrado")
                   time.sleep(1)
                   invalidate_config()
                   st.cache_data.clear()
                   st.rerun()

               except Exception as e:
                   st.error(f"Error: {e}")

    def mostrar_metricas(self):
        ahora = pd.Timestamp.now(tz='Europe/Madrid')
        ultima_toma = self.df['timestamp'].max() if not self.df.empty else ahora
        ml_dosis = st.session_state.get("dosis_toma", 3.0)

        min_desde_ultima_toma = (ahora - ultima_toma).total_seconds() / 60

        # Guardar en estado si el botón está pulsado para cambiar el modo
        if "visualizacion_activa" not in st.session_state:
             st.session_state.visualizacion_activa = "tiempo"

        # Botones para alternar visualización
        c_btn = st.columns(1)[0]
        if st.session_state.visualizacion_activa == "tiempo":
            if c_btn.button("🔄 Ver Dosis"):
                st.session_state.visualizacion_activa = "dosis"
                st.rerun()
        else:
            if c_btn.button("🔄 Ver Tiempo"):
                st.session_state.visualizacion_activa = "tiempo"
                st.rerun()
        # Sobreescribir variable tipo_visualizacion con el estado
        tipo_visualizacion = "⏱️ Tiempo" if st.session_state.visualizacion_activa == "tiempo" else "💊 Dosis"

        # RECALCULAR CON EL NUEVO TIPO
        if tipo_visualizacion == "⏱️ Tiempo":
             # ... (lógica tiempo) ...
            saldo = reduccion_por_tiempo.mlAcumulados()
            ml_dosis = reduccion_por_tiempo.dosis_actual()
            intervalo_teorico= reduccion_por_tiempo.intervalo()
            mins_espera = reduccion_por_tiempo.minEspera(ml_dosis,saldo)

        else:
             ml_dosis=reduccion_por_dosis.dosis_actual()
             saldo = reduccion_por_dosis.mlAcumulados()
             intervalo_teorico= reduccion_por_dosis.intervalo()
             mins_espera = reduccion_por_dosis.minEspera(ml_dosis,saldo)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis", f"{ml_dosis:.2f} ml")
        m2.metric("Última hace", f"{int(min_desde_ultima_toma // 60)}h {int(min_desde_ultima_toma % 60)}m")
        m3.metric("Intervalo", f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m")
        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")
        m5.metric("Saldo", f"{saldo:.2f} ml", delta_color="normal" if saldo >= 0 else "inverse")
