import os
import shutil
import tempfile
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import cv2
import numpy as np

# =========================
# Configuración general
# =========================
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

FILE = "Horbwartz.csv"
CATEGORIAS = ["Marca LCB", "Respeto", "Solidaridad", "Honestidad", "Gratitud", "Corresponsabilidad"]

# =========================
# Utilidades CSV
# =========================
def leer_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        cols = ["Código", "Nombre", "Apellidos", "Fraternidad", *CATEGORIAS, "Total"]
        return pd.DataFrame(columns=cols)

    # Intentar latin1 y luego utf-8
    try:
        df = pd.read_csv(path, sep=";", encoding="latin1")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="utf-8")

    df.columns = [str(c).strip() for c in df.columns]

    # Asegurar columnas mínimas
    for col in ["Código", "Nombre", "Apellidos", "Fraternidad", *CATEGORIAS]:
        if col not in df.columns:
            df[col] = 0 if col in CATEGORIAS else ""

    if "Total" not in df.columns:
        df["Total"] = 0

    # Totales coherentes
    df[CATEGORIAS] = df[CATEGORIAS].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    df["Total"] = df[CATEGORIAS].sum(axis=1)

    # Nombre completo auxiliar
    df["NombreCompleto"] = (
        df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
    ).str.strip()

    # Normalizar código a string
    df["Código"] = df["Código"].astype(str).str.strip()

    return df

def guardar_csv_seguro(df: pd.DataFrame, path: str):
    """Escritura segura para evitar PermissionError (Windows/OneDrive)."""
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "tmp.csv")
    df.to_csv(tmpfile, sep=";", index=False, encoding="latin1")
    shutil.move(tmpfile, path)
    shutil.rmtree(tmpdir, ignore_errors=True)

# =========================
# Cargar datos
# =========================
df = leer_csv(FILE)

# Fraternidades
frats_existentes = df["Fraternidad"].dropna().astype(str).str.strip().unique().tolist()
frats_default = ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"]
FRATERNIDADES = sorted(list(set(frats_existentes + frats_default)))

# =========================
# Session State (estado)
# =========================
st.session_state.setdefault("busqueda_codigo", "")
st.session_state.setdefault("busqueda_nombre", "")
st.session_state.setdefault("activar_camara", False)
st.session_state.setdefault("abrir_puntos", False)
# ESTE es el estado fuente-de-verdad del alumno seleccionado
st.session_state.setdefault("selected_code", "")

st.title("🏆 Sistema de Puntos Hogwarts")

# =======================================================
# Añadir estudiante
# =======================================================
with st.expander("➕ Añadir nuevo estudiante", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        add_codigo = st.text_input("Código", key="add_codigo")
    with c2:
        add_nombre = st.text_input("Nombre", key="add_nombre")
    with c3:
        add_apellido = st.text_input("Apellidos", key="add_apellido")
    with c4:
        add_frat = st.selectbox("Fraternidad", FRATERNIDADES, key="add_frat")

    if st.button("Agregar estudiante", key="btn_add_student"):
        if not add_codigo or not add_nombre or not add_apellido:
            st.error("⚠️ Todos los campos son obligatorios.")
        elif df["Código"].astype(str).eq(str(add_codigo).strip()).any():
            st.error("⚠️ Ya existe un estudiante con ese código.")
        else:
            nueva_fila = {
                "Código": str(add_codigo).strip(),
                "Nombre": str(add_nombre).strip(),
                "Apellidos": str(add_apellido).strip(),
                "Fraternidad": str(add_frat).strip(),
            }
            for c in CATEGORIAS:
                nueva_fila[c] = 0
            nueva_fila["Total"] = 0

            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            guardar_csv_seguro(df, FILE)
            st.success(f"✅ Estudiante {add_nombre} {add_apellido} añadido.")
            st.session_state["busqueda_codigo"] = str(add_codigo).strip()
            st.session_state["selected_code"] = str(add_codigo).strip()
            st.rerun()

# =======================================================
# Buscar estudiante (manual o QR)
# =======================================================
st.subheader("🔎 Buscar estudiante")

colb1, colb2 = st.columns([2, 1])
with colb1:
    st.session_state["busqueda_codigo"] = st.text_input(
        "Buscar por código",
        st.session_state.get("busqueda_codigo", ""),
        key="search_codigo",
        placeholder="Escribe el código o usa 📷"
    )
with colb2:
    if st.button("📷 Escanear QR", key="abrir_qr"):
        st.session_state["activar_camara"] = True
        st.session_state["busqueda_nombre"] = ""  # limpiar búsqueda por nombre

# Cámara solo cuando se activa; se apaga sola al detectar
if st.session_state.get("activar_camara", False):
    foto = st.camera_input("Apunta al QR y espera…")
    if foto:
        file_bytes = np.asarray(bytearray(foto.getbuffer()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)

        # OpenCV QR (sin pyzbar)
        detector = cv2.QRCodeDetector()
        qr, bbox, _ = detector.detectAndDecode(img)

        if qr:
            st.session_state["busqueda_codigo"] = qr.strip()
            st.session_state["selected_code"] = qr.strip()
            st.session_state["activar_camara"] = False  # apagar cámara
            st.session_state["abrir_puntos"] = True     # abrir puntos auto
            st.success(f"📌 Código detectado: {qr}")
            st.rerun()
        else:
            st.warning("No se detectó un QR válido. Intenta de nuevo.")

# Búsqueda por nombre
st.session_state["busqueda_nombre"] = st.text_input(
    "Buscar por nombre o apellido",
    st.session_state.get("busqueda_nombre", ""),
    key="search_nombre",
    placeholder="Ej: Camilo, Gerónimo…"
)

# Resolver búsqueda → lista de CÓDIGOS (no nombres)
def filtrar_codigos(_df: pd.DataFrame) -> list[str]:
    cods = _df["Código"].astype(str).tolist()
    # Únicos y ordenados por nombre
    _df2 = _df.drop_duplicates(subset=["Código"]).copy()
    _df2["NombreCompleto"] = (
        _df2["Nombre"].astype(str).str.strip() + " " + _df2["Apellidos"].astype(str).str.strip()
    ).str.strip()
    _df2 = _df2.sort_values("NombreCompleto")
    return _df2["Código"].astype(str).tolist()

found = pd.DataFrame()
if st.session_state["busqueda_codigo"].strip():
    found = df[df["Código"].astype(str) == st.session_state["busqueda_codigo"].strip()]
elif st.session_state["busqueda_nombre"].strip():
    found = df[df["NombreCompleto"].str.contains(st.session_state["busqueda_nombre"], case=False, na=False)]

if not found.empty:
    opciones_codigos = filtrar_codigos(found)
else:
    opciones_codigos = filtrar_codigos(df)

# Determinar índice por defecto (si ya hay seleccionado)
def make_label(code: str) -> str:
    row = df[df["Código"].astype(str) == str(code)]
    if row.empty:
        return str(code)
    r = row.iloc[0]
    return f"{r['Nombre']} {r['Apellidos']} ({r['Código']})"

if opciones_codigos:
    default_index = 0
    if st.session_state["selected_code"] in opciones_codigos:
        default_index = opciones_codigos.index(st.session_state["selected_code"])

    selected_code = st.selectbox(
        "Selecciona un estudiante",
        opciones_codigos,
        index=default_index,
        format_func=make_label,
        key="select_estudiante_code",
    )
    # Actualizar el estado fuente-de-verdad
    st.session_state["selected_code"] = selected_code
else:
    selected_code = ""
    st.warning("No hay estudiantes cargados.")

# Atajo: si se escribió un código válido en la caja, forzamos selección
if st.session_state["busqueda_codigo"].strip() and st.session_state["busqueda_codigo"].strip() in opciones_codigos:
    st.session_state["selected_code"] = st.session_state["busqueda_codigo"].strip()
    selected_code = st.session_state["selected_code"]

# =======================================================
# Card info
# =======================================================
row_sel = df[df["Código"].astype(str) == str(st.session_state["selected_code"])]
if not row_sel.empty:
    r = row_sel.iloc[0]
    estudiante_label = f"{r['Nombre']} {r['Apellidos']}"
    st.info(
        f"👤 **{estudiante_label}** | 🪪 Código: **{r['Código']}** | "
        f"🏠 Fraternidad: **{r['Fraternidad']}** | 🧮 Total: **{int(r['Total'])}**"
    )
else:
    estudiante_label = None

# =======================================================
# Editar estudiante (keys dinámicas por CÓDIGO)
# =======================================================
if estudiante_label:
    with st.expander("✏️ Editar datos del estudiante", expanded=False):
        fila = df[df["Código"].astype(str) == str(st.session_state["selected_code"])].iloc[0]

        e1, e2, e3, e4 = st.columns(4)
        with e1:
            new_codigo = st.text_input(
                "Código",
                value=str(fila["Código"]),
                key=f"edit_codigo__{st.session_state['selected_code']}"
            )
        with e2:
            new_nombre = st.text_input(
                "Nombre",
                value=str(fila["Nombre"]),
                key=f"edit_nombre__{st.session_state['selected_code']}"
            )
        with e3:
            new_apellido = st.text_input(
                "Apellidos",
                value=str(fila["Apellidos"]),
                key=f"edit_apellido__{st.session_state['selected_code']}"
            )
        with e4:
            try:
                idx_frat = FRATERNIDADES.index(str(fila["Fraternidad"]))
            except ValueError:
                idx_frat = 0
            new_frat = st.selectbox(
                "Fraternidad",
                FRATERNIDADES,
                index=idx_frat,
                key=f"edit_frat__{st.session_state['selected_code']}"
            )

        if st.button("💾 Guardar cambios", key=f"btn_save_edit__{st.session_state['selected_code']}"):
            old_code = str(fila["Código"]).strip()
            new_code_norm = str(new_codigo).strip()

            # Actualizar fila
            df.loc[df["Código"].astype(str) == old_code, ["Código","Nombre","Apellidos","Fraternidad"]] = [
                new_code_norm,
                str(new_nombre).strip(),
                str(new_apellido).strip(),
                str(new_frat).strip()
            ]

            # Recalcular auxiliares
            df["NombreCompleto"] = (
                df["Nombre"].astype(str).str.strip() + " " + df["Apellidos"].astype(str).str.strip()
            ).str.strip()
            df["Total"] = df[CATEGORIAS].sum(axis=1)

            guardar_csv_seguro(df, FILE)

            # Si cambió el código, re-seleccionar por el nuevo
            st.session_state["selected_code"] = new_code_norm
            st.session_state["busqueda_codigo"] = new_code_norm

            st.success("✅ Datos actualizados.")
            st.rerun()

# =======================================================
# Asignar puntos (rango -10..+10)
# =======================================================
if estudiante_label:
    with st.expander("➕➖ Asignar puntos", expanded=st.session_state.get("abrir_puntos", False)):
        # Cerrar auto en el siguiente render
        if st.session_state.get("abrir_puntos", False):
            st.session_state["abrir_puntos"] = False

        codigo_est = st.session_state["selected_code"]

        p1, p2, p3 = st.columns(3)
        with p1:
            cat = st.selectbox(
                "Categoría",
                CATEGORIAS,
                key=f"puntos_categoria__{codigo_est}"
            )
        with p2:
            puntos = st.number_input(
                "Puntos (+/-)",
                step=1, value=1, min_value=-10, max_value=10,
                key=f"puntos_valor__{codigo_est}"
            )
        with p3:
            accion = st.radio(
                "Acción rápida",
                ["Ninguna", "+1", "+5", "-1", "-5"],
                index=0, horizontal=True,
                key=f"puntos_rapidos__{codigo_est}"
            )
            if accion != "Ninguna":
                puntos = int(accion.replace("+","")) if "+" in accion else -int(accion.replace("-",""))
                puntos = max(-10, min(10, puntos))

        if st.button("Actualizar puntos", key=f"btn_actualizar_puntos__{codigo_est}"):
            df.loc[df["Código"].astype(str) == str(codigo_est), cat] += int(puntos)
            df["Total"] = df[CATEGORIAS].sum(axis=1)
            guardar_csv_seguro(df, FILE)
            st.success(f"✅ {puntos:+} puntos añadidos a **{estudiante_label}** en **{cat}**.")
            st.rerun()

# =======================================================
# Tabla y gráficas
# =======================================================
st.subheader("📊 Tabla de puntos")
frat_sel = st.selectbox("Filtrar por fraternidad", ["Todas"] + FRATERNIDADES, key="filtro_frat")
df_filtrado = df if frat_sel == "Todas" else df[df["Fraternidad"] == frat_sel]

# 👉 Aquí agregamos el total de la fraternidad
if frat_sel != "Todas":
    total_frat = df_filtrado["Total"].sum()
    st.info(f"🏠 **Total de puntos de {frat_sel}: {total_frat}**")

st.dataframe(df_filtrado, use_container_width=True)

g1, g2 = st.columns(2)
# Gráfico alumno
if estudiante_label:
    with g1:
        st.subheader(f"📈 Perfil de {estudiante_label}")
        vals = df.loc[df["Código"].astype(str) == st.session_state["selected_code"], CATEGORIAS].iloc[0]
        fig, ax = plt.subplots()
        vals.plot(kind="bar", ax=ax, color="skyblue")
        ax.set_title(f"Puntos por categoría - {estudiante_label}")
        ax.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig)

# Gráfico fraternidad
if frat_sel != "Todas":
    with g2:
        st.subheader(f"🏠 Fraternidad: {frat_sel}")
        tot = df_filtrado[CATEGORIAS].sum()
        fig2, ax2 = plt.subplots()
        tot.plot(kind="bar", ax=ax2, color="orange")
        ax2.set_title(f"Puntos acumulados - {frat_sel}")
        ax2.set_ylabel("Puntos")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig2)
