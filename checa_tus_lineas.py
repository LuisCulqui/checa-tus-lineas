import sys
import time
import psutil
import subprocess
import pymysql
import pandas as pd
import re
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path

import pyautogui

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

# ================= CONFIGURACIÓN =================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'mysql',
    'database': 'costecnology',
    'port': 3306
}

WORKBENCH_PATH = r"C:\Program Files\MySQL\MySQL Workbench 8.0 CE\MySQLWorkbench.exe"
URL_OSIPTEL = "https://checatuslineas.osiptel.gob.pe/"
URL_TRANSFORMA = "https://transforma.my.site.com/s/"

USUARIO_TRANSFORMA = "usuario1inversioneskajomihuaral@claro.comunidad.com"
PASSWORD_TRANSFORMA = "n@VId4d2o2cincO*"

conexion = pymysql.connect(**DB_CONFIG)

sql_empresas = "SELECT ruc, nombre FROM empresa WHERE ruc IS NOT NULL"
sql_insert_checa_tus_lineas = """
    INSERT INTO checa_tus_lineas 
    (numero_documento, razon_social, empresa_operadora, cantidad_de_lineas, estado)
    VALUES (%s, %s, %s, %s, 1)
"""

def mostrar_alerta_error(titulo, mensaje):
    """Muestra una ventana emergente de error nativa de Windows."""
    root = tk.Tk()
    root.withdraw()  # Ocultar ventana principal de Tk
    root.attributes("-topmost", True) # Forzar que salga encima de todo
    messagebox.showerror(titulo, mensaje)
    root.destroy()

# ================= SISTEMA Y LECTURA DE LA BD =================
def gestionar_workbench():
    """ ABRE WORKBENCH SI NO ESTÁ CORRIENDO """
    proceso = "MySQLWorkbench.exe"
    if any(p.info['name'] == proceso for p in psutil.process_iter(['name'])):
        print(f"✅ {proceso} ya está abierto.")
    else:
        print(f"⚠️ {proceso} cerrado. Abriendo...")
        try:
            subprocess.Popen(WORKBENCH_PATH)
            time.sleep(5)
        except FileNotFoundError:
            print(f"❌ No se encontró Workbench en: {WORKBENCH_PATH}")

# ================= CONSULTAMOS DATOS DE LA TABLA EMPRESA =================
def obtener_datos_bd():
    print("🔌 Conectando a la Base de Datos (Lectura)...")
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql_empresas)
            respuesta = cursor.fetchall()
        conexion.close()

        dataFrame = pd.DataFrame(respuesta, columns=['RUC', 'NOMBRE'])
        print(f"📥 {len(dataFrame)} registros cargados para procesar.")
        return dataFrame
    except Exception as e:
        print(f"❌ Error al leer DB: {e}")
        sys.exit(1)

# ================= INSERTAMOS LOS DATOS EN LA BD =================
def insertar_resultado_bd(ruc, nombre, operadoras, cantidad):
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql_insert_checa_tus_lineas, (str(ruc), nombre, operadoras, cantidad))
            conexion.commit()
            conexion.close()
            return True
    except Exception as e:
        print(f"   ❌ Error insertando en BD: {e}")
        return False

# ================= SCRAPING EN LA PAGINACIÓN =================
def limpiar_input_js(driver, elemento):
    driver.execute_script("arguments[0].value='';", elemento)

def obtener_cantidad_total(texto_info):
    if not texto_info: return 0
    match = re.search(r"de\s+([\d,.]+)\s+\w+", texto_info, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", "").replace(".", ""))
    return 0

def consultar_ruc_osiptel(driver, wait, ruc):
    try:
        select = Select(wait.until(EC.element_to_be_clickable((By.ID, "IdTipoDoc"))))
        select.select_by_value("2")

        input = wait.until(EC.visibility_of_element_located((By.ID, "NumeroDocumento")))
        limpiar_input_js(driver, input)
        input.send_keys(ruc)

        driver.find_element(By.ID, "btnBuscar").click()

        # REVISAR ERRORES ESPECIFICOS DEL INPUT
        try:
            wait.until(lambda d:
                d.find_element(By.ID, "GridConsulta_info").is_displayed() or
                (d.find_element(By.CSS_SELECTOR, "span[data-valmsg-for='NumeroDocumento']").is_displayed() and
                d.find_element(By.CSS_SELECTOR, "span[data-valmsg-for='NumeroDocumento']").text.strip() != "") or
                d.find_element(By.ID, "ctrData").is_displayed()
            )
        except TimeoutException:
            return 0, "TIMEOUT (La web no respondió)"
        
        # NO SE ENCONTRARON RESULTADOS
        try:
            ctr_data = driver.find_element(By.ID, "ctrData")
            if ctr_data.is_displayed():
                return 0, "SIN LINEAS (No encontrado)"
        except: pass

        # REVISAMOS SI HAY TABLA PERO VACIA (FALLBACK)
        filas_vacias = driver.find_elements(By.CSS_SELECTOR, "td.dataTables_empty")
        if filas_vacias and filas_vacias[0].is_displayed(): return 0, "SIN LINEAS"

        # EXTRACCIÓN DE DATOS
        try:
            info_element = driver.find_element(By.ID, "GridConsulta_info")
            total = obtener_cantidad_total(info_element.text)
        except:
            return 0, "ERROR LECTURA TOTAL"

        if total == 0: return 0, "SIN LINEAS (0)"

        empresas_set = set()

        while True:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#GridConsulta tbody tr")))

            filas = driver.find_elements(By.CSS_SELECTOR, "#GridConsulta tbody tr")
            for f in filas:
                cols = f.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 3 and "dataTables_empty" not in f.get_attribute("class"):
                    val = cols[2].text.strip()
                    if val: empresas_set.add(val)
            
            try:
                btn_next = driver.find_element(By.ID, "GridConsulta_next")
                if "disabled" in btn_next.get_attribute("class"):
                    break

                info_actual = driver.find_element(By.ID, "GridConsulta_info").text

                btn_next.click()

                wait.until(lambda d: d.find_element(By.ID, "GridConsulta_info").text != info_actual)
            
            except Exception:
                break
        return total, ", ".join(sorted(empresas_set))

    except Exception as e:
        return 0, f"ERR CRITICO: {str(e)[:20]}"

def main():
    gestionar_workbench()
    df_empresas = obtener_datos_bd()
    if df_empresas.empty:
        print("❌ No hay datos para procesar. Saliendo...")
        return

    try:
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        
        options.add_experimental_option("detach", True)

        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 15)

        try:
            driver.get(URL_OSIPTEL)
            #wait.until(EC.title_contains("Checa tus líneas"))
        except WebDriverException:
            mostrar_alerta_error("Sin Internet", "No se puede acceder a Osiptel.")

        total = len(df_empresas)
        for index, row in df_empresas.iterrows():
            ruc = str(row['RUC']).strip()
            nombre = str(row['NOMBRE']).strip() if row['NOMBRE'] else "SIN NOMBRE"

            if len(ruc) != 11 or not ruc.isdigit():
                print(f"[{index+1}/{total}] ⏭️ Salto RUC inválido: {ruc}")
                continue
                
            print(f"[{index+1}/{total}] 🔎 Consultando: {ruc}...", end=" ")

            cant, det = consultar_ruc_osiptel(driver, wait, ruc)

            ok = insertar_resultado_bd(ruc, nombre, det, cant)
            status = "💾 Guardado" if ok else "Error BD"
            print(f"--> {cant} líneas. ({status})")
        
    except Exception as e:
        mostrar_alerta_error("Error Fatal", f"Ocurrió un error inesperado:\n{e}")

if __name__ == "__main__":
    main()