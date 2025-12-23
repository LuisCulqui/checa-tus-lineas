import sys
import pymysql
import pandas as pd
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import config

def mostrar_error(titulo, mensaje):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror(titulo, mensaje)
    root.destroy()

def obtener_conexion():
    try:
        return pymysql.connect(**config.DB_CONFIG)
    except pymysql.MySQLError as e:
        msg = f"No se pudo conectar a MySQL.\nVerifica XAMPP.\n\n{e}"
        mostrar_error("Error Conexión BD", msg)
        sys.exit(1)

def obtener_empresas():
    connection = obtener_conexion()
    try:
        with connection.cursor() as cursor:
            cursor.execute(config.SQL_GET_RUCS)
            response = cursor.fetchall()
        return pd.DataFrame(response, columns=['RUC', 'NOMBRE'])
    finally:
        connection.close()

def guardar_resultado(ruc, nombre, operadoras, cantidad):
    connection = obtener_conexion()
    try:
        with connection.cursor() as cursor:
            cursor.execute(config.SQL_INSERT_RESULT, (str(ruc), nombre, operadoras, cantidad))
        connection.commit()
        return True
    except Exception as e:
        print(f"   ❌ [Error DB] No se pudo guardar {ruc}: {e}")
        return False
    finally:
        connection.close()

def guardar_salesforce(data):
    
    connection = obtener_conexion()
    try:
        fecha_actual = datetime.now()

        with connection.cursor() as cursor:
            cursor.execute(config.SQL_INSERT_SALESFORCE, (
                str(data['numero_documento']), 
                data.get('razon_social', ''), 
                data.get('pe_segmento', ''), 
                data.get('pe_tipo_cliente', ''), # Nota: corregí la clave aquí para que coincida con main
                data.get('ultima_asignacion', ''),
                data.get('proxima_desasignacion', ''),
                fecha_actual
            ))
        connection.commit()
        return True
    except Exception as e:
        print(f"   ❌ [Error DB] No se pudo guardar SF {data['ruc']}: {e}")
        return False
    finally:
        connection.close()