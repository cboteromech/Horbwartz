import streamlit as st
from supabase import create_client, Client
import streamlit.components.v1 as components

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
# 📌 Script para extraer tokens del hash y guardarlos en localStorage
# =========================
components.html(
    """
    <script>
    const hash = window.location.hash.substring(1);
    if (hash) {
        const params = new URLSearchParams(hash);
        const access_token = params.get("access_token");
        const refresh_token = params.get("refresh_token");
        if (access_token && refresh_token) {
            localStorage.setItem("hogwarts_access_token", access_token);
            localStorage.setItem("hogwarts_refresh_token", refresh_token);
            // limpiar hash de la URL
            window.location.replace(window.location.pathname);
        }
    }
    </script>
    """,
    height=0,
)

# =========================
# 📌 Recuperamos tokens desde query_params o localStorage
# =========================
access_token = st.query_params.get("access_token")
refresh_token = st.query_params.get("refresh_token")

if not access_token:
    # intentar leer desde localStorage con otro truco
    token_holder = st.empty()
    components.html(
        """
        <script>
        const access_token = localStorage.getItem("hogwarts_access_token");
        const refresh_token = localStorage.getItem("hogwarts_refresh_token");
        if (access_token && refresh_token) {
            const query = new URLSearchParams({
                access_token: access_token,
                refresh_token: refresh_token
            });
            window.location.replace(window.location.pathname + "?" + query.toString());
        }
        </script>
        """,
        height=0,
    )
    st.info("⏳ Procesando invitación...")
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
                supabase.auth.set_session(
                    {"access_token": access_token, "refresh_token": refresh_token}
                )
                supabase.auth.update_user({"password": nueva_password})
                st.success("✅ Contraseña creada correctamente. Ya puedes iniciar sesión en la página principal.")
                st.markdown("[🔑 Ir al login](https://hogwartznewteacher.streamlit.app/)")
            except Exception as e:
                st.error(f"❌ Error al actualizar contraseña: {e}")
