import pandas as pd
import numpy as np

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
