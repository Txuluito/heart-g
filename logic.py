import streamlit as st

import pandas as pd
import numpy as np
import database




# Usamos caché para no llamar a Google Sheets en cada interacción (TTL = 10 minutos)
ahora = pd.Timestamp.now(tz='Europe/Madrid')

def mlAcumulados():
    if st.session_state.config.get("checkpoint_fecha"):
        ml_reduccion_diaria = float(st.session_state.config.get("reduccion_diaria"))
        checkpoint_ml = float(st.session_state.config.get("checkpoint_ml"))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("checkpoint_fecha"))

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

def calcular_resumen_bloques(df):
    df_b = df.copy()
    df_b['horas_atras'] = (pd.Timestamp.now(tz='Europe/Madrid') - df_b['timestamp']).dt.total_seconds() / 3600
    df_b['bloque_n'] = np.floor(df_b['horas_atras'] / 24).astype(int)

    resumen = df_b.groupby('bloque_n').agg(
        total_ml=('ml', 'sum'),
        media_ml=('ml', 'mean'),
        num_tomas=('ml', 'count')
    ).sort_index()
    return resumen

def obtener_datos_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = database.get_plan_history_data() # Usa la función de database.py
    if df.empty:
        return pd.DataFrame()
    # Convertir a objetos datetime de Pandas, es esencial para la comparación.
    # 'errors=coerce' convertirá las fechas no válidas en NaT (Not a Time)
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    # Eliminar cualquier fila donde la fecha no se pudo convertir, para evitar errores
    df.dropna(subset=['Fecha'], inplace=True)
    # Asegurar que las columnas numéricas sean tratadas como números
    for col in ['Objetivo (ml)', 'Real (ml)', 'Reducción Plan', 'dosis_media']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    # --- CORRECCIÓN APLICADA AQUÍ ---
    def calcular_estado(fecha_ts): # El argumento es un Timestamp de Pandas
        # Comparamos objetos del mismo tipo: date vs date
        if fecha_ts.date() < pd.Timestamp.now(tz='Europe/Madrid'):
            return "Pasado"
        elif fecha_ts.date() == pd.Timestamp.now(tz='Europe/Madrid'):
            return "Hoy"
        else:
            return "Futuro"

    df["Estado"] = df["Fecha"].apply(calcular_estado)

    # Opcional: Al final, convertir la columna de fecha de vuelta a string para una visualización consistente.
    df['Fecha'] = df['Fecha'].dt.strftime('%Y-%m-%d')

    return df
