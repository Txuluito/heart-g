import streamlit as st
import pandas as pd

def minDesdeUltimaToma():
    df_excel = st.session_state.df_excel.copy()
    if not df_excel.empty and df_excel.iloc[0]['hora']:
        fecha_hora_ultima_toma = pd.to_datetime(
            df_excel.iloc[0]['fecha'] + ' ' + df_excel.iloc[0]['hora'],
            format='%d/%m/%Y %H:%M:%S').tz_localize('Europe/Madrid')
        return (pd.Timestamp.now(tz='Europe/Madrid')-fecha_hora_ultima_toma).total_seconds() / 60
    return 0