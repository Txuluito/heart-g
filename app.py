import streamlit as st
import pandas as pd
import numpy as np
import os.path
import time
import requests
import plotly.graph_objects as go
import json
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from plotly.subplots import make_subplots

URL_WEB_APP = "https://script.google.com/macros/s/AKfycbyW6E3Quf20DNCtsD9SsxxC4isMxqCzAv6JqKu6LYtuJhRLcfgo00Ay_e3BWg574TUU/exec"
# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="GHB & HR Analyzer", layout="wide")
st.title("🧪 Bio-Análisis: GHB vs. Frecuencia Cardíaca")


def enviar_toma_api(fecha_str, hora_str, cantidad):
    # PEGA AQUÍ LA URL QUE COPIASTE DEL PASO ANTERIOR
    payload = {
        "fecha": fecha_str,
        "hora": hora_str,
        "ml": cantidad
    }

    try:
        # Enviamos los datos mediante POST
        response = requests.post(URL_WEB_APP, json=payload)
        if response.status_code == 200:
            st.success(f"✅ Registrado en Google Sheets: {cantidad}ml")
            st.balloons()
            time.sleep(1)
            st.rerun()
        else:
            st.error("Error al conectar con la hoja.")
    except Exception as e:
        st.error(f"Fallo de conexión: {e}")


def mediasConsumos():
    st.subheader("📊 Media de Consumo por cada 24 Horas")

    if not tabla_excel.empty:
        df_agrupado = tabla_excel.copy()
        df_agrupado = df_agrupado.set_index('timestamp')

        # Nos aseguramos de que 'ml' sea numérico por si acaso
        df_agrupado['ml'] = pd.to_numeric(df_agrupado['ml'], errors='coerce')

        # FILTRADO: Solo operamos sobre la columna 'ml' para evitar el error de 'object'
        resumen_diario = df_agrupado[['ml']].resample('D').agg(['mean', 'sum', 'count'])

        # Limpiamos los nombres de las columnas (vienen de un MultiIndex)
        resumen_diario.columns = ['Media (ml)', 'Total (ml)', 'Nº de Tomas']

        # Eliminar días sin datos para que la tabla no sea infinita
        resumen_diario = resumen_diario.dropna(subset=['Total (ml)'])

        # Formatear índice
        resumen_diario.index = resumen_diario.index.strftime('%d/%m/%Y')

        st.dataframe(resumen_diario.sort_index(ascending=False), use_container_width=True)

        media_total = resumen_diario['Media (ml)'].mean()
        st.info(f"💡 Tu media histórica de consumo diario es de **{media_total:.2f} ml** por toma.")
    else:
        st.write("No hay datos suficientes.")


def get_google_fit_data():
    creds = None
    scopes = ['https://www.googleapis.com/auth/fitness.heart_rate.read']

    # 1. INTENTAR CARGAR DESDE SECRETS (Sin que rompa la app si no existen)
    try:
        if "google_fit_token" in st.secrets:
            token_info = json.loads(st.secrets["google_fit_token"])
            creds = Credentials.from_authorized_user_info(token_info, scopes)
    except Exception:
        # Si falla o no existen secrets, no hacemos nada y pasamos al punto 2
        pass

    # 2. SI NO HAY CREDS, BUSCAR ARCHIVO LOCAL (Modo PC)
    if not creds and os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', scopes)

    # 3. Si el token expiró, refrescarlo
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Opcional: imprimir el nuevo token en consola para actualizar el Secret si fuera necesario

    # 4. Si no hay credenciales válidas, iniciar flujo (Solo local)
    if not creds or not creds.valid:
        if os.path.exists('credentials.json'):
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json',scopes)
            creds = flow.run_local_server(port=0)
        else:
            st.error("No se han encontrado credenciales de Google. Configura los Secrets en Streamlit Cloud.")
            st.stop()

    service = build('fitness', 'v1', credentials=creds)
    body = {
        "aggregateBy": [
            {"dataSourceId": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"}],
        "bucketByTime": {"durationMillis": 60000},
        "startTimeMillis": int(time.time() * 1000) - (48 * 60 * 60 * 1000),  # Pedimos 48h para los bloques
        "endTimeMillis": int(time.time() * 1000)
    }

    raw_data = service.users().dataset().aggregate(userId='me', body=body).execute()
    extracted_data = []
    for bucket in raw_data.get('bucket', []):
        for dataset in bucket.get('dataset', []):
            for point in dataset.get('point', []):
                ts = pd.to_datetime(int(point['endTimeNanos']), unit='ns', utc=True).tz_convert('Europe/Madrid')
                value = point['value'][0]['fpVal']
                extracted_data.append({'timestamp': ts, 'hr': value})

    df = pd.DataFrame(extracted_data)
    if not df.empty:
        df = df.set_index('timestamp').sort_index()
        df = df.resample('1T').mean().interpolate()
    return df


def get_excel_data():
    url_sheets = f"https://docs.google.com/spreadsheets/d/18KYPnVSOQF6I2Lm5P1j5nFx1y1RXSmfMWf9jBR2WJ-Q/export?format=csv&cache_bust={int(time.time())}"
    df = pd.read_csv(url_sheets)

    # 1. Normalizar nombres de columnas
    df.columns = df.columns.str.strip().str.lower()

    # 2. LIMPIEZA CRÍTICA DE NÚMEROS:
    # Convierte "3,2" en 3.2 y maneja posibles errores
    if 'ml' in df.columns:
        df['ml'] = (
            df['ml']
            .astype(str)  # Convertimos a texto por si hay mezcla
            .str.replace(',', '.')  # Cambiamos coma por punto
            .str.strip()  # Quitamos espacios
            .pipe(pd.to_numeric, errors='coerce')  # Convertimos a número real
            .fillna(0)  # Si algo falla, ponemos 0 en lugar de romper
        )

    # 3. Procesamiento de fecha y hora
    df['timestamp'] = pd.to_datetime(
        df['fecha'] + ' ' + df['hora'],
        format='mixed',
        dayfirst=True
    )

    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Madrid')
    else:
        df['timestamp'] = df['timestamp'].dt.tz_convert('Europe/Madrid')

    return df


# --- LÓGICA DE PROCESAMIENTO ---

def rellenarDatosSinFrecuencia():
    global tabla_final
    if tabla_final.empty:
        ultimo_registro_tiempo = tabla_excel['timestamp'].min() if not tabla_excel.empty else pd.Timestamp.now(
            tz='Europe/Madrid')
    else:
        ultimo_registro_tiempo = tabla_final.index.max()

    ahora = pd.Timestamp.now(tz='Europe/Madrid').floor('1T')
    if ahora > ultimo_registro_tiempo:
        rango_faltante = pd.date_range(start=ultimo_registro_tiempo + pd.Timedelta(minutes=1), end=ahora, freq='1T')
        df_relleno = pd.DataFrame(index=rango_faltante)
        tabla_final = pd.concat([tabla_final, df_relleno]).sort_index()


def calcularConcentracionDinamica(ka_val, hl_val):
    k_el = np.log(2) / hl_val
    timeline = tabla_final.index
    concentracion = np.zeros(len(timeline))

    for _, row in tabla_excel.iterrows():
        t = (timeline - row['timestamp']).total_seconds() / 3600
        mask = t >= 0
        curr_ka = ka_val if ka_val != k_el else ka_val + 0.01
        factor_escala = curr_ka / (curr_ka - k_el)
        curva = row['ml'] * factor_escala * (np.exp(-k_el * t[mask]) - np.exp(-curr_ka * t[mask]))
        concentracion[mask] += curva

    res = pd.Series(concentracion, index=timeline)
    res[res < 0.05] = 0
    return res


# --- COMPONENTES DE INTERFAZ ---

def historico_consumo24h():
    global resumen_bloques
    st.subheader("📊 Consumo en bloques de 24h (desde ahora)")
    if not tabla_excel.empty:
        ahora = pd.Timestamp.now(tz='Europe/Madrid')
        df_bloques = tabla_excel.copy()
        df_bloques['horas_atras'] = (ahora - df_bloques['timestamp']).dt.total_seconds() / 3600
        df_bloques['bloque_n'] = np.floor(df_bloques['horas_atras'] / 24).astype(int)

        resumen_bloques = df_bloques.groupby('bloque_n').agg(
            total_ml=('ml', 'sum'),
            media_ml=('ml', 'mean'),
            num_tomas=('ml', 'count')
        ).sort_index()

        def etiqueta_tiempo(n):
            if n == 0: return "Últimas 24h"
            return f"Hace {int(n * 24)}h - {int((n + 1) * 24)}h"

        resumen_bloques.index = [etiqueta_tiempo(n) for n in resumen_bloques.index]
        st.dataframe(resumen_bloques, use_container_width=True)


def planificadorReduccion():
    st.header("📉 Planificador de Reducción")
    ahora_local = pd.Timestamp.now(tz='Europe/Madrid')

    try:
        if len(resumen_bloques) >= 2:
            consumo_ref = resumen_bloques.iloc[1]['total_ml']
            msg_ref = "Bloque 24h-48h"
        else:
            consumo_ref = resumen_bloques.iloc[0]['total_ml'] if not resumen_bloques.empty else 0.0
            msg_ref = "Bloque actual"
    except:
        consumo_ref, msg_ref = 0.0, "Sin datos"

    # --- FILA 1: DATOS DE REFERENCIA Y OBJETIVO ---
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.write(f"📊 **Base de referencia:** {consumo_ref:.2f} ml")
        st.caption(f"Calculado sobre: {msg_ref}")
    with col_info2:
        # Dejamos espacio para el cálculo del objetivo que viene abajo
        pass

        # --- FILA 2: SELECTORES DE AJUSTE ---
    col_adj1, col_adj2 = st.columns(2)
    with col_adj1:
        dosis = st.number_input("Dosis habitual (ml):", 0.1, 10.0, 3.2, 0.05)
    with col_adj2:
        reducir = st.slider("ML a reducir respecto a base:", 0.0, max(float(consumo_ref), 0.1), 0.0, 0.05)

    # Calculamos el objetivo después de los inputs
    objetivo = max(0.0, consumo_ref - reducir)

    # Ahora rellenamos la información de la Fila 1 (Objetivo) con un st.info para que resalte
    with col_info2:
        st.markdown(f"🎯 **Objetivo 24h:** `{objetivo:.2f} ml`")
        st.caption(f"Reducción del {((reducir / consumo_ref) * 100 if consumo_ref > 0 else 0):.1f}%")

    if objetivo > 0:
        intervalo_min = int((24 / (objetivo / dosis)) * 60)
        h_obj, m_obj = intervalo_min // 60, intervalo_min % 60
        texto_espera = f"{h_obj}h {m_obj}min" if h_obj > 0 else f"{m_obj}min"

        ultima_toma = tabla_excel['timestamp'].max()

        # Cálculos de tiempos
        pasado_mins = (ahora_local - ultima_toma).total_seconds() / 60
        h_pas, m_pas = int(pasado_mins // 60), int(pasado_mins % 60)

        proxima_toma = ultima_toma + pd.Timedelta(minutes=intervalo_min)
        dif_restante = (proxima_toma - ahora_local).total_seconds() / 60

        st.markdown("---")
        st.subheader("⏱️ Control de Tiempos")
        t1, t2, t3 = st.columns(3)

        t1.metric("Desde última toma", f"{h_pas}h {m_pas}min")
        t2.metric("Intervalo Objetivo", texto_espera)

        if dif_restante > 0:
            st.session_state['abrir_registro'] = False  # Todavía falta tiempo
            h_res, m_res = int(dif_restante // 60), int(dif_restante % 60)
            t3.metric("Siguiente Dosis en", f"{h_res}h {m_res}min", delta="En espera", delta_color="inverse")

            progreso = min(max(pasado_mins / intervalo_min, 0.0), 1.0)
            st.progress(progreso)
            st.warning(f"⏳ **Disponible a las:** {proxima_toma.strftime('%H:%M')}")
        else:
            st.session_state['abrir_registro'] = True
            extra_mins = abs(dif_restante)
            h_ext, m_ext = int(extra_mins // 60), int(extra_mins % 60)
            t3.metric("Siguiente Dosis", "¡LISTO!", delta=f"+{h_ext}h {m_ext}min", delta_color="normal")
            st.progress(1.0)
            st.success(f"✅ **Intervalo cumplido.**")

        st.markdown("#### Resumen del día")
        m_a, m_b = st.columns(2)
        m_a.metric("Tomas/día permitidas", f"{(objetivo / dosis):.1f}")

        consumo_hoy = resumen_bloques.iloc[0]['total_ml'] if not resumen_bloques.empty else 0
        m_b.metric("Meta hoy", f"{objetivo:.2f} ml", delta=f"{objetivo - consumo_hoy:.2f} ml restantes")
    elif objetivo == 0:
        st.success("🏁 Plan de cese de consumo activo.")

def metricas():
    c1, c2, c3 = st.columns(3)
    df_c = tabla_final.dropna(subset=['hr', 'ghb_active'])
    if len(df_c) > 5:
        corr = df_c['hr'].corr(df_c['ghb_active'])
        c1.metric("Correlación Pulso/GHB", f"{corr:.2f}")
    else:
        c1.metric("Correlación", "Calculando...")
    c2.metric("Nivel Estimado", f"{tabla_final['ghb_active'].iloc[-1]:.2f} ml")
    ultimo_p = tabla_final['hr'].dropna()
    c3.metric("Último Pulso", f"{int(ultimo_p.iloc[-1])} LPM" if not ultimo_p.empty else "---")


def graficas():
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=tabla_final.index, y=tabla_final['hr'], name="LPM", line=dict(color="#FF4B4B")),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=tabla_final.index, y=tabla_final['ghb_active'], name="GHB (ml)", fill='tozeroy',
                             line=dict(color="rgba(0,150,255,0.5)")), secondary_y=True)
    fig.update_layout(hovermode="x unified", height=500)
    st.plotly_chart(fig, use_container_width=True)


def eliminar_ultima_toma():
    global e
    try:
        # Enviamos la orden a Google
        respuesta = requests.get(f"{URL_WEB_APP}?action=borrarUltima")

        if "Success" in respuesta.text:
            st.success("✅ Fila eliminada en Google Sheets.")
            time.sleep(1.5)
            st.rerun()  # Recarga la app para actualizar la tabla
        else:
            st.error("No hay más datos para borrar o la hoja está vacía.")
    except Exception as e:
        st.error(f"Error de conexión: {e}")


# --- EJECUCIÓN PRINCIPAL ---
try:
    tabla_excel = get_excel_data()
    tabla_final = get_google_fit_data()
    rellenarDatosSinFrecuencia()

    tab1, tab2, tab3 = st.tabs(["📉 Reductor y Planificación", "📊 Gráficas y Frecuencia", "📜 Historial Detallado de Tomas"])

    with tab1:
        # 1. CÁLCULOS PREVIOS (Invisibles)
        ahora = pd.Timestamp.now(tz='Europe/Madrid')
        if not tabla_excel.empty:
            df_bloques = tabla_excel.copy()
            df_bloques['horas_atras'] = (ahora - df_bloques['timestamp']).dt.total_seconds() / 3600
            df_bloques['bloque_n'] = np.floor(df_bloques['horas_atras'] / 24).astype(int)
            resumen_bloques = df_bloques.groupby('bloque_n').agg(
                total_ml=('ml', 'sum'),
                media_ml=('ml', 'mean'),
                num_tomas=('ml', 'count')
            ).sort_index()

            consumo_ref = resumen_bloques.iloc[1]['total_ml'] if len(resumen_bloques) >= 2 else resumen_bloques.iloc[0][
                'total_ml']
        else:
            consumo_ref = 0.0

        # --- SECCIÓN 1: AJUSTES DEL PLAN (ARRIBA, PANEL DE CONTROL) ---
        with st.expander("⚙️ CONFIGURACIÓN DEL PLAN Y OBJETIVOS", expanded=False):
            c_adj1, c_adj2 = st.columns(2)
            with c_adj1:
                dosis = st.number_input("Dosis habitual (ml):", 0.1, 10.0, 3.2, 0.05)
            with c_adj2:
                reducir = st.slider("ML a reducir respecto a base:", 0.0, max(float(consumo_ref), 1.0), 1.0, 0.05)

            objetivo = max(0.0, consumo_ref - reducir)
            st.info(f"🎯 **Objetivo 24h:** {objetivo:.2f} ml (Basado en referencia de {consumo_ref:.2f} ml)")

        # --- SECCIÓN 2: ESTADO DEL INTERVALO (DINÁMICO) ---
        col_t1, col_t2, col_t3 = st.columns(3)
        placeholder_progreso = st.empty()
        placeholder_mensaje = st.empty()

        # --- LÓGICA DINÁMICA DE TIEMPOS ---
        if objetivo > 0:
            intervalo_min = int((24 / (objetivo / dosis)) * 60)
            ultima_toma = tabla_excel['timestamp'].max()
            pasado_mins = (ahora - ultima_toma).total_seconds() / 60
            proxima_toma = ultima_toma + pd.Timedelta(minutes=intervalo_min)
            dif_restante = (proxima_toma - ahora).total_seconds() / 60

            # RELLENO DE MÉTRICAS
            col_t1.metric("Intervalo Objetivo", f"{intervalo_min // 60}h {intervalo_min % 60}min")
            col_t2.metric("Llevas sin tomar", f"{int(pasado_mins // 60)}h {int(pasado_mins % 60)}min")

            if dif_restante > 0:
                # Caso: Aún hay que esperar
                h_res, m_res = int(dif_restante // 60), int(dif_restante % 60)
                col_t3.metric("Siguiente dosis en", f"{h_res}h {m_res}min", delta="Espera", delta_color="inverse")

                porcentaje = min(max(pasado_mins / intervalo_min, 0.0), 1.0)
                placeholder_progreso.progress(porcentaje)
                placeholder_mensaje.warning(f"⏳ **Disponible a las:** {proxima_toma.strftime('%H:%M')}")
                st.session_state['abrir_registro'] = False
            else:
                # Caso: INTERVALO CUMPLIDO (Calculamos horas y minutos extra)
                extra_mins_total = abs(dif_restante)
                h_ext, m_ext = int(extra_mins_total // 60), int(extra_mins_total % 60)

                # Mostramos el delta con formato +Xh Ymin
                col_t3.metric("Siguiente dosis", "¡LISTO!", delta=f"+{h_ext}h {m_ext}min", delta_color="normal")

                placeholder_progreso.progress(1.0)
                placeholder_mensaje.success(f"✅ **Intervalo cumplido.** Llevas {h_ext}h {m_ext}min de margen.")
                st.session_state['abrir_registro'] = True

        # --- SECCIÓN 3: REGISTRO (AUTO-OPEN) ---
        with st.expander("➕ REGISTRAR NUEVA TOMA", expanded=st.session_state.get('abrir_registro', False)):
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                cant_toma = st.number_input("Cantidad (ml):", 0.1, 10.0, dosis, 0.05, key="reg_cant")
            with col_r2:
                fecha_sel = st.date_input("Fecha:", ahora.date(), key="reg_fecha")
            with col_r3:
                hora_sel = st.time_input("Hora:", ahora.time(), key="reg_hora")

            if st.button("🚀 ENVIAR A GOOGLE SHEETS", use_container_width=True):
                enviar_toma_api(fecha_sel.strftime('%d/%m/%Y'), hora_sel.strftime('%H:%M:%S'), cant_toma)

        # --- SECCIÓN 4: HISTÓRICOS ---
        st.markdown("---")
        historico_consumo24h()
        mediasConsumos()

    with tab2:
        st.subheader("🧬 Calibración Metabólica")
        cp1, cp2 = st.columns(2)
        with cp1: hl = st.slider("Vida media (h)", 0.5, 4.0, 0.75)
        with cp2: ka = st.slider("Absorción (ka)", 0.5, 5.0, 3.0)

        tabla_final['ghb_active'] = calcularConcentracionDinamica(ka, hl)
        metricas()
        graficas()
    with tab3:
        st.subheader("📜 Historial Detallado de Tomas")

        if not tabla_excel.empty:
            # 1. Preparar los datos
            df_hist = tabla_excel.copy()

            # Ordenamos cronológicamente para calcular la diferencia correctamente
            df_hist = df_hist.sort_values('timestamp', ascending=True)
            df_hist['diff'] = df_hist['timestamp'].diff()


            # Función para convertir el tiempo a formato legible
            def formatear_delta(x):
                if pd.isnull(x): return "---"
                total_segundos = int(x.total_seconds())
                horas = total_segundos // 3600
                minutos = (total_segundos % 3600) // 60
                return f"{horas}h {minutos}min"


            df_hist['Intervalo Real'] = df_hist['diff'].apply(formatear_delta)

            # 2. Preparar tabla para visualización (más reciente primero)
            df_display = df_hist.sort_values('timestamp', ascending=False).copy()
            df_display['Fecha'] = df_display['timestamp'].dt.strftime('%d/%m/%Y')
            df_display['Hora'] = df_display['timestamp'].dt.strftime('%H:%M')
            df_display['Cantidad'] = df_display['ml'].apply(lambda x: f"{x:.2f} ml")

            df_final = df_display[['Fecha', 'Hora', 'Cantidad', 'Intervalo Real']]

            st.dataframe(df_final, use_container_width=True, hide_index=True)

            # 3. Métricas de Logros
            st.markdown("---")
            col_h1, col_h2 = st.columns(2)
            df_valid_diffs = df_hist.dropna(subset=['diff'])

            if not df_valid_diffs.empty:
                media_int_total = df_valid_diffs['diff'].mean()
                max_int = df_valid_diffs['diff'].max()
                col_h1.metric("Intervalo Medio Real", formatear_delta(media_int_total))
                col_h2.metric("Intervalo Máximo (Récord)", formatear_delta(max_int))

            # 4. FUNCIÓN PARA BORRAR ÚLTIMA TOMA
            st.markdown("---")
            with st.expander("⚠️ ZONA DE PELIGRO", expanded=False):
                st.write("¿La última toma es un error?")
                if st.button("🗑️ BORRAR ÚLTIMA TOMA"):
                    eliminar_ultima_toma()
        else:
            st.info("Aún no hay tomas registradas en el historial.")
except Exception as e:
    st.error(f"Error crítico: {e}")