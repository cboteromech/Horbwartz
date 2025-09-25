import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# =========================
# ⚙️ Configuración general
# =========================
st.set_page_config(page_title="🎓 Portal del Estudiante", page_icon="📘", layout="wide")

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

CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# 📂 Función para leer estudiantes
# =========================
@st.cache_data(ttl=60)
def leer_estudiantes() -> pd.DataFrame:
    query = "SELECT * FROM estudiantes;"
    df = pd.read_sql(query, engine)

    # Normalización de datos
    for c in CATEGORIAS:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    if "Total" not in df.columns:
        df["Total"] = 0
    df["Total"] = df[CATEGORIAS].sum(axis=1)

    if not df.empty:
        df["NombreCompleto"] = (
            df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
        )
        df["Código"] = df["Código"].astype(str).str.strip()
    return df

df = leer_estudiantes()

# =========================
# 🎓 Portal del Estudiante
# =========================
st.title("🎓 Portal del Estudiante - Sistema Hogwarts")

# Lista de estudiantes disponibles
opciones = df.apply(lambda r: f"{r['NombreCompleto']} ({r['Código']})", axis=1).tolist()
seleccion = st.selectbox("Selecciona tu nombre o código:", [""] + opciones)

if seleccion != "":
    codigo = seleccion.split("(")[-1].replace(")", "").strip()
    alumno = df[df["Código"] == codigo]

    if alumno.empty:
        st.error("⚠️ No se encontró ningún estudiante con ese código.")
    else:
        r = alumno.iloc[0]

        # Perfil
        st.success(
            f"👤 **{r['NombreCompleto']}** | 🪪 Código: {r['Código']} | "
            f"🏠 Fraternidad: {r['Fraternidad']} | 🧮 Total: {int(r['Total'])}"
        )

        # Gráfico individual
        st.subheader("📈 Tus puntos por categoría")
        vals = r[CATEGORIAS]
        fig, ax = plt.subplots()
        vals.plot(kind="bar", ax=ax, color="skyblue")
        ax.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)

        # Resumen de la fraternidad
        frat_df = df[df["Fraternidad"] == r["Fraternidad"]]
        total_frat = frat_df["Total"].sum()
        st.subheader(f"🏠 Resumen de tu fraternidad: {r['Fraternidad']}")
        st.info(f"👥 {len(frat_df)} estudiantes | 🧮 {total_frat} puntos en total")

        # Gráfico de la fraternidad
        frat_vals = frat_df[CATEGORIAS].sum()
        fig2, ax2 = plt.subplots()
        frat_vals.plot(kind="bar", ax=ax2, color="orange")
        ax2.set_ylabel("Puntos")
        ax2.set_title(f"Puntos acumulados - {r['Fraternidad']}")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig2)
