import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

# =========================
# Configuración general
# =========================
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

# =========================
# Conexión a Supabase Postgres
# =========================
# ⚠️ Reemplaza con tu contraseña real de Supabase
DB_USER = st.secrets["postgres"]
DB_PASS = st.secrets["Socralia*0705"]
DB_HOST = st.secrets["db.pgrfwakeiapwimbmulfo.supabase.co"]
DB_PORT = st.secrets["5432"]
DB_NAME = st.secrets["postgres"]

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Categorías de puntos
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# Funciones DB
# =========================
def leer_estudiantes() -> pd.DataFrame:
    query = "SELECT * FROM estudiantes;"
    df = pd.read_sql(query, engine)

    # Normalizar datos
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
# App principal
# =========================
df = leer_estudiantes()
frats_default = ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"]
FRATERNIDADES = sorted(set(df["Fraternidad"].dropna().astype(str).tolist() + frats_default))

st.title("🏆 Sistema de Puntos Hogwarts (Supabase)")

# =======================================================
# Añadir estudiante
# =======================================================
with st.expander("➕ Añadir nuevo estudiante", expanded=False):
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
# Buscar estudiante
# =======================================================
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

        # -------------------------
        # Gráfico alumno
        # -------------------------
        st.subheader("📈 Puntos individuales")
        fig, ax = plt.subplots()
        r[CATEGORIAS].plot(kind="bar", ax=ax, color="skyblue")
        st.pyplot(fig)

        # -------------------------
        # Editar fraternidad
        # -------------------------
        nueva_frat = st.selectbox("Cambiar fraternidad", FRATERNIDADES, index=FRATERNIDADES.index(r["Fraternidad"]))
        if st.button("💾 Guardar fraternidad"):
            actualizar_estudiante(codigo, "Fraternidad", nueva_frat)
            st.success("Fraternidad actualizada.")
            st.rerun()

        # -------------------------
        # Asignar puntos
        # -------------------------
        categoria = st.selectbox("Categoría", CATEGORIAS)
        delta = st.number_input("Puntos (+/-)", -10, 10, 1)
        if st.button("Actualizar puntos"):
            actualizar_puntos(codigo, categoria, delta)
            st.success(f"{delta:+} puntos añadidos en {categoria}.")
            st.rerun()

# =======================================================
# Asignar puntos en bloque
# =======================================================
with st.expander("🏠 Asignar puntos a fraternidad completa", expanded=False):
    frat_target = st.selectbox("Selecciona fraternidad", FRATERNIDADES, key="bulk_frat")
    cat_bulk = st.selectbox("Categoría", CATEGORIAS, key="bulk_frat_cat")
    pts_bulk = st.number_input("Puntos (+/-)", step=1, value=1, min_value=-50, max_value=50, key="bulk_frat_pts")
    if st.button("Aplicar a fraternidad"):
        actualizar_puntos_frat(frat_target, cat_bulk, pts_bulk)
        st.success(f"✅ {pts_bulk:+} puntos añadidos a todos en {frat_target}.")
        st.rerun()

with st.expander("👥 Asignar puntos a varios estudiantes", expanded=False):
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
# Tabla y gráficas
# =======================================================
st.subheader("📊 Tabla de estudiantes")
st.dataframe(df, use_container_width=True)

# =======================================================
# Resumen por fraternidad
# =======================================================
st.subheader("📋 Resumen por fraternidad")
resumen = (
    df.groupby("Fraternidad")
      .agg(Estudiantes=("Código", "count"), PuntosTotales=("Total", "sum"))
      .reset_index()
      .sort_values("PuntosTotales", ascending=False)
)
st.dataframe(resumen, use_container_width=True)

for _, row in resumen.iterrows():
    st.write(f"🏠 **{row['Fraternidad']}** → {row['Estudiantes']} estudiantes | {row['PuntosTotales']} puntos")
