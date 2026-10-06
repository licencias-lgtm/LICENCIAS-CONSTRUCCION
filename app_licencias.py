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
    ("saldo_70", "TEXT"),
    ("confirma_pago_70", "TEXT"),
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
    # Entrega final
    ("fecha_entrega_final", "TEXT"),
    ("persona_recibe", "TEXT"),
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
    "Nueva Construcción", "Ampliación", "Remodelación", "Demolición",
    "Regularización", "Cambio de Uso", "Obra Menor", "Re-subdivisión",
    "Urbanización", "Parcelación", "Otro"
]

ESTADOS = [
    "Radicado", "En revisión", "En Acta de Observaciones", "Subsanación",
    "Acto proyectado", "En firmas", "Resolución firmada",
    "Oficio de notificación", "Notificado", "En publicación",
    "Ejecutoriado", "Entrega final", "Archivado", "Negado", "Inadmitido"
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
            st.dataframe(df, use_container_width=True, hide_index=True)

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

def pagina_nuevo_editar():
    st.title("➕ Nuevo / Actualizar Expediente")
    st.info("Puedes guardar avances sin completar todos los campos. Solo el número de radicado es obligatorio para crear.")

    conn = get_connection()
    df = pd.read_sql_query("SELECT numero_radicado FROM expedientes ORDER BY id DESC", conn)
    conn.close()
    radicados = ["— Nuevo expediente —"] + df['numero_radicado'].tolist()

    modo = st.selectbox("Modo", radicados)
    es_nuevo = modo == "— Nuevo expediente —"
    exp = None
    if not es_nuevo:
        conn = get_connection()
        df_e = pd.read_sql_query("SELECT * FROM expedientes WHERE numero_radicado=?", conn, params=(modo,))
        conn.close()
        if not df_e.empty:
            exp = df_e.iloc[0]

    # ── Sección 1: Identificación ──
    with st.expander("1. Identificación y radicación", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            numero = st.text_input("N° Radicado *",
                                   value=safe_get(exp, 'numero_radicado', '') if exp is not None else '',
                                   disabled=not es_nuevo)
            fecha_rad = st.date_input("Fecha de radicación",
                                      value=parse_date(safe_get(exp, 'fecha_radicacion')) or date.today())
            modalidad = st.selectbox("Modalidad", MODALIDADES,
                                     index=MODALIDADES.index(safe_get(exp, 'modalidad', MODALIDADES[0]))
                                     if safe_get(exp, 'modalidad') in MODALIDADES else 0)
        with col2:
            # Vencimiento 45 días hábiles
            if fecha_rad:
                fv45 = sumar_dias_habiles(fecha_rad, 45)
            else:
                fv45 = None
            st.text_input("Fecha vencimiento (45 días hábiles)",
                          value=fv45.strftime('%Y-%m-%d') if fv45 else '', disabled=True)
            hoy = date.today()
            if fv45:
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
            estado = st.selectbox("Estado", ESTADOS,
                                  index=ESTADOS.index(safe_get(exp, 'estado', 'Radicado'))
                                  if safe_get(exp, 'estado') in ESTADOS else 0)
        with col3:
            num_res = st.text_input("Número de resolución", value=safe_get(exp, 'numero_resolucion', '') or '')
            fecha_res = st.date_input("Fecha resolución",
                                      value=parse_date(safe_get(exp, 'fecha_resolucion')),
                                      key="fecha_res_id")
            if st.checkbox("Sin fecha resolución", value=parse_date(safe_get(exp, 'fecha_resolucion')) is None,
                           key="sin_fecha_res"):
                fecha_res = None

    # ── Sección 2: Pagos ──
    with st.expander("2. Pagos"):
        col1, col2, col3 = st.columns(3)
        with col1:
            pago30 = st.selectbox("Pago del 30% anticipo", ["", "Sí", "No", "Pendiente"],
                                  index=["", "Sí", "No", "Pendiente"].index(safe_get(exp, 'pago_30_anticipo', '') or '')
                                  if (safe_get(exp, 'pago_30_anticipo') or '') in ["", "Sí", "No", "Pendiente"] else 0)
        with col2:
            saldo70 = st.selectbox("Saldo del 70%", ["", "Sí", "No", "Pendiente"],
                                   index=["", "Sí", "No", "Pendiente"].index(safe_get(exp, 'saldo_70', '') or '')
                                   if (safe_get(exp, 'saldo_70') or '') in ["", "Sí", "No", "Pendiente"] else 0)
        with col3:
            conf70 = st.selectbox("Confirma pago 70%", ["", "Sí", "No"],
                                  index=["", "Sí", "No"].index(safe_get(exp, 'confirma_pago_70', '') or '')
                                  if (safe_get(exp, 'confirma_pago_70') or '') in ["", "Sí", "No"] else 0)

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
    with st.expander("4. Revisiones (plazos hábiles)"):
        st.caption("Ingresa la fecha de ingreso a revisión jurídica; las demás se calculan automáticamente (5 días jurídica, 8 arquitectura, 8 estructural). Puedes sobrescribirlas.")
        col1, col2, col3 = st.columns(3)
        with col1:
            fi_jur = st.date_input("Fecha ingreso revisión jurídica (5 días hábiles)",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_juridica')),
                                   key="fi_jur")
            if st.checkbox("Sin fecha ingreso jurídica", value=parse_date(safe_get(exp, 'fecha_ingreso_juridica')) is None, key="sin_fi_jur"):
                fi_jur = None
            calc = calcular_fechas_revision(fi_jur)
            fs_jur = st.date_input("Fecha salida jurídica",
                                   value=parse_date(safe_get(exp, 'fecha_salida_juridica')) or calc.get("fecha_salida_juridica"),
                                   key="fs_jur")
            if st.checkbox("Sin fecha salida jurídica", value=False, key="sin_fs_jur"):
                fs_jur = None
        with col2:
            fi_arq = st.date_input("Fecha ingreso arquitectura (8 días hábiles)",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_arquitectura')) or calc.get("fecha_ingreso_arquitectura"),
                                   key="fi_arq")
            if st.checkbox("Sin fecha ingreso arq.", value=False, key="sin_fi_arq"):
                fi_arq = None
            fs_arq = st.date_input("Fecha salida arquitectura",
                                   value=parse_date(safe_get(exp, 'fecha_salida_arquitectura')) or calc.get("fecha_salida_arquitectura"),
                                   key="fs_arq")
            if st.checkbox("Sin fecha salida arq.", value=False, key="sin_fs_arq"):
                fs_arq = None
        with col3:
            fi_est = st.date_input("Fecha ingreso revisión estructural",
                                   value=parse_date(safe_get(exp, 'fecha_ingreso_estructural')) or calc.get("fecha_ingreso_estructural"),
                                   key="fi_est")
            if st.checkbox("Sin fecha ingreso est.", value=False, key="sin_fi_est"):
                fi_est = None
            fs_est = st.date_input("Fecha salida revisión estructural",
                                   value=parse_date(safe_get(exp, 'fecha_salida_estructural')) or calc.get("fecha_salida_estructural"),
                                   key="fs_est")
            if st.checkbox("Sin fecha salida est.", value=False, key="sin_fs_est"):
                fs_est = None

        # Días en estudio (automático)
        if fecha_rad:
            dias_est = dias_habiles_entre(fecha_rad, date.today())
        else:
            dias_est = 0
        st.metric("Número de días en estudio (automático)", dias_est)

    # ── Sección 5: Acta de observaciones ──
    with st.expander("5. Acta de observaciones y prórroga"):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_elab_acta = st.date_input("Fecha elaboración acta observaciones (1ª revisión)",
                                            value=parse_date(safe_get(exp, 'fecha_elaboracion_acta')), key="fea")
            if st.checkbox("Sin fecha elab. acta", value=parse_date(safe_get(exp, 'fecha_elaboracion_acta')) is None, key="sin_fea"):
                fecha_elab_acta = None
            num_acta = st.text_input("Número de acta", value=safe_get(exp, 'numero_acta', '') or '')
            rad_salida_acta = st.text_input("Radicado de salida acta", value=safe_get(exp, 'radicado_salida_acta', '') or '')
            fecha_rad_acta = st.date_input("Fecha de radicado acta",
                                           value=parse_date(safe_get(exp, 'fecha_radicado_acta')), key="fra")
            if st.checkbox("Sin fecha rad. acta", value=parse_date(safe_get(exp, 'fecha_radicado_acta')) is None, key="sin_fra"):
                fecha_rad_acta = None
        with col2:
            rad_prorroga = st.text_input("Radicado oficio prórroga", value=safe_get(exp, 'radicado_oficio_prorroga', '') or '')
            fecha_of_prorroga = st.date_input("Fecha oficio prórroga",
                                              value=parse_date(safe_get(exp, 'fecha_oficio_prorroga')), key="fop")
            if st.checkbox("Sin fecha oficio prórroga", value=parse_date(safe_get(exp, 'fecha_oficio_prorroga')) is None, key="sin_fop"):
                fecha_of_prorroga = None
            tiene_prorroga = st.selectbox("¿Tiene prórroga?", ["No", "Sí"],
                                          index=0 if safe_get(exp, 'tiene_prorroga', 'No') != 'Sí' else 1)
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
            rad_corr = st.text_input("Radicado entrada corrección", value=safe_get(exp, 'radicado_entrada_correccion', '') or '')
            fecha_rad_corr = st.date_input("Fecha radicado corrección",
                                           value=parse_date(safe_get(exp, 'fecha_radicado_correccion')), key="frc")
            if st.checkbox("Sin fecha rad. corrección", value=parse_date(safe_get(exp, 'fecha_radicado_correccion')) is None, key="sin_frc"):
                fecha_rad_corr = None
            fecha_acta_fin = st.date_input("Fecha acta finalización para resolución",
                                           value=parse_date(safe_get(exp, 'fecha_acta_finalizacion')), key="faf")
            if st.checkbox("Sin fecha acta finalización", value=parse_date(safe_get(exp, 'fecha_acta_finalizacion')) is None, key="sin_faf"):
                fecha_acta_fin = None

    observaciones = st.text_area("Observaciones generales", value=safe_get(exp, 'observaciones', '') or '')

    # Guardar
    if st.button("💾 Guardar avance / Actualizar expediente", type="primary", use_container_width=True):
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
            "saldo_70": saldo70 or None,
            "confirma_pago_70": conf70 or None,
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
                st.success(f"Expediente **{radicado_final}** actualizado correctamente (mismo registro, sin duplicar).")
            else:
                # INSERTAR solo si no existe
                cols = list(datos.keys())
                placeholders = ",".join(["?"] * len(cols))
                c.execute(
                    f"INSERT INTO expedientes ({','.join(cols)}) VALUES ({placeholders})",
                    [datos[k] for k in cols],
                )
                conn.commit()
                st.success(f"Expediente **{radicado_final}** creado correctamente.")
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
        st.info("No hay expedientes. Crea uno desde «Nuevo / Actualizar».")
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
# Aprobaciones por área
# ─────────────────────────────────────────────
def pagina_aprobaciones():
    st.title("✅ Aprobaciones por Área")
    st.write(f"Usuario: **{st.session_state['nombre']}** ({st.session_state['rol']})")
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
        st.dataframe(df[['numero_radicado', 'propietario', 'aprobacion_juridica',
                         'aprobacion_arquitectura', 'aprobacion_ingenieria']].head(50),
                     use_container_width=True, hide_index=True)
        return

    st.subheader(titulo)
    sel = st.selectbox("Seleccionar expediente", df['numero_radicado'].tolist())
    exp = df[df['numero_radicado'] == sel].iloc[0]
    st.write(f"**Propietario:** {safe_get(exp, 'propietario')}  |  **Estado:** {safe_get(exp, 'estado')}")
    st.write(f"**Aprobación actual:** {safe_get(exp, campo, 'Pendiente')}")
    decision = st.radio("Tu decisión", ["Pendiente", "Aprobado", "Rechazado", "Con observaciones"], horizontal=True)
    obs = st.text_area("Observaciones de tu revisión")
    if st.button("Registrar mi aprobación"):
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"UPDATE expedientes SET {campo}=?, ultima_actualizacion=? WHERE numero_radicado=?",
                  (decision, datetime.now().strftime("%Y-%m-%d %H:%M"), sel))
        if obs:
            c.execute("UPDATE expedientes SET observaciones=? WHERE numero_radicado=?",
                      ((safe_get(exp, 'observaciones') or '') + f"\n[{campo}] {obs}", sel))
        conn.commit()
        conn.close()
        st.success(f"Aprobación registrada: {decision}")
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
    st.title("📬 Notificación, Publicación y Entrega Final")
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
        oficio_valla = st.text_input("Oficio de solicitud de fijación de valla",
                                     value=safe_get(exp, 'oficio_fijacion_valla', '') or '')
        st.caption("En la notificación se entrega también el oficio de solicitud de fijación de valla.")

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

    # 5. Entrega final
    with st.expander("5. Entrega final"):
        col1, col2 = st.columns(2)
        with col1:
            fecha_ent = st.date_input("Fecha de entrega final",
                                      value=parse_date(safe_get(exp, 'fecha_entrega_final')), key="fef")
            if st.checkbox("Sin fecha entrega", value=parse_date(safe_get(exp, 'fecha_entrega_final')) is None, key="sin_fef"):
                fecha_ent = None
        with col2:
            persona_rec = st.text_input("Persona que recibe", value=safe_get(exp, 'persona_recibe', '') or '')

    if st.button("💾 Guardar notificación / publicación / entrega", type="primary"):
        # Determinar estado
        nuevo_estado = safe_get(exp, 'estado')
        if fecha_ent:
            nuevo_estado = "Entrega final"
        elif tiene_ej == "Sí" or fecha_ej:
            nuevo_estado = "Ejecutoriado"
        elif fecha_notif:
            nuevo_estado = "Notificado"
        elif oficio_sol:
            nuevo_estado = "Oficio de notificación"

        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE expedientes SET
                oficio_solicitud_notificacion=?, fecha_oficio_notificacion=?,
                fecha_notificacion_personal=?, oficio_fijacion_valla=?,
                soporte_publicacion_emisora=?, foto_valla=?, link_publicacion=?,
                tiene_ejecutoria=?, fecha_ejecutoria=?,
                fecha_entrega_final=?, persona_recibe=?,
                estado=?, ultima_actualizacion=?
            WHERE numero_radicado=?
        ''', (
            oficio_sol or None, fmt_date(fecha_oficio),
            fmt_date(fecha_notif), oficio_valla or None,
            soporte_emisora or None, foto_valla or None, link_pub or None,
            tiene_ej or None, fmt_date(fecha_ej),
            fmt_date(fecha_ent), persona_rec or None,
            nuevo_estado,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            sel
        ))
        conn.commit()
        conn.close()
        st.success("Datos de notificación, publicación y entrega guardados.")
        st.rerun()

# ─────────────────────────────────────────────
# Reportes
# ─────────────────────────────────────────────
# Diccionario de variables disponibles para reportes (nombre legible → columna BD)
VARIABLES_REPORTE = {
    "N° Radicado": "numero_radicado",
    "Fecha radicación": "fecha_radicacion",
    "Modalidad": "modalidad",
    "Estado": "estado",
    "Fecha vencimiento 45 días": "fecha_vencimiento_45",
    "Alerta": "alerta",
    "N° Resolución": "numero_resolucion",
    "Fecha resolución": "fecha_resolucion",
    "Propietario": "propietario",
    "Cédula / NIT": "cedula_titular",
    "Apoderado": "apoderado",
    "Celular": "celular",
    "Persona autoriza": "persona_autoriza",
    "Ficha catastral": "ficha_catastral",
    "Matrícula inmobiliaria": "matricula_inmobiliaria",
    "Dirección": "direccion",
    "Barrio": "barrio",
    "Zona": "zona",
    "Superficie (m²)": "superficie",
    "Valor obra": "valor_obra",
    "Pago 30% anticipo": "pago_30_anticipo",
    "Saldo 70%": "saldo_70",
    "Confirma pago 70%": "confirma_pago_70",
    "Fecha ingreso jurídica": "fecha_ingreso_juridica",
    "Fecha salida jurídica": "fecha_salida_juridica",
    "Fecha ingreso arquitectura": "fecha_ingreso_arquitectura",
    "Fecha salida arquitectura": "fecha_salida_arquitectura",
    "Fecha ingreso estructural": "fecha_ingreso_estructural",
    "Fecha salida estructural": "fecha_salida_estructural",
    "Días en estudio": "dias_en_estudio",
    "Fecha elaboración acta": "fecha_elaboracion_acta",
    "N° Acta": "numero_acta",
    "Radicado salida acta": "radicado_salida_acta",
    "Fecha radicado acta": "fecha_radicado_acta",
    "Tiene prórroga": "tiene_prorroga",
    "Fecha vencimiento subsanación": "fecha_vencimiento_subsanacion",
    "Radicado entrada corrección": "radicado_entrada_correccion",
    "Fecha radicado corrección": "fecha_radicado_correccion",
    "Fecha acta finalización": "fecha_acta_finalizacion",
    "Aprobación jurídica": "aprobacion_juridica",
    "Aprobación arquitectura": "aprobacion_arquitectura",
    "Aprobación ingeniería": "aprobacion_ingenieria",
    "Área predio": "area_predio",
    "Área libre": "area_libre",
    "N° pisos": "numero_pisos",
    "N° vivienda": "numero_vivienda",
    "Área primer piso": "area_primer_piso",
    "Área segundo piso": "area_segundo_piso",
    "Área existente": "area_existente",
    "Área ampliación": "area_ampliacion",
    "Área total construida": "area_total_construida",
    "Índice ocupación": "indice_ocupacion",
    "Índice construcción": "indice_construccion",
    "Sector": "sector",
    "Ubicación predio": "ubicacion_predio",
    "Prof. arquitectónico": "profesional_arquitectonico",
    "Prof. estructural": "profesional_estructural",
    "Cant. planos arq.": "cantidad_planos_arq",
    "Cant. planos est.": "cantidad_planos_est",
    "Firma jurídico": "firma_juridico",
    "Firma arquitecto": "firma_arquitecto",
    "Firma ingeniero": "firma_ingeniero",
    "Firma jefe planeación": "firma_jefe_planeacion",
    "Planos sellados": "planos_sellados",
    "Fecha notificación personal": "fecha_notificacion_personal",
    "Tiene ejecutoria": "tiene_ejecutoria",
    "Fecha ejecutoria": "fecha_ejecutoria",
    "Fecha entrega final": "fecha_entrega_final",
    "Persona recibe": "persona_recibe",
    "Observaciones": "observaciones",
    "Última actualización": "ultima_actualizacion",
}

PRESETS_REPORTE = {
    "Básico (radicado, fechas, estado, propietario)": [
        "N° Radicado", "Fecha radicación", "Modalidad", "Estado",
        "Propietario", "Fecha vencimiento 45 días", "Alerta", "N° Resolución"
    ],
    "Plazos y alertas": [
        "N° Radicado", "Propietario", "Estado", "Fecha radicación",
        "Fecha vencimiento 45 días", "Alerta", "Días en estudio",
        "Fecha ingreso jurídica", "Fecha salida jurídica",
        "Fecha ingreso arquitectura", "Fecha salida arquitectura",
        "Fecha ingreso estructural", "Fecha salida estructural",
        "Fecha vencimiento subsanación"
    ],
    "Aprobaciones y firmas": [
        "N° Radicado", "Propietario", "Estado", "Modalidad",
        "Aprobación jurídica", "Aprobación arquitectura", "Aprobación ingeniería",
        "Firma jurídico", "Firma arquitecto", "Firma ingeniero", "Firma jefe planeación",
        "Planos sellados", "N° Resolución", "Fecha resolución"
    ],
    "Datos del predio y acto": [
        "N° Radicado", "Propietario", "Modalidad", "Dirección", "Barrio", "Zona",
        "Ficha catastral", "Matrícula inmobiliaria", "Superficie (m²)", "Valor obra",
        "Área predio", "Área libre", "N° pisos", "N° vivienda",
        "Área total construida", "Índice ocupación", "Índice construcción",
        "Sector", "Ubicación predio", "Prof. arquitectónico", "Prof. estructural"
    ],
    "Notificación y entrega": [
        "N° Radicado", "Propietario", "Estado", "N° Resolución", "Fecha resolución",
        "Fecha notificación personal", "Tiene ejecutoria", "Fecha ejecutoria",
        "Fecha entrega final", "Persona recibe"
    ],
    "Completo (todas las variables)": list(VARIABLES_REPORTE.keys()),
}

def pagina_reportes():
    st.title("📑 Reportes")
    st.caption("Genera reportes personalizados eligiendo filtros y variables. Descarga en CSV o Excel.")

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

    # ── Filtros ──
    with st.expander("🔍 Filtros", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            estados_disp = ["Todos"] + sorted([x for x in df["estado"].dropna().unique().tolist() if x])
            filtro_estado = st.multiselect("Estado", estados_disp, default=["Todos"])
            modalidades_disp = ["Todas"] + sorted([x for x in df["modalidad"].dropna().unique().tolist() if x])
            filtro_mod = st.multiselect("Modalidad", modalidades_disp, default=["Todas"])
        with col2:
            fecha_desde = st.date_input("Fecha radicación desde", value=None, key="rep_desde")
            fecha_hasta = st.date_input("Fecha radicación hasta", value=None, key="rep_hasta")
            solo_alertas = st.checkbox("Solo con alerta de vencimiento (≤ 5 días o vencidos)", value=False)
        with col3:
            texto_busqueda = st.text_input("Buscar texto (radicado, propietario, cédula, ficha…)")
            zona_disp = ["Todas"] + sorted([x for x in df.get("zona", pd.Series(dtype=str)).dropna().unique().tolist() if x])
            filtro_zona = st.selectbox("Zona", zona_disp)

    # Aplicar filtros
    df_f = df.copy()
    if filtro_estado and "Todos" not in filtro_estado:
        df_f = df_f[df_f["estado"].isin(filtro_estado)]
    if filtro_mod and "Todas" not in filtro_mod:
        df_f = df_f[df_f["modalidad"].isin(filtro_mod)]
    if fecha_desde:
        df_f = df_f[df_f["fecha_radicacion"].apply(lambda x: parse_date(x) is not None and parse_date(x) >= fecha_desde)]
    if fecha_hasta:
        df_f = df_f[df_f["fecha_radicacion"].apply(lambda x: parse_date(x) is not None and parse_date(x) <= fecha_hasta)]
    if filtro_zona != "Todas":
        df_f = df_f[df_f.get("zona", pd.Series(dtype=str)) == filtro_zona]
    if texto_busqueda:
        mask = (
            df_f["numero_radicado"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
            df_f["propietario"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
            df_f.get("cedula_titular", pd.Series([""] * len(df_f))).astype(str).str.contains(texto_busqueda, case=False, na=False) |
            df_f.get("ficha_catastral", pd.Series([""] * len(df_f))).astype(str).str.contains(texto_busqueda, case=False, na=False) |
            df_f.get("direccion", pd.Series([""] * len(df_f))).astype(str).str.contains(texto_busqueda, case=False, na=False)
        )
        df_f = df_f[mask]
    if solo_alertas:
        hoy = date.today()
        def tiene_alerta(row):
            fv = parse_date(row.get("fecha_vencimiento_45"))
            estado = str(row.get("estado") or "")
            if not fv or estado in ("Ejecutoriado", "Archivado", "Negado", "Entrega final"):
                return False
            return fv <= hoy + timedelta(days=5)
        df_f = df_f[df_f.apply(tiene_alerta, axis=1)]

    # ── Selección de variables ──
    st.subheader("Variables del reporte")
    preset = st.selectbox("Plantilla rápida", list(PRESETS_REPORTE.keys()), index=0)
    vars_default = PRESETS_REPORTE[preset]

    # Multiselect con nombres legibles
    vars_seleccionadas = st.multiselect(
        "Selecciona las columnas a incluir",
        options=list(VARIABLES_REPORTE.keys()),
        default=[v for v in vars_default if v in VARIABLES_REPORTE],
        help="Puedes combinar la plantilla con columnas adicionales."
    )

    if not vars_seleccionadas:
        st.warning("Selecciona al menos una variable.")
        return

    # Construir DataFrame del reporte
    cols_bd = [VARIABLES_REPORTE[v] for v in vars_seleccionadas]
    # Solo columnas que existan en el df
    cols_existentes = [c for c in cols_bd if c in df_f.columns]
    nombres_existentes = [v for v, c in zip(vars_seleccionadas, cols_bd) if c in df_f.columns]

    if not cols_existentes:
        st.error("Ninguna de las columnas seleccionadas existe en los datos.")
        return

    df_rep = df_f[cols_existentes].copy()
    df_rep.columns = nombres_existentes  # nombres legibles

    # Resumen
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Expedientes en el reporte", len(df_rep))
    with col_m2:
        st.metric("Columnas seleccionadas", len(df_rep.columns))
    with col_m3:
        if "Estado" in df_rep.columns:
            st.metric("Estados distintos", df_rep["Estado"].nunique())

    st.dataframe(df_rep, use_container_width=True, hide_index=True)

    # ── Descargas ──
    st.subheader("Descargar reporte")
    col_d1, col_d2 = st.columns(2)

    # CSV
    csv_data = df_rep.to_csv(index=False).encode("utf-8-sig")
    with col_d1:
        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv_data,
            file_name=f"reporte_licencias_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Excel
    try:
        from io import BytesIO
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_rep.to_excel(writer, index=False, sheet_name="Reporte")
        buffer.seek(0)
        with col_d2:
            st.download_button(
                label="⬇️ Descargar Excel",
                data=buffer,
                file_name=f"reporte_licencias_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception:
        with col_d2:
            st.info("Para Excel instala `openpyxl` (pip install openpyxl). Mientras tanto usa CSV.")

    # Resumen por estado / modalidad (si están en el reporte o en los datos filtrados)
    st.divider()
    st.subheader("Resúmenes rápidos")
    c1, c2 = st.columns(2)
    with c1:
        if "estado" in df_f.columns:
            resumen_est = df_f["estado"].value_counts().reset_index()
            resumen_est.columns = ["Estado", "Cantidad"]
            st.write("**Por estado**")
            st.dataframe(resumen_est, use_container_width=True, hide_index=True)
    with c2:
        if "modalidad" in df_f.columns:
            resumen_mod = df_f["modalidad"].value_counts().reset_index()
            resumen_mod.columns = ["Modalidad", "Cantidad"]
            st.write("**Por modalidad**")
            st.dataframe(resumen_mod, use_container_width=True, hide_index=True)

    # ── Respaldo de base de datos y exportación completa ──
    st.divider()
    st.subheader("💾 Respaldo y base de datos")
    st.caption("Descarga la base de datos completa o un Excel con todos los expedientes (todas las columnas).")

    col_b1, col_b2, col_b3 = st.columns(3)

    # Descargar archivo .db
    with col_b1:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                label="⬇️ Descargar base de datos (.db)",
                data=db_bytes,
                file_name=f"licencias_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                mime="application/x-sqlite3",
                use_container_width=True,
                help="Archivo SQLite completo. Puedes restaurarlo reemplazando licencias.db.",
            )
        else:
            st.warning("Aún no existe el archivo de base de datos.")

    # Excel completo (todas las columnas de expedientes filtrados)
    with col_b2:
        try:
            from io import BytesIO
            buf_full = BytesIO()
            with pd.ExcelWriter(buf_full, engine="openpyxl") as writer:
                df_f.to_excel(writer, index=False, sheet_name="Expedientes")
            buf_full.seek(0)
            st.download_button(
                label="⬇️ Excel completo (filtrado)",
                data=buf_full,
                file_name=f"expedientes_completo_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception:
            st.caption("Instala openpyxl para Excel completo.")

    # CSV completo
    with col_b3:
        csv_full = df_f.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ CSV completo (filtrado)",
            data=csv_full,
            file_name=f"expedientes_completo_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

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
7. **Notificación** — Oficio de solicitud de presentación → notificación personal + oficio de valla → soportes (emisora, foto valla, link web) → ejecutoria → entrega final.
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
        pagina = st.radio("Menú", [
            "Dashboard",
            "Consulta",
            "Nuevo / Actualizar Expediente",
            "Expedientes",
            "Aprobaciones por Área",
            "Proyección de Acto",
            "Control de Firmas",
            "Notificación y Entrega",
            "Reportes",
            "Información"
        ])
        st.divider()
        if st.button("Cerrar sesión"):
            st.session_state['logged_in'] = False
            st.rerun()

    if pagina == "Dashboard":
        pagina_dashboard()
    elif pagina == "Consulta":
        pagina_consulta()
    elif pagina == "Nuevo / Actualizar Expediente":
        pagina_nuevo_editar()
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