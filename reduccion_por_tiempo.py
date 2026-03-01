from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pandas import DataFrame

from database import get_plan_history_data, save_plan_history_data, save_config


def mlAcumulados():
    if st.session_state.config.get("plan.checkpoint_fecha"):
        # Lógica original para plan por tiempo (reducción continua)
        ml_reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))
        # Obtener la tasa diaria actual (ml/día) desde la configuración
        ml_dia_actual = float(st.session_state.config.get("consumo.ml_dia", 15.0))
        
        checkpoint_ml = float(st.session_state.config.get("tiempos.checkpoint_ml"))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("plan.checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_desde_checkpoint = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600
        
        # Cálculo correcto de la generación:
        # Generado = Integral de (Tasa_actual - Reduccion * t) dt
        # = Tasa_actual * t - (Reduccion * t^2) / 2
        # Donde t está en días.
        
        t_dias = horas_desde_checkpoint / 24.0
        
        # Calcular cuándo la tasa llegaría a 0 para no generar negativo
        if ml_reduccion_diaria > 0:
            t_fin_dias = ml_dia_actual / ml_reduccion_diaria
        else:
            t_fin_dias = 999999
            
        t_eff_dias = min(t_dias, t_fin_dias)
        
        generado = (ml_dia_actual * t_eff_dias) - (ml_reduccion_diaria * (t_eff_dias**2) / 2)

        print(f"[mlAcumulados] -> checkpoint_ml: {checkpoint_ml}, generado: {generado}, ml_dia: {ml_dia_actual}")
        return  float(checkpoint_ml + generado)

    else:
        return float(0)
def crear_tabla(ml_dosis_actual, reduccion_diaria, ml_dia_actual):

    tabla = []
    fecha_dia = datetime.now()
    objetivo_dia = ml_dia_actual

    while objetivo_dia > 0:
        # Intervalo (minutos) = 24h / (Objetivo / Dosis)
        intervalo_teorico = int((24 * 60) / (objetivo_dia / ml_dosis_actual)) if (objetivo_dia > 0 and ml_dosis_actual > 0) else 0
        intervalo_horas = f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m" if intervalo_teorico > 0 else "---"

        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(objetivo_dia, 2),
            "Reducción Diaria": round(reduccion_diaria, 2),
            "Dosis": round(ml_dosis_actual, 2),
            "Intervalo": intervalo_horas,
            "Real (ml)": 0,
            "Estado": "",
        })
        objetivo_dia = max(0, objetivo_dia - reduccion_diaria)
        fecha_dia += timedelta(days=1)
        ml_dosis_actual = round(ml_dosis_actual, 2)
    return pd.DataFrame(tabla)
def obtener_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data(sheet_name="Plan Tiempo") # <- CORREGIDO
    if df.empty:
        return pd.DataFrame(columns=['Fecha', 'Objetivo (ml)', 'Real (ml)', 'Reducción Diaria', 'Dosis', 'Estado'])

    # Manejo robusto de fechas
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Si las fechas ya tienen zona horaria (tz-aware), convertimos directamente
    if df['Fecha'].dt.tz is not None:
         df['Fecha'] = df['Fecha'].dt.tz_convert('Europe/Madrid')
    else:
         # Si no tienen zona horaria (tz-naive), las localizamos primero
         # Asumimos que vienen en UTC o sin zona, las tratamos como UTC y luego Madrid
         df['Fecha'] = df['Fecha'].dt.tz_localize('UTC').dt.tz_convert('Europe/Madrid')


    def calcular_estado(row):
        if row["Fecha"] < datetime.now().strftime("%Y-%m-%d"):
            # Ciclo cerrado (días anteriores)
            if row['Real (ml)'] <= row['Objetivo (ml)'] + 0.5:
                return "✅ Sí"
            else:
                return "❌ No"
        elif row["Fecha"] == datetime.now().strftime("%Y-%m-%d"):
            # Ciclo en curso (hoy)
            return "⏳ En curso"
        else:
            # Días futuros
            return "🔮 Futuro"


    df["Fecha"] = df["Fecha"].dt.strftime('%Y-%m-%d')
    df["Objetivo (ml)"] = pd.to_numeric(df['Objetivo (ml)'], errors='coerce').fillna(0)
    df["Reducción Diaria"] = pd.to_numeric(df['Reducción Diaria'], errors='coerce').fillna(0)
    df['Dosis'] = pd.to_numeric(df['Dosis'], errors='coerce').fillna(0)
    # df['Intervalo'] = df["Fecha"].dt.strftime('%Y-%m-%d')
    df['Real (ml)'] = pd.to_numeric( df['Real (ml)'], errors='coerce').fillna(0)
    df['Estado'] = df.apply(calcular_estado, axis=1)

    return df
def replanificar(dosis_media, reduccion_diaria, ml_dia_actual):
    fecha_hoy = pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')
    df_nuevo = crear_tabla(dosis_media, reduccion_diaria, ml_dia_actual)
    df_plan = st.session_state.df_tiempos.copy()

    fila_hoy_antigua = df_plan[df_plan["Fecha"] == fecha_hoy]
    if not fila_hoy_antigua.empty:
        df_nuevo.loc[df_nuevo['Fecha'] == fecha_hoy, 'Real (ml)']= fila_hoy_antigua['Real (ml)']
    df_plan = df_plan[df_plan["Fecha"] < fecha_hoy]
    df_final = pd.concat([df_plan, df_nuevo], ignore_index=True)
    save_plan_history_data(df_final, sheet_name="Plan Tiempo")
    print(f"Plan replanificado en la hoja 'PlanHistory'.")

def add_toma(fecha_toma, ml_toma) -> DataFrame:
    df = st.session_state.df_tiempos.copy()
    row = df[df["Fecha"] == fecha_toma.strftime('%Y-%m-%d')]
    if not row.empty:
        df.loc[df["Fecha"] == fecha_toma.strftime('%Y-%m-%d'), 'Real (ml)']+=ml_toma
    save_plan_history_data(df, sheet_name="Plan Tiempo")
def dosis_actual():
    df = st.session_state.df_tiempos.copy()
    if df.empty or "Fecha" not in df.columns:
        return 0
    row = df[df["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')]
    if not row.empty:
        return float(row['Dosis'].iloc[0])
    else:
        return 0

def objetivo_ml():
    df = st.session_state.df_tiempos.copy()
    if df.empty or "Fecha" not in df.columns:
        return 0
    row = df[df["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')]
    if not row.empty:
        return float(row['Objetivo (ml)'].iloc[0])
    else:
        return 0

def calcular_metricas_tiempo(df_tomas):
    ahora = pd.Timestamp.now(tz='Europe/Madrid')

    # --- Lógica de Cálculo Dinámico ---
    
    # 1. Cargar parámetros del plan
    fecha_inicio_plan = pd.to_datetime(st.session_state.config.get("plan.fecha_inicio_plan", ahora))
    if fecha_inicio_plan.tzinfo is None:
        fecha_inicio_plan = fecha_inicio_plan.tz_localize('UTC').tz_convert('Europe/Madrid')
    
    ml_dia_inicial = float(st.session_state.config.get("consumo.ml_dia", 15.0))
    reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))

    # 2. Calcular el objetivo de consumo diario en este preciso instante
    dias_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / (3600 * 24)
    objetivo_actual_ml_dia = max(0, ml_dia_inicial - (reduccion_diaria * dias_desde_inicio))
    
    # 3. Calcular la tasa de generación de ml por minuto actual
    tasa_gen_actual_ml_por_minuto = objetivo_actual_ml_dia / 1440.0

    # 4. Obtener la dosis del plan para hoy
    dosis_plan_hoy = dosis_actual()

    # 5. Calcular el intervalo teórico basado en la tasa actual
    intervalo_teorico = 0
    if tasa_gen_actual_ml_por_minuto > 0 and dosis_plan_hoy > 0:
        intervalo_teorico = dosis_plan_hoy / tasa_gen_actual_ml_por_minuto
    
    # 6. Calcular tiempo desde la última toma
    ultima_toma_ts = df_tomas['timestamp'].max() if not df_tomas.empty else ahora
    min_desde_ultima_toma = (ahora - ultima_toma_ts).total_seconds() / 60

    # 7. Calcular minutos de espera restantes (basado en intervalo)
    mins_espera = max(0, intervalo_teorico - min_desde_ultima_toma)

    # 8. Calcular minutos de espera restantes (basado en SALDO)
    saldo_actual = mlAcumulados()
    mins_espera_saldo = 0
    if tasa_gen_actual_ml_por_minuto > 0 and saldo_actual < dosis_plan_hoy:
        mins_espera_saldo = (dosis_plan_hoy - saldo_actual) / tasa_gen_actual_ml_por_minuto

    return dosis_plan_hoy, intervalo_teorico, mins_espera, mins_espera_saldo
