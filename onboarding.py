import streamlit as st
from sqlalchemy import create_engine, text
from supabase import create_client, Client

st.set_page_config(page_title="Resetear acceso", page_icon="🔑")

# =========================
# 🔗 Conexión DB
# =========================
DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}", pool_pre_ping=True
)

# 🔑 Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("🔑 Resetear acceso del profesor")

with st.form("reset_form"):
    cedula = st.text_input("Ingrese su cédula").strip()
    submit = st.form_submit_button("Resetear acceso")

    if submit:
        if not cedula:
            st.error("⚠️ Debes ingresar la cédula.")
        else:
            try:
                # Buscar profesor en DB
                with engine.begin() as conn:
                    prof = conn.execute(
                        text("SELECT id, email FROM profesores WHERE cedula = :ced"),
                        {"ced": cedula}
                    ).fetchone()

                if not prof:
                    st.error("❌ No existe un profesor con esa cédula.")
                else:
                    # La nueva "email" será igual a la cédula
                    nuevo_email = f"{cedula}@hogwartz.edu"  # 👈 aquí defines el dominio institucional
                    nueva_pass = cedula  # clave = cedula

                    # Actualizar en Supabase (usuario + password)
                    supabase.auth.admin.update_user_by_email(
                        prof.email,
                        {"email": nuevo_email, "password": nueva_pass}
                    )

                    # Actualizar en tu tabla profesores
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE profesores SET email=:email WHERE id=:id"),
                            {"email": nuevo_email, "id": prof.id}
                        )

                    st.success(f"✅ Acceso reseteado. Ahora puede entrar con:\n- **Usuario:** {nuevo_email}\n- **Contraseña:** {cedula}")
                    st.markdown("[Ir al login](https://horbwartz-zheasdtrshxosf7izr9fv9.streamlit.app/)")
            except Exception as e:
                st.error(f"❌ Error: {e}")
