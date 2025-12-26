import time
import psutil
import subprocess
import re
import pyautogui
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path

# LIBRERIAS DE SELENIUM
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# CONFIGURACIÓN
import config
import database

# ================= UTILITARIOS =================

def gestionar_workbench():
    """ ABRE WORKBENCH SI NO ESTÁ CORRIENDO """
    proceso_name = "MySQLWorkbench.exe"
    if any(p.info['name'] == proceso_name for p in psutil.process_iter(['name'])):
        print(f"✅ {proceso_name} ya está abierto.")
    else:
        print(f"⚠️ {proceso_name} cerrado. Abriendo...")
        try:
            subprocess.Popen(config.WORKBENCH_PATH)
            time.sleep(5)
        except FileNotFoundError:
            print(f"❌ No se encontró Workbench en la ruta configurada.")

def efecto_tecleo(texto):
    for char in texto:
        pyautogui.write(char)
        time.sleep(0.01)

def limpiar_input_js(driver, elemento):
    driver.execute_script("arguments[0].value='';", elemento)

def obtener_cantidad_total(texto_info):
    if not texto_info: 
        return 0
    match = re.search(r"de\s+([\d,.]+)\s+\w+", texto_info, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", "").replace(".", ""))
    return 0

# ================= LÓGICA DE SCRAPING (OSIPTEL) =================

def consultar_ruc_osiptel(driver, wait, ruc):
    try:
        # LLENAR FORMULARIO
        select = Select(wait.until(EC.element_to_be_clickable((By.ID, "IdTipoDoc"))))
        select.select_by_value("2")

        input_ruc = wait.until(EC.visibility_of_element_located((By.ID, "NumeroDocumento")))
        limpiar_input_js(driver, input_ruc)
        input_ruc.send_keys(str(ruc))

        driver.find_element(By.ID, "btnBuscar").click()

        # ESPERAR CARGA DE RESULTADOS
        time.sleep(1)

        # ERROR DE VALIDACIÓN
        spans_error = driver.find_elements(By.CSS_SELECTOR, "span[data-valmsg-for='NumeroDocumento']")
        for span in spans_error:
            if span.is_displayed() and span.text.strip():
                return 0, f"ERROR WEB: {span.text.strip()}"
        
        # SIN RESULTADOS
        div_ctr = driver.find_elements(By.ID, "ctrData")
        if div_ctr and div_ctr[0].is_displayed():
            return 0, "SIN LINEAS"
        
        # TABLA VACÍA (FALLBACK)
        filas_vacias = driver.find_elements(By.CSS_SELECTOR, "td.dataTables_empty")
        if filas_vacias and filas_vacias[0].is_displayed():
            return 0, "SIN LINEAS"
        
        # ÉXITO
        try:
            wait.until(EC.visibility_of_element_located((By.ID, "GridConsulta_info")))
            info_element = driver.find_element(By.ID, "GridConsulta_info")
            total = obtener_cantidad_total(info_element.text)
        except TimeoutException:
            return 0, "ERROR LECTURA TOTAL"
        
        if total <= 0: 
            return 0, "SIN LINEAS"

        # PAGINACIÓN
        empresas_set = set()

        while True:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#GridConsulta tbody tr")))
            filas = driver.find_elements(By.CSS_SELECTOR, "#GridConsulta tbody tr")

            for fila in filas:
                columnas = fila.find_elements(By.TAG_NAME, "td")
                if len(columnas) >= 3 and "dataTables_empty" not in fila.get_attribute("class"):
                    empresa = columnas[2].text.strip()
                    if empresa:
                        empresas_set.add(empresa)
            
            try:
                btn_siguiente = driver.find_element(By.ID, "GridConsulta_next")
                clase = btn_siguiente.get_attribute("class")
                if "disabled" in clase:
                    break 
                else:
                    btn_siguiente.click()
                    time.sleep(1)
            except:
                break
            
        detalle = ", ".join(sorted(empresas_set)) if empresas_set else "SIN OPERADORAS"     
        return total, detalle

    except Exception as e:
        return 0, f"ERROR: {str(e)[:80]}"

# ================= LÓGICA DE SCRAPING (TRANSFORMA) =================
def login_transforma(driver, wait):
    try:
        driver.get(config.URL_TRANSFORMA)
        
        try:
            if driver.find_elements(By.CSS_SELECTOR, ".cProfileMenu"):
                print("✅ Ya estabas logueado (Sesión activa).")
                return
        except: pass

        print("⏳ Esperando formulario de acceso...")

        try:
            ## ESPERAMOS QUE LOS INPUTS SEAN VISIBLES E INTERACTUABLES
            username_input = wait.until(EC.visibility_of_element_located((By.ID, config.ID_INPUT_USER)))
            password_input = wait.until(EC.visibility_of_element_located((By.ID, config.ID_INPUT_PASS)))

            # EFECTO DE TECLADO PARA USUARIO Y CONTRASEÑA
            username_input.clear()
            for char in config.TRANSFORMA_USER:
                username_input.send_keys(char)
                time.sleep(0.02)


            password_input.clear()
            password_input.send_keys(config.TRANSFORMA_PASS)
            time.sleep(0.5)

            # ENVIAR FORMULARIO
            password_input.send_keys(Keys.RETURN)

            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, ".cProfileMenu") 
                or d.find_elements(By.CSS_SELECTOR, ".comm-navigation"))
            print("✅ Login Exitoso (Dashboard cargado).")

        except TimeoutException:
            database.mostrar_error("Error Login", "No se pudo iniciar sesión en Transforma (Tiempo agotado).")
            raise
    except Exception as e:
        database.mostrar_error("Error Login Transforma", str(e))

def procesar_detalle_salesforce(driver, wait, ruc, nombre):
    # 1. DICCIONARIO BASE
    datos = {
        "numero_documento": str(ruc),
        "razon_social": nombre,          
        "pe_segmento": "SIN RESULTADOS",
        "pe_tipo_cliente": "SIN RESULTADOS",
        "ultima_asignacion": "SIN RESULTADOS",
        "proxima_desasignacion": "SIN RESULTADOS"
    }

    print(f"   🔍 Buscando: {ruc}")

    try:
        # 2. BUSCAR EN BARRA GLOBAL
        try:
            search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.forceSearchInputDesktop input")))
            driver.execute_script("arguments[0].value = '';", search_box)
            search_box.clear()
            search_box.send_keys(str(ruc))
            time.sleep(0.5)
            search_box.send_keys(Keys.RETURN)
            time.sleep(5) # Espera para resultados
        except:
            print("   ⚠️ Error en barra de búsqueda.")
            return datos 

        # 3. VALIDAR SI NO EXISTE
        try:
            no_results = driver.execute_script("""
                return document.querySelector("div.forceSearchNoResults, div.noResultsTitle") != null;
            """)
            if no_results:
                print(f"   ⚠️ Salesforce: No se encontraron resultados.")
                return datos
        except: pass

        # 4. ENTRAR AL PERFIL
        try:
            selector = "a.outputLookupLink[data-refid='recordId']"
            link = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            print("   👆 Cliente encontrado. Entrando...")
            driver.execute_script("arguments[0].click();", link)
        except TimeoutException:
            print("   ⚠️ No apareció el enlace del cliente.")
            return datos

        # 5. EXTRACCIÓN DE DATOS (SHADOW DOM FINDER)
        try:
            print("   ⏳ Esperando renderizado (5s)...")
            time.sleep(5) # Damos tiempo a que Salesforce pinte todo el Shadow DOM

            # --- SCRIPT MAESTRO: BUSCA EN PROFUNDIDAD (SHADOW DOM) ---
            # Este script recorre todas las capas ocultas hasta encontrar el atributo
            js_shadow_finder = """
            return (function(apiName) {
                // Función recursiva para atravesar Shadow Roots
                function findInShadow(root, selector) {
                    if (!root) return null;
                    
                    // 1. Intentar encontrarlo directamente en este nivel
                    var found = root.querySelector(selector);
                    if (found) return found;

                    // 2. Si no, buscar en los hijos que tengan shadowRoot
                    // Usamos TreeWalker para eficiencia
                    var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null, false);
                    while (walker.nextNode()) {
                        var node = walker.currentNode;
                        if (node.shadowRoot) {
                            var deepFound = findInShadow(node.shadowRoot, selector);
                            if (deepFound) return deepFound;
                        }
                    }
                    return null;
                }

                // Selector exacto basado en tu HTML
                var targetSelector = "div[data-target-selection-name='sfdc:RecordField.Account." + apiName + "'] lightning-formatted-text";
                
                // Iniciamos la búsqueda desde el body
                var el = findInShadow(document.body, targetSelector);
                
                if (el) {
                    return el.innerText.trim() || "VACIO"; 
                }
                return "VACIO"; 
            })(arguments[0]);
            """

            # EJECUTAMOS LA BÚSQUEDA PARA CADA CAMPO
            # Si el JS devuelve "VACIO" (porque no encontró texto o el elemento), guardamos eso.
            
            val_segmento = driver.execute_script(js_shadow_finder, "PE_Segmento__c")
            # Pequeño hack: Si el primero falla (devuelve VACIO siendo improbable), esperamos un poco más y reintentamos una vez
            if val_segmento == "VACIO":
                time.sleep(2)
                val_segmento = driver.execute_script(js_shadow_finder, "PE_Segmento__c")

            datos["pe_segmento"] = val_segmento
            datos["pe_tipo_cliente"] = driver.execute_script(js_shadow_finder, "PE_Tipo_de_Cliente__c")
            datos["ultima_asignacion"] = driver.execute_script(js_shadow_finder, "PE_ultima_fecha_de_asignacion__c")
            datos["proxima_desasignacion"] = driver.execute_script(js_shadow_finder, "PE_Fecha_de_proxima_desasignacion__c")

            print(f"   ✅ Datos extraídos: Seg={datos['pe_segmento']} | Tipo={datos['pe_tipo_cliente']}")

        except Exception as e:
            print(f"   ❌ Error JS Shadow: {e}")
        
    except Exception as e:
        print(f"   ❌ Error general SF: {str(e)[:50]}")
    
    return datos

# ================= MAIN =================
def main():
    
    gestionar_workbench()

    df = database.obtener_empresas()
    
    if df.empty:
        print("❌ No se encontraron empresas RUC 20 en la base de datos.")
        return
    
    total_empresas = len(df)
    print (f"ℹ️ Se encontraron {total_empresas} empresas 'RUC 20' para procesar.")

    print("🌐 [CHROME] Iniciando...")
    try:
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("detach", True)

        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)
        
        # PROCESO OPSITEL
        print("\n🔵 [FASE 1] Iniciando Scraping Osiptel...")
        rucs_ya_en_osiptel = database.obtener_rucs_procesados('OSIPTEL')
        print(f"   ℹ️ RUCs ya registrados anteriormente en Osiptel: {len(rucs_ya_en_osiptel)}")
        
        try:
            driver.get(config.URL_OSIPTEL)
            procesadas = 0

            for index, row in df.iterrows():
                ruc = str(row['RUC']).strip()
                nombre = str(row['NOMBRE']).strip() if row['NOMBRE'] else ""

                # VALIDACIÓN
                if len(ruc) != 11 or not ruc.isdigit():
                    print(f"   ❌ [SKIP] RUC inválido: {ruc}")
                    continue

                # VALIDACIÓN DE DUPLICADOS
                if ruc in rucs_ya_en_osiptel:
                    print(f"[{index+1}/{total_empresas}] RUC: {ruc} --> ⏩ Ya existe en BD. Saltando.")
                    continue
                
                # SI NO EXISTE, PROCESAMOS
                cantidad, detalle = consultar_ruc_osiptel(driver, wait, ruc)
                guardado = database.guardar_resultado(ruc, nombre, detalle, cantidad)
                
                estado = "💾 Guardado" if guardado else "❌ Error BD"
                print(f"[{index+1}/{total_empresas}] RUC: {ruc} --> {cantidad} líneas. ({estado})")
                procesadas += 1

            print(f"✅ Fase 1 terminada. Nuevos procesados: {procesadas}.")

        except Exception as e:
            print(f"❌ Error crítico en Fase Osiptel: {e}")
        
        # PROCESO SALESFORCE
        print("\n🔵 [FASE 2] Iniciando Scraping Salesforce...")
        rucs_ya_en_sf = database.obtener_rucs_procesados('SALESFORCE')
        print(f"   ℹ️ RUCs ya registrados anteriormente en Salesforce: {len(rucs_ya_en_sf)}")

        # VERIFICAMOS
        rucs_pendientes = [str(r).strip() for r in df['RUC'] if str(r).strip() not in rucs_ya_en_sf]

        if not rucs_pendientes:
            print("✅ Todos los RUCs ya fueron procesados en Salesforce. No hay pendientes.")
        else:
            login_transforma(driver, wait)

            for index, row in df.iterrows():
                ruc = str(row['RUC']).strip()
                nombre = str(row['NOMBRE']).strip() if row['NOMBRE'] else ""
                
                if len(ruc) != 11 or not ruc.isdigit():
                    print(f"   ❌ [SKIP] RUC inválido: {ruc}")
                    continue
                
                # VALIDACIÓN DE DUPLICADOS
                if ruc in rucs_ya_en_sf:
                    print(f"[{index+1}/{total_empresas}] Salesforce {ruc}... ⏩ Ya existe en BD. Saltando.")
                    continue

                print(f"[{index+1}/{total_empresas}] Salesforce {ruc}...")

                driver.get(config.URL_TRANSFORMA)

                try:
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.forceSearchInputDesktop input")))
                except: pass

                data_sf = procesar_detalle_salesforce(driver, wait, ruc, nombre)
                guardado_sf = database.guardar_salesforce(data_sf)
                print(f"   💾 Guardado: {'SÍ' if guardado_sf else 'NO'}\n")

        
        print("\n" + "="*50)
        print("✅ PROCESO COMPLETADO.")
        print("🔓 EL NAVEGADOR SIGUE ABIERTO.")
        print("="*50)
        input("\n🔴 Presiona la tecla [ENTER] en esta ventana para finalizar el script...")

    except Exception as e:
        database.mostrar_error("Error Crítico", f"Ocurrió un error inesperado: {str(e)}")

if __name__ == "__main__":
    main()