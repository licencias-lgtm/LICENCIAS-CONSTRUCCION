import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
import sqlite3
import os

try:
    import holidays
    CO_HOLIDAYS = holidays.CO(years=range(2024, 2032))
except ImportError:
    CO_HOLIDAYS = {}

st.set_page_config(
    page_title="Sistema de Licencias de Construcción",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ruta fija del archivo de base de datos (siempre el mismo archivo, sin duplicados)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licencias.db")

# ─────────────────────────────────────────────
# Utilidades de días hábiles (Colombia)
# ─────────────────────────────────────────────
def es_dia_habil(d: date) -> bool:
    if d.weekday() >= 5:  # sábado o domingo
        return False
    if d in CO_HOLIDAYS:
        return False
    return True

def sumar_dias_habiles(fecha_inicio, n_dias: int) -> date:
    """Suma n días hábiles a partir de la fecha dada (no cuenta el día de inicio)."""
    if fecha_inicio is None:
        return None
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
    elif isinstance(fecha_inicio, datetime):
        fecha_inicio = fecha_inicio.date()
    cont = 0
    actual = fecha_inicio
    while cont < n_dias:
        actual += timedelta(days=1)
        if es_dia_habil(actual):
            cont += 1
    return actual

def dias_habiles_entre(fecha_ini, fecha_fin) -> int:
    if not fecha_ini or not fecha_fin:
        return 0
    if isinstance(fecha_ini, str):
        fecha_ini = datetime.strptime(fecha_ini, "%Y-%m-%d").date()
    if isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    if fecha_fin < fecha_ini:
        return 0
    cont = 0
    actual = fecha_ini
    while actual < fecha_fin:
        actual += timedelta(days=1)
        if es_dia_habil(actual):
            cont += 1
    return cont

def parse_date(val):
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def fmt_date(val):
    d = parse_date(val)
    return d.strftime("%Y-%m-%d") if d else None

def safe_get(exp, key, default=None):
    try:
        v = exp.get(key, default) if hasattr(exp, "get") else exp[key] if key in exp.index else default
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return v
    except Exception:
        return default

# ─────────────────────────────────────────────
# Base de datos
# ─────────────────────────────────────────────
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def boton_descarga_bd(key_suffix=""):
    """Botón reutilizable para descargar la base de datos SQLite."""
    if not os.path.exists(DB_PATH):
        st.caption("Sin base de datos aún.")
        return
    try:
        with open(DB_PATH, "rb") as f:
            db_bytes = f.read()
        st.download_button(
            label="⬇️ Descargar respaldo (.db)",
            data=db_bytes,
            file_name=f"licencias_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
            mime="application/x-sqlite3",
            use_container_width=True,
            key=f"dl_db_{key_suffix}",
            help="Guarda este archivo en tu PC. Así no pierdes la información al actualizar o redesplegar la app.",
        )
    except Exception as e:
        st.caption(f"No se pudo leer la BD: {e}")

COLUMNAS_EXPEDIENTES = [
    # Identificación y radicación
    # NOTA: SQLite no permite UNIQUE en ALTER TABLE ADD COLUMN.
    # El UNIQUE se declara solo en el CREATE TABLE completo.
    ("numero_radicado", "TEXT"),
    ("fecha_radicacion", "TEXT"),
    ("modalidad", "TEXT"),
    ("fecha_vencimiento_45", "TEXT"),
    ("alerta", "TEXT"),
    ("estado", "TEXT"),
    ("numero_resolucion", "TEXT"),
    ("fecha_resolucion", "TEXT"),
    # Pagos
    ("pago_30_anticipo", "TEXT"),
    ("valor_pago_30", "REAL"),
    ("numero_recibo_30", "TEXT"),
    ("saldo_70", "TEXT"),
    ("valor_pago_70", "REAL"),
    ("numero_recibo_70", "TEXT"),
    ("confirma_pago_70", "TEXT"),
    ("observaciones_pago", "TEXT"),  # vigencias anteriores, ajustes, casos atípicos
    # Personas
    ("persona_autoriza", "TEXT"),
    ("propietario", "TEXT"),
    ("cedula_titular", "TEXT"),
    ("apoderado", "TEXT"),
    ("celular", "TEXT"),
    # Predio
    ("ficha_catastral", "TEXT"),
    ("matricula_inmobiliaria", "TEXT"),
    ("direccion", "TEXT"),
    ("barrio", "TEXT"),
    ("zona", "TEXT"),
    ("superficie", "REAL"),
    ("valor_obra", "REAL"),
    # Revisiones (plazos hábiles)
    ("fecha_ingreso_juridica", "TEXT"),
    ("fecha_salida_juridica", "TEXT"),
    ("fecha_ingreso_arquitectura", "TEXT"),
    ("fecha_salida_arquitectura", "TEXT"),
    ("fecha_ingreso_estructural", "TEXT"),
    ("fecha_salida_estructural", "TEXT"),
    ("dias_en_estudio", "INTEGER"),
    # Acta de observaciones
    ("fecha_elaboracion_acta", "TEXT"),
    ("numero_acta", "TEXT"),
    ("radicado_salida_acta", "TEXT"),
    ("fecha_radicado_acta", "TEXT"),
    ("radicado_oficio_prorroga", "TEXT"),
    ("fecha_oficio_prorroga", "TEXT"),
    ("fecha_vencimiento_subsanacion", "TEXT"),
    ("tiene_prorroga", "TEXT"),
    ("radicado_entrada_correccion", "TEXT"),
    ("fecha_radicado_correccion", "TEXT"),
    ("fecha_acta_finalizacion", "TEXT"),
    # Chequeo / entrega planos (compatibilidad)
    ("tipo_entrega_planos", "TEXT"),
    ("correo_entrega", "TEXT"),
    ("fecha_entrega_planos", "TEXT"),
    ("hora_entrega_planos", "TEXT"),
    ("chequeo_realizado", "TEXT"),
    # Aprobaciones
    ("aprobacion_juridica", "TEXT"),
    ("aprobacion_arquitectura", "TEXT"),
    ("aprobacion_ingenieria", "TEXT"),
    ("cumple_juridica", "TEXT"),
    ("cumple_arquitectura", "TEXT"),
    ("cumple_ingenieria", "TEXT"),
    # Proyección acto administrativo
    ("area_predio", "REAL"),
    ("area_libre", "REAL"),
    ("numero_pisos", "INTEGER"),
    ("numero_vivienda", "INTEGER"),
    ("area_primer_piso", "REAL"),
    ("area_segundo_piso", "REAL"),
    ("area_existente", "REAL"),
    ("area_ampliacion", "REAL"),
    ("area_total_ampliacion", "REAL"),
    ("area_total_construida", "REAL"),
    ("indice_ocupacion", "REAL"),
    ("indice_construccion", "REAL"),
    ("sector", "TEXT"),
    ("ubicacion_predio", "TEXT"),
    ("profesional_arquitectonico", "TEXT"),
    ("profesional_estructural", "TEXT"),
    ("cantidad_planos_arq", "INTEGER"),
    ("cantidad_planos_est", "INTEGER"),
    ("descripcion_acto", "TEXT"),
    # Firmas y sellos
    ("firma_juridico", "TEXT"),
    ("firma_arquitecto", "TEXT"),
    ("firma_ingeniero", "TEXT"),
    ("firma_jefe_planeacion", "TEXT"),
    ("fecha_firma_juridico", "TEXT"),
    ("fecha_firma_arquitecto", "TEXT"),
    ("fecha_firma_ingeniero", "TEXT"),
    ("fecha_firma_jefe", "TEXT"),
    ("planos_sellados", "TEXT"),
    ("operacion_planos", "TEXT"),
    ("requiere_firma_juridico", "TEXT"),
    ("requiere_firma_arquitecto", "TEXT"),
    ("requiere_firma_ingeniero", "TEXT"),
    # Notificación y publicación
    ("oficio_solicitud_notificacion", "TEXT"),
    ("fecha_oficio_notificacion", "TEXT"),
    ("fecha_notificacion_personal", "TEXT"),
    ("oficio_fijacion_valla", "TEXT"),
    ("soporte_publicacion_emisora", "TEXT"),
    ("foto_valla", "TEXT"),
    ("link_publicacion", "TEXT"),
    ("tiene_ejecutoria", "TEXT"),
    ("fecha_ejecutoria", "TEXT"),
    # Entrega final (cumplimiento, no es un estado del flujo)
    ("fecha_entrega_final", "TEXT"),
    ("persona_recibe", "TEXT"),
    ("entrega_cumplida", "TEXT"),  # Sí / No — chuleo de cumplimiento
    # Archivo físico (después de ejecutoria)
    ("archivo_tomos", "INTEGER"),
    ("archivo_folios", "INTEGER"),
    ("archivo_numero_caja", "TEXT"),
    ("archivo_ubicacion", "TEXT"),  # Archivo de gestión / Mesa nene / Archivo general
    # Meta
    ("revisor_actual", "TEXT"),
    ("observaciones", "TEXT"),
    ("ultima_actualizacion", "TEXT"),
    ("tipo_obra", "TEXT"),  # compatibilidad
]

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            usuario TEXT UNIQUE,
            clave TEXT,
            nombre TEXT,
            rol TEXT
        )
    ''')

    # Crear tabla completa de una sola vez (incluye UNIQUE en numero_radicado).
    # SQLite NO permite UNIQUE/PRIMARY KEY en ALTER TABLE ADD COLUMN.
    cols_sql = ",\n            ".join(
        f"{col} {tipo}" for col, tipo in COLUMNAS_EXPEDIENTES
    )
    # Asegurar UNIQUE solo en el CREATE TABLE
    cols_sql = cols_sql.replace("numero_radicado TEXT", "numero_radicado TEXT UNIQUE", 1)

    c.execute(f'''
        CREATE TABLE IF NOT EXISTS expedientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {cols_sql}
        )
    ''')

    # Migración: agregar columnas que falten en bases de datos antiguas
    # (sin UNIQUE ni PRIMARY KEY, porque ALTER no los soporta)
    for col, tipo in COLUMNAS_EXPEDIENTES:
        try:
            c.execute(f'ALTER TABLE expedientes ADD COLUMN {col} {tipo}')
        except Exception:
            pass

    # Índice UNIQUE sobre numero_radicado (protege contra duplicados
    # aunque la tabla se haya creado antes sin la restricción)
    try:
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_expedientes_numero_radicado "
            "ON expedientes(numero_radicado)"
        )
    except Exception:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS requerimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_requerimiento TEXT,
            numero_radicado TEXT,
            fecha_acta TEXT,
            tipo TEXT,
            descripcion TEXT,
            fecha_limite_respuesta TEXT,
            fecha_respuesta TEXT,
            estado TEXT,
            elaborado_por TEXT,
            observaciones TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS prorrogas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_prorroga TEXT,
            numero_radicado TEXT,
            solicitante TEXT,
            calidad TEXT,
            fecha_solicitud TEXT,
            motivo TEXT,
            dias_solicitados INTEGER,
            decision TEXT,
            fecha_decision TEXT,
            nuevo_vencimiento TEXT,
            observaciones TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS historial_firmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_radicado TEXT,
            firmante TEXT,
            rol_firmante TEXT,
            fecha_firma TEXT,
            accion TEXT,
            observaciones TEXT
        )
    ''')

    usuarios_demo = [
        ('admin', 'admin123', 'Administrador del Sistema', 'Administrador'),
        ('juridica', 'juridica123', 'Patricia Gómez', 'Revisor Jurídico'),
        ('arquitectura', 'arq123', 'Laura Rivas', 'Revisor Arquitectónico'),
        ('ingenieria', 'ing123', 'Carlos Méndez', 'Revisor Ingeniería'),
        ('ventanilla', 'ventanilla123', 'Ana Receptor', 'Ventanilla'),
        ('proyectista', 'proy123', 'Andrés Rojas', 'Proyectista'),
        ('jefe', 'jefe123', 'María Planeación', 'Jefe de Planeación'),
    ]
    for u in usuarios_demo:
        c.execute('INSERT OR IGNORE INTO usuarios (usuario, clave, nombre, rol) VALUES (?, ?, ?, ?)', u)

    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────
def login():
    st.markdown("## 🏗️ Sistema de Gestión de Licencias de Construcción")
    st.markdown("### Inicio de sesión")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            conn = get_connection()
            c = conn.cursor()
            c.execute('SELECT nombre, rol FROM usuarios WHERE usuario=? AND clave=?', (usuario, clave))
            result = c.fetchone()
            conn.close()
            if result:
                st.session_state['logged_in'] = True
                st.session_state['nombre'] = result[0]
                st.session_state['rol'] = result[1]
                st.session_state['usuario'] = usuario
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        st.info("""
        **Usuarios de prueba:**
        - admin / admin123
        - juridica / juridica123
        - arquitectura / arq123
        - ingenieria / ing123
        - ventanilla / ventanilla123
        - proyectista / proy123
        - jefe / jefe123
        """)

# ─────────────────────────────────────────────
# Helpers de formulario
# ─────────────────────────────────────────────
def date_input_optional(label, value=None, key=None):
    """Campo de fecha opcional: permite dejar vacío."""
    col_a, col_b = st.columns([3, 1])
    with col_a:
        d = st.date_input(label, value=value if value else None, key=key)
    with col_b:
        st.write("")
        st.write("")
        limpiar = st.checkbox("Vacío", value=(value is None), key=f"{key}_vacio" if key else None)
    if limpiar:
        return None
    return d

MODALIDADES = [
    "Obra Nueva", "Ampliación", "Remodelación", "Demolición",
    "Regularización", "Cambio de Uso", "Obra Menor", "Re-subdivisión",
    "Urbanización", "Parcelación", "Otro"
]

ESTADOS = [
    "Radicado", "En revisión", "En Acta de Observaciones", "Subsanación",
    "Aprobado",
    "Acto proyectado", "En firmas", "Resolución firmada",
    "Oficio de notificación", "Notificado", "En publicación",
    "Ejecutoriado", "Archivado", "Negado", "Inadmitido"
]

# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
def pagina_dashboard():
    st.title("📊 Dashboard")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes", conn)
    conn.close()

    if df.empty:
        st.warning("No hay expedientes registrados todavía.")
        return

    # Calcular alertas de vencimiento
    hoy = date.today()
    alertas = 0
    for _, row in df.iterrows():
        fv = parse_date(row.get("fecha_vencimiento_45"))
        if fv and fv <= hoy + timedelta(days=5) and row.get("estado") not in ("Ejecutoriado", "Archivado", "Negado"):
            alertas += 1

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Expedientes", len(df))
    with col2:
        st.metric("En revisión / Observaciones",
                  len(df[df['estado'].astype(str).str.contains('revisión|observacion|Subsanación', case=False, na=False)]))
    with col3:
        st.metric("Alertas de vencimiento", alertas)
    with col4:
        st.metric("Ejecutoriados", len(df[df['estado'] == 'Ejecutoriado']))
    with col5:
        st.metric("En firmas", len(df[df['estado'] == 'En firmas']))

    st.divider()
    st.subheader("Últimos expedientes")
    cols = [c for c in ['numero_radicado', 'fecha_radicacion', 'modalidad', 'estado', 'propietario',
                        'fecha_vencimiento_45', 'alerta', 'numero_resolucion'] if c in df.columns]
    st.dataframe(df[cols].head(15), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# Consulta
# ─────────────────────────────────────────────
def _normalizar_url(url: str) -> str:
    """Asegura que el enlace tenga esquema http/https para que sea clicable."""
    if not url or not str(url).strip():
        return ""
    u = str(url).strip()
    if u.lower().startswith(("http://", "https://")):
        return u
    return f"https://{u}"


def pagina_consulta():
    st.title("🔍 Consulta de Expedientes")
    col1, col2 = st.columns(2)
    with col1:
        tipo = st.radio("Buscar por:", ["Número de Radicado", "Cédula / NIT", "Ficha catastral", "Matrícula inmobiliaria"])
    with col2:
        valor = st.text_input("Valor de búsqueda")
        fecha = None
        if tipo == "Número de Radicado":
            fecha = st.date_input("Fecha de radicación (opcional)", value=None)

    if st.button("Buscar"):
        conn = get_connection()
        if tipo == "Número de Radicado":
            if fecha:
                df = pd.read_sql_query(
                    "SELECT * FROM expedientes WHERE numero_radicado LIKE ? AND fecha_radicacion = ?",
                    conn, params=(f"%{valor}%", fecha.strftime('%Y-%m-%d')))
            else:
                df = pd.read_sql_query(
                    "SELECT * FROM expedientes WHERE numero_radicado LIKE ?",
                    conn, params=(f"%{valor}%",))
        elif tipo == "Cédula / NIT":
            df = pd.read_sql_query(
                "SELECT * FROM expedientes WHERE cedula_titular LIKE ?",
                conn, params=(f"%{valor}%",))
        elif tipo == "Ficha catastral":
            df = pd.read_sql_query(
                "SELECT * FROM expedientes WHERE ficha_catastral LIKE ?",
                conn, params=(f"%{valor}%",))
        else:
            df = pd.read_sql_query(
                "SELECT * FROM expedientes WHERE matricula_inmobiliaria LIKE ?",
                conn, params=(f"%{valor}%",))
        conn.close()
        if df.empty:
            st.warning("No se encontraron expedientes.")
        else:
            st.success(f"Se encontraron {len(df)} expediente(s)")
            # Tabla principal (sin el link para no mezclarlo; se muestra aparte)
            cols_tabla = [c for c in [
                "numero_radicado", "fecha_radicacion", "modalidad", "estado",
                "propietario", "cedula_titular", "direccion", "barrio",
                "fecha_vencimiento_45", "alerta", "numero_resolucion",
                "fecha_resolucion", "tiene_ejecutoria", "fecha_ejecutoria",
            ] if c in df.columns]
            st.dataframe(df[cols_tabla] if cols_tabla else df, use_container_width=True, hide_index=True)

            # Link de publicación: se muestra aparte, clicable hacia el documento
            st.divider()
            st.subheader("🔗 Link de publicación (acto en página web)")
            st.caption("Enlace directo al documento publicado. Abre en una pestaña nueva.")
            n_rows = len(df)
            for i, (_, row) in enumerate(df.iterrows()):
                rad = safe_get(row, "numero_radicado") or "—"
                link_raw = safe_get(row, "link_publicacion") or ""
                link = _normalizar_url(link_raw)
                with st.container():
                    c_a, c_b = st.columns([1, 3])
                    with c_a:
                        st.markdown(f"**Radicado:** `{rad}`")
                    with c_b:
                        if link:
                            st.markdown(
                                f'<a href="{link}" target="_blank" rel="noopener noreferrer">'
                                f"📄 Abrir documento de publicación</a>",
                                unsafe_allow_html=True,
                            )
                            st.caption(link)
                        else:
                            st.caption("Sin link de publicación registrado.")
                if i < n_rows - 1:
                    st.markdown("---")

# ─────────────────────────────────────────────
# Nuevo / Editar expediente (guardado parcial)
# ─────────────────────────────────────────────
def calcular_fechas_revision(fecha_ingreso_jur):
    """A partir de la fecha de ingreso a jurídica calcula las demás."""
    if not fecha_ingreso_jur:
        return {}
    f = parse_date(fecha_ingreso_jur)
    if not f:
        return {}
    salida_jur = sumar_dias_habiles(f, 5)
    ingreso_arq = salida_jur  # mismo día o siguiente; usamos salida como ingreso
    salida_arq = sumar_dias_habiles(ingreso_arq, 8)
    ingreso_est = salida_arq
    salida_est = sumar_dias_habiles(ingreso_est, 8)  # mismo criterio de 8 días
    return {
        "fecha_salida_juridica": salida_jur,
        "fecha_ingreso_arquitectura": ingreso_arq,
        "fecha_salida_arquitectura": salida_arq,
        "fecha_ingreso_estructural": ingreso_est,
        "fecha_salida_estructural": salida_est,
    }

def _mensajes_post_guardado(key_suffix=""):
    """Muestra mensaje de éxito y oferta de respaldo tras guardar."""
    if st.session_state.get("msg_guardado"):
        st.success(st.session_state.pop("msg_guardado"))
    if st.session_state.get("ofrecer_backup"):
        st.warning("**Recomendado:** descarga un respaldo de la base de datos para no perder información al actualizar o redesplegar la app.")
        boton_descarga_bd(key_suffix=f"post_save_{key_suffix}")
        if st.button("Continuar sin descargar ahora", key=f"skip_backup_{key_suffix}"):
            st.session_state["ofrecer_backup"] = False
            st.rerun()


def pagina_nuevo():
    """Página exclusiva para crear un expediente nuevo."""
    st.title("➕ Nuevo expediente")
    st.info("Completa los datos del nuevo expediente. Solo el número de radicado es obligatorio. Puedes guardar avances parciales.")
    _mensajes_post_guardado("nuevo")
    _formulario_expediente(es_nuevo=True, exp=None, radicado_fijo=None)


def pagina_actualizar():
    """Página exclusiva para actualizar un expediente existente: muestra todos los datos y permite editar."""
    st.title("✏️ Actualizar expediente")
    st.info("Selecciona el expediente. Se cargan **todos** sus datos para que edites lo necesario y al final pulses **Actualizar y guardar**.")
    _mensajes_post_guardado("act")

    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT numero_radicado, propietario, estado, fecha_radicacion FROM expedientes ORDER BY id DESC",
            conn,
        )
    except Exception as e:
        st.error(f"Error al leer expedientes: {e}")
        conn.close()
        return
    conn.close()

    if df.empty:
        st.warning("No hay expedientes registrados. Crea uno desde **Nuevo expediente**.")
        return

    # Selector con info útil
    opciones = []
    for _, row in df.iterrows():
        prop = row.get("propietario") or "—"
        est = row.get("estado") or "—"
        opciones.append(f"{row['numero_radicado']}  |  {prop}  |  {est}")

    sel_label = st.selectbox("Seleccionar expediente a actualizar", opciones, key="act_sel_exp")
    radicado_sel = sel_label.split("  |  ")[0].strip() if sel_label else None

    if not radicado_sel:
        st.warning("Selecciona un expediente.")
        return

    conn = get_connection()
    df_e = pd.read_sql_query(
        "SELECT * FROM expedientes WHERE numero_radicado=?",
        conn,
        params=(radicado_sel,),
    )
    conn.close()
    if df_e.empty:
        st.error("No se encontró el expediente seleccionado.")
        return

    exp = df_e.iloc[0]
    st.success(f"Cargado: **{radicado_sel}** — {safe_get(exp, 'propietario') or 'Sin propietario'} — Estado: {safe_get(exp, 'estado') or '—'}")
    _formulario_expediente(es_nuevo=False, exp=exp, radicado_fijo=radicado_sel)


def _formulario_expediente(es_nuevo: bool, exp, radicado_fijo=None):
    """Formulario compartido de expediente. es_nuevo=True crea; False actualiza."""
    modo = radicado_fijo  # en actualización es el radicado fijo
    expand_all = not es_nuevo  # en actualizar se abren las secciones
    pfx = "n_" if es_nuevo else "a_"  # prefijo de keys para no mezclar sesión Nuevo/Actualizar

    # ── Sección 1: Identificación ──
    with st.expander("1. Identificación y radicación", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            numero = st.text_input("N° Radicado *",
                                   value=safe_get(exp, 'numero_radicado', '') if exp is not None else '',
                                   disabled=not es_nuevo)
            fecha_rad = st.date_input("Fecha de radicación",
                                      value=parse_date(safe_get(exp, 'fecha_radicacion')) or date.today())
            _mod = safe_get(exp, 'modalidad', MODALIDADES[0]) or MODALIDADES[0]
            if _mod == "Nueva Construcción":
                _mod = "Obra Nueva"  # nombre anterior unificado
            modalidad = st.selectbox(
                "Modalidad",
                MODALIDADES,
                index=MODALIDADES.index(_mod) if _mod in MODALIDADES else 0,
            )
        with col2:
            # Estado primero (define si hay alertas y conteo de días)
            _est = safe_get(exp, 'estado', 'Radicado') or 'Radicado'
            if _est == "Entrega final":
                _est = "Ejecutoriado"  # estado antiguo eliminado del flujo
            estado = st.selectbox(
                "Estado",
                ESTADOS,
                index=ESTADOS.index(_est) if _est in ESTADOS else 0,
                key=f"{pfx}estado",
            )
            # Estados cerrados: no alertas ni conteo de días en estudio
            ESTADOS_CERRADOS = ("Ejecutoriado", "Archivado", "Negado")
            cerrado = estado in ESTADOS_CERRADOS

            # Vencimiento 45 días hábiles
            if fecha_rad:
                fv45 = sumar_dias_habiles(fecha_rad, 45)
            else:
                fv45 = None
            st.text_input("Fecha vencimiento (45 días hábiles)",
                          value=fv45.strftime('%Y-%m-%d') if fv45 else '', disabled=True)
            hoy = date.today()
            if cerrado:
                alerta = "—"  # sin alertas si ya está ejecutoriado / cerrado
            elif fv45:
                dias_rest = dias_habiles_entre(hoy, fv45) if fv45 > hoy else -dias_habiles_entre(fv45, hoy)
                if dias_rest < 0:
                    alerta = f"⚠️ VENCIDO ({abs(dias_rest)} días hábiles)"
                elif dias_rest <= 5:
                    alerta = f"🔴 Próximo a vencer ({dias_rest} días hábiles)"
                elif dias_rest <= 15:
                    alerta = f"🟡 Atención ({dias_rest} días hábiles)"
                else:
                    alerta = f"🟢 En término ({dias_rest} días hábiles)"
            else:
                alerta = ""
            st.text_input("Alerta", value=alerta, disabled=True)
        with col3:
            num_res = st.text_input("Número de resolución", value=safe_get(exp, 'numero_resolucion', '') or '')
            fecha_res = st.date_input("Fecha resolución",
                                      value=parse_date(safe_get(exp, 'fecha_resolucion')),
                                      key=f"{pfx}fecha_res_id")
            if st.checkbox("Sin fecha resolución", value=parse_date(safe_get(exp, 'fecha_resolucion')) is None,
                           key=f"{pfx}sin_fecha_res"):
                fecha_res = None

    # ── Sección 2: Pagos ──
    with st.expander("2. Pagos", expanded=expand_all):
        st.caption("Registra el estado, valor y número de recibo de Hacienda de cada pago.")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Anticipo 30%**")
            pago30 = st.selectbox("Estado pago 30%", ["", "Sí", "No", "Pendiente"],
                                  index=["", "Sí", "No", "Pendiente"].index(safe_get(exp, 'pago_30_anticipo', '') or '')
                                  if (safe_get(exp, 'pago_30_anticipo') or '') in ["", "Sí", "No", "Pendiente"] else 0,
                                  key=f"{pfx}pago30_estado")
            valor_pago30 = st.number_input(
                "Valor pago 30% ($)",
                min_value=0.0,
                value=float(safe_get(exp, 'valor_pago_30') or 0),
                step=100000.0,
                format="%.0f",
                key=f"{pfx}valor_pago30",
            )
            num_recibo30 = st.text_input(
                "N° recibo Hacienda (30%)",
                value=safe_get(exp, 'numero_recibo_30', '') or '',
                key=f"{pfx}recibo30",
            )
        with col2:
            st.markdown("**Saldo 70%**")
            saldo70 = st.selectbox("Estado saldo 70%", ["", "Sí", "No", "Pendiente"],
                                   index=["", "Sí", "No", "Pendiente"].index(safe_get(exp, 'saldo_70', '') or '')
                                   if (safe_get(exp, 'saldo_70') or '') in ["", "Sí", "No", "Pendiente"] else 0,
                                   key=f"{pfx}saldo70_estado")
            valor_pago70 = st.number_input(
                "Valor pago 70% ($)",
                min_value=0.0,
                value=float(safe_get(exp, 'valor_pago_70') or 0),
                step=100000.0,
                format="%.0f",
                key=f"{pfx}valor_pago70",
            )
            num_recibo70 = st.text_input(
                "N° recibo Hacienda (70%)",
                value=safe_get(exp, 'numero_recibo_70', '') or '',
                key=f"{pfx}recibo70",
            )
        with col3:
            st.markdown("**Confirmación**")
            conf70 = st.selectbox("Confirma pago 70%", ["", "Sí", "No"],
                                  index=["", "Sí", "No"].index(safe_get(exp, 'confirma_pago_70', '') or '')
                                  if (safe_get(exp, 'confirma_pago_70') or '') in ["", "Sí", "No"] else 0,
                                  key=f"{pfx}conf70")
            total_pagos = (valor_pago30 or 0) + (valor_pago70 or 0)
            st.metric("Total pagado registrado", f"$ {total_pagos:,.0f}")
        obs_pago = st.text_area(
            "Observaciones de pago (casos atípicos)",
            value=safe_get(exp, "observaciones_pago", "") or "",
            key=f"{pfx}obs_pago",
            height=100,
            help="Use este campo para vigencias anteriores, pagos ajustados, liquidaciones especiales u otras situaciones atípicas.",
            placeholder="Ej.: pago 30% con vigencia 2023; ajuste de liquidación; pago consolidado en un solo recibo; etc.",
        )

    # ── Sección 3: Personas y predio ──
    with st.expander("3. Personas y predio", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            propietario = st.text_input("Propietario", value=safe_get(exp, 'propietario', '') or '')
            cedula = st.text_input("Cédula / NIT titular", value=safe_get(exp, 'cedula_titular', '') or '')
            persona_aut = st.text_input("Persona autoriza (si aplica)", value=safe_get(exp, 'persona_autoriza', '') or '')
            apoderado = st.text_input("Apoderado", value=safe_get(exp, 'apoderado', '') or '')
            celular = st.text_input("Celular", value=safe_get(exp, 'celular', '') or '')
        with col2:
            ficha = st.text_input("Ficha catastral", value=safe_get(exp, 'ficha_catastral', '') or '')
            matricula = st.text_input("Matrícula inmobiliaria", value=safe_get(exp, 'matricula_inmobiliaria', '') or '')
            direccion = st.text_input("Dirección", value=safe_get(exp, 'direccion', '') or '')
            barrio = st.text_input("Barrio", value=safe_get(exp, 'barrio', '') or '')
            zona = st.selectbox("Zona", ["", "Centro", "Norte", "Sur", "Oriente", "Poniente", "Residencial", "Industrial", "Comercial"],
                                index=["", "Centro", "Norte", "Sur", "Oriente", "Poniente", "Residencial", "Industrial", "Comercial"].index(
                                    safe_get(exp, 'zona', '') or '') if (safe_get(exp, 'zona') or '') in
                                ["", "Centro", "Norte", "Sur", "Oriente", "Poniente", "Residencial", "Industrial", "Comercial"] else 0)
        with col3:
            superficie = st.number_input("Superficie (m²)", min_value=0.0,
                                         value=float(safe_get(exp, 'superficie') or 0))
            valor = st.number_input("Valor de la obra", min_value=0.0,
                                    value=float(safe_get(exp, 'valor_obra') or 0), step=1000000.0)
            tipo_entrega = st.radio("Tipo entrega planos", ["", "Físico", "Magnético (digital)"],
                                    index=["", "Físico", "Magnético (digital)"].index(safe_get(exp, 'tipo_entrega_planos', '') or '')
                                    if (safe_get(exp, 'tipo_entrega_planos') or '') in ["", "Físico", "Magnético (digital)"] else 0,
                                    horizontal=True)
            correo_ent = st.text_input("Correo entrega (si magnético)", value=safe_get(exp, 'correo_entrega', '') or '')

    # ── Sección 4: Revisiones ──
    with st.expander("4. Revisiones (plazos hábiles)", expanded=expand_all):
        st.caption("Ingresa la fecha de ingreso a revisión jurídica; las demás se calculan automáticamente (5 días jurídica, 8 arquitectura, 8 estructural). Puedes sobrescribirlas.")
        col1, col2, col3 = st.columns(3)
        with col1:
            fi_jur = st.date_input("Fecha ingreso revisión jurídica (5 días hábiles)",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_juridica')),
                                   key=f"{pfx}fi_jur")
            if st.checkbox("Sin fecha ingreso jurídica", value=parse_date(safe_get(exp, 'fecha_ingreso_juridica')) is None, key=f"{pfx}sin_fi_jur"):
                fi_jur = None
            calc = calcular_fechas_revision(fi_jur)
            fs_jur = st.date_input("Fecha salida jurídica",
                                   value=parse_date(safe_get(exp, 'fecha_salida_juridica')) or calc.get("fecha_salida_juridica"),
                                   key=f"{pfx}fs_jur")
            if st.checkbox("Sin fecha salida jurídica", value=False, key=f"{pfx}sin_fs_jur"):
                fs_jur = None
        with col2:
            fi_arq = st.date_input("Fecha ingreso arquitectura (8 días hábiles)",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_arquitectura')) or calc.get("fecha_ingreso_arquitectura"),
                                   key=f"{pfx}fi_arq")
            if st.checkbox("Sin fecha ingreso arq.", value=False, key=f"{pfx}sin_fi_arq"):
                fi_arq = None
            fs_arq = st.date_input("Fecha salida arquitectura",
                                   value=parse_date(safe_get(exp, 'fecha_salida_arquitectura')) or calc.get("fecha_salida_arquitectura"),
                                   key=f"{pfx}fs_arq")
            if st.checkbox("Sin fecha salida arq.", value=False, key=f"{pfx}sin_fs_arq"):
                fs_arq = None
        with col3:
            fi_est = st.date_input("Fecha ingreso revisión estructural",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_estructural')) or calc.get("fecha_ingreso_estructural"),
                                   key=f"{pfx}fi_est")
            if st.checkbox("Sin fecha ingreso est.", value=False, key=f"{pfx}sin_fi_est"):
                fi_est = None
            fs_est = st.date_input("Fecha salida revisión estructural",
                                   value=parse_date(safe_get(exp, 'fecha_salida_estructural')) or calc.get("fecha_salida_estructural"),
                                   key=f"{pfx}fs_est")
            if st.checkbox("Sin fecha salida est.", value=False, key=f"{pfx}sin_fs_est"):
                fs_est = None

        # Días en estudio (automático): se detiene si está Ejecutoriado / Archivado / Negado
        if estado in ("Ejecutoriado", "Archivado", "Negado"):
            # Conservar el valor ya guardado si existe; no seguir contando
            prev = safe_get(exp, "dias_en_estudio")
            try:
                dias_est = int(prev) if prev is not None else 0
            except (TypeError, ValueError):
                dias_est = 0
            st.metric("Días en estudio", dias_est, help="Conteo detenido: expediente ejecutoriado/cerrado.")
            st.caption("⏸️ No se cuentan más días en estudio (estado Ejecutoriado / Archivado / Negado).")
        elif fecha_rad:
            dias_est = dias_habiles_entre(fecha_rad, date.today())
            st.metric("Número de días en estudio (automático)", dias_est)
        else:
            dias_est = 0
            st.metric("Número de días en estudio (automático)", dias_est)

    # ── Sección 5: Acta de observaciones ──
    with st.expander("5. Acta de observaciones y prórroga", expanded=expand_all):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_elab_acta = st.date_input("Fecha elaboración acta observaciones (1ª revisión)",
                                            value=parse_date(safe_get(exp, 'fecha_elaboracion_acta')), key=f"{pfx}fea")
            if st.checkbox("Sin fecha elab. acta", value=parse_date(safe_get(exp, 'fecha_elaboracion_acta')) is None, key=f"{pfx}sin_fea"):
                fecha_elab_acta = None
            num_acta = st.text_input("Número de acta", value=safe_get(exp, 'numero_acta', '') or '', key=f"{pfx}num_acta")
            rad_salida_acta = st.text_input("Radicado de salida acta", value=safe_get(exp, 'radicado_salida_acta', '') or '', key=f"{pfx}rad_salida_acta")
            fecha_rad_acta = st.date_input("Fecha de radicado acta",
                                           value=parse_date(safe_get(exp, 'fecha_radicado_acta')), key=f"{pfx}fra")
            if st.checkbox("Sin fecha rad. acta", value=parse_date(safe_get(exp, 'fecha_radicado_acta')) is None, key=f"{pfx}sin_fra"):
                fecha_rad_acta = None
        with col2:
            rad_prorroga = st.text_input("Radicado oficio prórroga", value=safe_get(exp, 'radicado_oficio_prorroga', '') or '', key=f"{pfx}rad_prorroga")
            fecha_of_prorroga = st.date_input("Fecha oficio prórroga",
                                              value=parse_date(safe_get(exp, 'fecha_oficio_prorroga')), key=f"{pfx}fop")
            if st.checkbox("Sin fecha oficio prórroga", value=parse_date(safe_get(exp, 'fecha_oficio_prorroga')) is None, key=f"{pfx}sin_fop"):
                fecha_of_prorroga = None
            tiene_prorroga = st.selectbox("¿Tiene prórroga?", ["No", "Sí"],
                                          index=0 if safe_get(exp, 'tiene_prorroga', 'No') != 'Sí' else 1,
                                          key=f"{pfx}tiene_prorroga")
            # Vencimiento 30 días hábiles + 15 si prórroga
            base_subs = fecha_rad_acta or fecha_elab_acta
            if base_subs:
                dias_sub = 30 + (15 if tiene_prorroga == "Sí" else 0)
                fv_sub = sumar_dias_habiles(base_subs, dias_sub)
            else:
                fv_sub = parse_date(safe_get(exp, 'fecha_vencimiento_subsanacion'))
            st.text_input("Fecha vencimiento subsanación (30/45 días hábiles)",
                          value=fv_sub.strftime('%Y-%m-%d') if fv_sub else '', disabled=True)
        with col3:
            rad_corr = st.text_input("Radicado entrada corrección", value=safe_get(exp, 'radicado_entrada_correccion', '') or '', key=f"{pfx}rad_corr")
            fecha_rad_corr = st.date_input("Fecha radicado corrección",
                                           value=parse_date(safe_get(exp, 'fecha_radicado_correccion')), key=f"{pfx}frc")
            if st.checkbox("Sin fecha rad. corrección", value=parse_date(safe_get(exp, 'fecha_radicado_correccion')) is None, key=f"{pfx}sin_frc"):
                fecha_rad_corr = None
            fecha_acta_fin = st.date_input("Fecha acta finalización para resolución",
                                           value=parse_date(safe_get(exp, 'fecha_acta_finalizacion')), key=f"{pfx}faf")
            if st.checkbox("Sin fecha acta finalización", value=parse_date(safe_get(exp, 'fecha_acta_finalizacion')) is None, key=f"{pfx}sin_faf"):
                fecha_acta_fin = None

    observaciones = st.text_area("Observaciones generales", value=safe_get(exp, 'observaciones', '') or '', key=f"{pfx}obs")

    # Guardar
    btn_label = "💾 Guardar nuevo expediente" if es_nuevo else "🔄 Actualizar y guardar"
    if st.button(btn_label, type="primary", use_container_width=True, key=f"{pfx}btn_guardar"):
        if es_nuevo and not numero.strip():
            st.error("El número de radicado es obligatorio para crear un expediente.")
            return

        datos = {
            "numero_radicado": numero.strip() if es_nuevo else modo,
            "fecha_radicacion": fmt_date(fecha_rad),
            "modalidad": modalidad,
            "fecha_vencimiento_45": fmt_date(fv45),
            "alerta": alerta,
            "estado": estado,
            "numero_resolucion": num_res or None,
            "fecha_resolucion": fmt_date(fecha_res),
            "pago_30_anticipo": pago30 or None,
            "valor_pago_30": valor_pago30 if valor_pago30 else None,
            "numero_recibo_30": num_recibo30 or None,
            "saldo_70": saldo70 or None,
            "valor_pago_70": valor_pago70 if valor_pago70 else None,
            "numero_recibo_70": num_recibo70 or None,
            "confirma_pago_70": conf70 or None,
            "observaciones_pago": obs_pago.strip() if obs_pago and obs_pago.strip() else None,
            "persona_autoriza": persona_aut or None,
            "propietario": propietario or None,
            "cedula_titular": cedula or None,
            "apoderado": apoderado or None,
            "celular": celular or None,
            "ficha_catastral": ficha or None,
            "matricula_inmobiliaria": matricula or None,
            "direccion": direccion or None,
            "barrio": barrio or None,
            "zona": zona or None,
            "superficie": superficie,
            "valor_obra": valor,
            "tipo_entrega_planos": tipo_entrega or None,
            "correo_entrega": correo_ent or None,
            "fecha_ingreso_juridica": fmt_date(fi_jur),
            "fecha_salida_juridica": fmt_date(fs_jur),
            "fecha_ingreso_arquitectura": fmt_date(fi_arq),
            "fecha_salida_arquitectura": fmt_date(fs_arq),
            "fecha_ingreso_estructural": fmt_date(fi_est),
            "fecha_salida_estructural": fmt_date(fs_est),
            "dias_en_estudio": dias_est,
            "fecha_elaboracion_acta": fmt_date(fecha_elab_acta),
            "numero_acta": num_acta or None,
            "radicado_salida_acta": rad_salida_acta or None,
            "fecha_radicado_acta": fmt_date(fecha_rad_acta),
            "radicado_oficio_prorroga": rad_prorroga or None,
            "fecha_oficio_prorroga": fmt_date(fecha_of_prorroga),
            "fecha_vencimiento_subsanacion": fmt_date(fv_sub),
            "tiene_prorroga": tiene_prorroga,
            "radicado_entrada_correccion": rad_corr or None,
            "fecha_radicado_correccion": fmt_date(fecha_rad_corr),
            "fecha_acta_finalizacion": fmt_date(fecha_acta_fin),
            "observaciones": observaciones or None,
            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tipo_obra": modalidad,  # compatibilidad
        }

        radicado_final = (numero.strip() if es_nuevo else modo).strip()
        if not radicado_final:
            st.error("El número de radicado es obligatorio.")
            return

        datos["numero_radicado"] = radicado_final

        conn = get_connection()
        c = conn.cursor()
        try:
            # Verificar si ya existe ese radicado
            c.execute("SELECT id FROM expedientes WHERE numero_radicado = ?", (radicado_final,))
            existe = c.fetchone()

            if existe:
                # ACTUALIZAR el mismo registro (nunca duplicar)
                sets = ", ".join([f"{k}=?" for k in datos.keys() if k != "numero_radicado"])
                vals = [datos[k] for k in datos.keys() if k != "numero_radicado"] + [radicado_final]
                c.execute(f"UPDATE expedientes SET {sets} WHERE numero_radicado=?", vals)
                conn.commit()
                st.session_state["msg_guardado"] = f"Expediente **{radicado_final}** actualizado correctamente (mismo registro, sin duplicar)."
            else:
                # INSERTAR solo si no existe
                cols = list(datos.keys())
                placeholders = ",".join(["?"] * len(cols))
                c.execute(
                    f"INSERT INTO expedientes ({','.join(cols)}) VALUES ({placeholders})",
                    [datos[k] for k in cols],
                )
                conn.commit()
                st.session_state["msg_guardado"] = f"Expediente **{radicado_final}** creado correctamente."
            st.session_state["ofrecer_backup"] = True
        except sqlite3.IntegrityError:
            # Seguridad extra por si hay condición de carrera
            st.error(f"Ya existe un expediente con el radicado **{radicado_final}**. No se duplicó el registro.")
            conn.rollback()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
            conn.rollback()
        finally:
            conn.close()
        st.rerun()

# ─────────────────────────────────────────────
# Listado de expedientes
# ─────────────────────────────────────────────
def pagina_expedientes():
    st.title("📁 Expedientes")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    if df.empty:
        st.info("No hay expedientes. Crea uno desde «Nuevo expediente».")
        return

    col1, col2 = st.columns(2)
    with col1:
        estados = ["Todos"] + sorted([x for x in df['estado'].dropna().unique().tolist() if x])
        filtro_estado = st.selectbox("Estado", estados)
    with col2:
        filtro_texto = st.text_input("Buscar (radicado, propietario, cédula, ficha…)")

    df_f = df.copy()
    if filtro_estado != "Todos":
        df_f = df_f[df_f['estado'] == filtro_estado]
    if filtro_texto:
        mask = (
            df_f['numero_radicado'].astype(str).str.contains(filtro_texto, case=False, na=False) |
            df_f['propietario'].astype(str).str.contains(filtro_texto, case=False, na=False) |
            df_f.get('cedula_titular', pd.Series([''] * len(df_f))).astype(str).str.contains(filtro_texto, case=False, na=False) |
            df_f.get('ficha_catastral', pd.Series([''] * len(df_f))).astype(str).str.contains(filtro_texto, case=False, na=False)
        )
        df_f = df_f[mask]

    cols_show = [c for c in ['numero_radicado', 'fecha_radicacion', 'modalidad', 'estado', 'propietario',
                             'fecha_vencimiento_45', 'alerta', 'numero_resolucion',
                             'aprobacion_juridica', 'aprobacion_arquitectura', 'aprobacion_ingenieria']
                 if c in df_f.columns]
    st.dataframe(df_f[cols_show].head(80), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# Roles profesionales (solo lectura + aprobación)
# ─────────────────────────────────────────────
def es_revisor_profesional(rol=None):
    """Revisores de área: solo ven información y aprueban por radicado."""
    rol = rol or st.session_state.get("rol", "")
    return any(x in rol for x in ("Jurídico", "Arquitectónico", "Ingeniería")) and rol != "Administrador"


def _mostrar_info_expediente_solo_lectura(exp):
    """Muestra los datos del expediente sin campos editables."""
    st.subheader("📋 Información del expediente (solo lectura)")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**N° Radicado:** {safe_get(exp, 'numero_radicado') or '—'}")
        st.markdown(f"**Fecha radicación:** {safe_get(exp, 'fecha_radicacion') or '—'}")
        st.markdown(f"**Modalidad:** {safe_get(exp, 'modalidad') or '—'}")
        st.markdown(f"**Estado:** {safe_get(exp, 'estado') or '—'}")
        st.markdown(f"**Vencimiento 45 días:** {safe_get(exp, 'fecha_vencimiento_45') or '—'}")
        st.markdown(f"**Alerta:** {safe_get(exp, 'alerta') or '—'}")
    with c2:
        st.markdown(f"**Propietario:** {safe_get(exp, 'propietario') or '—'}")
        st.markdown(f"**Cédula / NIT:** {safe_get(exp, 'cedula_titular') or '—'}")
        st.markdown(f"**Apoderado:** {safe_get(exp, 'apoderado') or '—'}")
        st.markdown(f"**Celular:** {safe_get(exp, 'celular') or '—'}")
        st.markdown(f"**Dirección:** {safe_get(exp, 'direccion') or '—'}")
        st.markdown(f"**Barrio:** {safe_get(exp, 'barrio') or '—'}")
        st.markdown(f"**Zona:** {safe_get(exp, 'zona') or '—'}")
    with c3:
        st.markdown(f"**Ficha catastral:** {safe_get(exp, 'ficha_catastral') or '—'}")
        st.markdown(f"**Matrícula:** {safe_get(exp, 'matricula_inmobiliaria') or '—'}")
        st.markdown(f"**Superficie:** {safe_get(exp, 'superficie') or '—'}")
        st.markdown(f"**Valor obra:** {safe_get(exp, 'valor_obra') or '—'}")
        st.markdown(f"**N° Resolución:** {safe_get(exp, 'numero_resolucion') or '—'}")
        st.markdown(f"**Fecha resolución:** {safe_get(exp, 'fecha_resolucion') or '—'}")

    with st.expander("Pagos", expanded=False):
        st.write(
            f"30%: **{safe_get(exp, 'pago_30_anticipo') or '—'}** | "
            f"Valor: {safe_get(exp, 'valor_pago_30') or '—'} | "
            f"Recibo: {safe_get(exp, 'numero_recibo_30') or '—'}"
        )
        st.write(
            f"70%: **{safe_get(exp, 'saldo_70') or '—'}** | "
            f"Valor: {safe_get(exp, 'valor_pago_70') or '—'} | "
            f"Recibo: {safe_get(exp, 'numero_recibo_70') or '—'}"
        )
        st.write(f"Confirma 70%: {safe_get(exp, 'confirma_pago_70') or '—'}")
        _op = safe_get(exp, "observaciones_pago")
        if _op:
            st.write(f"**Observaciones de pago:** {_op}")

    with st.expander("Revisiones y plazos", expanded=False):
        st.write(f"Ingreso jurídica: {safe_get(exp, 'fecha_ingreso_juridica') or '—'} → Salida: {safe_get(exp, 'fecha_salida_juridica') or '—'}")
        st.write(f"Ingreso arquitectura: {safe_get(exp, 'fecha_ingreso_arquitectura') or '—'} → Salida: {safe_get(exp, 'fecha_salida_arquitectura') or '—'}")
        st.write(f"Ingreso estructural: {safe_get(exp, 'fecha_ingreso_estructural') or '—'} → Salida: {safe_get(exp, 'fecha_salida_estructural') or '—'}")
        st.write(f"Días en estudio: {safe_get(exp, 'dias_en_estudio') or '—'}")

    with st.expander("Aprobaciones registradas", expanded=True):
        st.write(f"Jurídica: **{safe_get(exp, 'aprobacion_juridica') or 'Pendiente'}**")
        st.write(f"Arquitectura: **{safe_get(exp, 'aprobacion_arquitectura') or 'Pendiente'}**")
        st.write(f"Ingeniería: **{safe_get(exp, 'aprobacion_ingenieria') or 'Pendiente'}**")

    with st.expander("Observaciones", expanded=False):
        st.text(safe_get(exp, 'observaciones') or "Sin observaciones.")


# ─────────────────────────────────────────────
# Aprobaciones por área (profesionales: solo aprobar)
# ─────────────────────────────────────────────
def pagina_aprobaciones():
    st.title("✅ Aprobaciones por Área")
    st.write(f"Usuario: **{st.session_state['nombre']}** ({st.session_state['rol']})")
    st.caption("Los profesionales solo pueden **consultar** el expediente y **registrar su aprobación** por número de radicado. No pueden modificar otros datos.")

    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    if df.empty:
        st.info("No hay expedientes.")
        return

    rol = st.session_state['rol']
    if "Jurídico" in rol:
        campo, titulo = "aprobacion_juridica", "Aprobación Jurídica"
    elif "Arquitectónico" in rol:
        campo, titulo = "aprobacion_arquitectura", "Aprobación Arquitectónica"
    elif "Ingeniería" in rol:
        campo, titulo = "aprobacion_ingenieria", "Aprobación de Ingeniería"
    else:
        st.info("Esta sección es para revisores de Jurídica, Arquitectura e Ingeniería.")
        cols = [c for c in ['numero_radicado', 'propietario', 'estado',
                            'aprobacion_juridica', 'aprobacion_arquitectura', 'aprobacion_ingenieria']
                if c in df.columns]
        st.dataframe(df[cols].head(50), use_container_width=True, hide_index=True)
        return

    st.subheader(titulo)
    # Buscar / seleccionar solo por radicado
    busqueda = st.text_input("Buscar por número de radicado", key="apr_buscar_rad")
    lista = df['numero_radicado'].astype(str).tolist()
    if busqueda:
        lista = [r for r in lista if busqueda.strip().lower() in r.lower()]
        if not lista:
            st.warning("No se encontró ningún radicado con ese criterio.")
            return
    sel = st.selectbox("Seleccionar número de radicado", lista, key="apr_sel_rad")
    exp = df[df['numero_radicado'].astype(str) == str(sel)].iloc[0]

    _mostrar_info_expediente_solo_lectura(exp)

    st.divider()
    st.subheader(f"Registrar {titulo}")
    st.write(f"**Aprobación actual de tu área:** {safe_get(exp, campo, 'Pendiente') or 'Pendiente'}")
    decision = st.radio(
        "Tu decisión",
        ["Pendiente", "Aprobado", "Rechazado", "Con observaciones"],
        horizontal=True,
        key="apr_decision",
    )
    obs = st.text_area("Observaciones de tu revisión (opcional)", key="apr_obs")
    if st.button("✅ Registrar mi aprobación", type="primary", use_container_width=True):
        conn = get_connection()
        c = conn.cursor()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute(
            f"UPDATE expedientes SET {campo}=?, ultima_actualizacion=? WHERE numero_radicado=?",
            (decision, ahora, sel),
        )
        if obs and obs.strip():
            prev = safe_get(exp, 'observaciones') or ''
            c.execute(
                "UPDATE expedientes SET observaciones=? WHERE numero_radicado=?",
                (prev + f"\n[{campo} {ahora}] {obs.strip()}", sel),
            )
        conn.commit()
        conn.close()
        st.success(f"Aprobación registrada: **{decision}** para el radicado **{sel}**")
        st.rerun()

# ─────────────────────────────────────────────
# Proyección de acto administrativo
# ─────────────────────────────────────────────
def pagina_proyeccion():
    st.title("📝 Proyección de Acto Administrativo")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    if df.empty:
        st.info("No hay expedientes.")
        return

    sel = st.selectbox("Seleccionar expediente", df['numero_radicado'].tolist(), key="proy_sel")
    exp = df[df['numero_radicado'] == sel].iloc[0]

    st.subheader("Datos precargados del expediente")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**Radicado:** {sel}")
        st.write(f"**Fecha radicado:** {safe_get(exp, 'fecha_radicacion')}")
        st.write(f"**Propietario:** {safe_get(exp, 'propietario')}")
        st.write(f"**Estado:** {safe_get(exp, 'estado')}")
    with col2:
        st.write(f"**Modalidad:** {safe_get(exp, 'modalidad')}")
        st.write(f"**Dirección:** {safe_get(exp, 'direccion')}")
        st.write(f"**Barrio:** {safe_get(exp, 'barrio')}")
    with col3:
        st.write(f"**Ficha catastral:** {safe_get(exp, 'ficha_catastral')}")
        st.write(f"**Matrícula:** {safe_get(exp, 'matricula_inmobiliaria')}")
        st.write(f"**N° Resolución:** {safe_get(exp, 'numero_resolucion')}")

    st.divider()
    st.subheader("Datos del acto administrativo")

    col1, col2, col3 = st.columns(3)
    with col1:
        num_res = st.text_input("Número de resolución", value=safe_get(exp, 'numero_resolucion', '') or '', key="proy_nr")
        fecha_res = st.date_input("Fecha resolución", value=parse_date(safe_get(exp, 'fecha_resolucion')), key="proy_fr")
        if st.checkbox("Sin fecha resolución", value=parse_date(safe_get(exp, 'fecha_resolucion')) is None, key="proy_sin_fr"):
            fecha_res = None
        area_predio = st.number_input("Área del predio (m²)", min_value=0.0,
                                      value=float(safe_get(exp, 'area_predio') or safe_get(exp, 'superficie') or 0))
        area_libre = st.number_input("Área libre (m²)", min_value=0.0, value=float(safe_get(exp, 'area_libre') or 0))
        n_pisos = st.number_input("Número de pisos", min_value=0, value=int(safe_get(exp, 'numero_pisos') or 0))
        n_viv = st.number_input("Número de vivienda", min_value=0, value=int(safe_get(exp, 'numero_vivienda') or 0))
    with col2:
        area_p1 = st.number_input("Área primer piso (m²)", min_value=0.0, value=float(safe_get(exp, 'area_primer_piso') or 0))
        area_p2 = st.number_input("Área segundo piso (m²)", min_value=0.0, value=float(safe_get(exp, 'area_segundo_piso') or 0))
        es_ampliacion = safe_get(exp, 'modalidad', '') in ("Ampliación", "Remodelación")
        area_exist = st.number_input("Área existente (m²)", min_value=0.0,
                                     value=float(safe_get(exp, 'area_existente') or 0),
                                     disabled=not es_ampliacion and not safe_get(exp, 'area_existente'))
        area_ampl = st.number_input("Área ampliación (m²)", min_value=0.0,
                                    value=float(safe_get(exp, 'area_ampliacion') or 0))
        area_tot_ampl = st.number_input("Área total ampliación (m²)", min_value=0.0,
                                        value=float(safe_get(exp, 'area_total_ampliacion') or 0))
        area_tot_const = st.number_input("Área total construida (m²)", min_value=0.0,
                                         value=float(safe_get(exp, 'area_total_construida') or 0))
    with col3:
        idx_oc = st.number_input("Índice de ocupación (2 decimales)", min_value=0.0, max_value=1.0,
                                 value=round(float(safe_get(exp, 'indice_ocupacion') or 0), 2), format="%.2f", step=0.01)
        idx_const = st.number_input("Índice de construcción (2 decimales)", min_value=0.0,
                                    value=round(float(safe_get(exp, 'indice_construccion') or 0), 2), format="%.2f", step=0.01)
        sector = st.selectbox("Sector", ["", "Residencial", "Comercial", "Mixta", "Industrial", "Institucional", "Otro"],
                              index=["", "Residencial", "Comercial", "Mixta", "Industrial", "Institucional", "Otro"].index(
                                  safe_get(exp, 'sector', '') or '') if (safe_get(exp, 'sector') or '') in
                              ["", "Residencial", "Comercial", "Mixta", "Industrial", "Institucional", "Otro"] else 0)
        ubicacion = st.selectbox("Ubicación del predio", ["", "Urbano", "Suburbano", "Rural"],
                                 index=["", "Urbano", "Suburbano", "Rural"].index(safe_get(exp, 'ubicacion_predio', '') or '')
                                 if (safe_get(exp, 'ubicacion_predio') or '') in ["", "Urbano", "Suburbano", "Rural"] else 0)
        prof_arq = st.text_input("Profesional responsable diseño arquitectónico",
                                 value=safe_get(exp, 'profesional_arquitectonico', '') or '')
        prof_est = st.text_input("Profesional responsable diseños estructurales",
                                 value=safe_get(exp, 'profesional_estructural', '') or '')
        cant_arq = st.number_input("Cantidad planos arquitectónicos", min_value=0,
                                   value=int(safe_get(exp, 'cantidad_planos_arq') or 0))
        cant_est = st.number_input("Cantidad planos estructurales", min_value=0,
                                   value=int(safe_get(exp, 'cantidad_planos_est') or 0))

    desc = st.text_area(
        "Descripción del acto (paz y salvo, certificado de libertad y tradición, descripción por pisos, etc.)",
        value=safe_get(exp, 'descripcion_acto', '') or '',
        height=200
    )

    if st.button("💾 Guardar proyección de acto", type="primary"):
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE expedientes SET
                numero_resolucion=?, fecha_resolucion=?,
                area_predio=?, area_libre=?, numero_pisos=?, numero_vivienda=?,
                area_primer_piso=?, area_segundo_piso=?,
                area_existente=?, area_ampliacion=?, area_total_ampliacion=?, area_total_construida=?,
                indice_ocupacion=?, indice_construccion=?,
                sector=?, ubicacion_predio=?,
                profesional_arquitectonico=?, profesional_estructural=?,
                cantidad_planos_arq=?, cantidad_planos_est=?,
                descripcion_acto=?,
                estado=CASE WHEN estado IN ('Radicado','En revisión','Subsanación','En Acta de Observaciones')
                            THEN 'Acto proyectado' ELSE estado END,
                ultima_actualizacion=?
            WHERE numero_radicado=?
        ''', (
            num_res or None, fmt_date(fecha_res),
            area_predio, area_libre, n_pisos, n_viv,
            area_p1, area_p2,
            area_exist, area_ampl, area_tot_ampl, area_tot_const,
            round(idx_oc, 2), round(idx_const, 2),
            sector or None, ubicacion or None,
            prof_arq or None, prof_est or None,
            cant_arq, cant_est,
            desc or None,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            sel
        ))
        conn.commit()
        conn.close()
        st.success("Proyección de acto administrativo guardada.")
        st.rerun()

# ─────────────────────────────────────────────
# Control de firmas
# ─────────────────────────────────────────────
def pagina_firmas():
    st.title("✍️ Control de Firmas y Sellos")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    if df.empty:
        st.info("No hay expedientes.")
        return

    sel = st.selectbox("Seleccionar expediente", df['numero_radicado'].tolist(), key="firma_sel")
    exp = df[df['numero_radicado'] == sel].iloc[0]
    modalidad = safe_get(exp, 'modalidad', '')

    st.write(f"**Propietario:** {safe_get(exp, 'propietario')}  |  **Modalidad:** {modalidad}  |  **Estado:** {safe_get(exp, 'estado')}")

    # Determinar quién debe firmar según modalidad
    st.subheader("¿Quién debe firmar? (según tipo de proyecto)")
    es_obra = modalidad not in ("Re-subdivisión", "Urbanización", "Parcelación")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        req_jur = st.checkbox("Requiere firma Jurídico",
                              value=safe_get(exp, 'requiere_firma_juridico', 'Sí' if es_obra else 'No') == 'Sí')
    with col2:
        req_arq = st.checkbox("Requiere firma Arquitecto",
                              value=safe_get(exp, 'requiere_firma_arquitecto', 'Sí') == 'Sí')
    with col3:
        req_ing = st.checkbox("Requiere firma Ingeniero estructural",
                              value=safe_get(exp, 'requiere_firma_ingeniero', 'Sí' if es_obra else 'No') == 'Sí')
    with col4:
        st.checkbox("Firma Jefe de Planeación (siempre)", value=True, disabled=True)

    st.divider()
    st.subheader("Estado de firmas")
    rol = st.session_state['rol']
    nombre = st.session_state['nombre']

    def registrar_firma(campo, fecha_campo, etiqueta):
        actual = safe_get(exp, campo, 'No')
        st.write(f"**{etiqueta}:** {'✅ Firmado' if actual == 'Sí' else '⏳ Pendiente'}")
        if actual == 'Sí':
            st.caption(f"Fecha: {safe_get(exp, fecha_campo)}")
        puede = (
            (campo == 'firma_juridico' and ("Jurídico" in rol or rol == "Administrador")) or
            (campo == 'firma_arquitecto' and ("Arquitectónico" in rol or rol == "Administrador")) or
            (campo == 'firma_ingeniero' and ("Ingeniería" in rol or rol == "Administrador")) or
            (campo == 'firma_jefe_planeacion' and (rol in ("Jefe de Planeación", "Administrador")))
        )
        if puede and actual != 'Sí':
            if st.button(f"Firmar como {etiqueta}", key=f"btn_{campo}"):
                conn = get_connection()
                c = conn.cursor()
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                c.execute(f"UPDATE expedientes SET {campo}=?, {fecha_campo}=?, ultima_actualizacion=? WHERE numero_radicado=?",
                          ('Sí', ahora, ahora, sel))
                c.execute("INSERT INTO historial_firmas (numero_radicado, firmante, rol_firmante, fecha_firma, accion) VALUES (?,?,?,?,?)",
                          (sel, nombre, rol, ahora, f"Firmó {etiqueta}"))
                # Actualizar estado si todas las requeridas están firmadas
                c.execute("SELECT firma_juridico, firma_arquitecto, firma_ingeniero, firma_jefe_planeacion, requiere_firma_juridico, requiere_firma_arquitecto, requiere_firma_ingeniero FROM expedientes WHERE numero_radicado=?", (sel,))
                row = c.fetchone()
                if row:
                    fj, fa, fi, fjp, rj, ra, ri = row
                    ok = True
                    if (rj or 'Sí') == 'Sí' and fj != 'Sí':
                        ok = False
                    if (ra or 'Sí') == 'Sí' and fa != 'Sí':
                        ok = False
                    if (ri or 'Sí') == 'Sí' and fi != 'Sí':
                        ok = False
                    if fjp != 'Sí':
                        ok = False
                    if ok:
                        c.execute("UPDATE expedientes SET estado=? WHERE numero_radicado=?", ('Resolución firmada', sel))
                    else:
                        c.execute("UPDATE expedientes SET estado=? WHERE numero_radicado=?", ('En firmas', sel))
                conn.commit()
                conn.close()
                st.success(f"{etiqueta} firmado por {nombre}")
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if req_jur:
            registrar_firma('firma_juridico', 'fecha_firma_juridico', 'Jurídico')
        if req_arq:
            registrar_firma('firma_arquitecto', 'fecha_firma_arquitecto', 'Arquitecto')
    with col2:
        if req_ing:
            registrar_firma('firma_ingeniero', 'fecha_firma_ingeniero', 'Ingeniero estructural')
        registrar_firma('firma_jefe_planeacion', 'fecha_firma_jefe', 'Jefe de Planeación')

    st.divider()
    st.subheader("Planos")
    col1, col2 = st.columns(2)
    with col1:
        planos_sellados = st.selectbox("¿Planos sellados?", ["No", "Sí"],
                                       index=0 if safe_get(exp, 'planos_sellados', 'No') != 'Sí' else 1)
    with col2:
        op_planos = st.text_input("Operación de planos (observaciones)", value=safe_get(exp, 'operacion_planos', '') or '')

    if st.button("Guardar control de planos y requisitos de firma"):
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE expedientes SET
                planos_sellados=?, operacion_planos=?,
                requiere_firma_juridico=?, requiere_firma_arquitecto=?, requiere_firma_ingeniero=?,
                ultima_actualizacion=?
            WHERE numero_radicado=?
        ''', (
            planos_sellados, op_planos or None,
            'Sí' if req_jur else 'No', 'Sí' if req_arq else 'No', 'Sí' if req_ing else 'No',
            datetime.now().strftime("%Y-%m-%d %H:%M"), sel
        ))
        conn.commit()
        conn.close()
        st.success("Control de planos y requisitos actualizado.")
        st.rerun()

    # Historial
    conn = get_connection()
    hist = pd.read_sql_query(
        "SELECT * FROM historial_firmas WHERE numero_radicado=? ORDER BY id DESC",
        conn, params=(sel,))
    conn.close()
    if not hist.empty:
        st.subheader("Historial de firmas")
        st.dataframe(hist[['firmante', 'rol_firmante', 'fecha_firma', 'accion']], use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# Notificación, publicación y entrega
# ─────────────────────────────────────────────
def pagina_notificacion():
    st.title("📬 Notificación, Publicación, Entrega y Archivo Físico")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    if df.empty:
        st.info("No hay expedientes.")
        return

    sel = st.selectbox("Seleccionar expediente", df['numero_radicado'].tolist(), key="notif_sel")
    exp = df[df['numero_radicado'] == sel].iloc[0]
    st.write(f"**Propietario:** {safe_get(exp, 'propietario')}  |  **Estado:** {safe_get(exp, 'estado')}  |  **Modalidad:** {safe_get(exp, 'modalidad')}")

    # 1. Oficio de solicitud de presentación
    with st.expander("1. Oficio de solicitud de presentación en oficina (notificación)", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            oficio_sol = st.text_input("N° Oficio solicitud de notificación",
                                       value=safe_get(exp, 'oficio_solicitud_notificacion', '') or '')
            fecha_oficio = st.date_input("Fecha oficio solicitud",
                                         value=parse_date(safe_get(exp, 'fecha_oficio_notificacion')), key="fon")
            if st.checkbox("Sin fecha oficio", value=parse_date(safe_get(exp, 'fecha_oficio_notificacion')) is None, key="sin_fon"):
                fecha_oficio = None
        with col2:
            st.info("Tras generar el oficio, el titular debe presentarse en la oficina para la notificación personal.")

    # 2. Notificación personal
    with st.expander("2. Notificación personal"):
        fecha_notif = st.date_input("Fecha de notificación personal",
                                    value=parse_date(safe_get(exp, 'fecha_notificacion_personal')), key="fnp")
        if st.checkbox("Sin fecha notificación", value=parse_date(safe_get(exp, 'fecha_notificacion_personal')) is None, key="sin_fnp"):
            fecha_notif = None
        _ov = safe_get(exp, 'oficio_fijacion_valla', '') or ''
        # Solo Sí / No (si había texto antiguo se interpreta como Sí)
        if _ov not in ("", "Sí", "No"):
            _ov = "Sí"
        oficio_valla = st.radio(
            "Oficio de solicitud de fijación de valla",
            ["No", "Sí"],
            index=1 if _ov == "Sí" else 0,
            horizontal=True,
            key="oficio_valla_si_no",
        )
        st.caption("Marca si se entregó o no el oficio de fijación de valla.")

    # 3. Soportes de publicación
    with st.expander("3. Soportes de publicación (según tipo de licencia)"):
        col1, col2 = st.columns(2)
        with col1:
            soporte_emisora = st.selectbox("Soporte publicación en emisora",
                                           ["", "Sí", "No", "No aplica"],
                                           index=["", "Sí", "No", "No aplica"].index(
                                               safe_get(exp, 'soporte_publicacion_emisora', '') or '')
                                           if (safe_get(exp, 'soporte_publicacion_emisora') or '') in
                                           ["", "Sí", "No", "No aplica"] else 0)
            foto_valla = st.selectbox("Foto de la valla en el lugar de la obra",
                                      ["", "Sí", "No", "No aplica"],
                                      index=["", "Sí", "No", "No aplica"].index(
                                          safe_get(exp, 'foto_valla', '') or '')
                                      if (safe_get(exp, 'foto_valla') or '') in ["", "Sí", "No", "No aplica"] else 0)
        with col2:
            link_pub = st.text_input("Link de publicación (acto en página web de la Alcaldía)",
                                     value=safe_get(exp, 'link_publicacion', '') or '')

    # 4. Ejecutoria
    with st.expander("4. Ejecutoria"):
        col1, col2 = st.columns(2)
        with col1:
            tiene_ej = st.selectbox("¿Tiene ejecutoria?", ["", "Sí", "No"],
                                    index=["", "Sí", "No"].index(safe_get(exp, 'tiene_ejecutoria', '') or '')
                                    if (safe_get(exp, 'tiene_ejecutoria') or '') in ["", "Sí", "No"] else 0)
        with col2:
            fecha_ej = st.date_input("Fecha de ejecutoria",
                                     value=parse_date(safe_get(exp, 'fecha_ejecutoria')), key="fej")
            if st.checkbox("Sin fecha ejecutoria", value=parse_date(safe_get(exp, 'fecha_ejecutoria')) is None, key="sin_fej"):
                fecha_ej = None

    # 5. Entrega (cumplimiento — no cambia el estado del expediente)
    with st.expander("5. Entrega (cumplimiento)"):
        st.caption("La entrega es un **cumplimiento** independiente del estado del flujo. No se usa «Entrega final» como estado.")
        col1, col2, col3 = st.columns(3)
        with col1:
            entrega_ok = st.checkbox(
                "✅ Entrega cumplida (ya fue entregado)",
                value=(safe_get(exp, 'entrega_cumplida', '') == 'Sí'),
                key="entrega_cumplida_chk",
            )
        with col2:
            fecha_ent = st.date_input("Fecha de entrega",
                                      value=parse_date(safe_get(exp, 'fecha_entrega_final')), key="fef")
            if st.checkbox("Sin fecha entrega", value=parse_date(safe_get(exp, 'fecha_entrega_final')) is None, key="sin_fef"):
                fecha_ent = None
        with col3:
            persona_rec = st.text_input("Persona que recibe", value=safe_get(exp, 'persona_recibe', '') or '')

    # 6. Archivo físico (después de ejecutoria)
    UBICACIONES_ARCHIVO = ["", "Archivo de gestión", "Mesa nene", "Archivo general"]
    with st.expander("6. Archivo físico", expanded=True):
        st.caption(
            "Control de archivo físico del expediente **después de la ejecutoria**: "
            "cantidad de tomos, folios, número de caja y ubicación donde se archiva."
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            arch_tomos = st.number_input(
                "Cantidad de tomos",
                min_value=0,
                value=int(safe_get(exp, "archivo_tomos") or 0),
                step=1,
                key="arch_tomos",
            )
        with col2:
            arch_folios = st.number_input(
                "Cantidad de folios",
                min_value=0,
                value=int(safe_get(exp, "archivo_folios") or 0),
                step=1,
                key="arch_folios",
            )
        with col3:
            arch_caja = st.text_input(
                "Número de caja",
                value=safe_get(exp, "archivo_numero_caja", "") or "",
                key="arch_caja",
            )
        with col4:
            _ubi = safe_get(exp, "archivo_ubicacion", "") or ""
            if _ubi not in UBICACIONES_ARCHIVO:
                _ubi = ""
            arch_ubicacion = st.selectbox(
                "Ubicación de la caja",
                UBICACIONES_ARCHIVO,
                index=UBICACIONES_ARCHIVO.index(_ubi),
                key="arch_ubicacion",
                help="Archivo de gestión · Mesa nene · Archivo general",
            )

    if st.button("💾 Guardar notificación / publicación / entrega / archivo", type="primary"):
        # Estado del flujo (sin usar «Entrega final»)
        nuevo_estado = safe_get(exp, 'estado')
        if tiene_ej == "Sí" or fecha_ej:
            nuevo_estado = "Ejecutoriado"
        elif fecha_notif:
            nuevo_estado = "Notificado"
        elif oficio_sol:
            nuevo_estado = "Oficio de notificación"
        # Si el estado anterior era el viejo "Entrega final", normalizar
        if nuevo_estado == "Entrega final":
            nuevo_estado = "Ejecutoriado"
        # Si se registró archivo físico con ubicación, marcar como Archivado
        if arch_ubicacion and (arch_tomos or arch_folios or arch_caja):
            nuevo_estado = "Archivado"

        conn = get_connection()
        c = conn.cursor()
        # Si queda Ejecutoriado/cerrado, apagar alerta
        alerta_upd = "—" if nuevo_estado in ("Ejecutoriado", "Archivado", "Negado") else safe_get(exp, "alerta")

        c.execute('''
            UPDATE expedientes SET
                oficio_solicitud_notificacion=?, fecha_oficio_notificacion=?,
                fecha_notificacion_personal=?, oficio_fijacion_valla=?,
                soporte_publicacion_emisora=?, foto_valla=?, link_publicacion=?,
                tiene_ejecutoria=?, fecha_ejecutoria=?,
                fecha_entrega_final=?, persona_recibe=?, entrega_cumplida=?,
                archivo_tomos=?, archivo_folios=?, archivo_numero_caja=?, archivo_ubicacion=?,
                estado=?, alerta=?, ultima_actualizacion=?
            WHERE numero_radicado=?
        ''', (
            oficio_sol or None, fmt_date(fecha_oficio),
            fmt_date(fecha_notif), oficio_valla or None,
            soporte_emisora or None, foto_valla or None, link_pub or None,
            tiene_ej or None, fmt_date(fecha_ej),
            fmt_date(fecha_ent), persona_rec or None,
            "Sí" if entrega_ok else "No",
            arch_tomos if arch_tomos else None,
            arch_folios if arch_folios else None,
            arch_caja or None,
            arch_ubicacion or None,
            nuevo_estado,
            alerta_upd,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            sel
        ))
        conn.commit()
        conn.close()
        st.success("Datos de notificación, publicación, entrega y archivo físico guardados.")
        st.rerun()

# ─────────────────────────────────────────────
# Reportes
# ─────────────────────────────────────────────
COLS_BASE = [
    "numero_radicado", "fecha_radicacion", "modalidad", "estado", "propietario",
    "cedula_titular", "direccion", "barrio", "fecha_vencimiento_45", "alerta",
    "numero_resolucion",
]

COLS_PAGOS = COLS_BASE + [
    "pago_30_anticipo", "valor_pago_30", "numero_recibo_30",
    "saldo_70", "valor_pago_70", "numero_recibo_70", "confirma_pago_70",
    "observaciones_pago", "valor_obra",
]

COLS_VENC = COLS_BASE + ["dias_en_estudio", "fecha_ingreso_juridica", "fecha_vencimiento_subsanacion"]

def _df_existentes(df, cols):
    return [c for c in cols if c in df.columns]

def _descargar_reporte(df_rep, nombre_base):
    st.subheader("Descargar")
    c1, c2 = st.columns(2)
    csv_data = df_rep.to_csv(index=False).encode("utf-8-sig")
    with c1:
        st.download_button(
            "⬇️ CSV",
            data=csv_data,
            file_name=f"{nombre_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_csv_{nombre_base}",
        )
    try:
        from io import BytesIO
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_rep.to_excel(writer, index=False, sheet_name="Reporte")
        buf.seek(0)
        with c2:
            st.download_button(
                "⬇️ Excel",
                data=buf,
                file_name=f"{nombre_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"dl_xlsx_{nombre_base}",
            )
    except Exception:
        with c2:
            st.caption("Instala openpyxl para Excel.")

def pagina_reportes():
    st.title("📑 Reportes")
    st.caption("Reportes fijos por estado, pagos, mes, vencidas y próximas a vencer.")

    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM expedientes ORDER BY id DESC", conn)
    except Exception as e:
        st.error(f"No se pudo leer la base de datos: {e}")
        conn.close()
        return
    conn.close()

    if df.empty:
        st.warning("No hay expedientes registrados todavía.")
        return

    # Normalizar estados antiguos "Entrega final"
    if "estado" in df.columns:
        df["estado"] = df["estado"].replace({"Entrega final": "Ejecutoriado"})

    tipo = st.radio(
        "Tipo de reporte",
        [
            "Por estado de licencia",
            "Por pagos y pendientes",
            "Por mes de radicación",
            "Vencidas",
            "Próximas a vencer",
        ],
        horizontal=False,
        key="tipo_reporte",
    )

    hoy = date.today()
    df_rep = pd.DataFrame()
    titulo = tipo

    # ── Por estado ──
    if tipo == "Por estado de licencia":
        estados_disp = ["Todos"] + sorted([x for x in df["estado"].dropna().unique().tolist() if x and x != "Entrega final"])
        sel = st.multiselect("Estado(s)", estados_disp, default=["Todos"], key="rep_estados")
        df_rep = df.copy()
        if sel and "Todos" not in sel:
            df_rep = df_rep[df_rep["estado"].isin(sel)]
        cols = _df_existentes(df_rep, COLS_BASE + ["entrega_cumplida", "fecha_entrega_final"])
        df_rep = df_rep[cols] if cols else df_rep
        st.write("**Resumen por estado**")
        if "estado" in df.columns:
            st.dataframe(df["estado"].value_counts().rename_axis("Estado").reset_index(name="Cantidad"),
                         use_container_width=True, hide_index=True)

    # ── Pagos ──
    elif tipo == "Por pagos y pendientes":
        sub = st.radio(
            "Filtro de pagos",
            ["Todos", "Solo pagos completos (30% y 70% = Sí)", "Pagos pendientes (30% o 70% pendiente/no)", "Sin registro de pago"],
            key="rep_pago_filtro",
        )
        df_rep = df.copy()
        p30 = df_rep.get("pago_30_anticipo", pd.Series([""] * len(df_rep))).astype(str).str.strip()
        s70 = df_rep.get("saldo_70", pd.Series([""] * len(df_rep))).astype(str).str.strip()
        if sub == "Solo pagos completos (30% y 70% = Sí)":
            df_rep = df_rep[(p30 == "Sí") & (s70 == "Sí")]
        elif sub == "Pagos pendientes (30% o 70% pendiente/no)":
            df_rep = df_rep[
                p30.isin(["", "No", "Pendiente"]) | s70.isin(["", "No", "Pendiente"])
            ]
        elif sub == "Sin registro de pago":
            df_rep = df_rep[(p30 == "") | (p30 == "None") | p30.isna()]
        cols = _df_existentes(df_rep, COLS_PAGOS)
        df_rep = df_rep[cols] if cols else df_rep
        # Métricas
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Registros en reporte", len(df_rep))
        with m2:
            if "valor_pago_30" in df.columns:
                st.metric("Suma valores 30%", f"$ {pd.to_numeric(df_rep.get('valor_pago_30', 0), errors='coerce').fillna(0).sum():,.0f}")
        with m3:
            if "valor_pago_70" in df.columns:
                st.metric("Suma valores 70%", f"$ {pd.to_numeric(df_rep.get('valor_pago_70', 0), errors='coerce').fillna(0).sum():,.0f}")

    # ── Por mes ──
    elif tipo == "Por mes de radicación":
        años = sorted({
            str(parse_date(x).year)
            for x in df["fecha_radicacion"].dropna()
            if parse_date(x)
        }, reverse=True)
        if not años:
            st.warning("No hay fechas de radicación para agrupar por mes.")
            return
        anio = st.selectbox("Año", años, key="rep_anio")
        mes = st.selectbox(
            "Mes",
            list(range(1, 13)),
            format_func=lambda m: [
                "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
            ][m],
            key="rep_mes",
        )
        def _en_mes(val):
            d = parse_date(val)
            return d is not None and d.year == int(anio) and d.month == int(mes)
        df_rep = df[df["fecha_radicacion"].apply(_en_mes)].copy()
        cols = _df_existentes(df_rep, COLS_BASE)
        df_rep = df_rep[cols] if cols else df_rep
        titulo = f"Radicaciones {anio}-{int(mes):02d}"
        st.metric("Expedientes en el mes", len(df_rep))

    # ── Vencidas ──
    elif tipo == "Vencidas":
        def _vencida(row):
            fv = parse_date(row.get("fecha_vencimiento_45"))
            estado = str(row.get("estado") or "")
            if not fv or estado in ("Ejecutoriado", "Archivado", "Negado"):
                return False
            return fv < hoy
        df_rep = df[df.apply(_vencida, axis=1)].copy()
        cols = _df_existentes(df_rep, COLS_VENC)
        df_rep = df_rep[cols] if cols else df_rep
        st.metric("Expedientes vencidos", len(df_rep))

    # ── Próximas a vencer ──
    else:
        dias_aviso = st.slider("Días hábiles de anticipación", 1, 15, 5, key="rep_dias_aviso")
        def _proxima(row):
            fv = parse_date(row.get("fecha_vencimiento_45"))
            estado = str(row.get("estado") or "")
            if not fv or estado in ("Ejecutoriado", "Archivado", "Negado"):
                return False
            if fv < hoy:
                return False  # ya vencidas van en otro reporte
            limite = hoy + timedelta(days=dias_aviso * 2)  # margen calendario; filtramos con días hábiles abajo
            if fv > limite:
                return False
            rest = dias_habiles_entre(hoy, fv)
            return 0 <= rest <= dias_aviso
        df_rep = df[df.apply(_proxima, axis=1)].copy()
        cols = _df_existentes(df_rep, COLS_VENC)
        df_rep = df_rep[cols] if cols else df_rep
        st.metric(f"Próximas a vencer (≤ {dias_aviso} días hábiles)", len(df_rep))

    st.divider()
    st.write(f"**{titulo}** — {len(df_rep)} registro(s)")
    if df_rep.empty:
        st.info("No hay registros para este reporte con los filtros actuales.")
    else:
        st.dataframe(df_rep, use_container_width=True, hide_index=True)
        _descargar_reporte(df_rep, "reporte_" + tipo.lower().replace(" ", "_")[:30])

    # ── Gráficos estadísticos ──
    st.divider()
    st.subheader("📊 Gráficos estadísticos")
    if df.empty:
        st.caption("Sin datos para graficar.")
    else:
        g1, g2 = st.columns(2)

        with g1:
            st.markdown("**Expedientes por estado**")
            if "estado" in df.columns:
                por_est = df["estado"].fillna("Sin estado").astype(str).value_counts()
                st.bar_chart(por_est)
            st.markdown("**Expedientes por modalidad**")
            if "modalidad" in df.columns:
                por_mod = df["modalidad"].fillna("Sin modalidad").astype(str).value_counts()
                st.bar_chart(por_mod)

        with g2:
            st.markdown("**Pagos 30% (anticipo)**")
            if "pago_30_anticipo" in df.columns:
                p30 = df["pago_30_anticipo"].fillna("Sin registro").astype(str).replace({"": "Sin registro", "None": "Sin registro"})
                st.bar_chart(p30.value_counts())
            st.markdown("**Pagos 70% (saldo)**")
            if "saldo_70" in df.columns:
                p70 = df["saldo_70"].fillna("Sin registro").astype(str).replace({"": "Sin registro", "None": "Sin registro"})
                st.bar_chart(p70.value_counts())

        # Radicaciones por mes (año en curso o todos)
        st.markdown("**Radicaciones por mes**")
        meses_lab = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        if "fecha_radicacion" in df.columns:
            def _ym(val):
                d = parse_date(val)
                return (d.year, d.month) if d else None
            ym = df["fecha_radicacion"].apply(_ym).dropna()
            if len(ym) > 0:
                años_disp = sorted({y for y, m in ym}, reverse=True)
                anio_g = st.selectbox("Año del gráfico de radicaciones", años_disp, key="graf_anio_rad")
                conteo = {m: 0 for m in range(1, 13)}
                for y, m in ym:
                    if y == anio_g:
                        conteo[m] += 1
                serie = pd.Series({meses_lab[m - 1]: conteo[m] for m in range(1, 13)})
                st.bar_chart(serie)
            else:
                st.caption("No hay fechas de radicación.")

        # Situación de plazos (solo activos)
        st.markdown("**Situación de plazos (expedientes activos)**")
        activos = df[~df["estado"].astype(str).isin(["Ejecutoriado", "Archivado", "Negado", "None", ""])].copy() if "estado" in df.columns else df.copy()
        cats = {"Vencido": 0, "≤ 5 días": 0, "6–15 días": 0, "> 15 días": 0, "Sin fecha": 0}
        for _, row in activos.iterrows():
            fv = parse_date(row.get("fecha_vencimiento_45"))
            if not fv:
                cats["Sin fecha"] += 1
                continue
            if fv < hoy:
                cats["Vencido"] += 1
            else:
                rest = dias_habiles_entre(hoy, fv)
                if rest <= 5:
                    cats["≤ 5 días"] += 1
                elif rest <= 15:
                    cats["6–15 días"] += 1
                else:
                    cats["> 15 días"] += 1
        st.bar_chart(pd.Series(cats))

        # Entrega cumplida
        if "entrega_cumplida" in df.columns:
            st.markdown("**Entrega cumplida**")
            ent = df["entrega_cumplida"].fillna("No registrado").astype(str).replace({"": "No registrado", "None": "No registrado"})
            st.bar_chart(ent.value_counts())

    # Respaldo BD
    st.divider()
    st.subheader("💾 Respaldo de base de datos")
    boton_descarga_bd(key_suffix="reportes")

# ─────────────────────────────────────────────
# Información
# ─────────────────────────────────────────────
def pagina_info():
    st.title("ℹ️ Información del sistema")
    st.markdown("""
### Flujo implementado

1. **Radicación / Actualización parcial** — Formulario completo con todas las variables. Se puede guardar sin llenar todos los campos.
2. **Cálculo de plazos hábiles (Colombia)** — 45 días hábiles de vencimiento general; 5 días jurídica, 8 arquitectura, 8 estructural; 30 días de subsanación (+15 si hay prórroga). Excluye sábados, domingos y festivos nacionales.
3. **Alertas** — Automáticas según días hábiles restantes al vencimiento.
4. **Aprobaciones por área** — Jurídica, Arquitectura, Ingeniería de forma independiente.
5. **Proyección de acto administrativo** — Datos del predio, índices, profesionales, descripción (paz y salvo, certificado de libertad, etc.). Precarga datos del expediente.
6. **Control de firmas** — Trazabilidad de quién firmó. Configuración de quién debe firmar según modalidad (obra vs re-subdivisión). Siempre firma el Jefe de Planeación. Control de planos sellados.
7. **Notificación** — Oficio de solicitud de presentación → notificación personal + oficio de valla → soportes (emisora, foto valla, link web) → ejecutoria → entrega → **archivo físico** (tomos, folios, n° de caja y ubicación: archivo de gestión / mesa nene / archivo general). Al registrar archivo físico el estado pasa a **Archivado**.
8. **Reportes e informes** — Filtros + selección de variables + plantillas. Exportación a CSV/Excel. Descarga de la base de datos (.db) y respaldo completo.

### Usuarios de prueba
| Usuario | Clave | Rol |
|---------|-------|-----|
| admin | admin123 | Administrador |
| juridica | juridica123 | Revisor Jurídico |
| arquitectura | arq123 | Revisor Arquitectónico |
| ingenieria | ing123 | Revisor Ingeniería |
| ventanilla | ventanilla123 | Ventanilla |
| proyectista | proy123 | Proyectista |
| jefe | jefe123 | Jefe de Planeación |
""")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login()
        return

    with st.sidebar:
        st.markdown(f"**{st.session_state['nombre']}**")
        st.caption(st.session_state['rol'])
        st.divider()
        # Menú restringido para revisores profesionales
        if es_revisor_profesional():
            opciones_menu = [
                "Dashboard",
                "Consulta",
                "Aprobaciones por Área",
                "Información",
            ]
            st.info("Acceso profesional: solo consulta y aprobación por radicado.")
        else:
            opciones_menu = [
                "Dashboard",
                "Consulta",
                "Nuevo expediente",
                "Actualizar expediente",
                "Expedientes",
                "Aprobaciones por Área",
                "Proyección de Acto",
                "Control de Firmas",
                "Notificación y Entrega",
                "Reportes",
                "Información",
            ]
        pagina = st.radio("Menú", opciones_menu)
        st.divider()
        if not es_revisor_profesional():
            st.markdown("**Respaldo de datos**")
            st.caption("Descarga la BD después de guardar cambios importantes.")
            boton_descarga_bd(key_suffix="sidebar")
            st.divider()
        if st.button("Cerrar sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    # Bloqueo de seguridad: profesionales no pueden abrir pantallas de edición
    paginas_edicion = {
        "Nuevo expediente", "Actualizar expediente", "Expedientes",
        "Proyección de Acto", "Control de Firmas", "Notificación y Entrega", "Reportes",
    }
    if es_revisor_profesional() and pagina in paginas_edicion:
        st.warning("No tienes permiso para esta sección. Solo puedes consultar y aprobar por radicado.")
        pagina = "Aprobaciones por Área"

    if pagina == "Dashboard":
        pagina_dashboard()
    elif pagina == "Consulta":
        pagina_consulta()
    elif pagina == "Nuevo expediente":
        pagina_nuevo()
    elif pagina == "Actualizar expediente":
        pagina_actualizar()
    elif pagina == "Expedientes":
        pagina_expedientes()
    elif pagina == "Aprobaciones por Área":
        pagina_aprobaciones()
    elif pagina == "Proyección de Acto":
        pagina_proyeccion()
    elif pagina == "Control de Firmas":
        pagina_firmas()
    elif pagina == "Notificación y Entrega":
        pagina_notificacion()
    elif pagina == "Reportes":
        pagina_reportes()
    elif pagina == "Información":
        pagina_info()

if __name__ == "__main__":
    main()