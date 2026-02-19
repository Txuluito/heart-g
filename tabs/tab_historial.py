import streamlit as st
import pandas as pd
import database
import time
import logic

class HistorialTab:
    def __init__(self, df):
        self.df = df

    def _formatear_delta(self, x):
        if pd.isnull(x): return "---"
        total_segundos = int(x.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        return f"{horas}h {minutos}min"

    def _render_tabla_historial(self):
        st.subheader("📜 Historial Detallado de Tomas")
        if not self.df.empty:
            df_hist = self.df.copy().sort_values('timestamp', ascending=True)
            df_hist['diff'] = df_hist['timestamp'].diff()
            df_hist['Intervalo Real'] = df_hist['diff'].apply(self._formatear_delta)

            df_display = df_hist.sort_values('timestamp', ascending=False)
            df_display['Fecha'] = df_display['timestamp'].dt.strftime('%d/%m/%Y')
            df_display['Hora'] = df_display['timestamp'].dt.strftime('%H:%M')
            df_display['Cantidad'] = df_display['ml'].apply(lambda x: f"{x:.2f} ml")

            st.dataframe(df_display[['Fecha', 'Hora', 'Cantidad', 'Intervalo Real']], use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos registrados todavía.")

    def _render_metricas_logros(self):
        st.markdown("---")
        if not self.df.empty:
            df_valid_diffs = self.df.copy().sort_values('timestamp', ascending=True)
            df_valid_diffs['diff'] = df_valid_diffs['timestamp'].diff().dropna()

            if not df_valid_diffs['diff'].empty:
                col_h1, col_h2 = st.columns(2)
                media_int_total = df_valid_diffs['diff'].mean()
                max_int = df_valid_diffs['diff'].max()
                col_h1.metric("Intervalo Medio Real", self._formatear_delta(media_int_total))
                col_h2.metric("Récord de espera", self._formatear_delta(max_int))

    def _render_zona_peligro(self):
        st.markdown("---")
        with st.expander("⚠️ ZONA DE PELIGRO", expanded=False):
            c_del, c_bal = st.columns(2)
            with c_del:
                st.write("¿La última toma es un error?")
                if st.button("🗑️ BORRAR ÚLTIMA TOMA"):
                    if database.eliminar_ultima_toma():
                        st.success("Fila eliminada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("No se pudo borrar la toma.")
            
            with c_bal:
                st.write("Ajuste manual de saldo")
                # Obtenemos el plan para saber el saldo actual y proponerlo
                config = logic.load_config()
                plan = logic.ReductionPlan(self.df, config)

                nuevo_saldo = st.number_input("Nuevo Saldo Disponible:", value=plan.saldo, step=0.1, format="%.2f")
                if st.button("🔧 Aplicar Ajuste de Saldo"):
                    gastos_totales = self.df['ml'].sum()
                    nuevo_checkpoint_ingresos = nuevo_saldo + gastos_totales
                    ahora_ajuste = pd.Timestamp.now(tz='Europe/Madrid')

                    logic.save_config({
                        "checkpoint_ingresos": nuevo_checkpoint_ingresos,
                        "checkpoint_fecha": ahora_ajuste.isoformat()
                    })
                    st.cache_data.clear()
                    st.success(f"Saldo actualizado a {nuevo_saldo:.2f} ml")
                    time.sleep(1)
                    st.rerun()

    def _render_filtros_visualizacion(self):
        st.markdown("---")
        st.subheader("📅 Filtros de Visualización")
        if not self.df.empty:
            c_f1, c_f2 = st.columns(2)
            fecha_inicio = c_f1.date_input("Fecha Inicio", self.df['timestamp'].min().date())
            fecha_fin = c_f2.date_input("Fecha Fin", pd.Timestamp.now(tz='Europe/Madrid').date())

            mask = (self.df['timestamp'].dt.date >= fecha_inicio) & (self.df['timestamp'].dt.date <= fecha_fin)
            df_filtrado = self.df.loc[mask]
            resumen_filtrado = logic.calcular_resumen_bloques(df_filtrado)

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.subheader("📊 Resumen Bloques")
                st.dataframe(resumen_filtrado, use_container_width=True)
            with col_t2:
                st.subheader("🕒 Tomas Filtradas")
                st.dataframe(df_filtrado[['fecha', 'hora', 'ml']], use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos para filtrar.")

    def render(self):
        self._render_tabla_historial()
        self._render_metricas_logros()
        self._render_zona_peligro()
        self._render_filtros_visualizacion()

def render(df):
    tab = HistorialTab(df)
    tab.render()
