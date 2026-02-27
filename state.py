import streamlit as st
import database
import logging

def load_config():
    """
    Carga la configuración en st.session_state si aún no ha sido cargada.
    Esta función es segura para ser llamada múltiples veces.
    """
    if 'config' not in st.session_state:
        logging.info("STATE: No se encontró config en session_state. Cargando desde la base de datos...")
        st.session_state.config = database.get_config()
        logging.info("STATE: Configuración cargada y guardada en session_state.")
    # No es necesario devolver nada, ya que el estado se gestiona en st.session_state

def invalidate_config():
    """
    Borra la configuración de st.session_state para forzar una recarga.
    Debe llamarse después de cualquier operación que modifique la config.
    """
    if 'config' in st.session_state:
        del st.session_state.config
        logging.info("STATE: Configuración invalidada (borrada) de session_state.")
