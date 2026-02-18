import streamlit as st
import pandas as pd
import logic

def render(df, resumen, media_3d, dosis_habitual):
    st.subheader("💰 Presupuesto de ML (Saldo Acumulado)")
    ahora = pd.Timestamp.now(tz='Europe/Madrid')

    # Cargar configuración
    config = logic.load_config()
    saved_ritmo = config.get("ritmo", 1.0)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.metric("Consumo Base", f"{media_3d:.2f} ml/día")
    with col_p2:
        ritmo = st.number_input("Reducción diaria (ml/día)", 0.1, 5.0, float(saved_ritmo), step=0.1)
        if ritmo != saved_ritmo:
            logic.save_config({"ritmo": ritmo})

    tasa_h = (media_3d - ritmo) / 24

    inicio = df['timestamp'].min()
    ingresos = ((ahora - inicio).total_seconds() / 3600) * tasa_h
    gastos = df['ml'].sum()
    saldo = ingresos - gastos

    color = "#2ecc71" if saldo >= 0 else "#e74c3c"
    st.markdown(f"""<div style="border:3px solid {color}; padding:20px; border-radius:15px; text-align:center;">
                <h1 style="color:{color};">{saldo:.3f} ml</h1><p>SALDO DISPONIBLE</p></div>""", unsafe_allow_html=True)

    dosis_t = st.number_input("Dosis deseada (ml)", 0.1, 10.0, float(dosis_habitual))
    if saldo < dosis_t:
        espera_h = (dosis_t - saldo) / tasa_h
        st.warning(f"⏳ Espera: {int(espera_h)}h {int((espera_h % 1) * 60)}min")