import pandas as pd
import numpy as np
import json
import os
import database
import streamlit as st

# Usamos caché para no llamar a Google Sheets en cada interacción (TTL = 10 minutos)
@st.cache_data(ttl=600, show_spinner=False)
def get_cached_config():
    return database.get_remote_config()

def load_config():
    # Cargamos la configuración desde la caché
    return get_cached_config()

def save_config(data):
    # Guardamos la configuración en Google Sheets
    database.save_remote_config(data)
    # Limpiamos la caché para que la próxima vez se descargue la nueva configuración
    get_cached_config.clear()

def calcular_resumen_bloques(df):
    ahora = pd.Timestamp.now(tz='Europe/Madrid')
    df_b = df.copy()
    df_b['horas_atras'] = (ahora - df_b['timestamp']).dt.total_seconds() / 3600
    df_b['bloque_n'] = np.floor(df_b['horas_atras'] / 24).astype(int)

    resumen = df_b.groupby('bloque_n').agg(
        total_ml=('ml', 'sum'),
        media_ml=('ml', 'mean'),
        num_tomas=('ml', 'count')
    ).sort_index()
    return resumen

def calcular_seguimiento_plan(df, config, force_recalc=False):
    """
    Genera un DataFrame con el seguimiento diario del plan:
    Fecha | Objetivo (Plan) | Real | Reducción | Intervalo Teórico | Cumplido
    """
    # 1. Cargar parámetros del plan
    try:
        raw_start = config.get("plan_start_date", str(pd.Timestamp.now().date()))
        s_start = str(raw_start).strip()
        if len(s_start) == 8 and s_start.isdigit():
             start_date = pd.to_datetime(s_start, format='%Y%m%d').date()
        else:
             start_date = pd.to_datetime(s_start).date()
    except:
        start_date = pd.Timestamp.now().date()
        
    start_amount = float(config.get("plan_start_amount", 15.0))
    rate = float(config.get("reduction_rate", 0.1))
    dosis_media = float(config.get("dosis", 3.0))

    # 2. Agrupar consumo real por día
    df_real = df.copy()
    df_real['fecha_date'] = df_real['timestamp'].dt.date
    diario_real = df_real.groupby('fecha_date')['ml'].sum()

    # 3. Generar calendario completo (Pasado + Futuro hasta fin del plan)
    hoy = pd.Timestamp.now(tz='Europe/Madrid').date()
    
    if rate > 0:
        dias_estimados = int(start_amount / rate) + 1
        end_date = start_date + pd.Timedelta(days=dias_estimados)
    else:
        end_date = hoy + pd.Timedelta(days=30) # Proyección por defecto si no hay reducción

    fechas = pd.date_range(start=start_date, end=max(end_date, hoy), freq='D')

    # --- LÓGICA DE CACHÉ (GOOGLE SHEETS) ---
    history_cache = {}
    df_hist = pd.DataFrame()
    if not force_recalc:
        df_hist = database.get_plan_history_data()
        if not df_hist.empty:
            # Asegurar tipos numéricos
            if 'Objetivo (ml)' in df_hist.columns:
                df_hist['Objetivo (ml)'] = pd.to_numeric(df_hist['Objetivo (ml)'], errors='coerce').fillna(0)
            if 'Reducción Plan' in df_hist.columns:
                df_hist['Reducción Plan'] = pd.to_numeric(df_hist['Reducción Plan'], errors='coerce').fillna(0)
            
            # Convertimos a diccionario para búsqueda rápida por fecha
            for _, row in df_hist.iterrows():
                history_cache[row['Fecha']] = row

    data_rows = []
    for i, fecha in enumerate(fechas):
        fecha_date = fecha.date()
        fecha_str = fecha_date.strftime('%d/%m/%Y')
        
        # Cálculos del Plan
        # Si es un día pasado y existe en caché, usamos el dato guardado (congelamos historia)
        if not force_recalc and fecha_date < hoy and fecha_str in history_cache:
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
    
    # Guardamos en Google Sheets automáticamente SOLO SI HAY CAMBIOS
    # Esto evita el error de Timeout por guardar en cada renderizado
    guardar = True
    if not force_recalc and not df_hist.empty:
        try:
            # Comparamos si el resultado nuevo es igual al historial cargado
            # Convertimos a lista de dicts para comparar contenido ignorando índices
            new_data = df_result.to_dict(orient='records')
            old_data = df_hist.to_dict(orient='records')
            
            # Si tienen la misma longitud y contenido, no guardamos
            if new_data == old_data:
                guardar = False
        except Exception:
            # Si falla la comparación por tipos de datos, guardamos por seguridad
            guardar = True
            
    if guardar:
        database.save_plan_history_data(df_result)
        
    return df_result

def obtener_media_3d(resumen):
    if len(resumen) >= 4:
        return resumen.iloc[1:4]['total_ml'].mean()
    elif len(resumen) >= 2:
        return resumen.iloc[1]['total_ml']
    return 15.0  # Valor por defecto
def calcular_concentracion_dinamica(df_final, df_excel, ka_val, hl_val):
    k_el = np.log(2) / hl_val
    timeline = df_final.index
    concentracion = np.zeros(len(timeline))

    for _, row in df_excel.iterrows():
        # Calcular tiempo transcurrido desde cada toma en horas
        t = (timeline - row['timestamp']).total_seconds() / 3600
        mask = t >= 0

        # Evitar división por cero si ka == k_el
        curr_ka = ka_val if ka_val != k_el else ka_val + 0.01

        factor_escala = curr_ka / (curr_ka - k_el)
        curva = row['ml'] * factor_escala * (np.exp(-k_el * t[mask]) - np.exp(-curr_ka * t[mask]))
        concentracion[mask] += curva

    res = pd.Series(concentracion, index=timeline)
    res[res < 0.05] = 0  # Limpiar ruido visual bajo
    return res
def rellenar_datos_sin_frecuencia(df_fit, df_excel):
    # Determinar el punto de inicio
    if df_fit.empty:
        inicio = df_excel['timestamp'].min() if not df_excel.empty else pd.Timestamp.now(tz='Europe/Madrid')
    else:
        inicio = df_fit.index.max()

    ahora = pd.Timestamp.now(tz='Europe/Madrid').floor('1min')

    if ahora > inicio:
        rango = pd.date_range(start=inicio + pd.Timedelta(minutes=1), end=ahora, freq='1min')
        df_relleno = pd.DataFrame(index=rango)
        return pd.concat([df_fit, df_relleno]).sort_index()
    return df_fit