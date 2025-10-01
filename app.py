# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from supabase import create_client, Client

# =========================
# ⚙️ Configuración general
# =========================
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

# Evitar recargas innecesarias al cambiar widgets
if "initialized" not in st.session_state:
    st.session_state.initialized = True

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
# 🔑 Autenticación Supabase
# =========================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# =========================
# 📌 Utilidades de caché
# =========================
def clear_all_caches():
    """Limpia todas las cachés de datos tras operaciones de escritura."""
    st.cache_data.clear()

# =========================
# 📌 Obtener rol desde profesores
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
        row = conn.execute(query, {"email": email}).fetchone()
        return row

# Inicialización de variables de contexto
profesor_id = rol = fraternidad_id = colegio_id = None
nombre_completo = asignatura = area = grados = None

# =========================
# 📌 Login
# =========================
if "user" not in st.session_state:
    st.sidebar.title("Acceso profesores")
    email = st.sidebar.text_input("Correo", key="email")
    password = st.sidebar.text_input("Contraseña", type="password", key="password")

    if st.sidebar.button("Iniciar sesión", use_container_width=True):
        try:
            auth_resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state["user"] = auth_resp.user
            st.success(f"✅ Bienvenido {email}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")
    st.stop()
else:
    st.sidebar.write(f"Conectado como **{st.session_state['user'].email}**")

    datos = get_profesor(st.session_state["user"].email)
    if datos:
        profesor_id, rol, fraternidad_id, colegio_id, nombre_completo, asignatura, area, grados = datos
        st.sidebar.markdown("### 👨‍🏫 Perfil del profesor")
        st.sidebar.write(f"**Nombre:** {nombre_completo}")
        st.sidebar.write(f"**Rol:** {rol}")
        st.sidebar.write(f"**Asignatura:** {asignatura or '-'}")
        st.sidebar.write(f"**Área:** {area or '-'}")
        st.sidebar.write(f"**Grados:** {grados or '-'}")
    else:
        st.error("❌ No tienes un rol asignado en este colegio")
        st.stop()

    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        try:
            supabase.auth.sign_out()
        finally:
            st.session_state.pop("user", None)
            # También limpiamos selección de estudiante
            st.session_state.pop("estudiante_sel_id", None)
            st.rerun()

# =========================
# 📂 Funciones DB
# =========================
@st.cache_data(ttl=60)
def leer_resumen_estudiantes(colegio_id: int) -> pd.DataFrame:
    """Vista o tabla resumen que trae por estudiante el total por valor (si existe)
       y metadatos (código, nombre, apellidos, fraternidad, grado, etc.)."""
    q = text("SELECT * FROM resumen_puntos_estudiantes WHERE colegio_id = :cid")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": colegio_id})
    # Normalizamos nombres de columnas
    df.columns = df.columns.str.lower()
    # FIX: Asegurar columnas esperadas
    esperadas = {"estudiante_id", "codigo", "nombre", "apellidos", "fraternidad", "grado", "valor", "puntos"}
    faltantes = esperadas - set(df.columns)
    for c in faltantes:
        df[c] = pd.Series(dtype="object") if c not in {"puntos"} else 0
    # FIX: puntos siempre numérico
    df["puntos"] = pd.to_numeric(df["puntos"], errors="coerce").fillna(0).astype(int)
    return df

@st.cache_data(ttl=60)
def leer_historial_puntos(estudiante_id: int, colegio_id: int) -> pd.DataFrame:
    q = text("""
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
        df = pd.read_sql(q, conn, params={"eid": estudiante_id, "cid": colegio_id})
    return df

@st.cache_data(ttl=60)
def leer_valores(colegio_id: int) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM valores WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": colegio_id})
    return df

@st.cache_data(ttl=60)
def leer_fraternidades(colegio_id: int) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM fraternidades WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": colegio_id})
    return df

def actualizar_estudiante_full(estudiante_id, codigo, nombre, apellidos, grado, fraternidad_id):
    # FIX: Transacción atómica + invalidación de caché
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE estudiantes
            SET codigo=:codigo, nombre=:nombre, apellidos=:apellidos, grado=:grado, fraternidad_id=:frat
            WHERE id=:id
        """), {
            "codigo": codigo.strip(),
            "nombre": nombre.strip(),
            "apellidos": apellidos.strip(),
            "grado": grado.strip(),
            "frat": fraternidad_id,
            "id": estudiante_id
        })
    clear_all_caches()

def actualizar_puntos(estudiante_id, valor_nombre, delta, profesor_id=None):
    # FIX: Validaciones y transacción
    if delta == 0:
        st.info("ℹ️ No se registran movimientos por 0 puntos.")
        return
    with engine.begin() as conn:
        valor_q = conn.execute(
            text("SELECT id FROM valores WHERE nombre = :valor AND colegio_id = :colegio"),
            {"valor": valor_nombre, "colegio": colegio_id}
        ).fetchone()
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
            "cantidad": int(delta),
            "profesor_id": profesor_id
        })
    clear_all_caches()

# =========================
# 🏆 App principal
# =========================
st.title("🏆 Sistema de Puntos Hogwarts")

# Datos base
df = leer_resumen_estudiantes(colegio_id)

# 📊 Estadísticas
st.header("📊 Estadísticas generales del colegio")
stats = None
@st.cache_data(ttl=60)
def leer_estadisticas_fraternidades(colegio_id: int) -> pd.DataFrame:
    q = text("""
        SELECT f.nombre as fraternidad, COALESCE(SUM(p.cantidad),0) as total_puntos
        FROM fraternidades f
        JOIN estudiantes e ON e.fraternidad_id = f.id AND e.colegio_id = :cid
        LEFT JOIN puntos p ON e.id = p.estudiante_id
        GROUP BY f.nombre
        ORDER BY total_puntos DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": colegio_id})
    # FIX: garantizar entero
    df["total_puntos"] = pd.to_numeric(df["total_puntos"], errors="coerce").fillna(0).astype(int)
    return df

stats = leer_estadisticas_fraternidades(colegio_id)
if not stats.empty:
    st.dataframe(stats, use_container_width=True)
    fig, ax = plt.subplots(figsize=(6,3))
    # (Matplotlib simple, sin estilos fijos)
    stats.plot(kind="bar", x="fraternidad", y="total_puntos", ax=ax, legend=False)
    ax.set_ylabel("Puntos")
    ax.set_title("🏆 Comparativa de fraternidades")
    st.pyplot(fig)
else:
    st.info("ℹ️ No hay puntos registrados todavía.")

# =======================================================
# 🔎 Buscador simple (por código / nombre / apellidos)
# =======================================================
with st.expander("🔎 Búsqueda rápida por texto", expanded=False):
    q_text = st.text_input("Buscar (código, nombre o apellidos):", "")
    if q_text.strip():
        mask = (
            df["codigo"].fillna("").str.contains(q_text, case=False, na=False) |
            df["nombre"].fillna("").str.contains(q_text, case=False, na=False) |
            df["apellidos"].fillna("").str.contains(q_text, case=False, na=False)
        )
        resultados = (df[mask]
                      .drop_duplicates(subset=["estudiante_id"])
                      .loc[:, ["codigo", "nombre", "apellidos", "fraternidad", "grado"]]
                     )
        st.dataframe(resultados, use_container_width=True)

# =======================================================
# 🎓 Buscador jerárquico
# =======================================================
st.header("🎓 Buscar estudiante por grado y sección")
grados_unicos = df["grado"].dropna().astype(str).unique().tolist()

# FIX: Mantener parsing robusto: grado como '6A', '7B', etc.
def partir_grado(g: str):
    g = g.strip()
    if len(g) >= 2 and g[:-1].isdigit() and g[-1:].isalpha():
        return g[:-1], g[-1:].upper()
    return None, None

grados_numeros = sorted({partir_grado(g)[0] for g in grados_unicos if partir_grado(g)[0]})
grado_sel = st.selectbox("Selecciona el grado:", [""] + grados_numeros, index=0)

estudiante_seleccionado = None

if grado_sel != "":
    secciones = sorted({partir_grado(g)[1] for g in grados_unicos if partir_grado(g)[0] == grado_sel})
    seccion_sel = st.selectbox("Selecciona la sección:", [""] + secciones, index=0)

    if seccion_sel != "":
        grado_completo = f"{grado_sel}{seccion_sel}"
        df_filtrado = (df[df["grado"] == grado_completo]
                       .drop_duplicates(subset=["estudiante_id"])
                       .sort_values(["apellidos", "nombre"], na_position="last"))
        if df_filtrado.empty:
            st.warning("⚠️ No hay estudiantes en este grado y sección.")
        else:
            st.subheader(f"👥 Estudiantes de {grado_completo}")
            st.dataframe(df_filtrado[["codigo", "nombre", "apellidos", "fraternidad", "grado"]],
                         use_container_width=True, hide_index=True)

            # FIX: selector por "mostrar" (nombre + código) para evitar ambigüedades
            df_filtrado = df_filtrado.assign(
                mostrar=df_filtrado["apellidos"].fillna("") + ", " +
                        df_filtrado["nombre"].fillna("") + " — " +
                        df_filtrado["codigo"].fillna("")
            )
            opciones = [""] + df_filtrado["mostrar"].tolist()
            sel = st.selectbox("Selecciona un estudiante:", opciones, index=0, key="select_estudiante")

            if sel != "":
                est_row = df_filtrado[df_filtrado["mostrar"] == sel].iloc[0]
                estudiante_seleccionado = est_row
                # FIX: guardar ID en sesión para persistir selección cuando se re-renderiza
                st.session_state["estudiante_sel_id"] = int(est_row["estudiante_id"])

# Si hay un estudiante en sesión pero no se mostró el selector (por ejemplo, tras rerun),
# reconstituimos su fila desde DB de respaldo (df).
if estudiante_seleccionado is None and st.session_state.get("estudiante_sel_id") is not None:
    est_id = st.session_state["estudiante_sel_id"]
    cand = df[df["estudiante_id"] == est_id]
    if not cand.empty:
        estudiante_seleccionado = cand.drop_duplicates(subset=["estudiante_id"]).iloc[0]

# =======================================================
# 📌 Detalles del estudiante
# =======================================================
if estudiante_seleccionado is not None:
    r = estudiante_seleccionado

    st.subheader(f"👤 {r['nombre']} {r['apellidos']} | 🎓 {r['grado']} | 🏠 {r['fraternidad']}")
    valores_df = leer_valores(colegio_id)

    # FIX (KeyError groupby): aseguramos universo de valores y reindexamos
    df_alumno = df[df["estudiante_id"] == r["estudiante_id"]][["valor", "puntos"]].copy()
    df_alumno["puntos"] = pd.to_numeric(df_alumno["puntos"], errors="coerce").fillna(0)

    # Base con todas las categorías configuradas en el colegio
    base = pd.DataFrame({"valor": valores_df["nombre"].tolist()})
    totales = (base.merge(df_alumno, on="valor", how="left")
                    .fillna({"puntos": 0}))
    totales.rename(columns={"valor": "valor_nombre"}, inplace=True)

    # Agrupamos sin riesgo: columna existe y es completa
    serie_totales = (totales.groupby("valor_nombre", dropna=False)["puntos"]
                            .sum()
                            .astype(int))
    total_general = int(serie_totales.sum())

    st.markdown(f"### 🧮 Total de puntos: **{total_general}**")
    tabla = serie_totales.reset_index().rename(columns={"valor_nombre": "Valor", "puntos": "Puntos"})
    st.dataframe(tabla, use_container_width=True, hide_index=True)

    fig, ax = plt.subplots(figsize=(6,3))
    tabla.plot(kind="bar", x="Valor", y="Puntos", ax=ax, legend=False)
    ax.set_ylabel("Puntos")
    ax.set_title("Distribución de valores")
    st.pyplot(fig)

    # ========= Asignar puntos =========
    st.subheader("➕ Asignar puntos")
    categoria = st.selectbox("Categoría", valores_df["nombre"].tolist(), key="categoria_asignar")
    delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_puntos")

    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("Actualizar puntos", use_container_width=True):
            actualizar_puntos(int(r["estudiante_id"]), str(categoria), int(delta), profesor_id)
            st.success(f"{delta:+} puntos añadidos en {categoria}.")
            st.rerun()
    with col_b:
        if st.button("Recalcular vista", use_container_width=True):
            clear_all_caches()
            st.rerun()

    # ========= Edición del estudiante (solo director) =========
    if rol == "director":
        st.header("✏️ Editar estudiante")
        frats = leer_fraternidades(colegio_id)

        # FIX: el formulario se rellena SIEMPRE con el estudiante actual
        with st.form("editar_estudiante", clear_on_submit=False):
            codigo_edit = st.text_input("Código", value=r["codigo"] or "")
            nombre_edit = st.text_input("Nombre", value=r["nombre"] or "")
            apellidos_edit = st.text_input("Apellidos", value=r["apellidos"] or "")
            grado_edit = st.text_input("Grado", value=r["grado"] or "")

            frat_nombres = frats["nombre"].tolist()
            idx_frat = frat_nombres.index(r["fraternidad"]) if r["fraternidad"] in frat_nombres else 0
            fraternidad_edit = st.selectbox("Fraternidad", frat_nombres, index=idx_frat)

            submit = st.form_submit_button("💾 Guardar cambios")
            if submit:
                frat_id = int(frats.loc[frats["nombre"] == fraternidad_edit, "id"].iloc[0])
                actualizar_estudiante_full(int(r["estudiante_id"]), codigo_edit, nombre_edit, apellidos_edit, grado_edit, frat_id)
                st.success("✅ Estudiante actualizado correctamente.")
                st.rerun()

        st.subheader("📋 Historial de puntos")
        historial = leer_historial_puntos(int(r["estudiante_id"]), colegio_id)
        st.dataframe(historial, use_container_width=True, hide_index=True)

# =======================================================
# 👨‍🏫 Gestión de profesores (solo director)
# =======================================================
if rol == "director":
    st.header("👨‍🏫 Gestión de profesores")

    with st.form("agregar_profesor"):
        email_prof = st.text_input("Email del profesor").strip()
        nombres_prof = st.text_input("Nombres").strip()
        apellidos_prof = st.text_input("Apellidos").strip()
        rol_prof = st.selectbox("Rol", ["profesor", "director"])
        asignatura_prof = st.text_input("Asignatura").strip()
        area_prof = st.text_input("Área").strip()
        grados_prof = st.text_input("Grados (ej: 6A,7B)").strip()

        frats = leer_fraternidades(colegio_id)
        fraternidad_prof = st.selectbox("Fraternidad", frats["nombre"].tolist())

        submit_prof = st.form_submit_button("➕ Agregar profesor")

        if submit_prof:
            if not email_prof or not nombres_prof or not apellidos_prof:
                st.error("❌ Debes llenar al menos email, nombres y apellidos.")
            else:
                # ✅ Obtener el UUID de la fraternidad como string
                frat_id = str(frats.loc[frats["nombre"] == fraternidad_prof, "id"].iloc[0])
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO profesores 
                            (email, nombres, apellidos, rol, asignatura, area, grados, fraternidad_id, colegio_id)
                            VALUES (:email, :nombres, :apellidos, :rol, :asignatura, :area, :grados, :frat, :colegio)
                        """), {
                            "email": email_prof,
                            "nombres": nombres_prof,
                            "apellidos": apellidos_prof,
                            "rol": rol_prof,
                            "asignatura": asignatura_prof or None,
                            "area": area_prof or None,
                            "grados": grados_prof or None,
                            "frat": frat_id,             # 👈 ahora UUID válido
                            "colegio": str(colegio_id)   # 👈 también casteado a string
                        })
                    # Crear también el usuario en Supabase
                    try:
                        supabase.auth.admin.create_user({
                            "email": email_prof,
                            "password": "temporal123",
                            "email_confirm": True
                        })
                        st.success("✅ Profesor agregado y usuario creado en Supabase (contraseña: temporal123)")
                    except Exception as e:
                        st.warning(f"⚠️ Profesor creado en DB, pero error en Supabase: {e}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al crear profesor en la base de datos: {e}")


    # 🔑 Resetear contraseña (solo profesores del mismo colegio)
    st.subheader("🔑 Resetear contraseña de profesor")
    email_reset = st.text_input("Email del profesor a resetear").strip()
    if st.button("Resetear contraseña"):
        if not email_reset:
            st.warning("⚠️ Ingresa un email.")
        else:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT id FROM profesores 
                    WHERE email = :email AND colegio_id = :cid
                """), {"email": email_reset, "cid": colegio_id}).fetchone()

            if not row:
                st.error("❌ Ese profesor no pertenece a tu colegio.")
            else:
                try:
                    supabase.auth.reset_password_email(email_reset)
                    st.success(f"🔑 Email de reseteo enviado a {email_reset}")
                except Exception as e:
                    st.error(f"❌ Error al enviar email de reseteo: {e}")
