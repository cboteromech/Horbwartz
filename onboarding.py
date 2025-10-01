# onboarding.py
import streamlit as st
from supabase import create_client, Client

# =========================
# 🔗 Conexión a Supabase
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]  # ⚠️ Debe ser service_role para admin
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Crear contraseña", page_icon="🔑")

st.title("🔑 Bienvenido al Sistema Hogwarts")
st.write("Crea tu nueva contraseña para acceder al sistema.")

# =========================
# 📌 Captura del token de invitación
# =========================
query_params = st.query_params
token = query_params.get("token", [None])[0] if query_params else None

if not token:
    st.error("❌ No se encontró un token de invitación. Verifica el link de tu correo.")
    st.stop()

# =========================
# 📌 Formulario de nueva contraseña
# =========================
with st.form("crear_contrasena"):
    nueva_password = st.text_input("Nueva contraseña", type="password")
    confirmar_password = st.text_input("Confirmar contraseña", type="password")
    submit = st.form_submit_button("💾 Guardar")

    if submit:
        if not nueva_password or not confirmar_password:
            st.warning("⚠️ Debes llenar ambos campos.")
        elif nueva_password != confirmar_password:
            st.error("❌ Las contraseñas no coinciden.")
        else:
            try:
                # 👇 Usamos el token de la invitación para autenticar
                supabase.auth.set_session(access_token=token, refresh_token=token)
                supabase.auth.update_user({"password": nueva_password})
                st.success("✅ Contraseña creada correctamente. Ya puedes iniciar sesión desde la página principal.")
                st.info("👉 Vuelve a la página de inicio y usa tu correo + nueva contraseña para entrar.")
            except Exception as e:
                st.error(f"❌ Error al actualizar contraseña: {e}")
