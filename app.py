import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from supabase import create_client, Client

# =========================
# ⚙️ Configuración general
# =========================
st.set_page_config(page_title="Sistema Hogwarts", page_icon="🏆", layout="wide")

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
# 📌 Utilidades
# =========================
def clear_all_caches():
    st.cache_data.clear()

def get_profesor(email):
    with engine.connect() as conn:
        query = text("""
            SELECT 
                id, rol, fraternidad_id, colegio_id, 
                (nombres || ' ' || apellidos) as nombre_completo,
                asignatura, area, grados
            FROM profesores
            WHERE email = :email
        """)
        row = conn.execute(query, {"email": email}).fetchone()
        return row

# =========================
# 📌 Login
# =========================
if "user" not in st.session_state:
    st.sidebar.title("Acceso profesores")
    email = st.sidebar.text_input("Correo")
    password = st.sidebar.text_input("Contraseña", type="password")

    if st.sidebar.button("Iniciar sesión", use_container_width=True):
        try:
            auth_resp = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            st.session_state["user"] = auth_resp.user
            st.query_params["refresh"] = "1"
            st.success(f"✅ Bienvenido {email}")
            st.rerun()   # 👈 Redibuja la app con el usuario activo
        except Exception as e:
            st.error(f"❌ Error: {e}")

    # 👇 Solo se detiene si NO hay usuario aún
    st.stop()
    
# Ya logueado
st.sidebar.write(f"Conectado como **{st.session_state['user'].email}**")

datos = get_profesor(st.session_state["user"].email)
if not datos:
    st.error("❌ No tienes un rol asignado en este colegio")
    st.stop()

profesor_id, rol, fraternidad_id, colegio_id, nombre_completo, asignatura, area, grados = datos
st.session_state["profesor_id"] = profesor_id
st.session_state["colegio_id"] = colegio_id   # 👈 GUARDA colegio_id en sesión

# Cerrar sesión
if st.sidebar.button("Cerrar sesión", use_container_width=True):
    try:
        supabase.auth.sign_out()
    finally:
        st.session_state.clear()
        st.query_params["logout"] = "1"
        st.rerun()   # 👈 Limpia y reinicia la app sin usuario


# =========================
# 📂 Funciones DB (cache)
# =========================
@st.cache_data(ttl=60)
def leer_resumen_estudiantes(colegio_id: str) -> pd.DataFrame:
    q = text("SELECT * FROM resumen_puntos_estudiantes WHERE colegio_id = :cid")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": str(colegio_id)})
    df.columns = df.columns.str.lower()
    if "puntos" in df.columns:
        df["puntos"] = pd.to_numeric(df["puntos"], errors="coerce").fillna(0).astype(int)
    return df

@st.cache_data(ttl=60)
def leer_valores(colegio_id: str) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM valores WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        return pd.read_sql(q, conn, params={"cid": str(colegio_id)})

@st.cache_data(ttl=60)
def leer_fraternidades(colegio_id: str) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM fraternidades WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        return pd.read_sql(q, conn, params={"cid": str(colegio_id)})

# =========================
# ✏️ CRUD estudiante
# =========================
def actualizar_estudiante_full(estudiante_id, codigo, nombre, apellidos, grado, fraternidad_id):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE estudiantes
            SET codigo=:codigo, nombre=:nombre, apellidos=:apellidos, grado=:grado, fraternidad_id=:frat
            WHERE id=:id
        """), {
            "codigo": (codigo or "").strip(),
            "nombre": (nombre or "").strip(),
            "apellidos": (apellidos or "").strip(),
            "grado": (grado or "").strip(),
            "frat": str(fraternidad_id) if fraternidad_id else None,
            "id": str(estudiante_id)
        })
    leer_resumen_estudiantes.clear()

def insertar_estudiante(codigo, nombre, apellidos, grado, fraternidad_id, colegio_id):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO estudiantes (codigo, nombre, apellidos, grado, fraternidad_id, colegio_id)
            VALUES (:codigo, :nombre, :apellidos, :grado, :frat, :colegio)
        """), {
            "codigo": (codigo or "").strip(),
            "nombre": nombre.strip(),
            "apellidos": apellidos.strip(),
            "grado": grado.strip(),
            "frat": str(fraternidad_id) if fraternidad_id else None,
            "colegio": str(colegio_id)
        })
    leer_resumen_estudiantes.clear()

# =========================
# 🧮 Puntos
# =========================
def actualizar_puntos(estudiante_id, valor_nombre, delta, profesor_id=None):
    if delta == 0:
        return

    prof_id = profesor_id or st.session_state.get("profesor_id")
    if not prof_id:
        return

    with engine.begin() as conn:
        valor_q = conn.execute(
            text("SELECT id FROM valores WHERE nombre=:valor AND colegio_id=:colegio"),
            {"valor": valor_nombre, "colegio": str(colegio_id)}
        ).fetchone()
        if not valor_q:
            return
        valor_id = str(valor_q[0])

        conn.execute(text("""
            INSERT INTO puntos (estudiante_id, valor_id, cantidad, profesor_id)
            VALUES (:estudiante_id, :valor_id, :cantidad, :profesor_id)
        """), {
            "estudiante_id": str(estudiante_id),
            "valor_id": valor_id,
            "cantidad": int(delta),
            "profesor_id": str(prof_id)
        })
    leer_resumen_estudiantes.clear()

def asignar_puntos_fraternidad(fraternidad_id, valor_nombre, delta, profesor_id):
    if delta == 0:
        return
    with engine.begin() as conn:
        valor_q = conn.execute(
            text("SELECT id FROM valores WHERE nombre=:valor AND colegio_id=:colegio"),
            {"valor": valor_nombre, "colegio": str(colegio_id)}
        ).fetchone()
        if not valor_q:
            return
        valor_id = str(valor_q[0])

        estudiantes = conn.execute(
            text("SELECT id FROM estudiantes WHERE fraternidad_id=:fid AND colegio_id=:cid"),
            {"fid": str(fraternidad_id), "cid": str(colegio_id)}
        ).fetchall()

        for (est_id,) in estudiantes:
            conn.execute(text("""
                INSERT INTO puntos (estudiante_id, valor_id, cantidad, profesor_id)
                VALUES (:eid, :valor_id, :cantidad, :profesor_id)
            """), {
                "eid": str(est_id),
                "valor_id": valor_id,
                "cantidad": int(delta),
                "profesor_id": str(profesor_id)
            })
    leer_resumen_estudiantes.clear()


# =========================
# 🏆 App principal (tabs)
# =========================
st.title("🏆 Sistema de Puntos Hogwarts")
tabs = st.tabs(["📊 Estadísticas", "🎓 Estudiantes", "🏠 Fraternidades", "👨‍🏫 Profesores"])

# ---- TAB 1: Estadísticas ----
with tabs[0]:
    st.header("📊 Estadísticas generales del colegio")
    q = text("""
        SELECT f.nombre as fraternidad, COALESCE(SUM(p.cantidad),0) as total_puntos
        FROM fraternidades f
        JOIN estudiantes e ON e.fraternidad_id = f.id AND e.colegio_id = :cid
        LEFT JOIN puntos p ON e.id = p.estudiante_id
        GROUP BY f.nombre
        ORDER BY total_puntos DESC
    """)
    with engine.connect() as conn:
        stats = pd.read_sql(q, conn, params={"cid": colegio_id})

    if not stats.empty:
        st.dataframe(stats, use_container_width=True)
        fig, ax = plt.subplots(figsize=(6,3))
        stats.plot(kind="bar", x="fraternidad", y="total_puntos", ax=ax, legend=False)
        ax.set_ylabel("Puntos")
        ax.set_title("🏆 Comparativa de fraternidades")
        st.pyplot(fig)
    else:
        st.info("ℹ️ No hay puntos registrados todavía.")


# ---- TAB 2: Estudiantes ----
with tabs[1]:
    st.header("🎓 Buscar y gestionar estudiantes")
    df = leer_resumen_estudiantes(colegio_id)

    estudiante_seleccionado = None

    # ========================
    # 🔎 Buscador INDIVIDUAL
    # ========================
    st.subheader("🔎 Búsqueda individual (detalle completo)")
    opciones_individual = df.drop_duplicates(subset=["estudiante_id"]).apply(
        lambda r: f"{r['codigo'] or ''} | {r['nombre']} {r['apellidos']} | {r['grado']} | {r['fraternidad'] or '-'}",
        axis=1
    ).tolist()

    seleccion_individual = st.selectbox("Elige un estudiante:", [""] + opciones_individual, key="busqueda_individual")

    if seleccion_individual and seleccion_individual != "":
        idx = opciones_individual.index(seleccion_individual)
        est = df.drop_duplicates(subset=["estudiante_id"]).iloc[idx]
        estudiante_seleccionado = est
        st.session_state["estudiante_sel_id"] = str(est["estudiante_id"])

    # ========================
    # 🔎 Búsqueda por texto (multi)
    # ========================
    st.subheader("🔎 Búsqueda por estudiantes (múltiple)")
    opciones_multi = df.drop_duplicates(subset=["estudiante_id"]).apply(
        lambda r: f"{r['codigo'] or ''} | {r['nombre']} {r['apellidos']} | {r['grado']} | {r['fraternidad'] or '-'}",
        axis=1
    ).tolist()

    seleccion_multi = st.multiselect("Escribe y selecciona varios:", opciones_multi, key="busqueda_texto_multi")

    ids_texto = []
    if seleccion_multi:
        for sel in seleccion_multi:
            idx = opciones_multi.index(sel)
            est = df.drop_duplicates(subset=["estudiante_id"]).iloc[idx]
            ids_texto.append(str(est["estudiante_id"]))

    if ids_texto:
        st.success(f"✅ {len(ids_texto)} estudiante(s) seleccionados")
        valores_df = leer_valores(colegio_id)
        st.subheader("➕ Asignar puntos a seleccionados (texto)")
        categoria = st.selectbox("Categoría", valores_df["nombre"].tolist(), key="categoria_masiva_texto")
        delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_masiva_texto")

        if st.button("Asignar puntos a seleccionados (texto)", type="primary", use_container_width=True):
            for est_id in ids_texto:
                actualizar_puntos(str(est_id), str(categoria), int(delta), profesor_id)
            st.success(f"✅ {delta:+} puntos asignados a {len(ids_texto)} estudiantes.")
            st.rerun()

    # ========================
    # 🎓 Búsqueda jerárquica
    # ========================
    st.subheader("🎓 Buscar por grado y sección (múltiple)")
    grados_unicos = df["grado"].dropna().astype(str).unique().tolist()

    def partir_grado(g: str):
        g = g.strip()
        if len(g) >= 2 and g[:-1].isdigit() and g[-1:].isalpha():
            return g[:-1], g[-1:].upper()
        return None, None

    grados_numeros = sorted({partir_grado(g)[0] for g in grados_unicos if partir_grado(g)[0]})
    grado_sel = st.selectbox("Selecciona el grado:", [""] + grados_numeros, index=0, key="grado_sel")

    if grado_sel != "":
        secciones = sorted({partir_grado(g)[1] for g in grados_unicos if partir_grado(g)[0] == grado_sel})
        seccion_sel = st.selectbox("Selecciona la sección:", [""] + secciones, index=0, key="seccion_sel")

        if seccion_sel != "":
            grado_completo = f"{grado_sel}{seccion_sel}"
            # Agrupar por estudiante y sumar puntos
            df_filtrado = (df[df["grado"] == grado_completo]
                           .groupby(["estudiante_id","codigo","nombre","apellidos","fraternidad","grado"], as_index=False)
                           .agg({"puntos": "sum"})
                           .sort_values(["apellidos","nombre"], na_position="last"))


            if df_filtrado.empty:
                st.warning("⚠️ No hay estudiantes en este grado y sección.")
            else:
                df_filtrado = df_filtrado.reset_index(drop=True)
                df_filtrado["Seleccionar"] = False

                df_sel = st.data_editor(
                    df_filtrado[["estudiante_id","codigo","nombre","apellidos","fraternidad","grado","puntos","Seleccionar"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Seleccionar": st.column_config.CheckboxColumn(required=True),
                        "estudiante_id": None
                    },
                    key="tabla_jerarquica"
                )

                seleccionados = df_sel[df_sel["Seleccionar"] == True]
                ids_seleccionados = seleccionados["estudiante_id"].astype(str).tolist()

                if ids_seleccionados:
                    st.success(f"✅ {len(ids_seleccionados)} estudiante(s) seleccionado(s) en jerárquico")
                    valores_df = leer_valores(colegio_id)
                    st.subheader("➕ Asignar puntos a seleccionados (jerárquico)")
                    categoria = st.selectbox("Categoría", valores_df["nombre"].tolist(), key="categoria_masiva_jerq")
                    delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_masiva_jerq")

                    if st.button("Asignar puntos (jerárquico)", type="primary", use_container_width=True):
                        for est_id in ids_seleccionados:
                            actualizar_puntos(str(est_id), str(categoria), int(delta), profesor_id)
                        st.success(f"✅ {delta:+} puntos asignados a {len(ids_seleccionados)} estudiante(s).")
                        st.rerun()

                    # si hay uno solo → mostrar detalle abajo
                    if len(ids_seleccionados) == 1:
                        est_row = df_filtrado.loc[seleccionados.index[0]]
                        estudiante_seleccionado = est_row
                        st.session_state["estudiante_sel_id"] = str(est_row["estudiante_id"])

    # ========================
    # Detalle del estudiante (INDIVIDUAL o jerárquico 1)
    # ========================
    if estudiante_seleccionado is None and st.session_state.get("estudiante_sel_id") is not None:
        est_id = st.session_state["estudiante_sel_id"]
        cand = df[df["estudiante_id"] == est_id]
        if not cand.empty:
            estudiante_seleccionado = cand.drop_duplicates(subset=["estudiante_id"]).iloc[0]

    if estudiante_seleccionado is not None:
        r = estudiante_seleccionado
        st.markdown(f"## 👤 {r['nombre']} {r['apellidos']} | 🎓 {r['grado']} | 🏠 {r['fraternidad']}")

        # 👉 Si el rol es director, permitir edición
        if rol == "director":
            st.subheader("✏️ Editar datos del estudiante")
            frats_df = leer_fraternidades(colegio_id)
            with st.form("editar_estudiante"):
                codigo_n = st.text_input("Código", value=r["codigo"] or "")
                nombre_n = st.text_input("Nombre", value=r["nombre"] or "")
                apellidos_n = st.text_input("Apellidos", value=r["apellidos"] or "")
                grado_n = st.text_input("Grado", value=r["grado"] or "")
                frat_n = st.selectbox("Fraternidad", frats_df["nombre"].tolist(), 
                                      index=frats_df["nombre"].tolist().index(r["fraternidad"]) if r["fraternidad"] in frats_df["nombre"].tolist() else 0)
                submit_edit = st.form_submit_button("Actualizar estudiante")
                if submit_edit:
                    frat_id = str(frats_df.loc[frats_df["nombre"] == frat_n, "id"].iloc[0]) if not frats_df.empty else None

                    actualizar_estudiante_full(r["estudiante_id"], codigo_n, nombre_n, apellidos_n, grado_n, frat_id)
                    st.success("✅ Estudiante actualizado.")
                    st.rerun()

        # 👉 Estadísticas y puntos
        valores_df = leer_valores(colegio_id)
        df_alumno = df[df["estudiante_id"] == r["estudiante_id"]][["valor", "puntos"]].copy()
        df_alumno["puntos"] = pd.to_numeric(df_alumno["puntos"], errors="coerce").fillna(0)
        base = pd.DataFrame({"valor": valores_df["nombre"].tolist()}) if not valores_df.empty else pd.DataFrame({"valor": []})
        totales = (base.merge(df_alumno, on="valor", how="left").fillna({"puntos": 0}))
        totales.rename(columns={"valor": "valor_nombre"}, inplace=True)
        serie_totales = (totales.groupby("valor_nombre", dropna=False)["puntos"].sum().astype(int))
        total_general = int(serie_totales.sum()) if not serie_totales.empty else 0

        st.markdown(f"### 🧮 Total de puntos: **{total_general}**")
        tabla = serie_totales.reset_index().rename(columns={"valor_nombre": "Valor", "puntos": "Puntos"})
        st.dataframe(tabla, use_container_width=True, hide_index=True)

        if not tabla.empty:
            fig, ax = plt.subplots(figsize=(6,3))
            tabla.plot(kind="bar", x="Valor", y="Puntos", ax=ax, legend=False)
            ax.set_ylabel("Puntos")
            ax.set_title("Distribución de valores")
            st.pyplot(fig)

        st.subheader("➕ Asignar puntos al estudiante")
        if valores_df.empty:
            st.info("No hay valores configurados en el colegio.")
        else:
            categoria = st.selectbox("Categoría", valores_df["nombre"].tolist(), key="categoria_asignar")
            delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_puntos")
            if st.button("Actualizar puntos", use_container_width=True):
                actualizar_puntos(str(r["estudiante_id"]), str(categoria), int(delta), profesor_id)
                st.success(f"{delta:+} puntos añadidos en {categoria}.")
                st.rerun()

    # ========================
    # Agregar estudiante (solo director)
    # ========================
    if rol == "director":
        st.subheader("➕ Agregar nuevo estudiante")

        frats_df = leer_fraternidades(colegio_id)

        with st.form("agregar_estudiante"):
            codigo_n = st.text_input("Código")
            nombre_n = st.text_input("Nombre")
            apellidos_n = st.text_input("Apellidos")
            grado_n = st.text_input("Grado (ej: 6A)")
            fraternidad_n = st.selectbox("Fraternidad", 
                                         frats_df["nombre"].tolist() if not frats_df.empty else [])

            submit_new = st.form_submit_button("➕ Agregar estudiante")

            if submit_new:
                if not nombre_n or not apellidos_n or not grado_n:
                    st.error("⚠️ Nombre, apellidos y grado son obligatorios.")
                else:
                    frat_id = str(frats_df.loc[frats_df["nombre"] == fraternidad_n, "id"].iloc[0]) if not frats_df.empty else None


                    try:
                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO estudiantes (codigo, nombre, apellidos, grado, fraternidad_id, colegio_id)
                                VALUES (:codigo, :nombre, :apellidos, :grado, :frat, :colegio)
                            """), {
                                "codigo": (codigo_n or "").strip(),
                                "nombre": nombre_n.strip(),
                                "apellidos": apellidos_n.strip(),
                                "grado": grado_n.strip(),
                                "frat": frat_id,
                                "colegio": str(colegio_id)
                            })
                        clear_all_caches()
                        st.success("✅ Estudiante agregado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al agregar estudiante: {e}")


# ---- TAB 3: Fraternidades ----
with tabs[2]:
    st.header("🏠 Fraternidades")

    frats = leer_fraternidades(colegio_id)
    valores_df = leer_valores(colegio_id)

    if frats.empty:
        st.info("No hay fraternidades configuradas.")
    else:
        # ===================================
        # 🏆 Leaderboard general de fraternidades
        # ===================================
        st.subheader("🏆 Leaderboard de fraternidades")
        q_leader = text("""
            SELECT f.nombre as fraternidad, COALESCE(SUM(p.cantidad),0) as total_puntos
            FROM fraternidades f
            LEFT JOIN estudiantes e ON e.fraternidad_id = f.id
            LEFT JOIN puntos p ON e.id = p.estudiante_id
            WHERE f.colegio_id = :cid
            GROUP BY f.nombre
            ORDER BY total_puntos DESC
        """)
        with engine.connect() as conn:
            df_leader = pd.read_sql(q_leader, conn, params={"cid": colegio_id})

        if not df_leader.empty:
            st.dataframe(df_leader, use_container_width=True, hide_index=True)
            fig, ax = plt.subplots(figsize=(6,3))
            df_leader.plot(kind="bar", x="fraternidad", y="total_puntos", ax=ax, legend=False)
            ax.set_ylabel("Puntos")
            ax.set_title("Ranking de fraternidades")
            st.pyplot(fig)
        else:
            st.info("ℹ️ No hay puntos registrados aún.")

        # ===================================
        # 📊 Estadísticas por fraternidad y valor
        # ===================================
        st.subheader("📊 Estadísticas por fraternidad y valor")
        frat_sel = st.selectbox("Selecciona fraternidad", frats["nombre"].tolist())

        if frat_sel:
            q_valores = text("""
                SELECT v.nombre as valor, COALESCE(SUM(p.cantidad),0) as total_puntos
                FROM valores v
                LEFT JOIN puntos p ON v.id = p.valor_id
                LEFT JOIN estudiantes e ON p.estudiante_id = e.id
                LEFT JOIN fraternidades f ON e.fraternidad_id = f.id
                WHERE v.colegio_id = :cid AND f.nombre = :fname
                GROUP BY v.nombre
                ORDER BY total_puntos DESC
            """)
            with engine.connect() as conn:
                df_valores = pd.read_sql(q_valores, conn, params={"cid": colegio_id, "fname": frat_sel})

            if not df_valores.empty:
                st.dataframe(df_valores, use_container_width=True, hide_index=True)
                fig, ax = plt.subplots(figsize=(6,3))
                df_valores.plot(kind="bar", x="valor", y="total_puntos", ax=ax, legend=False)
                ax.set_ylabel("Puntos")
                ax.set_title(f"Distribución de valores - {frat_sel}")
                st.pyplot(fig)
            else:
                st.warning("⚠️ Esta fraternidad aún no tiene puntos asignados.")

        # ===================================
        # ➕ Asignación masiva (como ya la tenías)
        # ===================================
        st.subheader("➕ Asignar puntos por fraternidad")
        if valores_df.empty:
            st.info("No hay valores configurados.")
        else:
            col1, col2, col3 = st.columns([2,2,1])
            with col1:
                frat_sel2 = st.selectbox("Fraternidad", frats["nombre"].tolist(), key="frat_asignar")
            with col2:
                valor_sel = st.selectbox("Valor", valores_df["nombre"].tolist(), key="valor_asignar")
            with col3:
                delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_asignar")

            if st.button("Asignar puntos a toda la fraternidad", type="primary", use_container_width=True):
                frat_id = str(frats.loc[frats["nombre"] == frat_sel2, "id"].iloc[0])
                asignar_puntos_fraternidad(frat_id, valor_sel, delta, st.session_state["profesor_id"])
                st.success(f"✅ {delta:+} puntos asignados a todos los estudiantes de {frat_sel2}")
                st.balloons()


# ---- TAB 4: Profesores (solo director) ----
with tabs[3]:
    if rol != "director":
        st.warning("⚠️ Solo los directores pueden gestionar profesores.")
    else:
        st.header("👨‍🏫 Gestión de profesores")

        # ===================================
        # ➕ Crear profesor
        # ===================================
        st.subheader("➕ Agregar profesor")
        with st.form("agregar_profesor"):
            email_prof = st.text_input("Email del profesor").strip()
            cedula_prof = st.text_input("Cédula (será la contraseña inicial)").strip()
            nombres_prof = st.text_input("Nombres").strip()
            apellidos_prof = st.text_input("Apellidos").strip()
            rol_prof = st.selectbox("Rol", ["profesor", "director"])
            asignatura_prof = st.text_input("Asignatura").strip()
            area_prof = st.text_input("Área").strip()
            grados_prof = st.text_input("Grados (ej: 6A,7B)").strip()

            frats = leer_fraternidades(colegio_id)
            fraternidad_prof = st.selectbox("Fraternidad", frats["nombre"].tolist() if not frats.empty else [])

            submit_prof = st.form_submit_button("➕ Agregar profesor")

            if submit_prof:
                if not email_prof or not nombres_prof or not apellidos_prof or not cedula_prof:
                    st.error("❌ Debes llenar email, cédula, nombres y apellidos.")
                else:
                    frat_id = str(frats.loc[frats["nombre"] == fraternidad_prof, "id"].iloc[0]) if not frats.empty else None
                    try:
                        user_resp = supabase.auth.admin.create_user({
                            "email": email_prof,
                            "password": cedula_prof,
                            "email_confirm": True
                        })
                        auth_id = str(user_resp.user.id)

                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO profesores 
                                (email, cedula, auth_id, nombres, apellidos, rol, asignatura, area, grados, fraternidad_id, colegio_id)
                                VALUES (:email, :cedula, :auth_id, :nombres, :apellidos, :rol, :asignatura, :area, :grados, :frat, :colegio)
                            """), {
                                "email": email_prof,
                                "cedula": cedula_prof,
                                "auth_id": auth_id,
                                "nombres": nombres_prof,
                                "apellidos": apellidos_prof,
                                "rol": rol_prof,
                                "asignatura": asignatura_prof or None,
                                "area": area_prof or None,
                                "grados": grados_prof or None,
                                "frat": frat_id,
                                "colegio": str(colegio_id)
                            })

                        st.success(f"✅ Profesor agregado. Contraseña inicial = cédula ({cedula_prof}).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear profesor: {e}")

        # ===================================
        # 🔄 Resetear contraseña
        # ===================================
        st.subheader("🔄 Resetear contraseña del profesor (clave = cédula)")
        with st.form("reset_pass_prof"):
            cedula_reset = st.text_input("Cédula del profesor").strip()
            submit_reset = st.form_submit_button("Resetear contraseña")
            if submit_reset:
                if not cedula_reset:
                    st.error("⚠️ Ingresa la cédula.")
                else:
                    try:
                        with engine.begin() as conn:
                            prof = conn.execute(
                                text("SELECT id, email, auth_id, cedula FROM profesores WHERE cedula = :ced AND colegio_id = :cid"),
                                {"ced": cedula_reset, "cid": str(colegio_id)}
                            ).fetchone()

                        if not prof:
                            st.error("❌ No existe un profesor con esa cédula en este colegio.")
                        else:
                            supabase.auth.admin.update_user_by_id(
                                str(prof.auth_id),
                                {"password": str(prof.cedula)}
                            )
                            st.success(
                                f"✅ Contraseña reestablecida. El profesor entra con:\n"
                                f"- **Usuario:** {prof.email}\n- **Contraseña:** {prof.cedula}"
                            )
                    except Exception as e:
                        st.error(f"❌ Error al resetear contraseña: {e}")

        # ===================================
        # ✉️ Enviar Magic Link / OTP
        # ===================================
        st.subheader("✉️ Enviar Magic Link / OTP")
        with st.form("magic_link_form"):
            email_magic = st.text_input("Email del profesor").strip()
            submit_magic = st.form_submit_button("Enviar acceso")
        if submit_magic:
            if not email_magic:
                st.warning("⚠️ Ingresa email del profesor.")
            else:
                try:
                    supabase.auth.sign_in_with_otp({
                        "email": email_magic,
                        "options": {
                            "email_redirect_to": "https://resethogwartz.streamlit.app/"
                        }
                    })
                    st.success(f"✅ Se envió un Magic Link/OTP a {email_magic}. Redirige a la app de reset.")
                except Exception as e:
                    st.error(f"❌ Error al enviar acceso: {e}")

        # ===================================
        # ✏️ Editar profesor existente
        # ===================================
        st.subheader("✏️ Editar profesor existente")

        with st.form("buscar_profesor"):
            cedula_buscar = st.text_input("Cédula del profesor a buscar").strip()
            submit_buscar = st.form_submit_button("Buscar profesor")

        profesor_edit = None
        if submit_buscar and cedula_buscar:
            with engine.connect() as conn:
                profesor_edit = conn.execute(
                    text("""
                        SELECT id, email, cedula, nombres, apellidos, rol, asignatura, area, grados, fraternidad_id
                        FROM profesores
                        WHERE cedula = :ced AND colegio_id = :cid
                    """),
                    {"ced": cedula_buscar, "cid": str(colegio_id)}
                ).fetchone()

            if not profesor_edit:
                st.error("❌ No se encontró profesor con esa cédula en este colegio.")
            else:
                st.success(f"✅ Profesor encontrado: {profesor_edit.nombres} {profesor_edit.apellidos}")

        if profesor_edit:
            frats_df = leer_fraternidades(colegio_id)

            with st.form("editar_profesor"):
                email_n = st.text_input("Email", value=profesor_edit.email)
                cedula_n = st.text_input("Cédula", value=profesor_edit.cedula)
                nombres_n = st.text_input("Nombres", value=profesor_edit.nombres)
                apellidos_n = st.text_input("Apellidos", value=profesor_edit.apellidos)
                rol_n = st.selectbox("Rol", ["profesor", "director"], index=["profesor","director"].index(profesor_edit.rol))
                asignatura_n = st.text_input("Asignatura", value=profesor_edit.asignatura or "")
                area_n = st.text_input("Área", value=profesor_edit.area or "")
                grados_n = st.text_input("Grados (ej: 6A,7B)", value=profesor_edit.grados or "")

                fraternidad_n = st.selectbox(
                    "Fraternidad", 
                    frats_df["nombre"].tolist() if not frats_df.empty else [],
                    index=frats_df["id"].astype(str).tolist().index(str(profesor_edit.fraternidad_id)) if profesor_edit.fraternidad_id and str(profesor_edit.fraternidad_id) in frats_df["id"].astype(str).tolist() else 0
                )

                submit_edit_prof = st.form_submit_button("Actualizar profesor")

            if submit_edit_prof:
                frat_id = str(frats_df.loc[frats_df["nombre"] == fraternidad_n, "id"].iloc[0]) if not frats_df.empty else None
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE profesores
                            SET email=:email, cedula=:cedula, nombres=:nombres, apellidos=:apellidos,
                                rol=:rol, asignatura=:asignatura, area=:area, grados=:grados, fraternidad_id=:frat
                            WHERE id=:id
                        """), {
                            "email": email_n,
                            "cedula": cedula_n,
                            "nombres": nombres_n,
                            "apellidos": apellidos_n,
                            "rol": rol_n,
                            "asignatura": asignatura_n or None,
                            "area": area_n or None,
                            "grados": grados_n or None,
                            "frat": frat_id,
                            "id": str(profesor_edit.id)
                        })
                    st.success("✅ Profesor actualizado exitosamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar profesor: {e}")

