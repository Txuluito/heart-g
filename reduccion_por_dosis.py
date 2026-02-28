import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
# Importa las funciones de base de datos
from database import get_plan_history_data, save_plan_history_data, get_config, save_config, enviar_toma_api

def mlAcumulados():
    if st.session_state.config.get("checkpoint_fecha"):
        dosis_actual = float(st.session_state.config.get("dosis.dosis_inicial", 3.0))
        intervalo = float(st.session_state.config.get("dosis.intervalo_horas", 2.0))

        # Tasa de generación (ml/hora) = Dosis / Intervalo
        tasa_generacion = dosis_actual / intervalo if intervalo > 0 else 0

        checkpoint_ml = float(st.session_state.config.get("checkpoint_ml", 0.0))
        checkpoint_fecha = pd.to_datetime(st.session_state.config.get("checkpoint_fecha"))

        if checkpoint_fecha.tzinfo is None or checkpoint_fecha.tzinfo.utcoffset(pd.Timestamp.now(tz='Europe/Madrid')) is None:
            checkpoint_fecha = checkpoint_fecha.tz_localize('UTC').tz_convert('Europe/Madrid')
        else:
            checkpoint_fecha = checkpoint_fecha.tz_convert('Europe/Madrid')

        horas_pasadas = (pd.Timestamp.now(tz='Europe/Madrid') - checkpoint_fecha).total_seconds() / 3600

        generado = tasa_generacion * horas_pasadas
        return float(checkpoint_ml + generado)
    else:
        return float(0)


def crear_tabla(dosis_inicial, reduccion_dosis, intervalo_horas):
    """
    (LÓGICA PURA)
    Crea una tabla de reducción manteniendo el intervalo fijo y reduciendo la dosis por toma.
    """
    tabla = []
    fecha_dia = datetime.now()
    dosis_actual = float(dosis_inicial)
    reduccion_dosis = float(reduccion_dosis)
    intervalo_horas = float(intervalo_horas)
    tomas_dia = 24.0 / intervalo_horas
    
    # Límite de seguridad
    max_dias = 365
    dias_count = 0

    while dosis_actual >= 0.1 and dias_count < max_dias:
        total_dia = dosis_actual * tomas_dia

        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(total_dia, 2),
            "Real (ml)": 0.0,
            "Dosis Obj (ml)": round(dosis_actual, 3),
            "Intervalo": f"{intervalo_horas}h",
            "Reducción Dosis": round(reduccion_dosis, 3),
            "Estado": ""
        })
        
        dosis_actual = max(0.0, dosis_actual - reduccion_dosis)
        fecha_dia += timedelta(days=1)
        dias_count += 1

    return pd.DataFrame(tabla)

def obtener_datos_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data(sheet_name="PlanHistoryDosis")
    if df.empty:
        return pd.DataFrame()

    # Asegurar tipos numéricos
    cols_num = ['Objetivo (ml)', 'Real (ml)', 'Dosis Obj (ml)', 'Reducción Dosis']
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    if 'Fecha' in df.columns:
        # Convertir a datetime
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        # Si no tiene zona horaria, se la ponemos (asumimos UTC o local y convertimos)
        if df['Fecha'].dt.tz is None:
             # Si asumimos que vienen como string "YYYY-MM-DD", al parsear son naive.
             # Las localizamos a Madrid directamente o convertimos si fuera necesario.
             # Para simplificar y ser consistentes con el resto de la app:
             df['Fecha'] = df['Fecha'].dt.tz_localize('Europe/Madrid')
        else:
             df['Fecha'] = df['Fecha'].dt.tz_convert('Europe/Madrid')

    hoy = datetime.now().date()
    
    def calcular_estado(row):
        fecha_row = row["Fecha"].date()
        if fecha_row < hoy:
            # Ciclo cerrado
            if row['Real (ml)'] <= row['Objetivo (ml)'] + 0.5:
                return "✅ Sí"
            else:
                return "❌ No"
        elif fecha_row == hoy:
            # Ciclo en curso
            return "⏳ En curso"
        else:
            # Días futuros
            return "🔮 Futuro"

    if 'Fecha' in df.columns:
        df['Estado'] = df.apply(calcular_estado, axis=1)

    return df

def crear_nuevo_plan(dosis_inicial, reduccion_dosis, intervalo_horas):
    """
    (ESCRIBE DATOS en 'PlanHistory')
    Crea un nuevo plan basado en reducción de dosis con intervalo fijo.
    """
    df_nuevo = crear_tabla(dosis_inicial, reduccion_dosis, intervalo_horas)
    save_plan_history_data(df_nuevo, sheet_name="PlanHistoryDosis")

    save_config({
        "fecha_inicio_plan": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "tipo_plan": "dosis", # Marca el tipo de plan activo
        "dosis.dosis_inicial": dosis_inicial,
        "dosis.reduccion_dosis": reduccion_dosis,
        "dosis.intervalo_horas": intervalo_horas,
        "checkpoint_ml": 0.0
    })

    print(f"Nuevo plan por dosis guardado.")
    return df_nuevo

def replanificar(dosis_inicial, reduccion_dosis, intervalo_horas, ml_acumulados):
    """
    (LEE Y ESCRIBE en 'PlanHistory')
    Recalcula el futuro manteniendo el historial pasado.
    """
    df_existente = obtener_datos_tabla()
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
    
    # Conservar historial pasado
    if not df_existente.empty and 'Fecha' in df_existente.columns:
        # Convertir a string para comparar fechas solamente
        mask = df_existente["Fecha"].dt.strftime("%Y-%m-%d") < fecha_actual_str
        df_conservada = df_existente[mask]
    else:
        df_conservada = pd.DataFrame()
        
    df_nuevo = crear_tabla(dosis_inicial, reduccion_dosis, intervalo_horas)
    
    # Aseguramos que las columnas coincidan para el concat
    # (podría haber diferencias si el plan anterior era por tiempo)
    df_final = pd.concat([df_conservada, df_nuevo], ignore_index=True)

    # Limpieza final antes de guardar
    if 'Estado' in df_final.columns:
        df_final = df_final.drop(columns=['Estado'])

    save_plan_history_data(df_final, sheet_name="PlanHistoryDosis")

    save_config({
        "dosis.dosis_inicial": dosis_inicial,
        "dosis.reduccion_dosis": reduccion_dosis,
        "dosis.intervalo_horas": intervalo_horas,
        "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
        "checkpoint_ml": ml_acumulados,
        "tipo_plan": "dosis"
    })

    print(f"Plan replanificado por dosis.")
    return df_final

def guardar_toma(fecha_toma, hora_toma, ml_toma, ml_bote):
    """
    (LEE Y ESCRIBE)
    Guarda una toma en la API y actualiza la tabla localmente.
    """
    nuevo_checkpoint_ml = ml_bote - ml_toma
    enviar_toma_api(fecha_toma.strftime('%d/%m/%Y'), hora_toma.strftime('%H:%M:%S'), ml_toma)

    # Actualizar tabla local
    df_plan = obtener_datos_tabla()
    
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
        
        save_plan_history_data(df_to_save, sheet_name="PlanHistoryDosis")

        save_config({
            "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat(),
            "checkpoint_ml": nuevo_checkpoint_ml
        })
        print(f"Toma guardada. Checkpoint actualizado.")
    else:
        print(f"ERROR: La fecha {fecha_toma_str} no se encontró en el plan.")

    return df_plan