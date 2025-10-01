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
# UI
# =========================
st.title("🔑 Restablecer tu contraseña")

with st.form("reset_password"):
    email = st.text_input("📧 Correo institucional")
    nueva_pass = st.text_input("Nueva contraseña", type="password")
    confirmar_pass = st.text_input("Confirmar contraseña", type="password")
    submit = st.form_submit_button("Actualizar")

    if submit:
        if not email or not nueva_pass or not confirmar_pass:
            st.error("⚠️ Completa todos los campos.")
        elif nueva_pass != confirmar_pass:
            st.error("⚠️ Las contraseñas no coinciden.")
        else:
            try:
                # validar que el correo exista en la tabla profesores
                with engine.connect() as conn:
                    prof = conn.execute(
                        text("SELECT id FROM profesores WHERE email = :email"),
                        {"email": email}
                    ).fetchone()

                if not prof:
                    st.error("❌ El correo no está registrado en el sistema.")
                else:
                    # actualizar clave en supabase
                    supabase.auth.admin.update_user_by_email(
                        email, {"password": nueva_pass}
                    )
                    st.success("✅ Contraseña actualizada correctamente.")
                    st.markdown("[Ir al sistema de puntos](https://horbwartz-zheasdtrshxosf7izr9fv9.streamlit.app/)")
            except Exception as e:
                st.error(f"❌ Error: {e}")
