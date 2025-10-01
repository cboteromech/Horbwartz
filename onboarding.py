import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Resetear contraseña", page_icon="🔑")

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("🔑 Restablecer tu contraseña")

# Leer tokens directamente desde la URL
params = st.query_params
access_token = params.get("access_token", None)
refresh_token = params.get("refresh_token", None)

if not access_token:
    st.info("⏳ Procesando invitación... El enlace aún no contiene credenciales.")
    st.stop()

# Ya validado: si hay tokens, es que el correo fue correcto
with st.form("reset_password"):
    nueva_pass = st.text_input("Nueva contraseña", type="password")
    confirmar_pass = st.text_input("Confirmar contraseña", type="password")
    submit = st.form_submit_button("Actualizar")

    if submit:
        if not nueva_pass or nueva_pass != confirmar_pass:
            st.error("⚠️ Las contraseñas no coinciden.")
        else:
            try:
            # Crear sesión usando tokens del Magic Link
            supabase.auth.set_session({
                "access_token": access_token,
                "refresh_token": refresh_token
            })

            # Actualizar contraseña
            supabase.auth.update_user({"password": nueva_pass})

            st.success("✅ Contraseña cambiada correctamente.")
            st.markdown("[🔑 Ir al login](https://resethogwartz.streamlit.app/)")
        except Exception as e:
            st.error(f"❌ Error: {e}")

