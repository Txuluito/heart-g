import streamlit as st
import pandas as pd
import database
import logic
import datetime

def render(df, resumen_bloques, URL_WEB_APP=None):
    # 1. Recuperar referencia de consumo
    if len(resumen_bloques) >= 2:
        consumo_ref = resumen_bloques.iloc[1]['total_ml']
    else:
        consumo_ref = 15.0  # Por defecto

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
    try:
        saved_start_date = datetime.datetime.strptime(saved_start_date_str, "%Y-%m-%d").date()
    except ValueError:
        saved_start_date = today

    # --- CÁLCULOS DEL PLAN ---
    current_day_idx = (today - saved_start_date).days
    
    # --- CÁLCULO DE PRESUPUESTO (CON CHECKPOINTS) ---
    ahora = pd.Timestamp.now(tz='Europe/Madrid')
    horas_tramo_actual = (ahora - checkpoint_fecha).total_seconds() / 3600
    tasa_gen_actual = (consumo_ref - saved_rate) / 24
    ingresos_tramo_actual = horas_tramo_actual * tasa_gen_actual
    
    if checkpoint_ingresos == 0.0 and checkpoint_fecha_str is None and not df.empty:
        inicio = df['timestamp'].min()
        horas_totales = (ahora - inicio).total_seconds() / 3600
        ingresos_totales = horas_totales * tasa_gen_actual
    else:
        ingresos_totales = checkpoint_ingresos + ingresos_tramo_actual
        
    gastos_totales = df['ml'].sum()
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
            horas_pasadas = (ahora_reg - checkpoint_fecha).total_seconds() / 3600
            ingresos_nuevos = horas_pasadas * tasa_gen_actual
            nuevo_checkpoint_ingresos = checkpoint_ingresos + ingresos_nuevos
            
            logic.save_config({
                "checkpoint_ingresos": nuevo_checkpoint_ingresos,
                "checkpoint_fecha": ahora_reg.isoformat()
            })
            
            res = database.enviar_toma_api( f_sel.strftime('%d/%m/%Y'), h_sel.strftime('%H:%M:%S'), cant)
            if res.status_code == 200:
                st.success("Registrado correctamente")
                st.rerun()

    # st.markdown("---")
    
    # Lógica de Tiempos
    ultima_toma = df['timestamp'].max()
    pasado_mins = (ahora - ultima_toma).total_seconds() / 60
    
    # Recalcular objetivo para mostrar tiempos teóricos
    if current_day_idx < 0:
        reducir_hoy = 0.0
    else:
        reducir_hoy = saved_rate * (current_day_idx + 1)

    reducir = min(max(0.0, reducir_hoy), float(consumo_ref))
    objetivo = max(0.0, consumo_ref - reducir)
    
    # Intervalo teórico (velocidad del plan)
    if objetivo > 0:
        intervalo_min = int((24 / (objetivo / saved_dosis)) * 60)
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
    
    if objetivo > 0:
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
        m5.metric("Saldo Disponible", f"{saldo:.3f} ml", delta="Disponible", delta_color="normal")
    else:
        m5.metric("Saldo Disponible", f"{saldo:.3f} ml", delta="-Déficit", delta_color="inverse")

    # Barra de progreso (Basada en porcentaje de saldo para la siguiente dosis)
    if not es_listo:
        progreso = max(0.0, min(1.0, saldo / saved_dosis))
        st.progress(progreso)
    else:
        st.success("🎉 Saldo suficiente para la siguiente dosis")

    # st.markdown("---")
    #
    # # --- VISUALIZACIÓN: ESTADO DEL PLAN ---
    # st.markdown("### 📊 Estado del Plan")
    #
    # 2. Configuración de Objetivos (Expander) - MOVIDO AQUÍ
    with st.expander("⚙️ CONFIGURACIÓN DEL PLAN", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            reduction_rate = st.number_input("Reducción diaria (ml):", 0.0, 5.0, float(saved_rate), 0.05)
        with c2:
            plan_start = st.date_input("Fecha Inicio Plan", saved_start_date)
        
        # Lógica de Checkpoint: Si cambia la tasa
        if reduction_rate != saved_rate:
            ahora_calc = pd.Timestamp.now(tz='Europe/Madrid')
            horas_pasadas = (ahora_calc - checkpoint_fecha).total_seconds() / 3600
            tasa_gen_anterior = (consumo_ref - saved_rate) / 24
            ingresos_nuevos = horas_pasadas * tasa_gen_anterior
            nuevo_checkpoint_ingresos = checkpoint_ingresos + ingresos_nuevos
            
            logic.save_config({
                "reduction_rate": reduction_rate,
                "checkpoint_ingresos": nuevo_checkpoint_ingresos,
                "checkpoint_fecha": ahora_calc.isoformat()
            })
            st.rerun()

        if plan_start != saved_start_date:
            logic.save_config({"plan_start_date": str(plan_start)})
            st.rerun()

        # Cálculo de estimaciones para mostrar en el input disabled
        if reduction_rate > 0:
            total_days_est = int(consumo_ref / reduction_rate)
            plan_end_est = plan_start + datetime.timedelta(days=total_days_est)
        else:
            total_days_est = 0
            plan_end_est = today
            
        with c3:
            st.date_input(f"Fecha Fin Estimada ({total_days_est} días)", plan_end_est, disabled=True)

    # Cálculo de estimaciones
    if saved_rate > 0:
        total_days_plan = int(consumo_ref / saved_rate)
    else:
        total_days_plan = 0
    days_remaining = max(0, total_days_plan - current_day_idx)

    # Métricas de Estado del Plan
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Consumo Base", f"{consumo_ref:.2f} ml")
    col2.metric("Objetivo Hoy", f"{objetivo:.2f} ml", delta=f"-{reducir:.2f} ml", delta_color="inverse")
    col3.metric("Reducción Plan", f"{saved_rate:.2f} ml/día")
    col4.metric("Días Restantes", f"{days_remaining} días", help=f"Total plan: {total_days_plan} días")