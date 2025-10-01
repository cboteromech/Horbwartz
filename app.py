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
# 🔑 Autenticación Supabase (debe ir ANTES del login)
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# =========================
# 📌 Obtener rol desde la tabla profesores
# =========================
def get_profesor(email):
    with engine.connect() as conn:
        query = text("""
            SELECT 
                id, 
                rol, 
                fraternidad_id, 
                colegio_id, 
                (nombres || ' ' || apellidos) as nombre_completo,
                asignatura, 
                area, 
                grados
            FROM profesores
            WHERE email = :email
        """)
        result = conn.execute(query, {"email": email}).fetchone()
        return result


rol, fraternidad_id, colegio_id, profesor_id = None, None, None, None
nombre_completo, asignatura, area, grados = None, None, None, None

if "user" in st.session_state:
    profesor_data = get_profesor(st.session_state["user"].email)
    if profesor_data:
        profesor_id, rol, fraternidad_id, colegio_id, nombre_completo, asignatura, area, grados = profesor_data
    else:
        st.error("❌ No tienes un rol asignado en este colegio")
        st.stop()



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

    # 👉 Aquí obtenemos datos del profesor ANTES de mostrarlos
    profesor_data = get_profesor(st.session_state["user"].email)
    if profesor_data:
        profesor_id, rol, fraternidad_id, colegio_id, nombre_completo, asignatura, area, grados = profesor_data

        st.sidebar.markdown("### 👨‍🏫 Perfil del profesor")
        st.sidebar.write(f"**Nombre completo:** {nombre_completo}")
        st.sidebar.write(f"**Rol:** {rol}")
        st.sidebar.write(f"**Asignatura:** {asignatura}")
        st.sidebar.write(f"**Área:** {area}")
        st.sidebar.write(f"**Grados:** {grados}")
    else:
        st.error("❌ No tienes un rol asignado en este colegio")
        st.stop()

    if st.sidebar.button("Cerrar sesión"):
        supabase.auth.sign_out()
        del st.session_state["user"]
        st.rerun()



# =========================
# 📂 Funciones DB
# =========================
@st.cache_data(ttl=60)
def leer_resumen_estudiantes(colegio_id) -> pd.DataFrame:
    query = text("SELECT * FROM resumen_puntos_estudiantes WHERE colegio_id = :cid")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"cid": colegio_id})
    df.columns = df.columns.str.lower()
    return df

@st.cache_data(ttl=60)
def leer_historial_puntos(estudiante_id, colegio_id) -> pd.DataFrame:
    query = text("""
        SELECT 
            p.id, 
            v.nombre as valor, 
            p.cantidad, 
            (pr.nombres || ' ' || pr.apellidos) as profesor, 
            p.created_at
        FROM puntos p
        JOIN valores v ON v.id = p.valor_id
        LEFT JOIN profesores pr ON pr.id = p.profesor_id
        JOIN estudiantes e ON e.id = p.estudiante_id
        WHERE p.estudiante_id = :eid AND e.colegio_id = :cid
        ORDER BY p.created_at DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"eid": estudiante_id, "cid": colegio_id})
    return df


@st.cache_data(ttl=60)
def leer_valores(colegio_id) -> pd.DataFrame:
    query = text("SELECT id, nombre FROM valores WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"cid": colegio_id})
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

@st.cache_data(ttl=60)
def leer_estadisticas_fraternidades(colegio_id):
    query = text("""
        SELECT f.nombre as fraternidad, SUM(COALESCE(p.cantidad,0)) as total_puntos
        FROM estudiantes e
        JOIN fraternidades f ON e.fraternidad_id = f.id
        LEFT JOIN puntos p ON e.id = p.estudiante_id
        WHERE e.colegio_id = :cid
        GROUP BY f.nombre
        ORDER BY total_puntos DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"cid": colegio_id})
    return df


# =========================
# 🏆 App principal
# =========================
df = leer_resumen_estudiantes(colegio_id)

st.title("🏆 Sistema de Puntos Hogwarts")

st.header("📊 Estadísticas generales del colegio")

stats = leer_estadisticas_fraternidades(colegio_id)

if not stats.empty:
    st.dataframe(stats, use_container_width=True)

    fig, ax = plt.subplots(figsize=(6,3))
    stats.plot(kind="bar", x="fraternidad", y="total_puntos", ax=ax, color="orange", legend=False)
    ax.set_ylabel("Puntos")
    ax.set_title("🏆 Comparativa de fraternidades")
    st.pyplot(fig)
else:
    st.info("ℹ️ No hay puntos registrados todavía.")


# =======================================================
# 🔎 Buscar estudiante
# =======================================================
st.header("🔎 Buscar estudiante")
opciones = (
    df[["estudiante_id", "codigo", "nombre", "apellidos"]]
    .drop_duplicates()
    .apply(lambda r: f"{r['nombre']} {r['apellidos']} ({r['codigo']})", axis=1)
    .tolist()
)
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
        valores_df = leer_valores(colegio_id)  # todos los valores del colegio

        totales = (
            valores_df.merge(
                df[df["estudiante_id"] == r["estudiante_id"]],
                how="left",
                left_on="nombre",
                right_on="valor"
            )[["nombre", "puntos"]]
            .fillna(0)
            .set_index("nombre")["puntos"]
        )

        total_general = totales.sum()

        st.markdown(f"### 🧮 Total de puntos: **{total_general}**")

        # Tabla pivote
        tabla = totales.reset_index().pivot_table(values="puntos", index=None, columns="valor", fill_value=0)
        st.dataframe(tabla, use_container_width=True)

        # Gráfico de barras
        if not totales.empty:
            fig, ax = plt.subplots(figsize=(6,3))
            totales.plot(kind="bar", ax=ax, color="skyblue")
            ax.set_ylabel("Puntos")
            ax.set_title("Distribución de valores")
            st.pyplot(fig)
        else:
            st.info("ℹ️ Este estudiante aún no tiene puntos asignados.")


        # =========================
        # ➕ Asignar puntos
        # =========================
        st.subheader("➕ Asignar puntos")

        valores_df = leer_valores(colegio_id)

        if valores_df.empty:
            st.warning("⚠️ Este colegio aún no tiene valores definidos.")
        else:
            categoria = st.selectbox("Categoría", valores_df["nombre"].tolist())
            delta = st.number_input("Puntos (+/-)", -10, 10, 1)
            if st.button("Actualizar puntos"):
                actualizar_puntos(r["estudiante_id"], categoria, delta, profesor_id)
                st.success(f"{delta:+} puntos añadidos en {categoria}.")
                st.rerun()


        # =========================
        # ✏️ Editar datos completos (solo DIRECTOR)
        # =========================
# =========================
# ➕ Añadir nuevo estudiante (solo DIRECTOR)
# =========================
        if rol == "director":
            st.header("✏️ Editar estudiante")
            with st.form("editar_estudiante"):
                codigo_edit = st.text_input("Código", value=r["codigo"])
                nombre_edit = st.text_input("Nombre", value=r["nombre"])
                apellidos_edit = st.text_input("Apellidos", value=r["apellidos"])
                grado_edit = st.text_input("Grado", value=r["grado"])

                # Obtener fraternidades disponibles
                with engine.connect() as conn:
                    frats = pd.read_sql(
                        text("SELECT id, nombre FROM fraternidades WHERE colegio_id=:cid"),
                        conn,
                        params={"cid": colegio_id}
                    )

                fraternidad_edit = st.selectbox(
                    "Fraternidad",
                    frats["nombre"].tolist(),
                    index=frats["nombre"].tolist().index(r["fraternidad"]) if r["fraternidad"] in frats["nombre"].tolist() else 0
                )

                submit = st.form_submit_button("💾 Guardar cambios")
                if submit:
                    frat_id = frats.loc[frats["nombre"] == fraternidad_edit, "id"].iloc[0]
                    actualizar_estudiante_full(r["estudiante_id"], codigo_edit, nombre_edit, apellidos_edit, grado_edit, frat_id)
                    st.success("✅ Estudiante actualizado correctamente.")
                    st.rerun()

       # 📋 Historial de puntos
        st.subheader("📋 Historial de puntos")
        historial = leer_historial_puntos(r["estudiante_id"], colegio_id)  # 👈 pasa también el colegio_id
        st.dataframe(historial, use_container_width=True)

