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

@st.cache_data(ttl=60)
def leer_historial_puntos(estudiante_id) -> pd.DataFrame:
    query = text("""
        SELECT p.id, v.nombre as valor, p.cantidad, pr.nombre as profesor, p.created_at
        FROM puntos p
        JOIN valores v ON v.id = p.valor_id
        LEFT JOIN profesores pr ON pr.id = p.profesor_id
        WHERE p.estudiante_id = :eid
        ORDER BY p.created_at DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"eid": estudiante_id})
    return df

def actualizar_estudiante_full(estudiante_id, codigo, nombre, apellidos, grado, fraternidad_id):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE estudiantes
            SET codigo=:codigo, nombre=:nombre, apellidos=:apellidos, grado=:grado, fraternidad_id=:frat
            WHERE id=:id
        """), {
            "codigo": codigo,
            "nombre": nombre,
            "apellidos": apellidos,
            "grado": grado,
            "frat": fraternidad_id,
            "id": estudiante_id
        })
    st.cache_data.clear()

def actualizar_puntos(estudiante_id, valor_nombre, delta, profesor_id=None):
    with engine.begin() as conn:
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

# =======================================================
# 🔎 Buscar estudiante
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
        st.subheader(f"👤 {r['nombre']} {r['apellidos']} | 🎓 {r['grado']} | 🏠 {r['fraternidad']}")

        # =========================
        # Totales del estudiante
        # =========================
        totales = df[df["estudiante_id"] == r["estudiante_id"]].groupby("valor")["puntos"].sum()
        total_general = totales.sum()

        st.markdown(f"### 🧮 Total de puntos: **{total_general}**")

        # Tabla pivote
        tabla = totales.reset_index().pivot_table(values="puntos", index=None, columns="valor", fill_value=0)
        st.dataframe(tabla, use_container_width=True)

        # Gráfico de barras
        fig, ax = plt.subplots(figsize=(6,3))
        totales.plot(kind="bar", ax=ax, color="skyblue")
        ax.set_ylabel("Puntos")
        ax.set_title("Distribución de valores")
        st.pyplot(fig)

        # =========================
        # ➕ Asignar puntos
        # =========================
        st.subheader("➕ Asignar puntos")
        categoria = st.selectbox("Categoría", df["valor"].unique().tolist())
        delta = st.number_input("Puntos (+/-)", -10, 10, 1)
        if st.button("Actualizar puntos"):
            actualizar_puntos(r["estudiante_id"], categoria, delta, profesor_id)
            st.success(f"{delta:+} puntos añadidos en {categoria}.")
            st.rerun()

        # =========================
        # ✏️ Editar datos completos (solo DIRECTOR)
        # =========================
        if rol == "director":
            st.subheader("✏️ Editar datos del estudiante")
            nuevo_codigo = st.text_input("Código", r["codigo"])
            nuevo_nombre = st.text_input("Nombre", r["nombre"])
            nuevo_apellido = st.text_input("Apellidos", r["apellidos"])
            nuevo_grado = st.text_input("Grado", r["grado"])
            nueva_frat = st.text_input("Fraternidad ID", str(r["fraternidad"]))  # puede mejorarse con selectbox

            if st.button("💾 Guardar cambios en estudiante"):
                actualizar_estudiante_full(
                    r["estudiante_id"], 
                    nuevo_codigo.strip(),
                    nuevo_nombre.strip(),
                    nuevo_apellido.strip(),
                    nuevo_grado.strip(),
                    nueva_frat.strip()
                )
                st.success("✅ Datos del estudiante actualizados.")
                st.rerun()

        # =========================
        # 📋 Historial de puntos
        # =========================
        st.subheader("📋 Historial de puntos")
        historial = leer_historial_puntos(r["estudiante_id"])
        st.dataframe(historial, use_container_width=True)
