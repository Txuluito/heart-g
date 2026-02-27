from datetime import datetime

import streamlit as st
import pandas as pd

import logic
import reduccion_plan
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
            c2.date_input("Fecha:", pd.Timestamp.now(tz='Europe/Madrid').date(),key="fecha_toma")
            c3.time_input("Hora:", pd.Timestamp.now(tz='Europe/Madrid').time(),key="hora_toma")

            if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
               try:
                   reduccion_plan.guardar_toma(st.session_state.get("fecha_toma"),
                                               st.session_state.get("hora_toma"),
                                               st.session_state.get("dosis_toma"),
                                               logic.mlAcumulados())
                   st.success("Registrado")
                   time.sleep(1)
                   invalidate_config()
                   st.cache_data.clear()
                   st.rerun()

               except Exception as e:
                   st.error(f"Error: {e}")

    def mostrar_metricas(self):
        ahora =pd.Timestamp.now(tz='Europe/Madrid')
        ultima_toma = self.df['timestamp'].max() if not self.df.empty else ahora
        ml_dosis = st.session_state.get("dosis_toma")

        min_desde_ultima_toma = (ahora - ultima_toma).total_seconds() / 60

        fecha_inicio_plan = pd.to_datetime(st.session_state.config.get("fecha_inicio_plan")) if st.session_state.config.get("fecha_inicio_plan") else ahora

        if fecha_inicio_plan.tzinfo is None or fecha_inicio_plan.tzinfo.utcoffset(datetime.now()) is None:
            fecha_inicio_plan = fecha_inicio_plan.tz_localize('Europe/Madrid');


        ml_reduccion_diaria = float(st.session_state.config.get("reduccion_diaria", 0.5))
        ml_iniciales_plan = float(st.session_state.config.get("ml_iniciales_plan", 15.0))
        horas_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / 3600
        dias_flotantes = max(0.0, horas_desde_inicio / 24.0)
        objetivo_actual = max(0.0, ml_iniciales_plan - (ml_reduccion_diaria * dias_flotantes))
        tasa_gen= objetivo_actual / 24.0
        saldo = logic.mlAcumulados()
        mins_espera = ((ml_dosis - saldo) / tasa_gen * 60) if saldo < ml_dosis and tasa_gen > 0 else 0
        intervalo_teorico = int((ml_dosis / tasa_gen) * 60) if tasa_gen > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis", f"{st.session_state.get('dosis_toma'):.2f} ml")
        m2.metric("Última hace", f"{int(min_desde_ultima_toma // 60)}h {int(min_desde_ultima_toma % 60)}m")
        m3.metric("Intervalo", f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m")

        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")

        m5.metric("Saldo", f"{saldo:.2f} ml", delta_color="normal" if saldo >= 0 else "inverse")
