from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pandas import DataFrame

from database import get_plan_history_data, save_plan_history_data, save_config


def mlAcumulados():
    if st.session_state.config.get("plan.checkpoint_fecha"):
        # Lógica original para plan por tiempo (reducción continua)
        ml_reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))
        checkpoint_ml = float(st.session_state.config.get("tiempos.checkpoint_ml"))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("plan.checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_desde_checkpoint = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600
        def integral(t_h):
            if t_h < 0: return (checkpoint_ml / 24.0) * t_h
            t_fin = (checkpoint_ml / ml_reduccion_diaria) * 24 if ml_reduccion_diaria > 0 else 999999
            t_eff = min(t_h, t_fin)
            return (checkpoint_ml / 24.0) * t_eff - (ml_reduccion_diaria / 1152.0) * (t_eff ** 2)

        integ= integral(horas_desde_checkpoint)

        print(f"[mlAcumulados] -> checkpoint_ml: {checkpoint_ml},integral: {integ}, checkpoint_fecha: {checkpoint_fecha}, ml_reduccion_diaria: {ml_reduccion_diaria}")
        return  float(checkpoint_ml + integ)

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
        return pd.DataFrame()

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
    row = df[df["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')]
    if not row.empty:
        return float(row['Dosis'].iloc[0])
    else:
        return 3.5
def intervalo():
    df = st.session_state.df_tiempos.copy()
    ahora = pd.Timestamp.now(tz='Europe/Madrid')
    fecha_inicio_plan = pd.to_datetime(st.session_state.config.get("plan.fecha_inicio_plan")) if st.session_state.config.get(
        "plan.fecha_inicio_plan") else ahora

    if fecha_inicio_plan.tzinfo is None:
        fecha_inicio_plan = fecha_inicio_plan.tz_localize('UTC').tz_convert('Europe/Madrid')
    else:
        fecha_inicio_plan = fecha_inicio_plan.tz_convert('Europe/Madrid')

    ml_reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))
    ml_dia = float(st.session_state.config.get("plan.ml_dia", 15.0))

    horas_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / 3600
    dias_flotantes = max(0.0, horas_desde_inicio / 24.0)
    objetivo_actual = max(0.0, ml_dia - (ml_reduccion_diaria * dias_flotantes))
    tasa_gen = objetivo_actual / 24.0
    if tasa_gen > 0:
        return  int((dosis_actual() / tasa_gen) * 60)
    else:
        return 0

def minEspera(ml_dosis,saldo):
    ahora = pd.Timestamp.now(tz='Europe/Madrid')
    fecha_inicio_plan = pd.to_datetime(
        st.session_state.config.get("plan.fecha_inicio_plan")) if st.session_state.config.get(
        "plan.fecha_inicio_plan") else ahora
    if fecha_inicio_plan.tzinfo is None:
        fecha_inicio_plan = fecha_inicio_plan.tz_localize('UTC').tz_convert('Europe/Madrid')
    else:
        fecha_inicio_plan = fecha_inicio_plan.tz_convert('Europe/Madrid')

    ml_reduccion_diaria = float(st.session_state.config.get("plan.reduccion_diaria", 0.5))
    ml_dia = float(st.session_state.config.get("plan.ml_dia", 15.0))

    horas_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / 3600
    dias_flotantes = max(0.0, horas_desde_inicio / 24.0)
    objetivo_actual = max(0.0, ml_dia - (ml_reduccion_diaria * dias_flotantes))
    tasa_gen = objetivo_actual / 24.0
    if tasa_gen > 0 and saldo < ml_dosis:
        return ((ml_dosis - saldo) / tasa_gen * 60)
    return 0