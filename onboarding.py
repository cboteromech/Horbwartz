import streamlit as st
from supabase import create_client, Client
import urllib.parse

# =========================
# 🔗 Conexión a Supabase
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]  # service_role
supabase: Client = create_client(url, key)

st.set_page_config(page_title="Crear contraseña", page_icon="🔑")
st.title("🔑 Bienvenido al Sistema Hogwarts")
st.write("Crea tu nueva contraseña para acceder al sistema.")

# =========================
# 📌 Capturar access_token del fragmento #
# =========================
# Usamos un pequeño truco JS para leer window.location.hash
token_container = st.empty()
st.markdown(
    """
    <script>
    const hash = window.location.hash.substring(1); // quita el #
    const params = new URLSearchParams(hash);
    const access_token = params.get("access_token");
    const refresh_token = params.get("refresh_token");
    if (access_token) {
        const query = new URLSearchParams({
            access_token: access_token,
            refresh_token: refresh_token
        });
        window.location.replace(window.location.pathname + "?" + query.toString());
    }
    </script>
    """,
    unsafe_allow_html=True
)

# =========================
# 📌 Ahora sí leemos de query_params
# =========================
query_params = st.query_params
access_token = query_params.get("access_token", [None])[0] if query_params else None
refresh_token = query_params.get("refresh_token", [None])[0] if query_params else None

if not access_token:
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
                # 👇 Establecemos la sesión con los tokens del link
                supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
                supabase.auth.update_user({"password": nueva_password})
                st.success("✅ Contraseña creada correctamente. Ya puedes iniciar sesión en la página principal.")
                st.info("👉 Vuelve al inicio y usa tu correo + nueva contraseña.")
            except Exception as e:
                st.error(f"❌ Error al actualizar contraseña: {e}")
