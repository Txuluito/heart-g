from datetime import datetime, timedelta
from . import historial
import pandas as pd
import streamlit as st
from pandas import DataFrame

from dao.database import get_plan_history_data, save_plan_history_data




def objetivo_ml():
    df = st.session_state.df_tiempos.copy()
    if df.empty or "Fecha" not in df.columns:
        return 0
    row = df[df["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')]
    if not row.empty:
        return float(row['Objetivo (ml)'].iloc[0])
    else:
        return 0
def mlDesdeUltimaToma():
    return  objetivo_ml()/(24*60) * historial.minDesdeUltimaToma()
def mlAcumulados():
    return  mlDesdeUltimaToma() + float(st.session_state.config.get("tiempos.checkpoint_ml",0))
def mlAminutos(ml):
    if objetivo_ml() ==0:
        return 0
    resultado =(1140 * ml) / objetivo_ml()
    return int(resultado)
def minutosAml(minutos):
   return (objetivo_ml()/(24*60))/minutos
def minSiguienteDosisConBote():
    return  mlAminutos(dosis_actual() + mlAcumulados())
def intervalo_teorico():
    if dosis_actual ==0 or objetivo_ml() ==0:
        return 0
    return dosis_actual() / (objetivo_ml() / 1440.0)
def mins_espera():
    return  max(0, intervalo_teorico() - historial.minDesdeUltimaToma())
def mins_espera_saldo():
    saldo_actual = mlAcumulados()
    if saldo_actual < dosis_actual():
        return (dosis_actual() - saldo_actual) / (objetivo_ml() / 1440.0)
    return 0


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
        return float(0)
    row = df[df["Fecha"] == pd.Timestamp.now(tz='Europe/Madrid').strftime('%Y-%m-%d')]
    if not row.empty:
        return float(row['Dosis'].iloc[0])
    else:
        return float(0)
