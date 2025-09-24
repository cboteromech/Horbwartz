import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

FILE = "Horbwartz.csv"
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# Cargar datos
# =========================
@st.cache_data
def leer_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="latin1")
    # Asegurar columnas numéricas
    df[CATEGORIAS] = df[CATEGORIAS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    df["Total"] = df[CATEGORIAS].sum(axis=1)
    df["NombreCompleto"] = (
        df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
    )
    return df

df = leer_csv(FILE)

# =========================
# App Estudiantes
# =========================
st.title("🎓 Portal del Estudiante - Sistema Hogwarts")

# Lista de estudiantes disponibles (código + nombre)
opciones = df.apply(lambda r: f"{r['NombreCompleto']} ({r['Código']})", axis=1).tolist()

# Selector de estudiante (con búsqueda incluida en selectbox)
seleccion = st.selectbox("Selecciona tu nombre o código:", [""] + opciones)

if seleccion != "":
    # Extraer código desde la opción elegida
    codigo = seleccion.split("(")[-1].replace(")", "").strip()
    alumno = df[df["Código"].astype(str) == codigo]

    if alumno.empty:
        st.error("⚠️ No se encontró ningún estudiante con ese código.")
    else:
        r = alumno.iloc[0]

        # Perfil del estudiante
        st.success(
            f"👤 **{r['NombreCompleto']}** | 🪪 Código: {r['Código']} | "
            f"🏠 Fraternidad: {r['Fraternidad']} | 🧮 Total: {int(r['Total'])}"
        )

        # Gráfica individual
        st.subheader("📈 Tus puntos por categoría")
        vals = r[CATEGORIAS]
        fig, ax = plt.subplots()
        vals.plot(kind="bar", ax=ax, color="skyblue")
        ax.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)

        # Resumen de fraternidad
        frat_df = df[df["Fraternidad"] == r["Fraternidad"]]
        total_frat = frat_df["Total"].sum()
        st.subheader(f"🏠 Resumen de tu fraternidad: {r['Fraternidad']}")
        st.info(f"👥 {len(frat_df)} estudiantes | 🧮 {total_frat} puntos en total")

        # Gráfica de la fraternidad
        frat_vals = frat_df[CATEGORIAS].sum()
        fig2, ax2 = plt.subplots()
        frat_vals.plot(kind="bar", ax=ax2, color="orange")
        ax2.set_ylabel("Puntos")
        ax2.set_title(f"Puntos acumulados - {r['Fraternidad']}")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig2)
