import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from supabase import create_client, Client

# =========================
# ⚙️ Configuración general
# =========================
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

# =========================
# 🔗 Conexión a Supabase Postgres
# =========================
DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_pre_ping=True
)

# =========================
# 🔑 Autenticación Supabase
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# =========================
# 📌 Login
# =========================
if "user" not in st.session_state:
    st.sidebar.title("Acceso profesores")
    email = st.sidebar.text_input("Correo", key="email")
    password = st.sidebar.text_input("Contraseña", type="password", key="password")

    if st.sidebar.button("Iniciar sesión"):
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state["user"] = user.user
            st.success(f"✅ Bienvenido {email}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")
    st.stop()
else:
    st.sidebar.write(f"Conectado como {st.session_state['user'].email}")
    if st.sidebar.button("Cerrar sesión"):
        supabase.auth.sign_out()
        del st.session_state["user"]
        st.rerun()

# =========================
# 📌 Obtener rol desde la tabla profesores
# =========================
def get_profesor(email):
    with engine.connect() as conn:
        query = text("SELECT id, rol, fraternidad_id, colegio_id FROM profesores WHERE email=:email")
        result = conn.execute(query, {"email": email}).fetchone()
        return result

rol, fraternidad_id, colegio_id, profesor_id = None, None, None, None
if "user" in st.session_state:
    profesor_data = get_profesor(st.session_state["user"].email)
    if profesor_data:
        profesor_id, rol, fraternidad_id, colegio_id = profesor_data
    else:
        st.error("❌ No tienes un rol asignado en este colegio")
        st.stop()

# =========================
# 📂 Funciones DB
# =========================
@st.cache_data(ttl=60)
def leer_resumen_estudiantes() -> pd.DataFrame:
    query = "SELECT * FROM resumen_puntos_estudiantes;"
    df = pd.read_sql(query, engine)
    df.columns = df.columns.str.lower()
    return df

def insertar_estudiante(codigo, nombre, apellido, fraternidad):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO estudiantes (codigo, nombre, apellidos, fraternidad_id, colegio_id)
            VALUES (:codigo, :nombre, :apellido, :frat, :colegio)
        """), {"codigo": codigo, "nombre": nombre, "apellido": apellido,
               "frat": fraternidad_id, "colegio": colegio_id})
        st.cache_data.clear()

def actualizar_estudiante(codigo, campo, valor):
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE estudiantes SET "{campo}" = :valor WHERE codigo = :codigo'),
                     {"valor": valor, "codigo": codigo})
        st.cache_data.clear()

def actualizar_puntos(estudiante_id, valor_nombre, delta, profesor_id=None):
    with engine.begin() as conn:
        # buscamos el valor_id a partir del nombre del valor
        valor_q = conn.execute(text("SELECT id FROM valores WHERE nombre = :valor AND colegio_id = :colegio"),
                               {"valor": valor_nombre, "colegio": colegio_id}).fetchone()
        if not valor_q:
            st.error("⚠️ El valor no existe en este colegio.")
            return
        valor_id = valor_q[0]

        conn.execute(text("""
            INSERT INTO puntos (estudiante_id, valor_id, cantidad, profesor_id)
            VALUES (:estudiante_id, :valor_id, :cantidad, :profesor_id)
        """), {
            "estudiante_id": estudiante_id,
            "valor_id": valor_id,
            "cantidad": delta,
            "profesor_id": profesor_id
        })
    st.cache_data.clear()


# =========================
# 🏆 App principal
# =========================
df = leer_resumen_estudiantes()
st.title("🏆 Sistema de Puntos Hogwarts")

# =========================
# 👤 Gestión de estudiantes (solo DIRECTOR)
# =========================
if rol == "director":
    with st.expander("➕ Añadir nuevo estudiante"):
        c1, c2, c3 = st.columns(3)
        with c1: codigo = st.text_input("Código")
        with c2: nombre = st.text_input("Nombre")
        with c3: apellido = st.text_input("Apellidos")

        if st.button("Agregar estudiante"):
            if not codigo or not nombre or not apellido:
                st.error("⚠️ Todos los campos son obligatorios.")
            elif df["codigo"].astype(str).eq(str(codigo).strip()).any():
                st.error("⚠️ Ya existe un estudiante con ese código.")
            else:
                insertar_estudiante(codigo.strip(), nombre.strip(), apellido.strip(), fraternidad_id)
                st.success(f"✅ Estudiante {nombre} {apellido} añadido.")
                st.rerun()

# =======================================================
# 🔎 Buscar y asignar puntos (PROFESORES y DIRECTORES)
# =======================================================
st.header("🔎 Buscar estudiante")
opciones = df.apply(lambda r: f"{r['nombre']} {r['apellidos']} ({r['codigo']})", axis=1).tolist()
seleccion = st.selectbox("Selecciona estudiante:", [""] + opciones)

if seleccion != "":
    codigo = seleccion.split("(")[-1].replace(")", "").strip()
    alumno = df[df["codigo"] == codigo]

    if alumno.empty:
        st.error("No encontrado.")
    else:
        r = alumno.iloc[0]
        st.success(f"👤 {r['nombre']} {r['apellidos']} | 🏠 Fraternidad: {r['fraternidad']}")

        # ➕ Asignar puntos
        st.subheader("➕ Asignar puntos")
        categoria = st.selectbox("Categoría", df["valor"].unique().tolist())
        delta = st.number_input("Puntos (+/-)", -10, 10, 1)
        if st.button("Actualizar puntos"):
            actualizar_puntos(r["estudiante_id"], categoria, delta, profesor_id)
            st.success(f"{delta:+} puntos añadidos en {categoria}.")
            st.rerun()

        # ✏️ Editar datos (solo DIRECTOR)
        if rol == "director":
            with st.expander("✏️ Editar datos del estudiante"):
                nuevo_nombre = st.text_input("Nombre", r["nombre"], key=f"nombre_{codigo}")
                nuevo_apellido = st.text_input("Apellidos", r["apellidos"], key=f"apellidos_{codigo}")

                if st.button("💾 Guardar cambios"):
                    actualizar_estudiante(codigo, "nombre", nuevo_nombre.strip())
                    actualizar_estudiante(codigo, "apellidos", nuevo_apellido.strip())
                    st.success("✅ Datos actualizados correctamente.")
                    st.rerun()
