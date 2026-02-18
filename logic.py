import pandas as pd
import numpy as np
import json
import os

CONFIG_FILE = "config/config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(data):
    config = load_config()
    config.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

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

    ahora = pd.Timestamp.now(tz='Europe/Madrid').floor('1T')

    if ahora > inicio:
        rango = pd.date_range(start=inicio + pd.Timedelta(minutes=1), end=ahora, freq='1T')
        df_relleno = pd.DataFrame(index=rango)
        return pd.concat([df_fit, df_relleno]).sort_index()
    return df_fit