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
            auth_resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state["user"] = auth_resp.user
            st.success(f"✅ Bienvenido {email}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")
    st.stop()

# Ya logueado
st.sidebar.write(f"Conectado como **{st.session_state['user'].email}**")

datos = get_profesor(st.session_state["user"].email)
if not datos:
    st.error("❌ No tienes un rol asignado en este colegio")
    st.stop()

profesor_id, rol, fraternidad_id, colegio_id, nombre_completo, asignatura, area, grados = datos
st.session_state["profesor_id"] = profesor_id

st.sidebar.markdown("### 👨‍🏫 Perfil")
st.sidebar.write(f"**Nombre:** {nombre_completo}")
st.sidebar.write(f"**Rol:** {rol}")
st.sidebar.write(f"**Asignatura:** {asignatura or '-'}")
st.sidebar.write(f"**Área:** {area or '-'}")
st.sidebar.write(f"**Grados:** {grados or '-'}")

st.sidebar.markdown("### 🔑 Cambiar contraseña")
with st.sidebar.form("cambiar_contrasena"):
    actual = st.text_input("Contraseña actual", type="password")
    nueva = st.text_input("Nueva contraseña", type="password")
    confirmar = st.text_input("Confirmar nueva", type="password")
    submit_pass = st.form_submit_button("Actualizar")
    if submit_pass:
        if not actual or not nueva or not confirmar:
            st.sidebar.error("⚠️ Completa todos los campos.")
        elif nueva != confirmar:
            st.sidebar.error("⚠️ Las contraseñas no coinciden.")
        else:
            try:
                supabase.auth.sign_in_with_password({
                    "email": st.session_state['user'].email,
                    "password": actual
                })
                supabase.auth.update_user({"password": nueva})
                st.sidebar.success("✅ Contraseña actualizada.")
            except Exception as e:
                st.sidebar.error(f"❌ Error: {e}")

if st.sidebar.button("Cerrar sesión", use_container_width=True):
    try:
        supabase.auth.sign_out()
    finally:
        st.session_state.clear()
        st.rerun()

# =========================
# 📂 Funciones DB (cache)
# =========================
@st.cache_data(ttl=60)
def leer_resumen_estudiantes(colegio_id: int) -> pd.DataFrame:
    q = text("SELECT * FROM resumen_puntos_estudiantes WHERE colegio_id = :cid")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"cid": colegio_id})
    df.columns = df.columns.str.lower()
    # asegurar tipos
    if "puntos" in df.columns:
        df["puntos"] = pd.to_numeric(df["puntos"], errors="coerce").fillna(0).astype(int)
    return df

@st.cache_data(ttl=60)
def leer_historial_puntos(estudiante_id: int, colegio_id: int) -> pd.DataFrame:
    q = text("""
        SELECT 
            p.id, 
            v.nombre AS valor, 
            p.cantidad, 
            COALESCE(pr.nombres || ' ' || pr.apellidos, '---') AS profesor,
            p.created_at
        FROM puntos p
        JOIN valores v ON v.id = p.valor_id
        LEFT JOIN profesores pr ON pr.id = p.profesor_id
        JOIN estudiantes e ON e.id = p.estudiante_id
        WHERE p.estudiante_id = :eid
          AND e.colegio_id = :cid
        ORDER BY p.created_at DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={
            "eid": int(estudiante_id),
            "cid": int(colegio_id)
        })
    return df

@st.cache_data(ttl=60)
def leer_valores(colegio_id: int) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM valores WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        return pd.read_sql(q, conn, params={"cid": colegio_id})

@st.cache_data(ttl=60)
def leer_fraternidades(colegio_id: int) -> pd.DataFrame:
    q = text("SELECT id, nombre FROM fraternidades WHERE colegio_id = :cid ORDER BY nombre")
    with engine.connect() as conn:
        return pd.read_sql(q, conn, params={"cid": colegio_id})

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
            "frat": int(fraternidad_id) if fraternidad_id is not None else None,
            "id": int(estudiante_id)
        })
    clear_all_caches()

# =========================
# 🧮 Puntos
# =========================
def actualizar_puntos(estudiante_id, valor_nombre, delta, profesor_id=None):
    if delta == 0:
        st.info("ℹ️ No se registran movimientos por 0 puntos.")
        return

    prof_id = profesor_id or st.session_state.get("profesor_id")
    if not prof_id:
        st.error("⚠️ No se reconoce al profesor logueado.")
        return

    with engine.begin() as conn:
        valor_q = conn.execute(
            text("SELECT id FROM valores WHERE nombre=:valor AND colegio_id=:colegio"),
            {"valor": valor_nombre, "colegio": colegio_id}
        ).fetchone()
        if not valor_q:
            st.error("⚠️ El valor no existe en este colegio.")
            return
        valor_id = str(valor_q[0])   # ✅ UUID en texto

        conn.execute(text("""
            INSERT INTO puntos (estudiante_id, valor_id, cantidad, profesor_id)
            VALUES (:estudiante_id, :valor_id, :cantidad, :profesor_id)
        """), {
            "estudiante_id": str(estudiante_id),  # ✅ UUID como texto
            "valor_id": valor_id,
            "cantidad": int(delta),              # ✅ numérico
            "profesor_id": str(prof_id)          # ✅ UUID como texto
        })
    clear_all_caches()

def asignar_puntos_fraternidad(fraternidad_id, valor_nombre, delta, profesor_id):
    if delta == 0:
        st.info("ℹ️ No se registran movimientos por 0 puntos.")
        return
    with engine.begin() as conn:
        valor_q = conn.execute(
            text("SELECT id FROM valores WHERE nombre=:valor AND colegio_id=:colegio"),
            {"valor": valor_nombre, "colegio": colegio_id}
        ).fetchone()
        if not valor_q:
            st.error("⚠️ El valor no existe en este colegio.")
            return
        valor_id = str(valor_q[0])   # ✅ Guardar como texto

        estudiantes = conn.execute(
            text("SELECT id FROM estudiantes WHERE fraternidad_id=:fid AND colegio_id=:cid"),
            {"fid": str(fraternidad_id), "cid": str(colegio_id)}
        ).fetchall()

        for (est_id,) in estudiantes:
            conn.execute(text("""
                INSERT INTO puntos (estudiante_id, valor_id, cantidad, profesor_id)
                VALUES (:eid, :valor_id, :cantidad, :profesor_id)
            """), {
                "eid": str(est_id),             # ✅ UUID como texto
                "valor_id": valor_id,
                "cantidad": int(delta),         # ✅ numérico
                "profesor_id": str(profesor_id) # ✅ UUID como texto
            })
    clear_all_caches()


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

    # Búsqueda rápida
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
                          .loc[:, ["codigo", "nombre", "apellidos", "fraternidad", "grado", "puntos"]]
                         )
            st.dataframe(resultados, use_container_width=True)

    # Buscador jerárquico
    st.subheader("🎓 Buscar por grado y sección")
    grados_unicos = df["grado"].dropna().astype(str).unique().tolist()

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
                st.markdown(f"### 👥 Estudiantes de {grado_completo}")
                st.dataframe(df_filtrado[["codigo", "nombre", "apellidos", "fraternidad", "grado", "puntos"]],
                             use_container_width=True, hide_index=True)

                # Tabla interactiva con checkbox de selección
                df_filtrado = df_filtrado.reset_index(drop=True)
                df_filtrado["Seleccionar"] = False

                df_sel = st.data_editor(
                    df_filtrado[["codigo", "nombre", "apellidos", "fraternidad", "grado", "puntos", "Seleccionar"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Seleccionar": st.column_config.CheckboxColumn(required=True)
                    }
                )

                # Verificar selección
                seleccionados = df_sel[df_sel["Seleccionar"] == True]
                if not seleccionados.empty:
                    est_row = df_filtrado.loc[seleccionados.index[0]]
                    estudiante_seleccionado = est_row
                    st.session_state["estudiante_sel_id"] = int(est_row["estudiante_id"])


    if estudiante_seleccionado is None and st.session_state.get("estudiante_sel_id") is not None:
        est_id = st.session_state["estudiante_sel_id"]
        cand = df[df["estudiante_id"] == est_id]
        if not cand.empty:
            estudiante_seleccionado = cand.drop_duplicates(subset=["estudiante_id"]).iloc[0]

    # Detalle del estudiante
    if estudiante_seleccionado is not None:
        r = estudiante_seleccionado
        st.markdown(f"## 👤 {r['nombre']} {r['apellidos']} | 🎓 {r['grado']} | 🏠 {r['fraternidad']}")
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

        # Asignar puntos al estudiante
        st.subheader("➕ Asignar puntos al estudiante")
        if valores_df.empty:
            st.info("No hay valores configurados en el colegio.")
        else:
            categoria = st.selectbox("Categoría", valores_df["nombre"].tolist(), key="categoria_asignar")
            delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1, key="delta_puntos")

            col_a, col_b = st.columns([1,1])
            with col_a:
                if st.button("Actualizar puntos", use_container_width=True):
                    actualizar_puntos(str(r["estudiante_id"]), str(categoria), int(delta), profesor_id)
                    st.success(f"{delta:+} puntos añadidos en {categoria}.")
                    st.rerun()
            with col_b:
                if st.button("Recalcular vista", use_container_width=True):
                    clear_all_caches()
                    st.rerun()

        # Edición solo director
        if rol == "director":
            st.header("✏️ Editar estudiante")
            frats = leer_fraternidades(colegio_id)

            with st.form("editar_estudiante", clear_on_submit=False):
                codigo_edit = st.text_input("Código", value=r["codigo"] or "")
                nombre_edit = st.text_input("Nombre", value=r["nombre"] or "")
                apellidos_edit = st.text_input("Apellidos", value=r["apellidos"] or "")
                grado_edit = st.text_input("Grado", value=r["grado"] or "")

                frat_nombres = frats["nombre"].tolist() if not frats.empty else []
                idx_frat = frat_nombres.index(r["fraternidad"]) if r["fraternidad"] in frat_nombres else 0
                fraternidad_edit = st.selectbox("Fraternidad", frat_nombres, index=idx_frat if frat_nombres else 0)

                submit = st.form_submit_button("💾 Guardar cambios")
                if submit:
                    frat_id = int(frats.loc[frats["nombre"] == fraternidad_edit, "id"].iloc[0]) if not frats.empty else None
                    actualizar_estudiante_full(int(r["estudiante_id"]), codigo_edit, nombre_edit, apellidos_edit, grado_edit, frat_id)
                    st.success("✅ Estudiante actualizado correctamente.")
                    st.rerun()

            #st.subheader("📋 Historial de puntos")
            #historial = leer_historial_puntos(int(r["estudiante_id"]), colegio_id)
            #st.dataframe(historial, use_container_width=True, hide_index=True)

# ---- TAB 3: Fraternidades ----
with tabs[2]:
    st.header("🏠 Asignar puntos por fraternidad")
    frats = leer_fraternidades(colegio_id)
    valores_df = leer_valores(colegio_id)
    if frats.empty:
        st.info("No hay fraternidades configuradas.")
    elif valores_df.empty:
        st.info("No hay valores configurados.")
    else:
        col1, col2, col3 = st.columns([2,2,1])
        with col1:
            frat_sel = st.selectbox("Fraternidad", frats["nombre"].tolist())
        with col2:
            valor_sel = st.selectbox("Valor", valores_df["nombre"].tolist())
        with col3:
            delta = st.number_input("Puntos (+/-)", min_value=-50, max_value=50, value=1, step=1)

        if st.button("Asignar puntos a toda la fraternidad", type="primary", use_container_width=True):
            frat_id = int(frats.loc[frats["nombre"] == frat_sel, "id"].iloc[0])
            asignar_puntos_fraternidad(frat_id, valor_sel, delta, st.session_state["profesor_id"])
            st.success(f"✅ {delta:+} puntos asignados a todos los estudiantes de {frat_sel}")
            st.balloons()

# ---- TAB 4: Profesores (solo director) ----
with tabs[3]:
    if rol != "director":
        st.warning("⚠️ Solo los directores pueden gestionar profesores.")
    else:
        st.header("👨‍🏫 Gestión de profesores")

        # Crear profesor
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
                    frat_id = int(frats.loc[frats["nombre"] == fraternidad_prof, "id"].iloc[0]) if not frats.empty else None
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
                                "colegio": int(colegio_id)
                            })

                        st.success(f"✅ Profesor agregado. Contraseña inicial = cédula ({cedula_prof}).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al crear profesor: {e}")

        # Resetear contraseña = cédula (conservando email)
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
                                {"ced": cedula_reset, "cid": int(colegio_id)}
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

        # Enviar Magic Link / OTP
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
