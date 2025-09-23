import os
import shutil
import tempfile
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import numpy as np

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
st.session_state.setdefault("select_estudiante", None)

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

        # Detectar QR con OpenCV
        detector = cv2.QRCodeDetector()
        qr, bbox, _ = detector.detectAndDecode(img)

        if qr:
            st.session_state["busqueda_codigo"] = qr.strip()
            st.success(f"📌 Código detectado automáticamente: {qr}")
            st.session_state["activar_camara"] = False  # cerrar cámara
            # Forzar selección automática en el selectbox
            match = df[df["Código"].astype(str) == qr.strip()]
            if not match.empty:
                st.session_state["select_estudiante"] = match["NombreCompleto"].iloc[0]
            st.rerun()

st.session_state["busqueda_nombre"] = st.text_input(
    "Buscar por nombre o apellido", st.session_state.get("busqueda_nombre", ""), key="search_nombre"
)

# Resolver búsqueda
found = pd.DataFrame()
if st.session_state["busqueda_codigo"].strip():
    found = df[df["Código"].astype(str) == st.session_state["busqueda_codigo"].strip()]
elif st.session_state["busqueda_nombre"].strip():
    found = df[df["NombreCompleto"].str.contains(st.session_state["busqueda_nombre"], case=False, na=False)]

opciones = found["NombreCompleto"].tolist() if not found.empty else df["NombreCompleto"].tolist()

if opciones:
    index_default = 0
    if st.session_state.get("select_estudiante") in opciones:
        index_default = opciones.index(st.session_state["select_estudiante"])
    estudiante = st.selectbox("Selecciona un estudiante", opciones, index=index_default, key="select_estudiante")
else:
    estudiante = None

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
