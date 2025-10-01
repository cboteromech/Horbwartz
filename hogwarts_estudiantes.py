import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# =========================
# ⚙️ Configuración general
# =========================
st.set_page_config(page_title="🎓 Portal del Estudiante", page_icon="📘", layout="centered")

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
# 📂 Función para leer resumen
# =========================
@st.cache_data(ttl=60)
def leer_resumen() -> pd.DataFrame:
    query = "SELECT * FROM resumen_puntos_estudiantes;"
    return pd.read_sql(query, engine)

df = leer_resumen()

# =========================
# 🎓 Portal del Estudiante
# =========================
st.title("🎓 Portal del Estudiante - Sistema Hogwarts")

# Pivot para tener una fila por estudiante y columnas dinámicas por valores
df_pivot = df.pivot_table(
    index=["codigo", "nombre", "apellidos", "grado", "fraternidad", "colegio"],
    columns="valor",
    values="puntos",
    aggfunc="sum",
    fill_value=0
).reset_index()

df_pivot["Total"] = df_pivot.drop(
    columns=["codigo", "nombre", "apellidos", "grado", "fraternidad", "colegio"]
).sum(axis=1)

# Lista de estudiantes disponibles
opciones = df_pivot.apply(lambda r: f"{r['nombre']} {r['apellidos']} ({r['codigo']})", axis=1).tolist()
seleccion = st.selectbox("Selecciona tu nombre o código:", [""] + opciones)

if seleccion != "":
    codigo = seleccion.split("(")[-1].replace(")", "").strip()
    alumno = df_pivot[df_pivot["codigo"] == codigo]

    if alumno.empty:
        st.error("⚠️ No se encontró ningún estudiante con ese código.")
    else:
        r = alumno.iloc[0]

        # =========================
        # Perfil destacado
        # =========================
        st.markdown(
            f"""
            ### 👤 {r['nombre']} {r['apellidos']}  
            🪪 **Código:** {r['codigo']}  
            🏠 **Fraternidad:** {r['fraternidad']}  
            🏫 **Colegio:** {r['colegio']}  
            🎓 **Grado:** {r['grado']}  
            🧮 **Total puntos:** {int(r['Total'])}
            """
        )

        # =========================
        # Tabla de puntos dinámicos
        # =========================
        puntos_df = pd.DataFrame(r.drop(
            labels=["codigo","nombre","apellidos","grado","fraternidad","colegio"]
        )).reset_index()
        puntos_df.columns = ["Categoría", "Puntos"]

        st.subheader("📊 Tus puntos por valor")
        st.table(puntos_df)

        # =========================
        # Gráfico de barras
        # =========================
        fig, ax = plt.subplots(figsize=(5, 3))
        puntos_df.set_index("Categoría")["Puntos"].plot(kind="bar", ax=ax, color="skyblue")
        ax.set_ylabel("Puntos")
        ax.set_title("Tus puntos por categoría")
        plt.xticks(rotation=30, ha="right")
        st.pyplot(fig)
