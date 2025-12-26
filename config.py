import certifi

# ================= CREDENCIALES BASE DE DATOS =================

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'mysql',
    'database': 'costecnology',
    'port': 3306
}
"""
DB_CONFIG = {
    'host': 'transportek.mysql.database.azure.com',
    'user': 'adminlinktek',
    'password': 'Linktek2025@123transportek',
    'database': 'costecnology',
    'port': 3306,
    'ssl': {
        # certifi.where() devuelve la ruta al certificado oficial instalado en tu Python
        'ca': certifi.where(),
        'check_hostname': True
    }
}
"""
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
SQL_GET_RUCS = "SELECT ruc, nombre FROM empresa WHERE ruc IS NOT NULL AND tipo_ruc = 'RUC 20'"

SQL_GET_EXISTING_OSIPTEL = "SELECT DISTINCT numero_documento FROM checa_tus_lineas"
SQL_GET_EXISTING_SF = "SELECT DISTINCT numero_documento FROM sale_force"

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