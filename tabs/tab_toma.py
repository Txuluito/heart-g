import streamlit as st
import pandas as pd

import database
import logic
import reduccion
import reduccion_por_dosis
import reduccion_por_tiempo
from state import invalidate_config

import time

class TomaTab:
    def __init__(self, df):
        self.df = df

    def mostrar_registro(self):
        with st.expander("➕ REGISTRAR TOMA", expanded=False):
            c1, c2, c3 = st.columns(3)
            ml_dosis_input=self.df.iloc[-1]['ml'].max() if not self.df.empty else 3.2
            c1.number_input(
                "Dosis Consumida (ml):",
                0.1, 10.0,
                ml_dosis_input,
                help="...",
                key="dosis_toma"
            )
            c2.date_input("Fecha:", pd.Timestamp.now(tz='Europe/Madrid').date(), key="fecha_toma_input", format="DD/MM/YYYY")
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
        min_desde_ultima_toma = (ahora - ultima_toma).total_seconds() / 60

        # Cargar preferencia guardada si no está en sesión
        if "visualizacion_activa" not in st.session_state:
             st.session_state.visualizacion_activa = st.session_state.config.get("visualizacion_activa", "tiempo")

        # --- CABECERA CON TÍTULO Y BOTÓN ---
        col_titulo, col_boton = st.columns([3, 1])

        with col_titulo:
            if st.session_state.visualizacion_activa == "tiempo":
                st.subheader("Modo: ⏱️ Plan por Tiempo")
            else:
                st.subheader("Modo: 💊 Plan por Dosis")

        with col_boton:
            if st.session_state.visualizacion_activa == "tiempo":
                if st.button("🔄 Cambiar a Dosis"):
                    nuevo_modo = "dosis"
                    st.session_state.visualizacion_activa = nuevo_modo
                    # Guardar preferencia
                    database.save_config({"visualizacion_activa": nuevo_modo})
                    st.session_state.config["visualizacion_activa"] = nuevo_modo
                    st.rerun()
            else:
                if st.button("🔄 Cambiar a Tiempo"):
                    nuevo_modo = "tiempo"
                    st.session_state.visualizacion_activa = nuevo_modo
                    # Guardar preferencia
                    database.save_config({"visualizacion_activa": nuevo_modo})
                    st.session_state.config["visualizacion_activa"] = nuevo_modo
                    st.rerun()
        
        st.markdown("---") # Separador visual

        tipo_visualizacion = st.session_state.visualizacion_activa

        if tipo_visualizacion == "tiempo":
            saldo = reduccion_por_tiempo.mlAcumulados()
            ml_dosis, intervalo_teorico, mins_espera, mins_espera_saldo = reduccion_por_tiempo.calcular_metricas_tiempo(self.df)
        else: # 'dosis'
             saldo = reduccion_por_dosis.mlAcumulados()
             ml_dosis, intervalo_teorico, mins_espera, mins_espera_saldo = reduccion_por_dosis.calcular_metricas_dosis(self.df)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis Plan", f"{ml_dosis:.2f} ml")
        m2.metric("Última hace", f"{int(min_desde_ultima_toma // 60)}h {int(min_desde_ultima_toma % 60)}m")
        m3.metric("Intervalo Plan", f"{int(intervalo_teorico // 60)}h {int(intervalo_teorico % 60)}m")
        
        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")
        
        # Mostrar tiempo de espera por saldo si es relevante
        if mins_espera_saldo > 0:
            m4.caption(f"⏳ Saldo: {int(mins_espera_saldo // 60)}h {int(mins_espera_saldo % 60)}m")

        m5.metric("Saldo", f"{saldo:.2f} ml", delta_color="normal" if saldo >= 0 else "inverse")
