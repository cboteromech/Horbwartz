import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

FILE = "Horbwartz.csv"
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# Diagnóstico inicial
# =========================
st.title("🎓 Portal del Estudiante - Sistema Hogwarts")

try:
    df_raw = pd.read_csv(FILE, sep=";", encoding="latin1")
except UnicodeDecodeError:
    df_raw = pd.read_csv(FILE, sep=";", encoding="utf-8")

st.subheader("🔍 Columnas originales detectadas en el CSV")
st.write(df_raw.columns.tolist())
st.dataframe(df_raw.head())

# =========================
# Función para normalizar
# =========================
@st.cache_data
def leer_csv(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, sep=";", encoding="latin1")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="utf-8")

    # Normalizar nombres de columnas
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.replace("ó", "o", regex=False)
    df.columns = df.columns.str.replace("í", "i", regex=False)
    df.columns = df.columns.str.replace("Í", "i", regex=False)

    # Intentar mapear a los esperados
    renombres = {
        "Codigo": "Código",
        "codigo": "Código",
        "cod": "Código",
        "nombre": "Nombre",
        "apellidos": "Apellidos",
        "fraternidad": "Fraternidad",
    }
    df = df.rename(columns={c: renombres.get(c, c) for c in df.columns})

    # Si no hay columna Código → buscar similar
    if "Código" not in df.columns:
        posibles = [c for c in df.columns if "cod" in c.lower()]
        if posibles:
            df = df.rename(columns={posibles[0]: "Código"})
        else:
            st.error("❌ No encontré columna para Código en el CSV.")
            return df

    # Asegurar categorías
    for c in CATEGORIAS:
        if c not in df.columns:
            df[c] = 0

    # Calcular total y nombre completo
    df[CATEGORIAS] = df[CATEGORIAS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    df["Total"] = df[CATEGORIAS].sum(axis=1)
    df["NombreCompleto"] = (
        df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
    )
    df["Código"] = df["Código"].astype(str).str.strip()

    return df

# =========================
# Recargar datos
# =========================
if st.button("🔄 Refrescar datos"):
    st.cache_data.clear()

df = leer_csv(FILE)

if "Código" in df.columns:
    # Lista de estudiantes
    opciones = df.apply(lambda r: f"{r['NombreCompleto']} ({r['Código']})", axis=1).tolist()
    seleccion = st.selectbox("Selecciona tu nombre o código:", [""] + opciones)

    if seleccion != "":
        codigo = seleccion.split("(")[-1].replace(")", "").strip()
        alumno = df[df["Código"].astype(str) == codigo]

        if alumno.empty:
            st.error("⚠️ No se encontró ningún estudiante con ese código.")
        else:
            r = alumno.iloc[0]

            # Perfil
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

            # Gráfica fraternidad
            frat_vals = frat_df[CATEGORIAS].sum()
            fig2, ax2 = plt.subplots()
            frat_vals.plot(kind="bar", ax=ax2, color="orange")
            ax2.set_ylabel("Puntos")
            ax2.set_title(f"Puntos acumulados - {r['Fraternidad']}")
            plt.xticks(rotation=45, ha="right")
            st.pyplot(fig2)
