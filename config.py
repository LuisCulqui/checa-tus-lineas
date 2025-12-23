# ================= CREDENCIALES BASE DE DATOS =================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'mysql',
    'database': 'costecnology',
    'port': 3306
}

# ================= RUTAS Y URLS =================
WORKBENCH_PATH = r"C:\Program Files\MySQL\MySQL Workbench 8.0 CE\MySQLWorkbench.exe"
URL_OSIPTEL = "https://checatuslineas.osiptel.gob.pe/"
URL_TRANSFORMA = "https://transforma.my.site.com/s/"

# ================= CREDENCIALES WEB (TRANSFORMA) =================
TRANSFORMA_USER = "usuario1inversioneskajomihuaral@claro.comunidad.com"
TRANSFORMA_PASS = "n@VId4d2o2cincO*"

ID_INPUT_USER = "149:0"
ID_INPUT_PASS = "162:0"

# ================= SENTENCIAS SQL =================
SQL_GET_RUCS = "SELECT ruc, nombre FROM empresa WHERE ruc IS NOT NULL"

SQL_INSERT_RESULT = """
    INSERT INTO checa_tus_lineas 
    (numero_documento, razon_social, empresa_operadora, cantidad_de_lineas, fecha_registro, estado)
    VALUES (%s, %s, %s, %s, %s, 1)
"""

SQL_INSERT_SALESFORCE = """
    INSERT INTO sale_force 
    (numero_documento, razon_social, pe_segmento, pe_tipo_de_cliente, 
    ultima_fecha_asignacion, ultima_fecha_desasignación, fecha_registro, estado) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
"""