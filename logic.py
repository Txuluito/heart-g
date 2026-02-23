import pandas as pd
import numpy as np
import database
from typing import Any
from pandas import DataFrame


from config import config

# Usamos caché para no llamar a Google Sheets en cada interacción (TTL = 10 minutos)
ahora = pd.Timestamp.now(tz='Europe/Madrid')

def tasaGeneracion():

    fecha_inicio_plan = pd.to_datetime(config.get("plan_start_date")) if config.get("plan_start_date") else ahora
    ml_reduccion_diaria = float(config.get("reduction_rate", 0.5))
    ml_iniciales_plan = float(config.get("plan_start_amount", 15.0))
    horas_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / 3600
    dias_flotantes = max(0.0, horas_desde_inicio / 24.0)
    objetivo_actual= max(0.0, ml_iniciales_plan - (ml_reduccion_diaria * dias_flotantes))
    return objetivo_actual / 24.0

def saldo(df):
    fecha_inicio_plan = pd.to_datetime(config.get("plan_start_date")) if config.get("plan_start_date") else ahora

    checkpoint_ingresos = float(config.get("checkpoint_ingresos", 0.0))
    consumo_total = df[df['timestamp'] >= fecha_inicio_plan]['ml'].sum()
    return (checkpoint_ingresos + ingresosTramo()) - consumo_total

def ingresosTramo():
    ml_reduccion_diaria = float(config.get("reduction_rate", 0.5))
    ml_iniciales_plan = float(config.get("plan_start_amount", 15.0))
    fecha_inicio_plan = pd.to_datetime(config.get("plan_start_date")) if config.get("plan_start_date") else ahora

    checkpoint_fecha_str = config.get("checkpoint_fecha", None)
    checkpoint_fecha = pd.to_datetime(checkpoint_fecha_str) if checkpoint_fecha_str else fecha_inicio_plan
    if checkpoint_fecha.tz is None:
        checkpoint_fecha = checkpoint_fecha.tz_localize('Europe/Madrid')

    horas_desde_inicio = (ahora - fecha_inicio_plan).total_seconds() / 3600

    def integral(t_h):
        if t_h < 0: return (ml_iniciales_plan / 24.0) * t_h
        t_fin = (ml_iniciales_plan / ml_reduccion_diaria) * 24 if ml_reduccion_diaria > 0 else 999999
        t_eff = min(t_h, t_fin)
        return (ml_iniciales_plan / 24.0) * t_eff - (ml_reduccion_diaria / 1152.0) * (t_eff ** 2)

    return integral(horas_desde_inicio) - integral((checkpoint_fecha - fecha_inicio_plan).total_seconds() / 3600)


def calcular_resumen_bloques(df):
    df_b = df.copy()
    df_b['horas_atras'] = (ahora - df_b['timestamp']).dt.total_seconds() / 3600
    df_b['bloque_n'] = np.floor(df_b['horas_atras'] / 24).astype(int)

    resumen = df_b.groupby('bloque_n').agg(
        total_ml=('ml', 'sum'),
        media_ml=('ml', 'mean'),
        num_tomas=('ml', 'count')
    ).sort_index()
    return resumen

def crear_plan(df, config):
    hoy = ahora.date()
    database.save_config({"plan_start_date": hoy.strftime('%Y-%m-%d')})
    config['plan_start_date'] = hoy.strftime('%Y-%m-%d')

    df_result = create_tabla_reduccion(df,{},hoy)
    database.save_plan_history_data(df_result)
    return df_result


def obtener_plan(df):
    # 1. Cargar parámetros del plan
    df_hist = database.get_plan_history_data()

    # Asegurar tipos numéricos
    if 'Objetivo (ml)' in df_hist.columns:
        df_hist['Objetivo (ml)'] = pd.to_numeric(df_hist['Objetivo (ml)'], errors='coerce').fillna(0)
    if 'Reducción Plan' in df_hist.columns:
        df_hist['Reducción Plan'] = pd.to_numeric(df_hist['Reducción Plan'], errors='coerce').fillna(0)

    # Convertimos a diccionario para búsqueda rápida por fecha
    history_cache = {}
    for _, row in df_hist.iterrows():
        history_cache[row['Fecha']] = row

    df_result = create_tabla_reduccion(df,history_cache,config.get("plan_start_date"))
    return df_result


def create_tabla_reduccion(df,history_cache: dict[Any, Any],raw_start) -> DataFrame:
    hoy = ahora.date()
    start_date = pd.to_datetime(str(raw_start).strip()).date()
    start_amount = float(config.get("plan_start_amount", 15.0))
    rate = float(config.get("reduction_rate", 0.1))
    dosis_media = float(config.get("dosis", 3.0))

    # 2. Agrupar consumo real por día
    df_real = df.copy()
    df_real['fecha_date'] = df_real['timestamp'].dt.date
    diario_real = df_real.groupby('fecha_date')['ml'].sum()

    if rate > 0:
        dias_estimados = int(start_amount / rate) + 1
        end_date = start_date + pd.Timedelta(days=dias_estimados)
    else:
        end_date = hoy + pd.Timedelta(days=30)  # Proyección por defecto si no hay reducción

    fechas = pd.date_range(start=start_date, end=max(end_date, hoy), freq='D')
    data_rows = []
    for i, fecha in enumerate(fechas):
        fecha_date = fecha.date()
        fecha_str = fecha_date.strftime('%d/%m/%Y')

        # Cálculos del Plan
        # Si es un día pasado y existe en caché, usamos el dato guardado (congelamos historia)
        if fecha_date < hoy and fecha_str in history_cache:
            objetivo = float(history_cache[fecha_str]['Objetivo (ml)'])
            reduccion_hoy = float(history_cache[fecha_str]['Reducción Plan'])
        else:
            objetivo = max(0.0, start_amount - ((i + 1) * rate))
            reduccion_hoy = rate

        # Intervalo teórico (minutos) = 24h / (Objetivo / Dosis)
        intervalo_teorico = int((24 * 60) / (objetivo / dosis_media)) if (objetivo > 0 and dosis_media > 0) else 0
        intervalo_str = f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m" if intervalo_teorico > 0 else "---"

        # Datos Reales
        consumo_real = diario_real.get(fecha_date, 0.0)

        if fecha_date < hoy:
            # Ciclo cerrado (días anteriores)
            estado = "✅ Sí" if consumo_real <= (objetivo + 0.5) else "❌ No"
        elif fecha_date == hoy:
            # Ciclo en curso (hoy)
            estado = "⏳ En curso" if consumo_real <= (objetivo + 0.5) else "⚠️ Excedido"
        else:
            # Días futuros
            estado = "🔮 Futuro"

        data_rows.append({
            "Fecha": fecha_str,
            "Objetivo (ml)": round(objetivo, 2),
            "Real (ml)": round(consumo_real, 2),
            "Reducción Plan": round(reduccion_hoy, 2),
            "Intervalo Teórico": intervalo_str,
            "Estado": estado
        })

    df_result = pd.DataFrame(data_rows)
    # Convertir a datetime para ordenar correctamente y no alfabéticamente
    df_result['fecha_dt'] = pd.to_datetime(df_result['Fecha'], format='%d/%m/%Y')
    df_result = df_result.sort_values('fecha_dt', ascending=True).drop(columns=['fecha_dt'])
    return df_result
