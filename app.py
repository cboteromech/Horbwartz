import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

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

try:
    with engine.connect() as conn:
        st.success("✅ Conexión a Supabase exitosa")
except Exception as e:
    st.error(f"❌ Error al conectar: {e}")

# Categorías de puntos
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# 📂 Funciones DB
# =========================
def leer_estudiantes() -> pd.DataFrame:
    query = "SELECT * FROM estudiantes;"
    df = pd.read_sql(query, engine)

    # Normalización
    for c in CATEGORIAS:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    if "Total" not in df.columns:
        df["Total"] = 0
    df["Total"] = df[CATEGORIAS].sum(axis=1)

    df["NombreCompleto"] = (
        df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
    ).str.strip()
    df["Código"] = df["Código"].astype(str).str.strip()
    return df

def insertar_estudiante(codigo, nombre, apellido, fraternidad):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO estudiantes ("Código","Nombre","Apellidos","Fraternidad","Marca LCB","Respeto",
            "Solidaridad","Honestidad","Gratitud","Corresponsabilidad","Total")
            VALUES (:codigo, :nombre, :apellido, :frat, 0,0,0,0,0,0,0)
        """), {"codigo": codigo, "nombre": nombre, "apellido": apellido, "frat": fraternidad})

def actualizar_estudiante(codigo, campo, valor):
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE estudiantes SET "{campo}" = :valor WHERE "Código" = :codigo'),
                     {"valor": valor, "codigo": codigo})

def actualizar_puntos(codigo, categoria, delta):
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE estudiantes SET "{categoria}" = "{categoria}" + :delta WHERE "Código" = :codigo'),
                     {"delta": delta, "codigo": codigo})

def actualizar_puntos_frat(frat, categoria, delta):
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE estudiantes SET "{categoria}" = "{categoria}" + :delta WHERE "Fraternidad" = :frat'),
                     {"delta": delta, "frat": frat})

def actualizar_puntos_grupo(codigos, categoria, delta):
    with engine.begin() as conn:
        conn.execute(text(f'UPDATE estudiantes SET "{categoria}" = "{categoria}" + :delta WHERE "Código" = ANY(:codigos)'),
                     {"delta": delta, "codigos": codigos})

# =========================
# 🏆 App principal
# =========================
df = leer_estudiantes()
frats_default = ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"]
FRATERNIDADES = sorted(set(df["Fraternidad"].dropna().astype(str).tolist() + frats_default))

st.title("🏆 Sistema de Puntos Hogwarts")

# =======================================================
# 👤 Gestión de estudiantes
# =======================================================
with st.expander("➕ Añadir nuevo estudiante"):
    c1, c2, c3, c4 = st.columns(4)
    with c1: codigo = st.text_input("Código")
    with c2: nombre = st.text_input("Nombre")
    with c3: apellido = st.text_input("Apellidos")
    with c4: frat = st.selectbox("Fraternidad", FRATERNIDADES)

    if st.button("Agregar estudiante"):
        if not codigo or not nombre or not apellido:
            st.error("⚠️ Todos los campos son obligatorios.")
        elif df["Código"].astype(str).eq(str(codigo).strip()).any():
            st.error("⚠️ Ya existe un estudiante con ese código.")
        else:
            insertar_estudiante(str(codigo).strip(), nombre.strip(), apellido.strip(), frat.strip())
            st.success(f"✅ Estudiante {nombre} {apellido} añadido.")
            st.rerun()

# =======================================================
# 🔎 Buscar y editar estudiante
# =======================================================
st.header("🔎 Buscar estudiante")
opciones = df.apply(lambda r: f"{r['NombreCompleto']} ({r['Código']})", axis=1).tolist()
seleccion = st.selectbox("Selecciona estudiante:", [""] + opciones)

if seleccion != "":
    codigo = seleccion.split("(")[-1].replace(")", "").strip()
    alumno = df[df["Código"] == codigo]

    if alumno.empty:
        st.error("No encontrado.")
    else:
        r = alumno.iloc[0]
        st.success(f"👤 {r['NombreCompleto']} | 🏠 {r['Fraternidad']} | 🧮 {r['Total']} puntos")

        # 📊 Gráfico individual
        st.subheader("📈 Puntos del estudiante")
        fig, ax = plt.subplots(figsize=(5,3))
        r[CATEGORIAS].plot(kind="bar", ax=ax, color="skyblue")
        st.pyplot(fig)

        # ✏️ Editar datos
        with st.expander("✏️ Editar datos del estudiante"):
            nuevo_nombre = st.text_input("Nombre", r["Nombre"])
            nuevo_apellido = st.text_input("Apellidos", r["Apellidos"])
            nueva_frat = st.selectbox("Fraternidad", FRATERNIDADES, index=FRATERNIDADES.index(r["Fraternidad"]))

            if st.button("💾 Guardar cambios"):
                actualizar_estudiante(codigo, "Nombre", nuevo_nombre.strip())
                actualizar_estudiante(codigo, "Apellidos", nuevo_apellido.strip())
                actualizar_estudiante(codigo, "Fraternidad", nueva_frat.strip())
                st.success("✅ Datos actualizados correctamente.")
                st.rerun()

        # ➕ Asignar puntos individuales
        st.subheader("➕ Asignar puntos")
        categoria = st.selectbox("Categoría", CATEGORIAS)
        delta = st.number_input("Puntos (+/-)", -10, 10, 1)
        if st.button("Actualizar puntos"):
            actualizar_puntos(codigo, categoria, delta)
            st.success(f"{delta:+} puntos añadidos en {categoria}.")
            st.rerun()

# =======================================================
# ⚡ Asignación masiva de puntos
# =======================================================
with st.expander("🏠 Asignar puntos a una fraternidad"):
    frat_target = st.selectbox("Selecciona fraternidad", FRATERNIDADES, key="bulk_frat")
    cat_bulk = st.selectbox("Categoría", CATEGORIAS, key="bulk_frat_cat")
    pts_bulk = st.number_input("Puntos (+/-)", step=1, value=1, min_value=-50, max_value=50, key="bulk_frat_pts")
    if st.button("Aplicar a fraternidad"):
        actualizar_puntos_frat(frat_target, cat_bulk, pts_bulk)
        st.success(f"✅ {pts_bulk:+} puntos añadidos a todos en {frat_target}.")
        st.rerun()

with st.expander("👥 Asignar puntos a varios estudiantes"):
    opciones_codigos = df["Código"].astype(str).tolist()
    seleccionados = st.multiselect("Selecciona estudiantes", opciones_codigos,
                                   format_func=lambda c: df[df["Código"] == c]["NombreCompleto"].iloc[0])
    cat_bulk2 = st.selectbox("Categoría", CATEGORIAS, key="bulk_group_cat")
    pts_bulk2 = st.number_input("Puntos (+/-)", step=1, value=1, min_value=-50, max_value=50, key="bulk_group_pts")
    if st.button("Aplicar a seleccionados"):
        actualizar_puntos_grupo(seleccionados, cat_bulk2, pts_bulk2)
        st.success(f"✅ {pts_bulk2:+} puntos añadidos a {len(seleccionados)} estudiantes.")
        st.rerun()

# =======================================================
# 📊 Reportes y análisis
# =======================================================
st.header("📊 Reportes")

# Tabla completa
st.subheader("📋 Tabla de estudiantes")
st.dataframe(df, use_container_width=True)

# Resumen por fraternidad
st.subheader("📋 Resumen por fraternidad")
resumen = (
    df.groupby("Fraternidad")
      .agg(Estudiantes=("Código", "count"), PuntosTotales=("Total", "sum"))
      .reset_index()
      .sort_values("PuntosTotales", ascending=False)
)
st.dataframe(resumen, use_container_width=True)

# Ranking gráfico
st.subheader("🏆 Ranking de casas")
fig2, ax2 = plt.subplots(figsize=(6,3))
resumen.plot(x="Fraternidad", y="PuntosTotales", kind="barh", ax=ax2, color="gold")
st.pyplot(fig2)

# Tabla filtrada
st.subheader("📊 Ver estudiantes por fraternidad")
frat_filtro = st.selectbox("Elige una fraternidad", [""] + FRATERNIDADES)
if frat_filtro:
    df_frat = df[df["Fraternidad"] == frat_filtro]
    st.dataframe(df_frat, use_container_width=True)

# Valores fuertes de cada casa
st.subheader("💪 Valores fuertes por casa")
resumen_valores = df.groupby("Fraternidad")[CATEGORIAS].sum().reset_index()
frat_valores = st.selectbox("Selecciona una fraternidad para ver sus valores", FRATERNIDADES)

if frat_valores:
    datos_casa = resumen_valores[resumen_valores["Fraternidad"] == frat_valores]
    valores = datos_casa[CATEGORIAS].iloc[0]

    fig3, ax3 = plt.subplots(figsize=(6,3))
    valores.plot(kind="bar", ax=ax3, color="skyblue")
    ax3.set_ylabel("Puntos acumulados")
    ax3.set_title(f"Valores de {frat_valores}")
    st.pyplot(fig3)
