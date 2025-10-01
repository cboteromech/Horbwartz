import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Resetear contraseña", page_icon="🔑")

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("🔑 Restablecer tu contraseña")

# Script para mover tokens del hash (#) a query params
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
            window.location.href = baseUrl + "?" + query.toString();
        }
    }
    </script>
    """,
    unsafe_allow_html=True
)

# Leer los tokens desde query params
params = st.query_params
access_token = params.get("access_token", None)
refresh_token = params.get("refresh_token", None)

if not access_token:
    st.info("⏳ Procesando invitación... espera un momento.")
    st.stop()

# Mostrar formulario para nueva contraseña
with st.form("reset_password"):
    nueva_pass = st.text_input("Nueva contraseña", type="password")
    confirmar_pass = st.text_input("Confirmar contraseña", type="password")
    submit = st.form_submit_button("Actualizar")

    if submit:
        if not nueva_pass or not confirmar_pass:
            st.error("⚠️ Completa ambos campos.")
        elif nueva_pass != confirmar_pass:
            st.error("⚠️ Las contraseñas no coinciden.")
        else:
            try:
                # Establecer sesión con Supabase
                supabase.auth.set_session({
                    "access_token": access_token,
                    "refresh_token": refresh_token
                })

                # Actualizar contraseña
                supabase.auth.update_user({"password": nueva_pass})

                st.success("✅ Contraseña cambiada correctamente.")
                # Después de reset, puedes redirigir al login de la app principal
                st.markdown("[🔑 Ir al sistema de puntos](https://horbwartz-zheasdtrshxosf7izr9fv9.streamlit.app/)")
            except Exception as e:
                st.error(f"❌ Error: {e}")
