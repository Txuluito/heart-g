import streamlit as st
import pandas as pd
import database
import logic
import datetime

def render(df, resumen_bloques, URL_WEB_APP=None):

    # Cargar configuración
    config = logic.load_config()
    saved_dosis = config.get("dosis", 3.2)
    saved_rate = config.get("reduction_rate", 0.5)
    
    # Recuperar datos de checkpoint para el saldo
    checkpoint_ingresos = config.get("checkpoint_ingresos", 0.0)
    checkpoint_fecha_str = config.get("checkpoint_fecha", None)
    
    # Determinar fecha de checkpoint
    if checkpoint_fecha_str:
        checkpoint_fecha = pd.to_datetime(checkpoint_fecha_str)
        if checkpoint_fecha.tz is None:
            checkpoint_fecha = checkpoint_fecha.tz_localize('Europe/Madrid')
    else:
        # Si no hay checkpoint, usamos el inicio de los datos
        if not df.empty:
            checkpoint_fecha = df['timestamp'].min()
        else:
            checkpoint_fecha = pd.Timestamp.now(tz='Europe/Madrid')

    # Recuperar fechas del plan
    today = pd.Timestamp.now(tz='Europe/Madrid').date()
    saved_start_date_str = config.get("plan_start_date", str(today))
    saved_start_amount = config.get("plan_start_amount", 15.0)
    
    try:
        # Aseguramos que sea string y manejamos posibles formatos
        d_str = str(saved_start_date_str).strip()
        if len(d_str) == 8 and d_str.isdigit():
            saved_start_date = datetime.datetime.strptime(d_str, "%Y%m%d").date()
        else:
            saved_start_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        saved_start_date = today

    # --- CÁLCULOS DEL PLAN (CONTINUO) ---
    # Convertir inicio a datetime con zona horaria para precisión de minutos/segundos
    plan_start_dt = pd.Timestamp(saved_start_date).tz_localize('Europe/Madrid')
    ahora = pd.Timestamp.now(tz='Europe/Madrid')
    
    # Tiempo transcurrido desde el inicio del plan en horas
    horas_desde_inicio = (ahora - plan_start_dt).total_seconds() / 3600
    
    # 1. Objetivo Instantáneo: Se reduce cada segundo
    # Fórmula: Start - (Rate * Dias_Flotantes)
    dias_flotantes = max(0.0, horas_desde_inicio / 24.0)
    objetivo_actual_instantaneo = max(0.0, saved_start_amount - (saved_rate * dias_flotantes))
    
    # 2. Tasa de generación actual (para proyecciones futuras inmediatas)
    tasa_gen_actual = objetivo_actual_instantaneo / 24.0

    # --- CÁLCULO DE PRESUPUESTO (INTEGRAL) ---
    # Calculamos el ingreso acumulado exacto usando la integral de la curva de reducción
    def calcular_ingreso_acumulado(t_horas, start, rate):
        # Si es antes del plan, asumimos generación constante al valor inicial
        if t_horas < 0:
            return (start / 24.0) * t_horas
            
        # Límite donde el objetivo llega a 0
        t_fin = (start / rate) * 24 if rate > 0 else 999999999
        t_eff = min(t_horas, t_fin)
        
        # Integral: (Start/24)*t - (Rate/1152)*t^2
        return (start / 24.0) * t_eff - (rate / 1152.0) * (t_eff ** 2)

    # Calculamos ingresos desde el checkpoint hasta ahora
    t_checkpoint = (checkpoint_fecha - plan_start_dt).total_seconds() / 3600
    t_ahora = horas_desde_inicio
    
    ingresos_tramo_actual = calcular_ingreso_acumulado(t_ahora, saved_start_amount, saved_rate) - \
                            calcular_ingreso_acumulado(t_checkpoint, saved_start_amount, saved_rate)
    
    if checkpoint_ingresos == 0.0 and checkpoint_fecha_str is None and not df.empty:
        # Fallback para compatibilidad antigua (si no hay plan definido)
        ingresos_totales = ((ahora - df['timestamp'].min()).total_seconds() / 3600) * (saved_start_amount / 24)
    else:
        ingresos_totales = checkpoint_ingresos + ingresos_tramo_actual
        
    # Solo contamos los gastos realizados DESDE el inicio del plan actual
    gastos_totales = df[df['timestamp'] >= plan_start_dt]['ml'].sum()
    saldo = ingresos_totales - gastos_totales

    # --- CONTROL DE TOMAS ---
    # st.markdown("### ⏱️ Control de Tomas")
    #
    # 5. Formulario de Registro (MOVIDO ARRIBA)
    with st.expander("➕ REGISTRAR TOMA", expanded=False):
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            # Cantidad es el input principal ahora
            cant = st.number_input("Cantidad (ml):", 0.1, 10.0, float(saved_dosis))
            # Actualizamos la dosis deseada (informativa) si cambia la cantidad
            if cant != saved_dosis:
                logic.save_config({"dosis": cant})
                saved_dosis = cant # Actualizamos variable local para cálculos inmediatos
                
        with col_r2:
            f_sel = st.date_input("Fecha:", ahora.date())
        with col_r3:
            h_sel = st.time_input("Hora:", ahora.time())

        if st.button("🚀 ENVIAR REGISTRO", use_container_width=True):
            # GUARDAR CHECKPOINT ANTES DE REGISTRAR
            ahora_reg = pd.Timestamp.now(tz='Europe/Madrid')
            # Usar el cálculo integral para la precisión
            t_checkpoint_reg = (checkpoint_fecha - plan_start_dt).total_seconds() / 3600
            t_ahora_reg = (ahora_reg - plan_start_dt).total_seconds() / 3600
            ingresos_desde_checkpoint = calcular_ingreso_acumulado(t_ahora_reg, saved_start_amount, saved_rate) - \
                                        calcular_ingreso_acumulado(t_checkpoint_reg, saved_start_amount, saved_rate)
            nuevo_checkpoint_ingresos = checkpoint_ingresos + ingresos_desde_checkpoint
            
            logic.save_config({
                "checkpoint_ingresos": nuevo_checkpoint_ingresos,
                "checkpoint_fecha": ahora_reg.isoformat()
            })
            
            # Calcular el saldo que quedará tras esta toma para guardarlo en el registro
            # Saldo = (Ingresos hasta ahora) - (Gastos previos + Esta toma)
            gastos_previos = df[df['timestamp'] >= plan_start_dt]['ml'].sum()
            saldo_snapshot = nuevo_checkpoint_ingresos - (gastos_previos + cant)
            
            res = database.enviar_toma_api( f_sel.strftime('%d/%m/%Y'), h_sel.strftime('%H:%M:%S'), cant, saldo_snapshot)
            
            if res.status_code == 200:
                st.success("Registrado correctamente")
                st.rerun()

    # Lógica de Tiempos
    ultima_toma = df['timestamp'].max()
    pasado_mins = (ahora - ultima_toma).total_seconds() / 60
    
    # Reducción que aplica hoy (solo informativa)
    reduccion_acumulada = saved_rate * dias_flotantes
    
    # Intervalo teórico (velocidad del plan)
    if objetivo_actual_instantaneo > 0:
        intervalo_min = int((24 / (objetivo_actual_instantaneo / saved_dosis)) * 60)
    else:
        intervalo_min = 999999
        
    # --- LÓGICA DE SIGUIENTE DOSIS BASADA EN SALDO ---
    tiempo_espera_mins = 0
    es_listo = False
    
    if saldo >= saved_dosis:
        es_listo = True
    else:
        falta = saved_dosis - saldo
        if tasa_gen_actual > 0:
            horas_falta = falta / tasa_gen_actual
            tiempo_espera_mins = horas_falta * 60
        else:
            tiempo_espera_mins = 999999 # Infinito si no hay generación

    # Métricas de Control
    m1, m2, m3, m4, m5 = st.columns(5)
    
    with m1:
        # Dosis deseada ahora es una métrica
        st.metric("Dosis Deseada", f"{saved_dosis:.2f} ml")

    m2.metric("Última toma hace", f"{int(pasado_mins // 60)}h {int(pasado_mins % 60)}min")
    
    if objetivo_actual_instantaneo > 0:
        m3.metric("Tiempo entre dosis", f"{intervalo_min // 60}h {intervalo_min % 60}min")
    else:
        m3.metric("Tiempo entre dosis", "∞")

    if not es_listo:
        h_res, m_res = int(tiempo_espera_mins // 60), int(tiempo_espera_mins % 60)
        m4.metric("Siguiente dosis en", f"{h_res}h {m_res}min", delta="Insuficiente", delta_color="inverse")
    else:
        m4.metric("Siguiente dosis", "¡LISTO!", delta="Disponible", delta_color="normal")

    # Visualización del Saldo
    if saldo >= 0:
        m5.metric("Saldo Disponible", f"{saldo:.2f} ml", delta="Disponible", delta_color="normal")
    else:
        m5.metric("Saldo Disponible", f"{saldo:.2f} ml", delta="-Déficit", delta_color="inverse")

    # Barra de progreso (Basada en porcentaje de saldo para la siguiente dosis)
    if not es_listo:
        progreso = max(0.0, min(1.0, saldo / saved_dosis))
        st.progress(progreso)
    else:
        st.success("🎉 Saldo suficiente para la siguiente dosis")

    # --- TABLA DE SEGUIMIENTO DEL PLAN ---
    st.markdown("---")
    
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.subheader("📅 Historial y Cumplimiento del Plan")
    with col_h2:
        mostrar_futuro = st.checkbox("Mostrar días futuros", value=False)
    
    # Variable de estado para forzar recálculo desde el botón de configuración
    force_recalc = st.session_state.get('force_recalc_plan', False)
    df_seguimiento = logic.calcular_seguimiento_plan(df, config, force_recalc=force_recalc)
    
    # Resetear el flag después de usarlo
    if force_recalc:
        st.session_state['force_recalc_plan'] = False
    
    # Filtro para mostrar/ocultar días futuros
    hoy_str = pd.Timestamp.now(tz='Europe/Madrid').strftime('%d/%m/%Y')
    df_display_seguimiento = df_seguimiento.copy()
    if not mostrar_futuro:
        df_display_seguimiento = df_display_seguimiento[df_display_seguimiento['Estado'] != "🔮 Futuro"]

    # Estilo: Resaltar el día actual
    def resaltar_hoy(row):
        if row['Fecha'] == hoy_str:
            return ['background-color: rgba(255, 75, 75, 0.1); border-left: 5px solid #ff4b4b'] * len(row)
        return [''] * len(row)

    # Tabla interactiva
    event = st.dataframe(
        df_display_seguimiento.style.apply(resaltar_hoy, axis=1).format({
            "Objetivo (ml)": "{:.2f}",
            "Real (ml)": "{:.2f}",
            "Reducción Plan": "{:.2f}"
        }),
        width='stretch',
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Mostrar detalles al seleccionar una fila
    if event.selection.rows:
        idx = event.selection.rows[0]
        selected_row = df_display_seguimiento.iloc[idx]
        fecha_seleccionada = selected_row['Fecha']
        objetivo_dia = selected_row['Objetivo (ml)']
        
        st.info(f"🔎 Detalles del día: **{fecha_seleccionada}** | Objetivo: {objetivo_dia} ml")
        
        # Calcular tasa de generación para ese día (ml/hora)
        rate_dia = objetivo_dia / 24.0 if objetivo_dia > 0 else 0
        
        # Preparar DF completo para calcular diferencias de tiempo correctamente
        df_sorted = df.sort_values('timestamp', ascending=True).copy()
        df_sorted['diff_seconds'] = df_sorted['timestamp'].diff().dt.total_seconds()
        
        # Filtrar para el día seleccionado
        mask_dia = df_sorted['timestamp'].dt.strftime('%d/%m/%Y') == fecha_seleccionada
        df_dia = df_sorted[mask_dia].copy().sort_values('timestamp', ascending=False)
        
        if not df_dia.empty:
            # Funciones auxiliares para columnas calculadas
            def format_interval(seconds):
                if pd.isna(seconds): return "---"
                m = int(seconds // 60)
                h = m // 60
                m = m % 60
                return f"{h}h {m}m"

            def calc_details(row):
                ml = row['ml']
                diff = row['diff_seconds']
                int_real_str = format_interval(diff)
                
                if rate_dia <= 0:
                    return pd.Series([int_real_str, "---", "---", "---"])
                
                # Tiempo necesario: (ml / rate) * 3600
                needed_seconds = (ml / rate_dia) * 3600
                int_obj_str = format_interval(needed_seconds)
                
                if pd.isna(diff):
                    return pd.Series([int_real_str, int_obj_str, "🏁 Inicio", "---"])
                
                # Balance: (Tiempo Real * Tasa) - Consumo
                generado = (diff / 3600) * rate_dia
                balance = generado - ml
                
                if balance >= -0.05: # Margen de tolerancia
                    cumple = "✅ Sí"
                    vote_str = f"+{balance:.2f} ml"
                else:
                    cumple = "❌ No"
                    vote_str = f"{balance:.2f} ml"
                
                return pd.Series([int_real_str, int_obj_str, cumple, vote_str])

            df_dia[['Intervalo Real', 'Int. Necesario', 'Cumple', 'Impacto Vote']] = df_dia.apply(calc_details, axis=1, result_type='expand').values

            df_display_dia = df_dia.copy()
            df_display_dia['ml'] = df_display_dia['ml'].map('{:.2f}'.format)

            st.dataframe(
                df_display_dia[['hora', 'ml', 'Intervalo Real', 'Int. Necesario', 'Cumple', 'Impacto Vote']],
                width='stretch', 
                hide_index=True
            )
        else:
            st.warning("No hay tomas registradas en este día.")

    # --- CONFIGURACIÓN DEL PLAN ---
    st.markdown("---")
    with st.expander("⚙️ CONFIGURACIÓN DEL PLAN", expanded=False):
        st.info("Define los parámetros iniciales. Al generar, se creará el calendario de reducción.")
        
        c1, c2 = st.columns(2)
        with c1:
            new_start_amount = st.number_input("Consumo Inicial (ml/día)", 0.0, 50.0, float(saved_start_amount))
            new_start_date = st.date_input("Fecha Inicio Plan", saved_start_date)
        with c2:
            new_rate = st.number_input("Reducción diaria (ml)", 0.0, 5.0, float(saved_rate), 0.05)
            
            # Estimación de fin
            if new_rate > 0 and new_start_amount > 0:
                dias_est = int(new_start_amount / new_rate)
                fecha_fin_est = new_start_date + datetime.timedelta(days=dias_est)
                st.write(f"🏁 Fin estimado: **{fecha_fin_est.strftime('%d/%m/%Y')}** ({dias_est} días)")
            else:
                st.write("🏁 Fin estimado: ---")

        # Botón para limpiar el historial y recalcular todo
        if st.button("♻️ RECALCULAR HISTORIAL COMPLETO", help="Borra los datos guardados y aplica la configuración actual a todos los días pasados."):
            st.session_state['force_recalc_plan'] = True
            st.rerun()

        if st.button("💾 GENERAR / ACTUALIZAR PLAN", use_container_width=True):
            logic.save_config({
                "plan_start_amount": new_start_amount,
                "plan_start_date": str(new_start_date),
                "reduction_rate": new_rate,
                # Reseteamos checkpoint para evitar inconsistencias grandes al cambiar el plan
                "checkpoint_ingresos": 0.0, 
                "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat()
            })
            st.success("Plan actualizado correctamente.")
            st.rerun()

    # Cálculo de estimaciones
    if saved_rate > 0:
        total_days_plan = int(saved_start_amount / saved_rate)
    else:
        total_days_plan = 0
    
    current_day_idx = int(dias_flotantes)
    days_remaining = max(0, total_days_plan - current_day_idx)

    # Métricas de Estado del Plan
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Inicio Plan", f"{saved_start_amount:.2f} ml")
    col2.metric("Objetivo Actual", f"{objetivo_actual_instantaneo:.2f} ml", delta=f"-{reduccion_acumulada:.2f} ml", delta_color="inverse")
    col3.metric("Reducción Plan", f"{saved_rate:.2f} ml/día")
    col4.metric("Días Restantes", f"{days_remaining} días", help=f"Total plan: {total_days_plan} días")