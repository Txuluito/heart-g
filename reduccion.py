import pandas as pd

import reduccion_por_dosis
import reduccion_por_tiempo
# Importa las funciones de base de datos
from database import save_plan_history_data, save_config, enviar_toma_api


def guardar_toma(fecha_toma, hora_toma, ml_toma):
    enviar_toma_api(fecha_toma.strftime('%d/%m/%Y'), hora_toma.strftime('%H:%M:%S'), ml_toma)
    reduccion_por_tiempo.add_toma(fecha_toma, ml_toma)
    reduccion_por_dosis.add_toma(fecha_toma, ml_toma)
    save_config({
        "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "tiempos.checkpoint_ml":  reduccion_por_tiempo.mlAcumulados() - ml_toma,
        "dosis.checkpoint_ml": reduccion_por_tiempo.mlAcumulados() - ml_toma,
    })


def crear_nuevo_plan(ml_dia_actual, ml_dosis_actual, intervalo_horas,reduccion_diaria):
    save_plan_history_data(reduccion_por_tiempo.crear_tabla(ml_dosis_actual, reduccion_diaria, ml_dia_actual), sheet_name="Plan Tiempo")
    save_plan_history_data(reduccion_por_dosis.crear_tabla(reduccion_diaria, ml_dia_actual, intervalo_horas), sheet_name="Plan Dosis")
    save_config({
        "plan.fecha_inicio_plan": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "plan.reduccion_diaria": reduccion_diaria,
        "consumo.ml_dia": ml_dia_actual,
        "consumo.intervalo_minutos": (intervalo_horas.hour * 60) + intervalo_horas.minute,
        "consumo.ml_dosis": ml_dosis_actual,
        "dosis.checkpoint_ml": 0.0,
        "tiempos.checkpoint_ml": 0.0
    })

    print(f"Nuevo plan por dosis guardado.")

def replanificar(ml_dia_actual, ml_dosis_actual, intervalo_horas,reduccion_diaria):

   reduccion_por_tiempo.replanificar(ml_dosis_actual, reduccion_diaria, ml_dia_actual)
   reduccion_por_dosis.replanificar(reduccion_diaria, ml_dia_actual, intervalo_horas)
   
   save_config({
       "plan.checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
       "plan.reduccion_diaria": reduccion_diaria,
       "consumo.ml_dia": ml_dia_actual,
       "consumo.intervalo_minutos": (intervalo_horas.hour * 60) + intervalo_horas.minute,
       "consumo.ml_dosis": ml_dosis_actual,
       "tiempos.checkpoint_ml":  reduccion_por_tiempo.mlAcumulados(),
       "dosis.checkpoint_ml":  reduccion_por_dosis.mlAcumulados()
   })
