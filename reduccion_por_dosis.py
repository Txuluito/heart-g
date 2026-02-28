from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from pandas import DataFrame

from database import get_plan_history_data, save_plan_history_data, save_config


def mlAcumulados():
    if st.session_state.config.get("plan.checkpoint_fecha"):
        dosis_actual = float(st.session_state.config.get("dosis.ml_dia", 3.0))

        intervalo_val = st.session_state.config.get("dosis.intervalo_horas", 2.0)
        # Asegurar conversión a float si viene como time o string
        if hasattr(intervalo_val, 'hour'):
            intervalo = intervalo_val.hour + intervalo_val.minute / 60.0
        else:
            try:
                intervalo = float(intervalo_val)
            except:
                intervalo = 2.0

        # Tasa de generación (ml/hora) = Dosis / Intervalo
        tasa_generacion = dosis_actual / intervalo if intervalo > 0 else 0

        checkpoint_ml = float(st.session_state.config.get("dosis.checkpoint_ml", 0.0))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("plan.checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_localize('UTC').tz_convert('Europe/Madrid')
        else:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_pasadas = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600

        generado = tasa_generacion * horas_pasadas
        return float(checkpoint_ml + generado)
    else:
        return float(0)
def crear_tabla(reduccion_diaria, ml_dia_actual, intervalo_horas):
    tabla = []
    fecha_dia = datetime.now()
    objetivo_dia = float(ml_dia_actual)
    reduccion_diaria = float(reduccion_diaria)

    # Manejar intervalo_horas si viene como objeto time o string
    intervalo_val = 0.0
    if isinstance(intervalo_horas, (int, float)):
        intervalo_val = float(intervalo_horas)
    elif hasattr(intervalo_horas, 'hour') and hasattr(intervalo_horas, 'minute'):
        intervalo_val = intervalo_horas.hour + intervalo_horas.minute / 60.0

    tomas_dia = 24 / intervalo_val if intervalo_val > 0 else 0
    horas_int = int(intervalo_val)
    mins_int = int((intervalo_val - horas_int) * 60)

    # Límite de seguridad
    dias_count = 0
    while objetivo_dia >= 0.1 and dias_count < 365:
        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(objetivo_dia, 2),
            "Reducción Diaria": round(reduccion_diaria, 2),
            "Dosis": round(objetivo_dia / tomas_dia, 2) if tomas_dia > 0 else 0,
            "Intervalo": f"{horas_int}h {mins_int}m",
            "Real (ml)": 0.0,
            "Estado": ""
        })
        
        objetivo_dia = max(0.0, objetivo_dia - reduccion_diaria)
        fecha_dia += timedelta(days=1)
        dias_count += 1
    return pd.DataFrame(tabla)
def obtener_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data(sheet_name="Plan Dosis")
    if df.empty:
        return pd.DataFrame()

    for col in ['Objetivo (ml)', 'Real (ml)', 'Reducción Diaria', 'Dosis']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Manejo robusto de fechas
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # Si las fechas ya tienen zona horaria (tz-aware), convertimos directamente
    if df['Fecha'].dt.tz is not None:
         df['Fecha'] = df['Fecha'].dt.tz_convert('Europe/Madrid')
    else:
         # Si no tienen zona horaria (tz-naive), las localizamos primero
         # Asumimos que vienen en UTC o sin zona, las tratamos como UTC y luego Madrid
         df['Fecha'] = df['Fecha'].dt.tz_localize('UTC').dt.tz_convert('Europe/Madrid')

    # fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
    hoy = datetime.now().date() # Obtener la fecha de HOY (objeto date) una sola vez
    def calcular_estado(row):
        if row["Fecha"].date() < hoy:
            # Ciclo cerrado (días anteriores)
            if row['Real (ml)'] <= row['Objetivo (ml)'] + 0.5:
                return "✅ Sí"
            else:
                return "❌ No"
        elif row["Fecha"].date() == hoy:
            # Ciclo en curso (hoy)
            return "⏳ En curso"
        else:
            # Días futuros
            return "🔮 Futuro"


    df['Estado'] = df.apply(calcular_estado, axis=1)
    df['Dosis'] = df['Dosis'].map('{:.2f}'.format)
    return df
def add_toma(fecha_toma, ml_toma) -> DataFrame:
    ml_bote=mlAcumulados()
    nuevo_checkpoint_ml = ml_bote - ml_toma
    # Actualizar tabla local
    df_plan = obtener_tabla()

    # Usar string formateado para comparar fechas sin problemas de hora/zona
    # Asumimos que fecha_toma viene como objeto date o datetime
    if isinstance(fecha_toma, datetime):
        fecha_toma_str = fecha_toma.strftime('%Y-%m-%d')
    else:
        fecha_toma_str = str(fecha_toma)

    # Crear columna temporal de string para matching
    df_plan["Fecha_Str"] = df_plan["Fecha"].dt.strftime('%Y-%m-%d')

    if fecha_toma_str in df_plan["Fecha_Str"].values:
        idx = df_plan[df_plan['Fecha_Str'] == fecha_toma_str].index
        df_plan.loc[idx, 'Real (ml)'] += ml_toma

        # Guardar sin columnas auxiliares ni Estado
        cols_to_drop = ['Fecha_Str', 'Estado']
        df_to_save = df_plan.drop(columns=[c for c in cols_to_drop if c in df_plan.columns])

        save_plan_history_data(df_to_save, sheet_name="Plan Dosis")

        save_config({
            "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
            "dosis.checkpoint_ml": nuevo_checkpoint_ml
        })
        print(f"Toma guardada. Checkpoint actualizado.")
    else:
        print(f"ERROR: La fecha {fecha_toma_str} no se encontró en el plan.")
    return df_plan
def replanificar(reduccion_diaria, ml_dia_actual, intervalo_horas):
    df_existente = obtener_tabla()
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d")

    df_conservada = df_existente[df_existente["Fecha"] < fecha_actual_str]
    df_nuevo = crear_tabla(reduccion_diaria, ml_dia_actual, intervalo_horas)

    df_final = pd.concat([df_conservada, df_nuevo], ignore_index=True)

    save_plan_history_data(df_final, sheet_name="Plan Dosis")  # <- CORREGIDO

    print(f"Plan replanificado en la hoja 'PlanHistory'.")
    return df_final