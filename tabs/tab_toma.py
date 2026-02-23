import streamlit as st
import database
import logic
from logic import ahora
from config import config
import time

class TomaTab:
    def __init__(self, df):
        self.df = df

    def mostrar_registro(self):
        with st.expander("➕ REGISTRAR TOMA", expanded=False):
            c1, c2, c3 = st.columns(3)
            ml_dosis=self.df.iloc[-1]['ml'].max() if not self.df.empty else 3.2
            cant = c1.number_input(
                "Dosis Consumida (ml):",
                0.1, 10.0,
                ml_dosis,
                help="...",
                key="dosis_input"  # <--- Agregamos esta clave
            )
            f_sel = c2.date_input("Fecha:", ahora.date())
            h_sel = c3.time_input("Hora:", ahora.time())

            if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
               ingresos_tramo= logic.ingresosTramo()
               database.save_config({
                    "checkpoint_ingresos": float(config.get("checkpoint_ingresos", 0.0)) + ingresos_tramo,
                    "checkpoint_fecha": ahora.isoformat(),
                    "dosis": cant
               })
               try:
                   saldo= logic.saldo(self.df)
                   res = database.enviar_toma_api(f_sel.strftime('%d/%m/%Y'), h_sel.strftime('%H:%M:%S'), cant, saldo - cant)
                   if res.status_code == 200:
                       st.success("Registrado")
                       time.sleep(1)
                       st.rerun()
               except Exception as e:
                   st.error(f"Error: {e}")

    def mostrar_metricas(self):
        ultima_toma = self.df['timestamp'].max() if not self.df.empty else ahora
        ml_dosis = st.session_state.get("dosis_input")
        pasado_mins = (ahora - ultima_toma).total_seconds() / 60

        tasa_gen=logic.tasaGeneracion()
        saldo = logic.saldo(self.df)
        mins_espera = ((ml_dosis - saldo) / tasa_gen * 60) if saldo < ml_dosis and tasa_gen > 0 else 0
        int_teorico = int((ml_dosis / tasa_gen) * 60) if tasa_gen > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis", f"{ml_dosis:.2f} ml")
        m2.metric("Última hace", f"{int(pasado_mins // 60)}h {int(pasado_mins % 60)}m")
        m3.metric("Intervalo", f"{int_teorico // 60}h {int_teorico % 60}m")

        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")

        m5.metric("Saldo", f"{saldo:.2f} ml", delta_color="normal" if saldo >= 0 else "inverse")
