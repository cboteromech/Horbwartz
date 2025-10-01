import streamlit as st
from sqlalchemy import create_engine, text
from supabase import create_client, Client

# =========================
# Configuración
# =========================
st.set_page_config(page_title="Resetear Contraseña", page_icon="🔑")

DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}", pool_pre_ping=True
)

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# =========================
# Leer email desde la URL
# =========================
params = st.query_params
email = params.get("email", [None])[0] if isinstance(params.get("email"), list) else params.get("email")

st.title("🔑 Restablecer tu contraseña")

if not email:
    st.error("❌ El enlace no contiene un correo válido.")
    st.stop()

st.info(f"📧 Restableciendo contraseña para: **{email}**")

# =========================
# Formulario
# =========================
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
                # Validar en BD
                with engine.connect() as conn:
                    prof = conn.execute(
                        text("SELECT id FROM profesores WHERE email = :email"),
                        {"email": email}
                    ).fetchone()

                if not prof:
                    st.error("❌ El correo no está registrado en el sistema.")
                else:
                    # Actualizar clave en Supabase
                    supabase.auth.admin.update_user_by_email(
                        email, {"password": nueva_pass}
                    )
                    st.success("✅ Contraseña actualizada correctamente.")
                    st.markdown("[Ir al sistema de puntos](https://horbwartz-zheasdtrshxosf7izr9fv9.streamlit.app/)")
            except Exception as e:
                st.error(f"❌ Error: {e}")
