# resethogwartz/app.py
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Resetear contraseña", page_icon="🔑")

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]  # usa ANON KEY aquí
supabase: Client = create_client(url, key)

st.title("🔑 Restablecer tu contraseña")

# ===============================
# 1) Verificación OTP
# ===============================
if "otp_ok" not in st.session_state:
    st.session_state.otp_ok = False
if "email" not in st.session_state:
    st.session_state.email = ""

if not st.session_state.otp_ok:
    st.subheader("1) Verifica tu código")
    with st.form("otp"):
        email = st.text_input("Correo", value=st.session_state.email)
        code = st.text_input("Código de 6 dígitos", max_chars=6)
        submit = st.form_submit_button("Verificar")

        if submit:
            try:
                supabase.auth.verify_otp({
                    "email": email,
                    "token": code,
                    "type": "email"
                })
                st.session_state.otp_ok = True
                st.session_state.email = email
                st.success("✅ Código verificado. Ahora cambia tu contraseña.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error verificando: {e}")

# ===============================
# 2) Nueva contraseña
# ===============================
else:
    st.subheader("2) Nueva contraseña")
    with st.form("newpass"):
        new = st.text_input("Nueva contraseña", type="password")
        confirm = st.text_input("Confirmar contraseña", type="password")
        submit = st.form_submit_button("Actualizar")

        if submit:
            if new != confirm:
                st.error("⚠️ Las contraseñas no coinciden.")
            else:
                try:
                    supabase.auth.update_user({"password": new})
                    st.success("✅ Contraseña cambiada correctamente.")
                    st.markdown("[Ir al sistema de puntos](https://horbwartz-zheasdtrshxosf7izr9fv9.streamlit.app/)")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
