import os
import shutil
import tempfile
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import numpy as np
from pyzbar.pyzbar import decode

# ----------------------------
# Config & utilidades
# ----------------------------
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

FILE = "Horbwartz.csv"
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

def leer_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        cols = ["Código", "Nombre", "Apellidos", "Fraternidad", *CATEGORIAS, "Total"]
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(path, sep=";", encoding="latin1")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
    df.columns = [str(c).strip() for c in df.columns]
    for col in ["Código", "Nombre", "Apellidos", "Fraternidad", *CATEGORIAS]:
        if col not in df.columns:
            df[col] = 0 if col in CATEGORIAS else ""
    if "Total" not in df.columns:
        df["Total"] = 0
    df["Total"] = df[CATEGORIAS].sum(axis=1)
    return df

def guardar_csv_seguro(df: pd.DataFrame, path: str):
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.csv")
    df.to_csv(tmpfile, sep=";", index=False, encoding="latin1")
    shutil.move(tmpfile, path)
    shutil.rmtree(tmpdir, ignore_errors=True)

# ----------------------------
# Cargar datos
# ----------------------------
df = leer_csv(FILE)
df["NombreCompleto"] = (df["Nombre"].astype(str).str.strip() + " " +
                        df["Apellidos"].astype(str).str.strip()).str.strip()

fraternidades_existentes = df["Fraternidad"].dropna().astype(str).str.strip().unique().tolist()
fraternidades_default = ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"]
FRATERNIDADES = sorted(list(set(fraternidades_existentes + fraternidades_default)))

st.session_state.setdefault("busqueda_codigo", "")
st.session_state.setdefault("busqueda_nombre", "")
st.session_state.setdefault("activar_camara", False)

st.title("🏆 Sistema de Puntos Hogwarts")

# =======================================================
# Añadir estudiante
# =======================================================
with st.expander("➕ Añadir nuevo estudiante", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        nuevo_codigo = st.text_input("Código", key="add_codigo")
    with col2:
        nuevo_nombre = st.text_input("Nombre", key="add_nombre")
    with col3:
        nuevo_apellido = st.text_input("Apellidos", key="add_apellido")
    with col4:
        nueva_fraternidad = st.selectbox("Fraternidad", FRATERNIDADES, key="add_frat")

    if st.button("Agregar estudiante", key="btn_add_student"):
        if not nuevo_codigo or not nuevo_nombre or not nuevo_apellido:
            st.error("⚠️ Todos los campos son obligatorios.")
        elif df["Código"].astype(str).eq(str(nuevo_codigo).strip()).any():
            st.error("⚠️ Ya existe un estudiante con ese código.")
        else:
            nueva_fila = {
                "Código": str(nuevo_codigo).strip(),
                "Nombre": str(nuevo_nombre).strip(),
                "Apellidos": str(nuevo_apellido).strip(),
                "Fraternidad": str(nueva_fraternidad).strip(),
            }
            for c in CATEGORIAS:
                nueva_fila[c] = 0
            nueva_fila["Total"] = 0
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            guardar_csv_seguro(df, FILE)
            st.success(f"✅ Estudiante {nuevo_nombre} {nuevo_apellido} añadido.")
            st.rerun()

# =======================================================
# Buscar estudiante (manual o QR)
# =======================================================
st.subheader("🔎 Buscar estudiante")

colb1, colb2 = st.columns([2,1])
with colb1:
    st.session_state["busqueda_codigo"] = st.text_input(
        "Buscar por código", st.session_state.get("busqueda_codigo", ""), key="search_codigo"
    )
with colb2:
    if st.button("📷 Escanear QR", key="abrir_qr"):
        st.session_state["activar_camara"] = True

# Cámara solo cuando se activa
if st.session_state.get("activar_camara", False):
    foto = st.camera_input("Apunta al QR y espera...")
    if foto:
        file_bytes = np.asarray(bytearray(foto.getbuffer()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        decoded = decode(img)
        if decoded:
            qr = decoded[0].data.decode("utf-8").strip()
            st.session_state["busqueda_codigo"] = qr
            st.success(f"📌 Código detectado automáticamente: {qr}")
            st.session_state["activar_camara"] = False  # cerrar cámara
            st.rerun()

st.session_state["busqueda_nombre"] = st.text_input(
    "Buscar por nombre o apellido", st.session_state.get("busqueda_nombre", ""), key="search_nombre"
)

# Resolver búsqueda
estudiante = None
found = pd.DataFrame()
if st.session_state["busqueda_codigo"].strip():
    found = df[df["Código"].astype(str) == st.session_state["busqueda_codigo"].strip()]
elif st.session_state["busqueda_nombre"].strip():
    found = df[df["NombreCompleto"].str.contains(st.session_state["busqueda_nombre"], case=False, na=False)]

if not found.empty:
    opciones = found["NombreCompleto"].tolist()
else:
    opciones = df["NombreCompleto"].tolist()

estudiante = st.selectbox("Selecciona un estudiante", opciones, key="select_estudiante") if opciones else None

# =======================================================
# Card info
# =======================================================
if estudiante:
    row = df.loc[df["NombreCompleto"] == estudiante].iloc[0]
    st.info(f"👤 **{estudiante}** | 🪪 Código: **{row['Código']}** | 🏠 Fraternidad: **{row['Fraternidad']}** | 🧮 Total: **{int(row['Total'])}**")

# =======================================================
# Editar estudiante
# =======================================================
if estudiante:
    with st.expander("✏️ Editar datos del estudiante", expanded=False):
        fila = df.loc[df["NombreCompleto"] == estudiante].iloc[0]
        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1:
            nuevo_codigo = st.text_input("Código", str(fila["Código"]), key="edit_codigo")
        with ec2:
            nuevo_nombre = st.text_input("Nombre", str(fila["Nombre"]), key="edit_nombre")
        with ec3:
            nuevo_apellido = st.text_input("Apellidos", str(fila["Apellidos"]), key="edit_apellido")
        with ec4:
            try:
                idx_frat = FRATERNIDADES.index(str(fila["Fraternidad"]))
            except ValueError:
                idx_frat = 0
            nueva_fraternidad = st.selectbox("Fraternidad", FRATERNIDADES, index=idx_frat, key="edit_frat")

        if st.button("💾 Guardar cambios", key="btn_save_edit"):
            df.loc[df["Código"].astype(str) == str(fila["Código"]).strip(),
                   ["Código","Nombre","Apellidos","Fraternidad"]] = [
                        str(nuevo_codigo).strip(),
                        str(nuevo_nombre).strip(),
                        str(nuevo_apellido).strip(),
                        str(nueva_fraternidad).strip()
                   ]
            df["NombreCompleto"] = (df["Nombre"].astype(str).str.strip() + " " +
                                    df["Apellidos"].astype(str).str.strip()).str.strip()
            df["Total"] = df[CATEGORIAS].sum(axis=1)
            guardar_csv_seguro(df, FILE)
            st.success("✅ Datos actualizados.")
            st.rerun()

# =======================================================
# Puntos
# =======================================================
if estudiante:
    with st.expander("➕➖ Asignar puntos"):
        codigo_est = df.loc[df["NombreCompleto"] == estudiante, "Código"].iloc[0]

        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            columna = st.selectbox("Categoría", CATEGORIAS, key="puntos_categoria")
        with pc2:
            # Limitar rango entre -10 y +10
            puntos = st.number_input("Puntos (+/-)", step=1, value=1, min_value=-10, max_value=10, key="puntos_valor")
        with pc3:
            accion_rapida = st.radio("Acción rápida", ["Ninguna", "+1", "+5", "-1", "-5"],
                                     index=0, horizontal=True, key="puntos_rapidos")
            if accion_rapida != "Ninguna":
                puntos = int(accion_rapida.replace("+","")) if "+" in accion_rapida else -int(accion_rapida.replace("-",""))
                # Aseguramos el límite
                puntos = max(-10, min(10, puntos))

        if st.button("Actualizar puntos", key="btn_actualizar_puntos"):
            if -10 <= puntos <= 10:
                df.loc[df["Código"].astype(str) == str(codigo_est), columna] += int(puntos)
                df["Total"] = df[CATEGORIAS].sum(axis=1)
                guardar_csv_seguro(df, FILE)
                st.success(f"✅ {puntos:+} puntos a **{estudiante}** en **{columna}**.")
                st.rerun()
            else:
                st.error("⚠️ Solo se permite asignar entre -10 y +10 puntos.")


# =======================================================
# Tabla y gráficas
# =======================================================
st.subheader("📊 Tabla de puntos")
frat_sel = st.selectbox("Filtrar por fraternidad", ["Todas"] + FRATERNIDADES, key="filtro_frat")
df_filtrado = df if frat_sel == "Todas" else df[df["Fraternidad"] == frat_sel]
st.dataframe(df_filtrado, use_container_width=True)

gc1, gc2 = st.columns(2)
if estudiante:
    with gc1:
        st.subheader(f"📈 Perfil de {estudiante}")
        vals = df.loc[df["NombreCompleto"] == estudiante, CATEGORIAS].iloc[0]
        fig, ax = plt.subplots()
        vals.plot(kind="bar", ax=ax, color="skyblue")
        ax.set_title(f"Puntos por categoría - {estudiante}")
        ax.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)

if frat_sel != "Todas":
    with gc2:
        st.subheader(f"🏠 Fraternidad: {frat_sel}")
        tot = df_filtrado[CATEGORIAS].sum()
        fig2, ax2 = plt.subplots()
        tot.plot(kind="bar", ax=ax2, color="orange")
        ax2.set_title(f"Puntos acumulados - {frat_sel}")
        ax2.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig2)
