# onboarding.py
import streamlit as st
from supabase import create_client, Client

# =========================
# 🔗 Conexión a Supabase
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]  # Usa service_role o anon según config
supabase: Client = create_client(url, key)

# =========================
# ⚙️ Configuración UI
# =========================
st.set_page_config(page_title="Crear contraseña", page_icon="🔑")
st.title("🔑 Bienvenido al Sistema Hogwarts")
st.write("Crea tu nueva contraseña para acceder al sistema.")

# =========================
# 📌 Script para mover el hash (#) a query params
# =========================
st.markdown(
    """
    <script>
    const hash = window.location.hash.substring(1);
    if (hash) {
        const params = new URLSearchParams(hash);
        const access_token = params.get("access_token");
        const refresh_token = params.get("refresh_token");
        if (access_token) {
            const query = new URLSearchParams({
                access_token: access_token,
                refresh_token: refresh_token
            });
            const baseUrl = window.location.href.split("#")[0];
            // 👇 Forzar recarga con query params en vez de hash
            window.location.replace(baseUrl + "?" + query.toString());
        }
    }
    </script>
    """,
    unsafe_allow_html=True
)

# =========================
# 📌 Leer tokens desde query_params
# =========================
qp = st.query_params
access_token = qp.get("access_token", [None])[0] if isinstance(qp.get("access_token"), list) else qp.get("access_token")
refresh_token = qp.get("refresh_token", [None])[0] if isinstance(qp.get("refresh_token"), list) else qp.get("refresh_token")

if not access_token:
    st.info("⏳ Procesando invitación... redirigiendo.")
    st.stop()

# =========================
# 📌 Formulario para nueva contraseña
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
                # 👇 Inicia sesión con el token del link de invitación
                supabase.auth.set_session({
                    "access_token": access_token,
                    "refresh_token": refresh_token
                })
                # 👇 Actualiza la contraseña del usuario
                supabase.auth.update_user({"password": nueva_password})

                st.success("✅ Contraseña creada correctamente.")
                st.markdown("[🔑 Ir al login](https://hogwartznewteacher.streamlit.app/)")

                # 👇 Limpieza de tokens de la URL por seguridad
                st.markdown(
                    """
                    <script>
                    if (window.location.search.includes("access_token")) {
                        window.history.replaceState({}, document.title, window.location.pathname);
                    }
                    </script>
                    """,
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.error(f"❌ Error al actualizar contraseña: {e}")
