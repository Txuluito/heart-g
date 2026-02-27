import logging

import streamlit as st
import pandas as pd
import os.path
import time
import requests
import json

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


URL_WEB_APP = "https://script.google.com/macros/s/AKfycbwUNNchR4XdVwAqkwlfRQ17GjrV3WPqx6bNlPiSRwt31FDk_USG2HAsep06JTLa4X_Q/exec"
def get_excel_data():
    # Usamos el ID de tu hoja que ya tenías
    SHEET_ID = "18KYPnVSOQF6I2Lm5P1j5nFx1y1RXSmfMWf9jBR2WJ-Q"
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&cache_bust={int(time.time())}"

    df = pd.read_csv(url)
    df.columns = df.columns.str.strip().str.lower()

    if 'ml' in df.columns:
        df['ml'] = df['ml'].astype(str).str.replace(',', '.').pipe(pd.to_numeric, errors='coerce').fillna(0)

    df['timestamp'] = pd.to_datetime(df['fecha'] + ' ' + df['hora'], format='mixed', dayfirst=True)
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('Europe/Madrid')

    return df.sort_values('timestamp', ascending=False)
def enviar_toma_api( fecha_str, hora_str, cantidad):
    payload = {"fecha": fecha_str, "hora": hora_str, "ml": cantidad}
    return requests.post(URL_WEB_APP, json=payload)
def get_plan_history_data():
    """Obtiene el historial del plan desde Google Sheets."""
    try:
        params = {"action": "get_plan_history"}
        response = requests.get(URL_WEB_APP, params=params, timeout=10)
        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get('status') == 'success':
                    data = json_response.get('data', [])
                    return pd.DataFrame(data) if data else pd.DataFrame()
            except ValueError:
                print(f"Error decodificando respuesta JSON de Sheets: {response.text[:100]}")
    except Exception as e:
        print(f"Error cargando historial plan: {e}")
    return pd.DataFrame()
def save_plan_history_data(df):
    """Guarda el historial del plan en Google Sheets."""
    try:
        data_list = df.to_dict(orient='records')
        payload = {"action": "save_plan_history", "data": data_list}
        requests.post(URL_WEB_APP, json=payload, timeout=15)
    except Exception as e:
        print(f"Error guardando historial plan: {e}")
def get_config():
    """Obtiene la configuración desde la hoja 'Config'."""
    logging.warning("Cargando configuracion")
    try:
        params = {"action": "get_config"}
        response = requests.get(URL_WEB_APP, params=params, timeout=15)
        if response.status_code == 200:
            try:
                json_response = response.json()
                if json_response.get('status') == 'success':
                    config =json_response.get('data', {})
                    print(f"{config}")
                    return config
            except ValueError:
                print(f"Error decodificando config JSON de Sheets: {response.text[:200]}")
    except Exception as e:
        print(f"Error cargando config remota: {e}")
    return {}

def save_config(data):
    """Guarda/Actualiza la configuración en la hoja 'Config'."""
    try:
        payload = {"action": "save_config", "data": data}
        requests.post(URL_WEB_APP, json=payload, timeout=15)
        return True
    except Exception as e:
        print(f"Error guardando config remota: {e}")
        return False
def eliminar_ultima_toma():
    try:
        # Enviamos una petición POST con un parámetro especial para indicar borrado
        # OJO: Tu Google Apps Script debe estar preparado para recibir esto.
        # Si no lo está, tendrás que modificar el script.gs también.
        # Asumiremos que mandamos action="delete_last"
        payload = {"action": "delete_last"}
        response = requests.post(URL_WEB_APP, json=payload)
        
        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error al eliminar: {e}")
        return False
def get_google_fit_data():
    creds = None
    scopes = ['https://www.googleapis.com/auth/fitness.heart_rate.read']

    # 1. INTENTAR CARGAR DESDE SECRETS (Sin que rompa la app si no existen)
    try:
        if "google_fit_token" in st.secrets:
            token_info = json.loads(st.secrets["google_fit_token"])
            creds = Credentials.from_authorized_user_info(token_info, scopes)
    except Exception:
        # 2. SI NO HAY CREDS, BUSCAR ARCHIVO LOCAL (Modo PC)
        if not creds and os.path.exists('local/token.json'):
            creds = Credentials.from_authorized_user_file('local/token.json', scopes)

    # 3. Si el token expiró, refrescarlo
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Opcional: imprimir el nuevo token en consola para actualizar el Secret si fuera necesario

    # 4. Si no hay credenciales válidas, iniciar flujo (Solo local)
    if not creds or not creds.valid:
        if os.path.exists('local/credentials.json'):
            flow = InstalledAppFlow.from_client_secrets_file('local/credentials.json',scopes)
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
        df = df.resample('1min').mean().interpolate()
    return df