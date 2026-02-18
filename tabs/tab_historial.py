import streamlit as st
import pandas as pd
import database
import time
import logic

def render(df):
    st.subheader("📜 Historial Detallado de Tomas")

    if not df.empty:
        # 1. Preparar los datos
        df_hist = df.copy()

        # El DataFrame ya viene ordenado, pero aseguramos cronología para el cálculo de diff
        df_hist = df_hist.sort_values('timestamp', ascending=True)
        df_hist['diff'] = df_hist['timestamp'].diff()

        def formatear_delta(x):
            if pd.isnull(x): return "---"
            total_segundos = int(x.total_seconds())
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            return f"{horas}h {minutos}min"

        df_hist['Intervalo Real'] = df_hist['diff'].apply(formatear_delta)

        # 2. Preparar tabla para visualización (más reciente primero)
        df_display = df_hist.sort_values('timestamp', ascending=False).copy()
        df_display['Fecha'] = df_display['timestamp'].dt.strftime('%d/%m/%Y')
        df_display['Hora'] = df_display['timestamp'].dt.strftime('%H:%M')
        df_display['Cantidad'] = df_display['ml'].apply(lambda x: f"{x:.2f} ml")

        df_final = df_display[['Fecha', 'Hora', 'Cantidad', 'Intervalo Real']]

        st.dataframe(df_final, use_container_width=True, hide_index=True)

        # 3. Métricas de Logros
        st.markdown("---")
        col_h1, col_h2 = st.columns(2)
        df_valid_diffs = df_hist.dropna(subset=['diff'])

        if not df_valid_diffs.empty:
            media_int_total = df_valid_diffs['diff'].mean()
            max_int = df_valid_diffs['diff'].max()
            col_h1.metric("Intervalo Medio Real", formatear_delta(media_int_total))
            col_h2.metric("Récord de espera", formatear_delta(max_int))

        # 4. Zona de Borrado y Ajuste de Saldo
        st.markdown("---")
        with st.expander("⚠️ ZONA DE PELIGRO", expanded=False):
            c_del, c_bal = st.columns(2)
            
            with c_del:
                st.write("¿La última toma es un error?")
                if st.button("🗑️ BORRAR ÚLTIMA TOMA"):
                    # Llamamos a la función de borrado que debe estar en database.py
                    exito = database.eliminar_ultima_toma()
                    if exito:
                        st.success("Fila eliminada correctamente.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("No se pudo borrar la toma.")
            
            with c_bal:
                st.write("Ajuste manual de saldo")
                nuevo_saldo = st.number_input("Nuevo Saldo Disponible:", value=0.0, step=0.1)
                if st.button("💾 ACTUALIZAR SALDO"):
                    # Para ajustar el saldo, recalculamos el checkpoint_ingresos necesario
                    # Saldo = Ingresos_Totales - Gastos_Totales
                    # Ingresos_Totales = Nuevo_Saldo + Gastos_Totales
                    # Checkpoint_Ingresos = Ingresos_Totales (y reseteamos fecha a ahora)
                    
                    gastos_totales = df['ml'].sum()
                    nuevo_checkpoint_ingresos = nuevo_saldo + gastos_totales
                    ahora_ajuste = pd.Timestamp.now(tz='Europe/Madrid')
                    
                    logic.save_config({
                        "checkpoint_ingresos": nuevo_checkpoint_ingresos,
                        "checkpoint_fecha": ahora_ajuste.isoformat()
                    })
                    st.success(f"Saldo actualizado a {nuevo_saldo:.2f} ml")
                    time.sleep(1)
                    st.rerun()

    else:
        st.info("No hay datos registrados todavía.")

    st.markdown("---")

    # Filtros y tablas que estaban en tab_reductor
    st.subheader("📅 Filtros de Visualización")
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        fecha_inicio = st.date_input("Fecha Inicio", df['timestamp'].min().date() if not df.empty else pd.Timestamp.now().date())
    with c_f2:
        fecha_fin = st.date_input("Fecha Fin", pd.Timestamp.now(tz='Europe/Madrid').date())

    mask = (df['timestamp'].dt.date >= fecha_inicio) & (df['timestamp'].dt.date <= fecha_fin)
    df_filtrado = df.loc[mask]
    resumen_filtrado = logic.calcular_resumen_bloques(df_filtrado)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("📊 Resumen Bloques")
        st.dataframe(resumen_filtrado, use_container_width=True)
    with col_t2:
        st.subheader("🕒 Tomas Filtradas")
        st.dataframe(df_filtrado[['fecha', 'hora', 'ml']], use_container_width=True, hide_index=True)