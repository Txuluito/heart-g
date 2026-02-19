import streamlit as st
import pandas as pd
import database
import logic
import time

class ReductorTab:
    def __init__(self, df):
        self.df = df
        self.ahora = pd.Timestamp.now(tz='Europe/Madrid')
        self.config = logic.load_config()
        self.plan = logic.ReductionPlan(self.df, self.config)

    def _mostrar_registro(self):
        with st.expander("➕ REGISTRAR TOMA", expanded=False):
            c1, c2, c3 = st.columns(3)
            cant = c1.number_input("Cantidad (ml):", 0.1, 10.0, self.plan.dosis)
            f_sel = c2.date_input("Fecha:", self.ahora.date())
            h_sel = c3.time_input("Hora:", self.ahora.time())

            if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
                logic.save_config({
                    "checkpoint_ingresos": self.plan.checkpoint_ingresos + self.plan.ingresos_tramo,
                    "checkpoint_fecha": self.ahora.isoformat(),
                    "dosis": cant
                })
                try:
                    res = database.enviar_toma_api(f_sel.strftime('%d/%m/%Y'), h_sel.strftime('%H:%M:%S'), cant, self.plan.saldo - cant)
                    if res.status_code == 200:
                        st.success("Registrado")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    def _mostrar_metricas(self):
        ultima_toma = self.df['timestamp'].max() if not self.df.empty else self.ahora
        pasado_mins = (self.ahora - ultima_toma).total_seconds() / 60
        tasa_gen = self.plan.objetivo_actual / 24.0

        mins_espera = ((self.plan.dosis - self.plan.saldo) / tasa_gen * 60) if self.plan.saldo < self.plan.dosis and tasa_gen > 0 else 0
        int_teorico = int((self.plan.dosis / tasa_gen) * 60) if tasa_gen > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Dosis", f"{self.plan.dosis:.2f} ml")
        m2.metric("Última hace", f"{int(pasado_mins // 60)}h {int(pasado_mins % 60)}m")
        m3.metric("Intervalo", f"{int_teorico // 60}h {int_teorico % 60}m")

        if mins_espera > 0:
            m4.metric("Siguiente en", f"{int(mins_espera // 60)}h {int(mins_espera % 60)}m", delta="Esperando", delta_color="inverse")
        else:
            m4.metric("Siguiente", "¡LISTO!", delta="Disponible")

        m5.metric("Saldo", f"{self.plan.saldo:.2f} ml", delta_color="normal" if self.plan.saldo >= 0 else "inverse")

    def _configurar_nuevo_plan(self):
        with st.expander("📈 CONFIGURAR PLAN DE REDUCCIÓN"):
            c1, c2, c3, c4 = st.columns(4)

            # Control para la fecha de inicio del plan
            new_start_date = c1.date_input(
                "Fecha de Inicio",
                value=self.plan.plan_start_dt.date()
            )

            # Control para la cantidad inicial
            new_start_amount = c2.number_input(
                "Cantidad Inicial (ml/día)",
                value=self.plan.start_amount,
                step=0.5
            )

            # Control para la reducción diaria
            new_rate = c3.number_input(
                "Reducción Diaria (ml)",
                value=self.plan.rate,
                step=0.05,
                format="%.2f"
            )

            # Control para la dosis por defecto
            new_dosis = c4.number_input(
                "Dosis Defecto (ml)",
                value=self.plan.dosis,
                step=0.1
            )

            if st.button("💾 GUARDAR CONFIGURACIÓN DEL PLAN"):
                logic.save_config({
                    "plan_start_date": new_start_date.isoformat(),  # Guardamos la nueva fecha
                    "plan_start_amount": new_start_amount,
                    "reduction_rate": new_rate,
                    "dosis": new_dosis
                })
                st.success("Configuración del plan guardada.")
                time.sleep(1)
                st.rerun()

    def _mostrar_ajustes_rapidos(self):
        with st.expander("⚙️ AJUSTES"):
            if st.button("💾 REINICIAR PLAN / BALANCE A 0"):
                logic.save_config({
                    "plan_start_date": self.ahora.isoformat(),
                    "checkpoint_ingresos": 0.0,
                    "checkpoint_fecha": self.ahora.isoformat()
                })
                st.rerun()

    def render(self):
        st.header("📉 Panel Reductor")

        self._mostrar_registro()
        self._mostrar_metricas()

        st.markdown("---")
        self._configurar_nuevo_plan()

        col_h1, col_h2 = st.columns([3, 1])
        mostrar_futuro = col_h2.checkbox("Ver futuro", value=False)
        df_seg = logic.calcular_seguimiento_plan(self.df, self.config)
        if not mostrar_futuro:
            df_seg = df_seg[df_seg['Estado'] != "🔮 Futuro"]

        st.dataframe(
            df_seg.style.apply(
                lambda r: ['background-color: rgba(255, 75, 75, 0.1)'] * len(r) if r['Fecha'] == self.ahora.strftime('%d/%m/%Y') else [''] * len(r), axis=1
            ).format({"Objetivo (ml)": "{:.2f}", "Real (ml)": "{:.2f}", "Reducción Plan": "{:.2f}"}),
            width='stretch', hide_index=True
        )

        self._mostrar_ajustes_rapidos()

def render(df):
    tab = ReductorTab(df)
    tab.render()
