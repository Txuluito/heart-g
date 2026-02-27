import pandas as pd
from datetime import datetime, timedelta
# Importa las funciones que SÍ existen en tu database.py
from database import get_plan_history_data, save_plan_history_data, get_config, save_config,enviar_toma_api

def crear_tabla_reduccion(dosis_media, reduccion_por_dia, objetivo_inicial):
    """
    (LÓGICA PURA)
    Crea una tabla de reducción como un DataFrame de pandas. No interactúa con la base de datos.
    """
    tabla = []
    fecha_dia = datetime.now()
    objetivo_dia = objetivo_inicial

    while objetivo_dia > 0:
        # Intervalo teórico (minutos) = 24h / (Objetivo / Dosis)
        intervalo_teorico = int((24 * 60) / (objetivo_dia / dosis_media)) if (objetivo_dia > 0 and dosis_media > 0) else 0
        intervalo_str = f"{intervalo_teorico // 60}h {intervalo_teorico % 60}m" if intervalo_teorico > 0 else "---"

        # dosis_media=round(dosis_media, 2)

        tabla.append({
            "Fecha": fecha_dia.strftime("%Y-%m-%d"),
            "Objetivo (ml)": round(objetivo_dia, 2),
            "Real (ml)": 0,
            "Reducción Plan": round(reduccion_por_dia, 2),
            "Intervalo Teórico": intervalo_str,
            "Estado": "",
            "dosis_media": round(dosis_media, 2),
        })
        objetivo_dia = max(0, objetivo_dia - reduccion_por_dia)
        fecha_dia += timedelta(days=1)
        dosis_media = round(dosis_media, 2)

    return pd.DataFrame(tabla)

def obtener_datos_tabla():
    """
    (LEE DATOS de 'PlanHistory')
    Obtiene los datos del plan, los convierte a tipos correctos y calcula el estado.
    """
    df = get_plan_history_data() # <- CORREGIDO
    if df.empty:
        return pd.DataFrame()

    # Asegurar que las columnas numéricas sean tratadas como números
    for col in ['Objetivo (ml)', 'Real (ml)', 'Reducción Plan', 'dosis_media']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.tz_convert('Europe/Madrid')

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

    # Usamos axis=1 para pasar cada fila a la función
    # df["Estado"] = df["Fecha"].apply(calcular_estado)
    df['Estado'] = df.apply(calcular_estado, axis=1)
    df['dosis_media'] = df['dosis_media'].map('{:.2f}'.format)

    return df

def crear_nuevo_plan(dosis_media, reduccion_diaria, cantidad_inicial):
    """
    (ESCRIBE DATOS en 'PlanHistory')
    Limpia la hoja y guarda la nueva configuración del plan.
    """
    df_nuevo = crear_tabla_reduccion(dosis_media, reduccion_diaria, cantidad_inicial)
    save_plan_history_data(df_nuevo) # <- CORREGIDO
    save_config({
        "fecha_inicio_plan": pd.Timestamp.now(tz='Europe/Madrid').isoformat() ,  # Guardamos la nueva fecha
        "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat() ,  # Guardamos la nueva fecha
        "ml_iniciales_plan":cantidad_inicial,
        "checkpoint_ml":  0.0,
        "reduccion_diaria": reduccion_diaria,
        "dosis_media": dosis_media
    })

    print(f"Nuevo plan guardado en la hoja 'PlanHistory'.")
    return df_nuevo

def replanificar(dosis_media, reduccion_diaria, cantidad_inicial, mlBote):
    """
    (LEE Y ESCRIBE en 'Plan History')
    Recalcula los registros desde la fecha actual, conservando los anteriores.
    """
    df_existente = obtener_datos_tabla()
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d")
    
    df_conservada = df_existente[df_existente["Fecha"] < fecha_actual_str]
    df_nuevo = crear_tabla_reduccion(dosis_media, reduccion_diaria, cantidad_inicial)
    
    df_final = pd.concat([df_conservada, df_nuevo], ignore_index=True)

    save_plan_history_data(df_final) # <- CORREGIDO
    save_config({
        "ml_iniciales_plan": cantidad_inicial,
        "checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat() ,  # Guardamos la nueva fecha
        "checkpoint_ml": mlBote,
        "reduccion_diaria": reduccion_diaria,
        "dosis_media": dosis_media
    })

    print(f"Plan replanificado en la hoja 'PlanHistory'.")
    return df_final

def guardar_toma(fecha_toma, hora_toma, ml_toma,ml_bote):
    """
    (LEE Y ESCRIBE en 'PlanHistory' y 'Config')
    Guarda una toma, actualiza el plan y el checkpoint en la configuración.
    """

    nuevo_checkpoint_ml = ml_bote - ml_toma
    enviar_toma_api(fecha_toma.strftime('%d/%m/%Y'), hora_toma.strftime('%H:%M:%S'), ml_toma)

    fecha_hora_toma = datetime.combine(fecha_toma, hora_toma)
    fecha_hora_toma = pd.Timestamp(fecha_hora_toma).tz_localize('Europe/Madrid')
    df_plan = obtener_datos_tabla()
    df_plan["Fecha"]=df_plan["Fecha"].dt.strftime('%Y-%m-%d')
    print(f"[guardar_toma] Argumentos -> df_plan['Fecha']: {df_plan["Fecha"]}")
    fecha_toma = pd.Timestamp(fecha_toma).tz_localize('Europe/Madrid')
    if fecha_toma.strftime('%Y-%m-%d') not in df_plan["Fecha"].values:
        print(f"ERROR: La fecha {fecha_toma} no se encontró en el plan.")
    else:
        # print(f"[guardar_toma] Argumentos -> fecha: {df_plan['Fecha'].dt.date()}, (Tipo: {type(df_plan['Fecha'].dt.date())})")
        print(f"[guardar_toma] Argumentos -> fecha: {df_plan})")
        df_plan.loc[df_plan['Fecha'] == fecha_toma.strftime('%Y-%m-%d'), 'Real (ml)'] += ml_toma
        print(f"[guardar_toma] Argumentos -> fecha: {df_plan})")
        save_plan_history_data(df_plan)  # <- CORREGIDO
        # 3. Actualizar los valores del checkpoint EN la configuración existente

        save_config({"checkpoint_fecha": pd.Timestamp.now(tz='Europe/Madrid').isoformat() ,
                     "checkpoint_ml"   : nuevo_checkpoint_ml})
        print(f"Toma de {ml_toma} ml guardada para el día {fecha_toma}.")
        print(f"Checkpoint en 'Config' actualizado a fecha {fecha_hora_toma} con {nuevo_checkpoint_ml:.2f}ml.")

    return df_plan

def borrar_toma(fecha_toma, cantidad):
    """
    (LEE Y ESCRIBE en 'PlanHistory')
    Resta una cantidad de una toma. No revierte el checkpoint.
    """
    df_plan = obtener_datos_tabla()

    if fecha_toma not in df_plan["Fecha"].values:
        print(f"ERROR: La fecha {fecha_toma} no se encontró en el plan.")
        return df_plan
            
    df_plan.loc[df_plan["Fecha"] == fecha_toma, "Real (ml)"] -= cantidad
    save_plan_history_data(df_plan) # <- CORREGIDO
    df_plan.loc[df_plan["Fecha"] == fecha_toma, "Real (ml)"] -= cantidad
    print(f"Toma de {cantidad}ml borrada para el día {fecha_toma}.")
    print("ADVERTENCIA: La lógica del checkpoint no se revierte automáticamente al borrar.")
            
    return df_plan

